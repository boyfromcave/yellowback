# LOW — 04/F-4 — ycash6's block assembler has a thinner per-candidate safety net than ycash-dd's (no PQ-script or sequence-lock recheck)

**Repos / branches to change:** `ycash6` (`src/vault/node.{h,cpp}` `TemplateRun`, `src/miner.cpp`), branch `fix/04-F-4-miner-recheck-parity` off `upgrade/vault`; `yellowback` workspace `docs/mapping.md` §22 row "Template validation of the miner".
**Audit source:** `04-cross-line-parity-activation.md` §F-4 (`:165-184`); `verification/04-verification.md` row F-4 (`:69`), detail (`:98-106`) and the `TemplateRun` probe (`:45`).
**Status:** pending.

## 1. Finding

ycash-dd's `CreateNewBlock` re-validates every candidate transaction at the template height: `ContextualCheckSequenceLocks`, PQ policy sigops, `ContextualCheckInputs` with `MANDATORY | GetVaultScriptFlags(nHeight)` (every script, including `OP_CHECKPQSIG` and the set opcodes against the snapshot), the vault trial, then `FilterTemplate`. ycash6's `BlockAssembler` takes sigops from the mempool entry, checks finality/expiry, runs `TemplateRun::Try` (the primitive's `ApplyTx` plus `RecheckTemplateScripts`, i.e. **template-input** scripts only) and `FilterTemplate`; it never re-runs sequence locks or ordinary/PQ input scripts, and `TestNewBlockAtTipValidity` under `CheckAs::BlockTemplate` runs no scripts. ycash6 relies on the mempool being valid at tip+1 (`RecheckMempool` on every tip change, `removeForReorg`).

Not a consensus split: `ConnectBlock` is identical on both lines and enforces everything; a template that slipped an invalid transaction fails `TestNewBlockAtTipValidity` for non-script rules (and throws, `miner.cpp:488-489`) or, for a script-only failure, yields a block the network rejects — a self-DoS of the mining node. The asymmetry matters because ycash6 is the release line and the one pools mine with. Verified Low.

## 2. Root cause

- ycash-dd `055d9c2` `src/miner.cpp:557-576` (`ContextualCheckSequenceLocks` `:559`, `GetPQSigOpCount` `:566`, `ContextualCheckInputs` with vault flags `:576`), `:580-588` vault trial, `:592` `FilterTemplate`.
- ycash6 `e866c45` `src/miner.cpp:530` (sigops from the entry; PQ-inclusive via `main.cpp:2030`), `:548-553` `IsFinalTx`/`IsExpiredTx`, `:556-563` `vaultRun->Try`, `:567` `FilterTemplate`, `:488` `TestNewBlockAtTipValidity`; `grep -n 'ContextualCheckInputs\|ContextualCheckSequenceLocks' src/miner.cpp` → none.
- ycash6 `src/vault/node.cpp:294-300` `TemplateRun::Try`: `trial->ApplyTx` then `RecheckTemplateScripts`; `RecheckPQScripts` (`:167-192`) lives in an anonymous namespace and is called only from `RecheckMempool` (`:241`).
- `docs/mapping.md` §22 row "Template validation of the miner" records the 6.20.0 design ("TestBlockValidity runs no scripts, finding 28").

## 3. Fix options considered

1. Port dd's full per-candidate `ContextualCheckInputs` into `BlockAssembler`: re-verifies every ECDSA input of every candidate per template (sigcache makes it cheap, but 6.20.0 deliberately dropped it, and `CheckAs::BlockTemplate` exists for that reason). More than parity needs. Rejected.
2. **Extend `TemplateRun::Try` with the two vault-specific rechecks dd performs:** `RecheckPQScripts` (PQ inputs at the template height's flags and branch — catches a Falcon spend a reorg below `pqFalconHeight` left behind, or a PQ spend signed for the wrong branch at the boundary) and `ContextualCheckSequenceLocks` at `height` (BIP68 against the template's view — catches an intent RELEASE that became too young after a reorg). Both are the overlay's own code paths; cost is one cached verify per PQ input and one height comparison per input. **Recommended.**
3. Do nothing; rely on `RecheckMempool`. The verifier's trace shows `RecheckMempool` runs on both tip moves before any template is built, so the window is a mempool transaction admitted *between* the tip change and the template build with stale assumptions — narrow, but the fix is small.

## 4. Recommended fix

ycash6 only (ycash-dd already has the checks):

1. `src/vault/node.h`: declare `std::optional<std::string> RecheckPQScripts(const CTransaction&, const CCoinsViewCache&, int height, const std::shared_ptr<const SetSnapshot>&, const Consensus::Params&)` beside `RecheckTemplateScripts` (`:84`); move it out of the anonymous namespace in `node.cpp:167`.
2. `src/vault/node.cpp` `TemplateRun::Try` (`:294-300`):
   ```cpp
   std::optional<std::string> bad = trial->ApplyTx(tx, height, coins);
   if (!bad) bad = RecheckTemplateScripts(tx, view, height, snapshot, params);
   if (!bad) bad = RecheckPQScripts(tx, view, height, snapshot, params);     // parity with ycash-dd's per-candidate ContextualCheckInputs (audit 04/F-4)
   if (!bad) { CValidationState s; if (!ContextualCheckSequenceLocks(tx, view, height, s, false)) bad = std::string("sequence-locks: " + s.GetRejectReason()); }
   ```
   (`ContextualCheckSequenceLocks` is in `main.h` on ycash6, `main.cpp:891-933`; `TemplateRun` already holds a `CCoinsViewCache view` over the mempool-backed view, which is what dd's miner passes too.) Only run the sequence-lock check when `UPGRADE_VAULT` is active at `height` — `TemplateRun` exists only then (`miner.cpp` constructs it under the activation check; confirm).
3. `src/miner.cpp`: no change beyond a comment at `:556` ("Try also rechecks PQ scripts and BIP68 at nHeight; see node.cpp").
4. `docs/mapping.md` §22 row "Template validation of the miner": append "parity: `TemplateRun::Try` rechecks PQ scripts and sequence locks per candidate (04/F-4)".

Consensus footprint: none (`src/miner.cpp` and `src/vault/node.cpp` are not consensus; the template becomes stricter, never looser than `ConnectBlock`).

## 5. Tests

- ycash6 `qa/rpc-tests/vault_upgrade.py` (the rewrite already covers reorg eviction) and `vault_pq_reorg.py` (once 04/F-1's SKIP guard lands): after the reorg below `pqFalconHeight`, additionally assert `getblocktemplate` contains no transaction with a Falcon input — `vault_harness.py`'s `assert_template` after every tip change already runs the template; add the explicit negative.
- Unit: `TemplateRun` needs `chainActive`, `g_vaultdb` and a mempool; the existing ycash6 `vault_state_tests` `EjectingTestModule` fixture does not host it. Cover functionally; if a unit seam is wanted, a `TemplateRun` constructed over a `CCoinsViewCache` in a `TestChain100Setup` with a PQ spend signed for the NU5 branch → `Try` returns `input 0: …` is a ~40-line addition to `pq_script_tests.cpp` on ycash6.
- `yellowback_void_mint` (TPL-1, once 04/F-3 is ported) stays green — order of `Try`/`FilterTemplate` unchanged.

## 6. Acceptance criteria

- `TemplateRun::Try` on ycash6 refuses a candidate whose PQ signature does not verify at the template height's flags/branch, and one whose BIP68 lock is unsatisfied at that height; the mempool side (`RecheckMempool`) is unchanged.
- Functional negative in place; `vault_upgrade`, `vault_pq_reorg`, `yellowback_void_mint`, `yellowback_stratum` (pool template) pass on ycash6.
- Mapping row updated.

## 7. Risks and side effects

- Template build cost: one PQ verify per PQ input per candidate per template; successes are cached (`sigcache`), so repeated templates are free. Pools (yolo) call `getblocktemplate` every few seconds — measure once with 1,000 PQ spends in the mempool (`contrib/yellowback/pq-dos/pq_dos.py` has the generator) and record the number in `doc/yellowback-pq-dos.md`.
- A stricter template can only drop transactions a block would have rejected; no client impact.

## 8. Effort estimate and dependencies

~2 hours plus the functional negative. Dependency: the Falcon-reorg assertion needs 04/F-1 (report R8) so `vault_pq_reorg.py` actually runs in CI; the sequence-lock part has none.
