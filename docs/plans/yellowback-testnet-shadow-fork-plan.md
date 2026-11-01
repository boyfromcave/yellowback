# Ycash Yellowback (YED) testnets: the shadow-fork plan for testnet-yb-slow and testnet-legacy

**Revision 2 (2026-10-31), owner decision; implementation started.** Revision 2 folds in an independent review: the shadow upgrade is a new network upgrade, slow and legacy are built on mainnet's parameters, the founders' and dev-fund history checks, the Rust network parameters, the slow funding timeline, the client pins, harvest trust and disk sizes. This plan details revision 4 of
the [testnet plan](yellowback-testnet-plan.md): testnet-yb-slow and testnet-legacy are rebuilt as
replay-safe shadow forks of Ycash mainnet. testnet-yb-fast is unchanged. The testnet plan stays the
parent document: decisions T-1 to T-20, the bundles, the release-candidate CI and the infrastructure
are there.

**Implementers (people and agents): read §1 and §2, then go straight to §6.** It lists every work package with its repository, branch, files, fixed values, acceptance criteria and what not to touch.

## In plain words

Ycash will run three practice networks ("testnets") with worthless coins before Yellowback goes
live on the real network ("mainnet"). They differ in what they are for:

- **testnet-yb-fast** is for building and testing quickly. Every Yellowback waiting period is short,
  so a whole vault or bond lifecycle takes hours. Its history is borrowed from Zcash's public
  testnet.
- **testnet-yb-slow** is the dress rehearsal for mainnet. Every Yellowback value is exactly
  mainnet's.
- **testnet-legacy** is the control: today's Ycash rules with no Yellowback at all, so any difference
  between slow and legacy is caused by the upgrade and nothing else.

A dress rehearsal is best on the real stage. So slow and legacy start from **a copy of real Ycash
mainnet** up to a recent block, and from there on continue as testnets. This is called a
**shadow fork**. Slow then switches Yellowback on, on top of the real coins and history, exactly as
mainnet will one day.

Copying mainnet copies everyone's coins too. The one thing that must never happen is a transaction
made on a testnet being replayed on real mainnet, where it would move real money. Every Ycash
signature includes an ID of the network upgrade it was made under (the "branch ID"). So each shadow
testnet gets **its own branch IDs, which mainnet has never used and never will**. A testnet
signature is then simply invalid on mainnet, and the reverse.

## 1. The four networks side by side

| | **mainnet** | **testnet-yb-fast** | **testnet-yb-slow** | **testnet-legacy** |
|---|---|---|---|---|
| Purpose | the real network | fast iteration | mainnet dress rehearsal | control (no upgrade) |
| History before its own blocks | its own | Zcash testnet blocks 0..510,247 (`testnet-prefix-v1`) | **Ycash mainnet blocks 0..H_S** (`mainnet-prefix-v1`) | **Ycash mainnet blocks 0..H_S** (same bundle) |
| Genesis block | `00040fe8…3dce08` (Zcash mainnet's) | `05a60a92…4a2c38` (Zcash testnet's) | `00040fe8…3dce08` (mainnet's) | `00040fe8…3dce08` (mainnet's) |
| Where it splits off | — | 510,248 (the Ycash fork height, as Ycash did from Zcash) | H_S + 1 (the shadow split) | H_S + 1 |
| Branch ID of the current epoch, then after | Canopy `0x19bd2d2f`, then Vault `0x6d5b7a31` at P8 | Canopy `0x19bd2d2f` from 510,254, then Vault `0x6d5b7a31` at 510,400 | mainnet's (Canopy `0x19bd2d2f`) up to H_S; **`UPGRADE_SHADOW` with a slow-only ID** at H_S + 1; then **Vault with a slow-only ID** | mainnet's up to H_S; **`UPGRADE_SHADOW` with a legacy-only ID** at H_S + 1; nothing after |
| Vault (Yellowback) activates | at the gate-passing release (P8) | 510,400 | after the split, once the house seats can be bonded; set by slow's rc (T-15; see S0 for the funding timeline) | never |
| Set and bond maturity | 16,128 blocks (14 days) | 48 blocks (1 hour) | 16,128 | — |
| Other YED waiting periods | mainnet's | the fast column (scaled down, every invariant kept) | mainnet's | — |
| House-seat bond | 10,000 YEC (cap 20,000) | 10 TAY (cap 20) | 10,000 TAY (cap 20,000) | — |
| Founding signer set | P8 | 7 house seats | 3 house seats, then 4 invited operators | — |
| Difficulty | real mining | testnet rules | mainnet's up to H_S; minimum difficulty from H_S + 1 for one averaging window, then testnet rules (minimum-difficulty blocks allowed after H_S) | same as slow |
| Coin unit shown | YEC | TAY | TAY (copied mainnet balances are TAY, worthless) | TAY |
| Address prefixes shown | mainnet's (`s1…`, `zs…`) | testnet's | testnet's (display only; the copied history's founders' and dev-fund outputs are checked against mainnet's scripts) | testnet's (same) |
| Network magic | `24 e9 27 64` | `f7 79 62 d3` | `f7 79 62 d4` | `f7 79 62 d5` |
| P2P / RPC ports | 8833 / 8832 | 18833 / 18832 | 18933 / 18932 | 19033 / 19032 |
| Data directory | (default) | `testnet-yb-fast` | `testnet-yb-slow` | `testnet-legacy` |
| Node flag | — | `-testnet -testnetprofile=fast` | `-testnet -testnetprofile=slow` | `-testnet -testnetprofile=legacy` |
| History size (estimate) | 60–90 GB | 1 GB | 60–90 GB | 60–90 GB (non-seed nodes may prune) |

