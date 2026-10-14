# LOW — 02/PQ-3 — Hedge SLH-DSA wallet signing (`pq::Sign` → `SignWithEntropy` with 16 fresh bytes)

**Repos / branches to change:** `ycash-dd` and `ycash6` (`src/crypto/pq/sign.{cpp,h}` identical across lines), branch `fix/02-PQ-3-slhdsa-hedged` off `upgrade/vault` in each; `yellowback` workspace docs (one sentence each in the quantum plan/spec and `src/crypto/pq/README.md`).
**Audit source:** `02-post-quantum-crypto.md` §PQ-3 (`:86-103`); `verification/02-verification.md` §2.1 row PQ-3 (`:50`), §4.5 ("SLH-DSA is deterministic by design (PQ-3)").
**Status:** done — completed 2026-10-13T07:30Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13, re-confirmed 2026-10-14 at ycash-dd 3fe3492b6 and ycash6 1ebfee622; nightly tier pending the owner's dispatch)

## 1. Finding

The wallet signs SLH-DSA-SHA2-128s deterministically: `pq::Sign` passes an empty entropy vector, so `slh_sign` sets `opt_rand = PK.seed`. FIPS 205 §9.2 permits this but recommends the hedged variant, and for hash-based signatures the deterministic variant is the one with a known fault attack (Castelnovi–Martinelli–Prest 2018; Genêt et al. 2018): a fault during the FORS/hypertree computation of a *repeated* signature over the same message yields a second WOTS+ signature under the same one-time key and leaks it. Randomised `R` gives every signature a fresh FORS/leaf path, removing the repeat.

Risk is low for a software wallet on a general-purpose CPU, but hedging costs 16 bytes from `GetRandBytes` and nothing else: the entry point already exists, is NIST-tested (ACVP sigGen 474/475 are hedged cases run through it) and the verifier is `R`-agnostic. Verifier confirmed, Low.

## 2. Root cause

ycash-dd `055d9c2` / ycash6 `e866c45` (identical):
- `src/crypto/pq/sign.cpp:88-92`: `Sign` for `SCHEME_SLH_DSA_SHA2_128S` calls `SignWithEntropy(scheme, sk, msg, std::vector<unsigned char>(), sig)`.
- `src/crypto/pq/sign.cpp:62-73`: `SignWithEntropy` hands `entropy.empty() ? nullptr : entropy.data()` to `slh_sign`'s `addrnd`.
- `src/crypto/pq/slhdsa/slh_dsa.c:626-633`: `addrnd == NULL` → `opt_rand = var.pk_seed`.
- `src/crypto/pq/sign.h:29-32` documents `Sign` as "SLH-DSA: … deterministic (opt_rand = PK.seed)"; `README.md` says the same; `docs/plans/yellowback-quantum-plan.md:213` ("SLH-DSA signatures are deterministic in the non-hedged mode …").

## 3. Fix options considered

1. Keep deterministic signing and document the accepted fault-attack surface. Costs nothing, leaves a free mitigation on the table. Rejected.
2. Hedge in `pq::Sign` with 16 bytes from `GetRandBytes`, mirroring the Falcon branch (`sign.cpp:93-100`). **Recommended.**
3. Hedge in `CPQKey::Sign` (`pqkey.cpp:36-42`) instead: same effect, but `pq::Sign` is the documented "wallet" entry point and the Falcon randomness already lives there. Rejected for symmetry.

## 4. Recommended fix

`src/crypto/pq/sign.cpp:88-92` (both lines, identical):

```cpp
if (scheme == SCHEME_SLH_DSA_SHA2_128S) {
    std::vector<unsigned char> entropy(SLH_N);        // FIPS 205 hedged variant: 16 bytes of opt_rand
    GetRandBytes(entropy.data(), entropy.size());
    const bool ok = SignWithEntropy(scheme, sk, msg, entropy, sig);
    memory_cleanse(entropy.data(), entropy.size());
    return ok;
}
```

Then:
- `sign.h:29-32`: "SLH-DSA: FIPS 205 pure, empty context, **hedged (16 bytes of opt_rand from the OS RNG)**. Falcon: randomized, 88 bytes …". Leave the `SignWithEntropy` comment as is (empty entropy = deterministic remains the test/vector mode).
- `src/crypto/pq/README.md`: the sentence describing wallet signing ("SLH-DSA deterministic") → hedged; note that the golden vectors are produced with explicit entropy and are unaffected.
- `docs/plans/yellowback-quantum-plan.md:213`: "SLH-DSA signatures are deterministic in the non-hedged mode (the node wallet signs hedged; vectors use explicit entropy) and Falcon's are randomized, so v4 txids remain malleable by the signer …" (the malleability conclusion is unchanged and if anything strengthened). Mirror in the quantum spec if it repeats the sentence (`grep -n deterministic docs/plans/yellowback-quantum-spec.md`), then `make spec` / `make spec-check`.
- `docs/mapping.md` §22: no new row needed (no impedance mismatch); mention in the PR.

