# Transaction v4 vs v5: protocol, code, trade-offs

Research note, 2026-11-01. Read-only survey. Pins: `ref/ycash` v4.5.0 (624c12814), `ref/ycash6` @ 040894344b,
`ref/zakura` @ 2b062412c5, `librustzcash6` on `upgrade/vault` @ af841431, `ycash6` working fork on `upgrade/vault`.
Primary sources: [ZIP 225](https://zips.z.cash/zip-0225) (v5 format), [ZIP 244](https://zips.z.cash/zip-0244)
(txid / sighash / auth digest), [ZIP 243](https://zips.z.cash/zip-0243) (v4 sighash),
[ZIP 239](https://zips.z.cash/zip-0239) (v5 relay), [ZIP 2003](https://zips.z.cash/zip-2003) (disallow v4).

## 1. Wire format

| | v4 (Sapling, ZIP 202/243 era) | v5 (NU5, ZIP 225) |
|---|---|---|
| header | `fOverwintered` + version 4 | `fOverwintered` + version 5 |
| `nVersionGroupId` | `0x892F2085` (`ref/ycash6/src/primitives/transaction.h:42`) | `0x26A7270A` (`transaction.h:54`; Zakura `zakura-chain/src/parameters/transaction.rs:13`) |
| consensus branch id in bytes | **no** (bound only via the sighash personalization) | **yes**: `nConsensusBranchId` is the third field (ZIP 225 "Common fields"; `ref/ycash6/src/primitives/transaction.h:583-591`) |
| order | header, vgid, `vin`, `vout`, `nLockTime`, `nExpiryHeight`, Sapling (`valueBalance`, spends, outputs), JoinSplits, `bindingSig` | header, vgid, branch id, `lock_time`, `nExpiryHeight`, transparent bundle, Sapling bundle, Orchard bundle (`transaction.h:593-603`; `librustzcash6/zcash_primitives/src/transaction/mod.rs:1164-1177`) |
| Sprout JoinSplits | present (count always serialized) | **removed** ("Migration from Sprout requires V4", ZIP 225 rationale); ycash6 rejects `bad-tx-has-joinsplits` (`ref/ycash6/src/main.cpp:1164-1170`); `write_v5` refuses a Sprout bundle (`mod.rs:1165-1170`) |
| Sapling anchor | one anchor **per spend** | one **shared** `anchorSapling` per bundle (Zakura `transaction.rs:131` `PerSpendAnchor` vs `:149` `SharedAnchor`) |
| Sapling layout | effecting data and proofs/sigs interleaved per description | effecting data first, then `vSpendProofsSapling`, `vSpendAuthSigsSapling`, `vOutputProofsSapling` (ZIP 225 "separation of effecting and authorizing data") |
| empty-bundle encoding | `valueBalance` (8 B) and the three counts always present | `valueBalanceSapling`/`bindingSigSapling` omitted if no spends+outputs; `anchorSapling` omitted if no spends; all Orchard fields after `nActionsOrchard` omitted if 0 (ZIP 225) |
| Orchard | absent | `nActionsOrchard`, actions, `flagsOrchard`, `valueBalanceOrchard`, `anchorOrchard`, `sizeProofsOrchard`, proofs, spend-auth sigs, `bindingSigOrchard` |

Byte cost of a transparent-only tx outside `vin`/`vout`: v4 = 4+4+4+4+8+1+1+1 = **27 B**; v5 = 4+4+4+4+4+1+1+1 = **23 B**.
v5 is the more compact encoding for both transparent-only and multi-spend Sapling txs (one shared 32 B anchor).

ZIP 225 states the design goal: with ZIP 244 "the serialized format [is] non-consensus-critical", and a
systematic per-pool layout "enables future extensibility". In practice extension still means a **new version**:
NU6.3/NU7's v6 (vgid `0xD884B698`, Zakura `parameters/transaction.rs:16`) appends an Ironwood bundle
(Zakura `transaction.rs:155-175`) and ZIP 233 fields; v5 has no TLV / extension slot.

## 2. Txid and sighash

### v4: ZIP 243
- **txid** = SHA-256d of the full serialization, signatures and proofs included (Zakura
  `transaction/txid.rs:37-38` `txid_v1_to_v4` uses `sha256d`; `librustzcash6 .../mod.rs:785-793` `from_data_v4`
  hashes the written bytes; lightwalletd `ref/lightwalletd/parser/transaction.go:279-286` does the same).
- **sighash** = BLAKE2b-256, personalization `"ZcashSigHash" || BRANCH_ID` (`ref/ycash/src/script/interpreter.cpp:1207`),
  preimage: header, vgid, hashPrevouts, hashSequence, hashOutputs, hashJoinSplits, hashShieldedSpends,
  hashShieldedOutputs, nLockTime, nExpiryHeight, valueBalance, nHashType, then for a transparent input
  (prevout, scriptCode, **its own amount**, nSequence) (ZIP 243 §Specification).
- Only the amount of the input being signed is committed. Hashes are cached per tx (ZIP 143 lineage), so
  verification is linear, not quadratic (`ref/ycash6/src/script/interpreter.cpp:1171-1176` `hashPrevouts`… precompute).
- Shielded signatures (spendAuthSig, bindingSig, joinSplitSig) sign this digest with `SIGHASH_ALL`, `NOT_AN_INPUT`.

### v5: ZIP 244
- **txid** = tree of BLAKE2b-256 digests, root personalization `"ZcashTxHash_" || BRANCH_ID`:
  T.1 header, T.2 transparent (prevouts / sequence / outputs), T.3 Sapling (compact / memos / non-compact
  sub-digests), T.4 Orchard (`librustzcash6/zcash_primitives/src/transaction/txid.rs:34-68` personalizations,
  `:395-431` `to_hash`; Zakura `transaction/zip244.rs`). **Proofs and signatures are excluded** →
  "transaction identifiers will be stable irrespective of any possible malleation of witness data" (ZIP 244 Motivation).
- **auth digest** (A.1 scriptSigs, A.2 Sapling proofs/sigs, A.3 Orchard proofs/sigs; root `"ZTxAuthHash_" || BRANCH_ID`).
  Blocks must commit to it: `hashLightClientRoot` becomes `hashBlockCommitments = BLAKE2b("ZcashBlockCommit",
  hashLightClientRoot || hashAuthDataRoot || terminator)` (ZIP 244 §Block Header Changes); ycash6 computes it at
  `ref/ycash6/src/main.cpp:3305-3310`. Pre-v5 txs contribute 32×`0xFF` to `hashAuthDataRoot`.
- **wtxid** = txid ‖ auth digest (64 B); v5 must be relayed with `MSG_WTX` (0x05); v4 must not (ZIP 239).
- **sighash** (S.1–S.4) reuses the txid tree but replaces T.2 with `transparent_sig_digest`:
  S.2a hash_type, S.2b prevouts, **S.2c `amounts_sig_digest` ("ZTxTrAmountsHash") — values of *all* spent outputs**,
  **S.2d `scriptpubkeys_sig_digest` ("ZTxTrScriptsHash") — scriptPubKeys of *all* spent outputs**, S.2e sequence,
  S.2f outputs, S.2g per-input `txin_sig_digest` (prevout, value, scriptPubKey, nSequence)
  (`librustzcash6/.../sighash_v5.rs:34-36, 60-135`).
- With no transparent inputs the sighash **equals the txid**; shielded signatures sign the txid
  (ycash6 short-circuits: `interpreter.cpp:1221-1235` returns `txTo.GetHash()`).
- Stricter hash types: undefined `hash_type` and `SIGHASH_SINGLE` without a matching output are invalid
  (`interpreter.cpp:1236-1258`); v4 tolerates both.

### What the ZIP 244 property buys, and what it costs
- **Non-malleable txid.** Under v4 anyone relaying a tx can change its txid without invalidating it (scriptSig
  re-encoding within policy limits, Groth16 proof re-randomization, any witness byte), which breaks chains of
  pre-signed unconfirmed children. v5 txids commit only to effects.
- **Hardware / offline signers.** ZIP 244: "amounts_sig_digest prevents the transaction creator from lying to the
  hardware wallet about the transaction fee"; "scriptpubkeys_sig_digest helps the hardware wallet to determine the
  subset of inputs belonging to it"; "Without these commitments, the hardware wallet would need to be sent every
  transaction containing an outpoint referenced in the transaction being signed." (BIP 341 lineage.)
- **Light clients.** T.3/T.4 compact sub-digests align with ZIP 307 compact blocks.
- **Quadratic hashing:** not a differentiator — both are linear (ZIP 243 already fixed it). ZIP 244's gain is digest
  reuse between txid and sighash.
- **Costs.** (a) Verifier and signer need *every* spent output (amount + scriptPubKey) to compute any transparent
  sighash: ycash6 `PrecomputedTransactionData(tx, allPrevOutputs)` (`interpreter.cpp:1134-1188`), and the vault fork's
  RPC fabricates placeholders that are inert only because v5 is refused (`ycash6/src/rpc/vault.cpp:196-203`).
  (b) The txid is no longer "hash the bytes": every tool that computes txids (lightwalletd, explorers, wallets,
  pool software) needs a ZIP 244 implementation. (c) A second, consensus-critical block commitment
  (`hashAuthDataRoot`) and a wtxid-based relay path. (d) In ycash6 the digests cross FFI into Rust on every
  `CTransaction` construction (`ref/ycash6/src/primitives/transaction.cpp:136-155`), so parsing becomes consensus.

## 3. Version gating per upgrade

**Zcash** (spec §7.1 "txnconsensus", quoted in Zakura `zakura-consensus/src/transaction.rs:1062-1072`):
- Overwinter: v3 only. Sapling..Canopy: v4 only (vgid `0x892F2085`).
- NU5..NU6.x: v4 **or** v5. v5 invalid before NU5 (`transaction.rs:1152-1190`).
- NU6.3 (Zakura): v6 from NU6.3 (`transaction.rs:1239-1250`, mainnet height 3,428,143,
  `zakura-chain/src/parameters/constants.rs:108`).
- **NU7: v4 banned** — ZIP 2003 (status *Proposed*): "[NU7 onward] The transaction version number MUST be 5 or 6".
  Zakura enforces it in `verify_v4_transaction_network_upgrade` (`zakura-consensus/src/transaction.rs:1030-1054`),
  with `is_nu7_active` (`zakura-chain/src/parameters/network_upgrade.rs:640-642`) gating the ZIP 218 limits
  (`zakura-consensus/src/block/check.rs:448-456`); mainnet NU7 at 3,543,405 (`constants.rs:111`, "assigned by ZIP 259").
  librustzcash6 mirrors it under `cfg(zcash_unstable="nu7")`: `TxVersion::V4 … Nu7 => false, // ZIP 2003` (`mod.rs:260-267`).
  Consequence: Sprout funds become unspendable on Zcash (ZIP 2003, not burned).

**Ycash**:
- `ref/ycash` v4.5.0 (ycash-dd's base): **no v5 code at all** — only Overwinter/Sapling/ZFUTURE vgids
  (`ref/ycash/src/primitives/transaction.h:28-55`), serializer throws on anything else (`:610`), no `SIGVERSION_ZIP244`
  (`src/script/interpreter.h:100-104`), no Orchard, librustzcash pinned at `cc26e791` / zcash_primitives 0.5 (`Cargo.toml:36,62`).
- `ref/ycash6` 6.20.0: **carries the whole v5 stack dormant** — ZIP 225 serializer, `SIGVERSION_ZIP244`
  (`interpreter.h:123`), ZIP 244 via Rust FFI, Orchard bundle, `hashBlockCommitments`, Orchard tree — but mainnet
  NU5/NU6/NU6.1/NU6.2 are `NO_ACTIVATION_HEIGHT` (`ref/ycash6/src/chainparams.cpp:139-150`), so the pre-NU5 Sapling
  rule rejects a v5 tx as `bad-sapling-tx-version-group-id` (`ref/ycash6/src/main.cpp:994-1001`) and any Orchard
  bundle or branch id as `bad-tx-has-orchard-actions` / `bad-tx-has-consensus-branch-id` (`main.cpp:1201-1221`).
- `ycash6` `upgrade/vault`: v5 is **invalid under Vault** (`bad-vault-tx-version-group-id`, `ycash6/src/main.cpp:1216-1227`,
  marked *potentially relaxing*: "a later upgrade that defines the ZIP-244 vault message lifts it (U-26)"); `-nuparams`
  that schedule any of NU5..NU6.2 together with Vault are refused at init because the Vault epoch builds ZIP 221 V1
  history leaves while NU5 builds V2 (`ycash6/src/init.cpp:1542-1563`, quantum spec R-A3). librustzcash6:
  `suggested_for_branch(Vault) = V4` (`mod.rs:242-243`), `V5.valid_in_branch(Vault) = false` (`mod.rs:269-272`).

## 4. What v5 does and does not require

- **No Orchard bundle needed.** ZIP 225: Orchard fields after `nActionsOrchard` are "all omitted if nActionsOrchard = 0";
  an Orchard-less v5 tx costs one `0x00` byte. The txid still includes the Orchard slot, filled with
  `hash_bundle_txid_empty` = BLAKE2b("ZTxIdOrchardHash", "") (`librustzcash6/.../txid.rs:419-423`) — a constant,
  no Orchard crypto. Same for an empty Sapling bundle (`hash_sapling_txid_empty`, `txid.rs:413-418`).
- **Separable at the protocol level, coupled in the code.** Format/digest (ZIP 225/244) and the Orchard pool are
  independent specs; Zcash merely activated both in NU5. Proof by precedent: ycash6 already carries a rule
  that keeps v5 valid while forbidding Orchard actions (the temporary Orchard-disabling soft fork,
  `ref/ycash6/src/main.cpp:1233-1247`). But in ycash6 every v5 gate is keyed on `UPGRADE_NU5`, and NU5 also turns on
  the Orchard turnstile (`main.cpp:3352-3395`), the Orchard note-commitment tree and its empty-root anchor
  (`main.cpp:3480-3492`), ZIP 221 V2 history leaves, and `hashBlockCommitments` (`main.cpp:3305-3310`). "v5 without
  Orchard" on Ycash = either activate NU5 and forbid Orchard actions by rule, or write a new epoch that admits v5
  under different gates — both are consensus changes to `main.cpp`.
- **What a node must do beyond parsing v5:** ZIP 244 txid and auth digest (consensus); all-prevouts sighash
  precompute; `hashAuthDataRoot` in `hashBlockCommitments` (block header semantics change); ZIP 239 `MSG_WTX`
  relay and wtxid mempool keys (peer protocol ≥ 170014 in Zcash); per-bundle Sapling shared anchor; v5 coinbase
  rules (ZIP 203 expiry change, `main.cpp:1174-1188`); mining/getblocktemplate emitting the block commitments.
- **Clients:** every wallet/library must build v5 with the branch id embedded and compute ZIP 244 txids and sighashes
  (all spent amounts and scriptPubKeys). The yodl lightwalletd at the pin parses v4 layouts only
  (`ref/lightwalletd/parser/transaction.go:341-470`) and computes txids by SHA-256d (`:279-286`), so it would mis-handle
  v5. YecWallet drives ycashd over RPC and inherits whatever the node builds.

## 5. Trade-offs

| Dimension | v4 (status quo) | v5 |
|---|---|---|
| ycash-dd (zcashd 4.5 lineage) footprint | zero; the vault upgrade is built on it | **very large**: backport zcashd 5.0 NU5 — ZIP 225 serializer, ZIP 244 (new Rust FFI and a newer librustzcash than `cc26e791`), auth-data root and header commitment, ZIP 239 relay, ZIP 221 V2 leaves, plus Orchard or an explicit ban. Touches `src/primitives/`, `src/script/`, `main.cpp` |
| ycash6 (6.20.0) footprint | zero | code exists dormant; enabling is a schedule + gating change, **but** collides with Vault: R-A3 refuses NU5..NU6.2 with Vault (`init.cpp:1542-1563`), the vault opcodes/templates and `vault_*` RPC sighash are defined on ZIP 243 only (`main.cpp:1216-1227`, `rpc/vault.cpp:196-203`); defining a ZIP 244 vault message is new consensus spec (U-26) |
| Zakura (Zcash, Rust) | parse/verify v4 until NU7, then rejected (ZIP 2003) | native v5 and v6; ZIP 244 in `transaction/zip244.rs`, v4 sighash kept as `sighash/v4.rs` |
| lightwalletd / light wallets | yodl lightwalletd, YEW, YecWallet: v4 today | needs ZIP 244 txid + v5 parser in lightwalletd-dd; Zcash light-wallet SDKs already do v5 |
| hardware wallets | must be shown each spent prev-tx to trust amounts (ZIP 244 quote) | signs all amounts/scriptPubKeys: fee is provable on-device |
| exchanges / indexers | SHA-256d txid = bytes hash, universal tooling | ZIP 244 implementation required; Zcash tooling has it, Ycash-forked tooling does not |
| malleability | txid malleable by third parties (witness bytes, proof re-randomization) | txid non-malleable; wtxid identifies the exact bytes |
| sighash expressiveness | ALL/NONE/SINGLE ±ANYONECANPAY; per-input amount only; lenient hash_type | same flag set, stricter; commits to all input amounts + scriptPubKeys; no new modes (no ANYPREVOUT etc.) |
| extensibility for vault/attestation data | fixed layout; a new field = new version + extending ZIP 243 preimage in C++ | still a new version (see v6/Ironwood), but the ZIP 244 tree adds a digest leaf cleanly (cf. TZE leaf, `txid.rs:425-431`). Moot for the vault upgrade, which keeps its data in scripts/opcodes (prime directive: template > opcode > tx field) |
| size | 27 B fixed overhead (transparent-only), per-spend anchor | 23 B, shared anchor |
| future-proofing | dead end on Zcash after NU7 (ZIP 2003 Proposed); upstream librustzcash may treat v4 as legacy-only | the format Zcash builds on (NU6.3 v6, NU7, Tachyon bundles extend the v5 shape) |
| Sprout | spendable | not expressible (v4 must remain valid if Sprout funds are to stay spendable) |

## Facts the product decision rests on

1. v5 differs from v4 in four things that matter: branch id in the bytes, per-pool bundles with no Sprout, a
   non-malleable ZIP 244 txid plus a separate auth digest committed in the block header, and a sighash that signs
   every spent output's amount and scriptPubKey.
2. Orchard is **optional inside v5** (one zero byte; constant empty digest). v5 and Orchard are separable by spec;
   in ycash6's code both hang off `UPGRADE_NU5`, so separating them is a consensus change.
3. ycash-dd (v4.5.0 base) has **no** v5 code; adding it is a zcashd-5.0-sized backport touching every frozen area.
4. ycash6 already contains the full v5/ZIP 244/Orchard stack, dormant (mainnet NU5 unset). The vault upgrade line
   deliberately makes v5 invalid under Vault and refuses NU5..NU6.2 alongside Vault (R-A3), because the vault opcodes,
   templates and `vault_*` RPCs are defined over the ZIP 243 sighash; that rule is "potentially relaxing", liftable by
   a later upgrade that defines a ZIP 244 vault message.
5. Zcash will **ban v4 at NU7** (ZIP 2003, Proposed; Zakura enforces it, mainnet NU7 3,543,405). Ycash is not bound
   by that, but a v4-only Ycash diverges from the format Zcash libraries, hardware wallets and Tachyon evolve on.
6. The concrete user-visible v5 wins are non-malleable txids (pre-signed child chains, e.g. vault recovery) and
   hardware-wallet fee safety; the concrete costs are ZIP 244 in every client (lightwalletd's SHA-256d txid,
   YEW, pool/explorer tooling), all-prevouts at signing, and a new block-header commitment and relay type.
7. v5 does not by itself provide a slot for vault/attestation data; carrying new data in a tx field means a new
   version (as v6/Ironwood does) on either base.
