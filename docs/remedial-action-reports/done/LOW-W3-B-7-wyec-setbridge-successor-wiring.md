# LOW — W3-B-7 — `setBridge` does not check that the successor reads this bridge as its predecessor

Repos / branches to change: `wyec` (`fix/W3-B-7-successor-wiring` off `upgrade/vault`: `contracts/WyecBridge.sol`, `script/Deploy.s.sol`, `test/Successor.t.sol`, `test/Deploy.t.sol`, `docs/wyec-contract-design.md` §4.6); `hawkeye` (`fix/W3-B-7-successor-check` off `upgrade/vault`: `cli.rs` `status --params`, `hawkeye-eth` bindings, `eth/script/Deploy.s.sol`, `eth/tools/fetch-wyec.sh` re-pin, `docs/operations.md` §7). No node change. · Audit source: `docs/audits/quantum-vault-ecosystem-wave3/05-bridge-hawkeye-wyec.md` §W3-B-7 (`:186-201`); `docs/audits/quantum-vault-ecosystem-wave3/verification/05-verification.md` §W3-B-7 (`:207-214`); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row "W3-B-4..13, 05/N-1..N-4"; `docs/audits/quantum-vault-ecosystem-wave4/04-clients-wyec-recheck.md` status row W3-B-7 (`:62`) (**STILL OPEN**; wyec has had no commit since `dfd51cb`); `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` status row W3-B-7 (`:56`). Follows `done/LOW-05-L-3-wyec-setbridge-successor-consumed.md` (which introduced `predecessor`). · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13): wyec unchanged; in Hawkeye only `cli.rs` moved (`status_params` now `:283-398`). · Status: done — completed 2026-10-16 (merged on `upgrade/vault`; see the completion record). Previously pending

## 1. Finding

Since wyec `28e806e` a successor bridge reads its predecessor's consumed `lockId`s through the immutable `predecessor` (`contracts/WyecBridge.sol:120-125`, `isConsumed` `:241-244`), so a lock that minted on the old bridge can never mint again — **if** the successor was constructed with `predecessor = old bridge` (or a `ConsumedView` over it). `setBridge` (`:387-392`) checks only the threshold over `SetBridge(newBridge, adminNonce)` and hands the token over; `WrappedYcash.setBridge` (`WrappedYcash.sol:52-56`) checks only `newBridge != 0`. `script/Deploy.s.sol:60` defaults `PREDECESSOR` to `OLD_BRIDGE` but accepts an override, and `:138` asserts `bridge.predecessor() == c.predecessor` — the env value, not `OLD_BRIDGE` — so an overridden `PREDECESSOR`, a typo, or a hand-deployed successor (`predecessor = address(0)`, or a view over the wrong bridge) passes. The only guard is the runbook's re-read (`hawkeye/docs/operations.md:194-196`).

Effect if it happens: every `lockId` minted on the old bridge is unconsumed on the new one, and a quorum signing for the new EIP-712 domain could mint it again. An honest Hawkeye does not: a lock it already saw minted is `MINTED` in its ledger, and before signing it asks the bridge's `isConsumed` (`engine/mint.rs:1053-1075`) — which on a mis-wired successor answers `false`, so a re-built or restored ledger, or any other signer, has no guard left. Double mint, unbacked wYEC, bounded by `mintCap` per window. Requires a threshold-signed act over a mis-deployed contract: an operator error, not an attack. Low.

## 2. Root cause

- `wyec/contracts/WyecBridge.sol:387-392` — `setBridge` validates nothing about `newBridge`.
- `wyec/contracts/WrappedYcash.sol:52-56` — non-zero only.
- `wyec/script/Deploy.s.sol:60, 123, 138` — `PREDECESSOR` overridable; the post-deploy assertion compares with the env value.
- `hawkeye/docs/operations.md:194-196` — procedural check only; `hawkeye status --params` (`cli.rs:283-398`) shows the new file's floors but not its wiring.

## 3. Fix options considered

