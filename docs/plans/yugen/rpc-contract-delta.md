# Yugen line — RPC contract delta (`rpcversion` 12)

**Revision 1 (2026-11-27).** The machine-readable form of the `rpcversion` 11 → 12 step of the Yugen line (ycash6
`upgrade/yugen`, `doc/yugen-node.md` decision Y-6: "the Yugen RPCs are rpcversion 12") for the contract generator
(`scripts/extract-spec.sh --write-yugen` / `--check-yugen`, `make spec-yugen` / `make spec-check-yugen`). It layers on
the beta4 line's delta ([`../beta4/rpc-contract-delta.md`](../beta4/rpc-contract-delta.md) §4.14, `rpcversion` 11)
exactly as that one layers on the beta3 delta: the generator reads only the `### 4.15` section below.

**No `yed_*` field is new and none changes shape.** The step adds RPCs outside the `yed_*` contract, all documented in
ycash6 `doc/yugen-node.md` and registered in `src/rpc/common.h` in their own group: `yugen_getinfo`,
`yugen_getblockdata`, `yugen_getanchor`, `gettransferstatus`, `submittransfer` and `submitbundle`.
`yed_getinfo.rpcversion` (and the contract's top-level `rpcversion`) becomes 12, so a client tells a Yugen node from a
beta4 node by `rpcversion >= 12` rather than by probing the Yugen calls.

**How the generator recognises the line.** ycash6 `upgrade/yugen` keeps `doc/yellowback-rpc.md` titled
`rpcversion 11`, since its `yed_*` contract is the beta4 line's; the Yugen line is the tree whose `doc/` also holds
`yugen-node.md`, and the rpcversion it states is the one in decision Y-6 there. A doc titled `rpcversion 12` or above
is the Yugen line too. ycash-dd stays on the beta4 line (decision Y-3: it recognises the Yugen upgrade and refuses
Yugen transactions and blocks; it serves none of the Yugen RPCs). kogany is not on the Yugen line, so it gets no Yugen
copies. The client contract copies (yecwallet-dd, lightwalletd-dd) are compared with ycash6's contract on this line.

## Tasks

| # | Task | Acceptance criteria |
|---|---|---|
| YC-1 | The generator gains the Yugen line (`EXTRACT_SPEC_LINE=yugen`, `--write-yugen` / `--check-yugen`, `make spec-yugen` / `make spec-check-yugen`). | A ycash6 tree with `doc/yugen-node.md` reads as the Yugen line; its contract is the beta4 contract with both `rpcversion` fields at 12 and nothing else changed; a tree whose Y-6 states another rpcversion than §4.15 is refused. |
| YC-2 | The release train maps `rpcversion` 12 to `--check-yugen`, per component. | `scripts/release-train.py check` accepts `release.rpcversion: 12` in a 6.23.x train; ycash6 and yecwallet-dd are checked at 12 and by `--check-yugen`, ycash-dd (Y-3) and lightwalletd-dd, which stay on the vault contract, at 11 and by `--check-beta4`; the validator tests pass. |
| YC-3 | ycash6's CI "RPC contract" step compares exactly. | With `YB_WORKSPACE_COMMIT` at the published workspace `upgrade/yugen` commit carrying YC-1, the step reads the doc as the Yugen line and the committed `doc/yellowback-rpc-contract.json` equals the generator's output byte for byte; the rpcversion-12 bridge is removed. |
| YC-4 | The client copies move to 12. | yecwallet-dd and lightwalletd-dd on `upgrade/yugen` carry the ycash6 contract at 12 (`make spec-yugen`); until then `--check-yugen` skips a copy below 12, loudly, and the release train refuses it. |

### 4.15 RPC contract delta (`rpcversion` 12)

The Yugen line's RPC contract is the beta4 line's (§4.14 applied) with the delta below. The generator reads this
section as it reads the beta4 delta's §4.14: each ```json block belongs to the `yed_*` command named in backticks on
the nearest non-blank line above it, merged into that command's `returns`. The generator refuses when the node's
documents state another `rpcversion`.

#### `yed_getinfo`

```json
{
  "rpcversion": 12
}
```
