# Reorganisation depth and check order: ycashd vs koganyd (beta3 item 12, note N-4)

Copyright (c) 2026 The Ycash developers. Decision note for the Yellowback lead architect. Read-only:
no node code changes with this note. Chunk 12 (kogany, two independent reviews) implements what is
approved here.

Heads read (2026-11-15, all `origin/upgrade/vault`): ycash6 `9a794e7619` (the reference), ycash-dd
`f273cf90af`, kogany `0c4f678f62`. Citations: `y6:` ycash6, `dd:` ycash-dd, `kg:` kogany.
Nothing was run; every claim is a code reading, and the tests in §5 are what turns each into a fact.

## 1. Recommendation table

| # | Difference | Validity parity? | Proposed (kogany, `ycash` feature only) | Size, crates | Gate | Recommend |
|---|---|---|---|---|---|---|
| R1 | Reorg of 100..1,000 blocks: ycashd shuts down, koganyd follows | yes (fork choice, not validity) | **(b)** refuse a reorg that rolls back more than 99 blocks and shut down with ycashd's message; keep `MAX_BLOCK_REORG_HEIGHT` = 1,000 | M, ~100–150 lines + tests; `zakura-state` (consensus path), `zakurad` (shutdown wiring) | two reviews | **(b)** |
| R2 | Reorg of 1,001+ blocks: ycashd shuts down, koganyd ignores the branch and stays up | yes | covered by R1(b) (the guard fires first) | 0 beyond R1 | — | with R1 |
| R3 | Order: kogany checks MTP time before `nBits`; ycashd `nBits` first | yes | swap the order under `ycash` in `validate_contextual_difficulty_and_time` | S, ~15 lines + 2 vectors; `zakura-header-chain/src/validation/` (consensus path) | two reviews | **swap** |
| R4 | Score of the two MTP time rules: ycashd 0, kogany 100 (commit path) and a disconnect (header path) | yes | (a) keep 100, document; or (b) 0 on the commit path, only together with R3 | (b) S, ~10 lines; `zakura-state/src/error.rs` (not consensus path) | one review | **(a) document** |
| R5 | `high-hash` score: ycashd 50, kogany 100 | yes | do nothing, document | 0 | — | **document** |
| R6 | Order: ycashd checks the Equihash solution before the hash; kogany the hash first | yes | do nothing, document (Zakura's deliberate cheap-check-first order) | 0 | — | **document** |
| — | Local-clock rule (`time-too-new`): both score 0, both retry later | yes, and same score | none | — | — | MATCH |

No difference found changes which blocks are valid. Every one changes fork choice (R1, R2), a
reject reason (R3, R6) or a peer penalty (R4, R5).

## 2. Reorganisation depth (R1, R2)

**ycashd.** `MAX_REORG_LENGTH = COINBASE_MATURITY - 1` = 99 (`y6:src/main.h:69`, `dd:src/main.h:66`).
In `ActivateBestChainStep` the depth is `reorgLength = oldTip.nHeight - fork.nHeight`, the number of
blocks that would be disconnected (`y6:src/main.cpp:5004`, `dd:src/main.cpp:4135`). If
`reorgLength > 99` (`y6:5006`, `dd:4137`), before any block is disconnected, the node logs and shows
"A block chain reorganization has been detected that would roll back %d blocks! This is larger than
the maximum of %d blocks, and so the node is shutting down for your safety." (`y6:5007-5020`),
calls `StartShutdown()` and returns false. "Shuts down" means the process exits cleanly on its old
tip; nothing is marked invalid. So 99 disconnected blocks are followed; 100 or more stop the node,
**however deep the fork**, as long as the branch has more work and the node has its blocks (the
branch is only a candidate once its bodies are stored). The same bound guards the startup rewind
(`y6:src/main.cpp:7483-7505`, `dd:5639-5660`). ycash-dd agrees line for line (it uses `LogPrintf`
where ycash6 uses `LogError`). Proved on both C++ lines by `qa/rpc-tests/reorg_limit.py` (99 followed,
100 stops the node with the message for 100 blocks; in `y6:qa/pull-tester/rpc-tests.py:190`).

On restart the block index still holds the heavier branch, so `ActivateBestChain` meets it again and
shuts down again: ycashd stays down until an operator acts (`invalidateblock` on the branch to stay,
or `-reindex` to accept it). This is a code reading; `reorg_limit.py` does not restart the node.

**koganyd.** `MAX_BLOCK_REORG_HEIGHT = 1000` (`kg:crates/zakura-chain/src/parameters/constants.rs:30`,
re-exported `kg:crates/zakura-state/src/constants.rs:20`), documented there as "a local-only node
policy; it is not part of consensus". It is a finality window, not a guard: after each commit the
writer finalizes the oldest block while the best non-finalized chain is longer than 1,000
(`kg:crates/zakura-state/src/service/write.rs:3408-3412`). A fork whose parent is the finalized tip
or above is followable (`kg:crates/zakura-state/src/service/read/block.rs:331-336`); below it, the
parent is unavailable, gossip drops the block without a penalty
(`kg:crates/zakurad/src/components/inbound/downloads.rs:1061-1065,1125-1139`) and the header graph
keeps the branch but marks it ineligible (`FinalityConflict`,
`kg:crates/zakura-header-chain/src/graph/header_node.rs:63-67`). So, by rollback depth d:

| d (blocks rolled back) | ycashd | koganyd today |
|---|---|---|
| ≤ 99 | follows the heavier branch | follows |
| 100 | **shuts down** | follows |
| 999, 1,000 | shuts down | follows |
| 1,001 and deeper | shuts down | ignores the branch, stays up on its chain, keeps serving and mining |

**What happens when both meet a 100–1,000-block heavier branch.** Both consider every block on both
branches valid; this is **not a consensus (validity) split**. It is a fork-choice difference with
two consequences:

- Availability: every ycashd that downloads the branch stops (pools on ycashd stop too); every
  koganyd switches silently and carries on.
- Divergence afterwards: kogany is on the attacker's branch, ycashd is down on the old tip. If ycashd
  operators then `invalidateblock` the branch (the usual answer to a hash-rate attack), the two
  node lines sit on different chains until kogany operators do the same (kogany has
  `invalidateblock`, `kg:crates/zakura-rpc/src/methods.rs:247`). Anyone using a kogany-backed service
  (the planned mainnet explorer and insight node, a lightwalletd behind it) sees 100+ confirmations
  reversed with no alarm, where ycashd users get a halt.

**Proposed R1(b).** Under `ycash`, before switching the best chain, compute the rollback depth
(old best tip height minus fork height); if it is above 99, do not switch, log ycashd's message
word for word, and shut the node down; feature off, unchanged. Three requirements for the chunk:
(1) the check sits where the best chain changes (the non-finalized commit path in `zakura-state`;
`non_finalized_state.rs` is on the consensus path list `kg:qa/kogany-consensus-paths.txt`);
(2) it must survive a restart: with the default non-finalized backup on
(`kg:crates/zakura-state/src/config.rs:477`) the restarted node reloads its old tip and meets the
branch again, but with the backup off (or `ephemeral`) a restarted koganyd has no old tip to compare
and would adopt the branch, so the chunk either refuses to start in that case or records the
refusal durably; (3) the depth counts disconnected blocks exactly as ycashd does, so 99 passes and
100 stops.

**Why not set the window to 99 (option c).** It would leave koganyd up on its old chain (not
ycashd's halt), and the window is load-bearing elsewhere: the header-chain engine pins it
(`kg:crates/zakura-header-chain/src/config.rs:478,502`, spec v1.3), the checkpoint generator asserts
it is at least coinbase maturity 100 (`kg:crates/zakura-utils/src/bin/zakura-checkpoints/main.rs:37`,
so 99 fails to compile), and the pruning floors, the YED undo window and the queue and locator sizes
derive from it (`kg:crates/zakura-state/src/constants.rs:68-78`,
`kg:crates/kogany-rpc/src/yed/live.rs:1072-1086`, `service.rs:415`, `write.rs:1490`). Rejected.

**Do nothing, document (option a).** Defensible only while kogany serves no mainnet users: the
difference is reachable only by a hash-rate attack of 100+ blocks. Risk if left: on such an attack
kogany-backed services follow the attacker while ycashd halts, and the lines can end on different
chains.

## 3. Check order and ban scores (R3–R6)

Score scale: ycashd bans at 100 (`state.DoS(n)`; `state.Invalid` is 0). kogany's commit path uses
`misbehavior_score` (100 bans); its header-sync path has no score: a peer fault disconnects the peer
and imposes a readmission cooldown (`kg:crates/zakura-network/src/zakura/header_sync/reactor.rs:5210-5226,5258-5266`).

**R3, order of difficulty and MTP time.** ycashd checks `nBits` (`bad-diffbits`, DoS 100) before
`time-too-old` and `time-too-far-ahead-of-mtp` (DoS 0) (`y6:src/main.cpp:6129-6153`; `dd:4771-4795`,
`state.Invalid`). kogany checks `TimeTooEarly`, then `TimeTooLate`, then `InvalidDifficultyThreshold`
(`kg:crates/zakura-header-chain/src/validation/contextual/validate.rs:56-92`), one function for both
the header path (`.../transition/planner/event_effects/header_validation.rs:135-141`) and the commit
path (`kg:crates/zakura-state/src/service/check.rs:468`). The two rules are independent, so the
accept/reject set is the same. What differs: for a block wrong in both, `submitblock` and proposal
answer `time-too-old`/`time-too-far-ahead-of-mtp` on kogany
(`kg:crates/zakura-rpc/src/methods/types/ycash_reject.rs:443-445`) and `bad-diffbits` on ycashd.
Proposed: under `ycash`, check difficulty first (move the `disable_pow` / expected-difficulty block
above the two time checks, `cfg`-gated). Risk if left: a reject string differs for doubly invalid
blocks only; no network effect.

**R4, score of the MTP time rules.** ycashd scores both 0 (`y6:6136-6153`, `dd:4777-4795`). kogany
scores `TimeTooEarly` and `TimeTooLate` 100 on the commit path
(`kg:crates/zakura-state/src/error.rs:1167-1174`); the header path reports them as
`ContextualDifficultyAndTime` and disconnects the peer
(`kg:crates/zakurad/src/commands/start/zakura/header_sync_driver.rs:780-810`). Now that the constants
agree (kogany #27, `2f247bd32`), an honest ycashd peer validates both rules before relaying, so it can
never send such a block; the 100 only bites if the parameters disagree again, which is how kogany
banned its honest peers at fast 510,256. Options: (a) keep 100 and document; this was the choice in
#27 (`620066216`), after review B showed that a score of 0 ahead of the difficulty check lets a
peer feed near-free invalid blocks unpunished. (b) 0 on the commit path under `ycash`, only after R3,
so a wrong `nBits` still scores 100 first; the header path keeps its disconnect (splitting it would
touch the header-chain planner for a peer-policy gain). Recommend (a). Risk if left: self-partition
only under a future parameter mismatch, which the cross-line tests exist to catch.

**R5, `high-hash` score.** ycashd scores a hash above its own `nBits` target 50
(`y6:src/main.cpp:5956-5959`, `dd:4658-4660`); kogany scores `DifficultyFilter` 100
(`kg:crates/zakura-consensus/src/error.rs:875-885`). Same rejection; kogany bans after one such block,
ycashd after two. Proposed: document. Risk if left: none for honest peers (an honest block always
meets its target).

**R6, Equihash vs hash order.** ycashd checks the solution (`invalid-solution`, 100) before the hash
(`y6:5951-5959`, `dd:4652-4660`); kogany checks the difficulty filter first, deliberately
("Do the difficulty checks first, to raise the threshold for attacks",
`kg:crates/zakura-consensus/src/block.rs:513-516`), then Equihash (100,
`block.rs:258-262`). Same rejection; for a block bad in both, the reason is `high-hash` on kogany
(`ycash_reject.rs:513`) and `invalid-solution` on ycashd, and both score 100. Proposed: document.

**Local-clock rule (checked, matches).** ycashd `time-too-new` DoS 0 (`y6:6157-6161`); kogany
`BlockError::Time` scores 0 and is retryable (`kg:crates/zakura-consensus/src/block.rs:209,258-265`),
both at 4 hours since #27 (`kg:crates/zakura-chain/src/block/header.rs:94-97`).

## 4. Corrections to the sweep (`wt/handoff/KG-CONSENSUS-SWEEP.md`, 2026-11-12)

- A1 and A2 (90 min / 2 h) are stale: kogany #27 (`2f247bd32`) set 10,800 s and 4 h under `ycash`
  (`kg:crates/zakura-header-chain/src/validation/contextual/constants.rs:63-70`, `header.rs:94-97`).
- F10 is right on the numbers and the halt. Sharper: ycashd stops at 100 rolled-back blocks for any
  fork depth, so above 1,000 the lines also differ (kogany up, ycashd down), not only in 100..1,000.
- F9's "both refuse reorgs deeper than their window" is wrong for ycashd: it does not refuse and
  carry on, it shuts down.
- Review B's MEDIUM-2 (score 0 ahead of the difficulty check) is moot at today's head: `620066216`
  restored 100.

## 5. Tests that prove parity

**T1 (R1, R2), cross-line regtest, new `crates/kogany-rpc/qa/reorg_parity.py`** on the plumbing of
`rpc_ycash_parity.py` (ycashd mines, koganyd is fed by `submitblock`; kogany's regtest PoW waiver,
sweep B8, does not matter because every block comes from ycashd). Two ycashd nodes A and B and one
koganyd K share 200 blocks. For each rollback depth d in {99, 100, 101}: A mines d blocks (K gets
them), B mines d+1 on the common tip (K gets them), then A and B are connected. Expected:

| d | ycashd A | koganyd K (after R1(b)) |
|---|---|---|
| 99 | follows B, `getbestblockhash` = B's tip | same hash as A |
| 100, 101 | exits; stderr has "would roll back d blocks!" | exits with the same sentence; old tip kept |

Then restart A and K: both stop again (the restart requirement), and K with the backup disabled must
not adopt B's branch. Today's kogany fails the d = 100 row (it follows), which is the regression the
chunk fixes. Run against both ycash6 and ycash-dd binaries; `reorg_limit.py` already proves the C++
side on each line. A `zakura-state` unit test pins 99 accepted / 100 refused and feature-off
unchanged (1,000 window, no shutdown).

**T2 (R3, R6), reject reasons.** kogany regtest waives PoW and the `nBits` value (sweep B8), so these
cannot be cross-line regtest tests. Use unit vectors in `zakura-header-chain` with mainnet parameters
and real headers: one header with both a wrong `nBits` and time = MTP must give
`InvalidDifficultyThreshold` under `ycash` and `TimeTooEarly` with the feature off; the
`ycash_reject` mapping test checks `bad-diffbits`. Add the same case to
`crates/kogany-rpc/qa/rpc_reject_parity.py` once regtest PoW parity (B8) exists.

**T3 (R4, R5), scores.** Unit tests on `misbehavior_score` pinning the chosen values under `ycash`
and upstream's with the feature off; if R4(b) is chosen, one more vector shows that a wrong `nBits`
plus a bad time still scores 100.

## 6. What chunk 12 then touches

R1(b): `zakura-state` (non-finalized commit path, consensus path list; two reviews), `zakurad`
(shutdown), new `reorg_parity.py`, its CI row. R3: `zakura-header-chain/src/validation/contextual/validate.rs`
(consensus path; two reviews). R4(b) if chosen: `zakura-state/src/error.rs` (one review). R2, R5, R6:
a `docs/mapping.md` §24 row each and a release-note line. Feature off stays upstream Zakura's
behaviour in every case.
