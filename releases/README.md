# Release trains

## In plain words

A new version of the Ycash node is only tested together with the programs around it: the wallets,
the light-wallet server, the mining pool, the chain visualizer, the agent-payment library and the
bridge attestor. Each file here is the list of exactly which version (which commit) of each of them
one node release was tested with. It is written before the release is tagged, checked by CI, and
read by the release-candidate qualification (`rc-qualify` in ycash6), so "tested together" always
means the same set of commits.

## The file

One file per release, `releases/v<version>.yaml` (testnet plan §5.4), in the flat shape of
`repos.yaml`: an unindented `section:` line, then two-space `key: value` fields; a trailing
`# comment` is ignored; nothing else is allowed. `none` marks a value that is not set yet.

```yaml
release:
  version: 6.22.0-rc1        # 6.22.N, 6.22.N-rcM or 6.22.N-betaM
  rpcversion: 8              # the node's YELLOWBACK_RPC_VERSION
  workspace: <40-hex>        # the workspace commit whose spec and contract copies the clients carry
testnet:
  fast-vault-height: 510400  # testnet-yb-fast's UPGRADE_VAULT height
  fast-set-id: <64-hex>      # its YED attestor set, from its launch ceremony
  slow-vault-height: none    # testnet-yb-slow: set by its first rc (T-15)
  slow-set-id: none          # created after slow's activation; a later rc names it
  bundle-height: none        # H_B of the state bundle the release pins
ycash6:
  commit: <40-hex>
  tag: v6.22.0-rc1
ycash-dd:
  commit: <40-hex>
  tag: vault-params/v6.22.0-rc1
librustzcash6:
  commit: <40-hex>
lightwalletd-dd:
  commit: <40-hex>
yecwallet-dd:
  commit: <40-hex>
yew:
  commit: <40-hex>
yolo:
  commit: <40-hex>
chain-viz:
  commit: <40-hex>
x402-ycash:
  commit: <40-hex>
hawkeye:
  commit: <40-hex>
wyec:
  commit: <40-hex>
```

Every component is required. The testnet values follow the node's own release rules for the stage
(`qa/yellowback-vault-params.py` on both node lines): an rc names testnet-yb-fast's height and set;
a set never appears without its height; a final release names both `yb` networks.

## The check

`make release-train-check` (CI: `workspace-check.yml`, job `release-train`) runs
`scripts/release-train.py check --online` on every train:

- every commit is on its repository's `upgrade/vault`;
- `ycash6`'s and `ycash-dd`'s tags, once they exist, name the train's commits;
- the node lines' `YELLOWBACK_RPC_VERSION` and every client contract copy state the train's `rpcversion`;
- the clients' contract copies match the node's, by the workspace's own `scripts/extract_spec.py`
  at `release.workspace` (the `make spec-check` logic for that rpcversion's line);
- hawkeye fetches the train's wyec commit.

`scripts/release-train.py pins releases/v<version>.yaml` prints the train as `TRAIN_*` lines. That
is how `rc-qualify` takes its pins on the release path, in place of the push tier's
`YOLO_COMMIT`, `CHAINVIZ_COMMIT`, `LWD_COMMIT` and `YB_WORKSPACE_COMMIT`.

## Order

1. The ceremony and the node's release parameters are done; the commits are known.
2. Add `releases/v<version>.yaml` here by pull request; the check passes (tags may not exist yet).
3. Tag ycash-dd `vault-params/v<version>`, then ycash6 `v<version>`, on those commits.
   ycash6's release workflow drafts the release and starts `rc-qualify`, which reads this file
   from the workspace's `upgrade/vault`.
