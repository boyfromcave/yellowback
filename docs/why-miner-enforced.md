# Why Yellowback is miner-enforced

**Ycash Yellowback (YED)** is the system this document is about; YED is its unit.

**Audience:** anyone who needs to understand, or explain to the Ycash team and to pool operators,
why Yellowback v2 is enforced by mining pools rather than by a federation or by a network upgrade,
what that buys, and what it costs. This is the plain-language rationale behind
[`plans/yellowback-v2-development-plan.md`](plans/yellowback-v2-development-plan.md) §1 and V1.
The plan is normative; this document explains it. It replaces `why-no-consensus-change.md`
(retired 2026-09-10), which argued for the federation design on the grounds that it needed no consensus
change; §2 below keeps the part of that argument that is still true, and §5 says plainly what v2
gives up by not taking the same road.

Every claim below was checked against the pinned trees (`ref/digibyte` @ `v9.26.5`, `ref/ycash` @
`v4.5.0`) and against the v2 plan at revision 6 (2026-09-10) and the proposal
[`reference/yellowback-miner-enforced-proposal.md`](reference/yellowback-miner-enforced-proposal.md)
(v0.2). Line cites are to those pins; run `make status` before trusting them.

---

## 1. The one-sentence answer

**The only party on a proof-of-work chain that can refuse a transaction without a consensus change
is the miner, so the one rule Ycash script cannot express is handed to mining pools.** Pools that
run the Yellowback module publish a YEC/USD quote in each coinbase, keep rule-breaking Yellowback
transactions out of their own blocks, and, once three quarters of blocks signal, refuse to build on
a block that releases vault collateral without burning the debt. Nobody holds a key to anyone's
collateral but the minter. Nobody sits between a minter and their redemption. The price comes from
hashpower, not from a committee. Anyone who does not hold YED changes nothing; a wallet or exchange
that holds YED runs a Yellowback-aware node, with no enforcement role; GPU miners
change nothing.

**Is this a consensus change? Yes, in effect; no, in code.** Enforcing pools apply one block-validity
rule that stock nodes do not (a block that releases collateral without the burn is invalid to
them), so once a majority of hashpower enforces it, the whole network lives under that rule. That
is the definition of a soft fork, the same category as P2SH and CLTV, and this document calls it
one. What it is **not** is a change to the rules every Ycash node applies: no new opcode, no branch
ID, no network upgrade, and no release the Ycash team must ship. The check lives in `ConnectBlock`
of the patched node (about 50 lines, §5), is inert without `-yellowback`, and is switched off by a
flag. Every block an enforcing pool mines is valid to a stock node, and a stock node never rejects
anything it accepts today.

## 2. The rule Ycash cannot enforce, and why every no-fork design ends in a committee

A vault is a P2SH output whose redeem script Ycash already validates in every block with
`SCRIPT_VERIFY_P2SH | SCRIPT_VERIFY_CHECKLOCKTIMEVERIFY` (`ref/ycash/src/main.cpp:2931`). A script
can say *not before height H* and *this key must sign*. It cannot say *only if the matching YED was
burned in this transaction*, and it cannot read a price. That is a covenant, and Ycash has none.
DigiByte enforces exactly this in consensus (`ref/digibyte/src/digidollar/validation.cpp:2163`,
`bad-redeem-dd-not-burned`), which it could add cheaply because Tapscript's `OP_SUCCESSx` gave it a
soft-fork mechanism; the same opcode bytes are simply invalid on Ycash
(`ref/ycash/src/script/interpreter.cpp:942`), and Ycash's only activation mechanism is a
height-gated network upgrade with a new branch ID ([`mapping.md`](mapping.md) §2, §4).

Without an enforcer, a minter sells the YED, waits out the lock, takes the collateral back, and
keeps both. That hole is in the normal case, not only in a crash.

Every remedy that avoids touching consensus substitutes a group holding keys for the missing rule:
a federation co-signing releases (the retired federation design), an oracle committee, threshold signers, a redemption pool, a
DLC settlement set. They differ in ceremony, not in kind. Each of them means:

- **Redemption has a gatekeeper.** A release needs `k` named operators online, reachable and
  willing. The federation design needed 5 of 9 for every redemption and every price. An operator outage pauses
  redemptions; an operator veto blocks them; the roster decides who redeems.
- **Somebody can release without a burn.** A colluding quorum holds the release key to every
  vault. Detection is possible after the fact; prevention is not.
- **The price is whatever the committee signs.** The federation design published prices by spending a k-of-n anchor
  coin. Manipulation cost was the cost of corrupting `k` operators.
- **It is a standing institution.** Roster rotation, key ceremonies, operator agreements and
  liability all have to exist and be maintained for as long as one vault is open.

Coordinating those signers was the burden the product owner named on 2026-09-10. The proposal's
answer is to remove the committee rather than to run it better.

## 3. Why miners

- **They already have the power.** A majority of hashpower that will not include an invalid vault
  spend, and will not build on a block that contains one, enforces the rule for the whole network.
  No node release, no new opcode, no branch ID. This is the category P2SH and CLTV belong to on
  Bitcoin, deployed at the pool layer.
- **They are the natural price source.** One quote per block, aggregated as rolling medians of 96,
  576 and 2,016 blocks, gives a feed whose manipulation cost is *a majority of quote-tagged blocks
  sustained over hours to days*, which is a majority of hashpower only when most blocks carry quotes;
  the claim-price windows therefore require two thirds of their blocks to carry a quote before they
  are defined (L9). A minority pool moves a median
  by at most its share's percentile and, under wallets' default payee choice, loses fee income for
  lying (L1).
- **They can be paid for it.** Every mint, redemption and claim pays an enforcement fee of
  `max(0.5 YEC, 0.25 % of the collateral)` to a pool that published a quote in the 100 blocks
  up to and including the transaction's reference height. The fee pays for *quoting*, not for
  including the transaction: a pool earns in proportion to how many blocks it quotes in, whether
  or not a Yellowback transaction happens to land in one of them, so a small pool that quotes
  every block earns its share. The wallet names the payee at signing time (by default weighted
  toward pools whose quotes track the peer median; the defaults are release-versioned and a node
  may override them, L6), since the miner of the containing block is not known yet, and block
  validity checks only the amount and that the payee quoted recently. `yed_redeem` and
  `yed_claim` dry-run the transaction against the node's own evaluator before broadcasting, so a
  user never sends what an enforcing pool would reject (V24).
- **They are accountable on chain.** Every quote carries a payout key in a permanent block. A
  pool that skews the feed is visible to its own hashers and to everyone else.
- **Nobody else has to move.** Hashers keep their GPU software. Anyone who does not hold YED
  changes nothing; a wallet or exchange that holds YED runs a Yellowback-aware node
  with no enforcement role; the overlay reads the chain, it does not change it.

## 4. What the priorities are, and how the design serves them

The product owner's priorities (decision of 2026-09-10) are decentralization and self-custody, no
committee that can gatekeep or override redemption, a price that is expensive to move, and a launch
that does not require the Ycash team to ship a network upgrade. The concrete consequences:

| Priority | Federation design (retired) | Miner-enforced (this plan) |
|---|---|---|
| Who can spend a vault before the claim height | owner **and** 5-of-9 federation | owner only |
| What a redemption needs | a signing round with `k` operators online | one wallet call; no counterparty |
| Who can release collateral without a burn | the owner plus a colluding quorum | the owner plus a non-enforcing hashpower majority (which could already reorganise the chain); after the claim height, anyone, under the same majority |
| Who sets the price | the federation, by co-signing an anchor spend | medians of quotes from every pool that mines a block |
| Cost to move the price | corrupt `k` operators | a majority of quote-tagged blocks for hours to days (a hashpower majority when quoting is near-universal; the claim-price windows need two-thirds fill, L9) |
| What exists as a standing institution | a roster with keys, rotation and ceremonies | nothing; pools opt in per block |
| Node changes for users and exchanges | none beyond the Yellowback-aware node a YED holder already runs | same |
| Ycash network upgrade required | no | no |

