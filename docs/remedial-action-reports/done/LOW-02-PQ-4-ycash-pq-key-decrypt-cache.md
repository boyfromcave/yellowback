# LOW — 02/PQ-4 (+ verification N-2) — Cache decrypted PQ keys per unlock instead of re-running keygen on every `GetPQKey`

**Repos / branches to change:** `ycash-dd` (`src/wallet/crypter.{h,cpp}`, tests) and `ycash6` (same files, 6.20.0 line numbers below), branch `fix/02-PQ-4-pq-key-cache` off `upgrade/vault` in each.
**Audit source:** `02-post-quantum-crypto.md` §PQ-4 (`:105-118`); `verification/02-verification.md` §2.1 row PQ-4 (`:51`, "sharpened": every `GetPQKey` pays it), §3 N-2 (`:98-103`), keygen timings §1 (87 ms SLH-DSA, 12 ms Falcon at `-O2`).
**Status:** done — completed 2026-10-13T07:30Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13; nightly tier pending the owner's dispatch)

## 1. Finding

On an encrypted wallet every `CCryptoKeyStore::GetPQKey` decrypts the 48-byte seed and reconstructs the key pair with a full `pq::KeyGen` (`CPQKey::Set`), then checks the stored `pk` and id. SLH-DSA-SHA2-128s keygen computes a 2^9-leaf XMSS root — the verifier measured **87 ms per key** (Falcon-512: 12 ms). Nothing caches the result, so the cost is paid on every PQ signature (`CreatePQSig` → `GetPQKey`, i.e. per input signed), on every `dumpwallet` / `z_exportwallet` line, on every `IsOwnPQKey` scan (`SeedPQIssued` on a wallet without the `pqissued` record decrypts every PQ key it holds), and on unlock (one key when `fDecryptionThoroughlyChecked`, all keys the first time).

Usability / self-DoS only: a vault owner redeem with a few SLH-DSA inputs spends hundreds of milliseconds inside `cs_wallet`; a legacy encrypted wallet with dozens of PQ keys spends seconds on first unlock; RPC timeouts follow. Not a security defect — the keygen-on-load design is what makes the stored `pk` checkable, and the plaintext never leaves `secure_allocator` memory. Verifier confirmed, Low.

## 2. Root cause

ycash-dd `055d9c2`:
- `src/wallet/crypter.cpp:164-176` `DecryptPQKey`: `DecryptSecret` + `CPQKey::Set` (= `pq::KeyGen`, `src/pqkey.cpp:17-33`) + `GetID()/PubKey()` check.
- `src/wallet/crypter.cpp:479-489` `CCryptoKeyStore::GetPQKey`: on a crypted store, `DecryptPQKey` on every call; no decrypted map exists (contrast `mapPQKeys` for the plain store, `keystore.h:111,135`).
- `src/wallet/crypter.cpp:269-279` `Unlock` loop over `mapCryptedPQKeys` (breaks after one on `fDecryptionThoroughlyChecked`).
- Callers paying per call: `src/script/sign.cpp:46-47` (`CreatePQSig`), `src/wallet/rpcdump.cpp:909-918` (per `pqseed=` line), `src/wallet/wallet.cpp:443-458` (`SeedPQIssued`: `GetPQKey` for every PQ key when `pqissued` is absent), `:453`/`:539` (`IsOwnPQKey`). `TopUpPQKeys` (`:488-520`) itself uses the cheap `GetPQKeyInfo` for the `held` set and derives new keys from the HD seed (unavoidable keygen, 20 lookahead per scheme, `wallet.h:1023`).
- ycash6 `e866c45`: `src/wallet/crypter.cpp:194` (`DecryptPQKey`), `:310` (unlock loop), `GetPQKey` likewise; `rpcdump.cpp:880` (`z_exportwallet`).

## 3. Fix options considered

1. **Eager decrypt-all on `Unlock`** into a cache: simplest, but makes unlock O(keys × 87 ms) for every wallet, the very hang the finding describes. Rejected.
2. **Store-only check on load** (verify `pk`/`keyhash` by SHA-256, defer `KeyGen` to the first `Sign`): removes the keygen from `GetPQKey` callers that only need `pk`/index (`dumpwallet`, `IsOwnPQKey` via `Seed()`), but requires a "seed-without-sk" `CPQKey` state and touches `CPQKey`, walletdb load (`walletdb.cpp:926-931`) and every `IsValid()` user. Larger change; keep as a follow-up if (3) is not enough.
3. **Lazy per-unlock cache in `CCryptoKeyStore`** (first-wave fix, verifier-endorsed): decrypt on first `GetPQKey` after unlock, keep the `CPQKey` in a secure map, clear on `Lock()`. Unlock stays as it is. **Recommended.**

## 4. Recommended fix

Both lines (same logic; line numbers differ):

