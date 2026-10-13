# MEDIUM — 04/F-2 (+ 02/I-4) — v5 (ZIP-225) transactions under NU5 + Vault are unspecified: declare v5 invalid under Vault, refuse NU5 ≤ Vault on regtest, and fix the placeholder-prevout rechecks

**Repos / branches to change:** `ycash6` (`src/main.cpp` `ContextualCheckTransaction` — consensus, review gate; `src/init.cpp` `-nuparams`; `src/vault/node.cpp` rechecks; `src/rpc/vault.cpp` `TxData`; `src/test/pq_script_tests.cpp`), branch `fix/04-F-2-v5-under-vault` off `upgrade/vault`; `ycash-dd` (a parity unit test only), same branch name; `yellowback` workspace (`docs/plans/yellowback-quantum-spec.md`, `yellowback-upgrade-plan.md` §15.1/§15.2, `yellowback-quantum-plan.md`, `docs/mapping.md` §22); `librustzcash6` follows in report `LOW-04-F-6-…`.
**Audit source:** `04-cross-line-parity-activation.md` §F-2 (`:101-147`); `verification/04-verification.md` row F-2 (`:67`), detail (`:80-91`, the placeholder-prevout aggravation); `02-post-quantum-crypto.md` §I-4 (`:155-161`); `verification/02-verification.md` row I-4 (`:59`).
**Status:** done — completed 2026-10-13T11:21Z (merged locally on `upgrade/vault`; not yet pushed) Post-verification severity: **Medium as a spec gap, Low as a live risk** (NU5 has no height on any network of either line).

## 1. Finding

On ycash6, with NU5 and Vault both active (reachable only on regtest with two `-nuparams`), `ContextualCheckTransaction` admits `ZIP225_VERSION_GROUP_ID` (v5) transactions, and `SignatureHash` routes a v5 transaction to ZIP-244, where "the consensusBranchId parameter is ignored; we use the value stored in the transaction itself". `SetSigChecker::CheckSetSig` and `CheckPQSig` take whatever `SignatureHash` returns, so under that configuration a set signature or a PQ signature over a v5 transaction binds the ZIP-244 transparent signature digest, not the ZIP-243 sighash the specs define — and ycash6's own unit test asserts `SCRIPT_ERR_OK` for SLH-DSA and Falcon over a v5 transaction as *expected* behaviour. The quantum plan, the upgrade plan and the quantum spec all define the signed message as ZIP-243 and say nothing about v5; ycash-dd has no v5 type at all. The verifier added an aggravation: the mempool rechecks (`RecheckTemplateScripts`, `RecheckPQScripts`) and `rpc/vault.cpp` build `PrecomputedTransactionData` with `CTxOut()` placeholders for any input whose coin the view cannot see — inert for v4 (the ZIP-243 path ignores `allPrevOutputs`) but wrong for v5, where it feeds a wrong `allPrevOutputs` to the ZIP-244 digest, so a tip change would *silently evict* a valid v5 vault/PQ spend rather than fail loudly. The same configuration already breaks ycash6 for an unrelated reason (history-tree leaves: `history.rs` maps Vault to V1 leaves while `ConnectBlock` builds V2 under NU5; `docs/mapping.md:1212`).

Not a chain split today: NU5 is `NO_ACTIVATION_HEIGHT` everywhere on both lines, both lines reject every non-Sapling version group while NU5 is inactive, and the regtest back-fill excludes Vault. It is a consensus surface the normative text does not define, exercised by a test that calls it expected, with an eviction bug behind it.

## 2. Root cause

