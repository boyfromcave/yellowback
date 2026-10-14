# LOW — 04/F-5 — ycash-dd's `vault_upgrade.py` tests Vault-after-Sapling; mainnet is Vault-after-Canopy (never exercised on dd)

**Repos / branches to change:** `ycash-dd` (`qa/rpc-tests/vault_upgrade.py`, `src/test/vault_script_tests.cpp`), branch `fix/04-F-5-upgrade-topology` off `upgrade/vault`. ycash6 unchanged (already tests Canopy → Vault).
**Audit source:** `04-cross-line-parity-activation.md` §F-5 (`:186-201`); `verification/04-verification.md` row F-5 (`:70`), detail (`:108-112`).
**Status:** done — completed 2026-10-13T11:21Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13, re-confirmed 2026-10-14 at ycash-dd 3fe3492b6 and ycash6 1ebfee622; nightly tier pending the owner's dispatch)

## 1. Finding

Regtest defaults set every upgrade to `NO_ACTIVATION_HEIGHT` on both lines, and each line's `-nuparams` handling differs: ycash6 back-fills unset upgrades below the highest one named (excluding Vault, so `-nuparams=6d5b7a31:<h>` alone never schedules NU5..NU6.2), ycash-dd does not back-fill at all. ycash-dd's `vault_upgrade.py` starts its nodes with the Vault `-nuparams` only and asserts the previous epoch is **Sapling**; ycash6's uses `YCASH_UPGRADE_ARGS` (Ycash, Blossom, Heartwood, Canopy at height 1) and asserts **Canopy**. On every public network the transition will be Canopy → Vault, with four never-activated upgrades (NU5..NU6.2 on ycash6; NU5 on dd) between them in the index for `PrevEpochBranchId`'s walk-back to skip. dd's suite therefore never exercises the only topology that will happen; the walk-back code is identical on both lines and ycash6 tests it, so the risk is Low — but dd is also the line the hardening fallback and most client CI run against.

## 2. Root cause

- ycash-dd `055d9c2` `qa/rpc-tests/vault_upgrade.py:94` `args = [nuparams(VAULT_BRANCH_ID, ACTIVATION), '-debug=mempool']`; previous-epoch assertions at `:194-195`, `:247` (Sapling); `src/consensus/upgrades.cpp:197-204` `PrevEpochBranchId` walk-back; `src/test/vault_script_tests.cpp` checks `UPGRADE_VAULT == UPGRADE_NU5 + 1`.
- `YCASH_UPGRADE_ARGS` exists on dd (`qa/rpc-tests/test_framework/yellowback_util.py:132`) and is already used by `vault_pq_reorg.py:71` and `yellowback_upgrade.py:53`.
- ycash6 `e866c45` `qa/rpc-tests/vault_upgrade.py:78` `YCASH_UPGRADE_ARGS + [nuparams(VAULT_BRANCH_ID, ACT), '-txindex']`; `src/init.cpp:1495-1505` back-fill excluding Vault.
- `SANITIZER_SCRIPTS` runs `vault_upgrade` on dd only (`yellowback-tests.yml:91`).

## 3. Fix options considered

1. Switch dd's `vault_upgrade.py` to `YCASH_UPGRADE_ARGS` and Canopy assertions, dropping the Sapling-direct topology. Loses a cheap check of the one-gap walk-back. 
2. Parametrise: run the suite's epoch assertions under the mainnet topology (Canopy at 1) and keep a short Sapling-direct section (the walk-back over one unactivated index). **Recommended**: mainnet topology becomes the main run; the Sapling-direct case moves to a unit test where it is free.
3. Make dd back-fill like ycash6: a node change for a test; and dd's "set only what is named" is simpler. Rejected.

## 4. Recommended fix

ycash-dd only:
1. `qa/rpc-tests/vault_upgrade.py:94`: `args = list(YCASH_UPGRADE_ARGS) + [nuparams(VAULT_BRANCH_ID, ACTIVATION), '-debug=mempool']` (import from `yellowback_util` as `vault_pq_reorg.py:43` does); update the previous-epoch assertions (`:194-195`, `:247`) to Canopy's branch id (`0xe9ff75a6`), and the `old-consensus-branch-id` case (a signature bound to the **Canopy** branch is rejected after activation, matching the mainnet event). Keep `-txindex` if any assertion needs it (ycash6 passes it).
2. `src/test/vault_script_tests.cpp` (the `UPGRADE_VAULT == UPGRADE_NU5 + 1` case): add `PrevEpochBranchId` assertions for both topologies on regtest params: (a) Canopy at 1, NU5 unset, Vault at 10 → prev of 10 is Canopy; (b) Sapling only, Vault at 10 → prev is Sapling; (c) at heights below Vault, `CurrentEpochBranchId` is Canopy/Sapling respectively. This keeps the one-gap case dd's suite drops.
3. CI: `vault_upgrade` stays in `YELLOWBACK_SCRIPTS` and `SANITIZER_SCRIPTS` on dd (no list change).
4. `docs/mapping.md` §19/§22: the existing row on `-nuparams` back-fill gains "both suites now test Canopy → Vault; the one-gap walk-back is a dd unit test".

## 5. Tests

The change is tests; confirm the Canopy-bound-signature negative fails if `PrevEpochBranchId` is stubbed to return Sapling (local experiment, PR note).

## 6. Acceptance criteria

- dd's `vault_upgrade.py` runs with Canopy active below Vault and asserts the Canopy → Vault epoch change, the `old-consensus-branch-id` rejection of a Canopy-bound signature after activation, and the existing CSV/BIP68/opcode properties; passes in the functional shard and under the sanitizer run.
- Unit test covers both walk-back topologies.

## 7. Risks and side effects

None to code. Blocks mined under Canopy on regtest use Canopy's funding-stream rules on dd; the harness's `mine_block_raw` / `generate` already handles that in `yellowback_upgrade.py`.

## 8. Effort estimate and dependencies

~1–2 hours. No dependencies.

## Completion record

- **Completed:** 2026-10-13T11:21Z
- **Merged:** with fix/ci-guard: 9be306bb7 (vault_upgrade.py runs Canopy below Vault, NU5 unscheduled; a Canopy-bound signature refused as old-consensus-branch-id) plus the integration fix 886927344 (restart with YCASH_UPGRADE_ARGS). Passes.
- **Verification:** Integration run 2026-10-13 (both node lines built; full test_bitcoin dd 872/872, ycash6 923/923; qa/yellowback-audit.sh dd --mode upgrade rc 0 (18 PASS), ycash6 --report-only rc 0; functional suites pass; vault_vectors / golden / pq vectors byte-identical across lines). Logs: wt/scratch/integ/.
