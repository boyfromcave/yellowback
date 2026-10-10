# Quantum line Q7 preparation: client-impact survey (DRAFT, for the coordinator)

Client-survey agent, 2026-10-10. This survey was read-only on every repository. Nothing was built, run or committed.

**Inputs**
- Quantum plan rev 2: §2, §4.4, §4.6, §4.7, §7 and the §8 Q7 row.
- `wt/BRIEFING-quantum.md`.
- **The frozen node spec `wt/QUANTUM-SPEC-draft.md`.** Where the plan and the spec differ, this inventory follows the spec:
  - F-1: `TX_PQPKH` is 35 bytes, with the scheme as `OP_1`/`OP_2`.
  - F-2: payload version 0x04 for every type.
  - F-3: the residual pays `PQPKH(owner)`.
  - F-4: PQ address versions `ye 0x56BF`, `yt 0x571E`, `yr 0x5710`, 53 characters.
  - F-7: the `TOK-PQ` rule applies only after Falcon.
  - A-3: `yed_mint` keeps its six arguments.
  - A-13: `yed_getnewaddress` stays P2PKH until Falcon.
  - §6.2: the rpcversion 7 delta.

**Trees surveyed:** the main checkouts on `upgrade/vault`.

| Repo | HEAD |
|---|---|
| yecwallet-dd | `9c331d7` |
| yew | `6eb6712` |
| lightwalletd-dd | `f0746e4` |
| chain-viz | `96e0a5b` |
| x402-ycash | `aba74af` |
| hawkeye | `bdd0e1a` |
| yolo | `d41274f` |
| ycash-dd devnet | `ec9abe852` |
| ycash6 devnet | `0f150defb` |
| yb-calibration | `main` `d769b95` (= its `upgrade/quantum-vaults`) |
| wyec | `main` `d2e382b` |

**How it was done:** six read-only sub-surveys covered one or two repos each. I spot-checked their citations. Two scratch dependency resolutions were run with `cargo metadata` only, under `wt/scratch/q-clients/` (nothing compiled). Crate sources were downloaded to `wt/scratch/q-clients/dl/` and read.

---

## 0. Findings that change the plan or the spec (read first)

| # | Finding | Effect | Recommendation |
|---|---|---|---|
| **C-1** | **F-2 (payload version 0x04 for every type) is a fund-loss hazard for every client that builds a TRANSFER itself.** Three clients hard-code version 3: YEW `core/src/payload.rs:36` (`VERSION = 0x03`, written at `:285`), x402 `packages/ycash/src/yed/payload.ts:12,395` and `python/x402_ycash/yed/payload.py:18,203`. On the quantum line a v3 payload is "non-Yellowback" (`ycash-dd/src/yellowback/payload.cpp:376`, V23), so the YED inputs of that transaction are **burned**. Decoders that reject version ≠ 3 will also stop seeing YED: chain-viz `src/classify.rs:32,119`, YEW `payload.rs:469`, x402 `payload.ts:353` / `payload.py:181`. | YEW and x402 cannot ship a single binary that speaks both `upgrade/vault` and the quantum line. | Make the payload version a per-chain value chosen by `rpcversion` (≥ 7 → 4), not a constant. Add a guard test: "refuse to build a v3 TRANSFER against an rpcversion-7 server". Q7 must land in YEW and x402 **before** any quantum devnet is used for YED payments. |
| **C-2** | **The plan says x402 needs nothing ("none until YED channels", §4.7, §8). That is wrong.** x402 already ships YED exact payments and YED batch channels. It hard-codes the 20-byte `ye…` codec, the 25-byte P2PKH shape, P2PKH-sized fee estimation and DER-only scriptSig checks (§6 below). | x402 is an M task. | Add x402 to the Q7 scope list. |
| **C-3** | **YED channels conflict with `TOK-PQ` (F-7).** x402 funds a YED channel into a **P2SH** 2-of-2 secp256k1 output (`channel/yed.ts:5-8`). After `pqFalconActive`, every assigned token output must be `TX_PQPKH` scheme 2, so channel funding becomes invalid. A PQ redeem script cannot hold an 897-byte key (520-byte element). | This is a product decision, needed before Falcon activation. | Owner decision at Q8, with three options: (a) exempt P2SH holders from `TOK-PQ` (weakens the PQ guarantee for channel balances); (b) retire YED channels when Falcon activates; (c) redesign channels on a template. Record it in plan §9. |
| **C-4** | **hawkeye cannot get a PQ owner through its permitted interface.** Its `lock` builds the V itself, because `vault_lock` has no `data` parameter (open CR-N1). It takes the owner from `getnewaddress`/`validateaddress.pubkey` (`crates/hawkeye/src/cli.rs:123-143`). It may not call `yed_*`, and spec §6.2's `yed_getnewaddress "pqowner"` is a `yed_*` RPC. | `hawkeye lock` is blocked. | A node CR on the `vault_*` surface. Either (a) CR-N1 lands (`vault_lock` gains `"data"`) and hawkeye switches to `vault_lock` with a default wallet SLH-DSA owner; or (b) add `vault_getnewowner` → `{owner: pqkeyid}`. (a) also removes hawkeye's hand-built V. Needs a spec §6.2 row. |
| **C-5** | **The plan's fee wording overstates the change at the default.** `-pqfeerate` defaults to 1× the 100 zat/KB relay floor. An SLH-DSA owner spend is 7,939-byte scriptSig, about 8.1 KB of transaction, which is ≈ 810 zat, so `max(1000, 810)` = **1,000 on ycash-dd: unchanged**. Size pricing binds above ≈ 1.23× for owner spends and ≈ 5.9× for Falcon holder spends. `VAULT_RPC_FEE` 10,000 binds up to ≈ 12×. **ycash6 already prices by size:** its wallet fee is `max(yellowbackfee, ZIP-317 conventional)`, and an 8.1 KB input is ≈ 55 actions ≈ **27,500 zat**. ycash6's ZIP-317 relay limits are off by default (`ycash6/src/zip317.h:25-54`), so 1,000 still relays there. | Clients that compute fees (YEW, x402, hawkeye's devnet fallback, yb-calibration) give different answers per node line. Spec §6.2 exposes no rate. | Add `pq.feeRateZatPerKB` (the node's effective `-pqfeerate`) to `yed_getinfo.params.pq` in spec §6.2. Clients compute `max(DEFAULT_FEE, rate × size)` from it. yb-calibration states both lines' formulas. |
| **C-6** | **Plan §4.7's library table is stale against rev 2.** It names PQClean `sphincs-sha2-128s-simple` for the node and `pqcrypto-sphincsplus` for YEW. Both are **round-3 SPHINCS+ v3.1, not FIPS 205** (§1). It also names `falcon-512/clean`, where the briefing says `falcon-padded-512`. | Client agents could follow the wrong row. | Fix the §4.7 table. YEW uses `slh-dsa` (RustCrypto). |
| **C-7** | **`fn-dsa` 0.4.0, the version the plan points at, is not byte-compatible with PQClean `falcon-padded-512`.** It hashes `mu = SHAKE256(hpk ‖ 0x00 ‖ len(ctx) ‖ ctx ‖ msg)` into the point (`fn-dsa-comm-0.4.0/src/lib.rs:176-203,245`), where round-3 Falcon hashes `nonce ‖ msg`. 0.3.0 still has `HASH_ID_ORIGINAL_FALCON` (`fn-dsa-comm-0.3.0/src/lib.rs:157-180`). fn-dsa's keygen (ntrugen) also differs from PQClean's, so the same seed gives different keys. | YEW's Falcon holder signatures would fail on the node. | Before Falcon: YEW needs no Falcon. For the Falcon step, YEW uses PQClean `falcon-padded-512/clean` via `cc` (the node's vendored files at the same commit), or `fn-dsa =0.3.0` in original-Falcon mode proven against PQClean KATs in both directions. Falcon keys are not seed-portable across implementations (plan §4.6 already says so). |
| **C-8** | **The Falcon keygen seed length.** The briefing says 32 bytes "for PQClean's SHAKE256 keygen RNG", but PQClean's keygen reads **48** bytes (`falcon-padded-512/clean/pqclean.c:50`). | YEW and the Python framework will copy whatever the node patch does. | Freeze it in the Q0 vectors. |
| **C-9** | **The lightwalletd-dd quantum branch is behind.** `upgrade/quantum-vaults` (`c8346c3`) is 2 commits behind `upgrade/vault` (`f0746e4`): the read cache `cb03bf3` and its docs. It was cut from `origin/upgrade/vault`, which lags the local branch. | The Q7 work would miss the cache's allow-list test. | Fast-forward before cutting `q/lwd`. |
| **C-10** | **Owner identity versus holder identity in UIs.** Under spec §3.6 the MINT token goes to a fresh holder key (P2PKH until Falcon), no longer to the owner key. YecWallet's receive copy and YEW's `receive.dart:69` ("same key as your public address") assume one key per user. The 53-character owner `ye…` (spec §6.2 `ownerAddress`) is a vault identifier, not a YED receive address. | UX confusion: a user could send YED to an SLH-DSA owner address, and each transfer out of it would cost an 8 KB spend. | Wallets label `ownerAddress` as "vault owner (post-quantum)" and never offer it as a receive address. |
| **C-11** | **The exact-match rpcversion handshake** in YecWallet (`src/yellowbackcontroller.cpp:152-166`), lightwalletd (`common/yellowback.go:184-185`) and YEW (`core/src/net/yellowback.rs:193-194`). | Node, lightwalletd, YecWallet and YEW must be deployed in lockstep. This is already true for 5→6, but worth stating in the Q8 release notes. | No change; release-note it. |

