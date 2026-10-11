# Yellowback post-quantum — RPC contract delta (`rpcversion` 7)

**Revision 1 (2026-10-10).** The machine-readable form of
[`yellowback-quantum-spec.md`](yellowback-quantum-spec.md) §6.2 for the contract generator
(`scripts/extract-spec.sh --write-quantum` / `--check-quantum`, `make spec-quantum` /
`make spec-check-quantum`; spec §6.3 item 2). It is the section the Q4 agent proposed as the quantum plan's
"§4.10 RPC contract delta"; it lives in this file so the plan is not edited by the generator's author. The
coordinator may move the section below into the plan verbatim and point `PLAN_QUANTUM` in
`scripts/extract_spec.py` at the plan: the generator reads only the `### 4.10` section, wherever it is.
Where this file and the quantum spec differ, the spec wins and this file is corrected.

### 4.10 RPC contract delta (`rpcversion` 7)

The quantum line's RPC contract (`upgrade/quantum-vaults`) is the in-term line's (in-term claims plan §4.1,
itself the upgrade line's contract generated from the node's `doc/yellowback-rpc.md`) with the deltas below,
which are quantum spec §6.2 as a client sees them. The generator reads this section the way the in-term
generator reads the in-term plan's §4.1: each ```json block belongs to the `yed_*` command named in backticks
on the nearest non-blank line above it, and a heading's text after the name is that command's arguments. A
block is merged into the command's `returns` (objects key by key, a one-element row array into its row, any
other value replaced; this section wins on values). The generator refuses when the node's document lacks a
field or command named here, gives a command other arguments than a heading here states, states another
`rpcversion`, or still documents a field the ```removed list names, so this section and the document cannot
drift. The in-term line's contract (`make spec-in-term`, `rpcversion` 6) is untouched by it.

Changed meanings (no shape change, so no block): `ownerAddress` on `yed_getvault`, `yed_listvaults`,
`yed_listpositions` and `yed_listclaimable` is the owner's post-quantum address (53 characters); a MINT's
`yed_decodepayload` `version` is `4` (every other payload type stays `3`, quantum spec C-1);
`yed_validateaddress` adds the **optional** `pqscheme` (present only when `type` is `pq`; an optional field is
not in the node's example block, so it is named here and not merged); `yed_send`, `yed_sendmany`,
`yed_listtokens` and `yed_validateaddress` take either address form. The fees of `yed_mint`, `yed_redeem` and
`yed_claim` grow with the transaction's size (`params.pq.feeRateZatPerKB`, Q5).

Removed fields (the reason for the bump: no public key is on chain), one path per line, `cmd.field` for an
object result and `cmd[].field` for a row of a list result:

```removed
yed_getvault.ownerPubKey
yed_getvault.ownerKeyId
yed_listvaults[].ownerPubKey
yed_listvaults[].ownerKeyId
yed_listpositions[].ownerPubKey
yed_listpositions[].ownerKeyId
yed_decodepayload.ownerPubKey
```

#### `yed_getinfo`

```json
{
  "rpcversion": 7,
  "params": {
    "addressVersion": "2002",
    "pqAddressVersion": "5710",
    "pq": {
      "schemes": [ 1 ],
      "falconActive": false,
      "falconHeight": -1,
      "feeRateZatPerKB": 100,
      "plainAddressVersion": "4c51"
    },
    "attest": { "mintPayloadVersion": 4 }
  }
}
```

#### `yed_getvault`

```json
{
  "ownerScheme": 1,
  "ownerHash": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
}
```

#### `yed_listvaults`

```json
[ {
  "ownerScheme": 1,
  "ownerHash": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
} ]
```

#### `yed_listpositions`

```json
[ {
  "ownerScheme": 1,
  "ownerHash": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
} ]
```

#### `yed_decodepayload <hex>`

```json
{
  "version": 4,
  "ownerScheme": 1,
  "ownerHash": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
}
```

#### `yed_mint`

```json
{ "ownerAddress": "yrExamplePQOwnerAddress11111111111111111111111111111" }
```

#### `yed_validateaddress <address>`

```json
{ "type": "p2pkh" }
```

#### `yed_getnewaddress [type]`

```json
"yrExampleOwnerAddress111111111111111"
```

#### The vault primitive (`doc/vault-rpc-contract.json`)

The primitive's RPCs are not in the `yed_*` contract: the node's `qa/vault-rpc-contract.py` generates
`doc/vault-rpc-contract.json` from `doc/vault-rpc.md`, and it carries no `rpcversion` (quantum spec §6.1). The
generator only checks that file, in each node tree it checks, against the block below, so the two contracts
move together: every `types` entry is defined; every `methods` entry exists, with each named parameter (a
dotted name is a field of an object parameter) and each named result field; and no `absent` name is present
(`vault_lock`'s former `ownerkey`, refused with `ownerkey-removed`).

```json
{
  "types": [ "pqkeyid" ],
  "methods": {
    "vault_getnewowner": { "params": [ "scheme" ], "result": [ "scheme", "keyhash", "owner", "address" ] },
    "vault_lock": { "params": [ "params.owner" ], "result": [ "owner" ], "absent": [ "params.ownerkey", "ownerkey" ] }
  }
}
```
