# Survey A: Zakura architecture and Yellowback hook points

Date: 2026-11-01. Lane A of the kogany planning exercise (`wt/BRIEFING-kogany.md`).

Pins surveyed: `ref/zakura` @ `2b062412c5` (= kogany `upgrade/vault` = `kogany-legacy`);
`ref/ycash6` @ `040894344b`; `ref/ycash` @ v4.5.0; `ycash6` `upgrade/vault` @ `65cb4ae0f`;
`ycash-dd` `upgrade/vault` @ `781946771`; `librustzcash6` `upgrade/vault` @ `af841431`. Every
`crates/...` path is under `ref/zakura/`. Comparisons with the C++ lines use `docs/mapping.md`
§19 and §22 and `ycash6` at the head above.

**Summary.** Zakura splits validation into three layers: structural parsing in `zakura-chain`, a
*semantic* verifier in `zakura-consensus` (scripts, proofs, subsidy, run per transaction and
concurrently), and *contextual* validation inside `zakura-state` when a block is pushed onto an
in-memory non-finalized chain fork; blocks older than the reorg window are written once to
RocksDB and never undone. That shape fits the vault upgrade well in three places. A spent coin
carries its height, which removes mapping §22's replay-height problem. Reorgs are handled by
dropping in-memory forks, so no vault undo log is needed. The existing NSM rule already waits for
the parent block's committed state, which is the pattern for "scripts read the set state after
the parent". It fits badly in four places, each a finding the plan must design around.
(1) **In Zakura the order of the `NetworkUpgrade` enum controls which features are on.** About 20
consensus sites test `current >= NuX`, and `activation_height` falls back to the next upgrade's
height when one is missing. Vault therefore cannot sit where the C++ lines put it, after the
Zcash upgrades. It must go between Canopy and Nu5, and "Vault is active" cannot be written as
`current >= Vault` on any network that also schedules Nu5.
(2) **The script interpreter is a crates.io Rust crate (`zakura-zcash-script` 0.0.1).** It has no
CSV, no flags that depend on height, and a checker that does not depend on state. Adding the new
opcodes means patching that crate with `[patch.crates-io]`, and `zakura-primitives` and
`zakura-transparent` also depend on it.
(3) **Every transaction is converted through `zakura-protocol`'s `BranchId::try_from`.** It
rejects the Vault branch ID and every Ycash-specific branch ID.
(4) **Zakura has no wallet, no `signrawtransaction`, no ZMQ and no notify hooks.** The
`yed_*`/`vault_*` RPCs that sign or build transactions have no home in the node.

---

## 1. Crate map and the block / transaction flow

| Layer | Crate / file | Role |
|---|---|---|
| Structural | `crates/zakura-chain` (`transaction/serialize.rs`, `parameters/`, `work/equihash.rs`, `history_tree.rs`) | types, parsing, network parameters, ZIP-221 trees, v4 sighash (native) |
| Semantic | `crates/zakura-consensus` (`block.rs`, `transaction.rs`, `transaction/check.rs`, `script.rs`, `router.rs`, `checkpoint.rs`) | per-block and per-tx checks that need no chain state beyond UTXO lookups |
| Script | `crates/zakura-script/src/lib.rs` over `zakura-zcash-script` 0.0.1 | transparent script evaluation (`CachedFfiTransaction::is_valid`) |
| Contextual + storage | `crates/zakura-state` (`service/non_finalized_state*`, `service/finalized_state*`, `service/check*`, `service/write.rs`, `request.rs`) | UTXO/nullifier/anchor checks, chain forks, RocksDB column families |
| Mempool | `crates/zakurad/src/components/mempool*` (+ `crates/zakura-node-services/src/mempool`) | download, verify, policy, eviction, tip-change handling |
| RPC | `crates/zakura-rpc/src/methods.rs` (one `rpc_trait!` trait), `methods/types/*`, `indexer.proto` | zcashd-compatible JSON-RPC, gRPC indexer streams |
| P2P | `crates/zakura-network` | per-upgrade minimum protocol versions (`protocol/external/types.rs:88-127`) |

**Block flow (full verification).** `router.rs:359` sends any block at or below
`max_checkpoint_height` to the `CheckpointVerifier` (`router.rs:401`). That verifier checks hashes
only, runs no scripts and no contextual rules, and commits with
`CommitCheckpointVerifiedBlock` (`checkpoint.rs:1371`). Every other block goes to the semantic
verifier in `block.rs:350`, which runs these steps in order:
1. difficulty and Equihash (`:407-413`);
2. Merkle root, time and coinbase position;
3. ZIP-218 limits (`:493`);
4. **the NSM parent read**: once ZIP-234 is active it awaits the parent's committed `BlockInfo`
   (`:503-530`);
5. subsidy (`:547`);
6. one `tx::Request::Block` per transaction, dispatched **concurrently** (`:595`);
7. sigops and fees;
8. `SemanticallyVerifiedBlock` (`:723`) is committed to state.

