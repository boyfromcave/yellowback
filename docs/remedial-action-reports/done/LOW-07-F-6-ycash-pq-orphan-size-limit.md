# LOW — 07/F-6 — Orphan size bound (5,000 B) drops every SLH-DSA spend that arrives before its parent

**Repos / branches to change:** `ycash-dd` (`src/main.cpp`, `src/main.h`, `src/test/DoS_tests.cpp`) and `ycash6` (same, 6.20.0 line numbers), branch `fix/07-F-6-pq-orphan-size` off `upgrade/vault` in each.
**Audit source:** `07-node-rpc-mempool-durability-ci.md` §F-6 (`:186-193`); `verification/07-verification.md` row F-6 (`:16`), detail (`:94-96`).
**Status:** done — completed 2026-10-13T12:00Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13, re-confirmed 2026-10-14 at ycash-dd 3fe3492b6 and ycash6 1ebfee622; nightly tier pending the owner's dispatch)

## 1. Finding

`AddOrphanTx` refuses to park any transaction larger than 5,000 bytes (an inherited Bitcoin Core bound from the era of 10,000-orphan maps). An SLH-DSA `TX_PQPKH` spend is ~8,044 B and a V/I owner spend with an SLH-DSA signature is similar, so a PQ child that reaches a node before its parent is logged "ignoring large orphan tx" and dropped: not parked, not added to `recentRejects`, and the stock relay never re-`inv`s it. Chains of PQ transactions (a YED mint followed by a transfer, an x402 voucher chain, a YEW change-spend) relay only when strictly parent-first; out-of-order arrival, which `inv`/`getdata` ordering produces routinely across several hops, silently loses the child until the sender rebroadcasts. Falcon spends (~1.6 KB) are unaffected. Relay policy only; both verifiers confirmed Low.

## 2. Root cause

ycash-dd `055d9c2`:
- `src/main.cpp:645-660` `AddOrphanTx`: `unsigned int sz = GetSerializeSize(tx, …); if (sz > 5000) { LogPrint("mempool", "ignoring large orphan tx …"); return false; }` with the stale comment "10,000 orphans × 5,000 bytes = 500 MB"; the actual default is `DEFAULT_MAX_ORPHAN_TRANSACTIONS = 100` (`src/main.h:80`).
- `src/main.cpp:6756-6764` `tx` message handler: on `fMissingInputs` (no JoinSplits/Sapling) → `AddOrphanTx` then `LimitOrphanTxSize(-maxorphantx)`; the `else` branch (`recentRejects->insert`) is not taken for an oversize orphan, so the txid can be re-requested but nobody re-announces it.
- Policy sizes: `MAX_STANDARD_PQ_SCRIPTSIG = 9,000` (`src/policy/policy.h:37-39`), SLH-DSA scriptSig 7,938 B (`pq_constants`).
- ycash6 `e866c45`: `src/main.cpp:694` (same bound), `:8756` (`-maxorphantx`), `src/main.h:85` (`DEFAULT_MAX_ORPHAN_TRANSACTIONS = 100`).

## 3. Fix options considered

