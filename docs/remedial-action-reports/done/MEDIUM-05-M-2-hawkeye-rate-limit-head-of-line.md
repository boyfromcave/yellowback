# MEDIUM — 05/M-2 — Rate-limit head-of-line blocking: an over-cap burn parks every later release forever

Repos / branches to change: `hawkeye` (`fix/05-M-2-over-cap-burn` off `upgrade/vault`); `wyec` only through an optional §10 change request (CR-W5, §4.4). No node change. · Audit source: `05-bridge-hawkeye-wyec.md` §M-2 (`:163-180`); `verification/05-verification.md` row M-2 (`:17`); `00-consolidated.md` row 05/M-2, recommendation R7. · Status: done — completed 2026-10-13T06:11Z (merged locally on `upgrade/vault`; not yet pushed)

## 1. Finding

As leader, `Engine::burns` (`crates/hawkeye/src/engine/burn.rs:80-98`) walks the assigned burns in nonce order and, when `b.amount > available` (`set_getinfo.unlockavailable`, the set's remaining cap for the current epoch: `ycash-dd/src/rpc/vault.cpp:295-302`), parks the burn `WaitingCap` and `break`s — "FIFO: later burns wait behind it". HK-8 (plan §12) forbids splitting a burn. At the next epoch `available` is at most the **full** window cap; a burn larger than that is parked again (`burn_cap_released` → `Finalized` → assigned → `WaitingCap`, `:31-43, 84-96`), every epoch, and every later nonce waits behind it, forever. The same `WaitingCap` transition fires on the node's `bad-txns-vault-rate` rejection (`:218-234`).

`burn` has no per-transaction maximum (`wyec/contracts/WyecBridge.sol:289-293`; the Ethereum `mintCap` bounds mints, not burns), so a holder of more than one window's cap of wYEC — accumulated across locks, since `MAX_LOCK` is per lock — burns it in one transaction and stalls every release after that nonce until governance raises `ratelimitbps` or handles the burner out of band. Accidental or deliberate, a cheap liveness attack; the burner loses nothing (its burn is eventually paid when the cap is raised).

## 2. Root cause

- `crates/hawkeye/src/engine/burn.rs:84-96` — `break` on `amount > available` without distinguishing "does not fit this epoch's remainder" from "never fits a full epoch".
- `crates/hawkeye/src/engine/burn.rs:218-234` — the node-rejection path parks the same way.
- `hawkeye/docs/hawkeye-bridge-plan.md:562-566` (§5.5) and HK-8 — "waits for the next epoch, FIFO by burn nonce, never splitting".
- `wyec/contracts/WyecBridge.sol:289-293` — no burn maximum (by design, R2: the contract knows nothing about Ycash parameters).

## 3. Fix options considered

| Option | Verdict |
|---|---|
| (a) Split an over-cap burn into several intents across epochs (matcher sums intents per nonce; memo gets a part index) | Changes the normative memo (§4.3), the matcher (§3.2 "one burn ↔ one intent", HK-4/HK-8), the consensus-visible shape every watcher judges, and the benign-race rule (two intents for one burn are the fraud signature today). Too large for a fix; recorded as the v2 design option. |
| (b) Skip an over-cap burn (serve later nonces) and alarm | Small, local to `burns()`, preserves FIFO for burns that fit. **Chosen.** |
| (c) Contract-side per-burn maximum (`maxBurn`, threshold-set, synchronised with the Ycash cap) | Needs a wyec change plus governance synchronisation of a parameter that lives on Ycash; mis-sync either blocks legitimate burns or does nothing. Optional CR-W5, not blocking. |
| (d) Client-side pre-check in `hawkeye burn` | Helps honest users, does nothing against a deliberate burn; included as a courtesy. |

## 4. Recommended fix

### 4.1 `burns()` (`engine/burn.rs:71-103`)

Compute the full window cap from the set: `cap_full = epochbasis × ratelimitbps / 10_000` (`Set.epochbasis`, `SetParams.ratelimitbps`, `hawkeye-ycash/src/types.rs:17-43`; `ratelimitbps == 0` means no limit → `None`). Then:

```rust
for b in assigned {
    if b.leader != Some(self.ctx.me) { continue; }
    if let Some(full) = cap_full && b.amount > full {
        // never serviceable under the current parameters: park it out of the FIFO and alarm
        self.ctx.db(|t| t.burn_wait_cap(&b.key, u64::MAX /* "over cap", not an epoch */, Some(tip)))?;
        self.alarm("burn-over-cap", format!("burn {} ({} zat) exceeds the set's full-window cap {} zat (ratelimitbps {}, epochbasis {}); it waits for a governance change", b.key.nonce, b.amount, full, bps, basis));
        continue;                       // later nonces are served
    }
    if let Some(av) = available && b.amount > av {
        … existing WaitingCap + break (FIFO for burns that fit a full window) …
    }
    …
}
```

`burn_cap_released` (`:31-43`) must **not** release an over-cap burn on an epoch turn (`waiting_epoch == u64::MAX` means "until the cap changes"); instead, re-evaluate over-cap burns whenever the set's `ratelimitbps`/`epochbasis` change (compare with the previous tick's values in `Memory`) and release them to `Finalized` when `amount ≤ cap_full`. Store: add `BurnState::WaitingCap` reason text to the transition (`"over-cap"` vs `"epoch"`) so `/burns/<nonce>` and `hawkeye status` show which; no schema change (`waiting_epoch` already exists; `u64::MAX` is the sentinel — document it in `burns.rs`).

