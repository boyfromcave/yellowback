# YDollar v1 — Development Plan

**Status:** DECIDED — revision 12. Revisions 3–6 were re-audited claim-by-claim against the
pinned trees and the code paths in `ycash-dd` that every rule, hook and RPC depends on (validation
interface, init and shutdown, wallet spend tracking, coin selection, rebroadcast and encryption,
raw-transaction and multisig RPCs, transaction lookup, policy, script interpreter, coins view,
mempool limiter and expiry, chain parameters, DB wrapper, build layout, unit-test and functional
test harnesses); §0 lists what each audit changed. This document resolves every `**OPEN**` item in
[`../spec/ydollar-adaptation-spec.md`](../spec/ydollar-adaptation-spec.md) and is the plan to
follow to ship a working YDollar on Ycash in `ycash-dd/`.

**Pins this plan was written against** (verify with `make status` before trusting any line cite):

| Repo | Pin | Commit |
|---|---|---|
| `ref/digibyte` | tag `v9.26.5` | `05b50e229d` |
| `ref/ycash` | tag `v4.5.0` | `624c12814` |
| `ycash-dd` | branch `feature/digidollar` off `ycash-legacy` (= `v4.5.0`) | `624c12814` |
| `ref/yecwallet` | tag `v4.5.0` (YecWallet, the Qt 6 full-node GUI that bundles `ycashd`) | `1eb277d` |
| `yecwallet-dd` | branch `feature/digidollar` off `yecwallet-legacy` (= `v4.5.0`) | `1eb277d` |

**How to use this document.** §1 is the decision in one page. §2 is the decision record (every
option weighed, what was chosen, what it costs). §3 is the normative protocol. §4 is the code
architecture inside `ycash-dd`. §5 is the federation coordinator. §6 is the phased work plan with
exit criteria; **§6.0 is how one developer builds and tests the whole multi-operator system on one
machine, and how CI runs it.** **§4.7 is the user interface: what users see, which application it
lives in, and the RPC contract it is built on.** §7 is the test plan. §8 is the trust statement and threat model. §9 is the later
consensus-enshrinement path. §10 lists deviations from DigiDollar. §11 lists the launch inputs
that only operators can supply. Implementers start at §6 and refer back.

---

## 0. Audit log (revision 2)

Revision 1 was audited claim-by-claim against the pinned trees. Every line cite was re-read.
Findings and the resulting changes, so a reviewer can see what moved and why:

