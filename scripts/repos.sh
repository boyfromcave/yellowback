#!/usr/bin/env bash
# Minimal reader for repos.yaml (see the schema comment at the top of that file).
#
#   scripts/repos.sh list               every repository path, one per line
#   scripts/repos.sh get <path> <key>   one field's value (empty string, exit 0, if absent)
#   scripts/repos.sh fields <path>      every key=value of one repository
#
# REPOS_FILE overrides the manifest location (used by the bootstrap self-test).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="${REPOS_FILE:-$ROOT/repos.yaml}"
[ -r "$FILE" ] || { echo "repos.sh: manifest not found: $FILE" >&2; exit 2; }

# Section lines: `path:` unindented. Field lines: two spaces, `key: value [# comment]`.
parse() {
  awk -v mode="$1" -v want="${2:-}" -v key="${3:-}" '
    /^[^ \t#][^:]*:[ \t]*$/ {
      sec = $0; sub(/:[ \t]*$/, "", sec)
      if (mode == "list") print sec
      next
    }
    /^  [A-Za-z][A-Za-z0-9_-]*:/ {
      if (mode == "list" || sec != want) next
      line = $0; sub(/^  /, "", line)
      k = line; sub(/:.*/, "", k)
      v = line; sub(/^[^:]*:[ \t]*/, "", v); sub(/[ \t]+#.*$/, "", v); sub(/[ \t]+$/, "", v)
      if (mode == "fields") print k "=" v
      else if (k == key) { print v; exit }
    }
  ' "$FILE"
}

case "${1:-}" in
  list)   parse list ;;
  get)    [ $# -eq 3 ] || { echo "usage: repos.sh get <path> <key>" >&2; exit 2; }; parse get "$2" "$3" ;;
  fields) [ $# -eq 2 ] || { echo "usage: repos.sh fields <path>" >&2; exit 2; }; parse fields "$2" ;;
  *)      sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
esac