The state then runs `initial_contextual_validity` (`service/check.rs:499`) and
`validate_and_commit` (`service/non_finalized_state.rs:790`), which does the transparent spend
check (`:815`), the anchors, and `Chain::push` (`chain.rs:346`) through the `UpdateWith` trait
(`chain.rs:1909-1940`: `update_chain_tip_with` and `revert_chain_with`). Blocks deeper than
`MAX_BLOCK_REORG_HEIGHT` = **1,000** (`zakura-chain/src/parameters/constants.rs:30`; ycashd uses
99) leave the non-finalized state through `commit_finalized_direct`
(`service/finalized_state.rs:754`). That is the **single** write path for both sources, the
checkpoint verifier and finalization (doc comment `:740-745`), into `prepare_block_batch`
(`zakura_db/block.rs:1348`).

**Transaction flow.** `transaction.rs:467` runs, in this order:
- quick checks (`:485-560`);
- the branch-ID check, v5+ only (`:489`; `check.rs:930-950`);
- the UTXO load (`:599`);
- for the mempool only, maturity, `mempool_standard_input_scripts` and ZIP-317 (`:609-625`);
- `CachedFfiTransaction::new(tx, spent_outputs, nu)` (`:629`), which builds the sighasher;
- a version dispatch: V4 to `verify_v4_transaction` (`:1000`), V5 (`:1114`), V6 (`:1194`);
- one `script::Request` per input (`:1257-1286`, `script.rs`).

A script request carries only `(cached tx, input_index)`. It has no height and no chain state
(`zakura-consensus/src/script.rs`).

## 2. Network, upgrades, activation, branch IDs

- `Network` is `Mainnet` or `Testnet(Arc<testnet::Parameters>)` (`parameters/network.rs:65`).
  **Mainnet is hard-coded**: `activation_list()` returns `MAINNET_ACTIVATION_HEIGHTS` for
  `Mainnet` and the configured map for `Testnet` (`network_upgrade.rs:388-393`). Regtest and
  configured testnets are `Testnet` with a builder (`network/testnet.rs:741` onward). How Ycash
  mainnet is represented is lane B's question. It decides whether Vault's height is a constant or
  a parameter.
- `NetworkUpgrade` is a fieldless enum whose **declaration order is checked at compile time**
  against `NETWORK_UPGRADES` (`network_upgrade.rs:27-100`). `current()` is "the latest upgrade at
  or below this height" (`:419-426`).
- **`activation_height(nu)` falls back to the next upgrade's height** when `nu` has none
  (`:459-469`). Zakura relies on this deliberately, for example in the NU7 v4 ban
  (`transaction.rs:1043-1053`).
- **Order is used as a feature gate.** 23 non-test sites compare upgrades with `<`/`>=`
  (inventory: `git grep -n ">= NetworkUpgrade::\|< NetworkUpgrade::"`). The ones that matter
  most:
  - `is_nu7_active` = `current >= Nu7` (`:640-642`; its doc says every later upgrade counts as
    NU7-active);
  - `consensus_branch_id` skips the check when `current < Nu5` (`check.rs:937`);
  - the v5 parser rejects a branch below Nu5 (`serialize.rs:1140`);
  - the v6 rules start at Nu6_3 (`serialize.rs:834,1199`; `transaction.rs:1243`);
  - the fee and difficulty rules at Nu7 (`subsidy/fees.rs:25`, `network_upgrade.rs:564`);
  - ZIP-212 at Canopy (`zcash_note_encryption.rs:23`);
  - Canopy funding streams (`subsidy.rs:449`);
  - lockbox / NU6 (`block/check.rs:377`);
  - checkpoint and finalized-state auth-data handling (`checkpoint.rs:1357`,
    `finalized_state.rs:943,1081`).
- The other style is **exhaustive `match` statements over the enum**, which force any new variant
  to be classified at compile time. Each forces an explicit decision for Vault:
  - `target_spacing`, `averaging_window` (`network_upgrade.rs:503-617`);
  - `verify_v4_…`/`verify_v5_transaction_network_upgrade` (`transaction.rs:1055-1083,1168-1191`);
  - the history-tree leaf version (`history_tree.rs:126-170`, `primitives/zcash_history.rs:425-446`);
  - the block commitment field (`block/commitment.rs:130-150`);
  - Halo2 (`primitives/halo2.rs:394`);
  - P2P minimum versions (`types.rs:92-126`);
  - GBT roots (`get_block_template/proposal.rs:207`);
  - the configured-heights conversion (`testnet.rs:178-204`).
- **Branch IDs come from one global table**, the same for every network:
  `CONSENSUS_BRANCH_IDS` (`network_upgrade.rs:259-274`), with reverse lookup through
  `TryFrom<u32>` (`:102-112`).
- **Configurable activation (regtest, configured testnet).** `ConfiguredActivationHeights`
  (`testnet.rs:549-582`) has one `Option<u32>` per upgrade and is
  `serde(deny_unknown_fields, PascalCase)`, so Vault needs its own field. `for_regtest` back-fills
  only Overwinter through Canopy and leaves NU5+ unset (`:589-628`).
  `with_activation_heights` builds a `BTreeMap<Height, NU>`, so **one upgrade per height**:
  a later upgrade at the same height overwrites an earlier one. It then rejects any map whose
  height order differs from enum order (`OutOfOrderUpgrades`, `:960-972`) and rejects height 0
  (`:967`). `with_activation_height_overlay` refuses duplicate heights (`:994-1006`).
