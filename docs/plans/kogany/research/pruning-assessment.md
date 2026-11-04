# Pruning on the three node lines: assessment

Research note, 2026-11-02. Read-only survey. It changes no code and no decision.

**Question (the Yellowback lead architect).** Zakura publishes a pruned snapshot and a full archive with a large
size difference. What pruning does Zakura do? What do ycashd 4.5.0, ycash6 on `upgrade/vault` and kogany do or
forbid? Why can ycashd not simply prune everything *below* the vault activation height `H_V`? What can and should
Ycash do as the chain grows?

**Short answer.**

- **Zakura prunes one thing**: the raw transaction bytes (`tx_by_loc`) of finalized blocks older than a
  retention window (floor 10,000 blocks on Mainnet/Testnet). Everything consensus needs stays: headers, hash
  indexes, the UTXO set, nullifiers, trees, history tree and value pools. On the Ycash mainnet cache that one
  column family is **18.4 of 25.6 GB (72 %)**.
- **ycashd 4.5.0** has Bitcoin 0.11-style block-file pruning (a size target over whole `blk`/`rev` file pairs,
  288-block floor). **Both C++ vault lines refuse `-prune` outright** wherever `UPGRADE_VAULT` has a height
  (audit 01/N-1), because the vault set-state database and the YED index rebuild themselves by replaying
  blocks and undo data from disk.
