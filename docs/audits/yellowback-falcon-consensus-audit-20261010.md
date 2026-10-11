> Independent audit (Fable reviewer agent, 2026-10-10) of the Falcon-512 / SLH-DSA consensus verification path on the
> post-quantum line, commissioned after the owner's decision to activate Falcon from day one (quantum plan D-Q-2).
> Harnesses and logs: `wt/scratch/falcon-audit/` (workspace-local).

# Falcon-512 (padded) in consensus from day one — independent audit

**Scope:** `ycash-dd` `upgrade/quantum-vaults` @ `0131122ab` (= `q/falcon1` at audit time; the day-one change was still
uncommitted in `wt/q-falcon1`), `ycash6` `upgrade/quantum-vaults` @ `1b023d1d6` and its `q/falcon1` commit `361d9c833`
(`consensus.pqFalconHeight = 0` for MAIN and TESTNET, nothing else). Read-only; all artefacts under
`wt/scratch/falcon-audit/` (notes `NOTES-static.md`, harness `harness/`, corpora `data_*.txt`, logs `fuzz.log`).
Auditor: senior crypto/consensus review, 2026-10-10. Prior reviewers' claims were re-derived, not trusted.

## 0. Verdict in one paragraph

The vendored Falcon verify path is a faithful, byte-identical copy of PQClean `falcon-padded-512/clean` at the pinned
commit (only the documented SHAKE-context patch differs), the Ycash entry point is PQClean's `crypto_sign_verify`
verbatim, and `pq::Verify`'s exact-length gate makes the accepted signature encoding unique per `(pk, msg, nonce, s2)`.
It is integer-only, allocation-free, exit-free, deterministic across compiler initialisation modes and optimisation
levels, and free of sanitizer findings over 34 M mutated verifications. It agrees with two other verifiers (the repo's
pure-Python one and Thomas Pornin's independent Rust `fn-dsa` in original-Falcon mode) on every one of 6,503 inputs,
including all 100 NIST round-3 KATs. The opcode integration enforces the frozen error order, canonical chunking, exact
sizes and one PQ check per `EvalScript`; the day-one gate (`pqFalconHeight = 0`) reduces `IsPQFalconActive` to
"UPGRADE_VAULT active" at every call site (mempool, block, miner, policy, module mirror), so there is no height at which
mempool and block disagree. **No critical or high finding. Code-level opinion: ship-able.** The remaining risk is
protocol-level and irreversible: a pre-standard signature scheme frozen into consensus for every YED holder; see §5.

## 1. Findings

Severity scale: critical / high / medium / low / info.

### F-1 (low) `ycash_falcon512_verify` itself accepts the compact (unpadded) form at its own length
`src/crypto/pq/falcon/ycash_falcon_verify.c:53-67` (PQClean's `do_verify` logic): when `sigbuflen != 625` the call still
succeeds if the compressed `s2` consumes exactly `sigbuflen` bytes. Only `pq::Verify` (`scheme.cpp:50`) rejects any
signature that is not 666 bytes. Evidence: the fuzzer's `raw_compact_accepts` counter (197 per 2 M iterations), every
one at `siglen == 41 + len(comp s)`; zero accepts at the `pq::Verify` level. Consensus is unaffected (the opcode
reassembles exactly `SigSize+1` bytes before calling `CheckPQSig`, `interpreter.cpp:1143-1145`, and `pq::Verify`
re-checks), but the Ycash-owned C entry point is called directly by the wallet and the tests and documents itself as
"the caller enforces the exact signature length". **Fix:** add `if (siglen != YCASH_FALCON512_SIGBYTES) return -1;` to
`ycash_falcon512_verify` (a Ycash file, not vendored), and keep the `pq::Verify` gate: two independent length checks on
the consensus path. Both lines together.

### F-2 (info) "No third-party malleability" holds only under standard policy
Plan §4.2 / spec R-B4: the stack elements are unique, but push *encodings* are not consensus-canonical
(`MINIMALDATA` is policy; `MANDATORY_SCRIPT_VERIFY_FLAGS = SCRIPT_VERIFY_P2SH`, `standard.h:85`). A miner can re-encode
`OP_PUSHDATA2` pushes and change a v4 txid. This is the pre-existing Ycash property for every scriptSig (ECDSA inputs
included) and is not introduced by Falcon; the signature bytes themselves have no benign re-encoding (§2). **Fix:**
wording only — "no *new* third-party malleability; push minimality is policy as for every Ycash input".

### F-3 (info) `hash_to_point_ct` vs the specification's rejection sampler
`common.c:70-232` uses Falcon's constant-time variant (717 draws, 205 spares). Its output equals the spec's vartime
sampler unless more than 205 of 717 draws are rejected: computed tail probability 2^-256 (binomial, p = 4091/65536).
The Python model and `fn-dsa` use the vartime sampler; 1,500 traced inputs agree coefficient-for-coefficient. No action;
record it in the README so a future "why do they differ?" has an answer.

### F-4 (medium, process) FIPS 206 status and the round-3 pin cannot be confirmed from here
NIST's `csrc.nist.gov/pubs/fips/206/{ipd,final}` return 404 at audit time and the briefing forbids `api.github.com`, so
neither the standard's status nor any PQClean issue filed after `0586a824fc` could be checked online. From the
auditor's knowledge: no verify-affecting erratum against Falcon `clean` after 2021 (the round-2 trailing-bit and
"-0" canonicity checks are present: `codec.c:449-463`); the FN-DSA draft is known to change *signing-side hashing*
(domain separation `nonce ‖ H(pk) ‖ 0x00 ‖ len(ctx) ‖ ctx ‖ msg`, see `fn-dsa-comm/src/lib.rs:154-190`) and possibly the
header/nonce layout, while key format and the `s2` codec were not expected to change. **Treat as unverified** until the
owner checks the FIPS 206 page and PQClean's issue tracker from an allowed machine; record the result in
`src/crypto/pq/README.md` with the date.

### F-5 (low) Undefined hashtype bytes are consensus-valid (as for ECDSA)
`STRICTENC` is policy, so e.g. hashtype `0x05` passes consensus and ZIP-243 hashes it as `SIGHASH_ALL`-shaped with the
raw byte committed in the preimage. Because the byte is inside the signed preimage, a third party cannot change it
(§2); it is signer-side freedom only, identical to `OP_CHECKSIG`. No action beyond keeping `pq_hashtypes`.

### F-6 (low) KAT coverage in the repo is 5 of 100
`pq_crypto_tests.cpp:507` replays round-3 counts 0–4 and PQClean's one padded KAT. This audit ran all 100 round-3
Falcon-512 KATs through `pq::Verify` (all 100 are representable in the padded format — none has `len(comp s) > 625`) and
through `fn-dsa`: 100/100 accept. **Fix:** ship the 100 as `pk msg paddedSig` verify-only rows (≈ 420 KB) or at least a
SHA-256 of the converted set with a nightly replay; the conversion is `harness/kat.py`.

### F-7 (info) Signer-side: the wallet's Falcon signer is PQClean's integer FP emulation, randomised from `GetRandBytes`
Not consensus. 5,000 signatures generated under ASan+UBSan verified under all three verifiers with no sanitizer output,
so the emulation is at least self-consistent on arm64. A signing bug can only lose the signer's own funds (a bad
signature is rejected), never create a consensus split.

