# LOW — W3-B-4, W3-B-5 — The lock policy accepts the zero destination address; a Ycash-mainnet config is not bound to Ethereum chain id 1

Repos / branches to change: `hawkeye` (`fix/W3-B-4-B-5-input-binding` off `upgrade/vault`: `hawkeye-core/src/lock.rs`, `engine/mint.rs`, `config.rs`, `foreign/ethereum.rs`, tests). No wyec change. No node change. · Audit source: `docs/audits/quantum-vault-ecosystem-wave3/05-bridge-hawkeye-wyec.md` §W3-B-4 (`:144-158`), §W3-B-5 (`:160-172`); `docs/audits/quantum-vault-ecosystem-wave3/verification/05-verification.md` §W3-B-4 (`:180-187`), §W3-B-5 (`:189-196`); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row "W3-B-4..13, 05/N-1..N-4"; `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` status rows W3-B-4 (`:53`) and W3-B-5 (`:54`), both **STILL OPEN** (`lock.rs`, `policy.rs`, `config.rs`, `mint.rs`, `foreign/ethereum.rs`, `hawkeye-eth` byte-unchanged since `b0f085f`); `docs/audits/quantum-vault-ecosystem-wave4/verification/02-verification.md` status row (`:42`, confirmed: `config.rs:719-723` mainnet → `MAINNET`). · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13): every line cited below is unchanged except `cli.rs` (moved). · Status: done — completed 2026-10-16 (merged on `upgrade/vault`; see the completion record). Previously pending

Two independent, small input-binding checks in the same repository and the same review; grouped so they land as one PR. Either may be split off without affecting the other.

## 1. Finding

**W3-B-4.** Plan §4.1 rule 3 (`docs/hawkeye-bridge-plan.md:426-428`) says a lock's destination must not be the zero address ("a mint to `address(0)` reverts and would leave the `lockId` unconsumed forever"). `parse_destination` (`crates/hawkeye-core/src/lock.rs:91-106`) checks the `OP_RETURN` shape, the 32-byte push, the `0x5956` prefix and the 12 zero bytes, and returns `EthAddress` without comparing it to `EthAddress::ZERO` (`hawkeye-core/src/eth.rs:18`). The policy (`policy.rs:243-258`) accepts it, every attestor signs `Mint(lockId, amount, 0x0)`, `proposeMint` reverts `ZeroRecipient` (`wyec/contracts/WyecBridge.sol:272`) and `mint` reverts in the token (`ERC20InvalidReceiver`), so the lock stays `SIGNED` and the mint leader resubmits every `takeover` blocks (`engine/mint.rs:1481-1486`, `recently_submitted`) forever. No loss (the locker keeps the owner branch), but the daemon diverges from the normative policy, burns gas on reverting estimates, and the rule has no test. `hawkeye lock` already refuses `--dest 0x0…0` (`cli.rs:514`; `hawkeye burn` likewise refuses a zero `--to`, `:996-999`); a hand-built lock is not refused.

**W3-B-5.** The NEAR branch of config validation requires `near.network_id == "mainnet"` iff `network.name == "mainnet"` (`crates/hawkeye/src/config.rs:653-659`). The Ethereum branch takes `chain_id` from the deployment file (`:695-701`) and, on mainnet, only *substitutes* 1 for the floor checks (`:719-723`); the same substitution is at `foreign/ethereum.rs:302-306`. `hawkeye-eth/src/client.rs:151-157` checks the RPC's `eth_chainId` against the **file**, not against the Ycash network. `floors.rs` has no chain rule. A Ycash-mainnet attestor started with `deployments/11155111.json` passes every check and signs mainnet locks for Sepolia wYEC (and a testnet attestor could be pointed at chain 1). An operator error, not an attack, but the NEAR branch shows the intended rule.

## 2. Root cause

- `crates/hawkeye-core/src/lock.rs:91-106` — no zero-address comparison.
- `crates/hawkeye/src/engine/mint.rs:1481-1486` — the resubmission loop has no terminal case for a recipient the contract can never accept.
- `crates/hawkeye/src/config.rs:719-723` — `let chain_id = if mainnet { MAINNET } else { core_deployment.chain_id }`: substitution, not an `ensure!`; `crates/hawkeye/src/foreign/ethereum.rs:302-306` — the same pattern for the live contract checks.
- `crates/hawkeye/src/config.rs` tests (`:1217`, `:1283`, `:1361`, `:1663`, `:1700`) build mainnet configs over a `31337.json` deployment, which is why the substitution exists; `mainnet_example_config_passes` (`:1325-1335`) already rewrites the file to `"chainId":1`.

## 3. Fix options considered

