# Beta4 tag v2 step — RPC contract delta (`rpcversion` 11)

**Revision 1 (2026-11-18).** The machine-readable form of the `rpcversion` 10 → 11 step of the beta4 price-feed plan
([`price-feed.md`](price-feed.md) §4.3 "RPC contract", task D-T9; decisions D-8, D-10: tag v2, a post-quantum payout
key) for the contract generator (`scripts/extract-spec.sh --write-beta4` / `--check-beta4`, `make spec-beta4` /
`make spec-check-beta4`). It layers on the beta3 line's delta ([`../beta3/rpc-contract-delta.md`](../beta3/rpc-contract-delta.md)
§4.13, `rpcversion` 10) exactly as that one layers on the prefix delta: the generator reads only the `### 4.14`
section below. A node tree whose `doc/yellowback-rpc.md` states `rpcversion` 10 stays on the beta3 line, untouched.

**One `yed_*` field is new; none changes shape.** `yed_gettag` (and the same tag object in `yed_getprice.tag`) gains `payoutScheme` (`"p2pkh"`, `"fn-dsa-512"` or
`"slh-dsa-sha2-128s"`), and its `version` (documented since the upgrade line, always `1` until now) is `1` for a P2PKH
payout key and `2` for a post-quantum one (the 49-byte v2 tag). `yed_getinfo.rpcversion` becomes 11.

**Every payee and payout address field may now hold a plain post-quantum address** of the network, in the D-9 form
(`sqf…`/`sqs…` on mainnet, `tqf…`/`tqs…` on the testnets, `rqf…`/`rqs…` on regtest). The field names and their JSON
type (a string) are unchanged, so the contract does not change for them; a client that parsed them as P2PKH must accept
the post-quantum form from `rpcversion` 11. The fields (price-feed plan §4.3, and the node document ycash-dd
`doc/yellowback-rpc.md`, "Tag v2"):

| Call | Field |
|---|---|
| `yed_gettag` | `payoutAddress` |
| `yed_getinfo` | `miner.payoutAddress`, `policy.preferredPayee` |
| `yed_listminers` | `[].payoutAddress` |
| `yed_setquote` | `next.payoutAddress` (`nextTag.payoutAddress`) |
| `yed_getfeepayee` | `eligible[]`, `default.payoutAddress`, `preferred` |
| `yed_getprice` | `pinnedKeys[]` |
| `yed_gettxinfo`, `yed_validaterawtransaction`, `yed_getblockverdict`, `yed_listtransactions`, `yed_estimateredeem`, the wallet's mint, redeem and claim calls | every `payee` |

The fee output a MINT, a claim REDEEM or an owner REDEEM must carry is the eligible payee's script: the 25-byte P2PKH
or the 35-byte TX_PQPKH (`0x20 <hash> OP_1|OP_2 OP_CHECKPQSIG`). The attestor fee (AFEE-1) stays P2PKH. The options
`-yellowbackpayoutaddress` and `-yellowbackpreferredpayee` (kogany: `mining.yellowback_payout_address`) accept a
post-quantum address of the network. The `-mineraddress` default applies to a P2PKH `-mineraddress` only: the internal
miner refuses a post-quantum `-mineraddress`, and kogany's `mining.miner_address` cannot hold one, so a post-quantum
payout is set with the payout option.

### 4.14 RPC contract delta (`rpcversion` 11)

The beta4 line's RPC contract is the beta3 line's (§4.13 applied) with the delta below. The generator reads this
section as it reads the beta3 delta's §4.13: each ```json block belongs to the `yed_*` command named in backticks on
the nearest non-blank line above it, merged into that command's `returns`. The generator refuses when the node's
document lacks a field named here or states another `rpcversion`.

#### `yed_gettag`

```json
{
  "version": 1,
  "payoutScheme": "p2pkh"
}
```

#### `yed_getprice`

```json
{
  "tag": {
    "payoutScheme": "p2pkh"
  }
}
```

#### `yed_getinfo`

```json
{
  "rpcversion": 11
}
```
