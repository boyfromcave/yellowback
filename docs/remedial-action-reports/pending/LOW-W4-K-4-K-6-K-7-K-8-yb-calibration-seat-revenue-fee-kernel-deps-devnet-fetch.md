# LOW — W4-K-4, W4-K-6, W4-K-7, W4-K-8 — yb-calibration hygiene: per-seat attestor revenue over 6 seats instead of 9; the vectorised fee kernel diverges from C++ on malformed band tables; floor-pinned dependencies with no lock file; `devnet fetch-binary` installs any CI run's artifact

**Repos / branches to change.** `yb-calibration` only; four independent branches off `upgrade/vault` (or one `fix/W4-K-lows` with four commits): `fix/W4-K-4-seat-revenue` (`src/ybcal/studies/fees_option_d.py`, `tests/studies/test_fees_option_d.py`, `docs/reports/2026-10-fees/{attestors.md,README.md,fees.json}`), `fix/W4-K-6-vkernel-fee-bands` (`src/ybcal/model/{vkernels.py,parity.py}`, `tests/model/`), `fix/W4-K-7-lockfile` (`pyproject.toml`, new `requirements.lock` / `uv.lock`, `.github/workflows/ci.yml`, run-manifest writers in `src/ybcal/report/build.py` and the study CLIs), `fix/W4-K-8-fetch-binary` (`src/ybcal/devnet/{build.py,cli.py}`, `tests/devnet/test_build.py`). No node change.
**Audit source.** `docs/audits/quantum-vault-ecosystem-wave4/03-yb-calibration.md:210-223` (W4-K-4), `:235-249` (W4-K-6), `:251-261` (W4-K-7), `:263-274` (W4-K-8); `docs/audits/quantum-vault-ecosystem-wave4/verification/03-verification.md:24` (W4-K-4 lowered to Low), `:26` (W4-K-6 Low/Info, one example mislabelled), `:27-28` (W4-K-7, W4-K-8 confirmed Low), `:143-151` (W4-K-4 detail: 9.5 → ≈ 14 mints/day break-even; no verdict changes), `:162-170` (W4-K-6 re-run: the second example is at $500; at $5,000 it is 59,000,000 vs 50,000,000), `:172-178` (W4-K-7/8 detail: `conclusion` fetched at `build.py:818` and never read); `00-consolidated.md:47`.
**Verified at** yb-calibration `97d5279` / ycash6 `0742e43` / ycash-dd `da5e0fe` (2026-10-13).
**Status:** pending

## 1. Finding

**W4-K-4 (seat revenue).** The fees study divides the attestor fee revenue over `SEATS = 6` ("mSelect 4 + kSlack 2 … the seated attestor set paid by AFEE-1"). On the node each Yellowback transaction pays exactly **one** member of the selected set A (`AttestFeeOk`), and A (mSelect + kSlack = 6) is drawn by bond weight from **all** seated, unpinned members — up to `nSlots` 9. Over time the revenue is shared by 9 members, so per-seat income is overstated 1.5× (equal bonds) and break-even mints/day understated 1.5× (≈ 9.5 → ≈ 14 per day at the D-Q-25 example). The bond's opportunity cost is also priced at the retired flat `BOND_MIN_YEC` 20,000 rather than the D-Q-30 floor/clamp. These figures support AFEE-1′ = 5,000 and the bond-affordability narrative; the correction makes an existing "bands inadequate in the low case" conclusion worse without flipping any verdict, hence Low.

**W4-K-6 (vkernel fee bands).** C++ `ProtocolFeeUnits` stops at the first empty band (`inBand <= 0 → break`) and carries `lo = hi` even after an unbounded band; `vkernels.protocol_fee_units` clamps each band at 0, continues, and breaks after `hi == 0`. Reproduced (debts in cents): bands `((1,000,000, 50), (100,000, 100), (0, 10))` at $5,000 → C++/kernel 25,000,000 units, vkernel 29,000,000; bands `((0, 100), (100,000, 50), (0, 10))` at **$500** → 7,500,000 vs 5,000,000 (the audit labelled this $5,000; at $5,000 it is 59,000,000 vs 50,000,000). The shipped table is monotone and compiled in, and parity samples only the default table, so no current study is affected; a future band search through `vkernels` would misprice without failing a test.

**W4-K-7 (dependencies).** `numpy>=1.26`, `scipy>=1.11`, `matplotlib>=3.8`, `jinja2>=3.1`, dev `pytest>=8`, `hypothesis>=6.90`, `ruff>=0.4`, no lock file; CI installs fresh with the pip cache keyed on `pyproject.toml`; run manifests record no package versions. Studies use scipy optimisers, float statistics and seeded RNGs, so "reproduce a run exactly from its manifest" is not guaranteed. The workspace precedent is Hawkeye's rule 6 (exact pins, committed lock, `--locked`).

