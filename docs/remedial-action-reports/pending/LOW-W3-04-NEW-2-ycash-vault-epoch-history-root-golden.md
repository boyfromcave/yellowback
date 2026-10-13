# LOW — 04/NEW-2 (+ the history-root half of W3-P-8) — A shared golden for the Vault-epoch ZIP-221 history root; ycash-dd checks `chainhistoryroot`

**Repos / branches to change:** `ycash-dd` and `ycash6` (both), new branch `fix/W3-04-NEW-2-vault-history-golden` off `upgrade/vault` in each. New test data, a generator and tests only; no consensus or Rust source change.
**Audit source:** `docs/audits/quantum-vault-ecosystem-wave3/verification/04-verification.md:66-76` (NEW-2), `:31` (the re-derivation of both Rust paths); `docs/audits/quantum-vault-ecosystem-wave3/04-cross-line-parity-activation.md:259-264` (W3-P-8: `vault_upgrade.py` written twice; ycash6 checks the history tree reset, ycash-dd does not); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:52` and priority 5 (`:104`). Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:104` (STILL OPEN, Δ-free); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`, none of which this report cites; still no history vector in `src/test/data` and no `chainhistoryroot` in dd's `vault_upgrade.py`.
**Status:** pending

## 1. Finding

`hashLightClientRoot` (`hashBlockCommitments` on 6.20.0) is a header-committed value: every node recomputes it in `ConnectBlock` and rejects a block whose header disagrees. It is the one consensus value that the two lines compute through **different versions of a Rust crate**. ycash-dd calls `librustzcash_mmr_append` over `zcash_history` 0.2. ycash6 calls its own `history.rs`, which dispatches `BranchId::Vault` to the V1 tree of `zcash_history` 0.4. Both are meant to produce V1 leaves under the Vault branch ID (`ZcashHistory` ‖ LE32(0x6d5b7a31) BLAKE2b personalisation). Nothing ties the two together. No vector file holds a Vault-epoch history node or root. ycash6's `vault_upgrade.py` checks the roots at `ACT+1` and `ACT+2` against the Python model (`flyclient.py`), and ycash-dd's `vault_upgrade.py` does not read `chainhistoryroot` at all.

Failure scenario: a dependency bump on either line (`zcash_history` 0.2 → 0.3 on dd, or a librustzcash6 change to the V1 path or to the `cbranch` personalisation) changes a V1 leaf encoding or node hash in the Vault epoch. That line's unit and functional suites stay green: dd checks nothing, and ycash6 checks only against its own Python model. The first block after activation then has a header root that the other line rejects, a header-level chain split at the first Vault block. The verifier rated this Low (test fidelity): today both paths are equivalent by inspection and ycash6's functional cell holds the line on one side.

## 2. Root cause

ycash-dd `da5e0fe`, ycash6 `0742e43`, librustzcash6 `c78c8ff` (re-verified):

- **ycash-dd Rust:** `src/rust/src/rustzcash.rs:1110-1125` (`librustzcash_mmr_append(cbranch, …)`), entries decoded with `MMREntry::from_bytes(cbranch, …)` (`:1098`). `Cargo.toml:35` `zcash_history = "0.2"`; `Cargo.lock:1490-1492` `zcash_history 0.2.0`.
- **ycash6 Rust:** `src/rust/src/history.rs:49-61` (`dispatch`: `Sprout | Overwinter | Sapling | Heartwood | Canopy | Vault => v1`, everything else V2). `Cargo.toml:67` `zcash_history = "0.4"`; `Cargo.lock:3062-3064` `0.4.0`. `BranchId::Vault` comes from librustzcash6 (pinned `eeb7740d`, `Cargo.toml:131-136`).
- **C++ call sites:** ycash-dd `src/main.cpp:3438` (`block.hashLightClientRoot != view.GetHistoryRoot(prevConsensusBranchId)`), `:3465` (`PushHistoryNode(consensusBranchId, …)`); ycash6 `src/main.cpp:4256-4300`, template side `:6374`. Leaf constructors: `libzcash::NewLeaf` (dd `src/zcash/History.hpp:45`), `libzcash::NewV1Leaf` / `NewV2Leaf` (ycash6 `History.hpp:52,63`).
- **Tests:** ycash6 `qa/rpc-tests/vault_upgrade.py:182-193` (`history_leaf` → `ZcashMMRNode.from_block(header, height, sapling_root, sapling_tx, branch_id, None)`), `:285-294` (roots at `ACT+1`, `ACT+2`). `grep -n chainhistoryroot ycash-dd/qa/rpc-tests/vault_upgrade.py` finds nothing. The gtests `src/gtest/test_history.cpp` (both lines) use Heartwood/branch `3` leaves only, never the Vault branch ID, and dd runs gtests only in the nightly. None of the nine `src/test/data` files has a history node (`grep -l -i history src/test/data/*.json` finds nothing).
- **Python model:** `qa/rpc-tests/test_framework/flyclient.py`, which differs between the lines. dd imports `pyblake2` (shimmed to `hashlib` in CI, `yellowback-tests.yml:631-635`) and its `from_block` has no `v2_data` argument. ycash6 imports `hashlib.blake2b` and adds V2 fields. The V1 serialisation (`serialize`, `make_parent`, `make_root_commitment`, `H` with `b'ZcashHistory' + LE32(branch)`) is the same logic on both.

## 3. Fix options considered

1. **The verifier's suggestion as written: record the regtest roots at `ACT+1`/`ACT+2` "deterministic from the golden chain" in a shared vector.** A regtest chain is not deterministic across runs. Header `nTime` follows the wall clock or mocktime, coinbase outputs follow the wallet's fresh keys, and the Equihash solution follows the nonce, so the roots differ per run unless the whole chain is pinned. Rejected as the vector source. The functional cell stays a *model* check (below), as on ycash6.
2. **A synthetic golden: fixed leaf inputs → expected V1 leaf bytes, node hashes and root commitments under the Vault branch ID, replayed by both lines' C++ through each line's own Rust.** Deterministic, cheap (no node, no chain), and it exercises exactly the code that differs (crate version and FFI glue). **Recommended**, together with porting ycash6's functional cell to dd.
3. **Pin both lines to the same `zcash_history` version.** Not possible without a Rust toolchain/edition move on the v4.5.0 line. It would also not remove the need for a vector, since a future bump on either side must still be caught.

## 4. Recommended fix

### A. The vector: `src/test/data/vault_history_vectors.json` (new; the tenth shared vector file)

Generated by `qa/rpc-tests/test_framework/gen_vault_history_vectors.py` (new, byte-identical on both lines; `--check` mode as `gen_vault_vectors.py` does). It uses a **self-contained** V1 model copied into the generator: about 60 lines of `serialize` / `make_parent` / `make_root_commitment` / `append` from `flyclient.py`, with `hashlib.blake2b`. This keeps it independent of the two differing `flyclient.py` copies. Content:
```json
{"comment": "ZIP-221 V1 history tree under the Vault branch ID 0x6d5b7a31 (audit 04/NEW-2) ...",
 "branchId": "6d5b7a31",
 "leaves": [ {"blockHash": "...", "time": 1700000000, "target": 520617983, "saplingRoot": "...",
              "totalWork": "...", "height": 130, "saplingTxCount": 0,
              "node": "<244-byte V1 node data, hex>"}, ... 7 leaves ],
 "roots": [ {"leaves": 1, "commitment": "<32-byte hex>"}, ..., {"leaves": 7, "commitment": "..."} ],
 "controls": [ {"branchId": "e9ff75a6", "leaves": 3, "commitment": "..."} ] }
```
- Seven leaves give peaks of every shape up to a 3-peak tree (1, 2, 3, 4, 5, 6 and 7 leaves; the bagging path at 3, 5, 6 and 7).
- Leaf inputs are derived deterministically (`blockHash = sha256("vault-history" ‖ i)`, `time = 1700000000 + 75·i`, non-trivial `saplingTxCount` on two leaves, heights starting at 130 to mirror `ACT`).
- The `controls` row is the same three leaves under the **Canopy** branch ID (`e9ff75a6`). It proves the personalisation is actually bound: the commitment must differ from the Vault one.

Add the file to `src/Makefile.test.include` (`:47-55`, both lines) and to the cross-line manifest (MEDIUM-W3-P-2). Add the generator to the manifest too.

### B. The C++ replay (both lines, in `test_bitcoin`, not the nightly-only gtest)

New Boost case `vault_history_vectors` in `src/test/vault_vectors_tests.cpp` (it already loads `vault_vectors.json`; both lines):
1. For each leaf, build the node with the line's constructor. The two signatures are the same (`commitment, time, target, saplingRoot, totalWork, height, saplingTxCount`): dd `libzcash::NewLeaf` (`History.hpp:45-53`), ycash6 `libzcash::NewV1Leaf` (`History.hpp:52-60`). So the vector carries `totalWork` explicitly as a 32-byte hex per leaf, generated as `ConnectBlock` would (`GetBlockProof` of `target`), but simply recorded, not recomputed in the test. Assert the 244-byte serialisation equals `node`. The JSON enters the test through the generated header, as `vault_vectors.json` does (`vault_vectors_tests.cpp:14,57`: `JSON_TEST_FILES` → `test/data/vault_history_vectors.json.h`).
2. Push the leaves one by one into a `CCoinsViewCache` over an empty fake view with `PushHistoryNode(0x6d5b7a31, node)`, and after each push assert `GetHistoryRoot(0x6d5b7a31) == roots[k].commitment`. `coins_tests.cpp` on both lines already has a fake `CCoinsView` with `GetHistoryLength` / `GetHistoryAt`; reuse it, or copy the 10-line fake from `gtest/test_history.cpp:8-63`.
3. Controls: the same with the Canopy branch ID, and assert the commitment differs from the Vault one at the same leaf count.
4. One negative: flip one byte of leaf 2's `saplingRoot`; the root at 3 leaves must change.

This runs through `librustzcash_mmr_append` / `zcash_history` 0.2 on dd and `history.rs` / `zcash_history` 0.4 V1 on ycash6, against the same bytes.

### C. ycash-dd functional cell (W3-P-8's history half)

Port ycash6's `vault_upgrade.py:182-193` (`history_leaf`) and `:285-294` (the two root assertions) into `ycash-dd/qa/rpc-tests/vault_upgrade.py`, after its post-activation wallet sends (dd `ACT = 130`, `:70`). Adaptations:
- dd's `flyclient.ZcashMMRNode.from_block(Z, block, height, sapling_root, sapling_tx_count, consensusBranchId)` has no sixth argument: drop the trailing `None`.
- Import `ZcashMMRNode, append, make_root_commitment` from `test_framework.flyclient`. dd's `flyclient.py` imports `pyblake2`; the functional CI job must have the same shim as the `python` job (`yellowback-tests.yml:631-635`), or change the import to `from hashlib import blake2b` (stdlib since 3.6, as ycash6 already does). The import change is the smaller fix, but `flyclient.py` is an inherited framework file; mark the one-line change in a comment.
- dd's topology is mainnet-shaped (Canopy at 1, NU5 unscheduled, Vault at `ACT`). Block `ACT` still commits the Canopy epoch's tree; `ACT+1` commits the one-leaf Vault tree. Same expectations as ycash6.
- Add the cell's rule tag (if the line's `leg_rule_tags` vocabulary has one for U-9/ZIP-221; otherwise a comment) and update the docstring's bullet list at `:6-23`.

### D. Docs

`qa/rpc-tests/test_framework/VAULT_VECTORS.md` (identical on both lines): a section "vault_history_vectors.json" (what it pins, the generator, the control row). `docs/mapping.md` §22: one row ("ZIP-221 history in the Vault epoch: dd `zcash_history` 0.2 via `librustzcash_mmr_append`, ycash6 0.4 V1 via `history.rs` dispatch → shared vector `vault_history_vectors.json`") with the citations above. The spec (`docs/plans/yellowback-upgrade-plan.md`, wherever U-9's "V1 leaves under Vault" is stated) cites the vector.

## 5. Tests

- `vault_history_vectors` (B) on both lines in the default `test_bitcoin` run (so in every push CI and in the ASan/UBSan `vault_*` filter).
- `gen_vault_history_vectors.py --check` in both `python` jobs next to `gen_vault_vectors.py --check` (dd `:676-677`; ycash6 equivalent): a hand-edited vector fails.
- dd `vault_upgrade.py` with the two new assertions.
- **Would-have-caught proof, once, in the PR:** change the personalisation constant in the generator's model (`b'ZcashHistory'` → `b'ZcashHistorz'`), regenerate, and run `test_bitcoin --run_test=vault_vectors_tests/vault_history_vectors` on both lines: both fail at leaf 1. Equivalently, temporarily route `BranchId::Vault` to `v2` in ycash6's `history.rs:58` dispatch and watch ycash6 alone fail while dd passes, which is exactly the split this vector exists to catch. Revert both.

## 6. Acceptance criteria

- `src/test/data/vault_history_vectors.json` and its generator are byte-identical on both lines, listed in both `Makefile.test.include`, and in the cross-line manifest.
- `vault_history_vectors` passes on both lines and replays every leaf, every root and the control.
- `ycash-dd/qa/rpc-tests/vault_upgrade.py` asserts `chainhistoryroot` at `ACT+1` and `ACT+2` against the model.
- The "would-have-caught" runs are recorded in the PR.
- `VAULT_VECTORS.md` and `docs/mapping.md` updated.

## 7. Risks and side effects

- None to consensus. New tests only.
- **Leaf encoding drift:** dd's `NewLeaf` and ycash6's `NewV1Leaf` take the same arguments but are implemented by different crate versions. That is the point of the leaf-bytes assertion; if they disagree on bytes, stop and treat it as a finding, not a test to adjust.
- **`pyblake2` on dd:** changing `flyclient.py`'s import touches an inherited file. The alternative (shim in the functional job) is equally small. Either way, record it.
- Vector freeze: the file pins V1 behaviour under Vault. A future decision to move Vault to V2 leaves (only meaningful with NU5, which R-A3 refuses) regenerates it on both lines together.

## 8. Effort estimate and dependencies

- ~1 day: generator and vector (0.25), C++ replay on two lines with the constructor differences (0.5), dd functional port (0.25). One reviewer.
- **Depends on:** MEDIUM-W3-P-2 (the manifest that carries the new files). Pairs with INFO-W3-P-7-P-8-P-9 (the rest of the `vault_upgrade.py` reconciliation). Independent of the consensus reports.
