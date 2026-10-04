# x402 agent payments plan — HTTP-402 payments in YEC and YED, on both node lines

**Status:** revision 2, 2026-10-03, **in implementation — every phase item that does not need the owner is done (2026-10-04)**. The owner's decisions are recorded
in §0.0; every X-decision of §0.2 is now decided. The repository `boyfromcave/x402-ycash` exists
and is the primary repository for executing this plan. §3 is the
on-paper proof: every claim the design rests on is checked against the code of **both** node
lines, `ycash-dd` (v4.5.0) and `ycash6` (6.21.0-rc1), with citations. The phases in §7 turn that
paper proof into a running one on the regtest devnet of each line. The checklists in §7 and the
table in §10 are the status of record; agents tick a box the moment the item is done.

x402 is an open protocol (the x402 Foundation, `github.com/x402-foundation/x402`, protocol
version 2) that revives HTTP status `402 Payment Required`. A server answers an unpaid request
with its price. The client, typically an AI agent, retries with a signed payment in a header. A
**facilitator** verifies the payment and settles it on a chain, and the server returns the
resource. Today it runs on EVM chains, Solana, Cardano, Stellar, Lightning and a dozen others,
but on no Zcash-lineage chain and with no private payment rail. This plan adds Ycash as an x402
network. YEC and YED are the assets, and private (shielded) payments are the feature no other
x402 network has. It does this **with no consensus change and no node change**, on both node
lines, as an optional add-on that node operators and pool operators never have to know about.

## 0. Revision log

### Revision 2 (2026-10-03) — the owner's decisions; implementation begins

#### 0.0 Owner decisions (2026-10-03)

| # | Decision | Where |
|---|---|---|
| X-1 | **Confirmed.** The owner created `github.com/boyfromcave/x402-ycash` (a README only). It is a net-new, writable `app` repository with no reference to pin and no baseline, and it is **the primary repository for executing this plan**. Workspace path `x402-ycash/`, branch `main`, wired into `repos.yaml` and the `make` targets in X0. | §5.1, X0 |
| X-2 | **Confirmed: TypeScript first**, the x402 main SDK language, for ease of use, reference, adoption and compatibility. **A backend SDK, Python, stays on the radar.** Concretely: (i) every binding rule lives in the language-neutral spec files, not only in TypeScript; (ii) X1–X3 emit **JSON test vectors** (`vectors/*.json`: transactions, sighashes, scriptSigs, payloads, verify verdicts) that any port must reproduce; (iii) X5 carries a Python mechanism (`python/x402/mechanisms/ycash`, upstream layout) for backend facilitators and servers, built from the specs and vectors. | §5.2, X1, X5 |
| X-7 | **Confirmed: the YED dollar floor** as proposed. | §5.8 |
| X-8 | **Confirmed: private payments start simple (X4a) and the advanced variant (X4b) stays in the plan.** The owner names **trial decryption, view keys and selective disclosure** as the major challenge. To know a note is yours, a Sapling wallet must trial-decrypt every shielded output, and that may block private payments in the short run. §5.10 analyses who scans what in X4a and X4b, what a viewing key reveals to whom, and what selective disclosure exists. X4 begins with a **measurement gate** (X4-M) before any build beyond X4a. | §5.9, §5.10, X4 |
| X-3..X-6, X-9..X-11 | **Adopted as proposed.** The owner directed the work to proceed with questions kept to a minimum. Revisit only if implementation finds a reason. | §0.2 |

Revision 2 also adds §5.10 (the shielded scanning problem), the X4 measurement gate, the
vectors requirement, the Python item in X5, and the execution model (§7.0).

### Revision 1 (2026-10-03) — first draft, from the owner's direction

Built from:

- the x402 v2 launch notes (`x402.org/x402-v2-launch/`);
- the specification tree at `x402-foundation/x402` commit `751590a` (2026-10-02);
- two node surveys, of `ycash-dd` at `feature/yellowback-price-attest` and `ycash6` at
  `feature/yellowback`;
- a survey of the workspace tooling (devnet, qa, yolo, lightwalletd-dd, YEW, chain-viz).

All of these were taken on 2026-10-03.

### 0.1 Owner direction (2026-10-03), as given

| # | Direction | Where |
|---|---|---|
| O-1 | **A new repository for the code is approved.** | §5.1, X0 |
| O-2 | **Order: YEC pay-per-request, then payment channels (YEC, then YED), then private payments.** | §7 X1 → X2 → X3 → X4 |
| O-3 | **Both node lines:** Ycash 4.5.0 (`ycash-dd`) and 6.21.0 (`ycash6`). | §6, every phase's acceptance |
| O-4 | **Optional for node operators and pool operators.** The feature is experimental and nobody running a node or a pool has to enable, configure or upgrade anything. | §4 |
| O-5 | **Prove it on paper first, then prove the plan, and record the precedent of Cardano and the other chains.** | §2.3, §3, §7 |

### 0.2 Decisions as proposed in revision 1 (all decided in revision 2, §0.0)

| # | Decision (proposed) | Where |
|---|---|---|
| X-1 | **Repository `boyfromcave/x402-ycash`**, an `app` in `repos.yaml` like `yolo` and `chain-viz`: branch `main`, no reference, no baseline. Workspace path `x402-ycash/`. It holds the binding specs, the SDK mechanism package and the facilitator. | §5.1, X0 |
| X-2 | **TypeScript on `@x402/core` (protocol v2)**, modelled on `@x402/cardano`. x402's TypeScript SDK is the reference: every network ships there first, and the Foundation's CONTRIBUTING asks for a reference implementation in one SDK before others. Node 23.3 and npm are installed (pnpm is not; it is needed only inside the upstream monorepo). There is no TypeScript in the workspace today, which is the cost; the alternative (Go, as lightwalletd) is recorded in §5.2. | §5.2 |
| X-3 | **Network ids `ycash:mainnet`, `ycash:testnet`, `ycash:regtest`**, following Cardano's unregistered `cardano:mainnet` form. The genesis-hash form that Lightning (`lnbtc:`) and Algorand use **cannot** be used: Ycash's three genesis hashes are Zcash's (§3, row G-1). | §5.3 |
| X-4 | **Assets `YEC` (atomic unit the zatoshi, 10⁻⁸) and `YED` (atomic unit the cent).** These are symbols, like Lightning's `"BTC"` and Canton's `"CC"`. Neither asset has a contract address. | §5.3 |
| X-5 | **The payer pays the network fee in every phase (`areFeesSponsored: false`)**, as Cardano and XRPL do. Fee sponsorship (`ALL\|ANYONECANPAY` plus a pool of fee-sized coins) is recorded and not scheduled. | §5.4, §8 |
| X-6 | **Confirmation policy is per route and default-fast.** The default is `exact` settled at mempool acceptance (`confirmations: -1`) up to a server-set amount cap, with 1 confirmation above it. Channels need their funding transaction confirmed once before the first voucher, or zero confirmations for small channels if the server opts in. The field follows Cardano's `extra.confirmationPolicy`. | §5.5 |
| X-7 | **YED channel rule ("the dollar floor"):** every YED voucher's cumulative amount is at least $1.00 (it pre-pays the first dollar). The client's remainder is either 0 or at least $1.00. A remainder in (0, $1.00) goes to the server, never to a burn. | §5.8 |
| X-8 | **Private payments start client-submitted** (X4a). The server hands out a fresh diversified `ys1…` address per request, the client pays it with any shielded wallet, and the server checks receipt. This uses stock RPCs only, on both lines. A facilitator-submitted shielded variant (X4b, which needs a Rust Sapling builder from `librustzcash6`) is built only on a separate owner go. | §5.9 |
| X-9 | **Upstream after proof.** We build and prove in our repo. After X1 is green on both devnets, we open the Foundation's spec PR (`scheme_exact_ycash.md`). After X3, the `batch-settlement` binding follows, then the implementation PR into `typescript/packages/mechanisms/ycash`. Until then we publish from our repo. | X5 |
| X-10 | **No node change, on either line.** Anything the node could do better (a dry-run acceptance RPC, a raw-transaction decrypt with a viewing key) is recorded as an N-ask (§4.4), not scheduled. If one is ever built, it is behind `-experimentalfeatures` plus its own flag, using Yellowback's conditional-registration pattern, not atomic swap's. | §4.4 |
| X-11 | **Regtest first, then a small mainnet run; testnet as available.** Testnet was unreachable on 2026-10-02 (no fixed seeds, the seeders did not resolve). Mainnet YED waits for Yellowback's mainnet `startHeight` 3,075,000. | §6.3, X6 |

## 1. The problem

AI agents increasingly buy things a call at a time: a search, a dataset row, a model call, a
tool. x402 is becoming the standard way to charge them, and it is chain-agnostic by design. v2
made new networks plug-ins: "developers register chains, assets, and payment schemes instead of
editing SDK internals". Ycash has two things to offer that market:

- **YED, a dollar.** Agents and the APIs they call price in dollars; x402's dominant asset today
  is USDC.
- **Privacy.** Every x402 network today is transparent: each agent payment publicly links payer,
  payee and amount. Ycash's Sapling pool can carry a payment that reveals none of them on chain.

What stands in the way is that Ycash has no smart contracts, no EIP-3009-style signed-transfer
authorization, no account nonces and no CSV, and YED transfers have a $1.00 minimum output. Every
other x402 binding leans on at least one of those. This plan shows that x402 needs none of them
from Ycash, and gives the order in which to prove it.

### 1.1 What "done" means

1. **X1–X4 green on both node lines.** An x402 client pays an x402-protected HTTP endpoint on the
   regtest devnet of `ycash-dd` and of `ycash6` in each of the four modes: YEC per request, YEC
   channel, YED channel (and YED per request at ≥ $1), private YEC. The test is an end-to-end run
   through the stock x402 HTTP middleware, the SDK's client, server and facilitator mechanisms,
   and a real node.
2. **Optionality proven, not asserted (§4).** The same runs pass with the payments mined by the
   devnet's stock seat, by Yellowback pool seats under the default `strict` template policy, and
   by the `yolo` stratum pool, with no flag added anywhere. No commit from this plan touches
   either node repository.
3. **The binding specs are written in the Foundation's format** and pass its family checklists
   (§2.2) line by line, ready for the upstream PRs (X5).

## 2. x402 v2: what a network must supply

### 2.1 The protocol in one page (`specs/x402-specification-v2.md`)

- **Types.**
  - `PaymentRequired` carries `accepts[]`, each entry giving `scheme`, `network` (CAIP-2),
    `amount` (atomic units), `asset`, `payTo`, `maxTimeoutSeconds` and `extra`.
  - `PaymentPayload` carries `accepted` plus a scheme-specific `payload`.
  - The responses are `SettleResponse {success, transaction, network, payer, amount?}` and
    `VerifyResponse {isValid, invalidReason, payer}`.
