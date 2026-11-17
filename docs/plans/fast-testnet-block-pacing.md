# Fast-testnet block pacing (design note)

Status: design note, 2026-11-16. Read-only work: no repository other than this one is changed, and
nothing here touches the frozen `upgrade/vault` of ycash-dd, ycash6 or kogany. The numbers come
from the code at `origin/upgrade/vault`, from 900 real headers of `testnet-yb-fast` (heights
511,118 to 512,017, read over RPC from a local beta2 node) and from the simulation beside this
file, [`fast-testnet-block-pacing-sim.py`](fast-testnet-block-pacing-sim.py).

The question (the Yellowback lead architect): on the fast testnet, blocks are too slow with a CPU
and too fast with a rented GPU. Can there be a middle ground, ideally a block every 30 to 60
seconds, with a throttle on the miner? Or is the difficulty rule wrong for this network?

## 0. Conclusion first, and the decisions

**The difficulty rule is not broken, but three of its properties fit this network badly, and one
pool flag removes the first two. A steady 30 to 60 second block is not possible without a consensus
change: the target spacing is 75 seconds, and any miner who keeps producing blocks faster than that
only raises the difficulty until blocks take 75 seconds again.**

1. **A GPU arriving at difficulty 1 mines about 240 blocks in its first hour.** The rule may raise
   the difficulty by about 1.9 % a block at most, so it needs about 225 blocks to go from 1 to 75.
   A one-hour burst is that climb and nothing else: it ends at the moment blocks begin to take a
   minute.
2. **A GPU that stays never settles at 75 seconds either.** About once in 220 blocks one block
   takes more than 450 seconds by chance, the testnet minimum-difficulty rule fires, that one block
   pulls the average back from about 90 to about 14, and the climb starts again. The long-run mean
   is about 44 seconds, in a sawtooth between 3-second and 2-minute blocks (simulated; the chain
   shows it at 511,156).
3. **A CPU is slow at any difficulty.** Difficulty 1 on this network is 32 Equihash 192,7 solutions
   per block. The local node measures 0.068 Sol/s with two threads: one block in about 8 minutes
   at the minimum. After a GPU burst it is about 10 to 15 minutes for the first hours. No
   difficulty rule changes this; only more solutions per second do (0.43 Sol/s gives 75-second
   blocks), or a higher proof-of-work limit, which is a consensus change.

