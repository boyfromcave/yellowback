# DigiByte → Ycash crosswalk (`mapping.md`)

**Purpose.** This is the anchor document for every agent session in this workspace (the
product is **Ycash Yellowback (YED)**: Yellowback is the system, YED is the unit). Before you
transplant *anything* from `ref/digibyte` into `ycash-dd`, find the row here. Each row says:

> DigiByte does **X** in file **Y** using **mechanism M**; the Ycash equivalent is **Z**, which
> lacks **M**, so the adaptation is **W**.

**Pinned versions this document describes:**

| Repo | Path | Pin | Commit |
|---|---|---|---|
| DigiByte | `ref/digibyte` | tag `v9.26.5` (2026-07-19) | `05b50e229d` |
| Ycash | `ref/ycash` | tag `v4.5.0` (2026-04-03) | `624c12814` |
| YecWallet (GUI) | `ref/yecwallet` | tag `v4.5.0` (2026-04-07; upstream `master` is 7 build-only commits later) | `1eb277d` |
| Working fork (node) | `ycash-dd` | branch `feature/yellowback-sf` off `ycash-legacy` (= `v4.5.0`); `feature/digidollar` is the retired federation prototype, kept as a record | `624c12814` |
| Working fork (wallet) | `yecwallet-dd` | branch `feature/yellowback-sf` off `yecwallet-legacy` (= `v4.5.0`); `feature/digidollar` likewise | `1eb277d` |

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
| GUI | `src/qt/digidollar*` (≈ 10.4k lines, in-process Qt widgets over `WalletModel`) | `src/qt/` does not exist; the GUI is **YecWallet** (`ref/yecwallet`, ≈ 8.3k lines, Qt 6 + CMake), a separate application that bundles `ycashd` and drives it over JSON-RPC | Build the Yellowback screens in `yecwallet-dd` against the `yed_*` RPCs; DigiByte's widgets are the behavioural reference. See §12. |

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
> 1. **Network-upgrade hard fork (Zcash-native).** Add `UPGRADE_YELLOWBACK` to
>    `Consensus::UpgradeIndex` (`ref/ycash/src/consensus/params.h`) with a fresh `nBranchId` in
>    `NetworkUpgradeInfo` (`ref/ycash/src/consensus/upgrades.cpp`), and gate the new opcodes on
>    `NetworkUpgradeActive(nHeight, params, Consensus::UPGRADE_YELLOWBACK)`. This is how Zcash-family
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
> adaptation is**: add `UPGRADE_YELLOWBACK` before `UPGRADE_ZFUTURE` in `UpgradeIndex`, add a matching
> `NetworkUpgradeInfo` entry with a fresh `nBranchId` and `nProtocolVersion`, set
> `nActivationHeight` per network in `chainparams.cpp`, and replace every
> `DeploymentActiveAt(..., DEPLOYMENT_DIGIDOLLAR)` call with `NetworkUpgradeActive(..., UPGRADE_YELLOWBACK)`.
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
> (ZIP-202) — **so the adaptation is**: **do not touch `nVersion`.** Carry the Yellowback type/flags
> either (a) in a new `nVersionGroupId` value gated by `UPGRADE_YELLOWBACK` plus a new tx version 5
> with an appended Yellowback field group, following the ZIP-202/ZIP-225 pattern Ycash already
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
> — **so the adaptation is**: state explicitly, in the plan's normative protocol (§3, V8), whether
> YED-bearing outputs may be shielded. The safe default is **no** — require DD mint/redeem
> outputs to be transparent and reject any transaction that is both `UPGRADE_YELLOWBACK`-typed and
> carries `vShieldedOutput`/`vJoinSplit` — because a shielded DD output makes global DD supply and
> the collateral ratio unverifiable. If shielded DD is a product requirement, it is a research
> project (a Zcash-style value-pool commitment per asset type), not a port.

**Refinement (plan revision 14, I1).** The argument above is about *YED-bearing outputs*, and for
those it is structural: the payload assigns cents to `vout` indexes and a Sapling output has none,
so shielded YED is undefined rather than forbidden. It does **not** extend to the YEC side of the
same transaction. A mint whose collateral arrives via `vShieldedSpend` + `valueBalance > 0` still
has a transparent `vout[0]` whose `nValue` every node can read (MINT-5); a transfer whose fee comes
from `ys1…` still assigns cents to transparent outputs. The state rules therefore ignore the
shielded fields (TX-0 covers the coinbase only). Transparent-only is enforced where it is a cost,
not a soundness matter: the v1 wallet builder (plan D9) and the redemption co-signers (RED-4).

---

## 7. Oracle subsystem

| | DigiByte | Ycash |
|---|---|---|
| Code | `src/oracle/` (`bundle_manager.cpp` 2812 L, `signing_orchestrator.cpp`, `musig2_session.cpp`, `node.cpp`, `exchange.cpp`), `src/primitives/oracle.cpp` | *(nothing)* |
| Crypto | MuSig2 aggregate Schnorr over secp256k1; 7-of-35 threshold (`ref/digibyte/src/kernel/chainparams.cpp:305-307`) | `src/secp256k1/` is present but **Schnorr/MuSig2 modules are not enabled**; Ycash uses ECDSA for transparent sigs and RedJubjub/Groth16 for shielded |
| Transport | dedicated P2P messages, `src/net_processing.cpp` | `src/main.cpp` P2P message handling (monolithic, older `ProcessMessage`) |
| Block commitment | oracle bundle committed per-block; `nDigiDollarMuSig2Height` gate | Ycash commits `hashFinalSaplingRoot` / chain history root in the header — a different commitment slot |
| Price sources | six exchange fetchers compiled in, one class each (`ref/digibyte/src/oracle/exchange.cpp:1092-1097`), sequential fetch, 10 % median outlier filter (`FilterOutliers`, `:1225`) | *(nothing)*. Yellowback: operator TOML `[[sources]]` with presets for the two venues that list YEC (SafeTrade, Nonkyc) and CoinGecko, or a generic URL + JSON path with list selectors; YEC/BTC pairs converted with a median of configured BTC/USD references; per-source freshness and spread guards; thresholds configurable (`ycash-dd/contrib/yellowback/yellowback_fed.py`, plan D22) |

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
| DD RPC | `src/rpc/digidollar.cpp` (6305 L), `src/rpc/digidollar_transactions.cpp` | Add a new `src/rpc/yellowback.cpp`; register in `src/rpc/register.h` |
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

---

## 11. Rows added while writing the federation prototype's plan (2026-09, retired)

All cites at the pinned tags. The impedance mismatches recorded here still hold for the current
design; the federation-specific adaptations (anchor UTXO, roster, co-signing) were retired with
that design on 2026-09-10 (its plan is history under `plans/archived/`; the current plan is
[`plans/yellowback-v2-development-plan.md`](plans/yellowback-v2-development-plan.md)).

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| Wallet recognises and signs DD vaults via descriptor/Taproot solvers (`src/wallet/digidollarwallet.cpp`, script-path signing) | `IsMine` and `ProduceSignature`/`signrawtransaction` only solve standard templates; a P2SH redeem script with `CLTV … CHECKSIGVERIFY … CHECKMULTISIG` is unsolvable (`ref/ycash/src/script/sign.cpp`, `ref/ycash/src/rpc/rawtransaction.cpp:1057-1061`) | Track vaults in the Yellowback index, not the wallet; sign vault inputs manually with `SignatureHash(redeemScript, tx, nIn, SIGHASH_ALL, amount, branchId)` + `CKey::Sign`, as `ref/ycash/src/rpc/atomicswap.cpp:760-775` does; `yed_cosignredeem` merges signatures in roster order |
| Carries DD metadata in `OP_RETURN` with no tight relay bound (`src/digidollar/txbuilder.cpp:407-418, 807-818`) | Policy allows exactly one `OP_RETURN` and 80 data bytes (`ref/ycash/src/policy/policy.cpp:52,123`; `ref/ycash/src/script/standard.h:34`) | Payload budget of 80 bytes per tx: MINT ≤ 47 B, TRANSFER ≤ 12 assignments; roster pubkeys never travel in payloads — rosters are revealed by anchor spends |
| Mint lock window `[tier, tier+100]` against confirmation height (`src/digidollar/validation.cpp:1377`); no tx expiry | Every Ycash tx has `nExpiryHeight`; default delta 40 post-Blossom; mempool rejects "expiring soon" (`ref/ycash/src/main.h:78-81`, `main.cpp:1548`) | `MINT_WINDOW = 40` = expiry delta; wallet sets `lockHeight = tip + tierBlocks + 40`; redeems use a normal expiry of `tip + 40` (never 0) |
| Index/state updated synchronously inside `ConnectBlock`/`DisconnectBlock` (`src/validation.cpp`, `src/index/`) | `ThreadNotifyWallets` delivers `ChainTip(pindex, pblock, added)` for every connect and disconnect, in order, once per second on a background thread, from genesis under `-reindex`, without try/catch around block callbacks (`ref/ycash/src/validationinterface.cpp:183-217`; started at `init.cpp:1831-1847`) | Yellowback index is a `CValidationInterface` subscriber (zero `main.cpp` lines); handler must be idempotent, catch all exceptions, and RPCs report the index height rather than `chainActive.Height()` |
| 35-key oracle roster aggregated by MuSig2 into one 64-byte signature | P2SH limits: 520-byte redeem script push (`ref/ycash/src/script/script.h:23`), 1650-byte scriptSig (`policy.cpp:93`), 15 P2SH sigops (`policy.h:24`) | Federation roster bounded to n ≤ 13 with one owner key; v1 uses 5-of-9 |
| `__int128` collateral/health math (`src/consensus/dca.cpp:37-44`, `err.cpp:100`) | No `__int128` anywhere in Ycash | Use `arith_uint256` (`ref/ycash/src/arith_uint256.h`) for all products |
| BIP-340 Schnorr + MuSig2 via modern libsecp256k1 modules | Vendored `secp256k1` configured with only `--enable-module-recovery` (`ref/ycash/configure.ac:1282`) | ECDSA `OP_CHECKMULTISIG` for both price attestations and vault co-signing; no crypto library changes |
| DD-ness read from `nVersion`; no shielded fields exist | `nVersion` pinned to 4; `nExpiryHeight`, `valueBalance`, `vShieldedSpend/Output`, `vJoinSplit` on every tx (`ref/ycash/src/primitives/transaction.h:553-558`) | Payload type byte marks Yellowback txs; rule TX-0 requires fully transparent transactions |
| Miner embeds the oracle bundle in the coinbase (`src/node/miner.cpp`) | Coinbase shape governed by founders'/YDF streams; `miner.cpp` is on the consensus-adjacent list | Prices are ordinary transactions spending a federation anchor UTXO; consensus verifies the k-of-n ECDSA signatures for free (`MANDATORY_SCRIPT_VERIFY_FLAGS = P2SH`, `ref/ycash/src/script/standard.h:53`) |

### Rows added by the revision-3 audit of the plan (full `ycash-dd` read)

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| Oracle/coordinator code builds transactions with a modern `createrawtransaction` that accepts `"data"` outputs, or in-process (`src/oracle/`) | Ycash's `createrawtransaction` takes only `{"address": amount}` outputs — no `OP_RETURN` (`ref/ycash/src/rpc/rawtransaction.cpp:539-620`) | A node RPC (`yed_createpricetx`) builds the unsigned price transaction with `CreateNewContextualCMutableTransaction` (`ref/ycash/src/main.cpp:7364`); the coordinator only signs and broadcasts |
| Descriptor wallets sign any solvable P2SH/P2WSH from the descriptor | `signrawtransaction` adds a `prevtxs` `redeemScript` to its keystore only when private keys are supplied (`fGivenKeys`, `ref/ycash/src/rpc/rawtransaction.cpp:966-974`); wallet signing needs the script in `wallet.dat` | Every federation operator runs `addmultisigaddress` once (`AddCScript`, `ref/ycash/src/wallet/rpcwallet.cpp:1175`); `prevtxs` (with `amount`) only for unconfirmed anchors |
| Consensus rejects an invalid mint; the user loses nothing | An overlay cannot reject; a mint that fails its rules at confirmation locks collateral for the whole tier | The MINT payload commits an `evalHeight`; collateral rules read the node's snapshot at that height, so the wallet knows the exact requirement before signing (plan §3.7, B3) |
| Wallet marks DD coins via its own tables at creation | Own 0-conf outputs are *trusted* and immediately spendable (`CWalletTx::IsTrusted`, `ref/ycash/src/wallet/wallet.cpp:4842-4867`); `LockCoin` is in-memory and asserts `cs_wallet` (`wallet.cpp:6265`) | Lock overlay coins **before** `CommitTransaction`, pre-lock from `SyncTransaction`, reconcile in `ChainTip`; lock order `cs_main → cs_wallet → cs_yellowback` |
| Functional tests run with standardness enforced | Regtest sets `fRequireStandard = false` (`ref/ycash/src/chainparams.cpp:671`); no `-acceptnonstdtxn`; `IsStandardTx`/`AreInputsStandard` skipped (`main.cpp:1558,1646`) | Pin relay constraints with Boost unit tests that call both functions directly |
| Test framework carries the chain's real deployment parameters | `qa/rpc-tests/test_framework/util.py:40-42` has **Zcash's** Blossom/Heartwood/Canopy branch IDs; Ycash's are `0x8e471bd6`, `0x66314da3`, `0x19bd2d2f` (`ref/ycash/src/consensus/upgrades.cpp`) and `-nuparams` rejects unknown IDs (`init.cpp:1212-1246`); the cached regtest chain activates only Overwinter+Sapling; CI (`.github/workflows/book.yml`) runs no functional tests | Define Ycash IDs in `yellowback_util.py`, activate all upgrades at height 1 with `setup_clean_chain = True` (regtest keeps Equihash 48/5, `chainparams.cpp:860-863`); add a fork-local CI job |
| Deep reorgs handled by the index framework | Node refuses reorgs longer than `MAX_REORG_LENGTH = 99` (`ref/ycash/src/main.h:62`, `main.cpp:3772`); `RewindBlockIndex` at init can move the tip further (`init.cpp:1695`) | Keep ~1,000 undo records; deeper ⇒ wipe and rebuild |
| Fee estimation loop in the DD wallet | Every `z_*` operation uses a flat `DEFAULT_FEE = 1000` zat (`ref/ycash/src/policy/fees.h:15`) | Flat fee, no estimation |
| `TransactionBuilder`-style helpers accept arbitrary scripts | Ycash's `TransactionBuilder` (`ref/ycash/src/transaction_builder.h`) has no raw-script output and `Build()` signs only keystore-solvable inputs | Build manually as `rpc/atomicswap.cpp` does; start from `CreateNewContextualCMutableTransaction` |
| Wallet history is the source of truth | `-DYCASH_WR` builds add `-deletetx`, pruning old wallet transactions (`ref/ycash/src/wallet/wallet.cpp:4112-4400`) but keeping those with unspent transparent outputs that are mine (`:4336-4348`) | History RPCs read the overlay index, not `mapWallet` |

