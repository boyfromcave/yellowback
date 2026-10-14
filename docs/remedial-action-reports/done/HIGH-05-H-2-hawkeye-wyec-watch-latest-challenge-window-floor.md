# HIGH — 05/H-2, 05/T-3 — Watch `MintProposed` at `latest`, enforce a mainnet `challengeWindow` floor and a non-zero `mintCap`, alarm and pause on a finality stall, and test it with pinned finality

Repos / branches to change: `hawkeye` (`fix/05-H-2-watch-latest` off `upgrade/vault`), `wyec` (`fix/05-H-2-mainnet-floors` off `upgrade/vault`; a contract change here means a re-pin in Hawkeye's `eth/tools/fetch-wyec.sh`, ABI export and vector regeneration, §7). No node change. · Audit source: `05-bridge-hawkeye-wyec.md` §H-2 (`:108-137`), T-3 (`:275`); `verification/05-verification.md` §H-2 (`:81-96`), T-3 (`:27`); `00-consolidated.md` rows 05/H-2, 05/T-3 and recommendation R3. · Status: done — completed 2026-10-13T06:41Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13, re-confirmed 2026-10-14 at ycash-dd 3fe3492b6 and ycash6 1ebfee622; nightly tier pending the owner's dispatch)

## 1. Finding

The optimistic-mint watcher only ever sees a `MintProposed` once its block is **finalized**: `scan_eth` (`crates/hawkeye/src/engine/mint.rs:139-160`) scans `[cursor+1, finalized]` with `finalized_height()` → `EthClient::finalized_block_number` (`crates/hawkeye-eth/src/scanner.rs:234-251`, the `finalized` tag; a depth fallback is refused on mainnet, `config.rs:688-691`) and returns early while `fin < from` (`:151-153`). The contract, however, runs the other half of the protocol on `latest`: `proposeMint` sets `eta = block.timestamp + challengeWindow` (`wyec/contracts/WyecBridge.sol:230-233`), `executeMint` needs only `block.timestamp ≥ eta` and the proposer still a guardian (`:257-267`), and `challengeMint` has no time condition at all (`:243-251`). Detection latency is therefore Ethereum finality (2 epochs ≈ 12.8 min nominal, unbounded during a stall) plus a tick, while the watcher's own deadline is `eta − window/4` (`challenge_due`, `mint.rs:66-77`).

