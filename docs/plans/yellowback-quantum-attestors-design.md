# Yellowback post-quantum signer sets: Falcon member keys for attestors and bridges (design study)

**Status: design study, 2026-10-11. Nothing is built.** This is a read-only study written for the owner's goal of
2026-10-11. It is a delta on [`yellowback-quantum-plan.md`](yellowback-quantum-plan.md) (rev 3; it reverses that
plan's D-Q-5), on [`yellowback-quantum-spec.md`](yellowback-quantum-spec.md) and on upgrade plan §15
([`yellowback-upgrade-plan.md`](yellowback-upgrade-plan.md)). The code it cites is ycash-dd `q/attest`
(`wt/q-attest`, HEAD `ae8781c20` plus the uncommitted slashing fixes in its working tree) and ycash6
`wt/q6-fees` (`c85e9ab4a`, which does not yet have the seats or Displace work).

**The goal (owner):** before mainnet, every signer-set member key is post-quantum. That covers the Yellowback
attestor set, the bridge sets (wYEC through hawkeye, and nYEC later) and every set action. After the change, no
classic elliptic-curve key can authorize a price, a vault release or a set action on Ycash.

**Why this is not "another vault application".** Vaults are the safe; signer sets are the people holding the
release keys. We've made the safe's owner key post-quantum. This work makes the release keys post-quantum, and
that can't be done by putting them in another safe.
- Every vault application (Yellowback, the wYEC bridge, the nYEC bridge) releases YEC either by the owner's key,
  which is already SLH-DSA, or by a signer set's k-of-n approval. The set members' keys are what remain classic EC.
- A fourth application that held attestor bonds in vaults would itself be released by a signer set, the same keys
  this work replaces. It would also be circular, because a bonder's own set would approve its bond's release.
  And vaults have no freeze, so slashing would have to be rebuilt.
- So bonds stay simple PQ outputs tracked by the primitive's bond bookkeeping. QS decision 1 (a separate bond
  owner) still lets a cold SLH-DSA key hold the bond.

**The design in one paragraph:**
- **Keys.** A member is identified by `member = scheme ‖ SHA256(scheme ‖ pk)`. That is 33 bytes, the
  `CPQKeyID`/PQPKH form. Its Falcon-512 public key is revealed once, in its `SET_JOIN`, and stored in per-set
  primitive state.
- **The set opcode.** `OP_CHECKSETSIG` keeps its byte (0xc0), its templates and its one-per-`EvalScript` rule.
  Under `UPGRADE_VAULT` it is **redefined**: it verifies k Falcon signatures, each naming its signer, against
  the stored keys. Nothing is activated, so redefining the opcode costs nothing. There is no new opcode, and the
  V and I templates do not change by a byte.
- **Acts.** Acts move to version `0x02`. The member fields stay 33 bytes. Signatures become
  `signer ‖ Falcon sig` elements, and the act message binds the branch ID.
- **Price bundles.** Bundles become version 2 (676-byte attestations, message `YBATTEST2`). They ride as the
  tail of the YB payload OP_RETURN (payload `0x05`), so the P2SH carrier, its EC key and its funding transaction
  are gone.
- **Bonds.** A bond is a bare `TX_PQPKH` output. Its lock lives entirely in primitive state, which is already
  true of the exit delay.
- **No EC fallback.** EC member keys are not allowed at all. Nothing is activated, so there is no migration.

## 0. Decisions proposed here (QS-*)

| # | Proposal | Rung (prime directive) |
|---|---|---|
| QS-1 | Member identity is `member = scheme u8 ‖ keyHash 32`, with `keyHash = SHA256(scheme ‖ pk)`. That is 33 bytes, the same length as today's compressed key, so every act body, state key and module record keeps its size. Member scheme: **`0x02` FN-DSA-512 only** (a later `0x03` if FIPS 206 changes the bytes). The admit key and the bond owner may also be `0x01` SLH-DSA. | per-set state; no new field |
| QS-2 | The public key is revealed **once**, in `SET_JOIN` (the body carries it; the join checks `KeyHash`), and stored per set under a new key `'p'‖setId‖member`. Signatures never carry it again. The one exception is an admit key, which has no record: its signature element carries its key. | per-set state over per-signature bytes |
| QS-3 | `OP_CHECKSETSIG` (0xc0) is **redefined in place**. The stack holds k signer groups `<sigChunk_1>…<sigChunk_c> <member:33>`. The opcode verifies Falcon natively over the unchanged `SetSigMsg`. **No new opcode, and OP_CHECKPQSIG is not reused**, so SCRIPT_ERR_PQ_COUNT is untouched. The roles 1/2 thresholds are capped at **14** (`MAX_SCRIPT_SIZE`). | opcode semantics (already an opcode); template unchanged |
| QS-4 | The act codec moves to **version `0x02`**, and `0x01` becomes `bad-vault-act-version`. A signature element is `member 33 ‖ sig`. `ActMsg2 = SHA256d("YcashSetAct" ‖ branchId u32 LE ‖ P ‖ vin[0].prevout)`. | primitive codec |
| QS-5 | YED price bundles are **version 2**. An attestation is `seq u16 ‖ price u32 ‖ citedHeight u32 ‖ sig 666` (676 bytes). The message is `SHA256("YBATTEST2" ‖ seq ‖ price ‖ citedHeight ‖ blockHash)`. | module |
| QS-6 | The bundle rides as the **tail of the YB payload push**. MINT, REDEEM, CLAIM_NOTICE and EQUIVOCATION move to payload version `0x05`; TRANSFER stays `0x03`. **The P2SH carrier is retired** (W2 option (a), which v3 specified behind `BUNDLE_CARRIER` but never shipped). | module; removes a template |
| QS-7 | Bond B becomes a bare `TX_PQPKH(bondOwner)` (35 bytes). Spendability is decided by the bond index: not frozen, `exitHeight ≠ 0`, `h ≥ exitHeight + maturity`, and **new** `h ≥ bondLocktime`. **Owner decision: is `bondOwner` the member key (QS-7a), or a separate 33-byte field (QS-7b)?** | per-set state; template simplified |
| QS-8 | All non-cryptographic checks run before any signature verify, and the first failure aborts. Pure-crypto results go through the existing PQ signature cache; membership is never cached. | — |
| QS-9 | Policy only: raise the YV act OP_RETURN limit from 1,200 to 12,288 bytes; allow a YB payload OP_RETURN of up to 4,200 bytes; template inputs (V/I) get `MAX_SCRIPT_SIZE` (10,000) as their standard scriptSig limit. | policy |

## (a) Inventory: every set-member EC key in consensus today (ycash-dd `q/attest`)