| # | Finding | Severity | Change |
|---|---|---|---|
| A1 | Revision 1 put an `evhttp` client and an `AsyncRPCOperation` inside `ycashd` for redemption co-signing: outbound plaintext HTTP from the node, ≈ 250 new C++ lines, and a new failure surface in the wallet process. | design | **Removed.** `ycashd` does no outbound networking. `yd_redeem` returns the owner-signed hex; a Python client in `contrib/ydollar/` collects co-signatures over HTTPS; `yd_submitredeem` verifies and broadcasts. (D16) |
| A2 | PRICE-1 required the anchor at `vin[0]`; an anchor spent at any other input index would silently break custody. | rule | Anchor spend detected at any input index. (§3.7) |
| A3 | XFER-2 burned *all* inputs when a TRANSFER under-assigned; DigiByte rejects such a tx at consensus, so its users lose nothing, whereas an overlay "reject" is a burn. | user-loss | Assignments with `Σ ≤ ydIn` are honoured and only the remainder burns; `Σ > ydIn` assigns nothing. (§3.7) |
| A4 | Transactions with two `OP_RETURN` outputs are non-standard but consensus-valid (a miner can include one); rule was unstated. | determinism | Explicit: more than one `OP_RETURN` ⇒ non-YDollar. (§3.2) |
| A5 | RED-5 asked co-signers to check where collateral goes; unnecessary (the owner's `SIGHASH_ALL` signature already commits to every output) and unverifiable (co-signers do not know the owner's address). | precision | Dropped. Replaced by RED-6 (price defined), RED-7 (owner signature verifies), RED-8 (expiry bound), and SUB-1 (owner's node re-verifies the returned transaction). (§3.8) |
| A6 | Redemptions during an oracle outage: `health = 0` ⇒ `errBps = 8000` ⇒ 125 % burn demanded of users because the oracle failed. | user-loss | RED-6: co-signers refuse while `price(indexTip)` is undefined — pause, never guess (DigiDollar's own fail-closed rule). |
| A7 | `ThreadNotifyWallets` fires once per second (`ref/ycash/src/validationinterface.cpp:92-96`), not "milliseconds"; under `-reindex` it starts from genesis (`:77-88`); it reads blocks from disk so `-prune` would break a rebuild. | accuracy | D7 corrected; `-ydollar` refuses `-prune`; `yd_getinfo.synced`; test helper waits on the index height. |
| A8 | Claimed the index must register after the wallet so wallet updates precede coin locking. Not needed: `IsMine` and `LockCoin` depend only on keys and `cs_wallet`. | precision | Dependency removed. (§4.3) |
| A9 | Revealed roster scripts were appended without requiring that they parse as `k-of-n CHECKMULTISIG`. | rule | Only parseable multisig scripts become rosters; anchor custody still moves. (§3.7) |
| A10 | Ycash transparent keys are a random keypool, not HD (`CWallet::GenerateNewKey`, HD seed is Sapling-only in 4.5). A vault owner key lives only in `wallet.dat`. | operational | One fresh key per mint for both token output and owner; documented backup rule; `yd_mint` warns when the keypool is low. (§4.5) |
| A11 | Genesis anchor / roster script consistency was assumed. | safety | Startup check: read the genesis block from disk and assert `HASH160(genesisRosterScript)` equals the anchor's `scriptPubKey`; otherwise refuse to enable. (§4.3) |
| A12 | A fully co-signed redemption could be held and broadcast later under different health. | policy | RED-8: `nExpiryHeight ≤ indexTip + 40`, so a held transaction dies within the same window the wallet's own mint uses. |
| A13 | Undo records grow without bound. | operational | Undo pruned below `tip − 20,000`; deeper reorgs trigger a rebuild. (§4.3) |
| A14 | Standardness constraints on the vault spend (`MINIMALDATA`, `CLEANSTACK`, `LOW_S`, `AreInputsStandard` treatment of non-template P2SH subscripts) were implied, not stated. | precision | Stated with cites; `AreInputsStandard` accepts any subscript with ≤ 15 accurate sigops (`ref/ycash/src/policy/policy.cpp:170-178`). (§3.3) |
| A15 | `signrawtransaction` for anchor spends needs `prevtxs` with `amount` and `redeemScript` (ZIP-243 sighash commits to the input value) because a k-of-n script is not "mine" to the wallet. | feasibility | Coordinator supplies `prevtxs` from `gettxout` (no `txindex` needed). (§5) |
| A16 | Thin YEC markets make the price feed manipulable by small trades. | risk | Coordinator brakes: ≥ 3 sources, 10 % outlier filter, per-round move clamp ± 10 %, 5-minute TWAP per source. (§5) |

Everything else in revision 1 survived the audit unchanged: the Tier-0 choice, the vault script
and the no-fallback rule, the anchor-chain oracle, ECDSA-only cryptography, the `ChainTip` index,
the rebuildable LevelDB, the manual transaction builder, and the diff budget (now smaller).

### Revision 3 audit

Revision 2 was checked against the actual code paths in `ycash-dd` (= `ref/ycash` at v4.5.0)
that each rule or hook depends on, not only against the cited lines. Four findings are
feasibility or user-loss defects (B1–B4); the rest are precision and simplification.

| # | Finding | Severity | Change |
|---|---|---|---|
| B1 | §5 had the coordinator build PRICE transactions with `createrawtransaction` carrying an `OP_RETURN`. Ycash's `createrawtransaction` accepts only `{"address": amount}` outputs — there is no `"data"` output (`ref/ycash/src/rpc/rawtransaction.cpp:539-620`). | **feasibility** | New node RPC `yd_createpricetx` builds the unsigned PRICE/ROSTER transaction (anchor input, optional refill, anchor output, `OP_RETURN`) with `CreateNewContextualCMutableTransaction`; the coordinator only signs (`signrawtransaction`) and broadcasts. No Python transaction serialiser. (§4.4, §5) |
| B2 | A15 said the coordinator supplies `redeemScript` in `prevtxs`. `signrawtransaction` adds a `prevtxs` redeem script to its keystore **only when private keys are passed in** (`fGivenKeys`, `rawtransaction.cpp:966-974`); when signing with the wallet, the P2SH redeem script must already be in `wallet.dat`. | **feasibility** | Every operator runs `addmultisigaddress k [sorted keys]` once — it stores the script via `AddCScript` (`ref/ycash/src/wallet/rpcwallet.cpp:1175`) — and the coordinator asserts the returned address equals `yd_getroster`. `prevtxs` (with `amount`) is needed only when the anchor being spent is unconfirmed; confirmed anchors are read from `pcoinsTip` (`rawtransaction.cpp:906-921`). (§4.6, §5) |
| B3 | MINT-4/5 were evaluated at the **confirmation** height with `price(H)` and `dcaBps(health(H))`. A price fall of more than the 2 % margin, or a DCA step (health crossing 150/120/110 %), inside the 40-block window voids the mint and locks the collateral for the **whole tier** (up to one year) with no YDollar created. That is the worst user-loss path in the design and it is triggered by ordinary volatility. | **user-loss** | The MINT payload commits an `evalHeight`; MINT-4/5 are evaluated against `Snapshots[evalHeight]` (price, health, DCA, freeze), which every node has for every block ≥ `startHeight`, with `H − MINT_WINDOW ≤ evalHeight ≤ H`. The wallet therefore knows the exact collateral requirement before it signs; the 2 % margin is removed; the only remaining void causes are the supply cap (MINT-6) and a reorg that changes the snapshot at `evalHeight`. (§3.2, §3.7, §3.8) |
| B4 | Coin locking ran only after a block was applied. A wallet's own 0-conf outputs are *trusted* and spendable by `sendtoaddress`/`z_sendmany` at once (`CWalletTx::IsTrusted`, `ref/ycash/src/wallet/wallet.cpp:4842-4867`), so a `sendtoaddress` issued right after `yd_mint`/`yd_send` could burn the fresh YDollar. YDollar received in a block is spendable between `SyncTransaction` and `ChainTip` of the same notifier cycle (`validationinterface.cpp:213-217`). | **user-loss** | Three-stage locking: (i) `yd_mint`/`yd_send`/`yd_redeem` lock their own YDollar outputs **before** `CommitTransaction`; (ii) the index's `SyncTransaction` override pre-locks every output a well-formed payload assigns to a script that is mine, for mempool and block transactions alike; (iii) `ChainTip` reconciles against the state. Over-locking a VOID mint's token output is undone at (iii). (§4.3, §4.5) |
| B5 | Regtest sets `fRequireStandard = false` (`ref/ycash/src/chainparams.cpp:671`) and Ycash has no `-acceptnonstdtxn`. `IsStandardTx` and `AreInputsStandard` are therefore **never executed** in functional tests (`main.cpp:1558,1646`); §3.3's relay constraints were "pinned" by tests that cannot see them. | test gap | Boost unit tests call `IsStandardTx` and `AreInputsStandard` directly on every transaction template (mint, transfer, redeem with k = n = 13, PRICE with refill), and `VerifyScript` under `STANDARD_SCRIPT_VERIFY_FLAGS`. Functional tests still verify the flows end to end. (§7) |
| B6 | `qa/rpc-tests/test_framework/util.py:40-42` defines Blossom/Heartwood/Canopy branch IDs with **Zcash's** values (`0x2BB40E60`, `0xF5B9230B`, `0xE9FF75A6`); Ycash's are `0x8e471bd6`, `0x66314da3`, `0x19bd2d2f` (`ref/ycash/src/consensus/upgrades.cpp`), and `-nuparams` rejects unknown IDs (`init.cpp:1212-1246`). The inherited post-Blossom functional tests cannot start on Ycash, and Ycash's CI runs none of them (`.github/workflows/` holds only `book.yml`). The cached regtest chain activates only Overwinter and Sapling (`util.py:266-267`). | test gap | `ydollar_util.py` defines the Ycash IDs and starts nodes with Ycash, Blossom, Heartwood and Canopy active from height 1 (regtest keeps Equihash 48/5 regardless, `chainparams.cpp:860-863`) using `setup_clean_chain = True`. Phase 0 records the baseline test run and adds a fork-local CI job for `rpc-tests.py`. (§6, §7) |
| B7 | PRICE-3 claimed "the chain prevents two anchor spends in one block". Two PRICE transactions can chain inside one block (the second spends the first's new anchor). | determinism | `Prices[H]` is the price of the **last** valid anchor spend in block order. (§3.7) |
| B8 | A PRICE transaction that (accidentally) paid the new anchor to a different P2SH moved custody *and* recorded a price under a roster nobody had revealed. | safety | Custody follows `vout[0]` as before, but a price is recorded only if `vout[0].scriptPubKey` equals the spent anchor's `scriptPubKey`; a change of script is a rotation whatever the payload says. Roster reveal is unchanged. (§3.7) |
| B9 | A11's genesis-anchor check read block `startHeight` from disk at init; a freshly syncing node does not have it yet. | precision | The check runs inside `ApplyBlock` at `H == startHeight` (the anchor transaction must be in that block) and marks the index unhealthy on mismatch; init runs it only when the block is already on disk. (§4.3) |
| B10 | Undo records kept for 20,000 blocks. Ycash shuts down rather than reorg more than `MAX_REORG_LENGTH = 99` blocks (`ref/ycash/src/main.h:62`, `main.cpp:3772`); only `RewindBlockIndex` at startup (`init.cpp:1695`) can move the tip further, and the rebuild fallback already covers that. | simplification | Keep 1,000 undo records; anything deeper wipes and rebuilds. (§4.3) |
| B11 | `cents` as `CompactSize` tied the payload to `ReadCompactSize`'s canonical-encoding rules and its `MAX_SIZE` ceiling of 33,554,432 (`ref/ycash/src/serialize.h:292-315`). | precision | Fixed-width `u32le` everywhere: no canonical-form question, no serializer coupling; MINT body 46 B, TRANSFER up to 15 assignments. (§3.2) |
| B12 | `Solver` classifies any `OP_RETURN` followed by *any* push-only sequence as `TX_NULL_DATA` (`ref/ycash/src/script/standard.cpp:102`); the payload shape was under-specified. | determinism | The payload is the single data push that follows `OP_RETURN`; any other shape is non-YDollar. (§3.2) |
| B13 | D3's script-size bound: with a 3-byte height push the vault script is `44 + 34n ≤ 520` ⇒ `n ≤ 14`, and sigops allow `n ≤ 14` too; heights above 8,388,607 need a 4-byte push ⇒ `n ≤ 13`. | precision | Stated; the roster bound stays `n ≤ 13` so the arithmetic never depends on the height. (D3) |
| B14 | The builder hand-set `nVersion`/`nVersionGroupId`/`nExpiryHeight` and ran a `GetMinimumFee` loop. Ycash already has `CreateNewContextualCMutableTransaction(consensus, nextHeight)` (`ref/ycash/src/main.cpp:7364-7392`), and every `z_*` operation uses a flat `DEFAULT_FEE = 1000` zat (`ref/ycash/src/policy/fees.h:15`). | simplification | Use both; smallest-first input selection as `AsyncRPCOperation_sendmany::find_utxos`; `-ydollarfee` overrides. Builder budget ≈ 400 lines, not 900. (D9, §4.5) |
| B15 | Lock ordering was unstated. The notifier thread must not take `cs_main` in block callbacks (`validationinterface.cpp:162-166`); `LockCoin` requires `cs_wallet` (`wallet.cpp:6265`). | safety | Order `cs_main → cs_wallet → cs_ydollar`. The `ChainTip`/`SyncTransaction` handlers take `cs_ydollar` for the state update, release it, then take `cs_wallet` for locking; they never take `cs_main`. RPCs take `LOCK2(cs_main, cs_wallet)` then `cs_ydollar`. (§4.3) |
| B16 | Signers must agree on the sighash branch ID. `rpc/atomicswap.cpp:760` uses `Height()`, `signrawtransaction` uses `Height() + 1` (`rawtransaction.cpp:1024`). | precision | Every YDollar signer uses `CurrentEpochBranchId(chainActive.Height() + 1)`; the two differ only at an upgrade boundary and none is scheduled (NU5 is `NO_ACTIVATION_HEIGHT`). (§3.3) |
| B17 | Handler behaviour below `startHeight` was implicit; the parent-hash continuity check needs a defined start. | precision | Blocks below `startHeight` are ignored entirely; at `startHeight` the parent check is skipped and the tip is set; above it the parent must equal the stored tip. (§4.3) |
| B18 | "Refuse when fewer than 2 keypool keys remain" would fail under the test framework's `-keypool=1`. | precision | `yd_mint` calls `TopUpKeyPool()` first (wallet must be unlocked) and refuses only if the pool is still short. (§4.5) |
| B19 | `yd_redeem` locks inputs but nothing unlocked them if the redemption was abandoned. | operational | `yd_abortredeem <hex>` unlocks the inputs of a redemption that was never broadcast. (§4.4) |
| B20 | Co-signers evaluated RED rules against their index without checking that it is healthy and at the chain tip. | safety | RED-0: refuse when `!synced` or unhealthy. (§3.8) |
| B21 | Old rosters remained mintable-into forever via the `Rosters[size−2]` grace. | safety | Rosters record `revealHeight`; the previous roster is accepted for MINT-3 only while `H ≤ revealHeight(back) + ROSTER_GRACE` (1,152 blocks). Existing vaults are unaffected. (§3.7, §3.9) |
| B22 | Ycash builds with `-DYCASH_WR` (`zcutil/build.sh:81-85`) add `-deletetx`, which prunes old wallet transactions from `wallet.dat` (`wallet.cpp:4112-4400`). | compatibility | It keeps any transaction with an unspent transparent output that is mine (`wallet.cpp:4336-4348`), so YDollar coins survive; the index, not the wallet, is the source of `yd_listtransactions`, so history survives too. Documented, no code. (§4.5) |
| B23 | Operator key import with `importprivkey` triggers a full rescan. | operational | `importprivkey <key> "" false`. (§4.6) |
| B24 | The redemption client's deadline was implicit. | precision | With `nExpiryHeight = indexTip + 40` and `TX_EXPIRING_SOON_THRESHOLD = 3` (`main.h:81`), a redemption must be broadcast within 36 blocks (≈ 45 min) of `yd_redeem`; the client shows the deadline and `yd_abortredeem` recovers otherwise. (§5) |

Everything else in revision 2 survived: Tier 0, the vault script and no-fallback rule, the
anchor-chain oracle, ECDSA-only cryptography, the `ChainTip` index with zero `main.cpp` lines, the
rebuildable LevelDB, D10's address bytes (re-verified by exhaustive Base58 search: `0x1FE2`→`yd`,
`0x2007`→`yt`, `0x2002`→`yr`, 35 characters), and the trust statement.

### Revision 4 audit

Every line cite in revision 3 was re-read at the pins and resolves (a handful drifted by one or
two lines and are corrected in place). D10's address bytes were re-derived independently. The
Tier-0 decision, the vault script, the anchor-chain oracle and the trust statement are unchanged.
Findings, most severe first:

| # | Finding | Severity | Change |
|---|---|---|---|
| C1 | RED-4 said co-signers run `IsStandardTx`/`AreInputsStandard` and check the fee "against a `CCoinsViewCache` populated from the index's view of the inputs". The index holds only YDollar outpoints (and no `nValue` for them); the fee needs every input's value and `AreInputsStandard` needs every input's `scriptPubKey`, including the owner's YEC inputs, which the index never sees. | **feasibility** | `yd_validaterawtransaction` and `yd_cosignredeem` hold `cs_main` and build the input view exactly as `signrawtransaction` does — `pcoinsTip` behind `CCoinsViewMemPool` (`ref/ycash/src/rpc/rawtransaction.cpp:906-921`) — which also yields the vault's value for the sighash. `Tokens` records additionally store `nValue`. (§3.5, §3.8, §4.4) |
| C2 | Regtest tests must create the genesis anchor on chain before any node can run `-ydollar`, but the plan gave regtest only `-ydollargenesisanchor` and `-ydollargenesisroster`; nothing supplied `startHeight`. | **feasibility** | `-ydollarstartheight=<h>` (regtest only). Test flow: start without `-ydollar`, fund and mine the anchor, restart with the three arguments. (§3.1, §4.4, §6) |
| C3 | Stage (iii) of B4 unlocked "the removed outpoints" on disconnect. `ThreadNotifyWallets` emits `SyncTransaction(tx, NULL, h)` identically for mempool arrivals, conflicted transactions and every transaction of a disconnected block (`ref/ycash/src/validationinterface.cpp:183,210,226`), and a disconnected transaction goes back to the mempool where its outputs are trusted 0-conf again — so unlocking on disconnect reopens exactly the hole B4 closed. | **user-loss** | Locks are never released on disconnect. A lock is released only when a *confirmed* transaction's applied verdict assigns no cents to that outpoint (a VOID mint's token output, a non-YDollar output that was pre-locked from a malformed-looking mempool payload); spent outpoints are pruned from `setLockedCoins` at reconcile. (§4.3, §4.5) |
| C4 | B3 fixed `evalHeight = indexTip`, which gives the mint zero reorg tolerance: a one-block reorg that replaces the tip with a block carrying a different price or supply changes `Snapshots[evalHeight]` and voids the mint (collateral locked for the tier). The threat model called this "residual" without bounding it. | **user-loss** | `evalHeight = indexTip − MINT_EVAL_LAG` (`MINT_EVAL_LAG` = 2 blocks, wallet-side, `-ydollarmintlag`), `nExpiryHeight = evalHeight + MINT_WINDOW`, `lockHeight = evalHeight + tierBlocks + MINT_WINDOW`. The mint then survives any reorg shorter than `MINT_EVAL_LAG + 1` blocks; every confirmation height still satisfies MINT-2 (arithmetic in §3.4). (§3.1, §3.4, §8.2) |
| C5 | Peers co-sign PRICE transactions with `signrawtransaction`, which signs **every** input the wallet can solve (`rawtransaction.cpp:1044-1057`). A malicious proposer could include a peer's own P2PKH coin as the "refill" input and have the peer sign it away. | safety | A peer refuses to sign a PRICE transaction that contains any input other than the anchor that its own wallet can solve; the refill is always the proposer's coin. Operator wallets are dedicated (hold nothing but the roster key) so the wallet can solve nothing else anyway. `yd_cosignredeem` never calls `signrawtransaction`: it signs only `vin[0]`, over the vault script **reconstructed from the index**, never the script found in the supplied scriptSig, so it cannot be turned into a signing oracle for anything else. (§4.6, §5) |
| C6 | `yd_createpricetx` runs in node context (no wallet) yet §5 had the refill produce "the proposer's refill change" — there is no wallet to pick a change address from, and every extra output is something peers must vet. | safety | The refill input is absorbed entirely into the new anchor (no change output); the operator prepares a UTXO of the exact refill amount with `sendtoaddress` and waits one confirmation so every peer's `signrawtransaction` finds it in `pcoinsTip`. Peers verify inputs = {current anchor} ∪ {at most one refill}, outputs = anchor P2SH with the same script + one `OP_RETURN`, fee = `YD_FEE`. (§3.4, §4.4, §5) |
| C7 | Roster keys were "imported with `importprivkey`", which implies generation outside the node. | safety | Generate the roster key inside the operator's `ycashd` (`getnewaddress`, then `validateaddress` for the `pubkey`); the key never leaves `wallet.dat`. `importprivkey <key> "" false` is only the backup-restore path. (§4.6) |
| C8 | B18's guard "refuse if fewer than 2 keypool keys remain" was written against the test framework's `-keypool=1`. `CWallet::GetKeyFromPool` generates a fresh key whenever the pool is empty and the wallet is unlocked (`ref/ycash/src/wallet/wallet.cpp:6005-6022`), so the pool size is never a blocker. | simplification | Guard dropped. `yd_mint` calls `GetKeyFromPool` (as `getnewaddress` does) after `EnsureWalletIsUnlocked`; the backup warning stays. (§3.8, §4.5) |
| C9 | The ROSTER payload type duplicated B8: rotation is already defined as "`vout[0].scriptPubKey` differs from the spent anchor's", whatever the payload says. | simplification | ROSTER type removed. A rotation is an anchor spend to a new P2SH with no `OP_RETURN`; `yd_createpricetx` takes `"rotate" <newRosterScriptHex>` for it. Payload types: MINT, TRANSFER, REDEEM, PRICE. (§3.2, §3.4, §3.7, §3.9, §4.4, §5) |
| C10 | REDEEM required "YEC fee inputs" in addition to the vault and the YDollar burn inputs. Every YDollar input already carries `TOKEN_VALUE` = 10 × `YD_FEE`, and a VOID release has the collateral itself. | simplification | No YEC inputs in a REDEEM. The fee comes from the transaction's own inputs; surplus token value goes into the collateral output. Fewer inputs to select, sign and vet. (§3.4) |
| C11 | `signrawtransaction` resolves inputs through `CCoinsViewMemPool` (`rawtransaction.cpp:908-912`), so an unconfirmed anchor that is in the signer's mempool is already solvable; B2's "prevtxs whenever the anchor is unconfirmed" was too broad. Also, outside regtest it signs with `CurrentEpochBranchId(max(Height()+1, APPROX_RELEASE_HEIGHT))` (`rawtransaction.cpp:1023-1028`, `deprecation.h:12`), not plain `Height()+1`. | precision | `prevtxs` (with `amount`) is needed only when the previous PRICE transaction is in neither the chain nor the signer's mempool; `yd_createpricetx` still returns it. Branch ID: identical today because no upgrade is scheduled; RED-7 doubles as the agreement check — a co-signer verifies the owner's signature under the branch ID it would sign with, so a mismatch is a refusal, never a mixed-branch signature set. (§3.3, §4.6, §5) |
| C12 | Regtest activates **no** upgrade by default — Overwinter, Sapling, Ycash, Blossom, Heartwood and Canopy are all `NO_ACTIVATION_HEIGHT` (`ref/ycash/src/chainparams.cpp:576-604`); B6's "activate all four" omitted Overwinter and Sapling. With `UPGRADE_YCASH` active from height 1 the coinbase must pay 5 % to the YDF script until `nYdfMandateEndHeight = 5` (`main.cpp:4507-4523`, `chainparams.cpp:609`), which the miner does by itself (`miner.cpp:201-203`). `atomicswap.py` starts nodes with no upgrades and no `-experimentalfeatures`, so it is not a usable template. | precision | `ydollar_node_args()` passes six `-nuparams` at height 1 plus `-experimentalfeatures -ydollar`. (§6, §7) |
| C13 | `wait_for_yd_index` polled `yd_getinfo.synced` because "the notifier runs once per second". The framework's `sync_blocks`/`sync_mempools` already wait on `fullyNotified` (`qa/rpc-tests/test_framework/util.py:133,160`; `src/rpc/blockchain.cpp:1188,1415`), which the notifier sets only after every subscriber — the index included — has run for that cycle (`validationinterface.cpp:238-241`). | simplification | After `sync_all()` the index is at the tip on every node; the helper reduces to `sync_blocks([node])` followed by an assertion on `synced`. (§6, §7) |
| C14 | Fuzz harness placed in `src/test/fuzz/`. Ycash's fuzz targets live in `src/fuzzing/<Target>/fuzz.cpp` with an `input/` corpus (`ref/ycash/src/fuzzing/`). | precision | `src/fuzzing/YDollarPayload/`, `src/fuzzing/YDollarScript/`. (§6, §7) |
| C15 | `IsStandard` rejects bare multisig with n > 3 (`ref/ycash/src/policy/policy.cpp:42-50`); a reader could take the 5-of-9 roster for non-standard. | precision | Stated: that rule is for bare multisig **outputs**; anchors and vaults are P2SH. `AreInputsStandard` accepts a P2SH multisig subscript of any n ≤ 16 whose scriptSig carries exactly k signatures (`ScriptSigArgsExpected` = k + 1, `standard.cpp:146-149`). (§3.3) |
| C16 | `YD_FEE = DEFAULT_FEE` was presented as convention. ZIP-401's limiter adds `LOW_FEE_PENALTY` to the eviction weight of any transaction paying less than `DEFAULT_FEE` (`ref/ycash/src/mempool_limit.cpp:151-157`). | precision | `-ydollarfee` is clamped to ≥ `DEFAULT_FEE`; the reason is recorded. (§3.1) |
| C17 | "Maximum output $100,000 as DigiByte (`digidollar.h:86-88`)": DigiByte defines no maximum output — those lines hold min mint, max mint and min output. | accuracy | `MAX_OUTPUT` is a YDollar parameter equal to DigiByte's maximum mint (`digidollar.h:87`). (D11, §3.1) |
| C18 | Phase 0 asked to fix `AGENTS.md`'s branch name; it already reads `feature/digidollar`. | stale | Item removed. (§6) |
| C19 | `IsStandardTx` checks `nVersion` against the rules active at the height passed in (`policy.cpp:58-68`); unit tests that pass 0 would test Sprout rules. | precision | Unit tests pass an explicit post-Sapling height. (§7) |
| C20 | A YDollar change amount in `(0, MIN_OUTPUT)` cannot be assigned (XFER-1) and would burn. | precision | `yd_send`/`yd_redeem` refuse such a change; users add or remove cents. (§4.5) |
| C21 | `-disablewallet` leaves `pwalletMain == nullptr`; the plan assumed a wallet. | precision | Index and node RPCs run without a wallet; the three locking stages are skipped when there is none. (§4.3) |
| C22 | `CommitTransaction` adds the transaction to the wallet **before** `AcceptToMemoryPool`; a mempool rejection leaves a stale wallet record (`ref/ycash/src/wallet/wallet.cpp:5723-5747`). | precision | `yd_submitredeem` checks `chainActive.Height() ≥ lockHeight`, the expiry margin and `VerifyScript` before committing. (§3.8 SUB-1) |
| C23 | `-datacarrier=0` on a relaying node drops every `OP_RETURN` transaction (`policy.cpp:52`). | operational | Runbook and threat model: user and operator nodes keep the default; the index is unaffected either way. (§5, §8.2) |
| C24 | The signature combiner "matches each signature to a key with `CPubKey::Verify`"; `Verify` takes the DER signature without the trailing hashtype byte. | precision | Stated. (§3.3) |
| C25 | The atomic-swap precedent was quoted as "17 lines in `main.cpp`". It also changed ≈ 400 lines of `wallet.{h,cpp}` and `walletdb.{h,cpp}` (`ref/ycash` commit `ccddd22e4`). | accuracy | YDollar's zero-lines target for `src/wallet/` is stricter than the precedent, not equal to it. (§1) |

Rows for C1, C3, C5, C6, C12, C13, C14 and C16 are added to `docs/mapping.md` §11.

### Revision 5 audit

Revision 4 was re-read against the code it depends on, with attention to the paths the earlier
audits had not exercised: shutdown, the coins view used by the policy checks, the wallet's spent
tracking, the DB wrapper and the unit-test harness. Every cite added in revision 4 was re-checked
(three drifted by one to five lines; corrected in place). The design is unchanged. Findings:

| # | Finding | Severity | Change |
|---|---|---|---|
| D1 | `AreInputsStandard` reaches inputs through `CCoinsViewCache::GetOutputFor`, which **asserts** the coin exists and is unspent (`ref/ycash/src/coins.cpp:898-903`); so does `GetValueIn` (`:912`). A co-signer's node fed a redemption hex naming an unknown outpoint would abort — a remote crash via the public `/cosign` path. | **safety (DoS)** | `CheckRedeem` first verifies `HaveCoins` + `IsAvailable` for every input on the view it built and refuses on any miss; only then does it call `AreInputsStandard` and compute the fee. Unit test with a phantom input. (§3.8 RED-4, §8.4) |
| D2 | Shutdown was described as "mirrors ZMQ" (unregister at `init.cpp:255`). On the normal path `WaitForShutdown` interrupts and **joins** the thread group before `Shutdown()` (`ref/ycash/src/bitcoind.cpp:52-55`), so the notifier is gone; on the startup-failure path `join_all` is deliberately skipped (`bitcoind.cpp:191-194`) and `Shutdown()` can run while `ThreadNotifyWallets` is inside a `ChainTip` call. `UnregisterValidationInterface` does not wait for a running slot, so deleting the index there is a use-after-free on that path. | safety | The index is never deleted during `Shutdown()`. Teardown is: `UnregisterValidationInterface(g_ydollar)`; then `{ LOCK(cs_ydollar); g_ydollar->Stop(); g_ydollar->Flush(fSync = true); }` — taking `cs_ydollar` waits out any in-flight handler, `Stop()` makes every later handler return at once, and the object is left for process exit (as Ycash leaves `pcoinsTip`'s siblings). Placed right after `StopRPC()` so no RPC can race it. (§4.3) |
| D3 | `yd_redeem` "locked the consumed coins" and `yd_abortredeem` "unlocked" them. With C10 a REDEEM has no YEC inputs, and its YDollar inputs are *already* `LockCoin`-locked as tokens — unlocking them on abort would expose them. Nothing stopped a second `yd_redeem`/`yd_send` from re-using the same YDollar inputs while co-signatures were being collected, and SUB-1 had no defined place to find "the transaction `yd_redeem` produced". | precision | `src/ydollar/wallet.cpp` keeps an in-memory `PendingRedemption { vaultOutpoint, ownerSignedTx, reservedInputs, createdHeight }` map. `yd_redeem` records one (refusing if the vault already has one); YDollar input selection skips reserved outpoints and outpoints the wallet already reports spent by an unconfirmed transaction (`CWallet::IsSpent`, `ref/ycash/src/wallet/wallet.cpp:1087-1099`); `yd_submitredeem` compares against the record (SUB-1) and clears it on commit; `yd_abortredeem <vaultTxid>` clears it; records die with the process and expire with the transaction. `LockCoin` is not involved in a REDEEM at all. (§3.8, §4.4, §4.5) |
| D4 | `yd_createpricetx` needs the current anchor's value (new anchor = anchor + refill − fee; `prevtxs.amount`), but `Anchor` stored only `{outpoint, scriptPubKey}`. | precision | `Anchor` records `nValue` (from `vout[0].nValue` on every anchor move); the RPC also cross-checks it against the UTXO view under `cs_main`. (§3.5, §4.4) |
| D5 | Right after launch, `indexTip − MINT_EVAL_LAG` can be below `startHeight`, where no snapshot exists, so MINT-2's `startHeight ≤ evalHeight` fails. | precision | MINTPOL-1 refuses to mint until `indexTip ≥ startHeight + MINT_EVAL_LAG`. (§3.8) |
| D6 | C19 said unit tests "pass a post-Sapling height", but `BasicTestingSetup` selects **mainnet** by default (`ref/ycash/src/test/test_bitcoin.h:19`) and the regtest fixture activates nothing. | precision | Script/standardness unit tests use `SelectParams(REGTEST)` plus `RegtestActivateSapling()` / `RegtestActivateCanopy()` (`ref/ycash/src/utiltest.h:40-53`), the helpers Ycash's own tests use, and pass height 1. (§7) |
| D7 | The roster-size arithmetic assumes 33-byte keys; nothing in the key ceremony required it. `CWallet::GenerateNewKey` makes compressed keys (`ref/ycash/src/wallet/wallet.cpp:270-273`), but an imported or externally generated key might not be. | precision | `RosterScript` and `yd_getroster`, `addmultisigaddress` inputs and the ceremony checklist reject any pubkey that is not 33 bytes. (§3.3, §4.6) |
| D8 | Per-block `WriteBatch` durability was unstated. `CDBWrapper::WriteBatch(batch, fSync = false)` (`ref/ycash/src/dbwrapper.h:238`) is atomic per batch but a crash may lose the last batches. | precision | Batches are unsynced during normal operation (the chainstate does the same); `SyncToChain` at startup already handles a stored tip behind the chain; `fSync = true` on the shutdown flush and at the end of `SyncToChain`. (§4.3) |
| D9 | Anyone can create VOID vaults (a MINT payload with a P2SH `vout[0]` and any failing rule) and every YDollar node records them forever. | operational | Bounded by the transaction fee like any UTXO growth; `yd_listvaults` is paged; Phase 6 DoS review measures records-per-block at the mempool's cost limit. (§6) |

Rows for D1 and D2 are added to `docs/mapping.md` §11.

### Revision 6 audit

Revision 5 was re-read with attention to what each RPC needs as a *data source*, to skew between
nodes in the co-signing rules, and to operator key custody. The design is unchanged. Findings:

| # | Finding | Severity | Change |
|---|---|---|---|
| E1 | `yd_listtransactions` and `yd_gettxinfo` were said to read "from the index", but no table supports them: IN-1 erases a `Tokens` record when it is spent, and confirmed transactions can only be fetched from disk with `-txindex` (`ref/ycash/src/main.cpp:1858-1870`), which the plan promises not to require. | **feasibility** | New `TxLog` table: `txid → { height, type, verdict, ydIn, ydOut, burned, assignedOutpoints[], closedVaults[] }`, written for every transaction that carries a payload or spends a `Tokens`/`Vaults`/`Anchor` outpoint, undone with the block. History and verdict RPCs read it; wallet filtering is `IsMine` over the assigned outputs' scripts (kept in `Tokens` while unspent, copied into the log entry when erased). (§3.5, §3.7, §4.4) |
| E2 | RED-8 `nExpiryHeight ≤ indexTip + 40` was evaluated on the co-signer's node, but the owner's node may be a block ahead (the notifier trails the tip by up to a second per node and blocks propagate unevenly), so an honestly built redemption would be refused. RED-0 and RED-2 have the same transient form. | liveness | RED-8 allows `RED_SKEW = 2` blocks of slack (`indexTip + 40 + 2`); the rule's purpose — bounding how long a co-signed transaction can be held — is unaffected. RED-0/RED-2 refusals are reported as *transient* and the client retries after the next block. (§3.8, §5) |
| E3 | RED-6 (price defined) blocked every co-signature during an oracle outage, including the release of a VOID vault, which needs no burn and therefore no price. | precision | RED-6 applies to ACTIVE vaults only. (§3.8) |
| E4 | The idempotence rule in §4.3 compares "the stored hash at that height" with `pindex->GetBlockHash()`, but no table stored a hash per height. | precision | `Snapshots[H]` records `blockHash`; `Undo` stays keyed by hash. (§3.5, §4.3) |
| E5 | Ycash wallet encryption is experimental and gated (`encryptwallet`/`walletpassphrase` refuse unless `-developerencryptwallet`, `ref/ycash/src/wallet/rpcwallet.cpp:2127,2160`), so roster keys and vault owner keys sit unencrypted in `wallet.dat` on every node. | safety | Custody is stated: operator nodes are dedicated hosts with full-disk encryption, RPC bound to localhost, and offline `wallet.dat` backups; users are told the same for vault keys. No reliance on the experimental encryption path. (§4.5, §4.6, §5) |
| E6 | Block `startHeight` may itself contain a spend of the genesis anchor; the order of "initialise `Anchor`/`Rosters` from params" versus "process the block's transactions" was unstated. | precision | At `startHeight`, `Anchor` and `Rosters[0]` are initialised from params **before** any transaction of that block is processed. (§3.7) |
| E7 | Transaction malleation by a miner (re-encoded signatures change a txid; Ycash has no SegWit) was not in the threat model. The index is unaffected (it keys on confirmed outpoints), but a wallet that tracked a position by the txid it broadcast would lose it. | threat model | Positions and balances are derived from the index by key ownership (`HaveKey(ownerPubKey)`, `IsMine(scriptPubKey)`), never by remembered txid; a malleated own transaction shows as conflicted in the wallet, which is the existing Ycash behaviour. Row added. (§8.2) |
| E8 | Build placement was unstated; Ycash links `test_bitcoin` and `ycashd` from `libbitcoin_common`/`_server`/`_wallet` (`ref/ycash/src/Makefile.am:267,324,413`). | precision | Pure modules (`params`, `amount`, `payload`, `script`, `address`, `view`, `state`) go in `libbitcoin_common`; `db`, `index`, `policy` and `rpc/ydollar.cpp` in `libbitcoin_server`; `wallet`, `txbuilder` and `rpc/ydollarwallet.cpp` in `libbitcoin_wallet`. (§4.2) |
| E9 | `yd_getnewaddress` did not add the key to the address book, unlike `getnewaddress`. | precision | It calls `SetAddressBook(keyID, "", "receive")` so the standard listing RPCs see the key. (§4.4) |

Rows for E1 and E5 are added to `docs/mapping.md` §11.

### Revision 7 audit

Revision 6 was re-read end to end for internal consistency across the edits of revisions 4–6,
and the wallet's coin-selection, rebroadcast and expiry paths were read. No feasibility or
user-loss defect was found; the design is unchanged. Findings:

| # | Finding | Severity | Change |
|---|---|---|---|
| F1 | The threat model's accountability check, "`burnedCents < requiredBurn` on a CLOSED vault", had no defined evaluation height: RED-3 computes `requiredBurn` at the co-signer's `indexTip`, which may be a few blocks before the closing block, and the vault record stored only `burnedCents`. | precision | IN-2 records `errBpsAtClose = Snapshots[closeHeight − 1].errBps` and `requiredBurnAtClose = RequiredBurn(mintedCents, errBpsAtClose)` on the vault (0 for VOID). `yd_getvault` reports both and an `unbacked` flag (`burnedCents < requiredBurnAtClose`). Because ERR tiers are 5 % health bands, a co-signer's `indexTip` and the closing block rarely straddle a band; the flag is what rotation decisions read. (§3.5, §3.7, §4.4, §8.2) |
| F2 | §5 had peers sign sequentially. `signrawtransaction` already merges any number of partially signed copies passed as concatenated hex (`ref/ycash/src/rpc/rawtransaction.cpp:886-893,1058-1062`), so the proposer can collect partials in parallel and merge in one call. | simplification | Price rounds POST the unsigned hex to all peers at once, then call `signrawtransaction` once with the concatenated replies. Round latency drops from k sequential hops to one. (§5) |
| F3 | The builder took YEC inputs from `AvailableCoins` with the default depth, which includes the wallet's own 0-conf outputs (B4's trusted rule) and outputs of the wallet's own *expired* transactions — `AvailableCoins` has no expiry filter and `RelayWalletTransaction` rebroadcasts any depth-0 transaction forever (`ref/ycash/src/wallet/wallet.cpp:4653-4668,5038-5052`). A YDollar transaction chained on such an input can never confirm; for a MINT that means a wasted `evalHeight` window and a re-run. | hardening | Every input of every YDollar transaction is confirmed: YDollar inputs from the index (already the rule) and YEC inputs via `AvailableCoins(..., nMinDepth = 1)`, the existing parameter (`wallet.cpp:5052`). No bespoke filtering. (§3.4, §4.5) |
| F4 | §8.2 still listed the "keypool guard" dropped in C8. | stale | Row fixed. (§8.2) |
| F5 | `CheckFinalTx` runs with `STANDARD_LOCKTIME_VERIFY_FLAGS = LOCKTIME_MEDIAN_TIME_PAST` (`ref/ycash/src/consensus/consensus.h:49`), which changes the reference *time* for time-based locks only; the plan did not say so. | precision | Stated: vault locks are heights, so median-time-past never enters. (§3.3) |
| F6 | Behaviour of YDollar transactions that expire unmined was implicit. The mempool drops them at the next block (`main.cpp:3636`, `txmempool.cpp:411`); the wallet keeps them at depth 0 and rebroadcasts them (F3). | precision | Stated per type: an expired MINT/TRANSFER leaves no index trace and its stage-(i) locks are harmless; an expired REDEEM leaves the vault ACTIVE and the `PendingRedemption` record is dropped at `nExpiryHeight`; `yd_gettxinfo` reports `expired` for a wallet transaction past its `nExpiryHeight` that is in neither `TxLog` nor the mempool. (§4.4, §4.5) |

### Revision 8

Adds §6.0 — the single-developer, single-machine development and test workflow, and the CI job —
and the regtest parameter overrides in §3.1 it relies on. Nothing in the protocol changes: the
overrides are values of parameters the plan already declared per network, and every tool named is
one the repository already ships (`qa/rpc-tests`, `zcutil/build.sh`, `zcutil/fetch-params.sh`).

### Revision 9 audit (of §6.0)

Every tool §6.0 names was re-checked at the pin. One finding blocks the whole functional-test
plan as inherited, and is cheap to fix; the rest are precision.

| # | Finding | Severity | Change |
|---|---|---|---|
| G1 | **The inherited functional-test framework cannot start a Ycash node at all.** `initialize_datadir` writes the node's settings — including `regtest=1` and the RPC credentials — to `zcash.conf` (`qa/rpc-tests/test_framework/util.py:175`; also `multi_rpc.py:29`), but Ycash reads `ycash.conf` (`BITCOIN_CONF_FILENAME`, `ref/ycash/src/util.cpp:76`), has no fallback, and `ycashd` exits with "Before starting ycashd, you need to create a configuration file" when it is missing (`util.cpp:372-378`, `bitcoind.cpp:104-113`). `start_node` does not pass `-regtest` on the command line (`util.py:357-362`), so even a node that started would be on mainnet. B6's baseline ("post-Blossom tests fail on branch IDs") was therefore optimistic: at the pin, **every** `qa/rpc-tests` script fails at node start, and `atomicswap.py` has never run. | **feasibility** | Phase 0 fixes the filename in the two framework files (`"zcash.conf"` → `"ycash.conf"`, two lines; `ycash-cli` reads the same name, `bitcoin-cli.cpp:113`). This is a test-framework bug fix, not a node change, and it is what makes the Phase 0 baseline run meaningful. Diff budget updated. (§4.1, §6, §6.0) |
| G2 | §6.0 generated roster keys 6–9 with `test_framework/key.py`, which binds OpenSSL through `ctypes` (`key.py:14-24`) — a host-library dependency that varies by platform and OpenSSL version. | precision | Keys 6–9 come from node 1's wallet (`getnewaddress` + `validateaddress` → `pubkey`), the node that never runs `-ydollar` and is never asked to co-sign. No Python crypto at all. (§6.0) |
| G3 | `rpc-tests.py -j4 ydollar_*` implied a glob. The runner accepts individual names only if they appear in its own lists (`qa/pull-tester/rpc-tests.py:213-218`) and does not glob. | precision | The YDollar scripts are appended to `BASE_SCRIPTS` (already in the diff budget) and CI names them explicitly. (§6.0) |
| G4 | CI step 4 named `src/zcash-gtest --gtest_filter=YDollar*`. The binary is `ycash-gtest` (`src/Makefile.gtest.include:6`) and the plan writes Boost tests only (§7). | precision | Step 4 is `src/test/test_bitcoin --run_test=ydollar_*`; the nightly `make check` covers gtest. (§6.0) |
| G5 | The regtest overrides table left the volatility windows at mainnet values (`BLOCKS_PER_DAY` = 1,152), so the 24-hour breach could never be exercised in a short test. `-ydollarsupplycap` was introduced there but not in the configuration list. | precision | Regtest overrides for the two volatility windows (48 / 96); `-ydollarsupplycap` (regtest only) added to §4.4. (§3.1, §4.4) |
| G6 | Node 1 (no `-ydollar`) must still share consensus parameters, and it has no index to compare. | precision | Node 1 gets the same six `-nuparams`; the state-hash assertion runs over the `-ydollar` nodes only. (§6.0, §7) |
| G7 | The coordinator's test-only transport flag was named in §6.0 but not in Phase 4. | precision | `--insecure-localhost` added to the Phase 4 deliverable. (§6) |

### Revision 10

Adds §4.7 (user interface and user experience), decision D21, a wallet-application phase in §6,
UI rows in §7 and §11, and corrects §10's "Qt GUI: none" row, which read as if no user interface
were needed. The facts behind it: Ycash ships no GUI at all — `ycashd` and `ycash-cli` only, no
`src/qt/` (`mapping.md` §1) — its wallet applications are external and speak to the node over
RPC, and Ycash's own atomic-swap feature shipped RPC-first with "GUI integration" listed as a
future enhancement (`ref/ycash/doc/atomic-swaps.md:611-615`). DigiByte's DigiDollar UI is seven
Qt tabs, ≈ 10,400 lines (`ref/digibyte/src/qt/digidollar*`, `digidollartab.cpp:100-106`); it is
the *behavioural* specification for §4.7, not source.

### Revision 11

Resolves the open input of revision 10: the Ycash full-node GUI is **YecWallet**
(`github.com/ycashfoundation/yecwallet`), a Qt 6 / CMake C++ application (≈ 8,300 lines) that
ships `ycashd` beside its binary, starts it, writes its `ycash.conf`, and drives it over JSON-RPC.
The workspace now holds it as a third read-only reference (`ref/yecwallet` @ `v4.5.0`,
`1eb277d`) and a second working fork (`yecwallet-dd`, `feature/digidollar` off
`yecwallet-legacy`), wired into `make status`/`diff`/`log`, `AGENTS.md` and `docs/mapping.md`
(new §12: DigiByte `src/qt/digidollar*` → YecWallet). §4.7 and Phase 5b are rewritten from
"an external application to be identified" to concrete files, hooks and a diff budget in
`yecwallet-dd`; D21 is restated; §6.0 gains the wallet's build and playground test; §10 and §11
are updated. The node-side plan (§1–§4.6, §5, §6 Phases 0–5) is unchanged.

### Revision 12 audit (of the YecWallet material)

Every cite added in revision 11 was re-read at `ref/yecwallet` @ `v4.5.0`, and every claim about
the wallet's behaviour was checked in its source. One finding is a feasibility defect in the
wallet test plan; one removes code the plan had proposed; the rest are precision.

| # | Finding | Severity | Change |
|---|---|---|---|
| H1 | §4.7 called Qt Test "part of Qt 6 — no new dependency". The wallet's static Qt is configured with `-no-feature-testlib` (`ref/yecwallet/scripts/build-qt.sh:129`), so release builds have **no** `Qt6::Test` and a test target would not even configure. | **feasibility** | `build-qt.sh` stays untouched. The test target is declared with `find_package(Qt6 OPTIONAL_COMPONENTS Test)` — the pattern the file already uses for `LinguistTools` (`CMakeLists.txt:53`) — and built only when found, i.e. in development and CI builds against a system Qt 6, never in the static release build. Phase 0 (wallet side) verifies the unmodified app configures and builds against the CI runner's system Qt 6. (§4.7, §6 Phase 5b) |
| H2 | §4.7 and Phase 5b added a `--regtest-playground` option. The stock wallet already attaches to any node: `--conf <file>` reads `rpcuser`, `rpcpassword` and `rpcport` from it (`src/connection.cpp:647-673`) and `--no-embedded` stops it starting its own node (`src/main.cpp:168`); the playground's per-node conf has exactly those keys (`test_framework/util.py:175-181`). | simplification | Option removed. Attaching is `yecwallet --conf <tmpdir>/node0/ycash.conf --no-embedded`; the QTest target does the same. Fewer lines in `main.cpp`/`connection.cpp`. (§4.7, §6.0, Phase 5b) |
| H3 | Network detection on the playground was unstated. The wallet sets testnet mode from `getinfo.testnet` (`src/controller.cpp:255-257`), which regtest reports as `false` (`ref/ycash/src/chainparams.cpp:673`); regtest transparent addresses share testnet prefixes and still pass the wallet's `isTAddress` (`src/settings.cpp:78-83`), so the stock tabs work against the playground, but a YDollar-address check keyed on that flag would pick the mainnet prefix. | precision | `yd_getinfo` returns `network` (`main`/`test`/`regtest`); the YDollar tab validates and renders `yd`/`yt`/`yr` addresses from that field, never from `getinfo.testnet`. (§4.4, §4.7) |
| H4 | "polls `getinfo` every few seconds": `Settings::updateSpeed` is 20 s (`src/settings.h:124`); `txTimer` drops to 1 s only while an operation is pending (`controller.cpp:45-50`). | precision | Stated; the redemption wizard uses the 1-second pending mode, everything else the 20-second cycle. (§4.7) |
| H5 | `--headless` was described as the test mode. It hides the main window and skips the connection and shutdown dialogs (`src/main.cpp:251-257`, `connection.cpp:31-32`, `controller.cpp:849`); it does not remove the need for a display. | precision | The QTest target runs under `QT_QPA_PLATFORM=offscreen` with headless mode on — the standard Qt way to run widget tests on a CI runner. (§4.7) |
| H6 | TLS availability for the wizard's HTTPS was asserted, not shown. | precision | The static Qt links OpenSSL statically (`build-qt.sh:147-159`) and the wallet already makes HTTPS calls (`controller.cpp:685,757`), so the wizard's `/cosign` POSTs need nothing new; the network client is `Connection::client` (`connection.cpp:221`), not line 274 as cited. (§4.7, `mapping.md` §12) |

[`../why-no-consensus-change.md`](../why-no-consensus-change.md) was re-checked against revisions
4–12: none of the changes alters a claim in it (every change is inside the overlay index, the
wallet layer, the coordinator, the test workflow or the GUI wallet; nothing moves into consensus
or policy), and its line cites still resolve. A row for G1 is added to `docs/mapping.md` §11.

---

## 1. The decision in one page

**YDollar v1 is a Tier-0 build: no consensus change, no policy change, no new opcodes, no network
upgrade, zero lines changed in `src/main.cpp`, `src/consensus/`, `src/script/`, `src/primitives/`,
`src/pow/`, or `src/chainparams.cpp`.** It is an *overlay protocol* on ordinary Ycash v4 transparent
transactions, exactly the shape of the atomic-swap feature Ycash shipped in v4.5.0 (commit
`ccddd22e4`: 17 lines in `main.cpp` plus ≈ 400 in `wallet.{h,cpp}`/`walletdb.{h,cpp}`), but with
even fewer hooks: the YDollar index subscribes to the existing `CValidationInterface::ChainTip`
signal instead of adding calls to `main.cpp`, and touches no file under `src/wallet/`.

The five load-bearing choices:

1. **Token representation.** A YDollar balance is an ordinary transparent output (P2PKH to the
   holder's key, carrying a token-floor amount of YEC) whose USD-cent value is declared in the
   transaction's single `OP_RETURN` payload. This is the colored-coin model (Omni, Counterparty,
   Runes) and it is what DigiDollar itself does for amounts — DigiByte's DD token output is a
   0-value P2TR and the cents live in `OP_RETURN` (`ref/digibyte/src/digidollar/txbuilder.cpp:407-418,
   807-818`). Every YDollar-aware node computes the *same* YDollar state from the *same* chain, so
   conservation and all accounting rules are deterministic and enforced by every honest node, without
   the chain rejecting anything.

2. **Collateral vault.** Collateral is locked in a P2SH output whose redeem script is
   `<lockHeight> OP_CHECKLOCKTIMEVERIFY OP_DROP <ownerKey> OP_CHECKSIGVERIFY <k> <Q1…Qn> <n> OP_CHECKMULTISIG`.
   The timelock is consensus-enforced (Ycash validates CLTV in every block:
   `ref/ycash/src/main.cpp:2931`). The "you must burn YDollar to get collateral back" rule is
   enforced by a **k-of-n federation co-signature**, because without covenants no script can bind a
   spend to a burn. There is deliberately **no owner-only fallback path** (§2, D3 explains why any
   such path makes minting free money).

3. **Oracle.** The same federation publishes the YEC/USD price by spending a well-known **anchor
   UTXO** (a standard k-of-n P2SH multisig) into a new anchor plus an `OP_RETURN` price payload. The
   k-of-n ECDSA signatures are verified by Ycash consensus for free; the overlay only parses. No
   coinbase changes, no miner involvement, no P2P messages, no new signature code.

4. **Cryptography.** ECDSA over secp256k1 with `OP_CHECKMULTISIG`, i.e. exactly what Ycash already
   runs in consensus. No Schnorr, no MuSig2, no change to the vendored `secp256k1` (built with only
   the recovery module: `ref/ycash/configure.ac:1282`).

5. **State.** A self-contained, rebuildable LevelDB index under `<datadir>/ydollar/` with per-block
   undo records, fed by the `ChainTip` signal Ycash already delivers to the wallet for every block
   connect and disconnect (`ref/ycash/src/validationinterface.cpp:183-217`). Deterministic,
   reorg-safe, no floats, no wall clock.

**What this costs, stated plainly.** Two properties DigiByte enforces in consensus are enforced by
the federation instead: (a) collateral cannot be released without burning the required YDollar, and
(b) prices are honest. A colluding quorum (k of n operators) can release collateral without a burn
or publish a false price; a failed quorum (fewer than k operators alive) freezes redemptions and new
mints until it recovers. DigiDollar already trusts a 7-of-35 oracle quorum for (b); the additional
trust in v1 is (a). §8 states this as the project's trust statement. §9 describes the later network
upgrade that removes (a) by letting the chain enforce burns, reusing this plan's validator unchanged.

**Why not go straight to a network upgrade.** It is the largest possible ask of a risk-averse team
(coordinated hard fork of a chain with a shielded pool), it still needs the oracle quorum, and every
line of it can be built later on top of the v1 overlay — the overlay *is* the specification the
consensus rule would enforce. Shipping v1 first produces a working system, real operator experience,
and a validator with months of testnet mileage before any consensus rule is proposed.

---

## 2. Decision record

Each entry: options considered → **decision** → why → what it costs. Numbers cite the pinned trees.

### D1. Change-budget tier

Options: Tier 0 (overlay, existing opcodes) · Tier 2 (`OP_NOPx` soft fork) · Tier 3 (network
upgrade `UPGRADE_YDOLLAR`).

**Decision: Tier 0.** Tier 2 is rejected outright: Ycash's free `OP_NOP` slots are bare no-ops
that consume nothing (`ref/ycash/src/script/interpreter.cpp:388-392`), so they cannot carry
multi-operand semantics, and a soft fork has never been done on Ycash. Tier 3 is deferred to §9
because (i) the README's prime directive is minimal change, (ii) the atomic-swap precedent proves
Tier 0 is mergeable, (iii) the two invariants Tier 3 adds can be added later without redesign.
Cost: the trust statement in §8.

### D2. Token representation

Options: (a) colored transparent outputs + `OP_RETURN` amounts · (b) a new script template
(`OP_RETURN`-tagged P2SH or a marker script) · (c) a new tx version / version group (ZIP-202 style).

**Decision: (a).** Ycash policy allows exactly one `OP_RETURN` output per tx and 80 data bytes
(`ref/ycash/src/policy/policy.cpp:52,123`; `ref/ycash/src/script/standard.h:34`). (b) adds nothing:
consensus still would not see the token. (c) is Tier 3 and collides with `nVersion == 4` pinning
(`mapping.md` §5). Cost: a non-YDollar-aware wallet that spends a YDollar-bearing output burns the
YDollar (same property as Omni). Mitigation: the YDollar wallet layer locks such coins
(`CWallet::LockCoin`, `ref/ycash/src/wallet/wallet.h:1369`) and a distinct address format (D10)
stops users from sending YDollar to plain `s1…` addresses by accident.

### D3. Vault script and the no-fallback rule

Options for the collateral output: (a) `CLTV + owner CHECKSIG` only · (b) `CLTV + owner
CHECKSIGVERIFY + k-of-n federation CHECKMULTISIG` · (c) (b) plus an owner-only path after a grace
period · (d) (b) plus a second cold-key recovery quorum after a grace period.

**Decision: (b), with no owner-only path.** (a) cannot work: after `lockHeight` the owner takes
the collateral back *and keeps the YDollar they sold* — minting becomes a free loan that is never
repaid, and the overlay cannot stop it. (c) has the same exploit delayed by the grace period; with
200–1000% collateral the exploit still pays ~18%/yr at a one-year grace, so it would be used.
(d) doubles the operational surface for a marginal liveness gain. Cost of (b): if the federation
loses liveness (fewer than k keys available), collateral stays locked until it recovers. Bounded by
D11 (v1 tiers ≤ 1 year), by roster rotation (§3.9) and by the operator runbook (§5).

Script-size arithmetic that bounds the roster: redeem scripts must fit in one 520-byte push
(`ref/ycash/src/script/script.h:23`), scriptSigs must be ≤ 1650 bytes to relay
(`ref/ycash/src/policy/policy.cpp:93`), and a P2SH input may count at most 15 sigops
(`ref/ycash/src/policy/policy.h:24`). With one owner key plus `n` roster keys the vault script is
`44 + 34n` bytes when `lockHeight` fits a 3-byte push (heights < 8,388,608) and `45 + 34n` bytes
with a 4-byte push, so n ≤ 14 by script size today and n ≤ 13 once heights need four bytes; sigops
(`n + 1 ≤ 15`) give n ≤ 14. **The roster bound is n ≤ 13** so it never depends on the height.
**v1 roster: n = 9, k = 5** (script = 350 B, worst-case scriptSig ≈ 800 B, 10 sigops).

### D4. Oracle transport

Options: (a) price committed in the coinbase (DigiByte's `OP_RETURN OP_ORACLE` bundle) · (b) new
P2P messages plus a node-side bundle manager · (c) **anchor-chain price transactions**: the
federation spends a k-of-n P2SH anchor UTXO into a new anchor plus an `OP_RETURN` price.

**Decision: (c).** (a) needs miner/`miner.cpp` integration and block-validation hooks — Tier 3
territory in Ycash because the coinbase is already shaped by founders'/YDF streams. (b) means
editing the monolithic `ProcessMessage` in `main.cpp` and writing signature-verification code.
(c) uses consensus to verify the quorum's ECDSA signatures (`MANDATORY_SCRIPT_VERIFY_FLAGS =
SCRIPT_VERIFY_P2SH`, `ref/ycash/src/script/standard.h:53`), serialises updates by construction
(each price tx spends the previous anchor), and is signable today with the existing
`signrawtransaction` partial-signature merging (`ref/ycash/src/rpc/rawtransaction.cpp:1057-1061`).
Cost: one small fee per price update (≈ 1 YEC per year at 10-minute cadence) and the anchor must be
kept funded (anyone can add a refill input).

### D5. Cryptography

Options: ECDSA `OP_CHECKMULTISIG` · BIP-340 Schnorr + MuSig2 (port DigiByte's `src/oracle/musig2_*`).

**Decision: ECDSA multisig.** MuSig2 would require upgrading the vendored `secp256k1` that
verifies every transparent signature on the chain, plus porting ~10 kLOC of session/nonce code that
DigiByte hardened over many "waves". ECDSA multisig is what Ycash consensus already executes, with
RFC6979 deterministic nonces and no interactive rounds. Cost: bigger on-chain signatures (k × 72 B
per vault redeem; irrelevant at Ycash's block sizes).

### D6. Where the federation logic lives

Options: (a) inside `ycashd` (like DigiByte's `src/oracle/node.cpp`) · (b) a separate coordinator
process driving `ycashd` over RPC.

**Decision: (b), Python, shipped in `ycash-dd/contrib/ydollar/`.** Price fetching needs an HTTPS
client and JSON parsing; `ycashd` links neither libcurl nor OpenSSL (`ref/ycash/configure.ac`).
Signing uses the node's own wallet via `signrawtransaction` (anchor spends) and the new
`yd_cosignredeem` RPC (vault spends). This keeps the C++ diff to the overlay and wallet.

### D7. How the index observes the chain

Options: (a) explicit calls in `AcceptToMemoryPool`/`ConnectBlock`/`DisconnectTip` (atomic-swap
style, 17 lines in `main.cpp`) · (b) a `CValidationInterface` subscriber using `ChainTip(pindex,
pblock, added)`.

**Decision: (b).** `ThreadNotifyWallets` already reads every connected and disconnected block from
disk and calls `ChainTip` in exact chain order — disconnects with `std::nullopt`, connects with the
old trees (`ref/ycash/src/validationinterface.cpp:183-217`); the thread is started before block
import so nothing is missed (`ref/ycash/src/init.cpp:1831-1847`), and under `-reindex` it waits
for genesis and then delivers every block (`validationinterface.cpp:77-88`). The wallet is itself a
subscriber (`ref/ycash/src/wallet/wallet.cpp:6676`) and its note-witness cache depends on these exact
semantics, so the mechanism is proven on every node today. **Result: zero lines in `main.cpp`.**
Costs: the notifier runs once per second (`validationinterface.cpp:92-96`), so the index trails the
tip by up to one second and every YDollar RPC reports the index height it answers for
(`yd_getinfo.synced`); rebuilds read blocks from disk, so `-ydollar` refuses to start with `-prune`
(same pattern as `-insightexplorer` requiring `-txindex`, `ref/ycash/src/init.cpp:1597-1600`).

### D8. State storage

Options: (a) wallet.dat records only · (b) reuse `pblocktree` like the insight-explorer indexes ·
(c) a dedicated `CDBWrapper` LevelDB under `<datadir>/ydollar/`.

**Decision: (c).** Global state (supply, vaults, prices) is not wallet state; (a) breaks
wallet-less nodes. (b) means editing `txdb.cpp` and `main.cpp`. `CDBWrapper` is the same class the
chainstate uses (`ref/ycash/src/dbwrapper.h:175`). The DB stores its own tip plus one undo record
per block so it can roll back in-process reorgs, and it can be wiped and rebuilt from the YDollar
start height with `-reindex-ydollar`. Cost: a new directory and ~600 lines of DB code.

### D9. Wallet integration

Options: (a) extend `CWallet::CreateTransaction` to understand YDollar · (b) build YDollar
transactions by hand from public `CWallet` primitives, as `z_sendmany` does.

**Decision: (b).** `CreateTransaction` places change at a random index and signs internally, which
fights the payload's (vout, cents) assignments. `AsyncRPCOperation_sendmany` already builds
transparent transactions manually (`ref/ycash/src/wallet/asyncrpcoperation_sendmany.cpp:854,1196`),
and the atomic-swap RPCs sign custom P2SH inputs manually with `SignatureHash` + `CKey::Sign`
(`ref/ycash/src/rpc/atomicswap.cpp:760-775`). `TransactionBuilder` (`ref/ycash/src/transaction_builder.h`)
was considered and rejected: it has no raw-script output (so no `OP_RETURN`) and `Build()` signs
every transparent input through the keystore, which cannot solve the vault script. The manual path
reuses what exists: `CreateNewContextualCMutableTransaction(consensus, tip + 1)` for version,
version group and expiry (`ref/ycash/src/main.cpp:7364-7392`); a flat fee of `DEFAULT_FEE` =
1,000 zat as every `z_*` operation (`ref/ycash/src/policy/fees.h:15`; `-ydollarfee` overrides), so
no fee-estimation loop; smallest-first input selection as `find_utxos` does; `SignSignature` for
P2PKH inputs and the manual sighash for the vault input. Cost: ≈ 400 lines in
`src/ydollar/txbuilder.cpp` and `wallet.cpp`; zero lines in `src/wallet/`.

### D10. Address format

**Decision: a YDollar address is Base58Check(version ‖ 20-byte key hash) with version bytes
`0x1F 0xE2` (mainnet, renders `yd…`), `0x20 0x07` (testnet, `yt…`), `0x20 0x02` (regtest, `yr…`),
decoding to an ordinary P2PKH destination.** Verified by exhaustive search over all payloads to
render those two leading characters. Implemented entirely in `src/ydollar/address.cpp`; no
`chainparams.cpp` edit. Mirrors DigiByte's `DD/TD/RD` prefixes (`DIGIDOLLAR_ARCHITECTURE.md` §3.2).

### D11. v1 parameters

**Decision:** tiers 0–4 only (1 h, 30 d, 90 d, 180 d, 1 y) at DigiByte's ratios 1000/500/400/350/300 %
(`ref/digibyte/src/consensus/digidollar.h:72-84`); tiers 5–9 (2–10 y) are deferred to §9 because a
federated vault must not outlive the roster that can co-sign it. Mint bounds $100–$10,000 (DigiByte:
$100–$100,000) and a v1 mainnet supply cap of $1,000,000 — both are parameters, not protocol, and
exist because Ycash's liquidity is a small fraction of DigiByte's. Minimum output $1.00 as DigiByte
(`digidollar.h:88`); maximum output $100,000, a YDollar parameter set equal to DigiByte's maximum
mint (`digidollar.h:87`) — DigiByte defines no maximum output (C17).

### D12. Protection systems

**Decision:** port DCA and ERR exactly (integer basis-point tables from
`ref/digibyte/src/consensus/dca.cpp:53-58` and `err.cpp:38-41`); port volatility protection in a
simplified, integer-only, block-window form that **freezes minting only** (never transfers or
redemptions). Rationale: in an overlay, a frozen transfer is a burned transfer for any wallet that
did not know; freezing mints has no such failure mode. All arithmetic uses `arith_uint256`
(`ref/ycash/src/arith_uint256.h`), never `double` and never `__int128` (which Ycash does not use
anywhere).

### D13. Shielded pools

**Decision:** YDollar transactions must be fully transparent: empty `vShieldedSpend`,
`vShieldedOutput`, `vJoinSplit`, and `valueBalance == 0` (`ref/ycash/src/primitives/transaction.h:553-558`).
A YDollar payload on a transaction with any shielded component is invalid (mint void, transfer
burns). Shielded YDollar is out of scope (`mapping.md` §6).

### D14. Activation

**Decision:** an experimental-features flag `-ydollar` (requires `-experimentalfeatures`, pattern
of `ref/ycash/src/experimental_features.cpp`) plus a per-network **start height** and **genesis
anchor outpoint** in `src/ydollar/params.cpp`. No branch ID, no activation height in
`chainparams.cpp`. Nodes without the flag are unaffected in every way.

### D15. Naming and layout

**Decision:** namespace `ydollar`, directory `src/ydollar/`, RPC prefix `yd_`, log category
`ydollar`, config prefix `-ydollar…`. The word *DigiDollar* appears only in comments citing upstream
files (AGENTS.md rule 6).

### D16. Redemption co-signing transport

Options: (a) user copies owner-signed hex to operators by hand · (b) `ycashd` calls operator
endpoints over HTTP (`evhttp`, no TLS) · (c) a small client outside the node collects co-signatures
over HTTPS and hands the result back to the node for verification and broadcast.

**Decision: (c), with (a) always possible.** `ycashd` gains **no outbound networking, no new
dependency and no background operation**: `yd_redeem <vault>` builds and owner-signs the
transaction and returns its hex plus the vault's roster; `contrib/ydollar/ydollar-redeem` (Python,
`requests`, TLS verified) POSTs it to each operator's `/cosign` endpoint until `k` signatures are
present; `yd_submitredeem <hex>` re-verifies on the user's node — the transaction must be identical
to the one `yd_redeem` produced except for added signatures (SUB-1), and every input must pass
`VerifyScript` with `STANDARD_SCRIPT_VERIFY_FLAGS` — then commits it through the wallet. This is
strictly less code and less attack surface than revision 1's in-node client, it gives TLS for free,
and it keeps the node's behaviour fully synchronous and testable through RPC alone.

### D17. Price semantics

**Decision:** the price in effect at height H is the price from the most recent valid attestation
confirmed at height ≤ H whose height is ≥ H − 48 (one hour at 75-second blocks,
`ref/ycash/src/consensus/params.h:212`). Attestations in the same block count in transaction order
(the last one wins). No price → no mints (fail closed, as DigiDollar's `bad-oracle-price`,
`ref/digibyte/src/digidollar/validation.cpp:1148`). **A mint's collateral rules are evaluated at the
`evalHeight` the minter commits to in the payload**, which must lie within `MINT_WINDOW` blocks
below the confirmation height; Ycash's transaction expiry (`DEFAULT_POST_BLOSSOM_TX_EXPIRY_DELTA =
40`, `ref/ycash/src/main.h:78-79`) makes that window enforceable by the wallet. DigiByte evaluates
at the confirmation block because its rule is consensus and an invalid mint is simply rejected; in
an overlay an "invalid" mint locks collateral for the whole tier, so the requirement must be known
exactly when the user signs (B3). The wallet chooses `evalHeight = indexTip − MINT_EVAL_LAG` so a
short reorg cannot change the snapshot it committed to (C4). The staleness a minter can exploit is
bounded to `MINT_WINDOW` = 40 blocks of price movement against a 300–1000 % collateral ratio.

### D18. Semantics of invalid YDollar transactions

**Decision (deterministic, applied by every node):** an invalid MINT registers a *void* vault
(collateral locked, no YDollar created; releasable at `lockHeight` with federation co-sign and zero
burn). An invalid TRANSFER burns all YDollar inputs. Any spend of a YDollar-bearing output that is
not assigned by a valid payload burns it. Any spend of a vault closes it and removes its collateral
from the total. This is the Runes "cenotaph" rule and it is the only rule that keeps the state
machine total (every chain has exactly one YDollar state).

### D19. Enshrinement constraint

**Decision:** the validator is written as pure functions of `(transaction, YDollarStateView,
height)` returning a typed verdict, with block-level `Apply`/`Undo` over an abstract key-value
view. This is the shape `ConnectBlock` would call in §9. No YDollar code may read wall-clock time,
the mempool, wallet state, or node configuration inside the validator.

### D20. Testing

**Decision:** Boost unit tests for every pure function; `qa/rpc-tests/ydollar_*.py` regtest tests
for every flow including reorg, restart and rebuild determinism (state hash equality); a
three-node regtest federation (2-of-3) that signs price transactions with `signrawtransaction` and
co-signs redemptions with `yd_cosignredeem`, so the whole protocol is tested without the Python
coordinator; a fuzz harness for the payload parser. Details in §7.

### D21. User interface

Options: (a) port DigiByte's Qt DigiDollar tabs into the node · (b) add a Qt (or other) GUI to
`ycash-dd` · (c) add a YDollar tab to **YecWallet** — the Qt 6 full-node GUI Ycash users already
run, which bundles `ycashd` and drives it over JSON-RPC — in a fork `yecwallet-dd`, driven
entirely by the `yd_*` RPCs · (d) RPC and `ycash-cli` only.

**Decision: (c), with `ycash-cli` as the first-class power-user and operator interface, and the
`yd_*` RPC surface frozen as the contract between the two forks.** (a) is impossible: Ycash has
no `src/qt/` to port into. (b) would add a GUI toolkit and a build-system branch to a node that
deliberately ships without one, and would duplicate what YecWallet already is. (d) is not a
product. (c) is how every Ycash wallet feature reaches users today (`ref/yecwallet`), and the
same toolkit as DigiByte's DigiDollar GUI, so DigiByte's `src/qt/digidollar*` is a close
behavioural reference — with one architectural difference that governs every line: DigiByte's
widgets read in-process `WalletModel`/`ClientModel` objects, YecWallet reads RPC JSON on a timer
(`mapping.md` §12). Cost: a second fork with its own diff budget (§4.7), a release process that
bundles the `ycash-dd` node into the wallet, and one screen — the redemption wizard — that talks
to something other than the local node (the operators' co-sign endpoints).

---

## 3. YDollar v1 protocol (normative)

Everything in this section is deterministic given the block sequence and the parameters. Words in
**bold caps** are rule identifiers used by the test plan.

### 3.1 Units and constants

| Name | Value | Notes |
|---|---|---|
| `CENT` | 1 | YDollar amounts are integer US cents; `100 = $1.00` |
| `MICRO_USD` | 1 | prices are integer micro-USD per YEC; `1,000,000 = $1.00` |
| `COIN` | 100,000,000 | zatoshi per YEC (existing) |
| `BLOCKS_PER_HOUR` | 48 | 75-second target spacing post-Blossom |
| `BLOCKS_PER_DAY` | 1,152 | |
| `PRICE_MAX_AGE` | 48 blocks | attestation older than this is not a price |
| `PRICE_MIN` / `PRICE_MAX` | 100 / 100,000,000 µUSD | $0.0001 – $100.00 per YEC (DigiByte bounds) |
| `MINT_WINDOW` | 40 blocks | protocol constant; equals `DEFAULT_POST_BLOSSOM_TX_EXPIRY_DELTA` (`ref/ycash/src/main.h:78-79`) but does not follow `-txexpirydelta` |
| `MINT_EVAL_LAG` | 2 blocks | **wallet-side, not protocol**: `evalHeight = indexTip − MINT_EVAL_LAG`, so a reorg shorter than 3 blocks cannot change the snapshot a mint committed to (C4); `-ydollarmintlag` overrides (0..36) |
| `ROSTER_GRACE` | 1,152 blocks | how long the previous roster stays mintable after its successor is revealed |
| `YD_FEE` | 1,000 zat | flat transaction fee, = `DEFAULT_FEE` (`ref/ycash/src/policy/fees.h:15`). Not only convention: ZIP-401's mempool limiter adds `LOW_FEE_PENALTY` to the eviction weight of any transaction paying less (`ref/ycash/src/mempool_limit.cpp:151-157`), so `-ydollarfee` is clamped to ≥ `DEFAULT_FEE` (C16) |
| `TOKEN_VALUE` | 10,000 zat | YEC carried by every YDollar output; ≥ 100× the dust floor (`GetDustThreshold`, `ref/ycash/src/primitives/transaction.h:460`) |
| `MIN_MINT` / `MAX_MINT` | 10,000 / 1,000,000 cents | $100 / $10,000 (param) |
| `MIN_OUTPUT` / `MAX_OUTPUT` | 100 / 10,000,000 cents | $1 (DigiByte's `minOutputAmount`) / $100,000 (param; DigiByte's `maxMintAmount`, C17) |
| `SUPPLY_CAP` | 100,000,000 cents | $1,000,000 mainnet v1 (param; 0 = none on regtest) |
| `MAX_PAYLOAD` | 80 bytes | Ycash `nMaxDatacarrierBytes − 3` |
| `HEALTH_CAP` | 30,000 % | as DigiByte |
| `VOL_1H_BPS` / `VOL_24H_BPS` | 2,000 / 3,000 | 20 % / 30 % |
| `VOL_COOLDOWN` | 1,728 blocks | 36 h, DigiByte's `COOLDOWN_BLOCKS` in Ycash blocks |
| `ROSTER_N` / `ROSTER_K` | 9 / 5 | mainnet & testnet; regtest 3 / 2 |

Lock tiers (`tierBlocks` at 75 s; ratios from `ref/digibyte/src/consensus/digidollar.h:72-84`):

| Tier | Period | `tierBlocks` | Ratio |
|---|---|---|---|
| 0 | 1 hour | 48 | 1000 % |
| 1 | 30 days | 34,560 | 500 % |
| 2 | 90 days | 103,680 | 400 % |
| 3 | 180 days | 207,360 | 350 % |
| 4 | 1 year | 420,480 | 300 % |

Per-network parameters (`src/ydollar/params.cpp`): `startHeight`, `genesisAnchor` (outpoint),
`genesisRosterScript` (the k-of-n redeem script, so the roster is known before its first spend),
address version bytes (D10), `SUPPLY_CAP`, `MAX_MINT`. Regtest takes the first three from
`-ydollarstartheight=<h>`, `-ydollargenesisanchor=<txid:n>` and `-ydollargenesisroster=<hex>`
(all three required together, refused on any other network) so tests can create the anchor on
chain first and then restart with `-ydollar` (C2).

**Regtest overrides** (`params.cpp`, network `"regtest"` only; ratios, formulas and every rule are
identical, only block counts shrink so a test can walk through a full lifecycle in seconds — the
protocol is height-based and never reads a clock, so this changes nothing but the numbers):

| Parameter | Mainnet / testnet | Regtest |
|---|---|---|
| `tierBlocks` tiers 0–4 | 48 / 34,560 / 103,680 / 207,360 / 420,480 | 48 / 96 / 144 / 192 / 240 |
| `ROSTER_GRACE` | 1,152 | 48 |
| `VOL_COOLDOWN` | 1,728 | 96 |
| `PRICE_MAX_AGE`, `MINT_WINDOW`, `MINT_EVAL_LAG` | 48 / 40 / 2 | unchanged (tied to expiry and reorg depth, not to time) |
| volatility windows `BLOCKS_PER_HOUR` / `BLOCKS_PER_DAY` (§3.6) | 48 / 1,152 | 48 / 96 (G5) |
| `ROSTER_N` / `ROSTER_K` | 9 / 5 | whatever the test's genesis roster script says (2-of-3 for fast tests, 5-of-9 for the production-shape tests, §6.0) |
| `SUPPLY_CAP` | 100,000,000 cents | 0 (none) unless `-ydollarsupplycap` is passed |

### 3.2 Payload encoding

The YDollar payload is the data of the transaction's **only** `OP_RETURN` output (policy forbids
two), and that output must be exactly `OP_RETURN <one push of 4..80 bytes>`; `Solver` accepts any
push-only tail as `TX_NULL_DATA` (`ref/ycash/src/script/standard.cpp:102`), so this shape rule is
ours (B12). A transaction with an `OP_RETURN` that does not have this shape or does not begin with
the magic is a non-YDollar transaction (its inputs are still processed by **IN-1..3** below).
All multi-byte integers are fixed-width little-endian; nothing in the payload uses `CompactSize`
or `VARINT` (B11).

```
magic   2 bytes   0x59 0x44 ("YD")
version 1 byte    0x01
type    1 byte    0x01 MINT | 0x02 TRANSFER | 0x03 REDEEM | 0x10 PRICE
body    variable  per type; total ≤ 80 bytes; trailing bytes → malformed
```

| Type | Body | Size (incl. 4-byte header) |
|---|---|---|
| MINT | `tier u8`, `cents u32le`, `lockHeight u32le`, `evalHeight u32le`, `ownerPubKey 33 B compressed` | 50 |
| TRANSFER | `count u8`, then `count ×` (`vout u8`, `cents u32le`) | 5 + 5·count → count ≤ 15 |
| REDEEM | same body as TRANSFER (assigns YDollar change); `count` may be 0 | |
| PRICE | `priceMicroUsd u64le` | 12 |

There is no rotation payload: a roster rotation is an anchor spend whose `vout[0]` pays a
different P2SH, with no `OP_RETURN` at all (§3.7, C9).

Malformed payload (bad magic/version/type, short/long body, `vout` out of range, duplicate `vout`,
`vout` pointing at the `OP_RETURN`, `cents == 0`) ⇒ the transaction is treated as **non-YDollar**
for outputs and as an ordinary spend for inputs (**IN-1..3**). Unknown `type` ⇒ same. This is the
forward-compatibility rule: a future version bump is ignored by v1 nodes, never mis-parsed.

One more encoding rule, for determinism: a transaction with **more than one** `OP_RETURN` output
(non-standard, but a miner may include it) is non-YDollar regardless of contents. The decoder is a
bounds-checked reader over a `std::vector<unsigned char>`; it never uses `CDataStream` so it cannot
throw.

### 3.3 Scripts

**Roster script** (also the anchor's redeem script). Keys must be 33-byte compressed encodings
(the size arithmetic in D3 depends on it; a 65-byte key is rejected everywhere a roster is built or
parsed, D7), sorted ascending so every party derives the same script:

```
<k> <Q1> … <Qn> <n> OP_CHECKMULTISIG            (k=5, n=9 mainnet)
```

**Vault script** (redeem script of the P2SH collateral output; `Q1…Qn` in the same sorted order):

```
<lockHeight> OP_CHECKLOCKTIMEVERIFY OP_DROP
<ownerPubKey> OP_CHECKSIGVERIFY
<k> <Q1> … <Qn> <n> OP_CHECKMULTISIG
```

`lockHeight` is pushed as a minimal `CScriptNum` and must be `< LOCKTIME_THRESHOLD`
(`ref/ycash/src/script/script.h:30`), i.e. a block height.

**Vault scriptSig** (built by `yd_redeem` + co-signers; stack order matters):

```
OP_0 <qsig_1> … <qsig_k> <ownerSig> <vaultScript>
```

The spending transaction sets `nLockTime = lockHeight`, `vin[0].nSequence = 0xFFFFFFFE`, and a
normal `nExpiryHeight` (tip + 40); Ycash's `CheckFinalTx` then admits it once the tip is at or above
`lockHeight` (`ref/ycash/src/main.cpp:1566`). Its `STANDARD_LOCKTIME_VERIFY_FLAGS` is
`LOCKTIME_MEDIAN_TIME_PAST` (`ref/ycash/src/consensus/consensus.h:49`), which affects only
time-based locks; vault locks are heights (F5). Signature hash: `SignatureHash(vaultScript, tx, nIn,
SIGHASH_ALL, vaultValue, consensusBranchId)` as `ref/ycash/src/rpc/atomicswap.cpp:760-762`, with
`consensusBranchId = CurrentEpochBranchId(chainActive.Height() + 1, consensus)` for **every**
signer (owner and co-signers) — the convention `signrawtransaction` uses
(`ref/ycash/src/rpc/rawtransaction.cpp:1024`); it differs from the atomic-swap code's `Height()`
only at an upgrade boundary, and no upgrade is scheduled (NU5 is `NO_ACTIVATION_HEIGHT` on every
network). Signatures must be placed in the scriptSig in roster key order; the combiner sorts them by
matching each signature to a key with `CPubKey::Verify`.

Relay constraints the spend already satisfies, and that tests must pin: mempool verification uses
`STANDARD_SCRIPT_VERIFY_FLAGS` (`ref/ycash/src/policy/policy.h:32-40`), so pushes must be minimal
(`MINIMALDATA`: `lockHeight` as a minimal `CScriptNum`, `k`/`n` as `OP_5`/`OP_9`, the dummy as
`OP_0`), exactly one element may remain after execution (`CLEANSTACK`: `CHECKMULTISIG` leaves one
`true`), and signatures must be low-S (`LOW_S`: `CKey::Sign` produces normalized signatures).
`AreInputsStandard` accepts a P2SH input whose redeem script is not a standard template as long
as it has ≤ 15 accurate sigops (`ref/ycash/src/policy/policy.cpp:173-178`) — the same path the
atomic-swap HTLC relies on. The anchor's redeem script *is* a template (`TX_MULTISIG`), so its
scriptSig must hold exactly `OP_0`, `k` signatures and the script (`ScriptSigArgsExpected` = k + 1,
`ref/ycash/src/script/standard.cpp:146-149`; `policy.cpp:182-183`) — which is what
`signrawtransaction`'s combiner produces. `IsStandard`'s "x-of-3" limit (`policy.cpp:42-50`)
applies to **bare** multisig outputs only; anchors and vaults are P2SH and unaffected (C15).

The signature combiner matches each returned signature to a roster key with `CPubKey::Verify`
over the DER bytes **without** the trailing hashtype byte (C24), and places them in roster key
order; a co-signer verifies the owner's signature the same way under the branch ID it would
itself sign with, so a branch-ID disagreement surfaces as a RED-7 refusal (C11).

**YDollar token output**: `OP_DUP OP_HASH160 <keyHash> OP_EQUALVERIFY OP_CHECKSIG` with value
`TOKEN_VALUE`. The overlay does not require this shape or value (any non-`OP_RETURN` output may be
assigned YDollar); the wallet always produces this shape.

### 3.4 Transaction templates (what the wallet builds)

**MINT** (`yd_mint <cents> <tier>`):

| Index | Output | Value |
|---|---|---|
| vin[*] | wallet YEC inputs (never YDollar-bearing, never vaults) | |
| vout[0] | P2SH(vaultScript) | exactly `requiredZat(cents, tier, Snapshots[evalHeight])` (§3.6), rounded up to a multiple of 1,000 zat |
| vout[1] | P2PKH(owner's fresh key) — receives all minted cents | `TOKEN_VALUE` |
| vout[2] | `OP_RETURN` MINT payload | 0 |
| vout[3] | YEC change (optional) | |

With `indexTip` the index's synced height and `L = MINT_EVAL_LAG` (default 2, C4):
`evalHeight = indexTip − L`; `nExpiryHeight = evalHeight + MINT_WINDOW` (so the mint cannot
confirm at `H > evalHeight + MINT_WINDOW`, MINT-2); `lockHeight = evalHeight + tierBlocks +
MINT_WINDOW`. For every height the transaction can confirm at, `H ∈ [indexTip + 1, evalHeight +
40]`, this gives `tierBlocks ≤ lockHeight − H ≤ tierBlocks + 39 − L ≤ tierBlocks + MINT_WINDOW`,
so MINT-2 holds at every possible confirmation height; and the mempool's expiring-soon rule
(`nextHeight + 3 ≤ nExpiryHeight`) holds for `L ≤ 36`. Because every input to MINT-4/5 is fixed at
`evalHeight`, the wallet knows before signing whether the mint will register; the 2 % margin of
revision 2 is gone (B3), and a reorg must be longer than `L` blocks to disturb the snapshot.

**TRANSFER** (`yd_send`, `yd_sendmany`): YDollar inputs (confirmed only) + YEC fee inputs
(confirmed only, F3);
outputs: one `TOKEN_VALUE` P2PKH per recipient, one for YDollar change, `OP_RETURN` TRANSFER
payload assigning cents to those vouts, YEC change.

**REDEEM** (`yd_redeem <vaultTxid>`): `vin[0]` = vault outpoint; `vin[1..]` = YDollar inputs
totalling ≥ `requiredBurn` (§3.7). **No YEC inputs** (C10): every YDollar input carries
`TOKEN_VALUE` = 10 × `YD_FEE` and a VOID release has the collateral itself. Outputs: collateral to
the owner's address (value = vault value + surplus token value − `YD_FEE` − `TOKEN_VALUE` × number
of YDollar change outputs), optional YDollar change (`TOKEN_VALUE`) with a REDEEM payload
(`count = 0` if none, but the payload is still present so the transaction is self-describing).

**PRICE** (federation coordinator, built by `yd_createpricetx`): `vin[0]` = current anchor;
at most one refill input, **absorbed entirely into the new anchor** (no change output, C6);
`vout[0]` = P2SH(rosterScript) — the **same** script as the spent anchor (the new anchor, value =
anchor + refill − `YD_FEE`); `vout[1]` = `OP_RETURN` PRICE. Exactly two outputs.

**ROTATION** (federation, rare): `vin[0]` = current anchor, optional refill as above, `vout[0]` =
P2SH(*new* roster script), **no `OP_RETURN`** (C9). Exactly one output.

### 3.5 State

```
Tip            { height, blockHash, schemaVersion, network }
Params         (in code)
Anchor         { outpoint, nValue, scriptPubKey }
Rosters        ordered list of { script, revealHeight }; Rosters[0] = { genesisRosterScript, startHeight }
Prices         height → priceMicroUsd            (only heights with a valid attestation; last in block wins)
Vaults         outpoint → { ownerPubKey, tier, lockHeight, collateralZat, mintedCents,
                             mintHeight, status ∈ {ACTIVE, VOID, CLOSED}, closeHeight,
                             closingTxid, burnedCents, errBpsAtClose, requiredBurnAtClose,
                             rosterIndex }
Tokens         outpoint → { cents, nValue, scriptPubKey, height }
TxLog          txid → { height, type, verdict, ydIn, ydOut, burned, assigned[] (outpoint, cents,
                        scriptPubKey), closedVaults[] }   (every payload-bearing tx and every tx
                        spending a Tokens/Vaults/Anchor outpoint; source for history RPCs, E1)
Totals         { supplyCents, collateralZat, activeVaults, voidVaults }
Volatility     { lastBreachHeight }              (mint freeze until lastBreachHeight + VOL_COOLDOWN)
Snapshots      height → { blockHash, supplyCents, collateralZat, price, healthPct, dcaBps, errBps, mintFrozen }
Undo           blockHash → list of inverse operations for that block
```

`Snapshots` are written for every block ≥ `startHeight` (≈ 60 bytes each) and are what
`yd_gethistory` and the Phase-B consensus rule read.

### 3.6 Derived quantities (integer, `arith_uint256`)

**Price at height H** — `price(H)`: the entry in `Prices` with the greatest height `h ≤ H` such
that `H − h ≤ PRICE_MAX_AGE`; undefined otherwise.

**Health** — with `S = supplyCents`, `C = collateralZat` **as they stand immediately before the
transaction being evaluated** (earlier transactions in the same block have already been applied),
and `p = price(H)`:

```
health(H) = HEALTH_CAP                              if S == 0
          = 0                                       if p undefined      (fail closed)
          = min(HEALTH_CAP, floor(C · p / (COIN · S · 100)))   otherwise
```
(Check: 1 000 YEC at $0.05 backing $10 → `1e11·5e4 / (1e8·1000·100)` = 500 %.)

**DCA multiplier** (`ref/digibyte/src/consensus/dca.cpp:53-58`):

| health | `dcaBps` |
|---|---|
| ≥ 150 | 10,000 |
| 120–149 | 12,500 |
| 110–119 | 15,000 |
| < 110 | 20,000 |

**Required collateral** for `cents` at tier ratio `R %` (DigiByte's formula, `txbuilder.h`
`CalculateRequiredCollateral`):

```
requiredZat = ceil( cents · R · dcaBps · COIN / (100 · p) )
```

Worst case magnitude `1e7 · 1000 · 20000 · 1e8 ≈ 2e22` exceeds 64 bits, hence `arith_uint256`.

**ERR ratio** (`ref/digibyte/src/consensus/err.cpp:38-41,53`):

| health | `errBps` |
|---|---|
| ≥ 100 | 10,000 (ERR inactive) |
| 95–99 | 9,500 |
| 90–94 | 9,000 |
| 85–89 | 8,500 |
| < 85 | 8,000 |

**Required burn** to release a vault that minted `M` cents: `requiredBurn = ceil(M · 10000 / errBps)`
(`err.cpp:100`).

**Volatility** — let `p0 = price(H)`, `p1 = price(H − BLOCKS_PER_HOUR)`, `p24 = price(H −
BLOCKS_PER_DAY)` (each undefined ⇒ that window is not evaluated). `breach(H)` iff
`|p0 − p1| · 10000 ≥ VOL_1H_BPS · p1` or `|p0 − p24| · 10000 ≥ VOL_24H_BPS · p24`. If `breach(H)`,
`lastBreachHeight := H`. `mintFrozen(H)` iff `H ≤ lastBreachHeight + VOL_COOLDOWN`.

### 3.7 Rules

Blocks below `startHeight` are ignored completely (not even the tip is recorded). At `startHeight`
the block is applied without a parent check and must contain the genesis anchor transaction with
`vout[genesisAnchor.n].scriptPubKey == P2SH(HASH160(genesisRosterScript))`, otherwise the index is
unhealthy (B9); `Anchor` and `Rosters[0]` are initialised from `Params` **before** any transaction
of that block is processed, so a spend of the genesis anchor inside block `startHeight` is seen
(E6). Within a block, transactions are processed in block order and each transaction's inputs are
processed before its outputs. Every transaction that carries a payload or spends a `Tokens`,
`Vaults` or `Anchor` outpoint gets a `TxLog` entry (E1).

**IN-1** Every input that spends an outpoint in `Tokens` removes it and adds its cents to `ydIn`.
**IN-2** Every input that spends an outpoint in `Vaults` with status ACTIVE or VOID sets the vault
to CLOSED (`closeHeight = H`, `closingTxid`, `errBpsAtClose = Snapshots[H − 1].errBps`,
`requiredBurnAtClose = RequiredBurn(mintedCents, errBpsAtClose)` for ACTIVE and 0 for VOID, F1),
and, if it was ACTIVE, subtracts its `collateralZat` from `Totals.collateralZat` and decrements
`activeVaults`.
**IN-3** After outputs are processed, `burned = ydIn − ydOut`; `Totals.supplyCents −= burned`;
`burned` is recorded on every vault closed by this transaction (split is informational).

**TX-0** A transaction with any shielded component (`vJoinSplit`, `vShieldedSpend`,
`vShieldedOutput` non-empty or `valueBalance ≠ 0`) or that is a coinbase has `ydOut = 0` regardless
of payload.

**MINT-1** payload MINT, well-formed. **MINT-2** `tier ∈ {0..4}`, `MIN_MINT ≤ cents ≤ MAX_MINT`,
`lockHeight < LOCKTIME_THRESHOLD`, `tierBlocks ≤ lockHeight − H ≤ tierBlocks + MINT_WINDOW`
(DigiByte's canonical window, `validation.cpp:1377`), `startHeight ≤ evalHeight ≤ H` and
`H − evalHeight ≤ MINT_WINDOW`. **MINT-3** `vout.size() ≥ 3`; `vout[0]` is P2SH and its hash
equals `HASH160(vaultScript(lockHeight, ownerPubKey, roster))` for `roster = Rosters.back()`, or
`roster = Rosters[size−2]` if `H ≤ Rosters.back().revealHeight + ROSTER_GRACE` (rotation grace,
B21); `ownerPubKey` is a valid compressed key. **MINT-4** with `E = Snapshots[evalHeight]`:
`E.price` defined; `E.healthPct ≥ 100` (else `minting-blocked-during-err`, `validation.cpp:2707`);
`¬E.mintFrozen`. **MINT-5** `vout[0].nValue ≥ requiredZat(cents, tier, E.price, E.dcaBps)`.
**MINT-6** `Totals.supplyCents + cents ≤ SUPPLY_CAP` (if cap ≠ 0), evaluated at `H`. **MINT-7**
`vout[1]` is not the `OP_RETURN`. MINT-4 and MINT-5 read only the snapshot, so they are a pure
function of the payload and a block every node has already applied (B3).

If MINT-1..7 hold: `Vaults[txid:0] = ACTIVE {…}`, `Tokens[txid:1] = cents`, `supplyCents += cents`,
`collateralZat += vout[0].nValue`, `ydOut = cents`. If MINT-1 holds but any of MINT-2..7 fails and
`vout[0]` is P2SH: `Vaults[txid:0] = VOID` (so it can be tracked and released), `ydOut = 0`. Note
that `ydIn` in a MINT is always burned (a mint never assigns YDollar to outputs other than by
minting).

**XFER-1** payload TRANSFER or REDEEM, well-formed; every assigned `vout` exists and is not the
`OP_RETURN`; `MIN_OUTPUT ≤ cents ≤ MAX_OUTPUT` per assignment. **XFER-2** `Σ assigned cents ≤
ydIn` (TRANSFER and REDEEM share this rule; the difference `ydIn − Σ` is burned — for a TRANSFER
built by the wallet it is always 0, for a REDEEM it is the burn). **XFER-3** `ydIn > 0`.

If XFER-1..3 hold: each assignment creates `Tokens[txid:vout] = cents`; `ydOut = Σ`. If XFER-1 or
XFER-3 fails, or `Σ > ydIn`, nothing is assigned and `ydOut = 0` (all inputs burned, D18). This is
the most forgiving rule that is still total: an honest wallet bug that under-assigns loses only the
unassigned remainder, never the whole input.

**PRICE-1** some input `vin[i].prevout == Anchor.outpoint` (any index — the anchor is consumed
wherever it sits). **PRICE-2** `vout[0]` is P2SH. If both hold the anchor moves: `Anchor = {txid:0,
vout[0].scriptPubKey}`; the redeem script (last push of `vin[i].scriptSig`) is appended to
`Rosters` with `revealHeight = H` iff it parses as `<k> <keys…> <n> OP_CHECKMULTISIG` with
`1 ≤ k ≤ n ≤ 13` and differs from `Rosters.back().script` (a non-parseable script moves custody but
never becomes a roster). **PRICE-3** payload PRICE with `PRICE_MIN ≤ price ≤ PRICE_MAX`, PRICE-1
and PRICE-2 held, **and `vout[0].scriptPubKey` equals the spent anchor's `scriptPubKey`** (B8) ⇒
`Prices[H] = price`; if several anchor spends chain inside one block, the last one in block order
wins (B7). An anchor spend that changes the script (a rotation, C9), or carries a malformed or
absent payload, moves the anchor without recording a price. An anchor spend whose `vout[0]` is not P2SH
breaks the chain of custody: `Anchor` becomes null and no further prices are accepted until a
software release with a new genesis anchor (operator failure, §8). A PRICE payload on a transaction
that does not spend the anchor is non-YDollar.

**SNAP** After the last transaction of the block: recompute `breach(H)`, write `Snapshots[H]`.

**UNDO** Every mutation in the block is logged; `Undo[blockHash]` reverses them exactly. Applying
then undoing a block must restore byte-identical state (tested).

### 3.8 Policy checks (wallet and federation, not state rules)

These are computed by `yd_validaterawtransaction` and used by the wallet before broadcasting and by
federation members before co-signing. They do **not** change the state machine (D18) but they are
the rules §9 would promote to consensus.

- **RED-0** the co-signer's index is healthy and `synced` (its tip is `chainActive.Tip()`);
  otherwise refuse without evaluating anything else (B20). An unsynced-but-healthy refusal is
  reported as *transient* (the notifier trails the tip by up to a second) and the client retries
  (E2).
- **RED-1** `vin[0]` spends an ACTIVE or VOID vault; the transaction spends no other vault.
- **RED-2** `nLockTime ≥ vault.lockHeight` and `indexTip ≥ vault.lockHeight`.
- **RED-3** `ydIn − ydOut ≥ requiredBurn(vault.mintedCents, health(indexTip))` (0 for VOID).
- **RED-4** the transaction is transparent-only, standard, and pays a fee in
  `[YD_FEE, 100 × YD_FEE]`. `IsStandardTx(tx, reason, Params(), tip + 1)` and
  `AreInputsStandard(tx, view, branchId)` run against a `CCoinsViewCache` built exactly as
  `signrawtransaction` builds it — `pcoinsTip` behind `CCoinsViewMemPool` under `cs_main`
  (`ref/ycash/src/rpc/rawtransaction.cpp:906-921`) — because the fee needs every input's value and
  `AreInputsStandard` every input's `scriptPubKey`, which only the UTXO set has (C1; regtest does
  not run these checks itself, B5). **Before either call**, every input must be present and
  unspent in that view (`HaveCoins` + `IsAvailable`), because `GetOutputFor` and `GetValueIn`
  assert it (`ref/ycash/src/coins.cpp:898-903,912`); any miss ⇒ refuse (D1).
- **RED-6** for an ACTIVE vault, `price(indexTip)` is defined. During an oracle outage co-signers
  pause redemptions of ACTIVE vaults; they never compute a burn from `health = 0`. A VOID vault
  needs no burn and no price, so its release is not blocked (E3).
- **RED-7** the owner signature already present in `vin[0].scriptSig` verifies against
  `ownerPubKey` for the sighash of this transaction (`CPubKey::Verify`, hashtype byte stripped),
  computed over the vault script **reconstructed from the index record** (`lockHeight`,
  `ownerPubKey`, roster) and the vault value from the index — never over the script or value the
  caller supplied — so a co-signer never adds a signature to a transaction the owner did not
  authorise and can never be used to sign anything but a real vault spend (C5).
- **RED-8** `nExpiryHeight ≤ indexTip + 40 + RED_SKEW` with `RED_SKEW = 2`, so a fully co-signed
  transaction cannot be held and broadcast later under different health, while an owner whose node
  is a block or two ahead of the co-signer's is not refused (E2).
- **SUB-1** (owner's node, in `yd_submitredeem`) the returned transaction equals the one
  `yd_redeem` produced — held in the node's `PendingRedemption` record for that vault (D3) — except
  for additional signature pushes in `vin[0].scriptSig`, every input
  passes `VerifyScript` under `STANDARD_SCRIPT_VERIFY_FLAGS`, `chainActive.Height() ≥ lockHeight`
  and `nExpiryHeight ≥ chainActive.Height() + 1 + TX_EXPIRING_SOON_THRESHOLD` — all **before**
  `CommitTransaction`, which records the transaction in the wallet before it tries the mempool
  (`ref/ycash/src/wallet/wallet.cpp:5723-5747`, C22). The owner's `SIGHASH_ALL` signature already
  makes any other change invalid; SUB-1 turns that into an explicit, testable check.
- **MINTPOL-1** the wallet builds only when its index is `synced`, `indexTip ≥ startHeight +
  MINT_EVAL_LAG` (D5), `evalHeight = indexTip − MINT_EVAL_LAG` has a defined price, `healthPct ≥
  100` and `¬mintFrozen`, and `supplyCents + cents ≤ SUPPLY_CAP`; it sets `vout[0].nValue` to exactly the snapshot's requirement (rounded up
  to 1,000 zat). Keys come from `GetKeyFromPool`, which generates a fresh key if the pool is empty
  and the wallet is unlocked (`ref/ycash/src/wallet/wallet.cpp:6005-6022`, C8). It warns when the
  remaining supply cap is below `10 × MAX_MINT`, the one condition (MINT-6) it cannot fix at
  `evalHeight`.

Co-signers do not check where the collateral goes: the owner signs every output with
`SIGHASH_ALL`, so only the owner can decide that, and only the owner can be harmed by it.

### 3.9 Roster rotation

The federation rotates by publishing a ROTATION transaction — an anchor spend paying to the new
roster script with no `OP_RETURN` (C9) — immediately followed by a PRICE transaction from the new
anchor (which reveals the new script). Wallets read `yd_getroster` (returns `Rosters.back()` and its pubkeys) before every mint.
MINT-3 accepts the current or previous roster, so a mint built just before a rotation still
registers, but only for `ROSTER_GRACE` (1,152 blocks, one day) after the new roster is revealed
(B21). Old roster members must retain their keys until every vault that references their roster is
CLOSED; `yd_listvaults` reports the count per roster index for the runbook. With v1 tiers capped at
one year, this obligation is bounded to one year and one day past rotation.

### 3.10 Determinism requirements for implementers

The validator and state machine may read only: the block being applied, the state view, and
`Params`. Forbidden: `GetTime()`, `GetAdjustedTime()`, `mempool`, `pwalletMain`, `GetArg`, floating
point, `std::map` iteration order that depends on pointers. Every function in `src/ydollar/state.*`
must be callable from a unit test with an in-memory view.

---

## 4. Architecture in `ycash-dd`

### 4.1 Diff budget

Target for the whole feature at the end of Phase 6:

| Existing file | Lines changed | What |
|---|---|---|
| `src/init.cpp` | ≈ 40 | help text, `-prune` incompatibility check, regtest-only argument check, index open/sync/close, register validation interface, `-reindex-ydollar`, wallet-RPC registration under `ENABLE_WALLET` |
| `src/experimental_features.{h,cpp}` | ≈ 8 | `fExperimentalYDollar` |
| `src/rpc/register.h` | ≈ 6 | `RegisterYDollarRPCCommands`, `RegisterYDollarWalletRPCCommands` |
| `src/rpc/client.cpp` | ≈ 15 | numeric-argument conversions for `yd_*` |
| `src/Makefile.am`, `src/Makefile.test.include` | ≈ 25 | new sources and tests |
| `qa/pull-tester/rpc-tests.py` | ≈ 6 | new tests |
| `qa/rpc-tests/test_framework/util.py`, `qa/rpc-tests/multi_rpc.py` | 2 | `zcash.conf` → `ycash.conf` so the inherited framework can start a Ycash node at all (G1) |
| `src/main.cpp`, `src/consensus/*`, `src/script/*`, `src/primitives/*`, `src/chainparams.cpp`, `src/wallet/wallet.{h,cpp}`, `src/wallet/rpcwallet.cpp`, `src/txdb.*`, `configure.ac` | **0** | |

Everything else is new files under `src/ydollar/`, `src/rpc/ydollar*.cpp`, `src/test/ydollar_*`,
`src/fuzzing/YDollar*/`, `qa/rpc-tests/ydollar_*.py`, `contrib/ydollar/`, `doc/ydollar.md`, and one fork-local CI workflow
(`.github/workflows/ydollar-tests.yml`; Ycash's own CI runs only the `book.yml` docs job and no
functional tests, B6).

### 4.2 New modules

```
src/ydollar/
  params.{h,cpp}      Params per network (§3.1), lookup by CChainParams::NetworkIDString()
  amount.h            cents/µUSD typedefs, arith helpers (RequiredCollateral, Health, DcaBps,
                      ErrBps, RequiredBurn) — arith_uint256 only
  payload.{h,cpp}     Encode/Decode payload (§3.2); FindPayload(const CTransaction&)
  script.{h,cpp}      RosterScript(keys,k), VaultScript(lock, owner, roster), Parse*,
                      BuildVaultScriptSig(sigs, ownerSig, script), ExtractRedeemScript(scriptSig)
  address.{h,cpp}     YDollar address encode/decode (D10) over CKeyID
  view.h              Abstract StateView (Get/Put/Erase for each table) + in-memory impl for tests
  state.{h,cpp}       ApplyBlock(view, block, height, undo&), UndoBlock(view, undo),
                      ProcessTx(...) implementing §3.7; Verdict struct; Policy checks §3.8
  db.{h,cpp}          CDBWrapper-backed StateView; batch commit per block; tip + undo storage
  index.{h,cpp}       class YDollarIndex : public CValidationInterface — ChainTip handler,
                      startup SyncToChain(), health flag, cs_ydollar lock, accessors for RPC
  wallet.{h,cpp}      (ENABLE_WALLET) coin locking, balance, listunspent, positions; uses only
                      public CWallet API
  txbuilder.{h,cpp}   (ENABLE_WALLET) BuildMint/BuildTransfer/BuildRedeem on
                      CreateNewContextualCMutableTransaction, flat YD_FEE, smallest-first inputs,
                      SignSignature for P2PKH inputs, manual vault sighash, AddCosignature,
                      IsComplete, SameExceptSignatures (SUB-1); BuildPriceTx / BuildRotationTx
                      (node context, no wallet) for yd_createpricetx
  policy.{h,cpp}      (node context) CheckRedeem (RED-0..8) over a CCoinsViewCache the caller
                      builds from pcoinsTip + CCoinsViewMemPool under cs_main (C1); pure given
                      the view, the index tip and the transaction
src/rpc/ydollar.cpp          node-context RPCs (work with pwalletMain == nullptr, C21)
src/rpc/ydollarwallet.cpp    wallet-context RPCs

Build placement (E8, `ref/ycash/src/Makefile.am:267,324,413`): `params`, `amount`, `payload`,
`script`, `address`, `view`, `state` → `libbitcoin_common` (linked by `test_bitcoin` and every
binary); `db`, `index`, `policy`, `rpc/ydollar.cpp` → `libbitcoin_server`; `wallet`, `txbuilder`,
`rpc/ydollarwallet.cpp` → `libbitcoin_wallet` under `ENABLE_WALLET`.
contrib/ydollar/ydollar_fed.py      federation coordinator (§5)
contrib/ydollar/ydollar-redeem      user-side co-signature collector (§5)
```

The node has no networking code of its own for YDollar: it never opens a connection, never runs a
background operation, and every YDollar action is a synchronous RPC.

### 4.3 Hook points (with citations)

| Where | What | Why it is safe |
|---|---|---|
| `init.cpp` after wallet load (`CWallet::InitLoadWallet`, `ref/ycash/src/init.cpp:1782`), immediately before the notifier thread starts (`init.cpp:1831-1847`) | `if (fPruneMode) InitError`; `g_ydollar = new YDollarIndex(...)`; `g_ydollar->SyncToChain()`; `RegisterValidationInterface(g_ydollar)` | Nothing else runs yet (block import is step 10, networking step 11), so the index is at `chainActive.Tip()` when notifications begin. Registered after the wallet, so `boost::signals2` delivers each signal to the wallet first; the index does not depend on that |
| `CValidationInterface::ChainTip(pindex, pblock, added)` (`ref/ycash/src/validationinterface.h:40`) | `added.has_value()` ⇒ `ApplyBlock`; else `UndoBlock`; then reconcile coin locks | Same signal, same ordering guarantees, same thread the wallet's witness cache relies on |
| `CValidationInterface::SyncTransaction(tx, pblock, height)` (`validationinterface.h:38`), called with `pblock == NULL` for mempool arrivals, conflicted transactions **and every transaction of a disconnected block** (`validationinterface.cpp:183,210,226` — indistinguishable by arguments, C3), and with the block, before `ChainTip`, for every transaction of a connected block | **required**: pre-lock every output that a well-formed payload assigns (`vout[1]` of a MINT, each assigned `vout` of a TRANSFER/REDEEM) whose script is mine (B4), for `height ≥ startHeight`; record the decoded payload for `yd_gettxinfo` | Never mutates YDollar state; a pre-lock on an output that later confirms with no cents is released by `ChainTip` (C3) |
| `Shutdown()` in `init.cpp`, immediately after `StopRPC()` (`init.cpp:210`) | `UnregisterValidationInterface(g_ydollar)`; then under `cs_ydollar`: `Stop()` and `Flush(fSync = true)`; the object is **never deleted** | On the normal path the notifier thread has already been joined (`bitcoind.cpp:52-55`); on the startup-failure path it has not (`bitcoind.cpp:191-194`) and a `ChainTip` call may be in flight — taking `cs_ydollar` waits it out and `Stop()` makes later calls return immediately (D2). Same lifetime rule as Ycash's other globals |

**Lock order (B15):** `cs_main → cs_wallet → cs_ydollar`. The two handlers above run on the
notifier thread, which must not take `cs_main` (`validationinterface.cpp:162-166`; the wallet's
own handler bends this for a block locator, `wallet.cpp:636-641`, but the index never does): they
take `cs_ydollar` for the state update, collect the outpoints to lock or release, release
`cs_ydollar`, then take `pwalletMain->cs_wallet` for `LockCoin`/`UnlockCoin` (which assert
`cs_wallet`, `wallet.cpp:6265-6275`). `IsMine` needs only `cs_KeyStore`. RPC handlers take
`LOCK2(cs_main, pwalletMain->cs_wallet)` and then `cs_ydollar`, and never call back into the
wallet while holding `cs_ydollar`. With `-disablewallet` (`pwalletMain == nullptr`) the locking
steps are skipped and everything else is unchanged (C21).

Idempotence rules for the handler (B17): blocks with `pindex->nHeight < startHeight` are ignored
and leave no trace. At `nHeight == startHeight` the block is applied with no parent check and
becomes the tip. Above it: if `pindex->nHeight ≤ tip.height` and `Snapshots[nHeight].blockHash`
equals `pindex->GetBlockHash()`, skip (already applied during `SyncToChain`, E4); if
`pindex->pprev->GetBlockHash() ≠ tip.hash`, mark the index unhealthy (never apply out of order). On
disconnect, if `pindex->GetBlockHash() ≠ tip.hash`, skip if the block is below `startHeight` or not
in the index, else mark unhealthy.

`SyncToChain()` at startup: walk back from the stored tip using `Undo` while the stored tip is not
in `chainActive` (reorg while offline); then apply forward from `tip.height + 1` to
`chainActive.Height()` reading blocks with `ReadBlockFromDisk`. If an undo record is missing, the
DB schema version differs, the stored network differs, or `chainActive.Tip()` is null or below
`startHeight` (the `-reindex` case, where the notifier will deliver every block from genesis), wipe
and start empty (logged; also forced by `-reindex-ydollar`). Undo records older than `tip − 1,000`
are pruned (B10): the node itself refuses reorgs longer than `MAX_REORG_LENGTH = 99`
(`ref/ycash/src/main.h:62`, `main.cpp:3772`), and the one deeper case — `RewindBlockIndex` after a
network-upgrade release (`init.cpp:1695`) — is exactly the "stored tip not in `chainActive`" walk
above, falling back to wipe-and-rebuild when it runs out of undo records. Per-block batches are
written unsynced (`CDBWrapper::WriteBatch`, `ref/ycash/src/dbwrapper.h:238`); a crash can lose the
last few, which `SyncToChain` repairs on the next start; the shutdown flush and the end of
`SyncToChain` use `fSync = true` (D8).

Genesis-anchor check (A11, B9): part of `ApplyBlock` at `H == startHeight` — the block must contain
`genesisAnchor.txid`, and that output's `scriptPubKey` must equal
`P2SH(HASH160(genesisRosterScript))`; otherwise the index is marked unhealthy with a message naming
the mismatch. `SyncToChain` performs the same check at init whenever block `startHeight` is already
on disk, so a misconfigured release fails at first start rather than at first block.

Every `ChainTip` override is wrapped in `try { … } catch (...)`: on any exception the index logs,
sets `unhealthy = reason`, and returns; it never throws into `ThreadNotifyWallets` (which does not
wrap block callbacks, `ref/ycash/src/validationinterface.cpp:223-233`).

Unhealthy state: every `yd_*` RPC except `yd_getinfo` returns `RPC_MISC_ERROR "ydollar index
unhealthy: <reason>; restart with -reindex-ydollar"`. The node itself never stops or fails a block
because of YDollar.

### 4.4 RPC surface

All commands use Ycash's `fHelp` + `UniValue params` convention and are gated by
`fExperimentalYDollar` (pattern: `ref/ycash/src/rpc/atomicswap.cpp:1753`).

Node context (`src/rpc/ydollar.cpp`):

| Command | Purpose |
|---|---|
| `yd_getinfo` | enabled, `rpcversion`, `network` (`main`/`test`/`regtest`, so a GUI never infers it from `getinfo.testnet`, H3), network params, index height/hash, `synced` (index tip == `chainActive.Tip()`), health flag, anchor, roster index |
| `yd_getstatehash [height]` | SHA-256 over the canonical serialisation of every table (tests assert equality across nodes and across rebuilds) |
| `yd_getstats` | supply, collateral, active/void vaults, price, health, dcaBps, errBps, mintFrozen |
| `yd_getprice [height]` | `price(H)`, source height, age |
| `yd_getroster` | current roster pubkeys, k, n, script hex, P2SH address, previous roster |
| `yd_getvault <txid>` | vault record, including `requiredBurnAtClose` and `unbacked = burnedCents < requiredBurnAtClose` for CLOSED vaults (F1) |
| `yd_listvaults [status] [rosterIndex]` | paged list |
| `yd_gettxinfo <txid>` | the `TxLog` entry for a confirmed transaction (E1), or a dry-run for a mempool transaction, or `expired` for a wallet transaction past its `nExpiryHeight` that is in neither (F6); no `-txindex` needed |
| `yd_decodepayload <hex>` | payload decoder |
| `yd_validaterawtransaction <hex>` | dry-run §3.7 + §3.8 against the index tip, with the input view built from `pcoinsTip` + `CCoinsViewMemPool` under `cs_main` (C1); returns verdict, type, ydIn/ydOut/burn, fee, requiredBurn, reasons — used by co-signers and the coordinator |
| `yd_estimatecollateral <cents> <tier> [priceMicroUsd]` | `requiredZat` at current or given price and current DCA |
| `yd_gethistory <fromHeight> <toHeight>` | snapshots |
| `yd_createpricetx <priceMicroUsd\|"rotate"> [refill_txid:n] [newRosterScriptHex]` | unsigned PRICE transaction (or, with `"rotate"`, a ROTATION with no `OP_RETURN`, C9) spending the current anchor: `CreateNewContextualCMutableTransaction`, `YD_FEE`, anchor value from the index's `Anchor.nValue` cross-checked against the UTXO view (D4), anchor output to the current (or new) roster script, the optional refill absorbed whole into the anchor (must be confirmed, C6); returns hex plus the `prevtxs` array `signrawtransaction` needs when the previous anchor is in neither the chain nor the signer's mempool (C11). Ycash's `createrawtransaction` cannot emit an `OP_RETURN` (B1) |

Wallet context (`src/rpc/ydollarwallet.cpp`, `ENABLE_WALLET`):

| Command | Purpose |
|---|---|
| `yd_getnewaddress` | fresh keypool key, added to the address book as `getnewaddress` does (E9), rendered as a YDollar address |
| `yd_validateaddress <addr>` | decode; `ismine` |
| `yd_getbalance [minconf]` | confirmed / unconfirmed cents |
| `yd_listunspent [minconf]` | YDollar outputs that are mine |
| `yd_mint <cents> <tier>` | builds, signs, commits a MINT; returns txid, vault outpoint, lockHeight, collateral |
| `yd_send <ydaddr> <cents>` / `yd_sendmany {addr:cents}` | TRANSFER |
| `yd_redeem <vaultTxid>` | builds the REDEEM, signs the owner input and the YDollar inputs, records a `PendingRedemption` for the vault (reserving those inputs, D3), returns `{hex, vault, roster, requiredBurn, expiry}` — no network I/O; refuses if a pending record for that vault exists |
| `yd_submitredeem <hex>` | SUB-1 check against the `PendingRedemption` record, `VerifyScript` on every input, lock-height and expiry margin (C22), then `CommitTransaction` (wallet tracking + relay) and clears the record |
| `yd_abortredeem <vaultTxid>` | clears the `PendingRedemption` record of a redemption that was never broadcast (B19, D3); YDollar coin locks are untouched |
| `yd_cosignredeem <hex>` | federation member: RED-0..8, add own signature in roster order, return hex; never signs twice for the same vault outpoint within one height |
| `yd_listpositions [status]` | my vaults with `canRedeem`, `requiredBurn`, `unlockHeight` |
| `yd_listtransactions [count] [skip]` | mint/send/receive/redeem history from `TxLog` (E1), filtered by `IsMine` over the assigned outputs' scripts and `HaveKey` over vault owner keys |
| `yd_lockcoins` | re-run coin locking (maintenance) |

Configuration: `-ydollar`; `-ydollarstartheight`, `-ydollargenesisanchor` and
`-ydollargenesisroster` (regtest only, all three together, C2); `-reindex-ydollar`;
`-ydollarfee=<zat>` (default and minimum `DEFAULT_FEE`, C16); `-ydollarmintlag=<blocks>` (default
2, C4); `-ydollarsupplycap=<cents>` (regtest only, default 0 = none, G5); `-debug=ydollar`. Co-signer URLs are configuration of the Python client, not of the node.

### 4.5 Wallet behaviour

- **Coin locking (three stages, B4).** (i) `yd_mint`/`yd_send`/`yd_redeem` call `LockCoin` on
  every YDollar output of the transaction they are about to commit **before** `CommitTransaction`,
  because a wallet's own 0-conf outputs are trusted and spendable at once (`CWalletTx::IsTrusted`,
  `ref/ycash/src/wallet/wallet.cpp:4842-4867`). (ii) The index's `SyncTransaction` override
  pre-locks every output a well-formed payload assigns to a script that `IsMine`, for mempool and
  block transactions alike; it runs before `ChainTip` for the same block
  (`validationinterface.cpp:213-217`). (iii) After every applied block and at startup, `ChainTip`
  reconciles: every `Tokens` outpoint that is mine is locked; a pre-lock is released **only** when
  the outpoint's transaction is now confirmed and the applied verdict assigned it no cents (a VOID
  mint's token output, an output of a transaction that turned out non-YDollar); outpoints that are
  spent are pruned from the set. **Nothing is unlocked on disconnect** (C3): the disconnected
  transaction returns to the mempool, where its outputs are trusted 0-conf again, so the lock must
  stay until the outpoint is either confirmed-and-worthless or spent. Vault outputs need no lock: a P2SH whose redeem script the wallet does not hold is
  never `IsMine` (`ref/ycash/src/script/ismine.cpp:76-86`) and never enters `AvailableCoins`.
  `yd_send`/`yd_redeem` select YDollar and vault inputs directly from the index — skipping
  outpoints reserved by a `PendingRedemption` and outpoints the wallet reports spent by one of its
  own unconfirmed transactions (`CWallet::IsSpent`, `wallet.cpp:1087-1099`; D3) — and YEC fee
  inputs from `AvailableCoins`, which skips locked coins (`wallet.cpp:5074`). Locks are in-memory in
  Ycash (`setLockedCoins`), hence re-applied at startup.
- **Ownership and keys.** `yd_mint` draws **one** fresh keypool key and uses it both as the vault
  `ownerPubKey` and for the token output, so a position depends on exactly one key. A vault is mine
  iff `pwalletMain->HaveKey(ownerPubKey.GetID())`; a token output is mine iff `IsMine(scriptPubKey)`.
  Nothing YDollar-specific is written to `wallet.dat`; wallet restore = restore keys + the index.
  Ycash 4.5 transparent keys are a random keypool, not HD (the HD seed serves Sapling only), so the
  user documentation states the same rule as for any t-address: **back up `wallet.dat` after minting**
  — a backup taken before the keypool was consumed does not contain the vault key. Keys are drawn
  with `GetKeyFromPool`, which generates a new one when the pool is empty and the wallet is
  unlocked (`wallet.cpp:6005-6022`), so `-keypool=1` needs no special case (C8); `yd_listpositions`
  shows the owner key id so a user can verify a backup with `dumpprivkey`. Builds compiled with `-DYCASH_WR` offer `-deletetx`, which prunes old wallet
  transactions but keeps any with an unspent transparent output that is mine
  (`wallet.cpp:4336-4348`); YDollar coins survive it and `yd_listtransactions` reads the index, not
  the wallet (B22). Ycash's wallet encryption is experimental and gated behind
  `-developerencryptwallet` (`ref/ycash/src/wallet/rpcwallet.cpp:2127,2160`), so user documentation
  must not present it as protection for vault keys; the stated custody rule is full-disk
  encryption, RPC on localhost only, and an offline copy of `wallet.dat` (E5).
- **Confirmed-only chaining.** The wallet never spends unconfirmed YDollar (DigiByte commit
  `0b4959f563`). The state machine allows in-block chaining (an earlier tx in the same block) so
  block-internal ordering is never ambiguous.
- **Expiry.** A YDollar transaction that expires unmined is dropped by the mempool at the next
  block (`main.cpp:3636`) but stays in the wallet at depth 0 and is rebroadcast like any other
  (`wallet.cpp:4653-4668`); the wallet does not mark it. For YDollar: an expired MINT or TRANSFER
  leaves no index trace (its stage-(i) locks name outputs that never exist and are harmless); an
  expired REDEEM leaves the vault ACTIVE and its `PendingRedemption` is dropped when the index
  passes `nExpiryHeight`; the user re-runs the command (F6).
- **Change floor.** `yd_send`/`yd_sendmany`/`yd_redeem` refuse to build a transaction whose YDollar
  change would lie in `(0, MIN_OUTPUT)`: XFER-1 could not assign it and it would burn (C20). The
  error names the smallest amount that works.
- **Wallet views.** `listunspent` and every coin-selecting RPC go through `AvailableCoins`, which
  skips locked coins (`wallet.cpp:5074`), so YDollar outputs never appear as spendable YEC;
  `getbalance` still counts their `TOKEN_VALUE` (0.0001 YEC each). Documented, not changed.
- **Transaction building** (`txbuilder.cpp`, B14): start from
  `CreateNewContextualCMutableTransaction(consensus, chainActive.Height() + 1)`
  (`ref/ycash/src/main.cpp:7364`) and set `nExpiryHeight` explicitly (`-txexpirydelta` must not
  leak in: MINT uses `evalHeight + MINT_WINDOW`, TRANSFER and REDEEM `indexTip + 40`); for MINT and
  TRANSFER choose YEC inputs via `AvailableCoins(vCoins, true, nullptr, false, false, nMinDepth = 1)`
  — confirmed only, locked coins excluded (F3; the wallet's own 0-conf and *expired* outputs are
  otherwise selectable, `wallet.cpp:5038-5052`) — smallest first, until inputs cover outputs plus
  the flat `YD_FEE` (a REDEEM has no YEC inputs, C10); change via
  `CReserveKey`; sign each P2PKH input with `SignSignature(keystore,
  scriptPubKey, mtx, i, amount, SIGHASH_ALL, branchId)` (`ref/ycash/src/script/sign.h:73-80`) and
  the vault input manually; `EnsureWalletIsUnlocked` first; commit with `CommitTransaction`
  (`wallet.cpp:5707`) so the wallet tracks and relays it like any transaction.

### 4.6 Federation member node

An operator runs a normal `ycashd` with `-experimentalfeatures -ydollar` on a **dedicated host**
with full-disk encryption and RPC bound to localhost — Ycash's wallet encryption is experimental
and cannot be relied on (E5) — whose wallet is **dedicated**: it holds the roster key and nothing
else, so `signrawtransaction` can solve no input but the anchor and the operator's own refill
coins (C5). The roster key is generated inside
that node — `getnewaddress`, then `validateaddress <addr>` for the `pubkey` (33 bytes; the
ceremony rejects anything else, D7) to hand to the key ceremony — and never exported (C7); `importprivkey <key> "" false` (no rescan, B23) is only the
restore-from-backup path. The operator **must run `addmultisigaddress k [sorted pubkeys]` once**
so the roster redeem script is stored in `wallet.dat`
(`AddCScript`, `ref/ycash/src/wallet/rpcwallet.cpp:1175`): `signrawtransaction` solves a P2SH
input from the wallet keystore only if the wallet holds the redeem script, and it takes a
`redeemScript` from `prevtxs` only when private keys are passed explicitly (`fGivenKeys`,
`rawtransaction.cpp:966-974`, B2). The resulting address must equal `yd_getroster`. The operator
exposes `yd_cosignredeem` and `signrawtransaction` to the coordinator over local RPC only. A
confirmed anchor's `scriptPubKey` and `amount` come from `pcoinsTip`, and an unconfirmed one from
the node's mempool, inside `signrawtransaction` (`CCoinsViewMemPool`, `rawtransaction.cpp:906-921`);
`prevtxs` with `amount` is required only when the previous PRICE transaction is in neither (C11;
ZIP-243 commits to the input value). The anchor is never "mine" to the wallet (multisig needs all
keys, `ismine.cpp:88-102`), so it never appears in balances or coin selection. The coordinator (§5)
is the only component that talks to the internet. Relaying nodes must keep `-datacarrier` at its
default (`policy.cpp:52`), or `OP_RETURN` transactions are not relayed (C23).

### 4.7 User interface and user experience

**What exists on the Ycash side.** Nothing in the node tree: `ycash-dd` builds `ycashd` and
`ycash-cli` only. The GUI is **YecWallet** (`ref/yecwallet`, pinned `v4.5.0`): a Qt 6 / CMake
C++ application of the zec-qt-wallet lineage, ≈ 8,300 lines, with four tabs — Balance, Send,
Receive, Transactions — and a hidden `ycashd` console tab (`src/mainwindow.ui:29,289,663,894,911`).
It looks for `ycashd` beside its own executable and starts it with no arguments
(`src/connection.cpp:323-380`); on first run it writes `~/.ycash/ycash.conf` with `server=1`,
`addnode`, `rpcuser` and a random `rpcpassword` (`connection.cpp:130-215`); and it reads
everything over JSON-RPC (`Connection::doRPCWithDefaultErrorHandling`, `src/connection.h:100-104`)
from a `Controller` that polls `getinfo` every 20 seconds (`Settings::updateSpeed`,
`src/settings.h:124`; a 1-second mode while an operation is pending, `controller.cpp:45-50`) and
refreshes balances, addresses and transactions whenever the block height changes
(`src/controller.cpp:28-52,247-280`). It decides testnet versus mainnet from `getinfo.testnet`
(`controller.cpp:255-257`), which regtest reports as `false`; the YDollar tab therefore takes its
network from `yd_getinfo.network` (H3). Sends go
through validation, a confirm dialog and `executeTransaction` (`src/sendtab.cpp:661-701`,
`controller.cpp:587-607`). The YDollar work is a fork of this application, `yecwallet-dd`, on
`feature/digidollar` off `yecwallet-legacy` (= `v4.5.0`), held to the same rules as the node fork
(AGENTS.md rule 2). The light application (YecWallet Lite over `lightwalletd`) is out of scope
for v1 (below).

**What DigiByte's UI does, and what carries over.** DigiByte's DigiDollar tab has seven panes —
Overview, Send, Receive, Mint, Redeem, Vault (positions), Transactions — plus a coin-control
dialog (`ref/digibyte/src/qt/digidollartab.cpp:100-106`). Every one of those panes maps onto
YDollar RPCs that already exist in §4.4; the table below is the functional specification for the
wallet application. Coin control is dropped for v1 (the node's builder selects YDollar inputs
smallest-first and confirmed-only, §4.5; a user has no reason to pick outpoints).

| Screen | What the user sees and does | RPCs behind it | Ycash-specific UX rules |
|---|---|---|---|
| **Status banner** (every screen) | index syncing / synced / unhealthy; "YDollar unavailable" with the reason and the fix (`-reindex-ydollar`) | `yd_getinfo` | shown whenever `synced` is false or `healthy` is false; every action button is disabled while it shows |
| **Overview** | YD balance (confirmed, unconfirmed), YEC balance, YEC price, system health %, DCA multiplier, ERR status, "minting paused" (volatility freeze / ERR / no fresh price / cap reached), price age, recent YDollar transactions | `yd_getbalance`, `getbalance`, `yd_getstats`, `yd_getprice`, `yd_listtransactions` | health and freeze are the reasons a mint may be refused; show them *before* the user opens Mint |
| **Receive** | a fresh YDollar address with QR; label; copy | `yd_getnewaddress`, `yd_validateaddress` | the address is visibly a YDollar address (`yd…`), never a `s1…` address; text: "send only YDollar here" |
| **Send** | recipient (validated, `yd` prefix), amount in dollars and cents, YEC fee shown, confirm | `yd_validateaddress`, `yd_send`, `yd_sendmany` | refuse `s1…` recipients with a clear message; surface the change-floor error (C20: "amount leaves less than $1.00 of change") with the nearest workable amount; unconfirmed YD is shown but not spendable (§4.5) |
| **Mint** | amount ($100–$10,000), tier picker showing lock period, ratio and the **exact** YEC collateral required now, unlock height and estimated date (75 s/block), YEC available; confirm | `yd_estimatecollateral`, `yd_getstats`, `yd_mint` | gates (with the reason) when health < 100 %, mint frozen, no fresh price, cap headroom < amount, index not synced or `indexTip < startHeight + MINT_EVAL_LAG` (D5); confirmation text states that the requirement is fixed at signing (B3/C4) and that collateral is locked until the unlock height and needs the federation's co-signature to release (§8.1); **after a successful mint the app insists on a `wallet.dat` backup** (keypool keys are not derived from a seed, A10) |
| **Vaults** (positions) | one row per vault: status (ACTIVE / VOID / CLOSED), minted, collateral, unlock height + date, required burn *now*, redeemable yes/no; VOID rows explain why (verdict from `yd_gettxinfo`) and that collateral returns at unlock with no burn | `yd_listpositions`, `yd_getvault`, `yd_gettxinfo` | "required burn" can exceed "minted" during ERR (§3.6); say so and link to the health figure |
| **Redeem** (wizard) | 1 pick a redeemable vault; 2 review burn (YD to be destroyed) and collateral to be returned; 3 **collect co-signatures**: progress "k of 5", operator names from the roster, transient failures retried, deadline countdown (36 blocks ≈ 45 min, B24); 4 submit; or abort at any step | `yd_listpositions`, `yd_redeem`, operators' `/cosign` (HTTPS), `yd_submitredeem`, `yd_abortredeem` | this is the **only** screen that talks to anything but the local node; the app embeds the `ydollar-redeem` logic (§5) and the published operator endpoint list, verifiable against `yd_getroster`; on deadline expiry it calls `yd_abortredeem` and offers to restart; a refusal reason from a co-signer (RED-3 short burn, RED-6 oracle outage, RED-8 expiry) is shown verbatim |
| **Transactions** | mint / send / receive / burn / redeem history with amounts in dollars, confirmations, and `expired` for wallet transactions that died unmined (F6) | `yd_listtransactions`, `yd_gettxinfo` | a plain-YEC spend of a YDollar output shows as **burn** with an explanation (D18) |
| **Settings** | operator endpoint list (defaults shipped, editable), display unit, show/hide advanced (raw hex) | — | `-ydollar` and `-experimentalfeatures` must be set in the node's `ycash.conf`; the app detects their absence (`yd_getinfo` → "Method not found") and shows the two lines to add |

**Where the code goes in `yecwallet-dd`** (mirrors §4.1–§4.2 for the node; the crosswalk is
`mapping.md` §12):

| File | Lines (est.) | What |
|---|---|---|
| `src/ydollartab.{cpp,h,ui}` | ≈ 600 | the YDollar tab: a `QTabWidget` of the sub-pages below, added to `MainWindow`'s tab bar after Transactions |
| `src/ydollarcontroller.{cpp,h}` | ≈ 500 | issues every `yd_*` call through the existing `Connection`; refresh hooked into `Controller::getInfoThenRefresh`'s "block changed" branch; pending redemptions watched on `txTimer` like `watchTxStatus` |
| `src/ydollarmodels.{cpp,h}` | ≈ 400 | `QAbstractTableModel`s for positions and YDollar transactions (pattern: `txtablemodel.h`, `balancestablemodel.h`) |
| `src/ydollarmint.ui`, `ydollarsend.ui`, `ydollarreceive.ui`, `ydollarredeem.ui`, `ydollarpositions.ui`, `ydollartransactions.ui`, `ydollaroverview.ui` | ≈ 1,200 (XML) | the sub-pages, laid out after DigiByte's `src/qt/digidollar*widget.cpp` behaviourally |
| `src/ydollarredeemwizard.{cpp,h}` | ≈ 400 | the co-signature collector: HTTPS POSTs to operator `/cosign` endpoints via the app's existing `QNetworkAccessManager`, progress, retry of transient refusals, deadline countdown, abort |
| `src/connection.cpp` | ≈ 10 | `createZcashConf` also writes `experimentalfeatures=1` and `ydollar=1`; detection of an existing conf without them (`yd_getinfo` → "Method not found") and an offer to append |
| `src/mainwindow.{cpp,h}`, `src/controller.{cpp,h}`, `src/settings.{cpp,h}` | ≈ 60 | tab registration, refresh hook, operator endpoint list and RPC-version check in `Settings` |
| `CMakeLists.txt`, `application.qrc` | ≈ 25 | new sources and icons |
| everything else | **0** | `Connection`, `Controller`'s existing flows, Send/Receive/Balance tabs untouched |

The wallet's release bundles the `ycash-dd` build of `ycashd` exactly where the unmodified wallet
expects it (`connection.cpp:348-364`), so a user who installs YecWallet-YD gets a YDollar-capable
node without knowing it; the wallet checks `yd_getinfo.rpcversion` at connect and refuses a node
it does not know.

**Cross-cutting rules.**

1. **The RPC surface is the contract.** `doc/ydollar-rpc.md` in `ycash-dd` documents every `yd_*`
   call, argument, result field and error code; `yd_getinfo.rpcversion` is bumped on any
   incompatible change and the application refuses to run against a version it does not know.
   Nothing else — no shared library, no file format, no database — crosses the boundary.
2. **No key material outside the node.** The application never holds a private key; every
   signature is made by `ycashd` through its wallet RPCs. Coin locking (§4.5) is the node's job;
   the application only displays it.
3. **Heights, not clocks, with a translation.** The protocol speaks block heights; the application
   shows both the height and an estimated date/time at 75 s per block, labelled as an estimate.
4. **Transparent by design.** YDollar is transparent-only (D13); the application says so where a
   user might expect shielded behaviour (Receive, Send).
5. **Backups.** Ycash wallet encryption is experimental (E5); the application's guidance is a
   `wallet.dat` backup after every mint, and it nags until one is confirmed.
6. **Errors are the node's words.** RPC error strings from `yd_*` are stable identifiers (§4.4,
   Verdict reason strings); the application maps them to friendly text but always shows the
   identifier.

