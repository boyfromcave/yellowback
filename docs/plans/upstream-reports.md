# Upstream reports: defects found in dependencies

Copyright (c) 2026 The Ycash developers

Defects the Yellowback work found in crates and libraries it depends on but does not fork. Each entry
says where the defect is, how it was found, what our code does about it, and whether it has been relayed
upstream. Defects in the ycashd 6.20.0 pin are in [`ycash6/upstream-report/report.md`](ycash6/upstream-report/report.md);
defects in Zakura are triaged under the kogany plan.

## 1. sapling-crypto: `DiversifiableFullViewingKey::decrypt_diversifier` never returns `Scope::Internal`

- **Found:** 2026-11-12, beta2 run (YEW-REAL finding: a second private-to-post-quantum send from the YEW
  core failed with "key-mismatch: a spent note is not this account's"). Root cause by YEW-FIX, confirmed
  independently by YEW-FIX-REVIEW with a unit test.
- **Where:** `sapling-crypto` 0.7.0 (crates.io; the version yew's lock files take, not patched by
  librustzcash6), `src/zip32.rs:816-831`. The internal arm decrypts the diversifier index with the
  internal `dk` (`:822-825`), then tests `self.address(j_internal)` (`:826`). `address()` is
  `self.to_external_ivk().address_at(j)` (`:756-757`): it re-encrypts the index with the external `dk`
  and uses the external `ivk`, so it never yields an internal address. `Scope::Internal` is
  unreachable: `decrypt_diversifier(change_address)` is `None`. The same code is on sapling-crypto
  `main` (after 0.9.0); its CHANGELOG neither fixes nor documents it.
- **Effect:** a caller that checks a note's ownership with `decrypt_diversifier` refuses every
  internal-scope (change) note. Liveness only: change cannot be spent; no funds are at risk and no
  note is wrongly accepted.
- **Our side:** yew no longer calls it for this check. `core/src/build/hybrid.rs` `owns_in_scope`
  rebuilds the address from the named scope's key and compares all 43 bytes; yewd-signer does the same
  (yew `up/b2-real-run-fixes`, in review). The other callers in the workspace use only the external arm
  (yewd `wallet/src/sapling.rs`), or do not call it (x402-ycash `light/`, zcash_client_sqlite's IVK
  path).
- **Suggested upstream fix:** test `self.derive_internal().address(j_internal)` in the internal arm,
  and a test that `decrypt_diversifier(dfvk.change_address().1)` returns `Scope::Internal`.
- **Status:** to be relayed upstream (zcash/sapling-crypto) by the Yellowback lead architect; the draft
  report is `wt/handoff/upstream-sapling-crypto-decrypt-diversifier.md` (lane YEW-FIX-2). Not yet relayed.
