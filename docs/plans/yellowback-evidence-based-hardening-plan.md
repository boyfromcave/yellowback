# Ycash Yellowback (YED) — Evidence-Based Hardening Plan

**Revision 1 (2026-10-05).** Branch `harden/yellowback` in every writable repository of the
workspace (the workspace itself, `ycash-dd`, `ycash6`, `librustzcash6`, `yecwallet-dd`,
`lightwalletd-dd`, `yew`, `yolo`, `chain-viz`, `x402-ycash`, `yb-calibration`), each cut from its
branch of record on 2026-10-05. Nothing in this plan is implemented yet.

**Input.** The first real-data calibration of the Yellowback parameter set,
`yb-calibration/docs/reports/2026-10-real/` (README, `recommended.json`, the robustness sweeps,
the devnet differential on both node lines) and its decision log `yb-calibration/docs/decisions.md`
(D-RD-*). The 2026-10-01 security audit (`docs/audits/yellowback-security-audit-20261001.md`) is
the second input: two of its findings (A-5, A-6) are load-bearing here. The code citations below
were re-verified on `ycash6` at the branch point and are identical in rule content on `ycash-dd`
(every rule file is byte-identical; `state.cpp` line numbers are the same on both lines).

**Standing rules.** AGENTS.md applies unchanged: minimal consensus footprint, both node lines
together, the `yed_*` RPCs as the only node interface, `ref/` read-only. This plan adds no line to
`main.cpp`, `miner.cpp`, `rpc/mining.cpp`, `policy.cpp` or any frozen directory. Every change is
in `src/yellowback/`, the wallets, the agents' sample configs, or the parameter set.

---

## 1. The verdict in one page

**The overlay as it stands on 2026-10-05 must not ship to mainnet.** The audit found no defect in
the mechanism. The calibration found that the mechanism was designed for a chain and a market that
do not exist: YEC's volatility is 2.3× what the parameters assume, one pool mines 52 % of blocks and
sets every price median alone, the venues are too thin to sell a $1,000 vault's collateral, and two
of the three term classes produce bad debt at any ratio the registry allows. Those are not tuning
problems. They are the environment, and the product has to be shaped to it.

**What this plan does.** It takes the calibration's recommended set as the floor and makes five
structural decisions the calibration flagged as owner-level, each on the cheapest tier that works:

1. **Attestation becomes a precondition for minting.** No YED is created on the miner price alone.
   The 52 % pool cannot mint against a price it sets by itself. (overlay rule, `state.cpp`; §3.1)
2. **Class A only at launch.** Classes B (90–365 d) and C (1–5 y) are disabled by parameter until a
   rule that acts before maturity exists. P(bad debt) for B is 7× its tolerance and for C 17×; no
   ratio fixes that. (parameter set; §3.2)
3. **The work valve is made resistant to a free attack.** A matured-vault owner can today switch
   enforcement off on every enforcing node within hours at no cost. Node-local fix in `index.cpp`,
   no consensus change. (§3.3)
4. **Activation and the enforcement gaps are bounded procedurally and by two small overlay rules.**
   Lock-in needs two consecutive windows; owner sweeps are admitted at the sunset; wallets protect
   the owner before `claimHeight`. (§3.4)
5. **Issuance is guarded.** The soft cap admits class A only; `maxMint` is sized to the real order
   book for the first parameter lifetime; the global halt moves to 300 %. (§3.5)

Plus the defects: the wallet bug that breaks back-to-back mints on both lines (F-DEV-1), the
attestor and pool sample configs that fail closed on 53 % of blocks, and the two audit residuals
that are still open (A-5 wallet warning, A-6 odometer). (§4)

**What this plan does not do.** It does not build a liquidation engine, a price-feed oracle in
consensus, a new opcode, or a network upgrade. It does not change the hashrate distribution; that is
a fact about Ycash, and §6 states what the product can and cannot promise under it. It does not
re-enable classes B and C; that needs a design the calibration can score (§8, open item 1).

**Ship criteria** are in §7: measurable launch gates, each with the number and the tool that reads
it. The release does not go out until every gate is green on both node lines.

---

## 2. Evidence: what prevents shipping, with the source

Ship blockers first, cautions second. Each row names the calibration or audit item, the code that
makes it true, and the section of this plan that resolves it.

### 2.1 Ship blockers

