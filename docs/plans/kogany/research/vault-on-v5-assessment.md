# Vault on transaction v5: assessment

Research note, 2026-11-01. Read-only survey. It changes no code and no decision.
**Question:** the vault network upgrade, and Ycash Yellowback (YED) as its rule module, is defined for v4
transactions only (U-26). What would it take to define it on v5 instead, or as well? What would be gained, and what lost?

**Pins read:**

| Tree | Branch | Commit |
|---|---|---|
| `ycash6` | `upgrade/vault` | `65cb4ae0ff` |
| `ycash-dd` | `upgrade/vault` | `7819467715` |
| `librustzcash6` | `upgrade/vault` | `af841431c3` |
| `ref/zakura` = `kogany` | (kogany: `upgrade/vault`, nothing on it yet) | `2b062412c5` |
| `lightwalletd-dd` | | `a1d141e` |
| `yew` | | `c4dd450` |
| `hawkeye` | | `7022742` |
| `x402-ycash` | | `334d74c` |
| `chain-viz` | | `0165934` |

The kogany plan is cited from branch `plan/kogany-yellowback` @ `45929d0`
(`docs/plans/kogany/kogany-yellowback-plan.md`). It is not on `upgrade/vault` yet.

---

## 1. How the vault upgrade uses the transaction today

### 1.1 The rule (U-26 / quantum spec R-A3)

- **Upgrade plan §15.1** (`docs/plans/yellowback-upgrade-plan.md:834`) defines the vault templates and opcodes for v4
  only: Sapling version group, ZIP-243 sighash. Under `UPGRADE_VAULT` any other version group is invalid. No
  ZIP-244 message is defined. At start-up, every network refuses (`InitError`) a schedule that puts Vault with any of
  NU5..NU6.2, or Vault without Sapling active at or below it.
- **U-26** (`:827`) chose option (a) on 2026-10-13 (owner).
  - **Rejected, option (b):** a ZIP-244 message for the set signatures and PQ signatures under v5. The reason given
    is "a second signed-message definition, golden vectors and a history-tree fix for a configuration no Ycash
    network has".
  - **Given up:** "NU5 cannot activate on a Vault chain without a further upgrade that defines that message".
- **Scope** (`docs/plans/yellowback-quantum-spec.md:50-65`): R-A3 covers more than vaults. It covers
  `OP_CHECKSETSIG`, `OP_CHECKSETDORMANT`, **`OP_CHECKPQSIG` and TOK-PQ**. So every post-quantum signature is
  v4-bound: YED holders' Falcon `TX_PQPKH` transfers, and x402's PQ channel scripts, as well as vault owners.
- **Source:** audit 04/F-2. On ycash6 with NU5 and Vault both active (regtest only), a v5 transaction was admitted,
  and `SignatureHash` silently switched the vault and PQ messages to ZIP-244. A unit test asserted this as
  *expected*. The mempool rechecks also fed `CTxOut()` placeholders into ZIP-244's all-prevouts digest, which would
  silently evict a valid spend.
  - The report is `docs/remedial-action-reports/done/MEDIUM-04-F-2-ycash6-v5-under-vault.md` §1–§3. Its option (b)
    is the "v5" option this note re-examines.

### 1.2 What is signed, and over which transaction bytes

| Item | Message | Depends on the tx version? |
|---|---|---|
| Set signature (`OP_CHECKSETSIG`, 0xc0) | `SHA256d("YcashSetSig" ‖ setId ‖ role ‖ prevout ‖ sighash)` (plan §15.2 step 4, `:848`). `sighash = SignatureHash(scriptCode, tx, nIn, ALL\|ANYONECANPAY, amount, branchId)` (ycash6 `src/vault/checker.cpp:37-41`; `SetSigMsg` `src/vault/act.cpp:329`) | **yes**: the inner sighash is ZIP-243 |
| Owner / holder PQ signature (`OP_CHECKPQSIG`, 0xc2) | the ZIP-243 sighash itself, `SIGHASH_ALL` (quantum spec §5.3 `:635-641`; quantum plan `:205-206`) | **yes** |
| Act (`YV` OP_RETURN, `0x59 0x56`) | `actMsg = SHA256d("YcashSetAct" ‖ P ‖ vin[0].prevout)` (plan §15.5 `:952-953`; `act.cpp:316`) | **no**: it binds only the payload and the first prevout |
| `YED\0` module payload (MINT etc.) | carried in outputs and templates. It is not a signature message (quantum spec §3.1) | no |
| Coinbase price tag | `"YED!"` ‖ v1, 36 bytes in the coinbase scriptSig (`ycash6/src/yellowback/params.h:62-65`) | no. A v5 coinbase still has a scriptSig |

