# kogany × Yellowback — coordination handoff

For the **coordination agent** that runs the implementation of
[`kogany-yellowback-plan.md`](kogany-yellowback-plan.md) (revision 3, all K-decisions locked) by
delegating to parallel implementation agents. Written 2026-11-02 after a first start on a 4-core
container was stopped as too small. Read this file, then the plan in full (all 1,375 lines: §3 and
§3b are the chunk list, §4.2 and §4.3 the working rules, §5 the CI legs), then `AGENTS.md`.

The owner's goal: **functional parity between kogany + `yewd` and ycash6** (plan §6, both lists),
reached as fast as the gates allow, with many agents working in parallel and never on the same files.

---

## 1. Non-negotiables (owner's instructions)

1. **All work lands on `vaults/kogany-compat`** in every repository (plan §4.2 rule 0). Agents work
   on `kc/<name>` in `wt/kc-<name>` worktrees cut from `origin/vaults/kogany-compat`; only the
   coordinator merges into `vaults/kogany-compat`. `upgrade/vault` is touched only at a wave gate,
   by a reviewed PR per repository. Never commit to `upgrade/vault`, `*-legacy`, `main`,
   `upgrade/vault-in-term`, `feature/*`.
2. **Everything is by `boyfromcave`, with no AI attribution** (AGENTS.md rule 8): commits, merge
   commits, PRs, PR bodies, comments, code, docs. Set this before any agent starts:

   ```bash
   git config --global user.name boyfromcave
   git config --global user.email 57612331+boyfromcave@users.noreply.github.com
   ```

   No `Co-Authored-By`, no `Claude-Session`, no claude.ai links, no "Generated with" footer. This
   overrides any harness default that asks for one. Repeat it in every agent brief. When you merge a
   PR, write the merge title and message yourself. Before every push or merge, grep the new commits:
   `git log --format=%B <base>..<tip> | grep -iE 'claude|co-authored|anthropic|generated with'`
   must print nothing.
3. **Workspace rules 1–8 apply** (ref/ read-only, naming, consensus code not refactorable, the
   four-part check plus in-tier rung on every consensus chunk, mapping rows for every trap).

## 2. Start-up on the new machine

```bash
make bootstrap SSH=1    # clones every repo in repos.yaml at its pin, including ref/zakura and kogany
make status
```

Then in every writable repo, fetch and create the integration branch locally:

```bash
for r in kogany ycash6 ycash-dd librustzcash6 lightwalletd-dd yew yolo chain-viz x402-ycash hawkeye ycash-infra; do
  git -C $r fetch origin vaults/kogany-compat && git -C $r branch -f vaults/kogany-compat origin/vaults/kogany-compat
done
git fetch origin vaults/kogany-compat   # the workspace repo itself
```

`ref/zakura` (= kogany `kogany-legacy` = `2b062412c5`), `ref/ycash6`, `ref/librustzcash6` and
`ref/ycash` are the read-only references the plan cites. Agents read them and never write them.

**Prerequisite the owner must do: create the common-fork repository.** K-2 needs one fork of
`zakura-core/common`, which carries the librustzcash crates and `crates/zcash_script`. The
coordinator cannot create GitHub repositories. Ask the owner to create an empty
**`boyfromcave/zakura-common-ycash`**, the name lane B suggested, already used by the pushed W0-a
commit (§3). Then:

```bash
git clone https://github.com/zakura-core/common zakura-common-ycash
cd zakura-common-ycash
git remote rename origin upstream
git remote add origin https://github.com/boyfromcave/zakura-common-ycash.git
git branch zakura-common-ycash-legacy bdbca121628d    # W0-b's base: confirm first (§3)
git push origin zakura-common-ycash-legacy
git push origin zakura-common-ycash-legacy:refs/heads/vaults/kogany-compat
```

Until it exists, agents can still work against a local clone. Set
`git config --global url."file://$PWD/zakura-common-ycash".insteadOf https://github.com/boyfromcave/zakura-common-ycash`
and build with `CARGO_NET_GIT_FETCH_WITH_CLI=true`. Kogany's `[patch.crates-io]` is always
committed with the real GitHub URL and an exact `rev` (plan §4.2 rule 8). Pushed kogany branches
build on GitHub only once the fork repo has the rev.

