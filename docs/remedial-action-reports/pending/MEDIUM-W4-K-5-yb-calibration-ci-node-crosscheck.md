# MEDIUM — W4-K-5 — yb-calibration's CI never reaches the node: clone-backed tests skip, delegated-kernel parity is tautological, the release-constants test never reads `params.cpp`, and the drift test pins the v3 drift as passing

**Repos / branches to change.** `yb-calibration` only, new branch `fix/W4-K-5-ci-node-crosscheck` off `upgrade/vault`: `.github/workflows/ci.yml` (new job), `src/ybcal/model/{cli.py,parity.py,vendor.py}`, `src/ybcal/studies/fees_option_d.py` (`ReleaseConstants` gains the node commits it was built against), new `tests/node/test_release_constants_vs_node.py`, `tests/model/test_vendor.py`, `tests/model/test_worked_examples.py`, `tests/conftest.py` (a "required clone" mode), `Makefile` (`make ci-node`). No change in `ycash-dd`/`ycash6` (they are fetched read-only by CI).
**Audit source.** `docs/audits/quantum-vault-ecosystem-wave4/03-yb-calibration.md:225-233` (W4-K-5, fix), `:286-304` (test-fidelity table: self-referential vendor check, clone tests skipped in CI, tautological delegated parity, `test_release_constants_are_the_recommendation_as_built` never reads the node, `test_supply_rows_and_rule_cap` asserts the retired rule, `params check` = v3 consistency, vacuous lock-readiness); `docs/audits/quantum-vault-ecosystem-wave4/verification/03-verification.md:25` (confirmed, Medium), `:153-160` (CI's only ycash6 mention is a comment; the drift pin is a deliberate tripwire but keeps CI green; the golden chain pins the vulnerable claim → cancel → release as valid); `00-consolidated.md:43`, `:55`, remediation priority 3 (`:63-64`).
**Verified at** yb-calibration `97d5279` / ycash6 `0742e43` / ycash-dd `da5e0fe` (2026-10-13).
**Status:** pending

## 1. Finding

yb-calibration's value is that the constants it produces and checks are the node's constants. In CI nothing compares them. Every test that reads a real ycash6 tree skips when no clone is present, and CI never provides one: the vendored-model byte comparison, the clone extraction tests, the feed ports, the emitter's patch-application tests. What does run is self-referential or tautological: `vendor.check_vendored` checks the vendored files against hashes written by the same `revendor` call (it cannot detect a re-vendor from the wrong ref); `parity` "kernels == reference" for the delegated kernels (`required_zat`, `claimant_max_zat`, `protocol_fee_*`, `early_redeem_fee_zat`, `residual_zat`, `sigma_mult_bps`, `min_ratio_bps`, `cap_cents`, `global_ratio_bps`, `attest_fee_zat`) compares `kernels.f` with `_ref.f` that `kernels.f` itself returns after guards; `test_release_constants_are_the_recommendation_as_built` compares `RELEASE_CONSTANTS` with the study's own `recommend()` and literals, never with `params.cpp`/`policy.h`; `test_reference_mainnet_column_drift_is_the_known_v3_registry_set` asserts the 15-value v3 drift as the expected result; `params check` proves the registry equals its own `7702d22` snapshot.

Consequence: a stale constant or a wrong vendor ref passes CI. That is how W4-K-2's retired supply base survived a merge whose commit message says the kernels follow `1310a41a1`, and how the registry can drift from the release line (W4-K-1) with CI green. The auditor checked by hand that `RELEASE_CONSTANTS` and the vendored files currently match both node HEADs; nothing keeps them matching. (Sound and independent, for the record: the 121 C++ worked examples transcribed from `yellowback_math_tests.cpp`, the 67 spec-rational math cases, and the golden replay for the transcribed, non-delegated rules — though the golden replay also pins the W3-Y-1 claim → cancel → residual release sequence as valid, which this report notes for the W4-K-3 model work.)

## 2. Root cause

At yb-calibration `97d5279`:

- `.github/workflows/ci.yml:1-9` (header: "The devnet-marked tests need a built ycashd (YBCAL_YCASH6); they stay a developer's run" — the only ycash6 mention), `:43-52` (lint: `params doc --check`, `params check` on the snapshot, `ybcal verify` without `--ycash6`), `:66-69` (pytest without a clone).
- Clone-gated skips: `tests/model/test_vendor.py:80`, `:84`, `:105`, `:110`; `tests/sim/test_feeds.py:66`, `:72`; `tests/studies/test_g8_ports.py:27`, `:37`; `tests/report/test_emit.py:59`, `:109`; `tests/test_cli.py:50`; `tests/studies/test_release.py:71`; `tests/devnet/test_diff_cli.py:211`; `tests/conftest.py:31`, `:35`.
- `src/ybcal/model/vendor.py:392` `check_vendored` (manifest hashes written by `revendor`, `:374`), `:364` `check_vendored_v3`.
- `src/ybcal/model/kernels.py` delegations, e.g. `:206` `return _ref.sigma_mult_bps(…)`, `:262` `_ref.cap_cents`, `:428` `_ref.protocol_fee_units`, `:446` `_ref.protocol_fee_zat`, `:456` `_ref.early_redeem_fee_zat`; `src/ybcal/model/parity.py:45` `quick_parity` compares them with the same reference.
- `src/ybcal/model/cli.py:90` "vendored files intact" row (self-referential), `:107` "equal to ycash6 …" rows only when a clone is given, `:129-134` drift printed as an informational note.
- `tests/studies/test_fees_option_d.py:244-259` — `RELEASE_CONSTANTS` vs `recommend()` and literals; `:116-123` — asserts the retired MINT-6 base.
- `tests/model/test_worked_examples.py:52-72` — `KNOWN_V3_REGISTRY_DRIFT` pinned.
- `src/ybcal/studies/fees_option_d.py:266` `RELEASE_CONSTANTS = ReleaseConstants()` — records no node commit it was checked against.

## 3. Fix options considered

| | A — **CI job that fetches both node lines at recorded commits and runs the clone-backed checks as required** | B — vendor `params.cpp`/`policy.h` into the repo and test against the copy | C — keep developer-run clone tests |
|---|---|---|---|
| Effect | Real cross-check on every push; a pin bump is a one-line change that CI then proves. | Still self-referential unless the copy itself is checked against the node (needs A anyway). | Today's state. |
| Verdict | **Recommended** (auditor fix). | Rejected as the only check; acceptable as an offline fallback. | Rejected. |

Note the owner's CI rule (2026-10-05, `ci.yml:5-8`): no calibration runs in CI. A node fetch plus `ybcal verify --ycash6` and a constants parse are **checks, not calibration runs**, so they fit the rule; no market data is fetched.

## 4. Recommended fix

1. **Record the node commits.** `vendor.py` already has `VENDORED_COMMIT`; add `RELEASE_NODE_COMMITS = {"ycash6": "<commit>", "ycash-dd": "<commit>"}` to `ReleaseConstants` (or a small `src/ybcal/node_pins.py`) — the commits whose `params.cpp`/`policy.h` the release constants are claimed to equal (today ycash6 `0742e43`-equivalent `cdec862`, ycash-dd `da5e0fe`).
2. **New CI job `node`** (`ci.yml`, push and PR, SHA-pinned actions, `persist-credentials: false`): fetch `boyfromcave/ycash6` and `boyfromcave/ycash-dd` (the workspace's repos per `repos.yaml`) with `actions/checkout` at `VENDORED_COMMIT` and at `RELEASE_NODE_COMMITS` (`fetch-depth: 0` or a fetch of the exact commits — also fixes W4-K-9's shallow-clone test), set `YBCAL_YCASH6`/`YBCAL_YCASHDD`, then:
   - `ybcal verify --ycash6 $YBCAL_YCASH6` with the "equal to ycash6 <pin>" rows **required** (`model/cli.py:107`): a mismatch fails;
   - `pytest -m "not devnet" --require-clone` — a new `conftest.py` option that turns every clone-gated `pytest.skip` (list in §2) into a failure, so a silent skip cannot pass the job (same idea as the node's SKIP guard, `done/MEDIUM-04-F-1-…`);
   - the new constants test (step 3) against both node lines.
3. **`tests/node/test_release_constants_vs_node.py`:** parse `src/yellowback/params.cpp` `SetCommon` and `src/policy/*.h`/`main.h` network-fee constants at `RELEASE_NODE_COMMITS` on **both** lines with the existing fail-closed extractor (`params/extract.py`, extended as W4-K-1 part 2 requires), and assert equality with `RELEASE_CONSTANTS` field by field (fee bands 100/50/10 bps at $1k/$10k, $1 floor, early 500/250/100, `attestFeeBps` 5,000, `maxMint`, `supplyCapBps`, `maxVaultShareBps`/floor, `residualMinCents`/`residualMinZat`, bond floor/cap/share, `bondMinLock`, `bondMaturity`, network fee µUSD/KB, $2 cap, 10-YEC ceiling) and the D-Q-25 base (`issuedBeforeStart` set by the index — assert the `CirculatingSupplyAt` formula, not a value). Assert both lines agree.
4. **Independent parity for delegated kernels:** for each delegated kernel, add C++-transcribed cases to `examples.py` (from `yellowback_math_tests.cpp` at the pin, as for the 121 existing ones) or spec-rational cases, so a wrong vendored reference is caught by something other than itself; mark the delegated rows in `ybcal verify` output as "guard-only".
5. **Vendor check against upstream:** the `ybcal verify --ycash6 … --ref $VENDORED_COMMIT` call of step 2 already re-renders the vendored files from the clone and diffs them (`model/cli.py:44-50`, rows at `:107`); the clone tests in `tests/model/test_vendor.py` do the same and are now required under `--require-clone`. Also run it with `--ref` = the ycash-dd commit against the ycash-dd clone.
6. **Drift tripwire:** keep `KNOWN_V3_REGISTRY_DRIFT` until W4-K-1's re-pin, but after it assert `reference_param_drift() == {}`; per W4-K-1 the non-empty drift is already a refusal condition for `recommend`.
7. `Makefile`: `make ci-node` runs the same locally.

## 5. Tests

- The new job fails on a deliberate one-value mismatch (temporarily set a `RELEASE_CONSTANTS` field off by one in a throwaway commit, or a unit test that feeds the comparator a mutated `params.cpp` text) — would have caught W4-K-2's base and any constant drift.
- `--require-clone` fails when `YBCAL_YCASH6` is unset (test of the option itself).
- The job passes at the current pins on both lines (the auditor's manual comparison: all vendored files identical at ycash6 `1310a41a1`/`cdec862`; ycash-dd differs only in a comment in `reference_util.py`).

## 6. Acceptance criteria

- A CI job on every push/PR reads both node lines at recorded commits; vendor equality, clone-backed tests and the constants comparison are required, never skipped.
- `RELEASE_CONSTANTS` records the node commits it equals; a mismatch on either line fails CI.
- Delegated kernels have at least one independent case each; `ybcal verify` labels guard-only rows.

## 7. Risks and side effects

- CI needs read access to the two node repositories (public or a read-only token; no write credentials, `persist-credentials: false`). Runtime: two checkouts plus parsing — minutes, no build of `ycashd`.
- ycash-dd's `reference_util.py` differs from ycash6's by a comment and a trailing space: the vendor byte check runs against ycash6 (the vendored line) and a normalised comparison against ycash-dd, or the job reports that one known difference explicitly.
- No node, client or consensus impact.

## 8. Effort estimate and dependencies

- 1.5–2 days (job, conftest option, constants test, delegated-kernel cases).
- Independent of the node reports. Works best after `MEDIUM-W4-K-1-yb-calibration-v3-registry-repin-lock-guard.md` part 2 (the extractor can then read the release line); before it, the constants test parses only the `RELEASE_CONSTANTS` fields, which the current extractor subset must be extended to read (struct-array fee bands, `N * COIN`). Pairs with `LOW-W4-K-4-K-6-K-7-K-8-yb-calibration-seat-revenue-fee-kernel-deps-devnet-fetch.md` (lock file for the job's environment) and `INFO-W4-K-9-yb-calibration-float-fee-study-ds-store-shallow-clone.md` (full-history checkout).
