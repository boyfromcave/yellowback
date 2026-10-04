# Phase 7 compatibility survey — non-`yed_*` node interfaces, v4.5.0 → 6.20.0

> **Historical survey (2026-09-30).** Its findings are carried into
> [`../yellowback-ycash6-plan.md`](../yellowback-ycash6-plan.md) §6 as the Phase 7 rows F-43, F-44
> and F-46..F-58, which record how each was resolved; F-49's tree-state check is the one still
> marked open there. (F-59..F-65 are later branding, attribution and process rows, not from this
> survey.)

Agent `compat`, 2026-09-30. Read-only: nothing was built, run or edited.

**Pins compared**
- `ref/ycash`: v4.5.0 `624c12814`
- `ref/ycash6`: `040894344b`, the 6.20.0 baseline
- `ycash6`: branch `feature/yellowback` (`5576005b0`)
- `ycash-dd`: the v4.5.0 + Yellowback node

Paths below are relative to the workspace root.

**Method**
- Components: the four component sources (yecwallet-dd, lightwalletd-dd, yolo, chain-viz) plus yew's net layer and the devnet launcher were grepped for every node interaction.
- Registered RPCs: the dispatch tables at both pins were diffed with
  `git grep -hP '^\s*\{\s*"[a-z_-]+",\s+"[a-zA-Z_]+",\s+&'`.
  - Removed in 6.20.0: `estimatefee estimatepriority getrescaninfo rescanblockchain zcrawjoinsplit zcrawkeygen zcrawreceive`.
  - Added in 6.20.0: `getaddressfirstlastheight getcompactblock getcompactblockrange getexportchainstatus listaddresses walletconfirmbackup z_converttex z_getaddressforaccount z_getbalanceforaccount z_getnewaccount z_getsubtreesbyindex z_listaccounts z_listunifiedreceivers`.
  - ycash6's non-yed list equals ref/ycash6's exactly.
- Result shapes: the `pushKV` key sets of each RPC the components use were compared, and the arity table `ref/ycash6/src/rpc/common.h` was checked.
- Arity is now **server-enforced**: `ref/ycash6/src/rpc/server.cpp:488-512` rejects a call whose argument count falls outside `rpcCvtTable` with `RPC_INVALID_PARAMS`, "Too many parameters…". That happens before the handler runs. The JSON *types* of arguments are still checked only by each handler.

**Global facts that hold for every component**
- **Deprecated features:** every one is allowed by default (`ref/ycash6/src/deprecation.h:47-75`), including `gbt_oldhashes`, `getnewaddress`, `z_getnewaddress`, `z_getbalance`, `z_gettotalbalance`, `z_listaddresses`, `legacy_privacy`, `wallettxvjoinsplit` and `accounts`. So nothing deprecated breaks unless an operator passes `-allowdeprecated=none`.
- **`z_sendmany` privacy policy:** the default is `AllowFullyTransparent` unless a UA is involved (`ref/ycash6/src/wallet/rpcwallet.cpp:395-401`).
- **Wallet backup:** never required. `fRequireWalletBackup` defaults to false (`ref/ycash6/src/chainparams.h:213`) and no network sets it true (`chainparams.cpp:780` is regtest). So `EnsureWalletIsBackedUp` (`rpcwallet.cpp:106`) does not bite `getnewaddress` or `z_getnewaddress`.
- **ZIP-317 unpaid-action limits are effectively off.** Both are `SIZE_MAX` (`ref/ycash6/src/zip317.h:42,54`). The checks that remain are min relay fee and the Ycash per-Sapling-output floor (`ref/ycash6/src/main.cpp:1941-1965`).
- **Branch IDs are identical at both pins:**
  - `ref/ycash/src/consensus/upgrades.cpp:18-53`
  - `ref/ycash6/src/consensus/upgrades.cpp:19-68`
  - 6.20.0 adds NU5, NU6 and NU6.1 IDs, which are not active on Ycash or on the devnet. The devnet passes no `-nuparams` for them.
- **Coinbase stays a v4 transaction while NU5 is inactive.** It has an empty Sapling bundle for a t-addr miner (`ref/ycash6/src/miner.cpp:249-264,267-290`). The block header's 4th field is `hashBlockCommitments`, which equals the v4.5.0 `hashLightClientRoot` pre-NU5.
- **Equihash on regtest:** ycash6 keeps (48,5) on regtest under every upgrade. That is baseline fix 3, `e98128239`. The **unfixed `ref/ycash6` binary does not**, so every Phase 7 run must use the `ycash6` build.
- **Version strings:**
  - `CLIENT_VERSION` goes from 4.5.0-50 (`ref/ycash/configure.ac:3-6`) to 6.20.0-50 (`ref/ycash6/configure.ac:3-6`), so `getinfo.version` becomes 6200050.
  - `CLIENT_NAME` is `YcashCpp` at both pins.
