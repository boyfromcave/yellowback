# INFO — W3-B-12, W3-B-13, 05/N-4 (05/N-3 closed) — Contract observations (boundary burst, a retired bridge still takes proposals, zero-amount mint), test fidelity (node-vector pin, anvil skip), the replay cache across a restart

Repos / branches to change: `wyec` (`fix/W3-B-12-contract-notes` off `upgrade/vault`: `contracts/WyecBridge.sol`, `test/`, `docs/wyec-contract-design.md`) — ride the same release as `MEDIUM-W3-B-3`, `LOW-W3-B-7`, `LOW-W3-B-8-B-9`; `hawkeye` (`fix/W3-B-13-test-fidelity` off `upgrade/vault`: `.github/workflows/ci.yml`, new `tools/fetch-node-vectors.sh`, `crates/hawkeye-core/tests/vault_vectors.rs`, `engine/mod.rs`, `README.md`, `docs/operations.md`). N-4 is implemented by `LOW-W3-B-6` (same function). No node change. · Audit source: `docs/audits/quantum-vault-ecosystem-wave3/05-bridge-hawkeye-wyec.md` §W3-B-12 (`:251-262`), §W3-B-13 and "Test fidelity" (`:266-297`); `docs/audits/quantum-vault-ecosystem-wave3/verification/05-verification.md` §W3-B-12 (`:240-246`), §W3-B-13 (`:248-257`), "Hostile second look" (`:261-280`), N-3 (`:313-316`), N-4 (`:318-324`); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row "W3-B-4..13, 05/N-1..N-4"; `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` status rows W3-B-12 (`:61`, STILL OPEN), W3-B-13 (`:62`, "CHANGED, worse in scope"), 05/N-3 (`:65`, **FIXED** in `900205a`), 05/N-4 (`:66`, STILL OPEN), stale-report note (`:78-80`: "§4.5 implemented differently by `900205a`; drop it"); `docs/audits/quantum-vault-ecosystem-wave4/verification/02-verification.md` rows 05/N-3 (`:37`, confirmed fixed) and W3-B-13 (`:40`, **PARTIALLY**: the engine-suite gate is not new), V-N4 (`:212`); `docs/audits/quantum-vault-ecosystem-wave4/04-clients-wyec-recheck.md` (wyec unchanged at `dfd51cb`). · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13). · Status: pending

None of these is a vulnerability at the audited commits; each is a small hardening, a documentation obligation, or a test that would catch a future regression. Grouped as one INFO report; the wyec items should not cost a separate redeploy.