| # | Where (file:line) | What the EC key does | Frequency | Bytes today |
|---|---|---|---|---|
| 1 | `src/script/interpreter.cpp:1010-1053` `OP_CHECKSETSIG`, `:223` `IsCompactSetSignature` | k recoverable ECDSA set signatures for vault UNLOCK (role 1) and intent CANCEL (role 2); membership is checked by key recovery | every bridge unlock and every YED/bridge cancel | 65 B per sig (66 pushed) |
| 2 | `src/vault/checker.cpp:28-40`, `src/vault/act.cpp:325-338` `SetSigMsg` | message `SHA256d("YcashSetSig"‖setId‖role‖prevout‖sighash)` (the ZIP-243 sighash binds the branch ID) | as 1 | 32-B message |
| 3 | `src/vault/state.cpp:289-307` `SetSnapshot::CheckSetSigs` | recovers each signer and checks it is a distinct current member | as 1 | — |
| 4 | `src/vault/act.h:55-112`, `act.cpp:114-125` body sizes; `act.cpp:312-323` `ActMsg`; `:347-368` `RecoverSig`/`SignRecoverable` | YV act codec: `admitKey 33` (SET_CREATE), `memberKey 33` (JOIN 70, HEARTBEAT 65, REMOVE 66), `sigA/sigB 65` (EQUIVOCATION 264); act signatures S_i, 65 B each, over `ActMsg` (**no branch ID**) | per act | as listed |
| 5 | `src/vault/state.cpp:663-668` | every act signature is recovered to a key | per act | 65 B per S_i |
| 6 | `state.cpp:702-714` SET_JOIN | the joiner's self-signature; on a non-OPEN set, `slashThreshold` cosigners or the admit key | per join | 70 + 65 × (1 + cosigners) |
| 7 | `state.cpp:746`, `src/vault/template.cpp:283-315`, `template.h:131-136` | **Bond B** = P2SH(`<locktime> CLTV DROP <memberKey:33> CHECKSIG`): the member's EC key spends up to 20,000 YEC | per join / withdrawal | 23-B output, ~107-B redeem plus DER sig |
| 8 | `state.cpp:777-786` SET_HEARTBEAT | self-signed liveness | 1 per member per day (`heartbeat_blocks` 1,152; `livenessWindow` 2 days, D-U5) | 69-B payload + 65 |
| 9 | `state.cpp:788-828` SET_REMOVE | a cosigned slash vote (`slashThreshold` sigs, burn 0/1, including a member that already left) or `set_leave` (self) | rare | 66 + 65 × n |
| 10 | `state.cpp:829-851` SET_EQUIVOCATION | two set signatures recovering to one key → ejection and a frozen bond | rare | 264 |
| 11 | `state.cpp:852-862` SET_WINDDOWN | `slashThreshold` cosigners | once per set | 32 + 65 × n |
| 12 | `state.h:39,120-144,169`; `module.h:78,89,99` | state keys `'m'‖setId‖memberKey(33)`; `BondRecord.memberKey`; the `Ejections`/`Displace`/`Liveness` hooks return `CPubKey` | — | 33-B key |
| 13 | `src/yellowback/attest.h:21-54`, `attest.cpp:38,51` | price attestation: `seq‖price‖citedHeight‖sig64`, compact ECDSA, message `YBATTEST1` | ~115 signed per attestor per day off chain (k = 10); 4–6 per MINT / CLAIM_NOTICE / claim REDEEM on chain | 74 B |
| 14 | `src/yellowback/bundle.h:27`, `bundle.cpp:114-170` `VerifyBundle` | bundle `"YA"‖1‖count‖74·n`, at most 6 (fits one 520-byte push) | per mint/claim | 448 B for 6 |
| 15 | `src/yellowback/script.h:134-148`, `bundle.cpp:72-104` | the P2SH **carrier** (`OP_SWAP OP_SHA256 <h> OP_EQUALVERIFY <pk> OP_CHECKSIG`). Its key is the minter's, not a member's, but it is EC and it exists only because a bundle needs a 520-byte push | per mint/claim, plus a funding transaction | 71-B redeem, ~600-B input, ~226-B funding transaction |
| 16 | `src/yellowback/state.cpp:1728-1750` `EquivocationEvidence`/`EquivocatedBy` | EQV-1: two prices for one (seq, citedHeight) | rare | 2 × 74 |
| 17 | `state.cpp:1790-1822` `AttestationLiveness` | raises `lastAct` from attestations in bundles, **verifying each attestation against every member by trial** (up to 6 × 15 verifies per transaction) | per mint/claim | — |
| 18 | `state.cpp:1858-1874` `RefusedAttestorSetAct` | recovers the signer to tell a self-exit from a vote | per act on the attestor set | — |
| 19 | `src/yellowback/view.h:431-452` `AttestorRecord.attestorPubKey/bondPubKey` | the module's mirror of the members (the index never reads the vault DB, finding 40) | per join | 2 × 33 |
| 20 | `src/yellowback/index.cpp:821` (`yed_addattestation`), `txbuilder.cpp:1777-1835` (equivocation builder) | node policy and wallet side of 13 and 16 | — | — |
| 21 | `src/rpc/vault.cpp:565,802-806,1171,1438-1447` | `vault_decodescript`, `set_signact`, `set_sendact`, `set_signunlock`/`set_signcancel` recover and sign with EC member keys | — | — |
| — | Not member keys: `ATTESTOR_REGISTER`/`ATTESTOR_REVIVE` payloads (`payload.h`) are invalid after activation (finding 41) and never appear on this line | | | |

ycash6 (`wt/q6-fees`) has items 1–16 at shifted lines (`interpreter.cpp:1013`, `vault/state.cpp:296,643,760`).
It does not yet have the Displace/exit-delay work, which arrives with the q/attest port.

**Off-chain and on other chains** (from the client survey):
- **hawkeye.** It holds one secp256k1 secret, used three ways:
  - imported into the node (`hawkeye enroll` → `importprivkey`), so Ycash signing goes through `set_*` RPCs;
  - as the Ethereum guardian address (`keccak256(pk)[12:]`, EIP-712 Mint/Challenge/Set*);
  - as the NEAR guardian key.
- **wyec (`WyecBridge.sol`).** It verifies **only EIP-712 ecrecover by guardian addresses**
  (`proposeMint :226`, `challengeMint :246`, `_checkThreshold :438-442`). **No contract verifies any Ycash-side
  set or attestor signature.** The "one key on both chains" link (`docs/wyec-contract-design.md:51-54`) is
  convention only; hawkeye derives it.

## (b) Design

### b.1 Key type and storage (item 1)

