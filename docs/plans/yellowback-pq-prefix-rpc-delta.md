# Yellowback scheme-visible post-quantum prefixes — RPC contract delta (`rpcversion` 9)

**Revision 1 (2026-11-11).** The machine-readable form of decision D-9 as a client sees it
([`yellowback-quantum-spec.md`](yellowback-quantum-spec.md) §4.1) for the contract generator
(`scripts/extract-spec.sh --write-prefix` / `--check-prefix`, `make spec-prefix` / `make spec-check-prefix`). It
layers on the fees line's delta ([`yellowback-quantum-fees-rpc-delta.md`](yellowback-quantum-fees-rpc-delta.md)
§4.11, `rpcversion` 8) exactly as that one layers on the quantum delta: the generator reads only the `### 4.12`
section below. A node tree whose `doc/yellowback-rpc.md` states `rpcversion` 8 stays on the fees line, untouched.
Where this file and the quantum spec differ, the spec wins and this file is corrected.

**What changes shape (old → new), for the ports.**

| Field | `rpcversion` 8 | `rpcversion` 9 |
|---|---|---|
| `yed_getinfo.params.pqAddressVersion` | hex string, the 2-byte YED PQ version (`"5710"` regtest), followed by a scheme byte | object of hex keyed by scheme number, one 3-byte version per scheme (`{"1": "5715aa", "2": "571444"}` regtest) |
| `yed_getinfo.params.pq.plainAddressVersion` | hex string, the 2-byte plain-YEC PQ version (`"4c51"` regtest) | object of hex keyed by scheme number (`{"1": "4c5655", "2": "4c54ef"}` regtest) |

**The keys and values.** Each object is keyed by the scheme number as a string: `"1"` = SLH-DSA-SHA2-128s, `"2"` =
FN-DSA-512. Both keys are always present, on every network, before and after Falcon is active (the address of a key
is defined whether or not its scheme may be spent yet); a later scheme adds a key. The values (lower-case hex, 3 bytes):

| Network | `pqAddressVersion` (YED) | `pq.plainAddressVersion` (plain YEC) |
|---|---|---|
| main | `{"1": "56b044", "2": "56aede"}` (`ybs…` / `ybf…`) | `{"1": "4dde6a", "2": "4ddd04"}` (`sqs…` / `sqf…`) |
| test | `{"1": "572330", "2": "5721c9"}` (`yts…` / `ytf…`) | `{"1": "4f667f", "2": "4f6519"}` (`tqs…` / `tqf…`) |
| regtest | `{"1": "5715aa", "2": "571444"}` (`yrs…` / `yrf…`) | `{"1": "4c5655", "2": "4c54ef"}` (`rqs…` / `rqf…`) |

An address is Base58Check(version ‖ 32-byte keyHash), 53 characters; the shared vectors are
`src/test/data/pq_address_vectors.json` in ycash-dd.

**Client copies and the release gate.** While a client (YecWallet, lightwalletd) still carries its rpcversion-8
contract copy, plain `make spec-check` skips that copy, loudly ("SKIPPED (client one version behind)"), and only when
it is exactly one version behind the node; anything further behind fails. The gate is the release train:
`scripts/release-train.py` refuses a train whose client copy states another rpcversion than the train's, so no
release ships with a skipped copy.

Every post-quantum address string any RPC returns or accepts changes text (quantum spec §4.1): `sqf…`/`sqs…`,
`tqf…`/`tqs…`, `rqf…`/`rqs…` plain YEC; `ybf…`/`ybs…`, `ytf…`/`yts…`, `yrf…`/`yrs…` YED; still 53 characters, so
no other field changes type. `yed_getinfo.params.addressVersion` (the 35-character ECC YED form) is unchanged.

### 4.12 RPC contract delta (`rpcversion` 9)

The prefix line's RPC contract is the fees line's (§4.11 applied) with the deltas below. The generator reads this
section as it reads the fees delta's §4.11: each ```json block belongs to the `yed_*` command named in backticks on
the nearest non-blank line above it, merged into that command's `returns` (objects key by key, any other value
replaced; this section wins on values). The generator refuses when the node's document lacks a field named here
or states another `rpcversion`. A ```reshaped path is a field whose type this line changes (an earlier delta gave it
as a hex string): the generator takes its value from the node's document before merging, and refuses when the
document does not have it, when no json block below pins its new shape, or when the document's object has other keys
than the block's.

```reshaped
yed_getinfo.params.pqAddressVersion
yed_getinfo.params.pq.plainAddressVersion
```

#### `yed_getinfo`

```json
{
  "rpcversion": 9,
  "params": {
    "pqAddressVersion": { "1": "5715aa", "2": "571444" },
    "pq": {
      "plainAddressVersion": { "1": "4c5655", "2": "4c54ef" }
    }
  }
}
```
