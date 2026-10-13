# LOW — W3-PQ-2 — Compile out the unused `malloc`/`exit(111)` SHAKE128/SHA3 contexts from the consensus `fips202.c` (local patch P4) and gate the verify objects' undefined symbols at link level

**Repos / branches to change:** `ycash-dd` and `ycash6` (both; `src/crypto/pq` is byte-identical and must stay so), new branch `fix/W3-PQ-2-fips202-p4` off `upgrade/vault` in each. Vendored C plus a shared `qa/` script. `fips202.c` is linked into `libzcash_script` (consensus library); the patch removes only code that nothing calls, so no consensus behaviour changes, but treat the PR as consensus-adjacent: two reviewers, the four-part check in the body.
**Audit source:** `docs/audits/quantum-vault-ecosystem-wave3/02-post-quantum-crypto.md:90-103` (W3-PQ-2), method `:39-42`; `docs/audits/quantum-vault-ecosystem-wave3/verification/02-verification.md:83-91` (CONFIRMED, Low: `nm -u fips202.o` gives `calloc exit free malloc`; the other verify objects reference none; no caller of `shake128*`/`sha3_*`/`shake256_absorb`/`shake256_squeezeblocks` outside `fips202.c`); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:49`. Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:74` (STILL OPEN, Δ-free: `fips202.c`); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`. ycash6's CI step shifts its `yellowback-tests.yml` by +8 lines after `:911`; the one ycash6 workflow citation is updated.
**Status:** pending

## 1. Finding

Local patch P1 (2026-10-10) made PQClean's **SHAKE256 incremental** context inline, so the only SHAKE API Falcon uses (`inner_shake256_*` → `shake256_inc_*`) neither allocates nor exits. The rest of PQClean's `fips202.c` is still compiled. That covers the SHAKE128 incremental and non-incremental contexts, the SHAKE256 non-incremental context, and SHA3-256/384/512 incremental. Each of these allocates with `malloc` and calls `exit(111)` when the allocation fails. `fips202.c` is in `PQ_VERIFY_SOURCES`, so it is linked into `libbitcoin_crypto` and `libzcash_script`. The verify objects' undefined-symbol list therefore contains `malloc`, `calloc`, `free` and `exit`.

Nothing calls those functions today: the verifier grepped the whole tree, and the README says so. The scenario is a future one. A new caller, perhaps a later Falcon/FN-DSA update that uses SHAKE128 for key expansion, or a fuzz harness that pulls a context in, would put an `exit(111)` behind attacker-sized input on a script-verification thread, and a failed allocation there terminates the node. More generally, the consensus PQ objects should carry a mechanically enforced property: no allocation and no process exit. Today the only enforcement is a README sentence. Low.

## 2. Root cause

ycash-dd `da5e0fe` (ycash6 `0742e43` identical):

- `src/crypto/pq/falcon/fips202.c` (922 lines):
  - static helpers used only by the non-incremental APIs: `keccak_absorb` `:337-381`, `keccak_squeezeblocks` `:383-415`;
  - SHAKE128 incremental with `malloc`/`exit(111)`/`free`: `:524-555`;
  - SHAKE256 incremental, patched by P1 and the only API in use: `:557-581`;
  - from `shake128_absorb` (`:583-594`) to the end of the file: SHAKE128/SHAKE256 non-incremental contexts, `shake128()`/`shake256()` one-shots, SHA3-256/384/512 incremental and one-shot, with `malloc`/`exit(111)` at `:595-597, 619-621, 643-645, 667-669, 742-744, 750-752, 803-805, 811-813, 864-866, 872-874` and `free` at `:554, 628, 676, 758, 823, 884`.
- `src/crypto/pq/falcon/fips202.h:15-40` (context typedefs; only `shake256incctx` is inline, `:27-33`) and the prototypes `:95-130`.
- `src/crypto/pq/falcon/inner.h:111-116`: `inner_shake256_*` map to `shake256_inc_*` only.
- `src/Makefile.am:385-406` (ycash-dd: `fips202.c` in `PQ_VERIFY_SOURCES`), `:440` (→ `libbitcoin_crypto`), `:691` (→ `libzcash_script`). ycash6: `src/Makefile.am:499-520` (`PQ_VERIFY_SOURCES`), `:554` (→ `crypto_libbitcoin_crypto_a_SOURCES`), `:863-865` (`libzcash_script_la_SOURCES = $(crypto_libbitcoin_crypto_a_SOURCES) …`).
- The other users of `fips202.c`: `qa/rpc-tests/test_framework/pq.py:527-529` compiles it into the optional Falcon signer (it uses only the Falcon entry points); no `src/test` file includes `fips202.h`.
- `src/crypto/pq/README.md:135-158` (P1; "The other contexts … still `malloc`; nothing in the node calls them").

## 3. Fix options considered

1. **Delete the unused functions from `fips202.c`.** Smallest object, but a large diff against upstream (~400 lines removed), which makes the provenance check ("patched files differ only by marked lines") harder to read.
2. **Wrap the unused regions in `#if 0 /* YCASH LOCAL PATCH P4 … */ … #endif`** (the audit's alternative). The upstream text stays byte-for-byte inside the guards; the diff is a handful of marked lines; the provenance check stays mechanical. **Recommended.** Keep the prototypes in `fips202.h` so the header remains upstream-shaped. A future caller then gets an *undefined reference* at link time, which is exactly the loud failure wanted, and the README says what to do.
3. **Patch every remaining context inline as P1 did.** That keeps dead code alive and maintained for no caller. Rejected.
4. **Only the `nm` gate, no source change.** It would fail today, since `fips202.o` references `malloc`/`exit`, unless it allow-lists them, and an allow-list defeats the purpose. Rejected as stand-alone; the gate comes with option 2.

