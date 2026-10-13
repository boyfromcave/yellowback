# LOW — W4-N-1 (+ W4-N-4's doc sentence) — The vault builders' and `vault_refee`'s "unspent in the node's UTXO view (chain tip and mempool)" check does not see mempool spends: add the `mapNextTx` check in one shared helper, and correct the comment and the doc

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W4-N-1-mempool-spent-coins` off `upgrade/vault` in each: `src/rpc/vault.cpp` (a helper `UnspentInNodeView`; `EligibleCoins`, `FeeInputsUnspent`, `Refee`'s new-input check; the comment above `EligibleCoins`), `doc/vault-rpc.md` (`vault_refee`, `:416-419`), `doc/vault-rpc-contract.json` (`source.sha256` only), `qa/rpc-tests/vault_refee.py`. Wallet/RPC only — no consensus or gated file. Client impact: none (fewer spurious failures).
**Audit source.** `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md` W4-N-1 (summary row line 136; detail lines 142-177), W4-N-4 third bullet (line 234, "the doc's '(chain tip and mempool)' is inaccurate until W4-N-1 is fixed"), §3.1 (lines 240-250), row W3-V-8 (line 67, "its `mapNextTx` conflict lookup in `Broadcast` should share a helper with the W4-N-1 fix"); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md` row W4-N-1/N-2/N-5 (line 46, Low, "not re-verified" by a second auditor — re-verified for this report against the code below). Merged here: W4-N-1, and the mempool-claim bullet of W4-N-4 (its other bullets are in `LOW-W3-N-2-W4-N-2-N-3-N-4-ycash-vault-refee-cap-lock-release.md`).
**Status:** pending — re-verified at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): open on both lines; introduced by the refee-utxo commits (ycash-dd `ce6df11`, ycash6 `22c6354`), whose claim it corrects.

## 1. Finding

The refee-utxo delta makes `EligibleCoins` keep a wallet coin only if `GetCoin(op, utxo, height)` succeeds with `height >= 0` and the same output (`ycash-dd/src/rpc/vault.cpp:747-749`; ycash6 `:764-766`), and adds a check in `Refee` that refuses a new input `GetCoin` cannot find (`:920-930`; ycash6 `:937-947`). The comment (`:729-731`), the commit message and `doc/vault-rpc.md:416-417` ("Coins are taken only when unspent in the node's own UTXO view (chain tip and mempool)") claim mempool spends are excluded. They are not: `GetCoin` (`:184-194`, identical on ycash6) reads through `CCoinsViewMemPool`, whose `GetCoins` returns a mempool transaction's outputs or else the base view's coins, **without pruning outputs that mempool transactions spend** (`ycash-dd/src/txmempool.cpp:781-791`; `ycash6/src/txmempool.cpp:1207-1217`). A confirmed coin spent only in the mempool therefore passes. The file already knows this elsewhere: `FeeInputsUnspent` adds an explicit `mempool.mapNextTx.count(in.prevout)` (`:818-819`; ycash6 `:835-836`). The wallet does not close the gap either: `AvailableCoins` filters `IsSpent` (`src/wallet/wallet.cpp:5337`), but the wallet learns of mempool transactions on the same once-per-second notifier as blocks (`src/validationinterface.cpp:90-96`; ycash6 `:125-131`), and `Broadcast` (`:963-979`; ycash6 `:980-996`) submits straight to `AcceptToMemoryPool`, not through `CommitTransaction`. So the race refee-utxo fixed for **block** spends persists for **mempool** spends, for up to about a second.

Scenarios. (a) An operator or Hawkeye `vault_send`s a remembered unlock (its fee coin F now spent in the mempool, the wallet not yet notified) and, within the second, retries `vault_buildunlock` for the same vault: `FeeInputsUnspent` sees F in `mapNextTx` and calls `Refee`; `Refee` releases F's lock (`:900-903`); `ExactCoin` excludes F from the exact search, but its split's `Fund(split, 0)` may pick F (largest first; unlocked, `IsSpent` false, `GetCoin` true) → the split's `Broadcast` fails `txn-mempool-conflict` → the RPC errors (locks restored at `:911-913`). (b) Any external `signrawtransaction` + `sendrawtransaction` of a wallet coin followed at once by a builder: `Fund` funds a set-signed build from a coin already spent; members sign; `vault_send` fails; a later re-fund recovers (the sighash is unchanged, so no sign-once slot is burned). Impact: spurious failures and an extra signing round, not loss of funds — Low.

## 2. Root cause

- `src/rpc/vault.cpp:184-194` — `GetCoin` answers "does this output exist in the chain tip or the mempool", not "is it unspent by the mempool"; `EligibleCoins` (`:732-753`; ycash6 `:749-770`) and `Refee`'s check (`:924`; ycash6 `:941`) use it as the latter.
- `src/rpc/vault.cpp:729-731` and `doc/vault-rpc.md:416-417` — the comment and the doc state the stronger property.
- Three places in the file decide "unspent" three different ways: `FeeInputsUnspent` (`GetCoin` + wallet `IsSpent` + `mapNextTx`), `EligibleCoins` (`GetCoin` + height), `Refee` (`GetCoin` only).