**Operators.** No graphical interface. `ycash-cli`, the coordinator's own status output
(`ydollar-fed status`: price age, last round, peers, anchor value) and `yd_getinfo` are the
operator interface; the runbook (§5) is written for them.

**Light wallets.** A light client cannot compute the YDollar index (it has no blocks), so the
light application is out of scope for v1. The path, if wanted later: a small indexer service that
runs `ycashd -ydollar` and exposes the read-only `yd_*` calls to light clients, alongside
`lightwalletd`; the redemption wizard would still need the user's node for signing. Recorded
here so the light-wallet decision is not mistaken for an oversight.

**Testing the wallet.** YecWallet has no automated test suite at the pin (`ref/yecwallet` has no
test target in `CMakeLists.txt`), so the fork adds the smallest thing that works, in the tooling
the wallet already has. Attaching the GUI to the §6.0 playground needs **no new code**: the stock
options `--conf <tmpdir>/node0/ycash.conf --no-embedded` (`src/main.cpp:168-172`) point it at
node 0 — the conf parser reads `rpcuser`, `rpcpassword` and `rpcport` (`src/connection.cpp:647-673`),
which is exactly what the framework writes — instead of starting an embedded mainnet node (H2).
The test is a Qt Test target that drives the YDollar tab against that node: mint, send, `generate`
through a tier-0 lock via RPC, redeem through the wizard against the five local operators, abort
path, expired-transaction display. It is declared with `find_package(Qt6 OPTIONAL_COMPONENTS Test)`
and built only when the module is present (H1): the wallet's static release Qt is configured with
`-no-feature-testlib` (`scripts/build-qt.sh:129`) and stays that way; development and CI test
builds use a system Qt 6, which ships `Qt6::Test`. The target runs with
`QT_QPA_PLATFORM=offscreen` and headless mode on (`--headless` hides the window and skips the
modal dialogs, `src/main.cpp:251-257`, `connection.cpp:31-32`, `controller.cpp:849`; H5). The RPC
contract itself is covered by `ydollar_*.py` (§7), so a green node suite plus a green wallet test
is the definition of done. CI for `yecwallet-dd` reuses the node CI's cached `ycashd` build
(§6.0 item 6), builds the app and the test against the runner's system Qt 6, and — on tags only —
runs the wallet's own `build.sh --package` (static Qt 6.5.8, `build.sh:57`, cached the same way
as `depends/`).

