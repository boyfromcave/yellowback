# Pool regtest plan — real pool software on the devnet, and yolo in Rust

**Status:** revision 1, 2026-09-28. In implementation. The status table is §8; agents update it.

This plan is a delta on [`role-based-regtest-plan.md`](role-based-regtest-plan.md) scenario 3
("I am a mining pool", §4.3). It replaces the one thing that scenario cannot test as written:
the pool seat mines with the node's internal miner (`generate`), which is the one block-building
path no real Ycash pool uses. The deliverable is a Rust rewrite of Ycash's solo-pool stratum
software (`yecdev/yolo`, Perl) that runs against the Yellowback-enabled `ycash-dd` node on
**regtest**, a headless Python stratum miner that stands in for a GPU rig at regtest's Equihash
parameters, and a devnet pool seat whose blocks flow node → stratum → miner → `submitblock`
end to end — with the Yellowback coinbase tag verified on every block.

## 0. Revision log

### Revision 1 (2026-09-28) — first draft, from the owner's direction

| # | Decision | Where |
|---|---|---|
| P-1 | **Real pool software, not the internal miner.** Nobody mines Ycash with the embedded node miner; "miner-enforced" is only tested when a real stratum layer builds the block. The devnet pool seat gets a `--stratum` mode. | §1, §3.4 |
| P-2 | **Regtest parameters, no GPU.** Ycash mainnet is Equihash 192/7 (GPU, high memory); regtest is 48/5 (`ref/ycash/src/chainparams.cpp:560-563`). GPU miners (gminer, miniZ, lolMiner) do not solve 48/5, so a Python stratum client using the test framework's pure-Python Wagner solver stands in for the rig. The stratum layer under test is real; only the solver is a fixture. | §3.3 |
| P-3 | **yolo, not the Perl lineage.** `yecdev/yolo` (fork of ChileBob/StratumPool: `stratumpool`, `stratumsolo`, `cenote`) is the reference, pinned read-only at `ref/yolo`; `boyfromcave/yolo` is the working repo and is rewritten in Rust. The Perl is the behavioural and wire-format reference, not source to translate line by line. | §2, §3.2 |
| P-4 | **Wire compatibility with the GPU miners the Perl serves is a hard requirement.** The Rust server must speak the exact `mining.subscribe/authorize/extranonce.subscribe/set_target/notify/submit` shapes the Perl sends, so that on mainnet (192/7) gminer/miniZ/lolMiner connect unchanged. Regtest changes only n, k and the solution length. | §3.2.2 |
| P-5 | **The tag must survive every coinbase path yolo has.** The three Perl variants treat the node's coinbase differently (§2.2) and one of them (`cenote`) drops the Yellowback tag. The Rust rewrite carries the tag on all of them, and the regression test proves it. | §2.2, §3.2.4 |

## 1. The problem

`docs/plans/role-based-regtest-plan.md` §4.3 walks the pool operator through configuring a
payout address, running the quote agent, stopping signalling, and getting pinned. Every one of
those observations is real. But the *blocks* in that scenario are built by `ycashd`'s internal
miner (`CreateNewBlock` → `IncrementExtraNonce` → `generate`), which appends the tag itself.
`contrib/yellowback/pool/README.md` lists three carriers for the tag and says plainly that the
two a real pool uses — `coinbasetxn.data` taken as is, or `coinbaseaux.flags` appended to a
self-assembled coinbase — are **"unverified against a live pool"** (survey question Q9 of the v2
plan, parked for the outreach phase). Miner enforcement is the core of the design; the one
thing the devnet does not exercise is the code path that decides whether a real pool's blocks
carry the tag.

Testing it on regtest is possible because the stratum protocol and the coinbase assembly do
not care about n and k; only the solver does, and the test framework already has one
(`qa/rpc-tests/test_framework/equihash.py` `gbp_basic`, `mininode.CBlock.solve`, ≈ 1 s per
48/5 block, see `docs/mapping.md` §14 "mine_block_raw").

### 1.1 What "done" means

1. `yolo` (Rust) runs against a regtest `ycash-dd` node with `-yellowback` on.
2. A Python stratum miner connects to it, receives work, solves 48/5, submits, and the node
   accepts the block (`submitblock` → `null`, height advances on every devnet node).
3. `check-coinbase <height> -regtest` and `yed_gettag <height>` agree that the block carries
   the pool's quote tag, on every yolo mode (§2.2), including the one that rebuilds the
   scriptSig.
4. `yellowback-devnet up --role pool --stratum` puts the seat's blocks through that path, the
   scenario 3 checklist has the steps, and `qa/rpc-tests/yellowback_stratum.py` proves 1–3
   unattended.
5. The same binary, told `--equihash 192,7` (or left to derive it from the chain), serves a
   mainnet node with the Perl's exact wire format. That is asserted by a wire-format test
   against recorded Perl exchanges, not by a GPU.

