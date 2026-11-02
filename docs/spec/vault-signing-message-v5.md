# Vault signing messages under transaction v5 (ZIP-244): dormant

> **DORMANT. Not in force on any network.** The vault upgrade is defined for v4 transactions only
> (upgrade plan §15.1, U-26; quantum spec R-A3). Under `UPGRADE_VAULT` a v5 transaction is invalid.
> This section is the text a **later** upgrade switches on if Ycash adopts NU5. It does not change
> any rule today, and nothing in either node line, kogany or a client reads it.
>
> Decision: kogany plan **K-21**, option D of
> [`../plans/kogany/research/vault-on-v5-assessment.md`](../plans/kogany/research/vault-on-v5-assessment.md):
> v4 now, with the v5 message pre-written so that at the NU5 (or NU7/Tachyon, K-7) forcing event
> it is reviewed text rather than a blank page.

It restates [upgrade plan §15.2](../plans/yellowback-upgrade-plan.md) step 4 (set signatures), the
`OP_CHECKPQSIG` owner message (quantum spec §5.3) and §15.5 (`actMsg`) over a ZIP-225 v5
transaction and the ZIP-244 signature digest. Wording follows §15: "template input" is an input
spending a V or I output (§15.3). Every byte layout not named here is §15's, unchanged.

**Why a sibling file, not a "§15.2-v5" inside the plan.** §15 has no slot for a dormant rule, and
`scripts/extract_spec.py` copies all of §15 verbatim into the generated node specs
(`ycash-dd/doc/yellowback-spec.md`, `ycash6/doc/yellowback-spec.md`, byte-identical across lines
under `qa/yellowback-cross-line.manifest`, hashed on line 1). A dormant paragraph there would
put rules that are not in force into the normative spec of both node lines, and every edit
would force `make spec-in-term` on both. This file is linked from `docs/spec/README.md`. The
§15.2 cross-reference is a proposed one-line edit, to be made when §15 is next regenerated (see §7).

---

## 1. Preconditions for switching it on

The message alone does not make v5 usable under Vault. The activating upgrade must also deliver
the following (assessment §3, §4 B):

1. **NU5 on Ycash** (branch ID `0xf919a198`, reserved, `ycash6/src/consensus/upgrades.cpp:68`; K-7),
   with its block auth-data commitment (`hashBlockCommitments` / `hashAuthDataRoot`,
   `ycash6/src/main.cpp:6395-6405`). A v5 txid does not commit to scriptSigs, so without that
   commitment no vault or PQ signature would be committed by the block hash.
2. **Epoch order and history.** `CurrentEpoch` reordering (K-6) and ZIP-221 V2 history leaves
   under the combined epoch (`src/rust/src/history.rs`; mapping §22).
3. **Lifting U-26.** The `bad-vault-tx-version-group-id` clause (`ycash6/src/main.cpp:1217-1226`),
   the start-up `InitError` (`src/init.cpp:1542-1565`) and librustzcash6's
   `V5.valid_in_branch(Vault) = false` (`eeb7740d`, `zcash_primitives/src/transaction/mod.rs:253-279`).
4. **Real spent outputs everywhere a vault digest is computed.** ZIP-244 hashes the amount and
   scriptPubKey of every spent output, not just the one being signed (§3). The `CTxOut()`
   placeholders of the mempool and miner rechecks (`src/vault/node.cpp:186-188, 236-239`) and of
   the vault RPCs' `TxData` (`src/rpc/vault.cpp:196-203`) are inert only under ZIP-243. Under
   ZIP-244 they would make the node compute a wrong digest and evict or refuse a valid spend (the
   04/F-2 aggravation). Every one of them must carry the real coins.
5. **Signers.** The node's `V4TxData` (`src/yellowback/txbuilder.cpp:322-327`), YEW
   (`core/src/tx.rs`, `vault.rs`, `pq.rs`), Hawkeye (`hawkeye-core/src/sighash.rs`), x402 (TS,
   Python, `light/`) and lightwalletd-dd's parser (assessment §2 rows 11–14) gain a v5 codec and
   this digest.
