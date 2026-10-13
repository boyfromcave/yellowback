# LOW — W4-N-5 — The refee-utxo regression test is timing-dependent, neither new refusal branch nor the cancel re-fund path is exercised, and its fee assertion is ten times too loose: make the regression deterministic and cover the branches

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W4-N-5-refee-test-fidelity` off `upgrade/vault` in each: `qa/rpc-tests/vault_refee.py`, and for the deterministic hook either `src/validationinterface.cpp` plus `src/init.cpp` (a regtest-only `-walletnotifydelay` option, help text marked debug) or nothing (see §3). Test code (plus at most one regtest-only debug option) — no consensus, wallet-format or RPC-contract change. CI: no workflow change (`vault_refee` is already registered: `ycash-dd/.github/workflows/yellowback-tests.yml:94`, ycash6 `:123`; `qa/pull-tester/rpc-tests.py` ycash-dd `:79`, ycash6 `:90`).
**Audit source.** `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md` W4-N-5 (summary row line 140; pointer line 236) and §4 "Test fidelity" (lines 282-305); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md` row W4-N-1/N-2/N-5 (line 46, Low).
**Status:** pending — re-verified at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): open on both lines (`vault_refee.py` differs between the lines only in its harness preamble; the refee-utxo rounds are byte-identical, ycash-dd `:227-266` = ycash6 `:232-271`).

## 1. Finding

The refee-utxo commits (ycash-dd `ce6df11` + `da5e0fe`, ycash6 `22c6354` + `cdec862`) add three rounds to `qa/rpc-tests/vault_refee.py` (`:227-266`; ycash6 `:232-271`): each spends the fee coin of a signed unlock in a block mined at once (`spend_and_mine_now`, `:113-121`; ycash6 `:116-124`) and calls `vault_refee` / `vault_buildunlock` immediately ("no sync, no wait", `:242`, `:256`). The bug they guard (a wallet coin spent in a block, still counted unspent by the wallet) is visible only while the wallet's notifier — a 1-second tick, `src/validationinterface.cpp:90-96`, ycash6 `:125-131` — has not yet run. Likely within one RPC round-trip, not guaranteed; three rounds raise the odds. On the fixed code the test cannot fail falsely; on a regressed tree it can pass. That is a probabilistic regression test for a correctness fix.

Coverage gaps: (a) neither new refusal in `Refee` is exercised — "the new fee input … is spent or is a replaced input" (`src/rpc/vault.cpp:924-928`; ycash6 `:941-945`) and "would pay a fee of …" (`:931-937`; ycash6 `:948-954`); (b) `BuildIntentCancel`'s re-fund path (`:1886-1888`) is never raced (only unlocks are); (c) mempool spends (`LOW-W4-N-1`), a foreign hex naming a locked coin (W4-N-2) and any W3-N-2 negative are untested; (d) the fee assertion `0 < fee <= 0.001` (`:247`) admits ten times the only reachable values, 0.0001-0.00010999 YEC (`VAULT_RPC_FEE` = 10,000 zat plus an excess below `VAULT_RPC_MIN_CHANGE` = 1,000 zat), so a regression that over-pays the fee by up to 9× passes. The real assertions are sound: new input ≠ replaced (`:245`, `:260`), unspent per `gettxout` (`:246`, `:261-262`), sighash unchanged (`:244`, `:258`), the spend confirms (`:248-250`, `:263-265`).

## 2. Root cause

- `qa/rpc-tests/vault_refee.py:227-266` — the race is reproduced by timing, with no hook to hold the wallet notification.
- `qa/rpc-tests/vault_refee.py:247` — the bound was chosen loose rather than derived from `VAULT_RPC_FEE`/`VAULT_RPC_MIN_CHANGE`.
- No case reaches the refusal branches or the cancel re-fund path.

## 3. Fix options considered