The claim rule follows from the same priorities. When YEC crashes far enough that minters abandon
underwater vaults, YED holders take the collateral themselves by burning YED after a grace period,
once the vault is underwater at a price from the slow windows. The loss is bounded and automatic,
and available to every holder subject to the claim-ordering question that is still open (plan §12
Q2, §5 below). There is no keeper, no auction, no custodian releasing anything, and nothing a liquidation
engine could cascade during the lock.

## 5. What it costs, stated plainly

These are the trade-offs the team is accepting. Each row cites where the plan bounds it. `Vn`,
`Kn`, `Ln` and `Qn` are the plan's decision-record entries, its revision-2 audit findings, its
revision-3 and revision-4 decisions, and its §12 open questions.

| Trade-off | What v2 gives up or takes on | How the plan bounds it |
|---|---|---|
| **It is a soft fork.** | The federation design changed zero lines in `main.cpp`. This design inserts about 50 lines across `main.cpp` and `miner.cpp`, all behind `-yellowback`, one insertion of them the block-validity check, and zero lines in `consensus/`, `script/`, `primitives/` or `pow/`. A node without the flag runs v4.5.0's code paths unchanged. | Plan §4.1 diff budget (its one wallet-tier row, `src/wallet/rpcwallet.cpp`, is the H5/H8 coin-locking and key-import guards); V1 places the hook in the `ConnectBlock` window `ref/ycash/src/main.cpp:3191-3193` after every consensus check; `DoS(0)` so a stock peer is never banned (`:2304-2305`). |
| **A bug in the hook can fork enforcing miners off the chain.** | A federation bug pauses redemptions; an enforcement bug orphans blocks. | The hook fires only on spends of ACTIVE vaults, never on mints, transfers or tags (V3); evaluation is total and fails open only on storage failure (V13, K1); `-yellowbackenforce=0` plus `ReconsiderBlock` rejoins the network's chain, and the **work valve** does the same automatically: when a chain rooted at a block this node rejected is six blocks ahead in work, the node stops enforcing for the session, follows the majority chain and alerts (ACT-7, L7); descendants of a rejected block are never a reason to ban a stock peer (BLK-2); enforcement is off until activation, while signalling is below half, and past each release's sunset height (V12, ACT-5, L8); no rejection happens during initial sync or a reindex, and none on a block the network has already built six blocks of work on, so a node catching up after an outage follows the chain instead of splitting from it (BLK-2, L11). |
| **Soundness depends on pool participation, not on a fixed roster.** | Below a majority, "miner-enforced" is probabilistic. A non-participating pool's block that releases collateral without a burn stands unless enforcers orphan it. The signal bit is set only by a node that also enforces (`-yellowbackenforce=1`), but it is self-reported and anyone can forge it, so the count under-counts only among honest pools; the work valve (L7) is the mechanical backstop. | Minting is impossible before ≥ 75 % of a 2,016-block window signals plus a 2,016-block delay, so no YED exists before it is protected. The two floors are split (L3): minting halts when signalling in the trailing 2,016-block window falls below 60 % (1,210 blocks) and resumes at 75 % (1,512); block rejection suspends only below 50 % (1,008) and resumes at 60 % (1,210), so enforcement outlasts the mint halt (hysteresis, K15; K2), and if enforcers do end up on a losing branch the work valve returns them to the majority chain within six blocks (L7). Each release also stops enforcing at a sunset height about a year after its start, so a stale release can never split from an upgraded one (L8). Redemptions by minters never pause. As with any soft fork, every pool, participating or not, should run the module at least in filter-only mode, or one attacker vault can have its blocks orphaned repeatedly. |
| **The claim path is anyone-can-spend at the script level.** | While block rejection is suspended, an abandoned vault's collateral is protected only by pools that still filter their templates. This is the one degraded state. | Vaults cannot be minted before activation; while rejection is suspended neither the owner path nor the claim path is policed, collateral spent then is gone and its YED stays in circulation as unbacked, and vaults untouched during the pause are protected again when it ends; the grace period gives minters time to redeem first. If the module is ever abandoned (rejection suspended for two full signal windows — which is also where a sunset with no successor release ends up, L12), owners may sweep their own collateral without a burn through `yed_sweep`, gated on that chain-derived state and never on the owner's own node, and YED holders keep the claim path: a fair race that already existed at the script level (L10). |
| **Hashpower concentration.** | If one pool exceeds the threshold, "miner-enforced" means "that pool-enforced". | A written launch bar (L2, L4): at least `N` independent pools, no pool above `X %` of quote-tagged blocks over a full 2,016-block window, counted by payout key (provisional `N ≥ 3`, `X ≤ 40 %`). On mainnet `-yellowbacksignal` defaults to off in the first release, so pools quote with the signal bit clear and the bar is measured on real quote tags and published before the signalling announcement; after it, pools set `-yellowbacksignal=1`. This is still governance, not code; a pool can quote from many keys. |
| **Price availability depends on pools running the quote agent.** | The federation could publish a price as long as `k` operators were up. Under v2, a window in which fewer than half the blocks carry a quote has no price, and because claims read the slow-window price, a thin window pauses claims as well as mints. | Fail closed: no `P_mint` means no new mints; burns and redemptions never depend on a price (V16, HALT-1). Signal-only tags keep activation counting when a pool's feed is down (V9); the quote agent clears its quote after two failed polls so a pool with a dead feed goes signal-only within about a minute (L5). |
| **The price is slow by design.** | `P_mint` is the minimum of three medians and lags a genuine rise by about two days; `P_claim` uses the slow windows. | Deliberate: prefer hard-to-move prices over fast ones. A fast crash marks `P_mint` down within two hours through the 96-block window and a divergence halt pauses minting (proposal §8.2). |
| **Users pay an enforcement fee.** | `max(0.5 YEC, 0.25 % of collateral)` on every mint, redemption and claim, on top of the ordinary transaction fee. A mint must lock at least four times the minimum fee so its redemption can always pay (K14). | The fee is the module's only income and the plan's reason to expect pools to run it; whether it is enough is measured on testnet and in the 90-day mainnet review (Phases 9 and 10). No fee is required when no pool quoted in the window (FEE-0), so a redemption never waits on miners. |
| **Parameters are consensus-shaped among enforcers.** | The price windows, the payee window, the fee constants, the claim threshold and the grace period must be identical on every enforcing node; changing one is a coordinated release with a start height (K10). | Narrowed by L1: the peer-median judgements, penalties and accuracy scores are wallet policy and `yed_listminers` data, never a validity input, so a bug there cannot split the enforcing set. |
| **Quotes are unauthenticated.** | A pool can publish a tag under another pool's payout key, penalising the victim in wallets' default payee choice for one window. The lie still counts once in the medians. | The attacker forfeits its own slot and fee for that block; signed tags or a registration transaction are open (K9, plan §12 Q14). |
| **Pools see claims first.** | A pool can front-run a claim on its own block. | Open (Q2); a commit-reveal claim window is the candidate fix. |
| **Shielded YED is deferred.** | Miners cannot enforce what they cannot read, so YED stays on transparent colored outputs. | The federation design was transparent-only too; research item (V8, plan §12 Q6). |
| **Pool operators must act.** | Each participating pool runs a patched `ycashd`, sets a payout address, and runs the quote agent against exchange sources it chooses. | The pool kit (plan §5): a pool that reuses the node's `coinbasetxn` needs nothing else; one that assembles its own coinbase appends `coinbaseaux.flags`, and which stacks honour that is a Phase 7 survey (plan §12 Q9). Hashers' GPU software is unchanged; a pool must keep its own coinbase text under about 55 bytes (V4), and a pool whose index goes unhealthy stops tagging and can be told to stop serving templates (`-yellowbackrequirehealthy`, K24). |
| **Two user-loss residuals stay.** | A mint that races the supply cap, or whose reference snapshot is changed by a reorg deeper than `REF_LAG` (2 blocks), is VOID: collateral locked until `lockHeight` with no YED. Because a VOID vault is not policed, its owner must sweep it before `claimHeight` (K3). | Inherited from the prototype code; strict template policy keeps enforcing pools from mining such a mint; `yed_getvault` and the wallet warn a VOID owner to sweep. |

