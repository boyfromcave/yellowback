# Yellowback post-quantum — SLH-DSA vault owners, Falcon YED holders, one opcode

**Revision 3 (2026-10-10), in implementation; byte layouts frozen in [`yellowback-quantum-spec.md`](yellowback-quantum-spec.md), which wins over §4 where they differ.** A delta on the
[upgrade plan](yellowback-upgrade-plan.md) (revision 2, §15) and the
[in-term claims plan](yellowback-in-term-claims-plan.md), on branch **`upgrade/quantum-vaults`** in every
repository that changes, cut from each repository's `upgrade/vault` (local only until the owner says to push). Decided in principle by the owner on
2026-10-10 after the research in `research_notes/Falcon post quantum Ycash integration/` and its report
`reports/Falcon post quantum Ycash integration.md` (both workspace-local, untracked). Items are **Q-\*** (rules),
**D-Q-\*** (decisions) and phases **Q0–Q8**. The node lines go first (`ycash-dd`, then `ycash6` as the port);
the clients follow in Q7.

**In one sentence:** every vault — YED and bridge — is owned by a post-quantum key (SLH-DSA, a final NIST standard), every
YED balance is held behind a post-quantum key (Falcon-512 when its standard is final, SLH-DSA until then), both
through **one new opcode** that verifies a hash-committed post-quantum public key over the existing ZIP-243
sighash; the attestor set, the bridge guardians, plain YEC and Sapling are **not** changed.

## Execution status (authoritative; update as work lands)

Legend: `[x]` done and verified on the integration tree, `[~]` in flight (agent / branch), `[ ]` not started.

| Phase | ycash-dd | ycash6 | clients / other |
|---|---|---|---|
| Q0 decide and specify (§2, §4); library spike; golden vectors from a reference implementation | `[x]` spec + `pq_vectors.json` | — | `[~]` Python framework reproduces them |
| Q1 PQ verification library in the node (`src/crypto/pq/`), unit tests, benchmarks | `[x]` slhdsa-c 174c02e + PQClean falcon-padded-512 0586a82; ACVP/KAT green; Python framework `q/pyfw` merged; Falcon SHAKE no-malloc patch | `[x]` ported byte-identical (Makefile layout adapted to 6.20.0's libbitcoin_script) | — |
| Q2 `OP_CHECKPQSIG` in the interpreter, sigop cost, activation gate — **consensus review gate** | `[x]` `q/op` merged after reviews A+B and delta re-reviews (one PQ check per EvalScript, `pqFalconHeight`) | `[x]` port merged after reviews A+B (6,641-case cross-line corpus identical) | — |
| Q3 templates: `TX_PQPKH`, PQ owner variant of V and I, standardness and policy limits — **review gate** (`src/script/standard.cpp`, `src/vault/template.cpp`) | `[x]` merged aa0fd3812 (reviews A+B, fixes q/fix3) | `[x]` port merged 1b023d1d6 (reviews A+B; cross-line 71/71 + 597/597 identical; PQ lookahead) | — |
| Q4 YED module: MINT payload, PQ-only mints, PQ holder scripts, token index, RPC contract (`rpcversion` 7) | `[x]` merged aa0fd3812 (reviews A+B + delta re-reviews; TOK-PQ, TX_PQCHANNEL, rpcversion 7) | `[x]` port merged 1b023d1d6 (reviews A+B; cross-line 71/71 + 597/597 identical; PQ lookahead) | lightwalletd proto `[ ]` |
| Q5 node wallet: PQ keystore, seed derivation, signing, size-priced fees | `[x]` merged aa0fd3812 (reviews A+B) | `[x]` port merged 1b023d1d6 (reviews A+B; cross-line 71/71 + 597/597 identical; PQ lookahead) | — |
| Q6 tests, devnet, walk, roles, fuzz, DoS measurement, CI, cross-line vector identity | `[x]` DoS measured (doc/yellowback-pq-dos.md), devnet walk + roles with Falcon, PQ sigcache, zmq race fixed, CI green | `[x]` walk + roles, CI green | — |
| Q7 clients: YecWallet, YEW, lightwalletd, chain-viz, x402, yb-calibration | — | — | `[x]` on each quantum branch, tested vs ycash-dd: hawkeye f0f5691→cdc95ef, YEW ca3961f+5319d9a, lightwalletd ef70570, chain-viz dfbef2b, YecWallet ee8b19f, x402 c87a987, yb-calibration 855faaa; all clients also pass against the ycash6 quantum node (2026-10-11); CI green on GitHub for all but x402 (fix in progress) |
| Q8 release: gate pass, FIPS 206 check, activation decision (D-Q-10), release line version | `[ ]` | `[ ]` | — |
| Fees: D-Q-23..D-Q-26 fee restructure — protocol fee in dollars at the stored `pMint`, `maxMint` $100,000, supply cap on the circulating supply, network fee in $/KB, `rpcversion` 8 (`yellowback-quantum-fees-spec.md`, delta `yellowback-quantum-fees-rpc-delta.md` rev 2) — **review gate** (module rules) | `[x]` `q/fees` @ 430002b16 (`wt/q-fees`), reviewed A+B with fix-ups (M-1, A-2..A-7, L-1, N-3, MINT-8′ lower bound) and D-Q-26; not yet merged into the integration tree | `[ ]` port pending | `[ ]` clients pending (rpcversion 8: YecWallet, YEW, lightwalletd, chain-viz, x402); yb-calibration policy constants `[~]` `q/fees` |

### Log

- 2026-10-11: **fee restructure (D-Q-23..D-Q-26) done and reviewed on ycash-dd** (`q/fees` @ 430002b16, not yet merged):
  FEE-1′/RED-3′/IT-9′ in dollars at `VaultRecord.pMint` (schema 9), MINT-6 on the circulating supply with MINT-6b,
  RED-5′, `maxMint` $100,000, the $/KB network fee (max of windows, none under a halt; `-yellowbackmaxtxfee` 10 YEC
  ceiling; plain PQ shares the cap), `rpcversion` 8. Workspace follow-ups: the contract delta reconciled to rev 2
  (`--check-fees` clean on a copy of the node doc), the fees spec's §5 implementation record, mapping §22 rows,
  yb-calibration's policy constants. Pending: the ycash6 port, the clients, and the owner item on class C and
  MINT-6 (fees spec §5.2).

- 2026-10-11: **all Q0–Q7 work merged and pushed** on both node lines and every client; GitHub CI green on every
  `upgrade/quantum-vaults` branch. Since Falcon day one: PQ signature cache (reviewed A+B), Q6 devnet (walk `pq`/`falcon`
  steps, roles with PQ personas, Falcon signer in the Python framework), the inherited ZMQ publisher race fixed (still
  present on `upgrade/vault`/`harden/yellowback` — owner to decide), chain-wide `sq…` addresses with the PQ address index
  (reviewed A+B both lines) and their review follow-ups. Remaining before Q8: the owner's release decisions (§9).

- 2026-10-11: **Falcon from day one merged on both lines** (ycash-dd 8119e2a10, ycash6 44c4f48bc; `pqFalconHeight = 0`
  mainnet/testnet; Falcon audit F-1/F-6) after Fable reviews A+B (17/17 cross-line verdicts identical); pushed with
  the ycash-dd follow-ups and the Q6 DoS tooling. All ten repos' quantum branches were green on GitHub before this push.

- 2026-10-10: revision 1 written from the research; owner decided D-Q-1, D-Q-3..D-Q-9 in discussion; D-Q-2
  (Falcon timing) and D-Q-10 (which upgrade carries it) are the open decisions (§9).
- 2026-10-10: **revision 2**, owner decisions before implementation: D-Q-10 **ride `UPGRADE_VAULT`**; D-Q-1
  widened — **every vault's owner is PQ-only** (bridge vaults too; one owner shape in the V/I templates, no
  secp256k1 owner variant); D-Q-2 build SLH-DSA and Falcon, Falcon behind `pqFalconActive` (timing still at Q8);
  D-Q-14..D-Q-18 added (library, review gate, fee default, publishing, scope Q0–Q7). Branch name
  `upgrade/quantum-vaults` cut locally in ycash-dd, ycash6, yecwallet-dd, lightwalletd-dd, yew, chain-viz,
  x402-ycash, hawkeye (from `origin/upgrade/vault`) and yb-calibration (from `origin/main`); integration
  worktrees `wt/q-dd`, `wt/q6`. No `librustzcash6` branch (no new branch ID).
