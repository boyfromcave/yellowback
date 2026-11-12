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
- **Applied (2026-10-28, both Yellowback node lines):** the refinement as suggested, plus one line in
  `LoadBlockIndexDB` that marks each descendant of a failed entry `BLOCK_FAILED_CHILD`. Without it the
  refinement erases the failed entry but keeps an unmarked child (a header received before the
  parent failed, or an off-chain block whose `BLOCK_FAILED_CHILD` from `FindMostWorkChain` was never
  written), whose `pprev` then dangles; `CheckBlockIndex` fails `nNodes == forward.size()`. The
  v4.5.0 line (`ycash-dd`) takes `1770fce16` with both. `vault_activation_restart.py` covers it.
  **Then (2026-10-28) generalised:** `1770fce16` has the same hole for a connected entry erased for a
  stale branch id (a node that connected post-activation blocks under the old rules and holds
  never-connected blocks above them, then upgrades): the child was kept under the erased parent.
  `RewindBlockIndex` now visits entries parents first and erases every descendant of an erased
  entry, which also covers the failed case, so the `LoadBlockIndexDB` line was removed.

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

### 3.9 `getunconfirmedbalance` cannot be called (no argument-table row)

> Added 2026-11-10, after this report was sent. Found on our 6.22.0-beta1 build; the cause is in the
> pin unchanged.

- **Where:** `getunconfirmedbalance` is registered (`src/wallet/rpcwallet.cpp:6488`, category
  `wallet`) but has no row in the shared argument table `rpcCvtTable` (`src/rpc/common.h:43`).
  Both sides require a row: `ycash-cli` refuses the call with "error: Unknown RPC method,
  getunconfirmedbalance" (`src/rpc/client.cpp:72`), and the server answers a plain JSON-RPC call with
  HTTP 500, code -32603, "Parameters for getunconfirmedbalance not found – this is an internal error,
  please report it." (`src/rpc/server.cpp:519`). `help getunconfirmedbalance` works, so the method
  looks available.
- **Introduced:** Upstream zcashd `4ddf2a93d` ("Share RPC param table between client and server",
  Greg Pfeil, 2023-02-20). Before it, the client table listed only methods with non-string
  arguments and any other method went through; the shared table made a row mandatory, and this
  no-argument method was never given one. Upstream zcashd has the same defect at least up to
  `b66266c31` (2026-06-02, the newest upstream zcashd commit in the history of this pin): the method is
  registered, the table has no row and the server check is there. We did not check zcashd after that
  commit.
- **Same class:** `dumpwallet` (registered as `hidden`, `rpcwallet.cpp:6480`) has no row either.
  Upstream removed it in `265145145` and kept the handler as a tombstone that points callers to
  `z_exportwallet`; without a row the tombstone's message is never reached, and callers get the two
  errors above instead. We keep that behaviour (the method is removed either way) and record it.
- **Impact:** The method is unusable through every interface; there is no workaround.
- **Suggested fix:** Add `{ "getunconfirmedbalance", {{}, {}} }` to `rpcCvtTable`, and a unit test
  that compares every registered method with the table in both directions. We did both on our line
  (`boyfromcave/ycash6`, `src/wallet/test/rpc_table_tests.cpp`, with `dumpwallet` as the one
  allowlisted exception).

### 3.10 `-deletetx` leaves dangling `wtxOrdered` pointers, and its spent-tx loop leaves spend-index entries

> Added 2026-11-11. Found while reviewing a wallet erase on our 6.22.0-beta2 line; the cause is in the
> pin unchanged.

- **Where:** `CWallet::DeleteTransactions` (`src/wallet/wallet.cpp:2913`) erases from `mapWallet` in
  two loops: expired/conflicted transactions at `:2934` and spent, deeply confirmed ones at `:2952`.
  `wtxOrdered` (`src/wallet/wallet.h:1805`) holds a raw `CWalletTx*` for every entry, inserted at
  `wallet.cpp:3919` and `:3940`, and nothing in the tree ever erases from it. Each erased transaction
  therefore leaves a dangling pointer. Readers that dereference it include `listtransactions`
  (`src/wallet/rpcwallet.cpp:2161`) and the smart-time loop in `AddToWallet`
  (`wallet.cpp:3952`ff.), which walks `wtxOrdered` from the newest entry. The spent-tx loop
  (`:2952`) also skips `RemoveFromSpends` (`:2694`), which the expired loop calls (`:2936`), so that
  transaction's `mapTxSpends` / nullifier entries stay behind (see 3.12).