## 3. State at handoff (2026-11-02)

| Repo / branch | Commit | What | Status |
|---|---|---|---|
| kogany `vaults/kogany-compat` | `4c82f1f` | `testdata/yellowback/`: the nine cross-line vector files, byte-identical to ycash6 `src/test/data/*.json` @ `65cb4ae0f`, plus `PIN` (SHA-256 per C++ path) | **merged**. This is W2-c's copy step, brought forward so every crate chunk shares one pinned set |
| kogany `kc/kogany-pq` | `29b98a64b` | W3-b: crate `crates/kogany-pq` (vendored verify-only Falcon-512 + SLH-DSA SHA2-128s C via `cc`, `src/ffi.rs`, `src/lib.rs`, tests for `pq_vectors`, `pq_acvp_slhdsa`, `pq_falcon_kat`, a `vendored.rs` pin test), plus the first `testdata/yellowback/CHECKLIST.md` | **pushed, not reviewed, not merged.** The agent was stopped right after pushing, so its gate report never arrived. Re-run its exit gate (debug **and** `--release`) and review it before merging |
| workspace `kc/w0-scaffold` | `59b50ef` | W0-a: `repos.yaml` entry for `zakura-common-ycash` (pin left as a marked TODO), AGENTS.md amendments (layout, rule 2 branches, K-19 shared-defect rule, YEW paragraph widened to `app`/`web`/`yewd`), `docs/mapping.md` §24 from plan §10, `.gitignore` and code-workspace entries | **pushed, not reviewed, not merged.** Fill the fork pin once the fork exists, then review and merge |
| `zakura-common-ycash` (local only, lost with the old container) | — | W0-b's agent had chosen **`bdbca121628d`** (the "prepare Common 5.0.0-rc.2" commit) as `-legacy` base | **not pushed.** Redo W0-b, and verify that `zakura-zcash-script` 0.0.1 (published from `ca4c341ed9c4`) reproduces from that base file for file. If not, record the finding (plan §1.4) |
| everything else | — | W0-c/d, W1-Y0, W2-a, W3-a, W4-a, W5-a, W1-Y1, S0 and the harness were started, but their work was uncommitted when stopped | **lost. Restart from the briefs in §6** |

Plan status block: still all `[ ]`. Update it as gates are seen green; it is authoritative and the
coordinator owns it.

## 4. Operating model

**Roles.**
- **Coordinator (you):** splits work, writes briefs, merges, keeps the plan's status block,
  findings log (§9) and mapping §24, and runs each wave gate from a clean worktree at the
  integration tip.
- **Implementation agents:** one chunk each, one worktree each.
- **Reviewer agents:** one per consensus chunk, never the author. They are a pre-merge check, not
  the plan's two-human review gate, which still applies at the merge into `upgrade/vault`.

**One shared brief.** Write `wt/COORDINATION.md` once and point every agent at it. Include:
- the non-negotiables (§1);
- where references live;
- the worktree and branch recipe;
- "touch only the paths your brief names";
- the build discipline (§5);
- the definition of done.

Each agent prompt then holds only its chunk: scope, paths it owns, entry, exit gate, plan sections
to read, and the API it must report.

**Definition of done for an agent.** The exit gate is run and passing, or a precise list of what
could not run and why. Commits are on `kc/<name>`, with the four-part check and in-tier rung in the
body for consensus chunks, and are pushed. The worktree is clean. The final report gives:
- branch and head SHA;
- the commands run and their results;
- what remains;
- findings, each as wave/chunk, finding, resolution and proposed M24 row;
- the exact public API that later chunks code against.

Agents never open PRs, comment on GitHub, or merge.

**Merging.**
- Merge `kc/<name>` into `vaults/kogany-compat` with `--no-ff` and a message you write.
- Resolve the predictable conflicts yourself: kogany root `Cargo.toml` `[workspace] members`,
  `Cargo.lock`, `testdata/yellowback/CHECKLIST.md`.
