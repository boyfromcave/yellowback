# INFO — W3-C-6, W3-C-9 — YecWallet keeps the signed cancel in `QSettings` and its RPC password in `QSettings` (both accepted; one small hardening: consult the node's sign-once records)

Repos / branches to change: `yecwallet-dd` (`fix/W3-C-6-signed-cancel-record` off `upgrade/vault`, or stacked on `fix/W4-C-1-yed-cancel`; optional). W3-C-9: docs only, same branch.
Audit source: wave 3 `docs/audits/quantum-vault-ecosystem-wave3/06-clients-wallets-infra.md:48, 51` (summary rows), `:183-190` (W3-C-6), `:194-198` (W3-C-9 context); verification `docs/audits/quantum-vault-ecosystem-wave3/verification/06-verification.md:20, 23` (verdicts: W3-C-6 Info, down from Low; W3-C-9 Info), `:224-231` (W3-C-6), `:237-243` (W3-C-9); consolidated `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:53`. Wave 4 `docs/audits/quantum-vault-ecosystem-wave4/04-clients-wyec-recheck.md:56` (W3-C-6 STILL OPEN, accepted design), `:59` (W3-C-9 STILL OPEN, upstream behaviour), `:58` (W3-C-8 **NO LONGER REPRODUCIBLE**: x402's retry loop rethrows at `i >= 15`, so the one-byte counter never wraps; it was never a defect and is dropped from this report, which earlier grouped it); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:27`.
Status: pending — re-verified at yecwallet-dd `c830233` (unchanged since wave 3) and node `ycash-dd` `da5e0fe` (2026-10-13); every line below re-grepped. Note: the cancel flow this report hardens does not work today at all (W4-C-1, `MEDIUM-W4-C-1-W4-C-4-yecwallet-yed-cancel-claim-vault-contract.md`); land that first.

## 1. Finding

**W3-C-6 (YecWallet).** When an attestor member cancels a wrong-price claim from the GUI, YecWallet stores the transaction it signed in `QSettings` under `yellowback/signedcancel/<outpoint>` *before* sending. From then on it only offers to re-send that hex. The node's own sign-once record in `wallet.dat` is the real guard: `set_signcancel` refuses a different spend of the same `(setid, prevout)` with `set-sign-once`. A wiped or edited `QSettings` therefore cannot produce an equivocation. The stored artefact is a transaction anyone may broadcast without harm. The verifier rated it Info: the record *prevents* a second, different signing in the GUI; it does not enable one.

One small gap remains. If `QSettings` is lost (new OS user, config reset), the GUI offers the full build-and-sign flow again. The node then refuses at `set_signcancel` with `set-sign-once`, but only after the member has gone through the confirm dialog and a build call, and the error says nothing about the original transaction. The node already exposes its records (`set_listsigned`), which the GUI does not read.

**W3-C-9 (YecWallet).** Upstream behaviour: the generated `ycash.conf` holds a 24-character alphanumeric `rpcpassword` from `QRandomGenerator::global()` (OS-seeded), and the connection settings mirror it into `QSettings`. Already hardened by the first wave (`INFO-06-W-1`, done: alphabet size and the NUL truncation). Accepted as is.

(W3-C-8, x402's Falcon retry counter, was listed here before wave 4. Wave 4 re-read `x402-ycash` `6af477a` `packages/ycash/src/pq/sign.ts:121-134`: the loop rethrows at `i >= 15`, so the counter stays in `0..15` and never wraps. It is not a finding and needs no change; the optional "name the bound" tidy-up is dropped to keep this list to defects.)

## 2. Root cause (yecwallet-dd `c830233`; node `ycash-dd` `da5e0fe`)

- **W3-C-6.**
  - `yecwallet-dd/src/yellowbacktab.cpp:2074-2087`: the stored hex is read, and if present only a re-send is offered after `confirm`.
  - `:2117-2118`: `setYellowbackSignedCancel(outpoint, shex)`, "Kept before anything is sent".
  - `:2029-2030`: the status text "already signed".
  - `src/settings.cpp:181-187`: plain `QSettings` key, with `:` replaced by `_`.
  - Node: `ycash-dd/doc/vault-rpc.md:332-348` (sign-once; "The record lives only in this `wallet.dat`" at `:336`), `:392` (`set_signcancel`), `:430-439` (`set_listsigned`: `{restored, records:[{setid, prevout, role, sighash}]}`, role 2 = cancel). The same text is on ycash6 (`doc/vault-rpc.md:430`).
  - `grep -rn set_listsigned yecwallet-dd/src` is empty.
- **W3-C-9.**
  - `yecwallet-dd/src/connection.cpp:120-132` `randomPassword()` (the post-INFO-06-W-1 form);
  - `:197-200` writes `server=1`, `addnode=…`, `rpcuser=ycash`, `rpcpassword=…` and no `rpcbind`/`rpcallowip`;
  - `:846-858` `loadFromSettings` reads `connection/rpcuser` and `connection/rpcpassword`.

## 3. Fix options considered

1. **W3-C-6: move the record out of `QSettings`** (encrypted, or into the node's data directory). Rejected: the record holds a broadcastable transaction, not a secret, and the authoritative record is the node's.
2. **W3-C-6: consult the node's record before offering to sign.** Accepted. One read-only RPC that the node already offers. It turns a late, confusing `set-sign-once` failure into an up-front explanation, and works when `QSettings` was lost.
3. **W3-C-9: switch to cookie authentication.** Not pursued here. It is an upstream design choice (the GUI also supports user-entered remote connections, which need a password). No change.

## 4. Recommended fix

1. **W3-C-6 (YecWallet).** Apply on top of `MEDIUM-W4-C-1-…` (same function, `YellowbackTab::cancelClaim`).
   - In `YellowbackController` (where `isAttestor()`/`setCancelThreshold()` live, `yellowbackcontroller.h:141-143`), add `listSigned(cb)`, which calls `set_listsigned`, and cache the records with the other per-refresh state. Skip the call when `!isAttestor()`.
   - In `yellowbacktab.cpp`, before the build path (after the `stored.isEmpty()` branch at `:2087`): if a record with `role == 2` exists for the intent's `prevout` under the attestor set id while `QSettings` has no hex, show `notice(tr("Cancel already signed"), tr("This wallet's node already signed a cancel of intent %1 (sighash %2), but this computer does not have the signed transaction. The node will not sign a different one. If you still have the transaction, broadcast it; otherwise nothing more can be done from this wallet."))` and return.
   - Do the same check in the status text at `:2029`.
   - If `set_listsigned` returns `restored: true`, surface the node's `set-sign-restored` state (the sign RPCs refuse until `set_acknowledgerestore`). Wording: "This wallet was restored; its sign-once history may be incomplete (vault-rpc.md 07/F-5)".
   - Add `SET_LISTSIGNED` and a `ListSigned` field namespace to `src/vaultrpc.h`. Once `MEDIUM-W4-C-1-W4-C-4-…` has added the vault-contract check, it covers the new name and fields automatically.
2. **W3-C-9.** No code change. Record the accepted risk in `yecwallet-dd/docs/yellowback.md`: the bundled node's RPC listens on loopback only (`connection.cpp:197-200` writes no `rpcbind`/`rpcallowip`), and the password is readable by the same OS user that can already read `wallet.dat`.

## 5. Tests

- **W3-C-6.** Extend the offline QTest `cancelClaimFlow` (`tests/yellowbacktab_test.cpp:1586-1655`), which already drives `cancelClaim` through the fake transport and reads `QSettings`:
  - with `h.rpc.results["set_listsigned"]` holding a role-2 record for the intent and the `QSettings` key cleared, `cancelClaim` shows "Cancel already signed" and makes **no** build call and no `set_signcancel` call (`h.rpc.count(...) == 0`);
  - a record for another prevout, or role 1, does not block;
  - `restored: true` shows the restore notice and signs nothing;
  - with the `QSettings` key present, the re-send path is unchanged.
  - Optional regtest manual check in the PR: sign a cancel as a member, delete `yellowback/signedcancel/*`, and confirm with the node's `-debug=rpc` log that no build call follows.
- **W3-C-9.** None.

## 6. Acceptance criteria

- YecWallet refuses to start a new cancel signing for an intent the node's `set_listsigned` shows as cancel-signed, whether or not `QSettings` has the hex, and says why. `restored: true` is surfaced.
- The QTest cases above pass offline in CI.
- W3-C-9 is recorded as accepted in YecWallet's docs.

## 7. Risks and side effects

- W3-C-6 adds one read-only RPC per refresh for members of the attestor set only. There is no change to signing.
- Neither item touches consensus, vectors or the wire.

## 8. Effort estimate and dependencies

- W3-C-6 ~0.5 day; W3-C-9 ~15 minutes (docs).
- **Depends on `MEDIUM-W4-C-1-W4-C-4-yecwallet-yed-cancel-claim-vault-contract.md`**: until the cancel flow calls `yed_buildcancel`, no cancel is ever signed from the GUI, so this hardening has nothing to protect. Land it after, or in the same PR.
- Related to the node reports on sign-once records (wave-1 `MEDIUM-07-F-5`, done; wave-3 W3-N-3 and 07/NEW-1 on the node lines). It needs only `set_listsigned`, which exists at `da5e0fe` on ycash-dd and at `0742e43` on ycash6.
