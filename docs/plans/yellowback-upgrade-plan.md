# Ycash Yellowback (YED) and Wrapped Ycash (wYEC) — one agnostic primitive, two applications, one rule module

**Revision 1 (2026-10-05), a plan; nothing implemented.** Promoted from
`docs/ideation/` (its revision 3, same day) by owner decision: the Ycash Foundation is still
ideating its lock/unlock primitive and has not written a spec, so **this plan proceeds on stated
assumptions about the primitive (§0) and it is Yellowback's responsibility to build out what the
primitive plus two applications can be.** Every assumption is marked so it can be replaced by the
Foundation's text when it exists. Builds on the
[evidence-based hardening plan](yellowback-evidence-based-hardening-plan.md) ("the hardening plan",
revision 1) and the delivered [v3 design](yellowback-v3-development-plan.md) ("v3", revision 4);
both still apply where this plan does not amend them. Items are numbered **U-\*** (decisions),
**O-\*** (owner and Foundation decisions), **A-\*** (assumptions), and phases **P0–P8**.

## 0. Assumptions about the Foundation's primitive

Stated once, numbered, each with what happens if the Foundation decides otherwise. Where this plan
says "the primitive", it means §3 as assumed here.

| # | Assumption | If the Foundation differs |
|---|---|---|
| A-1 | The primitive is a **vault output** with unlock, cancel and owner branches, parameterised by a signer set, a delay and an owner key (§3.1) | a different template changes §3.1 and the wallets' vault recognition; nothing in the module |
| A-2 | **Signer sets are a consensus object** with bonds, threshold, cancel, rate limit, slashing and liveness (§3.2–§3.7) | if sets are plain multisig, rotation, rate limit and slashing move into each application, and the bridge is no longer module-free; the plan would be re-cut |
| A-3 | **BIP68 / CSV** relative timelocks are part of it (§3.3) | if absolute CLTV only, intents carry an explicit maturity height set at creation; weaker but workable |
| A-4 | The primitive carries an **opaque application tag** and a compile-time **module table** (§3.8) | if declined (O-12), YED runs the fallback of §5.4: collateral in consensus, dollar rules in the overlay |
| A-5 | The bridge signer shape is the Foundation's (O-9); this plan designs for **both** the single-relayer-plus-challengers and the 9 / 6 / 7 rows (§4.2) and tests both | none: whichever they pick is a parameter row |
| A-6 | Opcodes are allocated above `OP_NOP10`, gated on one new branch ID, on both node lines (§3.9, §8) | an opcode allocation of theirs is adopted as given, never `0xbb`–`0xbf` |
| A-7 | R1–R3 are firm (O-1) | if R2 is relaxed, the ZK path of §14 is reconsidered for the bridge only; YED is unaffected |

What this plan shows the Foundation: the primitive of §3 as a complete, testable spec; the bridge
running on it with zero application code in consensus (§4); and a second application that needs
exactly one registered module and why (§5). P2 delivers the primitive with **no application** on
both node lines first, so the Foundation can evaluate the generic part on its own.

**The premise.** The Ycash Foundation has set three requirements for a bridge, which the owner
has confirmed as firm and as covering Yellowback's collateral too (O-1). In this plan's words:

- **R1, Ethereum-failure tolerance.** Ycash keeps working, unchanged, if Ethereum stops, forks or
  the contract disappears, and vaulted YEC stays recoverable.
- **R2, rules independence.** Ycash consensus never reads Ethereum data or state. The Ethereum
  contract may carry Ycash identifiers but never interprets them. An upgrade on either chain
  cannot break the other's rules.
- **R3, miners enforce, miners do not vote.** Every bridge rule on Ycash is a consensus rule that
  every full node checks; miners keep only ordinary transaction selection.

The Foundation has also expressed a design preference: the consensus change should be a generic
lock and unlock facility, agnostic as to application, with wYEC as one application of it and YED
as a possible other.

**The owner's position.** Yellowback is one collateralised dollar on Ycash, not a toolkit. The
dollar's rules (who may mint, at what price, who may take a bad vault's collateral) must be checked
by every full node, not by pools that opt in. Price attestation stays **multi-party** (bonded
attestors, a bond-weighted quantile), whatever signer shape the Foundation chooses for its bridge.

**The reconciliation, in one table** (agreed 2026-10-05):

| | Bridge (wYEC) | Dollar (YED) |
|---|---|---|
| Uses the generic vault | yes | yes |
| Uses a registered signer set | guardians | attestors |
| Uses delay, cancel, cap, slashing | yes | yes, for the claim path |
| Needs consensus to know the application | **no** | **yes**: the rule module |

**Reading map.** §0 the assumptions. §1 the decision in one page. §2 R1–R3 as design rules. **§3 the primitive: what
is generic, element by element, each with its tier and why no cheaper tier does.** §4 the bridge
as an application with no module. §5 Yellowback as an application with a module. §6 what the
upgrade removes from v3 and what closes by construction. §7 the hardening plan: kept, reshaped,
retired. §8 activation plumbing on both node lines. **§9 the working rules that change
(AGENTS.md amendments, proposed).** §10 tier, trust statement, what is given up. §11 threat rows.
§12 sequencing. §13 decision record. §14 rejected.

