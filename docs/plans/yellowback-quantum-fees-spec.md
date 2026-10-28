> Companion to [`yellowback-quantum-plan.md`](yellowback-quantum-plan.md) D-Q-23 / D-Q-24 (owner, 2026-10-11): the rule-level
> and byte-level spec of the Option D fee structure and `maxMint` $100,000. Normative for the implementation; band rates,
> the floor and the $/KB targets are parameters that yb-calibration's fee study may adjust before activation.

# Yellowback fee structure (D-Q-23 Option D) and `maxMint` $100,000 (D-Q-24) — draft spec

Draft for the coordinator, 2026-10-11. Read-only survey of `wt/q-dd` (`upgrade/quantum-vaults` @ `d41026209`) and
`wt/q6` (@ `0c6c5fdf2`); every `file:line` below is `wt/q-dd` unless marked `6:`. The fee rules (`math.h`,
`params.cpp`, `state.cpp` MINT/RED sections) are byte-identical on both lines, so the dd citations hold on 6 with the
offsets the Q3–Q5 port introduced. Sources: quantum plan §2 D-Q-23/D-Q-24, §9 items 3 and 5;
`wt/scratch/lockup-investigation/REPORT.md`; upgrade plan §15.10; in-term plan §3–§4 (IT-9); hardening H-12.

Status of the knobs: D-Q-23 says the bands, rates, floor and $/KB targets are "calibrated by yb-calibration before
implementation". Every number below is the owner's stated value, carried as a **parameter** (`Params`, `yed_getinfo`)
so the calibration result changes one table and no rule.

---

## 0. Findings that shape the spec (read first)

| # | Finding | Consequence |
|---|---|---|
| F-A | **`pMint` is not stored in the vault record.** D-Q-23 says "already stored"; the investigation's "facts stored at mint" was wrong at the record level. `VaultRecord` (`view.h:215-270`) has no price field. `Snapshots[ref].pMint` (`view.h:645`) is only the cross-section `xMint`; the mint's actual `pMint = min(xMint, aMint)` (`state.cpp:414`, ARMED — mainnet always, `mintRequiresArmed`) exists transiently in `MintVerdict` and the bundle statistic `aMint` survives only in `TxLogRecord.aMint` (`view.h:334`), which is history, **excluded from the state hash** and not consensus state. | The owner's redeem path must read a **stored** price without reading a live one, so the MINT appends `pMint` to the vault record (§1.2). Schema 8 → 9, golden vector regenerates. Recompute-from-TxLog is rejected (unhashed, prunable history). |
| F-B | Today's pool fee is on the **collateral** (`FeeZat(collateralZat)`, `math.h:193-200`) at mint (`state.cpp:398`), redeem and claim (`:576`), and feeds the attestor share (`AttestFeeZat(FeeZat(...))`, `:409`, `:587`). The early fee is also on the collateral (`EarlyRedeemFeeZat`, `math.h:186-191`, `state.cpp:579-583`). | Four consensus sites change, plus the wallet's mirrors (`txbuilder.cpp:765-771, :936, :1368`). |
| F-C | MINT-5's second clause `vout[0].nValue >= 4 * feeMin` (`state.cpp:372`; K14) exists only so that FEE_MIN 0.5 YEC can always be paid from the collateral. `feeMin` disappears with Option D. | The clause goes (§2.3); the new fee is structurally ≤ 2 % of the collateral (§1.6), which is what K14 wanted. |
| F-D | The claimant pays the pool fee today (RED-3 applies to selector 4, `state.cpp:569-578`); the early fee is owner-only (`!claim`, `:579`); under FEE-0 (no eligible payee at R) both are skipped (`:574`, K11). | All three kept (§1.4). |
| F-E | `pMint` is bound by the chain and the bundle, never chosen freely (§1.7). | The fee inherits MINT-5's binding; no new attack surface. |
| F-F | Regtest overrides `feeBps 25` and `maxMint $10,000` (`params.cpp:200-204`) "because scripts' arithmetic is written against the v3 values". | Both overrides are removed; regtest = mainnet for the new parameters (§5 ambiguity 8). |
| F-G | `maxMint` $100,000 at today's price is **unsatisfiable (K14) for classes B and C** and takes 80 % of Ycash's max supply for class A (§2.1). | Correct behaviour (nobody can lock more YEC than exists), but the RPC error must say so and yb-calibration must know the realistic ceiling is the supply, not `maxMint`. |
| F-H | The network fee today is `max(flat, min(-pqfeerate × size, -maxtxfee))` on a PQ input only (`policy.cpp:373-408`, `wallet.cpp:5947-5949`, `txbuilder.cpp:49-64`, `rpc/vault.cpp:1731-1747`; `6: wallet.cpp:6840-6843`, `txbuilder.cpp:850-852`, `rpc/vault.cpp:1765`). | The $/KB target slots in as the rate those sites already consume (§3); nothing in consensus. |

---

## 1. Protocol fee (consensus, YED module) — FEE-1′, RED-3′, IT-9′, AFEE-1′

### 1.1 Parameters (`src/yellowback/params.h/.cpp`, replacing `feeMin` / `feeBps`)

```cpp
/** FEE-1' (quantum plan D-Q-23): the protocol fee is tiered by the vault's debt, in cents, like tax brackets. */
static const int FEE_BANDS = 3;
struct FeeBand { Cents uptoCents; int bps; };   // the band covers (previous upto, uptoCents]; the last band has uptoCents = 0 = unbounded
FeeBand feeBands[FEE_BANDS];   //!< { {100000, 100}, {1000000, 50}, {0, 10} }: first $1,000 at 1.0 %, $1,000–$10,000 at 0.5 %, above at 0.1 %
Cents    feeFloorCents;        //!< 100: $1 per action (mint, redeem, claim)
Cents    maxMint;              //!< 10000000: $100,000 (D-Q-24; was 250000, H-12)
int      earlyRedeemFeeBps[NUM_CLASSES];   //!< 500 / 250 / 100: unchanged values, now bps of the DEBT (IT-9')
int      attestFeeBps;         //!< 5000: unchanged, now a share of the protocol fee
```

Same values on mainnet, testnet and regtest (`SetCommon`; the regtest `feeBps = 25` and `maxMint = 1000000` lines
`params.cpp:202, 204` are deleted). `feeMin`/`feeBps` are removed from `Params`, the constructor (`:106`), `ParamsRecord`
is untouched (neither was hashed; `view.h:709-737`). Micro-USD stays `int64_t MicroUsd`; cents stay `int64_t Cents`.

### 1.2 Stored mint price (`src/yellowback/view.h`)

```cpp
struct VaultRecord {
    ...
    int32_t ownerHeight;
    int64_t pMint;   //!< FEE-1' (D-Q-23): MINT-5's price at the mint, micro-USD per YEC (min(xMint, aMint) when ARMED,
                     //!< xMint otherwise; 1..PRICE_MAX); the fee price of every later spend. Appended last (SERIALISATION.md §1 row 5).
};
static const uint32_t SCHEMA_VERSION = 9;   // 9: VaultRecord.pMint (D-Q-23)
```

