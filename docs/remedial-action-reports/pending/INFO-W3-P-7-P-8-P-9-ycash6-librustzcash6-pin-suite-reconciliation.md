# INFO — W3-P-7, W3-P-8, W3-P-9 — Pin librustzcash6 at its branch head; reconcile the two `vault_upgrade.py` cell sets; record the v5-under-Vault reason-string difference for a future NU5

**Repos / branches to change:** `ycash6` (`Cargo.toml`/`Cargo.lock` re-pin; `vault_upgrade.py` cells), `ycash-dd` (`vault_upgrade.py` cells), branch `fix/W3-P-7-pin-and-cells` off `upgrade/vault` in each. The workspace gets `CLAUDE.md` / `repos.yaml` / `docs/mapping.md` pin text and a plan checklist line. No consensus, Rust-source or node-behaviour change.
**Audit source:** `docs/audits/quantum-vault-ecosystem-wave3/04-cross-line-parity-activation.md:240-246` (W3-P-7), `:248-274` (W3-P-8), `:276-291` (W3-P-9); `docs/audits/quantum-vault-ecosystem-wave3/verification/04-verification.md:46-48` (all three CONFIRMED, Info); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:52`. Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:103` (STILL OPEN: librustzcash6 still `c78c8ff`, `ycash6/Cargo.toml` and `vault_upgrade.py` unchanged); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open (librustzcash6 HEAD `c78c8ff`, `ycash6/Cargo.toml` still pins `eeb7740d`); the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`. The `cargo test` citation is corrected to the job that runs it.
**Status:** pending

## 1. Finding

Three bookkeeping items. Each is Info; none affects what either node accepts.

- **W3-P-7.** `ycash6/Cargo.toml` and `Cargo.lock` pin `boyfromcave/librustzcash6` at `eeb7740d`. The repository's `upgrade/vault` head is `c78c8ff`, a merge (`Merge fix/ycash6-v5 into upgrade/vault`) whose tree equals `eeb7740d`. The build is exactly the audited source. But the pin, the branch head, `git describe` and the workspace's `CLAUDE.md`/`repos.yaml` name two different commits, and the next reader has to prove they are the same tree.
- **W3-P-8.** `vault_upgrade.py` was written twice rather than ported. ycash-dd (359 lines) checks the mainnet-shaped topology (NU5 unscheduled; `PrevEpochBranchId` walk-back Canopy→Vault). ycash6 (398 lines) checks the ZIP-221 history-tree reset with V1 leaves under Vault and the NU5..NU6.2 refusal. Each checks things the other does not. `YELLOWBACK_SCRIPTS` differs by three 6.20.0-only suites (ZIP-317/401/wallet flags, legitimately line-specific). `SANITIZER_SCRIPTS` runs `vault_upgrade` on ycash-dd only. Unit case counts differ in four suites by exactly the documented line-specific additions.
- **W3-P-9.** On ycash6 the port's `bad-vault-tx-version-group-id` rule sits inside `if (nu5Active)`. On every startable network (NU5 unset; `init.cpp` refuses NU5..NU6.2 with Vault) a v5 transaction is rejected one rule earlier as `bad-sapling-tx-version-group-id`. ycash-dd cannot deserialise v5 at all. The outcome is the same and the reason string differs. Nothing to fix. A future NU5 activation on Ycash must revisit U-26 on both lines together; mapping §22 records this already.

## 2. Root cause

ycash-dd `da5e0fe`, ycash6 `0742e43`, librustzcash6 `c78c8ff` (re-verified):

- **P-7:** `ycash6/Cargo.toml:130-136` (`[patch.crates-io]`, six crates at `rev = "eeb7740d771829ccde466340466cf13d27fa4e5b"`); `Cargo.lock` source lines `:758, :783, :3041, :3054, :3088, :3141, :3182`. `git -C librustzcash6 log --oneline -2`: `c78c8ff` (merge), `eeb7740` (the fix). Both are on `origin/upgrade/vault`. `git diff --stat eeb7740d c78c8ff` is empty (verifier). The two-commit description sits in the workspace's `CLAUDE.md:99-101`, `repos.yaml:115` and `docs/mapping.md:1211,1219`.
- **P-8:** `ycash-dd/qa/rpc-tests/vault_upgrade.py` (no `chainhistoryroot`; mainnet topology per its docstring `:8-13`); `ycash6/qa/rpc-tests/vault_upgrade.py:182-193, 285-294` (history), `:382-388` (R-A3 refusals). `YELLOWBACK_SCRIPTS`: `ycash-dd/.github/workflows/yellowback-tests.yml:94`, `ycash6/…:123`. `SANITIZER_SCRIPTS`: dd `:99`, ycash6 `:124`.
- **P-9:** `ycash6/src/main.cpp:1097-1105` (`bad-sapling-tx-version-group-id` while NU5 is inactive), `:1205-1226` (`bad-vault-tx-version-group-id` inside `if (nu5Active)`); `ycash6/src/init.cpp:1512-1530` (refuses NU5..NU6.2 with Vault); ycash-dd `src/main.cpp:1039`, `src/test/vault_script_tests.cpp:228-243`. librustzcash6 agrees (`TxVersion::V5.valid_in_branch(Vault) == false`, `BranchId::Vault.has_orchard() == false`).

## 3. Fix options considered

- **P-7:** (a) re-pin to `c78c8ff` (the branch head; the audit's recommendation), or (b) leave `eeb7740d` and state "tree-identical to the head" everywhere. (a) is one mechanical commit and removes a recurring question; recommended. Re-pinning to a commit with the same tree changes no compiled byte.
- **P-8:** (a) merge the two scripts into one shared file. Not possible: they test different topologies on purpose, and their framework helpers differ (`flyclient.py`, `yellowback_util.py`). (b) Each line gains the other's applicable cells. Recommended, as the audit says.
- **P-9:** move ycash6's `bad-vault-tx-version-group-id` out of `if (nu5Active)` so that the reason strings match. Rejected: it is a consensus-file edit (`main.cpp`, G-9 gate) for a reason string on an unreachable path. Record it instead.

## 4. Recommended fix

1. **P-7, ycash6.** In `Cargo.toml:131-136`, replace `eeb7740d771829ccde466340466cf13d27fa4e5b` with `c78c8ff`'s full hash in all six `rev =` entries. Then run `cargo update -p zcash_protocol`: the six crates share one git source, so the lock re-resolves all of them to the new rev. Confirm that the `Cargo.lock` diff touches only the seven `source = "git+…?rev=…#…"` lines and that no version number moved. If `qa/supply-chain/` (`audits.toml`, `imports.lock`, `config.toml`) records the librustzcash6 git source or rev, update it in the same commit (`grep -n librustzcash6 qa/supply-chain/*`; nothing today). Build once (`make -C src rust` or the CI `cargo test --locked`, ycash6 `yellowback-tests.yml:1028-1031`) and record that `src/rust` artefacts are unchanged.
   **Workspace:** `CLAUDE.md:99-101` ("pins every `zcash_*` crate to `boyfromcave/librustzcash6` at `eeb7740d`") becomes `c78c8ff` (tree = `eeb7740d`, audit 04/F-6 fix). Do the same for `repos.yaml:115` and `docs/mapping.md:1211,1219`. The workspace `CLAUDE.md` edit follows the workspace's own rules for that file: owner/coordinator commit.
2. **P-8, cell reconciliation.**
   - ycash-dd gains ycash6's history-tree cell. That is LOW-W3-04-NEW-2 part C; do it there, not twice.
   - ycash6 gains dd's mainnet-topology walk-back cell: with Canopy at 1 and NU5 unscheduled, assert `getblockchaininfo()['consensus']['chaintip']` moves from Canopy (`e9ff75a6`) to Vault at `ACT`, and that a Canopy-bound spend is `old-consensus-branch-id` naming Canopy, not NU5. ycash6 already asserts the latter (`:296-299`); add the explicit "names Canopy, not NU5" check dd makes at `vault_upgrade.py:286-288`.
   - ycash-dd gains ycash6's NU5 check where it is meaningful: dd has no NU5..NU6.2 R-A3 refusal (no v5 type), so it gets only a comment in its docstring saying why.
   - `SANITIZER_SCRIPTS` on ycash6 (`:124`): add `vault_upgrade` if the sanitizer job's time budget allows (dd runs it). Otherwise record in the workflow comment why not.
   - A short table in `doc/yellowback-testing.md` on both lines, "line-specific suites and cells", listing the three 6.20.0-only scripts, the four unit-suite count differences (`pq_script_tests` 19/21, `vault_script_tests` 12/11, `vault_state_tests` 35/36, `yellowback_txbuilder_tests` 20/22) with their case names, and the sanitizer-list difference. The next audit then compares against a stated expectation instead of rediscovering it.
3. **P-9.** No code. Add a line to the upgrade plan's (or quantum spec's R-A3 section's) "if Ycash ever schedules NU5" checklist: "move ycash6's `bad-vault-tx-version-group-id` (`main.cpp:1205-1226`) out of `if (nu5Active)` and decide v5 under Vault on both lines together (U-26; audit W3-P-9)". Mapping §22 line ~1218 already records the behaviour; add the audit ID.

## 5. Tests

- P-7: ycash6 CI green (whole `test_bitcoin`, `cargo test --locked`, functional list). The tree identity means no expected change. Record `git diff --stat eeb7740d c78c8ff` (empty) in the PR body.
- P-8: the added cells on each line pass. `vault_upgrade` under ycash6's sanitizer run, if added.
- P-9: none.

## 6. Acceptance criteria

- `ycash6/Cargo.toml` and `Cargo.lock` name `c78c8ff` (no `eeb7740d` left: `grep -c eeb7740d Cargo.toml Cargo.lock` = 0); the workspace pin text agrees.
- ycash6's `vault_upgrade.py` asserts the Canopy→Vault walk-back naming Canopy. ycash-dd's history cell lands via LOW-W3-04-NEW-2. `doc/yellowback-testing.md` on both lines lists the line-specific suites and counts.
- The NU5 checklist line exists in the plan; the mapping row cites W3-P-9.

## 7. Risks and side effects

- P-7: a git-dependency rev change re-fetches the crates into `~/.cargo/git` in CI (cache miss once). If `c78c8ff` were ever force-pushed away, the build would break. It is on `origin/upgrade/vault` today, and pinning a merge commit is no riskier than pinning its parent.
- P-8: test-only.
- P-9: none.

## 8. Effort estimate and dependencies

- ~0.5 day total (re-pin 1 h incl. CI; cells 2-3 h; docs 1 h). One reviewer.
- P-8's dd history cell is LOW-W3-04-NEW-2. The `vault_upgrade.py` edits overlap LOW-W3-P-4 and MEDIUM-W3-P-1 (protocol-version cell); land in one order and rebase. No other dependency.
