# Yellowback (YED): A Miner-Enforced Decentralized Dollar on Ycash

**Proposal draft v0.2 — September 10, 2026**

---

## 1. Summary

Yellowback is a decentralized, over-collateralized US-dollar note native to Ycash. Users lock YEC in a time-locked vault and mint Yellowback dollars (YED) against it. The design follows the DigiByte DigiDollar model — self-custodied collateral, no margin calls, no liquidation engine during the lock — with one structural difference: Yellowback is deployed as an **overlay protocol enforced by Ycash mining pools**, not as a hard fork.

Mining pools that run the Yellowback module (a patched `ycashd`) do three things: publish a YEC/USD price quote in each coinbase, refuse to include rule-breaking Yellowback transactions in their templates, and — once activation triggers — reject blocks from other miners that contain rule-breaking transactions. Mint and burn transactions pay a dedicated fee to a registered Yellowback miner, so running the module is directly profitable.

The result is a system where:

- The minter alone holds the key to their collateral.
- Price and rule enforcement both come from proof-of-work, with no oracle committee, no multisig, and no custodian.
- If YEC crashes far enough that minters abandon their vaults rather than redeem, YED holders can take the abandoned collateral themselves by burning YED (the claim rule, §5.5). They absorb a bounded loss instead of holding a worthless note.
- No user, exchange, or wallet needs to upgrade a node. GPU mining software (ccminer, gminer, miniZ, lolMiner) is unchanged.

**Terminology.** The only price in this protocol is the **YEC/USD reference price**: a rolling median of quotes that mining pools publish in their coinbase. It is used to size collateral at mint, compute the global ratio, and determine when a vault is underwater. YED has no protocol price; it is defined as one US dollar for accounting purposes. Whatever YED trades for on exchanges is outside the protocol.

---

## 2. Motivation

### 2.1 Why an overlay needs an enforcer

A DigiDollar-style vault has two consensus requirements:

1. A vault output cannot be spent unless the same transaction burns the matching debt.
2. Mints must satisfy a collateral ratio computed against a trustworthy price.

Ycash script can express a time lock and a key check, but it cannot verify a burn or read a price. Without an enforcer, a minter could sell YED, wait out the lock, and reclaim the collateral — keeping both. This hole exists in the *normal* case, not only in a crash.

Every non-fork remedy considered (oracle committees, threshold signers, DLC settlement, redemption pools, Starknet-governed signers) substitutes some group holding keys for the missing rule. Each reintroduces a trusted party.

### 2.2 Why miners

Miners are the one party on a proof-of-work chain that can *reject a transaction* without a consensus change. A majority of hashpower that refuses to include invalid Yellowback transactions — and refuses to build on blocks that contain them — enforces the rule for the whole network. This is a soft fork carried by mining software, the same category as P2SH and SegWit on Bitcoin, but deployed at the pool layer rather than requiring a node release.

The same miners are also the natural price source. A per-block quote in the coinbase, aggregated as a long rolling median, yields a price feed whose manipulation cost is sustained majority hashpower — the chain's existing security assumption.

### 2.3 Design principles

- **Self-custody.** The minter's key is the only key on the vault.
- **No committees.** No set of named parties ever holds or can move user or system funds.
- **Forkless launch, upgrade path later.** Rules live in mining software; they can be promoted to a Ycash network upgrade once proven.
- **Prefer hard-to-move prices over fast prices.** The YEC/USD reference price is a 12-hour median by design.
- **Degrade to safe.** Loss of miner participation pauses minting; it never unbacks existing YED.

---

## 3. Architecture

### 3.1 Components

| Component | Who runs it | Change required |
|---|---|---|
| GPU hashing software | Individual miners | None |
| Pool stratum layer | Pool operators | None, or consume filtered template (see 3.3) |
| `ycashd` + Yellowback module | Pool operators, solo miners | Patched node |
| Yellowback wallet / indexer | Users, exchanges, wallets | New overlay client (no node change) |
| Stock `ycashd` | Everyone else | None |

### 3.2 The Yellowback module

A patch to `ycashd` adding one module with four responsibilities:

1. **Overlay indexer.** Parses Yellowback records (vault creation, mint, burn, transfer, claim) from transparent OP_RETURN outputs and Sapling memos. Maintains the YED ledger, the vault set, per-vault debt, global collateral ratio, and the rolling price median.
2. **Template filter.** Excludes any transaction that violates the rules in §5 from the pool's block template.
3. **Coinbase tag.** Inserts the Yellowback tag (§4.3) into the coinbase scriptSig.
4. **Block validation hook.** After activation (§7), treats any block containing a rule-violating Yellowback transaction as invalid and does not build on it.