**Why the vectors are unaffected.** `pq_vectors.json` stores `seed`, `msg` and an explicit `entropy` per entry (`""` for the SLH-DSA entries, 88 bytes for Falcon), and `pq_golden_vectors` (`src/test/pq_crypto_tests.cpp:607-618`) regenerates every signature through `BuildVectors()` → `pq::SignWithEntropy` with the file's entropy — never through `pq::Sign`. The ACVP deterministic cases (sigGen 157/161/162) likewise call `SignWithEntropy` with empty entropy and the hedged cases (474/475) with the file's `additionalRandomness`. The Falcon KAT does not touch SLH-DSA. Verification (`slh_verify`) recomputes the digest from the `R` carried in the signature, so every existing signature, vector and on-chain spend verifies exactly as before, and no vector file is regenerated. Clients (YEW, x402, lightwalletd) compare against the same files and are unaffected; YEW's own signer may stay deterministic or hedge independently — the node's verifier accepts both.

Consensus footprint: none (`sign.cpp` is wallet-only; `pq::Verify` untouched).

## 5. Tests

- `pq_crypto_tests.cpp:325-347` (`pq_round_trip_and_rejects`): the block at `:341-347` already asserts "the hedged variant differs and verifies" via `SignWithEntropy`. Check how `sig` at `:325-340` is produced: if it comes from `pq::Sign` and is compared to a deterministic expectation (equality with a second `Sign` or with `SignWithEntropy(…, {}, …)`), change that comparison to use `SignWithEntropy` with empty entropy for the deterministic expectation, and add: two `pq::Sign` calls on the same `(sk, msg)` give **different** SLH-DSA signatures that both verify (the hedging property), and `pq::Sign` output verifies under `pq::Verify` (already asserted for Falcon).
- `pq_wallet_tests.cpp` `pqpkh_sign_and_size` (`:212`) and `vault_owner_signer` (`:257`) go through `CPQKey::Sign` → `pq::Sign`; they assert verification and sizes, not bytes, so they pass unchanged. Confirm nothing in `src/test` or `qa/rpc-tests` compares an SLH-DSA signature produced by the wallet against a fixed hex (`grep -rn 'deterministic' qa/rpc-tests/test_framework/pq.py qa/rpc-tests/*pq*.py`); the pure-Python signer in `test_framework/pq.py` is used to *produce* owner signatures in some suites, never to predict the node's bytes.
- `pq_golden_vectors`, `pq_slhdsa_acvp` unchanged and passing is the regression proof that vectors are untouched.

## 6. Acceptance criteria

- `pq::Sign` for scheme 1 draws 16 bytes from `GetRandBytes`, passes them as `entropy`, cleanses them; two signatures of one message differ and both verify.
- `src/test/data/pq_vectors.json` and `pq_acvp_slhdsa.json` are byte-identical to `upgrade/vault` before the change (CI's cross-line vector `cmp` still passes).
- `sign.h`, `README.md`, quantum plan/spec sentence updated; `make spec-check` clean.
- Both lines identical in `src/crypto/pq`.

## 7. Risks and side effects

- None to consensus or to any client. Signatures become non-deterministic: anything that assumed "same key + same sighash ⇒ same scriptSig bytes" (e.g. a retry comparing bytes) would now see a different but valid signature — the node's sign-once records are keyed by sighash, not signature bytes, so set signing is unaffected; PQ owner spends are rebuilt on retry anyway.
- `GetRandBytes` aborts on RNG failure (baseline behaviour), same as the Falcon branch.

## 8. Effort estimate and dependencies

~30 minutes code + tests, ~30 minutes docs. No dependencies. Independent of 02/PQ-1/PQ-2 (different file) and 02/PQ-4.

## Completion record

- **Completed:** 2026-10-13T07:30Z
- **ycash-dd** merge b8d6fd141: 809efaf59. **ycash6** merge 32b5df099: 87502ca86. **Workspace** merge f6d18c6: a9ddc71 (plan §4.2 and spec Q5 sentences). Spec copies regenerated.
  - `pq::Sign` draws 16 bytes from `GetRandBytes` into `SignWithEntropy` and cleanses them afterwards.
- **Tests:** `pq_round_trip_and_rejects` asserts that two signatures differ and both verify; empty entropy stays deterministic. Vectors are unchanged; golden and ACVP pass. All §6 criteria met.
- **Follow-up:** YEW may hedge its own SLH-DSA signing independently.
