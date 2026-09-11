# Ycash Yellowback (YED) — Interoperability Plan

> **Status: INACTIVE — experimental idea, not a plan** (see [`README.md`](README.md)). Written on
> 2026-09-06 against the federation design that was retired on 2026-09-10; its escrow, attestation
> and roster assumptions must be re-examined under miner enforcement before any of it is adopted.

**Status:** PROPOSAL — revision 1 (2026-09-06). Not decided. Companion to
[`../plans/archived/yellowback-v1-development-plan.md`](../plans/archived/yellowback-v1-development-plan.md) (the *development plan*)
and [`../plans/archived/yellowback-v1-hardening-plan.md`](../plans/archived/yellowback-v1-hardening-plan.md) (the *hardening plan*). It
changes no decision recorded in either and cites their identifiers (`D3`, `D10`, `D23`, `C20`,
`XFER-1..3`, `IN-1..3`, development plan §9). Its own items are numbered **I1–I18** (decisions),
**ESC-\*** (escrow), **DEP-\*** (peg-in), **REL-\*** (peg-out), **XFR-\*** (co-sign policy) and
**T1–T3** (the trust ladder) and **OP-\*** (opcode design rules).

**The problem.** YEC is the collateral asset; Ycash Yellowback (YED) is the dollar minted against it.
YED's rails are Ycash transparent outputs read by an overlay index, so YED can be held or moved only
by software that runs that index — today, two programs. Ycash has no virtual machine, so there will
never be lending, an automated market, a payment processor or an exchange integration *on* the YED
rail. Minting is fine where it is. **Distribution is the problem this plan solves.**

**The answer in one paragraph.** Keep the Ycash index as the ledger of record: every YED that
exists anywhere else is a YED sitting in escrow on Ycash. Build exactly **one** bespoke hop from
Ycash to one EVM **hub** chain, then reach every other chain over rails other people maintain. Launch
the hop on a federated signer set because that is what can ship, but aim it at a destination where
**an individual proves and the chain verifies**: proofs of the Yellowback index verified on the hub
(no Ycash change) and a generic proof-verifying opcode on Ycash (a network upgrade) that lets a user
redeem a vault, or release escrow, with a proof instead of operator signatures. The opcode's larger
prize is not the bridge: it removes the federation's custody of **collateral** and leaves it a price
oracle. Add a liquidity layer of atomic swaps so users see minutes, not hours. Publish a trust
statement that says exactly which rung the system is on.

**Reading map.** §1 the precedent and the four principles. **§3 the table that says, for every
component, whether it is node-fork code, GUI code, a deployed contract, or supplemental software in a
sister repository.** §4 the hub decision and the expansion path. §5–§9 the design (escrow,
contracts, peg-in, peg-out, co-sign policy). **§10 the trust ladder and the proof opcode: what it
buys for redemption and for the bridge, what stays trusted, and what it costs a node to verify.** §11 the swap layer. §12 the trust statement. §13
decisions, §14 work plan, §15 launch inputs, §16 considered and rejected.

**Pins.** As the development plan: `ref/ycash` `v4.5.0` (`624c12814`), `ref/digibyte` `v9.26.5`
(`05b50e229d`). Cites into `ycash-dd` are against `feature/digidollar` on 2026-09-06.

---

## 1. The precedent and the principles

**The precedent.** Tether launched in 2014 on Omni, a coloured-coin overlay on Bitcoin with YED's
architecture exactly: transparent outputs, a data payload, an index every wallet had to run. It had
almost no reach until it was issued on Ethereum; Omni USDT is now dead. The overlay was not the
mistake — it was the right ledger of record. The lesson is that the demand for a dollar lives where
the composability is, and the issuer has to go there.

**Principle 1 — the Ycash index is the ledger of record (I1).** Supply, health, DCA, ERR and the
cap are computed once, on Ycash. Every unit of YED on another chain is backed one-for-one by a unit
in escrow on Ycash. Nothing off Ycash can create or destroy YED. This is also why "issue YED
natively on Ethereum against Ycash vaults" is not a separate option: the mint still happens on
Ycash and the token output goes straight to escrow. A "mint directly to the hub" button is two
chained Ycash transactions in one wallet action (§7.4).

**Principle 2 — one custom hop, then standard rails (I2).** Ycash has no smart contracts, and no
cross-chain messaging network can read it, so the Ycash-to-elsewhere hop is bespoke and is the
*only* new trust this plan adds. Once YED is an ERC-20 on one EVM chain, every further chain is a
deployment on infrastructure other people maintain: canonical rollup bridges from Ethereum L1, and
Wormhole NTT, LayerZero OFT or Chainlink CCIP for Solana and non-canonical routes. A second bespoke
hop buys one chain for the price of the first.

**Principle 3 — build the hop so its trust can be tightened in place (I3).** The contract interface
is "mint on evidence of a deposit, burn on a release request, refund on timeout" and the escrow is
"a spending condition". What counts as *evidence* and what the *spending condition* is change across
the three rungs of §10; the escrow script family, the token and the user flow do not.

**Principle 4 — prefer "an individual proves, the chain verifies" over coordination (I19).** Where
two designs remove the same trust, take the one with fewer parties, less capital lock-up and no
governance: a proof a user can generate alone and a rule every node checks beats a bonded signer set
with a slashing process, and beats an external signing network. Coordination-heavy mechanisms
(operator bonding, threshold-signature networks, MPC services) are recorded in §16 as fallbacks
for the case where a network upgrade is refused, not as steps on the path.

---

## 2. Background the reader needs

### 2.1 Yellowback in five facts

| Fact | Consequence | Where |
|---|---|---|
| A YED holding is a **transparent output** plus a payload in the creating transaction; a Sapling output has no index a payload could name, so shielded YED is undefined | the escrow is a transparent script; nothing here can be private | development plan D13, I1 |
| The overlay recognises exactly **one `OP_RETURN`** per transaction; a second one makes the transaction non-Yellowback and **burns** its YED inputs | the foreign recipient cannot ride in a data output; it rides in the escrow script (§5) | `ycash-dd/src/yellowback/payload.cpp:258`; spec §3.2 |
| A YED transfer's *validity* is a fact of the **index**: the inputs were tokens, the payload parsed, the amounts were in bounds | no inclusion proof (SPV or zero-knowledge over the transaction alone) can show that YED arrived; either a party running the index says so, or the index's execution is proven (§10, T2) | spec IN-1..3, XFER-1..3 |
| Every YED output is ≥ `MIN_OUTPUT` ($1.00) and ≤ `MAX_OUTPUT` ($100,000); change below $1.00 cannot exist | releases obey the same bounds; escrow change uses the hardening plan's selector (C20) | spec §3.1 |
| Ycash script has **ECDSA only** — no Schnorr, no Taproot, no proof verification; threshold custody is `OP_CHECKMULTISIG` in P2SH, capped near 14 keys by script size | the escrow is k-of-n CHECKMULTISIG (v1) and its signing reuses the vault co-signing code; a proof-verifying opcode replaces the signature clause entirely (§10.3) | development plan D3 `:404-411`; `mapping.md` §2 |

### 2.2 The EVM in five facts

Accounts are keys or contracts; ERC-20 is the token standard every wallet, exchange and protocol
integrates; contracts emit events that off-chain software subscribes to; rollups (Base, Arbitrum,
Optimism, Starknet, zkSync) settle to Ethereum L1 through **canonical bridges** that inherit L1
security; an **optimistic** rollup's state is final on L1 after a challenge window (seven days), a
**validity** rollup's after its proof is verified on L1 (hours). Solidity contracts can verify
secp256k1 signatures and Groth16 / PLONK proofs at modest gas.

### 2.3 Vocabulary

- **Hub** — the one EVM chain the bespoke hop connects to (§4). **Spoke** — any chain reached from
  the hub over standard rails.
- **Escrow output** — a YED output whose script is an escrow script (§5). **Pool escrow** — an
  escrow output with no beneficiary, the bridge's working balance.
