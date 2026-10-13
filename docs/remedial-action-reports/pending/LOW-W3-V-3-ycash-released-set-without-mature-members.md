# LOW — W3-V-3 — A set with fewer than `cancelThreshold` mature members is "released" from its first block: a vault locked to it is owner-spendable at once. Refuse in the wallet, document, and put the consensus options to the owner before P8

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W3-V-3-released-at-lock` off `upgrade/vault` in each: `src/rpc/vault.cpp` (`vault_lock`), `src/yellowback/txbuilder.cpp` (the YED mint shape, `YedVaultScript` at `:1468`), `doc/vault-rpc.md` (`vault_lock`, `:284-299`), `qa/rpc-tests/vault_rpc.py`. Workspace: `docs/plans/yellowback-upgrade-plan.md` §15.4 (lines 918-931) — a decision row. Consensus options (§3) are **not** implemented by this report; if the owner takes one, it is a separate consensus PR through the review gate with new vectors.
**Audit source.** Wave 3: `docs/audits/quantum-vault-ecosystem-wave3/01-vault-primitive-consensus.md` W3-V-3 (lines 64-70); `docs/audits/quantum-vault-ecosystem-wave3/verification/01-verification.md` W3-V-3 (verdict line 15, "CONFIRMED, Low (primitive) / open for audit 03 … Spec-conformant (§15.4 lines 921-923). The 'missing test' remark is wrong: `vault_pq_wallet.py:148`, `vault_pq_wallet_restore.py:140` exercise the member-less released set") and §6 (lines 129-139); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row W3-V-3..V-9. Wave 4: `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md` §1.1 row W3-V-3 (line 64, "STILL OPEN … `vault_lock` cite `:1467-1527` is now `:1499-1559` (+32); fix unaffected").
**Status:** pending — re-verified at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): open on both lines (`src/vault/` unchanged since wave 3; `vault_lock` still checks only that the sets are confirmed).

## 1. Finding

`IsDormant` counts members that are **current** (`MEMBER_ACTIVE` and `h ≥ joinHeight + maturity`, `ycash-dd/src/vault/state.cpp:195-198`) and acted within `livenessWindow`; a set is dormant when fewer than `cancelThreshold` such members exist (`:214-222`), and `IsReleased` = dormant ∨ wound down ∨ unknown (`:224-229`). A freshly created set has zero current members and `cancelThreshold ≥ 1` (`SetCreateBody::Valid`, `src/vault/act.cpp:129-131`), so it is released from its first block and stays released until `cancelThreshold` members have matured — at least `maturity` blocks, ≥ 16,128 on mainnet (D-Q-31). V-1 requires only that both sets exist and were created in an earlier block (`state.cpp:562-565`), and `vault_lock` checks only that the sets are confirmed (`src/rpc/vault.cpp:1544`; ycash6 `:1565`). So a vault can be locked to a set that is already released: the owner's OWNER-RELEASED branch (V selector 3, `OP_CHECKSETDORMANT OP_VERIFY … OP_CHECKPQSIG`) is open immediately, and every intent unlocked from it is owner-reclaimable through I selector 3 for as long as the set stays below `cancelThreshold` current members.

This is exactly the spec (§15.4, plan lines 921-923: "Dormant at h: fewer than `cancelThreshold` current members with `lastAct ≥ h − livenessWindow`"; "Released … or the set is unknown") and the owner's recorded non-exclusivity decision (plan lines 924-931, 2026-10-12). It is the vault owner's own value, so not theft by the primitive's model — but a module that counts the vault as locked while its set matures, or an application that pays a third party through an intent, inherits an owner exit it may not expect. For YED, `yellowback::Module::ValidateSpend` refuses V + selector 1 and I + selector 3 but allows **V + selector 3** (`src/yellowback/module.cpp:80-86`); whether a mint can be made against the attestor set during its first `maturity` blocks (and then owner-released) is a module question for audit 03 / the YED owner. Same on `ycash6` (`src/vault/*` byte-identical).

## 2. Root cause

- `src/vault/state.cpp:214-229` — "released" does not distinguish "never reached `cancelThreshold` current members" from "lost them".
- `src/vault/state.cpp:562-565` — V-1 does not look at the set's liveness.
- `src/rpc/vault.cpp:1499-1559` (`vault_lock`; ycash6 `:1520-1580`) — no warning or refusal for a released set.

## 3. Fix options considered

1. **Wallet refusal + documentation (recommended now, non-consensus).** `vault_lock` refuses to lock into a set (or cancel set) that is released at the next height unless `{"allowreleased": true}`; `vault_getinfo`/`set_getinfo` already expose the state for others. Prevents the accident; changes no rule.
2. **Consensus (a): V-1 requires the set not released at h** (or `CountCurrent ≥ cancelThreshold`) at creation. Closes the "lock into a released set" case for every creator; does not affect a set that becomes dormant later (the intended exit). Needs a spec row, vectors, the review gate; a module that mints into a not-yet-mature set (YED's first mints) would be refused until the attestor set matures — a product decision.
3. **Consensus (b): `IsReleased` treats a set that has never reached `cancelThreshold` current members as not released until `createHeight + maturity + livenessWindow`.** Also removes the "set with no members ever → perpetually owner-spendable" case, but changes `OP_CHECKSETDORMANT`'s semantics for every vault and needs a new per-set flag ("has been live") in state. Larger.
4. **Accept and document only.** Leaves the RPC accident open.

## 4. Recommended fix

1. **`vault_lock` (`src/rpc/vault.cpp:1499-1559`; ycash6 `:1520-1580`):** after the "confirmed sets" check (`:1544`; ycash6 `:1565`), `if (snap->IsReleased(vp.setId, NextHeight()) || snap->IsReleased(vp.cancelSetId, NextHeight()))` and the options lack `"allowreleased": true` → `RPC_INVALID_PARAMETER` `vault-lock-released: set <id> has fewer than cancelThreshold current, live members at the next block (dormant; a new set is dormant until cancelThreshold members have matured): the owner could spend this vault at once with its owner key (selector 3). Pass allowreleased=true to lock anyway.` Apply the same check in the YED mint builder (`src/yellowback/txbuilder.cpp:1468`, `YedVaultScript` → `vault::BuildVault` via `src/yellowback/script.cpp:98`) with the module's own error text — the attestor set is both `setId` and `cancelSetId` there.
2. **Docs.** `doc/vault-rpc.md` `vault_lock`: the refusal and its reason; the set life-cycle sentence "a new set is released (owner-spendable vaults) until `cancelThreshold` members are current". Plan §15.4: add under the 2026-10-12 decision a 2026-10-13 row "W3-V-3: released-from-creation is intended / or option (a)/(b) chosen" — **the owner decides before P8**; until then the wallet refusal stands.
3. **Hand-off to the module owner.** Record in the YED plan (or audit 03's tracker) the question: can a YED vault exist while the attestor set has fewer than `cancelThreshold` current members, and if so is V + selector 3 acceptable then? (Module-side answer, not this report.)

## 5. Tests

- **Functional `qa/rpc-tests/vault_rpc.py` (both lines):** `set_create` a set, then `vault_lock` into it at once → `vault-lock-released`; with `allowreleased: true` → locked, and `vault_ownerspend` succeeds immediately (documents the semantics; the verifier notes `vault_pq_wallet.py:148` / `vault_pq_wallet_restore.py:140` already exercise owner spends of a member-less set — reuse their shape); after `cancelThreshold` members join and mature, `vault_lock` without the option succeeds.
- **Unit (optional, documents the predicate):** `vault_state_tests.cpp` — `IsReleased` true for a member-less set at `createHeight + 1`, false once `cancelThreshold` members are current and live.

## 6. Acceptance criteria

- `vault_lock` (and any YED V builder) refuses a released set without an explicit option, on both lines; the doc says why; the plan carries the owner's decision on the consensus options (or the explicit "kept as specified").

## 7. Risks and side effects

- None for consensus. Scripts and clients that lock into brand-new sets on regtest must pass `allowreleased` or let the set mature (regtest maturity is small, `nVaultMinSetMaturity`). Hawkeye/bridge flows lock into the mature attestor set — unaffected; check `contrib/yellowback/devnet/bridge-sim` and `upgrade-walk`.
- If the owner later picks consensus option (a) or (b): a vector/spec change before P8, both lines, review gate.

## 8. Effort estimate and dependencies

- Wallet refusal + docs + test: 0.5 day both lines. Owner decision: before P8. Consensus option, if taken: 1.5-2 days + review gate + vectors.
- Dependencies: none. Context: the done `INFO-02-N-1-01-V-11-01-N-2-01-N-3` (released-set branch non-exclusivity).
