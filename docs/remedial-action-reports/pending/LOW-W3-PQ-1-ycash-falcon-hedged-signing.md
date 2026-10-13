# LOW — W3-PQ-1 — Hedge Falcon wallet signing: derive the nonce and sampler seed from SHAKE256(domain ‖ sk ‖ msg ‖ fresh OS randomness)

**Repos / branches to change:** `ycash-dd` and `ycash6` (both; `src/crypto/pq` is byte-identical across the lines and must stay so), new branch `fix/W3-PQ-1-falcon-hedged-sign` off `upgrade/vault` in each. Wallet-only: no consensus path, no vector change.
**Audit source:** `docs/audits/quantum-vault-ecosystem-wave3/02-post-quantum-crypto.md:70-88` (W3-PQ-1); `docs/audits/quantum-vault-ecosystem-wave3/verification/02-verification.md:49-81` (CONFIRMED, Low, scenario narrowed: a dead RNG aborts, so the residual is state duplication); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:49` ("residual: VM-snapshot replay"). Precedent: LOW-02-PQ-3 (done; SLH-DSA hedged signing). Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:73` (STILL OPEN, Δ-free: `src/crypto/pq`); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`; `src/crypto/pq` is untouched and still identical across the lines.
**Status:** pending

## 1. Finding

`pq::Sign` for Falcon-512 (scheme `0x02`) draws 88 bytes from `GetRandBytes` and passes them straight to `ycash_falcon512_sign`: 40 bytes become the signature nonce (copied into the signature and hashed with the message by `hash_to_point_ct`), 48 bytes seed the SHAKE256 PRNG that drives the Gaussian sampler (`sign_dyn`). That is a faithful port of PQClean's `randombytes` usage. No key or message material enters either value. SLH-DSA, by contrast, computes `R = PRF_msg(SK.prf, opt_rand, M)` (hedged since LOW-02-PQ-3), and ECDSA uses RFC 6979.

The scenario (narrowed by the verifier) is the following. `GetRandBytes` is `OsRng.fill_bytes` through the Rust FFI, which panics (aborts) when the OS source fails, so a *dead* RNG stops the node rather than repeating bytes. What remains is **state duplication**: a VM snapshot restored twice, or a forked container whose kernel entropy pool is replayed. There the same 88 bytes recur for two different sighashes. The same 40-byte nonce appears on chain in both signatures, and the same sampler stream is applied to two different target points. No published attack recovers a Falcon key from that correlation, so this is not ECDSA nonce reuse. But Falcon's security argument assumes independent per-signature sampler randomness, and the vendored sampler has no argument for the correlated case. Among the wallet's secret draws, Falcon is the only one where such a replay is both visible (the nonce) and untreated. Low, hardening; the fix is cheap and standard.

## 2. Root cause

ycash-dd `da5e0fe` (ycash6 `0742e43` identical, `diff -r src/crypto/pq` empty):

- `src/crypto/pq/sign.cpp:101-107`: `pq::Sign`, scheme 2: `std::vector<unsigned char> entropy(FALCON_SIGN_ENTROPY_SIZE); GetRandBytes(entropy.data(), entropy.size()); SignWithEntropy(...)`, then `memory_cleanse`.
- `src/crypto/pq/sign.cpp:76-82`: `SignWithEntropy`, scheme 2, which requires exactly `FALCON_SIGN_ENTROPY_SIZE` (= 88, `sign.h:44`) bytes and calls `ycash_falcon512_sign(out, msg, 32, sk, entropy, entropy + YCASH_FALCON512_NONCEBYTES)`.
- `src/crypto/pq/falcon/ycash_falcon_sign.c:110-112` (signature), `:162-165` (`memmove(sigout + 1, nonce, NONCELEN)`), `:172-177` (`hash_to_point_ct` over nonce ‖ m), `:182-184` (`inner_shake256_inject(&sc, seed, YCASH_FALCON512_SIGN_SEEDBYTES)`), `:190-198` (`sign_dyn` loop). The `done:` wipes at `:201-215` already cover `sc` (LOW-02-PQ-1).
- `src/crypto/pq/falcon/ycash_falcon.h:27-31,62` (sizes: sk 1281, nonce 40, seed 48; the C entry point).
- `src/random.cpp:37-40` → `src/rust/src/rustzcash.rs:1249-1252` (`OsRng.fill_bytes`, which panics on failure); per the verifier.
- Contrast: SLH-DSA `pq::Sign` `:91-100` (16 bytes of `opt_rand`; `R = PRF_msg(SK.prf, opt_rand, M)` in `slhdsa/slh_dsa.c`).

## 3. Fix options considered

1. **Leave as is** (faithful to PQClean). Rejected: the cost of hedging is a few lines and one SHAKE256 call per signature.
2. **Hedge in C++ (`sign.cpp`) with HMAC-SHA512** (`crypto/hmac_sha512.h` exists): two HMAC blocks to cover 88 bytes. Works, but it mixes a second hash family into the Falcon path for no reason. Rejected in favour of 3.
3. **Hedge in C with SHAKE256, in a new Ycash-owned entry point next to `ycash_falcon512_sign`** (the audit's construction, the verifier's preferred form). SHAKE256 is already linked into the sign path through `inner_shake256_*` (local patch P1: inline context, no heap). It keeps all Keccak use in one C file that is Ycash-owned (no vendored-file provenance change), and the derivation is directly unit-testable. **Recommended.**
4. **Fully deterministic Falcon** (derive from sk ‖ msg only, no RNG). Rejected: it removes the fault-attack and side-channel hedging that fresh randomness gives. The hedged form keeps it, and the verifier's point stands that "deterministic if the RNG is dead" is moot here (a dead RNG aborts).

## 4. Recommended fix

Both lines, identical bytes. Apply to `ycash-dd`, copy the three files to `ycash6`, and confirm `diff -r src/crypto/pq` is empty.

1. **`falcon/ycash_falcon.h`** declares two functions:
   ```c
   /* Hedged signing randomness (audit W3-PQ-1): out[0..88) = SHAKE256(domain || LE16(sklen) || sk ||
    * LE16(mlen) || m || LE16(rndlen) || rnd)[0..88); the first 40 bytes are the nonce, the next 48 the
    * sampler seed. Wallet-only. */
   #define YCASH_FALCON512_HEDGE_DOMAIN "Ycash Falcon-512 hedged signing v1"
   void ycash_falcon512_hedge(uint8_t out[YCASH_FALCON512_NONCEBYTES + YCASH_FALCON512_SIGN_SEEDBYTES],
                              const uint8_t *sk, size_t sklen, const uint8_t *m, size_t mlen,
                              const uint8_t *rnd, size_t rndlen);
   /* ycash_falcon512_sign with the nonce and seed from ycash_falcon512_hedge(sk, m, rnd); wipes them. */
   int ycash_falcon512_sign_hedged(uint8_t *sig, const uint8_t *m, size_t mlen, const uint8_t *sk,
                                   const uint8_t *rnd, size_t rndlen);
   ```
   The length prefixes make the encoding injective. `sk` is the full 1,281-byte encoded key (f, g, F), with no slicing. The domain string is 34 ASCII bytes, absorbed without a terminator.
2. **`falcon/ycash_falcon_sign.c`** (Ycash-owned): implement both with `inner_shake256_init/inject/flip/extract`. In `_sign_hedged`, keep `uint8_t ent[88]`, call `ycash_falcon512_sign(sig, m, mlen, sk, ent, ent + 40)`, then `wipe(ent, sizeof ent)` on every path. In `_hedge`, name the SHAKE context `hctx` and `wipe(&hctx, sizeof hctx)` before returning. (The audit leg counts `wipe(&sc, …)` / `wipe(&rng, …)` exactly once each, so do not reuse those names.) Use the file's existing `wipe()` (volatile loop), not `memset`.
3. **`sign.cpp`, `pq::Sign` scheme 2** (`:101-107`) becomes:
   ```cpp
   if (scheme == SCHEME_FN_DSA_512) {
       // Hedged (audit W3-PQ-1): nonce and sampler seed = SHAKE256(domain || sk || msg || 48 fresh bytes),
       // so a replayed OS RNG (VM snapshot, forked container) cannot repeat them across messages. The
       // verifier is nonce-agnostic; vectors use SignWithEntropy with explicit entropy and are unaffected.
       if (sk.size() != SecretKeySize(scheme)) return false;
       std::vector<unsigned char> rnd(FALCON_SIGN_SEED_RND_SIZE);   // 48
       GetRandBytes(rnd.data(), rnd.size());
       std::vector<unsigned char> out(SigSize(scheme));
       const bool ok = ycash_falcon512_sign_hedged(out.data(), msg.begin(), msg.size(), sk.data(),
                                                   rnd.data(), rnd.size()) == 0;
       memory_cleanse(rnd.data(), rnd.size());
       if (ok) sig.swap(out);
       return ok;
   }
   ```
   Add `static const size_t FALCON_SIGN_SEED_RND_SIZE = 48;` to `sign.h` next to `FALCON_SIGN_ENTROPY_SIZE` (`:44`). `SignWithEntropy` is **unchanged**.
4. **`src/crypto/pq/README.md`**, "Ycash entry points" (the `ycash_falcon_sign.c` description): one paragraph describing the hedged entry point, the exact derivation, the domain string, and that `SignWithEntropy` / `ycash_falcon512_sign` remain the explicit-entropy path for vectors. No change to the vendored-file lists (only Ycash-owned files change).
5. **Spec:** `docs/plans/yellowback-quantum-spec.md` §4.6 ("Sign once") / the wallet signing paragraph: Falcon wallet signing is hedged like SLH-DSA, with the derivation and domain string. `docs/mapping.md` §22: one row ("PQClean draws nonce/seed from `randombytes` → Ycash hedges them with SHAKE256(sk ‖ msg ‖ rnd)").
6. **Optional, test framework:** add a `falcon_sign_hedged(sk, msg, rnd)` binding to `qa/rpc-tests/test_framework/pq.py` (next to the `ycash_falcon512_sign` binding at `:584-585`) so functional tests can produce node-identical hedged signatures. It is not needed by any existing test.

### Why the vectors are unaffected (and why this is byte-compatible)

- **Verification is nonce-agnostic.** A Falcon signature carries its own 40-byte nonce; the verifier (`ycash_falcon512_verify`) recomputes `hash_to_point(nonce ‖ m)` from the signature bytes and checks the norm bound. *How* the signer chose nonce and seed is invisible to it, so every hedged signature verifies under the unchanged consensus `pq::Verify`, and every node of every version accepts it. There is no consensus footprint, and no client (YEW, Hawkeye, x402) has to change.
- **The golden and conformance vectors use the explicit-entropy path.** `pq_vectors.json` records the 88 bytes of entropy per Falcon signature and is regenerated and replayed through `SignWithEntropy` → `ycash_falcon512_sign`, which this change does not touch. The NIST/PQClean KAT replay (`pq_falcon_kat.json`) drives the same function with the KAT's DRBG output. `pq_wallet_vectors.json` covers key derivation, not signing. So all nine vector files are byte-identical before and after, and the cross-line identity check stays green.
- **Sign-once records** (wallet `vaultsetsig`, Hawkeye's records) store and re-use the bytes they signed. A hedged signature is just a different valid signature at first signing; a retry still re-uses the stored bytes (workspace rule "sign once").

## 5. Tests

New cases in `src/test/pq_crypto_tests.cpp` (both lines; identical file apart from includes):
- `pq_falcon_hedge_derivation`: a known-answer test of `ycash_falcon512_hedge` with fixed sk (golden key 2's sk), msg and rnd. The expected 88 bytes are computed independently in Python: `hashlib.shake_256(domain + len(sk).to_bytes(2,'little') + sk + len(m).to_bytes(2,'little') + m + len(rnd).to_bytes(2,'little') + rnd).digest(88)`. Write the Python one-liner in the test comment. This pins the encoding so that a later "tidy-up" cannot silently change it.
- `pq_falcon_hedged_sign`:
  - (a) `ycash_falcon512_sign_hedged` with fixed rnd equals `ycash_falcon512_sign` with `ycash_falcon512_hedge`'s output (composition), and verifies with `pq::Verify`;
  - (b) same rnd, different msg gives different nonce bytes (`sig[1..41)`), which is the replay case;
  - (c) same rnd, same msg gives an identical signature (deterministic given its inputs);
  - (d) two `pq::Sign` calls on the same msg give different nonces (fresh randomness still mixed in);
  - (e) a 1-bit change in `sk` gives a different nonce;
  - (f) `pq::Sign` output is accepted by `OP_CHECKPQSIG` through `VerifyScript` in an existing `pq_script_tests` real-key case (switch one Falcon case from `SignWithEntropy` to `pq::Sign` if none uses it).
- Existing: `pq_golden_vectors`, `pq_falcon_kat`, `pq_round_trip_and_rejects`, `pq_wallet_tests`, `pq_timings` and the `vault_pq*` / `yellowback_pq*` / `wallet_pq_address` functional scripts pass unchanged on both lines. That they pass unchanged is the vector-compatibility proof.
- `qa/yellowback-audit.sh` `leg_pq_wipes` (dd `:521-534`) counts `wipe(&rng, sizeof rng)` and `wipe(&sc, sizeof sc)` and requires **exactly 1** of each (`:528-529`). Name the new SHAKE context `hctx` (not `sc`/`rng`) so those counts stay correct, and add two counts of 1: `wipe(ent, sizeof ent)` and `wipe(&hctx, sizeof hctx)`. ycash6 has no such leg; its workflow's cross-line identity check carries the file.

## 6. Acceptance criteria

- `pq::Sign` for scheme 2 calls `ycash_falcon512_sign_hedged` with 48 fresh bytes. `SignWithEntropy` and `ycash_falcon512_sign` are unchanged. The hedge buffer and SHAKE context are wiped on every path.
- The derivation KAT matches the Python one-liner; (a)-(f) pass on both lines.
- All nine `src/test/data` vector files are byte-identical to before (`git diff --stat src/test/data` empty), and `src/crypto/pq` is identical across the lines.
- README, quantum spec and mapping updated.

## 7. Risks and side effects

- No consensus or vector impact (section 4). A mistake in the new path would produce signatures that fail `pq::Verify`, which (a) and (f) catch at once.
- Cost: one SHAKE256 over ~1.4 KB per Falcon signature, negligible beside `sign_dyn`.
- YEW signs Falcon independently (its own Kotlin/Rust stack, OS RNG; `00-consolidated.md:78`). This change does not reach it. If the owner wants the same hedge there, that is a one-function YEW follow-up using the same derivation and domain string. Note it in the YEW plan; it is not required for this report.

## 8. Effort estimate and dependencies

- ~0.5 day code (both lines), ~0.5 day tests and docs. One reviewer (crypto-literate).
- No dependency. Touches `ycash_falcon_sign.c`, which LOW-W3-PQ-2 does not touch (that one touches `fips202.c`), so they are independent. Order relative to MEDIUM-W3-P-2 does not matter: its manifest lists `src/crypto/pq` as a `tree` (compared across lines, not pinned by hash), so the only requirement is that both lines carry the change in paired PRs.
