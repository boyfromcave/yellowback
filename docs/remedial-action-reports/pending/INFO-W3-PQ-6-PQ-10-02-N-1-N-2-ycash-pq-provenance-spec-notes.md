# INFO — W3-PQ-6, W3-PQ-7, W3-PQ-8, W3-PQ-9, W3-PQ-10, 02/N-1, 02/N-2 — PQ information items: machine-check the Falcon KAT provenance; spec corrections (stale draft rows, `SIGHASH_SINGLE` out of range on ZIP-243, no `FindAndDelete`, constant-time hash-to-point); key-cache and portability notes

**Repos / branches to change:** `ycash-dd` and `ycash6` (both; `src/crypto/pq` and the test framework files are byte-identical across lines), branch `fix/W3-PQ-info` off `upgrade/vault` in each. The workspace (`docs/plans/yellowback-quantum-spec.md`, `docs/mapping.md`) gets text. One new generator script, one new unit case and comments; no consensus behaviour change.
**Audit source:** `docs/audits/quantum-vault-ecosystem-wave3/02-post-quantum-crypto.md:147-193` (W3-PQ-6..10), `:244-248` (the sentence corrected by N-1); `docs/audits/quantum-vault-ecosystem-wave3/verification/02-verification.md:115-165` (W3-PQ-6..10 CONFIRMED, Info), `:277-293` (N-1, N-2); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:49`. Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:78-79` (W3-PQ-6..10, 02/N-1, 02/N-2 STILL OPEN, Δ-free); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`. The one ycash6 workflow citation (+8 after `:911`) is updated.
**Status:** pending

## 1. Finding

Seven information items from the PQ audit and its verification. None is a defect in consensus or wallet behaviour. Each is either a provenance check that is not automated yet, or a statement in a spec or audit that would mislead the next reviewer.

- **W3-PQ-6 (Falcon KAT provenance).** `src/test/data/pq_falcon_kat.json` records its source (`falcon-round3.zip`, sha256 `d625407d…`; PQClean's `nistkat-sha256` for the padded entry), but nothing re-derives the JSON from those sources. Neither auditor could fetch the zip (sandbox proxy 403). The keygen replay through the NIST AES-CTR DRBG is strong evidence that the file was not fabricated, but the derivation is not mechanised the way `gen_pq_wallet_vectors.py --check` mechanises the HKDF vector.
- **W3-PQ-7 (PQ keys not seed-portable across lines).** This is the same fact as W3-P-5, and **it is closed by LOW-W3-P-3-P-5-P-6-04-NEW-3** (docs, help text and release notes on both lines). Nothing further here.
- **W3-PQ-8 (per-unlock decrypted PQ key cache).** An unlocked encrypted wallet keeps every decrypted PQ secret in `mapDecryptedPQKeys` until `Lock()`. ECDSA keys are decrypted per call instead. The verifier traced the lifecycle: nothing is cached on a failed unlock, `Lock()` clears the cache together with `vMasterKey`, `GetPQKey` refuses while locked, and the memory comes from `secure_allocator`. The exposure class is unchanged (the master key is resident for the same interval); the footprint is larger (≈1.3 KB per Falcon key). The fix is optional.
- **W3-PQ-9 (stale spec rows).** `yellowback-quantum-spec.md:168-169` still lists `PQ_SIGOP_COST` "in `script.cpp` `GetSigOpCount`" and `Consensus::Params::pqFalconActive` as a `bool`. Rulings F-5 and R-A2 supersede both: the code has `GetPQSigOpCount` in `policy.cpp` and `pqFalconHeight`. Readability only.
- **W3-PQ-10 (constant-time vs variable-time hash-to-point).** Consensus verification uses `hash_to_point_ct` (717 draws, 205 spares for logn 9). The Python model and `fn-dsa` use rejection sampling. They disagree only when more than 205 of 717 draws are rejected (probability ≈ 2⁻²⁵⁶), and in that case consensus *rejects* a spec-valid signature. Nobody should "fix" one side.
- **02/N-1 (a correction to the audit text).** The first-wave report says, under "Sighash", "`SIGHASH_SINGLE` out of range throws → false". That holds only on the **pre-Overwinter** `SignatureHash` path, which a PQ input cannot reach (v4 only). On the ZIP-243 path that `OP_CHECKPQSIG` uses, a `SIGHASH_SINGLE` with `nIn ≥ vout.size()` leaves `hashOutputs` as the zero hash. The signature is then computed and verified over that preimage: ZIP-243's specified behaviour, identical to `OP_CHECKSIG`. No security effect, but the sentence must not be relied on.
- **02/N-2 (no `FindAndDelete` for PQ signatures), with a correction.** The verifier observed that `OP_CHECKPQSIG` does not strip the signature from `scriptCode` and contrasted this with `OP_CHECKSIG`, which it said "removes the signature (`:901`, `:959`)". **At the audited commits neither line calls `FindAndDelete` anywhere.** Zcash removed it: `grep -rn FindAndDelete src/script` is empty on both lines, and `src/test/data/tx_invalid.json:12-21` documents "Valid in Bitcoin because of FindAndDelete, but invalid for Zcash". So `OP_CHECKPQSIG` and `OP_CHECKSIG` treat `scriptCode` identically. The verifier's conclusion stands: a self-referential signature in a non-push-only scriptSig can never verify, which is a safe failure. Only the "unlike OP_CHECKSIG" framing is wrong, and the spec should say so in one sentence so nobody adds `FindAndDelete` "for symmetry".

## 2. Root cause

ycash-dd `da5e0fe` (ycash6 `0742e43` identical where noted):

- **PQ-6:** `src/test/data/pq_falcon_kat.json` (keys `comment`, `r3_source`, `r3` with 5 entries `{count, seed, msg, pk, sk, sm}`, `padded` with 1 entry, `r3_all` with 100 entries `{count, pk, msg, sig}`), identical on both lines. Consumed by `src/test/pq_crypto_tests.cpp:525-573` (keygen replay through the NIST DRBG, `sm` comparison). The pattern to follow is `qa/rpc-tests/test_framework/gen_pq_wallet_vectors.py --check`, run at `yellowback-tests.yml:690` (dd) / `:1155` (ycash6).
- **PQ-7:** see LOW-W3-P-3-P-5-P-6-04-NEW-3 §2.
- **PQ-8:** `src/wallet/crypter.cpp:222-233` (`Lock`), `:246-327` (`Unlock`, the cache filled at `:323-326`), `:488-511` (`GetPQKey`), `:476-485` (`AddCryptedPQKey`); identical PQ lines on ycash6.
- **PQ-9:** `docs/plans/yellowback-quantum-spec.md:168-169` (the draft table under "§0 Constants"; the rulings at the top of the file, `:1-156`, win). Code: `src/policy/policy.cpp:403` (`GetPQSigOpCount`), `src/consensus/params.h:258` (`pqFalconHeight`).
- **PQ-10:** `src/crypto/pq/falcon/ycash_falcon_verify.c:72-77` (`hash_to_point_ct` over nonce ‖ m), `ycash_falcon_sign.c:172-177` (the signer uses the same `_ct` variant); `falcon/common.c:93-111` (the `_ct` sampler with `overtab[9] = 205`); `qa/rpc-tests/test_framework/pq.py:457` (`_falcon_hash_to_point`, rejection sampling).
- **N-1:** `src/script/interpreter.cpp:1405-1411` (ZIP-243 branch: `SIGHASH_SINGLE && nIn < vout.size()` hashes the output, otherwise `hashOutputs` stays zero), `:1474-1480` (pre-Overwinter branch: `throw logic_error("no matching output for SIGHASH_SINGLE")`), `:1527-1549` (`CheckPQSig` catches `logic_error` → false, unreachable for v4); ycash6 `CheckPQSig` at `interpreter.cpp:1672`. `src/test/pq_script_tests.cpp:887-934` (`pq_hashtype_matrix_real`) covers `SIGHASH_SINGLE` only in range (input 0 of 2 outputs).
- **N-2:** `src/script/interpreter.cpp:905` (`OP_CHECKSIG` passes the whole `script` as `scriptCode`, no stripping), `:963` (`OP_CHECKMULTISIG`, same), `:1156` area (`OP_CHECKPQSIG` passes `script`), `:322` (`OP_CODESEPARATOR` disabled). `grep -rn FindAndDelete ycash-dd/src/script ycash6/src/script` finds nothing. `src/test/data/tx_invalid.json:12-21`.

## 3. Fix options considered

- **PQ-6:** (a) commit `falcon512-KAT.rsp` into the tree (~0.4 MB) and check against it offline; (b) fetch the zip in CI with its pinned sha256 and re-derive. (b) keeps the tree small and proves the link to the published artefact. (a) is the fallback if the host proves unreliable: commit the `.rsp` (sha256-pinned) under `src/test/data/upstream/`. Recommended: (b), nightly, with (a) as the fallback.
- **PQ-8:** (a) LRU / time-bounded eviction; (b) decrypt on demand like ECDSA, which costs a full `KeyGen` per signature, the cost LOW-02-PQ-4 (done) removed; (c) no change, documented. Recommended: (c). The verifier and the auditor both rate it optional, and (b) undoes a deliberate fix.
- **PQ-9 / PQ-10 / N-1 / N-2:** text and comments only. N-1 also gets a unit case that pins the ZIP-243 behaviour, so the corrected sentence has a test behind it.

## 4. Recommended fix

1. **PQ-6: `qa/rpc-tests/test_framework/gen_pq_falcon_kat.py` (new, byte-identical on both lines; add it to the MEDIUM-W3-P-2 manifest).**
   - `--check --zip PATH` (or `--fetch`, which downloads `https://falcon-sign.info/falcon-round3.zip` to a temp dir).
   - Verify the zip's sha256 equals `r3_source`'s recorded `d625407dbda9e5835f610aaeba1147e029988a6610e0107dfd292033138e1d47`, and refuse otherwise. Extract `KAT/falcon512-KAT.rsp` (the path the JSON's comment names). Parse the `count = / seed = / mlen = / msg = / pk = / sk = / smlen = / sm =` records.
   - Regenerate `r3` (the first 5 records, all six fields) and `r3_all` (all 100 as `{count, pk, msg, sig}`, with `sig` re-laid-out exactly as the JSON's comment describes: `sm = sig_len(2, BE) ‖ nonce(40) ‖ msg ‖ 0x29 ‖ compressed s`). Compare field by field with the committed JSON.
   - For `padded`: fetch PQClean's `crypto_sign/falcon-padded-512/META.yml` at the pin `0586a824…` (`https://raw.githubusercontent.com/PQClean/PQClean/<pin>/crypto_sign/falcon-padded-512/META.yml`). Check that its `nistkat-sha256` equals the value the JSON records. The `.rsp` itself is not in PQClean, which pins only its hash, so the `padded` entry stays anchored by the keygen replay plus this hash agreement.
   - Wire it into the **nightly** job of both lines (network access; never on push): `python3 qa/rpc-tests/test_framework/gen_pq_falcon_kat.py --check --fetch`. If `falcon-sign.info` is unreachable from GitHub runners, switch to fallback (a): commit the `.rsp` and run `--check --rsp src/test/data/upstream/falcon512-KAT.rsp` in the `python` job.
   - Document it in `src/crypto/pq/README.md` "Conformance data".
2. **PQ-7:** nothing here. LOW-W3-P-3-P-5-P-6-04-NEW-3 carries it.
3. **PQ-8:** one paragraph in `src/crypto/pq/README.md` (or `doc/yellowback-rpc.md`'s wallet section, both lines). It says that an unlocked encrypted wallet holds decrypted PQ keys (seed and sk, `secure_allocator`) until `walletlock` or the `walletpassphrase` timeout, that this is deliberate (LOW-02-PQ-4: one `KeyGen` per unlock, not per signature), and that operators who want a short exposure window should use short `walletpassphrase` timeouts. No code. If the owner later wants (a), it is a separate report.
4. **PQ-9:** in `docs/plans/yellowback-quantum-spec.md:168-169`, strike or annotate the two rows. Example: `PQ_SIGOP_COST` | 20 | ~~`script.cpp GetSigOpCount`~~ **superseded by F-5: policy only, `GetPQSigOpCount` in `src/policy/policy.cpp`**; and `pqFalconActive` → **superseded by R-A2: `Consensus::Params::pqFalconHeight` (`consensus/params.h`)**. Keep the rows, so history is not lost, but make the superseding obvious in the row itself.
5. **PQ-10:** a comment in `ycash_falcon_verify.c` above `:76` (Ycash-owned file; both lines identical):
   ```c
   /* Consensus uses the constant-time hash-to-point (717 draws, 205 spares for logn 9), as the signer does.
    * A rejection-sampling verifier (the Python model, fn-dsa) agrees except when > 205 of 717 draws are
    * rejected (probability ~2^-256), where this verifier rejects a signature the other accepts. Do not
    * change either side to "match" the other (audit W3-PQ-10). */
   ```
   Add the same sentence to `qa/rpc-tests/test_framework/pq.py` at `_falcon_hash_to_point` (`:457`) and one line to the quantum spec's Falcon section.
6. **N-1:**
   - **Spec sentence** in `yellowback-quantum-spec.md` §5.3 ("Checker hook"): "For v4 transactions the sighash is ZIP-243: `SIGHASH_SINGLE` with `nIn ≥ vout.size()` commits to a zero `hashOutputs` and verifies normally, exactly as `OP_CHECKSIG`; the pre-Overwinter `logic_error` throw is unreachable for PQ inputs (audit 02/N-1)."
   - **Unit case** `pq_sighash_single_out_of_range` in `src/test/pq_script_tests.cpp` (both lines; model it on `pq_hashtype_matrix_real` at `:887-934`): a Sapling v4 tx with 2 inputs and 1 output; sign input 1 with hashtype `SIGHASH_SINGLE` (0x03) and with `0x83`, for both schemes and for ECDSA as the reference. Assert `VerifyPQ(…) == SCRIPT_ERR_OK` under consensus and policy flags. Assert that `SignatureHash(spk, tx, 1, 0x03, amount, VAULT_BRANCH_ID)` equals the digest computed with a zero `hashOutputs`: recompute it by building the same tx with `vout` resized so that `nIn < vout.size()` is false. Alternatively, assert that changing the single output does **not** change the digest, which is the property that matters.
   - **Audit text:** add an erratum line to `docs/audits/quantum-vault-ecosystem-wave3/02-post-quantum-crypto.md` at `:246` ("Erratum (verification 02/N-1): on the ZIP-243 path an out-of-range `SIGHASH_SINGLE` hashes a zero `hashOutputs`; it does not throw"), if the audit owner allows edits to the audit file. Otherwise leave this report as the record.
7. **N-2:** spec sentence in §5.3: "Neither `OP_CHECKSIG` nor `OP_CHECKPQSIG` applies `FindAndDelete` (Zcash removed it; `src/test/data/tx_invalid.json`). A PQ signature that appears in its own `scriptCode` (only possible in a non-push-only scriptSig, already non-standard) can never verify. Do not add `FindAndDelete` (audit 02/N-2)." Add the same note as a comment in `CheckPQSig` (`interpreter.cpp:1527`, dd; `:1672`, ycash6). That is a comment-only change in a G-9 consensus file, so it goes through the review gate as a no-op diff. Alternatively, put the comment only in the spec, which avoids the gate; recommended unless the reviewers want it in code.
8. **Mapping:** `docs/mapping.md` §22: rows for the KAT generator (PQ-6) and for "no `FindAndDelete` on either Zcash-lineage line" (N-2).

## 5. Tests

- `gen_pq_falcon_kat.py --check` passes against the real zip (nightly, or locally with network access) and fails when one byte of the committed JSON's `r3_all[57].sig` is flipped (scratch, recorded).
- `pq_sighash_single_out_of_range` passes on both lines. It would have contradicted the first-wave sentence.
- Comment-only edits: build both lines; `diff -r src/crypto/pq` is still empty.

## 6. Acceptance criteria

- The KAT generator exists on both lines, is in the manifest, and runs in the nightly (or, if the fallback is taken, offline in the `python` job against a committed, sha256-pinned `.rsp`).
- The spec's `:168-169` rows are marked superseded. §5.3 carries the N-1 and N-2 sentences. The Falcon section carries the PQ-10 note.
- `ycash_falcon_verify.c` and `pq.py` carry the PQ-10 comment. `src/crypto/pq` and the test framework are identical across lines.
- `pq_sighash_single_out_of_range` runs on both lines.
- The PQ-8 note is in the docs. PQ-7 points to the LOW-W3-P-3 report.

## 7. Risks and side effects

- None to consensus or wallet behaviour.
- The KAT fetch depends on a third-party host; hence nightly-only, with the committed-`.rsp` fallback.
- A comment in `interpreter.cpp` (N-2) triggers the G-9 two-reviewer gate for a no-op. Prefer the spec-only option unless reviewers ask for the code comment.

## 8. Effort estimate and dependencies

- ~1 day total: KAT generator and nightly wiring (0.5), unit case (0.25), spec, comments and docs (0.25). One reviewer.
- Depends on MEDIUM-W3-P-2 for the manifest lines. W3-PQ-7 is delivered by LOW-W3-P-3-P-5-P-6-04-NEW-3. No other dependency.