1. Leave as is and require clients to relay parent-first (the status quo, undocumented). Rejected: the loss is silent and the clients cannot control multi-hop ordering.
2. Raise the per-orphan bound unconditionally to cover one SLH-DSA input (e.g. 10,000 B). Simple; changes the pre-activation relay surface by 2× for a 100-entry map (1 MB). Acceptable but gratuitous before activation.
3. Raise the bound only once `UPGRADE_VAULT` is active for the next block, to `MAX_STANDARD_PQ_SCRIPTSIG + 1,000` (= 10,000 B), keeping the count bound (`-maxorphantx`, default 100). **Recommended** — the PQ shape exists only after activation; memory ≤ 100 × 10 KB.
4. Bound the orphan map by total bytes instead of count (Bitcoin Core's later `-maxorphantx` weight accounting). More code; not needed for a Low item.

## 4. Recommended fix

Both lines (the function is in the unchanged baseline part of `main.cpp`; this is relay policy, not consensus, but `main.cpp` is a review-gated file on `upgrade/vault` — carry the rule-4 note "no consensus semantics; orphan parking only"):

1. `src/main.h` (dd `:80`, y6 `:85`): add `static const unsigned int MAX_ORPHAN_TX_SIZE = 5000;` and `static const unsigned int MAX_ORPHAN_TX_SIZE_VAULT = 10000; // one post-quantum scriptSig (MAX_STANDARD_PQ_SCRIPTSIG) plus a transaction skeleton (audit 07/F-6)`.
2. `AddOrphanTx` (dd `:645-660`, y6 `:694`): compute `const unsigned int maxSize = Params().GetConsensus().NetworkUpgradeActive(chainActive.Height() + 1, Consensus::UPGRADE_VAULT) ? MAX_ORPHAN_TX_SIZE_VAULT : MAX_ORPHAN_TX_SIZE;` (the function already requires `cs_main`); replace `5000` by `maxSize`; fix the stale comment ("`-maxorphantx` (default 100) × `maxSize` bounds the map at ≤ 1 MB").
3. `doc/yellowback-pq-dos.md`: one paragraph in the relay section (orphan memory bound after activation, 100 × 10 KB) so the DoS budget stays documented.
4. Optionally (same PR): when an orphan is refused for size, insert its hash into `recentRejects` only if its size also exceeds `MAX_TX_SIZE_AFTER_SAPLING`; otherwise leave it re-requestable (today's behaviour). No change recommended beyond the comment.

A transaction with two SLH-DSA inputs (~16 KB) or YEW's 250-input Falcon maximum (~394 kB, 06/L-2) is still not parked; that is the same class as any large legacy transaction and is documented, not fixed, here.

## 5. Tests

- Unit: `src/test/DoS_tests.cpp` already exercises `mapOrphanTransactions` (`DoS_mapOrphans`). Add a case: build a transaction with one 7,938-byte push-only scriptSig (an SLH-DSA-shaped owner spend; signature validity is irrelevant to orphan parking) and a missing parent; with regtest `UPGRADE_VAULT` unset, `AddOrphanTx` returns false; with it active at `chainActive.Height()+1` (`UpdateNetworkUpgradeParameters` in the fixture), it returns true and `LimitOrphanTxSize(100)` keeps it; a 10,001-byte one is refused.
- Functional (both lines): `qa/rpc-tests/vault_pq_relay.py` (new, nightly-ok but small enough for the merge gate) using `test_framework/mininode.py`: a P2P peer sends the SLH-DSA child `tx` before its parent to node 0; assert the child is absent from `getrawmempool`, then send the parent and assert **both** appear (orphan resolved). Run once pre-activation (child dropped, stays absent after the parent) and once post-activation.

## 6. Acceptance criteria

- After activation an ~8 KB PQ transaction with a missing parent is parked and admitted once the parent arrives, on both lines; before activation behaviour is unchanged.
- Orphan memory bound documented; `-maxorphantx` semantics unchanged.
- `DoS_tests`, the new functional case, `yellowback_pq*` and `vault_pq*` suites pass; `pq-dos` doc updated.

## 7. Risks and side effects

- Relay-only; no consensus or client change. The orphan map's worst case doubles (0.5 MB → 1 MB at the default count). A peer can still fill it with junk orphans, exactly as today; eviction is random (`LimitOrphanTxSize`).
- `main.cpp` is a review-gated file on `upgrade/vault`: the PR body states that the hunk has no consensus semantics.

## 8. Effort estimate and dependencies

~1–2 hours per line plus the mininode functional test (~2 hours once, ported by delta). No dependencies.

## Completion record

- **Completed:** 2026-10-13T12:00Z
- **Merged:** with fix/mempool. ycash-dd 3204460cd + 9c38e3204: SLH-DSA-sized orphans park once UPGRADE_VAULT is active, up to 99,999 bytes (parity with 6.20.0's 100,000 bound; 100 × 100 KB). ycash6 already had the bound, so only tests were added. vault_pq_relay.py passes on both lines.
- **Verification:** the same final pre-push run as 07/F-1.