- **Identity.** `member = scheme u8 ‖ keyHash 32`, the existing `CPQKeyID` (`src/script/standard.h:38`)
  serialised as scheme then hash, exactly as the MINT payload's owner (quantum spec §3.1). Hex is 66 characters,
  like a compressed key, so RPC field widths do not move.
- **Scheme.** A member must be scheme `0x02` (FN-DSA-512, padded: 897-byte key, 666-byte signature without a
  hashtype byte). `IsPQFalconActive(params, h)` must hold, or the join fails with `bad-vault-act-params`.
- **Where the key lives:**

  | State key | Value | Size per member |
  |---|---|---|
  | `'m'‖setId‖member(33)` → `MemberRecord` | unchanged fields | ~60 B |
  | `'p'‖setId‖member(33)` → `pk` (**new**) | the 897-byte public key, written by SET_JOIN | 897 B + 67-B key |
  | `'b'‖outpoint` → `BondRecord{setId, member(33), frozen, exitHeight}` | `CPubKey` becomes `CPQKeyID` | unchanged length |

  - **Size.** At most 15 current members per set, so ≤ 15 × ~1 KB ≈ 15 KB of state per set. History grows
    by ~1 KB per join, and every join costs a bond plus a fee.
  - **Pruning.** The `'p'` record is erased (undo-covered) when the member's bond is spent and its status is not
    ACTIVE. From then on no signature by it can count and no slash can reach it.
  - **Loading.** `SetSnapshot::Load` keeps loading only `'m'` records. Keys are point-read per signer (k ≤ 14).
  - **Hash form.** It hides nothing for a PQ key, but it keeps every identifier at 33 bytes and lets bond and
  member outputs commit to the key before it is revealed.
- **Module mirror (YED).** `AttestorRecord.attestorPubKey`/`bondPubKey` (33 B) become `member` (33 B), and the
  module stores the 897-byte key under its own key (`'K'‖seq`). The index therefore still rebuilds without
  reading the vault DB. `SCHEMA_VERSION` goes from 11 to 12.

### b.2 Group signatures: `OP_CHECKSETSIG` verifies Falcon natively (item 2)

**Three ways to do it:**
1. **A new opcode `OP_CHECKSETPQSIG`.** It needs a byte (0xc3), new templates (V and I lose their byte
   identity), and leaves the old opcode as dead weight.
2. **Act-level k-of-n checks outside the interpreter.** An unlock would carry its signatures in an OP_RETURN that
   the primitive checks, which breaks the "script decides who may spend" model and the S-1/U-17 snapshot design.
3. **Redefine 0xc0.** It is unactivated, so this is free. The template bytes, the checker interface, the
   one-per-`EvalScript` count (`SCRIPT_ERR_SETSIG_COUNT`) and the role/threshold model all stay. **Chosen.**

**Why not reuse `OP_CHECKPQSIG`.** That would need k executions per script, which R-B1 forbids
(SCRIPT_ERR_PQ_COUNT). It also needs one script-supplied key hash per signer, while set membership must be read
from state (U-13). `OP_CHECKSETSIG` is already the bounded k-signature opcode; only its signature format changes.

**Rule text (replaces upgrade plan §15.2 steps 3–5):**
1. Pop `role` and then `setId`, as today.
2. `k = SetThreshold(setId, role)`; an unknown set is `SCRIPT_ERR_SETSIG`.
3. For j = 1..k, starting at the stack top:
   1. Pop `member`: exactly 33 bytes, and a scheme that is registered for members.
   2. Pop `c = ceil(SigSize(scheme)/520)` chunks (Falcon: c = 2). Every chunk but the last must be exactly 520
      bytes (canonical chunking), and the concatenation must be exactly `SigSize(scheme)` (666).
   3. Anything else is `SCRIPT_ERR_SETSIG`. No count pushes are needed, because the scheme fixes c.
4. **Before any verify:**
   - all k members are distinct;
   - each is a current member of `setId` in the snapshot (§15.4);
   - each stored key is present, and its `KeyHash` equals the member's hash (defence in depth: the join checked it).
5. `msg = SetSigMsg(setId, role, prevout, sighash)`, **unchanged**. `sighash` is ZIP-243 under
   `consensusBranchId` with `SIGHASH_ALL`; there is no hashtype byte on a set signature.
6. Verify each signature with `pq::Verify(scheme, pk, sig, msg)` through the PQ signature cache. The first failure
   is `SCRIPT_ERR_SETSIG`. Success pushes 1.

**scriptSig shapes:**
- UNLOCK: `<s1_1:520> <s1_2:146> <m_1:33> … <sk_1> <sk_2> <m_k> OP_1`
- CANCEL: the same, ending in `OP_2`

**Per signer** it costs 523 + 148 + 34 = **705 bytes**. With `MAX_SCRIPT_SIZE` = 10,000, k ≤ 14. That gives a
new SET_CREATE rule: `unlockThreshold, cancelThreshold ≤ MAX_SETSIG_K = 14`. Slash and wind-down thresholds stay
≤ 15, because they are act signatures in an OP_RETURN, which is never executed and so has no 10,000-byte bound.

**Bindings and gating:**
- **Branch.** It is bound through the sighash (ZIP-243 commits `consensusBranchId`), as today.
- **Prevout and role.** Bound as today, so equivocation stays provable from two signatures alone (U-14).
- **Checker.** `CheckSetSigs` keeps its signature. `SetSnapshot::CheckSetSigs` takes `(member, sig)` pairs
  instead of recoverable signatures.
- **Falcon gate.** The opcode passes the interpreter's `SCRIPT_VERIFY_PQ_FALCON` flag to the checker. Without it,
  a Falcon member signature is `SCRIPT_ERR_SETSIG`, as `OP_CHECKPQSIG` returns `SCRIPT_ERR_PQ_SCHEME`. On mainnet
  and testnet the flag is set from the vault activation (D-Q-2).

### b.3 Acts: version `0x02` (item 4)

`OP_RETURN <P> <S_1> … <S_n>`, with `P = "YV" ‖ 0x02 ‖ type ‖ body` and every integer little-endian.

| Type | v2 body | Size (Falcon member) |
|---|---|---|
| 0x01 SET_CREATE | as v1, with `admit 33` (= scheme ‖ keyHash; scheme 0x01 or 0x02) in place of `admitKey 33`; new rule `unlockThreshold, cancelThreshold ≤ 14` | 64 (unchanged) |
| 0x02 SET_JOIN | `setId 32, member 33, bondLocktime u32, bondVout u8, [bondOwner 33 — QS-7b only], pk (PubKeySize(member.scheme))` | 967 (QS-7a) / 1,000 (QS-7b) |
| 0x03 SET_HEARTBEAT | `setId 32, member 33` | 65 (unchanged) |
| 0x04 SET_REMOVE | `setId 32, member 33, burn u8` | 66 (unchanged) |
| 0x05 SET_EQUIVOCATION | `setId 32, prevout 36, member 33, roleA u8, sighashA 32, sigA 666, roleB u8, sighashB 32, sigB 666` | 1,499 |
| 0x06 SET_WINDDOWN | `setId 32` | 32 (unchanged) |

