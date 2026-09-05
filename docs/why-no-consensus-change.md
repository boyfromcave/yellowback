# Why Yellowback needs no consensus change

**Ycash Yellowback (YED)** is the system this document is about; YED is its unit.

**Audience:** anyone who needs to understand, or explain to the Ycash team, how a full
DigiDollar-style stablecoin can run on Ycash without a hard fork, a soft fork, a new opcode, or a
network upgrade — and what that costs. This is the plain-language rationale behind the Tier-0
decision in [`plans/yellowback-v1-development-plan.md`](plans/yellowback-v1-development-plan.md) §1 and D1.
The plan is normative; this document explains it.

Every claim below was checked against the pinned trees (`ref/digibyte` @ `v9.26.5`, `ref/ycash` @
`v4.5.0`). Line cites are to those pins; run `make status` before trusting them.

Re-checked against plan revisions 4–12 (audit rows C1–C25, D1–D9, E1–E9, F1–F6, G1–G7 and
H1–H6, the development workflow in §6.0, the user-interface section §4.7 and the YecWallet fork
`yecwallet-dd`): every change in those revisions is inside the overlay index, the wallet layer, the
federation coordinator, the test workflow or the GUI wallet; none moves any rule into consensus or
policy, so every claim here stands unchanged. Nothing in this document depends on
`ref/yecwallet`.

---

## 1. The one-sentence answer

**The Ycash chain never needs to know Yellowback exists.** Yellowback uses only transaction shapes Ycash
already accepts today and puts the "this is a dollar" meaning in a small data note that every
Yellowback-aware node interprets identically. Ordinary nodes see ordinary transactions. Yellowback nodes
see a stablecoin. Nothing new is rejected and nothing new is accepted by consensus, so there is
nothing to fork.

This is the same shape as the atomic-swap feature Ycash shipped in v4.5.0 (`ref/ycash` commit
`ccddd22e4`: RPCs, a script helper, an experimental-features flag, 17 lines in `main.cpp` and
about 400 in the wallet files). Yellowback needs even fewer hooks — zero lines in `main.cpp` and zero
in `src/wallet/`, for the reason in §3.5.

## 2. Why DigiByte *did* change consensus, and why that is not required

DigiByte added opcodes `0xbb–0xbf` (`ref/digibyte/src/script/script.h:210-211`) and a validation
module (`ref/digibyte/src/digidollar/validation.cpp`) so that the chain itself rejects an invalid
mint, transfer, or redemption. That is the strongest possible guarantee, and it is available to
DigiByte cheaply because it already had Taproot and Tapscript's `OP_SUCCESSx` soft-fork mechanism.

Ycash has none of that. Bytes `0xbb–0xbf` are simply bad opcodes there
(`ref/ycash/src/script/interpreter.cpp:942`), and Ycash has never done a soft fork; its only
activation mechanism is a height-gated network upgrade with a new consensus branch ID
([`mapping.md`](mapping.md) §2, §4). So "port the opcodes" is a coordinated network upgrade — the
most expensive thing one can ask of a risk-averse team running a chain with a shielded pool.

The key observation is that **the consensus rules are not what makes DigiDollar work; they are
what makes it trustless.** Every DigiDollar feature can be *expressed* with the tools Ycash
already has. What changes is *who enforces* one rule (§4).

## 3. How each DigiDollar feature maps onto rules Ycash already enforces

### 3.1 Tokens — colored outputs plus an `OP_RETURN` note

A YED balance is an ordinary transparent P2PKH output carrying a small amount of YEC, plus the
transaction's single `OP_RETURN` output saying "output N is worth X cents." This is the
colored-coin model (Omni, Counterparty, Runes).

It is also **what DigiDollar itself does**: its token output is a zero-value P2TR and the cent
amount lives in `OP_RETURN` metadata (`ref/digibyte/src/digidollar/txbuilder.cpp:407-418`). Ycash
policy already relays exactly one `OP_RETURN` per transaction with up to 80 data bytes
(`ref/ycash/src/policy/policy.cpp:52,121-122`; `ref/ycash/src/script/standard.h:34`). No change.

### 3.2 Locked collateral — P2SH with `CHECKLOCKTIMEVERIFY` and multisig

DigiDollar locks collateral in a Taproot script tree with a timelock leaf. Ycash has no Taproot,
but it has enforced `CHECKLOCKTIMEVERIFY` and P2SH in every block for years: `ConnectBlock`
validates with `SCRIPT_VERIFY_P2SH | SCRIPT_VERIFY_CHECKLOCKTIMEVERIFY`
(`ref/ycash/src/main.cpp:2931`).

So the vault is a P2SH output whose redeem script says: *not before height H, and the owner's
signature, and k-of-n federation signatures.* The chain enforces the timelock and every signature
for free. The federation's role in this script is explained in §4.

### 3.3 Price oracle — an anchor coin the federation keeps spending

DigiByte publishes prices in the coinbase, signed by a 7-of-35 MuSig2 quorum
(`ref/digibyte/src/oracle/musig2_session.h:66`). Ycash has no MuSig2, no Schnorr, and its coinbase
is already shaped by founders'/YDF streams, so touching either is a network upgrade.

Instead the federation holds a well-known **anchor UTXO** — an ordinary k-of-n P2SH multisig — and
publishes a price by spending it into a new anchor plus an `OP_RETURN` price note. Consensus
verifies the k-of-n ECDSA signatures as it would for any transaction; Yellowback nodes only parse the
note. Because each price spends the previous anchor, updates are serialised by construction. No
miner involvement, no P2P messages, no new signature code.

