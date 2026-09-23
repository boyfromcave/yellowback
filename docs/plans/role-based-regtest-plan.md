# Role-based regtest plan — walking in each participant's shoes

**Status:** revision 3 (2026-09-20), **in implementation** — see §8 for what is built, what is
running and what remains; every chunk's row there is updated as it lands. Revision 2 scheduled the
work (owner decision D-4). This is a plan for a *testing and feedback* capability, not a change to Yellowback itself:
nothing here touches consensus, mining or policy code. It exists so the product owner can occupy
each seat in the Yellowback economy in turn and give grounded feedback before real attestors are
recruited (v3 plan Phase A7), and so that the comprehensive regression coverage those scenarios
imply exists in CI rather than in someone's terminal history.

## 0. Revision log

### Revision 3 (2026-09-20) — implementation begins; two deviations recorded

| # | Deviation from revision 2 | Why |
|---|---|---|
| I-1 | **Eleven nodes, not ten**, in every role preset: the simulated population is node 9 and the liquidator node 10 in *every* preset, and node 0 is the owner's seat (`user`) or the funding and subscriber node (`attestor`, `pool`). | §3.2 put the population on node 0 in two presets and left it without a node in the third. Scenario 1 step 7 ("someone else's vault claimed … as a bystander") needs the personas' vaults to belong to a wallet that is not the owner's, so the population can never share node 0 with the owner; one map for all three presets is also one map to get wrong. |
| I-2 | **The inherited port helper caps a run at 8 nodes** (`test_framework/util.py`, `MAX_NODES`, asserted in `p2p_port`). The devnet raises it in one place before any port is computed and **writes every node's RPC URL into `devnet.json`**, so the simulator, the regression suite and any other process read ports from the state file instead of recomputing them. | A second process recomputing ports with a different cap would land on different ports silently. Recorded in `docs/mapping.md` §14.2. |
| I-3 | **Risk appetite is the term class.** `yed_mint` always locks exactly the minimum collateral for the class (there is no over-collateralise argument), so "close to the minimum ratio" and "2–3× over-collateralised" are not choices a wallet can make. The leveraged minter takes **class C** (300 %, the longest terms), the conservative minter **class A** (500 %, the shortest), which is exactly the plan's contrast by a different lever. | §3.4 was written as if collateral were a free parameter. It is not; the class ranges are (`src/yellowback/params.cpp`). |

### Revision 2 (2026-09-20) — the owner's four decisions

| # | Decision | Applied |
|---|---|---|
| D-1 | **The attestor scenario is walked twice: GUI *and* headless.** An attestor will likely use the GUI for the initial bond, but operates from the command line thereafter. | §4.2 splits into 2a (the bonding ceremony, GUI) and 2b (operation, `ycash-cli` + the agent). 2b is walked by following `doc/yellowback-attestor.md` literally, so the scenario also tests the operator documentation. |
| D-2 | **Pools stay daemon-first; a dashboard is optional.** Most pools will run `ycashd` as a daemon. | §4.3 is unchanged in emphasis; the optional read-only view becomes R8, a terminal status view rather than a GUI page, explicitly deferred and not blocking. |
| D-3 | **The simulated users must be realistic**, not a random action walk. | §3.4 replaced with six personas, including a third-party liquidator — without which nobody ever claims an underwater vault and the attested price has no consequence. |
| D-4 | **Build it now.** Comprehensive regtests are wanted immediately; "before or alongside A6" is not a distinction worth drawing. | §6 reordered and the regression script promoted from a footnote to its own chunk (R7). |

### Revision 1 (2026-09-20) — first draft

The triangle, the one-manual-seat rule, the three gaps, the three scenarios, R1–R6.

**Audience:** whoever implements this, and the owner walking the scenarios. Read
[`yellowback-v3-development-plan.md`](yellowback-v3-development-plan.md) §5 (the devnet) and
§3.1 (the regtest parameter column) first; this plan is a layer on top of the devnet that
landed with A4.

---

## 1. The problem

Yellowback has three participants whose incentives only make sense in relation to each other:

```
                         minters and holders
                        (mint YED, redeem, claim)
                                  ▲
                                 ╱ ╲
     price they can mint at     ╱   ╲     price their vaults are judged at
                               ╱     ╲
                              ╱       ╲
              mining pools ◄──────────► bonded attestors
             (quote, signal, mine)    (sign prices, post bonds)
                   the min/max combination of the two populations
```

Today the devnet automates **all three** so that the chain arms itself and a GUI demo works.
That is right for a demo and wrong for feedback: the owner cannot experience being any one of
them, because the devnet is doing all of it for them.

What we want instead is **one seat left empty for you, and only one.** Sitting in a seat means
doing that participant's work with that participant's tools, at that participant's tempo, while
the other two vertices carry on without you — including carrying on *badly* when you stop
doing your job, which is where most of the learning is.

### 1.1 The rule that makes this work

> **Exactly one seat is manual. Everything else runs on a timer, including the chain itself.**

The corollary matters as much as the rule: in every scenario the world must keep moving while
you think. Blocks must arrive, prices must drift, other people's vaults must be minted and
redeemed and liquidated. A chain that only advances when you type `mine` teaches you nothing
about what it feels like to be a participant, because real participants never have that power.

---

## 2. What exists today, and the three gaps

Landed with A4 (`ycash-dd/contrib/yellowback/devnet/yellowback-devnet`, v3 plan §5):

