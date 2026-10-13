# MEDIUM — W3-P-2 — Extend the cross-line byte-identity check to all nine vector files, the Python model and the `src/vault` / `src/yellowback` / `src/crypto/pq` trees, with a pinned allow-list of the known 6.20.0 shims

**Repos / branches to change:** `ycash-dd` and `ycash6` (both; one shared manifest file and one shared checker script, byte-identical on both lines), new branch `fix/W3-P-2-cross-line-manifest` off `upgrade/vault` in each. CI and `qa/` only; no consensus file.
**Audit source:** `docs/audits/quantum-vault-ecosystem-wave3/04-cross-line-parity-activation.md:135-161` (W3-P-2), test-fidelity gap `:308`; `docs/audits/quantum-vault-ecosystem-wave3/verification/04-verification.md:22-23` (the 11 differing overlay files, every hunk read; all nine vectors identical and listed), `:41` (verdict: Medium, test fidelity; "`pq_vectors.json` … makes its omission the material one"); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:42`, priority 5. Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:100` (STILL OPEN, Δ-free; the delta adds no vector file); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`. Re-run at HEAD: the same 81 tracked files under `src/vault`, `src/yellowback`, `src/crypto/pq` on each line, the same 11 differing files, all nine vector files identical.
**Status:** pending

## 1. Finding

Byte identity of the shared golden material is the only mechanised evidence that the two node lines enforce the same rules. The CI step that checks it compares 3 of the 9 vector files that both lines' `test_bitcoin` replay: `vault_vectors`, `yellowback_golden`, `yellowback_math_cases`. It also compares the qa golden, `yellowback_model.py`, `SERIALISATION.md` and `src/crypto/pq`. Six vector files are not compared:

- `pq_vectors.json`: OP_CHECKPQSIG sighash and chunking, two full signed spends;
- `pq_wallet_vectors.json`: the HKDF derivation;
- `yellowback_attest_vectors.json`;
- `yellowback_pq_vectors.json`: TOK-PQ;
- `pq_acvp_slhdsa.json` and `pq_falcon_kat.json`: conformance.

Nor are the overlay sources compared: `src/vault`, `src/yellowback`, the rest of the Python second implementation (`vault.py`, `pq.py`, `yellowback_attest.py`, the generators). All are identical today, apart from 11 overlay files that differ by reviewed 6.20.0 shims.

Failure scenario: a TOK-PQ encoding change regenerates `yellowback_pq_vectors.json`, or a sighash change regenerates `pq_vectors.json`, on one line. That line's CI passes against its own new vectors, and the cross-line step passes because it does not look at those files. The other line keeps validating against stale vectors, and the two populations disagree on which PQ spends are valid at the next block that uses the changed shape. The same holds for a rule change made in `src/vault/state.cpp` on one line only: the "a shared defect or rule change is made on both lines together" rule (workspace `CLAUDE.md`) is not checked by anything. Confirmed Medium (test fidelity) by the verifier.

## 2. Root cause

ycash-dd `da5e0fe`, ycash6 `0742e43` (re-verified):

- `ycash6/.github/workflows/yellowback-tests.yml:701-742`, "Cross-line vectors": file list at `:725-727` (six paths); `src/crypto/pq` by tree hash at `:731-737`.
- `ycash-dd/qa/yellowback-audit.sh:538-572`, `leg_cross_line`: the same six paths at `:553-555`; `src/crypto/pq` file by file at `:561-570`; blocking in upgrade mode at `:653`.
- All nine files are shipped and loaded on both lines: `src/Makefile.test.include:47-55` (both). `cmp` of each pair: identical (this report's re-run).
- Overlay trees: `git ls-files src/vault src/yellowback src/crypto/pq` gives 81 files on each line, the same path set. `diff -rq` lists exactly 11 differing files, with diff line counts in parentheses:
  - `src/vault/`: `checker.cpp` (4), `db.cpp` (2), `node.cpp` (127), `node.h` (52);
  - `src/yellowback/`: `index.cpp` (28), `index.h` (5), `params.h` (2), `policy.cpp` (14), `txbuilder.cpp` (558), `txbuilder.h` (41), `wallet.cpp` (23).

  The verifier read every hunk: all are API shims (constructor order, `PrecomputedTransactionData`, header renames, `UniqueLock`, `MerkleFrontiers`, member-form `GetBlockSubsidy`), the miner's `TemplateRun`, and the P-2 builder fee path. `src/crypto/pq` is identical.
- Further shared files that are identical today and unguarded:
  - `qa/rpc-tests/test_framework/`: `pq.py test_pq.py gen_pq_wallet_vectors.py vault.py test_vault.py gen_vault_vectors.py vault_contract.py vault_module_hook.py yellowback_attest.py test_yellowback_attest.py test_yellowback_math_spec.py test_yellowback_model.py test_yellowback_util.py VAULT_VECTORS.md yellowback_pq_vectors.json key.py bignum.py equihash.py blockstore.py`;
  - `src/pqkey.{h,cpp}`, `doc/yellowback-spec.md`;
  - `src/test/{vault_fuzz_harness.h, vault_state_fuzz_harness.h, yellowback_fuzz_harness.h, yellowback_bench.h, yellowback_math_tests.cpp}`.

  Re-verified with `cmp` at the audited commits and again at `da5e0fe` / `0742e43`. `vault_harness.py`, `yellowback_util.py`, `flyclient.py`, `util.py` and the inherited framework differ (stock 4.5.0 vs 6.20.0 framework).

## 3. Fix options considered

1. **Add the six vector files to the two hard-coded lists** (the audit's minimal fix). Closes the material gap (`pq_vectors.json`). It leaves the sources unguarded, and it keeps two lists, in two formats on two lines, that must be edited in step. Necessary but not sufficient.
2. **Compare whole trees and fail on any difference.** It would fail today on the 11 shim files, and nothing in it distinguishes a reviewed shim from a fresh one-line rule change. Rejected.
3. **Tree comparison with an allow-list by path only** (the audit's wording). Weak: once `src/yellowback/txbuilder.cpp` is on the list, any later change to it on one line, including a rule change, passes silently. Rejected as stated.
4. **One shared manifest, byte-identical on both lines, listing `identical` paths and trees plus `shim` entries pinned by the hash pair (sha256 on ycash-dd, sha256 on ycash6).** A shim file may differ, but only in exactly the reviewed way: editing it on either line breaks the pin until both lines' PRs update the manifest. That is the "visible, reviewed exception" the audit asks for. **Recommended.**

## 4. Recommended fix

### A. The manifest: `qa/yellowback-cross-line.manifest` (new, byte-identical on both lines)

Plain text, one entry per line, `#` comments:
```
# Every path here is the same on both node lines (workspace CLAUDE.md "two node lines, one overlay";
# audit W3-P-2). identical = byte-identical file; tree = every git-tracked file under the directory,
# same path set, byte-identical unless listed as shim; shim = may differ, pinned by both hashes.
identical src/test/data/vault_vectors.json
identical src/test/data/pq_vectors.json
identical src/test/data/pq_wallet_vectors.json
identical src/test/data/yellowback_golden.json
identical src/test/data/yellowback_attest_vectors.json
identical src/test/data/yellowback_math_cases.json
identical src/test/data/yellowback_pq_vectors.json
identical src/test/data/pq_acvp_slhdsa.json
identical src/test/data/pq_falcon_kat.json
identical qa/rpc-tests/test_framework/yellowback_golden.json
identical qa/rpc-tests/test_framework/yellowback_model.py
identical qa/rpc-tests/test_framework/SERIALISATION.md
identical qa/rpc-tests/test_framework/yellowback_pq_vectors.json
identical qa/rpc-tests/test_framework/VAULT_VECTORS.md
identical qa/rpc-tests/test_framework/pq.py
identical qa/rpc-tests/test_framework/test_pq.py
identical qa/rpc-tests/test_framework/gen_pq_wallet_vectors.py
identical qa/rpc-tests/test_framework/vault.py
identical qa/rpc-tests/test_framework/test_vault.py
identical qa/rpc-tests/test_framework/gen_vault_vectors.py
identical qa/rpc-tests/test_framework/vault_contract.py
identical qa/rpc-tests/test_framework/vault_module_hook.py
identical qa/rpc-tests/test_framework/yellowback_attest.py
identical qa/rpc-tests/test_framework/test_yellowback_attest.py
identical qa/rpc-tests/test_framework/test_yellowback_math_spec.py
identical qa/rpc-tests/test_framework/test_yellowback_model.py
identical src/pqkey.h
identical src/pqkey.cpp
identical doc/yellowback-spec.md
identical src/test/vault_fuzz_harness.h
identical src/test/vault_state_fuzz_harness.h
identical src/test/yellowback_fuzz_harness.h
identical src/test/yellowback_math_tests.cpp
identical qa/yellowback-cross-line.manifest
identical qa/yellowback-cross-line.py
tree src/crypto/pq
tree src/vault
tree src/yellowback
# 6.20.0 platform shims, read hunk by hunk in audit wave 3 (verification/04 :22). Pinned: <path> <sha256 ycash-dd> <sha256 ycash6>
shim src/vault/checker.cpp       <dd-sha256> <y6-sha256>
shim src/vault/db.cpp            <dd-sha256> <y6-sha256>
shim src/vault/node.cpp          <dd-sha256> <y6-sha256>
shim src/vault/node.h            <dd-sha256> <y6-sha256>
shim src/yellowback/index.cpp    <dd-sha256> <y6-sha256>
shim src/yellowback/index.h      <dd-sha256> <y6-sha256>
shim src/yellowback/params.h     <dd-sha256> <y6-sha256>
shim src/yellowback/policy.cpp   <dd-sha256> <y6-sha256>
shim src/yellowback/txbuilder.cpp <dd-sha256> <y6-sha256>
shim src/yellowback/txbuilder.h  <dd-sha256> <y6-sha256>
shim src/yellowback/wallet.cpp   <dd-sha256> <y6-sha256>
```
Fill the hashes from the merge commits of this fix (`sha256sum` of each file on each line). Add `qa/yellowback-vault-params.py` and its test files when MEDIUM-W3-P-1 lands. Add `src/test/data/vault_history_vectors.json` and its generator when LOW-W3-04-NEW-2 lands. Add `qa/yellowback-pq-link-check.sh` and `qa/yellowback-pq-provenance.sh` when LOW-W3-PQ-2 / PQ-4 land. Each of those reports says so.