### Rows added by the revision-4 audit of the plan

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| Consensus validation has the full UTXO set in hand for every DD transaction (`src/digidollar/validation.cpp`) | The overlay index knows only Yellowback outpoints; a redemption's fee and `AreInputsStandard` need every input's value and `scriptPubKey`, which only `pcoinsTip` has | Co-signer and validator RPCs hold `cs_main` and build the input view as `signrawtransaction` does — `pcoinsTip` behind `CCoinsViewMemPool` (`ref/ycash/src/rpc/rawtransaction.cpp:906-921`); `Tokens` records also store `nValue` (plan C1) |
| Wallet knows a DD coin is a DD coin from its own tables, in and out of blocks | `ThreadNotifyWallets` emits `SyncTransaction(tx, NULL, h)` identically for mempool arrivals, conflicts and every transaction of a **disconnected** block (`ref/ycash/src/validationinterface.cpp:183,210,226`); a disconnected transaction re-enters the mempool where its outputs are trusted 0-conf | Overlay coin locks are never released on disconnect; only a confirmed transaction whose verdict assigns no cents releases a lock (plan C3) |
| Oracle members sign a bundle, never a transaction (`src/oracle/`) | `signrawtransaction` signs **every** input the wallet can solve (`rawtransaction.cpp:1044-1057`) | Operator wallets are dedicated; a co-signing peer refuses any non-anchor input its wallet can solve; `yed_cosignredeem` signs only `vin[0]` over the vault script reconstructed from the index (plan C5) |
| Modern `createrawtransaction`/wallet picks change addresses for oracle-side transactions | `yed_createpricetx` runs in node context with no wallet to pick change from | The refill input is absorbed whole into the new anchor; the proposer pre-creates a confirmed UTXO of the exact amount (plan C6) |
| Regtest chain parameters activate every deployment by default (`src/kernel/chainparams.cpp` regtest) | Ycash regtest sets Overwinter, Sapling, Ycash, Blossom, Heartwood, Canopy all to `NO_ACTIVATION_HEIGHT` (`ref/ycash/src/chainparams.cpp:576-604`); post-Ycash coinbases need a 5 % YDF output until `nYdfMandateEndHeight = 5` (`main.cpp:4508-4522`), which `miner.cpp:201-203` adds itself | Functional tests pass six `-nuparams=<id>:1`; nothing else needed (plan C12) |
| Index tests poll the index for the tip | `sync_blocks`/`sync_mempools` wait on `fullyNotified` (`qa/rpc-tests/test_framework/util.py:133,160`; `src/rpc/blockchain.cpp:1188,1415`), set after every `CValidationInterface` subscriber ran for the cycle (`validationinterface.cpp:238-241`) | After `sync_all()` the overlay index is at the tip; no separate poll (plan C13) |
| Fuzz targets under `src/test/fuzz/` (libFuzzer, Core ≥ 0.19) | Ycash fuzz targets are `src/fuzzing/<Target>/fuzz.cpp` with an `input/` corpus (`ref/ycash/src/fuzzing/`) | Same layout for `YellowbackPayload` and `YellowbackScript` (plan C14) |
| Fee is estimated per transaction | ZIP-401 mempool limiter adds `LOW_FEE_PENALTY` to any transaction paying under `DEFAULT_FEE` (`ref/ycash/src/mempool_limit.cpp:151-157`) | Flat `YELLOWBACK_FEE = DEFAULT_FEE`, and `-yellowbackfee` may not go below it (plan C16) |
| Regtest DD parameters are compiled in | Regtest genesis anchor is created by the test at run time; the index needs the anchor's block height as well as the outpoint and script | `-yellowbackstartheight`, `-yellowbackgenesisanchor`, `-yellowbackgenesisroster` (regtest only, all three together) (plan C2) |

### Rows added by the revision-5 audit of the plan

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| Validation reads inputs through `Coin` lookups that return "missing" gracefully (`src/validation.cpp`, `AccessCoin`) | `CCoinsViewCache::GetOutputFor` and `GetValueIn` **assert** the coin exists and is unspent (`ref/ycash/src/coins.cpp:898-903,912`); `AreInputsStandard` calls the former (`policy.cpp:137`) | Any policy check on a caller-supplied transaction verifies `HaveCoins` + `IsAvailable` for every input first; a phantom input is a refusal, never an abort (plan D1) |
| Index/subscriber lifetime managed by `node::NodeContext` with an ordered shutdown | Normal shutdown joins the thread group before `Shutdown()` (`ref/ycash/src/bitcoind.cpp:52-55`), but the startup-failure path skips `join_all` (`:191-194`), so `ThreadNotifyWallets` may still be inside a `ChainTip` slot when `Shutdown()` unregisters subscribers; `UnregisterValidationInterface` does not wait for a running slot | Unregister, then stop and flush the index under its own lock; never delete it during `Shutdown()` (plan D2) |

### Rows added by the revision-6 audit of the plan

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| Wallet and RPC history read DD transactions back through `txindex` / the wallet's DD tables (`src/wallet/digidollarwallet.cpp`) | `GetTransaction` finds a confirmed transaction only with `-txindex` (`ref/ycash/src/main.cpp:1858-1870`); the overlay erases spent token records | The overlay keeps an append-only `TxLog` per Yellowback-relevant transaction, undone with the block; history and verdict RPCs read it, so `-txindex` is never required (plan E1) |
| Descriptor wallets with mature encryption hold oracle and vault keys | Ycash wallet encryption is experimental and gated behind `-developerencryptwallet` (`ref/ycash/src/wallet/rpcwallet.cpp:2127,2160`) | Custody by host: dedicated machine, full-disk encryption, localhost RPC, offline `wallet.dat` backups; no reliance on wallet encryption (plan E5) |

### Rows added by the revision-7 audit of the plan

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| Transactions never expire; an unmined DD transaction stays valid and the wallet's unconfirmed outputs stay spendable | Every Ycash transaction has `nExpiryHeight`; the mempool drops it at the next block (`ref/ycash/src/main.cpp:3636`), but the wallet keeps it at depth 0, rebroadcasts it (`wallet.cpp:4653-4668`) and still offers its outputs to coin selection (`AvailableCoins`, `wallet.cpp:5038-5052`, no expiry filter) | Every YED input is confirmed — YED inputs from the index, YEC inputs via the existing `AvailableCoins(..., nMinDepth = 1)`; expired Yellowback transactions are reported by `yed_gettxinfo` and re-run (plan F3, F6) |
| DigiDollar's oracle tests run a 35-member roster with in-process mock signers (`src/test/`, `mock_oracle.cpp`) | Ycash's functional framework runs at most `MAX_NODES = 8` separate `ycashd` processes per test (`qa/rpc-tests/test_framework/util.py:46`), one wallet each | Five operator nodes hold five real keys; keys 6–9 are generated by `test_framework/key.py` and enter the roster as public keys only, so the production 5-of-9 script is exercised with five signers (plan §6.0, G2: the keys come from a node wallet, not `test_framework/key.py`, which binds OpenSSL via `ctypes`) |
| Functional tests write `bitcoin.conf`/`digibyte.conf` matching the daemon | The inherited framework writes `zcash.conf` (`qa/rpc-tests/test_framework/util.py:175`, `multi_rpc.py:29`) but Ycash reads only `ycash.conf` (`ref/ycash/src/util.cpp:76`) and exits without it (`util.cpp:372-378`, `bitcoind.cpp:104-113`); `start_node` relies on the file for `regtest=1` | Two-line framework fix in Phase 0; until then no `qa/rpc-tests` script can start a Ycash node (plan G1) |

### Rows added by revisions 14 and 15 of the plan (2026-09-05)

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| Every DD transaction is transparent because the chain is; `validation.cpp` never asks where the collateral came from | A Ycash transaction can fund its transparent outputs from Sapling (`valueBalance > 0`, `ref/ycash/src/primitives/transaction.h:553-558`) or shield its change (`valueBalance < 0`); the overlay's first draft voided/burned any payload on such a transaction (old TX-0) | The state rules ignore the shielded fields: the index reads transparent inputs, `vout` indexes and the `OP_RETURN`, all of which are unchanged by a Sapling component. Transparent-only lives in the v1 wallet builder (`ycash-dd/src/yellowback/txbuilder.cpp`, plan D9) and co-signer policy (RED-4, `policy.cpp`), both changeable without an index-consensus change (plan I1, §6 above) |
| DD mints and redemptions are built by `src/digidollar/txbuilder.cpp` from transparent coins only; the chain has no shielded pool to fund from or pay to | Ycash users hold YEC in Sapling notes; `TransactionBuilder` (`ref/ycash/src/transaction_builder.h:129-180`) is the only code that produces Sapling proofs and the binding signature, but it offers no raw-script output (the `OP_RETURN` payload), signs every transparent input through the keystore (`transaction_builder.cpp:303`, the vault script is not solvable) and has no lock-time setter (`nLockTime = lockHeight` is how a redemption passes CLTV) | Three additive methods in `ycash-dd/src/transaction_builder.{h,cpp}` — raw-script output, unsigned transparent input with explicit `nSequence`, `SetLockTime` — and `Build()` skips unsigned inputs. The vault and YED inputs are signed after `Build()`: ZIP-243 covers `hashPrevouts`/`hashSequence`/`hashOutputs`, never `scriptSig`s (`ref/ycash/src/script/interpreter.cpp:1109-1121`), so the binding signature survives. The fork's first logic edit outside `src/yellowback/` (plan D9, I2) |

---

## 12. The GUI — DigiByte `src/qt/digidollar*` → YecWallet (`yecwallet-dd`)

Ycash has no in-tree GUI. Its full-node GUI is **YecWallet** (`ref/yecwallet`, pinned `v4.5.0`,
`1eb277d`): a Qt 6 / CMake C++ application of the zec-qt-wallet lineage that ships `ycashd`
beside its own binary, starts it (`src/connection.cpp:323-380`), writes its `~/.ycash/ycash.conf`
on first run (`connection.cpp:130-215`), and reads everything over JSON-RPC on a timer
(`src/controller.cpp:28-52,247-280`). DigiByte's DigiDollar GUI is seven in-process Qt tabs over
the node's `WalletModel`/`ClientModel` (`ref/digibyte/src/qt/digidollartab.cpp:100-106`). Same
toolkit, different architecture: **the DigiByte widgets read wallet objects; YecWallet reads RPC
JSON.** Every row below has the same shape as §1–§11.

| DigiByte does X (Y, mechanism M) | YecWallet equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| Seven DD tabs inside the node's own Qt GUI (`src/qt/digidollartab.cpp`), sharing `WalletModel`, `ClientModel`, `OptionsModel` | YecWallet has four tabs — Balance, Send, Receive, Transactions — plus a hidden `ycashd` console tab (`src/mainwindow.ui:29,289,663,894,911`; `mainwindow.cpp:132-139`), each populated by `Controller` from RPC replies; no in-process wallet objects at all | One new **Yellowback** tab (`src/yellowbacktab.cpp`, `.ui`) holding the sub-pages of plan §4.7, populated by a `YellowbackController` that issues `yed_*` calls through the existing `Connection::doRPCWithDefaultErrorHandling` (`src/connection.h:100-104`); no new transport, no new dependency |
| Widgets refresh on wallet signals (`NotifyTransactionChanged`, `numBlocksChanged`) | `Controller::getInfoThenRefresh` polls `getinfo` every `Settings::updateSpeed` and refreshes everything when `blocks` changes (`controller.cpp:38-43,247-280`) | Hook the Yellowback refresh into the same "block changed" branch (`yed_getinfo` → `yed_getstats`, `yed_getbalance`, `yed_listpositions`, `yed_listtransactions`); pending redemptions poll on `txTimer` like `watchTxStatus` (`controller.cpp:45-50`) |
| Mint/Send/Redeem call the wallet directly (`DigiDollarWallet::CreateMintTransaction` etc.) | Sends go `sendtab.cpp` → `doSendTxValidations` → `Controller::executeTransaction` → `z_sendmany` (`sendtab.cpp:661-701`, `controller.cpp:587-607`), with a confirm dialog (`src/confirm.ui`) | `yed_mint`, `yed_send`, `yed_redeem`/`yed_submitredeem` follow the same validate → confirm → RPC → watch pattern; the node builds and signs, the wallet never touches keys |
| Coin-control dialog for DD outputs (`digidollarcoincontroldialog.cpp`) | no coin control anywhere in YecWallet | dropped (node selects inputs smallest-first, confirmed-only; plan §4.5) |
| Positions/redeem read vault state from wallet DB tables (`digidollarwallet.cpp`) | no wallet tables; `DataModel` holds RPC snapshots (`src/datamodel.h:7-17`) | `yed_listpositions` / `yed_getvault` into a `YellowbackPositionsModel : QAbstractTableModel` (pattern: `src/txtablemodel.h`, `balancestablemodel.h`) |
| Node started by the same process with its own option model | YecWallet launches the bundled `ycashd` with **no arguments**; every setting comes from the `ycash.conf` it writes (`server=1`, `addnode`, `rpcuser`, `rpcpassword`, optional `fastsync`/`datadir`/`proxy`; `connection.cpp:189-209`) | `createZcashConf` also writes `experimentalfeatures=1` and `yellowback=1`; for an existing conf the wallet detects `yed_getinfo` → "Method not found" and offers to append the two lines (plan §4.7 Settings row) |
| Oracle/co-sign traffic handled in the node (`src/oracle/`) | YecWallet's only network client is the RPC `QNetworkAccessManager` (`Connection::client`, `connection.cpp:221`) plus HTTPS calls it already makes (price fetch and release check, `controller.cpp:685,757`); the static Qt links OpenSSL statically (`scripts/build-qt.sh:147-159`) | The redemption wizard reuses that `QNetworkAccessManager` for HTTPS POSTs to the operators' `/cosign` endpoints — the one screen that talks to anything but the local node (plan §4.7) |
| Qt 5 widgets in Bitcoin Core's build, with the node's test framework | Qt **6.5.8** built statically by `build.sh` (`build.sh:57`) **with `-no-feature-testlib`** (`scripts/build-qt.sh:129`), CMake source list in `CMakeLists.txt:68-92`, `.ui` files under `src/`; no test target at all | New sources are appended to the CMake list; `.ui` files use the existing `uic` step; the QTest target is an `OPTIONAL_COMPONENTS Test` (pattern of `CMakeLists.txt:53`) built only against a system Qt 6 in development/CI, never in the static release build (plan H1) |
| GUI tests attach to a regtest node through the test harness | Stock `--conf <file> --no-embedded` already attach the wallet to any node whose conf has `rpcuser`/`rpcpassword`/`rpcport` (`src/main.cpp:168-172`, `connection.cpp:647-673`); network is taken from `getinfo.testnet`, `false` on regtest (`controller.cpp:255-257`) | No new options; the Yellowback tab reads `yed_getinfo.network` for address prefixes (plan H2, H3) |
| Release bundles the node in the same binary | YecWallet looks for `ycashd` (Linux: `zqw-ycashd` then `ycashd`) beside its executable (`connection.cpp:348-364`) | Releases of `yecwallet-dd` ship the `ycash-dd` build of `ycashd`; the wallet checks `yed_getinfo.rpcversion` and refuses a node it does not know |

### Rows added while building Phases 2–5 (2026-09-05)

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| Volatility protection compares timestamped oracle prices with a standard deviation (`src/consensus/volatility.cpp`) | The overlay has only heights and the `Prices` table; §3.6 compares `price(H)` with `price(H − 48)` and `price(H − 96)` and a window with no price is not evaluated | A step change made before the windows hold any price breaches only when its echo reaches the windows; a step change re-breaches every block until `price(H − 48)` reads the new level, so the last breach is at `H + 47` and the freeze ends at `H + 47 + VOL_COOLDOWN`. Tests settle both windows before asserting on a spike (`yellowback_protection.py`) |
| `bitcoin.conf`/`digibyte.conf` and `bitcoind`/`digibyted` names match the daemon in the test runner | `qa/pull-tester/rpc-tests.py:262` set `BITCOIND` to `src/zcashd`; the binary is `src/ycashd` | One-line runner fix beside the G1 `ycash.conf` fix; the functional suite cannot start without both |
| Test framework runs on the platform's Python | `test_framework/mininode.py` imports `asyncore` (removed in Python 3.12) and `pyblake2` (unmaintained C extension) | The workspace venv carries `pyasyncore` and a one-line `pyblake2` shim over `hashlib.blake2b`; no framework file changed |
| `CScript` in Core's test framework appends scripts with `+` | Ycash's `test_framework/script.py` coerces a `CScript` operand of `+` to a data push (`__coerce_instance`, `isinstance(other, bytes)`) | Concatenate raw bytes when composing the vault script in Python (`yellowback_util.build_mint_tx`) |
| `invalidateblock` tests wait on the node's own notification | `getblockchaininfo.fullyNotified` covers connects only; a disconnect is delivered on the next notifier cycle without bumping the sequence | `yellowback_util.wait_yed_synced` polls `yed_getinfo.synced` after `invalidateblock` |