The module also exposes RPCs (`getyecusdprice`, `getyedstate`, `getvault`, `validateyellowbacktx`) for wallets and services.

### 3.3 Pool integration

Most pools run `ycashd` and take templates via `getblocktemplate`; for those, the patch is a drop-in replacement. Pools that assemble templates in a separate stratum layer either consume the filtered template from the patched node or embed the filter library in the stratum layer. Either way the change is on the operator's server and invisible to hashers.

Fees earned by the pool (§6) flow to hashers through the pool's existing payout scheme.

---

## 4. Price feed

### 4.1 Per-block quote

Each registered miner publishes a YEC/USD quote in the coinbase tag. The quote is computed by the module as a **15-minute volume-weighted average** across the operator's configured sources.

- Sources are operator-configured. The module ships with defaults covering the venues where YEC trades plus an aggregator as a cross-check, but operators may add, remove, or weight sources. Source diversity across pools is a security property.
- Sources deviating more than a configurable threshold from the others are dropped for that computation.
- If all sources fail, the module reuses the last good quote for up to 30 minutes, then omits the tag. A miner without a tag is not registered (§6.2) and earns no Yellowback fees.

### 4.2 Reference prices

Three rolling medians are computed from the per-block quotes, considering only blocks that carry a valid tag:

| Name | Window | Approximate span |
|---|---|---|
| `P_fast` | 96 blocks | 2 hours |
| `P_mid` | 576 blocks | 12 hours |
| `P_slow` | 2,016 blocks | 42 hours |

Two derived prices are used by the rules:

- **Mint price** `P_mint = min(P_fast, P_mid, P_slow)`. Used for collateral ratios at mint, the supply cap, and the global ratio.
- **Claim price** `P_claim = max(P_mid, P_slow)`. Used only to determine whether a vault is underwater for the purposes of §5.5.

This min/max structure is a direction-aware selector without an explicit trend classifier. When YEC is rising, `P_slow` is lowest, so minters are held to the old, proven price. When YEC is falling, `P_fast` is lowest, so minters are marked to the crash within about two hours. Claims use the opposite bias: a falling market must persist across the slow window before any vault becomes claimable. No threshold defines "rising" or "falling"; a small push on any window produces a proportionally small effect and never flips a rule.

`P_fast` is deliberately excluded from `P_claim`. A short window can be nudged by one large pool for a couple of hours; including it in a maximum could only make claims *harder*, but there is no benefit to that, and excluding it keeps the claim path dependent on sustained prices only.

Consequences:

- A single block's quote, and any lag between template creation and block solve, is immaterial.
- Moving any median requires sustained hashpower over that window. A miner with 30% of blocks can shift a median only to roughly the 30th percentile of honest quotes.
- A genuine sustained rise reaches `P_mint` with about a 42-hour lag; a genuine crash reaches it within about 2 hours. This asymmetry is intentional.

Wallets display `P_mid` as the headline YEC/USD reference price and use `P_mint` for ratio calculations at mint time.

### 4.3 Coinbase tag format

Encoded in the coinbase scriptSig after the BIP34 height push. All integers little-endian.

| Field | Size | Description |
|---|---|---|
| magic | 4 bytes | `0x59454421` ("YED!") |
| version | 1 byte | Tag format version |
| flags | 1 byte | bit 0: activation signal; bits 1–7 reserved |
| price_uusd | 8 bytes | YEC/USD in integer micro-dollars |
| source_mask | 2 bytes | Bitfield of price sources used (registry in Appendix A) |
| payout_key | 20 bytes | Hash160 of the miner's fee payout key |

Total: 36 bytes. No floats anywhere in the protocol; all ratio math is integer arithmetic on `price_uusd`.

### 4.4 Why pools publish honest quotes

A pool's quote is not used directly; only the median across 576 blocks is. This shapes the incentives:

**A minority pool cannot move the price meaningfully.** Honest quotes drawn from the same few exchanges cluster within a few percent of each other. A pool with `x%` of blocks can shift the median only to roughly the `x`-th percentile of that cluster. A 30% pool publishing quotes 50% too high moves the reference price by whatever the spread between the 50th and 70th percentile of honest quotes is — typically 1–3%. The lie is almost entirely discarded.

