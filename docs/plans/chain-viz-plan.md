# chain-viz plan — real-time x-ray of the chain and the Yellowback overlay

**Status:** revision 2, 2026-09-29. In implementation. Decisions C-1..C-8 confirmed and C-9..C-11
taken by the owner (§0). The checklists in §5 and the table in §9 are the status of record; agents
tick a box the moment the item is done, so anyone can read the state at any time.

chain-viz is the sixth component around the node: a **read-only sidecar** of `ycashd` that shows,
live, what the chain and the Yellowback (YED) overlay are doing — the mempool, the block sequence,
time since the last block, fork/orphan/reorg risk, the state of every enforcement mechanism, the
net flow of YED and collateral, and **who is being paid what** for participating. It is, in
effect, an advanced mempool and block explorer, because Yellowback lives in transparent UTXOs and
coinbase tags and is therefore entirely visible to a node that watches. It exists first for the
regtest and devnet simulations that harden the system (`role-based-regtest-plan.md`,
`role-pool-regtest-plan.md`), and second as the thing a pool operator or a prospective attestor
opens to see that the overlay pays.

## 0. Revision log

### Revision 2 (2026-09-29) — the owner's decisions; implementation begins

| # | Decision | Where |
|---|---|---|
| C-1..C-8 | **Confirmed as proposed** in revision 1, including C-4: Rust single binary with an embedded, build-step-free UI. | below |
| C-9 | **USD equivalents, priced by `pMint`.** Every YEC amount in the revenue view carries a USD figure computed with the protocol's own mint price at that height (`yed_gethistory[].pMint`, or the current `yed_getstats.pMint` for the mempool), labelled "at pMint". No external price feed. | §3.2.5 |
| C-10 | **A hosted public instance is wanted; where is undecided.** C7 therefore delivers the pieces any host needs (loopback bind + reverse-proxy note, a read-only mode with RPC credentials outside the snapshot, a rate-limited API, a static snapshot export) and leaves the host itself as an owner item, not a chunk. | §5 C7, §8 |
| C-11 | **The devnet auto-starts chain-viz.** `yellowback-devnet up` launches it on `devnet.json` when a `chain-viz` binary is found (`CHAINVIZ_BIN`, then `$PATH`), prints its URL, and `down` stops it; `--no-viz` opts out. Not a separate `viz` subcommand. | §3.4, §5 C4 |

### Revision 1 (2026-09-29) — first draft, from the owner's direction

