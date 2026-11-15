# Value pools by type (beta3 item 2, design note N-2)

**Status: design, read-only.** Chunks 2 (ycash-dd, then its ycash6 twin) and 2k (kogany) build it.
Item 2 is in `wt/beta3-list.md`; plan chunk N-2 is in `beta3-plan.md` §5. Citations are to the `upgrade/vault` main trees
of 2026-11-15: ycash-dd `00247d5c3`, ycash6 `c8f25b0ba`, kogany `2f247bd32`, `ref/inzyght` `17f505f273`.

## 0. Decisions in one screen

1. **`valuePools` does not change on any line.** The split goes in a new sibling field,
   `transparentPools`, in `getblockchaininfo` and in `getblock` (verbosity 1 and 2). Its own `transparent` total is
   split into five disjoint entries (`transparent_ecc`, `transparent_pq`, `pq_channel`, `vault`, `vault_intent`), with
   `pq_by_scheme` splitting `transparent_pq` and `vault_by_module` giving the YED module's part of the two vault entries.
2. **The data is a separate node-side index, not a `CBlockIndex` field.** On the C++ lines it is a small LevelDB keyed by
   block hash, written by one hook in `ConnectBlock` after every check has passed. `chain.h` and the block-index disk
   format do not change. On kogany it is a new column family plus a disk-format upgrade.
3. **Existing nodes do not reindex.** When the beta3 binary first starts, it fills the index once from the block and undo
   files it already has. Until that finishes, or wherever it cannot run (a pruned node), the new entries say
   `monitored: false`. On mainnet the fill starts from a compiled seed at the chain-supply checkpoint (height 2,800,000),
   so it reads about 300,000 blocks: an estimated 3–6 minutes, to be measured in chunk 2. A fill from genesis, by
   `-reindex` or by deleting the index, checks the seed.
4. **No validity rule changes.** The hook cannot reject a block, and it runs only for blocks that are already valid
   (§6). The one gated file is `main.cpp`, for a single call; the plan's two reviews (§7, chunk 2) stand.

## 1. Entries and names

### 1.1 The wallet names this matches

beta2 item 15 split the wallet balance. `z_gettotalbalance` returns `transparent_ecc`, `transparent_pq` and `pq_by_scheme`
(ycash-dd `src/wallet/rpcwallet.cpp:3965-3980`, `:4020-4029`; ycash6 `src/wallet/rpcwallet.cpp:5211-5226`, `:5260-5269`).
`getwalletinfo` returns `balance_ecc`, `balance_pq` and `pq_by_scheme` (ycash-dd `:2625-2640`). A coin is post-quantum
when its script is exactly the 35-byte `TX_PQPKH` template, `0x20 <keyHash:32> OP_1|OP_2 OP_CHECKPQSIG`
(`PQSchemeOfScript`, ycash-dd `rpcwallet.cpp:1300-1305`, the byte copy of `MatchPayToPQKeyHash`,
`src/script/standard.cpp:66-75`). Schemes are listed in the order 1 (SLH-DSA-SHA2-128s), then 2 (FN-DSA-512), and both
always appear (`PQ_BALANCE_SCHEMES`, `:1287`). The wallet's ECC figure is "transparent minus PQ": every
non-`TX_PQPKH` script counts as ECC.

### 1.2 The chain entries

Each transparent output falls in exactly one class. Classes are tested in this order, and the first match wins. The
script types are those of ycash-dd `src/script/standard.h:87-106`.

| id | Script | Matcher (C++ / kogany) |
|---|---|---|
| `transparent_pq` | `TX_PQPKH` | the 35-byte compare above / `Script::pq_key_id` (`zakura-chain/src/transparent/destination.rs:49`) |
| `pq_channel` | `TX_PQCHANNEL` (D-Q-19) | `MatchPQChannel` (`standard.h:203`, `standard.cpp:355`) / `match_pq_channel` (`kogany-yellowback/src/codecs/script.rs:280`) |
| `vault` | `TX_VAULT` | `vault::ParseVault` (`src/vault/template.cpp:253`) / `parse_vault` (`kogany-vault/src/template.rs:412`) |
| `vault_intent` | `TX_VAULT_INTENT` | `vault::ParseIntent` (`template.cpp:258`) / `parse_intent` (`template.rs:417`) |
| `transparent_ecc` | everything else: P2PKH, P2PK, P2SH, multisig, `OP_RETURN` with value, nonstandard | the remainder |

