# MEDIUM — W3-B-3 — A rogue guardian can open unlimited optimistic proposals on fresh `lockId`s; every one costs the watchers a challenge, and a burst can outrun them

Repos / branches to change: `wyec` (`fix/W3-B-3-proposal-cap` off `upgrade/vault`: `contracts/WyecBridge.sol`, `script/Deploy.s.sol`, `test/`, `docs/wyec-contract-design.md` §4.5); `hawkeye` (`fix/W3-B-3-challenge-throughput` off `upgrade/vault`: `engine/mint.rs`, `engine/mod.rs`, `hawkeye-eth` client/bindings/deploy, `eth/` pin and deploy script, `docs/operations.md`, plan §5.3 / §10). No node change. · Audit source: `docs/audits/quantum-vault-ecosystem-wave3/05-bridge-hawkeye-wyec.md` §W3-B-3 (`:125-142`); `docs/audits/quantum-vault-ecosystem-wave3/verification/05-verification.md` §W3-B-3 (`:166-178`); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row W3-B-3, priority 4 ("bound proposal spam per guardian"); `docs/audits/quantum-vault-ecosystem-wave4/04-clients-wyec-recheck.md` status row W3-B-3 (`:61`) (**STILL OPEN**; wyec has had no commit since `dfd51cb`); `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` status row W3-B-3 (`:52`). · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13): every wyec line and every Hawkeye line in `engine/mint.rs` and `hawkeye-eth` is unchanged since wave 3; `engine/mod.rs` and the runbook moved (cited at `f4436df`). · Status: done — completed 2026-10-16 (merged on `upgrade/vault`; see the completion record). Previously pending

## 1. Finding

`proposeMint` (`wyec/contracts/WyecBridge.sol:266-285`) accepts any opaque `lockId` that is not consumed, on one current guardian's `Mint` signature, submittable by anyone. The only per-proposer state is `vetoed[lockId][proposer]` (`:278`, set by `challengeMint` at `:298`), which bars that proposer from **that** `lockId` only; there is no counter, no bond and no limit on live proposals per proposer. Every proposal must be challenged (`challengeMint`, `:293-301`: one guardian signature, one transaction) before its `eta` or anyone can `executeMint` it for up to the window's `mintCap` (`:307-320`, `_mint` `:436-450`). A single compromised guardian key can therefore post thousands of proposals for invented `lockId`s; each watcher (Hawkeye, `engine/mint.rs:487-522` `challenge_if_due`, `:820-865` `challenge`, `:869-905` `submit_challenge`) pays one challenge transaction per proposal while the attacker pays one proposal each. The gas account (`[eth] sender_keystore`) drains at the attacker's pace; `gas-low` is a ticket (`docs/operations.md:255`). The only stops are a threshold `setPaused(true)` (which blocks `proposeMint` and `executeMint`, not `challengeMint`) and emergency rotation (`setGuardians` voids the rogue's proposals), both human-speed admin rounds.

Re-verification adds a throughput dimension the audit did not quantify. Hawkeye sends one Ethereum transaction at a time per account and waits for its receipt (`hawkeye-eth/src/client.rs:554-574`, `send`; "Hawkeye sends one transaction at a time per account", `:580-583`), and every attestor challenges every undecided proposal in the same order with no partition (`challenge_if_due` has no leader rule), so the **set's** challenge throughput is about one distinct proposal per Ethereum block, not one per attestor. A proposal for an absent lock becomes due `C_Y` Ycash blocks after it is first judged (≈ 25 min at the floor) or at the last quarter of the window (`challenge_due`, `mint.rs:102-113`); with the mainnet floor `challengeWindow = 2 h` that leaves roughly 400–475 block slots per window. A burst larger than that (one block can carry many `proposeMint` transactions from many funded senders, each with the rogue's signature over a different `lockId`) leaves proposals unchallenged at `eta`; each then executes for its amount until `mintCap` for the window is used, and the rest wait for the next window. Loss: up to `mintCap` of unbacked wYEC per window until the set pauses. This path was derived by reading and must be reproduced on anvil (§5); the verifier's Medium (a griefing race bounded by pause and rotation) stands, with the burst as the reason to fix it in the contract rather than in operations only.