**What v2 does not give up.** No operator, committee or key other than the minter's can move
collateral before the claim height; after it, only a burn of the vault's debt can. Nothing any
pool does can create YED, move a user's YED, or take collateral before the claim height. Accounting (conservation, supply, collateral totals, vault status, prices,
activation, halts) is computed identically by every Yellowback-aware node from the chain alone.
The full trust statement is plan §8.1 and must be published verbatim with v2.

## 6. What is kept from the no-fork design

The overlay groundwork from the federation prototype is not wasted; this design stands on it. The first three use only rules Ycash
enforces today and shapes it relays today; the last three are the prototype's machinery moved to where the
hook can read it:

- **Tokens** are transparent P2PKH outputs carrying dust, with one `OP_RETURN` payload per
  transaction saying which output is worth how many cents. Ycash relays exactly one `OP_RETURN` of
  up to 80 bytes (`ref/ycash/src/policy/policy.cpp:52,121-122`). DigiByte's own token follows the
  same model (`ref/digibyte/src/digidollar/txbuilder.cpp:407-418`).
- **Vaults** are P2SH with `CHECKLOCKTIMEVERIFY`, validated by consensus in every block. The
  federation keys leave the script; a second branch with a later timelock and no key is added for
  the claim path. The chain enforces the timelocks and the owner's signature for free.
