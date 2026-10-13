# LOW — 02/PQ-1, 02/PQ-2 — Wipe the Falcon DRBG/sampler SHAKE states and zeroize slhdsa-c's `slh_var_t` (local patch P3)

**Repos / branches to change:** `ycash-dd` and `ycash6` (both; `src/crypto/pq` is byte-identical across the lines and must stay so), new branch `fix/02-PQ-1-pq-stack-zeroize` off `upgrade/vault` in each.
**Audit source:** `docs/audits/quantum-vault-ecosystem/02-post-quantum-crypto.md` §PQ-1 (`:47-67`), §PQ-2 (`:69-84`); `verification/02-verification.md` §2.1 rows PQ-1, PQ-2 (`:48-49`), §4.4 ("Residue: the vendored C's own stack frames").
**Status:** pending.

## 1. Finding

Wallet-side secret residue in dead stack frames of the vendored PQ C code. In the Falcon entry points, local patch P1 (2026-10-10) turned PQClean's heap-allocated SHAKE256 context into a 208-byte inline array (`fips202.h:27-33`) and made `shake256_inc_ctx_release` a no-op (`fips202.c:557-580`). The wipe lists written at the same time cover the secret polynomials and the scratch buffer only. So after `ycash_falcon512_keygen_from_seed` returns, the SHAKE256 state seeded with the HKDF-derived keygen seed — which deterministically yields the whole key pair — sits in the dead frame; after `ycash_falcon512_sign` returns, the sampler's RNG state (seeded from `GetRandBytes`) does too, and the Gaussian draws it produced, together with the public signature, reveal the sampler centre, a function of the secret basis.

In `slhdsa-c`, `sha2_mk_var` copies `SK.seed` and `SK.prf` (the 32 bytes that fully determine an SLH-DSA key) into a stack-resident `slh_var_t`, and upstream never zeroizes it; `slh_keygen_internal` and `slh_sign` return with the copy still in the frame. Upstream marks the library "not recommended for production" and has no cleanse. Exposure is local (a same-process memory disclosure, a core dump, swap); no network or consensus path is affected, and the consensus `slh_verify` / `ycash_falcon512_verify` paths hold only public values. Both verifiers confirmed; severity Low.

## 2. Root cause

ycash-dd `055d9c2` (ycash6 `e866c45` identical, `diff -r src/crypto/pq` empty):

- `src/crypto/pq/falcon/ycash_falcon_sign.c:39` `inner_shake256_context rng;` in `ycash_falcon512_keygen_from_seed`; seeded `:51-55` (`inner_shake256_inject(&rng, seed, seedlen)`), released as a no-op `:55`; the `done:` wipes at `:96-99` list `f g F tmp.b` only.
- `src/crypto/pq/falcon/ycash_falcon_sign.c:117` `inner_shake256_context sc;` in `ycash_falcon512_sign`; first use is the public message hash `:166-170`, then it is re-initialised from the 48-byte sampler seed `:176-178` and drives `sign_dyn` in the loop `:183-191`; the `done:` wipes at `:198-202` list `f g F G tmp.b` only.
- `src/crypto/pq/falcon/fips202.h:27-33` (P1: `uint64_t ctx[26]` inline); `fips202.c:557-580` (`shake256_inc_ctx_release` is `(void)state;`).
- `src/crypto/pq/slhdsa/slh_sha2.c:338-351` `sha2_mk_var` `memcpy`s `sk_seed`, `sk_prf`, `pk_seed`, `pk_root` into `var`; `slh_dsa.c:477` `slh_var_t var;` in `slh_keygen_internal` (no wipe before `}`); `slh_dsa.c:613` `slh_var_t var;` in `slh_sign`, returns at `:641` without a wipe. `grep -n 'memset\|wipe' slh_dsa.c` shows only `PK.root` initialisation.
- `src/crypto/pq/README.md:70` lists `slh_dsa.c` under "Files, **unmodified**"; `:127-160` documents P1 and P2 as the only local patches. There is no CI provenance script: provenance is the README's file lists plus the auditors' `cmp` against the pinned upstream commits (`0586a824…`, `174c02e4…`).

## 3. Fix options considered

1. **Caller-side scrubbing in `sign.cpp`** (overwrite "the stack region below" after the call): not portable, undefined behaviour, and the frame layout is compiler-dependent. Rejected by the first wave.
2. **Fork `slh_dsa.c`'s keygen/sign into a Ycash-owned file** (as `ycash_falcon_sign.c` does for PQClean's `pqclean.c`): would duplicate ~150 lines of standard-bearing code and leave `slh_dsa.c` in the build anyway (for `slh_verify`); larger delta than needed.
3. **Local patch P3 inside `slh_dsa.c`, marked like P1** (first-wave recommendation, verifier-confirmed): three one-line wipes at function exit through a volatile-safe helper. Smallest reviewable change. **Recommended.**
4. For Falcon, the only option is adding the two missing wipes to the existing lists (Ycash-owned file, no provenance impact).

## 4. Recommended fix

Both lines, identical bytes (apply the patch to `ycash-dd`, then `cp` the two files into `ycash6` and confirm `diff -r src/crypto/pq` is empty).

**Falcon (`src/crypto/pq/falcon/ycash_falcon_sign.c`, Ycash-owned, no README list change):**
1. In `ycash_falcon512_keygen_from_seed`, add `wipe(&rng, sizeof rng);` to the `done:` block (after `:99`, before `return ret;`). Keep the `inner_shake256_ctx_release(&rng)` call at `:55` (no-op, upstream shape).
2. In `ycash_falcon512_sign`, add `wipe(&sc, sizeof sc);` to the `done:` block (after `:202`). It must be in `done:`, not after the hash-to-point at `:170`, because `sc` is re-seeded at `:176` and used until the loop breaks at `:187`; `done:` is also reached on the early `goto done` failure paths, which is what we want.
3. Update the comment above each `done:` ("wipe the secret polynomials, the keygen scratch **and the DRBG state**").