- `getblockchaininfo` reports `upgrades` and `consensus.{chaintip,nextblock}` from the enum and
  table (`zakura-rpc/src/methods.rs:2229-2250`). Light clients get Vault's `nextblock` (mapping
  §22 row "Next-block branch for light clients") with no extra work once Vault is in the table.

## 3. Transaction versions, sighash, where Orchard / NU5+ are gated

- Every transaction is converted to `zakura-primitives` through `Transaction::to_librustzcash(nu)`
  (`zakura-chain/src/transaction.rs:1857-1876`). That calls
  `zcash_protocol::consensus::BranchId::try_from(branch_id)`, and **an unknown ID fails**, so
  `CachedFfiTransaction::new` fails with `UnsupportedByNetworkUpgrade` (`transaction.rs:629-631`).
  `0x6d5b7a31` and Ycash's `374d694f`, `8e471bd6`, `66314da3` and `19bd2d2f`
  (`ycash6/src/consensus/upgrades.cpp:34-63`) are all unknown to `zakura-protocol` 5.0.0-rc.2.
  This is the same defect librustzcash6 fixed for ycash6 (mapping §22 row "Rust branch ID").
- **The v4 (ZIP-243) sighash is native Rust in Zakura.** `V4Sighash` takes
  `consensus_branch_id` from `NetworkUpgrade::branch_id()` (`transaction/sighash/v4.rs:147-170`),
  and `SigHasher::sighash` and `sighash_v4_raw` use it for v4
  (`transaction/sighash.rs:206-300`). The `zakura-primitives` object is still built, for the
  Sapling bundle and as a fallback. Once the conversion succeeds, the v4 transparent and Sapling
  sighash bind whatever ID the Zakura enum holds. This is inferred from the code and still needs
  a vector test: `vault_vectors.json` should reproduce byte for byte.
- **v4 is accepted from Sapling through NU7** (`transaction.rs:1055-1083`), except where NU7 has
  a height (ZIP-2003: `Nu7.activation_height(network).is_some_and(..)`, `:1043-1053`). **v5** is
  accepted for Nu5..Nu7 only (`:1168-1191`) and its parser needs a branch at or above Nu5
  (`serialize.rs:1140`). **v6 (Ironwood)** needs Nu6_3 or later (`transaction.rs:1243`,
  `serialize.rs:1199`). Orchard and Ironwood bundles exist only in v5/v6
  (`transaction.rs:1114-1255`). Ycash's R-A3 rule (Vault is v4-only) falls out of enum position
  **if** Vault sits below Nu5. ZIP-244 is used only for v5+ (`zakura-script/src/lib.rs:186-214`).

## 4. The script crate

- `zakura-script` is "transparent script verification with the Rust `zcash_script` interpreter"
  (`crates/zakura-script/src/lib.rs:1`), `forbid(unsafe_code)`. **No C++ is involved.** The
  interpreter is `zcash_script = { package = "zakura-zcash-script", version = "=0.0.1" }`
  (`ref/zakura/Cargo.toml:159`). It is pure Rust (`Cargo.lock:3633-3645`: bitflags, bounded-vec,
  ripemd, secp256k1, sha1, sha2) and **is also a dependency of `zakura-primitives`,
  `zakura-transparent`, `zakura-chain`, `zakura-consensus` and `zakura-rpc`**.
- **The flags are a constant, `Flags::P2SH | Flags::CHECKLOCKTIMEVERIFY`, for every height**
  (`lib.rs:170`). The checker is `CallbackTransactionSignatureChecker { sighash, lock_time,
  is_final }` (`lib.rs:224`).
- *Uncertainty:* the `zakura-zcash-script` source is not on this machine. The upstream
  `zcash_script` 0.4.5 it forks (`~/.cargo/registry/src/*/zcash_script-0.4.5/`) has a
  `SignatureChecker` trait with only `check_sig` and `check_lock_time` (`interpreter.rs:185-196`)
  and a flag set that ends at `CHECKLOCKTIMEVERIFY = 1 << 9` (`:180`). In it, 0xb2 is `OP_NOP3`
  and 0xb9 is `OP_NOP10` (`opcode/mod.rs:400-407`), and 0xc0-0xc2 do not exist. Unless
  Zakura's fork differs, **`OP_CHECKSEQUENCEVERIFY`, `OP_CHECKSETSIG`, `OP_CHECKSETDORMANT` and
  `OP_CHECKPQSIG` all need interpreter changes**: new opcode variants, new flag bits,
  set-signature and post-quantum signature callbacks, and a sequence check.
- **Where new opcodes go:** a kogany fork of `zakura-zcash-script` substituted with
  `[patch.crates-io]` (same name, API-compatible, so `zakura-primitives` and
  `zakura-transparent` resolve to it). The Ycash-specific checker and the flags that depend on
  height go in `zakura-script/src/lib.rs`. The script request has to carry the height (or `nu`)
  and a shared set snapshot (`zakura-consensus/src/script.rs`, the `Request` struct).
  Signature-operation counting (`lib.rs` `legacy_sigop_count`, `p2sh_sigop_count`) must decide
  how to count 0xc0-0xc2. The C++ lines count them via `script.cpp` (+24 lines).
