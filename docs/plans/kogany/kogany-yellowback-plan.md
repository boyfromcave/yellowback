# Ycash Yellowback (YED) and the vault network upgrade on kogany (Zakura) — integration plan

**Revision 1 (2026-11-01).** Synthesis of the five planning surveys in [`surveys/`](surveys/) (lanes A–E,
same date). Nothing is ported yet: kogany `upgrade/vault` = `kogany-legacy` = Zakura `main` @
`2b062412c5`. Modelled on [`yellowback-ycash6-plan.md`](../yellowback-ycash6-plan.md) (the 4.5.0 →
6.20.0 port) and the execution-status style of [`yellowback-upgrade-plan.md`](../yellowback-upgrade-plan.md).
Items are numbered **K-\*** (owner decisions), waves **W0–W9**, chunks **W<n>-<x>**, findings
**KF-\*** (§9) and mapping rows **M24-\*** (§10).

**Pins.** Every citation is at these commits unless it names another tree.

| Tree | Ref | Commit |
|---|---|---|
| `ref/zakura` (= `kogany` `upgrade/vault` = `kogany-legacy`) | detached | `2b062412c5` |
| `ref/ycash6` | detached | `040894344b` |
| `ref/ycash` | v4.5.0 | `624c12814` |
| `ycash6` | `upgrade/vault` | `65cb4ae0f` |
| `ycash-dd` | `upgrade/vault` | `781946771` |
| `librustzcash6` | `upgrade/vault` | `af841431` |
| `zakura-zcash-script` 0.0.1 (crates.io, checksum = `ref/zakura/Cargo.lock:3636`) | `zakura-core/common` `crates/zcash_script` | `ca4c341ed9c4` |
| `zakura-protocol`/`-primitives`/`-address`/`-equihash` 5.0.0-rc.2 (crates.io) | `zakura-core/common` | `bdbca121628d` |

