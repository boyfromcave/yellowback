# kogany × Yellowback — cross-line CI design

Revision 1, 2026-11-01. Scope: how the CI of the three node lines and their clients fits together
for the kogany port (plan [`kogany-yellowback-plan.md`](kogany-yellowback-plan.md) §5, §3b S0–S5,
§4.2 rule 4, §6; [`coordination-handoff.md`](coordination-handoff.md) §7). It covers ycash6, yew,
yolo, kogany (its side is aligned with the `ci-kogany` chunk, which restructures kogany's own
workflows; the contract here is what the other repositories consume from it), lightwalletd-dd and
chain-viz (read-only here: what they would need).

GitHub Actions stay as they are on every repository: nothing in this document turns a workflow on
or off. §9 is the checklist of settings for the Yellowback lead architect when Actions are turned on.

---

## 1. The rules this design follows

The lead architect's requirements, and what each one became:

1. **Never trigger jobs we do not want, or on other branches.** Every new job names its branches
   (`vaults/kogany-compat`, `upgrade/vault`) or runs only on a manual dispatch. The one job that
   needs a build of another repository's code (the mixed tier) is also behind a repository
   variable, `KOGANY_MIXED`, which is the lead architect's switch (§9). Scheduled jobs run only
   from the default branch's copy of a workflow (`upgrade/vault`), so nothing scheduled on
   `vaults/kogany-compat` runs before the wave-gate merge.
2. **The three node lines need functional parity, so jobs are interdependent.** The dependencies
   are artifacts at **pinned commits**, never branch tips: a consumer names the producer's commit
   in a file it owns (§4), and a pin moves only by a reviewed commit. No repository's gate depends
   on another repository's branch tip (plan §5, last paragraph of "yewd's CI").
3. **Compartmentalize: a failed part re-runs alone.** One job per check, with the shared inputs
   resolved once per run and re-uploaded as that run's artifacts. "Re-run failed jobs" then
   re-runs one group or one stage against the same binaries, for 30 days, whatever the producer's
   retention (§6).

Two more rules from the plan:

4. **Report-only until the wave's gate, then blocking for what that gate named** (plan §5). The flip
   is one word in a file under review (§5), never a workflow restructure.
