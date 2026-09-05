# DigiByte → Ycash crosswalk (`mapping.md`)

**Purpose.** This is the anchor document for every agent session in this workspace. Before you
transplant *anything* from `ref/digibyte` into `ycash-dd`, find the row here. Each row says:

> DigiByte does **X** in file **Y** using **mechanism M**; the Ycash equivalent is **Z**, which
> lacks **M**, so the adaptation is **W**.

**Pinned versions this document describes:**

| Repo | Path | Pin | Commit |
|---|---|---|---|
| DigiByte | `ref/digibyte` | tag `v9.26.5` (2026-07-19) | `05b50e229d` |
| Ycash | `ref/ycash` | tag `v4.5.0` (2026-04-03) | `624c12814` |
| Working fork | `ycash-dd` | branch `dev/digidollar` off `ycash-legacy` (= `v4.5.0`) | `624c12814` |

Line numbers below were read at these pins. If a pin moves, re-verify before trusting them.

---

## 0. The one-paragraph warning

DigiByte v9.26.5 is a **Bitcoin Core ~v26/28-era** codebase with SegWit, Taproot, Tapscript, BIP9
deployments, the per-output `Coin` UTXO model, and a `src/kernel` / `src/node` / `src/index` split.
Ycash v4.5.0 is a **Zcash 4.5 / Bitcoin Core ~0.11–0.12-era** codebase with *no SegWit at all*, no
Taproot, no BIP9, the per-transaction `CCoins` UTXO model, a monolithic `src/main.cpp`, and a
ZIP-243 sighash bound to a consensus branch ID. **DigiDollar's entire opcode layer is gated on
`SigVersion::TAPSCRIPT` and rides on BIP342 `OP_SUCCESSx` semantics for its soft fork.** Neither
of those things exists in Ycash. A naive port produces code that compiles and is consensus-dead.

---

## 1. Structural layout

| Concern | DigiByte (`ref/digibyte`) | Ycash (`ref/ycash`) | Adaptation |
|---|---|---|---|
| Block/tx validation | `src/validation.cpp` (+ `src/consensus/tx_verify.cpp`, `tx_check.cpp`) | `src/main.cpp` (7392 lines, monolithic) | No 1:1 file. Locate the equivalent *function* (`ContextualCheckTransaction`, `ConnectBlock`, `AcceptToMemoryPool`) in `main.cpp`. Do not create `validation.cpp`. |
| Chain parameters | `src/kernel/chainparams.cpp` | `src/chainparams.cpp` | Direct analogue, different path. |
| UTXO set | `src/coins.h` — `class Coin` (per-output, ≥ Core 0.15) | `src/coins.h:75` — `class CCoins` (per-tx, pre-0.15) + `CCoinsModifier` | Any DigiDollar state keyed off a `Coin` must be re-expressed against `CCoins`/`CCoinsViewCache::ModifyCoins`. |
| Indexes | `src/index/` (`digidollarstatsindex.cpp`) | *(no `src/index/`)* | No base index framework. Either build one, or persist DD state in a dedicated LevelDB wrapper alongside `src/txdb.cpp`. |
| Node/kernel split | `src/node/`, `src/kernel/`, `src/init/`, `src/util/`, `src/logging/`, `src/common/` | *(none of these)* | Flatten into `src/`, `src/util*.cpp`, `src/init.cpp`. |
| Shielded pools | *(none)* | `src/zcash/`, `src/rust/`, JoinSplit + Sapling spends/outputs | **DigiByte has no analogue.** See §6. |
| GUI | `src/qt/digidollar*` (≈8k lines) | `src/qt/` does not exist (`ycashd` + `ycash-cli` only; wallet UI is external) | Drop the Qt layer entirely, or scope it out. |

---

## 2. The opcode layer — the single biggest trap

### What DigiByte does

`ref/digibyte/src/script/script.h:209-215`

```
// DigiDollar specific opcodes (using Tapscript OP_SUCCESSx slots for soft fork)
OP_DIGIDOLLAR     = 0xbb,   // Marks DD outputs / payloads
OP_DDVERIFY       = 0xbc,   // Verify DD conditions
OP_CHECKPRICE     = 0xbd,   // Check oracle price
OP_CHECKCOLLATERAL= 0xbe,   // Verify collateral ratio
OP_ORACLE         = 0xbf,   // Oracle price data marker
```

