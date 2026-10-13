# MEDIUM — 07/F-5 — The set sign-once record lives only in `wallet.dat`: a seed restore or a second host can equivocate. Document, export/import the record, warn at restore time

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/07-F-5-sign-once-restore` off `upgrade/vault` in each: `doc/vault-rpc.md` (must), `doc/yellowback-attestor.md` (must), `src/wallet/rpcdump.cpp` + `src/wallet/walletdb.{h,cpp}` + `src/rpc/vault.cpp` (optional code: export/import of the record, a restore marker, a read RPC), `qa/rpc-tests/vault_pq_wallet_restore.py`. Wallet/RPC/doc only — no consensus, no review gate leg beyond the normal review. Cross-reference: `hawkeye` R7 runbook (05/M-3) for the sidecar's own mirror.
**Audit source.** `07-node-rpc-mempool-durability-ci.md` F-5; `verification/07-verification.md` F-5 ("CONFIRMED, Medium — `vaultsetsig` lives only in `wallet.dat`; the restore suite has no sign-once case; the doc is silent on restores"), N-2; `00-consolidated.md` row 07/F-5, remediation R7 (last sentence).
**Status:** done — completed 2026-10-13T11:21Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13; nightly tier pending the owner's dispatch)

## 1. Finding

`SignSetInPlace` (`ycash-dd/src/rpc/vault.cpp:1438-1512`) is the only guard between a member key and a provable equivocation: before signing it reads `vaultsetsig` for `(setId, prevout)` and refuses a different `(role, sighash)` (`:1459-1476`), and writes the record before the first signature (`:1480-1486`). The record is a plain wallet-DB entry (`src/wallet/walletdb.cpp:1498-1511`, key `("vaultsetsig", (setId, prevout))` → `(role, sighash)`); nothing derives it from the chain or the mempool, and `dumpwallet`/`z_exportwallet` (`src/wallet/rpcdump.cpp:876-923`) do not export it. A member key restored from its seed on another machine (`-hdseedfile`, `src/wallet/wallet.cpp:6914-6950`; `vault_pq_wallet_restore.py` exercises exactly this for PQ keys), an `importwallet`/`z_importwallet`/`importprivkey` of the member key, or an HA pair sharing a seed, carries **no record**: asked to sign a different unlock or cancel of the same prevout it signs, and anyone submits `set_equivocation` → `MEMBER_EJECTED`, bond frozen (`src/vault/state.cpp:837-860`). 07/N-2 shows how easily the "different build" arises: `vault_buildunlock` draws new fee inputs and a new change key on every call. `doc/vault-rpc.md:302-304` says the record holds "across restarts" and nothing about restores or second hosts. Hawkeye mirrors the record in its own SQLite ledger (`hawkeye/crates/hawkeye-store/src/signonce.rs`, `ycash-unlock`/`ycash-cancel` keyed by `(domain, setId, prevout)`) but the node wallet's record is what protects the key (plan finding (70)). Same on `ycash6` (`src/rpc/vault.cpp:1487`, `src/wallet/walletdb.cpp:90`, `doc/vault-rpc.md:302`).

## 2. Root cause

- `src/wallet/walletdb.cpp:1498-1511` — the record exists only in the one `wallet.dat` that signed; `src/wallet/rpcdump.cpp:876-923` (`dumpwallet_impl`) writes keys, the HD seed fingerprint and `pqseed=` lines, never `vaultsetsig`; `importwallet_impl` (`:594-660`) has no line type for it.
- `src/wallet/wallet.cpp:6914-6950` — a `-hdseedfile` wallet is a new wallet with no records and no marker that it is a restore.
- `src/rpc/vault.cpp:1459-1476` — the guard consults the local record only; no "this wallet may be a copy" check.
- `doc/vault-rpc.md:302-304` — "across restarts"; nothing on backups, restores, mirrors.

## 3. Fix options considered

1. **Document + operational rule (must).** One signer host per member key; back up `wallet.dat` after every set signature (the seed is not enough); never restore and sign without importing the record; never run two wallets with one member key. Zero code; closes nothing by itself but makes the hazard visible.
2. **Export/import the record (recommended, optional code).** `z_exportwallet`/`dumpwallet` write `vaultsetsig=` lines; `z_importwallet`/`importwallet` read them (refusing to overwrite a differing existing record); a read RPC `set_listsigned` lists the records so an operator can verify a restore. Makes the operational rule executable.
3. **Restore-time marker + refusal (recommended, optional code).** A wallet record `vaultsignrestored` written when a wallet is created from `-hdseedfile` or when `importwallet`/`z_importwallet`/`importprivkey` imports a key that is a member of any set in the vault DB; while set, `set_signunlock`/`set_signcancel` refuse with `set-sign-restored` until `set_importsigned`/an import clears it or the call passes `acknowledgerestore: true`. Fails closed where today it fails open.
4. **Derive the record from chain data** (scan the mempool and recent blocks for the member's existing set signatures over the prevout). Partial — a signed, never-broadcast transaction is invisible, which is exactly the dangerous case (05/N-1). Rejected as the guard; acceptable as an extra check in (3).

## 4. Recommended fix

1. **`doc/vault-rpc.md` (both lines, `:294-304` "Sign once"; `ycash6/doc/vault-rpc.md:302`)** — add a paragraph: the record is in `wallet.dat` only; what has no record (seed restore, `importwallet`, `importprivkey`, a second host); the consequence (ejection + frozen bond, by anyone); the rule: **one signing host per member key; back up `wallet.dat` after every `set_signunlock`/`set_signcancel`; restoring from seed alone is unsafe for a member key; before signing on a restored wallet, import the record (`set_importsigned` / the dump's `vaultsetsig=` lines) and verify with `set_listsigned`.** Cross-reference `MEDIUM-01-V-2` (with ANYONECANPAY a re-funded build has the same sighash — the record stays valid across re-funding; the hazard is a *different* build).
2. **`doc/yellowback-attestor.md`** — a "Member-key hosts" section with the same rule for YED attestors and bridge attestors (Hawkeye's `hawkeye.db` must be backed up with the node's `wallet.dat` as one unit; the R7 runbook owns the full procedure).
3. **Export/import (optional code, recommended):**
   - `src/wallet/walletdb.{h,cpp}`: `ListVaultSetSigs(std::vector<{setId, prevout, role, sighash}>&)` (a cursor over the `vaultsetsig` prefix, as other list helpers do) and `EraseVaultSetSig` is **not** added (the record must never be deleted by RPC).
   - `src/wallet/rpcdump.cpp` `dumpwallet_impl` (`:876-923`): after the `pqseed=` block, `# Vault set signatures (vaultsetsig=<setid>:<txid>:<n>:<role>:<sighash>)` lines; `importwallet_impl` (`:594-660`): parse `vaultsetsig=`; if a record exists with a different `(role, sighash)` → abort the import with `RPC_WALLET_ERROR` naming the pair (two histories for one key must never be merged silently); identical → no-op.
   - `src/rpc/vault.cpp`: `set_listsigned` → `[{setid, prevout, role, sighash}]`; `set_importsigned [{setid, prevout, role, sighash}]` with the same refuse-on-conflict rule; both in `doc/vault-rpc.md`, `doc/vault-rpc-contract.json`, `rpc/client.cpp`.