**Signature element** `S_i` (one push; an OP_RETURN push may exceed 520 bytes because it is never executed, and
the canonical-encoding check of `DecodeAct` stands): `signer 33 ‖ sig(SigSize(signer.scheme))`. That is 699 B
for Falcon.

**The admit key's element.** On a JOIN to a non-OPEN set with fewer than `slashThreshold` current members, the
admit key signs. Its element is `signer 33 ‖ pk ‖ sig`, with `KeyHash(pk)` checked against `SetRecord.admit`.
The decoder tells the two forms apart by length, which the signer's scheme fixes. An SLH-DSA admit element is
33 + 32 + 7,856 = 7,921 B, which is fine for a founder's cold key.

**Message** `ActMsg2 = SHA256d("YcashSetAct" ‖ consensusBranchId u32 LE ‖ P ‖ vin[0].prevout)`. Binding the
branch ID is new. It closes replay of an act across a chain split, or into a later upgrade with different act
semantics, at the cost of 4 bytes of hashing.

**Rules** (only the differences from §15.5):
- **Signer identification.** A signer is identified by `S_i.signer` and verified against its stored key, or for
  the JOIN self-signature against the body's `pk`. Recovery is gone, so `RecoverSig`/`SignRecoverable` and
  `IsCompactSetSignature` are deleted.
- **SET_JOIN.**
  - `KeyHash(member.scheme, pk) == member.hash`.
  - `S_1.signer == member`, and `S_1` verifies under the body's `pk`. This is proof of possession, so a key
    nobody holds cannot be seated and a stranger's key cannot be squatted.
  - Cosigners and admit as today.
  - The bond output is per QS-7.
  - Writes `'p'`.
- **SET_HEARTBEAT, set_leave (a self SET_REMOVE), SET_REMOVE votes, SET_WINDDOWN.** Exactly as today, with each
  `S_i.signer` in place of the recovered key. The D-Q-31 rules (slash in the exit delay, no rejoin over an
  unspent bond) are untouched; they compare 33-byte identities, as now.
- **SET_EQUIVOCATION.**
  - The body names `member`.
  - Both signatures verify under the stored key of `member` over their `SetSigMsg`.
  - `(roleA, sighashA) ≠ (roleB, sighashB)`, as today. Two different Falcon signatures over **the same** message
    are not equivocation: Falcon is randomized, and the rule already compares messages, not signatures.
- **Signature count.** Exact and distinct, as today.
- **Order of checks.** The cheap checks (decode, counts, distinctness, membership, key present) all run before
  any verify. Verify results go through the PQ signature cache.

### b.4 Price bundles: format v2 in the payload tail (item 3)

**Attestation v2 (676 B):** `seq u16 ‖ priceMicroUsd u32 ‖ citedHeight u32 ‖ sig 666`. The message is
`SHA256("YBATTEST2" (9 B) ‖ seq LE16 ‖ price LE32 ‖ citedHeight LE32 ‖ blockHash 32)`.
- The block hash binds the chain, as today.
- The new tag separates the format from v1.
- `seq` resolves to the member through the module's mirror (`Attestors[seq].member`, `'K'‖seq` → pk). That
  lookup is what lets a recovery-free scheme verify with one key per attestation.

**Bundle v2:** `"YA" ‖ 0x02 ‖ count u8 ‖ count × 676`. Six attestations make 4,060 B.

**The carrier.** v3 chose the P2SH carrier (W2) only to avoid a `policy.cpp` change on the frozen-file line. On
`upgrade/vault` that rule is replaced by the review gate, and policy already carries the YV and PQ carve-outs.
A 4 KB bundle does not fit a 520-byte push in an *executed* script, and the chunked alternatives either need
`OP_CAT` (to hash the chunks in script) or leave chunks on the stack, which CLEANSTACK forbids.

**QS-6.** The bundle becomes the tail of the YB payload push:

```
OP_RETURN < "YB" ‖ 0x05 ‖ type ‖ fixed body ‖ bundleV2 >
```

- **Fixed bodies.** MINT 52, REDEEM `11 + 5n`, CLAIM_NOTICE 41, EQUIVOCATION 0. They are unchanged, and the tail
  is whatever follows.
- **Versions.** MINT, REDEEM, CLAIM_NOTICE and EQUIVOCATION carry version `0x05`; their v3/v4 forms are invalid
  on this line. TRANSFER stays `0x03`.
- **When the tail may be empty.** Only where no price is read (an owner REDEEM).
- **Malleability.** The bundle sits in an output, so every input's `SIGHASH_ALL` signature commits to it. That is
  stronger than the carrier's commitment (R2), and relay cannot void or malleate it.
- **Extraction.** `ExtractBundle` keeps one extractor, the existing `OP_RETURN` path. The `SCRIPTSIG` carrier,
  `BundleCarrier`, `-yellowbackbundlecarrier`, `CarrierScript`, `carriers.dat` and the carrier funding step are
  removed (net deletion).

**Rules:**
- BUNDLE-1 runs the same checks in the same order (W8: shape, count, membership, freshness and range, then
  signatures). Verification is `pq::Verify(0x02, pk(seq), sig, msg)` through the W8 per-attestation cache, keyed
  by `SHA256(attestation676 ‖ blockHash)`.
- `aMint`/`aClaim` are unchanged: `BundleStat` over the verified attestations with bond weights.
- **EQV-1:** the EQUIVOCATION payload's tail holds exactly two attestations, with the same seq and citedHeight
  and different prices; both verify under `pk(seq)`. The ejection hook returns a `CPQKeyID`.
- **`AttestationLiveness` (a DoS fix, required).** Each attestation is verified only against its own seq's key,
  and through the W8 cache, which normally hits because BUNDLE-1 just verified it. This replaces trial
  verification against every member: 6 × 15 Falcon verifies per 4 KB transaction would be ≈ 22 verifies per KB.
- `RefusedAttestorSetAct` reads `S_1.signer` instead of recovering it.
- **Off-chain pool.** `yed_addattestation` and `yed_signattestation` carry 676-byte attestations (hex 1,352). At
  k = 10 that is ~115 signatures per attestor per day, ≈ 78 KB/day of gossip per attestor.

### b.5 Bonds (item 5)

Today's Bond B (P2SH CLTV + EC `CHECKSIG`, upgrade plan §15.3) is replaced by a **bare `TX_PQPKH`**:

```
<bondOwner.hash:32> <OP_1|OP_2> OP_CHECKPQSIG
```

- The output is 35 bytes and is spent like any PQPKH output.
- It is bare because a P2SH redeem script with `OP_CHECKPQSIG` is non-standard (R-B2). It is also simpler: the
  bond value is already public through the bond index.

**The lock moves entirely into primitive state**, where the D-Q-30/31 exit delay already lives
(`state.cpp:451-455`). A bond outpoint in the index is spendable only if:
- it is not frozen;
- `exitHeight ≠ 0`;
- `h ≥ exitHeight + maturity`;
- **new:** `h ≥ MemberRecord.bondLocktime`. This replaces the script's CLTV, so `bondLockMin` keeps its meaning.

Otherwise the spend fails with `bad-vault-bond-frozen` or `bad-vault-bond-locked`, as today. SET_JOIN checks that
`vout[bondVout].scriptPubKey == PQPKH(bondOwner)` and that its value is at least `bondMin`. `BuildBondRedeem`,
`ParseBondRedeem` and `BondScriptPubKey` go, along with the YED module's own v3 `BondScript`, which is already
dead after activation.

**The owner decides who owns the bond:**
- **QS-7a: the member key (Falcon).** Zero new fields; the smallest change. The bond stays hot, as D-U4 accepted.
- **QS-7b: a separate `bondOwner 33` field in SET_JOIN, scheme 0x01 or 0x02.** It costs 33 bytes and one
  equality check. It lets an operator hold up to 20,000 YEC under a **cold SLH-DSA key**, a final FIPS 205
  standard with no signer side channel, while the hot Falcon key signs prices ~115 times a day. Slashing is
  unaffected, because it acts on the bond index and not on the key. It reverses the "given up" note of D-U4.
  **Recommended.**

### b.6 Everything that carries a set signature (item 4, summary)

| Action | Carrier | Signatures (Falcon) | Key source |
|---|---|---|---|
| Unlock / cancel (bridge release, YED claim cancel) | template input scriptSig | k × 705 B (k = unlockThreshold or cancelThreshold, ≤ 14) | state `'p'` |
| SET_JOIN | YV act | self 699, plus cosigners × 699, or admit (with pk) | body pk / state / inline |
| SET_HEARTBEAT | YV act | 1 × 699 | state |
| set_leave (self SET_REMOVE) | YV act | 1 × 699 | state |
| Cosigned slash vote (SET_REMOVE burn) | YV act | slashThreshold × 699 | state |
| SET_WINDDOWN | YV act | slashThreshold × 699 | state |
| SET_EQUIVOCATION | YV act body | 2 × 666 (no S_i) | state |
| Price attestation (MINT / CLAIM_NOTICE / claim REDEEM) | YB payload tail | 4–6 × 676 | module mirror |
| EQV-1 | YB payload tail | 2 × 676 | module mirror |

### b.7 Signature cache

Today set signatures bypass every cache (upgrade plan §15.2), because membership is snapshot-dependent. Under this
design:
- **Crypto results are cached.** `(scheme, msg, pk, sig) → valid` goes through the existing PQ signature cache.
  That cache's entry is `SHA256(pqNonce ‖ scheme ‖ msg32 ‖ len‖pk ‖ len‖sig)`, it stores successes only, and it
  is reviewed A+B on both lines. Its key already binds the 32-byte message, so feeding it `SetSigMsg` or `ActMsg2`
  instead of a sighash is safe.
- **Membership is never cached.**
- **One helper for every caller.** A `pq::CachedVerify` used by the checker, `ApplyAct` and the module (W8
  stays as it is) means a block whose transactions the node saw in its mempool connects in milliseconds.
- **ycash6.** It has no script-execution cache (finding 22); the PQ signature cache is present on both lines.

### b.8 Falcon gating

- **Mainnet and testnet.** `pqFalconHeight = 0` (D-Q-2), so Falcon is active wherever `UPGRADE_VAULT` is, and sets
  are Falcon from their first act.
- **Rules.** SET_CREATE (admit scheme 0x02), SET_JOIN (member or bondOwner scheme 0x02) and any Falcon signature
  verify require `IsPQFalconActive(params, h)`; the opcode reads `SCRIPT_VERIFY_PQ_FALCON`.
- **Regtest.** A `-pqfalconheight` above the vault height means no set can have members until Falcon activates.
  So a regtest run of the "Falcon inactive" regime cannot run YED or a bridge. Those suites either set
  `-pqfalconheight` ≤ the vault height or drop that regime (owner item O-7).

### b.9 Malleability

- **Signatures.** Falcon padded signatures have a unique encoding: the audit's 34 M mutation runs found no
  accepts (Falcon audit F-2 and §malleability). Only the signer can produce a second valid signature, because
  Falcon is randomized. Set signatures then behave like ECDSA in a scriptSig today: signer-malleable, with push
  re-encoding a policy matter (MINIMALDATA).
- **Acts and bundles.** These sit in outputs, so every input's signature commits to them: no third-party
  malleability.
- **The sign-once guard (finding 70).** It refuses a second, *different* set signature for the same
  (setId, prevout). It must key by (setId, member, prevout) and compare **sighash**, not signature bytes,
  because re-signing the same sighash with Falcon yields new bytes. That is still not equivocation.

### b.10 DoS: verification cost per block and size limits

- **Per-byte bound.** Every Falcon verify that counts in a valid block consumes ≥ 666 bytes of distinct signature
  data: 705 per set signature, 699 per act signature, 676 per attestation.
  - **Valid blocks.** Signatures cannot be reused across signers (distinct members) or across messages (prevout
    and sighash bound), so a 2 MB block holds ≤ ~3,000 Falcon verifies ≈ **80 ms** single-threaded at the
    measured 26.5 µs. For comparison, a P2PKH-full block is 0.26 s and a Falcon PQPKH block 0.03 s (Q6). Acts
    and bundles apply serially in `ApplyBlock` and the index; set signatures verify in the script threads.
  - **Invalid blocks.** Checking all membership first and aborting on the first failed verify bounds an invalid
    attempt at ≤ (valid signatures supplied) + 1 verifies.
  - **Staged outputs.** A staged-output trick (signature bytes parked in a bare output, the R-A1/R-B1 class)
    cannot pre-stage a *valid* set signature, because it must sign the spending transaction's sighash. It yields
    at most one failing verify per `OP_CHECKSETSIG` and at most two per input.
- **The one remaining multiplier is `AttestationLiveness`.** Fixed by b.4.
- **Consensus size limits.** The only new one is MAX_SETSIG_K = 14 for roles 1/2. `MAX_SCRIPT_SIZE` (10,000)
  already bounds a template scriptSig, and `MAX_BLOCK_SIZE` bounds everything else.
