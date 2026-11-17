#!/usr/bin/env python3
# Copyright (c) 2026 The Ycash developers
# Distributed under the MIT software license, see the accompanying
# file LICENSE or https://www.opensource.org/licenses/mit-license.php .
"""Simulation behind docs/plans/fast-testnet-block-pacing.md.

The retarget rule is the node's (ycash6 src/pow.cpp GetNextWorkRequired / CalculateNextWorkRequired,
testnet parameters): mean target of the last 17 blocks, median-time-past span of that window damped
by 4 and clamped to -16 % / +32 %, capped at the proof-of-work limit, and the testnet rule that a
block whose time is more than 6 x 75 s after its parent's is at the limit. Miners are Poisson
processes: a miner doing S Sol/s finds a block at difficulty D at rate S / (32 D).

Two kinds of miner, as on the network:
  cpu   ycashd -gen: the header time follows the clock (UpdateTime on every nonce).
  pool  yolo: the header time is the node's curtime when the job was made; a new job when the
        template's target changes (the 450 s rule). With pace N, a block found sooner than N
        seconds after the pool first saw the tip is held and submitted at that moment.

Standard library only. Run: python3 fast-testnet-block-pacing-sim.py
"""
import random
import statistics

LIMIT = (1 << 251) - 1          # powLimit 07ff...ff: difficulty 1 = 32 solutions per block
WINDOW, SPAN, DAMP, UP, DOWN = 17, 11, 4, 16, 32
GPU, CPU = 40.0, 0.068          # Sol/s: one rented RTX 3060-class card; this machine, -genproclimit=2
OVERHEAD = 2.0                  # s per pool block: submit, new template, miner restart (measured ~2-3 s)


class Chain:
    def __init__(self, spacing=75, gap=6, difficulty=1.0):
        self.spacing, self.gap = spacing, gap
        self.times = [-spacing * i for i in range(40, 0, -1)]
        self.targets = [int(LIMIT / difficulty)] * 40

    def mtp(self, end):         # median-time-past of the block at index end-1
        return sorted(self.times[max(0, end - SPAN):end])[len(self.times[max(0, end - SPAN):end]) // 2]

    def normal_target(self):
        n = len(self.times)
        avg = sum(self.targets[-WINDOW:]) // WINDOW
        win = WINDOW * self.spacing
        actual = self.mtp(n) - self.mtp(n - WINDOW)
        actual = win + int((actual - win) / DAMP)        # C++ division truncates toward zero
        actual = max(win * (100 - UP) // 100, min(win * (100 + DOWN) // 100, actual))
        return min(LIMIT, avg // win * actual)

    def min_diff_from(self):    # header times above this are at the limit
        return self.times[-1] + self.gap * self.spacing

    def add(self, time, target):
        self.times.append(max(time, self.mtp(len(self.times)) + 1))
        self.targets.append(target)

    def difficulty(self):
        return LIMIT / self.normal_target()


def find(rng, sols, start, chain):
    """(wall time found, target used, time the min-difficulty phase began or None)."""
    if sols <= 0:
        return float("inf"), 0, None
    normal, switch = chain.normal_target(), max(start, chain.min_diff_from() + 1)
    t = start + rng.expovariate(sols * normal / 2 ** 256)
    if t <= switch or normal == LIMIT:
        return t, normal, None
    return switch + rng.expovariate(sols * LIMIT / 2 ** 256), LIMIT, switch


def run(hours, pool=lambda t: 0.0, cpu=lambda t: 0.0, pace=0, seed=1, **chain_args):
    """Returns rows (wall time, interval, difficulty, miner) for every block in `hours`."""
    rng, chain, now, rows = random.Random(seed), Chain(**chain_args), 0.0, []
    while now < hours * 3600:
        seen = now                                        # the pool first sees this tip
        pt, ptarget, pswitch = find(rng, pool(now), now + OVERHEAD, chain)
        ct, ctarget, _ = find(rng, cpu(now), now, chain)
        release = max(pt, seen + pace) if pace else pt
        if release == float("inf") and ct == float("inf"):  # nobody mines: step to the next change
            now += 60
            continue
        if ct < release:
            chain.add(int(ct), ctarget)                   # the clock at the moment it is found
            who, at = "cpu", ct
        else:
            chain.add(int(pswitch if pswitch else seen), ptarget)  # the job's curtime
            who, at = "pool", release
        rows.append((at, at - now, LIMIT / chain.targets[-1], who))
        now = at
    return rows


def show(title, rows, marks):
    print(f"\n{title}")
    print("  window (h)     blocks  mean s  median s   D end   cpu blocks")
    for a, b in marks:
        seg = [r for r in rows if a * 3600 <= r[0] < b * 3600]
        if not seg:
            print(f"  {a:5.1f}-{b:<5.1f}        0")
            continue
        gaps = [r[1] for r in seg]
        print(f"  {a:5.1f}-{b:<5.1f}  {len(seg):7d} {statistics.mean(gaps):7.1f} {statistics.median(gaps):9.1f} {seg[-1][2]:7.1f} {sum(r[3] == 'cpu' for r in seg):8d}")


def burst(h):
    return lambda t: GPU if t < h * 3600 else 0.0


if __name__ == "__main__":
    on = lambda t: 1.0
    steady = [(0, 1), (1, 4), (4, 12), (12, 24)]
    after = [(0, 1), (1, 2), (2, 4), (4, 8), (8, 13)]
    c2 = lambda t: CPU
    show("1. CPU only (0.068 Sol/s), start at difficulty 1", run(24, cpu=c2), steady)
    show("2. CPU only (0.068 Sol/s), start at difficulty 75", run(24, cpu=c2, difficulty=75), steady)
    show("3. CPU only, 0.43 Sol/s (the rate 75 s blocks need at difficulty 1)", run(24, cpu=lambda t: 0.43), steady)
    show("4. one GPU for 1 h, no pacing, then CPU only", run(13, pool=burst(1), cpu=c2), after)
    for n in (30, 45, 60, 75, 90):
        show(f"5. one GPU for 1 h, pool pace {n} s, then CPU only", run(13, pool=burst(1), cpu=c2, pace=n), after)
    show("6. one GPU always on, no pacing", run(24, pool=lambda t: GPU, cpu=c2), steady)
    for n in (30, 45, 60, 75, 90):
        show(f"7. one GPU always on, pool pace {n} s, CPU beside it", run(48, pool=lambda t: GPU, cpu=c2, pace=n), steady + [(24, 48)])
    for h in (2, 4, 8):
        show(f"7b. one GPU for {h} h, pool pace 60 s, then CPU only", run(h + 6, pool=burst(h), cpu=c2, pace=60), [(0, h), (h, h + 1), (h + 1, h + 3), (h + 3, h + 6)])
    show("8. four GPUs for 1 h, no pacing, then CPU only", run(13, pool=lambda t: 4 * GPU if t < 3600 else 0.0, cpu=c2), after)
    show("9. four GPUs for 1 h, pool pace 60 s, then CPU only", run(13, pool=lambda t: 4 * GPU if t < 3600 else 0.0, cpu=c2, pace=60), after)
    show("10. a small always-on miner, 0.5 Sol/s on the pool, no pacing", run(24, pool=lambda t: 0.5), steady)
    show("11. consensus variant: 30 s target spacing (minimum-difficulty gap 180 s); one GPU 1 h, then CPU",
         run(13, pool=burst(1), cpu=c2, spacing=30), after)
    show("12. consensus variant: 75 s spacing, minimum-difficulty gap 2 x 75 s; one GPU 1 h, then CPU",
         run(13, pool=burst(1), cpu=c2, gap=2), after)
