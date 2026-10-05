# ycashd 6.20.0 (`dev-rebase-6.20.0` @ 040894344b): baseline test report

> **Draft — discussed with miodragpop.**

To: miodragpop. From: boyfromcave. Date: 2026-09-30.

Why this exists: we are porting a separate overlay onto your 6.20.0 tree. Before adding anything, we
built and exercised the unmodified tree so that we would have a known-good baseline. This report
covers only your tree. It contains three small patches and a list of defects we recorded but did not
fix. All `file:line` references are at `040894344b`.

Thank you for the rebase. It built cleanly from depends, and the core node behaved well. Every
problem below is either narrow or regtest/harness-only.

## 1. What was tested

| | |
|---|---|
| Tree | `miodragpop/ycash` `dev-rebase-6.20.0` @ `040894344b`. `Cargo.lock` resolves every `zcash_*` crate from `miodragpop/librustzcash` rev `ec525fae` (`ycashd-v6.20.0`) |
| Platform | macOS 26 (Darwin 25), Apple Silicon (arm64). Host Apple clang 17; depends-built clang 15 and Rust 1.96 |
| Build | `LIBTOOLIZE=glibtoolize ./zcutil/build.sh -j8` (cold ~35 min), with GNU libtool/coreutils first on `PATH` and `CARGO_TARGET_DIR` pointed inside the tree. Result: `Ycash Daemon version v6.20.0-040894344`, `getnetworkinfo` 6200050 `/YcashCpp:6.20.0/` |
| Unit tests | `test_bitcoin`: two failures at the pin (fix 1). After fix 1: "No errors detected" |
| Regtest, by hand | `nuparams=5ba81b19:1` and `76b809bb:1` (Overwinter and Sapling at height 1). We ran `generate 110`, a transparent send, `z_shieldcoinbase` (10 UTXOs), Sapling to Sapling, Sapling to transparent, 20 more blocks and a clean `stop`. All of it works after fix 1. With fix 3, the same flows also work with all six upgrades through Canopy active at height 1 |
| Functional suite | All 119 `BASE_SCRIPTS` of `qa/pull-tester/rpc-tests.py`, plus `zmq_test` and four extended scripts. Each script was run on its own against the pin plus the three patches. Every pass was run twice. Every failure was re-run or inspected (section 4) |

## 2. Patches (in `patches/`)

These are three independent `git format-patch` files. Each one applies to `040894344b` with
`git apply --check`, and all three apply in order with `git am`. They touch separate files. Together
they change 12 lines.

### 0001: miner: zero-initialise the coinbase Sapling anchor

- **What:** All three coinbase paths declare `std::array<uint8_t, 32> saplingAnchor;` without
  initialising it, then pass it to `sapling::new_builder`. The locations are `src/miner.cpp:196`
  (Orchard recipient), `:235` (Sapling) and `:252` (transparent). `new_sapling_builder`
  (`src/rust/src/sapling.rs:392`, `:404-405`) runs `Anchor::from_bytes` and returns
  `"Invalid Sapling anchor"` for non-canonical bytes.
- **Impact:** Whether a block template can be built depends on what is on the stack. On this build
  the failure was deterministic: `test_bitcoin` failed `miner_tests/CreateNewBlock_validity` and
  `tx_validationcache_tests/tx_mempool_block_doublespend`. On regtest, `getblocktemplate` and
  `generate` failed once a valid Sapling spend was in the mempool. The spend used the chain's own
  `finalsaplingroot` as its anchor. Other compilers or platforms may happen to see zeroes and never
  hit this. It can affect any miner that calls `getblocktemplate`.
- **Fix:** `= {}`. A coinbase bundle has no spends, so its anchor is unconstrained, and all-zero
  bytes are a canonical field element. After the fix, both tests pass, the whole of `test_bitcoin`
  is clean, and the stuck spend is mined by the next block.
- **Origin:** Upstream zcashd `fd675c320` ("rust: Migrate to `zcash_primitives 0.14.0`", Jack Grigg,
  2024-03-01; `git blame src/miner.cpp:196`). zcashd may want the same one-line fix.

### 0002: qa: harness writes ycash.conf and defaults to src/ycashd

