# x402 demonstrations: live, agent-made payments on Ycash

Status: design note, revision 1 (2026-11-16). Read-only survey: nothing here has changed any
repository yet. It answers the Yellowback lead architect's question: ycash.team lists x402-ycash
as available, the repository is complete, but how can anyone use it, and what should a first live
demonstration be? It builds on the x402 plan
([`x402-agent-payments-plan.md`](x402-agent-payments-plan.md), §7 X5 "x402-gated services around
the node" and X6 "mainnet", both still open) and on the hosts the beta3 run deployed.

## 0. Conclusion first

**x402-ycash works end to end today, but only on a laptop.** Every role (paying agent, merchant
server, facilitator) is built and tested on both node lines, for transparent YEC, YEC payment
channels, shielded YEC and YED. What does not exist is any running instance a stranger can reach,
a resource worth paying for, a way to install the client without building it, or a way to get the
first coins. So the honest answer to "how do I use this" is: clone the repository and run a
five-node devnet.

**Recommendation: the first demonstration is a small paid chain-data API for agents on the fast
testnet, `fastnet-x402.ycash.team`, on its own small host in the pool-host pattern, with a
faucet on the same page, a reference agent that pays from a key and the public light-wallet
server (no node of its own), and a recorded end-to-end run.** About 8–10 agent-days and about
$21 a month. A local MCP tool that pays for the same API is the next step (+2–3 days). The
second step is the same API on mainnet, after the lead architect has run the X6 runbook.
**The snapshot downloads stay free** (§3.1).

### Decisions for the Yellowback lead architect

Recommended option first (A) in each.

| # | Decision | Options |
|---|---|---|
| D-1 | The first demonstration | **A. A paid chain-data API for agents on the fast testnet, with a reference agent and a recorded run (§3.2)**; B. a paid mirror of the snapshot downloads (§3.1); C. an MCP tool first (§3.3) |
| D-2 | Where it runs | **A. Its own small host: an `x402` block in ycash-infra's seeds module beside `pool`, `explorer` and `lightwallet` (t3a.small, ≈ $21/month)**; B. co-hosted on the lightwallet host (saves about 1.5 days, couples the demo to item 17's acceptance and a host already near 4 GiB); C. the Kubernetes testnet chart (not deployed) |
| D-3 | The agent's chain access | **A. A key plus `--lwd fastnet-lightwallet.ycash.team` (no node; the CLI supports it today)**; B. the agent's own node or yewd |
| D-4 | How a visitor gets testnet YEC | **A. The faucet (`images/faucet`, testnet mode: fixed amount, per-IP and per-address limits, proof of work) on the same host, and the API's `payTo` is the faucet's own wallet, so spent coins flow back to the faucet**; B. coins on request from the team; C. wait for the chart's faucet (decision T-9) |
| D-5 | How the client is distributed | **A. Container images, by digest, of the CLI, the facilitator and the API from x402-ycash's CI (the ycash-infra image pattern), plus clone-and-build**; B. publish the packages to npm (an outward-facing account and licence decision, as the upstream PRs in X5); C. clone and build only |
| D-6 | The fast testnet's x402 network id | **A. Keep `ycash:testnet`; the facilitator and the API refuse to start unless the node reports `testnetprofile` = `fast` (the faucet's check)**; B. a new id `ycash:testnet-fast` (touches specs, vectors and both SDKs) |
| D-7 | The snapshot downloads | **A. Stay free; no paywall now; revisit a paid "pay what it costs" mirror only after the mainnet API has users**; B. a paid mirror beside the free link; C. replace the free link with a paid one |
| D-8 | MCP | **A. Second step on the fast testnet: a local MCP server that pays the API from a capped budget (§3.3)**; B. in the first step; C. not at all |
| D-9 | Mainnet | **A. After the lead architect runs the X6 runbook, the same API on mainnet at `x402.ycash.team` with tiny YEC prices, transparent and shielded; YED once the vault upgrade is active there**; B. the snapshot mirror as the mainnet service; C. no mainnet service |
| D-10 | Prices on the fast testnet | **A. 0.0001 testnet YEC per request (exact), 0.00001 per request on a channel, mempool settlement up to 0.001 (`MERCHANT_ZERO_CONF_CAP_ZAT`)**; B. other numbers |

## 1. What exists and works today

Repository `x402-ycash` (`upgrade/vault` at `e1201bf`, 2026-11-16); plan status in
`docs/plans/x402-agent-payments-plan.md` §10.

### 1.1 The roles