**Recommended (option A): `yolo --min-block-interval <seconds>`, off by default, set on the
fast-testnet pool.** The pool holds a block it has found until the node time in its header is that
many seconds old, then submits it. The header times stay the node's own and end up at least that
many seconds apart, so the difficulty rule sees a slow chain and leaves the difficulty at 1. No
consensus change, no node change, no change in any miner. (Section 4a, "Why the header times are
spaced", answers the question whether holding a block leaves its timestamp too close to its
parent's: it does not.)

| | Value | A GPU on | After the GPU leaves |
|---|---|---|---|
| Bursts, as today | **60** | a block every 60 to 75 s (section 4a); difficulty 1.5 after 1 h, 2.2 after 2 h, 4.6 after 4 h | CPUs at difficulty 1 within the hour: about 8 minutes a block with two threads |
| A card always on | **90** | a block every 80 s for ever, difficulty stays 1; a two-thread CPU beside it finds 1 block in 6 | no such period |

Decisions for the lead architect:

| # | Decision | Recommendation |
|---|---|---|
| P-1 | Build `--min-block-interval` in yolo | **Yes.** Small, testable on regtest, off by default, refused on mainnet |
| P-2 | Its value on the fast-testnet pool | **60** while the network runs on bursts, each at most 4 hours; 90 if P-3 is yes |
| P-3 | One card always on (about $45 to 60 a month) so the chain never stops | The lead architect's call. It is the only way to a usable rate with no CPU miner, short of a consensus change. With it, 90 and not 60: at 60 the difficulty reaches the GPU's own level within a day and the sawtooth returns |
| P-4 | Land the flag before the four-miner demonstration, or after the beta3 tags | **Before, if yolo's beta3 build is still open.** Without it four cards produce about 300 blocks in the first hour and leave difficulty 225 behind. The node lines are not involved either way |
| P-5 | A consensus change for the fast profile (section 4d) | **Not now.** Not possible in beta3; reconsider only if 60-second blocks from CPUs alone become a goal |

## 1. The rule, from the code

Both C++ lines agree; citations are ycash6 `origin/upgrade/vault` (ycash-dd `src/pow.cpp:95-101`
has the same minimum-difficulty rule). `CTestNetFastParams` (`src/chainparams.cpp:659-676`) sets
none of the proof-of-work values: it inherits them from `CTestNetParams`.

| Fact | Value | ycash6 | kogany |
|---|---|---|---|
| Target spacing | 75 s from Blossom, which is at 510,250 on the re-forked testnet | `src/consensus/params.h:184-185`, `src/consensus/params.cpp:164-171`, `src/chainparams.cpp:428-429`, `:456` | `crates/zakura-chain/src/parameters/network_upgrade.rs:350` |
| Averaging window | 17 blocks; the mean of their targets (not of their difficulties) | `src/chainparams.cpp:424`, `src/pow.cpp:109-128` | `network_upgrade.rs:375` |
| Time measured | median-time-past of the tip minus median-time-past 17 blocks back; each median is over 11 blocks, so the newest five timestamps do not count yet | `src/pow.cpp:130-133` | `crates/zakura-header-chain/src/validation/contextual/adjusted_difficulty.rs:418-439` |
| Damping | the difference from 17 x 75 = 1,275 s is divided by 4 | `src/pow.cpp:146-147` | `adjusted_difficulty.rs:380` |
| Limits | the damped time is kept within 1,071 s (-16 %) and 1,683 s (+32 %): the target falls to 0.84 or rises to 1.32 times the window mean, per block | `src/chainparams.cpp:426-427`, `src/consensus/params.cpp:177-183`, `src/pow.cpp:149-154` | `adjusted_difficulty.rs:389-391` |
| Proof-of-work limit | `07ff…ff`: difficulty 1 is 1 solution in 32 | `src/chainparams.cpp:423`, `src/pow.cpp:159-161` | the network's `target_difficulty_limit()` |
| Minimum-difficulty rule | active from 299,187: a block whose **header time** is more than 6 x 75 = **450 s after its parent's header time** must be at the limit. Its `nBits` is the limit and enters the next 17 window means like any other block | `src/chainparams.cpp:430`, `src/pow.cpp:97-104` | `network_upgrade.rs:430`, `:713-776`, `adjusted_difficulty.rs:265-284` |
| Header check | `nBits` must equal the rule's result for that block's own time | `src/main.cpp:6131-6135` | the same function |
| Time, lower bound | above the parent's median-time-past | `src/main.cpp:6138-6143` | — |
| Time, upper bounds | at most median-time-past + 3 h (consensus), and at most the node's clock + 4 h (local) | `src/chain.h:32`, `:38`, `src/main.cpp:6151-6164` | `crates/zakura-chain/src/parameters/ycash.rs:194`, `:202` |
| Miner's time | the clock, kept inside both bounds, re-read on every nonce; `nBits` recomputed with it | `src/miner.cpp:70-90`, `:1054-1060` | — |
| Equihash | 192,7 from the Ycash fork (510,248); regtest stays 48,5 | `src/consensus/upgrades.cpp:37-42`, `src/chainparams.cpp:1229-1245` | — |
| CPU mining defaults | `-gen` off, `-genproclimit` 1 | `src/miner.h:29-30` | — |

Three consequences, each checked against the chain in section 2:

- **Fastest rise.** With every window at the -16 % limit the difficulty grows by a factor g per
  block where 1 = 0.84 x mean(g, g², …, g¹⁷): g = 1.0195. Doubling takes 36 blocks, a factor of 75
  takes about 225 blocks, however much hash rate arrives.
- **One minimum-difficulty block undoes most of it.** With k blocks at the limit among the 17, the
  next difficulty is about 17 / (k + (17 - k) / D). From D = 75: 14.0 after one, 7.9 after two, 2.8
  after six.
- **Timestamps, not arrival times, drive everything.** The rule never sees the clock. A chain whose
  header times are N seconds apart is, to the rule, a chain with N-second blocks.

## 2. What the chain did (511,118 to 512,017, 37.2 hours)

| Blocks | What happened | Blocks | Seconds | Mean interval | Difficulty |
|---|---|---|---|---|---|
| 511,119–511,155 | a GPU near its own level | 37 | 1,784 | 50 s | 60 → 83 |
| 511,156 | a 988 s gap: the minimum-difficulty rule fires | 1 | 988 | | 1.0 |
| 511,157–511,352 | the same GPU climbs again | 196 | 6,993 | 36 s | 10 → 97 |
| 511,353–511,401 | CPU blocks after a long stop; header times capped at median-time-past + 3 h | 49 | | | 12 → 1.0 |
| 511,402–511,638 | GPU burst from difficulty 1 | 237 | 3,220 | 14 s | 1.0 → 58.5 |
| 511,639 | 6,823 s gap, minimum difficulty | 1 | | | 1.0 |
| 511,640–511,800 | GPU burst | 161 | 3,350 | 21 s | 13 → 64.8 |
| 511,801–511,807 | two gaps of 10,329 s and 8,502 s, CPU blocks between | 7 | | | 1.0 → 15 → 1.0 |
| 511,808–512,017 | GPU burst | 210 | 3,236 | 15 s | 5 → 74.4 |

- **The rise is the clamp.** In every burst the difficulty grows by 1.33 per 15 blocks (2.35, 3.13,
  4.15, 5.51, 7.32 at 511,463 to 511,523): 1.019 per block, the 1.0195 of section 1.
- **A one-hour burst is the climb.** Reaching 75 needs about 225 blocks; the bursts produced 161
  to 237 blocks in 54 to 56 minutes and stopped at 58 to 74. Blocks took 3 s at the start (the
  pool's and the miner's turn-around, not hashing), 10 s at difficulty 10, 47 s at 64. The GPU's
  own level is difficulty 90 to 100 (75 s x 40 Sol/s / 32), which the burst never reaches.
- **The sawtooth is real.** At 511,155 the difficulty was 82.6 and a block took 988 s; the block at
  511,156 is at the limit, and the next windows read 10.0, 8.6, 11.8 (511,163 to 511,193). The
  formula gives 17 / (1 + 16/82.6) = 14.2 for the first block after it; the +32 % limit then pulls
  a little further.
- **After a stop longer than 3 hours the header times lag the clock.** The cap at median-time-past
  + 3 h makes every sixth block jump by 10,319 s (eight such jumps between 511,353 and 511,395),
  and each jump is a minimum-difficulty block. The chain's timestamps catch up with the clock in
  steps; explorers show block times that are hours old.
- **The tip.** 512,017 (time 1,794,848,240) was 9.6 hours old when read. The next block is at the
  limit for any miner (the gap is above 450 s); it then leaves difficulty about 14 behind for a
  GPU, and CPUs carry on at the limit.

How long a CPU-only period needs afterwards: the CPU never mines at the left-over difficulty. At
75 a two-thread CPU would need 9.8 hours a block, so it waits out the 450 seconds and mines at the
limit: about 450 + 470 = 920 s a block. Each such block lowers the window mean (14, 7.9, 5.4, …),
and with the +32 % limit the computed difficulty is back near 1 after 5 to 8 blocks, one to two
hours. From then on there is no 450-second wait: about 470 s a block. **So the burst costs the CPU
miners roughly a doubling of the block time for one to two hours; the larger part of "CPU too
slow" is the 470 seconds, which is there with or without bursts.**

## 3. The hash rates

A block at difficulty D needs 32 x D solutions on average.

| Miner | Sol/s | Source | Difficulty 1 | 10 | 75 |
|---|---|---|---|---|---|
| This machine, `-gen -genproclimit=2`, the node's default solver | 0.068 | `getmininginfo` `localsolps` on the local fast-testnet node (its counter over the time it mined; `genproclimit` 2) | 471 s | 78 min (in practice 920 s, by the 450 s rule) | 9.8 h (in practice 920 s) |
| One rented RTX 3060-class card, miniZ | 34 to 48, 40 used here | work in the three bursts divided by their time: 33.8, 34.3, 44.5 Sol/s; 47.6 over the last 117 blocks; `getnetworksolps` 47 | 0.8 s (3 s observed: turn-around) | 8 s | 60 s |
| Four such cards | 160 | | 0.2 s | 2 s | 15 s |
| What 75 s blocks need at difficulty 1 | 0.43 | 32 / 75; ycash-ops `docs/vast-setup.md` says the same | 75 s | | |

Not measured: this machine with more than two threads. No scratch benchmark exists for 192,7
(regtest is 48,5 and `zcbenchmark solveequihash` uses the base 200,9). If the solver scaled
linearly, ten threads would give about 0.34 Sol/s, a block in about 95 seconds at difficulty 1;
memory per thread makes that an upper bound. A ten-minute run with `-genproclimit=8` and one
`getlocalsolps` call settles it.

The block at 511,156 fits the CPU figure: 988 s against the expected 450 + 471.

## 4. The options, simulated

The simulation implements the rule of section 1 on integer targets and Poisson miners (CPU 0.068
Sol/s, GPU 40 Sol/s, 2 s of pool turn-around per block). Its unpaced one-hour burst gives 238
blocks ending at difficulty 67; the chain gave 210 to 237 ending at 58 to 74.

**Baselines.**

| Scenario | Result |
|---|---|
| CPU only, from difficulty 1 | 7 to 10 blocks an hour, mean 365 to 540 s, difficulty stays 1 |
| CPU only, from difficulty 75 | 3 blocks in the first hour (860 s), then as above |
| One GPU for 1 h, then CPU only | hour 1: 238 blocks, mean 15 s, median 5 s, ends at 67. Then 6 blocks in the next hour (580 s), 610 s for two more hours, 490 s after that |
| One GPU always on | hour 1 as above; after that mean 44 s, mean difficulty 52, a minimum-difficulty reset every 220 blocks (about 2.7 hours); between resets 70 s at difficulty 88. A CPU beside it finds 3 blocks a day |
| Four GPUs for 1 h | 300 blocks, median 4 s, ends at difficulty 225; CPUs afterwards 620 to 730 s for seven hours |

### a. Pool-side pacing: `--min-block-interval N` (recommended)

One GPU for one hour with pacing, then CPU only:

| N | Blocks in the hour | Mean interval | Difficulty at the end | CPU blocks in that hour | First hour after |
|---|---|---|---|---|---|
| none | 238 | 15 s | 67 | 1 | 6 blocks, 580 s |
| 30 | 123 | 29 s | 7.7 | 8 | 4 blocks, 450 s; then 890 s for two hours |
| 45 | 86 | 42 s | 2.7 | 10 | 6 blocks, 600 s |
| **60** | 64 | 56 s | 1.5 | 6 | 6 blocks, 580 s |
| 75 | 52 | 69 s | 1.1 | 5 | 14 blocks, 200 s |
| 90 | 45 | 79 s | 1.0 | 7 | 13 blocks, 260 s |

Why the threshold is the target spacing: with header times N apart the window spans 17 N seconds;
the damped time is 1,275 + (17 N - 1,275) / 4. At N = 75 that is 1,275, no change. At 60 it is
1,211, the target falls 5 % against a mean that lags, about +0.6 % difficulty a block. At 45 it is
1,148 (+1.2 % a block). At 30 it is 1,084, almost the 1,071 limit: +1.7 % a block, nearly the
unpaced climb, only spread over more time.

One GPU that stays, with pacing and a two-thread CPU beside it:

| N | 0–4 h | 4–12 h | 12–24 h | 24–48 h | CPU's share |
|---|---|---|---|---|---|
| 30 | 30 s, difficulty to 8 | 48 s, to 80 | 52 s, sawtooth | 53 s | none after hour 1 |
| 45 | 45 s, to 36 | 63 s | 62 s, to 83 | 59 s | none after hour 1 |
| 60 | 58 s, to 4.6 | 62 s, to 44–51 | 69–74 s, to 70 | 70–73 s, 44–76 | 11–14 blocks in 4 h, then almost none |
| 75 | 70 s, 1.4 | 71 s, 2.5 | 72 s, 4.5 | 74 s, 7 | 20 to 40 blocks per 12 h; fades over days (difficulty 10 to 14 on day 4, because the CPU's blocks make the chain a little faster than 75 s) |
| 80 | 75 s, stays below 1.8 | | | 75 s | 12 % of blocks |
| **90** | 79 s, 1.0 | 82 s, 1.0 | 83 s, 1.0 | 81 s, 1.0 | 16 to 18 % of blocks |

So: **30 to 60 seconds is achievable for a session, not as a steady state.** At 60 a session of up
to four hours leaves difficulty below 5 and costs the CPUs nothing measurable afterwards; an
eight-hour one leaves 18 and still clears within the hour. A card that stays needs N of 80 or
more; then the difficulty stays at the limit, so every CPU miner on the network keeps finding
blocks at the rate its own speed gives at difficulty 1, which is the "others can take part" the
question asks for.

The mechanism, and why this one:

- **Chosen: hold, then submit.** Jobs are exactly today's: the header time is the node's `curtime`
  of the template the job was built from, the bits are the node's for that time, and a miner must
  echo that time (yolo refuses any other `ntime`, `src/stratum.rs` `bad-ntime`; no rolling). A
  submit that meets the block target and passes the Equihash check is answered `true` and kept as
  a candidate instead of going to the node. The pool calls `submitblock` for it N seconds after it
  read that job's template from the node, and builds the next job only from a template read after
  the node accepted the block (`template_stale`, as today). Miners see nothing new: the same jobs,
  every submit answered at once, no idle period. If the chain moves while a block is held (someone
  else found one), the held block is dropped and counted; it is never submitted on a stale tip.
- **Why the header times are spaced (the point to settle before any code).** A held block does
  carry an old time: the one its job was given, a few seconds after the pool saw the tip. But the
  pool saw that tip only when the parent was *published*, and the parent was published N seconds
  after *its* job time. So block k has time t(k) = the node clock when its job was read, it is
  published at t(k) + N or later, and every job on top of it is read after that: t(k+1) >= t(k) + N.
  Each timestamp is N seconds behind its block's publication and N seconds after its parent's
  timestamp, not seconds after it. The rule reads only the timestamps (section 1), so it sees
  N-second blocks. What would make the difficulty climb is a block whose time is close to its
  parent's *time*; with this mechanism that needs a job read before the parent was published,
  which does not exist. The guarantee needs the release to be counted from the held block's own
  job, not from the moment the tip was first seen: yolo rebuilds a job with the newest `curtime`
  whenever a miner reconnects, fills a job's share set, or (a paired miner) gets a new coinbase,
  so a block found late on a tip can carry a time up to N seconds after the tip was seen. Counted
  from the tip, the gaps would average N and could each be anything from 0 to 2 N; counted from
  the job, each is at least N.
- **Which solution is held: one at random, not the first.** At difficulty 1 a card has a block in
  under a second, so "the first submit wins" pays the miner whose job arrives first. A transparent
  miner's job is built at once; a Sapling or post-quantum miner's needs a `getcoinbasetemplatefor`
  answer first (a proof, for Sapling) and would never win. So every block-target solution received
  in the first N seconds on a tip is a candidate and the held one is replaced by the k-th with
  probability 1/k: each solution has the same chance, each miner wins in proportion to the
  solutions it found, and the block is always the winner's own, paying it in full. Only one block
  is kept in memory. Every candidate's Equihash solution is verified before it counts.
- **The price of both.** A winner whose job was read d seconds after the tip was seen is published
  at tip + d + N. Transparent miners that stay connected have d near 0; miniZ reconnects at every
  block (d about 2 s); a paired miner on a busy mempool has any d up to N. Simulated (scenario 13):
  N = 60 gives a block every 62 s with no paired miner and every 72 to 75 s when three winners in
  four are paired and their jobs follow the mempool; the difficulty after one hour is 1.3 and 1.0
  to 1.1. Never more than 2 N.
- **Where the times are not N apart, and why that is not ours to fix.** (i) A block from another
  pool or a solo miner carries whatever time its miner chose. (ii) After a stop of more than three
  hours the node's `curtime` is capped at median-time-past + 3 h (section 2), so the first blocks
  share a time and then jump: the pool still publishes them N seconds apart, and the jumps lower
  the difficulty, they never raise it. (iii) A regtest chain generated in a burst has a
  median-time-past ahead of the clock and `curtime` = median-time-past + 1 until the clock passes.
- **Rejected: no job, or an unsolvable job, until the tip is N seconds old** (the same as taking
  only solutions whose job is at least that old). The timestamps would be the most honest (seconds
  before publication). But stratum has no pause: miners would keep working on the old job (every
  submit stale) or get a target they cannot meet, with no accepted share for a minute at a time;
  yolo itself disconnects a miner that is silent for three keepalive periods, and whether miniZ
  stays connected through it is unknown (it already drops its connection at every new block,
  ycash-ops#16). And once the minute is over the first job delivered wins the block, which is the
  unfairness above with no window to average it out.
- **Rejected: jobs dated max(`curtime`, tip time + N), submitted when the clock reaches that time.**
  Consensus would accept the time on all three lines (above median-time-past, at most
  median-time-past + 3 h and the clock + 4 h), and the timestamp would equal the publication time.
  But the bits belong to the time: a date pushed across tip time + 450 s needs the limit as bits,
  one below it needs the window's, and the node served bits for `curtime` only, so the pool would
  have to compute the rule itself or build a `bad-diffbits` block. `getblocktemplate` and
  `getcoinbasetemplatefor` do not give the tip's header time either (`mintime` is the
  median-time-past + 1), so it needs a call outside the pool's interface. The header time would no
  longer be "what the node said", the property that fixed Y-F5 and Y-F10.
- **Rejected: every job on a tip carries the first job's time** (so that all candidates are equal
  and the spacing is exactly N). The bits would still fit, but the block would pair one template's
  time with a later template's transactions and tag; nothing checks today that every rule on three
  node lines is indifferent to that.
- **Rejected: spacing the timestamps without spacing the blocks** (header times 75 s apart, blocks
  every 30 s). The times run ahead of the clock by 45 s a block and hit the 3-hour and 4-hour
  bounds after about 240 blocks; every explorer and wallet shows wrong times meanwhile.

Cost of pacing: the card's work is thrown away for most of each interval (at difficulty 1 it has a
block in a second and waits 59), and a miner outside the pool can take a block while one is held.
On a testnet whose purpose is a visible mempool, both are acceptable; on mainnet neither is, so the
flag is refused there.