The sub-splits are:

- `pq_by_scheme`: the split of `transparent_pq` by its scheme byte (`OP_1` gives scheme 1 and `OP_2` gives scheme 2),
  with the wallet's keys `pqscheme` and `pqschemename`.
- `vault_by_module`: for each registered rule module, the part of `vault` plus `vault_intent` whose template tag is that
  module's tag. Today the only module is YED, tag `{'Y','E','D',0x00}` (`src/yellowback/script.cpp:80`,
  `src/vault/module.h:28`). An unregistered tag, such as a bridge or NEAR vault, has no row and is counted only in
  `vault` and `vault_intent`.

**Where vault-locked value goes: its own entries, beside the PQ entries.** Every vault owner is a PQ key
(`vault/template.h:41-44`). Still, a vault's YEC cannot be spent by that key alone before its height: the set or the
module can move it. Counting it in `transparent_pq` would overstate the liquid PQ figure and break the wallet's meaning
of the name (`TX_PQPKH` only). The intent is listed apart from the vault for two reasons. First, `vault_getinfo`'s
`lockedvalue` counts only vault outputs, kind 0 (`src/rpc/vault.cpp:423-430`), so `vault` can be checked against it
exactly (§5). Second, an intent is YEC already released and waiting out its delay.

**The channel is listed on its own** for the same kind of reason. Its cooperative path needs a secp256k1 server and a
PQ client, and its refund path needs the PQ client alone. That makes it neither ECC-only nor `TX_PQPKH`.

**Where YED-carrying outputs go: inside `transparent_pq`, by their script.** A YED token output is an ordinary Falcon
`TX_PQPKH` worth `TOKEN_VALUE`, 10,000 zat (`src/yellowback/params.h:93`). From the Falcon height every token output must
be Falcon `TX_PQPKH` (`doc/yellowback-rpc.md:168-171`); before that height, on regtest, it can be P2PKH. Whether an
output carries YED is a fact of the Yellowback module's state (the payload's assignments, `src/yellowback/index.cpp`).
Its script does not show it, so a script classifier cannot see it. It also depends on `-yellowback`, and a chain index
must give the same answer on every node. So the YEC dust under YED stays in `transparent_pq` (scheme 2). The YED
figures themselves stay where they are: `yed_getstats` (`supplyCents`, `collateralZat`) and `yed_verifyindex`
(`tokens`; `src/rpc/yellowback.cpp:934-975`). Tokens × `TOKEN_VALUE` is the YEC they hold. The YEC *locked* by YED,
its collateral, is script-visible through the vault tag, and that is `vault_by_module`'s YED row.

`vault_by_module`.YED is **not** expected to equal `collateralZat`. `collateralZat` counts ACTIVE and CLAIMING vaults
only (`src/yellowback/index.h:94`, `index.cpp:384-385`). The chain figure counts every unspent YED-tagged template
output, whatever the module's view of it. Chunk 2 records the relation it observes, which should be chain figure ≥
`collateralZat`, and does not assert equality.

**Chain vs wallet meaning of `transparent_ecc`.** On the chain, `transparent_ecc` excludes the channel and vault
classes. The wallet's figure includes any such script only when it watches one, which is a corner case. Both RPC help
texts say so in one line.

### 1.3 The shape

```
"transparentPools": {
  "monitored": true,                      // false until the index covers this block (§4)
  "transparent": { "monitored", "chainValue", "chainValueZat", "valueDelta", "valueDeltaZat" },
  "pools": [                              // disjoint; they sum to "transparent"
    { "id": "transparent_ecc", "monitored", "chainValue", "chainValueZat", "valueDelta", "valueDeltaZat" },
    { "id": "transparent_pq",  ... }, { "id": "pq_channel", ... },
    { "id": "vault", ... },           { "id": "vault_intent", ... }
  ],
  "pq_by_scheme": [                       // sums to transparent_pq; both schemes always, wallet order
    { "pqscheme": 1, "pqschemename": "SLH-DSA-SHA2-128s", "monitored", "chainValue", ... },
    { "pqscheme": 2, "pqschemename": "FN-DSA-512", ... }
  ],
  "vault_by_module": [                    // registered modules only
    { "module": "YED", "tag": "59454400", "monitored", "chainValue", ... }
  ]
}
```

- **Entry fields are those of `valuePools`.** ycash6 builds them with `ValuePoolDesc` (`src/rpc/blockchain.cpp:93-112`),
  and the same helper serves both lists.
