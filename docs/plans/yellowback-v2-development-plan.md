# Ycash Yellowback (YED) v2 — Development Plan: miner-enforced Yellowback

**Execution status (2026-09-11, coordinator).** Node line `feature/yellowback-sf` is at `0d41a4a64` and builds clean: 115 `yellowback_*` unit tests green, `src/main.cpp` **11** changed lines vs `ycash-legacy` (budget 40, all six §4.3 sites, every statement under `if (g_yellowback)`, `DoS(0)` only), `src/miner.cpp` **12** (budget 35), `src/rpc/mining.cpp` **7** (budget 35), and the consensus set of §4.1 at **zero**.

| Phase | State |
|---|---|
| 0 — strip the federation, re-baseline | **complete**, both forks |
| 1 — protocol library v2 | **complete** (`77fa95b0b`) |
| 2 — state machine v2 | **complete** (`f86580c2a`); the C++ state hash reproduces the independent Python model's pinned golden vector |
| 3 — index, hooks, node RPCs | **complete and verified** (2026-09-11): all 9 checkboxes; `rpc-tests.py yellowback_index yellowback_activation yellowback_rpc_contract` exits 0 (1,519 s); the binary matches `doc/yellowback-rpc-contract.json` for all 19 node commands and all 8 node error identifiers |
| 4 — template filter, `getblocktemplate` | **complete**, merged (found and fixed a real defect: `OverlayStateView` was implicitly copyable, so a template dry run committed into the live index; the copy ctor is now `= delete`) |
| 5 — enforcement, the soft fork | **in progress**; the node machinery exists from Phases 3–4, the scripted safety scenarios of §7/§8.1 are being written |
| 6 — wallet: mint, send, redeem, claim | 7 of 9 checkboxes done; `yed_mint`/`yed_send`/`yed_redeem` are **live-tested** end to end on a six-node regtest; `yellowback_claim.py` and `yellowback_pricefeed.py` written, **not yet run** |
| 7 — quote agent, pool kit, devnet, docs | **complete except the pool-stack survey** (§12 Q9), which needs the operators; `yellowback_quote.py` passes, the devnet reaches `active` with real agents, `doc/yellowback-mining.md` written |
| 7b — YecWallet | **7b-a and 7b-b committed**; mint → send → redeem verified against a live devnet through the GUI's own code path; claim/sweep wired and offline-tested, awaiting the node RPCs |
| 8 — hardening and review | **started**: `doc/yellowback-review.md` v2 written with measured diff-budget actuals, the 11-site hook table with each four-part check, the safety-property evidence and the §8.4 checklist scored (11 PASS / 7 PARTIAL / 4 NOT YET / 2 FAIL / 1 awaiting a reviewer), plus the §8.5 statement drafted. **Not** complete: H1–H12 wallet hardening, `yellowback_runbook.py`, the reorg-stress adaptation, the rc1 run-through, and the two FAILs below |
| 9, 10 — testnet with real pools, mainnet | cannot be executed on one machine; they need pool operators |

**Open defects found by the review pass (2026-09-11), each to be closed before rc1:**

1. **Lock-order inversion (safety).** `src/rpc/yellowbackwallet.cpp` `yed_getbalance` takes
   `cs_yellowback` and then `mempool.cs` inside it, against the recorded order of §4.3/N25
   ("no RPC may take `mempool.cs` after `cs_yellowback`"). `CreateNewBlock` and
   `RemoveInvalidVaultSpends` take the opposite order, so this is a genuine deadlock pair that
   `cs_main` being held on both sides currently masks; `DEBUG_LOCKORDER` would abort on it.
   A tree-wide scan found no other instance. Assigned to the Phase 6 owner of that file.
2. **Rule→test tag coverage (§8.4 item 9) fails**: `TPL-1`, `TPL-2` are tagged but indented, and
   the acceptance grep anchors `# Rule:` at column 0; `MINTPOL-1` appears only in a docstring;
   **`TPL-3` has no test anywhere**. Assigned to Phases 5 and 6.
3. `yellowback_stockparity.py` and `yellowback_stock_node.py` (§8.4 item 21) do not exist yet —
   Phase 5.
4. The nightly `lockorder`, `sanitizers` and `coverage` jobs have never run: the fork branch has
   never been pushed, and Apple clang ships no libFuzzer (mapping §13.1), so the 8 CPU-hour fuzz
   run and the coverage floors remain unevidenced on this host.

Per-checkbox state is in §6; every impedance mismatch found while building is a row in `docs/mapping.md` §13.1–§13.9.

**Status:** DRAFT — revision 6 (2026-09-10; revision 5 plus one further audit — safety of the valve and the abandonment machinery against the pinned tree, followability of the wallet paths, and the mechanical strength of the test and CI gates — §0). **Ready for implementation, with four protocol adjustments applied and awaiting the product owner's confirmation (L11–L14, §0):** every open item in §12 is a parameter or a post-launch question; nothing in Phases 0–8 waits on a decision other than those four confirmations, each of which is applied in the text so that a "yes" changes nothing; every phase ends in an acceptance block whose exit code decides (§6), every safety claim of §8.1 has a scripted scenario (§7), every CI gate that must be mechanical is a command (§6.0 item 6), and the commands a developer needs on day one are in §6.0 item 0. Written against
[`../reference/yellowback-miner-enforced-proposal.md`](../reference/yellowback-miner-enforced-proposal.md)
(proposal v0.2, 2026-09-10) and against the prototype code on `feature/digidollar` (the
federation prototype; tip `f7e7eaeaa` in the node fork, `34e0679` in the wallet fork), which
Phase 0 strips of its federation and which is the starting point for this work. Every claim about
the Ycash tree below was read at the pins on 2026-09-10; every claim about the prototype was read
at those tips on the same day. Revision history is in §0.

**Pins this plan was written against** (verify with `make status` before trusting any line cite):

| Repo | Pin | Commit |
|---|---|---|
| `ref/digibyte` | tag `v9.26.5` | `05b50e229d` |
| `ref/ycash` | tag `v4.5.0` | `624c12814` |
| `ref/yecwallet` | tag `v4.5.0` | `1eb277d` |
| `ycash-dd` | federation prototype on `feature/digidollar` (tip `f7e7eaeaa`); v2 on **`feature/yellowback-sf`**, already branched from that tip (checked out on 2026-09-10) | base `624c12814` |
| `yecwallet-dd` | federation prototype on `feature/digidollar` (tip `34e0679`); v2 on **`feature/yellowback-sf`**, already branched from that tip | base `1eb277d` |

**One-line summary.** Yellowback v2 keeps everything the federation prototype built that is not the federation — the
colored-output token model, the payload codec, the rebuildable LevelDB index with per-block undo,
the manual transaction builder, the three-stage coin locking, the `yed_*` RPC contract, the
regtest playground, the fuzzers, the YecWallet tab — and replaces the federation with **mining
pools running a patched `ycashd`**: pools publish a YEC/USD quote in a coinbase tag, refuse to
mine rule-breaking Yellowback transactions, and, once ≥ 75 % of blocks signal, refuse to build on
a block that spends a vault in breach of them. The vault script becomes owner-only with an anyone-can-claim path after a
grace period; no key but the minter's ever touches collateral. It **is a soft fork**, carried by
mining software, and this plan says exactly which lines of `main.cpp` and `miner.cpp` carry it,
why those and no others, and how a pool operator turns it off.

**How to read this document.** §1 is the decision and its cost. §2 is the decision record (V1–V26:
every place the proposal was adapted to Ycash or simplified, with the option weighed and what it
costs). §3 is the normative protocol. §4 is the code architecture in `ycash-dd` and `yecwallet-dd`,
including the exact hook lines. §5 is the quote agent and the pool-integration kit. §6 is the
phased work plan with exit criteria; **§6.0 is how one developer builds and tests a multi-pool
network on one laptop.** §7 is the test plan, §8 the trust statement and threat model, §9 the later
network-upgrade path, §10 the deviations from the proposal, from the federation prototype and from DigiDollar, §11 the
launch inputs, §12 the open questions. Implementers start at §6 and refer back.

**Relation to the other documents.** The wallet-side hardening items (coin selection and coin
locking, H1–H12) are stated inline in Phase 8 of this plan. The interoperability idea lives in
`../ideation/` and is inactive; it builds on the `yed_*` index, not on anything this plan changes.
[`../why-miner-enforced.md`](../why-miner-enforced.md) is the plain-language rationale for this
plan: the rule Ycash script cannot express, why every no-fork remedy ends in a committee, why
miners, and the trade-offs of §1 and §8 in one table.

---

## 0. Revision log

### Revision 1 (2026-09-10) — first draft

Written from the proposal v0.2, the v1 plan and three code surveys made for this document: the
Ycash template and coinbase path (`miner.cpp`, `rpc/mining.cpp`, the coinbase consensus limits),
the block-connect and mempool paths (`main.cpp`: `ConnectBlock`, `DisconnectBlock`, `ConnectTip`,
`DisconnectTip`, `InvalidBlockFound`, `ReconsiderBlock`, `AcceptToMemoryPool`, `VerifyDB`,
`FlushStateToDisk`), and a file-by-file inventory of the v1 fork classifying every file as
reuse / adapt / remove (§4.2). Findings that changed the proposal are recorded as decisions in §2
and listed in §10.1.

### Revision 2 (2026-09-10) — two audits of revision 1

Revision 1 was audited the same day by two independent passes: one over the protocol (§1–§3, §7,
§8, §10, §12; arithmetic recomputed by hand, every proposal parameter traced, every rule checked
for determinism and for over- or under-rejection), one over the architecture and test workflow
(§4–§6.0, Phases 0–5, §8.4; every hook line cite re-read in `ref/ycash`, the v1 reuse claims
spot-checked in `ycash-dd`, the Python framework checked for what it can sign). Findings and the
resulting changes, most severe first:

| # | Finding | Severity | Change |
|---|---|---|---|
| K1 | Fail-open (V13, BLK-3) was attacker-triggerable: any evaluation path that could throw — a missing `Snapshots[refHeight]` (RED-1 had no `refHeight ≥ START_HEIGHT` bound), an undefined quantity in a division — would let one crafted vault spend, mined by a stock miner, make **every** enforcing node accept the block and disable enforcement network-wide until each operator reindexed. | **safety** | `EvaluateBlock` is **total**: every undefined lookup is a verdict, never an exception; it is fuzzed for throws (Phase 2 exit criterion); the BLK-3 boundary is restricted to storage failures. RED-1 gains `refHeight ≥ START_HEIGHT`. §8.2 row. |
| K2 | "Status never moves backward" plus "enforce iff ACTIVE" meant enforcement never ends: if module hashpower later fell below half, an enforcing node that saw one rule-breaking spend would fork onto a minority chain and, after 99 blocks, need `-reindex` to return. The trust statement said only "minting halts". | **safety** | **ACT-5:** BLK-1 additionally requires `¬Snapshots[H−1].haltMask.PARTICIPATION`; enforcement suspends with minting and resumes at 75 %. Recorded in V12, §8.1, §10.1; runbook step for a rising `rejectedBlocks`. |
| K3 | VOID vaults were policed by RED-1..4 and BLK-1. A VOID vault costs dust and its `lockHeight`/`claimHeight` may already be past (MINT-2 can fail on the lock), so anyone could mint one and claim-path-spend it in the same block through a stock miner, orphaning stock-mined blocks at zero cost on demand; benign owner sweeps could also be over-rejected. | **safety** | BLK-1 and RED-1..4 apply to **ACTIVE** vaults only (V3, RED-1, §10.1). A VOID vault's spend is an ordinary spend. The wallet never creates one except by the cap race or a deep reorg, and `yed_getvault`/the GUI warn a VOID owner to sweep before `claimHeight`; strict template policy declines claim-path sweeps of VOID vaults. |
| K4 | Path detection required exactly `OP_1`/`OP_0` selectors, but consensus verifies vaults with `P2SH \| CLTV` only (`main.cpp:2931`) — no `MINIMALDATA`, no `MINIMALIF` — so `<sig> OP_2 <script>` is a consensus-valid owner spend the plan would have made block-invalid. | safety (over-rejection) | Path = `CastToBool(selector)` per interpreter semantics; structural push-count checks are strict-template policy only (§3.4, RED-1). |
| K5 | `CheckConnect` runs under `TestBlockValidity` with `pindex = &indexDummy`, whose `phashBlock` is null (`chain.h:322-324, 368-371`); anything keyed on `pindex->GetBlockHash()` would crash on every template. | **feasibility** | `CheckConnect` uses `block.GetHash()` and `pindex->pprev->GetBlockHash()` only; unit test with a null-hash index (§4.3, §8.4). |
| K6 | `verifychain` (`rpc/blockchain.cpp:898-923`) runs `VerifyDB` at runtime with the index alive; level 4 reaches `CommitConnect` with the index tip ≠ `pprev`. Treating that as unhealthy would let a maintenance RPC disable enforcement; treating it as a silent skip would hide a real desync. | safety | The hooks distinguish the two: if `chainActive.Contains(pindex)` the block is being re-verified (`VerifyDB`) and the hook is a silent no-op; otherwise a tip mismatch marks the index unhealthy. `verifychain 4` is in the Phase 3 test. |
| K7 | `CWallet::CommitTransaction` records the transaction (`wallet.cpp:5725`) before `AcceptToMemoryPool` (`:5743`); an MP-1 refusal after the wallet's own dry run would strand a signed, never-mined transaction. The dry run (`EvaluateBlock`) and MP-1 (`MempoolCheck`) were two predicates. | safety | One predicate: `MempoolCheck` calls `EvaluateBlock` on a one-transaction pseudo-block; `yed_redeem`/`yed_claim` call `MempoolCheck` before `CommitTransaction` (§4.6). |
| K8 | The payee weight `1 + inBand` was a *count* over 576 heights, making selection quadratic in hashpower (a 50 % pool ≈ 289× a 1 % pool per block) and contradicting the Phase 2 "2:1" test. | precision / incentive | `w_h = 10⁴ + 10⁴ · inBand / quoted` (accuracy as a fraction of the miner's own judged quotes, bps), FEE-2 (now FEE-W after L1). §10.1 row ("576 heights, not 576 quotes"). |
| K9 | Tags are unauthenticated: a pool can publish a quote under another pool's `payoutKey`, penalising the victim and diluting its accuracy for the cost of one tag slot. | safety (gap) | §8.2 row; §12 item (a signed-tag variant fits the 100-byte budget only without pool text; deferred). |
| K10 | RED-3 (fee) pulls registration, judgement and accuracy into block validity; RED-4 pulls two medians. V3's "one pure function over one script-identifiable set" understated the consensus-shaped surface, and a parameter change (`N_REG`, `PEER_*`, `FEE_*`, `GRACE`, …) is a coordinated change of the enforcing set. | design | Stated in V3 and §9; parameters are versioned by start height and changed only in a release (§3.1). The alternative — demote the fee to template policy, which removes REG-1..4 from validity but lets fee-less redemptions through stock miners — was §12 Q13 for the team, decided in revision 3 (L1). |
| K11 | Once `C(R)` is empty, "`feeVout == 0xFF`" made a voluntarily fee-paying redemption block-invalid. | over-rejection | When `C(R)` is empty `feeVout` is ignored (MINT-8, RED-3). |
| K12 | SIGMA-1 silently fell to 1× when any sampled `pFast` was undefined (fail-open on the safety side); "42 samples" was 43. | safety | An undefined sample ⇒ `SIGMA_MULT_MAX_BPS`; 43 samples, `n = 42` returns. |
| K13 | Regtest `VOL_PERIODS_PER_YEAR = 8,760` contradicted "`= BLOCKS_PER_YEAR / VOL_STEP`". | precision | Independent parameter, 8,760 on every network so a return series gives the same multiplier everywhere; the formula is dropped from V17. |
| K14 | Worst-case collateral arithmetic: class A × 3× = 150,000 bps ⇒ `1.5·10¹⁹` exceeds `int64`; at `PRICE_MIN` the requirement exceeds `MAX_MONEY`. `FEE_MIN` = 0.5 YEC can exceed a tiny vault's collateral at a high YEC price. | precision / user-loss | Numbers corrected; `RequiredCollateralRounded` rejects `> MAX_MONEY`; MINT-5 adds `collateralZat ≥ 4 · FEE_MIN` so a fee can always be paid from collateral (§10.1). |
| K15 | ACT-4's "iff … cleared only when" was self-contradictory, and the hysteresis reads `Snapshots[H−1].haltMask`, which was unstated. | determinism | Reworded as carried state. |
| K16 | Off-by-one: status becomes ACTIVE in `Snapshots[activateHeight]`, so BLK-1 first applies at `activateHeight + 1`; the devnet's `2 × 64` blocks left `R = 126` not yet ACTIVE; Phase 3's "48th signalling block" case contradicted ACT-2's full-window bound. | precision | Recorded in §10.1; devnet mines `2 · 64 + REF_LAG + 1`; the Phase 3 case interleaves stock blocks. |
| K17 | `COINBASE_FLAGS` would be assigned under `cs_main` but the internal `-gen` miner reads it at `miner.cpp:832` without the lock — a data race once anything assigns it. | feasibility | The `-gen` loop's `IncrementExtraNonce` call takes `LOCK(cs_main)` (two lines, in budget). |
| K18 | The adversarial "owner-path spend without a burn" needs the owner's ZIP-243 signature; `signrawtransaction` cannot solve an `OP_IF` script and the plan invented an RPC helper. The shipped framework can sign natively: `test_framework/script.py:871 SignatureHash` (ZIP-243) and `key.py:88 CECKey`. | feasibility | `build_vault_spend_raw` takes the owner WIF from `dumpprivkey` and signs in Python; no new RPC (§6.0). |
| K19 | `split_network`/`join_network`/`sync_all` are hard-wired to four nodes (`test_framework.py:55-98`); the six-node topology needs an override, and every `split_network` restarts all nodes. | feasibility | `YellowbackTestFramework` base in `yellowback_util.py` with `num_nodes = 6` and a split point (as v1's `yellowback_reorg_stress.py:65-78` does). |
| K20 | `CommitConnect` placed "after `:3194`" would run before the undo/index writes that can `AbortNode` (`:3204-3263`), widening the index-ahead window. | precision | Placed after `view.SetBestBlock` (`:3268`). Cites corrected: `control.Wait()` `:3188-3189`, `fJustCheck` `:3193-3194`. |
| K21 | Kill-switch loop: `chainActive.Tip()` can be null on a fresh datadir before `ThreadImport`; `ActivateBestChain` should run after releasing `cs_main` as `reconsiderblock` does (`rpc/blockchain.cpp:1497-1509`). | precision | Skip when `Rejected` is empty or the tip is null; lock scope around the loop only. |
| K22 | `-yellowbackpayoutaddress` must be P2PKH (the tag carries a Hash160 for P2PKH); "any transparent address" admitted `s3…`. `RewindBlockIndex` runs before the index exists, so the index can be ahead of the chain at start. | precision | Init refuses non-P2PKH; defaults from `-mineraddress` when that is transparent. Rewind noted under startup. |
| K23 | Loose ends: `MINT` payload is 51 bytes not 52; `Totals` lacked closed/claimed counts; `feeVout` could coincide with an assigned vout; MINER-2 did not say "no payout address ⇒ no tag"; V26 and §4.4 listed different GBT fields; `yellowback_price.py` named both a module and a test; `yed_mint`'s numeric-or-string argument broke `rpc/client.cpp`'s index-based conversion; `yellowback_protection.py` and `load_config` were missing from the removal/keep lists; the CI socket grep matches `UndoDisconnect(`; `UNDO_KEEP` is already in `index.h`; the build/test budget row is ≈ 90; §1 said "tagged blocks" for the payee window; regtest `-yellowbackstartheight` must be one value across nodes. | precision | All fixed in place. `yed_mint <cents> <lockBlocks> [from]`: the class is derived from the lock length (the ranges are contiguous and disjoint); the payload still carries it and MINT-2 checks consistency. |
| K24 | Proposal fidelity: the proposal's un-registration of an untagged miner (§4.1 there), the "embed the filter in the stratum layer" option (§3.3), and an unhealthy pool continuing to mine were unrecorded. | fidelity | §10.1 row; §8.2 row and a `-yellowbackrequirehealthy` option (default off) that makes `getblocktemplate` refuse while unhealthy. |

### Revision 3 (2026-09-10) — two decisions by the product owner

| # | Question | Decision | Change |
|---|---|---|---|
| L1 | Q13 — is the enforcement fee block validity or policy, and how much of the payee arithmetic rides along? | **Amount plus any recent pool.** Block validity requires a fee of the right amount to *any* pool that published a quote tag in the payee window; *which* pool is wallet policy (default: the accuracy-weighted selection of revision 2). | V10 rewritten; FEE-2 split into the validity rule (eligible set `E(R)`) and the wallet default (FEE-W); MINT-8/RED-3 check membership in `E(R)`; REG-2/REG-3 leave the shared rules and become informational (`yed_listminers`) and the wallet's default preference; V3/K10's consensus-shaped surface shrinks to the price windows, `PAYEE_WINDOW`, the fee constants, `CLAIM_THRESHOLD_BPS` and `GRACE`. §10.1 row; §12 Q13 closed. |
| L2 | Q10 — what does "miner-enforced" mean on a chain with few pools? | The pool landscape is known and diverse (several independent pools, none near half of blocks; product owner, 2026-09-10). **A written launch bar is added:** mainnet signalling is announced only when at least `N` independent pools run the module and no single pool exceeds `X %` of signalling blocks; `N` and `X` are set in Phase 9 from the measured distribution and published with the announcement. | Phase 10 and §11; §8.2 row; §12 Q10 closed. Nothing in code: a pool can signal from many keys, so diversity cannot be enforced by a rule. |

Everything else in revision 1 survived: the tier and hook placement, the `COINBASE_FLAGS`
carrier, the external quote agent, the vault script, transparent YED, `refHeight`, the activation
state machine, the medians and selectors, the diff budget and the phase structure. The §3.7
arithmetic, the §3.1 parameter mapping to the proposal's Appendix B, the refHeight/expiry
arithmetic and the determinism of every rule were confirmed by the audit.

### Revision 4 (2026-09-10) — five audits of revision 3; four decisions by the product owner

Revision 3 was audited by five independent passes: identifiers and cross-references; protocol
completeness and determinism (could two implementations of §3 produce bit-identical state?);
every `file:line` citation re-read at the pins; implementation readiness of §4–§8 (could Phase 0
start tomorrow?); and the rationale document `../why-miner-enforced.md` against this plan. The
product owner then decided four questions the audits raised. Decisions first, then findings.

| # | Question | Decision (product owner, 2026-09-10) | Change |
|---|---|---|---|
| L3 | ACT-4/5 suspended block rejection when signalling fell below 60 % and resumed it at 75 %, so > 40 % of non-signalling hashpower (an attacker plus every stock pool) could switch enforcement off network-wide in ≈ 42 h and > 25 % could keep it off; while off, the owner path and the claim path were both unpoliced, and §8.1 said only "the claim path". The signal bit was also set regardless of `-yellowbackenforce`, so the count over-stated enforcing hashpower. | **Split the floors.** Block rejection suspends only when signalling in the trailing window falls below **50 %** (`ENFORCEMENT_FLOOR = 1,008`) and resumes at **60 %** (`ENFORCEMENT_RESUME = 1,210`); the mint halt keeps 60 % / 75 %. The signal bit is set only by a node that also enforces. | ACT-6 and the `ENFORCEMENT` halt bit (§3.7, §3.8); ACT-5 reads it; MINER-1; §3.1 rows; V12; §8.1 rewritten for the suspended state; §8.2 row; Phase 3 test; `mapping.md` §13 row. |
| L4 | The launch bar (L2) gated nothing mechanical: a release carrying mainnet `START_HEIGHT` with `-yellowbacksignal` defaulting on would have every installing pool signalling at once, and 75 % could lock in before the diversity bar was measured; measuring "share of signalling blocks" needs the signalling the bar precedes. | **Signal off by default on mainnet.** The first mainnet release quotes (tags with bit 0 clear) but does not signal; the bar is measured on **quote tags by `payoutKey`** over a full `SIGNAL_WINDOW`; after the announcement pools set `yellowbacksignal=1`. Provisional bar: **`N ≥ 3` independent pools, no pool above 40 %** of quote-tagged blocks, confirmed in Phase 9. | `-yellowbacksignal` default per network (§4.5); `yed_listminers [height] [window]`; Phase 10 rewritten; §11 rows; §8.1 states the precondition. |
| L5 | On a failed aggregate the quote agent called nothing, so during a crash a pool published a quote up to 30 minutes stale and was out of band by wallet policy. | **Clear after two failed polls.** After 2 consecutive failed aggregates (≈ 60 s) the agent calls `yed_setquote 0`; the node's 30-minute clock stays as the backstop for a dead agent. | §5 agent spec; Phase 7 test; §10.1 row. |
| L6 | After L1 the wallet-default payee choice (FEE-W) reads `N_PENALTY`, `ACCURACY_WINDOW` and the weight formula, which are policy; where do they live? | **Both.** Release-versioned defaults in §3.1, overridable per node (`-yellowbackpayeepenaltyblocks`, `-yellowbackpayeeaccuracywindow`, `-yellowbackpayeetiltbps`). The **judgement** constants (`PEER_*`, `DEVIATION_BPS`, `ACCURACY_BAND_BPS`) stay release-versioned because `Judgements` is shared state in the state hash. | §3.1 marks; FEE-W; §4.5 configuration; `yed_getfeepayee` reports the values it used. |

| # | Finding | Severity | Change |
|---|---|---|---|
| M1 | Totality (K1) was promised but not written down: "lower median" was undefined; every division but `requiredZat` had no rounding rule; `r_k` was signed inside an `arith_uint256` section; `s_0` read a snapshot not yet written; MINT-2's height arithmetic could underflow on regtest; `claimHeight` was not range-checked; RED-4 had no verdict when `pClaim` is undefined; HALT-2/3 had no value when a price is undefined and `Snapshots` had no encoding for "undefined"; `Snapshots[H − 1]` and the initial `Activation` did not exist at `START_HEIGHT`; `feeVout = 0xFF` was rejected only through `feeVout < vout.size()`; a vault-spend scriptSig with fewer than two pushes had no verdict. | **determinism** | §3.7 opens with the arithmetic conventions (`lowerMedian`, floor division, `isqrt`); SIGMA-1 restated; MINT-2 in signed 64-bit with the `claimHeight` bound; §3.8 opens with the totality rule ("undefined ⇒ the rule is false"); RED-4, HALT-2/3, the snapshot encoding of undefined values, the virtual snapshot below `START_HEIGHT`, `feeVout = 0xFF` and the push-count case are each stated. |
| M2 | TAG-1 ("first occurrence") and TAG-5 ("first occurrence is the tag") disagreed with TAG-2 ("an invalid tag is no tag") on whether the scan continues past an invalid first occurrence. | determinism | TAG-5: the first occurrence decides; the scan never continues. `START_HEIGHT ≥ 1` (the genesis coinbase has no height push). |
| M3 | A transaction spending an ACTIVE vault that also carries a MINT or TRANSFER payload had no rule; `unbackedCents` could go negative when a full burn paid the wrong payee. | determinism | Such a transaction is processed by IN-1..3 and RED-1..4 only (§3.8); `unbacked = burned < mintedCents`, `unbackedCents += max(0, …)`. |
| M4 | L1 was decided but not propagated: §1 items 6–7 and (c), V11, §8.1 (the published trust statement: "a registered pool", "lying forfeits fee income"), §9, Phase 6, §10.3, the §8.2 K9 row, Appendix B and the §3.1 table still described registration, penalties and accuracy weighting as rule inputs; the K8/K10/L1 rows pointed at stale identifiers. | consistency | All rewritten; the §3.1 table marks every row **validity**, **state (judgement)** or **wallet default**; `eligible` (membership in `E(tip)`) added beside `registered` in `getblocktemplate.yellowback` and `yed_getinfo.miner`. |
| M5 | Citations: the `ConnectBlock` hook window was cited three ways (V1 `:3187-3193`, §4.1 `:3189-3193`, §4.3 `:3188-3189`/`:3193-3194`) and none was right — `bad-cb-amount` is `:3182-3187`, `control.Wait()` `:3189-3190`, `if (fJustCheck) return true;` `:3194-3195`, so the window is **`:3191-3193`**; V2 still placed the commit "after `:3194`" although K20 moved it after `:3268`; V5 said `getblocktemplate` already emits `coinbaseaux.flags` (it builds it at `:742` and never pushes it, `:504-505`) and that "nothing else reads" `COINBASE_FLAGS` (`miner.cpp:720`, `rpc/mining.cpp:742`, `test_bitcoin.cpp:167` do); `rpc/mining.cpp:733` is `:732`; `ReconsiderBlock`'s mask-clearing lines are `:3979`/`:3995`; `IsFinalTx`/`CheckFinalTx` are `:721-731`/`:746-775`, not `:733-775`; `kernel/chainparams.cpp:174-187` ends at `:188`; the `init.cpp` cites `:1731`/`:1883` are pristine-tree lines, `:1779`/`:1952` in the fork; `MAX_REORG_LENGTH` measures how many of the node's own blocks a reorg would disconnect and the node shuts down, it does not "refuse". | precision | All corrected in place. Every other citation in the plan (≈ 120) was re-read and holds. |
| M6 | Identifiers: `R1`/`R2` used but never defined; `PEER_WINDOW` defined but unread; `payee(R, ·)` used but unnamed; v1's `PRICE-1..3` beside v2's `PRICE-1..2`; `MINTPOL-1` bold-caps outside §3; `VerifyDB L3/L4` colliding with decisions L1–L6; `SIGMA_MULT_MAX`/`SIGMA_REF` vs the table's `_BPS` names; HALT-4 with no test row; two `EvaluateBlock` signatures; `math::DefaultPayee`/`EligiblePayees`/`SupplyCapCents` in one list but not the other; `-yellowbackpreferredpayee`/`-yellowbacktestfault` missing from §4.5; "audit findings B–I" (A10 is cited); ambiguous "v1 D6"/"D2" (decision vs audit row); the §10.1 stale-quote row recorded a non-deviation; "below half" for the 60 % floor; V24's dry run named the wrong predicate; "six weeks" for a 42-hour window; "tagged" where "quote-tagged" was meant; "100 heights below" for a window that includes `R`; `miner.cpp` ≈ 25 vs ≈ 27; "eleven phases"; the one-line summary and §1 ("fails open on any internal error") contradicting V13. | precision | All fixed in place. |
| M7 | Phase sequencing: Phase 3's functional tests need Phase 4's tag emission and `MempoolCheck`; Phases 0–3 could not each build green (Phase 0 deleted `Roster` while `script.h` still took it; Phase 1 changed signatures `state.cpp` still called); Phase 1's exit forbade `src/test/`; Phase 7 had no exit; Phase 7b "parallel to 6–7" depended on a Phase 7 deliverable; Phase 8's hardening items touch `src/wallet/rpcwallet.cpp`, which §4.1, Phase 6's exit and the CI grep set to zero; `-yellowbacktestfault` was used but never delivered; Phase 0's cleanliness grep could never be empty (Sapling `anchor`); deleting `yellowback_fed.py:85-125` removed the RPC client the quote agent needs; `yellowback_util.py`'s v1 helpers had no stated fate; the two `init.cpp` rows were unordered. | **readiness** | Tag emission, `TagScript()`, the two `miner.cpp` tag lines and `MempoolCheck` move to Phase 3; a compile strategy for Phases 0–3 is written (§6 preamble); Phase 1's exit adds `src/test/`; Phase 7 gets an exit; `doc/yellowback-rpc.md` v2 is a Phase 3 deliverable (node context) extended at Phase 6 start, and Phase 7b is gated on it; §4.1 gains a `src/wallet/rpcwallet.cpp` row (wallet tier) and `src/wallet` leaves the CI zero set; `-yellowbacktestfault` is a Phase 3 deliverable; the cleanliness grep is staged by phase (Phase 0: the federation RPC and co-signing names; the anchor symbols join at Phase 2's exit, `roster` at Phase 3's — N26 supersedes revision 4's single grep); `:85-125` moves with the feed layer; a helper-fate table in §6.0; the kill-switch loop is ordered after `SyncToChain`. |
| M8 | RPC contract too thin for Phase 7b to start in parallel: no error identifiers; return shapes of `yed_getactivation`, `yed_listminers`, `yed_gethistory`, `yed_setquote`, `yed_claim`, `yed_listclaimable`, `yed_getblockverdict` unstated; `yed_getfeepayee` returned `feeZat` without a collateral argument; `yed_listtransactions` lacked the `claim`/`unbacked` fields §4.8 displays; `yed_gettag <height\|blockhash>` contradicted "no numeric-or-string argument"; the `rpc/client.cpp` rows were unlisted; "every command but `yed_getinfo` refuses while unhealthy" contradicted the runbook's use of `yed_getblockverdict`. | readiness | §4.5: an error-identifier table, return shapes, `yed_getfeepayee <refHeight> <collateralZat> [selectorHex]`, `yed_listtransactions` fields, `yed_gettag` as a string argument, the `client.cpp` rows, the unhealthy allow-list, and the `rpcversion` bump rule. |
| M9 | §5 under-specified the quote agent (config keys, RPC auth, RPC-failure behaviour, packaging, Python floor, `--once`), the per-carrier pool steps, and the source-mask bits; the devnet paragraph described v2 behaviour but not the changes to the 477-line script, and its block count left node 0 unfunded; the survey was placed in Phase 6 (it is Phase 7). | readiness | §5 rewritten with a spec block, a four-step pool procedure, the bit registry (proposal Appendix A plus Nonkyc = bit 3), and a devnet change list (`up` ≈ 232 blocks). |
| M10 | §7 had no rule→test table; REG-1, TX-0, TPL-3, MINER-2, MINT-7, the MINT-8/RED-3 `feeVout` edges, RED-1's second-vault case, SIGMA-1's undefined-sample cap, MINTPOL-1 per halt and HALT-1 had no named test; fuzz corpora had no location and `YellowbackEvaluate` no input grammar; the v1 `yellowback_fuzz_tests.cpp` corpus bytes were not scheduled for regeneration. | readiness | §7 gains the table and the cases; fuzz spec in Phase 2. |
| M11 | §8.4 items 2, 3, 8, 9, 13, 14, 17, 18, 20 were not mechanically checkable; item 12 / Phase 8 said `GetTime` lives in `policy.cpp` only while §4.2/§4.4 put the clock in `index.cpp` and the RPC. | readiness | Items rewritten as greps, test names or reviewer-signed claims; the clock has one home: the RPC stamps `receivedAt`, `policy::BuildTagScript(now)` takes the time as a parameter, and the grep is "`GetTime` only in `rpc/yellowback.cpp` and `policy.cpp`". |
| M12 | `MAX_REORG_LENGTH` runbook: a `-reindex` with enforcement on re-rejects the same blocks; `-reindex-yellowback`'s effect on `Rejected` was unstated; a release changing a parameter set below an already-validated height would disagree with stored rejections. | precision | Runbook: `-reindex -yellowbackenforce=0`, then re-enable; `-reindex-yellowback` clears `Rejected`; §3.1: a new parameter set starts above every height any released node has validated. |
| M13 | Residuals worth a row rather than a rediscovery: a pool that redeems or claims its own vault can name the collateral output as the fee output and pay no net fee; a claimant chooses `refHeight` among 40 heights and so the lowest `pClaim` of the last 40; MINT-4 reads halts at `R` while ACT-5 reads `H − 1`; `MempoolCheck` cannot see unconfirmed YED parents; `nExpiryHeight` is wallet convenience, not a rule; LOCKED_IN followed by a collapse never enforces until 75 % returns. | fidelity | §8.2 rows; notes beside V11, K16 and MP-1; test cases. |
| M14 | Phase 9's calibration and Phase 10's launch bar had no acceptance rule, no measuring tool, no lead time for `START_HEIGHT`, and "independent pool" was undefined. | readiness | Phase 9: the multiplier must sit in `[1×, 1.5×]` at realised volatility over the soak, else `SIGMA_REF_BPS` is re-set; Phase 10 per L4 with `yed_listminers … 2016` as the tool and "distinct operators, attested by the pool's public identity" as the definition; `START_HEIGHT` at least two weeks of blocks past the release date. |
| M15 | §3 said "as v1" for IN-1..3, XFER-1..3, the codec rules, the TRANSFER template and §3.10, while Phase 0 replaces the v1 spec with §3 — leaving Phase 2 with no text for them. §12 Q4 proposed a dormant fee-split parameter no rule reads, against K10. | readiness | The five rule texts are inlined in §3; Q4 records "no parameter until a rule exists". |

Everything else in revision 3 survived. The four decisions are the only changes to what the
protocol *does*; M1–M15 change what the document *says*.

### Revision 5 (2026-09-10) — four audits of revision 4; four decisions by the product owner

Revision 4 was audited by four independent passes: test suites, regtest setup and acceptance
criteria (41 findings: every rule crossed with unit / functional / adversarial / reorg coverage,
every phase exit, the CI job list, the testnet drills, the fuzz harness, the state hash); fidelity
of the text inlined from the archived documents (23: every inlined passage and its ≈ 120 citations
re-read); a security review from the standpoint of a risk-averse Ycash maintainer (29: nodes
without the flag, partitioning of enforcing nodes, cheap orphaning, acceptance of a rule-breaking
spend, DoS of an enforcer, the shielded pool, the trust statement, the kill switch, what the
maintainers are asked); and developer followability (63: could one developer execute each
checkbox with what the plan says — signatures, commands, framework details, per-phase
run-throughs). The product owner then decided the four questions the security review raised.
Decisions first, then findings.

| # | Question | Decision (product owner, 2026-09-10) | Change |
|---|---|---|---|
| L7 | ACT-6 reads `signalCount` from the enforcer's *own* chain. After enforcers reject a stock block and mine on, their branch is mined only by enforcers, its trailing window converges to 100 % signalling and enforcement never suspends there; so a signal share that drifts below half (a pool leaves, upgrades to a stock release, goes unhealthy — the window lags hashpower by up to 42 h) followed by one cheap vault spend mined by the stock majority splits the chain permanently, and a forged signal majority (any coinbase can carry the bit, TAG-3) can arrange the same on purpose. K2's "never left alone on a minority chain" was overstated. | **Work valve (ACT-7).** When a chain rooted at a block this node rejected (its hash in `Rejected`) has at least `VALVE_BLOCKS = 6` blocks more work than the node's tip — the condition `CheckForkWarningConditions` computes with `pindexBestInvalid` (`ref/ycash/src/main.cpp:2197`) — the node clears enforcement for the session (`enforcing = false`, reason `valve-tripped`), runs the V13 `ReconsiderBlock` loop at runtime under `cs_main` for every hash in `Rejected`, lets the normal download path (`ProcessNewBlock → ActivateBestChain`) reorganise onto the heavier chain, drops the signal bit (MINER-1), logs and alerts (`-alertnotify`, `getinfo.errors`, `yed_getinfo.valveTripped = true`), and re-arms only by operator restart. Enforcement therefore means "majority in fact". Regtest `VALVE_BLOCKS = 6` too. | §3.1 row; §3.9 ACT-7; V12, V13; §4.3 — the measurement is stated exactly: `pindexBestInvalid` lives in `main.cpp`'s anonymous namespace (`:139-285`, declared `:202`) and cannot grow from headers the node refuses, so the N1 `AcceptBlockHeader` clause is the valve's odometer; §4.5 `valveTripped`/`unhealthyReason`; §4.7 runbook; §8.1/§8.2 rewritten ("…for more than 6 blocks"); Phase 5 case 9; rc1 step 6b; drill D12. |
| L8 | Parameter versioning had no mechanism for stale enforcers: a pool still on an old release keeps enforcing the old set past a new set's start height and splits from upgraded enforcers on the first transaction where the sets disagree; a Ycash network upgrade the fork lags collapses the enforcing set on one flag day. | **Enforcement sunset.** Every release carries `ENFORCE_UNTIL_HEIGHT` per network in its parameter set: about 12 months of blocks (420,480) past the set's start height and never beyond the next known Ycash network-upgrade activation height. Past it the node stops rejecting (ACT-5 gains `H ≤ ENFORCE_UNTIL_HEIGHT`), keeps tagging and evaluating, drops the signal bit, logs "upgrade required" and sets `yed_getinfo.sunset = true`. A parameter change ships as a release whose set starts at or after the previous set's sunset (the "above every validated height" constraint of M12 stays as well). Regtest: `-yellowbackenforceuntil` (regtest-only flag, default 0 = none). | §3.1 row and versioning paragraph; ACT-5; MINER-1; §4.5; §4.7; §8.2 rows ("two enforcing releases with different parameter sets", "Ycash network upgrade"); §9; §11 ("fork release within 14 days of every Ycash release, tracked on `feature/yellowback-sf`"); Phase 3 case `act5_past_sunset_accepts`; drill D13. |
| L9 | Price medians are majorities of *quote tags*, not of hashpower: with the windows at 50 % fill a pool with 26 % of blocks holds more than half of the quote tags and sets all three medians once they roll (2 h / 12 h / 42 h); lowering `pClaim` for 42 h makes healthy vaults claimable by the attacker with YED it minted. §8.1's "sustained hashpower over hours to days" overstated the cost. | **Per-window minimum fill.** `WINDOW_MIN_FILL` is `⌈W/2⌉` for the fast window and `⌈2W/3⌉` for the mid and slow windows (the `pClaim` inputs). Consequence, stated and accepted: `pMint = min` needs all three medians defined, so a mint also needs two-thirds fill on the mid and slow windows. | §3.1 row; PRICE-1; V16; §8.1 wording ("a majority of quote-tagged blocks, which is a majority of hashpower only when most blocks carry quotes"); §8.2 row with the arithmetic (26 % of blocks at 50 % fill; 34 % at two-thirds fill for `pClaim`); `yellowback_pricefeed.py` case `price1_quote_majority_needs_fill`; drill D14. |
| L10 | If the module is abandoned every vault's claim path is anyone-can-spend at `claimHeight` and miners sweep every unswept vault; owners must sweep first, but `yed_redeem` refuses to build anything `MempoolCheck` rejects (V24) and an owner who sold the YED had no wallet path to recover collateral; §8.1's "existing YED always remains redeemable by its minters" held only for a minter still holding the YED. | **Owner sweep.** New wallet RPC `yed_sweep <vaultTxid> <"I understand this leaves YED unbacked"> [to]`: owner-path spend, no burn, no fee output. Builds only under **abandonment**, computed from state every node shares: `Snapshots[tip].haltMask.ENFORCEMENT` has been set continuously for ≥ `ABANDON_BLOCKS = 2 · SIGNAL_WINDOW` (4,032; regtest 128), or the tip is past `ENFORCE_UNTIL_HEIGHT` of every parameter set the release knows and no successor set is active. Never gated on the node's own `-yellowbackenforce`. Refused by MP-1 and TPL-1 while enforcement is on (it fails RED-1; nothing new). Records the vault `CLOSED, unbacked = true`; `yed_listtransactions.type = "sweep"`; `yed_getvault.sweepBefore` (= `claimHeight`) on ACTIVE vaults whenever abandonment holds. Errors `sweep-not-abandoned`, `sweep-acknowledgement-missing`. | §3.1 row; §3.5 SWEEP template; §4.5 (RPC, errors); §4.6 abandonment paragraph; §4.8; §8.1 abandonment paragraph; §8.2 row; Phase 6 deliverable; Phase 5/6 cases `sweep_*`; rc1 step 8b; Appendix B. |

| # | Finding | Severity | Change |
|---|---|---|---|
| N1 | **Peer ban on descendants.** "Never bans a peer" covered only the rejected block: once block B is `BLOCK_FAILED_VALID`, every later header or block on the stock chain hits `AcceptBlockHeader`'s `bad-prevblk` at DoS 100 (`main.cpp:4557-4558`) — or, for a block whose refused parent is not in `mapBlockIndex`, "prev block not found" at DoS 10 (`:4555`) — and both the `headers` (`:6604-6610`) and `block` (`:6651-6658`) handlers call `Misbehaving` with it, so an enforcing node banned every stock peer within one block of a rejection. | **safety** | BLK-2 gains the descendant clause; §4.3 row: one `main.cpp` clause at `:4553`, *before* both stock returns, answering `state.DoS(0, …, REJECT_INVALID, "bad-prevblk-yellowback")` for a header whose parent is a Yellowback-rejected block or a header already noted as descending from one (`IsRejectedAncestor` walks `pprev` to the first `BLOCK_FAILED_VALID`, not `_CHILD`, ancestor and checks `Rejected`); the same clause feeds the valve's odometer (L7). V1; §4.1 budget (≈ 29, breakdown summing); §8.2 row; §8.3; §8.4 item 4; Phase 5 case 1 extended (node 1 mines two more blocks on the rejected one and relays; `banscore == 0` on every connection of nodes 0, 2–4; node 1 still a peer). |
| N2 | **IBD and `-reindex` stranding.** A fresh enforcing node syncing from genesis re-evaluates a historically accepted rule-breaking block, rejects it and can never join; M12's runbook covered existing operators only. | **safety** | BLK-2: no rejection while `IsInitialBlockDownload()` (`main.cpp:2106`, latches false once caught up) is true or under `-reindex`/`fImporting`; evaluation and `CommitConnect` still run (the index is rebuilt), only the reject is suppressed. Plain `-reindex` is therefore safe and the M12 runbook step becomes `-reindex` (`-yellowbackenforce=0` kept as belt-and-braces). V13, §4.3, §4.7; §8.2 row; `yellowback_index.py` case `ibd_across_accepted_invalid`. |
| N3 | **Reusable ACTIVE-vault griefing of stock miners** (K3 fixed the VOID case only): an attacker mints the smallest class-A vault, waits for `lockHeight`, and broadcasts an owner-path spend without a burn to stock nodes only; every stock pool that includes it has its block orphaned, the transaction stays valid at the base layer and is included again next block, and the attacker's vault is never closed on the enforcing chain, so the same vault works forever at zero marginal cost. | **safety (accepted, documented)** | §8.2 row (cost = minimum collateral locked once; outcome: a stock pool's blocks are orphaned until it runs the module in filter-only mode, `-yellowbackenforce=0`, TPL-1); §8.1: "as with any soft fork, every pool — participating or not — should run the module at least in filter-only mode"; Phase 10 outreach reaches every pool with filter-only as the zero-risk option; `--extended` asserts node 1's surviving block count and a ban count of 0. |
| N4 | **False signalling.** "The signal bit counts only enforcing nodes" and "`signalCount` under-counts" were false against an adversary: any coinbase may carry `YED!` with bit 0 (TAG-3), so 30 % honest enforcers plus 25 % false signallers reach the 50 % floor while the 45 % majority in fact mines the stock chain. | **safety** | V12 and §8.2 reworded ("the count is self-reported and can be inflated by anyone; it under-counts only among honest pools; the work valve is the mechanical backstop"); Phase 3 case `act_forged_signal_tags` (node 1 forges signal tags; activation occurs; after node 1 mines a rule-breaking block with majority share the valve trips, Phase 5 case 9). |
| N5 | **Mempool not re-evaluated after a tip change.** A vault spend admitted at tip `T` can become BLK-1-invalid when the `refHeight` window slides, enforcement flips or a reorg changes `Snapshots[refHeight]`; TPL-1 skips it but the node still *relays* it (feeding N3). `DisconnectTip` resurrects through `AcceptToMemoryPool` (MP-1 runs), `ConnectTip` does not (`removeForReorg`, `main.cpp:3854`, checks finality only). | **safety** | MP-1 and TPL-2 strict additionally require, for a vault spend, `nExpiryHeight ≠ 0 ∧ nExpiryHeight ≤ refHeight + REF_WINDOW`, so it expires from every mempool (stock nodes enforce expiry) before RED-1's window closes; `ConnectTip` removes vault spends whose `MempoolCheck` now fails (§4.3 row after `removeExpired`, `:3636`). `yellowback_mining.py` cases `mp1_expiry_required`, `mp1_reorg_reevaluates_mempool`. |
| N6 | **`MempoolCheck` cost** was unstated: if the pseudo-block path computed a SNAP per transaction an attacker would buy milliseconds of CPU per ordinary-fee transaction on every enforcing node. | DoS | MP-1: `MempoolCheck` returns true in `O(inputs)` `Vaults` lookups when no input is an ACTIVE vault and never computes a SNAP (the tag at `H` never affects rules at `H`); benchmark unit test `mempoolcheck_bench` (10,000 plain transactions < 1 s; a 2 MB `OP_RETURN` block through `EvaluateBlock` < 200 ms). |
| N7 | **`TxLog` growth attacker-controlled**: every payload-carrying transaction got an entry (≈ 1 GB/day of index for ordinary fees; `-prune` is refused). | DoS | §3.8: `TxLog` entries only for transactions that create or spend `Tokens`/`Vaults` (a payload with a non-Yellowback verdict gets none); Phase 8 DoS-review row. |
| N8 | **Crash between the `Rejected` write and the block-index flush**: `BLOCK_FAILED_VALID` is flushed lazily, `Rejected` was written without `sync`; after a power loss the mark could exist with no `Rejected` entry and the kill switch could not un-reject. | precision | `Rejected` is written with `sync = true` (BLK-2); Phase 3 case `rejected_survives_kill9` (`kill -9` right after a rejection, restart with enforcement off, the reorg happens). |
| N9 | `CheckConnect`'s verdict cache was keyed on `blockHash` only; a rebuilt index with different regtest overrides between check and commit would reuse a stale verdict. | precision | Cache keyed on `(blockHash, indexTipHash, paramsHash)` (§4.3). |
| N10 | **`getblocktemplate` shape changed for stock-config nodes**: `coinbaseaux.flags` and `"coinbase/append"` were emitted unconditionally, contradicting "a node without the flag runs v4.5.0 code paths"; §1 said "byte-for-byte v4.5.0" of a binary that also carries the `+ COINBASE_FLAGS` append and the K17 lock; nothing tested the fork-without-flag against `ref/ycash`. | precision / test gap | The three `rpc/mining.cpp` edits are gated on `g_yellowback` (V26, §4.3, §4.4); §1 (a) and §4.1 reworded (every *behaviour-changing* statement guarded; the unguarded remainder listed in §8.4 item 2); `qa/rpc-tests/yellowback_stockparity.py` (nightly) diffs `ref/ycash` v4.5.0 and the fork without the flag over one scripted scenario; §8.4 item 21. |
| N11 | `CheckForkWarningConditions` fires after any rejection once the stock chain is 6 blocks ahead ("invalid chain at least ~6 blocks longer … corruption likely" via `-alertnotify`/`getinfo.errors`); operators were not told. | runbook | §4.7: expected after a rejection; with L7 it is the valve's trip signal. |
| N12 | `yed_getblockverdict` on an arbitrary historic block needs the state at its parent, which the index cannot produce without an undo replay; §4.5 did not say. | precision | Refuses unless the block's parent is the index tip, or the block is in `Rejected` with the current tip as parent (§4.5). |
| N13 | **The ask of the Ycash maintainers was under-specified** and not answerable with a yes: what they are asked, the exact bounded claims, what they are not asked, the honest facts, the upstream-release commitment. The shielded-pool evidence (the `ConnectBlock` failure path discards `view` before any flush; TX-0 ignores shielded components; `DisconnectBlock`'s undo runs after the coins rollback; the 35-line `transaction_builder` extension is additive) was scattered. | readiness | New §8.5 "Statement requested from the Ycash maintainers"; §8.4 item 22 (existing `transaction_builder` tests unchanged and green; the three new builder methods called only from `src/yellowback/`, grep). |
| N14 | **Reorg-flipped honest spends** (`refHeight` names a height, not a hash: a wallet-built spend valid at build time can fail RED-3/RED-4 after a reorg deeper than `REF_LAG` and a stock miner including it has an honest block orphaned) and **reorg across activation** (vaults minted on a branch whose activation is reorged away become VOID, hence a sweep race) had no row and no test. | precision | §8.2 rows; `yellowback_activation.py` cases `act2_reorg_across_lockin`, `act3_reorg_across_activateheight`; `yellowback_reorg_stress.py` records how often a wallet-built spend becomes invalid. |
| N15 | `MAX_REORG_LENGTH` was misdescribed as bounding "the node's *own* blocks" and §8.2 still said the node "refuses" the reorg (M5 not propagated to that row). | precision | V13 and §8.2: it is `pindexOldTip->nHeight − pindexFork->nHeight` — the active chain to disconnect, whoever mined it — and the node shuts itself down (`main.cpp:3770-3789`); runbook `-reindex` (N2); with the valve the case is unreachable in ordinary operation. |
| N16 | §8.1 overstated ("sustained hashpower over hours to days"; "a majority that does not could release collateral" where a *minority in fact* can when the window says otherwise; "nothing any pool does can create YED" where a quote-tag majority mints against inflated prices) and omitted the stock-miner cost, the peer-ban behaviour and the abandonment outcome; §8.2 lacked the rows for N1–N5, N14, L7–L10; §8.3 said mempool acceptance is "otherwise v4.5.0's" beside MP-1. | wording | §8.1 rewritten; §8.2 rows added and corrected; §8.3 reworded. |
| N17 | **Upstream network upgrades**: a Ycash upgrade changes the branch ID; a pool on a stale fork drops off, a pool that moves to stock loses enforcement; the plan asked nothing of anyone. | safety | §11 row: fork release within 14 days of every Ycash release, tracked on `feature/yellowback-sf`; the sunset never beyond the next known upgrade height (L8); §8.2 row. |
| N18 | **State-hash preimage unspecified** (which tables, field order, the encoding of `Activation`, the regtest flags "included in the preimage" without saying how, `Rejected` node-local yet not stated as excluded although §6.0 asserts hash equality between node 0 and the pools; new tables had no key prefixes), so a re-implementation could not reproduce the hash and M13's "mismatched test nodes fail loudly" was untestable. | **determinism** | §3.6 *State hash*: `SHA256` over the canonical serialisation of `Tip, Tags, Judgements, Activation, Vaults, Tokens, Totals, Snapshots` sorted by key plus the params record `{startHeight, sigmaRefBps, supplyCapBps, enforceUntil}`; `TxLog`, `Rejected` and `Undo` excluded; key prefixes listed; unit `statehash_golden_vector` with a pinned hex; the Python model recomputes it. |
| N19 | IN-3 lost v1's clarification for a MINT carrying YED inputs: under the literal text `burned = yedIn − yedOut` with `yedOut = cents` a MINT with `yedIn = 500` and `cents = 10,000` burns `−9,500` and *adds* supply. | **determinism** | IN-3: for a MINT `yedOut` in the burn formula is `0` (every YED input of a MINT is burned; `supplyCents += cents` is applied separately when MINT-1..8 hold). |
| N20 | Verdict strings: "keep the prototype's for MINT/XFER" could not be done (they are tier/ERR/volatility-shaped) and the additions mixed two styles; the wallet fork matches these strings. | determinism | Rule → verdict table in §4.2a; Phase 2 points at it. |
| N21 | §3.6 omitted `VaultRecord.voidReason` (§4.5/§4.8 "VOID rows explain the verdict" need it) and `TxLogRecord.spentTokens` (the wallet's `yed_listtransactions` filters on it) — two implementers would serialise different records; §4.2 omitted deletions/renames in `params`, `script`, `view`, `index`, `policy`, `txbuilder`. | determinism / readiness | §3.6 records completed; §4.2 rows completed (`PRICE_MAX_AGE`, `HEALTH_CAP`, `VOL_*`, `RED_SKEW`, `NUM_TIERS`, `IsValidTier`, `SortKeys`, `VaultScriptSize`, the `P<height>` price table, `Volatility`, `IsSynced`, `TestChainTip`, `SignerBranchId`/`VerifyAllInputs` to `txbuilder`, `BuiltTx` renames). |
| N22 | `issuedZat(H)` needs `GetBlockSubsidy`, defined in `main.cpp` (`libbitcoin_server`), while `math.h`/`state.cpp` are placed in `libbitcoin_common` — a layering inversion that also broke §3.10's "callable from a unit test with an in-memory view". | readiness | `EvaluateBlock` takes the block's subsidy as an argument (`CAmount subsidyZat`) computed by the caller in `index.cpp`; `math.h` drops `IssuedZat`; the seed loop lives in `index.cpp` (§4.2, Phase 2, Phase 8). |
| N23 | No **cross-implementation** check of §3.7 ("two implementations produce bit-identical state" was asserted, not tested); CI runs Linux only while the wallet builds on macOS. | determinism | `qa/rpc-tests/test_framework/yellowback_model.py` (pure-Python model of the snapshot arithmetic fed from `yed_gettag`; `assert_model_matches(node)` compares every `yed_gethistory` field for every height; run at the end of `yellowback_activation.py`, `yellowback_pricefeed.py` and the rc1 run-through); the golden vector runs in the macOS wallet job (§7). |
| N24 | **No build, run or fuzz commands** anywhere in the plan (the prototype's `doc/yellowback.md:123-151` has the host conditions and Phase 0 rewrites that file); no single-script invocation; no `ycash-cli` rebuild rule; the Python signer aborts on the developer's Mac (`key.py` loads `libcrypto` through ctypes; exit 134) without `DYLD_LIBRARY_PATH`. | **readiness** | §6.0 item 0 "Commands" (build recipe, unit run, one functional script, `ycash-cli` rule, devnet via the venv, fuzz build/run, the macOS variable); Phase 0 keeps and extends the "Build and test baseline" section of `doc/yellowback.md`. |
| N25 | Interfaces named but not typed: `math.h`, `tag.h`, `EvaluateBlock`/`ApplyBlock`, `EligiblePayees`/`DefaultPayee`, the three hook methods (no return types, lock preconditions or empty-index behaviour), `-yellowbacktestfault` semantics, the `MempoolCheck` pseudo-block (a one-transaction block would parse the vault spend as a coinbase), the "overlay-view helper" of §4.1 that §4.3 never used, "includes and a forward declaration" (the hook call needs the full class), `FilterTemplate` (the "tag applied to the overlay first" clause described a coinbase that does not exist during selection), `txbuilder` signatures, `TagScript` colliding with `policy::TagScript`. | readiness | §4.2a signature blocks; §4.3 rows rewritten with preconditions; the helper row deleted (budget recomputed); `#include "yellowback/index.h"`; `TagPush`; the lock-order decision `cs_main → cs_wallet → mempool.cs → cs_yellowback` with `TemplateView()` as an RAII holder of `cs_yellowback` and a Phase 8 grep that no RPC takes `mempool.cs` after it; `-yellowbacktestfault=storage:<check\|commit\|undo>[:<height>]\|template`. |
| N26 | **Phase ordering**: the Phase 0 grep forced `AnchorRecord`/`GetAnchor` out of `view.h`/`state.cpp` two phases before they migrate; the Phase 1 `roster` grep could not be empty (`ParamsFromArgs` parses it until Phase 3); from Phase 2 to Phase 6 the four wallet-flow scripts fail (the wallet builds v1 transactions) yet stayed in CI; Phases 3 and 5 needed `yed_mint` (Phase 6) to create a vault; the CI workflow's `on:` still named `feature/digidollar` and its nightly job had no `schedule:`; Phase 7b "parallel to 6–7" depended on a Phase 6 deliverable for half its screens; `TemplateInfo()` had no delivering phase; Phase 8 duplicated Phase 0's `tag.cpp` grep. | **readiness** | Phase 0/1/2/3 greps rewritten and ordered; Phase 2 removes the four wallet-flow scripts from CI (recorded in `doc/yellowback.md`), Phase 6 returns them; Phase 3 and 5 use raw builders only (`build_mint_tx` v2 signature stated); Phase 0 CI edits listed; Phase 7b split into 7b-a (node-context screens, after Phase 3) and 7b-b (mint/send/redeem/claim/sweep, after Phase 6's first commit); `TemplateInfo()` in Phase 4; the duplicate grep dropped. |
| N27 | **RPC contract still too thin for the wallet**: `yed_getprice`, `yed_getvault`, `yed_gettxinfo`, `yed_validaterawtransaction`, `yed_estimatecollateral`, `yed_getinfo`, `yed_getstats`, `yed_listpositions`, `yed_listtransactions` had no field lists; `yed_getinfo.params` lacked the class table the Mint page derives from; the change-floor and bad-address errors had no identifiers; the `client.cpp` list omitted rows the prototype keeps; the wallet's `RPC_VERSION = 2` was scheduled in Phase 0 although the node reports `rpcversion 1` until Phase 3 and the wallet refuses a mismatch; H10's `yed_getinfo` fields were dropped from §4.5. | readiness | §4.5 complete field lists; `change-floor`, `not-a-yellowback-address`; `client.cpp` rows completed with the `ycash-cli` rebuild rule; the wallet bump moves to Phase 7b-a's first commit; `doc/yellowback-rpc.md` v2 is written before the RPC code and is the contract. |
| N28 | **Framework gaps**: pool nodes need a payout address before they start (the fixture never said how); the inherited chain topology never delivers node 1's block to node 5 (case 1 "node 5 follows node 1" was impossible); `split_network` restarts every node; `activate()`'s block count was "two windows" (it is 129); `yellowback_util.py`'s constants are v1; `build_vault_spend_raw` needs a WIF decoder the framework lacks; `kill -9`, `verifychain 4 20`, the crash case and the fault-flag names were "adapted" but new; claim.py's price crash needs ≥ 33 low quotes of 64 and trips HALT-3 meanwhile; FEE-W statistics had no sample size or tolerance; Python-built blocks need `CBlock.solve()`; `yellowback_quote.py` must write a TOML per pool; the Phase 7b QTest must `QSKIP` without a devnet. | readiness | §6.0 item 4 rewritten (fixed regtest WIFs via `importprivkey`; star topology on node 1 with `disconnectnode` splits; `activate()` = 129 blocks; v2 constants; `wif_to_secret()`; the helper list incl. `checkpoint`, `assert_model_matches`, `kill9`, `snapshot_ledger`; `EXTENDED_SCRIPTS` registration); per-phase run-throughs; the Phase 6/7/7b notes. |
| N29 | "§3 published verbatim as the spec, regenerated from this plan" named no tool; a manual copy drifts every revision. | readiness | `scripts/extract-spec.sh` + `make spec`; `make status` fails when the copy is stale (Phase 0, §3 preamble). |
| N30 | **Rule × test matrix** had empty cells: no reorg case for activation, the eligible-payee set, the `refHeight` window or the mempool; no adversarial case for TAG-4 (garbage coinbases), TAG-3, SIGMA-1 (one pool cannot inflate), FEE-1 edges, HALT-2 at the exact threshold, HALT-3's second disjunct, TPL-2's non-wallet selector, MINER-2's defaults, the virtual snapshot, the undefined-value encoding, parameter versioning, the kill-switch edge cases (fresh datadir; a `Rejected` hash not in `mapBlockIndex`), BLK-3 across a reorg, `MAX_REORG_LENGTH`; the IN/XFER/MINT cases were not named so the rule → test grep could not find them. | **test gap** | §7 lists every case by name; Phases 2–6 carry them; the M10 identifiers are found through the comment-tag convention (N36). |
| N31 | **Every phase exit was prose**; only Phase 7 had a run-through; no rc1 regtest run-through existed for the release manager. | **test gap** | Per-phase "Acceptance" blocks with exact commands whose exit code decides, each ending "the block above exits 0 on CI jobs `main` + `audit`"; `qa/rpc-tests/yellowback_rc1.py` with its step table (incl. the valve and sweep steps) and a state-hash ledger pasted into the tag message (Phase 8). |
| N32 | **CI**: the prototype's nightly job has `if: github.event_name == 'schedule'` and no `schedule:` trigger (it has never run); the CI paragraph omitted five greps §8.4 relies on; no CI for `yecwallet-dd`; the functional list still named `yellowback_federation yellowback_protection`; `test_yellowback_fed.py` would fail between Phases 0 and 7; the plan described two workflows where one exists. | **test gap** | §6.0 item 6: one workflow, six jobs (`main`, `audit`, `python`, `wallet`, `nightly`, `weekly-fuzz`) with triggers, steps and the schedule fix; Phase 0 CI edits. |
| N33 | Phase 9 drills were a comma list with one shared check — no procedure, pass criterion, duration or evidence. | test gap | Phase 9 drill table D1–D14 (incl. the L7/L8/L9 drills), minimum durations, evidence artefacts, `doc/yellowback-testnet-report.md`. |
| N34 | **Fuzzing**: no target was ever compiled in CI (`fuzz.cpp` rots silently); the corpus generator was not in-tree; `YellowbackEvaluate` had no bounds, fixed params, height range or property assertions; no `YellowbackPayee`; found crashes were not replayed. | test gap | §7 fuzz section: `src/test/gen_yellowback_corpus.py`, grammar bounds, the four property assertions, `YellowbackPayee`, `crashes/` replay, nightly fuzz smoke, the weekly job; Phase 1/2 exits. |
| N35 | §8.1/§8.2 safety properties without a scripted scenario: the stock node unaffected (only a unit test), no-partition on suspension (no explicit assertion), the crash case not guaranteeing an unflushed chainstate, parameter versioning, state-hash equality only at test end, the `MAX_REORG_LENGTH` runbook. | test gap | `yellowback_stock_node.py`; the no-partition assertion in `yellowback_activation.py`; `SIGKILL` right after `generate(30)` with the `SyncToChain: undoing` log grep and the `UNDO_KEEP + 10` variant; `params_selected_by_height` / `params_mismatch_fails_loudly`; `checkpoint(label)` after every mined block in enforcement.py and claim.py; nightly `yellowback_runbook.py`. |
| N36 | `BOOST_AUTO_TEST_CASE` names cannot contain `-`, so "every rule identifier appears verbatim in the name of a test case" was impossible for hyphenated identifiers. | precision | Comment-tag convention: a `// Rule: RED-1` line on the case; the grep is `^// Rule: .*RED-1` over `src/test/yellowback_*.cpp` and `# Rule:` docstrings in `qa/rpc-tests/yellowback_*.py` (§7, §8.4 item 9, Phase 2). |
| N37 | §8.4 items 2, 3, 8, 9, 13, 17, 18, 20 were still not fully mechanical (item 13 also required vault outputs to be locked, contradicting §4.6). | readiness | Items rewritten as commands or named tests; item 13 corrected; new items 21 (stock parity) and 22 (`transaction_builder` grep). |
| N38 | Smaller test notes: TPL-3's fault flag must take the hook name; the crash and `verifychain` cases are new work, not "adapted"; `--extended` should also assert `Rejected == injected spends` and node 5's `unbackedCents > 0`; the claim test needs a stated mock-price schedule; the QTest "against the devnet" cannot run offscreen in CI; the FEE-W functional statistic needs a tolerance; the unhealthy-index route in `yellowback_mining.py` is the fault flag. | precision | All applied in Phases 3–7b. |
| N39 | **Fidelity of the inlined text (23 findings)**: V13 vs §4.5 on the unhealthy allow-list (M8 not propagated); §8.2's `MAX_REORG_LENGTH` row (M5 not propagated); IN-3 (N19); §8.4 item 13 vs §4.6 on vault locks; `miner.cpp` "≈ 27" vs a breakdown of 25; M7's grep vs Phase 0's; §4.7's `yellowbacksignal=1 # default` on mainnet; the `REF_LAG ≤ 36` bound justified by MINT-2 alone (it proves ≤ 39; the real source is `TX_EXPIRING_SOON_THRESHOLD`, `main.h:81`); the init-row ordering (the notifier thread starts at `:1844`, before `ThreadImport` at `:1883`); the `init.cpp:1731` cite on a blank line (`:1730`); XFER-3's merged sentences; `yed_claim` missing from the change-floor lists; the expired-transaction display without a test; "all behind `if (g_yellowback)`" in §1/§4.1 vs §8.4 item 2; bare prototype rule-set names `RED-0..8`/`PRICE-1..3`; `mapping.md:500` still `:174-187`; `/cosign` between two RPC names in §10.2; the `ys1…` REDEEM vout indexes that shift without change; the `Makefile.am` cite order; §4.8 dropping K3's `sweepBefore`; §5 omitting `min_btc_sources`/`outlier_bps`; H1 extended to `yed_claim` without a note; H10's `yed_getinfo` fields dropped. | wording | All fixed in place. |

Everything else in revision 4 survived. L7–L10 and N1, N2, N5–N9, N19 are the changes to what the
protocol or the node *does*; the rest change what the document *says* and what the tests prove.

### Revision 6 (2026-09-10) — one audit of revision 5; four adjustments applied pending confirmation

Revision 5 was audited once more, in one pass with three questions: does the valve and
abandonment machinery of L7–L10 behave as claimed against the pinned tree (every mechanism
re-read in `ref/ycash/src/main.cpp`: `IsInitialBlockDownload`, `AcceptBlockHeader`,
`FindMostWorkChain`, `CheckForkWarningConditions`, `ReconsiderBlock`, `AcceptToMemoryPool`'s lock
scope, the warning plumbing); can a developer execute every wallet path the plan promises
(mint, send, redeem, claim, sweep, and the release of a VOID vault); and is every gate the plan
calls "mechanical" actually a command that a CI job in the fork's own repository can run. The
audit found four places where the protocol or the node must change, applied them in the text as
**L11–L14** so that the plan is complete now, and lists them here for the product owner to
confirm or reverse; the rest are readiness, precision and test findings, applied in place.

| # | Question | Adjustment applied (product owner to confirm) | Change |
|---|---|---|---|
| L11 | **Catch-up rejections.** `IsInitialBlockDownload` in Ycash 4.5 tests only the tip's *age* (`nMaxTipAge`, 24 h, `ref/ycash/src/main.cpp:2174`, plus `nMinimumChainWork` and the upgrade-hash checks `:2130-2170`); there is no "blocks behind the best header" test, and the latch (`:2107-2112`) is a `static` reset only by restart. So a node that fell behind by less than a day — a partition, a restart after two hours offline, every regtest node — evaluates the network's blocks on catch-up outside IBD, **rejects** a rule-breaking block the network accepted hours ago, and splits; the valve's odometer cannot help at once because descendants indexed before the rejection are marked `BLOCK_FAILED_CHILD` by `FindMostWorkChain` (`:3712-3722`) and never pass the N1 clause, so the trip waits for the *next* new header. The revision-5 case `ibd_across_accepted_invalid` could not pass as written on regtest, where every block is recent. | **Catch-up suppression (BLK-2, clause 3).** `CheckConnect` does not reject a block when the best known header (`pindexBestHeader`, `main.h:209`) descends from it and already carries `VALVE_BLOCKS` of work above the node's tip — the network has demonstrably built on it — and instead accepts it, logs `catch-up: accepted rule-breaking block … (network N blocks ahead)`, counts it in `yed_getinfo.suppressedBlocks` and leaves enforcement state untouched (no trip, no restart needed). A rejection still happens when the network is fewer than six blocks ahead; the odometer then reads the real `nChainWork` of a `FAILED_CHILD` parent at the next header (`IsRejectedAncestor` walks through `_CHILD` marks) and trips within one block. | §3.9 BLK-2/ACT-7; §4.2a; §4.3; §4.5 `suppressedBlocks`; §4.7; §8.1; §8.2 row; unit `catchup_suppresses_reject`; `yellowback_enforcement.py` case 15 `valve_catchup_offline_node`; `ibd_across_accepted_invalid` restated; `mapping.md` §13 row. |
| L12 | **Abandonment must be a chain property.** L10's second clause ("the tip is past `ENFORCE_UNTIL_HEIGHT` of every parameter set *this release* knows and no successor set is active") is release-relative: a node on a stale release declares abandonment the block after its own sunset while upgraded pools, carrying the successor set, still enforce — and refuse its sweeps (RED-1). Two nodes on the same chain would answer `yed_getinfo.abandoned` differently, against §4.6's own rule. | **One clause.** Abandonment is exactly "`Snapshots[tip].haltMask.ENFORCEMENT` set continuously for `ABANDON_BLOCKS`". The signal bit is release-independent (any tag carries it), so this is the same answer on every node of every release. A sunset with no successor makes every honest signal bit vanish (MINER-1), `ENFORCEMENT` sets within a window, and abandonment follows 4,032 blocks later — the sunset case is covered without a clause of its own. | §3.1 row; §4.6; §8.1; Appendix B; `sweep_builds_past_sunset` replaced by `sunset_alone_is_not_abandonment` and `sweep_after_sunset_without_successor`. |
| L13 | **A sweep cannot leave its own node.** MP-1 applies "irrespective of ACT-5", so the owner's own `-yellowback` node refuses the SWEEP at `AcceptToMemoryPool` (it fails RED-1 by design), `CommitTransaction` records it and it is never relayed — the K7 stranding, reintroduced by L10 — and no pool that still runs the module, even filter-only, ever mines it. | **MP-1 and TPL-1/2 do not apply while `IsAbandoned()` holds** (the shared predicate of L12, never the node's own flag); under abandonment a vault spend is an ordinary transaction to every node that runs this release. `yed_sweep` also returns the raw `hex` so the owner can submit it anywhere. | §3.9 MP-1/TPL-1; §3.5 SWEEP; §4.5; `sweep_relayed_by_own_node`. |
| L14 | **No wallet path releases a VOID vault.** K3 says a VOID owner "sweeps before `claimHeight`", the GUI warns, `yellowback_void_mint.py` "releases at `lockHeight` with no burn and no fee" — but `yed_redeem` refuses anything not ACTIVE (`vault-not-active`) and `yed_sweep` refuses without abandonment. The collateral of every failed mint was unreachable from the wallet. | **`yed_redeem` on a VOID vault builds the release:** owner path, no burn, no fee, no payload — an ordinary spend that no rule polices (K3), `burnedCents = 0` in the return; `vault-not-active` is raised only for CLOSED and CLAIMED; `yed_listpositions.canRedeem` is true for a VOID vault at or past `lockHeight`; the Vaults screen offers **Release** on VOID rows. | §3.5 template; §4.5; §4.6; §4.8; `void_release_via_yed_redeem`. |

| # | Finding | Severity | Change |
|---|---|---|---|
| P1 | **N11 was wrong for the live case.** `CheckForkWarningConditions` (`main.cpp:2197`) reads `pindexBestInvalid`, which grows only from *indexed* blocks (`InvalidChainFound`, `:2280-2283`; `FindMostWorkChain`, `:3716-3717`); descendants of a refused header are never indexed, so after a live rejection `pindexBestInvalid` is the rejected block itself, one block of work above the tip, and the stock "invalid chain at least ~6 blocks longer" warning never fires. It fires only in the catch-up case (L11). Phase 5 case 9 and drill D12 asserted a warning that would not appear. | precision | The valve raises its own warning through the same two calls the stock code uses — `SetMiscWarning` (`warnings.cpp:22`; read by `getinfo.errors` via `GetWarnings("statusbar")`, `rpc/misc.cpp:111`) and `CAlert::Notify(…, true)` (`alert.h:107`) — with the text `Yellowback: work valve tripped at height H (rejected root …); enforcement off until restart`; §4.7, case 9 and D12 assert that string; §4.3. |
| P2 | **The odometer's note map was unbounded.** The N1 clause runs after `CheckBlockHeader` (`:4547`, proof of work against the header's *own* `nBits`) but before `ContextualCheckBlockHeader` (`:4561`, `nBits == GetNextWorkRequired`, `:4392`), so a peer can feed unlimited headers descending from a rejected block at any difficulty it likes; each costs it one cheap Equihash solution and costs the node a map entry for the session. (It cannot inflate the odometer: `GetBlockProof` is real work whatever `nBits` says.) | DoS | `NoteHeaderOnRejectedChain` notes a header only if its target is within the consensus per-block loosening of its parent's (`nPowMaxAdjustDown = 32 %`, `chainparams.cpp:104`: `target ≤ parentTarget · 132 / 100`; the parent is the rejected root or a note) and only while the root holds fewer than `VALVE_NOTE_CAP = 64` notes; beyond either bound the header is still answered DoS 0 but not noted. Unit `valve_note_map_bounded`, `valve_ignores_lowdiff_headers`; Phase 8 DoS row; §3.1 row. |
| P3 | **Convergence after a trip needs one more announcement.** The header that trips the valve is itself refused (DoS 0, unnoted); nothing is fetched until the next `inv` triggers `getheaders` from `pindexBestHeader` (`:6281`) — now accepted because the root is reconsidered — and the block download. Case 9 mined exactly enough blocks to trip and asserted the reorg. | precision | ACT-7 states the sequence; case 9 and rc1 step 6b mine `VALVE_BLOCKS + 2` on the rejected root and assert convergence after the last; §4.7 says "at the next block the network announces". |
| P4 | **CI in the fork cannot see the workspace.** The `audit` job ran `make -C .. spec-check` and Phase 7's acceptance diffed against `../docs/plans/…`; the fork's GitHub Actions checks out `ycash-dd` alone. `yellowback_stockparity.py` needed "a cached `ref/ycash` build" the runner does not have. | **readiness** | The spec and the trust statement are published *into the fork* (`doc/yellowback-spec.md`; the statement inside `doc/yellowback.md`) by `make spec`, which writes both copies with a `Source:` header (plan revision, `sha256` of §3); `make status` (workspace-local) checks staleness; the fork's `audit` job checks only fork-local facts (the spec file's header hash equals the hash of its body; the trust statement in `doc/yellowback.md` equals the fork's `doc/yellowback-spec.md` §8.1 copy). Stock parity builds `ycash-legacy` from the same repository in a `git worktree`, cached by commit. §6.0 item 6; Phase 0; Phase 7 acceptance. |
| P5 | **Stock behaviour had no PR gate.** `main` ran only `yellowback_*` unit tests; a regression in `miner_tests`, `main_tests` or `mempool_tests` from the `main.cpp`/`miner.cpp` edits surfaced nightly at best. | test gap | `main` runs the whole `test_bitcoin` on every PR plus a fixed inherited functional baseline (`getblocktemplate_proposals`, `getblocktemplate_longpoll`, `mempool_reorg`, `mempool_tx_expiry`, `p2p-acceptblock`, `invalidateblock`, `reorg_limit`, `reindex`, `wallet`, `rawtransactions`, `txn_doublespend` — all shipped in `ref/ycash/qa/rpc-tests/`); `make check` stays nightly. §6.0 item 6. |
| P6 | **Concurrency and memory safety were greps and a reviewer's word.** K17 was a real data race; the lock order `cs_main → cs_wallet → mempool.cs → cs_yellowback` was checked by grep only. Ycash ships the tools: `--enable-debug` defines `DEBUG_LOCKORDER` (`configure.ac:249`; `sync.cpp:22-224` aborts on a potential deadlock), `--with-sanitizers` (`:211`), `--enable-lcov` (`:167`). | test gap | Nightly jobs `lockorder` (debug build, the functional suite), `sanitizers` (address+undefined: `test_bitcoin yellowback_*` and `yellowback_index`/`yellowback_enforcement`; thread: `test_bitcoin yellowback_*`) and `coverage` (lcov with floors: ≥ 95 % lines in `state.cpp`, `math.h`, `tag.cpp`, `payload.cpp`, `script.cpp`; ≥ 85 % in `index.cpp`, `policy.cpp`; ≥ 80 % in `txbuilder.cpp`, `rpc/yellowback*.cpp`); Phase 3 and Phase 8 exits require them green; §8.4 items 23–24. |
| P7 | **The RPC contract was a document nobody executed.** `doc/yellowback-rpc.md` is "the contract" for the wallet fork, but no test compared it with the binary, and the wallet repository cannot read the node repository. | test gap | Each command's return shape in `doc/yellowback-rpc.md` is a fenced JSON block; `make spec` extracts them into `yellowback-rpc-contract.json`, copied into **both** forks; `qa/rpc-tests/yellowback_rpc_contract.py` (in `main` from Phase 3) calls every command and asserts every documented key with its type, and provokes every error identifier; the wallet job checks every field name in `yellowbackrpc.h` against its copy. §8.4 item 25. |
| P8 | **The accounting half of the model was optional.** N23's Python model covered snapshots only; the money rules (IN-1..3, MINT, XFER, RED) had one implementation. | test gap | `yellowback_model.py` models §3.8 too, from `getblock … 2` and `yed_gettag`; `assert_model_matches(node, full=True)` compares `yed_gettxinfo` and `yed_listvaults` for every transaction; required in `yellowback_lifecycle.py`, `yellowback_claim.py`, `yellowback_enforcement.py --extended` and rc1 (Phase 6 exit). |
| P9 | **The stock node in every scenario was the fork binary.** "Every block an enforcing miner produces is valid to a stock node" was tested against the fork without the flag; a real v4.5.0 binary sat only in the parity script. `start_nodes` takes per-node binaries (`util.py:396-410`). | test gap | `yellowback_stock_node.py` and `yellowback_enforcement.py` take `--stock-binary`; nightly runs both with node 1 on the `ycash-legacy` build. |
| P10 | TAG-1 scans for the 5-byte `24 59 45 44 21` while TAG-5 says "the first occurrence of the magic" (4 bytes). | precision | Both name the 5-byte pattern (push opcode ‖ magic); `tag1_magic_without_push_opcode_is_no_tag`. |
| P11 | The `AcceptToMemoryPool` row did not say that `pool.cs` is held for the whole function (`:1520`, "held through `pool.addUnchecked()`"), so MP-1 runs under `cs_main → pool.cs → cs_yellowback`. | precision | Stated in §4.3; it matches the recorded lock order. |
| P12 | `crash_unflushed_chainstate` and rc1 step 4 killed node 3 "right after `generate` on node 2" without syncing node 3 first; quote-staleness cases slept on the wall clock; the cached chain's block times put every node in IBD until its first fresh block (harmless, but a test asserting a rejection must mine one fresh block first). | precision | `sync_blocks([2, 3])` before `kill9(3)`; `setmocktime` (`rpc/misc.cpp:1202`) instead of `sleep`; the IBD note in §6.0 item 4. |
| P13 | No PR template carried the four-part check, the tier and the `// Rule:` tags; nothing said who reviews a hook change. | readiness | `.github/PULL_REQUEST_TEMPLATE.md` (Phase 0) and the review rule in the §6 preamble: two reviewers for any PR touching `main.cpp`, `miner.cpp`, `rpc/mining.cpp` or `state.cpp`, one from outside the implementing pair. |
| P14 | Phase 9 assumed two independent testnet pools with no fallback; Phase 10 had a 90-day review but no incident playbook. | readiness | Phase 9 fallback (team-run pool stacks on team hashpower, D9 per stack still); Phase 10 incident playbook with three scenarios and a hotfix cadence; `incident` joins the runbook greps (§8.4 item 18). |
| P15 | `pindexBestInvalid` and IBD semantics are Ycash-specific traps worth a row each. | mapping | `mapping.md` §13 rows. |

Everything else in revision 5 survived. L11–L14 change what the node *does* and are applied
pending confirmation; P1–P15 change what the document says and what the tests prove.

---

## 1. The decision in one page

**Yellowback v2 is a miner-enforced overlay: Tier 1 (mining policy) plus one block-validity hook
in `main.cpp` that is inert until an activation derived from the chain itself, that only ever
fires on transactions spending a Yellowback vault, that never bans a peer (neither for the rejected
block nor for its descendants, BLK-2), that fails open only on
a storage failure (its evaluation is total, K1), and that an operator can switch off with one flag.** Everything else is the prototype's
overlay: ordinary Ycash v4 transactions, one `OP_RETURN` payload, a self-contained index.

The seven load-bearing choices:

1. **Who enforces.** Mining pools running the module. Before activation they filter their own
   templates (policy, cannot fork anything). After activation (≥ 75 % of a 2,016-block window
   signalling, then a 2,016-block delay) they also reject blocks that contain a vault spend
   without the matching burn. That is a soft fork in the P2SH/CLTV sense: every block an enforcing
   miner produces is valid to a stock node; a stock miner's block is rejected only if it spends a
   vault in a way the rules forbid. (V1, V2)

2. **What can invalidate a block.** Exactly one class of transaction: a spend of an ACTIVE vault
   output whose burn or enforcement fee is wrong (rules RED-1..4, §3.8), and only while
   enforcement is not suspended (ACT-5/ACT-6: rejection suspends below 50 % signalling and resumes
   at 60 %, L3). Invalid mints and
   transfers keep the overlay verdict semantics (an invalid mint creates no YED and leaves a VOID
   vault; an invalid transfer burns the sender's inputs) and never invalidate
   a block. Coinbase tags never invalidate a block. This keeps the consensus-shaped surface to one
   pure function over one script-identifiable set of transactions. (V3)

3. **Where the price comes from.** A 36-byte tag in the coinbase scriptSig after the BIP34 height
   push, carried by the never-assigned `COINBASE_FLAGS` global so the internal miner, regtest
   `generate` and `getblocktemplate` all emit it without new plumbing. Three rolling medians
   (96 / 576 / 2,016 blocks) over quote-tagged blocks; `P_mint = min`, `P_claim = max(mid, slow)`. The
   quote itself is computed by a small external agent (the prototype's Python price-source layer:
   presets per venue, every field overridable, per-source guards) and pushed
   into the node with one RPC, because `ycashd` links no HTTPS client. (V4, V5, V6)

4. **The vault.** `OP_IF <lock> CLTV DROP <owner> CHECKSIG OP_ELSE <lock+grace> CLTV DROP OP_TRUE
   OP_ENDIF`, P2SH. The owner path needs the minter's key; the claim path needs nobody's key and
   is policed by RED-4 (burn the debt, vault underwater at `P_claim`). No federation key, no
   co-signature, no wizard: `yed_redeem` builds, signs and broadcasts in one call. (V7)

5. **State stays synchronous with the chain.** The prototype's index moves from the asynchronous `ChainTip`
   subscriber to two hook calls inside `ConnectBlock` and one inside `DisconnectBlock`, because a
   block-validity check needs the state at the parent block under `cs_main`, not a state that
   trails by a second. The `ChainTip`/`SyncTransaction` subscriber stays for wallet coin locking
   only. (V2)

6. **Money for enforcers.** Mints, redemptions and claims pay an enforcement fee
   (`max(0.5 YEC, 0.25 % of collateral)`) to any pool that published a quote in the 100 heights
   up to and including the transaction's reference height; the wallet picks which one, by default
   weighted toward pools whose quotes track the peer median (L1, overridable per node, L6).
   A block without a quote tag earns nothing. (V10)

7. **Reference heights.** Every mint, redemption and claim commits a `refHeight` in its payload
   (the prototype's `evalHeight`, set by the wallet a few blocks behind the tip so that a short
   reorg cannot change the snapshot it names); prices, halts and activation are read from the snapshot at that height
   and the eligible payee set from the quote tags at or below it, so the wallet knows the exact
   verdict before it signs and a 40-block window bounds staleness. (V11)

**What this costs, stated plainly.** (a) `main.cpp` and `miner.cpp` change — about 50 lines,
all insertions, every behaviour-changing statement behind `if (g_yellowback)` (the unguarded
remainder — two includes, the K17 lock, the empty `COINBASE_FLAGS` append — is listed in §8.4
item 2), listed line by line in §4.3. A node without `-yellowback` runs v4.5.0's code paths; the
only unguarded differences are the empty `COINBASE_FLAGS` append and one lock acquisition, both
listed in §8.4 item 2, and `yellowback_stockparity.py` diffs the two binaries nightly (N10). (b) A bug in the block-validity hook could fork enforcing
miners off the chain; the mitigations are that the hook rejects only ACTIVE-vault spends, fails
open on a storage failure only (the block is accepted and the index is marked unhealthy) while
its evaluation is total and can never throw (K1), is off until a chain-derived activation and
while participation is below the floor (ACT-5), has a kill switch that also un-rejects blocks
(V1, V13), trips a work valve that re-joins a rejected chain once it is six blocks heavier than
the node's own (ACT-7, L7), never rejects a block the network has already built six blocks on
(catch-up suppression, L11), and sunsets at a per-release height (L8). (c) The
price feed's honesty rests on the honest-majority-hashpower assumption the chain already makes,
made precise by medians and the min/max selectors (peer-median penalties and accuracy weighting
act only through wallets' default payee choice, L1); the feed's *availability*
rests on enough pools running the module, and the design degrades to "no new mints" when they do
not. (d) The claim path is anyone-can-spend at the script level; a vault is safe only while a
majority of hashpower enforces RED-4, which is why minting is impossible before activation, halts
when signalling falls below 60 %, and block rejection itself suspends only below 50 % (L3). (e) YED stays on transparent outputs; the proposal's
shielded YED transfers are deferred (V8), because miners cannot enforce what they cannot read.

**Why not the prototype's federation.** It worked on regtest, but every redemption needs `k` operators
online and reachable, every price needs a signing round, and the roster is a standing committee
that holds the release key to every vault. Coordinating signers was the burden the product owner
named on 2026-09-10; the proposal removes the committee entirely.

**Why not a network upgrade now.** It is still the largest ask of a risk-averse team, and every
rule below is written so that the same validator can be promoted to consensus later (§9), with
months of miner-enforced mileage behind it. Miner enforcement is the launch mechanism; consensus
enforcement is the destination.

---

## 2. Decision record

Each entry: options considered → **decision** → why → what it costs. Numbers cite the pinned
trees. Identifiers V1–V26 are used throughout.

### V1. Tier and enforcement mechanism

Options: (a) template filter only (never reject a block) · (b) template filter plus a
block-validity hook in `ConnectBlock`, active after a chain-derived activation · (c) a
consensus network upgrade now.

**Decision: (b).** Throughout, **R1** is the proposal's burn-on-release rule (§5.4 there: a vault
output is spent only with the matching burn) and **R2** its claim-path rule (§5.5: the claim path is
spent only against an underwater vault with the burn). (a) cannot enforce R1: a non-participating pool includes the vault spend, and
the enforcing pools would build on it. (c) is §9. The hook is placed in the window
`ref/ycash/src/main.cpp:3191-3193` — after every input has been checked and the coinbase value
rule (`bad-cb-amount`, `:3182-3187`) and `control.Wait()` (`:3189-3190`), before
`if (fJustCheck) return true;` (`:3194-3195`) — so it runs for every caller of `ConnectBlock`:
`ConnectTip` (`:3612`), `TestBlockValidity` (`:4711`, which is what `CreateNewBlock` calls on its
own template, `miner.cpp:660`) and `VerifyDB` level 4 (`:5162`). It reports with
`state.DoS(0, error(...), REJECT_INVALID, "yellowback-…")`: `InvalidBlockFound`
(`main.cpp:2297-2313`) marks the block `BLOCK_FAILED_VALID` and calls `Misbehaving` **only when
`nDoS > 0`** (`:2304-2305`), so a stock peer that relayed the block is never scored or banned —
essential when most of the network is unpatched. The same holds for the block's descendants: the
stock path answers a header built on a `BLOCK_FAILED_VALID` block with `bad-prevblk` at DoS 100
(`:4557-4558`), or "prev block not found" at DoS 10 when the refused parent never entered
`mapBlockIndex` (`:4555`), and both the `headers` (`:6604-6610`) and `block` (`:6651-6658`)
handlers pass that score to `Misbehaving` — so without a clause of its own an enforcing node would
ban every stock peer within one block of a rejection (N1). One inserted clause at `:4553`, before
both returns, answers such headers with `state.DoS(0, …, REJECT_INVALID,
"bad-prevblk-yellowback")` (BLK-2, §4.3). Cost: the fork risk of any soft fork, bounded by
V3 (only vault spends), V13 (fail open, kill switch) and V12 (activation threshold).

### V2. Synchronous state: the index moves into the block-connect path

Options: (a) keep the prototype's `CValidationInterface` subscriber (`ChainTip`, once per second on
`ThreadNotifyWallets`, never under `cs_main`) and have the hook read it · (b) apply and undo the
Yellowback state inside `ConnectBlock`/`DisconnectBlock` under `cs_main`, keep the subscriber for
wallet locking only.

**Decision: (b).** The hook needs the state at `pindex->pprev` at the moment the block is
connected; the notifier trails the tip by up to a second (`validationinterface.cpp:92-96`) and
runs on another thread. Placement: the check in the `:3191-3193` window (V1); the commit after
`view.SetBestBlock` (`:3268`), past every write that can `AbortNode` (`:3204-3263`, K20), so
`fJustCheck` runs never mutate anything; the undo at the end of `DisconnectBlock` (`main.cpp:2633-2635`, a `static` with an
`updateIndices` parameter that `DisconnectTip` passes as `true` (`:3541`) and `VerifyDB` level 3
as `false` (`:5133`) — the undo is gated on it, so the startup self-check cannot corrupt the index).
Both apply and undo are additionally guarded by "the index tip equals `pprev` (apply) / equals
this block (undo)" so a `VerifyDB` level-4 reconnect (`:5162`), which reconnects from an ancestor
with a throwaway coins view, is skipped rather than double-applied; the index does not exist yet
at that point in `init.cpp` anyway (it is created after wallet load, immediately before the notifier
thread starts, §4.3). Crash consistency:
the index commits one LevelDB batch per block while the chainstate flushes lazily
(`FLUSH_STATE_IF_NEEDED` writes only when the coin cache is full, `main.cpp:3324-3334`; periodic
flush once a day, `main.h:108`), so after a crash the index may be ahead of `chainActive` by up
to a day of blocks. The prototype's `SyncToChain` already handles "stored tip not in `chainActive`" by
undoing; `UNDO_KEEP` rises from 1,000 to **4,096** blocks so that walk succeeds, and the existing
wipe-and-rebuild fallback covers anything deeper (blocks are on disk; `-prune` is still refused).
Cost: `synced` disappears from `yed_getinfo` (the index is always at the tip) and RPCs take
`cs_main` before `cs_yellowback` exactly as before (lock order `cs_main → cs_wallet → cs_yellowback`
unchanged; the notifier thread never takes `cs_main` in block callbacks).

### V3. Block validity is exactly "vault spends obey RED-1..4"

Options: (a) every proposal rule makes a block invalid (mints, transfers, fees, tags) · (b) only
vault spends do; everything else keeps the overlay's verdict semantics (invalid mint ⇒ no YED and a VOID vault,
invalid transfer ⇒ the sender's inputs are burned).

**Decision: (b), for ACTIVE vaults only.** Soundness needs only two things the chain cannot see:
collateral is not released without the burn (R1), and the claim path is not swept (R2). Both are
properties of transactions that spend an ACTIVE vault output, a set every node identifies from the
`Vaults` table. VOID vaults (a failed mint's collateral, no debt) are not policed: they cost dust
to create and their lock may already be past, so policing them would let anyone orphan
stock-mined blocks on demand (K3); their owner sweeps them before `claimHeight`. An
invalid mint creates no YED (VOID), so it needs no rejection; an invalid transfer burns the sender's
own YED. Making them block-invalid would multiply the consensus-shaped arithmetic (ratios, caps,
halts, σ) by the fork risk for no soundness gain. Coinbase tags never invalidate a block either
(TAG-4): a stock miner's block is always valid unless it spends an ACTIVE vault. What the rule set
still drags into the enforcers' shared computation is stated plainly (K10, narrowed by L1):
RED-3 needs the eligible payee set (`Tags` in the payee window) and the fee amount, and RED-4
needs `P_claim`, hence two medians; so the windows, `PAYEE_WINDOW`, the fee constants, the claim
threshold and the grace period are consensus-shaped *among enforcing miners*, and a change to any
of them is a coordinated release with a start height (§3.1). The peer-median judgements,
penalties and accuracy scores are not: they feed only `yed_listminers` and the wallet's default
payee choice (whose selection parameters a node may even override, L6). Cost: the two user-loss
residuals the prototype already carries — a mint that races the supply cap, or a reorg deeper than
`REF_LAG` that changes the reference snapshot, leaves the mint VOID with its collateral locked for
the term — remain; the template filter's strict mode (V14) keeps
enforcing miners from mining such a mint in the first place.

### V4. Coinbase tag carrier

Options: (a) a zero-value `OP_RETURN` coinbase output (DigiByte's `OP_RETURN OP_ORACLE …`,
`ref/digibyte/src/oracle/bundle_manager.cpp:891-940`, appended as an extra output `:815-828`) ·
(b) a push in the coinbase scriptSig after the BIP34 height, as the proposal specifies.

**Decision: (b).** Consensus constrains the coinbase scriptSig to `2 ≤ size ≤ 100` bytes
(`bad-cb-length`, `ref/ycash/src/main.cpp:1456-1458`) and checks only that it *starts with* the
minimal height push (`bad-cb-height`, `:4477-4481`, a prefix comparison); nothing after the
prefix is inspected. A 36-byte tag pushed as `0x24 ‖ tag` costs 37 bytes, leaving 59 for a pool's
extranonce and signature at any mainnet height. An extra output would collide with the
founders'/YDF/funding-stream output layout that `getblocktemplate` hard-codes (`vout[1]` is
reported as `foundersreward`, `rpc/mining.cpp:732`) and would need pools to rebuild outputs.
Detection is a **byte-level scan** for `0x24 59 45 44 21` after the height push, not a script
parse, because pools write raw extranonce bytes that need not be push-encoded (§3.2). Cost: pools
must keep their own coinbase text ≤ ~55 bytes; documented in the pool kit (§5).

### V5. How the tag reaches every coinbase Ycash can produce

Finding: `IncrementExtraNonce` **replaces** the whole scriptSig with
`(CScript() << nHeight << CScriptNum(nExtraNonce)) + COINBASE_FLAGS` (`ref/ycash/src/miner.cpp:720`),
and it is on the path of the internal miner (`:832`), regtest `generate` (`rpc/mining.cpp:222`) and
the unit-test harness (`test/test_bitcoin.cpp:167`). `COINBASE_FLAGS` (`main.cpp:134`, `main.h:163`)
is **never assigned anywhere in the tree**; `getblocktemplate` builds a `coinbaseaux.flags` from it
(`rpc/mining.cpp:742`) but pushes it only in a branch that `coinbasetxn = true` (`:504-505`) makes
unreachable, which V26 fixes.

**Decision:** the module sets `COINBASE_FLAGS` to the tag push under `cs_main` whenever
`CreateNewBlock` builds a template (one call), and `CreateCoinbaseTransaction` appends
`COINBASE_FLAGS` to its scriptSig (`miner.cpp:327` becomes `CScript() << nHeight << OP_0` +
`COINBASE_FLAGS`, one line) so the `coinbasetxn` that `getblocktemplate` returns carries the tag
too. Three carriers, one source of truth, no new field on the miner path. The
`assert(scriptSig.size() <= 100)` at `miner.cpp:721` is safe: height (≤ 5 bytes) + extranonce
(≤ 6) + 37 = 48. Cost: `COINBASE_FLAGS` becomes mutable state under `cs_main` (it always was a
global; its readers — `miner.cpp:720`, `rpc/mining.cpp:742` — hold `cs_main` once K17 is applied, and
`test_bitcoin.cpp:167` is single-threaded).

### V6. Quote source: an external agent, one RPC

Options: (a) fetch exchange prices inside `ycashd` (the proposal's "module computes a 15-minute
VWAP") · (b) an external quote agent pushes the quote into the node.

**Decision: (b).** `ycashd` links neither libcurl nor OpenSSL (`ref/ycash/configure.ac`; the prototype
already kept price fetching out of process for that reason), and the prototype's price-source layer
already exists in Python with presets for every venue that lists
YEC, per-source freshness and spread guards, BTC-pair conversion and a time-weighted average
(presets expand into a bare `url` + JSON `path` per source, every field overridable;
`contrib/yellowback/yellowback_fed.py:126-637`). It becomes `yellowback-quote` (§5): it
polls, aggregates, and calls `yed_setquote <priceMicroUsd> <sourceMask>` every poll. The node
stores the quote with a receipt time and emits the tag only while the quote is younger than
`-yellowbackquotemaxage` (default 1,800 s, the proposal's 30-minute staleness limit); older, it
emits a **signal-only** tag (V9). Cost: one more process on the pool server (the pool already runs
several), and a mock-price file for tests instead of a compiled-in mock.

### V7. Vault script

Options: (a) the prototype's `CLTV + owner CHECKSIGVERIFY + k-of-n` · (b) the proposal's two-path script ·
(c) owner-only `CLTV + owner CHECKSIG` with no claim path.

**Decision: (b), one template for every vault.**
```
OP_IF   <lockHeight>  OP_CHECKLOCKTIMEVERIFY OP_DROP <ownerPubKey> OP_CHECKSIG
OP_ELSE <claimHeight> OP_CHECKLOCKTIMEVERIFY OP_DROP OP_TRUE
OP_ENDIF
```
with `claimHeight = lockHeight + GRACE`. Owner scriptSig `<sig> OP_1 <script>`; claim scriptSig
`OP_0 <script>`. Both leave exactly one true element (`CLEANSTACK`), both are minimal pushes
(`MINIMALDATA`), the script is 51–53 bytes with one sigop, and `AreInputsStandard` accepts any
P2SH subscript with ≤ 15 sigops (`ref/ycash/src/policy/policy.cpp:173-178`), so relay is as for
the prototype's vault. Ycash has no `MINIMALIF` flag (`interpreter.h:80-88`), so `OP_1` as the selector is
not policed beyond `MINIMALDATA`. (c) was rejected because it leaves YED holders with a claim on
nothing when YEC crashes and minters abandon vaults (proposal §8.4); (a) is the committee. Cost:
the claim path is anyone-can-spend at the base layer and safe only under enforcement, so
**minting is impossible before activation** (MINT-4) and the wallet refuses to build a vault
while the participation halt is on.

### V8. YED representation: transparent colored outputs, not a shielded ledger

The proposal (§5.3) records transfers in Sapling memos and tracks balances per recipient.

**Decision: YED stays on transparent colored outputs, as in the prototype, and that is structural rather
than a rule — a payload assigns cents to `vout` indexes and a Sapling output has no index, no script
and no amount the index can see (`ref/ycash/src/primitives/transaction.h:553-558`), so "shielded YED"
is undefined, not forbidden; shielded YED is deferred to research.** A miner cannot validate a burn it cannot read: R1 requires the burn's YED
inputs to be public so every enforcing node computes the same `yedIn`. A memo-based ledger would
make supply and per-vault burns unverifiable by anyone but the parties, and the enforcer is the
one party that must verify. What the prototype already gives the user stays: a mint funded straight from a
`ys1…` address and collateral returned straight to one (a user whose YEC is shielded must not have to
unshield in a separate, visible step; built with `TransactionBuilder` plus a three-method additive
extension in `src/transaction_builder.{h,cpp}` — raw-script output, unsigned transparent input,
lock-time setter).
Recorded in §10.1 and §12; the research direction is a per-asset value-pool commitment, which is
a network upgrade, not an overlay change (`mapping.md` §6).

### V9. Tag semantics: quote tags and signal-only tags

The proposal omits the tag when the quote is stale, which also drops the miner's activation
signal and its participation count.

**Decision:** a tag with `priceMicroUsd = 0` is a valid **signal-only** tag: it counts for
signalling and participation (ACT-1), contributes no quote, registers nobody and earns no fee
(TAG-3). A stale feed then affects the pool's income, not the network's activation state. Cost:
participation can be high while quote coverage is thin; the minimum-fill rule on every price
window (V16) fails closed in that case, so no mint can use a thin price.

### V10. Enforcement fee and payee selection

The proposal selects `selected_block = tip_height − (txid_low32 mod 100)`, which is circular (the
txid depends on the fee output) and undefined for an unconfirmed transaction.

**Decision (revised in revision 3, L1): validity checks the amount and that the payee is *some*
recently quoting pool; the choice of pool is wallet policy.** The eligible set `E(R)` is the set
of `payoutKey`s of the quote tags at heights `(refHeight − PAYEE_WINDOW, refHeight]`; the fee
output must pay `P2PKH(k)` for some `k ∈ E(R)`. That is a pure function of `Tags` alone, so the
peer-median judgements, penalties and accuracy scores (REG-2..4) are no longer read by any
validity rule (K10's surface shrinks to what `P_claim` needs). The wallet's **default** choice
(FEE-W) is revision 2's deterministic selection: `seed = SHA256(blockHash(R) ‖ selector)` with
`selector = ownerPubKey` (MINT) or the vault outpoint (REDEEM), over the tags in the window with
weight `10⁴ + accuracyBps` per block, skipping penalised keys — hashpower-proportional with a
1×–2× tilt toward careful pools (K8); its result is `payee(R, selector)`. The selection parameters
(penalty length, accuracy window, tilt) are release-versioned defaults a node may override, and
`-yellowbackpreferredpayee=<s1…>` replaces the choice outright when that key is eligible (L6). What this gives up against the proposal: a lying pool forfeits fee income
only through wallets' defaults, not through a rule; what it buys: a pool cannot dodge the fee,
and a bug in the judgement code can never split the enforcing set.
The amount is `max(FEE_MIN, collateralZat × FEE_BPS / 10⁴)` — the proposal's "0.25 % of
collateral value at `P_mint`" is 0.25 % of the collateral itself once expressed in YEC, so no
price enters. **FEE-0:** when the eligible set is empty (no quote tags in the window), no fee
is required and `feeVout` is ignored, so redemptions never depend on miner participation
(proposal §5.6: halts never affect burns). A mint requires `collateralZat ≥ 4 · FEE_MIN` so the
fee of its eventual redemption can always be paid from the collateral (K14). The fee is a block-validity condition for vault spends (RED-3) and a verdict
condition for mints (MINT-8 ⇒ VOID). Cost: the fee is paid in YEC to a P2PKH the payload names by
`feeVout`, so mints and redemptions each carry one more output.

### V11. Reference heights (`refHeight`) for every rule input

**Decision:** MINT and REDEEM payloads carry `refHeight` (the prototype's `evalHeight`: the payload commits
the height whose snapshot the rules read, so the wallet knows the exact requirement before it signs and a
short reorg cannot void the mint) with
`H − REF_WINDOW ≤ refHeight ≤ H − 1` (`REF_WINDOW = 40` = the transaction expiry delta,
`ref/ycash/src/main.h:78-79`). Prices, σ, halts and activation status are read from
`Snapshots[refHeight]`, the eligible payee set `E(refHeight)` from the quote tags in
`(refHeight − PAYEE_WINDOW, refHeight]`; supply totals for MINT-6 are read at `H` (in-block).
The wallet uses `refHeight = tip − REF_LAG` (default 2) and `nExpiryHeight = refHeight +
REF_WINDOW`, the prototype's arithmetic; the expiry is a wallet convenience, **not** a rule — a transaction
with `nExpiryHeight = 0` is still bound by the `refHeight` window (M13). Why `≤ H − 1`: `Snapshots[H]` is written after block `H` is
applied, so a rule evaluated while validating block `H` can only read snapshots below `H`. Cost:
none beyond what the prototype already carries.

### V12. Activation state machine lives in the overlay

Ycash has no versionbits (`mapping.md` §4). **Decision:** the state machine keeps
`Activation { status ∈ {SIGNALING, LOCKED_IN, ACTIVE}, lockInHeight, activateHeight }` computed
at every SNAP from the signal bits of the trailing `SIGNAL_WINDOW` tags (ACT-1..6), evaluated on a
rolling basis (deterministic; no period alignment needed). Enforcement at height `H` is on iff
`Snapshots[H − 1].activation == ACTIVE` **and** the `ENFORCEMENT` bit is clear at `H − 1` (ACT-5):
if signalling hashpower later falls below **half** (`ENFORCEMENT_FLOOR`, ACT-6), block rejection
suspends and resumes at 60 % (`ENFORCEMENT_RESUME`), so an enforcing node is not left alone on a
minority chain by a rule the majority no longer applies (K2) — and because ACT-6 reads the node's
*own* chain, which after a split is mined only by enforcers, the mechanical bound on that promise
is the work valve: a chain rooted at a rejected block that outruns the node's tip by
`VALVE_BLOCKS = 6` blocks of work switches enforcement off for the session (ACT-7, L7), so the
promise is "never for more than six blocks"; the *mint* halt is the separate,
earlier `PARTICIPATION` bit (below 60 %, back at 75 %, ACT-4), so minting stops well before
enforcement does (L3). While rejection is suspended neither the owner path nor the claim path is
policed by anyone but the pools that still filter their templates — the degraded state the
proposal accepts (§8.6 there), now bounded at half the hashpower rather than 40 %. The signal bit
is set only by a node that also enforces (MINER-1), but the count is self-reported and can be
inflated by anyone — any coinbase may carry `YED!` with bit 0 (TAG-3) — so it under-counts only
among honest pools; against a forged majority the work valve (ACT-7) is the mechanical backstop
(N4). Because status becomes ACTIVE in `Snapshots[activateHeight]`, BLK-1 first applies
at `activateHeight + 1` (K16). `startHeight` per network is the first height whose tags
count. A later release may pin `activateHeight` per network the way DigiByte buried its BIP9
deployment (`ref/digibyte/src/kernel/chainparams.cpp:174-188`) — optional, §9. Cost: a reindex
recomputes activation from tags, which is cheap (one bit per block).

### V13. Fail open, and the kill switch

**Decision:** (i) evaluation is **total** — `EvaluateBlock` never throws; every undefined lookup
(a missing snapshot, an undefined price, an out-of-range height) is a verdict — and it is fuzzed
for throws; only a storage failure (LevelDB) reaches the hook boundary, where it is caught,
logged, the block is **accepted**, and the index is marked unhealthy; while unhealthy the node
emits no tag, filters nothing, enforces nothing, and every `yed_*` call outside the diagnostic
allow-list of §4.5 (`yed_getinfo`, `yed_getblockverdict`, `yed_gettag`, `yed_decodepayload`,
`yed_setquote`) refuses (the prototype's unhealthy-index semantics, widened by M8). A fail-open that any transaction could trigger would be an attacker's kill switch
(K1), which is why totality is a rule, not a hope. (ii) `-yellowbackenforce=0` disables the block-validity check while keeping the
tag and the template filter. (iii) The index records every block hash it rejected
(`Rejected` table, written with `sync = true` so a power loss cannot leave a `BLOCK_FAILED_VALID`
mark the kill switch does not know about, N8); at startup with enforcement off, `init.cpp` calls `ReconsiderBlock`
(`ref/ycash/src/main.cpp:3970-3999`, public via `main.h:557`) for each under one `LOCK(cs_main)`
after the block index is loaded and before the notifier thread and `ThreadImport` (`ref/ycash/src/init.cpp:1730-1883`;
in the fork, whose `init.cpp` carries the prototype's 75 lines, `:1779-1952`), then
`ActivateBestChain` once, the pattern of the `reconsiderblock` RPC (`rpc/blockchain.cpp:1495-1509`).
Only recorded hashes are reconsidered because `ReconsiderBlock` clears `BLOCK_FAILED_MASK`
indiscriminately (`:3979`, `:3995`). Cost: an operator who disables enforcement rejoins whatever
chain the network has; `MAX_REORG_LENGTH = 99` (`main.h:62`, `= COINBASE_MATURITY − 1`) bounds the
length of the *active chain* a reorg may disconnect — `pindexOldTip->nHeight − pindexFork->nHeight`,
whoever mined those blocks — before the node shuts itself down (`main.cpp:3770-3789`, N15); any
enforcing node, mining or not, that stayed on an enforcing branch for more than 99 blocks must
restart with `-reindex` (BLK-2 suppresses rejection under `-reindex`, N2, so a reindex no longer
re-rejects the same blocks; `-yellowbackenforce=0` may be added as belt-and-braces) and re-enable
enforcement afterwards; `-reindex-yellowback` clears `Rejected` (the block index's
`BLOCK_FAILED_VALID` marks are what actually hold a rejection). With the valve below, a rejected
chain outruns the node by six blocks long before 99, so this path is unreachable in ordinary
operation; the runbook keeps it (M12). (iv) **The work valve (ACT-7, L7).** The kill switch of
(ii)–(iii) is manual and per operator; the valve is the automatic form of the same machinery: when
the index has noted, through the N1 clause in `AcceptBlockHeader`, headers descending from a block
in `Rejected` whose accumulated work is at least `VALVE_BLOCKS = 6` blocks of proof above the
node's tip (`work ≥ tip.nChainWork + VALVE_BLOCKS · GetBlockProof(*tip)`, the arithmetic of
`CheckForkWarningConditions`, `main.cpp:2197`), it sets `enforcing = false` for the session with
reason `valve-tripped`, runs the (iii) `ReconsiderBlock` loop right there under `cs_main` (which
`AcceptBlockHeader` holds), clears its note, drops the signal bit and alerts; the next stock block
to arrive then passes `AcceptBlockHeader`, is downloaded and `ProcessNewBlock → ActivateBestChain`
performs the reorganisation — no extra `ActivateBestChain` call and no new `main.cpp` line beyond
the N1 clause. Re-arming is an operator restart. Cost: enforcement becomes "majority in fact" —
the only guarantee a soft fork could give anyway; an attacker with a temporary majority can switch
it off for the session, but that attacker could already reorganise the chain. (v) **The sunset
(L8).** Past `ENFORCE_UNTIL_HEIGHT` of the parameter set in force the node stops rejecting (ACT-5),
keeps tagging and evaluating, drops the signal bit, logs "upgrade required" and reports
`yed_getinfo.sunset = true`; the fork release that carries the next set (or the next Ycash
network upgrade, §11) is the way back.

### V14. Template filter has a strict mode

**Decision:** `-yellowbacktemplatepolicy=strict` (default) excludes from the template every
transaction whose verdict would be block-invalid (RED-1..4) **and** every MINT that would register
VOID and every TRANSFER that would burn; `consensus` excludes only the block-invalid ones. The
filter runs in `CreateNewBlock`'s selection loop immediately before `UpdateCoins`
(`ref/ycash/src/miner.cpp:582`), on an overlay view that applies each accepted transaction in
template order, so in-block chaining and first-claim-wins are evaluated exactly as `ConnectBlock`
will. A mempool policy hook (MP-1) additionally refuses block-invalid vault spends at
`AcceptToMemoryPool` (`main.cpp:1643`, after `view.SetBackend(dummy)`, style of `:1567`:
`state.DoS(0, false, REJECT_NONSTANDARD, …)`), so enforcing nodes do not relay them. Cost: none
to consensus; strict mode is the user-protection the proposal asks pools to provide.

### V15. Combined VAULT+MINT, one debt per vault

The proposal records a VAULT then a MINT against it, allowing later top-up mints.

**Decision: the prototype's combined MINT (vault at `vout[0]`, token at `vout[1]`, payload) stays; a vault
carries exactly one debt for its life.** One transaction, one 51-byte payload, no "vault with no
debt yet" state for the claim path to mis-handle, and the vault outpoint is implied (`txid:0`).
Minting more against a risen price is a second vault. Cost: no top-ups; recorded in §10.1.

### V16. Price windows fail closed below their minimum fill

**Decision:** a median over window `W` is defined only if at least `WINDOW_MIN_FILL(W)` of the
blocks in `(H − W, H]` carry a quote tag (PRICE-1): `⌈W/2⌉` for the fast window, `⌈2W/3⌉` for the
mid and slow windows (L9). Otherwise that median, and every derived price that uses it, is
undefined and minting halts (HALT-1). The proposal does not say what a half-empty window means;
the conservative reading is the only safe one. The two-thirds rule on the `pClaim` windows is
the answer to the quote-majority arithmetic (L9, §8.2): a median is a majority of *quote tags*,
not of blocks, so at 50 % fill a pool with 26 % of blocks owns the median and can make healthy
vaults claimable for 42 hours; at two-thirds fill it needs 34 % of blocks — and once fill is near
100 % the two coincide. Cost, accepted: `pMint = min(pFast, pMid, pSlow)` needs all three
defined, so minting also needs two-thirds fill on the mid and slow windows.

### V17. Volatility multiplier computed on a smoothed series

The proposal takes σ from block-to-block log changes of the raw per-block quotes. With quotes from
different pools, consecutive blocks differ by the cross-pool spread (1–3 %) even in a flat market;
annualised over 420,480 blocks that reads as 600–2,000 % volatility and would multiply every ratio
by 6–20 (checked arithmetically: `isqrt(1e4 bps² × 420,480) ≈ 6.5e4 bps`).

**Decision:** σ is computed from the **`P_fast` series sampled every `VOL_STEP = 48` blocks**
over `VOL_WINDOW = 2,016` blocks (43 samples, 42 returns), in integer basis points, annualised by
the parameter `VOL_PERIODS_PER_YEAR = 8,760` (the same value on every network so a return series
gives the same multiplier everywhere, K13), with integer square roots (`arith_uint256`), and the
multiplier is capped at `SIGMA_MULT_MAX_BPS = 30,000` (3×) so a feed glitch cannot make minting
impossible for the whole 2,016-block (≈ 42-hour) volatility window; an undefined sample yields the
cap, never 1× (K12) (SIGMA-1). No floats, no logs (bps returns replace log returns; the difference is second
order at the magnitudes involved). Calibration of `SIGMA_REF_BPS` against YEC's realised volatility is
a testnet task (§6 Phase 9, §12). Cost: a deviation from the proposal, recorded in §10.1.

### V18. Peer-median judgement is lagged and one-shot

**Decision:** the quote in block `t` is judged once, when block `t + PEER_LAG` (`PEER_LAG = 10`)
is applied, against the median of the other quotes in `[t − 10, t + 9]`, provided at least
`PEER_MIN = 5` of them exist; the judgement (`evaluated`, `inBand`, `penalized`) is written to
`Judgements[t]` and undone with block `t + PEER_LAG`. Penalty and accuracy are then pure scans of
`Tags`/`Judgements` below a reference height (REG-2, REG-3). This is the proposal's "20 surrounding
blocks", made deterministic. Cost: the accuracy score is 10 blocks behind; immaterial.

### V19. Term classes are block ranges on the payload's own lock length

**Decision:** `MINT-2` checks `lockHeight − refHeight ∈ [classMin, classMax]` for the payload's
`termClass` (A `[30 d, 90 d]`, B `(90 d, 365 d]`, C `(365 d, 5 y]` in blocks, §3.1). The ranges
are contiguous and disjoint, so the class is a function of the lock length: the wallet takes
`lockBlocks` and derives the class; the payload still carries it and MINT-2 checks consistency.
No dependence on the confirmation height, so the wallet knows the class before signing.
`MAX_LOCK = 5 y` bounds class C (the proposal leaves it open). Cost: none.

### V20. Redemption burn is exactly the debt

**Decision:** RED-2 requires `yedIn − Σ assigned ≥ mintedCents`; the prototype's ERR discount (burn more
than minted when system health is low) and DCA (mint less when health is low) are **dropped**,
as the proposal replaces both with the global-ratio halt, the divergence halt, the volatility
multiplier and the claim path. The burn requirement is a block-validity rule (V3), and the simpler
it is the smaller the consensus-shaped surface. `math.h`'s DCA/ERR functions are deleted, not kept
dormant. Cost: none to the proposal; a deviation from the prototype and DigiDollar, §10.2–10.3.

### V21. Supply cap as a share of issued YEC

**Decision:** `issuedZat(H) = Σ_{h ≤ H} GetBlockSubsidy(h)` is a pure function of height
(`ref/ycash/src/main.cpp:2067-2104`; no chain state, no time) and is kept cumulatively in
`Snapshots`, seeded at `startHeight` by a one-time loop. The cap is `SUPPLY_CAP_BPS = 1,500`
(15 %) of `issuedZat × P_mint`. Cost: one `arith_uint256` product per mint.

### V22. Naming

Unchanged: Yellowback is the system, YED the unit (the test: swappable for "dollars" → YED, for "the
system" → Yellowback), `yed_*` the RPC prefix (the ticker as namespace, as Zcash's `z_`), namespace
`yellowback`, directory `src/yellowback/`, config prefix `-yellowback…`. New names:
the miner-paid fee is the **enforcement fee** (never "miner fee", which collides with the network
fee `YELLOWBACK_FEE` = 1,000 zat); the coinbase data is the **tag** (magic `YED!`); the price
medians are `P_fast`/`P_mid`/`P_slow`/`P_mint`/`P_claim` in prose and `pFast`… in code; the
external price process is the **quote agent** (`yellowback-quote`). The fork branches are
`feature/yellowback-sf` ("sf" = soft fork) in both repositories — already created from the prototype
tips on 2026-09-10; `feature/digidollar` is kept as the record of the federation prototype and is never deleted.

### V23. Payload version 2

**Decision:** the payload header's version byte becomes `0x02`; prototype nodes ignore it by the
forward-compatibility rule (an unknown version or type is non-Yellowback: ignored, never mis-parsed —
§3.3) and v2 nodes ignore version 1. Since the prototype never reached a
public network there is nothing to migrate; the bump makes the incompatibility explicit and lets
test vectors be regenerated without ambiguity. Type `0x10` (PRICE) is retired and reserved.

### V24. Wallet redemption in one step; a claim RPC

**Decision:** `yed_redeem <vault> [to]` builds, signs the owner path and every YED input, and
commits — no pending record, no deadline, no `yed_submitredeem`/`yed_abortredeem`/`yed_cosignredeem`.
`yed_claim <vault> [to]` builds the claim-path spend from the wallet's YED and commits. Both refuse
to build unless `MempoolCheck` — the MP-1 predicate, `EvaluateBlock` over a one-transaction
pseudo-block (K7) — passes, so a user never broadcasts a transaction an enforcing miner would reject. The YecWallet redemption
wizard (568 lines) is replaced by a confirmation dialog; a Claim page is added (§4.8).

### V25. Testing pools on one machine

**Decision:** a "pool" in every functional test is a regtest node started with
`-yellowback -yellowbackpayoutaddress=<its address>` whose quote is set by `yed_setquote`; it
mines with `generate`, which goes through `CreateNewBlock` + `IncrementExtraNonce` and therefore
emits the tag (V5). Hashpower shares are simulated by which node mines which block. A stock miner
is a node without `-yellowback`. Regtest windows shrink (§3.1) so activation takes 128 blocks. No
pool software is needed to test the protocol; the pool kit (§5) is tested against real pool
software on testnet (Phase 9).

### V26. Pool software integration surface

**Decision:** `getblocktemplate` gains three things, **all gated on `g_yellowback`** so that a
node without the flag returns v4.5.0's shape (N10; `yellowback_stockparity.py` proves it):
`coinbaseaux.flags` is emitted whenever the module is on (today it is in an unreachable branch
because `coinbasetxn` is hard-coded true, `ref/ycash/src/rpc/mining.cpp:504-505,762-767`),
`"coinbase/append"` is added to `mutable` (`:747-752`), and a `yellowback` object reports the
template's tag and the node's state (fields in §4.4). A pool that reuses `coinbasetxn` gets the tag for free; a pool
that assembles its own coinbase appends `coinbaseaux.flags` (the BIP 22 convention that
node-stratum-pool-lineage software already implements for Bitcoin-family chains — to be
verified per stack in Phase 7, §12 Q9; the per-carrier operator steps are §5). Cost: ≈ 20 lines
in `rpc/mining.cpp`.

---

## 3. Yellowback v2 protocol (normative)

Everything in this section is deterministic given the block sequence and the parameters. Words
in **bold caps** are rule identifiers used by the test plan. Every rule is written out here,
including those carried over from the federation prototype (marked *carried over*), so that this
section alone is the wording of record: Phase 0 publishes it verbatim as `../spec/yellowback-spec.md`
(extracted from this plan by `scripts/extract-spec.sh` — `make spec` — so every rule identifier
has one citable home and `make status` fails when the copy is stale, N29) and points
`../spec/README.md` at it (M15).

### 3.1 Units, constants and parameters

Units: `CENT` (YED amounts are integer US cents), `MICRO_USD` (prices are integer µUSD per
YEC; `1,000,000 = $1.00`), `COIN = 10⁸` zat, basis points (`10,000 bps = 100 %`) for every ratio.
`BLOCKS_PER_HOUR = 48`, `BLOCKS_PER_DAY = 1,152`, `BLOCKS_PER_YEAR = 420,480` (75-second spacing,
`ref/ycash/src/consensus/params.h:212`).

| Name | Mainnet / testnet | Regtest | Notes |
|---|---|---|---|
| `START_HEIGHT` | per network (params) | `-yellowbackstartheight` | first height whose tags count; nothing below it is read; **≥ 1** (the genesis coinbase has no height push, M2) |
| `TAG_MAGIC` / `TAG_VERSION` / `TAG_SIZE` | `59 45 44 21` (`YED!`) / `1` / 36 | same | §3.2 |
| `PRICE_MIN` / `PRICE_MAX` | 100 / 100,000,000 µUSD | same | as DigiByte (`primitives/oracle.h:23-24`) |
| `P_FAST_WINDOW` / `P_MID_WINDOW` / `P_SLOW_WINDOW` | 96 / 576 / 2,016 | 8 / 24 / 64 | proposal §4.2 |
| `WINDOW_MIN_FILL` | fast window `⌈W/2⌉` = 48; mid and slow windows `⌈2W/3⌉` = 384 / 1,344 quote tags | 4 / 16 / 43 | V16, L9: `pClaim` reads the mid and slow windows only; `pMint` needs all three, so a mint also needs two-thirds fill on the mid and slow windows (accepted) |
| `REF_WINDOW` | 40 | 40 | = `DEFAULT_POST_BLOSSOM_TX_EXPIRY_DELTA` (`main.h:78-79`), protocol constant |
| `REF_LAG` | 2 (wallet-side, `-yellowbackmintlag`, 0..36 — the bound is the mempool's expiring-soon rule, §3.5) | 2 | the mint survives any reorg shorter than `REF_LAG + 1` blocks (V11) |
| `SIGNAL_WINDOW` / `ACTIVATION_THRESHOLD` / `PARTICIPATION_FLOOR` / `ACTIVATION_DELAY` | 2,016 / 1,512 (75 %) / 1,210 (60 %) / 2,016 | 64 / 48 / 39 / 64 | proposal §7; ACT-2..4 (the mint halt) |
| `ENFORCEMENT_FLOOR` / `ENFORCEMENT_RESUME` | 1,008 (50 %) / 1,210 (60 %) | 32 / 39 | L3; ACT-6 (block rejection suspends / resumes) |
| `VALVE_BLOCKS` | 6 | 6 | L7; ACT-7 (work valve): a chain rooted at a block this node rejected that carries this many blocks of work above the node's tip switches enforcement off for the session; the same bound is BLK-2's catch-up suppression (L11: a block the network has already built this much on is accepted, not rejected); **node-local**, never a state input |
| `VALVE_NOTE_CAP` | 64 | 64 | P2; the most headers the odometer notes per rejected root; a header outside the consensus difficulty loosening of its parent (`nPowMaxAdjustDown`, `chainparams.cpp:104`) is never noted; **node-local** |
| `ENFORCE_UNTIL_HEIGHT` | per network, per parameter set: ≈ `startHeight + BLOCKS_PER_YEAR` (420,480) and never beyond the next known Ycash network-upgrade activation height | `-yellowbackenforceuntil` (regtest only; 0 = none) | L8; ACT-5 (enforcement sunset): past it the node tags and evaluates but never rejects; a parameter change ships as a set starting at or after the previous set's sunset |
| `ABANDON_BLOCKS` | 4,032 (= 2 · `SIGNAL_WINDOW`) | 128 | L10, L12; the abandonment predicate `yed_sweep` builds under (§4.6): `ENFORCEMENT` set continuously for this many blocks — the only clause, so every release answers alike; a sunset with no successor reaches it through the vanished signal bits |
| `N_REG` | 576 | 24 | proposal §6.2; **informational** (REG-1, `yed_listminers`) |
| `N_PENALTY` | 288 | 12 | proposal §6.2; **wallet default** (REG-2, FEE-W; node override `-yellowbackpayeepenaltyblocks`, L6) |
| `PEER_LAG` / `PEER_MIN` | 10 / 5 | 4 / 3 | V18; **judgement (state)**: the window is `[t − PEER_LAG, t + PEER_LAG − 1]`, 2·`PEER_LAG` blocks |
| `DEVIATION_BPS` / `ACCURACY_BAND_BPS` | 1,000 / 300 | 1,000 / 300 | proposal §4.4; **judgement (state)** (REG-4) |
| `ACCURACY_WINDOW` | 576 | 24 | proposal §4.4; **wallet default** (REG-3, FEE-W; node override `-yellowbackpayeeaccuracywindow`, L6) |
| `PAYEE_TILT_BPS` | 10,000 | same | FEE-W weight `10⁴ + PAYEE_TILT_BPS · accuracyBps / 10⁴` (1×–2× at the default, K8); **wallet default** (node override `-yellowbackpayeetiltbps`, L6) |
| `PAYEE_WINDOW` | 100 | 10 | proposal §6.1 |
| `FEE_MIN` / `FEE_BPS` | 50,000,000 zat (0.5 YEC) / 25 | same | enforcement fee, V10 |
| `GRACE` | 34,560 (30 d) | 24 | proposal §5.5 |
| `CLAIM_THRESHOLD_BPS` | 11,000 (110 %) | same | proposal §5.5 |
| `SUPPLY_CAP_BPS` | 1,500 (15 % of market cap) | `-yellowbacksupplycapbps` (0 = none) | proposal §5.6 |
| `GLOBAL_RATIO_HALT_BPS` | 25,000 (250 %) | same | proposal §5.6 |
| `DIVERGENCE_BPS` | 2,000 (20 %) | same | proposal §5.6 |
| Term class A: lock range / base ratio | `[34,560, 103,680]` blocks / 50,000 bps | `[48, 96]` / 50,000 | 30–90 days |
| Term class B | `(103,680, 420,480]` / 40,000 bps | `(96, 144]` / 40,000 | 90–365 days |
| Term class C | `(420,480, 2,102,400]` / 30,000 bps | `(144, 240]` / 30,000 | 1–5 years (`MAX_LOCK` = 5 y, V19) |
| `VOL_WINDOW` / `VOL_STEP` / `VOL_PERIODS_PER_YEAR` | 2,016 / 48 / 8,760 | 64 / 8 / 8,760 | V17; the annualisation is an independent parameter, deliberately equal on every network (K13) |
| `SIGMA_REF_BPS` / `SIGMA_MULT_MAX_BPS` | 10,000 (100 %) / 30,000 (3×) | `-yellowbacksigmaref` (0 = multiplier fixed at 1) / 30,000 | V17 |
| `MIN_MINT` / `MAX_MINT` | 10,000 / 1,000,000 cents | same | $100 / $10,000 (DigiByte: $100 / $100,000; a parameter, not protocol, because Ycash's liquidity is a small fraction of DigiByte's) |
| `MIN_OUTPUT` / `MAX_OUTPUT` | 100 / 10,000,000 cents | same | unchanged |
| `TOKEN_VALUE` | 10,000 zat | same | unchanged |
| `YELLOWBACK_FEE` | 1,000 zat (network fee; `-yellowbackfee` may not go below `DEFAULT_FEE` because ZIP-401's low-fee penalty would otherwise evict the transaction, `ref/ycash/src/mempool_limit.cpp:151-157`) | same | unchanged; distinct from the enforcement fee |
| `MAX_PAYLOAD` | 80 bytes | same | unchanged |
| `UNDO_KEEP` | 4,096 blocks | 4,096 | V2 |

Per-network parameters (`src/yellowback/params.cpp`): `startHeight`, address version bytes (unchanged:
Base58Check(version ‖ 20-byte key hash) with `0x1F 0xE4` mainnet `ye…`, `0x20 0x07` testnet `yt…`,
`0x20 0x02` regtest `yr…`, decoding to an ordinary P2PKH destination; implemented in
`src/yellowback/address.cpp`, no `chainparams.cpp` edit), the table above. **Parameter versioning (K10):** every value in the
table that a rule in §3.7–3.9 reads is consensus-shaped among enforcing miners — not only the
rows RED-3/RED-4 read directly, because any difference in ratios, caps, halts or activation
changes which vaults are ACTIVE and therefore what BLK-1 rejects. The exceptions are the rows
marked **informational** and **wallet default** (L6). A change ships in a release as a new
parameter set keyed by a start height, `EvaluateBlock` selects the set by `H`, and **the new set's
start height must lie above every height any released node has already validated**, so stored
`Rejected` marks and a rebuilt index can never disagree (M12) — and, stronger, **at or after the
previous set's `ENFORCE_UNTIL_HEIGHT`** (L8), so no released node still enforces the old set when
the new one starts: every set carries its sunset, about twelve months of blocks past its start
and never beyond the next known Ycash network-upgrade activation height, and past it a node keeps
tagging and evaluating but rejects nothing (ACT-5). Two releases with different sets can therefore
never both be enforcing at one height (§8.2). No value a rule reads comes from configuration,
with one deliberate exception: regtest takes `startHeight` from `-yellowbackstartheight`
(required) and the three regtest-only overrides (`-yellowbacksigmaref`, `-yellowbacksupplycapbps`,
`-yellowbackenforceuntil`); all four are reported in `yed_getinfo.params` and included in the
state-hash preimage (§3.6 *State hash*) so mismatched test nodes fail loudly rather than diverge
silently (M13). Every other regtest value in the table is compiled into `RegtestParams`; no flag
changes it. The test-only `-yellowbacktestfault` (Phase 3; `storage:<check|commit|undo>[:<height>]`
or `template`, §4.5) injects faults and reads nothing a rule reads. The genesis anchor and roster
parameters of the federation prototype are gone.

### 3.2 The coinbase tag

A tag is 36 bytes, all integers little-endian, carried in the coinbase `scriptSig` as a single
direct push (`0x24` followed by the 36 bytes) somewhere **after** the BIP34 height push:

| Field | Size | Meaning |
|---|---|---|
| `magic` | 4 | `59 45 44 21` (`YED!`) |
| `version` | 1 | `1` |
| `flags` | 1 | bit 0 = activation signal; bits 1–7 must be zero (reserved) |
| `priceMicroUsd` | 8 | YEC/USD quote in µUSD; `0` = signal-only (V9) |
| `sourceMask` | 2 | bitfield of price sources (Appendix A of the proposal); informational |
| `payoutKey` | 20 | Hash160 of the miner's enforcement-fee key (P2PKH) |

**TAG-1 (location).** The reader skips the height prefix (`CScript() << nHeight`, exactly what
`ContextualCheckBlock` expects, `ref/ycash/src/main.cpp:4477`) and scans the remaining bytes for
the first occurrence of the 5-byte pattern `24 59 45 44 21` (the direct-push opcode followed by
the magic; the magic without its push opcode is not a tag, P10); the 32 bytes that follow the
pattern are the tag body. If fewer than 32 bytes follow, or no occurrence exists, the block has no
tag. The scan is byte-level, never a script parse (pools write raw extranonce bytes, V4).
**TAG-2 (validity).** A tag is valid iff `version == 1`, `flags & 0xFE == 0`, and
`priceMicroUsd == 0 ∨ PRICE_MIN ≤ priceMicroUsd ≤ PRICE_MAX`. An invalid tag is no tag.
**TAG-3 (kinds).** A valid tag with `priceMicroUsd > 0` is a **quote tag**: it records a quote,
registers `payoutKey` (REG-1) and counts toward every window. A valid tag with
`priceMicroUsd == 0` is a **signal-only tag**: it counts for ACT-1..6 only. Any 20 bytes is a
valid `payoutKey` (a Hash160 needs no validation; an unspendable key only sends the payer's fee
to nobody), and whether it matches the coinbase output's key is irrelevant to every rule (M13).
**TAG-4 (never consensus).** No property of a coinbase — tag present, absent, valid or not — makes
a block invalid under any rule in this plan.
**TAG-5 (one per block).** The **first** occurrence of the 5-byte pattern after the height prefix
decides: if fewer than 32 bytes follow it, or TAG-2 fails on them, the block has no tag; the scan
never continues past the first occurrence (M2). Later occurrences are ignored.

`Tags[H]` is written for every block `≥ START_HEIGHT` with a valid tag.

### 3.3 Payload encoding

*Carried over from the prototype, restated (M15).* The payload is the data of the transaction's **only** `OP_RETURN`
output, which must be exactly `OP_RETURN <one push of 4..80 bytes>` (`Solver` accepts any
push-only tail as `TX_NULL_DATA`, `ref/ycash/src/script/standard.cpp:102`, so the shape rule is
ours). A transaction with **more than one** `OP_RETURN` output (non-standard, but a miner
may include it), or whose `OP_RETURN` does not have this shape or does not begin with the magic,
is a **non-Yellowback** transaction: its outputs create nothing and its inputs are still processed
by IN-1..3. All multi-byte integers are fixed-width little-endian (no `CompactSize`, no `VARINT`:
no canonical-form question and no coupling to `ReadCompactSize`'s rules or `MAX_SIZE`); the reader is bounds-checked and never throws. **Malformed** (bad magic, version or type;
short or long body; trailing bytes; `vout` out of range; duplicate `vout`; `vout` pointing at the
`OP_RETURN`; `cents == 0`) ⇒ non-Yellowback; **unknown `type`** ⇒ non-Yellowback (the
forward-compatibility rule: a v2 node ignores version 1 and every later version, V23). **Type
namespace:** `0x01–0x0F` are YED transaction types, `0x10–0x1F` are reserved (the federation
prototype's types; `0x10` retired), `0x20–0xFF` are reserved for other assets or payload families,
and a transaction carrying a payload of one asset or version must never spend a token output of
another — a v2 node applies IN-1..3 to that input and records a burn. Header `magic "YB" (0x59
0x42) ‖ version 0x02 ‖ type`:

| Type | Body | Size incl. 4-byte header |
|---|---|---|
| `0x01` MINT | `termClass u8` (`0`=A, `1`=B, `2`=C), `cents u32`, `lockHeight u32`, `refHeight u32`, `ownerPubKey 33 B`, `feeVout u8` | 51 |
| `0x02` TRANSFER | `count u8`, `count ×` (`vout u8`, `cents u32`) | 5 + 5·count → count ≤ 15 |
| `0x03` REDEEM | `refHeight u32`, `feeVout u8`, `count u8`, `count ×` (`vout u8`, `cents u32`) | 10 + 5·count → count ≤ 14 |
| `0x10` | retired (the prototype's PRICE type); reserved | — |

`feeVout = 0xFF` means "no enforcement-fee output"; when FEE-0 applies `feeVout` is ignored
whatever it says (K11). REDEEM is the payload for both the owner path and the claim path; the path
is read from the scriptSig (§3.4).

### 3.4 Scripts

**Vault script** (redeem script of the P2SH collateral output; `lockHeight` and `claimHeight =
lockHeight + GRACE` pushed as minimal `CScriptNum`, both `< LOCKTIME_THRESHOLD`):

```
OP_IF
  <lockHeight> OP_CHECKLOCKTIMEVERIFY OP_DROP <ownerPubKey> OP_CHECKSIG
OP_ELSE
  <claimHeight> OP_CHECKLOCKTIMEVERIFY OP_DROP OP_TRUE
OP_ENDIF
```

**Owner-path scriptSig:** `<ownerSig> OP_1 <vaultScript>`. **Claim-path scriptSig:**
`OP_0 <vaultScript>`. The spending transaction sets `nLockTime = lockHeight` (owner) or
`= claimHeight` (claim), `vin[0].nSequence = 0xFFFFFFFE`, and `nExpiryHeight = refHeight +
REF_WINDOW`. `IsFinalTx`/`CheckFinalTx` admit it once the tip is at or above `nLockTime`
(`ref/ycash/src/main.cpp:721-731`, `:746-775`); CLTV is enforced in every block
(`SCRIPT_VERIFY_CHECKLOCKTIMEVERIFY` in `ConnectBlock`'s flags, `main.cpp:2931`). Sighash for the
owner signature: `SignatureHash(vaultScript, tx, 0, SIGHASH_ALL, vaultValue, branchId)` with
`branchId = CurrentEpochBranchId(chainActive.Height() + 1)` (unchanged from the prototype).
**Path detection (used by RED-4):** the selector is the push immediately before the redeem-script
push in the scriptSig, and the path is `CastToBool(selector)` exactly as `OP_IF` evaluates it
(consensus verifies vaults with `P2SH | CLTV` only, `ref/ycash/src/main.cpp:2931`, so `OP_2` or a
non-minimal `1` is a valid owner selector and `0x80` a valid claim selector, K4). A `vin[0].scriptSig`
that is not push-only or has fewer than two pushes **fails RED-1**: consensus rejects such a spend
anyway (`OP_IF` on an empty stack), but `EvaluateBlock` also runs on unverified transactions in
`MempoolCheck`, TPL-1 and `yed_getblockverdict` and must return a verdict (M1). The wallet always
emits `OP_1`/`OP_0`; the strict template policy declines anything else (TPL-2).
Script size 51 bytes (3-byte height pushes) or 53 (4-byte); one sigop; standard under
`STANDARD_SCRIPT_VERIFY_FLAGS` and `AreInputsStandard` (unit-tested directly, because regtest sets
`fRequireStandard = false` and functional tests never execute the standardness checks).

**Token output** and **enforcement-fee output**: P2PKH. The fee output pays `P2PKH(payeeKey)`
(§3.7) and any `nValue ≥ feeZat`.

### 3.5 Transaction templates (what the wallet builds)

**MINT** (`yed_mint <cents> <lockBlocks> [from]`; the class follows from `lockBlocks`, V19), `R = refHeight = indexTip − REF_LAG`:

| Index | Output | Value |
|---|---|---|
| vin[*] | confirmed transparent YEC inputs (never YED, never vaults), or none when funded from `ys1…` (Sapling-funded mint, §4.6) | |
| vout[0] | P2SH(vaultScript(lockHeight, owner, lockHeight + GRACE)) | `requiredZat(cents, class, Snapshots[R])` rounded up to 1,000 zat |
| vout[1] | P2PKH(owner's fresh key) — the minted cents | `TOKEN_VALUE` |
| vout[2] | `OP_RETURN` MINT payload (`refHeight = R`, `feeVout = 3` or `0xFF`) | 0 |
| vout[3] | P2PKH(payee(R, ownerPubKey)) — enforcement fee (absent under FEE-0) | `feeZat(vout[0].nValue)` |
| vout[4] | YEC change (transparent funding only) | |

`lockHeight = R + lockBlocks` with `lockBlocks` inside the chosen class; `nExpiryHeight = R +
REF_WINDOW`. Every confirmation height `H ∈ [indexTip + 1, R + 40]` satisfies MINT-2's
`H − REF_WINDOW ≤ R ≤ H − 1` (`R = indexTip − REF_LAG`, so the earliest confirmation height
`indexTip + 1` gives `H − R = REF_LAG + 1` and the latest, `R + 40`, gives exactly `H − REF_WINDOW
= R`). Why `REF_LAG ≤ 36`: MINT-2's window alone allows `REF_LAG ≤ 39`, but the mempool refuses a
transaction whose `nExpiryHeight < nextHeight + 3` (`TX_EXPIRING_SOON_THRESHOLD`,
`ref/ycash/src/main.h:81`), and `R + 40 ≥ indexTip + 4` needs `REF_LAG ≤ 36`.

**TRANSFER** (`yed_send`, `yed_sendmany`), *carried over*: YED inputs (confirmed only) plus YEC fee inputs
(confirmed only — `AvailableCoins(..., nMinDepth = 1)`, since the wallet's own 0-conf and expired outputs
are otherwise selectable and a transaction chained on them may never confirm); outputs: one `TOKEN_VALUE` P2PKH per recipient, one for YED change, the
`OP_RETURN` TRANSFER payload assigning cents to those vouts, YEC change.

**REDEEM, owner path** (`yed_redeem <vaultTxid> [to]`): `vin[0]` = vault (owner scriptSig);
`vin[1..]` = confirmed YED inputs totalling ≥ `mintedCents` (no YEC inputs: every YED input carries
`TOKEN_VALUE` and the vault carries the collateral, so the fee comes from the transaction's own inputs). Outputs:
collateral to the destination (`vaultValue + surplus token value − YELLOWBACK_FEE − feeZat −
TOKEN_VALUE × YED-change outputs`), the enforcement-fee output (`P2PKH(payee(R, vaultOutpoint))`),
optional YED change (`TOKEN_VALUE`) and the REDEEM payload (`count = 0` allowed). A `ys1…`
destination is a single Sapling output (`TransactionBuilder` with the vault and YED
inputs unsigned, signed after `Build()`); in that shape the transparent outputs are YED change (if
any) at `vout[0]`, then the payload, then the fee output — `feeVout` names it wherever it lands
(`vout[2]` with change, `vout[1]` without) — and the fee output is always transparent (M13).

**CLAIM** (`yed_claim <vaultTxid> [to]`): identical to REDEEM with the claim-path scriptSig,
`nLockTime = claimHeight`, YED inputs from the claimant's wallet, collateral to the claimant.

**SWEEP** (`yed_sweep <vaultTxid> <"I understand this leaves YED unbacked"> [to]`, L10): the
owner-path spend with **no burn and no fee** — `vin[0]` = vault (owner scriptSig), no YED inputs,
no payload, one output paying `vaultValue − YELLOWBACK_FEE` to the destination (`ys1…` allowed,
same builder shape as REDEEM). It is by construction a vault spend that fails RED-1 (no REDEEM
payload), so every enforcing miner refuses it (MP-1, TPL-1) and an enforcing node that applies it
records the vault `CLOSED, unbacked = true` (IN-2); the wallet builds it **only** under the
abandonment predicate of §4.6, never gated on the node's own `-yellowbackenforce`. Under that
same predicate MP-1 and TPL-1/2 stand down (L13), so the owner's own node admits and relays the
sweep and any pool still running the module mines it; `yed_sweep` also returns the raw `hex`. The
wallet reports it as `yed_listtransactions.type = "sweep"` (the index's `TxLog.type` is `REDEEM`
with verdict `vault-spend-malformed`, §3.8).

**VOID RELEASE** (`yed_redeem <vaultTxid> [to]` on a vault whose status is VOID, L14): the
owner-path spend of a vault that never carried a debt — `vin[0]` = vault (owner scriptSig),
`nLockTime = lockHeight`, no YED inputs, no payload, no fee output, one output paying
`vaultValue − YELLOWBACK_FEE` to the destination. It is an ordinary spend: IN-2 closes the vault
(`CLOSED`, `unbacked = false`, nothing burned) and no rule of §3.8–3.9 reads it (K3). The wallet
builds it at or past `lockHeight`, refuses before (`vault-locked`), and returns `burnedCents = 0`.

### 3.6 State

```
Tip          { height, blockHash, schemaVersion = 2, network }
Tags         height → { payoutKey, priceMicroUsd, signal, sourceMask }        (valid tags ≥ START_HEIGHT)
Judgements   height → { evaluated, inBand, penalized }                       (for the tag at that height; written at height + PEER_LAG)
Activation   { status ∈ {SIGNALING, LOCKED_IN, ACTIVE}, lockInHeight, activateHeight }
Vaults       outpoint → { ownerPubKey, termClass, lockHeight, claimHeight, collateralZat,
                          mintedCents, mintHeight, refHeight, status ∈ {ACTIVE, VOID, CLOSED, CLAIMED},
                          voidReason, closeHeight, closingTxid, burnedCents, feePaidZat, unbacked }
Tokens       outpoint → { cents, nValue, scriptPubKey, height }              (carried over)
TxLog        txid → { height, type, path, verdict, yedIn, yedOut, burned, feeZat, payee,
                      assigned[], spentTokens[], closedVaults[] }             (carried over, plus fee fields; history RPCs
                                                                               read it because IN-1 erases spent Tokens and
                                                                               the plan does not require -txindex; only for
                                                                               transactions that create or spend Tokens/Vaults, N7)
Totals       { supplyCents, collateralZat, activeVaults, voidVaults, closedVaults, claimedVaults, unbackedCents }
Snapshots    height → { blockHash, tagged, quote, signalCount, activation, pFast, pMid, pSlow,
                        pMint, pClaim, sigmaMultBps, issuedZat, supplyCents, collateralZat,
                        globalRatioBps, haltMask }
Rejected     blockHash → { height, reason }                                  (blocks this node refused, V13; written sync)
Undo         blockHash → inverse operations                                  (carried over)
Params       { startHeight, sigmaRefBps, supplyCapBps, enforceUntil }       (one record, written at creation; N18)
```

`voidReason` is the verdict string of the MINT rule that failed (§4.2a), empty for an ACTIVE
vault; `spentTokens[]` lists the `Tokens` outpoints a transaction consumed (IN-1), which
`yed_listtransactions` filters on (N21).

`haltMask` bits: `NOT_ACTIVE`, `NO_PRICE`, `PARTICIPATION`, `GLOBAL_RATIO`, `DIVERGENCE`,
`ENFORCEMENT` (ACT-6; implies `PARTICIPATION`). `Snapshots` are written for every block
`≥ START_HEIGHT` (≈ 120 bytes each). **Encoding of undefined values (M1):** an undefined price
(`pFast`… `pClaim`) or `globalRatioBps` is stored as `0` (`PRICE_MIN = 100`, so `0` is never a
value); `sigmaMultBps` is always defined (SIGMA-1 yields the cap). `Activation` is the carried
state that ACT-2/3 read and update; `Snapshots[H].activation` is its copy at `H`; UNDO restores
both. **Virtual snapshot below `START_HEIGHT`:** wherever a rule reads `Snapshots[h]` for
`h < START_HEIGHT` it sees `activation = {SIGNALING, 0, 0}`, `haltMask = NOT_ACTIVE | NO_PRICE`,
every price undefined, and enforcement is off at any `H` whose `Snapshots[H − 1]` is virtual.

**State hash (N18).** `yed_getstatehash` is `SHA256` over the concatenation, in this order, of
the canonical serialisation of `Tip`; every `Tags` record in ascending height; every `Judgements`
record in ascending height; `Activation`; every `Vaults` record in ascending outpoint order
(`txid` bytes, then `vout`); every `Tokens` record likewise; `Totals`; every `Snapshots` record
in ascending height; and the `Params` record. Canonical serialisation is the LevelDB value
encoding: fixed-width little-endian integers, `u8` for booleans and for the `status`/`termClass`
enumerations in declaration order, `uint160`/`uint256` as raw bytes, `voidReason` as a
length-prefixed UTF-8 string, undefined prices and ratios as `0` (above); each record is preceded
by its key. **Excluded:** `TxLog` (history; no rule reads it), `Rejected` (node-local, V13; two
enforcing nodes that rejected different blocks must still agree), `Undo`. Key prefixes:
`Q<u32 height>` Tags, `J<u32 height>` Judgements, `C` Activation, `X<blockhash>` Rejected, `P`
Params, `U<blockhash>` Undo, the prototype's for `Vaults`/`Tokens`/`TxLog`/`Totals`/`Snapshots`;
removed: `A` (anchor), `Rc`/`R<u32>` (roster), the `P<u32>` price table, `O`. The unit test
`statehash_golden_vector` pins the hex of a fixed synthetic sequence (regtest params `{1, 0, 0,
0}`), and `yellowback_model.py` recomputes it from `yed_gethistory` (§7).

### 3.7 Derived quantities (integer, `arith_uint256`)

**Conventions (M1).** Every quantity is a non-negative integer in `arith_uint256` unless stated;
every division rounds toward zero (floor) unless written `⌈ ⌉`; `isqrt` is the floor square root;
`lowerMedian(S)` of a non-empty multiset of `n` values sorted ascending is the element at 0-based
index `⌊(n − 1)/2⌋` (for even `n`, the smaller of the two middle values); height comparisons are
evaluated in signed 64-bit arithmetic. A quantity is **undefined** when any input to it is
undefined; §3.8 says what an undefined input does to a rule.

**Medians.** `median(W, H)` = `lowerMedian` of `Tags[h].priceMicroUsd` over quote tags with
`h ∈ (H − W, H]`; **undefined** if fewer than `WINDOW_MIN_FILL(W)` quote tags exist in that range
(PRICE-1): `⌈W/2⌉` for `P_FAST_WINDOW`, `⌈2W/3⌉` for `P_MID_WINDOW` and `P_SLOW_WINDOW` (L9).
`pFast = median(P_FAST_WINDOW, H)`, `pMid`, `pSlow` likewise.
**PRICE-2.** `pMint = min(pFast, pMid, pSlow)`, undefined if any is; `pClaim = max(pMid, pSlow)`,
undefined if either is.

**Activation.** `signalCount(H)` = number of valid tags (either kind) with the signal bit in
`(H − SIGNAL_WINDOW, H]`.

**Volatility multiplier (SIGMA-1).** Let `s_0` be the `pFast` computed at this SNAP for `H` and
`s_k = Snapshots[H − k·VOL_STEP].pFast` for `k = 1 … VOL_WINDOW/VOL_STEP` (43 samples on mainnet,
`n = 42` returns); a sample below `START_HEIGHT` is undefined, and if any sample is undefined the
multiplier is `SIGMA_MULT_MAX_BPS` (K12). Returns `r_k = |s_k − s_{k+1}| · 10⁴ / s_{k+1}`, computed
unsigned (only `r_k²` is used, so the sign is immaterial, M1); `var = Σ r_k² / n`; `sigmaAnnualBps = isqrt(var · VOL_PERIODS_PER_YEAR)`;
`sigmaMultBps = clamp(sigmaAnnualBps · 10⁴ / SIGMA_REF_BPS, 10,000, SIGMA_MULT_MAX_BPS)`.
Regtest with `SIGMA_REF_BPS = 0` fixes the multiplier at `10,000`.

**Minimum ratio.** `minRatioBps(class, S) = baseRatioBps(class) · S.sigmaMultBps / 10⁴`.

**Required collateral.** `requiredZat(cents, class, S) = ⌈cents · minRatioBps(class, S) · COIN /
S.pMint⌉` (derivation: `cents/100` dollars × `minRatioBps/10⁴` ÷ `pMint/10⁶` dollars per YEC,
× `COIN`; the powers of ten cancel). Check: $100 at 300 % and $0.05/YEC →
`10,000 · 30,000 · 10⁸ / 50,000 = 6·10¹¹` zat = 6,000 YEC. Worst case is class A at the 3× cap:
`10⁶ · 150,000 · 10⁸ = 1.5·10¹⁹` before the division, above the `int64` limit, hence
`arith_uint256`; and at `PRICE_MIN` the quotient (`1.5·10¹⁷` zat) exceeds `MAX_MONEY`, so
`RequiredCollateralRounded` reports "unsatisfiable" rather than a number (K14).

**Issuance.** `issuedZat(H) = Σ_{h ≤ H} GetBlockSubsidy(h)`, carried in `Snapshots` (V21).
**Market cap in cents.** `capCents(S) = issuedZat · pMint / (COIN · 10⁴)`.
**Supply cap.** `supplyCapCents(S) = capCents(S) · SUPPLY_CAP_BPS / 10⁴` (0 = none on regtest).
**Global ratio.** `globalRatioBps = collateralZat · pMint / (COIN · supplyCents)` when
`supplyCents > 0`, else "no supply" (never halts).
**Claimable.** vault `v` is underwater at snapshot `S` iff
`v.collateralZat · S.pClaim < v.mintedCents · CLAIM_THRESHOLD_BPS · COIN` (derivation: collateral
value in cents is `collateralZat · pClaim / (COIN · 10⁴)`, the threshold is `mintedCents ·
CLAIM_THRESHOLD_BPS / 10⁴`; multiply both sides by `COIN · 10⁴`). Check: 6,000 YEC backing $100 is
underwater once `pClaim ≤ 18,333 µUSD` (`6·10¹¹ · p < 10⁴ · 11,000 · 10⁸`). If `S.pClaim` is
undefined the vault is **not** underwater (M1).

**Enforcement fee (FEE-1).** `feeZat(collateralZat) = max(FEE_MIN, collateralZat · FEE_BPS / 10⁴)`.

**Registration (REG-1).** `registered(key, R)` iff some quote tag with `payoutKey = key` exists in
`(R − N_REG, R]` (informational: `yed_listminers`).
**Penalty (REG-2)** — informational and wallet policy only, never read by a validity rule (L1);
`N_PENALTY` is the node's configured value (default from §3.1, L6). `penalized(key, R)` iff some
quote tag at height `t` with `payoutKey = key`
has `Judgements[t].penalized` and `t + PEER_LAG < R ≤ t + PEER_LAG + N_PENALTY`.
**Accuracy (REG-3)** — informational and wallet policy only (L1); `ACCURACY_WINDOW` likewise
configurable (L6). Over `t ∈ (R − PEER_LAG − ACCURACY_WINDOW, R − PEER_LAG]`: `quoted(key, R)`
= number of quote tags of `key` with `Judgements[t].evaluated`; `inBand(key, R)` = those with
`Judgements[t].inBand`. `accuracyBps(key, R) = 10⁴ · inBand / quoted`, or `0` if `quoted = 0`.
**Judgement (REG-4)** — shared state, release-versioned constants only (L6) — performed when block
`H = t + PEER_LAG` is applied, for the quote tag at
`t`: `peers` = the quote tags in `[t − PEER_LAG, t + PEER_LAG − 1]` other than `t`; if
`|peers| < PEER_MIN` the tag is not evaluated; else `m = lowerMedian(peers)`,
`dev = |price_t − m| · 10⁴ / m`, `inBand = dev ≤ ACCURACY_BAND_BPS`, `penalized = dev >
DEVIATION_BPS`, `evaluated = true`.

**Eligible payees (FEE-2).** `E(R)` = the set of `payoutKey`s of the quote tags at heights
`h ∈ (R − PAYEE_WINDOW, R]`. If `E(R)` is empty ⇒ **FEE-0** (no fee, `feeVout` ignored). A fee
output is valid iff it pays `P2PKH(k)` for some `k ∈ E(R)` with `nValue ≥ feeZat`. Nothing else
about the payee is a rule (L1).
**Wallet default (FEE-W, policy).** Candidates = the quote tags at `h ∈ (R − PAYEE_WINDOW, R]`
whose key is not `penalized(key, R)`, in height order, weight `w_h = 10⁴ + PAYEE_TILT_BPS ·
accuracyBps(key_h, R) / 10⁴` (K8; 1×–2× at the default tilt); `seed = SHA256(blockHash(R) ‖
selector)` as a little-endian `uint64`, `pick = seed mod Σ w_h`, payee = the first `h` whose
cumulative weight exceeds `pick`; `selector` = the 33-byte owner key (MINT) or the 36-byte
serialised vault outpoint (REDEEM). If every candidate is penalised, fall back to all of `E(R)`
with equal weights. The result is **`payee(R, selector)`**, the function §3.5 names. `N_PENALTY`,
`ACCURACY_WINDOW` and `PAYEE_TILT_BPS` are the node's configured values (defaults from §3.1;
`-yellowbackpayeepenaltyblocks`, `-yellowbackpayeeaccuracywindow`, `-yellowbackpayeetiltbps`,
L6), and `yed_getfeepayee` reports the values it used. `-yellowbackpreferredpayee` replaces the
choice outright when that key is in `E(R)`. A pool wallet may lawfully pay itself.

### 3.8 Rules

**Totality (M1, K1).** Every rule below is a predicate over defined quantities. A rule whose
input is undefined — a missing or virtual snapshot, an undefined price, a height outside the
index, a lookup that misses — is **false**; a MINT rule that is false gives the VOID verdict, a RED
rule that is false gives the block-invalid verdict. No rule may throw, assert on input, or divide
by an unchecked zero.

Blocks below `START_HEIGHT` are ignored completely. Within a block, the coinbase tag is read
first (TAG-1..5, `Tags[H]`), then transactions in block order, each transaction's inputs before
its outputs (carried over). Every transaction that creates or spends a `Tokens` or `Vaults` entry
gets a `TxLog` entry (a VOID mint creates a `Vaults` entry and so gets one); a transaction whose
payload yields a non-Yellowback verdict and touches neither gets none, so the log is bounded by
Yellowback-relevant transactions, not by payload bytes an attacker pays ordinary fees for (N7). **A transaction that spends an ACTIVE vault is processed by IN-1..3
and RED-1..4 only: MINT and XFER rules never apply to it, whatever payload it carries** (M3); if
RED-1..4 hold its REDEEM assignments create `Tokens`, otherwise `yedOut = 0` and no vault or token
is created, and `TxLog.type = REDEEM` either way.

**IN-1** (*carried over*) every input that spends an outpoint in `Tokens` removes it and adds its cents to
`yedIn`. **IN-2** (*carried over, amended*) every input that spends an outpoint in `Vaults` with status
ACTIVE or VOID closes it (`closeHeight = H`, `closingTxid`): a VOID vault becomes `CLOSED`; an
ACTIVE vault spent by a REDEEM that passes RED-1..4 becomes `CLOSED` (owner path) or `CLAIMED`
(claim path) and its `collateralZat` leaves `Totals.collateralZat`; an ACTIVE vault spent by
anything that fails RED-1..4 (possible on a non-enforcing node, before activation, or while
enforcement is suspended, ACT-5) becomes `CLOSED` with `unbacked = (burned < mintedCents)` and
`max(0, mintedCents − burned)` added to `Totals.unbackedCents` (recorded at close so the accountability
check has a defined evaluation height, M3). **IN-3** (*carried over*) after
outputs are processed, `burned = yedIn − yedOut`; `Totals.supplyCents −= burned`; `burned` is
recorded on every vault closed by this transaction. For a MINT, `yedOut` in this formula is `0` —
a mint's `yedOut = cents` is newly issued, not assigned from inputs — so every YED input of a MINT
is burned (carried over from the prototype); `supplyCents += cents` is applied separately when
MINT-1..8 hold (N19).
**TX-0** the coinbase has `yedOut = 0` and registers nothing; shielded components are ignored (the
YEC side of a transaction is never restricted: the index reads transparent inputs, `vout` indexes and
the `OP_RETURN` only, so a shielded-funded mint or a shielded collateral destination is accounted
exactly as a transparent one).

**MINT-1** payload MINT, well-formed. **MINT-2** (signed 64-bit arithmetic, M1) `termClass ∈
{0,1,2}`, `MIN_MINT ≤ cents ≤ MAX_MINT`, `lockHeight + GRACE < LOCKTIME_THRESHOLD`,
`H − REF_WINDOW ≤ refHeight ≤ H − 1`, `refHeight ≥ START_HEIGHT`, `lockHeight > refHeight` and
`lockHeight − refHeight ∈ classRange(termClass)`. **MINT-3**
`vout.size() ≥ 3`, `vout[0]` is P2SH and equals `HASH160(vaultScript(lockHeight, ownerPubKey,
lockHeight + GRACE))`, `ownerPubKey` is a valid compressed key. **MINT-4** with `S =
Snapshots[refHeight]`: `S.activation == ACTIVE` and `S.haltMask == 0`. **MINT-5** `vout[0].nValue
≥ requiredZat(cents, termClass, S)` (which must be satisfiable, K14) and `vout[0].nValue ≥ 4 · FEE_MIN`. **MINT-6** `Totals.supplyCents + cents ≤ supplyCapCents(S)`
(if a cap applies), evaluated at `H`. **MINT-7** `vout[1]` is not the `OP_RETURN`. **MINT-8**
fee: if `E(refHeight)` is empty the rule is vacuous (FEE-0); else `feeVout ≠ 0xFF` (M1),
`feeVout < vout.size()`, `vout[feeVout]` is `P2PKH(k)` for some `k ∈ E(refHeight)`,
`vout[feeVout].nValue ≥ feeZat(vout[0].nValue)`, and `feeVout ∉ {0, 1, opReturnIndex}`.
If MINT-1..8 hold: `Vaults[txid:0] = ACTIVE {…, feePaidZat}`, `Tokens[txid:1] = cents`, totals
updated, `yedOut = cents`. If MINT-1 holds and any of MINT-2..8 fails and `vout[0]` is P2SH:
`Vaults[txid:0] = VOID`, `yedOut = 0` (no YED is created; the collateral is locked until `lockHeight`).
MINT rules never make a block invalid (V3).

**XFER-1** (*carried over*) payload TRANSFER or REDEEM, well-formed; every assigned `vout` exists and is
not the `OP_RETURN`; `MIN_OUTPUT ≤ cents ≤ MAX_OUTPUT` per assignment. **XFER-2** `Σ assigned
cents ≤ yedIn` (the difference is burned; for a wallet-built TRANSFER it is 0, for a REDEEM it is
the burn). **XFER-3** `yedIn > 0`. If XFER-1..3 hold each assignment creates `Tokens[txid:vout] =
cents` and `yedOut = Σ`; if XFER-1 or XFER-3 fails, or `Σ > yedIn`, nothing is assigned and
`yedOut = 0` (all inputs burned — the Runes "cenotaph" rule of the prototype, under which every
chain has exactly one Yellowback state). Burning only the unassigned remainder when `Σ ≤ yedIn`
is the most forgiving rule that is still total.

**RED-1..4** apply to every transaction that spends a `Vaults` outpoint with status **ACTIVE**
(a VOID vault's spend is an ordinary spend that closes it, K3):
**RED-1** `vin[0]` is the vault (an ACTIVE vault at any other index, or a second ACTIVE vault in
the same transaction, fails); `vin[0].scriptSig` is push-only with at least two pushes and the
path is read per §3.4; the payload is a well-formed REDEEM with `H − REF_WINDOW ≤ refHeight ≤
H − 1` and `refHeight ≥ START_HEIGHT` (K1, signed arithmetic), and every assignment satisfies
XFER-1.
**RED-2** (burn): `yedIn − Σ assigned ≥ mintedCents`.
**RED-3** (fee): as MINT-8 with `feeZat(vault.collateralZat)` and
`feeVout ∉ {opReturnIndex} ∪ assigned vouts` (the fee output may not double as a token output;
it may be any other output, K23 — including the collateral destination, so a pool that redeems
or claims its own vault pays no net fee; a known and harmless consequence, M13).
**RED-4** (path): owner path — nothing further; claim path — the vault is underwater at
`Snapshots[refHeight]` (§3.7 *Claimable*; an undefined `pClaim` means not underwater, so the
rule fails, M1). A claimant chooses `refHeight` among the last 40 heights and so the lowest
`pClaim` among them; `pClaim` moves on 576/2,016-block windows, so the gain is small (M13).
If RED-1..4 hold: the vault becomes `CLOSED` (owner path) or `CLAIMED` (claim path),
`burnedCents = yedIn − yedOut`, `supplyCents −= burnedCents`, assignments create `Tokens`, and
`feePaidZat` is recorded. If any fails: **BLK-1** decides whether the block is invalid; on a node
that nevertheless applies the block the vault is `CLOSED` with `unbacked` per IN-2 and all YED
inputs are burned (IN-3), i.e. the same outcome as an invalid transfer.

**ACT-1** (signalling) at every SNAP: `signalCount(H)` as §3.7. **ACT-2** (lock-in) if
`status == SIGNALING`, `H ≥ START_HEIGHT + SIGNAL_WINDOW − 1` and `signalCount(H) ≥
ACTIVATION_THRESHOLD`: `status = LOCKED_IN`, `lockInHeight = H`, `activateHeight = H +
ACTIVATION_DELAY`. **ACT-3** (activation) if `status == LOCKED_IN` and `H ≥ activateHeight`:
`status = ACTIVE`. **ACT-4** (participation, carried state read from `Snapshots[H − 1].haltMask`): the bit is set
when `status == ACTIVE` and `signalCount(H) < PARTICIPATION_FLOOR`; once set it persists while
`signalCount(H) < ACTIVATION_THRESHOLD` and clears at the first `H` with `signalCount(H) ≥
ACTIVATION_THRESHOLD` (hysteresis, K15). Status never moves backward. **ACT-6** (enforcement
floor, L3; carried state like ACT-4): the `ENFORCEMENT` bit is set when `status == ACTIVE` and
`signalCount(H) < ENFORCEMENT_FLOOR`; once set it persists while `signalCount(H) <
ENFORCEMENT_RESUME` and clears at the first `H` with `signalCount(H) ≥ ENFORCEMENT_RESUME`. Since
`ENFORCEMENT_FLOOR < PARTICIPATION_FLOOR ≤ ENFORCEMENT_RESUME < ACTIVATION_THRESHOLD`, the bit
implies `PARTICIPATION`: minting always stops before rejection does. **ACT-5** (enforcement
window): enforcement at `H` is on iff `Snapshots[H − 1].activation == ACTIVE`,
`Snapshots[H − 1].haltMask.ENFORCEMENT` is clear (K2, L3), and `H ≤ ENFORCE_UNTIL_HEIGHT` of the
parameter set in force at `H` (the sunset, L8: past it the node keeps tagging and evaluating,
drops the signal bit, logs "upgrade required" and sets `yed_getinfo.sunset = true`). A LOCKED_IN status still becomes ACTIVE
at `activateHeight` even if signalling has collapsed by then; ACT-4/ACT-6 then set their bits in
the same snapshot, so enforcement never switches on and minting never opens until signalling
returns (M13). MINT-4 reads the halts at `R` while ACT-5 reads `H − 1`, so a mint whose snapshot
was clear can confirm at an `H` where enforcement is already suspended; the window is ≤ 40 blocks
and accepted (M13).

**HALT-1** `NO_PRICE` iff `pMint` undefined. **HALT-2** `GLOBAL_RATIO` iff `supplyCents > 0`,
`pMint` defined and `globalRatioBps < GLOBAL_RATIO_HALT_BPS`. **HALT-3** `DIVERGENCE` iff all three
medians are defined and `pFast · 10⁴ < (10⁴ − DIVERGENCE_BPS) · pMid` or `pMid · 10⁴ < (10⁴ −
DIVERGENCE_BPS) · pSlow` (when any price is undefined HALT-2/3 are clear and `NO_PRICE` covers the
case, M1). **HALT-4** `NOT_ACTIVE` iff `status ≠ ACTIVE`. `PARTICIPATION` and `ENFORCEMENT` are
ACT-4/ACT-6. Halts affect MINT-4 only; never transfers, redemptions or claims.

**REG-4** judgement runs at every SNAP for the tag at `H − PEER_LAG` (§3.7).
**SNAP** after the last transaction: judgement, activation, medians, σ, issuance, halts;
write `Snapshots[H]`. **UNDO** (carried over): applying then undoing a block restores byte-identical state.

### 3.9 Block validity, template and mempool rules

**BLK-1 (the soft-fork rule).** A block at height `H` is **Yellowback-invalid** iff enforcement
is on at `H` (ACT-5) and some transaction in it spends a `Vaults` outpoint with status ACTIVE and
fails RED-1..4, evaluated in block order over the in-block state. Nothing else in this plan makes
a block invalid (TAG-4, V3). `EvaluateBlock` is total: no input can make it throw (K1).
**BLK-2 (what an enforcing node does).** `ConnectBlock` returns `state.DoS(0, …, REJECT_INVALID,
"yellowback-vault-spend")` with the rule identifier in the log; the block is marked
`BLOCK_FAILED_VALID`, its hash and reason are written to `Rejected` synchronously (`sync = true`,
N8), no peer is punished. **Descendants:** a header (or block) whose parent is a
`BLOCK_FAILED_VALID` block in `Rejected`, or a header already noted as descending from one, is
answered in `AcceptBlockHeader` with `state.DoS(0, …, REJECT_INVALID, "bad-prevblk-yellowback")`
*before* the stock `bad-prevblk` returns (`main.cpp:4555` at DoS 10, `:4557-4558` at DoS 100),
which the `headers` and `block` handlers would otherwise pass to `Misbehaving` (`:6604-6610`,
`:6651-6658`); the index notes each such header's hash and accumulated work (from its parent's
work plus `GetBlockProof` of its own `nBits`) as the valve's odometer (ACT-7), so stock peers
relaying the stock chain are never scored either (N1). **Initial sync (clause 2):** no rejection
while `IsInitialBlockDownload()` is true or under `-reindex` / `fImporting`: evaluation and
`CommitConnect` still run — the index is rebuilt identically — only the reject is suppressed and
nothing is written to `Rejected`, so a plain `-reindex` is safe (N2). What IBD means in Ycash 4.5
(`main.cpp:2106-2178`): `fImporting || fReindex`, a null tip, a tip below `nMinimumChainWork`, or a
tip **older than `nMaxTipAge`** (24 h, `-maxtipage`, `:2174`) — nothing about how far behind the
best header the tip is — and once false it latches false (`:2107-2112`, a `static`, reset only by
restart). **Catch-up (clause 3, L11):** a node whose tip is younger than a day evaluates the
network's blocks outside IBD when it catches up after a partition, a short outage or a restart, so
BLK-2 additionally accepts, without a rejection, a block at `H` for which
`pindexBestHeader->GetAncestor(H) == pindex` and `pindexBestHeader->nChainWork ≥
chainActive.Tip()->nChainWork + VALVE_BLOCKS · GetBlockProof(*chainActive.Tip())` — the network
has already built `VALVE_BLOCKS` of work on it, which is exactly the condition under which ACT-7
would rejoin it anyway; the node logs `catch-up: accepted rule-breaking block <hash> at H
(network N blocks ahead)`, increments `yed_getinfo.suppressedBlocks`, writes nothing to
`Rejected` and leaves enforcement on (no trip, no restart). When the network is fewer than six
blocks ahead the block is rejected as usual; if headers beyond it were already indexed
(`BLOCK_FAILED_CHILD` marks from `FindMostWorkChain`, `:3712-3722`), the next header that arrives
has such a block as its parent and the odometer reads that parent's real `nChainWork`
(`IsRejectedAncestor` walks `pprev` through `_CHILD` marks to the `_VALID` root), so the valve
trips within one block. A fresh node syncing a chain that carries a historically accepted
rule-breaking block therefore reaches the tip with `rejectedBlocks == 0` whichever clause applied.
With `-yellowbackenforce=0` the same evaluation is logged and the block is accepted.
**BLK-3 (fail open on storage only).** A storage failure while reading or committing the index,
or an already-unhealthy index, accepts the block and disables enforcement until
`-reindex-yellowback` (V13). Evaluation itself has no failure mode.
**ACT-7 (work valve, L7; node-local, never a state input).** When the headers the node has noted
under BLK-2's descendant clause, rooted at a block in `Rejected`, reach accumulated work
`≥ chainActive.Tip()->nChainWork + VALVE_BLOCKS · GetBlockProof(*chainActive.Tip())` — the
arithmetic of `CheckForkWarningConditions` (`main.cpp:2197`), evaluated by the index because
`pindexBestInvalid` is inaccessible (`main.cpp:139-285`) and cannot grow from refused headers —
the node clears enforcement for the session (`enforcing = false`, `unhealthyReason` untouched,
`yed_getinfo.valveTripped = true`, reason `valve-tripped`), runs the V13 `ReconsiderBlock` loop
under the `cs_main` it holds for every hash in `Rejected`, clears `Rejected` and its notes, drops
the signal bit (MINER-1), and raises its own warning through the two calls the stock fork warning
uses — `SetMiscWarning` (`warnings.cpp:22`, read by `getinfo.errors`) and `CAlert::Notify`
(`alert.h:107`, `-alertnotify`) — with the text `Yellowback: work valve tripped at height H
(rejected root <hash>); enforcement off until restart` (P1; the stock warning itself never fires
here, because `pindexBestInvalid` grows only from indexed blocks and descendants of a refused
header are never indexed). The tripping header is answered DoS 0 like the ones before it;
convergence follows **at the next block the network announces** (P3): its `inv` triggers
`getheaders` from `pindexBestHeader` (`main.cpp:6281`), the stock chain's headers are now
accepted because the root is no longer marked, the blocks are downloaded, and `ProcessNewBlock →
ActivateBestChain` reorganises the node onto the heavier chain. Re-arming is an operator restart.
**What is noted (P2):** a header is noted only if its parent is the rejected root or an existing
note, its target is at most `132 / 100` of its parent's (the consensus per-block loosening,
`nPowMaxAdjustDown`, `chainparams.cpp:104` — the clause runs before `ContextualCheckBlockHeader`
verifies `nBits`), and the root holds fewer than `VALVE_NOTE_CAP` notes; anything else is answered
DoS 0 and forgotten. Fake difficulty cannot inflate the odometer (`GetBlockProof` is the work a
header actually proves); the bounds only cap memory. The node relies on stock peers announcing
new blocks by `inv` and on its own direct fetch of announced blocks while its tip is recent
(`main.cpp:6281-6286`), which is how descendants beyond the first reach the clause; on regtest the
six-node topology delivers them the same way. Enforcement thus means majority in fact: a minority
of enforcers is outrun for at most six blocks, a node catching up on a chain the network already
extended past that bound never rejects at all (BLK-2 clause 3), and a forged signal majority
(TAG-3, N4) buys a six-block split, not a permanent one.

**TPL-1** `CreateNewBlock` evaluates each candidate transaction, in the order it would be added,
against an overlay view of the state at the tip with the already-added transactions applied; a
transaction that would fail BLK-1's condition is skipped whether or not activation has occurred —
**except while `IsAbandoned()` holds** (§4.6, L13), when TPL-1 and TPL-2 stand down for vault
spends so that owner sweeps can be mined by whoever still runs the module.
**TPL-2** (`strict`, default) additionally skips a MINT whose verdict would be VOID, a
TRANSFER whose verdict would burn, a claim-path spend of a VOID vault, a vault spend whose
scriptSig is not exactly the wallet's `<sig> OP_1 <script>` / `OP_0 <script>` shape, and a vault
spend without the MP-1 expiry (`nExpiryHeight = 0` or `> refHeight + REF_WINDOW`). **TPL-3** the node's own template must pass its own
`TestBlockValidity`, which runs the BLK-1 check (`ref/ycash/src/miner.cpp:660`, `main.cpp:4711`);
a discrepancy is a bug and throws, as any template failure does today.
**MP-1** `AcceptToMemoryPool` on a `-yellowback` node refuses a transaction that spends an ACTIVE
vault and fails RED-1..4 at the next height, **irrespective of ACT-5** (as TPL-1) but **not while
`IsAbandoned()` holds** (L13: under abandonment every vault spend is admitted like any other
transaction, so a sweep leaves its owner's node), with
`REJECT_NONSTANDARD "yellowback-vault-spend"`; it also refuses a vault spend whose
`nExpiryHeight` is `0` or exceeds `refHeight + REF_WINDOW`, so the transaction expires from every
mempool — stock nodes enforce expiry — before RED-1's window closes and cannot linger for a stock
miner after a tip change made it invalid (N5); it never refuses mints or transfers. MP-1 is an
admission-time check: `ConnectTip` additionally drops from the mempool every vault spend whose
`MempoolCheck` fails at the new tip (§4.3), and `getrawmempool` on a node without that sweep may
still list a spend TPL-1 will never mine. `MempoolCheck` returns true in `O(inputs)` `Vaults`
lookups when no input is an ACTIVE vault and never computes a SNAP (the tag at `H` never affects
rules at `H`, §4.4), so an ordinary transaction costs an enforcing node nothing measurable (N6;
benchmark in §7). `MempoolCheck`
sees only confirmed YED inputs (unconfirmed parents are not in the index), so a chained redemption
is refused; the wallet uses confirmed inputs only, and `yed_validaterawtransaction` says so (M13).

**Miner-side (not consensus, not policy on others):** **MINER-1** a template's coinbase carries a
quote tag iff a quote younger than `-yellowbackquotemaxage` is held, else a signal-only tag iff
`-yellowbacksignal`; the signal bit is set iff `-yellowbacksignal` **and** `-yellowbackenforce=1`
**and** the valve has not tripped (ACT-7) **and** the tip is not past `ENFORCE_UNTIL_HEIGHT`
(the kill switch, the valve and the sunset all clear the signal, L3, L7, L8); **MINER-2** `payoutKey` is the key hash of
`-yellowbackpayoutaddress`, which must be a P2PKH (`s1…`) address (K22) and defaults to
`-mineraddress` when that is a P2PKH address; without one no tag of either kind is emitted; **MINER-3**
no tag is emitted while the index is unhealthy, and with `-yellowbackrequirehealthy`
`getblocktemplate` refuses outright while unhealthy (K24).

**Wallet-side (policy):** **MINTPOL-1**, the mint gate, is defined in §4.6.

### 3.10 Determinism requirements

*Carried over from the prototype, restated (M15).* The validator and state machine may read only the block being
applied, the state view and `Params`. Forbidden: `GetTime()`, `GetAdjustedTime()`, `mempool`,
`pwalletMain`, `GetArg`, floating point, and any iteration order that depends on pointers. Every
function in `src/yellowback/state.*` must be callable from a unit test with an in-memory view.
Three additions: the quote held by the node (MINER-1) and `-yellowbackenforce` are read **only** on
the miner path (`miner.cpp` → `policy.cpp`) and in the hook's "what to do with an invalid verdict"
branch, never inside evaluation; the clock has one home — `yed_setquote` stamps `receivedAt` with
`GetTime()` in `rpc/yellowback.cpp`, and `policy::BuildTagScript(now)` takes the time as a
parameter (M11) — so the grep is "`GetTime` only in `rpc/yellowback.cpp` and `policy.cpp`"; and
`Rejected`, the valve's header notes (ACT-7) and the valve state itself are node-local
bookkeeping that never feeds a rule. The block subsidy a SNAP needs (`issuedZat`) is passed to
`EvaluateBlock` by its caller, so `state.cpp` links against nothing in `main.cpp` (N22).

---

## 4. Architecture in `ycash-dd` and `yecwallet-dd`

### 4.1 Diff budget

Target for the whole node feature at the end of Phase 7, measured by
`git diff --stat ycash-legacy...feature/yellowback-sf`. Every behaviour-changing line in an
existing consensus or mining file is an **insertion** guarded by `if (g_yellowback)` (null unless
`-yellowback`); the unguarded remainder — two `#include`s, the K17 lock, the empty
`COINBASE_FLAGS` append — is enumerated in §8.4 item 2, so a node without the flag runs v4.5.0
code paths unchanged, which `yellowback_stockparity.py` proves against `ref/ycash` nightly (N10).

| Existing file | Lines (est.) | What | Tier |
|---|---|---|---|
| `src/main.cpp` | ≈ 29 | `ConnectBlock`: the check call in the `:3191-3193` window (≈ 6) and the commit call after `view.SetBestBlock` (`:3268`) (≈ 4); `DisconnectBlock`: the undo call before its final `return` (`:2796`), gated on `updateIndices` (≈ 4); `AcceptToMemoryPool`: MP-1 after `:1643` (≈ 5); `AcceptBlockHeader`: the descendant clause before `:4553` (≈ 6, N1/ACT-7); `ConnectTip`: the mempool sweep after `removeExpired` (`:3636`) (≈ 3, N5); `#include "yellowback/index.h"` (1). Sum 29. **No other consensus code changes**; the "overlay-view helper" of revision 4 never existed in §4.3 and is gone (N25). | soft fork (hook) |
| `src/miner.cpp` | ≈ 18 | `CreateNewBlock`: set `COINBASE_FLAGS` from the module and take the `TemplateView()` holder (≈ 4) and the TPL-1/2 filter call before `UpdateCoins` at `:582` (≈ 10); `CreateCoinbaseTransaction:327`: `+ COINBASE_FLAGS` (1); `LOCK(cs_main)` around the `-gen` loop's `IncrementExtraNonce` at `:832` (2, K17); `#include "yellowback/index.h"` (1). Sum 18. | mining policy |
| `src/rpc/mining.cpp` | ≈ 25 | all under `if (g_yellowback)` (N10): `coinbaseaux.flags` emitted; `"coinbase/append"` in `mutable`; the `yellowback` template object (V26); `-yellowbackrequirehealthy` refusal (K24) | RPC |
| `src/init.cpp` | ≈ 110 | the prototype's ≈ 75 (flag, `-prune` refusal, index open/sync/close, wallet layer, RPC registration) plus `-yellowbackenforce`, `-yellowbackpayoutaddress`, `-yellowbacksignal` (default per network, L4), `-yellowbackquotemaxage`, `-yellowbacktemplatepolicy`, `-yellowbackrequirehealthy`, `-yellowbackpreferredpayee` and the three payee-policy overrides (L6), the kill-switch `ReconsiderBlock` loop, the four regtest-only flags (`-yellowbackstartheight`, `-yellowbacksigmaref`, `-yellowbacksupplycapbps`, `-yellowbackenforceuntil`, L8) and the test-only `-yellowbacktestfault`; minus the genesis-anchor/roster arguments | node |
| `src/experimental_features.{h,cpp}`, `src/rpc/register.h`, `src/rpc/client.cpp`, `src/Makefile.am`, `src/Makefile.test.include`, `qa/pull-tester/rpc-tests.py`, `test_framework/util.py`, `multi_rpc.py` | ≈ 90 | as in the prototype (77 lines today) plus `tag.cpp`, its test and fuzz target, and the RPC argument conversions (numeric arguments only — `yed_gettag` takes a string, digits parsed as a height; the `client.cpp` rows are listed in §4.5) | build/test |
| `src/transaction_builder.{h,cpp}` | 35 (unchanged from the prototype) | raw-script output, unsigned transparent input, lock-time setter — the additive extension that lets `yed_mint` be funded from `ys1…` and `yed_redeem` pay collateral to `ys1…` | wallet |
| `src/wallet/rpcwallet.cpp`, `src/rpc/rawtransaction.cpp` | ≈ 40 (Phase 8) | hardening H5 (`lockunspent` refuses Yellowback-locked coins), H7 (`sendrawtransaction` guard), H8 (re-lock after `importprivkey`/`importwallet`); wallet tier, not consensus (M7) | wallet |
| `src/consensus/*`, `src/script/*`, `src/primitives/*`, `src/pow/*`, `src/chainparams.cpp`, `src/wallet/wallet.{h,cpp}`, `src/txdb.*`, `configure.ac` | **0** | | |

Everything else is new or prototype-derived under `src/yellowback/`, `src/rpc/yellowback*.cpp`,
`src/test/yellowback_*` (incl. the corpus generator `src/test/gen_yellowback_corpus.py`),
`src/fuzzing/Yellowback*/` (incl. the `YellowbackPayee` target), `qa/rpc-tests/yellowback_*.py`
(incl. `yellowback_stock_node.py`, the nightly `yellowback_stockparity.py` and
`yellowback_runbook.py`, the release run-through `yellowback_rc1.py`, and the Python model
`test_framework/yellowback_model.py`), `contrib/yellowback/`, `doc/yellowback*.md`, and the
fork-local CI workflow. The CI's zero-touch
assertion (the prototype's CI asserted zero changed lines in the consensus set) becomes a **line-budget assertion**: `main.cpp` ≤ 40, `miner.cpp` ≤ 35,
`rpc/mining.cpp` ≤ 35 changed lines, and the consensus set above at 0 (`src/wallet/rpcwallet.cpp`
and `rpc/rawtransaction.cpp` leave the zero set for Phase 8, M7). The existing no-sockets
grep is anchored (`\bconnect(`), since `UndoDisconnect(` would otherwise match, and the
determinism grep gains `tag.cpp` (K23).

### 4.2 Modules, and what happens to every prototype file

Classification from the 2026-09-10 inventory of `feature/digidollar` (66 node files, +13,629 lines;
30 wallet files, +3,915). **Reuse** = no change beyond renames; **adapt** = listed change;
**remove** = deleted in Phase 0.

```
src/yellowback/
  params.{h,cpp}     ADAPT   drop genesisAnchor/genesisRosterScript/rosterGrace/ROSTER_MAX_N and the
                             tier tables; DELETE PRICE_MAX_AGE, HEALTH_CAP, VOL_1H_BPS, VOL_24H_BPS, RED_SKEW,
                             NUM_TIERS, Params::volCooldown/volWindowShort/volWindowLong, IsValidTier (N21);
                             RENAME MINT_WINDOW -> REF_WINDOW, DEFAULT_MINT_EVAL_LAG/MAX_MINT_EVAL_LAG ->
                             DEFAULT_REF_LAG/MAX_REF_LAG (the flag -yellowbackmintlag keeps its name);
                             add §3.1 (windows, classes, fee, grace, σ, activation, VALVE_BLOCKS,
                             ENFORCE_UNTIL_HEIGHT, ABANDON_BLOCKS); IsConfigured() = startHeight known;
                             RegtestParams(startHeight, sigmaRefBps, supplyCapBps, enforceUntil) beside the old
                             overload until Phase 3 (§6 preamble); field list in §4.2a
  math.h             ADAPT   keep CeilDiv/FitsInt64/RequiredCollateral (new signature: minRatioBps, pMint)/
                             RequiredCollateralRounded; add LowerMedian, IsqrtU256, SigmaMultBps, MinRatioBps,
                             CapCents, SupplyCapCents, GlobalRatioBps, IsUnderwater, FeeZat; DELETE Health, DcaBps,
                             ErrBps, RequiredBurn, VolatilityBreach (V20); no IssuedZat — the subsidy is an
                             argument of EvaluateBlock (N22)
  tag.{h,cpp}        NEW     CoinbaseTag struct, EncodeTag, FindTag(scriptSig, nHeight) (TAG-1..5), TagPush()
                             (renamed from TagScript to avoid policy::TagScript, N25)
  payload.{h,cpp}    ADAPT   version 0x02; MINT gains termClass/refHeight/feeVout, REDEEM gains refHeight/feeVout;
                             PRICE removed; factories and tests regenerated
  script.{h,cpp}     ADAPT   VaultScript(lockHeight, owner, claimHeight); ParseVaultScript; OwnerScriptSig,
                             ClaimScriptSig, ParseVaultSpendPath; DELETE Roster*, BuildVaultScriptSig (quorum),
                             ParseVaultScriptSig (quorum), SortKeys, VaultScriptSize (roster-shaped, N21);
                             keep IsCompressedKey, P2SHScript, ExtractRedeemScript
  address.{h,cpp}    REUSE
  view.{h,cpp}       ADAPT   drop Anchor/Roster tables and accessors, the P<height> price table, the Volatility
                             record/key/GetVolatility; add Tags (Q), Judgements (J), Activation (C), Rejected (X),
                             Params (P) with the key prefixes of §3.6; VaultRecord: tier -> termClass, drop wasActive/
                             errBpsAtClose/requiredBurnAtClose/rosterIndex, keep voidReason, add claimHeight/refHeight/
                             feePaidZat/unbacked and the CLAIMED status; TxLogRecord: drop anchorSpend/priceRecorded,
                             add path/feeZat/payee, keep spentTokens (N21); Snapshot per §3.6; SCHEMA_VERSION = 2;
                             StateHash excludes prefixes U, X and the TxLog table (§3.6); OverlayStateView unchanged
                             (it is the template filter's view)
  state.{h,cpp}      ADAPT   ProcessTx: IN-1..3 as is; MINT-1..8; XFER-1..3 as is; RED-1..4 (new; replaces the prototype's
                             co-signer rules — v1 RED-0..8, archived plan §3.8 — as the vault-spend rule set);
                             ApplyBlock reads the tag first;
                             ComputeSnapshot per §3.7/§3.8 (medians, σ, activation incl. ACT-6, halts, judgement);
                             NEW EligiblePayees(view, params, R) (FEE-2) and DefaultPayee(view, params, R, selector,
                             policy) (FEE-W) — they read Tags/Judgements, so they live here, not in math.h;
                             DELETE the prototype's anchor-chain price rules (v1 PRICE-1..3, archived plan §3.7),
                             roster reveal/rotation, genesis-anchor init, MintableRosters;
                             NEW EvaluateBlock(overlay, params, block, height, blockHash, subsidyZat) -> BlockEvaluation
                             (signature in §4.2a; the subsidy comes from the caller, N22)
                             used by ConnectBlock, CreateNewBlock, MempoolCheck and yed_getblockverdict
  db.{h,cpp}         REUSE
  index.{h,cpp}      ADAPT   ChainTip no longer applies state; new methods under cs_main: CheckConnect(block, pindex,
                             fJustCheck) -> optional<reason>, CommitConnect(block, pindex), UndoDisconnect(pindex),
                             NoteHeaderOnRejectedChain(header) (the N1 clause and the ACT-7 odometer),
                             IsRejectedAncestor(pindex), RemoveInvalidVaultSpends(mempool) (N5), TemplateView(),
                             TemplateInfo(), MempoolCheck(tx), IsAbandoned() (L10; the §4.6 predicate);
                             SyncToChain unchanged in shape (undo-walk then apply-forward), UNDO_KEEP 1000 -> 4096;
                             enforcement flag, valve state {tripped, reason}, sunset flag, Rejected bookkeeping
                             (sync writes; cleared by -reindex-yellowback), quote holder {priceMicroUsd, sourceMask,
                             receivedAt} (stamped by the RPC — no clock here, M11), payout key, signal flag;
                             unhealthy => enforcement off (BLK-3); DELETE IsSynced (V2), TestChainTip/ApplyConnected/
                             ApplyDisconnected/ApplyOne/UndoOne (reshaped into the three hooks); ParamsFromArgs gains
                             -yellowbacksigmaref/-yellowbacksupplycapbps/-yellowbackenforceuntil and loses the anchor/
                             roster/-yellowbacksupplycap arguments; keep testBeforeApply (unit tests' fault hook, N25)
  policy.{h,cpp}     ADAPT   becomes the miner-side glue: FilterTemplate (TPL-1/2) over an OverlayStateView,
                             TagScript(index) -> BuildTagScript(index, now) (MINER-1..3; the one
                             GetTime() call outside the RPC, M11); the prototype's co-signer logic deleted
                             (RED-1..4 now live in state.cpp because they are block-validity rules); DELETE RedeemCheck,
                             CheckRedeem, FetchInputs; SignerBranchId and VerifyAllInputs MOVE to txbuilder (N21)
  wallet.{h,cpp}     ADAPT   keep ownership, three-stage locking, balances; DELETE PendingRedemption, reservedInputs,
                             IsReserved, MarkCosigned
  txbuilder.{h,cpp}  ADAPT   BuildMint (new vault script, fee output, class/lockBlocks), BuildTransfer (reuse),
                             BuildRedeem (owner path, fee output, returns a complete transaction), NEW BuildClaim,
                             NEW BuildSweep (L10); SignVaultSpend replaces SignRedeem (signs <sig> OP_1 <script>; the
                             claim path signs YED inputs only); keep FinishSapling; BuiltTx: evalHeight -> refHeight,
                             drop requiredBurn, add feeZat/payee/termClass/claimHeight/path; DELETE AddCosignature,
                             CountQuorumSignatures, SameExceptSignatures
src/rpc/yellowback.cpp        ADAPT   §4.5
src/rpc/yellowbackwallet.cpp  ADAPT   §4.5
```

Build placement (Ycash links `test_bitcoin` and `ycashd` from `libbitcoin_server`/`_wallet`/`_common`,
`ref/ycash/src/Makefile.am:267,324,413`): `params`, `math`, `tag`, `payload`, `script`, `address`, `view`,
`state` → `libbitcoin_common`; `db`, `index`, `policy`, `rpc/yellowback.cpp` → `libbitcoin_server`
(`main.cpp` and `miner.cpp` are in `libbitcoin_server`, so the hooks link without a new library);
`wallet`, `txbuilder`, `rpc/yellowbackwallet.cpp` → `libbitcoin_wallet`. Nothing in
`libbitcoin_common` may call a `libbitcoin_server` symbol — which is why `GetBlockSubsidy` is an
argument, not a call (N22).

### 4.2a Signatures and verdict strings (N25, N20)

The `std::optional` convention: "undefined" in §3.7 is `nullopt`; a function that §3.8 says is
*false* on an undefined input takes an `optional` and returns `false` on `nullopt`. `Cents` and
`MicroUsd` are `int64_t` typedefs; `CAmount` as in Ycash.

```
// math.h (libbitcoin_common; pure)
std::optional<MicroUsd> LowerMedian(std::vector<MicroUsd> v);                      // nullopt if empty
arith_uint256 IsqrtU256(const arith_uint256& x);                                    // floor sqrt
int SigmaMultBps(const std::vector<std::optional<MicroUsd>>& samples /* s_0..s_n */,
                 int sigmaRefBps, int periodsPerYear, int maxBps);                  // cap on any nullopt; sigmaRefBps == 0 ⇒ 10000
int MinRatioBps(int baseRatioBps, int sigmaMultBps);
std::optional<CAmount> RequiredCollateral(Cents cents, int minRatioBps, MicroUsd pMint);            // nullopt = unsatisfiable (> MAX_MONEY)
std::optional<CAmount> RequiredCollateralRounded(Cents, int, MicroUsd, CAmount granularity = 1000);
std::optional<Cents> CapCents(CAmount issuedZat, std::optional<MicroUsd> pMint);
std::optional<Cents> SupplyCapCents(CAmount issuedZat, std::optional<MicroUsd> pMint, int capBps); // capBps == 0 ⇒ nullopt (no cap)
std::optional<int64_t> GlobalRatioBps(CAmount collateralZat, std::optional<MicroUsd> pMint, Cents supplyCents); // nullopt when supply == 0 or price undefined
bool IsUnderwater(CAmount collateralZat, std::optional<MicroUsd> pClaim, Cents mintedCents, int thresholdBps);  // false on nullopt
CAmount FeeZat(CAmount collateralZat, CAmount feeMin, int feeBps);

// tag.h
struct CoinbaseTag { uint8_t flags; uint64_t priceMicroUsd; uint16_t sourceMask; uint160 payoutKey;
                     bool Signal() const; bool IsQuote() const; };
std::vector<unsigned char> EncodeTag(const CoinbaseTag&);                           // 36 bytes
std::optional<CoinbaseTag> FindTag(const CScript& scriptSig, int nHeight);          // TAG-1..5; nullopt = no tag
CScript TagPush(const CoinbaseTag&);                                                // 0x24 ‖ 36 bytes

// params.h — Params fields (every value a rule reads; hashed = the four regtest values only)
//   startHeight, enforceUntilHeight, addressVersion, pFastWindow, pMidWindow, pSlowWindow, signalWindow,
//   activationThreshold, participationFloor, activationDelay, enforcementFloor, enforcementResume,
//   valveBlocks, abandonBlocks, nReg, peerLag, peerMin, deviationBps, accuracyBandBps, payeeWindow,
//   feeMin, feeBps, grace, claimThresholdBps, supplyCapBps, globalRatioHaltBps, divergenceBps,
//   classMin[3], classMax[3], baseRatioBps[3], volWindow, volStep, volPeriodsPerYear, sigmaRefBps,
//   sigmaMultMaxBps, minMint, maxMint, minOutput, maxOutput, tokenValue, refWindow
//   plus the L6 wallet defaults nPenalty, accuracyWindow, payeeTiltBps (never hashed)

// state.h (libbitcoin_common; total; never throws on input)
struct BlockEvaluation {
    bool blockInvalid;                 // BLK-1 condition, independent of ACT-5
    bool enforcementOn;                // ACT-5 at H (from Snapshots[H-1], incl. the sunset); blockInvalid && enforcementOn ⇒ reject
    std::string reason;                // "<verdict>:<txid>" of the first failing vault spend, else ""
    std::vector<std::pair<uint256, TxLogRecord>> txlogs;
    Snapshot snapshot;
    UndoRecord undo;
};
BlockEvaluation EvaluateBlock(OverlayStateView& overlay, const Params&, const CBlock&, int height,
                              const uint256& blockHash, CAmount subsidyZat);   // writes into the overlay
std::optional<std::string> ApplyBlock(StateView& view, const Params&, const CBlock&, int height,
                              const uint256& blockHash, CAmount subsidyZat, UndoRecord& undo);  // = evaluate + Commit()
std::vector<CKeyID> EligiblePayees(const StateView&, const Params&, int refHeight);              // E(R), height order, deduplicated; empty ⇒ FEE-0
struct PayeePolicy { int penaltyBlocks; int accuracyWindow; int tiltBps; std::optional<CKeyID> preferred; };
std::optional<CKeyID> DefaultPayee(const StateView&, const Params&, int refHeight,
                                   const std::vector<unsigned char>& selector, const PayeePolicy&);  // FEE-W; nullopt iff E(R) empty

// index.h (libbitcoin_server) — every method: AssertLockHeld(cs_main); takes cs_yellowback inside; no-op when !healthy
std::optional<std::string> CheckConnect(const CBlock&, const CBlockIndex* pindex, bool fJustCheck);
//   H = pindex->nHeight. H < startHeight ⇒ nullopt. chainActive.Contains(pindex) ⇒ nullopt (re-verify, K6).
//   Consistency: (indexTip == null && H == startHeight) || indexTip.blockHash == pindex->pprev->GetBlockHash(),
//   else SetUnhealthy("tip-mismatch") ⇒ nullopt. Always evaluates (cache key {block.GetHash(), indexTipHash,
//   paramsHash}, N9); returns a reason iff blockInvalid && enforcementOn && enforceFlag && !valveTripped
//   && !IsInitialBlockDownload() && !fReindex && !fImporting (BLK-2 clauses 1–2)
//   && !NetworkAlreadyBuiltOn(pindex) (clause 3, L11: pindexBestHeader->GetAncestor(H) == pindex &&
//   pindexBestHeader->nChainWork >= tip.nChainWork + valveBlocks * GetBlockProof(*tip); when true the
//   block is accepted, logged and counted in suppressedBlocks); on a reason writes Rejected (sync).
//   Storage exception ⇒ SetUnhealthy(), nullopt (BLK-3). Never reads pindex->phashBlock (K5).
bool CommitConnect(const CBlock&, const CBlockIndex* pindex);   // same guards; reuses the cache else re-evaluates; one batch; false ⇒ unhealthy (block still connects)
bool UndoDisconnect(const CBlockIndex* pindex);                 // guard: indexTip.blockHash == pindex->GetBlockHash() (pindex is in chainActive here); false ⇒ unhealthy
bool NoteHeaderOnRejectedChain(const CBlockHeader&);            // true ⇒ caller returns DoS(0, "bad-prevblk-yellowback"); notes the header only within the
                                                                //   P2 bounds (target ≤ parent target · 132/100; < VALVE_NOTE_CAP notes per root); accumulates work;
                                                                //   trips ACT-7 in place (SetMiscWarning + CAlert::Notify, P1); returns false once tripped
bool IsRejectedAncestor(const CBlockIndex* pindexPrev) const;   // walks pprev through BLOCK_FAILED_CHILD marks to the first BLOCK_FAILED_VALID ancestor; hash ∈ Rejected?
bool NetworkAlreadyBuiltOn(const CBlockIndex* pindex) const;    // BLK-2 clause 3 (L11); reads pindexBestHeader under cs_main
void RemoveInvalidVaultSpends(CTxMemPool&);                     // takes mempool.cs, then cs_yellowback; N5
bool MempoolCheck(const CTransaction& tx);                      // MP-1 predicate (§4.3); O(inputs) when no ACTIVE vault is spent
class TemplateView;                                             // RAII: holds cs_yellowback, owns an OverlayStateView over the tip
TemplateView TemplateView();                                    // caller holds cs_main (and mempool.cs) for its lifetime
UniValue TemplateInfo();                                        // the getblocktemplate "yellowback" object (§4.4)
bool IsAbandoned() const;                                       // the §4.6 predicate (L10, L12): ENFORCEMENT set for abandonBlocks, from Snapshots alone;
                                                                //   read by MempoolCheck and FilterTemplate (L13) and by the wallet's yed_sweep

// policy.h (libbitcoin_server; miner side)
bool FilterTemplate(TemplateView&, const CTransaction& tx, int nHeight);   // TPL-1/2; reads templatePolicy from the index; commits the tx to the overlay when it keeps it
CScript TagScript(const YellowbackIndex&);                                 // = BuildTagScript(index, GetTime())
CScript BuildTagScript(const YellowbackIndex&, int64_t now);               // MINER-1..3; the only clock outside the RPC

// txbuilder.h (libbitcoin_wallet)
BuiltTx BuildMint(YellowbackWallet&, Cents cents, int lockBlocks, CReserveKey&, const std::string& from = "");
BuiltTx BuildRedeem(YellowbackWallet&, const uint256& vaultTxid, const std::string& to = "");   // ACTIVE: owner path + burn + fee; VOID: the release (L14)
BuiltTx BuildClaim(YellowbackWallet&, const uint256& vaultTxid, const std::string& to = "");
BuiltTx BuildSweep(YellowbackWallet&, const uint256& vaultTxid, const std::string& to = "");   // L10; caller checks IsAbandoned()
void SignVaultSpend(BuiltTx&, CWallet&, uint32_t branchId, bool ownerPath);                    // replaces SignRedeem
uint32_t SignerBranchId(int nextHeight);                                                       // moved from policy
bool VerifyAllInputs(const CTransaction&, const CCoinsViewCache&, std::string& err);            // moved from policy; yed_validaterawtransaction
```

**Verdict strings** (the contract the wallet fork and the tests match; `TxLog.verdict`,
`Vaults.voidReason`, `yed_getblockverdict.reason`, `mempool-check-failed:<verdict>`):

| Rule | Verdicts |
|---|---|
| MINT-2 | `bad-mint-amount`, `bad-mint-class`, `bad-mint-lock-height`, `bad-mint-ref-height` |
| MINT-3 | `bad-mint-outputs`, `bad-mint-owner-key`, `bad-mint-vault-script` |
| MINT-4 | `mint-not-active`, `mint-halted-no-price`, `mint-halted-participation`, `mint-halted-global-ratio`, `mint-halted-divergence` |
| MINT-5 | `bad-mint-collateral`, `mint-unsatisfiable` |
| MINT-6 | `mint-supply-cap` |
| MINT-7 | `bad-mint-token-output` |
| MINT-8 | `bad-mint-fee` |
| XFER-1..3 | `bad-transfer-assignment`, `transfer-over-assigned` (Σ > yedIn), `transfer-no-yed-input`; a burn by rule is `burned` |
| RED-1 | `vault-spend-malformed` |
| RED-2 | `vault-spend-missing-burn`, `vault-spend-short-burn` |
| RED-3 | `vault-spend-bad-fee`, `vault-spend-bad-payee` |
| RED-4 | `vault-claim-not-underwater` |
| ok | `ok` (`vault-claim-void` is a TPL-2 template-policy reason, never a verdict) |

The prototype's `bad-mint-tier`, `bad-mint-eval-height`, `bad-mint-eval-snapshot`,
`minting-blocked-during-err`, `mint-frozen-volatility`, `bad-oracle-price` are deleted, not kept.

**Removed outright in Phase 0** (≈ 2,400 node lines, ≈ 700 wallet lines): `Roster`,
`RosterScript`, `ParseRosterScript`, `AddCosignature`, `CountQuorumSignatures`,
`SameExceptSignatures`; `AnchorRecord`, `RosterRecord` and their keys; the prototype's anchor-chain
price rules (v1 PRICE-1..3) and rotation in `state.cpp`; `yed_getroster`, `yed_createpricetx`, `yed_cosignredeem`, `yed_submitredeem`,
`yed_abortredeem`, `yed_getprotectionstatus`; `PendingRedemption`; `qa/rpc-tests/yellowback_federation.py`
and `yellowback_protection.py` (its subject RPC is gone; the price tests move to
`yellowback_pricefeed.py`) with their `rpc-tests.py` entries; `contrib/yellowback/yellowback-redeem`;
the `Coordinator`/`Handler` half of `yellowback_fed.py` (`:641-918`, `:989-1063`) and the
coordinator half of `test_yellowback_fed.py` — `RpcError`/`Node` (`:85-125`, the JSON-RPC client the
quote agent needs) and `load_config` (`:921-948`) move with the feed layer (M7); `doc/yellowback-federation.md`; the
wallet's `yellowbackredeemwizard.{h,cpp}`, the Settings operator-endpoint box, `getRoster`,
`submitRedeem`, `abortRedeem` and the pending-redemption signals in `YellowbackController`.

**Other prototype files, for completeness (M7):** the fork's `README.md` and `contrib/yellowback/README.md`
are rewritten in Phase 7; `doc/yellowback-review.md` (the prototype's review) is kept as history and a v2 file is written
in Phase 8; `src/test/yellowback_fuzz_tests.cpp` embeds the prototype's corpus bytes and is regenerated for
payload v2 and script v2 in Phase 1; `qa/rpc-tests/test_framework/yellowback_util.py` per §6.0
item 4; on the wallet side `docs/yellowback.md` is rewritten in Phase 7b, `build.sh`,
`CMakeLists.txt`, `tests/yellowbacktab_test.cpp` and the eight `.ui` files are adapted (the wizard's
`.ui` deleted, a Claim page added).

### 4.3 Hook points (with citations)

All line numbers are `ref/ycash/src/…` at `v4.5.0`; the fork inserts at the same places.

| Where | What is inserted | Why it is safe |
|---|---|---|
| `main.cpp` `ConnectBlock`, between `control.Wait()` (`:3189-3190`) and `if (fJustCheck) return true;` (`:3194-3195`) — the `:3191-3193` window | `if (g_yellowback) { auto bad = g_yellowback->CheckConnect(block, pindex, fJustCheck); if (bad) return state.DoS(0, error("ConnectBlock(): %s", bad->c_str()), REJECT_INVALID, "yellowback-vault-spend"); }` | runs for `ConnectTip`, `TestBlockValidity` and `VerifyDB` level 4 alike; `DoS(0)` never calls `Misbehaving` (`:2304-2305`); it **always evaluates** when the index is healthy and its tip is `pindex->pprev` — or the index is empty and `H == startHeight`, the `-reindex` and first-start case (N25) — and caches the result under `(blockHash, indexTipHash, paramsHash)` for `CommitConnect` (M7, N9); it returns a reason only if enforcement is on at `H` (ACT-5, incl. the sunset) **and** `-yellowbackenforce` **and** the valve has not tripped (ACT-7) **and** the node is not in `IsInitialBlockDownload()`, `-reindex` or `fImporting` (BLK-2, N2 — `fReindex`/`fImporting` are `main.h:173-174` atomics, readable from the index) **and** the network has not already built `VALVE_BLOCKS` of work on the block (`pindexBestHeader`, `main.h:209`, BLK-2 clause 3, L11 — otherwise the block is accepted, logged and counted in `suppressedBlocks`); a reason is written to `Rejected` with `sync = true` before returning (N8); if `chainActive.Contains(pindex)` the block is being re-verified (`VerifyDB`, `verifychain`) and the call is a silent no-op, otherwise a tip mismatch marks the index unhealthy (K6); **never calls `pindex->GetBlockHash()`** — under `TestBlockValidity` `pindex` is `indexDummy` with a null `phashBlock` (`:4697-4700`, `chain.h:368-371`); it keys on `block.GetHash()` and `pindex->pprev->GetBlockHash()` (K5); evaluation is total, and only a storage failure is caught inside and returns `nullopt` (BLK-3) |
| `main.cpp` `ConnectBlock`, after `view.SetBestBlock(pindex->GetBlockHash())` (`:3268`), i.e. after every write path that can `AbortNode` (`:3204-3263`) | `if (g_yellowback) g_yellowback->CommitConnect(block, pindex);` | never reached under `fJustCheck`; same `chainActive.Contains` / tip guards as the check (K6, K20); writes one batch; on a storage failure marks unhealthy and returns (the block still connects) |
| `main.cpp` `DisconnectBlock` (`:2633-2635`), before its final `return fClean ? … ` (`:2796`, reached only after the view was rolled back), inside `if (updateIndices)` | `if (g_yellowback) g_yellowback->UndoDisconnect(pindex);` | `DisconnectTip` passes `updateIndices = true` (`:3541`, also for `fBare` rewinds); `VerifyDB` level 3 passes `false` (`:5133`) so the self-check never touches the index; guarded by tip == this block, mismatch ⇒ unhealthy |
| `main.cpp` `AcceptToMemoryPool`, after `view.SetBackend(dummy)` (`:1643`) | `if (g_yellowback && !g_yellowback->MempoolCheck(tx)) return state.DoS(0, false, REJECT_NONSTANDARD, "yellowback-vault-spend");` | policy only; style of `:1567`; `AcceptToMemoryPool` holds `pool.cs` for its whole body (`:1520`, "held through `pool.addUnchecked()`"), so the call runs under `cs_main → pool.cs → cs_yellowback`, the recorded order (P11); `MempoolCheck(tx)` (takes cs_yellowback) returns true unless some input spends an ACTIVE vault (`O(inputs)` lookups, no SNAP, N6), and returns true for every vault spend while `IsAbandoned()` (L13); else it checks the MP-1 expiry bound and builds `CBlock{ vtx = [a dummy coinbase with scriptSig = CScript() << (tip + 1) and no outputs, tx] }` — two transactions, because `EvaluateBlock` reads `vtx[0]` as the coinbase (TAG-1, TX-0; N25) — over a `TemplateView()` and returns `!ev.blockInvalid`; the same predicate the wallet runs before `CommitTransaction` (K7); mints and transfers are never refused (MP-1) |
| `main.cpp` `AcceptBlockHeader`, before `mapBlockIndex.find(block.hashPrevBlock)` (`:4553`) — i.e. before both stock `bad-prevblk` returns (`:4555` DoS 10, `:4557-4558` DoS 100) | `if (g_yellowback && g_yellowback->NoteHeaderOnRejectedChain(block)) return state.DoS(0, error("%s: descends from a Yellowback-rejected block", __func__), REJECT_INVALID, "bad-prevblk-yellowback");` | `NoteHeaderOnRejectedChain` returns true when the header's parent is in `mapBlockIndex` with `IsRejectedAncestor(parent)` (walking `pprev` through `BLOCK_FAILED_CHILD` marks to the first `BLOCK_FAILED_VALID` ancestor, whose hash must be in `Rejected`) or is a header it already noted; it records `{hash → rootHash, nChainWork = parent.work + GetBlockProof(header.nBits)}` (`pow.h:30`; a temporary `CBlockIndex` for the arithmetic) **only** when the header's target is at most `132 / 100` of its parent's and the root holds fewer than `VALVE_NOTE_CAP` notes — the clause sits after `CheckBlockHeader` (`:4547`, proof of work against the header's own `nBits`) but before `ContextualCheckBlockHeader` (`:4561`) verifies `nBits`, so without the bound a peer could bloat the map with cheap low-difficulty headers (P2; it could never inflate the work sum, which is real proof) — and, when that work reaches the ACT-7 bound, trips the valve in place (`cs_main` is held by `AcceptBlockHeader`; `SetMiscWarning` + `CAlert::Notify`, P1), answers the tripping header DoS 0 as well, and returns false for every later header so the stock chain is accepted normally from the next announcement on (P3). `DoS(0)` reaches `Misbehaving` in neither handler (`:6604-6610`, `:6651-6658`), so stock peers are never scored for relaying the stock chain (N1). Deeper descendants reach this clause through the direct fetch of `inv`-announced blocks while the tip is recent (`:6281-6286`); the `headers` handler stops at the first refused header, which is why the note map, not `pindexBestInvalid` (anonymous namespace, `:139-285`), is the valve's odometer. Under `-yellowbackenforce=0`, IBD or the sunset `Rejected` is empty and the clause is inert |
| `main.cpp` `ConnectTip`, after `mempool.removeExpired(pindexNew->nHeight)` (`:3636`) | `if (g_yellowback) g_yellowback->RemoveInvalidVaultSpends(mempool);` | policy only; re-runs `MempoolCheck` at the new tip for the mempool's vault spends and removes the failures (with `removeRecursive`-style descendants), so an enforcing node stops relaying a spend a tip change made invalid (N5); lock order `cs_main → mempool.cs → cs_yellowback` holds because the call takes `mempool.cs` first |
| `miner.cpp` `CreateNewBlock`, inside the `LOCK2(cs_main, mempool.cs)` scope (`:367`) before the selection loop | `COINBASE_FLAGS = g_yellowback ? yellowback::policy::TagScript(*g_yellowback) : CScript();` and `std::optional<yellowback::TemplateView> ybview; if (g_yellowback) ybview.emplace(g_yellowback->TemplateView());` | `COINBASE_FLAGS` is otherwise never assigned (`main.cpp:134`); every reader holds `cs_main` once the `-gen` loop's `IncrementExtraNonce` (`:832`) is wrapped in `LOCK(cs_main)` (K17); `TemplateView` is an RAII holder of `cs_yellowback` (taken after `mempool.cs`, the lock order below) owning an `OverlayStateView` over the index at the tip, released when `CreateNewBlock` returns (N25) |
| `miner.cpp` `CreateNewBlock`, in the selection loop immediately before `UpdateCoins(tx, view, nHeight)` (`:582`) | `if (ybview && !yellowback::policy::FilterTemplate(*ybview, tx, nHeight)) continue;` | must precede `UpdateCoins` or descendants see phantom coins; `FilterTemplate` applies the transaction to the overlay view when it keeps it (TPL-1/2) |
| `miner.cpp` `CreateCoinbaseTransaction` (`:327`) | `mtx.vin[0].scriptSig = (CScript() << nHeight << OP_0) + COINBASE_FLAGS;` | `IncrementExtraNonce` (`:720`) already appends `COINBASE_FLAGS`; this makes `coinbasetxn` match; `bad-cb-height` is a prefix check (`main.cpp:4477-4481`), `bad-cb-length` ≤ 100 (`:1456`) holds with ≥ 50 bytes to spare |
| `rpc/mining.cpp` `getblocktemplate` (`:742-767`), every edit under `if (g_yellowback)` (N10) | emit `coinbaseaux` with `coinbasetxn`; add `"coinbase/append"` to `aMutable` (`:747-752`); add `result.pushKV("yellowback", g_yellowback->TemplateInfo())` | informational; BIP 22 fields; without the flag the response is v4.5.0's, key for key (`yellowback_stockparity.py`) |
| `init.cpp` after the index is constructed and `SyncToChain` has run (fork `init.cpp:1881-1897`, after wallet load) and before the notifier thread is started (pristine `:1844`, Step 8) and `ThreadImport` (pristine `:1883`, Step 10; fork `:1952`) — ordering per M7, N39 | if `-yellowback`, `-yellowbackenforce=0`, `Rejected` non-empty and `chainActive.Tip() != nullptr`: `{ LOCK(cs_main); for (hash : index.Rejected()) if (mapBlockIndex.count(hash)) ReconsiderBlock(state, mapBlockIndex[hash]); }` then `ActivateBestChain(state, chainparams)` outside the lock, then clear `Rejected` | `ReconsiderBlock` needs only `cs_main` and a loaded block index (`main.cpp:3970-3999`) and compares against `chainActive.Tip()` (`:3981`); the exact pattern of `rpc/blockchain.cpp:1497-1509` (K21); it runs **before** the notifier thread exists, so the reorg it triggers is delivered to the wallet afterwards by the normal `ChainTip` path; a `Rejected` hash absent from `mapBlockIndex` (a block never stored after `-reindex`) is skipped and cleared (`killswitch_rejected_hash_not_in_mapblockindex`) |
| `init.cpp` index construction (the prototype's placement, fork `:1881-1897`: after wallet load, before the kill-switch loop, the notifier thread (`:1844`) and `ThreadImport` (`:1883`); `if (fPruneMode) InitError`, construct, `SyncToChain()`, `RegisterValidationInterface`) | as the prototype plus payout key (P2PKH only; defaults from `-mineraddress` when that is transparent), signal flag, quote max age, enforce flag, template policy, `-yellowbackrequirehealthy`, `-yellowbackenforceuntil` (regtest) | index exists only after `RewindBlockIndex` (`:1695`) and `VerifyDB` (`:1718`) have run, so neither touches it; a rewind can leave the on-disk index ahead of the chain, which `SyncToChain` undoes (K22) |
| `CValidationInterface::ChainTip` / `SyncTransaction` (the prototype's subscriber) | wallet lock reconciliation only (coin-locking stages ii–iii of §4.6: pre-lock on notify, reconcile after apply); reads the index under `cs_yellowback`, never applies state | as the prototype; the notifier thread still never takes `cs_main` (it must not, in block callbacks) |

**Lock order** (N25, a recorded decision): `cs_main → cs_wallet → mempool.cs → cs_yellowback`.
Every hook method is called with `cs_main` held (asserted) and takes `cs_yellowback` inside;
`TemplateView()` returns an RAII holder of `cs_yellowback` that `CreateNewBlock` keeps for the
selection loop, inside its `LOCK2(cs_main, mempool.cs)`; `RemoveInvalidVaultSpends` takes
`mempool.cs` before `cs_yellowback`; **no RPC may take `mempool.cs` after `cs_yellowback`** —
Phase 8 greps every `LOCK(mempool.cs)`/`LOCK2` in `src/rpc/yellowback*.cpp` and `src/yellowback/`
against that rule. `CheckConnect` and `CommitConnect` share one evaluation: `CheckConnect` caches
`{(blockHash, indexTipHash, paramsHash) → BlockEvaluation}` under `cs_yellowback`; `CommitConnect`
reuses it when the key matches, else re-evaluates (N9).

**Idempotence and startup** (`SyncToChain`, carried over from the prototype): undo while the stored tip is not in
`chainActive` (this now also covers "index ahead of the flushed chainstate after a crash", V2),
then apply forward from disk; wipe and rebuild on schema/network mismatch, missing undo, or
`-reindex-yellowback`. During `-reindex` the index is wiped at start and rebuilt by the
`ConnectBlock` hook as blocks connect in order (`LoadExternalBlockFile → ProcessNewBlock →
ActivateBestChain → ConnectTip`, `main.cpp:5441-5532`, `:3829`); BLK-2 suppresses rejection under
`-reindex`/`fImporting`/IBD, so the rebuilt index is identical whatever the node once rejected and
a plain `-reindex` is the runbook's reindex (N2; `-yellowbackenforce=0` is optional belt-and-braces, M12).

### 4.4 Miner integration

**Tag construction (MINER-1..3).** The index holds `{quote, sourceMask, receivedAt}` set by
`yed_setquote`, which stamps `receivedAt = GetTime()`. `policy::TagScript(index)` calls `GetTime()`
once and passes it to `BuildTagScript(index, now)`, which returns `CScript() << tagBytes` with
`priceMicroUsd = quote` if `now − receivedAt ≤ -yellowbackquotemaxage`, else `0` (signal-only) if
`-yellowbacksignal`, else an empty script; `flags.bit0 = -yellowbacksignal ∧ -yellowbackenforce`
(L3); `payoutKey` from `-yellowbackpayoutaddress` or, failing that, a P2PKH `-mineraddress` (K22;
required to emit any tag; the wallet's `getnewaddress` is fine). The clock here is the miner's own,
deciding what *it* publishes — never read by a rule (§3.10, M11).

**Template filter (TPL-1..3).** `TemplateView()` = an RAII holder of `cs_yellowback` owning an
`OverlayStateView` over the index at the tip (N25); `FilterTemplate(view, tx, nHeight)` (reads
`templatePolicy` from the index) runs `ProcessTx` on the overlay in dry-run, returns false for a
block-invalid vault spend (any activation state), for a vault spend without the MP-1 expiry, and,
in strict mode, for a VOID mint, a burning transfer, a claim-path sweep of a VOID vault or a
non-wallet selector (TPL-2); on true it commits the transaction's effect to the overlay so later
candidates see it. Cost: one dry run per Yellowback-relevant candidate. The template's own
coinbase does not exist during selection (`CreateCoinbaseTransaction` runs after the loop) and
need not: the tag at `H` never affects rules at `H`; only `Snapshots[≤ H−1]` do.

**`getblocktemplate`.** On a node with `-yellowback` (otherwise v4.5.0's response, N10) returns
`coinbasetxn` with the tag in its scriptSig, `coinbaseaux.flags` = the tag push in hex, `mutable`
including `"coinbase/append"`, and `TemplateInfo()` (Phase 4):

```
"yellowback": { "tag": "<hex>", "kind": "quote"|"signal"|"none", "priceMicroUsd": n,
                "quoteAgeSeconds": n, "signal": bool, "payoutAddress": "s1…",
                "registered": bool, "eligible": bool, "activation": "signaling"|"locked_in"|"active",
                "signalCount": n, "enforcing": bool, "valveTripped": bool, "sunset": bool,
                "healthy": bool, "templatePolicy": "strict" }
```

**Regtest `generate`.** Goes through `CreateNewBlock` + `IncrementExtraNonce`
(`rpc/mining.cpp:216-222`), so a regtest node with a payout address and a quote mines tagged
blocks with no further code (V25).

### 4.5 RPC surface (`rpcversion = 2`)

All commands gated by `fExperimentalYellowback`. While the index is unhealthy every command refuses
except `yed_getinfo`, `yed_getblockverdict`, `yed_gettag`, `yed_decodepayload` and `yed_setquote` —
the diagnostic and operator commands the runbook needs (M8). Node context (`src/rpc/yellowback.cpp`):

| Command | Purpose |
|---|---|
| `yed_getinfo` | `{rpcversion: 2, enabled, network, height, blockhash, chainHeight, startHeight, healthy, unhealthyReason, enforcing, valveTripped, sunset, rejectedBlocks, suppressedBlocks (BLK-2 clause 3 accepts, L11), templatePolicy, abandoned, activation: {status, lockInHeight, activateHeight, signalCount, window}, miner: {payoutAddress, signal, quoteKind, quoteAgeSeconds, registered, eligible}, params: {startHeight, enforceUntilHeight, sigmaRefBps, supplyCapBps, refLag, refWindow, grace, payeeWindow, feeMinZat, feeBps, tokenValueZat, feeZat (network fee), valveBlocks, abandonBlocks, windows: {fast, mid, slow, signal}, minFill: {fast, mid, slow}, classes: [{class: "A"\|"B"\|"C", minBlocks, maxBlocks, baseRatioBps}], policy: {penaltyBlocks, accuracyWindow, tiltBps, preferredPayee}}}` — `height`/`blockhash` are always the tip (V2); `enforcing` is false under the kill switch, the valve (`valveTripped`, N11/L7) or the sunset (`sunset`, L8); `abandoned` is the §4.6 predicate (L10); from Phase 8 also `lockedOutputs`, `protectedByIndex` (H10, N39) |
| `yed_getstatehash [height]` | unchanged (§3.6 *State hash*) |
| `yed_getstats` | `{height, supplyCents, collateralZat, activeVaults, voidVaults, closedVaults, claimedVaults, unbackedCents, issuedZat, pFast, pMid, pSlow, pMint, pClaim (null when undefined), sigmaMultBps, globalRatioBps (null when no supply), supplyCapCents (null when no cap), haltMask: [names], mintingAllowed}` |
| `yed_getprice [height]` | `{height, pFast, pMid, pSlow, pMint, pClaim (null when undefined), fill: {fast: {quoteTags, window, minFill}, mid: {…}, slow: {…}}, tag: {…as yed_gettag}}` |
| `yed_getactivation` | `{status, lockInHeight, activateHeight, signalCount, window, threshold, participationFloor, enforcementFloor, enforcementResume, mintHalted, enforcementSuspended, enforcing, valveTripped, sunset, enforceUntilHeight, history: [{height, signalCount}]}` — `history` samples every `SIGNAL_WINDOW/8` blocks ending at the tip (8 rows) |
| `yed_listminers [height] [window]` | one row per `payoutKey` with a quote tag in `(height − window, height]` (`window` defaults to `PAYEE_WINDOW`; the launch bar uses `2016`, L4): `{payoutAddress, lastTagHeight, lastQuote, quoteTags, share (bps of quote-tagged blocks in the window), registered, eligible, penalizedUntil, accuracyBps, quoted, inBand}` |
| `yed_gettag <height\|blockhash>` | string argument (all digits ⇒ height); decodes the coinbase tag of that block: `{found, kind, version, signal, priceMicroUsd, sourceMask, payoutAddress}` |
| `yed_setquote <priceMicroUsd> <sourceMask>` | miner control: store the quote (`0` clears) with `receivedAt = GetTime()`; requires RPC auth; returns `{priceMicroUsd, sourceMask, receivedAt, nextTag: {kind, signal, payoutAddress}}` |
| `yed_getfeepayee <refHeight> <collateralZat> [selectorHex]` | `{eligible: [payoutAddress…], feeZat, default: {payoutAddress, weight}, preferred (if configured and eligible), policy: {penaltyBlocks, accuracyWindow, tiltBps}}` — `E(refHeight)`, FEE-1 for that collateral, the FEE-W choice for the selector and the L6 values used (for external builders) |
| `yed_getvault <txid>` | `{txid, vout, status, ownerPubKey, ownerKeyId, ownerAddress, termClass, lockHeight, claimHeight, collateralZat, collateral, mintedCents, mintHeight, refHeight, feePaidZat, closeHeight, closingTxid, burnedCents, unbacked, claimable, underwaterAt, voidReason, sweepBefore}` — the prototype's `tier`/`rosterIndex`/`errBpsAtClose` are gone; `sweepBefore` (= `claimHeight`) is present for a VOID vault (its claim path is unpoliced after `claimHeight`, K3) and for an ACTIVE vault whenever abandonment holds (L10), absent otherwise |
| `yed_listvaults [status] [count] [skip]` | paged (the `rosterIndex` argument is gone; `rpc/client.cpp` updated) |
| `yed_listclaimable` | ACTIVE vaults past `claimHeight` that are underwater at the tip snapshot: `[{vault, ownerAddress, collateralZat, mintedCents (the burn), feeZat, claimHeight, underwaterAt, pClaim}]` |
| `yed_gettxinfo <txid>` | `{txid, height, type, path, verdict, yedIn, yedOut, burned, feeZat, payee, assigned: [{vout, cents}], spentTokens: [outpoint], closedVaults: [outpoint], expired}` (`expired` for a wallet transaction past its `nExpiryHeight` in neither `TxLog` nor the mempool, §4.6) |
| `yed_decodepayload <hex>` | unchanged (version 2) |
| `yed_validaterawtransaction <hex>` | `{valid, verdict, type, path, yedIn, yedOut, burned, feeZat, payee, blockValid, wouldBeRejected, mempoolExpiryOk, unconfirmedInputs: [outpoint]}` — dry run of §3.8 at the tip; for a vault spend `blockValid` (RED-1..4) and `wouldBeRejected` (whether an enforcing miner refuses it, incl. the MP-1 expiry bound); `VerifyAllInputs` for the scripts |
| `yed_getblockverdict <blockhash>` | `EvaluateBlock` on a stored block: `{blockInvalid, reason, enforcementOn, transactions: [{txid, type, path, verdict, yedIn, yedOut, feeZat, payee, closedVaults}]}`; used to explain a rejection. **Precondition (N12):** refuses (`verdict-parent-not-tip`) unless the block's parent is the index tip, or the block is in `Rejected` with the current tip as its parent — the state at any other parent would need an undo replay |
| `yed_estimatecollateral <cents> <lockBlocks> [priceMicroUsd]` | `{requiredZat (null when unsatisfiable), termClass, lockHeight, claimHeight, minRatioBps, baseRatioBps, sigmaMultBps, pMint, refHeight}` at the current snapshot (or the given price) |
| `yed_estimatefee <collateralZat>` | `feeZat` |
| `yed_gethistory <from> <to>` | the `Snapshots` records (§3.6 fields, `haltMask` decoded) for `from ≤ h ≤ to`, at most 2,016 per call |

Wallet context (`src/rpc/yellowbackwallet.cpp`): `yed_getnewaddress`, `yed_validateaddress`,
`yed_getbalance`, `yed_listunspent`, `yed_send`, `yed_sendmany`, `yed_lockcoins` unchanged;
`yed_listtransactions [count] [skip]` rows are `{txid, height, confirmations, type ∈ {mint, send,
receive, burn, redeem, claim, claimed, sweep}, verdict, path, yedIn, yedOut, burned, amountCents,
feeZat, payee, unbacked, expired}` (§4.8 displays them, M8, N27); `yed_mint <cents> <lockBlocks>
[from]` (returns `{txid, vault, termClass, lockHeight, claimHeight, collateralZat, feeZat, payee,
fundedFrom, warning}` — `warning` is the keypool-low nag); `yed_redeem <vaultTxid> [to]` (one
step, V24; on an ACTIVE vault the owner-path redemption, returns `{txid, burnedCents, feeZat,
payee, collateralOut, to}`; on a **VOID** vault the §3.5 VOID RELEASE with `burnedCents = 0`,
`feeZat = 0`, `payee = null` (L14); `vault-not-active` only for CLOSED/CLAIMED); `yed_claim
<vaultTxid> [to]` (same return shape); **`yed_sweep <vaultTxid> <acknowledgement> [to]`** (L10;
`acknowledgement` must be exactly `I understand this leaves YED unbacked`; builds the §3.5 SWEEP
only when `yed_getinfo.abandoned` is true — the §4.6 predicate, never the node's own
`-yellowbackenforce` — signs the owner path and commits through the node's own mempool, which
admits it under abandonment (L13); returns `{txid, hex, collateralOut, to, unbackedCents}`, the
`hex` so the owner can also submit it to any other node); `yed_listpositions` rows =
`yed_getvault` + `{canRedeem, canClaim, canSweep}` (`canRedeem` is true for an ACTIVE or VOID
vault at or past `lockHeight`).
Later, from Phase 8 (H3, H5, H10): `yed_estimatesend`, `yed_unlockcoin`, and
`yed_getinfo.lockedOutputs`/`protectedByIndex`. **`rpcversion` rule:** additions (new commands,
new fields) never bump it; a removal or a shape change does, so Phase 8's additions land under
`rpcversion = 2` (M8). **The contract is the document:** `doc/yellowback-rpc.md` v2 is written
*before* the RPC code in Phase 3 (node context) and at the start of Phase 6 (wallet context),
lists every field above and every field the wallet reads (the file's own rule,
`yecwallet-dd/src/yellowbackrpc.h:7-11`), and the wallet's `RPC_VERSION` goes to 2 in Phase
7b-a's first commit — not in Phase 0, because the node reports `rpcversion 1` until Phase 3 and
the wallet refuses a mismatch (N27).

**Error identifiers (M8).** Every refusal is `RPC_INVALID_PARAMETER` (bad argument),
`RPC_WALLET_ERROR` (funds, locking) or `RPC_VERIFY_REJECTED` (a rule) with a message that begins
with a stable identifier the wallet fork matches, shaped like the prototype's `doc/yellowback-rpc.md`:

| Identifier | Raised by | When |
|---|---|---|
| `yellowback-unhealthy` | every gated command | the index is unhealthy (`unhealthyReason` follows) |
| `mintpol-not-active`, `mintpol-no-price`, `mintpol-participation`, `mintpol-global-ratio`, `mintpol-divergence`, `mintpol-cap` | `yed_mint` | MINTPOL-1, one per halt bit and the cap |
| `mint-unsatisfiable` | `yed_mint`, `yed_estimatecollateral` | `requiredZat > MAX_MONEY` (K14) |
| `mint-bad-lock` | `yed_mint` | `lockBlocks` outside every class or `lockHeight + GRACE ≥ LOCKTIME_THRESHOLD` |
| `vault-not-found`, `vault-not-active`, `vault-not-owned` | `yed_redeem`, `yed_claim`, `yed_getvault` | as named; `vault-not-active` means CLOSED or CLAIMED — a VOID vault is releasable by `yed_redeem` (L14) |
| `vault-locked` | `yed_redeem` | tip below `lockHeight` (ACTIVE and VOID alike) |
| `claim-not-yet` | `yed_claim` | tip below `claimHeight` |
| `claim-not-underwater` | `yed_claim` | RED-4 would fail at the reference snapshot |
| `sweep-not-abandoned` | `yed_sweep` | the abandonment predicate (§4.6) is false: enforcement is on, or suspended for less than `ABANDON_BLOCKS` (L10, L12 — a passed sunset alone is not abandonment) |
| `sweep-acknowledgement-missing` | `yed_sweep` | the second argument is not the exact acknowledgement string |
| `change-floor` | `yed_send`, `yed_sendmany`, `yed_redeem`, `yed_claim` | YED change would lie in `(0, MIN_OUTPUT)` (§4.6); the message names the nearest workable amounts (structured by H2 in Phase 8) |
| `not-a-yellowback-address` | `yed_send`, `yed_sendmany`, `yed_validateaddress` | the recipient is not a `ye…`/`yt…`/`yr…` address of this network |
| `verdict-parent-not-tip` | `yed_getblockverdict` | the block's parent is not the index tip and the block is not a rejected child of it (N12) |
| `insufficient-yed` | `yed_redeem`, `yed_claim`, `yed_send` | wallet YED below the burn or amount |
| `mempool-check-failed:<verdict>` | `yed_redeem`, `yed_claim` | `MempoolCheck` returned the named RED verdict (K7) |
| `fee-no-eligible-payee` | `yed_getfeepayee` | `E(R)` empty (FEE-0; not an error for the wallet, which omits the output) |
| `quote-out-of-range` | `yed_setquote` | price outside `[PRICE_MIN, PRICE_MAX]` and not `0` |
| `no-payout-address` | `yed_setquote` | the node has no payout key and so can emit no tag |

**`rpc/client.cpp` conversion rows (Phase 3; index-based, so every numeric argument is listed):**
`yed_getstatehash 0`, `yed_getprice 0`, `yed_listminers 0,1`, `yed_setquote 0,1`,
`yed_getfeepayee 0,1`, `yed_listvaults 1,2` (was `1,2,3`), `yed_estimatecollateral 0,1,2`,
`yed_estimatefee 0`, `yed_gethistory 0,1`, `yed_mint 0,1`, and unchanged from the prototype
`yed_listtransactions 0,1`, `yed_send 1`, `yed_sendmany 0` (`client.cpp:159-164`); Phase 8 adds
`yed_estimatesend 0`, `yed_unlockcoin 1`; `yed_gettag`, `yed_redeem`, `yed_claim` and `yed_sweep`
have none (all strings). **Rebuild `ycash-cli` after every `client.cpp` change** — the
conversions live in the CLI, and a stale CLI passes a number as a string (N27).

Configuration: `-yellowback`; `-yellowbackenforce` (default 1); `-yellowbackpayoutaddress=<s1…>`
(defaults to a P2PKH `-mineraddress`); `-yellowbacksignal` (**default 0 on mainnet, 1 on testnet
and regtest**, L4; effective only with `-yellowbackenforce=1`, L3); `-yellowbackquotemaxage=<sec>`
(default 1800); `-yellowbacktemplatepolicy=strict|consensus`; `-yellowbackrequirehealthy` (default
0); `-yellowbackpreferredpayee=<s1…>`; `-yellowbackpayeepenaltyblocks`,
`-yellowbackpayeeaccuracywindow`, `-yellowbackpayeetiltbps` (FEE-W overrides, defaults from §3.1,
L6); `-reindex-yellowback` (also clears `Rejected`); `-yellowbackfee` (clamped to ≥ `DEFAULT_FEE`, §3.1); `-yellowbackmintlag`
(`REF_LAG`, §3.1); `-debug=yellowback`; regtest only: `-yellowbackstartheight`, `-yellowbacksigmaref`,
`-yellowbacksupplycapbps`, `-yellowbackenforceuntil` (L8; 0 = none); test only (regtest, Phase 3):
`-yellowbacktestfault=storage:<check|commit|undo>[:<height>]` — the named hook throws a
`dbwrapper_error` on its first call at that height (default: its next call), once; the fault is
consumed and logged — and `-yellowbacktestfault=template` (TPL-3's unit companion; makes
`FilterTemplate` disagree with `EvaluateBlock` once) and `-yellowbacktestfault=novalve` (disables
ACT-7 so `yellowback_runbook.py` can reach the `MAX_REORG_LENGTH` shutdown). Unit tests use
`testBeforeApply` (`index.h:85`) instead (N25). Removed:
`-yellowbackgenesisanchor`, `-yellowbackgenesisroster`, `-yellowbacksupplycap`.

### 4.6 Wallet behaviour

The prototype's wallet rules stand in every respect that survives:

- **Coin locking (three stages).** A wallet's own 0-conf outputs are trusted and spendable at once
  (`CWalletTx::IsTrusted`, `ref/ycash/src/wallet/wallet.cpp:4842-4867`), so a plain `sendtoaddress`
  issued right after a Yellowback command could burn fresh YED. Therefore (i) `yed_mint`/`yed_send`/
  `yed_redeem`/`yed_claim` call `LockCoin` on every YED output of the transaction they are about to
  commit **before** `CommitTransaction`; (ii) the index's `SyncTransaction` override pre-locks every
  output a well-formed payload assigns to a script that `IsMine`, for mempool and block transactions
  alike; (iii) after every applied block and at startup, `ChainTip` reconciles against the state:
  every `Tokens` outpoint that is mine is locked, a pre-lock is released **only** when its
  transaction is confirmed and the applied verdict assigned it no cents (a VOID mint's token output,
  an output that turned out non-Yellowback), and spent outpoints are pruned. **Nothing is unlocked on
  disconnect**: a disconnected transaction returns to the mempool where its outputs are trusted
  0-conf again, so a lock stays until the outpoint is confirmed-and-worthless or spent. Locks are
  in-memory (`setLockedCoins`) and re-applied at startup. Vault outputs need no lock (a P2SH whose
  redeem script the wallet does not hold is never `IsMine`). `yed_send`/`yed_redeem`/`yed_claim` select YED and
  vault inputs from the index, skipping outpoints the wallet reports spent by its own unconfirmed
  transactions (`CWallet::IsSpent`); YEC inputs come from `AvailableCoins`, which skips locked coins.
- **One fresh key per position.** `yed_mint` draws one fresh keypool key and uses it both as the
  vault `ownerPubKey` and for the token output, so a position depends on exactly one key. A vault
  is mine iff `HaveKey(ownerPubKey.GetID())`; a token output is mine iff `IsMine(scriptPubKey)`.
  Nothing Yellowback-specific is written to `wallet.dat`; wallet restore = restore keys + the index.
- **Confirmed-only inputs.** Every input of every Yellowback transaction is confirmed: YED inputs
  from the index, YEC inputs via `AvailableCoins(..., nMinDepth = 1)` — the wallet's own 0-conf and
  *expired* outputs are otherwise selectable (`wallet.cpp:5038-5052`) and a transaction chained on
  them may never confirm. The state machine still allows in-block chaining.
- **Expiry.** A Yellowback transaction that expires unmined is dropped by the mempool at the next
  block (`main.cpp:3636`) but stays in the wallet at depth 0 and is rebroadcast like any other. An
  expired MINT or TRANSFER leaves no index trace and its stage-(i) locks name outputs that never
  exist (harmless); the user re-runs the command. `yed_gettxinfo` reports `expired` for a wallet
  transaction past its `nExpiryHeight` that is in neither `TxLog` nor the mempool.
- **Sapling funding and destinations.** `yed_mint … ys1…` selects that address's confirmed Sapling
  notes largest-first (as `z_sendmany`), fetches witnesses and the anchor under `cs_main`/`cs_wallet`,
  releases every lock for `TransactionBuilder::Build()` (one spend proof per note), then re-locks to
  commit; the notes are not `LockNote`d, exactly as `z_sendmany` does not. `yed_redeem … ys1…` builds
  the same way with an unsigned vault input and unsigned YED inputs, proves the single Sapling output
  with no lock held, then re-locks to owner-sign `vin[0]` and `SignSignature` the YED inputs. Either
  RPC blocks for the proving time (no operation id). Built on the three-method
  `TransactionBuilder` extension of §4.1.
- **Change floor.** `yed_send`/`yed_sendmany`/`yed_redeem`/`yed_claim` refuse to build a transaction
  whose YED change would lie in `(0, MIN_OUTPUT)` (= $1.00): XFER-1 could not assign it and it
  would burn. The error (`change-floor`) names the smallest amount that works (Phase 8's H2/H3
  make the message structured).
- **The `wallet.dat` backup rule.** Ycash 4.5 transparent keys are a random keypool, not HD (the
  HD seed serves Sapling only), so a vault owner key lives only in `wallet.dat`: the user
  documentation states **back up `wallet.dat` after minting** — a backup taken before the keypool
  was consumed does not contain the vault key — and `yed_mint` warns when the keypool is low.
  Ycash's wallet encryption is experimental and gated behind `-developerencryptwallet`
  (`ref/ycash/src/wallet/rpcwallet.cpp:2127,2160`), so documentation must not present it as
  protection for vault keys; the stated custody rule is full-disk encryption, RPC on localhost only,
  and an offline copy of `wallet.dat`.
- **Transaction building.** Start from `CreateNewContextualCMutableTransaction(consensus,
  chainActive.Height() + 1)`, set `nExpiryHeight` explicitly (never `-txexpirydelta`), choose YEC
  inputs smallest-first until they cover outputs plus the flat `YELLOWBACK_FEE`, change via
  `CReserveKey`, sign P2PKH inputs with `SignSignature(..., SIGHASH_ALL, branchId)` and the vault
  input manually, `EnsureWalletIsUnlocked` first, commit with `CommitTransaction`.

With these changes:

- **Mint gate (MINTPOL-1, v2).** Build only when `Snapshots[R].activation == ACTIVE`,
  `haltMask == 0`, and the cap has room; refuse otherwise with the `mintpol-*` identifier of §4.5. Show the class, the σ multiplier, the exact
  collateral, the enforcement fee and its payee before signing.
- **Redeem and claim in one step (V24).** `yed_redeem`/`yed_claim` run `MempoolCheck` — the same
  predicate MP-1 applies, `EvaluateBlock` over a one-transaction pseudo-block at `tip + 1` — and
  refuse unless it passes; only then `CommitTransaction`, which records the transaction before it
  tries the mempool (`wallet.cpp:5725, 5743`) and must therefore never be reached by a transaction
  MP-1 would refuse (K7). No pending record exists, so there is nothing to abort; an expired
  transaction is simply re-run (the expiry rule above).
- **Claims.** `yed_listclaimable` is the source; a claim spends the claimant's own YED (locked
  coins, same selector as a transfer) and pays the fee from the collateral.
- **Fee payee.** The wallet picks a payee from `E(R)` by FEE-W (`state::DefaultPayee`, with the
  node's L6 values) or the configured preference, and checks membership in `E(R)` with the same
  function the validator uses (`state::EligiblePayees`), so the wallet and the validator cannot
  disagree on validity.
- **VOID vaults (K3, L14).** A failed mint leaves its collateral in a VOID vault with no debt;
  nothing polices its spend. `yed_redeem` on a VOID vault at or past `lockHeight` builds the
  §3.5 VOID RELEASE (owner path, no burn, no fee, no payload) and returns `burnedCents = 0`;
  `yed_getvault`/`yed_listpositions` show `sweepBefore = claimHeight` on every VOID vault because
  after that height its claim path is anyone-can-spend, and the GUI's Vaults row offers
  **Release**. Before `lockHeight` the command refuses with `vault-locked`.
- **Abandonment and the owner sweep (L10, L12).** The chain shows **abandonment** when
  `Snapshots[tip].haltMask.ENFORCEMENT` has been set continuously for at least `ABANDON_BLOCKS`
  (= 2 · `SIGNAL_WINDOW`, 4,032 on mainnet, 128 on regtest — two full windows in which fewer than
  half of blocks signalled). That is the whole predicate: the signal bit is carried by tags
  every release reads alike, so `YellowbackIndex::IsAbandoned()`, computed from `Snapshots`
  alone, answers the same on every node of every release — which a clause about "the sunsets
  this release knows" could not (a stale release would declare abandonment while upgraded pools
  still enforce, L12). A sunset with no successor reaches the same state on its own: every
  honest tag drops its signal bit past the sunset (MINER-1), `ENFORCEMENT` sets within a window,
  and abandonment follows `ABANDON_BLOCKS` later. It is **never** gated on the node's own
  `-yellowbackenforce`, its valve state or its health. While it holds, MP-1 and TPL-1/2 stand
  down for vault spends (L13), so the sweep below is admitted by the owner's own node, relayed,
  and mined by any pool that still runs the module.
  While abandonment holds: `yed_getinfo.abandoned = true`; `yed_getvault` and
  `yed_listpositions` show `sweepBefore = claimHeight` on every ACTIVE vault and `canSweep`; and
  `yed_sweep <vaultTxid> <acknowledgement> [to]` builds the §3.5 SWEEP — an owner-path spend with
  no burn and no fee — signs it, commits it through the node's own mempool (admitted under
  abandonment, L13) and returns its `hex` as well. It refuses with `sweep-not-abandoned`
  otherwise (enforcement on, or suspended for less than `ABANDON_BLOCKS`; a passed sunset alone is
  not abandonment, L12), and with `sweep-acknowledgement-missing` unless the second argument is
  the exact string `I understand this leaves YED unbacked`. The transaction is a rule-breaking
  vault spend by design (it fails RED-1): a node on which enforcement is still on — one that does
  not see abandonment, i.e. a node on a different chain — never mines it; on the abandoned chain
  every node that runs this release admits, relays and mines it like any other transaction, and
  so does every stock node; the vault is then `CLOSED, unbacked = true`, `Totals.unbackedCents`
  grows by the debt, and the row shows `type = "sweep"`. What the owner is told: after `claimHeight` the vault's claim path is
  anyone-can-spend and, with nobody enforcing RED-4, whoever mines first takes the collateral —
  sweep before `claimHeight` or lose it; the claim path stays open to everyone, so the race is
  fair; the YED that was minted against the vault is unbacked from then on (§8.1).

### 4.7 Miner node operations (what a pool operator runs)

A pool runs its normal `ycashd` from the `ycash-dd` release with:

```
experimentalfeatures=1
yellowback=1
yellowbackpayoutaddress=s1…        # where enforcement fees arrive; must be a P2PKH (s1…) address
yellowbacksignal=1                 # default on testnet/regtest; default 0 on mainnet until the signalling announcement (L4)
yellowbackenforce=1                # default; set 0 to leave the enforcing set (then restart)
```

plus the quote agent (§5) pointed at the node's RPC. On mainnet the first release leaves
`yellowbacksignal` at its default of 0 until the signalling announcement (L4). Monitoring is
`yed_getinfo.miner` (quote kind and age, registered, eligible), `yed_listminers` (own accuracy and
penalty), `yed_getactivation`, and
`yed_getinfo.rejectedBlocks` — a rising count with the network *not* following this node is the
signal to check `yed_getblockverdict` and, if the node is wrong, to restart with
`yellowbackenforce=0` (V13; a node that is more than 99 blocks behind — `MAX_REORG_LENGTH`, which
counts the active chain to disconnect whoever mined it, N15 — must `-reindex` first; plain
`-reindex` is safe because BLK-2 never rejects while reindexing, N2). **Expected after any
rejection (N11, corrected by P1):** once the stock chain is six blocks ahead the **work valve**
trips (ACT-7, L7) and the node raises `Yellowback: work valve tripped at height H (rejected root
…); enforcement off until restart` through `-alertnotify` and `getinfo.errors` (the stock
"invalid chain at least ~6 blocks longer" warning does not fire in this situation — it counts
only blocks the node stored, and descendants of a rejected block are refused as headers);
`yed_getinfo.enforcing == false`, `valveTripped == true`, the node reorganises onto the heavier
chain at the next block the network announces (P3) and its tags have lost the signal bit. The
operator's job is then to find out *why* the network did not follow — a bug in this node
(`yed_getblockverdict`), a stale release, a real enforcing minority — and to **restart** to
re-arm the valve once that is understood; nothing else re-arms it. **Expected after an outage
(L11):** a node that catches up after a partition or a restart never rejects a block the network
has already built six blocks on; it accepts it, logs `catch-up: accepted rule-breaking block …`
and counts it in `yed_getinfo.suppressedBlocks` with enforcement still on — a non-zero count is
worth a look at `yed_getblockverdict` but needs no action; a node restarted after more than a
day offline is in initial block download until its tip is a day old and rejects nothing until
then (N2). The pool's payout address is a hot-wallet key of the node it runs on: back up that
`wallet.dat` like any other. `yed_getinfo.sunset == true` means this release's `ENFORCE_UNTIL_HEIGHT` has
passed (L8): the node tags and evaluates but rejects nothing until upgraded; the log says
"upgrade required". `healthy == false` is an alert (the pool keeps mining unpoliced
templates unless `-yellowbackrequirehealthy` is set, K24). `-prune` is refused (the index needs every block on disk). `-datacarrier` stays default (`-datacarrier=0` on a relaying node drops
every `OP_RETURN` transaction, `policy.cpp:52`; the index is unaffected either way).
The runbook is `doc/yellowback-mining.md` (Phase 6).

### 4.8 YecWallet (`yecwallet-dd`)

The prototype's tab structure stays (one Yellowback tab in YecWallet with the mint, send, positions,
redeem and history functions, over the `yed_*` RPC contract only; `mapping.md` §12); the changes are the ones V24 and the
proposal force:

| Screen | Change |
|---|---|
| Status banner | adds the activation state (`signaling n/2016`, `locked in, active at H`, `active`), the participation halt, `enforcement suspended`, `valve tripped — restart the node` (L7), `enforcement sunset — upgrade` (L8) and `abandoned` (L10); `suppressedBlocks > 0` is shown as an information line, not a warning (L11); "Yellowback unavailable" also when `healthy == false` as before |
| Overview | shows `P_mid` as the headline YEC/USD, `P_mint`/`P_claim`, the σ multiplier, the global ratio and cap headroom, every halt reason by name |
| Mint | lock length (days) with the class and base ratio derived live; exact collateral; enforcement fee and payee; gate reasons per MINTPOL-1; the after-mint backup nag stays |
| Vaults | columns `claimHeight`, `claimable`, `unbacked`; VOID rows explain the verdict (`voidReason`), show `sweepBefore` (K3) and offer a **Release** action at or past `lockHeight` (one `yed_redeem` call, L14; the confirmation says no YED is burned and no fee is paid); while `abandoned` every ACTIVE row shows `sweepBefore` and a **Sweep** action whose dialog carries the L10 acknowledgement text verbatim and calls `yed_sweep` |
| Redeem | the wizard is replaced by a confirmation dialog (burn, fee, collateral out, destination) and one `yed_redeem` call; the pending-redemption watcher is removed |
| **Claim (new)** | `yed_listclaimable` table; confirmation shows the YED to burn, the fee and the collateral received; one `yed_claim` call |
| Transactions | `claim`, `claimed` and `sweep` types; `unbacked` badge on a vault closed without its burn; `expired` badge from `yed_listtransactions.expired` (N39) |
| Settings | the operator-endpoint box and `verifyEndpoints()` are removed; display unit, advanced and backup-nag stay |

`yellowbackrpc.h` goes to `RPC_VERSION = 2` in Phase 7b-a's first commit (N27) and drops `GETROSTER`, `SUBMITREDEEM`,
`ABORTREDEEM`, `Roster::*`, `Info::ANCHOR`, `Info::ROSTER_INDEX`; `Settings` drops the endpoint
pair. Offline QTest cases (fake `Connection`, N28): the status banner for each
`activation.status`, `enforcementSuspended`, `valveTripped`, `sunset`, `abandoned` and
`healthy == false`; Mint-page class derivation for lock lengths 47/48/96/97/144/145/240/241
(regtest ranges) against `params.classes`; the redeem, claim and sweep dialogs render
`burnedCents`/`feeZat`/`payee` and the sweep acknowledgement; Transactions renders `claim`,
`claimed`, `sweep`, `unbacked`, `expired`. The devnet end-to-end case reads
`YELLOWBACK_DEVNET_DIR` (the devnet's `--dir`), loads its `state.json` for the RPC port and
credentials, and `QSKIP`s when the variable is unset; CI runs only the offline cases. The wallet no longer talks to anything but the local node — the one exception the prototype had
(the federation endpoints) is gone. Copy review: the wallet must never describe Yellowback as "trustless"; the trust statement is
§8.1.

---

## 5. Quote agent and pool-integration kit (`contrib/yellowback/`)

**`yellowback_price.py`** (module): the prototype's price-source layer moved verbatim from
`yellowback_fed.py:126-637` — presets (`coingecko_simple`, `coingecko_ticker`, `nonkyc_market`,
`peatio_ticker`, `kraken_ticker`, `coinbase_ticker`, `generic`), per-source `max_age` /
`max_spread_bps` / `reject_paths` guards, BTC-pair conversion with a median of `[[btc_usd_sources]]`,
outlier filter, `min_sources`/`min_venues` fail-closed, the `sources` inspection subcommand and its
unit tests (`test_yellowback_fed.py`'s feed half). One change: the per-source average becomes a
15-minute window (`twap_seconds = 900`, the proposal's figure), volume-weighted where the venue
reports trade volume and time-weighted otherwise (recorded in §10.1).

**`yellowback-quote`** (daemon), specified (M9):

- **Loop.** Every `poll_seconds` (default 30) compute the aggregate and call `yed_setquote
  <priceMicroUsd> <sourceMask>`. After `fail_polls` (default 2) consecutive failed aggregates call
  `yed_setquote 0` so the pool goes signal-only at once (L5); the node's `-yellowbackquotemaxage`
  clock remains the backstop for a dead agent. Resume publishing on the next good aggregate.
- **RPC.** JSON-RPC over HTTP to the node with `rpc_url` and either `rpc_cookie` (the node's
  `.cookie` file, default) or `rpc_user`/`rpc_password`, using the `Node` client moved from
  `yellowback_fed.py:85-125`. An RPC failure (connection refused, auth error, `yellowback-unhealthy`)
  is logged at `error`, retried on the next poll with no backoff, and never exits the daemon; the
  exit code is non-zero only for a bad configuration.
- **Configuration** (`--conf yellowback-quote.toml`): `[node] rpc_url, rpc_cookie | rpc_user,
  rpc_password`; `[quote] poll_seconds, fail_polls, twap_seconds (900), min_sources, min_venues,
  min_btc_sources (2), outlier_bps (1000)` (the last two are the prototype's BTC-pair median and
  outlier-filter knobs, N39);
  `[[sources]]` rows with the prototype's `FEED_KEYS` (`preset, url, max_age, max_spread_bps, reject_paths,
  mask_bit`); `[[btc_usd_sources]]` as in the prototype. `mask_bit` is the source's bit in the registry below.
- **Options.** `--conf`, `--mock-price <file>` (tests and devnet; the file holds one USD price, re-read
  every poll), `--once` (one poll, exit 0 on a published quote, 1 otherwise; for cron), `--dry-run`
  (aggregate and print, no RPC), `sources` (the prototype's inspection subcommand).
- **Packaging.** Python ≥ 3.11 (`tomllib`), standard library only; installed as
  `contrib/yellowback/yellowback-quote` with a sample `yellowback-quote.toml` and sample `systemd`
  and `launchd` units in `contrib/yellowback/pool/`. No listening socket, no TLS server, nothing
  inbound.

**Source-mask bit registry (§3.2 `sourceMask`, informational):** bit 0 SafeTrade, bit 1 CoinGecko,
bit 2 CoinMarketCap (the proposal's Appendix A), bit 3 Nonkyc; bits 4–15 unassigned, allocated by
spec revision (M9). A pool sets the bits of the sources that contributed to the published quote.

**Pool kit** (`contrib/yellowback/pool/`): `README.md` explaining the three carriers (V5/V26),
the 100-byte budget and the byte-level scan, and **what an operator does, by pool type (M9):**

1. Run the release `ycashd` with the §4.7 options and the quote agent. A pool that takes
   `getblocktemplate`'s `coinbasetxn` as its coinbase needs nothing else: the tag is in it.
2. A pool that assembles its own coinbase appends the bytes of `coinbaseaux.flags` **verbatim**
   (they already begin with the `0x24` push opcode) after the BIP34 height push and before its
   extranonce and text, and keeps its own text ≤ ~55 bytes so the scriptSig stays ≤ 100.
3. A stratum layer that honours neither `coinbasetxn` nor `coinbaseaux.flags` uses the per-stack
   note or patch from the Phase 7 survey (§12 Q9: node-stratum-pool lineage such as s-nomp/z-nomp,
   miningcore, solo `getblocktemplate`), or switches to the `coinbasetxn` path.
4. Verify with `check-coinbase <height|blockhex>` (it calls `yed_gettag` and reports `found`,
   `kind` and `payoutAddress`), then watch `yed_getinfo.miner` with the monitoring snippet.

**Devnet** (`contrib/yellowback/devnet/yellowback-devnet`, adapted): `up` starts five regtest
nodes — node 0 the user wallet, node 1 a stock node, nodes 2–4 "pools" with payout addresses and
one `yellowback-quote --mock-price` each — funds node 0, and mines through activation so the first
`refHeight` a mint can use is ACTIVE (K16); `price USD` rewrites the mock; `mine N [node]`; `status`
prints activation, prices and each pool's registration and eligibility; **`check`** (new, N28)
exits 0 iff `yed_getactivation.status == "active"`, `yed_getstats.mintingAllowed`, all three
pools `eligible` and node 0's balance is positive — the machine-checkable exit Phase 7 needs;
`wallet`, `cli`, `down` as before. It is run through the workspace venv
(`../.venv/bin/python contrib/yellowback/devnet/yellowback-devnet up`, §6.0 item 0). The lifecycle test's "minting frozen on exit" caveat is gone (no volatility freeze in v2),
so `up` ends ready to mint. **Changes to the prototype's script (M9):** (a) the two-phase start becomes
start → `getnewaddress` on nodes 2–4 → restart 2–4 with `pool_args` (a payout address must exist
before the pool flags can be given); (b) the coordinator launch (`:248-267`) is replaced by three
`yellowback-quote --conf --mock-price` processes reading each pool node's `.cookie`; (c) the
`yed_getroster` assert (`:239`), the freeze text in `price`/`status` (`:372-374`) and the
`wait_yed_synced`/`fund_genesis_anchor`/`make_regtest_roster` imports (`:54`) go; (d) `mine N
[node]` accepts a node (today node 0 only, `:337`); (e) funding: node 0 first mines 101 untagged
blocks (`COINBASE_MATURITY = 100`; the current `generate(150)` at `:216` becomes 101) and the
pools then mine `2 · 64 + REF_LAG + 1 = 131` signalling blocks round-robin — the trailing window
makes the untagged prefix harmless — so `up` mines ≈ 232 blocks; (f) pools run with
`-yellowbacksigmaref=0` and `-yellowbackquotemaxage=120` so a stopped agent is visible within two
minutes. The devnet has no `-yellowbackenforce=0` observer (node 5 of §6.0); the wallet's
`unbacked` badge is shown by the functional tests, not the demo.

---

## 6. Work plan

Twelve phases (0–10 and 7b), each a reviewable PR series against `feature/yellowback-sf`. Sizes
are source lines excluding tests. A phase ends only when its exit criteria pass in CI.

**Review rule (P13).** Every PR uses `.github/PULL_REQUEST_TEMPLATE.md` (Phase 0): the four-part
check of AGENTS.md rule 4 for every ported symbol, the tier the change lands on and why a cheaper
tier will not do, the rule identifiers its tests tag, and the line-budget numbers. A PR that
touches `src/main.cpp`, `src/miner.cpp`, `src/rpc/mining.cpp` or `src/yellowback/state.cpp` needs
two approving reviewers, one of whom did not write or pair on it; a PR that touches anything in
the consensus set of §4.1 is refused outright (the `audit` job enforces the zero test, the
reviewers enforce the intent).

**Keeping the tree building through Phases 0–3 (M7).** The prototype's modules are coupled (`script.h`
takes a `Roster`; `state.cpp` and `txbuilder.cpp` call the prototype's signatures), so the phases cannot
each delete freely and stay green. The rule is: **a phase deletes only what nothing retained
references, and an old symbol stays beside its replacement until its last caller has migrated.**
Concretely, Phase 0 removes the federation RPCs, coordinator, wizard, tests and docs but keeps
`Roster` and the roster-typed `VaultScript`/`ParseVaultScript` for Phase 1 to replace; Phase 1 adds
the v2 signatures beside the old ones; Phase 2 migrates `state.cpp` and deletes the old ones; Phase 3
migrates `index.cpp` and the RPCs; `txbuilder.cpp` and the wallet RPCs migrate in Phase 6 and keep
compiling against the retained old signatures until then. "CI green" for Phase 1 means `make
check` (`test_bitcoin --run_test=yellowback_*`) plus the functional tests Phase 0's baseline
lists. **At Phase 2's first commit the four wallet-flow scripts (`yellowback_lifecycle.py`,
`yellowback_void_mint.py`, `yellowback_wallet_restore.py`, `yellowback_sapling.py`) leave the CI
list** — the payload goes to version 2 and the state machine to the v2 rules while the wallet
RPCs still build v1 transactions until Phase 6, so they cannot pass — recorded in
`doc/yellowback.md`, and they return at Phase 6 (N26). Phases 2–5 gate on the unit tests plus
`yellowback_index.py`, `yellowback_activation.py`, `yellowback_mining.py` and
`yellowback_enforcement.py` as each lands, all of which use raw builders only (`build_mint_tx`,
`build_vault_spend_raw`, §6.0 item 4); the full `rpc-tests.py` gate resumes at Phase 6's exit.
Phases 1–2 can run in parallel with Phase 0's clean-up once the branch exists. Phase 7b (wallet)
is split (N26): **7b-a** (node-context screens: banner, overview, vaults, claim list) may start
at Phase 3's exit, gated on the node context of `doc/yellowback-rpc.md` v2; **7b-b** (mint, send,
redeem, claim, sweep) at Phase 6's first commit, gated on its wallet context — neither on Phase 7.

### 6.0 Developing and testing on one machine

**Use only what the repository already ships** — regtest, the functional-test
framework (`MAX_NODES = 8`, `qa/rpc-tests/test_framework/util.py:46`), `zcutil/build.sh`, the
workspace venv. Nothing here needs a pool, a synced chain, or a second machine.

**0. Commands (N24).** Everything below runs from `ycash-dd/` on `feature/yellowback-sf`; the
"Build and test baseline" section of `doc/yellowback.md` carries the same text and is kept and
extended by Phase 0, never removed. Python is always the workspace venv (`../.venv/bin/python`),
never the system interpreter.

```
# host conditions (macOS, Apple Silicon; Linux CI needs none of the three exports)
export PATH="/opt/homebrew/opt/libtool/libexec/gnubin:/opt/homebrew/opt/coreutils/libexec/gnubin:/opt/homebrew/bin:$PATH"
export CARGO_TARGET_DIR="$PWD/target"          # the Makefile links target/<triple>/release/librustzcash.a relative to the repo
LIBTOOLIZE=glibtoolize BUILD_STAGE=depends ./zcutil/build.sh -j8    # once (~25 min): the depends tree
./zcutil/build.sh -j8                                              # ycashd, ycash-cli, ycash-tx, src/test/test_bitcoin
./zcutil/fetch-params.sh                                           # needs GNU sha256sum
# after a path change (workspace rename): configure bakes absolute depends paths, so reconfigure, then incremental
CONFIG_SITE="$PWD/depends/$(ls depends | grep -m1 darwin)/share/config.site" ./configure && make -C src -j8 test/test_bitcoin ycashd ycash-cli
make -C src -j8 ycash-cli                                          # after EVERY src/rpc/client.cpp change (conversions live in the CLI)

# unit tests
src/test/test_bitcoin --run_test='yellowback_*'
# one functional script (distinct --portseed per concurrent run; --nocleanup --noshutdown keeps the playground)
BITCOIND="$PWD/src/ycashd" ../.venv/bin/python -u qa/rpc-tests/yellowback_index.py --srcdir="$PWD/src" --tmpdir=/tmp/yb-index --portseed=11
# the suite by name (the runner does not glob; scripts are registered in BASE_SCRIPTS / EXTENDED_SCRIPTS)
qa/pull-tester/rpc-tests.py -j4 --nozmq yellowback_index yellowback_activation
# the Python owner-path signer (build_vault_spend_raw) loads libcrypto through ctypes; on macOS it aborts (exit 134) without:
export DYLD_LIBRARY_PATH="$(brew --prefix openssl@3)/lib"
# devnet (§5)
../.venv/bin/python contrib/yellowback/devnet/yellowback-devnet up && ../.venv/bin/python contrib/yellowback/devnet/yellowback-devnet check

# fuzz (Ycash's own harness: --enable-fuzz-main replaces main(); zcutil/clean.sh removes src/fuzz.cpp, confirming the layout)
CONFIG_SITE="$PWD/depends/<triple>/share/config.site" ./configure --enable-fuzz-main CC=clang CXX=clang++ CXXFLAGS='-fsanitize=fuzzer,address'
ln -sf fuzzing/YellowbackEvaluate/fuzz.cpp src/fuzz.cpp && make -C src -j8 ycashd
src/ycashd src/fuzzing/YellowbackEvaluate/output src/fuzzing/YellowbackEvaluate/input -max_len=4096   # libFuzzer; corpus in, findings out
../.venv/bin/python src/test/gen_yellowback_corpus.py --check                                          # embedded C++ corpus == input/ files
```

A failed `make` leaves the old `test_bitcoin` in place, so "tests pass" after a failed build means
nothing: check the make exit code. The wallet fork (Phase 7b) builds and tests with
`cd ../yecwallet-dd && cmake -S . -B build -DCMAKE_PREFIX_PATH=$(brew --prefix qt) && cmake --build build --target yellowback_test && QT_QPA_PLATFORM=offscreen build/bin/yellowback_test`
(the target exists only when `Qt6::Test` is present, `CMakeLists.txt:320-338`) and packages with
`bash build.sh macos-arm64 --package --ycashd ../ycash-dd/src/ycashd` (static Qt 6.5.8 in
`deps/`; `build.sh` selects the newest SDK that still ships `AGL.framework`).

**1. A pool is a regtest node (V25).** `-yellowback -yellowbackpayoutaddress=<addr>` plus
`yed_setquote` makes a node emit quote tags in every block it mines with `generate`. Hashpower
share is which node mines the next block. A stock miner is a node without `-yellowback`; a
non-enforcing observer is `-yellowback -yellowbackenforce=0`.

**2. Standard topology** (six of the eight nodes):

| Node | Role | Flags |
|---|---|---|
| 0 | user wallet (minter, redeemer, claimant) | `-yellowback` (enforcing; no payout address, so its own `generate` blocks carry no tag) |
| 1 | stock node and stock miner; the adversary | the six `-nuparams` only (`yellowback_node_args(yellowback=False)`) |
| 2–4 | three pools | `-yellowback -yellowbackpayoutaddress=<own> -yellowbacksignal=1` |
| 5 | non-enforcing observer (records `unbacked`) | `-yellowback -yellowbackenforce=0` |

State-hash assertions run over nodes 0 and 2–4 after every sync; node 5 is compared only where
the test expects it to follow the same chain.

**3. Regtest windows** (§3.1) make activation `64 + 64` blocks and a full lifecycle (mint class A
at 48 blocks, redeem, crash the price, wait the 24-block grace, claim) about 300 `generate` calls.
`-yellowbacksigmaref=0` fixes the σ multiplier at 1 for tests that are not about σ.

**4. `yellowback_util.py` (v2)** (N28): a `YellowbackTestFramework` base class with `num_nodes = 6`,
because the inherited helpers are hard-wired to four nodes (`test_framework.py:55-98`; the
prototype's `yellowback_index.py:64-90` and `yellowback_reorg_stress.py:65-98` already override
`setup_network`, `sync_all` and `join_network`) and the inherited `split_network` restarts every
node (K19). **Topology:** `setup_network` builds a **star on node 1** (`connect_nodes_bi(1, i)`
for `i ∈ {0, 2, 3, 4, 5}`) plus `2↔3↔4`, so the stock miner's blocks reach every node — with the
inherited chain `0-1-2-3-4-5` nodes 2–4 would never relay node 1's rejected block and node 5
could never "follow node 1"; `split_network()` disconnects `{1, 5}` from `{0, 2, 3, 4}` with
`disconnectnode` (`rpc/net.cpp:220`), no restart; `join_network()` reconnects the star.
**Payout addresses:** pools need one *before* they start, so `yellowback_util.py` carries three
fixed regtest WIFs (`POOL_WIFS`); `setup_nodes` starts nodes 2–4 with
`pool_args(address_of(POOL_WIFS[i]))` and `importprivkey`s the WIF after start (no two-phase
restart). **Constants** are v2: `REF_WINDOW = 40`, `REF_LAG = 2`, `TOKEN_VALUE`,
`YELLOWBACK_FEE`, and the §3.1 regtest windows and floors (`P_FAST_WINDOW = 8`, `P_MID_WINDOW =
24`, `P_SLOW_WINDOW = 64`, `MIN_FILL = (4, 16, 43)`, `SIGNAL_WINDOW = 64`, `ACTIVATION_THRESHOLD =
48`, `PARTICIPATION_FLOOR = 39`, `ACTIVATION_DELAY = 64`, `ENFORCEMENT_FLOOR = 32`,
`ENFORCEMENT_RESUME = 39`, `PAYEE_WINDOW = 10`, `GRACE = 24`, `VALVE_BLOCKS = 6`, `ABANDON_BLOCKS =
128`, …) so no test hard-codes them; the v1 `MINT_WINDOW`/`PRICE_MAX_AGE`/`DEFAULT_MINT_EVAL_LAG`
go. **Helpers:** `yellowback_node_args(extra, yellowback=True)` (six `-nuparams` at height 1 —
regtest activates no upgrade by default, `ref/ycash/src/chainparams.cpp:576-604` — plus
`-experimentalfeatures -yellowback -yellowbackstartheight=1`, the same start height on every
node since it is a per-node regtest parameter, and `-yellowbacksigmaref=0` unless the test is
about σ), `pool_args(payout_addr, extra)`, `set_quote(node, usd)`, `mine(node, n)` (`generate` +
`sync_all`), `mine_round_robin(pools, n, shares=None)`, `activate(pools, stock=None)` (mines
`SIGNAL_WINDOW + ACTIVATION_DELAY + 1 = 129` blocks round-robin and asserts
`yed_getactivation.status == "active"` on every enforcing node; a caller that then mints mines
`REF_LAG + 1` more so `Snapshots[tip − REF_LAG]` is ACTIVE, K16),
`build_mint_tx(node, cents, lock_blocks, ref_height, collateral_zat, fee_addr=None,
owner_pubkey=None) -> (hex, owner_pubkey)` (the raw MINT of §3.5: vault `vout[0]`, token
`vout[1]`, payload `vout[2]` with `feeVout = 3` when `fee_addr` else `0xFF`, change `vout[4]`;
`collateral_zat` from `yed_estimatecollateral`, `fee_addr` from `yed_getfeepayee` — the only mint
builder Phases 3–5 have, N26), `build_vault_spend_raw(node, vault, path, burn_inputs,
payload=None, fee=None, expiry=None)` (assembles an owner- or claim-path spend with
`test_framework.mininode.CTransaction`; the claim path needs no signature; the owner path is
signed in Python with the owner key from `dumpprivkey` decoded by the new 20-line
`wif_to_secret()` — the framework has no base58 decoder — the framework's ZIP-243
`SignatureHash(script, tx, 0, SIGHASH_ALL, amount, branchId)` (`test_framework/script.py:871`)
and `CECKey` (`key.py:88`, `set_compressed(True)` for the 33-byte owner key; on macOS
`DYLD_LIBRARY_PATH` per item 0) — no node RPC involved; the adversarial builder for every
"without a burn" test, K18, and with `payload=REDEEM(feeVout)`, `fee=(addr, zat)` also for the
*correct* spends Phase 5 needs), `mine_block_raw(node, txs)` (a Python-assembled block:
`mininode.CBlock`, `hashMerkleRoot = calc_merkle_root()`, `solve()` — regtest Equihash n=48, k=5,
seconds each — then `submitblock`; expect `None`/`'duplicate'` for accept and
`'yellowback-vault-spend'`/`'bad-cb-amount'` for reject), `assert_same_statehash(nodes)`,
`assert_best_hash(nodes)`, `checkpoint(label)` (= `sync_all` + `assert_same_statehash(enforcing)`
+ `assert_best_hash`; called after every mined block in `yellowback_enforcement.py` and
`yellowback_claim.py`; node 5 compared only when on the same chain), `assert_rejected(node,
blockhash)` (`yed_getinfo.rejectedBlocks` and `getblock(...).confirmations == -1`),
`assert_banscore_zero(nodes)`, `kill9(i)` (`os.kill(bitcoind_processes[i].pid, SIGKILL); del
bitcoind_processes[i]; wait_bitcoinds()`), `wait_yed_healthy(node)`, `snapshot_ledger(nodes)`
(the rc1 hash ledger), `assert_model_matches(node)` (`yellowback_model.py`, §7),
`assert_start_raises_init_error` (inherited; MINER-2's refusals), `advance_clock(seconds)`
(`setmocktime` on every node, `rpc/misc.cpp:1202` — quote staleness and every other wall-clock
case use it, never `sleep`, P12), `stock_binary()` (the path from `--stock-binary` or
`REF_YCASHD`, else the fork binary; passed as `binary=` for node 1 through `start_nodes`'s
per-node list, `util.py:396-410`, P9). **Initial block download on regtest (P12):** the cached
200-block chain carries the timestamps of the day the cache was built, so every node starts in
IBD (`nMaxTipAge`, BLK-2 clause 2) until the first fresh block connects and the latch flips; a
test that asserts a rejection must therefore mine at least one fresh block on the enforcing nodes
first — `activate()` does — and a test that *wants* IBD (a fresh node 6) gets it only until that
node's first fresh block, which is why `ibd_across_accepted_invalid` exercises clause 3 rather
than clause 2. The long scripts
(`yellowback_reorg_stress.py`, `yellowback_runbook.py`, `yellowback_rc1.py`) are registered in
`rpc-tests.py`'s `EXTENDED_SCRIPTS` (`ref:134`), the idiomatic home; the rest in `BASE_SCRIPTS`.
The fate of every prototype helper (M7): `assert_yed_synced`/`wait_yed_synced` → `wait_yed_healthy`
(`synced` is gone, V2); `restart_with_yellowback`, `sync_all_nodes`, `node_pubkey` → kept;
`genesis_args` → replaced by `pool_args`; `build_mint_tx` → the v2 signature above;
`fund_genesis_anchor`, `make_regtest_roster`, `publish_price`, `cosign_and_submit` → deleted.

**5. The inner loop**, fastest first: `src/test/test_bitcoin --run_test=yellowback_*` (seconds);
one flow (`yellowback_lifecycle.py`, 1–2 min); the suite by name in `rpc-tests.py -j4` (the runner
does not glob, `qa/pull-tester/rpc-tests.py:213-218`; the scripts are appended to `BASE_SCRIPTS`,
≈ 15 min); the playground (`--noshutdown --nocleanup`, then `ycash-cli -regtest -datadir=…`) and
the devnet (§5) for the GUI.

**6. CI (N32).** Ycash's own CI runs no tests (`.github/workflows/book.yml` only), so the fork carries
**one** workflow, `.github/workflows/yellowback-tests.yml`, plain GitHub Actions on `ubuntu-22.04`:
restore `depends/` and `~/.zcash-params` from `actions/cache` (keyed on `depends/packages/**` +
`depends/Makefile`, and on `zcutil/fetch-params.sh`), `./zcutil/build.sh -j$(nproc)`, then the
jobs below; on failure every node's `debug.log` is uploaded. The prototype's workflow triggers on
`feature/digidollar`, lists `yellowback_federation yellowback_protection`, runs
`test_yellowback_fed.py`, and its "nightly" job is `if: github.event_name == 'schedule'` with **no
`schedule:` trigger — it has never run**; Phase 0 fixes all four. `--extended` is declared by the
script's `add_options`, and the nightly step runs that script directly (`qa/rpc-tests/yellowback_enforcement.py --extended`)
because `rpc-tests.py` forwards every flag to every listed script (`:187-189`, M9).

| Job | Trigger | Steps | Blocks merge? |
|---|---|---|---|
| `main` | PR + push to `feature/yellowback-sf` | build; **the whole `src/test/test_bitcoin`** (P5: the hook edits sit in files `miner_tests`, `main_tests`, `mempool_tests` and `rpc_tests` cover; ≈ 10 min); `qa/pull-tester/rpc-tests.py -j4 --nozmq` over the Yellowback scripts the current phase lists (at Phase 6 and after: `yellowback_index yellowback_activation yellowback_mining yellowback_enforcement yellowback_lifecycle yellowback_claim yellowback_void_mint yellowback_pricefeed yellowback_wallet_restore yellowback_sapling yellowback_quote yellowback_stock_node yellowback_rpc_contract`) **and the inherited stock baseline** `getblocktemplate_proposals getblocktemplate_longpoll mempool_reorg mempool_tx_expiry p2p-acceptblock invalidateblock reorg_limit reindex wallet rawtransactions txn_doublespend` (all in `ref/ycash/qa/rpc-tests/`, run against the fork binary without `-yellowback`; the nightly job runs the same list a second time with `BITCOIND=qa/yellowback-wrapped-ycashd.sh`, a two-line wrapper that appends `-experimentalfeatures -yellowback -yellowbackstartheight=1` to every node, proving the inherited behaviour also survives with the module switched on); upload `debug.log` on failure | yes |
| `audit` | PR + push | line budget (`for f in src/main.cpp:40 src/miner.cpp:35 src/rpc/mining.cpp:35; do p=${f%%:*}; b=${f##*:}; n=$(git diff --numstat ycash-legacy...HEAD -- $p \| awk '{s+=$1+$2} END {print s+0}'); test "$n" -le "$b" \|\| exit 1; done`) and the zero test for the consensus set (§4.1, minus `src/wallet/rpcwallet.cpp`/`src/rpc/rawtransaction.cpp` from Phase 8); determinism grep over `state`, `math`, `tag`, `payload`, `script`, `view`, `index`; `GetTime` two-home grep; `DoS([1-9]` grep; `throw`/`assert(` grep on `state.cpp`/`math.h`; anchored no-sockets grep `\bconnect(`; lock-order grep (no `mempool.cs` after `cs_yellowback`, Phase 8); rule → test grep (`// Rule:` / `# Rule:` tags, §7) over `src/test/yellowback_*.cpp` + `qa/rpc-tests/yellowback_*.py`; `transaction_builder` call-site grep (§8.4 item 22); `! grep -q 'no consensus change' doc/yellowback.md`; **fork-local document checks only (P4)**: `doc/yellowback-spec.md`'s `Source:` header carries a `sha256` that equals the hash of the file's body (`sed '1,/^---$/d' doc/yellowback-spec.md \| sha256sum` — the copy was not hand-edited), the trust statement in `doc/yellowback.md` equals the `## 8.1` section of `doc/yellowback-spec.md` byte for byte (`diff` of the two extractions), and `doc/yellowback-rpc-contract.json` parses and lists every command `yed_*` registered in `src/rpc/yellowback*.cpp` (`grep -o '"yed_[a-z]*"' src/rpc/yellowback*.cpp \| sort -u` ⊆ the JSON's keys). Staleness *against the plan* is a workspace check (`make status` → `spec-check`), not a fork check | yes |
| `lockorder` | nightly (P6) | `./configure --enable-debug` (defines `DEBUG_LOCKORDER`, `configure.ac:249`; `sync.cpp:22-224` aborts the process on a potential deadlock) then `rpc-tests.py -j2 --nozmq` over the Yellowback scripts and the stock baseline; any abort is a failure | no (opens an issue) |
| `sanitizers` | nightly (P6) | `./configure --with-sanitizers=address,undefined` (`configure.ac:211`): `test_bitcoin --run_test='yellowback_*'` and `rpc-tests.py yellowback_index yellowback_enforcement yellowback_mining`; then `--with-sanitizers=thread`: `test_bitcoin --run_test='yellowback_*,miner_tests,mempool_tests'`; `ASAN_OPTIONS=detect_leaks=0` as Ycash's own CI notes | no (opens an issue) |
| `coverage` | nightly (P6) | `./configure --enable-lcov` (`configure.ac:167`), `make check`, the Yellowback functional suite against the instrumented `ycashd`, `lcov` over `src/yellowback/` and `src/rpc/yellowback*.cpp`; floors asserted by `qa/yellowback-coverage-floor.sh`: ≥ 95 % lines in `state.cpp`, `math.h`, `tag.cpp`, `payload.cpp`, `script.cpp`; ≥ 85 % in `index.cpp`, `policy.cpp`; ≥ 80 % in `txbuilder.cpp`, `wallet.cpp`, `rpc/yellowback*.cpp`; the HTML report is an artefact and its summary is pasted into `doc/yellowback-review.md` at Phase 8 | no (opens an issue) |
| `python` | PR + push | `python3 -m unittest contrib/yellowback/test_yellowback_price.py contrib/yellowback/test_yellowback_quote.py` (from Phase 7; `test_yellowback_fed.py`'s feed half until then); `python3 -m pyflakes qa/rpc-tests/yellowback_*.py qa/rpc-tests/test_framework/yellowback_util.py qa/rpc-tests/test_framework/yellowback_model.py contrib/yellowback/*.py src/test/gen_yellowback_corpus.py`; `gen_yellowback_corpus.py --check` | yes |
| `wallet` (`yecwallet-dd`) | PR + push to its `feature/yellowback-sf` | Qt 6 build; `QT_QPA_PLATFORM=offscreen` QTest (offline cases only); `grep -rn 'trustless' src/ \| { ! grep .; }` (§4.8 copy rule); the contract check (P7): every field name the wallet reads (`yellowbackrpc.h`'s constants) appears under its command in the repo's copy of `docs/yellowback-rpc-contract.json`, and the file's `RPC_VERSION` equals the JSON's `rpcversion`; on macOS runners additionally the golden vector: devnet `up` with a fixed mock price, `ycash-cli yed_getstatehash` equals the pinned hex (N23) | yes |
| `nightly` | `schedule: cron '0 3 * * *'` + `workflow_dispatch` | `make check` in full; the inherited functional scripts recorded as passing in Phase 0 (by name, from `doc/yellowback.md`); `yellowback_reorg_stress.py`; `qa/rpc-tests/yellowback_enforcement.py --extended`; `yellowback_runbook.py`; **the legacy binary**: `git worktree add /tmp/legacy ycash-legacy && (cd /tmp/legacy && ./zcutil/build.sh -j$(nproc))`, cached by the `ycash-legacy` commit hash (P4) — then `yellowback_stockparity.py` against it and `yellowback_stock_node.py --stock-binary=/tmp/legacy/src/ycashd` plus `yellowback_enforcement.py --stock-binary=…` (node 1 is a real v4.5.0 node, P9); fuzz smoke — `--enable-fuzz-main` build of each `Yellowback*` target and a 10-minute libFuzzer run per target from its corpus, new crashes uploaded as artefacts and replayed from `crashes/` | no (opens an issue on failure) |
| `weekly-fuzz` | `schedule: cron '0 4 * * 0'` | 2 h per target, corpus minimisation, a PR with the new corpus files and the regenerated C++ table | no |

**7. What one machine cannot show** — real pool software, real hashpower shares, real exchange
feeds, wall-clock quote staleness on a live network — is Phase 9.

### Phase 0 — Branch, strip the federation, re-baseline (≈ 3–5 days)

- [x] In both forks, `feature/yellowback-sf` exists at the prototype tip (created 2026-09-10).
- [x] Update `repos.yaml` (`branch:` for both forks), `AGENTS.md` rule 2 and the layout block, the
      README pin table, `docs/mapping.md`'s pin table; `feature/digidollar` is kept as the federation
      prototype's record (`make log` may list both). `make status` clean.
- [x] Node: delete everything under "Removed outright" in §4.2 that nothing retained references
      (the §6 preamble rule: `Roster` and the roster-typed `VaultScript`/`ParseVaultScript` stay
      until Phase 1; `AnchorRecord`/`GetAnchor` live in `view.h:124-141,420` and are read by
      `state.cpp` until Phase 2); keep the tree building at every commit — in
      `yellowback_state_tests.cpp` `#if 0` the cases named `price_*`, `rotation_*`, `anchor_*`
      rather than deleting the file (the retained cases are Phase 1–2's harness; the `#if 0` list
      is enumerated in the PR body), and leave `yellowback_index_tests.cpp` untouched until Phase 3
      (its `MakeTestParams` uses the roster-typed `RegtestParams`, which Phase 1 keeps as an
      overload). **Phase 0 grep:** `git grep -in 'cosign\|PendingRedemption\|createpricetx\|getroster\|submitredeem\|abortredeem' -- src/yellowback src/rpc/yellowback*`
      empty (`anchor` alone would match the Sapling anchor in `txbuilder.cpp`, M7);
      `genesisanchor\|AnchorRecord\|GetAnchor` joins the grep at **Phase 2's** exit (when `view.h`
      and `state.cpp` migrate) and `roster` at **Phase 3's** (`ParamsFromArgs` parses
      `-yellowbackgenesisroster` until then; N26).
- [x] Wallet: delete `yellowbackredeemwizard.*`, the endpoint settings, `getRoster`/`submitRedeem`/
      `abortRedeem`; build against Homebrew Qt 6 with the §6.0 item 0 command; the offscreen QTest
      still passes for the cases that remain. `RPC_VERSION` stays at 1 — the wallet must keep
      running against a `rpcversion 1` node until Phase 3 ships v2; the bump is Phase 7b-a's first
      commit (N27).
- [x] Publish §3 of this plan verbatim as `docs/spec/yellowback-spec.md` through a tool, not a
      copy: `scripts/extract-spec.sh` copies the lines from `## 3.` up to `## 4.` **and §8.1**
      with a generated header (`Source: yellowback-v2-development-plan.md revision N; sha256:
      <hash of the body>`), writes the same file to **`ycash-dd/doc/yellowback-spec.md`** (the copy
      the fork's CI can see, P4) and extracts every fenced JSON return shape of §4.5 /
      `doc/yellowback-rpc.md` into `yellowback-rpc-contract.json`, written to `ycash-dd/doc/` and
      `yecwallet-dd/docs/` (P7); `make spec` runs it, `make spec-check` (called by `make status`)
      fails when any copy is stale (N29); point `docs/spec/README.md` at it; add
      `.github/PULL_REQUEST_TEMPLATE.md` with the four-part check, tier, `// Rule:` tags and
      budget fields (P13); rewrite the opening of
      `ycash-dd/doc/yellowback.md` (the "no consensus change, no policy change" paragraph is false
      for v2) and mark the rest "federation prototype, being replaced by phase" — **except the
      "Build and test baseline" section, which is kept and extended (§6.0 item 0), never removed.**
- [x] CI (`.github/workflows/yellowback-tests.yml`, N32): `on.push.branches`/`on.pull_request.branches`
      → `feature/yellowback-sf`; add `on.schedule: [{cron: '0 3 * * *'}]` and `workflow_dispatch`
      (the nightly job is otherwise dead); replace the zero-touch `test -z "$(git diff --stat …)"`
      by the line-budget loop of §6.0 item 6 plus the zero test for the consensus set; anchor the
      no-sockets grep and add `tag.cpp` to the determinism grep (K23); drop `yellowback_federation
      yellowback_protection` from the run list; retarget the `Coordinator unit tests` step at the
      feed half of `test_yellowback_fed.py`; split the jobs as §6.0 item 6 (`main` — running the
      whole `test_bitcoin` and the inherited stock baseline from this phase on, P5 — `audit`,
      `python`, `nightly`; `lockorder`, `sanitizers` and `coverage` come with Phase 3, `wallet`
      and `weekly-fuzz` with Phases 7b and 2); the `audit` job checks only fork-local documents
      (P4); make `main` green on the reduced tree.
- [x] Record the baseline (`test_bitcoin` count, which functional tests still run) in
      `doc/yellowback.md`. Carry over the two Phase-0 leftovers of the prototype (`YCASH_WR=1` build; inherited
      `rpc-tests.py` baseline) as open items.

Exit: both forks build on `feature/yellowback-sf`; retained unit tests green; `make status` clean;
CI green. **Acceptance** (from `ycash-dd/`, `set -e`; N31):

```
make -C .. status                                            # exit 0: pins hold, tree clean, spec current
./zcutil/build.sh -j$(nproc)
src/test/test_bitcoin --run_test='yellowback_*'
! git grep -in 'cosign\|PendingRedemption\|createpricetx\|getroster\|submitredeem\|abortredeem' -- src/yellowback src/rpc/yellowback*
test -z "$(git diff --stat ycash-legacy...HEAD -- src/consensus src/script src/primitives src/pow src/chainparams.cpp src/wallet/wallet.h src/wallet/wallet.cpp src/txdb.cpp src/txdb.h configure.ac)"
qa/pull-tester/rpc-tests.py -j4 --nozmq yellowback_index yellowback_lifecycle yellowback_void_mint yellowback_wallet_restore yellowback_sapling
grep -q 'federation prototype, being replaced' doc/yellowback.md && grep -q 'Build and test baseline' doc/yellowback.md
make -C .. spec-check                                        # workspace-local: docs/spec/, doc/yellowback-spec.md and both rpc-contract copies == this plan
test "$(sed -n 's/^Source: .*sha256: \([0-9a-f]*\).*/\1/p' doc/yellowback-spec.md)" = "$(sed '1,/^---$/d' doc/yellowback-spec.md | sha256sum | cut -c1-64)"   # the fork-CI form of the same check
test -f .github/PULL_REQUEST_TEMPLATE.md && grep -q 'four-part' .github/PULL_REQUEST_TEMPLATE.md
src/test/test_bitcoin                                        # the whole suite, not only yellowback_* (P5)
qa/pull-tester/rpc-tests.py -j4 --nozmq getblocktemplate_proposals getblocktemplate_longpoll mempool_reorg mempool_tx_expiry p2p-acceptblock invalidateblock reorg_limit reindex wallet rawtransactions txn_doublespend
grep -q "cron: '0 3" .github/workflows/yellowback-tests.yml && ! grep -q 'yellowback_federation' .github/workflows/yellowback-tests.yml && ! grep -q 'make -C \.\.' .github/workflows/yellowback-tests.yml
```
Reviewer by hand: the `#if 0` list is enumerated in the PR body. Acceptance: the block above
exits 0 on CI jobs `main` + `audit` for this PR series.

### Phase 1 — Protocol library v2 (≈ 900 lines)

Files: `params`, `math.h`, `tag`, `payload`, `script`, `address` (unchanged). No chain, DB or
wallet dependencies. Four-part check for each (AGENTS.md rule 4) goes in the commit message.

- [x] `Params` per §3.1 (the field list of §4.2a) with the L6 wallet-default rows and
      `IsConfigured()`; `Params RegtestParams(int startHeight, int sigmaRefBps, int supplyCapBps,
      int enforceUntil)` **beside** the old roster-typed overload (the §6 preamble; the old one
      goes in Phase 3). Flag parsing is not here: `params.cpp` is `libbitcoin_common` and §3.10
      forbids `GetArg`; the prototype parses in `index.cpp:286-305` (`ParamsFromArgs`), which
      moves to the four regtest-only flags (`-yellowbackstartheight`, `-yellowbacksigmaref`,
      `-yellowbacksupplycapbps`, `-yellowbackenforceuntil`) in Phase 3. Every other regtest value
      is compiled into `RegtestParams` (§3.1).
- [x] `math.h` per the §4.2a signatures: `LowerMedian`, `IsqrtU256`, `SigmaMultBps`, `MinRatioBps`,
      `RequiredCollateral`, `CapCents`, `SupplyCapCents`, `GlobalRatioBps`, `IsUnderwater`, `FeeZat`
      — no `IssuedZat` (the subsidy is `EvaluateBlock`'s argument, N22) —
      (with the worked examples of §3.7 as tests, overflow tests at `MAX_MINT`/`PRICE_MIN`, the
      σ cross-pool-noise case that motivated V17 as a regression test: a flat price with ±2 %
      alternating quotes must give multiplier 1 on the `P_fast` series;
      `fee1_min_dominates_small_vault` (`collateral < 200 YEC ⇒ FEE_MIN`) and `fee1_at_max_money`
      (no overflow); `sigma1_first_sample_at_start_height` (`s_43` exactly at `START_HEIGHT`
      defined; one below ⇒ the cap)).
- [x] `tag.{h,cpp}` per §4.2a (`TagPush`, not `TagScript`, N25): `EncodeTag`, `FindTag(scriptSig, nHeight)` implementing TAG-1..5 with a
      table-driven test: tag right after the height, after an extranonce, after pool text, magic
      inside an extranonce with too few bytes following, two tags, bad version, reserved flag
      bit, price out of range, signal-only; and the 100-byte budget test at heights 1, 16, 17,
      65,535, 16,777,215, 16,777,216.
- [x] `payload.{h,cpp}` version 2 (§3.3): round-trip table, every malformed case, `feeVout`
      semantics, REDEEM `count` bound 14.
- [x] `script.{h,cpp}`: `VaultScript`, `ParseVaultScript`, `OwnerScriptSig`, `ClaimScriptSig`,
      `ParseVaultSpendPath`; tests: sizes and sigops; `VerifyScript` under
      `STANDARD_SCRIPT_VERIFY_FLAGS` for owner path (success; early; wrong key; claim-path
      selector with a signature), claim path (success at `claimHeight`; early; `nSequence` final);
      `IsStandardTx`/`AreInputsStandard` for MINT, TRANSFER, REDEEM (owner), CLAIM templates with
      `RegtestActivateSapling()`/`Canopy()` (`BasicTestingSetup` selects mainnet and the regtest
      fixture activates nothing, `ref/ycash/src/test/test_bitcoin.h:19`; the activation helpers are
      `ref/ycash/src/utiltest.h:40-53`, not under `src/test/`); fee output present.
- [x] Fuzz targets: `YellowbackTag` (new; seeds = the table cases above plus ten real Ycash mainnet
      coinbase scriptSigs from `getblock` at assorted heights, so the byte scan is fuzzed against
      pool-shaped extranonces), `YellowbackPayload` and `YellowbackScript` re-seeded (corpora under
      `src/fuzzing/<Target>/input`, Ycash's own fuzz layout, `ref/ycash/src/fuzzing/`); **the
      corpus generator is in-tree**: `src/test/gen_yellowback_corpus.py` (venv) writes
      `src/fuzzing/<Target>/input/*.bin` and prints the C++ initialiser pasted into
      `src/test/yellowback_fuzz_tests.cpp`, both committed together, `--check` for CI (N34; the
      prototype's "generated from the same generator" had no generator); corpus-replay Boost cases
      also replay `src/fuzzing/<Target>/crashes/` so a fixed crash stays fixed.

Exit: `test_bitcoin --run_test=yellowback_*` green; nothing outside `src/yellowback/`, `src/test/`,
`src/fuzzing/` and the two Makefiles touched; `roster` gone from the Phase 1 files (the
whole-directory grep is Phase 3's exit, N26). **Acceptance:**

```
src/test/test_bitcoin --run_test='yellowback_math_tests,yellowback_tag_tests,yellowback_payload_tests,yellowback_script_tests,yellowback_fuzz_tests'
! git grep -in roster -- src/yellowback/params.* src/yellowback/script.* src/yellowback/math.h src/yellowback/tag.* src/yellowback/payload.*
test -z "$(git diff --stat ycash-legacy...HEAD -- . ':!src/yellowback' ':!src/test' ':!src/fuzzing' ':!src/Makefile.am' ':!src/Makefile.test.include')"
for t in YellowbackTag YellowbackPayload YellowbackScript; do test -d src/fuzzing/$t/input && test "$(ls src/fuzzing/$t/input | wc -l)" -ge 20; done
../.venv/bin/python src/test/gen_yellowback_corpus.py --check
```
plus a 10-minute libFuzzer run of `YellowbackTag` and `YellowbackPayload` (§6.0 item 0) with no
crash, recorded in the PR. Acceptance: the block above exits 0 on CI jobs `main` + `audit`.

### Phase 2 — State machine v2 (≈ 1,200 lines)

- [x] `view.h` tables of §3.6 with the key prefixes and the `Params` record; `SCHEMA_VERSION = 2`;
      `StateHash` per §3.6 *State hash* (excluding `U`, `X` and `TxLog`); `statehash_golden_vector`
      (pinned hex over a fixed synthetic sequence; N18); `AnchorRecord`/`GetAnchor` and the
      `P<height>` price table go now (the Phase 0 grep gains `genesisanchor\|AnchorRecord\|GetAnchor`).
- [x] `state.cpp`: `ProcessTx` with IN-1..3 (amended, incl. the MINT clause of IN-3, N19), TX-0,
      MINT-1..8, XFER-1..3, RED-1..4 and the M3 rule (a vault-spending transaction sees no
      MINT/XFER rules); `TxLog` entries only for transactions that create or spend
      `Tokens`/`Vaults` (N7); `EligiblePayees`, `DefaultPayee` (FEE-2, FEE-W); `ComputeSnapshot`
      with REG-4 judgement, ACT-1..6 (ACT-5 incl. the sunset, L8), PRICE-1..2 with the per-window
      fill (L9), SIGMA-1, issuance from the `subsidyZat` argument (N22), HALT-1..4, the
      undefined-value encoding and the virtual snapshot (§3.6); `EvaluateBlock` and `ApplyBlock`
      with the §4.2a signatures — **total**: every lookup that can miss returns a verdict, no
      `throw`, no `assert` on input, no unchecked division (K1); `UndoBlock`.
- [x] Verdict strings exactly as the §4.2a table (the wallet fork and the tests match them; the
      prototype's tier/ERR/volatility verdicts are deleted, N20).
- [x] Unit tests on synthetic blocks (in-memory view): tags and medians including the half-fill
      boundary (`⌈W/2⌉ − 1` vs `⌈W/2⌉`); `P_mint`/`P_claim` selectors under rising and falling
      series; activation lock-in at exactly the threshold, delay, participation halt and
      hysteresis; judgement lag, penalty window edges, accuracy counts; the eligible payee set
      `E(R)` at window edges; the wallet default FEE-W (a 10-block window with equal block counts
      for one perfectly accurate and one never-in-band miner: over 1,000 selectors (`selector =
      i` as 33 bytes) at one `R`, the accurate miner is picked in `[1.8, 2.2] : 1` at the default
      tilt and `[0.9, 1.1] : 1` at tilt 0 (N28); a penalised key is skipped; the all-penalised
      fallback; `feew_override_flags_change_pick` for each of the three L6 flags); FEE-0 with a stray fee output; `feeVout = 0xFF`
      with a non-empty `E(R)` (MINT-8/RED-3 fail) and with an empty one (vacuous); `feeVout` at
      0, 1, the `OP_RETURN` and an assigned vout (K23); every MINT rule ⇒ VOID and never
      `blockInvalid`, MINT-7 included; TX-0 (a coinbase carrying a payload registers nothing);
      every RED rule ⇒ `blockInvalid` iff enforcement is on at `H` (ACT-5: active and
      `ENFORCEMENT` clear), and never for a VOID vault; RED-1 with the vault at `vin[1]` and with
      two ACTIVE vaults; a vault spend carrying a MINT payload creates no vault (M3); a full burn
      to the wrong payee closes the vault with `unbacked = false` (M3); RED-4 with an undefined
      `pClaim` (not underwater); the selector cases of K4 (`OP_2`, non-minimal `1`, `0x80`) and a
      one-push scriptSig (RED-1 fails); ACT-6 set below `ENFORCEMENT_FLOOR`, held below
      `ENFORCEMENT_RESUME`, cleared at it, always implying `PARTICIPATION`; LOCKED_IN followed by
      a collapse (ACTIVE at `activateHeight`, both bits set, no enforcement); HALT-1 and HALT-4
      by name, HALT-2/3 with an undefined price (clear); REG-1 lapse after `N_REG`; SIGMA-1 with
      an undefined sample ⇒ the cap (K12); `sigma1_one_pool_cannot_inflate` (one of three pools
      alternating ±20 % ⇒ `sigmaMultBps == 10000`); CLAIMED vs CLOSED vs unbacked; supply/collateral/
      unbacked totals; in-block chaining (`tpl1_overlay_order_in_block_chaining`); apply/undo
      byte-identity over every sequence; overlay-view equivalence (evaluating on an
      `OverlayStateView` and on the base gives the same verdicts). Cases the N30 matrix adds, each
      carrying its `// Rule:` tag (N36): `in1_spent_token_removed`, `in2_void_vault_spend_closes`,
      `in3_burn_recorded_on_closed_vault`, `in3_mint_with_yed_inputs_burns_them` (N19),
      `mint1_`…`mint8_` one case per rule (`mint2_regtest_height_underflow`: `H < REF_WINDOW` on
      regtest never wraps), `xfer1_`, `xfer2_`, `xfer3_`, `red4_undefined_pclaim`,
      `blk2_dos_level_zero` (a `CValidationState` from the hook's caller has `nDoS == 0` and
      `GetRejectReason() == "yellowback-vault-spend"`), `tpl2_declines_nonwallet_selector`
      (`OP_2` selector excluded from a strict template, included under `consensus`),
      `virtual_snapshot_below_start_height` (`EvaluateBlock` at `H = START_HEIGHT` reads a virtual
      `Snapshots[H − 1]`: enforcement off, MINT-4 false, `haltMask == NOT_ACTIVE | NO_PRICE`),
      `snapshot_undefined_price_is_zero` (write, read, hash; `yed_gethistory` renders `null`),
      `snap_written_for_every_height_ge_start`, `totality_every_lookup_misses` (empty view, `H =
      START_HEIGHT`, a block with a MINT, a REDEEM naming a non-existent vault and a TRANSFER of
      unknown tokens ⇒ verdicts, no throw), `params_selected_by_height` (two regtest sets;
      `EvaluateBlock` picks by `H`; a rule at the boundary reads the new set at its `startHeight`
      and the old one below), `act5_sunset_stops_rejection` (`H > ENFORCE_UNTIL_HEIGHT` ⇒
      `enforcementOn == false` with the same `blockInvalid`), `price1_mid_slow_need_two_thirds`
      (`⌈2W/3⌉ − 1` vs `⌈2W/3⌉` on the mid and slow windows, L9), `mempoolcheck_bench` (10,000
      plain transactions through `MempoolCheck` in < 1 s; a 2 MB `OP_RETURN` block through
      `EvaluateBlock` in < 200 ms, N6).
- [x] Totality: a fuzz target `YellowbackEvaluate` (corpus `src/fuzzing/YellowbackEvaluate/input`)
      decodes its input with a fixed prefix grammar — `k ≤ 64` tags, `m ≤ 16` vaults, `n ≤ 16`
      tokens, a snapshot row and an activation record seeded into a `MemoryStateView`, regtest
      params fixed, then a serialised `CBlock` and a height `H` drawn in `[START_HEIGHT − 2,
      START_HEIGHT + VOL_WINDOW + 8]` (the virtual-snapshot and first-sample edges), block hashes
      derived from the input (never `GetHash()` of an undeserialisable block) — and calls
      `EvaluateBlock` under a `try/catch` that fails the run on any exception; an input whose
      `CBlock` fails to deserialise is discarded (deserialisation is outside the totality claim,
      M10). It asserts **properties, not just no-throw** (N34): (i) apply → undo byte identity on
      the `MemoryStateView`; (ii) `EvaluateBlock` on an `OverlayStateView` equals the base result;
      (iii) `blockInvalid ⇒ enforcementOn` was computed at `H` (never a reject with enforcement
      off); (iv) `supplyCents == Σ Tokens`. Its corpus-replay Boost case (plus `crashes/`) is a
      Phase 2 exit criterion (K1). Also `YellowbackPayee` (FEE-W over random `Tags`/`Judgements`:
      the pick is in `E(R)`; the all-penalised fallback is never empty when `E(R)` is non-empty) —
      it guards the one wallet-side function that can make the wallet and the validator disagree.
- [x] CI: at this phase's first commit the four wallet-flow scripts leave the `main` job's list
      (§6 preamble, N26), recorded in `doc/yellowback.md`; the `weekly-fuzz` job and the nightly
      fuzz smoke are added (§6.0 item 6).

Exit: unit tests green, fuzz replay green; `grep` of §3.10's forbidden symbols empty in
`state.cpp`/`math.h`/`tag.cpp`; the `genesisanchor\|AnchorRecord\|GetAnchor` grep empty (N26).
**Acceptance:**

```
src/test/test_bitcoin --run_test='yellowback_state_tests,yellowback_fuzz_tests'
! grep -n 'GetTime\|GetAdjustedTime\|mempool\|pwalletMain\|GetArg\|double\|float' src/yellowback/{state,tag,payload,script,view}.cpp src/yellowback/{state,math,tag,payload,script,view}.h
! grep -n '\bthrow\b\|\bassert(' src/yellowback/state.cpp src/yellowback/math.h
! git grep -in 'genesisanchor\|AnchorRecord\|GetAnchor' -- src/yellowback src/rpc/yellowback*
for id in TAG-1 TAG-2 TAG-3 TAG-4 TAG-5 PRICE-1 PRICE-2 SIGMA-1 FEE-0 FEE-1 FEE-2 FEE-W REG-1 REG-2 REG-3 REG-4 IN-1 IN-2 IN-3 TX-0 MINT-1 MINT-2 MINT-3 MINT-4 MINT-5 MINT-6 MINT-7 MINT-8 XFER-1 XFER-2 XFER-3 RED-1 RED-2 RED-3 RED-4 ACT-1 ACT-2 ACT-3 ACT-4 ACT-5 ACT-6 HALT-1 HALT-2 HALT-3 HALT-4 SNAP UNDO; do git grep -qE "^// Rule: .*\b$id\b" -- src/test/yellowback_*.cpp || { echo "no unit test tagged $id"; exit 1; }; done
```
plus 8 CPU-hours of `YellowbackEvaluate` (§6.0 item 0) with zero crashes, recorded in
`doc/yellowback-review.md`. The identifiers are found through the comment-tag convention — a
`// Rule: RED-1` line on each `BOOST_AUTO_TEST_CASE` (hyphens cannot appear in a case name, N36);
ACT-7 joins the list at Phase 6's loop (its unit test is Phase 3's `valve_trips_at_six_blocks`). Acceptance: the
block above exits 0 on CI jobs `main` + `audit`.

### Phase 3 — Synchronous index, hooks, node RPCs (≈ 800 lines + ≈ 29 in `main.cpp`)

**Raw builders only (N26):** nothing in this phase or Phase 5 calls `yed_mint`/`yed_redeem`/
`yed_claim` (Phase 6); vaults come from `build_mint_tx` and spends from `build_vault_spend_raw`
(§6.0 item 4).

- [x] `index.{h,cpp}` per the §4.2a signatures: `CheckConnect`, `CommitConnect`, `UndoDisconnect`
      (V2 guards incl. the empty-index/`-reindex` case, exception boundary, `Rejected` with sync
      writes, the IBD/reindex suppression of BLK-2, the cache key of N9), `NoteHeaderOnRejectedChain`
      + `IsRejectedAncestor` (the N1 clause and the ACT-7 valve: the note map, the work arithmetic,
      the in-place trip that runs the `ReconsiderBlock` loop, clears enforcement and the signal bit
      and raises the alert), the sunset flag (ACT-5 at `ENFORCE_UNTIL_HEIGHT`, L8),
      `RemoveInvalidVaultSpends` (N5), `IsAbandoned()` (L10), `SyncToChain` with `UNDO_KEEP = 4096`,
      enforcement flag, quote holder, payout key, `TemplateView()` (RAII holder, lock order §4.3);
      the `ChainTip`/`SyncTransaction` subscriber reduced to wallet locking;
      `-yellowbacktestfault=storage:<check|commit|undo>[:<height>]` (regtest only; the named hook
      throws a `dbwrapper_error` once at that height, §4.5) and `-yellowbacktestfault=template`;
      `ParamsFromArgs` moves to the four regtest flags and loses the anchor/roster ones (the
      whole-directory `roster` grep is this phase's exit, N26); the seed loop for `issuedZat` at
      `startHeight` (`GetBlockSubsidy` is called here, never in `state.cpp`, N22).
- [x] `policy.{h,cpp}` first half (moved here from Phase 4, M7): `TagScript(index)`/`BuildTagScript`
      (MINER-1..3, incl. the valve and sunset conditions on the signal bit) and `MempoolCheck`
      (MP-1: the `O(inputs)` short-circuit, the expiry bound, the two-transaction pseudo-block of
      §4.3); the two `miner.cpp` tag lines (`COINBASE_FLAGS` assignment, `CreateCoinbaseTransaction`
      append) and the K17 lock, so `generate` emits tags.
- [x] `main.cpp` hooks exactly as §4.3 (six sites: the `ConnectBlock` check and commit, the
      `DisconnectBlock` undo, MP-1, the `AcceptBlockHeader` clause, the `ConnectTip` sweep) with
      `#include "yellowback/index.h"` (no forward declaration — the calls need the full class,
      N25); `init.cpp` options (incl. the per-network `-yellowbacksignal` default, L4, and
      `-yellowbackenforceuntil`) and the kill-switch loop ordered before the notifier thread
      (§4.3); `-reindex` and `-reindex-yellowback` behaviour; `-prune` refusal.
- [x] `doc/yellowback-rpc.md` v2, node context, written **first** (it is the contract, §4.5 —
      Phase 7b-a's gate, M7); then the node RPCs of §4.5 with the error identifiers and return
      shapes there, `yed_getblockverdict`'s precondition (N12), the `rpc/client.cpp` rows and a
      rebuilt `ycash-cli`.
- [x] Unit: `yellowback_index_tests.cpp` — a storage fault injected in `CheckConnect` accepts the
      block and sets unhealthy; the same in `CommitConnect` sets unhealthy without failing the
      block; `UndoDisconnect` with a mismatched tip refuses and sets unhealthy; `CheckConnect`
      with a `CBlockIndex` whose `phashBlock` is null (the `TestBlockValidity` shape) runs without
      dereferencing it (K5); a re-verification (`chainActive.Contains(pindex)`) is a no-op (K6);
      `check_ibd_suppresses_reject` (a healthy index with `fReindex` set evaluates, commits and
      returns `nullopt`, N2); `catchup_suppresses_reject` (`// Rule: BLK-2`: with `pindexBestHeader`
      set to a descendant of the block six blocks of work above the tip, `CheckConnect` returns
      `nullopt`, increments `suppressedBlocks`, writes nothing to `Rejected` and leaves
      `enforcing` true; at five blocks it rejects, L11); `valve_trips_at_six_blocks`
      (`// Rule: ACT-7`: six noted headers of one block of work each above the tip trip it, five
      do not; the note map is cleared; a `Rejected` hash absent from `mapBlockIndex` is skipped;
      `GetMiscWarning()` carries the P1 text); `valve_trips_through_failed_child` (the rejected
      root has two indexed `BLOCK_FAILED_CHILD` descendants; a header whose parent is the second
      is noted with that parent's real `nChainWork`, L11); `valve_note_map_bounded` (the 65th
      header on one root is answered but not noted; the sum stops growing, P2);
      `valve_ignores_lowdiff_headers` (a header whose target exceeds `132/100` of its parent's is
      answered but not noted, P2); `check_tripped_valve_never_rejects`.
- [x] `qa/rpc-tests/yellowback_index.py` (adapted; the crash and `verifychain` cases are new work,
      not in the prototype's script, N38): tags from `generate` on nodes 2–4 land in `Tags`;
      medians appear once windows fill; reorg via `split_network`/`join_network` across a tag
      change with equal state hashes; `price1_reorg_across_fill_boundary` (split at exactly the
      fill bound of the fast window; branch A adds a tag, branch B a stock block; join; `pFast`
      defined on the winner only; hashes equal); `reg4_judgement_undone_on_reorg` (a reorg of depth
      `PEER_LAG + 1` across a judged tag; `yed_listminers` reverts; hashes and `-reindex-yellowback`
      equal); restart; `-reindex-yellowback`; `-reindex`; `-prune` refused;
      `crash_unflushed_chainstate` — node 3 mines `generate(30)` itself, or node 2 mines and
      `sync_blocks([2, 3])` first, then `kill9(3)` **immediately** (so `FLUSH_STATE_IF_NEEDED`
      has not written, `main.cpp:3324-3334`, P12), restart, assert
      `yed_getinfo.height == getblockcount` and `yed_getstatehash` equals node 2's, and grep
      `debug.log` for `SyncToChain: undoing` (proves the undo walk ran); repeated with `UNDO_KEEP +
      10` blocks to exercise the wipe-and-rebuild fallback (N35); `rejected_survives_kill9`
      (`kill -9` right after a rejection; restart with `-yellowbackenforce=0`; the reorg happens,
      N8); `ibd_across_accepted_invalid` (a fresh node 6 started with enforcement on after a chain
      that contains an accepted rule-breaking block at least `VALVE_BLOCKS + 1` blocks below the
      tip — Phase 5 case 4's chain — syncs to the same tip with `rejectedBlocks == 0`,
      `suppressedBlocks == 1`, `valveTripped == false` and `enforcing == true` afterwards, and
      `debug.log` carries `catch-up: accepted rule-breaking block`; on regtest the fresh node
      leaves IBD at its first fresh block, so this is BLK-2 clause 3, L11, not clause 2 — the
      clause-2 path is `check_ibd_suppresses_reject` and `-reindex` below);
      `index_start_height_above_tip` (nodes started with `-yellowbackstartheight=50` on a
      200-block chain: `yed_gethistory 1 60` returns rows `≥ 50` only; `yed_getprice 49` reports
      every price undefined); `snap_history_contiguous` (`yed_gethistory START tip` returns
      `tip − START + 1` rows whose `blockHash` chain matches `getblockhash`);
      `params_mismatch_fails_loudly` (node 4 restarted with `-yellowbacksigmaref=1` ⇒ its state
      hash differs from nodes 0, 2–3 and `yed_getinfo.params.sigmaRefBps` shows why, N18);
      `killswitch_fresh_datadir` (node 2 wiped, started `-yellowbackenforce=0` with an empty
      `Rejected`: the K21 null-tip path; it must start) and
      `killswitch_rejected_hash_not_in_mapblockindex` (a `Rejected` entry for a block the node
      never stored after `-reindex`: skipped, cleared); `blk3_unhealthy_across_reorg` (an
      unhealthy node follows a reorg without applying; `-reindex-yellowback` catches up to the
      same hash); `verifychain 4 20` at runtime leaves the index hash and `healthy` unchanged (K6);
      `verdict_parent_not_tip` (`yed_getblockverdict` refuses for a buried block, N12).
- [x] `qa/rpc-tests/yellowback_activation.py`: signalling with 2 of 3 pools (below threshold)
      never locks in; with 16 stock blocks interleaved, lock-in happens at exactly the block that
      brings the trailing window to 48 signals and not one earlier (K16); activation at
      `lockIn + 64` and enforcement from the block after it; participation halt when one pool
      stops signalling for a window (≈ 43 of 64: no halt, both floors are below it); with node 1
      mining 45 % of blocks (`mine_round_robin(shares=)`, ≈ 35 signals) the mint halt sets
      (`< 39`) while enforcement stays on (`≥ 32`) and a rule-breaking block from node 1 is still
      rejected; at ≈ 30 signals enforcement suspends (ACT-6) and the same block is accepted
      (ACT-5) — with the explicit no-partition assertion `assert_equal(len({n.getbestblockhash()
      for n in nodes}), 1)` after node 1's block while suspended and again after 20 more stock
      blocks (N35); enforcement resumes at ≥ 39 and minting only at ≥ 48 (hysteresis, L3); a node
      with `-yellowbackenforce=0` emits tags without the signal bit (MINER-1); node 5
      (`enforce=0`) reports the same activation; `act2_reorg_across_lockin` (split so branch A
      reaches 48 signals at height `L` and branch B, with node 1's stock blocks, does not; join on
      B: on every enforcing node `status == "signaling"`, `lockInHeight == 0` — UNDO restores
      `Activation`; then A wins: `locked_in` again at the same `L`) and
      `act3_reorg_across_activateheight` (enforcement flips on, off, on across a 3-block reorg
      straddling `activateHeight + 1`; a rule-breaking block on the losing branch was rejected,
      the same transaction on the winning branch before `activateHeight + 1` is accepted;
      `Rejected` holds only the orphaned hash; a vault minted on the losing branch is VOID with
      `sweepBefore`, N14); `act_forged_signal_tags` (node 1, stock, mines with a forged signal
      tag under a random `payoutKey`: activation occurs on its count alone — the count is
      self-reported, N4 — and node 5's `yed_listminers` shows the forged key; the valve half of
      the story is Phase 5 case 9); `act5_past_sunset_accepts` (nodes 2–4 restarted with
      `-yellowbackenforceuntil=<tip + 5>`: five blocks later `yed_getinfo.sunset == true`,
      `enforcing == false`, tags carry no signal bit, a rule-breaking block from node 1 is
      accepted by everyone and the vault is recorded `unbacked`, L8); `tag3_signal_only_registers_nobody`
      (after 24 signal-only blocks from node 2, `yed_listminers` omits it, `yed_getfeepayee`
      excludes it from `eligible`, `signalCount` counts it); `assert_model_matches(node)` at the
      end (N23).
- [x] `qa/rpc-tests/yellowback_rpc_contract.py` (P7): loads `doc/yellowback-rpc-contract.json`,
      calls every node-context command on a node past activation with one vault, one token and
      one rejected block in `Rejected` (so every optional field has a value), and asserts every
      documented key is present with the documented JSON type — recursively for nested objects —
      and that every documented error identifier is produced by the documented provocation
      (`quote-out-of-range` by `yed_setquote 1`, `verdict-parent-not-tip` by a buried block, …);
      the wallet context joins in Phase 6. In `main` from this phase.
- [x] CI: the `lockorder`, `sanitizers` and `coverage` jobs of §6.0 item 6 are added now (P6);
      the coverage floors are asserted from this phase for the Phase 1–3 files.

Exit: green; `git diff --stat` shows `main.cpp` and `miner.cpp` within budget and nothing in the
consensus set; the three new nightly jobs green once. **Acceptance:**

```
src/test/test_bitcoin
qa/pull-tester/rpc-tests.py -j4 --nozmq yellowback_index yellowback_activation yellowback_rpc_contract
git diff --numstat ycash-legacy...HEAD -- src/main.cpp  | awk '{exit ($1+$2>40)}'
git diff --numstat ycash-legacy...HEAD -- src/miner.cpp | awk '{exit ($1+$2>35)}'
test -z "$(git diff --stat ycash-legacy...HEAD -- src/consensus src/script src/primitives src/pow src/chainparams.cpp src/wallet/wallet.h src/wallet/wallet.cpp src/txdb.cpp src/txdb.h configure.ac)"
! git grep -n 'DoS([1-9]' -- src/yellowback src/rpc/yellowback*
git diff ycash-legacy...HEAD -- src/main.cpp | grep '^+' | grep 'DoS(' | { ! grep -v 'DoS(0'; }
! git grep -n '\bconnect(\|evhttp\|socket' -- src/yellowback src/rpc/yellowback*
git grep -n 'GetTime' -- src/yellowback src/rpc/yellowback* | grep -v 'src/rpc/yellowback.cpp\|src/yellowback/policy.cpp' | { ! grep .; }
! git grep -in roster -- src/yellowback
test -f doc/yellowback-rpc.md && grep -q 'rpcversion.*2' doc/yellowback-rpc.md
python3 -c 'import json,sys; d=json.load(open("doc/yellowback-rpc-contract.json")); sys.exit(0 if "yed_getinfo" in d and "suppressedBlocks" in d["yed_getinfo"]["returns"] else 1)'
```
plus, once each on the nightly jobs: `lockorder` (no `potential deadlock detected` in any
`debug.log`, no abort), `sanitizers` (no report) and `coverage` (floors hold for the Phase 1–3
files), recorded in the PR.
Reviewer by hand: every inserted `main.cpp` statement is inside `if (g_yellowback)` (§8.4 item 2)
— `git diff ycash-legacy...HEAD -- src/main.cpp | grep '^+' | grep -v 'g_yellowback\|#include\|^+$'`
printed in the PR and each residual line justified. Run-through on one node by hand (N28):
`src/ycashd -regtest -experimentalfeatures -yellowback -yellowbackstartheight=1
-yellowbackpayoutaddress=<s1…> <six -nuparams>`; `yed_setquote 50000 2`; `generate 70`;
`yed_gettag <tip>` shows a quote tag, `yed_getprice` three defined medians at ≥ 64 blocks, and
`yed_getactivation` is already `locked_in` with `signalCount == 64` and `lockInHeight == 64` —
on a single signalling node ACT-2 locks in at the *first* height whose trailing window is full
and at threshold, which is height 64, so the status is never observed as `signaling` at height
70 (corrected 2026-09-11 against the binary; the earlier prose was one signalling window out);
`generate 58` more ⇒ `active` at `lockInHeight + ACTIVATION_DELAY = 128`; `verifychain 4 20`
leaves `yed_getstatehash` unchanged.
Acceptance: the block above exits 0 on CI jobs `main` + `audit`.

### Phase 4 — Mining: tag, quote, template filter, `getblocktemplate` (≈ 400 lines + ≈ 50 in `miner.cpp`/`rpc/mining.cpp`)

- [x] `policy.{h,cpp}` second half: `FilterTemplate` (TPL-1/2, §4.2a signature; `MempoolCheck` and
      `TagScript` arrived in Phase 3) and the index's `TemplateInfo()` (the `getblocktemplate`
      object of §4.4, N26); the `miner.cpp` filter edits and the `rpc/mining.cpp` edits as §4.3,
      **every `rpc/mining.cpp` edit under `if (g_yellowback)`** (N10).
- [x] `qa/rpc-tests/yellowback_mining.py`: a pool's `generate` block carries the tag
      (`yed_gettag`); `getblocktemplate` returns `coinbaseaux.flags` equal to the tag push,
      `mutable` contains `coinbase/append`, `coinbasetxn.data` decodes to a coinbase whose
      scriptSig contains the tag, and the `yellowback` object; a template submitted through
      `submitblock` after a Python-side coinbase rebuild that appends `coinbaseaux.flags` is
      accepted and its tag read (the pool path, end to end; `mine_block_raw` of §6.0 item 4 —
      the framework can solve regtest Equihash, N28); `tag2_invalid_tag_is_no_tag` (node 1
      submits Python-built blocks with `version = 2`, then `flags = 0x02`, then `price = PRICE_MAX
      + 1`; every node accepts each block, `yed_gettag` → `found: false`, `yed_getprice(h).tagged
      == false`; the same block orphaned by nodes 2–4 leaves `Tags` unchanged and hashes equal);
      `tx0_coinbase_payload_registers_nothing` (a coinbase with an `OP_RETURN` MINT payload as
      `vout[1]`: `yed_gettxinfo(coinbase)` absent, `Totals` unchanged); quote older than
      `-yellowbackquotemaxage` (test sets 5 s and sleeps) ⇒ signal-only tag; `yed_setquote 0` ⇒
      signal-only; `-yellowbacksignal=0` and no quote ⇒ no tag; an unhealthy index (via
      `-yellowbacktestfault=storage:commit`) ⇒ no tag; `miner2_default_from_mineraddress` (node 2
      started with `-mineraddress=<P2PKH>` and no payout address ⇒ the tag carries its hash; with
      `-mineraddress=<ys1…>` ⇒ no tag) and `miner2_non_p2pkh_refused`
      (`-yellowbackpayoutaddress=<s3…>` ⇒ `assert_start_raises_init_error`); strict template policy
      leaves a VOID-bound mint and a would-burn transfer in the mempool and out of the block,
      `consensus` policy includes them; `tpl1_template_includes_chained_mint_transfer` (a raw MINT
      and a TRANSFER of its token in one template, both mined); a block-invalid vault spend is
      never in a template under either policy and is refused by `sendrawtransaction` on an
      enforcing node (MP-1) while the stock node accepts it; `mp1_expiry_required` (a vault spend
      with `nExpiryHeight = 0` is refused by MP-1 and absent from every enforcing template; one
      with `nExpiryHeight = refHeight + 40` is admitted and dropped by `removeExpired` 41 blocks
      later, never relayed after that, N5); `mp1_reorg_reevaluates_mempool` (a claim valid at `tip
      + 1` sits in node 2's mempool; a reorg flips its eligible set (the `fee2` shape of Phase 5);
      after the reorg it is gone from node 2's mempool — the `ConnectTip` sweep — and
      `yed_validaterawtransaction.wouldBeRejected == true`); `gbt_shape_without_flag` (node 1's
      `getblocktemplate` has no `yellowback` key and no `coinbaseaux`, exactly v4.5.0's key set).

Exit: green; budgets hold. **Acceptance:** the Phase 3 block plus

```
qa/pull-tester/rpc-tests.py -j4 --nozmq yellowback_mining
git diff --numstat ycash-legacy...HEAD -- src/rpc/mining.cpp | awk '{exit ($1+$2>35)}'
git diff ycash-legacy...HEAD -- src/rpc/mining.cpp | grep '^+' | grep -v '^+$\|^+++' | grep -c 'g_yellowback' | { read n; test "$n" -ge 3; }
```
Run-through by hand on the Phase 3 node: `getblocktemplate` has `coinbaseaux.flags` beginning
`24 59 45 44 21` (37 bytes), `mutable` ∋ `coinbase/append`, `yellowback.kind == "quote"`;
`yed_setquote 0` ⇒ `kind == "signal"`. Acceptance: exits 0 on CI jobs `main` + `audit`.

### Phase 5 — Enforcement, the soft fork (≈ 100 lines; mostly tests)

**Raw builders only (N26):** every vault below is created with `build_mint_tx` and every spend
with `build_vault_spend_raw` (the *correct* spends too, with `payload=REDEEM(feeVout)` and
`fee=(addr, zat)`); the wallet-built flows are re-run in Phase 6's lifecycle and claim tests.
`checkpoint(label)` runs after every mined block (N35).

- [ ] `qa/rpc-tests/yellowback_enforcement.py` on the standard topology after `activate()`:
      1. node 0 mints (raw); the lock passes; node 1 (stock) mines a block containing an owner-path
         spend **without a burn** built by `build_vault_spend_raw`: nodes 0, 2–4 keep their tip,
         `assert_rejected` on each, `getpeerinfo` shows `banscore == 0` on every connection
         (DoS 0), node 5 follows node 1 (the star topology delivers the block, N28) and reports
         the vault `unbacked`; **then node 1 mines two more blocks on the rejected one and relays
         them: `banscore == 0` on every connection of nodes 0, 2–4 and node 1 is still a peer of
         each (`bad-prevblk-yellowback`, N1)**; nodes 2–4 mine three blocks; node 1 and node 5
         reorg to them; state hashes agree on 0, 2–5 afterwards (the invalid block is gone from
         every chain).
      2. the same with a **claim-path sweep** without a burn (R2), and with a short burn, and
         with a correct burn but the wrong payee or a short fee (RED-3): all rejected; a
         claim-path sweep of a **VOID** vault mined by node 1 is accepted by everyone (K3) and
         never appears in an enforcing node's template (TPL-2).
      3. a correct owner-path redemption and a correct claim mined by the **stock** node are
         accepted by everyone (a stock miner's honest block is valid).
      4. before activation the same rule-breaking block is accepted by every node (BLK-1
         requires ACTIVE) and the vault is recorded `unbacked`.
      5. kill switch: node 2 has rejected a block; node 1 mines 3 blocks on its own branch
         (star split, N28) so its chain is longer; restart node 2 with `-yellowbackenforce=0`:
         node 2 reconsiders, reorgs onto it, `rejectedBlocks` is 0; restart with enforcement on
         again and mine past it.
      6. fail open on storage only: node 3 started with the fault-injection flag — four scripted
         runs, `-yellowbacktestfault=storage:check`, `:commit`, `:undo` and `template` (N38) —
         accepts the rule-breaking block, `healthy == false`, emits no tag, `getblocktemplate`
         refuses under `-yellowbackrequirehealthy`, and `-reindex-yellowback` restores it; a
         block carrying a vault spend with a `refHeight` below `START_HEIGHT`, one above `H − 1`,
         a payload of maximal length and a scriptSig of random pushes is rejected as invalid on
         every enforcing node with `healthy == true` (K1).
      7. bookkeeping: a block that fails `bad-cb-amount` *and* RED-2 never appears in `Rejected`
         (the hook runs after every consensus check; `mine_block_raw` with a wrong subsidy); for
         every hash in `Rejected`, `yed_getblockverdict` returns `blockInvalid == true` with a
         non-empty reason (§8.4 items 8 and 17, M11).
      8. `--extended` (nightly): 200 blocks of random activity with node 1 injecting a
         rule-breaking spend every ~20 blocks and random 1–6 block reorgs; invariants: no
         enforcing node ever has an unbacked vault; hashes agree; `len(Rejected)` equals the
         number of injected spends that reached a block; node 5's `unbackedCents > 0` (the
         injections happened); node 1's surviving block count equals its share minus the
         injected blocks; the ban count is 0 on every node (N3, N38).
      9. **work valve (ACT-7, L7):** pools 2–4 hold 40 % of blocks (`mine_round_robin(shares=)`)
         while the trailing window still shows ≥ 50 % signalling (node 1 forges signal tags,
         `act_forged_signal_tags`); node 1 mines a rule-breaking block and `VALVE_BLOCKS + 2 = 8`
         more on it, one at a time with `sync_blocks` between (P3: the seventh trips the valve,
         the eighth's announcement drives the reorg); assert nodes 0, 2–4 reorg onto node 1's
         chain, `yed_getinfo.enforcing == false` and `valveTripped == true` on each,
         `getinfo.errors` contains `Yellowback: work valve tripped` (P1 — the stock "invalid
         chain at least ~6 blocks longer" text is asserted **absent**, since descendants of a
         refused header are never indexed), `banscore == 0` everywhere, state hashes agree on 0,
         2–5, the vault is `unbacked`, the pools' next tags carry no signal bit; a restart of
         node 2 re-arms it (`enforcing == true`, `valveTripped == false`); five blocks of stock
         lead do **not** trip it.
      10. `tag4_garbage_coinbase_never_invalid`: node 1 mines coinbases with (i) 32 random bytes
         after the height, (ii) the magic + 31 bytes, (iii) two valid tags, (iv) a valid tag
         under node 2's `payoutKey` (K9); every node's `getbestblockhash` equal and
         `rejectedBlocks == 0` on 0, 2–4 (TAG-4, TAG-5).
      11. `fee2_reorg_changes_eligible_set`: a redemption whose payee's only tag is at height
         `R` is in the mempool; a reorg replaces block `R` with a stock block; the transaction
         names `refHeight = R` whose snapshot changed ⇒ RED-3 fails; enforcing templates exclude
         it, `yed_validaterawtransaction.wouldBeRejected == true`, and a node-1 block containing
         it is rejected (N14).
      12. `red1_refheight_window_after_reorg`: a valid owner-path spend with `nExpiryHeight = 0`
         (M13) confirmed at `H = R + 40`; reorg it out and node 1 re-mines it at `H' = R + 41` ⇒
         RED-1 fails ⇒ enforcing nodes reject; node 5 records `unbacked`.
      13. `m3_vault_spend_with_mint_payload`: node 1 mines a correct-burn owner spend whose
         `OP_RETURN` is a MINT payload: RED-1 needs a REDEEM payload, so it is **rejected**; no
         vault is created on node 5 (M3).
      14. `blk3_unhealthy_across_reorg` and `red4_underwater_at_r_not_at_h` are in Phases 3 and 6.
      15. **catch-up (BLK-2 clause 3, L11)** `valve_catchup_offline_node`: node 2 is
         disconnected (`disconnectnode`, no restart, so it is *not* in IBD); node 1 mines a
         rule-breaking block and 8 more; reconnect: node 2 follows to node 1's tip with
         `rejectedBlocks == 0`, `suppressedBlocks == 1`, `valveTripped == false`, `enforcing ==
         true`, `banscore == 0`, and `debug.log` carries `catch-up: accepted rule-breaking
         block`; **variant within the bound:** the same with 3 blocks: node 2 rejects
         (`rejectedBlocks == 1`), stays on its branch, and when node 1 extends to
         `VALVE_BLOCKS + 2` the valve trips through the `FAILED_CHILD` path (the descendants
         were indexed before the rejection) and node 2 converges; **variant after a restart
         beyond a day:** `advance_clock(2 · nMaxTipAge)` on node 2, restart it, reconnect: it is
         in IBD (clause 2), accepts everything, `rejectedBlocks == 0`, `suppressedBlocks == 0`.
- [ ] `qa/rpc-tests/yellowback_stock_node.py` (N35): node 1 has no `yed_*` in `help`; its
      `getblocktemplate` has no `yellowback` key; node 1 mines and relays through every scenario
      above; with `--stock-binary=<path>` node 1 is that binary (nightly: the `ycash-legacy`
      build, P9) — `yellowback_enforcement.py` takes the same option.
- [ ] `qa/rpc-tests/yellowback_stockparity.py` (nightly, N10): the same 300-block scripted
      scenario (mine, transactions, a reorg, `getblocktemplate`, `getblock`) driven against a
      `ref/ycash` v4.5.0 binary and the fork binary **without** `-yellowback`; assert equal
      `getbestblockhash`, `gettxoutsetinfo.hash_serialized`, equal `getinfo` and equal
      `getblocktemplate` key sets (minus `curtime`/`longpollid`) at every step (§8.4 item 21).

Exit: green in CI including nightly. **Acceptance:** the Phase 4 block plus

```
qa/pull-tester/rpc-tests.py -j4 --nozmq yellowback_enforcement yellowback_stock_node
qa/rpc-tests/yellowback_enforcement.py --extended        # nightly
qa/rpc-tests/yellowback_stockparity.py                   # nightly; needs REF_YCASHD=<ycash-legacy build>/src/ycashd (a git worktree in CI, P4)
qa/rpc-tests/yellowback_stock_node.py --stock-binary="$REF_YCASHD" && qa/rpc-tests/yellowback_enforcement.py --stock-binary="$REF_YCASHD"   # nightly, P9
```
Run-through by hand on the six-node playground (`--noshutdown --nocleanup`): `ycash-cli
-datadir=node2 yed_getinfo` shows `rejectedBlocks == 1`, `getpeerinfo[*].banscore == 0` and
node 1 among the peers. Acceptance: exits 0 on CI jobs `main` + `audit` (+ `nightly` green once).

### Phase 6 — Wallet: mint, send, redeem, claim (≈ 800 lines)

- [x] `doc/yellowback-rpc.md` v2 extended with the wallet context at the **start** of this phase
      (Phase 7b-b's gate, M7) — every field of §4.5's wallet context, incl. `yed_sweep`.
- [x] `txbuilder.cpp` per §4.2a: `BuildMint` (class or lock length, fee output, payee),
      `BuildTransfer` (reuse), `BuildRedeem` (owner path, complete), `BuildClaim`, **`BuildSweep`**
      (L10), `SignVaultSpend`, `SignerBranchId`/`VerifyAllInputs` moved here, Sapling shapes per
      §4.6; `wallet.cpp` without pending records; wallet RPCs of §4.5 incl. `yed_sweep` with its
      acknowledgement and the `IsAbandoned()` gate (§4.6), `change-floor` and
      `not-a-yellowback-address` identifiers.
- [x] `yellowback_lifecycle.py` (adapted; the four wallet-flow scripts return to CI now, N26): mint
      class A; 0-conf lock; refHeight snapshot vs a later price drop; 2-block reorg tolerance;
      send; change floor (`change-floor` from `yed_send` and from `yed_claim`); plain-YEC burn
      recorded; under-assigned raw transfer; **one-step redeem** after the lock; `yed_redeem`
      before the lock refuses; the enforcement fee lands at an eligible payee (`yed_getfeepayee`
      lists it and its default choice matches the mined output); a raw redemption paying a key
      outside `E(R)` or a short amount is rejected by enforcing nodes and one paying a non-default
      eligible key is accepted; FEE-0 when no pool has tagged in the window;
      `expired_transaction_display` (a wallet MINT left unmined past `nExpiryHeight`:
      `yed_gettxinfo.expired == true`, `yed_listtransactions` row `expired`, no index trace,
      N39); `sweep_refused_while_enforcing` (`yed_sweep` on an ACTIVE vault with enforcement on
      ⇒ `sweep-not-abandoned`; with the wrong second argument ⇒ `sweep-acknowledgement-missing`);
      `assert_model_matches(node, full=True)` at the end (P8).
- [x] `yellowback_claim.py`: mint; price crash — the mock-price schedule is `price(0.01)` on all
      three pools then `mine_round_robin(64)`: `P_claim = max(pMid, pSlow)`, both must fall,
      `pSlow` is the lower median of a 64-block window at two-thirds fill so ≥ 33 low quotes are
      needed, and the divergence halt fires meanwhile without affecting claims (HALT-4 is MINT-4
      only, N28); before `claimHeight` a claim fails CLTV (`sendrawtransaction` rejects
      `non-final`); after it node 5's wallet (holding YED received from node 0) claims with
      `yed_claim`; vault `CLAIMED`, supply down by the debt, claimant holds the collateral; a
      claim on a healthy vault is refused by the wallet and, as a raw transaction from node 1,
      rejected by enforcing nodes (RED-4); a VOID vault's claim path is rejected; the owner can
      still redeem an underwater vault via the owner path; `red4_underwater_at_r_not_at_h` (the
      vault is underwater at `R`, the price recovers by `H`; the claim is still valid — the rule
      reads `R`); **sweep (L10):** `sweep_refused_when_merely_suspended` (signalling drops below
      50 % for one window: `enforcementSuspended == true` but `yed_getinfo.abandoned == false`,
      `yed_sweep` ⇒ `sweep-not-abandoned`); `sweep_builds_under_abandonment` (signalling stays
      below 50 % for `ABANDON_BLOCKS = 128`: `abandoned == true` on every node incl. node 5,
      `yed_getvault.sweepBefore == claimHeight` on the ACTIVE vault, `yed_listpositions.canSweep`;
      node 0's `yed_sweep <vault> "I understand this leaves YED unbacked"` returns a txid; node 1
      mines it; on every node the vault is `CLOSED, unbacked = true`, `unbackedCents` grew by the
      debt, `yed_listtransactions.type == "sweep"`; nodes 0, 2–4 also apply it — enforcement is
      suspended, ACT-5 — and hashes agree); `sweep_relayed_by_own_node` (L13: the sweep from
      node 0's `yed_sweep` is in node 0's `getrawmempool`, reaches node 1's and node 2's
      mempools, and node 2's `getblocktemplate` includes it — MP-1 and TPL-1 stand down under
      abandonment; `yed_validaterawtransaction(hex).wouldBeRejected == false`; the returned `hex`
      decodes to the same txid); `sunset_alone_is_not_abandonment` (L12: `-yellowbackenforceuntil`
      behind the tip on nodes 2–4 while node 1 forges signal tags so the window stays ≥ 50 %:
      `sunset == true`, `enforcing == false`, but `abandoned == false` and `yed_sweep` ⇒
      `sweep-not-abandoned`); `sweep_after_sunset_without_successor` (the same with no forged
      signals: the pools' tags drop the bit past the sunset, `ENFORCEMENT` sets, and after
      `ABANDON_BLOCKS` more blocks `abandoned == true` on every node and the sweep builds);
      `assert_model_matches(node, full=True)` at the end (P8).
- [x] `yellowback_void_mint.py` (adapted): each failing MINT rule ⇒ VOID, one case per rule named
      `mint1_`…`mint8_` (the M10 grep needs each identifier); `void_release_via_yed_redeem` (L14:
      `yed_redeem` on the VOID vault before `lockHeight` ⇒ `vault-locked`; at `lockHeight` it
      returns `{txid, burnedCents: 0, feeZat: 0, payee: null}`; the transaction has no
      `OP_RETURN` and no fee output; every node — enforcing, stock, observer — mines or accepts
      it; the vault is `CLOSED, unbacked = false`; `yed_listpositions.canRedeem` was true and
      `yed_getvault.sweepBefore == claimHeight` before the release); mint before activation ⇒
      VOID (wallet refuses with `mintpol-not-active`;
      raw succeeds as VOID); mint under each halt ⇒ VOID and the wallet refuses with the matching
      `mintpol-*` identifier (MINTPOL-1 per halt, M10); `mint6_cap_race_after_reorg` (two mints
      that together exceed the cap on different branches; the loser becomes VOID on join;
      `voidVaults == 1`, `voidReason == "mint-supply-cap"`).
- [x] `yellowback_pricefeed.py`: window fill boundary per window (`⌈W/2⌉` fast, `⌈2W/3⌉` mid and
      slow, L9); `P_mint = min` in a rising market, falling market; divergence halt fires within
      the fast window on a crash and clears on re-convergence; global-ratio halt and
      `halt2_fires_at_exact_threshold` (`globalRatioBps == 24,999` halts, `25,000` does not);
      `halt3_fires_on_mid_vs_slow` (the second disjunct); σ multiplier rises after a volatile
      series and is capped; `sigma1_one_pool_cannot_inflate` (node 2 alternates ±20 % while 3–4
      hold ⇒ `sigmaMultBps == 10000`); HALT-1 by name when a window empties; a lying pool is
      penalised for `N_PENALTY`: the wallet's default choice skips it while it stays in `E(R)` and
      a raw redemption paying it is still accepted (L1); accuracy weighting changes payee frequency
      (200 distinct selectors at one `R` through `yed_getfeepayee`, no mining; the accurate pool's
      share within `[0.6, 0.72]` for a 2:1 weight, N28); registration lapses `N_REG` blocks after
      a pool's last quote tag (REG-1); **`price1_quote_majority_needs_fill` (L9):** node 1 inserts
      quote tags at 2× the pools' price with 26 % of blocks while the pools fill 50 % of the mid
      and slow windows ⇒ `pClaim` stays unchanged or undefined (below two-thirds fill) and
      `yed_listclaimable` is empty; with node 1 at 34 % of blocks and fill at two-thirds ⇒
      `pClaim` moves and the mint gate reflects it (the accepted cost of a quote-tag majority at
      the new bound); `assert_model_matches(node)` at the end (N23).
- [x] `yellowback_wallet_restore.py`, `yellowback_sapling.py` adapted (no co-signer path; the
      `ys1…` REDEEM shape's fee output wherever `feeVout` names it — `vout[2]` with YED change,
      `vout[1]` without, N39).

- [x] `yellowback_model.py`, the accounting half (P8): IN-1..3, TX-0, MINT-1..8, XFER-1..3 and
      RED-1..4 modelled in Python from `getblock <hash> 2` (transparent inputs, `vout` scripts,
      the `OP_RETURN` payload decoded by a Python port of §3.3) and the snapshot half's prices;
      `assert_model_matches(node, full=True)` compares `yed_gettxinfo` for every transaction the
      model classifies as Yellowback-relevant, `yed_listvaults` and `yed_getstats` totals at the
      tip, and the state hash. Required at the end of `yellowback_lifecycle.py`,
      `yellowback_claim.py`, `yellowback_enforcement.py --extended` and `yellowback_rc1.py`.
- [x] `yellowback_rpc_contract.py` gains the wallet context (P7): every wallet command incl.
      `yed_sweep` under a forced abandonment and `yed_redeem` on a VOID vault.

Exit: green; `src/wallet/wallet.{h,cpp}` untouched; every rule identifier in §3.8–3.9 has a test
(the §7 table, checklist §8.4 item 9). **Acceptance:** the Phase 5 block plus

```
qa/pull-tester/rpc-tests.py -j4 --nozmq yellowback_lifecycle yellowback_claim yellowback_void_mint yellowback_pricefeed yellowback_wallet_restore yellowback_sapling yellowback_rpc_contract
test -z "$(git diff --stat ycash-legacy...HEAD -- src/wallet/wallet.h src/wallet/wallet.cpp)"
grep -q 'def model_transaction' qa/rpc-tests/test_framework/yellowback_model.py && grep -q 'full=True' qa/rpc-tests/yellowback_lifecycle.py qa/rpc-tests/yellowback_claim.py
for id in TAG-1 TAG-2 TAG-3 TAG-4 TAG-5 PRICE-1 PRICE-2 SIGMA-1 FEE-0 FEE-1 FEE-2 FEE-W REG-1 REG-2 REG-3 REG-4 IN-1 IN-2 IN-3 TX-0 MINT-1 MINT-2 MINT-3 MINT-4 MINT-5 MINT-6 MINT-7 MINT-8 XFER-1 XFER-2 XFER-3 RED-1 RED-2 RED-3 RED-4 ACT-1 ACT-2 ACT-3 ACT-4 ACT-5 ACT-6 ACT-7 HALT-1 HALT-2 HALT-3 HALT-4 BLK-1 BLK-2 BLK-3 TPL-1 TPL-2 TPL-3 MP-1 MINER-1 MINER-2 MINER-3 MINTPOL-1 SNAP UNDO; do git grep -qE "^(//|#) Rule: .*\b$id\b" -- src/test/yellowback_*.cpp qa/rpc-tests/yellowback_*.py || { echo "no test tagged $id"; exit 1; }; done
```
Run-through by hand on the playground: `yed_mint 10000 48` on node 0, `generate 49` on a pool,
`yed_redeem <txid>` returns a txid and `yed_getvault` shows `CLOSED`, `feePaidZat ≥ 0.5 YEC` and
the fee output's address ∈ `yed_getfeepayee(...).eligible`. Acceptance: exits 0 on CI jobs
`main` + `audit`.

### Phase 7 — Quote agent, pool kit, devnet, documentation (Python and docs; 0 C++)

- [x] `contrib/yellowback/yellowback_price.py` split out; `yellowback-quote` daemon with
      `--mock-price`; unit tests moved; `yellowback_fed.py` deleted.
- [x] `qa/rpc-tests/yellowback_quote.py`: the test writes `<tmpdir>/quote-<i>.toml` per pool
      (`rpc_url = rpc_url(i)` with the framework's `rpcuser`/`rpcpassword` — no cookie —
      `[[sources]]` = one `generic` preset pointing at nothing) and runs three `yellowback-quote
      --conf … --mock-price <file>` as `subprocess.Popen` it terminates in `tearDown` (N28); tags
      follow the mock; a stopped agent turns its node signal-only after the staleness limit; a
      source outage below `min_sources` clears the quote after `fail_polls` (L5) and the node
      goes signal-only within a minute; `--once` exit codes.
- [ ] Pool kit (§5): survey which stacks Ycash pools run (§12 Q9), write per-stack notes, the
      `check-coinbase` tool, monitoring snippet.
- [x] `yellowback-devnet` v2 with the `check` subcommand (§5); `doc/yellowback.md` (user; the
      abandonment and sweep story of §8.1), `doc/yellowback-mining.md` (pool operator runbook:
      options, the mainnet signal default (L4), quote agent, monitoring, kill switch, the
      `-reindex` procedure (M12, N2), the valve and its own warning text (N11, L7, P1), catch-up
      suppression and what `suppressedBlocks` means (L11), the sunset (L8), filter-only mode for
      non-participating pools (N3), the payout-key backup rule, and the incident playbook of
      Phase 10 in skeleton — the three scenarios and the 7-day fix cadence; the contact list and
      on-call owner are filled in before the signalling announcement (P14));
      `doc/yellowback-rpc.md` v2 finalised (its node and wallet contexts were written in Phases 3
      and 6).

Exit: `yellowback_quote.py` and `test_yellowback_price.py` green; `yellowback-devnet up` ends with
`yed_getactivation.status == "active"` and `yed_getstats.mintingAllowed == true`; `check-coinbase`
finds the tag on a devnet block; `doc/yellowback.md` passes §8.4 item 18. **Acceptance:**

```
python3 -m unittest contrib/yellowback/test_yellowback_price.py contrib/yellowback/test_yellowback_quote.py
qa/pull-tester/rpc-tests.py -j2 --nozmq yellowback_quote
../.venv/bin/python contrib/yellowback/devnet/yellowback-devnet up && ../.venv/bin/python contrib/yellowback/devnet/yellowback-devnet check
../.venv/bin/python contrib/yellowback/devnet/yellowback-devnet status | grep -c 'eligible: true' | { read n; test "$n" -eq 3; }
contrib/yellowback/pool/check-coinbase $(ycash-cli -regtest -datadir=$(../.venv/bin/python contrib/yellowback/devnet/yellowback-devnet cli --datadir 2) getblockcount) | grep -q 'kind: quote'
../.venv/bin/python contrib/yellowback/devnet/yellowback-devnet down
! grep -n 'no consensus change' doc/yellowback.md
diff <(sed -n '/^### 8.1 Trust statement/,/^### /p' doc/yellowback-spec.md | sed '1d;$d') <(sed -n '/^## Trust statement/,/^## /p' doc/yellowback.md | sed '1d;$d')   # both files are in the fork (P4)
for w in yellowbackenforce=0 reindex valve sunset filter-only incident catch-up; do grep -q "$w" doc/yellowback-mining.md || { echo "runbook lacks $w"; exit 1; }; done
contrib/yellowback/yellowback-quote --conf contrib/yellowback/pool/yellowback-quote.toml.sample --dry-run --mock-price /dev/stdin <<< 0.05
```
Acceptance: exits 0 on CI jobs `main` + `python`.

### Phase 7b — YecWallet (`yecwallet-dd`; two halves, N26; ≈ 900 lines changed, ≈ 700 removed)

- [ ] **7b-a** (may start at Phase 3's exit, gated on the node context of `doc/yellowback-rpc.md`
      v2): first commit bumps `yellowbackrpc.h` to `RPC_VERSION = 2` (N27); the status banner
      (incl. `valveTripped`, `sunset`, `abandoned`), overview, vaults and claim-list screens of
      §4.8; the offline QTest cases of §4.8 for those screens; the `wallet` CI job (§6.0 item 6).
- [x] **7b-b** (at Phase 6's first commit, gated on the wallet context): mint, send, redeem,
      claim and sweep screens and dialogs; the remaining offline QTest cases; the devnet
      end-to-end case (mint → send → redeem → claim → sweep after a forced abandonment), gated on
      `YELLOWBACK_DEVNET_DIR` and `QSKIP`ed without it (N28) — written this time (it was the
      prototype's leftover).
- [ ] Copy review against §8.1; `build.sh --package` with the v2 `ycashd`.

Exit: the offline QTest cases are green under `QT_QPA_PLATFORM=offscreen` and `build.sh
--package` produces the artefact (mechanical); a non-developer completes mint, send, redeem and
claim on the devnet with the wallet alone (acceptance). **Acceptance** (from `yecwallet-dd/`):

```
cmake -S . -B build -DCMAKE_PREFIX_PATH=$(brew --prefix qt) && cmake --build build --target yellowback_test
QT_QPA_PLATFORM=offscreen build/bin/yellowback_test
grep -rn 'trustless' src/ | { ! grep .; }
bash build.sh macos-arm64 --package --ycashd ../ycash-dd/src/ycashd && ls artifacts/*.dmg
```
Hand acceptance with a written script: the rc1 run-through's steps 1, 2, 3, 5 and 8b performed
in the GUI on the devnet, screenshots attached to the PR. Acceptance: exits 0 on CI job `wallet`.

### Phase 8 — Hardening and review (≈ 2 weeks)

- [ ] Wallet hardening H1–H12 (coin selection and coin locking; wallet tier, never consensus):
      - **H1** Replace smallest-first accumulation with a floor-aware selector for `yed_send`,
        `yed_sendmany`, `yed_redeem` and `yed_claim` (H1 extended to `yed_claim`, which did not
        exist when the hardening plan listed three RPCs; a CLAIM selects YED like a REDEEM, N39):
        exact match first, then a single input with valid change, then greedy with extension, then
        a bounded search. Deterministic; unit-tested against a table of adversarial coin sets.
      - **H2** TRANSFER never burns: if no selection yields change of 0 or ≥ `MIN_OUTPUT`, refuse
        (the §4.6 change floor) with a structured message carrying the nearest workable amounts
        below and above.
      - **H3** New RPC `yed_estimatesend` (dry run, no signing, no locking): given recipients and
        amounts, returns the selection, the change and, when the amount is unworkable, the
        alternatives; the GUI calls it while the user types. Mirrors `yed_estimatecollateral`.
      - **H4** REDEEM may burn a sub-dollar remainder: when the only selections leave change in
        `(0, MIN_OUTPUT)` the builder burns it (bounded by $0.99), reports `extraBurnCents`, and the
        dialog shows it; selections with valid change are still preferred.
      - **H5** Yellowback locks are protected: `lockunspent` refuses to unlock an outpoint the
        Yellowback wallet holds and `lockunspent true` re-applies them; the deliberate escape hatch
        is `yed_unlockcoin <txid> <n> "I understand this burns YED"`.
      - **H6** A wallet that holds YED refuses to start without `-yellowback`: if the datadir has the
        index and the flag is absent, `init` fails with a message; `-yellowback=0` given explicitly
        acknowledges that YED outputs become spendable as plain YEC.
      - **H7** `sendrawtransaction` guards owned YED: with `-yellowback` on, a raw transaction that
        spends a `Tokens` outpoint that is mine and whose payload does not reassign it is refused
        unless a new third parameter `allowyedburn` is true (same shape as `allowhighfees`).
      - **H8** Re-lock after key import: `importprivkey`, `importwallet`, `importaddress` (after
        their rescan) and `z_importkey`'s transparent path call `Reconcile()`, so imported YED is
        locked before the next block.
      - **H9** Documented, not enforced: keys imported into other software, `-yellowback` nodes that
        are not this wallet, YED sent to a recipient that does not run the overlay (the `ye…`
        prefix is the only technical guard and it stays).
      - **H10** `yed_getinfo` reports `lockedOutputs` and `protectedByIndex: true`; the GUI treats a
        mismatch between `lockedOutputs` and `yed_listunspent` as the trigger for `yed_lockcoins`.
      - **H11** Input cap stays 250 (`txbuilder.cpp:232`; 250 P2PKH inputs ≈ 37 kB, under
        `MAX_TX_SIZE`); no consolidation RPC — the greedy stage consolidates small outputs.
      - **H12** Tests before code for H1 (table-driven unit test) and H5/H6/H7 (functional); the
        lifecycle test's `lockunspent false` step becomes `yed_unlockcoin`.

      H5/H7/H8 touch `src/wallet/rpcwallet.cpp` and `rpc/rawtransaction.cpp`, the
      wallet-tier row of §4.1 (M7); no `rpcversion` bump (additions only).
- [ ] `yellowback_reorg_stress.py` adapted (random tags, random enforcement events; records how
      often a wallet-built spend becomes invalid across a reorg, N14).
- [ ] `yellowback_runbook.py` (nightly, N35): node 2 rejects node 1's block, then mines 105 blocks
      alone (split); node 1's branch grows to 110; join; node 2's valve trips at six blocks of
      lead (so the `MAX_REORG_LENGTH` shutdown is reached only with the valve disabled by the
      test flag `-yellowbacktestfault=novalve`): with it disabled node 2 refuses (log
      `MAX_REORG_LENGTH`) and shuts down — assert the process exits; restart `-reindex` ⇒ follows
      node 1, `rejectedBlocks == 0` (N2); restart with enforcement on ⇒ stays on the chain and the
      buried invalid block is **not** re-rejected (M12's concern).
- [ ] DoS review: `EvaluateBlock` cost per block is linear in Yellowback-relevant transactions
      plus one median per window per block (bounded); `MempoolCheck` `O(inputs)` for
      non-Yellowback transactions (`mempoolcheck_bench`, N6); `TxLog` bounded by
      Yellowback-relevant transactions (N7); `Rejected` growth (one entry per rejected block,
      pruned below `tip − UNDO_KEEP`) and the valve's note map (cleared on trip; at most
      `VALVE_NOTE_CAP` notes per rejected root, each requiring a header whose proof of work
      passed `CheckBlockHeader` and whose target lies within the consensus loosening of its
      parent's — P2, `valve_note_map_bounded`, `valve_ignores_lowdiff_headers`); snapshot size
      (≈ 120 B/block ≈ 50 MB/yr); `yed_setquote` and `yed_validaterawtransaction` behind RPC
      auth; the `sanitizers` and `lockorder` jobs green for the whole phase (P6).
- [ ] Greps: `GetTime` only in `rpc/yellowback.cpp` and `policy.cpp` (M11; the `tag.cpp`
      determinism grep is Phase 0's, N26); lock order — no `LOCK(mempool.cs)`/`LOCK2(…, mempool.cs)`
      after `cs_yellowback` in `src/rpc/yellowback*.cpp` and `src/yellowback/` (N25); the three
      `transaction_builder` methods called only from `src/yellowback/` (§8.4 item 22).
- [ ] `doc/yellowback-review.md` v2: diff-budget actuals, the hook table with the four-part
      check filled in for each hook, the fail-open, kill-switch, valve and sunset evidence, the
      §8.4 checklist with test names; the §8.5 statement sent to the Ycash maintainers.
- [ ] **rc1 regtest run-through** — `qa/rpc-tests/yellowback_rc1.py` (`--nocleanup`; prints a
      state-hash ledger the release manager pastes into the tag message, N31):

      | Step | Action | Expected `yed_*` output / assertion |
      |---|---|---|
      | 0 | `activate(pools=[2,3,4], stock=1)` | `yed_getactivation.status == "active"` on 0, 2–5; `H0 = statehash(0) == statehash(2..5)` |
      | 1 | node 0 `yed_mint 10000 48` (and a second and third vault for steps 3 and 6) | returns `termClass: "A"`, `feeZat ≥ 5e7`, payee ∈ `yed_getfeepayee(R, …).eligible`; after 1 block `yed_getvault.status == "ACTIVE"`; `yed_getstats.supplyCents == 30000`; `H1` equal on 0, 2–5 |
      | 2 | `yed_send` 4,000 cents to node 5 | `yed_getbalance` 26,000 / 4,000; `H2` equal |
      | 3 | mine to `lockHeight`; `yed_redeem` the second vault | `burnedCents == mintedCents`; vault `CLOSED`; `H3` equal |
      | 4 | `generate(20)` on node 2, `sync_blocks([2, 3])`, then `kill9(3)` at once (P12); restart | `yed_getinfo.height == getblockcount`; `statehash(3) == statehash(2)`; `debug.log` shows `SyncToChain: undoing` |
      | 5 | `price(0.01)` for 64 blocks; mine to `claimHeight`; node 5 `yed_claim` the first vault | `yed_listclaimable` lists it beforehand; vault `CLAIMED`; `supplyCents == 10000`; `H5` equal on 0, 2–5 (same chain) |
      | 6 | node 1 mines `build_vault_spend_raw(path="owner", burn_inputs=[])` on the third vault, then two more blocks on it | `assert_rejected` on 0, 2–4; `banscore == 0`; node 1 still a peer; node 5 follows and shows `unbacked: true`; nodes 2–4 mine 3 blocks; all six on one tip; `H6` equal on 0, 2–5 |
      | 6b | **valve:** `mine_round_robin(shares=)` gives node 1 60 % while forged signal tags keep the window ≥ 50 %; node 1 mines a rule-breaking block plus `VALVE_BLOCKS + 2` (P3) | nodes 0, 2–4 reorg onto it; `enforcing == false`, `valveTripped == true` on each; `getinfo.errors` contains `Yellowback: work valve tripped` (P1); `banscore == 0`; `H6b` equal on 0, 2–5; restart nodes 0, 2–4 (re-arm); `enforcing == true` |
      | 6c | **catch-up (L11):** disconnect node 3; node 1 mines a rule-breaking block on the fifth vault plus 8; reconnect | node 3 follows without a rejection: `rejectedBlocks` unchanged, `suppressedBlocks == 1`, `enforcing == true`, `valveTripped == false`; `H6c` equal on 0, 2–5 |
      | 7 | restart node 2 `-yellowbackenforce=0` while node 1's chain is longer by 3 | node 2 reorgs, `rejectedBlocks == 0`; restart enforcing; mine 2 on node 3; node 2 follows; `H7` equal on 0, 3–4; node 2 differs (it applied the unbacked spend) — **expected and printed** |
      | 8 | node 4 `-reindex`; node 0 `-reindex-yellowback` | `statehash(4) == statehash(3)`; `statehash(0) == statehash(3)`; `verifychain 4 50` on node 3 leaves `healthy == true` and the hash unchanged |
      | 8b | **sweep:** pools stop signalling for `ABANDON_BLOCKS` (128) | `yed_getinfo.abandoned == true` on 0, 2–5; node 0 `yed_sweep <fourth vault> "I understand this leaves YED unbacked"` returns a txid and `hex`; the transaction is in node 0's and node 2's mempool (L13); node 2 mines it; vault `CLOSED, unbacked`; `type == "sweep"`; `H8b` equal on 0, 2–5 |
      | 8c | **VOID release (L14):** a raw mint with `refHeight < START_HEIGHT` (VOID, `voidReason == "bad-mint-ref-height"`); mine to its `lockHeight`; node 0 `yed_redeem <void vault>` | returns `burnedCents == 0`, `feeZat == 0`; the vault is `CLOSED, unbacked == false` on every node; `H8c` equal on 0, 2–5 |
      | 9 | final | `assert_model_matches(node 0, full=True)` (P8); ledger `H0..H8c` printed; exit 0 |

Exit: every §8.4 item ticked with an evidence link (test name, grep output or reviewer initials)
in `doc/yellowback-review.md`; external review sign-off (§8.5); tag `yellowback-v2-rc1`.
**Acceptance:**

```
test "$(grep -c '^| *[0-9]* *|.*| *\(yellowback_[a-z_0-9]*\|grep:\|reviewer:\|job:\)' doc/yellowback-review.md)" -eq 25
qa/rpc-tests/yellowback_reorg_stress.py --blocks 600 --seed 1 && qa/rpc-tests/yellowback_reorg_stress.py --blocks 600 --seed 2 && qa/rpc-tests/yellowback_reorg_stress.py --blocks 600 --seed 3
qa/rpc-tests/yellowback_enforcement.py --extended
qa/rpc-tests/yellowback_runbook.py
qa/rpc-tests/yellowback_rc1.py --nocleanup
qa/yellowback-coverage-floor.sh coverage/lcov.info                  # from the coverage job's artefact (P6)
```
every §8.4 grep re-run in CI job `audit` and pasted into `doc/yellowback-review.md` with its
output; the last seven nightly runs of `lockorder`, `sanitizers`, `coverage` and the
`--stock-binary` scripts green (P6, P9), linked from the review document; `git tag
yellowback-v2-rc1` only after the rc1 run-through passes. Acceptance: exits 0 on CI jobs
`main` + `audit` + `nightly` + `lockorder` + `sanitizers` + `coverage`.

### Phase 9 — Testnet with real pools (≥ 4 weeks)

- [ ] `startHeight` (testnet) set at least two weeks of blocks past the release date (M14); at
      least two independent testnet pools run the release with real pool software and the quote
      agent on real sources; a third stays stock. **Fallback (P14):** if fewer than two pool
      operators commit to testnet within two weeks of the rc1 tag, the team runs the surveyed
      pool stacks itself (§12 Q9 — one instance per stack, each on its own node and payout key)
      on hashpower it supplies, with the stock pool likewise team-run; D9 is then executed per
      stack rather than per operator, D1–D14 stand, and the report records the substitution so
      the Phase 10 outreach knows no operator has yet run the kit unaided.
- [ ] Activation on testnet per §7 of the proposal; then the drills below (N33). Minimum
      durations: D1 3.5 d, D3 1 d, D10 4 w, D14 2 d, everything else within the soak. Pass = every
      row green in `doc/yellowback-testnet-report.md`, committed before the `yellowback-v2` tag.

      | Drill | Procedure | Pass criterion | Evidence artefact |
      |---|---|---|---|
      | D1 Activation | ≥ 2 pools signal; the stock pool mines ≥ 25 % | `yed_getactivation` reaches `locked_in` at the first height where the trailing window ≥ 75 %, `active` exactly `ACTIVATION_DELAY` later, on every enforcing node; ≤ 2 × 2,016 blocks (≈ 3.5 d) | `yed_getactivation` JSON from each node at lock-in and activation; `yed_gethistory lockIn−5 lockIn+5` |
      | (minimum durations for the revision-6 drills: D15 ≥ 28 h, D16 ≥ `ABANDON_BLOCKS` + one window ≈ 5.3 d) | | | |
      | D2 Rule-breaking block | the stock pool mines an owner-path spend without a burn (`build_vault_spend_raw` against a testnet vault, submitted through the pool's `submitblock`), then two more blocks on it | every enforcing node: `rejectedBlocks += 1`, `getblock(h).confirmations == −1`, `banscore == 0` on all peers and the stock pool still connected, `getbestblockhash` equal across enforcing nodes within 3 blocks; the `unbacked` recorded on an `enforce=0` observer | `yed_getblockverdict <hash>` from 3 nodes; `getpeerinfo` dumps |
      | D3 Lying pool | one pool publishes `P × 1.5` for 1,152 blocks (24 h) | `yed_listminers` shows it `penalizedUntil > tip` and `accuracyBps` falling; `pMint` moves by ≤ that pool's share percentile; a `yed_mint` on a wallet with the default policy names a different payee (`yed_getfeepayee`); a raw redemption paying it is still mined | hourly `yed_getprice` + `yed_listminers` CSV; the redemption txid |
      | D4 Agent death | `systemctl stop yellowback-quote` on one pool for 1 h | within `2 × poll_seconds` after two failed polls the pool's tags are signal-only (`yed_gettag`); `signalCount` unchanged; `yed_listminers.eligible` false after `PAYEE_WINDOW` | `yed_gettag` for each of its blocks in the hour |
      | D5 Kill switch | a pool flips `yellowbackenforce=0`, restarts; 6 h; flips back | its tags lose the signal bit (MINER-1); `signalCount` drops by its share; if it had `Rejected` entries they are reconsidered; on re-enable it stays on the chain | `yed_getinfo.miner` before/after; log lines `ReconsiderBlock` |
      | D6 Deliberate reorg | two enforcing pools mine a 3-block private branch containing a valid redemption, then release | all enforcing nodes reorg; `UndoDisconnect` runs (log); `Judgements`/`Activation` consistent; state hashes equal; the redemption's vault `CLOSED` once, `closeHeight` updated | `yed_getstatehash` pre/post from 3 nodes; `yed_getvault` |
      | D7 Cold rebuild | a fresh node syncs from genesis with `-yellowback` (across D2's accepted-on-observer block: it must not reject during IBD, N2); a second with `-reindex-yellowback` on an existing datadir | both `yed_getstatehash` equal the running pools' at the same height; `rejectedBlocks == 0` on the fresh node; sync time recorded | hashes + timing |
      | D8 Suspension | pools drop below 50 % signalling for a window (coordinated) | `ENFORCEMENT` bit set; a stock rule-breaking block is accepted by everyone (no partition); resume at 60 %: `haltMask` clears; minting only at 75 % | `yed_getactivation.history` |
      | D9 Real pool software | each pool's stack (§12 Q9) | `check-coinbase` finds a `quote` tag on ≥ 95 % of that pool's blocks over 576 blocks; coinbase `scriptSig ≤ 100` | `check-coinbase` log |
      | D10 σ calibration | 4-week soak | `sigmaMultBps ∈ [10000, 15000]` on ≥ 95 % of snapshots at realised volatility (M14) | `yed_gethistory` export + the exchange series |
      | D11 Crash consistency | `kill -9` a pool node mid-day; restart | `yed_getinfo.height == getblockcount` within 60 s; hash equal to peers | log excerpt |
      | D12 Work valve (L7) | with the enforcing pools at < 50 % of real hashpower but the window still ≥ 50 % (coordinated: one pool keeps signalling with enforcement off through a test build), the stock pool mines a rule-breaking block and 8 more | every enforcing node: `valveTripped == true`, `enforcing == false`, on the stock chain within 9 blocks, `getinfo.errors` contains `Yellowback: work valve tripped` (P1), `banscore == 0`; a restart re-arms; state hashes equal on the enforcing set afterwards | `yed_getinfo` from every enforcing node at trip and after restart; `debug.log` excerpts |
      | D15 Catch-up (L11) | one enforcing node is taken offline for 2 h (under `nMaxTipAge`) while the stock pool mines a rule-breaking block that the enforcing pools — briefly a minority by arrangement, as in D12 — end up building on; the node is brought back | it follows the chain with `rejectedBlocks` unchanged, `suppressedBlocks == 1`, `enforcing == true`, no valve trip, and the `catch-up:` log line; a second node taken offline for 26 h returns in IBD and shows `suppressedBlocks == 0` | `yed_getinfo` before/after; `debug.log` |
      | D16 Abandonment and sweep (L10, L12, L13) | on a dedicated testnet window (announced): every pool sets `yellowbacksignal=0` for `ABANDON_BLOCKS` + 1 window; a team vault is swept | `abandoned == true` on every node incl. the stock-pool operator's observer; the sweep is in every mempool and mined by a module-running pool; vault `CLOSED, unbacked`; pools re-enable signalling and enforcement resumes at 60 % / minting at 75 % | `yed_getinfo` series; the sweep txid |
      | D13 Sunset (L8) | a release built with testnet `ENFORCE_UNTIL_HEIGHT` 2 days ahead runs on one pool | past it: `yed_getinfo.sunset == true`, `enforcing == false`, its tags carry no signal bit, it accepts a stock rule-breaking block while the others reject it and its `rejectedBlocks` stays; the successor release (set starting at that height) restores enforcement | `yed_getinfo` before/after; `yed_gettag` |
      | D14 Quote majority (L9) | one pool publishes `P × 2` for 2 days while the mid/slow windows sit near 50 % fill, then near 70 % | at 50 % fill `pClaim` stays undefined (mint halt, no claims); at 70 % fill and 34 % of blocks `pClaim` moves and `yed_listclaimable` shows the consequence; at < 34 % of blocks it does not | hourly `yed_getprice` CSV |
- [ ] Calibrate `SIGMA_REF_BPS`: over the soak the multiplier must sit in `[1×, 1.5×]` at YEC's
      realised volatility (measured from exchange data over the same period), else `SIGMA_REF_BPS`
      is re-set and the soak extended a week (acceptance rule, M14); revisit `SUPPLY_CAP_BPS` and
      the class ratios (§12); confirm the provisional launch bar `N ≥ 3`, `X ≤ 40 %` (L4) against the
      mainnet distribution measured with `yed_listminers <height> 2016`.
- [ ] Fix-forward; tag `yellowback-v2`.

### Phase 10 — Mainnet

- [ ] Pool outreach with the runbook — **to every Ycash pool, participating or not** (N3): a pool
      that does not want to enforce runs the module in filter-only mode (`-yellowbackenforce=0`,
      TPL-1), the zero-risk option that keeps its blocks from being orphaned by rule-breaking
      transactions it cannot otherwise see; `startHeight` (mainnet, at least two weeks of blocks
      past the release date, M14) and `ENFORCE_UNTIL_HEIGHT` (L8) in a release whose
      `-yellowbacksignal` defaults to **0** on mainnet (L4): pools that install it publish quote
      tags but do not signal.
- [ ] **Launch bar (L2, L4):** once `startHeight` has passed, measure the distribution of
      quote-tagged blocks by `payoutKey` over a full 2,016-block window (`yed_listminers <height>
      2016`); the signalling announcement is made only when at least `N` independent pools
      (distinct operators, attested by each pool's public identity — not distinct keys, since a
      pool can quote from many) run the module and no single pool exceeds `X %` of quote-tagged
      blocks, with the measured distribution published alongside. Provisional `N ≥ 3`, `X ≤ 40 %`
      (L4), confirmed in Phase 9. After the announcement pools set `yellowbacksignal=1`; lock-in and
      activation are then automatic (ACT-2/3). Wallets cannot mint before activation.
- [ ] **Incident playbook (P14)**, published in `doc/yellowback-mining.md` before the signalling
      announcement, with the pool contact list and a named on-call owner:
      1. *An enforcing node rejects a block the network accepts* (a rule bug, a stale release, a
         real minority): the valve rejoins the chain within six blocks on its own (L7); the
         on-call owner asks every pool to set `yellowbackenforce=0` and restart until the cause
         is known, publishes `yed_getblockverdict` output for the block, and ships a fix release
         (or a parameter set with a new start height, §3.1) within 7 days; signalling stays off
         until the fix has run on testnet through D2 and D12 again.
      2. *A rule-breaking spend is accepted by the enforcing set* (an under-rejection bug):
         nothing forks; the affected vault is `unbacked`; the wallet shows it; the fix release
         follows the same 7-day path and the trust statement's "unbacked" wording already covers
         the outcome.
      3. *Price manipulation* (a pool or a quote-tag majority moves a median, L9): the L9
         arithmetic bounds it; pools compare `yed_listminers`; the on-call owner asks pools to
         set `-yellowbackpreferredpayee` away from the offender and, if `pClaim` moved, to halt
         signalling so minting pauses (60 %) while the windows roll; no code change.
      For every incident: a post-mortem in `doc/yellowback-incidents.md` within 14 days, with the
      regtest case that reproduces it added to the suite before the fix release is tagged.
- [ ] 90-day review: participation, fee income per pool, price-feed quality, any rejected block,
      every `suppressedBlocks` increment reported by a pool (each one is a rule-breaking block
      the network accepted, L11). Decide on burying `activateHeight` (§9) and on the
      network-upgrade proposal.

---

## 7. Test plan

| Layer | Location | Covers |
|---|---|---|
| Unit | `yellowback_math_tests.cpp` | §3.7 formulas, medians, isqrt, σ (incl. the V17 regression), fee, payee weighting, issuance, overflow |
| Unit | `yellowback_tag_tests.cpp` | TAG-1..5, byte budget, corpus replay |
| Unit | `yellowback_payload_tests.cpp` | §3.3 codec v2, malformed cases |
| Unit | `yellowback_script_tests.cpp` | §3.4 both paths under `VerifyScript`, standardness of every template (`IsStandardTx`/`AreInputsStandard` called directly; regtest never runs them) |
| Unit | `yellowback_state_tests.cpp` | every rule of §3.8–3.9 on synthetic blocks; apply/undo identity; overlay equivalence |
| Unit | `yellowback_index_tests.cpp` | fault injection at each hook; tip-mismatch guards |
| Unit | `yellowback_address_tests.cpp` | §3.1 address version bytes, `ye…`/`yt…`/`yr…` rendering, P2PKH round trip (unchanged) |
| Unit | `yellowback_index_tests.cpp` (cont.) | `mempoolcheck_bench` (N6), `valve_trips_at_six_blocks` (ACT-7), `valve_trips_through_failed_child`, `valve_note_map_bounded`, `valve_ignores_lowdiff_headers` (P2), `check_ibd_suppresses_reject` (N2), `catchup_suppresses_reject` (L11), `statehash_golden_vector` (N18) |
| Functional | `yellowback_rpc_contract.py` | every `yed_*` command against `doc/yellowback-rpc-contract.json`: documented keys and types present, every error identifier provoked (P7) |
| Functional | `yellowback_index.py` | tags → state, reorg (incl. `price1_reorg_across_fill_boundary`, `reg4_judgement_undone_on_reorg`, `blk3_unhealthy_across_reorg`), restart, reindex, crash recovery with an unflushed chainstate, `rejected_survives_kill9`, `ibd_across_accepted_invalid`, `index_start_height_above_tip`, `snap_history_contiguous`, `params_mismatch_fails_loudly`, the kill-switch edge cases, prune refusal |
| Functional | `yellowback_activation.py` | ACT-1..6, HALT-4, MINER-1's signal-iff-enforce, `act2_reorg_across_lockin`, `act3_reorg_across_activateheight`, `act_forged_signal_tags`, `act5_past_sunset_accepts` (L8), `tag3_signal_only_registers_nobody`, the no-partition assertion, `assert_model_matches` |
| Functional | `yellowback_mining.py` | tag emission, GBT fields (and `gbt_shape_without_flag`), pool path via `submitblock`, `tag2_invalid_tag_is_no_tag`, `tx0_coinbase_payload_registers_nothing`, `miner2_*`, template policy, `tpl1_template_includes_chained_mint_transfer`, MP-1 incl. `mp1_expiry_required` and `mp1_reorg_reevaluates_mempool` |
| Functional | `yellowback_enforcement.py` | BLK-1..3 end to end against a stock miner; DoS 0 incl. descendants (N1); kill switch; fail open per hook; the work valve (ACT-7, case 9, with the P1 warning text); catch-up suppression and its two variants (case 15, L11); `tag4_garbage_coinbase_never_invalid`; `fee2_reorg_changes_eligible_set`; `red1_refheight_window_after_reorg`; `m3_vault_spend_with_mint_payload`; `--extended` (with `assert_model_matches(full=True)`, P8); `--stock-binary` nightly (P9) |
| Functional | `yellowback_stock_node.py` | node 1 unaffected: no `yed_*`, v4.5.0 GBT shape, mines and relays throughout (N35); nightly with node 1 on the `ycash-legacy` binary (P9) |
| Functional (nightly) | `yellowback_stockparity.py` | `ref/ycash` v4.5.0 vs the fork without `-yellowback` over one scripted scenario: equal block hashes, `gettxoutsetinfo.hash_serialized`, `getinfo`, `getblocktemplate` key sets (N10, §8.4 item 21) |
| Functional (nightly) | `yellowback_runbook.py` | the `MAX_REORG_LENGTH` runbook: shutdown, `-reindex`, no re-rejection (N35) |
| Functional (release) | `yellowback_rc1.py` | the rc1 run-through of Phase 8 with its state-hash ledger, valve and sweep steps (N31) |
| Functional | `yellowback_lifecycle.py` | mint/send/burn/redeem, fees, FEE-0, `expired_transaction_display`, `sweep_refused_while_enforcing` |
| Functional | `yellowback_claim.py` | RED-4 incl. `red4_underwater_at_r_not_at_h`, CLTV on the claim path, CLAIMED accounting, the sweep cases `sweep_refused_when_merely_suspended`, `sweep_builds_under_abandonment`, `sweep_relayed_by_own_node`, `sunset_alone_is_not_abandonment`, `sweep_after_sunset_without_successor` (L10, L12, L13); `assert_model_matches(full=True)` |
| Functional | `yellowback_void_mint.py` | VOID-vault / burned-transfer outcomes incl. halts and pre-activation, one `mintN_` case per rule, `mint6_cap_race_after_reorg` |
| Functional | `yellowback_pricefeed.py` | PRICE-1..2 with the per-window fill and `price1_quote_majority_needs_fill` (L9), HALT-1..3 incl. `halt2_fires_at_exact_threshold` and `halt3_fires_on_mid_vs_slow`, SIGMA-1 incl. `sigma1_one_pool_cannot_inflate`, REG-1..4 (REG-2/3 as wallet defaults, L1), `assert_model_matches` |
| Functional | `yellowback_wallet_restore.py`, `yellowback_sapling.py` | restore = keys + index (§4.6); `ys1…`-funded mint and `ys1…` collateral destination; minus co-signing |
| Functional | `yellowback_quote.py` | the agent against mock prices |
| Functional | `yellowback_reorg_stress.py` | randomized reorgs with enforcement |
| Fuzz | `src/fuzzing/YellowbackTag`, `YellowbackPayload`, `YellowbackScript`, `YellowbackEvaluate`, `YellowbackPayee` (corpora in `<Target>/input`, found crashes in `<Target>/crashes`, generator `src/test/gen_yellowback_corpus.py`) | parser robustness; evaluator totality and the four properties (K1, N34); FEE-W never picks outside `E(R)` |
| Model | `qa/rpc-tests/test_framework/yellowback_model.py` | a second implementation of §3.7 **and §3.8** in Python: snapshots compared field by field with `yed_gethistory` (N23), transactions and vaults with `yed_gettxinfo`/`yed_listvaults` (P8, `full=True`) |
| Build variants (nightly) | `lockorder`, `sanitizers`, `coverage` jobs | `DEBUG_LOCKORDER` deadlock detection over the functional suite; address/undefined/thread sanitizers over the unit suites and three functional scripts; lcov floors per file (P6) |
| Application | `yecwallet-dd` QTest | (a) offline cases with a fake `Connection` for every §4.8 screen, run in CI; (b) the devnet end-to-end case, run by hand and skipped without `YELLOWBACK_DEVNET_DIR` (N28) |
| Application (macOS) | `wallet` CI job | the state-hash golden vector on a macOS runner (`arith_uint256`/serialisation across compilers, N23) |

Every functional test uses the §6.0 topology, `sync_all()` for index synchrony (the index is now
synchronous with `chainActive`, so `fullyNotified` is no longer the thing waited on, only block
propagation), and asserts `yed_getstatehash` equal on the enforcing nodes at the end;
`yellowback_enforcement.py` and `yellowback_claim.py` also call `checkpoint(label)` after every
mined block (N35).

**Rule → test (M10, N36).** Every identifier in §3.2, §3.7–3.9 (TAG-1..5, PRICE-1..2, SIGMA-1,
FEE-0..2, FEE-W, REG-1..4, IN-1..3, TX-0, MINT-1..8, XFER-1..3, RED-1..4, ACT-1..7, HALT-1..4,
BLK-1..3, TPL-1..3, MP-1, MINER-1..3, MINTPOL-1, SNAP, UNDO) appears verbatim in a **comment tag**
— a `// Rule: RED-1 RED-2` line immediately above the `BOOST_AUTO_TEST_CASE` (a case name cannot
contain `-`), or a `# Rule: …` line in the docstring of a functional-test case — and CI greps
`^(//|#) Rule: .*\b<id>\b` over `src/test/yellowback_*.cpp` and `qa/rpc-tests/yellowback_*.py`
for every identifier (§8.4 item 9; the loop is in Phase 6's acceptance block);
`doc/yellowback-review.md` keeps the table. Cases added by revision 4: REG-1 lapse, TX-0, MINT-7,
the `feeVout` edges of MINT-8/RED-3, RED-1's second-vault and `vin[1]` cases, SIGMA-1's
undefined-sample cap, MINTPOL-1 per halt, HALT-1 and HALT-4 by name, ACT-6 and the split floors,
MINER-1's signal-iff-enforce, MINER-2's default payout key, TPL-3 (a unit test that makes
`FilterTemplate` disagree with `EvaluateBlock` through the fault flag and asserts
`TestBlockValidity` throws). **Cases added by revision 5 (N30), by name:**
`tag2_invalid_tag_is_no_tag`, `tag3_signal_only_registers_nobody`,
`tag4_garbage_coinbase_never_invalid`, `price1_reorg_across_fill_boundary`,
`price1_mid_slow_need_two_thirds`, `price1_quote_majority_needs_fill`,
`sigma1_one_pool_cannot_inflate`, `sigma1_first_sample_at_start_height`,
`fee1_min_dominates_small_vault`, `fee1_at_max_money`, `fee2_reorg_changes_eligible_set`,
`feew_override_flags_change_pick`, `reg4_judgement_undone_on_reorg`, `in1_spent_token_removed`,
`in2_void_vault_spend_closes`, `in3_burn_recorded_on_closed_vault`,
`in3_mint_with_yed_inputs_burns_them`, `tx0_coinbase_payload_registers_nothing`,
`mint1_`…`mint8_` (unit and functional), `mint2_regtest_height_underflow`,
`mint6_cap_race_after_reorg`, `xfer1_`/`xfer2_`/`xfer3_`, `red1_refheight_window_after_reorg`,
`red4_underwater_at_r_not_at_h`, `red4_undefined_pclaim`, `act2_reorg_across_lockin`,
`act3_reorg_across_activateheight`, `act_forged_signal_tags`, `act5_past_sunset_accepts`,
`act5_sunset_stops_rejection`, `valve_trips_at_six_blocks`, `check_tripped_valve_never_rejects`,
enforcement case 9 (ACT-7), `halt2_fires_at_exact_threshold`, `halt3_fires_on_mid_vs_slow`,
`blk2_dos_level_zero`, `check_ibd_suppresses_reject`, `blk3_unhealthy_across_reorg`,
`tpl1_overlay_order_in_block_chaining`, `tpl1_template_includes_chained_mint_transfer`,
`tpl2_declines_nonwallet_selector`, `mp1_expiry_required`, `mp1_reorg_reevaluates_mempool`,
`miner2_default_from_mineraddress`, `miner2_non_p2pkh_refused`, `gbt_shape_without_flag`,
`snap_written_for_every_height_ge_start`, `snap_history_contiguous`,
`totality_every_lookup_misses`, `m3_vault_spend_with_mint_payload`,
`virtual_snapshot_below_start_height`, `snapshot_undefined_price_is_zero`,
`params_selected_by_height`, `params_mismatch_fails_loudly`, `statehash_golden_vector`,
`mempoolcheck_bench`, `crash_unflushed_chainstate`, `rejected_survives_kill9`,
`ibd_across_accepted_invalid`, `index_start_height_above_tip`, `killswitch_fresh_datadir`,
`killswitch_rejected_hash_not_in_mapblockindex`, `verdict_parent_not_tip`,
`expired_transaction_display`, `sweep_refused_while_enforcing`,
`sweep_refused_when_merely_suspended`, `sweep_builds_under_abandonment`,
`sweep_after_sunset_without_successor`, and the scripts `yellowback_stock_node.py`,
`yellowback_stockparity.py`, `yellowback_runbook.py`, `yellowback_rc1.py`. **Cases added by
revision 6 (L11–L14, P1–P9), by name:** `catchup_suppresses_reject`,
`valve_trips_through_failed_child`, `valve_note_map_bounded`, `valve_ignores_lowdiff_headers`,
`valve_catchup_offline_node` (three variants), `sweep_relayed_by_own_node`,
`sunset_alone_is_not_abandonment`, `void_release_via_yed_redeem`,
`tag1_magic_without_push_opcode_is_no_tag`, the scripts `yellowback_rpc_contract.py`, the
`--stock-binary` runs, the accounting half of `yellowback_model.py`, and the `lockorder`,
`sanitizers` and `coverage` jobs.

**Fuzzing (N34).** Ycash's harness builds one target at a time: `configure --enable-fuzz-main`
replaces `main()` (`ref/ycash/configure.ac:142-146`), the target's `fuzz.cpp` is linked as
`src/fuzz.cpp` (which `zcutil/clean.sh:27` removes), the prototype's `fuzz.cpp` files carry both
an AFL `main` and a libFuzzer entry; commands in §6.0 item 0. Targets: `YellowbackTag` (seeded
with the Phase 1 table cases and ten real mainnet coinbase scriptSigs), `YellowbackPayload`,
`YellowbackScript`, `YellowbackEvaluate` (the Phase 2 grammar: `k ≤ 64` tags, `m, n ≤ 16`,
regtest params fixed, `H ∈ [START_HEIGHT − 2, START_HEIGHT + VOL_WINDOW + 8]`, hashes derived
from the input; asserting apply→undo identity, overlay equivalence, `blockInvalid ⇒`
enforcement computed at `H`, and `supplyCents == Σ Tokens`), `YellowbackPayee` (FEE-W over
random `Tags`/`Judgements`: the pick is in `E(R)`; the all-penalised fallback is never empty
when `E(R)` is). Corpora live in `src/fuzzing/<Target>/input`, generated by
`src/test/gen_yellowback_corpus.py`, which also emits the C++ table embedded in
`src/test/yellowback_fuzz_tests.cpp` (`--check` in CI keeps the two equal); the Boost replay
cases also replay `src/fuzzing/<Target>/crashes/` so a fixed crash stays fixed. CI: the
`nightly` job builds every target with `--enable-fuzz-main` and runs each for 10 minutes from
its corpus (so `fuzz.cpp` can no longer rot uncompiled), uploading new crashes; the
`weekly-fuzz` job runs 2 hours per target with corpus minimisation and opens a PR with the new
corpus files. Phase 1's exit requires 10 minutes each of `YellowbackTag`/`YellowbackPayload`
with no crash; Phase 2's exit 8 CPU-hours of `YellowbackEvaluate`, recorded in
`doc/yellowback-review.md`.

**Cross-implementation check (N23).** `qa/rpc-tests/test_framework/yellowback_model.py` is a
pure-Python model of the §3.7 snapshot arithmetic — `lowerMedian` with the per-window fill,
`signalCount`, ACT-1..6 with the hysteresis, SIGMA-1 with `isqrt`, HALT-1..4, `issuedZat` from
the regtest subsidy schedule — fed from `yed_gettag` over `[START_HEIGHT, tip]`;
`assert_model_matches(node)` compares every field of `yed_gethistory` for every height and
recomputes `yed_getstatehash` from the §3.6 preimage. It runs at the end of
`yellowback_activation.py`, `yellowback_pricefeed.py` and `yellowback_rc1.py`, and its
`statehash_golden_vector` companion runs on a macOS runner in the `wallet` job, so an
`arith_uint256` or serialisation difference across compilers surfaces. Vault and token
accounting may be modelled the same way from `yed_gettxinfo` if time allows; the snapshot half
is where the arithmetic conventions (M1) live; revision 6 makes the accounting half required
too (P8): `model_transaction()` reproduces IN-1..3, TX-0, MINT-1..8, XFER-1..3 and RED-1..4 from
`getblock <hash> 2` and the snapshot model, and `assert_model_matches(node, full=True)` compares
`yed_gettxinfo` for every Yellowback-relevant transaction, `yed_listvaults` and `yed_getstats`
totals, and the state hash — a second implementation of the money rules, not only the prices.

---

## 8. Trust statement, threat model, review checklist

### 8.1 Trust statement (to be published verbatim with v2)

Yellowback v2 is a miner-enforced, over-collateralised stablecoin overlay on Ycash.

- Consensus-enforced (by every Ycash node, upgraded or not): collateral cannot leave a vault
  before its lock height; before the claim height only the minter's key can spend it.
- Enforced by every Yellowback-aware node deterministically: Yellowback accounting (conservation,
  supply, collateral totals, vault status, prices, activation, halts).
- Enforced by the mining pools that run the Yellowback module, and effective for the whole
  network once a supermajority of blocks signal: collateral is released only against the burn of
  the vault's debt; an underwater, abandoned vault can be claimed only by burning that debt; both
  pay a fee to a pool that published a price quote in the 100 blocks up to the transaction's
  reference height.
- Prices are the medians of the quotes pools publish in their own blocks; moving them needs a
  majority of *quote-tagged* blocks over a window, which is a majority of hashpower only when
  most blocks carry quotes — so the windows that decide claims are undefined until two-thirds of
  their blocks carry quotes, and the mint window until half do. A pool whose quotes stray from
  its peers' loses the fee income that wallets' default payee choice would otherwise send it.
- **Therefore:** a majority of hashpower that runs the module and follows it makes the rules
  hold; a majority that does not — or a minority that the trailing signal count mistakes for a
  majority, since the count is self-reported — could release collateral without burns or, with
  enough quote-tagged blocks, move the price; the same majority could already reorganise the
  chain. No operator, committee or key other than the minter's can move collateral before the
  claim height; after it, only a burn of the vault's debt can. No pool can move a user's YED or
  take collateral before the grace period; a pool can create YED only by first moving the mint
  price with a majority of quote-tagged blocks.
- An enforcing node that finds itself on the minority side of a split — a rejected chain that
  outruns its own by six blocks — stops enforcing for the session, rejoins the network's chain,
  raises an alert and waits for its operator; it is never stranded for more than six blocks, and
  it never bans the peers that relayed the other chain, neither for the rejected block nor for
  its descendants. A node that catches up after an outage never rejects a block the network has
  already built six blocks on; it accepts it, records that it did, and keeps enforcing.
  Enforcement means "majority in fact", not "majority by count".
- Every release enforces only until a sunset height about a year past its start; past it the
  node keeps publishing quotes and accounting but rejects nothing until upgraded, so two
  releases with different rules can never both be enforcing.
- As with any soft fork, every pool — participating or not — should run the module at least in
  filter-only mode, or its blocks can be orphaned by rule-breaking transactions it cannot see.
- Signalling is announced only once the pools running the module are diverse enough that no one
  of them decides alone (at least three independent pools, none above 40 % of quoting blocks,
  measured and published before the announcement).
- If pools stop participating: below 60 % of blocks signalling, minting pauses; below 50 %, block
  rejection pauses as well, and while it is paused neither the owner path nor the claim path is
  policed — collateral can leave a vault without its burn and YED so unbacked stays in
  circulation; vaults untouched during the pause are protected again when it ends. Minting resumes
  at 75 % and rejection at 60 %. Existing YED always remains redeemable by a minter who holds it.
- If the module is abandoned — rejection paused for two full windows, which is also where a
  sunset with no successor release ends up — every vault's claim path becomes spendable by
  anyone at its claim height: owners must sweep their collateral before that height
  (`yed_sweep`, which every node of every release offers under that one same condition, and
  whose transaction every node then relays and mines like any other) or lose it to whoever
  claims first; the claim path stays open to everyone, so the race is fair, but the YED minted
  against a swept or claimed vault is unbacked from then on. A failed mint's collateral (a VOID
  vault, which never carried a debt) is released by its owner with `yed_redeem` at its lock
  height at any time, abandonment or not.

### 8.2 Threat model

| Threat | Outcome in v2 | Mitigation |
|---|---|---|
| Minter spends the vault after the lock without burning | block rejected by enforcing majority; orphaned | BLK-1/RED-2; template filter; MP-1 |
| **Reusable ACTIVE-vault griefing of stock miners** (N3) | cost = the minimum collateral locked once; an owner-path spend without a burn is relayed by every stock node and included again after every orphaning; a stock pool's blocks are orphaned until it runs the module in filter-only mode (`-yellowbackenforce=0`, TPL-1) | accepted and documented: §8.1's "every pool should run at least filter-only"; Phase 10 outreach to every pool; `--extended` asserts node 1's surviving block count and a ban count of 0 |
| **Stock peers relaying descendants of a rejected block** (N1) | none: `bad-prevblk-yellowback` at DoS 0 replaces the stock `bad-prevblk` (DoS 100 / DoS 10) for headers on a Yellowback-rejected chain | BLK-2 descendant clause; Phase 5 case 1 (`banscore == 0`, node 1 still a peer) |
| **A new enforcing node syncs across a historically accepted invalid block** (N2) | none: no rejection during IBD, `-reindex` or import; the index is rebuilt identically | BLK-2 initial-sync clause; `ibd_across_accepted_invalid`; drill D7 |
| **Permanent split after the signal share drifts below half** (L7) | bounded: once the rejected chain is six blocks of work ahead the valve clears enforcement for the session, reconsiders the rejected blocks and the node reorganises at the next announced block; enforcement is majority in fact | ACT-7; Phase 5 case 9; drill D12; the valve's own alert (P1 — the stock fork warning does not fire for refused descendants) |
| **A node catching up rejects a block the network accepted hours ago** (L11): Ycash's IBD test is tip age only (24 h), so a node behind by less than a day evaluates on catch-up; descendants indexed before the rejection do not tick the odometer | none for the common case: a block the best known header already carries six blocks of work above is accepted without rejection, counted in `suppressedBlocks`, enforcement untouched; within six blocks the rejection stands and the odometer reads the real work of a `FAILED_CHILD` parent at the next header | BLK-2 clause 3; `catchup_suppresses_reject`; `valve_catchup_offline_node`; drill D15 |
| **Note-map bloat through cheap low-difficulty headers on a rejected root** (P2): the N1 clause runs before `nBits` is checked against the schedule | none: a header is noted only within the consensus per-block loosening of its parent's target and only up to `VALVE_NOTE_CAP` per root; it is still answered DoS 0; the work sum is real proof either way | `valve_note_map_bounded`; `valve_ignores_lowdiff_headers`; Phase 8 DoS row |
| **Release-relative abandonment** (L12): a stale release declares abandonment at its own sunset while upgraded pools still enforce | impossible: abandonment reads only the `ENFORCEMENT` bit, which every release derives from the same signal bits | §4.6; `sunset_alone_is_not_abandonment`; `sweep_after_sunset_without_successor`; drill D16 |
| **A sweep that no node will relay** (L13): the owner's own node applies MP-1 | none: MP-1 and TPL-1/2 stand down while abandonment holds, so the sweep is admitted, relayed and mined by module-running pools; `yed_sweep` returns the hex besides | `sweep_relayed_by_own_node`; rc1 step 8b |
| **False signalling** (N4): 30 % honest enforcers + 25 % forged signal bits reach the 50 % floor while 45 % mines the stock chain | the count is self-reported and can be inflated by anyone; it under-counts only among honest pools; a forged majority strands enforcers for at most six blocks | the work valve (ACT-7) is the mechanical backstop; the launch bar (governance); `act_forged_signal_tags` |
| **Quote-tag majority** (L9): at 50 % fill a pool with 26 % of blocks holds > 50 % of the quote tags and sets the medians when the windows roll | raising `pMint` 2× for 42 h lets its own mints run at half collateral; lowering `pClaim` makes healthy vaults claimable by the attacker with YED it minted | mid and slow windows undefined below `⌈2W/3⌉` fill, so `pClaim` needs 34 % of blocks at two-thirds fill and more as fill rises; the 3× σ cap; the min/max selectors; `price1_quote_majority_needs_fill`; drill D14 |
| **Two enforcing releases with different parameter sets** (L8) | impossible at one height: every set carries `ENFORCE_UNTIL_HEIGHT`, the next set starts at or after it, and a node past its sunset rejects nothing | §3.1 versioning; ACT-5; `act5_past_sunset_accepts`; drill D13 |
| **A Ycash network upgrade the fork lags** (N17) | a pool on the stale fork drops off the network; a pool that moves to stock loses enforcement; the enforcing set could collapse on one flag day | §11: a fork release within 14 days of every Ycash release; the sunset never beyond the next known upgrade height; ACT-7 bounds any split meanwhile |
| **Honest stock-mined block invalidated by a natural reorg that changes `Snapshots[refHeight]`** (N14) | a wallet-built spend valid at build time can fail RED-3 (its payee's only tags were in the replaced blocks) or RED-4 after a reorg deeper than `REF_LAG`; a stock miner that includes it from its mempool has an honest block orphaned; enforcing pools re-run TPL-1 and are safe | low probability, accepted; the MP-1 expiry bound (N5) and the `ConnectTip` sweep shorten the window; `yellowback_reorg_stress.py` records the rate |
| **A vault spend lingers in enforcing mempools after a tip change makes it invalid** (N5) | it would be relayed to stock miners (feeding the griefing row) | MP-1 requires `nExpiryHeight ≤ refHeight + REF_WINDOW`; `ConnectTip` drops failures; `mp1_*` cases |
| **`MempoolCheck` CPU per ordinary transaction** (N6) | none measurable: `O(inputs)` lookups, no SNAP, when no ACTIVE vault is spent | `mempoolcheck_bench` |
| **Index growth from payload spam** (N7) | bounded: `TxLog` records only transactions that create or spend `Tokens`/`Vaults`; `Snapshots` ≈ 50 MB/yr | Phase 8 DoS review |
| **Abandonment** (L10) | every unswept vault's claim path is anyone-can-spend at `claimHeight`; owners who do not sweep lose collateral to whoever claims; YED becomes unbacked | `yed_sweep` under the shared abandonment predicate (§4.6, one clause, L12); `sweepBefore` on every ACTIVE vault; §8.1 |
| **VOID vault whose owner cannot recover the collateral** (L14) | a failed mint's collateral would sit until `claimHeight` and then go to whoever claims | `yed_redeem` builds the release for a VOID vault at `lockHeight`; `sweepBefore` and the GUI's Release action; `void_release_via_yed_redeem` |
| Claim path swept without burn or on a healthy vault | rejected | RED-2/RED-4; minting gated on activation and participation |
| A single pool publishes false quotes | shifts a median by at most its share's percentile; wallets' default payee choice skips it for `N_PENALTY` and down-weights it afterwards (policy, not a rule, L1) | medians, min/max selectors, REG-2/3 as wallet defaults |
| **Non-signalling hashpower suspends enforcement** (an attacker plus every stock pool) | needs > 50 % of blocks in a window without the signal bit (L3), i.e. the same majority that could reorganise the chain; while suspended both vault paths are unpoliced (§8.1) | `ENFORCEMENT_FLOOR` at half with resume at 60 % (ACT-6); the signal bit is set only by enforcing nodes (MINER-1) but is self-reported and can be inflated by anyone (N4); minting stops earlier (60 %) so no new vault is created into a weakening set |
| Majority hashpower colludes | can move prices or release collateral | the chain's existing assumption; nothing new (§8.1) |
| **Hashpower concentration on Ycash** (a single pool above the threshold) | "miner-enforced" degrades to "that pool-enforced" | the launch bar (L2, Phase 10): at least `N` independent pools and no pool above `X %` of signalling blocks, published with the announcement; the 75 % threshold is not a substitute for pool diversity |
| A bug in the hook rejects a valid block | enforcing miners *and every enforcing node* fork off — for at most six blocks of work, after which the valve clears enforcement and they rejoin (ACT-7) | hook limited to ACTIVE-vault spends (V3); `-yellowbackenforce=0` + `ReconsiderBlock`; the work valve; extended enforcement test; testnet drills |
| A crafted transaction makes evaluation throw on every enforcing node (a fail-open kill switch) | none: evaluation is total; only storage failures fail open | K1: totality by construction, `YellowbackEvaluate` fuzz target, `refHeight ≥ START_HEIGHT` |
| Signalling falls below the floors after activation | minting halts below 60 %; block rejection suspends below 50 % (ACT-4/ACT-6); no node forks off | K2, L3; runbook |
| Cheap VOID vaults used to orphan stock blocks on demand | none: VOID vaults are not policed | K3 |
| A pool publishes tags under another pool's `payoutKey` | the victim is skipped or down-weighted by wallets' default payee choice for `N_PENALTY` / one window (policy only, L1); the lie still counts once in the medians | K9: §12 Q14 (signed tags); the attacker gives up its own slot and fee eligibility for that block |
| An enforcing pool's index goes unhealthy and it keeps mining unpoliced templates | its blocks may include what others reject | `-yellowbackrequirehealthy`; alerting on `healthy` (K24) |
| A bug in the template filter includes an invalid spend | `TestBlockValidity` throws; the pool gets no template until fixed | TPL-3; alerting on GBT errors |
| Feed outage at one pool | signal-only tags; no fee income; no effect on activation | V9 |
| Feed outage at many pools | windows under half fill ⇒ no `P_mint` ⇒ minting halts; burns unaffected | V16, HALT-1 |
| Fast genuine crash | `P_fast` marks `P_mint` within 2 h; divergence halt pauses minting; claims wait for the slow windows plus grace | proposal §8.2 |
| Mint races the supply cap or a reorg changes its snapshot | VOID, collateral locked for the term with no fee | carried over from the prototype (the reference-height design bounds it to a reorg deeper than `REF_LAG` or a cap race); strict template policy; wallet warnings |
| Enforcing node crashes with the index ahead of the chainstate | undo-walk at start; rebuild beyond `UNDO_KEEP` | V2 |
| Operator disables enforcement while > 99 blocks behind the network | the node shuts itself down (`MAX_REORG_LENGTH = 99` counts the active chain to disconnect, whoever mined it; `main.cpp:3770-3789`, N15) — unreachable in ordinary operation because the valve rejoins at six blocks | runbook: `-reindex` (BLK-2 never rejects while reindexing, N2); `yellowback_runbook.py` |
| `reject` P2P messages to stock peers after a rejection | noise only | none needed (§12 Q11) |
| Pool coinbase text pushes the scriptSig past 100 bytes | the pool's own `TestBlockValidity`/`submitblock` fails | pool kit budget rule |
| Payee selection gamed by a miner mining many blocks | proportional to hashpower by design | — |
| A pool redeems or claims its own vault and names the collateral output as the fee output | pays no net enforcement fee on its own vaults (RED-3 allows it, K23) | accepted; no soundness effect (M13) |
| A claimant picks the `refHeight` (of the last 40) with the lowest `pClaim` | at most the drift of `max(pMid, pSlow)` over 40 blocks | accepted (M13) |
| A mint's snapshot was clear but enforcement is suspended by the time it confirms | ≤ 40-block window (MINT-4 at `R`, ACT-5 at `H − 1`) | accepted (M13) |
| A parameter set changes at a height already validated by released nodes | stored rejections and rebuilt indexes would disagree | §3.1: a new set starts above every validated height (M12) |
| Wallet spends YED as YEC; keys imported elsewhere; `lockunspent` | §4.6 coin locking; H5–H9 | H1–H12 (Phase 8) |
| Payload/tag parser bugs | never affect consensus of stock nodes; on enforcing nodes bounded by fail-open | fuzzing; BLK-3 |
| DoS via `yed_setquote` | none: RPC auth; last-write-wins | — |

### 8.3 What Yellowback cannot affect

For a node without `-yellowback`: nothing; every code path is v4.5.0's. For a node with it and
`-yellowbackenforce=0`: block validity is v4.5.0's; only templates and relay policy differ. For an
enforcing node: block validity differs only for blocks that spend a Yellowback vault after
activation, and only until the release's sunset height. Mempool acceptance differs only for
spends of ACTIVE vaults (MP-1, incl. the expiry bound and the `ConnectTip` sweep); shielded-pool
value balance, fee policy and P2P behaviour are v4.5.0's — except that a header descending from a
block this node rejected is answered `bad-prevblk-yellowback` at DoS 0 instead of `bad-prevblk` at
DoS 100 (N1), and `getblocktemplate` carries the tag and a `yellowback` object (N16, N10).

### 8.4 Review checklist (Phase 8)

1. `git diff --stat ycash-legacy...feature/yellowback-sf` matches §4.1; zero lines in the
   consensus set (`src/wallet/rpcwallet.cpp` and `rpc/rawtransaction.cpp` are wallet tier, M7);
   `main.cpp` ≤ 40, `miner.cpp` ≤ 35, `rpc/mining.cpp` ≤ 35; `init.cpp` has no budget.
2. Every inserted *statement that can change behaviour* in `main.cpp`/`miner.cpp`/`rpc/mining.cpp`
   is inside `if (g_yellowback)` or assigns `COINBASE_FLAGS`; the unguarded insertions are exactly
   the three include lines (`yellowback/index.h` in `main.cpp` and in `rpc/mining.cpp`,
   `yellowback/policy.h` in `miner.cpp` — corrected 2026-09-11 against the tree; the earlier
   text said two, both `index.h`), the K17 `LOCK(cs_main)` and the
   `+ COINBASE_FLAGS` append at `miner.cpp:327` (empty without the flag) — mechanical:
   `git diff ycash-legacy...HEAD -- src/main.cpp src/miner.cpp src/rpc/mining.cpp | grep '^+' | grep -v 'g_yellowback\|#include\|LOCK(cs_main)\|COINBASE_FLAGS\|^+$\|^+++'`
   printed in the review document with every residual line justified (M11, N10); with
   `-yellowback` off `g_yellowback == nullptr` and `COINBASE_FLAGS` is empty (unit test
   `coinbase_flags_empty_without_flag`); the `getblocktemplate` shape without the flag is
   v4.5.0's (`gbt_shape_without_flag`, item 21).
3. The `ConnectBlock` check returns a reason only if `-yellowbackenforce`, the index is healthy,
   the tip equals `pprev`, the node is not in IBD/reindex/import, the network has not already
   built `VALVE_BLOCKS` on the block (L11), the valve has not tripped, and ACT-5 (incl. the
   sunset) holds at `H` — `yellowback_index_tests.cpp` cases `check_no_enforce`,
   `check_unhealthy`, `check_tip_mismatch`, `check_suspended`, `check_ibd_suppresses_reject`,
   `catchup_suppresses_reject`, `check_tripped_valve_never_rejects`,
   `act5_sunset_stops_rejection`; it never dereferences `pindex->phashBlock` (K5,
   `check_null_hash`); a re-verified block is a no-op (K6, `check_reverify`).
4. `DoS(0)` only: `! git grep -n 'DoS([1-9]' -- src/yellowback src/rpc/yellowback*` and every
   `DoS(` in the `main.cpp` diff is `DoS(0` (Phase 3 acceptance) — this covers the
   `bad-prevblk-yellowback` clause; `yellowback_enforcement.py` case 1 proves `banscore == 0`
   after the rejected block **and** after two relayed descendants, with node 1 still a peer (N1).
5. Fail open on storage only: a storage fault injected at each hook accepts the block;
   `EvaluateBlock` is total (fuzz replay green; grep for `throw`/`assert` in `state.cpp` empty).
6. `DisconnectBlock` undo is inside `if (updateIndices)`; `VerifyDB` at `-checklevel=4` on a
   node with an index leaves the index hash unchanged (test).
7. `CommitConnect` is never reached under `fJustCheck` (`TestBlockValidity` on a template leaves
   the index tip unchanged; test).
8. Kill switch and valve: `Rejected` hashes are reconsidered at start and cleared
   (`yellowback_enforcement.py` case 5; `killswitch_fresh_datadir`,
   `killswitch_rejected_hash_not_in_mapblockindex`); the same loop runs at the valve trip
   (case 9, `valve_trips_at_six_blocks`); a block that is also consensus-invalid is absent from
   `Rejected` (case 7); `Rejected` survives `kill -9` (`rejected_survives_kill9`).
9. Every rule identifier in §3.2 and §3.7–3.9 appears verbatim in a `// Rule:` / `# Rule:`
   comment tag on a unit case or a functional-test docstring (the §7 loop, run in CI job `audit`;
   N36) and every functional flow has a script (§7).
10. Apply/undo identity and cold-rebuild equality under reorg stress with enforcement events.
11. `IsStandardTx`/`AreInputsStandard` pass for every template incl. the claim path.
12. Determinism grep empty over the §3.10 set — `state.cpp`, `tag.cpp`, `payload.cpp`,
    `script.cpp`, `view.cpp` and `state.h`, `math.h`, `tag.h`, `payload.h`, `script.h`, `view.h`,
    exactly the set Phase 2's acceptance block greps. **`index.cpp` is deliberately not in it**
    (corrected 2026-09-11): `ParamsFromArgs` legitimately reads `GetArg` there for the four
    regtest-only flags, which Phase 3 places in that file, and the index is not a pure function of
    the chain the way the state machine is. `GetTime` only in `rpc/yellowback.cpp` and
    `policy.cpp` (M11).
13. Coin locking: every YED output the wallet owns is locked before `CommitTransaction` (vault
    outputs are never `IsMine` and need no lock, §4.6, N39) and stays locked across a reorg, and locking covers every mine-owned token outpoint after a
    restart; a YED input is never selected by the plain `sendtoaddress`/`z_sendmany` paths, even
    one issued immediately after `yed_mint`/`yed_send`; disconnecting a block never removes a coin
    lock and a VOID mint's token output is unlocked only once the block is applied; `lockunspent`
    cannot unlock a Yellowback lock (H5); `wallet.dat` format untouched — `yellowback_lifecycle.py` and
    `yellowback_wallet_restore.py`.
14. The wallet refuses to build a mint before activation and under each halt with the matching
    `mintpol-*` identifier (`yellowback_void_mint.py`), and refuses a redemption or claim that
    `MempoolCheck` rejects (`yellowback_lifecycle.py`, `yellowback_claim.py`).
15. `getblocktemplate` carries the tag in all three carriers, and a coinbase rebuilt by the
    pool path yields a readable tag (test).
16. The index survives `kill -9` with the chainstate unflushed (test) and refuses `-prune`.
17. For every hash in `Rejected`, `yed_getblockverdict` returns `blockInvalid == true` with a
    non-empty reason (`yellowback_enforcement.py` case 7), and refuses for any block whose parent
    is not the tip (`verdict_parent_not_tip`, N12).
18. Docs: `! grep -q 'no consensus change' doc/yellowback.md`; the trust statement is §8.1 verbatim
    (the `diff` command of Phase 7's acceptance block, run in CI job `audit`); the runbook covers
    the kill switch, the mainnet signal default (L4), the `-reindex` procedure (M12, N2), the fork
    warning and the valve (N11, L7), the sunset (L8), filter-only mode (N3), catch-up
    suppression (L11) and the incident playbook (P14) —
    `grep -q` for each of `yellowbackenforce=0`, `reindex`, `valve`, `sunset`, `filter-only`,
    `catch-up`, `incident` in `doc/yellowback-mining.md`.
19. No new build dependency; `configure.ac` untouched; no sockets in node Yellowback code.
20. The shutdown sequence (unregister, stop, flush) holds for the synchronous hooks: a block
    connecting during `Shutdown()` cannot race the index (the hooks run under `cs_main`, which
    `Shutdown()`'s flush takes) — a reviewer-signed claim, with `yellowback_index.py`'s
    `crash_unflushed_chainstate` and `rejected_survives_kill9` as the mechanical companions.
21. **Stock parity (N10):** `yellowback_stockparity.py` passes nightly — the fork binary without
    `-yellowback` and a `ref/ycash` v4.5.0 binary produce identical block hashes,
    `gettxoutsetinfo.hash_serialized`, `getinfo` and `getblocktemplate` key sets over the same
    scripted scenario; `yellowback_stock_node.py` passes on every PR.
22. **Shielded pool (N13):** the existing `transaction_builder` tests are unchanged and green;
    the three new `TransactionBuilder` methods are called only from `src/yellowback/` —
    `git grep -n 'AddRawScriptOutput\|AddUnsignedTransparentInput\|SetLockTime' -- src ':!src/transaction_builder.*' ':!src/yellowback' ':!src/test'`
    empty; the `ConnectBlock` failure path discards `view` before any flush (`ConnectTip`,
    `main.cpp:3612-3618`), TX-0 ignores shielded components, and `DisconnectBlock`'s undo runs
    after the coins rollback — a reviewer-signed claim with those three cites.
23. **Concurrency (P6):** the `lockorder` job (`DEBUG_LOCKORDER`) and the `sanitizers` job
    (address, undefined, thread) are green on the last seven nightly runs before the rc1 tag;
    links in the review document (`job:` evidence rows).
24. **Coverage (P6):** the `coverage` job's floors hold (`qa/yellowback-coverage-floor.sh`
    exits 0 on the last run's `lcov.info`); the per-file table is pasted into the review document.
25. **RPC contract (P7):** `yellowback_rpc_contract.py` passes on every PR, and the wallet job's
    field check against `yellowback-rpc-contract.json` passes on the wallet fork's tip.

### 8.5 Statement requested from the Ycash maintainers (N13)

**What they are asked.** A review of the hook lines — the ≈ 29 inserted lines in `main.cpp` and
≈ 18 in `miner.cpp` listed in §4.3 — and of the evidence in `doc/yellowback-review.md` for the
three claims below. Not a merge into Ycash, not an endorsement of Yellowback, not a statement
about its economics, its price feed or its governance bar; those are the pool operators' and the
product owner's, and §8.1 says so.

**The three bounded claims, each with the evidence that lets a reviewer sign it:**

1. *No consensus file changes.* `git diff --stat ycash-legacy...feature/yellowback-sf -- src/consensus
   src/script src/primitives src/pow src/chainparams.cpp src/wallet/wallet.h src/wallet/wallet.cpp
   src/txdb.cpp src/txdb.h configure.ac` is empty (§8.4 item 1, run in CI).
2. *Stock nodes are unaffected.* A node without `-yellowback` runs v4.5.0's code paths; the only
   unguarded differences are two includes, one lock acquisition and an empty script append
   (§8.4 item 2), and `yellowback_stockparity.py` shows the binary indistinguishable from
   `ref/ycash` v4.5.0 over a scripted scenario (item 21).
3. *The hook cannot corrupt the chainstate or the shielded pool.* The check runs in
   `ConnectBlock`'s window after every consensus check and returns through the same
   `state.DoS(0, …)` path any other failure uses, so a rejection discards `view` before any flush
   (`ConnectTip`, `main.cpp:3612-3618`) and leaves the Sprout/Sapling anchors and value-pool
   counters untouched; TX-0 ignores shielded components; the commit runs after every write that
   can `AbortNode`; the undo runs after the coins rollback and only under `updateIndices`; the
   `transaction_builder` extension is additive and called only from `src/yellowback/` (item 22).

**What they are not asked.** Whether the fee, the medians, the σ multiplier, the activation
floors or the launch bar are wise; whether pools will run it; whether YED holds its peg.

**The honest facts, stated so that a yes is a signature under a bounded claim rather than a
surprise later.** The Ycash team holds no kill switch — pool operators do (`-yellowbackenforce=0`),
and a split, if one happens, is resolved by pools and bounded mechanically by the work valve
(six blocks, ACT-7), not by the maintainers. Enforcing nodes never ban stock peers, neither for
a rejected block nor for its descendants (N1), never reject during initial sync (N2), and never
reject a block the network has already built six blocks on (L11). A stock
pool that runs nothing can have blocks orphaned by rule-breaking transactions it cannot see
(N3), which is why every pool is asked to run at least filter-only mode. Every release
enforces only until a sunset height (L8), and the fork commits to a release within 14 days of
every Ycash release (§11), so a Ycash network upgrade is never blocked or lagged by this work.

---

## 9. Upgrade path — consensus enshrinement (design constraint only)

When the rules have run under miner enforcement long enough, a Ycash network upgrade
(`UPGRADE_YELLOWBACK` with a fresh branch ID, `mapping.md` §4) can promote BLK-1 to a rule every
full node applies: `ContextualCheckBlock`/`ConnectBlock` call the same `EvaluateBlock`, the
`Rejected` table, the kill switch, the work valve (ACT-7) and the sunset (`ENFORCE_UNTIL_HEIGHT`,
L8 — a consensus rule needs neither, and the upgrade's own activation height is the last sunset)
are removed, `activateHeight` is pinned per network (the
activation state machine is retired, as DigiByte buried its deployment), and the coinbase tag
becomes a consensus-validated field (a block after the upgrade must carry a valid tag or none —
still never a price requirement, so a miner without a feed stays valid). Because v2's validator is
already a pure function of `(block, state, params)` and its state is already applied inside
`ConnectBlock`, the enshrinement changes *who runs the check*, not what it checks — including
everything §3.1 marks as consensus-shaped among enforcers today (every parameter a rule reads:
the price windows, `PAYEE_WINDOW`, the fee constants, `CLAIM_THRESHOLD_BPS`, `GRACE`, the
activation floors, the class ratios and caps; not the judgement or wallet-default rows, L1/L6),
which the upgrade would make consensus for every node. A proof-opcode
alternative — a generic `OP_CHECKPROOFVERIFY` (Groth16 over BLS12-381, the verifier Ycash already
runs for Sapling) under which the vault script becomes "lock height, owner signature, proof" and
the user proves that the redemption burns the required amount, so consensus learns nothing about
Yellowback and rule upgrades are circuit versions — remains a possible destination for the
vault-spend rule alone; it is not required for v2.

---

## 10. Deviations

### 10.1 From the proposal (v0.2)

| Proposal says | This plan does | Why |
|---|---|---|
| Every rule violation makes a block invalid after activation (§3.2 item 4, §5) | only vault spends failing RED-1..4 do; mints and transfers keep verdict semantics | V3: minimal consensus-shaped surface; soundness needs only R1/R2 |
| The module fetches exchange prices and computes a 15-minute VWAP (§4.1) | an external quote agent computes it and pushes it with `yed_setquote`; VWAP where volume is reported, TWAP otherwise | V6: no HTTPS in `ycashd`; the prototype's source layer exists |
| Stale quote ⇒ omit the tag (§4.1) | stale quote ⇒ signal-only tag | V9: keep participation independent of feed outages |
| Transfers may be recorded in Sapling memos; balances tracked by recipient id (§5.3) | YED stays on transparent colored outputs; the YEC side may be shielded (mint from / redeem to `ys1…`) | V8: miners cannot enforce what they cannot read |
| Separate VAULT and MINT records; top-up mints (§5.1–5.2) | one MINT creates the vault and its single debt | V15 |
| `selected_block = tip_height − (txid_low32 mod 100)`, weighted by accuracy, as a validity rule (§6.1) | validity: any pool that quoted in the payee window, right amount; the deterministic accuracy-weighted choice is the wallet default (FEE-W) | V10 / L1: the txid is circular, the tip is undefined for an unconfirmed transaction, and judgement arithmetic stays out of the shared rules |
| Fee = 0.25 % of collateral value at `P_mint` (§6.1) | `max(0.5 YEC, collateralZat / 400)` | identical in YEC; no price dependency |
| Fee always required (§6.1) | FEE-0: no fee when no pool tagged in the payee window | burns must never depend on participation (§5.6 of the proposal) |
| σ from block-to-block log changes of raw quotes (§5.2) | σ from the `P_fast` series every 48 blocks, bps returns, capped at 3× | V17: cross-pool spread would read as 600–2,000 % annualised |
| Peer median over "20 surrounding blocks" (§4.4) | judged once at `t + 10` over `[t − 10, t + 9]`, ≥ 5 peers | V18: deterministic and undoable |
| Class C is "> 365 days" (§5.2) | `(365 d, 5 y]` | V19 |
| Windows silently thin when few pools tag (§4.2) | a window below half fill is undefined ⇒ minting halts | V16 |
| Activation "modeled on BIP9" (§7) | rolling evaluation of the trailing 2,016 tags; lock-in, delay, hysteresis as specified | V12: Ycash has no versionbits |
| RPC names `getyecusdprice`, `getyedstate`, `getvault`, `validateyellowbacktx` (§3.2) | `yed_getprice`, `yed_getstats`, `yed_getvault`, `yed_validaterawtransaction` (the prototype's RPC contract, `yed_` prefix) | V22 |
| Claim ordering "first in block" (§5.5) | moot in the UTXO model (one spend per outpoint); the fairness concern is Q2 | §12 |
| Rules R1/R2 police every vault | ACTIVE vaults only; VOID vaults are unpoliced | K3 |
| Enforcement from `H_activate` on, unconditionally (§7) | from `activateHeight + 1`, and suspended while signalling is below half (resuming at 60 %); minting halts below 60 % (resuming at 75 %) | K2, K16, L3 |
| Signalling begins when a pool installs the module (§7) | on mainnet the first release does not signal by default; pools signal after the diversity bar is measured on quote tags and announced | L2, L4 |
| The agent reuses the last good quote for up to 30 minutes (§4.1) | the agent clears its quote after two failed polls; the node's 30-minute clock is the backstop | L5 |
| Accuracy weight over "its last 576 quotes" (§4.4) | over the judged quotes in the last 576 heights, as a fraction | K8 |
| "Embed the filter library in the stratum layer" (§3.3) | not provided; pools consume the node's template or append `coinbaseaux.flags` | §12 Q9 |
| No minimum collateral beyond the ratio | `collateralZat ≥ 4 · FEE_MIN` at mint | K14 |

### 10.2 From the federation prototype (`feature/digidollar`)

| Federation prototype | v2 | Why |
|---|---|---|
| Tier 0, zero lines in `main.cpp` | Tier 1 + a block-validity hook (≈ 29 lines in `main.cpp`, ≈ 18 in `miner.cpp`, §4.1) | the federation is gone; someone has to enforce burn-on-release |
| Federation k-of-n in the vault script; co-signed redemptions | owner-only path + anyone-can-claim path | V7 |
| Anchor-chain PRICE transactions | coinbase tags, medians | V4–V6 |
| Asynchronous `ChainTip` index | synchronous hooks; subscriber kept for wallet locks | V2 |
| DCA, ERR, volatility freeze (DigiByte's protection systems ported as integer tables; the freeze stopped mints only) | global-ratio halt, divergence halt, σ-indexed ratios, claims | V20 |
| Tiers 0–4 fixed lengths | classes A/B/C with a free lock length | V19 |
| `evalHeight` | `refHeight` (same rule, wider use) | V11 |
| `yed_redeem` + the operator `/cosign` endpoints + `yed_submitredeem`, `PendingRedemption`, wizard | one-step `yed_redeem`, `yed_claim`, `yed_sweep`, a dialog | V24, L10 |
| Payload version 1, PRICE type | version 2, PRICE retired | V23 |
| `synced` flag | gone (index at tip) | V2 |
| `UNDO_KEEP = 1,000` | 4,096 | V2 |

### 10.3 From DigiDollar (`v9.26.5`)

Rows the overlay inherits from the prototype, restated:

| DigiDollar | Yellowback v2 | Reason |
|---|---|---|
| Tapscript opcodes `0xbb–0xbf`, `SCRIPT_VERIFY_DIGIDOLLAR` | none | `mapping.md` §2; not needed for tx-level rules |
| P2TR 2-leaf MAST vault with NUMS key | P2SH two-path script (owner CLTV path, anyone-can-claim path) | no Taproot; V7 |
| `nVersion` bit-packed type/flags | payload type byte | `mapping.md` §5 |
| 10 tiers (1 h – 10 y) | classes A/B/C with a free lock length | V19 |
| Mint $100 – $100,000; no supply cap | $100 – $10,000; cap as a share of issued YEC | liquidity; V21 |
| Volatility uses timestamps and standard deviation | σ from block-window snapshots, integer | determinism |
| Mint window `[tier, tier+100]` at 15 s blocks | `refHeight` window of 40 at 75 s blocks | equals tx expiry; V11 |
| Mint collateral checked against the confirmation block's oracle price | checked against `Snapshots[refHeight]` committed in the payload | in an overlay a failed mint locks collateral instead of being rejected |
| `__int128` | `arith_uint256` / signed 64-bit | Ycash has no `__int128` use; portability |
| Wallet `dd_*` tables, descriptor wallets required | no wallet tables; keypool wallet + index | §4.6 |
| Qt GUI: seven DigiDollar tabs in-process over `WalletModel` (`src/qt/digidollar*`, ≈ 10,400 lines) | one Yellowback tab in **YecWallet** (`yecwallet-dd`, Qt 6) over the `yed_*` RPC contract; coin control dropped | Ycash ships no GUI in the node; `mapping.md` §12 |
| `txindex=1` required | not required | index is self-contained (`TxLog`) |
| Transfers require confirmed inputs at consensus | wallet-enforced; state machine allows in-block chaining | determinism without a mempool rule |
| Single asset, no type-namespace reservation | single asset; `type` `0x20–0xFF` reserved, no-mixing constraint stated | §3.3; a later asset is an overlay upgrade, not a network upgrade |

New rows:

| DigiDollar | Yellowback v2 | Reason |
|---|---|---|
| The consensus price is the single price in the block's own coinbase bundle (`ref/digibyte/src/validation.cpp:3110-3126`), signed 7-of-35 MuSig2 (`oracle/bundle_manager.cpp:2480-2597`) | medians over 96/576/2,016 tagged blocks; no signature — hashpower is the signature | Ycash has no MuSig2; medians make a single block immaterial |
| Miners are anonymous carriers; no per-miner accountability (grep confirms) | registration, peer-median penalties, accuracy-weighted fees (the penalty and weighting act through wallet defaults only, L1) | the proposal's incentive design |
| Buried BIP9 deployment (`kernel/chainparams.cpp:174-188`) | overlay signalling from tag bits | no versionbits in Ycash (`mapping.md` §4) |
| Invalid DD transactions rejected at DoS 100 (`digidollar/validation.cpp`) | only vault spends rejected, at DoS 0; descendants of a rejected block at DoS 0 too (`bad-prevblk-yellowback`) | soft fork carried by a minority of nodes; never ban stock peers |
| A consensus rule is in force for ever; no valve, no sunset | the work valve (ACT-7) and the per-release sunset (`ENFORCE_UNTIL_HEIGHT`) | a rule enforced by a subset of nodes must bound its own minority-chain exposure and its own lifetime (`mapping.md` §13) |
| Volatility from a wall-clock, process-global price history read inside consensus (`consensus/volatility.cpp:212-251`, `digidollar/validation.cpp:1153-1161`) | σ from snapshots, pure function of the chain | determinism |

---

## 11. Inputs required at launch (operational, not design)

| Input | Default in this plan | Who supplies |
|---|---|---|
| `START_HEIGHT` per network | at least two weeks of blocks past the release date (M14) | release engineering (testnet Phase 9, mainnet Phase 10) |
| Pools running the module | ≥ 2 on testnet; on mainnet enough for 75 % **and** the launch bar (≥ `N` independent pools, none above `X %`, L2) | Ycash pools; recorded in `doc/yellowback-mining.md` |
| `N`, `X` for the launch bar | provisional `N ≥ 3`, `X ≤ 40 %` (L4) | confirmed in Phase 9 from the mainnet distribution measured with `yed_listminers <height> 2016` (known diverse as of 2026-09-10) |
| Pool payout addresses, quote-agent source configuration | per pool | operators |
| Source-mask bit registry | bits 0–3 assigned in §5 (SafeTrade, CoinGecko, CoinMarketCap, Nonkyc); 4–15 by spec revision | this plan (M9) |
| `SIGMA_REF_BPS`, class base ratios, `SUPPLY_CAP_BPS`, `GRACE` | §3.1 | calibrated on testnet (Phase 9) |
| Pool-stack integration notes | — | Phase 7 survey |
| `ENFORCE_UNTIL_HEIGHT` per network, per release | `startHeight + 420,480`, capped at the next known Ycash network-upgrade activation height (L8) | release engineering, every release |
| Fork release cadence | a `ycash-dd` release within **14 days** of every Ycash release, tracked on `feature/yellowback-sf`, carrying the next parameter set with its sunset (N17) | release engineering; recorded in `doc/yellowback-mining.md` |
| Maintainer review of the hook lines | the §8.5 statement | Ycash maintainers (Phase 8) |

---

## 12. Open questions

1. **Grace period** (proposal Q1): 30 days is a placeholder; a testnet parameter.
2. **Claim fairness** (proposal Q2): a pool can front-run claims on its own blocks. A
   claim-announcement (commit-reveal) window would add a payload type and a state table; deferred.
3. **Supply cap** 15 % and **class ratios** (proposal Q3, Q5): calibrate on testnet.
4. **Reserve** funded by a fee slice (proposal Q4): not in v2, and **no dormant split parameter
   is added** — a value no rule reads would contradict K10's versioning rule and invite drift; a
   later slice is a new parameter plus one output rule in a release (M15).
5. **Exchange support** (proposal Q6): the read-only `yed_*` RPCs (and, if ever revived, the inactive
   indexer-service idea in `../ideation/`) cover it; a standalone verification library is not planned.
6. **Shielded YED** (V8): research; requires a value-pool commitment in consensus.
7. **σ calibration and the 3× cap** (V17): the cap is a safety rail, not a model; revisit with data.
8. **Burying activation** (§9): after mainnet activation, pin `activateHeight` in a release? (The
   work valve and the sunset — L7, L8 — are decided and not open; a buried activation would keep
   both until enshrinement.)
9. **Pool software**: which stacks Ycash pools actually run, and whether each honours
   `coinbaseaux.flags` / `coinbase/append` or needs the `coinbasetxn` path; Phase 7 survey.
10. **Hashpower concentration** — *decided (L2, L4)*: the landscape is known and diverse today;
    the launch bar in Phase 10 (`N ≥ 3` pools, `X ≤ 40 %`, measured on quote tags with signalling
    off by default until the announcement) is the safeguard; the measurement is code, the bar is
    governance.
11. **P2P `reject` messages**: an enforcing node still queues a `reject` to the peer that relayed a
    rejected block (`main.cpp:2302-2303`, sent at `:7168-7170`). Harmless; suppressing it would
    add a line to `main.cpp`. Leave it.
12. **Quote VWAP vs TWAP**: which venues report volume reliably enough for VWAP; the agent falls
    back to TWAP per source.
13. **Fee as block validity or as policy** — *decided (L1)*: amount plus any recently quoting
    pool is validity; the choice of pool, with its accuracy weighting and penalties, is wallet
    policy, with release-versioned defaults a node may override (L6). Revisit only if pools
    report that wallet defaults are being gamed.
14. **Signed tags** (K9): a 64-byte signature over the tag would end impersonation but leaves no
    room in the 100-byte coinbase scriptSig for a pool's own text; a compact alternative is a
    per-pool registration transaction binding `payoutKey` to a signing key. Deferred. (Forged
    *signal* bits, N4, are bounded by the work valve, L7, and are not this question.)

Nothing new opened in revision 5: the four questions its audits raised were decided (L7–L10).
Revision 6 opened none either; its four adjustments (L11–L14) are applied in the text and await
the product owner's confirmation — a "no" on any of them reopens it here as a question.

---

## Appendix A — Rows added to `docs/mapping.md`

Recorded there as §13 ("Rows added while planning v2, 2026-09-10"): the coinbase carrier
(scriptSig tag via `COINBASE_FLAGS` vs DigiByte's `OP_RETURN OP_ORACLE` output), the price
definition (medians vs the block's own bundle), activation (overlay signalling vs buried BIP9),
block rejection at DoS 0 and the kill switch, the index's crash consistency against a lazily
flushed chainstate, the hook placement (`ConnectBlock`/`DisconnectBlock` with `fJustCheck` and
`updateIndices` guards vs the atomic-swap split), the template filter site, the dead
`coinbaseaux` branch in `getblocktemplate`, volatility determinism, per-miner accountability,
`IncrementExtraNonce` overwriting the scriptSig, the claim path under Ycash's script flags,
`DisconnectBlock`'s `updateIndices` parameter, and (revision 5) the work valve and the enforcement
sunset — two things a consensus rule never needs and a subset-enforced rule must have.

## Appendix B — Glossary

- **Tag** — the 36-byte record a pool puts in its coinbase scriptSig: quote, signal, payout key.
- **Quote tag / signal-only tag** — a tag with / without a price.
- **R1 / R2** — the proposal's two rules: collateral is released only with the burn (R1); the claim
  path is spent only against an underwater vault, with the burn (R2). RED-1..4 implement both.
- **Registered miner** — informational (`yed_listminers`): a payout key that published a quote tag
  within the last `N_REG` blocks. Not a rule input (L1).
- **Eligible payee set `E(R)`** — the payout keys of the quote tags in the 100 heights up to and
  including `R`; the only thing block validity checks about a fee's payee (FEE-2).
- **FEE-W** — the wallet's default choice among `E(R)`: deterministic, accuracy-weighted, penalty-
  skipping, with release-versioned parameters a node may override (L6).
- **Enforcement fee** — the YEC a mint, redemption or claim pays to a key in `E(R)`.
- **Enforcement suspension** — the `ENFORCEMENT` halt bit (ACT-6): block rejection is off while
  signalling is below half, back at 60 %; distinct from the mint halt (60 % / 75 %).
- **Reference height (`refHeight`)** — the snapshot height a transaction's rules are read at.
- **Enforcing node** — a `-yellowback` node with `-yellowbackenforce=1` after activation, before
  its release's sunset, whose valve has not tripped.
- **Work valve (ACT-7)** — the node-local rule that clears enforcement for the session once a
  chain rooted at a block this node rejected is `VALVE_BLOCKS = 6` blocks of work ahead of its
  tip, reconsiders the rejected blocks and lets the node rejoin; re-armed by restart (L7).
- **Sunset (`ENFORCE_UNTIL_HEIGHT`)** — the height, carried by every release's parameter set,
  past which the node tags and accounts but rejects nothing until upgraded (L8).
- **Abandonment** — the shared condition (`ENFORCEMENT` set continuously for `ABANDON_BLOCKS`;
  nothing else, L12) under which `yed_sweep` builds, every ACTIVE vault shows `sweepBefore`, and
  MP-1/TPL-1 stand down for vault spends (L10, L13).
- **Sweep** — an owner-path vault spend with no burn and no fee, built only under abandonment;
  leaves the vault `CLOSED, unbacked` (L10).
- **VOID release** — the owner-path spend of a VOID vault (no debt, no burn, no fee, no payload),
  built by `yed_redeem` at the lock height; an ordinary spend no rule polices (K3, L14).
- **Catch-up suppression** — BLK-2's third clause (L11): a block the best known header already
  carries `VALVE_BLOCKS` of work above is accepted rather than rejected, counted in
  `suppressedBlocks`, enforcement untouched.
- **Filter-only mode** — `-yellowback -yellowbackenforce=0`: the pool filters its own templates
  and never rejects a block; the zero-risk way for a non-participating pool to keep its blocks
  from being orphaned (N3).
- **Activation** — the state machine SIGNALING → LOCKED_IN → ACTIVE computed from tags.
- **Vault** — a P2SH output with the two-path script; **claim path** — its anyone-can-spend branch.
- **Claim** — spending an underwater vault's claim path by burning its debt.
- **Unbacked** — a vault closed without its burn on a chain an enforcing node would not have accepted.
- **Halt** — a condition that stops minting only (never transfers, redemptions or claims).
- **Index** — the node-local, rebuildable Yellowback state database, now synchronous with the chain.

---

**Provenance.** The federation prototype this plan strips and builds on was designed in the
archived documents under `archived/` (development plan, hardening plan, protocol spec). They are
history, not inputs: every rule, constraint and finding this plan relies on is stated in this plan.
