#!/usr/bin/env bash
# Minimal reader for repos.yaml (see the schema comment at the top of that file).
#
#   scripts/repos.sh list               every repository path of the selected line, one per line
#   scripts/repos.sh get <path> <key>   one field's value (empty string, exit 0, if absent)
#   scripts/repos.sh fields <path>      every key=value of one repository
#
# LINE selects the release line: `vault` (the default) or `yugen`. `list` leaves out a
# repository whose `lines` field does not name it; `get <path> branch` returns `branch-<LINE>`
# where the repository has one, else `branch`.
# REPOS_FILE overrides the manifest location (used by the bootstrap self-test).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="${REPOS_FILE:-$ROOT/repos.yaml}"
[ -r "$FILE" ] || { echo "repos.sh: manifest not found: $FILE" >&2; exit 2; }
LINE="${LINE:-vault}"
case "$LINE" in vault|yugen) ;; *) echo "repos.sh: unknown LINE '$LINE' (vault or yugen)" >&2; exit 2 ;; esac

# Section lines: `path:` unindented. Field lines: two spaces, `key: value [# comment]`.
parse() {
  awk -v mode="$1" -v want="${2:-}" -v key="${3:-}" -v line="$LINE" '
    function flush() {   # list: the previous section, unless its `lines` leaves LINE out
      if (mode == "list" && sec != "" && (lines == "" || index(" " lines " ", " " line " ")))
        print sec
    }
    /^[^ \t#][^:]*:[ \t]*$/ {
      flush(); sec = $0; sub(/:[ \t]*$/, "", sec); lines = ""
      next
    }
    /^  [A-Za-z][A-Za-z0-9_-]*:/ {
      l = $0; sub(/^  /, "", l)
      k = l; sub(/:.*/, "", k)
      v = l; sub(/^[^:]*:[ \t]*/, "", v); sub(/[ \t]+#.*$/, "", v); sub(/[ \t]+$/, "", v)
      if (mode == "list") { if (k == "lines") lines = v; next }
      if (sec != want) next
      if (mode == "fields") print k "=" v
      else if (k == key) val = v
      else if (key == "branch" && k == "branch-" line) over = v
    }
    END {
      flush()
      if (mode == "get") print (over != "" ? over : val)
    }
  ' "$FILE"
}

case "${1:-}" in
  list)   parse list ;;
  get)    [ $# -eq 3 ] || { echo "usage: repos.sh get <path> <key>" >&2; exit 2; }; parse get "$2" "$3" ;;
  fields) [ $# -eq 2 ] || { echo "usage: repos.sh fields <path>" >&2; exit 2; }; parse fields "$2" ;;
  *)      sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
esac