- 2026-10-10: **revision 3**, Q0 spec frozen (`yellowback-quantum-spec.md`): scheme pushed as `OP_1`/`OP_2` so
  `TX_PQPKH` is **35** bytes; payload version `0x04`; PQ address versions `ye` 0x56BF / `yt` 0x571E / `yr` 0x5710
  (53 characters); **no consensus sigop count** for `OP_CHECKPQSIG`, 20 as policy; HKDF seed derivation on both
  lines; `TOK-PQ` once Falcon is active. Agents: `q/pqlib`, `q/op`, `q/pyfw` in flight.

## 1. What changes, in one page

A cryptographically relevant quantum computer breaks every elliptic-curve key on Ycash: the secp256k1 keys behind
`s1…` and `ye…` outputs and the vault owner keys, the attestor and guardian keys, and Sapling's spend authority
and proof soundness. A post-quantum **signature** repairs exactly one of those: spend authority of a key whose
public key is not on the chain until it is used. This plan uses that repair where it protects the most value for
the least consensus change.

1. **Vault owners become post-quantum (D-Q-1).** The owner key is the master key over a vault's locked YEC: it
   redeems (selector 2), it recovers once the attestor set is dormant (selector 3), and under R1 it is the backstop
   if every other key fails. It signs a handful of times over a position's life, so it takes the heavy,
   fully standardized scheme: **SLH-DSA-SHA2-128s** (FIPS 205, final since 2024-08-13), 7,856-byte signatures,
   32-byte public keys, no side channel of Falcon's kind. The V and I templates get an owner variant whose
   owner slot is a 32-byte hash of the owner's PQ key in place of the raw 33-byte secp256k1 key, verified by the
   new opcode; selectors 1 (unlock) and 4 (claim) do not change by a byte. **Every vault is PQ-only** (owner,
   rev 2): the V and I templates have exactly one owner shape, the PQ one, for YED and bridge vaults alike — the
   secp256k1 owner slot of upgrade plan §15.3 is replaced, not kept beside it. No vault is live on any public
   network, so nothing migrates.
2. **YED holders become post-quantum (D-Q-2).** YED is held in transparent outputs to a `ye…` address and spent
   with a scriptSig; no OP_RETURN carries a transfer. The holder key signs every transfer, so it takes the small
   scheme: **FN-DSA-512 (Falcon-512)**, 666-byte signatures, 897-byte public keys, verification cheaper than
   ECDSA. Its standard (FIPS 206) is not final, but the owner decided (D-Q-2, 2026-10-10) that Falcon goes live
   **from day one** with SLH-DSA, at the vault activation (`pqFalconHeight = 0` on mainnet/testnet); the opcode is
   **scheme-agnostic**, so a final FN-DSA that differs can be added later as scheme 0x03 (§9 item 6). A YED holder output is 35 bytes (hash-committed); the cost moves to the spend.
3. **One opcode, `OP_CHECKPQSIG` (0xc2), above `OP_NOP10` (D-Q-3).** It pops a scheme identifier, the key hash, the
   public key and the signature, the last two as several ≤ 520-byte pushes it reassembles, so the 520-byte element
   limit (`MAX_SCRIPT_ELEMENT_SIZE`) is **not** raised. The message is the ZIP-243 sighash `OP_CHECKSIG` already
   uses. Gated on the activation like 0xc0/0xc1; `SCRIPT_ERR_BAD_OPCODE` before it.
4. **Bigger transactions, priced by size, bounded by what Ycash already bounds (D-Q-7).** A Falcon spend is
   ~1.7 KB, an SLH-DSA spend ~8.1 KB, against ~230 B transparent and ~2.3 KB Sapling. The 2 MB block and the
   10,000-byte script already bound them; a full block of PQ spends verifies faster than a full block of Sapling
   spends. What changes is **policy**: the 1,650-byte standard scriptSig limit gains a PQ case, the opcode counts
   as 20 sigops toward `MAX_BLOCK_SIGOPS`, and the wallets and relay price PQ transactions **per kilobyte** instead
   of the flat `DEFAULT_FEE`, so a miner is paid for the bytes and block space is never cheap to fill. No fee rule
   enters consensus.
