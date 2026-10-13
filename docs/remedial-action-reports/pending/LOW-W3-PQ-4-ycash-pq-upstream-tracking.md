# LOW — W3-PQ-4 — Track the vendored PQ implementations upstream: a provenance script (pin mode, gating) and a scheduled upstream-drift job that opens an issue; a pin review at every release

**Repos / branches to change:** `ycash-dd` and `ycash6` (the script, byte-identical on both lines); `ycash6` (the scheduled workflow, one per project is enough because `src/crypto/pq` is identical across the lines); branch `fix/W3-PQ-4-pq-upstream-tracking` off `upgrade/vault`. CI and docs only; no code under `src/` changes.
**Audit source:** `docs/audits/quantum-vault-ecosystem-wave3/02-post-quantum-crypto.md:124-133` (W3-PQ-4), provenance method `:27-28`; `docs/audits/quantum-vault-ecosystem-wave3/verification/02-verification.md:102-107` (CONFIRMED, Low: slhdsa-c's README at the pin says "WE DO NOT CURRENTLY RECOMMEND RELYING ON THIS LIBRARY IN A PRODUCTION ENVIRONMENT"; PQClean's pin commit is the retirement-notice merge; "No tracking mechanism found in `.github/workflows`"), `:167-187` (provenance re-fetched: exact); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:49`. Open item carried from LOW-02-PQ-1-PQ-2 (done): "Open (optional): `qa/yellowback-pq-provenance.sh` (an upstream clone `cmp`)". Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:76` (STILL OPEN, Δ-free); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`. ycash6's CI step shifts `yellowback-tests.yml` by +8 lines after `:911`; the ycash6 workflow citations are updated.
**Status:** pending

## 1. Finding

The consensus PQ verifiers are vendored C from two upstreams.
- **SLH-DSA-SHA2-128s:** pq-code-package `slhdsa-c` at `174c02e4`. It is still marked "work in progress, not recommended for production".
- **Falcon-512 padded:** PQClean `falcon-padded-512/clean` and `common/fips202` at `0586a824`. PQClean is archived; its last commit is the retirement notice.

Provenance at the pins is exact. Both auditors re-cloned, `cmp`'d every unmodified file, and found the three local patches exactly as documented. The conformance evidence is strong (NIST ACVP, KAT replays, sanitizer runs).

What is missing is any process that notices upstream changes after the pin. Suppose `slhdsa-c` fixes a verification bug after `174c02e4`, for example an out-of-bounds read on a malformed signature, a carry bug in a rarely hit path, or a FIPS 205 errata change. Nothing in either line's CI, release checklist or docs would surface it. PQClean is frozen, so its risk differs: a Falcon issue would now be fixed elsewhere (the reference `falcon` implementation, FN-DSA / FIPS 206 implementations), not in PQClean. Watching PQClean alone tells us nothing. The scenario is a known-and-fixed upstream bug that stays in Ycash's consensus code indefinitely. Low, process.

## 2. Root cause

ycash-dd `da5e0fe` (ycash6 `0742e43` identical):

- `src/crypto/pq/README.md:69-83`: the `slhdsa-c` source, pin, licence, unmodified and patched file lists, and the "not recommended for production" note.
- `src/crypto/pq/README.md:85-117`: the PQClean source, pin and archived status; the unmodified and patched lists; `pqclean.c`/`api.h` replaced by Ycash files.
- `src/crypto/pq/README.md:133-191`: local patches P1-P3 and the provenance rule ("every file listed as unmodified `cmp`s equal to upstream at the pinned commit, and `diff` of `slh_dsa.c` … shows only lines marked `YCASH LOCAL PATCH P3`", `:189-190`).
- No script implements that rule. `grep -rn 'slhdsa-c\|PQClean' .github/workflows qa/*.sh` on both lines finds only comments. The cross-line checks (ycash6 `yellowback-tests.yml:729-737`, dd `qa/yellowback-audit.sh:561-570`) compare the two lines with each other, not with upstream.
- There is a precedent for a scheduled upstream check that opens an issue: ycash6 `yellowback-tests.yml:1193` (`issues: write`), `:1495-1500` ("Open an issue on failure", `gh issue create`). The workspace runs `scripts/check-ref-pins.sh` against upstream for the `ref/` pins.

## 3. Fix options considered

1. **A release-checklist line only** ("review upstream before each release"). Cheap, but it waits for a release, and P8 may be months away. Not sufficient alone; kept as part of the fix.
2. **Vendor via git submodule / subtree to make updates mechanical.** The workspace forbids submodules for its own reasons. A subtree merge brings in unreviewed upstream changes, the opposite of what a consensus verifier needs. Rejected.
3. **A provenance script with two modes, plus a weekly scheduled job and a release-checklist line** (the audit's recommendation, plus the open item from LOW-02-PQ-1). `--pin` re-proves the current provenance against the pinned upstream commits; it is gating, because it detects a hand edit outside the marked patches. `--upstream` diffs the vendored files against upstream's default branch and reports which vendored files changed since the pin; it never gates, but it opens an issue. **Recommended.**
4. Also watch the *successors*, not only the vendored repos. That covers Falcon/FN-DSA: the reference implementation and the FIPS 206 final text, whenever it is published. This is a watch item in the issue template and the release checklist, not code: a FIPS 206 encoding change would be a new scheme byte, never an edit of scheme `0x02`.

## 4. Recommended fix

### A. `qa/yellowback-pq-provenance.sh` (new, byte-identical on both lines; add it to the MEDIUM-W3-P-2 manifest)

Bash + git, no other dependency. It reads its pins and file lists from **one** machine-readable block that you add to `src/crypto/pq/README.md`, so the README stays the single source of truth:
```
<!-- provenance (read by qa/yellowback-pq-provenance.sh; keep in step with the lists above)
slhdsa  https://github.com/pq-code-package/slhdsa-c  174c02e42257f95c210963272877c49dbb50070f  main
  unmodified slhdsa/<f> <- <f>   for f in slh_dsa.h slh_sha2.c sha2_256.c sha2_512.c sha2_api.h plat_local.h slh_adrs.h slh_param.h slh_var.h slh_sys.h cbmc.h LICENSE
  patched    slhdsa/slh_dsa.c <- slh_dsa.c  P3
falcon  https://github.com/PQClean/PQClean  0586a824fc0d49df0b6b6e9179d8d15d06d0974f  master
  unmodified falcon/<f> <- crypto_sign/falcon-padded-512/clean/<f>   for f in inner.h fpr.h codec.c common.c vrfy.c keygen.c sign.c fft.c fpr.c rng.c LICENSE
  patched    falcon/fips202.c <- common/fips202.c  P1 P4
  patched    falcon/fips202.h <- common/fips202.h  P1
-->
```
(The upstream subdirectory for `LICENSE` and the exact upstream paths must be checked once against the clones. The auditors' `cmp` used them.) Modes:

- `--pin` (gating). For each upstream: `git clone --filter=blob:none --no-checkout <url>`, then `git fetch --depth 1 origin <pin>`, then `git show <pin>:<path>`.
  - Every `unmodified` file must `cmp` equal.
  - For each `patched` file, `diff -u upstream mine` may contain changed lines only where each `+` line, and each `-` line's replacement hunk, carries `YCASH LOCAL PATCH` or lies inside a `#if 0 /* YCASH LOCAL PATCH P4` … `#endif /* YCASH LOCAL PATCH P4 */` region. Implement it simply: strip the P4 guard lines, then require every remaining `+` line to contain `YCASH LOCAL PATCH` or be a continuation of a marked comment block. If that heuristic turns out too fragile for P1's multi-line comment, fall back to a per-file allow-list of expected `diff` hunk counts and the marker on each hunk's first `+` line.
  - Every file under `src/crypto/pq/{slhdsa,falcon}` that is neither listed nor a Ycash-owned file (`ycash_falcon*.{c,h}`, `README.md`) fails the check as "unlisted vendored file".
- `--upstream` (report). For each upstream, fetch the default branch head (`main` / `master` as recorded), then run `git diff --stat <pin> <head> -- <every upstream path in the block>`. Print the changed vendored paths with the commit subjects (`git log --oneline <pin>..<head> -- <paths>`). Exit 0 when nothing changed, and 3 (a distinct "upstream moved" code) when something did. For PQClean, also report whether the repository is archived (`gh api repos/PQClean/PQClean --jq .archived`, when `gh` is available).

### B. Wire it in

- **Gating, both lines.** Run `--pin` nightly in the nightly job (dd `yellowback-tests.yml` `nightly:` at `:935`; ycash6 equivalent), so network flakiness never blocks a push. Also run it in the release workflow's `version` job (ycash6 `yellowback-release.yml:60-100`) and in ycash-dd's new `yellowback-release-guard.yml` (MEDIUM-W3-P-1), where it blocks a tag.
- **Weekly upstream drift, ycash6 only.** Add a new workflow `.github/workflows/pq-upstream.yml` with `schedule: cron '17 5 * * 1'` and `workflow_dispatch`, `permissions: { contents: read, issues: write }`, and one job:
  1. Run `qa/yellowback-pq-provenance.sh --upstream`.
  2. On exit 3, `gh issue create`, or `gh issue comment` on the open issue whose title is `PQ upstream changed: <repo> <short head>`. Search first with `gh issue list --search` to avoid duplicates. The body carries the changed paths, the commit list, the README's provenance rule and the triage checklist below.
  3. The job fails only on a script error, never on drift (as the weekly fuzz job never blocks). This follows the pattern at ycash6 `yellowback-tests.yml:1495-1500`. Note 07/NEW-4 (the weekly fuzz job opens no issue on a crash) is a sibling gap in the same workflow, handled in `INFO-W3-N-10-N-14-07-NEW-3-NEW-4-ycash-node-rpc-ci-notes.md`. Keep the two consistent.
- **Triage checklist** (in the issue body and in `src/crypto/pq/README.md`, new section "Upstream tracking"):
  1. Is the change in a verify-path file (`PQ_VERIFY_SOURCES`)? If so, it is consensus: any adoption is a coordinated release on both lines through the G-9 review gate, with ACVP/KAT/golden replay.
  2. Is it a security fix? Assess exposure on our pinned code.
  3. Adopt by re-pinning (a new commit in the provenance block and the README lists; `--pin` green; all `pq_*` vectors byte-identical, or an explicit consensus decision if not), or record why not.
  4. For Falcon, check the successor implementations and FIPS 206 status (a change there is a new scheme byte, never an edit of `0x02`).
- **Release checklist** (`ycash6/doc/yellowback-release.md`, near "Network parameters"; dd `doc/yellowback.md`): "PQ upstream: `qa/yellowback-pq-provenance.sh --pin` green; `--upstream` run within the last 7 days with every open `PQ upstream changed` issue triaged."

### C. Docs

`src/crypto/pq/README.md`: the provenance block (A), an "Upstream tracking" section (B), and in the P3 section the sentence that the provenance rule is now `qa/yellowback-pq-provenance.sh --pin`. `docs/mapping.md` §22: one row.

## 5. Tests

- **`--pin` passes on today's trees** (both lines) and **fails on a scratch edit**: change one byte in `falcon/vrfy.c` ("unmodified" mismatch), or add an unmarked line to `slhdsa/slh_dsa.c` ("unmarked patch line"). Record both failures in the PR.
- **`--upstream` against a synthetic upstream:** point the script at a local bare clone of `slhdsa-c` with one commit added on `main` that touches `slh_sha2.c`. It must exit 3 and list the file and the commit. With no change it exits 0. Do this with an env override for the URL (`YB_PQ_UPSTREAM_SLHDSA=file:///…`), which the script should support for exactly this test.
- One `workflow_dispatch` run of `pq-upstream.yml` on ycash6, with its log linked in the PR. If upstream `slhdsa-c` has moved since `174c02e4`, the first run opens the first issue, which is the point. Triage it.

