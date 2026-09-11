# yellowback-workspace

Bring a decentralized digital dollar to **Ycash** as **Ycash Yellowback (YED)**, using DigiByte's **DigiDollar** as the
reference implementation — with the smallest possible change to the Ycash codebase.

The reference and target repos are pinned, side by side, so an agent or a human can read the
reference and the target at the same time without confusing one for the other. There are two
targets, because Ycash users reach the node through a GUI: **YecWallet**, a Qt application that
bundles `ycashd` and drives it over RPC.

```
yellowback-workspace/
├── ref/
│   ├── digibyte/    READ-ONLY  DigiByte  @ v9.26.5  — the DigiDollar reference (node + Qt GUI)
│   ├── ycash/       READ-ONLY  Ycash     @ v4.5.0   — the pristine node, for diffing against
│   └── yecwallet/   READ-ONLY  YecWallet @ v4.5.0   — the pristine GUI wallet, for diffing against
├── ycash-dd/        WORKING FORK of the node   — `feature/yellowback-sf` off `ycash-legacy`     (= v4.5.0)
├── yecwallet-dd/    WORKING FORK of the wallet — `feature/yellowback-sf` off `yecwallet-legacy` (= v4.5.0)
├── docs/
│   ├── spec/        DigiDollar's own design docs + the generated Yellowback spec (`make spec`)
│   ├── plans/       THE DEVELOPMENT PLAN (v2, miner-enforced); `archived/` = the retired federation design
│   ├── reference/   the miner-enforced proposal the v2 plan was written from
│   ├── ideation/    inactive experimental ideas — not plans, nothing here is being built
│   ├── mapping.md   the file-by-file, mechanism-by-mechanism crosswalk
│   ├── why-miner-enforced.md        the plain-language rationale for the v2 design
│   └── innovation-acknowledgements.md   what DigiDollar contributed, and where Yellowback diverges
├── repos.yaml       THE MANIFEST — every repo, its URL and its pin (no submodules)
├── Makefile         `make bootstrap` — recreate the workspace; `make status` — repo state + pin check
├── scripts/         bootstrap.sh, repos.sh (manifest reader), repo-status.sh, extract-spec.sh
├── requirements.txt Python deps for the workspace venv (.venv, created by bootstrap)
├── wt/             git worktrees of the forks for parallel agents (untracked, gitignored)
├── yellowback.code-workspace   VS Code: parent + all five clones as roots, ref/ read-only
└── AGENTS.md        working rules  (CLAUDE.md symlinks to it)
```

All `ref/` checkouts are `chmod -R a-w`, so "don't edit the reference" is enforced by the
filesystem, not just documented. All work happens in `ycash-dd/` (node) and `yecwallet-dd/`
(wallet); the `yed_*` RPC surface is the only interface between the two.

---

## What Yellowback is, in one page

**Yellowback v2 is a miner-enforced overlay.** A minter locks YEC in a time-locked P2SH vault they
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
`docs/plans/archived/` and as the `feature/digidollar` branch in both forks — a record, never an
input, never built on.

Rationale: [docs/why-miner-enforced.md](docs/why-miner-enforced.md). Normative protocol:
[docs/spec/yellowback-spec.md](docs/spec/yellowback-spec.md) (generated from the plan's §3 by
`make spec`). Lineage and divergence from DigiDollar:
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

### The change-budget ladder

Prefer the lowest tier that can work. Every step down the list costs review effort and risk.

| Tier | What it touches | Deploy | Precedent in Ycash |
|---|---|---|---|
| **0** | Wallet + RPC only. New script templates built from **existing** opcodes (P2SH, `OP_CHECKMULTISIG`, `OP_CHECKLOCKTIMEVERIFY`, `OP_HASH160`, `OP_IF`). Read-only observer hooks in `main.cpp`. | No fork. Off by default behind an experimental flag. | ✅ **Atomic swaps, shipped in v4.5.0** — see below |
| **1** | Tier 0 + relay/mempool policy (`src/policy/`), non-consensus | No fork (policy only) | standardness rules |
| **2** | New opcode semantics on unused `OP_NOP` slots | Soft fork; old nodes still accept | never done in Ycash |
| **3** | New network upgrade: `UPGRADE_YELLOWBACK`, new branch ID, new tx version / version group | **Hard fork**, coordinated | Overwinter, Sapling, Ycash, Heartwood, Canopy |