- **What:** `ycashd` reads `ycash.conf` (`src/util/system.cpp:82`) and refuses to start without it
  (`:385`). The harness still writes `zcash.conf` (`qa/rpc-tests/test_framework/util.py:203`) and
  defaults to `src/zcashd` (`util.py:32`). `qa/rpc-tests/multi_rpc.py:29` and
  `qa/rpc-tests/wallet_deprecation.py:36,51` open `zcash.conf` directly.
- **Impact:** Every functional test fails in `initialize_chain`.
- **Fix:** Use `ycash.conf` and `src/ycashd` in those four places. With the series applied, 39 of
  the 119 `BASE_SCRIPTS` pass. The rest are covered in section 4.

### 0003: chainparams: regtest keeps Equihash (48,5) under every network upgrade

- **What:** `CChainParams::EquihashN/K` (`src/chainparams.cpp:983-995`) consult
  `GetEquihashOverride()` (`:968`), which walks `NetworkUpgradeInfo` on every network. The v4.5.0
  accessors returned `consensus.nEquihashN/K` on regtest before looking at the per-upgrade table.
- **Impact:** If regtest activates the Ycash upgrade (`374d694f`), mining switches to (192,7). That
  took about 5 minutes per block here. Blossom, Heartwood and Canopy must activate after Ycash, so
  no practical regtest can run them. That also rules out testing anything at mainnet's current
  epoch.
- **Fix:** A regtest early-return in both accessors, 4 lines. Both relevant consumers use these
  accessors: the miner (`src/miner.cpp:894-895`) and the solution-size check in
  `ContextualCheckBlockHeader` (`src/main.cpp:5765-5766`). `CheckEquihashSolution` already accepts
  (48,5), so mining and validation stay consistent. Mainnet and testnet are unaffected.
  Verification: six upgrades active at height 1 (tip branch id `19bd2d2f`), 110 blocks in under a
  second, then shield, Sapling to Sapling, deshield and a transparent send all mined.

## 3. Defects recorded but not fixed

Listed roughly by operational impact.

### 3.1 `-lightwalletd` without `-insightexplorer` crashes on the first connected block

- **Where:** `src/init.cpp:1751` sizes the insight cache only under `-insightexplorer`, and
  `:1814-1816` creates `pinsightExplorerDB` only when that cache is non-zero. `-lightwalletd` still
  sets `fAddressIndex` (`src/main.cpp:6691-6693` and `:7296-7298`). `ConnectBlock` then calls
  `pinsightExplorerDB->WriteAddressIndex` on NULL at `src/main.cpp:4080`. The same applies to
  `DisconnectBlock` at `:3142`, and to the address-index read helpers behind the `getaddress*` RPCs at `:2142`/`:2156`/`:2170`. Crash
  stack: `ConnectBlock` > `CInsightExplorerDB::WriteAddressIndex` > `CDBWrapper::WriteBatch`.
- **Introduced:** `0e4c703da` ("Move insight explorer indexes to a separate database", 2026-05-11).
- **Impact:** An operator who runs a lightwalletd backend with `-lightwalletd` alone gets a node that
  dies on its first block. `addressindex.py` reproduces this 3 out of 3 times: its `-lightwalletd`
  node dies. Workaround: also pass `-insightexplorer -txindex`.
- **Suggested fix:** Create the insight DB (and give it a cache share) whenever `fAddressIndex`
  will be set, i.e. under `-insightexplorer || -lightwalletd`. Alternatively, keep the address
  index in `pblocktree` for the lightwalletd-only case. The `ReadFlag("insightexplorer")` fallback
  at `src/main.cpp:6680-6682` already expects the DB to be absent in some configurations.

### 3.2 `RewindBlockIndex` now keeps *failed* never-connected entries across a parameter change

- **Where:** The `sufficientlyValidated` lambda in `src/main.cpp:7066-7077` returns `true` early for
  `!pindex->IsValid(BLOCK_VALID_CONSENSUS)`. `IsValid` returns false for any entry with
  `BLOCK_FAILED_MASK` set (`src/chain.h:547-553`), so blocks marked failed are now also "retained".
  Before this change they lacked `nCachedBranchId` and were erased by the loop at `:7167`. That loop
  still resets `pindexBestInvalid` for erased entries, which shows the erasure was intended.
- **Introduced:** `1770fce16` ("rewind: Preserve unconnected block index entries across restarts",
  2026-05-08). The goal of that commit is sound: it keeps not-yet-connected `BLOCK_HAVE_DATA`
  entries after an interrupted sync or reindex. Only the failed subset is the problem.