### b. A steady baseline miner

| Baseline | Cost a month | Result |
|---|---|---|
| One RTX 3060-class card always on, unpaced | $45 to 60 (ycash-ops `docs/vast-setup.md`, $0.06 an hour, cap $0.09) | the sawtooth: mean 44 s, 3-second to 2-minute blocks, CPUs shut out |
| The same card, pool at 90 | the same | 80 s blocks, difficulty 1, CPUs take 1 block in 6 each |
| A 0.5 Sol/s miner (about 15 CPU threads if the solver scales, or 1 % of a card) | a 16-core host; mining on the AWS hosts is ruled out (testnet plan T-21) | 69 to 78 s blocks at difficulty 1.0 to 1.2, no pacing needed |

A constant small hash rate is the ideal; a paced card is the cheap way to imitate one.

### c. Throttling the rented card

Not realistic. The reduction needed is a factor of about 100 (40 to 0.4 Sol/s). Miner intensity
settings exist for heat and noise and do not reach 1 %; miniZ's options were not re-read for this
note, and nothing in `ycash-infra/images/miner` passes one. A wrapper that stops the miner 99 % of
the time would produce the right average, pay for an idle card as pacing does, and add stratum
timeouts and reconnects for every rented machine. Pacing in the pool has the same effect for every
miner at once, from one place.