**Implementation.**
- ycash6's `SignatureHash` routes a v5 transaction (`SIGVERSION_ZIP244`) to Rust
  (`src/script/interpreter.cpp:1441-1497`). There, "the amount parameter is ignored" and "the consensusBranchId
  parameter is ignored; we use the value stored in the transaction itself" (`:1481-1486`). The C++ ZIP-244 path also
  takes **no scriptCode**: ZIP-244 S.2g commits to the prevout's *scriptPubKey*, all input amounts and all
  scriptPubKeys (`librustzcash6 zcash_primitives/src/transaction/sighash_v5.rs:46-135`).
- The vault code has explicit v4 guards:
  - `RecheckPQScripts` / `RecheckTemplateScripts` return `"non-v4 transaction (R-A3)"`
    (`src/vault/node.cpp:186-188`, `:236-239`);
  - the vault RPCs refuse a non-v4 transaction (`src/rpc/vault.cpp:198-202`);
  - the Yellowback builder's `V4TxData` throws "Yellowback signs Sapling v4 transactions only"
    (`src/yellowback/txbuilder.cpp:322-327`).

### 1.3 v5 handling on each node line

- **ycash6 (zcashd 6.20 lineage)** has the full NU5 transaction layer. That covers `ZIP225_VERSION_GROUP_ID
  0x26A7270A` (`src/primitives/transaction.h:53-63`), the ZIP-244 txid, auth and sighash, Orchard, and the
  `hashBlockCommitments` auth-data root.
  - **Every piece of it is gated on `UPGRADE_NU5`.** Context-free, `CheckTransaction` admits the ZIP-225 group
    (`src/main.cpp:1562-1570`). In context, while NU5 is inactive any non-Sapling group is
    `bad-sapling-tx-version-group-id` (`:1097-1105`). The vault clause `bad-vault-tx-version-group-id` sits *inside*
    `if (nu5Active)` (`:1217-1226`).
  - **The block commitment to signatures is also NU5-gated.** `CheckBlockBodyAuthCommitment` builds
    `hashAuthDataRoot` and checks `hashBlockCommitments` only `if NetworkUpgradeActive(nHeight, UPGRADE_NU5)`
    (`src/main.cpp:6395-6405`).
  - Ycash mainnet runs Overwinter 347,500, Sapling 419,200, Ycash 570,000, and Blossom/Heartwood/Canopy from
    1,100,000 to 1,100,006. NU5..NU6.2 have no height (`src/chainparams.cpp`, CMainParams). Ycash's NU5 branch ID
    is reserved as `0xf919a198` (`src/consensus/upgrades.cpp:68`) and Vault's as `0x6d5b7a31` (`:90`).
