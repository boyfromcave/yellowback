# MEDIUM — 07/NEW-1 — The fork's own `-salvagewallet` drops every `vault*` record and `pqissued` and sets no restore marker: keep the records, and fail closed after any salvage

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W3-07-NEW-1-salvage-sign-once` off `upgrade/vault` in each: `src/wallet/walletdb.cpp` (`IsKeyType`), `src/wallet/wallet.cpp` (`CWallet::Verify`, the load path that already logs the restore warning), `src/wallet/wallet.h` (a salvage flag), `doc/vault-rpc.md` (sign-once section), `doc/yellowback-attestor.md` ("Member-key hosts"), `qa/rpc-tests/vault_pq_wallet_restore.py`. Wallet only — no consensus file.
**Audit source.** Wave 3: `docs/audits/quantum-vault-ecosystem-wave3/verification/07-verification.md` NEW-1 (lines 226-249, "Medium — the fork's own `-salvagewallet` wipes the sign-once guard without a marker") and W3-N-9 (lines 192-200, "CONFIRMED, and wider than stated"); `docs/audits/quantum-vault-ecosystem-wave3/07-node-rpc-mempool-durability-ci.md` W3-N-9 (lines 220-234, the stock-binary half, handled in `LOW-W3-N-9-ycash-stock-binary-salvage.md`); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row 07/NEW-1 and remediation priority 3 ("add vault records to `IsKeyType` or set the restore marker after salvage"). Wave 4: `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md` §1.5 row 07/NEW-1 (line 124, "STILL OPEN", Δ-free).
**Status:** pending — re-verified at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): open on both lines; `src/wallet/` unchanged since wave 3, so every source citation below stands.

## 1. Finding

`-salvagewallet` calls `CWalletDB::Recover(bitdb, walletFile, true)` (`ycash-dd/src/wallet/wallet.cpp:1274-1279`), which re-reads every salvageable row and, with `fOnlyKeys = true`, **keeps only rows whose type `IsKeyType` accepts** (`src/wallet/walletdb.cpp:1449-1461`). The fork's `IsKeyType` (`walletdb.cpp:1029-1038`) added `pqkey`/`cpqkey` and nothing else, so the fork binary's salvage drops `vaultsetsig` (the sign-once records, `:1524`), `vaultsignrestored` (the restore marker itself, `:1580`), `vaultbuild` (`:1598`), `vaultpendingkey` (`:1610`), `vaultrecipient` (`:1622`) and `pqissued` (`:155`). Nothing then sets the marker: it is written only by a seed restore (`wallet.cpp:6953-6956`), a member-key import, and a pending imported key's later `SET_JOIN` (`:7713-7739`). The salvaged wallet keeps its `key` records, so it still holds the member key, has an empty sign-once history and no marker — `set_signunlock` will sign a *different* spend of an outpoint the key already signed, and anyone can submit `set_equivocation` → `MEMBER_EJECTED`, bond frozen (`src/vault/state.cpp:845-870`). That is exactly the state 07/F-5 and `doc/vault-rpc.md:336-366` say must never arise, reached through a documented stock option that an operator uses precisely when the wallet is damaged.

Secondary losses: `vaultbuild` — remembered builds forgotten, so `vault_buildunlock` can build a second, different unlock of a vault this wallet already signed (and with the record also gone, nothing refuses the second signature); `vaultrecipient` — intent recipients forgotten (`vault_release` needs them); `pqissued` — recoverable through the 20-key lookahead (`wallet.h:1023`). Note: the automatic path, `bitdb.Verify(walletFile, CWalletDB::Recover)` → `RECOVER_OK` (`wallet.cpp:1282-1290`), uses the two-argument `Recover` (`walletdb.cpp:1481-1484`, all record types), so it keeps vault rows that survived — but a BDB salvage of a damaged file can lose **any** row, so it too must fail closed. Same on `ycash6` (`IsKeyType` `src/wallet/walletdb.cpp:1153-1164`, which also keeps `mnemonicphrase`/`mnemonichdchain`; salvage `src/wallet/wallet.cpp:2131-2135`, verify `:2140`; markers `:3110`, `:3129`, `:7966`).

## 2. Root cause

- `src/wallet/walletdb.cpp:1029-1038` (ycash6 `:1153-1164`) — the key-type list does not include the vault records whose loss is unsafe.
- `src/wallet/wallet.cpp:1274-1290` (ycash6 `:2131-2147`) — neither salvage path records that a salvage happened; the load path (`:7044`, the startup warning) cannot know.
- The sign-once guard is "fail open on absence": no record = may sign (by design for a fresh key, wrong for a wallet that lost its records).

## 3. Fix options considered

1. **Keep the records (extend `IsKeyType`).** Necessary for the common case (a keys-only salvage of a mostly healthy file); not sufficient (a damaged file can lose them anyway).
2. **Set the restore marker after any salvage (fail closed).** Sufficient on its own for the equivocation risk: the sign RPCs refuse every prevout without a record until the operator imports the history (`set_importsigned`, a dump) or acknowledges (`set_acknowledgerestore`, `{"acknowledgerestore": true}`) — the 07/F-5 machinery. Cheap.
3. **Both (recommended).** (1) keeps the history usable; (2) makes any loss safe.
4. **Keep a second copy of the sign-once records outside `wallet.dat`.** Multiplies the restore story (which copy is authoritative, how is it backed up), and the 07/F-5 decision was "the record lives in `wallet.dat`; one wallet per key". Rejected.

## 4. Recommended fix

1. **`IsKeyType` (both lines).** Add `"vaultsetsig"`, `"vaultsignrestored"`, `"vaultbuild"`, `"vaultpendingkey"`, `"vaultrecipient"`, `"pqissued"`, and — if `MEDIUM-W3-N-1` has landed — `"vaultfeein"`. Comment: "records whose loss is unsafe (07/NEW-1): the sign-once history and its marker are key material in the sense that matters". Check that `ReadKeyValue` on the dummy wallet in `Recover` (`walletdb.cpp:1449-1458`) returns `fReadOK` for each (it does for the types it parses — `vaultbuild`, `vaultpendingkey`, `vaultrecipient`, `pqissued` — and falls through to success for `vaultsetsig`/`vaultsignrestored`, which `ReadKeyValue` does not parse; confirm with the unit test below).
2. **Salvage flag.** In `CWallet::Verify` (`wallet.cpp:1265-1300`), set a file-scope `static bool g_walletSalvaged` when `-salvagewallet` ran `Recover(..., true)` successfully **or** `bitdb.Verify` returned `RECOVER_OK`.
3. **Marker after salvage.** In the wallet load path, next to the existing startup warning (`wallet.cpp:7044`; ycash6 the equivalent block), if `g_walletSalvaged`: `CWalletDB(walletFile).WriteVaultSignRestored()` unconditionally (a non-member wallet is unaffected: the marker only gates `set_signunlock`/`set_signcancel`, which have nothing to sign without a member key) and log `"vault: the wallet was salvaged; set sign-once history may be incomplete: restore marker set (set_signunlock / set_signcancel refuse until set_importsigned of the pre-salvage history and set_acknowledgerestore)"`. If the write fails, `UIError` and refuse to start (as `-hdseedfile` does at `:6955`).
4. **Remembered builds.** After salvage, `vaultbuild` rows that survived are re-loaded and their coins re-locked (existing `LoadVaultBuild`); nothing else changes.
5. **Docs (both lines).** `doc/vault-rpc.md` sign-once section (`:336-366`): add `-salvagewallet` (and an automatic "data salvaged" recovery) to the list of events that set the restore marker; the operator procedure is the restore procedure (`set_listsigned` on a backup or a dump taken before the damage → `set_importsigned` → check → `set_acknowledgerestore`); the original file is kept as `wallet.<timestamp>.bak` by the salvage and can be dumped by a fork binary to recover the records. `doc/yellowback-attestor.md` "Member-key hosts": same rule. Cross-reference `LOW-W3-N-9` for a salvage run by the wrong (stock) binary.

## 5. Tests

- **Functional `qa/rpc-tests/vault_pq_wallet_restore.py` (both lines) — would have caught it:** node 1 (a member) signs an unlock (one `vaultsetsig`), remembers a build, has one `vaultrecipient`; `stop_node`, restart with `-salvagewallet`: `set_listsigned` shows the record (option 1) **and** `restored: true` (option 2); `set_signunlock` of a *different* build of the same prevout → `set-sign-once`; of a fresh prevout → `set-sign-restored` until `set_acknowledgerestore`; `vault_buildunlock` returns the remembered build; `vault_release` still finds the recipient.
- **Simulated loss:** delete the `vaultsetsig` row with a test-only helper (or start from a wallet whose records were never written — copy the key into a fresh wallet with `importprivkey` *while the key is not yet a member*, then `-salvagewallet`) and assert `restored: true` and the refusal.
- **Automatic path:** if the test framework can corrupt a page reproducibly (the stock `wallet.py`-style corruption helpers), assert the marker after a "data salvaged" start; otherwise unit-test `CWallet::Verify`'s flag setting.
- **Unit `src/wallet/test/wallet_tests.cpp` (or a new `vault_walletdb_tests.cpp`):** a BDB file with each vault record type → `Recover(..., true)` → every row present.

## 6. Acceptance criteria

- After `-salvagewallet` (or an automatic salvage) on either node line, every surviving `vault*` and `pqissued` row is kept, the restore marker is set, and `set_signunlock`/`set_signcancel` refuse any prevout without a record until the operator imports and acknowledges.
- `doc/vault-rpc.md` lists salvage among the marker-setting events on both lines; the new restore test passes on both lines.

## 7. Risks and side effects

- **No consensus effect.** Fails closed: a salvaged member wallet cannot sign set spends until the operator acts — the intended direction (a refused signature is recoverable; a frozen bond is not).
- **Wallet compatibility:** `IsKeyType` affects only salvage; older fork binaries keep salvaging as before (and lose the rows — `LOW-W3-N-9`'s sentinel detects that on the next fork load).

## 8. Effort estimate and dependencies

- Code: 0.5 day. Tests: 0.75 day. Docs + ycash6: 0.25 day.
- Dependencies: builds on the done `MEDIUM-07-F-5` (marker, `set_importsigned`, `set_acknowledgerestore`). Include `vaultfeein` if `MEDIUM-W3-N-1-07-NEW-2` lands first. `LOW-W3-N-9-ycash-stock-binary-salvage.md` follows this report.