### d. A consensus change for the fast profile

Simulated, one GPU for an hour and then CPU only:

| Variant | Hour 1 | CPUs afterwards |
|---|---|---|
| Target spacing 30 s (minimum-difficulty gap 180 s) | 269 blocks, ends at 39 | 3 blocks in the next hour; no better than today |
| Minimum-difficulty gap 2 x 75 s instead of 6 x | 275 blocks, ends at 22 (resets come sooner) | 660 s, then 390 s |

Neither helps much, because neither touches the two real limits: the climb is capped at 1.9 % a
block, and difficulty 1 costs 32 solutions. A change that would matter is one of:

- a higher proof-of-work limit for the fast profile (difficulty 1 at 4 solutions a block gives a
  two-thread CPU a block a minute);
- minimum-difficulty blocks left out of the window mean, which ends the sawtooth;
- a faster rule (a larger step, or a target that decays with the time since the tip).

Each is a new activation height in `CTestNetFastParams`, a change in `src/pow.cpp` and
`src/chainparams.cpp` on ycash-dd and ycash6 together, the same in kogany
(`network_upgrade.rs`, `adjusted_difficulty.rs`), cross-line vectors, two independent reviews at
the consensus gate, and every fast-testnet node upgraded before the height. It cannot be in beta3:
the three node lines are frozen and the release-candidate cut is made (the mandate-end height
512,417 is compiled in).