- **Impact:** This changes how blocks are re-validated across an upgrade. Consider a node that
  rejected a block under its old rules: an un-upgraded binary that saw the post-activation chain, or
  a regtest node restarted with different `-nuparams`. That block used to be erased on restart and
  then re-evaluated under the new rules. Now it stays `BLOCK_FAILED_VALID`, so the upgraded node
  will not follow the chain it should follow until someone runs `reconsiderblock`. This is latent
  until Ycash's next activation, but that is exactly the moment it matters. `rewind_index.py` fails
  on its post-restart assertion (`rewind_index.py:71`, 2 out of 2).
- **Suggested fix:** Exempt only entries that have not failed:
  ```cpp
  if (!pindex->IsValid(BLOCK_VALID_CONSENSUS))
      return !(pindex->nStatus & BLOCK_FAILED_MASK);   // keep unconnected, erase failed (re-evaluate)
  ```
  This keeps the interrupted-sync benefit and restores the upstream re-evaluation of failed blocks
  and their `BLOCK_FAILED_CHILD` descendants. `rewind_index.py` is the regression test.

### 3.3 NU6 / NU6.1 / NU6.2 regtest protocol versions exceed `PROTOCOL_VERSION`

- **Where:** Regtest `nProtocolVersion` is 270110 / 270130 / 270150 (`src/chainparams.cpp:667`,
  `:670`, `:675`). `PROTOCOL_VERSION` = `MIN_PEER_PROTO_VERSION` = 270013 (`src/version.h:18`,
  `:26`). The peer check is at `src/main.cpp:7996-8006`.