**W4-K-8 (devnet fetch-binary).** `fetch_ci_binary` takes any run id of `boyfromcave/ycash6`, reads `headSha,status,conclusion` and uses only `headSha`; it checks neither `conclusion == success`, nor the branch/event, nor that `headSha` is the pin or an ancestor, and records no artifact hash before installing and running `ycashd`. Fork-PR runs also publish artifacts in the base repo. Impact is limited (opt-in, regtest on loopback with a random `secrets.token_hex(12)` RPC password, needs `gh auth`). Separately, `check_skew` compares against `PINNED_COMMIT` `7702d22`, so an upgrade-line binary always reports skew.

## 2. Root cause

At yb-calibration `97d5279`:

- W4-K-4: `src/ybcal/studies/fees_option_d.py:164` `SEATS = 6`; used at `:556` (`per_seat = att / SEATS / 12` in `revenue()`, `:527`), `:976` (`seat_revenue_usd_year`), `:1048-1050` (`break_even_mints_per_day`: `apr * bond * SEATS / (365 * mean_fee * share)`), `:833`, `:1125`, `:1370` (report fields); `:148-149` `BOND_MIN_YEC = 20_000` (retired flat v3 bond). Node (both lines): `src/yellowback/state.cpp:1649-1650` (seated = min(`nSlots` 9, set seats 15)), `:2052-2066` `Selected` (6 drawn by weight from all seated, unpinned), `:297-311` `AttestFeeOk` (one member of A paid); `params.cpp:80-82` `nSlots 9`, `mSelect 4`, `kSlack 2`.
- W4-K-6: `src/ybcal/model/vkernels.py:466-482` (clamp `np.maximum(top - lo, 0)`, `if hi == 0: break`); C++ `src/yellowback/math.h:192-204` (`if (inBand <= 0) break; … lo = hi;`); `src/ybcal/model/kernels.py:422-428` (delegates to the reference, matches C++); `src/ybcal/model/parity.py:45`, `:77-81` (samples debts only on the default table).
- W4-K-7: `pyproject.toml` `[project] dependencies` / `[project.optional-dependencies] dev`; `.github/workflows/ci.yml:38-44`, `:61-67` (`cache-dependency-path: pyproject.toml`, `pip install -e ".[dev]"`; only `pytest-xdist==3.8.0` exact).
- W4-K-8: `src/ybcal/devnet/build.py:799-873` `fetch_ci_binary` (`:817-821` run view with `conclusion` requested, `:824-827` only `headSha` used, `:836-844` manifest without hash), `:245-251` `check_skew(…, pin=PINNED_COMMIT)`; `src/ybcal/devnet/runner.py:186` random RPC password.

## 3. Fix options considered

- W4-K-4: divide by `nSlots` (9) — simple, right for equal bonds; **better**: use the bond-weight distribution the seat study already computes (`attest_seats.py`) to give per-seat revenue by bond size. Recommended: weight-based, with `nSlots` as the equal-bond special case. Also price the bond at the D-Q-30 clamp (`BOND_MIN_FLOOR_YEC_DQ30`… already defined at `:150-155`).
- W4-K-6: mirror the C++ loop exactly (recommended) vs restrict vkernels to monotone tables with an assertion (rejected alone: hides the divergence instead of removing it; keep as an extra guard).
- W4-K-7: `uv.lock` or a hashed `requirements.lock` (pip-tools `--generate-hashes`); either is fine — pick what the maintainer uses; CI installs `--require-hashes`.
- W4-K-8: full check (conclusion, event/branch, `headSha` = pin or release commit, artifact sha256) — recommended; documenting the risk only — rejected (the check is cheap).

## 4. Recommended fix

