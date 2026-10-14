# LOW — 07/F-9 — Regtest `nVaultMinSetMaturity` lowered 8→2 to fit the suites; add a functional below-floor rejection

**Repos / branches to change:** `ycash-dd` and `ycash6` (`qa/rpc-tests/vault_primitive.py`, `vault_rpc_contract.py`, `doc/vault-rpc.md`), branch `fix/07-F-9-maturity-floor-test` off `upgrade/vault` in each. No chain-parameter change.
**Audit source:** `07-node-rpc-mempool-durability-ci.md` §F-9 (`:212-222`) and the "Recent test changes" row for `1a55aca` (`:278`); `verification/07-verification.md` row F-9 (`:19`), detail (`:103-108`).
**Status:** done — completed 2026-10-13T11:21Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13, re-confirmed 2026-10-14 at ycash-dd 3fe3492b6 and ycash6 1ebfee622; nightly tier pending the owner's dispatch)

## 1. Finding

Commit `1a55aca` (2026-10-11) changed regtest's `Consensus::Params::nVaultMinSetMaturity` from 8 to 2 and raised the suites' maturity-1 sets to 2 so the existing functional suites kept passing — a "change the chain to fit the tests" commit, the only one of its kind in the audit window. The verifier found it benign: the 8 was introduced the same day with D-Q-31 and the bridge-shaped regtest sets already used 2–3, so this is a regtest scaling parameter settling, not a rule relaxed to hide a failure; mainnet/testnet stay at 16,128 (14 days). The residual gap stands: the D-Q-31 floor (`maturity ≥ MinSetMaturity()` → `bad-vault-act-params`) is exercised by a C++ unit test and by the Python model's constant assertion, but **no functional path ever submits a below-floor `SET_CREATE` to a node and asserts the rejection**, in the mempool or in a block, and nothing checks that `set_create`'s RPC default is the network minimum. Low (test fidelity).

## 2. Root cause

ycash-dd `055d9c2`:
- `src/chainparams.cpp:625` `consensus.nVaultMinSetMaturity = 2;   // D-Q-31 scaled for the suites …`; `src/consensus/params.h:265` default `16128`; `src/init.cpp:1319` `vault::SetMinSetMaturity(...)`; `src/vault/state.cpp:616-617` getter/setter, `:696` `if (act.create.maturity < MinSetMaturity()) return "bad-vault-act-params"`.
- Covered: `src/test/vault_state_tests.cpp:685-705` `min_set_maturity` (16,128 − 1 rejected, 16,128 ok; `SetMinSetMaturity(8)`: 7 rejected, 8 ok); `qa/rpc-tests/test_framework/test_vault.py:634-643` (model constants `(16128, 2, 2)` and a model-level maturity-7 rejection under floor 8).
- Not covered: `qa/rpc-tests/vault_primitive.py:112-128` lists the `SET_CREATE` parameter negatives (threshold > seats, unknown flag, sizes) — no `maturity` case; `grep -rn maturity.*bad-vault-act qa/rpc-tests` empty; `vault_rpc_contract.py:67` creates with `maturity: 2` only. `doc/vault-rpc.md:171,174` state the default and the D-Q-31 window.
- ycash6 `e866c45`: `src/chainparams.cpp:700`, `src/consensus/params.h:233`; same suites.

## 3. Fix options considered

1. Restore regtest to 8 and raise every suite's maturities: churn in six suites for no added coverage. Rejected.
2. Add a regtest-only `-vaultminsetmaturity=<n>` override so a functional test can run the floor at 8 or 16,128: a new flag and `init.cpp` plumbing for one assertion the C++ unit test already makes. Rejected (gold-plating); keep it in mind for the devnet if a 14-day-shaped window is ever wanted there.
3. **Add the functional negative at the regtest floor itself**: `maturity: 1` (below 2) is `bad-vault-act-params` in the mempool and in a block; `set_create` without `maturity` uses the network minimum; `set_create` with `maturity: 1` is an RPC error. Minimal, exercises the real node path. **Recommended.**

## 4. Recommended fix

Both lines (suites are ported by delta; the harness helpers exist on both):

1. `qa/rpc-tests/vault_primitive.py` next to `:112-128`: 
   ```python
   bad = dict(create, maturity=1)   # below the regtest floor (nVaultMinSetMaturity = 2, D-Q-31)
   self.reject(self.raw_act_hex(v.encode_act(bad, check=False)), 'bad-vault-act-params',
               'bad-vault-act-params', 'SET_CREATE maturity below MinSetMaturity')
   ```
   `self.reject` already asserts both the mempool reason and the block reason (its two reason arguments). If `v.encode_act(..., check=False)` refuses `maturity=1` on the model side, pass the model's regtest floor explicitly (`MIN_SET_MATURITY_REGTEST`, `vault.py`).
2. `qa/rpc-tests/vault_rpc_contract.py` (`:67`): add `set_create` with `maturity: 1` → `assert_rpc_error('maturity', ...)` (the RPC validates `maturity ≥ MinSetMaturity()`, `src/rpc/vault.cpp` parameter validation per 07 "Checked and found sound"), and `set_create` without `maturity` → `set_getinfo` reports `maturity == 2` (regtest).
3. `doc/vault-rpc.md:171-174`: already says "`maturity` the network's minimum" and names 2 on regtest; add one sentence that regtest's 2 is a scaling value and that the 14-day mainnet floor is pinned by `vault_state_tests` `min_set_maturity`.
4. `docs/audits/.../07` row for `1a55aca` is the record; no mapping row needed.

## 5. Tests

The change *is* tests. Run `vault_primitive`, `vault_rpc_contract` on both lines; confirm the new negatives fail when `state.cpp:696` is commented out locally (the "would have caught it" check).

## 6. Acceptance criteria

- A below-floor `SET_CREATE` is refused by the node in the mempool and in a block with `bad-vault-act-params` in a functional suite on both lines; `set_create` refuses `maturity: 1` and defaults to the network minimum.
- No chain-parameter change; `vault_state_tests` `min_set_maturity` unchanged.

## 7. Risks and side effects

None (tests and one doc sentence).

## 8. Effort estimate and dependencies

~1 hour both lines. No dependencies.

## Completion record

- **Completed:** 2026-10-13T11:21Z
- **Merged:** with fix/ci-guard: ef05bcacb / 7d2c7d9c8 (a below-floor SET_CREATE refused in mempool and block; set_create help states the network minimum).
- **Verification:** Integration run 2026-10-13 (both node lines built; full test_bitcoin dd 872/872, ycash6 923/923; qa/yellowback-audit.sh dd --mode upgrade rc 0 (18 PASS), ycash6 --report-only rc 0; functional suites pass; vault_vectors / golden / pq vectors byte-identical across lines). Logs: wt/scratch/integ/.