1. `src/wallet/crypter.h` (`CCryptoKeyStore`, near `mapCryptedPQKeys` `:137`): add `mutable PQKeyMap mapDecryptedPQKeys;` (the existing `std::map<CPQKeyID, CPQKey>`; `CPQKey` already holds `seed`/`sk` in `secure_allocator` vectors, `pqkey.h:29-35`) with a comment: "decrypted PQ keys of this unlock (keygen is ~90 ms per SLH-DSA key); filled lazily by GetPQKey, cleared by Lock()".
2. `crypter.cpp` `GetPQKey` (`:479-489`): under `cs_KeyStore`, look up `mapDecryptedPQKeys` first; on a miss, `DecryptPQKey` as today and, on success, insert before returning. Keep the `mapCryptedPQKeys` membership check first so an unknown id still returns false without touching the cache.
3. `crypter.cpp` `Lock()` (`:223-234`): inside the `cs_KeyStore` block, `mapDecryptedPQKeys.clear()` right after `vMasterKey.clear()`. (`std::map::clear` destroys the `CPQKey`s; their secure vectors are wiped by `secure_allocator` on free.)
4. `AddCryptedPQKey` / `AddPQKey` on a crypted store (`crypter.h:207-208`, `crypter.cpp`): if a key is re-added while unlocked, erase any cached entry for its id (or insert the fresh key), so the cache can never hold a key that no longer matches the stored record. `EncryptKeys` (`crypter.cpp:217`) runs on a plain store, so the cache is empty there; add an `assert(mapDecryptedPQKeys.empty())` for clarity.
5. Optional, same PR: `Unlock`'s PQ loop (`:269-279`) already decrypts one key on a thoroughly-checked wallet — insert that decrypted key into the cache instead of dropping it (one free hit).
6. `SeedPQIssued` (`wallet.cpp:443-458`): unchanged in code; with the cache its one-time scan on a legacy wallet is still O(keys × keygen) once per process. Note in `doc/vault-rpc.md` or `doc/yellowback.md` ("first unlock of a wallet created before the lookahead record derives every PQ key once").

Consensus footprint: none. Memory: ≤ (20 lookahead × 2 schemes + used keys) × (48 + 1,281 + 897 bytes) — tens of KB.

## 5. Tests

- `src/test/pq_wallet_tests.cpp` `crypto_keystore` (`:181-210`): add (a) after `Unlock`, two `GetPQKey` calls return equal keys and the second is served from the cache (expose a test-only `size_t DecryptedPQKeyCount() const` under `#ifdef`-free but documented "test accessor", or check via the test subclass at `:67-72` which already wraps `CCryptoKeyStore`); (b) after `Lock()`, `GetPQKey` fails and the cache count is 0; (c) `Unlock` with the wrong master key (`:207`) leaves the cache empty; (d) adding a key while unlocked then `GetPQKey` returns the new key.
- Timing (not a CI assertion): extend `pq_timings` (`pq_crypto_tests`) or a `BOOST_TEST_MESSAGE` in the new case printing the second `GetPQKey` wall time, for the PR record.
- Functional (both lines): `qa/rpc-tests/vault_pq_wallet.py` / `wallet_pq_address.py` already `encryptwallet` + `walletpassphrase`; add a step that signs two owner spends and runs `dumpwallet` (`z_exportwallet` on ycash6) after unlock and asserts every PQ address is listed — proves the cache does not drop keys — and then `walletlock` followed by a signing RPC that must fail with the locked-wallet error (proves the cache is cleared).

## 6. Acceptance criteria

- On an encrypted, unlocked wallet, the second and later `GetPQKey(id)` calls perform no `pq::KeyGen` (reviewer traces the code; the unit test's count assertion proves the cache path).
- `Lock()` clears the cache; a locked wallet cannot sign or export PQ keys (existing `EnsureWalletIsUnlocked` gates stay, `rpcdump.cpp:833`).
- No plaintext key is written to disk and no behaviour change for an unencrypted wallet.
- All `pq_wallet_tests`, `vault_pq_wallet.py`, `wallet_pq_address.py`, `vault_pq_wallet_restore.py` pass on both lines.

## 7. Risks and side effects

- A cached key must never outlive the master key: the `Lock()` clear is the whole security argument; a reviewer checks every path that clears `vMasterKey` (only `Lock()` in v4.5.0 / 6.20.0).
- If `AddCryptedPQKey` replaces a record for an existing id (re-import), a stale cache entry would sign with the old key: step 4 covers it.
- No change to the wallet file format, no `VAULT_DB_VERSION` or wallet version bump.

## 8. Effort estimate and dependencies

~2–3 hours per line including tests (ycash6 line numbers differ; logic identical). No dependencies; independent of 02/PQ-1..PQ-3.

## Completion record

- **Completed:** 2026-10-13T07:30Z
- **ycash-dd** merge b8d6fd141: 60a06b892, 182cb58e0. **ycash6** merge 32b5df099: 094868d1b, cf055898d.
  - `mapDecryptedPQKeys` is filled lazily by `GetPQKey` and cleared in `Lock()` right after `vMasterKey`; `AddCryptedPQKey` erases a stale entry.
  - The optional Unlock reuse (step 5) is taken.
- **Tests:**
  - unit case `crypto_keystore_decrypt_cache`, whose decrypt counts prove a cache hit does no keygen;
  - `vault_pq_wallet.py` on both lines: two spends of one key, the export lists every key, a locked wallet refuses, a re-unlock signs again.
  - All §6 criteria met.
