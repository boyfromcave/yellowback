# LOW — W3-N-9 — A stock (pre-upgrade) binary's `-salvagewallet` drops `pqkey`/`cpqkey` and every `vault*` record of a fork wallet: document it, and detect a keys-only salvage on the next fork load

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W3-N-9-stock-salvage` off `upgrade/vault` in each (after `MEDIUM-W3-07-NEW-1`): `src/wallet/walletdb.{h,cpp}` (a sentinel record), `src/wallet/wallet.cpp` (load-time detection → restore marker), `doc/vault-rpc.md` (sign-once section), `ycash6/doc/yellowback-release.md` and `ycash-dd/doc/release-notes.md`, `doc/yellowback-attestor.md`, `qa/rpc-tests/vault_pq_wallet_restore.py`. Wallet + docs only.
**Audit source.** Wave 3: `docs/audits/quantum-vault-ecosystem-wave3/07-node-rpc-mempool-durability-ci.md` W3-N-9 (lines 220-234); `docs/audits/quantum-vault-ecosystem-wave3/verification/07-verification.md` W3-N-9 (lines 192-200, "CONFIRMED — and wider … Confirmed Low for the stock-binary case; the fork-binary case is NEW-1"); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row W3-N-5..9. Wave 4: `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md` §1.5 row W3-N-9 (line 120, "STILL OPEN", Δ-free).
**Status:** pending — re-verified at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): open on both lines; `src/wallet/` unchanged since wave 3, so every source citation below stands.

## 1. Finding

Merely *opening* a fork `wallet.dat` with a stock v4.5.0 / 6.20.0 binary loses nothing: `ReadKeyValue` ignores unknown record types. But a stock binary's `-salvagewallet` runs `CWalletDB::Recover(..., fOnlyKeys = true)`, which keeps only its own `IsKeyType` rows (stock `origin/ycash-legacy:src/wallet/walletdb.cpp:947-955`, ending at `ckey`). It therefore drops the fork's `pqkey`/`cpqkey` (every post-quantum owner key not re-derivable from the seed: imported ones, `PQ_INDEX_NONE`) and every `vault*` record (`vaultsetsig`, `vaultsignrestored`, `vaultbuild`, `vaultrecipient`, `vaultpendingkey`) and `pqissued`. An operator who runs `-salvagewallet` with the wrong binary — plausible: the release line ships two binaries on two code lines, and an operator rolling back after a problem reaches for the stock one — loses PQ owner keys (funds in vaults owned by imported PQ keys become owner-unspendable; set paths still work) and the whole sign-once history. When the fork binary later opens the salvaged file, it sees member keys, no records and **no restore marker** (the marker row was dropped too), so the 07/NEW-1 hazard (sign a different spend of an already-signed outpoint → equivocation) is back, and `MEDIUM-W3-07-NEW-1`'s fix cannot help because the salvage happened outside the fork. `doc/vault-rpc.md:336-366` warns about restored wallets, not about salvage. Same for a `ycash6` wallet salvaged by a stock 6.20.0 binary.

## 2. Root cause

- A stock binary cannot know the fork's record types; its salvage is keys-only by design.
- The fork has no way to tell, on load, that a keys-only salvage happened elsewhere.

## 3. Fix options considered

1. **Documentation and release notes only.** Necessary; does not protect the operator who misses it.
2. **Make the stock binary refuse the file** (a `minversion` above stock). Does not help: the stock salvage runs `Recover` *before* `LoadWallet`'s version check, and `minversion` is not a key type, so it is dropped too. Rejected.
3. **A fork-only sentinel record, checked on load (recommended, with 1).** The fork writes `("vaultwalletformat") → 1` into every wallet it opens. The sentinel is deliberately **not** in any binary's `IsKeyType` (stock or fork), so every keys-only salvage — stock or fork — drops it. On load, the fork sees "keys present, sentinel absent": either a pre-fork wallet opened by the fork for the first time, or a wallet salvaged by keys only. Both are handled safely by setting the restore marker (a pre-fork wallet cannot hold a sign-once history anyway; the marker only gates `set_signunlock`/`set_signcancel`), then writing the sentinel.
4. **Detect via `hdseed` present ∧ `hdchain` absent** (every fork/Zcash seed is written with an `hdchain`, `src/wallet/wallet.cpp:3686-3705`, and `hdchain` is not a key type, so salvage drops it). Works on ycash-dd without a new record, but ycash6's mnemonic wallets keep `mnemonichdchain` as a key type (`ycash6/src/wallet/walletdb.cpp:1158`), so the heuristic differs per line and depends on stock internals. Rejected in favour of an explicit sentinel.

## 4. Recommended fix

1. **Sentinel (both lines).** `CWalletDB::WriteVaultWalletFormat()` / `ReadVaultWalletFormat()` (`"vaultwalletformat"`, a `uint8_t` 1). **Do not** add it to `IsKeyType` (comment why next to the list `MEDIUM-W3-07-NEW-1` extends).
2. **Load-time check (both lines)**, in the same place as `MEDIUM-W3-07-NEW-1`'s salvage marker (next to the startup warning, ycash-dd `wallet.cpp:7044`): if the wallet holds any key (`!mapKeys.empty() || !mapCryptedKeys.empty() || HaveHDSeed()`) and `!ReadVaultWalletFormat()` → `WriteVaultSignRestored()` and log `"vault: this wallet was created by another binary or salvaged keys-only (no vault-wallet sentinel): sign-once history may be missing; restore marker set"`; then (always) `WriteVaultWalletFormat()`. A brand-new wallet has no keys at that point → no marker, sentinel written.
3. **PQ keys.** Nothing re-derives imported PQ keys; the doc must say: "keep a dump (`z_exportwallet`, whose `pqseed=`/PQ key lines carry them) before any salvage; never salvage a fork wallet with a stock binary".
4. **Docs.** `doc/vault-rpc.md` sign-once section and the node's upgrade/release notes (`ycash6/doc/yellowback-release.md`, `ycash-dd/doc/release-notes.md`): "`-salvagewallet` must run with the fork binary of the same line; a salvage with a stock binary loses post-quantum keys and the sign-once history; the fork detects such a wallet on load and sets the restore marker". `doc/yellowback-attestor.md`: the same, in the member-key-host rules.

## 5. Tests

- **Functional `qa/rpc-tests/vault_pq_wallet_restore.py` (both lines):** simulate a stock salvage without a stock binary. The framework has no BDB writer, so add a regtest-only flag `-vaulttestdropvaultrecords` that erases the `vault*`, `pqissued` and `vaultwalletformat` rows at load, before the sentinel check runs (the state a stock keys-only salvage leaves). Stop node 1 (a member with one `vaultsetsig`), restart it with the flag. Assert: on restart `set_listsigned` → `restored: true`, and `set_signunlock` of a different build refuses `set-sign-restored`.
- **Upgrade path:** a wallet created by the pre-sentinel fork build (fixture wallet from `qa/rpc-tests/data/` if one exists, else created in-test by deleting only the sentinel) loads, gets the marker, gets the sentinel; a second restart does not set the marker again (if the operator cleared it).
- **Fresh wallet:** no marker after first start.

## 6. Acceptance criteria

- A fork wallet that lost its vault records to any keys-only salvage (stock or fork binary) is marked restored on the next fork load; a fresh wallet is not; both lines.
- Release notes and `doc/vault-rpc.md` warn against stock-binary salvage and say how to recover (dump before salvage; restore procedure).

## 7. Risks and side effects

- **One-time marker on upgrade:** every existing fork wallet that holds keys and predates the sentinel gets the restore marker once; a member operator must run `set_acknowledgerestore` after checking `set_listsigned` (the history is intact for an ordinary upgrade). Announce in the release notes; alternatively, write the sentinel without a marker when the wallet *does* hold `vaultsetsig` rows or `vaultbuild` rows (a sign it was never salvaged) — reviewer's choice; the conservative default is the marker.
- No consensus effect.

## 8. Effort estimate and dependencies

- 0.5 day code, 0.5 day tests (including the regtest-only helper), 0.25 day docs/release notes.
- Dependencies: after `MEDIUM-W3-07-NEW-1-ycash-salvagewallet-sign-once-records.md` (same code site, same marker).
