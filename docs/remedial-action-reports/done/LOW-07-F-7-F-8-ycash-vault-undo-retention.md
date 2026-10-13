# LOW — 07/F-7, 07/F-8 — Prune the vault DB's per-block undo records (and document the Yellowback index's 4,096-block recovery bound)

**Repos / branches to change:** `ycash-dd` (`src/vault/db.{h,cpp}`, `src/vault/node.cpp`, `src/main.cpp` call site, tests) and `ycash6` (same files, 6.20.0 line numbers), branch `fix/07-F-7-vault-undo-prune` off `upgrade/vault` in each; `doc/yellowback.md` / `doc/vault-rpc.md` for F-8.
**Audit source:** `07-node-rpc-mempool-durability-ci.md` §F-7 (`:195-202`), §F-8 (`:204-210`); `verification/07-verification.md` rows F-7 (Low), F-8 (Info) (`:17-18`), detail (`:98-101`).
**Status:** done — completed 2026-10-13T11:21Z (merged locally on `upgrade/vault`; not yet pushed)

## 1. Finding

**F-7.** `VaultDB::ConnectBlock` writes an undo record `'u'‖blockHash → BlockUndo` for every block after activation, including blocks that changed nothing (~40 B each: 33-byte key, empty CompactSize, overhead). Only `DisconnectBlock` ever erases one. Growth is unbounded — ~20 MB/year at Ycash's block rate — and useless beyond a reorg horizon: `Reconcile`'s off-chain walk disconnects by these records only as far as it needs to reach a block on the active chain, and already falls back to wipe-and-replay when it cannot disconnect. The Yellowback index prunes its own undo at `UNDO_KEEP = 4,096` blocks; the vault DB does not. Harmless for years; a durability-hygiene item.

**F-8 (Info).** The Yellowback index's "index ahead of the chainstate after a crash" recovery walks back with `UndoOne` while its tip is off the active chain and its undo is kept 4,096 blocks; a chainstate more than 4,096 blocks stale at crash time (hourly periodic flush; a large `-dbcache` sync) makes `UndoOne` fail, and the index wipes and rebuilds from `startHeight`. Correct outcome, long downtime; the same bound would apply to the vault DB once F-7 is fixed, and `Reconcile` handles it the same way. Documentation only.

## 2. Root cause

ycash-dd `055d9c2`:
- `src/vault/db.cpp:139` `batch.Write(RawKey(UndoKey(hash)), undoValue);` in `ConnectBlock` (every block); `:172` `batch.Erase(RawKey(UndoKey(hash)));` in `DisconnectBlock` (the only erase). `VaultDB` knows no heights or hashes other than the tip (`EncodeTip`), so it cannot name the record to prune by itself.
- `src/vault/node.cpp:304-318` `Reconcile` off-chain loop disconnects by undo; `:306-309` wipes and replays from activation when an undo is missing or the disconnect fails (the fallback pruning relies on).
- `src/yellowback/index.cpp:422-426` prunes `keys::Undo(snap->blockHash)` at `h − UNDO_KEEP` (`index.h:71`, 4,096); `:264-276` the crash walk-back with wipe on failure (F-8).
- `src/main.cpp:3496-3498` the `ConnectBlock` call site of `vault::g_vaultdb->ConnectBlock(...)` (has `chainActive`/`pindex` in hand).
- ycash6 `e866c45`: `src/vault/db.cpp:139`, `:172` (same lines); the `ConnectBlock` hook at `src/main.cpp:4341-4343`.

## 3. Fix options considered

1. **Prune in the same batch** that connects a block: erase the undo of the block `UNDO_KEEP` below, hash supplied by the caller (`chainActive[height − UNDO_KEEP]`). One extra `Erase` per block; no format change; `Reconcile`'s existing wipe path covers a deeper offline reorg. **Recommended.** Mirrors `index.cpp:422-426`.
2. Keep a height→hash side index in the vault DB so the DB prunes by itself: adds a key family and a `VAULT_DB_VERSION` bump. Rejected (more state for the same effect).
3. Periodic sweep (iterate `'u'` prefix at start-up): O(n) per start, and the prefix iteration cannot order by height without (2). Rejected.
4. Do nothing and document. Acceptable for years; but the fix is ~20 lines and the asymmetry with the index invites the wrong assumption in a future `Reconcile` change. Fix recommended.

## 4. Recommended fix

Both lines:

1. `src/vault/db.h`: add `static const int UNDO_KEEP = 4096; // undo records older than this are pruned on connect; a deeper offline reorg is a wipe + replay in Reconcile (as the Yellowback index, index.h UNDO_KEEP)`; change `ConnectBlock`'s signature to take `const std::optional<uint256>& pruneUndoOf` (the hash of the block at `height − UNDO_KEEP`, `nullopt` when below activation + UNDO_KEEP).
2. `src/vault/db.cpp` `ConnectBlock` (`:139`): after writing the new undo, `if (pruneUndoOf) batch.Erase(RawKey(UndoKey(*pruneUndoOf)));` — in the same `CDBBatch`, so atomicity is unchanged; also drop the cache entry if undo values are ever cached (they are read through `ReadUndo`, which does not use the cache — confirm, `:112-120`).
3. `src/main.cpp` call site (dd `:3496-3498`, y6 `:4341-4343`): compute `pruneUndoOf = (pindex->nHeight − UNDO_KEEP ≥ activationHeight) ? chainActive[pindex->nHeight − UNDO_KEEP]->GetBlockHash() : nullopt` (the parent chain is the active chain at this point, `AtParentOf` was checked at `:3119` / `:3587`).
4. `src/vault/node.cpp` `Reconcile` (`:304-318`): no logic change; add a comment that a missing undo past `UNDO_KEEP` is expected and takes the wipe path at `:306-309`. Replay also calls `ConnectBlock` (`:325-353`) — pass the same prune hash there (it walks the active chain, so `chainActive[]` is valid).
5. No `VAULT_DB_VERSION` bump: the record set only shrinks; old nodes' surplus records are harmless and are never pruned retroactively (document in `db.h`). If the owner wants a clean DB, bumping the version triggers the full replay (which is exactly what 01/V-1 warns about — do **not** bump for this).
6. **F-8 (docs only):** `doc/yellowback.md` "Operations" (or `doc/vault-rpc.md` durability section): "After a crash, the Yellowback index and the vault DB walk back their own undo records for at most 4,096 blocks; a chainstate older than that at the crash is a full rebuild from the activation height (minutes to hours). Flush more often (`-dbcache` smaller) on a node where downtime matters."

Consensus footprint: none (node-local database retention).

## 5. Tests

- `src/test/vault_state_tests.cpp` `db_connect_disconnect` (LevelDB-backed): connect `UNDO_KEEP + 2` empty blocks with the prune hash supplied as the caller would; assert `ReadUndo(block 1)` is false and `ReadUndo(tip)` true; `DisconnectBlock` of the tip succeeds; attempting to disconnect below the horizon (by hand-driving `DisconnectBlock` past `UNDO_KEEP` blocks) fails on the missing undo — the exact condition `Reconcile` turns into a wipe. Add a `Reconcile`-level unit case if the test fixture can host one (it drives `VaultDB` directly; `Reconcile` needs `chainActive`, so cover it functionally).
- Functional (nightly on both lines, `vault_primitive.py` section J or a new `vault_undo_prune.py`): regtest with `UNDO_KEEP` cannot be lowered without a flag, so mine 4,100 blocks past activation (~1 minute on regtest), SIGKILL the node, start it, assert a clean start (`vault_getinfo` tip = chain tip) and that `vaults/` contains no undo record for the activation block (a `vault_debugundo` RPC is not worth adding — check the LevelDB key count via a `debug` log line "pruned undo of %s at %d", asserted in the log).

## 6. Acceptance criteria

- After the change, a node that connected N > 4,096 blocks past activation holds at most 4,097 undo records; disconnects within the horizon work; `Reconcile` on a deeper off-chain tip wipes and replays (existing behaviour, now reachable).
- `VAULT_DB_VERSION` unchanged; `db.h` documents `UNDO_KEEP` and the no-retroactive-prune note.
- F-8 operations paragraph present in the node docs on both lines.

## 7. Risks and side effects

- A reorg deeper than 4,096 blocks after activation becomes a wipe + replay from activation instead of an undo walk — the same path a `VAULT_DB_VERSION` bump already takes, and a reorg that deep is a network event, not an operational one. **This makes 01/V-1 (report R4) slightly more reachable** (replay is the path V-1 breaks); land R4 first or together.
- Pruned nodes: replay after a wipe needs the blocks — 01/N-1 (report R4) refuses `-prune` with the vault upgrade; same dependency.

## 8. Effort estimate and dependencies

~2 hours per line plus the functional case. **Dependencies:** R4 (01/V-1 + 01/N-1: `CoinsFromUndo` height-0 fallback and the `-prune` refusal) should land first, since this change routes deep reorgs through the replay path R4 repairs.

## Completion record

- **Completed:** 2026-10-13T11:21Z
- **Merged:** with fix/vault-replay (ycash-dd 0810b8bd5, ycash6 f40cc2c1e): e8a944731 / 1c33da7f7 (UNDO_KEEP 4,096, erased in the block's batch), d5407960b (exact recovery bound: a >4,096-block invalidateblock needs -reindex). New vault_undo_prune.py passes on both lines.
- **Verification:** Integration run 2026-10-13 (both node lines built; full test_bitcoin dd 872/872, ycash6 923/923; qa/yellowback-audit.sh dd --mode upgrade rc 0 (18 PASS), ycash6 --report-only rc 0; functional suites pass; vault_vectors / golden / pq vectors byte-identical across lines). Logs: wt/scratch/integ/.
