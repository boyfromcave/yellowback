# Yellowback per-vault cancel limit: design for owner approval

**Revision 1, 2026-10-13. Design only, with no code.** This is a follow-up to CAN-1 (audit 03/H-1, lane `yed-cancel`:
ycash-dd `fix/yed-cancel` @ `9683a0411`, ycash6 `fix/yed-cancel`, and the remedial report
`docs/remedial-action-reports/pending/HIGH-03-H-1-ycash-yed-claim-cancel-refund.md`). The owner decided on
2026-10-13 to ship CAN-1 now and to design a per-vault cancel limit as a separate consensus change, which this
document does. Sources: upgrade plan §3.4–§3.6, §11, §15.2–§15.6, §15.10 U-23/U-24 (as revised by the lane);
in-term claims plan §2 (D-IT-13/14) and §4; quantum plan D-Q-29..D-Q-31. Line citations are at the lane's
heads (`src/yellowback/state.cpp`, `params.cpp:110`, `module.cpp:46`).

---

## Owner decisions (2026-10-13)

The owner answered §6 on 2026-10-13. This design is **approved for implementation** with these choices:

| # | Question | Decision |
|---|---|---|
| 3 | Approach | **C2, escalating co-signed cancels (CAN-2)**, not C0 "always require two" |
| 1 | One free hold | **Accepted**: the first cancel on a vault needs one attestor; a lone seat can delay one liquidation about 12 h per vault per week |
| 2 | Cap | **`CANCEL_SIGNERS_MAX` = 5** (regtest 3) — **superseded by round 2: 4**, schedule 1, 2, 3, 4, 4, …; `CANCEL_QUIET` = 8,064 blocks (7 days; regtest 40) |
| 4 | Claimant's fees | **No repayment** by cancellers (C3 rejected) |
| 5 | Owner's residual | **Held** up to `CANCEL_QUIET`, or until the position closes (C5 / CAN-3) |
| 6 | Penalty | **Include now: C4b**. A cancel carries the canceller's signed price statement at the claim's reference height, and EQV-1 slashes a member whose regular attestation at that height carries a different price. This ships together with C2 and C5 rather than as a phase 2. |
| 7 | Unlock budget | **Left as is**: S-3 is unchanged and the primitive is not touched. Document R-1d and size the YED set's `rateLimitBps` with it in mind. |

## Owner decisions, round 2 (2026-10-13)

After the two-reviewer gate (both APPROVE the consensus soundness), the owner decided:

| # | Finding | Decision |
|---|---|---|
| R2-1 | R-1c leak: after `CANCEL_QUIET` a held residual was released even while the position stayed claimable (both reviewers) | After `CANCEL_QUIET` a held residual is releasable only if **no claim in that block could pass**: for every reference height `R` a claim may cite (`[max(H − REF_WINDOW, START_HEIGHT), H − 1]`) the position is not claimable at `Snapshots[R]` under the claim's own rule, judged fail-closed — an undefined price counts as claimable; path (a) is judged at xClaim (a claim's `pClaim = max(xClaim, aClaim)` ≥ xClaim when ARMED, and a claim may carry a bundle whose aClaim is that low); path (b) counts whenever `R` is ARMED and a notice of the position persists for `R`. Otherwise it waits until the position closes (redeemed, or claimed by a later release). Reads only the owner's own vault and notice; at most `REF_WINDOW` (40) snapshot reads per release. (The first implementation read only `Snapshots[H−1]` at its price; both reviewers found the gap and it was fixed the same day.) |
| R2-2 | Cap | `CANCEL_SIGNERS_MAX` = **4** (regtest stays 3): schedule 1, 2, 3, 4, 4, … |
| R2-3 | Review M-2 (coordinator) | A cancel counts its **distinct valid current-member** co-signatures and needs ≥ `required`; invalid or non-current entries are ignored rather than failing the cancel; a malformed blob still fails. Wallets add spare co-signatures. |

