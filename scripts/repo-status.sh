#!/usr/bin/env bash
# Pretty per-repo git status for the Yellowback (YED) workspace.
#
# Usage: scripts/repo-status.sh [--short] [--no-fetch]
# Pins are supplied by the Makefile via the environment; the defaults here
# keep the script useful when run directly.
#
# Every writable repo with an `origin` is fetched (quietly, --prune) before its branch is
# compared with the remote — without that, `@{u}` is only as fresh as the last fetch and the
# script happily reports "in sync" against a stale remote-tracking ref. A fetch writes only
# remote-tracking refs; nothing is merged, checked out or discarded (that is `make pull`).
# --no-fetch (or NOFETCH=1) compares against the last fetch instead, e.g. when offline.
# ref/ repos are never fetched: they are detached at a pin and their .git is read-only.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# repos.yaml is the single source of truth. The Makefile exports these; when the script is
# run directly, read the manifest rather than repeat its values here — a stale copy in this
# file is how `make status` came to report a branch expectation nothing else believed.
manifest() { "$ROOT/scripts/repos.sh" get "$1" "$2" 2>/dev/null; }
DIGIBYTE_PIN="${DIGIBYTE_PIN:-$(manifest ref/digibyte tag)}"
YCASH_PIN="${YCASH_PIN:-$(manifest ref/ycash tag)}"
YECWALLET_PIN="${YECWALLET_PIN:-$(manifest ref/yecwallet tag)}"
LWD_PIN="${LWD_PIN:-$(manifest ref/lightwalletd commit)}"      # no upstream tag: pinned by commit
DD_BRANCH="${DD_BRANCH:-$(manifest ycash-dd branch)}"
WALLET_BRANCH="${WALLET_BRANCH:-$(manifest yecwallet-dd branch)}"
DD_BASE="${DD_BASE:-$(manifest ycash-dd base)}"
WALLET_BASE="${WALLET_BASE:-$(manifest yecwallet-dd base)}"
LWD_BRANCH="${LWD_BRANCH:-$(manifest lightwalletd-dd branch)}"
LWD_BASE="${LWD_BASE:-$(manifest lightwalletd-dd base)}"
YEW_BRANCH="${YEW_BRANCH:-$(manifest yew branch)}"

SHORT=0; FETCH=1
[ -n "${NOFETCH:-}" ] && FETCH=0
for arg in "$@"; do
  case "$arg" in
    --short)    SHORT=1 ;;
    --no-fetch) FETCH=0 ;;
    *) printf 'usage: %s [--short] [--no-fetch]\n' "$0" >&2; exit 2 ;;
  esac
done

# --- colour -----------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-dumb}" != "dumb" ]; then
  B=$'\033[1m'; D=$'\033[2m'; R=$'\033[0m'
  RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; CYA=$'\033[36m'
else
  B=""; D=""; R=""; RED=""; GRN=""; YEL=""; CYA=""
fi

OK="${GRN}✔${R}"; WARN="${YEL}●${R}"; BAD="${RED}✘${R}"
DIRTY_ANY=0; PIN_DRIFT=0; BRANCH_DRIFT=0
BEHIND_ANY=0; AHEAD_ANY=0; DIVERGED_ANY=0; FETCH_FAILED=0
ACTIONS=()   # one suggested command per out-of-sync repo, printed in the summary

field() { printf "    ${D}%-8s${R} %s\n" "$1" "$2"; }

