# koganyd on the three Ycash testnets

**2026-11-07. Preservation plan.** ycash6 is already running testnet-yb-fast, testnet-yb-slow, and
testnet-legacy. koganyd on `upgrade/vault` is not. A local implementation exists and could not be
pushed to `boyfromcave/kogany` or `boyfromcave/zakura-common-ycash` from the machine that wrote it
(GitHub 403 for `cursor[bot]`). This document and the patch files beside it are how that work
survives. The parent description of the networks is
[yellowback-testnet-shadow-fork-plan.md](yellowback-testnet-shadow-fork-plan.md) and
[yellowback-testnet-plan.md](yellowback-testnet-plan.md).

**Fact** is what is in a tree or a commit named below. **Intent** is what a later environment
should do with it. This note does not claim a koganyd process was run against the live seeds.

## In plain words

Ycash has three practice networks. Fast is a short-cycle chain borrowed from Zcash's public
testnet. Slow and legacy are copies of real Ycash mainnet up to a fixed block, then their own
networks, so a practice transaction cannot be replayed on mainnet. kogany, the Rust full node,
knows mainnet and an older idea of the testnets. The patches teach it the three networks ycash6
is actually running. One companion patch teaches the shared Rust cryptography crate the three
new signature IDs. Until that crate change is pushed and kogany's pin moves, kogany still cannot
check a signature made after the copy of mainnet ends.

## 1. What ycash6 does

**Fact.** ycash6's default branch is `upgrade/vault`. The shadow-fork commits since 2026-10-31
are on it: `0b2e8dcfe` (2026-10-31, slow and legacy as shadow forks) and `9b29019c9` (2026-11-03,
`H_S` and its checkpoint). They are ancestors of ycash6 `upgrade/vault` at `a8120c787` (the
checkout this plan was written against). There is no second default to follow.

All three profiles are `-testnet -testnetprofile=<fast|slow|legacy>`. `NetworkIDString()` stays
`"test"`. Data directories and RPC ports are in `ycash6/src/chainparamsbase.cpp`. Consensus
parameters are in `ycash6/src/chainparams.cpp`. Branch IDs are in `ycash6/src/consensus/upgrades.h`.

| | testnet-yb-fast | testnet-yb-slow | testnet-legacy |
|---|---|---|---|
| Flag | `-testnetprofile=fast` | `-testnetprofile=slow` | `-testnetprofile=legacy` |
| Data directory | `testnet-yb-fast` | `testnet-yb-slow` | `testnet-legacy` |
| Magic | `f77962d3` | `f77962d4` | `f77962d5` |
| P2P / RPC | 18833 / 18832 | 18933 / 18932 | 19033 / 19032 |
| History | Zcash testnet 0..510,247, then a Ycash fork at 510,248 | Ycash mainnet 0..H_S | the same bundle |
| Genesis | `05a60a92…4a2c38` | mainnet `00040fe8…3dce08` | mainnet genesis |
| After the split | Vault at 510,400, branch ID `0x6d5b7a31`, set maturity 48 | `UPGRADE_SHADOW` at H_S+1, id `0x57a24d5d`; Vault unset, id `0xe1f1cc08` when it is scheduled; maturity 16,128 | `UPGRADE_SHADOW` at H_S+1, id `0x35706728`; Vault never |
| Yellowback column | `TestFastParams` | mainnet's column | module stays off |

`H_S = 3,079,999`. The checkpoint hash is
`000005030be4763e433447000ef6b98c7ce310a8b0b7bb50f1a6aca3d31e4bef`
(`TESTNET_SHADOW_SPLIT_HEIGHT` / `TESTNET_SHADOW_SPLIT_HASH` in `ycash6/src/chainparams.cpp`).
`UPGRADE_SHADOW` uses protocol version 270013. `ycash6/src/pow.cpp` returns the PoW limit for the
shadow activation block and the next averaging window, and allows minimum-difficulty blocks only
after `H_S`. Slow and legacy inherit mainnet's founders' and YDF scripts and mandate end
2,275,000, and display testnet address prefixes. Fast keeps the re-forked testnet parameters,
including `minDifficultyAtYcashFork` and mandate end 900,000.

librustzcash6 at `d384b90d` already has `BranchId::SlowShadow`, `LegacyShadow`, and `SlowVault`
(`librustzcash6/components/zcash_protocol/src/consensus.rs`). ycash6 links that crate. kogany
links `zakura-common-ycash`, which on `upgrade/vault` (`13fdc53`) does not.

## 2. What kogany on upgrade/vault still is

**Fact.** Before the local commits, kogany `upgrade/vault` at `b3f5f70ee` treats
`network = "Testnet"` as the fast re-fork (magic, ports, genesis, Vault at 510,400). Its slow
network object is that same re-fork with magic `f77962d4` and no Vault height, and nothing in
`kogany.toml` selects it (`docs/mapping.md` M24-89). There is no legacy profile, no magic
`f77962d5`, and no port 19033. `NetworkUpgrade` has no shadow epoch. Branch IDs are one table
for every network, Vault `0x6d5b7a31`
(`kogany/crates/zakura-chain/src/parameters/network_upgrade.rs`). The fast checkpoint list
(`kogany/crates/zakura-chain/src/parameters/checkpoint/ycash-test-checkpoints.txt`) is marked
`# PARTIAL` and stops at 510,247, and the consensus router sends the pre-Canopy gap above that
list to the checkpoint verifier, which rejects it. Every testnet loads the mainnet-scale
Yellowback column, not `test_fast_params()`.