| # | Finding | Evidence | Why it blocks | Resolved in |
|---|---|---|---|---|
| B-1 | One pool mines 52 % of blocks, holds 72 % of quote tags and sets every median alone; it moves pFast in 1.4 h, pMid in 8.6–17 h, pSlow in 35 h; withholding its quotes gives NO_PRICE in 0.6 h. Activation is impossible without it. | README §3.2; D-RD-ORA-4, D-RD-ACT-1; medians at `state.cpp:1197-1210`, fill rule L9 | Until the attestation layer is ARMED the price that sizes collateral is one operator's number. The overlay mints on that number today (`MintVerdict`, `state.cpp:332-334`: unarmed ⇒ `pMint = xMint`). | §3.1 H-1, H-2; §3.4 |
| B-2 | Classes B and C cannot meet their bad-debt tolerance at any ratio ≤ 10,000 %: P(bad debt at claim opening) B ≈ 7 % (tolerance 1 %), C ≈ 34 % (2 %), a bad C vault short ≈ 70 % of its debt. Cause: nothing acts on a vault before `lockHeight + grace`. | README §3.1; D-RD-COL-4, `frontier.csv`, `needed_by_term.csv`; `script.cpp:79-93`, RED-2 `state.cpp:516-517` | A minter of a B or C vault is sold a product whose expected loss to YED holders is known and large. | §3.2 H-3 |
| B-3 | The work valve trips within hours, with certainty, under a free attack: any matured-vault owner keeps a no-burn owner-path sweep in stock mempools; each stock block on the enforcers' tip starts a race; the first 6-block stock burst trips every enforcing node and enforcement stays off until operator restart. | README §3.5; D-RD-ACT-5 (`valve2`: P(trip ≤ 30 d) = 1.00 at 6, median 8 h); `index.cpp:563-674`, `index.h:65` | While tripped, every vault past `claimHeight` is anyone-can-spend without burn (audit A-5). The attack costs nothing and needs no hashrate. | §3.3 H-5, H-6 |
| B-4 | A wallet defect on both node lines: a mint spends its carrier's change output, the wallet does not see it as spent until the notifier stamps the block, so the next carrier, mint or `yed_send` re-selects it and is rejected ("transaction commit failed"). Seen in 1–10 of 20–30 mints per run. | D-RD-DEV-7 F-DEV-1; `txbuilder.cpp:507-534` (`SelectYec`), `wallet.cpp:2531`/`:7812-7819` (`IsSpent`, depth −1), `rpc/yellowbackwallet.cpp:374-380` (the guard that exists only for the carrier's own input) | The first thing a user does twice fails. A stuck wtx at depth −1 is left in the wallet each time. | §4 F-1 |
| B-5 | Claimants cannot realise collateral: a $10,000 vault's liquidation is ≈ 65× the ±2 % bid depth ($119–188) and ≈ 18 days of p10 daily volume ($700); a $1,000 vault needs θ ≈ 145–150 % to be sold at a profit. The only claimant that exists is a YEC holder with YED to burn, and YED depth is unknown. | README §3.6; D-RD-COL-5, -6, D-RD-INF-4 | The claim path is the mechanism that keeps YED backed. If it does not pay, vaults stay underwater until the owner walks away. | §3.5 H-9, H-10 |
| B-6 | Every enforcement gap (IBD, reindex, valve trip, catch-up suppression, ENFORCEMENT halt, the sunset) makes every vault past `claimHeight` spendable by anyone without burn; at a sunset with no successor the exposure is ≈ 5 days before owner sweeps are admitted. | Audit A-5 (`script.cpp:90` claim branch `CLTV DROP OP_TRUE`; `index.cpp:376-445`; `state.cpp:950`) | Combined with B-1 (one pool can leave, or be rogue and never detected: D-RD-ACT-6 "a rogue ninjaraider is never detected") and B-3, this is the path by which users lose collateral. | §3.4 H-7, H-8; §5 |

### 2.2 Cautions that become launch gates

| # | Finding | Evidence | Resolved in |
|---|---|---|---|
| C-1 | NO_PRICE ≈ 1,220 h/yr with three quoting pools at the recommended windows (6 h/yr budget); 75 h/yr with the four largest payout keys; ≈ 0 with every key. | README §3.3; D-RD-ORA-1, -2 | §7 gate G-3 (pre-activation observation); §3.1 H-2 keeps L9 |
| C-2 | Sample agent configs (`attest.toml.sample:35`, `yellowback-quote.toml.sample:29`) set `min_sources = 3` with exactly three venues and a 1 h `max_age`; the agents fail closed, synchronously, on 53 % of blocks. | D-RD-ATT-2; `price.rs:26`, `:1120`, `:1129` | §4 F-2 |
| C-3 | A seat earns ≈ $33/month at 10 bps against a $50 floor; the bond's opportunity cost is ≈ $30/month. Attestors will not be funded by the product at low adoption. | README §3.4; D-RD-ATT-8 | §3.1 H-4 (fee split) |
| C-4 | Harmful attestor capture costs ≈ $50k of aged bonds (7 of 9 seats by splitting) plus the pool majority that already exists. | D-RD-ATT-4, -9 | §3.1 H-2 (arming bar), §7 gate G-5, §8 item 3 |
| C-5 | `globalRatioHaltBps` 250 %: P(system under water within grace) 2.5–6.4 % against 1.6 %; ≈ 300 % meets it but collided with class C's 300 % base. | README §3.6; D-RD-ORA-7 | §3.5 H-11 (no collision once C is off) |
| C-6 | The W20 soft-cap gate admits B and C above the cap once σref rises, inverting its intent. | D-RD-COL-9; `state.cpp:338-340` | §3.5 H-9 |
| C-7 | `sigmaRefBps` is window-sensitive: the full history says 17,000–18,000, the last 365 days 23,500–24,500, so class A's base ratio on the last year needs more than 725 %. | README §4 | §3.2 H-3 (the larger window's need decides) |
| C-8 | Spurious lock-in: a hop coalition (the 52 % pool plus an auto-switching pool) locks in within 30 days with probability ≈ 0.4–0.97 at every window inside the runbook bound, then holds the ENFORCEMENT halt until abandonment. | D-RD-ACT-4 (G5-DN-HOP); `state.cpp:1080-1090` | §3.4 H-7 |
| C-9 | The valve odometer trusts header work bounded against the previous *note*, not consensus; a griefer with ≈ 3 blocks of work per rejected root can trip it. | Audit A-6; `index.cpp:603` | §4 F-3 (closed together with H-5) |
| C-10 | The set is not lock-ready: the live spread log runs to 2026-10-18, the depth series is still short, and the final standard re-run has not happened. | README §7 | §7 gate G-1 |

