#!/usr/bin/env bash
# Pretty per-repo git status for the ydollar workspace.
#
# Usage: scripts/repo-status.sh [--short]
# Pins are supplied by the Makefile via the environment; the defaults here
# keep the script useful when run directly.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DIGIBYTE_PIN="${DIGIBYTE_PIN:-v9.26.5}"
YCASH_PIN="${YCASH_PIN:-v4.5.0}"
DD_BRANCH="${DD_BRANCH:-feature/digidollar}"
DD_BASE="${DD_BASE:-ycash-legacy}"

SHORT=0
[ "${1:-}" = "--short" ] && SHORT=1

# --- colour -----------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-dumb}" != "dumb" ]; then
  B=$'\033[1m'; D=$'\033[2m'; R=$'\033[0m'
  RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; CYA=$'\033[36m'
else
  B=""; D=""; R=""; RED=""; GRN=""; YEL=""; CYA=""
fi

OK="${GRN}✔${R}"; WARN="${YEL}●${R}"; BAD="${RED}✘${R}"
DIRTY_ANY=0; PIN_DRIFT=0

field() { printf "    ${D}%-8s${R} %s\n" "$1" "$2"; }

# repo_status <label> <path> <expected-tag|-> <expected-branch|->
repo_status() {
  local label="$1" path="$2" want_tag="$3" want_branch="$4"

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
    if [ "$tag" = "$want_tag" ]; then
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
  local up counts behind ahead rel
  up="$("${g[@]}" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)"
  if [ -n "$up" ]; then
    counts="$("${g[@]}" rev-list --left-right --count "${up}...HEAD" 2>/dev/null)"
    behind="${counts%%	*}"; ahead="${counts##*	}"
    if [ "$behind" = "0" ] && [ "$ahead" = "0" ]; then
      rel="${OK} in sync with ${up}"
    else
      rel="${WARN} ${ahead} ahead, ${behind} behind ${up}"
    fi
  else
    rel="${D}no upstream tracking branch${R}"
  fi
  field "remote" "$(printf '%b' "$rel")"

  # --- fork delta, working repo only ---
  if [ "$want_branch" != "-" ] && "${g[@]}" rev-parse --verify --quiet "$DD_BASE" >/dev/null; then
    local files ins del stat_line
    stat_line="$("${g[@]}" diff --shortstat "${DD_BASE}...HEAD" 2>/dev/null)"
    if [ -z "$stat_line" ]; then
      field "fork" "$(printf '%b' "${D}no changes vs ${DD_BASE}${R}")"
    else
      field "fork" "$(printf '%b' "${YEL}${stat_line# }${R} ${D}vs ${DD_BASE}${R}")"
    fi
  fi

  # --- file-level detail ---
  if [ "$SHORT" -eq 0 ] && [ -n "$porc" ]; then
    printf '%s\n' "$porc" | head -20 | sed "s/^/        ${D}/;s/\$/${R}/"
    local n; n=$(printf '%s\n' "$porc" | wc -l | tr -d ' ')
    [ "$n" -gt 20 ] && printf "        ${D}… and %d more${R}\n" "$((n - 20))"
  fi
}

printf "${B}ydollar-workspace${R} ${D}— repo status${R}\n"
printf "${D}%s${R}\n" "$(printf '─%.0s' $(seq 1 64))"

repo_status "workspace"    "."            "-"                "-"
repo_status "ref/digibyte" "ref/digibyte" "$DIGIBYTE_PIN"    "-"
repo_status "ref/ycash"    "ref/ycash"    "$YCASH_PIN"       "-"
repo_status "ycash-dd"     "ycash-dd"     "-"                "$DD_BRANCH"

printf "\n${D}%s${R}\n" "$(printf '─%.0s' $(seq 1 64))"
if [ "$PIN_DRIFT" -ne 0 ]; then
  printf "${BAD} ${RED}pin drift${R} — a ref/ repo is not at its expected tag.\n"
  printf "  ${D}Pins are recorded in AGENTS.md and docs/mapping.md. Re-pin, or update both.${R}\n"
  exit 1
elif [ "$DIRTY_ANY" -ne 0 ]; then
  printf "${WARN} pins OK; uncommitted changes present.\n"
else
  printf "${OK} all repos clean and at expected pins.\n"
fi