`ref/digibyte/src/script/interpreter.cpp:439-451`

```cpp
static bool IsDigiDollarOpcode(opcodetype opcode)
{ return opcode >= OP_DIGIDOLLAR && opcode <= OP_ORACLE; }

static bool IsOpSuccessForFlags(opcodetype opcode, unsigned int flags)
{
    // DigiDollar opcodes are BIP342 OP_SUCCESSx before activation, exactly as
    // old Taproot nodes see them. Once SCRIPT_VERIFY_DIGIDOLLAR is active they
    // are removed from OP_SUCCESSx and evaluated by the stricter new rules.
    ...
}
```

And every DD opcode case in `EvalScript` opens with the same guard
(`ref/digibyte/src/script/interpreter.cpp:652`, `:688`, `:708`, `:738`):

```cpp
case OP_DIGIDOLLAR: {
    if (sigversion != SigVersion::TAPSCRIPT) {
        return set_error(serror, SCRIPT_ERR_BAD_OPCODE);
    }
    if (!(flags & SCRIPT_VERIFY_DIGIDOLLAR)) {
        return set_success(serror);   // still OP_SUCCESSx pre-activation
    }
    ...
}
```

So the soft-fork story is: **old nodes see 0xbb–0xbf inside a Tapscript leaf and unconditionally
succeed (BIP342 `OP_SUCCESSx`); new nodes evaluate them.** That is the *only* reason DigiDollar can
deploy without a hard fork.

### What Ycash has

- `ref/ycash/src/script/interpreter.h:100-105` — `SigVersion` is
  `SIGVERSION_SPROUT / SIGVERSION_OVERWINTER / SIGVERSION_SAPLING`. **There is no `WITNESS_V0`,
  no `TAPROOT`, no `TAPSCRIPT`.** These constants select a *sighash algorithm*, not a script
  execution context — a completely different meaning from the same-named enum in DigiByte.
- No `SCRIPT_VERIFY_WITNESS`, no `scriptWitness` field, no `bech32`/`bech32m` — Ycash never
  activated SegWit.
- Highest defined opcode is `OP_NOP10 = 0xb9` (`ref/ycash/src/script/script.h:172`). There is no
  `OP_CHECKSIGADD`, no `OP_SUCCESSx`, and **no `OP_CHECKSEQUENCEVERIFY` at all** — only CLTV
  (`SCRIPT_VERIFY_CHECKLOCKTIMEVERIFY = 1U << 9` is the highest verify flag,
  `ref/ycash/src/script/interpreter.h:88`).
- `ref/ycash/src/script/interpreter.cpp:942-943`:
  ```cpp
  default:
      return set_error(serror, SCRIPT_ERR_BAD_OPCODE);
  ```
  Bytes 0xbb–0xbf are **hard failures today**, not no-ops and not successes.

### Adaptation