- **Policy limits (QS-9):**
  - YV act OP_RETURN up to 12,288 B (a 15-cosigner SET_WINDDOWN is ≈ 10.6 KB);
  - one YB payload OP_RETURN up to 4,200 B, only where `UPGRADE_VAULT` is active at tip+1;
  - template inputs get a standard scriptSig limit of 10,000 B, because `MAX_STANDARD_PQ_SCRIPTSIG` 9,000 is
    below 14 × 705.
- **Sigops.** Set signatures still count 0 consensus sigops (the precedent of `OP_CHECKSETSIG` and F-5). Policy
  counts PQ_SIGOP_COST (20) per signature in the block template.

### b.11 EC keys and migration

**EC member keys are not allowed at all.**
- Act version `0x01` is invalid.
- `OP_CHECKSETSIG` accepts only the PQ signer-group shape.
- `admit`, `member` and `bondOwner` must be PQ schemes.

**What can still be EC.** EC keys survive only where they authorize nothing set-related: plain YEC fee inputs
that fund an act, mint or unlock. Consensus cannot tell those apart and need not. Operator wallets should default
to `sq…` coins (policy and wallet; see O-2).

**No migration.** Nothing is activated on any network. The changes are:
- `vault_vectors.json`, `yellowback_golden.json` and every devnet/regtest fixture regenerate;
- `rpcversion` moves to 9;
- **D-Q-5 is reversed for the Ycash side.**

**Ethereum (wyec) keeps secp256k1 guardians** (see e.3).

### b.12 Software (item 6)

- **Node, primitive RPCs.**
  - `set_join`/`set_heartbeat`/`set_leave`/`set_create` take or return a `member` (66 hex) and a `scheme`.
    `set_join` takes the joiner's PQ key from the wallet's PQ keystore (Q5 HKDF derivation). A new
    `set_getnewmemberkey` returns `{scheme, member, pk}`, mirroring `vault_getnewowner`.
  - `set_signact`/`set_signunlock`/`set_signcancel` sign with `pq::Sign`. `set_equivocation`'s proof grows to
    two 666-byte signatures plus `member`.
  - `set_getinfo.memberlist[]` carries `member`, `scheme`, and the `pk` on request.
  - `vault_decodescript` decodes v2 acts and signer groups.
  - `doc/vault-rpc.md` and `vault-rpc-contract.json` follow.
- **YED RPCs.**
  - `yed_signattestation`/`yed_addattestation` handle 676-byte attestations.
  - `yed_listattestors.attestorPubKey` becomes `member`, plus `scheme`; the pk is on request.
  - `yed_registerattestor` sends the v2 join.
  - `yed_reportequivocation` builds the v5 EQUIVOCATION.
  - Builders (`txbuilder.cpp`) lose the carrier step (and `carriers.dat`) and write the bundle tail.
  - Fees use the existing $/KB rule (D-Q-26). `rpcversion` 9.
- **Attest agent (Rust, `contrib/yellowback/attest`).** It holds no key and signs through the node. Only the
  heartbeat argument changes (~10 lines plus fixtures).
- **Python framework.**
  - `vault.py`: act v2 codec, signer groups, `ActMsg2`.
  - `yellowback_attest.py`: Falcon attestation signer, using the framework's existing Falcon signer from `q/pyfw`.
  - `yellowback_model.py`: bundle v2, payload v5, liveness by seq.
  - `bridge-sim`, `yellowback-devnet`, `upgrade-walk`.
- **hawkeye.** ~800–1,000 lines.
  - `keys.rs`: the member becomes 33-byte `CPQKeyID`; canonical member order by member id.
  - `setsig.rs`/`attribution.rs`: verify instead of recover; attribution reads the signer id from each group.
  - `template.rs` bond: PQPKH.
  - Store schema: `member_key` 33 B, so the length is unchanged and only the meaning changes.
  - `enroll`: a PQ key in place of `importprivkey`.
  - Plus a separate secp256k1 **guardian key** (e.3).
- **wyec.** No contract change. The design doc's "same key on both chains" (`docs/wyec-contract-design.md:51-54`)
  is rewritten.
- **YEW.** ~150 lines plus vectors. Bundle v2 verify (the `fn-dsa` crate is already in the core for holders),
  Seated `u16 → member` plus pk fetch, payload v5, act decode, the vault template note.
- **chain-viz.** ~40 lines: decode YV v2 acts (member ids, signer groups), payload v5 tails, member scheme display.
- **lightwalletd.** ~40 lines: `vault-rpc-contract.json` fixtures (`memberkey` → `member`, still 66 hex); the
  read passthroughs are unchanged; strip `pk` from public proxies if it bloats responses.
- **YecWallet.** ~40 lines: attestor and member display (66-hex member id plus a scheme badge), and a
  heartbeat argument.
- **x402.** ~60 lines: payload v5 decode for MINT/REDEEM (it reads them), vectors. Its channel keys are not set
  keys.
- **yb-calibration.** Heartbeat and mint cost rows (§c) and a bond-economics note.

## (c) Size and fee impact

Assumptions:
- **Rates.** D-Q-26: $0.05/KB for Yellowback and vault transactions, YEC = $0.40, so 1 KB = $0.05 = 0.125 YEC.
- **Transaction overhead.** A v4 transaction carries 29 B of overhead.
- **Funding input.** Either a Falcon PQPKH input (1,620 B; scriptSig 1,577 = sig 667 + pk 897 + pushes) or a
  P2PKH EC input (148 B).
- **Outputs.** PQPKH change 44 B; V 228 B; I 210 B.
- **Today.** The current `q/attest` byte forms with EC member keys (the vault owner and holder are already PQ).

Computed by a size model (scratchpad `sizes.py`); every figure is ±2 %.

