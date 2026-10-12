#!/bin/bash
# wt-gc: dynamic garbage collector for the wt/ directory. Measures everything at run time; nothing is hard-coded.
#
#   bash utils/wt-gc.sh                 report: what is removable now, grouped, with sizes (default; touches nothing)
#   APPLY=1 bash utils/wt-gc.sh builds  remove regenerable build output (target/, build/, .dart_tool/, node_modules/) in idle trees
#   APPLY=1 bash utils/wt-gc.sh trees   remove idle worktrees whose work is already merged (branches are kept)
#   APPLY=1 bash utils/wt-gc.sh scratch remove wt/scratch/<name> dirs whose worktree is gone and which are idle
#   APPLY=1 bash utils/wt-gc.sh all     the three above, then `git worktree prune` in every repo
#
# Knobs (env):  IDLE_HOURS=24   build output is removable once the tree has had no source change for this long
#               MIN_DAYS=7      a worktree is removable once idle this long (and clean, merged, no process)
#               FILTER=glob     only consider wt entries matching the glob (e.g. FILTER='ci*')
#               MERGED=1        trees mode ignores the idle window: any clean, merged, not-in-use worktree goes (branch kept)
#               KEEP file       wt/.gc-keep lists names or globs never touched (one per line)
# "Idle" = time since the newest of: HEAD commit, newest non-build file written after checkout, worktree creation.
# A tree with any open file or process cwd inside it is never touched, whatever its age.
# Build output is never deleted from a tree with uncommitted changes to tracked files (a build may be in progress).
# .work/ (calibration sweep data) and .venv are never touched: they are data, not build output.
set -u
cd "$(cd "$(dirname "$0")/.." && pwd)"   # the workspace root, wherever the checkout lives
MODE=${1:-report}; IDLE_HOURS=${IDLE_HOURS:-24}; MIN_DAYS=${MIN_DAYS:-7}; FILTER=${FILTER:-*}
APPLY=${APPLY:-}; now=$(date +%s)
LINES="upgrade/vault harden/yellowback main master"
BUILD_NAMES='-name target -o -name build -o -name .dart_tool -o -name node_modules'
KEEP=$( [ -f wt/.gc-keep ] && grep -v '^#' wt/.gc-keep | grep -v '^$' )
kept() { for k in $KEEP; do case "$1" in $k) return 0;; esac; done; return 1; }
# one process snapshot: every open path and cwd under wt/
OPEN=$(lsof -Fn 2>/dev/null | grep "^n$PWD/wt/" | cut -c2- | sort -u)
busy() { echo "$OPEN" | grep -q "^$PWD/wt/$1\(/\|$\)"; }
run() { if [ "$APPLY" = 1 ]; then "$@"; else echo "  + $*"; fi; }
gb() { awk -v k="$1" 'BEGIN{printf "%6.1fG", k/1048576}'; }
idle_secs() { # worktree dir -> seconds since last activity
  local d=$1 h c t last
  h=$(git -C "$d" log -1 --format=%ct 2>/dev/null || echo 0); c=$(stat -f %m "$d/.git")
  t=$(find "$d" -type f -not -name .DS_Store -not \( -path "*/target/*" -o -path "*/build/*" -o -path "*/.dart_tool/*" -o -path "*/node_modules/*" -o -path "*/.work/*" -o -path "*/.venv/*" -o -path "*/.git/*" \) -newer "$d/.git" -print0 2>/dev/null | xargs -0 stat -f %m 2>/dev/null | sort -n | tail -1)
  last=$h; [ "$c" -gt "$last" ] && last=$c; [ -n "$t" ] && [ "$t" -gt "$last" ] && last=$t
  echo $((now-last))
}
tot_b=0; tot_t=0; tot_s=0; soon=0
if [ "$APPLY" = 1 ] && [ "$MODE" != report ]; then FREE=REMOVED; BANNER="APPLYING mode=$MODE: rows marked REMOVED are deleted"; else FREE=free; BANNER="REPORT ONLY: nothing is removed. 'free' = would be removed by APPLY=1, 'keep' = blocked, 'soon' = waiting out the idle window"; fi
echo "wt-gc $(date '+%F %R')  mode=$MODE idle_hours=$IDLE_HOURS min_days=$MIN_DAYS merged=${MERGED:-0} filter=$FILTER"
echo "$BANNER"
echo
echo "== build output in idle worktrees (regenerable) =="
for d in wt/$FILTER/; do d=${d%/}; n=${d#wt/}; [ -L "$d" ] && continue; [ "$n" = scratch ] && continue
  git -C "$d" rev-parse --git-dir >/dev/null 2>&1 || continue; kept "$n" && continue
  dirs=$(find "$d" -mindepth 1 -maxdepth 3 -type d \( $BUILD_NAMES \) -not -path '*/.git/*' -not -path '*/.work/*' -not -path '*/node_modules/*' -not -path '*/target/*' 2>/dev/null)
  [ -z "$dirs" ] && continue
  dirs=$(echo "$dirs" | while read -r x; do [ -z "$(git -C "$d" ls-files -- "${x#$d/}" | head -1)" ] && echo "$x"; done)   # a dir with tracked files is source, not build output
  [ -z "$dirs" ] && continue
  sz=$(echo "$dirs" | tr '\n' '\0' | xargs -0 du -sk 2>/dev/null | awk '{s+=$1}END{print s+0}'); [ "$sz" -lt 51200 ] && continue   # <50M: ignore
  why=""; busy "$n" && why="in use"
  [ -z "$why" ] && [ $(idle_secs "$d") -lt $((IDLE_HOURS*3600)) ] && why="source changed within ${IDLE_HOURS}h (build may be wanted)"
  [ -z "$why" ] && [ -n "$(git -C "$d" status --porcelain --untracked-files=no)" ] && why="uncommitted changes"
  if [ -n "$why" ]; then printf "  keep %s %-28s %s\n" "$(gb $sz)" "$n" "$why"; continue; fi
  printf "  %s %s %-28s %s\n" "$FREE" "$(gb $sz)" "$n" "$(echo "$dirs" | sed "s#^$d/##" | tr '\n' ' ')"; tot_b=$((tot_b+sz))
  if [ "$MODE" = builds ] || [ "$MODE" = all ]; then echo "$dirs" | while read x; do run rm -rf "$x"; done; fi
done
echo "  -> $(gb $tot_b) removable build output"
echo
if [ "${MERGED:-}" = 1 ]; then echo "== worktrees (clean, merged into a line, no process; MERGED=1: idle window ignored) =="; else echo "== worktrees (clean, merged into a line, idle >= ${MIN_DAYS}d, no process) =="; fi
for d in wt/$FILTER/; do d=${d%/}; n=${d#wt/}; [ -L "$d" ] && continue; [ "$n" = scratch ] && continue
  gd=$(git -C "$d" rev-parse --git-dir 2>/dev/null) || continue; case "$gd" in */.git/worktrees/*) ;; *) continue;; esac   # standalone clones are never touched
  kept "$n" && continue
  repo=$(git -C "$d" rev-parse --git-common-dir); repo=$(cd "$d/$repo/.." 2>/dev/null && pwd || dirname "$repo")
  br=$(git -C "$d" symbolic-ref --short HEAD 2>/dev/null || echo DETACHED); sz=$(du -sk "$d" | cut -f1)
  age=$(( $(idle_secs "$d") / 86400 )); why=""
  busy "$n" && why="in use"
  [ -z "$why" ] && [ -n "$(git -C "$d" status --porcelain | grep -v -e DS_Store -e '^?? target$')" ] && why="uncommitted changes"
  if [ -z "$why" ]; then m=""; for l in $LINES; do git -C "$d" rev-parse -q --verify "refs/heads/$l" >/dev/null 2>&1 && git -C "$d" merge-base --is-ancestor HEAD "$l" 2>/dev/null && { m=$l; break; }; done; [ -z "$m" ] && why="unmerged ($br)"; fi
  [ -z "$why" ] && [ "${MERGED:-}" != 1 ] && [ "$age" -lt "$MIN_DAYS" ] && { why="clean, merged into $m; idle ${age}d < ${MIN_DAYS}d, eligible in $((MIN_DAYS-age))d"; soon=$((soon+sz)); }
  [ "$br" = DETACHED ] && br="detached@$(git -C "$d" rev-parse --short HEAD)"
  if [ -n "$why" ]; then tag=keep; case "$why" in clean*) tag=soon;; esac; printf "  %s %s %-28s %-32s %s\n" "$tag" "$(gb $sz)" "$n" "$br" "$why"; continue; fi
  printf "  %s %s %-28s %-32s idle %dd, in %s\n" "$FREE" "$(gb $sz)" "$n" "$br" "$age" "$m"; tot_t=$((tot_t+sz))
  if [ "$MODE" = trees ] || [ "$MODE" = all ]; then
    run git -C "$repo" worktree remove --force "$d" 2>/dev/null
    [ "$APPLY" = 1 ] && [ -d "$d" ] && ! git -C "$repo" worktree list --porcelain | grep -qx "worktree $PWD/$d" && rm -rf "$d"   # Finder .DS_Store race
  fi
done
echo "  -> $(gb $tot_t) removable worktrees now; $(gb $soon) more become eligible as they pass ${MIN_DAYS}d idle (rows marked soon)"
echo
echo "== scratch dirs whose worktree is gone and idle >= ${MIN_DAYS}d =="
for s in wt/scratch/*/; do s=${s%/}; n=${s#wt/scratch/}; case "$n" in $FILTER) ;; *) continue;; esac; kept "$n" && continue
  [ -d "wt/$n" ] && continue; busy "scratch/$n" && continue
  t=$(find "$s" -type f -not -name .DS_Store -print0 2>/dev/null | xargs -0 stat -f %m 2>/dev/null | sort -n | tail -1); [ -z "$t" ] && t=$(stat -f %m "$s")
  age=$(( (now-t)/86400 )); [ "$age" -lt "$MIN_DAYS" ] && continue
  sz=$(du -sk "$s" | cut -f1); printf "  %s %s scratch/%-24s idle %dd\n" "$FREE" "$(gb $sz)" "$n" "$age"; tot_s=$((tot_s+sz))
  if [ "$MODE" = scratch ] || [ "$MODE" = all ]; then run rm -rf "$s"; fi
done
echo "  -> $(gb $tot_s) removable scratch"
if [ "$MODE" = all ] && [ "$APPLY" = 1 ]; then for r in $(git worktree list --porcelain >/dev/null 2>&1; ls -d */.git 2>/dev/null | xargs -n1 dirname) .; do git -C "$r" worktree prune 2>/dev/null; done; fi
echo; if [ "$FREE" = REMOVED ]; then echo "total removed: $(gb $((tot_b+tot_t+tot_s)))"; else echo "total that APPLY=1 would remove: up to $(gb $((tot_b+tot_t+tot_s))) (build output inside removable worktrees is counted in both lines)   e.g. APPLY=1 bash utils/wt-gc.sh all"; fi