**SLH-DSA (`src/crypto/pq/slhdsa/slh_dsa.c`, local patch P3):**
4. Add one static helper near the top of the file, marked:
   ```c
   /* YCASH LOCAL PATCH P3 (src/crypto/pq/README.md, "Local patches"): wipe a secret-bearing
    * slh_var_t before the frame dies; upstream slhdsa-c has no zeroization. */
   static void slh_wipe_var(slh_var_t *var)
   {
     volatile uint8_t *p = (volatile uint8_t *)var;
     size_t i;
     for (i = 0; i < sizeof(*var); i++) p[i] = 0;
   }
   ```
   (C90-compatible, same construction as `wipe()` in `ycash_falcon_sign.c:21-27`; do not use `memset`, which the optimiser may elide.)
5. Call `slh_wipe_var(&var);` immediately before the `return` of `slh_keygen_internal` (`:477-490`) and of `slh_sign` (`:613-641`; also wipe `digest` there — it is a message digest, public, but costs nothing). Grep the file for every other `slh_var_t var` declared from a secret key (`sk != NULL` path of `mk_var`) and treat it the same; the `slh_verify` path builds `var` from `pk` only and needs nothing. Mark every changed line `YCASH LOCAL PATCH`.
6. **Provenance bookkeeping** (`src/crypto/pq/README.md`): move `slh_dsa.c` from the `slhdsa/` "Files, **unmodified**" list (`:70`) to a new "**Patched**: `slh_dsa.c` (local patch P3)" line, and add a "### P3: `slhdsa/slh_dsa.c`, zeroization of `slh_var_t` (date)" section after P2 (`:153-160`) stating: the patch in full (helper + the call sites), that no function signature, constant or output changes, that the consensus `slh_verify` path is untouched, and that the patch is carried on the 6.20.0 line. The audit's provenance check is "every listed-unmodified file `cmp`s equal to upstream at the pinned commit, every patched file differs only by lines marked `YCASH LOCAL PATCH`" — keeping that true is what keeps the check passing. Optionally (not required) add `qa/yellowback-pq-provenance.sh` that clones the two upstreams at the pinned commits and performs exactly that check, run from the nightly tier.
7. `docs/mapping.md` §22: one row ("slhdsa-c has no zeroization → local patch P3", with the line citations above), per workspace rule 5.

Consensus footprint: none. `slh_dsa.c` is linked into the consensus verifier, but the patch adds code only to keygen/sign functions the verify path never calls; every vector (golden, ACVP, KAT) is byte-identical before and after.

## 5. Tests

- Existing: `pq_crypto_tests` (`pq_golden_vectors`, `pq_slhdsa_acvp`, `pq_falcon_kat`, `pq_round_trip_and_rejects`) and `pq_wallet_tests` must pass unchanged on both lines — proves outputs are unaffected.
- New, cheap, deterministic: in `pq_crypto_tests.cpp`, a `pq_sign_wipes_stack` case is not portable (frame layout); instead add a **compile-time grep leg** to `qa/yellowback-audit.sh` (both lines): `grep -c 'wipe(&rng' ycash_falcon_sign.c == 1`, `grep -c 'wipe(&sc' == 1`, `grep -c 'slh_wipe_var(&var)' slh_dsa.c >= 2`, and `diff -r ycash-dd/src/crypto/pq ycash6/src/crypto/pq` empty (the workspace's cross-line check).
- Manual, once, recorded in the PR: build with `-O2`, run a 40-line gcc harness (the verifier's method, `verification/02-verification.md` §1) that calls keygen then scans the dead frame region for the 48-byte seed and for `SK.seed`; before the patch the bytes are found, after they are not. Not a CI test.

## 6. Acceptance criteria

- `ycash_falcon_sign.c` `done:` blocks wipe `rng` (keygen) and `sc` (sign); every `slh_var_t` built from a secret key is wiped before its function returns; all changed lines carry `YCASH LOCAL PATCH`.
- README lists updated (P3 section; `slh_dsa.c` moved to "Patched"); a fresh clone of `slhdsa-c@174c02e4` `cmp`s equal to every file still listed as unmodified, and `diff` of `slh_dsa.c` shows only P3 lines. Same for PQClean@`0586a824` (P1 only).
- `src/crypto/pq` identical on both lines; all `pq_*` unit suites and the `vault_pq*` / `yellowback_pq*` / `wallet_pq_address` functional scripts pass on both.
- `docs/mapping.md` row added.

## 7. Risks and side effects

- None to consensus or vectors. A mis-placed `wipe(&sc)` before the signing loop would break signing (caught at once by `pq_golden_vectors`).
- The P3 helper must not be optimised away: use the volatile store loop, not `memset`.
- Provenance: the audit's "13/13 byte-identical" slhdsa-c statement becomes "12/13 + one documented patch"; the README is the record. If the owner prefers zero slhdsa-c delta, option 2 (fork keygen/sign into `ycash_slh_sign.c`) is the alternative at ~3× the diff.

## 8. Effort estimate and dependencies

~1 hour code (both lines), ~1 hour README/mapping/audit-leg, one reviewer. No dependencies; independent of every other report. Lands together with or before 02/PQ-3 (same file region in `sign.cpp` is untouched here, so no conflict).