- **ZMQ:** the topics (`pubhashblock/pubhashtx/pubrawblock/pubrawtx/pubcheckedblock`), the flags and the notifier hooks are unchanged:
  - `ref/ycash/src/zmq/zmqnotificationinterface.cpp:38-42`
  - `ref/ycash6/...:39-43`
  - `init.cpp` `:453-456` (v4.5.0) and `:439-442` (6.20.0)
- **Datadir, conf name and params dir are unchanged:**
  - `ycash.conf`; `~/.ycash` and `…/Ycash`; `ZcashParams` / `.zcash-params`.
  - Citations: `ref/ycash/src/util.cpp:76,234-281` and `ref/ycash6/src/util/system.cpp:82,241-276`.
  - 6.20.0 bundles the Sapling params in the binary and loads `sprout-groth16.params` lazily (`ref/ycash6/src/init.cpp:871-899`).
  - 6.20.0 also builds a new binary, `ycashd-wallet-tool` (`ref/ycash6/src/Makefile.am:39,217`).
- **JSON-RPC envelope:** `"params"` null or absent is treated as `[]` (`ref/ycash6/src/rpc/server.cpp:427-433`, same as `ref/ycash/...:442-448`). The warm-up error `-28` is unchanged.

---

## 1. yecwallet-dd (Qt GUI; JSON-RPC; bundles ycashd)

Sources: `src/connection.cpp`, `src/zcashdrpc.cpp`, `src/controller.cpp`, `src/mainwindow.cpp`, `src/settings.cpp`, `build.sh`, `tests/yellowbacktab_test.cpp`.