- Recoverable secp256k1 signatures (`OP_CHECKSETSIG`'s 65-byte signatures) need the `recovery`
  feature. The workspace pins `secp256k1 = "0.33"` with default features (`Cargo.toml:131`).
- **The node only verifies post-quantum signatures, never makes them.** With no wallet, kogany
  needs SLH-DSA and Falcon-512 verification and no signing. The secret-wiping patches
  (mapping §22, PQ-1/PQ-2/P3) do not apply. How to obtain verification that is byte-identical to
  the vendored C is a decision (open question 4).

## 5. State and storage: where vault and module state would live

- **Column families** are listed in `STATE_COLUMN_FAMILIES_IN_CODE`
  (`service/finalized_state.rs:163-225`). They cover blocks, header chain, transactions,
  transparent UTXOs and address indexes, per-pool nullifiers, anchors and trees (Sprout,
  Sapling, Orchard, Ironwood), `history_tree`, `tip_chain_value_pool`, `block_info`, VCT and
  pruning metadata. Format version `DATABASE_FORMAT_VERSION = 30` (`constants.rs:103`).
  Migrations live in `disk_format/upgrade/`; `add_ironwood_tree.rs` is the precedent for adding
  column families with a new pool or upgrade.
- **Per-UTXO state.** `transparent::Utxo { output, height, from_coinbase }`
  (`zakura-chain/src/transparent/utxo.rs:17-28`). Every spent coin's height is available to
  contextual validation (`ContextuallyVerifiedBlock.spent_outputs`, `request.rs:446-482`). The C++
  lines added the `'v'` index and rule S-0 because `CTxInUndo` lacked heights (mapping §22 rows
  "Spent-coin heights on replay" and "Spent-coin height on replay"). On Zakura that problem does
  not exist. S-0 is still a consensus rule and must be kept for cross-line identity.
- **Reorg model.** The non-finalized state is a set of in-memory `Chain` forks, each a cloned
  `ChainInner` with per-block maps updated through `UpdateWith` push and revert
  (`chain.rs:59-120,1909-1940`). `revert_chain_with` is called by `pop_tip` and `pop_root`
  (`:359,1390`). Finalized state is never undone online. It is undone only by the offline
  `rollback` tool (`zakura_db/rollback.rs:1`) and by pruning, which deletes **only raw
  transaction bytes** (`zakura_db/block.rs:1447` doc). Mapped onto the C++ design:
  - the per-block undo record, `UNDO_KEEP`, `Reconcile` and the tip marker (mapping §22 rows
    "Set state storage" and "Undo retention") **become** per-block `UpdateWith<VaultDelta>` on
    `Chain`, plus one atomic `prepare_vault_batch` inside `prepare_block_batch`;
  - `-reindex` replay **becomes** a database-format migration or a resync;
  - the offline rollback tool must either revert vault rows (which needs a finalized undo, open
    question 6) or refuse past Vault's height;
  - `-prune` (refused in C++ when Vault has a height) is harmless, since vault column families
    are retained consensus state.
- **The checkpoint path writes without contextual validation.** Vault and YED state transitions
  must therefore be *computed* in the shared finalized write path (`prepare_block_batch`), not
  only in `validate_and_commit`. The transition function must be total, never fail, on
  checkpointed blocks. This is the analogue of the C++ replay.
- **Proposed home** (input to lane D/synthesis):
  - set, member, bond and vault/intent records as new column families (`vault_set`,
    `vault_member`, `vault_bond`, `vault_template_out`, …, mirroring `vault/state.h:39-41,207-210`);
  - the YED module records (`yellowback/view.cpp:83-87` prefixes, `Totals`, `Snapshots`,
    `Attestors`) as their own column families;
  - the non-finalized mirror as a `Chain` field holding the per-block delta;
  - a read request `zs::ReadRequest::VaultSnapshot { parent_hash }` that resolves either the
    finalized tip or a non-finalized fork, plus an awaiting variant for block verification,
    modelled on `AwaitBlockInfo` (`request.rs:1572`; used at `block.rs:503-530`).

## 6. Mempool policy

- Standardness lives in `zakurad/src/components/mempool/storage.rs:340-420`:
  - `are_inputs_standard`, sigops;
  - `standard_script_kind` (`zakura-consensus/src/transaction/check.rs:714`), which classifies
    V/I template outputs as non-standard;
  - a single OP_RETURN of at most `max_datacarrier_bytes`, default 83
    (`mempool/config.rs:87`), where the `YV` act carrier needs 1,200 once Vault is active.
- **Tip changes.** `ChainTipChange` yields `Reset` on a switch of best chain, on skipped blocks,
  or when the next height is **any** upgrade activation (`zakura-state/src/service/chain_tip.rs:640-658`).
  So Vault activation resets the mempool with no new code. On `Grow` the mempool removes only
  mined, conflicting and expired transactions (`mempool.rs:1072-1110`). **Nothing re-checks
  scripts.** The C++ `RecheckMempool` / `RemoveInvalidVaultSpends` on every tip change (mapping
  §22 row "Script result depends on chain state") needs a new hook here, either re-verification
  of template-input transactions through the existing `retry_after_tip_reset` path
  (`mempool.rs:907`) or eviction.
- Peer scoring: `TransactionError::misbehavior_score` (`zakura-consensus/src/error.rs:782`) and
  `peer_action` (`mempool.rs:308`). The C++ "DoS 0 for set-state failures of the one template
  input" (mapping §22 row "DoS policy for state-dependent failures") becomes new error variants
  scored 0. The C++ previous-branch re-run (`old-consensus-branch-id`, DoS 10) maps to the
  mempool's `upgrade_grace_period` (`mempool.rs:191`) and the NU6.3 grace period
  (`transaction.rs:83`).
- No BIP68 anywhere (`git grep BIP68` finds nothing). Sequence locks must be added in both the
  transaction verifier (mempool, next height) and contextual validation (block). The coin
  heights are already there.

## 7. Block templates and mining

`getblocktemplate` picks mempool transactions by ZIP-317 weighted selection, aware of mempool
dependencies (`zakura-rpc/src/methods/types/get_block_template/zip317.rs:83`). Proposals,
including the server's own template (`PreparedCandidateSource::ServerTemplate`,
`zakura-consensus/src/block.rs:619-625`), go through the full block verifier
(`get_block_template.rs:1075`). As far as this survey can tell, Zakura therefore re-validates its
templates. That would remove ycash6's `TemplateRun::Try` gap (mapping §22 row "Template
validation of the miner"). Template **selection** still needs a sequential vault-act filter
(TPL-1, the analogue of `TestForBlock`), or a template with two conflicting acts is built and then
rejected. An internal miner exists (`zakurad/src/components/miner.rs`). Equihash is fixed at
`(200, 9)` for non-regtest networks (`work/equihash.rs:102-125`); that is lane B's.