5. **Not in this plan (D-Q-5, D-Q-6, D-Q-11).** The attestor set (`OP_CHECKSETSIG` identifies members by ECDSA
   key *recovery*, the state is keyed by the 33-byte member key, acts are capped at 1,200 bytes) and the wYEC
   guardians (secp256k1 on both chains, no Falcon precompile on Ethereum) stay elliptic-curve: the PQ owner's
   recovery path is the backstop if they break. Sapling is a pool-replacement problem that Zcash is solving
   (Ironwood recoverability live 2026-07-28; Tachyon with ML-KEM; Shielded Labs' Epoch, end-2027) and ECC declined
   a Sapling variant; Ycash adopts Zcash's PQ pool on the ycash6 line when it ships. A PQ address for plain YEC
   (`yq1…`) rides the same opcode and is a separate, later decision.

## 2. Decisions (owner, 2026-10-10 unless marked pending)

| # | Decision | Value |
|---|---|---|
| D-Q-1 | Vault owner keys are post-quantum | **yes, every vault (rev 2)**: SLH-DSA-SHA2-128s owners; the V/I templates have only the PQ owner slot (consensus, rule V-1), so YED and bridge vaults are both PQ-only; the MINT payload carries `ownerScheme ‖ ownerHash` |
| D-Q-2 | YED holder keys are post-quantum; which scheme, when | **Falcon from day one (owner, 2026-10-10, final): SLH-DSA vault owners and Falcon-512 YED holders/transfers both go live at the vault activation, before FIPS 206 is final.** `pqFalconHeight = 0` on mainnet and testnet (active with `UPGRADE_VAULT`); TOK-PQ binds from the first block, so P2PKH YED holders never exist on mainnet; wallets default to Falcon holders. **Risk accepted:** FIPS 206 may change Falcon's encodings; mitigation is the scheme-agnostic opcode — a later upgrade adds the final FN-DSA as scheme 0x03 beside 0x02, and holders migrate (vault owners are SLH-DSA, final, unaffected). Regtest keeps `-pqfalconheight` for testing both regimes |
| D-Q-3 | One scheme-agnostic opcode | **`OP_CHECKPQSIG` = 0xc2**, chunked pushes, no change to `MAX_SCRIPT_ELEMENT_SIZE` or `MAX_SCRIPT_SIZE` |
| D-Q-4 | Keys are hash-committed | **yes**: 32-byte `SHA256(schemeId ‖ pk)` in every scriptPubKey and in the MINT payload; the public key appears only in the spending scriptSig |
| D-Q-5 | Attestor set and bridge guardians | **stay secp256k1** in this plan (bridge vault *owners* are PQ per D-Q-1; the guardians' and attestors' keys are not) (recoverable-signature design, set-state layout, Ethereum coupling); recorded as the next candidate after Falcon is final |
| D-Q-6 | Sapling / shielded privacy | **not addressed here**; adopt Zcash's post-quantum pool on `ycash6` when it ships (`docs/plans/ycash6/` to track) |
| D-Q-7 | Fees and relay | **policy only**: per-kilobyte pricing in the wallets, standard scriptSig limit gains a PQ case, sigop cost 20 per `OP_CHECKPQSIG`; nothing in consensus |
| D-Q-8 | Branch | **`upgrade/quantum-vaults`** in every changed repo, cut from `upgrade/vault`; worktrees `wt/q-dd`, `wt/q6`, `wt/q-<client>`; agent branches `q/<name>`; merges back to `upgrade/vault` when the gate passes (or never: the line is feature work) |
| D-Q-9 | Order | **nodes first**: `ycash-dd` builds each chunk, `ycash6` ports it with byte-identical vectors; clients in Q7 |
| D-Q-10 | Which network upgrade carries it | **ride `UPGRADE_VAULT` (rev 2)**: `0x6d5b7a31`, `SCRIPT_VERIFY_VAULT`; no new branch ID, no `librustzcash6` change; quantum ships with vault or not at all |
| D-Q-11 | A PQ address for plain YEC (`yq1…`) | ~~deferred~~ **superseded by D-Q-20**: same opcode, same `TX_PQPKH` template, a wallet/address decision for a later revision |
| D-Q-20 | A PQ address for plain YEC (owner, 2026-10-10; **reverses D-Q-11**) | **yes, prefix `sq…`** (testnet `tq…`, regtest `rq…`; Base58Check versions 0x4DD9 / 0x4F61 / 0x4C51 over `scheme ‖ keyhash`, 53 characters): the same `TX_PQPKH` script as a PQ `ye…` address, decoded chain-wide by `key_io` so `getnewaddress`, `sendtoaddress`, `validateaddress` and `z_sendmany` recipients accept it. `yq1…` rejected as too close to `ys1…`. Built after the Q3–Q5 merge |
| D-Q-21 | Mainnet YED address prefix on this line (owner, 2026-10-10; supersedes D10's `ye…` here) | **`yb…`** (for Yellowback): 20-byte P2PKH holder Base58Check version **0x1FDD** (the only value; 35 chars), 33-byte PQ form **0x56AB** (53 chars). Testnet `yt…` (0x2007 / 0x571E) and regtest `yr…` (0x2002 / 0x5710) unchanged. One coordinated sweep on every `upgrade/quantum-vaults` branch after the Q3–Q5 merge (schedule §8.1); AGENTS.md rule 6's `ye…` changes when this line is adopted (Q8) |
| D-Q-22 | `PRICE_MAX` (owner, 2026-10-10, after the price-rise lockup investigation) | **raise from 100,000,000 µUSD ($100/YEC, inherited from DigiByte's oracle bounds) to 4,294,967,295 µUSD (≈ $4,294.97, `UINT32_MAX`, the attestation format's limit)**; `PRICE_MIN` unchanged. Consensus constant on both lines, under the review gate: overflow review of `RequiredCollateral`, `CapCents`, `GlobalRatioBps`; every price range check (tag, index, `yed_setquote`, attestor tooling) and the Python model/golden follow. Shipped with the Y-B sweep (§8.1). Investigation: `wt/scratch/lockup-investigation/REPORT.md` (no stalemate from a price rise; owner redeem reads no price) |
| D-Q-23 | Fee structure (owner, 2026-10-11; settles §9 items 3 and 5) | **Option D.** (a) **Protocol fee** (pool fee, FEE-1) becomes **tiered by debt** like tax brackets, charged at mint and again at redeem, **denominated in dollars and converted to YEC at the vault's mint price `pMint`** (already stored; the owner's redeem path still reads no live price): first $1,000 at 1.0 %, $1,000–$10,000 at 0.5 %, above $10,000 at 0.1 %, floor $1 per action; the **early-redeem fee** (IT-9) 5 / 2.5 / 1 % is charged on the **debt**, not the collateral. (b) **Network fee**: wallets target **dollars per KB** via the attested price — plain PQ $0.02/KB, vault/Yellowback $0.05/KB — bounded below by the 1× relay floor and above by `-maxtxfee` (policy only). Goals: small vaults relatively expensive, a falling effective rate so whales are not deterred, PQ/Yellowback bytes always pay their way, nothing explodes or collapses with the YEC price. Replaces the 0.5 YEC / 0.15 % pool fee, D-Q-16's 1× default and §9 item 3's 50× recommendation. Knobs (bands, rates, floor, $/KB) calibrated by yb-calibration before implementation; consensus review gate on both lines |
| D-Q-23a | Fee-study calibration (yb-calibration `docs/reports/2026-10-fees/`, 2026-10-11) | Bands and early fee **as decided**. Network fee: **floor 5,000 zat/KB** (not the relay floor; below P2PKH parity above $490–$1,225 otherwise), **cap max($2 at the attested price, 0.1 YEC)** (0.1 YEC binds on every vault path below ≈ $4). `bondMin` **$8,000 at the registration price** (floor 2,000 YEC); `residualMinZat` **$0.48 at pMint** (floor 100,000 zat); **per-vault share of the MINT-6 cap ≤ 10 %** (floor $10,000) — a parameter, owner may veto before activation. **Red flags for the owner:** (1) MINT-6 counts coinbase issued since the start height, not market cap (cap ≈ $3,240 after 30 d, $39k after a year at $0.40; a $100k vault fits after ≈ 2.5 years) — a market-cap base would be a consensus change to the cap rule; (2) a $100k vault is unliquidatable on today's books (≈ $5k visible bids) — hence the share limit; (3) attestor revenue ≈ $7/seat/month at low adoption vs a $33 bond cost. Supply 16.97 M YEC; 15 % of market cap = $1.0 M at $0.40, $12.7 M at $5, $25.5 M at $10 |
| D-Q-25 | Supply-cap base (owner, 2026-10-11; red flag 1 of D-Q-23a) | **MINT-6's cap is 15 % of circulating YEC supply × the attested price** (supply = the closed-form emission schedule at the mint's block height, deterministic), replacing "coinbase issued since the start height". Consensus change to the cap rule, review gate on both lines. The per-vault share limit (10 % of the cap, floor $10,000) stands. Attestor economics (yb-calibration `docs/reports/2026-10-fees/attestors.md`): revenue per seat is set by adoption, not bond size — $7 / $70 / $704 per month at 2 / 10 / 50 mints a day (50 % share); break-even 5 %/yr ≈ 9.5 mints/day on an $8,000 bond; bond size only sets the seat-capture cost ($56k at $8,000); recommendation **keep the 50 % share and the $8,000 pinned bond**, raise the share at a renewal if real mint counts warrant — pending the owner's confirmation |
| D-Q-26 | Network fee level (owner, 2026-10-11) | **Keep $0.02/KB plain PQ and $0.05/KB Yellowback/vault.** Target: a PQ transaction ≈ $0.10, acceptable range **$0.05–$0.50** (Bitcoin reference ≈ $0.84–$1.67/kB, $0.12–$0.42 per basic transaction). At $0.40/YEC a Falcon spend (≈ 2.6 KB) costs ≈ $0.05 plain / $0.13 YED and an SLH-DSA vault spend (≈ 9 KB) ≈ $0.18 / $0.45 — inside the range. The fees spec's earlier worked values were 10³ too small (review B N-4) and are corrected; the rates themselves were right. **Cap:** plain PQ YEC transfers take the same network-fee cap as Yellowback transactions — min(max(-maxtxfee, $2 at the price), -yellowbackmaxtxfee 10 YEC) — not -maxtxfee alone (which held them at 0.1 YEC ≈ $0.04 below ≈ $0.50/YEC); policy only |
| D-Q-27 | Class C and the supply cap (owner, 2026-10-11) | **Rules as is.** Class C (500 %) equals `recapRatioBps`, so its mints pass MINT-6 and HALT-2; the owner accepts this — 500 % is significant collateral. No change on either line |
| D-Q-28 | Attestor bond (owner, 2026-10-11; supersedes D-Q-23a's bondMin wording) | **bondMin = 20,000 YEC when no attested price is active** (founding window, any halt with no price); **with a price, min(20,000 YEC, max(2,000 YEC, $8,000 at the attested price at registration))** — capped at the no-price bond (owner, option B: below $0.40/YEC the minimum stays 20,000 YEC). **Price source** (owner, review A1/B1): the bond reads the snapshot before the join; when that snapshot has HALT_DIVERGENCE (pool quotes diverging from the attestors' signed price) it counts as no price — 20,000 YEC — so pools cannot inflate their quote to cheapen a seat. Seats stay competitive above the minimum: a larger YEC bond outranks a smaller one (e.g. 20,000 YEC posted at $1/YEC bumps an $8,000-minimum bond), by the existing bond-weighted seat ranking. Consensus change, review gate on both lines |
| D-Q-29 | Attestor seats: open set, log tenure, eviction (owner, 2026-10-11) | The attestor set is **open by rule**: the module adopts only an OPEN 15-member set and refuses SET_REMOVE / SET_WINDDOWN on it (EQV-1 slashing is the only removal). *(Audit 03/H-1, 2026-10-12: with no slash vote on the attestor set, D-U3's forfeit is revised to a refund — CAN-1, upgrade plan §15.10 U-24 — and D-Q-31's "a cosigned slash vote still lands on a member that already left" does not apply to the attestor set.)* **Seat ranking** (seats and eviction only; the price median keeps its existing weight) = bond × f(tenure), f rising on a log scale from ×1.0 to **×1.9 at one year**; a seated attestor counts ×1.05 (hysteresis). **Eviction:** a join to a full set displaces the lowest-ranked member (a non-live member first) when its bond exceeds that member's weight by > 5 %; no slash. Primitive gains a generic `Displace` hook for module-governed sets (owner approved). An honest evicted member must get its bond back soon (unbonding design pending); a long lock stays for misbehaviour |
| D-Q-30 | Attestor bond revised (owner, 2026-10-11; **supersedes D-Q-28's price-based minimum**) | Three attestor systems (Yellowback, wYEC, nYEC) cannot each demand 9 × 20,000 YEC. **bondMin = clamp(5 % of all YED vault collateral ÷ 9 seats, 10,000 YEC floor, 20,000 YEC cap)** (floor raised from 5,000 by the owner after the yb-calibration seat study: capturing 7 of 9 seats at launch ≈ 140,000 YEC instead of ≈ 70,000), counted in YEC from the snapshot before the join — **no price**, so the pool-inflation trick and the no-price/divergence cases are gone. The share is a consensus constant in the node (yb-calibration may refine it before a release, never at runtime). Checked once at registration; bigger bonds win seats (D-Q-29). **Exit any time:** an evicted or voluntarily leaving attestor's bond returns **14 days** (16,128 blocks) after exit, slashable until then; the one-year lock is dropped. Bridge sets keep their own value-at-risk bonds (hawkeye plan §2) |
| D-Q-31 | Slashing hardening + minimum exit window (owner, 2026-10-11; seats review A1/B1) | Slashing reaches **every** unspent bond of a key in a set, including one in its exit delay; a key cannot rejoin while an old bond is unspent; a cosigned slash vote still lands on a member that already left. **Every signer set, bridges included, has an exit window (maturity) of at least 14 days** (16,128 blocks) — so a member who leaves stays slashable for 14 days in every application. Hawkeye's mainnet proposal (maturity 1,152) moves to ≥ 16,128 |
| D-Q-24 | `maxMint` (owner, 2026-10-11) | **$100,000** (restores DigiByte's value; reverses hardening H-12's $2,500 launch guard) — equal to `maxOutput`. The 15 % supply cap (`supplyCapBps`) and the 200 % global-ratio halt stay as the system-wide limits; yb-calibration checks whale concentration against them |
| D-Q-12 | Security category | **NIST category 1** (128-bit classical / AES-128 quantum) for both schemes: SLH-DSA-128s and FN-DSA-512; category 5 variants rejected on size (Falcon-1024 does not fit the standard scriptSig limit; SLH-DSA-256s is 29.8 KB) |
| D-Q-19 | x402 YED payment channels after Falcon (`TOK-PQ`) (owner, 2026-10-10) | **hybrid channel template `TX_PQCHANNEL`**: client PQ + server secp256k1 cooperatively, client PQ alone after a CLTV refund height; one `OP_CHECKPQSIG` per path (fits R-B1); `TOK-PQ` accepts it as a holder. Pure PQ 2-of-2 rejected (would raise the per-evaluation cap; SLH 2-of-2 exceeds `MAX_SCRIPT_SIZE`). Spec header "D-Q-19" has the bytes |
| D-Q-13 | Hash-based one-time (WOTS) as the holder scheme | **rejected**: NIST approves WOTS only inside XMSS/LMS/SLH-DSA; a bare one-time key is unsafe under address reuse, which a receiving address cannot forbid. Revisit only if Zcash's Zakura opcode (target 2027-01) publishes a design worth sharing |
| D-Q-14 | Libraries (rev 2) | SLH-DSA from a **FIPS 205-conformant** C implementation chosen by the Q0 spike (e.g. PQ Code Package `slhdsa-c`), checked against NIST ACVP; Falcon-512 from **PQClean `falcon-512/clean`**; both vendored at a pinned commit in `src/crypto/pq/` |
| D-Q-15 | Consensus review gate on this line (rev 2) | two independent adversarial **reviewer agents** per Q2/Q3 chunk, four-part check in the merge message; the two-human gate applies at the merge into `upgrade/vault` |
| D-Q-16 | PQ fee default (rev 2) | `-pqfeerate` defaults to **1× the per-KB relay floor**, configurable; yb-calibration sets the release value |
| D-Q-17 | Publishing (rev 2) | branches stay **local** (no push, no GitHub CI) until the owner says; verification is local suites |
| D-Q-18 | Scope of this implementation (rev 2) | **Q0–Q7**: both node lines and every client (YecWallet, YEW, lightwalletd, chain-viz, hawkeye, yb-calibration study); Q8 is the owner's |

## 3. Threat model: what each key protects, before and after

| Key | Protects | Today | After this plan |
|---|---|---|---|
| Vault owner (V selectors 2/3, I selector 3) | the locked YEC of every YED position and every bridge lock; R1 recovery | secp256k1, raw key in the script | SLH-DSA-128s, hash-committed, every vault |
| YED holder (`ye…` outputs) | every YED balance | secp256k1 P2PKH | Falcon-512 (SLH-DSA until final), hash-committed |
| Claimant (V selector 4, I selector 1) | nothing: the claim and release branches are covenants with no signature | — | unchanged; a claimant needs no PQ key beyond the YED they burn |
| Attestor set (selector 1, I selector 2, acts) | unlock / cancel; price attestation | 65-byte recoverable ECDSA | unchanged (D-Q-5); the PQ owner path is the backstop |
| wYEC guardians | bridge mints on Ethereum | secp256k1 both sides | unchanged (D-Q-5) |
| Plain YEC `s1…` | user YEC | secp256k1 P2PKH | unchanged (D-Q-11) |
| Sapling `ys1…` | shielded YEC: privacy conditional on address secrecy; spend authority and proof soundness not PQ | Jubjub / Groth16 | unchanged (D-Q-6) |

**Exposure window that remains:** a PQ key is revealed in the mempool when it spends; the attacker's window is
the time to the next block. Bitcoin's BIP-360 and Bitcoin Cash's CHIP accept this window; so does this plan. A
hash-committed key that is reused (a second output to the same `ye…` address after a spend) is exposed from the
first spend on; wallets rotate holder addresses (Q5, Q7) and the vault owner key is single-use by construction
(one key per mint).

## 4. Specification

### 4.1 Constants and the scheme registry

| Field | Value |
|---|---|
| `OP_CHECKPQSIG` | `0xc2` (`src/script/script.h`, after `OP_CHECKSETDORMANT = 0xc1`) |
| `PQ_SIGOP_COST` | 20 (counted by `GetSigOpCount` and `GetP2SHSigOpCount` toward `MAX_BLOCK_SIGOPS` = 20,000) |
| `PQ_KEYHASH_SIZE` | 32 |
| `MAX_PQ_CHUNK` | 520 (= `MAX_SCRIPT_ELEMENT_SIZE`; every chunk but the last is exactly 520 bytes) |
| `MAX_STANDARD_PQ_SCRIPTSIG` | 9,000 bytes (policy; fits SLH-DSA-128s: 7,856 + 32 + chunk overhead; `MAX_SCRIPT_SIZE` 10,000 is the consensus bound) |

Scheme registry (`src/crypto/pq/scheme.h`), consensus:

| `schemeId` | Scheme | pk | sig (incl. hashtype byte) | Status |
|---|---|---|---|---|
| `0x01` | SLH-DSA-SHA2-128s (FIPS 205) | 32 | 7,857 | active from activation |
| `0x02` | FN-DSA-512 (FIPS 206), padded signature format | 897 | 667 | **active from the vault activation** on mainnet/testnet (D-Q-2: `pqFalconHeight = 0`; regtest `-pqfalcon`/`-pqfalconheight`) |
| other | — | — | — | script failure `SCRIPT_ERR_PQ_SCHEME` |

Sizes are **exact**: a public key or signature of any other length fails. SLH-DSA-SHA2 is chosen over SHAKE for
the SHA-256 code already in the tree; the `s` (small) parameter set over `f` because 128f's 17,088-byte signature
exceeds `MAX_SCRIPT_SIZE`.

### 4.2 `OP_CHECKPQSIG` (consensus, `src/script/interpreter.cpp`)

Gated on the same flag as 0xc0/0xc1 (`SCRIPT_VERIFY_VAULT`, or `SCRIPT_VERIFY_QUANTUM` under D-Q-10 option
"new upgrade"); without it, `SCRIPT_ERR_BAD_OPCODE`, exactly as the two vault opcodes.

Stack on entry (top last): `<sig_1> … <sig_s> <s> <pk_1> … <pk_p> <p> <keyHash:32> <schemeId:1>`.
The scriptPubKey supplies the last two; the scriptSig supplies the rest.

1. Pop `schemeId` (one byte, a registered scheme, else `SCRIPT_ERR_PQ_SCHEME`) and `keyHash` (32 bytes).
2. Pop `p` (minimal number, 1..`ceil(pkLen/520)`) and `p` chunks; pop `s` likewise and `s` chunks. Every chunk but
   the last of each sequence is exactly 520 bytes (**canonical chunking**, else `SCRIPT_ERR_PQ_CHUNK`); concatenate
   to `pk` and `sig`. Total lengths must equal the registry's, else `SCRIPT_ERR_PQ_SIZE`.
3. `SHA256(schemeId ‖ pk) == keyHash`, else push false (the `OP_CHECKSIG` failure semantics, so `OP_IF` branches
   compose).
4. The last byte of `sig` is the hashtype; `SignatureHash(scriptCode, tx, nIn, hashType, amount, consensusBranchId)`
   is the message — ZIP-243, unchanged; v4 transactions only (a v5 transaction is invalid under Vault, quantum
   spec R-A3). Hashtype handling as `OP_CHECKSIG` (including `SCRIPT_VERIFY_STRICTENC`).
5. Verify with the scheme's **verification** routine (integer-only for both schemes; no floating point enters
   consensus). Push true/false. `NULLFAIL` semantics as for `OP_CHECKSIG`.