- **HTTP transport.** The headers are `PAYMENT-REQUIRED` (base64 JSON, on the 402),
  `PAYMENT-SIGNATURE` (the client's payload) and `PAYMENT-RESPONSE`. The v1 `X-PAYMENT*` headers
  are retired. The MCP transport carries the payload in `params._meta["x402/payment"]`
  (`specs/transports-v2/mcp.md`).
- **Facilitator interface.** `POST /verify` is read-only and MUST NOT write chain state.
  `POST /settle` durably commits. `GET /supported` lists `kinds[]`, `extensions[]` and
  `signers{}`. A resource server MAY host these itself.
- **Payment flows (§6.1).**
  - `authorization` (default): verify, then the resource runs, then settle.
  - `upfront`: settle before the resource runs; required where there is no pull primitive.
  - `escrow`: settle a deposit, run the resource, then settle the charge.

  `extra.assetTransferMethod` and `extra.paymentFlow` are reserved keys.
- **Errors.** `settlement_pending` is non-terminal and MUST carry the broadcast transaction id.
- **Extensions.**
  - `payment-identifier` gives idempotent retries.
  - `offer-and-receipt` gives server-signed offers and receipts; its JWS format is chain-neutral.
  - `bazaar` gives discovery.
  - `sign-in-with-x` gives CAIP-122 wallet sessions. It covers `eip155:*` and `solana:*` only.

### 2.2 The obligations a binding must meet

`specs/schemes/exact/scheme_exact.md` splits `exact` methods into two families, and each family
has a checklist. Section 5 answers both checklists for every Ycash method.

- **Facilitator-submitted.** The client signs; the facilitator submits.
  - MUST declare: the fee payer; the replay primitive, including its limit on concurrent payments
    and whether unrelated payer activity can invalidate a payment after the handler ran; the
    validity window; and whether a duplicate submission is distinguishable.
  - MUST satisfy: settlement produces exactly one identifiable transfer of `amount` of `asset` to
    `payTo`; the facilitator is never debited beyond a sponsored fee; the network's replay
    primitive is authoritative; duplicate delivery is deduplicated atomically where a resubmission
    is indistinguishable.
- **Client-submitted (payment proof).**
  - MUST use `upfront`.
  - MUST advertise the instrument and carry the proof.
  - MUST bind the proof to the request by one of: an instrument unique to the request, a nonce, a
    payer signature, or a payee commitment.
  - MUST claim the proof atomically and single-use, keyed by `CAIP-2:payment-id`.
  - MUST bound retention.
  - MUST state how under- and over-payment are handled.
  - MUST declare the finality event, and MUST NOT consume the proof before it.
  - MUST state the failure disposition.

`specs/schemes/batch-settlement/scheme_batch_settlement.md` asks every binding for seven things:

1. commitment format;
2. verification rules;
3. storage behaviour and the commitment identifier;
4. double-spend prevention;
5. commitment expiry;
6. redemption;
7. trust model (capital-backed or credit-backed).

It names "payment channel streaming … a signed running total" as a use case and "payment
channels" as capital-backed. **Nothing in it requires a contract.**

`upto` (one authorization, settle ≤ a maximum) is **not** bound for Ycash. Every existing `upto`
binding is either an allowance (EVM Permit2) or a one-request escrow channel (SVM, which notes
that "a signed transfer can't lower its amount"). On Ycash the latter costs a confirmation (~75
s) per request. `batch-settlement` already allows the server to charge less than the committed
price per request, so channels cover metered pricing. This is recorded in §8.

### 2.3 Precedent: how the other chains did it

Every binding in the spec tree at `751590a`. Rows marked ★ are the ones the Ycash design copies.
"Silent" means the spec does not say.

| Binding | Network id | Payload | Family / flow | Fees | Replay primitive | Validity window | Duplicate rule | Lesson for Ycash |
|---|---|---|---|---|---|---|---|---|
| ★ exact **cardano** | `cardano:mainnet\|preprod\|preview`, **not CASA-registered** (`scheme_exact_cardano.md:23`) | `{transaction, nonce:"txHash#i"}`, a complete signed tx the client does not broadcast (:31, :663) | facilitator-submitted / authorization | **self-funded**, `areFeesSponsored:false`; sponsorship "left to a future extension" (:884-892) | the nonce UTXO | TTL slot ≤ now + maxTimeout (:818) | RECOMMENDED atomic claim on the txid (:913-932) | **The UTXO template.** Ycash's X1 is this binding with `nExpiryHeight` for TTL and txid dedup. Also the network-id form and `confirmationPolicy` (-1..20, default 1; :154-168) |
| ★ exact **xrpl** | `xrpl:<NetworkID>` | `{signedTxBlob}` (:257-261) | facilitator-submitted / authorization | **self-funded; MUST be false** (:11-21) | Sequence / TicketSequence | LastLedgerSequence | **REQUIRED** tx-hash dedup until expiry (:456-475) | Dedup is mandatory when resubmission is indistinguishable, which is exactly Ycash's `sendrawtransaction` (§3, R-3) |
| ★ exact **canton** | `canton:mainnet\|…` | prepared tx + signature | facilitator-submitted | sponsored | **consumed input holdings** (UTXO-like) (:292-316) | `executeBefore` | none beyond the ledger | The UTXO set is the replay primitive; spent inputs make a replay fail by construction |
| ★ exact **lnbtc** (Lightning) | `lnbtc:<BTC genesis[:32]>`, a new namespace on the bip122 convention (:23-34) | `{preimage}` | **client-submitted / upfront** (:43-61) | payer | payment hash | invoice expiry + grace | durable atomic `network:payment_hash` (:600-635) | **The client-submitted template for X4a**: a per-request instrument (a fresh invoice there, a fresh diversified address here), upfront, a durable consumption store. Its genesis-prefix id cannot be copied (G-1) |
| exact evm | `eip155:<id>` | EIP-3009 / Permit2 / ERC-7710 authorization | facilitator-submitted | sponsored | contract nonce | validBefore | silent | The authorization model Ycash cannot have: no contract can hold a nonce |
| exact svm | `solana:<genesis>` | partially signed tx | facilitator-submitted; upfront for long handlers (:47) | sponsored `extra.feePayer` | blockhash + signature | ~60–90 s | RECOMMENDED cache | Upfront exists for validity windows shorter than a handler |
| exact algo / aptos / concordium / hedera / keeta / near / starknet / stellar / ton | `algorand:`, `aptos:`, `ccd:`, `hedera:`, `keeta:`, `near:`, `starknet:`, `stellar:`, `tvm:` | signed tx, delegate action or authorization | facilitator-submitted | mostly sponsored | account or sequence nonces | expiry / ledger bounds | mostly silent or cache | Account chains; their safety rules (fee payer never debited beyond the fee) apply only if Ycash ever sponsors |
| exact casper / sui | `casper:`, `sui:` | CEP-3009 authorization / signed tx | facilitator-submitted | facilitator / self or gas station | nonce / owned objects | validBefore / silent | silent | — |
| ★ batch-settlement **svm** | solana | deposit / voucher / refund on a payment-channels program (`CHNLx…`) | program; authorization | sponsored | **cumulative watermark** | withdrawDelay, maxIdleSecs | Phase 5 (:1639) | **The channel shape**: open, then cumulative vouchers, then close, with a unilateral escape after a delay. Ycash's escape is a CLTV branch instead of a program |
| batch-settlement evm | eip155 | deposit / voucher / refund on `x402BatchSettlement` | contract | sponsored | cumulative `maxClaimableAmount` | withdrawDelay 15 min–30 d | silent | No dispute game and no voucher expiry (:666-672): a one-way channel needs neither |
| batch-settlement cloudflare | `cloudflare:402` | `{amount, asset}` + RFC 9421 HTTP signature | credit-backed | none | — | ~30 s freshness | stateless | How loose the generic contract is: no chain at all |
| upto evm / svm | eip155 / solana | Permit2 witness / one-request channel (escrow flow) | — | sponsored | Permit2 nonce / channel PDA | deadline / expiresAt | — | Why `upto` is skipped (§2.2) |
| auth-capture evm | eip155 | authorization to an escrow collector | escrow / authorization | relayed | collector nonce | several expiries | silent | Not applicable without contracts |

What the precedent settles:

- **There is a UTXO binding** (Cardano), shipped in the TypeScript SDK as `@x402/cardano`.
- **There is a self-funded binding** (Cardano and XRPL), so the payer paying the fee is accepted.
- **There is a client-submitted binding** (Lightning), so an `upfront` proof-of-payment method is
  accepted.
- **There is a channel binding** (EVM and SVM), and the generic channel contract does not require
  a contract.
- **Unregistered namespaces are accepted** (Cardano, Lightning).

Ycash would be the second UTXO network, the second network without smart contracts after
Lightning, and the first with private payments.

## 3. Feasibility on paper (both node lines)

Each row is a fact the design depends on, checked in the code on 2026-10-03. `ycash-dd`
citations are at `feature/yellowback-price-attest`; `ycash6` citations are at
`feature/yellowback` (6.21.0-rc1). "Same" means the same code at the cited line on the other line.

### 3.1 Transactions, relay and verification

| # | Fact | `ycash-dd` (v4.5.0) | `ycash6` (6.21.0) | Consequence |
|---|---|---|---|---|
| R-1 | A complete transparent v4 transaction signed offline can be relayed by anyone with `sendrawtransaction` | stock, `src/rpc/rawtransaction.cpp:1155-1179` | `:1255`, `:1325-1345`. **v5 is refused by consensus** while NU5 has no activation height (`src/chainparams.cpp:139-147`, `src/main.cpp:995-1003`), so v4 is the format on both lines | **X1's payload is a signed v4 tx**, like Cardano's |
| R-2 | **`nExpiryHeight` is a native validity window.** `createrawtransaction` takes it as its 4th argument; it must be ≥ next + `TX_EXPIRING_SOON_THRESHOLD` (3); the default `-txexpirydelta` is 40 blocks after Blossom | `:602-617`, `src/main.h:78-81` | `:688`, `:755`, `src/main.h:96-97,105`; capped at the next activation height − 1 (`src/main.cpp:9442-9467`) | The equivalent of `validBefore` with no contract. At 75 s blocks the minimum useful window is about 4 blocks (5 min) |
| R-3 | `sendrawtransaction` of a tx **already in the mempool returns its txid with no error**; already mined gives `-27` | `:1159`, `:1173-1178` | `:1325-1345` | A resubmission is **indistinguishable**, so the facilitator MUST deduplicate by txid (the XRPL rule) |
| R-4 | No `testmempoolaccept` or other dry-run acceptance RPC | absent | absent | `/verify` is a composite (§5.6). Recorded as N-1 |
| R-5 | `signrawtransaction hex [] []` (empty prevtxs and keys) runs `VerifyScript` on every input and returns `complete` and `errors` without signing: a **script verifier on a stock node** | `:1069-1079` | `:970`, `:1226-1231`; "deprecated" but allowed by default (`src/deprecation.h:47-77`) | X1 can verify scripts on a node without `-yellowback` |
| R-6 | `gettxout txid n includemempool` reports an unspent output and its `confirmations`; with `includemempool=true` it hides outputs a mempool tx already spends | `src/rpc/blockchain.cpp` (`gettxout`) | same | Input liveness, mempool double-spend detection and confirmation tracking **without `-txindex`** |
| R-7 | `createrawtransaction` has **no `data` (OP_RETURN) key**; every output key is decoded as an address | `:647-652` | `:790-808` | The SDK serialises transactions itself, as the qa framework does (`test_framework/yellowback_model.py:1099`) and YEW does (`yew/core/src/tx.rs`) |
| R-8 | The stock signer **cannot sign a custom (IF/ELSE) redeem script**: `SignStep` returns false for `TX_NONSTANDARD`, and `CombineSignatures` keeps the larger scriptSig | `src/script/sign.cpp:84-86`, `:288-292` | same | The SDK computes the ZIP-243 sighash and assembles channel scriptSigs itself. Precedent: atomic swap does exactly this (`src/script/atomicswap.cpp:151-185`, present on both lines) |
| R-9 | `signrawtransaction` supports `ALL\|ANYONECANPAY` | `:1008-1016` | `:1158-1167` | Fee sponsorship is possible later without a node change (X-5) |

### 3.2 Script and standardness

| # | Fact | `ycash-dd` | `ycash6` | Consequence |
|---|---|---|---|---|
| S-1 | A P2SH spend whose redeem script matches no template is **standard** if its sigops are ≤ 15 (`MAX_P2SH_SIGOPS`) | `src/policy/policy.cpp:174-179`, `policy.h:24` | `policy.cpp:204-209`, `policy.h:37` | The channel script (§5.7) counts 3 sigops and relays everywhere. (Quirk: that branch returns early for the whole tx; harmless here) |
| S-2 | **CLTV** is in the standard flags and the consensus flags; the spending input's `nSequence` must be non-final | `policy.h:32-40`, `src/main.cpp:2936`, `src/script/interpreter.cpp:1307-1338` | `policy.h:52`, `main.cpp:3413` | The channel's refund branch works |
| S-3 | **No CSV**: OP_NOP3 is a NOP, discouraged by policy | `interpreter.cpp:388-393` | `:391-395` | Not needed. A one-way channel with an in-script CLTV refund has no pre-signed refund tx, so txid malleability does not matter either |
| S-4 | One OP_RETURN per tx, ≤ 80 data bytes | `src/script/standard.h:34`, `policy.cpp:121-125` | `standard.h:26`, `policy.cpp:156-160` | A YED tx's single OP_RETURN is its TRANSFER payload (≤ 5 + 5·15 = 80 bytes). **There is no room for a second, request-binding OP_RETURN** |
| S-5 | scriptSig push-only, ≤ 1650 bytes; dust = 3 × relay fee × (size + 148) ≈ 54 zat | `policy.cpp:89-100`, `src/primitives/transaction.h:460-479` | `policy.cpp:116-124`, `src/primitives/transaction.cpp:67-79` | Channel scriptSigs (~250 bytes) fit |
| S-6 | **Fees.** v4.5.0: `DEFAULT_FEE` 1000 zat, min relay 100 zat/kB. 6.21.0: ZIP-317 conventional fee with `MARGINAL_FEE` 500 and `GRACE_ACTIONS` 2, unpaid-action limits off, ZIP-401 eviction penalty below the conventional fee | `src/policy/fees.h:15`, `src/main.h:68` | `src/zip317.h:16-17,42,54`, `src/mempool_limit.h:24-25`, `src/main.h:72` | One rule for both lines: **fee = max(1000, 500 × max(2, logical actions))**. It is 1000 zat for a 1-in-2-out payment and about 2500 for a channel close |

### 3.3 The Yellowback overlay (YED)

| # | Fact | `ycash-dd` | `ycash6` | Consequence |
|---|---|---|---|---|
| Y-1 | **Transfer rules XFER-1..3 ignore script type**; a token record takes any `scriptPubKey` | `src/yellowback/state.cpp:443-474` | same | **YED can sit in a P2SH channel output** at the overlay level |
| Y-2 | `yedIn` sums the token records of the spent outpoints, whatever their script | `state.cpp:797-810` | `:797-808` | YED spent out of a channel counts |
| Y-3 | **Minimum YED output $1.00** (`minOutput` 100 cents), maximum $100,000; an assignment outside the range makes the whole transfer invalid, and **everything burns** | `src/yellowback/params.cpp:18-19`, `state.cpp:448-456` | same | YED per request is possible only at ≥ $1. Sub-dollar YED goes through channels, with the dollar floor (X-7) |
| Y-4 | **A YED spend with no payload burns its YED** (type NONE, verdict BURNED, IN-3) | `state.cpp:860-865`, `:879-883` | `:864`, `:879-882` | **A YED channel's refund and close must each carry a TRANSFER payload** |
| Y-5 | The default template policy `strict` **skips a TRANSFER with `burned > 0`**, and never filters a tx with no token input and no payload | `src/yellowback/policy.cpp:91-100`, `:121`, `src/init.cpp:1176` | `policy.cpp:100`, `:124`, `init.cpp:411,1308` | Every channel transaction assigns all of `yedIn` by construction. A stock (non-Yellowback) miner would mine a burn, so the facilitator's verify is the guard |
| Y-6 | `MempoolCheck` refuses only spends of ACTIVE vaults | `src/yellowback/index.cpp:726-735` | `:774-778` | Channel and payment txs are never refused at relay by the overlay |
| Y-7 | "YED inputs must be confirmed" is **wallet policy**, not an overlay rule | `src/yellowback/txbuilder.cpp:365-370`, `policy.h:49-54` | same | The facilitator adopts it as its own policy (`unconfirmedInputs` must be empty) |
| Y-8 | **No P2SH YED address**: a `ye…` address is base58(version ‖ key hash) only; `yed_send` refuses anything else | `src/yellowback/address.cpp:11-27`, `src/rpc/yellowbackwallet.cpp:145-149` | `address.h:10-14`, same | The SDK builds YED channel funding transactions itself (R-7) |
| Y-9 | `yed_validaterawtransaction` returns 13 fields: `valid, verdict, type, path, yedIn, yedOut, burned, feeZat, payee, blockValid, wouldBeRejected, mempoolExpiryOk, unconfirmedInputs`. `yed_decodepayload` returns the assignments and `opReturnIndex` | `src/rpc/yellowback.cpp:1429`, `:1468-1488`, `:1384-1426` | `:1428`, `:1372` (identical fields) | The YED half of `/verify` is one RPC. It needs a node run with `-experimentalfeatures -yellowback` (off by default: `src/experimental_features.cpp:27,41-43`; `ycash6` `:28,45`) |
| Y-10 | `sendrawtransaction`'s `allowyedburn` guard concerns only YED this node's wallet owns | `rawtransaction.cpp:1143-1153`, `src/yellowback/wallet.cpp:507-540` | `:1310-1321` | Irrelevant to a facilitator relaying a client's tx. Channel keys are never imported into the facilitator node's wallet |
| Y-11 | TRANSFER payload: magic `YB`, version `0x03`, type `0x02`, count, then count × (vout u8, cents u32 LE); the OP_RETURN may sit at any vout, exactly one, and it may not assign itself | `src/yellowback/payload.h:21-29`, `payload.cpp:404-427` | same | The SDK's payload codec mirrors `encode_transfer_v3` (`test_framework/yellowback_attest.py:360`) and YEW's `core/src/payload.rs` |
| Y-12 | Each wallet-built YED output carries `TOKEN_VALUE` = 10,000 zat of YEC (a builder convention, not a rule) | `src/yellowback/params.h:78` | same | YED channel outputs carry 2 × `TOKEN_VALUE` + the close fee in YEC |

### 3.4 Shielded payments

| # | Fact | `ycash-dd` | `ycash6` | Consequence |
|---|---|---|---|---|
| Z-1 | No RPC builds and signs a shielded tx **without broadcasting** it (`z_sendmany` broadcasts) | `src/wallet/rpcwallet.cpp:5317-5322` | `src/wallet/wallet.cpp:6633,7409,7630` (only `-walletbroadcast=0`, node-wide) | A facilitator-submitted shielded payment needs a client-side Sapling builder (X4b) |
| Z-2 | No RPC decrypts an arbitrary unmined, non-wallet tx; `z_viewtransaction` needs the tx in the wallet | `rpcwallet.cpp:3702-3761` | `rpcwallet.cpp:4792` | Recorded as N-2 |
| Z-3 | **Diversified addresses and memos are exposed**: `z_getnewdiversifiedaddress`, `z_getalldiversifiedaddresses`; `z_listreceivedbyaddress` returns amount and memo, with `minconf` 0 including the mempool | `rpcwallet.cpp:3462-3557`, `:5327-5328`, `src/wallet/rpcdump.cpp:835` | `src/rpc/common.h:140-141,191`, `rpcdump.cpp:1351-1407`, `rpcwallet.cpp:6532` | **X4a works on stock RPCs**: a fresh diversified address per request is "an instrument unique to the request" (§2.2) |
| Z-4 | Orchard is inactive on Ycash; Sapling is the shielded pool on both lines | v4.5.0 has no Orchard | `chainparams.cpp:139-147` | Private payments are Sapling, `ys1…` |
| Z-5 | Ycash's branch ids and address prefixes are in the patched librustzcash (`zcash_primitives` 0.28, `pczt` 0.6, `sapling-crypto` 0.7) | — | `src/consensus/upgrades.cpp:34-68` (Canopy `0x19bd2d2f`); `librustzcash6` `components/zcash_protocol/src/consensus.rs:770-797`, `constants/mainnet.rs:30-54` | X4b's builder can come from `librustzcash6` |

### 3.5 Network identity, pools and clients

| # | Fact | Where | Consequence |
|---|---|---|---|
| G-1 | **Ycash's genesis blocks are Zcash's**: mainnet `00040fe8…dce08`, testnet `05a60a92…a2c38`, regtest `029f11d8…e327` | `ycash-dd/src/chainparams.cpp:213,475,663` | A genesis-hash CAIP-2 reference (bip122 style) would name Zcash too. Hence X-3 |
| P-1 | `yolo` takes every `getblocktemplate` tx in order, stopping only at the size limit; it needs no flag for P2SH spends | `yolo/src/work.rs:131-139` | Pools mine x402 transactions unchanged (§4) |
| C-1 | lightwalletd exposes `GetAddressUtxos` and `SendTransaction` | `lightwalletd-dd/walletrpc/service.proto:149,173` | A light agent wallet can pay without a full node (X5) |
| C-2 | YEW's Rust core has a v4 serialiser, a ZIP-243 `sighash(index, script_code, amount, hashtype, branch_id)` for arbitrary script codes, and a TRANSFER builder | `yew/core/src/tx.rs:347,428`, `core/src/build/yed_transfer.rs`, `core/src/payload.rs:282-537` | The reference for the SDK's TypeScript signer and test vectors |

**Verdict.** Every mechanism the four phases need exists today on both lines. No row requires a
consensus change or a node change. The constraints the paper proof found are in the design:

- the YED $1 floor and burn rule (Y-3, Y-4, Y-5): channels, the dollar floor, payloads on every
  YED spend;
- the signer gap (R-7, R-8): the SDK serialises and signs;
- the missing dry run (R-4): a composite verify;
- the genesis collision (G-1): a named namespace;
- the shielded tooling gap (Z-1, Z-2): client-submitted first.

## 4. Optionality: the contract with node and pool operators (O-4)

### 4.1 What each role must do

| Role | Must do | Must never have to do |
|---|---|---|
| **Node operator** (either line) | Nothing | Set a flag, upgrade, run a sidecar, open a port. No x402 flag exists |
| **Pool operator** (`yolo`, any stratum, the internal miner) | Nothing | Change a template policy, whitelist a script, run a sidecar |
| **Merchant / facilitator operator** (opts in) | Run the x402 server and facilitator from `x402-ycash` against a node they control. For YEC (X1, X2, X4a): **any** `ycashd` of either line, stock flags. For YED (X3): a node with `-experimentalfeatures -yellowback` (Y-9) | Patch the node |
| **Agent / payer** (opts in) | Run the x402 client from `x402-ycash` with keys (local signer) or a node wallet (RPC signer) | Patch the node |

### 4.2 Why it holds

Every x402 transaction is a standard transparent v4 transaction (S-1, S-4, S-5), or a standard
Sapling transaction (X4a). Every YED one is a well-formed TRANSFER that burns nothing (Y-5).
Relay policy (R-1, Y-6) and the template filters (Y-5, P-1) therefore treat them like any wallet
payment. A node that has never heard of x402 relays and mines them. There is no new message, no
new opcode, no new RPC and no new flag.

### 4.3 How it is proven (every phase's acceptance runs this matrix)

| # | Proof | How |
|---|---|---|
| OP-1 | The devnet's **stock seat** (node 1) relays and mines X1/X2/X4a transactions | the facilitator broadcasts to a Yellowback seat; node 1 mines the block (`yellowback-devnet mine 1 1`) |
| OP-2 | **Yellowback pool seats under the default `strict` policy** mine X2/X3 transactions; a deliberately burning YED transfer is refused by the facilitator's verify before it can reach a pool | `mine N 2..4`; a negative test case |
| OP-3 | The **`yolo` stratum pool** mines them with no flag added | `up --stratum`, then `mine N <pool node>` through the stratum miner |
| OP-4 | **Both node lines**, identical scripts | the same suite against a `ycash-dd` devnet and a `ycash6` devnet (`ZCASHD=…`; the two devnet CLIs differ only in that variable) |
| OP-5 | **Zero node delta** | no commit from this plan in `ycash-dd` or `ycash6`; the suite lives in `x402-ycash` and reads `devnet.json`. Checked at each phase's close with `git log` over the plan's merge list |
| OP-6 | **Stock binaries** for the YEC phases | X1/X2 also run with the facilitator on a stock-parity build of each line (no `-yellowback`), proving YEC needs no Yellowback node at all |

### 4.4 Node asks (recorded, not scheduled)

| # | Ask | Would replace | Rule if ever built |
|---|---|---|---|
| N-1 | A read-only dry-run acceptance RPC (`testmempoolaccept` semantics: standardness, fee, finality, inputs) | the composite verify of §5.6 | `-experimentalfeatures` plus its own flag; conditional registration and an `Ensure` guard as Yellowback does (`src/rpc/yellowback.cpp:68-73,1972`). Atomic swap's pattern registers its RPCs unconditionally (`src/rpc/atomicswap.cpp:1727-1746`) and is **not** the template |
| N-2 | Decrypt an unmined raw Sapling tx with a viewing key | X4b's client-side trial decryption | same |
| N-3 | A nullifier-unspent query | X4b's settle-time double-spend discovery | same |

## 5. Design

### 5.1 Shape (X-1)

```
x402-ycash/                         boyfromcave/x402-ycash, branch main (app role)
├── specs/                          the bindings, in the Foundation's templates (upstream PR material)
│   ├── scheme_exact_ycash.md            X1 (YEC), X3 (YED ≥ $1), X4a (shielded, client-submitted)
│   └── scheme_batch_settlement_ycash.md X2 (YEC), X3 (YED)
├── packages/ycash/                 the mechanism package (later typescript/packages/mechanisms/ycash upstream)
│   ├── src/tx/                     v4 serialiser, ZIP-243 sighash, secp256k1 signing, scriptSig assembly
│   ├── src/yed/                    TRANSFER payload codec, dollar-floor rules
│   ├── src/channel/                redeem script, open / voucher / close / refund builders, channel store
│   ├── src/exact/{client,server,facilitator}/
│   ├── src/batch/{client,server,facilitator}/
│   ├── src/node/                   ycashd JSON-RPC adapter (both lines); lightwalletd adapter (X5)
│   └── src/store/                  settlement / consumption / channel stores (memory + file)
├── facilitator/                    a standalone /verify /settle /supported service (self-hostable)
├── examples/                       an Express server and an agent client per mode
└── test/{unit,integration,devnet}/ devnet = the §6 suite against yellowback-devnet, both lines
```

The node interface is stock RPC plus the read-only `yed_*` RPCs:

- **Stock, always:** `getblockchaininfo`, `getblockcount`, `gettxout`, `decoderawtransaction`,
  `signrawtransaction` (as a verifier, R-5) and `sendrawtransaction`.
- **YED:** `yed_validaterawtransaction`, `yed_decodepayload`, `yed_getprice`.
- **X4a:** `z_getnewdiversifiedaddress`, `z_listreceivedbyaddress`.
- **The client's RPC signer:** `listunspent`, `createrawtransaction`, `signrawtransaction`.

The facilitator never calls a `yed_*` writer.

Size: `@x402/cardano` is 15.8k lines, of which about 3.6k are Masumi-specific. Without Masumi
and script support it is about 4–5k lines of source and 3–4k of tests, and Ycash's package should
land in that range across X1–X3.

### 5.2 Language (X-2)

**TypeScript, recommended.** Reasons:

- The reference SDK has the most mechanisms and the most complete core: every chain, including
  Cardano, ships there first.
- The Foundation's PR 2 must be "a reference implementation in a single SDK"
  (CONTRIBUTING.md:225-270), and TypeScript is where reviewers look.
- The plugin interfaces are small: `SchemeNetworkClient`, `SchemeNetworkServer` and
  `SchemeNetworkFacilitator` in `typescript/packages/core/src/types/mechanisms.ts:90,113,246`,
  registered with `x402Client.register`, `x402ResourceServer.register` and
  `x402Facilitator.register`.

Cryptography comes from `@noble/secp256k1` and `@noble/hashes` (BLAKE2b for ZIP-243). The
serialiser is about 400 lines, ported from YEW's `tx.rs`, with test vectors cross-checked against
`signrawtransaction` on both lines.

**Go, the alternative.** It is an x402 SDK too (`go/interfaces.go:87,232,301`), lightwalletd-dd
is Go, and it compiles to one binary. But Go has only the EVM and SVM mechanisms upstream, so we
would be first, and reviewers would see a less familiar layout. Recorded, not recommended.

**X4b's Sapling builder** is Rust in any case (`librustzcash6`), exposed to TypeScript through
WASM or a small N-API addon; that cost is one reason X4b waits for an owner go (X-8).

### 5.3 Network ids and assets (X-3, X-4)

| `network` | Node | `asset` values | `amount` unit |
|---|---|---|---|
| `ycash:mainnet` | either line, mainnet | `YEC`, `YED` (YED from Yellowback mainnet `startHeight` 3,075,000) | zatoshi / cent |
| `ycash:testnet` | either line, testnet | `YEC` (`YED` once testnet has a `startHeight`) | zatoshi / cent |
| `ycash:regtest` | the devnet | `YEC`, `YED` | zatoshi / cent |

`payTo` is an `s1…` address (transparent YEC; mainnet P2PKH, version `1C 28`; testnet and regtest share `1C 95`, `sm…`, so the network always comes from `network`, never from the address, X-F1), a `ye…` address (YED, P2PKH), or a `ys1…`
diversified address (X4a). The facilitator rejects a `network` whose node reports a different
chain (`getblockchaininfo.chain`), and the client checks the same against its own node.

The node line is not part of the network id. Both lines are the same network, and a payment
built on one validates on the other (v4 transactions, the same branch id).

### 5.4 Fees (X-5)

The payer funds the fee inside the signed transaction. Every binding declares
`extra.areFeesSponsored: false`, as Cardano and XRPL do. The fee floor the facilitator checks and
the SDK pays is the S-6 rule, max(1000, 500 × max(2, logical actions)). It satisfies v4.5.0's
wallet minimum and avoids 6.21.0's ZIP-401 eviction penalty. A sponsored method (the client signs
`ALL|ANYONECANPAY`, R-9, and the facilitator adds an input sized exactly to the fee, since it
cannot add change) would be a second `assetTransferMethod`. It is not scheduled.

