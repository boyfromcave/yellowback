# Survey E — Verification, test and CI strategy for the kogany port

**Date:** 2026-11-01. **Lane:** E (verification, test, CI). **Status:** input to
`docs/plans/kogany/kogany-yellowback-plan.md`; nothing here is decided.

**Pins surveyed:** `ref/zakura` @ `2b062412c` (= `kogany` `upgrade/vault` = `kogany-legacy`);
`ref/ycash6` @ `040894344b`; `ref/ycash` @ v4.5.0 (`624c12814`); `ycash6` `upgrade/vault` @
`65cb4ae0f`; `ycash-dd` `upgrade/vault` @ `781946771`; `librustzcash6` `upgrade/vault` @ `af841431`.
Paths below are relative to the workspace root unless they start with `crates/`, `.github/`,
`docs/`, `qa/` or `scripts/`, which are under `ref/zakura/` (that is, kogany at the pin).

## Summary

The two C++ lines already carry a usable oracle for a third line: nine golden-vector JSON files
that are byte-identical on both lines and pinned by `qa/yellowback-cross-line.manifest`, a 462-block
Yellowback golden chain with a published state hash, and a runtime cross-line driver
(`ycash6/qa/yellowback-rc-crossline.py`) that compares `getbestblockhash`,
`vault_getinfo.statehash` and `yed_getstatehash` between nodes of different lines on one devnet.
The kogany port should reuse all three as they are and add a Rust replay of the vectors. The
port's main verification instrument should be **mixed-line regtest**: kogany nodes added to the
existing Python functional suite and the devnet, where they follow and are checked against
`ycash6` nodes. That instrument works because of one finding. **Zakura's regtest and Ycash's
regtest share the genesis block and the magic bytes, and both use Equihash (48,5)**: the C++
lines keep (48,5) at every height, including after the Ycash upgrade. **But Zakura's regtest skips
PoW** (it checks the solution's shape only) **and has no (48,5) or (192,7) solver**, so
`generate` on kogany produces blocks ycashd rejects. So in mixed regtest only the C++ nodes mine,
or kogany's templates are solved by the Python framework's (48,5) solver. Real (192,7) PoW is
checked only by syncing Ycash mainnet and testnet.
Most of the Yellowback functional suite (48 of 58 scripts by a rough count) calls wallet RPCs that
Zakura cannot answer (it has no wallet). The way through is Zakura's own `zcashd-compat` pattern:
`ycash6` as a wallet sidecar behind kogany. For CI, kogany should run a short allowlist, about 6
trimmed upstream workflows, plus the workspace's four security workflows and a
`kogany-yellowback.yml` with the audit legs, the vector replay and the mixed-regtest suite. The 21
upstream fleet, release and Slack/DigitalOcean/Depot workflows stay off.

---

## 1. Zakura's test infrastructure (what exists at the pin)

| Piece | What it is | Use for the port |
|---|---|---|
| `cargo nextest` + `.config/nextest.toml` | 25 profiles. `all-tests` gates PRs, `full-tests` adds the ignored tests, and the long ones are `sync-full-mainnet`, `generate-checkpoints-*`, `rpc-submit-block` and `zcashd-compat-*` (`.config/nextest.toml:4-213`) | Every Rust-level gate. The sync and checkpoint profiles become the Ycash network-sync gate (W1) |
| `zakura-test` | Test harness crate: launch/transcript/mock services, plus Zcash block vectors `crates/zakura-test/src/vectors/block-{main,test}-*.txt` | Gets Ycash block vectors (fork block 570,000, the Ycash Blossom/Heartwood/Canopy activation blocks, a post-fork (192,7) block) next to the Zcash ones. Adding them never replaces Zcash's |
| `zakura-sim` | Deterministic simulation of the **P2P stack** only, built under `RUSTFLAGS="--cfg zakura_sim"` (`crates/zakura-sim/src/lib.rs:1-11`) | Not a consensus tool. Keep it nightly at most. It covers no Yellowback rule |
| `qa/suite.toml` + `cargo xtask sim-suite` | Registry of property suites, planted cases and ignored tests. Fails if a new harness or ignored test is unlisted (`qa/suite.toml:1-9`) | Any new ignored kogany test (e.g. a slow vault reorg) must be listed there, or the upstream check fails |
| `qa/fuzz/{header-chain,rpc,sim}` | cargo-fuzz targets | Model for a `qa/fuzz/vault` target that replays the C++ corpora (§3.1) |
| `crates/xtask` | `header-conformance`, `generate-/check-rpc-artifacts` (OpenRPC + indexer proto regenerated and diffed, `crates/xtask/src/rpc_artifacts.rs:7-18`), sim commands | `check-rpc-artifacts` must pass after `vault_*`/`yed_*` methods are added. The OpenRPC artifact is a second, generated statement of the RPC surface to diff against `yellowback-rpc-contract.json` |
| `crates/zakurad/tests/common/regtest.rs` | Regtest acceptance helpers: `Network::new_regtest(ConfiguredActivationHeights{…})`, template → `submit_block` (`:47-76`) | Pattern for kogany-only Rust regtest tests (activation, a vault spend, reorg) |
| `crates/zakurad/tests/zakura_regtest_e2e.rs` + `docker/zakura-regtest-e2e/run.sh` | Four-node host-networked regtest: smoke, pr-gate, long checkpoint and restart modes (`:1-50`) | The P2P/sync regression gate on Ycash regtest params, unchanged in shape |
| `zcashd-compat` (`docs/zcashd-compat.md`, `crates/zakurad/tests/common/zcashd_compat/`, `.github/workflows/zcashd-compat-regtest.yml`) | zakurad is the P2P/consensus front and a **zcashd is a wallet sidecar** with `connect=`/`listen=0`. The managed regtest suite spawns both (`docs/zcashd-compat.md:1-40`; README `:9-27`). The sidecar binary is a hash-pinned valargroup zcashd (`crates/zakurad/zcashd-compat-manifest.json`) | **The template for the wallet problem** (§4): `ycash6` as the sidecar. The upstream workflow itself is Zcash-only (it downloads a Zcash zcashd), so it is off on kogany |
| `docs/verify.md` | Release-artifact verification (minisign, GitHub attestations) only. Not a test document | Pattern for kogany release verification, later |

What Zakura does **not** have: a wallet, `gettxoutsetinfo`, `disconnectnode`, or any Ycash
parameter. Its RPC method set at the pin is the 41 names registered under `crates/zakura-rpc/src`
(`addnode … z_validateaddress`). It does include `generate`, `getblocktemplate`, `submitblock`,
`invalidateblock`, `reconsiderblock`, `getrawmempool` and `getbestblockhash`, which are what the
Python framework's sync and mining helpers call.

## 2. Equihash, mining and regtest (the finding)

| Line | Regtest Equihash | Mainnet/testnet | Solver available |
|---|---|---|---|
| `ycash6` (fork) | (48,5) at **every** height: `EquihashN/K` return the regtest default before consulting the upgrade table (`ycash6/src/chainparams.cpp:1100-1114`, baseline fix 3, `ycash6/doc/yellowback-review.md:149`). Without that guard, 6.20.0 applies (192,7) on regtest once the Ycash upgrade activates, about 5 min a block (`ycash6/doc/yellowback-baseline.md:54`) | (200,9) before 570,000, (192,7) after (`ref/ycash6/src/pow.cpp:165-176` by solution size; height check via `GetEquihashOverride`, `ref/ycash6/src/chainparams.cpp:968-995`) | C++ `default` solver, any (n,k) (`ref/ycash6/src/miner.cpp:829-895`). Python `gbp_basic(digest, n, k)` (`ycash6/qa/rpc-tests/test_framework/equihash.py:131`), used by `mine_block_raw` and `stratum-miner` |
| `ycash-dd` (v4.5.0) | (48,5): regtest returns before the upgrade table (`ref/ycash/src/chainparams.cpp:860-869`) | same as above | same C++ solver |
| Zakura/kogany | `REGTEST_N/K = 48/5` (`crates/zakura-chain/src/work/equihash.rs:50-53`). **Regtest PoW is waived**: the regtest builder forces `with_disable_pow(true)` (`crates/zakura-chain/src/parameters/network/testnet.rs:1533`), `RegtestParameters` has no field to turn it back on (`:1382-1403`), and the waiver checks the solution's *shape* only (`crates/zakura-header-chain/src/validation/context_free/pow_policy.rs:44,58-75`) | (200,9) only: `Solution::check` binds (n,k) to `is_regtest()` and nothing else (`equihash.rs:102-114`; upstream TODO at `:105-107` to make the regtest variant a `Vec` with arbitrary parameters). The solution enum has only 1344- and 36-byte variants (`:44-47`), so a 400-byte (192,7) solution does not parse (`from_bytes`, `:165-180`) | Internal miner: `tromp::solve_200_9` only (`equihash.rs:231`, feature `internal-miner`). `generate` works only when PoW is disabled (`crates/zakura-rpc/src/methods.rs:4259-4264`) and emits zero solutions (`for_proposal_for_network`, `equihash.rs:188-194`) |

The regtest networks are wire-compatible at genesis. ycash6's regtest genesis
`029f11d8…e327` (`ref/ycash6/src/chainparams.cpp:739`) and magic `aae83f5f` (`:726-729`) are
Zakura's `REGTEST_GENESIS_HASH` (`crates/zakura-chain/src/parameters/network/testnet.rs:51-52`)
and `magics::REGTEST` (`crates/zakura-chain/src/parameters/constants.rs:47`). So a kogany regtest
node can peer with ycash6 regtest nodes once the Ycash epoch (branch ids `374d694f`, `8e471bd6`,
`66314da3`, `19bd2d2f` at height 1, `ycash6/qa/rpc-tests/test_framework/yellowback_util.py:125-136`),
the YDF coinbase rule and the Vault upgrade are in place. That is lane B/D's work.

**Consequences for verification.**

1. **Mixed regtest: the C++ nodes mine and kogany follows.** kogany's own `generate` blocks carry
   an all-zero 36-byte solution, which ycashd rejects (`CheckEquihashSolution`). To have kogany
   *produce* blocks in a mixed test (template and coinbase-tag parity), take kogany's
   `getblocktemplate`, solve it with the Python (48,5) solver, and send it to `submitblock`. That
   is the path `mine_block_raw` already takes (`yellowback_util.py:22,1389`).
2. **kogany never checks (48,5) PoW on regtest.** Within a mixed network the C++ peers check it,
   which is enough for regtest. A regtest PoW switch would be a small kogany-only test affordance.
   Recommendation: none. Do not add one, and record the gap.
3. **(192,7) needs its own gate.** No regtest exercises it on any line. It is verified by (a) Rust
   unit vectors: Ycash mainnet headers before and after 570,000, with a negative case that a
   36-byte or 1344-byte solution after the fork is rejected (mirror `regtest_solution_is_rejected_off_regtest`,
   `crates/zakura-chain/src/work/tests/vectors.rs:200-240`); and (b) a full sync of Ycash mainnet
   and testnet from genesis (`sync-full-mainnet`-style profile). kogany needs no (192,7)
   **solver**. Testnet blocks come from external GPU miners (testnet plan T-21) and mainnet from
   pools. Whether kogany's internal miner should support Ycash is an open question (Q2).
4. **Trap row (rule 4).** Ycash proves PoW in `CheckEquihashSolution`/`ContextualCheckBlockHeader`
   by mapping solution size to (n,k) and then checking that the size matches the height
   (`ref/ycash6/src/pow.cpp:155-190`). Zakura binds (n,k) to the network kind through a two-variant
   enum (`equihash.rs:95-114`), which lacks any height dependence. Adaptation W: a third solution
   variant (400 bytes), with (n,k) chosen by network *and* height (the Ycash upgrade height); size
   is never trusted, which keeps Zakura's anti-downgrade property. Rung: this is Ycash network
   parameters (W1), not the vault upgrade, so it is outside the vault tier ladder. A per-network
   parameter, not a new consensus mechanism; the lower rung of "no change" does not exist, because
   kogany cannot parse a Ycash block without it. Lane B owns the design. Lane E owns the vectors and
   the sync gate.

## 3. Pointing each Yellowback test tier at kogany

### 3.1 Unit and golden vectors (the byte-identical oracle)

The nine `identical` vector files of `ycash6/qa/yellowback-cross-line.manifest` (lines 11-19),
together with what a Rust replay asserts:

| File | Content | kogany replay (Rust test, crate it lands in) | Wave |
|---|---|---|---|
| `vault_vectors.json` | branch id, opcodes 0xb2/0xc0/0xc1, template build/parse, acts, set sig messages, **ZIP-243 sighash under `0x6d5b7a31`**, owner spends that pass `VerifyScript` (`ycash6/qa/rpc-tests/test_framework/VAULT_VECTORS.md`, schema table) | template/act codecs; `spends[].sighash` through kogany's v4 sighash; `ownerSpends[]` through the script verifier | W2–W4 |
| `pq_vectors.json`, `pq_acvp_slhdsa.json`, `pq_falcon_kat.json`, `pq_wallet_vectors.json` | SLH-DSA/Falcon verify, ACVP and KAT, wallet derivation | `OP_CHECKPQSIG` verifier. KAT/ACVP pin the crypto crate. Wallet vectors only if kogany ever signs (it should not, §4) | W3 |
| `yellowback_golden.json` | 462 regtest blocks as `{height, hash, subsidyZat, txs[]}` plus `params`, `stateHash`, `totals` | Replay the txs through the YED module state machine and compare `stateHash` and `totals`. No headers, so it tests the module, not block validity | W5 |
| `yellowback_pq_vectors.json` | TX_PQCHANNEL/TX_PQPKH matcher cases plus a chain with its state | matcher plus state replay | W5 |
| `yellowback_attest_vectors.json` | attestation encodings, valid and invalid | attestation codec | W5 |
| `yellowback_math_cases.json` | 67 exact-rational arithmetic cases from the spec text | module arithmetic, i64/i128, no floats | W5 |

**Rules for the replay.** (1) kogany carries **byte-identical copies** of these files at one path
(proposed `crates/zakura-consensus/tests/data/yellowback/`). The cross-line manifest gains a third
column, or a kogany manifest maps each kogany path to the C++ path, and `qa/yellowback-cross-line.py`
learns a `--this-line kogany` path map. (2) kogany never regenerates a vector. The generators
(`gen_vault_vectors.py`, `gen_pq_wallet_vectors.py`, `test_yellowback_math_spec.py`) stay on the
C++ lines. A vector change lands on all lines together, which extends the existing both-lines rule.
(3) Every schema key a C++ test asserts gets a Rust assertion. A per-file checklist in the plan
records "key → Rust test" so nothing is silently skipped. (4) Fuzz corpora: `ycash6/src/test/gen_{vault,vault_state,yellowback,pq}_corpus.py`
produce inputs. A `qa/fuzz/vault` target can replay them in kogany against **verdicts recorded
from ycash6**, generated once and committed. Live cross-language differential fuzzing (FFI into the
C++) is out of scope as too heavy. Recommendation: verdict replay only.

**Rust-specific traps for byte-identity**, each as a four-part row:

| Ycash does X (via M) | Zakura's equivalent lacks M | Adaptation W | Rung |
|---|---|---|---|
| State hashes iterate `std::map` (ordered) in `ycash6/src/vault/state.cpp`, `src/yellowback/state.cpp` | Idiomatic Rust `HashMap` iterates in random order | Only `BTreeMap`/sorted `Vec` in the vault and YED crates. clippy `disallowed-types = HashMap/HashSet` in those crates' `clippy.toml`, plus an audit grep | No consensus change: an implementation discipline |
| Module arithmetic in `int64_t` with explicit range checks; overflow is UB and the code avoids it | Zakura's release profile has default `overflow-checks = false` (wrap); `dev`/`test` panic (`ref/zakura/Cargo.toml:195-210,302-336`) | `checked_*`/`i128` everywhere in the module, never bare `+`/`*` on amounts. `clippy::arithmetic_side_effects` denied in those crates. The math cases run under **release** too (`ci-tests` profile) | Discipline; no tier |
| No floating point, no clock, no sockets in the module (ycash6 audit "Determinism" step, `yellowback-tests.yml:712-720,840-906`; semgrep `ycash6/contrib/semgrep/rules/ycash-rpc.yaml`) | Nothing prevents `f64`, `SystemTime`, or `tokio::net` in a Rust crate | Port the greps as Rust patterns (`f32\|f64`, `SystemTime\|Instant`, `std::net\|tokio::net`) scoped to the module crates. Add a Rust variant of the semgrep "no float" rule | Discipline |
| `panic = abort`-free C++ (exceptions are rare in consensus) | Zakura unwinds on panic and requires consensus-state critical sections to be panic-free (`ref/zakura/Cargo.toml:196-204`) | No `unwrap`/`expect`/indexing in vault and YED state transitions. clippy `unwrap_used`/`expect_used`/`indexing_slicing` denied there | Discipline |

### 3.2 The Python functional suite (`ycash6/qa/rpc-tests`)

58 Yellowback scripts (`vault_*.py` ×16, `yellowback_*.py` ×42). A grep for wallet RPC calls
(`getnewaddress`, `sendtoaddress`, `z_*`, `yed_mint`/`yed_send`/`yed_redeem`, `listunspent`, …)
finds **10 with none**: `vault_activation_restart`, `vault_policy`, `vault_slashing`,
`vault_undo_prune`, `yellowback_devnet_upgrade`, `yellowback_framework_smoke`, `yellowback_index`,
`yellowback_mint_armed`, `yellowback_quote`, `yellowback_stock_node`. The grep is a rough
heuristic; some of these still need a wallet on a *peer* node. The other 48 need a wallet on at
least one node. `vault-rpc.md` splits the surface into "Read RPCs (no wallet needed)" and "Act RPCs
(wallet)" (`ycash6/doc/vault-rpc.md:108,166`). The RPC contract lists 52 `yed_*` methods
(`ycash6/doc/yellowback-rpc-contract.json`), several of them wallet-side (`yed_mint`, `yed_send`,
`yed_getnewaddress`, `yed_listunspent`, …).

**Proposal: the mixed-line harness (the cross-line equivalence harness).** Add kogany nodes as
followers inside the *unchanged* scripts, instead of porting the scripts:

- `YellowbackTestFramework` (`yellowback_util.py:515`) gains an opt-in `KOGANY_BIN`. When it is set,
  the framework starts k kogany nodes (default 1) with a generated `zakurad.toml`: regtest with the
  Ycash epoch at height 1, the Vault at `VAULT_ACTIVATION`, the same attestor-set and Falcon
  parameters as node 0, and `addnode` to node 1. The launcher maps ycashd arguments to TOML; the
  map is a table in the framework and its only kogany-specific code.
- `sync_all` (`yellowback_util.py:717`) and `mine` additionally wait for the kogany nodes' tip and
  assert equality of `getbestblockhash`, `vault_getinfo.statehash` and `yed_getstatehash.statehash`.
  At each sync point they also assert `getrawmempool` set equality: the mempool policy check.
- On a `assert_rejected`/negative path (a block or tx the C++ node rejects), the harness also offers
  it to kogany (`submitblock` / `sendrawtransaction`) and asserts the **same verdict class**. The
  reject *strings* are not compared, because they differ by design. The mapping of reject codes is a
  table in the plan.
- `split_network` uses `disconnectnode`, which Zakura lacks. kogany nodes stay on node 1's side
  of a split, and the plan records that.
- Nothing in a script changes. The same run is the C++ regression *and* the kogany equivalence
  check. CI runs the suite twice, with and without `KOGANY_BIN`, so that a kogany failure never
  hides as a C++ failure.

This generalises the existing runtime cross-line driver, `ycash6/qa/yellowback-rc-crossline.py`
(lines 1-22: ycash-dd nodes on a ycash6 devnet, compared every 100 blocks on the same three
values), to every functional script and every sync point.

**kogany-only Rust regtest tests** (in `crates/zakurad/tests/`, nextest profile `kogany-regtest`)
cover what needs no wallet: activation at the boundary, the dormant Zcash upgrades staying dormant,
a raw vault spend built from `vault_vectors.json` keys, reorg and undo across the vault state, and
restart. They are fast, need no Python, and are the PR gate when the mixed suite is too slow.

### 3.3 The devnet (`ycash6/contrib/yellowback/devnet`)

The devnet is wallet-driven throughout (`yellowback-devnet:645-873`: `sendtoaddress`,
`getnewaddress`, `generate`). kogany joins it the way ycash-dd does in rc-qualify step 3:
`yellowback-rc-crossline.py` gains `--kogany-zakurad PATH` (or a sibling `--line kogany`) next to
`--dd-ycashd`, takes the same consensus arguments from `devnet.json` and maps them to TOML. The
evidence file grows a column per line. **Three-way agreement every 100 blocks** becomes the
rc-qualify bar once kogany is a qualified line.

### 3.4 Client suites

| Client | Talks to the node via | Against kogany directly? | Otherwise |
|---|---|---|---|
| yolo | stock mining RPCs (`getblocktemplate`, `submitblock`, `validateaddress`, `getblockchaininfo`) | **Yes**, the first client to point at kogany. It needs the coinbase tag/TPL rules in kogany's template (W8) and the Python (48,5) stratum miner (`devnet/stratum-miner`) | — |
| chain-viz | read RPCs + read-only `yed_*`, `set_*`/`vault_*` panels | **Yes**, once the read surface lands (W7). Notify hooks (`-blocknotify`) need a Zakura equivalent: open (Q5) | — |
| lightwalletd-dd | `getblock`, `getaddresstxids` (insight index), read-only `yed_*`/`vault_*` proxies, the byte-equality gate | Mostly. Zakura serves `getaddresstxids/utxos/balance` (§1). Byte-equality of compact blocks against the yodl baseline is the gate | — |
| x402-ycash | `gettxout`, `sendrawtransaction`, `signrawtransaction` *as verifier*, `z_*` receipt RPCs | Partly. `signrawtransaction` and `z_*` receipt RPCs are wallet RPCs | sidecar |
| hawkeye | `set_*`/`vault_*` act RPCs (wallet) | No | ycash6 sidecar |
| YEW (via lightwalletd) | lightwalletd gRPC | Via lightwalletd-dd on kogany | — |
| YecWallet | drives a bundled ycashd's wallet over RPC | No; it bundles ycashd | sidecar, or out of scope (Q4) |

The client CI pattern today is a `node_line: [ycash-dd, ycash6]` input that fetches the node's
`node-bin` artifact (`lightwalletd-dd/.github/workflows/yellowback-tests.yml:40-61,236`; x402,
chain-viz and yolo the same, `chain-viz/.github/workflows/ci.yml:118-186`). kogany is added as a
**third option, report-only** until the plan's last wave: each client publishes against
`node_line: kogany` (a `zakurad` artifact plus a ycash6 sidecar where needed) without failing.

## 4. The wallet question, from the verification side

Zakura has no wallet (§1; confirmed by lane A). Its upstream answer to that is
`zcashd-compat`. The Ycash form is **`ycash6` as a P2P sidecar**: `connect=<kogany>`, `listen=0`.
kogany faces the network and ycash6 keeps wallet, RPC and ZMQ (`docs/zcashd-compat.md:1-33`).
For verification this costs nothing and gains much. A stock ycash6 with `connect=` still fully
validates every block it receives, so every sidecar run is also a two-line differential: if kogany
relays a block ycash6 rejects, the sidecar stalls and the test fails. The open part is whether
upstream's sidecar-specific zcashd changes (miner RPCs removed, the end-of-support halt off, the
"Zebra sync worker", `docs/zcashd-compat.md:85-104`; README `:30-60`) are needed for Ycash, or
whether a plain `connect=` ycash6 suffices for tests. Plain `connect=` is probably enough for
tests, but this is **unverified**; Q3.

