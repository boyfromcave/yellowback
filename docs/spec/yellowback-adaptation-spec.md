# Ycash Yellowback (YED) — adaptation spec (normative v1 protocol)

**Status:** DECIDED. This file is the normative protocol: §3 of the development plan, reproduced
verbatim so implementers and reviewers have one file to cite for rule identifiers (**MINT-1**,
**XFER-2**, **RED-7**, …). Every design decision, the rationale for each rule, the audit history,
the architecture, the federation coordinator, the phased work plan and the trust statement live in
[`../plans/yellowback-v1-development-plan.md`](../plans/yellowback-v1-development-plan.md); when the two
disagree, the plan wins and this file is regenerated from it.

**Base:** Ycash `v4.5.0` (`624c12814`) · **Reference:** DigiByte `v9.26.5` (`05b50e229d`)
**Mechanism crosswalk:** [`../mapping.md`](../mapping.md) — read that first.

Section numbering below matches the plan (§3.1–§3.10) so cross-references resolve in both files.

---

## 3. Yellowback v1 protocol (normative)

Naming: **Yellowback** is the system, **YED** is the unit (AGENTS.md rule 6).

Everything in this section is deterministic given the block sequence and the parameters. Words in
**bold caps** are rule identifiers used by the test plan.

### 3.1 Units and constants

| Name | Value | Notes |
|---|---|---|
| `CENT` | 1 | YED amounts are integer US cents; `100 = $1.00` |
| `MICRO_USD` | 1 | prices are integer micro-USD per YEC; `1,000,000 = $1.00` |
| `COIN` | 100,000,000 | zatoshi per YEC (existing) |
| `BLOCKS_PER_HOUR` | 48 | 75-second target spacing post-Blossom |
| `BLOCKS_PER_DAY` | 1,152 | |
| `PRICE_MAX_AGE` | 48 blocks | attestation older than this is not a price |
| `PRICE_MIN` / `PRICE_MAX` | 100 / 100,000,000 µUSD | $0.0001 – $100.00 per YEC (DigiByte bounds) |
| `MINT_WINDOW` | 40 blocks | protocol constant; equals `DEFAULT_POST_BLOSSOM_TX_EXPIRY_DELTA` (`ref/ycash/src/main.h:78-79`) but does not follow `-txexpirydelta` |
| `MINT_EVAL_LAG` | 2 blocks | **wallet-side, not protocol**: `evalHeight = indexTip − MINT_EVAL_LAG`, so a reorg shorter than 3 blocks cannot change the snapshot a mint committed to (C4); `-yellowbackmintlag` overrides (0..36) |
| `ROSTER_GRACE` | 1,152 blocks | how long the previous roster stays mintable after its successor is revealed |
| `YELLOWBACK_FEE` | 1,000 zat | flat transaction fee, = `DEFAULT_FEE` (`ref/ycash/src/policy/fees.h:15`). Not only convention: ZIP-401's mempool limiter adds `LOW_FEE_PENALTY` to the eviction weight of any transaction paying less (`ref/ycash/src/mempool_limit.cpp:151-157`), so `-yellowbackfee` is clamped to ≥ `DEFAULT_FEE` (C16) |
| `TOKEN_VALUE` | 10,000 zat | YEC carried by every YED output; ≥ 100× the dust floor (`GetDustThreshold`, `ref/ycash/src/primitives/transaction.h:460`) |
| `MIN_MINT` / `MAX_MINT` | 10,000 / 1,000,000 cents | $100 / $10,000 (param) |
| `MIN_OUTPUT` / `MAX_OUTPUT` | 100 / 10,000,000 cents | $1 (DigiByte's `minOutputAmount`) / $100,000 (param; DigiByte's `maxMintAmount`, C17) |
| `SUPPLY_CAP` | 100,000,000 cents | $1,000,000 mainnet v1 (param; 0 = none on regtest) |
| `MAX_PAYLOAD` | 80 bytes | Ycash `nMaxDatacarrierBytes − 3` |
| `HEALTH_CAP` | 30,000 % | as DigiByte |
| `VOL_1H_BPS` / `VOL_24H_BPS` | 2,000 / 3,000 | 20 % / 30 % |
| `VOL_COOLDOWN` | 1,728 blocks | 36 h, DigiByte's `COOLDOWN_BLOCKS` in Ycash blocks |
| `ROSTER_N` / `ROSTER_K` | 9 / 5 | mainnet & testnet; regtest 3 / 2 |