Spec items confirmed from the client side:
- **F-1:** clients build `20 <hash> 51 c2`, never `01 01`. The YecWallet, chain-viz and hawkeye surveys all assumed 36 bytes until aligned here.
- **F-8:** hawkeye and YEW both independently derived V 43→45 tokens (`appHeight` o[38]→o[40]) and I 31→32.
- **A-3:** the positional `yed_mint` risk raised by the YecWallet, lightwalletd, x402 and devnet surveys disappears.

---

## 1. Libraries for the Rust clients (YEW core, hawkeye)

Checked against crates.io and crate sources (`wt/scratch/q-clients/crates.md` has the long form).

| Need | Crate | Verdict |
|---|---|---|
| SLH-DSA-SHA2-128s | **`slh-dsa` (RustCrypto)** | **Use.** 0.1.0 (2024-08-18) implements FIPS 205 **final** (CHANGELOG: "FIPS 205 Initial Public Draft -> FIPS 205 Final") and ships NIST ACVP keyGen/sigGen/sigVer tests (`tests/acvp_*.rs`). The API maps onto the plan directly: `slh_keygen_internal(sk_seed, sk_prf, pk_seed)` = the 48-byte seed; `try_sign_with_context(msg, ctx = b"", opt_rand: None)` = deterministic, opt_rand = PK.seed. Pure Rust, `no_std`, MIT/Apache-2.0. Never independently audited (README). 0.2.0-rc.5 (2026-04-28) moves to edition 2024, MSRV 1.85 and digest 0.11. |
| | `pqcrypto-sphincsplus` 0.7.2 | **Reject.** PQClean `sphincs-sha2-128s-simple` is SPHINCS+ round 3.1 (`META.yml`), not FIPS 205. Its `crypto_sign_signature` has no pure-mode `0x00 ‖ len(ctx) ‖ ctx` prefix and is randomized. The rustpq project is archived ("no longer actively maintained … no security fixes"). |
| FN-DSA-512 padded | `fn-dsa` 0.4.0 | **Not compatible** with the node's scheme 0x02 (C-7). |
| | `fn-dsa` =0.3.0 | Possible only in `HASH_ID_ORIGINAL_FALCON` mode, after a two-way KAT proof against PQClean. Signatures are a fixed 666 bytes; MSRV 1.82; Unlicense (hawkeye's `deny.toml` does not allow Unlicense, though hawkeye needs no Falcon). |
| | `pqcrypto-falcon` 0.4.1 | Byte-identical C (`falcon-padded-512/clean`), but unmaintained and with no seeded keygen. Better: compile the node's vendored PQClean files with `cc`. |

**Dependency resolution against the real lockfiles** (scratch copies, `cargo metadata` only):

| Repo | `slh-dsa =0.1.0` | `slh-dsa =0.2.0-rc.5` |
|---|---|---|
| **YEW** (toolchain 1.92.0) | **resolves**, together with `fn-dsa =0.3.0`. It adds `signature 2.3.0-pre.7`, `sha3 0.10.9`, `zerocopy 0.7.35` and the fn-dsa crates. | **fails**: `hmac ^0.13` conflicts with YEW's pinned `hmac =0.13.0-pre.4` (bip32 pins the RustCrypto pre-releases, `core/Cargo.toml:25-31`). |
| **hawkeye** (rust 1.97) | **fails**: `signature 2.3.0-pre` conflicts with `k256 =0.13.4` → `ecdsa`'s `signature`. | **resolves** (`signature 3.0.0`, `sha2 0.11.0`, `hmac 0.13.0`). |

Pin YEW at `slh-dsa =0.1.0` and hawkeye, if it ever needs it, at `=0.2.0-rc.5`. Both must pass the same Q0 golden vectors.

**hawkeye needs no PQ crate today.** Owner signing stays in the depositor's node (`vault_ownerspend`), and `ownerHash = SHA256(scheme ‖ pk)` needs only `sha2`, which it already has.

No PQ library is needed in YecWallet, lightwalletd, chain-viz or yb-calibration.

x402 needs one only if a local-key PQ YED signer is scoped. In TypeScript, `@noble/post-quantum` has `slh_dsa_sha2_128s` but no Falcon (not evaluated in depth). Recommendation: keep x402's local signer P2PKH-only until Falcon.

The Python test_framework (devnet, §8) needs a pure-Python FIPS 205 signer and verifier (plan §4.7); that is the Q1/Q6 framework agent's work, not Q7.

**Mobile.** SLH-DSA-128s signing is about 0.5–1 s on a phone, once per redeem. The flutter_rust_bridge (FRB) calls are already async, so keep the signing off the UI isolate.

Pure-Rust `slh-dsa` needs no NDK or iOS C toolchain work. A PQClean `cc` build for Falcon does: it would need cargo-ndk/iOS CFLAGS checks (`scripts/build-core-{ios,android}.sh`).

---

## 2. YecWallet (`yecwallet-dd`, Qt/C++): **S–M**, about 2 days plus devnet

The wallet is a thin JSON-RPC client. The node signs, builds and prices everything. There is no bridge UI and no crypto library.

### (a)/(b) Sites and changes

| # | Site | Change |
|---|---|---|
| 1 | `src/yellowbackrpc.h:37` `RPC_VERSION = 6` (history :30-36, header :10); exact-match handshake at `src/yellowbackcontroller.cpp:152-166`; settings label `src/yellowbacktab.cpp:2684` | → 7 |
| 2 | **`looksLikeYellowbackAddress`** (`src/yellowbackcontroller.cpp:719-725`): `length < 26 \|\| > 40` → false | **Blocks every 53-character PQ `ye…`** before `yed_validateaddress` is called (Send, `yellowbacktab.cpp:605,630`). Accept exactly 35 or 53; `yed_validateaddress` stays the authority. Matters only once Falcon holders exist, or when a user pastes an owner address. |
| 3 | `p2pkhScriptForKeyId` (`yellowbackcontroller.cpp:325-331`), used for **the owner's residual release** (`yellowbacktab.cpp:1999-2003` → `vault_release <outpoint> <script>`, `yellowbackcontroller.cpp:1067`) | Per F-3 the residual pays `PQPKH(owner)` = `20 <ownerHash> 51\|52 c2`. Build it from the row's `ownerHash` + `ownerScheme`, and drop the `ownerKeyId` path (the field is removed). This is the one place a wrong script means a failed release. |
| 4 | Position model: `yellowbackrpc.h:245-246` (`ownerPubKey`, `ownerKeyId`), parsed in `src/yellowbackmodels.cpp:88-90,106` (members `yellowbackmodels.h:30,32,48`); tooltip "Owner key: <ownerKeyId>" at `yellowbackmodels.cpp:592` | Remove both. Add `OWNER_SCHEME`/`OWNER_HASH`. The tooltip shows "Owner: SLH-DSA, `ye…`(53)" using `ownerAddress`. `scriptPubKey` is only checked non-empty (`yellowbacktab.cpp:1212,1262`), so no change. |
| 5 | `Params` namespace (`yellowbackrpc.h:137-163`) | Add `PQ`/`ParamsPq{SCHEMES, FALCON_ACTIVE}` (+ `FEE_RATE` if C-5 lands) with `// contract:` markers. Show them in Overview/Settings. |
| 6 | Contract copy `docs/yellowback-rpc-contract.json` (rpcversion :435/:832; `ownerPubKey` :537,1061,1172; `ownerKeyId` :1060,1171,1255; V example `2102…ac` :1063,:1174) | Regenerate from the node (`make spec-quantum`, spec §6.3). CI `cmp`s it byte for byte. |
| 7 | `yed_mint` call `[cents, lockBlocks, from, "", false, maxCollateralZat]` (`yellowbackcontroller.cpp:1013-1017`) | **No change** (A-3). Optionally show the new result field `ownerAddress`. |
| 8 | Copy: owner-key disclosure (`yellowbacktab.cpp:731,982-1000,1563`) | Name the post-quantum owner key and say that wallet.dat backs it up. Add the plan §6 disclosures: no hardware wallet, Sapling and attestors not PQ. A redeem's network fee is larger on ycash6 (C-5). |
| 9 | Stale `docs/yellowback.md:5,458,463` ("rpcversion 5") | Fix the text. |

**No change needed:**
- `Settings::isValidAddress`/`isZAddress`/`isTAddress` (`src/settings.cpp:452-461,85-96`) never match a `ye…`, which is correct.
- Pool fee helpers (`yellowbackcontroller.cpp:1254-1290`).
- Branch-ID display strings.
- The `vault_*` RPCs the wallet uses (it never calls `vault_lock`/`vault_ownerspend`/`vault_decodescript`).

### (c) Tests

Existing: `tests/yellowbacktab_test.cpp` (≈112 slots, 4 devnet):
- RPC-version pin and `handshakeAcceptsRpcVersionSixOnly`: :626-632, :783, devnet :3580.
- `positionActive` fixture: :103-109.
- `releaseClaimRequestShapes`, which checks `76a914…88ac`: :1498-1501.
- `sendRefusesNonYellowbackAddress`: :1997.
- Devnet `looksLikeYellowbackAddress(yed_getnewaddress)`: :3515.
- `tests/check-rpc-contract.py`.

New tests:
- The guard accepts 35/53 and rejects 41–52, over 53 and wrong prefixes.
- `isZAddress`/`isTAddress` are false for a PQ `ye…`.
- The residual release builds `20…51c2` from `ownerHash`/`ownerScheme`.
- Fixtures without `ownerPubKey`.
- `params.pq` display.
- The handshake accepts 7 only.
- Devnet: mint, redeem with the PQ owner, release the PQ residual.

**Commands**
- Build: `cmake -S . -B build -G Ninja -DCMAKE_PREFIX_PATH=$(brew --prefix qt) && cmake --build build`.
- Unit and widget tests (minutes when warm): `QT_QPA_PLATFORM=offscreen ctest --test-dir build --output-on-failure`.
- Contract check (seconds): `python3 tests/check-rpc-contract.py [--spec ../ycash-dd/doc/yellowback-spec.md]`.
- Devnet (about 2 minutes to bring up): `contrib/yellowback/devnet/yellowback-devnet up --dir D` in the node repo, then `YELLOWBACK_DEVNET_DIR=D build/bin/yellowback_test`.

### (d) Dependencies

Node spec §6.2 fields:
- `ownerScheme`, `ownerHash` and `ownerAddress` on `yed_listpositions`/`yed_getvault`/`yed_listvaults`.
- `params.pq`.
- `yed_validateaddress` accepting 53-character addresses.

The regenerated node contract. A release must bundle an rpcversion-7 `ycashd` (`build.sh --package --ycashd`).

### (e) Order

1. Contract and `RPC_VERSION`.
2. Model fields.
3. Residual script.
4. Address guard.
5. `params.pq` display and copy.
6. Tests.
7. Devnet.

### (f) Risks

- The residual release sends the wrong script if item 3 is missed.
- Lockstep release with the bundled node (C-11).

---

## 3. YEW (`yew`, Flutter + Rust core): **L**, about 2–3 weeks; the largest client

YEW builds, parses, signs and prices every vault and YED transaction in `core/`. It reaches the node only through lightwalletd-dd gRPC, using `proto/yellowback.proto`, which is pinned by `proto/PIN` = lightwalletd `3244976`. So **lightwalletd's proto must land first.** There is no wYEC/bridge code (README:30), so the bridge flow named in the coordinator brief does not exist in YEW today.

### (a)/(b) Sites and changes

| Area | Sites | Change |
|---|---|---|
| Templates | `core/src/vault.rs`: `VaultParams.owner_key:[u8;33]` :92, `IntentParams.owner_key` :113; validity :117-132; builders :157-158, :169-170 (V), :204-205 (I); opcodes :40-42; `parse_vault` (`len != 43`, owner o[22], app_height o[38]) :247-257; `parse_intent` (`len != 31`, owner o[27]) :268-278; `intent_for` :289-299; YED params :380-431 | Owner becomes `{scheme:u8, hash:[u8;32]}`. Each owner slot pushes `hash32`, then `OP_1`/`OP_2` (F-1), then `OP_CHECKPQSIG` 0xc2. V 43→45 tokens (owner hash o[22], scheme o[23]; second owner o[34]/o[35]; app_height o[40]); I 31→32. Byte lengths are unchanged (spec §1.1). |
| Owner scriptSigs | `vault_owner_script_sig`/`vault_owner_released_script_sig` :332-345 | Chunked `<sig_1..16> OP_16 <pk> OP_1 OP_2\|OP_3`: chunks 1–15 are 520 bytes, chunk 16 is 57 bytes including the hashtype; 7,939 bytes in total (spec §1.5). `parse_selector` :312-329 already tolerates it. |
| Owner signing | `core/src/build/redeem.rs:300-319` `sign_owner_input` (ECDSA over the ZIP-243 sighash); `vault_script_of` :388 | SLH-DSA (`slh-dsa =0.1.0`, ctx empty, deterministic) over the same sighash bytes (`core/src/tx.rs:347` unchanged), with `SIGHASH_ALL` appended to the last chunk. |
| MINT | `core/src/build/mint.rs`: the owner is an HD secp key (:387-396, :637-676, :949-961); `mint_outputs` :822-860 (payload `owner_key` :857); token `p2pkh_script(owner_hash160)` :868-871; fee-payee selector = owner pubkey :390-396 (`GetFeePayee.selectorHex`, :232-251) | The owner is a fresh SLH-DSA key, and the payload carries `scheme ‖ hash`. **The token goes to a fresh P2PKH holder key, not the owner** (spec §3.6). The selector becomes the 33 `scheme ‖ hash` bytes (spec §3.6 `ctx.Payee`). |
| Payload codec | `core/src/payload.rs`: layout :20, `KEY_SIZE`/`MINT_BODY_SIZE` :50-51, `Mint.owner_key` :129, encode :293-301, decode :376, **`VERSION = 0x03` :36, written :285, checked :469** | Split the owner field. **Version → 4, keyed by server rpcversion (C-1).** |
| Terms | `core/src/build/terms.rs:221-283,390-394` (`check_vault_script` parses `owner_pub_key`) | New owner type; read `ownerScheme`/`ownerHash`. |
| Claim / residual / release | `build/claim.rs:247-250,327,637-655,727` (residual `p2pkh_script(hash160(owner))`); `sync.rs:698-720` `record_residual_intents`; `build/release.rs:86` (refuses a non-P2PKH recipient) | Residual = `PQPKH(owner)` (F-3). release.rs must accept and **spend** a 35-byte PQPKH residual with the SLH-DSA owner key: an 8 KB spend, once. Classify that coin in `coins.rs`. |
| Owner identity / sync / store | `sync.rs:356,591-612` (own vault = `hash160(pk) ∈ own`), `:640` (`VaultOutputFilter.owner`); `store.rs` `SCHEMA_VERSION = 4` :40, `owner_pubkey BLOB` :443,447,1680, 33-byte check :1396-1399; key chains `keys.rs:225-259`, `wallet.rs:252-330` | Add a deterministic, gap-scanned SLH-DSA owner chain from the BIP39 seed. Use the node's derivation if A-12 freezes HKDF-SHA256(seed, "YcashPQ", path); YEW and node seeds differ anyway, so only YEW-internal restore must be deterministic. Own-owner set keyed by `ownerHash`. Store v5 migration (`owner_scheme`, `owner_hash`, PQ key index). No legacy secp-owner vaults exist on a quantum chain, so no dual path. |
| Holder shapes | `core/src/script.rs:223-257,282,291` (P2PKH only; opcode table :58-100 lacks 0xc2); `coins.rs:170-210` `classify`/`pre_lock`; P2PKH-only filters `redeem.rs:600-625`, `yed_transfer.rs:204,378`, `yec_send.rs:112`, `yec_move.rs:226`, `mint.rs:767`, `release.rs:164`; signer `tx.rs:429-446` | Pre-Falcon: add `pqpkh_script`/`pqpkh_of` (35 B) and classify PQPKH (needed for the residual). Holder signing stays P2PKH. **Falcon step (later): Falcon keys and PQPKH holders, required by `TOK-PQ`.** |
| Addresses | `core/src/params.rs:93-99` (`yellowback_prefix`); `keys.rs:356,375` (20-byte encode), `:380-386` `AddressKind`, `:407-433` (`payload.len() != 22`); `api.rs:1330-1356` `validate_address`, `:2491` owner address, `:743-744`, `:938-939`; destination parsing `yed_transfer.rs:285-290`, `yec_send.rs:68-71`, `yec_private.rs:127`, `wallet.rs:316`, `mint.rs:893-895` | Add the PQ versions `56BF`/`571E`/`5710`, a 35-byte payload and `AddressKind::PqPkh{scheme,hash}`. `VaultSummary.owner_address` renders the 53-character PQ address. Reject PQ addresses as YEC destinations. |
| Fees | `params.rs:572-603` `FEE_ZAT = 1_000`, `RESERVE_MIN`; uses `redeem.rs:147-148`, `release.rs:90-92`, `claim.rs:268,441,493`, `mint.rs:964`, `yec_send.rs:80-82`, `api.rs:1599,2097,2665,2917`, `yec_move.rs:178` | `fee = max(FEE_ZAT, rate × size)`, using `params.pq.feeRateZatPerKB` (C-5) and the exact signed size (fixed for SLH). At 1× this stays 1,000 on ycash-dd. The redeem fee comes out of collateral (`redeem.rs:147`), so check `vault-value-too-small`. Add a pre-broadcast 9,000-byte scriptSig check. |
| rpcversion / proto | `core/src/net/yellowback.rs:37` `KNOWN_RPCVERSION = 6` (exact match :193-194); `proto/yellowback.proto` :128 (`ownerPubKey`), :140-141, :217, :239, `YellowbackParams` :53-66 | → 7. Re-pin the proto from lightwalletd `q/lwd` (`scripts/check-proto-pin.sh`). |
| Dart | `app/lib/screens/send.dart:69-84,78,206` (kind check, "(ye… or s…)"); `receive.dart:69` ("same key as your public address", C-10); `vault.dart:162,209,310`, `claimable.dart:114-115`, `release.dart:169`, `mint.dart:393`, `preview_card.dart:73,126` (fee display); `app/test/fake_wallet_api.dart:18,105,221,226,351,383` | Show the owner (PQ) address and size-priced fees, fix the copy, update the fixtures. Re-run `scripts/gen-bridge.sh` (generated files are committed and CI-diffed). |

Branch ID (`params.rs:365`, `signing_branch_id` :400-436): **no change**.

### (c) Tests

Existing tests:
- `vault.rs` unit tests over `core/tests/vectors/vault_vectors.json`, a byte copy of the node's vectors: `vaults_build_and_parse_byte_for_byte`, `selectors_match_the_vector`, `spends_sighash_under_the_vault_branch_id`, `yed_vault_matches_the_app_enabled_vector`, `out_of_range_fields_do_not_build`.
- `core/tests/vectors.rs`: `transparent_signing_vectors_byte_for_byte`, `address_vectors` (`addresses.json`), `template_payload_vectors_round_trip`, `w4_templates_reproduce_the_node_scripts_and_payloads` (`check_mint` :445, :453, :506; `check_redeem` :583; `check_in_term_claim` :748), fed by the node devnet `vectors` command plus `scripts/vectors-in-term.py`.
- Unit tests in `payload.rs`, `params.rs`, `coins.rs`, `gate.rs`, `redeem.rs`, `claim.rs`, `store.rs`, `tx.rs`.
- Devnet (`core/tests/devnet.rs`, `#[ignore]`): `w4_mint_resume_lapse_redeem_import_and_claim` :923, `w4_claim_cancelled_by_the_attestor_set` :1650, `it_early_redeem_and_in_term_claim` :1831.
- Flutter: 14 widget files and 3 integration flows.

New tests:
- PQ V/I vectors, including wrong scheme, scheme 2 while Falcon is inactive, and the hash length.
- Chunk boundaries (520 / 57, OP_16 / OP_1).
- SLH-DSA KAT plus a node-signed owner spend reproduced byte for byte.
- Seed → owner key determinism.
- PQ address vectors (53 characters, all three nets).
- v4 payloads, and a refusal to build v3 against rpcversion 7.
- The size estimate equals the actual size; the fee formula.
- PQPKH residual classify and spend.
- Store v4→v5 migration.
- rpcversion 7 probe.
- Devnet `w4_`/`it_` against a quantum node.
- Flutter fixtures.

**Commands**
- `cargo fmt --all -- --check && cargo clippy --workspace --all-targets --locked -- -D warnings && cargo test --workspace --locked`. CI caps: 45 min Linux, 60 min macOS. Local runs take minutes, since dev builds compile dependencies at opt 3.
- Checks: `scripts/check-{proto-pin,deps,licenses}.sh`, `scripts/audit.sh`. Every new crate must go into `scripts/allowed-deps.txt`.
- Flutter: `cd app && flutter pub get && flutter analyze && flutter test`, plus `scripts/gen-bridge.sh && git diff --exit-code -- core/src/frb_generated.rs app/lib/src/rust`.
- Devnet (over 60 minutes from cold; Sapling proofs take about 9 s each in dev): `scripts/devnet-w4.sh test`, `scripts/devnet-it.sh up|test`.

### (d) Dependencies

- lightwalletd `q/lwd` proto (owner fields, `pq`, fee rate).
- The node's `vault_vectors.json`, `templates.json`, `transparent.json` and `addresses.json` regenerated with PQ cases (devnet `vectors` command, §8).
- `slh-dsa =0.1.0`.
- Falcon (later): PQClean `cc` build, or `fn-dsa =0.3.0` (C-7).

### (e) Order

1. Proto re-pin and rpcversion.
2. Address codec and PQPKH helpers.
3. Payload v4 (C-1).
4. `vault.rs` templates and chunked scriptSigs; vectors.
5. SLH-DSA crate and the owner key chain; store v5.
6. MINT (fresh holder token) and redeem signing; fee by size.
7. Claim, residual and release; sync identity.
8. API surface and Dart.
9. Devnet.

Falcon holders come afterwards, as their own task.

### (f) Risks

- **C-1 burn:** a v3 TRANSFER sent to a quantum chain burns the YED.
- Restore depends on deterministic owner derivation.
- The fee comes out of small vaults' collateral.
- The digest/hmac pre-release pin blocks crate upgrades (§1).
- Phone signing latency.
- Vector dependency on the node.
- The exact-match rpcversion requires a staged rollout.

---

## 4. lightwalletd-dd (Go): **S**, about 1–2 days plus devnet

It is a read-only proxy: it signs nothing, builds no scripts and charges no fee.

**First step:** fast-forward `upgrade/quantum-vaults` to `upgrade/vault` (C-9).

### (a)/(b) Sites and changes

1. **rpcversion.** `common/yellowback.go:40` `KnownRPCVersion = 6` is an exact match (:184-185); a mismatch disables the service (`cmd/root.go:290-305`). Set it to 7 and update the comments at :31-39, `walletrpc/yellowback.proto:10` and `testtools/lwdinfo/main.go:119`.
2. **PQ address mapping.** `frontend/yellowback_addr.go:21-28,45-66` admits only the P2PKH versions, with `yedAddressLen = 35` and a 2+20+4 decode.
   - A 53-character PQ `ye…` falls through to `checkTaddress` (`service.go:67`) as an opaque "Invalid address".
   - Change: keep the O(1) pre-check (audit E-1). Recognise length 53 with versions `56BF`/`571E`/`5710` and return INVALID_ARGUMENT "PQ YED address: use GetAddressTokens". PQ outputs are not insight-indexed (spec A-11).
3. **`GetAddressTokens`.** `frontend/yellowback.go:37,430` `maxAddressLen = 64` already admits 53. Add a test.
4. **Owner filter.** `frontend/yellowback_vault.go:21` `pubkeyPattern = ^0[23][0-9a-fA-F]{64}$` (:90-94) rejects every PQ owner. Per spec §4/§6.2 it becomes `^0[12][0-9a-fA-F]{64}$` (pqkeyid). The old 02/03 form is **refused**, not accepted: spec §6.2 renames the type precisely because a `02…` key and a Falcon key id are the same length.
5. **Proto** (`walletrpc/yellowback.proto`), keeping spec §6.3's numbering advice (reserve removed numbers, add new ones):
   - `YedPayload.ownerPubKey = 5` (:128) → reserve it; add `ownerScheme`, `ownerHash`; `version` 4.
   - `YedVault` 14/15/16 (:140-141) → keep `ownerAddress` (14); reserve 15 and 16; add `ownerScheme`, `ownerHash`.
   - `VaultOutput.ownerkey = 14` (:239) → reserve it; add `owner` (pqkeyid) and `ownerscheme`.
   - `VaultOutputFilter.owner` (:217) → type comment only.
   - `YellowbackParams` (:53-66) → add `pq {schemes, falconActive, feeRateZatPerKB}`.
   - Regenerate (`Makefile:89,100-101`; protoc 36.1, protoc-gen-go v1.26.0, protoc-gen-go-grpc v1.1.0) and pass `scripts/check-generated.sh`.
6. **Fixtures.** Recopy `testdata/yellowback/contract.json` (rpcversion :435,:832; owner fields :537,1059-1061,1170-1172,1254-1256) and `testdata/vault/*.json` (`vault_list.json:16,41` `ownerkey`) from the quantum node.
7. **Allow-lists and cache.** `common/yellowback.go:44-131` and `common/yedcache.go:31-51`: classify any new RPC (for example a C-4 `vault_getnewowner` is wallet-only → NotOffered).
8. **CI.** `.github/workflows/yellowback-tests.yml:30,107-112,206-211`: add `upgrade/quantum-vaults` and map it to the node's quantum branch. Local-only per D-Q-17, but keep the file consistent.
9. **Devnet suite.** `frontend/yellowback_devnet_test.go`: `:456` parses `OwnerPubKey` from the node's `lwd-rawmint` (follows §8); `:324,1010` assert rpcversion; `:832-980` vault section.

### (c) Tests

Existing:
- `TestProbe` :547 (`KnownRPCVersion ± 1` refused).
- `TestYedToTransparent` :593, `TestTaddrOfMapsYedAddresses` :621, `TestTaddrOfRejectsLongGarbageCheaply` :845.
- `TestUnary/StreamingMethodsMatchContract` :296/:371.
- `TestUnaryInfoInTerm` :947 (hard-coded 6).
- `yellowback_vault_test.go` :65, :141 (owner filter; `"04"+owner` reject :184), :202, :243.
- `common/yedcache_test.go`.
- Devnet `TestDevnet*`.

**Gap:** the contract-match helper (`yellowback_test.go:255-273`) silently ignores fields the node adds or renames. Add a reverse check that every contract key is in the proto or on an explicit ignore list.

New tests:
- PQ address vectors are unmapped, with a clear error.
- `GetAddressTokens` with a PQ address.
- pqkeyid owner filter accept/reject (including that `02…` is refused).
- rpcversion 7 and `params.pq`.
- Owner-field decode.
- Devnet: a PQ-owner mint seen through the server.

**Commands** (CI says "a few minutes warm"):
- Baseline frontend tests hang (F-R1), so run the non-frontend packages and a filtered frontend set:
  - `go test -mod=vendor ./cmd/... ./common/... ./parser/... ./walletrpc/...`
  - `go test -mod=vendor -count=1 -timeout 120s -run 'Unary|Streaming|Params|NodeErrors|InputValidation|AllowList|Probe|YedTo|TaddrOf|RateLimit|CallYed|ListVaults|TipAnswers|ConfDefaultPorts|NewZRPCFromConf|ChainInfo|Vault' ./frontend/`
- Vet: `go vet -mod=vendor ./...`, and `go vet -mod=vendor -tags devnet ./frontend/`.
- `scripts/check-generated.sh`.
- Devnet (job cap 60 min): `YCASH_DD=<tree> scripts/devnet-test.sh --up --down`.

### (d) Dependencies

- Spec §6.2 field names.
- The node contract and `doc/vault-rpc.md` regenerated.
- `lwd-rawmint` emitting `ownerScheme`/`ownerHash`.
- The C-5 fee-rate field.

### (e) Order

1. Fast-forward.
2. Fixtures.
3. Version.
4. Proto and regeneration.
5. Owner filter.
6. Address handling.
7. Allow-lists.
8. CI map.
9. Devnet.

### (f) Risks

- Lockstep deployment with the node (C-11).
- Silent field drop (the test gap above).
- PQ holders cannot use the taddr RPCs; wallets must use `GetAddressTokens`.

**YEW and x402 vendor this proto, so this task is a prerequisite for both.**

---

## 5. chain-viz (Rust + plain JS, read-only): **S**, about 1 day (M with a new PQ-bytes chart)

There is no V/I byte parsing and no owner display. `vault_list` rows are opaque `serde_json::Value`.

### (a)/(b) Sites and changes

1. **Payload version.** `src/classify.rs:32` `VERSION = 0x03`, checked at :119. On a quantum chain **every** YED transaction would classify as non-Yellowback (C-1). Accept 4 when `rpcversion ≥ 7`, or accept {3, 4}, since it is display only.
2. **MINT body** (`classify.rs:141-152`): same 48 bytes. Optionally decode `ownerScheme` = body[13] and comment the 33 bytes as `scheme ‖ hash`.
3. **Selector classification** (`src/model/vault.rs:49-67`, last scriptSig byte 0x51..0x54): still correct for chunked owner spends. Add a test with a 7,939-byte scriptSig ending `52`/`53`.
4. **Residual and holder payees** (`src/model/revenue.rs:179-233,373-383`): P2PKH-only (`p2pkh_hash` needs 25 bytes; `decode_address` assumes 26-byte payloads).
   - Add `pqpkh_of` for `20 <32> 51|52 c2` (35 B) and encode it with the PQ versions.
   - Accept or skip 39-byte decodes in `learn_prefix`.
   - Without this the residual shows as "owner".
5. **rpcversion.** `src/rpc.rs:514` `KNOWN_RPC_VERSION = 6` and `ui/panels/health.js:20`: warning pill only. Set both to 7 and update README :426. Show `params.pq` in the health ribbon.
6. **Mempool visual.** The bubble radius (`ui/panels/mempool.js:49-51`) is linear in sqrt(size), so one 8 KB spend squashes the rest. Use a log scale and add a PQ badge.
7. **Plan Q7 "PQ byte share of blocks".** New work: per-block PQ-scriptSig bytes from `getblock 2`, as a chart in `ui/panels/chain.js`.
8. **Fixtures.** `tests/fixtures/rpc-contract-samples.json` (`ownerkey` :107-230; `src/rpc.rs:807-818` reads it): recopy from the node. `yb-txs.json`, `plain-txs.json` and `revenue-blocks.json` need PQPKH and PQ owner-spend examples.
9. **CI** `.github/workflows/ci.yml:26,141-150`: add the branch and map it.

Attestor acts (`vault.rs:83-86`) and the branch ID are unchanged.

### (c) Tests

Existing: `vault.rs` units (`selectors_and_acts`…), `classify.rs` (`mint_decodes`, `transfer_and_redeem`…), `revenue.rs` :735-873, `rpc.rs` :760-820, `tests/*.rs` (yb_classify, revenue_reconcile, replay, readonly_gate…), `qa/ui-smoke.mjs`.

New tests:
- v4 payloads.
- Chunked selectors.
- PQPKH payee.
- rpcversion-7 samples.

**Commands** (Rust 1.91.0; about a minute warm, not documented):
- `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test --locked`
- `cargo deny --locked check`, `cargo audit --deny warnings`
- `node qa/ui-smoke.mjs http://127.0.0.1:8480` against a running instance.
- Nightly: a five-node devnet.

### (d) Dependencies

- Node samples.
- The PQ version bytes (spec F-4).
- Whether `getblock 2` fills `scriptPubKey.addresses` for `TX_PQPKH`. Spec §2.4 covers key_io; if not, chain-viz encodes the address itself.

### (e) Order

1. Payload version.
2. Fixtures and rpcversion.
3. PQPKH payee.
4. Selector tests.
5. Visuals.
6. Optional bytes chart.

### (f) Risks

Low. The worst case is misattributed revenue for residuals, or YED invisible if item 1 is missed.

---

## 6. x402-ycash (TypeScript SDK + Python mirror + Rust light client): **M**, about 1–1.5 weeks (L with a local PQ signer)

Contrary to plan §4.7 and §8 (C-2), this repo ships YED exact payments and YED batch channels today.

**Breaking points on the quantum line**
- **Immediately:**
  - The payload version (C-1): it builds v3 TRANSFERs, which burn YED.
  - The rpcversion-7 field removals, which matter only where it reads them.
- **Before Falcon (A-13 keeps `yed_getnewaddress` P2PKH, so its own addresses still work):**
  - Any 53-character address a counterparty or a `yed_listtokens` row presents.
  - Any PQPKH coin it is asked to spend or verify.
- **After Falcon:** everything P2PKH-holder-shaped, plus channels (C-3).

### (a)/(b) Sites and changes

| Area | Sites | Change |
|---|---|---|
| Payload | `packages/ycash/src/yed/payload.ts:12,353,395`; `python/x402_ycash/yed/payload.py:18,181,203`; MINT `ownerKey` `payload.ts:85-93,214,288`, `payload.py:125`, `vectors/yed/gen_transfer_v3.py:47` | Version by rpcversion (C-1); decode `ownerScheme ‖ ownerHash`. |
| Address codec | TS `tx/address.ts:21-25` (versions), `:37` (20-byte encode), `:54` (`length !== 22`), `:74-77` (`addressToScript` → P2PKH); Python `tx/address.py:25-29,75,84,95` | Add a `yedpq` kind with versions `56BF`/`571E`/`5710`, a 35-byte decode, and `addressToScript` → `20 <hash> 51\|52 c2`. |
| Is-YED checks | TS `exact/policy.ts:149,174`, `batch/returnAddress.ts:25-32`; Python `exact/policy.py:101,125`, `batch/return_address.py:19-26`; `examples/merchant-express/src/config.ts:173,190-191`; `packages/cli/src/commands.ts:141` | Admit `yedpq`. |
| Coin and row parsing | `exact/client/rpcWalletSigner.ts:128,215`; `exact/client/utxoSource.ts:148`; `lwd/utxoSource.ts:105`; `batch/client/funder.ts:137,196,204`; `cli/src/commands.ts:126` | Each calls `addressToScript(<addr>)` and throws on a PQ address. Accept it, but **filter PQPKH coins out of the local P2PKH signer** (it cannot spend them). |
| Holder matching / payer display | `tx/script.ts:218-223` `p2pkhHash` (Python `tx/script.py:181`); `exact/facilitator/verify.ts:239,292-295`; `exact/script.ts:47-75` (`addressOfScript`, `addressOfScriptSig`); `lwd/chain.ts:18-23`; Python `exact/verify.py:233`, `exact/script.py:44-54` | Add `pqpkhHolder(spk)`. Derive the payer's PQ address from `SHA256(scheme ‖ pk)` in the scriptSig. |
| **Facilitator rule 5** | `exact/script.ts:13-37` (`looksLikeSignature` is DER-only, `checkSighashAll`), called at `facilitator/verify.ts:153-155`; Python `exact/script.py:8-28` | It refuses every honest PQ payer. Parse the chunked layout and check that the last byte of the last sig chunk is 0x01. |
| Fees | `tx/fee.ts:7-12,43-46` (max(1000, 500 × ZIP-317 actions), 150-byte input units); `yed/build.ts:20-21,158,166,173` `MAX_P2PKH_SCRIPTSIG = 108` (Python `yed/build.py:22,131`); `exact/facilitator/scheme.ts:116-118` (`feeCapZat` 100,000; `maxTransactionBytes` 100,000) | Per-input scriptSig size by holder type: 1,577 Falcon, 7,938 SLH. The ZIP-317 form already over-prices PQ relative to ycash-dd; reconcile with C-5. The caps stay valid. |
| Channels | `channel/yed.ts:5-8,69-70` (P2SH funding, P2PKH client output), `channel/funding.ts:83-86`; Python `channel/yed.py:56`, `channel/builders.py:162-165` | Pre-Falcon: accept a PQPKH return address. Post-Falcon: blocked on C-3. |
| Protos | `packages/ycash/proto/yellowback.proto:116,125-126`, `light/proto/yellowback.proto` | Re-vendor from lightwalletd `q/lwd`. No SDK code reads these fields. |
| Specs | `specs/scheme_exact_ycash.md:73,84-85,465,549,602-603,1056`; `specs/scheme_batch_settlement_ycash.md:183,231-232,320` ("P2PKH only") | Update. |

**No change needed:**
- Branch ID: signing reads `nextblock` dynamically (`exact/client.py:101`, `lwd/chain.ts:51-57,128-156`, `light/src/net.rs:40,85,213`).
- rpcversion: there is no gate in src; devnet tests assert `≥ 5`, so 7 passes.
- `yed_mint` positional calls (A-3).

### (c) Tests

Existing:
- TS: `packages/ycash/test/unit/` (`tx.address`, `tx.script` :70-74, `tx.fee`, `yed.build`, `yed.payload`, `yed.vectors`, `channel.yed`, `exact/*`, `batch/*`, `lwd/*`).
- Python: `test_tx_unit.py`, `test_exact_yed.py`, `test_exact_verify.py`, `test_channel_yed.py`, `test_yed_vectors.py`, `test_vault_branch.py`.
- Devnet: `test/devnet/yed.devnet.test.ts`, `examples/merchant-express/test/devnet/yed.http.devnet.test.ts`.

New tests:
- v4 payload, and a refusal of v3 at rpcversion 7.
- PQ address round trip against node vectors.
- PQPKH `addressToScript`.
- Rule 5 accepts a PQ scriptSig and still refuses a non-ALL hashtype.
- PQ payer display.
- Fee sizing for PQ inputs.
- Devnet: a payment where the payee is a PQ holder; a channel with a PQ return address.

**Commands**
- TS: `npm ci && npm run lint && npm run typecheck && npm test` (vitest; minutes).
- Python: in `python/`, `uv venv .venv && uv pip install -e . pytest pytest-asyncio mypy ruff && .venv/bin/ruff check x402_ycash tests && .venv/bin/mypy x402_ycash && .venv/bin/python -m pytest`.
- Rust light client: in `light/`, `cargo fmt --check && cargo clippy --all-targets --locked -- -D warnings && cargo test --locked` (needs protoc).
- Devnet (tens of minutes; needs Zcash params): `X402_SCRATCH=$PWD/scratch scripts/devnet.sh up dd 181 && npm run test:devnet && npm run test:devnet:http; scripts/devnet.sh down dd 181`.

### (d) Dependencies

- The spec §6.2 fields.
- PQ address vectors.
- `pq.feeRateZatPerKB` (C-5).
- The lightwalletd proto.
- No crypto library unless a local PQ signer is scoped.

### (e) Order

1. Payload version (C-1).
2. Address codec and kinds.
3. Holder matcher and payer display.
4. Rule 5.
5. Fees.
6. Channel return script.
7. Protos and specs.
8. Devnet.

### (f) Risks

- C-1 burn.
- C-3 channels.
- Fee under-pricing of PQ inputs: R3 in the survey said 30–80×; on ycash-dd at 1× it is not, so re-measure.
- The facilitator refuses PQ payers until rule 5 changes.

---

## 7. hawkeye (Rust, the wYEC bridge attestor): **M**; `lock` is blocked on C-4

The depositor's own `ycashd` wallet holds the bridge vault owner key, never hawkeye (HK-7, `docs/hawkeye-bridge-plan.md:101`):
- `recover` delegates signing (`vault_ownerspend`, `crates/hawkeye/src/cli.rs:474-502`).
- Rolls copy the owner from the spent vault (`crates/hawkeye/src/engine/roll.rs:214-221`).

So hawkeye **never signs or verifies an owner signature**, and it has no rpcversion check and no `ye…` handling. Its addresses are s1/sm only (`crates/hawkeye-core/src/address.rs`). The branch ID `VAULT_BRANCH_ID` (`crates/hawkeye-core/src/attribution.rs:22`) is unchanged.

### (a)/(b) Sites and changes

| Area | Sites | Change |
|---|---|---|
| Templates | `crates/hawkeye-core/src/template.rs`: `VaultParams.owner_key: PubKey33` :56-57, `IntentParams.owner_key` :75-76; `check()` :91-93, :139-141; builders :119-125 (V), :164-165 (I); parsers `V_OPS 43`/`I_OPS 31` :180-181, field indices :207-217, :232-241; skeletons :279-300; `template_shape` :315-323. Opcodes in `script.rs:55-63` | Owner `{scheme, hash}`. Push `hash32`, then **`OP_1`/`OP_2`** (not `push_to(&[scheme])`, which emits `01 01`: F-1), then `0xc2`. Token counts 45/32; appHeight o[40]; the second owner o[34]/o[35]; skeleton `F, F, o(OP_CHECKPQSIG)`. `PubKey33` stays for member and bond keys. Bond B is unchanged. |
| Lock policy | `crates/hawkeye-core/src/policy.rs:158,191` | Add `LockRejection::OwnerScheme(u8)`: accept scheme 1 only (owner decision). A scheme-2 owner V is refused even after Falcon unless the policy is widened. Plan §4.1 of hawkeye's own plan first (its AGENTS rule 3). |
| Roll / memo / matcher | `memo.rs:75-82,135-148`, `matcher.rs:206-224`, `roll.rs:209-245` | They follow the struct; no logic change. |
| RPC types | `crates/hawkeye-ycash/src/types.rs`: `VaultFields.ownerkey` :103, `IntentFields.ownerkey` :114 (flattened into `vault_list`/`vault_get` :122-136), `VaultListFilter.owner` :438, `VaultLockParams.ownerkey` :757-758, `VaultLockResult.ownerkey` :769; converters `crates/hawkeye/src/convert.rs:45,58` | Per spec §6.2: `owner: PqKeyId` (66 hex, `01`/`02` prefix) plus `ownerscheme`. `vault_lock` param `owner`, result `owner`. New type, not `PubKey`. |
| Contract | `crates/hawkeye-ycash/tests/data/vault-rpc-contract.json` (`key` type :24-27; `ownerkey` :267,291,353,404,1005,1032,1735-1742,1762); `tests/contract.rs` `samples()` :39-51 (KEY :20), hard samples :180, :309-315 | Re-copy. Add a `pqkeyid` sample arm (otherwise the test panics). |
| CLI `lock` | `crates/hawkeye/src/cli.rs:113-222` (owner :123-133, V :134-143, `LOCK_FEE = 10_000` :27,169-199) | Blocked on C-4. The flat fee stays valid: the lock spends P2PKH coins and the V is the same length. |
| CLI `recover` | `cli.rs:474-502` | No code change. Document that the owner spend is ≈ 8.1 KB; 10,000 zat covers it up to ≈ 12×. Check plan MIN_LOCK. |
| Engine placeholder | `crates/hawkeye/src/engine/watch.rs:183-191` (`owner_key: [2; 33]`) | `{scheme: 1, hash: [0; 32]}`. |
| Mock | `crates/hawkeye-ycash/src/mock.rs:44,194-205,477,499,873,878,1053-1073,1460-1505,1867-1921` (71-byte fake owner scriptSig :1903-1905) | PQ owner, a 7,939-byte owner scriptSig, and a size-aware fee. |
| Devnet | `devnet/hawkeye-devnet:210,251-264` (Python V builder `push(owner_key) OP_CHECKSIG`), `:1130,1165-1166` (owner from `validateaddress`), recover drill `:2062-2085`; `devnet/README.md:197` | PQ builder (`OP_1` scheme); owner from the C-4 RPC. |
| Docs | `docs/hawkeye-bridge-plan.md:101,228,240,249,378`; `roll.rs:7`; `template.rs` module docs | Update the text. |

The store persists no owner key (`crates/hawkeye-store/src/locks.rs`, `vaults.rs`), so no migration is needed.

### (c) Tests

Existing:
- `template.rs` units :418-548.
- `crates/hawkeye-core/tests/vault_vectors.rs`, which replays the node's `vault_vectors.json` (copied at `dbc1ab0`, sha256 in `tests/data/README.md`).
- `memo.rs:207-236`, `matcher.rs:246-523`, `policy.rs` :320-348.
- `tests/attribution.rs` with `crates/hawkeye-ycash/tests/data/vault_spends.json` (generated by `gen_fixtures.py` from the node's `vault.py`).
- `tests/client_mock.rs` `owner_and_app_branches` :435-490.
- `crates/hawkeye/tests/engine.rs` :325-365, :1326-1401 (needs anvil).
- `crates/hawkeye-store/tests/common/mod.rs:124`.

New tests:
- PQ V/I round trip from the regenerated vectors, plus the `OP_1` scheme encoding (and a negative for `01 01`).
- Owner copies differing → Malformed.
- Policy refuses scheme 2.
- An old EC-owner V → `None`.
- A 16-chunk owner scriptSig parses as selector 2/3.
- Contract round trip with `pqkeyid`.
- Mock: recover priced by size.
- Devnet scenarios `roll` and `dormancy` on both node lines.

**Commands** (about 30.6k lines of Rust)
- CI: `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`, `HAWKEYE_REQUIRE_ANVIL=1 cargo test --workspace --all-features --locked --no-fail-fast` (job cap 40 min), `cargo doc`, `cargo deny`, `cargo llvm-cov` (hawkeye-core gated at 90% lines).
- Per crate: `cargo test -p hawkeye-core`.
- Devnet: `devnet/hawkeye-devnet up && devnet/hawkeye-devnet scenario demo|roll|dormancy`. Dormancy takes a few minutes. The e2e workflow `devnet-e2e.yml` builds the node (about 1 h cold).

### (d) Dependencies

- The C-4 node CR.
- Spec §6.2 `pqkeyid`/`owner`/`ownerscheme`.
- The regenerated `vault-rpc-contract.json`, `vault_vectors.json` and `vault_spends.json`, identical on both lines.
- No PQ crate.

### (e) Order

1. C-4 decision and the hawkeye plan text.
2. Re-copy vectors and contract.
3. `template.rs`/`script.rs`.
4. Policy and memo.
5. RPC types and contract test.
6. Engine, mock, CLI.
7. Fixtures.
8. Devnet on both lines.

### (f) Risks

- `lock` blocked (C-4).
- Small bridge vaults stranded at higher fee multipliers.
- Op-index errors: rely on the node vectors.
- `push_to(&[scheme])` reproducing the F-1 defect.

---

## 8. Node-side devnet tooling (ycash-dd `contrib/yellowback/devnet`, `qa/rpc-tests/test_framework`; ycash6 the same): **M–L**

Strictly this is Q6 on the node lines, not Q7. But every client vector comes out of it, so it gates Q7.

**ycash6 versus ycash-dd.** The same file set. The differences are harness ports:
- the `BITCOIND`/`ZCASHD` environment variable;
- labels;
- `hashBlockCommitments` in `upgrade-walk`;
- a re-read loop in ycash6's `roles.py:238-242`;
- **fees:** ycash6's `yellowback_util.py` has `conventional_fee`/`wallet_network_fee` (ZIP-317), where ycash-dd asserts the flat `YELLOWBACK_FEE`.

The identical files are `yellowback_interm.py`, `test_framework/vault.py`, `vault_contract.py` and `yellowback_model.py`.

### (a)/(b) Sites and changes (ycash-dd paths)

- **Payload version:** `test_framework/yellowback_model.py` encoders and decoders follow F-2.
- **Vault builders** (`test_framework/vault.py`):
  - Constants: OPs :73-77 (add 0xc2), `VAULT_FEE` :134.
  - `VaultParams`/`IntentParams.owner_key` :571-626, `bad-template-ownerkey` :637-645.
  - `vault_script_unchecked` :648-658, `intent_script_unchecked` :680-688.
  - Matchers :771-784, parsers :716-760.
  - Owner scriptSigs :850-872 (→ chunked).
  - `owner_sig` :1302 (→ SLH-DSA), `build_owner_spend_tx` :1307.
  - `script.py` :241-242, :370-371, :491-492, :613-614 gain `OP_CHECKPQSIG`.
  - `vault_harness.py:70,318`.
  - Regenerate `gen_vault_vectors.py` → `src/test/data/vault_vectors.json`; `VAULT_VECTORS.md`.
- **YED model and util:**
  - `yellowback_model.py`: :896-924 V/I builders; :1064-1067, :1103 MINT owner; :1372-1397 vault state; :1740 serialisation; :2679-2684 validity; :2953 residual → `pqpkh_script(owner)` (F-3); :3256.
  - `SERIALISATION.md:40,70-73,166`: same 33 bytes, new meaning; statehash vectors regenerate.
  - `yellowback_util.py`: `build_mint_tx` :958-1000 (the token goes to a holder key, not the owner); `vault_from_mint` :1003-1011; `build_vault_spend_raw` :1039-1150; `YELLOWBACK_FEE` :204 and the flat `needed` :992,1076,1393,1442.
- **Silent mis-parse bug:** `address_key_hash` (`yellowback_model.py:590-595`) keeps the last 20 bytes of any version, so a 53-character PQ address becomes a wrong P2PKH.
  - Used by `yellowback_lifecycle.py:225-227` and `yellowback_hardening.py:219-221`.
  - Make it version-aware and add `pqpkh_script()`.
  - It bites only when a test asks `yed_getnewaddress "pq"` (A-13), but it should fail loudly.
- **`ownerPubKey` readers:**
  - `yellowback_interm.py:176,381`.
  - `yellowback_lifecycle.py:75,116` and `yellowback_pricefeed.py:328` use `dumpprivkey(pubkey_to_address(ownerPubKey))`. They need wallet-side owner signing (`vault_ownerspend`), since a PQ export RPC is not in the spec.
  - `yellowback_attest.py:291`, `yellowback_stock_node.py:195,221`, `yellowback_wallet_restore.py:89`, `yellowback_rpc_contract.py:81`.
  - **`lwd-rawmint:22,75-79`**: the lightwalletd devnet test consumes this.
- **bridge-sim:** `:266-299` builds the WYEC V with `owner_key = validateaddress(getnewaddress())["pubkey"]`, and so has C-4's problem. As a node-repo tool it may use `vault_lock`'s default PQ owner or `yed_getnewaddress "pqowner"`. `:367` `vault_ownerspend` is fine. `FEE` at `:78` stays.
- **rpcversion asserts** (6 → 7):
  - `yellowback-devnet:502` (lwd probe `("5","6")`).
  - `upgrade-walk:402-404`.
  - `yellowback_attest.py:348`, `yellowback_index.py:97`, `yellowback_upgrade.py:171`, `yellowback_attest_agent.py:291`, `yellowback_rpc_contract.py:189-192`.
  - The 6-only `yellowback_demo_v6.py:427`, and the stale ycash6 `qa/yellowback-release-smoke.sh:67`.
- **`upgrade-walk`:**
  - `:890-904` `bad_mint`, with a secp owner: rebuild it with a PQ owner so it fails for the intended reason.
  - `:885` and `yellowback_interm.py` `endswith("52")`: still true.
- **Vectors command** (YEW and x402 feed): `yellowback-devnet:1612-1651` `ADDRESS_VERSIONS` and `address_ye`, `:1715-1850`. Add PQ versions, PQ addresses (53 characters), PQ owner spend and PQPKH vectors, and the SLH-DSA KAT.
- **No PQ impact:**
  - heartbeat, price walk, mine, `--role`;
  - `yellowback_devnet_roles.py`, affected only through the yellowback-sim personas: redeem = SLH owner spend, so expect bigger blocks.
  - `yed_mint` call sites (`yellowback-sim:165`, `yellowback-devnet:1821`, `upgrade-walk:554,597,663,775-777`): A-3.

### (c) Tests

Commands:
- Framework units (fast, in CI): `cd qa/rpc-tests && python3 -m unittest test_framework.test_yellowback_attest test_framework.test_yellowback_model test_framework.test_yellowback_util -v`.
- `python3 qa/rpc-tests/test_framework/gen_vault_vectors.py --check && python3 -m unittest test_framework.test_vault -v`.
- Functional: `qa/pull-tester/rpc-tests.py -j1 --nozmq --nocleanup <name>` (`ZCASHD=` on ycash6).
- Nightly: `yellowback_devnet_roles` (about 30 min), `yellowback_devnet_upgrade` (under 10 min).
- Manual: `yellowback-devnet up` (about 2 min), `upgrade-walk` (about 6 min).

New tests: as plan §4.9, plus:
- `address_key_hash` negative on PQ.
- The `vectors` PQ section.
- bridge-sim PQ lock.

### (d) Dependencies

A pure-Python SLH-DSA signer and verifier (plan §4.7; `wt/q-pyfw` already exists) and Falcon vectors.

### (f) Risks

- The silent `address_key_hash` mis-parse.
- ZIP-317 versus flat fee assertions across the lines.
- SLH signing cost lengthening nightly runs.

---

## 9. yb-calibration (Python): **S–M**. The PQ growth + fee-multiplier study

Today there is no tx-size, block-size, throughput or chain-growth model. The network fee is the scalar 1,000 zat in four places:
- `src/ybcal/model/reference_util.py:42`;
- `src/ybcal/sim/agents.py:165` (`tx_fee_zat`, consumed by `sim/vaults.py:1015,1040,1424` and `studies/g3_collateral.py:687,843`);
- `src/ybcal/studies/g9_amounts.py:71-72,317,325` (dust bounds ≥ 3 × the network fee);
- `params/snapshot_7702d22.json:111`.

The vendored model (`src/ybcal/model/`, ycash6 `7702d22`) is pre-vault: the old P2SH vault, `ownerPubKey` (`reference.py:580,639-642,864-867,903,2369-2371,2617`). The registry `params/registry.py` is pinned to the same commit. Devnet RPC sites:
- `devnet/actions.py:106` (`yed_mint` positional: unchanged by A-3);
- `:111` (`yed_getnewaddress` → `yed_send`);
- `devnet/scrape.py:96,181` (`ownerAddress` as a string);
- `devnet/build.py:301-460` (ignores new `params` keys).

There are no rpcversion checks.

### Proposal

1. **A per-path fee function** `fee(path, mult) = max(DEFAULT_FEE, mult × 100 zat/KB × size(path))`, with ycash6's ZIP-317 variant beside it. It replaces the scalars in `agents.py`, G3 and G9; default `mult = 1` leaves today's results unchanged on ycash-dd (C-5).
2. **A new non-group analysis `src/ybcal/studies/pq_growth.py`** (like `oracle_replay.py`), with CLI `ybcal pq [--multipliers 1,2,5,10] [--out DIR]`, docs `docs/studies/pq.md`, report `docs/reports/2026-10-pq/` and test `tests/studies/test_pq_growth.py`.
   - **Inputs:** a size table per transaction type (MINT, TRANSFER P2PKH / Falcon, REDEEM owner spend 7,939-byte scriptSig, claim, release, bridge lock and recover); volumes from `policy/default.toml:94-97` `adoption_scenarios`, plus new keys (transfers/day, claims/day, bridge ops/day, holder mix, Falcon activation); constants `DEFAULT_FEE` (`ycash-dd/src/policy/fees.h:15`), relay floor 100 zat/KB (`main.h:72`), `VAULT_RPC_FEE` (`rpc/vault.cpp:51`), 2 MB block (`consensus.h:24`), 75 s spacing.
   - **Outputs:** bytes/day and GB/year per scenario; break-even multipliers; G9 dust bounds under PQ holder fees; the USD fee share at `worst_price_usd`; a recommended `-pqfeerate` multiplier (plan §9 item 3).
   - **First-order numbers to check against:** at 1× the floor binds (810 < 1,000). The "high" scenario of 30 redeems/day ≈ 243 KB/day ≈ 89 MB/year of owner-spend witness. A 2 MB block holds ≈ 245 SLH owner spends.
3. **Devnet (later):** record `getrawtransaction(...).size` and the fee per action (`devnet/actions.py`) and scrape `ownerScheme`, to calibrate the size table against a quantum ycash-dd build.
4. **The model and registry pins stay** until a quantum release exists. The owner rule says long sweeps run only after both node lines are green.

**Commands**
- `make setup` (python3.11 venv).
- `make test` = `PYTHONPATH=src .venv/bin/python -m pytest -q -m "not devnet"` (CI cap 30 min with xdist).
- `make lint verify params-check docs-check`.
- `make quick` (≤ 10 min on 4 cores).
- `ybcal devnet validate` (≈ 15 min per suite).

**Risks**
- Plan estimates instead of measured sizes until the devnet hook lands.
- Divergent recommendations across ycash6 (ZIP-317) and ycash-dd.
- The checkout is `harden/yellowback`; work goes on `upgrade/quantum-vaults` (= `main`).

---

## 10. wyec and yolo: confirmed, nothing needed

- **wyec** (`main` `d2e382b`): **no change.**
  - `contracts/WyecBridge.sol` carries no Ycash owner key and verifies no Ycash script.
  - `mint(lockId, amount, to, sigs)` (:69-78) uses EIP-712 over an opaque `lockId` and secp256k1 guardians (:25-32, :127-133), which D-Q-5 leaves unchanged.
  - `burn(amount, bytes32 ycashRecipient)` (:80-85) is a transparent YEC hash160, and plain YEC is unchanged. A 33-byte PQ `scheme ‖ hash` would not fit bytes32; that matters only if releases ever pay PQ holders. Worth one line in the design doc.
  - Test: `cd contracts && npm i solc@0.8 @openzeppelin/contracts@5 && node compile.js .` (seconds).
- **yolo** (`upgrade/vault` `d41274f`): **no change.**
  - Payout addresses go through the node's `validateaddress` (`src/rpc.rs:176-187`; `src/lib.rs:49-65`, `src/stratum.rs:400-445`). That RPC uses `KeyIO`, which never decodes `ye…`.
  - Templates are the node's, already sigop-bounded with cost 20 (`src/work.rs:124-140`, sizes from hex).
  - No signing, branch ID in the README only.
  - **Optional hardening, under an hour:** accept only a 25-byte P2PKH or 23-byte P2SH payout `scriptPubKey` (`lib.rs:59`, `stratum.rs:409-410`). This guards against spec §2.4 teaching `KeyIO` the PQ destination, which would make `validateaddress` accept a PQ `ye…` and pay a coinbase to it.
  - Commands: `cargo fmt --check && cargo clippy --all-targets --locked -- -D warnings && cargo test --locked`; with a node, `YCASHD=… cargo test --locked --features regtest`.

---

## 11. Recommended Q7 split (parallel agents)

**Common prerequisites (P0)**
- Spec frozen: `QUANTUM-SPEC-draft` adopted, including the C-4 and C-5 additions to §6.2.
- The node's Q4 RPC contract on `wt/q-dd` (rpcversion 7, regenerated `doc/yellowback-rpc-contract.json`, `doc/vault-rpc*.{md,json}`).
- Golden vectors: `vault_vectors.json`, `pq_vectors.json`, devnet `vectors` output with PQ addresses and spends.

**Prerequisites by level**
- Level 1 starts on P0 alone.
- Level 2 needs the lightwalletd proto.
- Level 3 needs a quantum devnet (both lines, from Q6).

| Task | Repo / worktree | Prereqs | Size | Notes |
|---|---|---|---|---|
| **Q7-lwd** | lightwalletd-dd `wt/q-lwd` (`q/lwd`) | P0; fast-forward first (C-9) | S | Proto first: it unblocks YEW and x402. Devnet leg after `lwd-rawmint` is updated (Q6). |
| **Q7-yecwallet** | yecwallet-dd `wt/q-yecwallet` | P0 | S–M | Devnet leg needs a quantum devnet. |
| **Q7-chainviz** | chain-viz `wt/q-chainviz` | P0 | S (M with the PQ-bytes chart) | Independent. |
| **Q7-hawkeye** | hawkeye `wt/q-hawkeye` | P0 + **the C-4 node CR merged on both lines** | M | Template, policy and types can start on P0. `lock` waits for C-4. |
| **Q7-yew-a** (templates, addresses, payload v4, owner signing, fees) | yew `wt/q-yew` | P0 + Q7-lwd proto | L | `slh-dsa =0.1.0` (resolves, §1). Do C-1 first. |
| **Q7-yew-b** (sync and store v5, residual, API, Dart) | same branch, after yew-a, or a second worktree off yew-a | yew-a | M | Sequential with yew-a: shared files (`mint.rs`, `claim.rs`, `sync.rs`). |
| **Q7-x402** | x402-ycash `wt/q-x402` | P0 + Q7-lwd proto (for re-vendoring) | M | C-1 first. C-3 is recorded for Q8, not solved here. |
| **Q7-ybcal** | yb-calibration `wt/q-ybcal` (`q/ybcal` off `upgrade/quantum-vaults`) | none for the analytic study; a quantum ycash-dd build for the devnet leg | S–M | It can start now. |
| **Q7-yolo** (optional) | yolo | none | XS | `scriptPubKey`-shape guard. |
| **Q6-devnet** (feeds Q7) | ycash-dd + ycash6 framework and devnet | Q4/Q5 on the node | M–L | Not a client task, but the vector source for YEW, x402, hawkeye and lightwalletd. Port to ycash6 is mechanical except fee asserts. |
| **Q7-yew-falcon** (later) | yew | Falcon library decision (C-7), Q8 D-Q-2 | M | PQClean `cc` build or `fn-dsa =0.3.0`; PQPKH holder signing; `TOK-PQ`. |

**Order and parallelism**
- Start now on P0 alone, in parallel: lwd, yecwallet, chain-viz, ybcal, and hawkeye's template/policy part.
- Then, once the proto exists: YEW-a and x402 in parallel.
- Then YEW-b.
- Devnet legs of every task run last, against a quantum devnet on **both** node lines, at most two functional runs at once (briefing load rule).

**Owner decisions to raise:**
- C-3: YED channels after Falcon.
- C-4: hawkeye's owner source.
- C-5: expose the fee rate.
- C-1: confirm F-2's version bump knowing it burns v3 TRANSFERs from stale clients. The alternative is to keep TRANSFER/REDEEM at v3 and bump only MINT: smaller blast radius, but the version byte then no longer means one thing.