- Set in `ApplyMint` from the `pMint` `MintVerdict` used in `mint5()` (`state.cpp:367-374, :414`): `MintFacts` gains
  `MicroUsd pMint` (set inside `mint5()` on success), `SetVault` (`:297-309`) stays pure; `ApplyMint` (`:435`) writes
  `vault.pMint = facts.pMint`. Value range 1..4,294,967,295 (`PRICE_MAX`, `params.h:79`); precision micro-USD, exactly
  the `uint32_t priceMicroUsd` of the attestation (`attest.h:36`) and the tag (`view.h:173`).
- An attestor cancel re-creates the vault by copying the record (`VaultRecord v = vault.value()`, `state.cpp:789`), so
  `pMint` survives a cancel unchanged. A vault minted before this change does not exist on any live network (no
  activation height is set anywhere), so there is no "pMint = 0" legacy case; the rule treats `pMint <= 0` as
  `vault-spend-malformed` defensively.
- State-hash preimage row 5 (`SERIALISATION.md:40`) gains `i64 pMint` last; the Python `_ser_vault`
  (`yellowback_model.py:1808-1812`) appends `_i64(v.p_mint)`; `Vault.__slots__` (`:1442-1443`) and `to_json` (`:1468-1470`)
  gain `p_mint`; the vault JSON (`rpc/yellowback.cpp:232-250`) gains `"pMint"`.

### 1.3 Arithmetic (`src/yellowback/math.h`, replacing `FeeZat` and `EarlyRedeemFeeZat`)

All products in `arith_uint256` as the file does; one rounding per quantity; "cent-bps" = cents × bps.

```cpp
/** FEE-1': the protocol fee of a debt in cent-bps: sum over the bands of (the debt inside the band) x bps, then at
 *  least feeFloorCents x 10^4. Pure, total, never overflows (debt <= maxMint). */
inline int64_t ProtocolFeeUnits(Cents debtCents, const Params& P)
{
    if (debtCents <= 0) return 0;
    int64_t units = 0, lo = 0;
    for (int i = 0; i < FEE_BANDS; i++) {
        const Cents hi = P.feeBands[i].uptoCents;                 // 0 = unbounded
        const Cents inBand = (hi == 0 ? debtCents : std::min(debtCents, hi)) - lo;
        if (inBand <= 0) break;
        units += (int64_t)inBand * (int64_t)P.feeBands[i].bps;
        lo = hi;
    }
    return std::max(units, (int64_t)P.feeFloorCents * BPS);
}

/** The dollar fee for display and RPC: ceil(units / 10^4) cents. */
inline Cents ProtocolFeeCents(Cents debtCents, const Params& P) { return (ProtocolFeeUnits(debtCents, P) + BPS - 1) / BPS; }

/** FEE-1' in zat at the vault's mint price: ceil(units x COIN / pMint) = the YEC worth of the dollar fee, rounded up to the
 *  zat. nullopt when pMint is undefined (<= 0); MAX_MONEY if it does not fit (unreachable for a vault that exists, section 1.6). */
inline std::optional<CAmount> ProtocolFeeZat(Cents debtCents, MicroUsd pMint, const Params& P)
{
    if (pMint <= 0) return std::nullopt;
    arith_uint256 f = CeilDiv(arith_uint256(ProtocolFeeUnits(debtCents, P)) * arith_uint256(COIN), arith_uint256(pMint));
    return FitsInt64(f) && MoneyRange((CAmount)f.GetLow64()) ? (CAmount)f.GetLow64() : MAX_MONEY;
}

/** IT-9': the early-redeem fee, bps of the DEBT at the mint price: ceil(debt x bps x COIN / pMint) (no floor); 0 at or after
 *  lockHeight (the caller's test) or when bps <= 0. Same shape as RequiredCollateral with the fee's bps. */
inline CAmount EarlyRedeemFeeZat(Cents debtCents, int earlyRedeemFeeBps, MicroUsd pMint)
{
    if (debtCents <= 0 || earlyRedeemFeeBps <= 0 || pMint <= 0) return 0;
    arith_uint256 f = CeilDiv(arith_uint256(debtCents) * arith_uint256(earlyRedeemFeeBps) * arith_uint256(COIN), arith_uint256(pMint));
    return FitsInt64(f) && MoneyRange((CAmount)f.GetLow64()) ? (CAmount)f.GetLow64() : MAX_MONEY;
}
/** AttestFeeZat(feeZat, attestFeeBps) unchanged (math.h:278-283): floor(protocolFeeZat x 5,000 / 10^4). */
```

Why `units × COIN / pMint`: cents/100 USD ÷ (pMint/10^6 USD per YEC) × 10^8 zat/YEC = cents × 10^12 / pMint, and
units = cents × 10^4, so zat = units × 10^8 / pMint. This is `RequiredCollateral(cents, bps, pMint)` with the fee's
bps (`math.h:115-124`), the arithmetic MINT-5 already trusts.

Rounding rule: **ceil to the zat** in consensus (never 1,000-zat granularity — that is the wallet's collateral
convenience, `RequiredCollateralRounded`, and stays wallet-only). The rule is `output >= feeZat`, so a wallet may round
its fee output up (it overpays; `txbuilder.cpp:765` may keep paying the exact value).

Worked values (`units`, dollars, zat at three prices):

| debt | units (cent-bps) | fee | zat @ PRICE_MIN $0.0001 | zat @ $0.018 (ref ≈ today) | zat @ PRICE_MAX $4,294.97 |
|---|---|---|---|---|---|
| $100 (minMint) | 1,000,000 = floor | $1.00 | 10^12 (10,000 YEC) | 5,555,555,556 (55.6 YEC) | 23,284 |
| $1,000 | 10,000,000 | $10 | 10^13 | 55,555,555,556 | 232,831 |
| $10,000 | 55,000,000 | $55 | 5.5×10^13 | 305,555,555,556 | 1,280,569 |
| $100,000 (maxMint) | 145,000,000 | $145 (0.145 %) | 1.45×10^14 (1.45 M YEC) | 805,555,555,556 (8,056 YEC) | 3,376,060 |
| early, $100,000 class A (5 %) | — | $5,000 | 5×10^15 (> MAX_MONEY, see §1.6) | 2.78×10^13 (277,778 YEC) | 116,415,322 |

The floor binds exactly at `minMint` ($100 × 1 % = $1); above it the bands bind.

### 1.4 Rules (the delta on upgrade plan §15.10 / in-term §4; verdict names unchanged unless marked NEW)

- **FEE-1′ (the fee amount).** `feeZat(V) = ProtocolFeeZat(V.mintedCents, V.pMint)`. At a MINT, `V.mintedCents =
  payload.cents` and `V.pMint` = MINT-5's price (so the mint fee is known only after MINT-9 when ARMED, exactly where
  MINT-5 sits in the evaluation order, `state.cpp:313-316`; **MINT-8's amount check moves after MINT-5** — see
  §1.5). Bands on `mintedCents` only: never on the burn (RED-2 allows over-burning), never on the assignments, never
  on the collateral; an over-collateralised vault pays the same fee as a tight one.
