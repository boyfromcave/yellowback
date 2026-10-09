# Ycash Yellowback workspace

This project proposes a **Ycash network upgrade, the vault upgrade**. It gives Ycash one new,
general-purpose feature: **vaults**, YEC locked under rules that every node enforces, released only
with the approval of a bonded **signer set**, after a delay during which the release can be
cancelled, and always recoverable by its owner if the signers go silent. Two applications are built
on it: **Ycash Yellowback (YED)**, a dollar token backed by YEC in vaults, and **wYEC**, wrapped YEC
for Ethereum, backed by YEC in vaults.

This repository is the workspace that ties the pieces together: it pins the node, the wallets and
the tools side by side, and holds the plans, the design documents and the scripts that clone and
check them all.

> **Status: proposed, not live.** It runs on a local test network (regtest) only. It has not been
> adopted by the Ycash Foundation, has not been audited, and has no activation height on mainnet
> or testnet.

### The words used here

- **YEC**: Ycash's coin.
- **Vault**: YEC locked on chain under rules that every Ycash node enforces.
- **Signer set**: a group of bonded members (they lock YEC as a bond) that can approve releasing a
  vault. Members who cheat lose their bond; a set whose members go silent is treated as gone.
- **Release**: taking YEC out of a vault. A release approved by a signer set first becomes a
  **pending release** that waits for a fixed delay and can be cancelled during it. The vault's
  **owner** can always recover the YEC if the signer set goes silent.
- **The vault upgrade**: the proposed network upgrade that adds vaults and signer sets to Ycash's
  consensus rules. It is general-purpose: it knows nothing about dollars or Ethereum.