- **Bridged YED** — the ERC-20 balance. It *is* YED: the unit is the cent, one bridged cent is one
  escrowed cent, the symbol is `YED`, the contract name "Ycash Yellowback".
- **Operator** — one Ycash secp256k1 key in the escrow roster plus one hub-chain account in the
  registry. **Roster** — the ordered set of n keys; **k** — the threshold.
- **Attestation** — a hub transaction from an operator's account stating facts about a Ycash
  transaction; the contract acts when k distinct active operators state the same facts.

---

## 3. Where every component lives

Four columns, exhaustive: a component is exactly one of them.

| Component | Node fork `ycash-dd` | GUI fork `yecwallet-dd` | Hub contract (deployed) | Supplemental software (sister repo `yellowback-bridge`) |
|---|---|---|---|---|
| Overlay protocol, payload, state machine, parameters | **no change** | — | — | — |
| Escrow script and P2SH address form (§5) | **yes** — `src/yellowback/script.{h,cpp}` gains `EscrowScript(...)`; `address.{h,cpp}` gains the P2SH form (I5) | reads via RPC | same derivation in Solidity so the contract can issue addresses (I6) | same derivation in the daemon, cross-checked against `yed_escrowaddress` |
| `yed_escrowaddress`, `yed_listescrow`, `yed_registerescrow` (§5.4) | **yes** — `src/rpc/yellowback.cpp`, read-only over the index | optional display | — | called by the daemon |
| `yed_buildrelease`, `yed_cosignrelease`, XFR policy (§8, §9) | **yes** — `src/rpc/yellowbackwallet.cpp`, `policy.cpp` (new rule set beside RED-\*), `txbuilder.cpp` | — | — | called by the daemon; the daemon never signs on Ycash |
| Coin selection, change floor for releases | inherited from the hardening plan H1–H4 | — | — | — |
| YED-aware HTLC claim/refund for the swap layer (§11) | **yes**, later phase — `yed_claimswap`, `yed_refundswap` | — | HTLC contract on the hub | swap client, provider daemon |
| Bridged YED ERC-20 (§6.1) | — | — | **yes** — `YellowbackToken` | — |
| Bridge: deposit requests, attestations, releases, timeouts (§6.2, §7, §8) | — | — | **yes** — `YellowbackBridge` | — |
| Operator registry, staking, slashing, pause (§6.3) | — | — | **yes** — `OperatorRegistry`, `OperatorVault` | — |
| T2: index-proof verifier on the hub (§10.2) | — | — | **yes**, later — `YellowbackIndexVerifier` | prover (a library anyone can run; a hosted service is a convenience, not a trust point) |
| T3: proof-verifying opcode (§10.3) | **network upgrade** — the one item in this plan that is not Tier 0; a separate decision for the Ycash team, packaged in Phase B9 | wallet attaches proofs to redemptions and releases | escrow release is a covenant; bridge contract assigns escrow outputs to burns (OP-6) | prover for the redemption circuit and the hub-finality circuit |
| Spoke deployments (NTT / OFT / CCIP adapters, canonical-bridge listings) | — | — | **configuration** of third-party contracts, not code | — |
| Operator daemon (§9.1) | — | — | — | **yes** — extends the coordinator pattern of `ycash-dd/contrib/yellowback/yellowback_fed.py` (I9) |
| User client (§9.2) | — | **later** — a "Bridge" screen in the Yellowback tab is Phase B5, optional | — | **yes** — CLI first, web second |
| Monitoring, alerting, runbooks, solvency dashboard | — | — | — | **yes** |
| Trust statement, user documentation | this document §12; `ycash-dd/doc/` page | in-app text | — | README |

**The rule behind the table (I4).** Anything that *interprets the Ycash chain* or *signs with a
roster key* is in the node, because that is where the index and the keys are and because it is the
code reviewers already trust; the node's new surface is generic ("build a release to these
addresses", "co-sign this release if the policy passes") and knows nothing about any other chain.
Anything that *talks to another chain* or *coordinates operators* is supplemental, because the node
has no outbound Yellowback networking (development plan §5) and must not grow any. Anything that
*holds bridged value* is a contract.

**Why a sister repository (I9).** The daemon needs an EVM client library and the contracts need a
Solidity toolchain, on a release cadence tied to contract upgrades, not node releases. Putting that
in the node fork would make its diff against `ycash-legacy` unreviewable for the Ycash team, which
the workspace's prime directive forbids. The sister repo pins the `ycash-dd` release it is tested
against, as this workspace pins `ref/`.

---

## 4. The hub and the expansion path

### 4.1 Candidates

The ERC-20, bridge, registry and daemon are the same code on any EVM chain; the hub is a deployment
decision with three consequences: attestation cost, who is already there, and how the spokes are
reached.

| Hub | For | Against |
|---|---|---|
| **Base** | cheap attestations; the largest stablecoin payments activity outside L1; Coinbase on-ramps and wallets; OP-Stack tooling | reaching Starknet is two hops or a third-party route; withdrawals to L1 through the canonical bridge take the seven-day window |
| **Ethereum L1** | the canonical home every issuer uses; trust-free canonical bridges to Base, Arbitrum, Optimism and Starknet (StarkGate); the natural place for T3's finality proofs | attestation gas: at launch scale the gas can exceed the fees earned even with hourly batching (§6.5); a launch input |
| **Starknet** | cheap; a validity rollup, so its L1 state root is proof-backed within hours — the best counterparty for T3 (§10.3); Cairo is capable | smaller stablecoin and payments ecosystem; the least third-party messaging support, so a poor hub even if a fine spoke |
| **Arbitrum / Optimism** | DeFi depth (Arbitrum); same tooling as Base | no distribution advantage over Base for a payments dollar |
| **Solana** | cheapest and fastest; large stablecoin volume | non-EVM: a second contract codebase on day one; better as the first spoke via NTT |

### 4.2 Decision proposed (I10)

**Base as the v1 hub**, with the token contract written so that Ethereum L1 can become the canonical
home later (the same bytecode; the bridge contract's `hubChainId` is a parameter; a migration is a
release from the Base escrow and a deposit to the L1 escrow, both ordinary flows). **If Starknet is a
first-order requirement rather than a destination, the decision flips to Ethereum L1 as hub** and
the gas budget of §6.5 becomes a launch input. This document is written for either; only §6.5 and
§4.3 differ.

### 4.3 Expansion path (I11)

Order of spokes once the hub is live, cheapest trust first:

1. **Ethereum L1** from Base over the canonical bridge (L1 → Base is minutes; Base → L1 is the
   seven-day window; both trust only Ethereum).
2. **Other OP-Stack and Arbitrum chains** — from L1 over their canonical bridges, or directly from
   Base over Superchain interop where it is live (verify maturity at deployment time; treat it as a
   third-party route until then).
3. **Starknet** — from L1 over StarkGate (validity-proof-backed both ways).
4. **Solana** — Wormhole NTT or LayerZero OFT from the hub; adds that network's guardian or DVN
   trust for that spoke only.

Each spoke adds *no* Ycash-side code and *no* change to the escrow: bridged YED on a spoke is
bridged YED on the hub locked in the spoke bridge. Supply on every spoke is visible from the hub, so
the solvency check (§9.1) stays one equation: `Σ escrow cents on Ycash ≥ hub totalSupply + locked`.

---

## 5. The escrow (Ycash side, no protocol change)

### 5.1 Script

```
escrowScript(commitment, roster) =
    <commitment: 32 bytes> OP_DROP
    <k> <Q1> <Q2> … <Qn> <n> OP_CHECKMULTISIG
```

`Q1…Qn` are the roster's 33-byte compressed keys in the sorted order the federation's roster script
uses (development plan D3, D7). The output's `scriptPubKey` is ordinary P2SH.

**ESC-1** `commitment = SHA256("yellowback-bridge-deposit" ‖ hubChainId ‖ recipient(32 B,
left-padded) ‖ nonce(8 B LE))` for a deposit escrow; `SHA256("yellowback-bridge-pool" ‖ hubChainId
‖ epoch(4 B LE))` for a pool escrow (§5.3). Domain tags keep the two spaces disjoint and distinct
from any other hash the federation uses.