| Option | Verdict |
|---|---|
| (a) `setBridge` requires `newBridge.predecessor()` to be `address(this)` (or a `ConsumedView` whose `bridge()` is `this`) and `newBridge.token()` to be this token | **Chosen.** Two static calls at a once-per-migration act; catches every mis-wiring the finding describes. |
| (b) Behavioural probe: the submitter passes one `lockId` consumed here (unsigned calldata) and `setBridge` requires `newBridge.isConsumed(probe)` | Optional add-on: it also catches a successor whose `predecessor()` is right but whose `isConsumed` is broken; needs a probe argument (ABI change of `setBridge`) and is vacuous before the first mint. Recommended only if the reviewers want behaviour, not wiring, checked. |
| (c) Store `lastConsumed` in `_mint` and probe it automatically | Rejected: a storage write on every mint (~2.9–20k gas) for a check used once. |
| (d) Deploy-script and Hawkeye checks only | Rejected as the only guard (the contract is where a hand-deployed successor is caught); kept as the guard for the **first** migration away from a bridge deployed before this fix, which has no on-chain check. |

## 4. Recommended fix

### 4.1 wyec contract (`contracts/WyecBridge.sol`)

```solidity
/// The successor interface `setBridge` checks (design §4.6).
interface IWyecBridgeSuccessor {
    function predecessor() external view returns (IWyecBridgeConsumed);
    function token() external view returns (IWrappedYcash);
}

/// @notice `setBridge`'s successor does not read this bridge's consumed lockIds or does not
///         bridge this token (W3-B-7).
error BadSuccessor(address newBridge);

function setBridge(address newBridge, bytes[] calldata sigs) external {
    _checkThreshold(
        _hashTypedDataV4(keccak256(abi.encode(SET_BRIDGE_TYPEHASH, newBridge, adminNonce++))), sigs
    );
    _checkSuccessor(newBridge);
    token.setBridge(newBridge);
}

function _checkSuccessor(address s) internal view {
    if (s.code.length == 0) revert BadSuccessor(s);
    try IWyecBridgeSuccessor(s).token() returns (IWrappedYcash t) {
        if (address(t) != address(token)) revert BadSuccessor(s);
    } catch { revert BadSuccessor(s); }
    address p;
    try IWyecBridgeSuccessor(s).predecessor() returns (IWyecBridgeConsumed q) { p = address(q); }
    catch { revert BadSuccessor(s); }
    if (p == address(this)) return;
    // a ConsumedView over this bridge is also a correct wiring
    try ConsumedView(p).bridge() returns (IConsumedGetter b) {
        if (address(b) == address(this)) return;
    } catch {}
    revert BadSuccessor(s);
}
```

The signed struct and type hash are unchanged (no EIP-712 vector change). Note the threshold check runs first, so `adminNonce` is consumed only by a call that also passes the successor check (the whole call reverts otherwise). Update the NatSpec of `setBridge` and design §4.6 step 3 ("`setBridge` refuses a successor that does not read this bridge as its predecessor or bridges another token").

### 4.2 wyec deploy script (`script/Deploy.s.sol`)

In `deploySuccessor` (`:117-145`): require `c.predecessor == c.oldBridge`, **or** that `c.predecessor` is a `ConsumedView` whose `bridge()` is `c.oldBridge` (generation-0 migrations); refuse otherwise with `"PREDECESSOR must be OLD_BRIDGE or a ConsumedView over it"`. Keep the `:138` assertion and add `require(address(bridge.token()) == address(token))`. Mirror both in Hawkeye's own `eth/script/Deploy.s.sol`.

### 4.3 Hawkeye (`cli.rs` `status --params`, `hawkeye-eth`)

`hawkeye status --params` with a deployment file whose `predecessor` is set reads the live successor's `predecessor()` and `token()` and the old bridge's `token().bridge()`, and prints rows `successor.predecessor == <old bridge>: OK | MISMATCH`, `successor.token == <old token>: OK | MISMATCH`, `handoff: pending | done`; non-zero exit on `MISMATCH`. At daemon start with such a file, the same check is an error on mainnet (warning elsewhere). `docs/operations.md` §7 step 2 cites the command; step 3 notes the on-chain check on bridges deployed after this fix.

## 5. Tests