6. **ycash-dd.** The v4.5.0 line has no v5 code at all (assessment §1.3). This text is written
   against ycash6 and kogany. Whether ycash-dd is still a consensus line at that point is the
   activating upgrade's decision.

---

## 2. The transaction

- **Format:** ZIP-225 v5. Header `0x80000005` (`fOverwintered` and version 5), `nVersionGroupId =
  0x26A7270A` (`ZIP225_VERSION_GROUP_ID`, `ycash6/src/primitives/transaction.h:53-63`).
- **Branch ID in the bytes.** `nConsensusBranchId` is the third field, and it must be the branch
  ID of the epoch at the spending height. ZIP-244 personalises every root digest with it. ycashd's
  `SignatureHash` *ignores* its `consensusBranchId` argument for v5 and reads the field instead
  (`ycash6/src/script/interpreter.cpp:1481-1486`). The vectors use `0xf919a198` (§6). Vault's own
  ID `0x6d5b7a31` is the v4 epoch's.
- **Template inputs, outputs and acts keep their byte shapes:** §15.3's V, I and B scripts, the
  selectors and scriptSigs, and §15.5's `YV` OP_RETURN. A v5 transaction keeps `scriptSig`
  and the whole script system. Sprout is not expressible in v5, Sapling moves to the shared-anchor
  layout, and Orchard costs one `0x00` byte when empty (`tx-v4-vs-v5-protocol.md` §1, §4).
- **txid** = the ZIP-244 T digest (BLAKE2b-256, root personalisation `"ZcashTxHash_" ‖ branchId`
  LE). Scripts, proofs and signatures are excluded. Everything §15 keys by txid follows from that:
  - `setId` (§15.3, "the txid of its `SET_CREATE` transaction") is the ZIP-244 txid of a v5
    `SET_CREATE` (vector `setCreate`);
  - prevouts in `SetSigMsg`, `actMsg` and the equivocation proof are ZIP-244 txids;
  - the template-output index keys (§15.4) are ZIP-244 txids.
  The selector and junk-push malleability of a template spend (§15.3 "Malleability", 01/V-4) no
  longer changes the txid. Fee-input replacement still does, because prevouts are in T.2.
- **Auth digest** (`"ZTxAuthHash_" ‖ branchId`) commits the scriptSigs, and so the set and owner
  signatures. The block commits to it through `hashAuthDataRoot` (precondition 1).

---

## 3. The digest tree (ZIP-244 S)

`S(t, i)` is the ZIP-244 signature digest for transparent input `i` under hash type `t`. All
digests are BLAKE2b-256 with the 16-byte personalisations shown.

```
S(t, i) = H("ZcashTxHash_" ‖ branchId LE,           S.1 ‖ S.2 ‖ S.3 ‖ S.4)
  S.1 header_digest       H("ZTxIdHeadersHash", header ‖ nVersionGroupId ‖ nConsensusBranchId ‖ nLockTime ‖ nExpiryHeight)
  S.2 transparent_sig     H("ZTxIdTranspaHash", S.2a ‖ S.2b ‖ S.2c ‖ S.2d ‖ S.2e ‖ S.2f ‖ S.2g)
    S.2a hash_type        1 byte, t
    S.2b prevouts         H("ZTxIdPrevoutHash", all prevouts)            empty if ANYONECANPAY
    S.2c amounts          H("ZTxTrAmountsHash", all spent values i64 LE) empty if ANYONECANPAY
    S.2d scriptpubkeys    H("ZTxTrScriptsHash", all spent scriptPubKeys, compact-size prefixed)  empty if ANYONECANPAY
    S.2e sequence         H("ZTxIdSequencHash", all nSequence)           empty if ANYONECANPAY
    S.2f outputs          H("ZTxIdOutputsHash", all outputs)             (SINGLE: the matching output; NONE: empty)
    S.2g txin             H("Zcash___TxInHash", prevout_i ‖ value_i i64 ‖ scriptPubKey_i ‖ nSequence_i)
  S.3 sapling_digest      T.3, H("ZTxIdSaplingHash", …)  (the txid's; an empty bundle hashes the empty string)
  S.4 orchard_digest      T.4, H("ZTxIdOrchardHash", …)  (same)
```