### Rows added while building the wallet tab (Phase 5b, 2026-09-05)

| DigiByte does X (Y, mechanism M) | YecWallet equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| `DigiDollarTab` builds seven widgets in code and switches a `QStackedWidget` to an "activation" label polled every 5 s (`ref/digibyte/src/qt/digidollartab.cpp:100-130`) | YecWallet tabs are `.ui` forms filled by `Controller` on the 20-s `getinfo` cycle (`ref/yecwallet/src/mainwindow.ui:23`, `controller.cpp:38-43`) | one `.ui` per sub-page under `yecwallet-dd/src/yellowback*.ui`; availability is a banner driven by `YellowbackController::availabilityChanged`, refreshed on the block-changed branch, not a separate timer |
| Console tab re-added by index: `Controller::setEZcashd` tests `ui->tabWidget->widget(4) == nullptr` (`ref/yecwallet/src/controller.cpp:80-82`) | — | the Yellowback tab takes index 4, so the test becomes `indexOf(main->zcashdtab) == -1`; any further tab must use `indexOf`, never a literal index |
| DD mint widget gates on `WalletModel` balance and in-process oracle state (`digidollarmintwidget.cpp`) | no wallet objects; YEC balance is `DataModel::getAllBalances()` (`ref/yecwallet/src/datamodel.h`) summed over `Settings::isTAddress` | gate reasons come from cached `yed_getstats`/`yed_getinfo`; the collateral figure is always `yed_estimatecollateral`, debounced, and Mint is enabled only when the estimate matches the typed amount |
| DD redeem widget signs and broadcasts in-process | `Controller::watchTxStatus` polls on `txTimer` at `Settings::quickUpdateSpeed` = **5 s** (`ref/yecwallet/src/settings.h:125`), not 1 s as plan H4 says | pending redemptions ride the same timer (`YellowbackController::watchPending()`); the wizard's own countdown is a 1-s `QTimer`. Plan H4's "1-second mode" is really the 5-second quick mode |
| DD widgets prompt with `QMessageBox` | `MainWindow::backupWalletDat` is private, reachable only through `ui->actionBackup_wallet_dat` (`ref/yecwallet/src/mainwindow.cpp:102`) | the tab triggers that `QAction` instead of adding a public method; the backup-nag state persists in `QSettings` |

Rules for `yecwallet-dd`, mirroring rules 2, 6 and 7 for the node: work only on `feature/yellowback-sf`
off `yecwallet-legacy`; naming follows AGENTS.md rule 6 (Yellowback for the system, YED for amounts, `yed_*` RPCs); do not restructure `Controller`, `Connection` or
`MainWindow` while adding the tab — add files, append to lists, hook into the two existing refresh
branches, and keep `git diff yecwallet-legacy...feature/yellowback-sf` reviewable.

### Rows added while building Phase 7b-b (2026-09-10, `feature/yellowback-sf`)

| DigiByte does X (Y, mechanism M) | YecWallet equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| DD's Qt tests drive widgets against an in-process `WalletModel` fixture (`ref/digibyte/src/qt/test/`) | every wallet RPC goes through `Connection::doRPCSafe`, which first calls `getrescaninfo` and then dereferences `this->main->getRPC()` (`ref/yecwallet/src/connection.cpp:763-790`) — a QTest has no `MainWindow`, so no `Connection` can be constructed for it | `YellowbackController::setTransport()` (the "fake Connection" of plan N28): when set, `call()` hands `(method, params, ok, err)` to it; the offline cases answer from a per-method table of contract example values and error identifiers, the devnet case posts JSON-RPC to node 0 through its own `QNetworkAccessManager` + `QEventLoop` (`yecwallet-dd/tests/yellowbacktab_test.cpp`, `DevnetTransport`) |
| DD confirmations are `QMessageBox` calls inside the widget (`digidollarmintwidget.cpp`) and are not exercised by tests | same pattern in `yellowbacktab.cpp`; a modal box blocks an offscreen QTest | `YellowbackTab::confirmFn` / `noticeFn` (`std::function`, defaulting to `QMessageBox`); the QTest replaces them to read the copy (the §8.1 check `copyIsClean`) and answer |
| — | `QObject::findChild<T>(name)` searches the whole tab: the Send and Mint pages both carry a `txtAmount`, and the Overview and the Mint page both carried a `lblMintStatus` (7b-a's cases found the Overview's by child order alone) | look-ups in the QTest are scoped to `YellowbackTab::page(Page)`; the Mint page's label is `lblMintPageStatus` |
| — | plan §4.8 says the devnet case "loads its `state.json` for the RPC port and credentials"; the devnet writes `devnet.json` (`ycash-dd/contrib/yellowback/devnet/yellowback-devnet:33`) with the port seed only, no credentials | the case reads `rpcuser`, `rpcpassword`, `rpcport` from `<YELLOWBACK_DEVNET_DIR>/node0/ycash.conf` — the same file the GUI reads through `--conf` (`ref/yecwallet/src/connection.cpp:647-673`) |
| — | the contract's `change-floor` message "names the nearest workable amounts" (structured only by H2 in Phase 8); the node at Phase 6's first commit still emits the prototype's sentence `change of N cents is below the minimum output … (C20); send A cents (all selected inputs) or at most B cents` (`ycash-dd/src/yellowback/txbuilder.cpp:229`) | `YellowbackController::parseChangeFloor` takes the two figures from either wording (`send (\d+) cents … or at most (\d+) cents`); the Send page matches the `change-floor` identifier or `(C20)` and offers both amounts |
| — | `ycash-dd/src/yellowback/txbuilder.cpp:381` refuses every non-ACTIVE vault with `vault-not-active`, so the wallet's Release (VOID, L14) fails against the node until Phase 6 applies L14 | the wallet codes to the contract (`yed_redeem` on VOID = release, `burnedCents = 0`) and shows the identifier verbatim with its meaning; nothing to change on the wallet side once the node follows the contract |
| — | the bundled `nlohmann::json` (`src/3rdparty`) predates `json::contains()` | `find() != end()` throughout, as `connection.cpp` already does |

### Rows added while running the devnet QTest against the finished node (2026-09-11)