### e. Local CPU mining, and the minimum-difficulty floor

- The local node runs `-gen=0`. With `-gen=1 -genproclimit=2` it finds a block in about 8 minutes
  at difficulty 1. More threads: measure first (section 3).
- The floor exists already: whatever the difficulty, a CPU miner is never slower than 450 s plus
  its time at difficulty 1 (920 s with two threads). The node's own miner uses it without any
  setting.
- It could be used deliberately: a miner may date a block 451 s after the tip at once (consensus
  allows up to the clock + 4 h) and mine at the limit immediately. That buys about 31 blocks before
  the 4-hour bound stops it, and leaves the chain's times hours ahead. Not recommended; it is the
  reason the difficulty of this network protects nothing.
- With the pool paced, none of this is needed: the difficulty is at the limit anyway.

## 5. Recommendation

**Build option A, set it to 60 on the fast-testnet pool, keep bursts to four hours.** A GPU then
gives a block a minute; CPUs give a block in about 8 minutes (two threads) between bursts, at
difficulty 1 from the first block. If the lead architect wants a chain that never stops (P-3), one
card always on with the pool at 90 gives a block every 80 seconds and room for CPU miners.

### The flag

```
--min-block-interval <SECONDS>    0 (default): off, today's behaviour, byte for byte.
                                  1..=300: a block is submitted no sooner than this after its
                                  job's time was read from the node; until then it is held.
```

