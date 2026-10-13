# MEDIUM — 04/F-1, 04/N-4 — `vault_pq_reorg.py` can pass the merge gate as a vacuous SKIP; CI has no SKIP detection

Repos / branches to change: `ycash-dd` (`fix/04-F-1-pq-reorg-skip-guard` off `upgrade/vault`), `ycash6` (same branch name, same change; both lines land together). No consensus code.
Audit source: `docs/audits/quantum-vault-ecosystem/04-cross-line-parity-activation.md:71-99` (F-1), verification `verification/04-verification.md:55` (verdict), `:68-87` (detail), `:198-202` (N-4); consolidated `00-consolidated.md` row 04/F-1 and R8.
Status: done — completed 2026-10-13T11:21Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13; nightly tier pending the owner's dispatch)

## 1. Finding

`vault_pq_reorg.py` is in the merge-gate list `YELLOWBACK_SCRIPTS` on both node lines and is the only functional proof of the quantum review's F-1 property ("a reorg below Falcon's height evicts Falcon spends", enforced by `vault::RecheckPQScripts` on every tip change). Its `run_test` needs the optional Falcon signer that `test_framework/pq.py` compiles on the fly with `$CC` (default `cc`). When that compile fails, the script prints `SKIP: …` and `return`s before its first assertion; `rpc-tests.py` treats any zero exit as a pass, so the shard goes green with the property unproved.