1. **W4-K-4.** Replace `SEATS` in `revenue()`, `seat_revenue_usd_year()` and `break_even_mints_per_day()` by the number of fee-sharing members (`N_SLOTS = 9` from `SEATS_MAINNET`/`ReleaseConstants`), or by a weight vector from the seat study (`share_i = w_i / Σw` over the seated set, since `Selected` draws by weight and AFEE-1 pays one of A); keep `SEATS = 6` only where the *selected set size* is meant. Price the bond's opportunity cost at the D-Q-30 rule (`clamp(5 % of collateral / 9, 10,000, 20,000)` YEC) instead of `BOND_MIN_YEC`. The "Attestor economics" tables (`docs/reports/2026-10-fees/attestors.md`, README §"Attestor economics", `fees.json`) are re-issued **once**, by `MEDIUM-W4-K-2-ycash-mint6b-per-vault-cap-owner-decision.md` §4 step 3 (whose fees-report re-issue is not blocked on the owner ruling); land this code first so that re-issue carries both corrections. This report does correct the D-Q-25 note in the workspace plan (`yellowback-quantum-plan.md:131`, "break-even 5 %/yr ≈ 9.5 mints/day") with a one-line erratum — owner-facing text, no decision changes.
2. **W4-K-6.** In `vkernels.protocol_fee_units`: compute `in_band = top - lo` without clamping; track a boolean mask `alive` that turns false element-wise at the first `in_band <= 0` (C++ `break`), add `where(alive, in_band * bps, 0)`; set `lo = hi` after every band including an unbounded one (C++ does not break on `hi == 0`). In `parity.quick_parity` add randomised band tables (non-monotone, zero-first, unbounded-first, negative bps) compared against `kernels.protocol_fee_units` (which delegates to the C++-faithful reference).
3. **W4-K-7.** Commit a lock file with hashes for runtime and dev extras (and `pytest-xdist`); CI installs from it (`pip install --require-hashes -r requirements.lock && pip install --no-deps -e .`, or `uv sync --locked`), cache keyed on the lock file. Every run manifest (`recommended.json`, study `--manifest` outputs) records `sys.version` and `importlib.metadata.version()` of numpy, scipy, matplotlib, jinja2.
4. **W4-K-8.** In `fetch_ci_binary`: request `headSha,status,conclusion,event,headBranch`; refuse (return `Skipped` with the reason) unless `status == "completed"`, `conclusion == "success"`, `event == "push"` (or a tag) on `upgrade/vault` (configurable allow-list), and `headSha` equals the requested release commit or the vendored pin (option `--commit`), or is an ancestor of it when `--allow-ancestor` is given. After download compute the sha256 of `ycashd` (and `ycash-cli`) and store it in the binary manifest; on a cache hit verify it. `check_skew`: default `pin` to the model pin (`vendor.VENDORED_COMMIT`) once the registry is re-pinned (W4-K-1), until then accept an explicit `--pin`.

## 5. Tests

- W4-K-4: `revenue()` per-seat income with 9 equal bonds equals set revenue / 9; break-even at the D-Q-25 example ≈ 14.25 mints/day (9.5 × 1.5); a weighted case matches the seat study's weights.
- W4-K-6: the two reproduced tables at $500 and $5,000 (25,000,000; 7,500,000 at $500; 59,000,000 at $5,000) give identical results from `kernels`, `vkernels` and a direct C++ transcription; randomised table parity passes 300 samples.
- W4-K-7: CI fails if the lock file is out of date with `pyproject.toml` (`uv lock --check` or `pip-compile --dry-run` diff); a manifest test asserts the version fields exist.
- W4-K-8: with a fake `gh` runner (`tests/devnet/test_build.py` already fakes `run`), `conclusion: failure`, `event: pull_request`, a foreign `headSha` and a hash mismatch on a cache hit each return `Skipped`; a successful push run on `upgrade/vault` at the pin installs and records the sha256.

## 6. Acceptance criteria

- Attestor economics divides by the fee-sharing set (or weights), prices the bond at D-Q-30, and the published tables are re-issued.
- `vkernels.protocol_fee_units` equals the C++ semantics on arbitrary band tables; parity covers non-default tables.
- Builds and CI are reproducible from a committed, hashed lock; manifests record interpreter and package versions.
- `devnet fetch-binary` installs only a successful push-run artifact at the expected commit, with a recorded and verified hash.

## 7. Risks and side effects

- W4-K-4 lowers the published per-seat revenue figures — owner-facing text changes; no node constant moves (AFEE 5,000 is an owner value).
- W4-K-7: a lock file needs periodic refresh; numeric results may shift slightly once pinned (document the pinned versions in the next report).
- W4-K-8: developers who fetched PR-run binaries must now build or use a push run; documented in the devnet README.
- No node, client or consensus impact.

## 8. Effort estimate and dependencies

- W4-K-4: 0.5 day plus report re-issue. W4-K-6: 0.5 day. W4-K-7: 0.5 day. W4-K-8: 0.5 day.
- Independent of each other and of the node reports. W4-K-8's `check_skew` default follows `MEDIUM-W4-K-1-yb-calibration-v3-registry-repin-lock-guard.md`; W4-K-7's lock file is also what `MEDIUM-W4-K-5-yb-calibration-ci-node-crosscheck.md`'s new CI job installs from.
