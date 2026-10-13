# MEDIUM — 07/F-1 — Narrow the mempool `DoS(0)` carve-out for template-input transactions to the set-state-dependent script errors

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/07-F-1-dos-carveout` off `upgrade/vault` in each: `src/main.cpp` (`AcceptToMemoryPool` hook only), `contrib/yellowback/pq-dos/pq_dos.py` (ycash-dd only — the tool does not exist in `ycash6`; run it with `BITCOIND=` pointing at the ycash6 binary), `doc/yellowback-pq-dos.md`, a functional test. Policy, not consensus — but `src/main.cpp` is in the review gate's file list, so the diff is reviewed under it.
**Audit source.** `07-node-rpc-mempool-durability-ci.md` F-1 (High); `verification/07-verification.md` F-1 ("PARTIALLY CONFIRMED, Medium — the carve-out is real and over-broad; per-byte cost ~10× lower than reported and within the Sapling baseline"), N-3; `00-consolidated.md` row 07/F-1 (Medium, ↓ from High), remediation R6.
**Status:** done — completed 2026-10-13T12:00Z (merged locally on `upgrade/vault`; not yet pushed)

## 1. Finding

`AcceptToMemoryPool` sets `fVaultTemplateInput = vaultFlags && vault::HasTemplateInput(tx, view)` (`ycash-dd/src/main.cpp:1869`) and, when true, runs both `ContextualCheckInputs` passes against a throwaway `CValidationState` and re-reports **any** failure as `state.DoS(0, …)` (`:1870-1880`, `:1888-1893`). The comment's justification — a template input's `OP_CHECKSETSIG`/`OP_CHECKSETDORMANT` reads set state the relaying peer need not share — is right for `SCRIPT_ERR_SETSIG` and `SCRIPT_ERR_SETSIG_COUNT` (`src/script/script_error.h:56-58`; the only errors the two opcodes raise, `src/script/interpreter.cpp:1018-1066`), but `HasTemplateInput` (`src/vault/node.cpp:102-113`) is true for any V or I coin whatever branch the scriptSig takes, so the exemption also covers the V/I **owner** paths (`OP_CHECKPQSIG` over an SLH-DSA or Falcon signature — a garbage SLH-DSA signature costs a full ~250–380 µs verification, never cached, run up to three times by the branch-ID and mandatory retries, `main.cpp:2636-2680`) and **every other input** of the transaction (garbage ECDSA on sibling P2PKH inputs). The transaction never enters the mempool, so the attacker's inputs are never spent and no fee is paid; `recentRejects` is beaten by a fresh signature nonce. `Misbehaving` is never incremented.

Severity Medium after verification: the per-byte CPU cost (≈ 0.11–0.16 ms/KB SLH-DSA, ≈ 0.25–0.4 ms/KB for the ECDSA variant) sits well below the ≈ 10 ms/KB stock Ycash already tolerates from a bad-Sapling-proof flood (per-IP bounded at 10 messages), and bans are per IP. Still strictly broader than its justification, and `doc/yellowback-pq-dos.md:189-199` lists the exemption as "Unverified, from code reading only". Same hook on `ycash6` (`src/main.cpp:2137-2160`).

## 2. Root cause

- `src/main.cpp:1866-1893` (ycash6 `:2133-2160`): the carve-out is keyed on *having* a template input, not on *which error* the script check returned. `ContextualCheckInputs` encodes the `ScriptError` only in the reject reason string: `"mandatory-script-verify-flag-failed (%s)"` with `ScriptErrorString(check.GetScriptError())` (`main.cpp:2679-2680`; ycash6 `:3000`), `"non-mandatory-script-verify-flag (%s)"` (`:2665`, already `Invalid`, DoS 0) or `"old-consensus-branch-id …"` (`:2652-2657`, DoS 10).
- `src/vault/node.cpp:102-113` (`HasTemplateInput`): shape-only.
- `contrib/yellowback/pq-dos/pq_dos.py:465-560` (`sc_invalid`): measures garbage `TX_PQPKH` spends only; no V-owner case; `doc/yellowback-pq-dos.md:97` records "Misbehaving 0 → 100, disconnected" for `TX_PQPKH` and `:189-199` the unmeasured exemption.

## 3. Fix options considered

1. **Narrow by error (recommended).** After a failing pass, apply `DoS(0)` only when the throwaway state's reject reason names `SCRIPT_ERR_SETSIG` or `SCRIPT_ERR_SETSIG_COUNT` (the dormancy failure of `OP_CHECKSETDORMANT` is also `SCRIPT_ERR_SETSIG`, `interpreter.cpp:1066`); otherwise copy the throwaway state's own score, code and reason into `state` (`CValidationState::IsInvalid(int& nDoS)`, `src/consensus/validation.h:66-70`). Zero signature changes, a dozen lines in the hook already touched, no consensus effect.
2. **Narrow `HasTemplateInput` to the set-signed selectors** (parse the selector push). Rejected: the selector is attacker-chosen (01/V-4 — extra pushes are consensus-valid), selector 3 (`OP_CHECKSETDORMANT`) is state-dependent too, and a V with selector 2 whose set is released still runs the PQ check — the error, not the branch, is the right key.
3. **Thread the `ScriptError` out of `ContextualCheckInputs`** (an out-parameter or a field on `CValidationState`). Cleaner, but touches a consensus-adjacent signature in `main.cpp` and `consensus/validation.h` for a policy decision. Rejected for footprint (rule 7: the upgrade adds, it never tidies).

**Rule-4 four-part check (PR body, brief — policy change).** DigiByte does **X** = score script failures per `ScriptError` in `ref/digibyte/src/validation.cpp` (`CheckInputScripts`, mechanism **M** = `TxValidationResult::TX_NOT_STANDARD` vs `TX_CONSENSUS` reasons carried in a structured `TxValidationState`). Ycash's **Z** = `CValidationState` with a free-text reject reason (`ycash-dd/src/consensus/validation.h`), which lacks **M**. So **W** = match the reason string that `ContextualCheckInputs` itself formats from `ScriptErrorString` for the two set-opcode errors, and otherwise forward the stock score. **Tier:** mempool policy (no consensus rung); the `main.cpp` lines go through the gate as a diff review only.

## 4. Recommended fix

1. `src/main.cpp:1866-1893` (ycash6 `:2133-2160`): keep `vaultScriptState`; replace both `if (fVaultTemplateInput) state.DoS(0, …)` blocks with one helper (a lambda in the hook):
   ```
   // Only the set opcodes read state the peer need not share (SCRIPT_ERR_SETSIG, SCRIPT_ERR_SETSIG_COUNT;
   // OP_CHECKSETDORMANT fails with the former). Every other failure keeps the stock score.
   int nDoS = 0; vaultScriptState.IsInvalid(nDoS);
   const std::string& why = vaultScriptState.GetRejectReason();
   const bool setState = why.find(ScriptErrorString(SCRIPT_ERR_SETSIG)) != std::string::npos ||
                         why.find(ScriptErrorString(SCRIPT_ERR_SETSIG_COUNT)) != std::string::npos;
   state.DoS(setState ? 0 : nDoS, false, vaultScriptState.GetRejectCode(), why, vaultScriptState.CorruptionPossible());
   ```
   (`ScriptErrorString` is in `script/script_error.h`, already included via `script/interpreter.h`.) The `old-consensus-branch-id` (10) and `non-mandatory-script-verify-flag` (0) paths forward unchanged. A comment pins the two strings to `script_error.cpp:69-72` so a wording change there fails the new unit assertion below.
2. `src/vault/node.cpp` `HasTemplateInput`: unchanged (it still decides whether the throwaway state is used).
3. `contrib/yellowback/pq-dos/pq_dos.py` `sc_invalid` (`:465`): add two cases — (a) **V-owner garbage**: `vault_lock` with `ownerheight: 1` and a dust amount, spend it with selector 2 and a correctly sized garbage SLH-DSA signature (and the Falcon variant), from a *peer* (the `sc_flood` peer path, `:557-568`, reads `banscore`): expect `banscore 100`, disconnected, and the per-message time; (b) **set-signed garbage**: selector 1 on a V (or 2 on an I) with a bad 65-byte set signature: expect `banscore 0`. Record the measured ms/KB figures.
4. `doc/yellowback-pq-dos.md`: move the `:189-199` paragraph out of "Unverified" into the measured table with the two new rows; state the narrowed rule.
5. Both lines: the same hunk in `ycash6/src/main.cpp:2137-2160` (the hook returns `false` instead of `error(...)` there — keep that).

## 5. Tests

- **Unit (`src/test/vault_script_tests.cpp` or a new `vault_policy_tests` case):** `ScriptErrorString(SCRIPT_ERR_SETSIG)` and `…SETSIG_COUNT` equal the two literals the hook matches (guards the string match).
- **Functional (new `qa/rpc-tests/vault_dos.py`, registered in `rpc-tests.py` and the workflow's `YELLOWBACK_SCRIPTS`; both lines):** via `mininode` send (a) a V-owner spend with a garbage PQ signature → `getpeerinfo()[0]['banscore'] == 100` and the peer disconnected (`DOS_LEVEL` as for `TX_PQPKH`, `doc/yellowback-pq-dos.md:97`); (b) a P2PKH sibling input with a garbage ECDSA signature on a transaction that also spends a V → 100; (c) a selector-1 unlock with `k` bad set signatures → 0, still connected; (d) a selector-3 owner spend of a V whose set is **not** released (`OP_CHECKSETDORMANT` false) → 0; (e) a selector-1 spend with a *valid* set signature from a set the node does not know yet (built against a peer's tip) → 0 (the original justification). `grep Misbehav qa/rpc-tests/vault_*.py` is no longer empty.
- **Measurement:** `pq_dos.py` scenario `invalid` with the two new cases, run against both binaries, numbers into the doc.

## 6. Acceptance criteria

- A garbage owner/sibling signature on a template-input transaction scores like the same signature on a `TX_PQPKH`/P2PKH spend (100); `SCRIPT_ERR_SETSIG`/`SETSIG_COUNT` failures score 0.
- `vault_dos.py` passes on both lines; `doc/yellowback-pq-dos.md` carries measured figures for the V-owner case; `yellowback-audit.sh` lists the new script.
- No change under `src/vault/`, `src/script/`, `src/consensus/`.

## 7. Risks and side effects

- **No consensus effect; no chain split.** The score is per node.
- **Accidental bans:** a wallet signing a V-owner spend for the wrong branch ID still gets the `old-consensus-branch-id` DoS 10 path (unchanged); a transaction that is valid on a peer's tip but not ours for a *set-state* reason stays at 0. A transaction that spends a V *and* fails an ordinary input's signature on our tip only (e.g. a reorg changed the coin) is a corner stock Ycash already has.
- **String coupling:** the match depends on `script_error.cpp` wording; the unit assertion makes a rewording fail loudly.

## 8. Effort estimate and dependencies

- Hook + unit assertion: 0.25 day; `vault_dos.py`: 0.75 day; `pq_dos.py` cases + measurement + doc: 0.5 day; ycash6 hunk + run: 0.25 day.
- Dependencies: none. Independent of every other report; can land first.

## Completion record

- **Completed:** 2026-10-13T12:00Z
- **Merged:** ycash-dd 6191e186a + 6021cb216, ycash6 7bfc1f7dc + 0b7cf5d8c, workspace ca45f85 + 57f2465 (branches fix/mempool, fix/mempool-2). Policy only (AcceptToMemoryPool): the template input is checked alone first (selected by ParseVault/ParseIntent); DoS 0 only for its own set-state failure (SETSIG, or VERIFY at selector 3); everything else keeps the stock score, so garbage owner or sibling PQ signatures score 100. A previous-branch re-run keeps the stock old-consensus-branch-id diagnosis (DoS 10). At most two garbage set-signature recoveries at DoS 0.
- **Review gate:** two independent reviewers. REQUEST CHANGES on round 1 (the TX_PQCHANNEL bypass), then APPROVE on the revision and on both follow-ups.
- **Verification:** final pre-push run at ycash-dd 8af82551b / ycash6 047b561ac. Builds rc 0; vault_*, DoS_tests, yellowback_* and pq_* unit tests pass; vault_dos, vault_primitive, vault_rpc, vault_refee and yellowback_upgrade pass on both lines; both audits rc 0.
- **Open:** port ycash6's ORPHAN_TX_EXPIRE_TIME to ycash-dd (parity follow-up).