### 2.3 What the calibration says is sound and this plan keeps

Named once, so the reader knows what is not in play: the overlay's arithmetic matches the
simulator at every height on both node lines (8/8 scenarios, §6 of the report); the audit found no
consensus split, theft path or remote crash; the supply chain is clean. The recommended values that
were stable in 20/20 runs (`peerMin` 12, `accuracyBandBps` 100, `dormancyMinBundles` 15,
`walletConfirmations` 24, `feeMin` 0.4 YEC) are adopted as they stand.

---

## 3. Decisions (H-1 … H-12)

Each decision states the problem, the cheapest tier that solves it, why a cheaper tier does not,
and which earlier owner decision it amends. The "tier" vocabulary is README.md's ladder: Tier 0 =
wallet, RPC, agent, parameter; overlay rule = a rule inside `ProcessTx`/`ComputeSnapshot` shared
by enforcing miners (the v2 soft-fork tier, no new hook); consensus = `src/consensus`, `src/script`,
`main.cpp` (not used by this plan).

### 3.1 The price

**H-1. Minting requires an ARMED attestation layer.** *Amends D-4's "until then v3 nodes behave as
v2".*
New parameter `mintRequiresArmed` (mainnet `true`, testnet `true`, regtest `false` by default and
settable, so every existing unarmed test keeps running). MINT-4 (`state.cpp:311-320`) gains the
clause: if `mintRequiresArmed` and not `Armed()`, verdict `mint-halted-unarmed` and the mint is
VOID like any other halted mint. Claims are unaffected (RED-1 already requires a bundle when armed;
an unarmed claim keeps the v2 path). `yed_getstats.mintableClasses` and the wallet gate MINTPOL
(`txbuilder.cpp:902-950`) mirror it; `yed_getinfo` gains `mintRequiresArmed`.
*Tier:* overlay rule (a halt bit, evaluated where the other halt bits are). *Why not cheaper:* a
wallet-only refusal does not bind a hand-built mint, and the 52 % pool runs a wallet. *Why not
procedural (publish `START_HEIGHT` after arming):* registration opens at `START_HEIGHT`
(`ApplyRegister`), so arming cannot precede it. *Effect on B-1:* `pMint = min(xMint, aMint)` on
every mint; the pool can still push `xMint` down (over-collateralising its own and others' mints)
but cannot mint against a price it inflates. *Residual:* `pEmerg = min(xClaim, aClaim)` lets the
pool alone open RED-4(b) on a noticed vault; that is a forced close at `pClaim = max` with the
residual returned (grief, not theft; v3 §8.2 row "attestor set colludes low" already accepts the
mirror case). Recorded in §5, not changed.

**H-2. The arming bar rises and arming is a launch gate.** *Amends D-4 (`ATTEST_ARM_MIN` 5).*
`attestArmMin` 5 → **7** on mainnet. D-RD-ATT-4 shows harmful capture needs 7 of 9 seats; a set that
arms with 5 can be 5 colluders. Seven matured, distinct bonds before TRIGGERED, then the one-day
notice. Gate G-5 (§7) requires that the 7 are operationally distinct (source sets, hosting, the §7.5
overlap disclosure) before `START_HEIGHT` is published; that is procedural and the layer cannot
check it, so the plan says so.
L9's fill (⌈2W/3⌉ on mid and slow) is **kept**. D-RD-ORA-2 observes that PRICE-2 covers L9's threat
once armed and that 0.6 W cuts NO_PRICE 10×, but with H-1 the unarmed window is exactly when L9 is
the only guard. NO_PRICE is addressed by adoption and measured by gate G-3.

**H-3. Collateral ratios are sized on the worse of the two data windows.** *Policy for the
calibration, not a node change.*
`sigmaRefBps` takes the recommended 18,000 (the lower reference raises the multiplier: conservative).
`baseRatioBps[0]` is **not** fixed at 72,500: the lock rule becomes "the smallest value that meets
class A's 0.5 % on *both* the full-history and the last-365-day standard runs", which the report
says is above 72,500 (C-7). `ybcal` decides the number under that rule in H-phase 4; the plan does
not guess it. `sigmaMultMaxBps` 47,500 as recommended. `claimThresholdBps` 12,500 as recommended
(D-RD-COL-6: at 125 % nine claims in ten pay for a holder-claimant).

**H-4. Attestors are paid from the attestor share, not from a larger pool fee.** *Amends D-3
(`ATTEST_FEE_BPS` 2,500).*
`feeBps` 25 → **15** (D-RD-ATT-8's own best point; the consolidation's 10 was least-harm under the
$50 floor the tool could not meet). `attestFeeBps` 2,500 → **5,000**: the attestor fee is additive
(`math.h:270`), so at 15 bps a seat's revenue doubles to ≈ $80/month at low adoption against the
$50 floor and the $30 opportunity cost, and the minter's round trip on a `minMint` class-A vault
moves from 1.69 % to ≈ 2.1 %, inside the 2.25 % the tool accepted for the 20 bps alternative. The
pools' fee does not rise. *Why:* with H-1 the attestors are the product's defence, and an unpaid
defence is not one. The split is re-decided at every renewal on observed revenue (W18).

### 3.2 The classes

**H-5. Class A only at launch; B and C disabled by parameter.** *Amends D-R-6 (the class bounds are
pinned).*
Classes B and C are made unreachable in the mainnet and testnet sets by giving them an empty term
range (`classMin[1] > classMax[1]`, `classMin[2] > classMax[2]`); MINT-3 (`state.cpp:303`) then
refuses every B/C term with the existing `mint-class-term` verdict and no new code path. The
`params` unit invariants that assume contiguous classes are relaxed to "contiguous or empty"; the
registry (`yb-calibration/src/ybcal/params/`) learns the empty-range convention and `ybcal params
check` accepts it. Wallets read `mintableClasses` and already hide what the node refuses.
*Why not a `classEnabled` mask:* that is a new field on a struct the golden vector hashes; an empty
range is a value, not a schema change. *Why not "B at ≤ 120 days at 700 %":* D-RD-COL-4's B
frontier is 700 % at 99 days rising to 3,000 % at 339 days, from a history whose effective sample is
6 one-year spans. A product line the data cannot certify is not shipped on a risk-averse plan.
*What is given up:* long-term YEC-backed dollar liquidity, until §8 item 1 produces a pre-maturity
rule the calibration can score. Class A (30–90 days) with renewal through the wallet (H-8) is the
launch product.

### 3.3 The valve

**H-6. The valve trips on a persisted lead, the note cap is raised, and the length is 12.** *Amends
L7 (`VALVE_BLOCKS` 6, pinned).* All node-local, `index.cpp`/`index.h`, both lines.
1. `VALVE_NOTE_CAP` 64 → **256** (`index.h:65`). D-RD-ACT-5: ≥ 256 keeps the cap-stuck share ≤ 5 %
   at 16–24 blocks for a 55 % stock majority. Memory: 256 notes × one header per rejected root,
   bounded as today.
2. **Persistence.** `NoteHeaderOnRejectedChain` records, per rejected root, the first tip height at
   which the noted work crossed `tip.nChainWork + valveBlocks × proof(tip)` (`index.cpp:621-623`).
   `TripValve` runs only when the lead is still at or above the bound after `VALVE_PERSIST` = 6
   further tips on the node's own chain, re-checked on every subsequent note and on every
   `CommitConnect`. A minority burst decays (the enforcers' chain catches up and the lead falls
   below the bound, the record clears); a majority's lead grows. The audit's A-6 cure lands in the
   same function (F-3).
3. `valveBlocks` 6 → **12** on mainnet and testnet (regtest stays 6 so the fifteen enforcement cases
   keep their timing). D-RD-ACT-5: least harm on the real block sequence; with the persistence rule
   the calibration's `valve.attack_trip` is re-measured (H-phase 4) and the plan expects it to fall
   below the 0.01-per-incident bound that L7 originally assumed.
*Why not consensus:* the valve is the enforcers' own safety release; stock nodes never see it.
*What is given up:* a genuine majority's reorg onto its chain takes ≈ 12 + 6 blocks instead of 6
(≈ 23 min); during that time enforcing nodes are on a minority branch they will abandon, exactly
as today for 6 blocks. Catch-up suppression (`NetworkAlreadyBuiltOn`, `index.cpp:554-561`) keeps
its 6-block margin: it is the IBD path, not the attack path.

### 3.4 Activation and the enforcement gaps

**H-7. Lock-in needs two consecutive windows above the threshold.** *Overlay rule, `state.cpp:1084`.*
SIGNALING → LOCKED_IN when the trailing count is ≥ `activationThreshold` at height H *and* at
H − `signalWindow`. D-RD-ACT-4 measured the hop coalition's spurious lock-in at ≈ 0.4–0.97 within
30 days under a single-window test; ACT-2 becomes a two-window test, which the same study can
re-score (H-phase 4). The L3 fractions (75/60/50/60 %) are unchanged. `signalWindow` 2,592 and its
fraction-pinned thresholds (1,944 / 1,556 / 1,296 / 1,556) as recommended.

**H-8. `START_HEIGHT` is published only after the enforcing coalition has committed.** *Procedural.*
The mainnet start height now in both lines (3,075,000) is **withdrawn** and re-set by the release
that passes §7. Before that release: written commitment from operators holding ≥ 70 % of blocks
over the preceding 60 days (the identified coalition is ninjaraider + mining-dutch + dapool at
71.9 %, D-RD-ACT-1), verified in `yed_getactivation` on a public observation node, and the
`chain-viz` coalition panel (§6 of its plan) showing the signalling share per payout key.
*What this does not fix:* the coalition is one operator plus two small ones. If ninjaraider leaves,
ENFORCEMENT halts within ≈ 33 h, abandonment follows after 30 days, and vaults past `claimHeight`
are exposed until owners sweep (B-6). That is stated in the trust statement (§6) in those words.

**H-9. Owner protection before `claimHeight` is the wallet's job, and sweeps are admitted at the
sunset.** *Tier 0 plus one overlay policy change.*
1. **Sunset stand-down** (audit A-5 recommendation): MP-1 (`index.cpp:769-812`) and TPL-1/2
   (`policy.cpp:68-145`) stop refusing non-burning *owner-path* spends once `height >
   enforceUntilHeight`, not only once `IsAbandoned()`. Node policy, not block validity. The ≈ 5-day
   exposure at a sunset without a successor becomes zero for an owner whose wallet acts.
2. **Wallet deadline enforcement** (yecwallet-dd, YEW): every ACTIVE vault shows its `lockHeight`
   and `claimHeight` as dates; from `lockHeight` the wallet offers *renew* (redeem and re-mint in
   one flow) and *redeem*; from `claimHeight − 1 day` it warns persistently; at
   `enforceUntilHeight − grace` it warns "redeem before sunset" (the A-5 residual, open since
   2026-10-02). An owner who follows the wallet is never exposed by A-5.
3. **Client plausibility** (audit G-1/G-2, open for YEW): the node gains optional
   `maxCollateralZat` on `yed_mint` and `maxBurnCents`/`minOutZat` on `yed_claim` (audit C/F-1);
   both wallets recompute the fee floor and the height identities locally. This is the audit's
   recommendation; it is in this plan because B-6's theft leg (a malicious server plus a stock
   miner) rides on the same gap.