| Finding | Option | Verdict |
|---|---|---|
| W3-B-4 | Reject zero in `parse_destination` (policy `BadDestination`) | **Chosen** (the plan's rule, one line, vectored by a unit test). |
| W3-B-4 | Reject only at signing time in `engine/mint.rs` | Rejected: the policy is what the ledger records and what peers compare (`GET /locks/<id>`); a rejection belongs there. A guard in the submit path is added only for ledgers that already hold such a lock. |
| W3-B-5 | `ensure!(mainnet == (chain_id == 1))` at config load, and the same at the live check | **Chosen.** Symmetric: a testnet/regtest attestor pointed at chain 1 is refused too. |
| W3-B-5 | A floor in `floors.rs` (warn on testnet) | Rejected: this is a pairing, not a magnitude; there is nothing to warn about at a quarter. |

## 4. Recommended fix

### 4.1 W3-B-4 (`hawkeye-core/src/lock.rs`)

```rust
let addr = EthAddress(data[12..].try_into().expect("20 bytes"));
if addr == EthAddress::ZERO {
    return Err(Error::Destination("the zero address (plan §4.1 rule 3)"));
}
Ok(addr)
```

Update the doc comment (`:88-90`). `Destination::parse` maps it to `LockRejection::BadDestination` (`policy.rs:257`), so the lock is `POLICY_REJECTED` with the reason in the ledger and in `GET /locks/<id>`; it is never signed.

For a ledger that already holds a `SIGNED` lock with `to == 0` (devnet/testnet history only): in the mint submission path (`engine/mint.rs`, before `recently_submitted` is consulted) skip it with a one-time `warn!(event = "mint_zero_recipient_skipped", lock_id)` and stop resubmitting; no state migration (the record stays `SIGNED`; `hawkeye status` lists it). No NEAR change (`parse_near_destination` cannot yield an empty account id).

### 4.2 W3-B-5 (`config.rs`, `foreign/ethereum.rs`)

At `config.rs:719-723` replace the substitution:

```rust
ensure!(
    mainnet == (core_deployment.chain_id == hawkeye_eth::mode::MAINNET),
    "[eth] deployment is on chain {} with network.name {:?}: a mainnet bridge pairs Ycash mainnet \
     with Ethereum mainnet (chain id 1), and only those",
    core_deployment.chain_id, self.network.name
);
let chain_id = core_deployment.chain_id;
```

At `foreign/ethereum.rs:302-306` use `self.client.chain_id()` (already verified against the file by `client.rs:151-157`) for the contract floor checks, with the same `ensure!` as a second line of defence. `hawkeye status --params` prints the pairing (`network mainnet ↔ chain 1: OK`).

Update the config tests that build a mainnet config over `31337.json` to write a `"chainId":1` deployment (the `mainnet_example_config_passes` pattern) — they test floors, not the chain.

### 4.3 Docs

Plan §4.1 rule 3: no text change (already normative); add "(enforced by `parse_destination`, W3-B-4)". `docs/operations.md` §8 table: a row `[eth] deployment chainId | network.name | 1 iff mainnet`.

## 5. Tests

- `hawkeye-core/src/lock.rs` `destination_round_trip_and_rejects` (`:145`): add `destination_script(&EthAddress::ZERO)` → `Err(Destination(_))`; a one-bit-nonzero address still parses.
- `hawkeye-core/src/policy.rs` tests: a lock whose `OP_RETURN` is 32 zero bytes → `LockRejection::BadDestination`.
- `crates/hawkeye/tests/engine.rs` (anvil-backed; run with `HAWKEYE_REQUIRE_ANVIL=1`, else it passes vacuously) `zero_destination_lock_rejected_not_signed`: a lock to `0x0…0` on the mock node; after `C_Y` blocks every engine records `POLICY_REJECTED`, no `sign_once_mint` row, no `proposeMint`/`mint` call. Fails at `f4436df`.
- `crates/hawkeye-eth/tests/anvil.rs` (optional): the same lock against a real bridge produces no transaction.
- `config.rs` tests: `mainnet_refuses_non_mainnet_chain` (mainnet + `11155111.json` → error naming both), `testnet_refuses_chain_one` (testnet + chain 1 → error), `mainnet_chain_one_passes`; the updated floor tests stay green.

## 6. Acceptance criteria

1. A zero-destination lock is policy-rejected with a recorded reason and never signed; the rule has a unit and an engine test.
2. Hawkeye refuses to start with a Ycash-mainnet config over a non-1 chain id, and with a non-mainnet config over chain id 1; the message names the pairing.
3. No other config test changes behaviour.

## 7. Risks and side effects

- An operator running a "mainnet-shaped" rehearsal (Ycash mainnet parameters against Sepolia) can no longer do so; rehearsals use `network.name = "testnet"` with the mainnet floors, which `floors.rs` already warns at a quarter. State this in the runbook §8.
- **Bridge downtime / key rotation / contract redeploy:** none.

## 8. Effort estimate and dependencies

0.5 day including tests. No dependencies.

## Completion record

- **Completed:** 2026-10-15
- **Merged:** hawkeye `#16` `d033591`. A zero-address lock is policy-rejected. Config load refuses mainnet over a non-1 chain and a non-mainnet config over chain 1 when an `[eth]` deployment is present.
- **Not closed by this landing:** the `engine/mint.rs` guard for already-signed zero-recipient locks, the anvil tests, and the plan §4.1 / operations §8 rows.