### 5.5 Confirmation policy (X-6)

`extra.confirmationPolicy.confirmations`, an integer from −1 to 20, as in Cardano:

| Value | Meaning |
|---|---|
| −1 | accepted into the facilitator node's mempool |
| 0 | included in a block |
| N | N confirmations |

The facilitator's `/supported` advertises its `{minimum, maximum}`. Under the `authorization`
flow the server responds only after settle, so each confirmation adds about 75 s to the agent's
response. The default is therefore −1 for an `exact` payment up to a server cap (configurable;
suggested $1 equivalent), and 1 above it. `settlement_pending` carrying the txid is returned when
the wanted depth is not reached in `maxTimeoutSeconds`; the facilitator never rebroadcasts on a
retried `/settle`.

Zero-confirmation risk: a payer could double-spend its own inputs after the handler ran. The
facilitator detects a conflicting mempool spend (R-6), and the server bounds its exposure with
the cap. X1 records whether either line relays replacements (expected: neither implements
replace-by-fee; verified in X1, not assumed).

### 5.6 Binding X1 — `exact`, transparent YEC (facilitator-submitted)

**Requirements** (one `accepts[]` entry):

```json
{ "scheme": "exact", "network": "ycash:mainnet", "asset": "YEC",
  "amount": "250000", "payTo": "s1…", "maxTimeoutSeconds": 300,
  "extra": { "assetTransferMethod": "transparent", "areFeesSponsored": false,
             "confirmationPolicy": { "confirmations": -1 } } }
```

