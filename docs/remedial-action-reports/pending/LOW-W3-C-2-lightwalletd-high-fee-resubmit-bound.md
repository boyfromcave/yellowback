# LOW — W3-C-2 — `SendTransaction`'s `allowhighfees` resubmission: bound it by the node's effective Yellowback cap and the published size rate, and meter its `gettxout` work

Repos / branches to change: `lightwalletd` (`fix/W3-C-2-high-fee-resubmit-bound` off `upgrade/vault`). No node change. Cross-reference only: `yew` (`MEDIUM-W3-C-1-yew-token-value-fee-bound-yed-activation.md`, the wallet-side fix that owns the fee decision).
Audit source: wave 3 `docs/audits/quantum-vault-ecosystem-wave3/06-clients-wallets-infra.md:44` (summary), `:219-240` (W3-C-2); verification `docs/audits/quantum-vault-ecosystem-wave3/verification/06-verification.md:16` (verdict: Low, down from Medium), `:164-191` (detail and the two impact corrections); consolidated `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:44`. Wave 4 `docs/audits/quantum-vault-ecosystem-wave4/04-clients-wyec-recheck.md:52` (STILL OPEN: `frontend/` unchanged, `service.go:332-337`, `sendfee.go:45`), `:213-228` (the `f89ce24` delta is fixtures only). Wave 4's lightwalletd Info item, W4-C-3 (the contract-fixture check follows a moving node branch), is a node-file pin issue and is handled with the other client pins in `LOW-W3-C-3-W3-C-4-W4-C-2-W4-C-3-yew-x402-lightwalletd-node-file-pins.md`, not here.
Status: pending — re-verified at lightwalletd `f89ce24` (the only commit since `0d29cf4` re-syncs `testdata/vault/`; `frontend/` and `common/` are unchanged, every line below re-grepped) and node `ycash-dd` `da5e0fe` (2026-10-13)

## 1. Finding

When the node refuses a submitted transaction as "absurdly high fee", lightwalletd's stock `SendTransaction` works out the fee. It reads the amount from ycash-dd's message, or computes it with up to 500 `gettxout` calls (ycash6 does not state the amount). It then resubmits with `allowhighfees = true` whenever the fee is at most `params.fees.network.yellowback.maxTxFeeCeilingZat`: the node's `-yellowbackmaxtxfee`, default **10 YEC**. This is deliberate (review M-2). Post-quantum and Yellowback transactions are priced in dollars per KB and can legitimately exceed `-maxtxfee` (0.1 YEC by default): an SLH-DSA vault spend is ~8 KB. Two problems remain.

- **The bound is the wrong one.** The node's own wallet relays such a transaction only within the *effective* Yellowback cap, `min(max(-maxtxfee, $2 at the price), -yellowbackmaxtxfee)`, which `yed_getinfo` publishes as `yellowback.maxTxFeeZat` (5 YEC at the contract example's $0.40). The server uses the ceiling instead, so it accepts up to twice what the node itself would pay, and more at higher prices. It also never compares the fee with what the transaction's size justifies at the published rate. So a client bug that overpays by orders of magnitude (W3-C-1 is one) has the node's sanity check turned off for it by an honest server, up to 10 YEC per transaction.
- **The work is unmetered.** The fee computation runs on the stock `CompactTxStreamer` path, outside the `YellowbackStreamer` per-peer limiter and outside the `yedInFlight` semaphore. Each refused submission costs up to 500 `gettxout` calls plus a `yed_getinfo`.

The verifier narrowed the impact. The module check follows the absurd-fee check in `AcceptToMemoryPool`, so on a node with the module live, W3-C-1's over-assigned transaction is refused anyway. A *malicious* server never needed this path, because it holds the RPC credentials. And the work is bounded (a transaction with unknown inputs fails on the first `gettxout`). Low: defence in depth and a bounded nuisance. The wallet, not the server, must own the fee decision; that is the W3-C-1 report.