## 8. RPC, zcashd-compat, the wallet question

- **JSON-RPC** comes from one `rpc_trait!` trait, `RpcServer` (`methods.rs:300-1010`, macro
  `server/jsonrpc.rs:839`), with about 41 methods. Parameters may be positional or named, and a
  trailing `Option` may be omitted. There is no client-side conversion table, so ycash6's
  `rpcCvtTable` arity rows (mapping §22 row "RPC arity") have no counterpart. `yed_*`, `vault_*`
  and `set_*` should go in a **separate module with its own `rpc_trait!` trait**, dispatched
  beside `RpcServer`, not in `methods.rs` (6,258 lines, upstream churn). The server is generic
  over one `RpcMethods` (`server.rs:641`), so composing two traits needs a small dispatcher
  (*uncertain*: not prototyped).
- **No wallet.** No wallet crate, and no `signrawtransaction`, `createrawtransaction`,
  `decoderawtransaction` or `getnewaddress` in `crates/` (only in the zcashd-compat supervisor's
  allow-list, `zakurad/src/components/zcashd_compat/supervisor.rs:34-36`). Zakura's answer for
  wallets is **zcashd-compat mode**: a `zcashd` sidecar that peers only with Zakura and serves
  the wallet RPCs (`docs/zcashd-compat.md:1-40`). The ycashd-wallet half of the delta
  (`src/rpc/yellowbackwallet.cpp`, `src/yellowback/{txbuilder,wallet,coinselect}.cpp`,
  `src/pqkey.*`, `src/wallet/*`: about 6k lines plus about 2.4k RPC lines in ycash6) has no home in
  kogany. The analogue is an `ycashd` sidecar in a "ycashd-compat" mode, but that ycashd would
  itself validate vault rules. Kogany can serve the **read-only** `yed_*` and `vault_*` RPCs and
  the build-unsigned ones (`vault_build*`, `yed_buildcancel`) that need no keys.
- **No ZMQ, no `-blocknotify`** (`git grep -i zmq` finds only a binary test vector). The
  replacement is the `indexer-rpc` gRPC streams `ChainTipChange`, `NonFinalizedStateChange` and
  `MempoolChange` (`crates/zakura-rpc/proto/indexer.proto:99-129`). chain-viz and any client that
  uses notify hooks are affected.

## 9. How Zakura keeps NU5 / NU6 / NU7 / Ironwood dormant

There is no feature flag. An upgrade is dormant on a network when it is **absent from
`activation_list()`** and no later upgrade is present. Then `current()` never reaches it, every
`>= NuX` gate is false, and `NuX.activation_height()` returns `None` because the fallback finds
no later upgrade (`network_upgrade.rs:459-469`). Rules keyed to an upgrade follow automatically:
- v5/v6 parsing and acceptance (§3);
- Orchard/Ironwood bundles, ZIP-218 limits and the NU7 v4 ban;
- NSM/ZIP-234 (`subsidy.rs:696-731`, gated on `Nu7.activation_height(..)?`);
- branch-ID checks;
- history-tree V2/V3 leaves.

Three kinds of rule are **not** keyed to an upgrade and need per-network handling. Lane B has
the parameter side.
1. Height constants on `Mainnet`: the temporary Orchard-disabling soft fork
   (`network.rs:22-32,352-378`), max-block-time and testnet minimum-difficulty heights
   (`network_upgrade.rs:369-375`).
