#!/bin/bash
# worktree-gc: project-agnostic garbage collector for a directory of git worktrees.
# Measures everything at run time; nothing is hard-coded to a project.
#
#   bash worktree-gc.sh                 report: what is removable now and why the rest is kept (default; touches nothing)
#   APPLY=1 bash worktree-gc.sh builds  remove regenerable build output ($BUILD_DIRS) inside idle worktrees
#   APPLY=1 bash worktree-gc.sh trees   remove idle worktrees whose HEAD is already in an integration branch (branches are kept)
#   APPLY=1 bash worktree-gc.sh scratch remove $SCRATCH_DIR/<name> dirs whose worktree <name> is gone and which are idle
#   APPLY=1 bash worktree-gc.sh all     the three above, then `git worktree prune` in every repo under $ROOT
#
# Configuration (env; all optional):
#   ROOT=<dir>          workspace root holding the repos.      default: parent of the directory this script lives in
#   WT_DIR=<dir>        directory of worktrees.                 default: $ROOT/wt
#   SCRATCH_DIR=<dir>   per-worktree scratch space.             default: $WT_DIR/scratch
#   KEEP_FILE=<file>    names or globs never touched, one per line, # comments.  default: $WT_DIR/.gc-keep
#   BASE_BRANCHES="a b c"       integration branches a HEAD must be contained in to count as merged.
#                       default: "main master" plus each repo's origin/HEAD target
#   BUILD_DIRS="..."    directory names treated as regenerable build output.
#                       default: "target build .dart_tool node_modules dist .next .gradle __pycache__"
#   DATA_DIRS="..."     directory names that are neither source nor build output: never deleted, never count as activity.
#                       default: ".work .venv .git"
#   IDLE_HOURS=24       build output is removable once the tree's sources have been untouched this long
#   MIN_DAYS=7          a worktree / scratch dir is removable once idle this long
#   MERGED=1            trees: ignore the idle window (any clean, merged, not-in-use worktree goes)
#   FILTER=glob         only consider entries matching the glob
#   APPLY=1             act; without it the script only reports
#
# Rules: "idle" = time since the newest of the HEAD commit, any source file written after checkout, and the checkout
# itself. Anything with an open file or a process cwd inside it (one lsof snapshot at start) is never touched.
# Build output is never deleted from a tree with uncommitted changes to tracked files (a build may be in progress).
# Standalone clones inside $WT_DIR (directories that are repos rather than registered worktrees) are never touched.
# Removing a worktree never deletes a branch. Works with bash 3.2+, BSD or GNU stat/find, macOS or Linux.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=${ROOT:-$(cd "$HERE/.." && pwd)}; cd "$ROOT" || exit 1
WT_DIR=${WT_DIR:-$ROOT/wt}; SCRATCH_DIR=${SCRATCH_DIR:-$WT_DIR/scratch}; KEEP_FILE=${KEEP_FILE:-$WT_DIR/.gc-keep}
MODE=${1:-report}; IDLE_HOURS=${IDLE_HOURS:-24}; MIN_DAYS=${MIN_DAYS:-7}; FILTER=${FILTER:-*}; APPLY=${APPLY:-}
BUILD_DIRS=${BUILD_DIRS:-"target build .dart_tool node_modules dist .next .gradle __pycache__"}
DATA_DIRS=${DATA_DIRS:-".work .venv .git"}
now=$(date +%s)
case $MODE in report|builds|trees|scratch|all) ;; *) echo "usage: $0 [report|builds|trees|scratch|all]  (see header for env knobs)"; exit 2;; esac
[ -d "$WT_DIR" ] || { echo "no worktree dir at $WT_DIR (set WT_DIR)"; exit 2; }