- **Ycash Yellowback (YED)**: lock YEC in a vault to mint YED (`1 YED = 1 US dollar`); return the
  YED to get the YEC back (always, even if the attestors go silent: a
  YED vault is only ever released by burning its YED). If a vault's YEC becomes worth less than the YED it backs, others can
  claim it. The YEC/USD price comes from mining pools and from **attestors** (members of
  Yellowback's signer set who sign prices).
- **wYEC (wrapped YEC)**: YEC represented as a token on Ethereum, backed 1:1 by YEC locked in Ycash
  vaults; a signer set releases the YEC when wYEC is burned. Ycash never reads Ethereum.
- **Network upgrade (hard fork)**: every node must upgrade before the activation height; a node
  that does not stops following the chain.

---

## The pieces

Each component is its own git repository, cloned into this workspace.

| Component | Repo | What it does | Plan |
|---|---|---|---|
| **Node** (Ycash 4.5 line) | `ycash-dd/` | `ycashd` with the vault upgrade, Yellowback and the bridge's Ycash side | [plan](docs/plans/yellowback-upgrade-plan.md) |
| **Node** (Ycash 6.20 line) | `ycash6/` + `librustzcash6/` | the same upgrade on `ycashd` 6.20.0 and the Rust library it builds against; releases are built from this line | [plan](docs/plans/yellowback-ycash6-plan.md) |
| **Desktop wallet** | `yecwallet-dd/` | YecWallet (Qt) with a Yellowback tab: mint, send, redeem and claim YED, join the attestor set; bundles the node | [plan](docs/plans/yellowback-upgrade-plan.md) |
| **Light-client server** | `lightwalletd-dd/` | lightwalletd with read-only Yellowback and vault calls for mobile wallets | [plan](docs/plans/yellowback-lightwalletd-plan.md) |
| **Mobile wallet** | `yew/` | YEW, an iOS/Android wallet for YEC (transparent and shielded) and YED | [plan](docs/plans/yellowback-wallet-plan.md), [shielded](docs/plans/yew-shielded-plan.md) |
| **Mining pool** | `yolo/` | a stratum solo-pool server for GPU miners (a Rust rewrite of yecdev/yolo) | [plan](docs/plans/role-pool-regtest-plan.md) |
| **Chain visualizer** | `chain-viz/` | a read-only live dashboard of blocks, the mempool, forks, vaults and Yellowback's health | [plan](docs/plans/chain-viz-plan.md) |
| **Agent payments** | `x402-ycash/` | x402 (HTTP 402) pay-per-request payments in YEC and YED for software agents | [plan](docs/plans/x402-agent-payments-plan.md) |
| **Parameter calibration** | `yb-calibration/` | derives and checks the constants each release builds into the node | `yb-calibration/docs/PLAN.md` |
| **Bridge contracts** | `wyec/` | the wYEC token and bridge contracts on Ethereum (drafts: not audited, not deployed) | [plan](docs/plans/yellowback-upgrade-plan.md) |
| **Bridge attestor** | `hawkeye/` | Hawkeye, the sidecar each wYEC bridge attestor runs: turns Ycash vault locks into wYEC mints and Ethereum burns into YEC releases, and challenges what it cannot match | [plan](hawkeye/docs/hawkeye-bridge-plan.md) |

### How they fit together

```
                         Ycash network
            ycashd with the vault upgrade (ycash-dd or ycash6)
       every rule for vaults, signer sets and YED is checked here
                                 ^
                                 | RPC
     +-------------+-------------+-------------+-------------+--------------+
     |             |             |             |             |              |
 YecWallet   lightwalletd      yolo        chain-viz    x402-ycash     bridge signers
 (desktop)   (light server)    (pool)      (read-only)  (payments)     (watch Ycash vaults
                 ^                                                      and Ethereum)
                 | gRPC                                                       |
                YEW (mobile)                                                  v
                                                                   wyec contracts on Ethereum
```

The node is the only place a rule lives: every upgraded node rejects a block that breaks one,
whoever mined it. Every other component reaches the node only through its public interfaces (the
node's RPCs, or lightwalletd's gRPC for the mobile wallet), so none of them needs to be trusted.
The pool mines ordinary blocks and adds a YEC/USD price quote to each; it enforces nothing. The
bridge's signers watch Ycash and Ethereum and act on both; Ycash itself never reads Ethereum.

---

## Getting started

**Prerequisites:** `git`, `make`, and `uv` or `python3` for the workspace's Python environment.
The C++, Qt, Go, Rust and Flutter toolchains are only needed to build a component. The clones pull
roughly 0.9 GB of git history, so the first run takes a few minutes.

```bash
git clone git@github.com:boyfromcave/yellowback.git yellowback-workspace
cd yellowback-workspace
make bootstrap                  # clone every repo at its pin, create .venv, then report status
code yellowback.code-workspace  # optional: VS Code, every repo as a root, ref/ read-only
```

`make bootstrap` clones every repository listed in [repos.yaml](repos.yaml): the read-only
references under `ref/` at their pinned commits, the forks and the application repos on their
working branch, and a Python venv in `.venv` for the test framework. It is safe to re-run: a repo
that already exists is only checked against the manifest, never changed. Options:
`SSH=1` (clone the writable repos over SSH so you can push), `NOVENV=1` (skip the venv),
`DRY=1` (print the commands, change nothing).

### Commands

```bash
make                # list targets and the current pins
make bootstrap      # recreate every clone and the venv from repos.yaml
make pull           # fast-forward every repo from its remote (never merges, rebases or discards)
make status         # fetch, then report every repo: in sync, behind, ahead, diverged; verifies ref/ pins
make status-short   # the same, without the per-file listing
make pins           # one line per repo, machine-readable
make diff           # each fork's changes against its pristine baseline
make log            # commits on each fork beyond its baseline
make spec           # regenerate docs/spec/yellowback-spec.md and its copies from the plans
make spec-check     # fail if a generated copy is stale
```

`make status` exits non-zero if a `ref/` repo has moved off its pin (every `file:line` citation in
[docs/mapping.md](docs/mapping.md) depends on the pins) or if a repo is not on the branch
`repos.yaml` records.

### Building

`make bootstrap` builds nothing. Each component documents its own build:

| Component | Build instructions |
|---|---|
| Node, Ycash 4.5 line | `ycash-dd/doc/yellowback.md`, section *Build and test baseline* (`./zcutil/build.sh`) |
| Node, Ycash 6.20 line | `ycash6/doc/yellowback.md`; releases: `ycash6/doc/yellowback-release.md` |
| Desktop wallet | `yecwallet-dd/docs/yellowback.md` (Qt 6 + CMake, bundles the node) |
| Light-client server | `lightwalletd-dd/docs/yellowback.md` (Go) |
| Mobile wallet | `yew/README.md` (Flutter + Rust) |
| Pool | `yolo/README.md` (`cargo build --release`) |
| Others | `chain-viz/README.md`, `x402-ycash/README.md`, `yb-calibration/README.md`, `wyec/README.md`, `hawkeye/README.md` |

### Try it: the one-laptop test network

The node repos carry a devnet: a regtest network of several nodes on one machine, with the vault
upgrade active, pools quoting prices and attestors signing them. On the `upgrade/vault` branch of
`ycash-dd`, after building `src/ycashd` and the attestor agent (`contrib/yellowback/attest`,
`cargo build --release`):

```bash
cd ycash-dd
source ../.venv/bin/activate
export PATH="$PWD/contrib/yellowback/devnet:$PATH"
yellowback-devnet up            # about 2 minutes: the network, funded, ready to mint
yellowback-devnet status        # what is running and the state of Yellowback
yellowback-devnet wallet        # open the desktop wallet on it
yellowback-devnet down
```

`yellowback-devnet up --role user|attestor|pool` leaves one seat for you to play while the rest of
the network runs on its own; `yellowback-devnet bridge …` runs the bridge's signers against it.
Everything else, including the end-to-end walk through every component, is in
`ycash-dd/contrib/yellowback/devnet/README.md`.

---

## For contributors

[AGENTS.md](AGENTS.md) holds the full working rules; read it before you change anything. In brief:

- **`ref/` is read-only.** Each reference is a pristine upstream checkout, pinned and made
  unwritable (`chmod -R a-w`). A `Permission denied` there means you are editing the wrong tree.
- **Code goes in the component's own repo.** Node code in `ycash-dd/` and `ycash6/` (the same
  change on both node lines, together), wallet code in `yecwallet-dd/`, light-server code in
  `lightwalletd-dd/`, and so on. Clients reach the node only through its RPCs; the mobile wallet
  only through lightwalletd.