- **FEE-0 (unchanged).** `E(R)` empty ⇒ `feeVout` ignored, no pool fee, no early fee (K11; `state.cpp:393, :574`).
  Kept: the owner's "no eligible pool, no fee" case is the price-feed-dead case and the investigation (c)4 shows it
  returning 100 %.
- **MINT-8′.** With `E(R)` non-empty: `feeVout` shape as today (`:395-397`), payee in `E(R)` (`:396-397`), and
  `vout[feeVout].nValue >= ProtocolFeeZat(p.cents, pMint)` (`:398`). `bad-mint-fee` as today.
- **AFEE-1′ (mint and claim).** `attestFeeZat = AttestFeeZat(ProtocolFeeZat(debt, pMint), attestFeeBps)`
  (`:409`, `:587`): the attestor share is half the protocol fee, its own output as today, the early fee never enters it
  (the owner path is never ARMED, `:558`, so the share exists only on mints and claims).
- **RED-3′.** With `E(R)` non-empty: `feeVout` shape and payee as today (`:573-577`);
  `vout[feeVout].nValue >= ProtocolFeeZat(V.mintedCents, V.pMint)` (`vault-spend-bad-fee`, `:578`). Owner and
  claimant alike pay it (the claimant pays the **redeem** fee of the vault it closes; its own mint paid at mint time).
- **IT-9′.** Owner path (selectors 2/3), `H < V.lockHeight`, valid class:
  `vout[feeVout].nValue >= ProtocolFeeZat(...) + EarlyRedeemFeeZat(V.mintedCents, earlyRedeemFeeBps[V.termClass], V.pMint)`
  (`bad-redeem-early-fee`, `:579-583`). No floor on the early fee; never on a claim; never under FEE-0; one output
  (the pool payee's), no attestor share — as today.
- **RED-1′ (defensive).** `V.pMint <= 0` ⇒ `vault-spend-malformed` (cannot occur; makes the rule total).
- **Price binding.** The redeem reads `V.pMint` only — a stored fact, never `Snapshots[ref]`, never a bundle — so
  the investigation's property "the owner's redeem path reads no live price" holds verbatim (REPORT (a)); a price
  rise cannot make the fee grow in YEC (it shrinks in dollars: the fee is fixed in YEC at the mint price). The
  investigation's "optional cap at the collateral needed at mint" ((d)2) is subsumed: the fee is now ≤ 2 % of that.
- **`feePaidZat` / `TxLog.feeZat`** semantics unchanged (the paid amount, 0 under FEE-0; `:444-445`, `:707-710`).

### 1.5 MINT evaluation order (state.cpp:313-316 comment, R15)

Today: MINT-2, 3, 4, [5 if not ARMED], 6, 7, 8, [9, AFEE-1, 5, 10 if ARMED]. MINT-8′'s amount needs `pMint`, which
when ARMED exists only after MINT-9. Smallest change: split MINT-8 into its shape/payee clauses (stay at `:393-397`,
before the bundle is verified — "bundle signatures are verified only for a mint that has paid its pool fee" keeps its
sense as "…that has a well-formed fee output to an eligible pool") and its **amount clause, evaluated immediately after
MINT-5** in both branches (not ARMED: after the v2-position `mint5()`; ARMED: after the post-MINT-9 `mint5()`, before
MINT-10). AFEE-1 (`:409`) moves with it, after MINT-5 (it needs the same `pMint`): order becomes MINT-9, MINT-5, MINT-8′
amount, AFEE-1′, MINT-10. The Python model (`yellowback_model.py:2741-2850`) mirrors the order; the golden vector's
`"invalid"` entries keep their verdicts (137 `bad-mint-amount`, 217, 231, 251 are not fee cases).

**As built (review fix-up, §5.1):** when ARMED, a **lower bound** of MINT-8′'s amount is also checked right after the
shape/payee clauses and **before MINT-9**: `vout[feeVout].nValue >= ProtocolFeeZat(cents, xMint)`. Since
`pMint = min(xMint, aMint) <= xMint` and `ProtocolFeeZat` is non-increasing in the price, a fee below that bound is
below the fee at every `pMint` MINT-9 can produce, so the early refusal (`bad-mint-fee`) changes no valid verdict — it
only stops a 1-zat fee output from buying a full bundle verification. The exact amount clause stays after MINT-5.

### 1.6 Bounds and overflow (both lines)

- `ProtocolFeeUnits` ≤ 145,000,000 at `maxMint` (int64 trivially). `ProtocolFeeZat` max = 1.45×10^14 zat at
  `PRICE_MIN`, 6.9 % of `MAX_MONEY`: always in `MoneyRange`. Min = 23,284 zat ($1 at `PRICE_MAX`) > dust and >
  `TOKEN_VALUE` 10,000: the fee output is never dust.
- `EarlyRedeemFeeZat` can exceed `MAX_MONEY` only for a vault that cannot exist: a vault with debt D at price p has
  `collateral C >= ceil(D × ratio × COIN / p)` with `ratio >= 30,000` (MINT-5), so
  `early = ceil(D × 500 × COIN / p) <= C / 60 + 1` and `protocol <= ceil(D × 100 × COIN / p) <= C / 300 + 1`.
  **Invariant (K14′): protocol + early ≤ C / 50 + 2 zat** — every fee is always payable from the collateral, with
  ≥ 98 % left, at any price in `[PRICE_MIN, PRICE_MAX]`. This is why MINT-5's `4 × feeMin` clause can go (§2.3).
  Unit test: the bound at `maxMint` × class A × `PRICE_MIN` (unsatisfiable collateral, fee `MAX_MONEY`) and at the
  satisfiability threshold prices of §2.1.
- `AttestFeeZat` ≤ protocol/2: in range.
- `pMint` ≤ `UINT32_MAX` so `units × COIN` ≤ 1.45×10^16 < 2^54: even int64 would do; `arith_uint256` is used for
  uniformity with the file.

### 1.7 Is `pMint` the bundle's price, not the minter's? (confirmed)

`pMint = min(xMint(R), aMint)` (`state.cpp:367, :414`, PRICE-2 revised), where `xMint(R)` = the min of the three
pool-tag medians at the snapshot R (`:1433-1439`, chain data, PIN-1/2 exclusions) and `aMint` = the weighted
quantile of a **verified** attestor bundle (BUNDLE-1, M_SELECT 4 of N_SLOTS 9, bonded seats, `math.h:236-250`), with
MINT-10 refusing an `aMint` more than 15 % from `pFast(R)` (`:418-425`). The minter chooses only R within
`REF_WINDOW` (40 blocks, `params.h:86`) and which valid bundle to carry; it can lean `pMint` lower (min), which
**raises** its fee in YEC and its collateral — no incentive — and cannot push it above the attested price. Under
`mintRequiresArmed` (mainnet/testnet true, `params.cpp:97`) a mint without a bundle is `mint-halted-unarmed`. The fee
therefore has exactly MINT-5's binding and no new one.

### 1.8 Verdict names

Unchanged: `bad-mint-fee`, `vault-spend-bad-fee`, `vault-spend-bad-payee`, `bad-redeem-early-fee`, `afee1-fee`,
`vault-spend-malformed` (now also `pMint <= 0`). No new verdict. `mint-unsatisfiable` (K14) and `bad-mint-collateral`
keep their names; the latter loses its second cause (§2.3).

### 1.9 What the Python model mirrors (`qa/rpc-tests/test_framework/`)

- `yellowback_model.py`: `Params` gains `fee_bands=((100_000, 100), (1_000_000, 50), (0, 10))`, `fee_floor_cents=100`,
  loses `fee_min`/`fee_bps` (`:184-212`, `:312, :331`); `max_mint=10_000_000` in both presets (`:317, :336`);
  new `protocol_fee_units`, `protocol_fee_cents`, `protocol_fee_zat(cents, p_mint, p)`, `early_redeem_fee_zat(cents, bps, p_mint)`
  replacing `fee_zat` (`:482-488`); `Vault.p_mint` + `_ser_vault` (`:1442, :1810`); `SCHEMA_VERSION 9`; MINT-5 second
  clause removed (`:2798`); the mint stores `v.p_mint` (`:2714`); MINT-8′/AFEE-1′ after MINT-5 (`:2824-2842`);
  RED-3′/IT-9′ read `vault.p_mint` (`:3005-3014`).
- `yellowback_util.py`: `FEE_MIN`/`FEE_BPS` → `FEE_BANDS`, `FEE_FLOOR_CENTS` (`:183-185`); `MAX_MINT = 10_000_000`
  (`:200`); `fee_zat(collateral)` → `protocol_fee_zat(cents, p_mint)` (`:440-448`); `build_mint_tx` (`:1018-1057`)
  computes the fee from `cents` and the estimate's `pMint`; `build_vault_spend_raw` (`:1104-1141`) from the vault's
  `pMint`; `mint_vault_raw` (`:1266-1272`, `requiredZatFloored` no longer carries the 2-YEC floor).
- `SERIALISATION.md`: row 5, schema 9, the §3 money-rule entries for FEE-1/RED-3/IT-9, the golden description.

### 1.10 Vectors and fixtures that regenerate (one commit each line, diff explained)

| Artefact | Why |
|---|---|
| `qa/rpc-tests/test_framework/yellowback_golden.json` + `GOLDEN_STATE_HASH` (`test_yellowback_model.py:43`) + C++ `statehash_golden_vector` + `src/test/data/yellowback_golden.json` (`gen_yellowback_corpus.py --check`) | schema 9, `pMint` in every vault record, fee outputs of every mint/redeem/claim in the vector, MINT-5 floor gone |
| `yellowback_pq_vectors.json` (qa + `src/test/data`), "chain" section | its mints carry fee outputs; verdict labels |
| fuzz corpus `src/test/data/yellowback/input/*.bin` + table (`gen_yellowback_corpus.py --write`) | the mint/redeem shapes' fee amounts (keep the verdict labels meaningful) |
| `doc/yellowback-rpc-contract.json`, `doc/yellowback-rpc.md`, `docs/plans/yellowback-quantum-rpc-delta.md` (`make spec --check-quantum`) | rpcversion 8 fields (§3.4) |
| client copies: `yecwallet-dd/docs/yellowback-rpc-contract.json`, `lightwalletd-dd/testdata/yellowback/contract.json`, `chain-viz/tests/fixtures/rpc-contract-samples.json` | same |
| `yb-calibration/src/ybcal/model/examples.py:32-36, :158-161, :203-208` and `policy/*.toml` `maxMint` (`harden-2026-10.toml:217, :241`) | constants and the K14 example |
| `src/test/data/vault_vectors.json` | **unchanged** (primitive only) |

---

## 2. `maxMint` → $100,000 (MINT-2′, D-Q-24)

### 2.1 Arithmetic review

- MINT-2 (`state.cpp:331`): `p.cents <= maxMint = 10,000,000`; the payload's `cents` is `u32` (`payload.h:28`, max
  $42.9 M) — fits. `maxOutput` is already 10,000,000 (`params.cpp:19`): a MINT's single token output equals `cents`
  and XFER-1/RED-1 bound every assignment by `maxOutput` (`:540-542`), so `maxMint == maxOutput` is consistent and a
  $100,000 mint yields one $100,000 token, transferable whole.