| Interface (call site) | v4.5.0 | 6.20.0 | Impact |
|---|---|---|---|
| `getrescaninfo` (no params). Sent as a pre-call before **every** RPC (`connection.cpp:765-796`), as the startup probe (`connection.cpp:468-477`), and by `refreshRescanStatus` (`zcashdrpc.cpp:152-165`). | Present (`ref/ycash/src/wallet/rpcdump.cpp:731`, `rpcwallet.cpp:5250`). | **Removed** (absent from the table, so the reply is HTTP 404 "Method not found"). | **Adapt component.** It works through the error fallbacks (`connection.cpp:790-794`, `:478-482` → `getinfo`). Costs: every call becomes two round trips; the rescan dialog never shows; a long synchronous rescan can no longer be detected. |
| `rescanblockchain [startHeight]` (`zcashdrpc.cpp:168-177`; `mainwindow.cpp:470-475`) | Present (`rpcdump.cpp:80`) | **Removed.** Rescans run only inside the imports (F-7/V-3). | **Adapt component.** The Rescan menu item fails with "Method not found". |
| `importprivkey [key, "", bool, height]`, 4 args (`zcashdrpc.cpp:247-256`; `mainwindow.cpp:658`) | 1–4 args, with a Ycash `startHeight` (`ref/ycash/src/wallet/rpcdump.cpp:121`, guard `params.size() > 4`, height read at `:48`) | 1–3 args (`ref/ycash6/src/wallet/rpcdump.cpp:87`, `+6`). Table row `{{s},{s,o}}` (`rpc/common.h:126`). | **Adapt component (BREAK).** "Too many parameters for method `importprivkey`". Drop the 4th argument; 6.20.0 always rescans from genesis. |
| `z_importivk [ivk, "yes"\|"no", height(int), zaddr]` (`zcashdrpc.cpp:95-107`; `mainwindow.cpp:655`) | Order `vkey, rescan, startHeight, zaddr` (`ref/ycash/src/wallet/rpcdump.cpp:1211`, help `+8..+11`) | **Reordered** to `ivk, zaddr, rescan, startHeight`, with 2 required (`ref/ycash6/src/wallet/rpcdump.cpp:1180`, help `+8..+16`; `rpc/common.h:138`). | **Adapt component (BREAK).** `params[1]="yes"` is decoded as an address and `params[2]=<int>`.get_str() throws. Fix: send `[ivk, zaddr, rescan, height]`. |
| `z_importkey [key, yes/no, height]` (`zcashdrpc.cpp:234-243`) | 1–3 | 1–3, `{{s},{s,o}}` | None |
| `z_importviewingkey [key, yes/no, height]` (`zcashdrpc.cpp:109-121`) | 1–3 | 1–3, `{{s},{s,o}}` | None |
| `getinfo` reads `.testnet .blocks .version .connections` (`controller.cpp:261-289`) | Same key set (`ref/ycash/src/rpc/misc.cpp` getinfo) | Same keys (`ref/ycash6/src/rpc/misc.cpp:44-72`). `version` = 6200050. | None. The migration gate `>= 2000552` (`controller.cpp:459`) still passes. |
| `getblockchaininfo` reads `.verificationprogress .blocks .estimatedheight` (`controller.cpp:306-313`) | Present | Present, plus `transactions` and `chainSupply` | None |
| `getnetworksolps` (no params) (`zcashdrpc.cpp:349-363`) | Present | Present, `{{},{o,o}}` | None |
| `z_gettotalbalance [0]` reads `transparent/private/total` as strings (`zcashdrpc.cpp:274-286`) | Same keys | Same keys. Deprecated, allowed by default. | None. Test needed: the string formatting. |
| `listunspent [0]` and `z_listunspent [0]` read `address confirmations txid amount spendable` (`zcashdrpc.cpp:52-78`) | Present | Present. `listunspent` drops `account`; `z_listunspent` drops `memo` and adds `pool/type/account`. | None (the dropped fields are not read) |
| `z_listaddresses` with no params, `[false]` and `[true]` (`zcashdrpc.cpp:39-50,409-414,459-464`) | Present | `{{},{o}}`; deprecated-allowed | None. Test needed: UA-derived addresses are not listed. |
| `getaddressesbyaccount [""]` (`zcashdrpc.cpp:25-37`) | Present | Present: the restored legacy accounts (`rpcwallet.cpp:6468` section, `fEnableLegacyAccounts`) | Test needed: it must return every t-addr. |
| `listtransactions` (no params) reads `fee address category time txid amount confirmations` (`zcashdrpc.cpp:288-299`) | Present | Present; `account` dropped | None |
| `z_listreceivedbyaddress [zaddr, 0]` reads `change txid memo amount` (`zcashdrpc.cpp:654-689`) | `memo` | `memo` (and `memoStr`) via `AddMemo`, `ref/ycash6/src/rpc/server.cpp:660-674` | None. The empty memo is still `f6…`. |
| `gettransaction [txid]` reads `confirmations time blocktime` (`zcashdrpc.cpp:608-631,694-729`) | Present | Present | None |
| `z_sendmany [from, [{address, amount(str), memo?}], 1, fee(double)]` (`zcashdrpc.cpp:301-320`; `controller.cpp:121-149`) | 2–4 args | 2–5 args (`rpcwallet.cpp` z_sendmany `+6`). The fee is honoured if ≤ `-maxtxfee` (`wallet_tx_builder.cpp:469-476`). Default policy is `AllowFullyTransparent`. Sapling padding to 2 outputs (F-17) stays under the flat 1000-zat floor. | Test needed: t→t, t→z, z→t and z→z sends at the wallet's `DEFAULT_FEE` (`settings.cpp:404-410`). |
| `z_getoperationstatus` reads `id status result.txid error.message` | Present | Present | None |
| `z_getnewaddress ["sapling"]` | Present | Present (deprecated-allowed; backup not required) | None |
| `z_getnewaddress ["sprout"]` (`mainwindow.cpp:566-567,1381-1382`) | Allowed | **Refused after Canopy** (`ref/ycash6/src/wallet/rpcwallet.cpp` z_getnewaddress `+42..+46`) | Adapt component (low): hide the Sprout option. |
| `getnewaddress`, `validateaddress`, `z_validateaddress`, `z_exportkey`, `dumpprivkey`, `z_exportviewingkey`, `z_exportivk` | Present | Present; arities fit | None |
| `z_getmigrationstatus` / `z_setmigration [bool]` (`zcashdrpc.cpp:365-397`) | Present | Present, with the same key set | None |
| `stop` | Present | Present | None |
| conf `fastsync=1` (written `connection.cpp:201`, read `:673`) | `-fastsync` (`ref/ycash/src/init.cpp:404`) | **Renamed** to `-ibdskiptxverification` (`ref/ycash6/src/init.cpp:369`). The unknown key is silently ignored. | Adapt component (low): the GUI option becomes a no-op. |
| conf `server rpcuser rpcpassword addnode experimentalfeatures yellowback proxy datadir` (`connection.cpp:130-218`) | OK | OK. `yellowback` gets `experimentalfeatures` (`ycash6/src/experimental_features.cpp:27,69`). | None |
| Params check: requires `sapling-spend/output` and `sprout-groth16` and downloads them from z.cash (`connection.cpp:221-235,584-613`) | Needed | Sapling params are bundled; sprout is lazy | None. The download is redundant; it needs the network on first run. |
| `build.sh --ycashd PATH`: copies it as `ycashd`, `lipo -archs` check (`build.sh:180-207`) | `ycash-dd/src/ycashd` | `ycash6/src/ycashd`. A new `ycashd-wallet-tool` is not needed by the GUI. | Test needed: a macOS arm64 package from the 6.20.0 binary; `otool -L` shows no Rust/Homebrew dylibs. |
| Yellowback: `yed_getinfo.rpcversion == 3` (`yellowbackrpc.h:23`) | 3 | 3 (the contract JSON is unchanged) | None |