| DigiByte does X (Y, mechanism M) | YecWallet / Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| DD's Qt tests drive an in-process node whose block-connect and wallet update are one call, so a test may build a transaction the instant a block lands | Ycash updates the wallet on its own thread after `UpdateTip`: `getblockcount` rises about a second before `AddToWallet <txid> update` marks the block's inputs spent (`ycash-dd/src/main.cpp`, the `SyncWithWallets` path). A GUI test that builds its next transaction on the height alone selects an input the block already spent and the node answers `AcceptToMemoryPool: inputs already spent` | `DevnetTransport::settle(txid)` in `yecwallet-dd/tests/yellowbacktab_test.cpp`: an empty mempool, `yed_getinfo.height == chainHeight == getblockcount`, and a confirmation for `txid` in `gettransaction` — the wallet's own view, which is the only one of the three that actually moves when the wallet catches up. `yed_getinfo` has no `synced` field; `height == chainHeight` is the index's |
| DD's GUI tests mine in-process, so a transaction is always in the miner's mempool | The devnet's pools are separate `ycashd` processes: a transaction node 0 broadcast reaches pool node 2 over p2p, and a `generate` issued before it arrives mines a block without it | the QTest waits for the txid in the mining pool's `getrawmempool` before it mines (`waitForTx`), and mines one block at a time round-robin, waiting for node 0 to see each — two pools generating from the same height fork the devnet |
| — | untagged blocks are not free in a GUI test: `devnetEndToEnd` mines ~48 of them on node 0 to reach a lock height, which drops the trailing signal count under the mint floor, so the next case's first `yed_mint` fails `mintpol-participation` | the claim/sweep case mines pool blocks until `mintBlocker` clears **and then `REF_LAG + 1` more**: MINTPOL-1 is read at the mint's reference height, not at the tip, so a recovered tip is not yet a recovered reference height |
| DD ships its GUI and node in one binary, so a headless CI run uses the same Qt as the tests | `build.sh` links Qt 6.5.8 statically with only the cocoa platform plugin (`yecwallet-dd/scripts/build-qt.sh`), so the **release** binary cannot run under `QT_QPA_PLATFORM=offscreen` ("Could not find the Qt platform plugin") | the offscreen QTest target builds against the system Qt (mapping §12, plan H1); the release bundle is exercised by launching it on a real display. A headless host can check that it starts and holds its RPC connections (`lsof -iTCP` to the node's `rpcport`), not what its widgets show |

## 13. Rows added while planning v2 — miner-enforced Yellowback (2026-09-10)

All cites at the pinned tags. Rationale and the resulting design live in
[`plans/yellowback-v2-development-plan.md`](plans/yellowback-v2-development-plan.md) (decision
identifiers V1–V26 there).

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| Embeds the oracle price bundle as an extra zero-value coinbase output `OP_RETURN OP_ORACLE <v3 data>` appended after the witness commitment (`ref/digibyte/src/oracle/bundle_manager.cpp:815-828, 891-940`; `node/miner.cpp:535-538`) | The coinbase output layout is fixed by founders'/YDF/funding-stream rules and `getblocktemplate` reads `vout[1]` as `foundersreward` (`ref/ycash/src/rpc/mining.cpp:733`); the coinbase **scriptSig** is bounded to 2..100 bytes (`main.cpp:1456-1458`) and only its BIP34 height prefix is checked (`main.cpp:4477-4481`) | A 36-byte tag pushed into the scriptSig after the height, carried by `COINBASE_FLAGS` — declared but never assigned (`main.cpp:134`, `main.h:163`), appended by `IncrementExtraNonce` (`miner.cpp:720`) and serialised by GBT (`rpc/mining.cpp:742`); read by a byte-level scan (plan V4, V5, §3.2) |
| `IncrementExtraNonce` is only the internal miner's business | `IncrementExtraNonce` **replaces** the whole coinbase scriptSig (`ref/ycash/src/miner.cpp:720`) and is on the path of regtest `generate` (`rpc/mining.cpp:222`) and the unit-test harness (`test/test_bitcoin.cpp:167`); `CreateCoinbaseTransaction` sets `<< nHeight << OP_0` without the flags (`miner.cpp:327`) | Put the tag in `COINBASE_FLAGS` so it survives every path; append `COINBASE_FLAGS` at `miner.cpp:327` so `coinbasetxn` matches (V5) |
| The consensus price is the single price in the block's own bundle, verified by 7-of-35 MuSig2 with epoch binding (`ref/digibyte/src/validation.cpp:3110-3126`; `oracle/bundle_manager.cpp:2480-2597`), fail closed (`digidollar/validation.cpp:1145-1149`) | No signed bundle, no MuSig2 (§7 above) | Three rolling lower medians (96/576/2,016 blocks) over tagged blocks, `P_mint = min`, `P_claim = max(mid, slow)`, undefined below half fill ⇒ minting halts (plan §3.7, V16) |
| Miners are anonymous carriers; no per-miner identity, penalty or reward (grep of `src/oracle`, `src/digidollar`, `src/consensus`: none) | — | The tag carries a payout key; registration for `N_REG` blocks, peer-median penalties, accuracy-weighted enforcement fees (plan REG-1..4, FEE-2) |
| DigiDollar activated by a buried BIP9 bit-23 deployment (`ref/digibyte/src/kernel/chainparams.cpp:174-188`; `DeploymentActiveAt`) | No versionbits (§4 above) | Overlay activation state machine from tag signal bits: 75 % of 2,016 ⇒ lock-in, +2,016 ⇒ active, < 60 % ⇒ minting halt (back at 75 %), < 50 % ⇒ block rejection suspends (back at 60 %), both with hysteresis (plan ACT-1..6, V12, L3); enforcement at `H` reads `Snapshots[H−1]` |
| Invalid DD transactions are rejected in `ConnectBlock` with DoS 100 and the relaying peer is scored | `InvalidBlockFound` calls `Misbehaving` only when `nDoS > 0` (`ref/ycash/src/main.cpp:2304-2305`) while still marking `BLOCK_FAILED_VALID` (`:2308-2312`); most peers of an enforcing node are unpatched | The block-validity hook returns `state.DoS(0, …, REJECT_INVALID, "yellowback-vault-spend")` from the window between `control.Wait()` and `if (fJustCheck)` (`main.cpp:3187-3193`); rejected hashes are recorded; `ReconsiderBlock` (`main.cpp:3970-3999`, public via `main.h:557`) un-rejects them on `-yellowbackenforce=0` (plan V1, V13) |
| DD state is consensus state written in the chainstate flush | The chainstate flushes lazily — `FLUSH_STATE_IF_NEEDED` writes only when the coin cache is full (`ref/ycash/src/main.cpp:3324-3334`), periodic full flush every 24 h (`main.h:108`) — so a per-block overlay LevelDB is ahead of the chainstate after a crash | Keep per-block commits; `SyncToChain` undo-walks while the stored tip is not in `chainActive`; `UNDO_KEEP = 4,096`; wipe-and-rebuild beyond (plan V2) |
| Index updates are symmetric in `ConnectBlock`/`DisconnectBlock` | Ycash's atomic-swap hooks are split between `ConnectBlock` (`main.cpp:3111`, runs even under `fJustCheck`) and `DisconnectTip` (`:3555`, skipped for `fBare`), and `UpdateTip`'s hook is skipped during IBD (`:3483`); `DisconnectBlock` is `static` with an `updateIndices` parameter, `true` from `DisconnectTip` (`:3541`), `false` from `VerifyDB` level 3 (`:5133`) — there is no `pfClean` in v4.5.0 | Check in `ConnectBlock`'s window, commit after `if (fJustCheck) return true;` (`:3193-3194`), undo at the end of `DisconnectBlock` inside `if (updateIndices)`, both guarded by tip equality (plan V2, §4.3) |
| `BlockAssembler` filters packages; the oracle output is added after `GenerateCoinbaseCommitment` | `CreateNewBlock`'s priority loop calls `UpdateCoins` (`ref/ycash/src/miner.cpp:582`) as it accepts each transaction and ends with `TestBlockValidity` (`:660`) | Template filter as a `continue` immediately before `UpdateCoins`, over an `OverlayStateView` applied in template order (plan TPL-1..3) |
| GBT returns `coinbaseaux` and `coinbasevalue` per BIP 22 | `coinbasetxn` is hard-coded true (`ref/ycash/src/rpc/mining.cpp:504-505`) so the `coinbaseaux`/`coinbasevalue` branch is dead (`:762-767`); `mutable` is `["time","transactions","prevblock"]` (`:747-752`) | Emit `coinbaseaux.flags` always, add `"coinbase/append"`, add a `yellowback` object (plan V26) |
| Volatility is 2σ of consecutive samples of a wall-clock price history kept in a process-global monitor (`ref/digibyte/src/consensus/volatility.cpp:212-251, 635-661`) and read inside consensus validation (`digidollar/validation.cpp:1153-1161`) | No such history; the overlay has only snapshots | σ from the `P_fast` snapshot series every 48 blocks over 2,016, integer bps, annualised, capped at 3×; a pure function of the chain (plan V17) |
| Vault spend paths are tapleaves | No Taproot; P2SH only; no `MINIMALIF` flag (`ref/ycash/src/script/interpreter.h:80-88`); `CLEANSTACK` and `MINIMALDATA` in `STANDARD_SCRIPT_VERIFY_FLAGS` (`policy/policy.h:32-40`) | `OP_IF <lock> CLTV DROP <owner> CHECKSIG OP_ELSE <claim> CLTV DROP OP_TRUE OP_ENDIF`; scriptSigs `<sig> OP_1 <script>` / `OP_0 <script>`; both leave one element (plan V7, §3.4) |
| The fee payee is implicit (the miner of the block) | An overlay transaction's block is unknown when it is built; a txid-derived selector is circular (the fee output is part of the txid) | Validity: the fee pays any pool that quoted in the 100 heights up to and including `refHeight` (`E(R)`, FEE-2); the wallet's default pick is `SHA256(blockHash(refHeight) ‖ selector)` over those blocks, accuracy-weighted (FEE-W, policy) (plan V10, L1) |
| A consensus rule needs no work valve: every node applies it, so a node can never be on the minority side of its own rule (`ref/digibyte/src/validation.cpp` rejects and never reconsiders) | A rule enforced by a subset of nodes reads its own chain for the signal count (ACT-6), so after a split the enforcers' branch always looks 100 % signalling and the suspension can never rescue them; `pindexBestInvalid` is in `main.cpp`'s anonymous namespace (`ref/ycash/src/main.cpp:139-285`, `:202`) and cannot grow from headers the node refuses at `AcceptBlockHeader` (`:4553-4558`); the headers handler stops at the first refused header (`:6604-6610`) | The work valve (plan ACT-7, L7): the `AcceptBlockHeader` clause that answers descendants of a rejected block at DoS 0 (`bad-prevblk-yellowback`) also notes their accumulated work; at `VALVE_BLOCKS = 6` blocks of proof above the tip the index clears enforcement for the session, reconsiders the rejected blocks under the `cs_main` it holds, and the next stock block (direct fetch on `inv`, `:6281-6286`) triggers the reorg; re-armed by restart. No equivalent exists in DigiByte because none is needed by a consensus rule |
| A consensus rule has no sunset: it is in force until the next network upgrade replaces it | Parameter sets among a subset of enforcers have no mechanism to retire a stale release — a pool on an old release keeps enforcing the old set past the new set's start and splits on the first disagreement; Ycash's own upgrades are height-gated network upgrades that change the branch ID (§4 above) | `ENFORCE_UNTIL_HEIGHT` per network per release (plan L8, ACT-5): ≈ `startHeight + 420,480`, never beyond the next known Ycash upgrade height; past it the node tags and accounts but rejects nothing; the next set starts at or after the previous sunset; the fork commits to a release within 14 days of every Ycash release (plan §11). DigiByte needs none: enshrinement makes the upgrade height the sunset |
| Initial block download in Bitcoin-Core-lineage code compares the tip with the best known header (`chainActive.Height() < pindexBestHeader->nHeight - 24*6`) as well as the tip's age | Ycash 4.5's `IsInitialBlockDownload` (`ref/ycash/src/main.cpp:2106-2178`) tests `fImporting || fReindex`, a null tip, `nMinimumChainWork`, the upgrade activation hashes and **only the tip's age** (`nMaxTipAge`, 24 h, `:2174`); once false it latches false for the process (`:2107-2112`) | A subset-enforced rule that suppresses rejection "during IBD" covers only a node restarted after more than a day offline; a node behind by hours, or partitioned without a restart, evaluates on catch-up. Plan BLK-2 clause 3 (L11): a block that `pindexBestHeader` (`main.h:209`) already descends from by `VALVE_BLOCKS` of work is accepted, not rejected |
| `pindexBestInvalid` and the "invalid chain ~6 blocks longer" warning track any invalid chain the node knows headers for | `pindexBestInvalid` grows only from *indexed* blocks (`InvalidChainFound`, `ref/ycash/src/main.cpp:2280-2283`; `FindMostWorkChain`, `:3716-3717`); `AcceptBlockHeader` refuses a header whose parent is marked failed (`:4557-4558`), so descendants of a live rejection are never indexed and `CheckForkWarningConditions` (`:2197`) never fires for them; descendants indexed *before* the rejection are marked `BLOCK_FAILED_CHILD` (`:3722`) | The valve keeps its own odometer from the refused headers (plan ACT-7) and raises its own warning through `SetMiscWarning` (`warnings.cpp:22`) and `CAlert::Notify` (`alert.h:107`) (plan P1); `IsRejectedAncestor` walks through `_CHILD` marks so a catch-up rejection trips at the next header (L11); the clause runs before `ContextualCheckBlockHeader` checks `nBits` (`:4561`, `:4392`), so noted headers are bounded by the consensus difficulty loosening and a per-root cap (plan P2) |
| DigiByte's RPC layer declares every command's result as a typed `RPCResult` tree inside `RPCHelpMan` (`ref/digibyte/src/rpc/util.h:283,405`), so a machine-readable result contract can be rendered from the binary itself | Ycash 4.5 commands are `rpcfn_type` = `UniValue(*)(const UniValue& params, bool fHelp)` (`ref/ycash/src/rpc/server.h:123,130`); the help is a free-form string thrown on `fHelp` (`ref/ycash/src/rpc/misc.cpp:47`) and nothing types the `UniValue` result | **The contract is the document** (plan P7): `scripts/extract-spec.sh` (`make spec`) derives `yellowback-rpc-contract.json` from the plan's §4.5 — whose return shapes are prose braces, parsed deterministically (format in the header of `scripts/extract_spec.py`) — and, from Phase 3, from the fenced ```json blocks of `ycash-dd/doc/yellowback-rpc.md`, which override per command; `yellowback_rpc_contract.py` then checks the binary against the document, never the reverse; the plan's §4.5 heading supplies `rpcversion` |
| DigiByte's regtest founders/dev-fund addresses are defined for every height | A stock Ycash v4.5.0 regtest node that activates no network upgrade aborts in `CChainParams::GetFoundersRewardAddressAtHeight` when `getblocktemplate` is called (SIGABRT; reproduced at the pin with `ycash-legacy`-identical `main.cpp`/`miner.cpp`/`rpc/mining.cpp`/`chainparams.cpp`), so the inherited `getblocktemplate_proposals`, `getblocktemplate_longpoll` and `invalidateblock` scripts fail at the pin; `p2p-acceptblock` fails at the pin too ("Unrequested block from whitelisted peer not accepted") | The CI stock baseline (`STOCK_BASELINE` in `ycash-dd/.github/workflows/yellowback-tests.yml`) is the seven inherited scripts that pass at the pin; the Yellowback scripts pass six `-nuparams` at height 1 and never hit the assert (Phase 0, 2026-09-10) |
| The DigiByte test framework signs SegWit/Taproot sighashes | `ref/ycash/qa/rpc-tests/test_framework/script.py:926` packs ZIP-243 `valueBalance` as `<Q` (unsigned), so a Sapling-output transaction (negative `valueBalance`) raises `struct.error` in Python-side signing | One-character framework fix in the fork (`<q`, matching `mininode.py`); `build_vault_spend_raw` (Phase 3+) relies on it (Phase 0, 2026-09-10) |

### 13.1 Rows added while building Phase 1 (2026-09-10, `feature/yellowback-sf-p1`)

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| The oracle output is a script the node parses (`OP_RETURN OP_ORACLE <data>`, `ref/digibyte/src/oracle/bundle_manager.cpp:891-940`), so push encoding is checked by the script parser | The tag reader is a byte-level scan of the coinbase scriptSig (plan TAG-1, V4), never a script parse | The 5-byte pattern `24 59 45 44 21` also occurs at offset 1 of a **non-minimal** `OP_PUSHDATA1` push of the tag (`4c 24 59 45 44 21 …`), so a tag pushed that way is found too; only the bare magic without the `0x24` byte is "no tag" (P10). Pinned by `tag1_magic_without_push_opcode_is_no_tag` (`ycash-dd/src/test/yellowback_tag_tests.cpp`) |
| Fuzz corpora are ordinary tracked files (`ref/digibyte/src/test/fuzz/…`) | `ref/ycash/.gitignore:122` ignores `src/fuzzing/*/input`; upstream's own seeds (`src/fuzzing/CheckBlock/input/0.bin`) are force-added | `git add -f src/fuzzing/<Target>/input` after `gen_yellowback_corpus.py --write`; `--check` catches a corpus that was written but not added |
| Tapscript leaves need no selector; `OP_IF` under BIP342 has `MINIMALIF` (`ref/digibyte/src/script/interpreter.cpp`, `SCRIPT_VERIFY_MINIMALIF`) | No `MINIMALIF` (`ref/ycash/src/script/interpreter.h:80-88`); `MINIMALDATA` polices only the *push* encoding (`CheckMinimalPush`, `interpreter.cpp`: 1-byte pushes of 1..16 and 0x81 must be `OP_N`/`OP_1NEGATE`), never the numeric form of an `OP_IF` operand | Under `STANDARD_SCRIPT_VERIFY_FLAGS`: `OP_2` and a two-byte zero `00 00` are valid selectors (owner / claim); a non-minimal `01 01` fails `MINIMALDATA` but is consensus-valid (P2SH \| CLTV). `ParseVaultSpendPath` = `CastToBool(selector)` (K4); `<sig> OP_0 <script>` at `claimHeight` fails `CLEANSTACK` under standard flags yet is consensus-valid. All pinned in `yellowback_script_tests.cpp` (`red1_owner_path_verifies`, `red4_claim_path_verifies`) |
| — | The prototype's `RequiredCollateral(cents, ratioPct, dcaBps, price)` / `RequiredCollateralRounded(…)` stay beside the v2 `(cents, minRatioBps, pMint[, granularity])` until Phase 2 (§6 preamble) | Overload hazard: a call with four `int` literals resolves to the **v1** overload (exact match on the third argument); pass typed `Cents`/`MicroUsd`/`CAmount` or three arguments. Phase 2 deletes the v1 overloads and the hazard |
| `DecodePayload` is one codec with one version | `state.cpp`, `txbuilder.cpp` and the prototype's state tests still build version-1 payloads (incl. PRICE `0x10`) until Phase 2 | Transitional deviation from V23: `DecodePayload` keeps a `version == 1` branch (`payload.cpp`, `DecodeBodyV1`) and `Payload::version` selects the layout; `v1_retained_codec` pins the behaviour so its removal in Phase 2 is a visible change; `payload_corpus_replay`'s decoded count drops from 10 to 9 then |
| The vault spend signature is BIP341 (`SigVersion::TAPROOT`) over the prevout amounts | ZIP-243 `SignatureHash(scriptCode, tx, nIn, nHashType, amount, consensusBranchId)` (`ref/ycash/src/script/interpreter.cpp`) binds the input amount **and** the epoch branch id | The owner signature is over the vault script with the vault's `nValue` and `CurrentEpochBranchId(nextHeight)`; a signature made under Sapling's branch id is invalid under Overwinter's and vice versa, and a wrong amount invalidates it (`red1_owner_path_verifies`). Phase 6 must sign with the branch id of the block the spend will confirm in (`SignerBranchId`) |
| — | `chainparams.h` declares `const CChainParams& Params()`; the overlay has `yellowback::Params` | With `using namespace yellowback` in a test that includes `chainparams.h`, `Params` is ambiguous — write `yellowback::Params` (or `const yellowback::Params&`) |
| Fuzz builds use libFuzzer via `-fsanitize=fuzzer` on any recent clang | Apple clang (Xcode 17) does not ship the libFuzzer runtime; Ycash's `--enable-fuzz-main` build needs a Homebrew LLVM (`brew install llvm`, `CC=/opt/homebrew/opt/llvm/bin/clang`) on macOS | Phase 1's 10-minute `YellowbackTag`/`YellowbackPayload` runs were not run on the 2026-09-10 macOS host; the `nightly` CI job (Linux clang) is where they run. The Boost replay cases cover the corpora in every build |

### 13.2 Rows added while building the v2 Python test framework (2026-09-10, `feature/yellowback-sf-pyfw`)

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| DigiByte's functional tests run on Bitcoin Core's `asyncio`-based P2P framework (`ref/digibyte/test/functional/test_framework/p2p.py`) | `ref/ycash/qa/rpc-tests/test_framework/mininode.py:27` imports `asyncore`, removed from the standard library in Python 3.12; the workspace venv is Python 3.13 | `mininode` imports only because the venv carries the `asyncore` backport package (`.venv/lib/python3.13/site-packages/asyncore`). `yellowback_model.py` avoids `mininode` altogether; `yellowback_util.py` imports it lazily inside `build_vault_spend_raw`/`mine_block_raw` (`CTransaction`, `CBlock`) so the module and its constants import without it. A CI Python without the backport needs `pip install asyncore` (or a Python ≤ 3.11) for those two helpers only |
| Blocks in tests are solved by the framework's `solve()` (SHA-256d, trivial on regtest) | Regtest Equihash n=48, k=5 (`ref/ycash/src/chainparams.cpp`); `mininode.CBlock.solve()` (`:919-936`) runs the pure-Python Wagner solver `equihash.gbp_basic` — seconds per block — and `getblocktemplate` refuses without a peer or during IBD (`ref/ycash/src/rpc/mining.cpp:556-559`) | `mine_block_raw(node, txs)` takes the header fields and `coinbasetxn.data` from `getblocktemplate` (`coinbasetxn` is always present, `:504-505`), subtracts the template's own fees from `coinbase.vout[0]` so the coinbase claims the subsidy alone (`bad-cb-amount` polices only an excess), solves with `CBlock.solve()`, and calls `submitblock`; a caller edits the coinbase from `template_coinbase(node)` for a forged tag or a wrong subsidy. Precondition: one fresh block on the node (P12) |
| The framework's cached chain is reused by every test | `initialize_chain` builds the 200-block cache with Overwinter and Sapling only (`ref/ycash/qa/rpc-tests/test_framework/util.py:262-268`); a node started on it with Heartwood at height 1 aborts in `LoadBlockIndex` ("block index inconsistency detected (post-Heartwood; hashLightClientRoot … != hashChainHistoryRoot 0…)") | `YellowbackTestFramework` sets `setup_clean_chain = True` and node 0 mines `initial_blocks = 101` from genesis in `setup_network` (the v1 scripts did the same by hand). Plan §6.0's "every node starts in IBD until the first fresh block" still holds — the fresh chain's genesis is older than `nMaxTipAge` — but the IBD ends at that first mined block, before `run_test` |
| — | The plan's six-node topology (§6.0 item 4: a star on node 1 plus 2↔3↔4) gives node 0 a single edge, to node 1, so `split_network()`'s `{1, 5}` vs `{0, 2, 3, 4}` isolates node 0 | One extra edge 0↔2 in `YellowbackTestFramework.EDGES`; node 0 still receives node 1's blocks through the star, and the enforcing half is connected while split |
| — | `wait_bitcoinds()` (`util.py:438`) waits for *every* process in `bitcoind_processes`, so the plan's `kill9` recipe (`os.kill(…); del bitcoind_processes[i]; wait_bitcoinds()`) would block on the five live nodes | `kill9(i)` pops the process, `SIGKILL`s it and `wait()`s that process alone; `self.nodes[i]` becomes `None` until `restart(i)` |
| `signrawtransaction` solves every standard input; DigiByte's tests sign Tapscript spends with `test_framework/script.py`'s Taproot helpers | Ycash's `signrawtransaction` cannot solve the `OP_IF` vault script (records "Input not found"/unsolvable and continues); the ZIP-243 sighash (`test_framework/script.py:871`) covers `hashPrevouts`/`hashSequence`/`hashOutputs` but no other input's `scriptSig` | `build_vault_spend_raw` lets the wallet sign the YED burn inputs first, then computes the owner signature in Python (`CECKey`, compressed, low-S) over the same transaction and sets `vin[0].scriptSig`; the two steps commute |
| — | The Phase 1 binary still requires the federation genesis arguments with regtest `-yellowback` (`src/yellowback/index.cpp:298`), so the v2 flags cannot start it | `YellowbackTestFramework.yellowback_enabled = False` starts all six as stock nodes (the framework smoke test); `yellowback_node_args(genesis=…)` keeps the v1 shape for the not-yet-rewritten scripts. Both go at Phase 6 |

### 13.3 Rows added while building Phase 2 (2026-09-10, `feature/yellowback-sf`)

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| DigiDollar state is consensus state; there is no cross-implementation hash to agree on | The overlay's state hash (plan §3.6, N18) is compared between the C++ index and the Python model; `uint256::GetHex()` renders bytes **reversed** (`ref/ycash/src/uint256.h`, `base_blob::GetHex`), while `hashlib.sha256().hexdigest()` is the natural digest order | `StateHash` stores the digest reversed into the `uint256` so `GetHex()` — what `yed_getstatehash` prints and what `statehash_golden_vector` pins — equals the model's hex (`ycash-dd/src/yellowback/view.cpp`). The preimage itself is key ‖ value per table in the §3.6 order with **no length prefixes** (the prototype hashed `len ‖ key ‖ len ‖ value` over every key in byte order; SERIALISATION.md §1 is the reference) |
| Records exist from genesis (the DigiDollar tables are part of the chainstate) | The model always hashes `Activation`, `Totals` and `Params` even when no transaction or tag touched them; a LevelDB overlay has no record until something writes it | `EvaluateBlock` writes `Params`, `Totals` and `Activation` at the first applied block when absent, so the hash of any state with ≥ 1 applied block agrees; an empty index hashes `Tip = {0, zero hash, 2, network}` and no `P` record (the functional tests never hash that state, SERIALISATION.md §1) |
| DigiDollar's mint validation rejects a malformed key at the transaction level (consensus) | §3.3 lists what makes a payload malformed and the owner key is not among it; MINT-3 owns key validity (`bad-mint-owner-key`) and a VOID vault records the 33 payload bytes verbatim (SERIALISATION.md §3 C), but `CPubKey::Set` invalidates any 33 bytes whose first byte is not `0x02`/`0x03` (`ref/ycash/src/pubkey.h`, `GetLen`), so a `CPubKey` cannot carry them | `Payload::ownerKeyBytes` carries the raw 33 bytes beside the `CPubKey`; the codec accepts any 33 bytes (Phase 1's `mint_key_prefix_04`/`_01` cases flipped to "decodes"); `VaultRecord::ownerPubKey` is a `std::vector<unsigned char>` (serialises exactly as a valid `CPubKey` does: CompactSize ‖ bytes) with `OwnerKey()` for callers that need a key |
| Consensus validation reads the UTXO set once per input | The prototype's `RequiredCollateral` took `int` literals; Phase 1 kept the v1 4-arg overload beside v2 (mapping §13.1) | Phase 2 deleted the v1 overloads, the tier tables, `PRICE_MAX_AGE`, `HEALTH_CAP`, `VOL_*`, `RED_SKEW`, `NUM_TIERS`, `MINT_WINDOW`/`DEFAULT_MINT_EVAL_LAG`/`MAX_MINT_EVAL_LAG` (callers use `REF_WINDOW`/`DEFAULT_REF_LAG`/`MAX_REF_LAG`), `PAYLOAD_VERSION_V1`, `DecodeBodyV1`, `Payload::Price`, the 5-arg `Payload::Mint`, the 1-arg `Payload::Redeem`, the v1 `RegtestParams` overload and `Params::{genesisAnchor,genesisRosterScript,supplyCap,tierBlocks,tierRatioPct,rosterGrace,volCooldown,volWindowShort,volWindowLong}`; the overload hazard is gone |
| Every DigiDollar rule is enforced by every node, so nothing needs a selectable parameter set | §3.1 *Parameter versioning* says `EvaluateBlock` selects the set by `H`, but its §4.2a signature takes one `const Params&` | `SelectParams(const std::vector<Params>& sets, int height)` in `params.h` picks the set with the greatest `startHeight ≤ H` (the first set when none qualifies); the caller (the index, Phase 3) selects and passes it; `params_selected_by_height` pins the boundary |
| `ConnectBlock` calls `GetBlockSubsidy` itself | `state.cpp` is `libbitcoin_common` and may not call `main.cpp` (N22) | `index.cpp`'s `ApplyOne` computes `GetBlockSubsidy(height, ::Params().GetConsensus())` and passes it; `issuedZat` is carried from `Snapshots[H − 1]` (virtual ⇒ 0), i.e. the sum over `[START_HEIGHT, H]` (SERIALISATION.md §2) |
| A Bitcoin-Core test reads JSON vectors through `read_json` (`src/test/test_util.cpp`) | Ycash's `read_json` accepts only a JSON **array** (`!v.isArray()` ⇒ "Parse error") and the golden vector is an object | `statehash_golden_vector` parses with `UniValue::read` directly; the vector is embedded through the stock `JSON_TEST_FILES` → `.json.h` rule (`src/Makefile.test.include`) as a copy of the qa/ file, and `gen_yellowback_corpus.py --check` fails when the two copies differ |
| libFuzzer targets are one binary per target with the harness in the target file | Ycash builds one target at a time as `src/fuzz.cpp` (`--enable-fuzz-main`), and the Boost replay needs the same body without a fuzzing build | The `YellowbackEvaluate`/`YellowbackPayee` bodies live in `src/test/yellowback_fuzz_harness.h` (header-only, no Boost), included by both `src/fuzzing/<Target>/fuzz.cpp` and `yellowback_fuzz_tests.cpp`; the prefix grammar is documented there; a `CBlock` that does not deserialise is "discarded" (return 1), never a failure (M10) |
| `\b` in `git grep -E` works on Linux (GNU regex) | macOS `git grep -E` uses the BSD `regcomp`, which has no `\b`: the plan's acceptance loop `git grep -qE "^// Rule: .*\b$id\b"` reports "no unit test tagged" for **every** identifier on this host | Run the loop with `-P` on macOS (identical result); CI runs it on `ubuntu-22.04` as written. The `// Rule:` tags themselves are one identifier per line (a case may carry several lines) |
| `FEE-W`'s seed is "SHA256(blockHash(R) ‖ selector) as a little-endian uint64" (plan §3.7) | A 32-byte digest is not a uint64 | `DefaultPayee` reads the **first eight bytes** of the digest little-endian, `blockHash(R)` as the 32 raw bytes of `Snapshots[R].blockHash` (zero when missing); Phase 6's wallet and any Python reimplementation must do the same. The N28 ratio test uses selectors shaped like an owner key (`0x02 ‖ LE(i)`), because the bare `LE(i)` encoding happens to land a 2.1σ draw (699:301) outside `[1.8, 2.2]` — a property of that seed, not of the sampler |
| The judgement of a tag is a per-node opinion | The model writes `Judgements[t]` for **every** quote tag at `t + PEER_LAG`, `evaluated = false` when `|peers| < PEER_MIN` (SERIALISATION.md §2) | Same in `state.cpp` (`Judge`); a signal-only tag gets no row. Also adopted from the model: a VOID vault's collateral is outside `Totals.collateralZat`, `feePaidZat` is rewritten by a passing redeem/claim (0 under FEE-0), a vault closed by a failing RED still removes its collateral from `Totals`, `burned` is recorded on VOID vaults a transaction closes, and the failure of a vault spend burns every YED input so `unbacked = (burned < mintedCents)` is false whenever the inputs covered the debt (M3) |
| Phase 1's `FindTag` requires the scriptSig to **start** with `CScript() << nHeight` | The model skips the height prefix by its **length** whatever the bytes are (SERIALISATION.md §4) | Not changed in Phase 2 (tag.cpp is Phase 1's): the two differ only on a coinbase whose BIP34 push is wrong, which is consensus-invalid, so no valid chain distinguishes them; recorded for Phase 8's review rather than adjusted |