## 2. Root cause (lightwalletd `f89ce24`; node `ycash-dd` `da5e0fe`)

- `frontend/service.go:315-339`: `SendTransaction`. Stock `sendrawtransaction` first (`:330`). On any error, `highFeeVerdict(rawtx.Data, rpcErr)` runs (`:337`); if it allows, the same hex is resubmitted with `"true"` (`:338`).
- `frontend/sendfee.go`:
  - `:49-71` `yellowbackFeeCeiling` reads only `params.fees.network.yellowback.maxTxFeeCeilingZat` through a raw `common.RawRequest("yed_getinfo")`, which is neither cached nor bounded.
  - `:43-45` `maxFeeInputs = 500`.
  - `:97-132` `computeFee`: one `common.RawRequest("gettxout", …)` per prevout (`:110`), no context, no semaphore.
  - `:136-156` `highFeeVerdict`; `:158-166` `verdict`: `fee > ceiling` → refuse, else allow. Fee and size are never compared.
- Node:
  - `src/rpc/yellowback.cpp:753-758` publishes `yellowback.{usdPerKBMicro, zatPerKB, maxTxFeeUsdMicro, maxTxFeeCeilingZat, maxTxFeeZat}`. `:757` marks the ceiling as "the cap's absolute ceiling", and `:758` `maxTxFeeZat` = `YedMaxTxFee()` is the effective cap.
  - `doc/yellowback-rpc.md:95-99`: "the Yellowback cap min(max(`-maxtxfee`, $2 at the price), `-yellowbackmaxtxfee`) … the node's own wallet relays one above `-maxtxfee` but within that cap".
  - `plain.zatPerKB` / `yellowback.zatPerKB`, `floorZatPerKB` and `flatZat` are published beside it (`:748-763`).
- Limiter and bounds that do not cover this path:
  - `frontend/yellowback_ratelimit.go:185-191` `limited` (per peer, `yedCostHeavy = 1`, `:44`) is called only by `YellowbackStreamer` handlers.
  - `common/yellowback.go:206-230` `yedInFlight` is used only by `CallYed` (`:249-280`). `StockMethods` (`:74-81`) is limited to parameterless reads.
  - `cmd/root.go:265` constructs `lwdStreamer` with no limiter.
- Mitigation already in the deployment: ycash-infra's gateway limits sends per IP (`charts/ycash-lightwallet/values.yaml:120` `sendPerIpPerMinute: 30`; `templates/gateway/routes.yaml:77`). Not every operator runs that chart.
- Tests: `frontend/sendfee_test.go:82-141` `TestSendHighFee` (cases at `:94-107`) uses the contract's `yed_getinfo` example. The ceiling there is `1000000000`, and the effective `maxTxFeeZat` is `500000000`.
- Docs: `docs/yellowback.md:152-159` describes the ceiling rule.

## 3. Fix options considered