## 2. What exists

### 2.1 Repos

| Repo | Role | Pin / branch | What |
|---|---|---|---|
| `ref/yolo` | reference, read-only | `main` @ `c9c155c6` (no tags) | `yecdev/yolo`: Perl `stratumpool` (608 lines), `stratumsolo` (516), `cenote` (677); MIT |
| `yolo/` | app, writable | `main` | `boyfromcave/yolo`, forked from yecdev at the same commit; becomes the Rust rewrite |
| `ycash-dd` | fork | `feature/yellowback-price-attest` | the node; gains the Python stratum miner, the devnet `--stratum` seat, the functional test |

### 2.2 The three Perl variants and what each does to the node's coinbase

All three poll `getblocktemplate` once a second by shelling out to `ycash-cli`, build the block
from `coinbasetxn.data` + the template's transactions (2 MB cap), and push
`mining.notify` to every miner with the header fields **byte-reversed as hex** (`version`,
`previousblockhash`, `merkleroot`, `finalsaplingroothash`, `time`, `bits`), a **14-byte** `nonce1`
per client (2-byte client index + 12 random bytes = 28 hex chars, leaving 18 bytes of nonce for the
miner; the Perl's `nonce1_size = 16` comment is wrong, Y-F6), and
`mining.set_target` with the template's `target` as given. On `mining.submit` they assemble
`version ‖ prev ‖ merkle ‖ saplingroot ‖ nTime(from miner) ‖ bits ‖ nonce1‖nonce2 ‖ solution ‖ txcount ‖ txs`
and call `submitblock`. Where they differ is the coinbase:

| Variant | Coinbase | Tag fate | Yellowback carrier (`pool/README.md`) |
|---|---|---|---|
| `stratumsolo` | `coinbasetxn.data` untouched; rewards go to the node's `mineraddress` | **survives** | `coinbasetxn` as is |
| `stratumpool` | `coinbasetxn.data` with the output `scriptPubKey` regex-replaced by the miner's (`validateaddress` of the stratum username) — `stratumpool:499-509` | **survives** (scriptSig untouched) | `coinbasetxn`, output rewritten |
| `cenote` | scriptSig **rebuilt** as `substr(data, 92, 10)` (the 5-byte height push) + `--text` (`cenote:522`), then the output rewritten and optionally zeroed (`--cenote N` burns N rewards) | **dropped** — everything after the height push is discarded, and the tag lives there | must append `coinbaseaux.flags` verbatim after the height push |

`cenote` is the case the README predicted ("a stack that assembles its own coinbase") and the
first concrete stack that provably loses the tag. That is finding **Y-F1**, recorded in
`docs/mapping.md` §17 by this plan. `stratumsolo` and `stratumpool` are safe today only because
they do not touch the scriptSig; the rewrite must keep them that way and make `cenote` append
the flags.

Three more Perl behaviours the rewrite must reproduce or deliberately fix (each a row in §7):

- `nTime` in the block is taken from the miner's `mining.submit` params[2], not from the
  template. The Perl sends its own `time` in `mining.notify`; miners echo it. Keep.
- A `submitblock` that returns nothing is reported to the miner as accepted; any string
  (`inconclusive`, `invalid-solution`, `high-hash`, `duplicate`…) as rejected. Keep, and log the
  string.
- Work is refreshed when height, target or `finalsaplingroothash` change, else re-sent after 60 s
  to keep miners alive. The **template is not refreshed when only the coinbase changes** — and
  with Yellowback the coinbase changes whenever the quote agent publishes a new price
  (`yed_setquote` → `COINBASE_FLAGS`). A pool that mines a template fetched before the quote
  moved carries a stale price; still a valid tag, but stale by up to a poll interval. The
  rewrite polls the template on a 1 s timer as the Perl does and additionally re-issues work
  when `coinbaseaux.flags` changes (finding **Y-F2**; see §3.2.3).

### 2.3 The devnet pool seat today

`yellowback-devnet up --role pool` (node 4) and `pool N configure | signal on|off | quote
start|stop` exist (`contrib/yellowback/devnet/yellowback-devnet` `pool()`); blocks are mined
with `mine N 4` → `generate`. The scenario checklist is
`contrib/yellowback/devnet/scenarios/3-pool.md`. `contrib/yellowback/pool/` has the operator kit
(`check-coinbase`, `monitor-quote.sh`, the quote agent's config and service units).

## 3. Design

### 3.1 Workspace plumbing (Y0)

- `repos.yaml`: `ref/yolo` (role `reference`, `branch: main`, `commit: c9c155c6`, no tag — same
  shape as `ref/lightwalletd`) and `yolo` (role `app`, `branch: main`). The generic
  `bootstrap.sh`, `pull.sh` and `repo-status.sh` loops pick both up; the Makefile's `pins`
  target and the "nine repos" wording become eleven; `.gitignore` and
  `yellowback.code-workspace` gain both folders (`ref/yolo` read-only in the editor).
- `AGENTS.md` layout block and rule 2 name the new repos: pool software goes in `yolo/` only;
  its sole interface to the node is `getblocktemplate` / `submitblock` / `validateaddress` /
  `getblockchaininfo` over JSON-RPC (no `yed_*` RPC, no shell-outs).
- `docs/mapping.md` §17: "Pool software (yolo)" — the impedance rows this plan finds (Y-F1,
  Y-F2, and whatever the agents hit).
- `make status` counts, `make pins` rows: the repo count is a literal in three places; grep
  for "nine".

### 3.2 yolo in Rust (Y1–Y3)

#### 3.2.1 Shape

One binary, `yolo`, one crate, `Cargo.toml` at the repo root; Rust 2021, MSRV = the toolchain
the attest agent already uses. Modes select the coinbase policy of §2.2:

```
yolo --mode solo   [--port 3334]                 # coinbasetxn as is (node wallet is paid)
yolo --mode pool   [--port 3333] [--password …]  # output rewritten to the miner's address
yolo --mode cenote [--port 3334] [--text …] [--cenote N] [--scrooge]  # scriptSig rebuilt + text
     --rpc http://127.0.0.1:18232 --rpc-user … --rpc-password …   (or --rpc-cookie <path>, or --conf <ycash.conf>)
     --equihash 48,5 | 192,7 | auto             # auto: getblockchaininfo.chain == regtest → 48,5, else 192,7
     --log info|debug                            # every submit with the node's verdict; every tag decode
```

Dependencies stay few and boring: `tokio` (net + timers), `serde`/`serde_json`, `sha2`, `hex`,
`clap`, one HTTP client (`ureq` or `reqwest` with rustls; no OpenSSL), `tracing`. No async trait
crates, no actor frameworks. The Perl's single-threaded select loop becomes one tokio task per
client plus one template poller; state is a `Mutex<Work>`.

Keep the Perl at the repo root untouched until Y3 declares parity, then move it to
`legacy/perl/` with a README line pointing at `ref/yolo` for history; never delete it from git.

#### 3.2.2 Wire format — reproduced exactly

Record the Perl's byte-exact messages as fixtures (`tests/fixtures/*.jsonl`) by running
`ref/yolo/stratumsolo` once against a regtest node with a scripted client, and assert the Rust
server produces the same JSON (field order, `null` id on notifications, `"ZcashPoW"` trailer,
`true`/`false` clean-jobs flag, `error: null`). Specifically:

| Message | Shape (from `stratumsolo`) |
|---|---|
| `mining.subscribe` → | `{"id":N,"result":[null,"<nonce1 hex, 28 chars>"],"error":null}` |
| `mining.authorize` → | `{"id":N,"result": true,"error": null}` (pool mode: validate the username as a transparent address via `validateaddress`; reject with `result:false` if invalid or if `--password` is set and wrong) |
| `mining.extranonce.subscribe` → | `{"id":N,"result": true,"error": null}` and re-issue target + work |
| ← `mining.set_target` | `{"id":null,"method":"mining.set_target","params":["<target hex, as the template gives it>"]}` |
| ← `mining.notify` | `{"id":null,"method":"mining.notify","params":["<job id>","<version LE hex>","<prevhash reversed>","<merkle reversed>","<saplingroot reversed>","<ntime LE hex>","<bits reversed>",<clean:bool>,"ZcashPoW"]}` |
| `mining.submit` [worker, job, ntime, nonce2, solution] → | `{"id":N,"result": true}` / `{"id":N,"result": false}` after `submitblock` |
| anything else | disconnect |

Solution encoding: the miner sends the solution already prefixed with its compact size
(`24` + 36 bytes at 48/5; `fd9001` + 400 bytes at 192/7). Validate the length for the configured
n, k before touching the node.

#### 3.2.3 Template and work

Poll `getblocktemplate` every second (the Perl's cadence; `getblocktemplate` on regtest requires
a connected peer, `ref/ycash/src/rpc/mining.cpp:556-559` — the devnet has eight). New work when
`height`, `target`, `finalsaplingroothash` **or `coinbaseaux.flags`** changes (Y-F2). Block
assembly: coinbase per mode + template transactions under a 2 MB cap, merkle root over the txids
(double-SHA256, Perl `merkleroot`), header serialised as the Perl does.

#### 3.2.4 Coinbase per mode — the Yellowback part

- `solo`: `coinbasetxn.data` verbatim.
- `pool`: decode `coinbasetxn.data` with the crate's own minimal v4 (Sapling) transaction
  parser — not a regex over hex, which is what the Perl does and which breaks the day the
  node's scriptPubKey bytes appear elsewhere in the data — and replace the payout output's
  `scriptPubKey` with the miner's (`validateaddress` → `scriptPubKey`). scriptSig untouched.
- `cenote`: rebuild the scriptSig as `height push ‖ coinbaseaux.flags (verbatim, may be empty)
  ‖ text push`, keep the scriptSig ≤ 100 bytes (`ref/ycash/src/main.cpp:1456-1458`; the tag is
  37 bytes and the height push up to 5, so the text is truncated to fit and a warning logged),
  then the output rewrite/burn. This is the `coinbaseaux.flags` carrier in
  `contrib/yellowback/pool/README.md`, implemented for real for the first time.
- All modes: after assembling, decode the scriptSig with the same byte scan the node uses
  (`24 59 45 44 21` + 36 bytes) and log `tag: quote|signal|none`; expose it on
  `yolo --status` (a tiny HTTP `GET /status` JSON: height, template age, connected miners,
  last tag kind, last submit verdict) so `monitor-quote.sh`-style checks can read the pool, not
  just the node.

#### 3.2.5 Tests inside the crate

- Unit: header serialisation, merkle root (vectors from a real regtest block via
  `getblock … 0`), compact size, coinbase parse/rewrite for a captured `coinbasetxn.data`, the
  scriptSig rebuild with and without flags and at the 100-byte boundary, solution length per
  n,k, tag decode.
- Wire: replay the recorded Perl fixtures through the Rust server with a fake RPC
  (`mockito`-style or a hand-rolled `TcpListener`) and compare byte for byte.
- Integration (feature-gated, `cargo test --features regtest`): needs `YCASHD` in the
  environment; starts a two-node regtest, runs `yolo --mode <each>`, drives it with the Python
  miner (§3.3), asserts one accepted block per mode with the tag present.

### 3.3 The Python stratum miner (Y2)

`ycash-dd/contrib/yellowback/devnet/stratum-miner` (Python, workspace venv, imports
`qa/rpc-tests/test_framework/equihash.py` for `gbp_basic` and `mininode` for the header
hashing):

```
stratum-miner --pool 127.0.0.1:3334 [--user s1…] [--password …] [--blocks N] [--equihash 48,5] [--nonce-start 0] [--once]
```

Speaks the client half of §3.2.2: subscribe, authorize, extranonce.subscribe, wait for target
+ notify, loop nonce2 over the solver until a solution's header hash ≤ target, `mining.submit`,
count accepted/rejected, exit after `--blocks` accepted. It must handle `clean_jobs` (abandon
the current nonce loop) and re-notify. Keep it under ~250 lines; it is a fixture, not a miner.

Before the Rust server exists it is proven against the **Perl** `ref/yolo/stratumsolo` on a
regtest node: `perl -MJSON` works on this machine, and the Perl shells out to `ycash-cli` with
no `-regtest` flag, so the test wraps a `ycash-cli` shim on `PATH` that adds
`-regtest -datadir=…`. That run also produces the wire fixtures of §3.2.2.

### 3.4 The devnet seat (Y4)

- `yellowback-devnet up --role pool --stratum` (and `pool 4 stratum start|stop [--mode
  solo|pool|cenote]`): starts `yolo` beside node 4 (binary found via `YOLO_BIN`, then
  `../yolo/target/release/yolo`, then `PATH`) and one `stratum-miner` against it; `mine N 4`
  with a stratum seat routes through the miner (`--blocks N`) instead of `generate`. The
  heartbeat never mines the seat's blocks (unchanged).
- `status` prints the pool's `/status` line: mode, miners, last tag kind, last verdict.
- `devnet.json` records the pids and the mode; `down` stops both; `report` collects yolo's log.
- `scenarios/3-pool.md` gains step 0 ("the real pool") and, in steps 1–5, "with `--stratum`,
  confirm with `check-coinbase`"; step 6 sends the operator to `yolo --help` and
  `contrib/yellowback/pool/README.md`, whose per-stack section gets its first verified row.

### 3.5 The functional test (Y5)

`ycash-dd/qa/rpc-tests/yellowback_stratum.py` (registered in `qa/pull-tester/rpc-tests.py`,
named in the workflow's `YELLOWBACK_SCRIPTS`, **executable bit set** — the three-part check in
`docs/plans/yellowback-v3-development-plan.md` §6.1): two nodes with `-yellowback`, quote set,
for each mode start `yolo`, run the miner for 2 blocks, assert `submitblock` accepted, both
nodes at the new height, `yed_gettag` `found: true` with the expected `priceMicroUsd` and
payout key, and for `pool`/`cenote` that the coinbase pays the miner's address. Then the
negative: `cenote` with flags **not** appended (a `--no-flags` test-only switch) yields
`found: false` — the Y-F1 regression, pinned. Skips cleanly when `YOLO_BIN` is unset so the
inherited CI matrix does not break; the fork's CI job builds yolo and sets it.

### 3.6 Docs (Y6)

`yolo/README.md` rewritten for the Rust binary (build, modes, regtest quick start, the tag
section, the GPU-miner compatibility statement); `contrib/yellowback/pool/README.md` per-stack
section gets "yolo (Rust): verified on regtest 2026-09-…: solo/pool carry the tag unchanged;
cenote appends `coinbaseaux.flags`"; `doc/yellowback-mining.md` points a pool operator at it;
`docs/mapping.md` §17; this plan's §8 and `role-based-regtest-plan.md` §8 (R-item "3-pool with
real pool software").

## 4. Work items and checklists

Owners are parallel worktree agents (`wt/<name>`), one per non-overlapping chunk, as the v3
plan was executed. Y0 is done by the orchestrator before any agent starts.

### Y0 — workspace plumbing (orchestrator, workspace repo)
- [x] clone `ref/yolo` detached at `c9c155c6`, `chmod -R a-w` (`.git` writable); clone `yolo` on `main`
- [x] `repos.yaml`: `ref/yolo` (reference, commit-pinned) and `yolo` (app)
- [x] `.gitignore`, `yellowback.code-workspace` (read-only include for `ref/yolo`)
- [x] `Makefile` `pins` rows; "nine repos" → eleven in `Makefile`, `AGENTS.md`, `README.md`, `scripts/*.sh`
- [x] `AGENTS.md` layout block + rule 2 sentence for `yolo/`
- [x] `docs/mapping.md` §17 stub with Y-F1 and Y-F2
- [x] `git config core.sshCommand` on `yolo/` (the BOY_GH key); `make status` green with eleven repos

### Y1 — yolo Rust core (agent `yolo-core`, repo `yolo/`, branch `main`)
- [x] crate skeleton, `--help`, `--equihash auto|48,5|192,7`, RPC client (`getblockchaininfo`, `getblocktemplate`, `submitblock`, `validateaddress`) with cookie/conf/user-pass auth
- [x] template poller (1 s) with change detection on height/target/saplingroot/**flags**
- [x] work builder: coinbase per mode (§3.2.4), tx selection under 2 MB, merkle root, header fields reversed as the Perl does
- [x] stratum server: subscribe/authorize/extranonce.subscribe/set_target/notify/submit, per-client nonce1 (2-byte client index + 12 random = 28 hex chars, Y-F6), 60 s keepalive re-notify, disconnect on garbage
- [x] submit path: assemble block, `submitblock`, map the verdict to `result: true|false`, log the verdict string
- [x] tag decode + log on every work build; `GET /status`
- [x] unit tests of §3.2.5 (no node needed)
- [x] `cargo build --release` clean on stable; `cargo clippy` clean; commit with the Y-F rows it found

### Y2 — Python stratum miner + Perl wire fixtures (agent `stratum-miner`, worktree `wt/stratum-miner` of `ycash-dd`)
- [x] `contrib/yellowback/devnet/stratum-miner` per §3.3, using `test_framework.equihash.gbp_basic`
- [x] `ycash-cli` shim + a script that runs `ref/yolo/stratumsolo` against a regtest node and drives it with the miner: one block accepted, `yed_gettag` finds the tag (proves the fixture and confirms §2.2 row 1 empirically)
- [x] same against `ref/yolo/cenote`: block accepted, `yed_gettag` `found: false` (proves Y-F1 empirically)
- [x] record the Perl exchanges as `wt/…/contrib/yellowback/devnet/fixtures/stratum-perl-*.jsonl` (both sides, in order) for Y1's wire test — hand them to `yolo/tests/fixtures/` when Y3 integrates
- [x] `make check`-style lint: the script runs under the venv from any directory, like the devnet
- [x] commit; note in `docs/mapping.md` §17 what the framework solver needed (e.g. header layout for `finalsaplingroot`, nonce byte order)

### Y3 — parity and integration (agent `yolo-integrate`, after Y1 and Y2)
- [x] wire test in `yolo/` replays Y2's fixtures: byte-identical output
- [x] `cargo test --features regtest` runs the three modes with the Python miner against a regtest node; tag present in all three; Perl at `legacy/perl/`
- [x] `yolo --mode cenote` at the scriptSig 100-byte boundary: text truncated, tag intact, block accepted
- [x] `yolo/README.md` rewritten; the Rust binary's `--help` matches it

### Y4 — the devnet seat (agent `devnet-stratum`, worktree of `ycash-dd`, after Y2; needs a yolo binary from Y1)
- [x] `up --role pool --stratum`, `pool N stratum start|stop [--mode]`, `mine N 4` via the miner, `status` line, `down`, `report`
- [x] `scenarios/3-pool.md` updated per §3.4; `contrib/yellowback/devnet/README.md` role section
- [x] one hand-run of scenario 3 with `--stratum`, notes in the session `NOTES.md`, findings into §7

### Y5 — the functional test (agent `devnet-stratum` or `yolo-integrate`)
- [x] `qa/rpc-tests/yellowback_stratum.py` per §3.5; registered in the runner, named in `YELLOWBACK_SCRIPTS`, executable bit
- [x] the fork's CI job builds `yolo` (checkout of `boyfromcave/yolo` at a recorded commit) and exports `YOLO_BIN`
- [x] green locally with `--portseed` distinct from any other running suite

### Y6 — docs (whoever finishes last, then orchestrator review)
- [x] `contrib/yellowback/pool/README.md` per-stack: yolo row verified; cenote note rewritten from "expected" to "fixed in yolo (Rust) — Perl cenote drops the tag"
- [x] `doc/yellowback-mining.md` operator pointer; `docs/mapping.md` §17 complete
- [x] this plan §8 final; `role-based-regtest-plan.md` §8 new R-item row; memory note

### Y7 — one pool, no modes (owner decision P-6, 2026-09-28)

The three Perl scripts are one program copy-pasted three times (git history: `stratumpool`
2020-10-17; `stratumsolo` two days later = pool minus address check and stats; `cenote` a month
later = pool + `--text` + a reward burn + `--scrooge` which is solo again). `cenote --scrooge`
≡ `stratumsolo`; `cenote` ≡ `stratumpool` + text. The Rust binary drops the mode concept:

| Flag | Unset | Set |
|---|---|---|
| `--payout <s1…>` | the miner's stratum username is the payout address and must validate (`stratumpool`) | every block pays this address (`stratumsolo` / `--scrooge`) |
| `--text "…"` | the node's scriptSig is used untouched | scriptSig rebuilt as height push ‖ `coinbaseaux.flags` verbatim ‖ text, ≤ 100 bytes |

`--mode`, `--cenote N` and `--scrooge` are removed; `--no-flags` stays hidden for the negative
test. The tag is carried in all four combinations. Wire format unchanged (the Perl fixtures
still replay).

- [x] `yolo/`: collapse `work.rs`/`main.rs`/`stratum.rs` to the two flags; tests become the payout × text grid; `tests/regtest.rs` covers all four cells + `--no-flags` + the 100-byte boundary; README/CHANGELOG (v0.13.0) rewritten; `legacy/perl/README.md` explains why three became one
- [x] `ycash-dd`: devnet `--stratum` loses `--stratum-mode`/`--mode` (seat always mines to node 4's payout address via the username; `--text` exposed as `--stratum-text`); `yellowback_stratum.py` iterates the four cells; scenario 3 / devnet README / pool README yolo row updated; CI `YOLO_COMMIT` bumped
- [x] full re-verification: `cargo test`, `--features regtest`, `stratum-perl-check`, `yellowback_stratum.py`, one `up --role pool --stratum` smoke

## 5. Sequencing

```
Y0 ──┬── Y1 (Rust core; unit tests only) ──┐
     └── Y2 (Python miner vs Perl; fixtures) ─┴── Y3 (parity) ── Y4 (devnet seat) ── Y5 (functional) ── Y6
```

Y1 and Y2 run in parallel and do not touch the same repo. Y3 needs both. Y4 needs Y2 and a
building Y1 (it can start against Y1's first `--mode solo` before parity). Y5 needs Y4's seat
only for convenience; it drives `yolo` directly.

## 6. Budgets and constraints

- **No node changes.** Nothing in this plan touches `ycash-dd/src/`. If yolo needs a node
  behaviour that is missing, that is a finding for §7, not a patch: the point is to test the
  node as pools will meet it.
- The Python miner is a fixture: correctness over speed; no C extensions, no GPU.
- `yolo` must not depend on anything Yellowback-specific to *function*: a plain Ycash node
  without `-yellowback` yields empty `coinbaseaux.flags` and yolo behaves as the Perl did.
  Yellowback shows up only in the tag log line and `/status`.
- Rust dependency count ≤ 10 direct crates; no OpenSSL; builds on macOS arm64 and Linux x86_64.

## 7. Findings (Y-F rows; mirrored in `docs/mapping.md` §17)

| # | Finding | Consequence / fix |
|---|---|---|
| Y-F1 | Perl `cenote` rebuilds the coinbase scriptSig as height-push + text (`ref/yolo/cenote:522`), discarding the node's extranonce and with it the Yellowback tag. `stratumsolo` and `stratumpool` keep the scriptSig. | The Rust `cenote` mode appends `coinbaseaux.flags` after the height push (`pool/README.md` carrier 3). Pinned by the negative case in `yellowback_stratum.py`. |
| Y-F2 | The Perl refreshes work on height/target/saplingroot changes only; a Yellowback coinbase also changes when the quote moves, so a pool serves a stale (still valid) price for up to one poll. | Rust polls at 1 s as before and re-issues work when `coinbaseaux.flags` changes. Cost: one extra `mining.notify` per quote update (agents publish at most every few blocks). |
| Y-F4 | The Perl reports every non-JSON `submitblock` outcome as accepted: `node_rpc` returns nothing for a non-JSON reply, so `$resp eq ''` (`stratumsolo:126`) matches `Block decode failed`, `time-too-old`, `high-hash`; the reject branches at `:117-125` are dead code. Observed on regtest. | Rust maps the verdict itself: `result: true` only on `null`; the string is logged and counted. |
| Y-F5 | The Perl stamps the header with wall-clock `time()` (`stratumsolo:379`, `cenote:571`), not the template's `curtime`; a chain generated in a burst has median-time-past ahead of the clock and the block is `time-too-old`. | Rust uses `max(template.curtime, now)`. `stratum-perl-check` generates its chain under `setmocktime`; Y4/Y5 will meet this on the devnet whose heartbeat mines in bursts. |
| Y-F6 | `nonce1` is 14 bytes (`sprintf("%04x")` = 2 bytes + `newkey(12)` = 12), not the 16 the Perl's own comment says (`stratumsolo:22,74`); GPU miners size nonce2 from nonce1's length. | Rust emits exactly 28 hex chars; the miner sizes nonce2 as `32 − len(nonce1)`. |
| Y-F7 | Framework solver facts: every `mining.notify` field is already in serialised order, so the 108-byte header is the fields concatenated; `hash_nonce` packs the uint256 as LE u32 words = raw nonce bytes; the template `target` is display (BE) hex, compare the LE block hash to `int(target,16)`. The Perl re-sends the same job with `clean_jobs: true` after `extranonce.subscribe` and again after an accepted submit until its next poll: a client must tolerate both or it re-mines and gets `duplicate`. | Encoded in `stratum-miner`; no solver change. |
| Y-F8 | `stratumsolo` hardcodes port 3334 (`:19`); `cenote` needs `mineraddress=` to be a wallet t-addr for its `ismine` vout scan (`cenote:531-537`). Unpatched `cenote` cannot even produce a decodable block on a tagging node: it assumes the node's scriptSig is exactly 5 bytes (`:522,527`), so with the 37-byte tag the remainder lands in the sequence field and `submitblock` says `Block decode failed`; the "tag dropped, block accepted" outcome needs the length fixed first (`cenote-fixed` in `stratum-perl-check`). | Y-F1 sharpened: the Rust `cenote` parses the real script length; Y5's negative case asserts `found: false` on a *decodable* block. |
| Y-F9 | The node's `getblocktemplate` caches its block for up to 5 s and rebuilds only on a new tip or a mempool change (`ycash-dd/src/rpc/mining.cpp:652-669`); `yed_setquote` does not invalidate it, so `coinbaseaux.flags` keeps the old price until the next block. Verified live. | Y-F2's re-issue works but its latency is bounded by the node: at most one stale-priced template per block. No node patch (§6); recorded for the mining runbook. |
| Y-F10 | `getblock <hash> 1` prints `finalsaplingroot` as a value that is *not* the header field (bytes 68..100 = the template's `lightclientroothash`, ZIP-221 under Heartwood); `ycash-dd/src/rpc/mining.cpp:759-761`. | A pool sends the template field, never getblock's; vectors come from `getblock <hash> 0`. |
| Y-F11 | The 32-byte nonce is serialised raw (nonce1 at header offset 108) but `getblock` displays it byte-reversed, so nonce1 appears at the *end* of the printed nonce. | Pinned by `work::tests::assembled_block_reproduces_block_105_layout`. |
| Y-F12 | Regtest coinbases have two outputs (miner + founders/YDF, `ycash-dd/src/miner.cpp:304`); `generate` blocks write `height ‖ CScriptNum(extranonce) ‖ flags` while templates write `height ‖ OP_0 ‖ flags` (`miner.cpp:328` vs `:725`). The Perl cenote's 5-byte slice is right only for mainnet heights (65536..8388607 = 4-byte push + OP_0). | "Rewrite the payout output" means `vout[0]`; the tag scan is layout-agnostic; the Rust parses the height push length. |
| Y-F13 | Perl block-size cap is 2,097,152 (`stratumsolo:27`) vs the node's `sizelimit` 2,000,000; `stratumpool`/`cenote` cap nothing. Perl compact-size has a gap at 65536..65556 (`stratumsolo:358`). | Rust uses the template's `sizelimit`; `codec::compact_size` is correct. |
| Y-F14 | After an accepted `submitblock`, yolo (like the Perl) kept re-issuing the stale template under new job ids until the next 1 s poll; a fast solver re-solved it and every submit was `inconclusive` (21 rejects in 3 blocks on the devnet). | The miner keys its done-set on prevhash; yolo polls the template immediately after an accepted block (fix in `yolo/` v0.12.x). |
| Y-F15 | `devnet.json`'s `rpc.url` carries the framework's emoji credentials in the userinfo; a non-Python HTTP client rejects the URI. | The devnet passes yolo a bare URL plus user/password. |
| Y-F16 | A stratum seat mining one block per second is 100 % of the 64-block participation window, so scenario 3 steps 4–5 (pause below 60 %, PIN-1) do not trigger unless the seat mines at the heartbeat's cadence. | Documented in scenario step 0: mine one block per heartbeat tick for those steps. |
| Y-F17 | The devnet exported `BITCOIND` only in `up`; `pool N configure` and every other node restart from a fresh shell launched `bitcoind` from PATH. | `load()` exports the recorded binary (`os.environ.setdefault`). |
| Y-F3 | GPU miners solve 192/7 (mainnet) only; regtest is 48/5, so no real miner can drive a regtest pool. | Python stratum client over `test_framework.equihash` stands in; the stratum layer under test is unchanged. |

## 8. Implementation status

| Item | Owner | State | Evidence |
|---|---|---|---|
| Y0 | orchestrator | **done 2026-09-28** | `make status` eleven repos green; commit in the workspace repo |
| Y1 | `yolo-core` | **done 2026-09-28** | `yolo/` 33752f1..4986631: crate, binary, 32 unit + 6 wire tests, clippy clean, release build verified by the orchestrator; hand-run end-to-end in all three modes with the Python miner (solo/pool/cenote tagged, `--no-flags` untagged, 100-byte scriptSig boundary) |
| Y2 | `stratum-miner` | **done 2026-09-28** | `wt/stratum-miner` b02d8c6c9..efacdbe41: `contrib/yellowback/devnet/stratum-miner`, `stratum-perl-check` (solo: tag found; cenote: decode failure; cenote-fixed: tag gone) PASS re-run by the orchestrator; fixtures `stratum-perl-{solo,cenote,cenote-fixed}.jsonl` |
| Y3 | `yolo-integrate` | **done 2026-09-28** | `yolo/` 6f75633..e449094: `tests/regtest.rs` (5 cases, re-run green by the orchestrator in 9.4 s), Perl at `legacy/perl/`, README + CHANGELOG v0.12.0 |
| Y4 | `devnet-stratum` | **done 2026-09-28** | `ycash-dd` 8871bc482, 4c61d5f1d: `up --role pool --stratum [--stratum-mode]`, `pool N stratum start\|stop\|status`, `mine N 4` via `stratum-miner`, `status`/`check`/`down`/`report`; scenario 3 walked in stratum mode (steps 1–5; 132/132 accepted) |
| Y5 | `devnet-stratum` | **done 2026-09-28** | `ycash-dd` 5d115175b: `qa/rpc-tests/yellowback_stratum.py` (exec bit, `BASE_SCRIPTS`, `YELLOWBACK_SCRIPTS`, CI checks out yolo at `YOLO_COMMIT`); `Tests successful` re-run by the orchestrator (portseed 4712). CI unverified until yolo is pushed |
| Y7 | `yolo-onepool`, `devnet-onepool` | **done 2026-09-28** | `yolo/` 121e3b4, 1343013 (v0.13.0: `--payout`/`--text`, 34 unit + 8 wire tests, regtest grid re-run by the orchestrator); `ycash-dd` 129112b1f..30f0ac39f + the `load()` BITCOIND fix: devnet seat without modes, `yellowback_stratum.py` four cells + negative (`Tests successful`, portseed 4717), docs, CI pinned at 1343013; devnet smoke with `--stratum-text` |
| ycashd 6.20.0 | ycash6 plan Phase 7 | **done 2026-10-01**, merged on `main` (`4a28eef`) | Findings in `docs/plans/yellowback-ycash6-plan.md` §6: F-46 `79f51e5` header root from `defaultroots.blockcommitmentshash` → the top-level old names → a non-zero `defaultroots.chainhistoryroot`, else no work (6.20.0 withholds the old names under `-allowdeprecated=none`); F-47 pre-Heartwood with `-allowdeprecated=none` cannot be served (no template field carries the final Sapling root); F-48 `6b9b467` `tests/regtest.rs` starts node A with `-mocktime` instead of `setmocktime`. Regtest grid 6/6 on v4.5.0, 6.20.0, 6.20.0 `-allowdeprecated=none`; `yellowback_stratum.py` green with yolo `4a28eef` on 6.20.0 |
| Y6 | orchestrator | **done 2026-09-28** | `pool/README.md` yolo per-stack section, `doc/yellowback-mining.md` pointer + template-cache note, `role-based-regtest-plan.md` R9, mapping §17 |
