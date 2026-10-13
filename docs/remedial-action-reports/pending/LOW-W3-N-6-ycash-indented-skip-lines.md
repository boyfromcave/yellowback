# LOW — W3-N-6 — Indented `skip` / `SKIP` lines evade `rpc-tests.py --fail-on-skip`: print `SKIP:` at column 0, run the Falcon owner spend in `vault_pq.py`, probe the signer on every shard

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W3-N-6-skip-lines` off `upgrade/vault` in each: `qa/rpc-tests/vault_pq.py`, `qa/rpc-tests/vault_policy.py`, `qa/pull-tester/rpc-tests.py` (regex + a self-test), `.github/workflows/yellowback-tests.yml` (functional job's signer probe; a lint step). Test infrastructure only.
**Audit source.** Wave 3: `docs/audits/quantum-vault-ecosystem-wave3/07-node-rpc-mempool-durability-ci.md` W3-N-6 (lines 179-191); `docs/audits/quantum-vault-ecosystem-wave3/verification/07-verification.md` W3-N-6 (lines 158-173, "PARTIALLY, Low — `vault_pq.py:189` is an unconditional note, not a dropped check; `vault_policy.py:120` shares shard 4 with `vault_pq_reorg`, so the signer probe covers it today (plan-dependent)"); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row W3-N-5..9 and remediation priority 5 ("fix the silent-skip paths (W3-PQ-5, W3-N-6)"). Wave 4: `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md` §1.5 row W3-N-6 (line 117, "STILL OPEN … the new test prints no skip lines").
**Status:** pending — re-verified at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): open on both lines (`rpc-tests.py`, `vault_pq.py`, `vault_policy.py` and the functional job's signer probe unchanged; ycash6 `0742e43` touched the workflow only after line 911).

## 1. Finding

`rpc-tests.py` marks a script as skipped only when a stdout line matches `SKIP_LINE = re.compile(r'^SKIP\b')` (`ycash-dd/qa/pull-tester/rpc-tests.py:349`, applied per line in `classify` `:351-355`; the comment `:345-348` makes column 0 the deliberate contract so `"interm: SKIP: ..."` mid-line does not count). Two vault scripts print indented skip lines and pass: `qa/rpc-tests/vault_policy.py:120` prints `'    SKIP the Falcon owner spend: no C compiler for the optional Falcon signer'` when `pq.falcon_signer_available()` is false (`:72-78`) and goes on — a real, conditional dropped check (the Falcon OWNER spend, its malleated-extra-push refusal and acceptance, `:112-118`); `qa/rpc-tests/vault_pq.py:189` prints `'    skip a Falcon owner spend: no Python Falcon signer (covered by vault_template_tests)'` **unconditionally** — a labelled permanent gap from the script's introduction, now stale, because the framework *has* a Falcon signer (`vault_policy.py` uses `pq.falcon_sign`).

Today the gap is closed by accident: the functional job probes the signer only for the shard whose names include `vault_pq_reorg` (`.github/workflows/yellowback-tests.yml:430-438`; ycash6 `:442-452`), and under the committed 4-shard plan `vault_policy` lands in the same shard. A new script or a re-weight re-partitions the shards, and a broken signer build would then leave `vault_policy`'s Falcon checks unexercised with a green result. Same files and lines on `ycash6` (`rpc-tests.py:416`, `vault_policy.py:120`, `vault_pq.py:189`).

## 2. Root cause

- `qa/rpc-tests/vault_policy.py:120`, `qa/rpc-tests/vault_pq.py:189` — skip lines not at column 0 (one lower-case).
- `.github/workflows/yellowback-tests.yml:430-438` — the probe is keyed on a script name, not run per shard.
- No lint enforces the column-0 contract.

## 3. Fix options considered

1. **Fix the two scripts + probe every shard + a lint (recommended).**
2. **Widen the regex to `^\s*SKIP\b` (case-sensitive).** Catches `vault_policy.py:120` as written, still ignores `"interm: SKIP:"` (does not start with whitespace + SKIP). Worth doing as defence in depth; on its own it misses the lower-case `vault_pq.py` line, and a case-insensitive `skip` at line start risks prose (`"skipping …"`).
3. **Raise instead of print under CI** (`if os.environ.get('CI'): raise`). Equivalent to failing; less uniform than the existing `SKIP:` contract. Not preferred.

## 4. Recommended fix

1. **`vault_policy.py:120`** — `print('SKIP: the Falcon owner spend: no C compiler for the optional Falcon signer')` at column 0 (the run is then "skipped" and `--fail-on-skip` fails it).
2. **`vault_pq.py:178-189`** — replace the unconditional note with the real check, as `vault_policy.py:112-118` does: if `pq.falcon_signer_available()`, lock a scheme-2 V with a near `ownerheight` (the V at `:178` uses `tip + 500`; use `tip + 12` as `vault_policy.py:68` does, or mine to it), then build and accept its Falcon OWNER spend — `pq.falcon_sign(sk, v.template_sighash(tx, 0, spk, value)) + SIGHASH_ALL`, `pq.pq_scriptsig(pk, sig) + OP_2`, `nLockTime = ownerheight` — and assert it confirms; else `print('SKIP: a Falcon owner spend: the optional Falcon signer did not build')` at column 0.
3. **`rpc-tests.py:349`** — `SKIP_LINE = re.compile(r'^\s*SKIP\b')`; update the comment; add a tiny self-test (the file already has `classify`; a `--self-test` flag or a doctest) covering `"SKIP: x"`, `"    SKIP x"`, `"interm: SKIP: x"` (not a skip).
4. **Workflow (both lines)** — run the Falcon-signer probe at the start of every functional shard (remove the `case … vault_pq_reorg` gate, `:430-438`; ycash6 `:442-452`); it is a few seconds. Add a lint step to the existing static-checks job: `! grep -nE "print\(\s*['\"]\s+(skip|SKIP)\b" qa/rpc-tests/*.py` (fails on any indented skip print).

## 5. Tests

- `rpc-tests.py` self-test (above).
- CI: on a runner with the signer, `vault_pq.py` now exercises a Falcon owner spend (a new `ok` line); with `CC=false` (signer cannot build) the probe fails every shard early, and `vault_policy`/`vault_pq` print `SKIP:` and fail under `--fail-on-skip` — verify once locally with `CC=false qa/pull-tester/rpc-tests.py --fail-on-skip vault_policy vault_pq`.
- What would have caught it: the lint step.

## 6. Acceptance criteria

- No `qa/rpc-tests/*.py` prints an indented skip; `vault_pq.py` runs the Falcon owner spend; the signer probe runs on every functional shard; `--fail-on-skip` fails a run whose signer is missing, on both lines.

## 7. Risks and side effects

- A runner without a C compiler now fails the functional shards instead of passing silently — intended. Check the sanitizer/lockorder legs, which also run `rpc-tests.py --fail-on-skip`, build the signer.

## 8. Effort estimate and dependencies

- 0.5 day both lines. Independent. Related: `LOW-W3-PQ-5-ycash-pq-model-ci-silent-skips.md` (`test_pq.py` `skipUnless`, audit 02) is the same class. Split of work: this report owns the per-shard Falcon-signer probe and the indented-skip lint step; `LOW-W3-PQ-5` owns the line-aware workflow guards, the no-skip unittest wrapper and the `qa/yellowback-audit.sh` workflow-shape check — neither adds the other's step; MEDIUM-04-F-1 (done) introduced the `--fail-on-skip` contract.