### F-8 (info) Everything the README claims about the verify path was re-derived and holds
Byte-identity with PQClean (11 files `cmp`-identical; `fips202.{c,h}` differ only by the P1 hunks); `-mgeneral-regs-only`
compiles; zero FP arithmetic instructions in the `-O3` objects; no `malloc`/`exit`/`free` reachable from
`ycash_falcon512_verify` after P1; `slhdsa/` has none at all.

## 2. Falcon verification path — what was checked and how

**Parsing / canonicity (codec.c, ycash_falcon_verify.c).** Header `0x39` (`:94`), `siglen ≥ 41`, `pk[0] == 0x09`
(`:36`). `modq_decode`: 512 × 14 bits = exactly 896 bytes, each coefficient `< 12289` (`codec.c:101`), the trailing-bit
test is vacuous (acc_len = 0) and shift-safe. `comp_decode`: sign bit, 7 low bits, unary high part, `m > 2047` rejected,
`-0` rejected, unused bits of the last byte must be zero, every read bounds-checked. Padding: with `sigbuflen == 625`
every byte after the consumed prefix must be `0x00`. Hence for fixed `(nonce, s2)` exactly one 666-byte string
verifies; flipping any bit of header, nonce, body or padding either fails decode or changes `s2`/`c`.

**Hash-to-point.** SHAKE256(nonce ‖ msg) with msg = the 32 sighash bytes in memory order (`CheckPQSig`,
`interpreter.cpp:1540-1548`), identical to what `CPubKey::Verify` receives. `hash_to_point_ct` as above (F-3).