**Fact.** kogany's Cargo pin of `boyfromcave/zakura-common-ycash` is
`049895445b6fe7a9db20b484736008952a6d6d94` (`kogany/Cargo.toml`). That revision's `BranchId`
does not contain the three shadow ids. `ConsensusBranchId` converts through
`zcash_protocol::BranchId::try_from`. An unknown id fails the conversion, and the sighash
path that builds a librustzcash transaction fails with it.

## 3. What the local commits implement

Two commits, each one commit past that repo's `upgrade/vault`. Neither has been pushed.
`git format-patch` copies are in [kogany-testnet-profiles/](kogany-testnet-profiles/).

| Repo | Branch (local only) | Commit | Parent (`upgrade/vault`) | Patch |
|---|---|---|---|---|
| `kogany/` | `cursor/ycash-testnet-profiles-f733` | `2183b3461d2009906fbd72df5724f9bf5f9c24ae` | `b3f5f70eeadf593232f4e082714cf98db9d61969` | `0001-kogany-add-the-three-ycash-testnet-profiles.patch` |
| `zakura-common-ycash/` | `cursor/shadow-branch-ids-f733` | `83c70a26748e6d2afcca80443cba1b01757d9b05` | `13fdc539adb3f4dae8f2107ac368211b6d30089c` | `0001-zakura-common-ycash-shadow-branch-ids.patch` |

**Fact, kogany `2183b3461` (46 files, +663/−140).** Checked by reading that commit, not by
re-running it for this document.

- Config names: `network = "Testnet"` (also `fast`) is yb-fast. `network = "TestnetSlow"` (also
  `slow`) and `network = "TestnetLegacy"` (also `legacy`) build the shadow profiles.
  `kogany/crates/zakura-chain/src/parameters/network.rs` (`FromStr`) and
  `kogany/crates/zakura-network/src/config.rs` (toml). A round-trip of those two names writes
  the string back, not a dumped parameter table.
- Fast stays the Zcash-testnet re-fork. Blocks above the partial checkpoint list are verified
  semantically (`kogany/crates/zakura-consensus/src/router.rs`). The fast Yellowback column is
  what `yed_network_params` loads for magic `f77962d3`
  (`kogany/crates/zakura-state/src/service/finalized_state/zakura_db/yed.rs`).
- Slow and legacy are built from mainnet activation heights plus `NetworkUpgrade::Shadow` at
  3,080,000, mainnet genesis, mainnet PoW limit, max-time rule from height 2, and a checkpoint
  list that is mainnet's list cut before 3,080,000 plus the H_S pin
  (`kogany/crates/zakura-chain/src/parameters/ycash.rs`).
- Per-network branch ids: slow shadow `0x57a24d5d`, slow Vault `0xe1f1cc08`, legacy shadow
  `0x35706728`. `ConsensusBranchId::current` and `NetworkUpgrade::branch_id_on` supply them.
  History-tree nodes use `branch_id_on`. Sighash takes an explicit branch id
  (`kogany/crates/zakura-chain/src/transaction/sighash.rs`,
  `kogany/crates/zakura-script/src/lib.rs` `CachedFfiTransaction::new_on`).
- PoW: fast resets to the PoW limit across the Ycash-fork window; shadow activation does the
  same; mainnet and the shadow forks keep the scaled Ycash-fork window
  (`kogany/crates/zakura-header-chain/src/validation/contextual/adjusted_difficulty.rs`).
  Minimum difficulty on a shadow network starts at 3,080,000, not at 299,188
  (`network_upgrade.rs`).
- Founders and YDF on a shadow network use the mainnet lists and mandate end 2,275,000
  (`kogany/crates/zakura-chain/src/parameters/ycash/ydf.rs`).
- `getblockchaininfo.testnetprofile` reports `fast`, `slow`, or `legacy`
  (`kogany/crates/zakura-rpc/src/methods/types/ycash.rs`).
- Shadow profiles advertise mainnet's per-upgrade protocol versions; the shadow upgrade itself
  is 270013 (`kogany/crates/zakura-network/src/ycash.rs`).

**Fact, common fork `83c70a2` (2 files, +65/−12).** `BranchId::SlowShadow`, `LegacyShadow`, and
`SlowVault` in `zakura-common-ycash/crates/zcash_protocol/src/consensus.rs`, with `rules()`
mapping the shadow ids to Canopy and `SlowVault` to Vault. Transaction version checks in
`zakura-common-ycash/crates/zcash_primitives/src/transaction/mod.rs` treat all three as v4.
`cargo check -p zakura-protocol -p zakura-primitives` succeeded on that commit. It is not
kogany's pin.

**Fact, tests run on the kogany commit, `ycash` feature, not against a live peer.**