## 2. Root cause

- `wyec/contracts/WyecBridge.sol:266-285` — `proposeMint`: no per-proposer bound; `:278` the per-lock veto is the only proposer state.
- `wyec/contracts/WyecBridge.sol:293-301` — `challengeMint`: one proposal per transaction.
- `wyec/contracts/WyecBridge.sol:215-235` — the constructor's mainnet floors bound `threshold`, `challengeWindow`, `mintCap`, nothing about proposals.
- `hawkeye/crates/hawkeye-eth/src/client.rs:554-574` — serial send-and-wait per account.
- `hawkeye/crates/hawkeye/src/engine/mint.rs:102-113, 487-522, 820-905` — every attestor challenges every due proposal; no partition, no batching.
- `hawkeye/crates/hawkeye/src/engine/mod.rs:585-610` (`check_gas`) — `gas-low` is a fixed-severity ticket; nothing escalates on an attack.

## 3. Fix options considered

| Option | Where | Verdict |
|---|---|---|
| (a) Per-proposer cap on **open** proposals (counter incremented on propose, decremented when a proposal leaves) | contract | **Chosen.** Bounds a rogue key's burst to `maxOpenProposals` per key at any instant, so the set never needs more than `maxOpenProposals × |rogue keys|` challenges in flight; one storage counter, no ETH custody, no new trust. Honest proposers at the cap fall back to the threshold path (already automated, `[bridge] fallback_to_threshold`, LOW-05-L-4). |
| (b) A batch `challengeMints(...)` | contract | **Chosen.** Raises the set's throughput from one challenge per block to as many as fit in one transaction's gas; each entry is still a sign-once `Challenge(lockId, proposalId)` signature. Skips entries already gone so racing watchers do not revert each other. |
| (c) Per-proposal ETH bond forfeited to the challenger | contract | Rejected for now: puts ETH custody in a contract that holds none (design §4: "guardian keys need hold no ETH"); a rogue *challenger* can make honest proposers forfeit bonds (the LOW-05-L-4 veto, now with a price); needs refund paths on void/override. Recorded as a v2 option. |
| (d) Strike counter: after `k` challenged proposals a proposer is barred from proposing at all | contract | Rejected: a rogue challenger could bar every honest proposer globally by challenging `k` of each one's honest proposals (today it can only veto per lock). |
| (e) Contract auto-pause after `k` challenges in a window | contract | Rejected: the same rogue challenger turns it into a one-key bridge shutdown; unpausing needs a threshold round. |
| (f) Off-chain: partition challenges (one owner per proposal first, everyone in the last quarter), batch submission, escalate `gas-low` and add a `rogue-proposer` page, runbook "pause at once" | Hawkeye + runbook | **Chosen**, needed with or without (a)/(b): partitioning alone turns N× gas into ≈ 1× in the normal case. |
| (g) Off-chain only (no contract change) | — | Rejected as the whole fix: it cannot bound the burst; the contract is not yet deployed on mainnet, so the change costs no migration now. |

## 4. Recommended fix

### 4.1 wyec: open-proposal cap (`contracts/WyecBridge.sol`)

```solidity
/// @notice The most proposals one proposer may have open at once (W3-B-3); 0 = no limit (not on
///         mainnet). A proposal is open from `proposeMint` until it is executed, challenged,
///         overridden by `mint`, or replaced after its proposer was rotated out.
uint256 public immutable maxOpenProposals;
/// @notice Open proposals per proposer.
mapping(address proposer => uint256) public openProposals;

error TooManyOpenProposals(address proposer, uint256 open);
error MainnetOpenProposalCapRequired();
```

- Constructor: new parameter `uint256 maxOpenProposals_` (after `capWindow_`); on `block.chainid == 1`, `maxOpenProposals_ == 0` reverts `MainnetOpenProposalCapRequired()`.
- `proposeMint` (`:266-285`), after the `vetoed` check:
  ```solidity
  if (p.id != 0) openProposals[p.proposer] -= 1;          // replacing a void proposal
  uint256 open = openProposals[signer];
  if (maxOpenProposals != 0 && open >= maxOpenProposals) revert TooManyOpenProposals(signer, open);
  openProposals[signer] = open + 1;
  ```
