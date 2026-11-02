# yellowback-workspace — agent instructions

Bring a decentralized digital dollar to **Ycash** as **Ycash Yellowback (YED)**, using DigiByte's **DigiDollar**
as the reference implementation — in the node (`ycashd`) **and** in the full-node GUI wallet
(**YecWallet**, a Qt application that bundles and drives `ycashd` over RPC). Start with
[README.md](README.md) for the goal and the change-budget ladder; this file is the working rules.

**The prime directive is minimal change to the Ycash codebase.** The Ycash team is risk-averse and
the shielded pool's soundness rests on consensus code few people fully understand. That still
governs every change. **The tier, though, is decided: a network upgrade (Tier 3)** — the owner's
decision (2026-10-06, `upgrade/vault`) and the Foundation's requirements: a generic,
application-agnostic lock/unlock primitive (R3, O-1) cannot be built from existing opcodes or a
soft fork, and its rules must be checked by every full node, not enforced by miners
(`docs/plans/yellowback-upgrade-plan.md` §1, §10). Within that tier, prefer a script template over
an opcode, an opcode over a transaction field, per-vault state over global state, and the
primitive over the module. When a design trades elegance for a smaller consensus footprint, take
the smaller footprint and record what was given up. (The cheaper-tier ladder — Tier 0 as Ycash's
atomic-swap feature did in commit `ccddd22e4`, then a soft fork — governs the `harden/yellowback`
fallback line only.)

## Layout

