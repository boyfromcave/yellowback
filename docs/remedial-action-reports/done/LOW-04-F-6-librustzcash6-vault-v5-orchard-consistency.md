# LOW — 04/F-6 — librustzcash6: `BranchId::Vault.has_orchard()` and `V5.is_valid_for_branch(Vault)` are permissive while the node (and `suggested_for_branch`) say v4-only

**Repos / branches to change:** `librustzcash6` (`components/zcash_protocol/src/consensus.rs`, `zcash_primitives/src/transaction/mod.rs`, tests), branch `fix/04-F-6-vault-v5-consistency` off `upgrade/vault`; `ycash6` (`Cargo.toml` `[patch.crates-io]` revs + `Cargo.lock`), branch `fix/04-F-6-librustzcash6-pin` off `upgrade/vault`.
**Audit source:** `04-cross-line-parity-activation.md` §F-6 (`:203-225`); `verification/04-verification.md` row F-6 (`:71`), detail (`:114-118`).
**Status:** done — completed 2026-10-13T11:21Z (merged locally on `upgrade/vault`; not yet pushed) — **blocked on the 04/F-2 decision** (report `MEDIUM-04-F-2-ycash6-v5-under-vault.md`).

## 1. Finding

The patched librustzcash wires `BranchId::Vault` into every match (verified: no panic path for Sapling verification, the v4 sighash is C++ on both lines, Rust is reached only for a ZIP-244 digest of a v5 transaction and for history-tree leaves). Three answers encode the opposite of the node's rule that Vault "does not itself bring Orchard" and that transactions stay v4: `has_orchard(Vault) = true`, `TxVersion::V5.is_valid_for_branch(Vault) = true`, while `suggested_for_branch(Vault) = V4` and `history.rs` maps Vault to V1 (no-Orchard) leaves. Dormant today — the C++ side admits v5 only under NU5, which has no height — but if 04/F-2 is resolved as "v5 invalid under Vault", the crate and the node must agree, and `has_orchard`'s wallet-side callers (`zcash_client_backend` input selection, `zcash_client_sqlite` encoding) would otherwise treat a Vault-epoch wallet as Orchard-capable. The pinned rev `4867cf85` is an ancestor of HEAD `48b544e` with only a rustfmt change between them. Verified Low.

## 2. Root cause

librustzcash6 `48b544e`:
- `components/zcash_protocol/src/consensus.rs:952-964` `has_orchard`: `Nu5 | Nu6 | Nu6_1 | Nu6_2 | Vault => true` with the comment "Vault does not itself bring Orchard … Orchard is present only where ycashd's NU5 gate admits it".
- `zcash_primitives/src/transaction/mod.rs:229-243` `suggested_for_branch`: `BranchId::Vault => TxVersion::V4` ("Ycash activates Vault without NU5: transactions stay v4"); `is_valid_for_branch` (same file, the `V5` arm) lists `Vault` among the branches where V5 is valid; `ProofSizeEnforcement::Strict` for Vault.
- `components/zcash_protocol/src/local_consensus.rs:228-245` `regtest_vault_without_nu5` test (Vault over Overwinter + Sapling only).
- ycash6 `e866c45` `Cargo.toml:131-136` pins every `zcash_*` crate to `4867cf85…`; `src/rust/src/history.rs:50-62` Vault → V1 leaves; ycash6's C++ gates v5 on NU5 (`src/main.cpp:1097-1103`, `:1205-1231`).

## 3. Fix options considered

1. Leave permissive and dormant; document. Rejected if F-2 picks "v5 invalid" (the crate would contradict a consensus rule); acceptable only if F-2 picks "define ZIP-244 under Vault", in which case only `has_orchard` is wrong.
2. **Make the crate say what the node enforces:** `has_orchard(Vault) => false`; `V5.is_valid_for_branch(Vault) => false` (V4 stays valid); keep `suggested_for_branch = V4` and `ProofSizeEnforcement::Strict`; add unit tests; re-pin ycash6. **Recommended, conditional on F-2 option (a).**

## 4. Recommended fix

