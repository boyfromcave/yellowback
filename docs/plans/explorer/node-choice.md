# Explorer backend: ycashd 6.22.0-beta2 or koganyd?

2026-11-14. Advice for the Yellowback lead architect, decision EX-1 of
[`explorer-plan.md`](explorer-plan.md).

## Recommendation

**Build the explorer on ycashd 6.22.0-beta2 now. Write it so that it does not depend on one node.
Add koganyd as a second backend after kogany's qualification (K-19) and the parity items in §4.**

"Does not depend on one node" means four rules for the explorer's code:

1. JSON-RPC only. Push notifications (ZMQ) when the node has them, polling otherwise.
2. Value pools are read by `id`, never by position.
3. Fields that only one node has (`blockfee`, `txcount`, `transactions`, input values and addresses,
   spent-by) are optional, with a fallback.
4. `yed_*` answering "Method not found" is the normal state until the module is active.

A separate kogany explorer is not worth building. One explorer that runs against both nodes is: it
is a standing cross-check that the two node lines agree on blocks, addresses and vault state.

## 1. The three reasons

**1. kogany lacks data an explorer shows.** Same mainnet block and transaction on both nodes
(ycashd explorer node and koganyd beta2, both at tip 3,101,393, same best block hash):

| An explorer shows | ycashd | koganyd |
|---|---|---|
| Sender addresses and input amounts (`vin[].address`, `value`) | yes | no: one extra call per input |
| Transaction fee, block fees (`blockfee`) | yes | no: computed from the extra calls |
| "Spent by" on an output (`vout[].spentTxId`, `getspentinfo`) | yes | no: not available at all |
| Transactions per address (`txcount`), first and last height (`getaddressfirstlastheight`) | yes | no |
| Chain transaction count (`transactions`) | yes | no |
| Old pay-to-pubkey outputs under their address | yes | no (from source; not probed live) |
| Push notification of new blocks and transactions | ZMQ | gRPC streams if configured, else polling |

What both serve gave identical answers: `getaddresstxids`, `getaddressdeltas`, `getaddressutxos`,
`getaddressmempool`, `getrawmempool`, `vault_getinfo` (same state hash), `vault_list`, `set_list`.

**2. The vault and post-quantum features do not favour kogany.** Both nodes:

- put post-quantum outputs (`sqf…` / `sqs…`) in the address index under the same key
  (`ycash6/src/script/script.cpp:272-312`; `kogany/crates/zakura-chain/src/transparent.rs:360-371`);
- carry the same read-only `vault_*`, `set_*` and `yed_*` calls and the same script type labels
  (`vault`, `vaultintent`, `pqpubkeyhash`, `pqchannel`);
- leave vault outputs out of every address index, and return only current state from `vault_list`
  and `set_*`. Vault history has to be decoded from blocks by the explorer on either node.

Checked live on the fast testnet with ycashd: a post-quantum address answers `getaddressbalance`,
`getaddressdeltas` and `getaddressfirstlastheight`; a vault transaction decodes with
`vault_decodescript`. kogany was not probed on a chain where the upgrade is active (no local kogany
testnet node), so its side of this comes from source and its parity tests.

**3. Maturity and operations favour ycashd.**

| | ycashd 6.22.0-beta2 with indexes | koganyd beta2, archive |
|---|---|---|
| Status | the release line (6.22.x) | not yet a qualified line (K-19 open) |
| Explorer lineage | Inzyght was written for it; every RPC and field it reads is present | Zakura sends explorers to Zaino, which is not in this workspace |
| Flags | `-experimentalfeatures -insightexplorer -txindex` and ZMQ; adding them later costs a reindex | none; the address index is always on in archive mode |
| Mainnet disk | about 53 GB | about 24 GB |
| Time to a full index | reindex from local block files about 2 h 28 min (one Mac); from peers, days | full sync from peers 2 h 25 min |
| Snapshot | signed `full-insight` bundle at 3,100,949, published under `main-insight/` | archive snapshot at 3,090,808 |

kogany's real advantages are disk, sync time and no flags. They matter for the mainnet explorer's
running cost, not for whether the explorer can show what it must.

## 2. What ycashd beta2 itself lacks (candidate beta3 items)

| # | Gap | Effect | Rung |
|---|---|---|---|
| Y-1 | An input that spends a post-quantum output has no `vin[].address` (`src/rpc/rawtransaction.cpp:265-269`, `src/rpc/blockchain.cpp:181-184`). Seen live on the fast testnet | The sender of a post-quantum spend is blank | RPC only, both C++ lines; no consensus change |
| Y-2 | `vault_list` shows unspent outputs only; `set_*` current state only | Closed vaults and past set states need decoding from blocks | Do it in the explorer (no node change); a history read RPC only if that proves too slow |
| Y-3 | No owner-keyed index of vault outputs | An address page cannot list vaults the address once owned | Same: explorer-side index first |
| Y-4 | Value pools are positional in today's consumers (Inzyght) | The beta3 "value pools by type" change must keep the existing order | Already noted on the beta3 list |

## 3. What is not verified

- Inzyght has not yet been run against either node (plan phase E1).
- kogany on a vault-active chain; kogany's gRPC streams; the pay-to-pubkey difference (source only).
- The reindex time is from one Mac with local block files; a cloud host will differ.

## 4. kogany parity items (candidate beta3 node items, for the second backend)

1. `getaddressfirstlastheight`, and `txcount` in `getaddressbalance`.
2. `vin[].value` / `valueSat` / `address` in `getrawtransaction 1` and `getblock 2`
   (`transaction.rs:1310` sets them empty today; the indexes to look them up exist).
3. `blockfee` and `chainSupply.valueDelta` in `getblock`; `transactions` in `getblockchaininfo`;
   `commitments` reads 0.
4. A spent index (`vout[].spent*`, `getspentinfo`): zakura-state's `indexer` feature is not in the
   release build. A storage and disk decision.
5. Pay-to-pubkey outputs folded into the address index as on ycash6. Changes address balances: a
   state-format bump and a resync.
6. Push: document and ship `indexer_listen_addr` as the explorer's path, or a ZMQ-compatible
   publisher (reopens K-17).
7. An explorer needs an archive node; a pruned snapshot is no use to it.