### 3.4 Tiers, collateral ratios, DCA, ERR, volatility protection — arithmetic

These are integer tables and formulas (`ref/digibyte/src/consensus/digidollar.h:72-84`,
`src/consensus/dca.cpp`, `src/consensus/err.cpp`). They are ported as-is into the overlay and
evaluated by every Yellowback node with the same integer math on the same blocks. Since all nodes read
the same chain and run the same deterministic rules, they all compute the same Yellowback state:
supply, vault status, required burns, health. Conservation and accounting are therefore enforced
by every honest Yellowback node — without the chain rejecting anything.

### 3.5 Watching the chain — a signal Ycash already emits

The atomic-swap feature added 17 lines to `main.cpp` to observe blocks. Yellowback needs none:
Ycash's wallet notifier already reads every connected and disconnected block from disk, in exact
chain order, and delivers it to subscribers through `CValidationInterface::ChainTip`
(`ref/ycash/src/validationinterface.cpp:183-217`). The wallet's own Sapling witness cache depends
on these semantics, so the mechanism is proven on every node today. The Yellowback index subscribes
to that signal, keeps its own rebuildable LevelDB, and rolls back on reorgs with per-block undo
records.

### 3.6 Everything else

| Need | Ycash already has |
|---|---|
| Signatures | ECDSA `OP_CHECKSIG` / `OP_CHECKMULTISIG`, the same code that verifies every transparent input |
| Partial signing across operators | `signrawtransaction` merges partial signatures (`ref/ycash/src/rpc/rawtransaction.cpp:1057-1061`) |
| Opt-in activation | `-experimentalfeatures` + a feature flag (`ref/ycash/src/experimental_features.cpp`), as atomic swaps do |
| Preventing accidental burns | `CWallet::LockCoin` (`ref/ycash/src/wallet/wallet.h:1369`), applied before the wallet commits a transaction and kept across reorgs, and a distinct Yellowback address prefix |
| Bounded staleness | transaction expiry (`DEFAULT_POST_BLOSSOM_TX_EXPIRY_DELTA = 40`, `ref/ycash/src/main.h:78-79`) |

## 4. The one rule an overlay cannot enforce, stated plainly

DigiByte's consensus refuses a redemption unless the matching DigiDollar is burned
(`ref/digibyte/src/digidollar/validation.cpp:2163`, `bad-redeem-dd-not-burned`). Ycash's chain
cannot check that: a script can say "not before height H" and "these keys must sign," but no
Ycash script can say "only if a token was destroyed in this transaction." That is a covenant, and
Ycash has none.

If the vault script were just *timelock + owner key*, the owner could wait out the lock, take the
collateral back, **and keep the YED they had already sold** — minting would be a free loan
(plan D3). So the vault script additionally requires **k-of-n federation signatures**, and the
federation signs a release only after verifying that the required burn is in the same transaction.

**Consequences:**

- **Functionality is complete.** Mint, transfer, redeem, lock tiers, collateral ratios, DCA, ERR,
  volatility protection, and the price feed all exist and behave as in DigiDollar (deviations, all
  parametric or platform-driven, are listed in the plan §10).
- **The trust model changes in one place.** DigiDollar already trusts a 7-of-35 quorum for prices.
  Yellowback v1 trusts a 5-of-9 quorum for prices *and* for "no release without burn." A colluding
  quorum could release collateral without a burn, or publish a false price. A quorum with fewer
  than k live keys pauses redemptions and new mints (transfers continue) until it recovers.
- **What the federation still cannot do:** create YED from nothing, move anyone's YED, or
  take collateral without the owner's signature. Those are pure accounting and script rules that
  every Yellowback node checks and the chain enforces respectively.
- **It is visible.** A release without the required burn is detectable by every Yellowback node on
  chain (the closed vault's `burnedCents` is below the burn its closing block required, plan F1),
  which is what makes roster rotation and public accountability possible.

The full trust statement and threat model are in the plan §8. They must be published verbatim
with v1.

## 5. Why this is the right order, not a compromise

1. **It is the smallest change that yields a working dollar.** Zero lines in `src/main.cpp`,
   `src/consensus/`, `src/script/`, `src/primitives/`, `src/pow/`, or `src/chainparams.cpp`. Block
   validity, mempool policy, shielded-pool value balance, fee policy, and P2P behaviour are
   byte-for-byte those of v4.5.0 for every node, with or without `-yellowback` (plan §8.3).
2. **It has precedent.** The atomic-swap feature was merged at exactly this tier.
3. **It is the specification for the consensus rule.** The overlay's validator is written as pure
   functions of `(transaction, state, height)`. If the Ycash team later chooses a network upgrade,
   `ConnectBlock` calls that same validator and the "burn before release" rule moves from the
   federation into consensus with no redesign (plan §9). Shipping the overlay first gives that
   future upgrade a validator with months of real mileage.

## 6. How to explain it in one paragraph

> Yellowback is an overlay on ordinary Ycash transactions, the way Omni was an overlay on Bitcoin and
> the way DigiDollar itself stores dollar amounts in `OP_RETURN`. Collateral sits in timelocked
> multisig scripts Ycash has enforced for years; prices are published by a federation spending a
> multisig anchor coin; every Yellowback node computes the same state from the same chain with the
> same integer rules. No consensus code changes and no fork is needed. The single thing DigiByte
> enforces in consensus that Ycash cannot — "you must burn YED to unlock collateral" — is
> enforced by requiring a 5-of-9 federation co-signature on every release, and that trust
> assumption is stated openly, with a defined path to move it into consensus later.