**Phase 7 acceptance (yecwallet-dd)**
1. Run `tests/check-rpc-contract.py` and the QTest suite offline.
2. Run `bash build.sh macos-arm64 --package --ycashd ../ycash6/src/ycashd`, then launch the .app against a fresh mainnet-less datadir (`--conf` regtest). The wallet must reach "ycashd is online" despite the `getrescaninfo` 404.
3. Run the devnet case against `ycash6/contrib/yellowback/devnet/yellowback-devnet up` with `YELLOWBACK_DEVNET_DIR` (the tests read `node%1/ycash.conf`; ycash6 adds `clockoffset`, which is harmless).
4. Do the four scenario walk-throughs.
5. **Add manual checks:**
   - import a WIF with a start height;
   - import a `zivk…` with its zaddr;
   - Rescan from the menu;
   - send t→t, t→z, z→t and z→z at the default fee;
   - new Sprout address (expect a clear error);
   - the migration panel.

The first three manual checks are expected to fail until the component is adapted.

---

## 2. lightwalletd-dd (Go; node RPC; read-only `yed_*` proxies)

Sources: `common/common.go`, `frontend/service.go`, `common/yellowback.go`, `frontend/yellowback.go`, `parser/*`, `scripts/devnet-test.sh`, `frontend/yellowback_devnet_test.go`.

| Interface | v4.5.0 | 6.20.0 | Impact |
|---|---|---|---|
| `getblockchaininfo []` reads `chain`, `upgrades["76b809bb"].activationheight`, `blocks`, `consensus.chaintip`, `estimatedheight` (`common/common.go:67-83,181-206`) | Present | Same keys, plus `transactions`/`chainSupply`. The Sapling ID is unchanged; `chaintip` is the Ycash ID. | None |
| `getinfo []` reads `build`, `subversion` (`common/common.go:86-89,171,213-214`) | Present | Same keys; the strings now say 6.20.0 | None. They are pass-through, and the byte-equality gate compares fork vs baseline on the same node. |
| `getblock ["<height>", 0]` raw hex, parsed by `parser/block.go` (`common/common.go:219-257`) | Verbosity handling `ref/ycash/src/rpc/blockchain.cpp` getblock `+60..+69` | Identical (`ref/ycash6/...` getblock `+93..+102`). `parseHeightArg` gives the same `-8` error (`:894-909` vs `ref/ycash:595-610`). | None, **while NU5 is inactive**. The parser is v1–v4 only (`parser/transaction.go:329-475`), and header field 4 is opaque. |
| `getaddresstxids [{addresses,start,end}]` (`frontend/service.go:102-113`) | `getHeightRange` rejects start/end ≤ 0 (`ref/ycash/src/rpc/misc.cpp:780-800`). Needs `-insightexplorer`. | More permissive: start ≥ 0, end clamped to tip (`ref/ycash6/src/rpc/misc.cpp:829-860`). Gated on `fExperimentalInsightExplorer \|\| fExperimentalLightWalletd` (`:1144`). `-insightexplorer` needs `-txindex` (`init.cpp:1751-1753`) and `-experimentalfeatures` (`experimental_features.cpp:36`); it now has its own leveldb (`-dbcache-insight`). | None. yew already clamps start ≥ 1 (`yew/core/src/sync.rs:113-115`). |
| `getaddressbalance` / `getaddressutxos [{addresses}]` read `balance`; `address txid outputIndex script satoshis height` | Present | Same key sets | None |
| `z_gettreestate ["<h>"\|"<hash>"]` reads `height hash time sapling.commitments.finalState sapling.skipHash` (`common/common.go:99-109`; `service.go:200-237`) | sprout + sapling | Adds `orchard` only if NU5 has an activation height (`ref/ycash6/src/rpc/blockchain.cpp` z_gettreestate `+87..+113`). The Sapling block is unchanged. | None |
| `getrawtransaction [txid,1]` reads `hex height`; `[txid,0]` | `params[1].get_int()` | Same (`rawtransaction.cpp` getrawtransaction `+177`). Adds `authdigest` and `orchard`. | None |
| `sendrawtransaction [hex]` | 1–2 args | `{{s},{o}}`, `{{s},{o,o}}` on ycash6 (H7) | None. Reject reason strings are new (per-Sapling-output floor, ZIP-317). |
| `getrawmempool []` → `[]string` | Present | Present | None |
| `getexperimentalfeatures` looks for `"yellowback"` (`common/yellowback.go:106-118`) | `ycash-dd/src/experimental_features.cpp:65` | `ycash6/src/experimental_features.cpp:69` | None |
| `yed_*` allow-list (`common/yellowback.go:32-52`), `rpcversion == 3` | — | Unchanged | None |
| `getcompactblock` / `getcompactblockrange` | Absent | New in `040894344b`. Gated by `-compactblocks` (experimental, `experimental_features.cpp:26,65`); range ≤ 10000. It hand-emits CompactBlock with **transparent vin/vout fields 7/8**, which are not in the yodl 0.4.6 proto, and omits `fee`. | **Do not adopt in Phase 7.** The fork must stay byte-equal to the yodl baseline. Adopting them is a separate change needing a proto bump on both servers; record as optional future work. |
| `-insightexplorer -txindex` on node 0 (launcher `:719`) | OK | OK (the yellowback args carry `-experimentalfeatures`) | None |
| Harness path `NODE_REPO=${YCASH_DD:-$WORKSPACE/ycash-dd}` (`scripts/devnet-test.sh:18-20`) | — | — | Invocation only: `YCASH_DD=$WORKSPACE/ycash6` |

