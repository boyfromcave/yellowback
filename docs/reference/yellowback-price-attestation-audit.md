# Audit: Bond-Weighted Price Attestation (revision 5)

Initial feasibility audit of `yellowback-price-attestation.md` revision 5 (13 September 2026),
read against the **implemented** Yellowback v2 (`docs/plans/yellowback-v2-development-plan.md`,
revision 6; node fork `ycash-dd` through Phase 8) and the pinned Ycash v4.5.0 source. Scope is
feasibility only; a development plan follows separately.

Branch for this work: `feature/yellowback-price-attest` in the workspace, `ycash-dd` and
`yecwallet-dd`, each cut from `feature/yellowback-sf` on 2026-09-13.

## 1. Verdict in one paragraph

**Worthy: yes. Feasible: yes, but not as written.** The problem is real — the plan's own trust
statement (§8.1) and threat model (§8.2, "Majority hashpower colludes: can move prices … the
chain's existing assumption") concede that price honesty rests entirely on honest-majority
hashpower, and the launch bar (`N ≥ 3` pools, none above 40 %) is governance, not mechanism. A
second population that hashpower cannot forge, combined by `min`/`max` so that theft needs both
populations at once, is a genuine security upgrade and the strongest idea in the document. The
registration/seating/quantile core maps cleanly onto the overlay machinery the fork already has
(a payload type, a state table, snapshot fields, `yed_*` RPCs) and stays on the same tier as the
existing soft fork. What does not survive contact with the implemented v2 is the **delivery
layer**: the in-transaction bundle, the relay carve-out, the in-node gossip stack and the in-node
price polling. Those four decisions are where the document is written against the retired v0.2
proposal rather than the plan, and each one either contradicts a standing plan decision or a
verified constraint of the pinned tree. §3 below argues that all four can be replaced by one
Tier-0 mechanism the plan already uses — an attestor **heartbeat transaction** — which also closes
the document's one structural defect (§2.1).

## 2. Findings

Ordered by severity. "Blocking" means the design cannot ship in that form; "adapt" means the
idea is sound and the plan must restate it in v2 terms.

### 2.1 Blocking — the attestation series is never on the chain, but three rules read it

The document keeps attestations off-chain by design (§4: "attestors never submit transactions
except to register"; §13). They reach the chain only inside a mint or normal-claim bundle. Yet:

- §10.1's responsiveness test arms when "the other source moved" — for the cross-section, the
  other source is the attestation statistic, which exists only at heights where someone minted.
- §10.2's divergence breaker compares the two statistics for `DIVERGE_PERSIST` consecutive
  blocks. There is no per-block attestation statistic to compare.
- §10.3 says emergency claims are "evaluated entirely from chain data" and carry no bundle, and
  in the same section that "under a pinned cross-section, the attestors alone can open the
  backstop". Both cannot hold: attestors alone can open nothing unless their attestations are on
  chain, and in a crash — when nobody is minting — no bundle carries them there. The payout
  "uses the last recorded attestation statistic", which during a quiet week may be days old,
  i.e. exactly the stale-high value §10 exists to defeat.

The design implicitly needs a continuous on-chain attestation series and explicitly refuses to
produce one. This is the defect that must be settled before anything else, and §3 proposes the
settlement.

### 2.2 Blocking — the transport and polling stack cannot go into `ycashd`

- **Rust toolchain.** The pinned `depends` Rust is 1.63.0 (`ref/ycash/depends/packages/native_rust.mk:6`).
  Current `iroh`/`iroh-gossip` releases require a far newer MSRV; `quinn` and the async stack
  they pull in would need a toolchain bump, a re-vendor of every crate (`depends/Makefile:133`
  runs `cargo vendor --locked` against the top-level `Cargo.toml`) and a `configure.ac` change.
  `configure.ac` is in the plan's zero-diff set (§4.1). This is a toolchain project, not a feature.
- **No sockets in the node.** Plan V6 keeps HTTPS out of `ycashd` (the quote agent pushes via
  `yed_setquote`), and the fork's CI asserts it — the "no clock, no sockets, no bans" grep in
  `ycash-dd/.github/workflows/yellowback-tests.yml:173-194`. §4's `-priceattest=1` node that
  "polls its configured sources" and §13's in-node QUIC stack both fail that gate.
- **Service-bit peering.** Ycash v4.5.0's `net.cpp` predates Bitcoin Core's relevant-services
  outbound preference (`nLocalServices = NODE_NETWORK` only, `net.cpp:60`); "preferentially fill
  outbound slots" is new peer-selection code in `net.cpp`, a file the fork has not touched.

Adaptation: an external **attestor agent** (Python, the shape of `contrib/yellowback/`'s quote
agent) signs and publishes; the node only verifies. Where the signed messages travel is then an
ordinary application question (any relay, HTTPS, or — per §3 — the chain itself).

### 2.3 Blocking as written — the oversized `OP_RETURN` carrier is a network-adoption dependency

The document's reading of the pinned tree is **correct**: every line cite in §8.1 checks out
(`standard.h:31-34`, `standard.cpp:19`, `init.cpp:1182`, `policy.cpp:51-53` and `:122-125`,
`main.cpp:1558`, `interpreter.cpp:445-447`, `script.h:618`, `standard.cpp:99-102`), and
`CheckTransaction` imposes no per-output shape rule. A 426-byte push is consensus-valid.

But the consequence is understated. A mint that only conforming nodes will relay, on a network
where the plan's own §8.2 assumes most nodes and some pools are stock, makes minting
reachability a function of Yellowback adoption density. The document's preferred remedy — ship
the carve-out "in the standard `ycashd` release" — is an ask to the Ycash maintainers to change
relay policy for everyone, which is exactly the kind of upstream change the workspace's prime
directive exists to avoid, and it is not in the maintainers' hands to make quickly. Three further
frictions with the implemented v2:

- The payload parser's shape rule is `OP_RETURN <one push of 4..80 bytes>`, `MAX_PAYLOAD = 80`
  (plan §3.1, §3.3; `ycash-dd/src/yellowback/params.h:45`). Widening it is fork-local but changes
  the "non-Yellowback transaction" definition every enforcing node shares.
- `src/policy/policy.cpp` is at zero diff today and outside the consensus zero set, so a
  prefix-gated carve-out is *permitted* by §4.1 — but it is a new row and a new
  `yellowback_stockparity.py` case, and its `full` tier runs signature verification on
  unauthenticated mempool input before any fee is paid.
- The combined record would also have to carry the MINT payload's existing 47-byte body, and
  `M_SELECT ≤ 6` is a cap derived from the 520-byte element limit, not from the threat model.

A cheaper carrier exists if a per-transaction bundle is kept at all: a **scriptSig data carrier**.
`IsStandardTx` allows a push-only scriptSig up to 1,650 bytes (`policy.cpp:88-97`), P2SH inputs
pass `AreInputsStandard` on sigop count alone, and a redeem script of the form
`OP_2DROP … <pk> OP_CHECKSIG` drops the attestation pushes before `CLEANSTACK` is checked. That
relays on every stock node today with no policy patch. Its cost is a prepared carrier output
(one extra funding output the wallet keeps on hand) and a redeem script to specify. Recorded
here as the fallback; §3 argues neither carrier is needed.

### 2.4 Adapt — the document targets v0.2 rules that v2 already replaced

§2's four critiques are of the *proposal's* rolling-median-plus-deviation-penalty design. In the
implemented v2:

- Deviation-based deregistration is **already not a rule**: L1 demoted peer-median judgements,
  penalties and accuracy to wallet-default payee policy (plan V3, V10, §12 Q13). "It punishes
  accuracy" therefore no longer describes anything that affects validity or price.
- The quote-tag-majority attack is analysed (L9) and partly closed by `WINDOW_MIN_FILL` (V16):
  `pClaim` needs two-thirds fill on the mid and slow windows, so it takes 34 % of blocks, not
  26 %. Still hashpower-only, so the document's central point stands — but the plan's numbers
  are the ones to argue against.
- The three windows (96/576/2,016) with `P_mint = min`, `P_claim = max(mid, slow)`, the
  σ-multiplier (V17), HALT-1..4 and `DIVERGENCE_BPS` (20 %, HALT-3) already exist. The
  document's §7.1 per-pool hashpower-weighted cross-section is a *replacement* for the three
  medians, and §10.2's breaker is a *second* divergence halt beside HALT-3. The plan must say
  which survive; running both is incoherent.
- §18 lists "sections of `yellowback-miner-enforced-proposal.md` requiring revision". The
  document that needs revising is the plan; the proposal is history (plan §10.1).

### 2.5 Adapt — limit prices and `valid_until_height` are already solved by `refHeight`

Plan V11: every MINT and REDEEM payload commits a `refHeight` in `[H − 40, H − 1]`, and prices,
halts and activation are read from `Snapshots[refHeight]`. The wallet therefore knows the exact
price and collateral requirement before it signs; there is no "free option resting in the
mempool" and no need for `max_price`/`min_price` fields or a separate `valid_until_height`
(the mempool already bounds expiry at `refHeight + REF_WINDOW`, MP-1/N5). Attestations should
cite `refHeight` and its block hash the same way, which also gives §8's hash-derived selection
its seed (`H(blockhash_at_refHeight ‖ vault_id)`) and makes §14's reorg rule identical to the
existing `refHeight` rule rather than a new one. §9 and §14 collapse into V11.

### 2.6 Adapt — "the transaction is invalid" means "the vault is VOID" in v2

Plan V3: mint rules have verdict semantics, not block validity. A mint whose bundle fails
(one attestor short of `M_SELECT`, a signature over the wrong block hash after a shallow reorg)
does not fail — it confirms as a **VOID** vault with the collateral locked until `lockHeight`
(L14 lets `yed_redeem` release it then, but that is 30 days at minimum, class A). The strict
template filter (TPL-2) keeps *enforcing* pools from mining such a mint, but a stock pool will.
The document's assumption that a bad bundle simply "fails" understates the user-loss residual it
adds to the plan's existing VOID cases (§8.2 "Mint races the supply cap or a reorg changes its
snapshot"). Any design that makes mint validity depend on an off-chain liveness input inherits
this; the heartbeat design in §3 removes the dependency.

### 2.7 Adapt — Schnorr is compiled out; ECDSA is the zero-cost choice

`ref/ycash/src/secp256k1/include/secp256k1_schnorrsig.h` exists, but `configure.ac:1282` builds
libsecp256k1 with `--enable-module-recovery` only; `schnorrsig` and `extrakeys` are not
enabled, and enabling them is a `configure.ac` change (zero set). A 64-byte compact ECDSA
signature over the same message, verified against the seated key resolved from the registration
record, is byte-for-byte the same size and uses code the node already links. Nothing in the
design needs Schnorr's linearity (aggregation was dropped in revision 3). Use ECDSA.

### 2.8 Adapt — the bond output must be P2SH with the script disclosed in the record

§5.2 specifies a bare `<locktime> OP_CHECKLOCKTIMEVERIFY OP_DROP <pubkey> OP_CHECKSIG`
output. `Solver` classifies that as `TX_NONSTANDARD`, so the registration transaction would not
relay on stock nodes — the same reachability problem as §2.3, for a transaction that must be
one-shot and public. The fix is the vault pattern the plan already uses (§3.4): a P2SH output,
with `bond_pubkey` and `bond_locktime` in the `OP_RETURN` record, and the module reconstructing
the redeem script and checking the P2SH hash. Standard relay, same verification strength.

### 2.9 Adapt — the consensus-shaped surface grows, and K10 governs it

Everything the seated set, bond weight, quantile thresholds, pin test, emergency tier and
residual return read is consensus-shaped among enforcing miners (plan K10, §3.1 versioning).
The document adds roughly fifteen parameters (§15) and two new claim rules (§10.3 changes
RED-4 and the payout arithmetic). Each is a parameter set keyed by start height with a sunset
(L8). Fine before mainnet, but the plan must add the rows and the model
(`test_framework/yellowback_model.py`) must reproduce every new snapshot field, or the N23
cross-implementation check silently stops covering the price layer.

### 2.10 Minor

- **Block time** is right: Blossom activated on Ycash mainnet at 1,100,000
  (`chainparams.cpp:131`), so 75 s and the plan's `BLOCKS_PER_HOUR = 48` hold.
- **§8.3 "policy heterogeneity is safe"** is true, but the `full` tier verifies four signatures
  per candidate before fee checks; the plan's DoS review (Phase 8) would need a row.
- **Dormancy suspended during halts** (§12) interacts with HALT-1/HALT-4: define "paused" as
  `haltMask ≠ 0` at the snapshot, or the two implementations will disagree.
- **Founding cohort** (§6.3) is sound and cheap; it is a snapshot field, not a rule.
- **§7.5 population overlap** is honestly stated and has no protocol remedy; agree.
- **Thin-market ceiling** (§4, §17) is correctly identified as outside the price layer; agree.
- **Naming**: the document uses `-priceattest`, `-ybrelaycheck`; the fork's convention is
  `-yellowback…` flags and `yed_*` RPCs (CLAUDE.md §6).

## 3. The recommended direction: attestor heartbeat transactions

> **Superseded (2026-09-13).** The product owner rejected this direction: it puts a periodic
> on-chain transaction, a funded hot wallet and reorg-watching on the attestor, which is the
> opposite of the design's allocation of cost (attestors free beyond the bond; minters and
> claimants pay for the price they need). The fee itself is negligible (≈ 0.4 YEC a year at
> `k = 10`); the operational burden and the principle are what matter. Revision 6 of the
> proposal keeps attestations off-chain and instead (a) carries bundles in a P2SH **scriptSig
> carrier input**, standard on stock nodes today (§2.3 above), (b) moves gossip and polling into
> external agents that may use a modern Rust toolchain, and (c) closes §2.1 by making whoever
> needs a trigger carry the evidence — per-bundle divergence, a two-step emergency claim, and a
> pin test armed from landed bundles. The toolchain bump is proposed upstream on its own merits.
> The text below is kept as the record of the alternative and its censorship trade-off.


Every blocking finding above traces to one decision — keeping attestations off-chain and
smuggling them into someone else's transaction. Reverse it.

**Each seated attestor publishes its own attestation as an ordinary transaction**, roughly
every `k` blocks: a dust-funded transaction with one `OP_RETURN` carrying
`magic ‖ version ‖ ATTEST ‖ seatedIndex u8 ‖ priceMicroUsd u32 ‖ refHeight u32 ‖ sig 64` —
77 bytes, inside the existing 80-byte shape rule. Then:

- **It is standard today.** No relay carve-out, no service bit, no `policy.cpp` row, no
  network-wide adoption ask. Stock nodes relay it and stock pools mine it. (§2.3 dissolves.)
- **The attestation series is on chain, continuously.** `Snapshots[h]` gains an attestation
  statistic computed from each seated attestor's latest attestation within `ATTEST_MAX_AGE`,
  bond-weighted, at the adverse quantile — the same shape as the cross-section. §10.1, §10.2
  and §10.3 all become computable exactly as written. (§2.1 dissolves.)
- **Mints and claims carry nothing new.** They keep their 51/10+5n-byte payloads and read
  `Snapshots[refHeight]` as today. Bundle selection, `K_SLACK`, grinding, the `M_SELECT ≤ 6`
  cap, the reorg rule and the wallet resubmit obligation all go away; §14 is V11. A mint can no
  longer be voided by an attestor's outage — it is halted before it is built, by HALT-1's
  existing fail-closed semantics extended to the attestation statistic. (§2.5, §2.6 dissolve.)
- **The node stays socket-free.** The attestor is an external agent (`contrib/yellowback/`)
  that polls venues, signs, and calls `sendrawtransaction` on its own node; the node's only
  new work is a payload type, a state table and a quantile. (§2.2 dissolves.)
- **Cost to an attestor** is `YELLOWBACK_FEE` per heartbeat — 1,000 zat, `0.00001` YEC — beside
  a 20,000 YEC bond. The document's objection to fee-paying quotes (§2, "pool operators will
  not publish periodic fee-paying transactions") was about pools; it does not apply to a party
  that has posted a bond three orders of magnitude larger than a year of heartbeats.

**The trade the plan must weigh: miner censorship of attestation transactions.** Miners cannot
forge an attestation, but they can decline to include one. Against a *minority* pool this is
harmless: the statistic takes each attestor's latest attestation from any block in the window,
so what one pool omits, the next pool includes. Against a *majority coalition* that both authors
the cross-section and censors the attestations it dislikes, the `max` side of the claim rule
loses its second population — a strictly weaker property than the in-transaction bundle, where
miners could only censor the whole claim. Two things bound it. First, that coalition is the
chain's standing assumption (plan §8.2, last row), and it can already reorganise the chain.
Second, the censorship is *visible*: a seated, bonded attestor whose heartbeats stop appearing
while it is demonstrably publishing them is an on-chain fact an explorer can show, unlike a
quietly skewed quote. Whether that is an acceptable residual, or whether claims (only) should
retain an optional in-transaction bundle via the scriptSig carrier of §2.3 as a belt-and-braces
path, is the first decision the development plan should put to the product owner.

**Tier.** Same tier as v2 today: overlay state plus enforcer-shared rules, no consensus change,
no upstream policy ask. The main-line changes are a payload type (`0x04 ATTEST`,
`0x05 ATTESTOR_REGISTER`, `0x06 EQUIVOCATION`), state tables (`Attestors`, `Attestations`),
snapshot fields, HALT and RED-4 changes, and RPCs (`yed_listattestors`, `yed_getattestations`,
`yed_registerattestor`), plus the Python agent and model. No new line in `main.cpp`,
`miner.cpp` or `policy.cpp` is required.

## 4. What the development plan needs from a revision 6 of the document

1. Re-base on the plan's §3 rules, not the v0.2 proposal: state which of the three medians,
   HALT-3 and the σ-multiplier survive beside the new cross-section and breaker (§2.4).
2. Adopt (or explicitly reject, with reasons) the heartbeat carrier of §3; if rejected, choose
   between the policy carve-out and the scriptSig carrier and answer the reachability question
   for the network as it is, not as it might be after upstream adoption.
3. Move attestor signing and transport out of the node; specify the agent the way plan §5
   specifies the quote agent.
4. ECDSA, P2SH bond with disclosed script, `refHeight` in place of `max_price`/`valid_until`.
5. Enumerate every new snapshot field and parameter for K10 versioning and the Python model.
6. Keep §16's two calibration measurements; both are still needed and still non-blocking.

## 5. Rough size (for budgeting only)

Against the heartbeat design: node ≈ 2,000–2,500 new lines under `src/yellowback/` and
`src/rpc/` (registration, seating, weight, quantile, pin test, emergency tier, three payload
types, RPCs), ≈ 1,000 of tests and model, 0 in the budgeted main-line files; attestor agent
≈ 500 lines of Python; wallet ≈ 300 (attestor status, halt reasons, explorer-style views);
docs and pool-kit updates. Comparable to Phases 2 and 3 together. The in-transaction-bundle
design would add the policy patch, a wallet bundle assembler and resubmitter, and either a
toolchain project or an external relay, and is not sized here.

## 6. Second pass (13 September 2026) — revision 6 after the five decisions

Read end to end against plan §3.6–3.8. Ten defects found, all fixed in the text:

| # | Defect | Fix |
|---|---|---|
| 1 | An EJECTED attestor who spent its bond became WITHDRAWN and could re-register | EJECTED is terminal; the bond spend records `bondSpentHeight` only (§5.2) |
| 2 | Dormancy was measured by bundle appearance, but only seated attestors can appear — every unseated ELIGIBLE attestor would go dormant, and a DORMANT one could never revive | Dormancy applies to attestors seated for the whole window and *selected* at least `DORMANCY_MIN_BUNDLES` times without delivering; `BundleLog` records `selectedSeqs[]`; revival by one `ATTESTOR_REVIVE` transaction (§12) |
| 3 | "A later valid notice replaces it" let the vault owner reset the emergency clock every 47 blocks | A standing notice within `EMERGENCY_NOTICE_TTL` is not replaced (NOT-1) |
| 4 | Founding cohort ambiguous for registrations before the trigger; weight negative before it | Cohort = `registerHeight ≤ triggerHeight + FOUNDING_WINDOW`; weight clamped at 0 (§6.1, §6.3) |
| 5 | Selection could draw pinned attestors, consuming `K_SLACK` | Selection draws from seated minus pinned (§8.4) |
| 6 | §7 and BUNDLE-1 disagreed on whether non-selected seated attestations may appear | BUNDLE-1 requires `seq ∈ selected` and `M_SELECT ≤ count ≤ BUNDLE_MAX` |
| 7 | `BundleLog` was prunable but in the state hash | Never pruned; one ≈ 60-byte row per bundle-carrying block (§15) |
| 8 | Bundle-verification cost under payload spam unstated | Cheapest-first ordering, verified-bundle cache from mempool acceptance, cost bounded and referred to the DoS review (§8.2) |
| 9 | A Sapling-funded mint now has a transparent carrier input | Stated; carrier outputs made to fresh keys from shielded funds (§8.1) |
| 10 | No bond withdrawal or revival RPC; signed message had no version byte | `yed_withdrawbond`, `yed_revive`, `yed_preparecarriers`; prefix `"YBATTEST1"` (§4, §13) |

Also added: equivocation is two prices for one block *hash*, so honest attestations on two
sides of a fork are not punished (§12). Checked and found consistent: the `refHeight` window
and the attestation window coincide (`ATTEST_MAX_AGE = REF_WINDOW`), so a bundle adds no reorg
exposure; MINT-9/10 are deterministic functions of `Snapshots[R]` and the committed bundle, so a
wallet that builds a mint can never see it VOID except through a reorg deeper than `REF_LAG`,
as in v2; every OP_RETURN payload is ≤ 80 bytes; TRANSFER is untouched; no budgeted main-line
file gains a line. **Ready for the development plan.**

## 7. Third pass (13 September 2026) — the v3 plan, two independent reads

The v3 development plan (`docs/plans/yellowback-v3-development-plan.md`, revision 1) was read
end to end by its author and, separately, by a reviewer with no context from the drafting
session. Thirty-eight findings (S1–S18 in the plan's §0.1; R1–R20 cited inline) were applied to
the plan, and the four that change the design were applied to this proposal:

| | Defect | Change |
|---|---|---|
| R1 | A captured attestor set could open emergency claims on every vault and keep the 10 % liquidation margin — extraction, not griefing. | A claim opened by the emergency clause alone pays exactly the debt at the adverse price (§10.3). |
| R2 | The 16-byte bundle hash in the payload *detected* a substituted bundle but turned the substitution into a VOID mint with collateral locked for the term — a free grief for any relay node. | The carrier's redeem script commits `SHA256(bundle)`; the commitment is signed and P2SH-pinned, a substituted bundle is simply invalid; carriers are per-transaction with one confirmation before the main transaction (§8.1). |
| R4 | Within a 40-block window a builder could pick each attestor's most favourable of ~4 signed prices. | `ATTEST_MAX_AGE = 20`: at most two per attestor (§15). |
| R5 | The residual formula carried a spurious `10⁴` (off by four orders of magnitude). | Corrected; v2's worked example added as the check (§10.3). |
| S13 | The mint's selection selector was the owner key, which the minter chooses freely — unlimited grinding. | The mint selector is empty; all mints at one reference height share a selection (§8.4). |

Also changed in the plan only: 256-bit selection arithmetic (R10), selection and dormancy read
the stored snapshot arrays, never a recomputation (R11), a per-attestation signature cache
instead of a per-bundle verdict cache (R3), bundle verification after the fee and vault rules so
spam costs `FEE_MIN` (R15), activation restored to the SNAP order (R7), `yed_signattestation`
takes a `seq` and refuses to sign a conflicting price (R17, S16), Python signatures canonicalised
to low-S (R18), the runner's `--portseed`/`--cachedir` override documented and patched (R16),
`ATTEST_REQUIRED` as a release-level disarm switch (S17), and one frozen-file list (R19).
