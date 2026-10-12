# Ycash vaults and Yellowback

**A post-quantum vault system for Ycash, and the applications built on it.**

This project proposes a Ycash network upgrade that adds **vaults**: YEC locked under rules that
every Ycash node checks. A vault is released only when a bonded **signer set** approves it, and
only after a delay during which the release can be cancelled. If the signers ever go silent, the
vault's owner can still get the YEC back.

Vault owners sign with **post-quantum keys** from day one. The vault system is general-purpose: it
knows nothing about dollars or other chains. Applications add their own rules on top.

> **Status: in development.** Everything runs on regtest and on a one-laptop devnet. No activation
> height is set on mainnet or testnet, and the upgrade has not been adopted by the Ycash
> Foundation.

## What's inside

```text
  Yellowback          wYEC bridge         nYEC bridge
  (YED, a dollar)    (to Ethereum)       (to NEAR)
        │                  │                   │
  ┌─────┴──────────────────┴───────────────────┴─────┐
  │  Post-quantum vault system                       │
  │  lock / unlock, signer sets, owner recovery      │
  │  a network upgrade, checked by every node        │
  └──────────────────────────────────────────────────┘
```

### The vault system

- **Vaults** lock YEC under consensus rules: every node enforces them, not just miners.
- **Signer sets** are groups of bonded members who approve releases. A member who cheats loses
  their bond.
- **Owner recovery** means a vault's owner can always reclaim the YEC if its signer set goes
  silent.
- **Post-quantum signatures:** vault owners use SLH-DSA, and YED holders and transfers use
  Falcon-512, through one new opcode (`OP_CHECKPQSIG`). Plain YEC can use post-quantum addresses
  too (`sq…`); the shielded (Sapling) pool is unchanged.

### Applications

| Application | What it is | State |
|---|---|---|
| **Yellowback** | **Ycash Yellowback (YED)**: a dollar backed by YEC locked in vaults (`1 YED = $1`). Lock YEC to mint YED; burn the YED to get the YEC back. Undercollateralized vaults can be claimed by others. | In development |
| **wYEC bridge** | Wrapped YEC on Ethereum, backed 1:1 by YEC in vaults. Bridge attestors run Hawkeye. Ycash never reads Ethereum. | In development; contracts are drafts, not deployed |
| **nYEC bridge** | Wrapped YEC on NEAR, the same design as wYEC. Hawkeye attests for both bridges. | In development; NEAR contracts not deployed |

**Naming:** Yellowback is the system, YED is the unit. Say "250 YED", and "Yellowback is a dollar
on Ycash".

## Status

| | |
|---|---|
| Vault upgrade | Built on both node lines, running on regtest and devnet |
| Post-quantum layer | Built on the `upgrade/quantum-vaults` branches; it joins `upgrade/vault` at release |
| Mainnet / testnet | **No activation height set.** Mainnet activation is not scheduled |
| Reviews | Internal: a [security audit](docs/audits/yellowback-security-audit-20261001.md) and a [Falcon consensus audit](docs/audits/yellowback-falcon-consensus-audit-20261010.md). No external audit yet |

## Components

Each component is its own git repository, cloned side by side into this workspace.