## 3. Fix options considered

1. **One helper with the mempool check, used everywhere (recommended).** `bool UnspentInNodeView(const COutPoint& op, CTxOut& out, int& height, bool confirmedOnly)`: `GetCoin` succeeds, `!confirmedOnly || height >= 0`, and, under `mempool.cs`, `!mempool.mapNextTx.count(op)`. Used by `EligibleCoins` (confirmed only), `FeeInputsUnspent`, `Refee`'s check, and the conflict lookup that `INFO-W3-V-8-01-N-3-01-N-4` adds to `Broadcast`.
2. **Add only `mapNextTx` inline in `EligibleCoins`** (the wave-4 minimal fix). Correct, but leaves three divergent definitions; prefer the helper.
3. **Make the wallet see its own broadcasts at once** (route `Broadcast` through `CommitTransaction`/`SyncTransaction`). Fixes only the wallet's own spends, not an external `sendrawtransaction`; larger change to the wallet path. Rejected.
4. **Document the residual window.** Leaves the claim false. Rejected as the fix; the doc is corrected either way.

## 4. Recommended fix

1. **Helper (both lines),** next to `GetCoin` (`:184-194`): `UnspentInNodeView` as in option 1 (take `mempool.cs` once; `GetCoin` already does — keep the lock order `cs_main → cs_wallet → mempool.cs` used throughout the file).
2. **`EligibleCoins`** (`:747-749`; ycash6 `:764-766`): replace the `GetCoin` line with `if (!UnspentInNodeView(op, utxo, height, true) || utxo != c.tx->vout[c.i]) continue;`.
3. **`Refee`** (`:924`; ycash6 `:941`): `if (!UnspentInNodeView(op, prev, ph, false) || …)`. If `LOW-W3-N-2-W4-N-2-N-3-N-4` lands first, its pick-then-check step uses the helper on the candidate before anything is locked or broadcast.
4. **`FeeInputsUnspent`** (`:811-822`; ycash6 `:828-839`): express it through the helper (plus its existing wallet `IsSpent`), no behaviour change.
5. **Comment and doc (W4-N-4 bullet).** Rewrite `:729-731` to say "unspent in the chain tip and not spent by any mempool transaction". `doc/vault-rpc.md:416-417` (both lines): "Coins are taken only when unspent in the node's chain tip and not spent by a transaction in its mempool, never from the wallet's view alone …"; regenerate `doc/vault-rpc-contract.json`'s `source.sha256` (each line its own).
6. **Shared with `INFO-W3-V-8-01-N-3-01-N-4`:** that report's `Broadcast` conflict lookup reads `mempool.mapNextTx` for the same outpoints; put both behind this helper (or a sibling `MempoolSpender(op)` returning the conflicting txid) so there is one definition.

## 5. Tests

- **Functional `qa/rpc-tests/vault_refee.py` (both lines) — the case that catches it deterministically:** a `spend_in_mempool_now(node, outpoint)` sibling of `spend_and_mine_now` (`:113-121`; ycash6 `:116-124`) that `sendrawtransaction`s the spend **without** `generate`. (i) Spend a signed unlock's fee coin F in the mempool, then call `vault_refee` at once → the new input is not F and no split spends F (inspect the split's inputs); (ii) spend a wallet coin in the mempool, then `vault_buildunlock` of a fresh vault at once → its fee inputs do not include that coin; (iii) repeat (i) via `vault_buildunlock` of a remembered build (`refunded`). Unlike the block-spend rounds (`:227-266`), these do not depend on the notifier tick: the coin is spent in the mempool the whole time, so the pre-fix code fails whenever the largest-first choice reaches the coin — make it the wallet's largest coin to force that.
- **`vault-refee-input` refusal:** a candidate spent in the mempool between pick and check (simulate by spending it from another node's relay) → refused, nothing locked or broadcast (pairs with `LOW-W4-N-5`'s refusal-branch coverage).
- Existing `vault_refee.py`, `vault_rpc.py`, `vault_bridge.py` unchanged.

## 6. Acceptance criteria

- No vault builder, `vault_refee` or a re-funding `vault_buildunlock`/`vault_buildcancel` chooses a coin spent by a mempool transaction, on both lines; one helper defines "unspent" for all of them.
- The `EligibleCoins` comment and `doc/vault-rpc.md` state the property the code has; the contract hash matches.

## 7. Risks and side effects

- None for consensus. A coin spent by a mempool transaction that is later evicted becomes eligible again on the next call — correct.
- Slightly more `mempool.cs` traffic (one map lookup per wallet coin), within the cost the wave-4 audit already accepted for `GetCoin` (row W3-N-12, Info).

## 8. Effort estimate and dependencies

- 0.25 day code, 0.5 day tests, 0.1 day docs, both lines.
- Dependencies: none hard. Land before or with `LOW-W3-N-2-W4-N-2-N-3-N-4-ycash-vault-refee-cap-lock-release.md` (its step 4 calls the helper) and `INFO-W3-V-8-01-N-3-01-N-4-ycash-acp-pinning-malleability.md` (shares it). Test additions coordinate with `LOW-W4-N-5-ycash-refee-utxo-test-fidelity.md`.
