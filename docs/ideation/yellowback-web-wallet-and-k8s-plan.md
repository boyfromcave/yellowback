# Ideation: a scalable web wallet and a Kubernetes lightwalletd for Ycash Yellowback (YED)

**Status: ideation, not a plan.** Written 2026-10-08 on `ideation/web-wallet` from the owner's
question: can the client infrastructure in this workspace (YEW, `lightwalletd-dd`, the x402 light
client) scale to millions of users, and if not, is the answer a lighter web wallet plus a
Kubernetes `lightwalletd`? Everything below is a recommendation for the owner to accept, amend or
reject; nothing is scheduled.

## 0. The recommendation in one page

1. **Build the web wallet as a third shell on the existing Rust core, not as a new wallet.**
   `yew-core` plus `x402-ycash/light` already hold everything that is dangerous to get wrong
   (ZIP-243 signing bound to the branch ID, the YED payloads, the carrier and vault scripts, the
   broadcast gate, the Sapling builder). Compile that core to WebAssembly and give it a browser
   shell (`yew/web/`), exactly as `yew/app/` is its Flutter shell. One core, three shells. A second
   wallet codebase is the one thing the wallet plan's contract rule 4 ("a client bug here burns
   YED") says never to have.
2. **Keep it non-custodial.** Keys stay in the browser; the server never sees a seed or a
   signature it did not receive as a finished transaction. A custodial web wallet would scale
   trivially and would also make the operator a bank. That is a product decision the owner must
   take explicitly; this document assumes "no".
3. **Ship the web wallet in two steps, in the order YEW itself took:** first transparent YEC +
   YED + vault operations (no proving parameters, no proving, instant in WASM), then Sapling
   (proving in a Web Worker, 10–30 s per send in WASM today). Step one already covers every
   Yellowback operation, because YED and vaults are transparent (V8).
4. **The scaling problem is not `lightwalletd`'s gRPC front; it is the node behind it.** Compact
   blocks are served from a local cache and scale horizontally with zero changes (the Zcash
   ecosystem already runs this at scale). What does not scale is that every address lookup
   (`GetAddressUtxos`, `GetTaddressTxids`) and every Yellowback call is a proxied JSON-RPC to one
   `ycashd` behind `cs_main` and a handful of RPC threads, and YEW polls per address. Millions of
   transparent/YED users means millions of node RPCs per sync tick. So the Kubernetes work is
   **a) replicas of `lightwalletd-dd` and a small pool of nodes, which is cheap and solves the
   first order of magnitude, and b) an address + YED index with a cache, which is the real
   unlock.** Measure the node's RPC ceiling on the devnet before building (b); the number
   decides its shape (§3.3).
5. **Yes to Kubernetes, as one Helm chart with two value sets, `kind` and `eks`.** The local
   cluster runs a regtest `ycashd` and a miner in-cluster; AWS swaps only storage class, load
   balancer, DNS and secrets. (Note: AKS is Azure's managed Kubernetes; AWS's is **EKS**. The
   design is the same for either, since nothing below is cloud-specific.)
6. **New repo for the deployment (`ycash-infra`, name open), not files in `lightwalletd-dd`.** The
   chart spans node, `lightwalletd`, gateway, index and the web wallet's static bundle; a fork that
   must stay a small delta on `yodl/lightwalletd` is the wrong home. `lightwalletd-dd` keeps its
   Dockerfile and gains nothing but, later, the index (§3.3).

What is rejected and why: a browser-native gRPC client (browsers cannot speak gRPC; the gateway
transcodes gRPC-web, so `lightwalletd-dd` does not change); a rewrite of `lightwalletd` (minimal
change, the yodl lineage, the four-service contract already in the proto); a custodial wallet
(above); relying on a third-party explorer for address data (a trust surface the trust statement
would have to disclose).

## 1. What exists, and where it stops scaling