### 13.6 Rows added while building Phase 4 (2026-09-10, `feature/yellowback-sf-p4`)

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| `BlockAssembler` selects packages and reads DigiDollar state from the chainstate (`ref/digibyte/src/node/miner.cpp`) | `CreateNewBlock`'s priority loop accepts one transaction at a time and calls `UpdateCoins` as it goes (`ref/ycash/src/miner.cpp:582`); no DD state in the coins view | `policy::FilterTemplate(TemplateView&, tx, nHeight)` dry-runs `ProcessTx` on a **nested** `OverlayStateView` over the template view and `Commit()`s it into the template overlay only when the transaction is kept, so chained candidates (a MINT and the TRANSFER of its token in one template) see each other exactly as `ConnectBlock` will; it sits immediately before `UpdateCoins` (one `continue`, behind `ybview`) |
| `getblocktemplate`'s `mutable` is built per call | `aMutable` is a **`static` UniValue filled once** (`ref/ycash/src/rpc/mining.cpp:747-752`) | `"coinbase/append"` is pushed inside that fill-once block under `if (g_yellowback)` — correct because `g_yellowback` is fixed for the process; a node without the flag keeps `["time","transactions","prevblock"]` (`gbt_shape_without_flag`) |
| A template is rebuilt per request | `getblocktemplate` reuses `pblocktemplate` while the tip is unchanged and the mempool did not change within 5 s (`rpc/mining.cpp:590-600`), so `COINBASE_FLAGS` — set by `CreateNewBlock` — is the tag *that cached template carries* | `TemplateInfo(now)` decodes `COINBASE_FLAGS` (V5's one source of truth) rather than recomputing the tag, so `yellowback.tag == coinbaseaux.flags == coinbasetxn`'s push always, and a quote that aged between calls shows as `signal` only once a new template is built; the staleness test mines a block first. `now` (the RPC's clock) feeds only `quoteAgeSeconds` |
| DD spends are byte-exact by construction (Tapscript) | `ParseVaultSpendPath` accepts every selector `OP_IF` accepts (K4: `OP_2`, non-minimal `1`, `0x80`) because consensus verifies vaults with P2SH \| CLTV only (`ref/ycash/src/main.cpp:2931`) | TPL-2's "exactly the wallet's shape" is a byte comparison of the scriptSig against `OwnerScriptSig(sig, script)` / `ClaimScriptSig(script)`; a script-valid `OP_2` owner spend is therefore MP-1-admitted, relayed by every node, and left out of every strict template until `removeExpired` drops it — which is how `mp1_expiry_required` keeps an admitted spend unmined for `REF_WINDOW` blocks |
| The Phase 5 `fee2` shape uses a **claim** (RED-4 needs an underwater vault: ≥ 33 low quotes of 64) | Nothing in Phase 4 crashes the price | `mp1_reorg_reevaluates_mempool` uses an **owner-path** redeem whose fee payee's only tag in `[R-9, R]` is block `R`, replaced by two stock blocks (`invalidateblock` + `generate 2` on node 1): the same RED-3 flip and the same `ConnectTip` sweep; the claim variant is Phase 5's |
| — | `sendrawtransaction` of a hand-built transaction does not mark its inputs spent for `listunspent` (the wallet only learns of it as a mempool tx if it is *to* the wallet), so `_select_funding` picks the same largest coin twice and the second raw transaction hits `pool.mapNextTx` in `AcceptToMemoryPool`, which returns **`false` with no `CValidationState` reason** (`ref/ycash/src/main.cpp:1580-1587`) — an empty RPC error message | `yellowback_mining.py`'s `send_locked()` locks the inputs with `lockunspent` after sending and unlocks after the block; the framework's raw builders stay unchanged |
| Quote staleness is wall-clock (`-yellowbackquotemaxage`) | The plan's case "sets 5 s and sleeps" | `advance_clock(1801)` (`setmocktime` on every node, P12) with the default 1800 s; `UpdateTime` keeps block times monotone (`max(MTP + 1, GetAdjustedTime())`) under a fixed mock time, so mining continues normally afterwards |
| `-yellowbacktestfault=template` "makes `FilterTemplate` disagree with `EvaluateBlock` once" | — | Implemented as: the first *block-invalid vault spend* the filter would skip is kept instead (`ConsumeTemplateFault`), so `TestBlockValidity` throws as TPL-3 says; a flip on a harmless transaction would not produce a disagreement |
| DigiByte's `CCoinsViewCache` layering is explicit (`CCoinsViewCache(CCoinsView*)`, pointer-based, non-copyable) | `OverlayStateView` took `StateView&` and had an **implicit copy constructor**, so `OverlayStateView sub(otherOverlay)` — the natural spelling of "nest one overlay in another" — picked the copy (an exact match beats a derived-to-base conversion) and `sub` shared the *index* as its base: `sub.Commit()` wrote the dry run into the database's pending batch. One `getblocktemplate` with an unmined mint bumped `Totals.activeVaults` on the live index and every pool that built a template diverged from the other nodes (found by `yellowback_mining.py`'s checkpoint; the Phase 2 unit test `overlay_view_equivalence` had the same copy and passed only because both "layers" committed to the same base) | `FilterTemplate` binds the template overlay as a `StateView&` before nesting; the copy constructor and copy assignment of `OverlayStateView` are `= delete` (`view.h`), and the unit test nests through a `StateView&`. Any future `OverlayStateView x(y)` where `y` is an overlay now fails to compile |

### 13.4 Rows added while building Phase 3 (2026-09-10, `feature/yellowback-sf`)

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| DigiDollar's state is consensus state, so a node "restarted with different parameters" does not exist | The overlay's four hashed regtest values (M13) live in a `Params` record of a separate LevelDB; `SyncToChain` wiped only on a schema or network change, so a node restarted with `-yellowbacksigmaref=1` (or a new `-yellowbackstartheight`) kept rows computed under the old set and its hash *agreed* with the others — `params_mismatch_fails_loudly` could not fail loudly | `SyncToChain` compares the stored `ParamsRecord` with the running set and wipes on a difference (`ycash-dd/src/yellowback/index.cpp`); `params_change_wipes_on_start` pins it. `-yellowbackenforce=0` changes no hashed value, so the kill switch's `Rejected` survives that restart as V13 needs |
| A DD transaction fails consensus with one verdict | MP-1 has two checks — RED-1..4 and the N5 expiry bound — and the bound needs the REDEEM payload's `refHeight`; checked first, a payload-less spend was reported as `mempool-expiry`, not by its RED verdict, which K7's `mempool-check-failed:<verdict>` names | `MempoolCheckLocked` evaluates RED-1..4 over the pseudo-block first and the bound second (same admit/refuse outcome); `mempoolcheck_bench` pins `vault-spend-malformed` for a bare owner-path spend and `mempool-expiry` for a well-formed one with `nExpiryHeight = 0` or `> refHeight + REF_WINDOW` |
| Bitcoin-Core test fixtures build blocks through the miner, so every header is complete | A synthetic `CBlock` whose `hashMerkleRoot` is left zero hashes as its *header only*: every block built in one second shares one hash, the index's cache key and tip guard (`block.GetHash()`, `pprev->GetBlockHash()`, K5) collapse, and hook tests pass by accident | `yellowback_index_tests.cpp`'s `Chain::Add` sets `hashPrevBlock` from the parent and `hashMerkleRoot = BuildMerkleTree()` before taking the hash; a rejected block never advances the fixture's tip (`Live::tip`), so a second rule-breaking block is a sibling, not a child |
| Core's `IsInitialBlockDownload` in a unit test is false once a recent block exists | Ycash 4.5's `IsInitialBlockDownload` (`ref/ycash/src/main.cpp:2106-2178`) tests only the tip's age and latches false process-wide; a `TestingSetup(REGTEST)` tip is the 2016 regtest genesis, so every BLK-2 rejection case would be suppressed as "IBD" | The suite's fixture raises `nMaxTipAge` (`main.h:206`) for its lifetime; the latch then stays false for the process, which is the state every suite after `TestChain100Setup` runs in anyway. The K6 case uses `TestChain100Setup` (real blocks in `chainActive`) because a fake `CBlockIndex` is never "contained" |
| `ReconsiderBlock` in DigiByte is an RPC over the real block index | The valve's `ReconsiderBlock` loop (ACT-7) and `IsRejectedAncestor` walk `mapBlockIndex`; `TestingSetup`'s destructor `delete`s every entry (`UnloadBlockIndex`), so a fake entry owned by the case would be freed twice | `MapGuard` inserts the case's fake `CBlockIndex` entries and erases them in its destructor; `GetMiscWarning()` (`warnings.h:13`) reads the P1 text back; the odometer cases set the rejected root's `nChainWork` equal to the tip's (a sibling), so "six headers of one block of work each above the tip" trip exactly at the sixth |
| `base_uint` arithmetic returns `arith_uint256` | `arith_uint256 / int * int` yields `base_uint<256>`, which has no `GetCompact()` | `arith_uint256(parentTarget / 100 * 140).GetCompact()` in `valve_ignores_lowdiff_headers`; `SetCompact` round-trips a 256-bit target with exponent 32 without `overflow` |
| Core flushes the chainstate on every block in tests (`FLUSH_STATE_ALWAYS` paths) | `FlushStateToDisk` (`ref/ycash/src/main.cpp:3305-3395`): the first call only records `nLastWrite`/`nLastFlush` ("avoid writing immediately after startup"), then writes hourly and flushes daily; a node killed before its first clean shutdown restarts with `hashBestChain height=0`, and `SyncToChain` takes the "chain below start height" *wipe* branch rather than the undo walk | `crash_unflushed_chainstate` restarts node 3 cleanly first (a shutdown flushes), so the 30 blocks below the kill are the unflushed part and `SyncToChain: undoing` runs; the `UNDO_KEEP + 10` variant does the same and reaches `wiping index (undo record missing …)`. The block index is written on the same schedule, so after `kill -9` right after a rejection the `Rejected` hash is *not* in `mapBlockIndex` at restart — `rejected_survives_kill9` is the "skipped and cleared" branch of the kill switch; a cleanly stopped node is the "reconsidered" branch |
| A DD oracle bundle is in the block; nothing per-node is lost on restart | The quote (`yed_setquote`) lives in the index's memory (V6: the agent pushes it, nothing persists it); a pool restarted mid-test emits **signal-only** tags until its agent quotes again, and the fast window's fill drops below its bound | `YellowbackTestFramework.quote(i, usd)` records the quote and `restart(i)` re-applies it the way a pool's agent would; the module-level `set_quote(node, usd)` stays for one-off calls. Found by `price1_reorg_across_fill_boundary` after the crash case had restarted node 3 |
| Core's `dumpprivkey` takes the address the wallet shows | `yed_getvault.ownerAddress` is the `ye…/yt…/yr…` rendering of the owner key (§3.1), which `dumpprivkey` refuses ("Invalid Zcash address") | `build_vault_spend_raw` derives the P2PKH address from `ownerPubKey` (`pubkey_to_address`) for the signing key; the field is display only |
| Core's `ParseParameters` keeps the first of a repeated flag | `mapArgs[str] = strValue` (`ref/ycash/src/util.cpp`, `ParseParameters`): the **last** repetition wins | `restart(i, ['-yellowbackstartheight=50'])` overrides the role arguments' `-yellowbackstartheight=1` without a special case (`index_start_height_above_tip`, `params_mismatch_fails_loudly`) |
| A fresh regtest wallet in Core has 50-BTC coinbases spendable after 100 blocks | Node 0 mines the 101 initial blocks moments before `run_test`; only the coinbases 100 deep are spendable, and a class-A mint of `MIN_MINT` (100 YED) at $2.00 needs 250 YEC of collateral | Scripts that mint before activation mine 60 more blocks on node 0 first (`yellowback_rpc_contract.py`, `yellowback_activation.py`); after `activate()` (129 blocks) enough has matured |
| Nothing in DigiDollar lets a block at the first enforced height spend a vault created under enforcement | MINT-4 voids every mint whose `Snapshots[refHeight]` is not ACTIVE, so at `activateHeight + 1` no ACTIVE vault can exist and BLK-1 has nothing to reject; the plan's `act3_reorg_across_activateheight` ("a rule-breaking block on the losing branch was rejected … before `activateHeight + 1` is accepted") cannot be built | The case keeps the reorg straddling `activateHeight + 1` (enforcement on → off → on), the VOID vault with `sweepBefore` on the losing branch, the same `activateHeight` on the winner and `Rejected` empty; the rejected-then-accepted half is the ACT-6 ladder later in the same script (rejected at ≈ 35 signals, accepted at ≈ 29) and Phase 5's `yellowback_enforcement.py` |
| Core's `mineBlock` helpers are instant | A Python-assembled block (`mine_block_raw`, regtest Equihash n=48, k=5 in pure Python) takes ≈ 1 s; `act_forged_signal_tags` needs 48 of them (≈ 50 s) and lock-in is one-shot | The forged lock-in is observed first, then rewound with `invalidateblock` on every node (the index undoes 48 blocks through `DisconnectBlock`), so the later K16 lock-in and `act2` reorg see a fresh window; `act2` makes "A wins" happen with `invalidateblock`/`reconsiderblock` on the enforcing nodes because an orphaned branch cannot be extended once its miners have moved |
| The rule → test grep of §7 is `^(//\|#) Rule:` | A Python docstring that opens with `"""# Rule: …` on one line does not start with `# Rule:`, so the functional scripts' tags were invisible to the CI loop (the C++ tags carried every identifier so far) | The three Phase 3 scripts carry a column-0 `# Rule: …` comment line above the test class; the `audit` job's loop reports (blocking from Phase 6, when `TPL-1..3` and `MINTPOL-1` gain tests) |
| A JSON number is a number | The framework's `AuthServiceProxy` parses JSON numbers with a fraction as `Decimal` (`yed_getvault.collateral`) | `yellowback_rpc_contract.py`'s type check counts `Decimal` as a number; `bool` is checked before `int` because Python's `bool` is an `int` |
| Core's test framework signs in Python with whatever OpenSSL `ctypes.util.find_library('ssl')` finds | On macOS that is `/usr/lib/libssl.dylib`, the SIP-protected LibreSSL shim, whose `ECDSA_sign` aborts the interpreter (SIGABRT, exit 134) — plan §6.0 item 0 works around it with `DYLD_LIBRARY_PATH`. But SIP **strips every `DYLD_*` variable** from the environment of a protected binary, and `#!/usr/bin/env python3` — the shebang `qa/pull-tester/rpc-tests.py` execs every script through (`:353`) — is one. So the export reaches `python3 qa/rpc-tests/<script>.py` and never the suite runner: the Phase 3 acceptance line reported all three scripts `Pass: False` with empty stdout and exit 134 | `yellowback_util.py` resolves a real `libcrypto*.dylib` (from `DYLD_LIBRARY_PATH`, then the two Homebrew prefixes) and wraps `ctypes.util.find_library` at import, before anything imports `key`; `key.py` calls only libcrypto symbols (`BN_*`, `EC_*`, `ECDSA_*`), the inherited file is untouched, and the shim is a no-op off Darwin or without a real OpenSSL. The runner's `passed = stderr == "" and returncode == 0` also means the dyld warning alone fails a script — a second reason not to rely on the variable |
| The acceptance grep `GetTime … \| grep -v policy.cpp` is run on code | `policy.h`'s *comments* named `GetTime()`, which the verbatim acceptance line counts | The comments say "the wall clock"; the two homes of the clock are unchanged (`rpc/yellowback.cpp`, `policy.cpp`) |
| A DigiDollar test mines any accepted transaction with `generate` | TPL-2 (`-yellowbacktemplatepolicy=strict`, the default) skips a MINT whose verdict would be VOID, so a pre-activation mint is admitted by MP-1, relayed, and then never selected by *any* pool's `CreateNewBlock`: `generate` mines an empty block and the VOID-vault fixture never exists (`yed_getvault` → `vault-not-found`) | Every script that needs a VOID mint on chain assembles the block in Python with `mine_block_raw` (plan §6.0 item 4): `yellowback_activation.py` act3 and `yellowback_rpc_contract.py`'s fixture. The alternative — a pool restarted with `-yellowbacktemplatepolicy=consensus` — costs a restart and changes the node under test |
| Core's `sync_mempools` after a reorg converges because both partitions saw every transaction | A transaction mined **only** on the losing branch of `split_network()` is returned to that branch's mempools by `DisconnectTip`, while the other partition never received it; after `join_network()` the two mempools differ for the life of the test and the next `sync_all()` raises `Mempool sync failed` | Give such a transaction an `nExpiryHeight` equal to the height of the losing block itself (`build_mint_tx(expiry=…)`): the first `ConnectTip` after the reorg is one height higher, so `mempool.removeExpired` drops it on exactly the nodes that got it back. Rebroadcasting it to the other partition instead would leave a VOID mint in every mempool that TPL-2 will never mine |
| — | The plan's N28 hand run-through says `generate 70` leaves `yed_getactivation.status == "signaling"` with `signalCount == 64` and that `generate 65` more reaches `locked_in`. ACT-2 locks in at the first height whose trailing `SIGNAL_WINDOW` is full and at or above the threshold, which on a single signalling node is height 64 — the run gives `locked_in` at 70 already, and `active` at `64 + ACTIVATION_DELAY = 128` rather than at `135 + 64` | The binary is right and the plan's prose is off by one window; the run-through was completed against the real numbers (`locked_in` lockInHeight 64, `active` at 128, three defined medians at ≥ 64 blocks, `verifychain 4 20` leaving `yed_getstatehash` unchanged). A coordinator fix to the plan text, not to code |

### 13.5 Rows added while building Phase 6 (2026-09-10, `feature/yellowback-sf-p6`)

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| DigiByte's wallet signs vault spends with the signer it links in-process | §4.2a moves `SignerBranchId`/`VerifyAllInputs` from `policy.h` (libbitcoin_server) to `txbuilder.h` (libbitcoin_wallet), but the node-context `yed_validaterawtransaction` (`src/rpc/yellowback.cpp`, libbitcoin_server) calls both and cannot link the wallet library | Not moved: `policy.h` keeps `SignerBranchId()` (no argument; `CurrentEpochBranchId(chainActive.Height() + 1)` under `cs_main`) and `VerifyAllInputs(tx, view, branchId, err)`; `txbuilder.cpp` includes `policy.h`. The plan's signatures `SignerBranchId(int)` / `VerifyAllInputs(tx, view, err)` do not exist |
| One reference height for every DD transaction | The wallet's MINT uses `R = indexTip − REF_LAG` (§3.5) so the mint survives a 2-block reorg; a vault spend has no such need and `yed_listclaimable` reads the tip snapshot | A vault spend (REDEEM, CLAIM, release, SWEEP) uses `R = indexTip` (`Context::spendRefHeight`, `txbuilder.cpp`): RED-1's window holds at `H = tip + 1`, `BuildClaim`'s RED-4 check and `yed_listclaimable` read the same snapshot, and `nExpiryHeight = R + REF_WINDOW` is the MP-1 bound. The live-tested main-tree behaviour, kept at the merge |
| The K7 gate and MP-1 were two evaluations in the p6 prototype (`MempoolGate` re-ran `EvaluateBlock`) | Phase 3's `YellowbackIndex::MempoolCheckReason` is the predicate `AcceptToMemoryPool` applies, including the N5 expiry bound (`mempool-expiry`) | `yed_redeem`/`yed_claim`/`yed_mint` call `MempoolCheckReason` and raise `mempool-check-failed:<reason>`; the transitional `index.h` stubs of `66c7c1242` were dropped at the merge |
| Core's `wallet.cpp` knows nothing of a transaction's expiry | §4.6/N39: `yed_gettxinfo.expired` for a wallet transaction past `nExpiryHeight` that is in neither `TxLog` nor the mempool — a node-context RPC (`rpc/yellowback.cpp`) that must read the wallet | Under `#ifdef ENABLE_WALLET`, as `rpc/misc.cpp`'s `getinfo` does: `LOCK2(cs_main, pwalletMain->cs_wallet)`, then `mempool.cs`, then `cs_yellowback` (the N25 lock order); the row is `{height: -1, type, verdict: "expired", zeros, expired: true}`; a `tx-not-found` otherwise. Pinned by `expired_transaction_display` |
| DD's history view is in-process | `yed_listtransactions.type` must classify from the `TxLog` alone | `burn` iff `burned > 0` and `yedOut == received` (nothing left the wallet but the burn: a plain-YEC spend, an under-assigned self-transfer); `send` whenever the wallet spent anything (an own-to-own transfer is a `send` with `amountCents 0`); `receive` only when it spent nothing; `redeem`/`claimed`/`sweep` for a closed own vault by verdict and path; `claim` for a passing claim-path spend of somebody's vault |
| A VOID DD position does not exist | A VOID vault keeps `mintedCents` from the payload (the model does the same) although it carries no debt; `Totals` exclude it | `yed_sweep.unbackedCents` reads `mintedCents`; tests assert `mintedCents == cents` and `supplyCents` unchanged for a VOID mint, never `mintedCents == 0` |
| The plan's §4.5 error table is the whole identifier set | The builder refuses for reasons the table does not name (`bad-address`, `insufficient-yec`, `bad-mint-amount`, `bad-xfer-amount`, `keypool-empty`, `wallet-locked`, `too-many-inputs`, `too-many-notes`, `expiring-too-soon`, `index-below-start`, `vault-value-too-small`) | Listed in a second table of `doc/yellowback-rpc.md` (*Error identifiers*); `extract_spec.py` derives the contract JSON's `errors` from the **plan's** table, so `make spec-check` is unaffected — adding them to plan §4.5 is a coordinator decision |
| — | The acceptance loop's grep `^(//\|#) Rule:` is anchored at column 0; a Python case tag indented inside `run_test` (and the main tree's `"""# Rule: …"""` docstring, mapping §13.6) is invisible to it | Every functional-script tag is a **column-0** `# Rule:` comment line inside the method body (legal Python); the six Phase 6 scripts carry 60+ such lines |
| — | FEE-0 for a *mint* is unreachable when minting is allowed: `E(R)` empty means no quote tag in `(R − 10, R]`, so the fast window (8, fill 4) is empty too and `NO_PRICE` voids the mint (MINT-4 before MINT-8) | The FEE-0 case is a **redemption** after `PAYEE_WINDOW + 1` untagged stock blocks (`yed_redeem` returns `payee: null, feeZat: 0`, three outputs) — `yellowback_lifecycle.py` `fee_0` |
| — | A six-node `sync_mempools` can never converge once the stock node holds a raw vault spend every overlay mempool refuses (MP-1), e.g. the raw claim of a healthy vault broadcast from node 1 | `yellowback_claim.py` overrides `sync_all` to sync mempools among the overlay nodes only; the stock node's mempool is asserted explicitly where it matters (the sweep's relay, L13) |
| — | The framework's `initial_blocks = 101` leaves exactly **one** mature coinbase (6.25 YEC) before activation; a pre-activation raw mint needs 10 YEC | `yellowback_void_mint.py` sets `initial_blocks = 112`; scripts fund other wallets after `activate()` (≈ 130 mature coinbases) |
| — | A raw MINT whose `refHeight` is `H − 41` (the `bad-mint-ref-height` case) would carry `nExpiryHeight = R + 40 = H − 1`: the mempool refuses it as `tx-expiring-soon` (`TX_EXPIRING_SOON_THRESHOLD`) before MINT-2 ever sees it | The adversarial mint carries a later `nExpiryHeight` (`raw_mint(…, expiry=tip + 10)`); MINT-2 reads the payload's `refHeight`, never the expiry |
| — | `pMint = min(pFast, pMid, pSlow)` and `pClaim = max(pMid, pSlow)` are defined only when **every** input is (model `_snap`, `state.cpp` SNAP); the mint price therefore appears at the slow window's fill (43 of 64), not the fast window's | `yellowback_pricefeed.py` asserts `pMint`/`pClaim` defined iff `n ≥ MIN_FILL[2]` and `NO_PRICE` until then; the wallet's `mintpol-*` refusal reads `Snapshots[tip − REF_LAG]`, so a halt asserted at the tip is asserted for the wallet two blocks later |
| — | `-yellowbacksigmaref` defaults to `0` on regtest (`ParamsFromArgs`, `index.cpp`): the σ multiplier is fixed at 1 in every script that does not say otherwise | σ cases set the class attribute `sigma_ref = SIGMA_REF_BPS` (10,000); a single 5 % step in `pFast` between two 8-block samples gives 16,545 bps, a 20 % step saturates at 30,000 |
| — | `IsAbandonedLocked` counts `abandonBlocks` snapshots **ending at the tip**, the tip's own included | With the ENFORCEMENT bit first set at `H0`, `abandoned` flips at `H0 + ABANDON_BLOCKS − 1` (33 + 127 unsignalled blocks on regtest), not at `H0 + ABANDON_BLOCKS` |
| The plan's `sunset_alone_is_not_abandonment` has node 1 forge signal tags | Forging is a Python-assembled block per tag (`mine_block_raw`, 0.08 s a solve on this host) and node 1 is the stock binary | `yellowback_claim.py` restarts **node 0** as a signalling tagger (`-yellowbackpayoutaddress`, no sunset) and gives it 34 of 64 blocks while nodes 2–4 run `-yellowbackenforceuntil` behind the tip; the observable state is the one the plan names (`sunset`, `enforcing = false`, `abandoned = false` on the pools). The L9 case in `yellowback_pricefeed.py` does forge quote tags on node 1 (`forge_quote_block`) |
| — | `yellowback_rpc_contract.py` did not exist on the merged tip although mapping §13.6 mentions it (Phase 3's file is being written concurrently) | The Phase 6 file covers the wallet context in full and the node context wherever its scenario passes it (every command but `yed_getblockverdict`'s success path, which needs a not-yet-connected child of the tip); its checker treats `Decimal` as a JSON number (§13.6). A merge with Phase 3's version must keep both scenarios |
| Linux CI runs `qa/pull-tester/rpc-tests.py`, which execs each script through `#!/usr/bin/env python3` | On macOS `/usr/bin/env` is SIP-protected and the exec **drops `DYLD_LIBRARY_PATH`**, so the runner's child loads the system libcrypto for the framework's `CECKey` signer and is aborted ("is loading libcrypto in an unsafe way"); `yellowback_mining.py` fails under the runner on this host at its first owner-path vault spend while the same script run directly passes | Recorded in `doc/yellowback.md` host notes; on macOS run the signing scripts directly (`../.venv/bin/python -u qa/rpc-tests/<script>.py …`); nothing to change in the scripts or the runner for CI |
| Bitcoin Core keeps a `BLOCK_FAILED_VALID` entry in the block index across restarts, so `reconsiderblock` after a restart finds it (the K21 pattern of `rpc/blockchain.cpp:1497-1509`) | Zcash's `RewindBlockIndex` (`ref/ycash/src/main.cpp:5185-5330`), run at every start, erases from `mapBlockIndex` every entry that is not "sufficiently validated" — which requires `nCachedBranchId`, set only by a *successful* `ConnectBlock` (`:3218`); a block the hook rejected never got one and is deleted with its `BLOCK_FAILED_VALID` mark, whether the node was killed or stopped cleanly | The kill-switch loop's `ReconsiderBlock` branch at start is unreachable in Ycash 4.5: every recorded hash takes the "not in the block index; skipped" branch, `Rejected` is cleared, and the node rejoins by re-downloading the block (its header is accepted again because the mark is gone; `-yellowbackenforce=0` then connects it). `rejected_survives_kill9` and the clean-stop restart in `yellowback_index.py` both assert that branch; the loop keeps `ReconsiderBlock` for the day the index keeps such entries, and the valve's runtime loop (ACT-7, same process) still needs it — `valve_trips_at_six_blocks` pins that path. With `-yellowbackenforce=1` a restarted node re-validates the re-downloaded block and rejects it again, so nothing is lost |

| DigiByte's regression tests mine a deliberately invalid DigiDollar transaction straight out of the mempool, because its miner applies no DigiDollar policy filter | Ycash's `CreateNewBlock` runs `yellowback::policy::FilterTemplate` (`src/yellowback/policy.cpp:66`), and TPL-2 (`-yellowbacktemplatepolicy=strict`, the default, V14) skips a MINT whose verdict would be VOID, a TRANSFER whose verdict would burn and a claim-path spend of a VOID vault (`policy.cpp:106-112`). `generate` on *any* overlay node — pool or not — therefore silently drops them, and the symptom is `vault-not-found` several lines later, not a mining error | Every wallet-flow case that needs an invalid transaction on chain assembles its own block with `mine_block_raw` and syncs `blocks_only`: `yellowback_void_mint.send_and_mine` (all eleven raw mints), `yellowback_claim`'s VOID vault Z, `yellowback_lifecycle`'s `under_assigned_raw_transfer`, `yellowback_rpc_contract`'s short-collateral mint. A framework-wide `-yellowbacktemplatepolicy=consensus` switch was tried first and removed: leaving the pools on the strict default is the stronger test |
| — | `mint6_cap_race_after_reorg` mines X on the losing branch of a `split_network()`; after the join X is over the cap, so its verdict is VOID and no template will confirm it, and the stock half never held it, so `sync_all()`'s mempool sync can never converge | The confirming block is assembled with `mine_block_raw` and the sync is `blocks_only=True`. The general rule for a split: a transaction mined only on the losing branch either gets an `nExpiryHeight` equal to that block's height (so the first `ConnectTip` expires it) or is never mempool-synced across the halves again |
| DigiByte picks its DigiDollar fee payee from an in-process oracle roster with equal weight per oracle (`ref/digibyte/src/oracle/`) | `DefaultPayee` (`src/yellowback/state.cpp:606-641`) builds **one weighted candidate entry per quote tag** in the last `payeeWindow` blocks, so a pool's probability is its tag frequency times its accuracy tilt, not the tilt alone. On regtest `payeeWindow = 10` (`src/yellowback/params.cpp:144`) and a three-pool rotation splits the window 4:3 or 3:4, putting the accurate pool's true share at exactly 0.600 or 0.727 — the plan's `[0.6, 0.72]` band read as a *sample* bound then straddles its own edge (measured 119/200, and 0.5973 over 4,000 draws) | `yellowback_pricefeed.py`'s FEE-W case reads the window's tags through `yed_gettag`, computes `expected = 2X/(2X+Y)`, asserts *that* inside `[0.6, 0.73]`, and asserts the 200-draw sample above the unweighted share and within 4 σ of it. Balancing the window by mining was tried and rejected: dropping a pool from the rotation changes the peer-median judgement and the accurate pool's `accuracyBps` falls to 5555 |
| — | `qa/rpc-tests/yellowback_claim.py` defined a method `quote(self, usd)` that silently shadowed `YellowbackTestFramework.quote(self, i, usd)` (`yellowback_util.py:524`), so `activate(quote_usd=…)` died with a `TypeError` on the first line of the test | Script-local price helpers are named `price()`. Any new method on a `YellowbackTestFramework` subclass must be checked against the base class's names first — `quote`, `mine`, `price`, `restart`, `activate`, `sync_all`, `checkpoint` are all taken |
| — | `qa/rpc-tests/yellowback_claim.py`, `_pricefeed.py` and `_rpc_contract.py` were committed mode 100644; `qa/pull-tester/rpc-tests.py` execs scripts directly, so they could never run under the suite even though they pass standalone | `chmod +x`. Check `git ls-files -s qa/rpc-tests/yellowback_*.py` for `100755` on every new script |
| DigiByte's GNU-grep CI counts a rule tag anywhere in a test file | The Phase 6 acceptance loop is `git grep -qP "^(//\|#) Rule: .*\b$id\b"` — anchored at column 0, and `-P` is required: `git grep -qE` does not implement `\b` and reports *every* identifier untagged, which reads as a total failure rather than a regex problem | Run the loop with `-qP`. At `57823b4a9` exactly one identifier is untagged, `TPL-3` (the node's own template passing `TestBlockValidity`), which belongs to Phase 4's `yellowback_mining.py`; `MINTPOL-1` is tagged at column 0 in five places (`yellowback_void_mint.py:136,153,165,246,298` and `yellowback_lifecycle.py:100`), contrary to the §13.9 row written before Phase 6 merged |