## 5. CI for kogany

### 5.1 Upstream workflows

At the pin `.github/workflows/` holds **40** workflow files (56 YAML files under `.github` in all,
counting composite actions and app configs). The briefing's "53" is likely a count that includes
other YAML or GitHub's listing; the plan should cite 40. All are off on the fork (AGENTS.md "Its
GitHub Actions stay off").

| Keep (trimmed) | Why | Trim |
|---|---|---|
| `lint.yml` | clippy, rustfmt, `cargo deny`, MSRV, header-conformance, supply-chain (`cargo vet`, `qa/supply-chain/`) | drop nightly `unused-deps`; no Slack |
| `tests-unit.yml` | `build-tests` + 3-shard `unit-tests` nextest (`:216-322`): the regression gate that kogany still behaves as Zakura on Zcash networks | drop `publish-graph`, `report-nightly-result` (Slack); sim jobs nightly→weekly or off |
| `zakura-e2e.yml` | four-node regtest `pr-gate` (`:104-183`): sync/reorg on regtest | pr-gate only; long modes weekly |
| `docs-check.yml` | markdownlint/codespell/lychee | optional; keep (cheap) |
| `test-crates.yml` | each crate standalone under feature combos — catches a Ycash `cfg` breaking a Zcash-only feature | weekly, not per PR |
| `header-fuzz.yml`, `rpc-fuzz.yml` | bounded fuzz campaigns | weekly |

