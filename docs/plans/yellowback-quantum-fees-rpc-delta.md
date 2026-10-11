# Yellowback fee structure — RPC contract delta (`rpcversion` 8)

**Revision 1 (2026-10-11). Draft — to reconcile against `q/fees`.** The machine-readable form of
[`yellowback-quantum-fees-spec.md`](yellowback-quantum-fees-spec.md) §3.4 (D-Q-23 Option D, D-Q-24
`maxMint`, D-Q-25 supply cap) for the contract generator (`scripts/extract-spec.sh --write-fees` /
`--check-fees`, `make spec-fees` / `make spec-check-fees`). It layers on the quantum line's delta
([`yellowback-quantum-rpc-delta.md`](yellowback-quantum-rpc-delta.md) §4.10, `rpcversion` 7) exactly as that
one layers on the in-term plan's §4.1: the generator reads only the `### 4.11` section below, wherever it
lives, and the coordinator may move it into the quantum plan verbatim (then point `PLAN_FEES` in
`scripts/extract_spec.py` at the plan). Where this file and the fees spec differ, the spec wins and this
file is corrected.

**Drafted from the spec, not from a node tree.** When this revision was written the node implementation
(`ycash-dd` branch `q/fees`, worktree `wt/q-fees`) was at `3cb6e7cab` ("store the mint price in the vault
record", schema 9): its `doc/yellowback-rpc.md` still stated `rpcversion` 7, still documented
`params.feeMinZat` / `params.feeBps`, and carried none of the fields below. Every block in §4.11 is therefore
the spec's wording (§3.4 and, for `supplyCap`, D-Q-25 as the owner stated it) and is **to be reconciled
against `q/fees`** once its document states `rpcversion` 8: the generator refuses any field, command or
argument list the two disagree on, so the reconciliation is mechanical (`--check-fees` names each one).
Entries whose final name is least certain are marked *(reconcile)* in the notes.

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

Removed fields (with the `yed_estimatefee` signature change, the reason for the bump: the flat `feeMin` /
`feeBps` fee no longer exists), one path per line, `cmd.field` for an object result and `cmd[].field` for a
row of a list result, dotted for a nested field:

```removed
yed_getinfo.params.feeMinZat
yed_getinfo.params.feeBps
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
        "priceMicroUsd": 18000,
        "priceSource": "tip",
        "plain": { "usdPerKBMicro": 20000, "zatPerKB": 111112 },
        "yellowback": { "usdPerKBMicro": 50000, "zatPerKB": 277778 },
        "floorZatPerKB": 100,
        "flatZat": 1000,
        "maxTxFeeZat": 10000000
      }
    },
    "supplyCap": {
      "circulatingZat": 1234567800000000,
      "priceMicroUsd": 18000,
      "capCents": 33333330
    }
  }
}
```

Notes. `fees.protocol.bands` are the FEE-1′ brackets in order, the last with `uptoCents: null` (unbounded;
`FeeBand.uptoCents = 0` in `params.h`, spec §1.1); `floorCents` the $1 per-action floor; `priceSource` names
the price the protocol fee is struck at (the vault's stored `pMint`). `fees.network` is the policy rate of
spec §3.1: `priceMicroUsd` is `Snapshots[tip].pMint` (`null` and `priceSource: "fallback"` when undefined,
then both `zatPerKB` are `-pqfeerate`); `plain` / `yellowback` the two targets (`-pqfeeusdperkb`,
`-yellowbackfeeusdperkb`) and the rate each gives; `floorZatPerKB` the relay floor, `flatZat` the wallet's
flat floor (= `params.feeZat`), `maxTxFeeZat` the cap. `supplyCap` is D-Q-25's base for MINT-6: the
closed-form circulating supply at the tip, the attested price it is valued at and the resulting cap in cents
(`null` when the price is undefined; `supplyCapCents` at the top level keeps reporting the same cap).
*(reconcile)*: `supplyCap` has no spec paragraph yet — its three names follow the owner's D-Q-25 wording and
the top-level `supplyCapCents` convention; `fees.network.priceMicroUsd` is the spec's name where the task
brief said `price`. The remaining names are spec §3.4's verbatim.

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

The vault's stored mint price (`VaultRecord.pMint`, schema 9, spec §1.2): micro-USD per YEC, the fee price
of every later spend; never `null` for a vault that exists (`1..PRICE_MAX`).

#### `yed_estimatefee <mintedCents> [priceMicroUsd]`

```json
{
  "feeCents": 100,
  "feeZat": 5555555556,
  "pMint": 18000,
  "attestFeeZat": 2777777778
}
```

A signature change (was `yed_estimatefee <collateralZat>` → `{ feeZat }`): the FEE-1′ protocol fee of a debt
of `mintedCents` — `feeCents` = `ProtocolFeeCents` (spec §1.3), `feeZat` at `pMint` (the estimate's price:
`priceMicroUsd` when given, else the current reference price as `yed_estimatecollateral` picks it; `null`
with `feeZat` when undefined), `attestFeeZat` = `AttestFeeZat(feeZat, attestFeeBps)`. *(reconcile)*: the
argument name `priceMicroUsd` mirrors `yed_estimatecollateral`'s override; the spec writes the signature as
`mintedCents ( priceMicroUsd )`.

#### `yed_estimatecollateral <cents> <lockBlocks> [priceMicroUsd]`

```json
{
  "protocolFeeCents": 100,
  "protocolFeeZat": 5037783375,
  "attestFeeZat": 2518891688
}
```

`protocolFeeCents` / `protocolFeeZat` are the mint's fee at the estimate's `pMint`; `attestFeeZat` is the
existing field on the new base (named so the doc must keep it).

#### `yed_estimateredeem <vaultTxid>`

```json
{
  "pMint": 1985000,
  "protocolFeeZat": 5037783375,
  "protocolFeeCents": 100,
  "earlyRedeemFeeCents": 5000,
  "earlyRedeemFeeBps": 500
}
```

`feeZat` stays protocol + early; `earlyRedeemFeeBps` is now of the debt (named so the doc must keep it);
`earlyRedeemFeeCents` is the early fee in dollars (what YEW shows, spec §3.4 last bullet).
