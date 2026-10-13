# INFO — W4-K-9 — yb-calibration notes: the fees study settles FEE-1′/IT-9′/RED-5′ with float dollars and a floor zat conversion instead of the ported exact kernels; `.DS_Store` files are tracked; one devnet test fails (instead of skipping) on a shallow ycash6 clone

**Repos / branches to change.** `yb-calibration` only, new branch `fix/W4-K-9-notes` off `upgrade/vault`: `src/ybcal/studies/fees_option_d.py`, `tests/studies/test_fees_option_d.py`, `tests/devnet/test_build.py`, `.gitignore`, removal of `src/.DS_Store` and `tests/.DS_Store`.
**Audit source.** `docs/audits/quantum-vault-ecosystem-wave4/03-yb-calibration.md:276-284` (W4-K-9), `:31-36` (the shallow-clone test failure in the auditor's run); `docs/audits/quantum-vault-ecosystem-wave4/verification/03-verification.md:29` (confirmed Info), `:179-180` (`usd_to_zat` floors; `.DS_Store` tracked; the `94bafa4` test); `00-consolidated.md:49`.
**Verified at** yb-calibration `97d5279` / ycash6 `0742e43` / ycash-dd `da5e0fe` (2026-10-13).
**Status:** pending

## 1. Finding

(a) The fees study that settled the FEE-1′ bands, IT-9′ and RED-5′ constants computes in float dollars and converts to zat with a floor (`usd_to_zat`), while the node uses exact integer ceilings (`ProtocolFeeZat`, `EarlyRedeemFeeZat`, `ResidualMinZat` in `math.h`). The difference is at most 1 zat per conversion and immaterial for dollar-level recommendations, but the exact kernels ported in the same merge (`kernels.protocol_fee_zat`, `early_redeem_fee_zat`, `residual_min_zat`) are not what produced the shipped constants, so the study and the node can disagree by a rounding step in any table the study publishes in zat.

(b) `src/.DS_Store` and `tests/.DS_Store` were committed in `68f6aff` (macOS Finder metadata; harmless, but noise in a repository whose outputs are provenance-checked). (c) `tests/devnet/test_build.py::test_skew_ci_commit_predates_pin` needs `b.KNOWN_CI_COMMIT` (`94bafa4`) and the eight commits between it and the pin in the local ycash6 clone; on a shallow clone it **fails** rather than skips (the auditor's run: 1 failure out of 1,164). Not a security issue in any case.

## 2. Root cause

At yb-calibration `97d5279`:

- (a) `src/ybcal/studies/fees_option_d.py:282-285` — `def usd_to_zat(usd, price_usd): return int(usd / price_usd * COIN)` (floor, float); node `src/yellowback/math.h` FEE-1′ / IT-9′ / RED-5′ helpers round up in integers (`ProtocolFeeUnits` `:192-204`, `ProtocolFeeZat` `:215`, `EarlyRedeemFeeZat` `:227`, `ResidualMinZat` `:361`); exact kernels `src/ybcal/model/kernels.py:422-456`.
- (b) `git ls-files` lists `src/.DS_Store`, `tests/.DS_Store`.
- (c) `tests/devnet/test_build.py:150-160` — `check_skew(REPO, b.KNOWN_CI_COMMIT)` asserts `relation == "predates"` and `len(commits_between) == 8`, its clone guard (`needs_repo`, `:27`, skips only when no clone exists) does not cover a shallow history that lacks the commit.

## 3. Fix options considered

- (a) Switch the study to the exact kernels (recommended: the kernels exist and are parity-checked) vs keep floats and document the ≤ 1-zat bound (acceptable fallback; the published dollar figures do not change).
- (b) Delete and ignore (only option).
- (c) Skip when `git cat-file -e 94bafa4^{commit}` fails (recommended) vs require a full clone in CI (W4-K-5's job does `fetch-depth: 0`; do both).

## 4. Recommended fix

1. (a) In `fees_option_d.py`, compute every zat amount the study reports or compares with the node (`fee_zat`, early-redeem fee, residual threshold) through `kernels.protocol_fee_zat`, `kernels.early_redeem_fee_zat`, `kernels.residual_min_zat` at the µUSD price (`Price`), keeping float dollars only for display; keep `usd_to_zat` for non-consensus estimates and rename it `usd_to_zat_floor_estimate` with a docstring stating the ≤ 1-zat difference from the node.
2. (b) `git rm --cached src/.DS_Store tests/.DS_Store`; add `.DS_Store` to `.gitignore`.
3. (c) At the top of `test_skew_ci_commit_predates_pin`: `pytest.skip("ycash6 clone lacks 94bafa4 (shallow?)")` when the commit is not resolvable in `REPO` (`git -C REPO cat-file -e 94bafa4^{commit}`), and mark the test as needing full history in its docstring.

## 5. Tests

- (a) A test that the study's zat figures for the release table equal the exact kernels' (and therefore the C++ worked examples at `yellowback_math_tests.cpp`) for the shipped bands at a grid of prices.
- (c) With a shallow clone (or a fake repo lacking the commit), the test reports SKIPPED, not FAILED.

## 6. Acceptance criteria

- The fees study's zat outputs come from the exact kernels; float conversion remains only for labelled estimates.
- No `.DS_Store` tracked; ignored going forward.
- `pytest -m "not devnet"` on a shallow ycash6 clone has no failure from the skew test.

## 7. Risks and side effects

- (a) Some published zat figures may move by 1 zat; no dollar recommendation or node constant changes. No node, client or consensus impact.

## 8. Effort estimate and dependencies

- 2–3 hours. Independent. (c) is also covered by `MEDIUM-W4-K-5-yb-calibration-ci-node-crosscheck.md`'s full-history checkout in CI, but the skip is still right for developer clones.