---

## 5. Federation coordinator (`contrib/ydollar/`)

Python 3, single file per role, no daemons beyond `ycashd`. Configuration in `ydollar-fed.toml`
(node RPC URL, operator id, peer coordinator URLs, exchange list, thresholds).

**Price round (every 8 blocks or on a ≥ 1 % move, whichever first):**

1. Each member fetches YEC/USD from every configured source (minimum three independent sources;
   sources that quote YEC/BTC are converted with a BTC/USD median), keeps a 5-minute time-weighted
   average per source, drops sources silent for > 120 s, removes outliers more than 10 % from the
   median (DigiByte's `FilterOutliers`), takes the median in micro-USD. **Move clamp:** the round's
   price is clamped to ± 10 % of the last on-chain price; a larger real move is followed over
   several rounds, which is what makes a thin-market wick or a single compromised source unable to
   move the collateral requirement in one step (the protocol's volatility freeze covers the rest).
2. The proposer for the round is the member whose id equals `(anchorHeight // 8) mod n`, falling
   back to the next id after 2 blocks without a proposal.
3. Proposer calls `yd_createpricetx <price> [refill]` on its node (Ycash's `createrawtransaction`
   has no `OP_RETURN` output, B1). When the anchor value is < 0.01 YEC it first creates a refill
   UTXO of the exact top-up amount with `sendtoaddress` to its own address and waits one
   confirmation; that UTXO is absorbed whole into the new anchor, no change output (C6). It signs
   with `signrawtransaction hex [prevtxs]` (the wallet holds the roster script, B2; `prevtxs` only
   when the previous anchor is in neither chain nor mempool, C11), then POSTs `{hex, price}` to
   peers over HTTPS with mutual authentication (operator client certificates).
4. Each peer runs `yd_validaterawtransaction` and `decoderawtransaction` on its own node and
   accepts iff `|price − ownMedian| ≤ 2 %` and the structure matches: inputs = the current anchor
   plus at most one refill; outputs = exactly the anchor P2SH with the **same** roster script and
   one `OP_RETURN` with the stated price; fee = `YD_FEE`; and **no input other than the anchor is
   solvable by the peer's own wallet** (C5 — `signrawtransaction` would otherwise sign it away).
   Then `signrawtransaction` on the **unsigned** hex and return the partial. Peers are asked in
   parallel; the proposer concatenates the returned hexes and calls `signrawtransaction` once —
   it merges any number of partially signed copies (`ref/ycash/src/rpc/rawtransaction.cpp:886-893,
   1058-1062`, F2) — and broadcasts with `sendrawtransaction` when it reports `complete: true`.
5. Failure to reach k signatures within 4 blocks ⇒ round abandoned; the overlay simply has no fresh
   price and mints pause (fail closed). Nothing else changes.

Roster keys are passed to `createmultisig`/`addmultisigaddress` in the sorted order of §3.3; the
coordinator asserts that the resulting P2SH address equals the one derived by `yd_getroster`.

**Redemption co-signing endpoint (`POST /cosign`, HTTPS, public):** body = owner-signed hex. The
coordinator calls `yd_cosignredeem` on its node, which applies §3.8 and signs only if every policy
check holds. Rate-limited per source IP and per vault outpoint; rejects transactions whose vault is
not ACTIVE/VOID; logs every decision. Returns the hex with one more signature.

**Redemption client (`contrib/ydollar/ydollar-redeem`):** `yd_redeem` on the user's node →
POST the hex to operators, one after another, from a published endpoint list (shipped with the
coordinator release and verifiable against `yd_getroster` key ids), each operator adding one
signature to the transaction it received, until `k` signatures are present → `yd_submitredeem` on
the user's node. Every co-signature is verified locally by the node before broadcast (SUB-1), so
the client and the endpoints are untrusted plumbing. A *transient* refusal (RED-0 unsynced, RED-2
not yet at `lockHeight` on that node) is retried after the next block (E2). The client shows the
deadline: with
`nExpiryHeight = indexTip + 40` and the mempool's expiring-soon threshold of 3 blocks
(`ref/ycash/src/main.h:81`, `main.cpp:1547`) the transaction must be submitted within 36 blocks
(≈ 45 minutes) of `yd_redeem`; past it, `yd_abortredeem` releases the locked inputs and the user
starts over (B24).

**Rotation (`ydollar-fed rotate`):** builds the ROTATION transaction (`yd_createpricetx rotate
<newRosterScriptHex>`, no `OP_RETURN`, C9), collects k signatures with the same structural checks
as step 4 (output = the agreed new roster script, nothing else), then a PRICE transaction from the
new anchor. Operators leaving the roster keep keys until
`yd_listvaults rosterIndex=<old>` reports zero ACTIVE/VOID vaults.

**Operator runbook (in `doc/ydollar-federation.md`):** key generation inside the node and pubkey
exchange (C7), dedicated wallet (C5), `addmultisigaddress` (B2), genesis anchor creation (fund a
k-of-n P2SH with 1 YEC, record `txid:0`, the block height and the script in `params.cpp`),
`-datacarrier` left at default (C23), monitoring (`yd_getinfo`, `yd_getprice` age, coordinator
heartbeat), incident procedures (member outage, key compromise → rotate, exchange outage → pause).

---

## 6. Work plan

Eight phases, each a reviewable PR series against `feature/digidollar`. Sizes are source lines
excluding tests. Each phase ends only when its exit criteria pass in CI (`make check` +
`qa/pull-tester/rpc-tests.py`).

### 6.0 Developing and testing on one machine

The system needs nine operators and a 5-of-9 quorum in production, but nothing about developing
or testing it needs more than one laptop, and nothing needs a synced chain. The rule for this
section: **use only what the repository already ships.** No new infrastructure, no container
orchestration, no external services. Every tool named below exists at the pin.

**1. Regtest is the whole development chain.** A regtest node starts at genesis, and
`generate(101)` produces a mature coinbase in seconds (Equihash 48/5, `chainparams.cpp:860-863`).
YDollar reads only block heights — never wall-clock time (§3.10) — so time is compressed by
mining blocks, and the regtest overrides in §3.1 shrink the lock tiers to at most 240 blocks. A
complete lifecycle (fund, publish price, mint tier 4, transfer, wait out the lock, redeem with
co-signatures, rotate the roster) is a few hundred `generate` calls. Testnet and mainnet sync
happen once, in Phase 7 and 8, on operator machines — never in the development loop.

**2. Many operators on one machine = many regtest nodes.** Ycash's functional-test framework
(`qa/rpc-tests/test_framework/`) already launches up to `MAX_NODES = 8` independent `ycashd`
processes per test (`util.py:46`), each with its own data directory, wallet, P2P port and RPC port
(`p2p_port`/`rpc_port`, `util.py:89-94`; distinct `--portseed` values let several tests run at
once), connects them (`connect_nodes_bi`), synchronises them (`sync_all`, which also waits for the
notifier cycle, C13), partitions and rejoins the network for reorg tests (`split_network` /
`join_network`, `test_framework.py:74,93`), and stops and restarts individual nodes (`stop_node` /
`start_node`, `util.py:350,418`). Each node's wallet holds only its own operator key, so "k of n
signatures" means "k separate processes each signed", exactly as in production.

Standard topology for YDollar functional tests (7 of the 8 available nodes):

| Node | Role | Flags |
|---|---|---|
| 0 | user wallet (minter, redeemer) | `-ydollar` |
| 1 | second user / plain relay node; source of roster keys 6–9 | **without** `-ydollar` but with the same six `-nuparams` — proves ordinary nodes relay and mine YDollar transactions unchanged (§8.3); excluded from state-hash assertions (G6) |
| 2–6 | five federation operators, one roster key each, `addmultisigaddress` run on each (B2) | `-ydollar` |

**5-of-9 on five nodes.** Production shape needs nine roster keys but only five signers. The test
takes keys 6–9 from node 1's wallet (`getnewaddress`, then `validateaddress` for the `pubkey`;
node 1 never runs `-ydollar` and is never asked to co-sign — no Python cryptography, G2), puts
those *public* keys into the roster script alongside the five operator nodes' keys
(`createmultisig`/`addmultisigaddress` accept hex pubkeys, `rpc/misc.cpp:343-347`), and never
signs with them. This exercises the real
350-byte script, the real scriptSig size, the real `AreInputsStandard` path, and the "four members
offline" case, on five processes. Quorum behaviour is tested by stopping operator nodes:
with four of five up, co-signing fails (4 < 5); restart one, it succeeds. Fast lifecycle tests use
a 2-of-3 roster on nodes 2–4 (the plan's regtest default) to keep runtime down.

**3. The coordinator runs in the same tests.** `ydollar_federation.py` launches
`contrib/ydollar/ydollar_fed.py` as one subprocess per operator node, pointed at that node's RPC
port, with `--mock-price <path>` (a file the test rewrites to move the price) and
`--insecure-localhost` (plain HTTP on 127.0.0.1; mutual TLS is configuration, exercised on
testnet in Phase 7, not in CI). The `ydollar-redeem` client is driven the same way. Nothing in the
test path opens a connection off the loopback interface.

**4. The developer's inner loop**, fastest first:

| Loop | Command | Time |
|---|---|---|
| Pure logic (payload, scripts, math, state machine) | `src/test/test_bitcoin --run_test=ydollar_*` | seconds |
| One flow end to end | `qa/rpc-tests/ydollar_lifecycle.py` | ≈ 1–2 min |
| Whole YDollar suite | `qa/pull-tester/rpc-tests.py -j4 ydollar_index ydollar_lifecycle …` — names must be listed in the runner's `BASE_SCRIPTS`, which Phase 2+ do; it does not glob (`rpc-tests.py:213-218`, G3); it already parallelises (`:174`) | ≈ 10 min |
| Interactive multi-node playground | any `ydollar_*.py --noshutdown --nocleanup` (`test_framework.py:105-107`), then `ycash-cli -regtest -datadir=<tmpdir>/nodeN …` and `generate` by hand | as long as wanted |
| The GUI against the playground | `yecwallet --conf <tmpdir>/node0/ycash.conf --no-embedded` — stock options, no new code (§4.7, H2): the wallet connects to the user node of a running playground instead of starting its embedded mainnet node; the wallet's QTest target does the same under `QT_QPA_PLATFORM=offscreen` | seconds to attach |

The playground is the "local devnet": the test sets up the anchor, roster, operators and
coordinators, then leaves everything running. A Docker Compose file would be a second way to
launch the same binaries with the same flags; it is deliberately **not** part of v1 (one more
artifact to keep in step with the test framework, and nothing it enables is unavailable above).
It can be added later under `contrib/ydollar/devnet/` without touching the plan.

**5. What one build needs.** `zcutil/build.sh` builds `depends/` and the node; `BUILD_STAGE=depends`
builds only the dependencies (`build.sh:90-93`), which is what makes them cacheable. Nodes refuse
to start without the three zk parameter files (`init.cpp:746-759`), fetched once with
`zcutil/fetch-params.sh` into `~/.zcash-params` — also the node's default (`util.cpp:266`,
overridable with `-paramsdir`) — ≈ 800 MB, mostly `sprout-groth16.params`; regtest needs them as
much as mainnet does. **And one two-line fix (G1):** the inherited framework writes each node's
`regtest=1` and RPC credentials to `zcash.conf` while Ycash reads only `ycash.conf` and exits
without it, so no functional test can start a node at the pin until `util.py:175` and
`multi_rpc.py:29` are corrected. Phase 0 does this first.

**6. CI.** Ycash's own CI runs no tests (`.github/workflows/book.yml` only, B6), so the fork adds
`.github/workflows/ydollar-tests.yml`, plain GitHub Actions on `ubuntu-22.04`:

1. Restore `depends/` from `actions/cache`, keyed on the hash of `depends/packages/**` and
   `depends/Makefile`; on a miss run `BUILD_STAGE=depends ./zcutil/build.sh -j$(nproc)` and save.
   (First build ≈ 1 h; cached builds skip it entirely.)
2. Restore `~/.zcash-params` from cache keyed on `zcutil/fetch-params.sh`'s hash; on a miss run
   the script.
3. `./zcutil/build.sh -j$(nproc)`.
4. `src/test/test_bitcoin --run_test=ydollar_*` (the plan's unit tests are Boost; the whole
   `make check`, including `ycash-gtest`, runs in the nightly job, not on every push — G4).
5. `qa/pull-tester/rpc-tests.py -j4 <every ydollar_* script by name>` — the multi-node functional
   suite, including the 5-of-9 federation test and the coordinator subprocesses (G3).
6. On failure, upload every node's `debug.log` and the coordinators' logs as an artifact.

A second, nightly workflow runs `make check` in full, the inherited functional tests recorded as
passing in Phase 0, and `ydollar_reorg_stress.py`. Pull requests to `feature/digidollar` are
gated on the first workflow. Both use the same `zcutil/build.sh` a developer runs locally, so a
green CI and a green laptop mean the same thing.

**7. What this does not cover, and where it is covered.** Real network latency, real exchange
feeds, TLS between operators, nine physically separate machines, and a chain with history: all of
these are Phase 7 (testnet soak, two weeks, operator machines). Nothing in the protocol or the
code differs between the regtest run and the testnet run except `params.cpp` values and the
coordinator's configuration file.

### Phase 0 — Groundwork (≈ 1 day)

- [x] Replace `docs/spec/ydollar-adaptation-spec.md` with §3 of this plan (normative spec) and a
      pointer here for rationale.
- [x] Add the mapping rows listed in Appendix A to `docs/mapping.md`. *(Done: all 23 rows were already present in §11 by the revision-7 audit; verified row by row.)*
- [x] Create `ycash-dd/doc/ydollar.md` skeleton and `contrib/ydollar/README.md`.
- [x] Fix the inherited framework's config filename (`qa/rpc-tests/test_framework/util.py:175`
      and `qa/rpc-tests/multi_rpc.py:29`: `zcash.conf` → `ycash.conf`, G1). Without it no
      functional test can start a node.