- **Term classes, collateral ratios, the volatility multiplier, halts and the supply cap** are integer arithmetic every
  Yellowback node evaluates identically.
- **The index** is a rebuildable LevelDB with per-block undo, now applied inside the block-connect
  path so a validity check can read the state at the parent block (V2).
- **Bounded staleness** comes from transaction expiry
  (`DEFAULT_POST_BLOSSOM_TX_EXPIRY_DELTA = 40`, `ref/ycash/src/main.h:78-79`), which is why every
  mint, redemption and claim commits a reference height.
- **The price tag** rides in the coinbase scriptSig after the BIP34 height push, in the never-assigned
  `COINBASE_FLAGS` global (Ycash reads it into every coinbase but nothing sets it), so the internal
  miner, regtest `generate` and `getblocktemplate` all
  emit it without new plumbing (V4, V5). A coinbase tag never makes a block invalid.

## 7. Why this order: miner enforcement first, consensus later

1. **It is the smallest change that yields a dollar nobody can gatekeep.** A federation has a
   smaller consensus footprint and a larger trust assumption; a network upgrade has the smallest
   trust assumption and the largest cost, and is the biggest ask a risk-averse team running a
   shielded pool can be given.
2. **The rules are written to be promoted.** The validator is a pure function of
   `(block, state, params)` and its state is already applied inside `ConnectBlock`. A later
   Ycash network upgrade would change who runs the check, not what it checks, retire the
   activation state machine, and make every full node rather than only miners enforce it
   (plan §9). Months of miner-enforced mileage would be the evidence to bring to that proposal.
3. **It degrades to safe where the design can.** Loss of participation or of a price ends in "no
   new mints", never in "a minter cannot redeem". The two residuals it cannot remove, a hashpower
   majority that stops enforcing and a hook bug that orphans blocks, are rows 2 to 4 of §5, and
   are the same assumption the chain already makes.

## 8. How to explain it in one paragraph

> Yellowback is an overlay on ordinary Ycash transactions: collateral sits in timelocked scripts
> Ycash has enforced for years, YED lives on colored outputs with an `OP_RETURN` note, and every
> Yellowback node computes the same state from the same chain. The one thing Ycash script cannot
> check, that collateral is released only when the debt is burned, is enforced by mining pools
> running a patched node: they publish a YEC/USD quote in each block, keep rule-breaking
> transactions out of their templates, and once three quarters of blocks signal, orphan any block
> that breaks the rule. That makes it a soft fork carried by mining software, with about sixty
> lines behind a flag, a kill switch, and an activation that waits for three quarters of blocks
> to signal, announced only once the pool set meets a written diversity bar measured on real
> quote tags (L4). In exchange there is no federation, no committee that can pause or veto a
> redemption, no key on a vault but the minter's, and a price whose manipulation costs a sustained
> majority of quoting blocks. The costs are the fork risk of any soft fork, bounded by a work valve
> that returns enforcers to the majority chain within six blocks, dependence on pool
> participation for minting and for protecting abandoned vaults, and an enforcement fee on every
> mint and redemption; each is bounded in the plan and stated in its trust statement.