## 4. Recommended fix

Both lines, identical bytes (patch ycash-dd, copy `fips202.c` and the README to ycash6, confirm `diff -r src/crypto/pq` is empty).

1. **`src/crypto/pq/falcon/fips202.c`, local patch P4.** Three guarded regions, each opened and closed by marked lines:
   ```c
   #if 0 /* YCASH LOCAL PATCH P4 (src/crypto/pq/README.md, "Local patches"): unused non-incremental
          * Keccak helpers; only the SHAKE256 incremental API (P1) is compiled. */
   ... keccak_absorb, keccak_squeezeblocks (:337-415) ...
   #endif /* YCASH LOCAL PATCH P4 */
   ```
   - Region 1 is `keccak_absorb` and `keccak_squeezeblocks` (`:337-415`), whose only callers are in region 3. Leaving them compiled would make `-Wunused-function` fire under `--enable-werror`.
   - Region 2 is the SHAKE128 incremental API (`:524-555`).
   - Region 3 runs from the `shake128_absorb` comment block (`:583`) to the end of the file (`:922`).

   **Keep compiled:** `load64`/`store64`, the round constants, `KeccakF1600_StatePermute`, `keccak_inc_init/absorb/finalize/squeeze`, and `shake256_inc_*` (P1). Check after the edit that every remaining `static` function is used (`-Wunused-function` clean), and that `#include <stdlib.h>` (`:10`) is still needed. If it is not, guard the include with a P4 marker too; it is harmless either way.
2. **`src/crypto/pq/falcon/fips202.h`:** unchanged (prototypes stay; upstream shape). Optionally add one marked comment above the non-incremental prototypes: "compiled out by P4; a caller fails to link".
3. **`src/crypto/pq/README.md`:** add "### P4: `falcon/fips202.c`, unused SHAKE128 / SHAKE256-non-incremental / SHA3 compiled out (date)". It covers the regions, why (no allocation and no `exit` in the consensus PQ objects; audit W3-PQ-2), that the guarded text is upstream byte-for-byte, and what a future caller must do: either remove the guard and patch the context inline as P1 did, or not use it. Update the P1 paragraph's last sentence ("still `malloc`; nothing calls them" becomes "compiled out by P4"). The provenance rule becomes: `diff` of `fips202.c` against upstream shows only P1 and P4 marked lines.
4. **Link-time gate: `qa/yellowback-pq-link-check.sh` (new, byte-identical on both lines; add it to the MEDIUM-W3-P-2 manifest).** It needs no node build, only `cc` and `nm`, so it runs in the dd `audit` job and in a ycash6 job that has a compiler. Steps:
   - Compile each verify-path translation unit standalone, as the auditors did: `cc -std=c99 -O2 -c -I src/crypto/pq/falcon -I src/crypto/pq/slhdsa <file> -o $tmp/<name>.o`. The files are `falcon/{fips202,vrfy,codec,common,ycash_falcon_verify}.c` and `slhdsa/{slh_dsa,slh_sha2,sha2_256,sha2_512}.c`; read the exact list from `PQ_VERIFY_SOURCES` in `src/Makefile.am` (the `.c` entries), so the gate follows the build.
   - Run `nm -u` on each. Fail if any undefined symbol matches `^_?(malloc|calloc|realloc|free|exit|_exit|_Exit|abort|atexit|printf|fprintf|puts|fputs|perror|getenv|rand|srand|random|time|clock|gettimeofday)$`. Allowed: `memcpy|memset|memmove|memcmp|__stack_chk_fail|__memcpy_chk|__memset_chk` and symbols defined by another object in the set. Print the offending object and symbol.
   - Also fail if a floating-point instruction appears in `objdump -d` of the Falcon verify objects (`vrfy.o codec.o common.o ycash_falcon_verify.o fips202.o`) on x86-64 (`grep -E '\b(v?(add|sub|mul|div)s[sd]|cvt|fld|fadd|fmul|fdiv)\b'`). This re-checks the README's "no floating point in verification" claim (both auditors did it by hand); skip with a message on a non-x86-64 runner.
   - Wire it: ycash-dd `qa/yellowback-audit.sh` gets a new blocking leg `leg_pq_link` ("PQ verify objects: no allocation, no exit, no floating point (audit W3-PQ-2)") calling the script. The `audit` job installs `gcc` if it does not already have it (the `python` job installs `gcc libc6-dev` at `yellowback-tests.yml:636-639`; copy that step). ycash6: a step in the `python` job after its compiler install (`:1084`).