**Why fast needs no new branch IDs.** fast's history is Zcash testnet's, with a different genesis
block from mainnet's. No coin on fast exists on mainnet, so nothing on fast can be replayed there,
even though fast uses the same Vault branch ID as mainnet.

**Why slow and legacy need them.** Their coins before H_S *are* mainnet's coins. Without new branch
IDs, a transaction spending one of them would be valid on both networks.

## 2. Replay safety, end to end

1. **Up to and including H_S** (the last copied block) the shadow testnets are byte-for-byte mainnet:
   same blocks, same rules, same branch IDs. Nothing is signed on them in that range; it is history.
   No vault or YED state exists at H_S, because Vault was never active on mainnet.
2. **At H_S + 1** each shadow testnet activates a new, testnet-only network upgrade, `UPGRADE_SHADOW`.
   It has Canopy's rules and its own branch ID, which every signature commits to (ZIP-243
   `consensusBranchId`). Because it is a new epoch, the history tree also restarts there.
   - A transaction signed on slow or legacy after the split carries an ID mainnet rejects.
   - A transaction signed on mainnet carries an ID the shadow testnets reject.
   - slow and legacy use different IDs, so they cannot replay onto each other.
3. **When slow activates Vault**, it uses a slow-only Vault branch ID, not mainnet's `0x6d5b7a31`.
   Otherwise, once mainnet itself activates Vault, a slow transaction spending a copied coin would be
   valid on mainnet again.
4. **Mainnet's values never change.** `UPGRADE_SHADOW` is never scheduled on mainnet, and the
   slow-only Vault ID is used by slow alone.
5. **Tested both ways** before anything ships:
   - a shadow-testnet signature is rejected under mainnet's parameters;
   - a mainnet signature is rejected under the shadow testnet's;
   - slow's Vault ID differs from mainnet's.

**For users, defence in depth:** even with replay protection, never import a wallet that holds real
YEC into a shadow testnet. Use fresh testnet keys and the faucet. The docs, the faucet page and
the status pages say so.

## 3. What changes, by component