6. Counts `PQ_SIGOP_COST` sigops wherever `OP_CHECKSIG` counts one.

Malleability: canonical chunking plus exact sizes make the scriptSig encoding unique for a given `(pk, sig)`;
SLH-DSA signatures are deterministic in the non-hedged mode (the node wallet signs hedged, 16 bytes of `opt_rand`
from the OS RNG, audit 02/PQ-3; vectors use explicit entropy) and Falcon's are randomized, so **v4 txids remain
malleable by the signer** exactly as ECDSA's are today (no third-party malleability is introduced). No `OP_CAT`,
no new sighash, no transaction field.

### 4.3 Templates (`src/script/standard.cpp`, `src/vault/template.cpp`)

**PQ pay-to-key-hash, `TX_PQPKH`** (bare, 35 bytes; scheme pushed as `OP_1`/`OP_2`):
```
<keyHash:32> <schemeId:1> OP_CHECKPQSIG
```
scriptSig: `<sig_1> … <sig_s> <s> <pk_1> … <pk_p> <p>`; push-only. Standard once the upgrade is active at tip+1.
`CTxDestination` gains `CPQKeyID { uint8 scheme; uint256 hash; }`; `Solver`, `ismine`, `sign` gain the case.

**Vault V, PQ owner (the only owner shape, rev 2).** Selectors 2 and 3 replace `<ownerKey:33> OP_CHECKSIG` by
`<ownerHash:32> <schemeId:1> OP_CHECKPQSIG`; selectors 1 and 4 are byte-identical to §15.3 of the upgrade plan.
`VaultParams::ownerKey` (`CPubKey`) becomes `VaultParams::owner` (`CPQKeyID`); `ParseVault` accepts only the PQ
shape (a 33-byte owner push is no longer a V), and the fixed token offsets after the owner slot shift by +1
against §15.3. The same for **Intent I** selector 3. **Bond B** is unchanged. Rule S-2's "every output is an I with the V's … `ownerKey`" carries the
variant through. scriptSigs: OWNER `<sig_1>…<sig_s> <s> <pk_1>…<pk_p> <p> OP_2`, OWNER-RELEASED likewise with
`OP_3`.