**Collusion threshold.** With the cap at 4, four colluding seats — about 27 % of the 15 — can veto one vault, or every
vault, indefinitely (was five, a third). That is the captured-set residual priced at four bonds.

**Honest owner after a wrong path-(b) claim.** A wrong path-(b) claim strips the vault to ~100 % at the claim's pClaim
(the claimant intent's value) and moves the RED-5 residual into the owner's residual intent. When it is cancelled the
re-created position is that stripped vault, which is claimable at most prices a claim may cite, so under R2-1 the
honest owner's residual stays held until the position closes: the owner must redeem (repaying the debt, the refunded
YED is the claimant's) to free it. Accepted (fail closed: the owner can always redeem).

Wallet fixes with them: `yed_signcancelcosign` co-signs only confirmed claims (A-6), looks its price guard up by key
(a rejoined member with a reused hot key), and reads one block-hash source; `yed_buildcancel` names the failing entry
and checks `PRICE_MAX`. Documented trade-offs: the C2/C4b co-signer limitation (members whose locked price at R clears
θ), membership from the in-block mirror, and the residual held for a campaign plus the quiet period.

**Implementation (2026-10-13, lane `fix/cancel-limit`, both node lines):** as specified, with the choices recorded in the
upgrade plan §15.10 ("The per-vault cancel limit"): one signature per co-signer is both the co-signature and the C4b
statement; the CANCEL_COSIGN payload body is empty (the count rides the carrier, so the set signature stays sign-once);
`IntentRecord` gains `claimRefHeight` as well as `heldBy`; every cancel, the first included, carries one statement.

Scope of the change: one module change on both node lines (C2 + C5 + C4b), plus attestor-agent support for gathering
co-signatures and price statements. It needs the consensus review gate (two reviewers), a golden regeneration under
the 03/T-1 process, and a yb-calibration T5 re-run before the release. It depends on HIGH-03-H-1 (CAN-1) and
MEDIUM-01-V-2 (ANYONECANPAY set signatures) having landed.

## 1. The threat

**Setting (after CAN-1).** Take a YED vault `V` with debt `D` that is claimable at height `h`: RED-4 holds by
path (a), meaning underwater at `pClaim` against θ = 125 % (in term or after it, IT-2), or by path (b), the
standing CLAIM_NOTICE with `pEmerg` under `EMERGENCY_RATIO_BPS` = 105 %. A claimant `C` spends `V` by the
APP branch into a claimant intent and, if `residualZat ≥ RESIDUAL_MIN`, an owner residual intent. `C` burns
`burnedCents ≥ D` YED and pays the FEE-1′ protocol fee on `D` at the vault's `pMint` (1 % of the first
$1,000, 0.5 % to $10,000, 0.1 % above that, with a $1 floor; half goes to an attestor payee when one is paid)
plus network fees. For `CLAIM_DELAY` = 576 blocks (12 h), the cancel branch
`<attestorSetId> OP_2 OP_CHECKSETSIG` lets **any one current member** of the OPEN 15-seat attestor set
(`cancelThreshold` pinned to 1, 03/I-3, `params.cpp:110`, `module.cpp:46`) spend the claimant intent back into
the byte-identical `V`. CAN-1 (`ApplyIntentSpend`, `state.cpp:~800-880`) then re-issues the burn to the holder
of the claim's lowest-index YED input and credits `supplyCents`. The vault is ACTIVE again, and its standing
notice is erased (`state.cpp`, the `keys::Notice` erase).

**The residual veto (R-1).** Nothing limits how often a cancel happens. The same member can cancel every claim
on `V`, round after round. Consensus does not record who cancelled (U-19, 03/V-2). No vote can remove the
member (D-Q-29: the module refuses SET_REMOVE/SET_WINDDOWN on the attestor set). EQV-1 slashes only two prices
at one height, which a cancel never produces. Each round costs the canceller one signature, a network fee and
the refund carrier (10,000 zat). Each round costs the claimant the protocol fee, the network fees, 12 h, and on
path (b) a fresh notice plus `EMERGENCY_PERSIST` (48 blocks). A rational claimant stops after one or two
rounds. The vault then stays open while its collateral falls through θ and through 100 %, and YED holders as a
whole carry the bad debt. D-IT-13's calibration puts a number on the cost of delay: 12 h of cancel window
means 2.1 % worst-year bad debt and 24 h means 3.2 %. An unbounded veto removes the bound.

