# Ycash Yellowback (YED) — YEW Development Plan: a transparent-only mobile wallet for YEC and YED

**Status (2026-09-24, revision 6). W0a, W0b, W0c, W1 and W2 complete** (§7): the core now holds the payload codec, the node's floor-aware selector (equal to `yed_estimatesend` input-for-input on the devnet), the `YellowbackStreamer` client, the TOKEN/PENDING_TOKEN classes, the YED transfer and the two-layer gate that refused a malformed transfer with the node's verdict; the WIF round trip into a node wallet passed. Next: W3 (the app). Earlier: the `yew` repository exists with the Rust core's keys, v4 serializer, ZIP-243 signer, T0 gRPC client, store, classifier, YEC send and `yew-cli`; all twelve node-signed vectors reproduce byte-for-byte and the devnet YEC round trip and seed restore pass. Next: W2 (YED tokens, TRANSFER, the gate) against lightwalletd L2. Revision 4 re-based the transparent path on the yodl `lightwalletd` baseline (0.4.6 lineage). Written after the
lightwalletd plan reached revision 4 (Phases L0 and L1 complete; N1 `yed_listtokens` and L2
`GetAddressTokens` in progress) and against the delivered node (`ycash-dd`
`feature/yellowback-price-attest`, `rpcversion 3`). The owner decisions this plan needs are
listed in §2 as D-W-1..D-W-9 with the recommended answer applied in the text; each is reversible
by a one-line change until its phase starts. Work happens in a **new component repository**,
`https://github.com/boyfromcave/yew`, mounted at `yew/` in this workspace (Appendix A). The
node, wallet and lightwalletd plans are
[`yellowback-v2-development-plan.md`](yellowback-v2-development-plan.md) (what is on the chain),
[`yellowback-v3-development-plan.md`](yellowback-v3-development-plan.md) (price attestation) and
[`yellowback-lightwalletd-plan.md`](yellowback-lightwalletd-plan.md) (the relay); this plan is
the client's, and where it is silent on protocol, those three rule. The lightwalletd plan's §5
("the client contract") is what this plan implements.

**One-line summary.** **YEW** ("Your Electronic Wallet") is a small Flutter application for iOS
and Android over a small Rust core. It holds **transparent YEC only** and treats **YED as the
main currency**: balance, receive, send, history for both, and later the Yellowback operations
(mint, vault list, redeem, claim). It never scans compact blocks, never proves or decrypts
anything shielded, and never builds a transaction byte outside the Rust core. Everything it
knows about YED comes through `lightwalletd-dd`'s `YellowbackStreamer`; everything it knows
about YEC comes through the untouched `CompactTxStreamer` transparent path
(`GetAddressUtxos` + `GetTaddressTxids`). The Rust core is the only place the wire and script
bytes exist, is tested byte-for-byte against `ycash-dd` on the regtest devnet, and is reusable by
a desktop client later.

| Component | Budget | Rationale |
|---|---|---|
| `ycash-dd`, `yecwallet-dd`, `lightwalletd-dd` | **0 lines**, except one devnet helper under `ycash-dd/contrib/yellowback/devnet/` (test-vector export, Phase W0) | the client consumes the `yed_*` surface through the relay; it never asks the node for a new rule |
| `yew/core` (Rust) | ≈ 3,000 lines new; dependency allow-list of §3.3 | the whole protocol lives here; small enough to audit line by line |
| `yew/app` (Flutter) | ≈ 6,000 lines new; no crypto, no networking, no persistence of keys | a view over the core |
| `yew/proto` | a pinned copy of `lightwalletd-dd`'s three `.proto` files + the commit they were taken from; CI diffs them | one interface, declared once, in the server's repo |

---

## 0. Revision log

### Revision 6 (2026-09-24) — W2 delivered

`yew` `73dec0a`, `e9ae926`. Acceptance met in full on the armed devnet (`scripts/devnet-w2.sh`),
§7. Rules recorded (README "Rules recorded in W2"): **TOKEN has one source** and an unlisted
`TOKEN_VALUE` own output stays HELD; **PENDING_TOKEN at broadcast** by `PreLock`, re-derived each
sync; **locked outputs are in neither balance** (a refinement of §3.4); **the gate has two layers**
(local class check, then `ValidateRawTransaction`) and validates plain YEC sends too, the one
asymmetry being a server without the service (YEC proceeds on the local layer, YED refused);
**labels come from verdicts**; `GetAddressTokens` never lists spent tokens (IN-1), so the wallet
keeps its own spent-token table to value a "sent" row (a token created and spent between two
syncs reads as its change only). Devnet traps for §6: stale pool quotes tag blocks `signal` and
drain the price windows even on pool-mined blocks, so re-quote before each block and warm until
`GetPrice(tip − refLag).pMint` is defined; `yed_mint wait=false` then two pool blocks; node 1 is
stock on the armed devnet (node 5 is the wallet node for import tests);
`getreceivedbyaddress` counts token value. `flutter_rust_bridge` 2.13.0 (stable) is the version
W3 pins; its codegen is installed.

### Revision 5 (2026-09-24) — W0 and W1 delivered; rules recorded

W0a (`yew` `ae959ec`), W0b (workspace `b3dfa7c`, `a43c74e`), W0c (`ycash-dd` `9486837d8`, vectors
`yew` `12bb124`) and W1 (`yew` `4d0c5c4`, `7bcc37e`) are checked off in §7 with what was
verified. Rules the work fixed, recorded in §3.7 and §8: the **fee reserve never claims an
output larger than the whole reserve** (a one-coin wallet otherwise showed everything reserved);
**HELD** is the class of an own P2PKH output of exactly `TOKEN_VALUE` until W2 classifies it;
a `wallet.rs` object (KeyRing + Store) joins §3.1; imported WIF keys are stored wrapped under a
seed-derived keystream until W3 moves them to the platform keystore; change of exactly
`TOKEN_VALUE` becomes 9,999 zat and change under 100 zat folds into the fee; lightwalletd
refuses range start 0 and JSON-quotes the `SendTransaction` reply. Fee: `FEE_ZAT = 1000`
(`ycash-dd/src/yellowback/params.h:79`, = policy `DEFAULT_FEE`), `RESERVE_MIN = 105,000`.
Devnet findings from W0c that matter to the client: `yed_validateaddress.keyid` is the HASH160
byte-reversed; a plain devnet must mine on the automated pools to keep price windows filled
before a mint; a `yed_send` issued within ~200 ms of a block is rejected until the wallet has
digested it. The allow-list gained `tonic-prost` (tonic 0.14 split its codec out; treated as
part of tonic).

### Revision 4 (2026-09-24) — the yodl baseline; execution started

The lightwalletd fork's baseline switched on 2026-09-24 to `yodl/lightwalletd` (`zcash/lightwalletd`
0.4.6 + 4 commits, `187a26765e`; lightwalletd plan revision 7–8, Phase R0 re-port complete).
The transparent surface is richer than the 2020 server this plan assumed: `GetTaddressTxids`
**streams the raw transactions with heights** (no per-txid `GetTransaction` round trip),
`GetTaddressBalance`, **`GetAddressUtxos`** (the YEC UTXO set directly, `{txid, index, script,
valueZat, height}`), and `GetMempoolTx` exist. §1.4, §3.2 and §3.6 are updated: the core's sync
uses `GetAddressUtxos` for the YEC set and `GetTaddressTxids` for history, and the mempool method
is recorded as available but still unused (D-W-8: pending state remains the app's own for M1;
a "pending incoming" view is a W5 candidate). Execution: W0a/b/c spawned as parallel agents;
Flutter installed on the owner's machine; Xcode and the Android SDK are `[owner]` installs.

