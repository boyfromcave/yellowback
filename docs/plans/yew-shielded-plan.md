# YEW shielded plan — Sapling in the mobile wallet on the x402 light-client core

**Status:** revision 2, 2026-10-04, **approved; S1 may start.** S0-1..S0-5 decided by the owner (below). Revision 1 was the draft from the owner's direction ("YWallet is deprecated; add Sapling to
YEW, keep YEW simple"). Owner decisions S0 pending. Built on the `yewsapling` investigation (below, verbatim)
and on `x402-ycash/docs/zwallet-comparison.md`. Depends on `x402-ycash/light` (chunk `lightcore`) landing.

## 0. Owner decisions (S0)

| # | Decision | Recommendation |
|---|---|---|
| S0-1 | Reverse wallet-plan D-W-2/D-W-7: Sapling in scope; ZIP-32 account 0 at `m/32'/347'/0'`, YWallet-compatible (one seed restores both pools) | **Decided: yes** (2026-10-04) |
| S0-2 | Proving parameters (52 MB) | **Decided: download on first shielded send**, SHA-256 pinned, from our HTTPS host |
| S0-3 | YEW `rusqlite` downgrade to 0.37 (libsqlite3-sys collision with librustzcash6) | **Decided: approved** |
| S0-4 | `lite.ycash.xyz` upgrade to lightwalletd-dd ≥ `0b3448e` (GetChainInfo) | **Decided: planned, may take time. Develop against regtest and the boyfromcave lightwalletd-dd fork for now**; the builder's fallback to `LightdInfo.consensusBranchId` covers the public endpoint until then |
| S0-5 | Scope: S1–S3 first (shielded receive/send/memo), then S4 shield/unshield; nothing more from YWallet | **Decided: yes** |
| S0-6 | **This is a Ycash project.** Code is derived from Zcash solutions, but every solution, name, parameter, screen string and document is for Ycash: `ys1…`/`s1…`/`ye…` addresses, coin type 347, Ycash branch ids, Ycash networks, "YEC". Zcash is named only when citing the origin of a file or a vector. (Owner, 2026-10-04; same rule as [`ycash6-naming-is-ycash`].) | **Standing rule** |

---

# Chunk `yewsapling`: Sapling in YEW via the x402 light client (research + plan)

Read-only, 2026-10-04. Verdict up front: **yes, feasible, and the right shape is a library split of `x402-ycash/light` that YEW's core depends on by path.** The hard parts are not cryptography but packaging (one SQLite, 52 MB of params, background sync on phones) and a Cargo version collision that must be fixed first. Minimal scope (shielded receive/send/memo, then shield/unshield) is roughly 6â8 engineering weeks after `lightcore` lands.

## 1. YEW today

- **Crate.** `/Users/boy/projects/yellowback-workspace/yew/core/Cargo.toml:10-14`: `yew_core`, `crate-type = ["rlib","staticlib","cdylib"]` (staticlib â iOS xcframework, cdylib â Android jniLibs). Deps are an exact-pinned allow-list (`yew/scripts/allowed-deps.txt`; plan Â§3.3), notably `tonic =0.14.6` with `tls-ring`/`tls-webpki-roots` (webpki needed because `rustls-native-certs` has no iOS backend, `Cargo.toml:27-33`), `rusqlite =0.40.2 bundled`, `flutter_rust_bridge =2.13.0`. No `zcash_*` crate anywhere (D-W-2/D-W-3, plan `docs/plans/yellowback-wallet-plan.md:282-300`).
- **Bridge.** `yew/flutter_rust_bridge.yaml`: surface is `core/src/api.rs` only; Dart output `app/lib/src/rust`. `api.rs` holds ~45 blocking functions on a private tokio runtime behind a global `WALLET: Mutex<Option<Open>>` (`api.rs:1057-1157` create/unlock/lock; `sync_now(sink: StreamSink<SyncEvent>)` at `:1540` streams progress). Dart calls through `app/lib/api/wallet_api.dart:41-137` (27 `Future` methods, an interface with a fake for widget tests) â `rust_wallet_api.dart`; CI forbids crypto/db/socket imports under `app/lib`.
- **Tx path.** Hand-written v4 serializer + ZIP-243 sighash + libsecp256k1 signer (`core/src/tx.rs:5-13`); the parser reads the transparent part of shielded txs but refuses to re-serialize them (`tx.rs:37-39`, `TxError::Shielded`). Coin classes/fee reserve in `coins.rs`/`coinselect.rs`; broadcast gate `gate.rs`.
- **Network.** Per-address sync, no compact blocks: `GetAddressUtxos`, `GetTaddressTxids`, `GetTaddressBalance`, `SendTransaction` (`core/src/net/compact.rs:5-8, 77-258`) plus `YellowbackStreamer` (`net/yellowback.rs`). `sync.rs:5-10` documents the model.
- **Storage.** Own rusqlite schema v3 (`store.rs:323-360`: meta, addresses, utxos, locks, history, pending_txs, own_outputs, own_tokens, mints, vaults); "the database is a cache" (`store.rs:12-13`).
- **Keys.** BIP39 â BIP32 secp256k1 at `m/44'/347'/0'/{0,1}/i`, Ywallet-compatible (`keys.rs:5-12`; D-W-7 at plan `:319-345`, which states "No ZIP-32 / Sapling keys are derived, ever"). Seed lives only in the platform keystore (`app/lib/state/secrets.dart:5-18`), handed to the core at unlock.
- **Screens.** 14 Dart files, 2,704 lines total (`app/lib/screens/`): onboarding, seed_backup, home, receive, send, history, settings, server, keys, yellowback, mint, mint_progress, vault, claimable. Plan Â§5.2 (`:616-618`): "Six screens. Numbers first. One gesture to sendâ¦ No dashboards."
- **Remaining plan items.** Only `[owner]` tasks: â¥4-week testnet run against a public lightwalletd-dd, default server list, Ywallet derivation vector capture (`plan:786-790`, `yew/README.md:228-229`). Shielded is explicitly out of scope today (`plan:793`).