**ESC-2 Size and standardness** (the D3 arithmetic, development plan `:404-411`): `37 + 34n` bytes;
n = 9 gives **343 B**, under the 520-byte P2SH push limit (`ref/ycash/src/script/script.h:23`). A
spend's scriptSig with k = 5 is ≈ 712 B, under the 1,650-byte relay limit
(`ref/ycash/src/policy/policy.cpp:93`). Sigops: 9 of the 15 allowed. `OP_DROP` of a 32-byte push is
`MINIMALDATA`-clean and leaves a clean stack. Ycash accepts a P2SH input whose redeem script is not a
standard template (development plan A14, C15), as for vaults.

**ESC-3 Overlay acceptance.** A TRANSFER assigning cents to an escrow output is valid by XFER-1..3
today; the state machine records `Tokens[txid:vout]` for any script
(`ycash-dd/src/yellowback/state.cpp:247-270`). Escrowed YED stays in `supplyCents`: held, not burned;
cap, health and protections unaffected (I1).

**ESC-4 Spending.** As a vault input: built unsigned, each operator adds its `SIGHASH_ALL` ECDSA
signature over the ZIP-243 digest with the roster branch ID (development plan C11, C24), signatures in
roster order. `AddCosignature` / `IsComplete` / `SameExceptSignatures` (`txbuilder.cpp`, SUB-1) apply
unchanged: they operate on a redeem script and a key set, not on the vault template.

**ESC-5 Script family, not script.** T3 (§10.3) replaces the multisig clause with a proof-verifying
clause (a §16 fallback would replace it with a single threshold-signed key). The commitment clause, the address form, the RPCs
and the contracts are unchanged; a migration is a release from the old family to the new (§10.4).

### 5.2 Why the commitment is in the script

The hub recipient must be bound to the deposit by the depositor, on Ycash, at deposit time;
otherwise the operators choose who gets the mint. The three places for 32 bytes in a Ycash
transaction are a second `OP_RETURN` (burns the YED, §2.1), a Sapling memo (YED cannot be shielded),
and the script the YED is paid to. The script is the only one available and the best one: the
recipient is provably part of the output that holds the funds, and an operator who attests a wrong
recipient is contradicted by the chain alone. The cost is one escrow address per deposit — normal
for bridges and exchanges — and it is why the contract, not the operators, issues addresses (§7.1):
the derivation is deterministic from `(recipient, nonce, roster)`, so the user's wallet, the
contract, every operator and any auditor compute the same address.

### 5.3 Pool escrows and change

A release spends deposit escrows and puts YED change (≥ `MIN_OUTPUT` or none, hardening plan H1)
into the **pool escrow** of the current epoch. **ESC-6** The daemon may build a consolidation
TRANSFER (escrow inputs → one pool output) under XFR-6 when spendable escrow outputs exceed a
configured count; it is a release to the pool with no hub counterpart.

### 5.4 Address form and RPCs (node fork)

**I5** D10's Yellowback address is Base58Check(version ‖ key hash) decoding to P2PKH, version bytes
found by exhaustive search to render `ye…`. This plan adds a **P2SH form** over
`HASH160(redeemScript)` with a second version pair found by the same search to render a distinct
two-letter prefix (launch input, §15). `ParseYedAddress` accepts both and returns the matching script
(today P2PKH only, `ycash-dd/src/rpc/yellowbackwallet.cpp:79-84`); `ScriptToYedAddress` renders both;
`yed_validateaddress` reports the form. The address form is what lets `yed_send` and the GUI Send
screen pay an escrow unchanged, and what lets a user compare the address the contract shows with
the one their node derives.

```
yed_escrowaddress <hubChainId> <recipientHex> <nonce> [rosterIndex]
  → { "address", "scriptHex", "commitmentHex", "rosterIndex" }
yed_registerescrow <commitmentHex>            (in-memory hint set, like PendingRedemption)
yed_listescrow [rosterIndex]
  → [ { "txid","vout","cents","commitmentHex","kind":"deposit"|"pool","height","spendable" } … ]
```

`yed_listescrow` matches `Tokens` scripts against `P2SH(escrowScript(c, roster))` for the
commitments it can reconstruct: pool epochs and registered deposit commitments. P2SH hides the
script until spent, so unknown commitments cannot be matched; the daemon, not the node, holds the
deposit list, and `yed_listescrow` is the check on the daemon rather than its source.

---

## 6. Hub contracts (deployed, Solidity)

Upgradeable behind a timelock, pausable, amounts `uint256` cents.

### 6.1 `YellowbackToken`

OpenZeppelin ERC-20 + ERC-20Permit + Pausable. `name = "Ycash Yellowback"`, `symbol = "YED"`,
**`decimals = 2`** (I7: the unit is the cent on both chains; rounding is impossible by
construction). `mint`/`burn` callable by the bridge only. `MAX_SUPPLY` = the Yellowback mainnet
supply cap (100,000,000 cents, spec §3.1). Pause blocks transfers, mint and burn.

### 6.2 `YellowbackBridge`

State: `depositRequests[id] = {recipient, nonce, escrowScriptHash, createdAt}`;
`attestedDeposits[outpoint] = {cents, recipient, attesters, minted}`;
`releaseRequests[id] = {owner, cents, yeAddress(25 B), lockedAt, status, releaseTxid?}`;
`rosterIndex`; `evidenceMode` (T1 attestation | T2 proof, §10); parameters (§6.5).

| Caller | Function | Effect |
|---|---|---|
| anyone | `requestDeposit(recipient)` | allocates `nonce`, derives the escrow address for the current roster, emits `DepositRequested(id, recipient, nonce, escrowAddress)` |
| operator (T1) / anyone with proof (T2) | `attestDeposit(txid, vout, cents, recipient, nonce, height)` / `proveDeposit(batchRoot, proof, leaves)` | on the k-th matching attestation, or on a valid proof, mints `cents` to `recipient` and marks the outpoint |
| anyone | `requestRelease(cents, yeAddress)` | pulls `cents` into a lock, deducts the fee, emits `ReleaseRequested(id, owner, cents, yeAddress)` |
| operator | `attestRelease(id, ycashTxid)` | on the k-th matching attestation burns the locked `cents` |
| anyone | `refundRelease(id)` | after `RELEASE_TIMEOUT` with no release attested, returns the lock |
| operator | `attestRoster(rosterIndex, rosterHash)` | k-th attestation switches address derivation to the new roster |
| owner / emergency admin | `pause`, `unpause`, `setParameter` | circuit breakers |

"k-th matching attestation": k distinct operators the registry reports active, byte-identical
facts. Conflicting attestations are recorded and emitted (`AttestationConflict`) and block action
until the owner resolves them. Replay keys: the outpoint for deposits, the request id for releases.

### 6.3 `OperatorRegistry`, `OperatorVault`

The registry maps each operator's hub account to its Ycash roster key (33 B), roster position and
status. Activation: whitelisted by the owner, staked ≥ `MIN_STAKE` in the vault, a free slot. The
vault is ERC-4626 with a 7-day unbonding delay. Slashing: owner-triggered with three tiers
and a published-evidence requirement (proof-triggered slashing is a §16 fallback, not a rung). Circuit breakers: `pause`
(owner), `emergencyPause` (owner or emergency admin), automatic unpause after a delay if the owner
does not confirm, and `DAILY_MINT_CAP`, which pauses deposits and never releases — a compromised
quorum must always be able to *return* funds and never able to *create* more than a day's worth.

### 6.4 Operator authentication (I8)

Default: by hub account (`isActive(msg.sender)`); the operator's hub key is separate from its Ycash
roster key and protected by whatever account policy the operator chooses. Option, not default: the
EVM verifies secp256k1 natively (`ecrecover`), so an attestation could carry a signature by the
operator's *roster key* over the attested facts, making the two identities one and letting anyone
verify from the roster alone. Left open (§15).

