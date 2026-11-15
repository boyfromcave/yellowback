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
| `rc-suites.py` | Step 1 against the package: the node's own functional lists and shards, read from ycash6's `yellowback-tests.yml` at the train's commit, and its `tests_config.ini` |
| `rc-record.py` | Step 1's CI-build evidence check (with the client pins) and the run's record (`rc-qualify.json`) |
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
| 1, package | the node's merge-gate functional lists (yellowback in 4 shards, stock in 2, exactly as its `functional` job shards them) run by its own `rpc-tests.py` on the **package's** `ycashd`, `ycash-cli`, `ycash-tx`, with yolo and chain-viz built at their train pins | `1-node-suites-package`; logs on failure |
| 1, CI build | the tiers that need a build of their own (the unit tests, the nightly's suites, lockorder, sanitizers, coverage): a ycash6 `yellowback-tests.yml` run of tier `all` (its `push tier` and `nightly` jobs), green at the train's ycash6 commit or the built commit, given by run id, whose default client pins (`YOLO_COMMIT`, `CHAINVIZ_COMMIT`, `LWD_COMMIT`, `YB_WORKSPACE_COMMIT`) are the train's | `1-node-suites-ci-build`, the run id |
| 2 | upgrade-walk with chain-viz, lightwalletd fork and baseline and yolo; YEW's devnet suites; x402's `test:devnet`; Hawkeye's `scenario demo`; YecWallet's QTest devnet cases; each at its train pin | `rc-ecosystem-<leg>` |
| 3 | ycash-dd built at the train's commit; two of its nodes on the devnet of the release binary; the three hashes agree at every 100th height | `rc-cross-line` |
| 4 | the launch ceremony rehearsed on regtest, fast and slow profiles | `rc-ceremony` |

**What step 1 runs on which binary.** Before the move, ycash6's rc-qualify called the node's test
workflow (tier `all`) with the package swapped in: every functional shard and the nightly's suites ran
the package's binaries; the unit tests and the instrumented variants were CI builds there too (no
`test_bitcoin` in a package). The beta2 run took about 950 runner-minutes on 17 runners, 4 hours
of wall time: build 6 min, the six functional shards 171, the nightly 249, lockorder 220,
coverage 243, sanitizers 48, the rest about 15.

A workflow in another repository cannot call that workflow on the node's tree (a called workflow
checks out its caller), and waiting on a dispatched run would bill a runner for nothing. So the
functional shards run here, on the package, from the node tree at the train's commit with its own
lists and test framework (no build: a `tests_config.ini` is written for the tree). About 180
runner-minutes on 7 runners (sidecars, six shards), about 50 minutes of wall time, free on this
public repository. What needs a build of its own comes from the node's own tier-all run: the
unit tests and variants as before, and **the nightly's suites, which now run a CI build of the same
commit rather than the package**. That is the one narrowing; the record says which binary each half
ran (`node_suites_binary`).

## Before you qualify

- The train `releases/v<V>.yaml` is filled in (no `placeholder`), merged, and `make release-train-check` passes. Every commit is on its repository's `upgrade/vault` or a `release/*` branch.
- **ycash6's default client pins are aligned with the train before the candidate is cut.** The `YOLO_COMMIT`, `CHAINVIZ_COMMIT`, `LWD_COMMIT` and `YB_WORKSPACE_COMMIT` defaults in its `yellowback-tests.yml` must equal the train's yolo, chain-viz, lightwalletd-dd and `release.workspace` commits. Step 1's CI-build half refuses a run with other pins, and a dispatch cannot override them.
- The node's own tier-all run is green at the train's ycash6 commit (its id is `node_suites_run`).
- For a draft, the secret `RC_QUALIFY_YCASH6_TOKEN` is set ("Token" below).

**The beta2 proof (the coordinator's ruling).** The move was proved by re-qualifying the unchanged beta2 commits. ycash6 at fbc9f625 pins yolo, chain-viz, lightwalletd-dd and workspace commits that differ from the beta2 train's, so the CI-build half of step 1 fails on the pin check. The check stands as written. That run proves the move if all of these are green:

- train;
- candidate;
- the package shards;
- steps 2 to 4.

The ONLY failure may be that client-pin mismatch, which the record names under
`node_suites_ci_build_problems`. A `qualified: true` record is not expected for beta2. From beta3 on, the pins are aligned first (above).

## Running it in CI

From the workspace's `upgrade/vault` (or a branch carrying the train under review):

```
# 1. the node's own tiers at the train's ycash6 commit, in ycash6 (tier all; its default client pins
#    must be the train's); note the run id
env -u GH_TOKEN gh workflow run yellowback-tests.yml -R boyfromcave/ycash6 --ref v<V> -f tier=all
# 2. once it is green, the qualification
env -u GH_TOKEN gh workflow run rc-qualify.yml -R boyfromcave/yellowback --ref upgrade/vault \
  -f train=releases/v<V>.yaml -f node_suites_run=<run id of 1>
```

Before the tag exists, add `-f proving_run=<id>`: a green, strict `yellowback-release.yml` dispatch
in ycash6 (its `release-dry-run` job green) on `upgrade/vault` or `release/*`. The train's
`ycash6.commit` is then the commit the tag will be cut at.

The switches `node_suites` (the package shards), `ecosystem`, `cross_line` and `ceremony` (default on) turn steps off for a rerun of
one part; a step that did not run is `skipped` in the record, and the record is then not a
qualification.

**A pass**: every job green, the record job's last step ("Qualified?") green, and the record says
`"qualified": true` with every `steps` value `success`. The record (artifact `rc-qualify`, also in
the run's summary) names `commit` (the train's ycash6 commit), `built_commit`, `harness_commit` (this
repository at the run), `train_file`, the train's pins, the package's sha256 and the run. On a
**draft** release it is also attached as `rc-qualify-<run id>.json`; a published release is never
changed.

**Token.** The jobs' own `github.token` is this repository's, and GitHub scopes it to this
repository: it can read anything public in ycash6 (a published release, its attestations, its
signature, a run's jobs, a file at a commit), and probably a public run's artifacts, but it cannot
see a **draft** release. GitHub lists drafts to users with push access only. So one case needs the
repository secret `RC_QUALIFY_YCASH6_TOKEN`, a fine-grained token for `boyfromcave/ycash6` only:

- qualifying a draft (reading it, and attaching the record) needs Contents read and write. Nothing
  read-only can see a draft. The token never pushes, tags or edits code.
- a proving run's artifact needs Actions read. `github.token` alone may be enough on a public
  repository; untested.

Without the secret, published releases qualify as before and a draft fails with GitHub's answer.
The secret is used only in the steps that call the GitHub API: train (tag and proving-run checks),
candidate (downloads), the CI-build evidence check and the record. **It is never present in a job
that runs another repository's code**: the leg jobs (step 1's package shards and sidecars, steps
2 to 4) have `contents: read`, this repository's own token, and no secrets.

**Cost.** The workspace repository is public, so its standard runners are free. No job waits on
another workflow. No job restores or saves an Actions cache: the legs run another repository's code
(ycash6 and ycash-dd at the train's commits, every client at its pin), and a cache written there in
this repository's default-branch scope could be read by its other workflows.
`vars.RC_QUALIFY_RUNNER` can name a larger runner for step 2, which is billed. A full run: step 1's
package half about 180 runner-minutes, step 2 five legs of up to 6 hours each, step 3 one (ycash-dd
build plus rounds), step 4 one.

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
