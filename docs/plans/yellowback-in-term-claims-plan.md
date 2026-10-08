# Yellowback in-term claims — the claim path opens at the threshold, not at the term end

**Revision 1 (2026-10-07), a plan; implementation opened the same day.** A delta on the
[upgrade plan](yellowback-upgrade-plan.md) (revision 2, §5 and §15.10), on branch
`upgrade/vault-in-term` in `ycash-dd` and `ycash6` (cut from each line's `upgrade/vault`). Decided by the
owner on 2026-10-07 from the calibration studies on `calib/bad-debt-tolerance` in `yb-calibration`
(`docs/reports/2026-10-zec/README.md` §3, the ranked risk levers; the explainer
`docs/reports/2026-10-zec/in-term-claims.html`, pushed as `calib/in-term-explainer`). Items are **IT-\***
(rules), **D-IT-\*** (decisions) and phases **T0–T5**.

## Execution status (authoritative; update as work lands)

Legend: `[x]` done and verified on the integration tree, `[~]` in flight (agent / branch), `[ ]` not started.

| Item | ycash-dd | ycash6 |
|---|---|---|
| T0 plan, decisions, parameters settled (§2, §3) | [x] | [x] |
| T1 consensus: `appHeight` = mint height; RED-4 in-term clause; CLAIMING vaults in the halt ratio | [x] `it/core`, merged `0b5937725` (incl. D-IT-15 ownerHeight = refHeight + 1, IT-9 early fee `965e41ca3`) | [x] `it6/port`, merged `c689b1052` (vectors byte-identical) |
| T1 parameters: classes A/B/C re-enabled at 300/400/500 %; θ 125 %; σ multiplier pinned at 1; halt/recap/cap per §3 | [x] `it/core`, merged `0b5937725` (regtest halt kept at 25,000) | [x] `it6/port`, merged `c689b1052` (vectors byte-identical) |
| T1 Python model parity, golden vector regenerated once, SERIALISATION.md | [x] `it/core`, merged `0b5937725` (golden SCHEMA_VERSION 8, b848a699…) | [x] `it6/port`, merged `c689b1052` (vectors byte-identical) |
| T1 unit tests (`in_term_*`), `yellowback_interm.py` functional suite, CI lists | [x] `it/core`, merged `0b5937725` (10 `in_term_*` cases; 27 functional suites green; rpc_contract waits on T2) | [x] `it6/port`, merged `c689b1052` (vectors byte-identical) |
| T2 RPC + wallet: `yed_listclaimable` in-term, `yed_claim` in-term, `yed_getinfo` params, contract regenerated (`rpcversion` 6) | [x] `it/rpc`, merged `e0d1383fb`: rpcversion 6, `claimable` rows, `yed_estimateredeem`, in-term spec generator (`make spec-in-term`), walk and roles green, audit green but the pre-existing attribution leg | [x] `it6/rpc`, merged `8f28dbcff` (contract suite passes; walk and roles green) |
| T3 attest agent + devnet: liquidator persona claims in-term; `upgrade-walk` gains an in-term claim; roles regtest | [x] `it/devnet`, merged `bdfed3228`; walk's owner-redeem assertion follows D-IT-15 in T2 | [x] `it6/port`, merged `c689b1052` (vectors byte-identical) |
| T4 clients: YecWallet, YEW, lightwalletd, chain-viz (threshold warning, "claimable now", disclosure text) | [x] on `upgrade/vault-in-term`: lightwalletd-dd `3244976`, yecwallet-dd `c927763`, yew `99d9f05` (proto pin, client-side early fee, real early redeem + in-term claim on devnet), chain-viz `97d1cbd`; x402 and yolo need no change. Pending owner: the calibration sentence after the promise, the 25 % warning margin; YEW vectors to regenerate on an in-term devnet | — |
| T5 calibration: `ybcal` G3 models the in-term claim path; P(bad debt) at 300/400/500 % per class re-read | [x] `upgrade/vault-in-term` (yb-calibration) `e3ece4b`: 5 % met everywhere, 2 % on calm windows, 19–50 % claimed in term | — |
| T6 CI (owner, 2026-10-07; staged, starts when T1 lands): `yellowback_interm.py` in the push-tier lists and shard weights; audit rule-tag list gains the IT-* tags; contract gate at the new rpcversion with `inTermClaims`; cross-line vector identity (so ycash6's push waits for its port); release-heights guard; actionlint/zizmor clean; push `upgrade/vault-in-term` on both lines and read the runs green | [~] `ci/interm` (merge of upgrade/vault's CI fixes, pins to workspace e37a7b0, branch lists in every repo, IT tags, H-10 help text) | [~] |
| Both lines: `vault_vectors.json`, `yellowback_golden.json`, model byte-identical; all suites green; CI green | [ ] | [ ] |

### Log
- 2026-10-08: T1 done and merged into `upgrade/vault-in-term` with T3 (`bdfed3228`). Findings for the record: a
  claim through the threshold path (a) structurally pays the owner no residual (D-IT-17's wording holds); the
  emergency path (b) now needs an attestor-to-pool price gap above 19 % (was 4.8 %); the early-redeem fee goes wholly
  to the pool payee because AFEE-1 gives the owner path no attestor share (and is not due under FEE-0); pre-plan
  vaults stay spendable at the record level, MINT-3 refuses new pre-plan mints. The in-term promise cannot go into
  the upgrade plan §10 (it would change the `upgrade/vault` spec), so the in-term line gets its own spec generator
  (T2). T2 and the ycash6 port started.
- 2026-10-07: T5 done (`calib/in-term` e3ece4b): plan ratios meet 5 % everywhere, 2 % on calm windows; in-term cuts P(bad) 4–9× and loss given bad to 6–8 % of debt; 19–50 % of vaults claimed in term; cancel delay is the strongest cost lever. Owner confirmed halt 200 % / recap 500 %; delay 12 h recommended.
- 2026-10-07: revision 1; branches cut (ycash-dd `upgrade/vault-in-term` from `7eb414f00`, ycash6 from `158c7d1d1`); wave 1 dispatched: `it-core-dd` (T1), `it-calib` (T5), `it-devnet` (T3). T2, the ycash6 port and T4 follow T1.

## 1. What changes, in one paragraph

Today a YED vault can be claimed by a third party only after its term (`appHeight = lockHeight + GRACE`, pinned
in the vault script by `OP_CHECKLOCKTIMEVERIFY`), so a vault that falls under water on day 10 of a 90-day term
sits there growing a bad debt until day 90, when nobody will claim it. With this plan the APP branch is spendable
from the mint height and the module's RED-4 decides validity: **a claim is valid at any height at which the vault's
collateral is worth less than θ × debt at the attested claim price** (θ = 125 %), and invalid otherwise. Who may
claim: anyone, by burning the full debt in YED; the first valid claim wins. What they get is unchanged (RED-5):
collateral worth θ × debt at the claim price, capped; the residual returns to the owner. The owner's redeem is
unchanged and available throughout. Nobody is ever offered an underwater vault, which is why the claim happens:
the earliest valid claim pays the most (the 25 % margin), and the collateral only has to survive the cancel window
after θ instead of the whole term. The calibration measured the required ratio on YEC's own history falling from
3.75× to 1.5–1.75× at a 2 % tolerance (ZEC study §3.4), which is what lets the flat ratios of §3 be 300–500 %.

## 2. Decisions (owner, 2026-10-07)

| # | Decision | Value |
|---|---|---|
| D-IT-1 | In-term claims are part of Yellowback; the claim path opens when collateral < θ × debt | yes |
| D-IT-2 | Claim threshold θ | **125 %** (`claimThresholdBps` 12,500; today 11,000 on the upgrade line) |
| D-IT-3 | Who may claim once the threshold is met | **anyone** (no priority window); the attestor set keeps its cancel |
| D-IT-4 | Flat collateral ratios by term class ("greater uncertainty with a longer term") | A short **300 %**, B medium **400 %**, C long **500 %** |
| D-IT-5 | Volatility multiplier | **retired: pinned at 1** (`sigmaRefBps = 0` ⇒ multiplier fixed at 1, the registry's documented convention; the code path stays for a later update) |
| D-IT-6 | Global collateral ratio halt (HALT-2) | **kept** |
| D-IT-7 | Recapitalisation under a halt (MINT-4) and above the soft cap (MINT-6) | **kept; only the 500 % tier (class C) recapitalises** |
| D-IT-8 | Soft supply cap | **kept** |
| D-IT-9 | Term classes | A, B, C re-enabled (hardening H-5 reversed), with term bounds per §3 |

Decided after T3's findings (owner, 2026-10-07):

| # | Decision | Value |
|---|---|---|
| D-IT-15 | Owner redeem in term | **yes, absolutely**: the V template's `ownerHeight = refHeight + 1` (as `appHeight`); the owner pays the full debt and takes the collateral at any height. T3 found the owner path was still locked until `lockHeight`, so an in-term claim could close a vault its owner could not redeem |
| D-IT-16 | Early-redeem fee (so a term still means something, and to incentivise the longer term) | **Decided by the owner 2026-10-07: 5 % (class A, short), 2.5 % (class B, medium), 1 % (class C, long)** of the collateral when redeeming before `lockHeight` — `earlyRedeemFeeBps[class]` = 500 / 250 / 100 — paid through the existing FEE-1 / AFEE-1 split (miner of the block and the attestor set); no new payee or accrual mechanism. Note for the wallet warning: for class A the fee (15 % of the debt at a 300 % ratio) approaches the cost of being claimed (up to 25 % of the debt), so redeeming still beats being claimed but narrowly; wide for B and C. T5 re-reads the owner's decision point at these fees |
| D-IT-17 | Disclosure of the claim payout | mechanics unchanged; the promise says plainly that at the threshold the owner usually receives nothing back (T3: a clause-(a) claim has residual 0 because collateral is already below θ × debt) |

All earlier proposals decided by the owner on 2026-10-07 (D-IT-10 in revised form):

| # | Proposal | Value and reason |
|---|---|---|
| D-IT-10 | Term bounds | **A 30–90 d (unchanged), B 91–180 d, C 181–365 d** — owner (2026-10-07): the first proposal (7–30 / 31–60 / 61–90 d) was "too short"; the in-term rule lets the product extend upward instead, since the ratio covers the cancel window, not the term. Regtest: A 48–96, B 97–144, C 145–240 blocks (already so) |
| D-IT-11 | `globalRatioHaltBps` | **200 %** (today 300 %) — **confirmed by the owner 2026-10-07**. The halt sits below every class's base ratio (§1.4 invariant); classes start at 300 % |
| D-IT-12 | `recapRatioBps` | **500 %** (today 600 %) — **confirmed by the owner 2026-10-07**: the recap floor equals class C's base; A and B fail it by construction, C meets it exactly |
| D-IT-13 | Cancel delay (`claimDelay`) | **12 hours (576 blocks)** — coordinator's recommendation after T5 (24 h → 3.2 % bad debt on the worst year, 12 h → 2.1 %, 6 h → 1.2 %); the window is the attestors' time to cancel a wrong-price claim and the claimant's exposure, not the owner's protection (that is the threshold plus the wallet warning, and redeem during the window still saves the vault). Regtest 10 blocks. **Decided by the owner 2026-10-07: 12 hours.** |
| D-IT-14 | System ratio during a claim's cancel window | the vault is counted as it is: its debt left supply at the claim (burned), its collateral is still present until release — the accurate reading; the effect is a few vaults for hours against the whole system. **Decided by the owner 2026-10-07: as proposed.** |

## 3. The parameter set (mainnet / testnet; regtest in brackets)

| Parameter | Today (upgrade line) | This plan |
|---|---|---|
| `classMin/Max[0]` (A) | 34,560–103,680 (30–90 d) | 34,560–103,680 (30–90 d, unchanged) [48–96] |
| `classMin/Max[1]` (B) | disabled | 103,681–207,360 (91–180 d) [97–144] |
| `classMin/Max[2]` (C) | disabled | 207,361–420,480 (181–365 d) [145–240] |
| `baseRatioBps[0..2]` | 50,000 / 40,000 / 30,000 | **30,000 / 40,000 / 50,000** |
| `claimThresholdBps` | 11,000 | **12,500** |
| `sigmaRefBps` / `sigmaMultMaxBps` | 10,000 / 30,000 | **0 / 10,000** (multiplier 1) |
| `globalRatioHaltBps` | 30,000 | **20,000** (D-IT-11) |
| `recapRatioBps` | 60,000 | **50,000** (D-IT-12) |
| `supplyCapBps` | 1,500 | 1,500 (kept) |
| `claimDelay` | 1,152 | **576** (12 h; D-IT-13) [10] |
| `grace` | 34,560 | 34,560 (kept: still bounds the owner's post-term window and `claimHeight` fields) |
| `appHeight` (template) | `lockHeight + grace` | **`refHeight + 1`** (the mint's own height: the branch is open from the first block after the mint; RED-4 governs) |
| `ownerHeight` (template) | `lockHeight` | **`refHeight + 1`** (D-IT-15: the owner may redeem at any height) |
| `earlyRedeemFeeBps[0..2]` | — (new) | **500 / 250 / 100** (D-IT-16; charged on a REDEEM at height < `lockHeight`, on the collateral, via the FEE-1/AFEE-1 split) |

The hardening plan's §1.4 invariant "halt < every enabled class's base ratio" holds (200 % < 300 %); W16's
"recap = 2 × halt" is replaced by D-IT-12 (recap = class C's base) and recorded as given up.

## 4. Rules (the delta on the upgrade plan §15.10 / v3 RED and MINT rules)

- **IT-1 (template).** A MINT's V has `appHeight = refHeight + 1` and (D-IT-15) `ownerHeight = refHeight + 1`. `YedVaultScript(P, owner, lock, ref)` gains
  the ref argument; MINT-3's expected-script check uses it. Python `yed_vault_script` likewise. A V with
  `appHeight = lockHeight + GRACE` (pre-plan) is still a valid YED vault for spends (old vaults keep working);
  new mints with it are refused (`bad-mint-vault-script`).
- **IT-2 (RED-4 amended).** For a claim (selector 4) at height H on a vault minted at ref R with lock L:
  (a) if `H ≤ L + GRACE` (in term or in grace): valid iff `IsUnderwater(collateral, pClaim, debt, θ)`; the
  CLAIM_NOTICE / `pEmerg` path (b) stays as today and is also available in term;
  (c) if `H > L + GRACE`: as today (the post-term rule is unchanged; it is now the rare case).
  There is no "claim only after the term" clause left anywhere.
- **IT-3 (RED-5).** Unchanged: claimant intent ≤ `ClaimantMaxZat(debt, θ, pClaim)`, residual intent to the owner.
- **IT-4 (MINT-5).** `MinRatioBps(base, sigmaMult)` with `sigmaMult = 1` ⇒ required ratio = `baseRatioBps[class]`.
  The σ sampling code stays; `sigmaRefBps = 0` short-circuits it to 10,000 (the registry's convention).
- **IT-5 (MINT-4/6 recap gate).** Under HALT_GLOBAL_RATIO, and above the soft cap, a mint is accepted iff
  `baseRatioBps[class] ≥ recapRatioBps` — with §3 that is class C only. The `termClass != 0` clause of H-10 is
  replaced by the ratio test (it was a proxy for it).
- **IT-6 (HALT-2).** The system ratio counts ACTIVE and CLAIMING vaults' collateral against outstanding supply;
  a claimed vault's debt leaves supply at the claim block (burn), its collateral at release (D-IT-14).
- **IT-9 (early-redeem fee, D-IT-16).** A REDEEM at height < `lockHeight` pays `earlyRedeemFeeBps[class]` of the
  collateral in addition to FEE-1, routed exactly as FEE-1/AFEE-1 route the normal fee (the pool payee and the
  attestor-fee output); a REDEEM at or after `lockHeight` pays FEE-1 only. The fee is a RED rule (`bad-redeem-early-fee`
  when the outputs do not carry it); `yed_estimateredeem`/`yed_redeem` quote it; wallets show it beside the claimable
  price.
- **IT-7 (wallet/RPC).** `yed_listclaimable` returns in-term rows with `claimable: true/false` and the price at
  which the vault becomes claimable; `yed_claim` works in term; `yed_getinfo.params` carries the new values and
  `inTermClaims: true`; `rpcversion` 6.
- **IT-8 (disclosure).** The product promise (upgrade plan §10, replacing its collateral paragraph; owner 2026-10-07,
  "align the wording with the actual mechanics of the lock"): **"Your YEC is locked for the term you choose. You can
  redeem at any time by paying back the YED you minted; redeeming before the term ends also costs an early-redeem
  fee of 5 %, 2.5 % or 1 % of your collateral for a short, medium or long term. If your collateral falls below
  125 % of your debt at the
  attested price, anyone may close your vault by paying your debt; you then receive whatever collateral is worth
  more than 125 % of the debt — which, at the threshold, is usually nothing. Before that happens, your wallet will
  warn you, and redeeming stops it."** (D-IT-17; the early-redeem fee per D-IT-16.) Wallets
  show each vault's claimable price and warn as it approaches; the calibration's expectation that 19–50 % of vaults
  are claimed in term in a year like the last is stated in the disclosure, not hidden.

### 4.1 RPC contract delta (`rpcversion` 6)

The in-term line's RPC contract is the upgrade line's (upgrade plan §15.10: generated from the node's
`doc/yellowback-rpc.md`, its `### `yed_*`` headings and ```json blocks) with the deltas below, which are
IT-7 and IT-9 as a client sees them. `make spec-in-term` (`scripts/extract-spec.sh --write-in-term`) reads
this section the way it reads the node's document: each ```json block belongs to the `yed_*` command named in
backticks on the nearest non-blank line above it, and the heading's text after the name is that command's
arguments. A block is merged into the command's `returns` (objects key by key, a one-element row array into
its row, any other value replaced); a command new on this line (`yed_estimateredeem`) is given whole. The
generator refuses when the node's document lacks a field or command named here, gives a command other arguments
than a heading here states, or states another `rpcversion`, so this
section and the document cannot drift. The upgrade line's own contract (`make spec-upgrade`, `rpcversion` 5)
is untouched by it. Removed fields: none. Changed meanings: `yed_listclaimable` lists every ACTIVE vault whose
claim branch is open (in term too), `claimable: false` for one above θ, whose `underwaterAt` is the price at
which it becomes claimable (the shape change behind the bump); `vault-locked` and `claim-not-yet` no longer
refuse an in-term redeem or claim of a vault minted under IT-1.

#### `yed_getinfo`

```json
{
  "rpcversion": 6,
  "params": {
    "classes": [ { "earlyRedeemFeeBps": 500 } ],
    "earlyRedeemFeeBps": [ 500, 250, 100 ],
    "claimThresholdBps": 12500,
    "sigmaMultMaxBps": 10000,
    "inTermClaims": true
  }
}
```

#### `yed_listclaimable`

```json
[ { "claimable": true, "lockHeight": 377 } ]
```

#### `yed_redeem`

```json
{ "earlyRedeemFeeZat": 12594458450 }
```

#### `yed_claim`

```json
{ "earlyRedeemFeeZat": 0 }
```

#### `yed_listpositions`

```json
[ { "earlyRedeemFeeZat": 0 } ]
```

#### `yed_estimateredeem <vaultTxid>`

```json
{
  "vault": "6a1f2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8:0",
  "status": "ACTIVE",
  "termClass": "A",
  "lockHeight": 377,
  "height": 360,
  "early": true,
  "burnedCents": 100000,
  "collateralZat": 251889169000,
  "feeZat": 13224181372,
  "earlyRedeemFeeBps": 500,
  "earlyRedeemFeeZat": 12594458450,
  "payee": "smQvTmAz2ExamplePayoutAddress1111111",
  "canRedeem": true,
  "error": ""
}
```

## 5. Four-part check and tier

> DigiByte liquidates DigiDollar vaults when collateral falls under the threshold at any time
> (`ref/digibyte/src/digidollar/`, the liquidation path), using its own oracle inside consensus. Ycash's
> delivered design opened the claim only after the term because, under miner enforcement, an any-time claim
> was anyone-can-spend at the base layer (v2 §3.4). On `upgrade/vault` every rule is consensus and the claim is
> a primitive intent with an attestor cancel, so the restriction no longer buys safety; the adaptation is to open
> the template's APP branch at the mint height and let RED-4's existing threshold test govern at every height.
> Tier: a YED-module consensus change on the upgrade line (RED-4, MINT-3's expected script, parameters), under the
> consensus review gate; the vault primitive, the attestor set and the cancel mechanism are unchanged.

## 6. What is given up / risks

1. The product promise "locked for the term" becomes "locked for the term unless it falls below 125 %"; disclosed (IT-8).
2. The attestor set's cancel power is also, in term, a 24-hour window in which the price keeps falling; D-IT-13 keeps it at one day and T5 re-reads the bad-debt probability with it.
3. Claimants need YED in reserve and depth to sell the YEC they receive; the 25 % margin is also their slippage budget. T5 cannot model claimant supply; the devnet liquidator persona demonstrates the mechanics only.
4. W16's recap = 2 × halt rule is replaced (D-IT-12); H-10's class-A-only cap gate is replaced by the ratio test (IT-5); H-5 (classes B/C off) is reversed (D-IT-9).

## 7. Branches in every repo (owner, 2026-10-07)

Any repository that changes for in-term claims carries that work on **`upgrade/vault-in-term`, cut from its own
`upgrade/vault`** — the same branch name as the node lines, so the whole feature is one branch name across the
workspace: ycash-dd and ycash6 (cut), then as each is touched: lightwalletd-dd, yecwallet-dd, yew, chain-viz,
x402-ycash, yolo, and yb-calibration (whose in-term calibration moves from `calib/in-term` onto
`upgrade/vault-in-term` cut from its `harden/yellowback`, since yb-calibration has no `upgrade/vault`). A repo that
needs no change gets no branch. Agents branch `it/<name>` off `upgrade/vault-in-term` in each repo.

## 8. Sequencing

T1 (consensus + parameters + model + tests) on ycash-dd first, then ported to ycash6 with the vectors byte-identical;
T2 and T3 in parallel once T1 is on the integration tree; T4 after T2's contract; T5 in parallel from T0 (ybcal
only needs the rule text). Both lines merge into their `upgrade/vault-in-term`; pushing them and merging into
`upgrade/vault` is the owner's call after the review gate.
