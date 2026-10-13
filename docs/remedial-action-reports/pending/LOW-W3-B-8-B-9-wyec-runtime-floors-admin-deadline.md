# LOW — W3-B-8, W3-B-9 — The mainnet floors hold only in the constructor; admin acts carry no deadline

Repos / branches to change: `wyec` (`fix/W3-B-8-B-9-admin-path` off `upgrade/vault`: `contracts/WyecBridge.sol`, `test/`, `test/utils/WyecEip712.sol`, `docs/wyec-contract-design.md` §4.3 / §4.5.3); `hawkeye` (`fix/W3-B-9-admin-deadline` off `upgrade/vault`: `hawkeye-core/src/eip712.rs`, `hawkeye-eth/src/eip712.rs` + `client.rs`, `eth/vectors/eip712.json` regeneration, `eth/tools/fetch-wyec.sh` re-pin, `devnet/hawkeye-devnet` rotation scenario, plan §4.4, `docs/operations.md` §7). No node change. · Audit source: `docs/audits/quantum-vault-ecosystem-wave3/05-bridge-hawkeye-wyec.md` §W3-B-8 (`:203-213`), §W3-B-9 (`:215-225`); `docs/audits/quantum-vault-ecosystem-wave3/verification/05-verification.md` §W3-B-8 (`:216-220`), §W3-B-9 (`:222-226`); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row "W3-B-4..13, 05/N-1..N-4"; `docs/audits/quantum-vault-ecosystem-wave4/04-clients-wyec-recheck.md` status row W3-B-8 / W3-B-9 (`:63-64`) (**STILL OPEN**; wyec has had no commit since `dfd51cb`); `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` status row W3-B-8 / W3-B-9 (`:57-58`). · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13): wyec, `hawkeye-core/src/eip712.rs`, `hawkeye-eth` and `devnet/hawkeye-devnet` unchanged; `engine/mod.rs` moved (cited at `f4436df`). · Status: pending

Both findings are on the threshold-signed admin path of `WyecBridge` and both need a new deployment; W3-B-9 also changes four EIP-712 type strings (a byte-exactness change: plan first, vectors regenerated). They land as one wyec change and one Hawkeye re-pin.

## 1. Finding

**W3-B-8.** On chain id 1 the constructor refuses `threshold < 2`, `challengeWindow < 2 h` and `mintCap == 0` (`contracts/WyecBridge.sol:225-232`). After deployment, `_setGuardians` (`:454-467`) accepts any `threshold_ ≥ 1` and `_setMintLimit` (`:470-477`) accepts `mintCap_ == 0` (no limit). A threshold of guardians can therefore move a mainnet bridge to `threshold = 1` — after which one key mints immediately through `mint`, skipping the optimistic window, and can lift the cap — or to an unlimited `mintCap`. Hawkeye pauses its own mint-side acts on `mintCap == 0` (`mint_cap_unbounded` in `mint_paused`, `engine/mod.rs:789-794`) and refuses to start on a below-floor contract (`hawkeye-eth/src/mode.rs:60-81`, `foreign/ethereum.rs:302-313`), but it cannot stop the contract. Authorised (it needs the current threshold), but it contradicts the documented invariant "`threshold` ≥ 2 in every mode" (`hawkeye/docs/operations.md:219`) and the contract's own header (`WyecBridge.sol:52-56`).

**W3-B-9.** The admin type hashes carry only `adminNonce` (`WyecBridge.sol:63-69`): `SetGuardians(address[] guardians,uint8 threshold,uint256 adminNonce)`, `SetPaused(bool paused,uint256 adminNonce)`, `SetBridge(address newBridge,uint256 adminNonce)`, `SetMintLimit(uint256 mintCap,uint256 capWindow,uint256 adminNonce)`; submission is permissionless (`:351-392`). A round signed and then abandoned — e.g. a `SetPaused(false)` prepared during an incident, after which the set decides to stay paused — stays submittable by anyone holding the signatures until some other admin act consumes the nonce. Nothing lets the set retire it short of performing another act.

## 2. Root cause

- `wyec/contracts/WyecBridge.sol:225-232` — floors in the constructor only.
- `wyec/contracts/WyecBridge.sol:454-467` (`_setGuardians`: `threshold_ == 0 || threshold_ > length` only), `:470-477` (`_setMintLimit`: `mintCap_ != 0 && capWindow_ == 0` only).
- `wyec/contracts/WyecBridge.sol:63-69, 351-392` — admin structs without an expiry.
- Hawkeye mirrors the type strings twice: `hawkeye-core/src/eip712.rs:98-170` (hand-rolled, byte-exact, vectored) and `hawkeye-eth/src/eip712.rs:38-66, 110-160` (alloy `sol!`), plus `eth/vectors/eip712.json` (Foundry-generated, stamped with `wyecCommit`), and `devnet/hawkeye-devnet:2630-2660` builds `SetGuardians` with `cast`.