### 13.7 Rows added while building Phase 7 (2026-09-10, `feature/yellowback-sf-p7rest`)

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| DigiDollar's oracle price is in the block; a test "source outage" is a consensus fixture | `yellowback-quote --mock-price` makes the mock file the whole market (`yellowback_price.py` `PriceFeed.aggregate`: mask 0, sources never fetched), so the L5 case "a source outage below `min_sources`" cannot be produced under the mock the plan's test fixture prescribes | `yellowback_quote.py` restarts one pool's agent **without** `--mock-price` on the same TOML, whose one `generic` source points at `http://127.0.0.1:1/never`: two failed polls → `yed_setquote 0` → `quoteKind == "signal"` within the 60 s deadline, the daemon still running; an unreadable mock file is the `--once` exit-1 case instead |
| — | `validate_config` refuses `max_age` on a `generic` source without `timestamp_path` ("max_age needs timestamp_path", exit 2); the plan's "one `generic` preset pointing at nothing" row therefore carries no freshness guard | The test's and the devnet's TOML rows are `name, kind, venue, url, path` only |
| Core's `setmocktime` is used by tests to age things | Ycash's `setmocktime` freezes `GetTime()` on the node, and `yed_setquote` stamps `receivedAt = GetTime()` — a live agent re-stamps at the frozen time (age 0 forever), a stopped agent's quote never ages until the next `advance_clock` | The stale case is deterministic: `advance_clock(1)` first (every node now on the mock clock), stop the agent, `advance_clock(QUOTE_MAX_AGE + 1)` → `"signal"` at once; the live agents show `"signal"` for at most one poll after the jump, so the test waits for `"quote"` with a deadline rather than asserting it immediately |
| — | `qa/pull-tester/rpc-tests.py` execs each script directly (`Popen((tests_dir + t).split() …)`), so a new script needs the executable bit or the runner dies with `PermissionError` before any node starts | `chmod +x qa/rpc-tests/yellowback_quote.py` (committed mode 100755, like the inherited scripts) |
| — | The Phase 7 acceptance diff selects the spec section with `^## 8.1 Trust statement`, but `extract_spec.py` keeps the plan's heading level `### 8.1 …` in `doc/yellowback-spec.md`, so the plan's literal command compares an **empty** left side and always fails | The CI `audit` job's `section()` (`^### 8\.1 `, blank lines trimmed) and the same `sed` pipeline with `^### 8.1` both hold byte for byte; `doc/yellowback.md` puts `## Build and test baseline` directly after the statement's last line so the `sed '1d;$d'` form matches the spec's trailing blank line exactly. The plan's pattern is a typo for the coordinator to fix |
| — | The acceptance line `check-coinbase $(ycash-cli -regtest -datadir=… getblockcount)` gives `check-coinbase` itself no network or datadir, so its own `ycash-cli getblock` would target mainnet's default datadir | `check-coinbase` passes unknown `-options` through to `ycash-cli` (`parse_known_args`), so `check-coinbase <height> -regtest -datadir=<dir>` works without the `--` separator; the acceptance was run that way. It also renders `payoutAddress` for `getblockchaininfo.chain` (chainparams `PUBKEY_ADDRESS` prefixes `1C28` main / `1C95` test+regtest) so its lines compare with `yed_gettag` one for one |
| — | The devnet's `status` printed Python's `True`/`False`; the acceptance greps `eligible: true` | `json.dumps` on the two booleans |
| — | `yellowback-quote` needs Python ≥ 3.11 (`tomllib`); the CI runners are `ubuntu-22.04` (Python 3.10), so the `python` job's unit step could never import the agent, and the `main` job's functional runner would start it under 3.10 | `python` job: `actions/setup-python@v5` with 3.11; `yellowback_quote.py` is registered in `rpc-tests.py` `BASE_SCRIPTS` but **not** in the `main` job's `YELLOWBACK_SCRIPTS` until that job's interpreter is ≥ 3.11 (inline comment; a coordinator decision — `setup-python` there would shadow the apt `python3-zmq`, unused under `--nozmq`) |