2. Funding streams and lockbox, keyed to Canopy and NU6 (`subsidy.rs:449`, `block/check.rs:377`).
3. Generic Orchard/Ironwood quick checks that run on every transaction and pass trivially on v4
   (`transaction.rs:485-519`).

The minimalism constraint can therefore ride on "leave Nu5..Nu7 out of Ycash's activation list".
It works only if Ycash's own upgrades (`Ycash` 374d694f between Sapling and Blossom, and `Vault`)
are **new enum variants in height order**. A consequence: on any network that lists Nu5,
`Vault.activation_height()` falls back to Nu5's height and `current() >= Vault` is true. On Zcash
networks this would wrongly switch Vault on. So the Vault predicate must be "Vault explicitly in
this network's list", or the variants must only exist on a Ycash network kind (lane D).

---

## 10. Hook table: Yellowback hook → Zakura location

The rows come from mapping §22 and the hook files in ycash6 (`main.cpp:840-934,2044-2260,2895,3409-3419,3677-3963,4342-4437,4789-4866`).

| # | Yellowback hook (C++ site) | Zakura location | Notes |
|---|---|---|---|
| 1 | `UPGRADE_VAULT` enum, branch `0x6d5b7a31` (`consensus/params.h:56`, `upgrades.cpp:90`) | `NetworkUpgrade` + `NETWORK_UPGRADES` + `CONSENSUS_BRANCH_IDS` (`network_upgrade.rs:27-100,259-274`) | must sit **before Nu5** (§9). Exhaustive matches force a decision at about 10 sites (§2) |
| 2 | activation heights; regtest `-nuparams=6d5b7a31:h`, back-fill excluded | `MAINNET_ACTIVATION_HEIGHTS` / Ycash parameters (lane B); `ConfiguredActivationHeights` + `for_regtest` + `with_activation_heights` (`testnet.rs:549-628,899-990`) | add a `Vault` field, leave it out of `for_regtest`'s back-fill, and keep the order check |
| 3 | Rust `BranchId::Vault` (librustzcash6 `4867cf85`/`eeb7740d`) | `to_librustzcash` (`transaction.rs:1857-1876`) through `zakura-protocol` | patch `zakura-protocol`, or bypass for v4 (lane B/D); Ycash IDs hit the same wall |
| 4 | v4-only under Vault, R-A3 (`main.cpp:1217-1220`) | `verify_v4/v5_transaction_network_upgrade` (`transaction.rs:1030-1191`), `serialize.rs:1140` | automatic below Nu5; add an explicit test |
| 5 | history-tree leaves V1 for Vault (`rust/src/history.rs`) | `history_tree.rs:126-170`, `zcash_history.rs:425-446`, `block/commitment.rs:130-150` | PreOrchard / `ChainHistoryRoot` arms; the tree resets at activation as for every upgrade |
| 6 | per-epoch P2P version (deferred to P8) | `min_specified_for_upgrade` (`zakura-network/src/protocol/external/types.rs:88-127`) | Ycash's 27xxxx versions are lane B |
| 7 | CSV 0xb2, BIP112 | `zakura-zcash-script` fork + checker (`zakura-script/src/lib.rs:170,224`) | needs a sequence callback and a flag |
| 8 | BIP68 sequence locks (`main.cpp:854-934,2044-2047,3828-3830`) | tx verifier (mempool, next height) + `service/check` contextual (block) | coin heights in `Utxo.height`; none of this exists in Zakura |
| 9 | `OP_CHECKSETSIG`/`OP_CHECKSETDORMANT` 0xc0/0xc1, `SCRIPT_VERIFY_VAULT` (`interpreter.cpp`, `vault/checker.cpp`) | interpreter fork + `CachedFfiTransaction::is_valid` checker + `script::Request` (+height, +snapshot) | set-signature digest = ZIP-243 with `ALL\|ANYONECANPAY` through the native `V4Sighash` |
| 10 | `OP_CHECKPQSIG` 0xc2 (SLH-DSA / Falcon verification) | same, plus a PQ verification library | verification only (§4) |
| 11 | flags that depend on height (`GetVaultScriptFlags`, `main.cpp:845`) | `lib.rs:170` (constant today) | thread `nu`/height into script verification |
| 12 | set snapshot after the parent block (`vault::TipSnapshot`, `AtParentOf`, `main.cpp:3681-3691`) | new `zs` request modelled on `AwaitBlockInfo` (`block.rs:503-530`, `request.rs:1572`) | fork-aware; must await the parent commit, which serializes pipelined verification for post-Vault blocks |
| 13 | sequential acts + template rules per block (`VaultState` overlay, `main.cpp:4342-4349`, `vault::CheckTx`) | `validate_and_commit` (`non_finalized_state.rs:790`) → new `check::vault`, then `Chain::push` `UpdateWith<VaultDelta>` | the transaction verifier is per-transaction and concurrent, so the sequential rules must live in state |
| 14 | vault DB commit / undo / reconcile (`vault/db.cpp`, `main.cpp:3409-3419,4436`) | `prepare_block_batch` (`zakura_db/block.rs:1348`) + `revert_chain_with` | no finalized undo, except for the offline rollback tool (open question 6) |
| 15 | checkpointed / replayed blocks (`CoinsFromUndo`) | `commit_finalized_direct` (`finalized_state.rs:754`) | the transition must be computed on checkpoint commits too, with no validation and no failure |
| 16 | YED module verdict, `CheckConnect` / `CommitConnect` (`main.cpp:4354-4357,4434`) | the same contextual hook as row 13, after the vault delta; YED column families | "index always on" and "unhealthy index stops the node" (U-22, D-U2) become ordinary consensus state |
| 17 | module ejection effect on the primitive (U-25) | inside the row-13 hook, the vault delta | undo comes for free through `revert_chain_with` |
| 18 | ATMP: `vault::CheckTx` against tip + mempool parents, DoS 0 (`main.cpp:2050-2260`) | tx verifier `Request::Mempool` path (`transaction.rs:609-625`) + mempool storage | needs a best-tip snapshot read and mempool-parent acts (`transaction_dependencies.rs`) |
| 19 | YED `MempoolCheckReason` (`main.cpp:2258-2259`) | same | |
| 20 | mempool recheck on each tip change (`main.cpp:4789-4866`) | `mempool.rs:1072-1110` (Grow), `chain_tip.rs:640-658` (Reset) | activation reset is free; per-block re-verification is new |
| 21 | policy: `YV` OP_RETURN ≤ 1,200, template outputs and scriptSigs standard (`policy/policy.cpp`, `script/standard.cpp`) | `mempool/storage.rs:340-420`, `check.rs:714`, `mempool/config.rs:87` | the data-carrier limit must depend on height |
| 22 | orphan size bound (ycash-dd only) | no orphan pool; pending outputs (`mempool/pending_outputs.rs`) | check tx-size limits for about 8 KB SLH-DSA spends (lane C/E) |
| 23 | dollar-per-KB fee policy, ZIP-317 floor for PQ inputs (`policy.cpp:395-476`) | `transaction::zip317` (`transaction.rs:620-625`), `get_standard_fee` | fee publication reads YED state |
| 24 | miner: TPL-1 filter / `TemplateRun::Try` (`miner.cpp`, `vault/node.cpp`) | `zip317.rs:83` selection; templates verified via `Request::Prepare` | add a sequential act filter in selection |
| 25 | `yed_*` read RPCs, `vault_*` / `set_*` read and build RPCs (`rpc/yellowback.cpp`, `rpc/vault.cpp`) | a new `rpc_trait!` module beside `methods.rs` | rpcversion 8 contract; `yed_*` only when the module is live |
| 26 | wallet RPCs (`rpc/yellowbackwallet.cpp`, `yed_mint` …), PQ keys (`pqkey.*`, `wallet/*`) | **none** | sidecar or client-side (open question 2) |
| 27 | `signrawtransaction` with vault flags (`rpc/rawtransaction.cpp`) | **none** | x402 uses it as a verifier; lane C |
| 28 | `getblockchaininfo.consensus.nextblock` | `methods.rs:2239-2250` | automatic |
| 29 | address forms `yb/yt/yr`, `sq/tq/rq` (`key_io.cpp`) | `validate_address.rs`, `NetworkKind` prefixes (`network.rs:75-117`) | lane B |
| 30 | ZMQ notifications (`zmqpublishnotifier.cpp`) | `indexer.proto:99-129` gRPC streams | clients adapt |
| 31 | init: attestor-set parameter, schedule `InitError`s, `-reindex-yellowback` (`init.cpp`) | `zakurad` config + `testnet::Parameters` builder checks (`testnet.rs:1293-1380`) | the R-A3 schedule check becomes a builder error |
| 32 | `MAX_REORG_LENGTH` 99 vs `UNDO_KEEP` 4,096 | `MAX_BLOCK_REORG_HEIGHT` 1,000 (`constants.rs:30`) | local policy, but the window that vault state is reverted within changes |

