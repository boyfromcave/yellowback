# Pool demonstration: four miners, three kinds of address (beta3 step D-1)

Copyright (c) 2026 The Ycash developers.

**Revision 1 (2026-11-16): the runbook, prepared; nothing in it has been run.** The coordinator
follows it in Wave 5 after T-1..T-4 (`beta3-plan.md` §5) and fills in §9; from then on it is the
record of beta3's second success criterion (`beta3-plan.md` §1, §9). Places where the repositories
did not settle a fact are marked **[CHECK]** and listed again in §8: the coordinator resolves each
before the step that needs it.

Sources, at the commits read: the plan (`beta3-plan.md` §1, §2.1, §5 Wave 5, §8, §9), the design note
(`getcoinbasetemplatefor.md` §5, §6, §8), yolo `upgrade/vault` `b3abf81` (README, CHANGELOG,
`src/stratum.rs`, `src/pairs.rs`), ycash-infra `upgrade/vault` `dbab91c` (`infra/vast-miners/README.md`,
`images/miner/README.md`, `infra/testnet-seeds/nodes/` and its `seedctl`, `scripts/vast-fleet.py`),
ycash-ops `main` `e72c77c` (`.github/workflows/miners.yml`, `miners/fleet.json`, `testnet-pools/`,
`docs/testnet-pools.md`, `docs/testnet-lightwallet.md`), ycash6 `upgrade/vault` `3ed5a96c2`.

## 0. What is shown, and the order