- `challengeMint` (`:293-301`), `executeMint` (`:307-320`) and `mint` (`:252-257`, when it clears a proposal): `openProposals[proposals[lockId].proposer] -= 1` before the `delete`. Factor the three into `_closeProposal(bytes32 lockId)`.
- Invariant (document in NatSpec, prove in an invariant test): `openProposals[a] == #{lockId : proposals[lockId].id != 0 && proposals[lockId].proposer == a}`.

Sizing: honest need per member ≈ (locks per `challengeWindow`) / |live| plus re-proposals after griefing; the mainnet value is an **owner decision at deployment** (start from 32), recorded in design §4.5.3 and the deployment checklist — yb-calibration has no bridge study (`MEDIUM-W4-K-3-…` §4 step 2: bridge parameters are out of its scope unless one is added), so no report calibrates it. Hawkeye reads `maxOpenProposals()` / `openProposals(me)` and treats `TooManyOpenProposals` like a veto: threshold fallback (`mint.rs:1437` region, where `ProposalPending`/`LockConsumed` are handled).

### 4.2 wyec: batch challenge

```solidity
/// @notice `challengeMint` for many proposals in one transaction. An entry whose proposal is no
///         longer `proposalIds[i]` (already challenged, executed or overridden) is skipped, so
///         racing watchers do not revert each other; a signature that recovers to a non-guardian
///         reverts the whole call. Callable by anyone, also while paused.
/// @return challenged how many proposals this call deleted
function challengeMints(bytes32[] calldata lockIds, uint256[] calldata proposalIds, bytes[] calldata sigs)
    external returns (uint256 challenged);
```

Same EIP-712 `Challenge(bytes32 lockId,uint256 proposalId)` struct (no new type hash, no new vectors beyond a batch case); `challengeMint` becomes a one-element call of the shared internal `_challenge(lockId, proposalId, sig) returns (bool)`. Lengths must match (`BadBatch()`).

### 4.3 wyec: deploy script and design doc

`script/Deploy.s.sol`: `MAX_OPEN_PROPOSALS` env (required on chain 1), passed to the constructor and written to the deployment JSON as `maxOpenProposals`. `docs/wyec-contract-design.md` §4.5.2 (threats) adds "a rogue proposer's burst", §4.5.3 (parameters) the cap and its floor, §4.5.5 (cost) the counter's gas.

### 4.4 Hawkeye: partitioned, batched challenges (`engine/mint.rs`)

1. **Challenge owner.** For each due proposal, `owner = mint_leader_for(lockId, live, …)` (`hawkeye-core/src/leader.rs:55`), the same rule as the mint leader. The owner challenges as soon as `challenge_due` says so (definite mismatches at once, as today). A non-owner challenges only in the last quarter of the window (`now + window/4 ≥ eta`) or when the owner is not live. Safety is unchanged (every honest attestor still challenges before `eta`); the normal-case gas falls from N× to ≈ 1×.
2. **Batching.** Collect every challenge due in a tick (each signed once through `sign_once_challenge`, `submit_challenge` `:869-905`, unchanged), and when the bound contract has `challengeMints` submit them in chunks of `[eth] challenge_batch` (default 64; bounded by a gas estimate under the block gas limit). Feature detection: the binding at the pinned commit (`hawkeye-eth/src/bindings.rs`) plus a `maxOpenProposals` field in the deployment file (`hawkeye-eth/src/deploy.rs:18`); an older deployment keeps single challenges.
3. **Backlog alarm.** Gauge `hawkeye_challenge_backlog` (due, not yet mined) and page alarm `challenge-backlog` when the earliest `eta` in the backlog is within `window/4` — proposals may escape; pause now.

### 4.5 Hawkeye: escalation (`engine/mint.rs` `fraudulent_mint` `:740-780`, `engine/mod.rs` `check_gas` `:585-610`)