- **`valueDelta` and `valueDeltaZat` appear only in `getblock`**, as with `valuePools`.
- **Amounts are numbers**, as in `valuePools`, not the wallet's strings. The ids and scheme keys match the wallet; the
  number format matches the chain RPCs.
- **On kogany, `monitored` means availability**, not "non-zero" as kogany's existing entries have it
  (`zakura-rpc/src/methods/types/get_blockchain_info.rs:61`; mapping row M-2 below).

## 2. Compatibility: why a sibling field, not appended entries and not a sub-object

**Today's arrays, by position:**

| Line | `valuePools` order | Where |
|---|---|---|
| ycash-dd | `[0]` sprout, `[1]` sapling: **there is no transparent entry** | `src/rpc/blockchain.cpp:262-264` (getblock), `:1159-1162` (getblockchaininfo) |
| ycash6 | `[0]` transparent, `[1]` sprout, `[2]` sapling, `[3]` orchard (always 0) | `src/rpc/blockchain.cpp:284-289`, `:1712-1717` |
| kogany | `[0]`–`[3]` as ycash6, then `[4]` lockbox, `[5]` ironwood; a fixed `[GetBlockchainInfoBalance; 6]` | `get_blockchain_info.rs:103-131`, `methods.rs:5201` |

**Inzyght reads `[0]`, `[1]` and `[2]` by position** (`ref/inzyght` `src/services/BlockchainState.cc:65-67`,
`src/services/BlockIndexer.cc:1586-1588`). On ycash-dd those reads are wrong today: Inzyght does not support ycash-dd,
which lacks `chainSupply` (`wt/handoff/INZYGHT-SURVEY.md`).

**Rejected: appending the split entries to `valuePools`.** Three reasons:

- **Inzyght would show them twice.** Its block page lists every element as a pool
  (`src/controllers/BlockController.cc:327-336`, `public/js/block.js:151-157`), so `transparent_ecc` and
  `transparent_pq` would appear as pools beside `transparent`.
- **It breaks Zcash's contract** for `valuePools`: the entries are disjoint and sum to `chainSupply`. Any client that
  sums the array would double-count.
- **It breaks kogany's own deserializer**, which accepts exactly 5 or 6 entries (`methods.rs:5225-5246`).

**Rejected: a sub-object inside the transparent entry.** Two reasons:

- ycash-dd has no transparent entry to hang it on, and adding one at `[0]` would move sprout and sapling. ycash-dd's
  own tests read `pools[0]` as Sprout (`qa/rpc-tests/wallet_persistence.py:67-69`, `:77-79`).
- It changes the schema of one `valuePools` element, which every client models as a flat record (Inzyght `ValuePool`,
  `src/models/RpcResponses.h:57-78`; kogany `GetBlockchainInfoBalance`).

**Chosen: the sibling field.** Readers by position are untouched. Inzyght's JSON readers ignore unknown keys
(`glz::opts{.error_on_unknown_keys = false}`, `BlockchainState.cc:199`, `:261`; `ycash_rpc_client.cc:489`, `:522`), so
it can adopt the field later by id. All three lines get the same new field, ycash-dd included, because the field
carries its own `transparent` total. The ycash6/kogany `[0..3]` agreement and ycash-dd's `[sprout, sapling]` are
left as they are, and that difference gets mapping row M-1.

## 3. Mechanism

### 3.1 How each line counts pools today

**ycash-dd.** It has only the shielded deltas: `nSproutValue` and `nSaplingValue` on disk, `nChainSproutValue` and
`nChainSaplingValue` in memory (`src/chain.h:235-262`). `ReceivedBlockTransactions` sums them (`src/main.cpp:4468`,
`:4492-4524`) and `LoadBlockIndexDB` sums them again on load (`:5320-5349`). Disk gates are `SPROUT_VALUE_VERSION` and
`SAPLING_VALUE_VERSION` (`chain.h:18-19`, `:497-506`). It has no transparent or supply tracking.

**ycash6.** It has zcashd 6's set:

- **Fields:** `nChainSupplyDelta` and `nTransparentValue`, persisted behind `TRANSPARENT_VALUE_VERSION = 6120350`
  (`chain.h:26`, `:648-654`); `nChainTotalSupply` and `nChainTransparentValue`, in memory (`chain.h:260-287`).