wyec (Foundry, exact selectors):
- `test/Successor.t.sol`: `test_SetBridge_RejectsSuccessorWithoutPredecessor` — the scenario that would have caught it: deploy a successor with `predecessor = address(0)`, threshold-sign `SetBridge`, expect `BadSuccessor(successor)`; and, in a companion test with the check disabled (a test harness subclass), show the old `lockId` minting twice — kept as the documented consequence. `test_SetBridge_RejectsWrongPredecessor` (a view over another bridge), `test_SetBridge_RejectsOtherToken`, `test_SetBridge_RejectsEOA`, `test_SetBridge_AcceptsConsumedViewOverThis`, `test_SetBridge_FailedCheckDoesNotConsumeAdminNonce`; the existing `test_Successor_*` cases pass unchanged.
- `test/Deploy.t.sol`: `test_Deploy_SuccessorPredecessorMustBeOldBridge` (env override to another address reverts), `test_Deploy_SuccessorGen0ConsumedViewAccepted`.
Hawkeye:
- `crates/hawkeye-eth/tests/anvil.rs` `anvil_status_flags_miswired_successor` — deploy a mis-wired successor on anvil (bypassing the script), run the `status --params` check → `MISMATCH`, non-zero.
- `eth/test/Deploy.t.sol` (Hawkeye's copy) mirrors the wyec script tests.

## 6. Acceptance criteria

1. On a bridge deployed from the fixed source, `setBridge` to a successor that does not read it as predecessor (directly or through a `ConsumedView` over it), or that bridges another token, reverts `BadSuccessor`.
2. The deploy scripts refuse a successor whose `PREDECESSOR` is not `OLD_BRIDGE` (or its `ConsumedView`).
3. `hawkeye status --params` reports successor wiring and fails on a mismatch; the runbook cites it.
4. Hawkeye re-pinned to the new wyec commit; CI pin and vector-stamp checks pass.

## 7. Risks and side effects

- **Redeploy.** Contract change ⇒ new deployment; none is persistent today (`deployments/` empty in both repos), and mainnet is not deployed, so ship it in the first mainnet bytecode. A test-network bridge deployed before the fix keeps the unchecked `setBridge`: its migration relies on §4.2/§4.3.
- **A future successor with a different interface** (e.g. one that splits `predecessor` into a list) must still expose `predecessor()` and `token()` for this check; record it in design §4.6 as an interface obligation of every successor.
- **Bridge downtime / key rotation:** none.

## 8. Effort estimate and dependencies

wyec 1 day; Hawkeye 0.5 day (status check, script mirror, re-pin). Ship in the same wyec release as `MEDIUM-W3-B-3-wyec-hawkeye-rogue-guardian-proposal-spam` and `LOW-W3-B-8-B-9-wyec-runtime-floors-admin-deadline` (one redeploy, one Hawkeye re-pin). The `setBridge` shown in §4.1 gains `LOW-W3-B-8-B-9`'s `deadline` argument (its `_checkDeadline` and `_checkThreshold` run before `_checkSuccessor`), whichever lands first in the shared release. **Single re-pin owner:** the one Hawkeye re-pin of the bundled wyec release (`eth/tools/fetch-wyec.sh` `WYEC_COMMIT`, the regenerated `eth/vectors/eip712.json` with its new `wyecCommit` stamp and negatives) is owned by `LOW-W3-B-8-B-9-wyec-runtime-floors-admin-deadline.md` §4.3 step 5, the only report that changes type strings; the Hawkeye branches of MEDIUM-W3-B-3, LOW-W3-B-7 and INFO-W3-B-12 stack on it and add only their own vector cases and bindings use.

## Completion record

- **Completed:** 2026-10-15
- **Merged:** wyec `#4` `0e0d87f`. `setBridge` reverts `BadSuccessor` unless the successor has code, bridges the same token, and has this bridge as `predecessor()` (directly or through a `ConsumedView`). `deploySuccessor` enforces the same. EIP-712 type strings are unchanged.
- **Not closed by this landing:** the Hawkeye `status --params` rows and the pin move. That re-pin is still owned by `LOW-W3-B-8-B-9`, which stays pending.