**Off (21):** the DigitalOcean fleet (`zakura-pr-node*`, `zakura-*-deploy`, `zakura-mainnet-rollback`,
`zakura-continuous-sync`, `zakura-vct-handoff-canary`, `zakura-mempool-{load,gossip}`, `zakura-cluster`),
the release pipeline (`create-release`, `release-binaries`, `release-ai-review*`, `release-drafter`,
`prepare-release-pr`, `release-pr-readiness`, `update-release-state`, `adopt-release-state`,
`publish-crates`, `semver-checks`, `changelog`), `ci-alerts`, `coverage` (Codecov), `benchmarks`
(gh-pages), `legacy-pages`, the cranelift pair, `cross-platform`, `history-growth`, `test-docker`,
and **`zcashd-compat-regtest`**, which runs a Zcash zcashd and is replaced by §5.2's sidecar job.
Several need secrets the fork does not have (`RELEASE_APP_PRIVATE_KEY`, the deploy SSH keys) or
self-hosted runners (`zakura-*-deploy`, `zakura-mainnet-rollback`). Also neutralise
`.github/dependabot.yml` version updates (security updates only, per SECURITY-CI) and ignore
`mergify.yml`/`zbot.yml` (the apps are not installed). The full keep/off list goes into the plan as
a decision (Q1), and enabling happens one workflow at a time.

