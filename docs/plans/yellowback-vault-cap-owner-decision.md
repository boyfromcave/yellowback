# Owner decision request: per-vault bound (MINT-6b) and class C aggregate cap (W4-K-2, W4 03/new-3)

Status: **open, no code change made.** Verified against `upgrade/vault` (ycash-dd, ycash6 `src/yellowback/params.cpp`,
`math.h`, `state.cpp`): `MaxVaultCents` (D-Q-23a) exists and is the 10 % share with a $10,000 floor
(`maxVaultShareBps` 1000, `vaultShareFloorCents` 1000000). That is the rule the audit finding questions, so the
finding is not resolved; D-Q-25 moved MINT-6's base to the circulating supply without re-running the fees study.

## Evidence (audit `03-yb-calibration.md:115-153`, verification `03-verification.md:82-113`)

Circulating supply 16,972,537.5 YEC at height 3,062,423; MINT-6 cap = 0.15 x S x price = $2,545,881 x price; each vault
also capped by `maxMint` $100,000. Executable claim: $34,675 (p50 visible bid book), $25,815 (p10).

| Largest single vault at YEC price | $0.10 | $0.20 | $0.40 | $1.00 | exceeds p50 depth above | reaches maxMint at |
|---|---|---|---|---|---|---|
| Today: 1,000 bps, floor $10k | $25,459 | $50,918 | $100,000 | $100,000 | $0.136 | $0.393 |
| O1 340 bps | $10,000 | $17,312 | $34,624 | $86,560 | $0.401 | $1.155 |
| O2 1,000 bps + absolute cap $35,000 | $25,459 | $35,000 | $35,000 | $35,000 | never | - |
| O3 `maxMint` $35,000 | $25,459 | $35,000 | $35,000 | $35,000 | never | - |

Class C (`baseRatioBps[2]` = `recapRatioBps` = 50,000) is never refused by MINT-6 (`state.cpp` clause
`baseRatioBps < recapRatioBps`), so a class C vault is bounded only by MINT-6b, `maxMint` and, in aggregate, HALT-2.

## Options

- O1 lower `maxVaultShareBps` (value only; bound still scales with price and drifts with supply).
- O2 add an absolute dollar `maxVaultCents` beside the share (new Params field; tracks measured depth; recommended).
- O3 lower `maxMint` (no new field; partly reverses D-Q-24; also moves RPC and wallet ceilings).
- O4 keep 1,000 bps, record the $100,000 per-vault exposure and correct `params.cpp` and quantum plan text citing MINT-6b as a bound.
- Class C: (C-i) stay outside the aggregate cap, bounded by O2/O3; (C-ii) apply MINT-6 to every class; (C-iii) a separate higher cap.

## Recommendation

O2 with `maxVaultCents` calibrated by yb-calibration from the depth series ($25,000 at p10, $35,000 at p50 on the
2026-10-04 books), with C-i (class C bounded per vault by O2). It is one module parameter and one clause, no new
state, nothing under `src/vault/`, `src/script/`, `src/consensus/`; `maxMint` stays at D-Q-24's $100,000 as the ceiling.
If the owner prefers zero consensus movement, O4 (comment and record correction only) is the fallback.

## Consequences once decided

Record the ruling as a row amending D-Q-23a/D-Q-25 in `yellowback-quantum-plan.md` and close the fees spec item
(`yellowback-quantum-fees-spec.md:528-533`). Then, on both node lines in one commit (same branch name), change the
constant (`params.cpp`, `params.h`, `math.h`, `state.cpp`, tests, `yellowback_model.py`, golden if it moves), and re-run
the yb-calibration concentration study on the circulating base (`fees_option_d.py` `supply_rows`, its test, the
`docs/reports/2026-10-fees/` re-issue, `decisions.md` D-MP-1 G7). Land after the LOW-W4-K-4 attestor-economics correction.