- [ ] Build `ycash-dd` (`zcutil/build.sh`, both with and without `YCASH_WR=1`) and record the
      baseline: `make check`, then `qa/pull-tester/rpc-tests.py`. Expect the inherited post-Blossom
      tests (`coinbase_funding_streams.py`, `feature_zip221.py`, `upgrade_golden.py`,
      `shorter_block_times.py`, `post_heartwood_rollback.py`) to fail at node start because
      `test_framework/util.py:40-42` carries Zcash's branch IDs (B6); record which tests pass so
      later phases only have to keep those green. Note also that `atomicswap.py` is not listed in
      `rpc-tests.py` and starts its nodes with no network upgrade active and without
      `-experimentalfeatures` (`qa/rpc-tests/atomicswap.py:28-35`), so it is not a template (C12).
- [x] Add `.github/workflows/ydollar-tests.yml` to the fork as specified in §6.0 item 6 (Ycash's
      CI runs no functional tests); confirm the `depends/` and `~/.zcash-params` caches restore
      on a second run.

Exit: `make status` clean; baseline test run recorded in `doc/ydollar.md`.

### Phase 1 — Pure protocol library (≈ 900 lines)

Files: `params`, `amount.h`, `payload`, `script`, `address`. No chain, DB or wallet dependencies.

