# Role-based regtest plan — walking in each participant's shoes

**Status:** draft, revision 1 (2026-09-20). Not yet implemented. This is a plan for a *testing
and feedback* capability, not a change to Yellowback itself: nothing here touches consensus,
mining or policy code, and nothing here is a prerequisite for A6, A7 or A8. It exists so the
product owner can occupy each seat in the Yellowback economy in turn and give grounded feedback
before real attestors are recruited (v3 plan Phase A7).

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
The preset decides three things: how many nodes start, which participant's automation is
*withheld*, and where `wallet` points.

| Preset | Your seat | Your node | Automated for you |
|---|---|---|---|
| `user` | a minter and holder of YED | 0 (the funded wallet) | 3 pools, 4 attestors, heartbeat, price walk |
| `attestor` | one bonded attestor | 8 (a fourth attestor node, unregistered at `up`) | 3 pools, 3 attestors, heartbeat, price walk, **synthetic users** |
| `pool` | one mining pool | 4 (a pool that neither quotes nor mines until you say so) | 2 pools, 4 attestors, heartbeat (excluding your pool), price walk, **synthetic users** |
| `none` | — (today's behaviour) | 0 | everything |

`status` prints a banner naming your seat and your node, because the single most likely mistake
is driving the wrong node.

### 3.2 Node budget

The `attestor` preset needs a ninth node. The counts are forced by the regtest parameters
(`src/yellowback/params.cpp`, v3 plan §3.1): `ATTEST_ARM_MIN = 3`, `N_SLOTS = 5`,
`M_SELECT = 2`, `K_SLACK = 1`.

- **Attestor preset.** If you occupy one of only three attestor slots and stop signing,
  `poolFresh` falls to exactly `M_SELECT` — minting still works, but with zero slack, so any
  hiccup in the other two looks like *your* fault. A fourth attestor (three automated + you)
  keeps a real margin and makes your absence legible rather than catastrophic. `N_SLOTS = 5`
  leaves room.
- **Pool preset.** Three pools is already right: if your pool stops signalling, 2 of 3 = 67 %
  is above the 60 % minting-pause threshold, so the chain survives you — and if you *also*
  stop the second, you cross the threshold deliberately and watch minting pause. That is a
  scenario, not an accident.

Nine `ycashd` processes plus up to five agent processes is the ceiling. On a laptop this is
fine for regtest, but `up --role attestor` should say so before it starts.

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

### 3.4 Synthetic users (G2)

A `yellowback-sim` process driving node 0's wallet (and, in the `user` preset, a second wallet
node so *your* actions are not the only ones): on a timer, with a seeded RNG so a run is
reproducible, it picks a weighted action:

| Action | RPC | Notes |
|---|---|---|
| mint | `yed_mint` | random term class and size within the collateral it holds; two-step, so it must handle `pending` |
| redeem a matured vault | `yed_redeem` | at or after `lockHeight` |
| claim an underwater vault | `yed_claim` | only when `yed_listpositions` says claimable — this is what makes your attested price *matter* |
| post a notice | `yed_claimnotice` | the emergency path, occasionally |
| send YED | `yed_send` | wallet-to-wallet, so balances move |
| sweep carriers | `yed_sweepcarriers` | housekeeping, so the run does not leak |

It must be **honest about failure**: a refused mint (`bundle-insufficient`, `mint10-diverged`,
`insufficient-yec`) is logged and counted, never retried blindly, because those refusals are
exactly the signal the attestor and pool scenarios exist to show you. `sim stats` prints the
tally.

A hard constraint from A3: every bundle-carrying command is two-step, so the simulator must
either use `wait=false` and complete on the next block, or run with the heartbeat mining its
carriers (see `two_step` in `test_framework/yellowback_attest.py`). The heartbeat makes this
natural; without it the simulator would deadlock.

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

Each is a script you can run start to finish in about half an hour, with a checklist of what to
notice. The value is in the noticing, so each ends with the questions we actually want answered.

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

```bash
yellowback-devnet up --role attestor
yellowback-devnet wallet          # opens on node 8, your attestor node
```

**Automated:** 3 pools, 3 other attestors, heartbeat, price walk, synthetic users minting and
claiming against the prices you help set.

**Walk-through.**
1. Register from the wallet's **Attestors** page (`btnRegister` → `yed_registerattestor`): post
   the bond, then wait out `BOND_MATURITY` (8 blocks, ~2 min) and `ATTEST_ARM_DELAY`.
   **Is it clear what you have committed and for how long?** The bond locks for
   `bondMinLock = 200` blocks and earns nothing.
2. Start your agent — either the Settings page's subscriber plus a hand-run
   `yellowback-attest attest --conf …`, or a devnet convenience wrapper. Configure it against
   the mock price so you can choose what you attest.