| Capability | State |
|---|---|
| Eight-node regtest that arms itself (0 user, 1 stock, 2–4 pools, 5–7 attestors) | **works** |
| Pool price quotes — `yed_setquote`, or one real `yellowback-quote --mock-price` per pool (`up --agents`) | **works** |
| Attestors — three real `yellowback-attest attest` processes on the `dir` transport, one `subscribe` beside node 0 | **works** |
| Attestor outage and divergence demos — `attestor N stop\|start\|price USD` | **works** |
| Emergency notice — `notice VAULTTXID` | **works** |
| Health check — `check` asserts ARMED, `poolFresh ≥ M_SELECT`, agents alive | **works** |
| Launch YecWallet against node 0 — `wallet` | **works** |

The gaps, all three of which are *tooling*, not product:

| # | Gap | Why each scenario needs it |
|---|---|---|
| **G1** | **No heartbeat.** Blocks appear only when you run `mine N`. | Every scenario. Without it you are simultaneously the participant *and* the miner of every block, which destroys the illusion in all three seats. |
| **G2** | **No synthetic user traffic.** Nothing mints, redeems, sends or claims on its own. | Scenarios 2 and 3. An attestor with no one to price for, and a pool with no transactions to include, are both inert. |
| **G3** | **No role presets.** The devnet automates all three vertices unconditionally, and `wallet` always points at node 0. | All three. Each scenario needs one participant *deliberately left unautomated* and the GUI pointed at that participant's node. |

A fourth, smaller gap: **the market never moves.** `price USD` is a step change you trigger by
hand. Real participants experience drift and the occasional shock. Scenario realism — especially
liquidation, which is the emotional core of the product — depends on a price that wanders.

---

## 3. Design

### 3.1 Role presets