- New page alarm `rogue-proposer`: two or more proposals with no lock from one proposer within 24 h, or any proposal over `maxOpenProposals / 2` from one proposer; text `"proposer <addr> (member <key>) opened <n> proposals with no lock: have the set pause the bridge now, then rotate it out (operations §7, emergency rotation)"`; gauge `hawkeye_fraudulent_proposals_open{proposer}`.
- New page alarm `gas-low-under-attack`: `gas-low`'s condition while `fraudulent-mint`, `rogue-proposer` or `challenge-backlog` is raised (a separate name keeps the alarm table's fixed severities; `tests/alarm_table.rs`).
- Every `fraudulent-mint` slash case against one proposer is grouped by the existing case key; no change.

### 4.6 Runbook and plan

- `docs/operations.md` §7 emergency rotation: on `rogue-proposer` or `challenge-backlog`, the set signs `setPaused(true)` **first** (it stops `proposeMint` and `executeMint`; challenges continue while paused, wyec `test_Pause_BlocksProposeAndExecuteNotChallenge`), then the rotation. Optional "break-glass" practice: each attestor keeps a `SetPaused(true)` signature at the current `adminNonce` off-host, re-signed after every admin act (with `LOW-W3-B-8-B-9`'s deadline, re-signed before it lapses).
- §9 alarm rows for `rogue-proposer`, `gas-low-under-attack`, `challenge-backlog`; §8 parameter row `contract maxOpenProposals` (`> 0` on mainnet; `hawkeye status --params` shows it against the floor; `hawkeye-eth/src/mode.rs` gains `check_max_open_proposals`, refused at start on mainnet like `check_mint_cap`).
- Plan §5.3 step 2: the challenge owner and batching; §10: record the wyec change as CR-W6 (done when merged), with CR-W5 still open.

## 5. Tests

wyec (Foundry; exact selectors as `LOW-05-T-1` requires):
- `test/ProposalCap.t.sol`: `test_Propose_OpenCapPerProposer` (cap 2: the third reverts `TooManyOpenProposals(signer, 2)`; after one challenge the proposer can propose again); `test_OpenCount_ExecuteChallengeMintAndVoidReplace` (each exit path decrements exactly once; a void proposal replaced by another guardian decrements the rotated-out proposer); `test_Constructor_MainnetRequiresOpenCap` (`vm.chainId(1)`, cap 0 reverts `MainnetOpenProposalCapRequired()`); `invariant_OpenCountMatchesProposals` (handler fuzzing propose/challenge/execute/mint/setGuardians).
- `test/OptimisticMint.t.sol`: `test_ChallengeMints_DeletesManyAndSkipsGone`, `test_ChallengeMints_NonGuardianReverts`, `test_ChallengeMints_LengthMismatchReverts`, `test_ChallengeMints_WorksWhilePaused`; `forge snapshot` comparing 50 single challenges with one batch of 50 (recorded in the design doc §4.5.5).
- `test/Deploy.t.sol`: the new env var and JSON field; mainnet refusal.

Hawkeye:
- `crates/hawkeye-eth/tests/anvil.rs` `anvil_rogue_proposer_burst_is_capped` (the test that would have caught it): deploy with `maxOpenProposals = 4`; a guardian key proposes 10 invented `lockId`s → the fifth reverts `TooManyOpenProposals`; three engines challenge the four; count `challengeMint`/`challengeMints` transactions per sender: only the owner sends before the last quarter. A companion `anvil_burst_outruns_serial_challenges` at `maxOpenProposals = 0` with a short window demonstrates the escape at `f4436df` behaviour (marked as the regression record; asserts that with batching enabled no proposal reaches `eta`).
- `crates/hawkeye/tests/engine.rs` (anvil-backed; CI's `HAWKEYE_REQUIRE_ANVIL=1` keeps them from passing vacuously): `challenge_owner_partition` (non-owner waits until the last quarter; owner not live → everyone at once); `rogue_proposer_alarm_raised_and_cleared`; `too_many_open_proposals_falls_back_to_threshold`.
- `crates/hawkeye-eth/tests/vectors.rs` and `eth/vectors/eip712.json`: re-stamp `wyecCommit` to the new pin (`eth/tools/fetch-wyec.sh` `WYEC_COMMIT`); add one batch-challenge digest case (digests are per entry and unchanged).
- `tests/alarm_table.rs` with the three new rows.
- Devnet: `hawkeye-devnet scenario rogue-mint --count 12` on both node lines.

## 6. Acceptance criteria

1. On a deployment with `maxOpenProposals = m`, one guardian key can never have more than `m` proposals open; the invariant test holds under fuzzing.
2. A burst of proposals larger than one-per-block for a window is fully challenged before `eta` on anvil with three Hawkeyes (batching), and in the normal case only the challenge owner pays gas before the last quarter.
3. `rogue-proposer`, `challenge-backlog` and `gas-low-under-attack` page; the runbook says "pause first".
4. Mainnet deploys refuse `maxOpenProposals = 0` (contract and `hawkeye status --params` / start-up floor).
5. Hawkeye re-pinned to the new wyec commit; CI's pin and vector-stamp checks pass.

## 7. Risks and side effects

- **Redeploy.** `WyecBridge` is immutable (no proxy). No deployment is committed anywhere (`hawkeye/eth/deployments/` and `wyec/deployments/` are empty) and mainnet is not deployed, so the change lands before the first mainnet deployment at no migration cost. A Sepolia or devnet deployment is replaced by a fresh one (or migrated with `setBridge` per design §4.6; note `LOW-W3-B-7` for that path). Bundle this with `LOW-W3-B-7`, `LOW-W3-B-8-B-9` and the `INFO-W3-B-12…` contract items into **one** wyec release and one Hawkeye re-pin.
- **Honest throughput.** An honest proposer at the cap is served by the threshold path (more signatures, one transaction); size `m` from calibration so that this is rare.
- **Constructor ABI change.** Every deploy script (wyec's and Hawkeye's `eth/script/Deploy.s.sol`) and the deployment-file reader change together; an old deployment file (no `maxOpenProposals`) is read as "no cap, no batch" and refused on mainnet.
- **Key rotation:** none. **Bridge downtime:** none beyond the redeploy window on test networks.
- **NEAR bridge** (`wyec-near`, `hawkeye-near`) is out of this audit's scope but has the same optimistic shape; raise the same change there as a separate item.

## 8. Effort estimate and dependencies

wyec 2 days (contract, tests, script, design doc); Hawkeye 3 days (partition, batching, alarms, anvil tests, re-pin, runbook). Depends on nothing; coordinate the single wyec release with `LOW-W3-B-7-wyec-setbridge-successor-wiring`, `LOW-W3-B-8-B-9-wyec-runtime-floors-admin-deadline` and the wyec items of `INFO-W3-B-12-B-13-05-N-4-bridge-contract-notes-test-fidelity` (one redeploy, one re-pin, one vector re-stamp). **Single re-pin owner:** the one Hawkeye re-pin of the bundled wyec release (`eth/tools/fetch-wyec.sh` `WYEC_COMMIT`, the regenerated `eth/vectors/eip712.json` with its new `wyecCommit` stamp and negatives) is owned by `LOW-W3-B-8-B-9-wyec-runtime-floors-admin-deadline.md` §4.3 step 5, the only report that changes type strings; the Hawkeye branches of MEDIUM-W3-B-3, LOW-W3-B-7 and INFO-W3-B-12 stack on it and add only their own vector cases and bindings use.

## Completion record

- **Completed:** 2026-10-15
- **Merged:** wyec `#3` `e9ea41a`. `WyecBridge` takes an immutable `maxOpenProposals` and counts each proposer's open proposals. Mainnet requires a non-zero cap. `forge test` was 107 passed.
- **Not closed by this landing:** batch `challengeMints`, Hawkeye partitioning and alarms, and the Hawkeye re-pin. That re-pin is still owned by `LOW-W3-B-8-B-9`, which stays pending. The mainnet value of `maxOpenProposals` is still an owner choice (the report suggests 32).