- `RequiredCollateral(maxMint, ratio, pMint)` (`math.h:115-124`, arith_uint256, K14): `10^7 × ratio × 10^8 / pMint`.
  It is **unsatisfiable (`mint-unsatisfiable`) when `pMint < ratio × 10^15 / MAX_MONEY`**: class A (30,000)
  below 14,286 µUSD ($0.0143), class B below 19,048 ($0.0190), class C below 23,810 ($0.0238). At the ≈ $0.018
  reference (REPORT #14) a $100,000 class B or C mint needs more YEC than exists (27.8 M for C vs 21 M max); class A
  needs 16.7 M YEC. Not a defect: `MAX_MONEY` is the physical cap and K14's path already reports it; the RPC text
  "the required collateral exceeds MAX_MONEY" (`rpc/yellowback.cpp:1647`, `txbuilder.cpp:1159`) should add "(more
  YEC than can exist; lower the amount or the term class)". yb-calibration's whale check must take the *supply*,
  not `maxMint`, as the binding ceiling at today's prices.
- `CapCents` / `SupplyCapCents` / `GlobalRatioBps` (`math.h:139-168`): no input scales with `maxMint`
  (issued × price); unchanged, no new overflow. MINT-6 (15 % soft cap, `:379-381`) and HALT-2 (200 %, `:1466`) stay
  the system-wide limits (D-Q-24); a single $100,000 mint vs the cap is a calibration question, not an arithmetic one
  (the cap is soft above `recapRatioBps`: class C passes).
- `IsUnderwater`, `ClaimantMaxZat` (`math.h:174-182, :259-268`): 256-bit, `maxMint × θ × COIN` = 1.25×10^19 fits; the
  existing `yb-calibration` example `claimant_max_zat(MAX_MINT, …, PRICE_MIN)` (`examples.py:295`) re-evaluates.
- `yed_estimatecollateral` (`rpc/yellowback.cpp:1592-1593`): range text follows the parameter; `requiredZatFloored`
  (`:1655-1657`) becomes `requiredZat` rounded up to 1,000 only (§2.3). `yed_mint` audit F-1 `maxCollateralZat` bound
  unchanged.

### 2.2 Tests and vectors

- `yellowback_math_tests.cpp:190-215` (`mint5_required_collateral_overflow_at_max_mint_and_price_min`): `bigMint`
  becomes `MainParams().maxMint` = 10,000,000 (the regtest override is gone); the H-12 comment (`:204`) is replaced by
  the three threshold prices above; add the exact boundary cases
  `RequiredCollateral(10^7, 30000, 14286)` satisfiable / `14285` not.
- Regtest scripts asserting `cents must be between 10000 and 1000000` or minting 1,000,000 cents as "the max":
  `yellowback_rpc_contract.py`, `yellowback_lifecycle.py`, `yellowback_void_mint.py` (grep `MAX_MINT`, `1_000_000`);
  the golden block 137 (`bad-mint-amount`) must mint > 10,000,000 cents to stay invalid (`test_yellowback_model.py`
  `build_golden`).
