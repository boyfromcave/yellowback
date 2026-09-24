#!/usr/bin/env bash
# Bring every repository in this workspace up to date with its remote, safely.
#
#   scripts/pull.sh [--dry-run] [--no-ref] [--short]
#
#   --dry-run  print what would be fetched/advanced and exit without touching anything
#   --no-ref   skip the ref/ repositories (no network for the read-only pins)
#   --short    pass --short to the closing `make status`
#
# The rule is fast-forward only, everywhere. Nothing here can lose a commit:
#
#   workspace   fetch, then fast-forward the current branch onto its upstream.
#   forks       fetch origin, fast-forward the feature branch (checked out) and the
#               -legacy baseline (updated by ref, never checked out). 'upstream' is
#               never fetched: re-basing the fork onto a newer Ycash is a deliberate
#               act, not something a pull does behind your back.
#   ref/        detached at a tag; there is nothing to advance. A read-only ls-remote
#               re-checks that the pinned tag still resolves to the commit repos.yaml records —
#               if it moved upstream, every file:line citation in docs/mapping.md is
#               suspect and this script says so loudly.
#
# A repository with uncommitted changes, no upstream, or a diverged branch is SKIPPED
# with an explanation of the git command to run yourself. `make pull` never merges,
# never rebases and never discards; `git reset --hard` stays something you type by hand,
# in the one repository you mean.
#
# Worktrees under wt/ are machine-local scratch branches (AGENTS.md, wt/): they are
# reported, never touched.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOS="$ROOT/scripts/repos.sh"
cd "$ROOT"

DRY=0; DO_REF=1; SHORT=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --no-ref)  DO_REF=0 ;;
    --short)   SHORT=1 ;;
    -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "pull: unknown option $a" >&2; exit 2 ;;
  esac
done

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-dumb}" != "dumb" ]; then
  B=$'\033[1m'; D=$'\033[2m'; R=$'\033[0m'
  RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; CYA=$'\033[36m'
else
  B=""; D=""; R=""; RED=""; GRN=""; YEL=""; CYA=""
fi
OK="${GRN}✔${R}"; WARN="${YEL}●${R}"; BAD="${RED}✘${R}"

SKIPPED=0; DRIFT=0; ADVANCED=0
say()  { printf '%s\n' "$*"; }
item() { printf "    %b\n" "$*"; }
ok()   { item "${OK} $*"; }
skip() { item "${WARN} ${YEL}skipped${R} — $*"; SKIPPED=$((SKIPPED + 1)); }
bad()  { item "${BAD} ${RED}$*${R}"; DRIFT=1; }
head2() { printf "\n${B}▸ %s${R}  ${D}%s${R}\n" "$1" "$2"; }
run()  { if [ "$DRY" -eq 1 ]; then item "${D}\$ $*${R}"; else "$@"; fi; }

dirty() { [ -n "$(git -C "$1" status --porcelain 2>/dev/null)" ]; }

# fast_forward <path> <branch>: advance a CHECKED-OUT branch onto its upstream.
fast_forward() {
  local dir="$1" br="$2" up counts behind ahead
  up="$(git -C "$dir" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)"
  if [ -z "$up" ]; then
    skip "$br has no upstream ${D}(git -C $dir branch -u origin/$br)${R}"; return
  fi
  counts="$(git -C "$dir" rev-list --left-right --count "${up}...HEAD" 2>/dev/null)"
  behind="${counts%%	*}"; ahead="${counts##*	}"
  if [ "$behind" = "0" ]; then
    if [ "$ahead" = "0" ]; then ok "$br up to date with $up"
    else ok "$br up to date with $up ${D}($ahead local commit(s) to push)${R}"; fi
    return
  fi
  if [ "$ahead" != "0" ]; then
    skip "$br has diverged: $ahead ahead, $behind behind $up ${D}(git -C $dir rebase $up)${R}"; return
  fi
  if dirty "$dir"; then
    skip "$br is $behind behind $up but the tree is dirty ${D}(commit or stash first)${R}"; return
  fi
  if [ "$DRY" -eq 1 ]; then
    item "${D}\$ git -C $dir merge --ff-only $up${R} ${D}(+$behind)${R}"; return
  fi
  if git -C "$dir" merge --ff-only --quiet "$up" 2>/dev/null; then
    ok "$br fast-forwarded $behind commit(s) to $(git -C "$dir" rev-parse --short HEAD)"
    ADVANCED=$((ADVANCED + 1))
  else
    skip "$br could not fast-forward onto $up ${D}(git -C $dir status)${R}"
  fi
}

# ff_ref <path> <branch>: advance a branch that is NOT checked out, by ref.
# `git fetch origin b:b` is fast-forward-only by definition — a non-ff is an error,
# never a rewrite — so a diverged baseline reports instead of moving.
ff_ref() {
  local dir="$1" br="$2" before after
  git -C "$dir" rev-parse --verify --quiet "$br" >/dev/null || {
    skip "baseline $br missing ${D}(git -C $dir branch --track $br origin/$br)${R}"; return; }
  git -C "$dir" rev-parse --verify --quiet "origin/$br" >/dev/null || {
    skip "origin/$br missing"; return; }
  before="$(git -C "$dir" rev-parse "$br")"
  [ "$before" = "$(git -C "$dir" rev-parse "origin/$br")" ] && { ok "$br up to date"; return; }
  if [ "$DRY" -eq 1 ]; then item "${D}\$ git -C $dir fetch origin $br:$br${R}"; return; fi
  if git -C "$dir" fetch --quiet origin "$br:$br" 2>/dev/null; then
    after="$(git -C "$dir" rev-parse --short "$br")"
    ok "$br fast-forwarded to $after"
    ADVANCED=$((ADVANCED + 1))
  else
    skip "$br has diverged from origin/$br ${D}(a baseline should never diverge — investigate)${R}"
  fi
}

