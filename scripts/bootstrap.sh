#!/usr/bin/env bash
# Recreate this workspace on a fresh machine from repos.yaml: the read-only reference clones at
# their pins, the working forks on their feature branch, and the Python venv.
#
#   scripts/bootstrap.sh [--ssh] [--no-venv] [--dry-run]
#
#   --ssh      clone the working forks over git@github.com: (you intend to push); references
#              stay on https, they are never pushed to
#   --no-venv  skip the Python virtual environment
#   --dry-run  print what would be done and exit
#
# Idempotent: a repository that already exists is verified against the manifest and left alone
# (nothing is fetched, checked out or chmod'ed behind your back); the venv is created only if
# missing and its requirements are (re)installed. Builds are NOT started: see
# ycash-dd/doc/yellowback.md and yecwallet-dd/docs/yellowback.md for the build recipes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOS="$ROOT/scripts/repos.sh"
WORKSPACE="${WORKSPACE_ROOT:-$ROOT}"     # the self-test points this at a scratch directory
REQUIREMENTS="$ROOT/requirements.txt"

SSH=0; VENV=1; DRY=0
for a in "$@"; do
  case "$a" in
    --ssh) SSH=1 ;;
    --no-venv) VENV=0 ;;
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "bootstrap: unknown option $a" >&2; exit 2 ;;
  esac
done

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then B=$'\033[1m'; D=$'\033[2m'; R=$'\033[0m'; G=$'\033[32m'; Y=$'\033[33m'; E=$'\033[31m'
else B=""; D=""; R=""; G=""; Y=""; E=""; fi
say()  { printf '%s\n' "$*"; }
ok()   { printf "  ${G}✔${R} %s\n" "$*"; }
warn() { printf "  ${Y}●${R} %s\n" "$*"; WARNINGS=$((WARNINGS + 1)); }
die()  { printf "  ${E}✘${R} %s\n" "$*" >&2; exit 1; }
run()  { if [ "$DRY" -eq 1 ]; then printf "  ${D}\$ %s${R}\n" "$*"; else "$@"; fi; }
WARNINGS=0

command -v git >/dev/null || die "git is required"
if [ "$VENV" -eq 1 ] && ! command -v python3 >/dev/null && ! command -v uv >/dev/null; then
  die "python3 (or uv) is required for the venv; pass --no-venv to skip it"
fi

ssh_url() {  # https://github.com/owner/repo.git -> git@github.com:owner/repo.git
  case "$1" in
    https://github.com/*) printf 'git@github.com:%s\n' "${1#https://github.com/}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}
head_is() {  # <path> <short-commit>: HEAD starts with the pinned prefix
  case "$(git -C "$1" rev-parse HEAD)" in "$2"*) return 0 ;; *) return 1 ;; esac
}

bootstrap_reference() {
  local path="$1" url="$2" tag="$3" commit="$4" dir="$WORKSPACE/$path"
  # No tag (the manifest omits it): the pin is the commit itself, detached.
  if [ -e "$dir/.git" ]; then
    local have; have="$(git -C "$dir" describe --tags --exact-match HEAD 2>/dev/null || true)"
    if [ "$have" = "$tag" ] && head_is "$dir" "$commit"; then ok "$path exists at ${tag:-commit} $commit"
    else warn "$path exists but is at '${have:-$(git -C "$dir" rev-parse --short HEAD)}', expected ${tag:-commit} $commit — see AGENTS.md rule 1 to re-pin"; fi
    if [ -w "$dir" ]; then warn "$path is writable; it should be read-only (chmod -R a-w, .git kept writable)"; fi
    return
  fi
  say "  cloning $path from $url"
  run git -c advice.detachedHead=false clone --quiet "$url" "$dir"
  run git -C "$dir" -c advice.detachedHead=false checkout --quiet --detach "${tag:+tags/$tag}${tag:-$commit}"
  if [ "$DRY" -eq 0 ] && [ -n "$tag" ]; then
    head_is "$dir" "$commit" || die "$path: tag $tag resolves to $(git -C "$dir" rev-parse --short HEAD), manifest says $commit — the tag moved upstream; do not proceed without updating the pin deliberately"
  fi
  # Enforce "never edit the reference" on the filesystem; git itself still needs its metadata.
  run chmod -R a-w "$dir"
  run chmod -R u+w "$dir/.git"
  ok "$path cloned, detached at ${tag:-$commit}, read-only"
}

