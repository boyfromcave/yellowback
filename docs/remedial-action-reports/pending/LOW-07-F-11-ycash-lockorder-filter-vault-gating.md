# LOW — 07/F-11 — Lockorder checker ignores `vault` locks; which nightly legs should gate

**Repos / branches to change:** `ycash-dd` (`qa/yellowback-lockorder-check.py`, `.github/workflows/yellowback-tests.yml`) and `ycash6` (same script at `:83`; its lockorder job at `yellowback-tests.yml:1433`), branch `fix/07-F-11-lockorder-vault` off `upgrade/vault` in each.
**Audit source:** `07-node-rpc-mempool-durability-ci.md` §F-11 (`:232-240`) and "Other fidelity notes" (`:295-298`); `verification/07-verification.md` row F-11 (`:21`, "Info; lockorder note: Low"), detail (`:110-114`).
**Status:** pending.

## 1. Finding

The nightly `lockorder` job builds with `--enable-debug` and `DEBUG_LOCKORDER_LOGONLY` (the aborting detector is tripped by stock Ycash's own `getpeerinfo`/`SendMessages` inversion on the first peer connection, so every inversion is only logged), runs the functional suite, and then `qa/yellowback-lockorder-check.py` is the sole gate: it groups every "POTENTIAL DEADLOCK DETECTED" report and **skips any report whose text lacks `yellowback` or `yed_`**. The vault primitive's locks and call sites — `VaultDB::cs` (`db.cpp`), `cs_main`/`mempool.cs` pairs in `src/vault/` and `src/rpc/vault.cpp`, the `set_*`/`vault_*` RPC frames — carry neither token, so a lock-order inversion introduced by the vault overlay is counted as "inherited" and passes. Separately, by design, the whole nightly tier (`make check`, stock parity, devnet walk, lockorder, sanitizers, coverage, weekly fuzz) "never blocks; opens an issue": a regression there is an issue, not a red PR. The filter bug is Low; the tier design is Info with a recommendation.

## 2. Root cause

ycash-dd `055d9c2`:
- `qa/yellowback-lockorder-check.py:49` `if 'yellowback' not in text and 'yed_' not in text: continue`; `:16` `ALLOWED = ({'cs_yellowback', 'ControlMutex'},)`; docstring `:6-14` (the one allow-listed pair and its proof).
- `src/vault/db.h:85` `mutable std::mutex cs;` (reports name it `cs` at `db.cpp:…`), `db.cpp:146` (`lock_guard` inside `ConnectBlock`), `src/rpc/vault.cpp` `LOCK2(cs_main, pwalletMain->cs_wallet)` frames; `src/vault/node.cpp` `TipSnapshot`/`RecheckMempool` under `cs_main` + `mempool.cs`.
- `.github/workflows/yellowback-tests.yml:5-20` (tier design), `:920-1000` (lockorder job: nightly/dispatch only, 600-minute budget, full depends + debug build, whole `YELLOWBACK_SCRIPTS` minus the two sidecar scripts, then the check script), `:1155` (`make check || true`), `:1007` (opens an issue). ycash6: `yellowback-tests.yml:1433-1457` (`qa/yellowback-lockorder-logonly.sh`), `qa/yellowback-lockorder-check.py:83`.

## 3. Fix options considered

**Filter**
1. Add `vault`, `Vault`, `set_` to the substring test. `set_` risks false positives on unrelated identifiers (`set_error` in `script_error`, `std::set`), but lockorder report lines name **lock variables and `file:line`**, so the practical risk is a `src/vault/` file path — which is exactly what we want to catch. Use a regex anchored on the tokens that appear in reports: `re.search(r'yellowback|yed_|/vault/|vault\.cpp|VaultDB|cs_vault|\bset_(sign|create|join|heartbeat|remove|winddown|getinfo|list)', text)`. **Recommended.**
2. Invert the filter: fail on every report **except** an allow-list of the known inherited pairs (`getpeerinfo`/`SendMessages` and the F-37 pair). Strictly stronger; requires enumerating stock Ycash's inversions once (the nightly logs have them). Recommended as the follow-up once the first run's inventory is reviewed; it removes the token-naming trap for good.

**Gating**
3. Make the entire nightly tier gating: not feasible (lockorder alone is a 10-hour budget; GitHub cannot gate a merge on a scheduled run).
4. Add a **path-filtered PR leg**: on `pull_request` whose changed files touch `src/vault/**`, `src/yellowback/**`, `src/rpc/vault.cpp`, `src/rpc/yellowback*.cpp`, `src/main.cpp`, `src/miner.cpp`, `src/txmempool.cpp`, run the DEBUG_LOCKORDER build (cached depends; ~20 min) over a short subset (`vault_primitive vault_rpc_contract vault_slashing vault_upgrade yellowback_index yellowback_void_mint yellowback_attest_live`) and the check script, gating. Keep the full run nightly. **Recommended.**
5. Same path filter for the sanitizers job's **unit-test** leg only (`test_bitcoin --run_test='vault_*,pq_*,yellowback_*'` under ASan/UBSan): minutes once built; gating on overlay paths. Recommended; the sanitizer functional run stays nightly.
6. The devnet walk, stock parity, coverage, weekly fuzz: stay nightly (hours; their failures are investigations, not merge blockers). Record the convention in the workflow header: an open nightly issue blocks the next release tag (ycash6's release workflow could check for open `lockorder failed` / `sanitizers failed` issues — optional).

## 4. Recommended fix

1. `qa/yellowback-lockorder-check.py` (both lines): replace the substring test at `:49` (y6 `:83`) with the regex of option 1; add `YELLOWBACK_TOKENS` at the top with a comment listing why each token is there; extend the docstring. Keep `ALLOWED` as is. Print, per report, which token matched (debuggability).
2. Run the nightly once by `workflow_dispatch` (`tier: nightly`) on both lines and review every report that the new tokens now surface; anything inherited from stock Ycash (not under `src/vault/`, `src/yellowback/`, `src/rpc/vault.cpp`) goes into `ALLOWED` with its proof in the docstring, exactly as the F-37 pair; anything in overlay code is a real finding (open an issue, fix on its own branch).
3. Workflow (both lines): add job `lockorder-pr` with `if: github.event_name == 'pull_request'` and a `dorny/paths-filter`-style step (or `git diff --name-only ${{ github.event.pull_request.base.sha }}` in a `bash` step) that sets `run=true` for the overlay paths; reuse the lockorder job's build steps (depends cache keys identical); run the subset with `-j2 --nozmq`; run the check script; **no `continue-on-error`**; add `lockorder-pr` to the push tier's required checks (repository settings — owner action, note it in the PR). Document the new leg in the header comment (`:5-20`) and in `doc/yellowback-review.md` (the CI/CD design).
4. Same pattern for `sanitizers-pr`: build the ASan/UBSan `test_bitcoin` only and run the overlay unit suites.
5. `docs/mapping.md` §22: no row (CI design); `docs/plans/yellowback-upgrade-plan.md` §7 (gates) one line: "the lockorder and sanitizer unit legs gate PRs that touch overlay or hook files; the full variants stay nightly".

## 5. Tests

- The check script gets a self-test: `qa/yellowback-lockorder-check.py --selftest` feeds three synthetic `debug.log` snippets (a `cs_main`/`VaultDB::cs` inversion → fails; the F-37 pair → allowed; the stock `getpeerinfo` pair → ignored) and exits 0 only if the verdicts match. Run it from `qa/yellowback-audit.sh` (gating push tier) so the filter cannot silently regress again.
- Dispatch the nightly on both lines after the filter change and attach the run URLs to the PR (step 2's inventory).

## 6. Acceptance criteria

- A synthetic report naming `VaultDB::cs` or a `src/vault/` frame fails the checker (self-test passes); the nightly's first run with the new filter has been triaged and its allow-list entries carry proofs.
- `lockorder-pr` and `sanitizers-pr` exist, run only on overlay-path PRs, gate (listed as required checks), and finish within the push tier's wall clock (≤ ~25 min warm).
- Workflow header and `doc/yellowback-review.md` describe the tiers accurately on both lines.

## 7. Risks and side effects

- First triage may surface inherited inversions that touch `main.cpp` frames near the vault hooks; classify by the *locks* in the pair, not the frame, and allow-list with a proof rather than loosening the regex.
- PR wall clock grows for overlay-path PRs (a second debug build; depends cached). Acceptable; the alternative is a shared artifact of the debug build across jobs, which the current artifact design (`node-bin.tar`) can carry if needed.

## 8. Effort estimate and dependencies

Filter + self-test: ~1 hour both lines. PR legs: ~3 hours both lines plus one nightly dispatch cycle for triage. Required-check configuration is an owner action. No dependencies on other reports; 04/F-1 (SKIP guard, report R8) shares the workflow file — coordinate the merge order to avoid conflicts.