- **R-1a, owner plus a seat.** The owner of `V` holds, or rents, one seat: a 10,000–20,000 YEC bond (D-Q-30),
  returned 14 days after exit (D-Q-31) and never slashed for this. The owner then holds a free put on its own
  collateral. If the price recovers, the vault survives. If it does not, the loss falls on YED holders.
- **R-1b, one seat for every vault.** In a crash a single member, whether it is griefing, has been bribed
  ("cancel as a service") or has had its key stolen, can stall **every** claim in the system at the moment
  liquidations matter most.
- **R-1c, path (b) residual extraction (U-24 "given up" (iv)).** An owner with a seat claims its own vault by
  path (b). The claim carries no margin (`marginBps` = 10⁴), so the owner's residual intent holds about
  `collateral − D/pClaim`, which is roughly 5 % of `D` and more when `pClaim > pEmerg`. The owner then cancels
  the claimant intent. The burn comes back (CAN-1), the vault reopens holding only the claimant intent's value
  (about 100 % at `pClaim`), and the residual intent can still be released to the owner after 576 blocks: the
  residual cannot be cancelled (`INTENT_CANCEL_RESIDUAL`), and S-1 (one template input per transaction) stops
  it being re-locked together with the claimant intent. The owner has taken `R` out of a vault that should
  have been liquidated. A second round yields about 0, because the reopened vault is at or below 100 %, so
  this extraction is one-shot per vault. It does combine with R-1a.
- **R-1d, rate budget (side effect).** S-3 never reduces `epochUsed` on a cancel. If the YED attestor set
  carries a non-zero `rateLimitBps`, a claim-and-cancel stream also spends the set-wide unlock budget, which
  can refuse **other** vaults' claims in that epoch. Any limit on cancels shrinks this effect too.