- **Where the transparent delta is computed:** in `ConnectBlock`, from the coins view's prevouts (`main.cpp:3838-3851`)
  and the outputs (`:4065-4070`). It is stored and summed at `:4115-4156`.
- **Existing rejects:** these sums can reject a block (`bad-transparent-value-delta-out-of-range`,
  `turnstile-violation-transparent`, `:3849`, `:4141-4185`). That is an inherited rule. The new index must not copy
  it (§6).
- **Checkpoint:** the mainnet chain-supply checkpoint at 2,800,000 seeds the totals on a node that lacks them
  (`chainparams.cpp:373-385`; `FallbackChainSupplyCheckpoint`, `main.cpp:5545-5600`). Per the comment there, re-reading
  every block on startup costs "~22 min on mainnet", which is why the checkpoint exists.

**kogany.** The chain value balance is a consensus type, `ValueBalance<NonNegative>`
(`zakura-chain/src/value_balance.rs:360-372`).

- **Non-finalized blocks:** each fork's `Chain` keeps a running total (`chain_value_pools`,
  `zakura-state/src/service/non_finalized_state/chain.rs:265`, `:2542-2552`).
- **Finalized blocks:** the value is written per height to `block_info`
  (`finalized_state/zakura_db/chain.rs:287-371`).
- **The RPCs:** `getblockchaininfo` reads it at `methods.rs:2358`, and `getblock` reads it and the parent's to form the
  delta at `:2818-2845`.

### 3.2 The new data: an index of transparent pools by type

The same design on each C++ line, as a new module `src/valuepools.{h,cpp}`, outside every gated directory:

- **Classifier.** `ClassifyTransparentScript(const CScript&)` returns the class, the scheme and the module tag, in the
  order of §1.2.
  - It reuses the exported matchers: `MatchPQChannel`, `vault::ParseVault` and `vault::ParseIntent`.
  - For `TX_PQPKH` it uses the same 35-byte compare the wallet already copies (`rpcwallet.cpp:1300`).
    `MatchPayToPQKeyHash` is `static` in `src/script/standard.cpp`, and exporting it would put a line under the gate.
    A unit test pins the classifier to `Solver` on every vector, so the copy cannot drift.
  - The address index (`CScript::AddressIndexKey`, ycash6 `src/script/script.cpp:270-319`) recognises only
    `TX_PQPKH` among the new shapes, so it is not enough on its own.
- **Delta of one block.** For every output of every transaction, add `nValue` to its class. For every input, take
  the spent output from the block's undo data (`CTxInUndo` keeps the whole `CTxOut`) and subtract it from its class.
  Coinbase inputs have no undo. The genesis block counts its outputs, as ycash6's `SetChainPoolValues` does
  (`main.cpp:5689-5712`).
- **Record.** A record is stored per block hash, holding the chain totals *after* that block for `transparent`, PQ
  scheme 1, PQ scheme 2, `pq_channel`, `vault`, `vault_intent`, and the YED rows of the vault and intent (8 amounts).
  - `transparent_ecc` is not stored. It is derived as `transparent` minus the rest, so the entries sum to the total by
    construction.
  - A delta is the record minus the parent's record.
  - Amounts are VARINTs. Before the Vault activation every class except `transparent` is 0, so a record is about
    15 bytes, or about 50 MB for 3.1 M mainnet blocks.
  - One extra key, `best`, names the last block written.
- **Store.** The store is a LevelDB at `<datadir>/blocks/valuepools/`, a separate database as the vault database is.
  That keeps `txdb.cpp` and `CDiskBlockIndex` unchanged, a downgrade to beta2 simply ignores the directory, and
  `-reindex` wipes it.
- **Hook.** One call in `ConnectBlock`, after `if (fJustCheck) return true;` and after the undo data is written:
  `valuepools::BlockConnected(block, blockundo, pindex)`. The places are ycash-dd `main.cpp:3546-3560` and ycash6
  `main.cpp:4361-4371`. At that point the inputs, the Yellowback hook (`yellowback::g_yellowback->CheckConnect`,
  ycash6 `:4357`) and every other check have passed.
- **Disconnecting a block needs no hook.** A record describes its block on that block's own chain, and the RPCs look
  records up by hash: `chainActive.Tip()` for `getblockchaininfo`, and the requested block for `getblock`.
- **Memory.** The tip's record is cached. Nothing is added to `CBlockIndex`, which on a 3.1 M-entry map would cost
  about 110 bytes per block, or 350 MB of RAM, if the totals sat there as Zcash's do.