### 13.9 Rows added while writing the review document (2026-09-11, `feature/yellowback-sf` @ `5ea56c577`)

Found while gathering evidence for `ycash-dd/doc/yellowback-review.md` (plan Phase 8). Each row is
also a numbered finding (R1–R7) in §8 of that document.

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| A reviewer reads DigiByte's DD hook as a contiguous block in `ref/digibyte/src/validation.cpp`, so "the inserted statements" and "the inserted lines" are the same set | The plan's §8.4 item 2 proof is the **line**-based grep `git diff … \| grep '^+' \| grep -v 'g_yellowback\|#include\|LOCK(cs_main)\|COINBASE_FLAGS'`, while the fork's guarded statements span 2–3 lines each (`if (g_yellowback) {` / body / `}`; `if (g_yellowback && …)` / `return state.DoS(0,…)`) | The grep can never be empty: it prints **7 continuation lines** at `5ea56c577`. Read it as "print the residue and justify each line", not "expect silence" — the review document carries the per-line justification table (R1). Do not "fix" it by joining statements onto one line; rule 7 forbids reformatting, and a 200-column `ConnectBlock` line is worse to review |
| — | §4.1 and §8.4 item 2 predict "the two `#include "yellowback/index.h"` lines"; the tree has **three** includes and one is a different header (`src/main.cpp` and `src/rpc/mining.cpp` → `yellowback/index.h`; `src/miner.cpp` → `yellowback/policy.h`, because `CreateNewBlock` calls `policy::TagScript`/`policy::FilterTemplate`, not the index directly) | Stale count in the plan; behaviourally immaterial. Cite three includes in any review text (R2) |
| — | §4.1 and §8.4 item 2 both cite the unit test `coinbase_flags_empty_without_flag` as the proof that `COINBASE_FLAGS` is empty without `-yellowback`; `git grep -l` finds it in **none** of `ycash-dd`, `wt/p5`, `wt/p6` | The property rests on inspection (nothing else in the tree assigns `COINBASE_FLAGS`; `ref/ycash/src/main.cpp:134` declares it and never assigns) plus `gbt_shape_without_flag`, which checks the GBT *shape*, not the scriptSig. One `BOOST_AUTO_TEST_CASE` still owed (R3) |
| The rule→test grep of §7 is `^(//\|#) Rule:` and DigiByte's tests are C++, where a tag is naturally at column 0 | Phase 4's Python tags in `qa/rpc-tests/yellowback_mining.py:410,469,509,537` are **indented** inside the method body, and `MINTPOL-1` is tagged only inside a docstring (`yellowback_lifecycle.py:20`) — both invisible to the column-0 anchor, exactly the traps recorded in §13.4 and §13.5; `TPL-3` has no test tag anywhere (only source comments in `index.h:109,285` and `policy.h:65`) | The loop reports `untagged: TPL-1 TPL-2 TPL-3 MINTPOL-1` at `5ea56c577`, so §8.4 item 9 is **red**. Fix by moving those tags to column 0 (legal Python inside a method body) and writing a TPL-3 case; do not relax the anchor — a docstring tag is not greppable in the C++ half |
| Every DigiDollar file is consensus code, so "no configuration reads" is uniform across the module | §3.10's pure set is `{state, math, tag, payload, script, view}` (clean: the determinism grep returns nothing), but **§8.4 item 12 adds `index.cpp`**, which legitimately reads `GetArg` at `src/yellowback/index.cpp:890-896` (the four regtest parameters) and includes `txmempool.h` for `RemoveInvalidVaultSpends` | §8.4 item 12's file list is wrong and the CI `audit` job already applies the correct narrower rule to `index.cpp` (no clock, no floating point). Correct the item to match §3.10 and the job (R5) |
| — | §4.1, §8.2, §8.4 item 21 and §8.5 claim 2 all rest on `yellowback_stockparity.py` (and `yellowback_stock_node.py`); **neither file exists** in `ycash-dd`, `wt/p5` or `wt/p6`, and `feature/yellowback-sf` has never been pushed (`git rev-parse origin/feature/yellowback-sf` → unknown revision), so no CI job that would run them has ever run | Until they exist, "stock nodes are unaffected" is supported only by the 30-line diff of `main.cpp`/`miner.cpp`/`rpc/mining.cpp`, printed in full in the review document §2. Say so in the §8.5 statement rather than citing a test that does not exist (R6) |
| DigiByte's DD RPCs read in-process state under one lock, so there is no mempool/overlay inversion to make | The recorded lock order (§4.3, N25) is `cs_main → cs_wallet → mempool.cs → cs_yellowback` with the explicit rule "no RPC may take `mempool.cs` after `cs_yellowback`". `yed_getbalance` takes `LOCK(index.cs_yellowback)` at `src/rpc/yellowbackwallet.cpp:138` and then `LOCK(mempool.cs)` at `:143` — the forbidden inversion. The opposite order is taken by `CreateNewBlock` (`TemplateView()` inside `LOCK2(cs_main, mempool.cs)`) and by `RemoveInvalidVaultSpends` on the `ConnectTip` path | Real defect, found by the static audit the Phase 8 grep prescribes; `cs_main` held on both sides is what has masked it, and the file's own header comment (`yellowbackwallet.cpp:8`) omits `mempool.cs` from the order, which is how it was missed. Fix: hoist the mempool scan above `LOCK(index.cs_yellowback)` (or take `mempool.cs` in the same `LOCK2` as `cs_wallet`). Run the `lockorder` job before rc1 (R7) |
| A Bitcoin-Core-lineage `test_bitcoin` is green at the tag | `ref/ycash` v4.5.0's suite has **two pre-existing failures** on an Apple Silicon build: `main_tests/subsidy_limit_test` (`nSum 2099999981520000 != 2099999990760000`) and `rpc_wallet_tests/rpc_z_sendmany_internals` (two change outputs share an address hash). Both files are byte-identical to the pin in the fork | Record them in every review and release document, so a 2-failure run of 537 cases is not read as a fork regression; only `--run_test='yellowback_*'` (115 cases) is the fork's own gate |