| Role | Where | State |
|---|---|---|
| Paying agent (library) | `packages/ycash` (the x402 mechanism on `@x402/core` v2: `exact`, `batch`, `shielded`, `yed`, `lwd`) | built, unit + devnet tests on both lines |
| Paying agent (CLI) | `packages/cli`, binary `x402-ycash`: `pay`, `channel open|status|close|refund`, `yed-key new|address` (`packages/cli/src/config.ts` USAGE) | built; not published (`"private": true` in the root `package.json`) |
| Example agent | `examples/agent-client` (an `@x402/fetch` agent; `AGENT_*` variables, `src/config.ts`) | built |
| Merchant (resource server) | `examples/merchant-express` (an `@x402/express` server, routes in `src/app.ts`: `/exact/ticker`, `/exact/quote`, `/channel/search`, `/shielded/report`, `/shielded/private-report`, `/yed/report`, `/yed/stream`) | built; **its content is placeholder**: it shows how to charge, it sells nothing |
| Facilitator | `packages/facilitator`: `/verify`, `/settle`, `/supported`, `/healthz`, a `Dockerfile` | built; holds no keys, pays no fee; no image published |
| Private agent | `light/` (`x402-light`, Rust Sapling light client on librustzcash6, `TEST_NETWORK` is testnet-yb-fast since `a4935c51`) | built; needs `cargo build` and protoc |
| Python SDK | `python/x402_ycash`: facilitator, server and channel builders at parity; Python agents are not done (plan X5) | built |

### 1.2 Payment kinds