Paths starting `crates/`, `.github/`, `qa/`, `docs/` or `Cargo.*` with no tree named are under
`ref/zakura/`. Crate-package citations are written `zakura-protocol:src/…` (lane B's convention).

---

## Execution status (authoritative; update as work lands)

Legend: `[x]` done and verified on the integration tree, `[~]` in flight (agent / branch named),
`[ ]` not started, `[-]` deliberately out of scope.

**Owner decisions (§0):** K-1 … K-19 all **pending**. W0 may start once K-2, K-5, K-15 and K-19 are
answered; W1 needs K-1, K-9, K-10, K-11, K-12 as well.

| Wave | Content | State | Gate seen green |
|---|---|---|---|
| W0 | scaffolding: fork repos, baseline tag, CI allowlist, security CI, audit legs, crate verification | [ ] not started | — |
| W1 | Ycash network on Zakura (Y0–Y8): branch IDs, Equihash (192,7), YDF, checkpoints, P2P, RPC answers, sync | [ ] not started | — |
| W2 | Vault epoch: `NetworkUpgrade::Vault`, `0x6d5b7a31`, v4-only, U-26 builder, vectors pinned | [ ] not started | — |
| W3 | script and PQ: CSV 0xb2, 0xc0, 0xc1, 0xc2, BIP68, SLH-DSA/Falcon verification | [ ] not started | — |
| W4 | the vault primitive: templates, acts, set state, storage, snapshot, reorg | [ ] not started | — |
| W5 | the YED rule module: math, params, codecs, attestations, state, index | [ ] not started | — |
| W6 | relay policy and mempool | [ ] not started | — |
| W7 | read RPCs (`vault_*`, `set_*`, `yed_*`), `rpcversion` 8 contract | [ ] not started | — |
| W8 | mining: template filter, coinbase tag | [ ] not started | — |
| W9 | wallet via ycash6 sidecar, full mixed matrix, client legs, demonstration | [ ] not started | — |

**Branches.** Integration branch `upgrade/vault` in `kogany` and in the common fork (K-2); agents
work in `wt/<chunk>` on `up/<chunk>` off `upgrade/vault`; the coordinator merges. No commit to
`kogany-legacy` or the fork's `-legacy` baseline, ever.

---

## Summary for the owner (reads standalone)

**What kogany is.** kogany is your fork of **Zakura**, a Rust full node that is consensus-compatible
with Zcash and descends from the Zcash Foundation's Zebra. It would become the third Ycash node
line beside the two C++ lines, `ycash-dd` (ycashd 4.5.0) and `ycash6` (ycashd 6.20.0). Today it
knows nothing about Ycash: there are zero occurrences of "ycash" in its crates, and an unpatched
Zakura cannot validate a single Ycash transaction after Ycash's fork at height 570,000. This plan
makes kogany a Ycash node first and then gives it the vault network upgrade and the Ycash
Yellowback (YED) rule module, so that it agrees with both C++ lines block for block.

**Your two constraints, and how the plan meets them.**
1. *Minimal integration, gate do not delete.* Zakura already keeps upgrades dormant the way you
   want: an upgrade with no activation height on a network is simply never switched on, and its
   code stays compiled and tested. The plan relies on exactly that mechanism. NU5 (Orchard),
   NU6.x (including Ironwood) and NU7 stay in the code with no Ycash height. Vault goes into
   Zakura's upgrade list **between Canopy and NU5**, and all Yellowback code goes into new crates.
   Upstream files are touched only at named hooks, measured per wave. Zakura's own NU5–NU7
   tests must stay green on kogany at every wave. That is the proof that nothing was deleted.
2. *Get it right.* The work is split into ten waves. Each wave has a gate one agent can run from a
   clean worktree. The oracle is what the C++ lines already share: nine golden-vector files that
   are byte-identical on both lines, the Python reference model, and the state hashes
   (`vault_getinfo.statehash`, `yed_getstatehash`). kogany never generates a vector. It must
   reproduce every one and match ycash6's state hash at every height of every shared regtest
   script.

**The shape of the answer.**
- **W0 scaffolding.** Fork repos, CI and the audit legs.
- **W1 Ycash on Zakura.** Ycash's own branch IDs, Equihash (192,7), the development-fund rule,
  checkpoints and P2P versions. Its exit gate is a full sync of Ycash mainnet that agrees with
  ycash6 block by block.
- **W2–W5 the vault and the module, bottom up.** The Vault epoch, then the script opcodes and
  post-quantum signature checks, then the vault primitive and its state, then the YED module.
  Each layer is checked against the vectors before the next starts.
- **W6–W8 the node around them.** Relay policy, the read RPCs and mining.
- **W9 the full test matrix.** kogany has no wallet. Wallet functions are covered the way Zakura
  itself covers them: a ycash6 node runs beside it as a wallet sidecar.

**Headline numbers** (estimates; §7 carries the uncertainty):

| Item | Size |
|---|---|
| The C++ Yellowback delta kogany has to match (`ycash6`, `ycash6-legacy...upgrade/vault`) | 5,498 files, **+192,129** lines; ~70 % tests, qa and tooling; ~30k production node lines |
| Share of that production code a wallet-less node needs | ~60 % (consensus core, policy, mining, 32 read RPCs); the 47 wallet RPCs and PQ signing do not port |
| New hand-written Rust production code in kogany | ~20–27k lines, about 70 % of it in new `kogany-*` crates (plus ~6k lines of vendored PQ verification C) |
| Edits to upstream Zakura files (the touch budget) | ~5–8k lines, about half of it in W1 (network identity is spread across many crates) |
| Edits to the forked crates (`zakura-core/common`) | ~0.9–1.3k lines (branch IDs, Ycash constants, Vault, four opcodes) |
| Tests | ~25–30k lines plus ~7k lines of generated checkpoints |
| Effort | **~70–105 agent-days** across 10 waves and 48 chunks; calendar time is set by the two-person consensus review gate and by mainnet sync wall-clock time |
| Owner decisions | 19 (K-1 … K-19), six of them decisive |

**The biggest risks.**
1. **Order is a feature switch in Zakura.** Copying the C++ position of Vault (after NU5..NU6.2)
   compiles and is consensus-dead: it would switch on v5 transactions, Orchard and, at NU7, 25-second
   blocks and a ban on the v4 transactions every vault spend uses. Handled by K-1 and §2.
2. **A third implementation of consensus code in a different language.** The fixed-point
   arithmetic of the YED module (`src/yellowback/math.h`) is the highest byte-exactness risk:
   Rust wraps on overflow in release builds, and a `HashMap` iterates in random order. Handled by
   K-4, the vector replays and the §4 disciplines.
3. **Dependency forks.** Zakura's librustzcash crates reject every Ycash branch ID, and its script
   interpreter is a crates.io crate. Both must be forked and kept rebaseable onto upstream (K-2).
4. **No wallet.** The roles that sign inside the node cannot run on kogany: attestors in `attest`
   mode, Hawkeye bridge members, the node bundled with YecWallet, and x402's `rpcWalletSigner`.
   They keep a ycashd (K-3).
5. **Upstream churn.** Zakura moves fast at the tail of its upgrade list (NU7 already has a
   mainnet height). The plan inserts in the middle and syncs upstream at wave boundaries (§4).

---

## 0. Owner decisions

Every "Open question for the owner" from the five surveys, deduplicated. The source column names
the survey questions merged into each row (A2 = lane A question 2, D-3 = lane D's D-3, and so on).
The six decisive ones come first. **Each recommendation is the plan's default;** a chunk that
needs a decision does not start before it is answered.

| # | Decision | Options | Recommendation and why | Blocks | Source |
|---|---|---|---|---|---|
| **K-1** | **Upgrade-enum placement.** Zakura's `NetworkUpgrade` order *is* the feature gate. | (a) `Ycash` between Sapling and Blossom, `Vault` between Canopy and Nu5, both new variants in height order; (b) Vault at the end (C++ order); (c) Vault after Nu6_2 (literal ycash6 mirror); (d) Vault not an upgrade, a parameter plus branch-ID override; (e) per-network upgrade sequences | **(a).** (b)/(c) inherit NU5–NU7 rules and fork on the first Vault block (§1.2). (d) spreads an override across 17 `branch_id()` callers and the history-tree reset. (e) rewrites ~20 Ord gates, which makes rebasing hostile. With (a), "v5 is invalid under Vault" (U-26) falls out of the existing gates. Vault activity is tested only by **explicit membership** (`is_vault_active`, §2), never by `current >= Vault`. | W1 (Ycash variant), W2 | A1, D-1, B (lane D input) |
| **K-2** | **Crate-fork strategy** for `zakura-protocol`/`-primitives`/`-address`/`-transparent` and for `zakura-zcash-script`. | (O1) Ycash-only replace-in-fork (the librustzcash6 pattern); **(O2)** feature-gated fork (`ycash` cargo feature); (O3) shim inside kogany, no fork; (O4) swap in librustzcash6's crates; (O5) upstream generalisation | **O2, one fork repo of `zakura-core/common`** carrying both the librustzcash crates and `crates/zcash_script`. Both come from that monorepo (§1.4), so one fork with one `-legacy` baseline. kogany pins it by exact rev through `[patch.crates-io]`, as ycash6 pins librustzcash6. Under O2 the forked crates are upstream when the feature is off, so upstream tests still run. O3 cannot represent Ycash's NU5 ID `f919a198` and so fails constraint 1. O4 breaks every NU6.3/NU7/v6 API. Pursue O5 alongside as an upstream proposal, never as a dependency. **Name** to be chosen (lane B suggests `zakura-common-ycash`); add it to `repos.yaml` with `-legacy` at the base commit. | W0, W1, W3 | A3, B1, C-T3 |
| **K-3** | **Wallet-less node, sidecar, or external signer.** | (a) wallet-less: read RPCs only, with signing roles staying on ycashd and the wallet functions served by a ycash6 `connect=` sidecar (Zakura's zcashd-compat pattern); (b) an external-signer interface (PSBT-like build/sign/send) in kogany; (c) a native kogany wallet | **(a).** Far smaller. The sidecar fully validates every block it receives, so it doubles as a two-line differential. kogany serves the read and node-state RPCs (R1–R4, §1.6). The "build" RPCs (`vault_buildunlock`, `vault_buildcancel`, `set_buildact`, `yed_buildcancel`) are **wallet RPCs**: they fund from the wallet and remember the build in it (`ycash6/src/rpc/vault.cpp:2002-2019,2191`). They stay on the sidecar. YecWallet against kogany is out of scope (it bundles ycashd). Record that attestor `attest` mode, Hawkeye and x402's `rpcWalletSigner` need ycashd. Revisit (b) only after W9. | W7 scope, W9 | A2, B7, C1, E3, E4 |
| **K-4** | **Rust rewrite or C++ through FFI** for `src/vault` and `src/yellowback` consensus code. | (a) rewrite in Rust as new `kogany-*` crates, checked by the vectors, the Python model and mixed regtest; (b) link the C++ overlay through FFI; (c) hybrid: FFI for pure codecs, Rust for state | **(a)** for the primitive and the module, with **vendored C only for PQ verification** (K-8). The C++ overlay is entangled with `CCoins`, LevelDB, `cs_main` and the 11 pinned shim files where the two C++ lines already differ (`qa/yellowback-cross-line.manifest`). Those are exactly the places Zakura differs most: concurrent semantic checks, RocksDB column families, `UpdateWith` reorgs. `zakura-script` is `forbid(unsafe_code)`. A Python model already exists as an independent implementation, and the vectors are designed to check another one. The cost is a third implementation, and the risk is the arithmetic (§4.4). | W3–W5 | C3 |
| **K-5** | **Runtime or compile-time gating; the shape of the Ycash network.** | Ycash identity: (a) compile-time `ycash` profile that swaps the mainnet/default-testnet/regtest constants (lane B); (b) a runtime `Network::Ycash` variant (touches ~641 non-test `Mainnet` sites); (c) Ycash mainnet as a configured `Testnet` (wrong `kind()` and t-addr kind). Vault: (d) runtime parameter (height `None` on Zcash networks); (e) cargo feature or `cfg`. | **(a) for network identity and (d) for Vault, reconciled as in §2.3:** the `Ycash` and `Vault` enum variants and the `0x6d5b7a31` table row exist in **every** build, as inert data without a height. The Ycash *values* (branch IDs of Blossom/Heartwood/Canopy/NU5, heights, ports, prefixes, Equihash and YDF rules) sit behind the `ycash` feature. So the feature-off build behaves as Zakura on Zcash networks, and upstream's NU5–NU7 tests run there with Vault present and dormant. The feature-on build is Ycash-only. Lane D's "keep Zcash networks in kogany" (D-3) is met by the feature-off build, not inside the Ycash binary. CI builds both ways. | W0 (CI matrix), W1, W2 | B2, D-3, D-5 |
| **K-6** | **C++ lines' `CurrentEpoch` realignment as a precondition of relaxing U-26.** On ycashd the epoch is the highest *index* with a height, and Vault's index is above NU5..NU6.2. If NU5 were ever scheduled after Vault, `CurrentEpoch` would return Vault forever (`ycash6/src/consensus/upgrades.cpp:130-139`). | (a) realign `ycash-dd`, `ycash6` and librustzcash6 now (Vault below NU5); (b) record it as a mandatory precondition of any U-26 relaxation and do nothing now | **(b).** It has no consensus effect today, because U-26 forbids scheduling Vault with any of NU5..NU6.2 (`ycash6/src/init.cpp:1541-1565`). Moving it now would put changes through the consensus review gate on both C++ lines for no behaviour. Record the four-line ordering divergence as invariant M24-3 and add the precondition to upgrade plan U-26's "given up". | none now; any future NU5 on Ycash | D-2 |
| K-7 | **Implicit activation and the far boundary.** In Zakura, adopting a later Zcash upgrade brings every earlier one. Tachyon ⇒ NU7 ⇒ 25 s blocks + v4 ban. | (a) accept, and record that Ycash cannot adopt NU7 or Tachyon until a v5/v6 vault signing message exists and the block-count constants are recalibrated for 25 s blocks; (b) per-network sequences (O5 in lane D) to cherry-pick | **(a).** Cherry-picking means rewriting every Ord gate. Also confirm that `0xf919a198` (`ycash6/src/consensus/upgrades.cpp:68`) is the reserved Ycash NU5 branch ID, so the W1 table carries it. | none now (record in W2) | D-4, D-6, D-7 |
| K-8 | **PQ verification source.** | (a) vendor the C++ lines' verify-only C (PQClean Falcon, slhdsa-c, with local patches) through `cc`; (b) Rust crates (YEW uses `slh-dsa =0.1.0`), held to the KAT/ACVP vectors and malformed cases | **(a)**, byte-identical by construction, pinned by SHA256SUMS as `yew/core/pq-c/README.md` does. Signing code is not vendored (no wallet). (b) stays an option once the malformed-encoding corpus exists. | W3 | A4, C4, C-T4 |
| K-9 | **Pre-Canopy trust and checkpoint coverage.** Zakura validates pre-Canopy blocks by checkpoint hashes only. | (a) checkpoint-only through 1,100,005, as Zakura does for Zcash, stated as an assumption; (b) also port the Ycash-fork difficulty and pre-Canopy YDF for an independent re-validation | **(a)**, written down. Checkpoint lists must **never** cover Vault-epoch blocks until kogany's vault and YED state matches the C++ lines there (M24-14). | W1 (Y4) | B4, D-T7 |
| K-10 | **Testnet profiles.** ycash6 carries three re-forked profiles (fast, slow, legacy). | (a) all three; (b) fast and slow only, with legacy testnet3 dropped as ycash6 did | **(b)**, as lane B recommends. | W1 (Y1, Y4) | B5 |
| K-11 | **Zakura's v2 P2P overlay (QUIC, signed discovery) on Ycash.** It identifies a chain by genesis hash, which Ycash shares with Zcash. Fixed seed IPs. | (a) legacy TCP only first, v2 off; (b) design a Ycash `chain_id` now (from the fork block `0000014f…7ec5` or a domain tag) | **(a).** Design (b) later as a network-layer change. Find out in W1-Y5 whether Zakura's peer cache can carry fixed seeds. | W1 (Y5) | B6 |
| K-12 | **Release-state machinery and fast-sync artefacts** (frontier grid `zakura-assets`, VCT manifest, `treestate_artifact.rs`, `scripts/check-release-state.sh`): all Zcash-mainnet bytes. | (a) disable on Ycash; (b) build Ycash equivalents | **(a).** Vault and YED state must never be imported from an artefact (M24-13). Revisit (b) after W9. | W1 (Y4) | B8 |
| K-13 | **Reorg window.** Zakura keeps 1,000 non-finalized blocks (`crates/zakura-chain/src/parameters/constants.rs:30`); ycashd's limit is 99 and its vault undo is kept 4,096 deep. | keep 1,000, or align to 99 | **Keep 1,000.** It is local policy, not consensus. It sets the memory spent on per-fork vault deltas, which W4 measures. | W4 | A5 |
| K-14 | **Offline rollback past Vault.** Zakura's finalized state is undone only by the offline `rollback` tool (`zakura_db/rollback.rs:1`). | (a) `rollback` refuses past the Vault height and asks for a resync; (b) keep a finalized vault/YED undo | **(a)** first. It is smaller, and the C++ `-reindex` analogue is a resync anyway. | W4 | A6 |
| K-15 | **Upstream CI on kogany.** All 40 workflows are off. | (a) six trimmed (`lint`, `tests-unit`, `zakura-e2e` pr-gate, `docs-check`, `test-crates` weekly, header/rpc fuzz weekly), 21 fleet/release/Slack ones off, enabled one at a time; (b) more | **(a)**, plus the four workspace security workflows and `kogany-yellowback.yml` (§5). Scheduled jobs only after kogany's default branch is `upgrade/vault`. | W0 | E1 |
| K-16 | **Mining on kogany.** Its internal miner solves (200,9) only, and regtest PoW is waived (shape check only). | (a) kogany validates (192,7) but never solves it; regtest PoW is checked by the C++ peers in mixed tests, and kogany-produced regtest blocks are solved by the Python (48,5) solver; (b) add Ycash solvers or a regtest PoW switch | **(a)**, with the gap recorded (M24-20). | W1 (record), W8 | E2, E7 |
| K-17 | **Notifications.** Zakura has no ZMQ and no `-blocknotify`. chain-viz uses ZMQ (`chain-viz/src/collector.rs:178`). | (a) chain-viz polls (or uses Zakura's gRPC `indexer.proto` streams) against kogany: no node change; (b) add a notify hook | **(a).** | W7 | C6, E5, A-§8 |
| K-18 | **Functional test reuse.** 48 of the 58 Yellowback functional scripts need a wallet on at least one node. | (a) mixed-line harness: the unchanged scripts gain kogany followers (`KOGANY_BIN`) whose tips and state hashes are asserted at every sync point; (b) port wallet RPCs so scripts run on kogany alone | **(a).** One run is both the C++ regression and the kogany equivalence check. CI runs it with and without `KOGANY_BIN`. | W1 (harness skeleton), W4+ | C2, E-§3.2 |
| K-19 | **When kogany becomes a qualified line, and the AGENTS.md amendment.** | (a) at the end of W9 by explicit owner decision: release train, three-way rc-qualify, "both lines" → "all lines"; until then kogany follows vector changes by a PIN bump and is report-only for clients; (b) earlier | **(a).** Amend AGENTS.md at W0 *now* only for the layout (kogany and the common fork as working forks, rule 2 branch names) and the shared-defect rule, which becomes "C++ lines together; librustzcash6, the common fork and kogany follow in the same change set from W2 on." Release obligations wait for (a). Also: who tries to obtain **Yolk v4.3.1** (§8, R-9)? | W0 (amendment), end of W9 | C5, E6, B3, B-synthesis |

---

## 1. What the surveys found

### 1.1 Corrections to the briefing (and which figure is right)

| Briefing said | Survey finding | Right |
|---|---|---|
| Yellowback delta "~86k inserted lines" per C++ line | `git -C ycash6 diff --shortstat ycash6-legacy...upgrade/vault` = 5,498 files, **+192,129 / −455** over 685 commits; ycash-dd +188,230 / −328 over 926 commits (lane C §Summary; re-measured for this plan). Fuzz corpora are 4,993 of the files; `qa/` +49k, `src/test/` +38k, `contrib/` +40k. No obvious subset gives 86k (excluding `src/fuzzing` still leaves 190,942). | **192k.** ~30k of it is production node code. |
| "Zakura ships 53 workflows" | `.github/workflows/` at the pin has **40** workflow YAML files (56 YAML files under `.github` counting composite actions and app configs) (lane E §5.1; re-counted with `git ls-files`) | **40** |
| `zakura-zcash-script` interpreter: Rust or C++ FFI? (lane A could not read the source) | Confirmed for this plan (§1.4): pure Rust, no `build.rs`, no C sources, no `unsafe` block | **Pure Rust** |
| C survey: "22 `vault_*.py`, ~45 `yellowback_*.py`" | `ycash6/qa/rpc-tests/` has 16 `vault_*.py` and 42 `yellowback_*.py` (lane E §3.2; re-counted) | **16 + 42 = 58** |
| A survey: kogany can serve the build-unsigned RPCs (`vault_build*`, `yed_buildcancel`) | They call `EnsureWallet` and fund from and remember in the wallet (`ycash6/src/rpc/vault.cpp:2002-2019` `vault_buildunlock`, `:2191` `vault_buildcancel`, `set_buildact` `:1619`); lane C classifies them as wallet RPCs (R5/R6) | **Lane C**: they need the sidecar (K-3) |

### 1.2 Upgrades, activation and branch IDs (lanes A, D)

- `NetworkUpgrade` derives `Ord`, and its variants "must be ordered by activation height"
  (`crates/zakura-chain/src/parameters/network_upgrade.rs:23-27`). Declaration order is checked at
  compile time against `NETWORK_UPGRADES` (`:73-100`). `current()` is the highest-height entry at
  or below h in `activation_list()` (`:388-393, 406-426`). **Mainnet is hard-coded**:
  `activation_list()` returns `MAINNET_ACTIVATION_HEIGHTS` for `Mainnet` and the configured map
  for `Testnet` (`:388-393`).
- **`activation_height(nu)` falls back to the next upgrade's height** when `nu` has none
  (`:459-469`, verified). Zakura relies on this, for example in the NU7 v4 ban
  (`crates/zakura-consensus/src/transaction.rs:1043-1053`). So on Zcash Mainnet a Vault placed
  before Nu5 "activates" at NU5's 1,687,104 if anyone asks `Vault.activation_height()` (lane D
  T1).
- **Order is a feature gate.** About 20–23 non-test sites compare upgrades (lane A counts 23,
  lane D "about 20"; the difference is grep scope, not substance). The ones that matter most:
  - `is_nu7_active` = `current >= Nu7`, and "every upgrade after NU7" counts as NU7-active (`:636-642`, verified);
  - v5 needs a branch at or above Nu5 (`transaction/serialize.rs:1140`);
  - v6 needs Nu6_3 or later (`serialize.rs:834,1199`; `transaction.rs:1243`);
  - NU6 coinbase equality (`block/check.rs:377`);
  - the NU7 fee split (`subsidy/fees.rs:25`);
  - spacing and averaging window (`network_upgrade.rs:503-617`);
  - ZIP-244 auth-data roots (`checkpoint.rs:1355-1357`, `finalized_state.rs:943,1081`).
- **Placing Vault after NU5..NU7 (the C++ order) is consensus-dead.** It inherits v5/v6, Orchard,
  ZIP-244 commitments, the NU6 coinbase rule, and at Nu7 the 25 s spacing and the v4 ban, so
  every vault spend becomes invalid (lane D §1 table). Placing Vault between Canopy and Nu5 makes
  every one of those gates read "Canopy era".
- **Exhaustive matches** force a decision for a new variant at about 10 sites:
  - spacing and window;
  - v4/v5 network-upgrade acceptance (`transaction.rs:1055-1083, 1168-1191`);
  - history-tree leaf version (`history_tree.rs:126-170`, `primitives/zcash_history.rs:425-446`);
  - block commitment (`block/commitment.rs:130-150`);
  - halo2 (`primitives/halo2.rs:394`);
  - P2P minimum versions (`zakura-network/src/protocol/external/types.rs:88-127`);
  - GBT roots;
  - the configured-heights conversion (`testnet.rs:178-204`).

  **Wildcard `_ =>` arms compile silently.** Known case: `get_block_template/proposal.rs:206-216`,
  where a Vault template would fall into the "pre-Canopy" error.
- **Configurable activation.** `ConfiguredActivationHeights` has one `Option<u32>` per upgrade
  and is `serde(deny_unknown_fields)` (`testnet.rs:547-582`). `for_regtest` back-fills Overwinter
  to Canopy only (`:589-628`). Heights go into a `BTreeMap<Height, NU>`, so one upgrade per
  height: **the later variant overwrites an earlier one at the same height** (`:924-929`). The
  builder refuses out-of-order maps and height 0 (`:959-976`).
- **Branch IDs come from one global table** (`network_upgrade.rs:249-274`), and each converts to
  librustzcash through `BranchId::try_from(u32)` in `Transaction::to_librustzcash`
  (`crates/zakura-chain/src/transaction.rs:1857-1878`). That conversion **rejects**
  `0x6d5b7a31` and every Ycash ID (`374d694f`, `8e471bd6`, `66314da3`, `19bd2d2f`).
  `zakura-protocol:src/consensus.rs:744-760` knows only Zcash IDs. It is reached from
  `SigHasher::new` → `PrecomputedTxData::new` (`transaction/sighash.rs:173-185`) and from coinbase
  note decryption (`primitives/zcash_note_encryption.rs:12-17`). The v4 ZIP-243 digest itself is
  native Rust and reads the u32 from Zakura's table (`transaction/sighash/v4.rs:147-170`). That
  is inferred from code, and `vault_vectors.json` must confirm it (lanes A, B, D).
- **Precedent for a mid-sequence insert:** upstream wired NU6.3 in as a no-op activation height in
  `51d3d8839` (2026-06-21, 27 files, +124/−37, verified).

### 1.3 Ycash identity on Zakura (lane B)

- **Ycash differs from Zcash in about a dozen places; Zakura hard-codes every one for Zcash.** They
  sit in two layers. First, Zakura's own tables keyed on the unit variant `Network::Mainnet`, with
  641 non-test mentions (`parameters/network.rs:62-73`). Second, the `zakura-*` crates: branch
  IDs, address constants, parsing.
- **Shared with Zcash:** the genesis blocks and the network magic (`ref/ycash6/src/chainparams.cpp:214-228`).
  That is why the regtest chains are wire-compatible (§1.7), and also why Zakura's v2 overlay
  would treat Ycash and Zcash as one chain (`zakura-network/src/zakura/handshake.rs:265-271`; K-11).
- **Equihash.** (200,9) before 570,000 and (192,7) after (`ref/ycash6/src/consensus/upgrades.cpp:37-43`,
  `pow.cpp:155-191`). Zakura's `Solution` has only `Common([u8;1344])` and `Regtest([u8;36])`, and
  `check` picks (200,9) for every non-regtest network (`work/equihash.rs:43-72,102-115`). The
  verifier crate accepts (192,7) (`zakura-equihash:src/params.rs:9-22`). Zakura deliberately never
  derives (n,k) from solution length, and that protection must be kept.
- **The development fund (YDF).** From 570,000 to 2,274,999 the coinbase pays exactly 5 % to a
  rotating P2PKH/P2SH list; from 2,275,000 it is unchecked (`ref/ycash6/src/main.cpp:5901-5939`,
  `chainparams.cpp:348-371`). Zakura's founders' reward ends at the first halving, and its Canopy
  funding streams are P2SH-only (`crates/zakura-consensus/src/block/check.rs:205-300`). This is live
  consensus from Canopy (1,100,006) to 2,274,999.
- **Prefixes and HRPs** (`s1`, `s3`, `sm`, `ys`, `ytestsapling`, `yregtestsapling`, coin type 347;
  `ref/ycash6/src/chainparams.cpp:161-182`), **ports** 8833/8832 and friends, **seeds**, **P2P
  versions** (270013 floor, 270200 at Vault; `ref/ycash6/src/version.h:13-56`). Zakura advertises
  170_190 (`zakura-network/src/constants.rs:350-364`), so every ycashd peer would drop it.
- **Checkpoints.** The 1,493 shared entries at or below 569,686 are reusable from
  `checkpoint/main-checkpoints.txt`. Above that the list must be regenerated from a synced ycash6
  (~7k lines). Pre-Canopy Ycash rules are then enforced by hashes, not code (K-9).
- **The library delta librustzcash6 needed** is about 250 lines with tests:
  - `02d42df5`: the Ycash variant and IDs, `ZIP212_GRACE_PERIOD` 3, prefixes;
  - `ec525fae`: tests;
  - `4867cf85` + `eeb7740d`: Vault, made v4-only.

  Those commits apply one for one by meaning, not mechanically, to `zakura-core/common` 5.0.0-rc.2.

### 1.4 The script crate (lane A, confirmed by this plan)

Lane A could not read `zakura-zcash-script`'s source and reasoned from upstream `zcash_script`
0.4.5. Lane B had read the package header. For this plan the crate was downloaded from crates.io
(`/api/v1/crates/zakura-zcash-script/0.0.1/download`) into the scratchpad, not into any repo. Its
SHA-256 is `d6e8e9ee2f42d0925d6c95337746d698b0ecc9cf21c8e1e69587bda65cfc80f5`, which equals
`ref/zakura/Cargo.lock:3636`. Findings, cited as `zakura-zcash-script:<path>`:

- **Pure Rust.** `.cargo_vcs_info.json` names `zakura-core/common` @ `ca4c341ed9c4`, path
  `crates/zcash_script`; the manifest says `repository = "https://github.com/zakura-core/common"`.
  There is no `build.rs` and there are no C/C++ sources. Dependencies are bitflags, bounded-vec,
  ripemd, sha1, sha2, thiserror and optional secp256k1 0.33 (`Cargo.toml.orig`). `src/lib.rs:8`
  says `#![allow(unsafe_code)]`, but the crate contains **no `unsafe` block**. The only "extern C"
  is a stale doc comment (`src/interpreter.rs:452`). It is `#![no_std]` (`src/lib.rs:3`), and its
  doc root says `zcash_script/0.6.0` (`:5`), so it forks a newer upstream than the 0.4.5 lane A
  compared against.
- **What lane A predicted holds:**
  - the flag set ends at `CHECKLOCKTIMEVERIFY = 1 << 9` (`src/interpreter.rs:136-180`);
  - `SignatureChecker` has only `check_sig` and `check_lock_time` (`:184-196`);
  - 0xb2 is `OP_NOP3` and 0xb9 is `OP_NOP10` (`src/opcode/mod.rs:399-407,469-477`);
  - 0xba and above, 0xc0–0xc2 included, decode to `Bad::Unknown` → `BadOpcode`
    (`:1193-1205,1279`);
  - there is no sequence check.

  So **CSV, `OP_CHECKSETSIG`, `OP_CHECKSETDORMANT` and `OP_CHECKPQSIG` all need interpreter changes
  in a fork**: new opcode variants, flag bits 10–12, and checker callbacks for set signatures,
  post-quantum signatures and sequence.
- **Consequence for K-2.** The interpreter and the librustzcash crates live in the **same
  upstream repository**, so one fork covers both. But the crates.io packages were cut at two
  different commits (`bdbca121628d` and `ca4c341ed9c4`). **W0-b verifies** that one fork commit
  rebuilds both packages with identical sources (or picks the fork base accordingly) before any
  patch lands.

### 1.5 Validation, state and mempool (lane A)

- **Three layers.**
  1. Structural (`zakura-chain`).
  2. Semantic, per transaction and **concurrent** (`zakura-consensus`, `block.rs:595`).
  3. Contextual, in `zakura-state` when a block is pushed onto an in-memory fork
     (`service/non_finalized_state.rs:790`, `chain.rs:346`, `UpdateWith` at `chain.rs:1909-1940`).

  A script request carries only `(cached tx, input_index)`: no height and no chain state
  (`zakura-consensus/src/script.rs`). Script flags are a constant, `P2SH | CHECKLOCKTIMEVERIFY`,
  for every height (`zakura-script/src/lib.rs:170`).
- **Fits well:**
  - a spent coin carries its height (`transparent/utxo.rs:17-28`; `request.rs:446-482`), so the
    C++ `'v'` replay-height index has no problem to solve, though rule S-0 stays for cross-line
    identity;
  - reorgs drop in-memory forks, so there is no vault undo log in the non-finalized window;
  - the NSM rule already awaits the parent's committed state (`block.rs:503-530`, `AwaitBlockInfo`
    `request.rs:1572`), which is the pattern for "scripts read set state after the parent".
- **Checkpointed blocks skip contextual validation** (`router.rs:401`, `checkpoint.rs:1371`) and
  share one finalized write path with finalization (`finalized_state.rs:754` →
  `zakura_db/block.rs:1348`). So vault and YED transitions must be *computed* in that write path,
  must be total, and must never fail.
- **Column families** are listed at `service/finalized_state.rs:163-225`, with format version 30
  (`constants.rs:103`). `disk_format/upgrade/add_ironwood_tree.rs` is the precedent for new
  column families.
- **Mempool.** A tip `Reset` happens on any upgrade activation (`chain_tip.rs:640-658`), so Vault
  activation clears the mempool for free. On `Grow` nothing re-checks scripts
  (`mempool.rs:1072-1110`), so the C++ `RecheckMempool` needs a new hook. The data carrier is
  limited to 83 bytes (`mempool/config.rs:87`), where an act needs 1,200. There is no BIP68
  anywhere.
- **Templates** go through the full block verifier (`get_block_template.rs:1075`;
  `block.rs:619-625`). That probably removes ycash6's `TemplateRun::Try` gap, but **selection**
  still needs a sequential act filter (`zip317.rs:83`).
- **RPC** is one `rpc_trait!` trait of ~41 methods (`zakura-rpc/src/methods.rs:300-1010`). A
  second trait needs a small dispatcher, which is not prototyped (*uncertain*). There is **no
  wallet, no `signrawtransaction`, no ZMQ, no `-blocknotify`**. Zakura's wallet answer is a
  zcashd sidecar (`docs/zcashd-compat.md:1-40`). Notifications come from gRPC streams
  (`zakura-rpc/proto/indexer.proto:99-129`).

### 1.6 The delta kogany must carry (lane C)

| Class | ycash6 source | Lines (ycash6) | Wallet-less kogany |
|---|---|---|---|
| Upgrade plumbing C1–C7 (Vault row, previous-epoch walk-back, heights/profiles, v4-only, Rust branch ID, history leaf V1, protocol 270200) | `src/consensus/{params.h,upgrades.cpp}`, `src/chainparams.cpp`, librustzcash6 | ~400 | Yes |
| Script S1–S6 (BIP68, CSV, 0xc0/0xc1, 0xc2, PQ verify, `TX_PQPKH`) | `src/script/*`, `src/crypto/pq/`, `src/vault/checker.*` | ~1k + ~6k vendored verify C | Yes (signing half no) |
| Primitive P1–P6 (templates, acts, set state, storage, module table, hooks) | `src/vault/*`, `src/main.cpp` hooks | ~4k | Yes; storage is *re-expressed*, while the `StateHash` preimage stays exact |
| YED module Y1–Y8 (params, math, payload/script/address, attest/bundle, tag, state/view, index, glue) | `src/yellowback/*` (excluding wallet files) | ~9.7k | Yes; the index is consensus state since U-21 |
| Policy M1–M8, mining N1–N4 | `src/policy/*`, `src/miner.cpp`, `src/yellowback/policy.*` | ~1.5k | Yes (N5 is C++-only) |
| RPC: 5 vault read, 25 `yed_*` read, 2 node-state (`yed_setquote`, `yed_addattestation`), 5 stock deltas | `src/rpc/{vault,yellowback}.cpp` | ~3–4k of 7.7k | **Yes** (R1–R4) |
| RPC: 22 `set_*`/`vault_*` act, 25 `yed_*` wallet, 3+ PQ wallet | `src/rpc/{vault,yellowbackwallet}.cpp` | ~4k | **No** (sidecar, K-3) |
| Wallet: PQ sign, keystore, builders, coin selection, carriers, sign-once guards | `src/crypto/pq/sign*`, `src/wallet/*`, `src/yellowback/{txbuilder,coinselect,wallet}.*` | ~15k | No |

**Dependency order** (lane C §5, adopted as the wave order):
L0 network → L1 upgrade plumbing → L2 script → L3 primitive → L4 YED module → L5 policy →
L6 mining → L7 read RPCs → L8 tooling. Inside L4:
`math.h` → `params` → `payload/script/address/tag` → `attest/bundle` → `view/state` → `index` →
module registration. **The module is not registered until `yellowback_golden.json` replays.**
Until then the primitive treats `YED\0` as inert, which is safe only on regtest.

**Clients** (lane C §4, lane E §3.4). Can run against kogany directly:
- lightwalletd-dd (allow-lists of 19 `yed_*` read and 4 vault methods, `rpcversion` 8 exactly,
  `lightwalletd-dd/common/yellowback.go:47-90`);
- YEW (via lightwalletd);
- chain-viz (RPC; ZMQ per K-17);
- yolo (stock mining RPCs; the coinbase tag must be in `coinbasetxn`);
- x402's verifier;
- ycash-infra.

Cannot: YecWallet, Hawkeye, attestor `attest` mode, x402's `rpcWalletSigner`.

### 1.7 Verification assets (lane E)

- **Nine byte-identical vector files** are pinned by `ycash6/qa/yellowback-cross-line.manifest:11-19`:
  `vault_vectors.json`, `pq_vectors.json`, `pq_acvp_slhdsa.json`, `pq_falcon_kat.json`,
  `pq_wallet_vectors.json`, `yellowback_golden.json` (462 blocks), `yellowback_pq_vectors.json`,
  `yellowback_attest_vectors.json` and `yellowback_math_cases.json` (67 cases). The Python model is
  `qa/rpc-tests/test_framework/yellowback_model.py`. The runtime three-value cross-line driver is
  `ycash6/qa/yellowback-rc-crossline.py`.
- **Regtest compatibility.** Zakura's regtest and Ycash's share genesis `029f11d8…e327` and magic
  `aae83f5f` (`crates/zakura-chain/src/parameters/network/testnet.rs:51-52`, `constants.rs:47`;
  `ref/ycash6/src/chainparams.cpp:726-739`), and both use Equihash (48,5)
  (`work/equihash.rs:50-53`; `ycash6/src/chainparams.cpp:1100-1114`).
- **But Zakura's regtest waives PoW**, through `.with_disable_pow(true)` (`testnet.rs:1533`,
  verified), with no switch to turn it back on. It has no (48,5) or (192,7) solver: the internal
  miner is `tromp::solve_200_9` only (`equihash.rs:231`). Its `generate` emits all-zero solutions
  that ycashd rejects (`methods.rs:4259-4264`). In mixed regtest, therefore, the C++ nodes mine and
  kogany follows. Blocks kogany produces are solved by the Python (48,5) solver
  (`yellowback_util.py:22,1389`). Real (192,7) is proven only by unit vectors and by mainnet and
  testnet sync.

---

## 2. The minimalism design

### 2.1 Placement

```
Genesis < BeforeOverwinter < Overwinter < Sapling < Ycash < Blossom < Heartwood < Canopy
        < Vault < Nu5 < Nu6 < Nu6_1 < Nu6_2 < Nu6_3 < Nu7 [< ZFuture]
```

- **`Ycash`** (`0x374d694f`) goes between Sapling and Blossom, the position librustzcash6 gives
  it (`ref/librustzcash6` `02d42df5`). **`Vault`** (`0x6d5b7a31`) goes between Canopy and Nu5,
  in kogany and in the `zakura-protocol` fork's `UPGRADES_IN_ORDER`. That is unlike librustzcash6,
  which puts Vault after Nu6_2 (`librustzcash6/components/zcash_protocol/src/consensus.rs:691-704`).
- Every exhaustive match gives Vault the **Canopy** behaviour unless a later wave says otherwise.
  That means 75 s spacing, window 17, history leaf V1/`PreOrchard` (matching ycash6's item-20
  dispatcher), `ChainHistoryRoot`, v4 supported, v5 not supported, and P2P minimum 270200 on
  Ycash. The `_ =>` arms are audited by hand (§1.2).
- **This order diverges from the C++ index order** (ycash-dd: Vault after NU5; ycash6 and
  librustzcash6: after NU6.2). The divergence has **no consensus effect** while U-26 forbids
  scheduling Vault with any of NU5..NU6.2. It is recorded as invariant M24-3, and K-6 makes
  realignment a precondition of ever relaxing U-26.

### 2.2 The `is_vault_active` rule

All vault, set and YED rules gate on one predicate:

> `Network::is_vault_active(height)` ⇔ `Vault` is **present** in `activation_list()` and
> `height ≥` its key.

**Never** `current(..) >= Vault`, and never `Vault.activation_height(..)`. On Zcash Mainnet both
would read Vault as active from NU5's height, through the fallback (§1.2). On a future Ycash
network that schedules NU5, `current()` stops being Vault, but the vault rules must stay on. The
guards:
- a unit test that walks Zcash Mainnet and Testnet heights across NU5..NU7 and asserts the
  predicate is false;
- a CI grep (`kogany-yellowback.yml` audit leg (e)) that rejects `>= NetworkUpgrade::Vault`,
  `Vault.activation_height` and `< NetworkUpgrade::Vault` outside the predicate's own module;
- **builder refusals mirroring U-26** (`ycash6/src/init.cpp:1541-1565`): Vault set together with
  any of Nu5..Nu7 (or a later tail variant), or Sapling unset or above Vault, is a
  `ParametersBuilderError`. The accept/refuse table equals `ycash6/src/test/testnet_params_tests.cpp:193`'s.
  This also guarantees Vault can never be collapsed away by a later upgrade at the same height
  (§1.2, `testnet.rs:924-929`). Vault at Canopy's height stays legal and wins the collapse.

**The `Ycash` upgrade is different on purpose.** Ycash-era rules (the Equihash switch, YDF, the
Ycash branch IDs) live only in code compiled under the `ycash` profile (K-5), where every network
is a Ycash network. There, an ordinal `current >= Ycash` is safe, and it **must** be ordinal. The
mixed-regtest harness activates Overwinter through Canopy all at height 1, the map keeps only
Canopy at 1, and an explicit-membership test for `Ycash` would read false (M24-6). Vault is never
scheduled at a shared height with a later variant (the builder refuses it), so explicit membership
is safe for Vault.

### 2.3 Runtime gating, compile-time identity (K-5)

| Build | Enum variants | Branch-ID table | Networks | What runs in CI |
|---|---|---|---|---|
| feature **off** (upstream-shaped) | all of Zakura's, plus `Ycash` and `Vault` with no heights | Zcash IDs, plus inert rows `374d694f` and `6d5b7a31` | Zcash Mainnet, Testnet, Regtest exactly as upstream | upstream unit, e2e and NU5–NU7 suites (the dormancy oracle); `is_vault_active` false everywhere |
| feature **`ycash`** | same | Ycash IDs (Blossom `8e471bd6`, Heartwood `66314da3`, Canopy `19bd2d2f`, NU5 `f919a198` reserved), `6d5b7a31` | Ycash mainnet, fast/slow testnet (K-10), Ycash regtest | every kogany gate |

Why this split:
- **One enum shape in both builds**, so the exhaustive matches compile identically and no `cfg`
  arms are needed (lane D's objection to a cargo feature for Vault, O6).
- **Vault is runtime-gated by its height.** Zakura's 641 `Mainnet` sites are swapped by the
  compile-time profile rather than threaded through a runtime variant (lane B's T2).
- **Feature unification is a known hazard.** A Zcash-built crate in the same binary would silently
  become Ycash. It is acceptable for a node binary, and the CI matrix builds both ways (lane B O2).

### 2.4 Turning Zcash's later upgrades on later

None of these is free. The design keeps each one *reachable* without reordering (lane D §5).

| Future step on Ycash | Zakura side | Vault side |
|---|---|---|
| **NU5** (Orchard, v5/ZIP-244) | schedule `Nu5` above Vault with Ycash ID `f919a198` (K-7) | **relax U-26**, which first requires K-6 (C++ `CurrentEpoch` realignment on both lines and librustzcash6). Then either vault templates and opcodes still require a v4 spender while v5 is valid generally, or a ZIP-244 message is defined for `OP_CHECKSETSIG`/`OP_CHECKPQSIG`. The history tree resets V1→V2 at the boundary (Zakura resets per upgrade; ycash6's dispatcher is keyed by branch ID). All three nodes, both Rust forks, and the YEW, x402 and Hawkeye signers change. |
| NU6, NU6.1 | parameters only; Ycash takes the NU6 coinbase-equality rule with empty funding streams | none |
| NU6.2, NU6.3 (Ironwood, v6) | parameters | the NU5 question again, for v6 |
| **NU7** | ZIP 2003 bans v4; 25 s blocks; ZIP-218 limits | **hard boundary.** A v5/v6 vault signing message must already exist and be in use. Every block-count constant (CLAIM_DELAY, CANCEL_QUIET, set maturity, …) shrinks 3× in wall-clock time, so the constants are recalibrated through `yb-calibration`. |
| **Tachyon** | no variant at the pin (named only in `README.md:21,30`, `docs/design/dogwood.md:47,203`); assume it is appended after Nu7 and carries NU7's rules | as NU7: **Tachyon ⇒ NU7 ⇒ 25 s blocks + v4 ban ⇒ a new vault signing message and recalibrated constants**, plus whatever transaction format Tachyon defines |

### 2.5 The invariant

> **At every wave, upstream Zakura's own tests, including every NU5, NU6.x, NU7 and Ironwood test,
> pass unchanged on kogany in the feature-off build. An edited upstream test is listed in the PR
> body with its reason. A deleted one fails the gate.** The frozen-file report
> (`qa/kogany-frozen-files.txt`: Orchard, Ironwood, NU5–NU7 and Tachyon paths) shows zero delta
> or a recorded finding.

---

## 3. Waves and chunks

Conventions:
- Each chunk is sized for **one agent in one worktree** (`wt/<chunk>`, branch `up/<chunk>`).
- **C** marks a consensus chunk: it changes block or transaction validity, a branch ID, a sighash,
  script evaluation, or consensus state. It goes through the review gate (AGENTS rule 2): two
  reviewers independent of the author, with the four-part check (rule 4) and the in-tier rung in
  the PR body.
- Sizes are hand-written production lines / test lines / agent-days.
- "Fork" means the common fork (K-2).
- A wave's exit gate is run from a clean worktree whose HEAD equals the integration tip and which
  has been rebuilt first.

### W0 — scaffolding (no consensus; ~2 agent-days)

Entry: K-2, K-5, K-15 decided.

| Chunk | Scope | Exit gate | Size | Needs |
|---|---|---|---|---|
| W0-a `ws-amend` | workspace: `repos.yaml` entry for the common fork (`-legacy` at its base); AGENTS.md layout and rule 2 for kogany and the fork; the shared-defect rule (K-19); `docs/mapping.md` §24 skeleton pasted from §10 | `make status` clean, with both new repos on `upgrade/vault` | docs | K-2, K-19 |
| W0-b `fork-verify` | create the common fork; reproduce `zakura-protocol`/`-primitives`/`-address`/`-transparent`/`-equihash` 5.0.0-rc.2 and `zakura-zcash-script` 0.0.1 from one fork commit (§1.4: `bdbca121` vs `ca4c341e`); `[patch.crates-io]` in kogany pointing at the fork with **no source change** | `cargo package` contents of each crate equal the crates.io tarball (file-by-file diff); kogany builds and `tests-unit` passes with the patch in place | 0 / script / 1 | K-2 |
| W0-c `ci` | trimmed upstream workflows (K-15); `semgrep`, `codeql`, `secops`, `code-scanning` from `ycash6/SECURITY-CI.md`; `kogany-yellowback.yml` with audit legs (a) consensus-diff and (b) frozen-file report-only, (e) naming/attribution greps blocking; build matrix feature off and on; dependabot security-only | upstream `lint` and `tests-unit` green on kogany unchanged; security workflows green; consensus-diff report empty | YAML / — / 1 | K-15 |
| W0-d `baseline` | tag `kogany-baseline` = the commit W0-c lands on; `qa/kogany-frozen-files.txt`; the consensus path set: `crates/zakura-consensus/`, `crates/zakura-script/`, `crates/zakura-chain/src/{transaction,block,parameters,work,transparent,amount}`, `crates/zakura-state/src/service/{check,finalized_state,non_finalized_state}`, `crates/zakura-header-chain/src/validation/`, the `Cargo.lock` lines of the forked crates | the audit leg reads both files | lists / — / ½ | — |

**W0 exit gate:**
- upstream `tests-unit` + `lint` green on kogany at `kogany-baseline`, with the fork patched in;
- security CI green;
- the consensus-diff and frozen-file reports empty.

### W1 — Ycash on Zakura (lane B's Y0–Y8; ~13–19 agent-days, plus sync wall-clock time)

Entry: W0 green; K-1, K-9, K-10, K-11, K-12 decided.

| Chunk | Scope | Entry | Exit gate | Size | Needs | C |
|---|---|---|---|---|---|---|
| W1-Y0 `fork-ycash` | fork, feature `ycash`: `NetworkUpgrade`/`BranchId::Ycash` (variant unconditional, values gated, §2.3), Ycash ID table, constants and HRPs, `ZIP212_GRACE_PERIOD` 3, Ycash epoch v4-only | W0-b | fork tests pass with the feature on and off; branch-ID round trip equals `ref/ycash6/src/consensus/upgrades.cpp:23-80` | 250–350 / 300 / 2 | K-2, K-5 | **C** |
| W1-Y1 `profile` | kogany `ycash` profile: `NetworkUpgrade::Ycash`, table, mainnet and testnet heights (K-10), ports, seeds, magic, names; Zcash-only paths (`network.rs:22-32,352-378`, funding streams, lockbox) safe when the height is `None` | Y0 | `ConsensusBranchId::current` for every height band of lane B §3 equals ycash6 `getblockchaininfo`; feature-off build still passes upstream | 400–700 / 500 / 2–3 | K-1, K-5, K-10 | **C** |
| W1-Y2 `equihash` | `Solution` 400-byte variant; `check`/`validate_shape` bound to network **and** height, never to length; header-chain policy (`header-chain/.../pow_policy.rs:69-74`) | Y1 | real Ycash headers at 569,999 and 570,000 accept; wrong-size solutions on either side reject (mirror `work/tests/vectors.rs:200-240`); fuzz on the solution length | 300–500 / 400 / 2 | — | **C** |
| W1-Y3 `ydf` | `ydf_reward_is_valid` in `subsidy_is_valid`; `ydf_address(height)`; mainnet, testnet and regtest lists; funding streams and lockbox empty | Y1 | coinbase golden vectors from ycash6 at 570,000; 570,000 + 17,917·k; 1,100,006; 2,274,999; 2,275,000; halving at 849,999 and 850,000 | 250–400 / 400 / 1½ | — | **C** |
| W1-Y4 `checkpoints` | Ycash mainnet list regenerated with `zakura-checkpoints` from a synced ycash6 (stopping below the Vault epoch, M24-14); testnet-profile lists; frontier grid and VCT off (K-12) | Y1–Y3 | checkpoint sync genesis → 1,100,005 | 150 + ~7k generated / — / 1½ | K-9, K-12 | **C** (data) |
| W1-Y5 `p2p` | version table (270013 floor, 270200 at Vault), user agent, MSG_WTX unadvertised, v2 overlay off (K-11), seeds | Y1 | peers with ycash6 and ycashd 4.5.0 on regtest and mainnet; no Zcash peer retained | 200–400 / 200 / 1½ | K-11 | — |
| W1-Y6 `rpc-ycash` | addresses in RPC and config (`s1`/`sm`/`ys`/`yc`); `getblocktemplate` YDF coinbase; `getblockchaininfo` (upgrades keyed by branch ID, as `vault_harness.py:134-136` asserts), `getblocksubsidy`, `validateaddress` | Y1, Y3 | RPC answers equal ycash6 field by field for the lightwalletd-dd and yolo call sets (lane B §1 row 19) | 400–700 / 400 / 2 | — | — |
| W1-Y7 `regtest-harness` | Ycash regtest parity (Ycash epoch at 1, `vault` height configurable, (48,5)); **mixed-line harness skeleton**: `KOGANY_BIN` in `YellowbackTestFramework`, the ycashd-argument → `zakurad.toml` map, `sync_all` tip assertion | Y1, Y5 | a ycash6 regtest script runs with one kogany follower in sync to the end; kogany ⇄ ycash6 P2P on regtest | 150–300 + harness ~400 / — / 2 | K-18 | — |
| W1-Y8 `sync-gate` | nextest profile `ycash-sync`: full mainnet and testnet sync beside ycash6, block by block (hash, value pools, ZIP-221 history root from Heartwood 1,100,003, `z_gettreestate` at sampled heights) | Y0–Y7 | byte-identical answers, zero rejected blocks, mainnet and testnet | harness / — / 1 + wall-clock | — | — |

**W1 exit gate (lane E):**
- Ycash block vectors parse and validate, including the negative solution-size cases;
- full mainnet and testnet sync, with every checkpoint and the tip equal to ycash6's;
- kogany ⇄ ycash6 P2P on regtest;
- the feature-off upstream suite green (dormancy).

Then tag **`kogany-ycash-baseline`**: the stock comparison binary for every later wave, as
`ycash6-stock` was.

### W2 — the Vault epoch (lane C L1, C1–C7; ~3–4 agent-days)

Entry: W1 green; K-1, K-5 decided; K-6, K-7 recorded.

| Chunk | Scope | Exit gate | Size | C |
|---|---|---|---|---|
| W2-a `fork-vault` | fork: `NetworkUpgrade::Vault`/`BranchId::Vault` **before `Nu5`** in `UPGRADES_IN_ORDER`, `has_orchard() = false`, V5 invalid under Vault (librustzcash6 `4867cf85`, `eeb7740d` by meaning) | fork tests on and off; `try_from(0x6d5b7a31)` round trip | 100 / 100 / 1 | **C** |
| W2-b `vault-epoch` | kogany: enum and `NETWORK_UPGRADES` insert; `(Vault, 0x6d5b7a31)` row; `vault: Option<u32>` through `ConfiguredActivationHeights`/`for_regtest` (default `None`)/builder; one arm per exhaustive match (Canopy behaviour); `_ =>` audit with one test per arm; `is_vault_active` + grep guard; U-26 builder refusals; P2P 270200 from Vault | **Zcash NU5–NU7 tests unchanged and green**; `is_vault_active` false on every Zcash network at every boundary; builder accept/refuse table equals ycash6's; v5 rejected after Vault on Ycash params | 150–250 / 300 / 1½ | **C** |
| W2-c `vectors-pin` | `testdata/yellowback/` byte-identical copies of the nine vector files plus a `PIN` of SHA-256 per C++ path; `qa/yellowback-cross-line.py --this-line kogany` path map; replay `vault_vectors.spends[].sighash` through the native v4 sighash; the previous-epoch walk-back (C2) mapped to Zakura's mempool upgrade grace (`zakurad/src/components/mempool.rs:191`) | sighash replay equal; audit leg (c) blocking from here | 100 / 300 / 1 | **C** (sighash) |
| W2-d `vault-boundary` | mixed harness: `vault_activation_restart` and an activation-boundary script comparing branch ID, `getblockchaininfo.upgrades` and `hashBlockCommitments` at H_V−1, H_V, H_V+1 (the history tree resets at H_V, `history_tree.rs:335-342`) | mixed run green; vault-params leg (d): kogany's Vault heights equal ycash6's via a Rust extractor for `qa/yellowback-vault-params.py` | 0 / 200 / ½ | — |

**W2 exit gate (lane E):**
- `vault_vectors.spends[].sighash` replays;
- the mixed `vault_activation_restart` run and the boundary script pass;
- the Zcash NU5–NU7 tests are unchanged and green;
- kogany rejects v5 after Vault on Ycash parameters.

Upstream precedent for size: `51d3d8839`, 27 files, +124/−37.

### W3 — script and post-quantum verification (lane C L2; ~7–10 agent-days)

Entry: W2 green; K-4, K-8 decided.

| Chunk | Scope | Exit gate | Size | C |
|---|---|---|---|---|
| W3-a `interp` | fork `zcash_script`: `OP_CHECKSEQUENCEVERIFY` 0xb2 under flag bit 10; `OP_CHECKSETSIG` 0xc0 / `OP_CHECKSETDORMANT` 0xc1 under bit 11 (at most one per evaluation, not cached); `OP_CHECKPQSIG` 0xc2 under bit 12 for Falcon (SLH-DSA unflagged), 520-byte chunked pushes; checker trait extended (sequence, set threshold, `CheckSetSigs`, `IsSetReleased`, PQ verify), with defaults that fail closed; sigop counting (20 per `OP_CHECKPQSIG`); **never 0xbb–0xbf** | the fork's own tests plus the `vault_vectors` and `pq_script` script cases against a mock checker; upstream `test_vectors.rs` (17k lines) unchanged and green | 500–800 / 800 / 2½ | **C** |
| W3-b `pq-verify` | new crate `kogany-pq`: the C++ lines' verify-only C (PQClean Falcon-512 padded, slhdsa-c SHA2-128s) vendored with local patches through `cc`, SHA256SUMS-pinned; `KeyHash = SHA256(scheme‖pk)` | `pq_vectors`, `pq_acvp_slhdsa`, `pq_falcon_kat` replays, debug **and** release; malformed-encoding cases | 300 glue + ~6k vendored / 400 / 1½ | **C** |
| W3-c `script-plumb` | `zakura-script`/`zakura-consensus`: `script::Request` carries `(network, height)` and an `Arc<SetSnapshot>` (mock until W4); height-dependent flags replace `lib.rs:170`'s constant, **independent of transaction version**; the Ycash checker; secp256k1 `recovery` feature for 65-byte set signatures | `vault_vectors.ownerSpends[]` through the real verifier with a mock snapshot; Zcash script vectors unchanged | 300–500 / 500 / 1½ | **C** |
| W3-d `bip68` | BIP68 relative locks (height only; bit 22 → `bad-txns-vault-timelock`) in the transaction verifier (mempool, next height) and contextual validation (block), from `Utxo.height` | unit cases from `ycash6/src/test` sequence-lock tests; reorg case | 200–300 / 300 / 1 | **C** |
| W3-e `pqpkh-fuzz` | `TX_PQPKH` in `standard_script_kind` (`check.rs:714`) and destinations; `qa/fuzz/vault` target replaying the C++ corpora against **verdicts recorded once from ycash6** | fuzz verdict replay equal; listed in `qa/suite.toml` | 200 / 300 / 1 | — |

**W3 exit gate:**
- `vault_vectors.ownerSpends`, `pq_vectors`, ACVP and KAT replays pass in debug and release;
- the fuzz verdict-corpus replay passes;
- the dormancy suite is green.

### W4 — the vault primitive (lane C L3; ~11–16 agent-days)

Entry: W3 green; K-13, K-14 decided. This is the largest structural risk (M24-11..M24-15).

| Chunk | Scope | Exit gate | Size | C |
|---|---|---|---|---|
| W4-a `templates-acts` | new crate `kogany-vault`: templates V/I/B parse/build, selector = last push 1..4; acts (`YV` OP_RETURN, ≤16 recoverable signatures over `SHA256d("YcashSetAct"‖P‖vin[0].prevout)`) | every `vault_vectors` template and act case | 1.0–1.3k / 1k / 2 | **C** |
| W4-b `set-state` | set state machine (`ApplyTx`/`ApplyBlock`: members, seats, maturity, liveness/dormancy/release, rate limit, bond and template-output indexes, S-0, V-*, I-*); the canonical `statehash` preimage encoder **separate from storage** (`ycash6/src/vault/node.cpp:505`, `SERIALISATION.md`); module table with `YED\0` inert; `BTreeMap` only | unit cases re-expressed from `vault_state_tests.cpp` (2,442 lines: the case list); `statehash` of the vector chains equals the C++ value | 1.5–2k / 2.5k / 3–4 | **C** |
| W4-c `vault-storage` | column families `vault_set`, `vault_member`, `vault_bond`, `vault_template_out`, …; DB format bump with migration (precedent `add_ironwood_tree.rs`); the transition **computed in `prepare_block_batch`** for checkpoint and finalized commits alike, total and never failing; `Chain` field + `UpdateWith<VaultDelta>`; `rollback` refuses past Vault (K-14) | restart and reorg Rust tests; a checkpoint-committed range produces the same state as the semantically verified range | 600–900 / 800 / 2–3 | **C** |
| W4-d `snapshot-hook` | `zs::ReadRequest::VaultSnapshot { parent_hash }` (fork-aware) plus an awaiting variant modelled on `AwaitBlockInfo`; contextual `check::vault` in `validate_and_commit` for sequential acts and template rules; S3 wired to the real snapshot; ejection effect (U-25) inside the delta | mixed: `vault_primitive`, `vault_slashing`, `vault_undo_prune`, `vault_pq_reorg`, `vault_dos` with `statehash` equal at every sync | 500–800 / 600 / 2–3 | **C** |
| W4-e `harness-state` | harness sync-point asserts of `vault_getinfo.statehash` (minimal read RPC, ahead of W7) and verdict-class equality on `assert_rejected` paths (reject-code map table); kogany-only nextest profile `kogany-regtest` (activation, raw vault spend from vector keys, reorg/undo, restart) | the profile is green and serves as the PR gate | 0 / 800 / 1½ | — |

**W4 exit gate (lane E):**
- the mixed vault scripts pass with `statehash` equal to ycash6 at every sync;
- the kogany-only reorg and restart tests pass;
- memory for per-fork deltas is measured at the 1,000-block window (K-13);
- the dormancy suite is green.

### W5 — the YED rule module (lane C L4; ~17–25 agent-days)

Entry: W4 green. Order inside the wave is strict (§1.6). The module is registered only in W5-f.

| Chunk | Scope | Exit gate | Size | C |
|---|---|---|---|---|
| W5-a `math-params` | new crate `kogany-yellowback`: fixed-point arithmetic (FEE-1′ in 256-bit, ratios, HALT-2 denominator) with `checked_*`/`i128` only; parameters (in-term tiers 300/400/500 %, θ 125 %, fees, `maxMint`, supply cap, testnet-fast scaling) **generated from or checked against the C++ `params.cpp`**, never hand-copied | `yellowback_math_cases.json` (67 cases) in debug **and** release; vault-params leg (d) extended to module constants | 0.9–1.2k / 1k / 3 | **C** |
| W5-b `codecs` | MINT payload (v4, PQ owner), YED token/carrier scripts, address encodings (`yb/yt/yr`, PQ 53-character forms), the coinbase tag `YED!` (byte scan, 36 bytes) | payload, script and tag cases from the C++ tests; address round-trips | 1.2–1.5k / 1k / 2–3 | **C** |
| W5-c `attest` | 74-byte attestations, bundles, the attestor registry mirrored from `attestorSetId`'s set acts, EQV-1 by key trial | `yellowback_attest_vectors.json` | 600–800 / 600 / 2 | **C** |
| W5-d1 `state-mint` | state machine part 1: MINT, transfer, claim → intents, cancel CAN-1/2/3 | `yellowback_state_tests.cpp` cases for these (the 5,712-line file is the case list) | 1.8–2.2k / 2k / 3–4 | **C** |
| W5-d2 `state-release` | part 2: release, redeem with early fee, HALT-1/2/3, supply cap, ejection, `EvaluateBlock`, `MempoolCheckReason` | remaining state cases; `yellowback_pq_vectors.json` matcher and chain | 1.8–2.2k / 2k / 3–4 | **C** |
| W5-e `yed-index` | the index as consensus state (U-21): column families, `UpdateWith` undo, computed in the shared write path, "cannot evaluate ⇒ stop the node", `yed_getstatehash` preimage, published fee price | reorg and restart tests; state hash equal to the C++ value on the vector chain | 800–1.1k / 1k / 2 | **C** |
| W5-f `module-register` | register `YED\0` with the primitive (verdict at DoS 100 where Vault is active and the attestor set is known); replay `yellowback_golden.json` (462 blocks: `stateHash`, `totals`) | golden replay equal; mixed `yellowback_lifecycle`, `_activation_reorg`, `_reorg_restart`, `_claim`, `_interm`, `_fees*` with `yed_getstatehash` equal to ycash6 **and** to `yellowback_model.py`'s `state_hash()` | 200 / 600 / 1½ | **C** |

**W5 exit gate:**
- all four YED vector files replay;
- the golden chain's state hash matches;
- the mixed YED scripts pass with three-way state-hash equality (kogany, ycash6, model);
- the dormancy suite is green.

### W6 — relay policy and mempool (lane C L5, M1–M8; ~4–6 agent-days)

| Chunk | Scope | Exit gate | Size | C |
|---|---|---|---|---|
| W6-a `standardness` | `YV` OP_RETURN up to 1,200 bytes **from the Vault height** (carrier limit made height-dependent); template scriptSig standardness (CLEANSTACK/selector, 01/V-4); PQ dust, PQ fee rate, PQ max fee; tx-size limits for ~8 KB SLH-DSA spends | `vault_policy_tests` cases | 300–500 / 400 / 1½ | — |
| W6-b `fee-policy` | dollar-per-KB network fee from the attested price (`AttestedFeePrice`, trusted unless HALT-1/3); ZIP-317 floor for PQ-input transactions; YED mempool limits (`-yellowbackfee`, `-yellowbackmintlag` as config) | mixed `yellowback_fees*`, `yellowback_mempool_limits` | 300–500 / 400 / 1½ | — |
| W6-c `tip-recheck` | on `Grow`: re-verify template-input transactions via `retry_after_tip_reset` (`mempool.rs:907`) or evict; YED `MempoolCheck` sweep; BIP68 eviction on reorg; new `TransactionError` variants scored 0 for state-dependent failures, 10 for byte-level act failures | mixed `vault_policy`, `vault_refee`; mempool-set equality at every sync | 300–500 / 400 / 1½–2 | — |

**W6 exit gate:** mixed mempool-set equality and verdict-class equality on every rejected
transaction.

### W7 — read RPCs (lane C L7, R1–R4; ~5–8 agent-days)

Entry: K-3, K-17 decided.

| Chunk | Scope | Exit gate | Size |
|---|---|---|---|
| W7-a `rpc-dispatch` | **prototype first**: a second `rpc_trait!` trait in a new crate `kogany-rpc`, dispatched beside `RpcServer` (A §8, not prototyped); `vault_getinfo` (`statehash`, `attestorsetid`, `moduleactive`), `set_list`, `set_getinfo`, `vault_list` (no `mine`), `vault_decodescript` (no ismine) | `qa/vault-rpc-contract.py` read subset | 800–1.2k / 400 / 2 |
| W7-b `rpc-yed` | the 25 `yed_*` read RPCs and the 2 node-state ones (`yed_setquote` miner quote, `yed_addattestation` pool, RPC-auth); `rpcversion` 8 | `yellowback_rpc_contract.py` read subset; lightwalletd-dd probe semantics (−32601 = no Yellowback) | 1.5–2k / 800 / 3 |
| W7-c `rpc-stock` | `sendrawtransaction` `allowyedburn` (H7), `validateaddress` P2PQPKH, `getblockchaininfo.testnetprofile` | contract cases | 200–300 / 200 / 1 |
| W7-d `rpc-artifacts` | `xtask check-rpc-artifacts` (OpenRPC ⊇ contract read methods; wallet methods listed as sidecar-served); `make spec` gains `EXTRACT_SPEC_KOGANY_DIR`; chain-viz (polling, K-17) and lightwalletd-dd legs against kogany, report-only | `make spec-check`; both client legs run | 100 / 200 / 1–2 |

**W7 exit gate:** the contracts' read shapes match against kogany, `check-rpc-artifacts` and
`spec-check` pass, and the client legs run (report-only).

### W8 — mining (lane C L6, N1–N4; ~3–5 agent-days)

Entry: K-16 decided.

| Chunk | Scope | Exit gate | Size | C |
|---|---|---|---|---|
| W8-a `tpl-filter` | sequential act and template filter in ZIP-317 selection (`zip317.rs:83`, the TPL-1 analogue), then the YED `FilterTemplate`; templates still verified through `Request::Prepare` | a template never carries two conflicting acts; template parity with ycash6 on a scripted mempool | 300–500 / 400 / 1½ | — |
| W8-b `coinbase-tag` | the coinbase tag from the node-local quote (`yed_setquote`) in the Rust coinbase builder; `coinbasetxn`; `getblocktemplate` refuses while the YED state is unhealthy; sigops field counts 20 per `OP_CHECKPQSIG` | mixed `yellowback_mining`; tag bytes equal ycash6's for the same quote | 200–400 / 300 / 1½ | — (feeds payee eligibility, M24-19) |
| W8-c `kogany-mines` | kogany templates solved by the Python (48,5) solver and submitted; yolo `ci.yml` against kogany | ycash6 accepts kogany-produced blocks; yolo leg green | 0 / 200 / 1 | — |

**W8 exit gate:** as in the table. The Equihash gap (K-16) is recorded in the review document.

### W9 — wallet via sidecar, full matrix, demonstration (~6–10 agent-days plus 7 days of nightlies)

| Chunk | Scope | Exit gate | Size |
|---|---|---|---|
| W9-a `sidecar` | a ycash6 `connect=<kogany>`, `listen=0` sidecar profile (plain `connect=`; whether any valargroup-style sidecar changes are needed is unverified, K-3); nightly job | the wallet-driven scripts run against kogany + sidecar; nightly green 7 days | 0 / 400 / 2 |
| W9-b `mixed-all` | the whole Yellowback functional suite (58 scripts) in mixed mode; `yellowback-rc-crossline.py --kogany-zakurad` with three-way agreement every 100 blocks on the devnet | suite green twice in a row; 5 rounds × 100 blocks, three-way | 0 / 300 / 2 |
| W9-c `client-legs` | `node_line: kogany` legs in lightwalletd-dd, chain-viz, yolo, x402 (verifier), YEW (via lightwalletd), ycash-infra (backend swap), with a ycash6 sidecar where needed | every leg green | client repos / 1–2 |
| W9-d `review-demo` | `kogany/doc/yellowback-review.md` (budget actuals, the hook table with every site's four-part check, the dormancy evidence); the §6 demonstration transcript; release-train entry prepared but not enabled (K-19) | §6 met | docs / 1–2 |

---

## 4. Diff budget and working rules

### 4.1 Budget per wave (estimates; actuals are measured against `kogany-baseline` by audit leg (a))

| Wave | New `kogany-*` crate production | Upstream-file edits (touch budget) | Common-fork edits | Tests | Frozen paths |
|---|---|---|---|---|---|
| W0 | 0 | CI/YAML only | 0 | — | 0 |
| W1 | ~0.3k | **2.2–3.7k** (identity is spread across `zakura-chain`, `-network`, `-consensus`, `-header-chain`, `-rpc`) | 250–350 | 3–5k + ~7k generated | 0 |
| W2 | 0 | 250–400 | ~100 | ~0.9k | 0 |
| W3 | ~0.5k (+6k vendored C) | 500–800 | 500–800 | ~2.3k | 0 |
| W4 | 3–4k | 600–900 (`zakura-state`, `zakura-consensus`) | 0 | ~5.5k | 0 |
| W5 | 7.3–9.2k | ≤ 150 (registration and the write-path call) | 0 | ~8k | 0 |
| W6 | 0.4–0.6k | 500–900 (mempool, policy) | 0 | ~1.2k | 0 |
| W7 | 2.6–3.5k | ≤ 150 (dispatcher wiring) | 0 | ~1.6k | 0 |
| W8 | 0.2k | 300–700 (template, coinbase) | 0 | ~0.9k | 0 |
| W9 | 0 | 0 | 0 | harness ~0.7k | 0 |
| **Total** | **~14.5–18.5k + 6k vendored** | **~4.8–7.7k** | **~0.9–1.3k** | **~25–30k + 7k** | **0** |

New crates plus upstream edits plus fork edits give the summary's ~20–27k hand-written production lines.
The budget is report-only (as on the C++ upgrade line). A wave that exceeds its touch budget by
more than 25 % stops for a findings row and a coordinator decision before it merges.

### 4.2 Working rules

1. **Where code goes.** New behaviour goes in new crates: `kogany-pq`, `kogany-vault`,
   `kogany-yellowback`, `kogany-rpc`. They use the `kogany-` prefix so `git grep` separates ours
   from upstream (naming rule 6: `yellowback` names the system, `yed` counts units). Edits to
   upstream files are hooks only, each listed in the wave's review table. The Ycash profile lives
   in `zakura-chain` under `cfg(feature = "ycash")`, because the network tables are there.
2. **Never tidy upstream code** (AGENTS rule 7 applies to every consensus path in §3 W0-d). A
   rename or refactor in an upstream file is a rebase cost and a review cost with no benefit.
3. **Four-part check for every consensus chunk** (rule 4), in the PR body:

   > *ycash6 does X in Y via M. Zakura's equivalent is Z, which lacks M. So the adaptation is W.
   > In-tier rung: …, and why a lower rung won't do.*

   The tier itself is decided (the network upgrade). The rung answers template < opcode <
   transaction field; per-vault < global state; primitive < module. A row already in §10 may be
   cited instead of repeated. Two reviewers independent of the author (rule 2 review gate). The
   consensus-diff artefact is attached.
4. **The three-way cross-line invariant** (every consensus wave from W2 on):
   - (i) kogany consumes the nine vector files **unmodified**, pinned by SHA-256 to the C++ files.
     Every schema key a C++ test asserts gets a Rust assertion, with a per-file "key → Rust test"
     checklist in `testdata/yellowback/CHECKLIST.md`.
   - (ii) At every sync point of every shared regtest script, `getbestblockhash`,
     `vault_getinfo.statehash` and `yed_getstatehash` are equal on ycash6, kogany and (for YED)
     `yellowback_model.py`.
   - (iii) Block and mempool verdicts agree by **class**: accept, reject-consensus at DoS 100,
     reject-state at DoS 0, reject-policy. Reject strings differ by design, so the code map is a
     table in the harness.
   - (iv) kogany never generates a vector. A vector change is one change set across ycash-dd,
     ycash6, librustzcash6 (when it touches Rust), the common fork (when it touches its crates)
     and a kogany PIN bump.
5. **Shared-defect rule** (K-19 amendment). A Yellowback rule change or shared defect is fixed on
   both C++ lines together, as today. From W2 on, kogany and the common fork land in the same
   change set when they already implement the affected layer. Otherwise they record it in §9 and
   pick it up when the layer lands.
6. **Rust determinism disciplines** (lane E §3.1), enforced by clippy configuration in the
   `kogany-vault` and `kogany-yellowback` crates and by audit greps:
   - no `HashMap`/`HashSet` (`disallowed-types`);
   - `clippy::arithmetic_side_effects`, `unwrap_used`, `expect_used`, `indexing_slicing` denied;
   - no `f32`/`f64`, `SystemTime`/`Instant`, `std::net`/`tokio::net`;
   - math and state tests also run under the release-like `ci-tests` profile (Zakura's release
     profile wraps on overflow, `ref/zakura/Cargo.toml:195-210,302-336`).
7. **Upstream sync ("rebase onto Zakura main").** kogany stays rebaseable onto Zakura main by
   *merging* upstream into `upgrade/vault`, never by rewriting published history.
   - **When:** at every wave boundary, and at least monthly. A Zakura release that bumps the
     `zakura-*` crates forces a sync of the common fork first (re-port of the ~250–1,300 fork lines).
   - **Who:** one agent per sync, chunk `sync-zakura-<date>`, in a worktree. The coordinator
     merges after review.
   - **What proves it:** on the merged tree, the feature-off upstream suite and the feature-on
     kogany gates of every completed wave are green; the consensus-diff report shows only kogany
     hunks; and a dry-run *rebase* of kogany's commits onto the new upstream tip, in a scratch
     worktree, is recorded as a conflict count (report-only, the rebase-ability measure).
   - **Re-pinning:** `ref/zakura` and `kogany-legacy` are re-pinned to the merged upstream commit
     by the deliberate rule-1 procedure. `repos.yaml`, AGENTS.md and the mapping §24 citations
     are updated in the same change.
8. **Crate-fork hygiene.**
   - The common fork has its own `-legacy` baseline (the W0-b base) and `upgrade/vault` branch,
     and is listed in `repos.yaml`.
   - kogany's root `Cargo.toml` `[patch.crates-io]` pins **every** forked crate to one exact
     `git` rev (never a branch).
   - Fork versions stay at upstream's version string with a build-metadata suffix (for example
     `5.0.0-rc.2+ycash.1`), so the lock file shows the fork.
   - Every fork change carries the four-part check if it is consensus.
   - The fork's CI builds and tests with the `ycash` feature on and off.
   - A bump of the fork rev in kogany is its own commit, with the fork's commit list in the
     message.
9. **No AI attribution** anywhere (rule 8). Commits are authored as the owner.

---

## 5. Verification and CI

**Upstream workflows (K-15).**
- **Kept, trimmed:**
  - `lint.yml`, without nightly unused-deps and without Slack;
  - `tests-unit.yml`, the build + 3-shard nextest, without graph publishing or Slack;
  - `zakura-e2e.yml`, pr-gate only, with the long modes weekly;
  - `docs-check.yml`;
  - `test-crates.yml`, weekly;
  - `header-fuzz.yml` and `rpc-fuzz.yml`, weekly.
- **Off (21):**
  - the DigitalOcean fleet and deploy jobs;
  - the release pipeline;
  - `ci-alerts`, `coverage` (Codecov), `benchmarks`, `legacy-pages`, the cranelift pair,
    `cross-platform`, `history-growth`, `test-docker`;
  - `zcashd-compat-regtest`, which downloads a Zcash zcashd and is replaced by the sidecar leg.

  Several of these need secrets or self-hosted runners the fork lacks. `mergify.yml`/`zbot.yml`
  are ignored. Dependabot runs security updates only. Jobs are enabled one at a time.
  **Scheduled jobs run only once kogany's GitHub default is `upgrade/vault`** (the ycash6 port's
  F-39(c)).

**Security CI.** `semgrep.yml`, `codeql.yml` (rust, actions, python), `secops.yml` (zizmor,
gitleaks, OSV over `Cargo.lock`, cargo-deny with `contrib/secops/deny-node.toml`; upstream's root
`deny.toml` stays) and `code-scanning.yml`, verbatim from `ycash6/SECURITY-CI.md`.

**`kogany-yellowback.yml` legs.**

| Leg | What | Blocking? | From |
|---|---|---|---|
| audit (a) consensus-diff | delta vs `kogany-baseline` over the W0-d path set + forked-crate lock lines; artefact for the two reviewers | report-only | W0 |
| audit (b) frozen-file | `qa/kogany-frozen-files.txt` (Orchard, Ironwood, NU5–NU7, Tachyon paths) | report-only (a non-zero is a §9 finding) | W0 |
| audit (c) cross-line identity | vector copies equal the ycash6 head (`qa/yellowback-cross-line.py --this-line kogany`) | **blocking** | W2 |
| audit (d) vault-params | heights and module constants equal ycash6's (Rust extractor) | **blocking** | W2 (heights), W5 (constants) |
| audit (e) greps | determinism (§4.2 rule 6), `is_vault_active` rule, naming (the upstream and retired names rule 6 excludes), attribution | **blocking** | W0 (naming), W2 (vault), W3 (determinism) |
| build matrix | feature off and `ycash` | **blocking** | W0 |
| upstream-dormancy | Zakura's NU5/NU6/NU7/Ironwood tests on Zcash params, feature off; an upstream test deleted fails | **blocking** | W0 |
| vectors | nextest `kogany-vectors`, debug and `ci-tests` | **blocking** | W2 |
| kogany-regtest | Rust regtest tests (activation, reorg, restart) | **blocking** | W4 |
| mixed-regtest | ycash6 `node-bin.tgz` at the matching branch + kogany; the §3 harness on a shard list, run with and without `KOGANY_BIN` | report-only until its wave's gate, then **blocking** for the scripts that wave named | W1 (skeleton), W2+ |
| sidecar | nightly: kogany + `connect=` ycash6 wallet scripts | report-only → blocking at W9 | W9 |
| sync | manual/weekly: full Ycash mainnet and testnet sync, checkpoints equal ycash6 | manual gate | W1 |

**The mixed-line harness (`KOGANY_BIN`).** `YellowbackTestFramework`
(`ycash6/qa/rpc-tests/test_framework/yellowback_util.py:515`) gains an opt-in `KOGANY_BIN`. It
starts k kogany followers (default 1) from a generated `zakurad.toml`:
- the Ycash epoch at height 1;
- Vault at `VAULT_ACTIVATION`;
- node 0's attestor-set and Falcon parameters;
- `addnode` to node 1.

`sync_all` (`:717`) and `mine` then assert equal tips, state hashes and `getrawmempool` sets.
Negative paths offer the rejected block or transaction to kogany and assert the same verdict
class. `split_network` uses `disconnectnode`, which Zakura lacks, so kogany stays on node 1's side
(recorded). No script changes.

**Equihash and regtest (K-16).**
- Mixed regtest: the C++ nodes mine and kogany follows, and its regtest checks the solution
  *shape* only. kogany-produced blocks go through the Python (48,5) solver.
- (192,7) is proven by unit vectors and the sync leg only.
- Recorded as M24-20.

**When the workspace tooling includes kogany.**
- `make spec`/`spec-check`: from W7, when kogany serves the RPCs (`EXTRACT_SPEC_KOGANY_DIR`).
- Release train (`scripts/release-train.py` `COMPONENTS`): only after K-19(a). Until then a train
  names it as `kogany: none`.
- Calibration (`yb-calibration`) is unchanged. It never reads a node, and kogany receives
  constants only through audit leg (d), so a constant can never drift on the third line without
  failing CI.

---

## 6. Success criteria (the demonstration that ends the plan)

On this machine, from `kogany` `upgrade/vault` at one commit, with the transcript attached to
`kogany/doc/yellowback-review.md`:

- [ ] **Ycash node.** kogany (feature `ycash`) syncs Ycash mainnet and the fast and slow testnets
  from genesis to tip with zero rejected blocks. Every checkpoint, the tip, value pools, ZIP-221
  roots and sampled tree states equal ycash6's.
- [ ] **Dormancy.** The feature-off build passes Zakura's upstream unit, e2e and NU5/NU6/NU7/Ironwood
  suites unchanged. The frozen-file report is zero. `is_vault_active` is false on every Zcash
  network at every boundary.
- [ ] **Oracle.** All nine vector files (eight consensus, plus `pq_wallet_vectors` marked
  N/A-without-wallet) replay byte for byte in debug and release. The golden chain's `stateHash`
  and `totals` match.
- [ ] **Equivalence.** All 58 Yellowback functional scripts pass in mixed mode (kogany followers,
  with the ycash6 sidecar for wallet scripts) twice in a row, with `statehash` and
  `yed_getstatehash` equal at every sync point and three-way equal to the Python model.
- [ ] **Devnet.** `yellowback-rc-crossline.py` with ycash-dd, ycash6 and kogany on one devnet:
  5 rounds × 100 blocks, three-way agreement on best block, vault state hash and YED state hash,
  across the Vault activation, a 2-block and a 10-block reorg, and a kogany restart.
- [ ] **Production.** Blocks built from kogany templates (Python-solved) are accepted by ycash6
  and carry the coinbase tag. yolo mines on kogany. A block ycash6 rejects is rejected by kogany
  with the same verdict class.
- [ ] **Clients.** lightwalletd-dd, chain-viz, yolo, the x402 verifier, YEW (via lightwalletd) and
  ycash-infra pass their `node_line: kogany` legs. The read-RPC contracts conform.
- [ ] **Review package.** Budget actuals, the hook table with four-part checks, the consensus-diff
  artefact with two reviewers per consensus PR, mapping §24 complete.
- [ ] **Owner decision K-19(a)** taken on whether kogany becomes a qualified release line.

---

## 7. Estimate

Agent-days. "Wall" means elapsed time that is not agent work.

| Wave | Agent-days | Uncertainty | Main driver |
|---|---|---|---|
| W0 | 2–3 | low | W0-b's two-commit question (§1.4) could add a day |
| W1 | 13–19 + wall (mainnet sync, days) | **medium-high** | identity spread over 641 `Mainnet` sites; header-chain Equihash height plumbing; YDF vectors |
| W2 | 3–4 | low | upstream precedent `51d3d8839` |
| W3 | 7–10 | medium | interpreter fork API; recoverable signatures; vendored C build on all CI targets |
| W4 | 11–16 | **high** | shared write path for checkpoint commits; fork-aware snapshot awaiting the parent (serialises post-Vault block verification; performance unknown) |
| W5 | 17–25 | **high** | the largest rewrite; arithmetic byte-exactness; index as consensus state |
| W6 | 4–6 | medium | mempool re-verification on `Grow` |
| W7 | 5–8 | medium | second RPC trait dispatcher not prototyped |
| W8 | 3–5 | low-medium | coinbase builder hook |
| W9 | 6–10 + wall (7 nightly days) | medium | sidecar behaviour unverified (K-3) |
| Rebase/sync chunks (~6 over the plan) | 3–6 | medium | upstream churn rate |
| **Total** | **~74–112 agent-days** (central ~90) | ±30 % | |

The summary's "~70–105" is the same figure without the sync chunks. **Calendar time** is set by
three things more than by agent count:
- W1 to W5 are serial (lane C's strict layering);
- each consensus chunk waits for two independent reviewers;
- there are two wall-clock gates (mainnet sync, seven days of nightlies).

With 2–4 parallel agents inside a wave, expect roughly **4–6 months** of elapsed time. This is
flagged as uncertain: the ycash6 port's speed (days) came from copying C++ verbatim, and nothing
here is copied.

---

## 8. Risks and open leads

| # | Risk or lead | Mitigation |
|---|---|---|
| R-1 | **Order-as-gate misuse:** someone writes `current >= Vault` or uses `Vault.activation_height` | §2.2 predicate, the grep leg, the Zcash-network test, the builder refusals |
| R-2 | **Arithmetic byte-exactness** in the YED module (overflow wraps in release; float or map-order leaks) | §4.2 rule 6; `math_cases` in release; three-way state-hash equality |
| R-3 | **Checkpointed or finalized blocks bypass the vault transition** | compute in `prepare_block_batch`; checkpoints never cover the Vault epoch until equality is proven (M24-13/14) |
| R-4 | **Pipeline serialisation:** post-Vault blocks must await the parent's committed set state before scripts run; verification throughput unknown | measure in W4; Zakura's NSM path already does this (`block.rs:503-530`) |
| R-5 | **Fork drift:** Zakura bumps `zakura-*` crates often; the two-commit origin of the published crates (§1.4) | §4.2 rules 7–8; W0-b reproducibility check; O5 upstream proposal |
| R-6 | **Wildcard `_ =>` arms** silently classify Vault | lane A's audit list in W2-b; one test per arm |
| R-7 | **Wallet-hosted roles** cannot run on kogany (attestor `attest` mode, Hawkeye, YecWallet, x402 `rpcWalletSigner`) | K-3: stated limitation; ycashd remains required for them |
| R-8 | **Same genesis and magic as Zcash** on Zakura's v2 overlay | K-11: v2 off; P2P versions exclude Zcash peers |
| R-9 | **Yolk v4.3.1**: `ref/ycash6/src/version.h:16,25,42,55` names a Zebra-based Ycash node on the live network ("agreed as the floor across ycashd and Yolk/Zebra"). Lane B's web search found no public source. If its source exists, it is the closest prior art for W1 (Zebra lineage with Ycash parameters: branch IDs, Equihash switch, YDF, P2P) and should become a `ref/` pin | owner (K-19) asks the Ycash developers before W1 starts; W1 does not wait for it |
| R-10 | **Unverified sidecar behaviour**: whether a plain `connect=` ycash6 suffices, or valargroup-style changes are needed (`docs/zcashd-compat.md:85-104`) | W9-a first; tests only, production hardening is a separate decision |
| R-11 | **Feature unification** turns a Zcash-built dependency into Ycash in one binary | both-ways build matrix; kogany ships one binary per profile |
| R-12 | **Reorg-window memory**: per-fork vault and YED deltas over 1,000 blocks | measure in W4 (K-13) |
| R-13 | **Upstream tests that enumerate all upgrades** may assume every variant has a height or a Zcash ID | found in W1/W2; any edit listed in the PR body (§2.5) |
| R-14 | **C++ lines cannot activate NU5 after Vault** as written (`CurrentEpoch`) | K-6 precondition; M24-3 |
| R-15 | **The NU7/Tachyon boundary** needs a new vault signing message and recalibrated constants | K-7 record in upgrade plan U-26 |

---

## 9. Findings log

Every surprise found while porting gets a row here **and** a mapping §24 row before it is fixed
(the ycash6 port's discipline).

| # | Wave/chunk | Finding | Resolution | Commit | Mapping row |
|---|---|---|---|---|---|
| | | | | | |

---

## 10. Mapping §24 rows to add — "kogany (Zakura) port"

Ready to paste as `docs/mapping.md` §24. The traps from all five surveys, deduplicated, in rule-4
form. Columns:
- **X/Y/M:** what Ycash does, where, and by which mechanism;
- **Z:** Zakura's equivalent, and what it lacks;
- **W:** the adaptation;
- **Rung:** which rung, and why not lower.

Citations are at the pins in the header (Zakura paths under `ref/zakura/`).

| # | Ycash does X in Y via M | Zakura's Z, lacking M | Adaptation W | Rung, and why not lower |
|---|---|---|---|---|
| M24-1 | Gates each upgrade by its own height, `NetworkUpgradeActive(h, idx)`; enum index carries no meaning, so Vault sits after NU6.2 (`ycash6/src/consensus/upgrades.cpp:130-139`, `params.h:43-56`) | `NetworkUpgrade` derives `Ord` and order **is** the gate: ~20 `>=`/`<` sites, `is_nu7_active` (`crates/zakura-chain/src/parameters/network_upgrade.rs:23-27,636-642`) | `Vault` between Canopy and Nu5; `Ycash` between Sapling and Blossom | enum-variant (data) rung; a parameter-only Vault misplaces the branch ID, and the C++ position inherits NU5–NU7 rules (consensus-dead) |
| M24-2 | Unset upgrade = `NO_ACTIVATION_HEIGHT`, simply inactive (`ycash6/src/consensus/upgrades.cpp:112-113`) | `activation_height` falls back to the next upgrade's height (`network_upgrade.rs:459-469`) | `is_vault_active` = Vault present in `activation_list()` and height ≥ its key; never `current >= Vault` or `Vault.activation_height`; CI grep + test | predicate in parameters; nothing lower |
| M24-3 | Vault's index is after NU5 (ycash-dd `src/consensus/params.h:41-44`), after NU6.2 (ycash6 `params.h:43-56`, librustzcash6 `consensus.rs:691-704`) | kogany and its fork put Vault before Nu5 | **Invariant:** the relative order has no consensus effect while U-26 forbids Vault with NU5..NU6.2; realigning the C++ lines is a precondition of relaxing U-26 (K-6) | record only; a realignment now would be a semantics-free consensus edit on two lines |
| M24-4 | Branch IDs per network via chainparams `NetworkUpgradeInfo` (`ycash6/src/consensus/upgrades.cpp:23-99`); Ycash's own Blossom/Heartwood/Canopy/NU5 IDs | One global const table, "the same for mainnet and testnet" (`network_upgrade.rs:249-274`) | Vault row unconditional; Ycash IDs as the `ycash`-profile table (compile time) | table rows; a runtime per-network table would touch 17 `branch_id()` callers |
| M24-5 | Rust branch-ID conversion patched in librustzcash6 (`02d42df5`, `4867cf85`) | `to_librustzcash` → `zakura-protocol` `BranchId::try_from` rejects Ycash IDs and `0x6d5b7a31` (`crates/zakura-chain/src/transaction.rs:1857-1878`; `zakura-protocol:src/consensus.rs:744-760`); reached from `SigHasher::new` (`transaction/sighash.rs:173-185`) and coinbase decryption | feature-gated fork of `zakura-core/common` (K-2) | dependency rung; a kogany-side shim cannot represent Ycash's NU5 ID `f919a198` (v5 carries it in its bytes), so it blocks "NU5 later" |
| M24-6 | Regtest activates six upgrades at height 1 (`ycash6/qa/rpc-tests/test_framework/yellowback_util.py:125-136`) | One upgrade per height: the later variant overwrites (`crates/zakura-chain/src/parameters/network/testnet.rs:924-929`) | Ycash-era rules gate ordinally inside the `ycash` profile; Vault uses explicit membership and the builder refuses Vault sharing a height with a later variant | parameter validation; no consensus code |
| M24-7 | U-26 refuses at start-up Vault together with NU5..NU6.2, or Vault without Sapling at or below it (`ycash6/src/init.cpp:1541-1565`) | Builder checks only order and height 0 (`testnet.rs:959-976`) | new `ParametersBuilderError` variants with ycash6's accept/refuse table (`ycash6/src/test/testnet_params_tests.cpp:193`) | parameter validation |
| M24-8 | Previous-epoch walk-back skips unset NU5..NU6.2 for `old-consensus-branch-id` (`ycash6/src/consensus/upgrades.cpp:144-162`) | Predecessor = previous variant; with Vault after Canopy the predecessor *is* Canopy; mempool grace instead of a re-run (`zakurad/src/components/mempool.rs:191`) | map the C++ diagnosis to the grace path; test the reject class | upgrade-table rung; nothing lower |
| M24-9 | Equihash (n,k) chosen from solution size, then checked against height (`ref/ycash6/src/pow.cpp:155-191`, `main.cpp:5757-5774`) | `Solution` has 1344- and 36-byte variants only; (n,k) bound to network kind (`crates/zakura-chain/src/work/equihash.rs:43-72,95-136`); header policy context-free (`zakura-header-chain/.../pow_policy.rs:69-74`) | a 400-byte variant; (n,k) chosen by network **and** height; size never trusted | network parameter, not the vault tier; "no change" cannot parse a Ycash block |
| M24-10 | YDF: 5 % to a rotating P2PKH/P2SH list, 570,000–2,274,999 (`ref/ycash6/src/main.cpp:5901-5939`) | Founders' reward ends at the first halving; funding streams P2SH-only (`crates/zakura-consensus/src/block/check.rs:205-300`) | `ydf_reward_is_valid` under the `ycash` profile; streams and lockbox empty | rule port, consensus-reviewed; reusing funding streams gets fraction and recipients wrong |
| M24-11 | Script flags from height (`GetVaultScriptFlags`, `ycash6/src/main.cpp:845`); checker subclass reads set state (`ycash6/src/vault/checker.h:25`) | Constant `P2SH \| CHECKLOCKTIMEVERIFY` (`crates/zakura-script/src/lib.rs:170`); `script::Request` = (tx, input) only | thread `(network, height)` and an `Arc<SetSnapshot>`; flags independent of tx version | verifier plumbing required by the opcodes; a version-keyed shortcut would turn 0xb2 back into NOP3 |
| M24-12 | Interpreter in-tree C++ (`ycash6/src/script/interpreter.cpp`, +302) | `zakura-zcash-script` 0.0.1 is a crates.io pure-Rust crate: flags end at bit 9, `SignatureChecker` has only `check_sig`/`check_lock_time`, 0xb2 = NOP3, 0xc0–0xc2 → `BadOpcode` (`zakura-zcash-script:src/interpreter.rs:136-196`, `src/opcode/mod.rs:399-407,1193-1205`) | fork it in the common fork; add 0xb2/0xc0/0xc1/0xc2, bits 10–12, checker callbacks that fail closed | opcode rung (already chosen on the C++ lines); never 0xbb–0xbf |
| M24-13 | `-reindex` replays acts from undo (`ycash6/src/vault/node.cpp` `CoinsFromUndo`) | Checkpoint commits skip contextual validation (`crates/zakura-consensus/src/router.rs:401`, `checkpoint.rs:1371`); VCT/frontier artefacts import state | compute vault and YED deltas in `prepare_block_batch` (`zakura-state/.../zakura_db/block.rs:1348`) for every commit; never import them | state rung; an indexer outside the write path would accept blocks the module rejects |
| M24-14 | Fork-block pin + sparse checkpoints (`ref/ycash6/src/chainparams.cpp:131-132,242-283`) | Dense checkpoints, pre-Canopy checkpoint-only (`checkpoint.rs:647-690`) | regenerate the Ycash list from ycash6 through 1,100,005+, **never** into the Vault epoch until state equality is proven; pre-Canopy trust stated (K-9) | data; full re-validation of pre-Canopy is optional (K-9 b) |
| M24-15 | `ConnectBlock` holds `cs_main` and applies acts sequentially on one overlay (`ycash6/src/main.cpp:3681-3691,4342-4349`) | Semantic verification is concurrent per transaction (`crates/zakura-consensus/src/block.rs:595`) | sequential vault and YED rules in contextual validation (`non_finalized_state.rs:790`) + `UpdateWith<VaultDelta>`; scripts read a fork-aware parent snapshot awaited like `AwaitBlockInfo` | same rung, new location; no cheaper place for the reads |
| M24-16 | Vault DB with per-block undo 4,096 deep, tip marker, reconcile (`ycash6/src/vault/db.*`) | In-memory forks reverted by `revert_chain_with`; finalized state undone only offline (`zakura_db/rollback.rs:1`) | no finalized undo; `rollback` refuses past Vault (K-14); window 1,000 (K-13) | state rung; storage layout free, `StateHash` preimage exact |
| M24-17 | `statehash` defined over the LevelDB key/value serialisation (`ycash6/src/vault/node.cpp:505`, `yellowback/view.h:933`, `SERIALISATION.md`) | RocksDB column families with their own encodings | a canonical preimage encoder separate from storage | state rung; changing the hash breaks both C++ lines and the model |
| M24-18 | YED index is consensus; `AbortNode` if it cannot evaluate (mapping §22 "Unhealthy index") | Zebra-lineage secondary indexes live outside block verification | YED state inside the verified write path, committed atomically with the block | state rung |
| M24-19 | Miner's price tag via the global `COINBASE_FLAGS` (`ycash6/src/miner.cpp`, `yellowback/policy.h:42-45`); feeds payee eligibility | Coinbase built in Rust, no flags hook | template hook reading the node-local `yed_setquote` | mining policy; a tagless kogany block changes later payee sets |
| M24-20 | Regtest mines real (48,5) PoW (`ycash6/src/chainparams.cpp:1100-1114`) | Regtest PoW waived, shape-only (`testnet.rs:1533`, `pow_policy.rs:44,58-75`); solver (200,9) only (`equihash.rs:231`) | C++ nodes mine in mixed tests; kogany templates solved by the Python solver; no regtest PoW switch (K-16) | test affordance only; recorded gap |
| M24-21 | `RecheckMempool`/`RemoveInvalidVaultSpends` on every tip change (`ycash6/src/vault/node.cpp`) | Mempool re-verifies only on `Reset` (`zakurad/src/components/mempool.rs:865-907,1072-1110`) | re-verify template-input transactions on `Grow`, or evict | policy only |
| M24-22 | DoS 0 for state-dependent template failures, 10 for byte-level act failures (`ycash6/src/main.cpp:2202`) | `misbehavior_score` per error (`crates/zakura-consensus/src/error.rs:782`) | new error variants with those scores | policy |
| M24-23 | `YV` act carrier standard to 1,200 bytes once active (`ycash6/src/policy/policy.h:46`) | Single OP_RETURN ≤ 83 bytes (`zakurad/src/components/mempool/config.rs:87`) | height-dependent data-carrier limit | policy |
| M24-24 | Recoverable secp256k1 signatures for `OP_CHECKSETSIG` (65 bytes) | `secp256k1 = "0.33"` default features (`ref/zakura/Cargo.toml:131`) | enable `recovery` | dependency feature |
| M24-25 | PQ verification by vendored C (`ycash6/src/crypto/pq/`, patches P1–P3) | No PQ code | vendored verify-only C via `cc`, SHA256SUMS-pinned (K-8) | primitive-crypto choice; byte-identical by construction |
| M24-26 | Ordered `std::map` iteration in state hashes; `int64_t` with range checks; no float, clock or socket | `HashMap` random order; release profile wraps on overflow (`ref/zakura/Cargo.toml:195-210`); unwinding panics | `BTreeMap` only; `checked_*`/`i128`; clippy denies; release-profile test runs | implementation discipline, no tier |
| M24-27 | `-blocknotify`/ZMQ for clients (`ycash6/src/zmq/zmqpublishnotifier.cpp`) | None; gRPC `indexer.proto:99-129` streams | clients poll or use gRPC (K-17) | no node change |
| M24-28 | Wallet signs YED, vault and PQ spends in the node (`ycash6/src/rpc/yellowbackwallet.cpp`, `rpc/vault.cpp` act RPCs) | No wallet, no `signrawtransaction` (`zakurad/src/components/zcashd_compat/supervisor.rs:34-36`) | read and node-state RPCs native; wallet via ycash6 sidecar (K-3) | interface decision, no consensus rung |
| M24-29 | Same genesis and magic as Zcash; separation by port, seeds, protocol version, branch IDs (`ref/ycash6/src/chainparams.cpp:214-228`) | v2 overlay `chain_id` = genesis hash (`zakura-network/src/zakura/handshake.rs:265-271`) | v2 off on Ycash (K-11); later a Ycash `chain_id` | network layer, no consensus change |
| M24-30 | P2P 270013 floor, 270200 at Vault, MSG_WTX unadvertised (`ref/ycash6/src/version.h:13-56`) | 170_190 and per-upgrade 170_xxx minima (`zakura-network/src/constants.rs:350-364`, `protocol/external/types.rs:88-129`) | profile-driven version table | network policy |
| M24-31 | Wildcard-free C++ switch on upgrade index | `_ =>` arms compile silently with a new variant (`zakura-rpc/src/methods/types/get_block_template/proposal.rs:206-216`) | hand audit of every `_ =>` match on `NetworkUpgrade`, one test per arm | review discipline |