- **Introduced:** `04d22dda9` ("chainparams: fix NU6.2 activation default; Ycash-scheme NU6.x
  versions", 2026-06-03).
- **Impact:** Once NU6.x activates on regtest, every peer, including another node of the same
  binary, is disconnected with `obsolete version 270013` and the nodes partition.
  `orchard_nu6_2.py` reproduces this ("Block sync failed"). This is latent: NU6.x has
  `NO_ACTIVATION_HEIGHT` everywhere. The mainnet values (NU5 270015, NU6 270120, NU6.1 270140,
  NU6.2 270150; `:139-148`) are also above 270013, which is expected as long as those upgrades stay
  unscheduled. Workaround on regtest: `-nurejectoldversions=0`.
- **Suggested fix:** Keep regtest's NU6.x versions at or below `PROTOCOL_VERSION`, as regtest
  already does for Canopy (170012) and NU5 (170050). Alternatively, bump `PROTOCOL_VERSION`
  whenever an upgrade is scheduled.

### 3.4 Absurd-fee error prints the payment total as "the conventional fee"

- **Where:** `src/wallet/wallet_tx_builder.cpp:815` (the no-change branch) calls
  `AbsurdFeeError(resolved.Total(), finalFee)`. The constructor's first parameter is
  `conventionalFee` (`wallet_tx_builder.h:319`). The change branch at `:804` passes
  `conventionalFee` correctly.
- **Introduced:** Upstream zcashd `c54c4ee98` ("Adjust wallet absurd fee check for ZIP 317", Greg
  Pfeil, 2023-04-13).
- **Impact:** Cosmetic only, because the comparison itself is correct. The message reads "Fee
  0.00015 is greater than 4 times the conventional fee for this tx (which is 9.99985)".
- **Suggested fix:** Pass `conventionalFee` at `:815`. zcashd likely needs the same change.
- **Related policy note (your call, not a bug):** Under the default `-feepolicy=peroutput`
  (`3223757e6`), the same `WEIGHT_RATIO_CAP` check (`src/zip317.h:23`, applied at `:803`/`:814`)
  compares an *explicit* fee with 4 × the flat per-output floor. That makes the cap 0.00004 YEC.
  v4.5.0 accepted any explicit fee up to the output total. The comment at
  `wallet_tx_builder.cpp:113-115` ("An explicit user-supplied fee is never clamped here") is true of
  the floor computation but not of the send as a whole. Existing clients that send an explicit fee
  above 0.00004 now get refused. Examples: YecWallet v4.5.0's `0.00001 × n` fee for 5 or more
  Sapling outputs, or any user-entered fee above 0.00004. Thirteen inherited scripts fail on this
  (section 4).

### 3.5 `TransactionBuilder` move constructor moves three members from themselves

- **Where:** `src/transaction_builder.h:297-299`:
  `orchardSpendingKeys(std::move(orchardSpendingKeys))`, `firstOrchardSpendAddr(...)` and
  `firstSaplingSpendAddr(...)` should read `builder.` in each case. Each member is initialised from
  itself before it has been constructed, which is undefined behaviour. In practice the members end
  up empty, so a builder moved after `AddSaplingSpend` / `AddOrchardSpend` loses its first spend
  address and spending keys. The move-assignment operator (`:307-333`) is correct, although three of
  its lines end in `,` instead of `;`.
- **Introduced:** Upstream zcashd `3e35f699b` ("builder: Move all fields in `TransactionBuilder` move
  constructors", 2023-05-17) and `457367bbd`.
- **Impact:** Latent. We found no in-tree code that moves a `TransactionBuilder`. The `std::move`
  calls in `asyncrpcoperation_*` move a `WalletTxBuilder`. Any future code that moves a builder
  would silently break.
- **Suggested fix:** Add `builder.` to the three initialisers. `-Wuninitialized` / `-Wself-init`
  may also flag them.

### 3.6 Stale `GetBlockSubsidy` declaration

- **Where:** `src/main.h:332` still declares the free function
  `CAmount GetBlockSubsidy(int nHeight, const Consensus::Params&)`. Since upstream `f94462c37`
  ("Make `GetBlockSubsidy` a method of `Consensus::Params`") only
  `Consensus::Params::GetBlockSubsidy(int)` exists (`src/consensus/params.h:255`).
- **Impact:** A call to the free function compiles and then fails to link. Nothing in-tree calls it.
- **Suggested fix:** Delete the declaration.

### 3.7 `-disablewallet`: `fullyNotified` never becomes true (unexplained)

- **What:** With `-disablewallet`, `getblockchaininfo.fullyNotified`
  (`src/rpc/blockchain.cpp:1744`, which reads `ChainIsFullyNotified` at `src/main.cpp:4581-4585`)
  stays false. The harness's `sync_blocks` (`util.py:142`) therefore never returns, and
  `disablewallet.py` fails 3 out of 3 times.
- **Not yet traced.** We did not trace this to a commit, and we did not compare it against upstream
  zcashd. Our unverified hypothesis: with no wallet, `ThreadStartWalletNotifier`
  (`src/init.cpp:663`, started at `:2081-2083`) takes `chainActive.Tip()` before genesis is
  connected, so the notified sequence never catches up with the connected sequence. The signal is
  regtest-only, so mainnet impact is nil.

### 3.8 Behaviour changes worth knowing (not defects)

- `setmocktime` now requires the node to be started with a non-zero `-mocktime`
  (`src/rpc/misc.cpp:519`). v4.5.0 switched clocks on the first call.
- Under a fixed mock clock, transaction relay stops. The inventory trickle fires on
  `nNextInvSend < nNow` (`src/main.cpp:9193-9197`, `nNow = GetTimeMicros()` at `:9085`), and that
  is read from the node clock, which does not advance. Tests have to nudge the clock while mempools
  converge.
- `lockunspent`'s arity row `{{o, o}, {}}` (`src/rpc/common.h:174`, upstream `4ddf2a93d`) makes
  both arguments required. As a result, the one-argument unlock-all branch in
  `src/wallet/rpcwallet.cpp` (`params.size() == 1`) cannot be reached from RPC.

## 4. Inherited functional suite (pin + the three patches)

**BASE_SCRIPTS: 39 pass and 80 fail** (75 fail outright and 5 hang). Outside `BASE_SCRIPTS`,
`zmq_test`, `invalidateblock` and `getblocktemplate_longpoll` pass. The last two aborted on v4.5.0.
`getblocktemplate_proposals` still builds a Bitcoin-format block. `p2p-acceptblock` still uses the
mininode.

Passing (each twice): wallet, walletbackup, fundrawtransaction, reorg_limit,
getrawtransaction_insight, spentindex, timestampindex, key_import_export, zapwallettxes,
feature_logging, feature_walletfile, rawtransactions, threeofthreerestore, rest,
wallet_deprecation, nodehandling, reindex, listtransactions, merkle_blocks, sapling_rewind_check,
sapling_v4_value_balance, wallet_parsing_amounts, wallet_zero_value, wallet_broadcast, proxy_test,
errors, keypool, txn_doublespend (both modes), mempool_reorg, mempool_resurrect_test,
mempool_spendcoinbase, regtest_signrawtransaction, httpbasics, multi_rpc, blockchain,
getmininginfo, decodescript, getchaintips.

Most failures come from upstream-Zcash assumptions in the harness, not from the node. Each row gives
the harness change that would clear that class:

| Class | # | Cause | Harness change that would fix it | Examples |
|---|---|---|---|---|
| Branch ids | 44 | `qa/rpc-tests/test_framework/util.py:41-44` hold Zcash's Blossom/Heartwood/Canopy/NU5 ids (`2bb40e60`, `f5b9230b`, `e9ff75a6`, `c2d6d0b4`). The node rejects them at start: `Invalid network upgrade (…)` | Use Ycash's ids from `src/consensus/upgrades.cpp:53-68`: Blossom `0x8E471BD6`, Heartwood `0x66314DA3`, Canopy `0x19BD2D2F`, NU5 `0xF919A198`, and add `YCASH_BRANCH_ID = 0x374D694F` (`:34`). Tests that activate Blossom or later must also activate Ycash first, which is practical only with patch 0003 | wallet_listunspent, wallet_z_sendmany, getblocktemplate, nuparams, every `*orchard*` |
| Fee cap | 13 | Scripts pass ZIP-317-era explicit fees (0.0001 / 0.00015 / 0.0002), and the cap is 0.00004 (3.4) | Either start test nodes with `-feepolicy=zip317`, or make `test_framework/zip317.py` (`MARGINAL_FEE = 5000`, `:16`) follow the per-output policy. `prioritisetransaction` also needs its unpaid-action expectations revisited | wallet_sapling, mempool_tx_expiry, zkey_import_export, wallet_changeaddresses |
| Mininode | 9 (4 hang) | `test_framework/mininode.py:54` connects at `SAPLING_PROTO_VERSION = 170006`, which is below `MIN_PEER_PROTO_VERSION` 270013, so the node logs `obsolete version 170006; disconnecting` | Default the mininode/comptool version to 270013 (or to the active epoch's Ycash version) | bip65-cltv-p2p, invalidblockrequest, p2p_node_bloom, p2p-fullblocktest |
| Addresses | 3 | Hard-coded Zcash regtest addresses (`tm…`, `zregtestsapling…`, `texregtest…`). Ycash regtest uses base58 `{0x1C,0x95}` / `{0x1C,0x2A}` and HRP `yregtestsapling` (`src/chainparams.cpp:689-699`) | Regenerate the vectors for Ycash regtest | signrawtransactions, sprout_sapling_migration, converttex |
| Pin defects | 3 | Sections 3.1-3.3 | Fix in the node | addressindex, rewind_index, orchard_nu6_2 |
| Caches | 2 | `qa/rpc-tests/cache/{sprout,golden-v5.6.0,tarnished-v5.6.0}` are Zcash regtest wallets: `Wallet wallet.dat is not for Ycash regtest network` | Regenerate the caches on ycashd | mergetoaddress_mixednotes, turnstile |
| Branding | 2 | `qa/rpc-tests/framework.py:36` looks for `Zcash version`, and the `show_help` fixture contains Zcash help text | Use `Ycash version` and regenerate the fixture | framework, show_help |
| Ycash policy | 2 | Intended Ycash behaviour: UA accounts are refused while NU5 is inactive (`81bab58fb`), and `walletconfirmbackup` with imported keys needs `acknowledge_imports=true` (`9e8b4f58c`) | Update or skip these tests | soft_fork_disabling_orchard, wallet_import_export |
| Environment | 1 | The `base58` Python module was missing on our side. With it installed, the script would hit the branch-id and funding-stream classes next | none (ours) | coinbase_funding_streams |
| Unexplained | 1 | Section 3.7 | — | disablewallet |

Python note: `mininode.py` still imports `asyncore`, which was removed in Python 3.12. We ran the
suite on 3.11.

Per-script logs and timings are available on request. Please treat everything here as a set of
suggestions. You know this tree far better than we do, and some of these may already be on your
list.
