# Yellowback fee structure — RPC contract delta (`rpcversion` 8)

**Revision 2 (2026-10-11). Reconciled against `q/fees` at `430002b16`** (`ycash-dd`, worktree
`wt/q-fees`), whose `doc/yellowback-rpc.md` states `rpcversion` 8 and is the truth. The machine-readable
form of [`yellowback-quantum-fees-spec.md`](yellowback-quantum-fees-spec.md) §3.4 (D-Q-23 Option D,
D-Q-23a, D-Q-24 `maxMint`, D-Q-25 supply cap, D-Q-26 network fee) for the contract generator
(`scripts/extract-spec.sh --write-fees` / `--check-fees`, `make spec-fees` / `make spec-check-fees`). It
layers on the quantum line's delta ([`yellowback-quantum-rpc-delta.md`](yellowback-quantum-rpc-delta.md)
§4.10, `rpcversion` 7) exactly as that one layers on the in-term plan's §4.1: the generator reads only the
`### 4.11` section below, wherever it lives, and the coordinator may move it into the quantum plan verbatim
(then point `PLAN_FEES` in `scripts/extract_spec.py` at the plan). Where this file and the fees spec differ,
the spec wins and this file is corrected.

**Revision history.** Revision 1 was drafted from the spec while the node document still stated
`rpcversion` 7. Revision 2 takes the implementation's names: `yed_getfeepayee` loses its `collateralZat`
argument and its `feeZat` field (heading and removed list below); the fields the implementation added are
named so the document must keep them (`yed_listclaimable[].pMint`; `params.supplyCap.issuedBeforeStartZat`,
`maxVaultShareBps`, `vaultShareFloorCents`, `maxVaultCents`; `params.fees.network.fallbackZatPerKB`;
`params.fees.network.yellowback.maxTxFeeUsdMicro`, `maxTxFeeZat`, `maxTxFeeCeilingZat`, review M-1 and
D-Q-26); and every network-fee and supply-cap sample is worked at one attested price, **$0.40/YEC** (`400000` µUSD, the D-Q-26
reference), so the merged contract is self-consistent: plain $0.02/KB = 5,000,000 zat/KB, Yellowback
$0.05/KB = 12,500,000 zat/KB, the Yellowback cap min(max(`-maxtxfee` 0.1 YEC, $2 = 5 YEC), 10 YEC) =
500,000,000 zat; a circulating supply of 12,345,678 YEC is worth $4,938,271.20, its 15 % cap 74,074,068
cents and MINT-6b's per-vault bound max(10 %, $10,000) = 7,407,406 cents; the $1 floor is 250,000,000 zat
at $0.40 (`yed_estimatefee`'s sample). The vault rows keep the document's sample vault, minted at $1.985
(`pMint` 1985000, 2,518.89 YEC for $1,000 at 500 %) and claimable at $0.40: its $10 protocol fee is
503,778,338 zat and its in-term early fee (5 % of the debt) 2,518,891,688 zat.

### 4.11 RPC contract delta (`rpcversion` 8)

The fees line's RPC contract (`upgrade/quantum-vaults` after the D-Q-23/24/25 fee change) is the quantum
line's (§4.10 of the quantum delta applied to the node's `doc/yellowback-rpc.md`) with the deltas below,
which are fees spec §3.4 as a client sees them. The generator reads this section as it reads the quantum
delta's §4.10: each ```json block belongs to the `yed_*` command named in backticks on the nearest non-blank
line above it, and a heading's text after the name is that command's arguments. A block is merged into the
command's `returns` (objects key by key, a one-element row array into its row, any other value replaced;
this section wins on values). The generator refuses when the node's document lacks a field or command named
here, gives a command other arguments than a heading here states, states another `rpcversion`, or still
documents a path the ```removed list names, so this section and the document cannot drift. The quantum
line's contract (`make spec-quantum`, `rpcversion` 7) is untouched by it. A removed path may be dotted
below the command (`cmd.a.b`, `cmd[].a.b` for a row): the removals of this version are nested under
`params`.

Changed meanings (no shape change, so no block): `params.pq.feeRateZatPerKB` is now equal to
`params.fees.network.plain.zatPerKB`, so `rpcversion`-7 clients keep working; `params.earlyRedeemFeeBps`
and `classes[].earlyRedeemFeeBps` are now bps **of the debt** (IT-9′), no longer of the collateral;
`yed_listclaimable[].feeZat`, `yed_estimateredeem.feeZat`, `yed_estimateclaim`'s and `yed_redeem` /
`yed_claim`'s fee amounts are the same fields on the new base (the tiered dollar protocol fee at the vault's
`pMint`, fees spec §1.3); `yed_estimatecollateral.requiredZatFloored` is `requiredZat` rounded up to 1,000 zat
(MINT-5′ drops the `4 × feeMin` clause, spec §2.3). The fees of every PQ or YED transaction follow the
attested price (`params.fees.network`, spec §3.1).

Removed (with the `yed_estimatefee` signature change, the reason for the bump: the flat `feeMin` / `feeBps`
fee no longer exists). `yed_getfeepayee` loses its `collateralZat` argument — its heading below states the new
argument list, which the generator compares with the document's — and its `feeZat` field: the fee is a
property of the debt and the mint price, quoted by the estimate RPCs (`yed_estimatefee`,
`yed_estimatecollateral` for a mint; `yed_estimateredeem`, `yed_listclaimable` for a spend). Removed fields,
one path per line, `cmd.field` for an object result and `cmd[].field` for a row of a list result, dotted for a
nested field:

```removed
yed_getinfo.params.feeMinZat
yed_getinfo.params.feeBps
yed_getfeepayee.feeZat
```

#### `yed_getinfo`

```json
{
  "rpcversion": 8,
  "params": {
    "maxMintCents": 10000000,
    "fees": {
      "protocol": {
        "bands": [ { "uptoCents": 100000, "bps": 100 }, { "uptoCents": 1000000, "bps": 50 }, { "uptoCents": null, "bps": 10 } ],
        "floorCents": 100,
        "attestFeeBps": 5000,
        "priceSource": "pMint"
      },
      "earlyRedeemFeeBps": [ 500, 250, 100 ],
      "network": {
        "priceMicroUsd": 400000,
        "priceSource": "tip",
        "plain": { "usdPerKBMicro": 20000, "zatPerKB": 5000000 },
        "yellowback": {
          "usdPerKBMicro": 50000,
          "zatPerKB": 12500000,
          "maxTxFeeUsdMicro": 2000000,
          "maxTxFeeCeilingZat": 1000000000,
          "maxTxFeeZat": 500000000
        },
        "floorZatPerKB": 5000,
        "fallbackZatPerKB": 100,
        "flatZat": 1000,
        "maxTxFeeZat": 10000000
      }
    },
    "supplyCap": {
      "circulatingZat": 1234567800000000,
      "issuedBeforeStartZat": 1200000000000000,
      "priceMicroUsd": 400000,
      "capCents": 74074068,
      "maxVaultShareBps": 1000,
      "vaultShareFloorCents": 1000000,
      "maxVaultCents": 7407406
    }
  }
}
```

Notes. `fees.protocol.bands` are the FEE-1′ brackets in order, the last with `uptoCents: null` (unbounded;
`FeeBand.uptoCents = 0` in `params.h`, spec §1.1); `floorCents` the $1 per-action floor; `priceSource` names
the price the protocol fee is struck at (the vault's stored `pMint`). `fees.network` is the policy rate of
spec §3.1: `priceMicroUsd` is the **highest of the tip's window medians** (review M-1; `null` and
`priceSource: "fallback"` while any halt bit is set or no median exists, then both `zatPerKB` are
`fallbackZatPerKB`, the `-pqfeerate` rate, default the relay floor); `plain` / `yellowback` the two targets
(`-pqfeeusdperkb` $0.02, `-yellowbackfeeusdperkb` $0.05; D-Q-26) and the rate each gives, never below
`floorZatPerKB` = max(5,000 zat/KB, `-pqfeerate`); `yellowback.maxTxFeeZat` is the Yellowback cap
min(max(`-maxtxfee`, `maxTxFeeUsdMicro` at the price), `maxTxFeeCeilingZat` = `-yellowbackmaxtxfee`, default
10 YEC), which caps plain post-quantum transfers too (D-Q-26); `flatZat` the wallet's flat floor
(= `params.feeZat`); `network.maxTxFeeZat` is `-maxtxfee` (0.1 YEC). `supplyCap` is D-Q-25's base for
MINT-6: `circulatingZat` the closed-form circulating supply (`Snapshots[R].issuedZat`, seeded at the start
height with `issuedBeforeStartZat` = `CirculatingSupplyAt(startHeight − 1)`), valued at `priceMicroUsd`
(the cross-section `xMint`), `capCents` = 15 % of that (`supplyCapBps`; `null` when the price is undefined;
`supplyCapCents` at the top level keeps reporting the same cap), and MINT-6b's per-vault bound
`maxVaultCents` = max(`maxVaultShareBps` of the cap, `vaultShareFloorCents`) (`null` with the cap).

#### `yed_getfeepayee <refHeight> [selectorHex]`

```json
{ "policy": { "penaltyBlocks": 12, "accuracyWindow": 24, "tiltBps": 10000 } }
```

The shape is the quantum line's less `feeZat`; the block only names the command so its heading's argument
list is checked (was `<refHeight> <collateralZat> [selectorHex]`).

#### `yed_getvault`

```json
{ "pMint": 1985000 }
```

#### `yed_listvaults`

```json
[ { "pMint": 1985000 } ]
```

#### `yed_listpositions`

```json
[ { "pMint": 1985000 } ]
```

#### `yed_listclaimable`

```json
[ { "pMint": 1985000, "feeZat": 503778338, "attestFeeZat": 251889169 } ]
```

The vault's stored mint price (`VaultRecord.pMint`, schema 9, spec §1.2): micro-USD per YEC, the fee price
of every later spend; never `null` for a vault that exists (`1..PRICE_MAX`). A claimable row's `feeZat` is
the FEE-1′ fee of its debt at that price (RED-3′: $10 on the sample's $1,000 debt at its $1.985 mint price,
`ceil(10⁷ units × 10⁸ / 1,985,000)`) and `attestFeeZat` half of it, floored (AFEE-1′); the claim itself is
priced at the tip (`pClaim` $0.40, the D-Q-26 reference, after a fall from $1.985).

#### `yed_estimatefee <mintedCents> [priceMicroUsd]`

```json
{
  "feeCents": 100,
  "feeZat": 250000000,
  "pMint": 400000,
  "attestFeeZat": 125000000
}
```

A signature change (was `yed_estimatefee <collateralZat>` → `{ feeZat }`): the FEE-1′ protocol fee of a debt
of `mintedCents` — `feeCents` = `ProtocolFeeCents` (spec §1.3; the sample is a $100 debt at the $1 floor),
`feeZat` at `pMint` (the estimate's price: `priceMicroUsd` when given, else the current reference price as
`yed_estimatecollateral` picks it; `null` with `feeZat` when undefined), `attestFeeZat` =
`AttestFeeZat(feeZat, attestFeeBps)`.

#### `yed_estimatecollateral <cents> <lockBlocks> [priceMicroUsd]`

```json
{
  "protocolFeeCents": 1000,
  "protocolFeeZat": 503778338,
  "attestFeeZat": 251889169
}
```

`protocolFeeCents` / `protocolFeeZat` are the mint's fee at the estimate's `pMint` (the document's sample, a
$1,000 mint at $1.985: 1 % = $10);
`attestFeeZat` is the existing field on the new base (named so the doc must keep it).

#### `yed_estimateredeem <vaultTxid>`

```json
{
  "pMint": 1985000,
  "feeZat": 3022670026,
  "protocolFeeZat": 503778338,
  "protocolFeeCents": 1000,
  "earlyRedeemFeeZat": 2518891688,
  "earlyRedeemFeeCents": 5000,
  "earlyRedeemFeeBps": 500
}
```

A $1,000 class-A debt redeemed in term at its `pMint` $1.985: protocol $10 (1 %) = 503,778,338 zat, early
$50 (5 % of the debt) = 2,518,891,688 zat, each rounded up on its own; `feeZat` their sum.
`feeZat` stays protocol + early; `earlyRedeemFeeBps` is now of the debt (named so the doc must keep it);
`earlyRedeemFeeCents` is the early fee in dollars (what YEW shows, spec §3.4 last bullet).
