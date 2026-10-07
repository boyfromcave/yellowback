# yellowback-workspace — agent instructions

Bring a decentralized digital dollar to **Ycash** as **Ycash Yellowback (YED)**, using DigiByte's **DigiDollar**
as the reference implementation — in the node (`ycashd`) **and** in the full-node GUI wallet
(**YecWallet**, a Qt application that bundles and drives `ycashd` over RPC). Start with
[README.md](README.md) for the goal and the change-budget ladder; this file is the working rules.

**The prime directive is minimal change to the Ycash codebase.** The Ycash team is risk-averse and
the shielded pool's soundness rests on consensus code few people fully understand. Prefer the
cheapest tier that works: Tier 0 (existing opcodes, wallet/RPC, observer hooks, experimental flag —
what Ycash's own atomic-swap feature did in commit `ccddd22e4`) over a soft fork, and a soft fork
over a coordinated network upgrade. When a design trades elegance for a smaller consensus
footprint, take the smaller footprint and record what was given up.

## Layout

```
yellowback-workspace/
├── ref/
│   ├── digibyte/    READ-ONLY. DigiByte, pinned to tag v9.26.5 (05b50e229d)
│   ├── ycash/       READ-ONLY. Ycash node, pinned to tag v4.5.0 (624c12814)
│   ├── yecwallet/   READ-ONLY. YecWallet GUI (Qt 6, bundles ycashd), pinned to tag v4.5.0 (1eb277d)
│   ├── lightwalletd/ READ-ONLY. yodl/lightwalletd (zcash/lightwalletd 0.4.6 + Ycash regex), master @ 187a26765e (no tag)
│   ├── ycash6/      READ-ONLY. miodragpop/ycash, ycashd 6.20.0 (Zcash 6.x lineage), dev-rebase-6.20.0 @ 040894344b (no tag)
│   ├── librustzcash6/ READ-ONLY. miodragpop/librustzcash, the patched librustzcash ref/ycash6's Cargo.toml pins, ycashd-v6.20.0 @ ec525fae82 (no tag)
│   └── yolo/        READ-ONLY. yecdev/yolo, the Perl solo-pool stratum servers (stratumpool/stratumsolo/cenote), main @ c9c155c6 (no tag)
├── ycash-dd/        WORKING FORK of the node.   branch `feature/yellowback-price-attest`, off `ycash-legacy`     (= v4.5.0)
├── yecwallet-dd/    WORKING FORK of the wallet. branch `feature/yellowback-price-attest`, off `yecwallet-legacy` (= v4.5.0)
│                    (`feature/digidollar` in both: the retired federation prototype, kept as a record — never built on)
├── lightwalletd-dd/ WORKING FORK of lightwalletd. branch `feature/yellowback-price-attest`, off `lightwalletd-legacy` (= 187a26765e)
├── ycash6/          WORKING FORK of the v6.20.0 node. branch `feature/yellowback`, off `ycash6-legacy` (= 040894344b) — the v6 port, see "Two node lines" below
├── librustzcash6/   WORKING FORK of the patched librustzcash. branch `feature/yellowback`, off `librustzcash6-legacy` (= ec525fae82)
├── yew/             THE MOBILE WALLET (YEW), its own repo, branch `main` — plan docs/plans/yellowback-wallet-plan.md
├── yolo/            THE POOL SOFTWARE (yolo in Rust), its own repo, branch `main` — plan docs/plans/role-pool-regtest-plan.md
├── chain-viz/       THE CHAIN VISUALIZER (chain-viz), its own repo, branch `main` — plan docs/plans/chain-viz-plan.md
├── x402-ycash/      x402 AGENT PAYMENTS (x402-ycash), its own repo, branch `main` — plan docs/plans/x402-agent-payments-plan.md
├── yb-calibration/  THE PARAMETER CALIBRATION TOOL (yb-calibration), its own repo, branch `main` — calibrates the constants baked into Yellowback releases
├── wyec/            THE BRIDGE CONTRACTS (wYEC), its own repo, branch `main` — the Ethereum side of the vault upgrade's bridge, plan docs/plans/yellowback-upgrade-plan.md §4.3
├── docs/
│   ├── spec/        DigiDollar upstream spec + the generated Yellowback spec (`make spec`)
│   ├── plans/       THE DEVELOPMENT PLANS (v3 = yellowback-v3-development-plan.md, current, revision 4;
│   │                v2 = the delivered miner-enforced plan v3 is a delta on; one plan per component)
│   │   ├── ycash6/     the 6.20.0 port's Phase 7 survey and the upstream defect report
│   │   └── archived/   README only: the retired federation design lives at tag `archive/v1-federation`
│   ├── audits/      the 2026-10-01 security audit of every component and its remediation checklist
│   ├── ideation/    README only: experimental ideas live on `ideation/*` branches, never on main
│   └── mapping.md   ← THE FILE-BY-FILE CROSSWALK (node §1–§11, wallet §12, v2/v3 §13–§14, lightwalletd
│                       §15, YEW §16, yolo §17, chain-viz §18, v4.5.0→6.20.0 port §19, x402 §20). READ IT FIRST.
├── repos.yaml       the manifest: every repo, URL, pin (plain nested clones — NOT submodules)
├── scripts/         bootstrap.sh (`make bootstrap`), pull.sh (`make pull`), repos.sh, repo-status.sh,
│                    extract-spec.sh + extract_spec.py (`make spec`), check-ref-pins.sh (CI: pins vs upstream)
├── wt/              git worktrees of the forks for parallel agents (untracked, gitignored)
├── yellowback.code-workspace   VS Code multi-root workspace (ref/ folders read-only)
└── AGENTS.md / CLAUDE.md   (this file; CLAUDE.md is a symlink to it)
```

**One overlay, two node lines, eight component repos.** Yellowback is an overlay on the node
(`ycash-dd` and `ycash6`, below); around it sit the GUI wallet, lightwalletd, the mobile wallet
(YEW), the mining pool (yolo), the visualizer (chain-viz), x402 agent payments (x402-ycash), the
parameter calibration tool (yb-calibration) and the wYEC bridge contracts (wyec), each in its own
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
as the crosswalk, and it is the release line (6.21.x: tag-driven GitHub releases,
`ycash6/doc/yellowback-release.md`; 6.21.0-rc1 is set, not yet tagged). Both lines carry the same
mainnet parameter set (`START_HEIGHT` 3,075,000, `ENFORCE_UNTIL_HEIGHT` 3,495,480; testnet unset)
and must stay in step: **a shared Yellowback defect or rule change is made on both lines together**,
and the clients (YecWallet, lightwalletd, the devnet, yolo, chain-viz, YEW) are tested against both.
`ycash6` builds against `librustzcash6`: `ref/ycash6/Cargo.toml` `[patch.crates-io]` pins every
`zcash_*` crate to `miodragpop/librustzcash` rev `ec525fae`, which is exactly `ref/librustzcash6`.
If a Yellowback change ever needs a librustzcash change, it goes in `librustzcash6/` and
`ycash6/Cargo.toml` is repointed at `boyfromcave/librustzcash6`; until then `librustzcash6` is a
zero-delta fork (it is a separate repo, not a GitHub fork, because `boyfromcave/librustzcash` is
already an older fork).

## Rules

### 1. `ref/` is read-only. Never edit, never commit, never checkout.

All seven `ref/` checkouts are pinned in detached HEAD (to a tag, or for `ref/lightwalletd`, `ref/ycash6`,
`ref/librustzcash6` and `ref/yolo`, whose upstreams publish no tags, to a commit) and their working trees are `chmod -R a-w`. They exist to be **read and grepped**, never modified. If a write fails with
`Permission denied` under `ref/`, that is the guardrail working — you are editing the wrong tree.
The file you want is under `ycash-dd/`.

To re-pin deliberately (rare): `chmod -R u+w ref/<repo>` → checkout → `chmod -R a-w ref/<repo>`,
and update the pins recorded in this file and in `docs/mapping.md`.

### 2. All work happens in `ycash-dd/`, `yecwallet-dd/` and `lightwalletd-dd/`, on their `feature/yellowback-price-attest` branches — and, for the 6.20.0 node line, in `ycash6/` and `librustzcash6/` on `feature/yellowback`.

**Since 2026-10-05 every writable repository, the workspace included, is checked out on
`harden/yellowback`** — the evidence-based hardening plan's branch
(`docs/plans/yellowback-evidence-based-hardening-plan.md`), cut from each repo's branch of record
below and merged back into it when the plan's gates pass. `repos.yaml` records `harden/yellowback`
for the duration; the branches of record named in this file are where the work returns.

The current branch in all three v4.5.0-era forks is `feature/yellowback-price-attest` — the v3 price-attestation
work, cut from `feature/yellowback-sf`. **Yellowback is v3 (price attestation).** `feature/yellowback-sf`
is the superseded v2 fork, kept only as a record: never commit to it and **never use it as a
comparison base**. Frozen-file zero-delta checks measure against the tag `yellowback-v3-baseline`
(ycash-dd, = `feature/yellowback-price-attest` at `ff7f45947`; re-tagged 2026-10-02 at the security-audit merge, which carried two reviewed hook changes in `main.cpp`/`rpc/mining.cpp` — audit A-1, A-7; the previous tag commit was `9da72131e`) or, for a change in review, against
`origin/feature/yellowback-price-attest`; line budgets against the `-legacy` baseline. The branch is
declared once, in `repos.yaml`; `make status` fails if a fork is not on it.

`ycash-legacy` and `yecwallet-legacy` are the pristine v4.5.0 baselines, `lightwalletd-legacy`
is upstream `master` at the pin, and `ycash6-legacy` / `librustzcash6-legacy` are the v6.20.0 pins — **never commit to them.** They exist so you can always `git diff <legacy>...feature/yellowback-price-attest` to see
the entire fork delta (`make diff` shows both). `feature/digidollar` in both forks is the retired federation
prototype (plan §0, 2026-09-10), kept only as a record: never commit to it and never build on it;
`make log` may list both. Keep those diffs reviewable. Node code goes in `ycash-dd`
only; wallet code goes in `yecwallet-dd` only; light-client server code goes in `lightwalletd-dd`
only; the `yed_*` RPC surface is the sole interface between the node and either client (plan §4.7).
Mobile-wallet (YEW) client code goes in `yew/` only — its own repository on `main`, not a fork,
so it has no `-legacy` baseline — and lightwalletd's `CompactTxStreamer` + `YellowbackStreamer`
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
Parameter calibration goes in `yb-calibration/` only — its own repository on `main`, net new, no
reference and no baseline. It derives and checks the constants each Yellowback release bakes into
the node (both node lines): a constant changes in `ycash-dd`/`ycash6` only with the calibration
result that justifies it, and the calibration tool never edits a node fork itself.
The wYEC bridge contracts go in `wyec/` only — its own repository on `main`, net new, no reference
and no baseline. It is the Ethereum side of the vault upgrade's bridge and the component the
bridge's guardians and relayer run against; Ycash consensus never reads Ethereum (upgrade plan R2),
so nothing in `wyec/` is ever a dependency of either node line.

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

See `docs/mapping.md` §2 for what to do instead.

### 4. Before you port a symbol, do the four-part check.

Write it down in the commit message or the PR body:

> DigiByte does **X** in file **Y** using mechanism **M**.
> The Ycash equivalent is **Z**, which lacks **M**.
> So the adaptation is **W**.

If you cannot fill in **W**, you are not ready to write code. If **M** turns out to be
Taproot, SegWit, BIP9, `nVersion` bit-packing, the `Coin` model, or MuSig2 — stop and check
`docs/mapping.md`; there is already a row for it.

Then one more: **which tier does W land on, and why won't a cheaper tier do?** A consensus change
needs that answer in writing before any code.

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
porting. Keep the fork diff minimal and reviewable.

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
make status     # git status across the workspace and its eighteen clones: fetches origin, ahead/behind, pins
make status-short   # same, without the per-file listing
make pins       # one line per repo, machine-readable
make diff       # fork deltas: each of the five forks vs its -legacy baseline
make log        # commits on each fork branch beyond its baseline
make spec       # regenerate the spec + RPC contract copies from the plans (make spec-check verifies)
```

`bootstrap` is create-only: a repository that already exists is verified against the manifest and
left alone, nothing is fetched. So it is the right command exactly once per machine — to *update* an
existing workspace, use `make pull`. That one is fast-forward only, everywhere: it fetches `origin`,
advances each fork's branch of record (now `feature/yellowback-price-attest`) and its `-legacy`
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