**Phase 7 acceptance (lightwalletd-dd)**

Run:
```
YCASH_DD=$WS/ycash6 LWD_DEVNET_DIR=~/yb-devnet-lwd6 scripts/devnet-test.sh --up …
```
- That runs `go test -tags devnet -run TestDevnet ./frontend/`: `TestDevnetBaselineByteEquality` (yodl baseline binary on the same ycash6 node), `…HasNoYellowback`, `…WalletMintSeenThroughServer` and `…RawMintThroughServer`.
- Add a spot check: `GetTreeState` at a height with Sapling notes equals `z_gettreestate` on the node.
- Add a spot check: `GetTaddressTxids` with start=1.

---

## 3. yolo (Rust stratum pool)

Sources: `src/rpc.rs`, `src/template.rs`, `src/work.rs`, `src/tx.rs`, `src/equihash.rs`, `src/lib.rs`, `tests/regtest.rs`.

| Interface | v4.5.0 | 6.20.0 | Impact |
|---|---|---|---|
| `getblockchaininfo []` reads only `chain` → Equihash auto (`lib.rs:66-84`; `equihash.rs:19-25`) | `"regtest"` → (48,5) | Same. Regtest stays (48,5) only on the ycash6 build (baseline fix 3). | None on ycash6. A mismatch on unfixed `ref/ycash6`. |
| `getblocktemplate []`, required: `version previousblockhash coinbasetxn.data target bits height` (`template.rs:25-44`) | `coinbasetxn` always present (`ref/ycash/src/rpc/mining.cpp:505`) | Always present (`ycash6/src/rpc/mining.cpp:537`); the other required keys are unchanged (`:395-404`) | None |
| Header field 4 from `lightclientroothash ?? finalsaplingroothash ?? ""` (`template.rs:56-61`; `work.rs:145`) | Always emitted (`ref/ycash/src/rpc/mining.cpp` GBT `+340,+342`) | Emitted **only under `gbt_oldhashes`** (`ycash6/src/rpc/mining.cpp:803`; default-allowed). Otherwise `defaultroots.chainhistoryroot` (pre-NU5) or `defaultroots.blockcommitmentshash` (NU5+). | None by default. **Adapt component (recommended):** fall back to `defaultroots`, so `-allowdeprecated=none` or a future removal does not produce an empty root (an invalid header). |
| `coinbasetxn.{foundersreward, ydfpercentage, foundersaddress, required}` | Always all of them (`ycash-dd/src/rpc/mining.cpp:735-737`) | `ydfpercentage`/`foundersaddress` gone; `foundersreward` only during the YDF mandate; `required` always true (`ycash6/src/rpc/mining.cpp` GBT `+332..+342`) (F-19) | None (yolo reads none of them) |
| `coinbasetxn.data`: parser demands v4 `0x80000004`/`0x892F2085`, one null input, zero shielded counts (`tx.rs:12-14,45-98`) | v4 coinbase | v4 while NU5 is inactive; empty Sapling bundle for a t-addr `mineraddress` (`ref/ycash6/src/miner.cpp:249-264`) | None. **Test needed**, because 6.20.0 builds the coinbase through the Rust Sapling builder. |
| `coinbaseaux.flags` | With `-yellowback` | Same: `coinbaseaux` only with `g_yellowback` when `coinbasetxn` (`ycash6/.../mining.cpp:390`) | None |
| New `transactions[].authdigest`, `defaultroots`, `blockcommitmentshash` | — | Added | None (ignored; no `deny_unknown_fields`) |
| `submitblock [hex]`: null = accept, any string = reject (`stratum.rs:353-367`) | BIP22 | Same, `{{s},{s}}` | None |
| `validateaddress [addr]` reads `isvalid`, `scriptPubKey` (`rpc.rs:182-194`) | Keys `ref/ycash/src/rpc/misc.cpp` validateaddress `+36..+52` | Identical | None |
| `-mineraddress` t-addr (README:131-147) | Accepted | Accepted: Sapling or P2PKH or UA (`ref/ycash6/src/init.cpp:1406-1424`) | None |
| `tests/regtest.rs:311,313`: `setmocktime [now-3600]` … `setmocktime [0]` | Works on any regtest node | **Refused** unless the node started with `-mocktime` (`ref/ycash6/src/rpc/misc.cpp:519-520`, F-8). Under a fixed clock, `0` means epoch, not "unmock". | **Adapt component (test only, BREAK):** start node A with `-mocktime=<now-3600>`, generate 101, restart it without `-mocktime`. Alternatively drop the trick and generate in smaller bursts. Note F-14 too: a fixed clock freezes tx relay. |

