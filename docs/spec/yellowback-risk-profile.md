# Ycash Yellowback (YED): the collateral model as implemented, and how its risk profile differs from DigiDollar's

**Read this before `yellowback-spec.md` in this directory.** That file is the generated spec of the
**v3 / `harden/yellowback` fallback line**, and its term-class table (A 500 %, B 400 %, C 300 %,
terms to five years) is **not what the `upgrade/vault` node enforces**. The current line's spec is
generated into the node trees (`ycash-dd/doc/yellowback-spec.md`, `ycash6/doc/yellowback-spec.md`,
`make spec-in-term`); this page is the plain-language companion to it, with every number taken from
the node source on `upgrade/vault` and cited to the line. When the two disagree, the code is right
and this page is stale: fix it.

Yellowback started from DigiByte's DigiDollar ([acknowledgements](../innovation-acknowledgements.md)).
Between 2026-10-04 and 2026-10-07 the Ycash lead Yellowback architect reviewed the risk profile of the
collateral model Yellowback had inherited from DigiDollar (hold-to-term vaults, a ratio falling with the
term) against YEC's own price history (the `yb-calibration` studies the hardening plan and the in-term
plan cite) and **changed that model in four places to make Yellowback more resilient than its
reference**. This page records what changed, why, and what it costs; the side-by-side with
DigiDollar's published design is this page's own.

## 1. What the node enforces today

Mainnet and testnet parameters, identical on both node lines (`ycash-dd/src/yellowback/params.cpp`
and `ycash6/src/yellowback/params.cpp`, `MainParams`; the line numbers are the same in both):

| Class | Term (blocks at 75 s) | Base collateral ratio | Early-redeem fee (owner redeem before `lockHeight`) | Where |
|---|---|---|---|---|
| A, short | 30–90 days (34,560–103,680) | **300 %** | 5 % of the debt | `params.cpp:59`, `:63` |
| B, medium | above 90 days to 180 days (103,681–207,360) | **400 %** | 2.5 % of the debt | `params.cpp:60`, `:63` |
| C, long | above 180 days to 365 days (207,361–420,480) | **500 %** | 1 % of the debt | `params.cpp:61`, `:63` |

Around the classes:

| Parameter | Value | Meaning | Where |
|---|---|---|---|
| Volatility multiplier | pinned at **1** (`sigmaRefBps = 0`) | the required ratio is exactly the class base; the sampling code stays for a later update (D-IT-5) | `params.cpp:68`, `math.h:80-82` |
| Claim threshold θ | **125 %** (`claimThresholdBps = 12500`) | a vault whose collateral is worth less than 125 % of its debt at the attested claim price may be claimed by anyone | `params.cpp:51` |
| Claim cancel delay | **12 hours** (576 blocks) | the attestor set's window to cancel a claim made against a wrong price | `params.cpp:50` |
| Global ratio halt | **200 %** | below this system-wide ratio only class C mints are accepted (the recapitalising tier); the ratio is the ACTIVE and CLAIMING vaults' collateral against their open debt, not against the YED in circulation (HALT-2 amended 2026-10-28, upgrade plan §15.10) | `params.cpp:53`, `:54` |
| Supply cap | **15 %** of market cap at the attested price; one vault at most the larger of 10 % of the cap and $10,000 (MINT-6b) | `params.cpp:19`, `:20`, `:52` |
| Mint size | $100 to $100,000 | `params.cpp:18`, `:22` |
| Grace after the term | 30 days; since IT-2 it gates no claim, it only sets the record's `claimHeight` and the mint's locktime bound | `params.cpp:48` |

The rules that use them, in `src/yellowback/state.cpp` (both lines, same line numbers):

- **Required collateral at mint** = `cents × MinRatioBps(baseRatioBps[class], sigmaMult) / pMint`
  with `sigmaMult = 1`, so the class base is the whole requirement (`state.cpp:389`, MINT-5).