- Clients that hard-code $2,500: none found (YecWallet, YEW, lightwalletd read `params.maxMint`); the YecWallet
  devnet cases and `yb-calibration` policy files carry the value.

### 2.3 MINT-5′ (the `4 × feeMin` clause)

`state.cpp:372` becomes `if (tx.vout[0].nValue < required.value()) return BAD_MINT_COLLATERAL;`. The clause existed
for K14 (a 0.5-YEC fee payable from the collateral twice); §1.6 proves the new fees are ≤ 2 % of any valid
collateral, so the floor has no remaining purpose and, at high prices, was the YEC-denominated distortion §9 item 5
named (2 YEC ≈ $8,590 minimum collateral for a $100 mint at `PRICE_MAX`). Wallet mirrors: `MintCollateral`
(`txbuilder.cpp:1155-1162`) drops `std::max(…, 4 * p.feeMin)`; `yed_estimatecollateral` (`:1655`); YecWallet
`yellowbackcontroller.cpp:1282`, `yellowbacktab.cpp:949`; `yellowback_util.py:1272`. The smallest required collateral
is then `minMint × 300 %` = $300 ≈ 6,984,920 zat at `PRICE_MAX`, far above dust and `residualMinZat`.
Alternative (not recommended): keep the behaviour under a new named constant `collateralMinZat = 2 × COIN` — it would be
the only YEC-denominated mint constant left and would need its own §9-item-5 follow-up.

### 2.4 H-12 reversal, recorded