**Payload:** `{ "transaction": "<hex, complete signed v4 tx>" }`.

**Client.** It selects confirmed UTXOs and builds a v4 tx: one output of exactly `amount` to
`payTo`, change to itself, the fee from §5.4. It sets `nLockTime = 0`,
`nExpiryHeight = tip + 3 + ⌈maxTimeoutSeconds / 75⌉`, and signs `SIGHASH_ALL` at the current
branch id (read from `getblockchaininfo` or lightwalletd `GetLightdInfo`). It does not broadcast.
There are two signer backends:

- the **RPC signer** (`listunspent` + `createrawtransaction` with expiry + `signrawtransaction`,
  both lines);
- the **local signer** (keys in the agent; the SDK's ZIP-243 code).

**Family declarations (`scheme_exact.md:26-42`):**

- **Fee payer:** the payer.
- **Replay primitive:** the transaction's input outpoints. They are exclusive to the payment
  unless the payer's wallet spends the same coins elsewhere. Unrelated payer activity can
  therefore invalidate a payment after the handler ran; the facilitator's mempool check (R-6)
  narrows that to a race. There is no limit on concurrent payments beyond the payer's coin count.
- **Validity window:** bounded by `nExpiryHeight` (R-2). An expiry of 0 is refused.
- **Duplicate submission:** indistinguishable (R-3). The facilitator deduplicates by txid
  atomically across every `/settle` process and keeps the key until `nExpiryHeight` has passed
  plus 10 blocks.

**`/verify`** (read-only, in order):

1. Version, scheme, network and `accepted` all match the requirements.
2. Decode: v4 with the Sapling version group, no shielded or JoinSplit components (this binding
   is transparent), `nLockTime` 0.
3. Exactly one output pays `payTo`, and it is worth exactly `amount`.
4. For every input: `gettxout(…, false)` finds it (confirmed and unspent), and
   `gettxout(…, true)` still finds it (no conflicting mempool spend).
5. Fee = Σ inputs − Σ outputs ≥ the §5.4 floor, and ≤ a sanity cap.
6. tip + 4 ≤ `nExpiryHeight` ≤ tip + 4 + ⌈maxTimeoutSeconds / 75⌉ + 1.
7. Scripts: `signrawtransaction hex [] []` returns `complete: true` (R-5).
8. On a Yellowback node, additionally `yed_validaterawtransaction` has `yedIn == 0`. A YEC
   payment must not spend a YED-bearing coin, which would burn the payer's YED (Y-4). This check
   is unavailable on a stock node; the client-side guard is the SDK's coin selection, which skips
   token outputs when it has a Yellowback node or lightwalletd `GetAddressTokens`.
9. The txid is not already claimed.

**`/settle`:** claim the txid atomically, then `sendrawtransaction`, then wait for the policy depth
with `gettxout(txid, vout_payTo, true)`. Return `{success, transaction: txid, network, payer:
<address of input 0>, extra: {status, confirmations}}`.

**Errors** use the core codes and the `invalid_exact_ycash_*` family: `_amount_mismatch`,
`_recipient_mismatch`, `_input_spent`, `_fee_too_low`, `_expiry`, `_script`, `_yed_input`,
`_duplicate`.

### 5.7 Binding X2 — `batch-settlement`, YEC payment channel

**Channel script** (P2SH; client key C, server key S, refund height t < 500,000,000):

```
OP_IF   OP_2 <C> <S> OP_2 OP_CHECKMULTISIG
OP_ELSE <t> OP_CHECKLOCKTIMEVERIFY OP_DROP <C> OP_CHECKSIG
OP_ENDIF
```

| Spend | scriptSig | Who | When |
|---|---|---|---|
| close (voucher) | `OP_0 <sigC> <sigS> OP_1 <redeemScript>` | server completes a client-signed voucher | any time before t |
| refund | `<sigC> OP_0 <redeemScript>`, `nLockTime ≥ t`, `nSequence` non-final | client alone | after t |

The script has 3 sigops and is standard (S-1). The refund is a script branch, not a pre-signed
transaction, so malleability and CSV are irrelevant (S-3). Both scriptSigs are assembled by the
SDK (R-8).

**Requirements `extra`:**

- `serverPubKey` (S);
- `minLockBlocks` (default 1152, about 24 h);
- `closeMarginBlocks` (default 96, about 2 h);
- `maxDeposit`;
- `pricePerRequest` (the batch-settlement `amount`, a ceiling);
- `confirmationPolicy` for the funding transaction.

**Payload types:**

- **`open`**: `{fundingTx: <hex, client-signed>, vout, redeemScript, firstVoucher}`.
  - The server verifies:
    - the P2SH matches the redeem script;
    - S is its own key;
    - t ≥ tip + `minLockBlocks`;
    - the deposit is ≤ `maxDeposit`;
    - the fee floor is met;
    - the funding tx is valid (as in §5.6, steps 2, 4, 5 and 7).
  - It relays the funding tx (or the client already has). Vouchers are accepted once the funding
    tx reaches the policy depth.
- **`voucher`**: `{channelId: "txid:vout", tx: <hex>, cumulative}`.
  - `tx` spends the channel outpoint only, with `nLockTime 0`, `nExpiryHeight 0` (a voucher must
    not expire before t) and outputs `payTo = cumulative` and client change = D − cumulative −
    closeFee.
  - The client signs `SIGHASH_ALL` and leaves its signature in the scriptSig skeleton.

**Server verification** (per voucher):

1. The channel is known and open.
2. tip < t − `closeMarginBlocks`.
3. The funding output is still unspent (R-6).
4. The outputs are exactly as above.
5. charged + `amount` ≤ cumulative ≤ D (EVM/SVM form; X-F16), with compare-and-set on the
   stored cumulative.
6. The client's signature is valid.
7. Completed locally with the server's signature, the tx passes `signrawtransaction hex [] []`.
8. Compare-and-set on the stored cumulative.

**The seven batch-settlement answers:**

| # | Requirement | Ycash answer |
|---|---|---|
| 1 | Commitment format | the client-signed voucher tx above |
| 2 | Verification | the eight steps above |
| 3 | Storage | the latest voucher per channel; commitment identifier `"<channelId>@<cumulative>"` |
| 4 | Double-spend | all vouchers spend one outpoint, so only one can be mined; the server only broadcasts its highest; one in-flight voucher per channel |
| 5 | Expiry | every voucher is good until t; after t the client can refund |
| 6 | Redemption | the server completes and broadcasts the latest voucher when the session idles, at tip ≥ t − `closeMarginBlocks`, at cumulative = D, or on its own schedule |
| 7 | Trust model | capital-backed: the deposit in the channel output |

**What it cannot match** (EVM/SVM extras, not generic requirements): top-up into the same channel
(open a new one), partial cooperative refund with reuse, and facilitator-sponsored rent.

**Client tooling:**

- `channel open|status|refund`;
- a watcher that warns at t − `closeMarginBlocks`;
- the refund builder.

The funding fee and the close fee are both paid by the client: the close fee is reserved inside
the channel output (X-5).

### 5.8 Binding X3 — YED channels, and YED per request at ≥ $1

**YED `exact` (≥ $1).** This is §5.6 with:

- `asset: "YED"`, `amount` in cents (≥ 100);
- `payTo` a `ye…` address;
- the payload a TRANSFER assigning `amount` to the `payTo` vout and the remainder to change, with
  YEC inputs for the fee.

`/verify` replaces step 3 with:

- `yed_decodepayload` shows exactly one assignment to the `payTo` vout, of `amount` cents;
- `yed_validaterawtransaction` reports `valid`, `verdict` OK (never `BURNED`), `burned` 0 and
  `unconfirmedInputs` empty.

It needs a Yellowback node (Y-9).

**YED channel.** This is §5.7 with these changes:

- **Funding:** a TRANSFER that assigns D cents to the P2SH vout. The SDK builds it, since there
  is no P2SH `ye…` address (Y-8). The channel output's YEC value is 2 × `TOKEN_VALUE` + the close
  fee (Y-12).
- **Voucher:** carries a TRANSFER payload assigning `cumulative` to the server's vout and D −
  cumulative to the client's vout, so **yedOut = yedIn = D** (Y-5).
- **Dollar floor (X-7):**
  - cumulative ≥ 100 cents, from the first voucher on. The first voucher pre-pays up to $1 that
    later requests consume; the server keeps a charged total under the voucher's cumulative.
  - D − cumulative is 0 or ≥ 100.
  - If the client's remainder would fall in (0, 100), the voucher assigns all of D to the server.
    The client's wallet sizes D to keep that rare.
- **Refund:** the CLTV branch with a TRANSFER assigning all of D to the client, never a bare
  spend (Y-4).
- **Verify adds:** `yed_validaterawtransaction` on the completed voucher (OK, burned 0,
  yedIn = D) and `yed_decodepayload` matching the two assignments exactly.

Yellowback's halts affect mints only, never transfers (`yellowback-v2-development-plan.md`, the
halts rule), so channels keep working through a halt.