**Phase 7 acceptance (yolo)**
1. `ZCASHD=$WS/ycash6/src/ycashd YOLO_BIN=$WS/yolo/target/release/yolo qa/rpc-tests/yellowback_stratum.py` in ycash6. That is five cells × 2 blocks: tag on both nodes, the scriptSig layout, `vout[0]` payee, accepted=2/rejected=0.
2. `cargo test --features regtest` with `YCASHD=…/ycash6/src/ycashd`, after the mocktime fix.
3. The `--stratum` pool seat on a ycash6 devnet: `yellowback-devnet up --role pool`, and the stratum-miner mines ≥ 10 blocks accepted.
4. A one-off GBT with `-allowdeprecated=none` to confirm the fallback (after the adaptation).

---

## 4. chain-viz (Rust read-only visualizer)

Sources: `src/rpc.rs`, `src/collector.rs`, `src/model/revenue.rs`, `src/source/zmq.rs`, `tests/readonly_gate.rs`.

| Interface | v4.5.0 | 6.20.0 | Impact |
|---|---|---|---|
| `getblockchaininfo []`: required `chain blocks bestblockhash` (`rpc.rs:322-334`) | Present | Present | None |
| `getbestblockhash []` | Present | Present | None |
| `getblock [hash, 2]`: required `hash height`; reads `size time chainwork tx[] previousblockhash`, plus `version`/`nextblockhash` from `extra` (`rpc.rs:363-380`; `collector.rs:784-798`) | `blockToJSON` keys | A superset: adds `blockcommitments authdataroot finalorchardroot chainSupply blockfee trees` | None |
| Transactions in `getblock 2` and `getrawtransaction [txid,1]`: required `txid`, `vout[].value`, `vout[].scriptPubKey` (`hex`, `addresses[0]`) (`rpc.rs:440-464`) | `TxToJSON` | A superset (`authdigest`, `orchard`) | None |
| `getrawmempool [true]`: optional `size fee time height depends` (`rpc.rs:392-405`) | Has `startingpriority/currentpriority` | Drops the priorities; adds `modifiedfee descendant*` (`ref/ycash6/src/rpc/blockchain.cpp:627-641`) | None |
| `getchaintips []`: required `height hash branchlen status` | Same | Same | None. Test needed: F-18 (a rejected block keeps its index entry after restart) may show an extra `invalid` tip. |
| `getblocksubsidy [height]`: required `miner`; reads `founders`, `fundingstreams[].valueZat`, `foundersaddress` (`revenue.rs:236-240`) | Emits all of them (`ref/ycash/src/rpc/mining.cpp` getblocksubsidy) | **Only `miner founders totalblocksubsidy`** (`ref/ycash6/src/rpc/mining.cpp` getblocksubsidy, tail) | None functionally. `revenue.rs:268-273` falls back to matching the output equal to `founders`. **Test needed:** the revenue view and test (e). If the miner's own output ever equals the YDF share, attribution would be ambiguous. |
| ZMQ `hashblock`, `hashtx` on one socket (`zmq.rs:44-45`) | Same | Same | None |
| `yed_*` reads | — | Unchanged | None |
| Never calls `getblocktemplate`/`getinfo` (the read-only gate `tests/readonly_gate.rs:15-46` forbids GBT) | — | — | None |
| C-F33 reorg depth (`docs/plans/chain-viz-plan.md:696`) | `assert(nWitnessCacheSize > 0)` unconditional (`ref/ycash/src/wallet/wallet.cpp:1735-1737`); `WITNESS_CACHE_SIZE = 100` (`wallet.h:282`) | Assert only if the wallet has observed Sprout or Sapling notes (`ref/ycash6/src/wallet/wallet.cpp:3590-3596`). `WITNESS_CACHE_SIZE` is still `MAX_REORG_LENGTH+1` = 100 (`wallet.h:89`, `main.h:66`). `ActivateBestChain` refuses a reorg > 99 with `StartShutdown` at both pins (`ref/ycash6/src/main.cpp:4673-4689`; `ref/ycash/src/main.cpp:3772`). | The note stands for wallets holding shielded notes and relaxes for transparent-only wallets. Keep the "never ≥ 99 deep" rule; re-word C-F33 with the 6.20.0 citation. |