**Lying forfeits income.** Deviation is measured against the **peer median**: the median of quotes in the 20 blocks surrounding the miner's block. During a genuine fast move all honest quotes move together, so measuring against peers rather than against the lagging reference price does not penalize pools for being correct. A registered miner loses registration for `N_penalty` blocks (initial: 288) if its quote deviates more than 10% from the peer median, or if it publishes a stale or missing quote. Deregistered miners earn no Yellowback fees.

**Accuracy is rewarded.** Fee payee selection (§6.1) is weighted by an accuracy score: each registered miner's weight is the fraction of its last 576 quotes that fell within 3% of the peer median at the time. A pool that consistently tracks the market earns a larger share of fees than one that drifts. This makes careful source configuration directly profitable.

**Every quote is attributable.** Quotes are tied to a payout key in the coinbase and are permanent on-chain records. A pool caught skewing the feed is exposed to its own hashers and to the community.

**The rules are asymmetric where manipulation direction matters.**

- *Upward* manipulation lets a minter mint more YED per YEC. Mints use `P_mint`, the minimum of three windows, so a pump must be sustained for about 42 hours before it affects minting, and the divergence halt (§5.6) pauses minting long before that.
- *Downward* manipulation could make healthy vaults appear underwater and expose them to claims. Claims use `P_claim`, the maximum of the two slower windows, and require the vault to be past its lock height plus a 30-day grace period, so a manipulation would have to be sustained for weeks.
- Pushing `P_fast` down only lowers `P_mint`, which makes minting *more* conservative. This is griefing with no payoff to the attacker.

**Damage is capped regardless.** The divergence halt (§5.6) pauses minting whenever the fast and mid windows disagree by more than 20%, so even a successful pump cannot be minted against quickly. The supply cap and global ratio halt bound total exposure.

**Majority manipulation is not a new risk.** A pool or cartel with sustained majority hashpower could move the median. That same majority could already reorganize the Ycash chain. Yellowback adds no trust assumption the chain does not already carry.

Compared with DigiDollar's fixed roster of oracle operators, whose honesty rests on reputation alone, Yellowback quotes are hashpower-weighted, fee-penalized, accuracy-rewarded, and publicly attributable.

---

## 5. Protocol rules

All rules below are enforced by registered miners at the template and block-validation layers. Wallets and overlay clients validate identically; a transaction rejected by the rules is treated by overlay clients as never having happened.

### 5.1 Vault

A vault is a transparent P2SH output with redeem script:

```
<lock_height> OP_CHECKLOCKTIMEVERIFY OP_DROP <minter_pubkey> OP_CHECKSIG
```

The creating transaction includes an OP_RETURN record:

```
YB | 0x01 (VAULT) | lock_height | term_class | reserved
```

`term_class` selects the collateral ratio schedule (§5.2). The vault UTXO is identified by outpoint. Vault outputs are recognizable by script template, which is what allows spends to be policed.

### 5.2 Mint

A mint records debt against a vault:

```
YB | 0x02 (MINT) | vault_outpoint | yed_amount | fee_output_index
```

Validity requires:

- The vault is unspent and has no existing debt, or the new total debt keeps the vault above the minimum ratio.
- `collateral_yec × P_mint / yed_amount ≥ min_ratio(term_class, σ)`.
- Global conditions (§5.6) are not in a halted state.
- The fee output (§6.1) is present and correct.

**Volatility-indexed ratio.** The minimum ratio is a base ratio per term class scaled by realized volatility, so the collateral buffer grows automatically in turbulent markets:

```
σ          = standard deviation of block-to-block log changes in the per-block
             quotes over the last 2,016 blocks, annualized
min_ratio  = base_ratio(term_class) × max(1, σ / σ_ref)
```

with `σ_ref` initially set to 100% annualized. In a calm market the multiplier is 1; in a market twice as volatile as reference, every ratio doubles. The function is continuous, so there is no regime boundary to straddle.

Base ratios:

| Term class | Lock length | Base ratio |
|---|---|---|
| A | 30–90 days | 500% |
| B | 91–365 days | 400% |
| C | > 365 days | 300% |

Shorter locks require more collateral because a shorter lock gives the minter an earlier free option on price. Base ratios and `σ_ref` may be raised by governance; they are never applied retroactively to existing vaults.