"Empty" means the personalised hash of the empty string. The source is librustzcash
`zcash_primitives/src/transaction/sighash_v5.rs:46-135` (ycash6 calls it through
`zcash_transaction_zip244_signature_digest`, `interpreter.cpp:1441-1497`). There are no
`scriptCode` and no `amount` arguments. The spent output's scriptPubKey and value are taken from
the full list of spent outputs (`PrecomputedTransactionData(tx, allPrevOutputs)`). Hash types
other than `0x01, 0x02, 0x03, 0x81, 0x82, 0x83` are invalid, and so is `SINGLE` without a
corresponding output (`interpreter.cpp:1455-1477`). The vault uses only `0x01` and `0x81`.

Two hash types, compared field by field:

| Field | Set signature `0x81` (ALL\|ANYONECANPAY) | Owner `0x01` (ALL) | v4 / ZIP-243 equivalent |
|---|---|---|---|
| header (version, group, **branch ID**, lock time, expiry) | bound | bound | bound (branch ID only via personalisation) |
| other inputs' prevouts / sequences | **not bound** | bound | same split |
| **every** spent amount and scriptPubKey | **not bound** | **bound** (new) | not in ZIP-243 |
| this input: prevout, value, scriptPubKey, nSequence | bound | bound | prevout, amount, **scriptCode**, nSequence |
| every output | bound | bound | bound |
| Sapling / Orchard effecting data | bound (T.3/T.4) | bound | `hashShieldedSpends/Outputs`, `valueBalance` |

`scriptCode` → `scriptPubKey`: ZIP-243 signs the script from the last `OP_CODESEPARATOR`. ZIP-244
signs the spent output's whole scriptPubKey. For the bare V and I templates, which contain no
`OP_CODESEPARATOR`, the two are the same bytes.

---

## 4. The messages

### 4.1 Set signature (`OP_CHECKSETSIG`, 0xc0)

§15.2 step 4 with only the inner digest replaced:

```
msg = SHA256d("YcashSetSig" (11) ‖ setId (32) ‖ role (1) ‖ prevout.hash (32) ‖ prevout.n (u32 LE) ‖ S(0x81, nIn))
```

The domain separator, the encoding, the 65-byte recoverable signature, low-S, `k` from set state,
"current member" and `SCRIPT_ERR_SETSIG` are all unchanged. The **01/V-2 property holds as
specified**. `0x81` commits to this input (prevout, value, template scriptPubKey, sequence), every
output, the header and the shielded digests. It does not commit to the other inputs or to their
amounts or scripts. So anyone may still replace the fee inputs without a new set signature, and a
re-funded spend has the same `S` (vector `spends[].feeReplaced`: another fee coin of another value,
equal sighash, different txid). The fee still never comes from the vault (S-2, I-1, I-2).

### 4.2 Owner and holder PQ signature (`OP_CHECKPQSIG`, 0xc2)

```
msg = S(0x01, nIn)
```

This is signed by the owner's SLH-DSA or FN-DSA-512 key. The push format is unchanged
(`<sig ‖ 0x01>` chunks, quantum spec §1.5). `0x01` now also commits to **every** spent amount and
scriptPubKey (S.2c, S.2d). A signer must be shown all the transaction's spent outputs, and a lie
about any one of them, the fee input included, invalidates the signature (vector
`ownerSpends[].feeAmountChanged`). This applies equally to `TX_PQPKH` YED-holder transfers and
x402's PQ channel scripts, which R-A3 binds to the same opcode.

### 4.3 Acts (`YV`), unchanged

```
actMsg = SHA256d("YcashSetAct" (11) ‖ P ‖ vin[0].prevout (36))
```

This is §15.5 byte for byte. It binds no transaction digest, so it is the same under v4 and v5
(vector `acts[].actMsgV4 == actMsg`). Only `vin[0].prevout.hash` is now a ZIP-244 txid. Act replay
across a chain split is as open as on v4 (`actMsg` carries no branch ID; assessment §5). The
transaction version does not fix it.

### 4.4 `SET_EQUIVOCATION`, and a transition hazard