bootstrap_fork() {
  local path="$1" url="$2" upstream="$3" branch="$4" base="$5" base_commit="$6" dir="$WORKSPACE/$path"
  [ "$SSH" -eq 1 ] && url="$(ssh_url "$url")"
  if [ -e "$dir/.git" ]; then
    local cur; cur="$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    if [ "$cur" = "$branch" ]; then ok "$path exists on $branch"; else warn "$path exists but is on '$cur', expected $branch"; fi
    if git -C "$dir" rev-parse --verify --quiet "$base" >/dev/null; then
      case "$(git -C "$dir" rev-parse "$base")" in
        "$base_commit"*) ok "$path: $base = $base_commit" ;;
        *) warn "$path: $base is $(git -C "$dir" rev-parse --short "$base"), manifest says $base_commit" ;;
      esac
    else warn "$path: baseline branch $base missing (git -C $path branch --track $base origin/$base)"; fi
    if [ -n "$upstream" ] && ! git -C "$dir" remote get-url upstream >/dev/null 2>&1; then
      warn "$path: remote 'upstream' missing (git -C $path remote add upstream $upstream)"; fi
    return
  fi
  say "  cloning $path from $url"
  run git clone --quiet --branch "$branch" "$url" "$dir"
  run git -C "$dir" branch --quiet --track "$base" "origin/$base"
  if [ -n "$upstream" ]; then run git -C "$dir" remote add upstream "$upstream"; fi
  if [ "$DRY" -eq 0 ]; then
    case "$(git -C "$dir" rev-parse "$base")" in
      "$base_commit"*) ;;
      *) die "$path: $base is $(git -C "$dir" rev-parse --short "$base"), manifest says $base_commit — the baseline must equal the reference pin" ;;
    esac
  fi
  ok "$path cloned on $branch; $base tracks origin/$base${upstream:+; remote 'upstream' = $upstream (not fetched)}"
}

bootstrap_venv() {
  local venv="$WORKSPACE/.venv" py="$WORKSPACE/.venv/bin/python"
  if [ -x "$py" ]; then ok ".venv exists ($("$py" --version 2>&1))"
  elif command -v uv >/dev/null; then say "  creating .venv with uv"; run uv venv --quiet "$venv"
  else say "  creating .venv with python3 -m venv"; run python3 -m venv "$venv"; fi
  if [ "$DRY" -eq 1 ]; then run "$py" -m pip install -q -r "$REQUIREMENTS"; return; fi
  if "$py" -m pip --version >/dev/null 2>&1; then "$py" -m pip install -q -r "$REQUIREMENTS"
  else uv pip install --quiet --python "$py" -r "$REQUIREMENTS"; fi
  # pyblake2 shim: the inherited test framework imports it; the stdlib has the same API.
  local site; site="$("$py" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
  printf '%s\n' '"""Shim: pyblake2 is unmaintained; Python 3.6+ has hashlib.blake2b with the same API."""' \
                'from hashlib import blake2b, blake2s  # noqa: F401' > "$site/pyblake2.py"
  "$py" -c 'import asyncore, zmq, requests, simplejson, pyblake2' || die "venv import check failed"
  ok ".venv ready: $(sed -n 's/^\([a-z0-9]*\)[>=].*/\1/p' "$REQUIREMENTS" | tr '\n' ' ')+ pyblake2 shim"
}

say "${B}$(basename "$WORKSPACE")${R} ${D}— bootstrap from repos.yaml${R}${DRY:+}"
if [ "$DRY" -eq 1 ]; then say "  ${D}(dry run: nothing will be changed)${R}"; fi
for path in $("$REPOS" list); do
  role="$("$REPOS" get "$path" role)"
  case "$role" in
    reference) bootstrap_reference "$path" "$("$REPOS" get "$path" url)" "$("$REPOS" get "$path" tag)" "$("$REPOS" get "$path" commit)" ;;
    fork)      bootstrap_fork "$path" "$("$REPOS" get "$path" url)" "$("$REPOS" get "$path" upstream)" \
                              "$("$REPOS" get "$path" branch)" "$("$REPOS" get "$path" base)" "$("$REPOS" get "$path" base-commit)" ;;
    *) die "$path: unknown role '$role' in repos.yaml" ;;
  esac
done
if [ "$VENV" -eq 1 ]; then bootstrap_venv; fi

if [ "$DRY" -eq 0 ] && [ "$WORKSPACE" = "$ROOT" ]; then
  say; make -C "$ROOT" --no-print-directory status-short || true
fi
if [ "$WARNINGS" -gt 0 ]; then say; say "  ${Y}$WARNINGS warning(s) above.${R}"; exit 1; fi