Field ranges: as §15.3; `schemeId` registered. A V- or I-shaped output with an unregistered scheme is not a
template (rule V-1 rejects it).

### 4.4 The YED module (`src/yellowback/`)

- **MINT payload (v4 codec).** `ownerPubKey 33` becomes `ownerScheme u8 ‖ ownerHash 32` — **33 bytes, the same
  length**, so the 80-byte OP_RETURN layout and `feeVout`/`attestFeeVout` offsets do not move. MINT-3
  (`bad-mint-owner-key`) now requires a registered scheme (and Falcon only while `pqFalconActive`); the vault
  output must equal `YedVaultScriptAt` built from that owner (D-Q-1; the template admits no other owner shape). `ATTESTOR_REGISTER` is unchanged (D-Q-5).
- **Holder scripts.** `P2PKHKey(script)` generalises to `HolderKey(script)` returning a `CTxDestination` for the
  25-byte P2PKH **or** the 35-byte `TX_PQPKH` shape; tokens, fees, payees and residual intents are recognised by
  either. The in-term claimant's residual intent commits `SHA256(holderScript(owner))`. **Holder policy per
  D-Q-2:** PQ-only holders (every token output must be `TX_PQPKH`) once the Falcon scheme is active; until then
  the module accepts both shapes so YED can launch before FIPS 206 if the owner chooses (b).
- **Token index.** Keyed by the destination; `yed_listtokens <addresses>` accepts the new address form.
- **RED / claim paths.** Unchanged in logic: the owner redeem signs with the PQ owner key over the V script as
  today (`txbuilder.cpp` owner-signature site becomes scheme-dispatched); selector 4 and I-1 have no signature.
- **Address encoding.** `ye…` keeps its prefix: a new 2-byte Base58Check version for the 33-byte
  `scheme ‖ hash` payload (found by search in Q0, as `0x1F,0xE4` was for 20 bytes), `yt…`/`yr…` likewise. The
  address is ~52 characters, under lightwalletd's 64-character guard. Decoded in `yellowback::Params`, not
  `chainparams`, as today.
- **RPC contract (`rpcversion` 7).** `yed_getinfo.params` gains `pq: {schemes: [...], falconActive}`;
  `yed_mint` takes `owneraddress` (a PQ `ye…`) in place of `ownerkey`; `yed_listpositions` rows carry
  `ownerScheme`; `yed_getnewaddress` returns a PQ address; `vault_lock`'s `ownerkey` accepts a PQ key hash with
  scheme; `vault_ownerspend` signs with whichever owner type the wallet holds.

### 4.5 Policy (`src/policy/policy.cpp`, `src/main.cpp` relay only)

- `IsStandardTx`: an input whose previous output is `TX_PQPKH` or a V/I PQ owner spend may carry a scriptSig up
  to `MAX_STANDARD_PQ_SCRIPTSIG`; all other inputs keep 1,650. Push-only stands.