- `zakura-chain` lib: `parameters::ycash` (13), `parameters::checkpoint::list::ycash_tests` (4,
  including the shadow list), `parameters::vault_tests` (11).
- `zakura-header-chain` lib: `ycash_fork_windows_reset_to_the_pow_limit`.
- `zakura-network` lib: `ycash::tests` (19), including the protocol-version table.
- `zakura-rpc` lib: `testnet_profile_matches_ycashd` (fast, slow, legacy). Linking that test
  needed `RUSTFLAGS="-C link-arg=-L/usr/lib/gcc/x86_64-linux-gnu/13"` because the default linker
  did not find `libstdc++`.

## 4. What is still open

**Fact.**

- The common-fork pin in `kogany/Cargo.toml` is unchanged. Post-split signature checks that
  convert the branch id still fail until `83c70a2` (or an equivalent tree) is on
  `boyfromcave/zakura-common-ycash` and the pin moves to that commit. The kogany patch does not
  contain that pin bump, because the commit was not on the remote.
- Fast still has no checkpoint hashes above 510,247. ycash6's own fast list also stops there.
  The kogany change verifies those blocks semantically instead of rejecting them. That is not
  the same as a pinned checkpoint.
- State directories stay kogany's: `testnet`, `testnetslow`, `testnetlegacy` under the kogany
  cache dir (`kogany/crates/zakura-state/src/config.rs` uses `lowercase_name()`). They are not
  `testnet-yb-fast`, `testnet-yb-slow`, or `testnet-legacy`.
- No ycash-infra chart, seed, or `mainnet-prefix-v1` bootstrap for koganyd. Seeds and charts
  still start ycashd (`ycash-infra/infra/testnet-seeds/README.md`).
- No koganyd process was pointed at the live seeds. Slow's Vault height is unset, matching
  ycash6 until slow's release candidate sets one.
- `cursor[bot]` received HTTP 403, "Permission denied", on
  `git push` to `boyfromcave/kogany` and to `boyfromcave/zakura-common-ycash`.

**Intent.** A later environment that can push those two repositories reapplies the patches,
pushes the common fork first, bumps kogany's pin, then pushes kogany. Section 5 is that
procedure. Deployment, datadir renaming, and a live peer test stay out of these two commits.

## 5. How to reapply the commits

The patches apply with `git am` from each repository root. They were taken with
`git format-patch -1` of the commits above. `git am` preserves the author and the message. The
committer is whoever applies them, so the new commit SHA will not equal the SHA in the table
unless the committer and timestamps match. That is expected.

**Intent, order.**

1. Confirm each repo's `upgrade/vault` still contains the parent in the table
   (`b3f5f70ee` in kogany, `13fdc53` in zakura-common-ycash). If `upgrade/vault` has moved,
   create the branch from the parent SHA, apply, then rebase onto the new `upgrade/vault` and
   resolve. Do not apply onto an unrelated history.
2. Common fork first:

   ```bash
   cd zakura-common-ycash
   git checkout upgrade/vault
   git checkout -b cursor/shadow-branch-ids-f733
   git am --3way /path/to/yellowback/docs/plans/kogany-testnet-profiles/0001-zakura-common-ycash-shadow-branch-ids.patch
   cargo check -p zakura-protocol -p zakura-primitives
   git push -u origin cursor/shadow-branch-ids-f733
   ```

   Record `git rev-parse HEAD`. Call it `COMMON_SHA`.
3. Kogany:

   ```bash
   cd kogany
   git checkout upgrade/vault
   git checkout -b cursor/ycash-testnet-profiles-f733
   git am --3way /path/to/yellowback/docs/plans/kogany-testnet-profiles/0001-kogany-add-the-three-ycash-testnet-profiles.patch
   ```

   If this clone still has `2183b3461d2009906fbd72df5724f9bf5f9c24ae`,
   `git diff 2183b3461d2009906fbd72df5724f9bf5f9c24ae HEAD` must be empty.
4. Pin the common fork. In `kogany/Cargo.toml`, replace every
   `049895445b6fe7a9db20b484736008952a6d6d94` with `COMMON_SHA`. Run
   `cargo update` so `Cargo.lock` follows that git commit. This is a second commit. It is not
   in the patch.
5. Re-run the tests in section 3, plus a check that
   `zcash_protocol::consensus::BranchId::try_from(0x57a24d5d)` is `SlowShadow` (and the same
   for `0x35706728` and `0xe1f1cc08`). That check fails on the old pin and passes after step 4.
6. Push `cursor/ycash-testnet-profiles-f733` to `boyfromcave/kogany` and open the pull request
   against `upgrade/vault`. Open the common-fork pull request against `upgrade/vault` as well.
   Land the common fork before kogany's pin commit, or kogany's CI cannot fetch `COMMON_SHA`.

Do not force-push. Do not apply these patches on top of each other in one repository: each
patch is for its own repo.

## 6. What not to treat as done

**Intent.** Merging this yellowback pull request does not change koganyd. It only stores the
plan and the patches. koganyd joins the three testnets only after section 5, and only a run
against the live seeds can say the node stayed in consensus with ycash6.