**Arithmetic (vrfy.c).** `s2 → +q` lift, NTT, pointwise Montgomery multiply by `h` (pre-converted by
`to_ntt_monty`), inverse NTT, subtract `c`, centre to `[-6144, 6144]` (`:666`). `is_short`: `|z| ≤ 6144 ⇒ z² ≤
37,748,736 < 2^31` (no signed overflow); the running `uint32` sum saturates through `ng` (each step adds < 2^26, so a
wrap must pass through `[2^31, 2^32)` and is caught); bound `l2bound[9] = 34,034,726 = ⌊β²⌋` of the round-3 spec.
`mq_montymul`: `z < 2^28`, `w < 2^30`, no overflow. 4,000 crafted `(s1, s2)` rows including exact-bound, over-bound,
saturating and max-magnitude cases: C `is_short` == exact Python arithmetic on all 4,000.

**UB / memory / determinism.** ASan+UBSan (`-fno-sanitize-recover=undefined`) over 34 M mutated verifications
(see §4) plus 1,400 structured mutations in trace mode: no report. Builds with `-ftrivial-auto-var-init=zero`,
`=pattern` and plain `-O3` give identical verdict streams and identical fuzz result hashes (so no uninitialised read
influences the result). No floating point (F-8). `tmp` (1,024 bytes) is exactly the 2·n bytes `hash_to_point_ct` and
`verify_raw` need; the union forces 8-byte alignment for the `uint16_t*` casts.

**Malleability / strong unforgeability.** A second valid `(nonce', s2')` for the same `(pk, msg)` with `(nonce', s2') ≠
(nonce, s2)` requires either a new short pre-image of a fresh `c'` (a forgery) or, for the same nonce, a different
short `s2'` with `c − s2'h` short — i.e. a short vector `(s2 − s2')·(h, −1)`, the SIS instance Falcon's security rests
on. Negation and per-coefficient tweaks were fuzzed explicitly (kinds 11/12/1): always rejected. Therefore v4 txids
remain malleable only by the holder of the signing key (and by miners through push re-encoding, F-2, as today).

**Cross-protocol reuse / domain separation.** Falcon round-3 has no context string. The message is a ZIP-243 sighash,
whose BLAKE2b personalisation `"ZcashSigHash" ‖ branchId(0x6d5b7a31)` and structure mean a Falcon signature produced by
the YED wallet can only ever be a signature over a Vault-branch v4 sighash; the PQ keys are derived for this use
(HKDF info `"Ycash PQ key"`) and nothing else in the node signs with them. A future protocol that let the same key sign
arbitrary 32-byte strings would reintroduce the concern — note it in the wallet plan.

**Hashtype (A-6).** The last byte of the reassembled 667-byte element is popped after the exact-size check; `STRICTENC`
restricts it to the six defined values under policy; the byte is committed inside the ZIP-243 preimage, so two
scriptSigs with different hashtype bytes need two signatures: no "two valid scriptSigs for one signature".

## 3. Opcode integration (`interpreter.cpp:1073-1163`, identical on both lines)

Order implemented: `SCRIPT_VERIFY_VAULT` (else `BAD_OPCODE`) → `++nPQSigCount > 1` (`PQ_COUNT`) → stack ≥ 2 →
scheme one byte & registered (`PQ_SCHEME`) → scheme 2 needs `SCRIPT_VERIFY_PQ_FALCON` (`PQ_SCHEME`) → keyHash 32
(`PQ_SIZE`) → `p` then `s`: one byte, `1..⌈len/520⌉`, with depth checks (`PQ_CHUNK` / `INVALID_STACK_OPERATION`) → every
non-last chunk exactly 520, none above (`PQ_CHUNK`) → reassembled sizes exact (`PQ_SIZE`) → `STRICTENC` hashtype →
`KeyHash(scheme‖pk) == keyHash && CheckPQSig` → pop `i−1`, push bool. This is spec A-7's frozen order. Index arithmetic
(`stacktop(-(iCount + nChunks − k + 1))`) and the final pop count were checked by hand. Chunking is injective. The
counter is per `EvalScript` (scriptSig, scriptPubKey, redeem script each start at 0), matching R-B1's "≤ 2 verifies
per input in practice". `scriptCode` is passed without `FindAndDelete` — correct, no signature bytes live in the
scriptPubKey. `KeyHash` binds the scheme byte, so a 0x02 key hash can never be satisfied by a future 0x03 key (§5).

