# INFO — W3-N-10, W3-N-11, W3-N-12, W3-N-13, W3-N-14, 07/NEW-3, 07/NEW-4 — Node RPC, durability and CI notes: decoded act in `set_signact`, scan-cost logging, index fsync on full flush, non-member signatures in `complete`, `make check || true`, and an issue on a fuzz crash

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W3-N-10-14-notes` off `upgrade/vault` in each: `src/rpc/vault.cpp` (`set_signact`/`set_buildact` result), `src/vault/node.cpp` and `src/yellowback/index.cpp` (bench log lines), `src/main.cpp` (`FlushStateToDisk`, one call — gated file, normal review-gate leg, no rule change), `.github/workflows/yellowback-tests.yml` (coverage job, weekly-fuzz job), `doc/vault-rpc.md`, `doc/vault-rpc-contract.json`. W3-N-14(b) is implemented by `MEDIUM-W3-N-3` (listed here for the record). **W3-N-7 was disproved and has no report** (`docs/audits/quantum-vault-ecosystem-wave3/verification/07-verification.md` lines 175-181: a "Fail on a crash" step already turns the weekly-fuzz run red); NEW-4 is the nicety that remains.
**Audit source.** Wave 3: `docs/audits/quantum-vault-ecosystem-wave3/07-node-rpc-mempool-durability-ci.md` W3-N-10..14 (lines 236-286); `docs/audits/quantum-vault-ecosystem-wave3/verification/07-verification.md` W3-N-10..14 (verdict lines 23-27, detail lines 202-224, with corrected citations), NEW-3 (lines 257-263), NEW-4 (lines 265-269); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row W3-N-5..9, 07/NEW-2..4. Wave 4: `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md` §1.5 rows W3-N-10, N-12, N-13 (line 121), W3-N-11 (line 122), W3-N-14 (line 123), 07/NEW-3, 07/NEW-4 (line 126).
**Status:** pending — re-verified at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): every item open on both lines. Only citations moved: `src/rpc/vault.cpp` after line 905 (+32 on ycash-dd) and ycash6's `.github/workflows/yellowback-tests.yml` after line 911 (+8, ycash6 `0742e43`'s split-`DoS(` audit clause).

## 1. Finding

- **W3-N-10 (relay-only gaps).** A MALFORMED V/I-shaped coin created before activation is consensus-spendable (its script is a plain script; `bad-txns-vault-malformed` fires only on *creation* after activation, `ycash-dd/src/vault/state.cpp:434-437`), but `Solver` matches V/I only through `ParseVault`/`ParseIntent` = `Shape::MATCH` (`src/script/standard.cpp:170-181`, `src/vault/template.cpp:253-256`), so `AreInputsStandard` refuses it (`src/policy/policy.cpp:243-244`) and only a miner can include its spend. Also by design: a template spend's txid is malleable until confirmed (selector, re-funding). Documentation exists; keep it (`doc/vault-rpc.md:409-428`: "Anyone may re-fund" … "Re-funding changes the txid" … "Pinning"); the malleability note is carried by `INFO-W3-V-8-01-N-3-01-N-4`.
- **W3-N-11 (`set_signact` blind).** `SignActInPlace` (`src/rpc/vault.cpp:1001-1085`; ycash6 `:1022-1106`) adds every current-member co-signature the wallet can for REMOVE (including `burn: true`), WINDDOWN and closed JOIN, up to the threshold, with no record (acts are not equivocation-slashable) and no decoded display; the result (`ActResult`, `:1087-1097`; ycash6 `:1108-1118`) is only `{hex, type, complete, signatures, required}`. A burn signature is irreversible for the removed member; `vault_decodescript` exists for a manual preview.
- **W3-N-12 (full scans).** `vault::RecheckMempool` (`src/vault/node.cpp:226-283`, `IsVaultRelevant` `:126`) and `YellowbackIndex::RemoveInvalidVaultSpends` (`src/yellowback/index.cpp:565-585`) walk the whole mempool on every tip change under `cs_main` + `mempool.cs`, re-recovering every template spend's set signatures (never cached by design); `vault_getinfo` (`src/rpc/vault.cpp:371-431`, `StateHash` at `:431`) hashes the whole state and `vault_list` (`:478+`) walks every template output under `cs_main`. Bounded by the mempool cost limit and the template caps in `doc/yellowback-pq-dos.md`; acceptable, but unmeasured in the logs. Wave-4 note: since refee-utxo, `EligibleCoins` (`src/rpc/vault.cpp:732-753`) also does one `GetCoin` (a fresh `CCoinsViewMemPool` + cache, `:184-194`) per wallet coin under `cs_main` + `mempool.cs` on every builder call — the same order as `AvailableCoins`; Info, include it in the bench logging if convenient. (The auditor's `node.cpp:604`/`:685-741`/`:743-835`/`:837-847` citations were wrong; corrected by the verifier.)
- **W3-N-13 (index durability by replay).** `FlushStateToDisk` fsyncs the vault database after the chainstate (`src/main.cpp:3692-3694`) but not the Yellowback index, whose per-block commits are `db->Commit(false)` (`src/yellowback/index.cpp:427`; `Commit(bool fSync = false)`, `src/yellowback/db.h:51`). After an OS crash the index can be behind the chainstate; `SyncToChain` (`index.cpp:225-300`) replays (sound: the tip marker is in the same batch), but on a mainnet-sized chain the replay can be long.
- **W3-N-14.** (a) On `upgrade/vault` the CI audit's frozen-file and line-budget legs are report-only by rule (workspace `CLAUDE.md` rule 2; `.github/workflows/yellowback-tests.yml:450-526`) — no action. (b) `SignSetInPlace` counts recovered signatures already on the hex toward `complete` without checking they are current members (`src/rpc/vault.cpp:1655-1660`, `:1707`; ycash6 `:1676-1681`, `:1728`) — **fixed by `MEDIUM-W3-N-3` §4 step 2**.
- **07/NEW-3.** The coverage job runs `make check || true` (`.github/workflows/yellowback-tests.yml:1405`; ycash6 `:1824`), then `src/test/test_bitcoin` directly; `make check` also runs the univalue, secp256k1 and leveldb suites, whose failures are swallowed on that leg (the functional and nightly jobs build `test/test_bitcoin` only, so those suites may run nowhere).
- **07/NEW-4.** The weekly-fuzz job now fails on a crash (`:1575-1584`, `if: always()`; ycash6 `:2012`) but, unlike lockorder (`:1251-1258`), opens no issue; the crash is visible only in the run and in the corpus PR body.

## 2. Root cause

Small omissions in an otherwise sound RPC/durability/CI surface; each is independent.

## 3. Fix options considered

Each item has one obvious fix (below). Rejected: caching set signatures to speed up `RecheckMempool` (W3-N-12) — the plan forbids it (state-dependent membership); a synchronous fsync on every index commit (W3-N-13) — one fsync per full flush is enough.

## 4. Recommended fix

1. **W3-N-11** — `ActResult` (`:1087-1097`) adds `"act": ActJSON(act, mtx.vin[0].prevout)` (`ActJSON` exists, `:529`) to the results of `set_buildact`, `set_signact` (and `set_sendact`'s dryrun from `MEDIUM-W3-N-1`); `doc/vault-rpc.md` `set_signact` (`:247-255`): "check `act` — for REMOVE with `burn: true` the removed member's bond is frozen for ever — before signing". Additive contract change.
2. **W3-N-12** — `LogPrint("bench", "vault: RecheckMempool %u txs, %u vault-relevant, %.2fms\n", …)` in `RecheckMempool` and the same in `RemoveInvalidVaultSpends`; nothing else.
3. **W3-N-13** — in `FlushStateToDisk`'s full-flush branch (`main.cpp:3692-3694`, ycash6 equivalent), after the vault DB flush: `if (yellowback::g_yellowback && !yellowback::g_yellowback->Sync()) return AbortNode(state, "Failed to write to the Yellowback index");` where `Sync()` is a new `YellowbackIndex` method that writes an empty batch with `fSync = true` (one fsync per full flush, as the vault DB).
4. **07/NEW-3** — replace `make check || true` with the suites it is meant to run, each failing the job: `make -C src/univalue check && make -C src/secp256k1 check && make -C src/leveldb check` (or plain `make check` once it is green on the coverage build); if a suite is known-broken under `--enable-lcov`, exclude it by name with a comment, not by `|| true`.
5. **07/NEW-4** — copy the lockorder job's "Open an issue on failure" step (`:1251-1258`) to weekly-fuzz with `if: failure()` and title `weekly-fuzz found a crash on $REF: run $GITHUB_RUN_ID`; both lines.
6. **W3-N-10, W3-N-14(a)** — no change.

## 5. Tests

- W3-N-11: `qa/rpc-tests/vault_rpc_contract.py` — the `act` field's shape; `vault_slashing.py` asserts `act.burn` on a burn removal before `set_sendact`.
- W3-N-13: `qa/rpc-tests/vault_undo_prune.py` already SIGKILLs after a flush — add an assertion that the Yellowback index tip equals the chain tip right after restart (no replay logged) when the kill follows a full flush.
- NEW-3/NEW-4: the workflow runs themselves (a deliberately failing univalue test on a scratch branch shows the leg goes red; a synthetic `crash-*` file on a scratch branch shows the issue is opened).

## 6. Acceptance criteria

- `set_signact`/`set_buildact` return the decoded act; the mempool rescans log their cost under `-debug=bench`; a full flush fsyncs the Yellowback index; the coverage job no longer swallows `make check` failures; weekly-fuzz opens an issue on a crash; both lines.

## 7. Risks and side effects

- The fsync adds one sync per full flush (minutes apart). The `make check` change may surface a pre-existing suite failure on the coverage build — fix or exclude it by name.

## 8. Effort estimate and dependencies

- ≈ 1 day total across both lines. Independent, except W3-N-14(b), which ships with `MEDIUM-W3-N-3-ycash-set-sign-validate-before-record.md`.
