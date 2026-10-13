# LOW — 04/N-1 — ZIP-317 unpaid-action gate (opt-in) and ZIP-401 low-fee penalty on ycash6 vs ycash-dd-fee PQ transactions: fee guidance for Yellowback clients and relays

**Repos / branches to change:** `ycash-dd` (wallet PQ fee default: `src/init.cpp` `-pqfeerate`, `src/wallet/wallet.cpp`, `src/yellowback/txbuilder.cpp`), branch `fix/04-N-1-pq-fee-conventional` off `upgrade/vault`; `ycash6` (`doc/yellowback-release.md`, `doc/yellowback-mining.md` release/operator notes), same branch name; `yellowback` workspace `docs/mapping.md` row; client follow-ups (YEW, Hawkeye) as issues, not in this report's scope.
**Audit source:** `verification/04-verification.md` §New findings N-1 (`:150-171`) (new by the verifier; no first-wave section); `docs/mapping.md:1058` (ZIP-401 row), `:1129` (wallet PQ fee row).
**Status:** done — completed 2026-10-13T07:30Z (merged locally on `upgrade/vault`; not yet pushed)

## 1. Finding

ZIP-317 is compiled and wired on ycash6 but off by default: `DEFAULT_TX_UNPAID_ACTION_LIMIT = DEFAULT_BLOCK_UNPAID_ACTION_LIMIT = SIZE_MAX`, so the unpaid-action rejection in `AcceptToMemoryPool` is a no-op unless an operator passes `-txunpaidactionlimit=0` — which `zip317.h` documents as a supported per-node opt-in. On such a node a PQ spend that pays ycash-dd's wallet fee is refused: an SLH-DSA spend carries ~7,938 B of scriptSig, which ZIP-317 counts as `ceil(7938/150) = 53` logical actions → conventional fee `53 × 500 = 26,500` zat (ycash6 `MARGINAL_FEE = 500`), while dd's wallet pays `max(1000, rate × size)` ≈ 1,000 zat at the default rate; every dd node relays the transaction, the opted-in ycash6 node answers `tx unpaid action limit exceeded`. Without the opt-in, the ZIP-401 limiter still adds `LOW_FEE_PENALTY = 40,000` to the eviction weight of any transaction paying under its conventional fee (~5× a 10,000-cost transaction), so under mempool pressure ycash6 nodes evict dd-fee PQ spends first; dd's limiter penalises only `fee < DEFAULT_FEE`. x402 already pays the conventional fee; YEW- and Hawkeye-built PQ spends depend on their fee choice. Policy, not consensus; the default network accepts the same set on both lines. Low.

## 2. Root cause

- ycash6 `e866c45` `src/zip317.h:16-18` (`MARGINAL_FEE = 500`, `GRACE_ACTIONS = 2`, `P2PKH_STANDARD_INPUT_SIZE = 150`), `:28-54` (off-by-default rationale and the `-txunpaidactionlimit=0` opt-in), `src/zip317.cpp:24-39` (`CalculateLogicalActionCount`), `src/main.cpp:2090-2103` (the gate), `src/mempool_limit.cpp:42-50` + `mempool_limit.h:25` (ZIP-401 penalty when `fee < tx.GetConventionalFee()`).
- ycash-dd `055d9c2` `src/init.cpp:548-552`, `:1225-1227` (`-pqfeerate` defaults to `-minrelaytxfee`; `-pqfeeusdperkb` / `-yellowbackfeeusdperkb` dollar-per-kB pricing at the attested price), `src/wallet/wallet.cpp:5951` (PQ input fee = max(flat, rate × size)), `src/yellowback/txbuilder.cpp:64` (same policy for YED builders).
- `docs/mapping.md:1129` ("an SLH owner redeem pays ~27,000 zat on 6 vs 1,000 on dd at the default rate"), `:1058` (ZIP-401 constants differ: dd `LOW_FEE_PENALTY = 16000` when `fee < DEFAULT_FEE`; y6 `40000` when below conventional).
- `x402-ycash/packages/ycash/src/tx/fee.ts:44` pays the conventional fee (unaffected).

## 3. Fix options considered

1. Lower ycash6's conventional fee for PQ inputs (e.g. count a PQ scriptSig as one action): changes 6.20.0's ZIP-317 accounting, a line-specific policy fork that the release line would carry alone. Rejected.
2. **Raise the floor on the dd side and in the clients:** every Yellowback wallet/builder pays at least the ZIP-317 conventional fee for a transaction with PQ inputs (`500 × max(2, max(ceil(in_size/150), ceil(out_size/34)))`), on both lines — dd's `-pqfeerate` fallback computes it as a third `max` term. 26,500 zat ≈ $0.0x at any plausible YEC price; the dollar-per-kB policy (`-pqfeeusdperkb`) already prices by size and will exceed it whenever the attested price is low. **Recommended.**
3. Documentation only: "keep `-txunpaidactionlimit` at its default on Yellowback relays". Necessary in any case (an operator can still opt in), insufficient alone because of the ZIP-401 eviction order. **Recommended in addition.**

## 4. Recommended fix