| Component | Change | Branch / PR |
|---|---|---|
| **Both node lines** (`ycash6`, `ycash-dd`) | (a) `UPGRADE_SHADOW`, a new network upgrade, and per-network branch IDs; (b) slow and legacy built on mainnet's parameters, with only the magic, ports, data directory, unit, displayed address prefixes, seeds and BIP-44 coin type changed; the founders' and dev-fund history checked against mainnet's scripts; (c) the difficulty reset after H_S; (d) the Rust side gets the profile's upgrade heights; (e) the RPCs report the network's own branch IDs; (f) the release guard learns H_S and the new IDs. **Consensus code: the G-9 review gate and the four-part check apply.** | `claude/shadow-fork` (in progress) |
| **librustzcash6** | new `BranchId` variants for the three new IDs (never aliases of existing ones), with the rules of the epoch they stand for; then ycash6's pin, and YEW's and x402's, move to that commit | `claude/shadow-fork` (in progress) |
| **ycash-infra** | the mainnet history harvest (`mainnet-prefix.yml`): a ycashd node syncs Ycash mainnet, exports blocks 0..H_S, verifies them against mainnet's checkpoints, the 570,000 Ycash fork block and a second independent node, packs them in the prefix format and publishes `mainnet-prefix-v1` with the Sapling tree state at H_S; import checks on both node lines. It runs on EC2 or a self-hosted runner: GitHub-hosted jobs stop at 6 hours. | `claude/mainnet-harvest` (in progress) |
| **ycash-infra** (later) | `seedctl` and the testnet chart bootstrap slow and legacy from `mainnet-prefix-v1` instead of the Zcash prefix, one network after the other; seed data volumes grow to about 300 GB per host; state bundles for slow and legacy | after the node change |
| **ycash6 / ycash-dd tools** | `ycash-bootstrap` and the ceremony learn the mainnet prefix for slow and legacy | after the node change |
| **ycash-ops** (private) | larger seed volumes; reset slow and legacy onto the shadow fork; no new secrets | owner, at launch |
| **Clients** (YEW, lightwalletd, wallets, x402, Hawkeye) | sign under the network's own branch ID, read from the node (`getblockchaininfo` consensus `nextblock`), never a hardcoded value (Hawkeye's `0x6d5b7a31` fallback goes: it fails closed); librustzcash6 pins bumped; lightwalletd and wallet birthdays start at H_S | WP-3b, checked in rc-qualify |

## 4. The steps, in order

Status: `[x]` done, `[~]` in progress, `[ ]` not started.

### S0. Decide
- [x] The shadow fork for slow and legacy, with replay-safe branch IDs (owner, 2026-10-31)
- [x] fast stays on the Zcash testnet history
- [ ] **H_S**, the last copied mainnet block: a recent height of the form k × 10,000 − 1 (for example
  3,089,999) at least 1,000 blocks below the tip when the harvest runs, so every history chunk holds
  exactly 10,000 blocks and the split is at the round k × 10,000. It is fixed by the harvest and compiled into the release;
  `UPGRADE_SHADOW` activates at H_S + 1.
- [ ] **Funding slow's house seats.** At H_S the block reward is about 1.56 TAY, so the 3 bonds of
  10,000 TAY plus a faucet take about 20,000 blocks, roughly 3 weeks at 75 s per block. slow's
  Vault height is therefore set after that (recorded at rc time from `getblocksubsidy`). The
  alternative, funding them from copied coins, is ruled out by the user safety rule (§2).
- [x] **The new branch-ID values** (owner, 2026-10-31), proposed by WP-1 and checked against every
  Zcash and Ycash ID and every magic: slow shadow `0x57a24d5d`, slow Vault `0xe1f1cc08`, legacy
  shadow `0x35706728`.
- [x] **Mining after the split** (owner, 2026-10-31): the PoW limit stays mainnet's (the copied history
  was checked against it), so a minimum-difficulty block on slow or legacy still needs about 8,192
  Equihash 192,7 solutions: GPU miners through yolo (rented on Vast.ai from `ycash-ops`: 2 × RTX
  3070 class on slow, legacy by burst; testnet plan revision 5). A separate, easier post-split limit would be a
  larger consensus change (not made). Because mining will be sparse, **every slow and legacy node runs
  with `-maxtipage=999999999`**, so the chain can sit idle for days and mining resumes whenever a
  miner returns (testnet plan §2.3; ycash-infra#19).
- [ ] **Merge timing:** WP-1 merges only once H_S is known; merging turns slow and legacy into the
  shadow profiles, which have no blocks of their own until then.
- [ ] **Where the harvest runs:** EC2 from `ycash-ops`, or a self-hosted runner.

### S1. Node changes (both lines + librustzcash6)
- [~] WP-1 and WP-2 written: draft PRs ycash6#73, ycash-dd#151, librustzcash6#19 (`UPGRADE_SHADOW`,
  per-network branch IDs, slow and legacy on mainnet's parameters, the difficulty reset, the Rust
  network parameters, the RPCs, R8 in the release guard). ycash6 pins librustzcash6 at the branch
  commit for CI; it moves to the merged commit later. CI is the first full build