**Design note.** The protocol never classifies the market as rising or falling. Direction is handled implicitly by the min/max price selectors (§4.2), and magnitude by the volatility multiplier here. Both are continuous. A discrete trend flag was considered and rejected: it would require a threshold, and thresholds on a thin market are noisy and can be straddled by a single pool.

### 5.3 Transfer

YED balances are tracked by the overlay. Transfers are recorded either in a transparent OP_RETURN or in a Sapling memo:

```
YB | 0x03 (TRANSFER) | recipient_id | yed_amount
```

Sapling transfers carry the record in the 512-byte encrypted memo, so YED balances and movements are private by default. Collateral is transparent; the dollar is shielded.

### 5.4 Redeem (burn-to-unlock)

After `lock_height`, the minter spends the vault. The spending transaction must contain:

```
YB | 0x04 (BURN) | vault_outpoint | yed_amount
```

with `yed_amount ≥` the vault's outstanding debt, drawn from the minter's YED balance, plus the fee output (§6.1).

**Rule R1:** any transaction spending a vault output that lacks a matching burn record is invalid. This is the rule that makes the system work, and it is the rule miners enforce.

### 5.5 Claim (extreme-case backstop)

**In plain terms.** If YEC falls so far that a vault's collateral is worth less than the YED minted against it, the minter has no reason to redeem; the collateral sits in a dead vault and the YED it backs would otherwise be worthless. The claim rule lets any YED holder take that collateral by burning the vault's debt in YED. The holder accepts a loss (the collateral is worth less than face), but it is an orderly, bounded loss available equally to everyone, instead of a total loss.

If a vault remains unspent past `lock_height + grace` (initial grace: 30 days) and its collateral value at `P_claim` is below 110% of its debt, it is **claimable**: any party may spend it by burning YED equal to the debt, receiving the full collateral.

If multiple claims target the same vault in one block, the first in block order is valid. Because the vault script requires the minter's signature, claims are implemented as a *second* spend path added to the vault script:

```
OP_IF
  <lock_height> OP_CHECKLOCKTIMEVERIFY OP_DROP <minter_pubkey> OP_CHECKSIG
OP_ELSE
  <claim_height> OP_CHECKLOCKTIMEVERIFY OP_DROP OP_TRUE
OP_ENDIF
```

where `claim_height = lock_height + grace`. The second path is anyone-can-spend at the base layer; **Rule R2** restricts it to transactions carrying a valid burn of the vault's debt. A miner majority enforcing R2 is what prevents the collateral from simply being swept.

*Note: this means an unenforced claim path is dangerous. Vaults using the claim path must not be created before activation (§7), and wallets must refuse to build them if signaling share falls below the safety threshold.*

### 5.6 Global guardrails

Computed from indexer state at each height:

- **Supply cap.** Total YED ≤ 15% of YEC market capitalization at `P_mint`. Mints exceeding the cap are invalid.
- **Global ratio halt.** If total collateral value at `P_mint` / total YED < 250%, minting halts until it recovers. Burns and claims continue.
- **Divergence halt.** If `P_fast` is more than 20% below `P_mid`, or `P_mid` is more than 20% below `P_slow`, minting halts until the windows re-converge within 20%. This fires within about two hours of a genuine crash, well before the slower windows catch up.
- **Participation halt.** If activation signaling share drops below 60% over the last 2,016 blocks, minting halts (§7).

Halts never affect redemption, transfer, or claims. Burns in particular are never restricted: a redemption removes YED and releases collateral in lockstep, which can only improve system health.

---

## 6. Fees and miner incentives

### 6.1 Yellowback fee

Every mint, burn, and claim transaction must include a dedicated fee output:

```
fee = max(0.5 YEC, 0.25% of vault collateral value at P_mint)
```

paid to the payout key of a **registered miner** selected deterministically:

```
selected_block = tip_height − (txid_low32 mod 100)
payee = payout_key from the tag in selected_block
```

If the selected block has no valid tag, walk back to the nearest block that does. Spreading fees across the last ~100 registered blocks rewards participation broadly rather than the current tip.

Selection is further weighted by the accuracy score defined in §4.4: a miner whose recent quotes tracked the median closely is selected proportionally more often. The exact weighting function is specified in the reference implementation and must be deterministic from chain state alone.

A transaction paying no fee, the wrong amount, or an unregistered key is invalid.

Initial split: 100% to the selected miner. A future version may route a slice to a YED-native reserve (§8.4).

### 6.2 Registration

