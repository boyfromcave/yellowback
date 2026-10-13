# INFO — W3-V-5, W3-V-7, W3-V-9 — Vault primitive notes for the upgrade documentation: the `YV` OP_RETURN namespace becomes consensus, BIP68 applies to every transaction, and cross-role equivocation with one sighash is slashable (plus the missing same-role unit positive)

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W3-V-5-V-7-V-9-notes` off `upgrade/vault` in each: `doc/vault-rpc.md` (node-behaviour section `:572+`, `set_equivocation` `:263-271`), `ycash-dd/doc/release-notes.md` and `ycash6/doc/yellowback-release.md` (upgrade notes), `src/test/vault_state_tests.cpp` (one unit positive). `yolo` (separate repo, `upgrade/vault`): `README.md` / pool docs — one paragraph. Workspace: `docs/plans/yellowback-upgrade-plan.md` §15.5 (equivocation row), §15.2 (BIP68). Documentation and one test only; no code change.
**Audit source.** Wave 3: `docs/audits/quantum-vault-ecosystem-wave3/01-vault-primitive-consensus.md` W3-V-5 (lines 80-82), W3-V-7 (lines 88-90), W3-V-9 (lines 96-98), test-fidelity note on equivocation (line 109); `docs/audits/quantum-vault-ecosystem-wave3/verification/01-verification.md` W3-V-5 (line 17), W3-V-7 (line 19), W3-V-9 (line 21) — all "CONFIRMED, Info"; `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row W3-V-3..V-9. Wave 4: `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md` §1.1 row W3-V-5, W3-V-7, W3-V-9 (line 66, "STILL OPEN … one line-shift").
**Status:** pending — re-verified at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): open on both lines (consensus files unchanged since wave 3; only the `src/rpc/vault.cpp` role-fixing cite moved).

## 1. Finding

- **W3-V-5 — the `YV` namespace.** `IsActOutput` is "OP_RETURN then a push starting `59 56`" (`ycash-dd/src/vault/act.cpp:186-195`). From activation, `ApplyTxInner` classifies such an output as an act (`src/vault/state.cpp:428-432`), it must decode and apply or the transaction is invalid (`:604-608`), and a coinbase carrying one is `bad-vault-act-coinbase` (`:669`), which invalidates the block. Any application that today writes OP_RETURN memos beginning with ASCII `YV` becomes consensus-invalid after activation, and pool software must never put such a push in a coinbase output. The standard tagged-OP_RETURN trade-off; it needs to be in the release notes and the pool documentation.
- **W3-V-7 — BIP68 for every transaction.** `ContextualCheckSequenceLocks` runs on every non-coinbase transaction of a vault-active block regardless of `fExpensiveChecks` (`src/main.cpp:3284-3287`), in ATMP (`:1797-1801`) and in the miner (`src/miner.cpp:557-562`); an input with bit 31 clear is a relative lock, and the type flag (bit 22) is a hard invalidity, `bad-txns-vault-timelock` (DoS 100 in a block, 0 in the mempool, `main.cpp:853`). Stock wallets use `0xffffffff`/`0xfffffffe`, and `nSequence = 0` is a lock of 0 blocks, so existing software is unaffected; `removeWithoutBranchId` clears pre-activation transactions at activation. Consistent between mempool, miner and block; worth stating in the upgrade notes for third-party transaction builders.
- **W3-V-9 — cross-role equivocation.** `ApplyAct` rejects an equivocation proof only when `roleA == roleB && sighashA == sighashB` (`src/vault/state.cpp:851`), so (role 1, sighash X) and (role 2, sighash X) by one key for one prevout is slashable — slightly broader than "two different spends". No honest path produces it: a V prevout is only signed with role 1 and an I prevout with role 2, and `set_signunlock`/`set_signcancel` derive the role from the template kind (`src/rpc/vault.cpp:1819-1821`, `:1955-1957`; ycash6 `:1840-1842`, `:1976-1978`). A member who signs an attacker-supplied role outside these RPCs is signing outside the wallet. The same `(role, sighash)` signed twice with different nonces is correctly *not* slashable. Test fidelity: the unit tier's only positive equivocation case is cross-role (`src/test/vault_state_tests.cpp:559-607`); the canonical same-role, two-sighash positive exists only functionally (`qa/rpc-tests/vault_slashing.py:79`, `:132`, `:175`).

All three are identical on `ycash6` (`src/vault/*` byte-identical).

## 2. Root cause

Design choices recorded in the plan (§15.5 act format, lines 937-942; §15.2 BIP68), not stated where third parties (application developers, pool operators, transaction builders, member operators) will read them.

## 3. Fix options considered

1. **Document (recommended)** in the node's upgrade notes, `doc/vault-rpc.md`, the plan and the pool's docs; add the unit positive.
2. **Narrow the equivocation rule to same-role** (consensus). Not justified: no honest path produces cross-role pairs, and the broader rule is simpler to reason about ("one signature per prevout per member"). Rejected.
3. **A versioned/longer act magic** to reduce namespace collisions (consensus, vectors). Not justified by any known `YV` memo user. Rejected.

## 4. Recommended fix

1. **Upgrade notes (`ycash-dd/doc/release-notes.md`, `ycash6/doc/yellowback-release.md`):** a "Vault activation: what changes for everyone" section: (a) from the activation height an OP_RETURN whose first push begins `YV` (0x59 0x56) must be a well-formed vault act or the transaction (or, in a coinbase, the block) is invalid; (b) BIP68 relative lock-times apply to every transaction: `nSequence` with bit 31 clear is a block-height lock, bit 22 (time-based) is invalid; use `0xffffffff`/`0xfffffffe` unless you mean a lock; (c) the policy act size 1,200 bytes.
2. **`yolo` (separate PR):** pool docs — never place a `YV`-prefixed push in a coinbase OP_RETURN (block invalid after activation); yolo builds coinbases from `getblocktemplate` and needs no code change.
3. **`doc/vault-rpc.md`:** `set_equivocation` section — "a proof is two recoverable signatures by one current member over the same `(setId, prevout)` with a different role **or** a different sighash; the wallet signs role 1 only for a vault and role 2 only for an intent — never sign a set message with any other tool". Node-behaviour section — the `YV` and BIP68 rules, one line each.
4. **Plan §15.5** equivocation row: "different `(role, sighash)` — cross-role with one sighash included (W3-V-9, intended)"; §15.2: "BIP68 applies to every transaction from activation (W3-V-7)".
5. **Unit test (both lines):** in `vault_state_tests.cpp` add the canonical positive: one member, two role-1 signatures over two different sighashes for the same prevout → `ACT_SET_EQUIVOCATION` applies, member EJECTED, bond frozen; and the negative: the same `(role, sighash)` signed twice with different nonces → `bad-vault-act-equivocation`.

## 5. Tests

- The unit positive/negative above (would have closed the test-fidelity gap the auditor noted).
- No functional change; `vault_slashing.py` already covers the functional positive.

## 6. Acceptance criteria

- Both lines' upgrade notes carry the `YV` and BIP68 paragraphs; `doc/vault-rpc.md` states the equivocation rule precisely; the yolo docs carry the coinbase rule; the plan rows are updated; the unit tier has a same-role positive.

## 7. Risks and side effects

- None.

## 8. Effort estimate and dependencies

- 0.25 day docs, 0.25 day unit test, both lines; yolo doc PR 0.1 day. Independent.