Two scenarios. **A — finality stall**: during a stall `finalized` does not advance (May 2023: ≈ 1 h); Hawkeye ingests nothing, never challenges, while a rogue guardian's `proposeMint` and, a window later, `executeMint` mine normally; one key mints up to `mintCap` per `capWindow`, or without bound when `mintCap = 0`, which is the deploy script's default (`wyec/script/Deploy.s.sol:16-17, 46-47`; Hawkeye's `eth/script/Deploy.s.sol` likewise). Slashing on Ycash afterwards recovers nothing on Ethereum. **B — window shorter than detection**: a `challengeWindow` ≤ ≈ 13 min + tick + inclusion can never be challenged; nothing enforces any relation between the window and finality — the design doc gives guidance only (`wyec/docs/wyec-contract-design.md:282`, "longer than Ethereum finality (~13 min) plus … latency; a P8 parameter"), `check_bridge` (`crates/hawkeye/src/foreign/ethereum.rs:259-283`) reads the window and enforces nothing, and `startup_checks` (`crates/hawkeye/src/daemon.rs:106-119`) logs it and warns only about `threshold == 1`. The attacker needs one current guardian key (bonded, slashable after the fact), so the verifier labels this "High, insider key"; the payoff is bounded only by `mintCap`, which defaults to unbounded. T-3: no existing test can observe any of this — the anvil fixtures use `--slots-in-an-epoch 1` (finalized = latest − 2) and 60–120 s windows (`crates/hawkeye/tests/engine.rs:182-184`, `hawkeye-eth/tests/anvil.rs:50`, `eth/test/Deploy.t.sol:22`), and the Ethereum-backed suites return early and pass vacuously without anvil (`engine.rs:174-181`, `anvil.rs:40-46`; CI sets `HAWKEYE_REQUIRE_ANVIL=1`, developers do not).

## 2. Root cause

- `crates/hawkeye/src/engine/mint.rs:139-160` — one scan, one cursor, `to = finalized`; `foreign/ethereum.rs:144-158` maps `MintProposed` only from that scan.
- `crates/hawkeye/src/engine/mint.rs:66-77` (`challenge_due`), `:321-358` (`check_pending_mints`), `:361-397` (`challenge_if_due`) — correct logic, fed too late.
- `crates/hawkeye-eth/src/mode.rs:9-13, 53-62` — `MAINNET`, `MAINNET_MIN_THRESHOLD`, `check_contract_threshold`: the only mainnet contract rule; nothing for the window or the cap.
- `crates/hawkeye/src/foreign/ethereum.rs:259-283` (`check_bridge`), `crates/hawkeye/src/foreign/mod.rs:287-292` (`BridgeInfo { threshold, challenge_window }`) — no `mint_cap`, no floor.
- `crates/hawkeye/src/engine/mod.rs:159-160` — `Memory.eth_finalized` is recorded but never compared across ticks; `:514-517` — `signing_paused` only knows guardian drift.
- `wyec/contracts/WyecBridge.sol:181-194` — constructor refuses only `challengeWindow == 0`; `wyec/script/Deploy.s.sol:62-64` — mainnet rule for `threshold` only, `MINT_CAP` defaults to 0.
- Tests: `crates/hawkeye/tests/engine.rs:182-184`, `crates/hawkeye-eth/tests/anvil.rs:50`, `eth/test/Deploy.t.sol:22`, `wyec/test/utils/BridgeTestBase.sol:13` (`WINDOW = 3600`).

## 3. Fix options considered

- **Keep `finalized`, lengthen the window to cover worst-case stalls.** Rejected: no window covers an unbounded stall, and the watcher would still sit idle for 13 minutes of every window for no safety gain — a challenge signature binds `(lockId, proposalId)` (`WyecBridge.sol:354-357`) and is harmless if its proposal's block reorgs out (`challengeMint` reverts `NoProposal`, which `challenge()` already treats as done, `mint.rs:578-582`).
- **Scan everything at `latest`.** Rejected: burns must stay finalized (a release against a reorged burn is a loss), `Minted` must stay finalized (ledger state `MINTED` is terminal), and slash evidence must be finalized (a `FRAUDULENT_MINT` case on a proposal that reorgs away is itself griefing). Only proposals and challenges move.
- **Floor in Hawkeye only vs also in wyec.** Hawkeye's `check_bridge` refusal protects an operator who starts an attestor; it does not stop a deployer. The deploy script already carries the mainnet `threshold` rule (`Deploy.s.sol:62`), so the window floor and the cap rule belong beside it; a constructor check is three lines, costs nothing on other chains, and is the only version a guardian can read back from the bytecode before signing (design §8 step 3). Chosen: all three layers (constructor, script, `check_bridge`), each independently sufficient.
- **Pause on stall: all signing vs own proposals only.** Chosen: pause *own* `proposeMint`/`mint` submissions and `Mint` signing; never pause challenges, cancels, heartbeats or slash votes (those are the defence).
- **Test: mock `ForeignChain` vs anvil.** Both: a trait wrapper for the deterministic unit path, anvil with a large epoch for the end-to-end path.

## 4. Recommended fix

### 4.1 Hawkeye: proposals at `latest` (`engine/mint.rs`, `foreign/mod.rs`, `foreign/ethereum.rs`, `hawkeye-store`)

1. `ForeignChain` gains `fn latest_height(&self) -> BoxFut<'_, u64>` (Ethereum: `EthClient::latest_block_number`, `client.rs:227-229`; NEAR: its `final`/`optimistic` distinction — implement as the optimistic head) and `fn scan_proposals(&self, from: u64, to: u64) -> BoxFut<'_, ScanBatch>` returning only `MintProposed` and `MintChallenged` events (Ethereum: the same `eth_getLogs` filter restricted to the two topics; `scanner.rs::scan` takes a topic list parameter).
2. `Engine::scan_eth` keeps the finalized pass unchanged. A new step `scan_proposals_latest`, run every tick right after it: `from = max(fin + 1, mem.latest_scanned.saturating_sub(PROPOSAL_RESCAN_DEPTH))`, `to = latest`, with `PROPOSAL_RESCAN_DEPTH = 64` blocks (two epochs: a proposal that reorgs in and out inside the unfinalized range is re-seen); no ledger cursor for this pass — the range is re-read each tick, which is at most 64 + a few blocks of logs filtered to two topics.
3. Each `MintProposed` from this pass is upserted into `pending_mints` with a new column `provisional INTEGER NOT NULL DEFAULT 0` (schema **V6** — coordinate with `HIGH-05-H-1`'s V6: one migration, both changes) set to 1 and judged by the existing `judge_minted(…, proposal = true)`; `MintChallenged` from this pass inserts into `mem.challenges_done`. When the finalized pass later ingests the same `(lock_id, tx_hash)` it clears `provisional` (`UPDATE pending_mints SET provisional = 0`); when the finalized cursor passes the provisional row's `block` without having seen it, the row is deleted (`DELETE FROM pending_mints WHERE provisional = 1 AND block <= ?fin` after the finalized ingestion of that range).
4. `check_pending_mints` (`mint.rs:321-358`): a provisional row follows the same `Defer`/`challenge_if_due` path — this is the whole fix — but the `Fraud` branch is split: `self.challenge(pm, &why)` runs for provisional and final rows alike; `fraudulent_mint`'s slash-case part (`:427-470`) and the `fraudulent-mint` alarm run only for `provisional == 0` (the finalized pass will re-judge the row and open the case then). `challenge_if_due` already re-reads the live proposal from the contract (`:363`) and compares ids, so a reorged proposal is never challenged with a stale id.
5. `judge_minted`'s `proposal` branch (`:114-119`) moves the lock `Signed|Challenged → Proposed` on a provisional observation too; a reorg that drops the proposal is handled by the existing `Void`/re-propose logic (`propose`, `:852-919`) because `foreign.proposal(lock_id)` is consulted before every action.

Memo for reviewers: the challenge signature is the sign-once `Challenge(lockId, proposalId)` record (`signonce.rs:225-283`); nothing about its keying changes. `ForeignChain::now()` (`ethereum.rs:319`) reads `latest` timestamp already, so `challenge_due`'s `now` is consistent with the new scan.

### 4.2 Mainnet floors (`hawkeye-eth/src/mode.rs`, `foreign/mod.rs`, `foreign/ethereum.rs`, `daemon.rs`)

```rust
/// Two epochs of 32 slots of 12 s: the nominal time to finality on Ethereum mainnet.
pub const ETH_FINALITY_NOMINAL_SECS: u64 = 2 * 32 * 12;            // 768
/// The smallest `challengeWindow` mainnet accepts: the watcher's usable share is ¾ of the window
/// (`challenge_due` keeps a quarter as margin), and that share must cover two finality periods
/// (a one-epoch stall still leaves a challenge in time even for an attestor on the old,
/// finalized-only scan), `C_Y` Ycash blocks for the lock-absent rule (20 × 75 s) and a
/// submission margin (600 s): ¾ W ≥ 1536 + 1500 + 600 ⇒ W ≥ 4848 s, rounded up to two hours.
pub const MAINNET_MIN_CHALLENGE_WINDOW_SECS: u64 = 2 * 60 * 60;     // 7_200
/// `finalized` not advancing for this long is a stall: three epochs (it normally moves every 6.4 min).
pub const ETH_FINALITY_STALL_SECS: u64 = 3 * 32 * 12;              // 1_152

pub fn check_challenge_window(chain_id: u64, window: u64) -> Result<()>   // Err(Error::ChallengeWindowTooShort(window)) on MAINNET
pub fn check_mint_cap(chain_id: u64, mint_cap: u128) -> Result<()>        // Err(Error::MintCapUnbounded) on MAINNET when 0
```

`BridgeInfo` gains `mint_cap: u128, cap_window: u64` (read with `EthClient::mint_limit`, `client.rs:319-323`); `check_bridge(mainnet)` calls both new checks beside `check_contract_threshold`; `startup_checks` logs `mint_cap`/`cap_window` and bails on mainnet (it already bails on `check_bridge` errors). The `MintLimitChanged` event is already ingested (`foreign/ethereum.rs:175-180`): on mainnet, a change to `mintCap = 0` raises alarm `mint-cap-unbounded` and sets the same pause as §4.3 (the quorum that did it can also unpause by setting a cap).

The P8 value may be far larger than the floor (the design doc's §4.5.3 guidance stands; the plan's mainnet row of `delay` is 24 h); the floor is the number below which Hawkeye refuses to start, not a recommendation.

### 4.3 Finality-stall alarm and pause (`engine/mod.rs`, `engine/mint.rs`)

`Memory` gains `eth_finalized_changed_at: Option<Instant>`; `scan_eth` updates it whenever `fin` differs from the previous tick's value. In `tick()`, after `scan_eth`: if `elapsed ≥ ETH_FINALITY_STALL_SECS` → alarm `eth-finality-stall` (detail: `finalized {fin} unchanged for {elapsed}s; latest {latest}`), `mem.finality_stalled = true`; cleared when `fin` advances. `signing_paused()` (`mod.rs:515-517`) becomes `(guardian_drift || finality_stalled || mint_cap_unbounded) && mainnet` — and it must be consulted by **exactly** the mint-side submitters: `propose` (`mint.rs:852`), `execute` (`:923`), the threshold-mode `mint()` submission and the `Mint` sign-once closure in `sign_mints`; **not** by `challenge`, `resubmit_challenges`, `cancel`, `heartbeat`, `releases` or slash voting. Also publish `finality_stalled` and `eth_finalized_age_secs` in `Status`/`/metrics` (`hawkeye_eth_finalized_age_seconds`).

Why pause own proposals during a stall: a stalled attestor's *own* proposal cannot be verified by peers that are also stalled, so an honest proposal would be challenged at `eta − window/4` by peers whose lock view is fine but whose proposal view (pre-fix) was blind; after §4.1 peers see it at `latest`, so the pause is belt-and-braces for mixed-version sets and for the depth-fallback case; it also stops a compromised attestor's key being used *through this daemon* while the set is blind. The pause does not stop a rogue guardian with its own tooling — only §4.1 and the cap do.

### 4.4 wyec: constructor and deploy-script floors (`contracts/WyecBridge.sol`, `script/Deploy.s.sol`, `docs/wyec-contract-design.md`)

```solidity
/// @notice Mainnet (chain id 1) floors: `threshold >= 2`, `challengeWindow >= MIN_MAINNET_CHALLENGE_WINDOW`,
///         `mintCap != 0`. Other chains are unconstrained (tests, devnets).
uint64 public constant MIN_MAINNET_CHALLENGE_WINDOW = 2 hours;
error MainnetThreshold(uint8 threshold);
error MainnetChallengeWindow(uint64 challengeWindow);
error MainnetMintCapRequired();

constructor(...) EIP712("WyecBridge", "1") {
    if (challengeWindow_ == 0) revert ZeroChallengeWindow();
    if (block.chainid == 1) {
        if (threshold_ < 2) revert MainnetThreshold(threshold_);
        if (challengeWindow_ < MIN_MAINNET_CHALLENGE_WINDOW) revert MainnetChallengeWindow(challengeWindow_);
        if (mintCap_ == 0) revert MainnetMintCapRequired();
    }
    ...
}
```

`Deploy.s.sol`: `require(block.chainid != 1 || c.challengeWindow >= 2 hours, "CHALLENGE_WINDOW must be >= 2 hours on mainnet")` and `require(block.chainid != 1 || c.mintCap > 0, "MINT_CAP is required on mainnet")` beside the existing threshold rule (`:62`); the NatSpec header (`:15-17`) says so; `MINT_CAP`'s "default 0 = no limit" line gets "(not on mainnet)". `_setMintLimit` keeps allowing `0` later (a quorum could raise the cap to 2²⁵⁶ anyway); the design doc §4.5.3 table gets the floor row and §4.5.2 "What it does not address" gets the finality paragraph (this report §1) and the Hawkeye-side rule. Hawkeye's own `eth/script/Deploy.s.sol` mirrors the two `require`s (it already mirrors the threshold one). Sizes: +~150 bytes deployed; re-measure and update §8.

EIP-712 structs do not change, so every `eip712.json` digest stays byte-identical; the stamp and the ABI/bytecode exports change (§7).

### 4.5 Developer-side vacuous pass (T-3, part)

`crates/hawkeye/tests/engine.rs:174-181` and `hawkeye-eth/tests/anvil.rs:40-46`: when `anvil` is absent and `HAWKEYE_REQUIRE_ANVIL` is unset, print `SKIPPED (anvil not on PATH)` **and** mark the test as skipped in a way `cargo test` surfaces: Rust has no skip, so emit the line to stderr and keep `return None`, but add a `tests/README.md` note and a `make test` target in the repo's `Makefile` that sets `HAWKEYE_REQUIRE_ANVIL=1` when `anvil` is on PATH; CI unchanged.

## 5. Tests

- `hawkeye-eth/src/mode.rs` unit tests: `check_challenge_window(MAINNET, 7_199)` → `Err`, `7_200` → `Ok`, any value on 31337/11155111 → `Ok`; `check_mint_cap(MAINNET, 0)` → `Err`.
- `crates/hawkeye/tests/engine.rs`:
  - `o_proposal_seen_at_latest_challenged_before_eta` (**the H-2 test**): anvil started with `--slots-in-an-epoch 32` (finalized lags 64 blocks) and `anvil_setBlockTimestampInterval 12`; deploy with `challengeWindow = 60`; a rogue proposal (`rogue-mint` drill from engine 0, or a raw `proposeMint` with guardian 0's signature over an invented lockId); engines 1–2 tick with blocks mined; assert `MintChallenged` is emitted while `finalized < proposal block` (read `finalized_block_number()` at the moment of the challenge and assert the inequality), `executeMint` after `eta` reverts `NoProposal`, and **no** `FRAUDULENT_MINT` slash case is open until the proposal's block finalizes (then one is).
  - `o2_stalled_finality_pauses_own_mints`: a test-only `StalledFinality<T: ForeignChain>` wrapper (delegates everything, pins `finalized_height()` to a constant) around `EthereumChain`; a policy-OK lock exists; after the stall threshold (`set_clock`/an injectable `Instant` source on `Memory`) `propose_mint` is never called (count on the wrapper), alarm `eth-finality-stall` is raised, `challenge` still runs for a fraudulent proposal seen at `latest`; unpinning clears the alarm and the proposal goes out on the next tick.
  - `o3_reorged_proposal_never_challenged_with_stale_id`: wrapper that returns a proposal from `scan_proposals` whose `proposal(lock_id)` no longer matches → `challenge_if_due` returns without signing (assert no `sign_once_challenge` row).
  - `o4_mint_cap_zero_refused_on_mainnet`: `startup_checks` with `params.mainnet = true` against a deployment with `mintCap = 0` → `Err` naming `MintCapUnbounded`; with `challengeWindow = 3600` → `ChallengeWindowTooShort`.
- `hawkeye-store/tests/migrations.rs`: V6 `pending_mints.provisional` column, default 0 for migrated rows.
- wyec Foundry: `test/WyecBridge.t.sol` `test_Deploy_MainnetFloors` using `vm.chainId(1)`: window `1 hours` → `MainnetChallengeWindow(3600)`, threshold 1 → `MainnetThreshold(1)`, `mintCap 0` → `MainnetMintCapRequired()`, all three satisfied → deploys; `test/Deploy.t.sol`: the script on `vm.chainId(1)` refuses the same three configs with the exact `require` strings. Existing tests (chain 31337, `WINDOW = 3600`, cap 0) unchanged.
- Hawkeye `eth/test/Deploy.t.sol`: same script checks.

## 6. Acceptance criteria

1. A proposal mined at `latest` is in `pending_mints` within one tick of its block, before its block is finalized, on both anvil fixtures (`--slots-in-an-epoch 1` and `32`).
2. The `o_…` test shows a challenge landing while the proposal's block is still unfinalized and `executeMint` failing after `eta`.
3. No slash case is opened from a provisional row.
4. On mainnet (`[network] name = "mainnet"`), `hawkeye run` refuses a bridge whose `challengeWindow < 7200` or `mintCap == 0`; the constants live in `hawkeye-eth/src/mode.rs` with the derivation comment.
5. `WyecBridge` on chain id 1 cannot be constructed with window `< 2 hours`, threshold `< 2` or cap `0`; Foundry proves each revert by selector.
6. A pinned `finalized` raises `eth-finality-stall` within `ETH_FINALITY_STALL_SECS` and suppresses own proposals and `Mint` signatures only.
7. `WyecBridge.sol`/`WrappedYcash.sol` bytes at the new pin are what `fetch-wyec.sh` verifies; `eip712.json` digests unchanged; `export-abi.sh --check` passes.

## 7. Risks and side effects

- **Contract redeploy**: the constructor change is a *new* bytecode; it does not affect any deployed bridge (none on mainnet yet; Sepolia redeploys with the runbook in plan §9 "Sepolia runbook"). Guardians re-read `MIN_MAINNET_CHALLENGE_WINDOW` as design §8 step 3 prescribes. If the owner prefers zero contract delta before the external audit (plan P5), drop §4.4's constructor part and keep the script + `check_bridge` layers; record the choice in `wyec-contract-design.md` §6.
- **Re-pin in Hawkeye**: `fetch-wyec.sh` `WYEC_COMMIT`, `eth/README.md`, `crates/hawkeye-eth/abi/*.json` (bytecode changes), `WRITE_VECTORS=true forge test --mc Eip712VectorsTest` (stamp only; see `LOW-05-T-1` which makes the stamp automatic — land T-1 first or together).
- **Bridge downtime**: none; the new scan is additive. During a mixed-version rollout, old attestors still challenge only at finality — the floor makes that safe for a one-epoch stall.
- **RPC load**: one extra `eth_getLogs` over ≤ ~70 blocks per tick with two topics; negligible on a self-hosted node, within free-tier limits on hosted providers (document in the runbook, 05/M-3).
- **Key rotation**: none.
- **NEAR adapter** (`hawkeye-near`, out of this audit's scope): must implement the two new trait methods; its optimistic head is cheap to read.

## 8. Effort estimate and dependencies

- Hawkeye scan/judging/store: 2 days. Floors + stall pause + status: 1 day. Tests (anvil epoch fixture is the fiddly part): 1.5 days. wyec contract/script/tests/doc: 0.5 day. Re-pin + ABI + vectors: 0.5 day. **Total ≈ 5.5 days.**
- Dependencies: share the V6 migration with `HIGH-05-H-1` (one migration, land in one PR or sequence H-1 → H-2 with V6 → V7). `LOW-05-T-1` (vector stamp from the pin) should land before the re-pin so the stamp cannot go stale again. `MEDIUM-05-M-4` adds its floors to the same `check_bridge`/`startup_checks` code; land after this.

## Completion record

- **Completed:** 2026-10-13T06:41Z
- **hawkeye** `upgrade/vault` merge 113d380 (branch `fix/bridge-watch`):
  - 3f251dc: `MintProposed`/`MintChallenged` are watched at `latest`. Provisional rows are confirmed or dropped at finality; store migration V7 adds `pending_mints.provisional`.
  - 3f251dc also adds the alarms `eth-finality-stall` and `mint-cap-unbounded`, each of which pauses mint signing on mainnet, and the mainnet floors in `check_bridge`.
  - 3e403ea: wyec re-pinned to f50eae6; ABI and vector stamp regenerated.
- **wyec** `upgrade/vault` merge d3d34e2:
  - 4881782: constructor floors on chain 1 (`challengeWindow` ≥ 2 h, threshold ≥ 2, `mintCap` ≠ 0) and the deploy-script floors.
  - b2f50e7: floor tests; design-doc finality paragraph.
- **Tests:** engine 32/32 (o1–o5, r, r2 new), store migrations 12, hawkeye-eth anvil 7; wyec 98/98. All seven §6 criteria met on anvil.
- **Choice:** a provisional proposal does not move the lock to PROPOSED. Moving it early made an honest challenge look like griefing once the L-4 rule was in.
- **Open (owner):** keep the constructor floors before the external audit (P5)? P8 mainnet values via yb-calibration. The NEAR adapter has no window/cap floors yet (follow-up).
- **Push order:** wyec before hawkeye (the pin f50eae6 must exist on GitHub).