### 3.5 Issuance

**H-10. The soft-cap gate admits class A only.** *Amends W20 (D-R-11); overlay rule,
`state.cpp:340`.*
MINT-6 above the cap: accepted iff `termClass == 0` **and** `MinRatioBps(base, σ) ≥
recapRatioBps`. With H-5 the clause is moot at launch; it is written now so that re-enabling a class
later does not silently re-open the cap. Mirrors at `txbuilder.cpp:921-923` and
`rpc/yellowback.cpp:821`.

**H-11. The global halt moves to 300 %; recap to 600 %.** *Amends W16's values, not its rule.*
`globalRatioHaltBps` 25,000 → **30,000** (meets the 1.6 % tolerance, D-RD-ORA-7); `recapRatioBps`
stays 2× the halt by W16, so 50,000 → **60,000**. The §1.4 invariant "halt < every class's base
ratio" holds because class C is off and class A's base is ≥ 72,500. The W20 gate at 600 % with H-10
admits only class A, whose locked ratio is ≥ 725 % at multiplier 1.0.

**H-12. Guarded issuance for the first parameter lifetime.** *Parameter.*
`maxMint` $10,000 → **$2,500**. D-RD-COL-6: at $2,500 a vault's liquidation at θ = 125 % is ≈ $3,125,
≈ 4.5 days of p10 volume and ≈ 20× the bid depth, which a holder-claimant absorbs and a seller does
not; at $10,000 nobody does. A per-vault cap does not bound the aggregate (owners split vaults;
D-RD-INF-4), so the aggregate stays bounded by `supplyCapBps` 1,500 and the class-A-only gate.
`supplyCapBps` does not move: D-RD-AUD-5 forbids moving it without an evidenced depth bound, and the
depth series is still short (C-10). Re-decided at the first renewal on the then-current book.