Lock tiers (`tierBlocks` at 75 s; ratios from `ref/digibyte/src/consensus/digidollar.h:72-84`):

| Tier | Period | `tierBlocks` | Ratio |
|---|---|---|---|
| 0 | 1 hour | 48 | 1000 % |
| 1 | 30 days | 34,560 | 500 % |
| 2 | 90 days | 103,680 | 400 % |
| 3 | 180 days | 207,360 | 350 % |
| 4 | 1 year | 420,480 | 300 % |

Per-network parameters (`src/yellowback/params.cpp`): `startHeight`, `genesisAnchor` (outpoint),
`genesisRosterScript` (the k-of-n redeem script, so the roster is known before its first spend),
address version bytes (D10), `SUPPLY_CAP`, `MAX_MINT`. Regtest takes the first three from
`-yellowbackstartheight=<h>`, `-yellowbackgenesisanchor=<txid:n>` and `-yellowbackgenesisroster=<hex>`
(all three required together, refused on any other network) so tests can create the anchor on
chain first and then restart with `-yellowback` (C2).

**Regtest overrides** (`params.cpp`, network `"regtest"` only; ratios, formulas and every rule are
identical, only block counts shrink so a test can walk through a full lifecycle in seconds — the
protocol is height-based and never reads a clock, so this changes nothing but the numbers):

| Parameter | Mainnet / testnet | Regtest |
|---|---|---|
| `tierBlocks` tiers 0–4 | 48 / 34,560 / 103,680 / 207,360 / 420,480 | 48 / 96 / 144 / 192 / 240 |
| `ROSTER_GRACE` | 1,152 | 48 |
| `VOL_COOLDOWN` | 1,728 | 96 |
| `PRICE_MAX_AGE`, `MINT_WINDOW`, `MINT_EVAL_LAG` | 48 / 40 / 2 | unchanged (tied to expiry and reorg depth, not to time) |
| volatility windows `BLOCKS_PER_HOUR` / `BLOCKS_PER_DAY` (§3.6) | 48 / 1,152 | 48 / 96 (G5) |
| `ROSTER_N` / `ROSTER_K` | 9 / 5 | whatever the test's genesis roster script says (2-of-3 for fast tests, 5-of-9 for the production-shape tests, §6.0) |
| `SUPPLY_CAP` | 100,000,000 cents | 0 (none) unless `-yellowbacksupplycap` is passed |

### 3.2 Payload encoding

The Yellowback payload is the data of the transaction's **only** `OP_RETURN` output (policy forbids
two), and that output must be exactly `OP_RETURN <one push of 4..80 bytes>`; `Solver` accepts any
push-only tail as `TX_NULL_DATA` (`ref/ycash/src/script/standard.cpp:102`), so this shape rule is
ours (B12). A transaction with an `OP_RETURN` that does not have this shape or does not begin with
the magic is a non-Yellowback transaction (its inputs are still processed by **IN-1..3** below).
All multi-byte integers are fixed-width little-endian; nothing in the payload uses `CompactSize`
or `VARINT` (B11).

```
magic   2 bytes   0x59 0x42 ("YB")
version 1 byte    0x01
type    1 byte    0x01 MINT | 0x02 TRANSFER | 0x03 REDEEM | 0x10 PRICE
body    variable  per type; total ≤ 80 bytes; trailing bytes → malformed
```

| Type | Body | Size (incl. 4-byte header) |
|---|---|---|
| MINT | `tier u8`, `cents u32le`, `lockHeight u32le`, `evalHeight u32le`, `ownerPubKey 33 B compressed` | 50 |
| TRANSFER | `count u8`, then `count ×` (`vout u8`, `cents u32le`) | 5 + 5·count → count ≤ 15 |
| REDEEM | same body as TRANSFER (assigns YED change); `count` may be 0 | |
| PRICE | `priceMicroUsd u64le` | 12 |

There is no rotation payload: a roster rotation is an anchor spend whose `vout[0]` pays a
different P2SH, with no `OP_RETURN` at all (§3.7, C9).

Malformed payload (bad magic/version/type, short/long body, `vout` out of range, duplicate `vout`,
`vout` pointing at the `OP_RETURN`, `cents == 0`) ⇒ the transaction is treated as **non-Yellowback**
for outputs and as an ordinary spend for inputs (**IN-1..3**). Unknown `type` ⇒ same. This is the
forward-compatibility rule: a future version bump is ignored by v1 nodes, never mis-parsed.