- **Cost per block.** Each output costs one byte compare; the parsers run only when the size and prefix match. Each
  input costs the same compare on a `CTxOut` that is already in memory. There is one LevelDB put of about 20–60 bytes.
  This is negligible next to script and proof verification. The hook does not need a coins view.

**kogany** (chunk 2k), all in `zakura-state` behind the `ycash` feature:

- **Column family:** `ycash_transparent_pools`, keyed by height, with the same 8 amounts.
- **Write path:** the record is written in the same batch as `block_info` (`zakura_db/chain.rs:369-371`). Spent
  outputs are the `spent_utxos` the commit path already holds.
- **Non-finalized forks:** each `Chain` carries an accumulator beside `chain_value_pools` (`chain.rs:265`,
  `:2542-2552`). It is a plain struct with checked arithmetic and is **not** part of `ValueBalance`, so the
  non-negativity rule stays exactly where it is.
- **Classifier:** `pq_key_id`, `match_pq_channel`, `parse_vault` and `parse_intent`. `zakura-state` already depends on
  `kogany-vault` and `kogany-yellowback` (`crates/zakura-state/Cargo.toml:75-77`).
- **RPC:** the field is added in `get_blockchain_info.rs` and at `methods.rs:2358` and `:2818-2845`.

## 4. Existing nodes: the fill, not a reindex

