# LOW — W3-PQ-3 — Per-block PQ verification is bounded only by block size: keep the ruling, add a CI benchmark gate on verify cost and a per-release staged-block figure

**Repos / branches to change:** `ycash-dd` and `ycash6` (both), new branch `fix/W3-PQ-3-pq-verify-cost-gate` off `upgrade/vault` in each. Test code, CI and docs only. **No consensus change:** the owner's ruling (spec F-5 / R-B1: PQ sigops are policy, not consensus) stands.
**Audit source:** `docs/audits/quantum-vault-ecosystem-wave3/02-post-quantum-crypto.md:105-122` (W3-PQ-3), test-fidelity note `:222`; `docs/audits/quantum-vault-ecosystem-wave3/verification/02-verification.md:93-100` (CONFIRMED, Low: "the acceptance rests on an unasserted measurement"); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:49`. Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:75` (STILL OPEN, Δ-free); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`; no workflow on either line runs `pq_timings` with a threshold or `pq_dos.py`.
**Status:** pending

## 1. Finding

Consensus counts no sigops for `OP_CHECKPQSIG`. `ConnectBlock` sums `GetLegacySigOpCount` + `GetP2SHSigOpCount` only, and `GetPQSigOpCount` (20 per PQ check) is applied in `AcceptToMemoryPool` and the block template, never to a received block. R-B1 caps executions at one per `EvalScript`. A non-P2SH input can therefore run at most two (scriptSig + scriptPubKey), and the "staged output" shape gives one SLH-DSA verification per ~41 bytes of a later block. The spec and `doc/yellowback-pq-dos.md` record the measurement for the worst block, and the owner accepted it:
- **staged SLH-DSA:** 48,000 verifies per ≈ 2 MB block, 18.2 s at `-par=1`, 8.0 s connect at default parallelism, 1.22 GB peak RSS, 383 MB undo;
- **legacy multi-CHECKSIG staged block, for comparison:** 65 s / 21 s, i.e. 3.6× more.

The acceptance depends on a one-off measurement of a ratio. If the SLH-DSA verify path became 4× slower relative to ECDSA (a compiler change, a slower SHA-2 path on a new target, a future vendored-code update, an accidental debug build flag in the PQ objects), the staged class would silently exceed the legacy bound that justified the ruling. `pq_timings` prints per-operation timings but asserts only success. The scenario: a miner publishes staged SLH-DSA blocks, every node spends ~8-18 s or more connecting each one, and nobody noticed the margin was gone. Low; the remedy is to measure continuously.

## 2. Root cause

ycash-dd `da5e0fe`, ycash6 `0742e43` (re-verified):

- Consensus sigops: `ycash-dd/src/main.cpp:3260` (`nSigOps += GetLegacySigOpCount(tx)`), `:3324` (`+= GetP2SHSigOpCount`); ycash6 `src/main.cpp:3895`. The PQ count is policy only: `ycash-dd/src/policy/policy.cpp:403-440` (`GetPQSigOpCount`), used at `main.cpp:1832` (ATMP) and `miner.cpp:567`; ycash6 `main.cpp:2088-2094`, carried in the mempool entry `:2124`, `miner.cpp:530`.
- R-B1: `src/script/interpreter.cpp:286` (`nPQSigCount` per `EvalScript`), `:1082-1083` (both lines).
- The timing test: `src/test/pq_crypto_tests.cpp:701-744` (dd) / `:701-743` (ycash6), `pq_timings`. Its comment says "Not a gate". It times keygen/sign/verify per scheme and ECDSA sign/verify, `BOOST_CHECK(ok)` only, and prints with `BOOST_TEST_MESSAGE`.
- The recorded figures: `ycash-dd/doc/yellowback-pq-dos.md:34-40` (table: P2PKH 19.8 µs/verify; SLH-DSA `TX_PQPKH` 247 µs; Falcon 26.5 µs; staged SLH-DSA 379 µs/verify, 18.2 s / 8.0 s connect; staged Falcon 45 µs; legacy staged ECDSA 20.3 µs, 65.2 s / 21.1 s), `:145-178` (the comparison and the undo/memory note). The reproduction harness `ycash-dd/contrib/yellowback/pq-dos/pq_dos.py` (`:253-266` of the doc), with results JSON for both lines (`results-20261012-vault-dd.json`, `results-20261012-vault-ycash6.json`). ycash6 carries no `doc/yellowback-pq-dos.md` and no `contrib/yellowback/pq-dos/`; the ycash6 figures live only in dd's JSON.
- No CI job runs `pq_timings` with a threshold, or `pq_dos.py` at all (`grep -n pq_dos .github/workflows/*.yml`: nothing on either line).

## 3. Fix options considered

1. **Count PQ sigops in consensus** (`ConnectBlock`) to cap staged blocks. It is a consensus change on both lines, contradicts the owner's F-5 ruling, and needs the review gate. Out of scope for this finding, which accepts the ruling. Rejected here; recorded in the spec as the lever if the gate below ever fires.
2. **Absolute thresholds** (fail if SLH-DSA verify > 2 × 250 µs). Hosted runners vary by 2× or more between machine types, so this would be flaky or too loose. Rejected as the primary metric.
3. **Ratio thresholds measured in-process against ECDSA verify on the same runner** (SLH-DSA verify / ECDSA verify, Falcon verify / ECDSA verify), medians over repeated batches, with 2× headroom over the recorded ratios. The ratio is what the ruling rests on (3.6× below the legacy staged block, which is ECDSA-bound). Runner speed cancels out. **Recommended**, plus a per-release full staged-block measurement recorded in the doc.

## 4. Recommended fix

1. **A gated test case** in `src/test/pq_crypto_tests.cpp` (both lines, identical text), next to `pq_timings`:
   ```cpp
   BOOST_AUTO_TEST_CASE(pq_verify_cost_gate)
   {
       // Audit W3-PQ-3: the R-B1 / F-5 ruling accepts staged SLH-DSA blocks because their verify cost is
       // ~3.6x below the legacy multi-CHECKSIG staged block (doc/yellowback-pq-dos.md §1). That rests on the
       // SLH-DSA/ECDSA verify-time ratio (247/19.8 = 12.5 recorded) and Falcon's (26.5/19.8 = 1.3). Fail
       // when either doubles. Runs only with YCASH_PQ_COST_GATE=1 (an optimised, uninstrumented build).
       if (!getenv("YCASH_PQ_COST_GATE")) { BOOST_TEST_MESSAGE("pq_verify_cost_gate: skipped (set YCASH_PQ_COST_GATE=1)"); return; }
       ...
   }
   ```
   Method:
   - One fixed key and signature per scheme. Build them with `SignWithEntropy`, so no RNG is involved.
   - Seven batches each of 200 SLH-DSA verifies, 2,000 Falcon verifies and 2,000 ECDSA verifies (`CPubKey::Verify`), timed with `GetTimeMicros`; take the median µs/op per kind.
   - Assert `slh/ecdsa <= 25.0` and `falcon/ecdsa <= 2.7`, i.e. 2× the recorded ratios. Name the constants `PQ_SLH_ECDSA_RATIO_MAX` and `PQ_FALCON_ECDSA_RATIO_MAX`, each with a comment citing the doc row.
   - Derive the staged-block projection: `48000 * slh_us` relative to `3216000 * ecdsa_us` (the legacy staged block). Assert the PQ projection stays below the legacy one. That assertion is the ruling's actual inequality, re-checked on the runner.
   - Print every figure with `BOOST_TEST_MESSAGE`, so the CI log carries the measurement.

   **The environment variable is the only skip, and it is explicit:** the case prints that it skipped and passes, so ordinary `make check`, sanitizer and coverage runs (where instrumentation distorts timing) are unaffected. The CI step below sets it.
2. **CI step, both lines:** in the `unit` job after the whole `test_bitcoin` run (dd `yellowback-tests.yml:352-355`; ycash6 equivalent), add
   ```yaml
   - name: PQ verify-cost gate (audit W3-PQ-3; release build, not instrumented)
     run: YCASH_PQ_COST_GATE=1 src/test/test_bitcoin --run_test=pq_crypto_tests/pq_verify_cost_gate --log_level=message
   ```
   This must run on the uninstrumented `build` artefact (`node-bin.tar`). Never run it in the sanitizer, coverage or lockorder jobs. If the hosted runner proves noisy, move the step to the nightly job and keep it blocking there. Do not loosen the ratios without a new measurement row in the doc.
3. **Per-release measurement** (process, both lines):
   - Add to the release checklist (`ycash6/doc/yellowback-release.md`, "Release notes" area; dd `doc/yellowback.md`): "run `contrib/yellowback/pq-dos/pq_dos.py --scenarios=staged,stagedf,legacy` against the release build of each line; add the row to `doc/yellowback-pq-dos.md` §1 and commit the results JSON as `results-<date>-<version>-<line>.json`; refuse the release if the staged SLH-DSA connect time at default `-par` exceeds the legacy staged block's".
   - ycash6 has neither the doc nor the harness. Either copy `doc/yellowback-pq-dos.md` and `contrib/yellowback/pq-dos/` to ycash6, adjusting `pq_dos.py`'s framework imports if needed, or state in ycash6's release doc that the measurement is run from ycash-dd's harness against the ycash6 binary (`BITCOIND=<ycash6 ycashd>`), as `results-20261012-vault-ycash6.json` shows it already was. The second is smaller; recommended.
4. **Spec (this report owns the single F-5 edit and the single "gated by" paragraph):** `docs/plans/yellowback-quantum-spec.md` R-B1 / F-5: one edit stating that the acceptance is gated by `pq_verify_cost_gate` (ratios) and re-measured per release, that a gate failure reopens the ruling (option 1), and — on behalf of `LOW-W3-V-4-V-6-01-N-1` — the per-block worst case (≈ 250 SLH-DSA-128s / ≈ 3,000 Falcon-512 verifications per 2 MB block, accepted, guarded by that report's nightly `vault_block_bench`). `doc/yellowback-pq-dos.md`: one "gated by" paragraph naming both gates (this ratio gate and the nightly bench). `LOW-W3-V-4-V-6` adds only its own "per-block (valid block) cost" section and plan §15.2 rule 6. `docs/mapping.md` §22: one row.

## 5. Tests

- The new case itself. Prove that it can fail: on a scratch branch, wrap `pq::Verify` for SLH-DSA in a 5× loop inside the gate's timing lambda only (test-local), or temporarily set `PQ_SLH_ECDSA_RATIO_MAX = 5`. The step must go red with the measured ratio printed. Record it in the PR; revert.
- Run the case 10 times on the CI runner type (a `workflow_dispatch` loop or a matrix of 10) before merging, and record the min/median/max ratios in the PR. The 2× headroom must cover the observed spread with margin. If it does not, the step goes to the nightly (as above), not to looser constants.
- `pq_timings` is unchanged.

## 6. Acceptance criteria

- `pq_verify_cost_gate` exists on both lines (identical text), skips loudly without `YCASH_PQ_COST_GATE`, and asserts the two ratios and the staged-vs-legacy inequality with it.
- The unit (or nightly) job on both lines runs it with the variable set on the release-optimised binary. The 10-run spread and the forced failure are recorded in the PR.
- The release checklist names the per-release staged-block run and where its figures go. `doc/yellowback-pq-dos.md` says the ratios are gated.
- Spec R-B1/F-5 sentence and mapping row added.

## 7. Risks and side effects

- None to consensus or the node binary.
- **Flakiness:** mitigated by ratios, medians and 2× headroom. The remaining risk is a noisy neighbour on a shared runner. The fallback is the nightly tier, never wider constants.
- **The explicit env-gated skip:** this is an intended, logged skip of a *benchmark*, outside the functional `--fail-on-skip` convention (which governs `rpc-tests.py`). Name it in `doc/yellowback-testing.md` so the next audit does not file it as a silent skip.
- If the gate fires on a legitimate toolchain change, the response is a re-measurement and an owner decision (keep the ruling with new numbers, or option 1), recorded in the doc.

## 8. Effort estimate and dependencies

- ~1 day: the test case (0.25), CI on two lines (0.25), the 10-run calibration and forced failure (0.25), docs/checklist (0.25). One reviewer.
- No dependency. LOW-W3-PQ-1 (hedged Falcon signing) does not touch verify cost. LOW-W3-PQ-2 does not change compiled verify code. Either order.
- **Coordinate with LOW-W3-V-4-V-6-01-N-1** (per-block validation cost of the vault primitive). It adds a nightly `src/bench/vault_block_bench.cpp` with an absolute per-block budget that includes "N SLH-DSA-128s and Falcon-512 owner spends", and it edits `doc/yellowback-pq-dos.md` and the quantum spec's F-5 note too. The two are complementary: this report's ratio gate catches a per-verify regression on any runner, while that report's bench measures whole-block cost. Land them in one PR series; this report owns the one "gated by" paragraph naming both and the one F-5 edit (§4 step 4), so that report does not touch either.