| Component | Repo | What it does |
|---|---|---|
| Node, Ycash 6.20 line (**release line**) | [ycash6](https://github.com/boyfromcave/ycash6) | `ycashd` 6.20.0 with the vault upgrade and Yellowback; releases are built here |
| Rust library for the 6.20 node | [librustzcash6](https://github.com/boyfromcave/librustzcash6) | the patched librustzcash that `ycash6` builds against |
| Node, Ycash 4.5 line | [ycash-dd](https://github.com/boyfromcave/ycash-dd) | the same upgrade on `ycashd` 4.5.0, where changes land first |
| Desktop wallet | [yecwallet-dd](https://github.com/boyfromcave/yecwallet-dd) | YecWallet (Qt) with a Yellowback tab; bundles the node |
| Light-client server | [lightwalletd](https://github.com/boyfromcave/lightwalletd) | lightwalletd with read-only Yellowback and vault calls (local dir `lightwalletd-dd/`) |
| Mobile wallet | [yew](https://github.com/boyfromcave/yew) | YEW, an iOS/Android wallet for YEC and YED (a web wallet is in progress) |
| Mining pool | [yolo](https://github.com/boyfromcave/yolo) | a stratum solo-pool server for GPU miners, in Rust |
| Chain visualizer | [chain-viz](https://github.com/boyfromcave/chain-viz) | a read-only live dashboard of blocks, the mempool, vaults and Yellowback |
| Agent payments | [x402-ycash](https://github.com/boyfromcave/x402-ycash) | pay-per-request HTTP 402 payments in YEC and YED for software agents |
| Parameter calibration | [yb-calibration](https://github.com/boyfromcave/yb-calibration) | derives and checks the constants each release builds into the node |
| Bridge attestor | [hawkeye](https://github.com/boyfromcave/hawkeye) | the sidecar each bridge attestor runs: watches Ycash and the other chain, and challenges what it cannot match |
| Ethereum contracts | [wyec](https://github.com/boyfromcave/wyec) | the wYEC token and bridge contracts (drafts, not audited, not deployed) |
| Infrastructure | [ycash-infra](https://github.com/boyfromcave/ycash-infra) | Kubernetes deployment of the light-wallet backend: `ycashd` pool, lightwalletd, address index, gateway |

Every client reaches the node only through its public RPCs (the mobile and web wallets through
lightwalletd). The node is the only place a rule lives.

## Getting started

You need `git`, `make`, and `uv` or `python3`. Build toolchains (C++, Qt, Go, Rust, Flutter) are
only needed for the component you build.

```bash
git clone git@github.com:boyfromcave/yellowback.git yellowback-workspace
cd yellowback-workspace
make bootstrap   # clone every repo at its pin and create .venv (SSH=1 to push)
```

Day to day:

```bash
make status      # where every repo stands; fails if a ref/ pin has drifted
make pull        # fast-forward every repo (never merges, rebases or discards)
make diff        # each fork's changes against its upstream baseline
make             # list every target
```

`make bootstrap` builds nothing. Each component's README explains its own build.

### Try it on one laptop

The node repos ship a devnet: several regtest nodes with the upgrade active, pools quoting prices
and attestors signing them. See
[`ycash-dd/contrib/yellowback/devnet/README.md`](https://github.com/boyfromcave/ycash-dd/blob/upgrade/vault/contrib/yellowback/devnet/README.md).

## Learn more

| Read | For |
|---|---|
| [Upgrade plan](docs/plans/yellowback-upgrade-plan.md) | the vault upgrade: requirements, design, spec, status |
| [Quantum plan](docs/plans/yellowback-quantum-plan.md) and [spec](docs/plans/yellowback-quantum-spec.md) | the post-quantum layer |
| [Fees spec](docs/plans/yellowback-quantum-fees-spec.md) | how Yellowback and network fees are priced |
| [Hawkeye bridge plan](hawkeye/docs/hawkeye-bridge-plan.md) | the bridge attestor |
| [All plans](docs/plans/README.md) | one plan per component |
| [Mapping](docs/mapping.md) | how each mechanism maps from DigiByte's DigiDollar to Ycash |
| [Acknowledgements](docs/innovation-acknowledgements.md) | what DigiDollar contributed, and where Yellowback differs |

Earlier designs that needed no network upgrade are kept as history: see the
[hardening plan](docs/plans/yellowback-evidence-based-hardening-plan.md) and
[why miners enforced it](docs/why-miner-enforced.md).

## Contributing

Read [AGENTS.md](AGENTS.md) before changing anything. The short version:

- **`ref/` is read-only.** It holds pinned upstream checkouts for reading and grepping.
- **Code goes in the component's own repo**, and a node change is made on both node lines together.
- **`upgrade/vault` is the line being built.** `harden/yellowback` is the no-upgrade fallback.
- **Consensus code is never tidied or refactored.** Change only what the feature needs, with two
  independent reviews.
- **Porting from DigiByte?** Read [docs/mapping.md](docs/mapping.md) first: DigiByte and Ycash
  are very different codebases.