## 11. Traps as four-part checks

| Trap | Ycash does X in Y via M | Zakura's Z lacks M | Adaptation W | Rung, and why not lower |
|---|---|---|---|---|
| T-1 enum order | gates each upgrade by its own height in `NetworkUpgradeActive(h, idx)` (`ycash6/src/consensus/upgrades.cpp`); enum index carries no meaning, so Vault sits after NU6.2 (`params.h:56`) | `NetworkUpgrade` order **is** the feature gate (`>= Nu5`, `is_nu7_active`, `activation_height` fallback; §2, §9) | insert `Ycash` and `Vault` variants in height order (Vault between Canopy and Nu5); express "Vault active" as "Vault present in this network's list at or below h", never `>=` on a Zcash network | transaction-field rung untouched; a primitive-level parameter change. Placing Vault after Nu7 (copying C++) would turn on the NU7 v4 ban, 25 s spacing and ZIP-218 at Vault (`transaction.rs:1043`, `network_upgrade.rs:640`): consensus-wrong |
| T-2 branch-ID conversion | sighash in C++ `SignatureHash(..., branchId)` over any `uint32` (`interpreter.cpp`); Rust conversion patched in librustzcash6 | `to_librustzcash` requires `zakura-protocol` to know the ID (`transaction.rs:1868`) | patch `zakura-protocol` (fourth crate fork, as librustzcash6), or skip the conversion for v4 where `V4Sighash` is native | dependency rung, not consensus; lane B owns the choice |
| T-3 interpreter | interpreter in-tree C++ (`src/script/interpreter.cpp` +302 lines) | interpreter is a crates.io crate with no CSV, static flags, no state callback (§4) | `[patch.crates-io]` fork of `zakura-zcash-script` adding 0xb2 CSV, 0xc0-0xc2, flag bits and callbacks; Ycash checker in `zakura-script` | opcode rung as on the C++ lines (template already chosen over opcode where possible) |
| T-4 state reads in scripts | `ConnectBlock` holds `cs_main` and a set snapshot; scripts read it (`main.cpp:3681-3691`) | semantic verification is concurrent and stateless apart from UTXOs | a fork-aware `AwaitVaultSnapshot(parent)` request; scripts read the snapshot, while sequential acts run in state | per-vault state as on the C++ lines; there is no cheaper place for the reads |
| T-5 sequential acts | `ConnectBlock` loops txs in order on one overlay (`main.cpp:4342`) | the block verifier fans transactions out concurrently (`block.rs:595`) | sequential vault and module rules in `zakura-state` contextual validation and `Chain::push` | same rung; only the location moves |
| T-6 checkpointed blocks | C++ `-reindex` replays acts from undo (`vault/node.cpp` `CoinsFromUndo`) | checkpoint commits skip contextual validation (`router.rs:401`, `checkpoint.rs:1371`) | compute the vault delta in `prepare_block_batch` for every committed block | same rung |
| T-7 no wallet | ycashd wallet signs YED and PQ spends (`rpc/yellowbackwallet.cpp`) | no wallet, no `signrawtransaction` (§8) | the node serves read and build-unsigned RPCs; signing moves to clients or a sidecar | no consensus rung; an interface decision |
| T-8 mempool recheck | `RecheckMempool` on every tip change (`vault/node.cpp`) | the mempool re-verifies only on `Reset` (`mempool.rs:865-907`) | re-verify template-input transactions on `Grow` | policy only |