### 5.9 Binding X4 — private payments

**X4a — `exact`, shielded YEC, client-submitted (payment proof), `upfront` (X-8).**

- **Requirements:** `asset: "YEC"`, `payTo` = a fresh diversified `ys1…` address
  (`z_getnewdiversifiedaddress` on the merchant's wallet, one per request).
  `extra = {paymentFlow: "upfront", assetTransferMethod: "sapling-proof", memo: "x402:" +
  <request hash>, confirmationPolicy}`.
- **Client:** any wallet that sends to a `ys1…` address with a memo: `z_sendmany` on either line,
  YecWallet, YecLite.
- **Payload:** `{ "txid": "…" }`.
- **Settle:** `z_listreceivedbyaddress(payTo, minconf)`: Σ amount ≥ `amount`, memo matches,
  depth meets policy. Then atomically consume `ycash:<net>:<txid>`.
- **Price in dollars:** the server quotes the YEC amount from `yed_getprice` (Yellowback's
  attested price) or a configured source, fixed for `maxTimeoutSeconds`.

Client-submitted checklist (`scheme_exact.md:44-56`):

- **Instrument and proof:** the diversified address in `payTo` plus the validity window; the txid
  in the payload.
- **Request binding:** an instrument unique to the request (the address), plus a payee
  commitment in the memo.
- **Single-use claim:** atomic, on `ycash:<net>:<txid>`.
- **Retention:** until the address is retired. An address is never reissued.
- **Amount acceptance:** underpayment is rejected and left at the merchant's address, refunded
  only manually; overpayment is accepted and kept. Both are declared.
- **Finality:** the policy depth, owned by the server. Below it, settle returns an error naming
  the depth and holds no claim.
- **Failure disposition:** none automatic; the client must not assume a return path.

**Privacy:** on chain, a payment from a shielded source reveals neither payer, payee nor amount.
The merchant learns the amount and the memo.

**X4b — `exact`, shielded YEC, facilitator-submitted, `authorization`** (only on an owner go).

- The client builds and signs a full Sapling v4 tx with a Rust builder from `librustzcash6` (Z-5)
  and does not broadcast it.
- The merchant's facilitator trial-decrypts the payment output with its incoming viewing key,
  checks value and memo, and broadcasts it after the handler.
- Replay primitive: nullifiers. Validity window: `nExpiryHeight`.
- **Known gap:** `/verify` cannot check that the nullifiers are unspent without N-3, so a
  double-spent payment surfaces only at settle, after the handler ran. This is declared, as the
  spec requires for shared replay primitives.

### 5.10 The shielded scanning problem: trial decryption, view keys, selective disclosure (X-8)

A Sapling output says nothing about its recipient in the clear. A wallet finds its own notes by
**trial-decrypting every shielded output** in every block (and in the mempool, for zero
confirmations) with its incoming viewing key (ivk). That is the cost of privacy, and it falls in
different places in the two variants:

| Who | X4a (client-submitted) | X4b (facilitator-submitted) | Cost and mitigation |
|---|---|---|---|
| **Merchant** (receiver) | Its node wallet already trial-decrypts every Sapling output as blocks connect; `z_listreceivedbyaddress` reads the result | Trial-decrypts **one** transaction per payment, the one the client hands it (cheap) | **Diversified addresses do not multiply the cost.** Every `ys1…` from `z_getnewdiversifiedaddress` belongs to one key, so it is one trial decryption per output however many per-request addresses exist. The cost is linear in chain shielded volume, which is low on Ycash. X4-M measures it |
| **Agent** (payer) | Must know its own spendable notes: a full-node wallet (scans as blocks connect) or a light wallet scanning compact blocks through lightwalletd (YEW does not do Sapling; C-2) | Same, plus a Rust builder | **The likely short-run blocker.** Agents want stateless keys and an instant start, and a shielded wallet needs a synced note set. Tiered fallback below |
| **Facilitator as a service** (third party) | Must hold the merchant's viewing key to check receipt, and so **learns every incoming payment to that key** | Same (it needs the ivk to decrypt the output) | **Self-hosted only** for private payments; a hosted facilitator is offered for transparent methods only. A merchant that must delegate uses a **dedicated key for x402 revenue**, so the viewing key reveals that revenue and nothing else |

**View keys.** Both lines export and import Sapling viewing keys (`z_exportviewingkey`,
`z_importviewingkey`). A full viewing key reveals incoming *and* outgoing notes; an incoming key
reveals incoming only. The plan never sends a spending key off the merchant's machine. If a
viewing key is shared, it is an incoming key for the dedicated x402 key.

**Selective disclosure.** Proving one payment to a third party (an auditor, a dispute) without
handing over a viewing key:

- **On chain:** Zcash's payment-disclosure RPCs were built for Sprout JoinSplits, and Ycash
  4.5.0 carries that code (`src/wallet/paymentdisclosuredb.h`, used by
  `asyncrpcoperation_mergetoaddress.cpp`). Whether either line can disclose a single **Sapling**
  output (for example from the sender's outgoing viewing key, or by revealing that output's
  `rcm`) is an X4-M research item. It is not assumed.
- **Off chain, available now:** x402's `offer-and-receipt` extension
  (`specs/extensions/extension-offer-and-receipt.md`). The merchant signs a JWS receipt naming
  the network, txid, amount and resource. The agent keeps it, and it proves payment to anyone
  who trusts the merchant's key, with nothing revealed on chain. X4a emits these receipts.

**Tiered privacy**, so the blocker does not stop the feature:

| Tier | Payer source | Revealed on chain | Agent needs |
|---|---|---|---|
| P0 | transparent `s1…` → merchant `ys1…` (t→z) | payer and the amount entering the pool; **not the payee** | no shielded wallet (stateless keys work) |
| P1 | shielded `ys1…` → merchant `ys1…` (z→z) | nothing | a synced shielded wallet (node or light) |
| P2 | X4b, z→z, verified before broadcast | nothing | P1 plus the Rust builder |

X4a ships P0 and P1. The X4-M gate decides whether P1 is practical for agents now and whether
X4b is worth building.

## 6. Both node lines (O-3)

### 6.1 What is the same

On both lines:

- the transaction format (v4, ZIP-243);
- relay standardness (S-1..S-5);
- CLTV (S-2);
- the overlay rules and RPCs the facilitator reads (Y-1..Y-12, with identical
  `yed_validaterawtransaction` fields);
- the diversified-address and memo RPCs (Z-3);
- the devnet CLI (`contrib/yellowback/devnet/yellowback-devnet`, 1856 lines on both lines, which
  differ only in `BITCOIND` → `ZCASHD`);
- `yolo`.

One SDK build serves both lines with no line switch.

### 6.2 What differs, and how the SDK copes

| Area | `ycash-dd` 4.5.0 | `ycash6` 6.21.0 | SDK rule |
|---|---|---|---|
| Fee rule | `DEFAULT_FEE` 1000 | ZIP-317 conventional, ZIP-401 eviction penalty | max(1000, conventional) on both (S-6) |
| Raw-tx RPC deprecation | none | allowed by default, never disabled by `-allowdeprecated=none` for create/sign (`src/deprecation.cpp:14-32`) | the RPC signer works on both; the local signer needs no RPC |
| Expiry cap | — | capped at the next activation height − 1 | irrelevant while NU5 has none; the client still reads `nextblock` from the node |
| `decoderawtransaction` | — | adds `authdigest` | ignored |
| Atomic-swap qa test | `qa/rpc-tests/atomicswap.py` | none | no dependency |

### 6.3 Where it runs

- **Regtest devnet of each line** (the proof of record).
- **Mainnet**, small amounts, owner-run (X6). YED on mainnet waits for `startHeight` 3,075,000 on
  both lines. The tip was 3,052,055 on 2026-10-02, about 20 days at 75 s blocks, so around
  2026-10-22.
- **Testnet** when it is reachable again (X-11).

The upstream e2e suite expects a testnet RPC URL (`e2e/README.md`, `config/mechanisms_<id>.json`).
Until Ycash testnet has seeds, our e2e config points at a regtest devnet, and the upstream PR
says so (§8).

## 7. Phases

Every phase ends with the §4.3 optionality matrix on both lines. Agents work in their own
worktrees of `x402-ycash`. No node repository is edited.

### 7.0 Execution model

The coordinator (the main session) splits each phase into chunks and delegates them to parallel
subagents:

- **Worktree:** each agent gets `wt/x402-<chunk>`, a `git -C x402-ycash worktree add` on branch
  `x402/<chunk>` from `main`.
- **Shared briefing:** `wt/BRIEFING-x402.md`, durable across sessions. It covers the rules, ports,
  the node binaries and the report format.
- **Port seeds:** each agent has its own devnet port seed, a few apart from every other agent's
  (chain-viz finding C-F31).
- **Agents never** edit `x402-ycash`'s main tree, a node repository or `ref/`.
- **The coordinator** merges `x402/*` into `main`, runs the unit tests and the devnet suites on
  both lines, pushes, and ticks the boxes here.

Chunks that share no files run at the same time. The dependency order is: X0 scaffold → {X1
`tx` core, X1 node adapter and devnet harness, spec drafts} in parallel → X1 mechanisms → X2 →
X3; X4a can start after the node adapter.

| Phase | What | Size |
|---|---|---|
| X0 | workspace plumbing and spec drafts | S |
| X1 | YEC pay-per-request | L (it carries the shared core) |
| X2 | YEC payment channels | M |
| X3 | YED channels and YED ≥ $1 per request | M |
| X4 | private payments (X4a; X4b on a go) | S (X4a) / L (X4b) |
| X5 | upstream and ecosystem | M |
| X6 | mainnet | S, owner-run |

### X0 — workspace plumbing and spec drafts

- [x] Owner creates the GitHub repo `boyfromcave/x402-ycash` (done 2026-10-03, README only). We
      push over SSH with the per-repo `core.sshCommand`.
- [x] `repos.yaml` entry (role `app`, branch `main`, beside `yolo` and `chain-viz` at
      `repos.yaml:130-140`).
- [x] `Makefile` per-app variable, its `export` line and the help text (`Makefile:24-44`).
- [x] `AGENTS.md` layout block and app prose (§2 rule list).
- [x] `README.md` components, layout, bootstrap and pins tables.
- [x] `yellowback.code-workspace` folder.
- [x] `docs/plans/README.md` row (revision 1).
- [x] `docs/mapping.md` §20 (revision 1).
- [x] `wt/BRIEFING-x402.md`, the agents' briefing (§7.0).
- [x] Scaffold: TypeScript workspace, `@x402/core` v2 pinned, lint and test (vitest, as the
      Cardano package uses), CI on GitHub Actions.
- [x] `specs/scheme_exact_ycash.md` and `specs/scheme_batch_settlement_ycash.md`, drafted from
      §5 in the Foundation's templates (`x402-ycash` `81feec5`, merged `1c27b7c`).
- [ ] **Acceptance:** `make status` lists the seventh app repo clean. Both spec drafts answer
      every item of §2.2 with no "TBD".

### X1 — YEC pay-per-request (`exact`, transparent)

- [x] `src/tx`: v4 serialiser and parser, ZIP-243 sighash, signing. Test vectors are generated
      from `signrawtransaction` on **both** lines and from YEW's `tx.rs`, and committed as
      language-neutral `vectors/*.json` (X-2).
- [x] `src/node`: the JSON-RPC adapter (cookie or user/password auth). It reads `devnet.json`,
      stripping userinfo and sending UTF-8 basic auth (chain-viz finding C-F1).
- [x] The exact client (RPC signer and local signer), server (`parsePrice` in YEC or in USD
      through a price source) and facilitator (§5.6 verify and settle, the txid store).
- [x] The standalone facilitator service: `/verify`, `/settle` and `/supported` (with `signers`
      empty, since there is no sponsorship).
- [x] An Express example server, and an agent client that pays N requests.
- [x] Devnet suite `test/devnet/exact_yec.test.ts`:
  - [ ] happy path at −1, 0 and 1 confirmations;
  - [ ] wrong amount, wrong recipient, spent input, a conflicting mempool spend, low fee, expiry
        out of window, bad signature;
  - [ ] the same tx presented twice (one resource, `duplicate`);
  - [ ] a YED-bearing input on a Yellowback node (refused);
  - [ ] `settlement_pending` when blocks stop;
  - [ ] whether either line accepts a replacement (records the R-6 race).
- [ ] **Acceptance:** green against a `ycash-dd` devnet **and** a `ycash6` devnet, plus OP-1,
      OP-3, OP-4, OP-5 and OP-6 (facilitator on a stock-parity build of each line). Record
      latency per confirmation policy.

### X2 — YEC payment channels (`batch-settlement`)

- [x] `src/channel`: the redeem script, the open, voucher, close and refund builders, scriptSig
      assembly (R-8), and the channel store with compare-and-set cumulative.
- [x] batch-settlement client, server and facilitator (§5.7): `open` and `voucher` payloads, the
      close triggers, the watcher.
- [x] Client CLI: `channel open|status|refund`.
- [x] Devnet suite `test/devnet/channel_yec.test.ts`:
  - [ ] open, then 1,000 paid requests, then a close: one on-chain close carries the total, and
        the server's balance equals Σ charges;
  - [ ] dynamic pricing below the ceiling;
  - [ ] a stale or lower voucher (refused);
  - [ ] a voucher at the margin (refused, close triggered);
  - [ ] the client refund after t;
  - [ ] the server closes before t − margin under a mined-block schedule;
  - [ ] a funding tx at 0 confirmations (server opt-in) and at 1.
- [ ] **Acceptance:** green on both lines, plus OP-1, OP-3, OP-4, OP-5 and OP-6. Record the
      chain cost (two transactions) against N `exact` payments.

### X3 — YED channels, and YED per request at ≥ $1

- [x] `src/yed`: the TRANSFER codec (cross-checked against `encode_transfer_v3` and YEW
      `payload.rs`) and the dollar-floor rules (X-7).
- [x] The YED `exact` method (§5.8), which requires a Yellowback node.
- [x] The YED channel: TRANSFER funding to P2SH, payload vouchers, and a refund with payload.
- [x] Devnet suite `test/devnet/yed.test.ts`:
  - [ ] YED `exact` at $1 and $25;
  - [ ] YED `exact` at $0.50 (refused: the burn guard);
  - [ ] a channel at D = $20 with $0.01 requests (first voucher at $1.00, remainder rule at the
        end);
  - [ ] refund with payload (YED back to the client, nothing burned: `yed_getstats` supply
        unchanged);
  - [ ] a hand-built burning voucher (refused by verify; mined only if forced through a stock
        seat, so the burn is visible in `yed_getstats`).
- [ ] **Acceptance:** green on both lines, plus OP-2 (Yellowback pools under `strict`), OP-3,
      OP-4 and OP-5. Yellowback supply is unchanged across every non-burning test case.

### X4 — private payments

- [x] **X4-M, the measurement gate (§5.10):**
  - [x] Merchant scan cost: the node wallet's block-connect time with and without a Sapling key,
        on the devnet and replayed over mainnet's shielded volume.
  - [x] Agent sync cost: a full-node wallet versus lightwalletd compact-block scanning (YecLite's
        path).
  - [x] Whether either line can disclose a single Sapling output (selective disclosure).
  - [x] Whether a viewing-key-only wallet can issue diversified addresses and see mempool
        receipts.
  - [x] Written verdict: P1 practical for agents now or later, and whether X4b is worth building.
- [x] **X4a:** the client-submitted shielded method (§5.9): per-request diversified addresses,
      the memo binding, the consumption store, the price quote from `yed_getprice`.
- [x] Verify on both lines that `z_getnewdiversifiedaddress` works on the merchant's wallet type
      (spending key; record whether a viewing-key-only wallet can issue one).
- [x] Devnet suite `test/devnet/shielded.test.ts`:
  - [ ] a payment from a `ys1…` source at 0 and 1 confirmations;
  - [ ] underpayment, overpayment, a wrong memo, the same txid on two requests (one resource);
  - [ ] a payment from an `s1…` source (works; the sender is public);
  - [ ] chain-level check: the payment tx shows no transparent output to the merchant.
- [x] X4a emits `offer-and-receipt` JWS receipts (off-chain selective disclosure, §5.10).
- [ ] **X4a acceptance:** green on both lines, plus OP-1 and OP-4; tiers P0 and P1 both
      exercised.
- [x] **X4-M verdict (`x402-ycash` `docs/x4m-measurements.md`, Verdict):** P1 is practical **now for agents with a full-node wallet** (restart to a payment the merchant sees: 2.8 s on v4.5.0, 6.9 s on 6.21.0; mainnet sync a few hours); stateless agents use **P0** for now; P1 through a light wallet is cheap in bandwidth and CPU (122 B per output, ~121 KB a day on mainnet; 66.6 µs per output trial decryption on one core) but **no Ycash Sapling light client for agents exists yet**. Merchant defaults: one dedicated Sapling key; addresses issued **offline from the viewing key** (index range from 2^40, disjoint from both lines' wallet walks); a settlement node holding only the viewing key; self-hosted facilitator; JWS receipts for disclosure.
- [x] **X4b go/no-go (owner): GO, 2026-10-04** — the owner directed "ship shielded Sapling x402" and build the agent light client now (N-A). Phase X4b below. The earlier recommendation was: **no-go for now**. X4b does not remove the agent sync blocker; build it together with the agent light client (N-A), which needs the same Sapling builder and prover. N-asks from X4-M: N-A agent light client from `librustzcash6` (the main one); N-B `chainMetadata`/`GetSubtreeRoots` in lightwalletd-dd; N-C a node RPC to issue addresses from a viewing key or an incoming-viewing-key import; N-D Sapling payment disclosure (ZIP-311); plus N-3 and a published bootstrap snapshot (operational). the Rust builder from `librustzcash6` (WASM or N-API),
      facilitator trial decryption, the nullifier-gap declaration. On a go, X4b gets its own
      chunk list in revision 2.

### X4b — the agent light client and the facilitator-submitted `sapling` method (owner go 2026-10-04)

Execution: chunks `lightcore` (Rust light client), `lwdnext` (lightwalletd-dd), `x4bspec` (spec + TS
primitives), `zwallet` (research), `saplingwire` (service, merchant, agent, Python, vectors), then the
end-to-end proof. The light client also becomes the engine of the YEW shielded plan
(`yew-shielded-plan.md`, S1 library split).

- [x] **lightwalletd-dd `GetChainInfo`** (next-block branch id, X-F71) on `YellowbackStreamer`; `GetTreeState` at arbitrary heights and `GetMempoolTx` Sapling-only pinned on both lines; no `GetSubtreeRoots` on Ycash (`z_getsubtreesbyindex` absent on 4.5.0). lightwalletd-dd `0b3448e`, pushed 2026-10-04. Mapping §20.1.
- [x] **zwallet (YWallet) sync-core study**: stay on librustzcash6, adopt download/scan overlap, birthday `GetTreeState` bootstrap, checkpoint reorg (`x402-ycash/docs/zwallet-comparison.md`, 2026-10-04).
- [x] **`sapling` method specified** (`specs/scheme_exact_ycash.md`: 11 verify rules, nullifier gap N-3 declared, ZIP-212 0x02 required, payTo exact match) and **pure-TS Sapling trial decryption + note commitment** proven against the Zcash test vectors; `SaplingExactFacilitator`, `ShieldedMethodRouter` (`x402-ycash` `272de75`, 2026-10-04).
- [ ] **Rust light client `x402-light`** (`x402-ycash/light`): compact-block sync from lightwalletd-dd, `zcash_client_sqlite` store, build+prove+sign without broadcast, JSON-RPC on loopback; devnet proof on both lines (chunk `lightcore`, in flight).
- [ ] `sapling` wired into the facilitator service (opt-in; refused on mainnet without an explicit flag), merchant route, agent/CLI builder contract, Python parity; Sapling devnet vectors on both lines; facilitator-side end to end on node-wallet-built transactions (chunk `saplingwire`, in flight).
- [ ] Library split `light/core` (shared with YEW, S1).
- [ ] End to end on both lines: an agent with only a spending key and a lightwalletd URL pays a `sapling` requirement (authorization flow) and a `sapling-proof` requirement from the light client; receipts verify.
- [ ] Regression of record updated; upstream staging refreshed with the `sapling` method; mainnet runbook: `sapling` stays opt-in until the proof is on mainnet.

### X5 — upstream and ecosystem

- [x] **Staged locally, not published** (`x402-ycash` `d20419a`, `docs/upstream.md`, `tools/upstream/stage.sh`): PR 1 (specs) and PR 2 (`typescript/packages/mechanisms/ycash` as `@x402/ycash`, e2e config, examples, changeset) on a remote-less fork at `wt/scratch/x402-upstream-prep/x402-fork`; drafted issue and PR bodies and the owner's decisions in `PUBLISHING.md` there (licence MIT vs Apache-2.0, signed commits, account, PR 1 scope, CODEOWNERS). All ten upstream checks pass at `3940e56` (fork `ycash-spec` `c93dcb49`, `ycash-binding` `778e1e24`). Discussions are disabled upstream, so the proposal is a Feature Proposal issue. Original item: Open a GitHub discussion at `x402-foundation/x402`, then **PR 1**: `scheme_exact_ycash.md`
      (after X1). Then `scheme_batch_settlement_ycash.md` (after X3).
- [ ] **PR 2:** `typescript/packages/mechanisms/ycash` with unit, integration and e2e tests
      (`config/mechanisms_ycash.json`, client, server and facilitator registration), the
      `all_networks` example entries, signed commits and changesets (CONTRIBUTING.md:151-270).
- [x] **Python backend SDK (X-2), first cut (`x402-ycash` `d6d6643`):** `python/x402_ycash` (tx, yed, node, store incl. SQLite, `exact` facilitator/server/client, channel builders), 233 tests, every vector reproduced, TS ↔ Python interop green on both lines; **parity reached** in `46cb366`: YED exact, `sapling-proof` (receipts byte-identical to TS, `vectors/shielded`), batch-settlement YEC and YED; 310 Python tests; TS ↔ Python interop 8/8 on both lines. Python clients (agents) are still TS-only. Original item: `python/x402/mechanisms/ycash` in the upstream layout
      (`python/x402/interfaces.py` protocols, `register` in `client_base.py`, `server_base.py`,
      `facilitator_base.py`). Facilitator and server first, which is what backends run. It must
      reproduce every `vectors/*.json` result, and the workspace `.venv` is used for development.
- [x] lightwalletd adapter for light agent wallets (`x402-ycash` merge of `x402/lwd`: agents pay with only a WIF key and a lightwalletd URL — YEC/YED exact, channels, refunds via `SendTransaction`; devnet 5/5 on both lines). Original item: (UTXOs, broadcast, token lookup via
      `GetAddressTokens`; C-1).
- [ ] x402-gated services around the node, each a small addendum to its own plan: a paid
      chain-viz API, paid lightwalletd tiers, a paid `yed_*` MCP server for keeper and vault
      agents (MCP transport, `_meta["x402/payment"]`). Bazaar listing for each.
- [ ] chain-viz: a classifier entry for x402 channel transactions (`chain-viz/src/classify.rs`;
      optional, the chain-viz repo).

### X6 — mainnet (owner-run)

- [x] **Runbook and capped smoke script ready** (`docs/mainnet-runbook.md`, `tools/mainnet/smoke.sh`: hard caps 0.01 YEC per payment, 0.1 YEC deposit, 50 requests; `--i-understand-this-spends-real-yec` required); rehearsed on regtest devnets of **both** lines (`add0578`).
- [ ] YEC `exact` and a YEC channel, small amounts, with the facilitator on each line's mainnet
      build.
- [ ] YED once `startHeight` 3,075,000 is passed.
- [ ] X4a.
- [ ] A one-page operator note for merchants: what to run, which node flags (none for YEC;
      `-experimentalfeatures -yellowback` for YED), key handling (channel keys never in the node
      wallet).

## 8. Risks and what was given up

| Risk / trade | Disposition |
|---|---|
| Zero-confirmation `exact` can be double-spent by the payer after the handler ran | Server cap (X-6), mempool conflict check (R-6); channels for volume |
| 75 s blocks make confirmation-based settlement slow | Default −1 for small amounts; channels amortise one confirmation over a session |
| YED cannot pay below $1 per transaction (Y-3) | Channels with the dollar floor; a remainder under $1 goes to the server (X-7) |
| A malformed YED transaction burns the payer's YED (Y-3, Y-4) | The SDK builds every YED tx; verify refuses `BURNED`; `strict` pools skip burns (Y-5) |
| No pull primitive and no sponsorship (X-5) | Payer-funded, as Cardano and XRPL; sponsorship recorded |
| `upto` not bound (§2.2) | Metered pricing through `batch-settlement` |
| Channel extras of EVM/SVM (top-up, partial refund, sponsored rent) | Open a new channel |
| No testnet for the upstream e2e suite | Regtest config in our repo; the PR states it; revisit when testnet has seeds |
| Transparent payments link agent addresses | A fresh address per channel and per `exact` change; X4 for privacy |
| X4b's settle-time double-spend gap | Declared; X4a first |
| The Foundation may re-audit a binding that differs from the reference (CONTRIBUTING.md:213-215) | The specs follow Cardano's structure and the family checklists line by line |
| No TypeScript precedent in the workspace | One package, one toolchain, CI from X0; X-2 records Go as the alternative |

## 9. Open questions for the owner

1. X-1..X-11: confirm or change.
2. The `exact` zero-confirmation cap: a dollar figure, or per merchant only?
3. Whether the facilitator should be offered as a hosted service (ours) or only self-hosted. The
   spec allows both, and self-hosting is required for X4 anyway.

## 10. Implementation status

| Phase | State | Both lines green | Notes |
|---|---|---|---|
| X0 | **done** | — | workspace wiring `ad8cab8`; scaffold `eaa5fb6`; spec drafts `1c27b7c`; the acceptance's `make status` lists the repo clean |
| X1 | **green on both lines, end to end** | ✓ | mechanisms `72633c2`; HTTP end-to-end over real processes (agent → merchant → facilitator service) `6a48e1c`: 6/6 per line incl. OP-1, OP-3 (yolo), OP-4, OP-6; `x402-ycash` CLI. Regression of every suite on both lines green at `e8ae7c0` (table below) |
| X2 | mechanisms **green on both lines** | ✓ (mechanism level) | `84ded9a`: 1,000 requests in one close (2 txs, 2,500 zat fees vs ~1,000,000 for per-request), dynamic pricing, refusals, margin close, refund after t, 0-conf and depth-1 funding, closes mined by stock node 1. Open: client CLI (wave 3) |
| X3 | **green on both lines** | ✓ | `x402-ycash` `6529969`: YED exact at $1/$25 (strict pools), $0.50 refused at server and facilitator, a $20 channel of 201 one-cent requests under the dollar floor closed by a strict pool, refund with payload, Yellowback supply unchanged in every non-burning case; a hand-built burning voucher refused by verify, skipped by strict templates, mined only by stock node 1 (supply −200 cents exactly). YED routes in merchant/agent/CLI merged `3db1468` (YED HTTP suite 12/12 per line) |
| X4 | X4a **green on both lines**; X4-M done; **X4b GO (2026-10-04): spec + TS primitives + lightwalletd `GetChainInfo` merged; Rust light client and service wiring in flight** | ✓ (X4a) | `x402-ycash` merge of `x402/shielded` + `a03fb9b`: P1 at −1 and 1, P0, under/over-payment, wrong memo, replay, multi-request tx, JWS receipts; merchant scan cost negligible, no on-chain Sapling disclosure on either line (`docs/x4m-measurements.md`). X4-M: `x402-ycash` merge of `x402/x4m` |
| X5 | **Python SDK at parity**; **lightwalletd adapter** for light agents | ✓ (interop 8/8; light 5/5 per line) | upstream PRs wait for the owner (outward-facing); lightwalletd adapter and x402-gated services open |
| X6 | not started | — | owner-run; YED after height 3,075,000 |

### Regression of record

The current record is `x402-ycash` `docs/regression.md` at `3940e56` (2026-10-04): 84 devnet tests per line plus the Python devnet suite, green on ycash-dd 4.5.0 and ycash6 6.21.0-rc1, and the upstream staging passing all ten of upstream's checks (lint 0 errors, 608 tests, 94.2 % line coverage, integration 57/58 per line against live devnets). The earlier record follows.

#### Earlier record (`x402-ycash` `e8ae7c0`, 2026-10-03, one devnet at a time)

| Suite | ycash-dd (v4.5.0) | ycash6 (6.21.0) |
|---|---|---|
| node | 8/8 | 8/8 |
| assumptions (R-2, R-3, R-5, R-6, RBF, branch id, Z-3) | 7/7 | 7/7 |
| exact_yec (incl. OP-1, OP-3 yolo, OP-6 stock facilitator) | 16/16 | 16/16 |
| channel_yec (incl. merchant restart) | 7/7 | 7/7 |
| shielded (X4a) | 6/6 | 6/6 |
| yed (X3, incl. OP-2 strict pools, supply invariant) | 9/9 | 9/9 |
| x4m | 2/2 | 2/2 |
| HTTP end to end (agent → merchant → facilitator) | 6/6 | 6/6 |

Unit tests at the same commit: 619 across five workspaces; lint and typecheck clean.

### Findings

Numbered in order of appearance; node and devnet facts are mirrored in `docs/mapping.md` §20.

| # | Finding | Disposition |
|---|---|---|
| X-F1 | **Ycash transparent addresses are `s1…`/`s3…`, not `t1…`.** Mainnet P2PKH `1C 28` (`s1…`), P2SH `1C 2C` (`s2…`/`s3…`); testnet **and** regtest share P2PKH `1C 95` (`sm…`), P2SH `1C 2A`, and WIF `0xEF` (`ycash-dd/src/chainparams.cpp:149-151,409-411,613-614`; `ycash6` `:161-163,456-458,689-690`). YED versions are distinct per network | Plan text corrected (revision 2); `decodeAddress` takes the expected network from `PaymentRequirements.network` and never infers testnet vs regtest |
| X-F2 | Both lines' `signrawtransaction` leave a `SIGHASH_SINGLE` input with no matching output unsigned (`rawtransaction.cpp:1059`; `ycash6` `:1225`), while consensus accepts the SDK-signed form | The RPC signer cannot produce that shape; X1 signs `ALL` only |
| X-F3 | **Neither line enforces the ZIP-317 fee floor at relay** (both wallets paid 1000 zat for 17–37-input shielding txs); a channel close input is ~308 bytes, so its floor is 1500 zat (3 actions), not ~2500 | `fee ≥ feeFloor` is SDK and facilitator policy (S-6 stands as policy); §3.2 S-6's channel figure is superseded by 1500 |
| X-F4 | No difference between the lines in codec, sighash, signing, channel-script standardness, CLTV behaviour or error strings; ycash6 regtest is testable only at the Sapling branch (its Ycash upgrade switches Equihash), so mainnet-branch (`19bd2d2f`) vectors come from `ycash-dd` | Recorded; vectors per line in `x402-ycash/vectors/tx/` |
| X-F5 | `@noble/secp256k1` 3.x signs compact only (DER throws) | Strict BIP66 DER codec in `src/tx/der.ts`, no new dependency |
| X-F6 | **R-3 qualifier:** "already mined → `-27`" holds only while the mined tx has an unspent output (per-tx `CCoins`, `AccessCoins(txid)`); once all outputs are spent a resubmission gives `-26 18: bad-txns-inputs-spent` (`ycash-dd/src/rpc/rawtransaction.cpp:1156-1174`; `ycash6` `:1325-1343`), both lines, live | The txid claim, not `-27`, is the "already settled" signal; settle tracks the `payTo` outpoint with `gettxout` |
| X-F7 | **No replace-by-fee on either line, but different errors:** a 10×-fee double-spend of a mempool input is refused; v4.5.0 answers `-25 ""` (ATMP false without a reason, `ycash-dd/src/main.cpp:1579-1583`), 6.21.0 `-26 258: txn-mempool-conflict` (`ycash6/src/main.cpp:1839-1842`) | Both mapped to `mempool-conflict`; §5.5's first-seen assumption is now verified |
| X-F8 | R-2 verified live: expiry must be ≥ next + 3; a tx is valid **through** `nExpiryHeight` inclusive, then dropped and refused `tx-expiring-soon`; expiry 0 allowed | §5.6 window rule stands |
| X-F9 | Branch id on both devnets is Canopy `19bd2d2f` (chaintip and nextblock), Overwinter..Canopy at height 1 on both lines | Clients read it from `getblockchaininfo` |
| X-F10 | R-5 verified live on both lines, stock node included; **but a tx double-spending a mempool tx still verifies `complete:true`** | Step 4 of the composite verify (`gettxout …, true`) is mandatory |
| X-F11 | **`z_getnewdiversifiedaddress` requires a base Sapling address** (`ycash-dd/src/wallet/rpcdump.cpp:835`; `ycash6` `:1391`): `z_getnewaddress sapling` first (regtest prefix `yregtestsapling1`; testnet `ytestsapling`). `z_listreceivedbyaddress <div> 0` shows the unconfirmed note and memo on both lines (v4.5.0 after ≤ ~1 s; v6 adds `memoStr`, `pool`); listing the base address does not show its diversified addresses' notes | X4a: one base key per merchant, a diversified address per request, poll ≤ a few seconds for 0-conf |
| X-F12 | On 6.21.0, `z_sendmany` from a transparent source with transparent change needs `privacyPolicy: "AllowFullyTransparent"` | The X4a P0 client passes the policy on v6 |
| X-F13 | **Wallet race (both lines):** right after a block or a `sendrawtransaction`, the wallet may still select a just-spent coin ("Transaction not valid") | The RPC signer `lockunspent`s its inputs and retries on `input_spent`; facilitators unaffected |
| X-F14 | **YED channels cannot use zero-confirmation funding:** `yed_validaterawtransaction` reads only confirmed token records, so a voucher spending an unconfirmed channel shows `yedIn` 0 | YED channel funding needs depth ≥ 0 (in a block); the 0-conf opt-in (X-6) is YEC-only |
| X-F15 | **Dust (54 zat) applies to YEC payments and channel outputs** | `exact` YEC `amount` ≥ 54; a YEC channel's first voucher ≥ 54 zat; a client remainder below dust folds into the server output |
| X-F16 | **A voucher cannot claim less than itself:** a signed voucher has fixed outputs, so under dynamic pricing a close can overpay the charged total by up to one `amount` less the last actual charge (EVM/SVM can claim less) | Voucher rule: charged + `amount` ≤ cumulative ≤ D, with compare-and-set; an optional client `close` voucher at exactly the charged total (also a cooperative early close); listed under "cannot match" |
| X-F17 | Upstream naming: Cardano's field is `confirmationPolicy.l1Confirmations` (plan: `confirmations`, kept); `offer-and-receipt` receipts carry no amount and require `payer` (spec uses `payer: "anonymous"` and the signed offer for the amount); upstream's error code is `duplicate_settlement` | Applied in the specs |
| X-F18 | A non-minimal push of an 80-byte payload makes an 84-byte script, over `MAX_OP_RETURN_RELAY` (83); the overlay itself accepts PUSHDATA1/2/4 | The SDK always writes minimal pushes |
| X-F19 | Upstream `x402Client`'s default spend controls reject assets `findDefaultAsset` does not know | YED (USD-pegged, 2 dp) is recognised; YEC is not USD-pegged, so agents add an `allowedAssets` entry (`exact.yecSpendControl`) |
| X-F20 | `x402Facilitator.verify/settle` throw on an unregistered kind; core `getSupported()` lists empty signer families | The service checks `getSupported()` first (`unsupported_scheme`/`invalid_network`) and drops empty families (`"signers": {}`) |
| X-F21 | Spec rule order: a txid the facilitator already broadcast fails rule 6 (`input_spent`) before rule 10 | For a claimed txid, verify skips rules 6–9Y and answers `duplicate_settlement`; settle checks the claim first. Spec fix in wave 3 |
| X-F22 | yolo issues new work only on height change (`yolo/src/poller.rs:5-9`), so a payment reaching the mempool mid-height lands one block later | Adds ~1 block to policies 0/1 on yolo-mined chains; a yolo option (new work on template change) is a possible pool-side improvement, not required |
| X-F23 | On the devnet `yed_getprice` pFast/pMid go null after untagged blocks; pSlow survives | Price sources fall back pMid → pSlow; no price ⇒ policy 1, never an error |
| X-F24 | A stock-node facilitator accepts a YEC payment that spends a YED coin (it cannot see tokens) | As specified: coin selection is the guard there; a Yellowback-node facilitator refuses (`invalid_exact_ycash_yed_input`) |
| X-F25 | **Vouchers are bound to the consensus branch id** (ZIP-243): a voucher signed before a network upgrade does not verify after it | Servers close every channel before an activation height, or clients choose t below it. Spec fix in wave 3 |
| X-F26 | A stateless facilitator re-checks t ≥ tip + `minLockBlocks` on a retried `open` | Clients choose t with slack (SDK: 10 blocks). Spec fix in wave 3; one-in-flight voucher gets the code `invalid_batch_settlement_ycash_channel_busy` |
| X-F27 | **sapling-proof consumption key:** keyed on the txid alone, one tx paying two requests bought only one | Coordinator decision: key = `ycash:<net>:<txid>@<payTo>` (payTo is unique per request, so binding holds and a payer never loses a payment); spec step 7 corrected so only −1 accepts mempool notes |
| X-F28 | On v4.5.0 a t→z `z_sendmany` returns transparent change to a fresh address, not the source | P0 payers must not assume change returns to the source |
| X-F29 | A viewing-key-only node **cannot issue** diversified addresses (`-4`, spending key required; `ycash-dd/src/wallet/rpcdump.cpp:869-870`; `ycash6` `:1425-1427`) but sees receipts at every diversified address of the key, mempool included; only full viewing keys import | Settlement can run on a viewing-key host; address issuance needs the spending key or offline derivation (wave 3 checks the latter) |
| X-F30 | **No on-chain selective disclosure for Sapling on either line:** `z_getpaymentdisclosure` is Sprout-only (`rpcdisclosure.cpp:103,109`), needs `-experimentalfeatures -paymentdisclosure`, and v6 never writes its DB | Selective disclosure = the JWS receipts (offer-and-receipt); an N-ask recorded |
| X-F31 | Merchant scan cost measured: 250 Sapling outputs reconnect in 22–28 ms with 0–1 keys on v4.5.0 (~51 ms with 10 keys); 59–67 ms on v6 regardless of key count (batch scanner); diversified addresses add nothing | Not a blocker for merchants; keep one dedicated x402 key |
| X-F32 | Core 2.28 fixes `payTo`, `amount` and `asset` once requirements exist (the enrich hook may only add `extra`) | The merchant issues the per-request diversified address in the route's dynamic `payTo(context)` and reuses it on the paid retry; the facilitator wraps `SaplingProofHandler` to core's handler signature |
| X-F33 | Over HTTP a shielded proof can arrive before the note reaches the merchant's node, and core treats `not_received` as final | The facilitator waits a bounded time for the note (`X402_SAPLING_NOTE_WAIT_MS`, default 10 s); spec step 4 says SHOULD |
| X-F34 | An agent can reselect a coin its previous payment spent if its node has not seen that payment yet (another node's facilitator broadcast it) | Durable reservations + `gettxout(…, true)` before signing (wave 4, `harden`) |
| X-F35 | The server's channel watcher kept tracked channels in memory only | `ChannelStore.list()` and re-tracking at start (wave 4, `harden`) |
| X-F36 | Spend controls cap `amount` only, not a channel's deposit | A client-side `maxDeposit` in the batch client (wave 4, `harden`) |
| X-F37 | The node's Yellowback verdicts are lowercase (`"ok"`, `"burned"`; `src/yellowback/state.cpp:23-24`, both lines) | Specs corrected |
| X-F38 | **`locked` in `yed_listunspent` does not mean taken:** the Yellowback wallet locks every YED output it holds against plain YEC spends (`ycash-dd/src/yellowback/wallet.cpp:404-410,450-465`, both lines), so `lockunspent` cannot reserve YED coins; and `rpcWalletFunder` could have spent a YED coin as plain YEC (masked because `listunspent` omits locked coins) | In-process (then durable) reservations; funders skip every `yed_listunspent` outpoint |
| X-F39 | `yed_validaterawtransaction.valid` is the script result, so a voucher with the server's slot empty is `valid: false` | A stateless facilitator checks everything but `valid` on a client voucher; the server and a `claim` check everything. Spec corrected |
| X-F40 | A voucher in the fixed YED layout cannot burn and still pass the shape check | The overlay check on vouchers catches only yedIn ≠ D; the burning voucher is refused as `voucher_shape` |
| X-F41 | The YED client `close` must be at max($1.00, charged); the close trigger reads "remainder strictly between $0 and $1.00" | Spec corrected |
| X-F42 | After a run of stock-node (untagged) blocks `yed_mint` refuses `mintpol-no-price` | Tests mine pool blocks before minting (devnet behaviour, not an x402 issue) |
| X-F43 | YED is a default asset in core with a $1 spend cap per payment | Agents paying more set `maxAmountPerPayment`; documented |
| X-F44 | Sync from genesis: 6.21.0 verifies Sapling blocks ~4.5× faster than v4.5.0 (41 vs 185 ms per shielded block), the opposite of the reconnect measurement (X-F31, a different path) | Recorded in `docs/x4m-measurements.md` |
| X-F45 | 6.21.0 answers RPC 3–5 s after a restart (v4.5.0 ~1 s), which dominates its time to first payment | Recorded |
| X-F46 | v4.5.0 refuses to start without all three parameter files incl. the 725 MB `sprout-groth16.params` (`ycash-dd/src/init.cpp:782-799`); 6.21.0 bundles Sapling parameters | An agent full-node bootstrap on v4.5.0 downloads the params |
| X-F47 | lightwalletd-dd 0.4.6 serves a 6.21.0 node for GetLightdInfo/GetBlockRange/GetTreeState; public `lite.ycash.xyz` runs the workspace pin `187a267` | A light agent path is available against either line (SendTransaction/GetMempoolTx not yet tested) |
| X-F48 | The explorer's `commitments` field is the Sprout tree size (`ycash-dd/src/rpc/blockchain.cpp:1148-1150`); its `/blocks` cannot page past the latest 10 | Mainnet Sapling counts taken from tree states instead |
| X-F49 | Diversified-address walks differ: v4.5.0 walks up from index 1 skipping wallet addresses (`rpcdump.cpp:877-905`), 6.21.0 from the base address's index | An offline issuer uses a disjoint index range (from 2^40) |
| X-F50 | The client caps the deposit D but not the server-chosen `closeFee`, which is also locked in V and paid to miners at close; a hostile server could inflate it | **Done** (`73cf5a1`): client `maxCloseFee`, default 5,000 zat |
| X-F51 | `FileChannelStore` never removes a closed channel's records, so `list()`/`resume()` slow over a merchant's lifetime | **Done** (`73cf5a1`): `retire`/`prune`, closed channels retired for 30 days |
| X-F52 | A channel funding has no expiry height, so its coin reservation is time-based (30 min); a server that never relays the funding ties up the agent's coins that long | **Done** (`73cf5a1`): funding expiry tip + 3 + 40, reservations released by height, server refuses fundings that expire before the policy depth |
| X-F53 | Upstream's Python scheme protocols are **synchronous** (`x402Facilitator.verify` calls `scheme.verify` without awaiting; server `parse_price`/`enhance_payment_requirements` sync) | The Python mechanism's logic is async and runs behind the sync protocol on a private event-loop thread; upstream maintainers may prefer a sync client (TVM does) |
| X-F54 | PyPI `x402` is at 2.25.0 (the Python SDK in upstream `751590a`); TS `@x402/core` at 2.28.0; versioned separately | Python pins `x402>=2.25.0,<3` |
| X-F55 | JSON equality and integer typing were undefined in the spec: Python's `False == 0`, `1 == 1.0`; JS parses `1.0` as 1 | Spec now says values compare as JSON values with types, integers without fraction or exponent |
| X-F56 | Python's `hashlib` offers RIPEMD-160 only with OpenSSL's legacy provider | The Python port carries a checked fallback |
| X-F57 | `yellowback-devnet down` prints "5 node process(es) did not stop over RPC and were terminated" on both lines, every time (seen by every chunk) | Devnet-CLI quirk in the node repos' `contrib/` (likely the RPC `stop` with the emoji credentials); not an x402 issue, nodes do stop; recorded for the devnet's owner |
| X-F58 | **A channel's client remainder (and a default refund) went to the channel key C**, which no wallet sees — YED stranded at C after closes | **Done** (`73cf5a1`): required `open.returnAddress`, bound into every voucher and the refund; devnet asserts the remainder reaches the client wallet and nothing sits at C, both lines |
| X-F59 | `utxoSourceFunder` refused YED, so the agent and CLI each carried a copy of a WIF YED funder | **Done** (`73cf5a1`) |
| X-F60 | `yed_validaterawtransaction` reads yedIn 0 once a tx is mined (its inputs are spent) | Overlay checks run while the tx is in the mempool (node behaviour) |
| X-F61 | `yed_mint` refuses amounts below $100 (`bad-mint-amount`) | Devnet setup mints ≥ $100 (node rule) |
| X-F62 | The bounded sapling-proof note wait lived only in the facilitator service, not the TS mechanism (Python has it in the mechanism) | **Done** (`73cf5a1`) |
| X-F63 | `SaplingProofHandler.enhanceRequirements` issued an address before checking the operator's confirmation range | **Done** (`73cf5a1`) |
| X-F64 | The Python batch server's hooks are coroutines (async `x402ResourceServer` only); verified-voucher state is keyed by payload identity in both languages | Recorded; a sync variant if a sync framework needs it |
| X-F65 | libsecp256k1 refuses high-S signatures while noble (`lowS: false`) accepts them | Verifiers normalise s and accept; signers MUST emit low-S; pinned in `vectors/shielded`; spec sentence (wave 5) |
| X-F66 | The resource server reads the facilitator's kinds once at initialize, so turning YED on later needs a reload of that cached view, not only a re-probe | Merchant `YedGate` + `SupportedCache.reload` (`73cf5a1`) |
| X-F67 | The batch spec's example `payTo` failed its base58check checksum | Replaced with a valid mainnet address (`46106c9`) |
| X-F68 | The Python batch server accepted but ignored `returnAddress` and the funding-expiry rule | **Done** (`14281ff`): 331 Python tests, devnet 8/8 on both lines |
| X-F69 | lightwalletd `SendTransaction` works on both lines (2–3 ms; success is the JSON-quoted txid in `errorMessage`; mempool re-send returns the txid; refusals carry the node's code and message) | `LwdChain` maps refusals to `SendRawTransactionError` |
| X-F70 | **`GetMempoolTx` never streams transparent txs** (`lightwalletd-dd/frontend/service.go:470-489`), and `GetAddressUtxos`/`GetAddressTokens` list confirmed outputs, still listing a coin whose spend is in the mempool | The light path has no mempool-spend guard; it relies on the reservation store; a foreign spend of the same key surfaces as a broadcast refusal |
| X-F71 | `GetLightdInfo` reports `consensus.chaintip`, not `nextblock` (`lightwalletd-dd/common/common.go:212`), so on the block before an upgrade a light client signs under the old branch id | Recorded; an N-ask for lightwalletd-dd (a `nextblock` field) |
| X-F72 | `YellowbackStreamer` is rate-limited to a burst of 20 per peer IP, refilled 1/s (`frontend/yellowback_ratelimit.go`) | Fast light agents may see `RESOURCE_EXHAUSTED`; not hit in tests |
| X-F73 | `GetAddressUtxos` carries no coinbase flag | Agent keys must never receive coinbase (documented) |
| X-F74 | `importaddress` answers `-4` "already contains the private key" when the WIF is already in the node wallet (`ycash-dd/src/wallet/rpcdump.cpp:230`; `ycash6` `:189`), which broke `RpcUtxoSource({importAddress})` | Treated as success (`2caaa54`) |
| X-F75 | Upstream `lint:check` requires JSDoc on every function and member ordering (1,028 errors on the staged package) | Fixed at the source and enforced in x402-ycash's own lint (wave 7, `doclint`) |
| X-F76 | pnpm 11's strict `minimumReleaseAge` fails against abbreviated registry metadata (`ERR_PNPM_MISSING_TIME`) | Staging passes `--config.minimum-release-age-strict=false`; the owner regenerates the lockfile before pushing |
| X-F77 | Upstream's e2e `batch-settlement` harness is EVM/SVM-specific orchestration | Ycash e2e covers `exact`; channels are proven by our devnet suites |
| X-F78 | **A viewing-key-only node answers `z_listreceivedbyaddress` with `-5` for an offline-issued address until it has decrypted a note to it** (`ycash-dd/src/wallet/rpcwallet.cpp:3514-3515`; `ycash6` `:4278-4279`; the wallet then adds the address, `ycash-dd/src/wallet/wallet.cpp:2850-2856`) | The facilitator reads `-5` at payTo as "not received yet" and keeps waiting (TS and Python, `add0578`) |
| X-F79 | `zSendMany` sent the fee as a string; v4.5.0 reads it with `get_real()` and refuses ("JSON value is not a number", `ycash-dd/src/wallet/rpcwallet.cpp:4301-4302`) | Sent as a JSON number (`add0578`) |
| X-F80 | 6.21.0 refuses a `z_sendmany` fee above 4× its ZIP-317 conventional fee; v4.5.0 has no cap | Clients setting a shielded fee on v6 stay under it |
| X-F81 | A 6.21.0 node behind `-connect` to a single peer once stalled mid catch-up for > 2 min (not reproduced) | Rehearsal nodes connect to two peers |
| X-F82 | Offline issuance rehearsed on both lines: the TS port (FF1-AES-256 + Jubjub via `@noble/curves`) reproduces the node wallets' and the Rust tool's addresses, including skipped invalid diversifiers (`vectors/shielded/divaddr.json`); merchant needs no node, settlement node holds only the viewing key, spending key offline yet able to spend | X4-M merchant defaults now implemented and rehearsed (`add0578`, `docs/mainnet-runbook.md` §4) |
| X-F83 | Order-dependent devnet flake: after many stock-node blocks the overlay halts minting for low participation (`mintpol-participation … (ACT-4)`, `ycash-dd/src/yellowback/txbuilder.cpp:812`); helpers retried only on `mintpol-no-price` | Harness defect fixed in all four mint helpers (TS and Python) — mine 8 pool blocks; not a mechanism or node defect |
| X-F84 | Upstream's lockfile carries `@noble/curves` 1.x; ours needs 2.x; `@grpc/*` is new upstream | Owner decision 9 in `PUBLISHING.md`: ship as is, or leave `src/lwd` out of PR 2 |
