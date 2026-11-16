# Ycash 6.22.0-beta3 and kogany 1.8.0-ycash.beta3: combined release notes (draft)

*Copyright (c) 2026 The Ycash developers. Draft, assembled for the beta3 cut (plan chunk R-2) from
each component's own notes: ycash6 and ycash-dd `doc/release-notes.md` (the beta3 section), kogany
`doc/release-notes/v1.8.0-ycash.beta3.md`, yew `docs/release-notes-beta3.md`, yolo's README and
notes, YecWallet `docs/release-notes/release-notes-6.22.0-beta3.md`. Where this text and a
component's own notes differ, the component's notes are right: correct this file. Two values are
filled in at the release-candidate cut: the fast testnet's mandate-end height (`<H_END>`, the
fast-testnet tip at the cut plus 400) and the yew commit yewd is built from (`<YEW COMMIT>`). One
sentence is confirmed at the cut, marked `<TO CONFIRM AT THE CUT>` (section 8). Changes from
pull requests still open when this draft was written are described as shipped and must be checked
against the merged code at the cut: ycash-dd #194 and ycash6 #132 (the value-pool index resumes
after an unclean stop; ycash6's `-reindex-chainstate` with a wallet), kogany #43 and #44 (pins and
the beta release guard; the backup and redial fixes) and yew #53 (the web wallet's answers).*

Beta3 is the third public beta of the Ycash vault network upgrade and of Ycash Yellowback (YED),
the dollar built on it. It ships as one tested set, the release train
[`releases/v6.22.0-beta3.yaml`](../../../releases/v6.22.0-beta3.yaml):

| Component | Version | Where |
|---|---|---|
| ycashd (the release line) | `v6.22.0-beta3` | boyfromcave/ycash6 releases |
| ycash-dd (the reference line; no binaries) | tag `vault-params/v6.22.0-beta3` | boyfromcave/ycash-dd |
| koganyd (Ycash on Zakura, Rust; pre-release, not a qualified line) | `v1.8.0-ycash.beta3` | boyfromcave/kogany releases |
| YecWallet (desktop, bundles ycashd `v6.22.0-beta3`; its first packaged release) | `v6.22.0-beta3` | boyfromcave/yecwallet-dd releases |
| YEW (mobile and web wallet) and yewd (kogany's wallet daemon) | the train's yew commit | source; the web wallet is also hosted for the fast testnet at https://fastnet-wallet.ycash.team |
| lightwalletd, yolo, chain-viz, x402-ycash, Hawkeye | the train's commits | source |

**It is a beta.** It runs on regtest, the one-laptop devnet and the public fast testnet
(`-testnet -testnetprofile=fast`). No activation height for the vault upgrade is set on mainnet,
the Ycash Foundation has not adopted it, and nothing in this release turns it on. Not for
production funds.

The theme: **a miner who finds a block is paid in full, at the miner's own address, whatever kind
of address that is** (transparent, Sapling or post-quantum).

## 1. What you must do when upgrading

1. **Fast-testnet nodes: upgrade before height `<H_END>`.** On testnet-yb-fast the Ycash
   Development Fund mandate now ends at its own height, `<H_END>` (ycashd
   `TESTNET_FAST_YDF_MANDATE_END_HEIGHT`, koganyd `mandate_end::TESTNET_FAST`). From that height a
   block without the 5 % fund output is valid; **this is one-way**: a node on beta2 or older rejects
   the first such block and stops following the chain. ycashd also bans the peer that sent it (24
   hours, kept in `banlist.dat`), so a node upgraded late needs `clearbanned`. A pool keeps `-ydf=5`
   until every node it cares about has upgraded: those blocks are valid under every build.
   Mainnet, the slow and legacy testnet profiles and regtest are unchanged.
2. **Miners and pools: the fund donation defaults to 0 %.** Past the mandate's end (mainnet
   2,275,000) a block your node builds pays the whole subsidy and every fee to the miner. To keep
   donating, set `-ydf=5` (koganyd: `ydf = 5` under `[mining]`). During the mandate the 5 % output
   is a consensus rule and is paid whatever the setting says. Values outside 0..100 are reset to
   the default, so `-ydf=-1` now means 0 where it meant 5.