- **The clock** is the pool's monotonic clock. Every job remembers when its template was read from
  the node (`template_at` in `src/poller.rs` `apply_template`; a paired job, when its pair was
  built), and the tip remembers when the poller first saw it. No new RPC.
- **Candidates:** a submit that meets the block target and verifies, on the current tip. If none is
  held and its job is already N seconds old, it goes to the node at once, as today. Otherwise it
  is answered `true` at once and held, or, while the tip is less than N seconds old, takes the
  held one's place with probability 1/k. The miner stays on its job. This holds for paired jobs
  (Sapling and post-quantum payouts) as well: the held block is its finder's own.
- **Release:** N seconds after the held block's job was read, if the current template is still on
  the same parent, `submitblock`; the result is logged and counted as today. When the poller sees
  another parent first, the block is dropped and `heldStale` counts it.
- **Refused on mainnet:** `getblockchaininfo` `chain` = `main` and a value above 0 is a start-up
  error. Holding a block there loses it to any other miner.
- **`/status`:** `minBlockInterval`, `nextBlockInSeconds` (0 when a block could be submitted now),
  `held` (height, candidates, seconds until release), `heldStale`.
- **Where it is set** (names only): ycash-infra `infra/testnet-seeds/nodes`, a `min_block_interval`
  key in the `pool` object beside `share_ratio` (`variables.tf`, `files/seedctl`, `tests/seedctl.sh`,
  the README); ycash-ops `testnet-pools/nodes/main.tf`, beside `share_ratio = 32`, and
  `docs/testnet-pools.md`.

