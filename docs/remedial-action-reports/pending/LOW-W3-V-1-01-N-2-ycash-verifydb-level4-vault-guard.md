# LOW — W3-V-1, 01/N-2 — `-checklevel=4` fails spuriously on any vault-active block with a set-signed or owner-released spend: stop level-4 reconnection at the Vault activation height

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W3-V-1-verifydb-level4` off `upgrade/vault` in each: `src/main.cpp` (`CVerifyDB::VerifyDB`, level-4 loop only — a gated file, normal review-gate leg; no rule changes), `doc/vault-rpc.md` ("Node behaviour behind the RPCs"), `qa/rpc-tests/vault_undo_prune.py` (or a new `vault_verifydb.py` registered in `YELLOWBACK_SCRIPTS`). Spec: `docs/plans/yellowback-upgrade-plan.md` §15.6 / U-17 note on VerifyDB; `docs/mapping.md` §22.
**Audit source.** Wave 3: `docs/audits/quantum-vault-ecosystem-wave3/01-vault-primitive-consensus.md` W3-V-1 (lines 42-52); `docs/audits/quantum-vault-ecosystem-wave3/verification/01-verification.md` W3-V-1 verdict (line 13, "PARTIALLY … the start-up VerifyDB runs **before** `vault::g_vaultdb` exists, so level 4 reconnects with a **null** snapshot") and §5 (lines 114-127), N-2 (line 168); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row W3-V-1 / 01/N-2, remediation priority 3 ("guard level-4 VerifyDB (01/N-2)"). Wave 4: `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md` §1.1 row W3-V-1 / 01/N-2 (line 62, "STILL OPEN", Δ-free).
**Status:** pending — re-verified at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): open on both lines; `src/main.cpp`, `src/init.cpp`, `src/vault/` unchanged since wave 3, so every source citation below stands.

## 1. Finding

`ConnectBlock` builds the script checker's set snapshot from the live vault database whenever Vault is active at the block's height — `vaultSnapshot = fVaultActive ? vault::TipSnapshot() : nullptr` (`ycash-dd/src/main.cpp:3204`) — and runs the state rules only when the database is at the block's parent: `fVaultRules = fVaultActive && g_vaultdb && !(!fJustCheck && chainActive.Contains(pindex))` (`:3198`), deliberately false for a block already on `chainActive`. `CVerifyDB::VerifyDB` at `nCheckLevel >= 4` reconnects such blocks (`:5473-5487`). Two failure mechanisms:

- **Start-up (01/N-2, the common case).** `VerifyDB` runs inside `LoadBlockIndex` (`src/init.cpp:1940`), **before** `vault::g_vaultdb` is created (`:1988`); `TipSnapshot()` returns `nullptr` (`src/vault/node.cpp:30-34`), so the reconnect passes a null snapshot, and `SetSigChecker` fails closed: `CheckSetSigs` → false (`src/vault/checker.cpp:31`), `IsSetReleased` → false (`:47`). Every block within `-checkblocks` (default 288) that contains a V UNLOCK, an I CANCEL or an OWNER-RELEASED spend fails `VerifyDB(): *** found unconnectable block` → "Corrupted block database detected" → the node will not start with `-checklevel=4`, membership changes or not.
- **`verifychain` RPC (W3-V-1 as reported).** The DB exists, so the reconnect uses the **tip's** set state with the historical spend height: a past set spend whose signers have since been removed/ejected/withdrawn, or an owner-released spend of a set no longer released, fails.

No consensus effect (VerifyDB works on a throwaway `CCoinsViewCache` and commits nothing); `-checklevel` defaults to 3, and levels ≤ 3 are unaffected (level 3 disconnects with `updateIndices = false`, `:5454`). Operational: an operator who verifies with level 4 gets a false "corrupted database". Same on `ycash6` (`src/main.cpp:3680`, `:3686`; level 4 `:7139-7150`; `src/init.cpp:2166` VerifyDB vs `:2256` `g_vaultdb`).

## 2. Root cause

- `src/main.cpp:5473-5487` — level 4 reconnects every block from `pindexState` to the tip with the full script flags, including `SCRIPT_VERIFY_VAULT`, but the set state at each block's parent is not available to it (the vault DB holds only the tip state, with undo records for rewinding — and none at all during start-up VerifyDB).

## 3. Fix options considered

1. **Stop level-4 reconnection at the first vault-active block and log why (recommended; the verifier's preference).** One condition in the loop; fixes both mechanisms; level 4 keeps checking every pre-activation block; levels 1-3 still cover vault-active blocks (block checks, undo validity, disconnect consistency).
2. **Rewind a `VaultState` overlay to each block's parent using the stored undo records** (the report's option (a)). Meaningful level-4 checks, but only works when the DB exists (not at start-up, which is the common case) unless the DB is opened earlier; adds a second state-rewinding path next to `Reconcile` in a gated file. Rejected for now.
3. **Open the vault DB before VerifyDB.** `Reconcile` needs the block index and runs before `ActivateBestChain`; moving the DB creation into the `LoadBlockIndex` retry loop entangles `-reindex` handling. Rejected.
4. **Skip only the set opcodes during VerifyDB** (a flag to the checker). Touches the script path; more surface than (1) for the same coverage. Rejected.

## 4. Recommended fix

1. **`CVerifyDB::VerifyDB` level-4 loop (`src/main.cpp:5473-5487`; ycash6 `:7139-7150`):** after `pindex = chainActive.Next(pindex)`, `if (chainparams.GetConsensus().NetworkUpgradeActive(pindex->nHeight, Consensus::UPGRADE_VAULT)) { LogPrintf("VerifyDB(): check level 4 stops at height %d: blocks with UPGRADE_VAULT active are reconnected only with the set state at their parent, which VerifyDB does not have (W3-V-1); levels 1-3 checked them\n", pindex->nHeight); break; }`. Heights are monotone along the active chain, so every later block is vault-active too. The coins view is throwaway, so stopping early leaves nothing inconsistent.
2. **`ConnectBlock` comment (`:3194-3197`)**: update "VerifyDB's reconnection … skips the vault rules" to say VerifyDB no longer reconnects vault-active blocks. No code change in `ConnectBlock`.
3. **Docs.** `doc/vault-rpc.md` node-behaviour section and `-checklevel` help text (`src/init.cpp:386`, both lines): "level 4 reconnects blocks below the Vault activation height only". Plan §15.6 / U-17 note; `docs/mapping.md` §22 row (why VerifyDB cannot re-run set-state-dependent scripts).

## 5. Tests

- **Functional (both lines) — the test that would have caught it** (`vault_undo_prune.py` already has restart machinery; or a new short `vault_verifydb.py`): build a chain with an UNLOCK (set-signed), a CANCEL and an OWNER-RELEASED spend after activation, then a membership change (remove one signer); `restart_node` with `-checklevel=4 -checkblocks=0` → the node starts (before the fix: "Corrupted block database detected"); `debug.log` contains the new "check level 4 stops at height" line; `verifychain 4 0` → `true`; `verifychain 3 0` → `true`. The verifier's note applies: a test that runs `verifychain` without a restart would pass for the wrong reason on the start-up mechanism — it must restart.
- **Pre-activation coverage:** on a chain where Vault activates late, `-checklevel=4 -checkblocks=<covering pre-activation blocks>` still reconnects those (log shows the stop height above them).

## 6. Acceptance criteria

- A node with `-checklevel=4` starts on both lines after any set-signed or owner-released spends and membership changes; `verifychain 4` returns true; level 4 still reconnects pre-activation blocks; the stop is logged.

## 7. Risks and side effects

- Level-4 coverage of vault-active blocks is reduced to levels 1-3 — it was not meaningful before (it could only fail falsely). No consensus or chain-state effect; review-gate leg because `main.cpp` is gated.

## 8. Effort estimate and dependencies

- 0.25 day code + docs, 0.5 day functional test, both lines. Independent.