> **DigiByte** defines DD opcodes at 0xbb–0xbf in `src/script/script.h` and evaluates them in
> `src/script/interpreter.cpp` **only under `SigVersion::TAPSCRIPT`**, relying on BIP342
> `OP_SUCCESSx` for forward compatibility. **Ycash** (`src/script/interpreter.cpp:942`) treats
> those same bytes as `SCRIPT_ERR_BAD_OPCODE` and has no Tapscript context at all, **so the
> adaptation is**: do not port an opcode layer at all if you can avoid one. Options, cheapest
> first — see the change-budget ladder in [`../README.md`](../README.md), which is the ordering
> that governs this project:
>
> 0. **No new opcodes (Tier 0 — try this first).** Express the mint/redeem contract with opcodes
>    Ycash already has: P2SH, `OP_CHECKMULTISIG`, `OP_CHECKLOCKTIMEVERIFY`, `OP_HASH160`,
>    `OP_IF`/`OP_ELSE`. Ycash's own atomic-swap HTLC (`ref/ycash/src/script/atomicswap.h`,
>    commit `ccddd22e4`) does exactly this and touched `interpreter.cpp`, `script.h`,
>    `consensus/` and `chainparams.cpp` **not at all**. The cost is that collateral and supply
>    invariants become quorum-enforced rather than consensus-enforced — a real weakening that must
>    be stated explicitly, not assumed away. **This is the recommended path** unless the trust
>    model is judged unacceptable.
> 1. **Network-upgrade hard fork (Zcash-native).** Add `UPGRADE_YDOLLAR` to
>    `Consensus::UpgradeIndex` (`ref/ycash/src/consensus/params.h`) with a fresh `nBranchId` in
>    `NetworkUpgradeInfo` (`ref/ycash/src/consensus/upgrades.cpp`), and gate the new opcodes on
>    `NetworkUpgradeActive(nHeight, params, Consensus::UPGRADE_YDOLLAR)`. This is how Zcash-family
>    chains normally ship consensus changes, and the branch-ID sighash binding gives free replay
>    protection across the fork. It is also a coordinated hard fork — the largest possible ask of
>    a risk-averse team, so it needs a written justification for why Tier 0 will not do.
> 2. **`OP_NOPx` soft fork (Bitcoin-native).** Re-encode DD semantics onto unused
>    `OP_NOP` slots, which Ycash accepts as no-ops today
>    (`ref/ycash/src/script/interpreter.cpp:388-392`). Nine slots are free — `OP_NOP1` and
>    `OP_NOP3`–`OP_NOP10`; note `OP_NOP3` is free precisely *because* Ycash never implemented
>    `OP_CHECKSEQUENCEVERIFY`, and `OP_NOP2` is CLTV. Each is a bare no-op that consumes nothing
>    from the stack, so multi-operand opcodes like `OP_CHECKCOLLATERAL` do not fit cleanly.
>    Do **not** reuse the 0xbb–0xbf byte values.
>
> In every case: **there is no `sigversion != TAPSCRIPT` guard to copy.** Copying it verbatim
> produces an opcode that can never execute, because `sigversion` in Ycash is never `TAPSCRIPT`.
> If you do add opcodes, that guard is replaced by a height/branch-ID gate.

`OP_CHECKPRICE` (0xbd) is already **deliberately disabled** upstream — see the long comment at
`ref/digibyte/src/script/interpreter.cpp:708-736`: consulting the live oracle price made the
opcode non-deterministic across nodes and was a chain-fork vector. **Do not port it as a working
opcode.** Any price-checking opcode must bind to the block's own committed bundle price.

---

## 3. Sighash and signature context

| | DigiByte | Ycash |
|---|---|---|
| Algorithms | Legacy, BIP143 (witness v0), BIP341 (taproot), BIP342 (tapscript) | Sprout legacy, ZIP-143 (Overwinter), **ZIP-243 (Sapling)** |
| Entry point | `SignatureHash(...)` / `SignatureHashSchnorr(...)` in `src/script/interpreter.cpp` | `SignatureHash(scriptCode, txTo, nIn, nHashType, amount, consensusBranchId, cache)` — `ref/ycash/src/script/interpreter.h:107-114` |
| Extra binding | annex, leaf hash, key/script path, output spent-value vector | **`consensusBranchId`** — sighash is bound to the active network upgrade |
| Precomputation | `PrecomputedTransactionData` w/ taproot fields | `PrecomputedTransactionData { hashPrevouts, hashSequence, hashOutputs, hashJoinSplits, hashShieldedSpends, hashShieldedOutputs }` — `ref/ycash/src/script/interpreter.h:93-98` |

> **DigiByte** signs DD spends with the BIP341/342 taproot sighash, which commits to the leaf
> script and the full spent-output set. **Ycash** signs with ZIP-243, which commits to
> `consensusBranchId` and the shielded bundle hashes but **not** to a script leaf (there are no
> leaves) — **so the adaptation is**: any DD script whose security relies on the taproot leaf
> commitment must get that binding some other way (an explicit commitment pushed into the script,
> or a consensus-level check in `main.cpp`). Concretely, the DigiByte mint script

```
<lockHeight> OP_CHECKLOCKTIMEVERIFY OP_DROP OP_DIGIDOLLAR <amount> OP_DDVERIFY <ownerKey> OP_CHECKSIG
```
(`ref/digibyte/src/digidollar/scripts.h:112`)

> lives in a tapleaf whose hash is committed to by the output's taproot key. In Ycash the same
> script would sit bare in a P2SH `redeemScript`, where its hash is committed to only by the
> 20-byte HASH160 in the `scriptPubKey`. That is a weaker binding and a different collision
> budget — evaluate it explicitly in the adaptation spec, do not assume it carries over.

---

## 4. Activation mechanism