# repo_status <label> <path> <expected-tag-or-commit|-> <expected-branch|-> [fork-base|-]
# The pin is a tag, or — for a reference whose upstream publishes no tags — a commit prefix.
# An app repo (repos.yaml role `app`) passes `-` as the base: branch check only, no fork delta.
repo_status() {
  local label="$1" path="$2" want_tag="$3" want_branch="$4" base="${5:-$DD_BASE}"

  if [ ! -e "$path/.git" ]; then
    printf "\n${B}▸ %s${R}  ${D}%s${R}\n" "$label" "$path"
    field "" "${BAD} not a git repository"
    PIN_DRIFT=1
    return
  fi

  local g=(git -C "$path")

  # access: ref/ worktrees are chmod a-w on purpose
  local access
  if [ -w "$path" ]; then access="writable"; else access="${CYA}read-only${R}"; fi

  printf "\n${B}▸ %s${R}  ${D}%s  (%s)${R}\n" "$label" "$path" "$(printf '%b' "$access")"

  # --- HEAD ---
  local branch tag head_desc
  branch="$("${g[@]}" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  tag="$("${g[@]}" describe --tags --exact-match HEAD 2>/dev/null)"
  if [ "$branch" = "HEAD" ]; then
    head_desc="${tag:-$("${g[@]}" rev-parse --short HEAD)} ${D}(detached)${R}"
  else
    head_desc="$branch"
    [ -n "$tag" ] && head_desc="$head_desc ${D}(= $tag)${R}"
  fi

  # pin / branch expectations
  if [ "$want_tag" != "-" ]; then
    if [ "$tag" = "$want_tag" ] || case "$("${g[@]}" rev-parse HEAD)" in "$want_tag"*) true ;; *) false ;; esac; then
      head_desc="$head_desc  ${OK} ${D}pinned${R}"
    else
      head_desc="$head_desc  ${BAD} ${RED}expected $want_tag${R}"
      PIN_DRIFT=1
    fi
  fi
  if [ "$want_branch" != "-" ]; then
    if [ "$branch" = "$want_branch" ]; then
      head_desc="$head_desc  ${OK}"
    else
      head_desc="$head_desc  ${WARN} ${YEL}expected branch $want_branch${R}"
      BRANCH_DRIFT=1
    fi
  fi
  field "HEAD" "$(printf '%b' "$head_desc")"

  # --- commit ---
  local sha subj
  sha="$("${g[@]}" rev-parse --short HEAD 2>/dev/null)"
  subj="$("${g[@]}" log -1 --format=%s 2>/dev/null)"
  [ "${#subj}" -gt 58 ] && subj="${subj:0:57}…"
  field "commit" "$(printf '%b' "${CYA}${sha}${R}  ${subj}")"

  # --- worktree ---
  local porc staged unstaged untracked tree
  porc="$("${g[@]}" status --porcelain 2>/dev/null)"
  if [ -z "$porc" ]; then
    tree="${OK} clean"
  else
    staged=$(  printf '%s\n' "$porc" | grep -c '^[MADRC]'   || true)
    unstaged=$(printf '%s\n' "$porc" | grep -c '^.[MD]'     || true)
    untracked=$(printf '%s\n' "$porc" | grep -c '^??'       || true)
    tree="${WARN} ${YEL}dirty${R} ${D}—${R} ${staged} staged, ${unstaged} unstaged, ${untracked} untracked"
    DIRTY_ANY=1
  fi
  field "tree" "$(printf '%b' "$tree")"

  # --- upstream ---
  # Fetch first (writable repos only): the remote-tracking ref is the thing being compared
  # against, and it is stale until somebody fetches. Failure (offline, no origin) is reported
  # on the line, not hidden — a comparison against a stale ref is then labelled as such.
  local up counts behind ahead rel fetched="" fnote=""
  up="$("${g[@]}" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)"
  if [ -n "$up" ] && [ "$FETCH" -eq 1 ] && [ -w "$path/.git" ]; then
    if "${g[@]}" fetch --quiet --prune origin 2>/dev/null; then
      fetched=1
    else
      FETCH_FAILED=1; fnote=" ${RED}(fetch failed — offline? comparing against last fetch)${R}"
    fi
  elif [ -n "$up" ] && [ "$FETCH" -eq 0 ]; then
    fnote=" ${D}(not fetched — as of last fetch)${R}"
  fi
  if [ -n "$up" ]; then
    counts="$("${g[@]}" rev-list --left-right --count "${up}...HEAD" 2>/dev/null)"
    behind="${counts%%	*}"; ahead="${counts##*	}"
    if [ "$behind" = "0" ] && [ "$ahead" = "0" ]; then
      rel="${OK} in sync with ${up}${fnote}"
    elif [ "$ahead" = "0" ]; then
      rel="${WARN} ${YEL}${behind} behind${R} ${up}${fnote} ${D}— run \`make pull\` (or: git -C ${path} merge --ff-only ${up})${R}"
      BEHIND_ANY=1; ACTIONS+=("${path}: ${behind} behind ${up} → make pull   (or: git -C ${path} merge --ff-only ${up})")
    elif [ "$behind" = "0" ]; then
      rel="${WARN} ${YEL}${ahead} ahead${R} of ${up}${fnote} ${D}— unpushed: git -C ${path} push${R}"
      AHEAD_ANY=1; ACTIONS+=("${path}: ${ahead} unpushed commit(s) → git -C ${path} push")
    else
      rel="${BAD} ${RED}diverged${R} — ${ahead} ahead, ${behind} behind ${up}${fnote} ${D}— git -C ${path} rebase ${up}${R}"
      DIVERGED_ANY=1; ACTIONS+=("${path}: diverged (${ahead} ahead, ${behind} behind ${up}) → git -C ${path} rebase ${up}, then push")
    fi
  else
    rel="${D}no upstream tracking branch${R}"
  fi
  field "remote" "$(printf '%b' "$rel")"

  # --- fork delta, working repo only ---
  if [ "$want_branch" != "-" ] && [ "$base" != "-" ] && "${g[@]}" rev-parse --verify --quiet "$base" >/dev/null; then
    local files ins del stat_line
    stat_line="$("${g[@]}" diff --shortstat "${base}...HEAD" 2>/dev/null)"
    if [ -z "$stat_line" ]; then
      field "fork" "$(printf '%b' "${D}no changes vs ${base}${R}")"
    else
      field "fork" "$(printf '%b' "${YEL}${stat_line# }${R} ${D}vs ${base}${R}")"
    fi
  fi

  # --- file-level detail ---
  if [ "$SHORT" -eq 0 ] && [ -n "$porc" ]; then
    printf '%s\n' "$porc" | head -20 | sed "s/^/        ${D}/;s/\$/${R}/"
    local n; n=$(printf '%s\n' "$porc" | wc -l | tr -d ' ')
    [ "$n" -gt 20 ] && printf "        ${D}… and %d more${R}\n" "$((n - 20))"
  fi
}

