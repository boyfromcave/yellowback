# yellowback-workspace

Bring a decentralized digital dollar to **Ycash** as **Ycash Yellowback (YED)**, using DigiByte's **DigiDollar** as the
reference implementation — with the smallest change to the Ycash codebase that meets the Ycash
Foundation's requirements.

The reference and target repos are pinned, side by side, so an agent or a human can read the
reference and the target at the same time without confusing one for the other.

**The preferred path is a network upgrade (owner, 2026-10-06).** On the branch `upgrade/vault` —
the GitHub default branch of `ycash-dd` and `ycash6` — Yellowback runs on **`UPGRADE_VAULT`**, a
coordinated network upgrade with consensus branch ID `0x6d5b7a31` ("Vault"). The upgrade adds the
Foundation's requested **application-agnostic lock/unlock primitive** (vaults, bonded signer sets,
relative timelocks, cancel, rate limit, slashing, dormancy recovery) and two applications on it:
the **wYEC bridge** (a script template, no application code in consensus) and **Yellowback**, the
one registered consensus rule module. YED's rules are checked by every upgraded full node from the
activation height, not by the pools. A node that does not upgrade stops following the chain at
that height. Plan: [docs/plans/yellowback-upgrade-plan.md](docs/plans/yellowback-upgrade-plan.md).
The earlier miner-enforced design (v2/v3, no network upgrade) is delivered history and lives on as
the **`harden/yellowback`** fallback line.

Yellowback is a token model, an index and a set of `yed_*` RPCs in the node, with the primitive's
`set_*` / `vault_*` RPCs beside them, on two node lines: `ycash-dd` (v4.5.0) and `ycash6` (ycashd
6.20.0, the release line). Around that node sit five compatible components, each its own
repository in this workspace, each reaching Yellowback only through the node's public interfaces
(a sixth, x402 agent payments, is listed after them, then the calibration tool that sets the release
constants and the wYEC bridge contracts). The table describes each component on `upgrade/vault`:

| Component | Repo | What it is | Talks to the node through | Plan |
|---|---|---|---|---|
| **Node, v4.5.0 line** | `ycash-dd/` (fork of Ycash `v4.5.0`) | `ycashd` with the `UPGRADE_VAULT` network upgrade: the lock/unlock primitive (BIP68 + `OP_CHECKSEQUENCEVERIFY`, `OP_CHECKSETSIG`, `OP_CHECKSETDORMANT`, signer sets, vault templates and intents, 21 `set_*`/`vault_*` RPCs), the wYEC bridge template, and Yellowback as the consensus rule module (`yed_*` RPCs, `rpcversion` 5, coinbase price tag, bonded attestor set) | — (it *is* the node) | [v3](docs/plans/yellowback-v3-development-plan.md) on [v2](docs/plans/yellowback-v2-development-plan.md) |
| **Node, 6.20.0 line** | `ycash6/` + `librustzcash6/` (forks of miodragpop's ycashd 6.20.0 rebase and the librustzcash it pins) | the same upgrade, primitive and module on ycashd 6.20.0 (Zcash 6.x lineage; golden vectors byte-identical across the lines); `librustzcash6` gains `BranchId::Vault` and is no longer zero-delta; **the release line** — releases are built from it | — (it *is* the node) | [ycash6 plan](docs/plans/yellowback-ycash6-plan.md) |
| **Full-node GUI wallet** | `yecwallet-dd/` (fork of YecWallet `v4.5.0`) | YecWallet with a Yellowback tab: mint, send, redeem, claim; pending claims with release and attestor cancel; attestor-set membership and heartbeat (`rpcversion` 5; the sweep and enforcement screens are gone); bundles `ycashd` and drives either node line | JSON-RPC (`yed_*`, `set_*`/`vault_*`) | v2 §4.8 / v3, wallet chunks |
| **Light-client server** | `lightwalletd-dd/` (fork of yodl/lightwalletd) | lightwalletd with a second gRPC service, `YellowbackStreamer`, each method a read-only proxy of a `yed_*` RPC (`rpcversion` 5), plus the primitive's read-only `GetVaultInfo`/`ListSets`/`GetSet`/`ListVaultOutputs`; reports the Vault branch ID in `GetChainInfo` | JSON-RPC (`yed_*`, read-only `set_*`/`vault_*`) | [lightwalletd plan](docs/plans/yellowback-lightwalletd-plan.md) |
| **Mobile wallet** | `yew/` (own repo) | YEW: iOS/Android, Flutter over a Rust core; YEC transparent and shielded (Sapling), YED transparent; mint/redeem/claim; its Rust signer builds the upgrade's vault and intent spends under branch ID `0x6d5b7a31` | lightwalletd's gRPC (`CompactTxStreamer` + `YellowbackStreamer`), never the node directly | [wallet plan](docs/plans/yellowback-wallet-plan.md), [shielded plan](docs/plans/yew-shielded-plan.md) |
| **Mining pool** | `yolo/` (own repo; Rust rewrite of yecdev/yolo) | stratum solo-pool server for GPU miners; carries the node's Yellowback coinbase price tag into every block it builds and mines across the vault activation with no code change (it carries no branch ID) | the stock mining RPCs (`getblocktemplate`, `submitblock`), never `yed_*` | [pool regtest plan](docs/plans/role-pool-regtest-plan.md) |
| **Chain visualizer** | `chain-viz/` (own repo) | real-time mempool, block-sequence, fork/orphan/reorg-risk and Yellowback-health dashboard for regtest, the devnet and mainnet, with vault-primitive panels (signer sets, vaults and intents, releases and cancels); shows miners and attestors what Yellowback pays them | ZMQ `hashblock`/`hashtx`, the stock read RPCs (`getblock`, `getrawmempool`, `getchaintips`, …) and the read-only `yed_*`, `set_*` and `vault_*` RPCs; never a write, never `getblocktemplate` (a CI grep enforces it) | [chain-viz plan](docs/plans/chain-viz-plan.md) |
| **x402 agent payments** | `x402-ycash/` (own repo) | x402 (HTTP-402) payments for AI agents in YEC and YED: pay-per-request, payment channels, private (shielded) payments; binding specs, the TypeScript SDK mechanism, the facilitator; signs for the next block's branch, so it pays across the vault activation | stock RPCs (`gettxout`, `sendrawtransaction`, `z_*` receipts) and the read-only `yed_*` RPCs; it asks no node change of its own on either line | [x402 plan](docs/plans/x402-agent-payments-plan.md) |
| **Parameter calibration** | `yb-calibration/` (own repo) | the calibration tool for the Yellowback parameters: derives and checks the constants baked into each Yellowback release | none at runtime; its output is the release constants, applied in `ycash-dd` and `ycash6` | — |
| **Bridge contracts (wYEC)** | `wyec/` (own repo) | Wrapped Ycash on Ethereum: the ERC-7802 wYEC token and the guardian-threshold bridge contract, the Ethereum side of the vault upgrade's bridge; the component the bridge's guardians and relayer run against (drafts, not audited, not deployed) | none: its signers watch the Ycash bridge vaults through the stock and `vault_*` read RPCs; Ycash consensus never reads Ethereum (R2) | [upgrade plan](docs/plans/yellowback-upgrade-plan.md) §4.3, P5 |

The node is the only place a rule lives, and on `upgrade/vault` it is a consensus rule: every
upgraded full node rejects a block that breaks it, whoever mined it. The wallet, the light server
and the mobile app show and spend YED; the pool mines ordinary blocks and supplies the coinbase
price quotes, but enforces nothing. (On the `harden/yellowback` fallback line the pools still
enforce, as in v2/v3.) Each fork, and the Rust pool that rewrites a Perl
one, has a read-only reference under `ref/` (the pristine upstream it forks or rewrites) so its
whole delta is one `git diff`; the other app repos are net new and have none.

**Status (2026-10-06).** The vault upgrade is **implemented and green on regtest and the
one-laptop devnet on both node lines** (all functional suites, the full devnet walk with every
client; the CI push tier green on both node lines and the clients). It is **not adopted by the Ycash Foundation, not audited, and not
activated on any public network**: `UPGRADE_VAULT` has no activation height on mainnet or testnet
and no YED attestor set is configured there (`NO_ACTIVATION_HEIGHT`; set only by the release that
passes the launch gates, upgrade plan P8). Regtest runs it with
`-nuparams=6d5b7a31:<h> -yellowbackattestorset=<setid>`. The launch gates G-1…G-10
([hardening plan](docs/plans/yellowback-evidence-based-hardening-plan.md) §7, as reshaped by
upgrade plan §7) and the parameter calibration are open; the Foundation has not written its
primitive spec, so the plan builds on stated assumptions (its §0). The fallback line's first
mainnet parameter set (`START_HEIGHT` 3,075,000, `ENFORCE_UNTIL_HEIGHT` 3,495,480) was **withdrawn**
by hardening F-5 and is unset on both lines. Testnet stays unset: on 2026-10-02 it was unreachable
(no fixed seeds, DNS seeders down). Releases come from `ycash6`
(`.github/workflows/yellowback-release.yml`, `doc/yellowback-release.md`): 6.21.x for the
`harden/yellowback` line, 6.22.x for the upgrade line (O-7); 6.21.0-rc1 is set in its
`configure.ac` but **nothing is tagged or released**.

```
yellowback-workspace/
├── ref/
│   ├── digibyte/    READ-ONLY  DigiByte  @ v9.26.5  — the DigiDollar reference (node + Qt GUI)
│   ├── ycash/       READ-ONLY  Ycash     @ v4.5.0   — the pristine node, for diffing against
│   ├── yecwallet/   READ-ONLY  YecWallet @ v4.5.0   — the pristine GUI wallet, for diffing against
│   ├── lightwalletd/ READ-ONLY yodl/lightwalletd @ master 187a26765e (0.4.6 + 4, no tag) — the pristine light-client server
│   ├── ycash6/      READ-ONLY  miodragpop/ycash @ dev-rebase-6.20.0 040894344b (no tag) — ycashd 6.20.0, the second node line
│   ├── librustzcash6/ READ-ONLY miodragpop/librustzcash @ ycashd-v6.20.0 ec525fae82 (no tag) — the patched librustzcash ycashd 6.20.0 pins
│   └── yolo/        READ-ONLY  yecdev/yolo @ main c9c155c6 (no tag) — the Perl stratum pools the Rust yolo rewrites
├── ycash-dd/        WORKING FORK of the node   — `feature/yellowback-price-attest` off `ycash-legacy`     (= v4.5.0)
├── yecwallet-dd/    WORKING FORK of the wallet — `feature/yellowback-price-attest` off `yecwallet-legacy` (= v4.5.0)
├── lightwalletd-dd/ WORKING FORK of lightwalletd — `feature/yellowback-price-attest` off `lightwalletd-legacy` (= 187a26765e)
├── ycash6/          WORKING FORK of the v6.20.0 node — `feature/yellowback` off `ycash6-legacy` (= 040894344b); the overlay on 6.20.0, the release line
├── librustzcash6/   WORKING FORK of the patched librustzcash — `feature/yellowback` off `librustzcash6-legacy` (= ec525fae82)
├── yew/             THE MOBILE WALLET (YEW), its own repo on `main` — plan docs/plans/yellowback-wallet-plan.md
├── yolo/            THE POOL SOFTWARE (yolo, Rust rewrite of yecdev/yolo), its own repo on `main` — plan docs/plans/role-pool-regtest-plan.md
├── chain-viz/       THE CHAIN VISUALIZER (chain-viz), its own repo on `main` — plan docs/plans/chain-viz-plan.md
├── x402-ycash/      x402 AGENT PAYMENTS (x402-ycash), its own repo on `main` — plan docs/plans/x402-agent-payments-plan.md
├── yb-calibration/  THE PARAMETER CALIBRATION TOOL (yb-calibration), its own repo on `main` — the constants baked into releases
├── wyec/            THE BRIDGE CONTRACTS (wYEC), its own repo on `main` — plan docs/plans/yellowback-upgrade-plan.md §4.3
├── docs/
│   ├── spec/        DigiDollar's own design docs + the generated Yellowback spec (`make spec`)
│   ├── plans/       THE DEVELOPMENT PLANS — the vault upgrade (preferred path) on the hardening plan, on
│   │                v3 (price attestation, delivered) on v2 (miner-enforced, delivered); ycash6 (6.20.0 line), lightwalletd, mobile wallet (YEW), YEW shielded, role-based regtest,
│   │                pool (yolo), chain-viz and x402 plans; ycash6/ holds the ycash6 plan's survey and upstream report;
│   │                README.md indexes them
│   ├── audits/      the 2026-10-01 ecosystem security audit and its remediation checklist
│   ├── reference/   the proposals the plans were written from (miner-enforced = v2, price attestation = v3)
│   ├── ideation/    README only — experimental ideas live on `ideation/*` branches, never on main
│   ├── mapping.md   the file-by-file, mechanism-by-mechanism crosswalk
│   ├── why-miner-enforced.md        the plain-language rationale for the v2 design
│   └── innovation-acknowledgements.md   what DigiDollar contributed, and where Yellowback diverges
├── repos.yaml       THE MANIFEST — every repo, its URL and its pin (no submodules)
├── Makefile         `make bootstrap` — recreate the workspace; `make status` — repo state + pin check
├── scripts/         bootstrap.sh, pull.sh, repos.sh (manifest reader), repo-status.sh, extract-spec.sh + extract_spec.py, check-ref-pins.sh
├── requirements.txt Python deps for the workspace venv (.venv, created by bootstrap)
├── wt/             git worktrees of the forks for parallel agents (untracked, gitignored)
├── yellowback.code-workspace   VS Code: parent + all eighteen clones as roots, ref/ read-only
└── AGENTS.md        working rules  (CLAUDE.md symlinks to it)
```

All `ref/` checkouts are `chmod -R a-w`, so "don't edit the reference" is enforced by the
filesystem, not just documented. All work happens in the five forks (`ycash-dd/`,
`yecwallet-dd/`, `lightwalletd-dd/`, `ycash6/`, `librustzcash6/`) and the six app repos (`yew/`,
`yolo/`, `chain-viz/`, `x402-ycash/`, `yb-calibration/`, `wyec/`). The `yed_*` RPC surface (on `upgrade/vault`, together with the primitive's `set_*`/`vault_*` RPCs) is the only interface between the node and its wallet and light-server clients;
lightwalletd's gRPC is the only interface the mobile wallet has; the stock mining RPCs are the
only interface the pool has.

---

## What Yellowback is, in one page

**On `upgrade/vault` (the preferred path): one agnostic primitive, two applications, one rule
module** ([upgrade plan](docs/plans/yellowback-upgrade-plan.md) §1, §3–§6, §15).

- **The primitive knows no application.** `UPGRADE_VAULT` (branch ID `0x6d5b7a31`) adds BIP68
  sequence locks and `OP_CHECKSEQUENCEVERIFY` (0xb2), `OP_CHECKSETSIG` (0xc0) and
  `OP_CHECKSETDORMANT` (0xc1); **signer sets** as a consensus object (bonds, threshold, cancel,
  rate limit, slashing on equivocation, liveness and dormancy); **vault templates** (V) and
  **intents** (I) with unlock, cancel and owner-recovery branches; set acts carried in a `YV`
  OP_RETURN; state in a vault database with undo; 21 `set_*`/`vault_*` RPCs
  (`doc/vault-rpc.md` in either node fork).
- **Application 1, the wYEC bridge**, is a template on the primitive and nothing else in
  consensus: lock → intent → release, cancel or owner recovery, with both signer shapes (the
  Foundation's single relayer plus challengers, and the owner's guardian threshold). The Ethereum
  side is `wyec/` (drafts, not audited, not deployed).
- **Application 2, Yellowback**, is the one registered **rule module** (`YED\0` tag). YED's block
  verdict is consensus from the upgrade height on every upgraded node. The YED vault is the
  primitive's V template: the owner redeems with the owner branch; a claim moves the collateral
  into a claimant intent that the YED attestor set may cancel during `CLAIM_DELAY`, and anyone
  releases after it; if the attestor set goes dormant the owner recovers the collateral without a
  burn. Attestors register by joining the YED attestor set (`SET_JOIN`, heartbeats). Price
  attestation (v3, below) and the hardening launch parameters carry over: class A only, minting
  requires ARMED, $2,500 maximum mint, 15 bps fee with a 50 % attestor share, 300 % halt and
  600 % recap floor.
- **Retired on this line:** pool signalling, lock-in, the work valve, the kill switch, the sunset,
  abandonment, VOID verdicts, `yed_sweep`, the anyone-can-spend claim branch, and the
  `-experimentalfeatures -yellowback` gate. YED is on wherever `UPGRADE_VAULT` and the YED
  attestor set are configured; a node whose Yellowback index is unhealthy stops, because
  consensus needs it.
- **Why a module at all.** A dollar's safety rule is "the spender burned this vault's debt at an
  attested price" — a statement about ledger state, not signatures. An agnostic primitive cannot
  check it, and a bonded set signing it would make the price oracle a custodian. The module is the
  smallest thing that gives YED full-node verification (plan §1, U-4). If the Foundation ships the
  primitive and declines the module, YED falls back to collateral in consensus and dollar rules in
  the overlay (plan §5.4).

### History: the miner-enforced design (v2/v3), now the `harden/yellowback` fallback

**Before the upgrade, Yellowback was v3: price attestation on top of v2's miner-enforced
overlay.** It was delivered, calibrated and hardened, and it is what the `harden/yellowback` line
still runs (no network upgrade). v3 is a delta, so the base it amends comes first; the price
attestation it adds carries over to the upgrade line unchanged.

**The base (v2) is a miner-enforced overlay.** A minter locks YEC in a time-locked P2SH vault they
control alone and receives YED, a dollar-denominated token on ordinary transparent outputs; burning
the YED unlocks the YEC. The one rule Ycash script cannot express — *release this collateral only
if the matching YED is burned* — is enforced by **mining pools**, because on a proof-of-work chain
the miner is the only party who can refuse a transaction without a consensus change.

- **Who enforces.** Any pool that runs the module. Before activation it filters its own block
  templates (policy only, which cannot fork anything). After activation — ≥ 75 % of a 2,016-block
  window signalling, then a 2,016-block delay — it also rejects a block containing a vault spend
  without the matching burn. That is a soft fork in the P2SH/CLTV sense: every block an enforcing
  pool mines is valid to a stock node, and a stock node never rejects anything it accepts today.
- **What can invalidate a block.** Exactly one class of transaction: a spend of an ACTIVE vault
  output whose burn or enforcement fee is wrong. Invalid mints and transfers never invalidate a
  block, and a coinbase tag never does.
- **Where the price comes from.** A 36-byte quote tag in the coinbase scriptSig, carried by the
  never-assigned `COINBASE_FLAGS` global, so the internal miner, regtest `generate` and
  `getblocktemplate` all emit it with no new plumbing. Prices are rolling medians of 96 / 576 /
  2,016 quote-tagged blocks, fail-closed below a minimum fill. No oracle roster, no quorum, no
  signing round.
- **Who gets paid.** Every mint, redemption and claim pays an enforcement fee of
  `max(0.5 YEC, 0.25 % of collateral)` to a pool that quoted recently — earned in proportion to
  blocks quoted, so a small pool that quotes every block earns its share. Permissionless: there is
  no slot to be granted.
- **What nobody can do.** No operator, committee or key other than the minter's can move
  collateral before the claim height; after it, only a burn of the vault's debt can. Nothing any
  pool does can create YED, move a user's YED, or take collateral early.

**No federation.** A 5-of-9 federation prototype was built, worked on regtest, and was **retired on
2026-09-10** because it put a counterparty on redemption. It survives as
tag `archive/v1-federation` (see `docs/plans/archived/`) and as the `feature/digidollar` branch in both forks — a record, never an
input, never built on.

**Yellowback v3 adds a second price population.** In v2 every price comes from one place — the
YEC/USD quotes mining pools publish in their coinbases — so the trust statement rests entirely on
honest-majority hashpower. v3 adds **bonded attestors**: anyone who posts a long time-locked bond
may sign prices off-chain, and a minter or claimant carries four to six of those signatures into
the transaction that needs them, in the scriptSig of a small P2SH *carrier* input that every stock
node relays today. Enforcing nodes combine the bond-weighted quantile with the pool medians by
`min` for mints and `max` for claims, so moving the price in the direction that pays now requires a
hashpower majority **and** a bond-weighted majority of the selected attestors at the same time.
Attestors pay nothing beyond the bond — no periodic transactions, no domain, no open port — and the
party who needs an attested price pays for it. No new line in any consensus, mining or policy file
of the node beyond v2's hooks, with one exception: the owner-approved security-audit fixes A-1 and
A-7 (2026-10-01) adjusted two of those hooks (`src/main.cpp` +1 line net, `src/rpc/mining.cpp`
+2/−1). Design:
[docs/reference/yellowback-price-attestation.md](docs/reference/yellowback-price-attestation.md).
Plan and status: [docs/plans/yellowback-v3-development-plan.md](docs/plans/yellowback-v3-development-plan.md)
(see its status table).

- **Release continuity (v3 revision 4, W18–W21, 2026-10-02; fallback line only — the upgrade
  retires the sunset, renewal and abandonment).** A *renewal* release — same values,
  only a later `ENFORCE_UNTIL_HEIGHT` — is not a parameter change and may ship any time before the
  sunset; a wrong value is replaced by "freeze, then fix" (pools switch enforcement off for a full
  window, then a corrected set starts); above the supply cap a mint is still accepted when the
  ratio it locks after the volatility multiplier is at least `RECAP_RATIO_BPS` (500 %); and a
  halted module waits `ABANDON_BLOCKS` = `GRACE` = 34,560 blocks (≈ 30 days) before abandonment.

Rationale for the v2/v3 design: [docs/why-miner-enforced.md](docs/why-miner-enforced.md); the
decision that superseded it: [upgrade plan](docs/plans/yellowback-upgrade-plan.md) §1, §10.
Normative protocol of the miner-enforced design:
[docs/spec/yellowback-spec.md](docs/spec/yellowback-spec.md) (generated from the plans' §3 by
`make spec`); for the upgrade line, the byte-level implementation specification is upgrade plan
§15. Lineage and divergence from DigiDollar:
[docs/innovation-acknowledgements.md](docs/innovation-acknowledgements.md).

---

## The prime directive: minimal changes to Ycash

**This is the constraint that decides the architecture, not a nice-to-have.**

The Ycash team is risk-averse, and correctly so — it is a small chain carrying real value with a
shielded pool whose soundness depends on consensus code that very few people fully understand.
Every line changed under `src/consensus/`, `src/script/`, or `src/main.cpp` is a line that has to
be reviewed by people with limited time, and a line that can split the chain or, worse, silently
break the value-balance invariants that keep the shielded pool sound.

So the design goal is **not** "port DigiDollar faithfully." It is:

> Find the smallest change to Ycash that yields a safe, decentralized dollar — and be explicit
> about what that minimality costs.

A smaller diff is a smaller ask, a smaller review burden, and a smaller blast radius. When a
design choice trades protocol elegance for a smaller consensus footprint, **take the smaller
footprint** and write down what was given up.

That principle survives the move to a network upgrade. The upgrade plan (§9) restates it for the
higher tier: within a network upgrade, prefer a script template over an opcode, an opcode over a
transaction field, per-vault state over global state, and the primitive over the module — and
record what was given up. (The matching amendment to [AGENTS.md](AGENTS.md) is an open owner
decision; until it is applied, AGENTS.md still states the Tier 0-first rule.)

### The change-budget ladder

Prefer the lowest tier that can work. Every step down the list costs review effort and risk.

| Tier | What it touches | Deploy | Precedent in Ycash |
|---|---|---|---|
| **0** | Wallet + RPC only. New script templates built from **existing** opcodes (P2SH, `OP_CHECKMULTISIG`, `OP_CHECKLOCKTIMEVERIFY`, `OP_HASH160`, `OP_IF`). Read-only observer hooks in `main.cpp`. | No fork. Off by default behind an experimental flag. | ✅ **Atomic swaps, shipped in v4.5.0** — see below |
| **1** | Tier 0 + relay/mempool policy (`src/policy/`), non-consensus | No fork (policy only) | standardness rules |
| **2** | New opcode semantics on unused `OP_NOP` slots | Soft fork; old nodes still accept | never done in Ycash |
| **3** | New network upgrade: a new `UPGRADE_*` entry and branch ID (and, if needed, a new tx version / version group) | **Hard fork**, coordinated | Overwinter, Sapling, Ycash, Heartwood, Canopy; **`UPGRADE_VAULT`** (proposed, `upgrade/vault`) |

**Where Yellowback lands now: Tier 3, a coordinated network upgrade.** `UPGRADE_VAULT` (branch ID
`0x6d5b7a31`) is a hard fork: every node operator, exchange and pool must upgrade before the
activation height, and a stock v4.5.0 or 6.20.0 node cannot follow past it. A cheaper tier does
not do, for a reason outside this project's control: the Ycash Foundation's requirements for a
bridge, which the owner confirmed as firm and as covering Yellowback's collateral too (upgrade plan
§0, O-1) — **R1**, Ycash keeps working and vaulted YEC stays recoverable if Ethereum fails; **R2**,
Ycash consensus never reads Ethereum; **R3**, *miners enforce, miners do not vote*: every rule is a
consensus rule that every full node checks, and miners keep only ordinary transaction selection.
R3 rules out the miner-enforced design by definition and, in the plan's words, forces "a network
upgrade: new branch ID, rules in block validity" (plan §2); "no cheaper tier meets R3" (§8).
Ycash has also never shipped a soft fork: its rule changes have all been height-gated network
upgrades. The Foundation also prefers a generic lock/unlock facility over an
application-specific one, which is why the consensus change is a primitive and YED is a module on
it. Size, measured as an estimate rather than a budget (plan §12): the primitive ≈ 1,500 lines per
node line; the module is the delivered `src/yellowback/` minus about a third plus the intent flow.
The four-part check for the mechanism is plan §8; the crosswalk rows are
[docs/mapping.md](docs/mapping.md) §22.

**What the upgrade gives up** (plan §10): the soft-fork tier and everything built for it,
delivered and calibrated, then retired; a trustless bridge release path (R2 forbids it — wYEC is a
federated bridge and says so); renewal releases as the parameter mechanism; `librustzcash6` as a
zero-delta fork; the frozen-file invariant as a one-command proof of consensus safety, replaced by
a two-reviewer consensus review gate; and full agnosticism — the primitive stays agnostic, the
node carries one registered module. What it buys: no pool that enforces, no pause, no
abandonment; YED created only when a hashpower majority and a bonded attestor majority agree on
the price; collateral recoverable by its owner if the attestor or bridge set goes silent; nothing
in either application touches the shielded pool.

**History: where Yellowback v2 landed (the `harden/yellowback` fallback line): Tier 1 plus one
block-validity hook — and no opcode.** Miner
enforcement does not sit on a rung of this ladder, because it buys a soft fork's effect without a
soft fork's code. Tier 2 is skipped entirely: there is no new opcode, no `OP_NOP` repurposing, no
branch ID, no network upgrade, and no release the Ycash team must ship. The whole enforcement rule
is a pure function of `(block, state, params)` called from the `ConnectBlock` window of the patched
node, inert without `-yellowback`, and switched off with one flag. Measured against `ycash-legacy`
(plan header, 2026-09-11): `src/main.cpp` **11** changed lines, `src/miner.cpp` **12**,
`src/rpc/mining.cpp` **7**, and `src/consensus/`, `src/script/`, `src/primitives/`, `src/pow/`,
`src/wallet/wallet.{h,cpp}` at **zero**. (Re-measured 2026-10-04, after v3 and the owner-approved
security-audit fixes A-1 and A-7: `src/main.cpp` +12/−0, `src/miner.cpp` +10/−2,
`src/rpc/mining.cpp` +9/−1; the rest still zero.) Vaults are ordinary P2SH with
`CHECKLOCKTIMEVERIFY` that Ycash already validates in every block; YED tokens are ordinary transparent P2PKH outputs with one
80-byte `OP_RETURN` payload that Ycash already relays; YED addresses are plain Base58Check P2PKH
with new version bytes and no `chainparams.cpp` edit.

### Tier 0 is not hypothetical — Ycash already did it

Ycash v4.5.0 ships **atomic swaps** (`src/script/atomicswap.h`), an HTLC built from nothing but
opcodes that already existed. The whole feature was **one commit, `ccddd22e4`, 4,066 lines across
17 files**, and it changed:

- `src/script/interpreter.cpp` — **nothing**
- `src/script/script.h` — **nothing**
- `src/consensus/` — **nothing**
- `src/chainparams.cpp` — **nothing**
- `src/main.cpp` — **17 lines**, and every one of them is a passive observer:
  `MonitorAtomicSwapTransaction(tx)` in `AcceptToMemoryPool` and `ConnectBlock`,
  `CheckAtomicSwapExpirations(...)` in `UpdateTip`, `HandleAtomicSwapDisconnect(tx)` in
  `DisconnectTip`. **No validation rule changed. No code path can reject a block.**

Everything else was script construction, RPC, and wallet — and the whole thing is off unless you
run with `-experimentalfeatures -atomicswaps`.

**That is the shape to aim for.** Study `ccddd22e4` before designing anything.

### What the miner-enforced minimality cost (history; still true of the `harden/yellowback` line)

This subsection describes the v2/v3 design. The vault upgrade removes these costs by putting the
rule in consensus, at the price listed above under *What the upgrade gives up*.

DigiDollar enforces collateral ratios and supply in *consensus*: the chain itself refuses an
invalid mint, which DigiByte could add cheaply because Tapscript's `OP_SUCCESSx` gave it a
soft-fork mechanism. Ycash has no such hook, so the miner-enforced design's guarantees rest on
hashpower instead, and that is a different and weaker assumption than consensus enforcement.
Stated plainly:

- **A vault is safe only while a majority of hashpower enforces the burn rule.** That is the same
  honest-majority assumption the chain already makes for double-spends, but it is an assumption —
  which is why minting is impossible before activation, halts when signalling falls below 60 %, and
  block rejection itself suspends below 50 % and resumes at 60 %.
- **The claim path is anyone-can-spend at the script level.** Its safety is the enforcement rule,
  not the script.
- **A bug in the hook could fork enforcing pools off the chain.** Bounded by: the hook rejects only
  ACTIVE-vault spends, fails open on a storage failure, never bans a peer, has a kill switch that
  also un-rejects blocks, trips a work valve that re-joins a heavier rejected chain, never rejects
  a block the network has already built six blocks on, and sunsets at a per-release height.
- **The feed's availability rests on pool participation**, and the design degrades to "no new
  mints" — never to "a minter cannot redeem".
- **YED stays on transparent outputs.** Miners cannot enforce what they cannot read, so shielded
  YED is deferred research. (On the upgrade line too, YED stays transparent and nothing in either
  application touches the shielded pool.)

Do not paper over this. The plan states which properties are consensus-enforced, which are enforced
by every Yellowback-aware node, and which are enforced by the mining pools that run the module —
the trust statement in
[docs/plans/yellowback-v2-development-plan.md](docs/plans/yellowback-v2-development-plan.md) §8.1,
which must be published verbatim with v2. The full trade-off table, each row with the plan citation
that bounds it, is [docs/why-miner-enforced.md](docs/why-miner-enforced.md) §5; that document also
explains why miner enforcement was chosen over a federation (retired; tag `archive/v1-federation`, see `docs/plans/archived/`) and
over a network upgrade. **Consensus enforcement was always the destination** — the validator was
written so a later Ycash network upgrade would change who runs the check, not what it checks
(v2 plan §9). The vault upgrade is that step: its YED module is the delivered rule set with the
enforcement machinery removed (upgrade plan §1, §6), and its trust statement (upgrade plan §10)
replaces the v2 one on the upgrade line.

---

## Why this is not a port

DigiByte and Ycash are not the same kind of codebase, and DigiDollar leans on exactly the features
Ycash lacks. Four walls, all verified against the pinned source:

**1. Taproot / Tapscript — DigiDollar's entire opcode layer depends on it.**
DigiDollar's opcodes (`OP_DIGIDOLLAR`, `OP_DDVERIFY`, `OP_CHECKPRICE`, `OP_CHECKCOLLATERAL`,
`OP_ORACLE`, bytes 0xbb–0xbf) sit in BIP342 `OP_SUCCESSx` slots, and every case in `EvalScript` is
guarded by `if (sigversion != SigVersion::TAPSCRIPT) return SCRIPT_ERR_BAD_OPCODE`. That guard is
the whole soft-fork story: old Taproot nodes see the bytes inside a tapleaf and succeed.
**Ycash has no SegWit and no Taproot.** Its `SigVersion` enum is a false friend — same name, but
it names a *sighash algorithm* (`SPROUT`/`OVERWINTER`/`SAPLING`), not a script context. Bytes
0xbb–0xbf hit `default: return set_error(serror, SCRIPT_ERR_BAD_OPCODE)`. A verbatim transplant
compiles and is consensus-dead.

**2. Shielded pools — Ycash has value DigiByte's model cannot see.**
Sprout JoinSplits and Sapling spends/outputs, plus a `valueBalance` moving value between
transparent and shielded. DigiDollar assumes every DigiDollar output is transparent and auditable,
which is how it computes supply and collateral ratios at all. **Orchard was never implemented** —
`UPGRADE_NU5` exists in the enum but is `NO_ACTIVATION_HEIGHT` on every network, and there are
zero occurrences of `orchard` in `src/`. The safe default is that YED outputs must be
transparent; shielded YED makes global supply unverifiable and is a research project, not a
port.

**3. Sighash and transaction format.**
DigiByte signs with BIP341/342, committing to a tapleaf and the full spent-output set. Ycash signs
with ZIP-243, committing to a `consensusBranchId` and the shielded bundle hashes. DigiDollar also
bit-packs its transaction type and flags into `nVersion` — a field Ycash pins to exactly `4`, with
bit 31 reserved for `fOverwintered` and a mandatory `nVersionGroupId` alongside it.

**4. Codebase generation.**
DigiByte v9.26.5 is Bitcoin Core ~v26/28 (`src/validation.cpp`, `src/kernel/`, `src/node/`,
`src/index/`, per-output `Coin`, BIP9 deployments). Ycash v4.5.0 is Zcash 4.5 on a Bitcoin Core
~0.11/0.12 base (monolithic `src/main.cpp`, per-transaction `CCoins`, height-gated network
upgrades, no Qt GUI). Almost no file path maps directly.

Full detail, with `file:line` citations at both pins:
**[docs/mapping.md](docs/mapping.md)**. What DigiDollar *did* contribute to Yellowback, credited
specifically, and where the two designs part company on principle:
**[docs/innovation-acknowledgements.md](docs/innovation-acknowledgements.md)**.

---

## Start here

1. **[AGENTS.md](AGENTS.md)** — the working rules. Short. Read it first.
2. **[docs/mapping.md](docs/mapping.md)** — the crosswalk. Read the relevant row *before* porting
   any symbol. It exists to stop one specific failure: grepping `ref/digibyte` for a DigiDollar
   symbol and transplanting it into a Ycash file with incompatible semantics.
3. **[docs/plans/yellowback-upgrade-plan.md](docs/plans/yellowback-upgrade-plan.md)** — **the
   preferred path**: the vault network upgrade, its decision (§1), the Foundation's requirements
   (§0, §2), the primitive (§3), the bridge (§4), YED as a module (§5), what it retires (§6), the
   tier and trust statement (§10), the byte-level spec (§15), and the authoritative execution
   status block at the top. It builds on the
   [hardening plan](docs/plans/yellowback-evidence-based-hardening-plan.md), whose gates still
   come first, and on v3 below, which still governs the price attestation it keeps.
4. **[docs/why-miner-enforced.md](docs/why-miner-enforced.md)** — history: the plain-language
   rationale for v2: why the one rule Ycash script cannot express (burn-before-release) is handed
   to mining pools rather than to a federation or a network upgrade, what that buys
   (self-custody, no committee on redemption, a hashpower-priced feed) and the trade-offs it
   accepts, each with where the plan bounds it. The upgrade plan §1 and §10 say why that choice
   was superseded.
5. **[docs/plans/yellowback-v3-development-plan.md](docs/plans/yellowback-v3-development-plan.md)** —
   the delivered price-attestation plan, the design the `harden/yellowback` line runs and the
   upgrade amends: its status table, decision record W1–W21, the normative
   protocol delta (§3), the concurrent one-machine test workflow (§6.0) and the phased work plan.
   It is a **delta on v2**, so keep
   **[docs/plans/yellowback-v2-development-plan.md](docs/plans/yellowback-v2-development-plan.md)**
   beside it — the delivered plan, whose §3 still governs everything v3 does not restate. Its
   branch, `feature/yellowback-sf`, is superseded by v3 and kept only as a record — it is **not** a
   comparison base: line budgets measure against `ycash-legacy`, and the frozen-file zero-delta
   check against the tag `yellowback-v3-baseline` in `ycash-dd` (owner, 2026-10-01; re-tagged at
   `ff7f45947` on 2026-10-02). `docs/plans/archived/` points at the retired
   federation design (tag `archive/v1-federation`, history only); `docs/ideation/` lists the
   `ideation/*` branches that hold inactive experimental ideas.
   **[docs/reference/yellowback-price-attestation.md](docs/reference/yellowback-price-attestation.md)**
   is the proposal v3 implements, and its audit companion records what three review passes changed.
6. **[docs/innovation-acknowledgements.md](docs/innovation-acknowledgements.md)** — what the
   DigiByte team contributed and what Yellowback owes them, alongside the specific points where
   Ycash's principles (decentralization, self-sovereignty, risk aversion) sent the design
   elsewhere. Read it before describing Yellowback to anyone outside the project.
7. **`ref/ycash` commit `ccddd22e4`** — the atomic-swap feature, as a worked example of what a
   well-scoped Ycash feature looks like.
8. **The component plans**, one per repo around the node:
   [ycash6](docs/plans/yellowback-ycash6-plan.md) (the 6.20.0 node line, the release line),
   [lightwalletd](docs/plans/yellowback-lightwalletd-plan.md) (the light-client server),
   [YEW](docs/plans/yellowback-wallet-plan.md) (the mobile wallet) and
   [YEW shielded](docs/plans/yew-shielded-plan.md) (Sapling in YEW),
   [role-based regtest](docs/plans/role-based-regtest-plan.md) (walking the devnet as a user, an
   attestor and a pool), [pool regtest](docs/plans/role-pool-regtest-plan.md) (yolo, the
   Rust stratum pool, and the devnet's real-pool seat), [chain-viz](docs/plans/chain-viz-plan.md)
   (the visualizer) and [x402](docs/plans/x402-agent-payments-plan.md) (agent payments);
   `yb-calibration` keeps its plan in its own repo (`yb-calibration/docs/PLAN.md`). Each has its
   own status table. [docs/plans/README.md](docs/plans/README.md) indexes them all.

**Where the work stands:** see the execution-status table at the top of each plan, kept current by
the coordinator. In one line: v2 and v3 are delivered and, with the hardening plan's node chunks,
form the `harden/yellowback` fallback line; the vault upgrade (`upgrade/vault`) is the preferred
path, implemented through P4 on both node lines with every client updated (P6) and green on
regtest and the devnet; the Foundation's spec, the external bridge-contract audit (P5), the launch
gates (P7) and the release that sets activation heights (P8) are open.

Before porting anything, answer four questions in writing:

> DigiByte does **X** in file **Y** using mechanism **M**.
> The Ycash equivalent is **Z**, which lacks **M**.
> So the adaptation is **W**.

If **M** turns out to be Taproot, SegWit, BIP9, `nVersion` bit-packing, the `Coin` model, or
MuSig2, stop — `docs/mapping.md` already has a row for it. And if **W** requires a consensus
change, say which tier it lands on and why a lower tier will not do.

---

## Getting started

The workspace repo tracks only the documents, the manifest and the scripts. The eighteen nested clones
under `ref/`, `ycash-dd/`, `yecwallet-dd/`, `lightwalletd-dd/`, `ycash6/`, `librustzcash6/`, `yew/`,
`yolo/`, `chain-viz/`, `x402-ycash/`, `yb-calibration/` and `wyec/` are plain git repositories (not submodules),
gitignored here and recreated from [repos.yaml](repos.yaml) by `make bootstrap`.

**Prerequisites:** `git`, `make`, and either `uv` or `python3` (3.10+) for the workspace venv.
Nothing else is needed to bootstrap; the C++/Qt toolchains are only needed to *build*, see below.
The eighteen clones pull roughly 0.9 GB of git history (measured 2026-10-04; DigiByte is the
largest, under a third of it), so allow a few minutes on the first run.

```bash
git clone git@github.com:boyfromcave/yellowback.git yellowback-workspace
cd yellowback-workspace
make bootstrap            # clone + pin + venv, then `make status` to confirm
code yellowback.code-workspace
```

What `make bootstrap` does, in order:

1. `ref/digibyte`, `ref/ycash`, `ref/yecwallet`, `ref/lightwalletd`, `ref/ycash6`, `ref/librustzcash6`,
   `ref/yolo` — cloned over https, checked out detached at the pinned tag (or, for `ref/lightwalletd`,
   `ref/ycash6`, `ref/librustzcash6` and `ref/yolo`, whose upstreams publish no tags, at the pinned
   commit), verified against the pinned commit (it aborts if a tag has moved upstream), then
   `chmod -R a-w` so the reference cannot be edited by accident (`.git/` stays writable).
2. `ycash-dd`, `yecwallet-dd`, `lightwalletd-dd` — cloned on `feature/yellowback-price-attest`; the
   pristine baseline branch (`ycash-legacy` / `yecwallet-legacy` / `lightwalletd-legacy`) is created
   tracking `origin`, verified to equal the matching `ref/` pin, and the upstream repo (Ycash
   Foundation, or `yodl` for lightwalletd) is added as remote `upstream` (not fetched).
   `ycash6` and `librustzcash6` — the same, on `feature/yellowback` with the baselines
   `ycash6-legacy` / `librustzcash6-legacy` and miodragpop's repos as `upstream`.
   `yew`, `yolo`, `chain-viz`, `x402-ycash`, `yb-calibration` and `wyec` — the app repos — are cloned on
   `main`; they have no baseline branch and no `upstream` remote (`yolo`'s Perl ancestor is `ref/yolo`).
   *2026-10-05:* every writable repo is on `harden/yellowback` (the hardening plan's branch, cut from
   the branch of record named above); `repos.yaml` records it, so `make status` expects it.
   *2026-10-06:* the **preferred branch of the node lines is `upgrade/vault`** (the vault network
   upgrade; the GitHub default branch of `ycash-dd` and `ycash6`), and `librustzcash6` and every
   client except `yb-calibration` and `wyec` carry an `upgrade/vault` branch to match.
   `harden/yellowback` stays as the no-upgrade fallback line. `repos.yaml` and the local main trees
   still record and check out `harden/yellowback` until the owner switches them; the upgrade line
   is worked in `wt/` worktrees meanwhile.
3. `.venv` — created with `uv` if available, else `python3 -m venv`, and `requirements.txt` installed
   (the Zcash functional-test framework's Python deps, plus a `pyblake2` shim).
4. `make status-short` — a summary of the workspace and its eighteen clones, with the `ref/` pins verified.

Options, passed as `make` variables:

| Invocation | Effect |
|---|---|
| `make bootstrap SSH=1` | Clone the forks and the app repos over `git@github.com:` so you can push. `ref/` stays on https. |
| `make bootstrap NOVENV=1` | Skip the Python venv. |
| `make bootstrap DRY=1` | Print every command that would run, change nothing. |

Bootstrap is idempotent: a repo that already exists is checked against the manifest (tag, commit,
branch, baseline, `upstream` remote, read-only bit) and never modified, so re-running it after a
`git pull` of the workspace is the way to see whether your clones still match `repos.yaml`. It
exits non-zero, listing the warnings, if anything disagrees. Fixing a disagreement is a manual,
deliberate step (see AGENTS.md rule 1 for re-pinning a reference).

Bootstrap does not build anything. The build recipes, with the exact toolchain each fork needs, are
in `ycash-dd/doc/yellowback.md` (node: `./zcutil/build.sh` with the depends system),
`yecwallet-dd/docs/yellowback.md` (wallet: Qt 6 + CMake, bundling the node binary),
`ycash6/doc/yellowback.md` (the 6.20.0 node) and `ycash6/doc/yellowback-release.md` (the release
workflow), `lightwalletd-dd/docs/yellowback.md` (Go), `yew/README.md` (Flutter + Rust core),
`yolo/README.md` (`cargo build --release`), `chain-viz/README.md`, `x402-ycash/README.md`,
`yb-calibration/README.md` and `wyec/README.md` (`contracts/compile.js`).

## Commands

```bash
make                # list targets and the current pins
make bootstrap      # recreate every clone and the venv from repos.yaml (see above)
make pull           # fast-forward every repo from its remote (never merges, rebases or discards; scripts/pull.sh)
make status         # git status for the workspace and its eighteen clones: fetches origin, ahead/behind, ref/ pins verified
make status-short   # same, without the per-file listing
make pins           # one line per repo, machine-readable
make diff           # fork deltas: each fork's branch vs its -legacy baseline
make log            # commits on each fork branch beyond its baseline
make spec           # regenerate docs/spec/yellowback-spec.md and the fork copies from the plan (scripts/extract-spec.sh)
make spec-check     # fail if any generated copy is stale (make status runs it)
```

`make status` **exits non-zero if a `ref/` repo drifts off its pin**, because every `file:line`
citation in `docs/mapping.md` was written against these exact revisions. It also fails if a fork
is not on the branch `repos.yaml` records.

| Repo | Pin | Commit |
|---|---|---|
| `ref/digibyte` | tag `v9.26.5` (2026-07-19) | `05b50e229d` |
| `ref/ycash` | tag `v4.5.0` (2026-04-03) | `624c12814` |
| `ref/yecwallet` | tag `v4.5.0` | `1eb277d` |
| `ref/lightwalletd` | `master` @ commit (2021-07-13; zcash/lightwalletd 0.4.6 + 4 commits, the last the Ycash `s…` regex; the commit carries no tag) | `187a26765e` |
| `ycash-dd` | branch `feature/yellowback-price-attest` (v3) off `ycash-legacy` (= `v4.5.0`); tag `yellowback-v3-baseline` (= `ff7f45947`, re-tagged 2026-10-02 at the security-audit merge; was `9da72131e`) = the frozen-file zero-delta base; `feature/yellowback-sf` = the superseded v2, kept as a record, never a comparison base; `feature/digidollar` = the retired federation prototype, record only; **`upgrade/vault` = the preferred line (the vault network upgrade, GitHub default branch since 2026-10-06)**, cut from `harden/yellowback`, which stays as the no-upgrade fallback | `624c12814` |
| `yecwallet-dd` | branch `feature/yellowback-price-attest` (v3) off `yecwallet-legacy` (= `v4.5.0`); `feature/yellowback-sf` (superseded v2) and `feature/digidollar` are records only, never comparison bases | `1eb277d` |
| `lightwalletd-dd` | branch `feature/yellowback-price-attest` off `lightwalletd-legacy` (= upstream `master` at the pin); re-forked from `yodl/lightwalletd` on 2026-09-24 — the earlier yecdev-based tree is not published | `187a26765e` |
| `ref/ycash6` | `dev-rebase-6.20.0` @ commit (miodragpop's ycashd 6.20.0 rebase, the exact commit its author built; no tag) | `040894344b` |
| `ref/librustzcash6` | `ycashd-v6.20.0` @ commit (miodragpop's Ycash-aware librustzcash; `ref/ycash6/Cargo.toml` `[patch.crates-io]` pins this rev; no tag) | `ec525fae82` |
| `ycash6` | branch `feature/yellowback` off `ycash6-legacy` (= `ref/ycash6`); added 2026-09-30; the overlay on ycashd 6.20.0 and now the release line (6.21.0-rc1 set, not yet tagged); kept separate from `ycash-dd`; **`upgrade/vault` = the preferred line (GitHub default branch since 2026-10-06; releases as 6.22.x)**, `harden/yellowback` the fallback | `040894344b` |
| `librustzcash6` | branch `feature/yellowback` off `librustzcash6-legacy` (= `ref/librustzcash6`); a separate repo, not a GitHub fork (`boyfromcave/librustzcash` is an older fork); zero-delta on `harden/yellowback`, while `upgrade/vault` adds `BranchId::Vault` (`4867cf85`) and `ycash6/Cargo.toml` there pins it | `ec525fae82` |
| `ref/yolo` | `main` @ commit (2020-12-17; yecdev's Ycash port of ChileBob/StratumPool: Perl `stratumpool`, `stratumsolo`, `cenote`; no tags) | `c9c155c6` |
| `yew` | branch `main` (app repo, no baseline: nothing is ported into it) | — |
| `yolo` | branch `main` (app repo; the Rust rewrite of `ref/yolo`, whose Perl is kept under `legacy/perl/`) | — |
| `chain-viz` | branch `main` (app repo, no baseline: a net-new read-only sidecar of the node) | — |
| `x402-ycash` | branch `main` (app repo, no baseline: net new, the primary repo of the x402 plan) | — |
| `yb-calibration` | branch `main` (app repo, no baseline: net new, calibrates the constants baked into Yellowback releases) | — |
| `wyec` | branch `main` (app repo, no baseline: net new, the wYEC token and bridge contracts on Ethereum; added 2026-10-06) | — |

Pins are declared once in [repos.yaml](repos.yaml) (the Makefile reads them from there) and
mirrored in `AGENTS.md` and `docs/mapping.md`. Re-pinning means updating all three.

Note that `ref/digibyte`'s `develop` branch has moved past `v9.26.5` with further DigiDollar
fixes, and `v9.26.6` has since been tagged (seen 2026-10-04); the pin stays at `v9.26.5`. `ref/ycash`
at `v4.5.0` is also upstream's `master` HEAD (checked 2026-10-04).