- Relay fee: unchanged mechanism — `minRelayTxFee.GetFeeForRelay(nBytes)` is already per byte; the plan only
  makes the **wallets** stop attaching the flat `DEFAULT_FEE` (1,000 zat) for PQ transactions and charge
  `max(DEFAULT_FEE, feeRate × size)` with a configurable `-pqfeerate` (default 100 zat/KB × a multiplier the
  owner sets at Q8). On `ycash6`, where P-2 made the fee `max(-yellowbackfee, ZIP-317 conventional fee)`, the
  conventional fee counts logical actions not bytes, so the same size term is added there.
- `-pqrelaybytes` (default 0 = unlimited) lets an operator cap PQ scriptSig bytes per block template; recorded,
  default off.

### 4.6 Keys, derivation, signing (`src/wallet/`, `src/keystore.*`)

- **Derivation.** A PQ key is derived from the wallet's existing HD seed by hardened-only derivation:
  `m / 44' / 347' / account' / 0x5100' / index'` (ZIP-32/BIP-32 hardened child → 64-byte seed material; SLH-DSA
  takes 48 bytes as `SK.seed ‖ SK.prf ‖ PK.seed`; Falcon takes 32 bytes as its SHAKE256 keygen seed). No public
  derivation exists for either scheme, so **no xpub / watch-only** for PQ keys; a watch-only wallet imports
  addresses. Backup = the seed, as today.
- **Falcon keygen determinism.** Falcon's reference keygen uses floating point and is **not** bit-reproducible
  across implementations (NIST pqc-forum, 2025); one implementation is pinned for keygen (§4.7) and the derived
  public key is stored, never recomputed from the seed across implementations, until FIPS 206 fixes an
  integer-only keygen.
- **Signing.** SLH-DSA-128s signs in ~0.5–1 s on a phone (acceptable for a vault action); Falcon-512 in ~0.2 ms.
  Signing never happens in the node's consensus path; the node wallet signs with the same vendored library's
  constant-time `clean` variant. Falcon's known signer side channel (ePrint 2026/2124: key recovery from 20–56
  signatures on Cortex-M4) is the reason the YED holder key is a **software** key on desktop/mobile only; no
  hardware wallet supports Falcon as of 2026-10 and this plan does not promise one.
- **Keystore.** `CBasicKeyStore` gains `std::map<CPQKeyID, CPQKey>`; `walletdb` a `pqkey` record; `CPQKey`
  holds `{scheme, seed, pk}`; `ismine` matches `CPQKeyID`.

### 4.7 Libraries

| Where | Library | Notes |
|---|---|---|
| node, both lines (`src/crypto/pq/`) | **PQClean** `sphincs-sha2-128s-simple/clean` and `falcon-512/clean`, vendored as C sources at a pinned commit (`depends/` package or `src/crypto/pq/pqclean@<sha>`) | verification in consensus; constant-time signing in the wallet; no AVX2 variants in consensus (not CT, and the optimised Falcon paths are FP) |
| YEW (`yew/core`, Rust) | `pqcrypto-sphincsplus`, `fn-dsa` (Pornin, 0.4.x, pure Rust, no_std) | Falcon via `fn-dsa`, which warns its encodings may change before FIPS 206: pinned by rev, vectors gate it |
| test_framework (Python) | pure-Python **verifiers** for both schemes + an SLH-DSA signer (slow but exact); Falcon signing from pinned vectors, not a Python signer | the pure-Python signer rule of the upgrade plan §15.9 holds for SLH-DSA; Falcon signing is vectors-only |
| YecWallet (Qt) | none: signs via node RPC | — |
| lightwalletd, chain-viz, x402 | none: no script parsing, read RPCs | x402 YED channels (phase X-later) would sign with the YEW core |

**Golden vectors** (`src/test/data/pq_vectors.json`, generated once in Q0 from PQClean, checked against the
NIST ACVP vectors for SLH-DSA and the Falcon reference KATs): keygen seed → pk, message → signature, scriptSig
chunking, and whole transactions, byte-identical on `ycash-dd`, `ycash6`, YEW's Rust core and the Python
framework (the cross-line identity leg of CI, as in-term claims T6).

### 4.8 Activation and parameters (`src/consensus/params.h`, `upgrades.cpp`)

- **Decided (rev 2): ride `UPGRADE_VAULT`**: no new upgrade; `OP_CHECKPQSIG` is active where
  `SCRIPT_VERIFY_VAULT` is, `pqFalconActive` is a per-network bool (regtest `-pqfalcon=1`).
- (Not taken) option "new upgrade": `UPGRADE_QUANTUM`, branch ID allocated at Q0 (recorded in `librustzcash6` as
  `NetworkUpgrade::Quantum`, the one `librustzcash6` change), `-nuparams=<id>:<h>` on regtest/devnet, mainnet
  and testnet `NO_ACTIVATION_HEIGHT` until the release (the heights guard in `yellowback-release.yml` extends to
  it); the release line is 6.23.x.
- Either way: no sunset; no activation height on any public network is set by this plan.

### 4.9 Tests and gates

- Unit: `pq_crypto_tests` (vectors, sizes, rejects), `pq_script_tests` (opcode: every error path, canonical
  chunking, hashtypes, pre-activation `BAD_OPCODE`), `vault_template_tests` (both owner variants, offsets),
  `yellowback_payload_tests` (v4 MINT), `yellowback_script_tests` (PQ holder recognition), fuzz target `PQScript`
  in `vault_fuzz_tests`.
- Functional: `vault_pq.py` (lock with PQ owner, ownerspend, released-set recovery, claim unchanged),
  `yellowback_pq.py` (PQ mint, transfer, redeem, in-term claim by a PQ claimant, index), `yellowback_fee.py`
  gains the size-priced cases, `vault_upgrade.py` gains the pre/post-activation rows, the `upgrade-walk` and the
  role devnet gain a PQ minter and a PQ claimant persona.
