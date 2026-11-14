# Explorer plan: a block explorer for the vault network upgrade

**Revision 1 (2026-11-14). Proposal. Nothing here is implemented.**
Decisions EX-1..EX-10 (§9) are the Yellowback lead architect's; each has a recommendation.

## 1. Goals

1. **An explorer that works with 6.22.0-beta2 nodes.** Today no public explorer runs against the
   6.22 line. Inzyght (`ref/inzyght`) was built against a patched v4.5.0 node; every RPC and field
   it reads is present in 6.22.0-beta2, but nobody has run the pair yet.
2. **Visibility of the vault upgrade and the post-quantum features.** Vaults, signer sets,
   post-quantum addresses (`sqf…` FN-DSA-512, `sqs…` SLH-DSA-SHA2-128s) and their large signatures,
   the upgrade's activation, and Ycash Yellowback (YED) once its module is active.
3. **Automated deployment**, like the seed nodes: Terraform, a deploy workflow, restore from a
   published bundle, no hand-built host.
4. **`fastnet-explorer.ycash.team` first**, on the public fast testnet (yb-fast, where the vault
   upgrade has been active since block 510,400), as the worked example for a mainnet explorer.
5. **Find what the node is missing.** Anything that does not work with Inzyght and beta2 becomes a
   candidate for beta3 (§8 lists what the surveys already found).

Not goals: a wallet, any write to the chain, a consensus or node change made for the explorer's
convenience (the explorer is a client: stock RPCs and the read-only `vault_*`, `set_*`, `yed_*`
calls are its whole interface, AGENTS.md rule 2).

## 2. What exists today (the facts the plan rests on)

**Inzyght** (`ref/inzyght`, `miodragpop/inzyght` @ `17f505f273`, version 1.0.9; mapping §25):

- One C++23 binary (Drogon, glaze, curl, libzmq) and a PostgreSQL index; static frontend.
- Talks to the node over JSON-RPC (including the insight address RPCs) and ZMQ `hashblock` /
  `hashtx`, with a polling fallback.
- Needs the node started with `-experimentalfeatures -insightexplorer -txindex` and ZMQ.
- Has no Dockerfile, no service unit, and **no licence file**.
- Sends peer IP addresses to `http://ip-api.com` for a map, and loads its frontend libraries from
  jsdelivr.
- Knows nothing of the vault upgrade: its address search rejects `sqf…` / `sqs…` and YED
  addresses, vault and post-quantum outputs show as bare types, value pools are read by position.

**The node** (`ycash6`, 6.22.0-beta2): see [`node-choice.md`](node-choice.md). In short, it serves
everything Inzyght reads and everything a vault view needs, with one defect (the sender address of
a post-quantum spend is blank) and no history calls for vaults and sets.

**Deployment** (`ycash-infra`, `ycash-ops`):

- The seeds and the pool host are **EC2 hosts running Docker Compose**, not Kubernetes: ycash-infra's
  `infra/testnet-seeds/{ips,nodes}` module, called from roots in `ycash-ops`, state in S3,
  `deploy.yml` → `scripts/seeds.sh` → `seedctl` on the host over SSM.
- "Restore from a snapshot" on those hosts is the **block prefix bundle** (`testnet-prefix-v1`,
  blocks 0..510,247, fetched from S3, checked against a pinned hash, imported with `-loadblock`).
- The closest template is the **pool host** (`ycash-ops/testnet-pools/`): one network, one node, one
  service container beside it (yolo), its own Elastic IP, state, deploy role and GitHub environment.
- Images are public on `ghcr.io`, built by `workflow_dispatch` workflows in ycash-infra
  (`yolo-image.yml` is the pattern for "another repo's source, our Dockerfile"), pinned by digest
  with build provenance.
- The Kubernetes layer (charts, RDS, TLS gateway, external-dns) is written but has never been
  deployed; the testnet snapshotter has never run; no testnet state bundle exists.
- **Missing for an explorer:** the seed tooling hard-codes the explorer indexes off
  (`files/seedctl:110`) and has no ZMQ setting; no slot for Inzyght and PostgreSQL; no HTTPS on any
  EC2 host; DNS names for hosts are made by hand; the deploy workflow, the root allow-list
  (`scripts/seeds.sh:20`), `scripts/validate.sh` and the role policy helper (`layer_policy`, two
  layers only) do not know an explorer layer.

**The chain is small.** A fast-testnet datadir with both indexes is 2.8 GB (insight index 370 MB).

