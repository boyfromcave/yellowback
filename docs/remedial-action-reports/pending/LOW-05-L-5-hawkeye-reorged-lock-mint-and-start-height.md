# LOW — 05/L-5 — A mint of a reorged-away lock is judged `Ok` (alarm only); a wrong `start_height` makes an attestor challenge and slash honest proposers

Repos / branches to change: `hawkeye` (`fix/05-L-5-exposure-pause-start-height` off `upgrade/vault`). No node change. · Audit source: `05-bridge-hawkeye-wyec.md` §L-5 (`:255-265`); `verification/05-verification.md` row L-5 (`:24`); `00-consolidated.md` row 05/L-1..L-5. · Status: pending

## 1. Finding

**Reorged lock.** `judge_minted` returns `Ok` for a lock in state `Reorged` (`crates/hawkeye/src/engine/mint.rs:110-112`): a `Minted` whose lock left the active chain after the attestor signed is recorded as fine. The only signals are the `exposure` alarm raised when the follower rewinds (`engine/ycash.rs:441-457`: `signed locks left the active chain`) and the `supply` alarm when `totalSupply > locked` (`engine/mod.rs:394-415`). Neither pauses anything: the attestor keeps signing and proposing new mints while wYEC is known to be unbacked. The wYEC cannot be clawed back (no admin burn, by design), so the only useful reaction is to stop adding exposure and get a quorum to `setPaused(true)` / lower `mintCap` while operators reconcile — which should not depend on someone watching the alarm.