**Phase 7 acceptance (chain-viz)**
1. `CHAINVIZ_BIN=… qa/rpc-tests/yellowback_chainviz.py` in ycash6. It checks:
   - (a) health
   - (b) block event
   - (c) mint
   - (d) reorg
   - (e) revenue (`totals.enforcefee`, rows; also eyeball the `SubsidyOther` rows)
   - (f) RPC budget (`getblocksubsidy` ≤ blocks+22)
   - (g) session file
2. A devnet session with `invalidateblock tip-2` reorgs and one restart of a node that rejected a block (F-18).
3. Re-run `revenue-blocks.json` fixture replay. Note: it was recorded from v4.5.0 and includes `foundersaddress`; a 6.20.0 recording will not.

---

## 5. yew (Flutter/Rust; through lightwalletd gRPC only)

There are no node RPCs. It depends on these lightwalletd fields:
- `GetLightdInfo.consensusBranchId`, the ZIP-243 sighash branch: unchanged Ycash ID.
- `chainName`, `blockHeight`, `taddrSupport`.
- `GetBlock.hash`, `GetLatestBlock`, `GetAddressUtxos`, `GetTaddressTxids` (start clamped ≥ 1, `core/src/sync.rs:113-115`), `GetTaddressBalance`, `SendTransaction`, plus the `YellowbackStreamer` methods.

The tx parser is v3/v4 only (`core/src/tx.rs:243-320`) and the fee is a flat 1000 zat (`core/src/params.rs:111`). Both are fine while NU5 is inactive: 1000 zat ≥ min relay, there are no Sapling outputs, and the unpaid-action limits are `SIZE_MAX`.

| Interface | v4.5.0 | 6.20.0 | Impact |
|---|---|---|---|
| Branch ID via `GetLightdInfo` | `374d694f` (Ycash) | Same | None |
| v4-only tx parse/serialise | v4 | v4 (NU5 inactive) | None (latent: NU5 would break it) |
| Flat 1000-zat fee, transparent-only | Accepted | Accepted (`ref/ycash6/src/main.cpp:1941-1965`; `zip317.h:42,54`) | Test needed |
| Devnet tooling defaults: `YEW_DEVNET_TOOL` default `ycash-dd/...` (`scripts/devnet-w{1,2,4}.sh:19-23`, `core/tests/devnet.rs:87,123`); `dn()` `cd`s into `ycash-dd` | — | — | Invocation only: set `YEW_DEVNET_TOOL=$WS/ycash6/contrib/yellowback/devnet/yellowback-devnet`. The `cd ycash-dd` is harmless while ycash-dd exists; better to `cd` to the tool's repo. |

**Phase 7 acceptance (yew):** run `scripts/devnet-w4.sh up` with `YEW_DEVNET_TOOL` pointing at ycash6 and lightwalletd-dd `--yellowback`. Then run `core/tests/devnet.rs` (`YEW_DEVNET=1`, w1/w2/w4) and the Flutter M1 test `app/integration_test/m1_flow_test.dart` (`YEW_SERVER`).

---

## 6. Devnet launcher JSON contract (`devnet.json`)