## 2. Reuse path: library split

**Current light client shape** (`wt/x402-lightcore/light/`, uncommitted `?? light/` in the worktree): one bin `x402-light` (`Cargo.toml:9-11`), modules `keys, lwd, net, rpc, sync, wallet` (`src/main.rs:6-11`). `wallet.rs:55-67` is already a clean struct: `WalletDb<rusqlite::Connection, YcashNetwork, SystemClock, OsRng>` + `FsBlockDb` cache + lazily loaded `LocalTxProver` from a params dir (`:366-379`) + tonic channel. `sync.rs:1-20` implements the three zwallet techniques (download/scan overlap chunked by output count, `GetTreeState` birthday bootstrap, checkpoint reorg rewind of 10 blocks) over `scan_cached_blocks`; `build()` (`wallet.rs:385-510`) uses `propose_standard_transfer_to_address` + `create_proposed_transactions` with ZIP-317 or a fixed fee, memo as text or hex, and refuses to build if its branch id disagrees with `GetChainInfo` (`lwd.rs:26-39`). Only `main.rs` (clap) and `rpc.rs` (hyper JSON-RPC) are server-specific.

**Proposed split (in `x402-ycash/light`, chunk `lightcore` or a follow-up):**
- `light/core/` â crate `x402-ycash-light-core` (rlib): `keys, lwd, net, sync, wallet` moved verbatim; `Wallet::open` takes an already-built channel or a `Server` config; `extsk` becomes an injected secret (today it is read from `spending.key`, `wallet.rs:97-103`, which YEW must not do); `tracing` kept, `clap`/`hyper` removed.
- `light/` bin keeps `main.rs` + `rpc.rs` and depends on the core. Both share one `[patch.crates-io]` block (`Cargo.toml:49-61`).

