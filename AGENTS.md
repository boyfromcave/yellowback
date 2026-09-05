# ydollar-workspace — agent instructions

Bring a decentralized digital dollar to **Ycash** as *YDollar*, using DigiByte's **DigiDollar**
as the reference implementation. Start with [README.md](README.md) for the goal and the
change-budget ladder; this file is the working rules.

**The prime directive is minimal change to the Ycash codebase.** The Ycash team is risk-averse and
the shielded pool's soundness rests on consensus code few people fully understand. Prefer the
cheapest tier that works: Tier 0 (existing opcodes, wallet/RPC, observer hooks, experimental flag —
what Ycash's own atomic-swap feature did in commit `ccddd22e4`) over a soft fork, and a soft fork
over a coordinated network upgrade. When a design trades elegance for a smaller consensus
footprint, take the smaller footprint and record what was given up.

## Layout

```
ydollar-workspace/
├── ref/
│   ├── digibyte/   READ-ONLY. DigiByte, pinned to tag v9.26.5 (05b50e229d)
│   └── ycash/      READ-ONLY. Ycash, pinned to tag v4.5.0 (624c12814)
├── ycash-dd/       THE WORKING FORK. branch `digidollar`, off `ycash-legacy` (= v4.5.0)
├── docs/
│   ├── spec/       DigiDollar upstream spec + the YDollar adaptation spec
│   └── mapping.md  ← THE FILE-BY-FILE CROSSWALK. READ IT FIRST.
└── AGENTS.md / CLAUDE.md   (this file; CLAUDE.md is a symlink to it)
```

## Rules

### 1. `ref/` is read-only. Never edit, never commit, never checkout.

Both `ref/` checkouts are pinned to a tag in detached HEAD and their working trees are
`chmod -R a-w`. They exist to be **read and grepped**, never modified. If a write fails with
`Permission denied` under `ref/`, that is the guardrail working — you are editing the wrong tree.
The file you want is under `ycash-dd/`.

To re-pin deliberately (rare): `chmod -R u+w ref/<repo>` → checkout → `chmod -R a-w ref/<repo>`,
and update the pins recorded in this file and in `docs/mapping.md`.

### 2. All work happens in `ycash-dd/` on the `digidollar` branch.

`ycash-legacy` is the pristine v4.5.0 baseline — **never commit to it.** It exists so you can
always `git diff ycash-legacy...digidollar` to see the entire fork delta. Keep that diff
reviewable.

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

Use **YDollar** / `ydollar` / `YD` in new Ycash code. Do not carry `DigiDollar` / `digidollar` /
`DD` naming across — it makes `git grep` ambiguous between "ported code" and "upstream reference"
and defeats the point of the split. The one exception is comments that cite an upstream file.

### 7. Consensus code is not refactorable.

Anything under `ycash-dd/src/consensus/`, `src/script/`, `src/main.cpp`, `src/pow/`, or
`src/primitives/` changes network rules. Do not tidy, rename, or "improve" surrounding code while
porting. Keep the fork diff minimal and reviewable.

## Useful commands

Start a session with `make status`. It reports all four repos and **exits non-zero if a
`ref/` repo has drifted off its pin** — which would silently invalidate every line citation in
`docs/mapping.md`.

```bash
make            # list targets (same as `make help`)
make status     # git status across all four repos, with pin verification
make status-short   # same, without the per-file listing
make pins       # one line per repo, machine-readable
make diff       # fork delta: ycash-legacy...digidollar
make log        # commits on the fork branch beyond the baseline
```

The pins are declared once, at the top of the `Makefile`, and mirrored in this file and in
`docs/mapping.md`. If you re-pin a reference repo, update all three.

```bash
# Search upstream DigiDollar (read-only)
git -C ref/digibyte grep -n 'OP_DIGIDOLLAR' -- src/

# Search the Ycash baseline (read-only)
git -C ref/ycash grep -n 'SignatureHash' -- src/
```