- **Branches.** `upgrade/vault` is the line being built (the vault upgrade; the GitHub default
  branch of the node and client repos, and what `repos.yaml`, `make bootstrap` and `make status`
  use). `harden/yellowback` is the fallback line that needs no network upgrade; the workspace
  repo and `yb-calibration` stay on it, and `wyec` is on `main`. Each fork also has a `-legacy` branch (`ycash-legacy`,
  `ycash6-legacy`, …), the untouched upstream it is measured against with `make diff`; never
  commit to it.
- **Consensus code is not refactored.** Under `src/consensus/`, `src/script/`, `src/main.cpp`,
  `src/pow/` and `src/primitives/`, change only what the feature needs.
- **Naming.** Yellowback is the system, YED is the unit (`yed_*` RPCs, `src/yellowback/`).

### Porting from DigiByte: read this first

The node work started from DigiByte's DigiDollar as a reference, and DigiByte and Ycash are not
the same kind of codebase. DigiByte is a recent Bitcoin Core with SegWit, Taproot and BIP9;
Ycash is Zcash 4.5 (or 6.20) on a much older Bitcoin Core base, with shielded pools, ZIP-243
sighashes and height-gated network upgrades. DigiDollar's opcodes only work inside Taproot
scripts; copied into Ycash they compile and are rejected as bad opcodes. Before porting any
symbol, find its row in **[docs/mapping.md](docs/mapping.md)**, the file-by-file crosswalk with
`file:line` citations at both pins, and write down: *DigiByte does X in file Y using mechanism M;
the Ycash equivalent is Z, which lacks M; so the adaptation is W.*

### Where things are

```
yellowback-workspace/
├── ref/             read-only upstream references (pins below)
├── ycash-dd/        the node, Ycash 4.5 line              (fork of ref/ycash)
├── ycash6/          the node, Ycash 6.20 line             (fork of ref/ycash6)
├── librustzcash6/   the Rust library ycash6 builds on     (fork of ref/librustzcash6)
├── yecwallet-dd/    the desktop wallet                    (fork of ref/yecwallet)
├── lightwalletd-dd/ the light-client server               (fork of ref/lightwalletd)
├── yew/  yolo/  chain-viz/  x402-ycash/  yb-calibration/  wyec/  hawkeye/   application repos
├── docs/
│   ├── plans/       one plan per component; README.md indexes them
│   ├── spec/        the generated Yellowback spec and DigiByte's own design docs
│   ├── mapping.md   the DigiByte-to-Ycash crosswalk
│   ├── audits/      the security audit and its remediation checklist
│   └── reference/   the design proposals the plans were written from
├── repos.yaml       the manifest: every repo, its URL, branch and pin (plain clones, not submodules)
├── Makefile, scripts/   bootstrap, pull, status, spec generation, pin checks
├── wt/              git worktrees for parallel work (untracked)
└── AGENTS.md        the working rules (CLAUDE.md links to it)
```

### Documentation

