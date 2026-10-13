# LOW — 05/T-1, 05/T-2, 05/T-4 — Test fidelity: the EIP-712 vector stamp follows the pin, exact `expectRevert` selectors, one copy of the contract tests, negative EIP-712 vectors

Repos / branches to change: `hawkeye` (`fix/05-T-1-test-fidelity` off `upgrade/vault`: `eth/test`, `eth/tools`, `eth/vectors`, `crates/hawkeye-eth/tests`, CI); `wyec` (`fix/05-T-2-exact-reverts` off `upgrade/vault`: `test/`). No node change. · Audit source: `05-bridge-hawkeye-wyec.md` "Test fidelity" rows T-1, T-2, T-4 (`:273-276`); `verification/05-verification.md` rows T-1, T-2, T-4 (`:25-28`); `00-consolidated.md` rows 05/T-1, T-2, recommendation R8. (T-3 is in `HIGH-05-H-2`.) · Status: pending

## 1. Finding

**T-1 — stale, unchecked provenance stamp.** `eth/vectors/eip712.json:3`, `eth/test/Vectors.t.sol:23` (`WYEC_COMMIT = "cad126a…"`) and `eth/vectors/README.md:24` record `wyecCommit = cad126a`, while the pin is `be177c5` (`eth/tools/fetch-wyec.sh:21`). `test_Eip712Vectors` compares the file against a string that embeds the hand-written constant (`Vectors.t.sol:68-87`), so regenerating "fixes" nothing, and a re-pin that changed the EIP-712 structs would still stamp `cad126a`. The digests are correct today (commit `c23849a` changed only `burn`/`_checkRecipient`), so this is provenance, not correctness — until the next re-pin.

**T-2 — bare `vm.expectRevert()`.** `wyec/test/WyecBridge.t.sol:182-191` (`test_Mint_TamperedFieldsRejected`), `:194-198` (`test_Mint_OtherDeploymentSignatureRejected`), `:543-547` (`test_Pause_ReplayOfAdminSigsRejected`), `wyec/test/OptimisticMint.t.sol:171-180` (`test_Propose_OtherDeploymentSignatureRejected`): any revert passes, including an ABI decoding error or an unrelated `require`. The contract does revert for the right reason (`NotGuardian(recovered)`), and the optimistic tests next to them already assert the exact error (`OptimisticMint.t.sol:136-144`). Hawkeye's copies (`hawkeye/eth/test/…`) carry the same four.

**T-4 — diverging copy; no negative vectors.** `diff -rq hawkeye/eth/test wyec/test`: `RateLimit.t.sol` only in wyec, `Vectors.t.sol` only in Hawkeye, `Deploy.t.sol`, `OptimisticMint.t.sol`, `WyecBridge.t.sol`, `utils/BridgeTestBase.sol`, `utils/WyecEip712.sol` differ. Two copies of "Hawkeye's assumptions about the contract" drift silently (the rate-limit assumptions are tested only upstream). `eip712.json` holds accepted cases only; `crates/hawkeye-eth/tests/vectors.rs:31-118` checks digest/signer/signature equality and a positive `recover`; the only negative cases are unit tests (`hawkeye-eth/src/eip712.rs:297-317`: high-S, `v ∈ {0,1}`, 64 bytes). Rust-side rejection of a wrong `chainId`/`verifyingContract` is only implied by digest inequality; nothing consumes a shared negative vector on both sides.

## 2. Root cause

- `hawkeye/eth/test/Vectors.t.sol:23, 68-87` — hand-maintained constant embedded in the generated JSON; `eth/tools/fetch-wyec.sh:21, 26, 72` — the pin and the `.wyec-commit` stamp it writes, never read by the tests.
- `wyec/test/WyecBridge.t.sol:184-189, 197, 546`; `wyec/test/OptimisticMint.t.sol:177` — bare `expectRevert`.
- `hawkeye/eth/README.md` table ("tests of Hawkeye's assumptions") and `fetch-wyec.sh:70` (`git archive … contracts docs` — tests are not fetched); `foundry.toml` `src = vendor/wyec/contracts`, `test = test`.
- `hawkeye/eth/vectors/README.md` format: no `expectAccepted`; `Vectors.t.sol` generates accepted cases only; `vectors.rs` asserts equality only.

## 3. Fix options considered