---

## 1. The decision in one page

1. **The primitive is the Foundation's and it knows no application.** A vault output, registered
   signer sets with bonds, a relative timelock, a cancel branch, a rate limit, equivocation
   slashing, a liveness test, and an opaque application tag. Script gains two opcodes. Nothing in
   it says "price", "dollar", "Ethereum" or "burn". (U-1)
2. **The bridge is a script template on the primitive and nothing else in consensus.** Lock to a
   vault; unlock by the guardian set after a delay unless a member cancels; rate-limited; owner
   recovery on guardian silence or a long timelock. The Foundation's preferred single-relayer plus
   challenge-window shape and the owner's 9-of-6 shape are **parameter choices of the same
   primitive** (§4.2). Everything that makes it a bridge is in the contract and the daemon. (U-2)
3. **Yellowback is a second application, and the only one that registers a rule module.** Its
   vaults, attestor set, claim delay, cancel, cap and slashing are the primitive's. Its dollar
   rules (mint, price, ratio, supply, transfer, claim-by-burn) are a module the upgrade ships,
   invoked by consensus only for vaults tagged `YED`. That module is the delivered v3 overlay's
   rule set with its enforcement machinery removed. (U-3)
4. **Why the module exists.** A dollar's safety rule is "the spender burned this vault's debt at
   an attested price". That is a statement about ledger state, not about signatures. An agnostic
   primitive cannot check it; a bonded set signing it would make the price oracle a custodian
   (v3 §1.6 forbids exactly that). The module is the smallest thing that gives YED full-node
   verification. (U-4)
5. **R3 is met for both.** Every bridge rule is the primitive. Every YED rule is the primitive or
   the module. Pool signalling, lock-in, the sunset, the valve, the ENFORCEMENT halt and VOID
   verdicts cease to exist. (U-5)
6. **R1 is the primitive's liveness test.** A set that posts nothing for a window is dormant, a
   Ycash-native fact; the owner branch of every vault opens. A dead Ethereum, a lost contract and
   a vanished guardian set all look the same to Ycash. (U-6)
7. **The fallback is built in.** If the Foundation ships the primitive and declines the module,
   the bridge is unchanged and YED runs with its collateral in consensus and its dollar rules in
   today's overlay (option A1 of the 2026-10-05 discussion). Same vaults, same attestors, same
   wallets. (U-7)
8. **The hardening gates still come first.** The upgrade fixes every enforcement finding. It does
   nothing about one pool setting every median, bad-debt classes, thin venues or quote
   availability. A dollar rule in consensus that mints on a bad price is worse than an overlay
   rule that does, because no renewal can switch it off. (U-8)

---

## 2. The three requirements as design rules

| Requirement | What it forbids | What it forces | Where it lands |
|---|---|---|---|
| R1 | any Ycash rule whose evaluation needs Ethereum liveness; collateral whose only exit is an Ethereum event | an owner branch on every vault, opened by set dormancy, set wind-down or age | primitive: liveness, `OP_CHECKSETDORMANT`, CLTV |
| R2 | ZK proofs of Ethereum headers; posted Ethereum checkpoints; any consensus-read field encoding Ethereum state; a contract that verifies Equihash or Yellowback payloads | every authorisation is a signature under a key registered on Ycash; identifiers crossing the bridge are opaque bytes on both sides | primitive: signer sets, the opaque application tag; contract: `bytes32` lock ids |
| R3 | pool signalling and lock-in, the valve, the ENFORCEMENT halt, the sunset, mined-but-VOID transactions, template policy carrying rule content | a network upgrade: new branch ID, rules in block validity | §8 |

"Neither chain's upgrade can break the other's rules" is structural: the Ycash side knows a set of
secp256k1 keys; the contract knows the same keys. Either chain changes everything else freely.

---

## 3. The primitive

Every element: what it is, the tier it lands on, why no cheaper tier does. The ladder vocabulary
is README.md's, applied **inside** the upgrade: a change that can be a script template is not an
opcode; one that can be an opcode is not a new transaction field; one that can be per-vault state
is not global state.

### 3.1 The vault output

A P2SH output whose redeem script is the **vault template**: an unlock branch, a cancel branch and
an owner branch, parameterised by a set id, a delay, and an owner key, with a 4-byte **application
tag** pushed and dropped (consensus reads the tag only to decide whether a registered module must
also validate the spend, §3.8). The template is fixed by the upgrade so every node, wallet and
indexer recognises a vault by shape, the way v3 recognises its vault script (`script.cpp`).

*Tier:* script template, no opcode of its own. *Why not cheaper:* a template is the cheapest
thing there is.

### 3.2 Signer sets