A miner is registered from the block in which it publishes a valid tag until `N_reg` blocks later (initial: 576), renewed by each subsequent valid tag. Registration is revoked for `N_penalty` blocks on a quote-quality violation (§4.4).

Only registered miners can be fee payees. This is what ties income to running the module and publishing honestly.

### 6.3 Why this aligns incentives

- Running the module and publishing a tag is the only way to earn Yellowback fees.
- Publishing a dishonest quote forfeits fees and cannot move the median alone.
- Including an invalid Yellowback transaction, after activation, risks the block being orphaned by the enforcing majority.
- Pools pass fees to hashers through existing payout schemes, so hashers benefit with no action.

---

## 7. Activation

**What activation means.** Before activation, the Yellowback rules are only followed by the pools that happen to run the module; a rule-breaking transaction would be mined by any other pool. Activation is the one-time point at which enough hashpower runs the module that rule-breaking blocks get orphaned, making the rules effective for the whole network. Minting is disabled until then so that no YED exists before it is protected.

Modeled on BIP9 signaling, carried in the tag's flag bit.

1. **Signaling.** Pools running the module set bit 0. Wallets refuse to mint while the system is unactivated.
2. **Lock-in.** When ≥ 75% of blocks in a 2,016-block window carry the signal bit, activation locks in and enforcement begins at `H_activate = lock_in_height + 2,016`.
3. **Enforcement.** From `H_activate`, registered miners apply the block-validation hook (§3.2 item 4). Minting is enabled.
4. **Safety.** If signaling share over the trailing 2,016 blocks falls below 60%, minting halts (§5.6). Existing vaults remain redeemable and claimable. If share recovers above 75%, minting resumes.

Enforcement is probabilistic below majority and deterministic above it. The purpose of the 75% threshold is to ensure no YED exists before it is protected.

---

## 8. Extreme scenarios

### 8.1 YEC rises 500% in a day

Honest quotes track the exchanges within minutes. `P_fast` follows within about two hours, `P_mid` within about six, `P_slow` within about 42. Because `P_mint` is the minimum, minters are held to the pre-rise price for roughly two days; existing vaults simply become far safer. The peer-median rule means no honest pool is penalized for quoting the new price ahead of the slow windows. No safety issue arises from a rise; the only effect is a delay in mint capacity.

### 8.2 YEC falls 80% in a day

`P_fast` marks `P_mint` to the crash within about two hours, and the divergence halt pauses minting as soon as `P_fast` drops 20% below `P_mid`, so no vault can be minted against a stale price during the lag. The volatility multiplier raises ratios for any subsequent mint. Claims are unaffected in the short term because `P_claim` uses the slow windows and requires the 30-day grace period. Minters with healthy vaults continue to redeem; nothing is liquidated.

### 8.3 YEC falls 67% (to the class C ratio floor)

Vaults remain fully collateralized at or above 100%. No action needed. Minting halts under the global ratio rule if the aggregate drops below 250%. Minters continue to redeem normally; nothing is liquidated.

### 8.4 YEC falls 90% (the "1-cent" case)

Vaults are underwater; collateral covers ~30% of debt at a 300% starting ratio. Rational minters do not redeem. Without a backstop, YED would be a claim on nothing.

With Rule R2: after `lock_height + grace`, each abandoned vault becomes claimable by burning its debt in YED. YED holders convert YED into distressed collateral at `P_claim`. The loss is real but **bounded, automatic, and equally available to every holder** — there is no run, no auction, no keeper, and no custodian releasing anything. YED supply shrinks with each claim, and the peg re-anchors to the remaining healthy vaults.

Minters who abandoned vaults lose all collateral to claimants, the same outcome a liquidation engine would produce, but without cascade dynamics during the lock.

### 8.5 Price manipulation attempt

A minority miner publishing false quotes moves any median by at most its hashpower percentile, is discarded by the min/max selectors in the harmful direction, and loses fee eligibility. A majority attacker could move the median, but a majority attacker can already reorganize the chain; Yellowback adds no new trust assumption.

### 8.6 Miner participation collapses