- Re-run the merged chunk's gate on the integration tree before pushing.
- Delete the `kc/` branch after the merge.
- After each merge, tell any running agent whose chunk depends on it to merge
  `origin/vaults/kogany-compat` into its own branch.

**Avoiding duplication and overwrites.**
- Each chunk owns named paths, listed in its brief.
- Two agents never own the same file, except the shared lists above, where each adds only its own
  lines.
- The plan file, its status block and its findings log are the coordinator's alone.

**Wave gates and `upgrade/vault`.** When a wave's exit gate is green on the integration tree:
1. update the status block;
2. tag where the plan says (`kogany-baseline` after W0, `kogany-ycash-baseline` after W1);
3. open one PR per repository `vaults/kogany-compat` → `upgrade/vault`, as boyfromcave, with the
   four-part checks and the consensus-diff artefact in the body;
4. leave the merge to the owner's two-reviewer gate.

The plan allows the refresh direction (`upgrade/vault` → `vaults/kogany-compat`) as routine.

**Upstream sync** (plan §4.2 rule 7): one agent per sync, chunk `sync-zakura-<date>`, at wave
boundaries.

## 5. Build discipline (sized for a big machine; adjust to it)

- **Builds:** kogany is a large Rust workspace, and ycash6 is a long C++/Rust build. Give each
  agent its own `CARGO_TARGET_DIR`. On a machine with fewer than ~32 cores, share one target dir
  among the agents that compile kogany's upstream crates (cargo serialises on its lock), and keep
  the new `kogany-*` crates on their own small target dirs. Agents test with `-p <crate>`. Only the
  coordinator runs workspace-wide `cargo test --workspace` and nextest profiles, at gates.
- **Disk:** budget ~15–25 GB per kogany target dir and ~10 GB for a ycash6 build. Check `df`
  before you start a batch.
- **One ycashd for everyone.** Build ycash6 (`vaults/kogany-compat`) once, early, into a shared
  location, and use it for the mixed-line harness, the S-track's `-disablewallet` backend and V5-spec.
  Look first for a CI `node-bin.tgz` artefact or a release of `boyfromcave/ycash6`.
- **Develop pure crates ahead of their wave.** `kogany-pq`, `kogany-vault`, `kogany-yellowback`
  (math, params, codecs, attest) and the fork's `zcash_script` opcodes depend only on the pinned
  vectors. Keep them free of zakura-chain and zakura-state dependencies, and replay their vectors
  before the upstream waves land. Their **hook** chunks (W3-c, W4-c/d, W5-e/f) still wait for the
  waves below them, so the plan's layering is kept for anything that touches consensus flow. This
  is the main lever for parallelism. Record it as a coordinator decision in §9.
- **Determinism disciplines** (§4.2 rule 6) are enforced per crate from day one: `clippy.toml`
  `disallowed-types` for HashMap/HashSet, plus deny attributes. Run math and state tests in release
  too.

## 6. Dependency graph and batches

Arrows are hard dependencies (an API or behaviour is consumed). Everything not connected runs in
parallel.

```
fork: W0-b ─▶ W1-Y0 ─▶ W2-a ─────────────────┐
      W3-a (zcash_script; base ca4c341, rebase onto fork) ─┐
kogany: W0-c/d ─▶ tag kogany-baseline        │            │
        W1-Y1 ─▶ Y2, Y3 ─▶ Y4 ─▶ Y8 (sync)    │            │
          │  └─▶ Y5 ─▶ Y7(harness live)       │            │
          └─▶ Y6                              ▼            ▼
        W2-b (needs W2-a, Y1) ─▶ W2-c, W2-d ─▶ W3-c (needs W3-a) ─▶ W3-d, W3-e
        W3-b kogany-pq ──────────────────────────────┘ (W3-c wires it)
        W4-a codecs ─▶ W4-b state ─▶ W4-c storage ─▶ W4-d snapshot hook (needs W3-c) ─▶ W4-e
        W5-a math ─▶ W5-b codecs ─▶ W5-c attest ─▶ W5-d1 ─▶ W5-d2 ─▶ W5-e index (needs W4-c) ─▶ W5-f register
        W6-a/b/c (need W4-d, W5-f) ; W7-a (prototype now) ─▶ W7-b ─▶ W7-c/d/e ; W8-a/b/c (need W6, W7-b)
        W9-a..d (need W8)
ycash6 qa: harness (KOGANY_BIN/YEWD_BIN) ─▶ used by W2-d, W4-e, W5-f, W6, S0..S5
yew:    S0 ─▶ S1 ─▶ S2 ─▶ S3 ─▶ S4 (needs W7-e) ─▶ S5 (needs W8, W9-a/b)
ycash6 + workspace: V5-spec (independent; needs a ycash6 build)
```