### Tests

1. Unit, with a fake clock: the hold decision at the boundary; release counted from the job; the
   random replacement (each of k candidates held with probability 1/k, none after the window); a
   held block dropped when the parent changes; off means no code path changes; the mainnet refusal.
2. Wire (`tests/wire.rs`): a recorded submit before the deadline is answered `true` and reaches
   `submitblock` only after it; the status fields.
3. Regtest (`tests/regtest.rs`, the 48,5 stratum miner), with an interval of 5 s: ten blocks whose
   header times are at least 5 s apart and whose arrival times are too (the chain is first left
   alone until the clock has passed its median-time-past); a block mined by the node during a hold
   drops the held one and nothing invalid is submitted; transparent, Sapling and post-quantum
   miners side by side, each winning blocks whose coinbase pays it in full; with the flag at 0 the
   existing tests pass unchanged.
4. The simulation in this directory, kept as the record of the numbers.
5. On the fast testnet, the acceptance run: one card for an hour at 60 gives 55 to 65 blocks and
   leaves difficulty below 2; miniZ stays connected through the holds (to be seen, not assumed).

### The four-miner demonstration

Its runbook (`beta3/beta3-plan.md` section 9) expects 75-second blocks and about 24 blocks a miner
in two hours. Unpaced, four cards from difficulty 1 give about 300 blocks in the first hour, most
of them seconds apart, and end near difficulty 225 with the same reset pattern afterwards. With
the pool at 60: 100 to 115 blocks in two hours (a block every 62 to 75 s, section 4a), about 25 to
30 a miner, the finder of each block chosen at random among the solutions of its minute, each block
paying its finder in full; fee-paying transactions sent during
the run wait at most a minute. This is the case for P-4.