**`start_height`.** `[ycash] start_height` (`crates/hawkeye/src/config.rs:85-87`, `Params.ycash_start_height`) lets an operator start the follower *after* existing locks. Such an attestor has no record of those locks; a legitimate proposal for one is `Defer` ("no lock … absent", `judge_minted:89-91`), then `challenge_if_due` challenges it when the lock is still absent `C_Y` blocks after first judging (`mint.rs:386-396`; `challenge_due:66-77`), and after the grace (`2 × C_Y + 2 × takeover + 10`, `:327`) `check_pending_mints` opens a `FRAUDULENT_MINT` case against the honest proposer (`:343-355`). The challenge is itself a griefing fault (plan §2.3) and vetoes the honest proposer for that lock (`LOW-05-L-4`). On mainnet, `start_height` has no legitimate use (the upgrade's activation height is the default, `config.rs:85-87`).

## 2. Root cause

- `crates/hawkeye/src/engine/mint.rs:110-112` — `if l.state == Reorged { return Ok(MintVerdict::Ok) }`.
- `crates/hawkeye/src/engine/ycash.rs:451-457` — `exposure` alarm only; `engine/mod.rs:514-517` — `signing_paused` ignores it.
- `crates/hawkeye/src/config.rs:85-87, 721` — `start_height` is a free field on every network; `engine/ycash.rs::start_height()` uses it when the ledger has no cursor.
- `crates/hawkeye/src/engine/mint.rs:343-355, 386-396` — pessimistic challenge and fraud case assume the ledger saw every lock since the bridge's first vault.

## 3. Fix options considered

- Treat a `Minted` on a `Reorged` lock as `Fraud` and slash the proposer: wrong — the proposer (often this attestor) acted on a lock that was `C_Y` deep; the fault is the reorg, not the signer. Rejected.
- New verdict `Exposure`: record, alarm, pause own mints until an operator acknowledges; no slash. **Chosen.**
- `start_height`: remove the field: breaks devnet scenarios that start mid-chain. Refuse on mainnet, validate elsewhere against the set's first vault. **Chosen.**

## 4. Recommended fix

### 4.1 Exposure handling (`engine/mint.rs`, `engine/ycash.rs`, `engine/mod.rs`, `hawkeye-store`)

1. `MintVerdict::Exposure(String)`; `judge_minted`: `Reorged` → `Exposure("lock left the active chain after signing")`; `check_pending_mints` handles it: transition the lock `Reorged → MintedUnbacked` (new `LockState`, terminal, with the edge in `state.rs`'s machine and a V6/V7 migration if the state column is `CHECK`-constrained — it is text; add the value to the machine, not the schema), remove the pending row, alarm `exposure` with the lock id, amount and recipient, and set `mem.exposure_pause = true`.
2. `signing_paused()` includes `exposure_pause` (mainnet and testnet; regtest alarm only) with the same scope as `HIGH-05-H-2` §4.3: own `Mint` signatures, proposals, executes and threshold mints are suppressed; challenges, cancels, heartbeats, releases and slash votes are not. `ycash.rs:451-457` sets the same flag at rewind time (the signed-but-not-yet-minted case, where the exposure can still be *prevented*: a `Signed` lock that reorged must also be **challenged if proposed** — add: on rewind, for each exposure whose lock is `Proposed`, call `challenge(pm, "the lock left the active chain")` through the existing path; the sign-once challenge record refuses only when the ledger holds a *policy-OK* lock, `signonce.rs:250-263`, and a `Reorged` lock is not in `MINTABLE`).
3. **Acknowledge**: `hawkeye exposure ack <lockId>` (new CLI; writes an `exposure_acks` row: lock id, operator note, time) clears the pause for that lock; the daemon re-reads acks every tick; a new exposure pauses again. `Status.exposure` lists unacknowledged lock ids; `/metrics` `hawkeye_exposure_unacked`.
4. Runbook (`MEDIUM-05-M-3` §10c): on `exposure`, the set pauses the bridge by quorum or lowers `mintCap` to 0 (`HIGH-05-H-2` makes a zero cap on mainnet an alarm — the runbook says to use `setPaused` instead), reconciles supply vs locks, and decides on the unbacked amount (plan Q-2 is "alarm only in v1" — this report does not change that decision; it only stops the *attestor* from adding to it).

### 4.2 `start_height` validation (`config.rs`, `engine/ycash.rs::start_height`)

- Mainnet: `ycash.start_height` is **refused** (`"mainnet refuses ycash.start_height: the follower starts at the upgrade's activation height"`).
- Testnet/regtest: when set and the ledger has no cursor, `start_height()` queries `vault_list tag=<tag> setid=<set> kind=vault` (the engine already does this for `locked_value`, `mod.rs:302-315`) and, if any vault's height `< start_height`, refuses to start: `"ycash.start_height {h} is above the set's oldest {tag} vault at {min}: this attestor would challenge and slash honest proposals for locks it never saw"`; `--i-accept-blind-start` overrides off-mainnet (devnet scenarios that intentionally start late must say so).
- When the ledger **has** a cursor, `start_height` is ignored (already) — log that it is ignored so an operator does not think a change took effect.
- Additionally, in `check_pending_mints`, the pessimistic challenge of an *absent* lock requires `caught_up` **and** that the ledger's Ycash cursor started at or below the proposal's lock height is unknowable (the lock id is a hash) — so instead require that the follower's `start_height` recorded in the ledger (`chain_cursor` start marker, add `meta.ycash_start_height`) is ≤ the set's first vault height (checked once at start-up as above); the runtime check is then unnecessary. Keep the challenge logic unchanged.

## 5. Tests

- `tests/engine.rs` `u_minted_on_reorged_lock_pauses_own_mints`: lock signed and proposed; the mock reorgs the lock's block away (`MockState` has a reorg helper, used by `reorg.rs` store tests — or build the fork via `mine` on a different branch); `Minted` arrives (anvil) → lock `MintedUnbacked`, `exposure` raised, next policy-OK lock is **not** signed/proposed until `exposure ack`; challenges still work (a rogue proposal is challenged during the pause).
- `u2_signed_then_reorged_proposal_is_challenged`: lock `Signed` and proposed; reorg before `Minted` → the attestor challenges its own proposal (`own_fraudulent_mint` is not raised: this is not fraud; a dedicated log `own_proposal_withdrawn`).
- `config.rs` tests: `start_height` on mainnet refused; `engine` test `u3_blind_start_refused`: mock with a vault at height 10, `start_height = 50` → `start_height()` errors with the message; with the override, the old pessimistic behaviour (documented) is observable.
- Store: `MintedUnbacked` edges in `transitions.rs`; `exposure_acks` table in `migrations.rs` `TABLES`.

## 6. Acceptance criteria

1. A mint over a reorged lock ends in `MintedUnbacked`, pauses this attestor's mint-side signing, and is visible in `status`/`metrics` until acknowledged.
2. A proposed-but-unminted reorged lock is challenged by its own proposer.
3. Mainnet refuses `start_height`; other networks refuse a `start_height` above the set's oldest vault unless overridden.

## 7. Risks and side effects

- A reorg deeper than `C_Y` is the trigger; with `MEDIUM-05-M-4`'s floor (`C_Y ≥ 20`) it is rare; when it happens the bridge *should* slow down.
- Pausing own mints on an exposure is per attestor; other attestors continue unless they saw the same reorg (they did: it is the chain). A quorum pause is still an operator act.
- No contract change, no key rotation, no node change.

## 8. Effort estimate and dependencies

1.5 days. Shares `signing_paused` scope with `HIGH-05-H-2` (land after it) and the schema migration slot with `HIGH-05-H-1`.