- **They replay only from `H_V`.** Since rule S-0 (the same remediation), no block below `H_V` is read by any
  vault or YED rebuild. So the refusal is wider than its reason. A **height floor** ("never prune a file that
  holds a block at or above `H_V`") keeps every block the rebuilds read and still drops everything before the
  upgrade. On mainnet today, with `H_V` in the future, that is **nearly all 25.9 GB of block and undo files**.
- **kogany needs no floor at `H_V`.** Its vault and YED transitions are computed from the block in hand, the
  UTXO set and the retained hash index, and it never rebuilds them from stored blocks (K-14: resync instead).
  Zakura's own retention window (≥ 10,000 > 1,000 reorg window, > 4,096 YED undo depth) is enough for
  consensus. A few read RPCs must say "pruned".
- **Growth is small.** Post-fork Ycash blocks average about 1.1 KB (mostly the header and the coinbase), so
  the archive grows by 0.7–0.9 GB a year at today's activity. Pruning is mainly about dropping the 19.4 GB of
  pre-fork Zcash history (heights 0–569,999). It is not about keeping up with growth, unless usage grows by
  orders of magnitude (§5).

**Pins read:**

| Tree | Branch | Commit |
|---|---|---|
| `ref/ycash` | v4.5.0 | `624c12814` |
| `ycash6` | `upgrade/vault` (= `vaults/kogany-compat`) | `65cb4ae0f` |
| `ycash-dd` | `upgrade/vault` | `781946771` |
| `ref/zakura` = kogany `kogany-legacy` | | `2b062412c5` |
| `kogany` | `origin/vaults/kogany-compat` | `eaac2b78d` |
| `lightwalletd-dd` | `upgrade/vault` | `a1d141e` |
| `ycash-infra` | `origin/kc/mainnet-snapshots` (the snapshotter) | `a1182c0` |

**Measured** (2026-11-02, read-only: `du`, a Python scan of the `blk*.dat` files and SST property blocks
opened read-only, and 17 RPC reads against the running ycash6 mainnet node; kogany was stopped):

- ycash6 mainnet datadir `wt/.data/ycash-mainnet`, tip 3,087,387, no `-txindex`, no `-insightexplorer`,
  `disablewallet=1`;
- kogany mainnet cache `wt/.data/kogany-mainnet/state`, finalized tip 3,086,340 plus 1,001 non-finalized blocks
  (tip 3,087,341), state format 30.2.0.

---

## 1. Zakura's Pruned mode

### 1.1 What it deletes and what it keeps

`StorageMode::{Archive, Pruned(PruningConfig { tx_retention })}`
(`ref/zakura/crates/zakura-state/src/config.rs:343-362`, `:446-465`). Archive is the default
(`zakurad/src/commands/default_config.toml:149`).

- **Deleted:** rows of the `tx_by_loc` column family (raw transaction bytes, keyed by height and index) for
  heights `[from, until)` below the retention boundary. Each range is deleted with one range tombstone
  (`zakura_db/block.rs:1447-1469`, `prepare_prune_batch`). A `pruning_metadata` marker records the lowest
  retained height, which makes the database permanently pruned. Afterwards the range is compacted to reclaim
  space (`block.rs:1092-1103`). Genesis is never pruned.
- **Kept** (`config.rs:169-187`): headers (`block_header_by_height`), `hash_by_height`/`height_by_hash`, the
  transaction location indexes `tx_loc_by_hash`/`hash_by_tx_loc` (needed to locate the creating transaction of
  any old UTXO), `utxo_by_out_loc`, nullifiers, anchors, note commitment trees, `history_tree`,
  `tip_chain_value_pool` and `block_info`. The full list is `service/finalized_state.rs:163-225`.
- **With checkpoint sync** (the default, `config.rs:224-226`): a pruned database also **stops maintaining the
  transparent address indexes**: `balance_by_transparent_addr`, `tx_loc_by_transparent_addr_loc`,
  `utxo_loc_by_transparent_addr_loc` and the spender index. Rows that already exist stay on disk but are never
  served as complete results, and this is recorded permanently (`config.rs:181-186`). Checkpoint blocks below
  `max_checkpoint − retention` are written without raw transactions at all (`finalized_state.rs:544-594`,
  `retention_plan`).

### 1.2 The retention floor and how it relates to reorgs

- `MIN_PRUNING_RETENTION = 10_000` (`constants.rs:45`). Regtest uses `MAX_BLOCK_REORG_HEIGHT + 1` = 1,001
  instead (`constants.rs:75-80`). A smaller value is refused at start-up (`config.rs:306-319`).
  `MAX_BLOCK_REORG_HEIGHT = 1000` (`zakura-chain/src/parameters/constants.rs:30`).
- **The window is counted from the finalized tip** (`prune_height_range`, `block.rs:790`). The finalized tip
  trails the best tip by up to 1,000 blocks, so a node at defaults holds raw bytes for roughly the last 11,000
  blocks (about 9.5 days at 75 s).
- Reorgs inside the 1,000-block window never touch the finalized state. They are in-memory forks
  (kogany plan §1.5). The only finalized undo is the **offline `rollback`** tool, which re-reads each
  rolled-back block and the **creating transaction of every output it spent** (`zakura_db/rollback.rs:509-512`,
  `:874-890`). On a pruned database it therefore fails with `MissingBlock`/`MissingTransaction` once it reaches
  pruned data. kogany already refuses `rollback` past `H_V` (K-14, `rollback.rs:497`
  `refuse_rollback_past_vault` on `vaults/kogany-compat`).
- **The change is one-way.** A pruned database will not open in Archive mode (`finalized_state.rs:429-435`).
  Going back means a resync.
- The offline `zakurad prune-state --tx-retention N --confirm` command (`zakurad/src/commands/prune_state.rs`)
  prunes an existing archive cache in place. That is how a snapshotter can derive a pruned bundle from an
  archive one.

### 1.3 What it breaks

| Consumer | Effect under Pruned |
|---|---|
| `getrawtransaction` / `getblock` (verbosity ≥ 1) of a pruned height | no body (`contains_body_at_height`, `block.rs:131-139`); the RPC reports the block or transaction as unavailable. `getblockchaininfo.pruned`/`pruneheight` say so (`zakura-rpc/src/methods.rs:4764-4782`) |
| Transparent address RPCs (`getaddressbalance`, `getaddressutxos`, `getaddresstxids`) | incomplete once checkpoint-synced pruned (§1.1); **lightwalletd-dd uses all three** (`lightwalletd-dd/common/common.go`, `frontend/service.go`) |
| **P2P serving** | a pruned node advertises **no `NODE_NETWORK`** (`zakurad/src/commands/start.rs:298-304`; the exception is zcashd-compat mode, `docs/zcashd-compat.md:236-255`). It cannot bootstrap peers |
| lightwalletd-dd ingestion | ingests every block from Sapling activation (419,200) with `getblock` (`cmd/root.go:234-238`). A fresh lightwalletd, or one returning from an outage longer than the window, cannot catch up; `getrawtransaction` for a wallet's old transaction (`GetTransaction`) fails |
| chain-viz | its live views read recent blocks and are unaffected. Historical drill-down below the window fails |
| ycash-infra `yindex` (its own address index) | builds from `getblock` over the whole chain, so it needs an archive source |
| Offline `rollback` | effectively unusable (§1.2). Moot on kogany past `H_V` (K-14) |
| Historical treestates (`z_gettreestate` at old heights) | trees are kept, so it is served. The VCT absent band is a separate limitation (`docs/design/historical-treestate-serving.md`) |
| A zcashd-compat or `yewd` sidecar | can sync from a pruned front only while its own tip is inside the window (`docs/zcashd-compat.md:240-252`) |

### 1.4 The measured kogany mainnet cache, by column family

Measured by attributing every SST file to its column family (the `rocksdb.column.family.name` property).
Total SST 25.57 GB; the write-ahead log is empty; 1,708 SST files.

| Column family | GB | Share | Pruned? |
|---|---|---|---|
| `tx_by_loc` (raw transactions) | **18.38** | 71.9 % | **yes** (all but ~11,000 blocks) |
| `block_header_by_height` | 2.27 | 8.9 % | no |
| `tx_loc_by_transparent_addr_loc` | 1.34 | 5.3 % | frozen, not updated (checkpoint-synced pruned) |
| `utxo_by_out_loc` | 0.89 | 3.5 % | no |
| `tx_loc_by_hash` + `hash_by_tx_loc` | 0.82 | 3.2 % | no |
| `utxo_loc_by_transparent_addr_loc` + `balance_by_transparent_addr` | 0.63 | 2.5 % | frozen, not updated |
| `commitment_roots_by_height` | 0.27 | 1.1 % | no |
| `block_info`, `hash_by_height`, `height_by_hash` | 0.51 | 2.0 % | no |
| Sapling/Sprout trees, anchors, nullifiers | 0.46 | 1.8 % | no |
| everything else (history tree, value pool, Orchard/Ironwood empties, metadata) | < 0.01 | | no |
| non-finalized backup (1,001 block files) | 0.004 | | n/a |

Raw transactions are 18.4 GB and block files on the C++ line are 23.2 GB. The difference is mostly headers,
which Zakura keeps in their own column family (2.3 GB). No vault or YED column family appears in this cache:
the binary that wrote it predates W4-c/W5-e, and no Ycash network schedules Vault on mainnet.

**The pruned kogany equivalent today:** 25.57 − 18.38 + ~0.01 (the retained window) ≈ **7.2 GB** when an
existing archive is pruned in place. About **5.2 GB** for a fresh checkpoint-synced pruned node, which never
writes the address indexes. Zakura's README advertises "~11 GB pruned" snapshots for Zcash (`README.md:26`).

### 1.5 Snapshots (`kogany-state/1`)

The snapshotter on `ycash-infra` `kc/mainnet-snapshots` packs a stopped kogany cache, including the
non-finalized backup (`bundles/state/FORMAT.md`, "kogany state cache, format v1"). Its tip bundle at
3,087,341 is **22.2 GB** gzipped (`records/kogany-tip-3087341/kogany/manifest.json`); bundles at 570,000 and at
the proposed H_S 3,079,999 are 18.4 and 22.4 GB. The 570,000 bundle is already 18.4 GB, which confirms that
most bytes are pre-fork Zcash history. The format does not record the storage mode.

- An archive cache restores as archive. A pruned cache restores as pruned, and the change is one-way (§1.2).
- A pruned bundle is self-sufficient for a node that will run pruned. Its `tx_by_loc` is a few MB, so the
  tarball would be about 5–7 GB.
- A pruned bundle cannot seed an archive node, lightwalletd-dd's backend, `yindex`, or a state agreement check
  that re-reads blocks.

---

## 2. ycashd: what `-prune` does and why the vault line refuses it

### 2.1 Stock behaviour (v4.5.0 = Bitcoin Core 0.11)

- `-prune=<MiB>` is a **size target** for `blk*.dat` + `rev*.dat` (`ref/ycash/src/init.cpp:389`, `:1094-1104`).
  The minimum is 550 MiB (`ref/ycash/src/main.h:235`).
- `FindFilesToPrune` deletes **whole file pairs**, oldest file number first, until usage is under target. It
  skips any file whose `nHeightLast` is within `MIN_BLOCKS_TO_KEEP` = 288 of the tip (`ref/ycash/src/main.h:222`;
  ycash6 `src/main.cpp:6702-6739`, `main.h:262`; ycash-dd `src/main.cpp:5116-5153`). Nothing prunes before
  `nPruneAfterHeight` (mainnet 100,000, ycash6 `src/chainparams.cpp:229`).
- **Kept:** the block index (`blocks/index`, every header with its Equihash solution) and the chainstate.
- **Refused or limited:** `-txindex` (`ref/ycash/src/init.cpp:1003-1005`); `-rescan`; key, address and wallet
  imports (`wallet/rpcdump.cpp:149` and others); wallet start-up after a gap beyond the pruned range
  (`wallet.cpp:6690-6700`); `getblock` of a pruned block ("Block not available (pruned data)",
  `rpc/blockchain.cpp:486-487`). `NODE_NETWORK` is unset (`init.cpp:1852-1856`).
- The help text says "disables wallet support". In fact the wallet runs; only imports and rescans are
  refused.
- **Going back** needs `-reindex`, which re-downloads everything (`init.cpp:1681-1684`).

### 2.2 Where the vault line forbids it, and why

The `-prune` help text (ycash6 `src/init.cpp:421`, ycash-dd `:429`) says it "is incompatible with -txindex and
with the vault upgrade (on any network where it has an activation height)". The txindex and rescan checks are
at ycash6 `:1202-1209` and the size target at `:1306-1316`. **The vault refusal is enforced later, after
`-nuparams` has been applied:**

| Check | ycash6 | ycash-dd | Introduced |
|---|---|---|---|
| `fPruneMode` and `UPGRADE_VAULT` has a height → `InitError` "the vault database is rebuilt from blocks and undo data" | `src/init.cpp:1608-1614` | `:1433-1439` | `671e8f84f` (ycash6) = `cc05bac0a` (ycash-dd), 2026-10-12, **audit 01/N-1** |
| `fPruneMode` and YED live → `InitError` | `:1615-1617` | `:1440-1442` | `716534dc8` (P4-a, U-21..U-24), 2026-10-06 |

The help-text wording came with `671e8f84f`. Its source is remedial report R4
(`docs/remedial-action-reports/done/MEDIUM-01-V-1-ycash-preactivation-template-coins.md` §1, §4 item 3). The
report found that the only refusal sat under `g_yellowbackLive`, so a node without a YED attestor set could
prune the `blk`/`rev` files that `Reconcile` reads and then fail to start. The audit asked for the refusal
"wherever the upgrade has a height". Nobody examined how far back the replay actually reads.

**What reads stored blocks on the vault line** (identical on both lines):

1. **Vault `Reconcile`** (ycash6 `src/vault/node.cpp:360-466`; ycash-dd `:285-391`). It runs on an unclean
   shutdown, a wiped `vaults/`, a `VAULT_DB_VERSION` bump, or a reorg deeper than the vault undo (07/F-7,
   `UNDO_KEEP` 4,096, `src/vault/db.h:70`, `UndoToPrune` `node.cpp:48-57`). In each case it wipes and replays
   **`ReadBlockFromDisk` + `ReadBlockUndo` for every height from `activation` to the tip** (`node.cpp:379`,
   `start = activation`; `:430-438`). `CoinsFromUndo` takes the spent coins from the undo files of those same
   blocks.
2. **YED index `SyncToChain`** (`src/yellowback/index.cpp:309-337`). It replays `ReadBlockFromDisk` from
   `params.startHeight`, which is the `UPGRADE_VAULT` activation height (U-22, `src/yellowback/params.cpp:179`).
   This runs on a wipe (`-reindex-yellowback`, a `SCHEMA_VERSION` or rules bump, a failed undo walk). It reads
   no undo files. `issuedBeforeStart` is closed-form (`CirculatingSupplyAt`, `index.cpp:1186`), not a block
   read.
3. **Ancestor hashes** for attestations and the claim reference (`AncestorHashes`, `node.cpp:38-46`) come from
   the in-memory block index, which `-prune` never deletes.
4. **Read RPCs that open old blocks**: `yed_gettag` (`src/rpc/yellowback.cpp:1207-1221`, any height),
   `yed_getblockverdict` (`:1711-1734`), `yed_getprice` and `yed_getnotice` (`:1101`, `:2185`, recent blocks).
   Each already answers "block not on disk".

**Why nothing below `H_V` is needed.** Before S-0, replay could need the creation height of a pre-activation
template coin, and v4.5.0's `CCoins` undo records that height only on the emptying spend (mapping §3). Rule
**S-0** (same report, option 1) made every template input created below the activation height invalid. Replay
now derives height 0 for any coin the template-output index does not hold, and S-0 rejects it exactly as the
live path does. So `Reconcile` reads blocks and undo **≥ `H_V` only**, and the YED index reads blocks
**≥ `H_V` only**. The undo files of post-activation blocks carry the pre-activation coins those blocks spend.

### 2.3 The height-floor design ("prune below activation")

DigiByte does not prune around DigiDollar state either: its state is in the chainstate itself
(`ref/digibyte/src/validation.cpp`), and nothing replays from block files. The four-part shape, at node-policy
level:

> ycashd prunes old blocks in `FindFilesToPrune` (`src/main.cpp:6702`) using **a size target over whole
> `blk`/`rev` pairs with a 288-block tip floor**. The vault and YED stores are rebuilt by replaying
> blocks ≥ `H_V` from those files, and the size target has **no notion of a height floor**. So the
> adaptation is: **`nLastBlockWeCanPrune = min(tip − MIN_BLOCKS_TO_KEEP, H_V − 1)`** wherever `UPGRADE_VAULT`
> has a height. A file whose `nHeightLast ≥ H_V` is never deleted. The blanket `InitError` becomes a
> start-up check that every `chainActive` block at or above `H_V` has `BLOCK_HAVE_DATA | BLOCK_HAVE_UNDO`;
> if not, `InitError` "re-download".

**Tier.** Node policy (not consensus): `init.cpp` and one expression in `main.cpp`. Under rule 2 it is still on
the review gate's file list, as 01/N-1 was. No cheaper rung exists: today's refusal is the zero-code option,
and the floor is the smallest change that permits pruning at all.

**Details:**

- *Margin.* None is needed: every read in §2.2 starts at exactly `H_V`. Disconnecting the activation block
  uses its own undo, which is kept. A margin of `MIN_BLOCKS_TO_KEEP` costs about 300 KB and can be added for
  comfort (Decision 2).
- *Before activation* (`tip < H_V`) the floor is the stock `tip − 288`. **Nothing changes** for a node that
  prunes today. When the network upgrades, every block from `H_V` on is retained.
- *Arrival order.* Files hold blocks in arrival order, so a file straddling `H_V` is kept whole: at most one or
  two extra 128 MiB files.
- *After activation the size target becomes a floor-bounded target.* Once the post-`H_V` files exceed it,
  pruning stops. Log "prune target below the vault floor" once rather than failing.
- *The upgrade path.* The release that sets the mainnet `H_V` (plan P8) makes today's refusal fire on **every
  pruned mainnet ycashd** that installs it. Those nodes must re-download ~26 GB of block data. Under the floor
  they start normally: they pruned only below a tip that is still below `H_V`. The start-up check catches the
  one bad case, a node that pruned past `H_V` with an old binary.
- *Regtest* activates with `-nuparams=6d5b7a31:<h>`; the same expression applies.

**What the floor would still break** (everything stock `-prune` already breaks, nothing more):

| Feature | Under the floor |
|---|---|
| Wallet rescan, key/address/wallet import, a wallet older than the pruned range | refused, as stock. YecWallet (bundles ycashd with a wallet) should stay archive by default |
| `-txindex`, `-insightexplorer` (lightwalletd-dd's backend, address index) | refused, as stock. lightwalletd-dd backends and `yindex` stay archive |
| `getrawtransaction` of a pre-`H_V` transaction | already needs `-txindex` for a confirmed non-wallet transaction, so no change |
| `getblock` / `yed_gettag` below `H_V` | "pruned data" / "block not on disk" |
| P2P serving | `NODE_NETWORK` unset, so it cannot serve IBD. The network must keep archive nodes |
| The snapshotter's `ycash-state/2` `full` and `full-insight` bundles | must come from an archive producer. A pruned flavour would be a new format field |
| `-reindex`, `-reindex-chainstate` | re-download everything, as stock |
| `-reindex-yellowback`, vault wipe/replay, `VAULT_DB_VERSION` bumps, YED schema bumps | **still work** (they read only ≥ `H_V`) |

**What it would save.** Today `H_V` is in the future on mainnet, so the floor equals stock pruning:

| ycash6 mainnet, today | Archive | Pruned below `H_V` (= stock today) |
|---|---|---|
| `blk*.dat` (173 files) | 23.16 GB | ~0.55 GB (target) |
| `rev*.dat` | 2.72 GB | included above |
| `blocks/index` | 4.51 GB | 4.51 GB (never pruned) |
| `chainstate` | 2.26 GB | 2.26 GB |
| **Total** | **32.7 GB** | **≈ 7.3 GB** |

Of the 23.16 GB of block files, **19.40 GB is heights 0–569,999** (pre-fork Zcash, 34 KB/block average,
8.8 tx/block) and 3.74 GB is the 2.52 M post-fork blocks. After activation the retained part grows by about
0.5 GB a year (blocks and undo at today's ~1.2 KB/block) plus the index.

**Cost.** About 15 lines per line (init check and message, one `min()` in `FindFilesToPrune`, the help text,
`doc/vault-rpc.md`'s operations note), plus a functional test. The stock `qa/rpc-tests/pruning.py` takes
30–120 minutes and 4 GB of disk, so the new test should be nightly only. `main.cpp` and `init.cpp` are on the
gate list.

**Benefit.** About 25 GB on any node that does not need a wallet rescan or `-txindex` (pools, seed-less
relays, explorers' secondary nodes, attestor nodes). It also removes the forced re-download for pruned nodes
at the upgrade.

---

## 3. What kogany's vault and YED state need from history

| Need | Where | Reads | Pruning impact |
|---|---|---|---|
| Vault transition per block | `prepare_vault_batch` (`zakura_db/vault.rs:540-560` on `vaults/kogany-compat`), `block_vault_delta_total` (`:292`) | the block in hand; the write path's `spent_utxos_by_outpoint` (UTXO set plus same-block outputs, `vault.rs:244-264`); vault column families | none (UTXOs are kept) |
| YED transition per block | `prepare_yed_batch` (`zakura_db/yed.rs:759`) | the block, the YED column families, the parent's YED tip | none |
| Attest hooks, claim reference, CAN-2 co-sign `blockHash(claimRefHeight)` | `finalized_block_hash_at` / `chain_block_hash_at` (`service/yed/module.rs:80-92`) | `hash_by_height` | none (kept) |
| Reorgs | the 1,000-block in-memory window (K-13); per-fork deltas | memory | none: retention ≥ 10,000 measured from the finalized tip |
| Finalized undo | **vault: none.** `rollback` refuses past `H_V` (K-14, `rollback.rs:497`). **YED: `U` records**, 4,096 deep (`yed.rs:132`, pruned at `:824`), used only for `YedSnapshot { hash }` reads (`service/yed.rs:589-600`) | the `yed_undo` column family | none: independent of `tx_by_loc` |
| Rebuild of vault/YED state | **none.** A schema, rules or network mismatch stops the node and asks for a resync (`yed.rs` module doc; K-14) | n/a | none |
| Mempool and template checks, `yed_validaterawtransaction` (`kogany-rpc/src/yed/live.rs:373-377`) | best-chain UTXOs and snapshot | none |

**So for consensus, kogany needs no raw transaction history at all.** The constraint is Zakura's own: retention
must exceed the reorg window. A floor at `H_V`, which the C++ lines need, buys kogany nothing, because nothing
replays from stored blocks. It would cost a delta in upstream `prune_height_range`. The only thing that would
change this is reversing K-14 by adding an in-place rebuild from blocks: that rebuild would need bodies from
`H_V`, and the floor would then become mandatory (Decision 5).

**Read RPCs that touch bodies** (`kogany-rpc/src/yed/live.rs` on `vaults/kogany-compat`):

| RPC | Reads | Under Pruned |
|---|---|---|
| `yed_gettag` (`coinbase_tag`, `:335-352`) | the coinbase of any block | must answer a **pruned** error below `pruneheight` (it now returns "not found") |
| `yed_getnotice` (`notice`, `:571`) | the block at the notice height, to name the notice txid | a standing notice lives at most `EMERGENCY_NOTICE_TTL` 1,152 blocks, inside the window. Degrade to the index row and flag `txid` unavailable |
| `yed_gettxinfo` (`tx_info`, `:528-538`) | `ReadRequest::Transaction` | silently falls back to index-only fields; it should add `"pruned": true` rather than look like a different answer |
| `yed_getblockverdict` (`:463`) | a block whose parent is the index tip | always recent, unaffected |
| `yed_*` at a block hash (`YedSnapshot`) | `U` records, 4,096 below the finalized tip | unaffected (4,096 + 1,000 < 11,000) |
| vault read RPCs (`kogany-rpc/src/vault.rs`) | vault snapshot only | unaffected |
| stock `getblock`, `getrawtransaction`, address RPCs | bodies, address indexes | Zakura's behaviour (§1.3) |

**Minimum retention for a pruned kogany.** Consensus needs more than 1,000 (Zakura's floor of 10,000 holds).
RPC coherence needs `tx_retention` ≥ `UNDO_KEEP` = 4,096, so that every block whose YED snapshot is servable
also has its body (it holds at 10,000). A node fronting lightwalletd-dd or a `yewd` sidecar needs enough to
cover the longest outage it must survive: 34,560 blocks is 30 days at 75 s. With Zakura's floor already above
every Yellowback depth, kogany needs **no new constant**: it allows Pruned on Ycash networks as Zakura does.

---

## 4. Recommendations

### 4.1 kogany

> Zakura prunes raw transaction bytes past a retention window (`tx_by_loc`, `block.rs:1447`) and relies on
> **headers, hash indexes and the UTXO set** to validate. kogany's vault and YED transitions read only
> those (§3), and it lacks C++'s **replay-from-blocks rebuild** by design (K-14). So the adaptation is:
> **allow `StorageMode::Pruned` on Ycash networks unchanged, with Zakura's floor (10,000)**. Add pruned errors
> to `yed_gettag`/`yed_getnotice`/`yed_gettxinfo`, and a test that pins the invariant
> `MIN_PRUNING_RETENTION > UNDO_KEEP + MAX_BLOCK_REORG_HEIGHT`.

In-tier rung: node policy and RPC; no consensus or storage-format change. Defaults: Archive stays the
default. ycash-infra runs lightwalletd-dd's kogany backend in Archive (address indexes, ingestion from
Sapling), or Pruned with `checkpoint_sync = false` and a retention of at least 34,560 when only recent
service is needed. The snapshotter publishes both an **archive** `kogany-state/1` bundle (as today, about 22 GB)
and a **pruned** one (about 5–7 GB, made with `zakurad prune-state` on a copy). The manifest gains
`storage_mode` and `lowest_retained_height` (a `kogany-state/2`, or an additive v1 field: Decision 6).

### 4.2 ycash6 and ycash-dd

> ycashd prunes with **a size target over whole file pairs** (`FindFilesToPrune`). Its vault and YED
> rebuilds replay blocks ≥ `H_V` from those files (`node.cpp:379`, `index.cpp:309`), and the size target
> lacks **a height floor**. So the adaptation is **`min(tip − 288, H_V − 1)` as the last prunable height**,
> plus a start-up check for missing data ≥ `H_V`, replacing the blanket refusal on both lines together.

**Recommendation: adopt the floor on both lines in the same release that sets the mainnet `H_V` (P8)**, not
later. Afterwards, every pruned mainnet node faces a forced re-download at the upgrade, and the floor no longer
helps it. If the lead architect prefers zero change before the release, **keep the refusal** (it is safe) and
write the forced re-download into the release notes. The floor is fully specified here and can land at any
later release (a pruned node would then still have to re-download once). The wallet limitations are stock and
unchanged in both cases. YecWallet's bundled ycashd stays archive.

### 4.3 Testing each needs

- **kogany, Pruned regtest (floor 1,001)** with Vault and YED active, against ycash6 in the mixed harness:
  - mine past `retention + 1,000`;
  - a **reorg of depth ≤ 1,000 whose fork point is near the pruned edge** (finalized tip − retention):
    `getbestblockhash`, `vault_getinfo.statehash` and `yed_getstatehash` equal on both nodes (rule 4 (ii));
  - a restart of the pruned node mid-run (the non-finalized backup reloads);
  - `yed_gettag` below `pruneheight` → pruned error; above → equal to ycash6;
  - `yed_*` at a hash 4,096 below the finalized tip → served; at 4,097 → not found;
  - offline `rollback` → refused (K-14).
- **kogany Pruned serving lightwalletd-dd**:
  - lightwalletd started with a cache tip inside the window → follows, `GetTransaction` of a recent
    transaction works;
  - started from scratch → fails with a clear "pruned" error (not a hang);
  - with `checkpoint_sync = true`: address RPCs report incomplete, and lightwalletd-dd's `GetTaddress*`
    surface the error.
- **ycash6 and ycash-dd floor**, nightly (`pruning.py`-sized):
  - regtest `-prune=550 -nuparams=6d5b7a31:<h>` with `h` placed after several 128 MiB files;
  - files below `h` deleted, none at or above it;
  - SIGKILL, wiped `vaults/`, and `-reindex-yellowback` all replay cleanly;
  - a datadir that pruned past `h` under the old binary → `InitError`;
  - the YED statehash equal to an archive node and to `yellowback_model.py`.
  - A cheap merge-gate unit test of the `nLastBlockWeCanPrune` expression.
- **Snapshotter**: `verify.py` rules for the pruned flavour (manifest fields; a pruned bundle restored into a
  build in Archive mode is refused, matching `finalized_state.rs:429`).

---

## 5. Size projections

Rates measured on mainnet:

- **Block spacing:** 75.5 s (heights 1,100,006 → 3,087,387: 1,987,381 blocks in 150.1 Ms), so about
  418,000 blocks a year (420,768 at exactly 75 s).
- **Block-file bytes** by 100,000-height bucket fell from 4.1 KB/block just after the fork to **1.05–1.10 KB**
  since 2,770,000. An empty block is 664–715 bytes (RPC samples at 2.0 M, 2.8 M, 3.0 M, 3.087 M), and blocks
  average 1.2 transactions.
- **Undo:** ~0.12 KB/block (the last `rev` file holds 101,338 blocks in 12.6 MB).
- **ycash6 block index:** ~1.0 KB/block (estimated; 4.5 GB over 3.09 M blocks today, inflated by the
  1,344-byte pre-fork solutions and uncompacted LevelDB).
- **kogany, from the column-family table:** ~0.54 KB/block of `tx_by_loc`, ~1.1 KB/block of everything else.

| Line, mode | Today | +1 year | +5 years | Growth |
|---|---|---|---|---|
| ycash6 / ycash-dd, archive | 32.7 GB | 33.6 GB | 37.4 GB | ~0.93 GB/yr |
| ycash6 / ycash-dd, pruned below `H_V` (assuming `H_V` ≈ now) | 7.3 GB | 8.2 GB | 12.0 GB | ~0.93 GB/yr (keeps all post-`H_V` blocks) |
| ycash6, stock pruning (only where no `H_V`, as mainnet today) | 7.3 GB | 7.7 GB | 9.4 GB | ~0.42 GB/yr (index only) |
| kogany, archive | 25.6 GB | 26.3 GB | 29.1 GB | ~0.70 GB/yr |
| kogany, pruned (archive pruned in place) | 7.2 GB | 7.6 GB | 9.5 GB | ~0.46 GB/yr |
| kogany, pruned (fresh, checkpoint-synced, no address indexes) | 5.2 GB | 5.6 GB | 7.3 GB | ~0.40 GB/yr |

The C++ figures exclude `debug.log` (0.9 GB here). The vault and YED stores are negligible at today's
activity (`vaults/` 20 KB), and they grow with use, not with height.

**Sensitivity.** Growth is linear in block bytes. At an average of **20 KB/block** (for instance about 20
template or YED transactions a block, with SLH-DSA owner signatures of 7,856 bytes,
`yellowback-quantum-spec.md`), archive growth is **~8.4 GB/yr** on either line. Pruned growth stays near the
header-and-index rate, except on ycashd with the floor, which keeps every post-`H_V` block. At the 2 MB
consensus ceiling (`src/consensus/consensus.h:29`) it is **~840 GB/yr**. The floor design's retained part grows
at the archive rate after activation, so under heavy use it must be revisited: options are a later floor (the
vault DB's oldest needed replay height) or an in-place migration in place of replay (option 4 in R4,
rejected then).

---

## 6. Decisions for the lead architect

1. **ycashd pruning on the vault line:** (a) keep the 01/N-1 refusal (no code; pruned mainnet nodes
   re-download at the P8 release), or (b) replace it with the height floor `min(tip − 288, H_V − 1)` plus a
   start-up data check, on ycash6 and ycash-dd together. *Recommended: (b), landed before P8 sets the mainnet
   height.*
2. **Floor margin:** none (every replay starts at `H_V`) or `MIN_BLOCKS_TO_KEEP` below `H_V` for comfort.
   *Recommended: none, with a test that a wipe and replay succeed with only blocks ≥ `H_V` on disk.*
3. **Fix the `-prune` help text** on both lines. It says "disables wallet support" (it does not) and
   "incompatible with the vault upgrade" (with (b) it becomes "keeps every block from the vault activation
   height").
4. **kogany Pruned on Ycash networks:** allow with Zakura's floor unchanged and no `H_V` floor; Archive stays
   the default. *Recommended: yes.*
5. **Record the coupling:** if an in-place vault/YED rebuild from blocks is ever added to kogany (reversing
   K-14), Pruned must gain an `H_V` floor in the same change. *Recommended: a mapping §24 row now.*
6. **Snapshots:** publish a pruned kogany bundle beside the archive one (manifest `storage_mode`,
   `lowest_retained_height`; additive v1 field or `kogany-state/2`), and, after 1(b), a pruned `ycash-state`
   flavour. *Recommended: kogany pruned bundle yes, format bump to `kogany-state/2`; ycash pruned flavour
   only on demand.*
7. **Archive service floor for the network:** pruned nodes of both kinds do not serve IBD, and Ycash has a
   handful of reachable peers. *Recommended: ycash-infra keeps at least two archive nodes per line (kogany
   archive and ycash6 archive) as seeds, and lightwalletd-dd backends stay archive.*
8. **Default retention for infra-pruned kogany** (not lightwalletd backends): Zakura's 10,000, or 34,560
   (30 days). *Recommended: 34,560.*

## 6a. Decisions taken (the Yellowback lead architect, 2026-11-02)

1. **(b)**: the height floor replaces the 01/N-1 refusal on ycash6 and ycash-dd together, before the release that sets the mainnet height.
2. **Margin: `MIN_BLOCKS_TO_KEEP` (288) below `H_V`**, as a constant. Rationale recorded: the arming window and attestor bonds live at or after `H_V` (bond UTXOs are in the chainstate, which pruning never touches), so the margin is comfort, not correctness.
3. Fix the `-prune` help text on both lines.
4. **kogany Pruned allowed** with Zakura's 10,000-block floor and no `H_V` floor; Archive stays the default. A pruned kogany still enforces Vault and Yellowback in full (consensus reads the block in hand, the UTXO set, the retained hash index and the vault/YED state database).
5. The K-14 coupling becomes a mapping §24 row.
6. A pruned kogany bundle beside the archive one as `kogany-state/2`; a pruned `ycash-state` flavour only on demand.
7. ycash-infra keeps at least two archive nodes per line as seeds; lightwalletd-dd backends stay archive.
8. Infra-pruned kogany retention: **34,560 blocks (30 days)**.

## 7. Proposed plan chunks

| Chunk | Repo(s) | Scope | Gate | Size |
|---|---|---|---|---|
| **PR-1 `prune-floor`** | ycash6 + ycash-dd (both lines, one change) | `FindFilesToPrune` floor; replace the two `InitError`s with the ≥ `H_V` data check; help text; `doc/vault-rpc.md` operations note; unit test of the floor expression | review gate (2 reviewers, four-part check above); `vault_primitive.py` section J and `vault_undo_prune.py` green | ~30 lines + tests per line |
| **PR-2 `prune-floor-nightly`** | ycash6 + ycash-dd `qa/` | the regtest floor scenario of §4.3 (nightly, `pruning.py`-sized) | nightly green 3 nights | ~250 lines Python |
| **KP-1 `pruned-rpc`** | kogany (`kogany-rpc`) | pruned errors in `yed_gettag`, `yed_getnotice`, `yed_gettxinfo`; `getblockchaininfo.pruned` parity row; constant-relation test | `kogany-rpc` tests; `rpc_ycash_parity.py` row | ~120 lines |
| **KP-2 `pruned-crossline`** | kogany + ycash6 `qa/` | the mixed-regtest pruned scenario of §4.3 (reorg at the retention edge, restart, statehash equality) | three-way invariant at every sync point | ~300 lines |
| **KP-3 `pruned-lightwalletd`** | lightwalletd-dd (tests only), kogany harness | lightwalletd-dd against a pruned kogany: inside the window, from scratch, address RPCs | client leg green | ~150 lines |
| **KP-4 `pruned-snapshot`** | ycash-infra `bundles/state` | `prune-state` on a copy, `kogany-state/2` manifest fields, `verify.py` rules, publish both | `test_mainnet.py`; one published pair | ~200 lines |
| **Mapping** | workspace `docs/mapping.md` §24 | rows below | n/a | n/a |

Proposed mapping §24 rows:

- **Pruning model.** ycashd: whole `blk`/`rev` file pairs to a size target, 288-block floor
  (`ycash6/src/main.cpp:6702`). Zakura: `tx_by_loc` rows outside a retention window from the finalized tip,
  floor 10,000 (`zakura-state/src/constants.rs:45`). Rung: node policy. ycashd needs the `H_V` floor (it
  replays from blocks); kogany does not (no replay, K-14).
- **Pruned serving.** Neither kind of pruned node advertises `NODE_NETWORK`
  (`ref/ycash/src/init.cpp:1855`; `zakurad/src/commands/start.rs:298`); a Zakura node pruned with checkpoint
  sync also stops its address indexes (`config.rs:224`). lightwalletd-dd backends stay archive.
