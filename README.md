# ydollar-workspace

Bring a decentralized digital dollar to **Ycash**, using DigiByte's **DigiDollar** as the
reference implementation — with the smallest possible change to the Ycash codebase.

The reference and target repos are pinned, side by side, so an agent or a human can read the
reference and the target at the same time without confusing one for the other. There are two
targets, because Ycash users reach the node through a GUI: **YecWallet**, a Qt application that
bundles `ycashd` and drives it over RPC.

```
ydollar-workspace/
├── ref/
│   ├── digibyte/    READ-ONLY  DigiByte  @ v9.26.5  — the DigiDollar reference (node + Qt GUI)
│   ├── ycash/       READ-ONLY  Ycash     @ v4.5.0   — the pristine node, for diffing against
│   └── yecwallet/   READ-ONLY  YecWallet @ v4.5.0   — the pristine GUI wallet, for diffing against
├── ycash-dd/        WORKING FORK of the node   — `feature/digidollar` off `ycash-legacy`     (= v4.5.0)
├── yecwallet-dd/    WORKING FORK of the wallet — `feature/digidollar` off `yecwallet-legacy` (= v4.5.0)
├── docs/
│   ├── spec/        DigiDollar's own design docs + our Ycash adaptation spec
│   ├── plans/       the development plan (node, federation, wallet GUI, single-machine testing)
│   └── mapping.md   the file-by-file, mechanism-by-mechanism crosswalk
├── AGENTS.md        working rules  (CLAUDE.md symlinks to it)
└── Makefile         `make status` — repo state + pin verification
```

All `ref/` checkouts are `chmod -R a-w`, so "don't edit the reference" is enforced by the
filesystem, not just documented. All work happens in `ycash-dd/` (node) and `yecwallet-dd/`
(wallet); the `yd_*` RPC surface is the only interface between the two.

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
| **3** | New network upgrade: `UPGRADE_YDOLLAR`, new branch ID, new tx version / version group | **Hard fork**, coordinated | Overwinter, Sapling, Ycash, Heartwood, Canopy |

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

### What Tier 0 costs, stated honestly

DigiDollar enforces collateral ratios and supply in *consensus*: the chain itself refuses an
invalid mint. A Tier-0 YDollar cannot do that — with no new opcodes, correctness has to rest on an
oracle/federation quorum co-signing valid mints and redemptions under a P2SH multisig, with CLTV
timeouts as the escape hatch.

That is a **weaker trust model**: a quorum that refuses to sign can censor, and a compromised
quorum can mint unbacked dollars. Consensus enforcement is strictly stronger.

Do not paper over this. The adaptation spec has to state which properties are consensus-enforced
and which are quorum-enforced, and the answer decides whether Tier 0 is acceptable or whether the
project has to buy its way up to Tier 2 or 3. **Decide this before writing code** — it is the
single most consequential open question in
[docs/spec/ydollar-adaptation-spec.md](docs/spec/ydollar-adaptation-spec.md).

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
zero occurrences of `orchard` in `src/`. The safe default is that YDollar outputs must be
transparent; a shielded YDollar makes global supply unverifiable and is a research project, not a
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
**[docs/mapping.md](docs/mapping.md)**.

---

## Start here

1. **[AGENTS.md](AGENTS.md)** — the working rules. Short. Read it first.
2. **[docs/mapping.md](docs/mapping.md)** — the crosswalk. Read the relevant row *before* porting
   any symbol. It exists to stop one specific failure: grepping `ref/digibyte` for a DigiDollar
   symbol and transplanting it into a Ycash file with incompatible semantics.
3. **[docs/why-no-consensus-change.md](docs/why-no-consensus-change.md)** — the plain-language
   rationale for the Tier-0 decision: how every DigiDollar feature maps onto rules Ycash already
   enforces, and the one rule (burn-before-release) that a federation enforces instead.
4. **[docs/spec/ydollar-adaptation-spec.md](docs/spec/ydollar-adaptation-spec.md)** — the design
   we are writing. Currently a skeleton of open decisions.
5. **`ref/ycash` commit `ccddd22e4`** — the atomic-swap feature, as a worked example of what a
   well-scoped Ycash feature looks like.

Before porting anything, answer four questions in writing:

> DigiByte does **X** in file **Y** using mechanism **M**.
> The Ycash equivalent is **Z**, which lacks **M**.
> So the adaptation is **W**.

If **M** turns out to be Taproot, SegWit, BIP9, `nVersion` bit-packing, the `Coin` model, or
MuSig2, stop — `docs/mapping.md` already has a row for it. And if **W** requires a consensus
change, say which tier it lands on and why a lower tier will not do.

---

## Commands

```bash
make            # list targets
make status     # git status for all four repos, and verify the ref/ pins
make pins       # one line per repo, machine-readable
make diff       # the fork delta: ycash-legacy...feature/digidollar
make log        # commits on the fork branch beyond the baseline
```

`make status` **exits non-zero if a `ref/` repo drifts off its pin**, because every `file:line`
citation in `docs/mapping.md` was written against these exact revisions.

| Repo | Pin | Commit |
|---|---|---|
| `ref/digibyte` | tag `v9.26.5` (2026-07-19) | `05b50e229d` |
| `ref/ycash` | tag `v4.5.0` (2026-04-03) | `624c12814` |
| `ycash-dd` | branch `feature/digidollar` off `ycash-legacy` (= `v4.5.0`) | `624c12814` |

Pins are declared once at the top of the [Makefile](Makefile) and mirrored in `AGENTS.md` and
`docs/mapping.md`. Re-pinning means updating all three.

Note that `ref/digibyte`'s `develop` branch has moved past `v9.26.5` with further DigiDollar
fixes; `v9.26.5` is the newest non-rc `9.26.x` tag. `ref/ycash` at `v4.5.0` is also the current
`master` HEAD upstream.
