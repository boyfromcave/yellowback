# LOW — 05/L-3 — A successor bridge does not inherit `consumed`; Hawkeye's `lockId`-keyed Mint record both guards and blocks across a migration

Repos / branches to change: `wyec` (`fix/05-L-3-predecessor-consumed` off `upgrade/vault`); `hawkeye` (`fix/05-L-3-mint-sign-once-per-deployment` off `upgrade/vault`, store schema; re-pin after the wyec change). No node change. · Audit source: `05-bridge-hawkeye-wyec.md` §L-3 (`:235-244`); `verification/05-verification.md` row L-3 (`:22`), contract re-read (`:107-114`); `00-consolidated.md` row 05/L-1..L-5. · Status: pending

## 1. Finding

`WyecBridge.setBridge` (`wyec/contracts/WyecBridge.sol:332-340`) hands the token's mint/burn right to `newBridge` (`WrappedYcash.setBridge`, `WrappedYcash.sol:50-56`); the old bridge's `consumed` mapping (`WyecBridge.sol:95-96`, set in `_mint`, `:384-385`) stays behind. A successor deployed from the same source starts with an empty `consumed`, so every historical `lockId` — every lock ever minted — can be minted again by a threshold of guardians signing `Mint(lockId, amount, to)` for the new domain (the EIP-712 domain binds `address(this)`, `:188`, so old signatures do not replay, but new ones are a fresh quorum decision over a lock that already paid out once). The design doc calls `setBridge` "the only upgrade path" (`wyec/docs/wyec-contract-design.md:95-101`) and says nothing about state carried across.

Hawkeye's own guard, `sign_once_mint` keyed by `lockId` alone (`crates/hawkeye-store/src/signonce.rs:138-213`; schema `sign_once_mint`, `schema.rs:120-130`), refuses a second signature whose digest differs (`:150-173`): that stops an honest attestor re-signing a consumed lock for the successor, **but also** stops it signing a lock that was `Signed` yet never minted before the migration (same `(amount, to)`, different digest → `SignOnceConflict`), so such a lock can never be minted on the successor by that attestor; and an attestor restored with a fresh ledger (`MEDIUM-05-M-3`) has no guard at all. The lock's ledger state (`Minted`, terminal) helps only where the ledger survived.

## 2. Root cause

- `wyec/contracts/WyecBridge.sol:332-340` — `setBridge` migrates nothing; `:95-96` — `consumed` is per contract instance; `:202-207, 216-228, 257-267` — all three mint entry points check only the local mapping.
- `crates/hawkeye-store/src/signonce.rs:138-174` — key `lockId`; conflict on digest difference.
- `crates/hawkeye/src/engine/mint.rs` — the mint path never consults `foreign.consumed(lock_id)` of a predecessor (there is none to consult).
- `wyec/docs/wyec-contract-design.md` §4, §8 — no migration section.

## 3. Fix options considered

| Option | Verdict |
|---|---|
| (a) Immutable `predecessor` in the successor; `isConsumed(lockId)` = local `consumed` or `predecessor.isConsumed(lockId)` (recursive view across a chain of bridges); every mint path checks `isConsumed` | One `immutable`, one view, one extra `SLOAD` + external `STATICCALL` per mint when a predecessor is set (none for the first deployment). Deterministic, no governance step, auditable from the bytecode. **Chosen.** |
| (b) `importConsumed(bytes32[] lockIds, sigs)` under threshold + `adminNonce` | O(n) gas over the whole history, a governance round that can be partial or wrong, and nothing stops a *missing* id. Rejected. |
| (c) Keep the token's `consumed` in the token (shared by all bridges) | Moves policy into the token, the design's one rule it will not break (§4 "policy outside the token"). Rejected. |
| Hawkeye: key `sign_once_mint` by `(deployment, lockId)` with an `(amount, to)` invariant across deployments | Keeps "one `(amount, to)` per lock ever" while allowing a second signature for a new domain. **Chosen.** |

## 4. Recommended fix

### 4.1 wyec (`contracts/WyecBridge.sol`, `script/Deploy.s.sol`, `docs/wyec-contract-design.md`)

```solidity
/// @notice The bridge this one succeeded (address(0) for the first). Its consumed lockIds are
///         consumed here too, recursively, so a lock never mints twice across a migration.
IWyecBridgeConsumed public immutable predecessor;

interface IWyecBridgeConsumed { function isConsumed(bytes32 lockId) external view returns (bool); }

constructor(IWrappedYcash token_, address[] memory guardians_, uint8 threshold_, uint64 challengeWindow_,
            uint256 mintCap_, uint256 capWindow_, IWyecBridgeConsumed predecessor_) … {
    predecessor = predecessor_;
}

function isConsumed(bytes32 lockId) public view returns (bool) {
    if (consumed[lockId]) return true;
    return address(predecessor) != address(0) && predecessor.isConsumed(lockId);
}
```

Replace `if (consumed[lockId]) revert LockConsumed(lockId);` in `mint` (`:203`) and `proposeMint` (`:221`) with `if (isConsumed(lockId)) …`; `executeMint` relies on the invariant "a lockId with a proposal is never consumed" (`:264`), which `proposeMint` now guarantees across predecessors too — keep the comment, add "(including the predecessor's)". The deployed `WyecBridge` at the Hawkeye pin has no `isConsumed`; a successor of **that** generation needs a one-off adapter or the first migration passes `predecessor_ = address(0)` and a threshold `importConsumed` of the (short) history — state in the design doc that generation-0 bridges (none deployed on mainnet yet) are migrated by the adapter `ConsumedView(oldBridge)` that forwards to the old `consumed(bytes32)` getter (a 10-line contract in `contracts/`, deployed once).

