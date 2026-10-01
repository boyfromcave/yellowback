# Ycash Yellowback (YED) on ycashd 6.20.0 — Port and Integration Plan (`ycash6`)

**Revision 2, 2026-09-30. Status: Phases 0-3 complete, Phase 4 in progress — 15 of 19 functional scripts pass on 6.20.0 (see the execution status below); findings through F-24 and V-1..V-6 in §6.** Owner decisions P-1..P-8 taken 2026-09-30, every recommendation accepted. Scope: the node only — `ycash6/`
(`boyfromcave/ycash6`, branch `feature/yellowback`, cut from miodragpop's `dev-rebase-6.20.0` @
`040894344b`) and the patched `librustzcash6/`. The GUI wallet, lightwalletd, YEW, yolo and chain-viz
are **out of scope until Phase 7**, which starts only after Phase 6's demonstration passes.

**Goal.** A ycashd 6.20.0 that is a full participant in the miner-enforced Yellowback system with
the same functionality the v4.5.0 node (`ycash-dd`, plans v2 + v3) has today: the overlay index,
the `yed_*` RPC surface at rpcversion 3, the coinbase price tag and template filter, mempool
rule MP-1, the block-validity hook after activation, attestation bundles, the wallet builders —
proven on a multi-node regtest devnet. `ycash-dd` (v4.5.0) stays the proven line and is **never
modified by this plan**; it is the source the port reads from, through `make diff`.

**The prime directive still applies, harder.** The Ycash team is risk-averse and 6.20.0 is
another developer's rebase. Every rule of the v2 plan carries over: no consensus change, every
behaviour-changing line in an existing mining/validation file is an insertion guarded by
`if (g_yellowback)`, fail-open, switchable off, line budgets enforced by CI, the consensus set at
zero delta. Where 6.20.0 moved a seam, the port follows the seam rather than re-creating the old one.

**Baseline.** The pin as published does not pass its own tests on this platform; the fixed baseline
(`ycash6/doc/yellowback-baseline.md`, mapping §19) is the comparison point for every budget and
gate in this plan — owner decision P-4. Tag it before Phase 1: `git -C ycash6 tag ycash6-baseline
8808258cd` (the three baseline commits: miner anchor fix `940987c51`, harness `141df8d48`, doc).

**Execution status (2026-09-30, coordinator; authoritative over the checkboxes below).**