**Mainnet is half ready.** A signed `full-insight` ycashd bundle at height 3,100,949 is published
under `snapshots/main-insight/` (41.8 GB; ycash-infra #44).

## 3. Design

### 3.1 Backend node (EX-1)

ycashd 6.22.0-beta2, with the explorer written to be node-agnostic and koganyd added later.
Reasons and evidence: [`node-choice.md`](node-choice.md).

### 3.2 Where the code lives (EX-2, EX-3)

Three kinds of code, three homes:

| Code | Home | Why |
|---|---|---|
| The explorer itself (Inzyght plus the vault and post-quantum views) | **a new component repo `inzyght/`**: the Ycash developers' fork of `miodragpop/inzyght`, branch `upgrade/vault`, baseline `inzyght-legacy` = `17f505f273`, a row in `repos.yaml` | The same shape as every other fork here: `ref/inzyght` stays the read-only pin, `make diff` shows our delta, upstream syncs stay possible. **Conditional on a licence** (below) |
| The image, the Compose stack, the host module changes | `ycash-infra/` (`images/inzyght/Dockerfile`, `explorer-image.yml`, the seeds module) | Where every other image and host recipe is; builds from the explorer repo at a pinned commit, copies no source |
| The Terraform root and the deploy wiring | `ycash-ops/` (`testnet-explorer/{ips,nodes}`, `deploy.yml`) | Where every deployed layer is |

It does not belong in `chain-viz` (a realtime visualizer with no stored index; different language,
different job), in `ycash-infra` (that repo deploys, it does not hold application source), or in a
node repo.

**The licence comes first.** Inzyght has no licence file, so today we may read and run it, and may
not publish a modified copy. Three routes:

- **A (recommended).** Ask the author to add a licence (MIT, like the node) and say whether he
  wants our changes as pull requests to his repository, in a Ycash developers' fork, or both. Then
  fork as in the table.
- **B.** If he prefers to keep it upstream-only: our changes go to him as pull requests; we deploy
  his repository at a pinned commit and hold no fork.
- **C (fallback, needs no agreement).** Deploy Inzyght unmodified, built from his repository at the
  pin, and put the vault and post-quantum views in a small service of our own beside it (its own
  pages under `/vault/…`, linked from the same host). More moving parts and two user interfaces;
  the address search gap in Inzyght itself stays.

Phases E1–E4 do not need the answer: they build and run Inzyght unmodified. E5 does.

### 3.3 Deployment (EX-4, EX-5, EX-8)

One EC2 host in the pool-host pattern, four containers under Compose, all rendered by `seedctl`:

```
            fastnet-explorer.ycash.team  (A record → Elastic IP)
                       │ 443 (80 only for the certificate and the redirect)
                 ┌─────▼──────┐
                 │   proxy    │  TLS (Let's Encrypt), security headers, rate limit
                 └─────┬──────┘
                       │ 127.0.0.1:8080  (HTTP and WebSocket)
                 ┌─────▼──────┐   127.0.0.1:5432   ┌────────────┐
                 │  inzyght   ├───────────────────►│ PostgreSQL │ volume on the data disk
                 └─────┬──────┘                    └────────────┘
     RPC 127.0.0.1:18832 │ ZMQ 127.0.0.1:<port>
                 ┌─────▼──────┐  P2P 18833 out to fastnet-seed.ycash.team
                 │  ycashd    │  -txindex -insightexplorer, ZMQ, -listen=0
                 └────────────┘
```

- **Host:** the seeds module as it is (VPC, Elastic IP, encrypted data volume, SSM only, no SSH).
  Start with `t3a.medium`, 60 GiB data; measure in E4.
- **Node:** the same pinned beta2 image as the seeds. New per-network options in the module,
  `insight` and `zmq`, replace the hard-coded `YCASHD_INSIGHT=0`. RPC and ZMQ stay on localhost.
- **Restore:** the existing prefix bundle. A node started with the index flags before its first
  import builds both indexes as it imports (expected; to confirm in E1). No state snapshot is
  needed on a 2.8 GB chain.
- **PostgreSQL:** a container on the host for the testnet (EX-8). The index is rebuilt from the
  node, so the database holds nothing that cannot be recreated; no backup is required for launch.
- **TLS (EX-5):** a small reverse proxy container that obtains and renews a Let's Encrypt
  certificate by itself. The alternative, CloudFront in front as on the Kogany site, adds a second
  hop and an origin that must still be protected; it is the better choice for mainnet if traffic
  or abuse warrants it.
- **DNS:** one A record. Either by hand as for the pool host, or a small hand-applied Terraform root
  as for the Kogany site; the deploy role gets no Route 53 rights.
- **Privacy and outside calls (EX-7):** the peer-location lookup to `ip-api.com` is off (it sends
  our peers' addresses to a third party over plain HTTP), and the frontend libraries are served
  from the host. Both need a switch in Inzyght if one does not exist; until E5 the proxy can block
  the first and a content security policy the second.
- **Ops repo wiring:** a new layer `explorer` in `deploy.yml`, environment `testnet-explorer`, role
  `testnet-explorer-deploy` trusted by the immutable OIDC subject, `layer_policy` extended to three
  layers (which re-puts the two existing role policies), the root added to `seeds.sh` and
  `validate.sh`. No account identifier enters the repository.

### 3.4 The vault and post-quantum views (phase E5)

All from read-only RPCs; no node change.

| View | Source | Notes |
|---|---|---|
| Address search and pages for `sqf…` / `sqs…` (and `tqf…`, `rqf…` forms) | `getaddress*`: already answers for post-quantum addresses | Show the scheme (FN-DSA-512 or SLH-DSA-SHA2-128s) from the prefix |
| YED addresses (`yb…`, `ybf…`, `ybs…`) | `yed_validateaddress`, `yed_listtokens` | Only once the module is active |
| Output types `vault`, `vaultintent`, `pqpubkeyhash`, `pqchannel` | `getrawtransaction`, `vault_decodescript` | Decode tag, signer set, delay, owner and owner scheme on the transaction page |
| Signature scheme and size on an input | the scriptSig | A 666-byte FN-DSA or roughly 7.9 KB SLH-DSA signature is worth showing |
| Vaults: list, one vault, total locked | `vault_list`, `vault_getinfo` | Current state |
| Signer sets: list, seats, bond, status | `set_list`, `set_getinfo` | Current state |
| Vault and set history (opened, spent, cancelled, set changes) | decoded from blocks into new PostgreSQL tables as the indexer passes | The node keeps no history; this is the explorer's own index |
| Upgrade status | `getblockchaininfo` `upgrades` (branch ID `0x6d5b7a31`), `rpcversion` | Activation height, active or not |
| Supply | value pools by `id` | "Locked in vaults" as its own series |
| Yellowback: price, supply, collateral, vaults, attestations | read-only `yed_*` | Pages hidden while `yed_getinfo` answers "Method not found" |

Naming on every page follows AGENTS.md rule 6: Yellowback is the system, YED the unit.

### 3.5 Mainnet (phase E7)

The same host module with `network = main`, a larger disk (about 53 GB of node data plus the
PostgreSQL index), and restore from the published `main-insight/latest` bundle through the node
image's `ycash-bootstrap`. Two things are new there: a signed PostgreSQL dump as its own bundle, so
a new host does not re-index 3.1 million blocks, and a decision on the name and on whether this
explorer runs beside or replaces any existing public one (EX-9).

## 4. Phases

Each phase ends with something that can be checked. Sizes are agent-days of work, not calendar time.

| Phase | Work | Done when | Size | Needs the lead architect |
|---|---|---|---|---|
| **E0** | Decisions EX-1..EX-8; write to the author about the licence (EX-2) | Decisions recorded here | — | Yes |
| **E1** | **Local proof.** Build Inzyght unmodified in a Linux container. Run it with PostgreSQL against (a) a fresh local yb-fast beta2 node started with the index flags and ZMQ, imported from the prefix bundle, (b) the local mainnet explorer node, read-only. Record every page and API route: works, wrong, or broken | A compatibility report in this folder; defects sorted into "explorer" and "node (beta3 candidate)"; the import-with-flags question answered | 2 | No |
| **E2** | **Packaging.** `images/inzyght/Dockerfile` and `explorer-image.yml` in ycash-infra; a local Compose stack (`make explorer-up`) of node, PostgreSQL, Inzyght and proxy; schema applied on first start; smoke test in CI | The stack comes up from nothing on a laptop and serves the tip | 2 | No |
| **E3** | **Host module and ops layer.** ycash-infra: `insight` and `zmq` options, an `explorer` block in `seedctl` (as `render_pool`), ports 80/443. ycash-ops: `testnet-explorer/` roots, the `explorer` layer in `deploy.yml`, validation, the three-layer role policy, the runbook | `check.yml` green; `plan` output reviewed | 3 | Review |
| **E4** | **Launch `fastnet-explorer.ycash.team`.** The lead architect creates the role, the environment and its secrets, and the DNS record (a CloudShell runbook, as for the Kogany site); then `deploy explorer yb-fast apply` | HTTPS answers; the tip matches the seeds within two blocks; a known post-quantum address and a known vault transaction display; index time, disk and memory recorded | 1 | Yes: AWS steps |
| **E5** | **Vault and post-quantum views** (§3.4), in the route EX-2 chose. Tests on regtest with `-nuparams=6d5b7a31:<h>` and against yb-fast | Every row of §3.4 shown on the fast testnet, except the YED rows (module inactive there), which are tested on the devnet | 6–9 | Licence answer |
| **E6** | **Node items into beta3.** Take the findings of E1 and E5 to `wt/beta3-list.md`; the lead architect picks; each lands on both C++ lines together | The chosen items are in a beta3 build and the explorer uses them | per item | Picks |
| **E7** | **Mainnet explorer** (§3.5): PostgreSQL dump bundle, host, restore from `main-insight` | A mainnet explorer restored from published bundles alone, in a measured time | 4 | Yes: name, AWS |
| **E8** | **koganyd as a second backend:** run the same explorer against kogany in polling mode; list what differs; parity items (node-choice §4) through the kogany plan | The explorer's own test suite passes against both nodes, differences documented | 3 + node work | After K-19 |

E1 and E2 can start now and run in parallel; E3 can start as soon as E2's Compose file settles.
Nothing before E4 touches AWS.

## 5. Checks before anything public

- The independent review before each merge, as for every repository here.
- The explorer is internet-facing C++ parsing user input: a security review of the request paths,
  the rate limiter and the proxy configuration before E4, and the container runs as a non-root
  user, read-only, with no access to instance metadata (as the pool container does).
- The node's RPC credentials reach only the explorer container; the explorer's RPC user is limited
  to read calls if the node offers a way, otherwise the RPC port stays on localhost.
- No secrets, account identifiers, zone IDs or e-mail addresses in any repository.

## 6. Cost (estimates, to be replaced by E4's measurements)

One `t3a.medium` host with 60 GiB of storage and an Elastic IP is on the order of a few tens of
US dollars a month for the testnet. The mainnet host needs more disk and memory; size it from E7.

## 7. Risks

| Risk | Handling |
|---|---|
| No licence answer, or a refusal | Route C (§3.2): unmodified Inzyght plus our own vault service |
| Inzyght does not run cleanly on beta2 | E1 finds out before any infrastructure is built |
| The index from genesis is slow on a small host | Measure in E1/E4; burst CPU credits during the first index as the pool host does; a PostgreSQL dump bundle if needed |
| A public explorer becomes a target | Proxy rate limits, no write paths, isolated host with nothing else on it, review before launch |
| The testnet is reset | The host rebuilds from the prefix bundle; the PostgreSQL index is disposable |
| Two user interfaces drift (route C) | Prefer A or B |

## 8. Candidate beta3 node items found so far

Not decisions; the list the lead architect picks from in E6. Details in
[`node-choice.md`](node-choice.md) §2 and §4.

- **ycashd (and ycash-dd with it):** the blank sender address on a post-quantum spend (Y-1);
  optional vault and set history reads (Y-2, Y-3) only if explorer-side decoding proves too slow;
  the value-pool split must keep today's order (Y-4).
- **kogany:** the seven parity items of node-choice §4.
- **Tooling:** the testnet snapshotter publishes both flavours under one `latest`; give
  `full-insight` its own path as mainnet has.

## 9. Decisions for the Yellowback lead architect

| # | Decision | Recommendation |
|---|---|---|
| EX-1 | Backend node | ycashd 6.22.0-beta2 now, node-agnostic code, koganyd second ([`node-choice.md`](node-choice.md)) |
| EX-2 | Licence route for Inzyght | A: ask the author for a licence and his preference; C as the fallback |
| EX-3 | Home of the explorer code | A new component repo `inzyght/`, a fork on `upgrade/vault` with `inzyght-legacy` as baseline (under route A) |
| EX-4 | Deployment pattern | An EC2 host like the pool host, not the undeployed Kubernetes layer |
| EX-5 | TLS | A self-renewing reverse proxy on the host for the testnet; CloudFront considered for mainnet |
| EX-6 | Testnet plan T-13 ("a full explorer is a separate proposal") | Replace it with this plan |
| EX-7 | Outside calls | Peer-location lookup off; frontend libraries served from the host |
| EX-8 | PostgreSQL | A container on the host for the testnet; revisit for mainnet |
| EX-9 | Mainnet name and timing | Decide after E4; E7 does not start before it |
| EX-10 | Start E1 and E2 now | Yes: both are local, need no AWS and no licence answer |