`Deploy.s.sol`: `PREDECESSOR` env (default `address(0)`), written to the deployment JSON; on a successor deploy also assert `oldBridge.token() == token` and print the `setBridge` admin act the guardians must sign next.

Design doc §4: new subsection **4.6 Migration to a successor**: order (deploy successor with `predecessor = old`; guardians re-read; old bridge `setBridge(new)` under threshold — after which the old bridge can neither mint nor burn; pending proposals on the old bridge are void: challenge-free, they simply cannot execute (`token.crosschainMint` reverts `NotBridge`), so Hawkeye re-proposes them on the successor; attestors switch `[eth] deployment` in one maintenance window), what carries over (`consumed` by view; nothing else: `adminNonce`, `burnNonce` restart at 0 — Hawkeye keys burns by `(chainId, bridge, nonce)`, `burns.rs:16-23`, so no collision), and the rule that `challengeWindow`/`threshold` changes happen this way.

### 4.2 Hawkeye (`hawkeye-store`, `engine/mint.rs`, `foreign/*`)

- Schema **V6/V7** (coordinate with `HIGH-05-H-1`/`H-2`): rebuild `sign_once_mint` with columns `chain_id INTEGER NOT NULL`, `bridge BLOB NOT NULL CHECK(length(bridge) = 20)`, PK `(lock_id, chain_id, bridge)`; migrate existing rows with the ledger's current deployment (read from `chain_cursor`/the config at migration time: `Store::backfill_mint_deployment(deployment)` called from `daemon::connect`, as the H-1 backfill); a trigger `sign_once_mint_one_amount_per_lock` that aborts an insert whose `(amount, recipient)` differs from any existing row with the same `lock_id` (the invariant that matters), and the immutability triggers as today.
- `sign_once_mint(lock_id, amount, to, digest, sign)` gains the deployment from `ctx.params.deployment`; semantics: same deployment + same `(amount, to, digest)` → stored record; same deployment + any difference → `SignOnceConflict`; other deployment + same `(amount, to)` → a new record (sign); other deployment + different `(amount, to)` → `SignOnceConflict` (trigger).
- Before signing or proposing, `evaluate_locks`/`sign_mints` call `foreign.consumed(lock_id)` (the trait has `consumed`, `foreign/mod.rs:35`) — which after §4.1 covers predecessors — and move a consumed lock straight to `Minted` with reason `"consumed on the bridge (predecessor)"` without signing.
- `ForeignChain::deployment()` already distinguishes bridges; `Ctx.params.deployment` is the one in `[eth] deployment`. A ledger whose rows are for another deployment is **allowed** (migration) but logged at start-up: `event = "ledger_has_other_deployment_rows"` with counts.
- `hawkeye-eth` bindings: regenerate from the re-pinned ABI (`isConsumed`, the new constructor arg); `EthClient::consumed` calls `isConsumed`.

### 4.3 Vectors and pin

The EIP-712 structs are unchanged → `eip712.json` digests unchanged; the ABI and bytecode change → `export-abi.sh`, `fetch-wyec.sh` pin, `eth/README.md` (`LOW-05-T-1` makes the stamp follow the pin).

## 5. Tests

- wyec: `test_Successor_PredecessorConsumedBlocksMint`: mint `L` on bridge A; deploy B with `predecessor = A`; `A.setBridge(B)`; `B.mint(L, …)` with B's guardians' signatures → `LockConsumed(L)`; `B.proposeMint(L, …)` → `LockConsumed(L)`; a fresh `L2` mints on B; chain of three (C with predecessor B) still refuses `L`. `test_Successor_OldBridgeCannotMintAfterHandoff`: `A.mint(L3)` after `setBridge` → `NotBridge(A)` from the token. Gas snapshot for `mint` with/without predecessor.
- Hawkeye store: `sign_once_mint` across two deployments with equal/different `(amount, to)`; migration keeps rows with the backfilled deployment.
- `tests/engine.rs` `s_migration_reproposes_pending_and_never_remints`: three engines on bridge A; lock `L1` minted, `L2` signed-not-minted; deploy B with predecessor A, hand off, switch the engines' `foreign` to B; `L2` is proposed and minted on B with new signatures (no `SignOnceConflict`); `L1` is never proposed (consumed via predecessor).

## 6. Acceptance criteria

1. On the successor, every lockId consumed by any predecessor reverts `LockConsumed` on both mint paths; proven for a chain of three.
2. A lock signed but unminted before a migration is minted on the successor by the same attestors without manual ledger surgery.
3. The `(amount, to)`-per-lock invariant holds across deployments at the SQLite level (trigger test).
4. `wyec-contract-design.md` §4.6 documents the migration; `README`/runbook cross-link.

## 7. Risks and side effects

- **Contract redeploy**: constructor signature changes (new last argument); Hawkeye's `DeployParams` and devnet scripts update; the Sepolia deployment is redone. Combine with `HIGH-05-H-2`'s constructor floors so the external audit sees one constructor change.
- **Gas**: +1 `STATICCALL` per mint only when a predecessor exists.
- **Migration itself** is an operational event (runbook); the first mainnet deployment has `predecessor = 0` and is unaffected.
- No node change, no key rotation forced.

## 8. Effort estimate and dependencies

wyec 1 day; Hawkeye store/engine/bindings 1.5 days; tests 1 day. **≈ 3.5 days.** Depends on `LOW-05-T-1` (pin stamp) and should share the re-pin with `HIGH-05-H-2`.
