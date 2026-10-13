# LOW — 03/M-1, 03/M-2 (+ 03/T-2 cancel-path tests) — Cancel accounting (`supplyCents` vs Σ debt) and `BundleLog` rows from non-held transactions: clarify the spec, add the tests, optionally harden

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/03-M-1-M-2-cancel-bundlelog` off `upgrade/vault`: `doc/yellowback-spec.md` (via the workspace plans + `make spec`), `doc/yellowback-rpc.md`, `src/test/yellowback_state_tests.cpp`, `qa/rpc-tests/test_framework/test_yellowback_model.py`; optionally `src/yellowback/state.cpp`, `qa/rpc-tests/test_framework/yellowback_model.py`, the golden. `yellowback` workspace: `docs/plans/yellowback-v3-development-plan.md` (R12, line 576), `yellowback-upgrade-plan.md` §15.10 U-24, `yellowback-in-term-claims-plan.md` D-IT-14.
**Audit source.** `03-yellowback-module.md` M-1, M-2, T-2; `verification/03-verification.md` M-1 ("PARTIALLY, Low — decided behaviour; `supplyCents` is the circulating supply, the correct liability"), M-2 ("PARTIALLY, Low — what R12 asks for; `LIVENESS_UNHELD` closes the cheap form"), T-2 (Low); `00-consolidated.md` rows 03/M-1, 03/M-2 (both ↓ to Low).
**Status:** done — completed 2026-10-13T11:21Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13; nightly tier pending the owner's dispatch)

## 1. Finding

**M-1.** A claim debits `totals.supplyCents` by the claimant's burn (`ycash-dd/src/yellowback/state.cpp:1290-1293`); an attestor cancel re-creates the vault ACTIVE with its full `mintedCents` and `burnedCents = 0` without crediting `supplyCents` (`:826-838`). From then on `Σ ACTIVE mintedCents > supplyCents` by the cancelled debt until the vault closes by a second burn; `GlobalRatioBps` (HALT-2, `math.h:165`, used at `state.cpp:1640`) and the MINT-6 headroom read the smaller supply; `yed_getvault`/`yed_getinfo` consumers show a debt the supply no longer carries. The verifier downgraded it: this is the *decided* behaviour (U-24, D-U3, D-IT-14 — "supply falls, the vault's debt does not"), the model mirrors it (`yellowback_model.py:2700-2708`), the golden covers it, and `supplyCents` is the right liability figure for HALT-2 (burned YED cannot be presented). What remains: an odd aggregate (less YED exists than debt), RPC consumers unaware of it, and no unit test of the cancel path's totals (03/T-2). **If `HIGH-03-H-1-ycash-yed-claim-cancel-refund.md` lands, M-1 disappears** (the cancel credits `supplyCents` by the refunded burn).

**M-2.** `EvalContext::Bundle` (`state.cpp:197-219`) records a verified bundle into the `BundleLog[H]` accumulator (`anyBundle`, `aMints`/`aClaims`, `selectedUnion`, `pairUnion`) *before* the calling rule decides; `ApplyNotice` (`:868-895`) calls it at `:878` and may still return `false` ("not underwater", TTL); the row is written at `:1748`. The row feeds PIN-1/PIN-2 and the S15 dormancy pass. The first wave saw a cheap seat-demotion lever (20 non-held notices over 14 days). The verifier found (a) this is what the spec's R12 asks for (`yellowback-v3-development-plan.md:576`: bundles "for which BUNDLE-1 held — whatever the transaction's final verdict"; `docs/spec/yellowback-spec.md:862`), and (b) `LIVENESS_UNHELD` (`state.cpp:1238-1268`, commit `86570af`) makes a failing MINT/REDEEM/NOTICE whose bundle carries any *fresh* attestation block-invalid, so only bundles of already-credited attestations (`citedHeight ≤ lastAct`, within `ATTEST_MAX_AGE`) still reach the accumulator; dormancy then needs the victim selected and absent from every row for 16,128 blocks with no organic held bundle including it, and a `SET_HEARTBEAT` reinstates it. Narrow, recoverable. The Python model mirrors the behaviour (`yellowback_model.py:2230-2241`), so it is not a shared misreading but a spec choice.

## 2. Root cause

- M-1: `src/yellowback/state.cpp:826-838` (no `supplyCents` credit; by design, U-24); spec text `yellowback-upgrade-plan.md:1189` and `docs/spec/yellowback-spec.md` U-23/U-24; no invariant states `supplyCents = Σ mintedCents`; `doc/yellowback-rpc.md` does not say that a re-created vault's `mintedCents` is not in `supplyCents`.
- M-2: `src/yellowback/state.cpp:197-219` + `:878` + `:1748`, implementing R12 verbatim; the spec sentence predates `LIVENESS_UNHELD` and does not mention it.
- T-2: `grep INTENT_CANCEL src/test/` is empty; the positive cancel is proved only by the golden replay (`test_yellowback_model.py:1528-1532`, `yellowback_state_tests.cpp:701-760`) and `yellowback_interm.py::cancel_case` (`--armed` only).

## 3. Fix options considered

- **M-1:** (a) the H-1 refund — resolves it entirely (recommended; see the HIGH report); (b) if H-1 is deferred, a doc/spec clarification only; (c) a per-vault `prepaidCents` so the re-created vault's remaining debt is `mintedCents − burned` — rejected: it transfers the claimant's burn to the owner (the owner's debt shrinks for free), the wrong party.
- **M-2:** (a) spec clarification only: record that R12's "whatever the verdict" is intentional, that `LIVENESS_UNHELD` bounds it to already-credited attestations, and the residual dormancy/pin lever with its cost and recovery (recommended minimum); (b) optional hardening: commit `BundleFacts` into the accumulator only when the enclosing rule **holds** (`ctx.CommitBundle(f)` called by `ApplyNotice`/`RedVerdict`/the MINT path after their verdict), mirrored in the model's `_bundle` (`yellowback_model.py:2230-2241`), with an R12 edit and a golden regeneration. Cleaner than the sentence it replaces; costs one golden regeneration and a plan edit — take it only if a golden regeneration is happening anyway (H-1).

No consensus rule changes under (a); (b) is a module-rule change (review gate, four-part check: DigiByte has no attestation bundles — **M** absent — so **W** is "record only on hold", one rung: module rule, no state change beyond what is already written).

## 4. Recommended fix

1. **Spec/plan (workspace, then `make spec`; copies land in `ycash-dd/doc/yellowback-spec.md` and `ycash6`):**
   - U-24 (`yellowback-upgrade-plan.md:1189`) and D-IT-14 (`yellowback-in-term-claims-plan.md:89`): add one sentence — "`supplyCents` is the circulating supply (the system's liability); after a cancel the re-created vault's `mintedCents` exceeds the supply it corresponds to by the cancelled burn; `Σ ACTIVE mintedCents = supplyCents` is **not** an invariant" — or, once H-1 lands, replace with CAN-1's text (the HIGH report's step 8) and delete this sentence.
   - R12 (`yellowback-v3-development-plan.md:576`, `docs/spec/yellowback-spec.md:862`): append "— including a failing CLAIM_NOTICE; since the focused review, `LIVENESS_UNHELD` makes any such transaction block-invalid when its bundle carries an attestation newer than its signer's `lastAct`, so only already-credited attestations reach the row through a non-held transaction (dormancy/pin residual: ≥ 20 rows over `DORMANCY_WINDOW` with the victim selected and absent; reinstated by `SET_HEARTBEAT`)". If option (b) is taken, replace the sentence with "for which BUNDLE-1 held **and** the carrying MINT/REDEEM/CLAIM_NOTICE held".
2. **`doc/yellowback-rpc.md` (both lines):** on `yed_getvault.mintedCents`/`burnedCents` and `yed_getinfo.supplyCents`: a re-created (cancelled) vault's debt is not in `supplyCents` (until H-1). On `yed_getinfo`'s ratio: it reads circulating supply.
3. **Tests (03/T-2, both lines, `src/test/yellowback_state_tests.cpp`):** the cancel path's verdicts and totals — `INTENT_CANCEL_RESIDUAL`, `INTENT_CANCEL_NO_VAULT` (no re-lock; two re-locks; re-lock not at vout 0), `INTENT_SPEND_MALFORMED` (payload on a cancel; selector 3), the notice erasure (`:836`), `totals.collateralZat`/`activeVaults` after the cancel (`:837-838`), and the explicit totals assertion `supplyCents_after == supplyCents_before` (today) — which becomes `+ burned` with H-1 — so the invariant the spec states is pinned by a test either way. For M-2: a unit that a failing CLAIM_NOTICE with a bundle of already-credited attestations leaves `BundleLog[H]` with that row (today's R12 behaviour, so a future change is deliberate), and that one with a fresh attestation is `LIVENESS_UNHELD`.
4. **Optional M-2 hardening (only with H-1's golden regeneration):** `EvalContext::Bundle` fills `BundleFacts` and a `pending` struct; a new `EvalContext::CommitBundle(const BundleFacts&)` appends to the accumulator; `ApplyNotice` commits after its last check (`:892`), `ApplyVaultSpend` after `RedVerdict` returned OK (`:716`), the MINT path likewise; the model's `_bundle` splits the same way; regenerate the golden by the T-1 process; R12 edited as in step 1. Unit: a failing notice leaves `BundleLog[H]` untouched.

## 5. Tests

As §4 step 3 (unit, both lines) and, for the optional hardening, step 4 plus the golden regeneration (`statehash_golden_vector`, `test_yellowback_model.py --write-golden` diff). `yellowback_interm.py::cancel_case` asserts `yed_getinfo.supplyCents` before/after the cancel per the documented rule.

## 6. Acceptance criteria

- The spec and `doc/yellowback-rpc.md` state the supply/debt relation after a cancel and the R12 residual (or the hardened rule) on both lines; `make spec-check` clean.
- `grep INTENT_CANCEL src/test/` is non-empty on both lines; the totals assertion after a cancel exists and matches the documented rule.
- If the hardening is taken: a failing notice leaves `BundleLog[H]` untouched in C++ and in the model; golden regenerated in its own commit with a reviewer recomputation.

## 7. Risks and side effects

- Doc/test-only path: none. Hardening path: a module-rule change (both lines together; golden regeneration; no vector change; no public activation height, so no split) — bundle it with H-1 to pay the regeneration once.

## 8. Effort estimate and dependencies

- Spec + RPC doc + unit tests: 1 day. Optional hardening: +0.5 day plus the shared golden regeneration.
- Dependencies: write the M-1 text in the form that matches the decision on `HIGH-03-H-1`; if H-1 lands, M-1's doc sentence is replaced by CAN-1's and only the T-2 tests remain from this report.

## Completion record

- **Completed:** 2026-10-13T11:21Z
- **Merged:** with fix/yed-cancel. M-1 text follows CAN-1 (a cancel credits supply back); the optional M-2 hardening was taken (R12: BundleLog rows only from bundles whose transaction holds); T-2 cancel-path C++ tests; TxLog accounting for claim_cancel documented.
- **Verification:** Integration run 2026-10-13 (both node lines built; full test_bitcoin dd 872/872, ycash6 923/923; qa/yellowback-audit.sh dd --mode upgrade rc 0 (18 PASS), ycash6 --report-only rc 0; functional suites pass; vault_vectors / golden / pq vectors byte-identical across lines). Logs: wt/scratch/integ/.