| | DigiByte | Ycash |
|---|---|---|
| Mechanism | BIP9 versionbits, **buried** after activation | Height-gated **network upgrades** (ZIP-200), no signalling |
| Declaration | `Consensus::DEPLOYMENT_DIGIDOLLAR` (`ref/digibyte/src/consensus/params.h:38`), `DigiDollarHeight` (`:122-126`), `deploymentinfo.cpp:44` | `enum UpgradeIndex` in `ref/ycash/src/consensus/params.h`; `NetworkUpgradeInfo[]` in `ref/ycash/src/consensus/upgrades.cpp` |
| Mainnet values | `consensus.DigiDollarHeight = 23869440`; `consensus.nDDActivationHeight = 23627520` (`ref/digibyte/src/kernel/chainparams.cpp:187,327`) | `consensus.vUpgrades[UPGRADE_X].nActivationHeight` in `ref/ycash/src/chainparams.cpp` |
| Query | `DeploymentActiveAt(block, params, Consensus::DEPLOYMENT_DIGIDOLLAR)` | `NetworkUpgradeActive(nHeight, params, Consensus::UPGRADE_X)` |

> **DigiByte** activates DigiDollar via a buried BIP9 bit-23 deployment and threads
> `SCRIPT_VERIFY_DIGIDOLLAR` into script flags once active. **Ycash** has no versionbits machinery
> — every consensus change is a scheduled network upgrade with a new branch ID — **so the
> adaptation is**: add `UPGRADE_YDOLLAR` before `UPGRADE_ZFUTURE` in `UpgradeIndex`, add a matching
> `NetworkUpgradeInfo` entry with a fresh `nBranchId` and `nProtocolVersion`, set
> `nActivationHeight` per network in `chainparams.cpp`, and replace every
> `DeploymentActiveAt(..., DEPLOYMENT_DIGIDOLLAR)` call with `NetworkUpgradeActive(..., UPGRADE_YDOLLAR)`.
> Note `UPGRADE_NU5` already exists in the enum but is **`NO_ACTIVATION_HEIGHT`** on all networks
> (`ref/ycash/src/chainparams.cpp:136-138`) and Ycash has **no Orchard code whatsoever** (zero
> matches for `orchard` in `src/`). Do not build on NU5.
>
> **But first:** a network upgrade is Tier 3 on the change-budget ladder — a coordinated hard fork.
> A Tier-0 design needs no activation mechanism at all, only an experimental-feature flag
> (`ref/ycash/src/experimental_features.h`, e.g. `-experimentalfeatures -atomicswaps`). Reach for
> this section only after Tier 0 has been ruled out in writing.

---

## 5. Transaction format and the `nVersion` collision

### DigiByte

`ref/digibyte/src/primitives/transaction.h:38-58` packs the DD transaction *type* and *flags*
directly into the 32-bit `nVersion`:

```cpp
static const int32_t DD_TX_VERSION  = 0x0D1D0770;   // "DigiDollar" marker
static const int32_t DD_VERSION_MASK= 0x0000FFFF;
static const int32_t DD_TYPE_MASK   = 0xFF000000;
static const int32_t DD_FLAGS_MASK  = 0x00FF0000;

inline int32_t MakeDigiDollarVersion(DigiDollarTxType type, uint8_t flags = 0) {
    return (type << 24) | (flags << 16) | (DD_TX_VERSION & DD_VERSION_MASK);
}
```
with `IsDigiDollarTransaction()` / `GetDigiDollarTxType()` / `GetDigiDollarFlags()` at `:411-427`.

### Ycash

`nVersion` is **not free**. `ref/ycash/src/primitives/transaction.h:548-600`:

- The serialized 4-byte header is `(fOverwintered << 31) | nVersion`.
- `nVersion` is validated to an exact allowed set: `SAPLING_MIN_CURRENT_VERSION == SAPLING_MAX_CURRENT_VERSION == 4` (`:523-524`).
- A separate `uint32_t nVersionGroupId` must equal `SAPLING_VERSION_GROUP_ID = 0x892F2085` (or `OVERWINTER_VERSION_GROUP_ID = 0x03C48270`, or `ZFUTURE_VERSION_GROUP_ID`) — enforced in `ref/ycash/src/main.cpp:896,908,927,1273-1275`.