- [x] `Params` for main/test/regtest with the constants of §3.1 (genesis anchor placeholders on
      main/test; regtest from args).
- [x] `RequiredCollateral`, `Health`, `DcaBps`, `ErrBps`, `RequiredBurn` in `arith_uint256`, with
      the worked examples of §3.6 as unit tests, plus overflow tests at `MAX_MINT`/`PRICE_MIN`.
- [x] Payload codec with a table-driven round-trip test and a rejection test for every malformed
      case listed in §3.2.
- [x] `RosterScript`, `VaultScript`, parsers, `BuildVaultScriptSig`, `ExtractRedeemScript`; tests
      that (i) script sizes ≤ 520 for n = 13 with a 4-byte height push, (ii) sigops = n + 1 via
      `GetSigOpCount(true)`, (iii) a vault script executes under `VerifyScript` with
      `STANDARD_SCRIPT_VERIFY_FLAGS` (a superset of the consensus flags, `policy.h:32-40`) on a
      synthetic spending tx (both success and the four failure modes: early, missing owner sig,
      k−1 quorum sigs, wrong roster), and (iv) **standardness**: `IsStandardTx` and
      `AreInputsStandard` return true for synthetic MINT, TRANSFER, REDEEM (k = n = 13) and PRICE
      transactions — regtest never runs these checks (B5).