5. **Trusted artifacts only.** A cross-repository artifact is taken only from a `push`, `schedule`
   or `workflow_dispatch` run of the producer at the pinned commit, never from a `pull_request` run
   (a fork's pull request can carry a branch of the same name).

---

## 2. Dependency graph

Hard edges only (`A ──▶ B`: B consumes A). Every edge across repositories is "artifact at a pinned
commit"; inside a repository it is "artifact of the same run".

```
  boyfromcave/zakura-common-ycash (the fork, K-2; not yet on GitHub)
        │ git rev in kogany's [patch.crates-io]
        ▼
  kogany  ── build ──▶ koganyd-bin ───────────────┬──────────────────────┬──────────────┐
        │                                         │ KOGANY_COMMIT        │ kogany_ref   │ (in-run)
        │                                         ▼                      ▼              ▼
        │                         ycash6 yellowback-tests:        yolo ci.yml       kogany legs:
        │                           koganyd ──▶ mixed (5 groups)  regtest (kogany)  client-legs,
        │                                    └▶ mixed tier                          kogany-regtest,
        │                                                                           mixed-regtest*,
  ycash6 ── build ──▶ node-bin ──┬──▶ unit, functional (column 1), mixed (column 2)  sidecar*, parity*
        │                        ├──▶ yew yewd-node ──▶ yewd-gates (S0–S3)          (* §7)
        │                        ├──▶ yolo regtest (every node line entry)
        │                        └──▶ kogany mixed-regtest / sidecar / parity (§7)
        └─ sidecars (yolo, chain-viz at pins) ──▶ functional, mixed attest
  yew ── yewd-bin ──┬──▶ yew yewd-gates (in-run)
                    └──▶ ycash6 yewd ──▶ yewd-pair (YEW_COMMIT)
                    └──▶ kogany parity (S5, a pinned yew commit)
```

Read top to bottom, the order a fresh change flows: the fork rev → kogany → koganyd-bin → the
mixed shards and the clients; ycash6 → node-bin → yew's gates and the clients; yew → yewd-bin →
the pair shard and the parity leg. A change on one line reaches another only when that line's pin
is bumped, so each repository's gate is reproducible from its own tree.

---

## 3. Artifact contracts

| Artifact | Producer (job) | Content | Built on | Retention | Consumers (lookup) |
|---|---|---|---|---|---|
| `node-bin` | ycash6 `yellowback-tests.yml` `build` (push, pull_request, dispatch tiers `push`/`all`/`bin`/`mixed`) | `node-bin.tgz`: `src/ycashd`, `src/ycash-cli`, `src/ycash-tx`, `src/test/test_bitcoin`, `qa/pull-tester/tests_config.ini` (tar keeps the mode bits) | ubuntu-22.04 (glibc 2.35; runs on 24.04) | **30 days** outside pull requests, 3 on a pull request | same run: `unit`, `functional`, `mixed`, `yewd-pair`; yew `yewd-node` at `yewd/PIN`'s ycash6 commit; yolo `regtest` (newest run of the node branch, or a given run id); kogany's legs at their ycash6 pin |
| `koganyd-bin` | kogany `kogany-bin.yml`, job `koganyd-bin` (`zakurad-bin` before kogany `dd834da8b`; consumers search **every** workflow's runs at the commit) | `koganyd-bin.tgz`: `koganyd` and `koganyd-bin.json` (`repository`, `commit`, `binary`, `features: ["ycash"]`, `profile: "dev"`, `runner`, `librocksdb`, `rustc`, `producer`) | ubuntu-24.04; links the runner's `librocksdb` (kogany's `setup-zakura-build`), so a consumer runs on ubuntu-24.04 with `librocksdb-dev` installed and checks `ldd` | 30 days outside pull requests | ycash6 `koganyd` (at `KOGANY_COMMIT`); yolo `regtest` kogany entry (at `kogany_ref`); the kogany legs of chain-viz, hawkeye, x402-ycash and lightwalletd-dd (at `KOGANY_REF`). Fallback in all: a build at the pinned commit, `--bin koganyd` (ycash6 caches the binary by commit) |
| `yewd-bin` | yew `ci.yml` `yewd-bin` (push, pull_request, dispatch) | `yewd-bin.tgz`: `yewd`, `yewd-signer` (yewd starts the signer from its own directory), `yewd-bin.json` | ubuntu-24.04, dev profile (dependencies at opt-level 3) | 30 days outside pull requests | same run: `yewd-gates`; ycash6 `yewd` (at `YEW_COMMIT`; fallback: a build at the commit, cached by commit); kogany `parity` (S5) |
| `sidecars` | ycash6 `sidecars` | `sidecars.tgz`: yolo (`--features regtest`), chain-viz at `YOLO_COMMIT`, `CHAINVIZ_COMMIT` | ubuntu-22.04 | 30 / 3 | same run only: `functional`, `mixed` (attest group) |
| `yewd-node` | yew `yewd-node` | `yewd-node.tgz`: `ycashd`, `ycash-cli` from the pinned `node-bin` | — (a copy) | 30 / 3 | same run only: `yewd-gates` |
| `koganyd-bin`, `yewd-bin` (copies) | ycash6 `koganyd`, `yewd` | the resolved producer artifact, or the fallback build (same layout and JSON) | ubuntu-24.04 | 30 / 3 | same run only: `mixed`, `yewd-pair` |

**The rename (`zakurad-bin` → `koganyd-bin`).** The Yellowback lead architect decided on
2026-11-02 that the Ycash node's binary is `koganyd` (`cargo build -p zakura --bin koganyd
--features ycash`, user agent `/koganyd:<version>/`). From kogany `dd834da8b` on, kogany publishes
`koganyd-bin` (job `koganyd-bin` of `kogany-bin.yml`) holding `koganyd-bin.tgz` with `koganyd` and
`koganyd-bin.json` (`"binary": "koganyd"`); a `--features ycash` build's `zakurad` refuses to run
(exit 2). It is the one breaking change of the contract: a consumer pinned at or after that
commit downloads `koganyd-bin`, falls back to `--bin koganyd` and runs `target/debug/koganyd`; one
pinned before it would need `zakurad-bin` and `zakurad`. Every consumer moved its pin to
`dd834da8b` with the rename (ycash6 `KOGANY_COMMIT`, yolo `kogany_ref`, the four client legs'
`KOGANY_REF`), so none takes the old name any more. The client legs' scripts read `KOGANYD` and
still accept `ZAKURAD` (and their rigs `--zakurad`) as the old names. kogany's own note:
`.github/README-kogany.md`, "Cross-line contract".

**Why "any workflow" for `koganyd-bin` and `yewd-bin`.** kogany's CI is being split into several
workflows (`kogany-audit.yml`, `kogany-build.yml`, …); a consumer that named one workflow file
would break on the next split. The artifact name is the contract; the lookup is
`gh run list -R <repo> -c <commit>` over trusted events, then `gh run download -n <name>`.

**Never expired at a pin.** Two mechanisms, chosen by build cost:

- *Expensive* (`node-bin`: depends, C++, Rust; over an hour cold). 30-day retention, plus
  ycash6's scheduled `bin-refresh`: every night it checks the tips of `vaults/kogany-compat` and
  `upgrade/vault`, and dispatches tier `bin` (the `build` job alone) on a branch whose tip has no
  unexpired `node-bin` with more than 7 days left. A tip that stops moving therefore always has a
  fresh `node-bin`. **The 30-day pin rule:** a consumer pin (`yewd/PIN`, yolo's node branch) names a
  branch-tip commit and is bumped before its artifact expires; yew's `yewd-node` warns at 7 days left.
- *Cheap* (`koganyd-bin` about 30–60 min cold, `yewd-bin` about 10 min): the consumer falls back
  to a build at the pinned commit, and ycash6 caches the built binary under a key that is the
  commit itself, so a pin never sees a stale binary and never rebuilds while the cache entry lives.

**Not used, and why.** `workflow_run` fires only for workflows of the same repository, and only
from the default branch's copy. `repository_dispatch` needs a cross-repository token on the
producer's side, and it chases the producer's tip instead of a pin. Release assets would never
expire but need `contents: write` on every push job and leave a release per commit. A
cross-repository read of a **public** repository's artifacts works with each run's own
`GITHUB_TOKEN` (`actions: read`), the method yew's and yolo's jobs already used; if a producer ever
becomes private, a fine-grained token with Actions read on the producers replaces `github.token` in
the `GH_TOKEN` lines (§9 item 10).

---

## 4. Pins

| Consumer | Pin | Names | Bumped |
|---|---|---|---|
| ycash6 `yellowback-tests.yml` | `KOGANY_COMMIT` (env) | kogany commit (now `dd834da8b`, vaults/kogany-compat at the koganyd identity) | by PR with each wave whose gate the mixed shards test |
| ycash6 `yellowback-tests.yml` | `YEW_COMMIT` (env) | yew commit (now `85aec6f`, S3) | by PR with each S stage |
| ycash6 `yellowback-tests.yml` | `KOGANY_LIVE` (env) | the kogany chunks whose koganyd.toml rows are live (`W1-Y1,W2-b`; W5-f is the harness default) | with `KOGANY_COMMIT` |
| yew | `yewd/PIN` `ycash6` line | ycash6 commit whose `node-bin` and `qa/` the gates use | **must move to a ycash6 `vaults/kogany-compat` commit with the YEWD_BIN harness and a CI run** (today it names `65cb4ae0f`, before the harness: the S1–S3 gates cannot run there; §8) |
| yolo | matrix `kogany_ref` | kogany commit (now `dd834da8b`, the koganyd identity) | by PR with W8 |
| yolo | matrix `of_record` (kogany entry) | ycash6 branch whose newest trusted `node-bin` is taken (`vaults/kogany-compat`) | — |
| chain-viz, hawkeye, x402-ycash `ci.yml`; lightwalletd-dd `yellowback-tests.yml` | `KOGANY_REF` (env, the kogany leg) | kogany commit (now `dd834da8b`, the koganyd identity) | with the kogany behaviour the leg checks |
| kogany | `LWD_REV`, `CHAINVIZ_REV` (client-legs) | lightwalletd-dd, chain-viz commits | the `ci-kogany` chunk |
| kogany | (proposed) a ycash6 pin for mixed-regtest / sidecar / parity, and a yew pin for parity | §7 | the `ci-kogany` chunk |

---

## 5. Job map, and what blocks when

### ycash6 (`.github/workflows/yellowback-tests.yml`)

| Job (check name) | Tier / trigger | Blocking | Flips | Re-run unit |
|---|---|---|---|---|
| `build` | push tier; tiers `bin`, `mixed` | in `push tier` | — | the build |
| `unit`, `functional <suite> <n>/<of>`, `audit`, `agent`, `python`, `lint`, `sidecars` | push tier | in `push tier` | — | one job / one shard |
| `push tier` (`gate`) | push tier | the required check | unchanged | — |
| `bin-refresh` (matrix: two branches) | schedule (from the default branch) | — | — | one branch |
| `koganyd` | mixed tier | in `mixed tier` | — | the resolve |
| `yewd` | mixed tier | no (feeds `yewd-pair`) | — | the resolve |
| `mixed <group>` (node, vault, yed, fees, attest) | mixed tier | its `gate` step only; `report` scripts never fail the job | per script, `qa/kogany-mixed-shards.txt` `report` → `gate` at the script's wave gate | one group |
| `yewd pair (report-only)` | mixed tier | no (`continue-on-error`) | contracts at S4, the 48 scripts at S5 (they move to kogany's `parity` nightly) | the job |
| `mixed tier` (`mixed-gate`) | mixed tier | **not required until W2** | the lead architect adds it as a required check of `vaults/kogany-compat` at the W2 gate | — |

The python job gains two blocking steps: the harness's own unit tests
(`qa/rpc-tests/test_framework/test_kogany.py`, 43 tests, no node) and the shard manifest check
(`qa/test_kogany_mixed_shards.py`): every `YELLOWBACK_SCRIPTS` entry is in exactly one mixed group
or excluded, every name is one `rpc-tests.py` knows (it drops an unknown name silently), the
peer-count scripts are excluded.

**The mixed shard file** `qa/kogany-mixed-shards.txt` (`<group> <script> <state> <wave> [flags]`)
and its runner `qa/kogany_mixed_shards.py` (`check`, `list`, `run GROUP --state report|gate`) are
the single source of the shard lists for both repositories: kogany's mixed-regtest leg calls the
same runner from a ycash6 checkout at its pin (§7). Groups and the waves that flip them:

| Group | Scripts | Flags | Waves |
|---|---|---|---|
| node | `kogany_mixed_smoke` (direct), stopatheight, ycash_bootstrap, testnet_ceremony, lightwalletd_only, z_validateaddress_nowallet | — | W1 (smoke), W9 |
| vault | 15: activation_restart, upgrade (W2); primitive, slashing, undo_prune, pq_reorg, dos (W4); rpc, rpc_contract (W7); pq_relay (W6); bridge, pq, pq_wallet, pq_wallet_restore, wallet_pq_address (W9) | `mirror` on the seven that invalidate | W2, W4, W6, W7, W9 |
| yed | 19: lifecycle, activation_reorg, reorg_restart, claim, interm, index, upgrade (W5); rpc_contract (W7); the rest W9 | `mirror` on five | W5, W7, W9 |
| fees | fees, fees_reaccept (W5); fee, mempool_limits, vault_policy, vault_refee (W6); wr_flags (W9) | `mempool` | W5, W6, W9 |
| attest | attest_evict, attest_rejoin, attest_live, pricefeed (W5); mining, stratum (W8); attest, attest_wallet, attest_bond, quote, chainviz (W9) | `mirror` on three | W5, W8, W9 |
| excluded | yellowback_framework_smoke (exact peer count) | — | never |

A `gate` script runs with `KOGANY_STRICT=1` (a missing kogany RPC or an unmapped reject reason
fails). The three-way invariant of plan §4.2 rule 4 (ii) and (iii) is asserted by the harness at
every `sync_blocks` / `sync_mempools` of every script in this tier.

### yew (`.github/workflows/ci.yml`; `secops.yml`; `scripts/audit.sh`)

| Job | Blocking | Flips | Re-run unit |
|---|---|---|---|
| `yewd check (ubuntu)` | **yes** | — | the job |
| `yewd bin (ubuntu-24.04)` | no check depends on it but the gates | — | the job |
| `yewd node (ycash6 at yewd/PIN)` | feeds the gates | — | the job |
| `yewd gate <stage>` × 6: `s0-roundtrip`, `s1`, `s2`, `s3-roles`, `s3-attest_wallet`, `s3-attest_bond` | report-only (`continue-on-error: !matrix.blocking`) | set `blocking: true` on the entry when the stage's gate is seen green in CI: S0 as soon as `yewd/PIN` names a ycash6 commit with a 30-day node-bin; S1, S2, S3 at their gates | one stage |
| `secops` `osv-scanner` | yes | — | — |
| `audit` (`scripts/audit.sh`) | yes (fix available) | — | — |

S3's `attest_agent` and `cancel_agent` stages need ycash6's attestation agent
(`YELLOWBACK_ATTEST_BIN`); they join the matrix when a job builds it (ycash6's `agent` job is the
natural producer: a fourth contract, `attest-bin`, when needed). The lockfile gap of KF-33 is
closed: OSV and `scripts/audit.sh` read `yewd/Cargo.lock` (409 crates; 0 vulnerabilities, 1
allowed warning at the time of writing). `web/core-wasm/Cargo.lock` and the `web/spike-*` locks are
still outside both scans (not in this chunk's scope; §8).

### yolo (`.github/workflows/ci.yml`)

| Job | Blocking | Flips |
|---|---|---|
| `check (ubuntu-latest, macos-latest)`, `audit` | yes (now also on `vaults/kogany-compat`) | — |
| `regtest (ycash-dd)`, `regtest (ycash6)` | yes, nightly dispatch | — |
| `regtest (kogany)` | report-only (`continue-on-error`) | blocking at the W8 gate |

The kogany entry takes `koganyd-bin` at `kogany_ref` when kogany publishes one and builds koganyd
otherwise (the build is today's only path: kogany publishes nothing yet). Its ycash6 nodes come
from `vaults/kogany-compat`'s newest trusted `node-bin`.

### kogany (aligned with the `ci-kogany` chunk)

kogany's own legs are plan §5's table. What the other repositories need from kogany's CI:

1. **Publish `koganyd-bin`** exactly as §3 states (name, tar layout, JSON keys, ubuntu-24.04,
   30 days outside pull requests), from a job of its own (so a failed check never blocks the
   artifact and the artifact never re-runs with a check), on pushes to `vaults/kogany-compat` and
   `upgrade/vault` and on dispatch.
2. **mixed-regtest leg** (plan §5): checkout ycash6 at a pinned commit, take that commit's
   `node-bin`, use this run's own `koganyd`, and run `python3 qa/kogany_mixed_shards.py run <group>
   --state gate|report` from the ycash6 checkout, one job per group, so kogany's PRs are tested
   against the same shard lists as ycash6's.
3. **sidecar** (W9-a) and **parity** (S5) nightlies: the same pattern with the ycash6 test rig and
   with `yewd-bin` at a pinned yew commit; scheduled only once the default branch carries them.

### lightwalletd-dd and chain-viz (read-only here)

Neither lists `vaults/kogany-compat` in its push or pull-request branches, and neither has a kogany
leg: kogany's `client-legs` job runs both, unmodified, at pinned commits against a regtest koganyd
(W7-d). For W9-c the client agents add `vaults/kogany-compat` to the branch list and a report-only
`node_line: kogany` entry consuming `koganyd-bin` as yolo's does (§8).

---

## 6. Re-run granularity

| Failure | Re-run | Inputs it reuses |
|---|---|---|
| one functional shard, one mixed group | that job ("Re-run failed jobs") | this run's `node-bin`, `koganyd-bin`, `sidecars` (30 days) |
| the yewd pair shard | that job | this run's `node-bin`, `yewd-bin` |
| one yewd stage gate | that job | this run's `yewd-bin`, `yewd-node` |
| koganyd / yewd resolution | that job; its dependants follow | the producer's artifact or the cache keyed by the pin |
| ycash6 `build` | the build (then everything after it) | ccache, depends caches |
| a stale cross-repository artifact | not a re-run: bump the pin, or dispatch tier `bin` on the ycash6 branch | — |

---

## 7. The three-way matrix (plan §6, S5) in CI

| Column | What | Where |
|---|---|---|
| 1. ycash6 alone (the reference) | the 58 scripts on ycash6 nodes | ycash6 `functional` (push tier, blocking) |
| 2. kogany + the ycash6 test rig | the same scripts, kogany followers asserting tips, state hashes, mempool sets and verdict classes at every sync point | ycash6 `mixed <group>` (report → gate per wave); kogany mixed-regtest (same runner) |
| 3. kogany + `yewd` | every node kogany + `yewd`; mixed variant with one ycash6 peer | today `yewd-pair` runs the backend-ycash6 differential (`yewd` in front of ycashd `-disablewallet`); column 3 proper needs the harness's kogany-backend mode (S5) and lands in kogany's `parity` nightly and in `yewd-pair` |

The S5 exit gate ("twice in a row, nightly green for 7 days") is read from the parity nightly's
run history; the `statehash` / `yed_getstatehash` equality is the harness's assertion, so a green
run is the evidence.

---

## 8. Open items and findings

1. **The fork repository does not exist on GitHub** (`boyfromcave/zakura-common-ycash`). Every build
   of kogany outside this machine fails at dependency resolution: kogany's own CI, ycash6's
   `koganyd` fallback, yolo's kogany entry. This is why the mixed tier is behind `KOGANY_MIXED`.
2. **`yewd/PIN` names ycash6 `65cb4ae0f`**, which predates the `YEWD_BIN` harness and the
   `-disablewallet` fixes (KF-36); the S1–S3 gates need a ycash6 `vaults/kogany-compat` commit.
   Bump it to the first `vaults/kogany-compat` commit with a ycash6 CI run once this design is merged
   and ycash6's Actions run there (the coordinator's or the yewd agents' change).
3. **`koganyd-bin` is a proposal** until the `ci-kogany` chunk publishes it; the consumers fall
   back to a build, so nothing waits on it.
4. **ubuntu-22.04 vs 24.04.** ycash6 builds on 22.04; koganyd links the runner's librocksdb, so a
   24.04 koganyd does not run on 22.04 (glibc 2.39, `librocksdb.so.8.9`). The mixed jobs run on
   24.04 (ycashd from 22.04 runs there) and check `ldd` first.
5. **`semgrep.yml` runs on a push to every branch** but `semgrep/**`, in every repository of the
   shared security-CI design, so a push of a `kc/*` branch starts a Semgrep run once Actions are on.
   Left unchanged here (one design across all repositories); a decision for the lead architect
   (restrict its push trigger to the integration branches, or accept it).
6. **`rpc-tests.py` silently drops a script name it does not list.** `kogany_mixed_smoke` is not
   registered (by design until the W1 gate), so the runner runs it directly (`direct` flag) and the
   manifest check refuses any other unregistered name.
7. **yew's other lockfiles** (`web/core-wasm/Cargo.lock`, `web/spike-*`) are outside OSV and
   cargo-audit.
8. **lightwalletd-dd and chain-viz** do not run on `vaults/kogany-compat` (§5).
9. **The workspace's own `workspace-check.yml`** does not list `vaults/kogany-compat` either; the
   kogany plan documents on that branch are checked only when they reach `upgrade/vault`. No
   cross-repository orchestration lives in the workspace (each consumer pins its producers), so this
   design adds no workspace workflow.

---

## 9. Settings for the lead architect when Actions are turned on

Nothing here was changed by this chunk. In order:

1. **Create `boyfromcave/zakura-common-ycash`** and push its `vaults/kogany-compat` (with the rev
   kogany's `[patch.crates-io]` pins, `1e6d6aa4…` today). Precondition for every kogany build on
   GitHub.
2. **Per repository, Settings → Actions → General:**
   - Actions permissions: allow the actions the workflows use. Every `uses:` is SHA-pinned, so
     "Require actions to be pinned to a full-length commit SHA" can be on.
   - Workflow permissions: "Read repository contents" (every workflow declares its own).
   - Fork pull-request workflows: require approval for outside contributors; the cross-repository
     lookups trust only push, schedule and dispatch runs.
   - Artifact and log retention: **at least 30 days** (the public-repository default is 90). Below
     30, the artifact contracts of §3 break silently.
3. **kogany:** follow `.github/README-kogany.md` (the `ci-kogany` chunk), its off-set disabled in the
   same session; then confirm one push run publishes `koganyd-bin`.
4. **ycash6:** set the repository variable **`KOGANY_MIXED` = `true`** (Settings → Secrets and
   variables → Actions → Variables) once item 1 is done. Until then the mixed tier is skipped.
5. **ycash6 rulesets on `vaults/kogany-compat`:** required check `push tier`; add **`mixed tier`** at
   the W2 gate (when the first scripts are flipped to `gate`).
6. **yew rulesets on `vaults/kogany-compat`:** required `yewd check (ubuntu)` beside the existing
   core, app and web checks; a stage gate job becomes required only when its entry is flipped to
   `blocking: true`.
7. **yolo rulesets on `vaults/kogany-compat`:** `check (ubuntu-latest)`, `check (macos-latest)`,
   `audit`.
8. **Default branches stay `upgrade/vault`.** Scheduled jobs (ycash6's `schedule-fanout` and
   `bin-refresh`, the security nightlies) run from the default branch's copy: `bin-refresh` starts
   only after the wave-gate merge of `vaults/kogany-compat` into `upgrade/vault`. Until then a stale
   `node-bin` is refreshed by hand: Actions → yellowback tests → Run workflow → branch, tier `bin`.
9. **Code security:** code scanning and Dependabot security updates on, as `SECURITY-CI.md` says in
   each repository; nothing new for this design.
10. **If a producer repository becomes private:** a fine-grained token with Actions: read on
    ycash6, kogany and yew, as a secret of each consumer, in place of `github.token` in the
    `GH_TOKEN` lines of ycash6 `koganyd`/`yewd`, yew `yewd-node`, yolo `regtest`.
11. **Cache budget:** the 10 GB per-repository cache is not grown by this design (kogany's target
    directory is never cached outside kogany; ycash6 caches only the two small binaries by pin).

---

## 10. Checking it locally

```bash
# ycash6 worktree
python3 qa/test_kogany_mixed_shards.py -v            # manifest complete, runner logic
python3 qa/kogany_mixed_shards.py check
python3 qa/kogany_mixed_shards.py run vault --state report --dry-run
(cd qa/rpc-tests && python3 -m unittest test_framework.test_kogany)
# a real mixed group (needs a ycash6 build and a koganyd):
KOGANY_BIN=<koganyd> KOGANY_LIVE=W1-Y1,W2-b python3 qa/kogany_mixed_shards.py run vault --state report
# every repository: actionlint (from the repository root) and zizmor --offline .github/
```