printf "${B}%s${R} ${D}— repo status${R}\n" "$(basename "$ROOT")"
printf "${D}%s${R}\n" "$(printf '─%.0s' $(seq 1 64))"

repo_status "workspace"    "."            "-"                "-"
repo_status "ref/digibyte" "ref/digibyte" "$DIGIBYTE_PIN"    "-"
repo_status "ref/ycash"    "ref/ycash"    "$YCASH_PIN"       "-"
repo_status "ref/yecwallet" "ref/yecwallet" "$YECWALLET_PIN" "-"
repo_status "ref/lightwalletd" "ref/lightwalletd" "$LWD_PIN" "-"
repo_status "ycash-dd"     "ycash-dd"     "-"                "$DD_BRANCH"    "$DD_BASE"
repo_status "yecwallet-dd" "yecwallet-dd" "-"                "$WALLET_BRANCH" "$WALLET_BASE"
repo_status "lightwalletd-dd" "lightwalletd-dd" "-"          "$LWD_BRANCH"   "$LWD_BASE"
repo_status "yew"          "yew"          "-"                "$YEW_BRANCH"   "-"

printf "\n${D}%s${R}\n" "$(printf '─%.0s' $(seq 1 64))"
print_actions() {
  local a
  for a in "${ACTIONS[@]}"; do printf "  ${D}%s${R}\n" "$a"; done
}
[ "$FETCH_FAILED" -ne 0 ] && printf "${WARN} ${YEL}fetch failed${R} for at least one repo — remote comparisons there are against the last fetch.\n"
if [ "$PIN_DRIFT" -ne 0 ]; then
  printf "${BAD} ${RED}pin drift${R} — a ref/ repo is not at its expected tag.\n"
  printf "  ${D}Pins are recorded in AGENTS.md and docs/mapping.md. Re-pin, or update both.${R}\n"
  exit 1
elif [ "$BRANCH_DRIFT" -ne 0 ]; then
  printf "${WARN} ${YEL}branch drift${R} — a fork or app repo is not on the branch repos.yaml records.\n"
  printf "  ${D}Check out the expected branch, or update repos.yaml (and its mirrors in AGENTS.md and README.md).${R}\n"
  [ "$DIRTY_ANY" -ne 0 ] && printf "  ${D}Uncommitted changes are also present.${R}\n"
  exit 1
elif [ "$DIVERGED_ANY" -ne 0 ]; then
  printf "${BAD} ${RED}diverged from remote${R} — local and origin both have commits the other lacks. \`make pull\` will skip these; resolve by hand:\n"
  print_actions
  exit 1
elif [ "$BEHIND_ANY" -ne 0 ] || [ "$AHEAD_ANY" -ne 0 ]; then
  if [ "$BEHIND_ANY" -ne 0 ]; then
    printf "${WARN} ${YEL}behind remote${R} — origin has newer commits. Run ${B}make pull${R} (fast-forward only; a dirty repo is skipped, commit or stash first).\n"
  fi
  if [ "$AHEAD_ANY" -ne 0 ]; then
    printf "${WARN} ${YEL}unpushed commits${R} — local commits origin does not have yet. Push when ready.\n"
  fi
  print_actions
  [ "$DIRTY_ANY" -ne 0 ] && printf "  ${D}Uncommitted changes are also present.${R}\n"
elif [ "$DIRTY_ANY" -ne 0 ]; then
  printf "${WARN} pins OK, in sync with remotes; uncommitted changes present.\n"
else
  printf "${OK} all repos clean, at expected pins and in sync with their remotes.\n"
fi
