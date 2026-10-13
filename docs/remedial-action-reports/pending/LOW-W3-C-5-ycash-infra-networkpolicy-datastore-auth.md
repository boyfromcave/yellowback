# LOW — W3-C-5 — ycash-infra: no NetworkPolicy, Redis without auth, a fixed Postgres password, and node RPC reachable from every pod

Repos / branches to change: `ycash-infra` (`fix/W3-C-5-networkpolicy` off `upgrade/vault`). No node or lightwalletd change: the node image's `rpcallowip` default is overridden by environment, which the image already supports.
Audit source: wave 3 `docs/audits/quantum-vault-ecosystem-wave3/06-clients-wallets-infra.md:47` (summary), `:345-356` (W3-C-5), `:358-374` (sound list: secrets, TLS, yindex trust); verification `docs/audits/quantum-vault-ecosystem-wave3/verification/06-verification.md:19` (verdict), `:214-222` (confirmed, "the proposed default-deny policy set is the right fix"); consolidated `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:53`. Wave 4 `docs/audits/quantum-vault-ecosystem-wave4/04-clients-wyec-recheck.md:55` (STILL OPEN: no `NetworkPolicy`, `redis.yaml:23` without `--requirepass`, `deployment.yaml:3, 120` fixed password).
Status: pending — re-verified at ycash-infra `9d19079` (unchanged since wave 3; every line below re-grepped) and the node image source `ycash-dd` `da5e0fe` (`contrib/docker/ycashd/entrypoint.sh:23-24` unchanged) (2026-10-13)

## 1. Finding

The `ycash-lightwallet` chart ships no `NetworkPolicy`. Every pod in the cluster, from any namespace, can therefore open:
- `ycashd`'s RPC port: a `ClusterIP` Service. The node image binds `rpcbind=0.0.0.0` and allows the RFC 1918 ranges, so pod IPs pass. The RPC credentials still gate calls.
- Redis: started with no `--requirepass`.
- the in-cluster Postgres that backs `yindex`: user and password both `yindex`, hard-coded in the template.