- **ycash-dd (zcashd 4.5 lineage) has no v5 code at all.** There is no `ZIP225`/`ZIP244` symbol in `src/`; the only
  hit is a test constant in `src/test/vault_script_tests.cpp:235-236`. `UPGRADE_NU5` is an enum placeholder
  (`ref/ycash/src/consensus/params.h:40`).
  - A v5 transaction does not even deserialize ("Unknown transaction format", `docs/mapping.md` §22 "History tree
    leaves" row). Any non-Sapling group is `bad-sapling-tx-version-group-id` (`src/main.cpp:1039`). The tests are
    `vault_tx_version_v4_only` (`:208`) and `vault_schedule_r_a3` (`:261`).
  - Its Rust side is `zcash_primitives 0.5` from the ycashfoundation fork (`Cargo.toml:36,62`), which predates
    ZIP-244.
- **librustzcash6.** `eeb7740d` ("Vault is v4-only: BranchId::Vault.has_orchard() = false,
  V5.valid_in_branch(Vault) = false (audit 04/F-6)") was made so that "the crate now says what ycashd enforces".
  - Its "Given up" line reads: "a Vault-epoch v5/Orchard transaction can no longer be built by this crate (a later
    upgrade that brings v5 to Ycash must define the ZIP-244 vault message first)". It also notes that no C++ path
    consults these answers.
  - It is now at `zcash_primitives/src/transaction/mod.rs:253-279`.
- **kogany / Zakura** gates v5 on `Nu5..Nu7` (`crates/zakura-consensus/src/transaction.rs:1152-1190`). It gates v4
  out at Nu7, following ZIP 2003 (`:1029-1052`; `zakura-chain/src/parameters/network_upgrade.rs:340-343`). It uses its
  own `zakura-primitives` (`Cargo.toml:58`), not librustzcash6.
  - The kogany plan places Vault between Canopy and Nu5 (K-1), so "v5 is invalid under Vault falls out of the
    existing gates".
  - K-7 records the far boundary: "Tachyon ⇒ NU7 ⇒ 25 s blocks + v4 ban ⇒ a new vault signing message and
    recalibrated constants" (plan §2.4).

---

## 2. Every place that assumes v4 for Vault

| # | Repo | Where | What assumes v4 |
|---|---|---|---|
| 1 | ycash6 | `src/main.cpp:1217-1226` | consensus: non-Sapling group invalid under Vault (U-26) |
| 2 | ycash6 | `src/main.cpp:1097-1105` | consensus: pre-NU5, only the Sapling group is valid (stock zcashd) |
| 3 | ycash6 | `src/init.cpp:1542-1565` | start-up: Vault with NU5..NU6.2, or Vault without Sapling, is an `InitError` |
| 4 | ycash6 | `src/vault/node.cpp:186-188, 236-239` | mempool/miner rechecks: CTxOut placeholders are "inert only for ZIP-243" |
| 5 | ycash6 | `src/rpc/vault.cpp:198-202` | `TxData`: non-v4 refused |
| 6 | ycash6 | `src/yellowback/txbuilder.cpp:322-327` | `V4TxData`: the wallet signs v4 only |
| 7 | ycash6 | `src/consensus/upgrades.cpp:130-137, 147-160` | `CurrentEpoch` is the highest *index* with a height. Vault's index is above NU5..NU6.2, so NU5 scheduled after Vault never becomes the epoch (kogany K-6) |
| 8 | ycash6 | `src/rust/src/history.rs` (mapping §22) | Vault gives V1 history leaves; NU5 `ConnectBlock` builds V2 |
| 9 | ycash-dd | whole tx layer | no v5 type; `main.cpp:1039`; tests at `vault_script_tests.cpp:208, 261` |
| 10 | librustzcash6 | `transaction/mod.rs:253-279`, `consensus.rs has_orchard` | `V5.valid_in_branch(Vault) = false`; `has_orchard(Vault) = false`; `suggested_for_branch(Vault) = V4` |
| 11 | lightwalletd-dd | `parser/transaction.go:329-475` | the block/tx parser is **v4-only** (zcash/lightwalletd 0.4.6, July 2021). A v5 transaction in any block would be misparsed. Its vault surface is RPC proxying only (`frontend/yellowback_vault.go`), so no acts are parsed |
| 12 | YEW | `core/src/tx.rs:5-13, 196-199, 276-282, 368-372`; `vault.rs:686, 780`; `build/yed_transfer.rs:9, 671`; `pq.rs:24, 556` | hand-written v4 serializer and parser plus a ZIP-243 sighash, used for vault owner spends and Falcon YED transfers; it refuses anything else |
| 13 | x402-ycash | `packages/ycash/src/tx/tx.ts:9-10, 64, 93`; `python/x402_ycash/tx/transaction.py`; `packages/ycash/src/channel/pqScript.ts`; `light/src/spend.rs:8` | TS and Python v4 codecs plus ZIP-243 signers, including PQ channel scripts (`OP_CHECKPQSIG`, so R-A3 applies); `light/` builds v4 Sapling through librustzcash6 |
| 14 | Hawkeye | `crates/hawkeye-core/src/sighash.rs:1, 93-135`; `tx.rs:49-55`; `attribution.rs:110` | parses v3/v4 only (`TxFormat`); signs set signatures over `zip243` |
| 15 | chain-viz | `src/classify.rs:323-335` | reads node JSON. Its "v5" test is a *payload* version byte, not a tx version. In practice version-agnostic |
| 16 | Python framework (both lines) | `qa/rpc-tests/test_framework/vault.py:979-983`, `pq.py:744-747`, `script.py:895+` | vault and PQ builders call the ZIP-243 `SignatureHash`. ycash6 alone has upstream `zip244.py` and v5 `CTransaction` (`mininode.py:65, 1147-1149`). Its `txin_sig_digest` hashes a *scriptCode* (`zip244.py:288-294`), an older draft. The final ZIP-244 hashes the scriptPubKey plus all amounts and scripts (sighash_v5.rs above), so it is unusable for vectors as is |
| 17 | Vectors | `src/test/data/vault_vectors.json` (byte-identical on both lines, checked with `cmp`) | `spends[]` (2) and `ownerSpends[]` (4) pin v4 tx bytes (header `04000080 85202f89`) and ZIP-243 sighashes. `acts[]`, `setSigMsgs[]` and `signatures[]` are version-free |
| 18 | Vectors | `pq_vectors.json` | message-agnostic: the 32-byte message is documented as "a ZIP-243 sighash" but nothing ties it to v4 |
| 19 | yolo | plan finding (48), `yellowback-upgrade-plan.md:1107-1108` | "a v4 coinbase carries no branch ID"; it uses the node's `coinbasetxn`, so no change follows |

---

## 3. Can v5 be made coherent on Ycash without Orchard?

**Option (B), "v5 format without NU5", is not a small switch.** On every node line, NU5 bundles four things:
1. the ZIP-225 format;
2. ZIP-244 txid, sighash and auth digest;
3. the ZIP-244 **block auth-data commitment** (`hashBlockCommitments`, ycash6 `main.cpp:6395-6405`);
4. Orchard.

The third item is load-bearing.
- A v5 txid omits scriptSigs; that is the point of ZIP-244. So a block with v5 transactions commits to its signatures
  only through `hashAuthDataRoot`.
- Admitting v5 under Vault without that commitment would leave every vault and PQ signature uncommitted by the block
  hash. That is the SegWit-witness-commitment hole: a relayed block with mutated auth data has the same hash, which
  causes invalid-block caching and DoS problems.
- So "v5 for Vault" means NU5's tx layer *and* its header rule, plus V2 history leaves (`history.rs`) and the
  `CurrentEpoch` reorder (K-6). That is NU5 minus Orchard, a configuration no zcashd or Zakura code path knows.
  Alternatively it means actually scheduling NU5 (Orchard on, `0xf919a198`) below Vault, which is the kogany K-1
  ordering.

Zakura agrees by construction: v5 is valid only from `Nu5`. Its upgrade order *is* the feature gate (K-1), so "v5
without Nu5" does not exist there either.

---

## 4. Options

### (A) Stay v4-only (status quo, U-26)

- **Footprint:** none. U-26 is merged on both lines, librustzcash6 and the vectors.
- **Cost:** Ycash cannot schedule NU5..NU6.2 on a Vault chain without a further upgrade (U-26 "given up"). Zcash's
  NU7 (ZIP 2003) bans v4, so Ycash can never follow NU7 or Tachyon while vault and PQ signatures exist only for v4
  (K-7).

### (B) Vault v5-only: acts and spends must be v5

- **ycash-dd:** a backport of zcashd 5.0's NU5 transaction layer into the 4.5 tree:
  - ZIP-225 serialization in `CTransaction` and `CMutableTransaction`;
  - the ZIP-244 txid, auth and sighash, which needs a newer librustzcash than `zcash_primitives 0.5`;
  - the auth-data block commitment, history V2 and the wallet builder.
  Realistically several thousand lines across `src/primitives/`, `src/main.cpp` and `src/script/`, all under the
  review gate. It is the largest change the line has ever carried, and it directly contradicts rule 7 and the prime
  directive.
- **ycash6:** the code exists, but every NU5 gate needs a `|| vaultActive` or an NU5 schedule:
  `main.cpp:1097-1105`, `:1217-1226` and `:6395-6405`; `init.cpp:1542-1565`; `CurrentEpoch` (K-6); `history.rs`.
  The rechecks and `TxData` must carry real prevouts (the 04/F-2 placeholder bug becomes live). The wallet builder
  must sign v5 (`V4TxData`, `rpc/vault.cpp`). Then a *v4-is-invalid-for-template-inputs* rule is needed, plus a
  ZIP-244 restatement of §15.2 step 4: `scriptCode` disappears (ZIP-244 hashes the scriptPubKey), and ALL now also
  commits to every input amount and script.
  Estimate: about 400–800 lines of consensus, wallet and test code.
- **librustzcash6:** revert `eeb7740d` and make V5 valid under Vault, with Orchard still off (a new combination).
- **kogany:** contradicts K-1. Vault must sit at or above Nu5, so Orchard is on, or the variant needs its own v5 gate.
- **Clients:**
  - YEW: a new v5 serializer and ZIP-244, or a switch to librustzcash6's builder;
  - Hawkeye: a v5 parser and ZIP-244 set-signature digest;
  - x402: TS, Python and the Rust light client;
  - lightwalletd-dd: upstream's v5 parser (all blocks, not just vault transactions);
  - the Python framework: a correct ZIP-244 model with all amounts and scriptPubKeys.
- **Vectors:** `spends[]` and `ownerSpends[]` are regenerated with new semantics. `acts[]` is unchanged.
- **Prime directive:** fails. A new transaction format becomes a precondition of the primitive. Under
  CLAUDE.md's ladder (template < opcode < tx field) this is the top rung or above, and it buys no requirement R1–R3.

### (C) Allow both v4 and v5 vault transactions

- Everything in (B), **plus** both messages kept forever: two set-signature digests, two PQ digests, two vector sets,
  and two signer paths in YEW, Hawkeye and x402.
- `SET_EQUIVOCATION` must accept either digest form (it compares `sighashA`/`sighashB`, §15.5). Otherwise a member
  could sign v4 and v5 spends of one prevout without being convictable. That is an extra consensus rule.
- ycash-dd must either gain v5 (B's backport) or diverge from ycash6, which breaks "both lines in step".
- **Strictly worse than (B) on footprint.** Its only merit is that existing v4 signers keep working.

### (D) Defer: v4 now, define the v5 or v6 message only when an upgrade brings v5 (the K-7 boundary)

- **Footprint now:** documents only. A dormant spec section ("§15.2-v5") could pin the intended ZIP-244 restatement
  so that the future upgrade starts from a reviewed text rather than a blank page:
  - `SetSigMsg` over the ZIP-244 S.2 digest with `ALL|ANYONECANPAY`;
  - `OP_CHECKPQSIG` over S.2 `ALL`;
  - `actMsg` unchanged.
- **Real work is incurred at the forcing event:** NU5 on Ycash (relax U-26 after K-6) or NU7/Tachyon (ZIP 2003, v4
  ban). At that point ycash-dd is likely retired as a consensus line, ycash6 and kogany already carry NU5, and the
  client signers move to the same ZIP-244 code they will need for ordinary transactions anyway.
- **Optional low-risk prep (non-consensus):**
  - fix or replace ycash6's stale Python `zip244.py` signature digest (§2 row 16) before any vector is derived
    from it;
  - add `has_orchard` / `valid_in_branch` tests for a hypothetical "Vault above NU5" in librustzcash6.

---

## 5. Does v5 solve anything Yellowback actually struggles with?

| Pain point (where recorded) | v4 today | Under v5 / ZIP-244 | Net |
|---|---|---|---|
| **Third-party txid malleability of template spends** (audit 01/V-4, plan `:907-912`). The selector and extra pushes are outside every signature, and CLEANSTACK is policy only, so "clients must not chain on an unconfirmed template-spend txid" | real; mitigated by relay policy and the no-chaining rule | the v5 txid excludes scriptSigs, so selector, junk-push and PQ re-randomisation malleability no longer changes the txid | **partial gain** |
| **Fee-input replacement malleability** (`:1247-1252`, ANYONECANPAY set signatures, remedial 01/V-2) | real | prevouts are in the v5 txid, so replacing a fee input still changes it | **no gain** |
| **Signer malleability of PQ / Falcon txids** (quantum plan `:211-214`) | "v4 txids remain malleable by the signer" | gone for the txid; the auth digest still varies | small gain |
| **Fee and amount coverage for offline / hardware signers** | ZIP-243 `ALL` commits to *this* input's amount only | ZIP-244 `ALL` commits to all input amounts and scriptPubKeys (sighash_v5.rs `:69-92`) | gain only for the owner's `ALL` signature (set signatures use ANYONECANPAY, which commits to this input only in both). No hardware wallet is promised for PQ keys (quantum plan `:287, :361`), so **no current consumer** |
| **PQ scriptSig size / chunking** (SLH-DSA 7,856 B; quantum spec §2.3 F-6 policy limit) | chunked pushes, 520-byte element limit | identical: v5 keeps scriptSig and the script rules | **none** |
| **`YV` act carrier size** (1,200-byte OP_RETURN policy, §15.5 `:957`) | policy | identical | **none** |
| **Act replay across a chain split** (`actMsg` binds no branch ID; the attestors design proposes `ActMsg2` with `consensusBranchId`, `yellowback-quantum-attestors-design.md:193-195`) | open design item | a v5 tx carries `nConsensusBranchId`, but `actMsg` is a separate digest | **none**. Fix it in `actMsg` if wanted, independently of the tx version |
| **Mempool placeholder prevouts** (04/F-2 aggravation) | inert under ZIP-243 | a **live bug** under ZIP-244 (all prevouts are hashed) | **loss** (must be fixed) |
| **Future Zcash upgrades** (owner constraint: NU5, NU6.x/Ironwood, NU7, Tachyon dormant but enable-able, kogany plan §2.4) | NU5 blocked by U-26 until a message exists; NU7 needs v5/v6 | v5 message in place ahead of time | gain only at the boundary, which (D) also reaches by defining the message then (v6 may need one anyway) |

**Verdict on gains.** The only concrete improvement to a recorded Yellowback problem is the *partial* removal of
template-spend txid malleability. It is already mitigated operationally, and its fee-input half survives v5.
Everything else is neutral or a cost.

---

## 6. Decision table

Footprint is a rough order of magnitude of changed lines (code + tests) per repo. "C" marks consensus code under the
review gate.

| Repo | (A) v4-only | (B) v5-only Vault | (C) v4 + v5 | (D) defer, spec later |
|---|---|---|---|---|
| ycash-dd | 0 | **≈ 3,000–6,000 C** (NU5 tx layer backport + new librustzcash) | ≈ B + 300 C | 0 now |
| ycash6 | 0 | ≈ 400–800 (≈ 150 C: NU5 gates, block commitment, epoch order, history, v4-ban for templates) | ≈ B + 300 (dual message, equivocation over both) | 0 now; ≈ B's ycash6 share at the NU5/NU7 event |
| librustzcash6 | 0 | ≈ 30 (revert `eeb7740d`, Vault-v5 without Orchard) | ≈ 30 | 0 now |
| kogany | 0 (K-1 ordering) | contradicts K-1: Vault ≥ Nu5 (Orchard on) or a bespoke v5 gate, ≈ 200 C | ≈ 300 C | 0 now (K-7 records it) |
| lightwalletd-dd | 0 | ≈ 300 (upstream v5 parser) | ≈ 300 | 0 now (needed for any NU5) |
| YEW | 0 | ≈ 600 (v5 codec + ZIP-244, or the librustzcash6 builder) | ≈ 800 (both paths) | 0 now |
| Hawkeye | 0 | ≈ 300 (v5 parse, ZIP-244 set-sig digest) | ≈ 350 | 0 now |
| x402-ycash | 0 | ≈ 2 × 400 (TS + Python), plus light | ≈ 2 × 500 | 0 now |
| chain-viz | 0 | ≈ 0–20 | ≈ 0–20 | 0 |
| Python framework | 0 | ≈ 300 (correct ZIP-244 S.2, v5 vault builders; dd also needs a v5 `CTransaction`) | ≈ 400 | optional ≈ 100 (fix `zip244.py`) |
| Vectors | 0 | `spends[]`/`ownerSpends[]` re-defined | both sets kept | 0 |
| Specs | 0 | §15.2/§15.5, R-A3, U-26 rewritten | as B + dual rules | ≈ 40 lines: a dormant "v5 message" section + U-26/K-7 cross-reference |
| Prime directive | best | fails (tx-format change on dd) | worst | best |
| Zcash-upgrade constraint | blocked until a message exists | NU5 effectively forced | NU5 forced | unblocked by a known, pre-written step |
| Fixes a live pain point | — | partial malleability only | same | — (01/V-4 stays mitigated by policy) |

**Recommendation: (D).** Keep v4-only now (U-26 stands) and pre-write the ZIP-244 restatement as a dormant spec
section. v5 cannot be made coherent on Ycash without NU5's block auth-data commitment, which means NU5 itself.
ycash-dd has no v5 code to build on, and the one real gain, partial txid non-malleability, does not justify a
transaction-format change before the NU5 or NU7 forcing event that will require the message anyway.