| Kind | Mechanism | Settlement | Status |
|---|---|---|---|
| Transparent YEC per request | `exact`: the agent signs a whole v4 transaction, the facilitator checks it and relays it (Cardano's pattern) | **about a second** at the mempool when the facilitator allows it (`X402_CONFIRMATIONS_MIN=-1`) and the amount is under the merchant's `MERCHANT_ZERO_CONF_CAP_ZAT`; otherwise one block (75 s on average) | green on both lines (X1) |
| YEC payment channel | `batch-settlement`: a one-way CLTV channel; vouchers off chain, one close | the funding waits for `MERCHANT_CHANNEL_CONFIRMATIONS` (1 by default, -1 allowed); then each request is instant; 1,000 requests cost two transactions | green (X2) |
| Shielded YEC | `sapling-proof` (agent sends from a node wallet; merchant issues a fresh diversified address and a signed receipt) and `sapling` (the agent's light client builds, the facilitator submits) | `MERCHANT_SHIELDED_CONFIRMATIONS` (-1 or 1) | green (X4a, X4b); the facilitator must be self-hosted with the merchant's viewing key |
| YED per request and on channels | `exact` at $1 or more (the dollar floor), YED channels on `TX_PQCHANNEL` with Falcon keys | as above | green on devnets (X3); **not possible on the fast testnet** (vault upgrade active, no YED attestor set: README "Status") and not on mainnet (no activation) |

Replay: the facilitator records every settled txid under `ycash:<net>:<txid>`
(`packages/ycash/src/store/settlementStore.ts`), so one payment buys one request. Mempool
settlement is a double-spend risk the merchant caps (`MERCHANT_ZERO_CONF_CAP_ZAT`; plan §8).

### 1.3 What each side must run

- **Merchant operator:** a synced `ycashd` (any; no flags for YEC; RPC on localhost, cookie auth),
  the facilitator against it, and an `@x402/express` server with the payment middleware. `payTo`
  is an address of a wallet the operator controls elsewhere: nothing on the request path holds a
  spending key, except the channel key S (`MERCHANT_CHANNEL_KEY`) when channels are on, and the
  viewing key when shielded routes are on (`docs/mainnet-runbook.md` §4, the key table). The
  facilitator's verify uses `signrawtransaction` with no keys as a script check; ycash6 allows it
  by default (`src/deprecation.h`, `DEFAULT_ALLOW_DEPRECATED`).
- **Agent:** Node.js 20+, a checkout built with `npm ci && npm run build`, and one of: a WIF key
  plus a lightwalletd URL (`--wif`, `--lwd`; no node at all), its own node wallet over RPC, a
  yewd in front of kogany (yewd serves the x402 `rpcWalletSigner` call set: yew
  `docs/plans/yewd-plan.md` S3), or `x402-light` alone for shielded routes. And funds.

### 1.4 What is missing for a public deployment

1. **No running instance anywhere.** The mainnet runbook and its capped smoke script exist and
   were rehearsed on regtest; the mainnet run itself (X6) has not been made.
2. **Nothing to buy.** The example merchant's routes return placeholders.
3. **No install path.** All packages are private; no image of the facilitator, merchant or CLI is
   published.
4. **No key generation for transparent YEC.** The CLI makes Falcon YED keys (`yed-key new`) but
   no WIF; an agent without a node has to get a key from a wallet export.
5. **No public faucet.** `images/faucet` has a testnet mode, but its image is not published and
   the chart faucet waits on decision T-9.
6. **One id for three testnets.** fast, slow and legacy all report `chain: "test"` and map to
   `ycash:testnet` (`packages/ycash/src/lwd/chain.ts`). A payment cannot settle on the wrong
   testnet (its inputs do not exist there), but a client cannot tell which testnet a server means.
7. **Block production on the fast testnet comes in rented-GPU bursts** (beta3 pool
   demonstration), so anything that waits for a confirmation can wait a long time. Mempool
   settlement avoids it.
8. **Generic x402 clients do not know `ycash:*`.** The upstream PRs are staged but not filed (X5),
   so an agent must use this repository's scheme package.

## 2. The public services today, and how x402 fits

| Service | Hosting | Fit for an x402 demo |
|---|---|---|
| Seeds `fastnet-seed.ycash.team` etc. | ycash-infra `infra/testnet-seeds` (EC2, P2P only, no HTTP) | none: P2P only by design |
| Pool `fastnet-pool.ycash.team` | seeds module `pool` block (yolo + a wallet-less node, t3a.small) | the pattern to copy: one role per host, its own state and deploy layer |
| Explorer `fastnet-explorer.ycash.team` | seeds module `explorer` block (node with insight indexes, PostgreSQL, Inzyght, Caddy; t3a.medium, already about 4 GB of limits) | poor: Inzyght has no licence (explorer plan, E5), so selling access to its API is a licensing question; and the host has no memory to spare |
| Light-wallet server `fastnet-lightwallet.ycash.team` | seeds module `lightwallet` block (node with insight indexes, lightwalletd-dd, Envoy gRPC-web, Caddy) | **the agent's backend**: the CLI pays with only `--wif` and `--lwd`; co-hosting the API there is possible (D-2 B) |
| Web wallet `fastnet-wallet.ycash.team` | a static bundle of `yew/web` (yew `web/README.md`), uses `x402_ycash_light` for Sapling | a human payer later: no "pay this 402" action today |
| Snapshots `snapshots.ycash.team` | static bundles in object storage behind a CDN (ycash-ops `site/snapshots`); the insight bundle is 41.8 GB; direct object-store access was left open on purpose (old links, in-region prefix reads by the seed and pool hosts) | a paywall needs a signing service and closing the direct path (§3.1) |
| ycash.team `x402/` page | `ycash-team-site/x402/index.html`: one line, "In development", a GitHub button | the page to rewrite (§5) |
| yewd | `yew/yewd`, the YEW core as a daemon in front of kogany | can be an agent's wallet over RPC today (§1.3) |

## 3. Candidates

Effort in agent-days; cost per month on AWS on-demand prices (ycash-infra
`infra/testnet-seeds/README.md`, "Cost estimate").

### 3.1 (a) A paid mirror of the snapshot downloads

- **Experience:** a person restoring a node runs `x402-ycash pay
  https://…/main-insight/latest` and gets back a short-lived download URL; or an agent setting up
  a node does it unattended.
- **To build:** a merchant whose resource is a signed URL: after `/settle` it signs a CDN URL
  (a CDN key pair) valid for the download's duration; ycash-ops: a key group on the
  distribution, the signer's credential, and **closing direct object-store reads**, without which
  the paywall is a suggestion. That last step breaks the old links and the seed and pool hosts'
  prefix reads unless they get signed access too.
- **Hosting:** the signer service (any small host) plus a mainnet facilitator node.
- **Risks:** the signing key is a hot credential (a leak lets anyone mint URLs: a transfer bill,
  not lost coins). A signed URL is shareable for its whole validity, which must cover a 40 GB
  download with resumes (hours): free-riding is easy; an IP-bound policy breaks clients whose
  address changes. Real money from day one, before the X6 run. YEC price volatility against a cost
  measured in dollars (about $0.085 per GB, ≈ $3.50 per insight download).
- **The bootstrap problem:** the person who needs a snapshot is the person without a synced node,
  so without a wallet holding YEC. The CLI's `--wif` + `--lwd` path solves it technically (a
  mainnet lightwalletd is enough), but it asks a newcomer for YEC on a key before they can run the
  node that would hold it.
- **Argument on the free link:** keep it. The snapshots exist to make running a node cheap, which
  is the network's interest; a toll on that path discourages exactly the operators the project
  wants, and a paid copy beside a free one demonstrates a donation button, not a market. The paid
  mirror explains x402 less well than an API, because the payment buys a URL rather than an answer.
- **Effort:** 7–10 days; cost: the signer host (≈ $21) plus transfer either way. **Not recommended
  now** (D-7).

### 3.2 (b) A paid chain-data API for agents on the fast testnet (recommended)

- **Experience:** an agent (or a person with the CLI) asks
  `GET https://fastnet-x402.ycash.team/v1/address/<addr>`, gets `402` with the price in the
  `PAYMENT-REQUIRED` header, signs 0.0001 testnet YEC, retries and gets JSON: balance, UTXOs,
  recent transactions, each with its decoded type (transparent, Sapling, vault, post-quantum). A
  free, rate-limited `/v1/tip` shows the difference between free and paid. The page at the same
  name explains the flow, links the explorer to watch the payment arrive, and has the faucet.
- **To build:**
  - x402-ycash: `examples/chain-api`, a real merchant on the existing middleware: routes for an
    address report, a decoded transaction, a mempool summary and a fee estimate, reading the
    host node's RPCs (`getaddressbalance`, `getaddressutxos`, `getaddresstxids`,
    `getrawtransaction`, `getrawmempool`), `exact` and a channel route (2–3 d). A `key new` CLI
    command that writes a WIF and prints its address, and a `--wif-file` option (0.5 d). The
    testnet-profile check of D-6 in the facilitator and the API (0.5 d). Images of the
    facilitator, the API and the CLI, built and published by x402-ycash CI by digest (1 d).
  - ycash-infra: an `x402` block in the seeds module (a node with `-txindex -insightexplorer` and
    a wallet for the faucet, the faucet, the facilitator, the API, Caddy with its certificate;
    seedctl's `apply`/`status`/`reset`; the hardening the other roles have: uid per container,
    read-only roots, no capabilities, RPC on the internal network, the metadata guard) and its
    tests (2–3 d).
  - ycash-ops: roots `testnet-x402/{ips,nodes}`, a deploy layer and its role, the DNS name; the
    lead architect applies by hand as for the other hosts (1 d).
  - The recorded run (an agent script: faucet, ten paid requests, a channel of 100 requests,
    close; the transcript and the txids on the explorer), the runbook and the site page (1 d).
