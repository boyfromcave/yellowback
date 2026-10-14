# LOW — 01/V-4, 01/V-5 — Template-spend malleability (selector and extra pushes outside the sighash) and the signature-free APP branch on ungoverned tags

**Repos / branches to change:** `ycash-dd` and `ycash6` (policy, wallet RPC, tests, docs), branch `fix/01-V-4-template-spend-policy` off `upgrade/vault` in each; `yellowback` workspace (plan §15.3/§15.6 and quantum spec text). The optional consensus clause for V-5 rides on report `R4` (01/V-1) if that PR is taken.
**Audit source:** `01-vault-primitive-consensus.md` §V-4 (`:104-112`), §V-5 (`:114-120`); `verification/01-verification.md` rows V-4/V-5 (`:17-18`), detail (`:112-125`).
**Status:** done — completed 2026-10-13T11:21Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13, re-confirmed 2026-10-14 at ycash-dd 3fe3492b6 and ycash6 1ebfee622; nightly tier pending the owner's dispatch)

## 1. Finding

**V-4 (txid malleability of every template spend).** Both owner branches of a V end in the same `<ownerHash> <scheme> OP_CHECKPQSIG`, and `OP_CHECKPQSIG` hashes the *whole* script as `scriptCode` (OP_CODESEPARATOR is disabled in Ycash), so one owner signature verifies under selector 2 (OWNER, past `ownerHeight`) and under selector 3 (OWNER-RELEASED, set released): whenever both conditions hold, a relay node or miner may swap `OP_2`/`OP_3` in the scriptSig. Likewise `OP_CHECKSETSIG` pops exactly `k` signatures and `CLEANSTACK` is a policy flag, so `<junk> <sig_1>..<sig_k> OP_1` is a consensus-valid block spend. Effect: a third party can change the txid of a template spend in flight; any transaction chained on that txid (a pre-built cancel of a *mempool* intent — plan finding (65) — or a client's unconfirmed change) is invalidated. No funds move; state rules see no difference between selectors 2 and 3 on a V (both only subtract `lockedValue`). The plan records the extra-push case ((5), §15.5 reconciliation); the selector case was new to the audit (the quantum spec `:56` mentions "the selector is outside the sighash" for a different point).

**V-5 (APP branch needs no signature).** The APP branch is `OP_4 OP_EQUALVERIFY <appHeight> OP_CHECKLOCKTIMEVERIFY`, ending with `appHeight` (true) on the stack. For a V whose tag has a registered module (`YED\0`) the module's `ValidateSpend` governs the spend; for an unregistered tag with `appHeight ≠ 0` the vault becomes anyone-can-spend-into-intents from `appHeight` under S-2/S-3, paying any recipient, with the cancel set's `delay` as the only backstop. The primitive accepts the shape; only `appHeight = 0` is refused for selector 4 (S-4). Hawkeye builds bridge vaults with `app_height: 0` (`hawkeye/crates/hawkeye/src/engine/roll.rs:219-223`, `cli.rs:215`), YEW builds YED vaults (registered tag), so no current client is exposed; a user calling `vault_lock` with `appheight` on a custom tag would be. Both verified Low.

## 2. Root cause

ycash-dd `055d9c2` (identical on ycash6 `e866c45`: `src/vault/template.cpp`, `state.cpp` byte-identical; opcode bodies identical):
- `src/vault/template.cpp:106-120` `VaultSkeleton`: indices 18-24 (selector 2) and 30-36 (selector 3) both end `F F VAULT_OP_CHECKPQSIG`; `:179-192` `BuildVault` emits them; `:191` `OP_4 OP_EQUALVERIFY appHeight CLTV` (V-5).
- `src/script/interpreter.cpp:1150` the opcode hands `script` (the executing script, never split) to `checker.CheckPQSig`; `:322` OP_CODESEPARATOR disabled; `:1036-1046` `OP_CHECKSETSIG` pops exactly `*k` signatures; CLEANSTACK only in `STANDARD_SCRIPT_VERIFY_FLAGS`.
- `src/vault/state.cpp:495` only `SEL_APP && appHeight == 0` is refused; `:548-558` V-1 output rules do not consult `FindModule(tag)`; `:580-586` module dispatch runs only when a module is registered.
- `src/rpc/vault.cpp:1313`, `:1330` `vault_lock` takes `appheight` from the caller (default 0); `:1836-1853` `vault_app` builds selector-4 spends.

## 3. Fix options considered

**V-4**
1. Bind the selector (and thereby the branch) into the signed message: add the selector byte to `SetSigMsg` and to the PQ message, or compute a per-branch `scriptCode`. Consensus change, regenerates `vault_vectors.json` and `pq_vectors.json`, touches every client's signer (YEW, Hawkeye, x402 vectors), and does not remove the extra-push malleability. Rejected for a Low finding by the prime directive (smallest footprint).
2. Policy standardness for template inputs (CLEANSTACK-equivalent): a template input's scriptSig must leave exactly the arguments its selector consumes, and the selector must be the lowest-numbered branch that is satisfiable — relay-level only, miners can still malleate. Cheap, no consensus. **Recommended**, together with 3.
3. Document the malleability as a property (plan §15.3/§15.6, quantum spec) and require clients not to chain on unconfirmed template-spend txids (Hawkeye rebuilds a cancel once the intent confirms; YEW/x402 never chain on template spends). **Recommended.**

**V-5**
4. Consensus V-1 clause: a V output with `appHeight ≠ 0` whose tag has no registered module is invalid (`bad-txns-vault-app`). Smallest in-tier rung (one clause in an existing rule), deterministic (modules are compiled-in, `FindModule` is the same on every node). Goes through the review gate. Recommended **only bundled with the R4 (01/V-1) consensus PR**, which already adds a clause to the same function; not worth a gate round of its own.
5. Wallet/RPC refusal: `vault_lock` refuses `appheight ≠ 0` for a tag without a module unless `"allowapp": true`; `vault_decodescript` flags the shape. No consensus. **Recommended now.**

## 4. Recommended fix

Both lines (policy and RPC files differ only by 6.20.0 API shape).

1. **Policy (`src/policy/policy.cpp`, `AreInputsStandard`, the V/I-input `continue` at `:187-189`):** replace the `continue` with a standardness check for template inputs: evaluate the scriptSig with `EvalScript` (push-only is already required at `:109-116`); read the selector as the top element; require the push count to equal the selector's argument count (`selector 1` on V: `k+2` with `k = SetThreshold`; `selector 2/3`: `s + p + 3` PQ pushes + selector, i.e. the same `s+p+2` shape as `TX_PQPKH` at `:191-204` plus the selector; `selector 4`: 1; I: `selector 1`: 1, `selector 2`: `k+2`, `selector 3`: PQ shape + 1); reject otherwise (`non-standard template scriptSig`). This needs the set snapshot for `k`; `AreInputsStandard` is called from `AcceptToMemoryPool` where `vaultSnapshot` is in hand (`main.cpp:1866-1872`) — pass it, or restrict the check to the PQ-shaped selectors (2/3 on V, 3 on I) and selector 4, and leave set-signed selectors to the existing `MAX_STANDARD_SCRIPTSIG` bound; the latter is enough for the owner-branch swap and keeps the change local. Do **not** try to canonicalise selector 2 vs 3 at the policy level (both are legitimately chosen by the owner); the txid-malleability residue is documented instead.
2. **Wallet (`src/rpc/vault.cpp` `vault_lock`, `:1330`):** after parsing `appheight`, `if (vp.appHeight != 0 && !vault::FindModule(vp.tag) && !allowApp) throw JSONRPCError(RPC_INVALID_PARAMETER, "appheight on a tag without a module makes the vault anyone-can-spend into intents from that height (V-5); pass \"allowapp\": true to build it anyway")`. Document in `doc/vault-rpc.md` under `vault_lock`; regenerate `doc/vault-rpc-contract.json` if the parameter set changes (`qa/vault-rpc-contract.py`).
3. **Docs:** upgrade plan §15.3 (templates) — one paragraph "Malleability: the selector and any extra scriptSig pushes are outside every signature; a template spend's txid is third-party malleable until confirmed; clients must not chain on an unconfirmed template-spend txid; the node's policy refuses non-canonical shapes but a miner may still re-encode" — and §15.6 S-4 note for V-5 ("an `appHeight ≠ 0` on a tag without a module is a signature-free branch; the wallet refuses it; module-less APP is not a supported shape"). Quantum spec: cross-reference at `:56`. `make spec`, `make spec-check`. `docs/mapping.md` §22 row for the CLEANSTACK-is-policy mismatch (Bitcoin Core's `SCRIPT_VERIFY_CLEANSTACK` is consensus under SegWit; Ycash has it as policy only).
4. **Client note (not this PR, open issues):** Hawkeye must rebuild a cancel against the *confirmed* intent txid (05 area); chain-viz should show template spends as "txid may change until confirmed".
5. **Optional consensus clause (only inside the R4 PR):** in `state.cpp` V-1 loop (`:548-558`) add `if (v.appHeight != 0 && !FindModule(v.tag)) return std::string("bad-txns-vault-app");` with the four-part check in the PR body: *DigiByte has no template branch without a signer (every DigiDollar path is MuSig2- or key-signed); the Ycash equivalent is the CLTV-only APP branch, which lacks a signer by design for module governance; the adaptation is to admit the branch only where a module governs it.* Tier answer: a clause on an existing rule, per-vault, primitive-level.

## 5. Tests

- `src/test/vault_policy_tests.cpp`: (a) a selector-3 scriptSig carrying a selector-2 owner signature is consensus-valid (`VerifyScript` with `SCRIPT_VERIFY_VAULT` ok) — documents V-4 — and non-standard only if the policy canonicalisation applies (it does not for 2↔3, so assert standard); (b) `<junk> <sig> OP_1` on a V: consensus-valid, `AreInputsStandard` false; (c) `TX_PQPKH`-shaped selector-2 scriptSig with one extra push: non-standard.
- `src/test/vault_script_tests.cpp`: extend `vault_opcodes_without_flag` (`:353-381`) with the T-4 assertion the verifier asked for: a scriptSig containing 0xc0 behaves the same before and after activation (push-only is policy).
- Functional `vault_primitive.py`: `vault_lock` with `appheight` on tag `TEST` → RPC error; with `"allowapp": true` → built; `vault_app` after `appheight` by a third-party wallet succeeds (documents V-5 on an ungoverned tag, both nodes agree), and a cancel within `delay` returns the value.
- If the consensus clause is taken: `vault_state_tests.cpp` case `bad-txns-vault-app` for an unregistered tag with `appHeight ≠ 0`, and `YED\0` with `appHeight ≠ 0` still accepted; `vault_vectors.json` unchanged (no message changes).

## 6. Acceptance criteria

- Policy: the malleated shapes in §5(b)(c) are refused by `AcceptToMemoryPool` with a non-standard reason and accepted in a block (`generate` with `-acceptnonstdtxn` or `submitblock`), on both lines.
- `vault_lock` refuses module-less `appheight ≠ 0` without `allowapp`; contract JSON regenerated if changed; `vault_rpc_contract.py` passes.
- Plan §15.3/§15.6 and the quantum spec carry the malleability and APP statements; `make spec-check` clean.
- No change to `vault_vectors.json` / `pq_vectors.json` unless the consensus clause (which changes no message) is taken — and even then none.

## 7. Risks and side effects

- Policy only: a stricter `AreInputsStandard` could refuse a legitimate client-built template spend whose scriptSig shape differs from the node's canonical pushes (YEW's owner spends use the same `PQScriptSigPushes` chunking per `vault_vectors.json`; Hawkeye uses the node's RPCs). Run YEW's vectors (`yew/core/tests/vectors`) and `vault_rpc_contract.py` before merging; keep the check shape-based, never byte-based.
- Residual: miners can still malleate; the documentation is the real fix for V-4. The consensus clause for V-5 must not land outside the review gate.

## 8. Effort estimate and dependencies

Policy + RPC + docs + tests: ~1 day per line (ycash6 by delta). Consensus clause: +½ day only as part of R4 (01/V-1), which must be taken first if the clause is wanted. No other dependencies.

## Completion record

- **Completed:** 2026-10-13T11:21Z
- **Merged:** with fix/vault-replay. CONSENSUS V-5 clause d92872242 / 3f6ead234 (an APP branch only on a registered tag). Template-spend relay policy (IsStandardTemplateScriptSig); vault_lock refuses APP unless the module governs a set (2a4bbad82); new vault_policy.py runs with standardness enforced (-acceptnonstdtxn=0) and passes on both lines.
- **Review gate:** two reviewers, APPROVE WITH NITS (addressed).
- **Verification:** Integration run 2026-10-13 (both node lines built; full test_bitcoin dd 872/872, ycash6 923/923; qa/yellowback-audit.sh dd --mode upgrade rc 0 (18 PASS), ycash6 --report-only rc 0; functional suites pass; vault_vectors / golden / pq vectors byte-identical across lines). Logs: wt/scratch/integ/.