```
yellowback-workspace/
├── ref/
│   ├── digibyte/    READ-ONLY. DigiByte, pinned to tag v9.26.5 (05b50e229d)
│   │                (upstream v9.26.7 d7265fb05e exists, with Thaw Day: docs/mapping.md §23, the addendum and re-pin plan)
│   ├── ycash/       READ-ONLY. Ycash node, pinned to tag v4.5.0 (624c12814)
│   ├── yecwallet/   READ-ONLY. YecWallet GUI (Qt 6, bundles ycashd), pinned to tag v4.5.0 (1eb277d)
│   ├── lightwalletd/ READ-ONLY. yodl/lightwalletd (zcash/lightwalletd 0.4.6 + Ycash regex), master @ 187a26765e (no tag)
│   ├── ycash6/      READ-ONLY. miodragpop/ycash, ycashd 6.20.0 (Zcash 6.x lineage), dev-rebase-6.20.0 @ 040894344b (no tag)
│   ├── librustzcash6/ READ-ONLY. miodragpop/librustzcash, the patched librustzcash ref/ycash6's Cargo.toml pins, ycashd-v6.20.0 @ ec525fae82 (no tag)
│   ├── zakura/      READ-ONLY. zakura-core/zakura, a Zcash full node in Rust (Zebra lineage), main @ 2b062412c5 (past v1.7.0)
│   └── yolo/        READ-ONLY. yecdev/yolo, the Perl solo-pool stratum servers (stratumpool/stratumsolo/cenote), main @ c9c155c6 (no tag)
├── ycash-dd/        WORKING FORK of the node.   branch `feature/yellowback-price-attest`, off `ycash-legacy`     (= v4.5.0)
├── yecwallet-dd/    WORKING FORK of the wallet. branch `feature/yellowback-price-attest`, off `yecwallet-legacy` (= v4.5.0)
│                    (`feature/digidollar` in both: the retired federation prototype, kept as a record — never built on)
├── lightwalletd-dd/ WORKING FORK of lightwalletd. branch `feature/yellowback-price-attest`, off `lightwalletd-legacy` (= 187a26765e)
├── ycash6/          WORKING FORK of the v6.20.0 node. branch `feature/yellowback`, off `ycash6-legacy` (= 040894344b) — the v6 port, see "Two node lines" below
├── librustzcash6/   WORKING FORK of the patched librustzcash. branch `feature/yellowback`, off `librustzcash6-legacy` (= ec525fae82)
├── kogany/          WORKING FORK of Zakura, THE THIRD NODE LINE. branch `upgrade/vault`, off `kogany-legacy` (= 2b062412c5) — just forked, no overlay yet, see "The third node line" below
├── zakura-common-ycash/ WORKING FORK of zakura-core/common (the common fork, kogany plan K-2): the zakura-* librustzcash crates and
│                    zakura-zcash-script behind kogany's `[patch.crates-io]`. branch `upgrade/vault`, off `zakura-common-ycash-legacy`
│                    (= the W0-b base commit, repos.yaml); kogany work on `vaults/kogany-compat`
│                    (the branches above are the branches of record; the line being built is `upgrade/vault` — rule 2)
├── yew/             THE MOBILE WALLET (YEW), its own repo, branch `upgrade/vault` — plan docs/plans/yellowback-wallet-plan.md
├── yolo/            THE POOL SOFTWARE (yolo in Rust), its own repo, branch `upgrade/vault` — plan docs/plans/role-pool-regtest-plan.md
├── chain-viz/       THE CHAIN VISUALIZER (chain-viz), its own repo, branch `upgrade/vault` — plan docs/plans/chain-viz-plan.md
├── x402-ycash/      x402 AGENT PAYMENTS (x402-ycash), its own repo, branch `upgrade/vault` — plan docs/plans/x402-agent-payments-plan.md
├── yb-calibration/  THE PARAMETER CALIBRATION TOOL (yb-calibration), its own repo, branch `upgrade/vault` — calibrates the constants baked into Yellowback releases
├── hawkeye/         THE BRIDGE ATTESTOR (Hawkeye), its own repo, branch `upgrade/vault` — the wYEC bridge's attestor sidecar, plan hawkeye/docs/hawkeye-bridge-plan.md
├── ycash-infra/     THE LIGHT-WALLET BACKEND (ycash-infra), its own repo, branch `upgrade/vault` — Kubernetes (kind + EKS), plan ycash-infra/docs/plans/ycash-infra-plan.md
├── ycash-ops/       THE OPERATIONS REPO (ycash-ops), PRIVATE, its own repo, branch `main` (no `upgrade/vault` yet) — the GitHub Actions that deploy the testnets on AWS from ycash-infra's recipes; no account identifiers in it
├── wyec/            THE BRIDGE CONTRACTS (wYEC), its own repo, branch `upgrade/vault` — the Ethereum side of the vault upgrade's bridge, plan docs/plans/yellowback-upgrade-plan.md §4.3
├── docs/
│   ├── spec/        yellowback-risk-profile.md (READ FIRST: the collateral model as the upgrade/vault node
│   │                enforces it, vs DigiDollar), the DigiDollar upstream docs, and the generated v3/harden
│   │                spec (`make spec`; the upgrade/vault spec is generated into the node trees, `make spec-in-term`)
│   ├── plans/       THE DEVELOPMENT PLANS (current = yellowback-upgrade-plan.md, the vault network upgrade,
│   │                its Execution status block is authoritative; yellowback-evidence-based-hardening-plan.md
│   │                = harden/yellowback, the no-upgrade fallback; v3 = yellowback-v3-development-plan.md
│   │                and v2 = the miner-enforced plan, both delivered, now history; one plan per component)
│   │   ├── ycash6/     the 6.20.0 port's Phase 7 survey and the upstream defect report
│   │   └── archived/   README only: the retired federation design lives at tag `archive/v1-federation`
│   ├── audits/      the 2026-10-01 security audit of every component and its remediation checklist
│   ├── ideation/    README only: experimental ideas live on `ideation/*` branches, never on main
│   └── mapping.md   ← THE FILE-BY-FILE CROSSWALK (node §1–§11, wallet §12, v2/v3 §13–§14, lightwalletd
│                       §15, YEW §16, yolo §17, chain-viz §18, v4.5.0→6.20.0 port §19, x402 §20,
│                       hardening §21, vault upgrade §22, kogany (Zakura) port §24). READ IT FIRST.
├── repos.yaml       the manifest: every repo, URL, pin (plain nested clones — NOT submodules)
├── scripts/         bootstrap.sh (`make bootstrap`), pull.sh (`make pull`), repos.sh, repo-status.sh,
│                    extract-spec.sh + extract_spec.py (`make spec`), check-ref-pins.sh (CI: pins vs upstream)
├── wt/              git worktrees of the forks for parallel agents (untracked, gitignored)
├── yellowback.code-workspace   VS Code multi-root workspace (ref/ folders read-only)
└── AGENTS.md / CLAUDE.md   (this file; CLAUDE.md is a symlink to it)
```

**One overlay, two node lines (a third, `kogany`, just started), ten component repos.** Yellowback is an overlay on the node
(`ycash-dd` and `ycash6`, below) — on `upgrade/vault`, the one registered rule module (`YED\0`) on
the vault network upgrade's lock/unlock primitive, beside the wYEC bridge template; around it sit the GUI wallet, lightwalletd, the mobile wallet
(YEW), the mining pool (yolo), the visualizer (chain-viz), x402 agent payments (x402-ycash), the
parameter calibration tool (yb-calibration), the wYEC bridge contracts (wyec), the bridge attestor (hawkeye) and the light-wallet backend (ycash-infra), each in its own
repo and each reaching the node only through a public interface (README.md, the components table).
The node fork (`ycash-dd`) adds the Yellowback overlay and its `yed_*`
RPCs; the wallet fork (`yecwallet-dd`) adds the Yellowback screens on top of those RPCs and bundles
the node build. DigiByte's `src/qt/digidollar*` is the behavioural reference for the wallet
fork the way `src/digidollar/` is for the node fork — and it is just as much *not* source to
copy: DigiByte's widgets read in-process wallet models; YecWallet reads everything over JSON-RPC
(`ref/yecwallet/src/controller.cpp`, `connection.cpp`).

**Two node lines, one overlay.** `ycash-dd` (v4.5.0) is the primary Yellowback node line.
`ycash6` (ycashd 6.20.0, another Ycash developer's rebase onto the Zcash 6.x lineage) carries the
same overlay, ported with `ycash-dd`'s delta (`make diff`) as the source and `docs/mapping.md` §19
as the crosswalk, and it is the release line (tag-driven GitHub releases,
`ycash6/doc/yellowback-release.md`): **6.22.x for `upgrade/vault`**, 6.21.x for the
`harden/yellowback` fallback; the release workflow refuses a tag whose version does not match its
line or whose heights are unset. **No activation height is set on any public network**: the old
`START_HEIGHT` 3,075,000 / `ENFORCE_UNTIL_HEIGHT` 3,495,480 were withdrawn (hardening F-5), the
upgrade line has neither (no sunset; `UPGRADE_VAULT`'s mainnet height and attestor set are set by
the gate-passing release, plan P8; testnet is unreachable), and regtest/devnet activate it with
`-nuparams=6d5b7a31:<h>`. Both lines carry the same branch ID (`0x6d5b7a31`) and parameters
and must stay in step: **a shared Yellowback defect or rule change is made on both lines together** —
the primitive, the module and the branch ID are one change on both —
(the shared-defect rule, kogany plan K-19: the C++ lines together; `librustzcash6`, the common fork
`zakura-common-ycash` and `kogany` follow in the same change set from W2 on, once they implement the
affected layer, and record it in the kogany plan's findings log until then)
and the clients (YecWallet, lightwalletd, the devnet, yolo, chain-viz, YEW, x402) are tested against both.
`ycash6` builds against `librustzcash6`: `ref/ycash6/Cargo.toml` `[patch.crates-io]` pins every
`zcash_*` crate to `miodragpop/librustzcash` rev `ec525fae`, which is exactly `ref/librustzcash6`.
**On `upgrade/vault` `librustzcash6` is no longer zero-delta**: it adds `NetworkUpgrade::Vault` /
`BranchId::Vault = 0x6d5b7a31` (`4867cf85`; since audit 04/F-6 Vault is v4-only there too,
`has_orchard() = false`, V5 not valid, `eeb7740d`), and `ycash6/Cargo.toml` pins every `zcash_*` crate to
`boyfromcave/librustzcash6` at `eeb7740d`. On `harden/yellowback` it stays a zero-delta fork. (It is
a separate repo, not a GitHub fork, because `boyfromcave/librustzcash` is already an older fork.)

**The third node line: `kogany`** (lead architect, 2026-11-01). `kogany` is the Ycash developers' GitHub fork of
Zakura (`ref/zakura`: zakura-core's consensus-compatible Zcash full node in Rust, forked from
Zebra), pinned at zakura `main` @ `2b062412c5` (past v1.7.0; the lead architect's choice, the commit the fork
was taken at). `kogany-legacy` is that pin (**never commit to it**) and `upgrade/vault` was cut
from it; nothing is ported yet, so `make diff` shows no delta. It is a third codebase lineage
(Rust, the Zebra architecture, no `src/main.cpp`, no `CCoins`), so the crosswalk is new work:
`docs/mapping.md` gets a section for it before the first port, and the four-part check (rule 4)
applies as on the other lines. Until it carries the overlay, the both-lines rules above (one
change on every line, the shared branch ID, clients tested against each line) do not yet include
it (beyond the shared-defect rule's W2 clause above), and `make spec` / the release train do not
cover it; kogany becomes a qualified line only at the end of its plan's W9, by the lead architect's
sign-off (K-19). Its crate fork is **`zakura-common-ycash`** (K-2: one feature-gated fork of
`zakura-core/common`, `ycash` cargo feature; with the feature off the crates are upstream's), pinned
by exact `git` rev in kogany's `[patch.crates-io]` as `ycash6` pins `librustzcash6`; its baseline
`zakura-common-ycash-legacy` is the upstream commit that reproduces the crates.io releases kogany
locks (kogany plan W0-b). Zakura's own `AGENTS.md` / `CLAUDE.md` /
`.claude/` ship in the tree and describe upstream's conventions; where they conflict with this
file, this file wins (rule 8 above all). **Its GitHub Actions stay off** except the
lead architect's allowlist (K-15, 2026-11-01): six trimmed upstream workflows, the workspace security
CI and `kogany-yellowback.yml`; every other upstream workflow is moved to
`.github/workflows-disabled/` (kogany plan §5, W0-c), and jobs are enabled one at a time.

## Rules

### 1. `ref/` is read-only. Never edit, never commit, never checkout.

All eight `ref/` checkouts are pinned in detached HEAD (to a tag, or for `ref/lightwalletd`, `ref/ycash6`,
`ref/librustzcash6` and `ref/yolo`, whose upstreams publish no tags, and `ref/zakura`, pinned past its last tag by choice, to a commit) and their working trees are `chmod -R a-w`. They exist to be **read and grepped**, never modified. If a write fails with
`Permission denied` under `ref/`, that is the guardrail working — you are editing the wrong tree.
The file you want is under `ycash-dd/`.

To re-pin deliberately (rare): `chmod -R u+w ref/<repo>` → checkout → `chmod -R a-w ref/<repo>`,
and update the pins recorded in this file and in `docs/mapping.md`.

### 2. All work happens in `ycash-dd/`, `yecwallet-dd/` and `lightwalletd-dd/` — and, for the 6.20.0 node line, in `ycash6/` and `librustzcash6/`, and for the third node line in `kogany/` and `zakura-common-ycash/` — on `upgrade/vault`; the branches of record are `feature/yellowback-price-attest` and, on the 6.20.0 line, `feature/yellowback`.

**`upgrade/vault` is the line being built** (owner, 2026-10-06; `docs/plans/yellowback-upgrade-plan.md`):
the integration branch in `ycash-dd`, `ycash6`, `librustzcash6` and every client repo (YecWallet,
lightwalletd, YEW, yolo, chain-viz, x402-ycash), and the GitHub default branch of all of them.
`repos.yaml` records it and the main trees check it out (since 2026-10-06), so `make status` and
`make pull` track it and integration happens in the main trees. Agents work in `wt/<name>` on
`up/<name>` off `upgrade/vault`; the coordinator merges.
**The kogany work is on `vaults/kogany-compat`** (lead architect, 2026-11-01): `upgrade/vault` is
stable, so every writable repository carries `vaults/kogany-compat` (cut from `upgrade/vault`;
ycash-ops from `main`), where the kogany node, the Zakura library fork, `yewd` and every
kogany-related change in the C++ lines and the clients land; it merges back into `upgrade/vault`
only at the wave gates of `docs/plans/kogany/kogany-yellowback-plan.md` (§4.2 rule 0). Main trees
stay on `upgrade/vault`; kogany agents work in `wt/kc-<name>` on `kc/<name>` off
`vaults/kogany-compat`. The branch names are the same in `kogany` and in the common fork
`zakura-common-ycash`: `upgrade/vault` is the branch of record (`repos.yaml`), `vaults/kogany-compat`
the integration branch, `kc/<name>` the agent branches, and `kogany-legacy` /
`zakura-common-ycash-legacy` the untouchable baselines (`kogany-baseline` is the tag the kogany CI
audit measures the consensus delta against, kogany plan W0-d).
**In-term claims are on `upgrade/vault`** (owner, 2026-10-09): `upgrade/vault` was fast-forwarded to
`upgrade/vault-in-term` in ycash-dd, ycash6, lightwalletd-dd, yecwallet-dd, chain-viz and yew
(`docs/plans/yellowback-in-term-claims-plan.md`). `upgrade/vault-in-term` is kept as a record — never
commit to it — and the tag `upgrade/vault-pre-in-term` marks each repo's `upgrade/vault` before the move.
**`harden/yellowback`** — the evidence-based hardening plan's branch
(`docs/plans/yellowback-evidence-based-hardening-plan.md`), cut 2026-10-05 from each repo's branch
of record below — is the **no-upgrade fallback**: its fixes merge `harden/yellowback` →
`upgrade/vault`, never the other way; it is worked in `wt/` worktrees. The workspace repo itself,
`yb-calibration` and `wyec` are on `upgrade/vault` too (GitHub default on all three since 2026-10-12;
the workspace's and `yb-calibration`'s content serves both lines, and their `harden/yellowback`
branches are the fallback's). **Every writable repo in this workspace checks out `upgrade/vault`.**
The branches of record named in this file are where the fallback work returns.

**The current design is the vault network upgrade, with Yellowback as its rule module.** v3 (price
attestation, `feature/yellowback-price-attest` in all three v4.5.0-era forks, cut from
`feature/yellowback-sf`) is delivered history and the base of the fallback; its price attestation
carries over into the module. `feature/yellowback-sf`
is the superseded v2 fork, kept only as a record: never commit to it and **never use it as a
comparison base**.

**On `upgrade/vault` the frozen-file zero-delta rule is replaced by the consensus review gate**
(upgrade plan §7 G-9, §9): every changed line under `src/consensus/`, `src/script/`, `main.cpp` and
`src/primitives/`, on both lines, is reviewed by two people independent of the author, with the
four-part check (rule 4) in the PR body. The CI audit's frozen-file and line-budget legs are
report-only there (print the delta, never fail); the `-legacy` line budgets stay as a size
measure, not a gate. **On `harden/yellowback` the zero-delta rule stands**: frozen-file checks measure against the tag `yellowback-v3-baseline`
(ycash-dd, = `feature/yellowback-price-attest` at `ff7f45947`; re-tagged 2026-10-02 at the security-audit merge, which carried two reviewed hook changes in `main.cpp`/`rpc/mining.cpp` — audit A-1, A-7; the previous tag commit was `9da72131e`) or, for a change in review, against
`origin/feature/yellowback-price-attest`; line budgets against the `-legacy` baseline. The branch is
declared once, in `repos.yaml`; `make status` fails if a fork is not on it.

`ycash-legacy` and `yecwallet-legacy` are the pristine v4.5.0 baselines, `lightwalletd-legacy`
is upstream `master` at the pin, and `ycash6-legacy` / `librustzcash6-legacy` are the v6.20.0 pins and `kogany-legacy` the Zakura pin (`zakura-common-ycash-legacy` the common fork's base) — **never commit to them.** They exist so you can always `git diff <legacy>...feature/yellowback-price-attest` to see
the entire fork delta (`make diff` shows both). `feature/digidollar` in both forks is the retired federation
prototype (plan §0, 2026-09-10), kept only as a record: never commit to it and never build on it;
`make log` may list both. Keep those diffs reviewable. Node code goes in `ycash-dd`
only; wallet code goes in `yecwallet-dd` only; light-client server code goes in `lightwalletd-dd`
only; the `yed_*` RPC surface — plus, on `upgrade/vault`, the vault primitive's `set_*` and
`vault_*` RPCs (`doc/vault-rpc.md`) — is the sole interface between the node and either client
(plan §4.7; upgrade plan §9). The bridge daemon uses only those plus stock RPCs.
Mobile-wallet (YEW) client code — the YEW core and its shells: `app`, `web`, `yewd` (the YEW core as a
daemon, the kogany wallet sidecar, `yew/yewd/`; kogany plan K-22) — goes in `yew/` only — its own
repository on `main`, not a fork, so it has no `-legacy` baseline (and `yewd` has no `repos.yaml`
row of its own) — and lightwalletd's `CompactTxStreamer` + `YellowbackStreamer`
gRPC services are its sole interface (`docs/plans/yellowback-wallet-plan.md`).
Pool software goes in `yolo/` only — also its own repository on `main` (`ref/yolo` is the Perl
reference it rewrites) — and the node's stock mining RPCs (`getblocktemplate`, `submitblock`,
`validateaddress`, `getblockchaininfo`) are its sole interface: a pool never calls `yed_*` and
never needs a node change (`docs/plans/role-pool-regtest-plan.md` §6).
The visualizer goes in `chain-viz/` only — its own repository on `main` — and it is a strictly
read-only sidecar: it reaches the node through the stock read RPCs (`getblock`, `getrawmempool`,
`getchaintips`, `getblocktemplate`, …), the read-only `yed_*` RPCs and the node's notify hooks,
never writes a transaction, and never needs a consensus change (`docs/plans/chain-viz-plan.md` §4).
x402 agent payments go in `x402-ycash/` only — its own repository on `main`, net new, no reference
and no baseline — and it reaches the node only through stock RPCs (`gettxout`, `sendrawtransaction`,
`signrawtransaction` as a verifier, `z_*` receipt RPCs) and the read-only `yed_*` RPCs: no node
change on either node line, nothing for node or pool operators to enable
(`docs/plans/x402-agent-payments-plan.md` §4).
Parameter calibration goes in `yb-calibration/` only — its own repository on `upgrade/vault`, net new, no
reference and no baseline. It derives and checks the constants each Yellowback release bakes into
the node (both node lines): a constant changes in `ycash-dd`/`ycash6` only with the calibration
result that justifies it, and the calibration tool never edits a node fork itself.
The wYEC bridge contracts go in `wyec/` only — its own repository on `upgrade/vault`, net new, no reference
and no baseline. It is the Ethereum side of the vault upgrade's bridge and the component the
bridge's guardians and relayer run against; Ycash consensus never reads Ethereum (upgrade plan R2),
so nothing in `wyec/` is ever a dependency of either node line.
The bridge attestor goes in `hawkeye/` only — its own repository on `upgrade/vault`, net new, no
reference and no baseline. It reaches `ycashd` only through stock RPCs and the vault primitive's
`set_*` / `vault_*` RPCs (never `yed_*`) and Ethereum only through standard JSON-RPC, fetches the
wyec contracts at a pinned commit, and never needs a node change (`hawkeye/AGENTS.md`).
The light-wallet backend goes in `ycash-infra/` only — its own repository on `upgrade/vault`, net
new, no reference and no baseline. It deploys `ycashd`, `lightwalletd-dd`, its own address index
(`yindex`) and the `yew/web` bundle on Kubernetes; it reaches `ycashd` only through stock JSON-RPC,
reaches `lightwalletd-dd` only by running its image, builds images from the workspace trees rather
than copying source, and never needs a node or lightwalletd change (`ycash-infra/AGENTS.md`).
On `upgrade/vault` the client rules above stand — yolo, chain-viz, x402-ycash and YEW still need no
consensus or node change of their own — but each is a **client update** on its own `upgrade/vault`
branch: the new branch ID `0x6d5b7a31` for signing or verifying (x402 signs for the next block's
branch, YEW signs vault spends; yolo needed no source change and is tested mining across the
activation), `rpcversion` 8 (5 was the vault upgrade, 7 post-quantum owners, 8 the fee rules:
`YELLOWBACK_RPC_VERSION` in `src/rpc/yellowback.cpp` on both node lines; Hawkeye parses only the
post-quantum owner shape and needs this line, `hawkeye/README.md` "Node requirement"), and the vault primitive's read RPCs (lightwalletd's read-only vault
calls, chain-viz's set/vault panels).

> The `feature/` prefix is deliberate. Git cannot hold a branch named `x` and a branch named
> `x/y` in the same repo at once, so a `dev/` prefix would have blocked checking out upstream
> Ycash's own `dev` branch locally. Upstream has no `feature` branch, so this prefix collides
> with nothing.

### 3. Read `docs/mapping.md` before porting anything.

This is the important one. **DigiByte v9.26.5 and Ycash v4.5.0 are not the same kind of codebase.**

| | DigiByte v9.26.5 | Ycash v4.5.0 |
|---|---|---|
| Lineage | Bitcoin Core ~v26/28 | Zcash 4.5 → Bitcoin Core ~0.11/0.12 |
| SegWit / Taproot / Tapscript | yes | **none of them** |
| Sighash | legacy, BIP143, BIP341, BIP342 | Sprout, ZIP-143, **ZIP-243** (bound to `consensusBranchId`) |
| Activation | BIP9 versionbits | height-gated **network upgrades** (new branch ID) |
| Tx `nVersion` | free for DigiDollar bit-packing | pinned to `4` + `fOverwintered` bit + `nVersionGroupId` |
| UTXO model | per-output `Coin` | per-tx `CCoins` |
| Validation entry point | `src/validation.cpp` | `src/main.cpp` (monolithic) |
| Shielded pools | none | Sprout JoinSplits + Sapling |
| Oracle / MuSig2 / Schnorr | `src/oracle/`, enabled | absent |
| Qt GUI | `src/qt/` | absent |

**The specific failure mode this workspace exists to prevent:** grepping `ref/digibyte` for
`OP_DIGIDOLLAR`, finding it in `src/script/interpreter.cpp`, and transplanting it into Ycash's
`src/script/interpreter.cpp`. DigiByte's DD opcodes (0xbb–0xbf) are gated on
`sigversion == SigVersion::TAPSCRIPT` and get their soft-fork safety from BIP342 `OP_SUCCESSx`.
Ycash has **no Tapscript**, its `SigVersion` enum means something else entirely (a sighash
algorithm: `SIGVERSION_SPROUT/OVERWINTER/SAPLING`), and bytes 0xbb–0xbf hit
`default: return set_error(serror, SCRIPT_ERR_BAD_OPCODE)` at
`ref/ycash/src/script/interpreter.cpp:942`. A verbatim port compiles and is consensus-dead.

See `docs/mapping.md` §2 for what to do instead. On `upgrade/vault`, new opcodes are allocated
**above `OP_NOP10`** (`OP_CHECKSETSIG` 0xc0, `OP_CHECKSETDORMANT` 0xc1; `OP_CHECKSEQUENCEVERIFY`
takes 0xb2) and are gated on the Vault branch ID (`UPGRADE_VAULT`) — **never 0xbb–0xbf**; the
mapping §2 row is the reason.

### 4. Before you port a symbol, do the four-part check.

Write it down in the commit message or the PR body:

> DigiByte does **X** in file **Y** using mechanism **M**.
> The Ycash equivalent is **Z**, which lacks **M**.
> So the adaptation is **W**.

If you cannot fill in **W**, you are not ready to write code. If **M** turns out to be
Taproot, SegWit, BIP9, `nVersion` bit-packing, the `Coin` model, or MuSig2 — stop and check
`docs/mapping.md`; there is already a row for it.

Then one more: **which tier does W land on, and why won't a cheaper tier do?** A consensus change
needs that answer in writing before any code. On `upgrade/vault` the tier itself is answered by the
requirements (a network upgrade, R3/O-1 — prime directive); the question becomes which rung of the
in-tier ladder (template, opcode, transaction field; per-vault or global state; primitive or
module) and why a lower one won't do. A consensus PR without the answer is rejected at the review
gate (rule 2).

### 5. Update `docs/mapping.md` as you go.

Every new impedance mismatch gets a row, with `repo/path/file.ext:line` citations at the pinned
tags — even if the workaround took five minutes. The file's value is that the next session does
not rediscover the same trap.

### 6. Naming

One rule covers every case: **Yellowback is the thing. YED is the unit.** Same relationship as
Bitcoin/BTC or dollar/USD — never "5 yellowbacks YED", never "the YED protocol".

- **YED when a number is attached or implied:** `1 YED = $1`, "you minted 250 YED", balances,
  price feeds, collateral ratios, exchange listings. Code that counts units: `yedAmount`,
  `yedIn`/`yedOut`, `yed_getbalance`, `yed_mint`.
- **Yellowback when naming the thing itself:** "Yellowback is a decentralized dollar on Ycash",
  the whitepaper title, the position or note ("minting a Yellowback against locked YEC"). Code
  that names the system: `CYellowbackPosition`, `src/yellowback/`, namespace `yellowback`,
  `-yellowback` config flags, log category `yellowback`.
- **The test:** if the word could be swapped for "dollars", it is YED. If it could be swapped for
  "the product" or "the system", it is Yellowback.
- **First mention in any formal document:** "Ycash Yellowback (YED)"; then YED for amounts and
  Yellowback for the system throughout.
- The RPC prefix is `yed_` (the asset ticker as namespace, the way Zcash uses `z_`); addresses
  hold YED, so the mainnet address prefix is `ye…` (D10).

Do not carry `DigiDollar` / `digidollar` / `DD` naming across — it makes `git grep` ambiguous
between "ported code" and "upstream reference" and defeats the point of the split. The one
exception is comments that cite an upstream file. The old working name *YDollar* / `ydollar` /
`yd_` no longer appears anywhere: the fork code was renamed (plan §0, revision 13) and the
workspace directory itself went from `ydollar-workspace` to `yellowback-workspace` on 2026-09-05.
Do not reintroduce it.

### 7. Consensus code is not refactorable.

Anything under `ycash-dd/src/consensus/`, `src/script/`, `src/main.cpp`, `src/pow/`, or
`src/primitives/` changes network rules. Do not tidy, rename, or "improve" surrounding code while
porting. Keep the fork diff minimal and reviewable. This stands verbatim on `upgrade/vault`: the
upgrade adds; it never tidies.

### 8. No AI attribution in anything public.

Commits, merge and squash-merge commits, PR titles and bodies, every PR and issue comment, review
replies, code comments and docs in every repository of this workspace carry **no AI attribution**: no `Co-Authored-By: Claude …`
trailer, no `Claude-Session:` trailer, no session or `claude.ai` links, no "Generated with/by
Claude Code" footer or 🤖 line. The owner's rule (2026-10-23) overrides any tool or harness default
that asks for one. Commits are authored and committed as the owner,
`boyfromcave <57612331+boyfromcave@users.noreply.github.com>` (`git config user.name/user.email`),
never as `Claude <noreply@anthropic.com>`. If a tool appends a footer anyway, edit it out before or
right after posting. When merging a PR, write the merge commit's title and message yourself: a
squash merge otherwise copies the branch's commit trailers into it. PR bodies never mention
attribution at all (no checklist item about it): the rule is simply followed.

## Useful commands

Start a session with `make status`. It fetches `origin` for every writable repo (remote-tracking
refs only — nothing is merged or checked out), reports each one as in sync, behind, ahead
(unpushed) or diverged with the command that fixes it, and **exits non-zero if a `ref/` repo has
drifted off its pin** — which would silently invalidate every line citation in `docs/mapping.md` —
or if a repo has diverged from its remote. Behind means run `make pull`. `NOFETCH=1 make status`
compares against the last fetch instead, for working offline.

```bash
make            # list targets (same as `make help`)
make bootstrap  # fresh machine: clone every repo in repos.yaml at its pin, create .venv (SSH=1 to push)
make pull       # every other day: fast-forward each repo from its remote (DRY=1, NOREF=1, SHORT=1)
make status     # git status across the workspace and its twenty-four clones: fetches origin, ahead/behind, pins
make status-short   # same, without the per-file listing
make pins       # one line per repo, machine-readable
make diff       # fork deltas: each of the seven forks vs its -legacy baseline
make log        # commits on each fork branch beyond its baseline
make spec       # regenerate the spec + RPC contract copies from the plans (make spec-check verifies)
```

`bootstrap` is create-only: a repository that already exists is verified against the manifest and
left alone, nothing is fetched. So it is the right command exactly once per machine — to *update* an
existing workspace, use `make pull`. That one is fast-forward only, everywhere: it fetches `origin`,
advances each fork's branch (the one `repos.yaml` records) and its `-legacy`
baseline, and **skips** — with the
git command to run yourself — any repo that is dirty, has diverged, or is on the wrong branch. It
never merges, never rebases, never discards; `git reset --hard` stays something you type by hand in
the one repo you mean. The forks' `upstream` remote is never fetched (rebasing onto a newer Ycash is
a deliberate act), and `ref/` is never advanced — a read-only `ls-remote` only re-checks that the
pinned tag still resolves to the commit `repos.yaml` records. If it has moved upstream, `make pull`
fails loudly: every `file:line` citation in `docs/mapping.md` was taken at the old commit. The `wt/`
worktrees carry per-agent branches and are reported, never touched.

The pins are declared once, in `repos.yaml` (the `Makefile` reads them from there), and mirrored
in this file and in `docs/mapping.md`. If you re-pin a reference repo, update all three. Never
convert the nested clones to submodules: the read-only `ref/` trees and the independently pushed
forks depend on each being an ordinary repository.

```bash
# Search upstream DigiDollar (read-only)
git -C ref/digibyte grep -n 'OP_DIGIDOLLAR' -- src/

# Search the Ycash baseline (read-only)
git -C ref/ycash grep -n 'SignatureHash' -- src/

# Search DigiByte's DigiDollar GUI and YecWallet (both read-only)
git -C ref/digibyte grep -n 'DigiDollarMintWidget' -- src/qt/
git -C ref/yecwallet grep -n 'doRPCWithDefaultErrorHandling' -- src/
```