The node-rejection path (`:218-234`): keep, but if the rejection's reason says the amount exceeds the cap even for an empty epoch (compare against `cap_full`), route to the over-cap branch.

### 4.2 Status and metrics

`Status.burns` already counts states; add `burns_over_cap` and a `hawkeye_burn_over_cap` gauge (`status.rs`); the alarm clears when no over-cap burn remains. `GET /burns/<nonce>` shows `state = "waiting_cap"`, `reason = "over-cap"`.

### 4.3 `hawkeye burn` pre-check (`cli.rs`)

Before sending, read `set_getinfo` and refuse `amount > cap_full` with: `"this burn exceeds the attestor set's per-window cap ({full} YEC): it would not be released until the set raises its rate limit; pass --allow-over-cap to burn anyway"`.

### 4.4 Optional change request (plan §10)

| # | Repo | Change | Why | Blocking? |
|---|---|---|---|---|
| CR-W5 | wyec | `maxBurn` (uint256, 0 = none) set by the threshold through `SetBurnLimit(uint256 maxBurn,uint256 adminNonce)`; `burn` reverts `BurnTooLarge(amount, maxBurn)` above it; the guardians keep it ≤ the Ycash full-window cap | makes an over-cap burn impossible rather than merely harmless; needs a new EIP-712 struct → vectors, Hawkeye binding, re-pin | no |

### 4.5 Docs

Plan §5.5: "an over-cap burn is parked out of the FIFO with alarm `burn-over-cap`; it is released when the set's cap rises". `wyec/docs/wyec-contract-design.md` §4.2 (Burn): one sentence that a burn above the Ycash set's window cap is not released until the set's parameters change. Runbook (`MEDIUM-05-M-3`): the governance action for an over-cap burn (`SET_PARAMS` raise, or a one-off threshold decision to leave it).

## 5. Tests

- `tests/engine.rs` `p_over_cap_burn_does_not_block_later_burns`: set with `ratelimitbps` such that cap_full = 5 YEC; burns `n` (8 YEC), `n+1` (1 YEC), `n+2` (1 YEC); after ticks across two epochs, `n+1` and `n+2` are released, `n` is `WaitingCap` with reason over-cap, alarm raised; raise the set's `ratelimitbps` (mock `set_getinfo`) → `n` is released next tick; alarm cleared.
- `p2_fifo_kept_for_burns_that_fit`: cap_full = 5; burns 4, 3, 1 → `4` released, `3` waits (break), `1` waits behind it (unchanged behaviour), next epoch `3` and `1` go.
- `cli` unit test for the pre-check message.

## 6. Acceptance criteria

1. An over-cap burn never stalls a later nonce; it is visible in `/status`, `/metrics` and `/burns/<nonce>` with the reason.
2. FIFO semantics for in-cap burns are byte-for-byte the old behaviour (existing tests `b_*`, `e_*` unchanged).
3. The alarm clears and the burn is released after a cap raise without a restart.

## 7. Risks and side effects

- **Fairness**: an over-cap burner waits indefinitely by design; its funds are not lost (released when the cap allows). Documented.
- **Bridge downtime / key rotation / contract redeploy**: none.
- **Consensus**: none; the set's rate limit is unchanged.

## 8. Effort estimate and dependencies

1.5 days including tests and docs. No dependencies; `MEDIUM-05-M-3` references the alarm.

## Completion record

- **Completed:** 2026-10-13T06:11Z
- **hawkeye** `upgrade/vault` merge f693026 (branch `fix/bridge-misc`): 3b5c75e (over-cap burn parked out of the FIFO, alarm `burn-over-cap`, `burns_over_cap` status/gauge, `/burns` `reason`, `hawkeye burn` pre-check with `--allow-over-cap`), 957a076 (plan §5.5, HK-8).
- **Tests:** 301 passed, 0 failed at 957a076 (`HAWKEYE_REQUIRE_ANVIL=1 cargo test --workspace --all-features --locked`); clippy, fmt and rustdoc clean. New: `p_over_cap_burn_does_not_block_later_burns` and the `cap_plan` unit tests. §6 criteria 1–3 met.
- **Choice:** the cap basis is max(`epochbasis`, `lockedvalue`), so a burn that fits the next epoch is not parked.
- **Open:** CR-W5 (a wyec `maxBurn` field) is optional and recorded in hawkeye plan §10.