> **DigiByte** marks a transaction as DigiDollar by bit-packing a magic marker, a type and flags
> into `CTransaction::nVersion`. **Ycash** reserves bit 31 of that field for `fOverwintered` and
> pins the remaining bits to exactly `4`, with a second mandatory `nVersionGroupId` field
> (ZIP-202) — **so the adaptation is**: **do not touch `nVersion`.** Carry the YDollar type/flags
> either (a) in a new `nVersionGroupId` value gated by `UPGRADE_YDOLLAR` plus a new tx version 5
> with an appended YDollar field group, following the ZIP-202/ZIP-225 pattern Ycash already
> implements for Overwinter/Sapling, or (b) out-of-band in an `OP_RETURN` payload output plus
> script-shape detection. Option (a) is more invasive but is the idiom the codebase is built
> around; option (b) avoids touching serialization but makes DD-ness a script-parsing question in
> `main.cpp` rather than a cheap field read.

Also note: `CTxOut` in Ycash is bare `{ CAmount nValue; CScript scriptPubKey; }`
(`ref/ycash/src/primitives/transaction.h`) with no extension point, and Ycash transactions carry
`valueBalance`, `vShieldedSpend`, `vShieldedOutput`, and `vJoinSplit` that DigiByte's transaction
model knows nothing about. Every DD invariant of the form "sum of inputs == sum of outputs" must
be restated to account for `valueBalance` and the shielded value pools.

---

## 6. Shielded pools — a DigiDollar concept with no DigiByte counterpart

DigiByte is transparent-only. Ycash has Sprout JoinSplits and Sapling shielded spends/outputs, plus
a `valueBalance` that moves value between the transparent and shielded pools.

> **DigiByte** can assume every DigiDollar UTXO is transparent and therefore fully auditable by
> consensus — collateral ratios, supply totals, and the stats index all read the UTXO set directly.
> **Ycash** allows value to enter a shielded pool where consensus cannot see amounts or ownership
> — **so the adaptation is**: state explicitly, in `docs/spec/ydollar-adaptation-spec.md`, whether
> YDollar-bearing outputs may be shielded. The safe default is **no** — require DD mint/redeem
> outputs to be transparent and reject any transaction that is both `UPGRADE_YDOLLAR`-typed and
> carries `vShieldedOutput`/`vJoinSplit` — because a shielded DD output makes global DD supply and
> the collateral ratio unverifiable. If shielded DD is a product requirement, it is a research
> project (a Zcash-style value-pool commitment per asset type), not a port.

---

## 7. Oracle subsystem

| | DigiByte | Ycash |
|---|---|---|
| Code | `src/oracle/` (`bundle_manager.cpp` 2812 L, `signing_orchestrator.cpp`, `musig2_session.cpp`, `node.cpp`, `exchange.cpp`), `src/primitives/oracle.cpp` | *(nothing)* |
| Crypto | MuSig2 aggregate Schnorr over secp256k1; 7-of-35 threshold (`ref/digibyte/src/kernel/chainparams.cpp:305-307`) | `src/secp256k1/` is present but **Schnorr/MuSig2 modules are not enabled**; Ycash uses ECDSA for transparent sigs and RedJubjub/Groth16 for shielded |
| Transport | dedicated P2P messages, `src/net_processing.cpp` | `src/main.cpp` P2P message handling (monolithic, older `ProcessMessage`) |
| Block commitment | oracle bundle committed per-block; `nDigiDollarMuSig2Height` gate | Ycash commits `hashFinalSaplingRoot` / chain history root in the header — a different commitment slot |

> **DigiByte** aggregates 7-of-35 oracle price signatures with MuSig2 (Schnorr, secp256k1) and
> commits the bundle into the block, verified by `OracleBundleManager`. **Ycash** ships no oracle
> subsystem, and its vendored `secp256k1` does not enable the Schnorr/MuSig2 modules — **so the
> adaptation is**: this subsystem is a **new build, not a port**. Decide first whether to (a)
> enable the `schnorrsig`/`musig` secp256k1 modules and port `src/oracle/` largely as-is, or
> (b) fall back to plain N-of-M ECDSA multisig over the price bundle, which is bigger on-chain but
> uses crypto Ycash already has. Then decide where the per-block bundle commitment lives — Ycash's
> block header has no spare field, so it goes in the coinbase (an `OP_RETURN` output or a
> committed hash), matching how Heartwood added `hashChainHistoryRoot`.

---

## 8. RPC and wallet