**Batch 1** (start at once, ~10 agents). Each has its own paths:

| Agent | Chunk(s) | Owns | Brief points beyond the plan row |
|---|---|---|---|
| `w0-scaffold` | W0-a (finish `kc/w0-scaffold`: fork pin), W0-c, W0-d | workspace `repos.yaml`/AGENTS.md/mapping §24; kogany `.github/`, `qa/kogany-*.txt`, `qa/` audit scripts, `contrib/secops/` | trim to K-15's six workflows; disable the rest in the least rebase-hostile way and record why; audit logic in Python under `qa/` (`main(argv=None)`), not YAML heredocs; the build-matrix leg tolerates the missing `ycash` feature until W1-Y1; propose the `kogany-baseline` commit; the coordinator tags it |
| `fork-protocol` | W0-b, W1-Y0, W2-a | fork crates except `crates/zcash_script`; kogany root `[patch.crates-io]` | §3's base `bdbca121`; reproduce every crates.io tarball file for file; port librustzcash6 `02d42df5`, `ec525fae`, `4867cf85`, `eeb7740d` **by meaning**; Vault **before Nu5** (K-1); the version suffix `+ycash.N` (§4.2 rule 8); report the variant and feature names |
| `fork-script` | W3-a | fork `crates/zcash_script/` only | start from `ca4c341ed9c4`; the coordinator rebases it onto the fork's integration branch; fail-closed checker defaults; never 0xbb–0xbf; report the trait and flag API exactly (W3-c codes against it) |
| `kogany-pq` (review + finish) | W3-b | `crates/kogany-pq/` | review `29b98a64b`, re-run the gate in debug and release, add malformed-encoding cases if missing |
| `kogany-vault` | W4-a | `crates/kogany-vault/` | own byte types, no zakura deps; secp256k1 `recovery`; leave a `state` module boundary for W4-b |
| `kogany-yed-math` | W5-a | `crates/kogany-yellowback/` (`math`, `params` only) | params **checked against** ycash6 `params.cpp` by a parsing test, never hand-copied; 256-bit FEE-1′ without floats |
| `w1-profile` | W1-Y1, then Y2, Y3 | `zakura-chain` parameters/network/work, the `ycash` feature plumbing, `zakura-header-chain` pow policy, consensus subsidy | do not add Vault (W2-b); merge `kc/fork-protocol` when pushed; list every edited upstream test; push after each chunk |
| `yewd-s0` | S0 | `yew/yewd/`, `yew/docs/plans/yewd-plan.md`, yew `ci.yml` `yewd` job | own Cargo workspace, yew-core by path; full method table answering `-32601`; forwarding with the backend cookie; report the CLI contract for the harness |
| `harness` | the W1-Y7 harness part (plus W2-d, W4-e scaffolding) | ycash6 `qa/` only (scripts unchanged) | `KOGANY_BIN`, a `zakurad.toml` generator from a key table (Vault/ycash keys filled when W1-Y1 and W2-b land), state-hash and mempool asserts at `sync_all`, the verdict-class map, `YEWD_BIN` hook points; produce the shared ycashd build |
| `v5-spec` | V5-spec (K-21) | workspace `docs/` dormant §15.2-v5 section; ycash6 unit-test vector generator | outside the cross-line manifest; fix or replace `zip244.py` first (assessment §2 row 16); no consensus change |