The `test_framework` files listed are identical today. If a new one appears on one line only, or an `identical` file has to diverge, it moves to `shim` in a reviewed PR on both lines.

### B. The checker: `qa/yellowback-cross-line.py` (new, byte-identical on both lines)

Stdlib Python. `qa/yellowback-cross-line.py --this-line {dd,y6} (--other-dir DIR --other-rev REV | --other-ref REF)`:
1. Read the manifest from **this** tree and from the other line (`git show`). If the two manifests differ, exit 1: "the manifest itself differs". This makes the manifest self-guarding even before the `identical` line is reached.
2. `identical`: sha256 of this file against the other line's. Missing on either side → error.
3. `tree`: `git ls-files <dir>` here and `git ls-tree -r --name-only <rev> <dir>` there. The path sets must be equal (a new file on one line fails with "only on ycash6: …"). Each file not listed as `shim` must hash equal.
4. `shim`: this line's hash must equal its pinned column and the other line's hash must equal the other column. On mismatch print "shim drifted: <path> (ycash-dd now <h>, pinned <h>) — review the hunk on both lines and update the manifest on both". A `shim` entry whose two hashes are equal is reported as "shim now identical: move it to the tree" and fails, so the allow-list only shrinks by review.
5. Print one line per entry, finish with a summary, exit 0/1.