3. **RPC clients: accept `rpcversion` 10.** `yed_getinfo.rpcversion` is 10 on all three node lines
   (beta2: 9). No `yed_*` field changes shape; 10 tells a client the node has every beta3 addition
   (section 7). A client that requires exactly 9 must be changed. Every beta3 client (lightwalletd,
   YecWallet, YEW and yewd, chain-viz, x402-ycash, Hawkeye) accepts 9 and 10.
4. **Allow for a slower first start.**
   - ycashd 6.22.0-beta3 fills its new value-pool index once: about 30 seconds on a mainnet node
     (it starts from a compiled seed at height 2,800,000). The RPC server answers -28 (warming up)
     with the fill's progress until it is done. No reindex.
   - ycash-dd fills the same index from genesis: about 12 minutes on a mainnet node.
   - koganyd moves its database from format 30.2.0 to 30.3.0 once, before it serves RPC or
     commits a block: a minute or two on mainnet (75 seconds measured), less on the fast testnet,
     resumable if interrupted. One-way: nothing takes the database back to 30.2.0, though a beta2
     koganyd still opens it. Give health checks and supervisors that time.
5. **Containers that restore a snapshot (`YCASHD_BOOTSTRAP`).** The entrypoint now refuses a
   network directory whose `blocks/` holds data but has no `bootstrap.json` (a datadir an earlier
   image started on after a failed restore): set `YCASHD_BOOTSTRAP_ACCEPT_DATADIR=1` if you know it
   is good, or unset `YCASHD_BOOTSTRAP`. A failed restore leaves `<network>.bootstrap-incomplete`
   and the container will not start past it until you clear it. On mainnet a restore needs a signed
   bundle (`--allow-unsigned` is refused); ycash-dd's image refuses a mainnet bundle altogether.
6. **koganyd operators who mine to a Sapling address** need `sapling-output.params` (3,592,860
   bytes), read from `mining.sapling_output_params` or ycashd's parameter directory and checked by
   its SHA-256 (ycash-infra release `zcash-params-v1`). Without it a Sapling coinbase is refused
   ("Sapling output parameters are not loaded"); transparent and post-quantum mining are unaffected.
7. **Miners paid at a post-quantum address: use a ycashd or yewd wallet for that address.** Only
   those wallets can move a post-quantum block reward (section 3, "A post-quantum reward"). The YEW
   app and the web wallet cannot tell that a coin is a coinbase, so a reward paid to one of their
   addresses shows as spendable but their sends are refused (section 8).
8. **ycash6 operators: do not combine `-reindex-chainstate` with `-rescan`.** The node now refuses
   to start with both (also when `-salvagewallet` or `-zapwallettxes` implies `-rescan`). Start with
   `-reindex-chainstate` alone, then use `-rescan` on a later start if you need it.

## 2. Node operators

- **The one consensus change: the fast testnet's mandate end** (item 1 above), on ycashd, ycash-dd
  and koganyd, at the same height.
- **Value pools by address type (`transparentPools`).** `getblockchaininfo` and `getblock`
  (verbosity 1 and 2) carry `transparentPools`: the transparent pool split into `transparent_ecc`,
  `transparent_pq` (with `pq_by_scheme`), `pq_channel`, `vault` and `vault_intent`, plus
  `vault_by_module`. `valuePools` and `chainSupply` are unchanged, entries and order alike; read
  pools by `id`, never by position. A node-side index, not a consensus rule: a failed write turns it
  off until the next restart. koganyd also answers `getblockchaininfo.transactions`, the chain's
  transaction count, as ycashd does.
- **The value-pool index resumes after an unclean stop** (ycashd and ycash-dd). After a kill or a
  power loss the node continues from the last block whose ancestors all have a record, where it
  used to fill the index again from the seed or from genesis, answering -28 throughout. Two log
  lines say where it resumed. `-reindex` and `-reindex-chainstate` still rebuild it.
- **ycashd: a wallet node survives `-reindex-chainstate`.** A node with a wallet (the default)
  started with `-reindex-chainstate` stopped on an assertion inherited from upstream zcashd; it now
  waits until the rebuilt chain reaches the wallet's last block, logs when it waits and when it
  resumes, and the wallet's balances read low until then. `-reindex-chainstate` together with
  `-rescan` is refused at start (item 8 above). ycash-dd has no `-reindex-chainstate`.