## Open questions for the lead architect

1. **Enum placement (T-1).** Do you accept that kogany's `NetworkUpgrade` gains `Ycash` and
   `Vault` variants in height order? Vault would sit before Nu5, the reverse of the C++ index
   order. The consensus meaning (heights and branch IDs) stays identical. Recommended. Lane D
   designs the predicate.
2. **Wallet scope.** Is kogany a validating and serving node only, with signing RPCs (`yed_mint`,
   owner spends, PQ keys) left to clients (YEW, YecWallet, Hawkeye) or an `ycashd` sidecar? Or
   must it eventually replace an `ycashd` wallet? The first is far smaller.
3. **Interpreter fork.** Is a fifth forked crate (`zakura-zcash-script`, patched with
   `[patch.crates-io]`) acceptable? It is the only place the new opcodes can go without
   rewriting `zakura-script`.
4. **PQ verification source.** Should kogany vendor the C++ lines' patched C (PQClean Falcon,
   slhdsa-c) through `cc`, which is byte-identical by construction? Or use a Rust verifier, held
   to `pq_vectors.json`?
5. **Reorg window.** Keep Zakura's 1,000-block non-finalized window (local policy) or align with
   ycashd's 99? It affects memory for per-fork vault deltas, not consensus.
6. **Offline rollback and finalized undo.** Should kogany keep per-block finalized vault undo so
   `zakurad rollback` works past Vault? Or should rollback refuse past the Vault height and
   require a resync?

## Inputs the synthesis needs from other lanes

- **Lane B:** how Ycash mainnet is represented (a `Network` variant, or a configured
  `Parameters` with a Ycash kind); the branch-ID dependency choice (T-2); the Ycash enum variant
  and its Equihash rule; the P2P versions per upgrade; address forms for the hook-29 row.
- **Lane C:** the authoritative list of which `vault_*`/`yed_*` RPCs need keys (rows 25-27); the
  client dependency on `signrawtransaction` and ZMQ (rows 27, 30); the transaction-size limits
  for PQ spends (row 22).
- **Lane D:** the Vault predicate under T-1, and the consequences for turning on Nu5 later on
  Ycash (Vault < Nu5 in heights; v5 under Vault invalid only while Nu5 is unscheduled); the
  history-tree leaf version if Nu5 ever activates after Vault.
- **Lane E:** whether `vault_vectors.json`/`pq_vectors.json` can be driven through
  `zakura-script` unit tests; a regtest with Canopy → Vault on kogany (Equihash and
  `disable_pow` on regtest, `testnet.rs:1533`); a cross-line equivalence harness that compares
  set, vault and YED state hashes after each block.
- **All lanes:** this survey did not read `zakura-zcash-script`'s source (it is not cached
  locally). §4 rests on its call sites and upstream `zcash_script` 0.4.5. The first planning
  chunk should fetch it at the pinned checksum (`Cargo.lock:3636`) and confirm.
