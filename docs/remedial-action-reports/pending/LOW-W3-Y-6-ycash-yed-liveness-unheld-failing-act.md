# LOW — W3-Y-6 — `LIVENESS_UNHELD` turns a benignly failing attestation-carrying act (a CLAIM_NOTICE that lost a same-block race) into a consensus-invalid transaction: keep the rule, specify it, and test the miner and mempool paths that contain it

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W3-Y-6-liveness-unheld` off `upgrade/vault`: tests (`src/test/yellowback_state_tests.cpp`, `src/test/miner_tests.cpp`, `qa/rpc-tests/yellowback_attest.py`), `doc/yellowback-spec.md`, `doc/yellowback-attestor.md`, workspace `yellowback-upgrade-plan.md` (the liveness rule's text) + `make spec`. No consensus change under the recommended option.
**Audit source.** `docs/audits/quantum-vault-ecosystem-wave3/03-yellowback-module.md:198-209` (W3-Y-6); `docs/audits/quantum-vault-ecosystem-wave3/verification/03-verification.md:162-167` (confirmed Low; the `FilterTemplate` / `RemoveInvalidVaultSpends` mitigations were not re-traced — re-traced below). Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:90` (STILL OPEN, Δ-free); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`, none of which this report cites.
**Status:** pending

## 1. Finding

If a transaction's attestation bundle credits liveness to any live member (`AttestationLiveness` finds structurally valid attestations by seated keys), the module requires it to be a **held** MINT, REDEEM or CLAIM_NOTICE whose bundle passes the whole BUNDLE-1; otherwise the transaction is invalid (`bad-yellowback-liveness-unheld`). The rule exists so the primitive's liveness hook (which credits structurally, without YED state) and the module's mirror never disagree in a valid block. Its side effect: a CLAIM_NOTICE whose NOT-1 fails for a *state* reason — the vault was claimed earlier in the same block, the notice's TTL guard, `pEmerg` not under 105 % — is not "non-Yellowback" (as the plan describes failing v3 acts) but invalid, and a block that includes it is invalid.

Re-trace of the containment (this report): the module's `FilterTemplate` dry-runs every block-template candidate in order on a nested overlay and skips any that is module-invalid after the candidates before it (`src/yellowback/policy.cpp:70-90`, called from `src/miner.cpp:593`); `RemoveInvalidVaultSpends` sweeps the mempool at each new tip (`src/main.cpp:3955`); mempool rejection is DoS 0. So a `ycashd`-built template (including every pool using `getblocktemplate`, yolo's only interface) never includes the losing notice. Residual exposure: an external block builder that does not run the module's filter, and the notice author's confusion (a "failed" notice is an invalid transaction, not a logged no-op). Low.

## 2. Root cause

At `ycash-dd` `da5e0fe` / `ycash6` `0742e43` (byte-identical): `src/yellowback/state.cpp:1291-1322` (the B2 liveness block; the failure at `:1309-1316`), `livenessHeld` set only for held acts at `:1234-1275`; the primitive's hook `src/yellowback/module.cpp:143-166` (`Module::Liveness`) over `AttestationLiveness` (`state.h:350-365`), applied by `src/vault/state.cpp:656-665`.

## 3. Fix options considered

| | A — **keep; specify; test the containment** | B — credit liveness only for held acts on both sides | C — invalidate only when the bundle itself fails |
|---|---|---|---|
| Change | Docs + tests. | The primitive-side hook must learn whether the YED act held, i.e. run the module's per-transaction evaluation (YED state) inside `ApplyEjectionsOf`, or move the credit after `EvaluateBlock`. Cross-hook ordering change in `main.cpp`'s connect path on both lines. | Same plumbing problem as B for the "act held" part. |
| Risk | None new. | A new coupling between the primitive's per-transaction state and the module's block evaluation; consensus review of two hook paths; the very disagreement the rule prevents becomes possible during the change. | As B. |
| Verdict | **Recommended** for this release. | Deferred: revisit only if an external block builder appears; record as a known design limit. | Rejected. |

No consensus change under A, so no four-part check; the rule's spec text is the deliverable.

## 4. Recommended fix

1. **Spec** (`doc/yellowback-spec.md`, upgrade plan's liveness paragraph): "A transaction whose bundle would credit liveness must be a held MINT, REDEEM or CLAIM_NOTICE whose bundle passes BUNDLE-1; otherwise it is **invalid** (`liveness-unheld`), not void. A CLAIM_NOTICE that fails NOT-1 for a state reason — including losing a same-block race to a claim of the same vault — is therefore invalid; block builders must evaluate candidates in order (the node's `FilterTemplate` does)."
2. **Attestor/operator doc** (`doc/yellowback-attestor.md`, notices section): a notice that fails is rejected by the mempool with `liveness-unheld`; re-check with `yed_getnotice` before re-sending; do not build blocks outside `getblocktemplate`.
3. **Wallet message:** `yed_claimnotice` already dry-runs; make its error text name the state reason (claimed earlier / TTL / not underwater) rather than only `liveness-unheld` when the dry run fails for that reason (txbuilder, both lines).

## 5. Tests

- Unit: a block with [claim of V, CLAIM_NOTICE of V] in that order → `bad-yellowback-liveness-unheld`; the reverse order → both valid. A notice past its TTL with a live member's attestation → invalid with the same verdict.
- Miner: two mempool transactions (claim, notice) — `CreateNewBlock` includes the claim and skips the notice (`FilterTemplate` log line), and the block connects.
- Mempool: after a block containing the claim connects, `RemoveInvalidVaultSpends` evicts the notice.
- Functional (`yellowback_attest.py` or `yellowback_interm.py --armed`): `yed_claimnotice` against a vault claimed in the mempool returns the state reason.

## 6. Acceptance criteria

Spec states the invalid-not-void semantics; the four tests exist on both lines and pass; wallet error text names the reason.

## 7. Risks and side effects

None to consensus. If an external block builder appears (P8 review), revisit option B.

## 8. Effort estimate and dependencies

Tests 0.5 day; docs and message 2 hours; ycash6 port 1 hour. Independent of the other W3 reports.
