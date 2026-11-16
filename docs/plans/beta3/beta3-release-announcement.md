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
6. **Miners paid at a post-quantum address should use a ycashd or yewd wallet for it.** Those are
   the wallets that can move a post-quantum block reward (below). The YEW app and the web wallet
   cannot, so do not give a pool one of their post-quantum addresses.
7. **ycashd operators: start with `-reindex-chainstate` alone.** The node now refuses to start when
   it is combined with `-rescan`; rescan on a later start if you need to.

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
- **ycashd recovers faster from a crash.** After an unclean stop its value-pool index carries on
  from where it was, instead of being built again. A node with a wallet no longer stops when it is
  started with `-reindex-chainstate`; it waits until the rebuilt chain catches up with the wallet.
- **kogany's guard covers `invalidateblock` too**, at the same 99-block boundary as ycashd, and a
  refusal is always either recorded or reported.
- **kogany keeps up with its peers in two cases where it used to fall behind**: while it holds a
  stale side branch (it now writes each block of its backup once, not at every new block), and
  when it has lost its only connection (it redials after 10 seconds, backing off, instead of
  waiting two minutes).
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
- **kogany can be a pool's node for every kind of miner.** The Sapling and post-quantum coinbases
  koganyd builds are accepted by ycashd, tested in kogany's automated runs.
- **A post-quantum miner can now move its reward.** On mainnet and the testnets a block reward has
  to be moved into the shielded pool before it can be spent elsewhere, and until now no wallet
  command could do that for a reward paid to a post-quantum address. In ycashd and yewd,
  `z_sendmany` from that address now does it, once the reward has 101 confirmations and when every
  recipient is a shielded address. Such a send cannot leave change: name an amount, and if it would
  leave change the wallet refuses and tells you the exact amount to send instead. One call moves
  one reward unless you ask for more than the largest one. `z_shieldcoinbase` and
  `z_mergetoaddress` do not move it. Transparent and Sapling rewards work as before.
- **The fast-testnet pool already pays each miner at its own address** (`fastnet-pool.ycash.team`):
  your stratum username is your payout address. Sapling and post-quantum miners are paid there once
  the pool's own node runs beta3.
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
  (gRPC over TLS) and the web wallet (gRPC-web), and their built-in testnet default. It keeps fixed
  connections to four fast-testnet nodes, the mining pool's among them, so a payment sent through
  it reaches the miners quickly.
- **The YEW web wallet, hosted for the fast testnet**, at https://fastnet-wallet.ycash.team. Your
  recovery phrase and keys stay in your browser, encrypted, and are never sent anywhere. The site
  changes only when a maintainer deploys a reviewed version by hand, and anyone can check that what
  it serves matches the published source. Fast-testnet coins have no value.
- **Other programs**: the x402 agent-payment library runs unchanged against beta3, and the
  light-wallet server, the desktop and mobile wallets, the chain visualizer, the bridge attestor and
  the x402 library all accept nodes at RPC version 9 or 10.

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

- https://ycash.team: one page for newcomers, with a short page per product, YEW Web among them.
- `fastnet-lightwallet.ycash.team`: the fast testnet's light-wallet server.
- https://fastnet-wallet.ycash.team: the YEW web wallet for the fast testnet.

## Known limits

- **Not on mainnet.** No mainnet activation height is set for the vault upgrade, and the Ycash
  Foundation has not adopted it.
- **YED is not live on the fast testnet** (no attestor set there). The light-wallet server there
  serves YEC; its Yellowback service is off.
- **The fast testnet's mandate-end height is fixed at the release candidate**; until then builds
  carry a placeholder far above the chain tip. Every fast-testnet node must run beta3 before the
  chain reaches that height.
- **The YEW app and the web wallet cannot spend a post-quantum block reward.** They cannot see that
  a coin is a block reward, so they show it as spendable and their sends are refused. Pay such
  rewards to an address held in ycashd or yewd.
- **The web wallet is for the fast testnet only.** A web page is whatever its server sends on each
  visit, so real money belongs in the apps. Its passkey sign-in is not covered by the automated
  tests (the passphrase sign-in is).
- **kogany's protection against deep reorganisations needs its block backup to survive a
  restart.** The backup is on by default; with it turned off, a restarted koganyd follows its
  peers' best chain where ycashd would stop. koganyd warns at every start when the backup is off.
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