| # | Decision (proposed; confirmed in revision 2) | Where |
|---|---|---|
| C-1 | **Own repository, app role, `main`.** `boyfromcave/chain-viz` is an `app` in `repos.yaml` like `yew` and `yolo`: no reference, no baseline, `make diff`/`make log` skip it. | §2.1, C0 |
| C-2 | **Strictly read-only.** chain-viz never holds a key, never builds or broadcasts a transaction, never calls a `yed_*` writer (`yed_setquote`, `yed_addattestation`, the wallet builders). Its node interface is the stock read RPCs, the read-only `yed_*` RPCs and the node's push channels (ZMQ, `-blocknotify`). A user who wants to act is sent to YecWallet or the CLI. | §4 |
| C-3 | **Zero node change to start; one optional Tier-0 RPC later.** Everything in §3 can be derived from RPCs the node already has. The one thing that is slow at scale — listing a block's Yellowback transactions — is done client-side (§3.2.3); a `yed_listblocktxs` read RPC is recorded as the single node ask (N-1) and is not scheduled. | §4.3, §7 |
| C-4 | **Rust backend, single binary, embedded frontend.** The collector is a Rust daemon (tokio + axum), the same shape and toolchain as `yolo/`, serving an embedded single-page UI over HTTP + WebSocket. No build step for the UI (vanilla ES modules + SVG; one vendored chart library). Rationale in §3.1; the alternative (Python, next to the devnet) is recorded there. | §3.1 |
| C-5 | **Many nodes, one view.** chain-viz connects to *N* nodes at once (all devnet seats; on mainnet one's own node plus any peers one runs) because fork, orphan and reorg risk is most visible as **tip disagreement between nodes**, which no single node reports. | §3.3 |
| C-6 | **Record and replay.** Every event the collector ingests is appended to a session log (`session.jsonl`) so a nightly regression run or a devnet incident can be replayed in the UI after the fact. This is what makes it a hardening tool rather than only a dashboard. | §3.6 |
| C-7 | **The revenue view is attributed, not estimated.** Fee outputs are attributed to their real payee from the transaction itself (`yed_gettxinfo` → `payee`, `attestPayee`), then rolled up per pool `payoutKey` and per attestor bond key. The counterfactual "what a non-participant forgoes" is computed from the same rows (§3.5) and labelled as such. | §3.5 |
| C-8 | **Devnet first, mainnet-safe by construction.** Phases C1–C6 are proven against `yellowback-devnet`; C7 hardens for a mainnet node (auth, TLS off-box, rate limits, `-txindex` awareness). No phase is mainnet-only. | §5, §6 |

## 1. The problem

The test suites are now robust: 24 `qa/rpc-tests/yellowback_*.py` functional tests, a nightly
`yellowback_devnet_roles.py`, a stratum test, a Python model of the state machine. They tell us
*whether* an invariant held at the end of a run. They do not show *how the chain behaved while it
ran*: how long the mempool held a vault spend before a pool included it, whether two pools briefly
disagreed on the tip, when the fast median crossed the mid median and flipped `pMint`, how far a
`--shock=-70%` price walk pushed vaults toward the 110 % claim line before the liquidator persona
acted, or why `rejectedBlocks` ticked from 0 to 1 at 03:14. Today that is reconstructed by hand
from eleven `debug.log` files and `sim.log`. The devnet's own `status` command prints text once
(`ycash-dd/contrib/yellowback/devnet/yellowback-devnet`, §5 of the survey below); nothing in the
workspace draws anything, streams anything, or keeps a timeline
(`lightwalletd-dd`'s Prometheus `/metrics` counts gRPC calls, not chain state).

Two audiences need that picture:

1. **Us, hardening the overlay.** A live, multi-node view of the chain and the index during a
   simulation, and a replay of it afterwards.
2. **Pool operators and prospective attestors**, who are asked to run patched software and post a
   bond. The pitch in `docs/why-miner-enforced.md` is that enforcement is paid for: an enforcement
   fee of `max(0.5 YEC, 0.25 % of collateral)` on every mint, redeem and claim goes to a key that
   published a quote tag in the last 100 blocks, and a further 25 % of that goes to an attestor
   once the attestor layer is armed. Nobody can currently *see* that money move. chain-viz must
   show, per block and cumulatively, the ordinary coinbase (subsidy + network fees) beside the
   Yellowback fees, per payout key, so the marginal revenue of participating is a number on a
   screen rather than a paragraph in a plan.

### 1.1 What "done" means

1. `chain-viz --nodes <devnet.json>` (or a list of RPC URLs) opens a page that, within one block,
   shows every §3 view populated from a running `yellowback-devnet up`, and keeps up with the
   15 s heartbeat, the price walk, the sim personas and a stratum pool without lag or a restart.
2. Fork, orphan and reorg events induced on the devnet (`yellowback_reorg_stress.py`'s recipe, a
   pool taken off-line and brought back with more work) appear on the block sequence as they
   happen, and the tip-disagreement panel shows which nodes are on which tip.
3. The Yellowback health panel reproduces, live, every field a `yellowback-devnet report` embeds
   from `yed_getinfo`/`yed_getstats`, plus the halt-mask, activation and arming state as a timeline.
4. The revenue panel attributes every enforcement fee and attestor fee output over a session to its
   payee, and its per-pool totals reconcile to the sum of `feeZat`/`attestFeeZat` over the same
   blocks' `yed_gettxinfo` rows (asserted by a test).
5. A session recorded on the devnet replays in the UI with no node running.
6. A pool operator can run the same binary against a mainnet `ycashd -yellowback` node with no
   change other than the RPC URL.

## 2. What exists

### 2.1 Repos

| Path | Role | State |
|---|---|---|
| `chain-viz/` | `app`, branch `main`, `https://github.com/boyfromcave/chain-viz.git` | `LICENSE` + one-line README (commit `8cfe353`). In `repos.yaml`, `make status`, the Makefile pins line, `.gitignore`, the VS Code workspace, README and AGENTS.md as of this revision (C0). |
| `ycash-dd/` | the node it watches | `feature/yellowback-price-attest`; no change needed (C-3) |
| `yolo/` | the pool; optional secondary source | `GET /status` JSON on `--status-port` (`yolo/src/status.rs`, `state.rs:101-116`) |

### 2.2 Data the node already exposes (survey, 2026-09-29, `ycash-dd` at `feature/yellowback-price-attest`)

**Push channels.** ZMQ is compiled in and unchanged from `ref/ycash` (`ycash-dd/src/zmq/*`;
`-zmqpubhashblock`, `-zmqpubhashtx`, `-zmqpubrawblock`, `-zmqpubrawtx` registered at
`src/init.cpp:487-490`). The devnet passes no `-zmq*` flag today. `-blocknotify` (`init.cpp:374`)
and `-txexpirynotify` (`init.cpp:415`) exist. There is **no Yellowback-specific push event**:
neither an index-applied/undone notification nor a rejected-block one.

**Chain RPCs** (all stock Ycash): `getblock` verbosity 0/1/2, `getchaintips`, `getmempoolinfo`,
`getrawmempool true` (per-tx size, fee, time, height, depends), `getnetworkhashps`,
`getmininginfo`, `getblocktemplate`, `getblocksubsidy` (`src/rpc/blockchain.cpp:1524-1531`,
`src/rpc/mining.cpp:1044-1049`). With `-insightexplorer -txindex`: `getblockdeltas`,
`getaddressdeltas` (`blockchain.cpp:1538-1539`).

**Read-only `yed_*` RPCs** (`ycash-dd/src/rpc/yellowback.cpp:1905-1930`; contract in
`ycash-dd/doc/yellowback-rpc-contract.json`), grouped by what chain-viz uses them for:

| Purpose | RPC | Notes |
|---|---|---|
| health + params, one call | `yed_getinfo` | tip, `healthy`, `enforcing`, `valveTripped`, `sunset`, `abandoned`, `rejectedBlocks`, `suppressedBlocks`, `activation{}`, `attest{}`, `miner{}`, every param. Works while the index is unhealthy. |
| supply, collateral, prices | `yed_getstats` | `supplyCents`, `collateralZat`, vault counts by status, `pFast/pMid/pSlow/pMint/pClaim`, `globalRatioBps`, `haltMask`, `mintingAllowed` |
| price at a height + the decoded tag | `yed_getprice [h]` | window fill, `xMint/xClaim`, `armed`, `seated`, pinned keys |
| timeline backfill | `yed_gethistory from to` | snapshot rows ≤ 2016 per call: prices, `signalCount`, activation, supply, collateral, ratio, `haltMask`, `blockHash` |
| activation detail | `yed_getactivation` | thresholds, `signalCount` history (8 rows) |
| who quotes | `yed_listminers [h window]` | one row per `payoutKey` with a tag in the window: last quote, count, eligible |
| tag of one block | `yed_gettag height\|hash` | 36-byte tag: `YED!`, version, flags (bit0 signal), `priceMicroUsd`, `sourceMask`, `payoutKey` (`src/yellowback/tag.h:16-31`) |
| vaults | `yed_listvaults [status count skip]`, `yed_getvault`, `yed_listclaimable`, `yed_getnotice` | paged, default 100 |
| tx attribution | `yed_gettxinfo txid` | type, path, verdict, `yedIn/yedOut/burned`, `feeZat`, `payee`, `attestFeeZat`, `attestPayee`, `residualZat`, `carrierVin` (`rpc/yellowback.cpp:319-368`) |
| payload decode, no index | `yed_decodepayload hex` | `feeVout`, `attestFeeVout` |
| mempool verdict | `yed_validaterawtransaction hex` | dry run at the tip; `wouldBeRejected` |
| why a block was rejected | `yed_getblockverdict hash` | |
| attestors | `yed_listattestors [h]`, `yed_getselection`, `yed_getfeepayee` | status, bond, seated/pinned, weight; E(R) and the default payee |
| tamper-evidence | `yed_getstatehash` | SHA-256 over all index tables; equal across healthy nodes on the same tip |

**Not available, and how chain-viz copes** (each is a row in §4.3):

- No RPC lists a block's Yellowback transactions or TxLog rows by height (`yed_listtokens` needs
  addresses). → chain-viz identifies Yellowback transactions itself from `getblock … 2` /
  `getrawmempool`+`getrawtransaction` by the payload's `OP_RETURN` marker, then calls
  `yed_gettxinfo` only for those (§3.2.3).
- No event on index disconnect/undo (`UndoDisconnect`, `src/yellowback/index.cpp:458`, logs only
  under `-debug=yellowback`). → derived from `getchaintips` + tip hash changes that are not
  child-of-previous (§3.3).
- Rejected blocks are a count plus a per-hash verdict. → chain-viz keeps the set of hashes it saw
  on any node's `getchaintips` that never became the main tip and asks `yed_getblockverdict` for
  each once (§3.3).

### 2.3 The devnet, as a data source

`ycash-dd/contrib/yellowback/devnet/yellowback-devnet` (Python, ~1.7 k lines) writes everything
chain-viz needs to find the nodes: `~/yb-devnet/devnet.json` carries `portseed`, the roles and a
per-node `rpc{url,port,user,password}` map (`yellowback-devnet:723-731`); `heartbeat.json`
(`{height,pool,time,rate,blockhash}`), `sim-stats.json` (per-persona ok/refused counts),
`mock-price` and `attest-price-N` (the walk's current prices) sit beside it. Plain `up` is 8
nodes (0 user, 1 stock, 2–4 pools, 5–7 attestors), `up --role …` is 11. Ports are computed by
`qa/rpc-tests/test_framework/util.py:48-94`; chain-viz reads `devnet.json` and never recomputes.
yolo's stratum status is at `21000 + (rpc − 16000) + 5000` (`yellowback-devnet:1041-1045`).

### 2.4 Revenue, as the protocol defines it (what the revenue view attributes)

From `docs/spec/yellowback-spec.md` and the v2/v3 plans:

| Flow | Amount | Paid to | Where in the tx | Source |
|---|---|---|---|---|
| Enforcement fee (FEE-1/2) on MINT, owner REDEEM, CLAIM | `max(0.5 YEC, 0.25 % × collateral)`; none if E(R) is empty (FEE-0) | `P2PKH(payoutKey)` for one key in E(R) = keys with a quote tag in (R−100, R], chosen by the builder's accuracy-weighted hash selection (FEE-W). **Not necessarily the block's miner.** | MINT `vout[3]`; REDEEM/CLAIM at the payload's `feeVout` | spec :184-198, :213-225, :369-383; `src/yellowback/math.h:185`; `state.cpp:338-345`, `:513-522` |
| Attestor fee (AFEE-1), only when ARMED | 25 % of the enforcement fee, in addition to it | `P2PKH(bondPubKey)` of one attestor in the bundle | `attestFeeVout` (MINT `vout[4]`) | spec :754-756, :808-820; `math.h:270`; `state.cpp:356-360`, `:524-533` |
| Network fee | 1 000 zat flat | the block's miner, as an ordinary fee | coinbase | spec :57 |
| Coinbase subsidy | stock Ycash | the block's miner | coinbase `vout` | `getblocksubsidy` |
| Claim / liquidation | claimant burns the debt in YED and takes the collateral; residual ≥ 100 000 zat back to the owner when ARMED (RED-5) | claimant / owner | vault spend outputs | spec :152-166, :909-917 |
| No-enforcement release | with enforcement off (sunset, valve, abandonment) the vault's `OP_TRUE` path lets whoever mines the spend take the collateral | the miner | vault spend | spec :160; `why-miner-enforced.md:140` |
| Attestor bond | earns nothing directly; ejection only (EQV-1), never slashed | — | `vout[0]` of ATTESTOR_REGISTER | spec :705, :995-997 |

The decisive point for the pitch: the fee goes to a **quoting** key, not to the block winner, so a
pool with 5 % of hashpower that publishes an honest tag every block is in E(R) for every fee in the
network, while a pool with 40 % that does not quote earns none of them. That is the number to show.

## 3. Design

### 3.1 Shape

```
chain-viz/
├── Cargo.toml                 one binary: `chain-viz`
├── src/
│   ├── main.rs                CLI: --nodes <devnet.json|url,…> --listen 127.0.0.1:8480 --record <dir> --replay <file>
│   ├── rpc.rs                 JSON-RPC client (auth from devnet.json / cookie / user:pass), retry, per-node rate limit
│   ├── zmq.rs                 optional: subscribe hashblock/hashtx per node when the node advertises -zmqpub*
│   ├── poll.rs                fallback: getbestblockhash + getrawmempool at --poll (default 1 s regtest, 5 s mainnet)
│   ├── model/                 the in-memory picture: chain.rs (blocks, tips, per-node heads), mempool.rs,
│   │                          yellowback.rs (health, prices, vaults, activation, arming), revenue.rs (ledger)
│   ├── classify.rs            Yellowback tx identification from raw tx (OP_RETURN marker) → yed_gettxinfo enrichment
│   ├── events.rs              the typed event stream every source produces and the UI consumes; session.jsonl codec
│   ├── server.rs              axum: GET / (embedded UI), GET /api/snapshot, GET /api/events?since, WS /ws
│   └── replay.rs              feed a session.jsonl into the model at wall-clock or accelerated speed
├── ui/                        embedded with include_dir!: index.html, app.js (ES modules), panels/*.js, vendored d3 (single file)
├── tests/                     fixture-driven: recorded RPC responses → model → asserted snapshots (no node needed)
└── qa/                        `regtest.sh`: bring up yellowback-devnet, run chain-viz, drive a scenario, assert over /api
```

**Why Rust rather than Python.** The devnet, the sim and the functional tests are Python, and a
Python collector would be quicker to start. But the deliverable is also something a pool operator
runs beside a mainnet node for weeks: one static binary with no interpreter, no venv and no
dependency on the workspace `requirements.txt` is the right shape for that audience, and `yolo/`
has already put the toolchain, the RPC-client patterns and the `tracing` conventions in place to
copy. The UI is deliberately build-step-free so that a contributor can edit `ui/app.js` and
reload. If the owner prefers Python (decision C-4), the layout above maps one-to-one onto
`asyncio` + `aiohttp` + `pyzmq` and the phases do not change.

**Why one process, many nodes.** Each configured node gets its own RPC client, poller and (when
advertised) ZMQ subscriber; all feed one event bus, tagged by node id. The model keeps a per-node
head and one merged block DAG. A single-node deployment is the degenerate case.

### 3.2 The views

Each view is a panel in one page; the layout is a fixed grid, phone-width down to a single column.
All charts follow the `dataviz` skill conventions (one system, light and dark).

#### 3.2.1 Chain — the block sequence

- **The DAG**, newest right: main-chain blocks as a row; side-chain and stale blocks hang below their
  fork point (`getchaintips`: `valid-fork`, `valid-headers`, `headers-only`, `invalid`). Each block:
  height, short hash, miner (from the tag's `payoutKey`, or the coinbase address when untagged),
  tx count, size, the tag's price and signal bit as a small badge, and a red edge if any node
  rejected it (`yed_getinfo.rejectedBlocks` delta + `yed_getblockverdict`).
- **Time since last block**, large, beside the target spacing (Ycash 75 s mainnet; the devnet
  heartbeat's `rate`), coloured past 2× and 4×.
- **Per-node heads**: one chip per configured node with its tip height and hash; chips that
  disagree with the majority are highlighted. This is the fork-risk indicator (C-5).
- **Reorg log**: every time a node's tip moves to a block that is not a child of its previous tip,
  an event `reorg{node, depth, from, to}` is recorded and shown; depth is the common-ancestor distance.
- **Risk gauges**, derived, labelled as derived: *fork risk* = number of nodes disagreeing × time
  disagreeing; *orphan risk* = blocks at the same height within the last window; *reorg risk* =
  max side-branch work within `branchlen` ≤ 6 (the work-valve depth, `index.cpp:575-600`), with
  the valve state overlaid, because a valve trip is exactly a reorg the enforcing nodes refused.

#### 3.2.2 Mempool

- Bubble/strip of `getrawmempool true` entries by fee rate and age; Yellowback transactions coloured
  by type (MINT, SEND, REDEEM, CLAIM, SWEEP, VOID, ATTESTOR_REGISTER, …) after §3.2.3
  classification; every other tx grey.
- Per Yellowback tx: `yed_validaterawtransaction` verdict at the current tip, so a vault spend that
  *would be rejected* by an enforcing node is shown red **before** a pool includes it — the miner-
  enforcement rule made visible.
- Counts and totals: tx count, bytes, fee total, and the YED value in flight (`yedIn/yedOut`).
- Time-in-mempool per tx, with the median shown; a Yellowback tx sitting longer than 2 blocks is
  flagged (a pool filtering it, or a fee below policy).
- Cross-node: a tx present on some nodes and not others is marked (propagation, or a stock node
  refusing a Yellowback tx it does not understand — the `stock_node` test's case).

#### 3.2.3 Yellowback transaction classification

A Yellowback transaction is recognised without the index by its payload output (the `OP_RETURN`
carrying the Yellowback payload; exact marker per `yed_decodepayload`'s contract in
`doc/yellowback-rpc-contract.json`). chain-viz scans each block's and each mempool tx's outputs
locally, and only for matches calls `yed_gettxinfo` (confirmed) or `yed_decodepayload` +
`yed_validaterawtransaction` (unconfirmed). Cost: one RPC per Yellowback tx, none per ordinary tx.
On a mainnet block of thousands of ordinary transactions this is a handful of calls. If it ever
is not, N-1 (§4.3) is the remedy, not a change here.

#### 3.2.4 Yellowback health

- **State ribbon**: `healthy`, `enforcing`, `valveTripped`, `sunset`, `abandoned`; activation
  `SIGNALING → LOCKED_IN → ACTIVE` with `signalCount/window` and the 75 %/60 %/50 % lines; arming
  `UNARMED → TRIGGERED → ARMED` with `seatedCount/poolSize`. Each is a stripe on a **timeline**
  (x = height) backfilled from `yed_gethistory` and extended live; state changes are events.
- **Halt mask** bits (`NOT_ACTIVE, NO_PRICE, PARTICIPATION, GLOBAL_RATIO, DIVERGENCE, ENFORCEMENT`)
  as a lane each; `mintingAllowed` as the summary.
- **Prices**: `pFast`, `pMid`, `pSlow` lines, `pMint` and `pClaim` as bands, the attestor `aMint`/
  `aClaim` when armed, the devnet's `mock-price` (the truth the walk is feeding) as a dotted line so
  lag and window fill are visible. Window fill per window (regtest 8/24/64; mainnet 96/576/2016,
  `src/yellowback/params.cpp:23-25, 190-192`).
- **Supply and collateral**: `supplyCents`, `collateralZat`, `globalRatioBps` vs the 110 % claim
  and 105 % emergency lines, `unbackedCents`; net change per block from the previous snapshot.
- **Vaults**: count by status (ACTIVE/VOID/CLOSED/CLAIMED); a scatter of ACTIVE vaults by ratio and
  blocks-to-`claimHeight`, with `yed_listclaimable` highlighted. This is where a `--shock` is watched.
- **Attestors**: `yed_listattestors` table with status, bond, seated/pinned, weight; equivocation
  reports and ejections as events.
- **Consistency**: `yed_getstatehash` per node; a mismatch between healthy nodes on the same tip is
  the loudest alarm on the page.
- **Rejected/suppressed** counters with the per-hash verdicts inline.

#### 3.2.5 Revenue — "what participation pays"

The ledger (`model/revenue.rs`) is a list of attributed outputs, one row per
`(height, txid, vout, kind, zat, payee)` with `kind ∈ {subsidy, netfee, enforcefee, attestfee,
collateral_release, residual}`, built from the coinbase (`subsidy`, `netfee`) and from the
`yed_gettxinfo` of every Yellowback tx (`feeZat`→`payee`, `attestFeeZat`→`attestPayee`,
`residualZat`→owner). The view:

- **USD (C-9)**: every YEC figure below is shown with its USD equivalent at that height's `pMint`,
  labelled "at pMint"; the mempool uses the current `pMint`.
- **Per block**: coinbase subsidy + network fees (what every miner already earns) beside the
  Yellowback fees paid in that block, and to whom.
- **Per pool `payoutKey`** over the session or a height range: blocks mined, tags published, times
  selected as fee payee, YEC earned from enforcement fees, YEC per tag, YEC per block mined,
  compared with the stock coinbase earned. `yed_listminers` supplies the tag counts and the
  eligible flag.
- **Per attestor bond key**: fees received, times selected, bond posted, fees ÷ bond as a running
  yield (labelled as realised, not promised).
- **The counterfactual for a non-participant** (C-7): for each fee output at height R, chain-viz
  knows E(R) (`yed_getfeepayee R collat`). A key that had quoted would have been one more member;
  its expected share under uniform selection is `fee / (|E(R)|+1)`, and the panel shows the sum of
  those over the range as "a quoting pool of any size would have expected ≈ X YEC in this range".
  Accuracy weighting (FEE-W) makes the realised figure for an honest quoter higher; the label says so.
- **Not enforced?** When `enforcing` is false, the ledger's `collateral_release` rows show who took
  vault collateral through the `OP_TRUE` path — the cost of not enforcing, made visible.

### 3.3 Fork, orphan and reorg detection without a push event

Per node, on each `hashblock` (ZMQ) or `getbestblockhash` change (poll):

1. Fetch `getblock <hash> 1`; if `previousblockhash` ≠ the node's last head → walk back until a
   known block; emit `reorg{depth}` if depth > 0 and the abandoned blocks are now `getchaintips`
   side branches.
2. Refresh `getchaintips`; any tip not seen before is a `sidechain_block` event; tips that later
   vanish are `orphaned`.
3. Poll `yed_getinfo.rejectedBlocks`/`suppressedBlocks`; a delta triggers `yed_getblockverdict` on
   each new side tip for the reason.
4. Merge: the DAG is the union across nodes; the "main chain" drawn is the majority head (ties →
   the most-work tip, as reported by `getchaintips`' `branchlen` ordering + `getblock.chainwork`).

### 3.4 Sources beyond the node (optional, each behind a flag)

- `--devnet <dir>`: read `devnet.json` for the nodes; read `heartbeat.json`, `sim-stats.json`,
  `mock-price`, `attest-price-N` for the devnet lanes (heartbeat rate, persona refusals, the
  price the walk is feeding).
- `--yolo <url>`: poll yolo's `/status` for `miners`, `templateAgeSeconds`, `accepted/rejected`,
  `lastSubmitVerdict`, drawn on the pool's chip.
- `--lightwalletd <url>`: scrape its Prometheus `/metrics` (default 127.0.0.1:9068) for request
  rates, drawn as a small lane, so a YEW/lightwalletd load test is visible beside the chain.

### 3.5 API

`GET /api/snapshot` — the whole model as JSON (what the UI loads on open).
`GET /api/events?since=<seq>` — the event log from a sequence number.
`WS /ws` — the same events, pushed.
`GET /api/revenue?from=<h>&to=<h>&by=payoutKey|attestor|block` — the ledger rolled up.
`GET /api/health` — for a nightly run to assert on (`yellowback_devnet_roles.py` can `curl` it).

The event schema (`events.rs`) is the contract between collector, UI, recorder and tests. It is
versioned; `session.jsonl` carries the version on line 1.

### 3.6 Record and replay

`--record <dir>` appends every event to `<dir>/session.jsonl` with wall-clock and height.
`--replay <file> [--speed 10]` runs the server from the file with no node, honouring inter-event
gaps ÷ speed; the UI is unchanged. `yellowback-devnet report` will bundle the session file (a
devnet change in `contrib/`, zero C++). The nightly regression keeps the last N sessions.

## 4. The interface contract with the node (read-only; AGENTS.md rule 2)

### 4.1 What chain-viz calls

| Channel | Methods |
|---|---|
| ZMQ (optional; the devnet will pass `-zmqpubhashblock`/`-zmqpubhashtx` per node — a `contrib/` change) | `hashblock`, `hashtx` |
| stock RPC | `getbestblockhash`, `getblock` (1, 2), `getblockhash`, `getchaintips`, `getrawmempool true`, `getrawtransaction`, `getmempoolinfo`, `getmininginfo`, `getnetworkhashps`, `getblocksubsidy`, `getblockchaininfo`, `getpeerinfo` (count only) |
| `yed_*` read | `yed_getinfo`, `yed_getstats`, `yed_getprice`, `yed_gethistory`, `yed_getactivation`, `yed_listminers`, `yed_gettag`, `yed_gettxinfo`, `yed_decodepayload`, `yed_validaterawtransaction`, `yed_getblockverdict`, `yed_listvaults`, `yed_getvault`, `yed_listclaimable`, `yed_getnotice`, `yed_listattestors`, `yed_getfeepayee`, `yed_getstatehash` |

### 4.2 What chain-viz never calls

`yed_setquote`, `yed_addattestation`, every wallet-table `yed_*` (`yed_mint`, `yed_send`, …,
`yed_registerattestor`, `yed_signattestation`), `generate`, `submitblock`, `sendrawtransaction`,
`getblocktemplate` (reserved to pools; not needed), any wallet RPC. A CI grep over `src/` for
these names fails the build (the same kind of gate the pool plan uses for the tag).

### 4.3 Gaps in the node surface, and their disposition

| # | Gap | chain-viz workaround | Node ask (Tier 0, RPC only; not scheduled) |
|---|---|---|---|
| N-1 | No RPC lists a block's Yellowback txs / TxLog rows by height | client-side classification (§3.2.3), one `yed_gettxinfo` per match | `yed_listblocktxs height\|hash` → TxLog rows |
| N-2 | No push event for index apply/undo/reject | derived from tips + counters (§3.3) | a ZMQ topic `yedevent` or a `-yellowbacknotify <cmd>` |
| N-3 | `yed_listtokens` needs addresses; no global token/UTXO set | supply from `yed_getstats`, flows from the ledger | a paged `yed_listalltokens` (also asked by the lightwalletd plan) |
| N-4 | Devnet passes no `-zmq*` flags | polling at 1 s is enough on regtest | `contrib/` only: add the flags per node (C4 does this) |

## 5. Work items and checklists

Chunks are sized for one agent each in the `yolo/`-style workflow (one repo, `main`, small
commits, `cargo test` green at every commit). Owner decisions C-1..C-8 gate C1.

### C0 — workspace plumbing (done 2026-09-29, workspace repo)

- [x] `repos.yaml` entry (`app`, `main`), Makefile pins line and `pins` target, `repo-status.sh`
      row, `.gitignore`, `yellowback.code-workspace` root, README components table/tree/pins,
      AGENTS.md layout and rule 2, this plan, `docs/plans/README.md` row.
- [x] `make status-short` shows `chain-viz … main ✔`; bootstrap dry run resolves it.

### C1 — collector core (agent `viz-core`, repo `chain-viz/`) — done 2026-09-29

- [x] Cargo skeleton mirroring `yolo/` (edition, `tracing`, `rust-toolchain.toml`, `clippy` clean).
- [x] `rpc.rs`: JSON-RPC over HTTP with basic auth from `devnet.json` or `--rpcuser/--rpcpassword`
      or cookie; per-node concurrency limit; typed responses for §4.1. (Cookie auth deferred to C7:
      the devnet and `--nodes` carry user/password; per-method call counters are in.)
- [x] `poll.rs` + `zmq.rs` behind one `Source` trait; `events.rs` schema v1.
- [x] `model/chain.rs`: block DAG, per-node heads, tips, reorg detection (§3.3) with unit tests on
      recorded fixtures (a 3-node fork, a depth-2 reorg, an orphan) — `tests/chain_model.rs`,
      `tests/fixtures/chain-{agree,reorg2,orphan}.json` recorded from a live devnet.
- [x] `model/mempool.rs`: entries with first-seen per node.
- [x] `server.rs`: `/api/snapshot`, `/api/events`, `/ws`, `/api/health`; `--record`.
- [x] Acceptance: against `yellowback-devnet up` (`--portseed 31`), `curl /api/snapshot` showed 8
      heads agreeing, a `mine 1` appeared as a `block` event 0.69 s after the command (poll 1 s),
      and a reorg induced on one node (`invalidateblock` of two blocks + `generate 3` from the
      recording script, never from chain-viz) appeared as `reorg{depth:2}` on every other node
      with the two abandoned blocks `orphaned`. The ZMQ source was verified by restarting the
      devnet's stock node by hand with `-zmqpubhashblock`/`-zmqpubhashtx` and running
      `chain-viz --zmq 1=tcp://127.0.0.1:28331 --poll 30`: the `block` event followed a
      `mine 1` by 0.21 s (the 30 s poll could not have caught it).

### C2 — chain and mempool UI (agent `viz-ui`, after C1's schema; can start on fixtures) — done 2026-09-30

- [x] `ui/`: page shell, theme tokens, WebSocket client with reconnect and snapshot resync.
      (`ui/index.html`, `style.css`, `lib.js`, `app.js`, `panels/{header,chain,mempool,events}.js`;
      vanilla ES modules + SVG, no vendored lib, no CDN; exponential backoff 0.5–15 s; `lagged`
      and reconnect resync via `/api/events?since=`; chain events refetch the snapshot, debounced.)
- [x] Block sequence panel (§3.2.1), per-node heads, time-since-block, reorg log, risk gauges.
      (Badges render `miner`/`tag{priceMicroUsd,signal}`/`rejected` when C3 supplies them, placeholders
      otherwise; gauges labelled "derived".)
- [x] Mempool panel (§3.2.2) without Yellowback colouring yet (colours by `yb.type` if present).
- [x] Events panel (tail, filterable by kind); `tests/ui_served.rs` (every embedded file 200 with its
      content type, shell references and ES imports resolve); `qa/ui-smoke.mjs` (fake-DOM run of the
      panels against a live server). `cargo test` + `clippy --all-targets -D warnings` clean.
- [x] Acceptance (devnet `--portseed 41`, heartbeat 15 s, `chain-viz --devnet`): `invalidateblock`
      tip−1 + `generate 3` on node 4 (via `yellowback-devnet cli --node 4 --`, never chain-viz)
      showed `reorg{depth:2}` on the other 7 nodes and the two abandoned blocks as `orphaned` in
      `chain.side`; the smoke check rendered them as 2 side blocks below the main row with 8 reorg-log
      rows. `pool 3 signal off` (a restart) produced `note "node 3: rpc transport …"` then `"node 3
      is back"` (the chip goes dim then recovers; the gap is sub-second). `invalidateblock` on
      node 1 without mining showed 1 chip disagreeing and the fork gauge lit; `reconsiderblock`
      recovered it within ~10 s. Two `sendtoaddress` txs drew 2 bubbles on all 8 nodes. No headless
      browser was available: verified with the smoke check + `curl /api/snapshot`, no screenshots.

### C3 — Yellowback health (agent `viz-yb`, after C1)

- [x] `classify.rs` (§3.2.3): the payload output (`OP_RETURN <push>`, magic `YB`, version 3, type
      byte; `src/yellowback/payload.cpp:364-408`) decoded locally, one `yed_gettxinfo` per match
      (claimed by one node task), `yed_decodepayload` + `yed_validaterawtransaction` in the mempool.
      Fixtures recorded from the devnet: mint, transfer, register, coinbases and plain spends
      (`tests/fixtures/yb-txs.json`, `plain-txs.json`); notice/equivocation/revive as synthetic
      bodies (the devnet does not produce them on its own; redeem/claim to be appended when the
      shock run yields them). `yb_tx` events, `yb` on mempool entries and `BlockInfo.yb{tag, miner,
      rejected, txs}`.
- [x] `model/yellowback.rs`: per node `yed_getstats` + `yed_getstatehash` per block; the leader
      (lowest-id non-stock node) adds `yed_getprice`, `yed_getactivation`, `yed_listminers`,
      `yed_listattestors`, `yed_listclaimable`, `yed_listvaults` paged when the vault counts change,
      and the one-time `yed_gethistory` backfill (2016-row pages, kept window); `yb_state` for
      `haltMask`, `mintingAllowed`, `activation.status`, `attest.status`, `attest.armed`; `price` /
      `stats` per block; `vault` / `attestor` status diffs; `statehash_mismatch` once per block
      hash between healthy nodes. Snapshot `yellowback{…}`; `GET /api/yellowback` for the panel.
      `--devnet`: `mock-price` and `attest-price-N` on the `price` event. Budget test
      `tests/yb_budget.rs` on recorded `rpcCalls`.
- [x] Health panel `ui/panels/health.js` + `health.css` (§3.2.4): state ribbon, timeline lanes
      (activation, arming, six halt-mask bits, rejected-block ticks), prices (pFast/pMid/pSlow,
      pMint–pClaim band, fed price dotted, window fill bars with minFill marks), supply/collateral
      tiles with per-block net change and the global-ratio line vs 110 %/105 %, vault scatter
      (ratio at pClaim × blocks-to-claimHeight, claimable ringed), attestor table, state-hash
      agreement + rejected/suppressed counters with verdicts, Yellowback tx table with
      `wouldBeRejected`. Self-contained (builds its own section; one import + one list entry in
      `app.js`), reads `GET /api/yellowback` once per block; passes `qa/ui-smoke.mjs`. Mempool
      colouring is C2's, keyed on `yb.type` (see C-F10 for the type-name mismatch).
- [x] Acceptance (2026-09-29, `up --role user --portseed 43 --sim-profile fast`, 11 nodes,
      `chain-viz --devnet --record`): `price --shock=-70%` (then `--shock=-25%`, walk stopped)
      raised `yb_state haltMask [] → [GLOBAL_RATIO, DIVERGENCE]` on every enforcing node at 281
      and the lanes filled; the global ratio fell 336 % → 115 %; after `mine 90 2` past the first
      underwater class-C vault's `claimHeight` it turned claimable (ringed in the scatter), the
      liquidator's CLAIM `d6739f14a5…` appeared in the mempool classified `redeem/claim`, verdict
      `ok`, `wouldBeRejected: false`, was mined at 437 (`claimedVaults` 0 → 1), its CLAIM_NOTICE
      `3530d9a9…` classified `notice`; both recorded into `tests/fixtures/yb-txs.json`.
      `yellowback-devnet report` at 444 agreed with `/api/snapshot.yellowback` on every field
      compared (supplyCents, collateralZat, globalRatioBps, haltMask, vault counts, pMint, pClaim,
      attestor statuses, quoting pools). State hash agreed on all 10 enforcing nodes. Budget
      fixture from the same run: 28 `yed_gettag` for 28 blocks, 10 `yed_gettxinfo` for 10 txs, one
      `yed_gethistory`. Note: mining 90 blocks on one node while the heartbeat mined on the others
      produced depth-43..86 reorgs on the other nodes (visible in the reorg log) — an artefact of
      the shortcut, not of the shock. `down --wipe` after.

### C4 — revenue ledger and panel (agent `viz-rev`, after C3)

- [x] `model/revenue.rs` (§3.2.5), rollups, `/api/revenue`, the counterfactual with its label.
      (2026-09-29, agent `viz-rev`, `wt/viz-rev` branch `c4-revenue`, unmerged.) Rows
      `(height, txid, vout, kind, zat, payee[, refHeight])`, `kind ∈ {subsidy, subsidy_other,
      netfee, enforcefee, attestfee, collateral_release, residual}` — `subsidy_other` added for the
      coinbase outputs that are not the miner's (Ycash regtest pays a 5 % YDF output at
      `getblocksubsidy.foundersaddress`; `netfee` = the miner's coinbase outputs − `miner`, no
      per-tx input lookups). Payee keys are addresses as the node spells them; a coinbase address
      is `scriptPubKey.addresses[0]` (else Base58Check-encoded from the P2PKH hex with the prefix
      learned from any node address); the tag's `payoutAddress` on the same block aliases the
      coinbase address to it (C-F23). `revenue` event per row (`entry` carries the ledger kind,
      C-F22), `revenue{totals, byPayee, aliases, window}` in the snapshot (cumulative, never
      evicted; per-height rows follow `--keep`). Counterfactual: `yed_getfeepayee R collat` once
      per `refHeight` (collat = the MINT's vault output, 0 for a redeem), Σ fee/(|E(R)|+1),
      labelled. USD at each row height's `pMint` (nearest row at or below), `priceLabel: "at pMint"`.
      `GET /api/revenue?from&to&by=payoutKey|attestor|block` → `{from, to, by, window, priceLabel,
      totals{<kind>{zat,usd,usdComplete}, blocks, ybTxs}, groups[…], counterfactual{zat, usd,
      feeOutputs, resolved, unresolved, noEligible, label, method}, noEnforcement{rows, total,
      label}, rows[≤5000], rowsTruncated, seq, tip, enforcing[], pMintNow}`.
- [x] Panel: per block, per pool, per attestor, counterfactual, no-enforcement releases.
      (`ui/panels/revenue.js` + `.css`, one import + one list entry in `app.js`; range selector
      last 50 / 200 / window; grouped thin bars stock coinbase vs enforcement + attestor fee per
      block with payees in the tooltip; pool table with blocks mined / tags / selected / fees
      YEC+USD / per tag / per block / stock coinbase / quoting status; attestor table with bond
      and realised yield labelled realised; counterfactual card with the label and method;
      release table. `qa/ui-smoke.mjs` asserts the pool rows and bar groups against
      `/api/revenue`. Not done: a browser screenshot of the panel.)
- [x] Reconciliation test: Σ ledger `enforcefee` over [a, b] = Σ `yed_gettxinfo.feeZat` over the
      same blocks' Yellowback txs; likewise `attestfee`. (`tests/revenue_reconcile.rs` on
      `tests/fixtures/revenue-blocks.json`, 37 devnet blocks (282–318, `up --role user
      --sim-profile fast --portseed 59`) recorded with `getblock 2`, `getblocksubsidy`,
      `yed_gettag`, `yed_gettxinfo`: 10 Yellowback txs including the exiter's owner REDEEM; also
      residual, the coinbase rows vs the coinbase outputs, per-pool sums, aliases, USD at a fixed
      pMint, and the release rows under enforcing = false. Live, twice: the same sums over
      262–283 (9 txs, mints only) and over 282–318 (10 txs incl. the redeem: 1.0 YEC enforcement
      fees, 0.125 YEC attestor fees, 131.25011 YEC coinbase, 37 blocks) agreed with
      `/api/revenue` field for field; `/api/revenue` also answered under `--public`. Budget on
      that run: 39 `getblocksubsidy` for 39 blocks, 2 `yed_getfeepayee` for 2 refHeights.
      `down --wipe` after.)
- [x] `contrib/` change in `ycash-dd`: the devnet passes `-zmqpubhashblock`/`-zmqpubhashtx` per node,
      `up` auto-starts chain-viz on `devnet.json` when a binary is found and prints the URL, `down`
      stops it, `--no-viz` opts out (C-11; Python only, zero C++). Done 2026-09-29, worktree
      `wt/devnet-viz` (branch `feature/chain-viz-devnet`, commit `3762d9f`), verified with a stub
      binary and a pyzmq subscriber; see C-F29..C-F32.

### C5 — devnet integration and the functional test (agent `viz-qa`, worktree of `ycash-dd`, after C4)

- [x] `qa/rpc-tests/yellowback_chainviz.py`: starts a 3-node regtest, runs the `chain-viz` binary
      (`CHAINVIZ_BIN`, skipped if unset, the way `yellowback_stratum.py` treats yolo), mines, mints,
      forces a reorg, asserts over `/api/health` and `/api/revenue` against the node's own RPCs.
      (2026-09-30, `wt/viz-qa-node` `038252fc9`; registered in `rpc-tests.py`, `YELLOWBACK_SCRIPTS`
      and a chain-viz checkout+build step exporting `CHAINVIZ_BIN`, `fb78a9b65`. Green locally
      against chain-viz `main` `9662694` (C4 merged) + branch `c5-fixes` (C-F25, C-F26); the
      `/api/revenue` assertion is unconditional since `a6d26c8b2`: `totals.enforcefee.zat` ==
      Σ `yed_gettxinfo.feeZat`, the `enforcefee` rows are the test's txs at their payees, `ybTxs`,
      the ledger's block window, `getblocksubsidy` in the budget.)
- [x] `yellowback_devnet_roles.py` gains an optional chain-viz session recording (`--record`).
      (`2fe3c47a9`: with `CHAINVIZ_BIN` set, `up` starts chain-viz with `--record` and the session
      file is copied to the test's output dir (kept with `--nocleanup`, as CI runs it); without
      it, `--no-viz`. Run 2026-09-30, `--presets user`: PASSED, session copied.)
- [ ] Acceptance: the test is green in the nightly (needs `c5-fixes` on chain-viz `main`); a
      recorded session replays — done locally 2026-09-30 (`--replay` of the test's `session.jsonl`,
      97/97 events, health `ok`, 3 nodes agreeing).

### C6 — record, replay, sessions (agent `viz-core`)

- [x] `replay.rs`, `--speed`, session versioning (done 2026-09-29, agent `viz-replay`, worktree
      `wt/viz-replay` branch `c6-replay`): `session.rs` owns the header (`version`, `chainViz`,
      `nodes`, `chain`, `started`) and the recorder; `--replay <file> [--speed N]` runs the server
      with no node from the same model and bus (`replay::apply` drives the chain and mempool models
      from events; `/api/health.replay = {file,pos,total,speed}`); a restart appends a new header to
      the same file. Round trip: `tests/fixtures/session-reorg2.jsonl` recorded from a live 8-node
      devnet (`--portseed 47`; mine 2, two blocks invalidated on node 3 and three mined there, one
      more block) replays to the same `chain.main`, tip, orphans and event count the live
      `/api/snapshot`/`/api/health` reported (`tests/replay.rs`); the binary was also checked at
      `--speed 0` and `--speed 10` and on a three-run file.
- [x] `yellowback-devnet report` bundles `session.jsonl` (done in the C4 devnet half, `ycash-dd` `3762d9f3d`).
- [ ] Acceptance: a nightly failure is diagnosed from its session file alone, once, and written up.

### C7 — mainnet hardening and packaging (agent `viz-core`, after C5)

- [x] `--poll 5s` defaults by network (from `getblockchaininfo.chain`); `-txindex`-less operation
      (`getrawtransaction` only for mempool txs and blocks fetched with verbosity 2). (2026-09-30, agent `viz-harden`, branch `c7-harden`: C1's `main.rs` already asks the first answering node; audit: `rpc::get_raw_transaction` has no caller at all, every block is `getblock … 1/2`; README "The node" says `-yellowback -experimentalfeatures`, no `-prune`, `-txindex` not needed. Cookie auth added beside it: `--cookie <path>` / `--datadir <dir>` (`src/auth.rs`, Ycash writes `.cookie` via `GenerateAuthCookie`, `ref/ycash/src/rpc/protocol.cpp:76`).)
- [x] Bind to loopback by default; `--listen` documented with a reverse-proxy note; no secrets in
      `/api/snapshot`; RPC credentials never logged. (2026-09-30: loopback default verified; README "Hosting" carries nginx + Caddy snippets and a warning is logged for a non-loopback `--listen` without `--public`; `RpcClient::scrub` replaces the node's address by `node <id>` in every transport error before it reaches `nodes[].error`, a `note` or the log (C-F19); `tests/hardening.rs` runs the binary with a password and hostnames that must not appear in `/api/health`, `/api/snapshot`, `/api/events`, stderr at `--log debug`, or an export.)
- [x] Hosting pieces (C-10): `--public` mode (API rate limit, no node credentials or hostnames in any
      response), `--export <dir>` writing a static snapshot the UI can open with no server. (2026-09-30: `src/public.rs` — per-IP token bucket 10 req/s burst 40 → 429, `X-Forwarded-For` honoured, WS cap 64 → 503, `/api/events` cap 2000, `public::redact` over every response and WS frame (URLs, `user@host`, `host:port`, paths; node ids stay); `src/export.rs` + `ui/static.js` — `index.html` rewritten to relative paths + `ui/data.js` (the three API answers as one global, so `file://` needs no fetch) + `ui/static.js` (answers `/api/*` from it, stubs WebSocket), `app.js` ends in conn state `static`; rewritten every 30 s and at shutdown; verified with `qa/ui-smoke.mjs <dir>` (static mode) and `python3 -m http.server`; C-F20.)
- [x] Release build in CI: `chain-viz/.github/workflows/ci.yml` (2026-09-29, agent `viz-replay`) — fmt, build, test, `clippy -D warnings` on ubuntu + macos stable on every push/PR; a `v*` tag builds linux x86_64 and macOS arm64 binaries and attaches them to the release (`yolo/` has no workflow to copy; written fresh).
- [ ] Acceptance: a run against a mainnet `ycashd -yellowback -experimentalfeatures` for 24 h with
      no RPC error storm and steady memory (blocks beyond `--keep 5000` are evicted from the model,
      the ledger rollups kept). **Not run: no mainnet node in this workspace.** What is in place
      (2026-09-30): eviction now also drops events below the floor from the `/api/events` window
      (`Bus::evict_below`, `ChainModel::floor`, `tests/hardening.rs`), and `qa/soak.sh` is the
      assertion (flat RSS, linear `rpcCalls`, no failure notes) — see C-F21 for the 22-minute
      devnet soak at `heartbeat rate 2` with `--keep 50`. The mainnet 24 h is the owner's to run:
      `chain-viz --nodes http://127.0.0.1:8832 --datadir ~/.ycash --public & qa/soak.sh http://127.0.0.1:8480 $! 1440 300`.

### C8 — docs

- [ ] `chain-viz/README.md`: run against the devnet, run against your node, what each panel means,
      what the revenue numbers are and are not.
- [ ] `docs/mapping.md` §18: the chain-viz findings (C-F rows) and the N-1..N-4 asks.
- [ ] This plan's §9 status table; the workspace README components row confirmed.

## 6. Sequencing

```
C0 ── C1 ──┬── C2 (UI shell, chain, mempool)
           └── C3 (health) ── C4 (revenue + devnet zmq/viz) ── C5 (qa) ── C7 (mainnet)
                                                           └── C6 (replay)      └── C8
```

C2 and C3 run in parallel from C1's event schema; C2 works on recorded fixtures until C3 lands.
Estimate: C1 3 d, C2 4 d, C3 4 d, C4 3 d, C5 2 d, C6 2 d, C7 3 d, C8 1 d ≈ 22 agent-days, of
which the C++ budget is **zero** and the `ycash-dd` delta is `contrib/` and `qa/` only.

## 7. Budgets and constraints

- **Node:** zero lines outside `contrib/yellowback/devnet/` and `qa/rpc-tests/`. N-1..N-3 are
  recorded, not scheduled; any one of them is a separate Tier-0 RPC commit with the four-part check.
- **Read-only:** §4.2 enforced by a CI grep in `chain-viz/`.
- **Load on the node:** per node, at most one `getrawmempool true` and one `yed_getinfo` per poll
  interval, `getblock` once per new hash, `yed_gettxinfo` once per Yellowback tx (cached by txid),
  `yed_listvaults` paged and refreshed only when `yed_getstats` vault counts change. Mainnet default
  poll 5 s. A budget test asserts RPC counts per block on the regtest fixture.
- **No consensus opinion:** chain-viz draws what the nodes say. Where nodes disagree it shows the
  disagreement; it never picks a "correct" chain beyond the majority-head rule for layout.
- **Naming:** Yellowback the system, YED the unit (AGENTS.md rule 6); no `digidollar` anywhere.
- **Not in scope:** shielded pools (Sprout/Sapling values are shown as opaque totals from
  `getblock`), address-level explorer search across history (needs `-insightexplorer`; a later
  option), alerts/paging (the health endpoint is what a monitor scrapes).

## 8. Open questions for the owner

1. Where the public instance (C-10) is hosted. Everything else in revision 1's list was decided in
   revision 2.

## 9. Implementation status

| Chunk | Status | Where |
|---|---|---|
| C0 workspace plumbing | done 2026-09-29 | workspace repo (`repos.yaml`, Makefile, scripts, README, AGENTS.md, this plan) |
| C1 collector core | done 2026-09-29, merged on `chain-viz` `main` and pushed | `chain-viz/src/{rpc,events,bus,collector,server}.rs`, `source/`, `model/{chain,mempool}.rs` |
| C2 chain + mempool UI | done 2026-09-30, merged on `main` and pushed | `chain-viz/ui/`, `tests/ui_served.rs`, `qa/ui-smoke.mjs` |
| C3 Yellowback health | done 2026-09-29, merged on `main` and pushed (with the C-F10 slot-map fix) | `chain-viz/src/{classify.rs,model/yellowback.rs}`, `ui/panels/health.js`, `tests/yb_*.rs` |
| C4 revenue + devnet zmq/viz | devnet half done 2026-09-29, merged on `ycash-dd` `feature/yellowback-price-attest` (`3762d9f3d`) and pushed; revenue half done 2026-09-29 (agent `viz-rev`, `wt/viz-rev`, branch `c4-revenue`, unmerged) | `chain-viz/src/model/revenue.rs`, `ui/panels/revenue.js`, `ycash-dd/contrib/` |
| C5 functional test | done locally 2026-09-30 (`wt/viz-qa-node`, branch `feature/chain-viz-qa`, 4 commits, unmerged; chain-viz `c5-fixes` in `wt/viz-qa-viz`, `9d1498e` on `main` `9662694`, unmerged); nightly acceptance open | `ycash-dd/qa/rpc-tests/yellowback_chainviz.py`, `.github/workflows/yellowback-tests.yml` |
| C6 record/replay | done 2026-09-29, merged on `main` and pushed; the nightly-diagnosis acceptance waits for C5's nightly | `chain-viz/src/{replay,session}.rs`, `tests/replay.rs`, `.github/workflows/ci.yml` |
| C7 mainnet hardening | done except the 24 h mainnet acceptance, 2026-09-30 (`wt/viz-hard`, branch `c7-harden`, unmerged) | `chain-viz/src/{auth,public,export}.rs`, `ui/static.js`, `tests/hardening.rs`, `qa/soak.sh`, README "The node"/"Hosting" |
| C8 docs | not started | `chain-viz/README.md`, `docs/mapping.md` §18 |

Findings (C-F rows) are appended here and mirrored to `docs/mapping.md` §18 as they arise.

### Findings

| # | Finding | Disposition |
|---|---|---|
| C-F1 | `devnet.json`'s `rpc.<n>.url` embeds the credentials as userinfo and they are non-ASCII (`rpcuser💻N` / `rpcpass🔑N`, `qa/rpc-tests/test_framework/util.py:185`). Python's `http.client` refuses the header (`latin-1`), reqwest percent-encodes it; either way the separate `user`/`password` fields are the ones to use. | `rpc::nodes_from_devnet` strips the userinfo and keeps `host:port`; the Authorization header carries the UTF-8 pair. Any other consumer of `devnet.json` (C5's test, yolo) should do the same. |
| C-F2 | Ycash 4.5 has no `getzmqnotifications` (`git -C ref/ycash grep` finds none), so a node's ZMQ endpoint cannot be discovered. | `--zmq <id>=<tcp url>` and an optional `zmq: {"<n>": "tcp://…"}` map in `devnet.json` (C4 writes it when it adds the `-zmqpub*` flags, N-4). Polling is always on; ZMQ only wakes the poller early. |
| C-F3 | `getchaintips` status is per node for the same hash: after `invalidateblock` on node 3, node 3 reports the majority's branch as `invalid` while the others call it `active`; a block that reached a node as a header only is `valid-headers` there and `valid-fork`/`active` elsewhere. And it lists tips only, never their ancestors. | The model keeps tips per node (`ChainSnapshot.tips`), never merges statuses, and knows a side branch's tip only (its parent stays unknown until some node's best chain walks through it). |
| C-F4 | A competing block that arrives as a header only moves no node's head, so refreshing `getchaintips` only on head changes misses it; refreshing every poll is wasteful on mainnet (`getchaintips` walks the whole block index, `src/rpc/blockchain.cpp:1214`). | The collector refreshes tips on every head move and every 10 polls otherwise (`collector::TIPS_EVERY`). |
| C-F5 | Eight collectors starting against an empty model each walked the 20-block backfill (8 × 21 `getblock`). | The first fetch per node is serialized behind one mutex; only the first node walks, the rest find their head known (21 + 7 × 1 `getblock` on the devnet). |
| C-F6 | There is no push for raw transactions the devnet uses (`-zmqpubrawtx` is not passed), so a mempool tx's outputs cost one `getrawtransaction` — for every tx, Yellowback or not; the payload scan itself is free. | One `getrawtransaction` per txid across all nodes (`YellowbackModel::check`), on whichever node reports it first; a stock node keeps the raw hex so a `yed_*` node can run `yed_decodepayload` + `yed_validaterawtransaction` later without a second fetch. |
| C-F7 | Eleven node tasks each fetch the tip and each would enrich it: the first live run spent 135 `yed_gettag` on 26 blocks and ten `yed_gethistory` backfills, because "is it tagged yet" was checked before the RPC and the leader was "the first node that is up" — a race eleven first polls all win. | A block hash / txid is *claimed* under the model lock before the RPC (`YellowbackModel::claim/release`), and the leader is deterministic: the lowest-id node not known to be stock or down, which every task agrees on from the start. The budget test asserts Σ`yed_gettag` ≤ blocks + 2 and Σ`yed_gethistory` ≤ pages + 1. |
| C-F8 | The serialized first backfill (C-F5) is walked by whichever node's task runs first — the stock node as often as not — and a stock node can classify (payload scan) but not enrich (`yed_gettag`, `yed_gettxinfo`), so the first 20 blocks stayed untagged. Likewise a node's `yed_*` capability was only learned *after* its first block walk. | `ChainModel::untagged()` + `Collector::enrich_pending`: every `yed_*` node sweeps up to 8 unenriched blocks per poll; and the first step probes `yed_getinfo` before the block walk (one extra call per node, once). |
| C-F9 | The two ratios on the page are priced differently by the node: `globalRatioBps` uses **pMint** (`src/yellowback/math.h:162`, `state.cpp:1219`), while a vault is claimable below **pClaim** (`UnderwaterAt`, `rpc/yellowback.cpp:218`: `collateralZat · pClaim < mintedCents · 11000 · COIN`). After a shock pMint (fast-tilted) falls first, so the global-ratio tile can read 115 % while every vault still sits at 300–500 % at pClaim and `yed_listclaimable` is empty — not a bug, the slow window. | The health panel prices the scatter at pClaim (`vault_ratio_bps`) and says so beside the tile's "at pMint"; the two are expected to disagree for ~one slow window after a move. |
| C-F10 | `ui/lib.js`'s `YB_TYPE_SLOT` keys are `MINT, SEND, REDEEM, CLAIM, …` but the node's `type` strings (`TypeLower`, `rpc/yellowback.cpp:126-138`; `PayloadTypeName`, `payload.cpp:432-442`) are lowercase `mint, transfer, redeem, register, notice, equivocation, revive`, and a CLAIM is a `redeem` with `path: "claim"`. C2's mempool colouring therefore falls to the default slot for every tx. | `health.js` carries its own map on the node's names (`TYPE_SLOT`, claim = redeem + path); C2 should key `YB_TYPE_SLOT` the same way (one-line change, not made here: `ui/lib.js` is C2's). |
| C-F11 | Payloads longer than 75 bytes (ATTESTOR_REGISTER 75 → fits; ATTESTOR_REVIVE 78) are pushed with `OP_PUSHDATA1`, not a direct push, and `ExtractOpReturnData` accepts PUSHDATA1/2/4 as long as the script ends with the push. | `classify::op_return_data` mirrors all four push forms and the 4..80 bound; the fixture test covers PUSHDATA1. |
| C-F12 | `mempool_add` is emitted once per txid (the first node to report it) and `mempool_remove` once (when no node holds it any more); a tx appearing on or leaving a further node emits nothing, so the §3.2.2 cross-node mark cannot be kept from events alone. | The UI applies add/remove incrementally and refetches `/api/snapshot` (debounced 400 ms) on every mempool event to refresh `present`. A per-node `mempool_seen{node,txid}` event would remove the refetch (C6/C7 candidate). |
| C-F13 | A page opened after a reorg sees nothing of it: the first resync starts at the snapshot's `seq`, and the snapshot carries no reorg history. | `app.js` pulls `/api/events?since=0` once per page load (the bus keeps 100 000 events, `main.rs:166`) and applies it as logs only (reorg log, rejected set, `yb` map), never mutating the snapshot. |
| C-F14 | `reorg` is per node, so one devnet reorg is 8 events; the reorg log shows 8 rows for it. | Kept as the plan defines (`reorg{node,depth,from,to}`); grouping rows by `(from,to)` is a UI nicety for later. `fork risk` clocks disagreement from the moment the page first sees it (a fresh page shows `1 × 0 s` for a fork that is minutes old). |
| C-F15 | The devnet's `cli` syntax is `yellowback-devnet cli --node N -- <rpc> [args]` (`args` is `REMAINDER`; without `--node` it targets the user node), and a pool restart is `pool N signal off|on` (`restart_node`), which takes well under a second — too fast for a 3 s health poll to catch `nodesUp` dipping. | Recorded for C5; the transition is still observable as the pair of `note` events. |
| C-F16 | `session.jsonl` lines could land out of `seq` order: the bus took `seq` from an atomic and wrote the line under a different lock, so two collectors publishing at once (8 nodes reporting the same tip) interleaved (seq 33, 34 before 32 in a first recording). | `Bus::publish_at` takes `seq` and writes the line under the log lock; `session::read_session` also stable-sorts each run by `seq` for files written earlier. |
| C-F17 | `EventKind::DevnetHeartbeat(Value)` (and every other `Kind(Value)` variant) is flattened into the envelope, so a value carrying `height` wrote the key twice: the line is not valid JSON for a strict decoder (`duplicate field height`) and killed replay of that file. | The collector strips `seq`/`ts`/`height`/`node`/`kind` from devnet values before publishing; the reader parses each line as a JSON value first (last key wins) and skips a line it still cannot decode (a torn last line after a crash) with a warning. Rule for C3/C4: a `Kind(Value)` payload must not carry those five keys. |
| C-F18 | Parallel worktrees share `$CARGO_TARGET_DIR` (`~/.cargo/shared-target`): another agent's `cargo build` replaced `debug/chain-viz` between two of this chunk's end-to-end runs (the replay run then said `--replay is not implemented yet`). And a binary copied out of the target dir and overwritten while a copy was executing left the processes stuck in macOS `UE` state (kill -9 has no effect). | Build the binary under test with a private `CARGO_TARGET_DIR` (12 s incremental after the first build); never re-copy over a running binary. |
| C-F19 | reqwest's transport errors quote the request URL (`error sending request for url (http://host:port/)`), so an unreachable node's address reached `nodes[].error`, the `note` event, `session.jsonl` and the log — and, with `--nodes http://user:pass@…`, would have carried the credentials had `node_from_url` not split them off first. | `RpcClient::scrub` replaces the node's URL and `host:port` by `node <id>` in every transport error; `--public` additionally redacts any URL/`host:port`/path-shaped string in every response and WS frame (`public::redact`), since devnet `heartbeat.json`/`sim-stats.json` and `--replay`'s file name are operator paths. `RpcClient`'s `Debug` prints the id only. |
| C-F20 | An `--export` cannot be a plain copy of `ui/`: `app.js` fetches absolute `/api/…` and opens `/ws`, and Chrome refuses module scripts from `file://` while also refusing `fetch` of a sibling file there. | The export rewrites `index.html` to relative paths and loads `ui/data.js` (the three API answers as one global) then `ui/static.js` (answers `/api/*` from it, stubs `WebSocket`) before the app module; `app.js` checks `window.CHAIN_VIZ_STATIC` and skips `connect()` (conn state `static`). Works from any static host; from `file://` only where module scripts are allowed (Firefox). `qa/ui-smoke.mjs <dir>` is the node-free check. |
| C-F21 | `yellowback-devnet up --heartbeat-rate 2` records the rate but does not start the heartbeat on the plain (no `--role`) devnet: `heartbeat status` says `never started`. | `heartbeat start` then `heartbeat rate 2` after `up`. Soak (`qa/soak.sh`, 22 min, 30 s samples, `--keep 50 --public --export --record`, 8 nodes, one block per 2 s): result: 44 samples, RSS 16.8 MB at the first-quarter mark, last-half max 16.4 MB, final 14.1 MB (flat — the floor evicted ~600 blocks and their events); `rpcCalls` +937 per 30 s median, min 914, max 971, no outliers; one host-wide blip at 02:02:33 (all 8 nodes failed one request within 40 ms, all "back" 1 s later, 8 notes) and nothing else, so the soak's failure criterion became per node and per interval (≤ 2 intervals with notes, ≤ 3 notes per node) rather than a flat count. |
| C-F22 | The plan's `revenue{height,txid,vout,kind,zat,payee,usd}` cannot carry a `kind` field: `EventKind` is `#[serde(tag = "kind")]`, so `kind` is the event's own name (`revenue`) and a second `kind` would collide in the flattened envelope. | The ledger kind travels as `entry` (`subsidy`, `netfee`, `enforcefee`, …); `height` is the envelope's. `/api/revenue` rows and the fixture keep `kind`. |
| C-F23 | A pool's coinbase does not pay its `payoutKey`: the devnet's pool nodes mine with `generate`, whose coinbase goes to a fresh wallet key every block (`smaRSw…`, `smYNwQ…`, …), while the tag's `payoutAddress` (`-yellowbackpayoutaddress`) is fixed; `getblock 2` carries `scriptPubKey.addresses`, so the address is readable but rolls up nowhere on its own. | `RevenueModel` aliases the coinbase address to the tag's `payoutAddress` seen on the same block (`on_tag`), so blocks mined, subsidy and net fees roll up under the quoting key; `/api/revenue` groups list their `aliases`. On the devnet that is one alias per block (the map is never evicted; ~60 B per block); a mainnet pool reuses one address. A block without a tag stays under its coinbase address. |
| C-F24 | `yed_getfeepayee` refuses `refHeight` above the index height or below `startHeight`, and answers `fee-no-eligible-payee` (FEE-0) when nobody quoted in the window — an RPC error, not an empty list. And the enforcement-fee tx's `refHeight` is only in its payload (`classify::Payload.ref_height`), not in `yed_gettxinfo`. | The collector asks once per `refHeight` the ledger's fee rows name, on the node that enriched the tx, remembers a refusal as "no eligible payee" (never re-asked), and the counterfactual reports `resolved` / `unresolved` / `noEligible` counts beside the sum. |
| C-F25 | `#[serde(default)]` covers a missing key only, not an explicit `null`, and the node renders an undefined price or ratio as `null` (`PriceOrNull`, `src/rpc/yellowback.cpp:424`): on a fresh regtest `yed_getstats.globalRatioBps` is `null` until the first vault, so every node's step failed (`rpc protocol: yed_getstats: invalid type: null, expected i64`), all three nodes showed `up: false`, `/api/health.ok` was `false` and nothing was enriched — chain-viz was blind on any chain without a vault. The devnet never showed it because its personas mint before chain-viz starts. | `rpc::null_default` (`Option<T>` → default) on `YedStats`'s `globalRatioBps` and `p*` fields, chain-viz branch `c5-fixes` (`wt/viz-qa-viz`, `9d1498e`, rebased onto `main` `9662694`); to merge. Rule for every typed `yed_*` struct: a field the node can render as `null` takes `null_default` or `Option`. |
| C-F26 | `--nodes a,b,c` numbered the nodes 0, 2, 4: `id = nodes.len() + i` while pushing into `nodes`. `--zmq 1=…` then matched nothing and `rpcCalls`/`snapshot.nodes` were keyed 0/2/4. `--devnet` was unaffected (ids come from `devnet.json`). | Same commit: the count is taken once before the loop. |
| C-F27 | `/api/health` can say `agreeing: 3` with `nodesUp: 2`: a node's head moves inside its step and `up` is set after the step returns, under a second model lock. | The test waits for `tip == getbestblockhash`, `agreeing == N` **and** `nodesUp == N` before asserting; a reader that keys on one of them alone sees a window of a few ms. |
| C-F28 | The RPC budget of §7 needs the wake rule to be checkable: the collector fetches the mempool on every wake, and a wake is a poll tick, a ZMQ `hashblock`, or a ZMQ `hashtx` — which ycashd publishes once per transaction entering the mempool **and** once per transaction of every connected block, coinbases included. A `reorg` event's `to` is whichever new block the node's poll caught (the first of three, as often as the last). | `yellowback_chainviz.py` bounds `getrawmempool ≤ seconds + blocks since start + txs in those blocks + mempool arrivals + 2`, `getblock ≤ blocks since start + 20 backfill + 2`, `yed_gettxinfo ≤ Yellowback txs` per node and in total; the observed run: 30/30/33 `getrawmempool` for 38 wakes, 30/10/11 `getblock`, 1/1/0 `yed_gettxinfo` for 2 txs. `to` is asserted to be one of the new blocks. |
| C-F29 | **ycashd shares one ZMQ PUB socket per address**: `-zmqpubhashblock` and `-zmqpubhashtx` given the same `tcp://` URL publish both topics on one socket (`src/zmq/zmqpublishnotifier.cpp`, "Reusing socket for address"). One port per node suffices; a subscriber on it received the `mine 1` tip hash and the coinbase txid. | The devnet uses one endpoint per node, both URLs in `nodes[n].zmq` equal. chain-viz's `--devnet` reader must tolerate (and should dedupe) equal `hashblock`/`hashtx` URLs. |
| C-F30 | **No `getzmqnotifications` RPC in Ycash 4.5**, and the zmq log lines are `LogPrint("zmq", …)` — silent in `debug.log` unless `-debug=zmq`. | The proof of the flags being accepted is `lsof -iTCP:<port>` (every ycashd binds its zmq port) or a subscriber; not the log. Documented in the devnet README §5. |
| C-F31 | **No 5000-wide port band is left below 32768.** The framework spreads a portseed over 4991 ports, and p2p/rpc/stratum/status already take 11000–31000; a band above 32768 would repeat the CI collision that moved stratum off 30000. | The zmq band folds the seed: `31000 + 12 * (seed % 140) + n` (31000–32679); chain-viz `32680 + seed % 88`. Two devnets whose seeds agree modulo 140 (or 88) collide there while their rpc ports do not — the README's port table says so. `yellowback_devnet_roles.py`'s presets use `portseed + 100, +103, +106`, which never agree modulo either. |
| C-F32 | `devnet.json` had no per-node map beyond `rpc` (keyed by node string). | Added a top-level `nodes` map, `nodes["<n>"].zmq = {hashblock, hashtx}`, keyed the way `rpc` is; `rpc` untouched. `chainviz = {pid, url, port, log, binary, pid_file, record}`. |