**Changes at this re-verification.** (1) **05/N-3 is closed** and removed from this report (its old §4.5): `900205a` ("never sign a second unlock for a burn while one this member signed could still confirm") made every row — leader or co-signer — survive a fee-input spend (`crates/hawkeye/src/engine/burn.rs:186-200`, `:298-332`: a lost or foreign fee input yields `Resend { refund: true }`, never `Dead`; `Dead` only on a spend of the **vault** `C_Y` deep or its own intent's cancel, `:266-288`), a takeover leader adopts and re-sends the co-signed build (`:410-431`), and co-signers merge their existing signature into a re-funded copy (`merge_own_signature`, `:1585-1636`; tests `k3_revived_cosigned_unlock_pays_the_burn_once`, `k9_takeover_at_unlock_threshold_two_resends_the_cosigned_unlock`, `k10_cosigner_merges_its_signature_into_a_refunded_unlock`, `tests/engine.rs:2245`, `:2468`, `:2567`). Nothing further is needed. (2) **W3-B-13 wording corrected** (wave-4 verifier, V-N4): the anvil gate hiding the *engine* suite is not new — at `b0f085f` the same `on_path("anvil")` gate already covered it (46 tests then, 72 now); only the count grew; CI and `make test` enforce anvil, so CI is sound. (3) **W3-B-13 (c) was already covered at both commits**: `k1_signing_routes_authenticated_and_inert_at_threshold_one` sends a replayed and a stale request end to end and asserts `401 replayed` / `401 stale` (`tests/engine.rs:2037-2079`; `:2011-2053` at `b0f085f`), so that item is dropped here and in `LOW-W3-B-6`. (4) V-N4's probe-helper hazard (`unlocks_for` reads the mempool only) is fixed in `INFO-W4-B-6-B-7-hawkeye-restore-false-positive-operator-drift`.

## 1. Finding

**W3-B-12 (wyec).** (a) The rate limit uses fixed windows (`_mint`, `contracts/WyecBridge.sol:441-449`): `mintCap` at the end of window *w* and again at the start of *w + 1* admits `2 × mintCap` in two adjacent blocks; tested and accepted (`test/RateLimit.t.sol:103` `test_FixedWindows_BoundaryBurst`). (b) After `setBridge` the old bridge still accepts `proposeMint` and `challengeMint` (no `token.bridge() == address(this)` guard); only `executeMint`/`mint` revert, in the token (`WrappedYcash.sol:58-60`). A watcher still pointed at the old deployment sees live-looking proposals. (c) `mint` (`:252-257`) has no `ZeroAmount` check (only `proposeMint`, `:273`), so a threshold `mint(lockId, 0, to, sigs)` consumes a `lockId` with no tokens; `burn(0, r)` consumes a burn nonce (Hawkeye orphans it, `engine/mint.rs:247-259`, tested). (d) `challengeMint` (`:293-301`) has no `eta` check: a challenge after `eta` but before `executeMint` still deletes the proposal — safe (favours the challenger) and consistent with the plan.

**W3-B-13 (test fidelity).** (a) `hawkeye-eth/tests/anvil.rs` (`:39-50`) and the whole engine suite (`crates/hawkeye/tests/engine.rs`, `setup_with` `:201-212`: all 72 `#[tokio::test]`s, every security test of the signing engine) return early without `anvil`: they print `SKIPPED` to stderr but cargo reports `ok`; CI and `make test` set `HAWKEYE_REQUIRE_ANVIL=1` (`.github/workflows/ci.yml:97-110`, `Makefile:5-19`), so the vacuous pass is local only (and was already so at `b0f085f`). (b) `crates/hawkeye-core/tests/data/vault_vectors.json` is stamped by **comment** only (`tests/vault_vectors.rs:1-3`: ycash-dd `8af82551b` = ycash6 `047b561ac`); no CI step compares it with the node trees. At this re-verification it is byte-identical to `src/test/data/vault_vectors.json` at ycash-dd `da5e0fe` and ycash6 `0742e43` (`cmp`), so the stamp is stale but the content is not. (c) Dropped (see above: covered end to end by `k1`). (d) The Foundry suites were reviewed, not run, in the audit environment (CI runs them: `ci.yml:189-232`).

**05/N-4 (restart window).** The replay cache is process memory (`crates/hawkeye/src/peer_auth.rs:80`, `admit_once` `:105-113`): a captured request younger than `SKEW_SECS` (60 s) can be replayed once within that window after a restart. Each handler is idempotent through its sign-once record (`verify_and_sign` answers a repeated act from `slash_votes_given`, `slash.rs:532-541`; unlock/cancel co-signs through `sign_once_*`; the three routes added since — `/burns/unlock`, `/vaults/orphaned`, `/members/gone`, `api.rs:36-38` — are reads, rate-capped reports and an idempotent declaration that re-records the same key with a fresh height, `burn.rs:1187-1196`), so the effect is a repeated read, not a second signature.

## 2. Root cause

- `wyec/contracts/WyecBridge.sol:441-449` (fixed windows by design, E-6), `:266-285` and `:293-301` (no retirement state), `:252-257` (no zero check in `mint`), `:341-345` (`burn` accepts 0).
- `hawkeye/.github/workflows/ci.yml` (`:97-110` Rust tests, `:189-232` forge) — no node-vector fetch; `crates/hawkeye-core/tests/vault_vectors.rs:1-3` — prose stamp.
- `hawkeye/crates/hawkeye/src/peer_auth.rs:80`, `:105-113` — in-memory cache, no process-start floor.

## 3. Fix options considered

| Item | Option | Verdict |
|---|---|---|
| B-12 (a) | Sliding-window or token-bucket rate limit | Rejected: more storage and gas per mint for a factor-2 edge the set can size around; document instead (design §4.5.4, runbook §8: "the worst case is `2 × mintCap` across a window edge"). The deployment's `mintCap` is set as half the tolerated burst (an owner value at deployment; yb-calibration has no bridge study, `MEDIUM-W4-K-3-…` §4 step 2). |
| B-12 (b) | A `retired` flag set by `setBridge`; `proposeMint` and `mint` revert `BridgeRetired()` | **Chosen**: one cold `SLOAD` per proposal/mint; `challengeMint` stays allowed (harmless, and lets watchers clean up). Alternative `token.bridge() == this` costs a `STATICCALL`; equivalent. |
| B-12 (b) | Hawkeye alarm when its configured bridge is retired | **Chosen** (`deployment-retired`, page): the operator forgot step 4 of the migration. |
| B-12 (c) | `ZeroAmount` in `mint` and `burn` | **Chosen** for `mint` (symmetry with `proposeMint`; Hawkeye never signs a zero mint, `MIN_LOCK > 0`); for `burn`, recommended (a zero burn is noise that Hawkeye must orphan) — reviewers may keep today's behaviour, it is tested either way. |
| B-12 (d) | `eta` check in `challengeMint` | Rejected: a late challenge only ever helps; document in design §4.5.1. |
| B-13 (b) | CI fetches the node's `vault_vectors.json` at pinned commits and `cmp`s, and the stamp becomes machine-readable | **Chosen** (the `fetch-wyec.sh` pattern). |
| B-13 (c) | End-to-end stale/replay tests | **Not needed**: `k1` already covers them (`tests/engine.rs:2037-2079`); `LOW-W3-B-6` §5 adds only the cases its own change creates (non-member never cached, the process-start floor). |
| N-4 | Persist the cache | Rejected; a process-start floor on `X-Hawkeye-Time` (in `LOW-W3-B-6` §4.3) closes the window with no I/O. |

## 4. Recommended fix

### 4.1 wyec (`contracts/WyecBridge.sol`, same release as the other W3 contract reports)

```solidity
/// @notice True once `setBridge` handed the token to a successor: no new proposals or mints here.
bool public retired;
error BridgeRetired();

// setBridge: after the checks, before token.setBridge(newBridge):
retired = true;
// proposeMint and mint, first line:
if (retired) revert BridgeRetired();
// mint: after the consumed check
if (amount == 0) revert ZeroAmount();
// burn (recommended):
if (amount == 0) revert ZeroAmount();
```

Design doc: §4.5.4 the boundary burst and its sizing rule; §4.5.1 the late-challenge note; §4.6 "after `setBridge` the old bridge refuses `proposeMint` and `mint` (`BridgeRetired`)".

### 4.2 Hawkeye: retired deployment (`engine/mod.rs`)

Every 20 ticks (with `check_gas`, `engine/mod.rs:587-610`), read `token().bridge()` for the configured bridge; if it differs, raise page alarm `deployment-retired` ("the bridge <addr> handed the token to <new>; switch `[eth] deployment` (operations §7 step 4)") and pause own mint-side acts (a new `mem.deployment_retired` flag ORed into `mint_paused`, `engine/mod.rs:789-794`). Row in `docs/operations.md` §9 (alarm-table test).

### 4.3 Hawkeye: node-vector pin in CI (W3-B-13 b)

- `tools/fetch-node-vectors.sh` with `YCASH_DD_COMMIT=` and `YCASH6_COMMIT=` lines (re-stamp to the commits current when this lands — at this re-verification ycash-dd `da5e0fe` and ycash6 `0742e43` carry an identical file —, and update the comment in `tests/vault_vectors.rs:1-3` with them), fetching `src/test/data/vault_vectors.json` from both node repositories at those commits (`git fetch --depth 1 <url> <commit>` + `git show`, as `eth/tools/fetch-wyec.sh` does for wyec) and `cmp`-ing each with `crates/hawkeye-core/tests/data/vault_vectors.json`; a CI job runs it (network required, like the forge job).
- `tests/vault_vectors.rs`: a test that the comment's commits equal the script's constants (the `wyecCommit` stamp check of `LOW-05-T-1` is the model), so a re-sync without updating the pin fails.
- Extend to `pq_vectors.json` if Hawkeye ever vendors it (it does not today).

### 4.4 Hawkeye: anvil skip (W3-B-13 a)

No code change needed beyond what exists; add one line to `README.md` "Build and try it": "`cargo test` without `anvil` passes the engine suite (`crates/hawkeye/tests/engine.rs`) and the Ethereum integration tests (`crates/hawkeye-eth/tests/anvil.rs`) vacuously (they print SKIPPED); use `make test`" (**owned by `INFO-W4-B-6-B-7-hawkeye-restore-false-positive-operator-drift.md` §4 item 5**; do not add it from this report — only the optional count guard below is this report's). Optional: `eth/tools/check-test-counts.sh` already guards Foundry counts; mirror it for the Rust anvil-backed suites in CI (assert that no test printed `SKIPPED` and that the number of engine tests run is ≥ the known count, 72 at `f4436df`).

### 4.5 Replay cache across a restart (05/N-4)

Implemented in `LOW-W3-B-6` §4.3 (`started_at` floor). Nothing further here.

## 5. Tests

- wyec: `test/Successor.t.sol` `test_RetiredBridge_RefusesProposeAndMint` (after `setBridge`: `proposeMint` and `mint` revert `BridgeRetired()`, `challengeMint` of a pre-existing proposal still works); `test/OptimisticMint.t.sol` `test_Mint_ZeroAmountRejected` (`ZeroAmount()`), `test_Burn_ZeroAmountRejected` (if adopted; then update Hawkeye's zero-burn orphan test to expect the revert on new deployments); `test_FixedWindows_BoundaryBurst` unchanged (documented).
- Hawkeye: `crates/hawkeye-eth/tests/anvil.rs` `anvil_retired_bridge_alarm` (deploy, migrate with `setBridge`, keep the engine on the old file → `deployment-retired` raised, own mint-side acts paused); CI job `node-vectors` green (and failing on a one-byte change to Hawkeye's copy); with anvil (`HAWKEYE_REQUIRE_ANVIL=1`), `anvil_retired_bridge_alarm` fails at `f4436df` (no alarm, own mint-side acts not paused).
- `tests/alarm_table.rs` with `deployment-retired`.

## 6. Acceptance criteria

1. A retired bridge refuses new proposals and mints; Hawkeye pages when its configured bridge is retired.
2. `mint` (and, if adopted, `burn`) refuses a zero amount.
3. CI fails if Hawkeye's copy of `vault_vectors.json` differs from either node line at the pinned commits.
4. Design doc and runbook carry the boundary-burst sizing rule and the late-challenge note.

## 7. Risks and side effects

- **Redeploy:** the wyec items change bytecode; bundle with the other W3 contract reports (one redeploy, one Hawkeye re-pin, one vector re-stamp). No persistent deployment exists; mainnet is not deployed.
- **CI network dependency:** the node-vector job fetches two repositories; mark it required on `upgrade/vault` like the forge job, so a fetch failure is visible rather than skipped.
- **Bridge downtime / key rotation:** none.

## 8. Effort estimate and dependencies

wyec 0.5 day (inside the shared release); Hawkeye 1 day (alarm 0.25, CI vector pin 0.5, README and count guard 0.25). Depends on `LOW-W3-B-6-hawkeye-peer-auth-replay-cache-before-membership` for N-4; ship the wyec part with `MEDIUM-W3-B-3`, `LOW-W3-B-7`, `LOW-W3-B-8-B-9`. **Single re-pin owner:** the one Hawkeye re-pin of the bundled wyec release (`eth/tools/fetch-wyec.sh` `WYEC_COMMIT`, the regenerated `eth/vectors/eip712.json` with its new `wyecCommit` stamp and negatives) is owned by `LOW-W3-B-8-B-9-wyec-runtime-floors-admin-deadline.md` §4.3 step 5, the only report that changes type strings; the Hawkeye branches of MEDIUM-W3-B-3, LOW-W3-B-7 and INFO-W3-B-12 stack on it and add only their own vector cases and bindings use.