| Transaction | Today (EC members) | PQ members, PQ-funded | PQ members, EC fee input |
|---|---|---|---|
| **MINT, 6-of-9 bundle** (6 attestations) | 1,508 B incl. the carrier funding transaction — $0.075 / 0.19 YEC | **6,162 B — $0.31 / 0.77 YEC** | 4,690 B — $0.23 / 0.59 YEC |
| MINT, 4 attestations (M_SELECT) | — | 4,810 B — $0.24 | 3,338 B — $0.17 |
| **Bridge release** (UNLOCK, unlockThreshold 1, hawkeye mainnet shape) | 527 B — $0.026 | **2,650 B — $0.13 / 0.33 YEC** | 1,168 B — $0.058 |
| Bridge release, 6-of-9 (bridge-sim multisig shape) | 859 B — $0.043 | 6,175 B — $0.31 | 4,693 B — $0.23 |
| UNLOCK at the cap, k = 14 | — | 11,815 B — $0.59 | 10,333 B — $0.52 |
| YED claim cancel (cancelThreshold 1) | 527 B | 2,650 B — $0.13 | 1,168 B — $0.058 |
| **Heartbeat** | 357 B — $0.018 | **2,477 B — $0.124 / 0.31 YEC** | 995 B — $0.050 / 0.12 YEC |
| **SET_JOIN** (OPEN set, QS-7b) | 394 B — $0.020 | **3,458 B — $0.17 / 0.43 YEC** | 1,976 B — $0.099 |
| SET_JOIN, non-OPEN, 4 cosigners | — | 6,266 B — $0.31 | — |
| set_leave | — | 2,478 B — $0.124 | 996 B — $0.050 |
| Slash vote, 4 / 7 / 14 cosigners | — | 4,584 / 6,690 / 11,604 B — $0.23 / $0.33 / $0.58 | — |
| **SET_EQUIVOCATION** | 494 B — $0.025 | **3,211 B — $0.16** | 1,729 B — $0.086 |
| EQV-1 (price equivocation) | 811 B incl. carrier funding | 3,068 B — $0.15 | 1,586 B — $0.079 |

**Per attestor per day (one heartbeat):**
- **PQ-funded:** $0.124/day ≈ **$3.7/month ≈ $45/year** (0.31 YEC/day).
- **EC fee input:** $0.050/day ≈ $1.5/month.
- **Today:** $0.018/day.
- **Against revenue.** At D-Q-25's low-adoption attestor revenue (≈ $7/seat/month) a PQ-funded heartbeat eats
  about half. The module's `AttestationLiveness` hook already credits liveness from attestations carried in
  mints, so a daemon can skip the on-chain heartbeat on days when its attestation was included. That is agent
  policy and needs no consensus change.
- **Set-wide.** 15 YED seats ≈ $56/month PQ-funded; each bridge set of 7 ≈ $26/month.

**Every row stays under the network-fee cap** (min(max(-maxtxfee, $2), 10 YEC)) and inside D-Q-26's acceptable
range ($0.05–$0.50), except the k ≥ 12 unlock and slash shapes, which are rare. **Chain growth:** at 50
mints/day, the bundle bytes add ≈ 0.23 MB/day (≈ 85 MB/year) over today.

## (d) Estimate and phase plan

### Lines per node line (ycash-dd; ycash6 ports byte-identical files, ~same size)

| Area | Files | Consensus lines | Notes |
|---|---|---|---|
| Primitive: opcode | `script/interpreter.{cpp,h}` (`OP_CHECKSETSIG`, error codes), `vault/checker.{cpp,h}` | ~90 | review gate |
| Primitive: act codec v2 | `vault/act.{h,cpp}` | ~260 | delete recoverable sig code |
| Primitive: state | `vault/state.{h,cpp}` (`CPQKeyID` identities, `'p'` records, CheckSetSigs, JOIN pk/PoP, EQUIVOCATION v2, bond lock rule, pruning), `vault/module.h` hooks | ~330 | review gate |
| Primitive: bond template | `vault/template.{h,cpp}` | ~40 (net −) | |
| Policy | `policy/policy.{h,cpp}` (QS-9) | ~30 | review gate (exempt file on this line) |
| **Primitive subtotal** | | **≈ 750** | |
| Module: attestation and bundle v2 | `yellowback/attest.*`, `bundle.*` | ~200 (net −100 with the carrier gone) | |
| Module: payload v5 tail | `yellowback/payload.*` | ~150 | |
| Module: state, mirror, EQV-1, liveness, refused acts, schema 12 | `yellowback/state.*`, `view.h`, `module.*`, `index.cpp`, `script.*` (carrier and bond removal) | ~400 (+ ~250 deleted) | review gate |
| **Module subtotal** | | **≈ 750** | |
| Node non-consensus | `rpc/vault.cpp`, `rpc/yellowback*.cpp`, `yellowback/txbuilder.*`, `wallet.*`, wallet PQ signing for set and act signatures, sign-once guard, docs, RPC contracts | ~1,300 (+ ~700 carrier code deleted) | `rpcversion` 9 |
| Unit tests | `vault_act/state/script/template_tests`, `yellowback_bundle/attest/payload/state_tests`, `vault_vectors_tests` | ~1,200 | |
| Functional | ~25 suites touch `set_*` or attestors (`vault_*`, `yellowback_attest*`, `yellowback_upgrade`, `yellowback_seats/fees`, devnet walk) | ~900 | |
| Python model mirror | `test_framework/vault.py`, `yellowback_attest.py`, `yellowback_model.py`, `SERIALISATION.md` | ~600 | byte-identical across lines |
| Golden vectors | `vault_vectors.json` (acts v2, signer groups, set-sig messages), `yellowback_golden.json` (bundles v2, payload v5), Falcon set-sig cases in `pq_vectors.json`; fuzz corpora `Vault`, `YellowbackBundle` | generated | cross-line identity check |
| Devnet tooling | `bridge-sim`, `yellowback-devnet`, `upgrade-walk`, attest agent | ~250 | |

Per node line: **≈ 1,500 consensus lines** (≈ 750 primitive, ≈ 750 module), ≈ 1,300 non-consensus, ≈ 2,100 test
lines plus vectors. ycash6 is a port of the same files at about 70 % of the effort.

### Clients

| Repo | Work | Lines |
|---|---|---|
| hawkeye | PQ member key, verify-based setsig/attribution, PQPKH bond, store meaning, enroll, **separate guardian key + binding** | 800–1,000 |
| YEW | bundle v2 verify, payload v5, act v2 decode, Seated map, vectors | ~200 |
| chain-viz | act v2 and payload v5 decode, scheme display | ~40 |
| lightwalletd-dd | contract fixtures, docs | ~40 |
| yecwallet-dd | member display, heartbeat argument | ~40 |
| x402-ycash | payload v5 decode (TS + Python), vectors | ~60 |
| wyec | design doc only | doc |
| yb-calibration | heartbeat and mint cost rows, bond economics with cold bonds | ~100 |

### Review gates

The consensus review gate (two independent reviewers per line, rule 4's four-part check plus the rung in every
commit) applies to QS1 (opcode + codec), QS2 (state) and QS3 (module rules) on both lines. Cross-line identity
of `vault_vectors.json`, `yellowback_golden.json` and the Python model is required before each merge.

### Phases (parallel with the in-flight work)

`q/attest` changes `vault/state.*`, `vault/module.h`, `policy.*` and `yellowback/*`. It does **not** touch
`vault/act.*`, `vault/template.*`, `vault/checker.*` or `script/interpreter.cpp`.