A compromised or merely buggy unrelated workload (another tenant's pod, a sidecar, a debug pod) could rewrite the address index that `yindex` serves to light wallets as their UTXO set, or poison the cache, without any credential. The address index matters most. Through the YED token path a forged UTXO row was one ingredient of W3-C-1; that is now closed on the wallet side by `MEDIUM-W3-C-1-…`. Elsewhere a forged row cannot produce a valid signature (ZIP-243 commits to the amount), so the remaining exposure is availability and display.

Mitigations in place: EKS uses RDS rather than the in-cluster Postgres (`values-eks.yaml:28-30`), with its URL from External Secrets; the RPC credentials come from a Secret or External Secrets. Not in place: any network-layer restriction, on either kind or EKS. Redis is deployed on both, although nothing reads it (§2). Low.

## 2. Root cause (ycash-infra `9d19079`; node image `ycash-dd` `da5e0fe`)

- `grep -rn NetworkPolicy charts/ infra/` returns nothing.
- RPC:
  - `charts/ycash-lightwallet/templates/ycashd/service.yaml:1-15` is a `ClusterIP` on `rpc`; `:17-30` is the headless Service with `rpc` and `p2p`.
  - `templates/kind/regtest.yaml:63-68` adds a NodePort for RPC (kind only, `regtest.rpcNodePort` 30832; used by the host-run `scripts/kind-personas.py`).
  - `ycash-dd/contrib/docker/ycashd/entrypoint.sh:23-24`: `rpcbind=${YCASHD_RPC_BIND:-0.0.0.0}`, `rpcallowip` from `${YCASHD_RPC_ALLOWIP:-127.0.0.1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16}`.
  - `templates/ycashd/statefulset.yaml:36-58` sets neither `YCASHD_RPC_BIND` nor `YCASHD_RPC_ALLOWIP`.
- Redis:
  - `templates/yindex/redis.yaml:23`: `args: ["--maxmemory", …, "--maxmemory-policy", "allkeys-lru", "--save", ""]`, no `--requirepass`; `:28-33` Service on 6379.
  - `values.yaml:86-89` `redis.enabled: true`; `values-eks.yaml:31-33` sizes it for EKS.
  - **No consumer.** `grep -rli redis yindex/ images/ scripts/` is empty. lightwalletd-dd's verdict cache is in-process: `docs/plans/ycash-infra-plan.md:118` (K3b) says "Not Redis … the chart's Redis is unused by lightwalletd until a vendoring decision".
- Postgres:
  - `templates/yindex/deployment.yaml:3` `$pgUrl := printf "postgres://yindex:yindex@%s-postgres:5432/yindex?sslmode=disable"`, used at `:33` (yindex) and `:77` (yindex-ingest).
  - `:119-121` `POSTGRES_USER=yindex`, `POSTGRES_PASSWORD=yindex` ("in-cluster only; EKS uses RDS").
  - `:138-142` Service on 5432.
  - EKS path: `:35-36`, `:79-80` read `url` from `yindex.postgres.existingSecret`, filled by `templates/externalsecrets.yaml:12-23`.
- Who legitimately talks to what. Components are labelled `app.kubernetes.io/component` (§4 table); the namespaces outside the release are:
  - gateway: Envoy Gateway's proxies run in `envoy-gateway-system` (`infra/eks/addons.tf:11-17`, `scripts/kind-up.sh:19`). Routes reach `yindex:9070`, `lightwalletd:9067`, `web:8080` (`templates/gateway/routes.yaml:22, 27, 39`);
  - monitoring: kube-prometheus-stack scrapes `lightwalletd:9068` and `yindex:9071` (`templates/observability/servicemonitor.yaml`; namespace `monitoring.grafana.namespace`, default `monitoring`).
- CNI:
  - kind uses its default `kindnetd` (`kind/kind.yaml` sets no `networking.disableDefaultCNI`). Recent kind releases enforce NetworkPolicy in kindnetd; **this must be confirmed on the pinned kind v0.33.0 with the negative test in §5** before it is relied on.
  - EKS: `infra/eks/main.tf:51` `vpc-cni = {}`. The VPC CNI enforces NetworkPolicy only with `enableNetworkPolicy: "true"` in its addon configuration.

## 3. Fix options considered

1. **Default-deny NetworkPolicy per component plus explicit allows** (the audit's fix; the verifier agrees). Accepted.
2. **Bind RPC to localhost and run lightwalletd/yindex as sidecars of `ycashd`.** Rejected: it breaks the pool design, where N nodes serve M lightwalletd replicas through one Service (`service.yaml:1`), and it changes the chart's scaling model.
3. **Narrow `rpcallowip` to the pod CIDR only.** Accepted as a second layer, not instead of option 1: on most CNIs every pod in every namespace shares the pod CIDR, so it does not separate tenants.
4. **Redis: add auth.** Accepted for when it is enabled. But nothing uses Redis, so first **turn it off by default**. A data store with no reader is pure attack surface.
5. **Postgres: chart-generated random password in a Secret, preserved across upgrades with `lookup`.** Accepted for the in-cluster (kind) path. EKS already uses RDS with a terraform-generated secret.

## 4. Recommended fix

1. **NetworkPolicies.** New `templates/networkpolicy.yaml`, rendered when `networkPolicy.enabled` (default `true`; new values block). For each component below, one ingress policy with `policyTypes: [Ingress]` and `podSelector` on `app.kubernetes.io/instance` + `component`. Ingress only, for the first PR: egress rules (DNS, node P2P to the internet, RDS, ACME) differ per cloud and are where outages come from. A second PR adds egress once the ingress set has run on both targets.

   | Target (component) | Port(s) | Allowed from |
   |---|---|---|
   | `ycashd` | `rpc` | pods with label `ycash.org/rpc-client: "true"` in the release namespace; on kind with `regtest.enabled`, also `ipBlock` `networkPolicy.kindNodeCidr` (the NodePort, SNAT'd to the node IP; default `172.18.0.0/16`, the kind Docker network) |
   | `ycashd` | `p2p` | `ycashd` pods (in-cluster peering); plus `0.0.0.0/0` when `ycashd.p2p.listen` and `networkPolicy.p2pPublic` (default false: no public P2P Service exists today) |
   | `lightwalletd` | `grpc` 9067 | namespace `networkPolicy.gatewayNamespace` (default `envoy-gateway-system`) |
   | `lightwalletd` | `http` 9068 | namespace `networkPolicy.monitoringNamespace` (default `monitoring`) when `monitoring.serviceMonitor` |
   | `yindex` | `grpc` 9070 | gateway namespace |
   | `yindex`, `yindex-ingest` | `http` 9071 | monitoring namespace |
   | `postgres` | `pg` 5432 | `yindex`, `yindex-ingest` |
   | `redis` | 6379 | pods with `ycash.org/redis-client: "true"` (none today) |
   | `web` | `http` 8080 | gateway namespace |
   | `faucet` (kind) | its port | gateway namespace |

   - Add `ycash.org/rpc-client: "true"` to the pod templates of `lightwalletd`, `yindex`, `yindex-ingest` and the kind workloads that call RPC: the bootstrap Job and `miner` (`templates/kind/regtest.yaml`), `arm-yellowback` (`templates/kind/arm.yaml`) and `faucet` (`templates/kind/faucet.yaml`).
   - The readiness and liveness probes run `ycash-cli` inside the `ycashd` pod (`templates/ycashd/configmap.yaml:16-30`). They are loopback and unaffected.
   - Values: `networkPolicy: { enabled: true, gatewayNamespace: envoy-gateway-system, monitoringNamespace: monitoring, kindNodeCidr: "", p2pPublic: false }`. `values-kind.yaml` sets `kindNodeCidr: 172.18.0.0/16`; check it against `docker network inspect kind`.
2. **EKS CNI.**
   - `infra/eks/main.tf:51`: `vpc-cni = { configuration_values = jsonencode({ enableNetworkPolicy = "true" }) }`.
   - Check `var.addon_versions` / the cluster version: the VPC CNI's network-policy agent needs CNI ≥ 1.14 and EKS ≥ 1.25.
   - `docs/eks-runbook.md`: add the verification step from §5.
3. **RPC allow-list (second layer).** In `templates/ycashd/statefulset.yaml`, set `YCASHD_RPC_ALLOWIP` from a new value `ycashd.rpc.allowIp`, default `"127.0.0.1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"` (today's behaviour). Document narrowing it to the cluster's pod CIDR (`values-eks.yaml`: the VPC CIDR `10.40.0.0/16`, as `trustedProxyCidrs` already uses at `:25`). Do not change `rpcbind`: the Service needs the pod IP.
4. **Redis.**
   - `values.yaml:87` `redis.enabled: false`, and drop the `redis` block from `values-eks.yaml:31-33` (or set `enabled: false` there).
   - When enabled, require a password: `templates/yindex/redis.yaml` adds a Secret `<fn>-redis` (`password`: `lookup`-preserved `randAlphaNum 32`, or `redis.existingSecret`, which is required when `externalSecrets.enabled`). Pass it to the container via env `REDIS_PASSWORD` from the Secret and args `["--requirepass", "$(REDIS_PASSWORD)", …]`; Kubernetes expands `$(VAR)` in `args`.
   - Readiness probe: `["sh","-c","redis-cli -a \"$REDIS_PASSWORD\" --no-auth-warning ping"]`.
   - Update the plan's K3 row and README to say Redis is off until a consumer exists.
5. **Postgres (in-cluster).** Generate the password once and keep it:
   ```yaml
   {{- $sec := lookup "v1" "Secret" .Release.Namespace (printf "%s-yindex-postgres" $fn) }}
   {{- $pw := ternary (index ($sec.data | default dict) "password" | default "" | b64dec) (randAlphaNum 32) (not (empty $sec)) }}
   ```
   - Emit a Secret `<fn>-yindex-postgres` with `password` and `url` (`postgres://yindex:<pw>@<fn>-postgres:5432/yindex?sslmode=disable`).
   - Point `POSTGRES_PASSWORD` (`:120`) and both `YINDEX_POSTGRES_URL` envs (`:33`, `:77`) at it with `secretKeyRef`, and delete the `$pgUrl` literal (`:3`).
   - `helm template` (CI) has no cluster, so `lookup` returns empty and a random password renders. That is fine for kubeconform.
   - **Existing kind clusters:** Postgres keeps the old password in its data directory, so a `helm upgrade` of an existing kind release must be followed by `make kind-reset-chain` (it already wipes the Postgres volume, `Makefile:103`), or by `ALTER USER yindex PASSWORD …` by hand. Say so in the PR and the README.
6. **Docs and CI.**
   - `docs/plans/ycash-infra-plan.md`: add a row "network policy" with the table above.
   - README security section.
   - `scripts/lint-images.sh` or a new `scripts/lint-chart.sh` in CI: `helm template … | yq` asserts every Deployment/StatefulSet/Job in the release is selected by at least one NetworkPolicy when `networkPolicy.enabled`, so a new component cannot ship unprotected.

## 5. Tests

- **CI (offline):** `helm lint` and `helm template | kubeconform -strict` for both `values-kind.yaml` and the EKS values (`.github/workflows/ci.yml:11-15, 27`), now including the NetworkPolicies. Run the new lint asserting coverage. Render with `redis.enabled=true` and without `existingSecret` under `externalSecrets.enabled`; this must fail (`required`).
- **kind (negative, required once, recorded in the PR):** `make kind-up`, then
  ```bash
  kubectl run np-probe --rm -i --restart=Never --image=busybox:1.36 -- \
    sh -c 'nc -zvw3 <rel>-ycashd 8832; nc -zvw3 <rel>-postgres 5432; nc -zvw3 <rel>-redis 6379'
  ```
  All three must time out (Redis: absent by default). The same `nc` from a pod labelled `ycash.org/rpc-client=true` connects to 8832. This is also the test that kindnetd enforces policies at all on the pinned kind. If it does not, set `networking.disableDefaultCNI: true` in `kind/kind.yaml` and install Calico in `scripts/kind-up.sh` (pinned version) before merging.
- **kind (positive):** `make kind-smoke` (GetLightdInfo, GetYellowbackInfo, GetVaultInfo, GetChainInfo, ListSets through the gateway), `make kind-parity` (yindex vs lightwalletd: proves yindex → Postgres and → RPC still work), `make kind-personas-up` (the host-run NodePort path) and, with monitoring on, the ServiceMonitor targets `UP`.
- **EKS (with credentials, `docs/eks-runbook.md`):** the same `np-probe` from a throwaway namespace, then `make eks-smoke`.

## 6. Acceptance criteria

- With default values, every chart workload is selected by an ingress NetworkPolicy; `ycashd:rpc` admits only labelled RPC clients (plus the kind node CIDR in regtest); Postgres admits only yindex; Redis is not deployed.
- No template contains a literal Postgres or Redis password; the in-cluster Postgres password is generated once and survives `helm upgrade`.
- `infra/eks/main.tf` enables network-policy enforcement in the VPC CNI.
- The kind negative probe fails to connect, and smoke/parity/personas pass, both recorded in the PR.
- The coverage lint is in CI.

## 7. Risks and side effects

- **Outage by omission.** A missed allow (a new Job that calls RPC, Prometheus in another namespace) shows up as timeouts. The coverage lint, the label convention and the kind smoke/parity runs are the guard, and egress is deliberately left for a second PR.
- **CNI enforcement varies.** If kindnetd on the pinned kind does not enforce, the kind policies are decorative until Calico is added (§5). EKS needs the addon flag, and an addon update can roll the node's CNI pods (brief pod-network interruption). Schedule it.
- **Existing kind Postgres volumes** keep the old password (§4.5).
- Turning Redis off removes nothing in use (§2). If K3's cache ever moves to Redis, its consumer gets the client label and the Secret.
- No change to the node image, lightwalletd, yindex code or any client.

## 8. Effort estimate and dependencies

- ~1.5 days: policies and labels, Postgres/Redis secrets, lint, kind verification (incl. the possible Calico switch); the EKS apply is part of the outstanding K2 run (credentials).
- Depends on nothing. Independent of `LOW-06-I-1-ycash-infra-kubectl-pin.md` (done).