| Phase | State | Commits on `ycash6` `feature/yellowback` |
|---|---|---|
| 0 decisions, baseline, scaffolding | **complete** | `e98128239` (baseline fix 3, regtest Equihash guard), `1f6df70a2` (frozen set, audit script, CI, guide) |
| 1 transplant | **complete** — 31 overlay files, 2 RPC files, 12 test files, 6 fuzz targets verbatim; 10 common-tier modules compile with include renames only | `7bcd38ff1` |
| 2 API adaptation | **complete** — whole tree builds; 226 `yellowback_*` unit cases green (= ycash-dd's 226); full `test_bitcoin` green; P-2 moved to Phase 6 | `05b7892dd` |
| 3 node hooks | **complete** — `main.cpp` 11, `miner.cpp` 14, `miner.h` 4, `rpc/mining.cpp` 7, `chainparams.cpp` 4 changed lines; frozen set zero; 48 arity rows generated; by hand: tagged coinbase, activation at 137, a two-step mint, a YED send | `6d5c176a7` |
| 4 harness and functional suite | **in progress** — harness transplanted and adapted; **15 of 19 scripts pass** on 6.20.0: `attest`, `lifecycle`, `claim`, `stock_node`, `sapling`, `pricefeed`, `wallet_lifecycle`, `void_mint`, `wallet_restore`, `rpc_contract`, `quote`, `hardening`, `attest_wallet`, `mining`, `framework_smoke`. Open: `activation` + `index` (block sync stalls after restart/`invalidateblock` — agent act-sync, F-22); `enforcement` + `attest_enforcement` (the work valve does not trip — agent valve, F-23); `stockparity` (rerunning, F-24). `pyfw` stays unchecked until `index` passes. CI `audit` and `python` jobs on (`main` still prefixed). `yellowback-review.md` written early (P-6), its V-1..V-6 in §6. Agents running: devnet (Phase 5), fee (P-2), lockorder (debug build; its `index` run hung), armed (`--armed` runs), stockbase (inherited baseline) | `45edf27ea`, `05f345faa`, `50192cd1d` (round 1: opt-in mock clock, `unlock_all`, GBT keys, Sapling padding, kill-switch branch), `966d8d746` (round 2: mining, stockparity, H5 help), `5576005b0` (CI python job, script lists, portable audit greps), `bdffa67eb` (review document) |
| 5 devnet, 6 hardening and demonstration, 7 components | 5: agent devnet started; 6: the review document is written (`bdffa67eb`, numbers to be re-measured at Phase 6), P-2 (agent fee) and lockorder started; 7: not started | |

Deviations recorded so far: the stock binary is branch `ycash6-stock` (P-5 needs fix 3); `miner.h` budgeted at 10; P-3 is met by refusing non-v4 transactions at every signer (`V4TxData`) rather than gathering prevouts there, since 6.20.0's precompute ignores them for v4 and throws for v5 (verified in `script/interpreter.cpp`); H8 also guards `importwallet` (a v4.5.0 gap). Findings: §6.

**Reading order.** `AGENTS.md` → `docs/mapping.md` §19 (this port's rows), §13 (the v2 hooks),
§14 (v3) → this plan §1–§3 → the chunk you own in §5 → the v2 plan §3/§4 for anything this plan
does not restate (**this plan is a delta on v2 and v3: where it is silent, they rule**).

---

## 0. Owner decisions — all eight decided 2026-09-30, each as recommended

| # | Decision | Recommendation (= the decision) | Needed by |
|---|---|---|---|
| P-1 | **Regtest upgrade epoch.** v4.5.0's Yellowback scripts and devnet activate all six upgrades at height 1 and sign under the Canopy branch id, mirroring mainnet. On 6.20.0 that flips regtest Equihash to (192,7) because `GetEquihashOverride()` no longer exempts regtest (mapping §19 row 1): minutes per block. Options: (a) restore v4.5.0's four-line regtest guard in `CChainParams::EquihashN/K` (`chainparams.cpp`, a file in the v2 zero set, test-only behaviour, no mainnet effect); (b) run every Yellowback test and the devnet at Overwinter+Sapling only (signing branch id Sapling, not the mainnet epoch; founders'/funding-stream rules at Canopy untested). | **(a)**, as baseline fix 3, with `chainparams.cpp` budgeted at exactly those 4 lines and a mapping row. The port must be proven under the epoch mainnet is actually at (Canopy, 1100006). | Phase 0 |
| P-2 | **Fee rule under ZIP-317.** 6.20.0's mempool admits a flat 1000-zat Yellowback fee but ranks it below conventional-fee transactions and `-blockunpaidactionlimit`/`-mempooltxcostlimit` evict it first. | `g_yellowbackFee = max(DEFAULT_YELLOWBACK_FEE, tx.GetConventionalFee())` computed from the built transaction; the Python fee assertions follow. No change to the protocol's enforcement fee (FEE_MIN 0.5 YEC). | Phase 2 |
| P-3 | **Transaction version.** `CreateNewContextualCMutableTransaction` gained `requireV4`. | `true`: the overlay is v4-only (mapping §5, TX-0). Still collect `allPrevOutputs` fully for every `PrecomputedTransactionData` so the day NU5 ever activates nothing is silently wrong. | Phase 2 |
| P-4 | **What the gates measure against.** No `feature/yellowback-sf` exists for ycash6; the raw pin cannot mine reliably. | Tag `ycash6-baseline` (= fixed baseline) and measure every budget and the frozen-file zero-delta against it. The baseline commits are listed in the review document as "not Yellowback". | Phase 0 |
| P-5 | **Stock-parity reference binary** (`yellowback_stockparity.py`, `yellowback_stock_node.py --stock-binary`). | Build `ycash6-baseline` once into `wt/ycash6-baseline/src/ycashd`; that is the stock binary. Not `ref/ycash6` (it has the anchor bug). | Phase 4 |
| P-6 | **Review package.** `doc/yellowback-review.md` cites 29 v4.5.0 line numbers and reviews that port. | Keep it as the v4.5.0 record; write `ycash6/doc/yellowback-review.md` fresh for 6.20.0 in Phase 6 with actuals measured on this tree. | Phase 6 |
| P-7 | **`yellowback_reorg_stress.py`** is still the v1 federation script (dead at its first `yed_getinfo` field). | Retire it here; the reorg coverage lives in `yellowback_index.py` and `yellowback_lifecycle.py`; a v2-shaped stress script is a Phase 6 item if time allows. | Phase 4 |
| P-8 | **Harness inheritance.** 6.20.0's `start_node` appends `-i-am-aware-zcashd-…` (the node ignores it) and `-rest`; `util.py` carries upstream Zcash branch ids. | Leave the inherited harness alone beyond the two baseline fixes; `yellowback_util.py` keeps its own Ycash branch-id table as today. | Phase 4 |

---

## 1. What the surveys found (2026-09-30; full tables in mapping §19)

**The good news.** 6.20.0 is not a Bitcoin-Core-style rewrite. Validation is still monolithic
`main.cpp` (`AcceptToMemoryPool :1771`, `DisconnectBlock :2959`, `ConnectBlock :3226`, `ConnectTip
:4485`, `AcceptBlockHeader :5944`); the coins model is still per-tx `CCoins`; args are still
`mapArgs`/`GetArg`; logging is still string categories; `pwalletMain`, `CRPCCommand` +
`tableRPC.appendCommand`, `rpc/register.h`, `std::variant` destinations, `CDBWrapper`, `KeyIO`,
`ADD_SERIALIZE_METHODS`, Boost.Test fixtures and the AFL `src/fuzzing/<Target>/` layout are all
unchanged. Of ~40 node headers the overlay includes, five moved (`util.h` → `util/system.h` +
`logging.h`, `utilstrencodings.h`, `utiltime.h`, `utilmoneystr.h`, `utiltest.h` → `util/…`).
**≈5.5k of the overlay's ≈10.6k lines (`address`, `attest`, `bundle`, `coinselect`, `db`, `math.h`,
`params`, `payload`, `script`, `state`, `tag`, `view`, all six fuzz targets) port with include
renames only.** Of the 20 pre-existing node files v4.5.0 modified, 14 hunks drop in verbatim, 6
are already upstream (drop them), and 4 seams moved.

**The seams that moved** (each gets a §5 chunk and a mapping row):

| # | v4.5.0 | 6.20.0 | Port |
|---|---|---|---|
| S1 | `rpc/client.cpp` `vRPCConvertParams[]` — client-side "convert param n" | `rpc/common.h` `rpcCvtTable` `{required…},{optional…}` consulted by **client and server**; `server.cpp:488-500` rejects any call whose arity is not listed | Every one of the ~45 `yed_*` RPCs needs a row with exact arity (including ones that needed no conversion before), plus `sendrawtransaction` → `{{s},{o,o}}` for H7 |
| S2 | `miner.cpp` `CreateNewBlock` free function; TPL-1 filter before `UpdateCoins` in the priority loop (`:582`) | `BlockAssembler::CreateNewBlock` (`:329`); selection is ZIP-317 weighted-random in `addTransactions`/`TestForBlock` (`:493-690`); `ConnectBlock(fJustCheck, CheckAs::BlockTemplate)` runs on every template (`:473`, `main.cpp:6251`) | `TemplateView` becomes a `BlockAssembler` member; the filter is a `return false` in `TestForBlock` after the expiry check (`:536`); `CheckConnect` must be side-effect-free under `CheckAs::BlockTemplate` and agree with `FilterTemplate`; `IncrementExtraNonce` is 4-arg (`:764`) |
| S3 | `sync.cpp` `DEBUG_LOCKORDER_LOGONLY` build flag | upstream `g_debug_lockorder_abort` (`sync.cpp:203`, `sync.h:66`); the detector now throws `std::logic_error` after logging | The lockorder CI job sets the global instead of the flag and expects the throw |
| S4 | `transaction_builder` patch: unsigned transparent input with an empty script | `PrecomputedTransactionData(tx, allPrevOutputs)` is built from `tIns` (`transaction_builder.cpp:617`), field `value` → `nValue`; the builder is move-only with `(orchardAnchor, saplingAnchor)` in the ctor (`.h:271-283`) | The unsigned input carries its real `scriptPubKey`/`nValue`; `NewBuilder` emplaces into `std::optional` and the Sapling anchor is fetched **before** construction |

**The three API changes that cost real lines** (all in `txbuilder.cpp`, `policy.cpp`, two tests):

1. ZIP-244: `SignatureHash(…, branchId, txdata)` with `txdata` mandatory; `TransactionSignatureChecker(&tx, txdata, nIn, amount)` (arg order flipped); `SignSignature(keystore, fromPubKey, mtx, txdata, nIn, amount, hashType, branchId)`. Sites: `txbuilder.cpp:146,155,188,203,477,1267`, `policy.cpp:153-163`, `yellowback_script_tests.cpp` ≈25 sites, `yellowback_txbuilder_tests.cpp` ≈5.
2. The Sapling builder: move-only, anchors in the ctor, `AddSaplingSpend(extsk, note, witness)`, `AddSaplingOutput(ovk, addr, value, std::optional<Memo>)`, `SendChangeTo(RecipientAddress, ovk)`. Sites: `txbuilder.cpp:333-470` (`NewBuilder`, `FreshKey`, `SelectSapling`), the four Sapling-funded shapes (`:640-665, 1040-1060, 1140-1160, 1440-1455`), `FinishSapling` (`:1665-1680`).
3. Wallet: `Have/GetSpendingKeyForPaymentAddress` visitors → `HaveSaplingSpendingKeyForAddress` + `GetSaplingExtendedSpendingKey`; `GetFilteredNotes(sprout, sapling, orchard, NoteFilter, asOfHeight, …)`; `GetSaplingNoteWitnesses(notes, confirmations, witnesses, anchor)` returns bool; `GetKeyFromPool` → `GenerateNewKey(bool external)`; `GetDepthInMainChain(asOfHeight)`, `IsSpent(hash, n, asOfHeight)`, `AvailableCoins(coins, asOfHeight, …)` (positional second — must fail to compile, not shift); `CommitTransaction(wtx, reservekey, CValidationState&)`; `ChainTip(pindex, pblock, std::optional<MerkleFrontiers>)`; `CreateNewContextualCMutableTransaction(consensus, height, requireV4)`; `PaymentAddress` variant widened (reject `UnifiedAddress`/`CKeyID`/`CScriptID` explicitly).

**6.20.0 features that interact** (recorded, each with a test in §5): ZIP-317 fee ranking and
`-txunpaidactionlimit`/`-blockunpaidactionlimit` (P-2); `-mempooltxcostlimit` eviction versus
`RemoveInvalidVaultSpends`; `IsExpiringSoonTx` (the builder must set a sane `nExpiryHeight`);
`BodyCorruption::HeaderOnly` on the BLK-2 header rejection; clang thread-safety annotations on
`sync.h` (warnings on overlay functions that lack `EXCLUSIVE_LOCKS_REQUIRED`); `TestChain100Setup`
under `#ifdef ENABLE_MINING`; `getblocktemplate` `finalsaplingroothash` is deprecated-but-default-
allowed (`gbt_oldhashes`), `defaultroots.chainhistoryroot` is the replacement; `mininode.CBlock.
hashFinalSaplingRoot` → `hashBlockCommitments`; `-walletrequirebackup`, `-allowdeprecated`,
`-feepolicy`, `-preferredtxversion` exist and v4.5.0's did not.

---

## 2. Diff budget (measured against `ycash6-baseline`, enforced by CI from Phase 3)

| Existing file | Budget | Expected | What |
|---|---|---|---|
| `src/main.cpp` | ≤ 40 | ≈ 12 | the same six hooks as v2 (include, MP-1 in ATMP `:1889`, undo in `DisconnectBlock :3158`, check in `ConnectBlock :4041`, commit after `SetBestBlock :4115`, sweep in `ConnectTip :4517`, BLK-2 in `AcceptBlockHeader :5966`) |
| `src/miner.cpp` | ≤ 35 | ≈ 16 | tag + `TemplateView` member in `CreateNewBlock :350`, filter in `TestForBlock :536`, scriptSig `+ COINBASE_FLAGS` at `:288`, `LOCK(cs_main)` around `IncrementExtraNonce :909`; the member in `miner.h` |
| `src/rpc/mining.cpp` | ≤ 35 | ≈ 7 | as v2 (`:517, :790, :819, :833`) |
| `src/chainparams.cpp` | **4** (P-1 only) | 4 | the regtest Equihash guard; otherwise zero |
| `src/miner.h` | ≤ 10 | ≈ 3 | the `TemplateView` member of `BlockAssembler` |
| `src/rpc/common.h` | ≈ 55 | ≈ 50 | S1 arity rows (new in this port; counted, not budgeted) |
| `src/init.cpp` | no budget | ≈ 165 | as v2/v3 (+ one-string debug categories edit) |
| `src/transaction_builder.{h,cpp}` | 40 | ≈ 38 | the I2 extension re-patched onto the 6.x builder (S4) |
| `src/rpc/rawtransaction.cpp`, `src/wallet/rpcwallet.cpp`, `src/wallet/rpcdump.cpp` | ≈ 70 | ≈ 65 | H5/H7/H8 as v2 (rpcdump: 3 sites + up to 4 new import RPCs) |
| `src/experimental_features.{h,cpp}`, `src/rpc/register.h`, `src/Makefile.am`, `src/Makefile.test.include`, `qa/pull-tester/rpc-tests.py`, `test_framework/{util,script}.py` | build/test | ≈ 90 | as v2 |
| `src/sync.cpp`, `src/wallet/asyncrpcoperation_sendmany.cpp`, `src/test/{main,net}_tests.cpp`, `src/wallet/test/rpc_wallet_tests.cpp` | **0** | 0 | v4.5.0 hunks already upstream — dropped |
| `src/consensus/*`, `src/script/*`, `src/primitives/*`, `src/pow/*`, `src/policy/*`, `src/wallet/wallet.{h,cpp}`, `src/txdb.*`, `configure.ac`, `src/rust/*`, `Cargo.*`, `librustzcash6/*` | **0** | 0 | the frozen set (`qa/yellowback-frozen-files.txt`, re-baselined) |

Everything else is new under `src/yellowback/`, `src/rpc/yellowback*.cpp`, `src/test/yellowback_*`,
`src/fuzzing/Yellowback*/`, `qa/rpc-tests/yellowback_*.py`, `test_framework/yellowback*.py`,
`contrib/yellowback/`, `doc/yellowback*.md`, `.github/workflows/yellowback-tests.yml`. The Rust side
(`src/rust/`, `librustzcash6`) is expected at **zero**: the overlay has no Rust and the surveys
found no reason for any; if a chunk ever needs it, that is an owner decision first.

---

## 3. Working rules for this port

- Work in `ycash6/` only, on `feature/yellowback`, from `wt/<chunk>` worktrees for parallel agents
  (memory: `ycash-dd-worktrees`; the shared depends triple and cargo target are symlinked). Never
  touch `ycash-dd`, `ref/`, or `librustzcash6` (zero delta expected).
- **Copy, then adapt, never redesign.** Each chunk starts by copying the v4.5.0 file verbatim
  (`git -C ycash-dd show feature/yellowback-price-attest:<path>`), then applies the minimum edits §1
  names. A diff of a ported file against its v4.5.0 original must read as "include renames + the
  listed API edits". Any further change is a finding, recorded in mapping §19 before it is made.
- The four-part check (AGENTS.md rule 4) is written in every commit that touches a pre-existing
  file: *6.20.0 moved X; the v4.5.0 hook sat at Y; the seam is now Z; so the adaptation is W.*
- `# Rule:` tags, rpcversion 3, the RPC contract JSON and `doc/yellowback-rpc.md` do **not** change:
  the `yed_*` surface is the interface every other component was built against, and Phase 7's
  compatibility tests assume it byte-for-byte. A contract change is an owner decision.
- Build and test invocations: memory `ycash6-build-and-baseline` (PATH, `CARGO_TARGET_DIR`,
  `ZCASHD=<repo>/src/ycashd` for functional tests, regtest at the P-1 epoch).
- Regtest realism: after P-1(a), the Yellowback scripts and the devnet keep `YCASH_UPGRADE_ARGS`
  (six upgrades at 1, signing under Canopy) exactly as v4.5.0; `yellowback_stock_node.py` and the
  stock baseline keep Overwinter+Sapling as the inherited harness does.

---

## 4. Success criteria (the Phase 6 demonstration)

A ycashd 6.20.0 devnet started by `contrib/yellowback/devnet/yellowback-devnet up` on this
machine, with pools, an observer, an attestor seat and a **stock** 6.20.0 node (`ycash6-baseline`
binary, no `-yellowback`), shows all of the following — the same checklist the v2 §6 phase
acceptances and the role-based regtest nightly prove on v4.5.0:

- [ ] every node starts from genesis with `-yellowback`, syncs the overlay index, `yed_getinfo` reports rpcversion 3 and `healthy`
- [ ] pools emit the coinbase tag with their quote; `yed_getprice` shows the rolling median; a forged tag from a non-pool is ignored
- [ ] signalling reaches ≥ 75 %, `yed_getactivation` walks PENDING → TRIGGERED → ARMED → ACTIVE at the plan's heights; the sunset and `-yellowbackenforceuntil` behave
- [ ] mint, send, redeem, claim, sweep and VOID release work from the wallet RPCs (`yed_mint … yed_claimnotice`) and from the raw builders; balances, positions and vaults agree with the Python model (`yellowback_model.py`, `full=True`)
- [ ] attestors register, bundles are built and carried; a mint with a bad bundle is refused at the template and, once enforcing, at block validity, by every enforcing node — at DoS 0, no peer banned
- [ ] the stock node mines a vault spend without the burn: enforcing nodes reject the block, the stock node is not banned, the chain continues on the enforcing side; the BLK-2 descendant clause holds
- [ ] a 2-block and a 10-block reorg leave every node's `yed_getstats` state hash equal; `-reindex` and a restart rebuild the same index
- [ ] the price walk and the six `yellowback-sim` personas run the economy for 30 minutes (the `yellowback_devnet_roles.py` nightly on all three presets) without a halt the model did not predict
- [ ] a `ycash6-baseline` stock node and a `feature/yellowback` node without `-yellowback` are byte-identical over 300 blocks (`yellowback_stockparity.py`)
- [ ] all `yellowback_*.py` scripts pass unarmed and `--armed`; the full `test_bitcoin` is green; the frozen set is at zero and every budget in §2 holds; the lockorder, sanitizer and coverage jobs are green

---

## 5. Phases and chunks

Checkboxes are flipped only when the chunk is merged on `feature/yellowback` and its gate has
been seen to run. Chunk names are the worktree names. Estimates are agent-days.

### Phase 0 — decisions, baseline, scaffolding (owner + coordinator, ½ day)

- [x] P-1 … P-8 answered in §0 (2026-09-30: all as recommended)
- [x] `ycash6-baseline` tag pushed (`8808258cd`). **Deviation:** the P-5 stock binary is built from branch `ycash6-stock` (`e98128239`, all three baseline fixes) in `wt/ycash6-stock`, because a stock node without fix 3 would reject the devnet's (48,5) blocks at the Canopy epoch
- [x] P-1(a): the regtest Equihash guard as baseline-fix commit 3 (`e98128239`; full `test_bitcoin` green; 110 blocks in < 1 s at Canopy, shield/Sapling/deshield/transparent all mined) in `chainparams.cpp` (4 lines) + mapping §19 row; regtest with six upgrades at 1 mines in ~0 s (re-run the §4 smoke of `yellowback-baseline.md` at the Canopy epoch: shield, Sapling send, deshield)
- [x] `qa/yellowback-frozen-files.txt` written for this baseline (the four budgeted files left out, `src/rust/`, `Cargo.*` added; `miner.h` budgeted at 10) and `qa/yellowback-audit.sh` added as the local mirror of the CI audit gates; with `src/rust/`, `Cargo.toml`, `Cargo.lock`; `qa/yellowback-coverage-floor.sh`, `qa/yellowback-lockorder-check.py` copied (the lockorder whitelist re-verified against 6.20.0 `miner.cpp` in Phase 3)
- [x] `.github/workflows/yellowback-tests.yml` copied (`1f6df70a2`) with branch names → `ycash6-legacy`/`ycash6-baseline`, `BITCOIND` → `ZCASHD`, the depends apt list for 6.x, budgets from §2 via `qa/yellowback-audit.sh`; every job except `audit` is **skipped** (`if: false && …`) until its phase removes the prefix
- [x] `docs/mapping.md` §19 gains the seam table (S1–S4) and the API-change rows from §1 with both pins' citations (the survey text is the source)
- [x] `ycash6/doc/yellowback.md` copied; its "Build and test baseline" section rewritten from `yellowback-baseline.md`

### Phase 1 — transplant the pure overlay (1 day, chunk `transplant`)

Copy, rename includes, build. No node hook, no API adaptation beyond includes.

- [x] `src/yellowback/` (31 files), `src/rpc/yellowback{,wallet}.cpp`, `src/rpc/yellowbackrpc.h`, `src/test/yellowback_*` (12 + harness + corpus generator + JSON vectors), `src/fuzzing/Yellowback*/` copied verbatim from `ycash-dd` `feature/yellowback-price-attest`
- [x] include renames (`util.h` → `util/system.h` + `logging.h`; `utilstrencodings`, `utiltime`, `utilmoneystr`, `utiltest` → `util/…`) — one sed commit
- [x] `src/Makefile.am` (5 hunks at `:301, :308, :371, :433, :577`) and `src/Makefile.test.include` (`:45`, `:119`) wired; `TestChain100Setup` users under `#ifdef ENABLE_MINING`
- [x] `experimental_features.{h,cpp}` (`-yellowback` flag), `rpc/register.h` (two lines) — so the RPC files link
- [x] **Gate:** `libbitcoin_common`, `libbitcoin_server`, `libbitcoin_wallet` compile with the stable files (`address`, `attest`, `bundle`, `coinselect`, `db`, `params`, `payload`, `script`, `state`, `tag`, `view`, `math.h`) and their unit tests green: `test_bitcoin --run_test='yellowback_{payload,tag,state,script,attest,bundle,params,view}_tests'`; the files needing API work (`index`, `policy`, `wallet`, `txbuilder`, the two RPC files, `yellowback_script/txbuilder/index_tests`) may be stubbed out of the build with a one-line `# PORT:` comment each, listed in the commit
- [x] `git diff --stat ycash6-baseline` shows nothing outside the new paths plus the four wiring files

### Phase 2 — API adaptation (2–3 days, three chunks, parallel)

- [x] **`api-index`** (½ day): `index.h/.cpp` `ChainTip(…, std::optional<MerkleFrontiers>)` (`validationinterface.h:91`); `policy.cpp` `VerifyAllInputs` with `PrecomputedTransactionData(tx, allPrevOutputs)` and the flipped checker order (`interpreter.h:96,167`); `wallet.cpp` `IsSpent(…, std::nullopt)`, `CommitTransaction(wtx, key, state)`; `CreateNewContextualCMutableTransaction(…, /*requireV4*/ true)` (P-3); thread-safety annotations where clang warns. Gate: `yellowback_index_tests`, `yellowback_policy_tests` green; `-Wthread-safety` clean on `src/yellowback/`.
- [x] **`api-txbuilder`** (1½ days, the rewrite bucket): re-patch the I2 extension onto the 6.x builder (`transaction_builder.{h,cpp}` `:383/:404/:618`, S4: real `scriptPubKey`/`nValue` on the unsigned input); `NewBuilder` → `std::optional<TransactionBuilder>::emplace(params, height, std::nullopt, saplingAnchor, keystore)` with the anchor from `pcoinsTip->GetBestAnchor(SAPLING)` before construction; `FreshKey` → `GenerateNewKey`; `SelectSapling` on `HaveSaplingSpendingKeyForAddress` / `GetSaplingExtendedSpendingKey` / `GetFilteredNotes(…, NoteFilter::ForPaymentAddresses, std::nullopt, …)` / `GetSaplingNoteWitnesses(notes, 1, witnesses, anchor)`; `AddSaplingSpend(extsk, note, witness)`, `AddSaplingOutput(…, std::nullopt)`, `SendChangeTo(addr, ovk)`; every raw sighash signer gets its `txdata` with full prevouts; `AvailableCoins(coins, std::nullopt, …)`; `nExpiryHeight` set as the 6.x builder does (`IsExpiringSoonTx`); P-2 fee floor from `CalculateConventionalFee` in `params.h`/`index.cpp` (**moved to Phase 6**: the flat 1000 zat is admitted and mined by 6.20.0's defaults, so P-2 changes priority, not acceptance; it lands once the functional suite can catch an amount regression). Gate: `yellowback_txbuilder_tests`, `yellowback_script_tests` (≈25 sites updated) green; a unit case per Sapling-funded shape.
- [x] **`api-rpc`** (1 day): `rpc/yellowback.cpp` + `rpc/yellowbackwallet.cpp` (`GetDepthInMainChain(std::nullopt)`, `IsSpent`, `GenerateNewKey`, `PaymentAddress` variant handling — reject unified/transparent alternatives with the existing error strings); **S1:** the `rpcCvtTable` rows in `rpc/common.h` for every `yed_*` RPC with exact `{required},{optional}` arity, generated from `doc/yellowback-rpc-contract.json` by a small script kept in `qa/` so the contract stays the source; `sendrawtransaction` → `{{s},{o,o}}`. Gate: `yellowback_rpc_tests` green; a new unit case asserts every registered `yed_*` has a `rpcCvtTable` row (the server would otherwise reject it silently).
- [x] Phase-2 gate: full `test_bitcoin` green (every `yellowback_*` case from v4.5.0 present, count recorded); `src/wallet/wallet.{h,cpp}` still zero; mapping §19 rows for each API edit

### Phase 3 — node hooks (1½ days, two chunks, serial on `main.cpp`/`miner.cpp`)

- [x] **`hooks-validation`** (`main.cpp`, `init.cpp`): the six v2 hooks at the §2 anchors; `CheckConnect` audited and unit-tested as side-effect-free under `CheckAs::BlockTemplate` (it now runs on every template — S2); BLK-2 passes `BodyCorruption::HeaderOnly`; `init.cpp` Step-3 validation block at `:1237`, registration at `:1244`, index construction/`SyncToChain`/kill-switch at `:2077` (`ActivateBestChain` arity checked), shutdown at `:206`, help text at `:392`, the single debug-categories string at `:478`. Gate: `yellowback_index_tests` with `TestChain100Setup`; `main.cpp` ≤ 40 lines measured.
- [x] **`hooks-mining`** (`miner.{h,cpp}`, `rpc/mining.cpp`): `TemplateView` as a `BlockAssembler` member; `COINBASE_FLAGS = TagScript(…)` in `CreateNewBlock`; the TPL-1/2 filter in `TestForBlock :536`; scriptSig `+ COINBASE_FLAGS` at `:288` (inside the visitor, before `ComputeBindingSig`); `LOCK(cs_main)` around the 4-arg `IncrementExtraNonce :909`; `rpc/mining.cpp` `:517/:790/:819/:833`; the lockorder whitelist re-derived for the new `TemplateView`/`TestNewBlockAtTipValidity` pair. Gate: `miner_tests` + `yellowback_miner_tests` green; `miner.cpp` ≤ 35 and `rpc/mining.cpp` ≤ 35 measured.
- [x] **`hooks-wallet`** (½ day, parallel with the two above): `rpc/rawtransaction.cpp` H7 (`:1249-1304`), `wallet/rpcwallet.cpp` H5 (`:2790-2868`), `wallet/rpcdump.cpp` H8 (`:115/:246/:825`, plus `importpubkey :314`, `importwallet_impl :380`, `z_importviewingkey :937`, `z_importivk :1208` — decide per site, record), S3: `g_debug_lockorder_abort` in the CI job. Gate: `rpc_wallet_tests` green.
- [x] Phase-3 gate: `getblocktemplate` on a `-yellowback` regtest node returns `coinbaseaux.flags` with the tag and the `yellowback` object; `generate` mines tagged blocks; CI `audit` job switched on (budgets + frozen zero-delta + determinism greps + `DoS(0)` grep); a one-node smoke of `yed_getinfo`/`yed_mint`/`yed_send` by hand

### Phase 4 — the Python harness and every functional test (2 days, two chunks)

- [ ] **`pyfw`**: `test_framework/yellowback_util.py`, `yellowback_attest.py`, `yellowback_model.py`, `yellowback_golden.json`, `test_yellowback_*.py`, `SERIALISATION.md` copied; `setup_clean_chain` → `cache_behavior='clean'`; `BITCOIND` → `ZCASHD`; `mininode.hashFinalSaplingRoot` → `hashBlockCommitments`; template reads switch to `defaultroots.chainhistoryroot` (or document `gbt_oldhashes`); the two explicit `Decimal('0.0001')` fees dropped; a 1 s settle in the `mine` helper; P-2 fee assertions; `script.py` `'<q'` fix re-applied; runner `BASE_SCRIPTS`/`EXTENDED_SCRIPTS` + `--cachedir`/`--portseed` precedence; `yellowback_hardening.py`'s init-error text re-checked. Gate: `yellowback_framework_smoke.py`, `yellowback_index.py`, `yellowback_rpc_contract.py` pass.
- [ ] **`scripts`**: the remaining 22 `yellowback_*.py` copied and run one by one, unarmed and `--armed`; each failure is a mapping row before a fix; `yellowback_stock_node.py` and `yellowback_stockparity.py` against the P-5 binary; `yellowback_stratum.py`/`yellowback_chainviz.py` keep their SKIP-without-binary behaviour (Phase 7 runs them); P-7 retirement of `reorg_stress`. Gate: 24 scripts green; `yellowback_rpc_contract.py` proves the contract JSON unchanged.
- [ ] `STOCK_BASELINE` re-recorded: the inherited suite at `ycash6-baseline` (which of the four v4.5.0-excluded scripts rejoin; `make check` whole-run status) in `doc/yellowback.md`
- [ ] CI `main` and `python` jobs switched on

### Phase 5 — the devnet (1½ days, chunk `devnet`)

- [ ] `contrib/yellowback/` copied whole (quote agent, pool kit, attest crate, calibrate, packaging, devnet, sim, stratum-miner, scenarios, fixtures); `BITCOIND` → `ZCASHD`; node 0's `-insightexplorer -txindex` and ZMQ flags verified on 6.20.0; `-walletrequirebackup=false` added only if a fresh wallet refuses; the `devnet.json` schema unchanged (chain-viz, the GUI and lightwalletd read it in Phase 7)
- [ ] `up`, `up --role {user,attestor,pool}`, `wallet`, `mine`, `price`, `walk`, `check`, `down` run on 6.20.0; the heartbeat and the six personas run; `yellowback_attest_agent.py` against the Rust agent
- [ ] `yellowback_devnet_roles.py` (nightly, ~30 min) passes on all three presets
- [ ] `doc/yellowback-devnet.md`, `yellowback-mining.md` (gbt field names) updated; CI `nightly` job switched on

### Phase 6 — hardening, gates, the review package, the demonstration (2 days)

- [ ] `lockorder` (`--enable-debug`, S3), `sanitizers` (ASan/UBSan, TSan on `yellowback_index`), `coverage` (floors as v2), `weekly-fuzz` jobs green on 6.20.0
- [ ] ZIP-317 and mempool-limit interaction tests: a mint at the P-2 floor is relayed and mined under `-blockunpaidactionlimit=0`; `RemoveInvalidVaultSpends` with `-mempooltxcostlimit` eviction; `IsExpiringSoonTx` never bites a builder transaction
- [ ] `ycash6/doc/yellowback-review.md` written fresh (P-6): §2 budget actuals measured on this tree, the hook table with every site's four-part check at 6.20.0 line numbers, the unguarded residue, the baseline-fix commits listed as "not Yellowback", the §8.4 checklist re-scored; `make spec` regenerates the spec copy for the fork
- [ ] **The §4 demonstration run end to end and its transcript attached to the review document** — this is the exit criterion of the node scope
- [ ] Report to miodragpop: the three baseline fixes (miner anchor, harness conf, Equihash regtest guard) as upstreamable patches, separate from Yellowback

### Phase 7 — component compatibility (**after** Phase 6; separate chunks, own plans' acceptance tests)

Each component reaches the node only through its public interface, so each test is "point the
existing component at a 6.20.0 devnet and run its own acceptance". Expected to need **zero**
component changes if the `yed_*` contract and `devnet.json` stayed byte-identical; any difference
is a finding against this plan, not against the component.

- [ ] `yecwallet-dd` (JSON-RPC `yed_*`): `build.sh --ycashd` bundling the 6.20.0 binary; the QTest suite offline; the devnet case against `yellowback-devnet up` on ycash6; the four scenario walk-throughs
- [ ] `lightwalletd-dd` (`getaddresstxids` via `-insightexplorer -txindex`, read-only `yed_*` proxies, `getcompactblock`/`getcompactblockrange` that 6.20.0 adds — check whether the server should prefer them): its Phase R0 regtest acceptance against the 6.20.0 devnet; the byte-equality gate still against the yodl baseline
- [ ] `yolo` (`getblocktemplate`, `submitblock`, `validateaddress`, `getblockchaininfo`): `yellowback_stratum.py` with `YOLO_BIN`; the `--stratum` pool seat on the devnet; gbt field names (`defaultroots`) and `coinbasetxn` handling
- [ ] `chain-viz` (stock read RPCs, read-only `yed_*`, ZMQ): `yellowback_chainviz.py` with `CHAINVIZ_BIN`; a devnet session with reorgs; the C-F33 reorg-depth note re-checked on 6.20.0's witness cache
- [ ] `yew` (via lightwalletd gRPC only): its M1 integration test against the 6.20.0 devnet through the ported lightwalletd
- [ ] A row in this table per finding, and the component's own plan gets the fix if one is needed

---

## 6. Findings log (filled in as the port runs; mirrored to mapping §19)

| # | Phase | Finding | Disposition |
|---|---|---|---|
| F-1 | 0 | Pin defects at `040894344b`: uninitialised coinbase Sapling anchor, harness `zcash.conf`, Equihash (192,7) on regtest under the Ycash upgrade, upstream branch ids in the harness, ZIP-317 fee gate vs `wallet_sapling.py`, NU5 inactive | baseline fixes 1–3; the rest recorded (`ycash6/doc/yellowback-baseline.md`) |
| F-2 | 2 | Upstream `TransactionBuilder`'s move constructor moves `orchardSpendingKeys`, `firstOrchardSpendAddr` and `firstSaplingSpendAddr` from itself, not from the source (`transaction_builder.h:296-298`): a builder moved after `AddSaplingSpend` loses its first spend address | The overlay constructs builders in place in `BuiltTx::builder` and never moves them; report upstream |
| F-3 | 2 | `main.h:332` still declares the free `GetBlockSubsidy(int, const Consensus::Params&)`, but 6.20.0 defines only `Consensus::Params::GetBlockSubsidy` — a call links-fails | Overlay calls the method |
| F-4 | 2 | The RPC contract's `args` grammar omits the optional argument of `yed_getbalance`, `yed_listunspent` and the required one of `yed_sendmany` (a v4.5.0 documentation gap) | Arity rows are generated from the handlers' guards, not the contract |
| F-5 | 2 | 6.20.0 has no keypool draw (`GetKeyFromPool` gone); the contract's `keypool-empty` error can no longer be raised; a locked wallet now fails with `wallet-locked` | Recorded; contract text to be updated in Phase 6 if `yellowback_rpc_contract.py` requires it |
| F-6 | 3 | The surveys said `CheckConnect` running on templates was new in 6.20.0; v4.5.0 already ran its own template through `TestBlockValidity` (`ref/ycash/src/miner.cpp:660`) | No new risk; mapping row corrected |
| F-7 | 3 | v4.5.0's H8 guarded `rescanblockchain`, `importprivkey`, `importaddress`, `z_importkey` but not `importwallet`, which imports spending keys and rescans too; 6.20.0 has no `rescanblockchain` RPC (rescans run inside the guarded imports) | `importwallet` guarded on ycash6; the `rescanblockchain` hunk dropped (V-3; mapping §19) |
| F-8 | 4 | 6.20.0's `setmocktime` works only on a node started with a non-zero `-mocktime` (`rpc/misc.cpp:519`); v4.5.0 switched clocks on the first call | The framework starts every mock-clock node at one `clock_base` with `-mocktime` (`05f345faa`; opt-in since `50192cd1d`, F-14) |
| F-9 | 2 | 6.20.0's mempool adds a Ycash per-Sapling-output fee floor (1000 zat within the exempt count) beside ZIP-317; the overlay's Sapling shapes stay within it | Covered by the P-2 tests in Phase 6 |
| F-10 | 4 | Apple git's ERE has no `\b`: the audit's rule→test tag greps (`git grep -qE '…\b$id\b'`) failed every identifier on macOS while passing on Linux | `git grep -qP` (`5576005b0`); the local `qa/yellowback-audit.sh` gate now equals CI |
| F-11 | 4 | BSD grep mis-handles BRE alternation (backslash-pipe) combined with `$` (the `GetTime`-homes filter) | `grep -vE` (`5576005b0`); same meaning on GNU |
| F-12 | 4 | `rpc-tests.py <names>` silently drops a name missing from `ALL_SCRIPTS` (both pins): a run goes green with fewer tests | Audit check: every `yellowback_*.py` and every name in `YELLOWBACK_SCRIPTS`, `SANITIZER_SCRIPTS`, `STOCK_BASELINE` must be registered (`5576005b0`) |
| F-13 | 4 | 6.20.0's framework imports `hashlib.blake2b` (the v4.5.0 `pyblake2` shim is unneeded) but `mininode.py` still imports `asyncore` (removed in Python 3.12) | CI stays on Python 3.11; the workspace venv keeps the `asyncore` backport |
| F-14 | 4 | A fixed clock freezes 6.20.0's transaction relay: the tx-inventory trickle fires when `nNextInvSend < GetTimeMicros()` on the node clock (`main.cpp:9193-9197`); v4.5.0's mock time never touched `GetTimeMicros` and picked a random trickle peer per round | Mock clock opt-in (`mock_clock = True` in `quote`, `mining`, the smoke test); the framework nudges the clock while mempools converge (`50192cd1d`, `966d8d746`) |
| F-15 | 4 | 6.20.0's `lockunspent` arity row `{{o,o},{}}` (`rpc/common.h:174`) requires both arguments, so v4.5.0's one-argument unlock-all form is refused by the server | Harness `unlock_all()` unlocks each locked outpoint except the overlay's own; the H5 hardening case asserts the refusal (`50192cd1d`); help text: V-2 |
| F-16 | 4 | The stock `getblocktemplate` gains `blockcommitmentshash` (deprecated, under `gbt_oldhashes`) and `defaultroots` | Stock GBT key set updated (`50192cd1d`); stockparity compares `defaultroots` (F-21) |
| F-17 | 4 | The 6.20.0 Rust Sapling builder pads a bundle to two outputs (`sapling-crypto` `MIN_SHIELDED_OUTPUTS = 2`) | Three count assertions expect two (`50192cd1d`). Free: the per-Sapling-output floor is one flat 1000 zat up to 50 outputs |
| F-18 | 4 | The kill switch takes its `ReconsiderBlock` branch after a clean restart: 6.20.0's `RewindBlockIndex` keeps entries below `BLOCK_VALID_CONSENSUS`, so a rejected block keeps its index entry; v4.5.0's erased it | Scripts accept either branch (`50192cd1d`); consistent with V-4 |
| F-19 | 4 | `coinbasetxn.foundersreward` appears only during the YDF mandate (or the founders' period); `ydfpercentage` and `foundersaddress` are gone; v4.5.0 always emitted all three | Stockparity reads it with `get()` (`966d8d746`); yolo's Phase 7 check must not rely on the two dropped keys |
| F-20 | 4 | `getinfo.errorstimestamp` differs between nodes. Not new on 6.20.0 (v4.5.0 returns it too): it is each node's `GetTime()` when no warning is set | Listed as per-node in stockparity (`966d8d746`) |
| F-21 | 4 | `defaultroots.merkleroot` commits to each node's own coinbase (payout key) | Stockparity compares `defaultroots` without it (`966d8d746`) |
| F-22 | 4 | `yellowback_activation.py`, `yellowback_index.py`: block sync stalls after a restart / `invalidateblock` | **open — agent act-sync**; blocks the `pyfw` gate |
| F-23 | 4 | `yellowback_enforcement.py`, `yellowback_attest_enforcement.py`: the work valve does not trip | **open — agent valve** |
| F-24 | 4 | `yellowback_stockparity.py` after the round-2 fixes | **open — rerunning** |
| V-1 | 6 (review) | The template filter commits its dry run into the template overlay (`yellowback/policy.cpp:125`) before 6.20.0's turnstile check in `TestForBlock` (`miner.cpp:548+`); a candidate failing the turnstile leaves phantom overlay state for later candidates | Accepted: fail-safe (a wrong accept is caught by `CheckConnect` at `TestNewBlockAtTipValidity`), needs a turnstile-violating tx; mapping §19 S2 row now says so |
| V-2 | 6 (review) | `lockunspent`'s unlock-all branch (`ReapplyLocks()`, `rpcwallet.cpp:2847`) is unreachable on 6.20.0 (F-15) and its H5 help sentence claimed it works | Help sentence dropped (`966d8d746`); dead branch kept so the hunk stays identical to v4.5.0 |
| V-3 | 6 (review) | H8's `rescanblockchain` site has no 6.20.0 counterpart; F-7's wording omitted it | F-7 corrected; no code change |
| V-4 | 6 (review) | `BodyCorruption`: the `CheckConnect` verdict (`main.cpp:4047`) is final on the `ConnectTip` path (both body-commitment flags set before it), body-replaceable under `fJustCheck` (harmless) | Mapping §19 row. **open — functional proof in `yellowback_enforcement.py` (agent valve, F-23)** |
| V-5 | 6 (review) | `lockunspent` is all-or-nothing on the fork with or without `-yellowback` (inherited from v4.5.0; stricter than stock) | Recorded: stock parity covers the chain and the RPC surface, not every wallet RPC's error-path side effects |
| V-6 | 6 (review) | `BlockAssembler::ybview` (`miner.h:133`) points into `CreateNewBlock`'s frame and is not reset on return | None: every `BlockAssembler` is a one-shot temporary and `CreateNewBlock` reassigns it; noted for the reviewer (mapping §19) |

---

## 7. Estimate

Phases 0–6: about 11 agent-days of work on the critical path with three agents in parallel in
Phases 2–4, roughly two calendar weeks including the owner's decision latency and the nightly
runs. Phase 7 is sized by each component's own acceptance suite (½ day each if nothing breaks).
The single largest risk to the estimate is `api-txbuilder` (the Sapling-funded shapes on the
move-only builder); the second is any surprise in `CheckConnect` running under
`CheckAs::BlockTemplate`, which v4.5.0 never did.