| | DigiByte | Ycash |
|---|---|---|
| DD RPC | `src/rpc/digidollar.cpp` (6305 L), `src/rpc/digidollar_transactions.cpp` | Add a new `src/rpc/ydollar.cpp`; register in `src/rpc/register.h` |
| RPC framework | modern `RPCHelpMan` / `UniValue` with argument specs | older `UniValue` + `fHelp` string convention (`ref/ycash/src/rpc/*.cpp`) — **rewrite, do not copy** |
| Wallet | `src/wallet/digidollarwallet.cpp` (8351 L), descriptor wallets, `CCoinControl` | `src/wallet/wallet.cpp`, legacy keypool wallet with `CWalletTx` + Sapling note management, no descriptors |
| Long ops | synchronous RPC | `AsyncRPCOperation` / `AsyncRPCQueue` (`ref/ycash/src/asyncrpcoperation.h`) — mint/redeem should use this |
| GUI | `src/qt/digidollar*widget.cpp` (~8k L) | **no `src/qt/`** — out of scope |

> **DigiByte** exposes DigiDollar through `RPCHelpMan`-style handlers and a descriptor wallet.
> **Ycash** uses the pre-0.13 `fHelp`/`params` RPC convention and a legacy keypool wallet with
> Sapling note bookkeeping — **so the adaptation is**: treat `src/rpc/digidollar.cpp` and
> `src/wallet/digidollarwallet.cpp` as *behavioural specifications*, not source. Re-derive the
> command surface and the coin-selection/locking rules; hand-write the Ycash-idiomatic
> implementation. Long-running mint/redeem flows should be `AsyncRPCOperation`s.

---

## 9. Quick lookup: "I grepped `ref/digibyte` and found …"

| You found | In | Stop, because | Go read |
|---|---|---|---|
| `OP_DIGIDOLLAR` and friends | `src/script/script.h`, `src/script/interpreter.cpp` | Tapscript-gated; Ycash has no Tapscript and rejects 0xbb–0xbf | §2 |
| `SigVersion::TAPSCRIPT` | `src/script/interpreter.cpp` | Ycash's `SigVersion` means *sighash algorithm*, not script context | §2, §3 |
| `SCRIPT_VERIFY_DIGIDOLLAR` | script flags | Ycash's flag enum stops at bit 9; no witness flags exist | §2, §4 |
| `SignatureHashSchnorr`, annex, tapleaf | `src/script/interpreter.cpp` | Ycash signs with ZIP-243 bound to `consensusBranchId` | §3 |
| `DEPLOYMENT_DIGIDOLLAR`, `DeploymentActiveAt` | `src/consensus/params.h`, `deploymentinfo.cpp` | Ycash has no BIP9 | §4 |
| `DD_TX_VERSION`, `nVersion` bit-packing | `src/primitives/transaction.h` | Ycash's `nVersion` is pinned to 4 + `fOverwintered` bit + `nVersionGroupId` | §5 |
| `class Coin`, `AccessCoin` | `src/coins.h`, `src/validation.cpp` | Ycash uses per-tx `CCoins`/`CCoinsModifier` | §1 |
| anything in `src/validation.cpp` | — | Ycash has no `validation.cpp`; it's `src/main.cpp` | §1 |
| anything in `src/oracle/`, MuSig2 | — | No oracle subsystem, no Schnorr/MuSig2 enabled in Ycash's secp256k1 | §7 |
| `src/index/digidollarstatsindex.cpp` | — | Ycash has no `src/index/` base-index framework | §1 |
| anything in `src/qt/` | — | Ycash has no Qt GUI | §1, §8 |
| `OP_CHECKSEQUENCEVERIFY` | any DD script | **Ycash does not implement CSV at all** — only CLTV | §2 |
| `OP_CHECKPRICE` | `src/script/interpreter.cpp:708` | Deliberately disabled upstream as a chain-fork vector | §2 |

---

## 10. Maintaining this file

- Add a row whenever you hit a new DigiByte↔Ycash impedance mismatch, **even if you worked around
  it in five minutes**. The point is that the next session does not rediscover it.
- Cite `repo/path/file.ext:line` at the pinned tags. Re-verify line numbers if a pin moves.
- Every row must answer all four parts: *DigiByte does X in Y using M; Ycash equivalent is Z, which
  lacks M; adaptation is W.* A row without a **W** is a TODO, not a mapping — mark it `**TODO**`.
