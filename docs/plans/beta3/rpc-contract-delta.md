# Beta3 RPC contract step — RPC contract delta (`rpcversion` 10)

**Revision 1 (2026-11-15).** The machine-readable form of decision B3-D5 ([`beta3-plan.md`](beta3-plan.md) §3:
one `rpcversion` step to 10, at integration, covering every new call and field of the beta3 run) for the contract
generator (`scripts/extract-spec.sh --write-beta3` / `--check-beta3`, `make spec-beta3` / `make spec-check-beta3`). It
layers on the prefix line's delta ([`../yellowback-pq-prefix-rpc-delta.md`](../yellowback-pq-prefix-rpc-delta.md)
§4.12, `rpcversion` 9) exactly as that one layers on the fees delta: the generator reads only the `### 4.13` section
below. A node tree whose `doc/yellowback-rpc.md` states `rpcversion` 9 stays on the prefix line, untouched.

**No `yed_*` field changes shape.** The `yed_*` contract is the prefix line's with `yed_getinfo.rpcversion` 10. The
step is taken by decision, as `3` and `4` were (`doc/yellowback-rpc.md`, "`rpcversion` rule"): every change of the
run is an addition to a stock call, and the number tells a client that the node it talks to has all of them, so a
client that needs one checks `rpcversion >= 10` instead of probing each call.

**What `rpcversion` 10 means (both C++ node lines; kogany when it reports 10).** Each with its beta3 item
(the numbering of the plan's §2 status block):

| Item | Call or field | Change |
|---|---|---|
| 3 | `getcoinbasetemplatefor "address" {"previousblockhash", "txids"}` | new call: a complete coinbase paying `address` (transparent, Sapling or post-quantum) for the named template; result `data`, `hash`, `height`, `previousblockhash`, `addresstype`, `subsidy`, `fund`, `fundrule` (`mandated`/`optional`/`none`), `fees`, `amount`, `txcount`, `flags`, `sigops`; errors `template-stale: …`, `coinbase-does-not-fit: …` |
| 3 | `getblocktemplate.coinbasetxn.foundersreward` (ycash-dd) | the fund output's value by the coinbase's rule, also for a Sapling miner address (was `vout[1]`, 0 when the coinbase had no transparent miner output); ycash6 was already right |
| 2 | `getblockchaininfo.transparentPools`, `getblock.transparentPools` (verbosity 1, 2) | new object: the transparent pool by address type (`pools[]` by `id`: `transparent_ecc`, `transparent_pq`, `pq_channel`, `vault`, `vault_intent`; `pq_by_scheme[]`, `vault_by_module[]`); `valuePools` unchanged, order included |
| 6 | `vin[].address` of an input spending a post-quantum output: `getrawtransaction` (verbose), `getblock` verbosity 2, `getblockdeltas` (`inputs[].address`), REST `/rest/tx/<txid>.json` | now present on an insight node, in the D-9 form (`sqf…`/`sqs…`, `tqf…`/`tqs…`, `rqf…`/`rqs…`); was absent |
| 1 | `gettransaction.fee` | the transaction's own fee for every funding shape (Sapling and Sprout spends included); absent when the wallet does not hold the funding transaction of every transparent input |
| 4 | `-ydf` default 0; `getblocksubsidy.founders`, `getblocktemplate.coinbasetxn.ydfpercentage` past the mandate | the share this node's `-ydf` donates, 0 by default (was 5) |

Item 5 (the fast testnet's mandate end) is a consensus parameter with no RPC field of its own; items 8 and 9
(`contrib/bootstrap/ycash-bootstrap`) are tooling. Neither moves the number.

### 4.13 RPC contract delta (`rpcversion` 10)

The beta3 line's RPC contract is the prefix line's (§4.12 applied) with the delta below. The generator reads this
section as it reads the prefix delta's §4.12: each ```json block belongs to the `yed_*` command named in backticks on
the nearest non-blank line above it, merged into that command's `returns`. The generator refuses when the node's
document lacks a field named here or states another `rpcversion`.

#### `yed_getinfo`

```json
{
  "rpcversion": 10
}
```
