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
│   └── lightwalletd/ READ-ONLY. Ycash lightwalletd (Go, gRPC), no upstream tags: pinned to master @ ec3b96f12
├── ycash-dd/        WORKING FORK of the node.   branch `feature/yellowback-price-attest`, off `ycash-legacy`     (= v4.5.0)
├── yecwallet-dd/    WORKING FORK of the wallet. branch `feature/yellowback-price-attest`, off `yecwallet-legacy` (= v4.5.0)
│                    (`feature/digidollar` in both: the retired federation prototype, kept as a record — never built on)
├── lightwalletd-dd/ WORKING FORK of lightwalletd. branch `feature/yellowback-price-attest`, off `lightwalletd-legacy` (= ec3b96f12)
├── docs/
│   ├── spec/        DigiDollar upstream spec + the generated Yellowback spec (`make spec`)
│   ├── plans/       THE DEVELOPMENT PLANS (v3 = yellowback-v3-development-plan.md, current, in
│   │                implementation; v2 = the delivered miner-enforced plan v3 is a delta on)
│   │   └── archived/   the retired federation design — history only, never an input
│   ├── ideation/    experimental ideas, inactive — not plans, nothing there is being built
│   └── mapping.md   ← THE FILE-BY-FILE CROSSWALK (node §1–§11, wallet §12). READ IT FIRST.
├── repos.yaml       the manifest: every repo, URL, pin (plain nested clones — NOT submodules)
├── scripts/         bootstrap.sh (`make bootstrap`), repos.sh, repo-status.sh, extract-spec.sh (`make spec`)
├── wt/              git worktrees of the forks for parallel agents (untracked, gitignored)
├── yellowback.code-workspace   VS Code multi-root workspace (ref/ folders read-only)
└── AGENTS.md / CLAUDE.md   (this file; CLAUDE.md is a symlink to it)
```

**Two forks, one feature.** The node fork (`ycash-dd`) adds the Yellowback overlay and its `yed_*`
RPCs; the wallet fork (`yecwallet-dd`) adds the Yellowback screens on top of those RPCs and bundles
the node build. DigiByte's `src/qt/digidollar*` is the behavioural reference for the wallet
fork the way `src/digidollar/` is for the node fork — and it is just as much *not* source to
copy: DigiByte's widgets read in-process wallet models; YecWallet reads everything over JSON-RPC
(`ref/yecwallet/src/controller.cpp`, `connection.cpp`).

## Rules

### 1. `ref/` is read-only. Never edit, never commit, never checkout.

All four `ref/` checkouts are pinned in detached HEAD (to a tag, or for `ref/lightwalletd`, whose
upstream publishes no tags, to a commit) and their working trees are `chmod -R a-w`. They exist to be **read and grepped**, never modified. If a write fails with
`Permission denied` under `ref/`, that is the guardrail working — you are editing the wrong tree.
The file you want is under `ycash-dd/`.

To re-pin deliberately (rare): `chmod -R u+w ref/<repo>` → checkout → `chmod -R a-w ref/<repo>`,
and update the pins recorded in this file and in `docs/mapping.md`.

### 2. All work happens in `ycash-dd/`, `yecwallet-dd/` and `lightwalletd-dd/`, on their `feature/yellowback-price-attest` branches.

The current branch in all three forks is `feature/yellowback-price-attest` — the v3 price-attestation
work, cut from `feature/yellowback-sf`. **`feature/yellowback-sf` is now a baseline, not a
workspace:** it is the delivered v2 (miner-enforced) fork, and the v3 plan measures its diff
budgets and frozen-file zero-delta checks against it, so never commit to it either. The branch is
declared once, in `repos.yaml`; `make status` fails if a fork is not on it.

`ycash-legacy` and `yecwallet-legacy` are the pristine v4.5.0 baselines, and `lightwalletd-legacy`
is upstream `master` at the pin — **never commit to them.** They exist so you can always `git diff <legacy>...feature/yellowback-price-attest` to see
the entire fork delta (`make diff` shows both). `feature/digidollar` in both forks is the retired federation
prototype (plan §0, 2026-09-10), kept only as a record: never commit to it and never build on it;
`make log` may list both. Keep those diffs reviewable. Node code goes in `ycash-dd`
only; wallet code goes in `yecwallet-dd` only; light-client server code goes in `lightwalletd-dd`
only; the `yed_*` RPC surface is the sole interface between the node and either client (plan §4.7).

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

Start a session with `make status`. It reports all eight repos and **exits non-zero if a
`ref/` repo has drifted off its pin** — which would silently invalidate every line citation in
`docs/mapping.md`.

```bash
make            # list targets (same as `make help`)
make bootstrap  # fresh machine: clone every repo in repos.yaml at its pin, create .venv (SSH=1 to push)
make pull       # every other day: fast-forward each repo from its remote (DRY=1, NOREF=1, SHORT=1)
make status     # git status across all eight repos, with pin verification
make status-short   # same, without the per-file listing
make pins       # one line per repo, machine-readable
make diff       # fork deltas: each fork (ycash-dd, yecwallet-dd, lightwalletd-dd) vs its -legacy baseline
make log        # commits on each fork branch beyond its baseline
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
