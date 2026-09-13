# Yellowback: Bond-Weighted Price Attestation

**Subsystem proposal / handoff document**
Companion to `docs/plans/yellowback-v2-development-plan.md` (revision 6). Extends v2; does not replace it.
Status: design complete, unvalidated. Not a specification.
Revision 6 — 13 September 2026 (amended 13 September 2026 by the v3 plan's review: R1, R2, R4, R5 below)

*Changes in revision 6 (after the feasibility audit, `yellowback-price-attestation-audit.md`,
and the product owner's correction of its first draft): the document is re-based on the
**implemented** Yellowback v2 — its rules, state, names and constraints — instead of on the
retired v0.2 proposal. The architecture of revisions 1–5 stands: **attestors publish nothing on
chain after registering; the party that needs a price carries the attestations and pays for
them.** What changes is the delivery: (1) the attestation bundle moves from an oversized
`OP_RETURN` into the **scriptSig of a carrier input** (§8), which every stock node relays today,
so the relay carve-out, service-bit peering and network-wide policy ask are withdrawn; (2) the
gossip stack and price polling move **out of `ycashd`** into the attestor agent and a wallet-side
subscriber, both free to use a modern Rust toolchain (§13); (3) the three rules that needed a
continuous on-chain attestation series are restated so that **whoever needs the trigger carries
the evidence** — per-bundle divergence (§10.2), a two-step emergency claim for persistence
(§10.3), and a pin test that arms from landed bundles (§10.1); (4) limit prices and the reorg
rule collapse into the plan's `refHeight` rule (V11); (5) residual return becomes a RED rule on
every claim; (6) signatures are ECDSA, the bond is P2SH with the script disclosed, the layer arms
automatically once enough attestors have matured, and every rule is named in v2's vocabulary.
The five decisions of §16 were taken by the product owner on 13 September 2026 and are applied
in the text.*

*Amendments after the v3 plan's independent review (13 September 2026): **(R2)** the bundle
commitment moves from a payload hash into the carrier's redeem script, so a relay node can no
longer void a mint by rewriting the scriptSig; carriers become per-transaction (§8.1); **(R1)** a
claim opened by the emergency clause alone pays exactly the debt at the adverse price, with no
margin (§10.3); **(R5)** the residual formula's spurious `10⁴` is removed; **(R4)** `ATTEST_MAX_AGE`
is 20 blocks so at most two of an attestor's signed prices fall in a bundle's window (§15). The
selector for mints is empty (§8.4).*

*Revisions 1–5 (September 2026) developed the two-source design: hashpower-weighted
cross-section, bond-weighted attestor quantile, `min`/`max` combination, the pinned-quote
failure mode and its three remedies, the `OP_RETURN` size analysis against the `ycashd` source,
the OR-triggered emergency tier with adverse payout, and the calibration questions. Their
reasoning survives here; the audit records what did not.*

---

## 1. Purpose

Yellowback v2 mints YED against overcollateralized YEC vaults with rules enforced by mining
pools running a patched `ycashd`. Every rule that matters reads a YEC/USD price from
`Snapshots[refHeight]`: `pMint` sizes collateral (MINT-5), `pClaim` decides when a vault is
claimable (RED-4), and both feed the halts (HALT-1..3). Today that price has one source — the
quote tags pools put in their coinbases — and the plan says so plainly: "Majority hashpower
colludes: can move prices … the chain's existing assumption" (§8.2), with a launch bar of at
least three pools and none above 40 % as the safeguard (L2, L4). That bar is governance, not
mechanism.

This document adds a second price population that hashpower cannot forge, and combines the two
so that moving the price in the direction that profits requires corrupting both at once.

**Design principle, restated because the first draft of this revision violated it.** Being an
attestor must cost nothing beyond the bond: no domain, no open port, no funded hot wallet, no
periodic transactions. The seated set the design wants — an explorer operator with an exchange
API key, a community member on a home connection — exists only if `-attest` plus a signing key
and a source list is the whole setup. The cost of an attested price falls on the party who
needs one: the minter, and the claimant.

**Scope.** The attestor role, bonding, registration, seating, the attestation and bundle
formats, the carrier, selection, the attestation statistic, the combination rule, the
pinned-quote remedies, the emergency tier, fees, ejection and transport — each stated as a
change to a named v2 rule, table or parameter. Out of scope: everything in v2 this does not touch.

---

## 2. Why a single hashpower-weighted source is not enough

v2 already answers the two critiques of the v0.2 design that earlier revisions led with:
deviation penalties are not rules (L1 moved them to wallet payee policy), and the
quote-tag-majority attack is bounded by `WINDOW_MIN_FILL` (V16, L9: `pClaim` needs 34 % of
blocks at two-thirds fill). What remains is structural:

**Influence is hashpower, full stop.** A median over quote-tagged blocks weights each pool by its
block share. Whatever the fill rule does to the arithmetic, the population is one population,
and a coalition holding a majority of it sets `pMint` and `pClaim` for as long as it likes. On a
chain whose launch bar is "no pool above 40 %", that coalition is two pools.

**The statistic is a time series, not a poll.** One block carries one quote from one pool. A
3 % pool's latest quote is ~33 blocks old on average; during the fast moves where accuracy
matters most the window measures *when* each pool mined, not what it believes.

**Indifference is cheap.** A hard-coded quote satisfies every rule and earns the same fee as a
maintained feed (§10). Nothing in v2 detects it.

**Consequence.** Pool quotes stay — Sybil-proof, and the machinery around them is built, tested
and model-verified — but they cannot be the only source. A second source must be one hashpower
cannot author, and the two must be combined so that neither can move the price in the
profitable direction alone.

---

## 3. Design overview

Two independent price populations, combined adversarially.

**Source A — the cross-section.** Unchanged from v2: `pFast`, `pMid`, `pSlow` over quote tags
(plan §3.7 *Medians*, with the fill rule), giving `xMint = min(pFast, pMid, pSlow)` and
`xClaim = max(pMid, pSlow)` — v2's `pMint` and `pClaim`, renamed. Two changes: pinned pools'
tags are excluded (§10.1), and so are they from the pool-side fee eligibility `E(R)`.

**Source B — bonded attestors.** A small set of bonded participants sign price messages
off-chain every `k` blocks and gossip them (§13). Attestations reach the chain only inside the
mint or claim that needs them, as a **bundle** in a carrier input (§8). From the bundle the
verifier computes `aMint` (the `Q_LOW` quantile, bond-weighted) and `aClaim` (`Q_HIGH`) (§7).

**Combination (PRICE-2, per transaction).**

```
mint:   pMint  = min(xMint(R),  aMint(bundle))     // adverse to the minter, who wants a high price
claim:  pClaim = max(xClaim(R), aClaim(bundle))    // adverse to the claimant, who wants a low price
        pEmerg = min(xClaim(R), aClaim(bundle))    // the OR trigger of the emergency tier (§10.3)
```

`R` is the transaction's `refHeight` (V11). Each is undefined if any input is (M1), with the
arming rule of §6.4 as the one exception. `xMint`/`xClaim` stay in `Snapshots`; `aMint`/`aClaim`
are properties of the transaction and are recorded in `TxLog`.

**What this buys.** Inflating a mint's price requires a hashpower majority *and* a
bond-weighted majority of the selected attestors quoting high together. Depressing a claim's
price requires the same coalition quoting low. Neither population needs to be trusted; each
needs to be independent of the other. Every later decision exists to preserve that property.

**What it costs.** Honest disagreement resolves conservatively: attestors at $1.60 and the
cross-section at $1.20 size mints at $1.20 — over-collateralized, not broken. Because the wallet
computes the same `pMint` from the same snapshot and the same bundle before signing (V11), the
minter sees the exact figure and declines if it is not acceptable.

**Where it fails.** The combination rule assumes each source errs in an unknown direction. A
source pinned to a constant errs in a known one, and the rule does not survive that unaided
(§10). The three remedies there and the emergency tier's exemption from the rule are part of the
design, not options.

---

## 4. The attestor role

An attestor is a party that has registered a bond (§5) and runs the **attestor agent**
(`yellowback-attest`, §13): an external process that polls price sources, signs an attestation
every `k` blocks, and gossips it. It never submits a transaction after registering. **The node
does nothing but verify**, per plan V6 (no network client code in `ycashd`) and the fork's CI
"no clock, no sockets" grep.

**Price sources are configurable and tiered**, as for the quote agent: direct exchange APIs
preferred (each is an independent observation, and volume permits a VWAP), public aggregators
permitted as a fallback tier so the casual participant is not excluded. Attestors should prefer
a median across venues over a VWAP from the single deepest one: on thin books, venue diversity
matters more than volume weighting.

*Market depth is the ceiling.* YEC trades on thin venues. An attacker who moves the traded price
on SafeTrade or nonkyc.io moves the honest inputs to both populations at once, and every
mechanism here then works correctly on a corrupted number. What contains that is the machinery
around the price layer — the fixed `refHeight` price, the divergence rule, the minting halt.
A residual (§17).

*Correlation is the cost of aggregators.* Eight attestors reading one aggregator are one
observation, not eight. Partial mitigations: the registration record's source-tier flag makes
the set's composition visible; the responsiveness test (§10.1) catches an aggregator that
freezes, though not one that is merely wrong. A known systemic exposure.

**The attestation** (74 bytes, the unit the bundle carries):

```
seq u16 ‖ priceMicroUsd u32 ‖ citedHeight u32 ‖ sig 64
sig = ECDSA(attestorKey, SHA256("YBATTEST1" ‖ seq ‖ priceMicroUsd ‖ citedHeight ‖ blockHash(citedHeight)))
```

`seq` is the attestor's registration sequence number (§5.2); the block hash is in the message,
not the payload — it binds the attestation to a chain without spending 32 bytes, and every
verifier has it in its index. Prices are integer µUSD, `[PRICE_MIN, PRICE_MAX]`. Signatures are
64-byte compact ECDSA, low-S, verified with the libsecp256k1 the node already links: Ycash's
bundled library ships the `schnorrsig` module source but `configure.ac:1282` does not enable it,
`configure.ac` is in the plan's zero-diff set, and nothing here uses aggregation.

---

## 5. Bond and registration

### 5.1 What a bond can be on Ycash

Ycash has no staking primitive and no covenants. A bond is one of: burned; time-locked to the
attestor's own key; or locked to a third party. The third is a custodian and is rejected; the
first punishes an honest operator's outage permanently. **The bond is a long CLTV back to the
attestor's own key.** There is no slashing: the penalty for misbehaviour is ejection, loss of
the fee stream, and the remaining lock on capital that now earns nothing.

That is sufficient only if attestors can grief but not extract — if no direction they push the
price in pays them. §10.3 works every direction and finds that, with residual return and the
two-step emergency claim in place, it holds. That conditionality is the load-bearing assumption
of this document.

### 5.2 Registration transaction

One transaction, the only one an attestor ever sends, standard under today's relay policy:

- **`vout[0]` — the bond.** `P2SH(bondScript)`,
  `bondScript = <bondLocktime> OP_CHECKLOCKTIMEVERIFY OP_DROP <bondPubKey> OP_CHECKSIG`,
  `nValue ≥ BOND_MIN`, `bondLocktime ≥ H + BOND_MIN_LOCK`. P2SH, not the bare script: `Solver`
  classifies a bare CLTV script as non-standard and the transaction would not relay; the module
  reconstructs the script and checks the hash, the vault pattern of plan §3.4.
- **`OP_RETURN` — payload type `0x05 ATTESTOR_REGISTER`** (§8.3):
  `attestorPubKey 33 ‖ bondPubKey 33 ‖ bondLocktime u32 ‖ flags u8` — 75 bytes with the
  4-byte header, inside `MAX_PAYLOAD`. `attestorPubKey` signs attestations (hot);
  `bondPubKey` owns the bond and **receives attestation fees** as `P2PKH(bondPubKey)` (cold;
  one key does both so the record fits). `flags`: bits 0–1 source tier (`0` exchange APIs,
  `1` mixed, `2` aggregator), bit 2 "operates a mining pool" (voluntary, §7.5), rest reserved.

**REG-A1** payload well-formed, both keys valid compressed keys, `vout[0]` is
`P2SH(HASH160(bondScript))`, `vout[0].nValue ≥ BOND_MIN`, `bondLocktime ≥ H + BOND_MIN_LOCK`,
`bondLocktime < LOCKTIME_THRESHOLD`, and `attestorPubKey` is not held by any `Attestors` record
other than one in `WITHDRAWN` (an `EJECTED` record never becomes `WITHDRAWN`, below, so an
ejected key is barred for good). If it holds: `Attestors[txid:0] = { seq, attestorPubKey,
bondPubKey, bondZat, bondLocktime, flags, registerHeight, status = PENDING, statusHeight }`,
`seq` from a monotonic `u16` counter. If it fails: non-Yellowback transaction. Registration
never makes a block invalid.

**PENDING** until `BOND_MATURITY` blocks after `registerHeight`, then **ELIGIBLE**. Spending the
bond outpoint (only possible after `bondLocktime`) sets **WITHDRAWN** at that block — except for
an `EJECTED` record, which stays `EJECTED` with `bondSpentHeight` recorded: ejection is terminal
for the key and the outpoint, whatever happens to the coin. The wallet tracks its own bond and
builds the withdrawal (`yed_withdrawbond`, §13).

### 5.3 No miner vote

Attestor activation is not gated on coinbase signalling: that would make miners the gatekeepers
of the population that exists to check miners. Seating is mechanical (§6).

---

## 6. Seating: top-N by bond weight

At every SNAP the **seated set** is the `N_SLOTS` ELIGIBLE attestors with the greatest bond
weight, ties by `seq` ascending, written to `Snapshots[H].seated[]` (at most `N_SLOTS` values
of `seq`). A bundle in a transaction with `refHeight = R` is verified against
`Snapshots[R].seated[]`, so a seating change after `R` cannot invalidate a transaction in
flight and no exit cooldown is needed.

### 6.1 Bond weight

```
weight = bondZat × clamp(H − ageOrigin, 0, AGE_CAP)
```

`ageOrigin = registerHeight`, or `Attest.triggerHeight` for the founding cohort (§6.3). Signed
64-bit for the difference, then `arith_uint256`; bounded since `bondZat ≤ MAX_MONEY` and
`AGE_CAP < 2³²`. The clamp at zero matters only before the trigger, when seating is computed
but read by nothing.

**Age makes buy-in slow and public.** Influence cannot be bought in a block.
**Splitting a bond gains nothing.** Influence is bond-weighted (§7) and selection is
bond-weighted (§8.4), so `X` over twenty keys is twenty entries of `X/20`. Sybil behaviour is
pointless rather than policed.

### 6.2 Why slots are capped

Not a security parameter, given §6.1. The cap bounds bundle size and keeps the fee per attestor
high enough that staying reachable pays. `N_SLOTS = 9`.

### 6.3 Founding cohort

Every attestor with `registerHeight ≤ triggerHeight + FOUNDING_WINDOW` — all who registered
before the trigger, and those who join within a week after it — is a founding member and
accrues age from `triggerHeight`, not from its own `registerHeight`. Before the trigger no rule
reads weight, so nothing is lost by the shared origin, and nobody gains from having registered a
block earlier than the rest; without it the first registrant would be the lowest-weighted and
displaceable by whoever registered a block later.

### 6.4 Arming: the attestation layer switches on by itself

The layer arms **automatically** (Decision D-4) from the state of the `Attestors` table, with
no release and no signalling. Carried state `Attest { status ∈ {UNARMED, TRIGGERED, ARMED},
triggerHeight, armHeight }`, initially `UNARMED`, copied into every snapshot:

**ARM-1** (trigger) at SNAP for `H`, if `status == UNARMED` and at least `ATTEST_ARM_MIN`
attestors are ELIGIBLE: `status = TRIGGERED`, `triggerHeight = H`, `armHeight = H +
ATTEST_ARM_DELAY`. **ARM-2** (arming) if `status == TRIGGERED` and `H ≥ armHeight`:
`status = ARMED`. Status never moves backward: a set that later shrinks below `ATTEST_ARM_MIN`
leaves the layer armed and, if fewer than `M_SELECT` of the selected can sign, minting halts
(§7.4) — fail closed, as V16 does for the cross-section.

Before `armHeight` no rule reads a bundle: PRICE-2 is `pMint = xMint`, `pClaim = xClaim`, v2
exactly as implemented, and a bundle present in a transaction is ignored. From `armHeight` on
(read as `Snapshots[R].attest.status == ARMED` for a transaction with `refHeight = R`), a mint
without a valid bundle is VOID (MINT-9) and a claim without one is invalid (RED-1).

`ATTEST_ARM_MIN = 5`, `ATTEST_ARM_DELAY = 1,152` (one day). The delay makes the trigger a public
fact for a day before anything changes: wallets show "attestation layer arms at height …",
late registrants can still join the founding cohort (`FOUNDING_WINDOW` runs from
`triggerHeight`), and an operator can hold a mint until the layer is live. Registration is
accepted from `START_HEIGHT`, so the set matures while v2 runs single-source.

**Residual, stated as the owner's accepted risk:** the attestors themselves supply the trigger.
Five founding registrants with matured bonds arm the layer whether or not the set is diverse,
and a hostile founding group could arm while small and friendly. What bounds it: bonds must be
real and matured (`BOND_MIN`, `BOND_MATURITY`, two weeks and 100,000 YEC in total for five), the
day's notice is public, the combination rule means a captured attestor set can still only grief
(§10.3), and displacement by higher-weighted honest registrants follows at the next SNAP. A
release can still override with a parameter-set change if testnet shows the trigger being
gamed; nothing here prevents that.

---

## 7. The attestation statistic

Given a verified bundle (§8.2) for a transaction with `refHeight = R`, let `C` be its
attestations — BUNDLE-1 already guarantees each is from a selected attestor (§8.4; the
selection excludes attestors pinned at `R`, §10.1), unique, fresh (`citedHeight ∈ (R −
ATTEST_MAX_AGE, R]`) and validly signed. If `|C| < M_SELECT`: `aMint`, `aClaim` undefined. Otherwise sort `C` by price ascending,
accumulate `weight(seq)` at `R`, and take

- `aMint` = the price at which cumulative weight first reaches `⌈Q_LOW_BPS · total / 10⁴⌉`,
- `aClaim` = the price at which cumulative weight first reaches `⌈Q_HIGH_BPS · total / 10⁴⌉`.

**A one-sided quantile, not symmetric trimming.** Centring is the wrong target: each operation
has a side it can be hurt from and the statistic sits on that side. Robustness comes from rank,
not magnitude.

### 7.1 The cross-section is unchanged in form

Revision 5 proposed a per-pool, block-share-weighted cross-section in place of the block
medians. Revision 6 does not: the medians with their fill rule are implemented, fuzzed and
reproduced by the independent Python model (N23), and the property this document adds does not
depend on how the first population is summarised. Recorded in §16 as a possible refinement.

### 7.2 `Q_LOW`, `Q_HIGH` and the selection size

**Rule:** `Q_LOW` must exceed the largest single-entity weight share among the selected
attestors and `Q_HIGH` must be below one minus it, or one participant spans the threshold alone.
Expected seating is 4–11 with 6–8 active; a high `BOND_MIN` compresses weights into a band above
the floor (eight attestors, one at 3× and seven at 1×: the largest share is 30 %), and the
founding cohort's shared age compresses them further. **`Q_LOW_BPS = 3,333`, `Q_HIGH_BPS =
6,667`**: two independent participants must agree before either statistic moves.

Selection draws `M_SELECT + K_SLACK = 6` from a seated set of up to 9 and requires
`M_SELECT = 4` of them (§8.4). When the seated set is smaller than 6 the selection is the whole
set and cherry-pick resistance degrades to the combination rule alone; `yed_getinfo` reports
this and the wallet shows it.

The asymmetry that makes the residual tolerable: an attestor quoting high sorts to the top,
where `Q_LOW` never reaches, so `aMint` cannot be inflated by one party; two combining to
depress `aMint` force over-collateralization — griefing, not theft.

### 7.3 `BOND_MIN`

**20,000 YEC.** Since §10.3 establishes that attestors grief rather than extract, the bond
prices griefing and can sit where a committed community participant can meet it.
YEC-denominated deliberately — a dollar bond would need the price feed to evaluate registration,
which is circular — so the barrier scales with YEC and the figure is revisited by release if
YEC appreciates materially. A parameter, not a constant.

### 7.4 Minimum contributing entries

`M_SELECT = 4` contributing attestations, after the exclusions. Below it the statistic is
undefined: the mint is VOID (and the strict template filter skips it; the wallet refuses to
build it), the claim is invalid.

### 7.5 Population overlap

Pools are expected among the attestors, and an entity in both populations weakens §3's
independence in proportion to its weight. No protocol remedy exists: identity cannot be proven
on chain, forbidding pool-operated attestors is unenforceable, and a rule keyed to *declared*
affiliation punishes only honesty. **Resolution:** the `flags` bit is voluntary disclosure;
`yed_listattestors` and the explorer publish the overlap. A standing residual (§17).

---

## 8. The bundle and its carrier

### 8.1 The carrier input now; the `OP_RETURN` layout as the stated target

Revision 5 put the bundle in a ~426-byte `OP_RETURN`. Its reading of the pinned source was
right — the 80-byte limit is relay policy (`nMaxDatacarrierBytes`, `standard.cpp:19`,
`policy.cpp:51-53`), not consensus — but the remedy, a prefix-gated carve-out shipped in the
standard `ycashd` release, makes minting reachability depend on network-wide adoption of a
policy change the Ycash maintainers would have to accept and every node operator install.

The scriptSig of a P2SH input is a data carrier that is **standard on every stock node today**:
`IsStandardTx` accepts a push-only scriptSig up to 1,650 bytes (`policy.cpp:88-97`),
`AreInputsStandard` checks a P2SH input on sigop count alone (`policy.cpp:178`), and each push
is bounded only by `MAX_SCRIPT_ELEMENT_SIZE = 520`. A **carrier output** is a P2SH output whose
redeem script discards one data push and checks the spender's signature:

```
carrierScript  = OP_SWAP OP_SHA256 <SHA256(bundle) 32> OP_EQUALVERIFY <carrierPubKey> OP_CHECKSIG   (72 bytes)
carrier output = P2SH(HASH160(carrierScript)), nValue = CARRIER_VALUE
scriptSig      = <bundle ≤ 520> <sig> <carrierScript>
```

Execution: stack `[bundle, sig]` → `OP_SWAP` → `[sig, bundle]` → `OP_SHA256` → `[sig, h']` →
push `h`, `OP_EQUALVERIFY` → `[sig]` → `OP_CHECKSIG` → `[true]`; `CLEANSTACK` is satisfied,
`MINIMALDATA` is satisfied by `OP_PUSHDATA2` for a 256–520-byte push, one sigop. Consensus
verifies it with `P2SH | CLTV` like every other input (`main.cpp:2931`).

**The redeem script commits to the bundle, so the carrier is made per transaction (R2).** The
wallet fixes `refHeight = R`, builds the bundle, funds a carrier whose redeem script names its
hash, waits one confirmation, and then broadcasts the mint or claim that spends it — two
transactions, one block apart, both expiring at `R + REF_WINDOW`. The cost is one small output
and one block of latency per mint or claim, borne by the minter — the allocation the design
intends.

*Consequence for shielded funding.* A mint funded from `ys1…` (plan §4.6) now has one
transparent input, the carrier. The wallet creates carrier outputs to fresh keys from shielded
funds, so the input links to nothing but itself; the collateral and change stay as shielded as
before. Stated so the wallet's privacy notes can say it.

**Malleability — why the commitment cannot live in the payload.** A scriptSig push is covered
by no signature. An earlier form of this revision committed a 16-byte hash of the bundle in the
`OP_RETURN` payload; that *detects* a substituted bundle, but detection makes the mint VOID and
locks the collateral until `lockHeight` — so any relay node or miner could lock a stranger's
collateral for the term at zero cost, a grief nobody but the owner can cause in v2. The redeem
script is covered (it is the input's `scriptCode` under ZIP-243) and is pinned by the P2SH hash
in the funding output, so with the hash there a substituted bundle simply fails script
verification and the transaction is invalid, never VOID. MINT and REDEEM therefore grow by one
byte only (`attestFeeVout`): 52 and `11 + 5·count`.

**The stated target (Decision D-1).** The carrier input is what ships. The `OP_RETURN` layout
of revision 5 is retained as the encoding that *replaces* it if and when stock `ycashd` relays a
prefix-gated oversized carrier — a change to `policy.cpp`'s `TX_NULL_DATA` branch that this
document recommends the Ycash maintainers consider on its own merits, separately from
Yellowback. Specified so the switch is mechanical, not a redesign:

- **Layout.** `OP_RETURN <one push>`: the v3 payload of §8.3 immediately followed by the bundle of §8.2 (`"YA" ‖ version ‖ count ‖ attestations`), ≤ 520
  bytes in one `OP_PUSHDATA2` push. The payload's `type` byte distinguishes the two shapes:
  a MINT/REDEEM whose body is longer than its fixed size carries an inline bundle.
- **Verification.** BUNDLE-1 unchanged except that the bundle is read from the payload; no
  carrier and no hash commitment are needed (the `OP_RETURN` is covered by every input's
  signature), and the payload reader admits a body of up to 520 bytes for these types.
- **Switch.** A parameter `BUNDLE_CARRIER ∈ {SCRIPTSIG, OP_RETURN, EITHER}` of the set in
  force (K10); `EITHER` accepts both shapes during a transition. The wallet builds whichever
  the set names, defaulting to the scriptSig carrier under `EITHER` until the relay change is
  observed on the network. Two encodings, one verifier, one test matrix (§18).

### 8.2 The bundle

```
"YA" ‖ version u8 = 1 ‖ count u8 ‖ count × attestation(74)        ≤ 4 + 6 × 74 = 448 bytes
```

Up to `BUNDLE_MAX = 6` attestations (`M_SELECT + K_SLACK`; the 520-byte push allows 6, and
that is the design cap). Push-only, minimal, one push.

**BUNDLE-1** (verification, for a transaction with `refHeight = R` where
`Snapshots[R].attest.status == ARMED`): exactly one input's scriptSig has the shape `<bundle> <sig>
<carrierScript>` with `carrierScript` of the form above (the vault input, `vin[0]` of a REDEEM,
is never the carrier) and `SHA256(bundle)` equals the hash in that redeem script; the bundle is
well-formed; `M_SELECT ≤ count ≤ BUNDLE_MAX`; every attestation's `seq ∈ selected(R,
selector)` (§8.4), no `seq` twice,
`citedHeight ∈ (R − ATTEST_MAX_AGE, R]`, `citedHeight ≥ START_HEIGHT`, price in range, and
`sig` verifies under that attestor's `attestorPubKey` over the message of §4 with
`blockHash(citedHeight)` from the index. An attestation that fails any per-item check makes
BUNDLE-1 false (no partial credit: the wallet has every fact needed to build a clean bundle).
When BUNDLE-1 is false the bundle is absent: MINT-9 fails (VOID), RED-1 fails (invalid).

**Cost.** Up to six ECDSA verifications per bundle, inside `ProcessTx` for every transaction
that carries a v3 price-dependent payload — comparable to the per-input signature checks
`ConnectBlock` already performs. Evaluate the bundle only after the transaction's other rules hold (for a mint: after
MINT-1..4 and 6..8, so a real vault output and a real `FEE_MIN` pool fee precede every signature
check), order the bundle checks cheapest first (shape, hash, count, membership, freshness, then
signatures), and cache per-attestation signature validity keyed by the attestation bytes and the
cited block hash — context-free, so no reorg or selector can stale it. A block stuffed with
valid bundles costs its author `FEE_MIN` per transaction and the verifier at most ≈ 20,000
signature checks (1–2 s); recorded for the plan's DoS review (§18).

### 8.3 Payload types

Added to plan §3.3 (header `"YB" ‖ version ‖ type`, fixed-width little-endian):

| Type | Body | Size incl. header |
|---|---|---|
| `0x01` MINT (v3) | as v2 `+ attestFeeVout u8` | 52 |
| `0x02` TRANSFER | **unchanged from v2**: `count u8`, `count ×` (`vout u8`, `cents u32`) — reads no price, carries no bundle, no fee vout, no carrier input | 5 + 5·count → count ≤ 15 |
| `0x03` REDEEM (v3) | as v2 `+ attestFeeVout u8` | 11 + 5·count → count ≤ 13 |
| `0x05` ATTESTOR_REGISTER | `attestorPubKey 33`, `bondPubKey 33`, `bondLocktime u32`, `flags u8` | 75 |
| `0x06` CLAIM_NOTICE | `vaultTxid 32`, `vaultVout u8`, `refHeight u32` | 41 |
| `0x07` EQUIVOCATION | empty (the carrier holds the two attestations) | 4 |
| `0x08` ATTESTOR_REVIVE | one attestation, 74 B (§12) | 78 |

Payload **version 3** for the release (V23: a v2 node ignores it; nothing is on mainnet).

Only the price-dependent operations change shape: MINT, REDEEM (owner and claim paths) and
CLAIM_NOTICE. TRANSFER, the everyday operation, keeps the v2 layout, stays inside every stock
node's relay policy, and does not depend on attestor liveness — with every attestor offline,
YED still moves between holders; only minting and claims pause.

### 8.4 Selection: the minter does not choose

If the minter chose which attestations to include, they would choose the favourable ones.
For a transaction with `refHeight = R` and `selector` — the 36-byte vault outpoint for REDEEM
and CLAIM_NOTICE, and **empty for MINT**. (FEE-W's mint selector, `ownerPubKey`, is not usable
here: the minter chooses that key freely and could grind it until the selection suited them; all
mints at one `R` therefore share one selection, and the only grind left is the 40 reference
heights below.)

```
pool(R)               = Snapshots[R].seated[] minus Snapshots[R].pinnedSeqs[]
selected(R, selector) = M_SELECT + K_SLACK attestors drawn from pool(R)
                        without replacement, weighted by weight(seq) at R,
                        seed = SHA256(Snapshots[R].blockHash ‖ selector ‖ "S")
```

(the FEE-W draw repeated with the drawn entry removed; when `|pool| ≤ M_SELECT + K_SLACK`,
the whole pool). Drawing from the unpinned set keeps `K_SLACK` for genuine outages rather than
spending it on attestors the statistic would discard anyway. Only attestations from `selected` contribute (§7); at least `M_SELECT` must.
`K_SLACK` absorbs an offline attestor without halting minting.

**Residual grinding.** The minter chooses `R` among the last `REF_WINDOW = 40` heights and so
among 40 draws. Against a 9-seat set that is enough to find a draw excluding two specific
attestors most of the time. The bound is the combination rule: a draw of high attestors lifts
`aMint` no higher than `xMint`, and a draw of low attestors on a claim lowers `aClaim` no lower
than `xClaim`. Grinding pays only when the cross-section is already corrupted in the same
direction — the case the design already concedes to a majority of both populations. The attestation
window is a separate lever: `ATTEST_MAX_AGE = 20` (R4) leaves at most two of each attestor's
signed prices in a bundle's window, bounding the per-attestor cherry-pick a builder can do
within the selection; tying the seed to a coarser height
(`R − R mod 40`) would, at the cost of a stale seed. Recorded in §16.

**No latency race.** Selection is independent of who was fastest; an attestor earns by being
seated, bonded and reachable, not by being first.

### 8.5 Reorgs

A bundle's attestations cite heights `≤ R`. If a reorg removes the block at any cited height it
has removed the block at `R` too, and v2 already accepts that a reorg deeper than `REF_LAG` can
void a mint (V11, §8.2 "Mint races the supply cap or a reorg changes its snapshot"). The bundle
adds **no reorg exposure beyond `refHeight`'s own.** The wallet's existing behaviour — watch to
`WALLET_CONFIRMATIONS`, rebuild with a fresh `refHeight` (and hence a fresh bundle) if the
transaction is dropped — covers it; the strict template filter keeps enforcing pools from
mining a mint whose bundle no longer verifies.

---

## 9. Reference prices: nothing new

Revision 5 carried `max_price`/`min_price` and `valid_until_height` in every mint and claim.
v2 already has the stronger form: `refHeight` fixes the snapshot every rule reads (V11), the
bundle is fixed by the carrier's redeem script, so the wallet computes the exact `pMint` before signing;
`nExpiryHeight = refHeight + REF_WINDOW` bounds the transaction's life and MP-1 requires it for
vault spends. There is no free option in the mempool because there is no price discovery after
signing. The wallet's job is display: *"Mint 1,000 YED — collateral 6,000 YEC at $1.58/YEC
(attestors $1.61 from 5 of 6 selected, pools $1.58)"*, and the reason when it cannot build.

---

## 10. Pinned quotes: the lazy equilibrium

The most probable failure mode in the document. **It requires no collusion.** A maintained feed
costs effort; a constant in a config file satisfies every rule and earns the same fee. Universal
pinning is the default outcome of indifference.

**It breaks the combination rule asymmetrically.** With the cross-section pinned at $1:

| true price | `pMint = min` | effect | `pClaim = max` | effect |
|---|---|---|---|---|
| $4.00 | 1 | 4× over-collateralization; minting dies | — | safe |
| $0.25 | 0.25 | correct | **1** | **vaults look healthy at 4× their real coverage; claims never open** |

The damage lands in the claim path, from a source that is stale-*high*. Three remedies, together.

### 10.1 Responsiveness test

Truth is unverifiable; *movement* is not. A quote unchanged over `PIN_WINDOW` blocks while the
**other** source moved by more than `PIN_DELTA_BPS` is a constant, not a price.

The attestation side has no per-height series, so the test reads what landed. `BundleLog
height → { aMint, aClaim, selectedSeqs[], seqs[], prices[] }` records every verified bundle (one row per height:
the `lowerMedian` of that block's bundle statistics, and the union of their attestations).

**PIN-1 (pools).** At SNAP for `H`, over `W = (H − 1 − PIN_WINDOW, H − 1]`: let `aHi`, `aLo` be
the greatest and least `BundleLog[h].aMint` for `h ∈ W` (the test is **armed** iff at least
`PIN_MIN_BUNDLES` rows exist in `W` and `(aHi − aLo) · 10⁴ > PIN_DELTA_BPS · aLo`). When armed,
`payoutKey k` is **pinned at `H`** iff `k` has at least `PIN_MIN_TAGS` quote tags in `W` all
carrying one `priceMicroUsd`. Effect: for the medians and for `E(H)`, a pinned key's quote
tags are read as signal-only (they still count for ACT-1). `Snapshots[H].pinnedKeys[]`;
per-height, nothing carried — a key un-pins the moment its quote moves.

**PIN-2 (attestors).** Symmetric: armed iff `xMint` at `H − 1` and at `H − 1 − PIN_WINDOW`
differ by more than `PIN_DELTA_BPS`; attestor `seq` is pinned iff it appears in at least
`PIN_MIN_TAGS` rows of `BundleLog` in `W` all at one price. Effect: contributes nothing to any
bundle statistic at `R = H` and is not a fee candidate. `Snapshots[H].pinnedSeqs[]`.

Both read only snapshots and rows already written, so there is no circularity with this
height's statistics. If no bundle landed in the window, PIN-1 never arms — correct, since with
no mints there is nothing on the mint side to protect, and the claim side is protected by the
claimant's own bundle (§10.3).

**What this is not.** Not a deviation test: it penalises a quote for *failing to move* while
the market moved, never for being far from its peers.

| | provisional | rationale |
|---|---|---|
| `PIN_DELTA_BPS` | 500 (5 %) | above routine noise on a thin book; below any move a maintained feed would miss |
| `PIN_WINDOW` | 288 blocks (~6 h) | a feed polling every 10 blocks has had ~29 chances to update |
| `PIN_MIN_TAGS` / `PIN_MIN_BUNDLES` | 3 / 2 | one unchanged sample is a sample, not a constant |

Provisional pending §16's calibration; bias larger initially.

**Limit.** It catches a source that is frozen, not one that is merely wrong.

### 10.2 Divergence: per transaction, not a global halt

Revision 5 halted minting when the two statistics diverged for `DIVERGE_PERSIST` blocks. With
attestations carried per transaction, the natural rule is per transaction:

**MINT-10** `|xMint(R) − aMint| · 10⁴ ≤ DIVERGE_BPS_ATTEST · min(xMint(R), aMint)`. A mint
whose bundle disagrees with the cross-section by more than 15 % is VOID — and never built,
since the wallet evaluates the same predicate on the same inputs first and the strict template
filter skips it. In effect minting pauses while the sources disagree, with no carried state, no
persistence parameter and no operator to train. A single stale attestation cannot trip it: the
quantile is over `M_SELECT` or more, and the wallet can wait a block for fresher ones. The
plan's intra-cross-section HALT-3 (`DIVERGENCE_BPS`, 20 %) is unchanged.

Claims carry no divergence rule: `max` is the protection.

### 10.3 Emergency claims: OR trigger, adverse payout, residual returned, two steps

The structural fix and the one deliberate exception to §3. **The trigger is relaxed; the
payout is not.** Because attestations reach the chain only when carried, persistence is carried
too: the claimant shows the condition twice, at least `EMERGENCY_PERSIST` blocks apart.

**Step 1 — CLAIM_NOTICE.** An ordinary transaction with a carrier input and payload `0x06`:
`vaultOutpoint`, `refHeight = R₁`. **NOT-1:** the vault is ACTIVE, BUNDLE-1
holds with selector = `vaultOutpoint`, and for `pEmerg₁ = min(xClaim(R₁), aClaim(bundle))`:
`v.collateralZat · pEmerg₁ < v.mintedCents · EMERGENCY_RATIO_BPS · COIN`. If it holds:
`Notices[vaultOutpoint] = { height = H, refHeight = R₁, pEmerg₁ }` — **only if no record
exists whose `refHeight` is within `EMERGENCY_NOTICE_TTL` of `H`**; while one stands, further
notices are ignored. Otherwise the vault owner could post a fresh notice every 47 blocks and hold
the clock at zero indefinitely. A notice never makes a block invalid and is not a vault spend.

**Step 2 — the claim.** RED-4 clause (b): a `Notices[vaultOutpoint]` record exists with
`EMERGENCY_PERSIST ≤ R − notice.refHeight ≤ EMERGENCY_NOTICE_TTL`, and with this claim's
bundle `pEmerg = min(xClaim(R), aClaim(bundle))` satisfies the same inequality at `R`.
Clause (a) is the existing rule: underwater at `pClaim = max(xClaim(R), aClaim(bundle))` under
`CLAIM_THRESHOLD_BPS`. **RED-4 holds iff (a) or (b).**

*Anyone* may post a notice — a YED holder, an explorer, a script. The vault owner sees it
(`yed_listpositions` shows `noticed`) and has an hour to top up by redeeming and re-minting, or
to accept the liquidation.

**Payout (RED-5, new, applies to every claim-path spend).** The claimant keeps at most the
debt's value at the *adverse* price — plus the threshold margin **only when the pools agree the
vault is underwater**; the rest returns to the owner:

```
marginBps      = CLAIM_THRESHOLD_BPS if RED-4 holds by clause (a), else 10⁴   (clause (b) alone: no margin, R1)
claimantMaxZat = ⌈ mintedCents · marginBps · COIN / pClaim ⌉                   (units cancel as in v2's Claimable, R5)
residualZat    = max(0, v.collateralZat − claimantMaxZat)
```

Check: $100 of debt at 110 % and `pClaim = 18,333` µUSD ⇒ `10⁴ · 11,000 · 10⁸ / 18,333 ≈
6.0·10¹¹` zat = 6,000 YEC, v2's worked example. **Why no margin under (b):** with the margin, a
captured attestor set could open emergency claims on every vault and collect 10 % of each debt
— extraction, not griefing. Paying exactly the debt at the adverse price leaves the attacker its
fees and nothing else.

RED-5: if `residualZat ≥ RESIDUAL_MIN_ZAT`, some output that is neither a token, the payload,
the pool fee nor the attestor fee pays `P2PKH(ownerPubKey)` at least `residualZat`. `pClaim`
undefined ⇒ RED-5 false (M1) ⇒ the claim is invalid: the emergency tier needs an adverse price
to pay at, and since BUNDLE-1 already holds, `aClaim` is defined and so is `pClaim`.

Why RED-5 applies to normal claims too: at `CLAIM_THRESHOLD_BPS = 110 %` the residual of a
normal claim is zero by construction, so the routine case is unchanged, and one rule is easier
to reason about than two. It also closes, as a side effect, the L9 attack's payoff: a
cross-section majority that opens claims on a healthy vault collects 110 % of the debt, not
300 % of it.

**Why the separation is load-bearing.** Working the four directions an attestor set can push:

| attackers push | `pMint = min` | normal claim `pClaim = max` | emergency `pEmerg = min` |
|---|---|---|---|
| **high** | no effect | claims held shut (bounded: the honest source still fires the emergency tier) | still fires |
| **low** | over-collateralization | no effect | **fires on healthy vaults** |

Three cells are griefing. The fourth was extraction under whole-vault distribution: a
low-pushing selected set opens the tier on a 300 %-covered vault and the claimant takes all of
it. With RED-5 paying exactly the debt at `pClaim = max` — the honest source, no margin — and
returning the residual, the same attack forces an early liquidation at an honest price with the
remainder returned: the owner loses the position, not the capital, and the attacker gains
nothing but the fee outputs it paid. With two steps an hour apart, it takes the selected
attestors misreporting on chain twice, an hour apart, against a warned owner, to do even that.
**Attestors grief; they do not extract**, provided the OR trigger, the adverse payout, the
residual and the two-step persistence ship together.

**Liveness.** The emergency tier needs a bundle, so it needs live attestors. Revision 5 wanted
it to work with every attestor dead; no design can, because with attestors dead and the
cross-section pinned high there is no honest price to open anything with. What this design
guarantees is narrower and true: if *either* population is honest and live, claims on a
genuinely underwater vault open within `EMERGENCY_PERSIST` blocks of a notice.

### 10.4 Scope

§3's rule holds when each source errs in an unknown direction and fails when one is persistently
biased in a known one. Pinning is the likeliest cause, not the only one. PIN-1/2 guard the
frozen case; MINT-10 and the emergency tier bound the rest.

---

## 11. Fees

Attestors are paid for attestations that are **used** — carried in a mint or claim that
confirmed — never for attestations published. Publication is unverifiable on chain and paying
for it invites signing garbage on a timer.

**AFEE-1.** `A` = the `seq` values of the transaction's contributing attestations `C` (§7).
If `A` is empty (impossible when BUNDLE-1 holds, stated for totality) ⇒ **AFEE-0**, no attestor
fee, `attestFeeVout` ignored. Otherwise `attestFeeVout ≠ 0xFF` names an output that pays
`P2PKH(bondPubKey(s))` for some `s ∈ A` at least `attestFeeZat = feeZat(collateralZat) ·
ATTEST_FEE_BPS / 10⁴`, distinct from every other assigned vout (MINT-8/RED-3's exclusions plus
the pool fee output). **Additive** to the pool fee, not carved from it (Decision D-3): the pool
fee is what makes pools run the module. MINT-8 and RED-3 gain the clause.

**Wallet default (AFEE-W, policy).** As FEE-W over `A`, weighted by `weight(s)`, seed
`SHA256(blockHash(R) ‖ selector ‖ "A")`; `-yellowbackpreferredattestor` overrides when that
`seq ∈ A`. Expected income is proportional to bond weight and reachability, never to latency.
An attestor that is selected but unreachable appears in no bundle, earns nothing, and trips
dormancy.

---

## 12. Ejection

Three mechanical paths, no vote.

**Equivocation.** Two valid attestations by one `seq` for one `citedHeight` with different
prices are a self-proving fraud. Anyone submits both in a carrier input with payload `0x07`
(the carrier's redeem script commits to a two-attestation bundle). **EQV-1:** the bundle is exactly two
attestations, same `seq`, same `citedHeight`, different `priceMicroUsd`, both signatures valid
(the `seq` need not be seated, and `citedHeight` need only be `≥ START_HEIGHT` and on the
chain). Both signatures are verified against the *current* chain's `blockHash(citedHeight)`, so
two honest attestations signed on two sides of a fork — different hashes, possibly different
prices — are not an equivocation; only two prices for one block are. If it holds: `status = EJECTED` at `H`; `attestorPubKey` and the bond outpoint can
never re-register (REG-A1); the bond is not seized (§5.1) and sits as dead capital until
`bondLocktime`.

**Dormancy.** Only a seated attestor can appear in a bundle, so only a seated attestor can be
dormant. `seq` is DORMANT at SNAP for `H` iff it was seated at every height in `(H −
DORMANCY_BLOCKS, H]`, at least `DORMANCY_MIN_BUNDLES` `BundleLog` rows in that window list it
in `selectedSeqs[]`, and none lists it in `seqs[]` — selected that often and never delivered.
The second condition is revision 5's hazard, made a rule: during a halt or a quiet period there
are no bundles, and nobody goes dormant for it. A DORMANT attestor is not seated and earns
nothing.

**Revival.** A DORMANT attestor cannot be selected, so it cannot re-appear in a bundle; it
revives with one transaction of its own — payload `0x08 ATTESTOR_REVIVE`, a single attestation
(`seq ‖ priceMicroUsd ‖ citedHeight ‖ sig`, 78 bytes with the header; no carrier). **REV-1:**
the record is DORMANT, `citedHeight ∈ (H − ATTEST_MAX_AGE, H − 1]`, the signature verifies ⇒
`status = ELIGIBLE`, age preserved. The one on-chain act the design asks of an attestor after
registration, and only after a fortnight of being selected and absent — proportionate, and not
the periodic burden §1 forbids.

**Displacement.** A higher-weighted ELIGIBLE attestor takes the lowest seat at the next SNAP.
Unseated attestors keep publishing and keep their age.

---

## 13. Transport and the node boundary

The gossip layer carries no trust. Every attestation is a signature over
`{seq, price, citedHeight, blockHash}` verified against a key set read from the chain.
Transport cannot forge or alter; it can only **withhold or delay**. Optimise for reachability.

**The node boundary.** `ycashd` verifies and builds; it does not connect anywhere. Two
processes outside it, both shipped from `contrib/yellowback/` and both free to use a current
Rust toolchain since they do not enter the node's `depends` build:

- **`yellowback-attest`** (the attestor agent): polls sources, signs every `k` blocks with the
  hot key, publishes to the gossip topic. Reads the chain tip and `Snapshots` through its node's
  RPC (`yed_getinfo`, `getblockhash`). Runs anywhere with outbound connectivity. After two failed
  polls it publishes nothing — a missing attestation is the correct report of a broken feed
  (L5's rule).
- **`yellowback-attest subscribe`** (the wallet-side subscriber): joins the topic, verifies each
  attestation against `yed_listattestors`, and pushes it into the node's **attestation pool**
  with `yed_addattestation <hex>`. Runs beside any minting node; YecWallet launches it beside
  the `ycashd` it bundles (§4.8).

**The attestation pool** is node-local, in-memory, non-consensus state (the mempool's cousin):
`yed_addattestation` re-verifies the signature against the current seated set and keeps the
last three attestations per `seq` (an attestor's node may be a block ahead, so its newest may cite above the minter's `R`; the builder takes the newest at or below `R`); `yed_getattestations` lists
it; `yed_mint`, `yed_claim` and `yed_claimnotice` build the bundle from it by §8.4's selection
and refuse, with the reason, when fewer than `M_SELECT` of the selected are present.
`yed_buildbundle <refHeight> <selector>` returns the bundle hex for manual use and
`yed_mint … bundleHex` accepts one — the last-resort path that keeps minting possible under
total transport failure. A restart empties the pool; the subscriber refills it.

**Carrier step.** Every mint, claim, notice and equivocation report is two transactions: the
carrier funding transaction (committing to the bundle chosen for `R`), then the main one after
one confirmation. Carriers and bonds are not `IsMine` — their scripts are non-standard to
`Solver` — so the wallet's Yellowback layer records outstanding carriers in a datadir file,
signs them by hand as it signs the vault input, and sweeps any whose window lapsed
(`yed_sweepcarriers`). Nothing is written to `wallet.dat`.

**Attestor-side RPCs.** `yed_registerattestor <bondYec> <lockBlocks>` builds the registration
(§5.2) and records the bond; `yed_withdrawbond` spends it after `bondLocktime`; `yed_revive`
builds the revival transaction of §12. None is periodic.

**Primary transport: `iroh-gossip`**, in the two agents. QUIC with hole-punching and relay
fallback means an attestor behind NAT reaches subscribers — the population worth having. Costs
acknowledged: a dependency on relay infrastructure someone must run (several independent
parties; the relay list configurable, never compiled in), and a second binary beside the node.
A global relay failure halts minting; the mitigation is organisational. **Not** an `iroh`
dependency inside `ycashd`: that would put a QUIC stack into a codebase whose network surface
the plan deliberately does not touch, and would wait on the `depends` Rust toolchain.

*On that toolchain.* The pinned Rust is 1.63 (August 2022; `depends/packages/native_rust.mk`).
The product owner's view, recorded here: four years of compiler and standard-library fixes is
reason enough to propose a bump to the Ycash maintainers on its own merits. That proposal is
separable from Yellowback — it re-vendors the crate set and re-verifies the Sapling FFI — and
nothing in this document waits on it.

**Optional: HTTPS.** An attestor *may* serve its current attestation at an endpoint declared
off-chain (agent config, published by the explorer); the subscriber polls declared endpoints as
a second path. Deliberately optional: requiring it would exclude exactly the participant §1
wants seated.

**Light clients** cannot gossip; `lightwalletd` gains `GetAttestations`, and the client
verifies every signature against the seated set it reads from the chain. The server is a relay
it cannot lie through — only withhold from — the trust already extended for block data.

**User experience.** Ideally invisible: the wallet shows the two source prices and the
reference price it will mint at; on failure, *"Price attestations unavailable (3 of 6 selected
attestors reachable) — cannot mint right now"*, which is correct: no fresh price, no new debt.

---

## 14. Reorg handling

No new consensus-shaped rule. `refHeight` (V11) fixes which snapshot a mint or claim reads and
bounds how stale it may be; a bundle cites heights at or below it (§8.5) and adds no exposure.
`WALLET_CONFIRMATIONS` (default 6, user-configurable) remains a wallet policy and is
deliberately a different number from `ATTEST_MAX_AGE`.

---

## 15. Parameters

75-second blocks (Blossom active on Ycash mainnet at 1,100,000, `chainparams.cpp:131`): 48 ≈
1 h, 1,152 ≈ 1 d, 8,064 ≈ 1 w. **Every consensus-shaped duration is in blocks**; real spacing
on a small chain can swing 2× between adjustments, so no window is short enough for its
duration to matter. Every row is consensus-shaped among enforcing miners and versioned by
parameter set (K10) unless marked **policy**.

| Parameter | Purpose | Mainnet | Regtest | ≈ |
|---|---|---|---|---|
| `ATTEST_ARM_MIN` / `ATTEST_ARM_DELAY` | ELIGIBLE attestors that trigger arming / blocks from trigger to armed (§6.4) | 5 / 1,152 | 3 / 8 (`-yellowbackattestarmmin` override, 0 = never arms) | 1 d |
| `BUNDLE_CARRIER` | which bundle encoding is accepted (§8.1) | `SCRIPTSIG` | `SCRIPTSIG` (`-yellowbackbundlecarrier` override) | — |
| `N_SLOTS` | seated attestors | 9 | 5 | — |
| `M_SELECT` / `K_SLACK` | required / extra selected (§8.4) | 4 / 2 | 2 / 1 | cap 6 (§8.2); regtest arms at 3 so one attestor may be down |
| `BUNDLE_MAX` | attestations per bundle | 6 | 6 | 520-byte push |
| `Q_LOW_BPS` / `Q_HIGH_BPS` | adverse quantiles (§7.2) | 3,333 / 6,667 | same | — |
| `ATTEST_MAX_AGE` | max `R − citedHeight` (§7) | 20 (= 2·k) | 8 | 25 min; R4 |
| `k` | attestor signing interval (**policy**, agent) | 10 | 4 | 12.5 min |
| `CARRIER_VALUE` | carrier output value (**policy**, wallet) | 10,000 zat | same | — |
| `PIN_WINDOW` / `PIN_DELTA_BPS` | responsiveness test (§10.1) | 288 / 500 | 16 / 500 | ~6 h |
| `PIN_MIN_TAGS` / `PIN_MIN_BUNDLES` | samples before a constant is a constant | 3 / 2 | 2 / 2 | — |
| `DIVERGE_BPS_ATTEST` | MINT-10 per-bundle divergence (§10.2) | 1,500 (15 %) | same | — |
| `EMERGENCY_RATIO_BPS` | emergency tier threshold (§10.3) | 10,500 | same | — |
| `EMERGENCY_PERSIST` / `EMERGENCY_NOTICE_TTL` | notice → claim distance, min / max | 48 / 1,152 | 4 / 64 | 1 h / 1 d |
| `RESIDUAL_MIN_ZAT` | RED-5 dust floor | 100,000 | same | 0.001 YEC |
| `ATTEST_FEE_BPS` | attestor fee as a share of `feeZat` (§11) | 2,500 (25 %) | same | — |
| `BOND_MIN` | minimum bond (§7.3) | 20,000 YEC | 10 YEC | ≈ $10k |
| `BOND_MIN_LOCK` | minimum CLTV distance at registration | 420,480 | 200 | ~1 y |
| `BOND_MATURITY` | PENDING → ELIGIBLE | 16,128 | 8 | ~2 w |
| `AGE_CAP` | weight accrual ceiling | 207,360 | 64 | ~6 mo |
| `FOUNDING_WINDOW` | shared age origin after arming (§6.3) | 8,064 | 16 | ~1 w |
| `DORMANCY_BLOCKS` / `DORMANCY_MIN_BUNDLES` | absence → DORMANT (§12) | 16,128 / 20 | 16 / 2 | ~2 w |
| `WALLET_CONFIRMATIONS` | wallet and agent finality (**policy**) | 6 | 1 | 7.5 min |

**State added** (plan §3.6; in the state hash except where noted):
`Attestors seq → { attestorPubKey, bondPubKey, bondOutpoint, bondZat, bondLocktime, flags,
registerHeight, status ∈ {PENDING, ELIGIBLE, DORMANT, EJECTED, WITHDRAWN}, statusHeight,
bondSpentHeight }` with `BondIndex bondOutpoint → seq` (derived, unhashed);
`AttestorSeq { next u16 }`; `BundleLog height → { aMint, aClaim, selectedSeqs[], seqs[],
prices[] }` (one row per height that carried a bundle; never pruned, so that the state hash is
the same on every node — at most one row per block, ≈ 60 bytes);
`Notices vaultOutpoint → { height, refHeight, pEmerg }` (removed when the vault closes);
`Attest { status, triggerHeight, armHeight }` (carried, like `Activation`);
`Snapshots` gains `attest`, `seated[]`, `pinnedKeys[]`, `pinnedSeqs[]` and the renames `xMint`, `xClaim`;
`TxLog` gains `aMint, aClaim, bundleSeqs[], attestFeeZat, attestPayee, residualZat` (history,
excluded from the hash like the rest of `TxLog`). Every hashed field is reproduced by
`yellowback_model.py` (N23) and covered by the golden vector.

---

## 16. Decisions for the product owner, and open measurements

**Decisions — taken by the product owner, 13 September 2026, and applied in the text:**

| | Question | Decision | Where |
|---|---|---|---|
| D-1 | Bundle carrier | **scriptSig carrier input now; the `OP_RETURN` layout specified as the stated target**, switched by `BUNDLE_CARRIER` if stock relay policy ever admits it | §8.1 |
| D-2 | Residual return | **every claim-path spend** (RED-5), not emergency claims only | §10.3 |
| D-3 | Attestor fee | **additive, 25 % of `feeZat`**; the pool fee untouched | §11 |
| D-4 | Arming | **automatic: 5 ELIGIBLE attestors, then one day** (`ATTEST_ARM_MIN = 5`, `ATTEST_ARM_DELAY = 1,152`); the recommendation had been a release-set height, and the residual is recorded in §6.4 | §6.4 |
| D-5 | Selection seed | **`blockHash(refHeight)`**; 40 draws, bounded by the combination rule; revisit if testnet shows gaming | §8.4 |

**Measurements** — neither blocks implementation; both precede the first mainnet registration
(arming is automatic, so the calibration must be done before the set can form):

1. **Calibrate `DIVERGE_BPS_ATTEST`.** Log the CoinGecko aggregate against SafeTrade and
   nonkyc.io at a few-minute cadence for two weeks; take the distribution of pairwise spreads
   under normal conditions; set the threshold near three times the 95th percentile.
2. **Calibrate `PIN_WINDOW` / `PIN_DELTA_BPS`.** Over hourly YEC history, the fraction of rolling
   6-hour windows with a ≥ 5 % move (the arming rate) and the longest run without one. Arming
   rate above ~20 % confirms the values; below ~5 % drop `PIN_DELTA_BPS` to 200–300.

**Deferred, not open:** the per-pool block-share-weighted cross-section (§7.1); signed coinbase
tags (plan §12 Q14 — `ATTESTOR_REGISTER` is now a precedent for binding a key by
registration); the Rust toolchain bump (§13, proposed upstream on its own merits).

---

## 17. Residual centralization

**Attestor influence tracks capital.** Bond-weighted quantiles are a plutocracy — costly,
visible, slow-moving and bounded by the combination rule, not eliminated.

**The attestor set is smaller than the miner set.** Which is why it is never the sole source and
why §3's rule is the thing holding the design up.

**Market depth bounds everything.** An attacker who moves the traded price moves the honest
inputs to both populations. Not a flaw in the price layer; the ceiling it operates under, and
possibly cheaper than any protocol attack here.

**Pools seated as attestors erode independence (§7.5).** Unenforceable; a governance obligation.

**Transport is a liveness dependency.** Relay infrastructure someone must run; a global failure
halts minting, never soundness. The manual bundle path is the floor.

**Miners retain the hashpower-majority attack on the cross-section.** Unchanged; the attestor
layer is what keeps that majority from translating into theft from YED holders. A majority can
also censor mints and claims outright — as it can today.

---

## 18. Relationship to the development plan

Changes the plan needs, by section, for its next revision:

- **§3.1** — the rows of §15 incl. `ATTEST_ARM_MIN/DELAY` and `BUNDLE_CARRIER`; `MAX_PAYLOAD`
  unchanged; payload version 3 (V23).
- **§3.3** — MINT and REDEEM v3 (`attestFeeVout`); types `0x05`–`0x08`.
- **§3.4** — the carrier script beside the vault script; the carrier scriptSig shape.
- **§3.5** — a carrier input in MINT, REDEEM (claim path) and CLAIM_NOTICE; the attestor fee
  output; `yed_claimnotice`.
- **§3.6** — the state of §15; state-hash order extended (`Attestors`, `AttestorSeq`,
  `BundleLog`, `Notices` after `Params`).
- **§3.7** — `xMint`/`xClaim` (renamed `pMint`/`pClaim`), the bundle quantile, bond weight,
  `selected(R, selector)`, `pEmerg`, `A`, `claimantMaxZat`/`residualZat`; medians and `E(R)`
  skip pinned keys.
- **§3.8** — PRICE-2 per transaction; ARM-1/2, REG-A1, BUNDLE-1, MINT-9 (bundle present and valid),
  MINT-10 (divergence), NOT-1, EQV-1, REV-1, PIN-1/2, RED-1 (bundle required on the claim path),
  RED-4 clause (b), RED-5, AFEE-0/1 and the MINT-8/RED-3 clause; SNAP order: judgement,
  activation, **pin tests (from prior snapshots and `BundleLog`), seating**, medians, σ,
  issuance, halts, **dormancy**.
- **§3.9** — BLK-1..3 unchanged in kind: block validity is still exactly "ACTIVE-vault spends
  obey RED-1..*5*". TPL-2 strict mode additionally skips a MINT failing MINT-9/10 and a
  claim failing RED-5. MP-1 unchanged.
- **§4.1** — no new line in `main.cpp`, `miner.cpp`, `rpc/mining.cpp`, `policy.cpp` or
  `configure.ac`; the budget is unchanged. Signature verification of bundles happens inside the
  overlay's `ProcessTx`, where the vault scriptSig is already read.
- **§4.5** — `yed_listattestors`, `yed_getattestations`, `yed_addattestation`,
  `yed_buildbundle`, `yed_claimnotice`, `yed_registerattestor`, `yed_withdrawbond`,
  `yed_revive`; `yed_getprice` gains the source
  breakdown; `yed_mint`/`yed_claim` gain `bundleHex`; `rpcversion` 3.
- **§4.6 / §4.8** — the two-transaction carrier step, the subscriber beside the bundled
  `ycashd`, the two-price display, notices on the Positions page, an Attestors view.
- **§5** — `yellowback-attest` (both modes) beside the quote agent; the devnet gains two
  attestor agents and an in-process relay, and arms the layer during `up`.
- **§7** — `yellowback_attest.py` (registration, seating, weight, selection, bundle
  verification in both carrier shapes, automatic arming and its one-day delay, pinning, MINT-10, notice and emergency claim, RED-5, equivocation,
  dormancy, carrier malleation, manual bundle path), the model fields, the golden vector.
- **§8.1 (trust statement)** — "price honesty rests on honest-majority hashpower" becomes
  "moving the price in the direction that pays requires a hashpower majority and a
  bond-weighted majority of the selected attestors together; a hashpower majority alone can
  halt minting, hold claims shut for the gap between 110 % and 105 %, or censor transactions as
  it always could".
- **§8.2** — rows for attestor collusion (grief only), aggregator correlation, pinning,
  bond-weight capture, selection grinding, carrier malleation, transport failure, notice spam
  and the notice-reset attack (closed in NOT-1), bundle-verification cost under payload spam.
- **§9 (enshrinement)** — at a network upgrade the bond becomes slashable and §5.1 stops being
  a limitation.

The forkless-launch-then-network-upgrade arc is unchanged, and the attestation layer joins it
by a release with an arming height rather than by a second launch.