3. Watch your `seq` get selected for real transactions. `yed_getselection` and the wallet's
   selection line show when you were picked; the fee you earn appears when you were.
4. **Stop signing for a while.** Watch your record go DORMANT after `DORMANCY_BLOCKS`, and
   revive it (`btnRevive` → `yed_revive`). Does the wallet tell you *before* you are ejected,
   or only after?
5. Attest a price 20 % away from everyone else and watch your attestations get dropped from
   selections while the honest three carry on.
6. Try to withdraw the bond before its locktime (`bond-locked`), then let it mature and withdraw.

**What we want to know.** Is the economic proposition legible — what you risk, what you earn,
what gets you ejected? Is running an agent something a competent operator would actually
sign up for? This scenario is the dress rehearsal for A7 recruiting, and the feedback from it
should shape the recruiting pitch.

### 4.3 Scenario 3 — "I am a mining pool"

```bash
yellowback-devnet up --role pool
# no GUI: pools are headless, which is the point
yellowback-devnet cli --node 4 -- yed_getinfo
```

**Automated:** 2 other pools, 4 attestors, heartbeat on the *other* two pools only, price walk,
synthetic users.

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
more config, one more thing to monitor? Are the failure modes discoverable from
`yed_getinfo` alone? A pool that finds this annoying simply will not run it, and the whole
design rests on pools running it.

---

## 5. Feedback capture

A scenario you cannot report on is a scenario wasted. Each run writes
`<dir>/session-<role>-<date>/` containing the devnet state, every agent log, the simulator's
tally, and a `NOTES.md` seeded with the walk-through checklist so observations can be typed
against the step that prompted them.

`yellowback-devnet report` bundles that directory into something attachable, with the parameter
set and both fork commits recorded at the top, so a note from three weeks ago can be placed.

Findings graduate into the v3 plan (a new §6.2, "found by walking the roles") and, where they
are impedance mismatches rather than product feedback, into `docs/mapping.md`.

---

## 6. Implementation

Six chunks, roughly a week in total, in this order — the first three are what make any scenario
work at all, and each is independently useful.

| # | Chunk | Deliverable | Effort |
|---|---|---|---|
| R1 | Heartbeat (G1) | `heartbeat` process and subcommand; `status` reports it; stops on a failing `check` | ~0.5 d |
| R2 | Role presets (G3) | `up --role`, the ninth node, `wallet --node`, the status banner | ~1 d |
| R3 | Synthetic users (G2) | `yellowback-sim`, seeded, two-step aware, with an honest failure tally | ~2 d |
| R4 | Price walk (G4) | `price --walk`, `--shock`; both populations move together | ~0.5 d |
| R5 | Scenario scripts | the three walk-throughs as runnable checklists; session directory and `NOTES.md` | ~1 d |
| R6 | Docs | `contrib/yellowback/devnet/README.md` role section; a short "walking the roles" page | ~0.5 d |

**Testing.** R1–R4 are devnet tooling, so they are covered the way the devnet is: a nightly
script (`yellowback_devnet_roles.py`) that brings up each preset, asserts the right
participants are automated and the right seat is empty, runs the heartbeat and simulator for a
fixed number of blocks, and asserts the chain is still healthy and `check` passes. That script
is the regression test for this entire plan and belongs in `EXTENDED_SCRIPTS`.

**Constraints inherited from the devnet.** Zero C++ (this is `contrib/` and `qa/` only); the
frozen-file set stays at zero delta; the plan's naming rules apply (Yellowback the system, YED
the unit); and the simulator must never be mistaken for a load test — it exists to make the
world feel inhabited, not to measure throughput. DoS and cost measurement is A6's job and uses
purpose-built scripts.

---

## 7. Open questions for the owner

1. **Is the GUI the right surface for the attestor scenario?** The wallet has a full Attestors
   page, but a real attestor is likelier to be a headless operator running the agent on a
   server. Walking it in the GUI may teach us about the wrong attestor. Worth doing both?
2. **Should the pool scenario get any GUI at all?** Today it is pure terminal, which is honest.
   If pool operators would expect a dashboard, that is a product finding we should surface now
   rather than after A7.
3. **How real should the simulated users be?** A seeded random walk of actions is cheap. Giving
   them personalities — a leveraged minter who rides the price down, a cautious one who
   over-collateralises — is more work but produces a far more instructive Positions list and
   much better liquidation scenarios.
4. **Does this run before or alongside A6?** It is not on the critical path and A7 recruiting is,
   but the attestor scenario is the best rehearsal we have for the recruiting pitch, which
   argues for doing it early.