**Batch 2** (as batch 1 lands):
- W1-Y5 `p2p` and W1-Y6 `rpc-ycash`: after Y1.
- W1-Y4 `checkpoints`: after Y3. It needs a synced ycash6 mainnet node; start that sync early, since
  it takes days of wall-clock time.
- W2-b `vault-epoch`: after W2-a and Y1.
- W4-b `set-state`: after W4-a.
- W5-b `codecs` and then W5-c `attest`: after W5-a.
- W7-a `rpc-dispatch`: the second `rpc_trait!` prototype, which is risky, so start early in a
  `kogany-rpc` crate.
- S1: yewd sync on yew-core against ycash6 `-disablewallet`.

**Batch 3 onward** follows the graph. The serial spine is W1 → W2-b → W3-c → W4-c/d → W5-e/f → W6 →
W8 → W9. Keep the spine staffed first. Put spare agents on the S-track (S2 is the largest at 6–9
agent-days, so split it: set/act builders, generic vault builders, signer process and protocol,
Sapling-in-signer), on W7 (W7-b is 25 RPCs, split by RPC group) and on client legs (W9-c, one agent
per client repo).

**Long wall-clock items to start on day one:**
- the ycash6 mainnet and testnet sync (for Y4 checkpoints and the Y8 sync gate);
- the ycashd build.

## 7. Gates checklist (copy into the status block as they go green)

| Gate | Command / evidence (run by the coordinator at the integration tip) |
|---|---|
| W0 | upstream `lint` + `tests-unit` green with the fork patched in; security CI green; consensus-diff and frozen-file reports empty; tag `kogany-baseline` |
| W1 | Ycash block vectors including negative solution sizes; full mainnet and testnet sync equal to ycash6; kogany ⇄ ycash6 P2P on regtest; feature-off upstream suite green; tag `kogany-ycash-baseline` |
| W2 | `vault_vectors.spends[].sighash` replay; mixed `vault_activation_restart` + boundary script; Zcash NU5–NU7 tests unchanged and green; v5 rejected after Vault |
| W3 | ownerSpends, pq, ACVP and KAT replays in debug and release; fuzz verdict replay; dormancy suite |
| W4 | mixed vault scripts with `statehash` equal at every sync; reorg and restart tests; per-fork delta memory measured at 1,000 blocks |
| W5 | four YED vector files; golden `stateHash`; mixed YED scripts three-way equal (kogany, ycash6, `yellowback_model.py`) |
| W6 | mempool-set and verdict-class equality in mixed runs |
| W7 | contract read shapes; `check-rpc-artifacts`; `make spec-check`; client legs run (report-only) |
| W8 | ycash6 accepts kogany-built blocks with the coinbase tag; yolo leg |
| W9 | 58 scripts in mixed mode twice; three-way devnet rounds; client legs; review document |
| S0–S5 | per plan §3b; S5 = both contract suites and the 48 wallet scripts on kogany + yewd twice, nightly green 7 days, three-way matrix |
| §6 | the demonstration transcript in `kogany/doc/yellowback-review.md`, with `pgrep -l ycashd` empty for the product demo |

## 8. Lessons from the first start

- **Bootstrap first.** Starting from flat clones without `ref/` meant every brief had to explain
  substitutes for the plan's `ref/…` citations. `make bootstrap` gives agents the layout the plan
  cites.
- **Fork base.** W0-b's first answer was `bdbca121` for the protocol crates. The open question is
  `zcash_script` (`ca4c341`), so W3-a is safe to start from `ca4c341` and rebase.
- **Pin vectors once.** Pinning the vectors before launching crate agents avoided nine divergent
  copies. Do the same for any shared fixture: create it once, on the integration branch, before the
  agents that read it start.
- **Commit WIP often.** Agents stopped mid-chunk lose uncommitted work. Tell agents to commit WIP to
  `kc/<name>` (pushed) at least every major step. The coordinator squashes nothing, since history
  on `kc/` branches is fine.
