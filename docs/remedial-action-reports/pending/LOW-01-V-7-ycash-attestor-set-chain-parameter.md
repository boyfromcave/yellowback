# LOW — 01/V-7 — Primitive set state depends on the node-local `-yellowbackattestorset` (the P8 chain-parameter item)

**Repos / branches to change:** `ycash-dd` and `ycash6` (`src/yellowback/params.cpp`, `src/yellowback/index.h`, `src/init.cpp`, `src/rpc/vault.cpp`/`yellowback.cpp`, `doc/`), branch `fix/01-V-7-attestor-set-chain-param` off `upgrade/vault` in each; `yellowback` workspace (upgrade plan P8 row, `docs/mapping.md`); `contrib/yellowback/devnet` walk assertion.
**Audit source:** `01-vault-primitive-consensus.md` §V-7 (`:133-141`); `verification/01-verification.md` row V-7 (`:20`), detail (`:132-137`); related `07-node-rpc-mempool-durability-ci.md` §F-4 (`:147-173`) and `04-cross-line-parity-activation.md` §F-7 (`:227-249`, release refusal of an unset mainnet set).
**Status:** pending (P8).

## 1. Finding

The YED module's hooks that *mutate* primitive set state — equivocation ejections, the liveness `lastAct` update, displacement — and its `ValidateSpend` rule answer from `yellowback::CurrentParams()`, which is built from the chain parameters plus, on regtest, the node-local `-yellowbackattestorset=<setid>`. When the parameter is unset the hooks return the inert value (no governed set, no ejections, no liveness, no spend rule). So two nodes started with different `-yellowbackattestorset` values compute different member records, bond freezes and spend verdicts for the same blocks: different `statehash`, and a block valid on one and invalid on the other (`ValidateSpend` rejects `SEL_UNLOCK` on a YED vault only where configured).

Today this is regtest/devnet-only: mainnet and testnet have no attestor set at all (plan P8 sets the mainnet set with the gate-passing release; the ycash6 release workflow refuses a tag with it unset), so no two public-network nodes can disagree. The audit reported it because the divergence lives in the primitive's `ApplyTx`, and because the devnet walk (`07/F-4`, commit `055d9c2`) had to drop the stock node from its hash comparison for exactly this reason. Verified Low until P8.

## 2. Root cause

ycash-dd `055d9c2` (ycash6 `e866c45` identical in `src/vault`, `src/yellowback/module.cpp`, `params.cpp`):
- `src/vault/state.cpp:633-657` `ApplyEjectionsOf`: `module.GovernedSet()`, `Ejections`, `Liveness` → writes `MemberRecord` / freezes bonds; `:731-757` the displacement path (`Displace`).
- `src/yellowback/module.cpp:78-91` `ValidateSpend` and `GovernedSet` return `nullopt` when `CurrentParams()` is null; `:93-108` `Ejections`, `:138-163` `Liveness` likewise.
- `src/yellowback/index.h:479-481`: "attestorSetId the network's (regtest: `-yellowbackattestorset=<setid>`, mainnet and testnet unset)"; `src/init.cpp:438` (regtest-only, debug help), `:1360-1367` `ParamsFromArgs` → `SetModuleParams` (before `Reconcile` at `:1957`, so replay and live agree on one node — verifier); `src/yellowback/params.cpp:164` (U-22), `:212-269` `RegtestParams(..., attestorSetId)`.
- Plan: `docs/plans/yellowback-upgrade-plan.md:1108` finding (74) ("a node without `-yellowbackattestorset` after the upgrade runs the YED module inert"); `:710` P8 row ("activation height and … set by this release"); `ycash6/qa/yellowback-release-heights.sh` refuses an unset or all-zero mainnet `attestorSetId` (04/F-7).

## 3. Fix options considered