One more encoding rule, for determinism: a transaction with **more than one** `OP_RETURN` output
(non-standard, but a miner may include it) is non-Yellowback regardless of contents. The decoder is a
bounds-checked reader over a `std::vector<unsigned char>`; it never uses `CDataStream` so it cannot
throw.

### 3.3 Scripts

**Roster script** (also the anchor's redeem script). Keys must be 33-byte compressed encodings
(the size arithmetic in D3 depends on it; a 65-byte key is rejected everywhere a roster is built or
parsed, D7), sorted ascending so every party derives the same script:

```
<k> <Q1> … <Qn> <n> OP_CHECKMULTISIG            (k=5, n=9 mainnet)
```

**Vault script** (redeem script of the P2SH collateral output; `Q1…Qn` in the same sorted order):

```
<lockHeight> OP_CHECKLOCKTIMEVERIFY OP_DROP
<ownerPubKey> OP_CHECKSIGVERIFY
<k> <Q1> … <Qn> <n> OP_CHECKMULTISIG
```

`lockHeight` is pushed as a minimal `CScriptNum` and must be `< LOCKTIME_THRESHOLD`
(`ref/ycash/src/script/script.h:30`), i.e. a block height.

**Vault scriptSig** (built by `yed_redeem` + co-signers; stack order matters):

```
OP_0 <qsig_1> … <qsig_k> <ownerSig> <vaultScript>
```

The spending transaction sets `nLockTime = lockHeight`, `vin[0].nSequence = 0xFFFFFFFE`, and a
normal `nExpiryHeight` (tip + 40); Ycash's `CheckFinalTx` then admits it once the tip is at or above
`lockHeight` (`ref/ycash/src/main.cpp:1566`). Its `STANDARD_LOCKTIME_VERIFY_FLAGS` is
`LOCKTIME_MEDIAN_TIME_PAST` (`ref/ycash/src/consensus/consensus.h:49`), which affects only
time-based locks; vault locks are heights (F5). Signature hash: `SignatureHash(vaultScript, tx, nIn,
SIGHASH_ALL, vaultValue, consensusBranchId)` as `ref/ycash/src/rpc/atomicswap.cpp:760-762`, with
`consensusBranchId = CurrentEpochBranchId(chainActive.Height() + 1, consensus)` for **every**
signer (owner and co-signers) — the convention `signrawtransaction` uses
(`ref/ycash/src/rpc/rawtransaction.cpp:1024`); it differs from the atomic-swap code's `Height()`
only at an upgrade boundary, and no upgrade is scheduled (NU5 is `NO_ACTIVATION_HEIGHT` on every
network). Signatures must be placed in the scriptSig in roster key order; the combiner sorts them by
matching each signature to a key with `CPubKey::Verify`.

Relay constraints the spend already satisfies, and that tests must pin: mempool verification uses
`STANDARD_SCRIPT_VERIFY_FLAGS` (`ref/ycash/src/policy/policy.h:32-40`), so pushes must be minimal
(`MINIMALDATA`: `lockHeight` as a minimal `CScriptNum`, `k`/`n` as `OP_5`/`OP_9`, the dummy as
`OP_0`), exactly one element may remain after execution (`CLEANSTACK`: `CHECKMULTISIG` leaves one
`true`), and signatures must be low-S (`LOW_S`: `CKey::Sign` produces normalized signatures).
`AreInputsStandard` accepts a P2SH input whose redeem script is not a standard template as long
as it has ≤ 15 accurate sigops (`ref/ycash/src/policy/policy.cpp:173-178`) — the same path the
atomic-swap HTLC relies on. The anchor's redeem script *is* a template (`TX_MULTISIG`), so its
scriptSig must hold exactly `OP_0`, `k` signatures and the script (`ScriptSigArgsExpected` = k + 1,
`ref/ycash/src/script/standard.cpp:146-149`; `policy.cpp:182-183`) — which is what
`signrawtransaction`'s combiner produces. `IsStandard`'s "x-of-3" limit (`policy.cpp:42-50`)
applies to **bare** multisig outputs only; anchors and vaults are P2SH and unaffected (C15).

The signature combiner matches each returned signature to a roster key with `CPubKey::Verify`
over the DER bytes **without** the trailing hashtype byte (C24), and places them in roster key
order; a co-signer verifies the owner's signature the same way under the branch ID it would
itself sign with, so a branch-ID disagreement surfaces as a RED-7 refusal (C11).

**Yellowback token output**: `OP_DUP OP_HASH160 <keyHash> OP_EQUALVERIFY OP_CHECKSIG` with value
`TOKEN_VALUE`. The overlay does not require this shape or value (any non-`OP_RETURN` output may be
assigned YED); the wallet always produces this shape.

### 3.4 Transaction templates (what the wallet builds)

**MINT** (`yed_mint <cents> <tier> [from]`):

| Index | Output | Value |
|---|---|---|
| vin[*] | wallet YEC inputs (never YED-bearing, never vaults); **or none** when the collateral is funded from a `ys1…` address (below) | |
| vout[0] | P2SH(vaultScript) | exactly `requiredZat(cents, tier, Snapshots[evalHeight])` (§3.6), rounded up to a multiple of 1,000 zat |
| vout[1] | P2PKH(owner's fresh key) — receives all minted cents | `TOKEN_VALUE` |
| vout[2] | `OP_RETURN` MINT payload | 0 |
| vout[3] | YEC change (optional; transparent funding only) | |

**Funding source** (`from`, I2): omitted — any confirmed transparent output of the wallet
(smallest-first, F3); an `s1…` address — only that address's confirmed outputs; a `ys1…` address
— the collateral, the token value and the fee come from that address's Sapling notes in the
**same** transaction: `vShieldedSpend` over the selected notes (largest-first, as `z_sendmany`;
at most `MAX_SAPLING_SPENDS` = 20), `valueBalance = vout[0].nValue + TOKEN_VALUE + fee`, no
transparent inputs, and the change is a Sapling output back to the funding address. The three
transparent outputs and the payload are identical in every case, so MINT-1..7 do not see the
difference (TX-0, D13).

With `indexTip` the index's synced height and `L = MINT_EVAL_LAG` (default 2, C4):
`evalHeight = indexTip − L`; `nExpiryHeight = evalHeight + MINT_WINDOW` (so the mint cannot
confirm at `H > evalHeight + MINT_WINDOW`, MINT-2); `lockHeight = evalHeight + tierBlocks +
MINT_WINDOW`. For every height the transaction can confirm at, `H ∈ [indexTip + 1, evalHeight +
40]`, this gives `tierBlocks ≤ lockHeight − H ≤ tierBlocks + 39 − L ≤ tierBlocks + MINT_WINDOW`,
so MINT-2 holds at every possible confirmation height; and the mempool's expiring-soon rule
(`nextHeight + 3 ≤ nExpiryHeight`) holds for `L ≤ 36`. Because every input to MINT-4/5 is fixed at
`evalHeight`, the wallet knows before signing whether the mint will register; the 2 % margin of
revision 2 is gone (B3), and a reorg must be longer than `L` blocks to disturb the snapshot.

**TRANSFER** (`yed_send`, `yed_sendmany`): YED inputs (confirmed only) + YEC fee inputs
(confirmed only, F3);
outputs: one `TOKEN_VALUE` P2PKH per recipient, one for YED change, `OP_RETURN` TRANSFER
payload assigning cents to those vouts, YEC change.

**REDEEM** (`yed_redeem <vaultTxid> [to]`): `vin[0]` = vault outpoint; `vin[1..]` = YED inputs
totalling ≥ `requiredBurn` (§3.7). **No YEC inputs** (C10): every YED input carries
`TOKEN_VALUE` = 10 × `YELLOWBACK_FEE` and a VOID release has the collateral itself. Outputs: collateral
(value = vault value + surplus token value − `YELLOWBACK_FEE` − `TOKEN_VALUE` × number of YED change
outputs) to the **collateral destination**, optional YED change (`TOKEN_VALUE`) with a REDEEM payload
(`count = 0` if none, but the payload is still present so the transaction is self-describing).

**Collateral destination** (`to`, I2): omitted — a fresh transparent key of the wallet at
`vout[0]`; an `s1…` address — that P2PKH at `vout[0]`; a `ys1…` address — a single Sapling
output (`vShieldedOutput`, `valueBalance = −collateral`) encrypted under the wallet's
`ovkForShieldingFromTaddr` key so it is recoverable from the seed, as `z_sendmany` does for
t→z; the YED change, if any, is then `vout[0]` and the payload `vout[1]`. The vault input and
the YED inputs are added to `TransactionBuilder` **unsigned** and signed after `Build()` with the
same code as the transparent shape — the ZIP-243 digest does not cover `scriptSig`s, so the
binding signature stays valid (D9).

**PRICE** (federation coordinator, built by `yed_createpricetx`): `vin[0]` = current anchor;
at most one refill input, **absorbed entirely into the new anchor** (no change output, C6);
`vout[0]` = P2SH(rosterScript) — the **same** script as the spent anchor (the new anchor, value =
anchor + refill − `YELLOWBACK_FEE`); `vout[1]` = `OP_RETURN` PRICE. Exactly two outputs.

**ROTATION** (federation, rare): `vin[0]` = current anchor, optional refill as above, `vout[0]` =
P2SH(*new* roster script), **no `OP_RETURN`** (C9). Exactly one output.

### 3.5 State

```
Tip            { height, blockHash, schemaVersion, network }
Params         (in code)
Anchor         { outpoint, nValue, scriptPubKey }
Rosters        ordered list of { script, revealHeight }; Rosters[0] = { genesisRosterScript, startHeight }
Prices         height → priceMicroUsd            (only heights with a valid attestation; last in block wins)
Vaults         outpoint → { ownerPubKey, tier, lockHeight, collateralZat, mintedCents,
                             mintHeight, status ∈ {ACTIVE, VOID, CLOSED}, closeHeight,
                             closingTxid, burnedCents, errBpsAtClose, requiredBurnAtClose,
                             rosterIndex }
Tokens         outpoint → { cents, nValue, scriptPubKey, height }
TxLog          txid → { height, type, verdict, yedIn, yedOut, burned, assigned[] (outpoint, cents,
                        scriptPubKey), closedVaults[] }   (every payload-bearing tx and every tx
                        spending a Tokens/Vaults/Anchor outpoint; source for history RPCs, E1)
Totals         { supplyCents, collateralZat, activeVaults, voidVaults }
Volatility     { lastBreachHeight }              (mint freeze until lastBreachHeight + VOL_COOLDOWN)
Snapshots      height → { blockHash, supplyCents, collateralZat, price, healthPct, dcaBps, errBps, mintFrozen }
Undo           blockHash → list of inverse operations for that block
```

`Snapshots` are written for every block ≥ `startHeight` (≈ 60 bytes each) and are what
`yed_gethistory` and the Phase-B consensus rule read.

### 3.6 Derived quantities (integer, `arith_uint256`)

**Price at height H** — `price(H)`: the entry in `Prices` with the greatest height `h ≤ H` such
that `H − h ≤ PRICE_MAX_AGE`; undefined otherwise.

**Health** — with `S = supplyCents`, `C = collateralZat` **as they stand immediately before the
transaction being evaluated** (earlier transactions in the same block have already been applied),
and `p = price(H)`:

```
health(H) = HEALTH_CAP                              if S == 0
          = 0                                       if p undefined      (fail closed)
          = min(HEALTH_CAP, floor(C · p / (COIN · S · 100)))   otherwise
```
(Check: 1 000 YEC at $0.05 backing $10 → `1e11·5e4 / (1e8·1000·100)` = 500 %.)

**DCA multiplier** (`ref/digibyte/src/consensus/dca.cpp:53-58`):

| health | `dcaBps` |
|---|---|
| ≥ 150 | 10,000 |
| 120–149 | 12,500 |
| 110–119 | 15,000 |
| < 110 | 20,000 |

**Required collateral** for `cents` at tier ratio `R %` (DigiByte's formula, `txbuilder.h`
`CalculateRequiredCollateral`):

```
requiredZat = ceil( cents · R · dcaBps · COIN / (100 · p) )
```

Worst case magnitude `1e7 · 1000 · 20000 · 1e8 ≈ 2e22` exceeds 64 bits, hence `arith_uint256`.

**ERR ratio** (`ref/digibyte/src/consensus/err.cpp:38-41,53`):

| health | `errBps` |
|---|---|
| ≥ 100 | 10,000 (ERR inactive) |
| 95–99 | 9,500 |
| 90–94 | 9,000 |
| 85–89 | 8,500 |
| < 85 | 8,000 |

**Required burn** to release a vault that minted `M` cents: `requiredBurn = ceil(M · 10000 / errBps)`
(`err.cpp:100`).

**Volatility** — let `p0 = price(H)`, `p1 = price(H − BLOCKS_PER_HOUR)`, `p24 = price(H −
BLOCKS_PER_DAY)` (each undefined ⇒ that window is not evaluated). `breach(H)` iff
`|p0 − p1| · 10000 ≥ VOL_1H_BPS · p1` or `|p0 − p24| · 10000 ≥ VOL_24H_BPS · p24`. If `breach(H)`,
`lastBreachHeight := H`. `mintFrozen(H)` iff `H ≤ lastBreachHeight + VOL_COOLDOWN`.

### 3.7 Rules

Blocks below `startHeight` are ignored completely (not even the tip is recorded). At `startHeight`
the block is applied without a parent check and must contain the genesis anchor transaction with
`vout[genesisAnchor.n].scriptPubKey == P2SH(HASH160(genesisRosterScript))`, otherwise the index is
unhealthy (B9); `Anchor` and `Rosters[0]` are initialised from `Params` **before** any transaction
of that block is processed, so a spend of the genesis anchor inside block `startHeight` is seen
(E6). Within a block, transactions are processed in block order and each transaction's inputs are
processed before its outputs. Every transaction that carries a payload or spends a `Tokens`,
`Vaults` or `Anchor` outpoint gets a `TxLog` entry (E1).

**IN-1** Every input that spends an outpoint in `Tokens` removes it and adds its cents to `yedIn`.
**IN-2** Every input that spends an outpoint in `Vaults` with status ACTIVE or VOID sets the vault
to CLOSED (`closeHeight = H`, `closingTxid`, `errBpsAtClose = Snapshots[H − 1].errBps`,
`requiredBurnAtClose = RequiredBurn(mintedCents, errBpsAtClose)` for ACTIVE and 0 for VOID, F1),
and, if it was ACTIVE, subtracts its `collateralZat` from `Totals.collateralZat` and decrements
`activeVaults`.
**IN-3** After outputs are processed, `burned = yedIn − yedOut`; `Totals.supplyCents −= burned`;
`burned` is recorded on every vault closed by this transaction (split is informational).

**TX-0** A coinbase has `yedOut = 0` regardless of payload (and registers no vault, not even
VOID). Shielded components (`vJoinSplit`, `vShieldedSpend`, `vShieldedOutput`, `valueBalance`)
play no part in any rule: they belong to the YEC side of the transaction (D13, I1). YED can still
only be assigned to transparent outputs, because an assignment names a `vout` index.

**MINT-1** payload MINT, well-formed. **MINT-2** `tier ∈ {0..4}`, `MIN_MINT ≤ cents ≤ MAX_MINT`,
`lockHeight < LOCKTIME_THRESHOLD`, `tierBlocks ≤ lockHeight − H ≤ tierBlocks + MINT_WINDOW`
(DigiByte's canonical window, `validation.cpp:1377`), `startHeight ≤ evalHeight ≤ H` and
`H − evalHeight ≤ MINT_WINDOW`. **MINT-3** `vout.size() ≥ 3`; `vout[0]` is P2SH and its hash
equals `HASH160(vaultScript(lockHeight, ownerPubKey, roster))` for `roster = Rosters.back()`, or
`roster = Rosters[size−2]` if `H ≤ Rosters.back().revealHeight + ROSTER_GRACE` (rotation grace,
B21); `ownerPubKey` is a valid compressed key. **MINT-4** with `E = Snapshots[evalHeight]`:
`E.price` defined; `E.healthPct ≥ 100` (else `minting-blocked-during-err`, `validation.cpp:2707`);
`¬E.mintFrozen`. **MINT-5** `vout[0].nValue ≥ requiredZat(cents, tier, E.price, E.dcaBps)`.
**MINT-6** `Totals.supplyCents + cents ≤ SUPPLY_CAP` (if cap ≠ 0), evaluated at `H`. **MINT-7**
`vout[1]` is not the `OP_RETURN`. MINT-4 and MINT-5 read only the snapshot, so they are a pure
function of the payload and a block every node has already applied (B3).

If MINT-1..7 hold: `Vaults[txid:0] = ACTIVE {…}`, `Tokens[txid:1] = cents`, `supplyCents += cents`,
`collateralZat += vout[0].nValue`, `yedOut = cents`. If MINT-1 holds but any of MINT-2..7 fails and
`vout[0]` is P2SH: `Vaults[txid:0] = VOID` (so it can be tracked and released), `yedOut = 0`. Note
that `yedIn` in a MINT is always burned (a mint never assigns YED to outputs other than by
minting).

**XFER-1** payload TRANSFER or REDEEM, well-formed; every assigned `vout` exists and is not the
`OP_RETURN`; `MIN_OUTPUT ≤ cents ≤ MAX_OUTPUT` per assignment. **XFER-2** `Σ assigned cents ≤
yedIn` (TRANSFER and REDEEM share this rule; the difference `yedIn − Σ` is burned — for a TRANSFER
built by the wallet it is always 0, for a REDEEM it is the burn). **XFER-3** `yedIn > 0`.

If XFER-1..3 hold: each assignment creates `Tokens[txid:vout] = cents`; `yedOut = Σ`. If XFER-1 or
XFER-3 fails, or `Σ > yedIn`, nothing is assigned and `yedOut = 0` (all inputs burned, D18). This is
the most forgiving rule that is still total: an honest wallet bug that under-assigns loses only the
unassigned remainder, never the whole input.

**PRICE-1** some input `vin[i].prevout == Anchor.outpoint` (any index — the anchor is consumed
wherever it sits). **PRICE-2** `vout[0]` is P2SH. If both hold the anchor moves: `Anchor = {txid:0,
vout[0].scriptPubKey}`; the redeem script (last push of `vin[i].scriptSig`) is appended to
`Rosters` with `revealHeight = H` iff it parses as `<k> <keys…> <n> OP_CHECKMULTISIG` with
`1 ≤ k ≤ n ≤ 13` and differs from `Rosters.back().script` (a non-parseable script moves custody but
never becomes a roster). **PRICE-3** payload PRICE with `PRICE_MIN ≤ price ≤ PRICE_MAX`, PRICE-1
and PRICE-2 held, **and `vout[0].scriptPubKey` equals the spent anchor's `scriptPubKey`** (B8) ⇒
`Prices[H] = price`; if several anchor spends chain inside one block, the last one in block order
wins (B7). An anchor spend that changes the script (a rotation, C9), or carries a malformed or
absent payload, moves the anchor without recording a price. An anchor spend whose `vout[0]` is not P2SH
breaks the chain of custody: `Anchor` becomes null and no further prices are accepted until a
software release with a new genesis anchor (operator failure, §8). A PRICE payload on a transaction
that does not spend the anchor is non-Yellowback.

**SNAP** After the last transaction of the block: recompute `breach(H)`, write `Snapshots[H]`.

**UNDO** Every mutation in the block is logged; `Undo[blockHash]` reverses them exactly. Applying
then undoing a block must restore byte-identical state (tested).

### 3.8 Policy checks (wallet and federation, not state rules)

These are computed by `yed_validaterawtransaction` and used by the wallet before broadcasting and by
federation members before co-signing. They do **not** change the state machine (D18) but they are
the rules §9 would promote to consensus.

- **RED-0** the co-signer's index is healthy and `synced` (its tip is `chainActive.Tip()`);
  otherwise refuse without evaluating anything else (B20). An unsynced-but-healthy refusal is
  reported as *transient* (the notifier trails the tip by up to a second) and the client retries
  (E2).
- **RED-1** `vin[0]` spends an ACTIVE or VOID vault; the transaction spends no other vault.
- **RED-2** `nLockTime ≥ vault.lockHeight` and `indexTip ≥ vault.lockHeight`.
- **RED-3** `yedIn − yedOut ≥ requiredBurn(vault.mintedCents, health(indexTip))` (0 for VOID).
- **RED-4** the transaction has no `vJoinSplit` and no `vShieldedSpend` (a co-signer policy, not
  a state rule — I1); `vShieldedOutput` is allowed, so the collateral may go straight to a `ys1…`
  address (I2), and `valueBalance ≤ 0` then; the transaction is standard and pays a fee in
  `[YELLOWBACK_FEE, 100 × YELLOWBACK_FEE]`, computed as `Σ transparent inputs − GetValueOut()`
  (`GetValueOut` already counts a negative `valueBalance` as an output,
  `ref/ycash/src/primitives/transaction.cpp`). `IsStandardTx(tx, reason, Params(), tip + 1)` and
  `AreInputsStandard(tx, view, branchId)` run against a `CCoinsViewCache` built exactly as
  `signrawtransaction` builds it — `pcoinsTip` behind `CCoinsViewMemPool` under `cs_main`
  (`ref/ycash/src/rpc/rawtransaction.cpp:906-921`) — because the fee needs every input's value and
  `AreInputsStandard` every input's `scriptPubKey`, which only the UTXO set has (C1; regtest does
  not run these checks itself, B5). **Before either call**, every input must be present and
  unspent in that view (`HaveCoins` + `IsAvailable`), because `GetOutputFor` and `GetValueIn`
  assert it (`ref/ycash/src/coins.cpp:898-903,912`); any miss ⇒ refuse (D1).
- **RED-6** for an ACTIVE vault, `price(indexTip)` is defined. During an oracle outage co-signers
  pause redemptions of ACTIVE vaults; they never compute a burn from `health = 0`. A VOID vault
  needs no burn and no price, so its release is not blocked (E3).
- **RED-7** the owner signature already present in `vin[0].scriptSig` verifies against
  `ownerPubKey` for the sighash of this transaction (`CPubKey::Verify`, hashtype byte stripped),
  computed over the vault script **reconstructed from the index record** (`lockHeight`,
  `ownerPubKey`, roster) and the vault value from the index — never over the script or value the
  caller supplied — so a co-signer never adds a signature to a transaction the owner did not
  authorise and can never be used to sign anything but a real vault spend (C5).
- **RED-8** `nExpiryHeight ≤ indexTip + 40 + RED_SKEW` with `RED_SKEW = 2`, so a fully co-signed
  transaction cannot be held and broadcast later under different health, while an owner whose node
  is a block or two ahead of the co-signer's is not refused (E2).
- **SUB-1** (owner's node, in `yed_submitredeem`) the returned transaction equals the one
  `yed_redeem` produced — held in the node's `PendingRedemption` record for that vault (D3) — except
  for additional signature pushes in `vin[0].scriptSig`, every input
  passes `VerifyScript` under `STANDARD_SCRIPT_VERIFY_FLAGS`, `chainActive.Height() ≥ lockHeight`
  and `nExpiryHeight ≥ chainActive.Height() + 1 + TX_EXPIRING_SOON_THRESHOLD` — all **before**
  `CommitTransaction`, which records the transaction in the wallet before it tries the mempool
  (`ref/ycash/src/wallet/wallet.cpp:5723-5747`, C22). The owner's `SIGHASH_ALL` signature already
  makes any other change invalid; SUB-1 turns that into an explicit, testable check.
- **MINTPOL-1** the wallet builds only when its index is `synced`, `indexTip ≥ startHeight +
  MINT_EVAL_LAG` (D5), `evalHeight = indexTip − MINT_EVAL_LAG` has a defined price, `healthPct ≥
  100` and `¬mintFrozen`, and `supplyCents + cents ≤ SUPPLY_CAP`; it sets `vout[0].nValue` to exactly the snapshot's requirement (rounded up
  to 1,000 zat). Keys come from `GetKeyFromPool`, which generates a fresh key if the pool is empty
  and the wallet is unlocked (`ref/ycash/src/wallet/wallet.cpp:6005-6022`, C8). It warns when the
  remaining supply cap is below `10 × MAX_MINT`, the one condition (MINT-6) it cannot fix at
  `evalHeight`.

Co-signers do not check where the collateral goes: the owner signs every output with
`SIGHASH_ALL`, so only the owner can decide that, and only the owner can be harmed by it.

### 3.9 Roster rotation

The federation rotates by publishing a ROTATION transaction — an anchor spend paying to the new
roster script with no `OP_RETURN` (C9) — immediately followed by a PRICE transaction from the new
anchor (which reveals the new script). Wallets read `yed_getroster` (returns `Rosters.back()` and its pubkeys) before every mint.
MINT-3 accepts the current or previous roster, so a mint built just before a rotation still
registers, but only for `ROSTER_GRACE` (1,152 blocks, one day) after the new roster is revealed
(B21). Old roster members must retain their keys until every vault that references their roster is
CLOSED; `yed_listvaults` reports the count per roster index for the runbook. With v1 tiers capped at
one year, this obligation is bounded to one year and one day past rotation.

### 3.10 Determinism requirements for implementers

The validator and state machine may read only: the block being applied, the state view, and
`Params`. Forbidden: `GetTime()`, `GetAdjustedTime()`, `mempool`, `pwalletMain`, `GetArg`, floating
point, `std::map` iteration order that depends on pointers. Every function in `src/yellowback/state.*`
must be callable from a unit test with an in-memory view.

---