- **koganyd stops on a reorganisation deeper than 99 blocks**, as ycashd does, logs ycashd's
  message and exits with status 1. Unlike ycashd it writes `ycash-reorg-refused` in the state
  directory and every start stops again while that file exists; `docs/kogany.md` ("Deep
  reorganisations") has the steps. `invalidateblock` goes through the same guard, counted from the
  parent of the invalidated block as on ycashd, so the boundary is the same 99 blocks; a refused
  `invalidateblock` answers an error, leaves the block valid and the tip where it was, and stops
  the node with the record. A refusal is always either recorded or, if the record cannot be
  written, reported as such when the node stops.
- **koganyd keeps up with a peer while it holds a stale side branch.** Its non-finalized backup
  rewrote every block two chains share at every tip update, so a follower with a stale side branch
  crawled until those blocks were finalized; each block is now written once.
- **A koganyd left without any peer connection redials after 10 seconds**, doubling the wait after
  each failed attempt at an address (10, 20, 40, 80 s, then about two minutes); with any connection
  open the upstream two-minute wait stands. An inbound reconnection from an address that connected
  in the last two minutes or so is still refused by the per-IP limit, so it is koganyd's own dial
  that restores the link.
- **koganyd checks a header's difficulty target before the median-time rules**, ycashd's order;
  the set of accepted blocks is unchanged.
- **Snapshot restores** (`contrib/bootstrap/ycash-bootstrap`): a refused or failed restore exits
  non-zero and leaves the marker; the import node ignores peers; bundles may be stored in 1 GiB
  parts (`ycash-state/3`), so bundles above 50 GB can be published; mainnet state bundles restore,
  signature required; a restore no longer hangs on a node stuck in warm-up (`--stall-timeout`,
  default 1800 s) and a full disk is named at once.
- **koganyd builds from source with the pinned Rust toolchain**, 1.100.0 (`rust-toolchain.toml`).
  OpenTelemetry crates at 1.45.2 (GHSA-mf5v-w3w3-f6cg).

## 3. Pools and miners

- **New RPC `getcoinbasetemplatefor "address" {"previousblockhash": …, "txids": […]}`** on all
  three node lines, with the same answers and error strings: a complete coinbase that pays
  `address` (transparent, Sapling or post-quantum) for the template the pool names. There is no
  amount argument: the node pays the subsidy plus the fee of every named transaction, less the fund
  output its own coinbase carries at that height (required during the mandate, then the node's
  `-ydf` share, 0 by default). Refusals: `template-stale: …`, `coinbase-does-not-fit: …`. Stateless,
  not a consensus change; `getblocktemplate` and `submitblock` are untouched.
- **yolo pays each miner at the miner's own address**: the stratum username is the payout address,
  optionally `<address>.<label>`. A transparent ECC miner's coinbase is built as before; a Sapling
  or post-quantum miner gets a paired job whose coinbase the node built for exactly the job's
  transactions. yolo never drops a transaction from a paired job, and `/status` shows miners by
  payout kind. yolo checks a Sapling coinbase's shape and value, not its recipient (the output is
  encrypted): that it pays the miner is the node's job, and the miner sees it in its own wallet.
- **What a yolo operator does** (yolo `CHANGELOG.md`, beta3): nothing for transparent miners or a
  `--payout` pool. To pay Sapling and post-quantum miners, run the pool node on a beta3 node with
  `-rpcthreads` of at least `--coinbase-concurrency` (default 2) plus 2, and leave its `-ydf` at 0
  (a pool whose node takes a fund share must tell its miners). GPU miners on a network whose blocks
  come minutes apart need `--share-ratio`. A node without `getcoinbasetemplatefor` still serves
  transparent miners; Sapling and post-quantum usernames are then refused. `--max-paired-per-ip`
  (default 8) caps the shielded and post-quantum payout addresses per source IP.
- **A pool's node interface** is now `getblocktemplate`, `submitblock`, `validateaddress`,
  `z_validateaddress`, `getblockchaininfo` and `getcoinbasetemplatefor`. A pool never calls `yed_*`.