### 6.5 Parameters

| Name | Proposed | Note |
|---|---|---|
| `k / n` | 5 / 9 | equals the federation roster if I12 is taken |
| `DEPOSIT_CONFIRMATIONS` | 24 Ycash blocks (≈ 30 min) | reorg margin before an irreversible mint; the federation's `PRICE_MAX_AGE` is 48 |
| `RELEASE_TIMEOUT` | 4 h | then `refundRelease` is available |
| `RELEASE_FINALITY` | hub-dependent: Base — sequencer-confirmed + 30 min; Ethereum L1 — finalized (≈ 15 min) | how long operators wait before spending escrow against a request; a launch input |
| `MIN_DEPOSIT` / `MAX_DEPOSIT` | `MIN_OUTPUT` / `MAX_OUTPUT` | a deposit is one YED output |
| `MIN_RELEASE` / `MAX_RELEASE` | `MIN_OUTPUT` / 15 × `MAX_OUTPUT` | releases above `MAX_OUTPUT` split across ≤ 15 outputs of one TRANSFER |
| `DAILY_MINT_CAP` | 10 % of `MAX_SUPPLY` | circuit breaker on creation |
| `RELEASE_FEE_BPS` | 10 (0.10 %), min 100 cents | paid in bridged YED to the proposing operator; covers YEC fee and `TOKEN_VALUE` (§8.3) |
| `BATCH_INTERVAL` | 1 h (L1 hub) / per deposit (Base hub) | attestations carry a Merkle root of a block range's deposits when gas matters; leaves are proven by the recipient or a relayer at mint |
| `MIN_STAKE`, staking token | launch input | |

---

## 7. Peg-in: YED → bridged YED

### 7.1 Flow

1. **Request.** The user's client calls `requestDeposit(recipient)`; the contract derives and emits
   the escrow address. The client shows it and recomputes it with the user's node
   (`yed_escrowaddress`); they must match.
2. **Deposit.** `yed_send <escrowAddress> <cents>` or the GUI Send screen. Nothing about this
   transaction is bridge-specific.
3. **Observation.** Every daemon registers the commitment with its node and watches
   `yed_listescrow` / `yed_gettxinfo`; at a clean verdict and `DEPOSIT_CONFIRMATIONS` it attests
   (DEP-1..6), or in T2 the prover produces the batch proof.
4. **Mint.** On the k-th matching attestation (T1) or a valid proof (T2), `cents` are minted to
   `recipient`; `DepositMinted` is emitted.

### 7.2 Operator rules (daemon, each against the operator's own node)

- **DEP-1** Index healthy and at the tip (= RED-0).
- **DEP-2** `yed_gettxinfo(txid)` shows a non-burning verdict and an assignment of exactly `cents`
  to `vout`, whose `scriptPubKey` equals `P2SH(escrowScript(commitment(recipient, nonce), roster))`
  for a `DepositRequested` the daemon saw.
- **DEP-3** `height + DEPOSIT_CONFIRMATIONS ≤ indexTip`.
- **DEP-4** The outpoint is unspent in the index.
- **DEP-5** The escrow's roster is the contract's current or grace-period roster.
- **DEP-6** No conflicting attestation by this daemon for this outpoint; on conflict, halt and
  alert.

### 7.3 Failure table

| Event | Outcome |
|---|---|
| Deposit to an escrow address nobody requested | no `DepositRequested` matches; no attestation; no release ever spends it. **Funds lost.** Client never accepts a typed address (copy/QR only) and recomputes node-side. Stated in §12. |
| Reorg deeper than `DEPOSIT_CONFIRMATIONS` after mint | unbacked bridged YED for that deposit; published; bounded by the caps; roster stake is the recourse |
| Fewer than k operators live | deposits wait; nothing lost |
| Operators disagree | `AttestationConflict`; no action; the operator the chain contradicts is slashed |

### 7.4 Mint directly to the hub

The GUI's Mint screen gains a destination choice: "my wallet" (today) or "hub chain, to
`recipient`". The second runs `yed_mint` and then, once the token output has one confirmation, a
`yed_send` of the minted cents to a freshly requested escrow address — two chained transactions, one
action, with the wallet's own YED never touched. The MINT's token output stays P2PKH to the owner
(spec §3.4); this is a wallet convenience, not a protocol change.

---

## 8. Peg-out: bridged YED → YED

### 8.1 Flow

1. **Request.** `requestRelease(cents, yeAddress)`: the contract locks `cents`, deducts the fee,
   validates the address (REL-1) and emits `ReleaseRequested`.
2. **Finality wait.** Each daemon waits `RELEASE_FINALITY` before treating the request as real.
3. **Proposal.** The proposer for request `id` is the active operator at roster position `id mod
   n` (next position after a timeout if down). It calls `yed_buildrelease [{yeAddress, cents}…]
   <poolCommitment>`: the node selects escrow inputs (hardening plan H1 over `yed_listescrow`
   spendable outputs), adds a YEC fee input from the proposer's wallet, builds the TRANSFER with
   change to the pool, signs the fee input and its roster signature, and returns the hex. One
   TRANSFER may serve up to 15 outputs (REL-3).
4. **Co-signing.** The proposer POSTs the hex to each peer's `/cosignrelease`; each runs
   `yed_cosignrelease <hex> <requests…>` on its own node (XFR-0..9, §9) and returns its signature.
   With k signatures the proposer broadcasts; the hardening plan's H7 guard passes because the
   payload reassigns every input.
5. **Attestation and burn.** At `DEPOSIT_CONFIRMATIONS` with a clean verdict, every operator
   `attestRelease(id, txid)` for each request served; on the k-th the lock is burned; `Released`.
6. **Refund.** After `RELEASE_TIMEOUT` with nothing attested, anyone calls `refundRelease(id)`;
   the lock and the fee return to the owner.

### 8.2 Contract rules

- **REL-1** `yeAddress` is a valid P2PKH Yellowback address for the configured Ycash network
  (Base58Check version bytes and checksum, in Solidity).
- **REL-2** `MIN_RELEASE ≤ cents ≤ MAX_RELEASE`; balance covers `cents`.
- **REL-3** One release attestation names one Ycash txid; several requests may share it.
- **REL-4** `LOCKED → RELEASED | REFUNDED`; no other transitions.
- **REL-5** `attestRelease` on a `REFUNDED` request is recorded and emitted (`LateRelease`) but
  burns nothing; it is an unbacked release the roster answers for (§12).
- **REL-6** (daemon) Never build or co-sign a release for a request within `2 ×
  DEPOSIT_CONFIRMATIONS` blocks of its timeout; leave it to refund.

### 8.3 Fees and the YEC a release costs

A TRANSFER pays `YELLOWBACK_FEE` (1,000 zat) and gives each YED output `TOKEN_VALUE` (10,000 zat);
escrow inputs bring 10,000 zat each, so a one-input, two-output release is 11,000 zat short. The
proposer's wallet supplies a YEC input and takes YEC change (the builder does this for every
TRANSFER, development plan §4.5). `RELEASE_FEE_BPS` in bridged YED reimburses the proposer; at
$0.05/YEC the YEC cost is under a cent, so the fee is a liveness incentive.

### 8.4 Concurrency and timing