| Piece | What it is today | Scales to millions? |
|---|---|---|
| `lightwalletd-dd` `CompactTxStreamer` | yodl/lightwalletd 0.4.6; compact blocks ingested from one `ycashd` into a file cache (`common/cache.go`), served by gRPC; Prometheus metrics on the gRPC handlers (`cmd/root.go`) | **Yes, by replication.** Each replica is stateless beyond its cache; the whole Ycash chain is ≈106 MB of compact data (872k outputs ever, 154/day; `yew-shielded-plan.md` §5). |
| `lightwalletd-dd` address RPCs | `GetAddressUtxos`, `GetTaddressTxids`, `GetTaddressBalance` → node `-insightexplorer -txindex` JSON-RPC | **No.** Each call is a node RPC; the node is one process behind `cs_main`, `-rpcthreads` 4, `-rpcworkqueue` 16. |
| `YellowbackStreamer` | 24 methods, each a thin allow-listed proxy of a read-only `yed_*` / `vault_*` / `set_*` RPC (plan D-L-2: proxy, not indexer) | **No, for the same reason**, but most results are immutable or tip-keyed and therefore cacheable (§3.3). |
| YEW sync model | per address: UTXOs, txids, tokens, then `GetTxInfo` per Yellowback tx; `GetLatestBlock` on a timer (wallet plan §3.2) | Client side it is tiny; server side it is O(users × addresses × ticks) node RPCs. |
| YEW Sapling (S1–S4, done) | `x402_ycash_light` library: compact-block scan, `zcash_client_sqlite`, `LocalTxProver`, params downloaded on first send | Client-side trial decryption: **scales by construction**; the server only streams blocks. |
| Node images | `ycash6/contrib/docker/Dockerfile` + `release-docker-hub.yml`; 6.22.x for `upgrade/vault` | Exists; no Kubernetes manifests anywhere (`lightwalletd-dd/kubernetes/` is a Tekton CI pipeline, not a deployment). |
| Public endpoint | `lite.ycash.xyz`, one host, owner-run | Single point of failure and the item S0-4 is waiting on. |

Conclusion: the shielded path is already the scalable one; the transparent/YED path is where a
web wallet with millions of users would fall over, and it falls over at the node, not at Go.

## 2. The web wallet

### 2.1 Shape

- **`yew/web/`**: a shell beside `yew/app/`. The core is compiled to `wasm32-unknown-unknown`
  with `wasm-bindgen`; the shell is a small TypeScript PWA (framework choice open; the screens
  are the six of the wallet plan §5, nothing more). The Dart bridge (`api.rs` over
  `flutter_rust_bridge`) becomes a second thin binding, `api_wasm.rs`, over the same internal
  functions; no logic moves.
- **Transport:** `tonic-web-wasm-client` (gRPC-web over `fetch`) replaces the native tonic channel
  behind the same trait the light library already takes as an injected channel (S1/Z-3 made the
  channel injectable). The gateway in §3 transcodes gRPC-web to gRPC; `lightwalletd-dd` is
  untouched.
- **Storage:** the core's rusqlite store and `zcash_client_sqlite`'s `FsBlockDb` do not compile
  to the browser. Two options: (a) `wa-sqlite`/sqlite-wasm over OPFS behind rusqlite's bundled
  feature, which is the smaller code change but a build-system fight, or (b) a storage trait with
  an IndexedDB implementation, which is what ChainSafe's WebZjs did for Zcash
  (`zcash_client_memory` + persisted snapshot). **Recommend (b) for the transparent step**, since
  YEW's own store is "a cache" by design (`store.rs`), and defer the Sapling store question to
  step two, where WebZjs is the reference to translate from (D-W-10 discipline: translate, do not
  reinvent).
- **Proving (step two only):** Sapling Groth16 in WASM runs in a Web Worker with the 52 MB
  parameters fetched once into the Cache API (same SHA-256 pins as YEW, same source order as
  S0-2). Expect 10–30 s per send; the slide-to-confirm plus progress sheet from YEW carries over.
  Receiving and scanning are fast enough (trial decryption of a day's 154 outputs is
  milliseconds).

### 2.2 Security, honestly

A web wallet is less secure than a native app with a platform keystore, and the trust statement
(`yew/docs/trust.md`) must say so. What makes it defensible:

- **Seed at rest:** encrypted under a key derived with WebAuthn **PRF** (passkey-bound; falls
  back to a passphrase + Argon2id where PRF is unavailable), stored in IndexedDB. The seed is
  never in `localStorage`, never in a cookie, never sent.