- T-1: assert the stamp in CI with shell (`grep WYEC_COMMIT= … | cut` vs `jq .wyecCommit`) vs read the pin inside the Foundry test with `vm.readFile`. Both: the test is the generator, so it must *write* the right stamp; CI's shell check is a second, independent witness. Chosen.
- T-4: (i) symlink `wyec/test` into Hawkeye; (ii) fetch upstream tests and run them via inheritance wrappers; (iii) delete Hawkeye's copies and rely on wyec CI. (i) breaks the "fetched at a pinned commit, never copied" rule and the workspace layout; (iii) loses the assertions against the *pinned* commit under Hawkeye's toolchain. **Chosen (ii)**: `fetch-wyec.sh` archives `test/` too; `foundry.toml` adds the remapping `wyec-test/=vendor/wyec/test/`; Hawkeye's `test/Upstream.t.sol` declares one empty contract per upstream test contract inheriting it (`contract Upstream_WyecBridge is WyecBridgeTest {}` …), so forge runs the upstream suites unchanged; Hawkeye keeps only `Vectors.t.sol`, `Deploy.t.sol` (its script differs: `mintMode`) and new Hawkeye-specific assertions, importing `BridgeTestBase`/`WyecEip712` from `wyec-test/utils/`.

## 4. Recommended fix

### 4.1 T-1 (`hawkeye/eth`)

- `Vectors.t.sol`: delete `WYEC_COMMIT`; `string memory pin = vm.trim(vm.readFile("vendor/wyec/.wyec-commit"))` (forge-std v1.17 has `vm.trim`; else trim the trailing newline by hand); require `bytes(pin).length == 40`; use `pin` in the JSON; in check mode also `assertEq(json.readString(".wyecCommit"), pin, "vectors stamp does not match the fetched pin")` before the byte comparison, so the error says *which* is wrong.
- `fetch-wyec.sh`: unchanged for the stamp (it already writes `.wyec-commit`); add `test` to the `git archive` list and the checksum (`:70-71`).
- CI (`.github/workflows/ci.yml` contracts job): a step `test -z "$(diff <(sed -n 's/^WYEC_COMMIT=//p' tools/fetch-wyec.sh) <(jq -r .wyecCommit vectors/eip712.json))"` named "vector stamp matches the pin"; and the same for `eth/README.md`'s table (`grep -c be177c5… README.md`) — or better, make the README cite `tools/fetch-wyec.sh` instead of repeating the hash.
- Regenerate: `WRITE_VECTORS=true forge test --mc Eip712VectorsTest` → `eip712.json` stamp `be177c5762019c2521ea43c81e90d59f972973b7`, digests byte-identical (assert in the PR by `jq 'del(.wyecCommit)'` diff = empty). `vectors/README.md:24`: "the pinned wyec commit, read from `vendor/wyec/.wyec-commit`".

### 4.2 T-2 (`wyec/test`, mirrored in Hawkeye's upstream run automatically after §4.3)

```solidity
function test_Mint_TamperedFieldsRejected() public {
    bytes[] memory sigs = signSorted(guardianPair(), mintDigest(address(bridge), LOCK, AMOUNT, alice));
    _expectNotGuardian(mintDigest(address(bridge), LOCK, AMOUNT + 1, alice), sigs[0]);
    bridge.mint(LOCK, AMOUNT + 1, alice, sigs);
    _expectNotGuardian(mintDigest(address(bridge), LOCK, AMOUNT, bob), sigs[0]);
    bridge.mint(LOCK, AMOUNT, bob, sigs);
    _expectNotGuardian(mintDigest(address(bridge), keccak256("other"), AMOUNT, alice), sigs[0]);
    bridge.mint(keccak256("other"), AMOUNT, alice, sigs);
    assertFalse(bridge.consumed(LOCK));
}
/// `_checkThreshold` recovers sigs[0] first; over a foreign digest it recovers to a non-guardian
/// (never address(0): OZ reverts on an invalid signature), so the first revert is NotGuardian(r0).
function _expectNotGuardian(bytes32 digest, bytes memory sig0) internal {
    vm.expectRevert(abi.encodeWithSelector(WyecBridge.NotGuardian.selector, ECDSA.recover(digest, sig0)));
}
```

Same helper for `test_Mint_OtherDeploymentSignatureRejected` (digest of `other`), `test_Pause_ReplayOfAdminSigsRejected` (the second call's digest is `setPausedDigest(true, adminNonce = 1)`: compute with `WyecEip712` and the first signature), and `OptimisticMint.t.sol:177` (`NotGuardian(ECDSA.recover(mintDigest(address(bridge), …), sig))` — note the recovered address uses *this* bridge's digest against a signature made for `other`). Add a grep to wyec CI: `! grep -rn "vm.expectRevert();" test/` ("bare expectRevert is not allowed; assert the selector").