## 6. Acceptance criteria

- `qa/yellowback-pq-provenance.sh` exists, is byte-identical on both lines and is in the cross-line manifest. It reads the README's provenance block, and `--pin` passes on both lines and fails on the scratch edits.
- `--pin` runs nightly on both lines and blocks the ycash6 release tag and the ycash-dd pairing tag.
- `pq-upstream.yml` runs weekly on ycash6 and opens or updates one issue per upstream head when vendored files change.
- README "Upstream tracking" section and triage checklist, release-checklist line, mapping row.
- The LOW-02-PQ-1 "Open (optional)" item is closed by reference.

## 7. Risks and side effects

- None to the node binary.
- Network dependence: `--pin` needs GitHub. Hence nightly and at tags, not on every push. A transient fetch failure in the nightly is a red nightly, re-run.
- The marked-line heuristic can be brittle for multi-line patch comments. Keep the fallback (expected hunk counts per file), and test it against the real P1/P3/P4 diffs before merging.
- Issue noise: upstream `slhdsa-c` is active, so expect issues for test-only or CBMC-proof changes. The script limits itself to **vendored paths**, which keeps the noise low.

## 8. Effort estimate and dependencies

- ~1 day: the script and its two modes (0.5), the workflow and wiring (0.25), README/checklists and the scratch proofs (0.25). One reviewer.
- Coordinate with LOW-W3-PQ-2 (P4 must be known to the patch-line rule; land PQ-2 first or together), MEDIUM-W3-P-2 (manifest line) and MEDIUM-W3-P-1 (ycash-dd release guard hosts the `--pin` step).
