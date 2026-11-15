# Release-candidate qualification

## In plain words

Before a Ycash node release goes to the practice networks, it is run, as released, together with
every program around it: the wallets, the light-wallet server, the pool, the chain visualizer, the
agent-payment library and the bridge attestor, at exactly the versions its release train names
(`releases/v<version>.yaml`). This directory is the harness that does that. It lives in the
workspace, not in the node's repository, so fixing the harness never changes the node commit being
qualified: the node's tag names the node alone, and every run records the harness commit beside it.

(Until beta3 the harness was ycash6's `qa/yellowback-rc-qualify.sh`, `qa/yellowback-rc-crossline.py`
and `.github/workflows/rc-qualify.yml`. In beta2 a harness fix moved the node's head during
qualification; process requirement P-1 of the beta3 run moved it here, beta3 plan B3-D3.)

## What is here

| File | What it does |
|---|---|
| `rc-qualify.sh` | The steps, one command each: `train`, `pins`, `install`, `walk`, `yew`, `x402`, `hawkeye`, `yecwallet`, `cross-line`, `ceremony` (usage at the top of the file) |
| `rc-crossline.py` | Step 3: ycash-dd (and optionally kogany) nodes on a running ycash6 devnet; block, vault-state and YED-state hashes compared every 100 blocks |
| `rc-record.py` | Step 1's evidence check and the run's record (`rc-qualify.json`) |
| `test_rc_qualify.py` | The harness's self-tests: no node, stub binaries, the real train files |
| [`../.github/workflows/rc-qualify.yml`](../.github/workflows/rc-qualify.yml) | The workflow: `workflow_dispatch` only, input `train` |

The node's own tools stay in the node: the devnet (`contrib/yellowback/devnet`), the attest agent,
the ceremony (`contrib/testnet/ceremony`), the test framework (`qa/rpc-tests`) and the CI
prerequisites action are read from ycash6 **at the train's commit**, because they are part of what
is qualified.

## The steps

| Step | What | Evidence |
|---|---|---|
| train | the train file at the run's commit; a skeleton (any `placeholder`) is refused; its ycash6 tag names its ycash6 commit, or a proving run built that commit (or an ancestor differing only in `qa/`, `doc/`, `.github/` files the release build does not read) | `rc-train` artifact |
| candidate | the tag's release (draft or published) or the proving run's `release-signed` artifact: `SHA256SUMS`, its cosign signature by ycash6's release workflow at the tag (or the proving branch), the linux_x86_64 package's build provenance | `rc-package` artifact |
| 1 | the node's own suites: a ycash6 `yellowback-tests.yml` run of tier `all` (its `push tier` and `nightly` jobs), green at the train's ycash6 commit or the built commit, given by run id | the run id in the record |
| 2 | upgrade-walk with chain-viz, lightwalletd fork and baseline and yolo; YEW's devnet suites; x402's `test:devnet`; Hawkeye's `scenario demo`; YecWallet's QTest devnet cases; each at its train pin | `rc-ecosystem-<leg>` |
| 3 | ycash-dd built at the train's commit; two of its nodes on the devnet of the release binary; the three hashes agree at every 100th height | `rc-cross-line` |
| 4 | the launch ceremony rehearsed on regtest, fast and slow profiles | `rc-ceremony` |

**Step 1 changed with the move.** The ycash6 workflow used to call the node's test workflow with the
release package swapped in. A workflow in another repository cannot do that (a called workflow
checks out its caller), and polling a dispatched run is not allowed (it bills a runner for waiting).
So step 1 is now evidence: the coordinator runs the node's suites in ycash6 and gives the finished
run's id. Those suites run a CI build of the same commit, not the package's binaries; steps 2 to 4
run the package.

## Running it in CI

From the workspace's `upgrade/vault` (or a branch carrying the train under review):

```
# 1. the node's own suites at the train's ycash6 commit, in ycash6 (tier all); note the run id
env -u GH_TOKEN gh workflow run yellowback-tests.yml -R boyfromcave/ycash6 --ref v<V> -f tier=all
# 2. once it is green, the qualification
env -u GH_TOKEN gh workflow run rc-qualify.yml -R boyfromcave/yellowback --ref upgrade/vault \
  -f train=releases/v<V>.yaml -f node_suites_run=<run id of 1>
```

Before the tag exists, add `-f proving_run=<id>`: a green, strict `yellowback-release.yml` dispatch
in ycash6 (its `release-dry-run` job green) on `upgrade/vault` or `release/*`. The train's
`ycash6.commit` is then the commit the tag will be cut at.

The switches `ecosystem`, `cross_line` and `ceremony` (default on) turn steps off for a rerun of
one part; a step that did not run is `skipped` in the record, and the record is then not a
qualification.

**A pass**: every job green, the record job's last step ("Qualified?") green, and the record says
`"qualified": true` with every `steps` value `success`. The record (artifact `rc-qualify`, also in
the run's summary) names `commit` (the train's ycash6 commit), `built_commit`, `harness_commit` (this
repository at the run), `train_file`, the train's pins, the package's sha256 and the run. On a
**draft** release it is also attached as `rc-qualify-<run id>.json`; a published release is never
changed.

**Token.** ycash6 is public: a published release, its signature and attestations need no secret. A
draft release, a proving run's artifact and attaching the record to a draft need the repository
secret `RC_QUALIFY_YCASH6_TOKEN`: a fine-grained token for `boyfromcave/ycash6` only, Contents read
and write (GitHub shows drafts to writers only) and Actions read. Without it those cases fail
plainly.

**Cost.** The workspace repository is public, so its standard runners are free. No job waits on
another workflow. `vars.RC_QUALIFY_RUNNER` can name a larger runner for step 2, which is billed.

## Running it locally

The self-tests (seconds, no node):

```
.venv/bin/python qualify/test_rc_qualify.py -v
```

Read a train (a skeleton is refused, exit 1):

```
qualify/rc-qualify.sh train releases/v6.22.0-beta2.yaml
```

A step on a laptop: a scratch directory `WS` whose `ycash6` is the ycash6 tree at the train's
commit, with the release binaries installed into its `src/` (Linux packages; on macOS install the
binaries of the macOS package by hand, the steps only need `src/ycashd`, `src/ycash-cli`,
`src/ycash-tx`):

```
WS=$(mktemp -d); git -C ycash6 worktree add --detach "$WS/ycash6" <train ycash6 commit>
qualify/rc-qualify.sh install <dir with the package and SHA256SUMS> "$WS/ycash6"
set -a; eval "$(qualify/rc-qualify.sh train releases/v<V>.yaml)"; set +a
WS=$WS PYTHON=$PWD/.venv/bin/python qualify/rc-qualify.sh walk     # or yew, x402, hawkeye, yecwallet, ceremony
WS=$WS PYTHON=$PWD/.venv/bin/python qualify/rc-qualify.sh cross-line <ycash-dd tree built at the train's commit>
```

Each step clones its clients beside `$WS/ycash6`, builds them into their own `target/`, and writes
its evidence under `$WS/rc-out`. Long steps; on a shared machine run one at a time.