pull_workspace() {
  head2 "workspace" "."
  local br; br="$(git rev-parse --abbrev-ref HEAD)"
  run git fetch --quiet --prune origin || { bad "fetch failed"; return; }
  fast_forward "." "$br"
}

pull_fork() {
  local path="$1" branch="$2" base="$3"
  head2 "$path" "fork"
  [ -e "$path/.git" ] || { bad "not a git repository — run 'make bootstrap'"; return; }
  run git -C "$path" fetch --quiet --prune origin || { bad "fetch origin failed"; return; }
  local cur; cur="$(git -C "$path" rev-parse --abbrev-ref HEAD)"
  if [ "$cur" = "$branch" ]; then
    fast_forward "$path" "$branch"
  else
    skip "on '$cur', not $branch ${D}(git -C $path checkout $branch)${R}"
  fi
  ff_ref "$path" "$base"
}

# A reference is verified, never advanced. ls-remote is deliberate: it asks the remote
# what the tag points at without fetching an object or writing a single byte into the
# clone — which matters, because ref/ working trees are chmod a-w and at least one of
# these clones has a read-only .git too, where `git fetch` cannot even open FETCH_HEAD.
pull_ref() {
  local path="$1" tag="$2" commit="$3" url="$4"
  head2 "$path" "reference, pinned ${tag:-commit $commit}"
  [ -e "$path/.git" ] || { bad "not a git repository — run 'make bootstrap'"; return; }
  if [ -z "$tag" ]; then   # pinned by commit: nothing upstream can move it, only local drift matters
    case "$(git -C "$path" rev-parse HEAD)" in
      "$commit"*) ok "still pinned at $commit; nothing to pull" ;;
      *) bad "HEAD is $(git -C "$path" rev-parse --short HEAD), not the pin $commit ${D}(local drift — see AGENTS.md rule 1)${R}" ;;
    esac
    return
  fi
  if [ "$DRY" -eq 1 ]; then item "${D}\$ git ls-remote --tags $url refs/tags/$tag${R}"; return; fi
  local out at
  out="$(git ls-remote --tags "$url" "refs/tags/$tag" "refs/tags/$tag^{}" 2>/dev/null)" \
    || { skip "ls-remote failed (offline?)"; return; }
  # An annotated tag lists both the tag object and the peeled commit (^{}); prefer the peel.
  at="$(printf '%s\n' "$out" | awk '/\^\{\}$/ {print $1; found=1} END {exit !found}')" \
    || at="$(printf '%s\n' "$out" | awk 'NR==1 {print $1}')"
  local local_head; local_head="$(git -C "$path" rev-parse HEAD)"
  if [ -z "$at" ]; then
    bad "tag $tag no longer exists at $url"
  elif case "$at" in "$commit"*) false ;; *) true ;; esac; then
    bad "tag $tag now resolves to ${at:0:10} upstream, repos.yaml says $commit — THE TAG MOVED"
    item "${D}Every file:line citation in docs/mapping.md was taken at $commit.${R}"
    item "${D}Do not re-pin casually: AGENTS.md rule 1 (chmod -R u+w $path → checkout →${R}"
    item "${D}chmod -R a-w), then update repos.yaml, AGENTS.md and docs/mapping.md together.${R}"
  elif case "$local_head" in "$commit"*) false ;; *) true ;; esac; then
    bad "HEAD is ${local_head:0:10}, not the pin $commit ${D}(local drift — see AGENTS.md rule 1)${R}"
  else
    ok "still pinned at $tag ($commit) upstream and locally; nothing to pull"
  fi
}

printf "${B}%s${R} ${D}— pull (fast-forward only)%s${R}\n" "$(basename "$ROOT")" \
  "$([ "$DRY" -eq 1 ] && printf ', dry run')"

pull_workspace
for path in $("$REPOS" list); do
  case "$("$REPOS" get "$path" role)" in
    reference) [ "$DO_REF" -eq 1 ] && pull_ref "$path" \
                 "$("$REPOS" get "$path" tag)" "$("$REPOS" get "$path" commit)" \
                 "$("$REPOS" get "$path" url)" ;;
    fork)      pull_fork "$path" \
                 "$("$REPOS" get "$path" branch)" "$("$REPOS" get "$path" base)" ;;
  esac
done

# Worktrees: reported, never touched — they carry per-agent branches (AGENTS.md, wt/).
if [ -d "$ROOT/wt" ]; then
  n=0; d=0
  for w in "$ROOT"/wt/*/; do
    [ -e "$w/.git" ] || continue
    n=$((n + 1)); dirty "$w" && d=$((d + 1))
  done
  if [ "$n" -gt 0 ]; then
    printf "\n${B}▸ wt/${R}  ${D}%d worktree(s), %d dirty — not touched by pull${R}\n" "$n" "$d"
  fi
fi

printf "\n${D}%s${R}\n" "$(printf '─%.0s' $(seq 1 64))"
if [ "$DRY" -eq 1 ]; then
  printf "${D}dry run: nothing was fetched or advanced.${R}\n"; exit 0
fi
[ "$ADVANCED" -gt 0 ] && printf "${OK} %d branch(es) advanced.\n" "$ADVANCED"
[ "$SKIPPED"  -gt 0 ] && printf "${WARN} %d skipped — see above; each needs a decision from you.\n" "$SKIPPED"
[ "$DRIFT" -ne 0 ] && { printf "${BAD} ${RED}pin problem — see above.${R}\n"; exit 1; }

say
make -C "$ROOT" --no-print-directory "$([ "$SHORT" -eq 1 ] && echo status-short || echo status)" || exit $?
[ "$SKIPPED" -gt 0 ] && exit 1
exit 0
