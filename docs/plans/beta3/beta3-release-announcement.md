# Ycash 6.22.0-beta3 and kogany 1.8.0-ycash beta3: release announcement (draft)

*Draft for the release pages (GitHub releases, the ycash.team product pages, the Kogany site).
Every statement here is taken from the beta3 plan and its design notes in this directory; check it
again against the final release notes of each repository before it is published. Copyright (c) 2026
The Ycash developers.*

---

## What beta3 is

Beta3 is the third public beta of the Ycash vault network upgrade and of Ycash Yellowback (YED),
the dollar built on it. It ships as one tested set:

- **ycashd 6.22.0-beta3**, the Ycash full node (the release line);
- **koganyd, kogany 1.8.0-ycash beta3**, the Ycash full node in Rust, with `yewd`, its wallet daemon;
- the programs tested with them: the YEW mobile and web wallet, the YecWallet desktop wallet (its
  first packaged release), the light-wallet server lightwalletd, the yolo mining pool, the chain
  visualizer, the x402 agent-payment library and the Hawkeye bridge attestor.

It is a beta. It runs on regtest, on the one-laptop devnet and on the public fast testnet. No
activation height is set on mainnet: the vault upgrade is not active on Ycash mainnet, and nothing
in this release turns it on.

The theme of beta3: **a miner who finds a block is paid in full, at the miner's own address,
whatever kind of address that is.** A pool can now pay transparent, shielded (Sapling) and
post-quantum miners side by side, each the block reward plus every fee of the block.

## What you must do when upgrading

1. **Miners who want to keep donating to the Ycash Development Fund set `-ydf=5`** (kogany:
   `ydf = 5` under `[mining]`). The default is now 0: once the fund's mandate has ended, a block
   your node builds pays the whole reward and every fee to the miner. While the mandate lasts,
   the 5 % fund output is a consensus rule and is paid whatever this setting says.
2. **Every fast-testnet node must run beta3 before the fast testnet's fund mandate ends.** On the
   fast testnet (`-testnet -testnetprofile=fast`) the mandate now ends at its own height, set at
   the release candidate. From that height a block without the fund output is valid; a node on an
   older build rejects it and stops following the chain. A node upgraded late may need
   `clearbanned` to reconnect to its peers. A pool that keeps `-ydf=5` until every node has
   upgraded mines blocks that old and new nodes both accept. Mainnet, the other testnets and
   regtest are not affected.
3. **Plan for a slower first start.**
   - ycashd builds a new index of the chain's value by address type once, on its first start
     (about 30 seconds on a mainnet node; until it is done the RPC server answers "warming up").
     No reindex is needed.
   - koganyd upgrades its database once, on its first start (about a minute; mainnet took 75
     seconds in a test). Until it is done it serves no RPC. Allow for it in health checks and
     service supervisors.
4. **Clients that check the node's RPC version must accept 10.** `yed_getinfo` reports
   `rpcversion` 10 (beta2 reported 9). Nothing in the `yed_*` calls changes shape; 10 tells a
   client that the node has every beta3 addition below. The beta3 clients accept 9 and 10.
5. **kogany operators who mine to a Sapling address** need the Sapling output parameters,
   `sapling-output.params`, the file ycashd uses (from ycashd's parameter directory, or the path in
   `mining.sapling_output_params`). Without it a Sapling coinbase is refused with "Sapling output
   parameters are not loaded"; transparent and post-quantum mining are unaffected.

## For node operators

- **The development-fund donation is opt-in** (`-ydf`, kogany `mining.ydf`, default 0), as above.
  Any whole percentage from 0 to 100 is accepted.
- **Value pools by address type.** `getblockchaininfo` and `getblock` carry a new
  `transparentPools` object: the transparent value split into ordinary keys (`transparent_ecc`),
  post-quantum addresses (`transparent_pq`, by signature scheme), post-quantum payment channels
  (`pq_channel`), vault-locked value (`vault`) and vault release intents (`vault_intent`), plus the
  YED module's part of the vault entries (`vault_by_module`). The existing `valuePools` and `chainSupply` are unchanged, entries and
  order alike. Read pools by their `id`, never by position: the lines list `valuePools` in
  different orders.
- **kogany: the chain's transaction count** (`transactions` in `getblockchaininfo`), as ycashd.
- **kogany refuses a reorganisation deeper than 99 blocks**, as ycashd does. It logs ycashd's
  message, stops, and stays stopped across restarts until an operator has decided which chain is
  right and removed the record file it writes (`ycash-reorg-refused`, in the state directory).
- **kogany checks a block header's difficulty before its time rules**, the order ycashd uses, so
  both nodes reject the same bad header for the same reason.
- **Snapshot restores fail loudly.** A restore that is refused or fails exits with an error and
  leaves a marker file; the node's container will not start on a half-restored data directory.
  Snapshot bundles can now be stored in parts of 1 GiB, so bundles above 50 GB can be published,
  and ycashd's restore tool (`ycash-bootstrap`) restores a mainnet state bundle. On mainnet the bundle's signature is always required
  (`--allow-unsigned` is refused).