- **Hosting:** one t3a.small (2 GiB + swap; the fast testnet chain is small), one address, ports
  80/443 and P2P out. ≈ $21/month plus transfer.
- **Risks:** no mainnet value at stake; the facilitator holds no key; `payTo` is the faucet's
  wallet (testnet coins, a hot wallet by design, the faucet's daily cap bounds a drain); the
  channel key S is hot but only guards testnet earnings. Replay is refused by the settlement
  store. Mempool double-spends are bounded by the zero-confirmation cap. Denial of service: a 402
  costs nothing, a paid attempt costs the facilitator a few RPC calls, so the facilitator's
  `X402_RATE_LIMIT` and a per-IP limit in Caddy apply, with the 64 KB header limit for vouchers.
  Free-riding: an agent may resell answers; that is fine. Burst block production (§1.4 item 7) is
  why the demo settles at the mempool and allows channel fundings at -1 on the testnet.
- **Effort:** 8–10 days.

### 3.3 (c) A paid MCP tool and a reference agent

- **Experience:** an AI assistant gets tools like `ycash_address_report`; each call costs 0.0001
  testnet YEC, which the tool pays by itself from a budget the user set, and the answer shows the
  txid. The recorded run is an assistant answering "what happened at this address today" with
  three paid calls.
- **To build:** a small local stdio MCP server in x402-ycash (`examples/mcp-agent`) whose tools are
  the API's routes, paying with the existing client (key file, `--lwd`, `--max-payment`, plus a
  per-session budget). Simpler and safer than the remote MCP payment transport
  (`_meta["x402/payment"]`, plan X5), which can follow once the upstream binding is filed.