| Phase | Scope | Branch | Can start | Size |
|---|---|---|---|---|
| QS0 | Freeze this design into a spec section (byte layouts, rules, vectors plan); owner decisions O-1..O-8 | workspace | now | 2 days |
| QS1 | Python first: `vault.py` act v2 + signer groups + `ActMsg2`, Falcon attestation signer, vectors generator | `q/pqset-py` off `upgrade/quantum-vaults` (ycash-dd) | now | 4 days |
| QS2 | Primitive codec + opcode + bond template: `act.*`, `interpreter.cpp`, `checker.*`, `template.*` (+ unit tests) — **review gate** | `q/pqset` off `upgrade/quantum-vaults` | now (no overlap with `q/attest`) | 1 week + review |
| QS3 | Primitive state: `state.*`, `module.h` hooks, policy QS-9 — **review gate** | `q/pqset` rebased onto `upgrade/quantum-vaults` after `q/attest` merges | after `q/attest` merge | 1 week + review |
| QS4 | YED module: attestation/bundle v2, payload v5, carrier removal, mirror/schema 12, liveness fix — **review gate** | `q/pqattest` off the post-`q/attest` integration tree | after `q/attest` merge (parallel with QS3 once QS2's types land) | 1.5 weeks + review |
| QS5 | RPCs, wallet signing, sign-once guard, builders, agent, docs/contracts (`rpcversion` 9), functional suites, devnet walk + roles, fuzz, DoS re-measure | `q/pqset-rpc`, `q/pqset-qa` | as QS3/QS4 land | 1.5 weeks |
| QS6 | ycash6 port (after the `q/fees` + `q/attest` ports reach `wt/q6`) with byte-identical vectors — **review gate** | `q/pqset` on ycash6 | after ycash6's fees/seats port | 1.5–2 weeks |
| QS7 | Clients (table above); hawkeye first (largest, guardian split) | each repo's `upgrade/quantum-vaults` | when QS5's RPC contract freezes | 2 weeks, parallel |

The critical path is ≈ 6–7 weeks to both node lines green, with clients overlapping the last two.

## (e) Risks and open owner decisions

### Risks

1. **Signer side channel on hot keys.** An attestor's Falcon key signs ~115 prices a day in a networked daemon.
   That is far more signing exposure than a holder key, and Falcon's known signer leakage (FALCON Down; "Every
   Signing Leaks", ePrint 2026/2124) matters most there. The mitigations are PQClean `clean` constant-time
   signing in software only, QS-7b cold bonds (a leaked hot key loses the seat, not the bond), and key rotation by
   leave and rejoin (14-day exit). The alternative is ML-DSA-44 (FIPS 204, final, 2,420-byte signature, no
   floating-point sampler). It would be a new scheme `0x03` and a new library, at ≈ 3.6× Falcon's bytes per
   attestation (a 6-attestation bundle ≈ 14.6 KB). It is not recommended now; it is recorded as the fallback.
2. **FIPS 206 drift.** As for holders: a final FN-DSA that differs makes a `0x03` scheme. Members then rotate by
   exit and rejoin (exit window ≥ 14 days, D-Q-31). Every client keeps the `0x02` verifier.
3. **Ethereum stays EC (D-Q-5, Ethereum side).** WyecBridge mints are authorized by secp256k1 guardians, and
   EIP-8052's Falcon precompile is not live. A quantum attacker who forges guardian signatures can mint unbacked
   wYEC on Ethereum, burn it, and ask hawkeye to release real YEC. Releases need the Falcon set signature, but
   honest Falcon members sign burns they observe. Mitigations:
   - the set's rate limit (S-3) bounds releases per epoch;
   - hawkeye must check the supply invariant (wYEC supply ≤ locked YEC) before signing a release, which is a
     hawkeye rule and not a consensus one;
   - the owner recovery path stands;
   - move guardians to Falcon when EIP-8052 (or a Solidity Falcon verifier at acceptable gas) is available.
4. **The key split in hawkeye.** One secp256k1 key no longer serves Ycash, Ethereum and NEAR. The member key
   (Falcon) and the guardian key (secp256k1) must be bound, or an operator could seat a Falcon key and register
   someone else's guardian address. See O-3.
5. **Heartbeat economics.** These are 7× today's bytes (see §c). They are cheap in absolute terms, but they are
   the largest recurring cost for low-revenue attestors.
6. **Bigger acts and mints are fine for consensus** but need the QS-9 policy limits on both lines identically.
   ycash6's ZIP-317 conventional fee bills OP_RETURN bytes differently: check `yellowback_fee.py` there.
7. **Review load.** ≈ 1,500 consensus lines per line, on top of the in-flight seats, slashing and fees reviews.
8. **The regtest Falcon-inactive regime.** It can no longer exercise YED or bridges (b.8).

### Open owner decisions

| # | Decision | Recommendation |
|---|---|---|
| O-1 | Bond owner: the member's Falcon key (QS-7a, smallest) or a separate `bondOwner` (QS-7b, SLH-DSA cold allowed, reverses D-U4's "given up") | **QS-7b** |
| O-2 | Fee and funding inputs of acts, mints and unlocks: leave EC allowed (consensus cannot tell; they authorize nothing set-related), with operator wallets defaulting to `sq…` | **allow; wallets default PQ** (costs ≈ 1.5 KB per transaction) |
| O-3 | Binding of a member's Falcon key to its Ethereum/NEAR guardian key: off-chain (a hawkeye config plus a Falcon-signed binding statement published to the set and checked by `setGuardians` signers), or a consensus field in SET_JOIN | **off-chain**: the primitive stays application-agnostic, and Ycash consensus never reads Ethereum (R2) |
| O-4 | Retire the P2SH bundle carrier for the payload tail (QS-6; reverses v3 W2/D-1 on this line) | **yes** |
| O-5 | Unlock and cancel threshold cap of 14 (`MAX_SCRIPT_SIZE`) | **accept** (hawkeye uses 1; the YED set uses 1) |
| O-6 | Member scheme: Falcon only (owner's intent), or also SLH-DSA (an SLH unlock with k ≥ 2 exceeds 10 KB) | **Falcon only**; SLH-DSA allowed for admit and bondOwner |
| O-7 | Regtest Falcon-inactive regime: drop it for sets, or keep it only for holder (TOK-PQ) tests | **keep for TOK tests only** |
| O-8 | Heartbeats: rely on attestation-carried liveness and skip redundant on-chain heartbeats (agent policy), or keep daily heartbeats | **skip when an attestation was included that day** |
| O-9 | Record D-Q-5's reversal (Ycash side) in the quantum plan, and whether this ships with the vault activation (it must: changing set formats after activation would be a further upgrade) | **ships with `UPGRADE_VAULT`** |
