# Security CI

Every Yellowback repository runs the same security legs in GitHub Actions, in three workflows:
`semgrep.yml`, `codeql.yml` and `secops.yml`. Results go to *Security → Code scanning* (SARIF, one
category per tool) and to each run's summary. The only pull requests the legs ever open are Semgrep's
rolling bucket PRs (at most four, `semgrep/critical|high|medium|low`, updated in place) and at most one
grouped Dependabot security PR per ecosystem.

## This repository

The workspace repository holds documents, the manifest (`repos.yaml`) and the workspace scripts
(bash, a little Python, the `Makefile`). The nested component clones are gitignored and are never
scanned from here; each component repository scans itself (table below).

| Leg | Workflow / job | Scans | Gate | Accepting a finding |
|---|---|---|---|---|
| Semgrep | `semgrep.yml` | semgrep-rules `bash`, `python/lang/security`, `generic/secrets`, `yaml/github-actions`; Trail of Bits `python`, `generic`, `yaml/github-actions`; the workspace rules in `contrib/semgrep/rules/workspace.yaml` | PR: fails on a new `critical` finding (diff-aware). Push/nightly: report, then the bucket PRs | `contrib/semgrep/accepted.json` with a reason ([README](contrib/semgrep/README.md)) |
| CodeQL | `codeql.yml` | `python`, `actions` (`security-extended`, no build) | new alerts only, through code scanning; pre-existing alerts never fail a PR | dismiss the alert in code scanning with a reason |
| Workflow security | `secops.yml` / `zizmor` | every workflow and `dependabot.yml`, default persona, online audits | fails on any finding | fix it; an inline `# zizmor: ignore[<audit>]` only with a reason beside it |
| Secrets | `secops.yml` / `gitleaks` | PR: its own commits. Push, nightly 03:43 UTC, dispatch: the full history | fails on a leak | `.gitleaksignore` fingerprint, only for test vectors or public constants, with a reason comment. A real secret is rotated, never ignored |
| Dependency vulnerabilities | `secops.yml` / `osv-scanner` | every lockfile: `requirements.txt`, `contrib/semgrep/requirements.txt`, `contrib/secops/zizmor-requirements.txt` | fails on a known vulnerability | `osv-scanner.toml` `[[IgnoredVulns]]` with `reason` and `ignoreUntil` at most 90 days out |
| Dependabot | `.github/dependabot.yml` | `github-actions`, `pip` (`/`, `/contrib/secops`) | security updates only, one grouped PR per ecosystem | — |

The workspace rules guard the scripts' own invariants: no download piped into a shell
(`pipe-to-shell`), no literal clone URL outside `repos.yaml` (`clone-without-manifest`), and every
function that clones a reference or fork checks the result against the manifest's commit pin
(`pinned-clone-unverified`; role `app` repositories track a branch and have no pin). Their test inputs
are `contrib/semgrep/rules/workspace.sh`:
`semgrep --test --metrics=off contrib/semgrep/rules`.

Not run here, and why: pip-audit (the root `requirements.txt` is the developer venv for the node repos'
test framework, unpinned ranges; OSV-Scanner covers it and the hash-locked tool files), Go, Rust,
Solidity, JavaScript and IaC scanners (no such code in this repository).

Tool versions are exact and verified: release binaries against a sha256 recorded in `secops.yml`,
PyPI tools with `pip --require-hashes`, every action pinned to a full commit SHA.

## Every repository

The legs each repository runs, as the security CI rollout (2026-10) sets them up. `—` = no such code
in that repository.

| Repository | Semgrep | CodeQL | zizmor | gitleaks | OSV-Scanner | Language-specific | Dependabot (security) |
|---|---|---|---|---|---|---|---|
| yellowback (workspace) | bash, python, actions, secrets | python, actions | yes | yes | pip | — | github-actions, pip |
| ycash-dd | c, rust, python, bash, dockerfile, secrets, actions | c-cpp, python, rust, actions | yes | yes | Cargo, pip | cargo-deny | github-actions, cargo, pip, docker |
| ycash6 | c, rust, python, bash, dockerfile, secrets, actions | c-cpp, python, rust, actions | yes | yes | Cargo, pip | cargo-deny | github-actions, cargo, pip, docker |
| librustzcash6 | rust, python, secrets, actions | rust, python, actions | yes | yes | Cargo | cargo-deny | github-actions, cargo |
| yecwallet-dd | c, python, typescript, dockerfile, secrets, actions | c-cpp, javascript-typescript, python, actions | yes | yes | — | — | github-actions, docker |
| lightwalletd-dd | go, dockerfile, secrets, actions | go, actions | yes | yes | Go | govulncheck, gosec | github-actions, gomod, docker |
| yew | dart (generic), rust, python, secrets, actions | rust, python, actions | yes | yes | pub, Cargo | — | github-actions, pub, cargo |
| yolo | rust, secrets, actions | rust, actions | yes | yes | Cargo | cargo-deny | github-actions, cargo |
| chain-viz | rust, secrets, actions | rust, actions | yes | yes | Cargo | cargo-deny | github-actions, cargo |
| x402-ycash | rust, go, typescript, python, dockerfile, secrets, actions | rust, go, javascript-typescript, python, actions | yes | yes | Cargo, Go, npm | cargo-deny, govulncheck, gosec, npm audit | github-actions, cargo, gomod, npm, docker |
| yb-calibration | python, secrets, actions | python, actions | yes | yes | pip | pip-audit | github-actions, pip |
| wyec | solidity, typescript, secrets, actions | javascript-typescript, actions | yes | yes | npm | Slither, npm audit | github-actions, npm |
| hawkeye | rust, solidity, python, secrets, actions | rust, python, actions | yes | yes | Cargo, npm | cargo-deny, Slither | github-actions, cargo, npm |
| ycash-infra | go, terraform, kubernetes, dockerfile, python, secrets, actions | go, python, actions | yes | yes | Go | govulncheck, gosec, Checkov | github-actions, gomod, docker, terraform |

Each repository's own `SECURITY-CI.md` (or its docs) is authoritative for its exceptions.