The yolo pool at `fastnet-pool.ycash.team:3333` pays **four rented miners at once**, each at its own
address: one transparent (`sm…`), two Sapling (`ytestsapling1…`), one post-quantum (`tqf…`). Each
finds blocks whose coinbase pays that miner the **block subsidy plus every fee in the block**, with
no development-fund output (the fund default is 0 in beta3 and the fast testnet's mandate has ended).

| # | Step | Section | Spends |
|---|---|---|---|
| 1 | The one-card username check (may run now, against today's pool) | §3 | about $0.02 to $0.09 |
| 2 | The demonstration wallet: node, four payout addresses, spare addresses funded | §2 | nothing |
| 3 | Preconditions P-1..P-11, each ticked with its command's output | §1 | nothing |
| 4 | The four-miner burst, fee-paying transactions during it, the live watch | §4, §5 | about $0.24 to $0.36 |
| 5 | Evidence: the acceptance table, Sapling notes in the wallet | §4.6, §5 | nothing |
| 6 | Teardown and the budget ledger | §6 | nothing |

Budget: the Yellowback lead architect approved **$10 in total on vast.ai** for this (the one-card
check included). The whole plan above stays under $1, with room for one repeat of each paid step.

## 1. Preconditions

Each is checked by a command; paste the output (trimmed) into §9. Shorthands used below:

- **deploy `<layer>` `<action>`**: ycash-ops Actions, workflow `deploy`, inputs `layer`, `network`
  `yb-fast` (or `all`), `action`. **miners `<action>`**: workflow `miners` (§3, §4).
- **On a host (SSM):** `aws ssm start-session --target <instance id>` with the coordinator's admin
  credentials (ycash-ops README, "Shell on a seed host"), then
  `HCLI='sudo docker exec ycashd-yb-fast ycash-cli -datadir=/var/lib/ycash -conf=/var/lib/ycash/ycash.conf'`
  followed by the node's own network flags (`seedctl`'s `cli()` appends `.node_args` from
  `/…/yb-fast/applied.json`; **[CHECK]** copy them from there, they should be `-testnet
  -testnetprofile=fast`). These are AWS calls: the coordinator's.
- **Demo node:** `DCLI='<beta3 bin>/ycash-cli -datadir=/Users/boy/ycash-fastnet-demo/data -testnet -testnetprofile=fast -rpcport=18862'`
  (the demonstration wallet's own node, §2; started by the coordinator, so its own to query).

| # | Precondition | Check | Pass |
|---|---|---|---|
| P-1 | **Every fast-testnet node runs beta3** (T-2's checklist) | below, node by node | every row's image digest or version is the T-1 candidate's |
| P-2 | **The mandate end `H_END` is crossed and agreed** (T-4) | below | every node has the same hash at `H_END`; that block has no fund output |
| P-3 | **The pool's node runs without `-ydf=5`** (after P-1 only) | `testnet-pools/nodes/main.tf` and the running node | no `-ydf` in the args; `getblocksubsidy <tip+1>` `founders` 0 |
| P-4 | **The pool is in per-miner (paired jobs) mode** with the beta3 yolo | below | yolo started without `--payout`, with `--coinbase-concurrency 2 --max-paired-per-ip 8`; `/status` `"payout":"username"`, `"coinbaseCall":true` |
| P-5 | **`getcoinbasetemplatefor` answers on the pool's node** for all three kinds | below | three answers, `fundrule` `"none"`, `fund` 0, `amount` = subsidy + fees |
| P-6 | **The pool host has CPU to prove** | `local.cpu_credits` in `testnet-pools/nodes/main.tf` | `"unlimited"` for the run (§5.2) |
| P-7 | **The light-wallet node has its four peers** (the 2026-11-16 loss) | deploy `lightwallet` `status` | `peers` ≥ 4 and `lightwallet.node.connections` ≥ 4; `phase` `serving` |
| P-8 | **The demonstration wallet is synced, its four addresses recorded** | §2 | `DCLI getblockcount` = the seeds' `blocks`; four addresses in §9 |
| P-9 | **The fee sources hold coins** | §4.5 | each spare address has a confirmed, non-coinbase balance |
| P-10 | **The one-card check passed** (or its fallback is in place) | §3 | the 88-character username reached yolo whole |
| P-11 | **No miner is rented and no burst is active** | miners `status`, network `fast` | no `ycash-fast-*` instance; `MINERS_ENABLED` as the coordinator left it |

### P-1: the node checklist

| Node | Where | How to read its version | And `rpcversion` |
|---|---|---|---|
| Seed host 1, `yb-fast` | AWS, layer `seeds` | deploy `seeds` `status`: `image` = the T-1 digest; SSM: `$HCLI getnetworkinfo \| jq .subversion` | see below |
| Seed host 2, `yb-fast` | AWS, layer `seeds` | as above (two hosts, one `yb-fast` container each) | |
| Pool host | AWS, layer `pools` | deploy `pools` `status` | |
| Explorer host (`fastnet-explorer.ycash.team`) | AWS, layer `explorer` | deploy `explorer` `status` | |
| Light-wallet host (`fastnet-lightwallet.ycash.team`) | AWS, layer `lightwallet` | deploy `lightwallet` `status` | |
| Local ycashd (the lead architect's), RPC 18842 | `/Users/boy/ycash-fast-sync` | `getnetworkinfo` `subversion` (the lead architect restarts it, or says who may) | |
| Local koganyd, fast testnet | `/Users/boy/kogany-fast-explorer` | its `getinfo` / `getnetworkinfo` `subversion` (`v1.8.0-ycash.beta3`) | |
| Local explorer ycashd | `/Users/boy/ycash-explorer` | **[CHECK]** whether it follows the fast testnet at all; if so it is on the checklist | |
| The demonstration node | `/Users/boy/ycash-fastnet-demo` | `$DCLI getnetworkinfo` | |

**`rpcversion` 10.** `yed_getinfo` is the only call that reports it (`ycash6 src/rpc/yellowback.cpp`,
`YELLOWBACK_RPC_VERSION`), and it refuses with `Method not found (Yellowback is not active: the vault
upgrade or the YED attestor set is not configured on this network)` where no attestor set is
configured, which is the fast testnet's state (`beta3-plan.md` §2.1, item 17's acceptance).
**[CHECK]** Try `yed_getinfo | jq .rpcversion` once on one node. If it refuses, the version is
proven instead by (a) the image digest equal to the T-1 build of the candidate commit (the
`node-image` run that built it, recorded in §9), (b) `subversion` naming 6.22.0-beta3, and
(c) `help getcoinbasetemplatefor` answering (beta3 only).

### P-2: the mandate end

`H_END` is the value compiled at the beta3 cut (`TESTNET_FAST_YDF_MANDATE_END_HEIGHT`, ycash6 and
ycash-dd `src/chainparams.cpp`; koganyd `mandate_end::TESTNET_FAST`; `releases/v6.22.0-beta3.yaml`
names the cut commit). **[CHECK]** The tree still carries the provisional 600,000; the
demonstration needs the cut's value (B3-D4, the tip at the cut plus 400). If beta3 shipped with
600,000 the fast testnet would need about 88,000 more blocks and the coinbases would keep the 5 %
fund output: criterion 2's "no development-fund deduction" could not be shown. Stop and ask.

```bash
H_END=<from the cut commit>
$DCLI getblockcount                                   # ≥ H_END
$DCLI getblockhash $H_END                             # the same hash on every P-1 node
$DCLI getblock "$($DCLI getblockhash $H_END)" 2 | jq '.tx[0].vout | length'
$DCLI getblocksubsidy $((H_END-1)) | jq .founders     # 0.3125 (mandated, 5 % of 6.25)
$DCLI getblocksubsidy $H_END | jq .founders           # 0 on a node at the default -ydf
```

The `vout` count at `H_END` is 1 only if the pool's node had already dropped `-ydf=5` (T-4 says the
first block without a fund output is accepted by every node; it need not be at `H_END` exactly).
Record the first height without a fund output and that every P-1 node holds it.

### P-3 and P-4: the pool's configuration, and what must change first

Where it lives: ycash-ops `testnet-pools/nodes/main.tf` (the `pool` object of
`networks.yb-fast`, the node's `extra_args`, `local.pool_image`), which calls ycash-infra's
`infra/testnet-seeds/nodes` module at `testnet-pools/infra.ref`; the module renders yolo's command
line in `files/seedctl`, `render_pool()`.

**[CHECK] — a gap, not yet staffed: the module has no per-miner mode.** At ycash-infra
`upgrade/vault` `dbab91c` the `pool` object requires `payout` (`variables.tf`), and `render_pool()`
always passes `--payout "<pool.payout>"`, with `--max-connections 64 --max-per-ip 4`, and has no
way to pass `--coinbase-concurrency` or `--max-paired-per-ip`. Its status filter
(`pool_status()`) drops `minersByKind`, `minerList`, `coinbaseCall` and `pairs`. No open branch
changes this. T-3 therefore needs one ycash-infra PR and one ycash-ops PR before P-4 can pass.
Proposed shape (the implementing lane decides the names):

- ycash-infra, `infra/testnet-seeds/nodes`: `pool.per_miner = optional(bool, false)`,
  `pool.coinbase_concurrency = optional(number, 2)`, `pool.max_paired_per_ip = optional(number, 8)`.
  With `per_miner` the yolo command drops `--payout …` and adds
  `--coinbase-concurrency <n> --max-paired-per-ip <m>`. **The node keeps
  `-mineraddress=<pool.payout>`** (`locals.tf`): yolo's paired-path checks compare every answer
  with the stock template's transparent coinbase (design note §8.3), and the swap path writes the
  transparent miner's script into `vout[0]` of that coinbase. `pool_status()` adds `payout`,
  `minersByKind`, `minerList`, `coinbaseCall`, `pairs`. A `render.tftest.hcl` and `seedctl.sh`
  case for each mode.
- ycash-ops, `testnet-pools/nodes/main.tf`: the module source and `testnet-pools/infra.ref` bumped
  (`scripts/bump-infra.sh --root testnet-pools <sha>`); `local.pool_image` = the `yolo-image`
  digest built from yolo `upgrade/vault` at or after `b3abf81` (paired jobs, yolo #16, #17); then

```hcl
    yb-fast = {
      profile    = "fast"
      # -ydf=5 only while a fast-testnet node may still run beta2 (P-1); removed for P-3
      extra_args = "-addnode=fastnet-seed.ycash.team:18833"
      pool = {
        image                = local.pool_image
        payout               = local.pool_payout   # the node's -mineraddress; yolo pays usernames
        per_miner            = true
        coinbase_concurrency = 2
        max_paired_per_ip    = 8
        port                 = 3333
        share_ratio          = 32
      }
    }
```

`-rpcthreads`: yolo needs at least `--coinbase-concurrency` + 2 = 4, which is ycashd's default;
no line is needed unless the concurrency is raised. The order is T-3, then deploy `pools` `upgrade`
(the node and yolo recreated on the images in `main.tf`, data kept), then `-ydf=5` removed and
`upgrade` again once P-1 is complete (or both in one `upgrade` if every node is already on beta3).

Checks, on the pool host (SSM):

```bash
sudo docker inspect yolo-yb-fast --format '{{json .Config.Cmd}}'     # no --payout; the two options
sudo docker inspect ycashd-yb-fast --format '{{json .Config.Cmd}}'   # no -ydf
curl -s 127.0.0.1:3334/status | jq '{payout, coinbaseCall, minersByKind, pairs, height, nodeUp}'
$HCLI getblocksubsidy $(( $($HCLI getblockcount) + 1 )) | jq .founders  # 0
```

### P-5: the call, once per kind, and its timing

On the pool host, with the demonstration wallet's addresses (§2):

```bash
TIP=$($HCLI getbestblockhash)
for a in "$T_ADDR" "$Z1_ADDR" "$PQ_ADDR"; do
  /usr/bin/time -f '%e s' $HCLI getcoinbasetemplatefor "$a" "{\"previousblockhash\":\"$TIP\",\"txids\":[]}" \
    | jq -c '{height, fees, fund, fundrule, amount}'
done
```

Pass: three answers, `fundrule` `"none"`, `fund` 0, `amount` equal to `getblocksubsidy`'s
`totalblocksubsidy` in zatoshi (no transactions named). The Sapling line's time minus the
transparent line's is the proof's cost on the pool host (§5.2). (`zcbenchmark createsaplingoutput`,
which the design note §6.2 names for this, is a wallet call and is not registered on the pool's
node, which runs `-disablewallet`.) **[CHECK]** that the pool's node has the Sapling output
parameters loaded: a `coinbase construction failed: …` answer (error row 17) on the Sapling call
means it has not, and the run cannot start.

## 2. The demonstration wallet

**Tool: one beta3 ycashd with its own wallet**, the only tool that both makes and later reads all
four kinds on the fast testnet with this run's binaries: `getnewaddress` (transparent),
`z_getnewaddress sapling` (Sapling), `getnewaddress "" "pq"` (post-quantum), and it decrypts the
Sapling coinbase notes with its incoming viewing keys. yew-cli (`wt/b3-lwcheck-yew`) reads
Sapling and transparent through the light-wallet server and has `address --new --falcon`, so it
may serve as a second reader of the post-quantum address too (**[CHECK]**, not needed for
acceptance). B3-D6: testnet coins only, outside `wt/`, the key location recorded.

**Where:** `/Users/boy/ycash-fastnet-demo/` (binaries in `bin/`, data in `data/`). The wallet file
is `data/testnet-yb-fast/wallet.dat` (**[CHECK]** the network subdirectory; the local fast node's
cookie is under `data/testnet-yb-fast/`). After the addresses are made:
`$DCLI backupwallet /Users/boy/ycash-fastnet-demo/wallet-backup-20261116.dat`, and record both paths
in §9. Nothing of it goes into any repository.

**The node:**

```
# /Users/boy/ycash-fastnet-demo/data/ycash.conf
testnet=1
testnetprofile=fast
rpcport=18862          # not 18842 (the lead architect's node)
port=18863
listen=0
addnode=fastnet-seed.ycash.team:18833
addnode=fastnet-explorer.ycash.team:18833
txindex=1              # the fee arithmetic of §4.6 reads prevouts (set before the first start)
```

It needs the fast testnet's blocks 0..510,247 (Zcash testnet history) before it can sync the rest.
Three ways, cheapest first; **[CHECK]** pick one with the lead architect:

1. During T-2 the local fast node (`/Users/boy/ycash-fast-sync`) is stopped for its upgrade anyway:
   copy its `blocks/` and `chainstate/` (not `wallet.dat`) into the demo datadir while it is
   stopped. The copy has no txindex: start once with `-reindex` (hours) or drop `txindex` and use
   §4.6's supply-delta check plus the fees of our own transactions only. Needs the lead
   architect's yes (their node).
2. The published prefix: ycash-infra `bundles/prefix/import/import.sh --keep` (testnet-prefix-v1,
   pin `c7b55a2a…`, about 66 minutes on a laptop), then start that datadir with the conf above.
   **[CHECK]** `import.sh` passes `-testnet` without `-testnetprofile`; the history below 510,248 is
   the same for every profile, but confirm the kept datadir starts under `-testnetprofile=fast`.
3. Plain P2P sync from the seeds: no preparation, several hours; start it a day ahead.

Start: `bin/ycashd -datadir=/Users/boy/ycash-fastnet-demo/data -daemon`. Before the burst it must be
at the seeds' tip (P-8). If `z_getnewaddress` or `getnewaddress` answers *Please acknowledge that
you have backed up the wallet's emergency recovery phrase*, use `ycashd-wallet-tool` (or
`walletconfirmbackup`) as that message says. **[CHECK]** whether the fast testnet requires it.

**The addresses** (make them before the burst, so the wallet sees every coinbase as it arrives;
a key made later needs a rescan):

| Role | Command | Form |
|---|---|---|
| `T_ADDR`, transparent miner | `$DCLI getnewaddress` | `sm…`, 35 characters |
| `Z1_ADDR`, Sapling miner 1 | `$DCLI z_getnewaddress sapling` | `ytestsapling1…`, 88 |
| `Z2_ADDR`, Sapling miner 2 | `$DCLI z_getnewaddress sapling` | `ytestsapling1…`, 88 |
| `PQ_ADDR`, post-quantum miner | `$DCLI getnewaddress "" "pq"` | `tqf…`, 53 |
| `SPARE_Z`, `SPARE_PQ`, `SPARE_T`: fee sources and sinks (§4.5), never payouts | the same commands | |

**Which post-quantum scheme: FN-DSA-512 (`tqf…`).** `getnewaddress "" "pq"` gives FN-DSA-512 where
Falcon is active at the next height, else SLH-DSA (ycash6 `src/wallet/rpcwallet.cpp`, the `pq`
type); check the prefix is `tqf` (`validateaddress` `pqschemename` `FN-DSA-512`). FN-DSA-512 is
the scheme plain YEC holders get by default and has the smaller signatures. Both schemes take the
same paired path and the coinbase differs only in the scheme byte of the 35-byte script, so one
proves the kind; a fifth miner at `getnewaddress "" "pqslh"` (`tqs…`) is optional (§9 of the plan).

Check each before it is used (the fleet refuses a wrong form before renting, too):

```bash
for a in $T_ADDR $PQ_ADDR; do $DCLI validateaddress $a | jq -c '{isvalid, ismine, scriptPubKey, pqschemename}'; done
for z in $Z1_ADDR $Z2_ADDR; do $DCLI z_validateaddress $z | jq -c '{isvalid, type, ismine}'; done
```

Keep each address's `scriptPubKey`: the evidence compares coinbase scripts with them.

**How each payout is verified, independently of the pool's accounting:**

| Kind | From the chain (a node that is not the pool's) | From the owning wallet | From the explorer |
|---|---|---|---|
| Transparent | `getblock … 2`: `tx[0].vout[0].scriptPubKey.hex` = `T_ADDR`'s script, `valueZat` = expected | `$DCLI gettransaction <coinbase txid>`: `details[]` with `T_ADDR`, category `immature`, the amount | the address page on `fastnet-explorer.ycash.team` lists the coinbase |
| Post-quantum | as transparent, with `PQ_ADDR`'s 35-byte script | as transparent (**[CHECK]** that `gettransaction` lists the post-quantum output; beta2's L-2/L-4 found post-quantum coins counted but not always listed) | **[CHECK]** Inzyght's post-quantum views wait on its licence (E5); the address page may not exist. The block page still shows the output |
| Sapling | `tx[0].vout` empty (or the fund's only, which must not be there), `vShieldedOutput` length 1, `valueBalanceZat` = −expected | `$DCLI z_viewtransaction <coinbase txid>`: an output to `Z1_ADDR` (or `Z2_ADDR`) of the amount; `z_listreceivedbyaddress <z> 0` lists it | the block page shows one shielded output; the recipient and amount are visible to the wallet only |

Every number comes from the demo node (or the explorer host's node over SSM), never from yolo's
`/status` or log, which only corroborate.

## 3. The one-card check (miniZ and an 88-character username)

**What it settles:** whether miniZ v2.5e3 sends a long username to the pool whole: its
documentation names no length limit and does not say whether it appends a worker name of its own
(ycash-infra `images/miner/README.md`, "Long usernames and miniZ"). The longest username of the
demonstration is a testnet Sapling address, **88 characters by itself** (HRP `ytestsapling`, ycash6
`src/chainparams.cpp`); post-quantum is 53, transparent 35.

**Why the bare address and not `<address>.<label>`:** the fleet passes the bare address as the
stratum username, and refuses a worker suffix before renting (`scripts/vast-fleet.py`
`payout_kind`; `infra/vast-miners/README.md`, "Payout addresses"; the image's entrypoint checks the
form, exit 64). An `<address>.<label>` username cannot be rented today without a fleet and image
change, and the demonstration does not need one (D-5: yolo accepts the label, F-1 passes the bare
address). yolo's label handling is covered by its own tests and by the stratum check of §4.7,
which needs no rental.

**When:** now, against the pool as it runs today (`--payout`): the username is then only a name,
nothing is paid to it, so any valid 88-character testnet Sapling address will do (`Z1_ADDR` once
§2 exists, or the item 17 test wallet's `ytestsapling129y30…` address in
`/Users/boy/yew-fastnet-check/a/send.log`). It does not depend on beta3.

**Inputs** (Actions → `miners` → Run workflow, ref `main`):

| Input | Value |
|---|---|
| `action` | `burst` |
| `network` | `fast` |
| `count` | `1` |
| `hours` | `1` (the minimum; ended early below) |
| `payouts` | the 88-character `ytestsapling1…` address |
| `dry_run` | first `true` once (prints the plan, the payout shown as `sapling ytestsap…<last 4>`), then `false` |

The run arms `miners-burst-expire` before renting; the container ends its own rental at
`MINER_UNTIL`.

**Success:**

- **Pool log** (SSM on the pool host, `sudo docker logs yolo-yb-fast 2>&1 | grep 'authorized' | tail`):
  under `--payout` yolo logs `miner <n>: authorized as "<username>", paying <pool payout>`
  (`src/stratum.rs`; strings up to 128 bytes are printed whole, in quotes). The quoted username
  must be **exactly** the 88 characters given, with nothing after them. Count it:
  `… | sed 's/.*authorized as "\([^"]*\)".*/\1/' | awk '{print length}'` → `88`.
- **Pool status**: deploy `pools` `status`: `miners` ≥ 1 and `shares`/`accepted` rising.
- **Miner log**: miners `logs`, network `fast`, `tail` 200: miniZ connected to
  `fastnet-pool.ycash.team:3333`, no authorization error, accepted shares counted. **[CHECK]**
  miniZ's exact wording; the fleet masks the address in what it prints.

Then end it: miners `down`, network `fast`, confirm `down fast`; miners `status` shows nothing
rented. Run one `miners-burst-expire` pass afterwards (its workflow, by hand) so the schedule
switches itself off.

**Cost:** one card at most `max_dph` $0.09 an hour (fleet file), billed while it runs: ten to
twenty minutes is about $0.02 to $0.03; at worst the full hour, $0.09.

**If it fails:**

| What the log shows | Meaning | Fallback |
|---|---|---|
| A username shorter than 88 | miniZ truncates | Sapling miners cannot be shown with miniZ. (a) Another Equihash 192,7 miner: the image carries lolMiner, whose OpenCL filter drops Nvidia cards on Vast (GPU bursts 2 and 6), so in practice a third miner program added to ycash-infra `images/miner` (a change and an image build). (b) A pool-side alias (a short username mapped to the full address): **yolo has no alias map today** (no such flag or file in `--help`, `src/pairs.rs` reads the username itself); it would be a yolo change, and a design question (who may register an alias), so not for beta3 without the lead architect. (c) A shorter label is no help: the bare address is already 88 |
| `<88 characters>.<something>` | miniZ appends a worker name | With the pool in per-miner mode this is accepted when the suffix is 1 to 32 of `A-Z a-z 0-9 _ -` (D-5; `split_username`); under today's `--payout` it does not matter. Note the suffix, and check that it fits that grammar |
| No `authorized` line, miniZ reports an authorization or protocol error | miniZ refuses the username | as truncation |
| No connection at all | not a username question (card, driver, pool) | read miners `logs`; the GPU burst notes in `miners/fleet.json` |

A transparent or post-quantum username is shorter; if 88 passes, they pass.

## 4. The four-miner run

### 4.1 Before starting

All of P-1..P-11 ticked. The demo node at the tip. The fee scripts of §4.5 ready in a terminal.
Write down the start height: `START=$($DCLI getblockcount)`.

### 4.2 Inputs

Actions → `miners` → Run workflow, ref `main`:

| Input | Value |
|---|---|
| `action` | `burst` |
| `network` | `fast` |
| `count` | `4` |
| `hours` | `1` |
| `payouts` | `<T_ADDR>,<Z1_ADDR>,<Z2_ADDR>,<PQ_ADDR>` (miner *n* is paid at entry *n* mod 4: `ycash-fast-0` transparent, `-1` and `-2` Sapling, `-3` post-quantum) |
| `dry_run` | `true` once (four `would run` lines, each payout shown by kind), then `false` |

The fleet file is left as it is (its one payout entry is the pool's own address); the input
overrides it for the slots this burst rents. A fifth, SLH-DSA, miner: `count` 5 and a fifth entry.

### 4.3 Duration and cost

On 2026-11-16 one card mined 247 blocks in about 25 minutes (a block every 6 seconds or so), all
paying one transparent address plus a 5 % fund output. The fast profile targets 75-second blocks,
so four cards push the difficulty up; **[CHECK]** how fast it rises on the fast profile (today's
burst stayed near 6 seconds for 25 minutes: look at `getblockchaininfo.difficulty` and the block
times of that burst). Either way one hour is enough: at 75-second blocks it gives about 48 blocks,
about 12 per miner; at 6 to 20 seconds, several times that. The Sapling miners find fewer than
their share while blocks come faster than their proofs (§5.2). **One hour; a second one-hour burst
with the same `payouts` only if after 40 minutes a miner has fewer than three blocks or no
fee-paying block.** (A later burst on the same network sets a new end time.)

Cost: 4 cards × 1 hour × at most $0.09 = **at most $0.36** (about $0.24 at the plan's $0.06 an
hour). A second hour, the same again.

### 4.4 Watching

| What | Where | Expect |
|---|---|---|
| Miners rented, shares per miner | miners `status`, network `fast` (`shares` on) | four `ycash-fast-*`, shares rising on each |
| A miner's own output | miners `logs`, network `fast`, `tail` 200 | pool connected, accepted shares; nothing about the username |
| Pool totals | deploy `pools` `status` | `miners` 4, `accepted` rising, `nodeUp` true, `templateAgeSeconds` small |
| Pool by kind, pairs | SSM: `curl -s 127.0.0.1:3334/status \| jq '{minersByKind, minerList, coinbaseCall, pairs, accepted, rejected, stale, highHash}'` | `minersByKind` `{"p2pkh":1,"sapling":2,"pq":1}`; `coinbaseCall` true; `pairs.addresses` 3, `failures` not growing |
| Blocks found, by miner | SSM: `sudo docker logs --since 1h yolo-yb-fast 2>&1 \| grep -E 'authorized, paying\|accepted by the node\|rejected by the node\|coinbase for'` | `miner <n>: authorized, paying "<address>" (<kind>)`; `miner <n>: block <h> accepted by the node`; no `rejected` other than lost races; no `coinbase for …` errors |
| Pairs and proof time | the same log, `grep 'pair for'` | `pair for "<address>" (sapling): height <h>, <k> txs, amount <zat> zat, <ms> ms` (§5.2) |
| The chain | `fastnet-explorer.ycash.team`; `$DCLI getblockcount` | blocks arriving; the explorer within a block of the demo node |
| The pool's node keeps up | deploy `pools` `status` `blocks` vs deploy `seeds` `status` `blocks` | equal, or one apart |

Not visible without SSM: the miner list by kind and the pair round trips (the deploy `status`
filter drops them until P-4's module change adds them).

### 4.5 Fee-paying transactions during the run

At least one block per miner kind must carry fee-paying transactions, a post-quantum spend among
them (plan §9). Send one transaction about every two minutes (15 to 25 over the hour), each after
the previous one is mined, so they land in different blocks and so in different miners' blocks;
the payout addresses themselves never send or receive anything but coinbases.

Sources (fund them before the run, P-9; coinbase outputs cannot be used: the fast testnet
requires a coinbase to be shielded and it matures after 100 blocks):

- **Sapling, from the item 17 test wallets** `/Users/boy/yew-fastnet-check/a` and `b` (wallet `b`
  received 2 YEC privately on 2026-11-15): yew-cli private sends between them and to `SPARE_Z`,
  fee 1,000 zat each:
  `wt/b3-lwcheck-yew/target/debug/yew-cli --server fastnet-lightwallet.ycash.team:443 --network testnet-yb-fast --wallet /Users/boy/yew-fastnet-check/b/wallet.sqlite --seed-file /Users/boy/yew-fastnet-check/b/seed sync`
  then `… send-yec <ytestsapling1… of wallet a> 1000000`. **[CHECK]** the exact options item 17's
  acceptance used (TLS, `--params`); the logs in that directory do not record the command line.
  These go through the light-wallet server, which is why P-7 matters.
- **Post-quantum and transparent, from the demo node:** before the run, send 0.5 YEC from wallet
  `b` to `SPARE_Z` (demo wallet), then `$DCLI z_sendmany <SPARE_Z> '[{"address":"<SPARE_PQ>","amount":0.2},{"address":"<SPARE_T>","amount":0.2}]'`
  (any-to-any, beta2 D-1; **[CHECK]** the Sapling → post-quantum direction on beta3, which beta2's
  matrix had not tested from a Sapling source). During the run:
  `$DCLI sendtoaddress <SPARE_T> 0.01` spends from whichever of `SPARE_PQ` / `SPARE_T` the wallet
  picks; to force a post-quantum input, `$DCLI z_sendmany <SPARE_PQ> '[{"address":"<SPARE_T>","amount":0.01}]'`
  (**[CHECK]** that `z_sendmany` takes a post-quantum source on beta3, else `sendtoaddress` with the
  only spendable coins being post-quantum).

Each transaction's fee is known to whoever sent it (yew-cli prints `fee 1000`; `$DCLI
gettransaction <txid> | jq .fee`, item 1). Record each txid; §4.6 finds the block that holds it.

### 4.6 Evidence and the acceptance table

For every block from `START` to the end, classify the coinbase and do the arithmetic, on the demo
node (never the pool's):

```bash
blk() { # height -> one JSON line: who was paid, how much, and the arithmetic inputs
  local h=$1 b; b=$($DCLI getblock "$($DCLI getblockhash "$h")" 2)
  jq -c --argjson h "$h" '{h: $h, hash, ntx: (.tx | length), cb: .tx[0].txid,
      vout: [.tx[0].vout[] | {zat: .valueZat, spk: .scriptPubKey.hex}],
      zouts: (.tx[0].vShieldedOutput | length), vbal: .tx[0].valueBalanceZat,
      paid: (([.tx[0].vout[].valueZat] | add // 0) - .tx[0].valueBalanceZat),
      supplyDelta: .chainSupply.valueDeltaZat, txids: [.tx[1:][].txid]}' <<<"$b"
}
sub() { $DCLI getblocksubsidy "$1" | jq -c '{total: (.totalblocksubsidy*1e8|round), founders: (.founders*1e8|round)}'; }
for h in $(seq $START $($DCLI getblockcount)); do blk $h; done > /Users/boy/ycash-fastnet-demo/blocks.jsonl
```

Per block:

- **Who:** `vout[0].spk` = `T_ADDR`'s or `PQ_ADDR`'s script, or `vout` empty with `zouts` 1 (a
  Sapling miner: which one, from `$DCLI z_viewtransaction <cb>`). A coinbase that pays anything
  else (the pool's payout address, another miner, a second output) in the burst window is a STOP
  (§6.1), unless it came from a miner not in this burst (**[CHECK]** that no other miner mines the
  fast testnet during the run: the lead architect's local node runs no `-gen`; nothing else is
  rented).
- **Expected** = `total` − `founders` (0 here) + Σ fees of `txids`. Fees: for our own transactions
  from §4.5's record; for any other, Σ prevout `valueZat` (via `$DCLI getrawtransaction <prevtxid> 1`,
  txindex) − Σ `vout` `valueZat` + `valueBalanceZat`.
- **Observed** = `paid` (transparent outputs minus `valueBalanceZat`; a Sapling coinbase has
  `valueBalanceZat` = −amount).
- **Difference** = observed − expected, **must be 0**.
- **Cross-check, needs no fee computation:** `supplyDelta` must equal `total` (the block adds
  coinbase value minus the fees it moved: equal to the subsidy exactly when the coinbase claims
  every fee). **[CHECK]** calibrate it first on one of today's 247 blocks (expect 625,000,000 zat,
  the fund output included in the coinbase total), and that `chainSupply` carries `valueDeltaZat`
  on a node whose history began with the prefix import.

Fill in, per miner, at least three blocks, at least one of them with fee-paying transactions:

| Miner | Kind | Address (short) | Blocks found | Height | Coinbase txid (short) | Subsidy (zat) | Fees (zat) | Expected (zat) | Observed (zat) | Diff | Supply delta = subsidy | Wallet sees it |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ycash-fast-0 | transparent | `sm…` | | | | | | | | | | `gettransaction` |
| | | | | | | | | | | | | |
| | | | | | | | | | | | | |
| ycash-fast-1 | Sapling | `ytestsapling1…` | | | | | | | | | | `z_viewtransaction` |
| | | | | | | | | | | | | |
| | | | | | | | | | | | | |
| ycash-fast-2 | Sapling | `ytestsapling1…` | | | | | | | | | | `z_viewtransaction` |
| | | | | | | | | | | | | |
| | | | | | | | | | | | | |
| ycash-fast-3 | post-quantum (FN-DSA-512) | `tqf…` | | | | | | | | | | `gettransaction` |
| | | | | | | | | | | | | |
| | | | | | | | | | | | | |

Plus: every block in the window classified (a count per payee, and zero unexplained); the
explorer's view of one block per kind (a screenshot or the page's numbers); the pool's `/status`
at the end (the plan's §9.6).

### 4.7 Negative checks (no rental needed)

From the coordinator's machine, a stratum client against the pool (plain TCP, port 3333):

```bash
pool() { { printf '{"id":1,"method":"mining.subscribe","params":["check"]}\n{"id":2,"method":"mining.authorize","params":["%s",""]}\n' "$1"; sleep 3; } | nc fastnet-pool.ycash.team 3333 | grep '"id":2'; }
pool "ytestsapling1notanaddress"     # refused: Invalid address
pool "${Z1_ADDR}.demo-check"          # true: the label path (D-5), then disconnect
pool "${Z1_ADDR}.bad.label!"          # refused: the worker label must be 1 to 32 characters …
pool "<a Sprout or mainnet address>"   # refused
```

and the pool log shows no coinbase built for an amount other than the exact one: no `coinbase for
… :` errors and no `rejected by the node: bad-cb-amount` in the burst window. Each authorize costs
the per-IP budget (ten a minute): space them out.

## 5. Sapling specifics

### 5.1 How the Sapling payouts are proven

yolo checks a Sapling pair's shape and value (one Sapling output, `valueBalance` of minus the
amount, no transparent output besides the fund's), **not its recipient**: it does not decrypt the
output; that the output pays the miner is the node's responsibility (plan §2.1; yolo README). So
the proof is the owning wallet's:

1. `$DCLI z_viewtransaction <coinbase txid>`: an output with `address` = `Z1_ADDR` (or `Z2_ADDR`)
   and `valueZat` = expected; the wallet found it with its incoming viewing key, so the note is
   spendable by that wallet after maturity.
2. The chain (demo node): `vShieldedOutput` length 1, `valueBalanceZat` = −expected, no
   transparent output.
3. Totals: `$DCLI z_listreceivedbyaddress <Z1_ADDR> 0 | jq 'map(.amountZat) | add'` equals the sum
   of that miner's coinbase values in the table (**[CHECK]** that the call lists coinbase notes
   below maturity; if not, sum `z_viewtransaction` per coinbase instead).
4. Optional, a check by someone without the wallet: a coinbase's Sapling output is encrypted to
   the all-zero outgoing viewing key (ZIP 213), so anyone can recover its recipient and amount.
   No tool in the workspace does this today; not needed for acceptance.

### 5.2 Proving time on the pool host

The pool host is a `t3a.small` (two vCPUs, one physical core, burstable). The design note (§6.2)
estimates **2 to 4 seconds per Sapling coinbase** there, and about twice that when its two
requests run at once; transparent and post-quantum pairs need no proof. Measured during the run
from yolo's log:

```bash
sudo docker logs --since 1h yolo-yb-fast 2>&1 | grep 'pair for' \
  | sed -E 's/.*\((sapling|pq)\): height ([0-9]+).* ([0-9]+) ms$/\1 \2 \3/' \
  | awk '{n[$1]++; s[$1]+=$3; if($3>m[$1])m[$1]=$3} END{for(k in n) printf "%s n=%d mean=%.0f ms max=%d ms\n",k,n[k],s[k]/n[k],m[k]}'
```

The Sapling mean minus the post-quantum mean is the proof's cost; `/status` `pairs.lastRoundTripMs`
is the latest one. Record both in §9, and P-5's single-call timing, and replace the design note's
estimate with them.

What it means here: after each new block a Sapling miner has no work until its pair arrives. With
blocks every 6 to 10 seconds and 4 to 8 seconds of proving for two Sapling miners, they idle much
of each interval and find fewer blocks than their share; as the difficulty climbs toward 75-second
blocks the loss falls to the design note's 4 to 10 %. That is not a payment defect. Keep the CPU
credits `"unlimited"` during the run (P-6): in `standard` mode an exhausted credit balance would
cut the host to its 20 % baseline and multiply the proof time by about five. If the Sapling
miners find no block at all in the first 30 minutes, extend by a second hour rather than change
anything; a larger pool host (the design note's suggestion) is the lead architect's decision,
after this measurement.

## 6. Failure handling, teardown, budget

### 6.1 Stop conditions

**STOP** means: miners `down` (network `fast`, confirm `down fast`) at once, keep every log, open a
defect with the block's evidence, and tell the lead architect. Do not retry until it is understood.

| Condition | Why |
|---|---|
| A demonstration miner's block pays less than expected (difference ≠ 0), or more | the criterion itself: a miner is paid in full, exactly |
| A coinbase in the window pays an address that is not the finder's username, or carries a fund or pool output | a payout defect |
| A Sapling coinbase the demo wallet does not see (`z_viewtransaction` shows no output to `Z1`/`Z2`), with the chain showing one Sapling output | the node built a coinbase to someone else; yolo cannot see this |
| `block <h> rejected by the node: <verdict>` with a verdict other than a lost race (`inconclusive`, `duplicate`, `duplicate-inconclusive`, `bad-prevblk`), above all `bad-cb-amount` | a malformed paired job |
| Two P-1 nodes hold different blocks at the same height for more than a block or two | a consensus split (the briefing's rule: stop and report at once) |
| yolo logs `coinbase for <address> at height <h>: <why>` repeatedly (an answer failed its checks) | the node and yolo disagree on an amount: no money is lost (the answer is dropped), but it is a defect |
| Spend reaches $5 in the ledger | half the approved budget: stop and report before more |

**Watch, not stop:**

- **Stale shares.** `stale` grows quickly at fast blocks (a GPU flushes solutions for the previous
  job after every block; yolo answers them at once, never counts them against the miner). Stop
  only if a miner's accepted shares stay at zero for 10 minutes while others rise.
- **`highHash`**: about one per five or six shares from miniZ; normal.
- **The pool's node falling behind** (`templateAgeSeconds` above about 30, `nodeUp` false, or its
  `blocks` more than two behind the seeds for five minutes): its miners mine on a stale tip and
  their blocks lose races. Look at its peers (deploy `pools` `status`); if it does not recover,
  `down` the miners, fix, restart the burst.
- **A miner that never connects** (Vast machine, driver): the fleet's `max_start_minutes` (30)
  replaces it on reconcile; or `down` and start the burst again with the same `payouts`.
- **The light-wallet node losing peers** (P-7): the fee transactions sent through it may not reach
  the pool; send from the demo node instead.

### 6.2 Teardown

1. miners `down`, network `fast`, confirm `down fast`; miners `status`: nothing rented.
2. One `miners-burst-expire` run by hand after the burst's end time, so its schedule switches
   itself off (workflow header of `miners.yml`); confirm that it did.
3. The pool: leave it in per-miner mode (beta3's intended configuration) or return it to
   `--payout`: the coordinator's choice, recorded in §9. Either way `-ydf` stays off.
4. The demo node keeps running until §5.1's checks and the 100-block maturity check of §7's first
   item are recorded; then `$DCLI stop`. The datadir and the wallet backup stay in
   `/Users/boy/ycash-fastnet-demo/` (B3-D6).

### 6.3 Budget ledger (vast.ai; approved total $10)

| When (UTC) | What | Cards × time | Cost (Vast's figure, else at most) | Running total |
|---|---|---|---|---|
| 2026-11-16 | One-miner burst (247 blocks, about 25 minutes; before this runbook) | 1 × ~25 min | about $0.03 to $0.04 | ~$0.04 |
| | One-card username check (§3) | 1 × | ≤ $0.09 | |
| | Four-miner run (§4) | 4 × 1 h | ≤ $0.36 | |
| | (if needed) second hour | 4 × 1 h | ≤ $0.36 | |

Take the real figures from the Vast account's billing after each step (the coordinator's). The
pool host's CPU surplus credits during the run are AWS, not Vast: a few cents, recorded separately.

## 7. What the demonstration does not prove

- **That the coins can be spent.** The fast testnet requires a coinbase to be shielded and matures
  it after 100 blocks. The transparent miner can shield its coinbase (`z_shieldcoinbase`). For the
  **post-quantum miner** this is open: beta2's interoperability matrix found post-quantum coins
  removed from `z_sendmany`'s inputs (PQ → Sapling refused), so a post-quantum coinbase may be
  unspendable with today's wallet while being consensus-valid to spend. Try it once after 100
  blocks (`$DCLI z_shieldcoinbase <PQ_ADDR> <SPARE_Z>`) and record the answer; a failure is a
  finding for after beta3, not a failure of the demonstration. The Sapling notes become spendable
  at maturity; one spend from each Sapling payout address is a cheap extra check.
- **kogany as the pool's node.** The pool's node is ycashd; kogany's `getcoinbasetemplatefor`
  (3k) is proven by its own tests and the cross-line acceptance, not here (plan §8). The local
  koganyd validating every block of the run is shown (P-1: it follows the same chain).
- **Mainnet**, or miners other than miniZ on Nvidia cards rented on Vast.
- **Many miners**: four (or five), not the scale the `--coinbase-concurrency` and
  `--max-paired-per-ip` limits are for; proving under load beyond two Sapling addresses.
- **That a Sapling payout's recipient is checked by the pool**: it is not, by design; the
  demonstration shows the node built it right in these blocks.
- **Yellowback**: the fast testnet has no attestor set, so no quote tag, no YED and no pool-fee
  share are involved.
- **A full block**: the boundary where a Sapling coinbase does not fit (`coinbase-does-not-fit`,
  D-3) is not reached by a few transactions.
- **Behaviour across a reorganisation** of a paired miner's block, and long runs (hours, days).

## 8. Open questions: what the coordinator must check first

1. **The beta3 mandate end (`H_END`)**: is the cut's value compiled into beta3, and is the chain
   past it? With the provisional 600,000 the criterion cannot be shown (P-2).
2. **The pool's per-miner mode does not exist in the deployment yet**: a ycash-infra module change
   (`--payout` optional, the two new options, the status fields) and a ycash-ops change are needed
   for T-3 (P-4). Nobody is on it as of this revision.
3. **`rpcversion` on the fast testnet**: `yed_getinfo` probably refuses there; use the digest and
   version evidence instead (P-1).
4. The pool's node has the Sapling output parameters and answers a Sapling `getcoinbasetemplatefor`
   (P-5).
5. How the demonstration node gets the history below 510,248 (§2: copy during T-2 with the lead
   architect's yes, the prefix import, or a P2P sync started early); the wallet's datadir
   subdirectory; whether the fast testnet requires the backup acknowledgement.
6. The post-quantum address in the wallet's views (`gettransaction` details), the explorer's
   post-quantum pages, and `z_sendmany` with a post-quantum source or recipient on beta3 (§2, §4.5).
7. The exact yew-cli command line item 17 used (§4.5).
8. How fast the fast profile's difficulty rises under four cards (§4.3).
9. `chainSupply.valueDeltaZat` present and calibrated on a known block (§4.6), and
   `z_listreceivedbyaddress` with immature coinbase notes (§5.1).
10. Whether the local explorer ycashd (`/Users/boy/ycash-explorer`) follows the fast testnet (P-1).
11. miniZ's log wording for a connection and accepted shares (§3).

## 9. Record (filled in by the coordinator)

| Item | Value |
|---|---|
| Candidate commits / T-1 image digests | |
| `H_END`; first height without a fund output; its hash on every P-1 node | |
| P-1..P-11, each with its output (trimmed) | |
| Demonstration wallet: node binary, datadir, `wallet.dat` path, backup path | |
| `T_ADDR`, `Z1_ADDR`, `Z2_ADDR`, `PQ_ADDR` (public addresses) and their scripts | |
| One-card check: run, username length seen by yolo, miniZ's behaviour, cost | |
| Four-miner run: start and end (UTC), `START` and end heights, blocks per miner | |
| Proving time: P-5's single call; the log's Sapling and post-quantum means and maxima | |
| The acceptance table (§4.6), filled | |
| Negative checks (§4.7) | |
| The pool's final `/status` | |
| Maturity checks (§7: the post-quantum shield attempt, a Sapling spend) | |
| Budget ledger (§6.3), real figures | |
| Defects found, with links | |
| Verdict | |