The proof format and rule (§15.5 type `0x05`) are unchanged. `sighashA` and `sighashB` are opaque
32-byte values inside the §4.1 message, so the rule already convicts two signatures over one
prevout whether each digest came from ZIP-243 or ZIP-244. **No second equivocation form is
needed.** That corrects assessment §4 C, which said one would be.

The consequence is a **transition hazard** for the activating upgrade. Take a member who signed a
v4 unlock or cancel of a prevout that is still unspent when v4 stops being accepted for template
inputs. If that member re-signs the same prevout and role as v5, the result is two different
`(role, sighash)` pairs: provable equivocation, so ejection and a frozen bond. The upgrade must
choose one of these before it switches this section on:

- (a) keep v4 valid for template inputs for a grace window and let v4-signed spends confirm;
- (b) signer policy: never re-sign a prevout already signed under v4, and let in-flight intents
  run out through CANCEL, owner or RELEASE;
- (c) domain-separate the v5 message (for example a version byte after `"YcashSetSig"`), and have
  `SET_EQUIVOCATION` carry the version and convict only same-version pairs.

(c) changes this section's message, and (a) changes no message. This text takes no position. It
is listed in §7.

### 4.5 Shielded signatures

Sapling spend-auth, binding and Orchard signatures sign `S` with no transparent input. When there
are transparent inputs, that is S.2 under `0x01` with an empty `txin` digest (`sighash_v5.rs`;
`zip244.py`). None of them is a vault message.

---

## 5. Vectors

| | |
|---|---|
| File | `ycash6/src/test/data/vault_v5_dormant_vectors.json`, branch `kc/v5-spec` @ `702fcdcd4`; SHA-256 `d359ba791db52afae1f36a77882bc6527c393791a8ebb9fad3a84c1dcfc18957`. ycash6 only, **not** in `qa/yellowback-cross-line.manifest`, none of the nine pinned files changed |
| Generator | `ycash6/qa/rpc-tests/test_framework/gen_vault_v5_vectors.py` (`--check` to compare). The vault builders and messages come from `vault.py` (unchanged); the digests come from the corrected `zip244.py` |
| Upstream proof | Before writing, the generator replays the ten upstream ZIP-244 vectors (`src/test/data/zip0244.json`, identical to librustzcash `zcash_primitives/src/transaction/tests/data.rs` `zip_0244`) and refuses to emit on any mismatch: 10 txids, 10 auth digests, 10 shielded and 30 transparent sighashes across the six hash types. `test_zip244.py` asserts the same as a unit test |
| Node replay | `ycash6/src/test/vault_v5_dormant_tests.cpp` (`test_bitcoin --run_test=vault_v5_dormant_tests`): decode and round trip, txid (`GetHash`), `GetAuthDigest`, `SignatureHash` through `SIGVERSION_ZIP244` and the Rust `sighash_v5.rs`, `SetSigMsg`, `ActMsg`, `RecoverSig`, `pq::Verify`, and `VerifyScript` of the OWNER branch and of the P2PKH fee inputs, all on hand-built v5 transactions. No `-nuparams` and no chain are involved |
| kogany | W2-c pins this file by SHA-256 **report-only** (K-21), like the nine files but outside the blocking audit leg |

Contents. All transactions are v5 with `nConsensusBranchId = 0xf919a198`. Keys come from fixed
labels (`vault.fixed_secret('vault-v5-vectors-…')`) and the SLH-DSA owner from a fixed seed.

- `spends[]`: `unlock` (V, selector 1, set A, members 0 and 1) and `cancel` (I, selector 2, set B,
  member 2). Each has a P2PKH fee input signed under ZIP-244 ALL, `prevOutputs` (every spent
  output), `S(0x81)`, the `setSigMsg`, the signatures, `v4Sighash` (the same spend as v4 under
  ZIP-243 and the vault branch: different), and `feeReplaced`.
- `ownerSpends[]`: `owner-selector-2` (V OWNER, through the interpreter) and
  `owner-released-selector-3-intent` (I, template and signature). Each has a fee input, `S(0x01)`,
  the SLH-DSA signature and `feeAmountChanged`.
- `acts[]`: a `SET_HEARTBEAT` in a v5 transaction (`actMsg == actMsgV4`).
- `setCreate`: a v5 `SET_CREATE`, with `setIdV5` (ZIP-244) and `setIdV4` (SHA-256d of the same act
  as v4).