- [x] Address encode/decode tests, including cross-network rejection.
- [x] Register in `Makefile.am` / `Makefile.test.include`.

Exit: `src/test/test_bitcoin --run_test=ydollar_*` green; no file outside the new module touched
except the two Makefiles. **Done 2026-09-05** (`ycash-dd` commit "YDollar Phase 1"); the math
header is `src/ydollar/math.h`, not `amount.h`, because a quoted `#include "amount.h"` from inside
`src/ydollar/` resolves to itself.

### Phase 2 — State machine, database, index, node RPCs (≈ 1,600 lines)

- [ ] `view.h` with in-memory implementation; `state.cpp` implementing §3.7 and §3.8 over the
      view; `Verdict` type with stable reason strings (reuse DigiByte's token names where they
      exist: `bad-mint-lock-tier-duration`, `minting-blocked-during-err`, `bad-oracle-price`,
      `dd-input-amounts-unknown` → `yd-input-unknown`).
- [ ] Unit tests: synthetic block sequences for every rule; apply/undo byte-identity for every
      sequence; price age boundary (48 vs 49 blocks); in-block chaining; anchor custody break.
- [ ] `db.cpp` on `CDBWrapper` with per-block batch, `Undo`, undo pruning; `index.cpp` with
      `ChainTip` handling, idempotence rules, exception boundary, `SyncToChain`, unhealthy flag,
      `-reindex-ydollar`, `-reindex` (start-empty) behaviour, `-prune` refusal, genesis-anchor
      check, `synced` flag, state hash.
- [ ] `experimental_features` flag; `init.cpp` wiring; `rpc/register.h`; `src/rpc/ydollar.cpp`
      node RPCs including `yd_getstatehash`; `rpc/client.cpp` conversions.
- [ ] `qa/rpc-tests/test_framework/ydollar_util.py`: Ycash branch IDs (`YCASH 0x374d694f`,
      `BLOSSOM 0x8e471bd6`, `HEARTWOOD 0x66314da3`, `CANOPY 0x19bd2d2f`) and
      `ydollar_node_args(extra)` = six `-nuparams` at height 1 (Overwinter `5ba81b19`, Sapling
      `76b809bb`, Ycash, Blossom, Heartwood, Canopy — regtest activates none by default,
      `chainparams.cpp:576-604`, C12) plus `-experimentalfeatures -ydollar` and the regtest genesis
      arguments once known (regtest keeps Equihash 48/5 whatever is active, `chainparams.cpp:860-863`;
      with Ycash active from height 1 the miner pays the 5 % YDF output itself until height 5,
      `miner.cpp:201-203`; every YDollar test uses `setup_clean_chain = True`, B6);
      `assert_yd_synced(nodes)` = `sync_blocks(nodes)` then `yd_getinfo.synced` on each — the
      framework's sync already waits for the notifier cycle in which the index ran (C13);
      `make_regtest_roster` (`addmultisigaddress` on every node so `signrawtransaction` can solve
      the anchor, B2); `fund_genesis_anchor` (returns `txid:0`, script and block height for
      `-ydollarstartheight` / `-ydollargenesisanchor` / `-ydollargenesisroster`, C2);
      `restart_with_ydollar(nodes, ...)`; `publish_price` (via `yd_createpricetx`, B1).
- [ ] `qa/rpc-tests/ydollar_index.py`: three regtest nodes started **without** `-ydollar`; test
      creates a 2-of-3 anchor with `addmultisigaddress` + `signrawtransaction`, mines it, restarts
      the nodes with `-ydollar -ydollarstartheight -ydollargenesisanchor -ydollargenesisroster`
      (C2), publishes prices (one with a confirmed refill absorbed whole, C6; one spending an
      anchor still in the mempool without `prevtxs`, C11), checks `yd_getprice`, ages a price past
      48 blocks, performs a rotation (anchor spend to a new script, no `OP_RETURN`) and asserts
      the new roster is revealed by the next PRICE (C9),
      reorgs with `invalidateblock`/`reconsiderblock` across a price change and asserts identical
      `yd_getstatehash` on all nodes; restarts a node and asserts equality; restarts with
      `-reindex-ydollar` and asserts equality; restarts with `-reindex` and asserts equality;
      asserts that a node started with `-prune` and `-ydollar` fails to start.

Exit: all of the above green; `git diff --stat ycash-legacy...feature/digidollar` shows `main.cpp`
untouched.

### Phase 3 — Wallet: mint, send, redeem, co-sign (≈ 1,000 lines)

- [ ] `wallet.cpp`: ownership, coin locking, balances, positions.
- [ ] `txbuilder.cpp`: `BuildMint`, `BuildTransfer`, `BuildRedeem` (owner signature only),
      `AddCosignature`, `IsComplete` (uses `VerifyScript` with the vault script),
      `SameExceptSignatures` (SUB-1).
- [ ] `src/rpc/ydollarwallet.cpp`: all wallet RPCs; `yd_redeem` returns hex; `yd_submitredeem`;
      `yd_cosignredeem` with RED-0..8.
- [ ] `qa/rpc-tests/ydollar_lifecycle.py`: node 0 mints tier 0 at a mocked price, asserts vault
      + balance; immediately after `yd_mint` (0-conf) a `sendtoaddress` for the node's whole
      balance must not consume the token output (`listlockunspent` shows it, B4); a price
      attestation 20 % lower is published before the mint confirms and the mint still registers
      (evalHeight, B3); a 2-block reorg (`invalidateblock` on the last two blocks, then mining a
      different pair with a different price) after a mint built with the default lag still leaves
      the mint ACTIVE (C4); a block containing a YDollar output is disconnected with
      `invalidateblock` and `listlockunspent` still shows the output locked (C3); sends to node 1
      (`yd_send`), asserts conservation and `yd_getbalance` on both; a `yd_send` whose change
      would be under `MIN_OUTPUT` is refused (C20);
      node 1 spends a YDollar output with plain `sendtoaddress` after `lockunspent false` and the
      test asserts the burn is recorded; a TRANSFER assembled with
      `test_framework.mininode.CTransaction` (`createrawtransaction` cannot emit `OP_RETURN`, B1)
      that under-assigns is confirmed and the test asserts only the remainder burned; after 48 blocks
      node 0 runs `yd_redeem`, passes the hex through `yd_cosignredeem` on federation nodes 1 and 2,
      `yd_submitredeem`, asserts vault CLOSED, supply and collateral decremented; a co-signer
      presented with a transaction whose owner signature was stripped, whose expiry is too far,
      or whose burn is short refuses (RED-3/7/8); a co-signer presented with a transaction whose
      `vin[0].scriptSig` carries a *different* redeem script (same owner key, different roster)
      refuses because RED-7 is computed over the index's script (C5); `yd_submitredeem` refuses a
      returned transaction with a modified output (SUB-1) and refuses before `lockHeight` (C22);
      the REDEEM carries no YEC inputs (C10).
- [ ] `qa/rpc-tests/ydollar_void_mint.py`: under-collateralised mint, mint whose `evalHeight` is
      older than `MINT_WINDOW` or has no price, mint during ERR at `evalHeight`, mint over the
      supply cap ⇒ VOID; release at lockHeight with zero burn; `yd_abortredeem` unlocks after an
      abandoned redemption (B19).
- [ ] `qa/rpc-tests/ydollar_wallet_restore.py`: dump keys, fresh node with `importprivkey` +
      index sync sees the same balances and positions; encrypted wallet flows.

Exit: full lifecycle passes on regtest; `src/wallet/wallet.{h,cpp}` untouched.

### Phase 4 — Federation coordinator and redemption client (≈ 900 lines Python, 0 lines C++)

- [ ] `contrib/ydollar/ydollar_fed.py` (price rounds with TWAP/outlier/clamp brakes over
      `yd_createpricetx` + `signrawtransaction` + `sendrawtransaction`, `/cosign` over HTTPS,
      rotate) with a `--mock-price` source and an `--insecure-localhost` transport (plain HTTP on
      127.0.0.1) for tests (G7); `contrib/ydollar/ydollar-redeem`.
- [ ] `qa/rpc-tests/ydollar_federation.py`: launches three coordinators against three regtest
      nodes with mock prices; asserts prices land on chain every 8 blocks, that the clamp limits a
      50 % mock jump to 10 % per round, that a member offline still yields 2-of-3, that
      `ydollar-redeem` completes end-to-end (`yd_redeem` → `/cosign` → `yd_submitredeem`), that a
      co-signer refuses an under-burned redemption and refuses during a price outage (RED-6), that
      a peer refuses to co-sign a PRICE transaction whose "refill" input is one of the peer's own
      coins (C5), and that rotation (ROTATION then PRICE) is followed by a successful mint against
      the new roster and a successful redemption of a vault on the old roster.

Exit: federation test green in CI; runbook drafted.

### Phase 5 — Protections (≈ 400 lines)

- [ ] DCA and ERR wired into MINT-4/5 and RED-3 (already in `amount.h`; this phase adds state
      plumbing, snapshots, `yd_getstats` fields, `yd_getprotectionstatus`).
- [ ] Volatility breach/cooldown in SNAP and MINT-4.
- [ ] `qa/rpc-tests/ydollar_protection.py`: drive price down through 149/119/109 % and assert
      `dcaBps`; below 100 % assert mints VOID and `requiredBurn` per ERR tier; spike price 25 % in
      one hour and assert mint freeze and cooldown expiry at exactly `lastBreach + 1728`.

Exit: protection matrix green; `yd_gethistory` shows the snapshots.

### Phase 5b — YecWallet fork `yecwallet-dd` (parallel to Phases 3–6; ≈ 3,200 lines incl. `.ui`)

- [ ] Phase 0 (wallet side): build `ref/yecwallet` unmodified two ways — plain CMake against the
      CI runner's system Qt 6 (this is the development and test configuration; confirm `Qt6::Test`
      is present) and the full static `build.sh` (release configuration, `-no-feature-testlib`,
      H1); record times; confirm it starts the `ycash-dd` `ycashd` placed beside it and that
      `--conf <playground node conf> --no-embedded` attaches to a §6.0 playground node (H2) with
      the stock Balance/Send tabs working (regtest addresses pass `isTAddress`, H3). Record the
      baseline in `yecwallet-dd/docs/ydollar.md`.
- [ ] `doc/ydollar-rpc.md` in `ycash-dd` frozen at the end of Phase 3 (wallet RPCs) and Phase 5
      (protection fields); `yd_getinfo.rpcversion = 1`; the wallet's `Settings` stores the
      version it was built for and refuses others.
- [ ] `connection.cpp`: `experimentalfeatures=1` / `ydollar=1` in `createZcashConf`; existing-conf
      detection and repair offer. (No new command-line options: `--conf` and `--no-embedded`
      already attach the GUI to a playground node, H2.)
- [ ] `YDollarController` + models + the YDollar tab, sub-pages in the order Overview → Receive →
      Send → Mint → Vaults → Transactions → Redeem wizard → Settings, each usable against the §6.0
      playground as soon as its RPCs exist (Overview/Send/Receive/Mint after Phase 3;
      Vaults/Redeem after Phase 4; protection fields after Phase 5). Behaviour follows DigiByte's
      `src/qt/digidollar*widget.cpp` pane by pane (`mapping.md` §12), minus coin control.