**Where Yellowback v2 landed: Tier 1 plus one block-validity hook — and no opcode.** Miner
enforcement does not sit on a rung of this ladder, because it buys a soft fork's effect without a
soft fork's code. Tier 2 is skipped entirely: there is no new opcode, no `OP_NOP` repurposing, no
branch ID, no network upgrade, and no release the Ycash team must ship. The whole enforcement rule
is a pure function of `(block, state, params)` called from the `ConnectBlock` window of the patched
node, inert without `-yellowback`, and switched off with one flag. Measured against `ycash-legacy`
(plan header, 2026-09-11): `src/main.cpp` **11** changed lines, `src/miner.cpp` **12**,
`src/rpc/mining.cpp` **7**, and `src/consensus/`, `src/script/`, `src/primitives/`, `src/pow/`,
`src/wallet/wallet.{h,cpp}` at **zero**. Vaults are ordinary P2SH with `CHECKLOCKTIMEVERIFY` that
Ycash already validates in every block; YED tokens are ordinary transparent P2PKH outputs with one
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

### What that minimality costs, stated honestly

DigiDollar enforces collateral ratios and supply in *consensus*: the chain itself refuses an
invalid mint, which DigiByte could add cheaply because Tapscript's `OP_SUCCESSx` gave it a
soft-fork mechanism. Ycash has no such hook, so Yellowback's guarantees rest on hashpower instead,
and that is a different and weaker assumption than consensus enforcement. Stated plainly:

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
  YED is deferred research.

Do not paper over this. The plan states which properties are consensus-enforced, which are enforced
by every Yellowback-aware node, and which are enforced by the mining pools that run the module —
the trust statement in
[docs/plans/yellowback-v2-development-plan.md](docs/plans/yellowback-v2-development-plan.md) §8.1,
which must be published verbatim with v2. The full trade-off table, each row with the plan citation
that bounds it, is [docs/why-miner-enforced.md](docs/why-miner-enforced.md) §5; that document also
explains why miner enforcement was chosen over a federation (retired, `docs/plans/archived/`) and
over a network upgrade. **Consensus enforcement is still the destination** — the validator is
written so a later Ycash network upgrade would change who runs the check, not what it checks
(plan §9).

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
transparent and shielded. DigiDollar assumes every DD output is transparent and auditable, which
is how it computes supply and collateral ratios at all. **Orchard was never implemented** —
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
3. **[docs/why-miner-enforced.md](docs/why-miner-enforced.md)** — the plain-language
   rationale for v2: why the one rule Ycash script cannot express (burn-before-release) is handed
   to mining pools rather than to a federation or a network upgrade, what that buys
   (self-custody, no committee on redemption, a hashpower-priced feed) and the trade-offs it
   accepts, each with where the plan bounds it.
4. **[docs/plans/yellowback-v2-development-plan.md](docs/plans/yellowback-v2-development-plan.md)** —
   the plan: decision record, the normative protocol (§3), the exact hook lines, the phased work
   plan. It stands alone. `docs/plans/archived/` is the retired federation design (history only);
   `docs/ideation/` holds inactive experimental ideas.
5. **[docs/innovation-acknowledgements.md](docs/innovation-acknowledgements.md)** — what the
   DigiByte team contributed and what Yellowback owes them, alongside the specific points where
   Ycash's principles (decentralization, self-sovereignty, risk aversion) sent the design
   elsewhere. Read it before describing Yellowback to anyone outside the project.
6. **`ref/ycash` commit `ccddd22e4`** — the atomic-swap feature, as a worked example of what a
   well-scoped Ycash feature looks like.

**Where the work stands** is the execution-status table at the top of the plan, kept current by the
coordinator — Phases 0–4, 6, 7 and 7b complete (the node builds clean, and mint / send / redeem /
claim / sweep are proven end to end through YecWallet against a live devnet), Phase 5 (the
enforcement scenarios) in progress, Phase 8 (hardening and review) partly done, and Phases 9–10
(testnet and mainnet with real pools) blocked on pool operators rather than on code. Trust that
table, not this paragraph.

Before porting anything, answer four questions in writing:

> DigiByte does **X** in file **Y** using mechanism **M**.
> The Ycash equivalent is **Z**, which lacks **M**.
> So the adaptation is **W**.

If **M** turns out to be Taproot, SegWit, BIP9, `nVersion` bit-packing, the `Coin` model, or
MuSig2, stop — `docs/mapping.md` already has a row for it. And if **W** requires a consensus
change, say which tier it lands on and why a lower tier will not do.

---

## Getting started

The workspace repo tracks only the documents, the manifest and the scripts. The five nested clones
under `ref/`, `ycash-dd/` and `yecwallet-dd/` are plain git repositories (not submodules),
gitignored here and recreated from [repos.yaml](repos.yaml) by `make bootstrap`.

