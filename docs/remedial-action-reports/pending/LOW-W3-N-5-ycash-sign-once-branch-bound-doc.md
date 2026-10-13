# LOW — W3-N-5 — The sign-once record binds the current branch ID's sighash: document it; re-signing under a new branch is self-slashing and must NOT be done (documentation only)

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W3-N-5-branch-bound-doc` off `upgrade/vault` in each: `doc/vault-rpc.md` (sign-once section of `set_signunlock`, `:320-366`; `set_signcancel` `:392-398`), `doc/yellowback-attestor.md`; workspace: `docs/plans/yellowback-upgrade-plan.md` (§15.8 RPCs and the "next upgrade" items of §12 Sequencing / §8 Activation plumbing), `docs/mapping.md` §22 (one row). Cross-repo: the matching `hawkeye/docs/operations.md` sentence is owned by `HIGH-W4-B-2-hawkeye-departed-signer-unlock-pins-vault.md` §4.8 (runbook §11), not by a separate PR from this report. **No code change.** Explicitly out of scope: any change to `SignSetInPlace`, the record format, or `ACT_SET_EQUIVOCATION`.
**Audit source.** Wave 3: `docs/audits/quantum-vault-ecosystem-wave3/07-node-rpc-mempool-durability-ci.md` W3-N-5 (lines 165-177); `docs/audits/quantum-vault-ecosystem-wave3/verification/07-verification.md` W3-N-5 (lines 138-156, "CONFIRMED, Low — the proposed fix must not be applied … the auditor's fix would get the member slashed"); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row W3-N-5..9 ("**re-signing under the new branch would be self-slashing, so the first-wave fix must not be applied**") and remediation priority 3 ("Do **not** apply the W3-N-5 re-sign suggestion"). Wave 4: `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md` §1.5 row W3-N-5 (line 116, "STILL OPEN … Its 'do not re-sign' warning still applies").
**Status:** pending — re-verified at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): open on both lines; `SetSighash` still uses `NextBranchId()` and the equivocation rule is unchanged.

## 1. Finding

The set-signature digest is ZIP-243 under the **next block's** consensus branch ID: `SetSighash` (`ycash-dd/src/rpc/vault.cpp:803-808`) uses `NextBranchId()` = `CurrentEpochBranchId(tip + 1)` (`:63`), as consensus does (`OP_CHECKSETSIG` passes `consensusBranchId`, `src/vault/checker.cpp:28-43`). The sign-once record stores that sighash (`WriteVaultSetSig`, `:1692`) and refuses any other for the same `(setId, prevout)` (`:1670-1675`). After any future network upgrade, the same transaction has a different sighash. So a set-signed build that was signed before the activation height and not confirmed by then is dead: consensus rejects the old signatures (the previous-epoch route in `ContextualCheckInputs`, `src/main.cpp:2725-2733`, and `VaultTemplateFailsOnSetState`, `:1663-1670`, only *diagnose* `old-consensus-branch-id` at DoS 10 — they do not accept), and every member that signed it is refused (`set-sign-once`) for the new-branch sighash of the same build, with no override, until the vault's `ownerHeight` (unlock) or the intent's `delay` (a cancel lapses into the recipient's RELEASE). (An *unsigned* remembered build has no record and signs normally under the new branch — the auditor's "every unsigned remembered build" was corrected by the verifier.) Vault is the last scheduled upgrade, so this is latent — it is the state the next upgrade's author will not expect.

**The first-wave/auditor remedy is unsafe and must not be implemented.** "Accept when the recorded sighash equals the build's sighash under the previous epoch's branch ID, rewriting the record" issues a **second signature over a different sighash for the same `(setId, prevout)`** — exactly what `ACT_SET_EQUIVOCATION` slashes (`src/vault/state.cpp:849-860`: the only exemption is `roleA == roleB && sighashA == sighashB`; the rule has no branch-ID awareness). Anyone holding the pre-upgrade signature (the builder, any member, anyone who saw the never-confirmed transaction) submits `set_equivocation` with both → the member is EJECTED and its bond frozen. Same on `ycash6` (`src/rpc/vault.cpp:63`, `SetSighash` `:820-825`, refusal and record `:1691-1713`).

## 2. Root cause

- `src/rpc/vault.cpp:803-808` — the digest includes the branch ID by construction (ZIP-243 personalization); the record is a sighash, so it is branch-bound.
- `src/vault/state.cpp:845-870` — equivocation is two signatures over different sighashes, whatever made them differ.
- `doc/vault-rpc.md:331-335` — says "across restarts … There is no override", nothing about upgrades.

## 3. Fix options considered

1. **Record rewrite / previous-epoch acceptance (auditor's proposal). Rejected — self-slashing** (above).
2. **Record `(role, txid-without-fee-inputs digest)` instead of the sighash.** Lets the wallet *recognise* the same build across branches, but signing it again under the new branch still produces a second, different sighash on chain → still slashable. Rejected for the same reason.
3. **A consensus rule in the next upgrade** (e.g. the equivocation act exempts two signatures whose transactions are identical modulo the branch ID, or the set message binds a branch-independent digest). The only real fix; it belongs to whoever designs the next upgrade, with vectors. Recorded as a requirement, not implemented here.
4. **Documentation and an operational rule (recommended now).** Drain or abandon set-signed builds before any future activation; never re-sign; know the recovery paths.

## 4. Recommended fix

1. **`doc/vault-rpc.md` (both lines), sign-once paragraph after `:335`** — add, verbatim in substance:
   > **Network upgrades.** The sighash a member signs includes the consensus branch ID of the next block. A set-signed unlock or cancel that is not confirmed before a later network upgrade activates can never confirm, and every member that signed it will be refused (`set-sign-once`) if asked to sign the same transaction under the new branch. **This refusal is correct. Do not work around it** — not with `rebuild=true`, not with another wallet or a restored copy of the key, not with `acknowledgerestore`: a second signature over a different sighash for the same outpoint is a provable equivocation even when the transaction is otherwise identical, and anyone holding the first signature can have the member ejected and its bond frozen (`set_equivocation`). Before a scheduled activation height: confirm or abandon every set-signed spend; do not start new set signatures within the last blocks before activation. After it: an unlock signed under the old branch waits for the vault's `ownerHeight` (or is completed by members who did not sign it); a cancel signed under the old branch lapses — the intent releases to its recipient after `delay`.
2. **`set_signunlock` / `set_signcancel` sections** — one line: "the sighash is bound to the next block's branch ID; see *Network upgrades* above".
3. **`doc/yellowback-attestor.md`** — the same rule in the operator's checklist for an upgrade window; **`hawkeye/docs/operations.md`**: owned by `HIGH-W4-B-2-…` §4.8 (its §11 network-upgrade step), which carries this rule — Hawkeye never re-signs a stored unlock/cancel across an activation (its sign-once ledger keys on the node's bytes and must keep refusing); the old-branch row dies `C_Y` past the activation and its vault is rolled instead. Do not write a second Hawkeye runbook paragraph here.
4. **Plan** — `yellowback-upgrade-plan.md` §15.8 (wallet-signing RPCs): the record is branch-bound; §12/§8: add to the checklist for **any future network upgrade after Vault**: "set-signed builds pending at activation are dead and their signers locked out until `ownerHeight`/`delay`; either drain them before activation or include a consensus rule that does not count the same transaction under two consecutive branch IDs as equivocation (W3-N-5); never a wallet-side re-sign". `docs/mapping.md` §22 row: "sign-once record is branch-bound; why a wallet re-sign is self-slashing".
5. **Optional, not part of this report:** a clearer error text when the recorded sighash equals the build's sighash under `PrevEpochBranchId` ("signed under the previous branch; it cannot confirm and must not be re-signed") — diagnostic only, never a signing path. If someone implements it later, it must be reviewed against this report.

## 5. Tests

- None required (documentation). If the optional diagnostic is ever added: a regtest case in `vault_upgrade.py` that activates a second upgrade (`-nuparams` for a test-only branch) between two `set_signunlock` calls on the same build and asserts the refusal text and that `set_listsigned` is unchanged.
- What would have caught it: a reviewer reading the sign-once record against the equivocation rule; there is no future upgrade on any network to test against today.

## 6. Acceptance criteria

- `doc/vault-rpc.md` on both lines states that the record is branch-bound, that re-signing under a new branch is self-slashing and must not be done, and what to do before and after an activation.
- The plan carries the next-upgrade requirement; `docs/mapping.md` §22 has the row; Hawkeye's operations doc has the matching rule (landed by HIGH-W4-B-2 §4.8).
- No code that re-signs or rewrites a record is added on either line.

## 7. Risks and side effects

- None from the docs. The risk is the opposite one: an implementer applying the auditor's original fix. The PR description should quote §3 option 1.

## 8. Effort estimate and dependencies

- 0.25 day (docs, both lines, plan, mapping), plus the Hawkeye doc PR.
- Dependencies: coordinate with `MEDIUM-W3-N-3-ycash-set-sign-validate-before-record.md` (same doc section). Builds on the done `MEDIUM-07-F-5` and `MEDIUM-01-V-2`.