`--this-line` is needed only to pick the shim column; derive it from `[ -f src/rust/src/history.rs ]` (ycash6-only) or pass it from the workflow.

### C. Wire it in on both lines (replace the hard-coded lists)

- **ycash6** `yellowback-tests.yml:701-742`: keep the fetch logic at `:713-723`. Replace the `for f in …` loop and the `src/crypto/pq` block (`:724-738`) with `python3 qa/yellowback-cross-line.py --this-line y6 --other-ref other-line/head`. The step fetches `--depth 1`, which `git ls-tree` and `git show` need, so keep that and drop `--filter`, if any, for that ref. Rename the step "Cross-line identity (qa/yellowback-cross-line.manifest)".
- **ycash-dd** `qa/yellowback-audit.sh` `leg_cross_line` (`:538-572`): replace the body after the `show()` setup with `python3 qa/yellowback-cross-line.py --this-line dd --other-dir "$YB_OTHER_LINE_DIR" --other-rev "$YB_OTHER_LINE_REV"`, or `--other-ref "$YB_OTHER_LINE_REF"`. Keep the "NOT CHECKED" fall-through for local runs without the other line. The workflow's clone (`yellowback-tests.yml:500-507`) uses `--filter=blob:none --no-checkout`, and `git -C … show REV:path` fetches blobs lazily, which works but costs one round trip per file (~130 files). Change the clone to `--depth 1 --no-checkout` without the blob filter (~2 s). Rename the leg's title at `:653` to "cross-line identity (manifest)".
- **Local developer use:** document in `doc/yellowback-testing.md` (both lines): `YB_OTHER_LINE_DIR=../ycash6 YB_OTHER_LINE_REV=upgrade/vault qa/yellowback-audit.sh --mode upgrade`, and for ycash6 `python3 qa/yellowback-cross-line.py --this-line y6 --other-dir ../ycash-dd --other-rev upgrade/vault`.
- **Workspace:** `docs/mapping.md` §22 row: "cross-line identity is a manifest (`qa/yellowback-cross-line.manifest`); a 6.20.0 shim is pinned by both hashes", citing this report.