- [ ] QTest end-to-end target (optional component, H1) against the playground (mint → send →
      tier-0 lock → redeem through five local operators → abort path → expired-transaction
      display), run in `yecwallet-dd` CI on the cached node build under
      `QT_QPA_PLATFORM=offscreen` (H5).
- [ ] Release: `build.sh --package` with the `ycash-dd` `ycashd` beside the wallet binary, on
      the three platforms `build.sh` already targets (`build.sh:9-15`).
- [ ] Copy review of every user-facing string against §8.1 (trust statement) — the wallet must
      never describe YDollar as trustless or shielded; `git diff yecwallet-legacy...feature/digidollar`
      reviewed against the table in §4.7.

Exit: the QTest target passes in CI against a `ydollar-v1-rc1` node; a non-developer completes
mint, send and redeem on the regtest playground using the wallet alone; the fork diff stays
within the §4.7 table.

### Phase 6 — Hardening, documentation, review (≈ 2 weeks)

- [ ] Fuzz harness for `payload::Decode` and `script::Parse*`: `src/fuzzing/YDollarPayload/fuzz.cpp`
      and `src/fuzzing/YDollarScript/fuzz.cpp` with `input/` corpora, the layout of Ycash's existing
      targets (`ref/ycash/src/fuzzing/CheckBlock/`, C14); plus a Boost test that replays the corpus
      so `make check` covers it without a fuzzing build.
- [ ] Reorg stress test: random 1–6 block reorgs over 500 blocks with random YDollar activity on
      three nodes; assert state-hash equality after every reorg and after a cold rebuild.
- [ ] DoS review: payload parse bounds, `yd_validaterawtransaction` cost and its phantom-input
      refusal (D1), `/cosign` rate limits, HTTP client timeouts, index DB size growth (snapshots
      ≈ 60 B/block ≈ 25 MB/yr; VOID-vault records per block at the mempool cost limit, D9).
- [ ] Determinism audit: grep `src/ydollar/state.cpp` and callees for the forbidden symbols of
      §3.10; add a CI grep.
- [ ] `doc/ydollar.md` (user), `doc/ydollar-federation.md` (operators), RPC help text review.
- [ ] Self-review against the checklist in §8.4; external review request to Ycash maintainers
      with the diff-budget table filled in with actual numbers.

Exit: review sign-off; tagged `ydollar-v1-rc1`.

### Phase 7 — Testnet launch

- [ ] Operators generate keys, build the testnet genesis anchor, fill `params.cpp` (testnet),
      release `rc` binaries.
- [ ] Two-week soak: mints across all tiers, daily redemptions, one planned rotation, one planned
      member outage, one deliberate reorg (mining on a fork), one node rebuilt from scratch —
      each checked with state-hash equality across operators.
- [ ] Fix-forward; tag `ydollar-v1`.

### Phase 8 — Mainnet launch

- [ ] Mainnet key ceremony and genesis anchor; `params.cpp` (mainnet) with `startHeight` set to
      the anchor's block; release.
- [ ] Launch caps per §3.1; review the cap after 90 days of operation (parameter change = software
      release, applied at a published height).

### Phase B — Consensus enshrinement (separate decision, see §9)

---

## 7. Test plan

| Layer | Location | Covers |
|---|---|---|
| Unit | `src/test/ydollar_math_tests.cpp` | §3.6 formulas, overflow, table boundaries |
| Unit | `src/test/ydollar_payload_tests.cpp` | §3.2 codec, every malformed case |
| Unit | `src/test/ydollar_script_tests.cpp` | §3.3 scripts, `VerifyScript` success/failure, size and sigop limits, `IsStandardTx`/`AreInputsStandard` on every template (B5) |
| Unit | `src/test/ydollar_state_tests.cpp` | §3.7 rules on synthetic blocks; apply/undo identity; anchor custody |
| Unit | `src/test/ydollar_address_tests.cpp` | D10 |
| Functional | `qa/rpc-tests/ydollar_index.py` | index, prices, anchor at non-zero input index, reorg, restart, `-reindex`, `-reindex-ydollar`, `-prune` refusal |
| Functional | `qa/rpc-tests/ydollar_lifecycle.py` | mint/send/burn/redeem with RPC co-signing; 0-conf lock; evalHeight price drop |
| Functional | `qa/rpc-tests/ydollar_void_mint.py` | D18 outcomes |
| Functional | `qa/rpc-tests/ydollar_wallet_restore.py` | restore, encryption |
| Functional | `qa/rpc-tests/ydollar_federation.py` | Python coordinator, HTTP co-sign, rotation |
| Functional | `qa/rpc-tests/ydollar_protection.py` | DCA, ERR, volatility |
| Functional | `qa/rpc-tests/ydollar_reorg_stress.py` | randomized reorgs, state-hash equality |
| Fuzz | `src/fuzzing/YDollarPayload/`, `src/fuzzing/YDollarScript/` | parser robustness (C14) |
| Application | wallet application's own CI, against the §6.0 playground | every §4.7 screen; redeem wizard against five local operators; RPC-version refusal |

Every functional test starts its nodes with `ydollar_node_args()` (six upgrades at height 1,
`setup_clean_chain = True`, C12), uses the topology of §6.0 (node 1 without `-ydollar`; 2-of-3 on
nodes 2–4 for lifecycle tests, 5-of-9 with four test-held keys for `ydollar_federation.py`),
relies on `sync_all()` for index synchrony (C13) and asserts `yd_getstatehash` equal on all
`-ydollar` nodes at the end (G6). Unit tests that call `IsStandardTx`, `AreInputsStandard` or
`VerifyScript` select regtest and activate Sapling (and Canopy) with `RegtestActivateSapling()` /
`RegtestActivateCanopy()` (`ref/ycash/src/utiltest.h:40-53`) — `BasicTestingSetup` defaults to
mainnet (`test_bitcoin.h:19`) — so the Sapling version rule is the one exercised
(`policy.cpp:58-68`, C19, D6). The regtest federation uses fixed test keys (`SHA256("ydollar_regtest_oracle_N")`,
mirroring DigiByte's `mock_oracle.cpp`) so tests are reproducible.

---

## 8. Trust statement, threat model, review checklist

### 8.1 Trust statement (to be published verbatim with v1)

YDollar v1 is a federated, over-collateralised stablecoin overlay on Ycash.

- Consensus-enforced (by every Ycash node, upgraded or not): collateral cannot leave a vault before
  its lock height; only the owner *and* k of n federation keys can spend it; price updates carry k of
  n federation signatures.
- Enforced by every YDollar-aware node deterministically: YDollar accounting (conservation, supply,
  collateral totals, vault status, DCA/ERR/volatility state).
- Enforced by the federation's mechanical policy: collateral is released only against the required
  burn; published prices reflect market medians.
- **Therefore:** a colluding quorum of k operators can release collateral without a burn or publish
  a false price. A federation with fewer than k live keys halts redemptions and mints until it
  recovers. Nothing the federation does can create YDollar out of nothing, move a user's YDollar, or
  take collateral without the owner's signature.

### 8.2 Threat model

| Threat | Outcome in v1 | Mitigation |
|---|---|---|
| k operators collude on price | under-collateralised mints (same as DigiDollar's 7-of-35) | roster diversity, exchange-median policy, public price history (`yd_gethistory`), rotation |
| k operators + owner collude on release without burn | unbacked YDollar equal to that vault's mint | visible on chain (`unbacked` flag: `burnedCents < requiredBurnAtClose`, F1); health falls; rotation of the colluding members |
| Federation liveness loss | redemptions and mints pause; transfers continue | n = 9, k = 5; runbook; tiers ≤ 1 y |
| Anchor drained / custody broken | no new prices → mints pause | release with new genesis anchor |
| Wallet spends YDollar as YEC | that YDollar is burned | coin locking; YDollar address format |
| Price or DCA change between building and confirming a mint | none: MINT-4/5 read `Snapshots[evalHeight]`, fixed when the user signs (B3) | residual: a reorg deeper than `MINT_EVAL_LAG` (2) blocks that changes the snapshot at `evalHeight`; the node refuses reorgs over 99 blocks and typical Ycash reorgs are 1 block (C4) |
| Supply-cap race | mint VOID; collateral recoverable at lockHeight with zero burn | wallet warns below `10 × MAX_MINT` of headroom |
| `sendtoaddress` right after `yd_mint`/`yd_send` | none: outputs locked before commit (B4) | three-stage locking; locks survive disconnects (C3) |
| Malicious proposer smuggles a peer's own coin into a PRICE transaction | none: peer refuses inputs its wallet can solve other than the anchor; operator wallets are dedicated | C5 |
| Co-signer used as a signing oracle for a non-vault script | none: RED-7 sighash is computed over the script and value the index holds, never the caller's | C5 |
| Relay node runs `-datacarrier=0` | that node does not relay YDollar transactions; others do | runbook (C23) |
| Miner malleates a YDollar transaction's signatures (txid changes; no SegWit) | index unaffected (keyed on confirmed outpoints); the wallet's copy shows as conflicted, as for any Ycash transaction today | positions and balances derived by key ownership, never by remembered txid (E7) |
| `wallet.dat` read from disk (encryption is experimental in Ycash) | keys exposed | dedicated hosts, full-disk encryption, localhost RPC, offline backups (E5) |
| Reorg | state rolls back exactly | undo records; tests |
| Payload parser bugs | none affect consensus; index bugs are node-local | fuzzing; unhealthy flag; rebuild |
| DoS via `yd_validaterawtransaction` / `/cosign` | CPU on the node/coordinator | bounded parsing, rate limits, RPC auth |
| Malicious co-signer or endpoint alters the redemption | owner's `SIGHASH_ALL` signature fails; SUB-1 rejects before broadcast | nothing leaves the owner's node unverified |
| Co-signer induced to sign a transaction the owner never signed | none: script needs the owner signature anyway | RED-7 makes the refusal explicit |
| Fully co-signed redemption held for later | expires within 40 blocks | RED-8 |
| Oracle outage | mints void; redemptions pause | RED-6; MINTPOL-1; no guessed prices anywhere |
| Wallet file lost after minting | collateral unrecoverable (as for any t-address) | one key per position; backup rule (C8) |

### 8.3 What YDollar cannot affect

Because no consensus or policy code changes: block validity, mempool acceptance, shielded-pool
value balance, fee policy, and P2P behaviour are byte-for-byte those of v4.5.0 for every node,
whether or not `-ydollar` is enabled. A crash bug in `src/ydollar/` must be caught at the
`ChainTip` boundary and turn the index unhealthy rather than affect validation. Note that
`ThreadNotifyWallets` wraps only its mempool notifications in try/catch
(`ref/ycash/src/validationinterface.cpp:223-233`), not the block connect/disconnect calls, so the
index's `ChainTip` override must catch every exception itself, log it, set the unhealthy flag and
return — never throw into the notifier thread.

### 8.4 Review checklist (Phase 6)

1. `git diff --stat ycash-legacy...feature/digidollar` matches §4.1; zero lines in the consensus
   set.
2. `grep -rn "GetTime\|GetAdjustedTime\|mempool\|pwalletMain\|GetArg\|double\|float" src/ydollar/state.cpp src/ydollar/amount.h src/ydollar/payload.cpp src/ydollar/script.cpp` returns nothing.
3. Every rule identifier in §3.7 has a unit test and every policy rule in §3.8 has a functional
   test.
4. Apply/undo identity and cold-rebuild equality tested under reorg stress.
5. All `yd_*` RPCs refuse when the flag is off or the index is unhealthy.
6. Coin locking covers every mine-owned token and vault outpoint after restart.
7. `yd_cosignredeem` never signs when §3.8 fails; test proves it.
8. No new build dependencies; `configure.ac` untouched; `grep -rn "evhttp\|socket\|connect(" src/ydollar src/rpc/ydollar*.cpp` returns nothing.
9. Every `ChainTip` override is exception-safe; a fault-injection unit test proves an exception in
   `ApplyBlock` sets `unhealthy` and does not propagate.
10. `-ydollar -prune` fails at init; `-reindex` rebuilds to the same `yd_getstatehash`.
11. `IsStandardTx` and `AreInputsStandard` pass in unit tests for every template (regtest does not
    run them).
12. A `sendtoaddress` issued immediately after `yd_mint`/`yd_send` cannot select a YDollar output.
13. Every `MINT-4`/`MINT-5` input is read from `Snapshots[evalHeight]`; nothing in the mint rules
    reads `price(H)` or `health(H)`.
14. `yd_createpricetx` output round-trips through `signrawtransaction` on a node that ran
    `addmultisigaddress`, and fails (`complete: false`) on one that did not.
15. `yd_cosignredeem` computes the sighash from the index's vault record only; a test with a
    substituted redeem script in the scriptSig is refused (C5).
16. Disconnecting a block never removes a coin lock (C3); a VOID mint's token output is unlocked
    only once the block is applied.
17. A mint built with `MINT_EVAL_LAG = 2` survives a 2-block reorg with a different price (C4).
18. `-ydollarfee` below `DEFAULT_FEE` is rejected at init (C16); `-ydollarstartheight` and the
    two genesis arguments are rejected outside regtest and must appear together (C2).
19. `yd_validaterawtransaction`/`yd_cosignredeem` refuse a transaction with an unknown or spent
    input **before** touching `AreInputsStandard` or the fee (D1); a unit test proves no assert.
20. The index object is unregistered and stopped under `cs_ydollar` in `Shutdown()` and never
    deleted (D2); a fault-injection test unregisters while a handler is blocked and observes a
    clean return.

---

## 9. Phase B — Consensus enshrinement (design constraint only)

Not part of v1. Recorded so v1 is built in the shape that makes it cheap.

Trigger: the Ycash community wants (a) of §1 enforced by the chain. Mechanism: a network upgrade
`UPGRADE_YDOLLAR` added before `UPGRADE_ZFUTURE` in `Consensus::UpgradeIndex` with a fresh branch
ID (`ref/ycash/src/consensus/upgrades.cpp`) and activation heights in `chainparams.cpp` (`mapping.md`
§4). After activation, in `ContextualCheckTransaction`/`ConnectBlock`:

1. Any transaction spending an ACTIVE vault must satisfy RED-1..3 (the same `state::CheckRedeem`
   function v1 uses for policy) — reject with `bad-vault-spend-missing-burn`.
2. Any transaction carrying a MINT payload must satisfy MINT-1..7 — reject with the same reason
   strings (invalid mints stop being void and start being invalid).
3. Any transaction carrying a TRANSFER/REDEEM payload must satisfy XFER-1..3 (burn-by-mistake
   stops being possible).
4. New vaults may use `<lockHeight> CLTV DROP <owner> CHECKSIG` (no federation key); MINT-3
   accepts both scripts. Existing federated vaults remain valid and redeem as before.
5. The YDollar state becomes consensus state: `db.cpp` moves into the chainstate flush path (same
   LevelDB batch as `pcoinsTip`), which is the one genuinely consensus-critical engineering item and
   the reason v1 keeps `Apply`/`Undo` block-atomic already.
6. The price anchor chain stays as is; tiers 5–9 are enabled because vaults no longer depend on a
   roster's longevity.

Nothing in the payload, scripts, or state schema changes. The federation's remaining role is the
price feed, which is exactly DigiDollar's trust model.

---

## 10. Deviations from DigiDollar (and why)

| DigiDollar (v9.26.5) | YDollar v1 | Reason |
|---|---|---|
| Tapscript opcodes `0xbb–0xbf`, `SCRIPT_VERIFY_DIGIDOLLAR` | none | `mapping.md` §2; not needed for tx-level rules |
| P2TR 2-leaf MAST vault with NUMS key | P2SH CLTV + owner + k-of-n | no Taproot; D3 |
| Consensus rejects invalid mints/redeems | overlay voids/burns; federation enforces burns | D1, D18 |
| `nVersion` bit-packed type/flags | payload type byte | `mapping.md` §5 |
| Coinbase `OP_ORACLE` MuSig2 v0x03 bundle, P2P oracle messages | anchor-chain PRICE transactions, ECDSA k-of-n | D4, D5 |
| 7-of-35 oracle roster | 5-of-9 federation (both price and redemption co-sign) | script-size bound; D3 |
| 10 tiers (1 h – 10 y) | 5 tiers (1 h – 1 y) | roster longevity; D11 |
| Mint $100 – $100,000; no supply cap | $100 – $10,000; $1 M cap (params) | liquidity; D11 |
| ERR path is a separate MAST leaf with `OP_CHECKCOLLATERAL` | ERR only changes `requiredBurn` | no opcode; same economics |
| Volatility freezes transfers/all ops at 24 h/7 d | freezes mints only | burn-safety in an overlay; D12 |
| Volatility uses timestamps and standard deviation | block-window absolute change, integer | determinism |
| Mint window `[tier, tier+100]` at 15 s blocks | `[tier, tier+40]` at 75 s blocks | equals tx expiry |
| Mint collateral checked against the confirmation block's oracle price | checked against `Snapshots[evalHeight]` committed in the payload, `evalHeight ≥ H − 40` | in an overlay a failed mint locks collateral instead of being rejected (B3) |
| Price max age 1 h = 240 blocks | 48 blocks | 75 s blocks |
| Cooldown 8,640 blocks (36 h) | 1,728 blocks (36 h) | 75 s blocks |
| `__int128` | `arith_uint256` | Ycash has no `__int128` use; portability |
| Wallet `dd_*` tables, descriptor wallets required | no wallet tables; keypool wallet + index | D9 |
| Qt GUI: seven DigiDollar tabs in-process over `WalletModel` (`src/qt/digidollar*`, ≈ 10,400 lines) | one YDollar tab with the same seven functions in **YecWallet** (`yecwallet-dd`, Qt 6), over the `yd_*` RPC contract; coin control dropped | Ycash ships no GUI in the node; YecWallet is a separate RPC-driven application (D21, §4.7, `mapping.md` §12) |
| `txindex=1` required | not required | index is self-contained |
| Transfers require confirmed inputs at consensus | wallet-enforced; state machine allows in-block chaining | determinism without a mempool rule |

---

## 11. Inputs required at launch (operational, not design)

| Input | Default in this plan | Who supplies |
|---|---|---|
| Federation membership (9 operators, 5 threshold) | — | Ycash community; recorded in `doc/ydollar-federation.md` |
| Exchange sources for YEC/USD (≥ 3) | Coordinator config | operators |
| Testnet/mainnet genesis anchor outpoint + roster script | placeholders | key ceremony (Phase 7/8) |
| `startHeight` per network | anchor's block height | Phase 7/8 |
| `MAX_MINT`, `SUPPLY_CAP` | $10,000 / $1,000,000 | may be raised by release after 90 days |
| Co-signer endpoint URLs | — | operators; shipped as defaults in `params.cpp` and in the wallet application's settings |
| Full-node wallet application | **resolved (rev. 11):** YecWallet, `github.com/ycashfoundation/yecwallet`, Qt 6 / CMake, JSON-RPC via `Connection` — forked as `yecwallet-dd` | maintainers' review of the `yecwallet-dd` diff (§4.7 table) |

None of these change code shape; all live in `params.cpp` or coordinator config.

---

## Appendix A — Rows to add to `docs/mapping.md`

Each was discovered while writing this plan and is not yet in the crosswalk (added under §11 there
by Phase 0):

1. `IsMine`/`ProduceSignature` cannot solve custom P2SH redeem scripts — a vault is invisible to the
   wallet and unsignable by `signrawtransaction`; sign manually (`rpc/atomicswap.cpp:760-775`) and
   track vaults in the index.
2. Single `OP_RETURN`, 80 data bytes (`policy.cpp:52,123`, `standard.h:34`) — payloads are
   size-budgeted; roster pubkeys cannot ride in a payload; rosters are revealed by anchor spends.
3. Transaction expiry (`main.h:78-81`) — bounds the mint window and forbids "never expires"
   redemptions in practice; use `tip + 40`.
4. `ThreadNotifyWallets`/`ChainTip` (`validationinterface.cpp:183-217`) — asynchronous, ordered
   connect/disconnect delivery; index must be idempotent and report its own height.
5. 520-byte push, 1650-byte scriptSig, 15 P2SH sigops — bound the federation roster to n ≤ 13.
6. No `__int128` anywhere in Ycash; use `arith_uint256`.
7. `secp256k1` built with recovery module only (`configure.ac:1282`) — no Schnorr/MuSig2.
8. `nVersion == 4` pinned; `nExpiryHeight`, `valueBalance`, shielded vectors exist on every tx —
   YDollar rules must state transparency (TX-0).
9. `createrawtransaction` has no `"data"`/`OP_RETURN` output (`rpc/rawtransaction.cpp:539-620`) —
   PRICE transactions are built by a node RPC (`yd_createpricetx`), not by the coordinator.
10. `signrawtransaction` takes a `prevtxs` `redeemScript` only with explicit private keys
    (`rpc/rawtransaction.cpp:966-974`); wallet signing needs `addmultisigaddress` first.
11. Regtest `fRequireStandard = false` (`chainparams.cpp:671`), no `-acceptnonstdtxn` — relay
    standardness is testable only in unit tests.
12. `test_framework/util.py:40-42` carries Zcash's Blossom/Heartwood/Canopy branch IDs; Ycash's
    differ (`consensus/upgrades.cpp`) and `-nuparams` rejects unknown IDs (`init.cpp:1212-1246`).
13. `MAX_REORG_LENGTH = 99` (`main.h:62`) — the node refuses deeper reorgs; only
    `RewindBlockIndex` moves the tip further.
14. `CWalletTx::IsTrusted` makes own 0-conf outputs spendable (`wallet.cpp:4842-4867`) — overlay
    coins must be locked before commit, not after confirmation.
15. `CreateNewContextualCMutableTransaction` (`main.cpp:7364`) and `DEFAULT_FEE = 1000`
    (`policy/fees.h:15`) replace hand-set versions and fee loops.
16. `TransactionBuilder` (`transaction_builder.h`) has no raw-script output and signs only
    keystore-solvable inputs — unusable for `OP_RETURN` payloads and vault spends.
17. `SyncTransaction` is emitted with `pblock == NULL` for mempool arrivals, conflicts **and**
    disconnected-block transactions alike (`validationinterface.cpp:183,210,226`) — overlay coin
    locks must survive disconnects (C3).
18. `signrawtransaction` signs every input the wallet can solve and resolves inputs through
    `pcoinsTip` + `CCoinsViewMemPool` (`rpc/rawtransaction.cpp:906-921,1044-1057`) — dedicated
    operator wallets; peers refuse foreign inputs they can solve (C5); `prevtxs` only when the
    input is in neither chain nor mempool (C11).
19. ZIP-401 `LOW_FEE_PENALTY` below `DEFAULT_FEE` (`mempool_limit.cpp:151-157`) — flat fee floor
    (C16).
20. Regtest activates no upgrade by default (`chainparams.cpp:576-604`); functional tests pass
    six `-nuparams`; `sync_blocks`/`sync_mempools` already wait on `fullyNotified`
    (`test_framework/util.py:133,160`) (C12, C13).
21. Ycash fuzz targets live in `src/fuzzing/<Target>/fuzz.cpp` (C14).
22. `CCoinsViewCache::GetOutputFor`/`GetValueIn` assert the input exists (`coins.cpp:898-912`) —
    check availability before any policy call on caller-supplied transactions (D1).
23. The notifier thread is joined before `Shutdown()` only on the normal path
    (`bitcoind.cpp:52-55,191-194`) — validation-interface subscribers are stopped under their own
    lock and never deleted (D2).

## Appendix B — Glossary

- **Anchor** — the federation's k-of-n P2SH UTXO whose spends carry price attestations.
- **Roster** — the ordered set of federation public keys and threshold; identified by the redeem
  script revealed when an anchor is spent.
- **Vault** — a P2SH collateral output created by a MINT.
- **Token output** — a transparent output assigned YDollar cents by a payload.
- **Void mint** — a MINT whose payload parsed but whose rules failed; collateral is locked, no
  YDollar exists.
- **Index** — the node-local, rebuildable YDollar state database.
