# utils/ — workspace housekeeping

Tools that keep the workspace itself healthy. Nothing here touches `ref/`, a fork's source, or a
branch; they act only on checkouts, build output and scratch space under `wt/`.

Two scripts, same algorithm:

- **`worktree-gc.sh`** — project-agnostic. Everything is a parameter with a sensible default: the
  worktree directory, the scratch directory, the hold file, the integration branches, the build-output
  and data directory names. Works on macOS or Linux (BSD or GNU `stat`), bash 3.2+. Drop it into any
  workspace of repos that uses a worktree directory.
- **`wt-gc.sh`** — the same collector with this workspace's layout and branches baked in
  (`wt/`, `wt/scratch`, `wt/.gc-keep`, lines `upgrade/vault harden/yellowback main master`,
  `.work` as data). Kept for the short command line; prefer `worktree-gc.sh` elsewhere.

## worktree-gc.sh — the general version

```bash
bash utils/worktree-gc.sh                 # report
APPLY=1 bash utils/worktree-gc.sh builds  # etc.; modes and knobs as for wt-gc.sh below, plus:
```

| variable        | default                                                   | meaning |
|-----------------|-----------------------------------------------------------|---------|
| `ROOT`          | parent of the script's directory                          | workspace root holding the repos |
| `WT_DIR`        | `$ROOT/wt`                                                | the worktree directory |
| `SCRATCH_DIR`   | `$WT_DIR/scratch`                                         | per-worktree scratch space |
| `KEEP_FILE`     | `$WT_DIR/.gc-keep`                                        | hold list |
| `BASE_BRANCHES` | `main master` + each repo's `origin/HEAD`                 | branches a HEAD must be contained in to count as merged |
| `BUILD_DIRS`    | `target build .dart_tool node_modules dist .next .gradle __pycache__` | regenerable output |
| `DATA_DIRS`     | `.work .venv .git`                                        | neither source nor build output: never deleted, never activity |

In this workspace run it as
`BASE_BRANCHES='upgrade/vault harden/yellowback main master' bash utils/worktree-gc.sh`, since
`ycash-dd`'s `origin/HEAD` still points at the retired `feature/digidollar`.

## wt-gc.sh — garbage-collect `wt/`

`wt/` holds the per-agent git worktrees (`wt/<name>`, one per task) and `wt/scratch/<name>` for
their temporary files. Agents create them freely and rarely remove them, and each one that builds
leaves its own copy of the build output, so `wt/` grows by hundreds of gigabytes per week.
`wt-gc.sh` measures the directory at run time and removes only what is provably dead. Nothing is
hard-coded: a worktree created an hour ago is judged by the same rules as one from last month.

### What it looks at

For every entry under `wt/` it determines, live:

- **the repo and branch** the worktree belongs to;
- **idle age**: time since the newest of the HEAD commit, any source file written after the
  checkout was created, and the checkout itself. Build output, `.work/`, `.venv/` and `.DS_Store`
  never count as activity;
- **in use**: one `lsof` snapshot at start; any entry with an open file or a process working
  directory inside it is never touched, whatever its age;
- **clean**: no uncommitted changes (an untracked `target/` is ignored);
- **merged**: HEAD is already contained in `upgrade/vault`, `harden/yellowback`, `main` or `master`.

Standalone clones in `wt/` (not registered worktrees) and calibration sweep data (`ybcal-*/.work`)
are never candidates. Names or globs listed in `wt/.gc-keep` (one per line, `#` comments) are never
touched either; use it to protect coordinator trees or long-running experiments.

### Three collectors

| mode      | removes                                                                 | when |
|-----------|-------------------------------------------------------------------------|------|
| `builds`  | real (non-symlink) `target/`, `build/`, `.dart_tool/`, `node_modules/` inside a worktree | tree idle > `IDLE_HOURS` (24), not in use, no uncommitted tracked changes |
| `trees`   | the worktree checkout (`git worktree remove`; the branch is kept)       | clean, merged, not in use, idle ≥ `MIN_DAYS` (7) — or any age with `MERGED=1` |
| `scratch` | `wt/scratch/<name>` whose worktree `wt/<name>` no longer exists         | idle ≥ `MIN_DAYS` |
| `all`     | the three above, then `git worktree prune` in every repo                |      |

A directory is only treated as build output if it contains **no tracked files**: `core/src/build/`
in YEW is source, and the collector leaves it alone even though it is named `build`.

Build output is separated from worktrees on purpose: it is regenerable, so it needs no merge check
and only a short idle window, and it is where most of the space is (a ycashd worktree's `target/`
is ~17 GB; a YEW worktree's up to ~28 GB).

### Usage

```bash
bash utils/wt-gc.sh                          # report only (default): what each mode would remove, and why the rest is kept
APPLY=1 bash utils/wt-gc.sh builds           # remove build output in idle trees
APPLY=1 bash utils/wt-gc.sh trees            # remove idle, merged, clean worktrees
MERGED=1 APPLY=1 bash utils/wt-gc.sh trees   # same, ignoring the idle window
APPLY=1 bash utils/wt-gc.sh all              # everything, then prune stale worktree registrations
```

Knobs (environment variables):

| variable     | default | meaning |
|--------------|---------|---------|
| `APPLY=1`    | unset   | act; without it the script only reports |
| `MERGED=1`   | unset   | `trees`: ignore the idle window — any clean, merged, not-in-use worktree goes |
| `IDLE_HOURS` | 24      | build output is removable once the tree's sources have been untouched this long |
| `MIN_DAYS`   | 7       | worktrees and scratch dirs are removable once idle this long |
| `FILTER`     | `*`     | only consider entries matching this glob, e.g. `FILTER='ci*'` or `FILTER='q6-*'` |

### Reading the report

The first line states the mode; the second says whether anything will be removed. Every row carries
a verdict and a reason:

- `free` — would be removed by `APPLY=1` (printed as `REMOVED` while applying);
- `keep` — blocked: `in use`, `uncommitted changes`, `unmerged (<branch>)`, or
  `source changed within 24h`;
- `soon` — clean and merged, only waiting out the idle window; the row says when it becomes eligible.

Each section ends with its total; the final line is an upper bound, because build output inside a
removable worktree is counted in both the `builds` and `trees` lines.

A full report takes a few minutes (a `git status` and a file scan per worktree). Use `FILTER` to
narrow it while iterating.

### Notes

- `git worktree remove` can fail with *Directory not empty* when a Finder window on `wt/` rewrites
  a `.DS_Store` into the directory mid-delete. The script detects that the registration is gone and
  finishes with `rm -rf`. Closing the Finder window avoids it.
- Removing a worktree never deletes its branch. Unmerged branches stay in the repo and can be
  checked out again with `git worktree add`.
- The Cargo-side duplication is a separate problem: every worktree path that builds leaves its own
  copy of each first-party crate in `~/.cargo/shared-target` (and of every depends crate in
  `ycash6/target`), so those caches need pruning by crate name or a full `cargo clean` of the
  profile, not by age.