- [~] Found on the way, and split out because it affects testnet-yb-fast today: ycash6#74. The Rust side
  used the old testnet's upgrade heights (Canopy 661,634, no Vault), so a ycash6 node on fast would
  reject a block with a shielded coinbase output between 510,254 and 661,634, and ycash-dd would
  accept it. It must merge, and the node image be rebuilt, before fast goes live
- [ ] Tests: replay rejected both ways; slow's Vault ID is not mainnet's; slow and legacy equal
  mainnet up to H_S; the difficulty reset
- [ ] librustzcash6 PR, then the ycash6 pin bump (WP-3), then the YEW and x402 pins (WP-3b)
- [ ] PRs on both lines; CI green; **two independent reviews (G-9)**; merge

### S2. Harvest Ycash mainnet history
- [~] `mainnet-prefix.yml`, `mainnet-prefix-import.yml`, `run-local-mainnet.sh` (the EC2 path) and their
  offline tests (69 green); the network `ycash-mainnet` in the prefix format, 10,000-block chunks,
  mainnet's 18 checkpoints vendored, the second-node cross-check and the tree state at H_S
- [ ] Run it: sync mainnet with ycashd, export 0..H_S, verify, pack; publish `mainnet-prefix-v1`
  (signed with the owner's minisign key from `ycash-ops`)
- [ ] Import checks: both node lines take the bundle under mainnet's parameters and reach H_S with
  the same hash

### S3. Bootstrap and infrastructure
- [ ] `ycash-bootstrap`, `seedctl` and the testnet chart use `mainnet-prefix-v1` for slow and
  legacy, framed with their own magic (`d4`, `d5`)
- [ ] Seed data volumes resized (about 300 GB per host); imports one network at a time; the cost
  estimate updated
- [ ] State bundles for slow and legacy at a post-split height

### S4. A release candidate that carries the shadow fork
- [ ] H_S and the checkpoint at H_S compiled in; the release guard checks them
- [ ] `rc-qualify` runs the replay test (a C++ test under slow's and mainnet's parameters)

### S5. Launch slow and legacy on the shadow fork
- [ ] In `ycash-ops`: deploy the rc image, then **reset** slow and legacy, so their seeds
  re-bootstrap from `mainnet-prefix-v1`
- [ ] Mine past H_S + 1 at minimum difficulty (`-maxtipage=999999999` on every node, the first miner's
  above all, since the copied tip is older than the node's one-day sync-age limit; a GPU miner
  through yolo after that: the Vast.ai fleet, `miners` `up` for slow and `burst` for legacy, testnet
  plan revision 5)
- [ ] Faucet, status pages and alerts per network; announce, with the user safety note (§2)

### S6. Slow's Yellowback activation (the rehearsal itself)
- [ ] slow's rc sets its Vault height (after the house seats can be funded, S0) and its slow-only
  Vault branch ID
- [ ] The ceremony for slow: its signer set at mainnet's maturity, 3 house seats, then invited operators
- [ ] legacy keeps running with no Vault: the comparison baseline

## 5. Risks

| Risk | What would happen | Mitigation |
|---|---|---|
| A replay-protection bug | a testnet transaction moves real mainnet money | new IDs on every post-split upgrade, tested both ways, G-9 review, mainnet values untouched, the user safety note |
| A client hardcodes `0x6d5b7a31` | its signatures fail on slow (safe, but broken) | clients read the branch ID from the node; rc-qualify checks |
| Size (60–90 GB) | slow syncs and harvests take hours; disks cost more; an import needs about twice the bundle in temporary space | state bundles for slow and legacy; seeds hold full history; imports one network at a time, deleting each chunk once framed; legacy non-seed nodes may prune |
| Harvest trust above the last checkpoint (2,250,000) | a bad peer feeds the harvest a wrong chain | a second independent node confirms H_S's hash; the release compiles H_S's checkpoint |
| A copied block rejected on import | slow and legacy cannot start | slow and legacy use mainnet's founders' and dev-fund scripts and mainnet's PoW parameters up to H_S; WP-1's parameter test and WP-4's import check |
| Difficulty right after the split | blocks are slow until the averaging window catches up | the one-time reset to minimum difficulty, tested on regtest-shaped data |
| Confusion with real YEC | someone treats copied balances as real | TAY everywhere, clear notes on the faucet and status pages |

## 6. Implementation guide (for agents and implementers)

### 6.1 Rules that apply to every work package

- **Workspace rules first:** `/home/user/yellowback/CLAUDE.md` (= `AGENTS.md`) and the component repo's
  own `AGENTS.md`. In particular:
  - **no AI attribution anywhere** (commits, comments, docs, PRs); commits are by `boyfromcave`;
  - `ref/` is read-only;
  - consensus code is never refactored;
  - every consensus change carries the four-part check and the in-tier ladder answer (rule 4) in its
    commit message and PR;
  - the same change is made on **both node lines** together, and the files listed in
    `qa/yellowback-cross-line.manifest` stay byte-identical (check with
    `qa/yellowback-cross-line.py` both ways);
  - modified upstream files carry a `The Ycash developers` copyright line, and the string `ycash6`
    never appears under `src/` (CI's audit enforces both).
- **Where to work:** in a `git worktree` under `/home/user/wt/<name>` on the branch named for the work
  package, cut from the repository's `upgrade/vault`.
  - Commit there.
  - **Do not push, open PRs or edit this plan**: the coordinator reviews, pushes, opens draft PRs and
    keeps the checkboxes.
  - Temporary files go in `/home/user/wt/tmp-<name>/`.
- **No node builds on the shared machine** (4 cores). Verify by reading, by the offline Python and
  qa suites, and with `cargo check` where it is light. CI builds and runs the rest after the push;
  say which tests only CI can run.
- **Public docs** have an "In plain words" section. Naming: Yellowback is the system, YED the unit,
  YEC the coin, TAY the testnet coin label.
- **Never change mainnet's values** (CMainParams, mainnet branch IDs, mainnet YED column). A diff that
  touches them is wrong.
- **Report back:**
  - commits per repository;
  - what changed, by file;
  - every check run and its result;
  - what is unverified or needs CI;
  - open questions for the owner;
  - `docs/mapping.md` §22 row text for any new impedance mismatch.

### 6.2 Fixed values every work package uses (the shared contract)

| Item | Value |
|---|---|
| Profiles (`-testnetprofile`) | `fast`, `slow`, `legacy`; `NetworkIDString()` stays `"test"` on all three |
| Magics | fast `f77962d3`, slow `f77962d4`, legacy `f77962d5`; mainnet `24e92764` |
| Ports P2P / RPC | fast 18833 / 18832, slow 18933 / 18932, legacy 19033 / 19032 |
| Data directories | `testnet-yb-fast`, `testnet-yb-slow`, `testnet-legacy` |
| Mainnet genesis | `00040fe8ec8471911baa1db1266ea15dd06b4a8a5c453883c000b031973dce08` |
| Ycash fork block (mainnet 570,000, `UPGRADE_YCASH.hashActivationBlock`) | `0000014fbc5917ba8bcacf3336faf588d86b32443aa3a490a587af5750c77ec5` |
| Mainnet Equihash | 200,9 before 570,000; 192,7 from it (unchanged after H_S on the shadow testnets) |
| fast's history | `testnet-prefix-v1` (ycash-infra release; network `zcash-testnet`, 0..510,247) |
| slow and legacy history | `mainnet-prefix-v1` (ycash-infra release, to be published; network `ycash-mainnet`, 0..H_S, same `ycash-prefix/1` format) |
| H_S | the **last copied** mainnet block; one value for slow and legacy; unset until S2's harvest fixes it |
| The shadow upgrade | `Consensus::UPGRADE_SHADOW`, a new upgrade index (after NU6_2, before VAULT), Canopy's rules, protocol version 270013, its own branch ID per network; `nActivationHeight = H_S + 1` on slow and legacy, `NO_ACTIVATION_HEIGHT` on every other network and while H_S is unset |
| slow's Vault | the existing `UPGRADE_VAULT`, with a slow-only `nBranchId` override; height unset until slow's rc |
| Founders' and dev-fund history on slow and legacy | mainnet's `vFoundersRewardAddress`, `vYcashFoundersRewardAddress` and `nYdfMandateEndHeight = 2,275,000`, resolved to scripts with mainnet's key constants. Nothing is owed after H_S: the mandate ends below it, and Ycash has no funding streams |
| Difficulty | mainnet's `powLimit` and fork-difficulty fields; `nPowAllowMinDifficultyBlocksAfterHeight = H_S`; the PoW limit for H_S + 1 … H_S + 1 + `nPowAveragingWindow`, as the Ycash fork did (`minDifficultyAtYcashFork`) |
| Rust network parameters | slow and legacy pass their own upgrade heights to the Rust side through the local-network path (as regtest does, network type Test), never librustzcash's built-in TestNetwork |
| Profile TOML keys (WP-5) | `[heights] shadow_split = H_S`; `[branch_ids] shadow = …`, `vault = …` |
| New branch IDs | three values (slow shadow, slow Vault, legacy shadow), proposed by WP-1, recorded in §4 S0 once the owner accepts them, and added to librustzcash6 as **new `BranchId` variants (never aliases)**. RPCs (`getblockchaininfo.upgrades` keys, `vault_getinfo.branchid`) report the network's own IDs; `-nuparams` keeps the global IDs |
| Branch ID a client signs with | read from the node, `getblockchaininfo` → `consensus.nextblock`; never hardcoded |
| Coin label | `TAY` on all testnets (`CChainParams::CurrencyUnits()`); amounts unchanged |
| Owner's signing key | minisign `02C923A6C593AF18`, public key `RWQYr5PFpiPJAigk86vf89bPYrJCXj5tskgRAPRYFsEXyciZo8dveOGQ` (ycash-infra `keys/ycash-release.pub`) |

### 6.3 Work packages

Dependencies:
- WP-1 and WP-2 first, together; WP-4 runs in parallel from the start.
- WP-3 and WP-3b need WP-2 merged. WP-1's ycash6 CI is judged after WP-3 (ycash6 cannot build the
  new IDs before its pin moves).
- WP-5 needs WP-1's values, WP-4's bundle format and N2 (ycash6#70, ycash-dd#147) merged.
- WP-6 needs WP-1's values and WP-4's bundle format.
- WP-7 needs WP-1, WP-5, WP-6 and N4 (ycash6#69, ycash-dd#146) merged.
- WP-8 is last.

Ownership: WP-1 owns `qa/yellowback-vault-params.py` and the release-height script; WP-7 only adds
the rc-time checks.

#### WP-1. Node: per-network branch IDs and the shadow-fork profiles (S1)
- **Repos, branch:** `ycash6` and `ycash-dd`, `claude/shadow-fork` (worktrees `ycash6-shadow`,
  `ycash-dd-shadow`). **In progress.**
- **Files:**
  - `src/consensus/upgrades.{h,cpp}` (`UPGRADE_SHADOW`; branch-ID lookup per network:
    `CurrentEpochBranchId`, `PrevEpochBranchId`, `IsConsensusBranchId`), `src/consensus/params.h`;
  - `src/chainparams.cpp` (slow and legacy on a mainnet-valued base, not `CTestNetParams`; the
    founders' and dev-fund scripts), `src/pow.cpp` (the difficulty reset);
  - `src/rust/src/params.rs` and its C++ call site (the local-network path for slow and legacy),
    `src/rust/src/history.rs` (the new `BranchId` variants dispatch to the V1 history leaves);
  - `src/rpc/blockchain.cpp` (`getblockchaininfo.upgrades` keys), `src/rpc/vault.cpp`
    (`vault_getinfo.branchid`);
  - wherever the transaction's `nConsensusBranchId` is checked;
  - `src/test/testnet_params_tests.cpp`, `src/gtest/test_upgrades.cpp`, `src/gtest/test_sighash.cpp`;
  - `qa/yellowback-vault-params.py` and `qa/yellowback-release-heights.sh` (the release guard).
- **Must do:**
  - everything in §6.2's rows for the shadow upgrade, slow's Vault, the founders' and dev-fund
    history, difficulty, Rust network parameters and branch IDs;
  - slow and legacy differ from mainnet only in magic, ports, data directory, unit, displayed address
    prefixes, seeds and BIP-44 coin type, and a test lists exactly those exceptions;
  - legacy never activates Vault;
  - the release guard (`qa/yellowback-vault-params.py`, which today expects slow and legacy as
    `CTestNetParams` subclasses) reads the new base and fields, and refuses an rc with slow or legacy
    while H_S is unset;
  - the replay test as a C++ unit test: `SelectParams` for slow (and legacy) against mainnet's
    parameters, both directions.
- **Must not touch:** mainnet values; fast's values; regtest; consensus code beyond what the
  override needs.
- **Done when:**
  - the replay test passes both ways; slow's Vault ID ≠ `0x6d5b7a31`;
  - the parameter test passes, and a copied mainnet block (a fixture from early mainnet, with a
    founders' reward output) validates under slow's parameters;
  - the difficulty reset is tested across the averaging window;
  - the cross-line check and the qa suites are green; ycash-dd CI green after the push, and ycash6
    CI green after WP-3.

#### WP-2. librustzcash6: the new branch IDs (S1)
- **Repo, branch:** `librustzcash6`, `claude/shadow-fork` (worktree `lrz6-shadow`). **In progress.**
- **Files:** `components/zcash_protocol/src/consensus.rs` (`BranchId`), and its tests.
- **Must do:** add three **new `BranchId` variants**, never aliases of existing ones (otherwise
  `u32::from(BranchId)` returns a mainnet ID and the Rust builder signs under it: a replay hole).
  The shadow variants have Canopy's semantics; the slow Vault variant has `Vault`'s (no Orchard; v5
  not valid). Signing and verification work under them.
- **Must not touch:** existing IDs and their behaviour.
- **Done when:** `cargo test -p zcash_protocol` passes, including `u32::from(BranchId::try_from(x)) == x`
  for every ID, old and new.

#### WP-3. ycash6: move the librustzcash6 pin (S1)
- **Repo:** `ycash6`, on WP-1's branch, after WP-2 is merged.
- **Files:** `Cargo.toml` `[patch.crates-io]` (every `zcash_*` crate to the merged librustzcash6
  commit), `Cargo.lock`.
- **Done when:** CI builds ycash6 against it and the sighash tests pass under the new IDs.

#### WP-3b. Clients: pins, branch IDs and birthdays (S1–S3)
- **Repos:** `yew` (`core/Cargo.toml`), `x402-ycash` (`light/Cargo.toml`, `light/src/net.rs`),
  `hawkeye`, `lightwalletd-dd`; one branch per repo, after WP-2 merges.
- **Must do:**
  - bump the librustzcash6 pins to the merged commit;
  - x402 gains slow and legacy network definitions;
  - Hawkeye's `0x6d5b7a31` fallback (`engine/sign.rs`, `burn.rs`, `ycash.rs`) is removed: it fails
    closed when the node does not answer;
  - lightwalletd starts slow and legacy at H_S (`-start-height`); YEW and x402 wallet birthdays on
    slow and legacy are at least H_S.
- **Done when:** each repo's CI is green against a node with the new IDs.

#### WP-4. ycash-infra: harvest Ycash mainnet history (S2)
- **Repo, branch:** `ycash-infra`, `claude/mainnet-harvest` (worktree `infra-mharvest`).
  **In progress.**
- **Files:**
  - `bundles/prefix/` (`FORMAT.md` gains the `ycash-mainnet` network; the verifier gains mainnet's
    checkpoints, vendored from `ycash6` `src/chainparams.cpp` with a sha256, and the 570,000 fork
    block);
  - `.github/workflows/mainnet-prefix.yml` and its import checks;
  - offline tests.
- **Must do:**
  - a ycashd node (the published image, or the CI `node-bin`) syncs mainnet from Ycash peers;
  - export blocks 0..H_S with `getblock <hash> 0`;
  - verify the hash chain from the mainnet genesis, every compiled checkpoint and the fork block;
  - above the last checkpoint (2,250,000), confirm H_S's hash and a few heights in between against a
    **second independent node**, and record both;
  - pack deterministically; `manifest.json` records H_S (the last copied block), its hash, time and
    `chaintx`, and `SHA256SUMS`;
  - publish `mainnet-prefix-v1` (chunks under 2 GiB) to a GitHub release, or to S3 behind an input,
    with `z_gettreestate` at H_S beside it;
  - run on EC2 (`run-local.sh`) or a self-hosted runner; GitHub-hosted jobs stop at 6 hours.
- **Must not touch:** `infra/testnet-seeds/`, `node-image.yml`, ycash-ops.
- **Done when:**
  - offline tests, actionlint, zizmor, shellcheck and `make lint` are green;
  - after the real run: two runs give an identical `SHA256SUMS`;
  - both node lines import it under mainnet parameters and reach H_S with the same hash.

#### WP-5. Node tools: bootstrap and ceremony on the shadow fork (S3)
- **Repos, branch:** `ycash6` and `ycash-dd`, `claude/shadow-tools` (after N2's PRs ycash6#70 and
  ycash-dd#147 merge, which add these tools).
- **Files:**
  - `contrib/yellowback/profiles/testnet-yb-slow.toml` and `testnet-legacy.toml`: mainnet genesis,
    the history bundle `mainnet-prefix-v1` and its pinned `SHA256SUMS` hash, `[heights] shadow_split`,
    mainnet's Equihash schedule, `[branch_ids] shadow` and `vault`;
  - `contrib/bootstrap/ycash-bootstrap`: the history bundle per profile;
  - `contrib/testnet/ceremony/ceremony`: slow's mainnet-scale maturity and bonds (it checks the
    wallet holds enough mined, shielded TAY before the seats step); mining past H_S + 1 needs
    `-maxtipage`, because the copied tip is old;
  - `test_ybprofile.py` keeps checking the profiles against the compiled parameters.
- **Done when:**
  - the offline tests are green;
  - `ycash-bootstrap --network testnet-yb-slow` verifies and imports a mainnet-shaped regtest bundle in
    a test;
  - the profile test passes against WP-1's parameters.

#### WP-6. Infrastructure: seeds and charts per history (S3)
- **Repo, branch:** `ycash-infra`, `claude/shadow-infra`.
- **Files:**
  - `infra/testnet-seeds/nodes/` (`variables.tf`, `locals.tf`, `files/seedctl`): today one shared
    `var.prefix` serves every network. It becomes **per network**: fast keeps `testnet-prefix-v1`,
    slow and legacy take `mainnet-prefix-v1`; each is framed with its network's magic;
  - imports one network at a time, deleting each downloaded chunk once it is framed (an import
    needs about twice the bundle in temporary space);
  - the default data volume sized for fast + slow + legacy (about 300 GB);
  - `charts/ycash-testnet/values-{yb-slow,legacy}.yaml` (the prefix restore per network) and the
    snapshotter's state bundles for slow and legacy;
  - the cost notes; the import timed on an rc image (with H_S's checkpoint compiled in).
- **Must not touch:** the `ips` layer (the addresses stay); fast's behaviour.
- **Done when:**
  - `make seeds-validate`, `make lint`, `make lint-testnet` and the Checkov gate are green;
  - `tests/seedctl.sh` covers a reset of slow onto the mainnet prefix while fast is untouched.

#### WP-7. Release: the shadow fork in a release candidate (S4)
- **Repos:** `ycash6` (and the ycash-dd guard), on top of N4 (ycash6#69, ycash-dd#146).
- **Must do:**
  - the rc-time checks on top of WP-1's guard: H_S, its checkpoint and the new IDs are set and
    consistent;
  - rc-qualify runs WP-1's replay unit test (`-nuparams` cannot schedule slow's IDs on regtest, so the
    test, not a network harness, is the check);
  - client checks (YEW, x402, Hawkeye, lightwalletd) confirm signing uses `consensus.nextblock`.
- **Done when:** the guard tests and rc-qualify's offline tests are green.

#### WP-8. Launch (S5, S6): coordinator and owner, not an agent
1. Merge WP-1..WP-7 and publish `mainnet-prefix-v1` signed with the owner's key.
2. Fix H_S and the IDs in an rc, and build its image.
3. In ycash-ops: resize the seed volumes, then reset slow and legacy onto the shadow fork.
4. Mine past the split.
5. Turn on the faucet, status pages and alerts.
6. Announce, with the user safety note.

Then S6: slow's Vault rc and its ceremony.