- **Builders of kogany from source** use the pinned Rust toolchain, 1.100.0
  (`rust-toolchain.toml`).

## For pools and miners

- **New RPC: `getcoinbasetemplatefor`**, on ycashd and koganyd. A pool names the block template it
  holds (its previous block hash and transaction ids) and a payout address; the node returns a
  complete coinbase that pays that address. The amount has no argument: the node derives it, the
  block reward plus every fee of the named transactions (less the fund output only where the
  mandate or the node's own `-ydf` puts one). The call keeps no state, changes no consensus rule,
  and leaves `getblocktemplate` and `submitblock` untouched. It refuses a template that is out of
  date (`template-stale`) and a coinbase the block has no room for (`coinbase-does-not-fit`).
- **yolo pays each miner at the miner's own address**, in three kinds: transparent (`s1…`, `s3…`),
  Sapling (`ys1…`) and post-quantum (`sqf…`, `sqs…`). Use the address as your stratum username,
  optionally followed by a worker label: `<address>.<label>`. A transparent miner's coinbase is
  built as before; a Sapling or post-quantum miner gets a coinbase from the node built for exactly
  the job's transactions ("paired jobs"). yolo's `/status` shows miners by payout kind.
- **No pool can ask for less.** There is no amount to request, and yolo never drops a
  transaction from a paired job: the coinbase always claims every fee of the block it is mined in.
- The pool's node interface is now `getblocktemplate`, `submitblock`, `validateaddress`,
  `z_validateaddress`, `getblockchaininfo` and `getcoinbasetemplatefor`. A pool never calls
  `yed_*`.

## For wallet users

- **YEW (mobile and web)**: a plain shielded send pays the same fee the ycashd wallet pays for that
  transaction (usually 0.00001 YEC), where it paid up to 0.0002 YEC before. The fee warning has a
  floor (a fee of 0.01 YEC or less never needs its own confirmation) and now says in plain words
  what happened and what to do.
- **YecWallet**: the first packaged release, with the matching ycashd inside. The macOS build is
  not signed by Apple: the release includes first-run instructions for macOS, and the project's own
  checksums and signatures, published beside each download, are how you check it.
- **`yewd`, kogany's wallet daemon**, closes its remaining gaps against ycashd's wallet, including
  watch-only addresses (`importaddress`, `importpubkey`).
- **`gettransaction` shows the real fee** for every way a send can be funded (a shielded-funded
  send showed a wrong fee, or none, before). It is a display fix; balances are unaffected.
- **A light-wallet server for the fast testnet**: `fastnet-lightwallet.ycash.team`, for the YEW app
  (gRPC over TLS) and the web wallet (gRPC-web).

## For explorers

- **Inputs that spend post-quantum coins name their address** (`sqf…`/`sqs…` and the testnet and
  regtest forms) in `getrawtransaction`, `getblock` verbosity 2, `getblockdeltas` and the REST
  transaction call, on an `-insightexplorer` node. No reindex is needed.
- **kogany as an explorer's node**: it answers JSON-RPC 1.0 batch requests as ycashd does, and with
  `[rpc] insight_explorer = true` names each input's value and address and adds `blockfee` to
  `getblock`, like ycashd's `-insightexplorer` (off by default; keep it off where untrusted clients
  reach the RPC port). Its address calls now report transaction counts and first and last heights.
- **`transparentPools`** (above) gives supply panels the value held by post-quantum addresses and in
  vaults. `valuePools` keeps its order, so explorers that read it by position keep working.
- The fast-testnet explorer runs at https://fastnet-explorer.ycash.team.

## New places

- https://ycash.team: one page for newcomers, with a short page per product.
- `fastnet-lightwallet.ycash.team`: the fast testnet's light-wallet server.

## Known limits

- **Not on mainnet.** No mainnet activation height is set for the vault upgrade, and the Ycash
  Foundation has not adopted it.
- **YED is not live on the fast testnet** (no attestor set there). The light-wallet server there
  serves YEC; its Yellowback service is off.
- **The fast testnet's mandate-end height is fixed at the release candidate**; until then builds
  carry a placeholder far above the chain tip.
- **A stateless call cannot see a whole block.** The node pays in full for the transactions a pool
  names; it cannot tell whether a block carries more. yolo checks every coinbase against the
  node's own template and never pairs one with other transactions. A miner can check any block
  it found with `getblock`.
- **yolo checks a Sapling coinbase's shape and value, not its recipient** (the output is
  encrypted); that the shielded output pays the miner is the node's job. A Sapling miner sees the
  payout in its own wallet.
- **A nearly full block has no room for a Sapling coinbase**; the node refuses
  (`coinbase-does-not-fit`) and the miner keeps working on its previous job until the next
  template.
- **Value-pool figures before the first run**: on a node filled from the compiled starting point
  (mainnet and the shadow testnets), blocks below it report `"monitored": false`; a pruned node
  without old undo data does the same until it is reindexed.
- **The YecWallet macOS build is unsigned by Apple** (see above). The Linux, Windows and macOS
  Intel builds are best-effort in this release.
