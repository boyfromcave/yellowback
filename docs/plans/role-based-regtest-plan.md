# Role-based regtest plan — walking in each participant's shoes

**Status:** revision 2 (2026-09-20), scheduled — **build now, alongside A6** (owner decision
D-4). This is a plan for a *testing and feedback* capability, not a change to Yellowback itself:
nothing here touches consensus, mining or policy code. It exists so the product owner can occupy
each seat in the Yellowback economy in turn and give grounded feedback before real attestors are
recruited (v3 plan Phase A7), and so that the comprehensive regression coverage those scenarios
imply exists in CI rather than in someone's terminal history.

## 0. Revision log

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
| **the leveraged minter** | mints close to the minimum collateral ratio, on the longest term, and never tops up | the first to go underwater on a downswing — it is what makes liquidation happen *to someone* without anyone staging it |
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