## 3. Fix options considered

| Finding | Option | Verdict |
|---|---|---|
| W3-B-8 | Apply the chain-1 floors in `_setGuardians` / `_setMintLimit` (the constructor calls them, so one place) | **Chosen.** |
| W3-B-8 | Make `threshold`/`mintCap` immutable on mainnet | Rejected: rotation and cap changes are needed operations. |
| W3-B-9 | `uint256 deadline` in every admin struct; `block.timestamp > deadline` reverts; a maximum lifetime | **Chosen.** Bounds an abandoned round to its deadline; the set chooses short deadlines for incident acts and longer ones for a break-glass pause. |
| W3-B-9 | A threshold-signed `bumpAdminNonce()` to void outstanding rounds | Rejected as the only fix: voiding needs another full threshold round at the very moment the set is split about the act; kept unnecessary with deadlines. |
| W3-B-9 | A deadline on `Mint` too | Rejected for now: a `Mint` signature is valid only for one `(lockId, amount, to)` of a policy-OK lock, is bounded by the `lockId`'s consumption and by `vetoed`, and Hawkeye's sign-once `Mint` record is one `(amount, to)` per `lockId` per deployment (`signonce.rs:164-275`); a deadline would force re-signing the same lock with a new digest and change those records. Recorded in design §4.5 as a considered, deferred option. |

## 4. Recommended fix

### 4.1 wyec: runtime floors (`contracts/WyecBridge.sol`)

```solidity
function _setGuardians(address[] memory guardians_, uint8 threshold_) internal {
    if (threshold_ == 0 || threshold_ > guardians_.length) revert BadGuardianSet();
    if (block.chainid == 1 && threshold_ < 2) revert MainnetThreshold(threshold_);
    …
}
function _setMintLimit(uint256 mintCap_, uint256 capWindow_) internal {
    if (mintCap_ != 0 && capWindow_ == 0) revert BadMintLimit();
    if (block.chainid == 1 && mintCap_ == 0) revert MainnetMintCapRequired();
    …
}
```

Remove the now-duplicate threshold and cap checks from the constructor (`:226`, `:230`); keep the `challengeWindow` floor there (it is immutable). Header comment `:52-56`: "Mainnet floors (chain id 1) hold for the constructor **and every admin act**". If `MEDIUM-W3-B-3` lands, its `maxOpenProposals` floor is constructor-only by nature (immutable).

### 4.2 wyec: admin deadlines (`contracts/WyecBridge.sol`)

```solidity
bytes32 private constant SET_GUARDIANS_TYPEHASH =
    keccak256("SetGuardians(address[] guardians,uint8 threshold,uint256 adminNonce,uint256 deadline)");
bytes32 private constant SET_PAUSED_TYPEHASH =
    keccak256("SetPaused(bool paused,uint256 adminNonce,uint256 deadline)");
bytes32 private constant SET_BRIDGE_TYPEHASH =
    keccak256("SetBridge(address newBridge,uint256 adminNonce,uint256 deadline)");
bytes32 private constant SET_MINT_LIMIT_TYPEHASH =
    keccak256("SetMintLimit(uint256 mintCap,uint256 capWindow,uint256 adminNonce,uint256 deadline)");

/// @notice The longest an admin round may stay valid (W3-B-9).
uint256 public constant MAX_ADMIN_TTL = 30 days;
error AdminActExpired(uint256 deadline);
error AdminDeadlineTooFar(uint256 deadline);

function _checkDeadline(uint256 deadline) internal view {
    if (block.timestamp > deadline) revert AdminActExpired(deadline);
    if (deadline > block.timestamp + MAX_ADMIN_TTL) revert AdminDeadlineTooFar(deadline);
}
```

Every admin function gains `uint256 deadline` before `sigs` (`setGuardians(guardians_, threshold_, deadline, sigs)`, `setPaused(paused_, deadline, sigs)`, `setMintLimit(mintCap_, capWindow_, deadline, sigs)`, `setBridge(newBridge, deadline, sigs)`), calls `_checkDeadline(deadline)` **before** `_checkThreshold` and hashes `deadline` last in the struct. `adminNonce` semantics are unchanged (HK-11: one round at a time). NatSpec and design §4.3 describe the deadline; the "break-glass pause" practice in `MEDIUM-W3-B-3` §4.6 uses deadlines up to `MAX_ADMIN_TTL` and is re-signed before they lapse.

`MAX_ADMIN_TTL` rationale: a 30-day bound lets the set pre-sign an emergency pause yet guarantees an abandoned act dies within a month; a shorter constant may be chosen in review.

### 4.3 Hawkeye: mirror the type strings (byte-exactness, `hawkeye/CLAUDE.md` rule 3)