**Compatibility findings:**
1. **BLOCKER: SQLite collision.** YEW links `libsqlite3-sys 0.38.2` (rusqlite 0.40.2, `yew/Cargo.lock:870`); librustzcash6 pins `rusqlite 0.37` â `libsqlite3-sys 0.35.0` (`librustzcash6/Cargo.toml:152`, `light/Cargo.lock:1253`). `libsqlite3-sys` has a `links` key, so Cargo refuses two versions in one graph. YEW must downgrade to `rusqlite =0.37` (allow-list change; one-line) or librustzcash6 must bump. Downgrading YEW is the cheaper, lower-risk move.
2. **tonic/prost agree** (0.14.6 in both lockfiles). `zcash_client_backend`'s `lightwalletd-tonic` feature reuses YEW's channel type; YEW's `tls-webpki-roots` fix carries over since the channel is built once in YEW's `net/`.
3. **FFI.** flutter_rust_bridge over an rlib dependency is routine: `yew_core` stays the only staticlib/cdylib; the light core is a plain Rust dependency, its types wrapped by `api.rs` DTOs (no `zcash_*` types cross the bridge). The light core's API is `async`; YEW already runs blocking calls on a private runtime (`README:171-173`), so `runtime().block_on` wraps it. Note `WalletDb` is `!Send` across awaits like YEW's store; same pattern.
4. **zcash_client_sqlite on iOS/Android.** Uses bundled SQLite (fine) and `FsBlockDb` writing compact blocks to a `blocks/` directory (`wallet.rs:85-89`); point it at YEW's existing `data_dir` (already backup-excluded on iOS, `secrets.dart:17-18`). Background execution: iOS gives no long-running background; sync must run in foreground and be resumable, which `scan_cached_blocks` ranges already are. Android: foreground service optional, later.
5. **Proving params (51.6 MB; `x4m-measurements.md:251`).** Options: (a) bundle in the app (adds ~52 MB to download; App Store/Play allow it; no review issue, Zcash wallets do this), (b) download on first shielded send via `zcash_proofs::download_sapling_parameters` (`zcash_proofs/src/lib.rs:120`, feature `download-params`, needs `minreq` â a new dep). Recommend **(b) from our own HTTPS host with the known SHA-256s**, with a one-time "Preparing private sending (52 MB)" sheet; keeps install small and params are only needed for *sending*, not receiving.
6. **Proving time.** X4-M: 1.1â1.7 s for 1 spend + 2 outputs on an M5 desktop (`x4m-measurements.md:292`). Published Zcash mobile figures for the same Groth16 circuit are 5â12 s per spend+output pair on mid-range phones; expect **5â15 s per send**, fine behind the existing slide-to-confirm + progress UI. Memory peak ~200â300 MB during proving; acceptable on API 24+/iOS 15 devices.
7. **Shared vs different.** Shared: sync, note store, builder/prover, lightwalletd client, reorg logic, network params. Different: key provenance (YEW derives the Sapling ExtSK from the BIP39 seed in-process, ZIP-32 `m/32'/347'/0'`, Ywallet-compatible â same account as D-W-7, so a Ywallet seed restores both pools), params location, UI, and the transparent side (YEW keeps its own UTXO/YED machinery; `zcash_client_sqlite`'s transparent support is not used).

## 3. Minimal product shape

- **One Sapling account, one default address** (`ys1â¦`), diversified addresses only via "new address" in Receive (cheap, same key, no UI complexity beyond the existing toggle).
- **Home:** one YEC total with a two-line split "shielded / transparent"; YED unchanged. No third tab.
- **Send:** address field accepts `sâ¦`/`yeâ¦`/`ys1â¦`; a memo field appears only for `ys1â¦`. Funding rule, automatic, one default: **prefer shielded**; if the recipient is transparent and shielded funds would be revealed (zât), show one amber line "This send leaves the private pool" in the existing preview card. No manual note picking; `GreedyInputSelector` + ZIP-317 as the light core already does.
- **Receive:** QR for `ys1â¦` by default when the wallet has synced shielded; toggle to `yeâ¦`/`sâ¦` for YED/mint.
- **History:** existing list gains memo text on tapped shielded rows (messaging = memos). No threads, no contacts.
- **Shield / Unshield:** one explicit action on Home ("Move to private" / "Move to public") = tâz or zât to own address, with the same preview. Lands after send/receive.
- **Restore:** existing birthday field already exists (`plan:607`); it now also seeds `AccountBirthday` via `GetTreeState`.
- **Do NOT carry over from YWallet:** multi-account, contacts, prices/fiat, Orchard, GPU paths, spam filter, swap/pay-URI extras, cold-storage/Ledger, SQLCipher, mempool unconfirmed-balance stream (zwallet's Ycash one panics anyway; `zwallet-comparison.md` finding 3), coin control / per-note exclusion, custom fee UI, viewing-key accounts.

## 4. Yellowback interplay

YED is transparent-only (V8) and mint/redeem need transparent YEC collateral and fees. Rule: **the fee reserve and all YED machinery stay transparent and untouched**; shielded YEC is a separate bucket the YED path never sees (same discipline as `coins.rs` classes: add class `SHIELDED` conceptually outside the UTXO table). UX: when Mint or a YED send lacks transparent YEC, the existing insufficient-funds message offers "Move YEC to public first" (deep link to Unshield with the shortfall prefilled). Balance card shows "YEC available for YED/fees" (transparent, as today) and "private YEC" (shielded). Mint collateral never auto-unshields: one explicit step, which also keeps the privacy story honest.

## 5. Risks

- **Sync/battery.** Ycash: 154 outputs/day, 872k ever (`x4m-measurements.md:391`). First sync from a recent birthday is seconds; a full-history restore is ~872k trial decryptions at ~60 Âµs/output single-core â ~1 min on a phone core, plus ~106 MB of compact data (122 B/output). Acceptable with the progress sink. Daily catch-up: ~121 KB and tens of ms. No `GetSubtreeRoots` on Ycash â a note is spendable only after full sync from birthday (`sync.rs:11-13`); UI must say "syncingâ¦ sending available at 100%".
- **Params review.** No store policy issue; downloading 52 MB on first send needs a hosted file + hash pin (owner: where to host).
- **Reorgs.** Light core rewinds 10 blocks to a checkpoint (`sync.rs:46`); YEW's transparent side re-queries per address and is reorg-agnostic; the two balances can briefly disagree â show one "updating" state.
- **Public endpoint.** `GetChainInfo` is in lightwalletd-dd `0b3448e` (merged 2026-10-04); `lite.ycash.xyz` must run â¥ that commit or the builder falls back to `GetLightdInfo`'s tip branch id (`lwd.rs:26-29`; wrong only on the block before an upgrade). Also TLS roots on iOS (already solved in YEW).
- **Devnet testing.** `YcashNetwork::devnet_regtest` exists (`net.rs:26`); YEW's `scripts/devnet-w4.sh` devnet is 4.5.0-line; the 6.21.0 line needs the second devnet (`x402-ycash/docs/regression.md`). Node vectors for Sapling spends must be regenerated on both.
- **Seed scope creep.** Deriving ZIP-32 keys reverses D-W-7's "never"; requires an owner decision and a Ywallet vector for the `ys1â¦` default address.

## 6. Plan

### Status (checklists are the status of record; tick with a date)

- [x] S0 decisions taken (2026-10-04, S0-1..S0-6).
- [x] S1 library split — delivered with the light client (2026-10-04, `x402-ycash` `22d7709`): YEW depends on the `x402_ycash_light` library (path `../../x402-ycash/light` from `yew/core`); spending key injected, no file key, no server code.
- [x] S2 YEW core integration — **done 2026-10-04** (`yew` `3946ced`); TLS gap Z-3 moved to S3 (below)
  - [x] Groundwork merged (`yew` `ef622ce`, 2026-10-04): rusqlite 0.37; `core/src/shielded_keys.rs` — Ycash ZIP-32 account 0 at `m/32'/347'/0'` via `zcash_keys` 0.14 (librustzcash6), YWallet-compatible (code-read: `zcash-sync/src/key2.rs:115-150`), node-verified vectors (`core/tests/vectors/sapling_keys_ycash.json`: `z_importkey` reports our default address 3/3, exports byte-identical, a diversified address receives); RustCrypto pre-release pins aligned with librustzcash6's `bip32 0.6.0-pre.1`; 91 tests, deps/audit/licence checks green.
  - [x] Light-library dependency, combined sync, shielded balance, send with memo, params download (`yew` `3946ced`, 2026-10-04): Sapling side under `<data>/shielded/` (0700), account registered at the restore birthday via `GetTreeState`, spending key never written by YEW; one progress stream with shielded stages and the "sending available at 100%" flag; bridge DTOs (`Balances` shielded total/spendable/pending, `receive_address(kind)`, `new_shielded_address`, `send_yec_preview` with memo, `funding`, `revealsShielded`, `paramsNeeded`; history memos; `params_status`/`download_params` with pinned SHA-256s); privacy-first funding; gate path `Shielded`; YED and the fee reserve untouched. Devnet `s2_` green on **both lines** (restore + balance + memo; z→z with memo confirmed on the node; z→t with the reveal flag; memo to a t-address refused; transparent YEC and YED still work; second restore recovers memos; no key on disk). Release-build z→z ≈ 2.6 s, z→t ≈ 2.3 s; restore sync ≈ 0.6 s on regtest. 102 tests; deps/licences/audit green; `flutter analyze` clean, `flutter test` 32/32.
  - Notes: z→t ZIP-317 fee is 15,000 zat (outputs padded to two); `time` stays at 0.3.37 via librustzcash6 (RUSTSEC-2026-0009, RFC 2822 parsing only, audited exception); a refused broadcast leaves its notes locked for 40 blocks (library behaviour); params host URL is an owner item (S0-2).
  - Notes: off mainnet the node's HD wallet uses coin type 1, YEW/YWallet 347 (by design); `docs/trust.md` statement ("holds no shielded funds") changes with S3, together with `app/lib/trust_text.dart`; release builds now depend on RustCrypto pre-releases until librustzcash6 leaves `bip32 0.6.0-pre.1`.
- [x] S3 YEW app: send/receive/memo — **done 2026-10-04** (`yew` `d2d20a9`): private YEC on the existing screens (14 screen files before and after; new: the proving-files sheet, a download-address dialog, a three-way Receive toggle, the memo field, one Settings row). Home Private/Public split with "sending available at 100%"; Receive private by default + "New private address"; Send with an optional message only for `ys1…` (512-byte counter), the amber "This payment leaves your private balance"; one-time "Preparing private sending (52 MB, once)" sheet; history lock glyph + message; "Move YEC to public first" on Mint/Send YED; trust statement rewritten in `docs/trust.md` and `app/lib/trust_text.dart` together. `flutter analyze` clean, `flutter test` 44/44 (12 new); iOS simulator flow (`app/integration_test/s3_screens_test.dart`) green against the S2 devnet (ycash-dd), 12 screenshots in `yew/docs/screenshots/shielded/`. Not run on device: the 6.21.0 line (S5). Left out for simplicity: one-tap move to public (S4), fee control, choosing which balance pays, memo threads.
  - [ ] **Z-3 (medium, from S2):** the light library opens its own TLS with native roots, so YEW's pinned certificate is ignored for the shielded scan and iOS (no native roots) would fail; YEW refuses shielded sync while a pin is set. Fix: channel injection in `x402-ycash/light` — **library side done 2026-10-04** (`x402-ycash` `9893f2e`); YEW passes its own channel and lifts the pin refusal inside S4 (`yewmove`).
- [ ] S4 shield/unshield (in flight from 2026-10-04, chunk `yewmove`); includes `validate_address` returning kind `sapling` (S3 bridge gap, worked around in Dart by prefix).
- [ ] S5 hardening (both node lines, devices).


| Phase | Where | Size | Content |
|---|---|---|---|
| S0 Decisions | owner | â | reverse D-W-2/D-W-7 (shielded in scope; ZIP-32 account 0); params hosting; rusqlite 0.37 downgrade; `lite.ycash.xyz` upgrade |
| S1 Library split | `x402-ycash/light` | **M** (3â4 d) | `light/core` rlib: injected ExtSK + channel, no fs key, no clap/hyper; bin + JSON-RPC as wrapper; existing devnet tests keep passing on both lines |
| S2 YEW core integration | `yew/core` | **L** (1.5â2 wk) | rusqlite 0.37; add `x402-ycash-light-core` by path (allow-list); `keys.rs` ZIP-32 derivation; `wallet.rs` holds the light `Wallet` beside the transparent store in the same data dir; `sync_now` runs both and streams one progress; `api.rs`: `Balances.yecShieldedZat`, `receive_address(shielded)`, `send_yec_preview/confirm` accepting `ys1â¦` + memo and the reveal warning, history memo field; params download API; node vectors + devnet tests on both lines |
| S3 YEW app, send/receive/memo | `yew/app` | **M** (1 wk) | balance split, address/memo field, reveal line in preview card, memo on history detail, params sheet, sync copy |
| S4 Shield/unshield | core + app | **S** (3 d) | one action, two directions, reuses preview/confirm |
| S5 Hardening | both | **M** (1 wk) | restore-from-seed with birthday on both lines, reorg test, battery/sync measurement on devices, trust.md + security-review.md update, Ywallet `ys1` vector |

**Total â 6â8 weeks** of one engineer after `lightcore` merges; S1 can start now on the worktree. Minimal first release = S1âS3; S4 follows.

### Critical Files for Implementation
- /Users/boy/projects/yellowback-workspace/wt/x402-lightcore/light/src/wallet.rs (the struct to become the library core; key injection and prover loading at :55-115, :366-379, build at :385-510)
- /Users/boy/projects/yellowback-workspace/wt/x402-lightcore/light/Cargo.toml (crate split, shared `[patch.crates-io]`, rusqlite 0.37)
- /Users/boy/projects/yellowback-workspace/yew/core/Cargo.toml (rusqlite downgrade, new path dependency, allow-list `yew/scripts/allowed-deps.txt`)
- /Users/boy/projects/yellowback-workspace/yew/core/src/api.rs (bridge surface: balances, receive, send preview/confirm, sync_now, new params/shield calls)
- /Users/boy/projects/yellowback-workspace/yew/core/src/wallet.rs and /Users/boy/projects/yellowback-workspace/yew/core/src/keys.rs (hold the shielded wallet beside the transparent one; ZIP-32 derivation)
- /Users/boy/projects/yellowback-workspace/docs/plans/yellowback-wallet-plan.md (D-W-2, D-W-7 to be revised; Â§5 screens)