**Day-one gating (`main.cpp:781-795`, ycash6 `:837-851`, same text).** `IsPQFalconActive = VAULT active ∧ pqFalconHeight ≠
NO_ACTIVATION ∧ h ≥ pqFalconHeight`; with 0 this is exactly "VAULT active". Call sites all use the block height being
validated: ATMP `nextBlockHeight` (`:1866` and the MANDATORY recheck `:1888`, both `| vaultFlags`), ConnectBlock
`pindex->nHeight` (`:3112`), miner `nHeight` (`miner.cpp:576`), policy `nHeight` = next (`policy.cpp:114`), YED module
mirror `PQFalconHeightOf = max(vault, falcon)` reading consensus params (`index.cpp:930`), −1 while the vault height is
unset. Consequences checked: (a) at the exact vault activation height H, a block at H and the mempool at tip H−1
compute the same flags; (b) a reorg below H evicts Vault-branch transactions by the existing branch-ID eviction
(`removeWithoutBranchId`, `main.cpp:4095`), the Falcon case being `vault_pq_reorg`; (c) reindex re-applies the rule from
H; (d) regtest is unchanged (`NO_ACTIVATION_HEIGHT` unless `-pqfalconheight`), `-pqfalcon*` on other networks is an
`InitError` (R-B3). No consensus behaviour differs between "Falcon at the vault height" and "Falcon at 0 after the
vault" because the conjunction with VAULT dominates. Both node lines: `src/crypto/pq/` (33 files), the opcode block,
`CheckPQSig`, the gate functions, `pq_vectors.json`, `pq_falcon_kat.json` and the README are byte-identical.

## 4. Robustness runs (all artefacts in `wt/scratch/falcon-audit/`)

| Run | Inputs | Result |
|---|---|---|
| NIST round-3 KATs, all 100, converted to padded (`harness/kat.py`) | `pq::Verify` semantics (ASan+UBSan build) | 100/100 accept; `fn-dsa` 100/100 |
| Golden vectors `pq_vectors.json` (3 Falcon, 2 SLH) | C, Python `pq.py`, `fn-dsa` | all accept |
| 5,000 fresh signatures (vendored signer under ASan+UBSan, 715 keys) | C, `fn-dsa` | 5,000/5,000 accept, no sanitizer output |
| Mutation fuzz, 16 mutation kinds incl. length, header, padding, nonce swap, pk ≥ q patterns | ASan+UBSan, 2 M-iteration chunks for 32 min | **34,000,000** calls (17 chunks × 2 M, 21:05–21:38), 0 accepts after mutation, 0 non-compact raw accepts, 0 sanitizer reports |
| Determinism | zero-init vs pattern-init vs `-O3`, 300 k + 200 k same-seed | identical result hashes; identical verdicts on the 5,103-line corpus |
| Structured mutations (14 kinds, 1,400 cases) in trace mode | C `comp_decode`/`modq_decode`/`hash_to_point_ct` vs Python; verdict vs Python and `fn-dsa` | 0 mismatches (101 accepts = 100 unmodified + 1 no-op nonce swap with itself) |
| `is_short` exactness, 4,000 rows incl. bound/saturation | C vs exact integers | 0 mismatches |
| SLH-DSA mutation fuzz (7 kinds), 300 k iterations | `slh_verify` under ASan+UBSan | 0 accepts after mutation, 0 reports |
| No-FP | `-mgeneral-regs-only` build of the 5 verify files; `objdump` of `-O3` objects | compiles; 0 FP arithmetic instructions |

Independence note: `pq.py` transliterates PQClean's `comp_decode` (same algorithm, so the decode comparison is
weak), but its hash-to-point is the spec's vartime sampler and its polynomial arithmetic is exact big-integer
Kronecker multiplication, so the NTT/Montgomery path is genuinely cross-checked. `fn-dsa` 0.3.0 (`HASH_ID_ORIGINAL_FALCON`,
`no_avx2`) shares no code with PQClean.

## 5. SLH-DSA (lighter pass)

`slh_verify` (`slh_dsa.c:705`): `ctx_sz > 255` rejected, `sig_sz == 7856` enforced twice, pure-mode prefix
`0x00 ‖ len(ctx)` added whenever `ctx_sz != 0x100` (`slh_sha2.c:35-42`; the sentinel is unreachable through
`slh_verify`), so an empty context is FIPS 205-conformant. State on the stack, no heap/exit (grep), SHA-2 only. ACVP
sigVer vectors already in the tree; 300 k mutations under sanitizers clean. No finding.

