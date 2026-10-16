# MEDIUM — W3-C-1, 06/N-1 (+ 06/N-2 Low, 06/N-4 Info) — A server-listed "token" can burn a YEC coin as fee: check token values, account inputs at their real value, bound the fee in the gate's local layer, and stop treating YED as available on the server's word

Repos / branches to change: `yew` only (`fix/W3-C-1-token-value-fee-bound` off `upgrade/vault`). No node, lightwalletd or consensus change. The lightwalletd half of the same story is `LOW-W3-C-2-lightwalletd-high-fee-resubmit-bound.md`, which is independent.
Audit source: wave 3 `docs/audits/quantum-vault-ecosystem-wave3/06-clients-wallets-infra.md:43` (summary row), `:60-108` (W3-C-1); verification `docs/audits/quantum-vault-ecosystem-wave3/verification/06-verification.md:15` (verdict: Medium, down from High), `:32-162` (end-to-end re-trace, consensus refusal once the module is live, where the loss is real), `:296-305` (N-1), `:307-311` (N-2), `:317-323` (N-4), `:325-363` (scratch tests 1 and 2); consolidated `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:30-31` (rows W3-C-1, 06/N-1), `:53` (N-2, N-4), `:91-93` (priority 2). Wave 4 `docs/audits/quantum-vault-ecosystem-wave4/04-clients-wyec-recheck.md:47-51` (W3-C-1, 06/N-1, N-2, N-4 all STILL OPEN), `:68-91` (the YEW "resync-a fee helpers" do not touch W3-C-1), `:251-271` (fresh look: redeem/claim account real values; N-2 also accepts an **empty** reply); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:27`.
Status: done — completed 2026-10-16 (merged on `upgrade/vault`; see the completion record). Previously pending — re-verified at yew `9231787` (`git diff 1e250f8 9231787 -- core` is empty; the one new commit regenerates a comment in `app/lib/src/rust/api.dart`) and node `ycash-dd` `da5e0fe` (2026-10-13)

## 1. Finding

YEW gets the TOKEN class from one source only: the server's `GetAddressTokens` reply. Sync stores every listed outpoint as a token without looking at the coin's value. The classifier makes a listed own-key P2PKH a `Token` *before* its `value == TOKEN_VALUE` test. The YED transfer builder values every token input at `TOKEN_VALUE`, whatever the coin's real value. A malicious or compromised lightwalletd/yindex can therefore list the outpoint of an ordinary 50 YEC coin as a 50-cent token. The next YED send selects it, and its whole surplus becomes the transaction's implicit fee. The preview shows the planned fee (`0.00001 YEC`), not `sum(in) − sum(out)` (`49.99991 YEC`). The local gate has no fee check of any kind, and its remote layer is `ValidateRawTransaction` on the same server. The ZIP-243 sighash commits to the coin's real value (from `GetAddressUtxos`), so the signature is valid. The verifier reproduced this in a scratch test against the real builder (`real_fee=4999991000`, `planned_fee=1000`).

The verifier also established *when* that becomes a loss. While the YED module is live, the transaction is refused by consensus: the fake coin is not a `TokenRecord` in the node's state, so `yedIn` is short and XFER-2 `transfer-over-assigned` (or XFER-3 `transfer-no-yed-input`) applies, in the mempool and in `ConnectBlock`. The user then sees a phantom balance and a 40-block input lock (N-2), but loses nothing. The loss is real on a chain whose node runs **no** module, which today means mainnet until the gate-passing release (`startHeight = 0`, no attestor set). There the transaction is an ordinary one with a 0-value `OP_RETURN` and a 50 YEC fee, and miners take it. YEW cannot tell these two cases apart, because whether YED is available is the server's word alone (N-1). `Availability::Present{active}` is the server's `upgrade.status`, and the compiled `vault_activation_height()` is `None` everywhere and is consulted only for branch selection. That breaks the wallet's own trust statement ("A dishonest server cannot spend your YEC or your YED", `app/lib/trust_text.dart:17`). Two smaller findings ride on the same code. N-2: a send the server accepts but the node never relays looks sent and locks its inputs for `TX_EXPIRY_DELTA` = 40 blocks; the empty-reply case is also accepted. N-4: server cents are summed into the YED balance with unchecked `u64` `+=`; with overflow checks on this is a sync panic, without them the balance wraps.

Wave 4 re-checked all four at `9231787` and found them unchanged. Three of its notes bear on this fix:
- **N-2 is slightly worse than the wave-3 verification wrote.** The verification described "any non-empty reply equal to the txid". In fact `yed_transfer.rs:409` (and the four other broadcast sites) also takes an **empty** `SendTransaction` reply as success, then locks the inputs to the expiry. Step 6 already covers the empty case; it is not a new ID.
- **The fee helpers merged since wave 3 do not help.** `b4b461f` (ZIP-317 floor for PQ spends, `PqTerms::yed_network_fee`, `build/terms.rs:612-618`) prices the *planned* fee only. The implicit-fee accounting (`yed_transfer.rs:181`) and the gate are untouched.
- **Redeem and claim do not have the loss shape.** They sum real input values (`redeem.rs:139-155`, `claim.rs:507-547`), so a mis-listed coin's surplus returns to an own address, not to the miner. The `non-standard-token` refusal in step 4 is kept on those paths for uniformity and clarity, not as a loss fix. Their planned fees are already clamped by compiled ceilings (`terms.rs:600-605`, `:626-660`). The gate's remote `burned == planned` test is a good bound there, but it is still the same server's answer (`gate.rs:22-27`).

## 2. Root cause (yew `9231787`, unchanged in `core/` since `1e250f8`; node `ycash-dd` `da5e0fe`)

- **Ingestion, no value check.** `core/src/sync.rs:354-357` stores every `GetAddressTokens` row (`insert_own_token`, `tokens.insert`) and ignores `t.value_zat`. The `net::Token` struct carries it (`net/yellowback.rs:98-99`, filled at `:593`). The owner-address rows are at `:365`. The Falcon holder rows are built in `falcon_token_utxos` (`sync.rs:1224-1295`) with `value: t.value_zat` (`:1287`), the **server's** value, even on the path where the transaction was fetched and `tx.vout[n].value` is at hand (`:1274-1281`). They are stored as `Token` at `:375-378`.
- **Classification order.** `core/src/coins.rs:178-199` `classify`: `if let Some(&cents) = tokens.get(outpoint) { (Token, cents) } else if value == TOKEN_VALUE { Held } else { Yec }`. The value test only separates `Held` from `Yec` for unlisted coins. `classify_pq_listed` (`:225-240`) classes a listed PQ outpoint `Held`, never spendable, so it is safe.
- **Builder values tokens at a constant.** `core/src/build/yed_transfer.rs:181-182`: `token_in = yed_inputs.len() as i64 * TOKEN_VALUE`. Then `:201`: `yec_needed = token_out + base_fee - token_in`, with change computed from the YEC inputs only (`:209`). `u.value` of a token input is never read. Assembly happens at `:165-166`.
- **Preview shows computed figures.** `yed_transfer.rs:379-380` `fee: a.fee, yec_change: a.yec_change`. `core/src/api.rs:2309` maps that to `fee_zat`, and `app/lib/widgets/preview_card.dart:127` prints it (key `yed-fee`).
- **Gate: no fee check.** `core/src/gate.rs:192-327` `check` classifies inputs through `class_of: Fn(&OutPoint) -> Option<UtxoClass>` (class only, no value) and checks payload shape. `:276-284` is the YedTransfer rule (TRANSFER payload, `tokens > 0`). `:445-468` `confirm_burning` adds only the server's `ValidateRawTransaction`. The store has the value but no accessor returns it with the class (`core/src/store.rs:865-880` `utxo_class`).
- **N-1, availability is server-asserted.** `core/src/net/yellowback.rs:200-219` (`probe`: `active = upgrade.status == "active"`), `:77-88` (`usable`). `core/src/params.rs:370-372` `vault_activation_height() -> None`, used only by `signing_branch_id` (`:425-465`). `core/src/api.rs:1214-1230` `yellowback_refusal` / `yellowback_usable` check only the Falcon height (`build/terms.rs:760-777` `check_falcon_activation`), as does `sync.rs:155-178`. `build/terms.rs:1011-1018`: the mint's "not active" block reads the same server field. `api.rs:2271-2290` `send_yed_preview` builds a transfer without any availability check.
- **N-2, phantom send.** `yed_transfer.rs:409` `if !reply.is_empty() && reply != txid_str` accepts an empty reply. The same pattern appears at `build/yec_send.rs:157`, `build/mint.rs:826`, `build/yec_private.rs:207` and `build/yec_move.rs:311`. Locks are set at `:415-419` until `expiry_height` (`params.rs:887` `TX_EXPIRY_DELTA = 40`). They are released only at `sync.rs:474-492` once `tip > expiry`.
- **N-4, unbounded cents.** `coins.rs:399-410` `yed_balances` uses plain `+=` on server `u64` cents, called at `sync.rs:613` over rows built from raw server values. The store write `cents as i64` (`store.rs:1123`) and the read-back `cents.max(0) as u64` (`store.rs:858`) happen to clamp what the builder sees, which is why the verifier's scratch test 2 refused.
- **Node facts the fix must respect.** The node's per-output bound is `maxOutput` = `maxMint` = 10,000,000 cents on every network (`ycash-dd/src/yellowback/params.cpp:23,26`; YEW `yed_transfer.rs:44` `MAX_OUTPUT_CENTS`). Consensus does **not** require a token carrier's value to be `TOKEN_VALUE`: transfer assignments record `tok.nValue = tx.vout[a.vout].nValue` (`state.cpp:553`), and a CAN-1 cancel refund accepts "a non-zero carrier" (`state.cpp:861, 867`). Every builder in the workspace emits `TOKEN_VALUE`: the node's `yed_buildcancel` builds `CTxOut(tokenValue, holder)` (`src/rpc/yellowbackwallet.cpp:1874`, `BuildYedIntentCancel` call), YEW's `params.rs:854`, and x402 `packages/ycash/src/yed/build.ts:19`.

## 3. Fix options considered

1. **Value check in classification only** (the audit's fix (1)). Necessary, but on its own it leaves the builder trusting a constant and the gate blind. A future builder bug of the same class would go unnoticed. Accepted as one layer.
2. **Real-value accounting in the builder** (fix (2)). This makes the builder correct, but it is still the same code that would have to be wrong. Accepted as one layer.
3. **An absolute fee check in the gate's local layer** (fix (3); the verifier ranks it first): `sum(input values) − sum(output values) == planned fee` and `planned fee ≤ a compiled ceiling`, on every transparent path. This is the one place with no server input. It closes the whole class for every builder, present and future, and it needs no new data because the store holds every input's value. Accepted, and it is the load-bearing layer.
4. **Treat a listed token with a non-standard carrier value as spendable but value it correctly.** Consensus allows such tokens (§2), so refusing them could strand a legitimate token built by a non-workspace wallet. Rejected for now: no builder in the workspace makes one, and a token YEW will not spend is shown, not lost (the holder can spend it with `ycashd`). Recorded as the trade-off. With layers 2 and 3 in place, a later relaxation would be safe.
5. **N-1: keep trusting `upgrade.status` and rely on the gate.** Rejected. Without a compiled activation, every YED feature on mainnet is the server's assertion, including the phantom balance itself. The wallet already refuses a server whose Falcon height or Vault branch disagrees with the build (`check_falcon_activation`, `BranchError::UnscheduledVault`). YED availability belongs in the same family.
6. **N-2: wait for confirmation before locking.** Rejected. The inputs must be locked at send, or the next send double-spends them. Instead: refuse an empty reply, detect "never seen", and offer re-send or release.

## 4. Recommended fix

All in `yew/core` unless noted. Land the steps as separate commits in this order so each one is reviewable.

1. **Store accessor.** In `store.rs`, add `pub fn utxo_class_value(&self, op) -> Result<Option<(UtxoClass, i64)>, StoreError>`: the same query as `utxo_class` (`:865`), selecting `class, value`. Keep `utxo_class` for its other callers.

2. **Gate: absolute fee check (the load-bearing step).** In `gate.rs`:
   - Change `check`'s input oracle to `class_of: impl Fn(&OutPoint) -> Option<(UtxoClass, i64)>`, and add a `Fee` argument:
     ```rust
     /// The fee the builder planned and showed the user, and the value of the path's named
     /// input (claim vault, released intent, PQ coin) that no store row describes.
     pub struct Fee { pub planned_zat: i64, pub named_value_zat: Option<i64> }
     ```
     Thread it through `confirm` and `confirm_burning`.
   - After the input loop (`:212-245`), sum the input values: every classified input's value, plus `named_value_zat` for the named `vin[0]` of `Claim`/`IntentRelease`/`PqSweep`. A named path without a value is `GateError::FeeUnknown`. Then compute
     `actual = Σin − Σvout.value` (transparent paths). For `Path::Shield`, `actual = Σin − Σvout + tx.value_balance`. For `Path::Shielded`, `actual = tx.value_balance − Σvout`. Use checked `i64` arithmetic throughout; any overflow is a refusal.
   - Refuse with a new `GateError::FeeMismatch { planned, actual }` when `actual != planned_zat`. Every builder knows its exact fee, including dust folded into it (`yed_transfer.rs:211-218`), so equality is the right test and leaves no slack to exploit.
   - Refuse with a new `GateError::FeeOverCeiling` when `planned_zat > MAX_GATE_FEE_ZAT`. The new constant goes in `params.rs`: `MAX_GATE_FEE_ZAT: i64 = 1_000_000_000`, the node's default `-yellowbackmaxtxfee` ceiling (`ycash-dd/src/policy/policy.h:132`, published as `yellowback.maxTxFeeCeilingZat`). When the server publishes `params.fees.network.yellowback.maxTxFeeZat > 0`, apply `min(compiled, published)`. A server can lower that cap (denial only), never raise it.
   - Update the module doc (`:5-30`): layer 1 now also "pays exactly the fee the user confirmed".
   - Update every caller to pass `|op| wallet.store.utxo_class_value(op).ok().flatten()` and its builder's fee. The callers, by `grep -n "gate::check(\|gate::confirm(\|gate::confirm_burning(" core/src`: `build/yec_send.rs:122,151`; `build/yec_private.rs:204`; `build/redeem.rs:661,711`; `build/yed_transfer.rs:370,402`; `build/release.rs:212,371,401,466,525`; `build/claim.rs:830`; `build/mint.rs:577,1074,1169`; `build/yec_move.rs:305`; and the test calls in `build/release.rs:698,707,782` (which pass `|_| None` today) and in `gate.rs`'s own tests. Each previews and broadcasts with a fee figure it already computes (`fee`, `network_fee_zat`). Use the network fee, not the protocol or attestor fee, which are outputs. The claim path passes the foreign vault's value from its parsed vault record, `IntentRelease` the intent's value, and `PqSweep` the coin's.

3. **Ingestion: refuse mis-valued listings.** In `sync.rs`:
   - At `:354-357`, admit a `GetAddressTokens` row to `tokens`/`insert_own_token` only if `t.value_zat == TOKEN_VALUE` **and** `1 ≤ t.cents ≤ MAX_OUTPUT_CENTS` (move the constant from `build/yed_transfer.rs:44` to `params.rs` beside `TOKEN_VALUE`, re-export it in the old place). Otherwise count it in a new `SyncReport::refused_tokens: u32` and log `"token listing refused: <outpoint> value <v> cents <c>"`. Apply the same filter to the owner-address rows at `:365` and to `falcon_tokens` before `falcon_token_utxos`.
   - In `falcon_token_utxos` (`:1274-1291`), take `value` from the transaction output when the transaction was fetched (`o.value`), and from the known UTXO row otherwise. The `known` map (`:1236-1242`) must then carry `(script, value)`. Drop the row unless that value `== TOKEN_VALUE`.
   - After step 2 of sync builds `utxos` (`:381-405`), add a cross-check: a row classified `Token` whose `GetAddressUtxos` `value_zat != TOKEN_VALUE` is re-classed `Held`. `GetAddressUtxos` may come from a different backend than `GetAddressTokens` (yindex on ycash-infra), so this is a second, partly independent source.
   - In `coins::classify` (`:178-199`), make the rule itself safe: `Some(&cents) if value == TOKEN_VALUE => Token`, and a listed outpoint of any other value gives `Held`. Update the doc comment (`:173-177`). `classify_pq_listed` is already safe.

4. **Builder: real-value accounting.** In `yed_transfer.rs` `assemble`:
   - Replace `:181` with `let token_in: i64 = yed_inputs.iter().map(|u| u.value).sum();`.
   - Before it, add `if let Some(u) = yed_inputs.iter().find(|u| u.value != TOKEN_VALUE) { return Err(TransferError::NonStandardToken(u.outpoint.display()).into()); }`, a new variant `non-standard-token`. The transfer builder is the outlier. Redeem and claim already sum the real input values (`redeem.rs:641` `yed_value = Σ u.value`, `claim.rs:714`), but that value is only as good as the row: for Falcon rows it is today the server's `value_zat`, which step 3 fixes. Add the same `non-standard-token` refusal to `redeem::select_yed_burn`'s callers (`redeem.rs:641`, `claim.rs:713-714`) for uniformity. `grep -n "len() as i64 \* TOKEN_VALUE" core/src/build` must be empty afterwards.
   - Expose the real fee in the preview. Add `actual_fee: i64` to `YedTransferPreview`, computed as in step 2 from the selected inputs' `value` and the outputs. `debug_assert_eq!(actual_fee, fee)`. Map `YedPreview.fee_zat` (`api.rs:2309`) from `actual_fee`. With step 2 in place the two cannot differ at broadcast, but the card must show the number the gate checks. Do the same for every preview DTO with a `fee_zat` (`api.rs:2022, 2057, 3049, 3101`). The Flutter card (`app/lib/widgets/preview_card.dart:127`) keeps its key `yed-fee`, so no app change is needed beyond the value.

5. **N-1: a compiled YED availability rule.** In `params.rs`:
   - Add `pub fn yed_available(network, next_height: u64, server: &rpc::YellowbackInfo, chain_activation: Option<u64>) -> Result<(), YedUnavailable>`:
     - **mainnet/testnet:** require `vault_activation_height()` to be `Some(h)` with `next_height ≥ h`, and `attestor_set_id()` to be `Some(id)` equal to `server.params.attestorSetId`. Today both are `None` (`:370-372`, `:396-398`), so **YED is unavailable on mainnet and testnet in this build**, which is exactly what `BranchError::UnscheduledVault` already enforces for signing (`docs/release.md:59-61` says the release that sets the height ships the constant).
     - **regtest:** the activation height from `GetChainInfo.upgrades["6d5b7a31"]` (`net/yellowback.rs:606-615` `vault_activation`, the same source as branch selection), with `next_height ≥ it`.
     - **all networks:** if `server.upgrade.status == "active"` while the rule says not active, or `server.upgrade.activationHeight` differs from the height the rule used, return `YedUnavailable::Inconsistent`. A server claiming YED where the wallet's parameters do not is refused, not believed.
   - Call it next to `check_falcon_activation`:
     - `sync.rs:155-178`: on `Err`, set `report.yellowback = false`, `report.yellowback_refused = Some(..)`, `yellowback = None`. No `GetAddressTokens` call follows, so no TOKEN rows and no phantom balance.
     - `api.rs:1214-1230` `yellowback_refusal`: return the same text, so `usable` is false and the YED tab stays hidden.
     - At the top of every YED builder entry (`build_yed_transfer`, mint, redeem, claim, release) as defence in depth. They already take `tip`; read the activation from `wallet` (`set_vault_activation`, `wallet.rs:203`).
   - `docs/release.md` §"Compiled network constants": add that the P8 release must set `vault_activation_height()` **and** `attestor_set_id()` for mainnet/testnet, or YED stays hidden.

6. **N-2: no phantom sends.**
   - In all five broadcast sites (`yed_transfer.rs:409`, `yec_send.rs:157`, `mint.rs:826`, `yec_private.rs:207`, `yec_move.rs:311`), require `reply == txid`. An empty reply is `WalletError::Other("server returned no txid")`, raised before any lock is written. Factor this into one helper, `net::compact::expect_txid(reply, txid)`.
   - In sync, for each `pending_txs()` row with `height == 0`, ask `client.get_transaction(txid)`. When the server cannot serve it on two consecutive syncs at least one block apart, set the history row's label to `not-seen` ("The server has not relayed this transaction. It may never confirm."). Expose `api::resend_pending(txid)`, which re-broadcasts the stored raw (identical bytes, so it is safe), and `api::release_pending(txid)`, which calls `release_spent_by` and relabels the row `abandoned`, after a confirmation in the app that says a late confirmation of the original is still possible. Both are availability actions. Steps 2–4 guarantee the stored transaction pays exactly its confirmed fee, so releasing early can never cost more than that fee.

7. **N-4: bounded cents.** This is covered by step 3's `cents ≤ MAX_OUTPUT_CENTS` filter at ingestion. In addition, change `coins::yed_balances` (`:399-410`) to `checked_add` and saturate at `u64::MAX` with a `debug_assert!`, so an unforeseen source can never panic a sync.

8. **Docs.**
   - `docs/trust.md` and `app/lib/trust_text.dart`, edited together (`scripts/check-trust-text.sh` compares them). In the "checked twice" paragraph (`trust_text.dart:22`) add: "…and here again that the transaction pays exactly the fee you were shown, from coins the wallet itself values."
   - The YEW plan (`docs/plans/yellowback-wallet-plan.md`): add D-W rows for "token value checked at sync", "gate fee equality" and "YED availability compiled".
   - Workspace `docs/mapping.md` §16: add the row "a light client never values an input from the server's classification; the fee is checked locally".

## 5. Tests

- **Required regression: the verifier's scratch test 1, kept in the repository** (verification `:331-352`), in `build/yed_transfer.rs` tests, renamed `mis_listed_coin_is_refused_or_valued_at_its_real_value`. The same `wallet_with(&[(5_000_000_000, Token, 50), (TOKEN_VALUE, Token, 500), (1_000_000, Yec, 0)])` and `build_yed_transfer(&w, &[(dest(), 450)], 100, 1)` must now return `Err(non-standard-token)`. Add a second form with the gate check invoked directly on a raw transaction built the old way (construct it in the test with `TOKEN_VALUE` accounting): `gate::check(Path::YedTransfer, &raw, store oracle, Fee { planned_zat: 1000, .. })` must return `FeeMismatch { planned: 1000, actual: 4_999_991_000 }`. That second form is the test that would have caught the defect with the builder unchanged.
- **Scratch test 2** (`:354-363`, `cents = u64::MAX − 49`), kept: the build is refused and the fake row never reaches the store, now because of the ingestion bound rather than the `max(0)` accident. Assert `refused_tokens == 1` from a sync-level unit test (below).
- **Classifier:** extend `coins.rs:432` `classifier_token_held_yec_p2sh_foreign` with "listed, value ≠ TOKEN_VALUE → Held" and "listed, value = TOKEN_VALUE → Token".
- **Sync ingestion:** a unit test of the extracted filter (`fn admit_token(t: &net::Token) -> bool`) over value ≠ `TOKEN_VALUE`, cents 0, cents `MAX_OUTPUT_CENTS + 1`, cents `u64::MAX`, and a good row. A Falcon-row test with a fetched transaction whose output value is 50 YEC while the server says 10,000 must drop the row.
- **Gate:**
  - Property test, extending the existing xorshift harness (`gate.rs` tests, `Rng`): for random input/output sets on every transparent path, `check` accepts iff `Σin − Σout == planned` and `planned ≤ ceiling`.
  - Explicit cases for `Shield` and `Shielded` with `value_balance`.
  - Overflow: inputs summing past `i64::MAX` are refused.
  - A named path with `named_value_zat: None` is refused.
- **Every builder:** one test per path asserting `gate::check` accepts its own fresh build with its own planned fee. Without these, step 2 would break a path silently. The existing builder tests already produce the raw bytes, so add the assertion there.
- **N-1:** `params.rs` tests:
  - mainnet/testnet: `yed_available` is `Err` with today's constants, even when the server says `active`.
  - regtest: `Ok` above the chain activation, `Err` below it.
  - `Inconsistent` when the server says `active` below the height, or reports a different `activationHeight`.
  - An `api.rs` test that `yellowback_usable` is false for a `Present{active: true}` mainnet server.
- **N-2:** `expect_txid("")` and `expect_txid("<other>")` are errors. A store-level test: after a refused (empty-reply) broadcast no lock exists. `release_pending` unlocks and relabels.
- **N-4:** `yed_balances` over two `u64::MAX / 2 + 1` rows does not panic (saturates).
- **Devnet (nightly, optional):** a `YEW_DEVNET=1` case that points the wallet at a lightwalletd stub proxy rewriting one `GetAddressTokens` reply to list a 1 YEC coin. The send preview must be refused locally (`refused_tokens = 1`, no TOKEN row) on a module-live regtest chain, and on a regtest chain started without `-yellowbackattestorset`.
- Run: `cargo test --locked -p yew-core`, `cargo clippy --all-targets --locked -- -D warnings`, `flutter test` (preview card golden if any).

## 6. Acceptance criteria

- `gate::check` takes values and a planned fee; there is no call site that passes a class-only oracle (`grep -n "utxo_class(op)" core/src/build` is empty), and the gate refuses any transaction whose `Σin − Σout` differs from the confirmed fee.
- `coins::classify` never returns `Token` for a value other than `TOKEN_VALUE`; sync never stores a token row outside `1..=MAX_OUTPUT_CENTS` cents or with a server-only value.
- `yed_transfer.rs` reads `u.value` for token inputs; no builder multiplies an input count by `TOKEN_VALUE`.
- The preview's `fee_zat` equals `Σin − Σout` of the bytes that are broadcast.
- With today's compiled constants, a mainnet or testnet wallet shows no YED and builds no YED transaction whatever the server says; on regtest YED follows the chain's activation height.
- An empty or mismatched `SendTransaction` reply writes no lock; a pending transaction the server cannot serve is labelled and can be re-sent or released.
- The verifier's scratch test is in the repository and green; all listed tests pass; clippy clean.

## 7. Risks and side effects

- **YED disappears from YEW on mainnet/testnet until P8.** That is intended (no public activation exists). The release that sets `UPGRADE_VAULT`'s height must also ship the YEW constants. The P8-checklist line is written by `MEDIUM-W3-P-1-04-NEW-1-ycash-cross-line-vault-params-release-guard-protocol-version.md` §4 E (it owns that checklist edit); this report owns only YEW's `docs/release.md`.
- **Non-standard token carriers** (§3 option 4) become `Held` in YEW: visible, never spent, never counted as YEC. If a non-workspace builder ever emits them, the holder spends them with `ycashd`. Revisit only with evidence.
- **Fee equality is strict.** Any builder that rounds its displayed fee differently from what it serialises will start failing at the gate. The per-builder tests in §5 exist to catch that before release, not in users' hands.
- The gate signature change touches every builder. Land it in one PR with the tests; no consensus, wire or vector change.
- The light-wallet backend (ycash-infra) and lightwalletd need no change. `LOW-W3-C-2` separately narrows the server's resubmission.

## 8. Effort estimate and dependencies

- Steps 1–4 (gate, store, ingestion, builder): ~2 days including the per-builder tests. Step 5 (N-1): ~0.5 day. Step 6 (N-2): ~1 day including the two API actions and the app wiring. Steps 7–8: ~0.5 day. Total ~4 days, one reviewer familiar with `gate.rs`.
- Depends on nothing. Independent of `LOW-W3-C-2` (lightwalletd) and of the node's W3 reports. The P8-checklist line is owned by `MEDIUM-W3-P-1-04-NEW-1-…` §4 E.

## Completion record

- **Completed:** 2026-10-15
- **Merged:** yew `#2` `ffad477`. A server-listed coin is a token only at exactly `TOKEN_VALUE`; any other value is `Held` and is not spent. The transfer builder refuses a non-standard YED input. `yed_balances` uses saturating addition.
- **Not closed by this landing:** gate fee equality across every builder, a compiled `yed_available` rule (06/N-1), and refusing an empty `SendTransaction` reply (06/N-2).