ycash-dd:
1. Add `CAmount ConventionalFeeZip317(const CTransaction&)` (or reuse the size-based helper the PQ fee code already has) in `src/yellowback/policy.{h,cpp}` with ycash6's constants (500 / 2 / 150 / 34), documented as "the release line's ZIP-317 conventional fee; dd pays it so both lines relay and rank the transaction identically".
2. PQ input fee (`wallet.cpp:5951` region) and YED builders (`txbuilder.cpp:64` region): `fee = max(flat, rate × size, ConventionalFeeZip317(tx))`; the probe that sizes stand-in signatures (mapping `:1129` row) already yields the sizes needed.
3. `-pqfeerate` help (`init.cpp:548`): mention the conventional floor. `doc/yellowback-rpc.md` / `vault-rpc.md` fee sections updated; `yellowback_fees.py` (dd) asserts the new floor for an SLH-DSA owner redeem (≥ 26,500 zat at the default rate) and that `-pqfeeusdperkb` still dominates when higher.

ycash6:
4. `doc/yellowback-release.md` and `doc/yellowback-mining.md`: "Yellowback relays and pools keep `-txunpaidactionlimit` / `-blockunpaidactionlimit` at their defaults (SIZE_MAX); a node that opts in refuses PQ spends paying less than the ZIP-317 conventional fee (~26,500 zat for an SLH-DSA input) that every other node relays; the ZIP-401 limiter ranks such spends first for eviction under pressure". `yellowback_mempool_limits.py` (ycash6-only suite) gains a case: a dd-fee (1,000 zat) SLH-DSA spend is relayed by default, refused with `-txunpaidactionlimit=0`, and evicted first when the mempool is filled past `-mempooltxcostlimit`.

Clients (issues, 06 area): YEW (`yew/core`) and Hawkeye's fee computation pay `max(their current fee, ZIP-317 conventional)`; lightwalletd's `rpcversion` contract is unaffected (fees are client-side).

Workspace:
5. `docs/mapping.md` §22: a row "ZIP-317/401 interaction across lines: dd-fee PQ spends vs opt-in gate and eviction order" with the citations above (rule 5); `docs/plans/yellowback-quantum-spec.md` §4.5 fee note: "wallets pay at least the ZIP-317 conventional fee for PQ inputs on both lines".

Consensus footprint: none (wallet fee policy and documentation).

## 5. Tests

- dd `yellowback_fees.py`: floor assertion (§4 step 3); `vault_pq_wallet.py`: an owner redeem built by `vault_ownerspend` pays ≥ the conventional fee.
- ycash6 `yellowback_mempool_limits.py`: the three-way case (§4 step 4).
- Cross-line: the devnet walk (`yellowback_devnet_upgrade.py`) mixes dd- and ycash6-built transactions where it already does; no change.

## 6. Acceptance criteria

- A PQ-input transaction built by either line's wallet pays ≥ ycash6's conventional fee and is relayed by a ycash6 node started with `-txunpaidactionlimit=0`.
- ycash6 release notes carry the operator guidance; mapping row and spec note present; both lines' fee suites green.

## 7. Risks and side effects

- Users on dd pay ~26× the previous minimum for SLH-DSA spends (still fractions of a cent); Falcon spends (~1.6 KB → 11 actions → 5,500 zat) rise less. The `-pqfeerate` override remains for operators who want the old floor on a dd-only network (documented as "may be refused/evicted by ycash6 relays").
- No effect on consensus or on already-signed transactions.

## 8. Effort estimate and dependencies

~2 hours dd wallet + tests, ~1 hour ycash6 docs + test case, client issues filed. No dependencies; coordinate with 06-area fee work in YEW/Hawkeye.

## Completion record

- **Completed:** 2026-10-13T07:30Z
- **ycash-dd** merge b8d6fd141: e782967a7, 182cb58e0, 64af46163.
  - `Zip317ConventionalFee` in `src/policy/policy.{h,cpp}` (ycash6's constants) is a floor in wallet `CreateTransaction`, `vault_ownerspend`, the YED builders (a pre-signing estimate) and the small-vault clamp.
  - The `-pqfeerate` help and `doc/vault-rpc.md` describe the floor; the contract is regenerated.
- **ycash6** merge 32b5df099:
  - 7922d7513: release and mining operator guidance; unit case `pq_zip317_low_fee_penalty`.
  - 5da505118: `yellowback_mempool_limits.py` §3 (a 1,000-zat SLH-DSA spend is refused at `-txunpaidactionlimit=0` and relayed at the defaults).
- **Workspace** a9ddc71: mapping rows.
- **Tests:** ycash-dd 114 unit cases; `yellowback_fees`, `vault_pq*` and `yellowback_pq*` functional tests pass; ycash6 mempool_limits passes. §6 met locally.
- **Choices:**
  - The floor is unconditional, as on ycash6; no opt-out.
  - The report's "evicted first" functional case was replaced by a unit test of the eviction weight, because the limiter evicts at random by weight and the functional case would be flaky.
- **Open:**
  - YEW and Hawkeye should pay `max(their fee, the ZIP-317 conventional fee)` for PQ spends; x402 already does.
  - Non-PQ YED transactions with many outputs on ycash-dd can still pay below the conventional fee (outside this report's scope).