### 13.10 Rows added while building Phase 8 (wallet hardening, 2026-09-11, `feature/yellowback-sf-p8`)

Found while building H1–H12 (the floor-aware selector, the coin-locking guards and the two new
wallet RPCs).

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| A DigiDollar transfer carries its amount in the output's own `nValue` (`ref/digibyte/src/digidollar/txbuilder.cpp`), so any change is representable and smallest-first accumulation can never strand a payer | A YED output is `TOKEN_VALUE` (10,000 zat) and its cents come from the payload's assignment table, where XFER-1 refuses any assignment below `MIN_OUTPUT` (`ycash-dd/src/yellowback/state.cpp:308-310`): change in `(0, MIN_OUTPUT)` cannot be expressed and would burn | `src/yellowback/coinselect.{h,cpp}` (H1): exact → single-with-valid-change → greedy-with-extension → bounded DFS, plus `NearestWorkable()` for the H2 message. Pure and table-tested. **The band is narrow but real:** with every coin ≥ `MIN_OUTPUT`, the only unworkable amounts are those in `(M − MIN_OUTPUT, M)` that are not an achievable subset sum, where `M` is the sum of the largest `MAX_YED_INPUTS` coins — which is why every functional provocation of `change-floor` must now be written as "50 cents under the whole spendable balance", never as a fixed amount |
| — | Consequence for stage 4: with all coins ≥ `MIN_OUTPUT`, greedy-with-extension always succeeds once it can cross the target (each further coin lifts the change by ≥ `MIN_OUTPUT`), so the bounded search is reachable **only** through the H11 input cap — a wallet of many small coins whose greedy prefix hits 250 inputs before the target, where a subset of larger coins does not | The stage-4 unit case is built that way (300 × $1.00 plus one $255.50 coin, target $255.00); do not "simplify" it to a small coin set, which would silently stop exercising stage 4 |
| RED-2's DigiByte counterpart is an equality (the redemption burns exactly the debt) | Ycash's RED-2 is `burn >= mintedCents` (`state.cpp:313-314`), so over-burning is already block-valid | H4 needs no consensus change at all: the builder simply leaves the sub-dollar remainder unassigned. `yed_redeem`/`yed_claim` report `burnedCents` as the debt and `extraBurnCents` beside it (`built.burnCents - built.extraBurnCents` in `rpc/yellowbackwallet.cpp`), so the two fields sum to what the chain sees |
| DigiByte's `lockunspent` has no notion of a lock the wallet must not undo | `CWallet::UnlockCoin`/`LockCoin` take a **non-const** `COutPoint&` (`ref/ycash/src/wallet/wallet.h`), and `src/wallet/wallet.{h,cpp}` is the zero-diff set | The overlay keeps its own `ourLocks` set and adds `IsYellowbackLocked`/`ReleaseLock`/`ReapplyLocks` to `yellowback/wallet.{h,cpp}`; `lockunspent` refuses before it applies anything (it collects the outpoints, checks them all, then acts), and `lockunspent true` with no argument re-applies the overlay locks after `UnlockAllCoins()`. Every call site passes a local copy, because the stock signature is non-const |
| — | H8's `Reconcile()` takes `cs_yellowback` and then `cs_wallet`, while every import RPC holds `LOCK2(cs_main, cs_wallet)` for its whole body: calling it inline would take the two in the order the notifier thread takes them the other way round | A one-line RAII guard (`YellowbackReconcileOnExit`) declared **before** the `LOCK2` in `importprivkey`, `importaddress`, `importwallet_impl` and `z_importkey`: destructors run in reverse order, so the reconcile happens after `cs_wallet` is released — the same way `yed_lockcoins` calls it with no lock held. Rule 7: not one existing line moved |
| Every DigiDollar spend is judged by consensus, so a wallet-side "are you sure" has nothing to be careful about | H7's guard sits in `sendrawtransaction` **before** `AcceptToMemoryPool`, so a too-broad rule would pre-empt the overlay's own refusals: a CLAIM whose burn leaves no change carries a REDEEM payload with **zero** assignments, and `yellowback_claim.py` asserts the `yellowback-vault-spend` refusal that MP-1 raises | The guard fires only for a transaction that spends a mine-owned `Tokens` outpoint and carries **no** payload, an unreadable one, a MINT payload, or a TRANSFER with no assignments. A REDEEM payload is always let through (MP-1 judges it). Found by reading `yellowback_claim.py:169-172` before running it |
| — | `yellowback_lifecycle.py`'s `plain_yec_burn_recorded` case is exactly the transaction H7 refuses, and the H5 lock is exactly what `coin_of()` hands it | The step now reads as the documented escape route: `yed_unlockcoin` then `sendrawtransaction(hex, False, True)`. Any future test that burns YED on purpose must do the same |
| — | `scripts/extract_spec.py` reads `ycash-dd/doc/yellowback-rpc.md` from the **workspace root**, not from the worktree a branch is being built in, so `make spec` on a branch would either regenerate from the merged tree's document or require writing into the shared main checkout | Generate into a throwaway root instead: copy `scripts/extract_spec.py`, `docs/plans/…`, and the branch's `doc/yellowback-rpc.md` into a scratch directory shaped like the workspace and run the script there, then copy the produced `yellowback-rpc-contract.json` into the branch. `make spec` in the workspace stays for the merged tree, and it must be re-run after the merge |

### 13.8 Rows added while building Phase 5 (2026-09-11, `feature/yellowback-sf-p5`)

| DigiByte does X (Y, mechanism M) | Ycash equivalent Z, which lacks M | Adaptation W |
|---|---|---|
| DigiDollar is consensus, so "the network has already built on this block" is not a case: a node re-derives the same verdict whenever it connects the block | BLK-2 clause 3 (L11) suppresses a rejection when `pindexBestHeader` already descends from the block by `VALVE_BLOCKS` of work (`ycash-dd/src/yellowback/index.cpp`, `ShouldSuppressCatchUp`). That predicate is only true once the **header** chain has arrived. A node that learns the branch from a peer which relays the *block* before the full header chain (Ycash's direct fetch of `inv`-announced blocks while the tip is recent, `ref/ycash/src/main.cpp:6281-6286`) connects the rule-breaking block with `pindexBestHeader` still at or near its own tip, so clause 3 does not fire and it **rejects** | Observed on an enforcing node that learned a suppressed branch through a second enforcing node rather than from the miner: `yellowback: rejecting block … at H` is followed in the same millisecond by three `valve: noted header …` lines, i.e. the descendants' headers arrived after the block. Clause 3 is therefore best-effort, not a guarantee; the ACT-7 valve is what bounds the outcome (it trips within `VALVE_BLOCKS`). §8.1's "A node that catches up after an outage never rejects a block the network has already built six blocks on" should read "usually does not reject … and in any case rejoins within six blocks". Pinned by `yellowback_enforcement.py` case 15 variant 1 (the plan's shape — the node reconnects to the miner and headers do lead — which passes) and by the comment on `catchup_recover` |
| A DigiDollar test can mine a competing branch with `invalidateblock` freely, because every node applies the same rule and no peer is scored for a branch the node itself invalidated | `invalidateblock` in a six-node Yellowback scenario makes peers relay headers whose parent the node has just marked `BLOCK_FAILED_VALID`, and Ycash answers those with the stock `bad-prevblk`/"prev block not found" (`ref/ycash/src/main.cpp:4555-4558`, DoS 10/100) — the N1 clause covers only hashes in `Rejected`, not hashes an operator invalidated by hand. The resulting `banscore == 10` is indistinguishable, in `getpeerinfo`, from a Yellowback ban | Phase 5 builds every reorg **naturally**: `split_network()`, or one pool disconnected with `disconnectnode` mining a competing branch, then reconnected. `invalidateblock` survives only where the node is taken *off* a branch it must stop relaying (`catchup_recover`), never where a peer could then send a descendant header |
| — | A second stock DoS source the same assertions trip over: an adversarial vault spend with a short `nExpiryHeight` is re-relayed by node 1 after the enforcing branch out-mines it, and `AcceptToMemoryPool` answers `tx-expired` at DoS 10 (`ContextualCheckTransaction`) | Every adversarial spend in `yellowback_enforcement.py` carries `nExpiryHeight = 0` (M13 — MP-1 refuses it on every overlay node either way, which is the wanted behaviour), and `clear_stock_mempool()` restarts node 1 whenever its mempool is non-empty after a reorg. Ycash 4.5 has no mempool persistence (`grep persistmempool src/init.cpp` → nothing), so a restart is a clean eviction |
| — | A transaction with `nExpiryHeight = 0` never leaves the stock node's mempool, so after a reorg node 1 re-includes it in **every** later block it mines; the next "correct spend mined by the stock node" case then fails for the earlier transaction's verdict | Same helper: `clear_stock_mempool()` after each convergence.  Without it a passing case is silently contaminated by the previous one |
| — | The framework's topology (a star on node 1 plus `2↔3↔4`, plus `0↔2`) has articulation points inside the *enforcing* half: taking node 3 out (a storage-fault run, an isolated pool mining a competing branch) partitions node 2 from node 4, and taking node 2 out (the kill-switch restart with `-yellowbackenforce=0`) partitions node 0 from every pool | `yellowback_enforcement.py` overrides `EDGES` to make `{0, 2, 3, 4}` a complete graph (`+ [(2, 4), (0, 3), (0, 4)]`). Node 1 is still the only route to the stock miner and node 5 still hangs off node 1 alone, so §6.0 item 2's roles are unchanged |
| DigiByte's `getblocktemplate` and its validator are the same code, so a template can never contain what the validator rejects | `-yellowbacktestfault=template` (TPL-3's lever) consumes its one shot only for a candidate that is **block-invalid and would be skipped**, and `FilterTemplate` only ever sees transactions in the node's own mempool — which MP-1 keeps such a spend out of, unconditionally. There is therefore **no live configuration** in which the functional lever fires: no `-yellowbacktemplatepolicy` value relaxes MP-1, a chained mint-then-spend is impossible (MINT-2 puts every new vault's `lockHeight` at least `48 − REF_WINDOW + …` blocks in the future), and the `ConnectTip` sweep removes a spend the window invalidated before any template is built | TPL-3 is pinned by the unit case `tpl3_template_fault_keeps_block_invalid_spend` (`ycash-dd/src/test/yellowback_index_tests.cpp`), which drives `policy::FilterTemplate` over the same candidate three times (skipped → kept under the fault → skipped again) and asserts `CheckConnect` rejects the block that template would have produced.  The functional half (`yellowback_enforcement.py`, `tpl3_template_fault_disagrees`) asserts the reason the lever cannot fire there: MP-1 holds the line |
| A DigiDollar vault spend is policed whatever the vault's status | BLK-1 polices ACTIVE vaults only (K3), so the plan's Phase 5 case 4 ("before activation the same rule-breaking block is accepted … and the vault is recorded `unbacked`") is not constructible as written: MINT-4 voids every pre-activation mint (K16), and `unbacked` is written only for an ACTIVE vault whose spend failed RED-1..4 (`state.cpp`, `ApplyVaultSpend`) | Case 4 asserts the constructible half — a pre-activation VOID vault, a rule-breaking spend of it, accepted by every node with `rejectedBlocks == 0` — and the `unbacked` half is asserted where it is actually produced, on node 5 in cases 1 and 2. Likewise `unbacked` is true only for the no-burn and short-burn variants: the RED-3 fee variants carry the full burn, so IN-3 leaves nothing unbacked |
| — | A K3 VOID vault needs a `claimHeight` in the past to be claim-path-spendable in the same test; a mint with a class-A lock always has `lockHeight ≥ refHeight + 48` | `build_mint_tx(..., lock_blocks=-80, term_class='A')`: MINT-2 fails on the lock (VOID) and `lockHeight`/`claimHeight` are already past — the exact shape K3 describes. It must be mined by the **stock** node, because TPL-2 declines any MINT whose verdict would be VOID |
| DigiByte's fork warning fires from `pindexBestInvalid`, which grows from indexed blocks | P1: after a live rejection the stock warning never fires, and the valve raises its own through `SetMiscWarning` | Confirmed end to end: `getinfo.errors` on every enforcing node carries `Yellowback: work valve tripped at height H (rejected root …); enforcement off until restart` and **not** the stock "invalid chain … longer than our best chain" text (`yellowback_enforcement.py` case 9) |
| — | Convergence after a trip needs one more announcement (P3) — and so does convergence after *any* branch swap in a six-node regtest: a node whose peers are all silent never learns of a heavier chain, because nothing announces a tip that has not just been mined | Every convergence loop in `yellowback_enforcement.py` and `yellowback_stock_node.py` mines one block at a time until the tips agree, rather than mining a fixed count and syncing once |