---

## 4. Defects to fix (both node lines, before any gate is read)

| # | Defect | Fix | Where | Test |
|---|---|---|---|---|
| F-1 | **F-DEV-1.** A mint's inputs, including the carrier's change, look unspent between the mint leaving the mempool and the wallet notifier stamping the block (`IsSpent` counts spenders at depth ≥ 0 only; a mined-but-unstamped wtx is at −1). The next `SelectYec` re-selects them; ATMP rejects the double spend; "transaction commit failed"; a depth −1 wtx is left behind. | `SelectYec` (`txbuilder.cpp:507-534`) skips any outpoint whose spender the wallet holds at depth −1 or the index has seen; `yed_mint`/`yed_send` `LockCoin` every selected YEC input and the carrier change until the spender is at wallet depth ≥ 1 (the guard that `CarrierConfirmed` already applies to the carrier's funding input, `rpc/yellowbackwallet.cpp:374-380`); a failed commit removes the orphan wtx. | ycash6, ycash-dd: `src/yellowback/txbuilder.cpp`, `src/rpc/yellowbackwallet.cpp`, `src/yellowback/wallet.cpp` | New case in `yellowback_attest_wallet.py`: 30 back-to-back mints and sends with `generate` between them, zero failures; `ybcal devnet validate` vault-cycle count unchanged |
| F-2 | Sample agent configs fail closed on 53 % of blocks (`min_sources = 3` with three venues, `max_age` 3600 on two thin venues). | `min_sources = 2`, `min_venues = 2` kept, in `contrib/yellowback/attest/attest.toml.sample` and `contrib/yellowback/pool/yellowback-quote.toml.sample`; the Rust default `MIN_SOURCES` (`price.rs:26`) and the Python quote tool's default follow; the `nonkyc-btc` cross route is enabled in the sample as a fourth source; README text says why. | ycash6, ycash-dd `contrib/yellowback/` | Fixture test replaying the reconstructed-spreads log: fail-closed rate ≤ 0.5 % of blocks (D-RD-ATT-2 measured 0.2–0.3 %) |
| F-3 | **A-6.** The valve odometer bounds a note's target against the previous note's, compounding to ≈ 3 blocks of discount. | Bound against the rejected root's `nBits` (not the previous note's); landed with H-6 in the same function. | `index.cpp:603` both lines | Unit `valve_ignores_lowdiff_headers` tightened; the Phase 8 DoS row re-run |
| F-4 | **A-5 residual.** No wallet warns "redeem before sunset"; YEW and YecWallet trust the server's heights and fee. | H-9 items 2 and 3. | yecwallet-dd, yew, both node lines (RPC args) | QTest and the YEW M1 integration test against a devnet with a near sunset |
| F-5 | Mainnet `START_HEIGHT` 3,075,000 and `ENFORCE_UNTIL_HEIGHT` 3,495,480 are set on both lines ahead of the gates. | Unset on `harden/yellowback`; re-set only by the release that passes §7 (H-8). | `params.cpp` both lines | `make status` pin check; the release workflow refuses to tag with the height unset |