librustzcash6:
1. `consensus.rs:952-964`: move `Vault` to the `false` arm of `has_orchard` and reword the comment ("Vault is a v4/Sapling-era upgrade on Ycash: no Orchard, no v5 (ycash6 `ContextualCheckTransaction`, quantum spec rule <F-2's rule id>)"). Check `has_sapling`, `has_zip212`, `has_blossom` etc. still answer `true` for Vault (they must: Vault is after Canopy).
2. `transaction/mod.rs`: in `is_valid_for_branch`, remove `Vault` from the `V5` arm and add it to the `V4` arm (the `Sapling | Ycash | Blossom | Heartwood | Canopy` list), so `V4.is_valid_for_branch(Vault) == true` and `V5.is_valid_for_branch(Vault) == false`. Review the proptest at the same site (`Just(V4)` for Vault already, per 04).
3. Tests: `consensus.rs` unit test (`vault_branch_id_round_trip` exists) gains `assert!(!BranchId::Vault.has_orchard())`, `assert!(BranchId::Vault.has_sapling())`; `transaction/mod.rs` gains `assert!(TxVersion::V4.is_valid_for_branch(BranchId::Vault)); assert!(!TxVersion::V5.is_valid_for_branch(BranchId::Vault)); assert_eq!(TxVersion::suggested_for_branch(BranchId::Vault), TxVersion::V4)`; `local_consensus.rs` `regtest_vault_without_nu5` unchanged.
4. `cargo test --locked -p zcash_protocol -p zcash_primitives`; commit; note the rev.

ycash6:
5. `Cargo.toml:131-136`: bump all six `rev =` to the new librustzcash6 commit; `cargo update -p zcash_protocol …` or regenerate `Cargo.lock` entries (`Cargo.lock:3141` region); build `--locked`; run `test_bitcoin` (the Rust FFI tests) and the functional merge-gate shards.
6. `grep -rn 'has_orchard\|is_valid_for_branch' ycash6/src/rust` — confirm no C++-reachable path consults them for Vault (04 found only wallet-side crate callers); record the grep in the PR.
7. Workspace: `CLAUDE.md`/`repos.yaml` record the librustzcash6 rev ycash6 pins ("`4867cf85`") — update both and `docs/mapping.md` §19/§22 (rule 5).

Consensus footprint: none in C++. In Rust, the ZIP-244 digest path is never reached for v4 and, after F-2, a v5 transaction is rejected before any Rust call; `history.rs` already builds V1 leaves for Vault.

## 5. Tests

As in §4 steps 3 and 5; plus ycash6's `vault_upgrade.py` and `yellowback_*` suites after the re-pin (they exercise the Rust FFI through Sapling spends in every block).

## 6. Acceptance criteria

- `cargo test --locked` green in librustzcash6 with the four new assertions; ycash6 builds `--locked` against the new rev; `make check` + functional shards green on ycash6.
- Workspace pins (`CLAUDE.md`, `repos.yaml`, `docs/mapping.md`) name the new rev.

## 7. Risks and side effects

- If F-2 resolves to option (b) (define ZIP-244 under Vault), do **not** apply step 2; apply only `has_orchard` (step 1) and adjust the tests.
- A librustzcash6 re-pin touches every `zcash_*` crate ycash6 links; the `--locked` build and the full test tier are the guard. `harden/yellowback` keeps librustzcash6 zero-delta and is unaffected.

## 8. Effort estimate and dependencies

~1–2 hours in librustzcash6, ~1 hour re-pin and CI cycle in ycash6. **Depends on** `MEDIUM-04-F-2-ycash6-v5-under-vault.md` (the rule decision) and should merge after it, in the same release.

## Completion record

- **Completed:** 2026-10-13T11:21Z
- **Merged:** librustzcash6 c78c8ff1 (eeb7740d: Vault v4-only, has_orchard false); ycash6 Cargo pin 4089d680e. cargo test zcash_protocol 15 passed. **Push order:** librustzcash6 before ycash6.
- **Verification:** Integration run 2026-10-13 (both node lines built; full test_bitcoin dd 872/872, ycash6 923/923; qa/yellowback-audit.sh dd --mode upgrade rc 0 (18 PASS), ycash6 --report-only rc 0; functional suites pass; vault_vectors / golden / pq vectors byte-identical across lines). Logs: wt/scratch/integ/.