### The mandate-end margin

The tip is 512,017 and the fund mandate ends at 512,417 on the fast profile: 400 blocks. The demonstration needs the chain past it; the rollout of beta3 nodes should be complete
before it.

| Who mines | Time to cover 400 blocks |
|---|---|
| One GPU, unpaced, from difficulty 1 | about 3 hours (238 in the first, then about 44 s a block) |
| Four GPUs, unpaced | about 2 hours (300 in the first) |
| One GPU, pool at 60 | 6.7 hours |
| One GPU, pool at 90 | 9 hours |
| Two-thread CPU only | about 50 hours |

Until the flag exists, every unpaced GPU hour spends more than half of the margin. No burst before
the beta3 nodes are in place; after that, a paced or unpaced run of a few hours crosses the height
on purpose.

## 6. What stays impossible without a consensus change

- A steady block every 30 to 60 seconds. The stable rates are 75 s (the target) or slower.
- A usable CPU-only chain from two threads: 8 minutes a block is the limit's price, 32 solutions.
- A GPU and CPUs mining side by side without pacing: the GPU's difficulty (90 to 100) leaves a CPU
  only the 450-second rule, and with blocks every minute that rule almost never applies.
- An unpaced GPU settling at 75 s: the reset about every 220 blocks is part of the testnet rule.

## 7. Reproducing the numbers

- Headers: `getblockhash` and `getblockheader` for 511,118 to 512,017 (time, bits, difficulty);
  `getmininginfo`, `getlocalsolps`, `getnetworksolps`.
- Simulation: `python3 docs/plans/fast-testnet-block-pacing-sim.py` (standard library, seeded,
  about ten seconds). Scenario numbers in its output: 1–3 CPU only, 4 the burst, 5 paced bursts,
  6 a card that stays, 7 paced and staying, 7b longer paced sessions, 8–9 four cards, 10 a small
  steady miner, 11–12 the consensus variants, 13 the mechanism as built (random candidate, release
  counted from the job, paired miners) beside the first model, with the gaps between header times. The 80-second and several-seed figures of section 4a
  come from the same `run()` with `pace=80` and seeds 1 to 3.
