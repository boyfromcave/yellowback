# Survey C — the Yellowback/vault delta inventory (what kogany has to carry)

Date: 2026-11-01. Lane C of the kogany planning briefing (`wt/BRIEFING-kogany.md`).

Pins surveyed:

| Tree | Ref | Commit |
|---|---|---|
| `ycash6` | `upgrade/vault` (vs `ycash6-legacy` = `040894344b`) | `65cb4ae0f` |
| `ycash-dd` | `upgrade/vault` (vs `ycash-legacy` = v4.5.0 `624c12814`) | `781946771` |
| `librustzcash6` | `upgrade/vault` (vs `librustzcash6-legacy` = `ec525fae82`) | `af841431` |
| `ref/zakura` | detached | `2b062412c` |
| clients | `upgrade/vault`: lightwalletd-dd `a1d141e`, yecwallet-dd `02fbf0f`, yew `c4dd450`, chain-viz `0165934`, x402-ycash `334d74c`, hawkeye `7022742`, yolo `0659f41`, ycash-infra `c180ceb` | |

All `path:line` citations below are in `ycash6` at `65cb4ae0f` unless another tree is named.

**Summary.** The 6.20.0 line's delta is 5,498 files, +192,129 / −455 lines over 685 commits
(ycash-dd: 5,444 files, +188,230 / −328, 926 commits). The briefing's "~86k" undercounts: 4,993 of
the files are fuzz corpora (`src/fuzzing/*`), and `qa/` (+49k), `src/test/` (+38k) and `contrib/`
(+40k) together are about 70 % of the lines. The **production node code** is about 30k lines:
16.2k vendored post-quantum C (`src/crypto/pq`, SLH-DSA + Falcon, of which only the verify set is
consensus), 14.2k of `src/yellowback/`, 3.8k of `src/vault/`, 7.7k of RPC, ~0.9k of `src/script/`,
and ~1.5k of hooks in `main.cpp`/`init.cpp`/`miner.cpp`/`policy.cpp`/`chainparams.cpp`. Of that, a
**wallet-less Rust node needs roughly 60 %**: the consensus core (upgrade plumbing, BIP68/CSV, three
opcodes, PQ verification, templates, acts, set state, the YED module and its index — the YED index
is consensus state since U-21), relay policy, the mining hooks (including the coinbase price tag,
which feeds a consensus rule), and the 32 node-context read RPCs. It does **not** need the 47
wallet-context RPCs (22 `set_*`/`vault_*` act RPCs, 25 `yed_*` wallet RPCs), the PQ signing code,
the wallet transaction builders (`txbuilder.cpp`, `coinselect.cpp`, `yellowback/wallet.cpp`) or the
node-side sign-once and equivocation guards — but that means the roles that sign **inside the node**
(attestors, Hawkeye bridge members, YecWallet's bundled node, x402's `rpcWalletSigner`) cannot run on
kogany without a design decision (open question 1). The cross-line invariant is the golden vectors
plus the two state hashes; for a third implementation in a different language it must be
re-expressed as "reproduces every vector byte-for-byte and the same `statehash` at every height"
(§6). The dependency order is a strict nine-layer stack (§5); nothing above layer 3 can be tested
against the vectors without the layers below.

## 1. How the inventory was taken

- `git -C ycash6 diff --numstat ycash6-legacy...upgrade/vault`, grouped by path; the same for
  `ycash-dd` and `librustzcash6`; `git log --oneline` counts (`make diff` / `make log` equivalents).
- The RPC tables at `src/rpc/vault.cpp:2607-2634`, `src/rpc/yellowback.cpp:2206-2232`,
  `src/rpc/yellowbackwallet.cpp:2404-2429`; wallet dependence read from the handlers and
  cross-checked against lightwalletd-dd's own classification (`lightwalletd-dd/common/yellowback.go:51-160`,
  which every `yed_*`/`set_*`/`vault_*` method must appear in, by its test).
- Specs: upgrade plan §15 (`docs/plans/yellowback-upgrade-plan.md:800-1310`), quantum spec
  (`docs/plans/yellowback-quantum-spec.md`), fees spec (`docs/plans/yellowback-quantum-fees-spec.md`),
  in-term plan, mapping §22 (`docs/mapping.md:1213-1308`), `doc/vault-rpc.md`, `doc/yellowback-rpc.md`,
  the cross-line manifest `qa/yellowback-cross-line.manifest`.
- Client usage: `git grep` of every client repo for `"(yed|set|vault)_…"` strings, then reading
  where they occur (allow-lists, devnet tests, semgrep fixtures excluded).

The two C++ lines' production file sets differ only in API-glue files (ycash-dd has
`rpc/client.cpp`, `sync.cpp`, two async wallet operations; ycash6 has `rpc/common.h`, `miner.h`,
`clientversion.h`, `util/system.cpp` and eight `src/rust/` files). The overlay itself is the same set.

## 2. Inventory by class

"Lines" = insertions on ycash6. "Wallet-less kogany" = does a Rust full node with no built-in wallet
need it: **Yes**, **No**, or **Re-express** (the obligation stays, the C++ artefact does not port).