Signaling falls below 60%: minting pauses. Existing vaults redeem normally (R1 enforcement weakens, but the minter's incentive to redeem a healthy vault — recovering 3–5× the debt — is unchanged). Claims on abandoned vaults become risky because the anyone-can-spend path may be swept; this is the one degraded state, and the reason claim-path vaults are gated on activation.

A future YED-native reserve, funded from a fee slice and held only in overlay state (no key can move it), could backstop holders in this state by burning reserve YED to raise the global ratio.

---

## 9. Security analysis

| Threat | Mitigation |
|---|---|
| Minter reclaims collateral without burning | R1, miner-enforced |
| Underwater minter abandons vault | R2 claim path after grace |
| Single-miner price manipulation | Three-window medians; min/max selectors; peer-median penalties; accuracy weighting |
| Thin-exchange flash crash | 15-minute VWAP per quote; multi-window medians; divergence halt |
| Genuine fast crash outruns the reference price | `P_fast` in the mint minimum; divergence halt; volatility-indexed ratios |
| Honest pools penalized during a genuine fast move | Deviation measured against peer median, not the lagging reference |
| Non-participating pool includes invalid tx | Orphaned by enforcing majority post-activation |
| Fee routed to non-participating pool | Registration requirement on payee |
| Anyone-can-spend claim path swept | R2 enforcement; activation gating; participation halt |
| Overlay state divergence between implementations | Integer-only arithmetic; canonical record formats; reference validator |

### Trust assumptions

- Honest majority of Ycash hashpower runs the module and follows its rules. This is the chain's existing security assumption.
- Exchange price sources are not simultaneously compromised across a majority of pools.

No party holds keys to any user's or the system's funds.

---

## 10. Upgrade path

Once the rules are proven under miner enforcement, the same rules can be proposed as consensus in a scheduled Ycash network upgrade. At that point:

- R1 and R2 become validated by every full node, not only miners.
- The coinbase tag becomes a consensus-validated field.
- The activation state machine is retired.

Miner enforcement is the launch mechanism; consensus enforcement is the destination.

---

## 11. Open questions

1. **Grace period length.** 30 days is a placeholder; it trades minter flexibility against holder exposure.
2. **Claim ordering.** First-in-block is simple but favors miners' own claims. Consider a claim-announcement window.
3. **Supply cap.** 15% of market cap is conservative by design; revisit with data.
4. **Reserve.** Whether and when to introduce a YED-native reserve funded by a fee slice.
5. **Term-class ratios.** Initial numbers are illustrative; calibrate against YEC realized volatility.
6. **Exchange support.** Exchanges listing YED need the overlay indexer; a lightweight verification library should ship with the reference implementation.

---

## 12. Roadmap

1. **Spec freeze.** Record formats, tag format, validation rules, test vectors.
2. **Reference module.** `ycashd` patch with indexer, template filter, tag insertion, validation hook, RPCs.
3. **Wallet integration.** Mint, transfer (transparent and Sapling), burn, claim; raw-median display.
4. **Testnet.** Two or more independent pools signaling; adversarial tests for R1, R2, price manipulation, halts.
5. **Pool outreach.** Operator onboarding, source configuration guidance, payout-key setup.
6. **Mainnet signaling.** Activation per §7.

---

## Appendix A: Source mask registry (initial)

| Bit | Source |
|---|---|
| 0 | SafeTrade |
| 1 | CoinGecko aggregate |
| 2 | CoinMarketCap aggregate |
| 3–15 | Reserved; assigned by spec revision |

Operators may set additional bits as venues are registered. Unregistered bits are ignored by validators but preserved for analysis.

## Appendix B: Initial parameters

| Parameter | Value |
|---|---|
| `P_fast` window | 96 blocks |
| `P_mid` window | 576 blocks |
| `P_slow` window | 2,016 blocks |
| Mint price `P_mint` | min(P_fast, P_mid, P_slow) |
| Claim price `P_claim` | max(P_mid, P_slow) |
| Quote VWAP window | 15 minutes |
| Quote staleness limit | 30 minutes |
| Peer median window | 20 blocks |
| Quote deviation penalty | > 10% from peer median |
| Accuracy score band | within 3% of peer median |
| Volatility window | 2,016 blocks |
| `σ_ref` | 100% annualized |
| N_reg | 576 blocks |
| N_penalty | 288 blocks |
| Fee | max(0.5 YEC, 0.25% collateral value) |
| Fee payee window | 100 blocks |
| Grace period | 30 days |
| Claim threshold | collateral < 110% of debt |
| Supply cap | 15% of YEC market cap |
| Global ratio halt | < 250% |
| Divergence halt | P_fast < 0.8 × P_mid, or P_mid < 0.8 × P_slow |
| Activation threshold | 75% of 2,016 blocks |
| Participation halt | < 60% of 2,016 blocks |