---

## 5. Threat model rows (added to v3 §8.2 by this plan)

| Threat | Outcome | Mitigation | Residual |
|---|---|---|---|
| The majority pool sets the miner medians alone | cannot mint against an inflated price (H-1: `min` with the attested quantile); can depress `xMint` and over-collateralise everyone's mints; can withhold quotes and halt minting | H-1, H-2; gate G-3 measures quote availability before activation | griefing and NO_PRICE; both visible in `yed_getinfo` and chain-viz; neither moves collateral |
| The majority pool opens RED-4(b) on a noticed vault via `pEmerg = min` | forced close at `pClaim = max`, residual to the owner | accepted (grief, bounded) | an owner can be closed early at an honest price |
| The majority pool leaves, or signals without enforcing (never detected: D-RD-ACT-6) | enforcement on with a minority in fact, then the valve (H-6) or the ENFORCEMENT halt; abandonment after 30 days | H-8 commitments; the trust statement; H-9 wallets redeem before `claimHeight` | vaults past `claimHeight` whose owners do not act are anyone-can-spend during the gap |
| Free valve attack by a matured-vault owner | a stock burst must now hold a 12-block lead for 6 more tips | H-6 | a genuine stock majority still trips it, as designed |
| Spurious lock-in by a hop coalition | needs two consecutive windows | H-7, H-8 | an auto-switching pool that stays 2 × `signalWindow` still locks in |
| Attestor set captured by seat splitting (≈ $50k) | with H-1 the captured quantile can raise `pMint` only up to `xMint` (still `min`) | H-2 (7 seats), gate G-5, D-RD-ATT-4's renewal rule on `bondMin` | a captured set plus the majority pool together move the price; stated in §6 |
| Claimants cannot sell collateral | claims that do not pay are not made; vaults stay underwater | H-12, θ 125 %, class A only | YED depth is unknown; measured at renewal |

---

## 6. Trust statement delta (to be published with the release)

The product promises, in these words, and no more:

- **YED is created only when both a hashpower majority and a bonded attestor majority agree on the
  price** (H-1). Neither alone can mint against a price it sets.
- **Collateral is locked for 30 to 90 days and returned to the owner who redeems before
  `lockHeight + 30 days`.** An owner who does not act by then has agreed that anyone may close the
  vault by paying its debt.
- **The system is enforced by mining pools that choose to run it.** Today one pool mines about half
  of Ycash's blocks. If the pools that enforce stop, enforcement pauses within two days and the
  module declares itself abandoned after thirty; during a pause, vaults past their claim height are
  not protected by the network. Wallets show every vault's deadlines and warn before them.
- **A Yellowback vault is not a leveraged position and is never liquidated early.** It is a term
  deposit against which dollars are issued at more than seven times over-collateralisation.
- **Nothing in Yellowback changes Ycash consensus**, the shielded pool, or what a node that does not
  run the module validates.

---

## 7. Launch gates (go / no-go)

Every gate is a number read by a named tool on both node lines. The release manager records the
readings in `ycash6/doc/yellowback-release.md` under the tag. No gate may be waived; a gate that
cannot be read is red.

| Gate | Reads | Threshold | Tool |
|---|---|---|---|
| G-1 Data complete | live spread log ≥ 14 days; depth series ≥ 30 days; final standard re-run on the frozen snapshot | all three present; lock-readiness checklist all green | `ybcal recommend --budget standard`, `docs/reports/<run>/README.md` §7 |
| G-2 Parameter invariants | every §1.4 invariant incl. the empty-class convention; devnet differential at the final set | 8/8 scenarios PASS on ycash6 and ycash-dd, `--strict` | `ybcal params check`, `ybcal devnet validate --strict` |
| G-3 Quote availability | NO_PRICE hours over a 30-day pre-activation mainnet observation (pools quote from `START_HEIGHT`, before lock-in) | ≤ 24 h in the window (≈ 290 h/yr; the 6 h/yr policy budget is unreachable with three pools and is re-set at renewal with the then-observed fill) | `yed_getinfo` history on the observation node; chain-viz halt-mask panel |
| G-4 Coalition commitment | written commitments; signalling share per payout key over 60 days | ≥ 70 % of blocks from committed operators; two consecutive windows ≥ 75 % before lock-in (H-7) | `yed_getactivation`, chain-viz coalition panel |
| G-5 Attestor set | matured, distinct bonds; overlap disclosure | ≥ 7 ELIGIBLE seats from ≥ 7 operators with ≥ 3 distinct source sets, none sharing hosting; ARMED observed on testnet with the drills of v3 Phase A7 | `yed_listattestors`, the §7.5 disclosure page |
| G-6 Valve under attack | the H-6 valve on the real block sequence | `valve.attack_trip` ≤ 0.05 in 30 days; `valve.capstuck` ≤ 0.05 | `ybcal` G5 with the persistence model (H-phase 4) |
| G-7 Class A solvency | P(bad debt at claim opening) on both windows and the stress models | ≤ 0.5 % on full and last-365 standard runs; reported on regime/martingale | `ybcal` G3 |
| G-8 Defects closed | F-1…F-5; audit checklist | all closed on both lines; the audit's "fix both lines" rule has no open row | `qa/yellowback-audit.sh`, the audit checklist |
| G-9 Frozen files | zero delta against `yellowback-v3-baseline` (ycash-dd) and `ycash6-baseline`; hook budgets | 0 / within budget | CI `audit` job |
| G-10 Testnet | four weeks ARMED with real attestors, no state-hash divergence; every A7 drill plus the H-6 valve drill and the H-9 sunset drill | all recorded in `doc/yellowback-testnet-v3.md` | manual, per v3 A7 |