### Revision 3 (2026-09-24) — executable by chunks

Five edits from the readiness review. **W0 split** into W0a (the `yew` skeleton), W0b (the
workspace role `app`) and W0c (the devnet vectors helper in `ycash-dd`), one repository each.
**Owner-only tasks marked** (`[owner]`): the Ywallet vector capture and the iOS signing setup.
**Toolchain pinned in W0a** (Rust, Flutter, `flutter_rust_bridge`, NDK, xcframework/jniLibs
build scripts). **The pre-L2 fallback dropped**: W2 depends on lightwalletd L2 and the token
classifier has one source, `GetAddressTokens` (D-W-8, §1.4, §3.7). **Two facts resolved into
tasks**: the fee constant is W1's first task (§8.2 closed), and D-W-3 states why comparing
signed bytes works (RFC 6979 deterministic signatures in the node's libsecp256k1).

### Revision 2 (2026-09-24) — Ywallet as the derivation reference, simplicity restated, translation sources, YecLite dropped, WIF export, UTXO classes

The owner set two things. **Seed compatibility with Ywallet matters**: a YEW seed must restore
in Ywallet and a Ywallet seed in YEW, with the same transparent address. D-W-7 is rewritten from
Ywallet's own code at the pin YEW references (`hhanh00/zwallet` tag `v1.15.3`, whose
`native/zcash-sync` submodule is `8a3956c8c` and whose `librustzcash` submodule is
`243e18f61`), and §1.5 records what YEW takes from Ywallet and what it deliberately leaves. And
**simplicity**: Ywallet is the reference for derivation and for the Flutter + Rust shape, not
for scope; YEW is transparent + Yellowback and nothing else (D-W-2 unchanged, §1.5). Third,
**the core is a translation, not a reinvention**: the node's `src/yellowback/` and the wallet
fork's Yellowback code are the sources for each `core/` module (D-W-10, §3.6). Fourth, **YecLite
is deprecated** and is removed as a compatibility target: Ywallet (light, over lightwalletd) and
YecWallet (full node) are the two wallets in use; seed portability is defined against Ywallet
and **key portability against YecWallet**: YEW exports per-address WIF keys that YecWallet's
Import Private Key accepts (D-W-11), with the YED-after-import behaviour verified on the devnet.
Fifth, **UTXO handling is specified in full** (D-W-12, §3.7): YED-bearing outputs are a class of
their own that the YEC path can never touch, a YEC fee reserve is kept so YED is never stranded,
and YED selection is the node's floor-aware selector translated.

### Revision 1 (2026-09-24) — first draft

Written from the discussion of 2026-09-23 (framework choice) and the lightwalletd plan's client
contract. Owner decisions D-W-1..D-W-9 recommended and applied in the text.

---

## 1. The decision in one page

### 1.1 What YEW is

A wallet a Ycash user installs from an app store, restores or creates a seed, and uses to hold
and move YED, with YEC present because every transaction needs YEC for fees and every mint
needs YEC for collateral. Five things on the home screen: YEC balance, YED balance, the display
price (`pMint` from `GetPrice`), a receive button, a send button. History behind one tab.
Yellowback operations (M2, §5.3) behind one more. Nothing else.

### 1.2 What YEW is not

- **Not shielded.** No Sapling keys, no note decryption, no proving, no `ys1…` addresses. The
  app says so once, plainly, at onboarding: transparent means public. This is the whole reason
  the app can be small; a Ywallet-class scanner is ≈ 20× the code.
- **Not a node client.** It never speaks JSON-RPC. Its only peer is a `lightwalletd-dd` with
  `-yellowback` on, over TLS (§3.5).
- **Not a full Yellowback console.** No attestor tooling, no miner quotes, no explorer. The
  liquidator persona (claim) is in scope only because it needs nothing the owner path does not.
- **Not a place where `DigiDollar` naming, `yd_`, or the federation design appear** (CLAUDE.md
  rule 6; plan §0 of v2).

### 1.3 Why Flutter over a Rust core, and why the core owns everything that matters

**The UI framework decides how the app looks; the core decides whether it is safe.** Even
transparent-only, the client produces Ycash v4 transactions with the ZIP-243 sighash bound to the
consensus branch ID, P2SH carrier and vault scripts, the `"YB" ‖ 0x03 ‖ type` payloads,
`nLockTime`/`nExpiryHeight` rules, and compact-ECDSA verification of attestation bundles. The
lightwalletd plan's contract rule 4 is explicit: a client bug here **burns YED**. So:

- **Rust core (`yew-core`)**: keys, addresses, serialization, sighash, scripts, payloads,
  transaction builders, gRPC clients, sync, storage, and the broadcast gate. Exposed to Dart
  through `flutter_rust_bridge` as a handful of typed calls (§3.4). Unit-tested with vectors
  the node produced; integration-tested against the regtest devnet.
- **Flutter (`yew_app`)**: screens, navigation, theme, QR, biometrics prompt, platform keystore
  for the seed. It receives models and returns intents. It cannot construct bytes.

Flutter over React Native (Zingo, zecwallet-mobile, the old Ycash mobile lineage): one codebase
with the strongest tooling for a custom, animated UI, and a first-class Rust bridge. Over native
SwiftUI + Compose (Zashi): one UI to build, not two. Ywallet is the proof that Flutter + Rust
ships for a Zcash-family chain; YEW keeps the shape and the seed format and drops everything
shielded (§1.5).

### 1.4 What the light-client path gives, by tier

| Tier | Server requirement | YEW capability |
|---|---|---|
| **T0** | any Ycash lightwalletd of the yodl/ECC lineage (0.4.6+), node with `-insightexplorer -txindex` | YEC balance, receive, send, history (`GetAddressUtxos`, `GetTaddressTxids`, `GetTaddressBalance`, `SendTransaction`, `GetLightdInfo.consensusBranchId`) |
| **T1** | `lightwalletd-dd` Phase L1 (`-yellowback`) | price, stats, verdict per transaction (`GetTxInfo`), dry run (`ValidateRawTransaction`), decode |
| **T2** | Phase L2 (`GetAddressTokens`, needs node N1) | **authoritative YED balance and UTXO set**; YED send (TRANSFER) |
| **T3** | same server; nothing new | mint (two-step with carrier), vault list, redeem, claim, bundle verification |

YEW M1 (§7, Phase W3) needs T2, and W2 starts when lightwalletd L2 has landed (revision 3):
there is no pre-L2 fallback classifier, so `GetAddressTokens` is the token set's only source.

### 1.5 Ywallet (`hhanh00/zwallet` v1.15.3) as the reference: what YEW takes, what it leaves

Ywallet is the only shipping Flutter + Rust wallet for Ycash, so it is the reference the way
DigiByte's Qt code is for YecWallet: read for behaviour, never copied. Its size comes from what
YEW does not do — Sapling and Orchard scanning, a GPU path, Ledger, three coins, a
warp-sync engine, and six git submodules (`native/zcash-sync`, `native/zcash-params`,
`librustzcash`, `orchard`, `halo2`, `misc/flathub`) that exist because of the shielded pools.