- **Code differences:** `ycash-dd/contrib/yellowback` vs `ycash6/contrib/yellowback` differ only in `devnet/yellowback-devnet`, in 4 lines that rename `BITCOIND` to `ZCASHD` (`:381,384,700,702`). Phase 5 owns that.
- **Schema:** unchanged, and it is the one written at `yellowback-devnet:735-744`.
- **Readers:**
  - lightwalletd reads `pools` and `rpc{n}.{port,user,password}` (`frontend/yellowback_devnet_test.go:84-130`).
  - chain-viz reads `rpc{n}.{url,user,password}`, `nodes{n}.zmq.{hashblock,hashtx}`, `pools`, `attestors`, `portseed` (`rpc.rs:40-85`; `main.rs:158-165`).
  - The GUI and yolo read no `devnet.json`. The GUI reads `node%1/ycash.conf`.
- **Launcher RPCs** are all present with fitting arity on 6.20.0: `generate`, `getnewaddress`, `sendtoaddress`, `importprivkey` (3 args), `sendmany("",{})`, `createrawtransaction` (4 args, `{{o,o},{o,o}}`), `signrawtransaction` (deprecated-allowed), `getnetworkinfo.relayfee`, `getinfo.paytxfee`, `getblockchaininfo.consensus.nextblock/upgrades`, `addnode onetry`, `validateaddress`, `dumpprivkey`, `decoderawtransaction`, `gettransaction.hex`. `-rest`, `-keypool`, `-discover`, `showmetrics` and `listenonion` all still exist.
- **Impact:** none for the components, provided Phase 5's gate (schema unchanged) holds.

---

## 7. Likely breakages, ranked by risk

1. **yecwallet `z_importivk` argument order** (BREAK; adapt component). 6.20.0 is `ivk, zaddr, rescan, startHeight` (`ref/ycash6/src/wallet/rpcdump.cpp:1180`); the wallet sends `ivk, rescan, height, zaddr` (`yecwallet-dd/src/zcashdrpc.cpp:95-107`). Every `zivk` import fails.
2. **yecwallet `importprivkey` with 4 args** (BREAK; adapt component). The server arity table now enforces 1–3 (`ref/ycash6/src/rpc/common.h:126`, `server.cpp:488-512`); the wallet sends 4 (`zcashdrpc.cpp:247-256`). Every WIF import fails.
3. **yecwallet `rescanblockchain` / `getrescaninfo` removed** (adapt component).
   - The Rescan menu fails.
   - Every RPC pays a failed `getrescaninfo` round trip first; it works through the fallback, at twice the request count.
   - Rescan progress can no longer be shown, and synchronous import rescans may make the UI look hung.
4. **yolo `tests/regtest.rs` `setmocktime`** (test-only BREAK; adapt component). F-8 means it is refused without `-mocktime`, and under `-mocktime`, `0` is not "unmock".
5. **yolo header root depends on `gbt_oldhashes`** (latent; adapt component recommended). `-allowdeprecated=none` or a future removal leaves an empty `hashLightClientRoot`, so every share submits an invalid block. Fall back to `defaultroots.chainhistoryroot` pre-NU5 and `defaultroots.blockcommitmentshash` post-NU5.
6. **Equihash on an unfixed 6.20.0 binary** (operational). Without baseline fix 3, regtest moves off (48,5) and yolo `--equihash auto` mismatches. Always use the `ycash6` build.
7. **chain-viz revenue without `foundersaddress`** (low; test needed). The value-match fallback covers it, but the fixture was recorded on v4.5.0.
8. **yecwallet `fastsync=1` silently ignored** (low). It was renamed `-ibdskiptxverification`.
9. **yecwallet Sprout address creation refused after Canopy** (low).
10. **v4-only parsers in lightwalletd-dd and yew** (latent). Harmless while NU5 is inactive on Ycash; any 6.20.0-era NU5 activation needs both parsers updated first.
11. **Harness paths default to `ycash-dd`** (invocation). `YCASH_DD` covers lightwalletd; `YEW_DEVNET_TOOL` and the `cd ycash-dd` cover yew; chain-viz's README and yecwallet's docs point at `ycash-dd/...`. Running Phase 7 against ycash6 needs these overrides or doc edits.
12. **`getcompactblock[range]`** (decision, not breakage). Do not adopt now: the experimental flag, transparent fields outside the 0.4.6 proto, and the baseline byte-equality gate all argue against it.

No interface that yolo, chain-viz, lightwalletd-dd or the devnet launcher actually reads was removed or reshaped in a way they fail on. All the hard breaks are in yecwallet's key-import and rescan paths, plus yolo's own regtest test. These are findings against the components' assumptions about stock RPCs, not against the `yed_*` contract.