### 5.2 Added

| Workflow | Legs | Blocks a PR when |
|---|---|---|
| `semgrep.yml`, `codeql.yml` (`rust`, `actions`, `python`), `secops.yml` (zizmor, gitleaks, OSV over `Cargo.lock`, cargo-deny with a `contrib/secops/deny-node.toml`, the root `deny.toml` stays upstream's), `code-scanning.yml` | the workspace security pattern, verbatim from `ycash6/SECURITY-CI.md` (four workflows, pinned tools, acceptance files) | as in SECURITY-CI |
| `kogany-yellowback.yml` **audit** | (a) **consensus-diff report** vs `kogany-legacy` over the consensus paths (proposed set: `crates/zakura-consensus/`, `crates/zakura-script/`, `crates/zakura-chain/src/{transaction,block,parameters,work,transparent,amount}`, `crates/zakura-state/src/service/{check,finalized_state,non_finalized_state}`, `crates/zakura-header-chain/src/validation/`, and `Cargo.lock` lines for `zakura-zcash-script`/`zakura-primitives`/`zakura-protocol`/`zakura-equihash`), uploaded as the two-reviewer gate's artifact (AGENTS rule 2; report-only like the C++ upgrade line); (b) **frozen-file report** (report-only): upstream files kogany must never touch (`qa/kogany-frozen-files.txt`: Orchard, NU5–NU7, Tachyon/Ironwood paths, the minimalism constraint made measurable), printing any delta; (c) cross-line identity: the vector copies match the ycash6 head (`qa/yellowback-cross-line.py --this-line kogany`); (d) vault chain parameters equal ycash6's (`qa/yellowback-vault-params.py` gains a Rust extractor for kogany's parameters); (e) determinism/naming greps (§3.1 traps; `DigiDollar`, `ydollar`, attribution) | (c), (d), (e) fail; (a), (b) never fail |
| `kogany-yellowback.yml` **vectors** | nextest profile `kogany-vectors`: every §3.1 replay, debug **and** `ci-tests` (release-like, wrapping) | any failure |
| `kogany-yellowback.yml` **upstream-dormancy** | Zakura's own NU5/NU6/NU7 tests on Zcash Mainnet/Testnet/regtest params, unchanged and green. Any edited upstream test is listed in the PR body with its reason | any failure, or an upstream test deleted |
| `kogany-yellowback.yml` **mixed-regtest** | build `zakurad`; fetch ycash6 `node-bin.tgz` at the matching branch (the ycash6 cross-line rule of `yellowback-tests.yml:759-801`); run the §3.2 harness on a shard list (`KOGANY_BIN` set) | from its wave's gate on (§6) |
| `kogany-yellowback.yml` **sidecar** (nightly) | kogany + a `connect=` ycash6 running the wallet scripts | from W9 |
| `kogany-yellowback.yml` **sync** (manual/weekly, long) | full Ycash mainnet and testnet sync from genesis; checkpoint hashes equal ycash6's | from W1 (manual) |

The scheduled jobs need the workflow on the **default branch**. The ycash6 port hit this (F-39(c),
`docs/plans/yellowback-ycash6-plan.md:344`), so kogany's GitHub default should be `upgrade/vault`
before any schedule is expected to run.

### 5.3 `make spec`, the release train, calibration

- **`make spec`/`spec-check`**: they write the generated spec and contract copies into the C++
  trees, `yecwallet-dd` and `lightwalletd-dd`. kogany gets a copy (`doc/yellowback-spec.md`,
  `doc/yellowback-rpc-contract.json`) **only when it serves the RPCs** (W7). Until then it is
  outside, as AGENTS.md says. From W7, `EXTRACT_SPEC_KOGANY_DIR` joins the targets and the audit's
  contract leg checks that kogany's OpenRPC methods (xtask artifact) ⊇ the contract's read methods,
  with the wallet methods listed as sidecar-served.
- **Release train** (`scripts/release-train.py`): kogany becomes a `COMPONENTS` entry with
  `commit` and later `tag` (`vault-params/v<version>`, as the C++ lines have), and
  `YELLOWBACK_RPC_VERSION` is read from kogany's Rust constant. **Not before** kogany is declared a
  qualified line (Q6). Until then a train names it at most as `kogany: none`.
- **Calibration (`yb-calibration`)** vendors ycash6's Python model and never reads a node
  (`yb-calibration/docs/decisions.md:342`). Nothing changes for it. kogany receives constants only
  through the vault-params cross-line equality (§5.2 (d)), so a constant can never drift on the
  third line without failing CI.

## 6. Wave → verification-gate matrix

The wave names are this lane's proposal and are to be reconciled with lanes B, C and D in the
synthesis. Each gate is runnable by one agent from a clean worktree. "Mixed" means §3.2's harness
with `KOGANY_BIN` set.

| Wave | Content (proposed) | Exit gate (all must hold) |
|---|---|---|
| **W0** scaffolding | baseline tag `kogany-baseline`, CI allowlist (§5.1), security CI, audit job (report legs), mapping §24 skeleton | upstream `tests-unit` + `lint` green on kogany unchanged; security workflows green; consensus-diff report empty |
| **W1** Ycash network | parameters, Equihash (192,7), branch ids, prefixes/HRPs, YDF, checkpoints (lane B) | Ycash block vectors parse and validate, with negative solution-size cases; **full mainnet and testnet sync from genesis**, tip and every checkpoint equal to ycash6; kogany ⇄ ycash6 P2P on regtest; Zcash networks' upstream suite still green (dormancy); tag `kogany-ycash-baseline` (the stock comparison binary for later waves, as `ycash6-stock` is, `yellowback-review.md:149`) |
| **W2** Vault epoch | `NetworkUpgrade` placement, `0x6d5b7a31`, v4-only, sighash binding (lane D) | `vault_vectors.spends[].sighash` replay; mixed: `vault_activation_restart`, the activation-boundary script; Zcash NU5–NU7 tests unchanged and green; kogany rejects v5 after Vault on Ycash params |
| **W3** script + PQ | CSV 0xb2, 0xc0, 0xc1, 0xc2; SLH-DSA/Falcon verify | `vault_vectors.ownerSpends`, `pq_vectors`, ACVP, KAT replays (debug and release); fuzz verdict-corpus replay |
| **W4** set/vault state | per-vault and set state, storage, undo/reorg | mixed: `vault_primitive`, `vault_slashing`, `vault_undo_prune`, `vault_pq_reorg`, `vault_dos` with `statehash` equality at every sync; kogany-only Rust reorg/restart tests |
| **W5** YED module | tags, attestations, math, fees rules | `yellowback_golden` + `yellowback_pq_vectors` + `attest_vectors` + `math_cases` replays; mixed: `yellowback_lifecycle`, `_activation_reorg`, `_reorg_restart`, `_claim`, `_interm`, `_fees*` with `yed_getstatehash` equality |
| **W6** mempool/policy | vault/YED standardness, fee rules, limits | mixed: `vault_policy`, `vault_refee`, `yellowback_mempool_limits` with mempool-set equality and verdict-class equality on every rejected tx |
| **W7** read RPCs | `vault_*`/`set_*`/`yed_*` read surface, `rpcversion` 8 | `vault_rpc_contract.py`/`yellowback_rpc_contract.py` shapes against kogany; `xtask check-rpc-artifacts`; spec copy in kogany (`make spec-check`); chain-viz and lightwalletd-dd read-only suites against kogany (report-only) |
| **W8** mining | template tag, TPL rules, coinbase | mixed `yellowback_mining`; kogany-produced blocks (Python solver) accepted by ycash6; yolo `ci.yml` against kogany green |
| **W9** wallet via sidecar + full matrix | ycash6 sidecar profile, client matrix | the whole Yellowback functional suite in mixed mode green, twice in a row; sidecar nightly green 7 days; three-way rc-crossline on the devnet (5 rounds × 100 blocks); every client's `node_line: kogany` leg green; then the lead architect decides whether kogany joins the release train |

Cross-cutting at every wave: the consensus-diff report attached to the PR with the four-part check
(AGENTS rule 2/4); mapping §24 rows for each trap; no change to the shared vectors except on all
lines together.

## 7. Estimate (verification work only, not the port itself)

Roughly 9–13 agent-days, flagged as a rough sizing. W0 CI and security port: 1½. Rust vector
replays: 3 (sighash, script and PQ are the largest). Python harness kogany adapter, TOML mapping and
sync-point asserts: 2. rc-crossline third line: ½. Sidecar profile: 1–2, mostly the unverified
part of Q3. Mainnet/testnet sync gate: 1, plus wall-clock sync time. Client `node_line: kogany`
legs: 1–2.

## Open questions for the lead architect

1. **Which upstream workflows run on kogany?** Recommendation: the six in §5.1 (trimmed), the 21
   others off, enabled one at a time; the scheduled ones only after kogany's default branch is
   `upgrade/vault`.
2. **Does kogany's internal miner support Ycash (192,7)?** Recommendation: no. kogany validates
   (192,7) but does not solve it; mining stays with pools and the C++ miners, and `generate` stays a
   regtest-only, PoW-waived affordance.
3. **Is `ycash6` as a plain `connect=` sidecar the supported wallet story for kogany**, and do we
   need any of valargroup's sidecar changes (miner RPCs removed, a single-peer hard lock)?
   Recommendation: plain `connect=` for tests now; production hardening is a later, separate
   decision.
4. **YecWallet against kogany**: out of scope (YecWallet bundles ycashd), or sidecar-tested?
   Recommendation: out of scope.
5. **Notify hooks** (`-blocknotify` and the like, used by chain-viz): add a Zakura equivalent or
   have chain-viz poll on kogany? Recommendation: poll, so no node change.
6. **When does kogany become a qualified line** (release train, three-way rc-qualify,
   both-lines → all-lines rule)? Recommendation: at the end of W9, by explicit decision of the lead architect,
   not automatically.
7. **Regtest PoW on kogany:** accept that kogany regtest checks the solution shape only, with
   (48,5) PoW checked by the C++ peers in mixed tests? Recommendation: accept, and record it.

## Inputs the synthesis needs from other lanes

- **Lane A:** the exact consensus-path set for the consensus-diff report (§5.2 (a)), including
  which `zakura-state` modules apply transparent spends; confirmation of no wallet; where
  `getblocktemplate` builds the coinbase (for W8's tag); whether `getblockchaininfo.upgrades` will
  list `6d5b7a31` keyed by branch id as ycashd does (the harness asserts it,
  `vault_harness.py:134-136`).
- **Lane B:** the Equihash design for the 400-byte solution and the height binding (§2 item 4);
  how Ycash regtest is selected in kogany config (a `Network::Ycash`-style kind, or configured
  regtest params with Ycash branch ids), because the Python TOML mapping depends on it; whether
  the YDF coinbase rule is active on regtest (`nYdfMandateEndHeight = 5`,
  `ref/ycash6/src/chainparams.cpp:685`); the Ycash block heights to vendor as vectors.
- **Lane C:** the per-RPC wallet/no-wallet split for all 52 `yed_*` plus `set_*`/`vault_*`
  methods (decides §3.4 and which scripts can run without a sidecar); the module state hash
  definitions (`vault_getinfo.statehash`, `yed_getstatehash`) as byte specs, which kogany must
  reproduce; the list of C++ unit tests (`ycash6/src/test/{vault,yellowback,pq}_*_tests.cpp`, 27
  files) with any that have no Rust counterpart (wallet, coinselect, txbuilder).
- **Lane D:** the `NetworkUpgrade` placement of Vault, so that W2's "Zcash NU5–NU7 tests
  unchanged" gate is well defined; the list of upstream files the minimalism constraint freezes
  (feeds `qa/kogany-frozen-files.txt`); whether any upstream test must change, with its
  justification.
