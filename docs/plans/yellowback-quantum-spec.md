# Yellowback post-quantum — frozen byte layouts (Q0 spec)

**Companion to [`yellowback-quantum-plan.md`](yellowback-quantum-plan.md) revision 3; normative for the
implementation on `upgrade/quantum-vaults`.** Where this file and plan §4 differ, this file wins.

**Coordinator rulings on §7 (2026-10-10):** every recommendation in §7 is adopted as written, except
**F-5**: `OP_CHECKPQSIG` counts **0** consensus sigops (as `OP_CHECKSETSIG`; a context-free count would reprice
historical blocks, and D-Q-7 keeps fees and relay out of consensus). The 20-sigop cost is a **policy** count
(mempool acceptance and the block template). **A-12**: PQ key seed material is HKDF-SHA256 from each line's
wallet seed, byte-identical across lines (deviation from plan §4.6's BIP32 path). **F-7**: `TOK-PQ` (PQ-only YED
token outputs once `pqFalconActive`) is a new consensus rule and goes through the review gate.

**Rulings after the client survey (`yellowback-quantum-clients.md`, 2026-10-10):**
- **F-2 superseded (C-1):** only **MINT** carries payload version **`0x04`** (its owner field changed); every other
  type stays **`0x03`**, so client TRANSFER builders are unchanged and no v3 TRANSFER is burned. A MINT at `0x03`
  is invalid on this line. Smallest footprint; one version byte per type.