Hardening plan H-12 ("`maxMint` $10,000 → $2,500 … re-decided at the first renewal") is reversed by D-Q-24 on the
quantum line only (`harden/yellowback` keeps $2,500; `upgrade/vault` inherits whatever the merge decides). Record it
in: `params.cpp:17` comment, the quantum plan §6 "what is given up" (the H-12 depth argument — a $100,000 vault's
liquidation at θ is ≈ $125,000, far beyond the measured bid depth; the aggregate stays bounded by `supplyCapBps` and
HALT-2, which is D-Q-24's stated reliance), `docs/mapping.md` §22 row, and `yb-calibration` `policy/harden-2026-10.toml:217`.

---

## 3. Network fee (policy, wallets) — $/KB via the attested price

### 3.1 Rule (both lines, policy only; nothing in consensus, D-Q-7 stands)

```
targetUsdPerKB:  plain PQ      20,000 µUSD/KB ($0.02)   -pqfeeusdperkb      (0 = off: today's -pqfeerate behaviour)
                 vault/YED     50,000 µUSD/KB ($0.05)   -yellowbackfeeusdperkb (0 = off)
price:           max(pFast, pMid, pSlow) at the index tip (every window defined; review M-1, §5.1 — the draft's
                 Snapshots[tip].pMint, the min of windows, overcharged in YEC exactly when YEC was cheapest);
                 undefined while the price is not trusted at the tip (HALT-1 or HALT-3; HALT-2 alone keeps it,
                 §5.1 amendment 2026-10-28), or with no index/startHeight — then "fallback"
rateZatPerKB  =  price defined ? max(floorPerKB, ceil(targetUsdPerKB x COIN / price)) : pqFeeRate (-pqfeerate)
floorPerKB    =  max(5,000 zat/KB, -pqfeerate)                                   (review A-7, §5.1)
fee(tx)       =  max(flatFloor, min(rateZatPerKB x size / 1000, cap))            -- capped, never refused
cap           =  plain non-PQ: -maxtxfee (unchanged);  PQ-input or Yellowback/vault:
                 min(max(-maxtxfee, $2 at the price), -yellowbackmaxtxfee 10 YEC)  (D-Q-23a, review M-1, D-Q-26)
```

- Which transactions, which rate: a transaction with a **PQ input** (today's trigger: `fPQInput`, `wallet.cpp:5947`;
  `6: :6840`) → plain rate; a transaction built by the **YED builder** (`YedNetworkFee`, `txbuilder.cpp:49-64`;
  `6: :850-852`, the P-2 third `max` argument, and `:965` Reprice) or a **`vault_*` RPC** (`rpc/vault.cpp:1731-1747`;
  `6: :1765`, floor `VAULT_RPC_FEE`) → vault/YED rate. A YED transaction with no PQ input (none exist on mainnet after
  TOK-PQ, D-Q-2) still takes the YED rate. Every other transaction is untouched (stock `GetMinimumFee` / ZIP-317 on 6).
- Floors: dd `DEFAULT_FEE` 1,000 zat (`policy/fees.h:15`) / `g_yellowbackFee` (`-yellowbackfee`, ≥ 1,000); 6
  `LEGACY_DEFAULT_FEE` (`amount.h:38`) / the ZIP-317 conventional fee (`ctx.fee`) — all kept as the `max` floor; relay
  floor `DEFAULT_MIN_RELAY_TX_FEE` 100 zat/kB (`main.h:72`; `6: :75`). Cap `DEFAULT_TRANSACTION_MAXFEE` 0.1 YEC
  (`main.h:74`; `6: :77`).
- Worked values (corrected 2026-10-11, review B N-4: the earlier figures were 10³ too small) at $0.40/YEC: plain
  5,000,000 zat/KB, YED 12,500,000 zat/KB; an SLH-DSA spend (≈ 9.0 KB: `PQSpendInputSize` 7,981 + 1,000) ≈ 0.45 YEC
  plain / 1.125 YEC YED (≈ $0.18 / $0.45); a Falcon spend (≈ 2.6 KB) ≈ $0.05 / $0.13. At $0.018 the rates are
  111,111,112 / 277,777,778 zat/KB (same dollars). At `PRICE_MAX` they are 466 / 1,165 zat/KB, so the 5,000 zat/KB
  floor (D-Q-23a) binds above ≈ $400/YEC (plain). Owner target (D-Q-26): a PQ transaction ≈ $0.10, range $0.05–$0.50
  (Bitcoin reference: $0.84–$1.67/kB, $0.12–$0.42 per basic transaction) — these rates meet it.

### 3.2 Where it lives

- `src/policy/policy.cpp:373-408` (`pqFeeRate`, `PQSizeFee`): add `CFeeRate yedFeeRate`, `PQSizeFee`'s sibling
  `YedSizeFee(floor, nBytes)`, and `void SetAttestedFeeRates(std::optional<MicroUsd> price)` that recomputes both
  from the targets (or restores the `-pqfeerate` fallback when `price` is empty). Called by the index on every tip
  advance/rewind (`index.cpp` `SetTip` path, next to the ZMQ/notify hooks) under `cs_main`/`cs_yellowback` as the
  existing `g_*` wallet globals are. `init.cpp:548, :1218-1227` gain the two `-…usdperkb` options (decimal dollars,
  `ParseMoney`-style with 6 decimals → µUSD).
- Consumers unchanged in shape: `wallet.cpp:5947-5949` (`PQSizeFee`), `txbuilder.cpp:49-64` (`YedSizeFee`),
  `rpc/vault.cpp:1731-1747` (`YedSizeFee`); 6: `wallet.cpp:6840-6843`, `txbuilder.cpp:850-852, :965`, `rpc/vault.cpp:1765`.
- `-pqfeerate` keeps its meaning as the fallback rate (no price) **and stays a floor with a price**: the rate is
  never below max(5,000 zat/KB, `-pqfeerate`), so an operator who raises `-pqfeerate` still raises every PQ and
  Yellowback rate (review A-7; D-Q-16 superseded only in that the dollar target usually binds above it). Its
  default stays 1× the relay floor (100 zat/KB), so by default the 5,000 zat/KB term is the floor.

### 3.3 Which price, exactly

Not `V.pMint` (a plain PQ spend has no vault; a redeem's `pMint` may be a year old). **Superseded by review M-1
(§5.1):** the draft chose `Snapshots[tip].pMint` (the min of windows, "errs high") and rejected the max of windows as
under-paying; the implementation publishes the **highest** window median (`pClaim`-style), because a fee in dollars
should cost the payer the target at the most favourable current price, not the most YEC in a falling market, and
**no** price while the price is not trusted (HALT-1 or HALT-3; since the §5.1 amendment of 2026-10-28 HALT-2 alone
keeps it) (the `-pqfeerate` fallback, bounded by the cap). The price is published
atomically by the index (`AttestedFeePrice()`, review N-3) and reported as `params.fees.network.priceMicroUsd`; a
client without an index (YEW via lightwalletd) reads the node-computed `zatPerKB` (§3.4) and never does price
arithmetic.

### 3.4 RPC fields (rpcversion **8**, both lines; `rpc/yellowback.cpp:61`, `6: :61`)

```json
"params": {
  "maxMintCents": 10000000,
  "fees": {
    "protocol": { "bands": [ { "uptoCents": 100000, "bps": 100 }, { "uptoCents": 1000000, "bps": 50 }, { "uptoCents": null, "bps": 10 } ],
                  "floorCents": 100, "attestFeeBps": 5000, "priceSource": "pMint" },
    "earlyRedeemFeeBps": [ 500, 250, 100 ],
    "network": { "priceMicroUsd": 400000, "priceSource": "tip" | "fallback",
                 "plain": { "usdPerKBMicro": 20000, "zatPerKB": 5000000 },
                 "yellowback": { "usdPerKBMicro": 50000, "zatPerKB": 12500000 },
                 "floorZatPerKB": 5000, "flatZat": 1000, "maxTxFeeZat": 10000000 }
  }
}
```

- **As built** (`q/fees` @ `430002b16`; the machine-readable form is
  [`yellowback-quantum-fees-rpc-delta.md`](yellowback-quantum-fees-rpc-delta.md) revision 2): `network` also carries
  `fallbackZatPerKB` (`-pqfeerate`) and `yellowback.{maxTxFeeUsdMicro, maxTxFeeCeilingZat, maxTxFeeZat}` (the cap's
  dollar term, its `-yellowbackmaxtxfee` ceiling and the cap in force; §5.1); `params.supplyCap` is
  `{circulatingZat, issuedBeforeStartZat, priceMicroUsd, capCents, maxVaultShareBps, vaultShareFloorCents,
  maxVaultCents}` (D-Q-25, MINT-6b); `yed_listclaimable` rows carry `pMint`; `yed_getfeepayee` loses its
  `collateralZat` argument and its `feeZat` field (`yed_getfeepayee <refHeight> [selectorHex]`).
- Removed (the contract's `removed` list): `params.feeMinZat`, `params.feeBps` (`:698-699`). Kept:
  `params.feeZat` (the flat floor), `params.pq.feeRateZatPerKB` (`:749`) now **equal to `fees.network.plain.zatPerKB`**
  so rpcversion-7 clients keep working; `params.earlyRedeemFeeBps` and `classes[].earlyRedeemFeeBps` (now "of the debt").
- `yed_estimatefee collateralZat` (`:1676-1695`) → `yed_estimatefee mintedCents ( priceMicroUsd )` →
  `{ feeCents, feeZat, pMint, attestFeeZat }` (a signature change: the reason the version bumps, with the removals).
- `yed_estimatecollateral`: + `protocolFeeCents`, `protocolFeeZat` (at the estimate's `pMint`), `attestFeeZat` on the
  new base; `requiredZatFloored` = `requiredZat` rounded to 1,000 (doc text `:1583`).
- `yed_estimateredeem` (`rpc/yellowbackwallet.cpp:1004-1021`): + `pMint`, `protocolFeeZat`, `protocolFeeCents`,
  `earlyRedeemFeeCents`; `feeZat` stays protocol + early; `earlyRedeemFeeBps` now of the debt.
- `yed_listclaimable.feeZat` (`:1334`), `yed_listvaults`/`yed_getvault` (+ `pMint`), `yed_estimateclaim`/`EstimateClaim`
  (`:2070`), `yed_redeem`/`yed_claim` results: the same amounts on the new base.
- Clients: YecWallet computes the pool fee locally from `feeMinZat`/`feeBps` (`yellowbackcontroller.cpp:1258-1261`)
  and the 2-YEC floor (`:1282`, `yellowbacktab.cpp:949`) — must read `fees.protocol` and the vault's `pMint` or, simpler,
  the estimate RPCs; lightwalletd `YellowbackParams` proto fields 5/6 (`walletrpc/yellowback.proto:60`) are deprecated
  (numbers never reused), a `fees` message is added, `common/yellowback.go:142` ("a light client computes the early
  fee from `earlyRedeemFeeBps`") now needs the vault's `pMint` in the vault message; chain-viz `InTermParams`
  (`model/yellowback.rs:617-624`) gains the bands; YEW shows the early fee in dollars (REPORT (d)2) from
  `earlyRedeemFeeCents`; x402 proto copies follow lightwalletd. All are rpcversion-8 client updates on their quantum
  branches; none needs a node change beyond this.

---

## 4. Review material

### 4.1 Rule-4 four-part check (for the consensus commit message, both lines)

> DigiByte charges no protocol fee at mint or redeem in **`src/digidollar/validation.cpp`** (its stability fee is a
> per-position interest accrued against the oracle price in IEEE-754, using mechanism **M** = a live oracle quote read at
> redemption); DigiByte's `maxMintAmount` is $100,000. The Ycash equivalent is the YED module's FEE-1/RED-3/IT-9 pool fee
> (`src/yellowback/state.cpp`, `math.h`), a flat max(0.5 YEC, 15 bps) of the **collateral** in YEC with no stored price,
> which lacks **M** (the owner's redeem path reads no live price by design — lockup investigation, D-Q-23) and whose
> YEC denomination explodes in dollars with the YEC price (§9 item 5). So the adaptation **W** is: a dollar-denominated,
> debt-tiered fee computed in integer cent-bps and converted to zat with `arith_uint256` at the vault's **stored** mint
> price `pMint` (one new `VaultRecord` field, schema 9), the early fee likewise on the debt, MINT-5's `4 × feeMin` floor
> removed (K14 now holds structurally, fee ≤ 2 % of collateral), `maxMint` restored to DigiByte's $100,000, and the
> network fee a wallet-policy $/KB target at the tip price with the relay floor and `-maxtxfee` as bounds.

**Tier rung.** Network upgrade (Tier 3, prime directive) — within it: a **module rule** change (`YED\0`), not the
primitive, not an opcode, not a template, not a transaction field; **per-vault state** (one `i64` appended to the
vault record) rather than global state; parameters in the module's `Params` table so calibration changes numbers, not
rules. A cheaper rung does not do: the fee is block validity (K10/L1: a policy fee lets fee-less redemptions through
stock miners), and the price must be a consensus fact of the vault (a wallet-side or TxLog price is not checked by
every full node). Nothing under `src/consensus/`, `src/script/`, `main.cpp`, `src/primitives/` changes; the review
gate applies through D-Q-15 (two independent reviewers on `src/yellowback/`).

### 4.2 Changed-line sites for reviewers (`wt/q-dd`; `wt/q6` mirrors at the port's offsets)

Consensus (module):
- `src/yellowback/params.h:150-152, :164, :175` and `params.cpp:17, :34-35, :52, :106, :200-204` — bands, floor, maxMint, regtest column.
- `src/yellowback/math.h:184-200` (`FeeZat`, `EarlyRedeemFeeZat` → §1.3), `:277-283` (`AttestFeeZat` comment).
- `src/yellowback/view.h:84` (schema 9), `:215-270` (`VaultRecord.pMint`).
- `src/yellowback/state.cpp:313-316` (order comment), `:323-330` (`MintFacts.pMint`), `:367-374` (MINT-5′), `:393-399`
  (MINT-8′ split), `:405-415` (AFEE-1′ after MINT-5), `:435-445` (`ApplyMint` stores `pMint`), `:569-584` (RED-3′, IT-9′),
  `:586-594` (AFEE-1′ claim), `:535` (RED-1′ `pMint` guard).
Wallet / RPC / policy (not consensus, reviewed for parity):
- `txbuilder.cpp:49-64, :765-771, :936, :1155-1162, :1368, :1377`; `wallet.cpp:5947-5949`; `rpc/vault.cpp:1731-1747`;
  `policy/policy.{h,cpp}:103-111, :373-408`; `init.cpp:548, :1218-1227`; `index.cpp` tip hook.
- `rpc/yellowback.cpp:61, :232-250, :471-476, :698-701, :735-749, :1122, :1334, :1592-1593, :1647-1658, :1676-1695, :2070`;
  `rpc/yellowbackwallet.cpp:310-311, :1004-1021, :1463-1495`.
Tests / docs: `src/test/yellowback_math_tests.cpp` (27 `FeeZat` uses, `:190-240`), `yellowback_state_tests.cpp` (20),
`yellowback_txbuilder_tests.cpp` (11), `yellowback_index_tests.cpp:265-303, :410-444`, `yellowback_script_tests.cpp` (2),
`pq_wallet_tests.cpp:302-308`; the eleven `qa/rpc-tests/yellowback_*.py` using `fee_zat`/`FEE_MIN`/`MAX_MINT`
(`attest, claim, interm, lifecycle, mining, pq, pricefeed, rpc_contract, sapling, void_mint`) and
`contrib/yellowback/devnet/yellowback-devnet`; `SERIALISATION.md`; `doc/yellowback-rpc.md`, `doc/yellowback-rpc-contract.json`.

### 4.3 Ambiguities and the recommended smallest reading

| # | Ambiguity | Recommended reading (smallest, both lines identical) |
|---|---|---|
| 1 | "Converted to YEC at `pMint`" — `pMint` is not in the record (F-A) | Append `pMint` to `VaultRecord` (schema 9); never recompute from snapshots/TxLog |
| 2 | Rounding of the zat amount | `ceil` to the zat, one rounding per quantity; no 1,000-zat granularity in consensus (wallet convenience only); the rule is `>=` so overpaying is valid |
| 3 | "Floor $1 per action" — does it apply to the early fee? | Protocol fee only; the early fee has no floor (it is an add-on to a fee that already has one) |
| 4 | Does a claimant pay the early fee? the protocol fee? | Protocol fee yes (as today), early fee no (as today, `!claim`) |
| 5 | FEE-0 with no eligible pool: skip both fees? | Yes (today's K11 behaviour; the investigation's side note); never make a fee-less redeem invalid when nobody can be paid |
| 6 | MINT-5's `4 × feeMin` clause once `feeMin` is gone | Delete it (K14 holds structurally, §1.6); do not introduce a YEC-denominated replacement |
| 7 | Attestor share base | Half of the **protocol** fee in zat (`AttestFeeZat` unchanged); the early fee never enters it |
| 8 | Regtest column | Same bands, floor and `maxMint` as mainnet; delete the `feeBps 25` / `maxMint $10,000` overrides and rewrite the handful of tests that assumed them |
| 9 | Bands on which amount | `mintedCents` (the debt) — not the burn, not the assignments, not the collateral |
| 10 | Mint fee when ARMED needs `pMint` after MINT-9 | Split MINT-8: shape/payee before MINT-9, amount right after MINT-5 (§1.5); AFEE-1 moves with it |
| 11 | Network-fee price | Draft: `Snapshots[tip].pMint` (min of windows). **As built (review M-1, §5.1): the max of the tip's window medians, none unless the price is trusted (HALT-1 and HALT-3 off; HALT-2 alone keeps it, §5.1 amendment 2026-10-28)**; fallback to `-pqfeerate` when undefined; YED-rate for every YED-builder and `vault_*` transaction, plain rate for any other PQ-input transaction, nothing else touched |
| 12 | rpcversion | 8 on both lines (`feeMinZat`/`feeBps` removed, `yed_estimatefee` signature changed); keep `params.pq.feeRateZatPerKB` = the effective plain rate |
| 13 | D-Q-23 mentions `bondMin`/`residualMinZat` "to follow the same pattern" | Out of scope here (no dollar anchor exists for a bond before the set is live); leave to yb-calibration as §9 item 5 says |
| 14 | `TxLog.feeZat`, `feePaidZat` | Unchanged semantics (the amount paid) |
| 15 | An early fee larger than the collateral at extreme prices | Impossible for a vault that exists (K14′, §1.6); the function returns `MAX_MONEY` on overflow as today, so the verdict is `bad-redeem-early-fee`, never a wrapped number |
| 16 | H-12 on the other branches | `harden/yellowback` keeps $2,500; the reversal is recorded for the quantum line and inherited by `upgrade/vault` only through the gate merge |

---

## 5. Implementation record (`ycash-dd` `q/fees` @ `430002b16`, reviewed; 2026-10-11)

The dd implementation is done and has passed two independent reviews (findings M-1, A-2..A-7, L-1, N-3 and the
MINT-8′ ordering fix-up). The changes below are the review's and the owner's (D-Q-26) on top of §1–§3; they are
policy except §5.1's MINT-8′ lower bound, a module rule reordering. `ycash6` and the clients follow (quantum plan
status).

### 5.1 Review-driven changes

- **Network-fee price = the max of the tip's window medians, none under a halt (review M-1).** §3.1/§3.3 as
  amended: `PublishFeePrice` publishes max(pFast, pMid, pSlow) at the tip; any halt bit (`HALT_NO_PRICE`,
  `HALT_GLOBAL_RATIO`, `HALT_DIVERGENCE`, …) publishes no price, and the wallets fall back to `-pqfeerate`. The price
  is an `std::atomic` written by the index under `cs_main` and read lock-free (N-3).

  **Amendment (owner decision 2026-10-28; cross-reference upgrade plan U-27, HALT-2 divides by open debt): fee
  publication follows price trust, not every halt bit.** `PublishFeePrice` publishes the dollar fee price whenever the
  price itself is trusted, that is whenever HALT-1 (`HALT_NO_PRICE`) and HALT-3 (`HALT_DIVERGENCE`) are both off,
  whatever HALT-2 (`HALT_GLOBAL_RATIO`) says; HALT-2 then restricts minting only (MINT-4, IT-5, unchanged). The reason:
  Yellowback has three halts and they say two different things. HALT-1 (no trustworthy price) and HALT-3 (the price
  windows disagree) mean "we do not trust the price right now"; a fee cannot honestly be priced in dollars at a price
  nobody trusts, so the flat YEC fallback (`-pqfeerate`) is the right answer there. HALT-2 (the system is
  under-collateralised) means "the vaults are thin": the price is still armed and the windows still agree. Since
  U-27 HALT-2 divides by open debt instead of circulating supply, so it fires more often than before, including for
  hours after a wave of claims in a crash, while the claimed debt waits for release. That is exactly when users need
  predictable dollar-priced fees and when the attestors, paid from those fees, are doing the work that matters most.
  Falling back to a flat YEC fee then makes every fee swing with the YEC price and cuts the attestors' share just
  when it is earned. The rule is written positively, as "publish when the price is trusted": an explicit allow-list
  of the halt bits that leave the price trusted (`FEE_PRICE_TRUSTED_HALTS` = `HALT_GLOBAL_RATIO`,
  `yellowback::FeePriceTrusted`, `src/yellowback/index.h`), never "publish when no halt bit is set". A future halt bit
  (a governance pause, say) is therefore not silently fee-neutral or fee-blocking: until someone decides it belongs on
  the allow-list it withholds the price, as the reserved bits do. This is node policy, not consensus: block validity
  never reads the published price (it is read only by the wallet, the YED builder, the `vault_*` RPCs and
  `yed_getinfo.params.fees.network`), and the change is the same on both node lines (`ycash-dd`, `ycash6`). The RPC
  contract is unchanged (`priceSource` stays `"tip"`/`"fallback"`; only when it reads `"tip"` moves).
- **`-yellowbackmaxtxfee`, default 10 YEC (review M-1).** An absolute YEC ceiling on the Yellowback cap: cap =
  min(max(`-maxtxfee`, `-yellowbackmaxtxfeeusd` $2 at the price), `-yellowbackmaxtxfee`), with or without a price
  (`yellowback.maxTxFeeCeilingZat`). `YellowbackWallet::Commit` and `rpc/vault.cpp` Broadcast submit with the
  absurd-fee check off, so both enforce this cap themselves (`YedFeeOverCap`: a Commit over it is not committed, a
  Broadcast over it throws `absurdly-high-fee`); the broadcast flag is restored by a scope guard (A-3).
- **`-pqfeerate` stays a floor (review A-7).** With a price the rate floor is max(5,000 zat/KB, `-pqfeerate`)
  (`AttestedFeeFloorPerKB`); without one the rate is `-pqfeerate` itself (§3.2).
- **Every Yellowback-builder transaction priced by size (review A-2).** `YedNetworkFee` prices a P2PKH-funded mint
  or a claimant-funded claim by its estimated size too (`YedEstimatedSize`: PQ inputs at `PQSpendInputSize`, others
  150 bytes, + 1,000), never below the flat fee, capped as above.
- **The owner-path clamp (review L-1).** An owner-path vault spend whose dollar-priced network fee would take
  everything the vault has left after the protocol fees (a small vault after a crash) is no longer refused
  `vault-value-too-small`: the builder clamps that fee to max(flat, floorPerKB × estimated size)
  (`YedFloorSizeFee`), so the owner is never stuck behind a policy rate.
- **Plain PQ transfers share the Yellowback cap (owner D-Q-26).** `PQMaxTxFee()` = `YedMaxTxFee()`: the wallet caps a
  PQ-input transaction's size fee at the Yellowback cap, not `-maxtxfee`, and `CommitTransaction` /
  `ReacceptWalletTransactions` submit with the absurd-fee check off exactly when the transaction spends a PQ input
  and its fee is within that cap (`PQFeeWithinCap`). `sendrawtransaction` is untouched: an outside submit keeps
  `-maxtxfee` unless `allowhighfees`. At $0.40 a Falcon plain transfer is ≈ $0.05 (≈ 0.13 YEC), an SLH-DSA spend
  ≈ $0.18 (≈ 0.45 YEC), both under the $2 (5 YEC) cap.
- **MINT-8′ lower bound before MINT-9 (consensus, module rule).** §1.5 as amended: `ProtocolFeeZat(cents, xMint)`
  checked before the bundle is verified; same verdict, no valid verdict changes. Unit test
  `mint8_lower_bound_before_mint9`.

### 5.2 Readings the implementation took (smallest reading, both lines identical)

- **Supply cap (D-Q-25) values the circulating supply at `xMint(R)` with `Snapshots[R].issuedZat`.** MINT-6 and
  MINT-6b read the reference snapshot's `issuedZat`, which is now the circulating supply at R (the snapshot below the
  start height is seeded with `Params::issuedBeforeStart = CirculatingSupplyAt(startHeight − 1)`, the closed-form
  subsidy sum from genesis; `Snapshot::Virtual()` keeps 0 and `ComputeSnapshot` substitutes the seed at the start,
  review A-4), priced at the cross-section `xMint` — the price MINT-6 already used, not the bundle's `pMint`.
  `yed_getinfo.params.supplyCap` reports the same base at the tip.
- **MINT-6b is per vault, not per owner.** `mint-vault-share` bounds one mint's debt by max(10 % of the MINT-6 cap,
  $10,000); an owner may hold several such vaults (owner identities are not linked on chain, and a per-owner sum
  would need new global state). Silent when the cap is undefined, as MINT-6 is.
- **Class C skips MINT-6 when `recapRatioBps` equals its base ratio — owner item.** MINT-6 refuses over the cap only
  when the class's `baseRatioBps < recapRatioBps` (W20/IT-5); with the in-term set class C's base is 50,000 =
  `recapRatioBps`, so class C mints are never refused by the aggregate cap — only MINT-6b's per-vault bound and
  HALT-2 bound them. This is the inherited W20 design, unchanged here, but D-Q-24's $100,000 `maxMint` and D-Q-25's
  larger cap base make it material: **the owner should confirm** that class C stays outside the aggregate cap on the
  fee line (alternatives: apply MINT-6 to every class, or a separate, higher cap for the recapitalisation tier).
- **The `-pqfeerate` floor wording.** "`-pqfeerate` defaults to 1× the relay floor" (D-Q-16, briefing) stands; with
  a price it is a floor under the dollar rate together with the 5,000 zat/KB policy floor — the floor is the larger
  of the two — and without a price it is the rate (§3.2).