Today it runs only by accident: the functional jobs on both lines are `runs-on: ubuntu-22.04` with a full checkout, and the hosted image ships GCC. Neither functional job installs a compiler (the `apt-get install build-essential` steps live in the *build* jobs; ycash6's functional job even runs its prerequisites action with `apt: 'false'`). A slimmer runner image, a self-hosted runner, a sparse checkout without `src/crypto/pq/falcon/`, or a `TMPDIR` the compiler cannot write to turns the merge-gate proof into a silent no-op. The other SKIP-capable scripts (`yellowback_stratum`, `yellowback_chainviz`, the three attest-agent scripts) are guarded by explicit `test -x … || exit 1` steps; this one is not, and nothing generic catches the convention (N-4).

## 2. Root cause

- The SKIP: `ycash-dd/qa/rpc-tests/vault_pq_reorg.py:121-124` and `ycash6/qa/rpc-tests/vault_pq_reorg.py:121-124` (byte-identical in this region):
  ```python
  pq.falcon_set_build_dir(self.options.tmpdir)
  if not pq.falcon_signer_available():
      print('SKIP: no C compiler for the optional Falcon signer (pq.falcon_signer_available)')
      return
  ```
  The docstring at `:25` says so: "Without a C compiler the test prints SKIP and passes."
- The signer loader: `qa/rpc-tests/test_framework/pq.py:553-593` (`_falcon_load`: `cc = shlex.split(os.environ.get('CC', 'cc'))`, `subprocess.run(cc + ['-O2','-shared','-fPIC', …], check=True)`, any `OSError`/`CalledProcessError` → `FalconSignerUnavailable`), `:595-601` (`falcon_signer_available()` never raises). Identical on both lines.
- The runner: `ycash-dd/qa/pull-tester/rpc-tests.py:448` and `ycash6/qa/pull-tester/rpc-tests.py:555`: `passed = stderr == "" and proc.returncode == 0`. `grep -i skip` finds only comments (`:95-99`, `:205-212` on dd). There is no SKIP notion.
- The workflows:
  - `ycash-dd/.github/workflows/yellowback-tests.yml:86` lists `vault_pq_reorg` in `YELLOWBACK_SCRIPTS`; the `functional` job is `:344-420` (`runs-on: ubuntu-22.04` at `:347`; Python prerequisites by `pip` only at `:365-375`; `tar -xf node-bin.tar` at `:384`; the only guard is the sidecar `test -x` at `:387`; the run at `:411`). Compiler installs exist only in `build` (`:154-155`), `nightly` (`:700-701`), `lockorder` (`:933-934`), `sanitizers` (`:1026-1027`), `coverage` (`:1113-1114`), `weekly-fuzz` (`:1232-1233`). The SKIP guards that do exist: `:776` (stock parity), `:804`, `:815`, `:827` (attest agent).
  - `ycash6/.github/workflows/yellowback-tests.yml:115` lists it; the `functional` job is `:354-444` (`runs-on: ubuntu-22.04` at `:358`; `./.github/actions/yellowback-prereqs` with `apt: 'false'` at `:374-376`; the sidecar guards at `:423-424`; the run at `:428`). The prereqs action (`.github/actions/yellowback-prereqs/action.yml`) installs `build-essential` only when `apt` is `'true'`.
  - The lockorder/coverage variants exclude `yellowback_stratum`/`yellowback_chainviz` **by name** (dd `:977-987`, `:1157-1165`; ycash6 `:1471-1482`, `:1629+`) — the same by-name approach that misses this script.
- The only other Falcon-signer consumer, `yellowback_devnet_upgrade.py:150-156`, asserts a `SKIP` *value* deliberately under `--no-pqfalcon`; it is nightly and not a vacuous pass.

## 3. Fix options considered

1. **Make the signer a hard requirement of the script** (raise instead of `return`). Simple, but a developer without `cc` loses the whole suite's green and the script's documented local behaviour; and it fixes one script, not the convention.
2. **Guard in the workflow only** (`python3 -c 'from test_framework import pq; …falcon_signer_available()…'` before the shard). Mirrors the existing sidecar guards; fixes F-1 but not N-4 (the next SKIP-capable script repeats the gap).
3. **Generic SKIP detection in `rpc-tests.py`** (print a `SKIPPED` column; `--fail-on-skip` exits non-zero). Closes F-1 and every future script that follows the `SKIP:` convention; costs ~20 lines in an inherited file that the fork already patches (the `--cachedir/--portseed` block at `:348`).
4. **Install the compiler explicitly in the functional jobs.** Removes the dependence on the runner image. Cheap (`gcc libc6-dev`, ~10 s), and orthogonal to the above.

Recommended: 2 + 3 + 4 together (the guard is the loud, early message; the detector is the generic net; the install removes the root cause). Option 1 is rejected only as a *replacement*: keep the local SKIP, but make CI unable to accept it.

## 4. Recommended fix

Both lines, one PR each, same content adapted to each workflow's shape.

1. **`qa/pull-tester/rpc-tests.py` — SKIP detection.**
   - In `RPCTestHandler.get_next` (dd `:420-452`, ycash6 `:525-560`) after reading `stdout`, compute `skipped = passed and any(line.startswith('SKIP') for line in stdout.splitlines())` and return it as a sixth tuple element.
   - In `run_tests` (dd `:365-395`, ycash6 equivalent) add a `SKIPPED` column to the results table, print `Skipped: <name>` in bold, and keep `all_passed = all_passed and passed and not (skipped and args.fail_on_skip)`.
   - Add `--fail-on-skip` (`parser.add_argument('--fail-on-skip', action='store_true', help='treat a script that prints a SKIP line as failed')`). Default off, so developer runs keep today's behaviour.
   - Match only lines that *start* with `SKIP` (`^SKIP\b`): the six scripts that use the convention (`vault_pq_reorg.py:123`, `yellowback_attest_agent.py:274`, `yellowback_chainviz.py:376`, `yellowback_devnet_roles.py:478`, `yellowback_devnet_upgrade.py:93`, `yellowback_stratum.py:252`) all print `SKIP:` at column 0; `yellowback_devnet_upgrade.py:140` prints `interm: SKIP: …` mid-line on purpose and must not match.
2. **Workflows — pass the flag everywhere and guard the signer.**
   - Every `qa/pull-tester/rpc-tests.py` invocation in both workflows gains `--fail-on-skip` (dd `:411, :754, :777, :805, :816, :828, :987, :1076, :1165`; ycash6 `:428, :1209, :1253, :1287, :1298, :1310, :1324, :1482, :1564` and the coverage run). The nightly `yellowback_devnet_upgrade` run is not invoked with `--no-pqfalcon`, so the flag is safe there; if a future job does pass it, that job alone omits `--fail-on-skip` with a comment.
   - Before the shard run, add the explicit precondition (next to the sidecar guard, dd after `:387`, ycash6 inside the `for n in "${sel[@]}"` case at `:421-425` as a `vault_pq_reorg)` arm):
     ```bash
     python3 - <<'PY' || { echo "the Falcon signer does not build (test_framework/pq.py _falcon_load); vault_pq_reorg would SKIP"; exit 1; }
     import sys; sys.path.insert(0, 'qa/rpc-tests')
     from test_framework import pq
     sys.exit(0 if pq.falcon_signer_available() else 1)
     PY
     ```
     The probe builds `libycashfalcon-<hash>.so` into `tempfile.gettempdir()/ycash-pq-falcon`; the script itself then rebuilds into its `--tmpdir` (same sources, same hash, ~2 s). Acceptable; or export `TMPDIR` first so both share the directory.
3. **Workflows — install the compiler explicitly.**
   - dd `functional` (`:355-375`): add a step `sudo apt-get update -q && sudo apt-get install -y -q gcc libc6-dev` before the Python prerequisites, with a comment citing this report.
   - ycash6 `functional` (`:374-376`): keep `apt: 'false'` (the full build list is slow) and add the same two-package step; or extend `yellowback-prereqs` with a `compiler` input. Same for ycash6's `python` job (`:1029-1031`) if `test_pq`'s Falcon cases are expected to run there (check `qa/rpc-tests/test_framework/test_pq.py` for `falcon_signer_available`).
4. **The script's docstring** (`vault_pq_reorg.py:25`, both lines): "Without a C compiler the test prints SKIP and passes locally; CI refuses a SKIP (`rpc-tests.py --fail-on-skip`) and probes the signer before the shard."
5. **Workflow header comments** (dd `:28-33`, ycash6 `:30-35`): add one line: "a script that prints `SKIP` fails under `--fail-on-skip`; the sidecar/agent `test -x` guards are the early, named message."
6. **`qa/yellowback-audit.sh`** (optional, both lines): a leg that fails when a `qa/rpc-tests/*.py` prints `SKIP` (grep `print('SKIP`) and the workflow has no by-name guard for it — report-only at first.

## 5. Tests

- **Detector unit test.** Factor the classification into a pure function `classify(stdout, stderr, returncode) -> (passed, skipped)` in `rpc-tests.py` and add `qa/pull-tester/test_rpc_tests_classify.py` (three cases: pass, skip-at-column-0, `interm: SKIP` mid-line is not a skip). Run it in the `python` job next to `yellowback-ci-shard.py`'s pyflakes line (dd `:613`, ycash6 equivalent).
- **End-to-end negative, once, in the PR:** push a commit that exports `CC=/bin/false` in the functional job; the guard step must fail with the message above (both lines); revert the commit before merge. Record the two failing run URLs in the PR body.
- **End-to-end positive:** `CC=/bin/false qa/pull-tester/rpc-tests.py --nozmq --fail-on-skip vault_pq_reorg` locally exits 1 and prints `Skipped: vault_pq_reorg`; without `--fail-on-skip` it exits 0 and the table shows `SKIPPED`.
- `vault_pq_reorg.py` itself is unchanged in substance; its existing assertions (the Falcon spend evicted on the reorg below `pqFalconHeight`, the SLH-DSA spend kept) are the proof the guard protects.

## 6. Acceptance criteria

- Both workflows pass `--fail-on-skip` to every `rpc-tests.py` run; `grep -c 'rpc-tests.py' .github/workflows/yellowback-tests.yml` equals `grep -c -- '--fail-on-skip'` on each line (reviewer checks).
- The functional jobs on both lines install `gcc libc6-dev` explicitly and probe `pq.falcon_signer_available()` before the shard that contains `vault_pq_reorg`.
- The `CC=/bin/false` run fails at the guard on both lines (linked in the PR).
- `rpc-tests.py` results table shows a `SKIPPED` column; the classify unit test runs in the `python` job.
- `qa/rpc-tests/vault_pq_reorg.py:25` docstring updated on both lines; `docs/mapping.md` §22 gains a row ("SKIP convention: CI refuses it").

## 7. Risks and side effects

- None to consensus or the node binary. CI only.
- `--fail-on-skip` will surface any script that already SKIPs silently in a CI variant (the lockorder/coverage jobs exclude the two sidecar scripts by name; if a third one turns up, the flag makes it visible — that is the point, but expect one red run while it is fixed).
- The nightly `yellowback_devnet_upgrade` prints `SKIP:` from inside `upgrade-walk` into a **log file** (`stdout=log`, `yellowback_devnet_upgrade.py:105`), not to the script's stdout, so the detector is unaffected; re-check if the walk's logging changes.
- `apt-get` in the functional job adds ~10 s per shard (×4 per line).

## 8. Effort estimate and dependencies

- ~0.5 day per line (the two workflows differ in shape; the Python change is identical and can be a shared patch). Review: one person; no review gate (no consensus files).
- No dependency on other reports. Land before the YEW/lightwalletd vector re-sync reports so their CI steps can follow the same "fail, never skip" convention.

## Completion record

- **Completed:** 2026-10-13T11:21Z
- **Merged:** ycash-dd 75f21b794, ycash6 e6702e8f5, workspace (fix/ci-guard). rpc-tests.py --fail-on-skip on every CI invocation (the audit enforces it); the Falcon signer probe; test_rpc_tests_classify.py. With CC=/bin/false the run exits 1 locally on both lines.
- **Open:** one deliberately failing CI run (CC=/bin/false) to record, at first push.
- **Verification:** Integration run 2026-10-13 (both node lines built; full test_bitcoin dd 872/872, ycash6 923/923; qa/yellowback-audit.sh dd --mode upgrade rc 0 (18 PASS), ycash6 --report-only rc 0; functional suites pass; vault_vectors / golden / pq vectors byte-identical across lines). Logs: wt/scratch/integ/.