| Read | For |
|---|---|
| [docs/plans/yellowback-upgrade-plan.md](docs/plans/yellowback-upgrade-plan.md) | the vault upgrade: requirements, design, byte-level spec, status |
| [docs/plans/README.md](docs/plans/README.md) | every component plan |
| [docs/mapping.md](docs/mapping.md) | how each mechanism maps from DigiByte to Ycash |
| `ycash-dd/doc/yellowback.md`, `doc/vault-rpc.md`, `doc/yellowback-rpc.md` | the node: how Yellowback works, the vault and `yed_*` RPCs (same paths in `ycash6/`) |
| [docs/innovation-acknowledgements.md](docs/innovation-acknowledgements.md) | what DigiDollar contributed and where Yellowback differs |

### Reference pins

Declared once in [repos.yaml](repos.yaml) and mirrored in AGENTS.md and docs/mapping.md;
re-pinning means updating all three.

| Repo | Pin | Commit |
|---|---|---|
| `ref/digibyte` | DigiByte, tag `v9.26.5` | `05b50e229d` |
| `ref/ycash` | Ycash, tag `v4.5.0` | `624c12814` |
| `ref/yecwallet` | YecWallet, tag `v4.5.0` | `1eb277d` |
| `ref/lightwalletd` | yodl/lightwalletd `master` (zcash/lightwalletd 0.4.6 + the Ycash changes; no tag) | `187a26765e` |
| `ref/ycash6` | miodragpop/ycash `dev-rebase-6.20.0`, ycashd 6.20.0 (no tag) | `040894344b` |
| `ref/librustzcash6` | miodragpop/librustzcash `ycashd-v6.20.0`, the rev `ref/ycash6/Cargo.toml` pins (no tag) | `ec525fae82` |
| `ref/yolo` | yecdev/yolo `main`, the Perl stratum pools (no tag) | `c9c155c6` |
| `ycash-dd` | fork of `ref/ycash`; baseline branch `ycash-legacy` | `624c12814` |
| `ycash6` | fork of `ref/ycash6`; baseline branch `ycash6-legacy` | `040894344b` |
| `librustzcash6` | fork of `ref/librustzcash6`; baseline branch `librustzcash6-legacy` | `ec525fae82` |
| `yecwallet-dd` | fork of `ref/yecwallet`; baseline branch `yecwallet-legacy` | `1eb277d` |
| `lightwalletd-dd` | fork of `ref/lightwalletd`; baseline branch `lightwalletd-legacy` | `187a26765e` |
| `yew`, `yolo`, `chain-viz`, `x402-ycash`, `yb-calibration`, `wyec`, `hawkeye` | application repos, no baseline | — |

---

## Design background

### Why a network upgrade

The design follows the Ycash Foundation's requirements for anything that locks YEC on behalf of
another system:

- **Ycash keeps working if Ethereum fails.** Vaulted YEC stays recoverable by its owner whatever
  happens off Ycash.
- **Ycash never reads Ethereum.** No Ycash rule depends on data from another chain.
- **Every rule is checked by every node.** Miners select transactions as they always have; they do
  not decide which rules apply.

The last requirement can only be met in consensus, which means a network upgrade with a new
consensus branch ID. The Foundation also asked for a general-purpose lock/unlock feature rather
than one built for a single application, so the upgrade adds vaults and signer sets, and Yellowback
adds only its own dollar rules on top. Ycash's past rule changes (Overwinter, Sapling, Ycash's own
fork) were all network upgrades of this kind.

### Smallest change first

Ycash is a small chain carrying real value, with a shielded pool whose soundness rests on
consensus code few people fully understand. So the aim is the smallest change that does the job,
not a faithful port of DigiDollar: within a network upgrade, prefer a script template over a new
opcode, an opcode over a new transaction field, per-vault state over global state, and the
general feature over application code. When a choice trades elegance for a smaller consensus
footprint, take the smaller footprint and write down what was given up. Nothing in either
application touches the shielded pool; YED lives on transparent outputs.

### Earlier designs (history)

Before the vault upgrade, Yellowback was designed to need no network upgrade at all: mining pools
enforced its rules, first with prices from the pools alone and then with bonded attestors added.
That design is kept on the `harden/yellowback` branch as the fallback line. Its plans and rationale,
for the record: [v2 plan](docs/plans/yellowback-v2-development-plan.md),
[v3 plan](docs/plans/yellowback-v3-development-plan.md),
[hardening plan](docs/plans/yellowback-evidence-based-hardening-plan.md) and
[why miners enforced it](docs/why-miner-enforced.md).