`up` gains `--role {user,attestor,pool,none}` (default `none` = today's fully-automated demo).
The preset decides three things: which nodes start and as what, which participant's automation
is *withheld*, and where `wallet` points.

| Preset | Your seat | Your node | Withheld from the automation |
|---|---|---|---|
| `user` | a minter and holder of YED | 0 | nothing — pools, attestors, heartbeat, price walk and the simulated population all run |
| `attestor` | one bonded attestor | 8, unregistered at `up` | your registration, your bond, your agent |
| `pool` | one mining pool | 4, with no payout address and no signalling | your quote, your signalling, your blocks |
| `none` | — (today's behaviour) | 0 | nothing; no simulator, no heartbeat |

`status` prints a banner naming your seat and your node, because the single most likely mistake
in this whole design is driving the wrong node.

### 3.2 Node budget

Ten nodes in every role preset. The allocation shifts, the count does not:

| Node | `user` | `attestor` | `pool` |
|---|---|---|---|
| 0 | **you** (minter) | sim population | sim population |
| 1 | stock (no `-yellowback`) | stock | stock |
| 2–4 | 3 pools, automated | 3 pools, automated | 2 pools automated, **4 is you** |
| 5–7 | 3 attestors, automated | 3 attestors, automated | 3 attestors, automated |
| 8 | 4th attestor, automated | **you** (attestor) | 4th attestor, automated |
| 9 | sim liquidator | sim liquidator | sim liquidator |

The counts are forced by the regtest parameters (`src/yellowback/params.cpp`, v3 plan §3.1):
`ATTEST_ARM_MIN = 3`, `N_SLOTS = 5`, `M_SELECT = 2`, `K_SLACK = 1`.

- **Four attestors, not three.** If you occupy one of only three slots and stop signing,
  `poolFresh` falls to exactly `M_SELECT` — minting still works, but with zero slack, so any
  hiccup in the other two looks like *your* fault. A fourth keeps a real margin and makes your
  absence legible rather than catastrophic. `N_SLOTS = 5` leaves room.
- **Three pools, not four.** If your pool stops signalling, 2 of 3 = 67 % stays above the 60 %
  minting-pause threshold, so the chain survives you — and stopping a second crosses the
  threshold deliberately. That is a scenario, not an accident.
- **A separate liquidator node** because claiming your own vault is a different path from a
  third party claiming an underwater one (§3.4).
- **The stock node stays stock.** It is the evidence that a node without `-yellowback` is
  unaffected, and borrowing it for a persona would destroy that.

Ten `ycashd` processes plus up to seven agent and simulator processes is the ceiling. The A4
devnet already runs eight nodes comfortably on a laptop, but `up --role` should print the
expected footprint before it starts, and `--lean` should drop the price walk and halve the
heartbeat rate for a constrained machine.

### 3.3 The heartbeat (G1)

A `yellowback-devnet heartbeat` process: mines one block every *N* seconds (default 15),
round-robin across the **automated** pools only, so your pool's blocks are always yours to mine.

- Started by `up` unless `--no-heartbeat`; `heartbeat {start|stop|rate N}` controls it live.
- Logs to `<dir>/heartbeat.log`; `status` reports its rate and last block.
- **Stops when `check` would fail**, to avoid burying a broken devnet under a thousand blocks,
  and says why in the log.

15 s per block against regtest windows (`REF_LAG = 2`, `ATTEST_MAX_AGE = 8`,
`attestInterval = 4`, `DORMANCY_CHECK = 4`) makes an attestation tick about every minute and a
dormancy evaluation about every minute — slow enough to watch, fast enough to feel alive.
`rate` exists because the pool scenario wants it faster and the user scenario slower.

### 3.4 Synthetic users (G2) — personas, not a random walk

A random action walk produces a Positions list where every vault looks the same, and a chain
where nothing ever quite goes wrong. `yellowback-sim` instead runs **personas**: each is a small
strategy with its own risk appetite, its own cadence, and its own characteristic failure. The
RNG is seeded, so a run is reproducible and a bug found in one is reproducible in another.

| Persona | Behaviour | Why it is in the set |
|---|---|---|
| **the leveraged minter** | mints close to the minimum collateral ratio, on the longest term, and never redeems early (a vault cannot be topped up: v2 plan V15) | the first to go underwater on a downswing — it is what makes liquidation happen *to someone* without anyone staging it |
| **the conservative minter** | over-collateralises 2–3×, short terms, redeems at maturity | the happy path, and the contrast that makes the leveraged one legible in a Positions list |
| **the exiter** | redeems the moment `lockHeight` passes; releases VOID vaults with `yed_redeem` | exercises the exit path and keeps supply from growing without bound |
| **the trader** | never mints; holds YED and moves it between addresses with `yed_send`/`yed_sendmany` | transfer payloads, balances, and the fact that most YED holders are not minters |
| **the liquidator** | watches every vault it does not own, posts `yed_claimnotice` when one is underwater, and claims after `EMERGENCY_PERSIST` | **the economically essential one.** Without a third party willing to claim, an underwater vault just sits there and the attested price has no consequence at all — which would quietly gut both the attestor and pool scenarios |
| **the absentee** | mints, then goes quiet: leaves carriers outstanding, never sweeps, never redeems | orphaned carriers, `yed_sweepcarriers` housekeeping, and what an abandoned vault looks like from outside |

**The liquidator must be a different wallet from the minters.** Claiming your own vault is a
different code path (clause (a), the owner path) from a third party claiming an underwater one
(clause (b)), and only the second is the one the price actually governs. So the simulator drives
**two** wallet nodes: a *population* node hosting the five minter/holder personas on distinct
addresses, and a *liquidator* node that owns none of their vaults.

**Honest about failure.** A refused action — `bundle-insufficient`, `mint10-diverged`,
`notice-not-underwater`, `insufficient-yec` — is logged and counted, never retried blindly,
because those refusals are precisely the signal the attestor and pool scenarios exist to show
you. `sim stats` prints the tally per persona, and a persona whose actions are *all* failing is
reported loudly rather than left to look busy.

**Two-step aware.** Every bundle-carrying command is two-step (A3, W7), so each persona either
uses `wait=false` and completes on a later block, or relies on the heartbeat to mine its carrier
(`two_step` in `test_framework/yellowback_attest.py`). Without the heartbeat the simulator would
deadlock, which is why R1 comes first.

### 3.5 The price walk (G4)

`price --walk` starts a random walk (configurable drift, volatility and tick) that writes both
the pool quote and every automated attestor's mock price file, keeping the two populations
*honestly* in agreement while both move. `price --shock -35%` applies a step. `price --walk stop`
freezes it.

This is what makes liquidation reachable without hand-crafting it: let the walk run with
negative drift and vaults go underwater on their own, which is the only way to see the claim
path the way a real holder would.

Divergence between the two populations stays a deliberate act (`attestor N price USD`), because
that is an attack, not weather.

### 3.6 Pointing the GUI

`wallet` gains `--node N` (default: the preset's seat). The existing macOS-only path lookup
should also accept `YELLOWBACK_WALLET_BIN`, since two of the three scenarios want the GUI open
on a node other than 0 and one may want two GUIs side by side.

---

## 4. The scenarios

Four walk-throughs across three seats (the attestor is walked twice, D-1). Each runs start to
finish in about half an hour, with a checklist of what to notice — the value is in the noticing,
so each ends with the questions we actually want answered.

### 4.1 Scenario 1 — "I want to mint"

```bash
yellowback-devnet up --role user
yellowback-devnet wallet          # opens on node 0
```

**Automated:** 3 pools quoting and signalling, 4 attestors signing, heartbeat at 15 s, price
walking gently.

**Walk-through.**
1. Open the Yellowback tab. Read the Overview before touching anything: is it obvious the
   system is live, activated, and armed? Is it obvious what YED *is*?
2. Mint 100 YED against YEC. Watch the two-step carrier: **does the wallet explain the pause,
   or does it just look stuck?** This is the single most suspicious moment in the product.
3. Look at the price the mint was offered. Three numbers are in play (pool median, attested
   quantile, and the `min` of the two). Does the GUI make the relationship legible, or does it
   present one number and hope?
4. Let the walk run. Watch Positions as your collateral ratio moves.
5. Redeem one vault at maturity. Send YED to another address.
6. Let the price fall (`price --shock -40%`) and watch your own vault approach liquidation.
   **Does the wallet warn you early enough to act?**
7. Let someone else's vault be claimed by the simulator and see what, if anything, you learn
   about it as a bystander.

**What we want to know.** Where does a first-time minter hesitate? Is the collateral ratio
comprehensible without reading the docs? Does the emergency path frighten people appropriately
without frightening them away?

### 4.2 Scenario 2 — "I am an attestor"

Walked **twice** (D-1), because that is how a real attestor will meet the product: the bond is a
one-off ceremony where a GUI earns its place, and everything after it is a server that has to
keep running for `bondMinLock` blocks. A design that is pleasant in one half and hostile in the
other is not a design an operator will accept.

```bash
yellowback-devnet up --role attestor
```

**Automated:** 3 pools, 3 other attestors, heartbeat, price walk, and the full simulated
population minting and being liquidated against the prices you help set.

#### 4.2a The bonding ceremony (GUI)

```bash
yellowback-devnet wallet          # opens on node 8, your attestor node
```

1. Open the **Attestors** page. Before registering, read it as someone who has not read the
   spec: is it clear what an attestor *is*, and what you are about to commit?
2. Register (`btnRegister` → `yed_registerattestor`). The bond locks for `bondMinLock = 200`
   blocks and earns nothing while locked. **Is that clear before you click, or only after?**
3. The wallet warns to back up `wallet.dat` — both keys come from the keypool and a backup taken
   a minute earlier does not contain them. **Is that warning proportionate to the consequence?**
   Losing it loses the bond.
4. Wait out `BOND_MATURITY` (8 blocks, ~2 min at the default heartbeat) and watch PENDING →
   ELIGIBLE, then the arming delay.

#### 4.2b Operation (headless)

Now close the GUI and **follow `doc/yellowback-attestor.md` literally**, using only
`ycash-cli` and the agent. The scenario is as much a test of that document as of the software:
if a step is missing, ambiguous, or assumes knowledge the reader does not have, that is the
finding. Its "Quick reference" table is the checklist.

```bash
yellowback-devnet cli --node 8 -- yed_listattestors
yellowback-attest attest --conf attest.toml       # your agent, run by you, in your terminal
```

1. Configure and start your own agent against the mock price, so you choose what you attest.
   `yellowback-attest sources --conf …` and `check-config` before `attest`, as the doc says.
2. Watch your `seq` get selected for real transactions (`yed_getselection`) and the attest fee
   arrive when it is. Is the connection between "I signed" and "I was paid" visible from the
   command line alone?
3. **Stop signing.** Watch DORMANT arrive after `DORMANCY_BLOCKS`, then revive with
   `yed_revive`. Does anything warn you *before* dormancy, or only after?
4. Attest 20 % away from the others and watch your attestations dropped from selections while
   the honest three carry on.
5. Try `yed_withdrawbond` before the locktime (`bond-locked`), then after.
6. Kill the agent uncleanly and restart it: the equivocation guard (S16) must refuse to sign a
   second price for a height you already signed. **This is the failure that ejects a real
   attestor**, so it is worth provoking deliberately.

**What we want to know.** Is the economic proposition legible — what you risk, what you earn,
what gets you ejected? Would a competent operator run this for a year? This scenario is the
dress rehearsal for A7 recruiting, and its output should shape the recruiting pitch.

### 4.3 Scenario 3 — "I am a mining pool"

```bash
yellowback-devnet up --role pool
# no GUI: pools are headless, which is the point
yellowback-devnet cli --node 4 -- yed_getinfo
```

**Automated:** 2 other pools, 4 attestors, heartbeat on the *other* two pools only, price walk,
the simulated population and liquidator.

Pools are **daemon-first** (D-2): this scenario is deliberately a terminal one, because that is
how a pool operator will actually meet Yellowback — as one more process, one more config file
and one more thing that can page them at 3 a.m. Any dashboard is a convenience layered on that,
never a substitute for it (R8).

**Walk-through.**
1. Start with your pool configured as a plain miner: no payout address, no signalling. Mine a
   few blocks. Observe that your blocks carry no quote (MINER-2) and you earn no Yellowback fees.
2. Configure the payout address and `-yellowbacksignal=1`, restart, mine again. Watch
   `yed_listminers` move you to registered and then eligible, and watch fees start arriving.
3. Run the real pool price agent (`yellowback-quote --conf … --mock-price …`) instead of
   `yed_setquote` by hand — the path an actual pool runs. Kill it and watch your quote go stale
   past `-yellowbackquotemaxage`.
4. **Stop signalling.** With 2 of 3 pools still signalling you stay above the 60 % threshold.
   Now stop a second (`--role pool` should expose a way to do this) and watch minting pause,
   then rejection pause below 50 %, then recovery at 75 %/60 %.
5. Quote a constant price while the attestors move and watch PIN-1 pin your pool.
6. Read `doc/yellowback-mining.md` as a pool operator would, and see whether it answers the
   questions this exercise raised.

**What we want to know.** Is the operational burden on a pool acceptable — one more agent, one
more config, one more thing to monitor? Are the failure modes discoverable from `yed_getinfo`
alone, without a dashboard, since that is what a daemon operator has? A pool that finds this
annoying simply will not run it, and the whole design rests on pools running it.

If the answer to "discoverable from `yed_getinfo` alone" turns out to be *no*, the fix is more
likely to be better fields and a clearer mining runbook than a GUI — which is exactly the
finding R8 is waiting on before anything is built.

---

## 5. Feedback capture

A scenario you cannot report on is a scenario wasted. Each run writes
`<dir>/session-<role>-<date>/` containing the devnet state, every agent log, the simulator's
tally, and a `NOTES.md` seeded with the walk-through checklist so observations can be typed
against the step that prompted them. The simulator's seed goes in the header, so a scenario that
produced an interesting liquidation can be replayed exactly.

`yellowback-devnet report` bundles that directory into something attachable, with the parameter
set and both fork commits recorded at the top, so a note from three weeks ago can be placed.

Findings graduate into the v3 plan (a new §6.2, "found by walking the roles") and, where they
are impedance mismatches rather than product feedback, into `docs/mapping.md`.

---

## 6. Implementation

**Scheduled now, alongside A6 (D-4).** The two do not contend: A6 is hardening, measurement and
the review document in `ycash-dd/src` and `doc/`; this is `contrib/` and `qa/` tooling. They
share only the owner's attention, and the scenarios are what generate the feedback A6's review
document should be answering.

Eight chunks. R1–R3 are the minimum that makes any scenario work at all; R7 is what makes this
a regression suite rather than a demo, and ships with them rather than after.

| # | Chunk | Deliverable | Effort |
|---|---|---|---|
| R1 | Heartbeat (G1) | `heartbeat` process and subcommand; `status` reports it; halts on a failing `check` and says why | ~0.5 d |
| R2 | Role presets (G3) | `up --role`, the ten-node maps of §3.2, `wallet --node`, the seat banner, `--lean` | ~1.5 d |
| R3 | Personas (G2, D-3) | `yellowback-sim`: six personas over a population node and a separate liquidator node, seeded, two-step aware, per-persona failure tally | ~3 d |
| R4 | Price walk (G4) | `price --walk`, `--shock`; both populations move together and honestly | ~0.5 d |
| R5 | Scenario scripts | the four walk-throughs (1, 2a, 2b, 3) as runnable checklists; session directory and seeded `NOTES.md` | ~1 d |
| R6 | Docs | `contrib/yellowback/devnet/README.md` role section; a "walking the roles" page; the 2b walk-through cross-checked against `doc/yellowback-attestor.md` | ~0.5 d |
| **R7** | **Regression suite** | `qa/rpc-tests/yellowback_devnet_roles.py` — see below | ~1.5 d |
| R8 | *(optional, deferred)* pool status view | a terminal `pool` view over `yed_getinfo`/`yed_listminers`. **Not built until Scenario 3 says it is needed** (D-2) | ~1 d if wanted |

About 8–9 days of work excluding R8, and R1/R2/R4 are independently useful the day they land.

### 6.1 R7 — the comprehensive regression suite

This is the deliverable that outlives the feedback exercise, so it is a chunk, not a footnote.
`yellowback_devnet_roles.py` (nightly, `EXTENDED_SCRIPTS`) brings up each preset in turn and
asserts, for each:

- the right seat is **empty** and every other participant is automated — the preset's node map
  matches §3.2, your node holds no registration/payout/quote as the preset promises;
- the heartbeat advances the chain **without any help from the test**, and only on the automated
  pools;
- the simulator's personas each perform their characteristic action at least once over a fixed
  block budget, and the per-persona failure tally is within expected bounds — in particular
  **the liquidator actually liquidates something**, which is the assertion that proves the
  attested price has consequences;
- the price walk moves both populations together and never manufactures a divergence;
- `check` passes at the end, and the state hash agrees across every enforcing node.

It runs with a fixed seed so a failure is reproducible, and it is the regression test for
everything in this plan. Like `yellowback_attest_agent.py` it needs the Rust binary, so it SKIPs
without one and the nightly job builds the crate first.

**Constraints inherited from the devnet.** Zero C++ (`contrib/` and `qa/` only); the frozen-file
set stays at zero delta against `feature/yellowback-sf`; the naming rules apply (Yellowback the
system, YED the unit); and the simulator is never a load test — it exists to make the world feel
inhabited, not to measure throughput. DoS and cost measurement is A6's job with purpose-built
scripts.

---

## 7. Decisions taken, and what is still open

The four questions raised in revision 1 were answered by the owner on 2026-09-20 and are
recorded as D-1 to D-4 in §0. In short: **both** GUI and headless for the attestor; pools stay
daemon-first with any dashboard optional and evidence-led; the simulated users get real
personas; and the work starts now.

Still open, and each answerable by walking a scenario rather than by discussion:

1. **Does the leveraged minter persona produce liquidations at a believable rate?** Too many and
   the product looks dangerous; too few and Scenario 1's most important moment never arrives.
   The price walk's drift and volatility are the knobs; expect to tune them once against a real
   walk-through.
2. **Is one liquidator enough?** A single one always wins the race. Two would show the
   competition a real claim path has, which is a materially different experience for the vault
   owner watching it happen.
3. **Should the personas persist across `up` runs?** A chain with history — vaults minted weeks
   ago, an attestor who has been dormant twice — is more instructive than one born five minutes
   ago, but it means a seeded replay of prior blocks at startup and a slower `up`.

---

## 8. Implementation status

Updated as each chunk lands. "Built" means the code exists on `feature/yellowback-price-attest`
in `ycash-dd`; "verified" means it was run end to end on one laptop and the result is recorded.

| # | Chunk | Status | Where | Notes |
|---|---|---|---|---|
| R1 | Heartbeat | **built, verified** | `contrib/yellowback/devnet/yellowback-devnet`: `heartbeat {start\|stop\|rate N\|status}`, `up --heartbeat-rate N`, `--no-heartbeat`; `<dir>/heartbeat.log`, `heartbeat.json`; `status` reports it | Halts on `liveness()` (narrower than `check`: F-1), and deliberate `attestor N stop` / `pool N quote stop` are recorded so they do not halt it (F-2). Run at 15 s, 3 s and 2 s per block |
| R2 | Role presets | **built, verified** | `up --role {user,attestor,pool}` (eleven nodes, I-1), the seat banner in `status`, `wallet --node N` and `YELLOWBACK_WALLET_BIN`, `--lean`, the footprint line, `pool N {configure\|signal on\|off\|quote start\|stop}`, `attestor 8` refused on the attestor seat, `attest-8.toml` template | RPC URLs published in `devnet.json` (I-2). `up --role user` ran end to end: ARMED at 250 with 4 attestors, 3 subscribers (nodes 0, 9, 10), heartbeat, walk and simulator up, `check` green |
| R3 | Personas | **built, verified** | `contrib/yellowback/devnet/yellowback-sim` (six personas, seeded, per-persona tally in `<dir>/sim-stats.json`, `sim stats` shouts at an all-failing persona); started by `up --role`, `sim {start\|stop\|stats}`; profiles `demo` / `fast` | Risk appetite is the term class (I-3). On the first run every persona acted within two minutes; after a −70 % shock the liquidator posted notices on and **claimed three class C vaults** (the absentee's and both of the leveraged minter's) by clause (a). Refusals seen and tallied honestly: `insufficient-yec` (single-coin wallet, F-3), `mintpol-global-ratio` after the shock, one mempool-settle race |
| R4 | Price walk | **built, verified** | `price --walk [start\|stop] [--drift] [--vol] [--tick]`, `price --shock=PCT`, `up --walk-*`, `--no-walk`; `<dir>/walk.log` | Writes the pools' mock file and every automated attestor's together; the seat's attestor file is never written. `--shock` must be written with `=` (F-4) |
| R5 | Scenario scripts | **built** | `contrib/yellowback/devnet/scenarios/{1-user,2a-attestor-gui,2b-attestor-headless,3-pool}.md`; `scenario [NAME]`; `up --role` creates `<dir>/session-<role>-<date>/NOTES.md` seeded with the role's checklist(s), seed and fork commits; `report` writes `REPORT.md` and a tarball | Verified: `scenario`, the seeded `NOTES.md` and `report` (tarball with session, `devnet.json`, tally, every agent log and every node's `debug.log`). The walk-throughs themselves are the owner's to walk (§4) |
| R6 | Docs | **built** | `contrib/yellowback/devnet/README.md` (new: commands, the rule, the node map, heartbeat, walk, personas, pool and attestor seats, sessions, the suite); `doc/yellowback-devnet.md` (the stale "v3 not built" text replaced, a §5 on walking the roles); `contrib/yellowback/README.md` row; `docs/mapping.md` §14.2 (seven rows) | The 2b walk-through cites `doc/yellowback-attestor.md` step by step and leaves that document unchanged: reading it *is* the test |
| R7 | Regression suite | **built, green** (after the F-7 fix) | `qa/rpc-tests/yellowback_devnet_roles.py`, executable, in `EXTENDED_SCRIPTS`, run by the nightly job after the agent script and named in the audit's allow-list | Drives the devnet script itself; per preset: seat empty, heartbeat on automated pools only, every persona's characteristic action, a redeem at maturity, the shock and the liquidator's claim, walk agreement, `check` before the shock, every node alive, state hash and liveness after. First full run (2026-09-20, seed 7): all three presets passed every assertion up to and including the liquidator's clause-(b) claim, then **found F-7** (the claimant's node segfaulted on its next RPC). After the fix the `user` preset is green end to end; §8.2 has the runs |
| R8 | Pool status view | deferred (D-2) | — | not built until Scenario 3 asks for it |

### 8.2 Runs of the regression suite (2026-09-20, seed 7, heartbeat 2 s, `fast` personas)

| Preset | Seat empty | Heartbeat | Walk | `check` | Personas | Redeem at maturity | Shock and liquidation | End state |
|---|---|---|---|---|---|---|---|---|
| `user` | ✔ (11 nodes, 4 attestors, 3 pools eligible, node 0 funded) | ✔ 6 blocks on 3 automated pools | ✔ pools = attestors, moving | ✔ | ✔ every minter minted, the trader moved YED | ✔ | notice + clause-(b) claim of a persona's vault returned success; **node 10 then segfaulted (F-7)** | red on F-7 |
| `pool` | ✔ (node 4 a plain miner, 2 pools eligible) | ✔ on nodes 2 and 3 only | ✔ | ✔ | ✔ | ✔ | same as `user`, on the leveraged vault | red on F-7 |
| `attestor` | ✔ (node 8 funded, unregistered, no agent, conf template written; 3 attestors) | ✔ | ✔ (node 8's price file untouched) | ✔ | ✔ | ✔ | same | red on F-7 |

Everything the plan asked the suite to prove about the *tooling* held on all three presets; the
one red assertion was a node defect the tooling found, fixed the same day (F-7). **After the
fix** (seed 7 again): `user` **PASSED** end to end — liquidated by clause (b), tally absentee 1 /
conservative 6 / exiter 15 / leveraged 2 / liquidator 3 / trader 36, heartbeat alive, one state
hash on 10 enforcing nodes, nothing pinned; `attestor` **PASSED** (liquidator 4, trader 34, state
hash agreed at 441) and `pool` **PASSED** (liquidator 4, exiter 17, state hash agreed at 446) the
same way. The suite is green on all three presets with the fix. Two suite bugs were fixed along the way
(`yed_gettag` wants its height as a string; the vault lookup on node 0 must wait a block for the
index), and the suite gained "every node alive at the end" so F-7 is named, not inferred.

### 8.1 Found while building

Each also has a row in `docs/mapping.md` §14.2.

| # | Found | Fix |
|---|---|---|
| F-1 | §3.3 said the heartbeat "stops when `check` would fail". `check` asserts `mintingAllowed`, and the scenarios' central move — a price shock — halts minting for a window (`DIVERGENCE`, then `GLOBAL_RATIO`). A heartbeat gated on `check` stops exactly when the chain must keep moving | The heartbeat gates on a narrower `liveness()`: node 0 up, activation active, ARMED, automated agents alive. The regression suite runs `check` before the shock and asserts only the state hash and liveness after |
| F-2 | On the first run, `attestor 5 stop` — the outage demo the plan asks for — killed the heartbeat five seconds later: `HALTING: attest-5 is dead` | Deliberate stops (`attestor N stop`, `pool N quote stop`) are recorded in `devnet.json` (`stopped_agents`); the heartbeat and `check` ignore them; `start` clears the record |
| F-3 | The population wallet was funded with one 260 YEC coin. A two-step mint spends the whole coin and its change is unconfirmed for a block, so every other persona refused with `insufficient-yec: have 0.00 confirmed and unlocked` for a block after each action | `up` funds the population and the liquidator as six coins each; the personas that share a wallet also serialise their spending calls |
| F-4 | `price --shock -70%` is refused by `argparse`, which reads `-70%` as a flag | `price --shock=-70%`; the help text and the docs say so |
| F-5 | The `pool` command's docstring used `%d` with a `%`-format and crashed on the `%` in `60 %` | Plain text |
| F-7 | **The claimant's node segfaults on the RPC after a clause-(b) claim.** Twice out of two runs of the regression suite (`user` and `pool` presets, seed 7): the liquidator's `yed_claim` by clause (b) returned success (`CommitTransaction` and `Relaying wtx` logged on node 10), and the *next* two-step RPC on that node, a few hundred milliseconds later — a second `yed_claim` in one run, a `yed_claimnotice` in the other — died with `EXC_BAD_ACCESS` at address `0x8` in `CScript::IsPayToScriptHash` ← `Solver` ← `IsMineInner` ← `CWallet::IsMine(CTxOut)` ← `CWalletTx::IsTrusted` ← `CWallet::AvailableCoins` ← `yellowback::Context::SelectYec` ← `yellowback::BuildCarrier` ← `CarrierStep` ← `yed_claim` (macOS crash reports `ycashd-2026-09-20-141847.ips`, `…-143053.ips`). `IsTrusted` reads `parent->vout[prevout.n]` for each input of an unconfirmed own transaction; a fault at `0x8` with `n = 0` means a wallet transaction whose `vout` is **empty** — the just-committed claim's parent at index 0 is either the vault outpoint (not this wallet's) or the carrier. Clause (a) claims (three in a row in the manual run, §8 R3) never crashed. **The claim was lost:** the node died before the transaction left it, so on every other node the vault stayed ACTIVE with the notice standing (verified on the pool devnet's node 0 after the run: `ACTIVE`, `noticed: true`, no CLAIMED vaults) — and `notice-standing` then blocks a second notice for `EMERGENCY_NOTICE_TTL` blocks | **Fixed the same day** (owner decision, 2026-09-20). Root cause: the inherited `CWallet::CommitTransaction` "notifies that old coins are spent" with `mapWallet[txin.prevout.hash]` — safe upstream, where a wallet only spends its own coins; for a claim the vault output belongs to the vault owner, so `operator[]` inserted a **blank `CWalletTx`** (no inputs, no outputs, depth −1) under the vault's id, and the first trust walk over the unconfirmed claim read its empty `vout[0]`. `src/wallet/wallet.cpp` is in the zero-delta set, so the fix is on the fork's side: `YellowbackWallet::Commit` (`src/yellowback/wallet.{h,cpp}`) records which inputs the wallet does not hold, calls `CommitTransaction`, and erases the blank entries it left; both fork commit sites use it. Regression case in `yellowback_attest_wallet.py` (the clause-(b) claim is followed by `gettransaction`, `getbalance` and `yed_listunspent` while unconfirmed). Verified: the `user` preset of the suite is green (liquidation by clause (b), every node alive, one state hash), and the liquidator's next notice, the call that used to kill the node, went through two seconds later. The same trap would have hit `yed_withdrawbond` from a restored wallet, whose bond transaction is not in `mapWallet` either |
| F-8 | **Scenario 1, walked by the owner (2026-09-20/21).** The global-ratio halt after a −40 % shock stopped every mint, including a 500 % one that would have raised the ratio | Product decision D-R-3 / v3 plan W16: `RECAP_RATIO_BPS`; class A mints through the halt. Node, model, tests, contract, docs and the wallet's Mint page (limit banner, greyed-out classes) changed 2026-09-21 |
| F-9 | Scenario 1 step 1: the Overview's attestation line was clipped ("ARMED — mints and"); step 3: the Mint page's "price sources" and "attestors reachable" values wrapped into one clipped line | The two form layouts wrap long rows and the three labels grow with their text; a QTest (`longValueLabelsAreNotClipped`) asserts each gets the height its text needs at a 720 px window |
| F-10 | Scenario 1 step 4 could not be walked: the Positions page shows no collateral ratio for the owner's own vault, only the global one | Positions gained **Ratio now** (collateral at the claim price over the debt, red below 110 %, orange below 150 %) and **Underwater below** (`underwaterAt`) |
| F-11 | Scenario 1 step 5: a `yed_send` to one of the wallet's own addresses listed as "Sent $0.00" | `amountCents` is the net effect on the wallet, 0 for a self-send, which is correct and read as a fault. The row is now labelled **self-transfer** with a tooltip saying why the amount is $0.00 |
| F-12 | Scenario 1 step 6: the "Minted. txid: …" line stayed on the Mint page through the price shock | Cleared two blocks after the mint (the notice and the Transactions list carry the record) |
| F-13 | Scenario 1 step 7 (from `sim stats`): the simulated liquidator ran its 400 YED inventory dry (`insufficient-yed x6`) and could not claim a third vault | Inventory 1,000 YED, topped up with a class A mint when spendable YED falls under 300 — the class that W16 keeps open during the halt the crash produces |
| F-14 | The owner's second `up --role user --force` died at node 8 with `500 Internal Server Error` during the start-up poll: a node from the previous day's devnet (PID from 22:10, 20 h earlier) still listened on node 8's RPC port. It had survived `down --wipe` because it answered RPC with 500, which `alive()` reads as "down", so `down` never asked it to stop and `--wipe` deleted its directory from under it; the new node 8 then failed with "Unable to start HTTP server" | `down` now finishes by process: after the RPC stops it terminates every `ycashd` whose `-datadir` is under the devnet directory (SIGTERM, 30 s, SIGKILL). `up` refuses over such processes and kills them under `--force` |
| F-15 | **Second walk (2026-09-21):** after a shock the owner's own vault ratio "didn't fall" for many blocks while the global ratio did: the column was judged at the claim price, which is the *higher* of the pools' cross-section (24- and 64-block windows) and the attested price, by design a slow figure that protects owners from flash crashes | The column is now **Ratio (market)** at the latest price, the leading indicator an owner wants; the claim-price ratio and the price at which a claim opens are in its tooltip. Red under 110 %, orange under 150 % |
| F-16 | "Claimable: no" while a notice stood and the claim height had passed; the vault was later claimed by the emergency clause with the attested price at $3 against a cross-section of $40 | Two things. Wallet: the cell now says *why not and when* — "not before H", "notice: opens at H", "no (claim price above $X)", "YES". Node (v3 plan D-R-5, for A6): the flag is node-local — `EstimateClaim` judges clause (b) with the bundle this node's pool can build and, when it cannot build one, falls back to the cross-section alone, so an owner's node can say "no" while a claimant's fed pool says "yes" |
| F-17 | Not enough time to act, hard to tell which vault needs action first; proposal of a 90-day grace period | Owner decision D-R-6 (2026-09-21): **grace stays 30 days**; the wallet makes the deadline visible instead. New **Act by** column ("locked; redeemable in N blocks, ~T", "REDEEMABLE: claim path opens in …", "CLAIM PATH OPEN …", and the VOID equivalents), rows tinted orange in the grace window and red under a notice or past the claim height |
| F-18 | The Overview's "minting" line was unreadable when multi-line; and the DIVERGENCE-then-GLOBAL_RATIO sequence after a shock was correct but "awkward" without a sense of when minting returns | Overview shows a short status ("paused: DIVERGENCE, GLOBAL_RATIO", "limited to class A", "open") with the full text as tooltip and the same two-line floor as the other long labels; the halt text now says when: the divergence clears within the slow window (N blocks, ~T), the ratio recovers with price, redemptions and claims, and class A mints again once it is the only halt |
| F-19 | The Vaults list mixed closed and claimed rows with the live ones, and lacked "blocks and time until I can redeem" | A **Show** filter above the table (Open = ACTIVE and VOID, the default; All; one status), and the Act-by column above; the selection maps through the filter |
| F-20 | The wallet's terminal output on launch: `qt.qpa.fonts: … missing font family "Monospace"` (34 ms of font-alias population) | Ours: the Receive page's address label asked for a family macOS does not have. It now takes the platform's fixed-width font from `QFontDatabase` |
| F-21 | Same output: `Could not parse stylesheet of object MainWindow` and one `QObject::disconnect: Unexpected nullptr parameter` | The stylesheet is upstream YecWallet's theme file, unchanged in the fork (its loader and `res/` are byte-identical to v4.5.0); harmless, left alone. The disconnect warning was located with `QT_FATAL_WARNINGS=1` and the crash report's stack: upstream `ConnectionLoader::doRPCSetConnection` calls a method on the embedded-node handle, which `--no-embedded` (how the devnet launches the wallet) leaves null. A one-line null guard; the start-up output is now clean apart from upstream's own lines |
| F-22 | (Notes, "what we want to know") "the landing Balance tab of the wallet needs to include the Yellowback confirmed YED balance and the total amount of YEC collateral in vaults" — the Balance tab was untouched upstream code and knew nothing of YED | Two rows under "Total (USD)" on the Balance tab: **Yellowback (YED)** (confirmed, with any unconfirmed amount) and **YEC in vaults** (the collateral in this wallet's active vaults, with its value at the mint price), refreshed with the Yellowback tab's own polling. Both strings are pure functions of the controller and are tested |
| F-23 | The wallet valued 19.5 YEC at $14.48 while the devnet's protocol price stood at $50–100: upstream YecWallet prices YEC from one CoinGecko call, unrelated to the price pools and attestors put on chain, so the Balance tab and the Yellowback tab disagreed by a factor of 70 | Owner decision D-R-7 (2026-09-22): **the protocol price is authoritative**. The Yellowback controller pushes the pools' fast median (`yed_getstats.pFast`) into the wallet's YEC/USD rate whenever the node is enabled, activated and has one; the CoinGecko poll becomes the fallback and never overwrites a protocol price fresher than 15 minutes (before activation, with no defined price, or once it goes stale, CoinGecko applies). The Balance tab's dollar tooltip names the source |
| F-24 | Sending to a regtest shielded address (`yregtestsapling1…`) was refused: "Recipient Address … is Invalid". The wallet's validator knew the mainnet (`ys…`, 78 chars) and testnet (`ytestsapling…`) Sapling shapes only, and its Sapling check keyed off a testnet flag regtest never sets — so every shielded path, including the Yellowback tab's shielded funding list, was dark on regtest | A regtest Sapling pattern (prefix + 76 characters, from a live `z_getnewaddress sapling`) and the prefix accepted on any network setting; tested. Shielded funding of mints and shielded redeem destinations can now be walked on the devnet |
| F-25 | The Send tab's Yellowback-address field was a few characters wide | The form's macOS default kept fields at their size hint; the form now lets fields grow and the recipient box starts at 44 characters |
| F-26 | After a +100 % shock the Mint page said "pools and attestors disagree by more than 15 %" for a whole slow window: MINT-10 compared the attestors, at the new price, with `xMint`, the *minimum* of the pool windows, which lags a rally by design (64 blocks here, ≈ 42 h on mainnet) | Owner decision D-R-8 / v3 plan W17 (2026-09-22): MINT-10 reads the pools' fast median, the current market; collateral is still sized at the minimum. A rally now passes the cross-check once the fast window fills (8 blocks; 96 on mainnet). Node, model, tests and the wallet's banner wording changed |
| F-6 | *(product feedback, for the walk-throughs)* After a −70 % shock, `yed_listclaimable` listed nothing for ≈ 30 blocks while `xClaim` (the mid and slow windows) caught up, then the liquidator's notice and the clause-(a) claim landed within six blocks of each other. The emergency tier and the ordinary claim opened at almost the same moment on regtest because `EMERGENCY_PERSIST` (4) ≈ the window lag; on mainnet (48 vs 576/2,016-block windows) the emergency tier leads by hours. Worth watching in Scenario 1 step 7 | none needed; noted for §7 question 1 (the walk's drift and volatility are the knobs) |