## 6. Supply chain

Vendored `falcon/` vs PQClean `0586a824fc` fetched from raw.githubusercontent into an isolated directory: `inner.h fpr.h
codec.c common.c vrfy.c keygen.c sign.c fft.c fpr.c rng.c LICENSE` byte-identical; `fips202.c/.h` differ exactly by
patch P1 (inline `uint64_t ctx[26]`, no `malloc`/`exit(111)`/`free`), which preserves every function signature and the
Keccak code; `ycash_falcon_verify.c` equals `pqclean.c`'s `do_verify`+`crypto_sign_verify` modulo two constant names.
PQClean is archived: the pin is stable but will never receive fixes; the owner takes on maintenance (F-4).

## 7. Ship / no-ship for Falcon-in-consensus on day one

**Code: ship, with conditions.** The verifier is correct, canonical and deterministic to the limits of this audit, and
the integration is consistent on both lines.

Conditions (all small):
1. F-1: exact-length check inside `ycash_falcon512_verify` on both lines (one line, Ycash-owned file, review-gated).
2. F-6: all 100 round-3 KATs in the test data (or their SHA-256 with a nightly replay).
3. F-4: confirm FIPS 206's public status and PQClean's post-pin issues from an allowed machine; record in the README.
4. Keep the three-verifier differential (C / Python / `fn-dsa` original mode) as a nightly job: the harness in
   `harness/` is reusable as is.
5. Docs: F-2 wording; F-3 note; the wallet plan notes that PQ keys must sign nothing but sighashes.

**Protocol-level risk the owner is accepting (not a code finding):** once a YED holder is paid to a scheme-0x02 hash,
that output is spendable only by a round-3 Falcon signature, forever; consensus cannot drop or alter 0x02 without
confiscation. Falcon-512's security estimates (NIST level 1) are unchanged by the FN-DSA process, and the known
Falcon weaknesses are signer-side (floating-point side channels, which a wallet on a user's machine tolerates). The
decision is therefore sound *cryptographically* and *irreversible operationally*.

## 8. FIPS 206 contingency: is "add scheme 0x03 later" sufficient?

**For consensus: yes.** The registry is scheme-indexed (`PubKeySize`/`SigSize`/`Verify` switch on the byte), the
opcode is scheme-agnostic beyond the per-scheme sizes and `KeyHash = SHA256(scheme ‖ pk)` binds the scheme, so a 0x03
key can never satisfy a 0x02 hash and vice versa. Adding 0x03 is one new case per function plus a network-upgrade gate
(the same shape as `SCRIPT_VERIFY_PQ_FALCON`), with no change to existing outputs' validity.

**But it is not sufficient on its own; three things must come with it:**
1. **`TOK-PQ` must be amended** in the same upgrade (it currently requires "scheme 2" holders, `yellowback/script.cpp:132`
   and the channel rule): otherwise new-scheme holders cannot receive YED. This is a reviewed consensus change in the
   YED module, not just the registry.
2. **Wallet migration, not key reuse.** FN-DSA's expected changes are in the hashed input (`nonce ‖ H(pk) ‖ 0x00 ‖ …`)
   and possibly the header; if the key format is unchanged the *same key material* could be a 0x03 key with a
   different hash. That is safe only if signatures cannot be transplanted across schemes — guaranteed here by the
   scheme byte in the key hash and the different hashed inputs — but the clean rule is: new scheme, new derivation
   index, move funds by ordinary transfers. The HKDF derivation already takes the scheme byte in `info`.
3. **0x02 stays forever.** Every client (YEW, lightwalletd, chain-viz, x402) must keep round-3 Falcon verification and
   both address encodings indefinitely; the node must keep PQClean's code even after FIPS 206 implementations
   supersede it. Budget for that maintenance now (PQClean is archived).

If FIPS 206 turns out to change the *codec* or *parameters* (not expected), nothing above changes: 0x03 is simply a
different scheme. If FIPS 206 is published byte-compatible with padded round-3 Falcon, 0x03 is unnecessary and 0x02
simply *is* FN-DSA-512 — the best case, and the reason the padded PQClean format (the FN-DSA draft's own encoding
lineage) was the right pick.