# portability: BSD vs GNU stat
if stat -f %m / >/dev/null 2>&1; then mtime() { stat -f %m "$@"; }; STAT_LOOP='for f; do stat -f %m "$f"; done'; else mtime() { stat -c %Y "$@"; }; STAT_LOOP='for f; do stat -c %Y "$f"; done'; fi
newest() { find "$@" -exec sh -c "$STAT_LOOP" _ {} + 2>/dev/null | sort -n | tail -1; }   # newest mtime among files matched by the find args
# find predicates built from the lists (arrays, so the patterns are never glob-expanded by the shell)
build_pred=(); for b in $BUILD_DIRS; do [ ${#build_pred[@]} -gt 0 ] && build_pred+=(-o); build_pred+=(-name "$b"); done
skip_pred=();  for b in $BUILD_DIRS $DATA_DIRS; do [ ${#skip_pred[@]} -gt 0 ] && skip_pred+=(-o); skip_pred+=(-path "*/$b/*"); done
KEEP=$( [ -f "$KEEP_FILE" ] && grep -v '^#' "$KEEP_FILE" | grep -v '^$' )
kept() { for k in $KEEP; do case "$1" in $k) return 0;; esac; done; return 1; }
OPEN=$(lsof -Fn 2>/dev/null | grep "^n$WT_DIR/" | cut -c2- | sort -u)     # one process snapshot
busy() { echo "$OPEN" | grep -q "^$WT_DIR/$1\(/\|$\)"; }
run() { if [ "$APPLY" = 1 ]; then "$@"; else echo "  + $*"; fi; }
gb() { awk -v k="$1" 'BEGIN{printf "%6.1fG", k/1048576}'; }
lines_for() { # repo -> integration branches to test (BASE_BRANCHES, else main/master + origin/HEAD)
  if [ -n "${BASE_BRANCHES:-}" ]; then echo "$BASE_BRANCHES"; return; fi
  local h; h=$(git -C "$1" symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')
  echo "main master $h"
}
idle_secs() { # worktree dir -> seconds since last activity
  local d=$1 h c t last
  h=$(git -C "$d" log -1 --format=%ct 2>/dev/null || echo 0); c=$(mtime "$d/.git")
  t=$(newest "$d" -type f -not -name .DS_Store -not \( "${skip_pred[@]}" \) -newer "$d/.git")
  last=$h; [ "$c" -gt "$last" ] && last=$c; [ -n "$t" ] && [ "$t" -gt "$last" ] && last=$t
  echo $((now-last))
}
tot_b=0; tot_t=0; tot_s=0; soon=0
if [ "$APPLY" = 1 ] && [ "$MODE" != report ]; then FREE=REMOVED; BANNER="APPLYING mode=$MODE: rows marked REMOVED are deleted"; else FREE=free; BANNER="REPORT ONLY: nothing is removed. 'free' = would be removed by APPLY=1, 'keep' = blocked, 'soon' = waiting out the idle window"; fi
echo "worktree-gc $(date '+%F %R')  root=$ROOT wt=$WT_DIR mode=$MODE idle_hours=$IDLE_HOURS min_days=$MIN_DAYS merged=${MERGED:-0} filter=$FILTER"
echo "$BANNER"; echo
echo "== build output in idle worktrees (regenerable: $BUILD_DIRS) =="
for d in "$WT_DIR"/$FILTER/; do d=${d%/}; n=${d#$WT_DIR/}; [ -L "$d" ] && continue; [ "$d" = "$SCRATCH_DIR" ] && continue
  git -C "$d" rev-parse --git-dir >/dev/null 2>&1 || continue; kept "$n" && continue
  dirs=$(find "$d" -mindepth 1 -maxdepth 3 -type d \( "${build_pred[@]}" \) -not \( "${skip_pred[@]}" \) 2>/dev/null)
  [ -z "$dirs" ] && continue
  dirs=$(echo "$dirs" | while read -r x; do [ -z "$(git -C "$d" ls-files -- "${x#$d/}" | head -1)" ] && echo "$x"; done)   # a dir with tracked files is source, not build output
  [ -z "$dirs" ] && continue
  sz=$(echo "$dirs" | tr '\n' '\0' | xargs -0 du -sk 2>/dev/null | awk '{s+=$1}END{print s+0}'); [ "$sz" -lt 51200 ] && continue   # <50M: ignore
  why=""; busy "$n" && why="in use"
  [ -z "$why" ] && [ $(idle_secs "$d") -lt $((IDLE_HOURS*3600)) ] && why="source changed within ${IDLE_HOURS}h (build may be wanted)"
  [ -z "$why" ] && [ -n "$(git -C "$d" status --porcelain --untracked-files=no)" ] && why="uncommitted changes"
  if [ -n "$why" ]; then printf "  keep %s %-28s %s\n" "$(gb $sz)" "$n" "$why"; continue; fi
  printf "  %s %s %-28s %s\n" "$FREE" "$(gb $sz)" "$n" "$(echo "$dirs" | sed "s#^$d/##" | tr '\n' ' ')"; tot_b=$((tot_b+sz))
  if [ "$MODE" = builds ] || [ "$MODE" = all ]; then echo "$dirs" | while read -r x; do run rm -rf "$x"; done; fi
done
echo "  -> $(gb $tot_b) removable build output"; echo
if [ "${MERGED:-}" = 1 ]; then echo "== worktrees (clean, merged into a line, no process; MERGED=1: idle window ignored) =="; else echo "== worktrees (clean, merged into a line, idle >= ${MIN_DAYS}d, no process) =="; fi
for d in "$WT_DIR"/$FILTER/; do d=${d%/}; n=${d#$WT_DIR/}; [ -L "$d" ] && continue; [ "$d" = "$SCRATCH_DIR" ] && continue
  gd=$(git -C "$d" rev-parse --git-dir 2>/dev/null) || continue; case "$gd" in */.git/worktrees/*) ;; *) continue;; esac   # standalone clones: never
  kept "$n" && continue
  repo=$(git -C "$d" rev-parse --git-common-dir); repo=$(cd "$d" && cd "$repo/.." && pwd)
  br=$(git -C "$d" symbolic-ref --short HEAD 2>/dev/null || echo "detached@$(git -C "$d" rev-parse --short HEAD)"); sz=$(du -sk "$d" | cut -f1)
  age=$(( $(idle_secs "$d") / 86400 )); why=""; m=""
  busy "$n" && why="in use"
  [ -z "$why" ] && [ -n "$(git -C "$d" status --porcelain | grep -v -e DS_Store)" ] && why="uncommitted changes"
  if [ -z "$why" ]; then for l in $(lines_for "$repo"); do git -C "$d" rev-parse -q --verify "refs/heads/$l" >/dev/null 2>&1 && git -C "$d" merge-base --is-ancestor HEAD "$l" 2>/dev/null && { m=$l; break; }; done; [ -z "$m" ] && why="unmerged ($br)"; fi
  [ -z "$why" ] && [ "${MERGED:-}" != 1 ] && [ "$age" -lt "$MIN_DAYS" ] && { why="clean, merged into $m; idle ${age}d < ${MIN_DAYS}d, eligible in $((MIN_DAYS-age))d"; soon=$((soon+sz)); }
  if [ -n "$why" ]; then tag=keep; case "$why" in clean*) tag=soon;; esac; printf "  %s %s %-28s %-32s %s\n" "$tag" "$(gb $sz)" "$n" "$br" "$why"; continue; fi
  printf "  %s %s %-28s %-32s idle %dd, in %s\n" "$FREE" "$(gb $sz)" "$n" "$br" "$age" "$m"; tot_t=$((tot_t+sz))
  if [ "$MODE" = trees ] || [ "$MODE" = all ]; then
    run git -C "$repo" worktree remove --force "$d" 2>/dev/null
    [ "$APPLY" = 1 ] && [ -d "$d" ] && ! git -C "$repo" worktree list --porcelain | grep -qx "worktree $d" && rm -rf "$d"   # registration gone, dir left (e.g. Finder .DS_Store race)
  fi
done
echo "  -> $(gb $tot_t) removable worktrees now; $(gb $soon) more become eligible as they pass ${MIN_DAYS}d idle (rows marked soon)"; echo
echo "== scratch dirs ($SCRATCH_DIR) whose worktree is gone and idle >= ${MIN_DAYS}d =="
if [ -d "$SCRATCH_DIR" ]; then for s in "$SCRATCH_DIR"/*/; do s=${s%/}; n=${s#$SCRATCH_DIR/}; case "$n" in $FILTER) ;; *) continue;; esac; kept "$n" && continue
  [ -d "$WT_DIR/$n" ] && continue; busy "${s#$WT_DIR/}" && continue
  t=$(newest "$s" -type f -not -name .DS_Store); [ -z "$t" ] && t=$(mtime "$s")
  age=$(( (now-t)/86400 )); [ "$age" -lt "$MIN_DAYS" ] && continue
  sz=$(du -sk "$s" | cut -f1); printf "  %s %s scratch/%-24s idle %dd\n" "$FREE" "$(gb $sz)" "$n" "$age"; tot_s=$((tot_s+sz))
  if [ "$MODE" = scratch ] || [ "$MODE" = all ]; then run rm -rf "$s"; fi
done; fi
echo "  -> $(gb $tot_s) removable scratch"
if [ "$MODE" = all ] && [ "$APPLY" = 1 ]; then for g in "$ROOT"/*/.git "$ROOT"/.git; do [ -e "$g" ] && git -C "$(dirname "$g")" worktree prune 2>/dev/null; done; fi
echo; if [ "$FREE" = REMOVED ]; then echo "total removed: $(gb $((tot_b+tot_t+tot_s)))"; else echo "total that APPLY=1 would remove: up to $(gb $((tot_b+tot_t+tot_s))) (build output inside removable worktrees is counted in both lines)"; fi