- **C-4:** the node wallet gains `vault_getnewowner` → `{scheme, keyhash, address}` (Q5); hawkeye's `lock` uses it.
- **C-5:** `yed_getinfo.params.pq` carries `feeRateZatPerKB`.
- **C-8:** Falcon keygen seed is **48** bytes (PQClean's DRBG seed), like SLH-DSA's.
- **C-3** (x402 YED channels in P2SH vs `TOK-PQ`) is deferred to the owner at Q8; `TOK-PQ` only binds after Falcon.

**Rulings after consensus review A of `q/op` (2026-10-10):**
- **R-A1 (verification bound):** with 0 consensus sigops, per-block PQ verification is bounded by
  `MAX_OPS_PER_SCRIPT` × inputs (one signature re-checked ~11× via `OP_PICK`; staged in a bare output, a spend input
  is ~41 B), **the same order as the legacy `OP_CHECKSIG` loop worst case Ycash already has** (measured Q6, 2026-10-10: ≈20 µs/op ECDSA vs
  ≈250 µs SLH, ≈21–27 µs Falcon — R-A1's original 22/7 µs figures were wrong); both need a miner to include non-standard outputs. Accepted: a hard per-block PQ verify
  bound would need an execution-time counter, a new consensus rule. The "≈252 SLH spends per block" bound in §5.1
  and plan §6 is wrong and is replaced by this.
- **R-B1 (supersedes R-A1's "accepted"; both reviewers flagged it):** at most **one executed `OP_CHECKPQSIG` per
  `EvalScript`** where `SCRIPT_VERIFY_VAULT` is set (precedent: the set-signature count), else `SCRIPT_ERR_PQ_COUNT`.
  Every template (PQPKH, V selectors 2/3, I selector 3) executes exactly one; the cap is ≤ 3 PQ verifies per input
  (scriptSig, scriptPubKey, redeem script). What remains is the staged-output class (a non-standard bare output
  holding the signature, spent by a ~41 B input: 1 verify per input), the same class as legacy bare `OP_CHECKSIG`
  outputs, whose spends Ycash has never charged; its creation costs ~9 KB of earlier block space per verify and is
  miner-only (non-standard). Given up: PQ k-of-n in one script, e.g. a PQ 2-of-2 or a PQ x402 channel (a later upgrade can lift the cap).
  Re-review A (2026-10-10): residual bound **≤ 2 PQ verifies per input** (one in a non-push-only scriptSig, one in
  the scriptPubKey; P2SH: 1); staged outputs ≈48k verifies per 2 MB block (measured: 48,000 in 1.97 MB; 18.2 s at -par=1, 8.0 s connect at default -par; ≈ 383 MB undo and ≈ 1.2 GB peak RSS per node), the legacy CHECKSIG-at-spend order by count — by time ≈ 18× a legacy single-CHECKSIG staged block, ≈ 1.7× a full Sapling z→z block, 3.6× below the legacy multi-CHECKSIG staged block consensus already admits (ycash-dd doc/yellowback-pq-dos.md).
- **R-B2:** `AreInputsStandard`'s P2SH redeem-script check counts the PQ policy sigops toward `MAX_P2SH_SIGOPS`, so a
  redeem script containing `OP_CHECKPQSIG` is non-standard (spec §2.3's claim now holds for every shape).
- **R-B3:** `-pqfalcon`/`-pqfalconheight` on a non-regtest network is an `InitError`, like `-nuparams`.
- **R-B4:** the scriptSig encoding is unique **under standard policy** (MINIMALDATA); consensus admits re-encoded pushes,
  as for every Ycash push.
- **R-A2 (Falcon activation):** `pqFalconActive` (bool) becomes **`pqFalconHeight`** (int, `NO_ACTIVATION_HEIGHT` on
  mainnet/testnet); `SCRIPT_VERIFY_PQ_FALCON` and `TOK-PQ` apply at `nHeight >= pqFalconHeight`; regtest
  `-pqfalconheight=<h>` (and `-pqfalcon=1` ≡ height 0). A bool would split the chain at no coordinated height and
  apply TOK-PQ to history on reindex.
- **R-A3 (transaction version; audit 04/F-2, 2026-10-13):** the vault templates, `OP_CHECKSETSIG`,
  `OP_CHECKSETDORMANT`, `OP_CHECKPQSIG` and TOK-PQ are defined for **v4** (Sapling version group, ZIP-243 sighash)
  transactions only. Under `UPGRADE_VAULT` a transaction whose `nVersionGroupId ≠ SAPLING_VERSION_GROUP_ID` is
  invalid (`bad-vault-tx-version-group-id` on ycash6, `ContextualCheckTransaction`; ycash-dd has no v5 type and
  already rejects every non-Sapling group once Sapling is active, `bad-sapling-tx-version-group-id`). No ZIP-244
  message is defined for the vault opcodes; a network upgrade that brings v5 to Ycash must define it then. On
  regtest, scheduling any of NU5..NU6.2 together with Vault is an `InitError` (ycash6 builds V1 history-tree
  leaves in the Vault epoch, so no order of the two is usable). The mempool/miner rechecks and the vault RPCs'
  sighash data refuse a non-v4 transaction explicitly (`non-v4 transaction (R-A3)`) rather than compute a
  digest over placeholder coins. librustzcash6 agrees: `BranchId::Vault.has_orchard() = false`,
  `TxVersion::V5.valid_in_branch(Vault) = false`.
- Push minimality of `s`/`p`/scheme is **policy** (MINIMALDATA); consensus requires a 1-byte element. §0's
  `PQ_SIGOP_COST` row means the policy count only. `getblocktemplate`'s per-tx `sigops` includes the PQ policy count.

**Rulings after the Q3 reviews (2026-10-10):** Q3, Q5 and Q4 merge into `upgrade/quantum-vaults` as **one unit**, gated
on Q4's MINT-3 Falcon gate, MINT payload 0x04, regenerated `yellowback_golden.json` + Python model, and a green YED
functional suite. **The old EC-owner V/I skeleton is `Shape::NONE`** (an ordinary output, not MALFORMED): smaller
consensus footprint; such an output is non-standard, so only a miner can create one, and if it does the set (selector 1,
no covenant) or, after `appHeight`, anyone (selector 4) can spend it. **A chain carrying `upgrade/vault`-era EC vaults is
not compatible with this line** (no public network has either). **Policy refuses scheme-2 V re-locks before Falcon**, so
a miner-created scheme-2 vault can only be unlocked without re-lock until then. The selector is outside the sighash:
a selector-2 owner signature also satisfies selector 3 for the same transaction, as with EC.

**D-Q-19 — hybrid payment-channel template `TX_PQCHANNEL` (owner, 2026-10-10).** Bare output, standard once the vault
upgrade is active at tip+1 (P2SH is not used: R-B2 makes PQ redeem scripts non-standard):
```
OP_IF
  <clientHash:32> OP_1|OP_2 OP_CHECKPQSIG OP_VERIFY  <serverKey:33 compressed> OP_CHECKSIG
OP_ELSE
  <refundHeight> OP_CHECKLOCKTIMEVERIFY OP_DROP  <clientHash:32> OP_1|OP_2 OP_CHECKPQSIG
OP_ENDIF
```
bytes `63 20<h> 5n c2 69 21<pk> ac 67 <num> b1 75 20<h> 5n c2 68` (111 B + the refund-height push = 112–117 B); both client slots byte-identical
(scheme and hash), `refundHeight` a minimal positive CScriptNum (1–5 bytes, < 500,000,000 = a height), server key a
valid compressed secp256k1 key. scriptSigs: cooperative `<serverSig> <sig_1>…<sig_s> <s> <pk_1>…<pk_p> <p> OP_1`;
refund `<sig_1>…<sig_s> <s> <pk_1>…<pk_p> <p> OP_0`. One `OP_CHECKPQSIG` executes on either path (R-B1); the 9,000-byte
PQ scriptSig allowance covers it (SLH coop ≈ 8,013 B). `Solver` returns `TX_PQCHANNEL` with solutions
{client CPQKeyID, server pubkey, refundHeight}; `ScriptSigArgsExpected` −1 with an exact-count check in
`AreInputsStandard` (cooperative s+p+4 incl. the server signature and selector; refund s+p+3). Policy refuses a scheme-2 client before Falcon (as A-1).
**`TOK-PQ`** (after `pqFalconHeight`): an assigned YED token output must be `TX_PQPKH` scheme 2 **or `TX_PQCHANNEL` with a
scheme-2 client**. Before Falcon, channels may use an SLH client (no token-shape rule applies). Given up: a pure PQ
2-of-2. Security (corrected after review A of Q4): the client's funds and the refund path need the client's PQ key, so an
outside attacker who breaks the server's EC key gains nothing without a client signature. But a **quantum-capable
client** can forge the server's ECDSA signature on the cooperative path and close with a fresh state paying itself
everything, clawing back its in-channel payments: the **server's in-channel balance is only secp256k1-secure**, as with
x402's P2SH channels today. Mitigation is operational: servers settle or close channels promptly. TOK-PQ's invariant (no
EC key alone moves the YED) holds.

**Q4 (YED module) as implemented (2026-10-10):** **TOK-PQ binds only token outputs that actually
receive YED** (ruling after both Q4 reviews, superseding the first implementation that checked every payload assignment
before XFER-1..3): a TRANSFER/REDEEM payload with no YED input, or one that XFER-1..3 burns (over-assignment), is
unaffected by TOK-PQ (non-Yellowback / burn as before); a successful assignment of YED to a non-holder output after the
Falcon height makes the transaction **invalid** (fund safety). Smallest footprint: TOK-PQ never reads non-YED data. A
port must evaluate it after XFER-1..3 on the assignments that succeed. a TRANSFER/REDEEM payload whose token output fails `TOK-PQ` makes the
transaction **invalid** rather than burning the YED (fund safety; a deliberate departure from burn semantics). After
Falcon a holder must be scheme 2 (an SLH-DSA PQPKH is not a valid holder). `yed_getinfo.attest.payloadVersion` stays 3
(non-MINT types) and `mintPayloadVersion` is 4. A channel output's YED is listed under the client's address and is not a
wallet-spendable coin. `pqFalconHeight` is not in the hashed Params record (no schema change; differing Falcon heights
diverge in consensus anyway). Golden state hash `17926ca6…24a1` (C++ = Python model).

**Q5 (node wallet) as implemented, normative for ycash6 (2026-10-10):** A-12 derivation = HKDF-SHA256 (RFC 5869),
IKM = the line's raw wallet seed (dd: `HDSeed::RawSeed()`, 32 B; 6: the `MnemonicSeed` raw seed), **salt empty**,
info = `"Ycash PQ key"` (12 ASCII bytes) ‖ scheme u8 ‖ index u32 big-endian, L = 48 for both schemes. Vectors in
ycash-dd `src/test/pq_wallet_tests.cpp` (HD seed 0x00..0x1f). No index lookahead. `-pqfeerate` defaults to
`-minrelaytxfee`. `vault_lock` accepts external owners; V/I outputs are never `ISMINE_SPENDABLE`.

(The original draft header follows.)


Spec agent, 2026-10-10. Read-only survey of `wt/q-dd` (ycash-dd, `upgrade/quantum-vaults` @ `ec9abe852`) and
`wt/q6` (ycash6, `upgrade/quantum-vaults` @ `0f150defb`). Both are `upgrade/vault` today. Normative inputs:
quantum plan rev 2 §2 and §4, upgrade plan §15.3, §15.6 and §15.10, in-term plan §4, `wt/BRIEFING-quantum.md`.
Citations are `file:line`: **dd** is `wt/q-dd`, **6** is `wt/q6`. "dd=6" means the file is byte-identical on both
lines, so the line numbers are the same.

Scratch tools, run with `.venv/bin/python`:
- `wt/scratch/q-spec/pq_addr_prefix.py`: the Base58Check version search and its proof (§4).
- `wt/scratch/q-spec/pq_template_sizes.py`: V/I/PQPKH and scriptSig byte lengths (§1, §2).

**Decisions this draft forces (details in §7):**
- **F-1.** `schemeId` is pushed as **`OP_1`/`OP_2` (0x51/0x52)**, not as `01 01`. With that push, `TX_PQPKH` is
  **35 bytes**, not 36.
- **F-2.** Payload version byte → **0x04 for every type**.
- **F-3.** The owner's residual intent commits `SHA256(PQPKH(owner))`.
- **F-4.** PQ address versions `ye` **0x56BF**, `yt` **0x571E**, `yr` **0x5710**, giving **53**-character
  addresses.
- **F-5.** Sigop counting reprices history, and verification is not bounded by it.
- **F-6.** The scriptSig limit splits across `IsStandardTx`/`AreInputsStandard`.
- **F-7.** There is no holder-shape rule today.

---

## 0. Constants (additions; both lines identical)

| Name | Value | Where |
|---|---|---|
| `OP_CHECKPQSIG` | `0xc2` | `src/script/script.h` after `OP_CHECKSETDORMANT = 0xc1` (dd `script.h:179`, 6 `script.h:180`); `GetOpName` case in `script.cpp` |
| `SCRIPT_VERIFY_PQ_FALCON` | `(1U << 12)` (next free; `SCRIPT_VERIFY_VAULT = 1U<<11` at dd `interpreter.h:100`, 6 `:103`) | `src/script/interpreter.h` |
| `SCRIPT_ERR_PQ_SCHEME`, `SCRIPT_ERR_PQ_CHUNK`, `SCRIPT_ERR_PQ_SIZE` | appended after `SCRIPT_ERR_SETSIG_COUNT` (dd `script_error.h:58`), before `SCRIPT_ERR_ERROR_COUNT`; strings in `script_error.cpp` | both |
| `pq::SCHEME_SLH_DSA_SHA2_128S` / `pq::SCHEME_FN_DSA_512` | `0x01` / `0x02` | `src/crypto/pq/scheme.h` (briefing contract) |
| `pq::PubKeySize` | 32 / 897 | |
| `pq::SigSize` (no hashtype) | 7,856 / 666; **on the stack +1 hashtype byte = 7,857 / 667** | |
| chunking (sig incl. hashtype) | SLH: s=16 = 15×520 + **57**; p=1 = **32**. Falcon: s=2 = 520 + **147**; p=2 = 520 + **377** | |
| `MAX_STANDARD_PQ_SCRIPTSIG` | 9,000 | `src/policy/policy.h` |
| `PQ_SIGOP_COST` | 20 | `script.cpp` `GetSigOpCount` (see §5, F-5) |
| `Consensus::Params::pqFalconActive` | `bool`, main/test `false`, regtest from `-pqfalcon=1` | `consensus/params.h` (dd fields near `:349`, 6 near `:314`); regtest setter in `chainparams.h` next to `UpdateNetworkUpgradeParameters` (dd `:153`, 6 `:237`); `init.cpp` beside the `-nuparams` loop (dd `:1272`, 6 `:1404`) |

Push encodings under `SCRIPT_VERIFY_MINIMALDATA`, which is a standard flag (dd `policy.h:38`, 6 `policy.h:50`).
`CheckMinimalPush` is at dd `interpreter.cpp:235-256` and is identical on 6. A 520-byte chunk is
`4d 0802 <520>` (3 bytes of overhead). 377 bytes is `4d 7901`. 147 is `4c 93`. 57 is `39`. 32 is `20`. `s` and `p`
are `OP_n`: `0x60` for 16, `0x52` for 2, `0x51` for 1.

---

## 1. Vault V and Intent I with the PQ owner (the only owner shape)

The parser and builder live in `src/vault/template.{h,cpp}`. **dd=6** (byte-identical), so every line below holds
on both lines. Tokens are matched by `MatchSkeleton` (`template.cpp:121-133`). A field `F` is any push, `OP_0`..`OP_16`
included (`IsPushTok`, `:34-37`). After matching, `MatchVault`/`MatchIntent` decode the fields, check the ranges,
**rebuild and compare bytes** (`:197-230`), and that comparison enforces minimal pushes.

### 1.1 The owner slot

| | Today (upgrade plan §15.3) | PQ (quantum plan §4.3) |
|---|---|---|
| tokens | `<ownerKey:33> OP_CHECKSIG` (2 tokens) | `<ownerHash:32> <schemeId> OP_CHECKPQSIG` (3 tokens) |
| bytes | `21 <33>` `ac` = **35** | `20 <32>` `51`/`52` `c2` = **35** |
| field check | `IsCompressedKeyBytes` (`template.cpp:137-140`): 33 bytes, `02`/`03` | `ownerHash` exactly 32 bytes (`TokU256`). `schemeId` via `TokNum` ∈ {1, 2} (`pq::IsKnownScheme`), else `Shape::MALFORMED` ("not a template", V-1 rejects) |
| builder | `<< valtype(key)` (`:161`, `:167`, `:169`, `:184`, `:192`) | `<< valtype(hash) << (int64_t)scheme << OP_CHECKPQSIG`. The `int64_t` push gives `OP_1`/`OP_2` (F-1) |

The slot is 35 bytes before and after, so **V and I keep their byte lengths**: V **209..220**, I **196..199**
(`pq_template_sizes.py`). The current `vault_vectors.json` lies inside those ranges: V 211..217, I 196/198. A
YED V (delay 576, `ownerHeight = appHeight = ref+1` ≈ 3.1M) is 217 bytes.

### 1.2 V skeleton: token indices (today → PQ)

```
idx today | idx PQ | token
 0..4     | 0..4   | <tag:4> <cancelSetId:32> <delay> OP_2DROP OP_DROP
 5..8     | 5..8   | OP_DUP OP_1 OP_EQUAL OP_IF
 9..12    | 9..12  | OP_DROP <setId:32>@10 OP_1 OP_CHECKSETSIG
13..17    | 13..17 | OP_ELSE OP_DUP OP_2 OP_EQUAL OP_IF
18..21    | 18..21 | OP_DROP <ownerHeight>@19 OP_CHECKLOCKTIMEVERIFY OP_DROP
22..23    | 22..24 | today <ownerKey>@22 OP_CHECKSIG@23  →  PQ <ownerHash>@22 <schemeId>@23 OP_CHECKPQSIG@24
24..28    | 25..29 | OP_ELSE OP_DUP OP_3 OP_EQUAL OP_IF                      (+1)
29..32    | 30..33 | OP_DROP <setId:32> OP_CHECKSETDORMANT OP_VERIFY          (+1; setId copy @30 → @31)
33..34    | 34..36 | today <ownerKey>@33 OP_CHECKSIG@34  →  PQ <ownerHash>@34 <schemeId>@35 OP_CHECKPQSIG@36
35..39    | 37..41 | OP_ELSE OP_4 OP_EQUALVERIFY <appHeight> OP_CHECKLOCKTIMEVERIFY   (+2; appHeight @38 → @40)
40..42    | 42..44 | OP_ENDIF OP_ENDIF OP_ENDIF                               (+2)
size 43   | size 45
```

**Shift:** +0 up to index 22, **+1 after the first owner slot, +2 after the second**. Plan §4.3 says "+1", which is
true only of the selector-3 prologue (F-8). `MatchVault` (`template.cpp:204-209`) becomes:
`t[22]`→hash, `t[23]`→scheme, `t[31]`→setId2, `t[34]`→hash2, `t[35]`→scheme2, `t[40]`→appHeight. It requires
`setId2 == setId`, `hash2 == hash` and `scheme2 == scheme`. The skeleton table (`:93-106`) gains
`F, F, OP_CHECKPQSIG` in place of `F, OP_CHECKSIG`, twice. `OP_CHECKPQSIG` must be a named opcode there, or a
`VAULT_OP_CHECKPQSIG = (opcodetype)0xc2` beside `template.h:32-35`.

### 1.3 I skeleton (today → PQ)

```
 0..4  | 0..4   | <tag:4> <recipientHash:32> <vaultHash:32> OP_2DROP OP_DROP
 5..8  | 5..8   | OP_DUP OP_1 OP_EQUAL OP_IF
 9..11 | 9..11  | OP_DROP <delay>@10 OP_CHECKSEQUENCEVERIFY
12..16 | 12..16 | OP_ELSE OP_DUP OP_2 OP_EQUAL OP_IF
17..20 | 17..20 | OP_DROP <cancelSetId:32>@18 OP_2 OP_CHECKSETSIG
21..26 | 21..26 | OP_ELSE OP_3 OP_EQUALVERIFY <setId:32>@24 OP_CHECKSETDORMANT OP_VERIFY
27..28 | 27..29 | today <ownerKey>@27 OP_CHECKSIG@28  →  PQ <ownerHash>@27 <schemeId>@28 OP_CHECKPQSIG@29
29..30 | 30..31 | OP_ENDIF OP_ENDIF (+1)
size 31 | size 32
```

`MatchIntent` (`template.cpp:221-223`) becomes `t[27]`→hash and `t[28]`→scheme.

### 1.4 Structs and call sites that carry the owner (dd=6 unless noted)

| Site | Today | PQ |
|---|---|---|
| `VaultParams::ownerKey` (`template.h:59`, `==` at `:65`) | `CPubKey` | `CPQKeyID owner` (scheme + uint256; `==` compares both) |
| `IntentParams::ownerKey` (`template.h:77`) | `CPubKey` | `CPQKeyID owner` |
| `VaultParamsValid` / `IntentParamsValid` (`template.cpp:142-153`) | `IsCompressedKey` | `pq::IsKnownScheme(owner.scheme)` |
| `IntentFor` (`template.cpp:258`) | copies `ownerKey` | copies `owner` |
| S-2 covenant (`vault/state.cpp:499`) | `ip.ownerKey != v.ownerKey` | `ip.owner != v.owner` |
| `TokKey` (`template.cpp:75-81`) | used for owner and bond | stays for Bond B only |
| `template.h:8` `#include "pubkey.h"` | | stays (Bond B) |

### 1.5 scriptSigs (selector = last push, parsed by `ParseSelector`, `template.cpp:295-315`, unchanged)

| Selector | Today | PQ | Bytes (PQ) |
|---|---|---|---|
| V 1 UNLOCK | `<sig_1>…<sig_k> OP_1` | **unchanged** | ≤ 15×66 + 1 |
| V 2 OWNER | `<ownerSig> OP_2` | `<sig_1>…<sig_s> <s> <pk_1>…<pk_p> <p> OP_2` | SLH **7,939**; Falcon 1,578 |
| V 3 OWNER-RELEASED | `<ownerSig> OP_3` | `… <p> OP_3` | same |
| V 4 APP | `OP_4` | **unchanged** (one byte `54`) | 1 |
| I 1 RELEASE / I 2 CANCEL | `OP_1` / `<sigs> OP_2` | **unchanged** | |
| I 3 OWNER-RELEASED | `<ownerSig> OP_3` | `… <p> OP_3` | as V 3 |

Selectors 1 and 4, and I 1 and I 2, are byte-identical because neither the opcode/push sequence of their branches
nor their scriptSigs touch the owner slot. Their **sighash** is unchanged too: the scriptCode is the whole V/I
script, `OP_CODESEPARATOR` is disabled (dd `interpreter.cpp:315`), and the V/I bytes before and after the owner slot
are equal. **The V bytes themselves do change** (the owner slot), so `vaultHash = SHA256(V)` differs from
today's for the same parameters. That is expected, and every vector regenerates.

`ParseSelector` returns every push before the selector in `ts.sigs` (`:302-313`). OP_n pushes come back as one byte
(`:305-306`), so `s` and `p` arrive as `{0x10}` and `{0x01}`. Nothing in the module reads `ts.sigs` for owner
selectors (grep `ts.sigs`/`->sigs`: set-signature paths only). No change.

Stack at `OP_CHECKPQSIG` for V selector 2: the scriptSig leaves `sig_1..sig_s s pk_1..pk_p p 2`. Then V runs
`… OP_DUP OP_2 OP_EQUAL OP_IF OP_DROP <ownerHeight> CLTV OP_DROP <ownerHash> <scheme>` → top is `scheme, hash, p,
pk_p..pk_1, s, sig_s..sig_1`, as quantum plan §4.2 requires. `OP_CHECKPQSIG` leaves one element, which satisfies
`CLEANSTACK` (a standard flag, dd `policy.h:41`).

### 1.6 Bond B and other owner-key templates

| Template | Owner key? | Change |
|---|---|---|
| Bond B `BuildBondRedeem`/`ParseBondRedeem` (`template.cpp:262-293`) | `memberKey:33`, an attestor's key | **none** (D-Q-5) |
| v2 P2SH `VaultScript`/`ParseVaultScript` (`yellowback/script.h:52-55`, dd=6) | `ownerPubKey` | **none**: refused for new mints since U-23 (MINT-3 compares the V). No v2 vault exists on the upgrade line (the index starts at activation, U-22). Dead for PQ; left as is (rule 7) |
| `OwnerScriptSig` (`yellowback/script.h:58`) | v2 only | none |
| set acts (`vault/act.cpp`) | member/admin keys | none (D-Q-5) |
| `ATTESTOR_REGISTER` payload | attestor + bond keys | none (plan §4.4) |
| YED token output vout[1] of a MINT (`txbuilder.cpp:51` dd) | P2PKH(**owner** EC key): the owner key doubles as the first holder key | must change: see §3.6 |

---

## 2. `TX_PQPKH`

### 2.1 Bytes (F-1)

```
20 <keyHash:32> 51|52 c2        35 bytes     (<32-byte push> OP_1|OP_2 OP_CHECKPQSIG)
```
scriptSig: `<sig_1>…<sig_s> <s> <pk_1>…<pk_p> <p>`, push-only. SLH **7,938** B, Falcon **1,577** B. A Falcon spend
fits under today's 1,650-byte limit. Only SLH needs `MAX_STANDARD_PQ_SCRIPTSIG`.

`Solver` match (exact): `size == 35 && s[0] == 0x20 && (s[33] == OP_1 || s[33] == OP_2) && s[34] == OP_CHECKPQSIG`.
`vSolutions = { {scheme}, hash32 }`. Any other scheme byte is `TX_NONSTANDARD` (and fails in the interpreter
anyway).

### 2.2 Integration points

The tables cover both lines. **Line numbers marked † come from the CTxDestination survey agent** (§2.4).

| What | dd | 6 | Change |
|---|---|---|---|
| `enum txnouttype` | `script/standard.h:56-69` | `standard.h:49-61` | add `TX_PQPKH` after `TX_VAULT_INTENT` |
| `CTxDestination` variant | `standard.h:85` | `standard.h:77` | `std::variant<CNoDestination, CKeyID, CScriptID, CPQKeyID>`; `CPQKeyID { uint8_t scheme; uint256 hash; }` with `==`/`<` (scheme then hash) |
| `GetTxnOutputType` | `standard.cpp:25-39` | `standard.cpp:~26-40` | `"pqpubkeyhash"` |
| `Solver` | `standard.cpp:87-151`, insert before the vault block `:134` | `:88-152` | the match in §2.1 |
| `ScriptSigArgsExpected` | `standard.cpp:153-174` | `:154-175` | `TX_PQPKH`: `-1` (variable), like `TX_VAULT`; `AreInputsStandard` special-cases it (§2.3) |
| `ExtractDestination` | `standard.cpp:176-204` | `:177-205` | `TX_PQPKH` → `CPQKeyID{vSolutions[0][0], uint256(vSolutions[1])}` |
| `CScriptVisitor` / `GetScriptForDestination` | `standard.cpp:248-280` | `:249-281` | `operator()(const CPQKeyID&)` → `<< ToByteVector(hash) << CScript::EncodeOP_N(scheme) << OP_CHECKPQSIG` |
| `IsKeyDestination` etc. | `standard.cpp:298-308` | `:299-309` | add `IsPQKeyDestination` |
| `DestFromAddressHash` (insightexplorer, `uint160`) | `standard.cpp:311-324` | `:312-…` | no PQ case (the address index keys on uint160): PQ outputs are not address-indexed (record it) |
| sigops `GetSigOpCount` | `script/script.cpp:156-176` | `script.cpp:158-178` | `OP_CHECKPQSIG` → `n += 20` (F-5) |
| IsMine / Sign / keystore / key_io | see §2.4 | | |

### 2.3 Policy: the scriptSig limit (quantum plan §4.5), F-6

| Site | dd | 6 | Today | PQ |
|---|---|---|---|---|
| `IsStandardTx` scriptSig size | `policy/policy.cpp:94` (`> 1650`) | `policy.cpp:125` | every input ≤ 1,650; no prevout access (signature dd `:60`, 6 `:84`) | `> (vaultActive ? MAX_STANDARD_PQ_SCRIPTSIG : 1650)`. `vaultActive` is computed at dd `:106` / 6 `:137`, so hoist it above the vin loop |
| `AreInputsStandard` | `policy.cpp:145-213`; vault skip at `:161` | `:176-…`; skip at `:192` | V/I inputs `continue` | sees the prevout: `TX_PQPKH`, `TX_VAULT`, `TX_VAULT_INTENT` → scriptSig ≤ `MAX_STANDARD_PQ_SCRIPTSIG`, `continue`; **every other type → re-check `scriptSig.size() ≤ 1650`** (the limit IsStandardTx now relaxes) |
| outputs standard only when active | `policy.cpp:120` | `:151` | `TX_VAULT/_INTENT && !vaultActive` → `scriptpubkey` | add `TX_PQPKH` to that test |
| Falcon output policy (recommended, §7 A-6) | same loop | same | — | `TX_PQPKH`/V/I with scheme 2 and `!pqFalconActive` → `scriptpubkey` |
| callers | `main.cpp:1652` (IsStandardTx), `:1756` (AreInputsStandard) | `main.cpp:1907`, `:2002` | | unchanged |

P2SH-wrapped PQPKH (redeem `20 <h> 51 c2`) is valid by consensus once active, but it stays **non-standard**: its
redeem `Solver`s to `TX_PQPKH`, args are `-1` → reject. Record it. Nothing needs it.

### 2.4 IsMine / signing / keystore / key_io / CTxDestination visitors

This section comes from a read-only survey agent, not re-verified line by line. Treat its lines as ±2.

Failure modes:
- **C**: an exhaustive visitor. It stops compiling once `CPQKeyID` is in the variant, which is good: the compiler
  lists the sites.
- **S**: a silent mishandling.
- **T**: an unchecked `std::get<CKeyID>`, which throws.

**Core (both lines; standard.cpp/ismine/sign switches are the same code with shifted lines)**

| Site | dd | 6 | Mode | Change |
|---|---|---|---|---|
| `CScriptID` definition (put `CPQKeyID` beside it) | `script/standard.h:23` | **`script/script.h:655`** (moved) | — | the location differs by line |
| `GetTxnOutputType` | `standard.cpp:25-38` | `:26-39` | S (returns NULL) | add a case |
| `IsMineInner` switch | `script/ismine.cpp:55-104` | `:56-105` | S (`ISMINE_NO`) | `TX_PQPKH` → `HavePQKey(CPQKeyID)` → `ISMINE_SPENDABLE` |
| watch-only dummy sign | `ismine.cpp:111` | `:112` | S | dummy PQ creator (sizes from the registry) |
| `SignStep` | `script/sign.cpp:70-121` | `:71-122` | S (`default: false`) | `TX_PQPKH`: push the sig chunks, `s`, the pk chunks, `p` |
| `CombineSignatures` (static) | `sign.cpp:284-332` | `:287-335` | **S, drops the sigs** | treat like a single-signer type (keep the non-empty side) |
| `ProduceSignature` self-verify flags | `sign.cpp:157` | `:158` | S | `STANDARD` only, so a PQ input fails with `BAD_OPCODE`. Pass `GetVaultScriptFlags(tip+1)` in (signature change) or verify separately (§5.2) |
| signature creator | `TransactionSignatureCreator(ks, tx, nIn, amount, hashType)` `sign.cpp:21` | adds `PrecomputedTransactionData&` (`sign.h:37-53`) | — | the PQ `CreateSig` follows each line's constructor |
| `IsStandard` | `policy/policy.cpp:38-58` | `:62-82` | — | follows Solver |
| bloom filter | `bloom.cpp:139-140` | `:140-141` | S | optional (no SPV for PQ) |

**Visitors over `CTxDestination`**

| Site | dd | 6 | Mode | Change |
|---|---|---|---|---|
| `DestinationEncoder` / `EncodeDestination` | `key_io.cpp:21-44`, `:267` | `:24-47`, `:391` | C | **Recommend: no plain-YEC PQ encoding (D-Q-11 defers `yq1…`).** The operator returns `""`. YED addresses come from `yellowback::EncodeAddress` (§4) |
| `CScriptVisitor` | `standard.cpp:249` | `:250` | C | §2.2 |
| `DescribeAddressVisitor` (validateaddress) | `rpc/misc.cpp:118-160` | `:124-166` | C | `isscript=false`, `pqscheme` |
| `CAffectedKeysVisitor` (key birth) | `wallet/wallet.cpp:6369-6399` | `:7268-7298` | C | no-op for PQ |
| `DecodePaymentAddress` transparent `match{}` | — | `key_io.cpp:516-529` | C | PQ → nullopt |
| `DecodeLegacyPaymentAddress` `match{}` | — | `key_io.cpp:553-566` | C | PQ → nullopt |
| `GetSourceForDestination` | — | `wallet/rpcwallet.cpp:623-633` | C | PQ lambda |
| `CKeyStore::GetUFVKMetadataForAddress` | — | `keystore.cpp:18-26` | C | PQ → nullopt (no UA receiver) |
| `-mineraddress` | `init.cpp:1922-1925`, `miner.cpp:736` | `init.cpp:1537`, `miner.cpp:743-768` (`ExtractMinerAddress` over `PaymentAddress`) | **T on dd** | dd: `get_if` (mining to PQ is not a goal); 6: unchanged unless `PaymentAddress` gains PQ |
| `IsChange` | `wallet.cpp:3326-3346` (address book) | `wallet.cpp:4711-4740` `match{CKeyID, auto→false}` | S on 6 | PQ change is never recognised on 6. The YED wallet does not use PQ change, so leave it and record it |
| insight address index (`uint160`) | `script.cpp:249-273`, `addressindex.h`, `spentindex.h:45`, `main.cpp:2821-3270` | `script.cpp:270-319`, `main.cpp:3143-3891` | S (PQ outputs are not indexed) | **no change** (A-11) |
| signmessage / verifymessage / dumpprivkey | `rpcwallet.cpp:597`, `misc.cpp:442`, `rpcdump.cpp:580` | `:1095`, `:483`, `:561` | S (errors) | none in Q5 |
| ZIP-317 fee | — | `zip317.cpp:24-35` (`P2PKH_STANDARD_INPUT_SIZE=150`); `yellowback/txbuilder.cpp:250` | — | 6 only: a PQ input is about 53 logical actions (7,938/150). Plan §4.5 adds the size term there |
| q6 only: `PaymentAddress` / `RecipientAddress` / `ZTXOPattern` | — | `zcash/Address.hpp:257-262`, `zcash/address/unified.h:55-59`, `wallet.h:1139-1148` | — | **Do not add PQ** (smallest). PQ outputs are built by the YED/vault builders, not by `z_sendmany`/`WalletTxBuilder`. Consequence: on 6, `z_sendmany` cannot pay or spend PQPKH; recorded |

**Keystore / walletdb / derivation (the main difference between the lines)**

| Item | dd | 6 |
|---|---|---|
| `CKeyStore` API | `keystore.h:20-97` | `keystore.h:37-160` (+ UA API `:121-159`) |
| `CBasicKeyStore` maps | `keystore.h:119-133` | `keystore.h:184-206` (+ `mapP2PKHUnified`/`mapP2SHUnified` `:205-206`) |
| add | `PQKeyMap = std::map<CPQKeyID, CPQKey>`; `AddPQKey`, `HavePQKey`, `GetPQKey` (plan §4.6) | same |
| encrypted | `CCryptoKeyStore` `wallet/crypter.h:131-200` (`mapCryptedKeys` `:135`, `EncryptKeys` `:152`) | `crypter.h:132-206` (`:137`, `:154`) → `mapCryptedPQKeys` |
| walletdb `ReadKeyValue` | `walletdb.cpp:495-946` (`key` `:650`, `ckey` `:729`, `hdseed` `:890`, `hdchain` `:923`) | `walletdb.cpp:411-981` (`mnemonicphrase` `:864`, `mnemonichdchain` `:928`, `unifiedfvk` `:755`, …) |
| add records | `pqkey`, `cpqkey`; `IsKeyType` `walletdb.cpp:948-956` | the same; `IsKeyType` `:983-993` |
| HD seed | `HDSeed` (random), `GenerateNewSeed` `wallet.cpp:3425-3446`. **Transparent keys are NOT HD** (`GenerateNewKey` `:267-291`, `MakeNewKey`) | `MnemonicSeed` (BIP39). Transparent keys are **BIP44 HD**: `GenerateNewKey(bool)` `wallet.cpp:342-376` → `transparent::AccountKey::ForAccount` `zcash/address/transparent.cpp:71-99`; legacy account `0x7FFFFFFF` |
| PQ derivation (plan §4.6 `m/44'/347'/account'/0x5100'/index'`) | from `HDSeed.RawSeed()` through the ZIP-32/BIP-32 transparent derivation, which dd does not have for transparent keys. See A-12 | from `MnemonicSeed.RawSeed()` through the same `transparent::AccountKey` machinery, account = the legacy account. See A-12 |
| sighash | C++ `SignatureHash`: ZIP-243, v4 only (R-A3) | ZIP-243, v4 only (R-A3; v5 is invalid under Vault), C++, with `PrecomputedTransactionData` required by the checker and creator |

---

## 3. YED module

### 3.1 MINT payload byte map (`src/yellowback/payload.{h,cpp}`, `params.h:47-53`; dd=6)

Offsets are from the start of the OP_RETURN data push (magic at 0). Header layout: `payload.h:21-25`. MINT body:
`payload.h:27-28`, `MINT_BODY_SIZE` at `payload.cpp:17`, decoded at `payload.cpp:242-250`, encoded at
`payload.cpp:314-322`.

| Offset | Len | v3 (today, version byte 0x03) | v4 (PQ) |
|---|---|---|---|
| 0 | 2 | magic `59 42` | same |
| 2 | 1 | version `03` | **`04`** (F-2) |
| 3 | 1 | type `01` MINT | same |
| 4 | 1 | termClass | same |
| 5 | 4 | cents u32 LE | same |
| 9 | 4 | lockHeight u32 LE | same |
| 13 | 4 | refHeight u32 LE | same |
| 17 | 33 | ownerPubKey (any 33 bytes; MINT-3 judges) | **17: ownerScheme u8; 18..49: ownerHash 32** (the uint256's internal bytes, = the bytes pushed in V) |
| 50 | 1 | feeVout | **same offset** |
| 51 | 1 | attestFeeVout | **same offset** |
| | **52** | total (header 4 + body 48) | **52** |

`feeVout`/`attestFeeVout` do not move, which confirms quantum plan §4.4. The "80-byte" figure in the plan is the cap
(`MAX_PAYLOAD`, `params.h:53`), not the MINT size.

Codec changes:
- `Payload::ownerPubKey` (`payload.h:99`) becomes `CPQKeyID owner` (scheme + hash).
- `ownerKeyBytes` (`:100`) stays as "the 33 payload bytes verbatim" (`scheme ‖ hash`).
- `Payload::Mint(…, const CPubKey& owner, …)` (`payload.h:129`, `payload.cpp:103-113`) takes a `CPQKeyID`.
- The decoder (`payload.cpp:246-249`) sets `owner.scheme = bytes[0]` and `owner.hash = uint256(bytes[1..33])`.
  **Any scheme byte decodes**: the codec fixes the shape and MINT-3 judges, the same pattern as today's comment at
  `:247-248`.
- `PAYLOAD_VERSION` (`params.h:49`) changes to `0x04`. The decoder's version gate (`payload.cpp:376`) then makes v3
  payloads non-Yellowback. The other bodies are unchanged byte for byte.
- `DecodeBodyV3` keeps its name (rule 7) or gains a one-line comment.
- `yed_getinfo.attest.payloadVersion` (`rpc/yellowback.cpp:724`) reports 4.
- Check `yellowback_attest_vectors.json` / BUNDLE messages for a bound version byte before Q4 (see §7 A-2).

### 3.2 Rules that read the owner, and what each compares

dd=6 for `state.cpp`, `script.cpp` and `vault/state.cpp`. The `txbuilder`/RPC line numbers differ on 6 and are
given where known.

| Rule / site | File:line | Today | PQ |
|---|---|---|---|
| **MINT-3 key validity** | `yellowback/state.cpp:338` | `ownerPubKey.IsValid && IsCompressed && IsFullyValid` → `bad-mint-owner-key` | `pq::IsKnownScheme(owner.scheme) && (owner.scheme != 0x02 \|\| P.pqFalconActive)`. Read the consensus param through `ctx` (`EvalContext` has `params`, the yellowback params; the Falcon flag must be reachable there, see A-5) |
| **MINT-3 vault script** | `state.cpp:342-343` | `vout[0].spk == YedVaultScript(P, ownerPubKey, ref)` | `YedVaultScript(P, owner, ref)` with `CPQKeyID`; byte compare unchanged |
| MINT-3 record | `SetVault` `state.cpp:297` | `v.ownerPubKey = p.ownerKeyBytes` | unchanged bytes (33 = scheme‖hash), see §3.4 |
| **RED-1/RED-4 claim (S-2 recognition)** | `state.cpp:550` | `vaultSpk = YedVaultScriptAt(P, vault.OwnerKey(), …)` | `vault.Owner()` (`CPQKeyID`) |
| **RED-5 residual (IT-3)** | `state.cpp:625-634` | `owner.IsValid()`; `ownerHash = SHA256(P2PKHOf(owner.GetID()))` | `ownerHash = SHA256(GetScriptForDestination(vault.Owner()))`, i.e. SHA256 of the **35-byte PQPKH** (F-3); the `IsValid` test becomes `IsKnownScheme` |
| **I-2 cancel relock** | `state.cpp:759` | `YedVaultScriptAt(P, vault->OwnerKey(), …)` | `vault->Owner()` |
| IT-1 heights | `script.cpp:94-108` | `YedVaultScriptAt(p, CPubKey owner, oh, ah)` | `const CPQKeyID& owner`; body sets `v.owner` (`:90`) |
| primitive S-2 | `vault/state.cpp:499` | `ownerKey` equality | `owner` equality |
| MINT-8 / RED-3 / AFEE-1 fee payees | `state.cpp:283, 387, 438, 578, 691` (`P2PKHKey`) | P2PKH of a pool payee / bond key | **unchanged** (§3.5) |
| IT-2, IT-4..IT-6, IT-9 | `state.cpp:567-612` | no owner read | unchanged |

`YedVaultScriptAt` / `YedVaultParams*` signatures (`script.h:104-111`): `const CPubKey& owner` → `const CPQKeyID& owner`.
Python follows: `yed_vault_script` / `yed_intent_script(params, owner_pubkey, …)` in
`qa/rpc-tests/test_framework/` (used e.g. `test_yellowback_model.py:172, 227`), and `vault.py` /
`gen_vault_vectors.py:100-163` (`owner_key=`) on both lines.

### 3.3 The residual intent (F-3)

The question was: is the owner's residual a holder script, or the owner key hash? **It is both, read the smallest
way: `holderScript(owner) := GetScriptForDestination(CPQKeyID owner)` = `20 <ownerHash> OP_scheme OP_CHECKPQSIG`**,
the 35-byte `TX_PQPKH` of the owner's own key. `recipientHash = SHA256(those 35 bytes)`.
- The vault record holds nothing else. The record has `scheme ‖ hash` only, with no EC key and no second address,
  so the payee is derived from the record exactly as `P2PKHOf(owner.GetID())` is today.
- The I-1 release pays exactly that script. The owner spends the residual with the same SLH-DSA key, an 8 KB spend,
  once.
- The holder policy (D-Q-2, PQ-only after Falcon) concerns **token** outputs. The residual carries YEC, not YED,
  so it is not a holder output. The question of a Falcon-holder destination does not arise.
- Wallet sites: `txbuilder.cpp` dd `:113` (`ownerIntent`) and `:183` (`RESIDUAL` output) use
  `GetScriptForDestination(s.ownerPubKey.GetID())`; 6 `:114`, `:184`. These become
  `GetScriptForDestination(s.owner)`.
- In-term model: `yed_intent_script(..., ym.p2pkh_script(OWNER_KEYHASH))` (`test_yellowback_model.py:227`) becomes
  `pqpkh_script(owner)`.

### 3.4 Vault record (index DB)

`VaultRecord::ownerPubKey` (`yellowback/view.h:216`, serialized first at `:245`) is a `std::vector` holding "the
33 payload bytes verbatim". **The serialization is unchanged**: it holds `scheme ‖ hash`, 33 bytes.
- Rename the accessor `OwnerKey()` (`:240`) to `Owner()` → `CPQKeyID`, invalid (scheme 0) when the size is not 33.
- Keeping the field name `ownerPubKey` is the smallest diff. It is misleading, so add a one-line comment instead of
  renaming. Renaming touches the DB code and the RPC (rule 7 spirit).
- No index-format version bump is needed, because no v3 record exists on a PQ chain: the index starts at
  activation.

### 3.5 Holder recognition (`P2PKHKey`) — F-7

`P2PKHKey` (`state.cpp:77-83`) is used **only for fee payees**: the pool payee (MINT-8 `:387`, RED-3 `:578`, logs
`:438`, `:691`) and the attestor-fee payee (`AttestFeeOk` `:283`, compared with `BondKey()`, an attestor key).
**No rule today checks a token output's shape.** `TokenRecord.scriptPubKey` stores any script (`:446`,
`:654-660`). Smallest reading of plan §4.4 "HolderKey":
- **Fee payees stay `P2PKHKey`.** They are pool and attestor keys, unchanged under D-Q-5, and the eligible set is
  `CKeyID` from coinbase tags.
- **Tokens:** while `pqFalconActive` is false there is no shape rule, as today. That satisfies "accepts P2PKH or
  TX_PQPKH".
- Once `pqFalconActive`, a **new** rule applies, proposed as `TOK-PQ`: every assigned token output of a MINT
  (vout[1]), a TRANSFER and a REDEEM (`p.assignments`) must be `TX_PQPKH` with scheme 0x02, else
  `bad-yed-holder`. This is new consensus surface: flag it for the review gate.
- `HolderKey(script) → CTxDestination` is then needed only by the wallet/index (`yed_listtokens`, balances), not by
  rules.

### 3.6 MINT construction (wallet)

`yed_mint` has **no `ownerkey` argument today**. Its signature is
`yed_mint cents lockBlocks ( "from" "bundleHex" wait maxCollateralZat )` (`rpc/yellowbackwallet.cpp:778` dd). The
owner is a fresh keypool key (`txbuilder.cpp:1270` dd, `ctx.FreshKey("yellowback-vault")`), and **the same key**
receives the token (vout[1] = P2PKH(owner), `txbuilder.cpp:51`). PQ:
- owner = a fresh SLH-DSA wallet key (`CPQKeyID`).
- vout[1] (token) = a fresh holder key, P2PKH while Falcon is inactive and Falcon PQPKH once active. Today's
  owner-is-holder coupling cannot hold: an SLH-DSA PQPKH token would cost an 8 KB scriptSig per transfer.
- `ctx.Payee(R, owner bytes)` (`:1278`) seeds payee selection with the 33 owner bytes. It passes the 33
  `scheme ‖ hash` bytes; this is a wallet-only choice, not consensus.
- Owner signing (`SignVaultSpend`, dd `txbuilder.cpp:197-203`, 6 `:216-222`) uses
  `keystore.GetKey(ownerPubKey.GetID())` + `CKey::Sign` + `<< sig << OP_2`. It becomes `GetPQKey(owner)` +
  `pq::Sign` + the chunked pushes + `OP_2`. The same applies to `vault_ownerspend` (`rpc/vault.cpp` dd
  `:1590-1617`, 6 `:1609-1635`, `OP_2`/`OP_3`).
- `VAULT_RPC_FEE = 10000` (`rpc/vault.cpp:51` dd) covers an 8 KB spend at the 100 zat/KB floor (≈ 800). Leave it.

---

## 4. Address encoding (F-4)

Today: `yellowback::Params::addressVersion` (`yellowback/params.h:119`). Mainnet is `{0x1F,0xE4}` (`params.cpp:138`),
testnet `{0x20,0x07}` (`:154`), regtest `{0x20,0x02}` (`:187`). The codec is `yellowback/address.{h,cpp}`
(dd=6): `EncodeAddress(CKeyID)` `:11-16`, and `DecodeAddress` `:18-27`, which requires exactly `ver.size() + 20`
bytes. These addresses are 35 characters.

Search (`wt/scratch/q-spec/pq_addr_prefix.py`): all 2-byte versions `v` for which the whole interval
`[v·2^296, (v+1)·2^296)` (33-byte payload + 4-byte checksum, so every payload and every checksum) encodes with the
target prefix and one length. The self-check re-derives today's 20-byte versions: `0x1FE4`, `0x2007` and `0x2002`
are each the lowest of their two hits.

| Net | Hits (all length 53) | **Chosen** (the lowest, same rule as `0x1FE4`) |
|---|---|---|
| main `ye` | 0x56BF..0x56C4 | **`{0x56, 0xBF}`** |
| test `yt` | 0x571E..0x5723 | **`{0x57, 0x1E}`** |
| regtest `yr` | 0x5710..0x5715 | **`{0x57, 0x10}`** |

Proof by sampling: 20,006 payloads per network all start with the target and are 53 characters long. The samples
are the all-zero and all-0xFF payloads, scheme 1 and 2 with zero and 0xFF hashes, 10,000 random `scheme∈{1,2} ‖
hash`, and 10,000 fully random 33-byte payloads.
- Mainnet: min `ye3SZot1kepFFNT7S9eGf61sufuSARvXG4VZQ4WqPqJKrosTayohv`, max
  `yeC2CP3NepyAPLy8ChifYtByPvLdpGLnzDwBXcyBVKn5a6CXWeucQ`.
- Testnet: min `yt6XU8DF…Apcp6`, max `ytF76hNc…fnPb`.
- Regtest: min `yr2Qe7xC…cND`, max `yrAzGh7Z…gKKG`.

**Length is 53, not "~52".** The plan's estimate is one short.

Integration:
- `Params` gains `pqAddressVersion`, set beside `addressVersion` at `params.cpp:138/154/187`.
- `EncodeAddress(const CPQKeyID&, const Params&)` returns `Base58Check(pqVer ‖ scheme ‖ hash)`.
- `DecodeAddress(str, params, CTxDestination&)` accepts **either** length (22 → `CKeyID`, 35 → `CPQKeyID`) by
  version. A decoded scheme outside {1, 2} is invalid.
- Both forms start `ye`, so the length disambiguates. The 20-byte decoder already refuses 35-byte data
  (`address.cpp:23`).
- Callers to widen: `rpc/yellowback.cpp` dd `:236, :1189, :1229, :1281`; `rpc/yellowbackwallet.cpp` dd
  `:150-160, :206, :688, :700` (6 offsets: see §6).

lightwalletd guard (`lightwalletd-dd`, read on `upgrade/vault` @ `f0746e4`):
- `frontend/yellowback.go:37` sets `maxAddressLen = 64`, enforced at `:430-431` (`GetAddressTokens`). A 53-character
  address passes.
- **However:** `frontend/yellowback_vault.go:21` `pubkeyPattern = ^0[23][0-9a-fA-F]{64}$` guards
  `ListVaultOutputs.owner` (`:90-94`), and a PQ owner filter fails it. In Q7 it becomes `^0[12][0-9a-fA-F]{64}$`
  (scheme ‖ hash, 66 hex digits: the same length).
- The t-address regex at `frontend/service.go:67` is untouched.
- `common/yellowback.go:40` `KnownRPCVersion = 6` is an exact match (`:184-185`) → 7.

---

## 5. Sigops and script-flag plumbing

### 5.1 Counting sites

`CScript::GetSigOpCount(bool)` (dd `script/script.cpp:156-176`, 6 `:158-178`) is the one place to add
`OP_CHECKPQSIG → n += PQ_SIGOP_COST`. Every site below inherits it.

| Site | dd | 6 |
|---|---|---|
| `GetLegacySigOpCount` (scriptSig + **scriptPubKey of outputs**) | `main.cpp:871-883` | `main.cpp:927-939` |
| `GetP2SHSigOpCount` (P2SH inputs only) | `main.cpp:885-897` | `main.cpp:941-953` |
| mempool `MAX_STANDARD_TX_SIGOPS` (= 4,000, `policy.h:27` / 6 `:39`) | `main.cpp:1764-1769` | `main.cpp:2013-2021`; entry carries `nSigOps` `:2048` |
| ConnectBlock `MAX_BLOCK_SIGOPS` | `main.cpp:3170-3173`, `:3234-3237` | `main.cpp:3701-3702`, `:3796-3801` |
| CheckBlock (context-free, **every historical block**) | `main.cpp:4575-4582` | `main.cpp:5955-5960` |
| miner | `miner.cpp:531-532`, `:565-566`, `:700` | `miner.cpp:485`, `:530-542`, `:617-620` (from `CTxMemPoolEntry::GetSigOpCount`, `txmempool.h:103`) |
| 6 only: `zcash_script` FFI copy | — | `script/zcash_script.cpp:23-36`, `:252`, `:273` (calls `CScript::GetSigOpCount`, so inherits it) |
| `MAX_BLOCK_SIGOPS = 20000` | `consensus/consensus.h:26` | `consensus.h:31` |
| `getblocktemplate` `sigoplimit` | `rpc/mining.cpp:787` | `:842` |

**F-5, the consequences of "count wherever OP_CHECKSIG counts":**
1. **Cost moves to creation.** Legacy counting charges a bare script's sigops when the *output is created*. Spends
   of bare outputs cost nothing, because `GetP2SHSigOpCount` covers P2SH only. Effects:
   - creating a `TX_PQPKH` output costs 20;
   - creating a V or I costs 40 (two `OP_CHECKPQSIG`), up from 2;
   - a block can create at most 1,000 PQ outputs;
   - PQ *verification* per block is bounded only by size (2 MB / 1,577 B ≈ 1,268 Falcon spends, or / 7,938 B ≈
     252 SLH spends).

   The plan's aim "toward MAX_BLOCK_SIGOPS" therefore throttles creation, not verification. Say so in plan §6.
2. **Historical repricing.** CheckBlock counts legacy sigops for every block on reindex. Any pre-activation script
   that contains a raw `0xc2` *opcode* gains 20 per occurrence. Push data is not counted; garbage output scripts or
   coinbase scriptSigs are. The upgrade plan §15.2 declined to count `OP_CHECKSETSIG` for exactly this reason.
   Smallest safe reading: count 20 as written, **and** make Q6 run a mainnet history scan (Ycash, which includes
   the Zcash history before the fork) proving that no block crosses 20,000 with the new count. If any block does,
   count 0, as `OP_CHECKSETSIG` does. This needs owner and reviewer sign-off at Q2.

### 5.2 Where the vault flags are assembled (the `SCRIPT_VERIFY_PQ_FALCON` choke point)

There is one function on each line: `GetVaultScriptFlags(nHeight, params)`, dd `main.cpp:781-786` and 6
`main.cpp:837-842`. It returns `SCRIPT_VERIFY_CHECKSEQUENCEVERIFY | SCRIPT_VERIFY_VAULT` when `UPGRADE_VAULT` is
active, else 0. **Add `| (params.pqFalconActive ? SCRIPT_VERIFY_PQ_FALCON : 0)` inside the active branch.** Every
caller then inherits it:

| Caller | dd | 6 |
|---|---|---|
| mempool accept (tip+1), standard + mandatory | `main.cpp:1856`, used `:1862`, `:1878` | `main.cpp:2122`, `:2128`, `:2144` |
| ConnectBlock flags | `main.cpp:3102` | `main.cpp:3575` |
| snapshot required when VAULT set | `main.cpp:2483`, `:2602` | `:2792`, `:2929` |
| miner re-check | `miner.cpp:575` | — (6's miner trusts the mempool) |
| `signrawtransaction` verify | `rpc/rawtransaction.cpp:1075-1079` | `:1241-1245` |
| vault node mempool re-check | `vault/node.cpp:170` | same |
| yellowback policy | `yellowback/policy.cpp:123-124` | same |
| unit tests asserting the flag value | `test/vault_script_tests.cpp:147, 168-169, 529` | `:154, 175-176, 540` |

The tests compare against `VAULT_FLAGS`. Regtest without `-pqfalcon` keeps the value; with it the test adds a case.

Not covered by `GetVaultScriptFlags`, so they never see PQ flags: `script/sign.cpp` `ProduceSignature` verifies with
`STANDARD_SCRIPT_VERIFY_FLAGS` only (dd `sign.cpp:157`, 6 `:158`), and so does `bitcoin-tx.cpp` (dd `:498`, 6
`:488`). The wallet's PQ signer must self-verify with `STANDARD | GetVaultScriptFlags(tip+1)`, or a PQ input fails
its own check with `BAD_OPCODE`. Today's vault signing is done by hand (`txbuilder.cpp`, `rpc/vault.cpp`) and
bypasses `ProduceSignature`, so it is not affected. A `TX_PQPKH` input signed through `SignSignature` **is**
affected (§2.4).

### 5.3 Checker hook (for Q2)

`BaseSignatureChecker` (dd `interpreter.h:128-180`; 6 has the same set-signature trio) gains:
```cpp
virtual bool CheckPQSig(uint8_t scheme, const std::vector<unsigned char>& sigWithHashtype,
                        const std::vector<unsigned char>& pk, const CScript& scriptCode,
                        uint32_t consensusBranchId) const { return false; }
```
`TransactionSignatureChecker` implements it: `SignatureHash(scriptCode, *txTo, nIn, sig.back(), amount, branchId,
txdata)` → `pq::Verify`. On 6 the constructor requires `PrecomputedTransactionData` (`bitcoin-tx.cpp:488`, 6
`interpreter.h` checker ctor). The result is cached in the signature cache (q/pqcache, 2026-10-11: key binds scheme, sighash, pk and sig under an independent nonce; successes only): `CachingTransactionSignatureChecker`
overrides only `VerifySignature(…CPubKey…)` (dd `sigcache.h:27`).

---

## 6. RPC contract delta, `rpcversion` 7

From a read-only survey agent plus spot checks. Lines are dd; 6 is the same unless given.

### 6.1 Where the version lives

| Item | Location |
|---|---|
| constant | `YELLOWBACK_RPC_VERSION = 6`, `rpc/yellowback.cpp:60` (both lines) → **7** |
| emitted | `yed_getinfo` `rpc/yellowback.cpp:613`; `params` object built at `:672-756` (`inTermClaims` `:714`, `attest.payloadVersion` `:724`) |
| `vault_getinfo` | `rpc/vault.cpp:320` (6 `:334`): no rpcversion; the vault contract is versioned by `branchid` only |
| doc | `doc/yellowback-rpc.md:1` title "rpcversion 6", rule at `:18`; `doc/yellowback-rpc-contract.json:435`, `:832` |
| tests asserting 6 | `qa/rpc-tests/yellowback_rpc_contract.py:189,192`, `yellowback_attest.py:348`, `yellowback_upgrade.py:171`, `yellowback_attest_agent.py:291`, `yellowback_index.py` (dd `:97`, 6 `:106`), 6 `yellowback_demo_v6.py:427`; 6 `qa/yellowback-release-smoke.sh:67` still says **5** (stale, pre-existing) |
| lightwalletd | `common/yellowback.go:40` `KnownRPCVersion = 6`, exact match |

### 6.2 Argument and field delta

Naming rule: the primitive's RPCs use lower-case keys (`ownerkey`) and YED's use camelCase (`ownerPubKey`). Keep
each family's style.

A new JSON type `pqkeyid` is 66 hex digits, `scheme ‖ hash`, scheme ∈ {01, 02}. It is the same length as today's
`key` type, so it is **renamed, never reused**: a 66-hex value beginning `02` would otherwise be read silently as
a Falcon key id.

| RPC | Today | rpcversion 7 |
|---|---|---|
| `vault_lock {…}` (`vault.cpp:1167`, 6 `:1185`; parse `:1192`/`:1210` via `WalletKeyParam`/`ParseKey` `:102`) | param key `"ownerkey"?: key` (default: a new wallet key); result `"ownerkey"` `:1207` | param **`"owner"?: pqkeyid`**, which must be a wallet PQ key (default: a new SLH-DSA wallet key). The old key `"ownerkey"` is **refused** with `ownerkey-removed: use owner (pqkeyid)`. Result **`"owner"`** (pqkeyid) |
| `vault_list {filter}` (`vault.cpp:416`; filter `:435`) | filter `"owner"?: key` | filter `"owner"?: pqkeyid` (same name, new type) |
| `VaultParamsJSON` / `IntentParamsJSON` (`vault.cpp:162-184`, 6 `:176-198`), used by `vault_list`, `vault_decodescript` | `"ownerkey"` | **`"owner"`** (pqkeyid) + **`"ownerscheme"`** (int) |
| `vault_ownerspend "outpoint" "address"` (`vault.cpp:1562`) | signs with the EC owner (`:1591-1617`) | arguments unchanged; signs with the wallet's PQ key (scheme-dispatched) |
| `yed_mint` (`yellowbackwallet.cpp:774`) | no owner argument (A-3) | **unchanged arguments**; the owner is a fresh SLH-DSA key. Result adds **`ownerAddress`** (the PQ `ye…`) |
| `yed_getnewaddress` (`:678`) | P2PKH `ye…` (35 characters) | the holder address per D-Q-2: P2PKH `ye…` while `!falconActive`, Falcon `ye…` (53) once active. **Optional arg 1 `"type"`** `"p2pkh"`, `"pq"` or `"pqowner"`. The plan says "returns a PQ address"; smallest reading = follow the holder policy, A-13 |
| `yed_getvault` / `yed_listvaults` (`VaultToJSON`, `yellowback.cpp:225-257`) | `ownerPubKey` `:233`, `ownerKeyId` `:235`, `ownerAddress` `:236` | **`ownerScheme`** (int), **`ownerHash`** (hex 64), `ownerAddress` (PQ `ye…`). `ownerPubKey` / `ownerKeyId` are **removed** (no public key exists on chain) |
| `yed_listpositions` (`VaultRow`, `yellowbackwallet.cpp:197-227`) | `ownerPubKey` `:203`, `ownerKeyId` `:205`, `ownerAddress` `:206` | as `yed_getvault`: + `ownerScheme`, `ownerHash`; − `ownerPubKey`, `ownerKeyId` |
| `yed_listclaimable` | `ownerAddress` `yellowback.cpp:1281` | same name, PQ address |
| `yed_decodepayload` (MINT, `PayloadToJSON` `yellowback.cpp:478`) | `ownerPubKey` | **`ownerScheme`**, **`ownerHash`**; `version` 4 |
| `yed_listtokens <addresses>` (`yellowback.cpp:1189-1192`) | `CKeyID` only | accepts both `ye…` forms |
| `yed_getinfo.params` | — | add `"pq": {"schemes": [1] or [1,2], "falconActive": bool}`; `attest.payloadVersion` 4 |
| `yed_redeem` / `yed_claim` / `yed_estimateredeem` | — | fields unchanged; `earlyRedeemFeeZat` etc. as rpcversion 6. The fees grow by size (Q5) |

Removed fields (`ownerPubKey`, `ownerKeyId`, `ownerkey`) make this a breaking bump, which is the reason for 7.

### 6.3 The contract generator and gates

Workspace `scripts/extract_spec.py`:
- `UPGRADE_RPCVERSION = 5` `:157`, `INTERM_RPCVERSION = 6` `:160`, `SECTION_INTERM = "4.1"` `:159`.
- `doc_line()` `:550-560` reads 6+ as `interm`. `contract_text_interm` dies when the doc version ≠ the plan's
  (`:775-776`), **so a doc at 7 fails every mode today.**
- Makefile targets: `spec*` (`:38-53`).

Needed (mirrors in-term T-phase), coordinator-owned except the node files:
1. Quantum plan: a new `§4.10 RPC contract delta (\`rpcversion\` 7)` with `#### \`yed_*\`` JSON blocks, in the
   format of `yellowback-in-term-claims-plan.md:151-226`. "Removed fields" must be expressible: the in-term
   generator only merges, so `contract_text_quantum` needs a removal list. Recommendation: a fenced
   `removed` list in the section.
2. `extract_spec.py`: `PLAN_QUANTUM`, `SECTION_QUANTUM`, `QUANTUM_RPCVERSION = 7`, a `quantum` line in `doc_line`
   (≥7), and `contract_text_quantum` (in-term contract + quantum delta), `--write-quantum` / `--check-quantum`;
   Makefile `spec-quantum` / `spec-check-quantum`.
3. Node: `rpc/yellowback.cpp:60`, `doc/yellowback-rpc.md`, the regenerated `doc/yellowback-rpc-contract.json` +
   `doc/yellowback-spec.md` on both lines; `doc/vault-rpc.md` (`key` `:53`, `VaultFields.ownerkey` `:74`,
   `IntentFields.ownerkey` `:75`, `vault_list` `:116-122`, `vault_lock` `:208-213`) via
   `qa/vault-rpc-contract.py` (write, `--check`). This has no version, so the field rename is its own delta.
4. CI on these files, all **local only** (D-Q-17), so they are edited but not run on GitHub:
   - a quantum marker (as `"inTermClaims"` is grepped): recommend grepping `"falconActive"` in
     `src/rpc/yellowback.cpp`;
   - dd `qa/yellowback-audit.sh:334-335` (`want=`), `:383-384`;
   - 6 `.github/workflows/yellowback-tests.yml:511`, `:676`, `:784`, `:798`.
5. Clients (Q7): `yecwallet-dd/docs/yellowback-rpc-contract.json`;
   `lightwalletd-dd/testdata/yellowback/contract.json`; lightwalletd `KnownRPCVersion` 7.

lightwalletd proto fields that change (`walletrpc/yellowback.proto`):
- `YedPayload.ownerPubKey = 5` (`:128`)
- `YedVault.ownerAddress/ownerKeyId/ownerPubKey = 14/15/16` (`:140-141`)
- `VaultOutputFilter.owner = 3` (`:217`)
- `VaultOutput.ownerkey = 14` (`:239`)
- a `pq` field beside `inTermClaims = 22` (`:66`)

Recommended: **reserve** the removed field numbers and add `ownerScheme`/`ownerHash` as new numbers.

### 6.4 Owner-key storage (no format change)

- YED `VaultRecord.ownerPubKey` (`view.h:216`, key `'V'`+outpoint `view.cpp:115`, statehash `view.cpp:455`,
  `SCHEMA_VERSION = 8` `view.h:83`) holds 33 bytes, `scheme ‖ hash` (§3.4).
- Primitive `TemplateOutRecord` (`vault/state.h:135-150`) stores the whole scriptPubKey and re-parses it.
- Neither changes format. **No `SCHEMA_VERSION` bump is needed**, but the statehash vectors change, because the
  bytes do.

---

## 7. Findings and ambiguities (recommended smallest reading)

| # | Plan text | Problem | Recommendation |
|---|---|---|---|
| **F-1** | §4.3 "`TX_PQPKH` (bare, 36 bytes)", `<schemeId:1>` | A 36-byte script means pushing the scheme as `01 01`. `SCRIPT_VERIFY_MINIMALDATA` is a standard flag and requires a 1-byte value 1..16 to be `OP_n` (`interpreter.cpp:239-241`), so a `01 01` output is **unspendable under standard policy** (`SCRIPT_ERR_MINIMALDATA`). | Push the scheme as **`OP_1`/`OP_2`**. `TX_PQPKH` = **35 bytes**; the V/I owner slot = 35 bytes (V/I lengths unchanged). The interpreter reads a 1-byte element `{0x01}` either way. The parser/Solver accept only the `OP_n` form. Fix plan §1 item 2 ("stays 36 bytes"; P2PKH is 25) and §4.3 |
| **F-2** | §4.4 "MINT payload (v4 codec)" | It is unclear whether the version byte changes, and for which types. Keeping `03` with a re-meant MINT body makes the same bytes mean two things across `upgrade/vault` and the quantum line (clients: YEW, lightwalletd, chain-viz). | `PAYLOAD_VERSION = 0x04` for **every** type. Bodies are unchanged except MINT offset 17..49. v3 decodes as non-Yellowback (the existing V23 rule). Golden vectors regenerate (the version byte) |
| **F-3** | §4.4 "residual intent commits `SHA256(holderScript(owner))`" | `holderScript` is undefined; the owner has no holder key in the record | `holderScript(owner) = PQPKH(owner.scheme, owner.hash)` (35 B), §3.3 |
| **F-4** | §4.4 "~52 characters" | Exact length is **53** | versions `0x56BF` / `0x571E` / `0x5710`; 53 < 64 |
| **F-5** | §4.1/§4.2 step 6 "20 sigops wherever OP_CHECKSIG counts" | (a) Legacy counting charges creation, not spend, so verification is not bounded by it. (b) Context-free CheckBlock reprices historical scripts that contain a raw 0xc2 | Implement as written. Q6 adds a mainnet history scan; if any block exceeds 20,000, count 0 (as `OP_CHECKSETSIG`). Correct the plan §6 wording |
| **F-6** | §4.5 "an input whose previous output is TX_PQPKH … may carry 9,000" | `IsStandardTx` has no prevouts | Two sites: `IsStandardTx` allows ≤ 9,000 when `vaultActive`; `AreInputsStandard` enforces 9,000 for PQPKH/V/I prevouts and 1,650 for everything else. The V/I allowance covers **all** selectors (smallest; the parser bounds them) |
| **F-7** | §4.4 "the module accepts both shapes … PQ-only holders once Falcon is active" | No token-shape rule exists today: any script can hold YED | Before Falcon: no rule (status quo). After `pqFalconActive`: new rule `TOK-PQ` (assigned token outputs must be `TX_PQPKH` scheme 2). Fee payees stay `P2PKHKey` (D-Q-5). `HolderKey` is wallet/index only |
| **F-8** | §4.3 "token offsets after the owner slot shift by +1" | V has two owner slots | +1 after the first, +2 after the second (§1.2); I +1 |
| A-1 | §4.3 "A V-/I-shaped output with an unregistered scheme is not a template" | Is scheme 2 a template before Falcon is active? `Solver`/`ParseVault` are context-free | The parser accepts {1, 2} always. The interpreter rejects scheme 2 without the flag. **Policy** refuses creating scheme-2 V/I/PQPKH outputs while `!pqFalconActive` (§2.3). Consensus (V-1) is untouched; a bridge vault with a Falcon owner created by a miner is spendable by the set (selector 1) |
| A-2 | §4.4 | Attestation bundle / `BUNDLE-1` messages may bind `PayloadVersion()` | Q4 agent to grep `PayloadVersion`/`PAYLOAD_VERSION` in `bundle.cpp`/`attest.cpp` and regenerate `yellowback_attest_vectors.json` if it is bound |
| A-3 | §4.4 "`yed_mint` takes `owneraddress` in place of `ownerkey`" | `yed_mint` has no `ownerkey` argument (§3.6) | `yed_mint` keeps its six arguments. The owner is a fresh wallet SLH-DSA key, the token a fresh holder key (P2PKH until Falcon). Add an **optional 7th** `"owneraddress"` only if a client needs an external owner (no client does today) — recommend not adding it |
| A-4 | §4.3 "MINT-3 … Falcon only while `pqFalconActive`" for owners | Plan §1 says owners are SLH-DSA | Accept both registered schemes as owner, with Falcon gated (as written). Wallets create SLH-DSA owners only |
| A-5 | §4.8 `pqFalconActive` per-network consensus param | MINT-3 runs in `yellowback::EvalContext` with `yellowback::Params`, not `Consensus::Params` | Mirror it into `yellowback::Params` (like `attestorSetId`, U-22: `-yellowbackattestorset`), set from `Consensus::Params::pqFalconActive` at index init. One source of truth: the consensus param |
| A-6 | §4.2 step 4 "Hashtype handling as OP_CHECKSIG (including STRICTENC)" | `IsDefinedHashtypeSignature` reads the last byte. LOW_S / DER checks are ECDSA-only | Apply only the hashtype check (`STRICTENC`: `SIGHASH_ALL/NONE/SINGLE[|ANYONECANPAY]`); no DER/LOW_S. `NULLFAIL` is not a Ycash flag (`interpreter.h` has none): "push false" only |
| A-7 | §4.2 step 2 "pop `p` … 1..ceil(pkLen/520)" | The order of the size check vs. scheme activation | Order: scheme byte → registered (`SCRIPT_ERR_PQ_SCHEME`, including scheme 2 without `PQ_FALCON`) → hash 32 → p/s range → chunk canonicality (`PQ_CHUNK`) → total sizes (`PQ_SIZE`) → hash compare (false) → verify. Freeze this order in `pq_script_tests` |
| A-8 | §4.6 keystore `std::map<CPQKeyID, CPQKey>` | ycash6's wallet differs (§2.4) | Add the map to `CBasicKeyStore` on both lines. 6 needs the `pqkey` walletdb record in its own `ReadKeyValue` list. HD path per §4.6 on both, from each line's seed type (§2.4) |
| A-9 | §4.4 "`vault_lock`'s `ownerkey` accepts a PQ key hash with scheme" | Naming | §6 |
| A-10 | `src/test/data/vault_vectors.json` identity | Both lines are identical today | Regenerate once on dd, copy to 6 byte for byte; `VAULT_VECTORS.md` schema `ownerKey` → `owner{scheme, hash}` |
| A-12 | §4.6 "derived from the wallet's existing HD seed: `m/44'/347'/account'/0x5100'/index'`" | dd has **no HD transparent derivation** (random keys, `HDSeed` used only for Sapling `m/32'`); 6 has BIP44 on a `MnemonicSeed`. "account'" is undefined for dd | Both lines: BIP32 secp256k1 CKD (hardened) from each line's raw seed, path `m/44'/347'/0x7FFFFFFF'/0x5100'/index'` (account = 6's legacy account `ZCASH_LEGACY_ACCOUNT`), then the 32-byte child private key ‖ chain code (64 bytes) is the seed material. dd needs the BIP32 code that 6 has in `zcash/address/transparent.cpp` (or ships HKDF-SHA256(seed, "YcashPQ", path) on both). Recommend **HKDF on both lines** (smallest, byte-identical, no BIP32 port to dd), and flag the deviation from §4.6's path |
| A-13 | §4.4 "`yed_getnewaddress` returns a PQ address" | That conflicts with "holders may use P2PKH until Falcon" and with 8 KB SLH transfers | Follow the holder policy (P2PKH until `falconActive`); add the optional `type` arg so tests can request PQ |
| A-14 | `ScriptSigArgsExpected(TX_PQPKH)` | The survey agent proposed `2` | **`-1` + an `AreInputsStandard` special case**: the arg count is `s+p+2` (19 for SLH, 6 for Falcon). Optionally check the exact count per scheme there |
| A-15 | ycash6 `z_sendmany`/`WalletTxBuilder` | PQ is absent from `PaymentAddress`/`RecipientAddress`/`ZTXOPattern` | Leave it absent; PQ outputs are built only by the YED/vault builders. Record it as a 6-only limitation; `IsChange` on 6 does not see PQ change |
| A-11 | address index | The insightexplorer address index is keyed by `uint160` (`DestFromAddressHash`) | PQPKH outputs are not address-indexed (no change); `yed_listtokens` uses the YED index, not insight |