**Prerequisites:** `git`, `make`, and either `uv` or `python3` (3.10+) for the workspace venv.
Nothing else is needed to bootstrap; the C++/Qt toolchains are only needed to *build*, see below.
The five clones pull about 500 MB of git history (DigiByte is half of it), so allow
a few minutes on the first run.

```bash
git clone git@github.com:boyfromcave/yellowback.git yellowback-workspace
cd yellowback-workspace
make bootstrap            # clone + pin + venv, then `make status` to confirm
code yellowback.code-workspace
```

What `make bootstrap` does, in order:

1. `ref/digibyte`, `ref/ycash`, `ref/yecwallet` — cloned over https, checked out detached at the
   pinned tag, verified against the pinned commit (it aborts if the tag has moved upstream), then
   `chmod -R a-w` so the reference cannot be edited by accident (`.git/` stays writable).
2. `ycash-dd`, `yecwallet-dd` — cloned on `feature/yellowback-sf`; the pristine baseline branch
   (`ycash-legacy` / `yecwallet-legacy`) is created tracking `origin`, verified to equal the matching
   `ref/` pin, and the Ycash Foundation repo is added as remote `upstream` (not fetched).
3. `.venv` — created with `uv` if available, else `python3 -m venv`, and `requirements.txt` installed
   (the Zcash functional-test framework's Python deps, plus a `pyblake2` shim).
4. `make status-short` — a summary of all six repos, with the `ref/` pins verified.

Options, passed as `make` variables:

| Invocation | Effect |
|---|---|
| `make bootstrap SSH=1` | Clone the two forks over `git@github.com:` so you can push. `ref/` stays on https. |
| `make bootstrap NOVENV=1` | Skip the Python venv. |
| `make bootstrap DRY=1` | Print every command that would run, change nothing. |

Bootstrap is idempotent: a repo that already exists is checked against the manifest (tag, commit,
branch, baseline, `upstream` remote, read-only bit) and never modified, so re-running it after a
`git pull` of the workspace is the way to see whether your clones still match `repos.yaml`. It
exits non-zero, listing the warnings, if anything disagrees. Fixing a disagreement is a manual,
deliberate step (see AGENTS.md rule 1 for re-pinning a reference).

Bootstrap does not build anything. The build recipes, with the exact toolchain each fork needs, are
in `ycash-dd/doc/yellowback.md` (node: `./zcutil/build.sh` with the depends system) and
`yecwallet-dd/docs/yellowback.md` (wallet: Qt 6 + CMake, bundling the node binary).

## Commands

```bash
make                # list targets and the current pins
make bootstrap      # recreate every clone and the venv from repos.yaml (see above)
make status         # git status for all six repos, with the ref/ pins verified
make status-short   # same, without the per-file listing
make pins           # one line per repo, machine-readable
make diff           # fork deltas: ycash-legacy...feature/yellowback-sf and yecwallet-legacy...feature/yellowback-sf
make log            # commits on each fork branch beyond its baseline
make spec           # regenerate docs/spec/yellowback-spec.md and the fork copies from the plan (scripts/extract-spec.sh)
make spec-check     # fail if any generated copy is stale (make status runs it)
```

`make status` **exits non-zero if a `ref/` repo drifts off its pin**, because every `file:line`
citation in `docs/mapping.md` was written against these exact revisions.

| Repo | Pin | Commit |
|---|---|---|
| `ref/digibyte` | tag `v9.26.5` (2026-07-19) | `05b50e229d` |
| `ref/ycash` | tag `v4.5.0` (2026-04-03) | `624c12814` |
| `ref/yecwallet` | tag `v4.5.0` | `1eb277d` |
| `ycash-dd` | branch `feature/yellowback-sf` off `ycash-legacy` (= `v4.5.0`); `feature/digidollar` = the retired federation prototype, record only | `624c12814` |
| `yecwallet-dd` | branch `feature/yellowback-sf` off `yecwallet-legacy` (= `v4.5.0`); `feature/digidollar` likewise | `1eb277d` |

Pins are declared once in [repos.yaml](repos.yaml) (the Makefile reads them from there) and
mirrored in `AGENTS.md` and `docs/mapping.md`. Re-pinning means updating all three.

Note that `ref/digibyte`'s `develop` branch has moved past `v9.26.5` with further DigiDollar
fixes; `v9.26.5` is the newest non-rc `9.26.x` tag. `ref/ycash` at `v4.5.0` is also the current
`master` HEAD upstream.
