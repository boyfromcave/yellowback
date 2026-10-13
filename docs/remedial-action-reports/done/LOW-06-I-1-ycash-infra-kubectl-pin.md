# LOW — 06/I-1 — `bitnami/kubectl:latest` is the only unpinned image in the Helm chart

Repos / branches to change: `ycash-infra` (`fix/06-I-1-kubectl-pin` off `upgrade/vault`).
Audit source: `docs/audits/quantum-vault-ecosystem/06-clients-wallets-infra.md:247-250` (I-1); verification `verification/06-verification.md:26` (verdict), `:76` ("verbatim"); consolidated `00-consolidated.md` row 06/Y-2..Y-5 and R10.
Status: done — completed 2026-10-13T07:12Z (merged locally on `upgrade/vault`; not yet pushed)

## 1. Finding

Every image in `charts/ycash-lightwallet/values.yaml` carries a tag (`local` on kind, ECR tags from `make eks-deploy`, `redis:7.4-alpine`, `postgres:17-alpine`) except the kind-only arming Job's `bitnami/kubectl`, which is `latest` with a comment recording "v1.37.1 on 2026-10-09". The Job runs with cluster credentials (it writes the attestor set id and payout address into the ConfigMap the StatefulSet reads and rolls lightwalletd), so an upstream tag move — Bitnami retired most of its free Docker Hub tags in 2025 and `latest` can change or vanish — either breaks the kind bring-up or runs an unreviewed image with write access to the namespace. kind-only, so no mainnet exposure; Low.

## 2. Root cause

- `ycash-infra/charts/ycash-lightwallet/values.yaml:12-13`:
  ```yaml
  # kind only (regtest.armYellowback): kubectl + curl + jq for the arming Job; v1.37.1 on 2026-10-09
  kubectl:      { repository: bitnami/kubectl,    tag: latest, pullPolicy: IfNotPresent }
  ```
- Rendered by `templates/_helpers.tpl:9` `{{- define "yc.image" -}}{{ .repository }}:{{ .tag }}{{- end -}}` (tag only; no digest form) into `templates/kind/arm.yaml:99-100` (`roll` container).
- No lint catches it: `.github/workflows/ci.yml:4-14` runs `helm lint` and `kubeconform` only.

## 3. Fix options considered

1. Pin the tag (`1.34.x`, the kubectl minor within ±1 of the kind node image's Kubernetes minor — read it from the kind config/`scripts/kind-up.sh` before choosing). Minimal; still trusts the registry not to move a tag.
2. Pin tag **and** digest (`repository@sha256:…`), extending `yc.image` with an optional `digest`. Accepted: `IfNotPresent` plus a digest makes the Job's image immutable; the comment keeps the human-readable version.
3. Replace the image with a minimal self-built `images/arm/Dockerfile` (alpine + kubectl + curl + jq, built by `make image-arm` like `images/faucet`). Best long-term (the chart already builds `yindex`, `web`, `faucet`); more work; offered as the follow-up if Bitnami's tags stop updating.

## 4. Recommended fix

1. `templates/_helpers.tpl:9`: `{{- define "yc.image" -}}{{ .repository }}:{{ .tag }}{{ with .digest }}@{{ . }}{{ end }}{{- end -}}`.
2. `values.yaml:13`: `kubectl: { repository: bitnami/kubectl, tag: "<pinned>", digest: "sha256:<pinned>", pullPolicy: IfNotPresent }`, with the comment stating the kind Kubernetes minor it matches and the date; `values-kind.yaml` inherits.
3. CI lint (`.github/workflows/ci.yml` `lint` job): `! grep -rnE 'tag: *latest|tag: *""' charts/*/values*.yaml` and `helm template … | ! grep -E 'image: .*:latest'` so the next `latest` fails the build.
4. `docs/` (the infra plan's image table): record the pin and the bump procedure (`docker pull`, `docker inspect --format '{{index .RepoDigests 0}}'`).

## 5. Tests

- `helm template t charts/ycash-lightwallet -f charts/ycash-lightwallet/values-kind.yaml | grep 'image: bitnami/kubectl'` shows `repo:tag@sha256:…`; `kubeconform` still passes (the existing CI step).
- `make kind-up` + the arming Job completes on a clean kind cluster (the existing `scripts/smoke.sh`/`parity.sh` path) with the pinned image.
- The new lint fails on a throwaway commit that sets `tag: latest` (prove once in the PR).

## 6. Acceptance criteria

- No `latest` in any `values*.yaml`; `yc.image` supports `digest`; CI lint present; smoke on kind green.

## 7. Risks and side effects

- A digest pin must be bumped by hand; the lint and the comment make it visible. kind-only; EKS unaffected (the Job is behind `regtest.armYellowback`).

## 8. Effort estimate and dependencies

- 1–2 hours. No dependencies. Option 3 (self-built arm image) as a separate follow-up if wanted.

## Completion record

- **Completed:** 2026-10-13T07:12Z
- **ycash-infra** `upgrade/vault` merge 01c8b50 (branch `fix/clients`): 6644d22.
  - `bitnami/kubectl` is pinned by its multi-arch digest `sha256:999d5eb2…52b7` (kubectl v1.37.1); `yc.image` renders `repo[:tag][@digest]`.
  - New `scripts/lint-images.sh`, run in `make lint` and CI, fails on `latest` or any unpinned rendered image.
  - The bump procedure is in the infra plan §1.3.
- **Deviation:** pinned by digest only, because Bitnami publishes no versioned tag any more.
- **Tests:** `make lint` green (helm lint kind + EKS, kubeconform 39/39); the negative cases fail as intended. Open: a kind smoke run with the merged chart.