**What the brake is for, and what any design must keep.** A **wrong-price claim** is one that is consensus-valid
(RED-4 holds at the claim's `pClaim` or `pEmerg`) at a price that is false because the inputs were
manipulated: a captured attestation quantile together with a pool majority on path (a), or a pool majority on
path (b) (the v3 collusion row in upgrade plan §11). Consensus cannot tell such a claim from a right one, so
the cancel is a human veto. **Requirement B:** a sustained wrong-price campaign against one vault must remain
stoppable by the honest members that the system already needs live. ARM-1 asks for `attestArmMin` = 7
attestors before YED prices arm at all.

## 2. Candidates

All candidates are **module-only** (`src/yellowback/`). The primitive (`src/vault/`), the templates, the opcodes,
`vault_vectors.json` and `main.cpp` are untouched except where a candidate says otherwise. "State" means fields
appended last to an existing record (SERIALISATION.md §1). Every one of them bumps `SCHEMA_VERSION` (13 → 14) and
changes the state-hash preimage.

### C0. Raise the set's cancel threshold (the smallest-footprint baseline)

- **Rule:** `ATTESTOR_CANCEL_THRESHOLD` = 2, or `k`, instead of 1. The interpreter enforces it with no new
  logic, because `OP_CHECKSETSIG` reads the threshold from set state (U-13).
- **State:** none. **Footprint:** one constant, plus the fixtures' set shapes.
- **Brake:** every cancel, including the first against the first wrong-price claim, needs `k` members who
  co-sign the **same transaction**. That is practical only once 01/V-2 (`fix/set-sig`, ANYONECANPAY set
  signatures) lands, with a canonical cancel skeleton. It gives up "one honest watcher stops the theft"
  (§3.4) for every claim.
- **Collusion:** `k` seats block every vault forever. With `k` = 2 that costs two returnable bonds.

### C1. Per-vault cancel budget: N cancels per window, after which the claim stands

- **Rule (CAN-2/C1):** `VaultRecord` gains `cancelWindowStart i32` and `cancelsInWindow u8`. A cancel of a
  claimant intent at height `h` first checks `h − cancelWindowStart ≥ CANCEL_WINDOW`; if so, the window
  restarts with `cancelWindowStart = h` and the count at 0. The cancel is valid only while
  `cancelsInWindow < N`, and it then increments the count. Otherwise the verdict is `intent-cancel-budget`
  and the claim releases after its delay.
- **State:** two per-vault fields. The cancel's record copy (`v = vault.value()`) already carries them to the
  re-created position. **Footprint:** about 15 lines and one verdict.
- **Brake: exhaustible. This is fatal.** See §3 A-1. A thief with captured prices files `N` wrong-price claims,
  which honest members cancel at once. The `N+1`-th claim cannot be cancelled by anyone. A variant, "each
  member may cancel each vault once per window", has the same flaw with `N` = the number of honest members.

### C2. Escalating co-signed cancels (recommended)

- **Rule (CAN-2):** `VaultRecord` gains `cancelCount u8` and `lastCancelHeight i32`, both 0 at the mint. For
  a cancel of a claimant intent at height `h`:
  `q = (h − lastCancelHeight < CANCEL_QUIET) ? cancelCount : 0`; `required = min(q + 1, CANCEL_SIGNERS_MAX)`.
  When `required ≥ 2`, the cancel must carry a **CANCEL_COSIGN** payload: a new YED payload type with a short
  OP_RETURN header and its signatures in the scriptSig carrier, as v3 bundles ride today (W2,
  `bundleCarrier = SCRIPTSIG`). The payload holds at least `required` 65-byte recoverable signatures over
  `SHA256d("YedCancelCosign" ‖ attestorSetId ‖ claimantIntentOutpoint)`. The recovered keys must be distinct
  **current members** of `attestorSetId` in the block's set snapshot (the snapshot `OP_CHECKSETSIG` reads).
  Otherwise the verdict is `intent-cancel-cosign`. Extra valid signatures are allowed. The interpreter's own
  single set signature still binds the transaction, and the co-signer count is independent of it, so the
  primary signer simply adds its own co-signature. On success the cancel sets
  `cancelCount = min(q + 1, 255)` and `lastCancelHeight = h`. When `required = 1` the cancel is exactly
  today's CAN-1 shape.
- **Why a separate message and not the set signature:** co-signatures over the intent outpoint can be
  gathered before anyone builds the transaction. They can be gossiped, they are not circular (a signature
  cannot sit inside the outputs it signs under SIGHASH_ALL), they avoid any SET_EQUIVOCATION risk (they are
  not set signatures over a prevout), and they need no relay-policy change to the template scriptSig, where
  the 07/F-1 DoS rule caps pushes at the role's threshold.
- **State:** two per-vault fields. **Footprint:** one payload type, one verification loop that reuses the
  existing compact-signature recovery and the membership lookup (`vault::GetSet` / snapshot), and one verdict.
  It needs no primitive, template, opcode or `main.cpp` change and no global table. D-Q-29 is not reopened.
- **Brake:** the first cancel needs one honest member, as today. A campaign against one vault needs
  2, 3, 4, then 5 distinct honest members, and 5 for every round after that. The capacity is never
  exhausted; it costs coordination, not budget.
- **Collusion:** `CANCEL_SIGNERS_MAX` seats acting together block one vault, or all of them, indefinitely.
  That is the captured-set row, priced at five bonds instead of one.

### C3. The canceller refunds the claimant's YEC costs

- **Rule:** the cancel must also pay the refund holder at least `feePaidZat + CANCEL_FEE_ALLOWANCE` zat.
  `feePaidZat` is already rewritten by the claim onto the CLAIMING `VaultRecord`. Otherwise the verdict is
  `intent-cancel-no-fee-refund`. An escalating variant multiplies the amount by `2^q`.
- **State:** none for the flat form, which reads the existing `feePaidZat`; for the variant, `cancelCount` as
  in C2. **Footprint:** one more output check.
- **Brake: inverted.** An honest member who cancels a wrong-price claim pays the thief's fee. Under the
  escalating variant the thief earns `2^q × F` per round: a money pump paid out of the honest brake (A-2). The
  flat form makes the thief's attempts free and charges the honest members `F` per round until they stop.
  Against R-1a it only prices the veto. For a $10,000 debt, `F` = $55 per 12 h, about 1 % of the debt per day,
  which an owner protecting a deep-water vault may happily pay.

### C4. A repeated cancel of a price-correct claim is slashable

Two ways to build the proof:

- **C4a, outcome proof (rejected).** The slash applies "if a later claim at no higher price is released", or
  "if the snapshot prices stayed under the cancelled claim's line for `X` blocks". Both read **the same price
  inputs a wrong-price attack falsifies**. In the very attack the brake exists for, a pool majority holds the
  snapshot prices low, and the honest canceller would then be slashed. It also chills honest cancels.
- **C4b, statement proof (a candidate deterrent).** The cancel carries the canceller's signed price statement
  `(seq, citedHeight = the claim's refHeight, price)` with `collateral · price ≥ D · θ`, meaning "at your
  reference height this vault was not claimable". **EQV-1, unchanged in meaning**, slashes any member whose
  regular attestation at that height carries a different price: two prices at one height, burned bond,
  ejection. The only removal D-Q-29 allows is therefore the one used, and D-Q-29 is not reopened. An honest
  canceller of a wrong-price claim is never at risk, because its own honest attestation at `R` already says
  "not claimable".
- **C4b footprint:** the cancel payload (shared with C2's), EQV-1 accepting a cancel statement as one side
  (one payload shape), plus wallet and agent support. It needs no state.
- **C4b limits:** a member that never attests at the heights claimants cite, or that attests falsely high
  everywhere (the median ignores it), is never slashable. It is a deterrent, not a bound.

### C5. Companion rule, holding the path-(b) residual (CAN-3, needed with any of C0–C4)

- **Rule:** a residual intent whose claimant intent was **cancelled** may be released (I-1) only once the
  re-created position is closed (REDEEMED, or CLAIMED by a later release), or once `CANCEL_QUIET` blocks have
  passed since the cancel and the position is not CLAIMING. Otherwise the verdict is
  `intent-residual-held`. A residual whose claimant was released keeps today's rule.
- **State:** one field appended to `IntentRecord`. The cancel writes the re-created position's outpoint
  into the residual's record (`heldBy`), so the release check is a single lookup.
- **Effect on R-1c:** the extracted residual is not liquid while the owner's seat holds the vault alive. Under
  C2 a later honest claim liquidates the vault within one round unless the owner has a second seat. An
  honest owner whose vault was wrongly claimed waits at most `CANCEL_QUIET` for the residual, or redeems to
  free it.

Re-locking the residual into the vault, which would be the clean fix, is impossible without a primitive
change: S-1 allows one template input per transaction, and a second V output would be a second position.

### Summary

| | State added | Consensus footprint | First wrong-price claim | Sustained wrong-price campaign | Lone seat (R-1a/b) |
|---|---|---|---|---|---|
| C0 k=2 | none | constant | 2 co-signers | 2 per round | powerless; 2 seats block forever |
| C1 budget | 2 vault fields | small | 1 | **fails after N** | N rounds per window |
| **C2 escalate** | 2 vault fields | payload + rule | 1 | ≤ 5 per round, never exhausted | 1 round per quiet period; 5 seats block |
| C3 fee refund | 0 (or 1) | 1 output check | honest pays F | honest pays F per round | priced, not bounded |
| C4b statement slash | 0 | payload + EQV-1 side | 1 | 1 | deterred if it attests honestly |
| C5 residual hold | 1 intent field | 1 rule | — | — | closes R-1c |

## 3. Attacks

- **A-1, burn the budget before the real claim.** The thief files claims quickly. A cancel may come one block
  after the claim, so a round takes minutes, not 12 h.
  - C1: exhausts `N` in `N` rounds and then steals. Fatal.
  - C2: raises `required` to 5 and stops there, and every later claim still costs the thief a captured price
    plus `F`. The honest set must then gather 5 co-signatures within 576 blocks for every round, for as long
    as the capture lasts. The co-signatures cover only the intent outpoint, so they gossip in minutes. The
    attack costs liveness, not safety.
  - A griefer that is also a member can raise the count with self-cancels only as far as its coalition size.
- **A-2, money pump.** Under C3's escalating form the thief harvests `2^q × F` per round from honest
  cancellers. Rejected. The flat form leaks `F` per round from the honest members.
- **A-3, collusion.** Under C2, `c < 5` colluding seats delay one vault by at most `c` rounds, then lose. Five
  block it indefinitely. They also need no new power to block: more than a third of attestation weight
  quoting high already lifts `aClaim` (`qHighBps` 6,667), which path (b)'s `pEmerg = min` exists to work
  around. C2 adds no protecting power that a coalition of that size lacks.
- **A-4, owner plus seat (R-1a).**
  - C2: one free 12 h delay per `CANCEL_QUIET`. Afterwards the owner needs a second seat or a bribed member.
  - C5: the path-(b) residual stays held while the vault lives.
  - Waiting out `CANCEL_QUIET` resets the count only if no claim succeeded meanwhile. While the vault is
    claimable, a claim at `q = 1` lands within one round, so in practice the reset does not help the owner.
- **A-5, systemic (R-1b).** Under C2 one seat delays each vault once, which is about the same as the
  D-IT-13 24 h case (3.2 % against 2.1 % worst-year bad debt) for the griefed vaults only. Each griefed round
  also stops consuming the rate budget after one cancel (R-1d).
- **A-6, reorgs.** The counters live in `VaultRecord` and undo through `OverlayStateView`/`UndoRecord` like
  every field.
  - `required` is computed from chain state at inclusion. A reorg that adds an earlier cancel raises it and
    voids a cancel carrying too few co-signatures. Agents therefore collect up to `CANCEL_SIGNERS_MAX`
    whenever they can (extras are valid).
  - Co-signatures bind the claim's txid. Template-spend txids are malleable until they confirm (§15.3), so
    agents co-sign only a **confirmed** claim and re-sign after a reorg that re-mines it under another txid.
- **A-7, censorship.** This is the existing row: a majority that censors cancels for 576 blocks enables
  theft. C2 adds gossip time to the latency budget that G-11 measures.
- **A-8, interaction with in-term claims, pMint and early redeem.**
  - **In-term claims** open at θ any time in term, so claims are more frequent (19–50 % of vaults a year)
    and so is the value of a veto. C2's counter is per position and survives each cancel's re-creation, and
    `CANCEL_QUIET` (7 d) is well under the shortest term (30 d).
  - **pMint:** the claimant's per-round fee is FEE-1′ at the vault's `pMint`, a fixed YEC amount set at
    mint. C3 would read it from `feePaidZat`; C2 does not depend on it.
  - **Early redeem:** after a cancel the owner may redeem with IT-9's early fee. A cancel that buys an owner
    12 h to repay is acceptable, because the debt is burned. Neither C2 nor C5 blocks redeem, and C5 lets
    the residual go once the position closes. No path lets an owner avoid the early-redeem fee through a
    self-claim plus cancel: the claim's burn is refunded, but the claim's FEE-1′ is not.

## 4. Recommendation

Adopt **C2 (CAN-2, escalating co-signed cancels) + C5 (CAN-3, residual held)** as one module change on both
lines. Keep **C4b** as an optional phase 2 if the owner wants a slashing deterrent; it shares C2's payload
plumbing. Reject C1 because the brake can be exhausted, C3 because it charges the honest brake, and C4a
because its proof is circular. C0 remains the fallback if the owner prefers zero new state over keeping a
single honest watcher.

**Parameters (mainnet/testnet; regtest in brackets):**

| Constant | Value | Why |
|---|---|---|
| `CANCEL_SIGNERS_MAX` | **5** [3] (**round 2: 4**; see below) | Equals the honest members that must be live to stop a sustained campaign. ARM-1 already requires 7 attestors for prices to arm, so 5 leaves 2 for captured or absent seats. 5 of 15 seats (about a third) matches the protecting power a coalition already has through `aClaim` (A-3). |
| Schedule | 1, 2, 3, 4, 5, 5, … | Linear. A lone seat gets exactly one round, and each extra round needs one more colluder. |
| `CANCEL_QUIET` | **8,064** (7 d) [40] | Longer than any campaign a lone seat can sustain, and shorter than the shortest term (30 d). After a genuine incident the vault returns to "one watcher" within a week. |
| Payload | `CANCEL_COSIGN`, next free type byte, `count u8` header plus carrier signatures | Reuses W2's carrier, so no relay change. |

These are consensus constants beside `ATTESTOR_SEATS`, following the 03/I-3 precedent: not in `ParamsRecord`
and not hashed. yb-calibration re-runs T5 with "one extra 12 h round per griefed vault" to confirm the
bad-debt bound before the release.

**Four-part check (for the PR).** DigiByte does **X** = it makes a liquidation final at inclusion, in **Y** =
`ref/digibyte/src/digidollar/`, using **M** = no challenge window, since DigiDollar has no veto. The Ycash
equivalent **Z** = the primitive's cancel branch (§3.4, I-2) with a set-level `cancelThreshold`, which has no
memory across rounds and so no per-vault limit. So the adaptation **W** = a module rule that remembers, per
vault, how many cancels the position has had recently and raises the number of distinct members who must
co-sign the next one, with a residual-hold rule that removes the extraction.

**In-tier ladder.**

- A **module** rule, not the primitive, because the limit is YED-specific and the bridge's cancels are
  unaffected.
- The **existing** template branch, so no opcode and no template.
- An existing carrier for the payload.
- **Per-vault** state (two `VaultRecord` fields and one `IntentRecord` field), with no global table.

A cheaper rung does not work. A wallet or agent policy cannot bind a hostile canceller. C0's set-wide
threshold is the only cheaper consensus rung, and it trades away the single-watcher response for every
claim.

**Given up:**

- (i) A lone seat still delays each vault once per week.
- (ii) Five colluding seats still block indefinitely. This is the stated captured-set residual.
- (iii) Honest attestors need a co-signature gossip path and must be live within 12 h for repeat
  wrong-price rounds.
- (iv) An honest owner's residual after a wrong-price claim can be held up to 7 days.
- (v) Claimants still lose the YEC fee of a cancelled round. That loss is bounded by the schedule rather than
  refunded.

## 5. Impact

- **Node, both lines in one PR each, same commit sequence** (workspace rule: a module rule change is made on
  `ycash-dd` and `ycash6` together):
  - `src/yellowback/{view.h (VaultRecord +2, IntentRecord +1, SCHEMA_VERSION 14), state.cpp (ApplyIntentSpend
    cancel branch, residual release), state.h (verdicts intent-cancel-cosign, intent-residual-held), params.{h,cpp},
    payload parser}`
  - `src/rpc/{yellowback.cpp, yellowbackwallet.cpp}`
  - `doc/yellowback-rpc*.{md,json}`
  - Review gate: two reviewers, the four-part check in the body.
  - No `src/vault/`, `src/script/`, `src/consensus/`, `src/primitives/` or `main.cpp` change.
- **RPCs:** these are additive and do not bump `rpcversion`, under the document's rule.
  - `yed_getvault`/`yed_listvaults` gain `cancelCount`, `cancelsRequired`, `cancelQuietUntil`.
  - New `yed_signcancelcosign <intent>` signs with the node-held member key, like `set_signcancel`.
  - `yed_buildcancel` gains `cosigs[]` and refuses to build when it holds fewer than `cancelsRequired`.
- **Tests:**
  - Unit (`yellowback_state_tests.cpp`):
    - schedule 1→5 and the cap;
    - quiet reset;
    - duplicate, non-member, removed-member and wrong-outpoint signatures;
    - extra signatures accepted;
    - the counter carried across re-creation;
    - undo byte-identical;
    - residual held, then released at close and at quiet;
    - a release of a residual whose claimant was released stays unchanged.
  - Functional: `yellowback_interm.py::cancel_case` extended to three rounds (1, 2, 3 signers), plus the R-1c
    path (b) scenario. Also `yellowback_upgrade.py`, `yellowback_rpc_contract.py`, and a devnet `upgrade-walk`
    scenario `cancel-escalation`.
- **Golden and vectors:**
  - `yellowback_golden.json` and `GOLDEN_HASH` regenerate once, by the T-1 process (hash in its own commit,
    independent recomputation in the PR). Coordinate with CAN-1's regeneration if both are still open.
  - `yellowback_model.py` mirrors CAN-2/CAN-3, and SERIALISATION.md gains the rows. Both are byte-identical
    across lines.
  - **`vault_vectors.json` does not change** (no primitive change), so the Hawkeye and YEW copies are
    unaffected.
- **Clients:**
  - **Attestor agent** (`contrib/yellowback/attest/`): today cancels are operator-driven
    (`yed_buildcancel` + `set_signcancel`). CAN-2 adds a cancel-co-sign message on its existing iroh-gossip
    topic (the `dir` transport in tests), a watcher that co-signs confirmed claims its own price says are
    wrong, and a "collect up to 5" policy.
  - **Hawkeye:** none. It is bridge-only, never cancels YED intents, and the template scriptSig shape is
    unchanged.
  - **YEW:** shows `cancelsRequired` before a claim ("one attestor can still cancel this claim" or "needs N")
    and the fee at risk per round. It reads the residual-held state on its owner view.
  - **chain-viz:** the cancel panel shows co-signers; this is optional.
  - **YecWallet, lightwalletd:** additive fields only.
  - **yolo, x402:** none.

## 6. Questions for the owner

1. **One free delay.** With the recommendation, any single attestor can still hold up a liquidation once, for
   about 12 hours, per vault per week. A second hold needs a second attestor, and so on. Is one free hold
   acceptable?
2. **The number five.** Five attestors acting together could protect a vault, or every vault, forever. In the
   other direction, a fake-price attack stays stoppable as long as five honest attestors are online and can
   co-sign within 12 hours. Is five the right balance, or do you prefer four or six?
3. **Simplest alternative.** Do you prefer the smaller change of always requiring two attestors to cancel?
   It needs no new records, but the first response to a fake-price claim then always needs two people, and
   two attestors together could block liquidations forever.
4. **Claimant's fees.** A cancelled claimant gets the YED back but not the YEC fee. Should attestors who join
   a *second or later* cancel also repay that fee? It is fair to claimants, but it makes honest attestors pay
   whenever a thief keeps trying.
5. **Owner's leftover after a cancelled claim.** If a claim on your vault is cancelled, the leftover collateral
   that claim set aside for you would be held for up to a week, or until the vault closes, so an owner who is
   also an attestor cannot pocket it. Is that acceptable for honest owners whose vault was wrongly claimed?
6. **A penalty as well?** Should we later add a rule under which an attestor who cancels while its own
   published price said the vault *was* liquidatable loses its bond? It deters but does not bound, and it
   costs one more payload.
7. **Unlock budget.** Cancelled claims currently use up the attestor set's shared unlock allowance (if one is
   set). Should cancelled YED claims stop counting? This is a separate small item, raised here because griefing
   makes it worse.