Testnet is currently unreachable (no seeds, 2026-10-02). G-10 therefore needs the Foundation to
stand up seeds, or the gate is read on a public multi-operator devnet with the real attestor agents
and at least three independent pool operators. Either is acceptable; "regtest on one laptop" is not.

---

## 8. Open items that remain the owner's (not blocking this plan)

1. **A pre-maturity rule for classes B and C.** The only lever that makes long terms viable
   (D-RD-COL-4 lever 2). Candidates for a later design note, none scheduled: periodic re-margining
   (a top-up output the owner can add to an ACTIVE vault; overlay rule), or a claim path above θ
   before `claimHeight` (a script change: a second CLTV at a shorter height, which is consensus-
   visible and therefore a larger change). Until one is scored by `ybcal`, B and C stay off.
2. **`supplyCapBps` and `maxMint` at renewal**, on the depth series G-1 completes.
3. **`bondMin`** should rise with adoption (D-RD-ATT-4 residual); the renewal set re-tunes it on
   observed attestor revenue and the then-current YEC price.
4. **The fill rule (L9) at 0.6 W** once attestation is mandatory and a year of fill data exists.
5. **A `classEnabled` field** if the empty-range convention proves awkward in tooling.

---

## 9. Work plan

Chunks are sized for the worktree pattern of the v3 plan (§6.0): one agent per chunk, both node
lines in one chunk where the change is shared, acceptance by command. Line counts are estimates
against `src/yellowback/` only; no budgeted hook file changes.

| Phase | Chunk | Repos | Content | Est. | Acceptance |
|---|---|---|---|---|---|
| **H0** docs | H0-a | workspace | this plan; `docs/plans/README.md` row; `docs/mapping.md` §21 rows (Appendix A); v3 plan §8.2 rows (§5 above); the trust statement (§6) into `docs/spec` via `make spec` | — | `make spec-check` |
| | H0-b | yb-calibration | policy `policy/harden-2026-10.toml`: class A only, `mint_requires_armed`, the two-window ACT-2, the H-6 valve model, `attest_arm_min` 7, fee split, the "worse window decides" lock rule for ratios; registry: empty-class convention, new fields | ~400 py | `ybcal params check`, `pytest` |
| **H1** defects | H1-a | ycash6, ycash-dd | F-1 (wallet spent-tracking), F-5 (heights unset) | ~120 | new wallet case green; `yellowback_attest_wallet.py` both modes |
| | H1-b | ycash6, ycash-dd | F-2 sample configs + agent defaults + fixture test | ~60 + toml | fixture test; `cargo test --locked` |
| | H1-c | ycash6, ycash-dd | F-3 odometer bound (lands inside H2-a if sequenced together) | ~20 | unit cases |
| **H2** valve | H2-a | ycash6, ycash-dd | H-6: `VALVE_NOTE_CAP` 256, persistence record, `VALVE_PERSIST`, `valveBlocks` param change, `yed_getinfo.valvePending` | ~150 | `yellowback_enforcement.py` cases 9/15 extended: a 6-block stock burst does not trip at `valveBlocks` 12; a 12-block lead held 6 tips does; a decaying lead clears |
| **H3** rules | H3-a | ycash6, ycash-dd | H-1 `mintRequiresArmed` (param, MINT-4 clause, verdict, RPC mirrors, MINTPOL) | ~120 | unit case per verdict; `yellowback_attest.py --armed` and unarmed both green; regtest default keeps every existing script green |
| | H3-b | ycash6, ycash-dd | H-7 two-window lock-in; H-10 class-A cap gate; H-11 values; H-9.1 sunset stand-down in MP-1/TPL | ~120 | `yellowback_activation.py` hop case; `yellowback_enforcement.py` sunset-sweep case; golden vector regenerated with the reason recorded |
| | H3-c | ycash6, ycash-dd | H-9.3 RPC bounds `maxCollateralZat`, `maxBurnCents`, `minOutZat`; contract JSON; `doc/yellowback-rpc.md`; `rpcversion` 4 | ~150 | `yellowback_rpc_contract.py`; `make spec-check` |
| **H4** calibration | H4-a | yb-calibration | re-run the four sweeps under H0-b's policy on the frozen snapshot plus G-1's completed data; `recommended.json` v2 of the report; devnet differential on both lines with the H1–H3 binaries | — | §7 G-1, G-2, G-6, G-7 |
| **H5** wallets | H5-a | yecwallet-dd | H-9.2 deadlines, renew flow, sunset warning; `mintRequiresArmed` and class-A-only messaging; the RPC bounds of H3-c | ~500 | QTest; the devnet role walk (minter) |
| | H5-b | yew | the same for YEW over lightwalletd; local fee/height recomputation (audit G-1/G-2) | ~600 Dart/Rust | M1 integration test against both devnets |
| | H5-c | lightwalletd-dd | pass-through of the new `yed_getinfo` fields and RPC args (allow-list only) | ~40 Go | byte-equality gate on the baseline service; proxy contract test |
| | H5-d | chain-viz | coalition panel per payout key; NO_PRICE-hours counter over a window; valve-pending state | ~300 TS | the devnet acceptance |
| **H6** operations | H6-a | ycash6 | release runbook: §7 gates as a checklist with the commands; the workflow refuses to tag while `START_HEIGHT` is unset or a gate reading is missing | — | dry-run of the tag workflow |
| | H6-b | workspace | commitments template for pool operators; attestor disclosure template | — | — |
| **H7** gates | — | all | read G-1…G-10; testnet or public devnet per §7 | — | the readings under the tag |
| **H8** release | — | ycash6 (release line), ycash-dd (in step) | 6.21.0 with `START_HEIGHT` set by the gate-passing release; renewal lead per W18 | — | G-9 green on both lines at the tag |

