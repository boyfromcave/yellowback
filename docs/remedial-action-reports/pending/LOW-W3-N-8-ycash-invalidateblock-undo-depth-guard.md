# LOW — W3-N-8 — `invalidateblock` deeper than `UNDO_KEEP` (4,096) aborts the node and a plain restart cannot recover: refuse it in the RPC

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W3-N-8-invalidateblock-depth` off `upgrade/vault` in each: `src/rpc/blockchain.cpp` (`invalidateblock`), a helper in `src/vault/node.{h,cpp}` (`MaxSafeDisconnectHeight`) and `src/yellowback/index.{h,cpp}` (its equivalent), `doc/vault-rpc.md` ("Node behaviour behind the RPCs", `:572+`), `src/vault/db.h:56-70` comment, `qa/rpc-tests/vault_undo_prune.py`. RPC-level only — `src/main.cpp` (`InvalidateBlock`, `DisconnectBlock`) is not touched.
**Audit source.** Wave 3: `docs/audits/quantum-vault-ecosystem-wave3/07-node-rpc-mempool-durability-ci.md` W3-N-8 (lines 205-218); `docs/audits/quantum-vault-ecosystem-wave3/verification/07-verification.md` W3-N-8 (lines 183-190, "CONFIRMED, Low … Known and documented, but unguarded on an operator RPC: the depth guard is the fix"); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row W3-N-5..9. Wave 4: `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md` §1.5 row W3-N-8 (line 119, "STILL OPEN", Δ-free).
**Status:** pending — re-verified at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): open on both lines; `src/rpc/blockchain.cpp`, `src/vault/db.*`, `src/yellowback/index.*` and `src/main.cpp` unchanged since wave 3 (the refee-utxo delta touched only `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py`), so every source citation below stands; the doc section moved to `:572+`.

## 1. Finding

Both databases prune undo records 4,096 blocks back: the vault DB (`ycash-dd/src/vault/db.h:56-70`, `UNDO_KEEP = 4096`; after connecting H the undo of H−4095..H is kept) and the Yellowback index (`src/yellowback/index.h:71`). `DisconnectBlock` calls `g_vaultdb->DisconnectBlock` for every vault-active block except the activation block, which wipes (`src/main.cpp:3041-3053`); a missing undo record makes it fail (`src/vault/db.cpp`, `DisconnectBlock` returns false) → `AbortNode("Failed to disconnect the block from the vault database")` (`:3048-3051`); the index does the same (`:3037-3040`; `index.cpp:447-470`). `invalidateblock` (`src/rpc/blockchain.cpp:1444-1475`) has no depth check: one mistyped hash 5,000 blocks below the tip of a vault-active chain stops the node, and — as `db.h:63-66` records, regtest-verified — a plain restart stops again in `PruneBlockIndexCandidates`; only `-reindex` (a full rebuild that also forgets the invalidation) recovers. The behaviour is documented in a source comment, not guarded in the operator-facing RPC. Same on `ycash6` (`src/rpc/blockchain.cpp:2134`, same `db.h`/`index.h` constants). Live reorgs are bounded far below (`MAX_REORG_LENGTH = COINBASE_MATURITY − 1 = 99`, `src/main.h:66`), so only the RPC reaches the hazard.

## 2. Root cause

- `src/rpc/blockchain.cpp:1444-1475` — `InvalidateBlock` is called for any known block.
- `src/vault/db.h:56-70`, `src/yellowback/index.h:71` — undo retention is finite by design (07/F-7), and the consequence of exceeding it is an abort.

## 3. Fix options considered

1. **Refuse in the RPC (recommended).** Compute the lowest height whose undo is still kept in each database and refuse an `invalidateblock` that would disconnect a vault-active (or index-active) block below it, with a message pointing to `-reindex`. Local, non-consensus, no new failure mode.
2. **`force=true` override** (auditor). Pointless: forcing still aborts the node and the way out (`-reindex`) forgets the invalidation. Rejected.
3. **Mark the databases for wipe-and-replay instead of aborting on a missing undo** (auditor's second half). Changes `DisconnectBlock`'s failure semantics in a gated file and interacts with the restart loop in `PruneBlockIndexCandidates`; larger than the hazard warrants. Not now; noted for the 07/F-8 durability backlog.

## 4. Recommended fix

1. **Helpers.** `int vault::LowestUndoHeight(const CBlockIndex* tip, const Consensus::Params&)` = `max(activation + 1, tip->nHeight − UNDO_KEEP + 1)` when Vault is active at the tip, else "no limit" (the activation block itself wipes and needs no undo; below activation the vault DB is empty). `yellowback::LowestUndoHeight(...)` likewise from the index's start height and its `UNDO_KEEP` (only when the index is enabled).
2. **`invalidateblock` (both lines).** Under `cs_main`, if `chainActive.Contains(pblockindex)` and `pblockindex->nHeight < min(vault::LowestUndoHeight(...), yellowback::LowestUndoHeight(...))` (each only when applicable) → `throw JSONRPCError(RPC_MISC_ERROR, strprintf("invalidateblock: block %s at height %d is more than %d blocks below the tip; the vault database (and the Yellowback index) keep undo records for the last %d blocks only, so disconnecting it would stop the node. Restart with -reindex to rebuild from the block files instead.", ...))`. A block not on the active chain is unaffected (nothing is disconnected).
3. **Docs.** `src/vault/db.h:63-66`: "the `invalidateblock` RPC refuses such a block (W3-N-8)". `doc/vault-rpc.md` node-behaviour section: the 4,096-block bound and the refusal. Release notes.

## 5. Tests

- **Functional `qa/rpc-tests/vault_undo_prune.py` (both lines; it already mines to `ACTIVATION + UNDO_KEEP + 3`, `:86`, with SIGKILL/replay cases) — would have caught it:** on a chain with Vault active and tip − activation > `UNDO_KEEP` (the script already mines enough on regtest, or lower the window via its existing test hook if one exists), `invalidateblock` of a block at `tip − UNDO_KEEP − 1` → the new error, the node still running, `getbestblockhash` unchanged; `invalidateblock` at `tip − 10` → works, `reconsiderblock` restores. A block below the activation height on a short chain (tip − activation < `UNDO_KEEP`) → allowed (walks through the activation wipe).
- The chain length is already paid for by the script; add the cases after its prune assertions, before the SIGKILL section.

## 6. Acceptance criteria

- `invalidateblock` refuses, without side effects, any active-chain block whose disconnection would need an undo record either database has pruned; shallower invalidations behave as before; both lines.

## 7. Risks and side effects

- None for consensus. An operator who truly needs to invalidate a deep block must `-reindex` — the only path that ever worked.

## 8. Effort estimate and dependencies

- 0.25 day code, 0.5 day test (block count), 0.25 day ycash6 + docs. Independent. Context: the done `LOW-07-F-7-F-8` (undo retention).