1. **Make the attestor set a consensus chain parameter** on every network (mainnet/testnet constants in `params.cpp` set by P8; regtest from `-yellowbackattestorset`, as now) and make the module hooks *never* inert where `UPGRADE_VAULT` has a height: a node on a network whose set is unset refuses to start (`InitError`) rather than validating inertly. This is the P8 plan already; the audit adds the "never inert on a public network" rule. **Recommended.**
2. Move the set id into the block chain itself (e.g. the activation block's coinbase commits the set id): larger consensus surface, nothing it buys over a chain parameter for a fixed-at-release set. Rejected (prime directive).
3. Pre-P8 only: documentation + tooling so regtest/devnet operators cannot run mismatched nodes unnoticed. **Recommended now**, as the deliverable before P8.

## 4. Recommended fix

**Now (pre-P8, both lines):**
1. `vault_getinfo` / `yed_getinfo`: expose `attestorsetid` (hex or null) and `moduleactive` (bool) so tests and operators can compare the configured set across nodes. `doc/vault-rpc.md` and the contract JSONs regenerated (`qa/vault-rpc-contract.py`; rpcversion bump only if the contract tool demands one).
2. `init.cpp` (`:1360-1367`): log one line at start ("Yellowback: attestor set <id> (regtest -yellowbackattestorset)" or "Yellowback: no attestor set; the YED module validates inertly on this network") so a mismatch is visible in `debug.log`.
3. `contrib/yellowback/devnet/upgrade-walk` and `qa/rpc-tests/yellowback_devnet_upgrade.py`: assert every module node reports the same `attestorsetid`, and (07/F-4's positive assertion) that the stock node's state hash differs from the module nodes' **only** in the attestor set's `MemberRecord.lastAct` fields (dump via `set_getinfo <id> withmembers` on both and diff), so a primitive-level divergence on the stock node fails the walk again.
4. `doc/yellowback-devnet.md` and `doc/yellowback-attestor.md`: "every validating node of a regtest/devnet network must be started with the same `-yellowbackattestorset`; nodes without it compute different set state and may reject blocks the others accept".
5. `docs/mapping.md` §22 row: "module-governed set state is a function of a node parameter until P8" with the citations above.

**At P8 (consensus, review gate, both lines):**
6. `params.cpp` `MainParams`/`TestParams`: the registered set id (the release sets it; `yellowback-release-heights.sh` already gates it).
7. `init.cpp`: `if (UPGRADE_VAULT has a height && !params.IsConfigured()) return InitError("Yellowback: this network's attestor set is unset; this build cannot validate the vault upgrade")` on mainnet/testnet; regtest keeps the flag and the inert mode for primitive-only suites, but the devnet walk never uses it.
8. Four-part check for the PR body: *DigiByte has no module-governed set; its oracle set is a chain constant in `chainparams`. The Ycash equivalent is `yellowback::Params::attestorSetId`, which today is a runtime argument on regtest and unset elsewhere. The adaptation is a chain parameter per network with a start-time refusal when unset.* Tier: a chain parameter, no new field or opcode.

## 5. Tests

- Functional (now): `yellowback_devnet_upgrade.py` / the walk assert equal `attestorsetid` across module nodes and the exact-field hash difference against the stock node.
- Functional (now): a two-node regtest case in `yellowback_void_mint.py` or a new `yellowback_module_params.py`: node A with the set, node B without; mine a block with an attestation-based ejection (or a YED `SEL_UNLOCK` attempt); assert the two `vault_getinfo.statehash` differ and that B accepts a block A rejects — **documenting** the pre-P8 divergence so the P8 change has a test to invert (at P8 the case becomes "B refuses to start").
- Unit: `src/test/yellowback_params_tests.cpp` (or the existing params test): `ParamsFromArgs` on mainnet with the set constant unset → not configured (today) / error (P8).

## 6. Acceptance criteria

- Pre-P8: RPC field, start-up log line, devnet-walk assertions, docs and mapping row landed on both lines; `make spec-check` clean if the plan text changes.
- P8: mainnet/testnet set ids in `params.cpp`; a public-network build with the set unset refuses to start; the devnet walk's module nodes and the Python `VaultModel` (with its liveness hook wired, `db1831d`) agree on the state hash.

## 7. Risks and side effects

- Pre-P8 changes are non-consensus. The P8 refusal is a start-up behaviour change for public-network nodes only after the release that sets the constants — intended.
- The rpcversion contract: adding read-only fields to `vault_getinfo` is additive; confirm with `qa/vault-rpc-contract.py` whether the contract generator treats new fields as a version bump (lightwalletd and chain-viz read `vault_getinfo`).

## 8. Effort estimate and dependencies

Pre-P8 work: ~1 day both lines (RPC field, walk assertion, docs). P8 part: owned by the release plan (P8), depends on the registered set (P7 gates) and on 07/F-4's walk rework (shares the assertion). Related: 03/I-3 (pin `cancelThreshold`/`unlockThreshold` in `AdoptedSet`, report R1).