Deterministic proposer assignment removes the double-spend race in the normal case;
`yed_cosignrelease` refuses inputs reserved by a release the co-signer already signed and that has
not expired (XFR-7, the analogue of D3's `PendingRedemption`) in the failure case. `nExpiryHeight =
indexTip + MINT_WINDOW` (40 blocks) frees a stuck proposal's inputs in 50 minutes. Normal release:
`RELEASE_FINALITY` + co-signing + one block + `DEPOSIT_CONFIRMATIONS` ≈ **65–75 min** to burn; the
user's YED is spendable after the first confirmation, ≈ 35 min in. §11 brings the user-visible time
to minutes.

---

## 9. Co-sign policy for releases (node fork, `policy.cpp`)

Run inside `yed_cosignrelease` on the co-signer's node against its own index, as RED-0..8 run inside
`yed_cosignredeem` (`ycash-dd/src/yellowback/policy.cpp:82-165`). The daemon passes the hex and the
list of `(requestId, yeAddress, cents)` it believes the transaction serves; the node verifies the
transaction against that list and the chain, never against the hub.

- **XFR-0** Index healthy, non-empty, at the tip. (= RED-0)
- **XFR-1** Well-formed TRANSFER; payload assigns every non-`OP_RETURN` output; `Σ assigned ==
  yedIn` (no burn; contrast REDEEM); every assignment in `[MIN_OUTPUT, MAX_OUTPUT]`.
- **XFR-2** Every YED input is an unspent `Tokens` outpoint whose script is
  `P2SH(escrowScript(c, roster))` for a reconstructible `c` (pool epoch or registered deposit) and a
  roster the co-signer belongs to. No vault, anchor or non-escrow token input.
- **XFR-3** Every YED output is (a) P2PKH to a `yeAddress` in the request list with exactly that
  request's `cents`, each request used once, or (b) P2SH to the **current** pool escrow, at most one.
  For a consolidation (XFR-6) all outputs are (b) and the list is empty.
- **XFR-4** The request list is non-empty (except XFR-6), duplicate-free, and *the co-signer's own
  daemon* has seen a matching final `ReleaseRequested` not near its timeout (REL-6). This is the one
  rule with a hub fact in it; the daemon checks that half before calling the RPC, the node checks
  only internal consistency and the match to the outputs. A daemon that lies to its own node can make
  only its own operator co-sign, never reach k.
- **XFR-5** Standardness and fee as RED-4; YEC inputs and change permitted (unlike REDEEM's C10)
  and ignored by the YED accounting.
- **XFR-6** Consolidation only when spendable escrow outputs exceed `CONSOLIDATE_ABOVE` (daemon
  parameter, default 50) and inputs ≤ 250.
- **XFR-7** No input reserved by an unexpired release this co-signer signed.
- **XFR-8** `nExpiryHeight ∈ [indexTip + 1, indexTip + MINT_WINDOW]`. (= RED-8)
- **XFR-9** Existing signatures verify for the keys they claim (`SameExceptSignatures`, SUB-1); the
  co-signer never signs a transaction it did not fully reconstruct.

Refusals return the rule id and reason, as RED-\* do.

---

## 10. The trust ladder and the proof opcode

The v1 system is federated custody. The value of this plan is that the *same* escrow family, token
and flows admit two upgrades that remove trust without a redesign, and that the second of them,
a proof-verifying opcode on Ycash, removes more trust from **Yellowback itself** than from the
bridge. The rungs are stated so the trust statement (§12) can name which one the system is on.

Principle 4 governs the ladder: each rung must be something an individual can drive alone with a
proof the chain checks. Mechanisms that instead add parties, capital and process — bonded operators
with slashing, threshold-signature networks, external MPC services — are not rungs; they are §16
fallbacks.

### 10.1 T1 — federated attestation (launch)

Evidence of a deposit is k of n attestations; evidence of a release is k of n attestations; escrow
is k-of-n CHECKMULTISIG. A colluding quorum can mint unbacked YED (bounded by the caps) or release
escrow to itself (bounded by the escrow balance). Recourse: stake, visibility, rotation. This is the
honest floor and everything in §5–§9 delivers it.

### 10.2 T2 — the hub verifies proofs of Ycash (no Ycash change)

A prover runs the Yellowback state machine over the Ycash block stream inside a zkVM and produces a
proof that, from a committed index state, the blocks in a range assign the listed `(outpoint,
cents, escrowScript)` deposits. `YellowbackIndexVerifier` on the hub verifies it and `proveDeposit`
mints with no operator involved. Anyone can prove — the depositor, a wallet, a hosted service — and
nothing depends on the prover being honest, because the proof is checked. The statement takes
Ycash block headers as public inputs, so it also proves **cumulative Equihash work from a
checkpoint**: the security assumption becomes the light-client one (an attacker must out-mine
Ycash over the window), weaker on a low-hashrate chain than on Bitcoin, mitigated by
`DEPOSIT_CONFIRMATIONS` and the caps. Recursive proofs make "prove the next block's transition" the
steady-state cost. The index is re-implemented in the zkVM's language and cross-checked against
`ycash-dd` by the existing state-hash tests (`yed_getstatehash`).

T2 makes the **mint side** trustless. The release side still needs the escrow to be spent, and
Ycash script cannot check a proof, so releases remain k-of-n signed until T3.

### 10.3 T3 — a proof-verifying opcode on Ycash (network upgrade)

#### What it is, in plain terms

Today a vault opens when the lock height has passed, the owner signs, **and** 5 of 9 federation keys
sign. The federation's signature has one job: before signing, each operator checks that the
redemption burns enough YED. That check cannot be written in script, because "these inputs are YED
and add up to the required burn" is a fact of the Yellowback index, which script cannot see. The
signature is how the rule reaches the chain.

The opcode gives script one generic instruction: **"check this proof against this verifying key,
bound to this transaction."** The vault script becomes "lock height, owner signature, and a valid
proof". The user's wallet attaches a proof that says, in effect, "run the Yellowback rules over the
Ycash chain up to this block; this transaction burns at least the required amount". The node
verifies the proof in milliseconds, using the same Groth16 verifier it already runs for every
Sapling spend, and never learns what Yellowback is. **No operator is involved, and redemptions keep
working if every operator disappears.**

#### What it buys, in order of importance

1. **Redemption without custodians.** The federation's custody of collateral — the largest trust
   in the development plan's §8.1 ("a colluding quorum of k operators can release collateral
   without a burn") — is gone. What remains is the **price oracle**: the required burn depends on
   the ERR band, which depends on the federation's signed price transactions, so a proof can only
   say "according to the prices on chain, the burn is sufficient". Price signers can make mints
   under-collateralised or redemptions cheaper or dearer, and everyone can compare their number
   with exchanges; they cannot take anyone's collateral and cannot stop anyone redeeming. The
   federation goes from custodian to oracle, and any set of price signers will do.
2. **Bridge release without operators.** The escrow stops being a multisig and becomes a
   covenant: "this output may be spent by any transaction carrying a valid proof that, on the hub,
   a burn of N cents naming Yellowback address A occurred, and this transaction pays exactly N
   cents to A with the rest back to the escrow". The user burns on the hub, produces the proof, and
   releases their own YED. Paired with T2 there are **no operators anywhere**, only provers, and
   anyone can be one. What remains is the consensus of the two chains, the correctness of the
   circuits, and the trusted setup.
3. **A general facility.** The opcode knows nothing about Yellowback. Any application on Ycash can
   use it, and Yellowback's own rules can evolve by circuit versions — each vault commits to the
   verifying key of the rule version it was minted under — without further upgrades.

#### Design rules

- **OP-1 Generic.** `OP_CHECKPROOFVERIFY` (a redefined `OP_NOP`, the usual soft-fork technique;
  Ycash activates by network upgrade, its convention) pops a verifying-key hash, a proof and a
  vector of public inputs; it fails the script unless the proof verifies. Consensus contains no
  circuit, no verifying key and no Yellowback logic.
- **OP-2 Transaction binding.** One public input is fixed by the opcode itself: the ZIP-243
  transaction digest the same way `CHECKSIG` computes it (`SignatureHash`, development plan C24).
  A proof made for one spend cannot be replayed on another. This is `CHECKSIG`'s discipline, not a
  covenant system.
- **OP-3 Chain context, the Sapling way.** A proof about the index or about a hub checkpoint must
  name a Ycash block it is anchored to. Script does not see the chain and must not: script validity
  has to be a pure function of the transaction. Ycash already solves this for Sapling **anchors**: a
  spend names a tree root, and the check that the root exists in the active chain is made at
  transaction-validation time, with reorgs evicting transactions whose anchor vanished. The opcode's
  block-hash public input gets the same treatment, with a minimum depth. No PoW is proven for
  Ycash's own chain; the node has it.
- **OP-4 Verifying key by hash.** The `scriptPubKey` carries only the 32-byte hash of the key, so
  outputs stay small and addresses stay P2SH; the key itself (≈ 400–600 B for a handful of public
  inputs) travels in the `scriptSig` and is checked against the hash. A deserialised, subgroup-
  checked key is cached by hash.
- **OP-5 Cost accounting.** One verification counts as `W` sigops (proposed `W = 200`) against the
  existing `MAX_BLOCK_SIGOPS = 20,000` (`ref/ycash/src/consensus/consensus.h:26`) and the standard
  per-transaction limit, so a block holds at most 100 proofs; public inputs are capped (proposed 8)
  because each adds one G1 scalar multiplication. This is the same tool that bounds `CHECKMULTISIG`.
- **OP-6 Replay for bridge releases.** A hub burn must release once. The bridge contract assigns a
  specific escrow output to each burn request, so the release spends exactly that output and cannot
  repeat; the covenant's statement names the outpoint. Pool escrows are split into request-sized
  outputs by ordinary consolidations (ESC-6).
- **OP-7 Checkpoints.** A bridge escrow's script names the hub checkpoint its proofs start from,
  and checkpoints age. Refreshing one is a spend of the pool escrow into a new script whose proof
  shows the new checkpoint descends from the old. Statements about the hub must cover **finality**,
  not inclusion: Ethereum L1 sync-committee finality (≈ 15 min); a validity rollup adds the hours
  until its state root is proven on L1; an optimistic rollup adds seven days. For T3, **Ethereum L1
  and validity rollups are the realistic counterparties**; Base is not, unless releases wait a week.

#### Performance: what a node pays to verify

The proving side is expensive and the verifying side is not, and the numbers below say by how
much. All of them are against Ycash 4.5.0 as it stands.

| Question | Answer | Basis |
|---|---|---|
| What does one verification cost? | **A few milliseconds** on one core: Groth16 over BLS12-381 is three pairings plus a small multi-scalar multiplication whose size is the number of public inputs. The cost does **not** depend on what was proven — a proof of the whole index over a year of blocks verifies in the same time as a proof of one addition. | the verifier is the same `bellman` code path Ycash's Sapling checks call today (`ref/ycash/src/rust/src/rustzcash.rs:526-582`, `main.cpp:1148,1168`) with a general verifying key instead of the fixed Sapling one |
| What does Ycash already accept? | Every Sapling spend **and** every Sapling output carries a Groth16 proof, verified **one at a time, sequentially**, in `ContextualCheckTransaction`. A 2 MB block (`consensus.h:24`) of 384-byte spends holds ≈ 5,000 proofs, i.e. ≈ 15 s of sequential verification. The network's existing worst case is an order of magnitude larger than the opcode's bounded worst case. | `main.cpp:1148-1180`; no batch verification in this tree |
| Is the opcode's worst case bounded? | Yes, by OP-5: ≤ 100 proofs per block ≈ **0.3 s sequential**, and they run in parallel (next row). | `MAX_BLOCK_SIGOPS`, `MAX_STANDARD_TX_SIGOPS` (`policy.h:26`) |
| Does it parallelise? | Yes. Script checks run on the `CCheckQueue` across `-par` threads (`main.cpp:2824-2937`); an opcode inside `VerifyScript` rides that queue. Sapling proofs today do **not**, so the opcode is verified more cheaply per proof than the shielded pool already is. | `scriptcheckqueue(128)`, `nScriptCheckThreads` |
| Is a transaction verified twice? | No. A proof-verification cache keyed by `(vk hash, proof, inputs, tx digest)` mirrors the signature cache (`ref/ycash/src/script/sigcache.h:19`): a transaction verified at mempool admission is not re-verified when its block arrives, which is the normal case for every block a node did not mine. | same pattern as `CachingTransactionSignatureChecker` (`main.cpp:2354`) |
| Initial sync? | Below the last checkpoint `fExpensiveChecks` is false and proof verification is skipped, exactly as Sapling's is (`main.cpp:2857-2865`); above it, the cache and the parallel queue apply. No change to sync-time behaviour. | `ProofVerifier::Disabled()` |
| Denial of service? | An invalid proof costs ≈ 3 ms to reject versus ≈ 0.1 ms for a bad ECDSA signature. The relay path already rate-limits by sigops, so OP-5's weight bounds the attacker's leverage; an invalid proof is a script failure with the same peer penalty as a bad signature. Subgroup checks on a verifying key (≈ 1 ms in G2) are done once per key hash and cached. | existing misbehaviour scoring |
| Memory, disk, bandwidth? | A proof is 192 B; with inputs and key, an input grows by ≈ 0.7 kB. Under OP-5 that is ≤ 70 kB of a 2 MB block. The caches are bounded like the signature cache. | — |
| And the prover? | Minutes on a workstation for an index transition; the Ethereum-finality circuit is established but heavy (aggregate BLS verification in-circuit) and is where proving services earn a fee. **None of this touches the node**: verification cost is independent of proving cost. | — |

The conclusion is that **verification is not the constraint**. A node that runs the shielded pool
today already performs, at its worst case, far more Groth16 work per block than the opcode could
add under its budget, and does it with less parallelism and no cache. The Phase B9 package includes
the measurement on the Ycash tree that turns "a few milliseconds" into a number, because the Ycash
team should be handed a benchmark, not an estimate.

#### Consensus footprint

- Interpreter: one opcode handler (≈ 100 lines in `src/script/interpreter.cpp`).
- Rust: one FFI wrapping `bellman`'s generic `verify_proof` (≈ 50 lines beside the Sapling checks).
- Sigop accounting: `W` per opcode in `GetSigOpCount`/`GetP2SHSigOpCount` and the standardness
  limits.
- Transaction validation: the anchor-style depth check for the block-hash public input (OP-3).
- Caches: proof cache and verifying-key cache.
- Activation: a network upgrade with a new branch ID, the Ycash convention. No change to the
  transaction format, to Sapling, or to any existing script.

This is the most expensive tier in the workspace's ladder and the opposite of every Tier-0 choice
made so far. It is recorded here because what it buys — a Yellowback whose collateral no quorum
can touch, and a bridge with no operators — is exactly the property the whole project exists to
deliver, and because the escrow family (ESC-5) and the vault script are designed not to preclude it.

#### Compared with enshrining the index (development plan §9)

| | Enshrine the overlay in consensus | Generic proof opcode |
|---|---|---|
| What consensus learns | the Yellowback rulebook, forever | a verifier; nothing about Yellowback |
| Who computes | every node runs the index during validation | the user (or any prover); the node verifies |
| Rule upgrades | another network upgrade each time | a new circuit and verifying key; vaults choose their version |
| Removes custody of collateral | yes | yes |
| Removes bridge operators | no (facts about other chains still need signers) | yes, with proofs that cover the hub's finality |
| Other applications | none | any |
| Residual trust | price oracle | price oracle, circuit correctness, trusted setup |
| Node cost | index CPU and disk on every node | milliseconds per proof, bounded and cached |

The opcode dominates on every row but one (trusted setup, which Sapling already accepted), so this
plan proposes it as the path and treats §9 enshrinement as the alternative if the Ycash team prefers
a Yellowback-specific rule to a general facility.

### 10.4 Migrating between rungs

Each rung changes the escrow *family* or the *evidence mode*, never the token or the flows. A move is
a release from the old family's pool escrow to the new family's pool escrow (a consolidation under
XFR-6 with the new pool as destination), a `setEvidenceMode` on the bridge, and a roster or verifier
attestation. Deposits in flight complete under the mode they were requested in. For vaults, T3
applies to vaults minted after activation; existing vaults keep their federation clause until they
are redeemed, so nothing retroactive is required.

---

## 11. Liquidity layer: atomic swaps on top of the peg (I13)

Ycash 4.5.0 ships hash time-locked contracts as P2SH with wallet RPCs
(`ref/ycash/src/script/atomicswap.cpp:24-46`; `ref/ycash/doc/atomic-swaps.md`). A swap is an
*exchange* between two holders, not a peg: someone must already hold bridged YED to swap it. So it is
not an alternative to §5–§9; it is the layer that makes them fast. **Liquidity providers** hold
inventory on both chains and swap with users atomically in minutes; the federation mints and burns
only when a provider rebalances, in bulk, on the hour-scale path. Users never touch an escrow address
or wait for attestations; providers earn a spread and carry inventory risk; the operators' workload
and attack surface shrink to a few large flows. Because both legs are the same dollar, the
free-option problem of cross-asset swaps is absent.

Two adaptations are mandatory:

- **YED-aware claim and refund.** The shipped `claimswap`/`refundswap` spend the HTLC output with no
  payload, which for a YED output is a **burn** (IN-1..3). New `yed_claimswap`/`yed_refundswap`
  build the spend as a TRANSFER with the payload and `TOKEN_VALUE` outputs. Tier 0, node fork.
- **A SHA256 hashlock variant.** The shipped script is fixed to HASH160, which the EVM has only at
  high gas (RIPEMD-160 precompile exists on L1 but not everywhere); `OP_SHA256` is available in
  Ycash script and matches `sha256` on every EVM chain. The YED HTLC uses SHA256; timelocks are
  asymmetric with the hub side expiring first.

Phase B6 in §14.

---

## 12. Trust statement and threat model

### 12.1 Trust statement (to be published verbatim; the bracketed rung is filled in at launch)

Bridged YED is a **[T1: federated custody / T2: proof-minted, federated release / T3: proof-secured
in both directions]** representation of Ycash Yellowback (YED).

- Enforced by Ycash consensus: escrowed YED cannot move without k of n roster signatures.
- Enforced by every Yellowback-aware node deterministically: what the escrow holds, and that every
  release is a valid YED transfer.
- Enforced by the hub contracts: bridged YED is minted only on [k of n operator attestations / a
  verified proof of the Yellowback index] of a deposit, burned only on k of n attestations of a
  release, capped by the Yellowback supply cap and a daily mint cap, and refundable to the user if a
  release is not attested in time. [T3: escrow is released by a proof of the hub burn that any
  user can produce; no operator signs.]
- Enforced by each operator's mechanical policy (XFR-0..9, DEP-1..6, REL-6): releases go only to
  the addresses users named, for the amounts they locked.
- **Therefore [T1]:** a colluding quorum of k operators can mint bridged YED without a deposit
  (bounded per day and in total) or release escrowed YED to itself (bounded by the escrow balance).
  **[T2]:** a colluding quorum cannot mint without a deposit but can still release escrow to itself.
  **[T3]:** there is no quorum; deposits, releases and vault redemptions each rest on a proof the
  user supplies and every node checks. [T1/T2: A roster with fewer than k live operators halts
  deposits and releases; locked release requests refund automatically; escrowed YED waits.] Nothing the operators do can create YED
  on Ycash, move a user's un-escrowed YED, or affect the overlay's accounting. **A deposit sent to an
  escrow address that was not issued by the contract is unrecoverable.**
- **What remains at T3** is the price oracle (it can misprice, it cannot take collateral or block a
  redemption), the correctness of the circuits, the trusted setup, and the consensus of the two
  chains. [T1/T2: T3 is a network upgrade on Ycash (§10.3); this statement does not claim it.]

### 12.2 Threat model

| Threat | Outcome (T1) | Mitigation | At T2 / T3 |
|---|---|---|---|
| k operators mint without deposit | unbacked bridged YED ≤ `DAILY_MINT_CAP`/day, `MAX_SUPPLY` total | solvency check public and continuous (§9.1); slashing; roster diversity | T2: impossible, mint requires a verified proof |
| k operators release escrow to themselves | loss ≤ escrow balance | every release names a `yeAddress` on chain; attributable to the k signers | T2: unchanged; T3: impossible, there are no signers |
| < k operators live | halt; locked releases refund; deposits wait | n = 9, k = 5; runbook | T3: no effect; users prove alone |
| Hub reorg / dropped tx after operators released | unbacked release | `RELEASE_FINALITY`; REL-6 | same |
| Ycash reorg after mint | unbacked bridged YED for that deposit | `DEPOSIT_CONFIRMATIONS`; caps | same (light-client assumption in T2) |
| Deposit to a non-issued escrow address | permanent loss of that deposit | client never accepts typed addresses; node-side recomputation; stated | same |
| Contract bug | up to everything bridged | audit before mainnet; pause; timelocked upgrades; caps | same |
| Daemon compromised (not node) | one false attestation; lies to own node | one < k; XFR-4 split | same |
| Node wallet compromised | one roster key | < k; rotation | same |
| Rotation mishandled (escrows unswept) | old roster keeps custody of unswept outputs | sweep checklist; solvency alert | same |
| Escrowed YED spent as YEC by an operator wallet | that YED burned | impossible: a partially owned multisig is never `IsMine` (`ref/ycash/src/script/ismine.cpp:88-96`); H7 guards raw sends | same |
| Spoke bridge (NTT/OFT/canonical) failure | bridged YED on that spoke stranded or unbacked | per-spoke caps; the hub is unaffected; spoke chosen cheapest-trust-first (§4.3) | same |

### 12.3 Why anyone holds YED on the hub

On Base, YED sits next to USDC. Its case is the collateral and the base layer: a dollar backed by
over-collateralised YEC vaults whose rules are enforced by Ycash consensus and readable by anyone,
with no issuer who can freeze a Ycash balance. The bridged form tempers that honestly — the hub
contract can pause and has caps — and the trust statement says so. The plan's answer is the ladder:
each rung narrows what the bridge can do to a holder until, at T3, it can do nothing.

---

## 13. Decisions proposed (I1–I18)

| # | Decision | Reason |
|---|---|---|
| I1 | The Ycash index is the ledger of record; every off-Ycash YED is escrowed YED | §1 |
| I2 | One bespoke hop to one EVM hub; all other chains over standard rails | §1, §4.3 |
| I3 | The hop's trust is upgradable in place along T1 → T2 → T3 | §10 |
| I4 | Chain interpretation and roster signing in the node; other-chain talk and coordination in supplemental software; value in contracts | §3 |
| I5 | Add a P2SH form of the Yellowback address (D10 extension) | usability from unchanged `yed_send`; user-side verification |
| I6 | The contract derives and issues escrow addresses; the user's node recomputes them | operators cannot substitute a recipient |
| I7 | Bridged YED has 2 decimals, symbol `YED` | the cent is the unit on both chains |
| I8 | Operators authenticate by hub account; roster-key `ecrecover` left as an option | §6.4 |
| I9 | Sister repository `yellowback-bridge` for contracts, daemon, client, monitoring | keeps the fork diff reviewable |
| I10 | Base as v1 hub, L1-migratable; Ethereum L1 if Starknet is first-order | §4.2 |
| I11 | Spokes in the order L1 → OP-Stack/Arbitrum → Starknet → Solana | cheapest trust first |
| I12 | Propose the Yellowback federation as the initial roster | already runs the index and co-signs YED; alternative: distinct roster with overlap |
| I13 | Atomic-swap liquidity layer as a phase, with YED-aware claim/refund and SHA256 hashlock | §11 |
| I14 | The daemon holds no roster key and signs nothing on Ycash | the node's rules are the last line |
| I15 | Releases never burn YED; consolidations are releases to the pool | XFR-1 |
| I16 | Deterministic proposer (`id mod n`) with expiry-based input freeing | §8.4 |
| I17 | The proof opcode (T3) is the destination; T2 (hub-side proofs) is the step that needs no Ycash change; operator bonding and signer networks are §16 fallbacks, not rungs | §10; Principle 4 |
| I18 | Mainnet only after an audit and a testnet season with the federation | §14 |
| I19 | Prefer "an individual proves, the chain verifies" over coordination-heavy mechanisms | Principle 4 |
| I20 | Package the opcode as a general Ycash facility with a benchmark, a spec and a ceremony plan, leading with what it buys for redemption, not for the bridge | §10.3; the Ycash team decides |

---

## 14. Work plan

| Phase | Deliverable | Where | ≈ size | Exit |
|---|---|---|---|---|
| **B0 — Spec** | This document DECIDED; §15 answered; P2SH address bytes found; hub chosen | docs | — | development plan revision entry cross-referencing I1–I18 |
| **B1 — Node** | `EscrowScript`, P2SH address form, `yed_escrowaddress`, `yed_listescrow`, `yed_registerescrow`, `yed_buildrelease`, `yed_cosignrelease`, XFR-0..9; unit tests; functional test `yellowback_escrow.py` | `ycash-dd` | 900 + 600 test | tests green; `make diff` shows no consensus files |
| **B2 — Contracts** | `YellowbackToken`, `YellowbackBridge`, `OperatorRegistry`, `OperatorVault`; Foundry tests for every rule, cap, pause, refund, conflict; escrow-derivation vectors shared with B1 | sister repo | 2,000 Solidity + tests | tests green; vectors match the node |
| **B3 — Daemon and client** | operator daemon, CLI client, monitoring; end-to-end on the one-laptop devnet (`ycash-dd/contrib/yellowback/devnet`) plus a local EVM node | sister repo | 3,000 | deposit → mint → release → burn; refund path; conflict path |
| **B4 — Testnet** | Base Sepolia (or Sepolia L1) + Ycash testnet with the testnet federation; runbooks; solvency dashboard; external audit of B2 | ops | — | four weeks without a solvency deviation; audit findings closed |
| **B5 — Clients** | web client; YecWallet "Bridge" screen and mint-to-hub (§7.4) behind a setting | sister repo; `yecwallet-dd` | 1,500 | QTest; devnet run |
| **B6 — Swap layer** | `yed_claimswap`/`yed_refundswap`, SHA256 HTLC variant, hub HTLC contract, provider daemon, swap client | `ycash-dd`; sister repo | 1,500 | atomic swap round-trip on devnet; refund on timeout |
| **B7 — Mainnet (T1)** | deployment; roster ceremony; trust statement published verbatim; first spoke (L1) | ops | — | — |
| **B8 — T2** | zkVM re-implementation of the index; cross-check by state hash; `YellowbackIndexVerifier`; `proveDeposit`; prover library | sister repo | research → 5,000 | proof of a devnet block range verifies on the hub; state hashes match `ycash-dd`; trust statement moves to the T2 text |
| **B9 — T3 package** | for the Ycash team: a ZIP-style specification of `OP_CHECKPROOFVERIFY` (OP-1..7); a **benchmark on the Ycash tree** (per-proof verification, worst-case block under OP-5, cache hit rate, sync-time impact) against the Sapling baseline; the redemption circuit and the hub-finality circuit with test vectors; a trusted-setup ceremony plan modelled on Sapling's; the migration plan of §10.4 | `ycash-dd` (a branch that is **not** `feature/digidollar`), sister repo | 1,500 + circuits | the package is reviewable without reference to Yellowback; numbers replace estimates |
| **B10 — T3 activation** | the network upgrade, if accepted; vault script v2 (lock height, owner, proof); escrow covenant; wallet prover integration; bridge `assignEscrowOutput` (OP-6) | Ycash network upgrade; `ycash-dd`; `yecwallet-dd`; sister repo | — | a user redeems a vault and releases escrow on testnet with no operator running |

B1 and B2 are independent once B0 fixes ESC-1 and the address bytes.

---

## 15. Launch inputs and open questions

- Hub: Base or Ethereum L1 (I10) — decided by whether Starknet is first-order.
- P2SH Yellowback address version bytes (exhaustive search as D10).
- Roster: the federation (I12) or a distinct set; n and k.
- `RELEASE_FINALITY` per hub; `BATCH_INTERVAL` if L1.
- Operator authentication: hub account or roster-key `ecrecover`.
- Staking token, `MIN_STAKE`.
- Daemon language (Python, as `contrib/yellowback/`, unless EVM tooling argues for TypeScript).
- Whether `requestDeposit` charges a spam-deterrent fee (proposed: none; per-account rate limit).
- Maximum age of escrow outputs before consolidation (bounds the commitments operators track).
- zkVM choice for T2 and whether the index re-implementation should be the reference for a future
  Rust `ycashd` component.
- Opcode parameters for the B9 package: sigop weight `W`, public-input cap, minimum anchor depth,
  verifying-key size limit; whether keys are carried in the `scriptSig` (OP-4) or registered by
  hash in a consensus table.
- Which circuit proof system: Groth16 (smallest proof, trusted setup, what Ycash has) or a
  universal-setup system with ≈ 1 kB proofs if the team prefers one ceremony for all circuits.

---

## 16. Considered and rejected

- **Operator bonding with proof-triggered slashing** (bond ≥ escrow; a hub contract slashes on a
  proof of an unauthorised release). It secures the release direction with zero Ycash change.
  Not taken, by Principle 4: it adds capital lock-up, a slashing
  process that needs governance, and a bridged supply capped by what operators will stake, to
  secure something the proof opcode secures with no parties at all. Kept as the **fallback if the
  network upgrade is refused**.
- **Threshold-ECDSA signer sets or external MPC signing networks** for the escrow key. Widen the
  quorum beyond the ≈ 14-key P2SH limit without touching Ycash, at the cost of an intricate
  protocol or another network's trust. Same verdict: fallback only.
- **A bespoke hop to Starknet first.** The design is chain-agnostic, but Starknet has the least
  third-party messaging support and a smaller stablecoin ecosystem, so as a *hub* it strands YED; as
  a *spoke* from L1 it is reached for free over StarkGate, and for T3 it is among the best
  counterparties. A destination and an endgame counterparty, not the hub.
- **Reusing the shielded-YEC bridge machinery.** An earlier internal design exists for bridging
  *shielded YEC* to Starknet: a Sapling escrow whose spend
  authority is a FROST threshold key on Jubjub, deposits identified by a Starknet recipient in the
  Sapling memo, releases via adaptor signatures verified by a Jubjub contract, and a peg-in path
  that verifies a proof of block-header hash and merkle inclusion. None of its Ycash-side machinery
  transfers: YED cannot be shielded, so there is no memo, no viewing key and no Sapling spend to
  threshold-sign; Ycash transparent script has ECDSA only, so FROST cannot sign an escrow spend; and
  an inclusion proof cannot show that YED arrived. Its Starknet-side patterns — staked operator
  registry, pausable bridge-only token, request-lock-timeout-refund, event-driven daemon,
  Prometheus monitoring — are adopted here in Solidity.
- **Issuing YED natively on the hub against Ycash vaults.** Collapses into I1 (§1): the mint is on
  Ycash and the token goes to escrow; anything else fragments supply and breaks health.
- **A zero-knowledge inclusion proof for deposits.** Proves a transaction is in a block, not that
  YED moved. T2 proves the right statement instead.
- **A new payload type carrying the recipient.** Requires every Yellowback node to upgrade first
  (D23); the script commitment achieves the binding with zero protocol change.
- **A second `OP_RETURN` for the recipient.** Burns the YED.
- **Adaptor signatures for atomic peg-out.** ECDSA adaptor signatures exist but are intricate and
  the gain over lock-then-burn-on-attested-release with refund is small. §11 provides atomicity
  where users feel it.
- **A single escrow address with an off-chain recipient registry.** Operators would choose the
  beneficiary.
- **Making the node talk to the hub.** Bloats the fork diff and puts a chain client in
  consensus-adjacent software; §3.
- **More than two decimals.** Diverges from the cent and invites rounding at release.
- **STARK-family proofs on Ycash.** Tens of kilobytes; do not fit a transaction. Groth16 over
  BLS12-381 is the only family Ycash could verify at transaction scale, and it already does for
  Sapling (§10.3).
