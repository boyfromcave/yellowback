# kogany branch inventory (2026-11-01, counts revised 2026-11-02)

`boyfromcave/kogany` is a GitHub fork of `zakura-core/zakura`. GitHub copied every upstream branch
into the fork when it was created, so the fork carries **617 remote branches** (603 on 2026-11-01), of which only 51
are ours (3 branches of record, 48 `kc/*`). This document classifies them all, proposes a KEEP list for the Yellowback lead
architect's review, and gives the commands to delete the rest by hand. **The deletion pass was
run on 2026-11-02** at the lead architect's request: 613 branches deleted, and `git ls-remote --heads
origin` now lists exactly `kc/w9-mixed`, `kogany-legacy`, `upgrade/vault` and `vaults/kogany-compat`.

Snapshot: `git -C kogany fetch origin --prune` and `git ls-remote --heads` of both
`boyfromcave/kogany` and `zakura-core/zakura` on 2026-11-01 22:24 PST. Integration tip
`vaults/kogany-compat` = `f299e69a4` (W6-b). Upstream `main` = `281fbf94b`. The comparison was
made in a scratch bare repository (kogany's object store as an alternate, upstream fetched into
it), so the kogany clone's refs and configuration were not touched.

Revision 2026-11-02: the counts, the KEEP table and the expected dry-run output below were
re-taken after the day's merges (`git ls-remote --heads origin`, 617 heads; integration tip
`vaults/kogany-compat` = `9c40d252f`). The inherited-branch classes are unchanged: no `kc/*` was
deleted and no inherited branch moved. **Re-pin `kogany-legacy` to `b44ec121d` first** (the Zakura
sync of 2026-11-02, AGENTS.md rule 1), then run the deletion pass; the script keeps it either way.

## 1. Summary

| Class | Count | Disposition |
|---|---:|---|
| Branches of record (`kogany-legacy`, `upgrade/vault`, `vaults/kogany-compat`) | 3 | KEEP |
| `kc/*` agent branches still in flight | 1 | KEEP until merged (`kc/w9-mixed`) |
| `kc/*` agent branches already merged into `vaults/kogany-compat` | 47 | DELETE |
| Inherited upstream branch, tip equal to upstream's | 547 | DELETE |
| Inherited upstream branch, tip behind upstream's | 14 | DELETE |
| Inherited upstream branch, tip has commits upstream lacks | 0 | none |
| Stale inherited branch (deleted upstream since the fork) | 5 | DELETE |
| **Total** | **617** | **4 KEEP, 613 DELETE** |

GitHub's default branch is `upgrade/vault` (`git -C kogany remote show origin` → `HEAD branch:
upgrade/vault`), as the plan says, so no inherited branch is needed as a default-branch fallback.

No inherited branch carries a commit of ours: none is "ahead of" or "diverged from" upstream, and
the five stale ones hold only upstream authors' unmerged work (below). Deleting them loses nothing
of the Ycash developers'.

## 2. KEEP list

| Branch | Tip | Reason |
|---|---|---|
| `upgrade/vault` | `2b062412c` | The line of record and GitHub's default branch (AGENTS.md rule 2); receives `vaults/kogany-compat` at the wave gates. |
| `vaults/kogany-compat` | `9c40d252f` | The kogany integration branch (plan §4.2 rule 0); every `kc/*` merges here. |
| `kogany-legacy` | `2b062412c` (to be re-pinned to `b44ec121d`) | The pristine Zakura pin (= `ref/zakura`, `repos.yaml` `base-commit`); `make diff` and every frozen-delta measure compare against it. Never committed to. |
| `kc/w9-mixed` | `0d036908d` | In flight (W9-b, the full mixed suite): not yet in `vaults/kogany-compat`. The coordinator deletes it after its merge (coordination handoff §4). Every other `kc/*` (47) is merged. |

Tags: keep them all. `kogany-baseline` (`7924d1627`, W0-b and W1-Y0, an ancestor of the
integration tip) is ours and is the plan's W0 tag (handoff §4, wave gates). The other 39 tags
(`v1.0.0` … `v1.7.0`, release candidates included) are Zakura release tags and point at the same
commits as upstream's; they cost nothing, are not branches, and are useful when reading upstream
history. Upstream has one tag the fork lacks, `v1.8.0-rc1`; the rule 7 sync of 2026-11-02 (`b44ec121d`,
that lineage) landed, so fetch it with the re-pin.

### Why neither `main` is kept

- **The fork's `main`** points at `2b062412c`, the pin: it is identical to `kogany-legacy` and
  already 14 commits behind upstream's `main`. It is not the default branch, nothing in
  `repos.yaml`, the plan or the CI references it, and the rule "never commit to `main`"
  (COORDINATION.md) becomes moot once it is gone. Keeping it invites the mistake it exists to
  prevent: GitHub's "Sync fork" button on `main` would silently move it off the pin.
- **Upstream's `main`** is not needed in the fork either. Plan §4.2 rule 7 syncs by fetching
  `zakura-core/zakura` directly (the `upstream` remote) and merging the fetched commit into
  `upgrade/vault`; the re-pin moves `ref/zakura` and `kogany-legacy` to the merged upstream
  commit. At no step does the procedure read a branch of the fork other than the three of
  record. A mirror of upstream `main` inside the fork would only be a second, staler copy of what
  the `upstream` remote already gives.

## 3. Our branches in detail

| Branch | State against `origin/vaults/kogany-compat` |
|---|---|
| `kogany-legacy`, `upgrade/vault` | `2b062412c` (the pin); `upgrade/vault` has received nothing yet |
| `vaults/kogany-compat` | `9c40d252f` |
| `kc/w9-mixed` | **in flight** (W9-b) |
| `kc/bip68`, `kc/ci-kogany`, `kc/coinbase-tag`, `kc/fee-policy`, `kc/fork-protocol`, `kc/fork-sync-rc4`, `kc/harness-state`, `kc/kogany-mines`, `kc/kogany-pq`, `kc/kogany-vault`, `kc/kogany-version`, `kc/kogany-yed-math`, `kc/koganyd-docker`, `kc/koganyd-image`, `kc/live-reads`, `kc/mempool-fixes`, `kc/module-register`, `kc/p2p`, `kc/pqpkh-fuzz`, `kc/pruned`, `kc/relay-ycash`, `kc/repin-b44ec121d`, `kc/rpc-artifacts`, `kc/rpc-dispatch`, `kc/rpc-parity`, `kc/rpc-stock`, `kc/rpc-ycash`, `kc/rpc-yed`, `kc/script-plumb`, `kc/set-state`, `kc/snapshot-hook`, `kc/standardness`, `kc/state-mint`, `kc/state-release`, `kc/sync-gate`, `kc/sync-resume`, `kc/sync-zakura-20261102`, `kc/tip-recheck`, `kc/vault-epoch`, `kc/vault-storage`, `kc/w0-scaffold`, `kc/w1-profile`, `kc/w9-review`, `kc/ycash-identity`, `kc/yed-attest`, `kc/yed-codecs`, `kc/yed-index` | **merged** (tip is an ancestor of the integration tip), 47 branches |

The 47 merged `kc/*` branches are the ones the coordinator should have deleted after each merge
(handoff §4, "Delete the `kc/` branch after the merge") but could not: the session's permission
classifier blocks remote branch deletion. They go in the same pass as the inherited branches. The
local `kc/*` branches and their `wt/kc-*` worktrees are the coordinator's to remove afterwards;
deleting the remote branch does not touch them. `kc/yewd-s4` lives in `yew`, not in kogany, and is
out of scope here.

## 4. DELETE: inherited branches by prefix

566 branches inherited from `zakura-core/zakura`. "Behind" means upstream has moved the branch
since the fork; "stale" means upstream has deleted it since.

| Prefix | Count | Not equal to upstream |
|---|---:|---|
| `adam/` | 155 | |
| `fix/` | 81 | |
| `ai-dev/` | 39 | |
| `roman/` | 38 | 2 stale |
| `feat/` | 31 | |
| `evan/` | 22 | 2 stale, 1 behind |
| `hc/` | 19 | |
| `test/` | 18 | |
| `upstream-sync/` | 15 | |
| `split/` | 14 | 6 behind |
| `perf/` | 13 | |
| `claude/` | 13 | 1 stale |
| no prefix | 12 | `main` behind |
| `agent/` | 10 | |
| `deps/`, `codex/` | 9 each | |
| `experiment/` | 8 | |
| `resource-accounting/` | 6 | 6 behind |
| `ci/` | 5 | |
| `smoke/`, `security/`, `docs/`, `cursor/` | 4 each | |
| `validate/`, `stack-base/`, `review/`, `release/`, `refactor/`, `integrate/`, `diag/`, `chore/`, `build/`, `archive/` | 2 each | |
| `restack/`, `ownership/`, `ops/`, `network/`, `hotfix/`, `feature/`, `diagnose/`, `deploy/`, `continuous-sync/`, `campaign/`, `bench/`, `backport/`, `audit/` | 1 each | |

The 12 unprefixed: `ambiguity-inv-fix`, `deduplicate-commitment-root-checks`,
`fix-sync-near-tip-header-fallback`, `headersync-fixes-combined-backup`, `ironwood-main`,
`ironwood-mega-PR`, `ironwood-zellic-jun23`, `main`, `mempool-peer-score-hardening`,
`nu7-testnet-live-branch-id-ad9`, `replace-vergen-build-metadata`, `restore-semver-enum-gate`.

**Behind upstream (14; commits upstream added since the fork):** `main` (14),
`evan/orphan-rate-adaptive-fanout` (10), `resource-accounting/backend-owner` (46),
`resource-accounting/block-owner` (27), `resource-accounting/compat-tcp` (69),
`resource-accounting/discovery-owner` (25), `resource-accounting/node-composition` (147),
`resource-accounting/sequencer-owner` (38), `split/pure-reactors/01-header-sync-reactor` (21),
`split/pure-reactors/02-header-sync-peers` (25), `split/pure-reactors/04-block-sync-reactor` (37),
`split/pure-reactors/06-block-sync-peers` (37), `split/pure-reactors/08-discovery-state` (19),
`split/pure-reactors/11-session-coordination` (24).

**Stale (5; deleted upstream; commits not reachable from any upstream branch or tag):**
`claude/inspiring-knuth-2zuhlp` (2 commits), `evan/orphan-rate-advert-slots` (0),
`evan/orphan-rate-missing-parent` (7), `roman/mac/claude/reuse-template-transactions` (3),
`roman/mac/codex/idle-peer-maintenance` (8). All are upstream authors' work (dated
2026-10-31/11-01); none is ours.

## 5. Deleting

Deleting a branch in the fork never affects `zakura-core/zakura`: a GitHub fork is a separate
repository whose refs are its own, and a `git push origin --delete` to `boyfromcave/kogany`
changes only that repository. No workflow on the default branch `upgrade/vault` listens to the
`delete` event, so the deletions start no Actions run.

Run from the kogany main tree (`$WS/kogany`), whose `origin` is `git@github.com:boyfromcave/kogany.git`
with the BOY_GH key. The script recomputes the list at run time rather than trusting this
snapshot: it keeps the three branches of record, keeps every `kc/*` whose tip is **not** an
ancestor of `origin/vaults/kogany-compat` (so an agent branch pushed after this inventory, or one
still in flight, survives), and deletes everything else.

**Dry run** (prints the counts and the KEEP lines, deletes nothing; runs in bash or zsh):

```bash
cd /Users/boy/projects/yellowback-workspace/kogany
git fetch origin --prune
git ls-remote --heads origin | awk '{sub("refs/heads/","",$2); print $1, $2}' |
while read -r sha name; do
  case "$name" in
    kogany-legacy|upgrade/vault|vaults/kogany-compat) echo "KEEP $name"; continue ;;
    kc/*) if ! git merge-base --is-ancestor "$sha" origin/vaults/kogany-compat; then
            echo "KEEP $name (kc, not merged)"; continue
          fi ;;
  esac
  echo "DELETE $name"
done > /tmp/kogany-branches.txt
grep -c '^KEEP' /tmp/kogany-branches.txt; grep -c '^DELETE' /tmp/kogany-branches.txt
grep '^KEEP' /tmp/kogany-branches.txt
```

Expected (2026-11-02): 4 KEEP (`kogany-legacy`, `upgrade/vault`, `vaults/kogany-compat`,
`kc/w9-mixed`) and 613 DELETE; once `kc/w9-mixed` is merged, 3 KEEP and 614 DELETE. If the numbers differ, read the list before going on.

**Delete** (50 refs per push; review `/tmp/kogany-branches.txt` first):

```bash
cd /Users/boy/projects/yellowback-workspace/kogany
sed -n 's/^DELETE //p' /tmp/kogany-branches.txt | xargs -n 50 git push origin --delete
git fetch origin --prune
git ls-remote --heads origin        # should list only the KEEP branches
```

`git push --delete` of several refs is atomic per push only if `--atomic` is added; without it, a
ref that has already gone (for example a `kc/*` the coordinator deleted in the meantime) is
reported and the rest of the chunk still goes through. Re-running the dry run afterwards should
print only KEEP lines.

## 6. Keeping them gone (rule 7 configuration)

The deletions stay deleted as long as nothing pushes upstream's branches back. Three ways they
could come back, and the guard for each:

1. **Fetching from upstream with the default refspec.** kogany's `upstream` remote currently has
   `remote.upstream.fetch = +refs/heads/*:refs/remotes/upstream/*` (never yet fetched: there are
   no `refs/remotes/upstream/*` today). A fetch with it would create ~576 remote-tracking refs
   locally, which is harmless on GitHub but makes the mistake in (2) one command away. Rule 7
   needs only upstream's `main`. Recommended configuration, to be set by the coordinator (or the
   first `sync-zakura-<date>` agent) in the kogany clone:

   ```bash
   git -C $WS/kogany config remote.upstream.fetch '+refs/heads/main:refs/remotes/upstream/main'
   git -C $WS/kogany config remote.upstream.tagOpt --no-tags
   git -C $WS/kogany config remote.upstream.prune true
   git -C $WS/kogany config remote.origin.prune true
   ```

   `--no-tags` keeps upstream's tags out of the clone's tag namespace (from which a
   `git push --tags` would publish them); when a sync re-pins to a release, fetch that one tag
   explicitly: `git fetch upstream tag v1.8.0`. The `upstream` remote keeps its disabled push
   URL.
2. **Pushing everything.** Never `git push --mirror` or `git push origin --all` from the kogany
   clone, and never push a `refs/remotes/upstream/*` refspec to `origin`. The sync agent pushes
   only its own `kc/sync-zakura-<date>` branch.
3. **GitHub's "Sync fork" button** (and `gh repo sync`). It merges upstream's same-named branch
   into the fork's branch on GitHub, outside the review of rule 7. With `main` deleted and the
   default branch `upgrade/vault` (which upstream lacks) it has nothing to act on; it should not
   be used in any case.

`ref/zakura` is a separate clone with its own `origin`; its branch list is unaffected by any of
this, and its re-pin stays the deliberate rule 1 procedure.