- **Hosting:** none beyond §3.2 (the MCP server runs on the user's machine).
- **Risks:** the MCP server holds a key, so the budget cap and testnet-only defaults matter; a
  prompt-injected assistant can at most spend the budget.
- **Effort:** 2–3 days on top of §3.2. **Recommended as the second step** (D-8).

### 3.4 (d) Faucet, pool, YED and other ideas

- **Faucet:** not an x402 use by itself (x402 is pay-to-get), but it is the missing first step of
  every demonstration; hence D-4. Pointing `payTo` at the faucet's wallet closes the loop.
- **Pool:** yolo reaches the node only through the stock mining RPCs (workspace rule 2), and
  miners are paid by the block, not per request. A paid pool-statistics API would work but
  explains nothing the chain-data API does not. Not recommended.
- **YED-denominated payments:** the routes, the channels on `TX_PQCHANNEL` and the Falcon keys
  are built (X3); the fast testnet has the vault upgrade but no YED attestor set. Once it has one,
  the API adds a `$0.01` YED channel route (an `exact` YED payment cannot go below $1). A small
  addition, blocked on the testnet's attestor set, not on x402.
- **Private agents (better idea, part of the first step if time allows):** the `sapling` method
  with `x402-light` and only the public light-wallet server is the feature no other x402 network
  has. On the demo host it needs the facilitator self-hosted with a viewing key and the receipt
  key (`docs/mainnet-runbook.md` §4, shielded layout). +1–2 days; the agent needs `cargo build`
  of `x402-light` or its image.
- **A human payer in the web wallet:** `yew/web` already carries the light client; a "pay this
  402 link" action would show x402 to people, not only agents. 5+ days in yew; later.

### 3.5 Ranking

| Rank | Candidate | Explanatory value | New infrastructure | Real money | Effort |
|---|---|---|---|---|---|
| 1 | (b) chain-data API, fast testnet, with faucet and reference agent | high: an agent buys an answer | one small host | no | 8–10 d |
| 2 | (c) MCP tool on (b) | high for AI users | none | no | +2–3 d |
| 3 | private agent (`sapling`) on (b) | high: unique to Ycash | none | no | +1–2 d |
| 4 | YED channel route on (b) | medium | none | no | small; blocked on a testnet attestor set |
| 5 | (a) snapshot paid mirror | low: buys a URL | signer, CDN key, closing direct reads | yes | 7–10 d |
| — | pool API, web-wallet payer | low / later | — | — | — |

## 4. Recommendation and sequence

1. **Fast testnet, soon after beta3:** §3.2 at `fastnet-x402.ycash.team` (D-1 A, D-2 A, D-3 A,
   D-4 A, D-5 A, D-6 A, D-10 A), then §3.3 and the private agent. Acceptance: from a clean machine,
   the two commands of §5 return paid JSON; the recorded run is linked from the site; the host's
   `status` shows payments settled and none refused for a reason other than the client's.
2. **Mainnet (D-9 A):** the lead architect runs X6 (`docs/mainnet-runbook.md`, `tools/mainnet/smoke.sh`)
   on both lines; then the same API at `x402.ycash.team` on a mainnet insight node, prices of
   0.0001 YEC, transparent and shielded, revenue to an offline key, the viewing-key layout. YED
   routes once the vault upgrade is active on mainnet. The snapshot mirror is reconsidered only
   with usage figures from this step (D-7).

## 5. The ycash.team x402 page, after step 1

Five sentences, then the two commands:

> x402 lets a program pay for a web request by itself: the server answers "402 Payment Required"
> with a price, the program signs a small YEC payment and asks again, and the answer arrives about
> a second later. You can try it now on the Ycash fast testnet, where coins are free:
> `https://fastnet-x402.ycash.team` sells chain data, such as an address report, for 0.0001
> testnet YEC a request. Make a key with the first command below, then get coins for its address
> from the faucet on that page. The second command pays for one report and prints it, and the
> explorer shows the payment. To charge for your own service, run the facilitator and put the
> payment middleware in front of your routes, as the guide on GitHub shows.

```
docker run --rm -v "$PWD:/w" ghcr.io/boyfromcave/x402-ycash-cli@sha256:<digest> key new /w/agent.wif
docker run --rm -v "$PWD:/w" ghcr.io/boyfromcave/x402-ycash-cli@sha256:<digest> pay \
  https://fastnet-x402.ycash.team/v1/address/<your address> \
  --network ycash:testnet --lwd fastnet-lightwallet.ycash.team --wif-file /w/agent.wif
```

(`key new` and `--wif-file` are the two CLI additions of §3.2; the rest exists today.)

## 6. Open checks before building

- The fast testnet's YED attestor set: if one is planned, schedule the YED channel route with it.
- Whether the lightwallet host's lightwalletd rate limits allow an agent's UTXO lookups at demo
  volume (its per-peer Yellowback limiter counts by client address).
- The licence of any third-party software served behind a paywall (Inzyght is excluded for this
  reason).