| Option | Mainnet cost | Verdict |
|---|---|---|
| Require `-reindex` | many hours: every proof and signature again, plus the insight indexes on an explorer node | rejected for a beta upgrade |
| Report `monitored: false` until the operator reindexes (Zcash's `valuePools` pattern) | none, but no data | kept only as the state *during* the fill and on pruned nodes |
| **Fill once at startup from block and undo files** | a read with no validation | **chosen** |

The fill runs in `init.cpp` after `LoadBlockIndex`, before the node connects blocks. If `best` is missing or behind the
tip, it walks `chainActive` from the start point to the tip. For each block it reads the block and its undo
(`ReadBlockUndo`, ycash-dd `main.cpp:2866-2871`, ycash6 `:3159`) and calls the hook's own function, so a filled record
equals a live one by construction. It logs progress every 10,000 blocks.

The start point is one of these:

- **`best`**, or `best`'s nearest ancestor on the active chain when the tip moved while an older binary ran. Records
  are keyed by hash, so the ancestor's record is still right.
- **Otherwise, a compiled seed:** the network's chain-supply checkpoint where one exists. On mainnet that is height
  2,800,000, with `transparent = nChainSupplyCheckpointTransparentValue` (1,053,104,265,390,951 zat) and every other
  class 0. The claim behind the seed is that no output below 2,800,000 matches a PQ, channel, vault or intent
  template. That block is about 260 days before the templates were designed. Chunk 2 proves the claim once with a fill
  from genesis on a mainnet copy, and records it in the PR. Every later fill from genesis checks the seed and stops
  with "please restart with -reindex" on a mismatch, as `applyCheckpoint` does (ycash6 `main.cpp:5567-5580`).
  - The fast and slow testnets share mainnet below their split height, so they take the same seed.
  - Regtest, devnets and ycash-dd start from genesis, because their chains are short and ycash-dd has no checkpoint.
- **A pruned node** whose undo files no longer reach the start point cannot fill. Its entries stay
  `monitored: false`, and the log and the help text say "reindex to enable".

**Upgrade cost on a mainnet node.** About 300,000 blocks and their undo, read once. Scaling ycash6's measured 22 minutes
for all 3.1 M blocks gives about 2–3 minutes for the blocks alone. With the undo and the classification, the estimate is
3–6 minutes, which chunk 2 measures and the release notes state. A first sync or `-reindex` costs nothing extra. An
explorer node (txindex plus insight) costs the same; its other indexes are untouched. kogany runs the same fill as a
disk-format upgrade in the background format-upgrade thread, the pattern of `block_info_and_address_received`
(`disk_format/upgrade/block_info_and_address_received.rs:58-130`), which loads spent outputs from the transaction
store. It is registered after `add_yed_state` (`disk_format/upgrade.rs:167-170`, the array grows from 15 to 16), with
`DATABASE_FORMAT_MINOR_VERSION` 2 → 3 (`zakura-state/src/constants.rs:114`). kogany starts from the same seed, and its
RPC reports `monitored: false` until the upgrade marks itself complete.

## 5. Invariant tests

Unit tests:

- **Classifier vectors on each C++ line.** Each template must be classified as its class, and near misses as
  `transparent_ecc`: 34- and 36-byte PQ shapes, scheme byte `OP_3`, a vault with one byte flipped, a channel with a bad
  height. The classifier must agree with `Solver` on every vector.
- **The same vectors in kogany.** The classifier and the vault vectors (`kogany-vault/tests/vault_vectors.rs`,
  ycash-dd `src/test/vault_vectors_tests.cpp`) give one table for all three lines.

Functional test `qa/rpc-tests/value_pools_by_type.py`, on both C++ lines in the same PR pair, on regtest with
`-nuparams=6d5b7a31:<h>`. The scenario creates and spends every class: P2PKH, P2SH, `TX_PQPKH` in both schemes, a
channel, a YED vault through mint and claim to an intent, a non-YED tag, and `OP_RETURN` with value. Then:

1. **Sum, at every height** (`getblock h 1`): the five `pools` sum to `transparent`; `pq_by_scheme` sums to
   `transparent_pq`; every value is ≥ 0; each `valueDelta` is the record minus the parent's record.
2. **Equality with the old figure:** `transparent` equals ycash6's `valuePools[0]` at every height. On ycash-dd, which has
   no transparent pool, it equals the test's own sum of the outputs it built, checked against `gettxoutsetinfo`
   `total_amount` plus the `OP_RETURN` value.
3. **Vault cross-check at the tip:** `vault` equals `vault_getinfo.lockedvalue`, exactly.
4. **Reorg.** `invalidateblock` on a block that spends a vault and creates PQ outputs: the tip figures return to the
   parent's. `reconsiderblock` restores them. A competing fork with a different spend set gives that fork's figures.
5. **Restart, fill and reindex.** Stop and start, and the figures are the same. Stop, delete `blocks/valuepools`, and
   start: the fill rebuilds identical records for every height, and `monitored` is false only while it runs. This is
   the migration test, and it needs no old binary. `-reindex` gives identical records.
6. **Pruned node:** `monitored: false` and the log line.

Cross-line checks:

- **ycash-dd = ycash6:** the same scenario script on each line gives the same per-height table. This is the cross-line
  manifest entry (`wt/BRIEFING-beta2.md`).
- **ycash6 = kogany:** kogany syncs the ycash6 regtest chain of that test (kogany's `qa/test_kogany_*.py` harness), and
  `transparentPools` is compared by id at every height.
- **Live, read-only:** the fast-testnet ycashd/koganyd pair, which carries PQ and vault activity, and the mainnet pair on
  this Mac (`ycashd` RPC 8852, `koganyd` 8832), at one height. Chunk 2k's lane must state that it may read them.

## 6. Files per line, the gate, and why no rule changes

| Line | Files | Gated |
|---|---|---|
| ycash-dd | new `src/valuepools.{h,cpp}`; `src/Makefile.am`; `src/main.cpp` (one hook line plus include); `src/init.cpp` (open, fill, wipe on `-reindex`); `src/rpc/blockchain.cpp` (two `pushKV` and help); new `src/gtest/test_valuepools.cpp`; new `qa/rpc-tests/value_pools_by_type.py` and the test lists; `doc/yellowback-rpc.md` and `doc/release-notes.md` | `main.cpp` only |
| ycash6 | the same set; also `src/chainparams.{h,cpp}` (the seed: three amounts and a height beside the existing checkpoint) and `src/rpc/common.h` if the help text lives there | `main.cpp` only |
| kogany | `zakura-state`: the new column family, `disk_format/upgrade/add_transparent_pools.rs`, `upgrade.rs`, `constants.rs`, `zakura_db/chain.rs`, `non_finalized_state/chain.rs`, a read request, `column_family_names.snap`; `zakura-rpc`: `get_blockchain_info.rs`, `methods.rs` | none of the consensus crates. `non_finalized_state/chain.rs` is on the commit path, so one independent review is recommended although §7 lists none for 2k |

`chain.h`, `src/script/`, `src/consensus/`, `src/primitives/`, `txdb.cpp`, `zakura-chain`'s `ValueBalance`,
`zakura-consensus` and `zakura-script` do not change. `YELLOWBACK_RPC_VERSION` is not bumped here; integration bumps it
to 10.

**Proof sketch: the set of valid blocks is unchanged.**

1. The hook sits after `if (fJustCheck) return true;`, so it never runs for `TestBlockValidity`, the miner's template
   check, and runs only for a block that has already passed every check in `ConnectBlock`.
2. It returns `void` and takes no `CValidationState`. A failure to classify or write, or a class going negative (which
   would be a bug), is logged, and the index marks itself not monitored. It never calls `state.DoS`, `AbortNode` or
   `assert`. This is the one deliberate difference from ycash6's transparent tracking, which can reject (§3.1).
3. It reads only `block`, `blockundo` and `pindex`, all const, and writes only its own database. It touches no coins
   view, mempool, `chainActive`, `setDirtyBlockIndex` or block-index field. Removing the call therefore leaves every
   state that validation reads unchanged.
4. kogany's accumulator is not part of `ValueBalance`, and its errors are logged, never returned from the commit. The
   chain-value rule (`value_balance.rs:360-372`) is untouched.
5. The block-index disk format is unchanged, so blocks are stored, loaded and chosen exactly as before, and a downgrade
   is safe.

## 7. Clients

| Client | Reads today | Change |
|---|---|---|
| Inzyght (`ref/inzyght`) | `valuePools[0..2]` by position (`BlockchainState.cc:65-67`, `BlockIndexer.cc:1586-1588`); lists every entry on the block page (`BlockController.cc:327-336`); `chainSupply` | **none needed**: positions are unchanged and new keys are ignored. Later, in explorer E5: read `transparentPools` by id for a "PQ / in vaults" supply panel, and key `valuePools` by `id` too (survey item 4) |
| chain-viz | no `valuePools` in code, only in test fixtures (`tests/fixtures/chain-agree.json:36`, `chain-orphan.json:36`); vault value from `vault_getinfo` (`README.md:223`) | none needed; an optional supply panel reads by id |
| lightwalletd-dd | `getblockchaininfo` into `Chain`, `Upgrades`, `Blocks`, `Consensus`, `EstimatedHeight` only (`common/common.go:86-92`) | none |
| YecWallet (`yecwallet-dd`) | no `valuePools` or `getblockchaininfo` pools (no match in `src/`) | none |
| yew / yewd | `yewd/facade/src/ycashd_rpc.json:121`, `:127` hold copies of ycashd's `getblock` and `getblockchaininfo` help | regenerate that file if it is a parity fixture once the help text changes (lane Y, after chunk 2) |
| ycash-infra bundles | `chainSupply.chainValueZat` only (`bundles/state/FORMAT.md:188`) | none |
| hawkeye | a mock answers `valuePools: []` (`crates/hawkeye-ycash/src/mock.rs:2995`, `:3047`) | none |

The rule for every client from now on: **find pools by `id`, never by position.** The new field has no positional
meaning, apart from `pq_by_scheme`'s fixed scheme order, which copies the wallet's.

## 8. Proposed `docs/mapping.md` rows (the coordinator lands them)

- **M-1.** `valuePools` order differs by line:
  - ycash-dd: `[sprout, sapling]` (`src/rpc/blockchain.cpp:262-264`);
  - ycash6: `[transparent, sprout, sapling, orchard]` (`:284-289`);
  - kogany: ycash6's four, then `lockbox` and `ironwood` (`get_blockchain_info.rs:103-131`).
  - Positions 0–3 agree between ycash6 and kogany only. The split is the id-keyed `transparentPools` on all three.
- **M-2.** kogany sets `monitored` to "pool non-zero" (`get_blockchain_info.rs:61`), while ycash6 sets it to "value
  known" (`blockchain.cpp:102`). A zero `orchard` therefore reads `monitored: false` on kogany and `true` on ycash6.
  Cross-line checks compare `chainValueZat` by id. `transparentPools` uses "value known" on both lines.
- **M-3.** The transparent-pool sums can reject a block on ycash6 (`main.cpp:3849`, `:4141-4185`) but do not exist on
  ycash-dd. The new index rejects nothing on any line.

## 9. Open for the lead architect

1. **The seed claim.** "No template-shaped output below 2,800,000 on mainnet" is checked once by a fill from genesis
   before ycash6's PR merges. If it fails, the seed moves to the first matching height minus one, or the fill runs from
   genesis, at about 30–45 minutes once.
2. **`vault_by_module`.** It lists registered modules only, which today means YED. Listing every tag ever seen would make
   the record unbounded, so it is not proposed.
