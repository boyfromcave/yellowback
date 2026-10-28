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
| Post-quantum layer | On `upgrade/vault` in every repo, with the fee and attestor rules; `upgrade/quantum-vaults` is the branch it was built on, kept as history |
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

## How Yellowback compares with DigiDollar

DigiByte's DigiDollar proved that a self-custodial digital dollar can live on a proof-of-work UTXO
chain with no company and no custodian. It is Yellowback's starting point: the time-locked vault,
the term-graded collateral and the canonical tiers are DigiByte's ideas
([acknowledgements](docs/innovation-acknowledgements.md)). Yellowback takes that design further in
two directions. It **innovates**: a general-purpose vault system that carries bridges as well as a
dollar, post-quantum signatures from the first block, and a price feed anyone can join. And it
**hardens**: shorter terms, an exit at any time, open market discipline on underwater vaults, a
supply cap, and dollar-priced fees that pay the people who keep the price honest.

| Area | Ycash Yellowback | DigiByte DigiDollar (the starting point) |
|---|---|---|
| **Foundation** | A general-purpose vault system in the chain's rules; the dollar is one application on it, so new applications need no new consensus code | A dedicated set of dollar rules in the node |
| **Applications on the vaults** | Three: Yellowback (YED), the wYEC bridge to Ethereum, the nYEC bridge to NEAR | One: DigiDollar |
| **Quantum resistance** | Post-quantum from day one: vault owners sign with SLH-DSA, dollar holders and transfers with Falcon-512, so no vault or dollar is ever protected by a key a quantum computer could break | Classic elliptic-curve keys (secp256k1, Schnorr) |
| **Cross-chain** | Wrapped YEC on Ethereum and NEAR, backed 1:1 by YEC in vaults and attested by a bonded signer set; Ycash's rules never depend on another chain | Single chain |
| **Price feed** | Two independent sources that must agree, mining pools quoting in their blocks and an **open** set of bonded price attestors. Anyone can join by posting a bond (10,000–20,000 YEC); the largest bonds hold the seats, an attestor can leave at any time, and one that signs a false price loses its bond. If the two sources diverge, minting pauses | A set of 35 oracle keys configured in the node, 7 of which must sign each price; from Thaw Day (DigiByte v9.26.6, mainnet block 24,490,000) a mint whose price is 20 % or more from the median of the previous 1–6 hours' block prices is invalid |
| **Who enforces the rules** | Every full node | Every full node |
| **Terms** | 30 days to 1 year in three classes: deliberately short, because Ycash is risk-averse about locking collateral against a price nobody can forecast years ahead | 1 hour to 10 years in ten tiers (the 1-hour tier is labelled for testing and onboarding but is valid on mainnet) |
| **Collateral** | 300 % (30–90 days), 400 % (91–180 days), 500 % (181–365 days): the longer the lock, the more margin it carries | 1,000 % at 1 hour, then 500 % at 30 days down to 200 % at 10 years; raised by 25–100 % for new mints as system health falls |
| **Getting out early** | The owner can redeem at any time; before the term ends a fee of 5 %, 2.5 % or 1 % of the debt applies, so the shortest commitments pay the most to break them | Redemption when the term ends |
| **An underwater vault** | Open market discipline: anyone can claim a vault that falls below 125 % collateral, through a pending release the signer set can cancel if it is wrong, and the owner keeps the surplus | The protocol raises collateral for new mints, halts all new mints below 100 % system health, and requires a larger burn to redeem, while the position rides out its term; from Thaw Day health is measured against the open vaults' original principal |
| **Fees** | A protocol fee in dollars, tiered by size (1 % of the debt up to $1,000, 0.5 % to $10,000, 0.1 % above; $1 minimum) at mint and at redeem, shared between the block's miner and the attestors who signed the price; a network fee priced in dollars per kilobyte, capped | A miner fee in DGB (the wallet pays at least 0.1 DGB); no protocol fee |
| **Mint size** | $100 to $100,000 per vault | $100 to $100,000 per mint |
| **Supply** | Capped at 15 % of the circulating YEC supply at the attested price, with no single vault above 10 % of the cap | Not capped in the published design |
| **Review and testing** | Every consensus change reviewed twice, independently, on both node lines; the two lines must produce byte-identical results; an internal security audit and a Falcon consensus audit; no external audit yet | Published design documents, a test suite with fuzzing, and an isolated multi-node Thaw Day rehearsal per release candidate |
| **Wallets and tools** | Desktop wallet, mobile wallet, light-client server, hosted backend, agent payments (x402), explorer, mining pool, calibration tool | Qt desktop wallet and RPC |

The DigiDollar column describes DigiByte v9.26.7 (`d7265fb05e`), including the Thaw Day rules
DigiByte v9.26.6 schedules for mainnet block 24,490,000; the workspace's reference tree is still
pinned at v9.26.5 until that height passes and DigiByte publishes the packages ([mapping.md §23](docs/mapping.md)).

The collateral rows are the result of a deliberate review, against YEC's own price history, of the risk
profile of the collateral model Yellowback inherited from DigiDollar: what was found, what was changed and what it costs is written up, cited
to the node source, in [docs/spec/yellowback-risk-profile.md](docs/spec/yellowback-risk-profile.md).

## Contributing

Read [AGENTS.md](AGENTS.md) before changing anything. The short version:

- **`ref/` is read-only.** It holds pinned upstream checkouts for reading and grepping.
- **Code goes in the component's own repo**, and a node change is made on both node lines together.
- **`upgrade/vault` is the line being built.** `harden/yellowback` is the no-upgrade fallback.
- **Consensus code is never tidied or refactored.** Change only what the feature needs, with two
  independent reviews.
- **Porting from DigiByte?** Read [docs/mapping.md](docs/mapping.md) first: DigiByte and Ycash
  are very different codebases.
- **Security CI.** Every repository runs Semgrep, CodeQL, zizmor, gitleaks and OSV-Scanner; see
  [SECURITY-CI.md](SECURITY-CI.md) for the gates and how to accept a finding.