A consensus object, keyed by `setId`, created by a `SET_CREATE` transaction and populated by
`SET_JOIN` transactions that lock a bond (a P2SH CLTV output, as v3's attestor bond). A set has:

| Field | Meaning | Bridge value (owner's O-2) | Bridge value (Foundation's single relayer) | YED attestors |
|---|---|---|---|---|
| `seats` | maximum members by bond | 9 | 1 | `N_SLOTS` 9 |
| `unlockThreshold` | signatures to spend the unlock branch | 6 | 1 | n/a (YED claims are not set-signed; §5.3) |
| `cancelThreshold` | signatures to spend the cancel branch | 1 | 1 of the **challenger** set (a second set, bonded, open) | 1 |
| `slashThreshold` | signatures to burn a member's bond on a contested cancel | 7 | challenger-set majority | 7 |
| `rateLimit` | value the set may unlock per `rateWindow` | `RELEASE_CAP_BPS` of locked value | same | n/a |
| `livenessWindow` | blocks without any member act before the set is DORMANT | `GUARDIAN_DORMANCY_BLOCKS` | same | `DORMANCY_BLOCKS` |
| `bondMin`, `bondLock`, `maturity` | as v3's attestor bond | ≥ attestor bond | high (one bond backs everything) | `BOND_MIN` |

A member's acts are: a signature on an unlock, a signature on a cancel, a `HEARTBEAT`. Membership
changes (join, withdraw at bond locktime, removal by `slashThreshold` with the bond returned, O-6)
are transactions, so the set rotates without touching any vault.

*Tier:* new consensus state (a table in the chainstate, UNDO-covered like v3's `Attestors`).
*Why not cheaper:* a `CHECKMULTISIG` over fixed keys cannot rotate, cannot be rate-limited and
cannot be slashed; a set referenced by id can. This is the one genuinely new consensus object and
it is shared by both applications.

### 3.3 Relative timelock

BIP68 sequence semantics and `OP_CHECKSEQUENCEVERIFY`, which Zcash and Ycash never adopted. The
unlock branch of a vault's **intent output** must age `delay` blocks before the set may spend it.

*Tier:* opcode plus `nSequence` semantics, exactly Bitcoin's. *Why not cheaper:* CLTV is absolute
and an intent's height is not known when the vault is created. *Why not bigger:* the design is
twelve years old and audited everywhere; it is the lowest-risk consensus change in this document.

### 3.4 The cancel branch

The intent output's second branch: spendable **before** maturity by `cancelThreshold` signatures
of the set (or of the challenger set, §4.2), back into a vault of the same owner. A cancel is a
native act with no reason field. Consensus never learns why.

*Tier:* template branch over `OP_CHECKSETSIG`. *Why not cheaper:* a cancel by a fixed key is a
single point of failure; a cancel by any bonded member is the pasted feedback's "one honest
watcher stops the theft".

### 3.5 Rate limit

Per set: the sum of values unlocked over the trailing `rateWindow` may not exceed `rateLimit`,
expressed as basis points of the value locked under that set at the window start. An unlock that
would exceed it is invalid.

*Tier:* consensus state (a rolling sum per set). *Why not cheaper:* a per-vault cap does not bound
the aggregate (hardening D-RD-INF-4); only the set knows its aggregate.

### 3.6 Slashing

Two signatures by one member over two different spends of **the same outpoint** is equivocation,
provable from the two signatures alone: the member is EJECTED and the bond is **burned**. This is
the slashing v3 could not have without a network upgrade (v3 §1.7). A contested cancel (the
Foundation's challenge window) is resolved by `slashThreshold` signatures of the relevant set
naming the member to slash; consensus records the slash, not the reason.

*Tier:* consensus rule over set state. *Why not cheaper:* without slashing a set's bond is a
deposit, not a stake, and the Foundation's single-relayer shape is unsafe.

### 3.7 Liveness and dormancy

A set is DORMANT when fewer than `cancelThreshold` members have acted in `livenessWindow`. A
member is DORMANT when it has not acted in that window (v3's per-attestor dormancy, S15). The
owner branch of every vault under a DORMANT set is open (`OP_CHECKSETDORMANT`). This is R1.

*Tier:* consensus state already needed by §3.2, plus one opcode.

### 3.8 The application tag and module registration

The tag is 4 opaque bytes. Consensus treats a vault as **untagged** (the primitive alone governs
spends) unless the tag matches a module registered by the upgrade, in which case the module's
`ValidateSpend` and `ValidateCreate` also run. Registration is a compile-time table in the upgrade
(`{ 'YED\0' → yellowback::Module }`), not a transaction: adding a module is a network upgrade,
which is the Foundation's review point.

*Tier:* one table and two virtual calls. *Why it exists:* §1.4. *Why it is still agnostic:* the
primitive runs identically for every tag; a module can only add constraints, never remove one.

### 3.9 Script additions, in full

| Opcode | Semantics |
|---|---|
| `OP_CHECKSEQUENCEVERIFY` | BIP112 |
| `OP_CHECKSETSIG` | pops `setId`, `k`; verifies `k` compact ECDSA signatures by distinct current members of `setId` over the ZIP-243 sighash; records them for §3.6 |
| `OP_CHECKSETDORMANT` | pops `setId`; true iff the set is DORMANT at the spending height |

Three opcodes from the unassigned range above `OP_NOP10`, gated on the branch ID. Bytes
`0xbb`–`0xbf` are **not** used (`docs/mapping.md` §2: on Ycash they are `BAD_OPCODE`, and the
DigiByte association would mislead).

---

## 4. Application 1: the bridge (wYEC), no module

### 4.1 On Ycash

| Step | Transaction | Rule |
|---|---|---|
| Lock | vault output, tag `WYEC`, set = guardians, `destination 32` opaque in an `OP_RETURN` (an Ethereum address the wallet writes and consensus never reads) | primitive only |
| Intent | the guardian set (per `unlockThreshold`) moves vault value into an **intent output** naming `recipient` (Ycash) and `amount` | primitive: `OP_CHECKSETSIG`, rate limit checked here |
| Release | after `delay`, the set spends the intent to `recipient`; change re-locks | primitive: `OP_CHECKSEQUENCEVERIFY`, `OP_CHECKSETSIG` |
| Halt / challenge | before `delay`, `cancelThreshold` members spend the intent back to a vault | primitive: cancel branch |
| Recovery | owner spends a vault iff the set is DORMANT, or a `SET_WINDDOWN` is final, or `height ≥ lockHeight + BRIDGE_MAX_AGE` and no intent names it (O-5) | primitive: owner branch, `OP_CHECKSETDORMANT`, CLTV |
| Griefer removal | `slashThreshold` members post `SET_REMOVE seq`; bond returned (O-6) | primitive |

There is no `yed_*`-style bridge RPC in consensus terms; the node exposes the primitive
(`set_list`, `set_getinfo`, `vault_list tag=WYEC`, the signing RPCs `set_signunlock`,
`set_signcancel`, `set_heartbeat`, which keep the key on the node as `yed_signattestation` does).

### 4.2 The two signer shapes

The Foundation's bridge prefers a **single relayer with a challenge window and slashing**; the
owner's O-2 chose **9 seats, 6 to unlock, 7 to slash**. Both are rows of §3.2:

| | Single relayer + challengers | 9 / 6 / 7 guardians |
|---|---|---|
| Who unlocks | one bonded relayer | 6 of 9 |
| Who cancels | any bonded challenger (an open second set) | any 1 of 9 |
| Who slashes a bad unlock | challenger-set majority after a contested cancel | 7 of 9 |
| Theft needs | the relayer plus every challenger silent for `delay` | 6 colluders plus the other 3 silent |
| Liveness needs | one party | 6 parties |
| Capture cost | one bond (so `bondMin` must be large) | 6 bonds |
| Matches Foundation preference | yes | no |

The owner's preference for multi-party applies to **price attestation** (§5.2), which is a different
set with a different job. The bridge's shape is the Foundation's call (O-9, open); the primitive
supports either, and the daemon differs only in configuration.

### 4.3 Off Ycash: the `wyec/` repository

Its own repository on `main`, net new, no reference, no baseline. The contract (Solidity, Ethereum
L1 first, O-4): an ERC-20 with `mint(lockId, amount, to, sigs[])` under the same guardian keys,
`lockId` stored as `bytes32` and never parsed (R2); `burn(amount, ycashRecipient)` emitting the
event the daemon turns into an intent; key rotation and pause by threshold. The daemon follows
Ycash by RPC and Ethereum by JSON-RPC (finalised blocks only), co-signs mints for observed locks,
posts intents for finalised burns, co-signs releases after `delay`, cancels any intent it cannot
match to a burn, and heartbeats. Contract audit is external and on the critical path.

---

## 5. Application 2: Yellowback (YED), with the rule module

### 5.1 On the primitive

| YED thing | Primitive element |
|---|---|
| Vault | the vault template, tag `YED\0`, set = attestors, owner branch at `lockHeight` (CLTV) as today |
| Attestor registry, bonds, maturity, dormancy, revival | a signer set (§3.2, §3.7) |
| Attestor equivocation (two prices, one height) | **stays in the module**: it is about signed prices, not outpoints; the bond burn uses §3.6's mechanism |
| Claim path delay and cancel | an intent output: the claimant moves the vault into an intent carrying its burn; after `CLAIM_DELAY` the claimant spends it; before, any attestor may cancel (a wrong-price claim is stopped by one honest attestor) |
| Cap | the set's `rateLimit` bounds claims per window; the **supply cap** is module state (§5.3) |

### 5.2 Price attestation stays multi-party

Unchanged from v3: `N_SLOTS` bonded attestors, bundles carried in the transaction, a bond-weighted
one-sided quantile, `pMint = min(xMint, aMint)`, `pClaim = max(xClaim, aClaim)`, the pins, the
arming bar (hardening H-2: seven matured distinct bonds). The attestor set is the signer set of
§3.2 with `unlockThreshold` unused: attestors never spend anything; they sign prices that the
module reads. The owner's position stands: a single price signer is not a price.

### 5.3 The module

`yellowback::Module` is the delivered `src/yellowback/` rule set, invoked by consensus for every
transaction that creates or spends a `YED`-tagged vault or carries a Yellowback payload:

| Stays, as consensus | Leaves (§6) |
|---|---|
| MINT-1..10, PRICE-2, the pins, ARM-1/2, AFEE | ACT-1..6, lock-in, `SIGNAL_WINDOW` |
| RED-1..5 (now: the intent's burn and price, checked at intent creation; the spend after delay re-checks nothing but the delay) | the valve, note cap, odometer |
| TRANSFER, the token index, `supplyCents`, HALT-1/2 (NO_PRICE, GLOBAL_RATIO, unarmed), MINT-6 cap gate | ENFORCEMENT halt, abandonment, catch-up suppression |
| NOT-1 emergency notice, EQV-1 price equivocation, REV-1 | VOID verdicts, `voidReason`, TPL-1/2, MP-1's rule content |
| SNAP, `Snapshots[h]`, the golden vector and the Python model (N23) | the anyone-can-spend claim branch (A-5): the claim is an intent on the primitive |

A failing mint is an invalid transaction. A failing claim intent is invalid. There is no
"mined but VOID". The module's state (`Snapshots`, the token index, `BundleLog`, `Notices`)
becomes chainstate, UNDO-covered, and the state hash joins the block-validity check it already
mirrors on the devnet (`ybcal devnet validate --strict`).

### 5.4 The fallback (A1)

If the Foundation declines the module: the `YED` tag is unregistered, vaults are governed by the
primitive alone (owner branch at `lockHeight`, claim intents under the attestor set's delay and
cancel with **no** burn check), and the delivered overlay keeps MINT, TRANSFER, the index and the
claim's burn rule at today's tier. Collateral is consensus-safe; the peg's enforcement is as
today. No vault, wallet or attestor change between the two outcomes.

---

## 6. What the upgrade removes from v3, and what closes by construction

| Removed | Was | Why it goes |
|---|---|---|
| Pool signalling, ACT-1..6, lock-in, `SIGNAL_WINDOW`, `activationThreshold` | v2 L3, hardening H-7 | activation is a height in `chainparams.cpp` |
| `ENFORCE_UNTIL_HEIGHT`, the sunset, renewal releases, W18/W19 | v3 revision 4 | a consensus rule has no sunset |
| The work valve, note cap, persistence, odometer | v2 L7, hardening H-6, F-3, audit A-6 | no enforcing minority to protect |
| ENFORCEMENT halt, catch-up suppression, abandonment | W21 | nothing to abandon |
| VOID verdicts, `voidReason`, MINTPOL's VOID mirror | v2 V3 | an invalid transaction is not mined |
| TPL-1/2, MP-1's rule content | v2 | mempool and template follow validity |
| The anyone-can-spend claim branch | `script.cpp:90`, audit A-5 | the claim is a primitive intent |
| Frozen-file zero-delta checks, hook budgets | v3 §4.1, gate G-9 | consensus files change by design; replaced by the review gate (§7) |

Closes by construction: hardening B-3, B-6, C-8, C-9; audit A-5, A-6; the "majority pool leaves"
and "spurious lock-in" rows. B-1's enforcement leg closes; its oracle leg does not.

Stays exactly as delivered: payloads (new types added), the carrier, PRICE-2, the pins, the
emergency notice, the `yed_*` surface (plus the primitive's `set_*`/`vault_*` RPCs), the Python
model and golden vector discipline, the devnet and role regtest, chain-viz, lightwalletd's
streamer, YEW, x402, yb-calibration.

---

## 7. The hardening plan under this idea

| Item | Fate | Note |
|---|---|---|
| H-1 minting requires ARMED | **kept** | the oracle leg of B-1; a hand-built unarmed mint is invalid |
| H-2 arming bar 7, G-5 | **kept** | applies to the attestor set; the bridge set's bar is O-9 |
| H-3 ratios on the worse window | **kept** | |
| H-4 fee split | **kept** | a bridge fee is a new line (O-2) |
| H-5 class A only | **kept** | B/C stay off; a pre-maturity rule is now a module change, not a script change |
| H-6 valve | **retired** | |
| H-7 two-window lock-in | **retired** | |
| H-8 START_HEIGHT after commitment | **reshaped** | the activation height is set by the gate-passing release; the commitment sought is node-operator and exchange **upgrade adoption** (G-4) |
| H-9.1 sunset stand-down | **retired** | |
| H-9.2 wallet deadlines, renew | **kept** | sunset warning dropped |
| H-9.3 client plausibility bounds | **kept** | |
| H-10 class-A cap gate | **kept** | module state |
| H-11 halt 300 %, recap 600 % | **kept** | |
| H-12 `maxMint` $2,500 | **kept** | |
| F-1 wallet spent-tracking, F-2 agent configs, F-5 heights unset | **kept** | |
| F-3 odometer | **retired** | |
| F-4 | **reshaped** | plausibility kept, sunset warning dropped |
| G-1, G-2, G-3, G-5, G-7, G-8, G-10 | **kept** | G-10 adds the primitive drills (§12) |
| G-4 coalition commitment | **reshaped** | upgrade adoption ≥ 70 % of blocks and the listed exchanges before the height |
| G-6 valve | **retired** | |
| G-9 frozen files | **reshaped** | the **consensus review gate**: every changed line under `src/consensus/`, `src/script/`, `main.cpp`, `src/primitives/`, both lines, reviewed by two people independent of the author, with the four-part check in the PR body |
| §6 trust statement | **rewritten** | §10 |
| §9 work plan | H0, H1, H3-a, H3-c, H4, H5 kept; H2 and H3-b's lock-in/sunset parts dropped; H6–H8 become P6–P8 |

---

## 8. Activation plumbing on both node lines

The four-part check, once for the mechanism:

> DigiByte activates in `src/consensus/params.h` using BIP9 versionbits (`docs/mapping.md` §4).
> The Ycash equivalent is a height-gated network upgrade (`enum UpgradeIndex`,
> `NetworkUpgradeInfo[]` in `src/consensus/upgrades.cpp`, `vUpgrades[].nActivationHeight` in
> `src/chainparams.cpp`, `NetworkUpgradeActive(...)` at each check site), which lacks signalling by
> design. So the adaptation is `UPGRADE_VAULT` with a fresh `nBranchId`, heights set by the
> gate-passing release, regtest via `-nuparams`, the three opcodes and the set table gated on it,
> and the YED module registered under it. Tier: network upgrade, by R3; no cheaper tier meets R3.

| Site | ycash-dd (v4.5.0 lineage) | ycash6 (6.20.0, Zcash 6.x lineage) |
|---|---|---|
| Upgrade table | `src/consensus/upgrades.cpp`, after Canopy | after `0x5437f330`, before the `0xffffffff` sentinel |
| Chain params | `vUpgrades[UPGRADE_VAULT]` main/test/regtest | same |
| Sighash | ZIP-243 bound to `consensusBranchId`: every signer presents the new ID | same; `librustzcash6` gains the `BranchId` and **stops being zero-delta**; `ycash6/Cargo.toml` repoints at `boyfromcave/librustzcash6` |
| Script | three opcodes in `src/script/interpreter.cpp` behind the branch ID; the vault template in `src/script/standard.cpp` | same |
| Consensus state | the set table and rate sums in the chainstate (`CCoinsView` extension on ycash-dd; the 6.x equivalent) | `docs/mapping.md` §19 |
| Check site | `main.cpp` `ConnectBlock`: set state transitions, module dispatch by tag | the 6.x equivalents |
| Clients that sign | YecWallet, YEW (Rust signer), yolo (branch ID in templates), x402 (verifier), the Python `test_framework` | same |
| Tooling | `make diff` budgets re-based; the frozen list becomes the review-gate list | same |

Both lines stay in step; branch ID and heights are identical. The release line is `ycash6`,
version **6.22.0** (O-7).

---

## 9. The working rules that change (AGENTS.md amendments, proposed)

The guiding principles stand: Ycash is risk-averse, the shielded pool's soundness rests on code
few people fully understand, and every change takes the smallest footprint that works. What
changes is that a network upgrade is now the owner's and the Foundation's decided tier, so the
rules written to keep the fork **off** that tier are replaced by rules that keep it **small on**
that tier.

| AGENTS.md rule today | Amendment |
|---|---|
| Prime directive: "Prefer the cheapest tier that works: Tier 0 … over a soft fork, and a soft fork over a coordinated network upgrade" | **"The tier is a network upgrade, by Foundation requirement R3 and owner decision O-1. Within it, prefer a script template over an opcode, an opcode over a transaction field, per-vault state over global state, and the primitive over the module. Record what was given up."** |
| Rule 2: frozen-file zero-delta checks against `yellowback-v3-baseline` | **retired** for `src/consensus/`, `src/script/`, `main.cpp`, `src/primitives/`; replaced by the consensus review gate (§7, G-9). The `-legacy` line budgets stay, as a size measure, not a gate |
| Rule 2: "the `yed_*` RPC surface is the sole interface between the node and either client" | **extended**: the primitive's `set_*` and `vault_*` RPCs join it; the bridge daemon uses only those plus stock RPCs; nothing else changes |
| Rule 3: "DigiByte's DD opcodes … a verbatim port compiles and is consensus-dead" | **stands**, and gains: the three new opcodes are allocated above `OP_NOP10`, never `0xbb`–`0xbf`; the mapping §2 row is the reason |
| Rule 4: the four-part check, "which tier does W land on, and why won't a cheaper tier do?" | **stands**, with the ladder of the prime directive amendment; a consensus PR without it is rejected at the review gate |
| Rule 7: "Consensus code is not refactorable … Do not tidy, rename, or improve surrounding code" | **stands, verbatim.** The upgrade adds; it never tidies |
| "Two node lines … a shared Yellowback defect or rule change is made on both lines together" | **stands**; the primitive, the module and the branch ID are one change on both lines |
| `librustzcash6` "zero-delta until the port needs it" | **it now needs it**: the branch ID |
| Component rules (yolo, chain-viz, x402, YEW "never needs a node change") | **stand**; they need the branch ID for signing or verifying, which is a client update, not a node change they ask for |
| Memory rule `v3-comparison-base` (frozen checks vs the tag) | **retired with rule 2's frozen check**; `feature/yellowback-sf` remains no comparison base |

Applied to AGENTS.md when this plan's first implementation chunk opens (P2), not before: until then the delivered forks are still measured by the rules as written.

---

## 10. Tier, trust statement, what is given up

**Tier.** Network upgrade, by R3, O-1 and the Foundation's own preference for a generic primitive.
Within it: three opcodes, one consensus object (signer sets with rate sums), one template, one
module table, one module. Recorded in `docs/mapping.md` (new §22) so no later session re-litigates
it.

**Trust statement (replaces hardening §6).** The product promises, in these words, and no more:

- **Every Yellowback and every bridge rule is a Ycash consensus rule, checked by every full node.**
  There is no pool that enforces, no pause, no abandonment.
- YED is created only when both a hashpower majority and a bonded attestor majority agree on the
  price. Neither alone can mint against a price it sets. A single signer is never a price.
- Collateral behind YED is locked for 30 to 90 days and returned to the owner who redeems before
  `lockHeight + 30 days`; after that, anyone may close the vault by paying its debt in YED, after
  a delay during which any honest attestor can stop a claim at a wrong price.
- **Wrapped Ycash is a federated bridge.** YEC behind wYEC is released only by its bonded signer
  set, after a delay, within a per-window cap, and only while no bonded watcher has cancelled.
  Ycash never reads Ethereum. If the signers go silent or wind down, every depositor recovers
  their own YEC with no counterparty. Bonds are burned for signing conflicting releases.
- Nothing in either application touches the shielded pool.

**What is given up:**

1. The soft-fork tier and everything built for it (§6), delivered and calibrated, then retired.
2. A trustless bridge release path: R2 forbids it; the bridge is federated and says so.
3. Renewal as the parameter mechanism: parameters move inside consensus-bounded ranges by set
   threshold signal (O-8), or by upgrade.
4. `librustzcash6` as a zero-delta fork.
5. The frozen-file invariant as a one-command proof of consensus safety, replaced by review.
6. Agnosticism in full: one registered module. The primitive stays agnostic; the node is not.

---

## 11. Threat model rows (added to v3 §8.2 and hardening §5)

| Threat | Outcome | Mitigation | Residual |
|---|---|---|---|
| Bridge set unlocks without a burn | theft bounded by `rateLimit` per window, only if no watcher cancels within `delay` | delay, cancel, rate limit, slashing, distinctness (G-5-style, O-9) | a captured unlock set with every watcher silent steals one window's cap; stated in §10 |
| One watcher cancels repeatedly | releases stall per cancel | `SET_REMOVE` by `slashThreshold`, bond returned (O-6) | delay, never loss |
| Ethereum halts, forks, contract lost | no mints, no burns; signers heartbeat or wind down | owner branch (R1) | wYEC on a dead chain is the Foundation's wind-down policy |
| Ethereum reorgs a burn after release | the daemon acts on finalised blocks only; `delay` exceeds finality many times | daemon policy | a finality failure is a bridge loss, bounded by the cap |
| Signer key compromise | one seat's acts | threshold, delay, cancel, ejection | one bond |
| A claimant's intent at a wrong price | any attestor cancels within `CLAIM_DELAY` | §5.1 | an attestor set captured **and** a pool majority **and** every honest attestor silent: the v3 collusion row, now with a delay in front of it |
| The majority pool censors cancels | ordinary censorship (R3) | `delay` long enough that a cancel reaches a block with high probability; measured (G-11) | a majority censoring every cancel for a full delay enables the theft rows |
| A module bug | an invalid YED transaction accepted, or a valid one refused, by every node at once | the golden vector and the Python model (N23) in CI; the state hash in block validity; the review gate | a consensus bug is a chain halt or a fork; this is the cost of full-node verification and is why the module is the delivered, calibrated rule set and not new code |

---

## 12. Sequencing

| Phase | Content | Depends on |
|---|---|---|
| **P0** decide | **done in part (2026-10-05):** this plan promoted with §0's assumptions; the AGENTS.md amendments of §9 land with it. **Open:** the Foundation's written primitive (replaces §0's assumptions one by one), O-9, O-12; the O-8 design note | — |
| **P1** harden | hardening H0, H1, H3-a, H3-c, H4, H5 as written minus §7's retired items; G-1, G-2, G-3, G-5, G-7, G-8 read | hardening plan |
| **P2** primitive | both lines: `UPGRADE_VAULT`, branch ID, BIP68/CSV, `OP_CHECKSETSIG`, `OP_CHECKSETDORMANT`, the set table and rate sums, the vault template, `SET_*` transactions, the module table (empty), the primitive's RPCs; `librustzcash6` branch ID; test framework ID; unit and functional suites for the primitive **with no application** | P1 binaries |
| **P3** bridge template | the `WYEC` template and intent flow on the primitive; a bridge persona in the role regtest with a local Ethereum (anvil); both signer shapes exercised | P2 |
| **P4** YED module | `yellowback::Module` from the delivered rule set: §6 removals, VOID → invalid, the claim as an intent, module state into chainstate, golden vector regenerated once with the diff explained, Python model parity | P2 |
| **P5** wyec repo | contract (external audit), daemon, devnet preset | P3 |
| **P6** clients | YecWallet, YEW, lightwalletd, chain-viz (set and vault panels), x402 and yolo (branch ID) | P2 for the ID; P3/P4 for the surface |
| **P7** gates | kept gates; reshaped G-4, G-9; **G-11** cancel inclusion latency on the real block sequence; **G-12** primitive drills on testnet or a public multi-operator devnet: cancel, equivocation slash, dormancy recovery, wind-down, both bridge shapes, a wrong-price claim cancelled | everything |
| **P8** release | `ycash6` 6.22.0 and `ycash-dd` in step; activation height and the later bridge enable height (O-3) set by this release; the contract deployed with the registered set | P7 |

P1 and P2 run in parallel worktrees; P2 does not touch P1's files until P1 merges. P3 and P4 are
independent and run in parallel. P5's contract audit is external and on the critical path.

**Budget.** No line budget on the consensus files under the review gate; a size estimate instead:
the primitive ≈ 1,500 lines per node line (BIP68/CSV is a known-size port from Bitcoin ≈ 300;
the set table, opcodes, template and transactions the rest); the module is the delivered
`src/yellowback/` minus ≈ a third (§6) plus the intent flow ≈ 400. The bridge adds nothing to the
node beyond the template.

---

## 13. Decision record

**Owner, 2026-10-05, under revision 2** (each put with the recommendation first; every
recommendation taken), re-read under revision 3:

| # | Decision | Decided | Under revision 3 |
|---|---|---|---|
| O-1 | Scope and firmness of R1–R3 | both mechanisms, R1–R3 firm | stands; "both" now means the primitive governs both and the module gives YED full-node verification |
| O-2 | Bridge set 9 / 6 / 7, bond ≥ attestor, bps fee | taken | one of the two rows of §4.2; the Foundation's single-relayer row is the alternative (O-9) |
| O-3 | Bridge enables at a later height in the same release | taken | stands (`WYEC` tag live at the second height) |
| O-4 | Ethereum L1 first | taken | stands |
| O-5 | `BRIDGE_MAX_AGE` recovery | yes | stands, on the owner branch |
| O-6 | Griefer removal by threshold, bond returned | taken | stands as `SET_REMOVE` |
| O-7 | Version 6.22.0 | taken | stands |
| O-8 | Bounded, set-signalled parameters | taken | stands; the signal is a set act in the primitive |

**Owner, 2026-10-05, under revision 3:**

| # | Decision | Decided |
|---|---|---|
| O-10 | The path: agnostic primitive, two applications, one registered rule module for YED | **yes** (the table in the preamble) |
| O-11 | Price attestation stays multi-party regardless of the bridge's signer shape | **yes** |

**Open, the Foundation's:**

| # | Decision | Recommendation |
|---|---|---|
| O-9 | Bridge signer shape: single relayer + challenger set, or 9 / 6 / 7 | the primitive supports both; if single relayer, `bondMin` must cover one window's `rateLimit` in full, so a theft never pays |
| O-12 | Acceptance of the module table (§3.8) as part of a generic primitive | the argument of §1.4; the fallback of §5.4 if declined |
| O-13 | Numeric values: `delay` per application, `rateWindow`, `rateLimit`, `livenessWindow`, `BRIDGE_MAX_AGE`, `CLAIM_DELAY` | `ybcal` derives them in P1/P4; starting points one day, one week, and a cap sized to the window's worst case |

---

## 14. Considered and rejected

- **ZK proof of the Ethereum sync committee as the release authority.** By R2. Also weaker than it
  looks (no slashing for a false header) and a proof-system mismatch with what ycashd verifies.
- **One application-aware consensus module for both** (revision 2). Rejected by the Foundation's
  preference for an agnostic primitive; the bridge needs no module, so the shared module was
  carrying bridge logic that belongs in a template.
- **YED's dollar rules enforced by the attestor set signing claims** (option A2). Turns the price
  oracle into a custodian; v3 §1.6 forbids it and the owner declined it.
- **A fully agnostic node with YED at the overlay tier** (option A1) as the primary path. It is the
  fallback (§5.4), not the plan: it leaves the peg's enforcement with opt-in pools.
- **Attestors as bridge signers.** Different jobs, different failure modes; v3 D-1 stands.
- **Guardian multisig in the vault script.** Cannot rotate, cannot be rate-limited, cannot be
  slashed.
- **Depositor veto on bridge releases.** Once wYEC is sold the depositor has no claim.
- **Reusing `0xbb`–`0xbf` for the opcodes.** `docs/mapping.md` §2.
- **Keeping VOID semantics under consensus.** Exists only because non-enforcing miners exist.
- **A single price signer with a challenge window** for YED. A challenge needs a second opinion to
  exist; a quantile over nine bonded opinions is the challenge, every block.