- **Code integrity:** strict CSP (no inline, no eval, `connect-src` pinned to the gateway),
  Subresource Integrity on every asset, a reproducible build whose bundle hash is published in
  the release notes (the same discipline as the node's reproducible release matrix).
- **Hosting:** the bundle is static files; serve it from the same chart (§3) or any CDN; the
  gateway's origin is the only network destination.
- **Broadcast gate:** `gate.rs` runs in WASM unchanged, so the invariants that protect YED
  (every `confirm` passes the gate, YED-bearing outputs are never fee inputs, D-W-12) hold in the
  browser exactly as on the phone.
- **Not solved by any web wallet:** a compromised browser extension or a malicious page on the
  same origin. State it; do not pretend otherwise.

### 2.3 Why not a separate, lighter wallet

The owner's word "lighter" is right about the UI and about sync, and both are already light in
YEW: no compact-block scan for YEC/YED, six screens. The weight is in the core, and that weight is
the part that must not be duplicated. "Lighter" therefore means: a web shell, step one without
Sapling, and the server-side index of §3.3 so that a browser session's sync is one round trip.

## 3. The server side on Kubernetes

### 3.1 Topology

```
                      ┌────────────────── namespace: ycash ──────────────────┐
  browser / YEW ──TLS─► Envoy Gateway (Gateway API)                             │
                      │  gRPC-web ⇄ gRPC, rate limits, per-IP quotas,          │
                      │  static web bundle (step one: same host)               │
                      │          │                                             │
                      │          ▼                                             │
                      │  lightwalletd-dd Deployment (HPA, N replicas)          │
                      │   each: own compact-block cache on an ephemeral        │
                      │   volume; --yellowback; Prometheus scraped             │
                      │          │  JSON-RPC (ClusterIP, round-robin)          │
                      │          ▼                                             │
                      │  ycashd StatefulSet (2–3 replicas, gp3 PVC,            │
                      │   -insightexplorer -txindex -experimentalfeatures,     │
                      │   -rpcthreads raised; 6.22.x image)                    │
                      │          ▲                                             │
                      │  [kind only] miner Job (generate loop / yolo),         │
                      │             yellowback-sim persona Job (load)          │
                      │                                                       │
                      │  [later] yindex: address + YED index, Postgres,        │
                      │          Redis verdict cache (§3.3)                    │
                      └───────────────────────────────────────────────────────┘
```

- **Node pool, not node redundancy.** Several `ycashd` replicas exist for RPC capacity and
  rolling restarts, each a full node with its own chain state; nothing is shared between them.
  `lightwalletd` replicas ingest from whichever answers. The vault upgrade's attestor set and
  activation height come from the release image, never from the chart.
- **`lightwalletd-dd` replicas each keep their own cache** (ephemeral `emptyDir` or a small PVC;
  a cold start re-syncs ≈106 MB from the node in minutes). No shared RWX volume: the cache's
  corruption recovery (`cache.go` `recoverFromCorruption`) assumes a single writer.
- **The gateway is the one place gRPC-web lives.** Envoy Gateway implements the Kubernetes
  Gateway API and runs identically on kind and EKS; it also carries TLS (cert-manager), HTTP/2,
  rate limiting and the web bundle's static route. No change to Go.
- **Observability:** the handlers already export Prometheus histograms; add `kube-prometheus-stack`
  with one dashboard: RPC latency per method, node RPC queue depth (the saturation signal),
  cache tip lag.

### 3.2 What the chart contains

`ycash-infra/charts/ycash-lightwallet/` with `values-kind.yaml` and `values-eks.yaml`:

| Component | kind | EKS |
|---|---|---|
| `ycashd` | regtest, `-nuparams=6d5b7a31:<h>`, 1 replica, `local-path` PVC, image built locally from `ycash6/contrib/docker/Dockerfile` (`kind load`) | mainnet/testnet, 2–3 replicas, gp3, Docker Hub image from `release-docker-hub.yml` |
| miner / sim | `generate` loop Job + `yellowback-sim` persona Job (the devnet's roles, `contrib/yellowback/devnet`) | absent |
| `lightwalletd-dd` | 2 replicas (to prove statelessness), `--yellowback`, self-signed TLS | HPA 3–50 on CPU + request rate, TLS via cert-manager |
| gateway | Envoy Gateway, `extraPortMappings` 443→host | Envoy Gateway behind an NLB, Route53 record, ACM or Let's Encrypt |
| secrets | plain Kubernetes Secret for `rpcuser/rpcpassword` | External Secrets Operator → AWS Secrets Manager, IRSA |
| web bundle | same gateway, `/` | same, or CloudFront in front |
| metrics | kube-prometheus-stack, optional | required |

Promotion is `helm upgrade --install -f values-eks.yaml`; the kind values are the CI target
(`kind create cluster --config kind.yaml && make kind-up && make kind-test`, where the test is
YEW's existing devnet suites pointed at `https://localhost`). Terraform (or `eksctl`) for the
cluster itself lives in the same repo under `infra/eks/` and is deliberately boring: one managed
node group, Karpenter optional later.

### 3.3 The index, and why it is "later"

The transparent/YED path's ceiling is the node. Before designing around it, **measure it**: run
the kind chart, point `ghz`/`k6` at `GetAddressUtxos` + `GetAddressTokens` + `GetTxInfo` with the
persona Job generating traffic, and find the requests/second at which node RPC queue depth
saturates. Then:

- **If a node pool of 3–5 covers the next two years** (likely for tens of thousands of users):
  do nothing more; add a **Redis cache in `lightwalletd-dd`** keyed by `(method, args, tip hash)`
  for the `YellowbackStreamer` reads whose results are tip-pure (verdicts of confirmed
  transactions, price at a height, sets, vault rows by txid). This is a small, reviewable change
  inside the existing `CallYed` path and keeps D-L-2 (the node is still the only source of a
  verdict; the cache only remembers it).
- **If millions are the target:** build `yindex`, a separate deployment that consumes blocks
  (from `lightwalletd`'s own cache, or the node's `blocknotify`, the way chain-viz does) and
  keeps `address → utxos/txids` in Postgres, so `GetAddressUtxos`/`GetTaddressTxids` never reach
  the node. **The YED token set stays the node's** (`yed_listtokens` is rule-module output;
  computing it elsewhere duplicates consensus logic, which contract rule 3 forbids), but it is
  cached by `(address, tip hash)` and invalidated per block, which turns per-user polling into
  per-block work. This is the one place a small node change could help: a `yed_listtokens` that
  also returns the tip hash it answered at, so the cache key is exact. Record that as a node ask,
  not a dependency (the x402 plan's §4.4 pattern).

Either way the browser does one round trip per sync tick instead of four, which is what makes
the web wallet feel "light".

### 3.4 What does not change

No consensus change on either node line. No new RPC surface: the web wallet uses the same four
services as YEW (`CompactTxStreamer`, `YellowbackStreamer`, and nothing else), so the interface
rule in `AGENTS.md` holds. `lightwalletd-dd` stays a small delta on yodl; the index, when it
comes, is a separate program that reads what `lightwalletd` already stores.

## 4. Risks and open decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| I-1 | Custodial or non-custodial web wallet | non-custodial (§0.2) |
| I-2 | Web shell inside `yew/` or a new repo | inside `yew/` as `web/`; one core, one CI |
| I-3 | Step one transparent-only on the web, Sapling second | yes; mirrors YEW's own W-then-S history |
| I-4 | Browser storage: IndexedDB trait vs sqlite-wasm | IndexedDB trait for step one; decide Sapling store with WebZjs as the reference |
| I-5 | Deployment repo name and home | new repo `ycash-infra` (name open), `upgrade/vault` default like the other clients |
| I-6 | Gateway: Envoy Gateway vs nginx ingress vs Istio | Envoy Gateway (Gateway API, gRPC-web native, same on kind and EKS) |
| I-7 | Index now or after measurement | after measurement; the cache first (§3.3) |
| I-8 | Where `lite.ycash.xyz` goes | onto this chart once the kind suite is green; S0-4 closes with it |

Risks: WASM proving time on low-end laptops (mitigated by step one needing none); browser
storage eviction (IndexedDB is a cache, the seed backup is the user's); the gRPC-web streaming
methods (`GetBlockRange`, `ListVaults`) need server-streaming over gRPC-web, which Envoy supports
and `tonic-web-wasm-client` supports, but which must be tested through the gateway early; EKS cost
of several full nodes with `-txindex` (each ≈ the Ycash chain plus the index, small today).

## 5. If adopted: the first four chunks

| Chunk | Where | Size | Acceptance |
|---|---|---|---|
| K0 chart on kind | `ycash-infra` | M (1 wk) | `make kind-up` brings regtest `ycashd` + miner + 2× `lightwalletd-dd` + Envoy Gateway; YEW's devnet suites pass against the gateway over TLS and gRPC-web |
| K1 load measurement | `ycash-infra` | S (3 d) | a number: node RPC ceiling per method, written into this document's §3.3 |
| W0 WASM build of the core | `yew/core` | M (1–2 wk) | `yew-core` compiles to wasm32 with the transparent + YED path; vectors green in Node; storage trait with IndexedDB impl |
| W1 web shell, step one | `yew/web` | L (2–3 wk) | the six screens; mint/send/redeem/claim on kind through the gateway; CSP + SRI + passkey seed encryption; trust statement |

K2 (EKS values + Terraform), K3 (cache/index per K1's number) and W2 (Sapling in WASM) follow.