5. **Mapping:** `docs/mapping.md` §22 row: "PQClean `fips202.c` mallocs/exits in unused contexts → P4 compiles them out; `qa/yellowback-pq-link-check.sh` enforces no alloc/exit/FP in the verify objects".

**Four-part check (PR body):** PQClean provides SHAKE/SHA3 in `common/fips202.c` with heap contexts and `exit(111)` on allocation failure (M). Ycash links that file into its consensus library but uses only the SHAKE256 incremental API (P1-patched). The adaptation (W) compiles out the unused APIs and enforces the property at link level. Tier: no rule change. Verify outputs are byte-identical (the compiled code that remains is unchanged).

## 5. Tests

- **Output unchanged:** `pq_crypto_tests` (`pq_golden_vectors`, `pq_falcon_kat` with all 100 `r3_all` entries, `pq_slhdsa_acvp`, `pq_round_trip_and_rejects`, `pq_falcon_padding_is_canonical`), `pq_script_tests` and `pq_wallet_tests` pass unchanged on both lines. So do `qa/rpc-tests/test_framework/test_pq.py` (its Falcon signer compiles `fips202.c`) and the `vault_pq*` / `yellowback_pq*` functional scripts.
- **The gate fails before P4 and passes after:** run `qa/yellowback-pq-link-check.sh` on the pre-patch tree. It must fail on `fips202.o: malloc, calloc, free, exit`. Record the output in the PR. After P4 it passes.
- **Build with `--enable-werror`** on both lines (or with `-Wunused-function -Werror` on the PQ objects) to prove no orphaned static helper remains.
- **Provenance:** `diff` of the patched `fips202.c` against PQClean `0586a824…/common/fips202.c` shows only lines containing `YCASH LOCAL PATCH` (P1 or P4) plus the guarded text's unchanged context. If LOW-W3-PQ-4's `qa/yellowback-pq-provenance.sh` exists, its pin mode must pass.

## 6. Acceptance criteria

- `fips202.c` compiles only the Keccak core, the incremental helpers and `shake256_inc_*`. Every added line carries `YCASH LOCAL PATCH P4`, or `P1` where unchanged.
- `nm -u` of every `PQ_VERIFY_SOURCES` object shows no allocation, exit or stdio symbol. `qa/yellowback-pq-link-check.sh` enforces it in CI on both lines, and it failed on the pre-patch tree (recorded).
- All `pq_*` unit suites, `test_pq.py` and the PQ functional scripts pass unchanged. `src/crypto/pq` is identical across lines.
- README P4 section added and P1's sentence updated. Mapping row added. The script is in the cross-line manifest.

## 7. Risks and side effects

- None to consensus outputs: the remaining code is untouched and the vectors replay byte-identically.
- A future change that needs SHAKE128/SHA3, e.g. if FIPS 206 FN-DSA final or an updated Falcon needs it, fails to link. That is intended. The README's P4 section tells the developer to patch that context inline (as P1 did) and to keep the gate green.
- The FP scan is x86-64 specific. It is skipped elsewhere with a message, so it cannot fail spuriously on arm64 runners (the README's arm64 claim stays manual).

## 8. Effort estimate and dependencies

- ~0.5 day (patch and README 2 h; the gate script and two wirings 2 h; Werror build and evidence 1 h). Two reviewers (vendored file in the consensus library).
- Coordinate with LOW-W3-PQ-4 (provenance script: knows about P4) and MEDIUM-W3-P-2 (manifest line for the new script). Independent of LOW-W3-PQ-1 (different file).