- DoS measurement (the hardening plan's method): validation time of a 2 MB block of SLH-DSA spends, of Falcon
  spends, and of invalid PQ signatures, against the Sapling full-block figure; mempool behaviour under a flood of
  8 KB transactions at the relay floor. Numbers into §6.
- CI: push tier runs the new suites on both lines; audit rule-tag list gains `Q-*`; contract gate at
  `rpcversion` 7; cross-line vector identity; the consensus review gate (AGENTS.md rule 2) for Q2 and Q3 with the
  four-part check in each PR body.

## 5. Four-part check and tier

> DigiByte does nothing here: DigiDollar has no post-quantum signature (Bitcoin Core v28 lineage, secp256k1 and
> Schnorr). The industry reference is instead Bitcoin's BIP-360 (P2MR, PQ opcodes deferred to `OP_SUCCESSx`),
> Ethereum's EIP-8052 (Falcon-512 precompile, 3,000 gas), Algorand's `falcon_verify` opcode (AVM v12, Falcon-1024)
> and Bitcoin Cash's CHIP-2026-06 (scheme byte on the key, hybrid, behind HASH160).
> The Ycash equivalent of every one of those mechanisms is **absent**: no Tapscript `OP_SUCCESSx`, no precompile,
> no AVM, and a 520-byte push limit the others do not have.
> So the adaptation is **one opcode above `OP_NOP10`, gated on the network-upgrade branch ID, that reassembles a
> chunked key and signature and verifies them over the ZIP-243 sighash, with the key hash-committed in a bare
> template** — BCH's hash-behind-the-key and Algorand's explicit opcode, on Ycash's own activation mechanism.

**Tier:** a network upgrade (the prime directive's decided tier). **Rung:** opcode + template; per-vault key
material (the owner key already is per-vault); no transaction field, no global state, no change to the element
or script size limits, no new sighash. Why not cheaper: no existing opcode verifies a non-ECDSA signature and
`OP_CHECKSIG` rejects any key not 33/65 bytes; a P2SH redeem script cannot hold an 897-byte key (520-byte
element); a soft fork cannot add a verifying opcode on Ycash's script (mapping §2). Why not the module alone: a
module can read keys but cannot make a spend condition — spend authority is the one thing only the script can
hold.

## 6. What is given up, and the risks

- **FIPS 206 is not final** (NIST: "in development", no public draft as of 2026-08). Falcon's padded signature
  format, key encoding, pre-hash mode and keygen may change. Mitigation: the scheme is reserved, not active, until
  the bytes are final (D-Q-2); vectors regenerate; one implementation pinned for keygen.
- **Chain growth.** Every SLH-DSA spend is ~8 KB forever; ten thousand a day is ~30 GB a year. Mitigation: SLH-DSA
  is the rare vault-owner signature; Falcon (~1.7 KB) is the holder signature; the UTXO set does not grow (35-byte
  outputs). yb-calibration models the growth and the fee multiplier (Q7).
- **No hardware wallet, no watch-only, no xpub** for PQ keys. Recorded in the wallet disclosure text.
- **Falcon's signer side channel** on embedded targets. Mitigation: verify-only in consensus; software signers
  only; the `clean` constant-time variant everywhere; no promise of hardware signing.
- **The mempool window** and address reuse remain the exposure (§3). Mitigation: address rotation in the wallets;
  one owner key per mint. A commit-delay-reveal spend (Ruffing, ePrint 2025/1307) is the known next step if the
  window ever matters; not in this plan.
- **The Foundation's primitive.** Making vault owners PQ is a change to the agnostic primitive. Rev 2 (owner)
  replaces the secp256k1 owner outright for every vault, bridge included: one template shape, the smaller
  consensus surface, at the cost of the primitive no longer offering an EC owner and of every bridge depositor
  needing an SLH-DSA key (hawkeye's `lock`/`recover`, YEW's bridge flow). Recorded for the Foundation.
- **Attestors and guardians stay elliptic-curve.** The PQ owner's recovery path (selector 3 on dormancy) is the
  backstop; a broken set cannot take a vault's collateral past its owner. A broken set *can* cancel claims and
  attest prices until it is released; that is the v3 collusion row, unchanged.
- **Sapling is unchanged.** Shielded YEC's spend authority and proof soundness remain pre-quantum until Ycash
  adopts Zcash's PQ pool. Said plainly in every disclosure.

- **Measured DoS envelope (Q6, ycash-dd `doc/yellowback-pq-dos.md`, 2026-10-10, Apple M5, -O3):** per verify ECDSA
  19.8 µs, SLH-DSA 247 µs, Falcon 26.5 µs; full 2 MB blocks: P2PKH 0.26 s, SLH-DSA 0.06 s, Falcon 0.03 s at -par=1; the
  R-B1 staged-output worst case (miner-only, ≈ 380 MB of earlier chain to set up) 18.2 s at -par=1 / 8 s connect at
  default -par, **≈ 383 MB undo and ≈ 1.2 GB peak RSS per node** (the per-tx `CCoins` model loads a large creating tx;
  true of any large bare output today) — inside the envelope Ycash already admits (legacy multi-CHECKSIG staged block
  65 s; spend-only Sapling block ≈ 20 s; full Sapling z→z ≈ 11 s at ≈ 4 ms/spend). Release resource guidance should say
  so. PQ verifications are now sig-cached (2026-10-11, reviewed A+B on both lines): an entry is
  SHA256(pqNonce ‖ scheme ‖ sighash ‖ len-prefixed pk ‖ len-prefixed sig), stored on success only; a miner's own
  240-SLH block connects in ≈ 2 ms of verify instead of ≈ 18–23 ms. A node that never saw the transactions still
  verifies everything once, so the worst-case figures above are unchanged.

- **`maxMint` $100,000 (D-Q-24): H-12's depth argument is given up on this line.** Hardening H-12 held `maxMint` at
  $2,500 because a $100,000 vault's liquidation at θ (≈ $125,000 of YEC) exceeds the measured bid depth of YEC
  markets, so a large claim could not be sold without moving the price against the claimant. Restoring DigiByte's
  $100,000 reverses that argument here: a single vault may now be larger than the market can absorb at the claim
  threshold. What bounds the exposure instead is aggregate — the 15 % supply cap on the circulating supply (D-Q-25),
  MINT-6b's per-vault share (max(10 % of that cap, $10,000), D-Q-23a) and HALT-2 — not the per-vault depth.
  `harden/yellowback` keeps $2,500 (fees spec §2.4, §4.3 row 16).

## 7. Branches in every repo

`upgrade/quantum-vaults`, cut from `origin/upgrade/vault`, in: `ycash-dd`, `ycash6`, `yecwallet-dd`,
`lightwalletd-dd`, `yew`, `chain-viz`, `x402-ycash`, `hawkeye` (bridge vault owners are PQ: its lock policy,
`lock`, `recover` and roll paths), and `yb-calibration` (cut from `main`, as it has no `upgrade/vault`).
**No branch** in `librustzcash6` (D-Q-10 rides `UPGRADE_VAULT`), `wyec` (the Ethereum side is untouched) or
`yolo` (the pool mines across the activation as before and is tested so). The workspace repo records the branch in `repos.yaml` only when the line is adopted (owner's call at Q8);
until then `make status` tracks `upgrade/vault` and the quantum branches live in `wt/q-*` worktrees. Agents work
on `q/<name>` off `upgrade/quantum-vaults`; the coordinator merges. Never commit to `upgrade/vault-in-term` or
any `-legacy` branch.

## 8. Phases and sequencing

| Phase | Scope | Size | Gate |
|---|---|---|---|
| **Q0** decide + specify | D-Q-2/D-Q-10 answered or explicitly deferred; `ye…` PQ version bytes found; branch ID allocated if needed; PQClean pin chosen; golden vectors generated and cross-checked against ACVP/KATs; this document to revision 2 with the byte layouts frozen | 3 days | vectors file committed on `ycash-dd` |
| **Q1** library | `src/crypto/pq/` on `ycash-dd`, build on macOS/Linux and in `depends/` cross builds, `pq_crypto_tests`, verify/sign benchmarks on the CI runners; port to `ycash6` | 1 week | both lines green; benchmark table in §6 |
| **Q2** opcode | `OP_CHECKPQSIG`, sigop cost, errors, activation gate, `pq_script_tests`, fuzz — review gate on both lines | 1 week + review | two independent reviews per line; four-part check in the PR |
| **Q3** templates | `TX_PQPKH`, V/I PQ owner variants, `Solver`/`ismine`/`sign`, standardness, scriptSig limit, `vault_template_tests`, `vault_pq.py` — review gate | 1 week + review | as Q2 |
| **Q4** module | MINT v4, PQ-only mints, holder scripts, index, RED/claim paths, address version, RPC contract `rpcversion` 7, `yellowback_pq.py`, `doc/yellowback-spec.md` + `make spec` | 1.5 weeks | contract suite; in-term claims suite unchanged and green |
| **Q5** node wallet | keystore, derivation, signing dispatch, `yed_getnewaddress`, `yed_mint`/`vault_lock`/`vault_ownerspend`, size-priced fees on both lines, `yellowback_fee.py` | 1 week | walk green with PQ minter |
| **Q6** proof | devnet/roles PQ personas, `upgrade-walk` rows, DoS measurement, CI push tier + nightly, cross-line vector identity, audit tags | 1 week | CI green on GitHub both lines; DoS numbers in §6 |
| **Q7** clients | YecWallet (PQ address display/validation, mint and redeem flows, fee by size, disclosure text); YEW (`fn-dsa`/`pqcrypto-sphincsplus` in the core, `[u8;33]` owner slot → scheme+hash, coin classification for `TX_PQPKH`, address rotation, fee by size, vectors); lightwalletd (proto fields for `ownerScheme`, address guard); chain-viz (vault owner type panel, PQ byte share of blocks); x402 (none until YED channels); yb-calibration (growth and fee multiplier study) | 2–3 weeks, parallel | each client's M1/CI green against both lines |
| **Q8** release | gate pass (hardening §7 gates re-run with PQ), FIPS 206 status check → D-Q-2 final, D-Q-10 final, release line version (6.22.x or 6.23.x), `repos.yaml` adoption, merge to `upgrade/vault` | 1 week | owner sign-off |

### 8.1 Scheduled sweeps (owner decisions after rev 3)

| Sweep | When | Repos (`upgrade/quantum-vaults`) |
|---|---|---|
| **Y-B** `ye…` → `yb…` mainnet prefix (D-Q-21) | right after the Q3–Q5 merge on ycash-dd; ycash6 takes it in its Q3–Q5 port | ycash-dd, ycash6 (yellowback params, address docs, golden/test vectors, test framework, devnet tooling, RPC docs), yecwallet-dd (address guard/display), lightwalletd-dd (regex, docs), YEW (core codec, vectors, UI copy), hawkeye (PQ address codec, docs), x402-ycash (TS + Python SDKs, specs), chain-viz, yb-calibration (if it renders addresses); not wyec, yolo |
| **PM** `PRICE_MAX` → `UINT32_MAX` µUSD (D-Q-22) | with Y-B, as its own reviewed consensus commit on each line | ycash-dd, ycash6 (params, range checks, maths overflow review, model/golden), attestor tooling wherever it range-checks the price (incl. YEW/x402/chain-viz if they validate quotes) |
| **SQ** chain-wide `sq…` PQ address (D-Q-20) | after Y-B | ycash-dd then ycash6 (key_io, getnewaddress/sendtoaddress/validateaddress/z_sendmany, every `std::get<CKeyID>` site audited), then clients in Q7 |

Critical path: Q0 → Q1 → Q2 → Q3 → Q4 → Q5 → Q6 on `ycash-dd`, with `ycash6` porting one phase behind
(vectors byte-identical before each merge, as the in-term port did); Q7 starts when Q4's RPC contract is frozen.
About 9–11 weeks to a releasable line if D-Q-2 is (b); (a) adds the wait for FIPS 206.

## 9. Open decisions for the owner

Rev 2 resolved D-Q-10 (ride `UPGRADE_VAULT`) and item 4 (bridge vaults are PQ-only, D-Q-1). Still open:

1. ~~D-Q-2, Falcon timing~~ — **decided 2026-10-10: Falcon from day one** (§2). Original text: (a) Hold activation until FIPS 206 is final (projected late 2026 – early 2027) and
   ship SLH-DSA owners and Falcon holders together — one upgrade, PQ-only `ye…` from day one, cleanest product.
   (b) Ship SLH-DSA for both now, 8 KB YED transfers until Falcon follows as the next upgrade — earliest
   protection, a second activation later, and `ye…` outputs on SLH-DSA keys to migrate or keep.
   Recommendation: build both now (the plan does), decide at Q8 on NIST's actual date.
2. ~~D-Q-10, which upgrade~~ — decided rev 2: ride `UPGRADE_VAULT`.
3. ~~The fee multiplier~~ — **superseded by D-Q-23 (Option D)**. Earlier study text: (`yb-calibration` `upgrade/quantum-vaults`,
   `docs/reports/2026-10-pq/`): **recommends m = 50 (5,000 zat/KB)** on both lines — at 1× a PQ byte pays 0.1 zat
   against 4.08 for P2PKH, and the lines disagree (ycash6's ZIP-317 already bills ~3,333 zat/KB of PQ input; m ≥ 34
   makes them identical). Dearest path 80,410 zat. Validation is not the constraint: a full block of SLH spends
   verifies in 0.058 s, of Falcon spends 0.022 s, vs 0.255 s ECDSA-full (Sapling figure missing). The multiplier
   prices honest wallets only; relay spam is bounded by `-pqrelaybytes`. Default stays 1× until the owner decides.
4. ~~Bridge vaults~~ — decided rev 2: PQ-only like every vault; wyec untouched.

5. ~~YEC-denominated constants at high prices~~ — **addressed by D-Q-23** (fees in dollars at `pMint`); `bondMin` / `residualMinZat` still to follow the same pattern (yb-calibration). Original text: (raised by the `PRICE_MAX` review, D-Q-22). With the ceiling at
   ≈ $4,294/YEC, constants fixed in YEC grow in dollars: `FEE_MIN` 0.5 YEC ≈ $2,147 per mint/redeem at the top (more
   than a $100 debt), `bondMin` 20,000 YEC ≈ $86M, `residualMinZat` likewise; the MINT-5 2-YEC floor binds above
   ≈ $150/YEC. No soundness issue (owner redeem always works); a yb-calibration item before a release that expects YEC
   to rise that far (dollar-denominated or price-tiered constants).

6. **FIPS 206 contingency (Falcon audit §8, 2026-10-10).** If FIPS 206's final bytes differ from round-3 padded Falcon,
   adding scheme 0x03 is sufficient for consensus (the registry is scheme-indexed and KeyHash binds the scheme byte), but
   it must ship with: a TOK-PQ amendment (TOK-PQ hard-codes scheme 2), wallet migration to NEW keys (no key reuse across
   schemes), and permanent retention of the 0x02 / PQClean verify code in the node and every client. Audit:
   `docs/audits/yellowback-falcon-consensus-audit-20261010.md` (ship, no critical/high findings).
   **FIPS 206 status (audit F-4, checked by the coordinator 2026-10-10 via web search):** still a draft; final expected late
   2026 – early 2027. NIST's FIPS 206 team published a new FN-DSA plan on Sept 28 seeking feedback, aiming at one signing
   procedure specified tightly enough that two correct implementations produce the same signature (deterministic,
   testable signing). That targets SIGNING (wallet side); consensus verification stays compatible if the final keeps
   round-3's signature/key encodings and hash-to-point — a change to those is the scheme-0x03 case above. Post-pin PQClean
   issues remain unverified (api.github.com not reachable by the auditor). Sources: x.com/P3b7_/status/2105296438615814333,
   encryptionconsulting.com/education-center/fn-dsa-fips-206/.

## 10. References

- Research (workspace-local, untracked): `research_notes/Falcon post quantum Ycash integration/` —
  `falcon_standard.md`, `blockchain_adoption.md`, `zcash_sapling_exposure.md`, `consensus_economics.md`,
  `local_integration_points.md`; report `reports/Falcon post quantum Ycash integration.md` (2026-10-09).
- NIST FIPS 205 (SLH-DSA, final 2024-08-13); FIPS 206 (FN-DSA, in development as of 2026-08); IR 8547 ipd
  (ECDSA deprecated after 2030, disallowed after 2035).
- Bitcoin BIP-360 (P2MR, draft, merged 2026-02-11) and BIP-361; Bitcoin Cash CHIP-2026-06 (scheme byte, hybrid,
  behind HASH160); Ethereum EIP-8052 (Falcon-512 precompile); Algorand `falcon_verify` (AVM v12); Starknet
  OpenZeppelin `cairo-pq-verifiers` (Falcon-512 accounts).
- Zcash ZIP 2005 (Ironwood quantum recoverability, mainnet 2026-07-28); Project Tachyon; Shielded Labs Epoch
  (2026-10-01); Zakura's transparent hash-based opcodes (target 2027-01).
- Falcon side channels: FALCON Down (2022); "Every Signing Leaks" ePrint 2026/2124; threshold Falcon ePrint
  2026/1300. Commit-delay-reveal: Ruffing ePrint 2025/1307.
- Local: upgrade plan §15.2–15.3 (templates, opcodes), §15.10 (YED on the primitive); in-term claims plan §4;
  `ycash-dd/src/script/script.h:24,27,178-179`; `src/vault/template.cpp:100-169`; `src/yellowback/payload.h:19-36`;
  `src/yellowback/state.cpp:76-87`; `src/policy/policy.cpp:84-96`; `src/consensus/consensus.h:26`;
  `src/policy/fees.h:15`; `src/main.h:72`.