- **Introduced:** `ae23774b3` ("Port deletetx + -bdbcache from YCASH_WR", 2026-05-15). The skipped
  `RemoveFromSpends` came across from the 4.5.0 code.
- **Reproduction (reasoning):** Run with `-deletetx` (and the default `-deletetxconflict`). An expired
  wallet transaction is erased whatever its age, through the `wtxDepth == -1` branch, and it is often
  the newest entry in `wtxOrdered`. The next `listtransactions` then reads freed memory, as does the
  next wallet transaction that arrives in a block. Spent transactions are older, so
  `listtransactions` with a large `count` reaches them.
- **Impact:** Use-after-free in the wallet of the operators `-deletetx` is meant for (pools,
  long-running nodes). In practice that means garbage times and amounts, or a crash. The option is
  off by default.
- **Severity:** High for `-deletetx` users (memory unsafety on a routine RPC); none otherwise.
- **Suggested fix:** Before each `mapWallet.erase`, erase the transaction's `wtxOrdered` entry by
  pointer (look up its `nOrderPos` range and compare pointers), and call `RemoveFromSpends(txid)` in
  the spent loop as in the expired loop. On our line, `CWallet::EraseUnbroadcastTx` does exactly this
  for our own erase (`boyfromcave/ycash6#99`). `DeleteTransactions` itself is **not yet fixed on our line**.
- **Same in 4.5.0:** Partly. `ref/ycash` has no `wtxOrdered` (it sorts `mapWallet` on each call), but
  its spent loop (`src/wallet/wallet.cpp:4080`) also skips `RemoveFromSpends`, unlike the expired
  loop (`:4051`-`:4055`). That code is built only with `YCASH_WR` (`:3949`).

### 3.11 `getbalance` / `getwalletinfo` with `asOfHeight` use a balance cache that ignores the height

> Added 2026-11-11. Found while reviewing our balance RPCs on 6.22.0-beta2; the cause is in the pin
> unchanged.

- **Where:** `CWallet::GetBalance` (`src/wallet/wallet.cpp:5834`) calls
  `GetAvailableCredit(asOfHeight, true, filter)` (`:5843`), with the cache on whatever the height.
  `CWalletTx::GetAvailableCredit` (`:5654`) keeps one cached value per transaction
  (`nAvailableCreditCached`). It returns that value when `fUseCache` is set (`:5674-5675`), and
  writes it after every computation (`:5691-5694`), even when the caller passed `fUseCache=false` or
  a historical `asOfHeight`. The computed value depends on the height through
  `IsSpent(hashTx, i, asOfHeight)`. Callers: `getbalance` (`src/wallet/rpcwallet.cpp:1231`),
  `getwalletinfo.balance` (`:3002`) and the balance check in `sendtoaddress` (`:296`).
- **Introduced:** Upstream zcashd `659077aff` ("Propagate asOfHeight to all relevant RPC calls", Greg
  Pfeil, 2022-11-17).
- **Reproduction (reasoning):** A coin received at height 100 and spent at 110.
  1. `getbalance` at the tip caches 0 for the receiving transaction.
  2. `getbalance "*" 1 false false 105` then returns that cached 0, though the coin was unspent at
     105.
  3. The other way round: after the spend has marked the parent dirty, a first call at
     `asOfHeight=105` caches the coin's value. Every later plain `getbalance`, and
     `sendtoaddress`'s balance check, then counts a spent coin until something else marks the
     transaction dirty.
- **Impact:** Wrong historical balances, and a historical query can inflate the current balance.
  Coin selection does not use this cache, so no invalid transaction results: a send against the
  inflated balance fails later with insufficient funds.
- **Severity:** Medium: a balance RPC reports wrong figures without any error. Funds are not at risk.
- **Suggested fix:** In `GetAvailableCredit`, read and write the cache only when
  `!asOfHeight.has_value()`. Write it only when `fUseCache` is set, or give historical callers a
  no-write path. `GetBalance` then needs no change. On our line, `getwalletinfo.balance` is computed
  without the cache (`boyfromcave/ycash6#96`), but `getbalance` is unchanged.