### 4.3 T-4 — one copy (`hawkeye/eth`)

- `fetch-wyec.sh`: archive `contracts docs test`; checksum all three.
- `foundry.toml`: remapping `wyec-test/=vendor/wyec/test/`; `[fmt] ignore` already covers `vendor`.
- `test/Upstream.t.sol` (new): imports `wyec-test/WyecBridge.t.sol`, `OptimisticMint.t.sol`, `RateLimit.t.sol`, `Deploy.t.sol` and declares `contract Upstream_WyecBridgeTest is WyecBridgeTest {}` etc. (forge runs inherited `test_*` functions; verify the count with `forge test --list` and assert it in CI: `forge test --list --json | jq '[.[] | .[] | length] | add'` equals upstream's count + Hawkeye's own).
- Delete `test/WyecBridge.t.sol`, `test/OptimisticMint.t.sol`, `test/utils/*` from Hawkeye; `Vectors.t.sol` and `Deploy.t.sol` import `wyec-test/utils/BridgeTestBase.sol` / `WyecEip712.sol`. Where Hawkeye's copies carried assertions upstream lacks (diff them first — e.g. `mintMode` in `Deploy.t.sol`, the challenge-id binding tests if any differ), move those into `test/HawkeyeAssumptions.t.sol` or upstream them to wyec in the T-2 PR.
- `eth/README.md`: the table rows for the deleted files → "upstream tests at the pin, run through `test/Upstream.t.sol`".

### 4.4 T-4 — negative EIP-712 vectors (`Vectors.t.sol`, `vectors/README.md`, `hawkeye-eth/tests/vectors.rs`)

Add to every case `"expectAccepted": true` and new cases with `"expectAccepted": false, "reject": "<reason>"`:

| `reject` | Construction | Foundry asserts | Rust asserts |
|---|---|---|---|
| `wrong-chain-id` | `Mint` signed over the 11155111 domain, submitted on 31337 | `proposeMint` → `NotGuardian(recovered)` with `recovered` recorded in the case | `mint_digest(31337, …) != case.digest`; `recover(digest_31337, sig) != case.signer` |
| `wrong-verifying-contract` | signed for `NEW_BRIDGE` address | same | same with the contract |
| `high-s` | `s → n − s`, `v` flipped | `ECDSAInvalidSignatureS(s)` (OZ 5.x selector) | `recover` → `Error::BadSignature` |
| `bad-v` | `v ∈ {0, 1}` | `ECDSAInvalidSignature()` | `BadSignature` |
| `duplicate-signer` | 2-of-3 `mint` with `[sig_a, sig_a]` | `SignersNotAscending()` | `sort_signatures` → `DuplicateSigner` |
| `not-ascending` | `[sig_b, sig_a]` with `b > a` | `SignersNotAscending()` | `sort_signatures` reorders (accepted after sorting — record `"acceptedAfterSort": true`) |
| `wrong-struct` | a `Challenge` signature submitted as a `Mint` | `NotGuardian(recovered)` | digest inequality |

The generator signs with the same three keys; the JSON gains the fields; `vectors.rs` iterates `expectAccepted == false` cases and asserts the Rust outcome in the table; the case count assertion (`:33`, `40`) is updated. `vectors/README.md` documents the new fields.

## 5. Tests

The changes *are* tests; the meta-checks: CI stamp step (§4.1), bare-`expectRevert` grep (§4.2), upstream test-count assertion (§4.3), `vectors.rs` negative-case count equals the Foundry negative-case count (both read the file).

## 6. Acceptance criteria

1. `eip712.json`'s `wyecCommit` equals `fetch-wyec.sh`'s pin, by construction and by CI; a re-pin without regenerating fails `forge test`.
2. No bare `vm.expectRevert()` in `wyec/test` or `hawkeye/eth/test`; every negative test names its selector and arguments.
3. `hawkeye/eth/test` contains no copy of a wyec test; upstream suites run under Hawkeye's toolchain at the pin; test counts asserted.
4. Negative EIP-712 vectors are consumed by both sides with the outcomes in §4.4's table.

## 7. Risks and side effects

- Running upstream tests under Hawkeye's remappings may surface compiler-version or `forge-std` version differences (wyec may pin another `forge-std`); align `package.json` pins or vendor `forge-std` per side. No runtime effect.
- No contract change (T-2 is tests only), no redeploy, no downtime.

## 8. Effort estimate and dependencies

T-1 0.5 day; T-2 0.5 day; T-4 1.5 days. **≈ 2.5 days.** Land T-1 **before** any re-pin (`HIGH-05-H-2`, `LOW-05-L-3`).