- **koganyd as a pool's node**: its Sapling and post-quantum coinbases (through
  `getcoinbasetemplatefor`) are accepted by ycashd: kogany's mixed-node CI mines paired Sapling and
  post-quantum blocks on koganyd and a ycashd peer accepts every one.
- **The fast-testnet pool runs in per-miner mode** (`fastnet-pool.ycash.team:3333`): the stratum
  username is the payout address. Transparent miners are paid at their own address now; Sapling and
  post-quantum miners are paid once the pool's node runs beta3 (until then the pool's `status`
  shows `"coinbaseCall": false`). At most two Sapling or post-quantum payout addresses per source
  IP there. The pool's node keeps the 5 % fund share until every fast-testnet node runs beta3
  (section 1, item 1).
- **A post-quantum reward.** Where a coinbase must be shielded (mainnet and the testnets), no
  wallet call could spend a reward paid to a post-quantum address. `z_sendmany` from that address
  (ycashd, ycash-dd and yewd) now spends its mature coinbase (101 confirmations) when every
  recipient is shielded and the address's other coins do not cover the send. Such a send makes no
  change: a send that would leave change is refused with the exact amount to send ("… To spend the
  selected coins, send exactly <a> to shielded recipients …"); send that amount. Coins are taken
  largest first, so one call moves one reward unless the amount is above the largest one. With a
  transparent or post-quantum recipient the coinbase is never used, and the refusal says how much
  coinbase the address holds. `z_shieldcoinbase` and `z_mergetoaddress` do not move it; ycash6
  `doc/yellowback-mining.md` §13 has a worked example. Transparent (ECC) and Sapling rewards are
  unchanged.
- `getblocksubsidy`'s `founders` past the mandate is this node's `-ydf` share. ycash6's
  `getblocktemplate` has no `coinbasetxn.ydfpercentage` (ycash-dd's has) and shows
  `foundersreward` only while the mandate runs.

## 4. Wallet users

- **`gettransaction` shows the transaction's real fee** for every funding shape (ycashd and
  ycash-dd): a Sapling-funded send showed its transparent outputs as the fee, a Sapling-to-Sapling
  send showed 0, and ycash-dd showed none. Display only. `fee` is left out when the wallet does not
  hold the funding transaction of every transparent input.
- **YecWallet `v6.22.0-beta3`**: the first packaged release, with ycashd `v6.22.0-beta3` inside.
  Tier 1 is macOS on Apple silicon; Intel macOS, Linux and Windows packages are best effort and may
  be missing. **Not signed by Apple and not notarized**: macOS warns on first open (click Done, then
  System Settings, Privacy & Security, Open Anyway; or `xattr -dr com.apple.quarantine
  /Applications/yecwallet.app` after checking the download). Windows shows a SmartScreen prompt.
  Check every download against `SHA256SUMS` and `SHA256SUMS.minisig` (Ycash release key
  `02C923A6C593AF18`, `RWQYr5PFpiPJAigk86vf89bPYrJCXj5tskgRAPRYFsEXyciZo8dveOGQ`).
- **YEW (mobile and web)** (yew `docs/release-notes-beta3.md`): a Sapling send pays what ycashd's
  wallet pays for that shape, a flat 1,000 zat (0.00001 YEC) with up to 50 Sapling outputs (the app
  paid ZIP-317's 5,000 zat per action, the web wallet 10,000 or 15,000 zat); sends with a
  post-quantum input keep the node's size-based fee. The unusual-fee question compares with the
  node's fee for the same shape, never asks about 0.01 YEC or less, and is titled "YEC price check"
  when only the server's YEC price is low. Home says when a server cannot look up post-quantum
  addresses instead of showing 0. The wallet accepts a server at contract version 9 or 10 and
  refuses 8. Its testnet default server is `fastnet-lightwallet.ycash.team`.
- **yewd restored from its phrase with a build older than yew `fc56fba7`** (the beta2 train named
  `6d9017e`) should be restored again with this one (the post-quantum fee, YED burn guard and seed
  restore fixes).
- **yewd** (kogany's wallet daemon, built from yew `<YEW COMMIT>`): watch-only imports
  (`importaddress`, `importpubkey`) with the watch-only reads, `getunconfirmedbalance`,
  `z_mergetoaddress` from post-quantum addresses, vault-call coin locks released, vault funding
  change listed, and the fees ycashd's wallet charges for each transaction shape.
- **A light-wallet server for the fast testnet** at `fastnet-lightwallet.ycash.team` (gRPC over TLS
  for the app, gRPC-web for the web wallet), the built-in testnet default of both. It serves YEC;
  its Yellowback service is off there (no YED attestor set on the fast testnet). Its node keeps
  fixed connections to four fast-testnet nodes (both seeds, the pool's node and the explorer's), so
  a transaction sent through it reaches the pool's node directly.
- **The YEW web wallet is hosted for the fast testnet** at https://fastnet-wallet.ycash.team: a
  testnet build with that server fixed (it cannot be changed there) and a banner saying the coins
  have no value. The recovery phrase and keys stay in the browser, encrypted at rest under a
  passkey or a passphrase, and are never sent. A merge never changes what the name serves: a
  maintainer deploys a reviewed commit by hand, and `scripts/verify-bundle.sh` compares what the
  site serves with a build of that commit. A second tab on the same wallet is told the wallet is
  open elsewhere; a screen shows an answer only for the selection it was asked for (an address
  picked in Receive, a Send preview). https://ycash.team has a YEW Web tile and page.

## 5. Explorers

- **Inputs spending post-quantum coins name their address** on an `-insightexplorer` ycashd:
  `getrawtransaction` (verbose `vin[].address`), `getblock` verbosity 2, `getblockdeltas` and REST
  `/rest/tx/<txid>.json`, in the scheme-visible form (`sqf…`/`sqs…`, `tqf…`/`tqs…`,
  `rqf…`/`rqs…`). No reindex.
- **koganyd as an explorer's node**: JSON-RPC 1.0 batches answered as ycashd does;
  `[rpc] insight_explorer = true` adds `value`, `valueSat` and `address` to non-coinbase inputs and
  `blockfee` to `getblock` (off by default; keep it off where untrusted clients reach the RPC port;
  no spent index, so a call with more than 5,000 distinct parent transactions answers without the
  input fields). `getaddressbalance` answers `txcount`, `getaddressfirstlastheight` is served, and
  `getblockchaininfo.commitments` is the Sprout tree size.
- **`transparentPools`** (section 2) gives supply panels the value at post-quantum addresses and
  in vaults; chain-viz's block tooltip shows it. The fast-testnet explorer is
  https://fastnet-explorer.ycash.team.

## 6. Other clients

- **x402-ycash** runs unchanged against the beta3 nodes; its tests were run against both C++ node
  lines at `rpcversion` 10.
- **lightwalletd, YecWallet, YEW and yewd, chain-viz, Hawkeye and x402-ycash accept `rpcversion` 9
  and 10.** chain-viz's block tooltip shows `transparentPools` by id.

## 7. What `rpcversion` 10 covers

| Call or field | Change |
|---|---|
| `getcoinbasetemplatefor` | new; result `data`, `hash`, `height`, `previousblockhash`, `addresstype`, `subsidy`, `fund`, `fundrule`, `fees`, `amount`, `txcount`, `flags`, `sigops`; errors `template-stale: …`, `coinbase-does-not-fit: …` |
| `getblockchaininfo`, `getblock` (verbosity 1, 2) | new `transparentPools`; `valuePools` unchanged; koganyd adds `transactions` |
| `getrawtransaction` (verbose), `getblock` verbosity 2, `getblockdeltas`, REST `/rest/tx` | `address` of an input spending a post-quantum output |
| `gettransaction` | `fee` for every funding shape; absent when a transparent input's funding transaction is not held |
| `z_sendmany` from a post-quantum address | spends its mature coinbase to shielded recipients with no change; new refusal text naming the exact amount (wallet only) |
| `-ydf`, `getblocksubsidy` `founders` | default 0; past the mandate `founders` is this node's `-ydf` share |

## 8. Known limitations

- **Not on mainnet**, and **no YED attestor set on any public network**: YED cannot be minted on the
  fast testnet with this release.
- **The fast testnet's fund mandate ends at a height set at the release candidate**, `<H_END>`.
  Every fast-testnet node must run beta3 before the chain reaches it; a node on beta2 or older
  stops following the chain there (section 1, item 1).
- **The YEW app and the web wallet cannot spend a post-quantum block reward.** The light-client
  coin listing (lightwalletd's `GetAddressUtxos`) carries no coinbase flag, so they show such a
  reward as spendable and the node refuses their sends. Pay post-quantum rewards to an address a
  ycashd or yewd wallet holds.
- **yewd's post-quantum coinbase spend** follows the C++ wallets' rule, strings and fee, and is
  covered by yew's own tests. `<TO CONFIRM AT THE CUT: whether the shared script
  wallet_pq_coinbase_spend.py has also passed with yewd in front of a real koganyd and ycashd; if
  it has, say "and proven against real nodes"; if not, say "it has not yet been run against real
  nodes">`
- **The hosted web wallet is for the fast testnet only**, by decision: a web page is whatever its
  server sends on that visit. Money belongs in the apps. The web wallet cannot send post-quantum to
  private, private to post-quantum, or fund a mint from the private balance (the app can).
- **The web wallet's passkey path has no automated test** (no browser authenticator in the
  headless runs); the passphrase path is the one the automated runs walk.
- `gettransaction`'s `fee` and `details[].fee` can differ for a Sapling-funded send (the second counts
  the transparent debit only).
- **Value pools below the seed**: on a ycashd that filled the index from the compiled seed (mainnet
  and the shadow testnets), blocks below 2,800,000 report `"monitored": false`; a pruned node lacking
  old undo data does too until it is reindexed. A koganyd that upgrades a pruned beta2 database gets
  `transactions` but not the pools.
- **`getcoinbasetemplatefor` checks that each named transaction is in the mempool, not that the set
  is complete or in order.** Name `getblocktemplate`'s list verbatim, or the block is invalid.
- **A nearly full block has no room for a Sapling coinbase**: the node refuses
  (`coinbase-does-not-fit`) and the miner keeps its previous job until the next template.
- **koganyd's 99-block guard needs the non-finalized backup to survive a restart.** With the
  backup turned off (`state.should_backup_non_finalized_state = false`; it is on by default) a
  restarted koganyd has only its finalized blocks, no tip to keep, and follows its peers' best
  chain, where a ycashd would stop again. koganyd warns of this at every start with the backup off;
  keep it on wherever the node must be able to refuse a deep reorganisation.
- **koganyd's non-finalized backup files are written non-atomically** (as upstream Zakura writes
  them): a kill in mid-write can leave a short file, which the next backup counts as written.
- **koganyd**: not a qualified node line; no wallet in the node (yewd is the wallet, built from
  source); wrong argument counts answer `-1` where ycashd answers `-32602`; a miner must quote the
  price with `yed_setquote` where Yellowback is live; different peer scores for some invalid blocks
  (both lines refuse the same blocks); no built-in testnet peers (name `fastnet-seed.ycash.team:18833`);
  no Windows or Intel macOS build; Linux needs glibc 2.39; macOS binaries are not notarized.
- **yewd** differs from ycashd's wallet as its README lists (no `z_importviewingkey`,
  `z_exportviewingkey`, `listsinceblock`; its recovery phrase derives other transparent keys).
- **YecWallet**: unsigned by Apple; only the Apple-silicon package is tier 1.
- The other limitations of beta2 stand (ycash6 `doc/release-notes/release-notes-6.22.0-beta2.md`,
  "Known limitations").

## 9. Verifying the downloads

ycashd and YecWallet: `SHA256SUMS`, its keyless cosign bundle (identity: the repository's release
workflow at the tag), GitHub build provenance (`gh attestation verify`), and the Yellowback lead
architect's minisign signature `SHA256SUMS.minisig`
(`minisign -Vm SHA256SUMS -P RWQYr5PFpiPJAigk86vf89bPYrJCXj5tskgRAPRYFsEXyciZo8dveOGQ`). koganyd:
`SHA256SUMS`, cosign (`kogany-release.yml` at `refs/tags/v1.8.0-ycash.beta3`) and build provenance;
no minisign signature. Each release page carries the exact commands.
