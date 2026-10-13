# LOW — 04/F-3 — Port the TPL-1 functional case (`tpl_primitive_skip_leaves_no_yed_effect`) to ycash6, whose spec still cites it

**Repos / branches to change:** `ycash6` (`qa/rpc-tests/yellowback_void_mint.py`, `doc/yellowback-spec.md`), branch `fix/04-F-3-tpl1-test-port` off `upgrade/vault`; `yellowback` workspace `docs/mapping.md:1111` row update.
**Audit source:** `04-cross-line-parity-activation.md` §F-3 (`:149-163`); `verification/04-verification.md` row F-3 (`:68`), detail (`:93-96`).
**Status:** done — completed 2026-10-13T11:21Z (merged locally on `upgrade/vault`; not yet pushed)

## 1. Finding

TPL-1 ("a mint the vault primitive skips adds no supply to the template") was fixed on ycash-dd by running the primitive's per-candidate trial *before* the YED module's `FilterTemplate` in the block assembler, and pinned by the functional method `tpl_primitive_skip_leaves_no_yed_effect` in `yellowback_void_mint.py` (97 lines, documented to fail on the old order). The miner fix was ported to ycash6 (`TemplateRun::Try` before `FilterTemplate`), the test was not: ycash6's `yellowback_void_mint.py` has no such method, `grep -rn tpl_primitive_skip ycash6/qa` is empty, while `ycash6/doc/yellowback-spec.md:377` still cites the test as the evidence for the rule. The release line therefore has the behaviour without its regression test, and a spec that points at a test that does not exist. `docs/mapping.md:1111` records the gap as pre-existing. Verified Low.

## 2. Root cause

- ycash-dd `055d9c2` `qa/rpc-tests/yellowback_void_mint.py:166-242` (the method; `checkpoint('primitive skip')` at `:242`), called at `:370`; docstring `:14`.
- ycash6 `e866c45` `qa/rpc-tests/yellowback_void_mint.py`: `diff -u` against dd removes the method and its call (04 report); `doc/yellowback-spec.md:377` "test `tpl_primitive_skip_leaves_no_yed_effect` (fails on the old order)".
- ycash6 `src/miner.cpp:556-567` (`vaultRun->Try` then `FilterTemplate`), `src/vault/node.cpp:294-300` `TemplateRun::Try` — the ported fix the test should pin.
- `docs/mapping.md:1111`: "Pre-existing test gap, not ported with in-term claims; the case's IT-5 edits (class A at 300 % is below the floor) apply when it is".

## 3. Fix options considered

1. Remove the citation from `ycash6/doc/yellowback-spec.md:377`. Honest but loses the regression guard on the release line. Rejected.
2. Port the method by delta with the 6.20.0 harness adaptations and the IT-5 edits the mapping row names. **Recommended.**

## 4. Recommended fix

1. Copy `tpl_primitive_skip_leaves_no_yed_effect` (dd `:166-242`) and its call (`:370`) and checkpoint into ycash6's `yellowback_void_mint.py`, then apply the 6.20.0 deltas the rest of the file already carries (compare the two files' existing methods for the pattern): `ZCASHD`/`cache_behavior` harness names, ZIP-317 wallet fee via `wallet_network_fee()` / `conventional_fee()` from `yellowback_util.py` where the method funds transactions, the 6.20.0 error strings (`non-mandatory-script-verify-flag` family) if any reject reason is asserted, and the IT-5 edit (class A at 300 % collateral is below the floor on the in-term line — use the collateral the file's other methods use after IT-5).
2. Keep the method's core assertion unchanged: a mint the primitive skips (e.g. one whose vault output fails V-1 at template time) must not appear in `getblocktemplate` **and** must leave `yed_getinfo`'s template supply unchanged; mine the template and assert the supply after the block equals the supply before.
3. Prove it pins the order: locally swap the two calls in `ycash6/src/miner.cpp:558-567` (`FilterTemplate` before `Try`), rebuild, run the method — it must fail; restore. Record in the PR.
4. `docs/mapping.md:1111`: change the row's status to "ported (commit …)".
5. `ycash6/doc/yellowback-spec.md:377`: unchanged (now true).

## 5. Tests

The method itself; `yellowback_void_mint` is already in ycash6's `YELLOWBACK_SCRIPTS` merge-gate list, so it runs on every push. Confirm `qa/yellowback-audit.sh`'s registration leg still passes (no new script file).

## 6. Acceptance criteria

- `grep -c tpl_primitive_skip ycash6/qa/rpc-tests/yellowback_void_mint.py` ≥ 2 (definition + call); the merge-gate functional shard that runs `yellowback_void_mint` passes on ycash6.
- The swapped-order experiment fails the method (PR evidence).
- Mapping row updated.

## 7. Risks and side effects

None to code. The ycash6 wallet's P-2 fee (ZIP-317 conventional) changes the amounts the method funds — follow the file's existing helpers rather than copying dd's fixed fees.

## 8. Effort estimate and dependencies

~2–4 hours. No dependencies.

## Completion record

- **Completed:** 2026-10-13T11:21Z
- **Merged:** with fix/ycash6-v5: c0125d43d (tpl_primitive_skip_leaves_no_yed_effect ported; byte-identical to dd's). Passes; the swapped-order experiment fails as it should.
- **Verification:** Integration run 2026-10-13 (both node lines built; full test_bitcoin dd 872/872, ycash6 923/923; qa/yellowback-audit.sh dd --mode upgrade rc 0 (18 PASS), ycash6 --report-only rc 0; functional suites pass; vault_vectors / golden / pq vectors byte-identical across lines). Logs: wt/scratch/integ/.