4. **Restore marker (optional code, recommended):** write `vaultsignrestored = 1` in `CWallet` when a new wallet takes `-hdseedfile` (`wallet.cpp:6919-6935`) and in `importwallet_impl`/`z_importwallet`/`importprivkey` when the imported key is a member of any set at the tip (`vault::TipSnapshot()`, `GetMembers`); `SignSetInPlace` refuses with `set-sign-restored` ("this wallet was restored or imported a member key and has no sign-once history; import it with set_importsigned, or pass acknowledgerestore=true if this key has never signed a set spend") unless `params[1]` is `{"acknowledgerestore": true}`; `set_importsigned` and a dump import clear the marker. Log a one-line warning at wallet load while the marker is set and the wallet holds a current member key.
5. Both lines: the wallet files differ only in 6.x API names; `doc/vault-rpc.md` is shared text.

## 5. Tests

- **Functional (`qa/rpc-tests/vault_pq_wallet_restore.py`, both lines; the verifier noted the file has no `set_sign*` case):** node 1 (a member) signs an unlock; (a) `backupwallet` → node 2 starts on the backup: re-signing the identical hex is idempotent, a different build is refused `set-sign-once`; (b) node 3 starts with `-hdseedfile` of node 1's seed: `set_signunlock` of a different build → `set-sign-restored`; with `acknowledgerestore` it signs (documents the override); after `set_importsigned` of node 1's `set_listsigned` output the refusal is `set-sign-once` (the real guard) and the identical hex signs; (c) `z_exportwallet` on node 1 contains the `vaultsetsig=` line; `z_importwallet` on a fresh node 4 restores it; importing a conflicting line aborts; (d) `set_listsigned` shape in `vault_rpc_contract.py`.
- **Unit:** `walletdb` round trip of `ListVaultSetSigs`.

## 6. Acceptance criteria

- `doc/vault-rpc.md` and `doc/yellowback-attestor.md` state the single-host rule, the backup rule and the restore procedure on both lines.
- (If the optional code is taken) a restored or key-importing wallet cannot sign a set spend without an explicit acknowledgement or an imported record; the record exports with the wallet dump and imports without silently merging conflicts; `set_listsigned` exists and is in the contract.
- `vault_pq_wallet_restore.py` carries the sign-once cases on both lines.

## 7. Risks and side effects

- **No consensus effect.** A stricter signer can only refuse, never equivocate; the `acknowledgerestore` override is the operator's explicit acceptance.
- **Liveness:** an operator who restores and forgets the import is refused until they act — the intended failure direction (a refused signature is recoverable; a frozen bond is not).
- **Dump files now carry set-signature history** — no secrets, but they identify the member's spends; the dump already carries keys and seeds, so no new sensitivity class.

## 8. Effort estimate and dependencies

- Docs: 0.25 day. Export/import + list RPC: 0.75 day. Marker + refusal: 0.5 day. Tests: 0.75 day. ycash6 port: 0.25 day.
- Dependencies: pairs with `MEDIUM-01-V-2-ycash-set-sig-anyonecanpay.md` (same doc paragraph; its persisted build memo is a second wallet record the dump should carry too). Hawkeye's R7 runbook (05/M-1..M-4) references this report for the node side.

## Completion record

- **Completed:** 2026-10-13T11:21Z
- **Merged:** with fix/set-sig. set_listsigned / set_importsigned; dumps carry the sign-once records and build memos; a restore marker blocks set signing until set_acknowledgerestore (imports never clear it; a key imported before its JOIN sets it when the JOIN connects); docs: one member key per wallet, cancel-pinning guidance. vault_pq_wallet_restore.py covers backup, seed restore, stale dump and late join.
- **Verification:** Integration run 2026-10-13 (both node lines built; full test_bitcoin dd 872/872, ycash6 923/923; qa/yellowback-audit.sh dd --mode upgrade rc 0 (18 PASS), ycash6 --report-only rc 0; functional suites pass; vault_vectors / golden / pq vectors byte-identical across lines). Logs: wt/scratch/integ/.
