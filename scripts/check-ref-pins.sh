#!/usr/bin/env bash
# Copyright (c) 2026 The Ycash developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://www.opensource.org/licenses/mit-license.php .
#
# Verify every reference pin in repos.yaml against its upstream, without a local clone:
#   - a tag pin: the tag still exists upstream and still points at the recorded commit;
#   - a commit pin (upstream publishes no tags): the commit is still in the history of the recorded
#     upstream `branch` (a force-push or history rewrite that drops it is caught). Only the commit
#     graph is fetched (--filter=tree:0), so even the large histories take seconds.
# Exits 1 on the first pin that no longer holds. Used by .github/workflows/workspace-check.yml.
#
#   usage: scripts/check-ref-pins.sh            (REPOS_FILE overrides the manifest, as for repos.sh)

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOS="$ROOT/scripts/repos.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail=0
for r in $("$REPOS" list); do
  [ "$("$REPOS" get "$r" role)" = reference ] || continue
  url=$("$REPOS" get "$r" url); tag=$("$REPOS" get "$r" tag)
  commit=$("$REPOS" get "$r" commit); branch=$("$REPOS" get "$r" branch)
  if [ -n "$tag" ]; then
    # An annotated tag lists the tag object and, with ^{}, the peeled commit: take the peel.
    out=$(git ls-remote --tags "$url" "refs/tags/$tag" "refs/tags/$tag^{}")
    at=$(printf '%s\n' "$out" | awk '/\^\{\}$/{print $1; f=1} END{if(!f) exit 1}') \
      || at=$(printf '%s\n' "$out" | awk 'NR==1{print $1}')
    case "$at" in
      "$commit"*) echo "ok    $r tag $tag = $commit" ;;
      "")         echo "GONE  $r: tag $tag no longer exists upstream"; fail=1 ;;
      *)          echo "MOVED $r: tag $tag now $at, manifest says $commit"; fail=1 ;;
    esac
  else
    if [ -z "$branch" ]; then echo "BAD   $r: commit pin without a branch field"; fail=1; continue; fi
    g="$TMP/${r//\//_}.git"
    git init -q --bare "$g"
    if ! git -C "$g" fetch -q --no-tags --filter=tree:0 "$url" "refs/heads/$branch" 2>/dev/null; then
      echo "GONE  $r: branch $branch no longer exists upstream"; fail=1; continue
    fi
    if git -C "$g" rev-parse -q --verify "$commit^{commit}" >/dev/null \
       && git -C "$g" merge-base --is-ancestor "$commit" FETCH_HEAD; then
      echo "ok    $r commit $commit in upstream $branch ($(git -C "$g" rev-parse --short FETCH_HEAD) now)"
    else
      echo "MOVED $r: commit $commit is no longer in upstream $branch"; fail=1
    fi
  fi
done
exit $fail
