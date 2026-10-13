# LOW — W3-Y-4, W3-Y-8 — YED test fidelity: untested verdicts (`transfer-no-yed-input`, `mint-not-active`, three `vault-claim-intents` shapes), a golden that pins the R-1c sequence as valid with no collateral assertion, and model-independent property checks; add a verdict-coverage gate

**Repos / branches to change.** `ycash-dd` and `ycash6`, new branch `fix/W3-Y-4-verdict-coverage` off `upgrade/vault` in each: `src/test/yellowback_state_tests.cpp`, `qa/rpc-tests/test_framework/{test_yellowback_model.py,yellowback_model.py (no rule change)}`, `src/test/data/yellowback_golden.json` (only if the new rejected blocks are added in the same window as HIGH-W3-03-NEW-1), a new `qa/yellowback-verdict-coverage.py`, `qa/yellowback-audit.sh` (one leg), `doc/yellowback-testing.md`. No consensus code.
**Audit source.** `docs/audits/quantum-vault-ecosystem-wave3/03-yellowback-module.md:156-187` (W3-Y-4), `:222-235` (W3-Y-8), test-fidelity summary `:262-276`; `docs/audits/quantum-vault-ecosystem-wave3/verification/03-verification.md:139-152` (W3-Y-4 partially confirmed, lowered to Low: `vault-claim-intents` and `attestor-seq-exhausted` *are* unit-tested under their C++ symbols; `transfer-no-yed-input` and `mint-not-active` are not; the golden pins the R-1c outcome), `:177-181` (W3-Y-8 confirmed, Note); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:43`, remediation priority 1 ("assertions on re-created collateral"). Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:89` (W3-Y-4 / W3-Y-8 STILL OPEN, Δ-free: golden, model); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`, none of which this report cites; golden hash and `test_yellowback_model.py` unchanged.
**Status:** pending

## 1. Finding

The golden vector — the one artefact both implementations replay — exercises the fund-losing W3-Y-1 sequence (path-(b) claim at 300 with a residual to the owner, attestor cancel of the claimant intent at 301, residual release at claim + 11; `test_yellowback_model.py:1762-1781`) and accepts it as **valid**, with no assertion anywhere that the re-created vault's collateral is what the claimed vault held less the residual, or that supply is restored. Both implementations agree, so the shared misreading (W3-Y-8: the model is a statement-for-statement port of the C++ — `yellowback_model.py:550-601` and `_apply_intent_spend` `:2672-2732` mirror `math.h` and `ApplyIntentSpend`) is invisible: no test would fail if the extraction got worse, and the CAN-3 fix will flip a golden outcome rather than an assertion. `yellowback_interm.py::cancel_case` (`:367-413`) runs only a path-(a), residual-0 claim.

Two verdicts have no test at all (verifier: confirmed absent from `src/test/*.cpp` and `qa/rpc-tests/*.py`): `transfer-no-yed-input` (XFER-3, `state.cpp:537` — the burn-by-rule path: the transaction stays **valid** and its TxLog row records the verdict, `:538-540`, so a test must assert the logged verdict and the absence of tokens, not a rejection) and `mint-not-active` (MINT-4, `state.cpp:369-378`, three branches: no snapshot, `HALT_NOT_ACTIVE`, an unknown halt bit). `vault-claim-intents` has one unit negative (`yellowback_state_tests.cpp:2136-2138`, no intents) but not its other shapes: three intents (`state.cpp:622`), a re-lock output on a claim (`:618`), two intents with no residual due (`:704-706`). The first wave's claims about `attestor-seq-exhausted` and `vault-claim-intents` being untested are wrong (`:2965-2976`, `:2136-2138`). The "independent recomputation" of the golden hash is a process control with no artefact (W3-Y-8; partly addressed by the done report `LOW-03-T-1`).

## 2. Root cause

At `ycash-dd` `da5e0fe` / `ycash6` `0742e43`:
- `qa/rpc-tests/test_framework/test_yellowback_model.py:1762-1781` (claim5 / cancel5 / release5r valid), `:1855-1875` (the only cancel asserts are rejected *shapes*); `src/test/yellowback_state_tests.cpp:701-760` (`statehash_golden_vector`: hash + rejected-verdict list `:733-740`, no state assertions on the R-1c leg).
- `src/test/yellowback_state_tests.cpp:4641-4891` (`intent_cancel_*`: single-intent claims), `:4791` (`intent_cancel_of_residual_invalid`: only that the residual cannot be cancelled).
- No verdict-coverage check in `qa/yellowback-audit.sh`; verdict strings live in `state.cpp:30-80` (`namespace verdict`).

## 3. Fix options considered

- **A (recommended): targeted tests + model-independent property assertions + a verdict-coverage gate.** Each verdict string or its `verdict::` symbol must appear in at least one C++ unit test or functional test, enforced by a script; property checks computed from raw block data (not from the model's state machine).
- B: an independent second model derived from the plan text. Better independence, but a large effort for a Low; defer (record in `doc/yellowback-testing.md` as a known limit).
- C: assertions only in the golden replay. Rejected alone: the golden changes with every rule change; properties belong in unit tests too.

No consensus change, so no four-part check; this report supports the review gate of HIGH-W3-03-NEW-1 and HIGH-W3-Y-2.

## 4. Recommended fix

1. **R-1c with explicit assertions (lands before or with HIGH-W3-03-NEW-1).** New unit test `claim_cancel_residual_collateral_accounting` in `yellowback_state_tests.cpp`: a path-(b) claim with a residual, cancel of the claimant intent; assert `reopened.collateralZat == claimantIntent.nValue`, `reopened.collateralZat + residualIntent.nValue ≥ claimed.collateralZat`, `supplyCents` equal to its pre-claim value, `reopened.mintedCents == claimed.mintedCents`. Write it first **asserting today's outcome for the residual release (valid)** with a `// W3-Y-1: flips under CAN-3` comment, so the CAN-3 commit changes one expectation to `intent-residual-held` — the flip is the review evidence.
2. **Missing negatives** (unit, exact verdict each): `transfer-no-yed-input` (a TRANSFER payload with no YED input: the transaction is valid; assert `log.verdict == transfer-no-yed-input`, `log.yedOut == 0` and that no output became a token); `mint-not-active` × 3 (no snapshot at the ref height; `HALT_NOT_ACTIVE` virtual snapshot below `START_HEIGHT`; an unknown `haltMask` bit forced into a stored snapshot); `vault-claim-intents` × 3 (three intents; a re-lock of the vault script on a claim; two intents when no residual is due).
3. **Golden.** In the HIGH-W3-03-NEW-1 regeneration window (not separately — one regeneration), add rejected blocks for `vault-claim-intents` (re-lock on a claim) and the new `red5-claimant-short` / `intent-residual-held`, and one **valid** TRANSFER with no YED input whose TxLog verdict `transfer-no-yed-input` is pinned by the hash; extend both rejected manifests (`yellowback_state_tests.cpp:733-740`, `test_yellowback_model.py:1622` `golden_rejected`) in step.
4. **Model-independent properties (W3-Y-8).** In `statehash_golden_vector` (C++) and a new `test_golden_properties` (Python, reading `yellowback_golden.json`'s raw transactions, not `yellowback_model`'s state): for every claim block, `claimant + residual intent values` cover the claimed vault's value and the claimant intent ≥ `collateral − residual` (fails today on the NEW-1 shape, passes on the fixture); for every cancel, `supply after cancel == supply before the claim` (from the per-block `supplyCents` the vector records) and `re-created collateral + held residuals ≥ claimed collateral`; no residual release while its position is open (post-CAN-3).
5. **Verdict-coverage gate.** `qa/yellowback-verdict-coverage.py`: parse `const char* const NAME = "string";` in `src/yellowback/state.cpp`'s `namespace verdict`; require each `NAME` (as `verdict::NAME`) or `"string"` to occur in `src/test/yellowback_*.cpp` or `qa/rpc-tests/*.py`; an allow-list file for deliberately unreachable totality verdicts, each with a reason. Add it as a leg of `qa/yellowback-audit.sh` (failing on `upgrade/vault`), byte-identical on both lines.
6. **Docs.** `doc/yellowback-testing.md`: the golden is model-generated and the model is a structural port (W3-Y-8, stated plainly); the property checks and the coverage gate are the independent layer; option B recorded as future work.

## 5. Tests

The report *is* tests; acceptance is that they exist and run in CI on both lines: `test_bitcoin --run_test=yellowback_state_tests`, `test_yellowback_model.py`, `qa/yellowback-verdict-coverage.py` (new), `qa/yellowback-audit.sh` leg. A deliberate regression check: temporarily revert RED-5a in a scratch tree — the property test and `claim_cancel_residual_collateral_accounting` must fail.

## 6. Acceptance criteria

- Every verdict in `state.cpp` is referenced by a test or listed with a reason in the allow-list; the gate fails CI on a new untested verdict.
- The R-1c unit test exists with collateral and supply assertions; under CAN-3 it asserts `intent-residual-held`.
- Golden rejected list extended in the shared regeneration; property checks run on both lines; `doc/yellowback-testing.md` updated.

## 7. Risks and side effects

- None to consensus. The coverage gate may flag verdicts that are unreachable by construction; keep the allow-list small and reasoned.
- Golden churn: fold the new rejected blocks into the HIGH-W3-03-NEW-1 regeneration so the hash moves once before P8.

## 8. Effort estimate and dependencies

- Unit negatives and R-1c test: 1 day; property checks (C++ + Python): 0.5 day; coverage script + audit leg: 0.5 day; docs: 1 hour; ycash6 port: 1 hour.
- Dependencies: step 1 lands before HIGH-W3-03-NEW-1 (so CAN-3 flips it); step 3 lands inside HIGH-W3-03-NEW-1's golden window; builds on the done `LOW-03-T-1-ycash-yed-golden-model-independence.md` process.