- **A claim is valid at any height** at which the vault is under water at θ: in term, in grace
  and after it, the same test decides; there is no "after the term" clause left
  (`state.cpp:668-688`, IT-2 / RED-4).
- **The owner may redeem at any height**: the vault script's owner branch opens at the block
  after the mint's reference height, not at `lockHeight` (`state.cpp:325`, IT-1 / D-IT-15).
- **An early redeem pays `earlyRedeemFeeBps[class]` of the debt** at the vault's mint price, on top
  of the protocol fee, into the same pool-payee output and with no attestor share
  (`state.cpp:652-655`, IT-9'; `math.h:227`).

Under a global-ratio halt, or above the supply cap, a mint is accepted only if its class base is at
least the recapitalisation ratio (500 %), which by construction is class C alone
(`state.cpp:379`, `:414`, IT-5).

## 2. What DigiDollar does, for comparison

From the upstream documents copied under `upstream-digibyte/` at DigiByte v9.26.5 (the repo map's
`DigiDollar::ConsensusParams`, `REPO_MAP_DIGIDOLLAR.md`; the explainer's collateral table):

- **Ten canonical tiers whose ratio falls with the term:** 1,000 % at one hour, 500 % at 30 days,
  400 % at 90 days, 350 % at 180 days, 300 % at one year, 275 % at two, 250 % at three, 225 % at
  five, 212 % at seven, **200 % at ten years**. The explainer states the principle: "shorter locks
  requiring more collateral".
- **No liquidation before the timelock.** Both redemption paths, the normal one and the
  Emergency Redemption Ratio (ERR) path, begin with `OP_CHECKLOCKTIMEVERIFY` at the lock height
  (`src/digidollar/scripts.cpp`: `CreateNormalPath` and `CreateERRPath`, and the comment at lines 85-86,
  "both require timelock expiry"). The upstream design note says it plainly: "we cannot
  force liquidations … positions must ride out the full term regardless of collateralization"
  (`4_tier_collateral.md`).
- **The response to stress is on future mints and on late redeemers:** Dynamic Collateral
  Adjustment raises the ratio for new mints by 25–100 % as system health falls through 150 %,
  120 % and 110 %; below 100 % system health the ERR path makes a redeemer burn more DigiDollar to
  recover full collateral.
- **No supply cap** in the published design (`REPO_MAP_DIGIDOLLAR.md:27`).

## 3. The assessment, and the four changes it produced

The question the Ycash lead Yellowback architect put to the calibration was: on YEC's price history, what collateral ratio
keeps the probability of bad debt (a vault worth less than its debt at the moment it can finally be
closed) within a tolerance a chain of Ycash's market capitalisation can live with?

**Finding 1: a hold-to-term design needs ratios no product can carry.** With claims only after the
term, the hardening calibration (2026-10-04 to 07) put class A's required base at 725 % at the
0.5 % bad-debt tolerance it was run at, and at 1,925 % under the worse-window rule; for the longer
classes it found ratios the data cannot certify and no product can carry: the B frontier ran from
700 % at 99 days to 3,000 % at 339 days, C needed 3,000 % at 410 days and above 10,000 % past about
1.6 years (hardening plan D-RD-COL-4, H-5). The Ycash lead Yellowback architect called 1,925 % unacceptable. The hardening answer was to ship class A
only (H-5). DigiDollar, with the same hold-to-term structure, a longer maximum term and a lower
ratio at that term, carries the risk this finding describes at its largest.

**Finding 2: the exposure that matters is the cancel window, not the term.** Once a vault can be
claimed the moment it is under water at θ, the collateral only has to survive the 12-hour cancel
window after the threshold, not the whole term. The in-term plan records the required ratio falling
from 3.75× to 1.5–1.75× at a 2 % tolerance (its §1, citing the calibration's ZEC study §3.4, ZEC
being the proxy series the calibration uses beside YEC's own history), and the T5 re-read of the
in-term model found the probability of bad debt cut 4–9× and the loss given bad debt cut to 6–8 % of
the debt (in-term plan execution status and log, 2026-10-07). That is what makes flat 300–500 %
ratios sound.

From these, the Ycash lead Yellowback architect decided (2026-10-07, in-term plan §2):

| # | Change versus DigiDollar | Decision | Why |
|---|---|---|---|
| 1 | **Liquidation at any height.** Anyone may claim an under-water vault (θ = 125 %) in term, in grace or after; the attestor set can cancel a wrong-price claim within 12 hours; the owner keeps whatever is worth more than θ × debt | D-IT-1, D-IT-2, D-IT-3, D-IT-13 | finding 2: the dominant risk lever. DigiDollar cannot do this at all |
| 2 | **More collateral for a longer term, not less.** A 300 %, B 400 %, C 500 % ("greater uncertainty with a longer term"); the inherited 500/400/300 schedule is reversed | D-IT-4 | a longer term is a longer time for the attested price and the market to drift; DigiDollar's discount for long locks puts its thinnest buffer on its longest exposure |
| 3 | **Shorter terms.** 30 days to one year in three classes, against DigiDollar's 30 days to ten years | D-IT-10 | Ycash does not lock collateral against a price nobody can forecast years ahead; the in-term rule lets the product extend later |
| 4 | **The owner can always get out.** Redeem at any height, paying an early-redeem fee of 5 % / 2.5 % / 1 % of the debt for the short / medium / long class | D-IT-15, D-IT-16 | a wallet warning plus a redeem beats being claimed; the fee is cheapest for the best-collateralised class to make the longer term attractive |

Kept from the earlier Yellowback designs and absent from DigiDollar: the **supply cap** (15 % of
market cap, v2, kept by D-IT-8), the **global-ratio halt** (v2 HALT-2, lowered to 200 % and recapitalised
by the 500 % tier only, D-IT-6, D-IT-7, D-IT-11, D-IT-12; measured against open vault debt since 2026-10-28, as
DigiByte v9.26.6 measures its system health), and minting that **requires an armed price
attestation** (`mintRequiresArmed`, hardening H-1).

## 4. Why this is the safer model, in one paragraph

DigiDollar pairs its thinnest buffer (200 %) with its longest unliquidatable exposure (ten years):
a ten-year position is under water after a 50 % drop and then sits there, unclosable, for up to a
decade, while the protocol's only tools act on future mints and on the people who redeem last.
Yellowback pairs its thickest buffer (500 %) with its longest term (one year), closes any vault
within hours of crossing 125 %, and lets the owner leave at any time. A long term in Yellowback is
not a long exposure; in DigiDollar it is the whole exposure.

## 5. What was given up, and the residual risk

- **Gap risk.** A crash that carries a vault from 125 % to below 100 % faster than a claim lands,
  or during the 12-hour cancel window, is a bad debt. The calibration's reading of the plan ratios is that a 5 % tolerance is met
  everywhere and 2 % on calm windows; the cancel delay is the strongest lever (24 h gave 3.2 % on
  the worst year, 12 h 2.1 %, 6 h 1.2 %; D-IT-13).
  This risk does not grow with the term, which is why the term premium is three flat tiers rather
  than a steep curve.
- **The volatility multiplier is off** (pinned at 1). The requirement does not rise when measured
  volatility rises; the sampling code is kept so that lever can return without a schema change.
- **Owners near the threshold usually receive nothing back** from a claim; the promise says so
  (IT-8), and the wallet warns before it happens.
- **The long tiers' liquidity** is bounded at one year; DigiDollar offers ten.

## 6. For anyone new to Yellowback

1. Numbers come from `src/yellowback/params.cpp` on `upgrade/vault`, never from a spec copy whose
   header names the v2 or v3 plan.
2. The current line's spec is the node tree's `doc/yellowback-spec.md`; its first line names the
   upgrade plan and the in-term plan.
3. The upstream DigiDollar documents under `upstream-digibyte/` describe DigiByte's design, not
   Yellowback's. Where they describe collateral, Yellowback does the opposite on purpose.