### 2.1 Consensus — upgrade plumbing and transaction format

| # | Component | Where (ycash6) | Lines | Wallet-less kogany |
|---|---|---|---|---|
| C1 | `UPGRADE_VAULT`, branch id `0x6d5b7a31`, `NetworkUpgradeInfo` row, Equihash row inherits (192,7) | `src/consensus/params.h:56`, `src/consensus/upgrades.cpp` (+19) | ~40 | Yes |
| C2 | Previous-epoch walk-back (Vault's predecessor is the highest upgrade *with* a height, not index − 1, because NU5..NU6.2 never activate) → `old-consensus-branch-id` | `src/consensus/upgrades.cpp:151-158` | 9 | Yes (trap T1) |
| C3 | Activation heights: `NO_ACTIVATION_HEIGHT` on mainnet; three testnet profiles (fast/slow/legacy, `-testnetprofile`); regtest `-nuparams=6d5b7a31:<h>` excluded from the back-fill | `src/chainparams.cpp:154-158, 463-465, 640-767`, `src/chainparamsbase.cpp`, `src/init.cpp` | ~170 | Yes (lane B/D own the shape) |
| C4 | Vault is v4-only: non-Sapling version group invalid under Vault (`bad-vault-tx-version-group-id`); no ZIP-244 message for templates | `src/main.cpp:1217-1220`; librustzcash6 `components/zcash_protocol/src/consensus.rs:955-958` (`has_orchard() = false`), `zcash_primitives/src/transaction/mod.rs` | ~30 | Yes (trap T2) |
| C5 | Rust-side branch id: `NetworkUpgrade::Vault` / `BranchId::Vault` in zcash_protocol; `local_consensus` gains `vault` height; ycash6 `src/rust/src/params.rs` gains `Network::Test(heights)` | librustzcash6 `consensus.rs:501-988` (+36), `local_consensus.rs` (+38); ycash6 `src/rust/src/params.rs` (+54), `history.rs` (+8) | ~140 | Yes, in Zakura's `zakura-primitives`/`-protocol` forks or kogany's own parameters (lane B option) |
| C6 | History-tree leaf version for `BranchId::Vault` = V1 (Sapling-era leaves) | `src/rust/src/history.rs` | 8 | Yes (lane D: ZIP-221 in `zakura-mmr-tree`) |
| C7 | Protocol version 270200 for the Vault epoch; `MIN_PEER_PROTO_VERSION` unchanged; peers below 270200 dropped once Vault is current | `src/version.h:18`, `src/chainparams.cpp:154` | 15 | Yes (p2p handshake) |

### 2.2 Consensus — script

| # | Component | Where | Lines | Wallet-less kogany |
|---|---|---|---|---|
| S1 | BIP68 relative lock (height only; bit 22 → `bad-txns-vault-timelock`), `SEQUENCE_*` constants | `src/primitives/transaction.h` (+11), `src/main.cpp` sequence-lock functions, `src/main.cpp:2044-2046, 3828` | ~120 | Yes |
| S2 | `OP_CHECKSEQUENCEVERIFY` (0xb2, was NOP3) under `SCRIPT_VERIFY_CHECKSEQUENCEVERIFY` (bit 10) | `src/script/script.h:169`, `src/script/interpreter.cpp:414`, `interpreter.h:99` | ~50 | Yes |
| S3 | `OP_CHECKSETSIG` 0xc0 / `OP_CHECKSETDORMANT` 0xc1 under `SCRIPT_VERIFY_VAULT` (bit 11); checker interface `SetThreshold`/`CheckSetSigs`/`IsSetReleased`; set-sig digest `SHA256d("YcashSetSig"‖…‖ZIP-243 sighash with SIGHASH_ALL\|ANYONECANPAY)`; not cached; max one per evaluation | `src/script/script.h:180-181`, `interpreter.cpp:1013-1075`, `interpreter.h:103`; `src/vault/checker.{h,cpp}` (`SetSigChecker`, `checker.h:25`) | ~300 | Yes (trap T3: needs chain state inside the interpreter) |
| S4 | `OP_CHECKPQSIG` 0xc2 (SLH-DSA-SHA2-128s scheme 1; Falcon-512 padded scheme 2 under `SCRIPT_VERIFY_PQ_FALCON` bit 12, height `IsPQFalconActive`); 520-byte chunked sig/pk pushes; 20 policy sigops per op | `interpreter.cpp:1076`, `interpreter.h:108`, `src/consensus/params.h:219-221`, `src/script/sigcache.cpp` (+45) | ~200 | Yes |
| S5 | PQ verification primitives: `scheme.{h,cpp}` (`KeyHash = SHA256(scheme‖pk)`, `Verify`) over vendored PQClean Falcon verify + SLH-DSA C | `src/crypto/pq/scheme.h:34`, `src/crypto/pq/{falcon,slhdsa}/` (verify set only; README "Golden vectors") | ~6k consensus of 16.2k | Yes (trap T4: choose Rust crate vs vendored C) |
| S6 | `TX_PQPKH` standard type, `CPQKeyID` destination, `P2PQPKH` | `src/script/standard.h:64,82`, `standard.cpp` (+135), `src/pqkey.{h,cpp}` | ~300 | Yes for solver/destination; signing half No |

### 2.3 Consensus — the vault primitive (templates, acts, set state)

| # | Component | Where | Lines | Wallet-less kogany |
|---|---|---|---|---|
| P1 | Templates V (vault), I (intent), B (bond): parse/build, selector = last push 1..4 | `src/vault/template.{h,cpp}` (`ParseVault`/`ParseIntent` `template.h:120-121`, `ParseBondRedeem` `:134`) | 503 | Yes |
| P2 | Acts: the `YV` OP_RETURN (`SET_CREATE/JOIN/HEARTBEAT/REMOVE/EQUIVOCATION/…`), ≤16 recoverable sigs over `SHA256d("YcashSetAct"‖P‖vin[0].prevout)`; after activation an OP_RETURN starting `YV` *is* an act | `src/vault/act.{h,cpp}` (decode `act.h:148`) | 542 | Yes |
| P3 | Set state and rules: members, seats, maturity, liveness/dormancy/release, rate limit, bond index, template-output index (consensus input: I-2 coin height, replay), rules S-0, V-*, I-*; module ejection hook (U-25) | `src/vault/state.{h,cpp}` (`ApplyTx` `state.h:376`, `ApplyBlock` `:381`) | 1,398 | Yes |
| P4 | Storage: separate LevelDB `<datadir>/vaults/`, per-block undo kept 4,096 deep, tip marker, reconcile (disconnect by own undo / wipe + replay), `CoinsFromUndo`, `StateHash` | `src/vault/db.{h,cpp}`, `src/vault/node.{h,cpp}` (`StateHash` `node.cpp:505`, `TemplateRun` `node.h:128`) | 1,082 | Re-express (state model yes; LevelDB layout no, but the `StateHash` preimage yes — trap T5) |
| P5 | Module table (compile-time; one entry `YED\0`) and module interface (`ValidateCreate`/`ValidateSpend`, `GovernedSet`, `Ejections`) | `src/vault/module.cpp:14-18`, `src/vault/module.h:39-116` | 147 | Yes |
| P6 | Node hooks: snapshot after the parent per block (ConnectBlock) and per tx (ATMP); script flags by height (`GetVaultScriptFlags`); disconnect = undo or wipe at the activation height; act/template overlay committed after the block | `src/main.cpp:840-922, 2050-2217, 2895-2897, 3023-3034, 3413-3419, 3677-3691, 4342-4437` | ~370 | Yes (hook points: lane A) |

### 2.4 Consensus — the YED rule module (U-21: its verdict is `DoS(100)` wherever Vault is active and the attestor set is known)

| # | Component | Where | Lines | Wallet-less kogany |
|---|---|---|---|---|
| Y1 | Parameters (per network, in-term tiers 300/400/500 %, θ 125 %, fees, `maxMint` $100k, supply cap, testnet-fast scaling) — the constants yb-calibration derives | `src/yellowback/params.{h,cpp}` (`params.cpp:59-68`) | 708 | Yes (trap T7: calibration targets C++) |
| Y2 | Fixed-point arithmetic (fees FEE-1′ in `arith_uint256`, ratios, HALT-2 denominator) | `src/yellowback/math.h` (`:151, :192-230, :320`) | 439 | Yes — highest byte-exactness risk |
| Y3 | MINT payload (v4, PQ owner), YED token/carrier scripts, YED address encodings (`yb/yt/yr`, PQ 53-char forms) | `src/yellowback/payload.*`, `script.*`, `address.*` (`address.h:5-30`) | 1,327 | Yes (address encoding is RPC-facing only) |
| Y4 | Price attestations (74-byte) and bundles; attestor registry mirrored from `attestorSetId`'s set acts; EQV-1 by key trial | `src/yellowback/attest.*`, `bundle.*`, `state.cpp:780-924` | 624 + | Yes |
| Y5 | Coinbase price tag (`YED!`, 36 bytes in the coinbase scriptSig) — read by a byte scan; feeds the protocol-fee **payee eligibility** (`EligiblePayees`, `state.cpp:137, 253`) | `src/yellowback/tag.{h,cpp}` (`FindTag` `tag.h:71`) | 157 | Yes (trap T6: miners must write it) |
| Y6 | State machine: MINT, transfer, claim → intents, cancel (CAN-1/2/3), release, redeem with early fee, HALT-1/2/3, supply cap, ejection; `EvaluateBlock`, `MempoolCheckReason` | `src/yellowback/state.{h,cpp}` (2,770), `view.{h,cpp}` (1,431) | 4,201 | Yes |
| Y7 | The index: consensus state since U-21, `SCHEMA_VERSION` 15, `<datadir>/yellowback/`, undo, health (`AbortNode` if it cannot evaluate), `GetStateHash`, published fee price | `src/yellowback/index.{h,cpp}` (`index.h:38-47, 350, 360-394`), `db.*` | 1,949 | Re-express (state yes; layout no; `statehash` preimage yes) |
| Y8 | Module glue (registers with the primitive; inert without height + set) | `src/yellowback/module.{h,cpp}` | 259 | Yes |

### 2.5 Relay policy and mempool

| # | Component | Where | Wallet-less kogany |
|---|---|---|---|
| M1 | `YV` act OP_RETURN standard up to 1,200 bytes once active | `src/policy/policy.h:46` | Yes |
| M2 | Template scriptSig standardness (CLEANSTACK / selector malleability, 01/V-4) | `src/policy/policy.cpp:222, 260` | Yes |
| M3 | PQ dust, PQ fee rate, PQ max fee; ZIP-317 conventional fee floor for PQ-input transactions | `policy.cpp:390-409, 507-581` | Yes |
| M4 | Network fee in dollars per KB from the attested price (`AttestedFeePrice`, trusted unless HALT-1/3) | `policy.cpp:475-556`, `src/yellowback/index.cpp:303` | Yes |
| M5 | DoS scores: state-dependent failures DoS 0, byte-level act failures DoS 10 | `src/main.cpp:2202` | Yes (Zakura's peer-scoring differs: lane A) |
| M6 | Tip-change re-check: template scripts re-run; YED `MempoolCheck` sweep; BIP68 eviction in `removeForReorg` | `src/txmempool.cpp`, `src/yellowback/index.h:383-394` | Yes |
| M7 | Orphan size bound 99,999 bytes for PQ spends (ycash-dd only; 6.20.0 already) | `ycash-dd/src/main.h` `MAX_ORPHAN_TX_SIZE*` | Check Zakura's bound (lane A) |
| M8 | YED module mempool limits (`yellowback/policy.cpp`, `-yellowbackfee`, `-yellowbackmintlag`) | `src/yellowback/policy.{h,cpp}`, `src/init.cpp:438-439, 1639-1650` | Yes |

### 2.6 Mining

| # | Component | Where | Wallet-less kogany |
|---|---|---|---|
| N1 | `vault::TemplateRun::Try/Commit` per candidate (acts, template rules, template-input scripts, BIP68 at nHeight) | `src/miner.cpp` (+39), `src/vault/node.h:128` | Yes (Zakura's block-template builder) |
| N2 | YED `FilterTemplate` after the primitive's trial | `src/yellowback/policy.h:57` | Yes |
| N3 | Coinbase tag via `COINBASE_FLAGS` = `TagScript`, the miner's quote from `yed_setquote`; template rebuilt on quote change | `src/miner.cpp`, `src/yellowback/policy.h:42-45`, `src/rpc/mining.cpp` | Yes (yolo depends on it via `coinbasetxn`) |
| N4 | `getblocktemplate` refuses while the index is unhealthy; sigops field counts 20 per `OP_CHECKPQSIG` | `src/rpc/mining.cpp` (+17) | Yes |
| N5 | Coinbase Sapling anchor zero-init (a 6.20.0 baseline defect) | `src/miner.cpp` | No (C++ only) |

### 2.7 RPC

`rpcversion` 8 (`src/rpc/yellowback.cpp:62`). Node-context = needs no wallet.

| Group | Methods | Count | Wallet-less kogany |
|---|---|---|---|
| R1 vault read | `vault_getinfo` (incl. `statehash`, `attestorsetid`, `moduleactive`), `set_list`, `set_getinfo`, `vault_list` (without `mine`), `vault_decodescript` | 5 | Yes (drop the `wallet`/`mine` fields) |
| R2 yed read | `yed_getinfo`, `getstatehash`, `verifyindex`, `getstats`, `getprice`, `getactivation`, `listminers`, `gettag`, `getfeepayee`, `getvault`, `listvaults`, `listclaimable`, `listtokens`, `gettxinfo`, `decodepayload`, `validaterawtransaction`, `getblockverdict`, `estimatecollateral`, `estimatefee`, `gethistory`, `listattestors`, `getattestations`, `buildbundle`, `getselection`, `getnotice` | 25 | Yes |
| R3 yed node-local state | `yed_setquote` (miner quote), `yed_addattestation` (attestation pool, RPC-auth) | 2 | Yes |
| R4 stock RPC deltas | `sendrawtransaction` `allowyedburn` (H7), `validateaddress` P2PQPKH, `getblockchaininfo.testnetprofile`, `consensus.nextblock` (stock), `getblocktemplate` (N3/N4) | 5 | Yes |
| R5 vault act/wallet | `set_create/join/heartbeat/leave/buildact/signact/sendact/equivocation/signunlock/signcancel/listsigned/importsigned/acknowledgerestore`, `vault_lock/getnewowner/buildunlock/buildcancel/refee/send/release/ownerspend/app` | 22 | No |
| R6 yed wallet | `yed_getnewaddress`, `validateaddress`, `getbalance`, `listunspent`, `mint`, `send`, `sendmany`, `redeem`, `estimateredeem`, `claim`, `claimnotice`, `sweepcarriers`, `registerattestor`, `withdrawbond`, `revive`, `reportequivocation`, `signattestation`, `listpositions`, `listtransactions`, `listaddresses`, `lockcoins`, `unlockcoin`, `estimatesend`, `buildcancel`, `signcancelcosign` | 25 | No |
| R7 wallet PQ | `getnewaddress "" "pq"`, `z_importpqkey`, dump/import `vaultsetsig=` lines | 3+ | No |
| R8 CLI arity | `src/rpc/common.h` 82-row table (generated by `qa/yellowback-rpc-cvt.py`) | — | Re-express if kogany ships a CLI |
| R9 contracts | `doc/yellowback-rpc-contract.json`, `doc/vault-rpc-contract.json` (+ `qa/vault-rpc-contract.py`) | — | Yes for R1–R4: the contract is the conformance test |

`yed_validateaddress` (R6) is wallet-context in the node; clients decode addresses locally. `yed_gettxinfo`
reads the wallet only for optional fields; treat it as node-context with those fields omitted (uncertain:
check the handler before the plan fixes it).

### 2.8 Wallet-side (does not port to a wallet-less node)

| Component | Where | Lines |
|---|---|---|
| PQ keygen/sign (hedged SLH-DSA, randomized Falcon), HKDF-from-seed derivation | `src/crypto/pq/sign.*`, sign C sources, `src/wallet/wallet.cpp` (+573) | ~10k |
| Keystore/crypter/walletdb for PQ keys; `pqissued`, `vault*` rows; sign-once records (`set-sign-restored`, 07/F-5) | `src/keystore.*`, `src/wallet/{crypter,walletdb,rpcdump}.*` | ~800 |
| Signing: `script/sign.cpp` (+138), `ismine`, `transaction_builder` | `src/script/sign.*`, `ismine.cpp`, `transaction_builder.*` | ~230 |
| YED transaction builders, coin selection, carriers (`carriers.dat`), attestation equivocation guard (`attest-signed.dat`) | `src/yellowback/txbuilder.*` (2,769), `coinselect.*` (387), `wallet.*` (1,031; `wallet.cpp:246-247`) | 4,187 |
| `ycashd-wallet-tool` delta | `src/rust/bin/wallet_tool.rs` | 12 |

### 2.9 Tests and golden vectors

| Tier | What | Wallet-less kogany |
|---|---|---|
| Golden vectors (the oracle) | `src/test/data/`: `vault_vectors.json` (1,322), `pq_vectors.json`, `pq_wallet_vectors.json`, `pq_acvp_slhdsa.json`, `pq_falcon_kat.json`, `yellowback_golden.json` (3,812; 440 heights), `yellowback_math_cases.json`, `yellowback_attest_vectors.json`, `yellowback_pq_vectors.json` (3,612); generators `src/test/gen_*.py`, `qa/rpc-tests/test_framework/gen_*_vectors.py` | Yes, all consensus ones; `pq_wallet_vectors` only if kogany ever signs |
| Independent model | `qa/rpc-tests/test_framework/yellowback_model.py` (3,952) + `SERIALISATION.md` + `vault.py` (2,083) + `vault_module_hook.py` | Yes — the second implementation kogany is checked against |
| C++ unit tests | 37 files, ~33k lines (`yellowback_state_tests.cpp` 5,712, `vault_state_tests.cpp` 2,442, …) | Re-express as Rust tests driven by the vectors; the C++ files are the case list |
| Fuzz | 3 harness headers + 9 corpora (`src/fuzzing/{Vault,VaultState,PQScript,Yellowback*}`, 4,993 files) | Re-express (cargo-fuzz); corpora reusable as seed inputs where the input grammar is the byte stream |
| Functional | `qa/rpc-tests/`: 22 `vault_*.py`, ~45 `yellowback_*.py`, `wallet_pq_address.py`, `ycash_bootstrap.py`, `testnet_ceremony.py` | Partly: those using only R1–R4 + stock RPCs; most drive the node wallet (open question 2) |
| Devnet | `contrib/yellowback/devnet/` (7.6k), role personas, `yellowback_devnet_roles.py` | Mixed node: kogany as a relay/miner beside ycash6 wallet nodes |

### 2.10 Release, tooling, docs

| Component | Where | Wallet-less kogany |
|---|---|---|
| Cross-line manifest + checkers | `qa/yellowback-cross-line.manifest`, `qa/yellowback-cross-line{,-trees}.py`, `qa/yellowback-rc-crossline.py` | Re-express (§6) |
| Release guard parsing C++ constructor bodies (Vault heights, R7) | `qa/yellowback-vault-params.py`, `qa/yellowback-release-heights.sh` | Re-express for Rust parameters |
| Release procedure / workflows | `doc/yellowback-release.md`, `.github/workflows/yellowback-release.yml`, `rc-qualify.yml`, `yellowback-tests.yml` (2.1k) | Re-express (lane E) |
| Spec generation | `make spec-upgrade` → `doc/yellowback-spec.md` + contract copies via `scripts/extract-spec.sh` (`EXTRACT_SPEC_NODE_DIR`, `_NODE6_DIR`) | Add a `_NODE_K` target |
| Release train | `scripts/release-train.py` `COMPONENTS` (`:55-67`), `releases/v*.yaml` | Add kogany as a component |
| Calibration | yb-calibration emits a `params.cpp` patch (`yb-calibration/README.md:10`) | Needs a Rust target (trap T7) |
| Attestor agent, price/quote tools | `contrib/yellowback/attest/` (Rust, 19.4k), `yellowback_price.py`, `yellowback-quote`, `pool/` | Runs beside a node; see §4 |
| Security CI | `contrib/semgrep`, `contrib/secops`, CodeQL, zizmor | Re-express per lane E |
| Bootstrap, docker, testnet ceremony | `contrib/bootstrap`, `contrib/docker/ycashd`, `contrib/testnet/ceremony` | Later wave, if kogany is shipped |

## 3. What does not apply to a wallet-less Rust node

1. **All 47 wallet-context RPCs** (R5, R6) and the PQ wallet RPCs (R7), with everything under §2.8.
2. **Node-held signing guards**: the attestation equivocation guard (`attest-signed.dat`, S16) and the
   set members' sign-once record (07/F-5) are wallet features of the node. They protect against a
   signer equivocating; a wallet-less node signs nothing, so it carries no such record — but the
   agents that rely on them (attestor `attest` mode, Hawkeye) **must keep a ycashd** as their signer.
3. **C++-only artefacts**: `rpc/common.h`/`rpc/client.cpp` arity tables (unless kogany ships a
   compatible CLI), `experimental_features`, lock-order checker, the miner's Sapling-anchor fix,
   `Makefile.am`/depends, the zmq send lock (`src/zmq/zmqpublishnotifier.cpp`; Zakura has no ZMQ
   publisher — no `zmq` dependency in `ref/zakura/crates/*/Cargo.toml`), libFuzzer harnesses.
4. **Byte identity of source files**: the manifest's `identical`/`tree` rule binds C++ files; it
   cannot bind a Rust tree (§6).
5. **The wallet's halves of mixed RPCs**: `wallet`/`mine` fields of `vault_list`, `set_getinfo`'s
   `memberlist[].wallet`, `vault_decodescript`'s ismine.

What **does** still apply although it looks wallet-ish: TX_PQPKH as a standard output type and
destination (relay and `validateaddress`), the YED/PQ address *encodings* (RPC output), `yed_buildbundle`
(builds an unsigned bundle from the attestation pool), and `yed_setquote` (miner state).

## 4. Which clients depend on what

| Client | What it calls / consumes | Can it run against wallet-less kogany? |
|---|---|---|
| lightwalletd-dd | allow-lists `YedMethods` (19 yed read), `VaultMethods` (4), `StockMethods` (`getblockchaininfo`); probes `yed_getinfo` (−32601 = no Yellowback), requires `rpcversion` 8 exactly (`common/yellowback.go:47-90`); plus lightwalletd's stock RPCs (`getblock`, `getrawtransaction`, `getaddress*` under `-lightwalletd`/`-insightexplorer`) | **Yes**, if R1–R2 and the stock lightwalletd RPCs match the contract (Zakura already serves lightwalletd: `ref/zakura/crates/zakura-rpc/src/methods.rs:4-7`) |
| YEW | through lightwalletd only; replays `vault_vectors.json`, `pq_vectors.json`, `pq_wallet_vectors.json` (`yew/scripts/check-node-vectors.sh`); devnet tests use a node's `yed_send`/`yed_getnewaddress` | Yes via lightwalletd; YEW's vector pin script must learn a third line or keep pinning the C++ lines |
| YecWallet (yecwallet-dd) | bundles ycashd; about 40 (mostly wallet-context) `yed_*`/`set_*`/`vault_*` calls | **No** — it needs the node wallet |
| chain-viz | read-only `yed_*` and `set_*/vault_*` panels, stock reads, ZMQ (`chain-viz/src/collector.rs:178`) | Yes for RPC; ZMQ has no Zakura equivalent (polling fallback or a notify hook — lane A) |
| x402-ycash | verifier: `yed_getinfo/getprice/listtokens/validaterawtransaction/decodepayload` + stock; optional `rpcWalletSigner` (`packages/ycash/src/exact/client/rpcWalletSigner.ts`) and devnet funder use wallet RPCs | Verifier yes; node-wallet signer no |
| hawkeye | 27 `set_*`/`vault_*` incl. all act/sign RPCs, `yed_getinfo` | **No** — its keys live in the node wallet |
| attestor agent (`contrib/yellowback/attest`) | `subscribe` mode: `yed_listattestors`, `yed_addattestation`, `yed_getinfo` (node-context); `attest` mode: `yed_signattestation`, `set_heartbeat`, `yed_signcancelcosign`, `yed_buildcancel`, `set_signcancel`, `vault_send`, `vault_refee` (wallet) | `subscribe` yes; `attest` no |
| yolo | stock `getblocktemplate`/`submitblock`/`validateaddress`/`getblockchaininfo`; relies on the node's `coinbasetxn` carrying the tag (mapping §22 row "Pool software") | Yes, if kogany's template carries N1–N4 and `coinbasetxn` |
| ycash-infra | deploys ycashd + lightwalletd; reads `yed_getinfo/getprice/getstats/listattestors/estimatecollateral`, statehashes | Yes as a backend swap, after lightwalletd is green on kogany |

The contracts (`doc/yellowback-rpc-contract.json`, `doc/vault-rpc-contract.json`) are the interface;
lightwalletd-dd's offline test asserts its allow-lists against them, so kogany passing the contract
for R1–R4 is the gate for every read-only client.

## 5. Dependency order (what must land before what)

| Layer | Content (rows above) | Needs | Verification gate (oracle) |
|---|---|---|---|
| L0 | Ycash network on Zakura (lane B): Equihash 192,7, Ycash upgrade, params, addresses | — | sync mainnet; ycash6 regtest parity |
| L1 | Upgrade plumbing C1–C7 | L0 | branch-id/walk-back unit cases from `vault_script_tests.cpp`; v5-under-Vault refusal |
| L2 | Script: S1, S2, S4–S6, and S3 against a mock checker | L1 | `pq_vectors`, `pq_acvp_slhdsa`, `pq_falcon_kat`, `pq_script_tests` cases, `vault_vectors` script cases |
| L3 | Primitive P1–P6 (templates, acts, set state, storage, module table with an inert YED, hooks); S3 wired to the real snapshot | L2 | `vault_vectors.json`; `vault_getinfo.statehash` equal to ycash6 at every height of a scripted regtest |
| L4 | YED module Y1–Y8 (math first, then payload/script/tag/attest, then state/index) | L3 | `yellowback_math_cases`, `yellowback_attest_vectors`, `yellowback_pq_vectors`, `yellowback_golden` (440 heights), `yed_getstatehash` = ycash6 and = `yellowback_model.py` |
| L5 | Policy/mempool M1–M8 | L3 (M1–M3), L4 (M4, M6, M8) | `vault_policy_tests` cases; mempool parity on a mixed regtest |
| L6 | Mining N1–N4 | L4, L5 | template parity with ycash6; yolo `yellowback_stratum` across activation |
| L7 | Read RPCs R1–R4 + contract R9 | L4 (R2), L3 (R1) | `qa/vault-rpc-contract.py`, `yellowback_rpc_contract.py` read subset; lightwalletd-dd suite |
| L8 | Tooling: spec copy, release guard, release train, calibration target, CI | L1 (heights), L4 (params) | `make spec-check`, `release-train-check` with kogany |
| — | Wallet (§2.8, R5–R7) | — | out of scope unless open question 1 decides otherwise |

Within L4 the order matters: `math.h` → `params` → `payload/script/address/tag` → `attest/bundle` →
`view/state` → `index` (consensus state + undo) → `module` registration. The module must not be
registered until `yellowback_golden` passes; until then the primitive treats the `YED\0` tag as inert,
which is safe only on regtest (a live network with an attestor set would diverge).

## 6. The cross-line invariant

Today: both C++ lines must produce byte-identical results; `qa/yellowback-cross-line.manifest`
enforces it by file identity (9 vector files `identical`, `src/vault` and `src/yellowback` as `tree`
with 11 pinned `shim` files — `checker.cpp`, `db.cpp`, `node.{h,cpp}`, `index.{h,cpp}`, `params.h`,
`policy.cpp`, `txbuilder.{h,cpp}`, `wallet.cpp`). The shims are exactly where the C++ APIs differ, and
are also where kogany's Rust will differ most.

For kogany the invariant has to change shape — **the golden vectors are the oracle**:

1. Every consensus vector file in §2.9 is consumed **unmodified** (a kogany copy pinned by hash to the
   C++ file, as YEW does with `core/tests/vectors/PIN`), and kogany reproduces every field.
2. At every height of a shared regtest script, `vault_getinfo.statehash` and `yed_getstatehash` are
   equal on ycash6 and kogany (and to `yellowback_model.py`'s `state_hash()`).
3. Block and mempool verdicts (`yed_getblockverdict`, reject reasons, `bad-*` strings) agree.
4. A vector change is one commit on each C++ line *and* a PIN bump on kogany; kogany never
   generates vectors.

## 7. Traps (rule-4 rows)

| # | Ycash does X in Y via M | Zakura's equivalent Z lacks M | Adaptation W | Rung, and why not lower |
|---|---|---|---|---|
| T1 | Diagnoses an old-branch spend under Vault by walking back to the last *activated* upgrade (`upgrades.cpp:151-158`), via an upgrade list where NU5..NU6.2 sit between Canopy and Vault with no height | Zakura's `NetworkUpgrade` sequence (lane A/D) assumes predecessor = previous variant | per-network "previous active upgrade" lookup, or Vault placed directly after Canopy for Ycash (lane D decides) | parameter/upgrade-table rung; nothing lower exists — it is the branch-id table itself |
| T2 | Pins Vault to v4 + ZIP-243 (`main.cpp:1217`; librustzcash6 `has_orchard() = false`) via C++ version-group checks | Zakura validates v5/ZIP-244 as the current format and gates Orchard by NU5 | a Vault-aware tx-version rule in kogany's consensus checks; v5 refused while Vault is the epoch | transaction-format rule; a policy-only refusal would let a miner mine a v5 vault spend |
| T3 | Evaluates `OP_CHECKSETSIG` with chain state inside the interpreter via `BaseSignatureChecker` subclassing (`vault/checker.h:25`) | `zakura-zcash-script` 0.0.1 (`ref/zakura/Cargo.toml:159`) — whether it is a Rust interpreter or the C++ `zcash_script` behind FFI, and whether its checker trait can carry a snapshot, is lane A's finding | fork the script crate with a checker callback carrying an `Arc<SetSnapshot>`, or a pre-pass that resolves set signatures before script evaluation (changes evaluation order — avoid) | opcode rung (already decided upstream); the fork of the script crate is the cost |
| T4 | Verifies SLH-DSA/Falcon with vendored C (`crypto/pq/`, local patches P1–P3) | no PQ code in Zakura | link the same vendored verify C (YEW precedent: `yew/core/pq-c/README.md`, SHA256SUMS-pinned) or a Rust crate (YEW uses `slh-dsa =0.1.0` for SLH-DSA) — verification must accept/reject exactly the same byte strings, including malformed encodings | primitive-crypto choice; prefer the vendored C for Falcon (same bytes, integer-emulated FP) and test any Rust crate against `pq_acvp_slhdsa`/`pq_falcon_kat` + malformed cases |
| T5 | Defines `statehash` over its LevelDB key/value serialisation (`vault/node.cpp:505`, `yellowback/view.h:933`, `SERIALISATION.md`) | Zakura's state crate uses RocksDB column families with its own encodings | implement the canonical preimage encoder separately from storage; storage free, hash exact | state rung; changing the hash definition would break both C++ lines and the model |
| T6 | Writes the miner's price tag into the coinbase scriptSig via the global `COINBASE_FLAGS` (`miner.cpp`, `policy.h:42-45`); the tag feeds fee-payee eligibility | Zakura's block template builds the coinbase in Rust and has no flags hook | a kogany template hook reading the node-local quote (`yed_setquote`) | mining-policy rung; not consensus for the miner itself, but a kogany-mined block without tags changes later payee sets |
| T7 | Bakes calibrated constants into `src/yellowback/params.cpp`; yb-calibration emits a `params.cpp` patch; `qa/yellowback-vault-params.py` parses C++ constructor bodies | Rust constants, no C++ parser | generate kogany's constants from the same source as the C++ (or check them against the C++ by a script), never hand-copied | tooling; a hand copy is a third place for a constant to drift |
| T8 | Treats the YED index as consensus and aborts the node when it cannot evaluate (`AbortNode`, mapping §22 "Unhealthy index") | Zebra-lineage nodes keep secondary indexes outside block verification | the YED state must be inside kogany's verified-state path (committed atomically with the block), not an indexer | state rung; an asynchronous indexer would accept blocks the module rejects |

## Open questions for the owner

1. **Wallet-hosted roles.** Is kogany wallet-less for good (attestors, Hawkeye, set members and
   YecWallet stay on ycashd), or does the plan include a signer — an external-signer interface (PSBT-like
   build/sign/send split) or a sidecar wallet? The node-side guards (S16 `attest-signed.dat`, 07/F-5
   sign-once) would then have to move to the signer. Recommendation: wallet-less first; record that
   attestor and bridge-member roles require ycashd.
2. **Functional test reuse.** Most `qa/rpc-tests/yellowback_*.py`/`vault_*.py` drive the node wallet.
   Accept a mixed-network harness (ycash6 wallet nodes + kogany validators, comparing state hashes) as
   kogany's functional tier, rather than porting wallet RPCs to make the scripts run unchanged?
3. **Re-implement vs link.** Rewrite `src/vault` and `src/yellowback` consensus code in Rust (a third
   implementation, checked by the vectors and the Python model), or link the C++ overlay through FFI
   (one implementation, but C++ in a Rust node and the shims to re-target)? This is the largest cost
   decision in the plan.
4. **PQ verification source.** Vendored C (byte-identical to both lines) or Rust crates?
5. **Is kogany a release line** (tags, release train, calibration target, `rpcversion` 8 contract
   conformance) or a validator-only third implementation used for cross-checking until later?
6. **ZMQ.** Is chain-viz expected to work against kogany (needs a notification feed Zakura lacks)?

## Inputs the synthesis needs from other lanes

- **Lane A:** whether `zakura-zcash-script` is Rust or C++ FFI and how a checker with chain state can
  be threaded (T3); where a per-block, reorg-safe, atomically-committed state (P4, Y7) fits in
  `zakura-state`; the block-template builder's coinbase hook (T6); mempool re-verification on tip change
  (M6); peer-scoring vs DoS 0/10/100 (M5); orphan bound (M7); notification hooks (ZMQ).
- **Lane B:** which option carries `BranchId::Vault`/`NetworkUpgrade::Vault` (C5) and the Ycash address
  encodings into Zakura's crate set; whether the testnet-profile split (C3) belongs in L0.
- **Lane D:** where Vault sits in the upgrade sequence (T1), the v4-only rule's form (T2), the
  history-tree leaf version (C6), and what must change in the vault rules if Orchard is turned on later.
- **Lane E:** the cross-implementation harness for §6 items 2–3; how kogany pins and replays the vector
  files; which `qa/rpc-tests` scripts can run against a mixed network unchanged; the CI shape for L8.