1. **A regtest-only `-walletnotifydelay=<ms>` (debug option) that postpones the notifier's next tick (recommended).** The test sets a large delay, spends and mines, calls the RPC, then asserts; the pre-fix code fails every time. Small, local, regtest-gated (refuse the option off regtest, as other test-only flags in the tree are).
2. **No node change: assert on a state the wallet cannot have caught up to.** E.g. stop the notifier's progress by holding `cs_main` from another RPC — not possible from Python without a hook. Rejected.
3. **Mempool-spend variant instead.** Deterministic without a hook (the wallet's view is irrelevant once the code checks `mapNextTx`), and it is the cheapest add — but it tests `LOW-W4-N-1`'s fix, not the block-spend fix. Do both: option 1 for blocks, the mempool variant (in `LOW-W4-N-1`) for the mempool.
4. **Leave three probabilistic rounds.** Rejected for a correctness regression.

## 4. Recommended fix

1. **Deterministic block-spend regression (both lines).** Add `-walletnotifydelay` (regtest only; `src/init.cpp` parses it, `src/validationinterface.cpp`'s notifier loop (`:90-96`; ycash6 `:125-131`) adds the delay before each tick). In `vault_refee.py`, restart node 0 with `-walletnotifydelay=5000` for the refee-utxo section; keep one of the three rounds as is (it now always races) and drop the other two or keep them as smoke. Assert additionally that `n0.gettransaction(<the spending tx>)` is **not** yet known to the wallet when `vault_refee` returns (proves the race was real).
2. **Tight fee assertion.** Replace `:247` with `assert Decimal('0.0001') <= r2['fee'] < Decimal('0.00011'), r2` and add the same for `r3`'s (`vault_buildunlock` result has no fee field: compute it from `decoderawtransaction` + `gettxout` of the inputs).
3. **Cancel re-fund race.** Mirror the `b3`/`r3` round for `vault_buildcancel` (spend the remembered cancel's fee coin with `spend_and_mine_now`, call `vault_buildcancel` at once → `refunded`, same sighash, new input unspent, the cancel confirms inside the delay).
4. **Refusal branches** (item (ii) is owned here; `LOW-W3-N-2-…` §5 points to it). (i) "spent or replaced input": reachable deterministically only with the mempool variant of `LOW-W4-N-1` (a candidate spent in the mempool between pick and check) or, after `LOW-W3-N-2-W4-N-2-N-3-N-4`, through its stable reason `vault-refee-input`; (ii) "fee": start a node with `-maxtxfee=0.0001` and no attested price, give it only an exact coin with excess → refused, `listlockunspent` and the mempool unchanged. Both reasons are also provoked by `vault_rpc_contract.py` once `LOW-W3-N-2-W4-N-2-N-3-N-4` adds them to the error table.
5. **Cross-report cases, owned elsewhere (do not duplicate):** mempool spends → `LOW-W4-N-1-ycash-mempool-spent-fee-coins.md` §5; foreign hex naming a `lockunspent` coin (W4-N-2) and the W3-N-2 negative (a build with a large foreign change output) → `LOW-W3-N-2-W4-N-2-N-3-N-4-ycash-vault-refee-cap-lock-release.md` §5. This report owns items 1-4 only; whoever lands second rebases the shared file.

## 5. Tests

- The test itself is the deliverable. Prove it bites: on a scratch branch revert `EligibleCoins`'s `GetCoin` filter (`src/rpc/vault.cpp:747-749`; ycash6 `:764-766`) and confirm the deterministic round fails on every run (10/10), on both lines; restore and confirm it passes.
- `vault_refee` stays in `YELLOWBACK_SCRIPTS` and the default `rpc-tests.py` list on both lines; its runtime grows by one restart.

## 6. Acceptance criteria

- With the block-spend filter reverted, `vault_refee.py` fails deterministically on both lines; with it present, it passes.
- The fee assertion admits only `[0.0001, 0.00011)` YEC; the cancel re-fund race and the fee refusal branch are exercised; the input refusal is exercised here or by `LOW-W4-N-1`.

## 7. Risks and side effects

- The debug option must be refused off regtest (a mainnet node must never delay wallet notifications on request). No consensus or wallet-format effect.
- A longer notifier delay can make later steps of the same script wait for the wallet; scope the restart to the refee-utxo section and restart without the flag afterwards.

## 8. Effort estimate and dependencies

- 0.25 day for the debug option, 0.5 day for the test rounds, both lines.
- Dependencies: none hard. Coordinate the shared file with `LOW-W4-N-1-ycash-mempool-spent-fee-coins.md` and `LOW-W3-N-2-W4-N-2-N-3-N-4-ycash-vault-refee-cap-lock-release.md` (their §5 cases land in the same script); if `LOW-W3-N-2-W4-N-2-N-3-N-4` lands first, assert its stable reason strings instead of today's free text.