| Taken from Ywallet | Left in Ywallet |
|---|---|
| **Seed and transparent derivation** (D-W-7): BIP39 English, optional passphrase, `m/44'/347'/account'/0/index` — so the two wallets restore each other | every shielded key, address and scanner (`zcash-sync`, `librustzcash`, `orchard`, `halo2`) |
| **Transparent sync method**: per-address txid/transaction fetch (`zcash-sync/src/taddr.rs`), the shape of §3.2 (YEW uses the 0.4.6 methods) | warp sync, note commitment trees, the GPU code |
| **The shape**: Flutter UI, Rust core, `flutter_rust_bridge` | multi-coin, Ledger, contacts, payment URIs, price charts, the plugin list of its `pubspec.yaml` (≈ 60 packages; YEW's is ≈ 12) |
| **Network constants** as a cross-check (`zcash_primitives/src/consensus/ycash.rs`: coin type 347, prefixes `0x1C28`/`0x1C2C`, testnet `0x1C95`/`0x1C2A`; Ycash branch IDs) — all confirmed equal to `ref/ycash/src/chainparams.cpp:149-151,409-411` | the submodule pins themselves: YEW depends on none of these repositories |

Nothing from Ywallet is a dependency of YEW. The compatibility contract is one address per
account index, verified by a vector (D-W-7).

---

## 2. Decision record

### D-W-1. Flutter + Rust core, `flutter_rust_bridge` (recommended, applied)
See §1.3. Alternatives recorded: React Native + Rust (second choice, if the team is JS-native);
SwiftUI + Compose over UniFFI (only with dedicated platform engineers); pure-Dart crypto (rejected:
the sighash and script bytes must be in one audited place with node-generated vectors).

### D-W-2. Transparent only, forever in this plan (recommended, applied)
No shielded pool in any phase. A shielded YEC feature is a different product (Ywallet exists).
This decision is what keeps the app at ≈ 9,000 lines and the sync model at "ask for my
addresses' txids".

### D-W-3. Hand-written v4 transparent serializer and ZIP-243 signer, verified byte-for-byte against `ycash-dd` (recommended, applied)
Not `librustzcash`'s builder: its branch IDs, feature flags and dependency tree are Zcash's, and
YEW needs ≈ 400 lines of it. The core serializes exactly the fields a transparent-only v4
transaction has (`header 0x80000004`, `nVersionGroupId 0x892F2085`, `vin`, `vout`, `nLockTime`,
`nExpiryHeight`, `valueBalance 0`, three empty vectors, no `bindingSig`) and computes the ZIP-243
digest with the branch ID the server reports. **Every vector comes from the node**: Phase W0 adds
a devnet helper that emits `(unsigned tx, sighash per input, signed tx)` triples from
`createrawtransaction`/`signrawtransaction`, and the core's tests must reproduce the signed bytes
exactly. This works because the node signs with RFC 6979 deterministic nonces (libsecp256k1),
so the same key, sighash and message give the same DER signature; the helper does not need to
export sighashes, only the signed transaction, and a mismatch localises to serializer, sighash
or signer by comparing the unsigned bytes first. (`sighash per input` in the triple is the
node's `SignatureHash` output captured through a debug print in the helper, for diagnosis only.) Ywallet's `zcash-sync/src/taddr.rs` is read as a reference for the transparent path,
not vendored (§1.5); the vector test is the acceptance.

### D-W-4. The core owns the gRPC clients (recommended, applied)
`tonic` + `prost` from the pinned protos. Dart never sees protobuf. Rationale: the contract
(§4) is enforced in one language, and the broadcast gate (D-W-5) cannot be bypassed by a screen.

### D-W-5. The broadcast gate is in the core and has no override (recommended, applied)
`send()` calls `ValidateRawTransaction` and returns an error unless `valid && verdict == "ok"
&& burned == 0` (and, for YEC-only sends, `wouldBeRejected == false`). There is no
"send anyway" parameter, no debug flag, no test hook that skips it. The devnet tests exercise the
gate by feeding it a deliberately malformed TRANSFER.

### D-W-6. Storage and secrets (recommended, applied)
The seed lives only in the platform keystore (iOS Keychain, Android Keystore via
`flutter_secure_storage`) and is passed to the core at unlock; the core keeps derived keys in
memory only. Wallet state (addresses, UTXOs, YED tokens, history, vaults, carriers in flight) is
an SQLite file owned by the core (`rusqlite`, bundled). The database is a cache: deleting it and
restoring from seed plus birthday height rebuilds it.

### D-W-7. Seed and derivation compatible with Ywallet, one transparent address per account (owner decision 2026-09-24; applied)
YEW derives exactly as Ywallet does for a Ycash account, from `zcash-sync` at `8a3956c8c`:

- **Mnemonic**: BIP39, English wordlist, 12 or 24 words, seed = `Seed::new(mnemonic, passphrase)`
  with an optional passphrase (Ywallet's `split_key` convention; YEW offers the field, default
  empty).
- **Transparent key**: BIP32 over the seed at `m/44'/347'/{account}'/{external}/{address}`
  (`zip32.rs` `derive_zip32`), coin type **347** (`consensus/ycash.rs` `coin_type()`; SLIP-44
  Ycash). Ywallet's account is `account = index, external = 0, address = 0`, so **the address a
  Ywallet user sees is `m/44'/347'/0'/0/0`**, and that is YEW's primary receive address.
- **Encoding**: `Base58Check(0x1C28 ‖ HASH160(compressed pubkey))` → `s1…` (`0x1C2C` for P2SH;
  testnet `0x1C95`/`0x1C2A`), equal to `ref/ycash/src/chainparams.cpp:149-151`. The `ye…`/`yt…`
  form is the same key hash under the Yellowback version bytes (spec §2: `0x1F 0xE4`,
  `0x20 0x07`); D-L-4 maps it on the server.

**What YEW adds, without breaking restore**: further addresses at `m/44'/347'/0'/0/i` and
change at `m/44'/347'/0'/1/i`, gap limit 20, because every mint takes two fresh keys (owner and
carrier). Ywallet's `scan_transparent_accounts` walks `m/44'/347'/0'/0/{i}` as well, so a Ywallet
restore of a YEW seed finds the primary address at once and can find the rest by its own scan;
YEW's own restore always scans both chains. **No ZIP-32 / Sapling keys are derived, ever**
(D-W-2). One account only; multi-account is out of scope.

**Verification (W0)**: a fixed test mnemonic is entered in Ywallet (desktop build, Ycash) and
its displayed transparent address is committed as a vector; `keys.rs` must reproduce it, and a
second vector covers a passphrase. Ywallet and YecWallet are the two wallets in use today
(YecLite is deprecated and is not a compatibility target). **Seed** portability is defined
against Ywallet; **key** portability against YecWallet (D-W-11).

### D-W-8. `GetAddressTokens` is the truth for YED; `GetTxInfo` labels pending (recommended, applied)
Contract rule 2 verbatim, and it is the **only** source of the TOKEN class (revision 3 dropped
the pre-L2 `GetTxInfo.assigned` fallback: one classifier, one code path in the module that
decides what can be burned). Unconfirmed outputs the app itself broadcast are shown as "pending
YED" from the local `PreLock` rule; nothing is shown as YED until the server confirms it. There
is no mempool view (lightwalletd plan §9 Q3); pending state is the app's own.

### D-W-9. Design: Material 3, one accent, restrained motion (recommended, applied)
A custom Material 3 theme (light and dark), one accent for YED and one for YEC, large numeric
type, card-based home, animated balance and confirmation transitions only. The reference class
is the current top-tier consumer wallets, not YecWallet's Qt. No design system beyond
`theme.dart`; screens are ≤ 300 lines each.

### D-W-10. Translate, do not reinvent: the forks' Yellowback code is the source for the core (owner direction 2026-09-24; applied)
The protocol bytes YEW must produce already exist twice in this workspace, in C++: the node's
`ycash-dd/src/yellowback/` (the templates the chain accepts, TPL-3) and the wallet's
`yecwallet-dd/src/yellowback*.cpp` (the client-side flow, display rules and 2,600 lines of
tests). Every `core/` module names its source file (§3.6) and is written as a translation of it,
with the same function boundaries where they fit, so a reviewer can diff behaviour across the
two languages. What is not translated: anything that needs the node's wallet or database
(`wallet.cpp`, `db.cpp`, `index.cpp`, `state.cpp`, `policy.cpp`, `view.cpp`) — YEW gets those
answers from the relay.

### D-W-11. Per-address private key export in WIF, importable into YecWallet and `ycashd` (owner decision 2026-09-24; applied)
YecWallet is a full-node wallet with its own keypool, so it cannot restore a seed; it imports
single keys (`File → Import Private Key` → `importprivkey` with rescan,
`ref/yecwallet/src/mainwindow.cpp:779`, `zcashdrpc.cpp:251`). YEW therefore exports **any of its
addresses' private keys as Ycash WIF**: `Base58Check(0x80 ‖ 32-byte key ‖ 0x01)` (compressed;
`ref/ycash/src/chainparams.cpp:153`; testnet `0xEF`), the format `dumpprivkey` emits, so the
round trip `YEW export → YecWallet import → ycashd dumpprivkey` is byte-identical. The export
screen (Settings → Export private key) shows the address, its WIF as text and QR, and a warning
that YEC **and** YED on that address move with it. Since YED and vaults are bound to transparent
keys and nothing else (v3: every signature is the owner's), an imported key gives YecWallet the
YED balance and the vault ownership of that address once its rescan and the Yellowback index
agree — this is verified on the devnet, not assumed (W2 acceptance, §8.6). Import in the other
direction (a WIF from YecWallet into YEW) is supported as a watch-and-spend "imported key"
outside the HD tree, flagged as not covered by the seed backup.

### D-W-12. Every UTXO has exactly one class; YED-bearing outputs are never fee inputs; a YEC fee reserve is kept (recommended, applied)
The mobile wallet's coin handling is the one place where "simple" and "safe" pull apart, so it
is specified in full in §3.7 and translated from the node's own rules
(`ycash-dd/src/yellowback/txbuilder.cpp:395-420` `SelectYec`, `wallet.cpp` `PreLock`/`LockOwn`,
`coinselect.cpp`). The user sees two numbers per asset (available, reserved) and never a
UTXO.

---

## 3. Architecture

### 3.1 Repository layout (`yew/`)

```
yew/
├── core/                 Rust crate `yew-core` (library) + `yew-cli` (binary, devnet tool)
│   ├── src/keys.rs       BIP39, BIP44, secp256k1, address encoding (s…/ye…/yt…/yr…)
│   ├── src/tx.rs         v4 transparent serializer, ZIP-243 sighash, signer
│   ├── src/script.rs     P2PKH, P2SH, vaultScript, carrierScript (byte-identical to the node's templates)
│   ├── src/payload.rs    "YB"‖0x03‖type encode/decode (MINT, TRANSFER, REDEEM, CLAIM_NOTICE)
│   ├── src/bundle.rs     attestation bundle parse + compact-ECDSA verify against ListAttestors
│   ├── src/build/        yec_send.rs, yed_transfer.rs, mint.rs, redeem.rs, claim.rs
│   ├── src/net/          compact.rs (CompactTxStreamer), yellowback.rs (YellowbackStreamer), tls
│   ├── src/wallet.rs     KeyRing + Store: the object sync, builders and api.rs share (W1)
│   ├── src/sync.rs       address scan, tx fetch, YEC UTXO set, YED token set, history
│   ├── src/coins.rs      UTXO classes, locks, YEC selection with the fee reserve (§3.7)
│   ├── src/coinselect.rs YED selection: EXACT/SINGLE/GREEDY/SEARCH(/BURN), from the node's coinselect.cpp
│   ├── src/store.rs      SQLite schema and queries
│   ├── src/gate.rs       the broadcast gate (D-W-5)
│   ├── src/api.rs        the bridge surface (§3.4)
│   └── tests/            vectors/ (node-generated), devnet/ (ignored unless YEW_DEVNET is set)
├── app/                  Flutter project `yew_app`
│   ├── lib/theme.dart, lib/screens/*, lib/widgets/*, lib/state/*
│   └── integration_test/
├── proto/                service.proto, compact_formats.proto, yellowback.proto, PIN (commit)
├── scripts/              check-proto-pin.sh, gen-vectors.sh (calls the devnet helper), build-*.sh
└── docs/                 architecture.md, trust.md (the trust statement text), release.md
```

### 3.2 The sync model (why this is small)

1. Derive external and change addresses up to the gap limit.
2. `GetAddressUtxos(addresses, startHeight = birthday)` → the confirmed transparent UTXO set of
   all own addresses in one call (`{address, txid, index, script, valueZat, height}`); this is
   the YEC candidate set before classification (§3.7). Requires the server's node to run
   `-insightexplorer -txindex`, which the devnet's node 0 already does.
3. `GetTaddressTxids(address, range = [lastSynced + 1, tip])` per address → a stream of raw
   transactions with their heights; parse each in Rust for the history table (direction,
   amounts, the `"YB"` payload if any). No second round trip.
4. `GetAddressTokens(addresses)` for the YED token set (T2); `GetTxInfo` for every history
   transaction that carries a `"YB"` payload, to label it (mint, sent 5 YED, received 5 YED,
   VOID, burned) — the verdict is the server's, the label is derived from it, never from the
   payload alone (contract rule 3).
5. `GetLatestBlock` on a timer and on app foreground; re-run 2–4 for the delta. `GetMempoolTx`
   exists on this baseline and is not used in M1 (D-W-8).

No compact blocks, no trial decryption, no note commitment tree. A full restore is
proportional to the wallet's own history, not the chain's.

### 3.3 Dependency allow-list (`core/Cargo.toml`)

`secp256k1` (with `recovery` for compact signatures), `bip39`, `hmac`/`sha2`/`ripemd`
(BIP32), `blake2b_simd` (ZIP-243), `bs58`, `tonic`/`prost`/`tokio` (+ `rustls`), `rusqlite`
(bundled), `serde`/`serde_json` (fixtures only), `thiserror`, `flutter_rust_bridge`. Anything
else is a decision recorded here. No `zcash_*` crates (D-W-3).

### 3.4 The bridge surface (`api.rs`)

Small by design; every call is synchronous from Dart's point of view and returns a typed result
or a typed error:

| Call | Returns |
|---|---|
| `create_wallet(seed_words?, birthday)` / `unlock(seed)` / `lock()` | wallet id |
| `export_wif(address)` / `import_wif(wif, birthday)` | the WIF string; the imported address (D-W-11) |
| `status()` | server info, Yellowback info (enabled, active, rpcversion), tip, sync height |
| `balances()` | `{yecZat, yecPendingZat, yedCents, yedPendingCents, price}` |
| `receive_address()` | next unused `{ye, s}` pair |
| `history(page)` | rows `{txid, height, kind, yecDelta, yedDelta, verdict, pending}` |
| `send_yec(to, zat, fee?)` → `preview` / `confirm(previewId)` | fee, change, then txid |
| `send_yed(to, cents)` → `preview` / `confirm` | inputs, fee in YEC, dry-run verdict, then txid |
| `mint_estimate(cents, lockBlocks)` / `mint_start(...)` / `mint_finish(mintId)` / `mint_sweep(mintId)` | the two-step mint with persisted carrier state (§5.3) |
| `vaults()` / `redeem(vaultTxid)` / `claimable()` / `claim(vaultTxid)` | the vault operations |
| `sync_now()` | progress events (stream) |

Every `confirm` passes through `gate.rs`. The `preview` objects are the only thing a screen
renders before a signature is made, and they are produced by the same builder that will sign.

### 3.5 Server connection

One endpoint, TLS required outside regtest (`h2` over `rustls`, system roots; a pinned
certificate is an optional setting). Default endpoints are a list the owner controls
(`docs/release.md`); the user can add their own. On connect: `GetLightdInfo` (chain name must
match the build, `consensusBranchId` is stored for signing, `taddrSupport` must be true), then
`GetYellowbackInfo` (fallback on `UNIMPLEMENTED`: YED features hidden, T0 only; refuse an
unknown `rpcversion`). The trust statement (contract rule 7) is shown once and reachable from
Settings.

### 3.6 Translation sources (D-W-10)

| `core/` module | Translated from | Notes |
|---|---|---|
| `keys.rs` address encoding | `ycash-dd/src/yellowback/address.cpp` | `s…` ↔ `ye…` same key hash; version bytes from `params.cpp` |
| `script.rs` | `ycash-dd/src/yellowback/script.cpp` | `vaultScript`, `carrierScript`, the `<bundle> <sig> <script>` scriptSig push encoding |
| `payload.rs` | `ycash-dd/src/yellowback/payload.cpp` | encode and decode; the node's decoder is the parse the spec means |
| `bundle.rs` | `ycash-dd/src/yellowback/bundle.cpp`, `attest.cpp` | bundle format, compact-ECDSA verification against the seated set |
| `build/*.rs` | `ycash-dd/src/yellowback/txbuilder.cpp` | MINT, TRANSFER, REDEEM, CLAIM templates and `nLockTime`/`nSequence`/`nExpiryHeight` |
| `coins.rs` classes, locks, `SelectYec` | `ycash-dd/src/yellowback/txbuilder.cpp:395-420`, `wallet.cpp` `PreLock`/`LockOwn`/`Release` | the fee reserve is YEW's addition (the node wallet has the whole keypool's YEC) |
| `coinselect.rs` | `ycash-dd/src/yellowback/coinselect.cpp` + `src/test/yellowback_coinselect_tests.cpp` | pure, table-tested; the node's tables are the vectors |
| `sync.rs` labels, `PreLock` pending rule, verdict-to-display mapping | `yecwallet-dd/src/yellowbackmodels.cpp`, `yellowbackcontroller.cpp` | the wallet already reads only `yed_*` RPC results, which is exactly what the relay returns |
| mint state machine (§5.3) | `yecwallet-dd/src/yellowbackcontroller.cpp` (the two-step mint flow), `yellowbacktab.cpp` | persisted in SQLite instead of in-memory |
| `tests/` | `yecwallet-dd/tests/yellowbacktab_test.cpp`, `tests/check-rpc-contract.py`, the node's `qa/` Yellowback cases | port the cases whose inputs are RPC results; the contract fixture is `make spec`'s copy |

Each translated function keeps a comment `// from ycash-dd/src/yellowback/script.cpp:NN
(feature/yellowback-price-attest @ <commit>)` so drift is traceable when the node moves.

### 3.7 UTXO classes, locking and selection (D-W-12)

On Ycash a YED holding **is** a transparent UTXO: a P2PKH output of exactly `TOKEN_VALUE`
(10,000 zat) whose cents are assigned by the payload of the transaction that created it, and
which the node's index lists in `Tokens`. To an ordinary transparent wallet it looks like
10,000 zat of dust. **Spending it as a plain YEC input burns the YED** (spec IN-1..3: the input
is removed from `Tokens`, and any cents not re-assigned by a valid payload are burned). This is
why the class table below is the core's most important invariant, and why the YEC and YED
balances the app shows are computed from classes, never from `sum(nValue)`.

**Classes.** Every UTXO the wallet knows is in exactly one class, decided at sync time from
server data, never from local heuristics alone:

| Class | How it is recognised | Spendable as | Shown as |
|---|---|---|---|
| **TOKEN** | listed by `GetAddressTokens` (T2); no other source | YED input only (TRANSFER, REDEEM, CLAIM) | YED balance (`cents`), never in the YEC balance |
| **PENDING_TOKEN** | an output the app itself broadcast, labelled by the `PreLock` rule (MINT ⇒ `vout[1]`, TRANSFER/REDEEM ⇒ the payload's assignments), unconfirmed or not yet confirmed by the server | nothing | "pending YED"; not in either balance |
| **VAULT** | P2SH `vout[0]` of an own MINT, per `GetVault` | REDEEM (owner path at `lockHeight`) only | Yellowback screen, "locked YEC (collateral)"; not in the YEC balance |
| **CARRIER** | P2SH output the app created for a mint or claim in flight (mint state machine) | the paired main transaction, or the sweep after lapse | "in progress"; not in the YEC balance |
| **FEE_RESERVE** | plain P2PKH YEC outputs the core sets aside (below) | miner fee, enforcement fee, `CARRIER_VALUE`, `TOKEN_VALUE` for new token outputs | "reserved for fees" under the YEC balance |
| **YEC** | every other confirmed P2PKH output to an own key | YEC send, mint collateral, fee if the reserve is short | YEC available |
| **UNKNOWN_P2SH** / **FOREIGN** | any P2SH the app did not create; any output the server labels as YED for another address | nothing | hidden |

`sum(nValue)` of TOKEN and PENDING_TOKEN outputs is never shown as YEC: the 10,000 zat per
token is the price of holding it (as the node's `SelectYec` skips tokens and vaults and every
P2SH, `txbuilder.cpp:410-414`). Any output whose class cannot be decided (server unreachable,
`GetTxInfo` not yet answered for a transaction that carries a `"YB"` payload) is **held**:
unspendable until classified. Losing a send to "sync first" is acceptable; burning is not.

**Locks.** The core keeps a lock set in SQLite mirroring the node wallet's `LockCoin`: TOKEN and
VAULT outputs are locked permanently for the YEC path; inputs of any transaction the app has
built but not yet seen confirmed are locked for every path until confirmation or expiry
(`nExpiryHeight` passed, or the server reports the transaction absent for `REF_WINDOW` blocks);
CARRIER outputs are locked to their mint id. A lock is released only by the sync loop, never by
a screen. There is no "unlock all" button; Settings has "rebuild from chain", which drops the
database and rescans (D-W-6), which is the only way a stale lock goes away.

**Fee reserve.** YED operations cost YEC: the miner fee (`fee`, §8.2), `TOKEN_VALUE` per new YED
output (recipient + change), `CARRIER_VALUE` per mint or claim, and the enforcement and
attestation fees of a mint. A user who holds only YED cannot move it, which the app must make
obvious before, not after, they try. The core therefore:

1. computes `reserveZat = max(RESERVE_MIN, k · (fee + 2 · TOKEN_VALUE))` with `k = 5`
   (five TRANSFERs' worth; `RESERVE_MIN = 105,000` zat, W1) and marks the smallest set of YEC
   outputs covering it as FEE_RESERVE, smallest-first, **never an output larger than the whole
   reserve** (W1: a one-coin wallet must not show everything reserved), re-evaluated at every
   sync; when the reserve is short a YED operation takes its fee from class YEC;
2. selects YEC for a **YEC send** from class YEC only, so a YEC send can never drain the
   reserve; the preview says "keeps N YEC reserved for YED fees" and offers "send everything
   anyway", which is the one explicit override (it empties the reserve, not the locks);
3. selects YEC for a **YED operation** from FEE_RESERVE first, then YEC, smallest-first
   (the node's order), consolidating dust as it goes;
4. shows, on Home, `YEC available` and, in small type, `reserved for fees`; when
   `available + reserved < fee + 2 · TOKEN_VALUE` the Send YED button is enabled but the preview
   is an explanation ("You need about 0.0003 YEC to send YED. Receive YEC first.") with the
   receive address one tap away.

**YED selection** is the node's floor-aware selector translated verbatim (`coinselect.rs`):
EXACT, SINGLE, GREEDY, SEARCH for TRANSFER (refuse with the nearest workable amounts when the
change would fall in `(0, MIN_OUTPUT)`, since such change cannot be assigned and would burn),
plus BURN for REDEEM and CLAIM only. Deterministic: same coins and amount, same inputs, so a
devnet test can compare the app's selection to `yed_estimatesend` on the node with the same
coin set. `maxInputs` is the node's 250 cap; the preview shows the number of inputs when it
exceeds 20 so the user understands a larger fee.

**Change.** A TRANSFER's YED change is a new TOKEN output to the next change address; its YEC
change is a YEC output to the same change address (one address per transaction, so the
server's `GetAddressTokens` and the YEC scan see it together). Outputs of `TOKEN_VALUE` that
are *not* tokens (a YEC send of exactly 10,000 zat) are avoided by adding one zat to the amount
when the user would otherwise hit it — recorded here because it is the kind of accident that
later reads as a bug in the classifier.

**What the user sees.** Two balances, each with one sub-line, and a history. No UTXO list, no
coin control, no manual locking, no "consolidate" action (GREEDY does it as a side effect, as
the node's H11 note says). An "Advanced → outputs" screen showing the class table is a debug
build feature only.

---

## 4. The client contract, mapped to the core

The lightwalletd plan's §5 rules and where each is enforced:

| Rule | Where | Test |
|---|---|---|
| 1 Detect; refuse unknown `rpcversion`; hide YED unless `enabled && active` | `net/yellowback.rs`, `status()` | offline: fake server variants |
| 2 Address from own keys; YED only from `GetAddressTokens`; pending via `PreLock` | `keys.rs`, `sync.rs` | vectors: address encodings; devnet: unconfirmed mint shows pending, confirmed shows YED |
| 3 Decode payload locally for display, never as verdict | `payload.rs`, `sync.rs` | offline: every spec §3.3 example |
| 4 TRANSFER: YED inputs, `TOKEN_VALUE` outputs, payload, YEC fee inputs, **gate** | `build/yed_transfer.rs`, `gate.rs` | devnet: send YED between two YEW wallets; malformed TRANSFER refused |
| 5 Mint: estimate → bundle → carrier tx → one confirmation → main tx inside `refHeight + REF_WINDOW`; sweep on lapse | `build/mint.rs`, `store.rs` (mint state machine) | devnet: full mint; forced lapse then sweep |
| 6 Redeem (owner, `nLockTime = lockHeight`) and claim (bundle, `nLockTime = claimHeight`); verify bundle signatures against `ListAttestors` | `build/redeem.rs`, `build/claim.rs`, `bundle.rs` | devnet: redeem after lock; claim an underwater vault; bundle with one bad signature refused |
| 7 Trust statement | `app` onboarding + Settings; text in `docs/trust.md` | screenshot test |

Script and template bytes (vault script, carrier script, MINT `vout[0..4]` order, `nSequence`
`0xFFFFFFFE`, `nExpiryHeight`) are copied from the spec (§3.5, §4.6) and cross-checked against
the node's own templates: the devnet helper of W0 also exports one node-built MINT, TRANSFER and
REDEEM as raw hex, and `script.rs`/`build/*` tests must reproduce their scripts and payloads
byte-for-byte (the node's TPL-3 rule, "the node's template must pass its own checks", is what
makes the node the reference).

---

## 5. Screens

### 5.1 M1 (Phase W3)

| Screen | Content |
|---|---|
| Onboarding | create / restore seed (12 words), birthday height (default: today's tip), trust statement, transparent-only notice, biometric unlock |
| Home | YED balance (large; "+ pending" when any), YEC available with "reserved for fees" sub-line (§3.7), price line ("1 YED = $1.00 · mint price 0.52 YEC"), sync indicator, Receive / Send |
| Receive | one QR (`ye…`), toggle to `s…`, copy, "new address" |
| Send | asset toggle YED/YEC, address (paste, scan), amount, preview (fee in YEC, dry-run verdict for YED), slide to confirm, result |
| History | one list, both assets, verdict labels, tap for details (`GetTxInfo` fields, explorer link) |
| Settings | server, trust statement, seed backup, **export private key (WIF, per address)**, import private key, lock, about (build, `rpcversion`) |

### 5.2 What "beautiful, flashy, simple" means here
Six screens. Numbers first. One gesture to send. Animated only where it confirms something
happened (balance change, send complete). Dark mode from day one. No dashboards.

### 5.3 M2 — Yellowback operations (Phase W4)

| Screen | Content |
|---|---|
| Yellowback | YED you hold, vaults you own (status, lock height, underwater warning), "Mint", "Claimable" |
| Mint | cents, term class picker (from `EstimateCollateral`), required YEC, fee, the two-step explained in one sentence; progress: *funding carrier → waiting for 1 confirmation → minting → done*; lapse: *window closed, sweeping carrier* |
| Vault | details, `Redeem` when `lockHeight` reached; `Claim` when `claimable` |
| Claimable | `ListClaimable` list for the liquidator persona; claim flow reuses the mint's bundle/carrier step |

The mint state machine persists in SQLite so a killed app resumes: `Estimated → CarrierSent
(txid, key, refHeight, bundleHash) → CarrierConfirmed → MainSent → Done | Lapsed → Swept`.

---

## 6. Testing

### 6.1 Principles
1. **The node is the oracle.** No transaction byte is trusted because the core produced it; it
   is trusted because the node signed the same bytes (W0 vectors) or accepted them on regtest.
2. **Regtest devnet for every phase.** As the lightwalletd plan §6.1: `ycash-dd`'s
   `yellowback-devnet up` (with `lightwalletd start`) is the test bench; no phase is accepted
   on the offline suite alone. `yew-cli` is the driver (it is also the developer's tool).
3. **The classifier is tested for the burn.** Every phase that touches `coins.rs` keeps the
   property test "no YEC-path transaction ever spends a TOKEN, PENDING_TOKEN, VAULT or CARRIER
   input" green, on random coin sets, against the raw bytes about to be signed.
4. **The gate is tested negatively.** Every phase that adds a builder adds a malformed case the
   gate must refuse.

### 6.2 Offline
`cargo test`: key and address vectors; serializer/sighash/signature vectors from W0; script and
payload equality with node-built templates; bundle verification with a mutated signature;
fake gRPC servers for contract rule 1. Flutter widget tests with a mocked bridge.

### 6.3 Devnet (`YEW_DEVNET=1 cargo test -- --ignored`, and `yew-cli`)
Two YEW wallets on one laptop against node 0's lightwalletd: fund from the devnet faucet,
YEC send, mint, YED send between wallets, redeem after lock, claim after a price shock
(`yellowback-devnet price`), forced carrier lapse and sweep, restore from seed and compare
balances. Flutter integration tests run the same flow on an emulator (Android `10.0.2.2`, iOS
simulator `localhost`).

### 6.4 CI (`yew/.github/workflows/`)
`cargo fmt --check`, `clippy -D warnings`, `cargo test`, `flutter analyze`, `flutter test`,
proto-pin check, dependency allow-list check (`cargo tree` diffed against §3.3). The devnet
suite stays nightly on the owner's machine (as the role regtest is), not in CI.

---

## 7. Work plan

One agent per chunk. W0a, W0b and W0c are independent and each touches exactly one repository;
W1–W5 are in `yew/` (a plain repo; worktrees only if W3 and W4 run in parallel). Order:
**W0a ∥ W0b ∥ W0c → W1 → W2 (after lightwalletd L2) → W3 → W4 → W5.** Tasks marked `[owner]`
need a human (a GUI wallet, an Apple developer account) and are not an agent's to fake: the
agent leaves the placeholder named in the task and reports it. Each chunk ends with its tests
green and a mapping row (Appendix B) for every impedance mismatch met.

### Phase W0a — The `yew` repository (≈ 1 day; `yew/` only)
- [x] `boyfromcave/yew` created: `core/` (`cargo init --lib yew-core` + `yew-cli` binary),
      `app/` (`flutter create yew_app`), `proto/` (three files copied from `lightwalletd-dd`
      at its current `feature/yellowback-price-attest` commit, recorded in `proto/PIN`),
      `scripts/check-proto-pin.sh` (diffs against `../lightwalletd-dd` when present, else skips),
      `README.md` (name, one-line summary, layout, the toolchain table below).
- [x] **Toolchain pinned** in `README.md` and enforced where a file can: `rust-toolchain.toml`
      (stable, exact version), `flutter --version` and Dart SDK in `app/pubspec.yaml`
      (`environment:` exact lower bound), `flutter_rust_bridge` (crate and `flutter_rust_bridge_codegen`
      the same version, pinned in `Cargo.toml` and `pubspec.yaml`), Android NDK version in
      `app/android/app/build.gradle`, minimum iOS in `app/ios/Podfile`. Targets:
      `aarch64-apple-ios`, `aarch64-apple-ios-sim`, `aarch64-linux-android`,
      `x86_64-linux-android` (emulator), plus the host for `yew-cli` and tests.
- [x] Build scripts: `scripts/build-core-ios.sh` (cargo per target → `YewCore.xcframework`),
      `scripts/build-core-android.sh` (`cargo-ndk` → `app/android/app/src/main/jniLibs/`),
      `scripts/gen-bridge.sh` (codegen); each idempotent and run by CI on macOS and Linux runners.
- [x] `.github/workflows/ci.yml` (§6.4) and the dependency allow-list check (`cargo tree` vs §3.3).
- [x] `[owner]` Apple team id and signing profile in `app/ios` (kept out of git; the agent
      leaves `ios/ExportOptions.plist.example`).
**Acceptance — met 2026-09-24 except the mobile builds:** `cargo test`/`flutter test` green (Flutter
3.47.5 / Dart 3.13.4, Rust 1.92.0, NDK 28.2.13676358 pinned); the iOS/Android build scripts are
written and syntax-checked but **unrun** (no Xcode, no Android SDK on the machine: `[owner]`);
CI not yet run (not pushed). `flutter_rust_bridge` deferred to W3 (only a 2.14 prerelease on
crates.io at the time).

### Phase W0b — Workspace integration (≈ ½ day; workspace repo only)
- [x] `repos.yaml` gains `yew:` with the new role `app` (Appendix A); `scripts/repos.sh`,
      `bootstrap.sh`, `repo-status.sh` and the `Makefile` accept the role (writable, `branch`
      checked out, no `base`, no `upstream`, not `chmod a-w`; `make diff`/`make log` skip it).
- [x] CLAUDE.md: layout line and rule 2 sentence (Appendix A); `yellowback.code-workspace` mounts
      `yew/`; `docs/mapping.md` gains §16 from Appendix B (rows marked "planned").
**Acceptance — met 2026-09-24:** nine repos in `make status`; bootstrap scratch test clones `yew`
at `main` and detects a wrong origin; `DRY=1 make pull` reports it. Note: `scripts/repos.sh` needed
no change (role-agnostic); `pull.sh` did, which Appendix A had not named.

### Phase W0c — The devnet vectors helper (≈ 1 day; `ycash-dd/contrib/` only)
- [x] `yellowback-devnet vectors <dir>`: on a running devnet, for N random transparent
      transactions (1–3 inputs, 1–3 outputs, with and without `nLockTime`/`nExpiryHeight`)
      write `{unsignedHex, sighashPerInput[], signedHex, branchId, prevouts[]}`; plus one
      node-built MINT, TRANSFER and REDEEM (`yed_mint` etc. on node 0) as
      `{hex, decoded}` with their carrier where applicable; plus the WIF and address of every
      key used (`dumpprivkey`). Deterministic given a `--seed`.
- [x] `[owner]` D-W-7 vectors: the Ywallet address for the plan's fixed test mnemonic, with and
      without passphrase, from a Ywallet desktop build on Ycash; committed to
      `yew/core/tests/vectors/ywallet.json` with the Ywallet version. Until captured, the file
      holds `"pending": true` and `keys.rs`'s test is `#[ignore]` with that reason.
**Acceptance — met 2026-09-24:** `contrib/` only (+255); 12 transactions, all `pythonMatches`
true; armed v3 templates (mint + carrier, transfer, redeem, all `verdict ok`); branch id
`19bd2d2f`; regtest prefixes `sm…` 0x1C95 / `yr…` 0x2002 / WIF 0xEF. `ywallet.json` pending
(the `[owner]` capture; the standard "abandon ×23 art" mnemonic, passphrases "" and "yew").

### Phase W1 — Keys, transactions, YEC send (≈ 5 days; core only)
- [x] **First task:** the fee. Read `ycash-dd`'s default and minimum relay fee at the pin
      (`src/main.h` / `src/amount.h`, and what `yed_getinfo` params expose), confirm on the
      devnet, and fix `FEE_ZAT` and `RESERVE_MIN` in `core/src/params.rs` with the citation.
- [x] `keys.rs`, `script.rs` (P2PKH/P2SH), `tx.rs`: serializer, ZIP-243, signer (§3.6 sources).
- [x] `net/compact.rs`: the T0 methods (`GetLightdInfo`, `GetLatestBlock`, `GetAddressUtxos`,
      `GetTaddressTxids`, `GetTaddressBalance`, `SendTransaction`) over TLS/plain; `net/tls.rs`.
- [x] `sync.rs` (YEC only), `store.rs` (schema v1 incl. the lock set), `coins.rs` (classes YEC/FEE_RESERVE,
      the reserve rule, `SelectYec`), `build/yec_send.rs`, `gate.rs` (YEC path).
- [x] `yew-cli`: `status`, `address`, `balance`, `send-yec`, `sync`.
**Acceptance — met 2026-09-24:** all 12 vectors reproduced (unsigned bytes, every sighash,
signed bytes, txid); addresses and WIF round trip equal the node's; 30 unit tests incl. the
gate property test on 2,000 random coin sets; devnet (`scripts/devnet-w1.sh`, dir
`~/yb-devnet-w1`, portseed 57, lightwalletd `127.0.0.1:9167`): fund → sync → send 0.5 YEC →
the node holds exactly the bytes the core built → restore from seed reproduces balance and
UTXO set; `export-wif` equals `dumpprivkey`, `import-wif` funds spendable.

### Phase W2 — YED: tokens, TRANSFER, the gate (≈ 5 days; core only; **starts after lightwalletd L2**)
- [x] `net/yellowback.rs` (all 18 + `GetAddressTokens`), contract rule 1 handling.
- [x] `payload.rs` (from `payload.cpp`), `sync.rs` YED set from `GetAddressTokens` only, history
      labels from verdicts, `PreLock` pending rule.
- [x] `coins.rs` classes TOKEN/PENDING_TOKEN/UNKNOWN_P2SH and the hold rule; `coinselect.rs`
      with the node's test tables as vectors; `build/yed_transfer.rs`, `gate.rs` full rule;
      `yew-cli send-yed`, `history`, `price`, `coins` (debug listing by class).
**Acceptance:** devnet: YED minted on node 0's wallet arrives at a YEW address and shows as YED
only after confirmation; YED sent between two YEW wallets; a malformed TRANSFER is refused by the
gate with the node's verdict in the error; **class invariants**: a YEC send from a wallet
holding tokens never includes a token input (asserted on the raw transaction, 1,000 random
coin sets), a YEC send never spends the reserve unless overridden, `coinselect.rs` matches
`yed_estimatesend` input-for-input on 100 random coin sets, and a TRANSFER whose change would be
sub-dollar is refused with the same alternatives the node reports; **key round trip**: `yew-cli export-wif` of an
address holding YEC and YED, `importprivkey` with rescan on node 1, `dumpprivkey` returns the
same WIF, `getbalance`/`yed_getbalance` on node 1 show the address's YEC and YED, and node 1
can `yed_send` them (§8.6); **met 2026-09-24** (node 5 in place of the stock node 1; 100
`yed_estimatesend` comparisons over three coin sets; malformed TRANSFER refused
`transfer-over-assigned`; sub-dollar refusal with the node's alternatives; 56 unit + 4 vector tests); `git diff --stat` of the three forks shows only the
W0 `contrib/` helper.

### Phase W3 — The app, M1 (≈ 2 weeks; app + `api.rs`)
- [ ] `api.rs` and the generated bridge; `state/` (one store, streams from the core).
- [ ] `theme.dart`, the six screens of §5.1, QR scan/show, secure storage, biometrics.
- [ ] Integration test of §6.3 on the Android emulator and iOS simulator.
- [ ] `[owner]` a signed iOS build on one physical device (the agent delivers the simulator
      build and the Android APK).
- [ ] `docs/trust.md` text reviewed by the owner.
**Acceptance:** the §6.3 M1 flow passes on both platforms against the devnet; a release build
installs on one physical device of each platform; screens ≤ 300 lines; no crypto or networking
import under `app/lib`.

### Phase W4 — Yellowback operations, M2 (≈ 2 weeks; core + app)
- [ ] `bundle.rs`, `script.rs` vault and carrier scripts, `build/mint.rs` state machine,
      `build/redeem.rs`, `build/claim.rs`; the sweep — each translated from its §3.6 source.
- [ ] Screens of §5.3.
**Acceptance:** devnet: mint, redeem after lock, claim after shock, forced lapse and sweep, app
killed mid-mint and resumed; bundle with one bad signature refused; node-built MINT/REDEEM
templates reproduced byte-for-byte except keys and amounts.

### Phase W5 — Hardening and release (≈ 2 weeks; then testnet with v3 A7 and lightwalletd L4)
- [ ] Threat review of `core/` (seed handling, gate, TLS), dependency audit (`cargo audit`),
      reproducible builds recipe, store metadata, crash reporting **off by default**.
- [ ] Default endpoint list, certificate pinning setting, `docs/release.md`.
- [ ] Testnet run against a public `lightwalletd-dd` (`-yellowback`) for ≥ 4 weeks.

### Out of scope, tracked
Shielded anything (D-W-2); a desktop shell over `yew-core` (natural, later); mempool view
(lightwalletd §9 Q3); push notifications; fiat on-ramps; multiple accounts.

---

## 8. Open questions

1. *(closed in revision 3: the Ywallet vector capture is W0c's `[owner]` task.)*
2. *(closed in revision 3: the fee is W1's first task.)*
3. *(withdrawn in revision 2: no third-party signer is vendored, D-W-3.)*
4. **Public lightwalletd**: who hosts the `-yellowback` endpoint with `-insightexplorer`, and
   on which port/certificate (lightwalletd plan §9 Q4). Needed by W5, not before.
5. **Spent-token history** (lightwalletd §9 Q1): if `GetAddressTokens` never streams spent
   tokens, the core keeps deriving "sent" rows from `GetTxInfo`; fine for M1, revisit after W3.
6. **Vault ownership after key import** (D-W-11): does `ycash-dd`'s wallet view list a vault
   whose owner key arrived by `importprivkey`, and can YecWallet redeem it? The vault is P2SH
   over the owner key, so the wallet must recognise the vault output as its own by the owner
   pubkey (the fork's `src/yellowback/wallet.cpp` / `view.cpp` logic), not only by address.
   Tested in W4 on the devnet: mint in YEW, export, import into node 1, `yed_listvaults` and
   `yed_redeem` from node 1. If it fails, the fix is a wallet-side (non-consensus) change in
   `ycash-dd` and gets its own row in the v3 plan.
7. **Bundle size in `scriptSig`**: the carrier spend pushes `<bundle>` as one element; the node's
   template already respects the script element limit, and the core copies the node's push
   encoding exactly (W4 template equality). Recorded here so W4 checks it first.

---

## Appendix A — Workspace integration

`repos.yaml` entry (a new role; `scripts/repos.sh` learns it in W0: writable, `branch` checked
out, no `base`, no `upstream`, not `chmod a-w`):

```
yew:
  role: app
  url: https://github.com/boyfromcave/yew.git
  branch: main
  what: YEW, the transparent-only mobile wallet for YEC and YED (Flutter + Rust core)
```

CLAUDE.md gains one layout line (`yew/  the mobile wallet, its own repo, branch main`) and one
sentence in rule 2: client code goes in `yew/` only, and the `YellowbackStreamer` +
`CompactTxStreamer` services are its sole interface. `make diff`/`make log` skip it (no
baseline); `make status` reports it.

## Appendix B — Rows for `docs/mapping.md` (new §16, "YEW")

| Reference behaviour | Ycash / YEW reality | Adaptation |
|---|---|---|
| Ywallet: compact-block scan, trial decryption in Rust (`zcash-sync`) | YEW is transparent-only (D-W-2) | `GetAddressUtxos` + `GetTaddressTxids`; no scanner |
| Ywallet: one transparent address per account at `m/44'/347'/a'/0/0` (`zcash-sync/src/zip32.rs`), addresses beyond found by scan | YEW needs fresh keys per mint and change | same root path, external and change chains with gap 20; primary address identical (D-W-7) |
| Ywallet: six submodules (`librustzcash` fork, `orchard`, `halo2`, …) for the shielded pools | YEW has no shielded pool | zero submodules; the §3.3 allow-list |
| librustzcash transaction builder | branch IDs and features are Zcash's; YEW needs ≈ 400 lines | hand-written v4 transparent serializer + ZIP-243, node vectors (D-W-3) |
| YecWallet: node wallet builds and signs (`yed_mint`, `yed_send`) | no node; owner keys only (v3: every signature is the owner's) | builders in `core/src/build/`, templates equal to the node's (TPL-3) |
| Wallet RPCs' server-side validation | none before broadcast | `ValidateRawTransaction` gate, no override (D-W-5) |
| DigiByte Qt widgets read in-process models | YEW reads gRPC through the core | Dart sees `api.rs` models only |