1. Plan §4.4 first: the four new type strings and the deadline rule.
2. `hawkeye-core/src/eip712.rs` (`set_guardians_struct_hash` `:157`, `set_paused_digest` `:112`, `set_guardians_digest` `:98`, and the mint-limit/bridge equivalents): add `deadline: u64` (encoded as `uint256`).
3. `hawkeye-eth/src/eip712.rs` `sol!` structs (`:38-66`) and digest helpers (`:110-160`); the type-string test (`:254-265`) updated.
4. `hawkeye-eth/src/client.rs` `set_paused`/`set_guardians`/`set_mint_limit`/`set_bridge` (`:490-552`) take `deadline`.
5. `eth/vectors/eip712.json`: regenerate with Foundry from the new pin (`eth/test/Vectors.t.sol`), new `wyecCommit` stamp; add negative vectors: an expired act and one with a deadline beyond `MAX_ADMIN_TTL` (`expectAccepted: false`), consistent with `LOW-05-T-1`'s negative-vector process. `hawkeye-core/tests/eip712.rs` replays them.
6. `devnet/hawkeye-devnet:2630-2660` (`set_guardians` via `cast`): the new type string and a `deadline = now + 1 h`.
7. `docs/operations.md` §7: every admin round states its deadline in the out-of-band request; incident acts use hours, not days.

## 5. Tests

wyec (Foundry, exact selectors):
- `test/WyecBridge.t.sol` / `test/RateLimit.t.sol`: `test_SetGuardians_MainnetThresholdFloor` (`vm.chainId(1)`, threshold 1 reverts `MainnetThreshold(1)`; 2 passes); `test_SetMintLimit_MainnetCapRequired` (cap 0 reverts `MainnetMintCapRequired()`); the same calls pass on chain 31337 (dev deployments keep threshold 1).
- `test_Admin_ExpiredActReverts` for each of the four acts (`vm.warp(deadline + 1)` → `AdminActExpired(deadline)`), `test_Admin_DeadlineTooFarReverts`, `test_Admin_ExpiredActDoesNotConsumeNonce`, `test_Admin_DeadlineIsSigned` (a signature over deadline `d` does not verify with `d + 1` → `NotGuardian`/`Threshold`).
- `test/utils/WyecEip712.sol` (the independent encoder) updated; the type-string assertion tests updated.
Hawkeye:
- `hawkeye-core/tests/eip712.rs` and `hawkeye-eth/tests/vectors.rs` replay the regenerated vectors (positive and the new negatives).
- `crates/hawkeye-eth/tests/anvil.rs`: `anvil_admin_act_expires` (sign `SetPaused(true)` with a short deadline, advance anvil time, submission reverts `AdminActExpired`); `anvil_mainnet_floor_on_set_guardians` (anvil with `--chain-id 1`: threshold-1 rotation reverts).
- Devnet `scenario rotation` on both node lines.

## 6. Acceptance criteria

1. On chain 1 no admin act can set `threshold < 2` or `mintCap = 0`.
2. Every admin act carries a signed deadline, is refused after it, and is refused when the deadline exceeds `MAX_ADMIN_TTL`.
3. Hawkeye's two EIP-712 implementations, the Foundry vectors (with negatives) and the devnet scripts agree byte for byte; CI's vector-stamp and pin checks pass.
4. Plan §4.4, design §4.3 and runbook §7 updated.

## 7. Risks and side effects

- **Redeploy and ABI change.** New constructor-free but signature-changing admin functions and type hashes ⇒ a new deployment; none is persistent today and mainnet is not deployed. Every tool that builds an admin act (Hawkeye client, devnet script, any guardian runbook using `cast`) must change in the same release. A guardian who signs with an old tool produces a signature that simply does not verify (fails closed).
- **Emergency rotation down to one guardian** is impossible on mainnet after W3-B-8; the set must keep at least two guardians (state it in the runbook §7: rotate in a replacement before removing the second-to-last).
- **Key rotation / bridge downtime:** none beyond the redeploy on test networks.
- **NEAR bridge** (`wyec-near`, `hawkeye-core/src/near.rs:544-600`) has the same admin messages; out of this audit's scope — raise separately.

## 8. Effort estimate and dependencies

wyec 1 day; Hawkeye 1.5 days (two encoders, vectors, client, devnet, docs). Same wyec release as `MEDIUM-W3-B-3-wyec-hawkeye-rogue-guardian-proposal-spam`, `LOW-W3-B-7-wyec-setbridge-successor-wiring` and the wyec items of `INFO-W3-B-12-B-13-05-N-4-…`; this report owns the single Hawkeye re-pin and vector regeneration for that release (§4.3 step 5), on which the other three reports' Hawkeye branches stack; if W3-B-7 lands first, its `setBridge` gains the `deadline` argument here (the successor check runs after `_checkDeadline` and `_checkThreshold`).