1. **Make the resubmission opt-in per request** (a new `SendTransaction` field, or a separate RPC the wallet calls after showing the real fee; the audit's first suggestion). Rejected as the primary fix. `RawTransaction` is the frozen upstream message (`walletrpc/service.proto:36-39`), so a field means a proto change in YEW, x402 and every light client. YEW needs the resubmission for correctly priced PQ spends today. The wallet-side fee check (W3-C-1 step 2) is where the decision belongs, and it lands independently.
2. **A server flag, off on public deployments** (the audit's second suggestion). Rejected as the default: switched off, every SLH-DSA vault spend above `-maxtxfee` fails on public servers. Accepted as an *operator* switch whose default keeps today's behaviour.
3. **Tighten the rule to what the node itself would do, and meter it** (this report). The resubmission stays for correctly priced transactions and is refused for overpaying ones. Accepted.
4. **Remove the resubmission and ask operators to raise `-maxtxfee`.** Rejected: that disables the sanity check for every transaction, not only Yellowback/PQ ones.

## 4. Recommended fix

1. **Use the node's effective cap.**
   - In `sendfee.go`, replace `yellowbackFeeCeiling` with `yellowbackFeeTerms(ctx) (feeTerms, bool)`, reading `params.fees.network`. The struct gets `capZat = yellowback.maxTxFeeZat` (the effective cap), `ceilingZat = yellowback.maxTxFeeCeilingZat`, `rateZatPerKB = max(yellowback.zatPerKB, plain.zatPerKB, floorZatPerKB)` and `flatZat`.
   - Fall back to `ceilingZat` only when `maxTxFeeZat` is absent or 0 (an older rpcversion-8 node), and log it.
   - Fetch through `common.CallYed(ctx, "yed_getinfo")`. That call is already allow-listed and cached per tip (`common/yedcache.go:32`) and bounded by the in-flight semaphore, so a burst of refused sends costs one node call per block.
2. **Bound the fee by the size the node prices.** In `verdict`, allow only if `fee ≤ capZat` **and** `fee ≤ sizeBound`, where
   ```go
   // The most a correctly priced transaction of this size pays: the higher published per-KB rate, rounded
   // up per started KB, at least the flat fee, times a margin for a price move between the client's
   // quote and this submission (the node re-prices per block; the Yellowback window medians move slowly).
   sizeBound := max(flatZat, ceilDiv(int64(len(data))*rateZatPerKB, 1000)) * sendFeeMargin   // sendFeeMargin = 3
   ```
   When the fee is above `sizeBound`, refuse with the node's error code and the message `absurdly-high-fee: fee <f> zat exceeds <sizeBound> zat, <margin>× the published rate for <n> bytes (yed_getinfo.params.fees.network)`. Keep the existing message for `fee > capZat`.
   - When `priceMicroUsd` is null (`priceSource: "fallback"`), `zatPerKB` is the fallback rate the node itself uses, so the rule holds unchanged.
   - Record the margin and its reason in `docs/yellowback.md:152`. The margin is a constant, not a flag. Its only purpose is to absorb a quote-to-submit price move, and 3× is far below the factor-of-5,000 overpayment W3-C-1 produced.
3. **Meter the refused path.**
   - Add an exported limiter hook on `lwdStreamer`: a package variable `sendFeeLimiter *rateLimiter`, set in `cmd/root.go` after `NewYellowbackStreamer` (`:292`) via `frontend.SetSendFeeLimiter(service)`, which reuses the service's limiter and `TrustProxies` set.
   - Before `computeFee`, charge `yedCostHeavy * ceil(len(prevouts)/50)`, with a minimum of one heavy unit, against `peerKey(ctx)`. When the budget is spent, keep the node's original refusal (no resubmission) and add `"; fee check rate limited"` to the message. Do not return `ResourceExhausted`: the stock RPC's error contract is the `SendResponse` code.
   - Run the `gettxout` loop under one `yedInFlight` slot. Export `common.AcquireYedSlot(ctx) (release func(), err error)`, factored out of `CallYed:263-275`, and pass a context with `YedCallTimeout`. When the deadline passes, stop the loop and keep the node's refusal.
   - Lower `maxFeeInputs` from 500 to 250: YEW's `MAX_INPUTS`, the node's own `maxInputs` for YED selection. A wallet transaction with more inputs that is *also* over `-maxtxfee` is not a shape any workspace client builds.
4. **Operator switch** (option 2, default unchanged): `--yellowback-high-fee-resubmit` (`LWD_YELLOWBACK_HIGH_FEE_RESUBMIT`), default `true`. When `false`, the node's refusal always stands. Document it in `docs/yellowback.md`. In ycash-infra, `values.yaml` `lightwalletd.extraArgs` can carry it; no chart change is required.
5. **Docs.**
   - `docs/yellowback.md:152-159`: rewrite the rule (effective cap, size bound, margin, metering, flag).
   - Header comment `sendfee.go:5-24`: the same.
   - Workspace `docs/mapping.md` §15: add the row "lightwalletd's high-fee resubmission is bounded by `yellowback.maxTxFeeZat` and the published size rate".

## 5. Tests

- `TestSendHighFee` (`sendfee_test.go:82`): update the case table.
  - "ycash-dd, at the ceiling" (`1000000000`) must now **refuse**, because the example's `maxTxFeeZat` is `500000000`. Add "at the effective cap" (`500000000`) and "over the cap, under the ceiling".
  - The `v4Tx` fixture is ~100 bytes. Add a case whose fee is within the cap but above `sizeBound` (e.g. 50,000,000 zat for 100 bytes at the example rate 12,500,000 zat/KB, which gives `sizeBound = max(1000, 1,250,000) × 3 = 3,750,000`): **refused**, message names the size bound. A case at 3,000,000 zat is resubmitted.
  - A node answer without `maxTxFeeZat` falls back to the ceiling (one case).
- New `TestSendHighFeeMetered`: a stub limiter with a budget of 1 unit and a refusal that needs `computeFee` (ycash6 message) with 60 prevouts (a cost of 2 units). No `gettxout` calls are made, the node's refusal stands, and the message carries `fee check rate limited`. With budget 2, exactly 60 `gettxout` calls are made.
- New `TestSendHighFeeInFlight`: with `SetYedMaxInFlight(1)` and the slot held by the test, the refused path makes no `gettxout` call within `yedQueueWait` and keeps the node's refusal.
- New `TestSendHighFeeTooManyInputs`: 251 prevouts → no `gettxout`, node refusal stands.
- New `TestSendHighFeeSwitchOff`: with the flag false, no `yed_getinfo` or `gettxout` call is made and no resubmission happens.
- `yed_getinfo` through `CallYed`: assert it is served from the cache on the second refused send at the same tip (`common.YedCacheStats` hit counter).
- Devnet, behind the existing build tag (`frontend/yellowback_devnet_test.go`), optional: an SLH-DSA vault spend priced at the published rate and above `-maxtxfee` is still accepted through `SendTransaction`. That is the regression this path exists for.
- Run `go test -mod=vendor ./frontend/ -run 'SendHighFee|InputValidation|RateLimit'` and add the new names to the frontend job's `-run` regex in `.github/workflows/yellowback-tests.yml`.

## 6. Acceptance criteria

- The resubmission is allowed only for `fee ≤ min(maxTxFeeZat, sizeBound)` (the ceiling only as a documented fallback). No code path reads `maxTxFeeCeilingZat` as the bound when `maxTxFeeZat` is present.
- `yed_getinfo` on this path goes through `CallYed`, and the `gettxout` loop runs under an in-flight slot, a deadline and the per-peer limiter. `maxFeeInputs` is 250.
- A flag turns the resubmission off; its default keeps the current behaviour for correctly priced transactions.
- All tests above are green and in the CI `-run` regex. `docs/yellowback.md` matches the code.

## 7. Risks and side effects

- **A correctly priced transaction refused.** The node re-prices per block. A client that quoted at a much lower price than the tip's could exceed `3×` the rate. The window medians move slowly and the margin is wide; if it is ever hit, the user sees the node's absurd-fee refusal and rebuilds at the current rate. That is the right failure: rebuild, not overpay.
- The effective cap is lower than the ceiling, so a transaction between the two that an honest server used to relay is now refused. The node's own wallet would not relay it either, so this matches node behaviour.
- The metering ties the stock RPC to the Yellowback limiter's budget per peer. A peer that exhausts it on Yellowback reads gets the node's refusal for an over-`-maxtxfee` send until the bucket refills (1 unit/s). Acceptable, and documented.
- No wire, proto or vector change; clients are unaffected. Rollout: lightwalletd image rebuild, then the ycash-infra deployment picks it up.

## 8. Effort estimate and dependencies

- ~1 day (rule, metering, flag, tests, docs). No consensus review.
- Depends on nothing. Complements `MEDIUM-W3-C-1-yew-token-value-fee-bound-yed-activation.md`, which closes the user-facing loss in the wallet; the two land in either order.