### D. What stays out (and why)

- The script-layer fork deltas (`interpreter.cpp`, `standard.cpp`, `sign.cpp`, `sigcache.cpp`, `main.cpp`) cannot be compared whole-file: they sit in stock files that differ by 4.5.0 vs 6.20.0 history. The verifier's delta-to-delta comparison (fork delta against each `-legacy`, hunk headers stripped) is the right tool. It is noisy, so it is an **optional, report-only** leg: add `--deltas` to the checker, which writes the two deltas and their diff to the `consensus-diff` artifact that `leg_consensus_diff` already uploads (dd `:574-590`). It never fails. It is review material for the G-9 gate.
- The fuzz corpora directories: optional `tree` entries if the owner wants them; the generators' `--check` steps already pin them per line.

## 5. Tests

- **Checker unit tests** `qa/test_yellowback_cross_line.py`, run in both `python` jobs. They build two throwaway git repos in a temp dir (stdlib `subprocess git init`) and cover: identical pass; an identical file differing (fail, path named); a tree with an extra file on one side (fail); a shim at its pinned hashes (pass); a shim edited on one side (fail, "shim drifted"); a shim whose two sides became equal (fail, "move it to the tree"); a manifest that differs between the lines (fail first).
- **Negative proof on the real trees, once, recorded in the PR:** on a scratch branch of each line, append a space to `src/test/data/pq_vectors.json` (fails as "identical") and a comment line to `src/yellowback/txbuilder.cpp` (fails as "shim drifted"). Both steps must go red; revert.
- **Positive:** both lines' CI green with the full manifest; the step's log lists the nine vector files, 3 trees (70 identical files, 11 pinned shims) and the qa/test_framework files.

## 6. Acceptance criteria

- `qa/yellowback-cross-line.manifest` and `qa/yellowback-cross-line.py` exist, are byte-identical on both lines and list themselves.
- The manifest names all nine `src/test/data` vector files, the qa golden/model/test-framework files listed in A, `src/pqkey.{h,cpp}`, `doc/yellowback-spec.md`, and the trees `src/crypto/pq`, `src/vault`, `src/yellowback`. The 11 shims are pinned by both hashes.
- ycash6's CI step and ycash-dd's `leg_cross_line` call the checker. Neither carries its own hard-coded list (`grep -n 'vault_vectors.json' .github/workflows/yellowback-tests.yml qa/yellowback-audit.sh` finds no comparison loop).
- The scratch negatives fail on both lines. The checker's unit tests run in CI.
- `docs/mapping.md` row and `doc/yellowback-testing.md` usage note added on both lines.

## 7. Risks and side effects

- None to consensus or the node binary.
- **Workflow friction (intended):** every edit to a shim file now needs a manifest update on both lines, in the same pair of PRs. A one-line ycash6-only shim fix touches ycash-dd too (manifest only). That is the cost of making divergence visible. Document it in the manifest header and in `doc/yellowback-testing.md`.
- **Merge order between the lines:** while the pair of PRs is open, each line's check compares against the other line's `upgrade/vault`, which does not yet have the new manifest, so it fails ("manifest differs"). The existing branch matching helps only on `push` runs. The ycash6 step's `REF` is `github.base_ref || github.ref_name` (`:709`), and `:715` probes the other line for a branch of that name. A push to `fix/W3-P-2-cross-line-manifest` therefore compares with the same-named branch on the other line, but a `pull_request` run compares with `upgrade/vault`. Fix that in this PR: try `github.head_ref` first, falling back to `base_ref` / `ref_name` when the other line has no such branch. Do the same in the dd `mode` step that computes `other`. Then open both PRs on the same branch name and merge both in one sitting.
- `test_framework` identity can surprise: a stock-framework fix to e.g. `key.py` on one line will fail. That is correct, since those files are shared today. Move the file to `shim` if the divergence is wanted.

## 8. Effort estimate and dependencies

- ~1 day: manifest + checker + unit tests (0.5), wiring on two lines (0.25), negatives and docs (0.25). One reviewer. No review gate.
- **Land first among the W3-P reports.** MEDIUM-W3-P-1 (extractor), LOW-W3-04-NEW-2 (history vector) and LOW-W3-PQ-2 / LOW-W3-PQ-4 (shared qa scripts) each add a manifest line. No dependency on consensus reports. A consensus report that regenerates a vector (e.g. the YED lifecycle fixes, W3-Y-*) must regenerate it on both lines in the paired PRs, and this check is what enforces that.