Budget check (ycash6 overlay today: 31 files, +11,570): H1–H3 add ≈ 750 lines to `src/yellowback/`
and `src/rpc/yellowback*.cpp`, and zero to any budgeted hook file. `make diff` on both lines is the
measurement; a chunk that touches a frozen file is rejected at review.

Sequencing: H0 and H1 are independent and start at once. H2 and H3 are independent of each other
and of H1 except F-3 ∈ H2-a. H4 needs H1–H3 binaries. H5 needs H3-c's contract. H6 needs H4's set.
H7 needs everything. Estimated calendar: H0–H3 two weeks in parallel worktrees; H4 one week (the
standard runs are ≈ 6 h each on 10 cores); H5 three weeks in parallel with H4; H7 is bounded below
by G-1 (2026-10-18) and G-10 (four weeks ARMED), so the earliest release is late November 2026 if
testnet is reachable in October.

---

## 10. Test plan additions

- `yellowback_enforcement.py`: valve persistence (three cases: burst below `valveBlocks`, lead held
  for `VALVE_PERSIST`, lead that decays), note cap at 256, sunset stand-down for owner sweeps.
- `yellowback_activation.py`: two-window lock-in; a one-window excursion does not lock in.
- `yellowback_attest.py`: `mintRequiresArmed` true → unarmed mint VOID with `mint-halted-unarmed`;
  armed mint unchanged; claim unarmed unchanged.
- `yellowback_attest_wallet.py`: 30 back-to-back mint/send pairs (F-1); the RPC bounds reject a
  server-inflated fee and height (H-9.3).
- Unit: params invariants with empty classes; W16/H-11 "halt < base ratio" over the active classes
  only; golden vector regenerated once, in its own commit, with the diff explained.
- `ybcal`: parity test of the simulator's new ACT-2 and valve models against the node (the
  differential suite, `--strict`); the G3 lock rule on two windows.
- The one-laptop devnet (`contrib/yellowback/devnet`) gains `--mint-requires-armed` and a
  `sunset` preset for the wallet drills.

---

## 11. What was given up, in one list

Recorded so the next revision can reconsider each with evidence rather than rediscover it.

1. Classes B and C (H-5): long-term dollar liquidity against YEC, until a pre-maturity rule exists.
2. Unarmed minting (H-1): the v2 "works on the miner price alone" mode on mainnet; the layer must
   form before the product opens.
3. Six-block valve (H-6): a genuine majority's reorg takes ≈ 23 min longer to be accepted.
4. The $10,000 vault (H-12) and the 25 bps pool fee (H-4).
5. The published start height (F-5): the release date is now a function of the gates.
6. The 6 h/yr NO_PRICE budget (G-3): replaced by an observed 30-day reading until adoption grows.

---

## Appendix A — rows for `docs/mapping.md` (new §21)

| Item | DigiByte / earlier plan mechanism | Ycash reality | Adaptation | Citation |
|---|---|---|---|---|
| Mint price source | v3: `pMint = xMint` until ARMED (D-4) | one pool sets every median (D-RD-ORA-4) | `mintRequiresArmed` halt bit in MINT-4 | `state.cpp:311-320`, `:332-334` |
| Term classes | three contiguous classes (D-R-6) | B/C bad debt 7×/17× tolerance (D-RD-COL-4) | empty term ranges for B/C; MINT-3 refuses | `state.cpp:303`, `params.cpp:44-53` |
| Work valve | trip on first header crossing 6 blocks of work (L7) | free sustained attack trips in hours (D-RD-ACT-5) | note cap 256, persisted lead, 12 blocks | `index.cpp:563-674`, `index.h:65` |
| Lock-in | one window ≥ 75 % (ACT-2) | hop coalition locks in spuriously (D-RD-ACT-4) | two consecutive windows | `state.cpp:1080-1090` |
| Soft cap gate | ratio ≥ `recapRatioBps` (W20) | admits B/C once σref rises (D-RD-COL-9) | class A only above the cap | `state.cpp:338-340` |
| Sunset | MP-1/TPL stand down only on abandonment | ≈ 5-day anyone-can-spend gap (audit A-5) | stand down on `enforceUntilHeight` for owner-path spends | `index.cpp:769-834`, `policy.cpp:115-116` |
| Wallet spent-tracking | `IsSpent` on depth ≥ 0 | mined-unstamped wtx at depth −1 (F-DEV-1) | lock inputs until spender depth ≥ 1 | `txbuilder.cpp:507-534`, `wallet.cpp:2531`, `:7812-7819` |
| Agent fail-closed | `min_sources = 3` | three venues, one often stale (D-RD-ATT-2) | `min_sources = 2`, fourth source enabled | `attest.toml.sample:35`, `price.rs:26` |