ycash6 `e866c45`:
- `src/main.cpp:1097-1103` (pre-NU5: `bad-sapling-tx-version-group-id` for any non-Sapling group), `:1205-1231` (NU5 active: admits `SAPLING_VERSION_GROUP_ID` or `ZIP225_VERSION_GROUP_ID`); no clause consults `UPGRADE_VAULT` for the version group.
- `src/script/interpreter.cpp:1436-1497` (`SIGVERSION_ZIP244` branch, branch id from the transaction).
- `src/vault/checker.cpp:34` (`CheckSetSig` takes `SignatureHash`'s result), `CheckPQSig` likewise; `src/vault/act.cpp`, `template.cpp`, `CheckTx` (identical across lines) exclude nothing by version.
- `src/test/pq_script_tests.cpp:935-954`: the v5 case asserting `SCRIPT_ERR_OK`.
- `src/vault/node.cpp:171-178` (`RecheckPQScripts` placeholders), `:197-215` (`RecheckTemplateScripts` placeholders), `src/rpc/vault.cpp` `TxData` (same pattern).
- `src/init.cpp:1446-1475` (`-nuparams` parsing, `maxUpgradeHeight` tracked), `:1495-1505` (back-fill walks down from `MAX_NETWORK_UPGRADES-1`, excludes Vault from filling NU5..NU6.2's heights).
- `src/rust/src/history.rs:50-62` (Vault → V1 leaves); `src/main.cpp:4140-4150` (V2 leaves when NU5 active).
- `src/chainparams.cpp:139-150` (NU5..NU6.2 `NO_ACTIVATION_HEIGHT` on mainnet; `:443-444` testnet).
- Specs: `docs/plans/yellowback-quantum-plan.md:14-15`, `:205` ("`SignatureHash(scriptCode, tx, nIn, hashType, amount, consensusBranchId)` is the message — ZIP-243, unchanged"), `:213`; `yellowback-upgrade-plan.md:438` (`OP_CHECKSETSIG` "over the ZIP-243 sighash"), `:612` ("Sighash: ZIP-243 bound to consensusBranchId"), `:823` (step 4); `yellowback-quantum-spec.md:363` ("sighash: C++ `SignatureHash` (v4)").
- ycash-dd `055d9c2` `src/main.cpp:1034` rejects non-Sapling groups unconditionally once Sapling is active (`bad-sapling-tx-version-group-id`), so dd already enforces "v4 only" — but as an accident of having no v5 type, not as a stated vault rule.

## 3. Fix options considered

- **(a) Declare v5 invalid under Vault** (spec rule + one consensus clause on ycash6 + regtest `InitError`): one line of consensus, no new vectors, matches `suggested_for_branch(Vault) = V4`, `history.rs` and dd's behaviour; closes the placeholder-prevout eviction by making the only affected transaction type invalid. **Recommended** (prime directive: smallest footprint; Ycash has no NU5 plan).
- **(b) Specify the ZIP-244 message** for set and PQ signatures under a v5 transaction and add golden vectors: a second signed-message definition for a configuration no Ycash network will have, plus fixing the history-tree leaf inconsistency and the placeholder rechecks for real. Rejected.
- **(c) Test-comment-only** ("unspecified, not expected"): leaves the surface undefined. Rejected as the sole measure; the comment change is part of (a).

## 4. Recommended fix

**Spec first (workspace, `upgrade/vault`):**
1. `docs/plans/yellowback-quantum-spec.md`: add rule **R-A3 (transaction version):** "The vault templates, `OP_CHECKSETSIG`, `OP_CHECKSETDORMANT`, `OP_CHECKPQSIG` and TOK-PQ are defined for v4 (Sapling version group, ZIP-243 sighash) transactions only. Under `UPGRADE_VAULT` a transaction whose `nVersionGroupId ≠ SAPLING_VERSION_GROUP_ID` is invalid (`bad-vault-tx-version-group-id`). No ZIP-244 message is defined for the vault opcodes. A network upgrade that brings v5 to Ycash must define it then." Update the `:363` table row ("sighash: ZIP-243, v4 only, R-A3").
2. `docs/plans/yellowback-upgrade-plan.md` §15.1 (constants/activation) and §15.2 step 4 (`:823`): the same sentence, plus in §15.0 a U-decision line (owner) recording option (a) over (b) and the reason. `yellowback-quantum-plan.md:205`: cross-reference R-A3. `make spec`, `make spec-check`.
3. `docs/mapping.md` §22 row "History tree leaves" (`:1212`) gains "and v5 under Vault is invalid (R-A3); NU5 ≤ Vault on regtest is an `InitError`" with the citations.

**ycash6 (consensus, review gate; rule-4 four-part check and tier answer in the PR body):**
4. `src/main.cpp` `ContextualCheckTransaction`, inside the `nu5Active` block after the version-group admission (`:1205-1211`): 
   ```cpp
   // UPGRADE_VAULT (quantum spec R-A3): the vault opcodes and templates are defined over the ZIP-243
   // sighash of v4 transactions only; under Vault a v5 (ZIP-225) transaction is invalid.
   if (vaultActive && tx.nVersionGroupId != SAPLING_VERSION_GROUP_ID) {
       return state.DoS(dosLevelConstricting, error("ContextualCheckTransaction(): v5 transaction under the vault upgrade"),
                        REJECT_INVALID, "bad-vault-tx-version-group-id");
   }
   ```
   with `vaultActive = NetworkUpgradeActive(nHeight, UPGRADE_VAULT)` computed beside `nu5Active` (the function already has the height and `chainparams`). Four-part check: *DigiByte has no transaction-version split (one `nVersion`, DigiDollar bit-packs it); the Ycash equivalent is `nVersionGroupId` gating by network upgrade (NU5 admits ZIP-225), which lacks any vault rule; the adaptation is a Vault-gated version-group restriction.* Tier: a check on an existing transaction field under the existing activation; no new field, opcode or state.
5. `src/init.cpp` after the `-nuparams` loop (`:1475`), regtest only: if `UPGRADE_VAULT` has a height and any of `UPGRADE_NU5..UPGRADE_NU6_2` has one, `return InitError("-nuparams: NU5..NU6.2 cannot be scheduled together with the Vault upgrade (quantum spec R-A3; ycash6 builds V1 history-tree leaves in the Vault epoch)")`. This refuses the whole configuration, not only NU5 ≤ Vault, because the history-tree inconsistency makes any order unusable; state that in the message.
6. `src/vault/node.cpp` `RecheckPQScripts` (`:171-178`) and `RecheckTemplateScripts` (`:205-215`), `src/rpc/vault.cpp` `TxData`: with v5 invalid the placeholders are provably inert; keep them, but replace the "(a v4 sighash ignores them)" comment with an assertion-grade check: `if (tx.nVersionGroupId != SAPLING_VERSION_GROUP_ID) return std::string("non-v4 transaction (R-A3)")` at the top of both rechecks (evicts explicitly and loudly rather than computing a wrong digest), and the same guard in `TxData`.
7. `src/test/pq_script_tests.cpp:935-954`: delete the v5 "expected OK" block or invert it into "the script layer alone cannot see the version rule; the transaction layer refuses v5 under Vault" by adding a `ContextualCheckTransaction` test (see §5). Do not leave a test asserting the unspecified behaviour as expected.

**ycash-dd (parity test only):**
8. `src/test/vault_state_tests.cpp` or a new `vault_tx_version_tests.cpp`: `ContextualCheckTransaction` on regtest params with Vault active and a transaction with `nVersionGroupId = 0x26A7270A` (ZIP-225) → rejected (`bad-sapling-tx-version-group-id` on dd — the reason string differs by line; assert rejection, document the string difference in `docs/mapping.md`).

## 5. Tests

- ycash6 unit (`src/test/`): regtest params with Canopy at 1, NU5 at 5, Vault at 10 (set directly via `UpdateNetworkUpgradeParameters` in the fixture, bypassing the new `InitError`): a v5 transaction at height 8 passes the version-group check, at height 10 fails with `bad-vault-tx-version-group-id`; a v4 transaction passes at both.
- ycash6 functional: `vault_upgrade.py` (or `yellowback_wr_flags.py`, the flags suite) starts a node with `-nuparams=f919a198:5 -nuparams=6d5b7a31:10` and asserts start-up fails with the R-A3 message (`start_node` raises; check `debug.log`/stderr).
- ycash6 unit: `RecheckPQScripts` / `RecheckTemplateScripts` on a v5 transaction return the R-A3 string (callable from `pq_script_tests.cpp` with a `CCoinsViewCache`).
- dd unit (§4 step 8). Cross-line: `vault_vectors.json`, `pq_vectors.json` unchanged (no message change) — the CI vector `cmp` proves it.
- librustzcash6 follow-up tests are in report `LOW-04-F-6-…`.

## 6. Acceptance criteria

- R-A3 present in the quantum spec and the upgrade plan; `make spec-check` clean; mapping row updated.
- ycash6: a v5 transaction is invalid at any height where `UPGRADE_VAULT` is active (mempool and block); a regtest node refuses to start with NU5..NU6.2 and Vault both scheduled; the two rechecks and `TxData` refuse non-v4 transactions explicitly; `pq_script_tests.cpp` no longer asserts v5-under-Vault as expected.
- Consensus PR reviewed by two people independent of the author (review gate), with the four-part check and the tier answer in the body; `src/main.cpp` delta on ycash6 is the one clause.
- dd parity test present; both lines' functional merge gates green.

## 7. Risks and side effects

- Consensus on ycash6 only in the sense that no current network can reach the clause (NU5 unscheduled); the lines stay in step because dd already rejects every non-Sapling version group. If Ycash ever schedules NU5, this rule says v5 is invalid *under Vault* — i.e. NU5 cannot be activated on a Vault chain without a further upgrade that defines the ZIP-244 message; the owner must accept that (record it with the U-decision in §15.0).
- The regtest `InitError` removes a configuration some future test might want (NU5+Vault); it was already broken (history tree), so nothing is lost.
- No vector regeneration, no client change (YEW, Hawkeye, x402, lightwalletd all build v4).

## 8. Effort estimate and dependencies

Spec edits ~1 hour; ycash6 code + tests ~half a day; review gate adds the two-reviewer cycle (~1 day calendar). **Followed by** `LOW-04-F-6-librustzcash6-vault-v5-orchard-consistency.md` (crate consistency + ycash6 re-pin), which depends on this decision. Independent of every other report.

## Completion record

- **Completed:** 2026-10-13T11:21Z
- **Merged:** ycash6 ccc6d7e50, ycash-dd (48da2863b merged), workspace 4e72e23, ycash-infra 9d19079. CONSENSUS 5a3992c5a (v5 / non-Sapling version group invalid under Vault) plus c630d44ef (DoS level potentially-relaxing). Owner decision 2026-10-13: U-26 (a), v4-only. Start-up refuses NU5..NU6.2 with Vault, and Vault without Sapling, on every network; the docker entrypoints write the full upgrade list.
- **Review gate:** two reviewers, approved after follow-ups (the docker fix).
- **Verification:** Integration run 2026-10-13 (both node lines built; full test_bitcoin dd 872/872, ycash6 923/923; qa/yellowback-audit.sh dd --mode upgrade rc 0 (18 PASS), ycash6 --report-only rc 0; functional suites pass; vault_vectors / golden / pq vectors byte-identical across lines). Logs: wt/scratch/integ/.
