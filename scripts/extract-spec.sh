#!/usr/bin/env bash
# Publish the plan's normative sections and the RPC contract through a tool, not a copy
# (plan Phase 0; N29, P4, P7). The whole contract — what is read, what is written, how the
# JSON is shaped — is documented at the top of scripts/extract_spec.py, which does the work.
#
# Usage: scripts/extract-spec.sh            write every copy         (`make spec`)
#        scripts/extract-spec.sh --check    exit 1 when any is stale  (`make spec-check`, run by `make status`)
#        scripts/extract-spec.sh --check-workspace   only the copies in this repo (the workspace CI, which has no clones)
#        scripts/extract-spec.sh --check-upgrade     the upgrade/vault line's copies in the integration worktrees
#                                                    (`make spec-check-upgrade`; trees that do not exist are skipped)
#
# Python is always the workspace venv (.venv, created by `make bootstrap`); python3 is the
# fallback only so a bare checkout can still run the check.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
exec "$PY" "$ROOT/scripts/extract_spec.py" "${1:---write}"