Reference values (internal byte order):

| Vector | `S` | message |
|---|---|---|
| `unlock` `S(0x81)` | `5a49c1aaecdc61d575d6a5fb538bf11da63cbd16379d04081f762ff1bd3e027d` | `setSigMsg` `42519ae2705b8d5d0e91b69c8016d7a73f53a0667a359a3b1edd79d9645d7eba` |
| `cancel` `S(0x81)` | `f8d3e0b7473bceb1312842356e23fd554d0a104c03337b22aacaf1e9f443ed9b` | `setSigMsg` `72ca42c4132985e7029db46231fa79ab9937832b9aa6de097976553309915ca5` |
| `owner-selector-2` `S(0x01)` | `7cbb0886d66b007be1d51dfd7e5411ec3b9dc791258f26f1ae4ffb21a72e9499` | (the digest itself) |
| `owner-released-selector-3-intent` `S(0x01)` | `17b04cff7c52986df6a91df1d665da3b2b1c7eb02351eb72ed836028b043137c` | (the digest itself) |
| `heartbeat` | — | `actMsg` `aaa13075b081de326a6a93480fe1ba742465a6d729a8eaa7413d077b5c45aa5a` |

```
.venv/bin/python -m unittest qa/rpc-tests/test_framework/test_zip244.py            # upstream ZIP-244
.venv/bin/python qa/rpc-tests/test_framework/gen_vault_v5_vectors.py --check       # vectors up to date
src/test/test_bitcoin --run_test=vault_v5_dormant_tests                             # the node's ZIP-244 path  (3 cases, 137 assertions, pass)
```

**`zip244.py` (assessment §2 row 16).** The upstream file ycash6 carried had a draft S.2: a
`scriptCode` per input, the sequence digest blanked for SINGLE and NONE, and no amounts or
scriptPubKeys digests. It also raised `TypeError` on `bytes(COutPoint)` before producing any
digest. With that one line patched it still matched 0 of the 6 upstream ALL vectors. It is
replaced by the final S.2 (`signature_digest(tx, t_inputs, hash_type, txin)`, with a
`TransparentInput(nIn, scriptPubKey, amount)` per input). Nothing in the tree called the old
function. The txid and auth-digest halves were already correct and are unchanged.

---

## 6. Branch ID

The vectors pin `0xf919a198`: Ycash's reserved NU5 ID, the epoch in force when v5 first becomes
valid under the K-1 ordering (Vault below NU5). If the activating upgrade introduces its own branch
ID (for example a combined "NU5 + Vault-v5" epoch), the message text is unchanged.
`gen_vault_v5_vectors.py` `BRANCH_ID` changes, and the vectors are regenerated and re-reviewed.
Every digest in §3 is personalised by the branch ID, so no vector survives a change of ID.

---

## 7. Open for the activating upgrade (not decided here)

1. The v4→v5 equivocation transition (§4.4: a, b or c).
2. The branch ID (§6), and whether ycash-dd is still a consensus line (precondition 6).
3. The real spent outputs in the rechecks and RPCs (precondition 4). This is a live bug under
   ZIP-244 and must be fixed before activation, not after.
4. Whether v4 template inputs stay valid alongside v5 (assessment option C, which keeps two
   messages for ever) or v5 only (B).
5. **NU7 / ZIP 2003** bans v4 and brings v6 (`0xD884B698`). v6 extends the ZIP-244 tree with new
   bundle digests. This text covers v5 only. A v6 restatement is the same exercise again (K-7).
6. The proposed §15 cross-reference, applied with a `make spec-in-term` regeneration on both node
   lines: append to upgrade plan §15.1's "Transaction version" bullet "A dormant ZIP-244
   restatement for a later upgrade is in `docs/spec/vault-signing-message-v5.md` (K-21); it is not
   in force."

**Rung (rule 4).** This is documentation and test vectors only, with no consensus change. The
transaction-field rung (a v5 message in force) is deferred to the NU5/NU7 forcing event.
Template < opcode < transaction field is kept: what is given up is one partial malleability gain
(the template-spend txid) until then.