### 3.12 `SyncMetaData` creates an empty wallet transaction from a stale spend entry, and the next resend crashes

> Added 2026-11-11. Hit on our 6.22.0-beta2 line through our own erase (now fixed there); the code is
> in the pin unchanged and in 4.5.0.

- **Where:** `CWallet::SyncMetaData` (`src/wallet/wallet.cpp:1898`) indexes `mapWallet[hash]` for
  every txid in a spend range (`:1909`, `:1913`, `:1920`). It runs from `AddToTransparentSpends` /
  the Sprout and Sapling variants (`:2598`, `:2607`, `:2616`) whenever a wallet transaction is
  recorded as spending an outpoint or nullifier. If the range still names a txid that is no longer
  in `mapWallet`, `operator[]` inserts an empty `CWalletTx` (no `pwallet`, `nOrderPos` -1). Its
  `nOrderPos` is the smallest, so the empty entry becomes `copyFrom`, and its blank `mapValue`,
  `fFromMe` and `nTimeSmart` overwrite those of the real transaction. The next
  `ResendWalletTransactionsBefore` (`:5776`) calls `RelayWalletTransaction` on it (`:5794`), which
  dereferences the null `pwallet` at `:5552`.
- **Precondition at the pin:** Something must erase a transaction from `mapWallet` without
  `RemoveFromSpends`. At the pin, only the spent loop of `-deletetx` does that (3.10), and its stale
  entries are revisited only if a later wallet transaction spends the same input, which a confirmed
  spend makes unlikely. `EraseFromWallet` (`:4365`) has the same gap, but nothing fires the
  `EraseTransaction` signal that calls it. Any future erase path inherits the crash, as ours did
  (a refused send erased, then sent again in the same process).
- **Impact:** A node crash on a wallet resend (periodic, after a block, or
  `resendwallettransactions`), plus wrong metadata written to disk for the real transaction.
- **Severity:** Low at the pin (it needs a rare precondition), but the failure is a crash.
- **Suggested fix:** In `SyncMetaData`, use `mapWallet.find` and skip txids that are not found. Also
  call `RemoveFromSpends` on every erase path (3.10). Our line fixes the erase side:
  `CWallet::EraseUnbroadcastTx` (`boyfromcave/ycash6#99`) removes the spend entries, nullifier maps and
  `wtxOrdered` pointer before erasing. `SyncMetaData` itself is unchanged there.
- **Same in 4.5.0:** Yes. `ref/ycash` `src/wallet/wallet.cpp:1045` (`mapWallet[hash]` at `:1056`),
  `RelayWalletTransaction` at `:4653` (there `assert(pwallet)` at `:4655` aborts instead).

### 3.13 Legacy transparent addresses have no lookahead, so the seed alone cannot find them (latent)

> Added 2026-11-11. Found while building a seed-only restore on our line; latent at the pin, which
> has no restore path.

- **Where:** `getnewaddress` (`src/wallet/rpcwallet.cpp:171`, `:211`) calls `GenerateNewKey(true)`.
  That derives the next external key of the legacy account at `GetLegacyTKeyCounter`, adds it, and
  advances the counter (`src/wallet/wallet.cpp:342-377`). The keypool only ever holds internal
  (change) keys (`GenerateNewKey(false)`, `:6880`). No external key is derived ahead of the counter,
  and a rescan that finds a payment to a derived key does not advance the counter.
- **Introduced:** Not traced. It came in with zcashd's mnemonic-seed wallet.
- **Impact:** A wallet re-created from the same mnemonic holds only the keys it derives itself. A
  rescan then misses every coin paid to a `getnewaddress` address it has not yet re-derived, and
  calling `getnewaddress` again does not trigger a rescan. At the pin this is latent, since there is
  no way to create a wallet from a phrase and `z_exportwallet` carries the keys themselves. It
  matters to any restore tool built on this wallet.
- **Severity:** Low at the pin (latent); High for any seed-only restore.
- **Suggested fix:** Hold a window of external (and internal) keys ahead of the counter, with a
  gap limit like the keypool. When a scanned output pays a held key, mark it used and move the
  counter past it, then top the window up and re-scan the affected range. A fix of this shape is
  in review on our line; it is not on our `upgrade/vault` yet, and this report will cite the pull
  request once it is published.

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
