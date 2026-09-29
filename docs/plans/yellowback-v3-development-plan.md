# Ycash Yellowback (YED) v3 — Development Plan: bond-weighted price attestation

**Execution status (2026-09-14, coordinator).** Implementation began 2026-09-13 with parallel
subagents, one per non-overlapping chunk, each in its own `wt/<name>` worktree off
`feature/yellowback-price-attest` (the v2 pattern; the shared briefing is the orchestrator's
`BRIEFING.md`). This table is the authoritative state; the checkboxes in §6 are flipped only
when the coordinator has merged the chunk and seen its tests run.

**Where it stands: A0–A5 are implemented and merged in both forks.** On the node's
`feature/yellowback-price-attest`: 224 unit cases green, the corpus check green, and
`yellowback_rpc_contract`, `yellowback_attest`, `yellowback_attest_wallet`,
`yellowback_attest_enforcement`, `yellowback_index`, `yellowback_stock_node`,
`yellowback_wallet_restore` and the four v2 flow scripts in **both** unarmed and `--armed` modes
all pass. Frozen files are at **zero** delta against `feature/yellowback-sf`, and `main.cpp` (11),
`miner.cpp` (12) and `rpc/mining.cpp` (7) are unchanged from v2 against `ycash-legacy`; `init.cpp`
gained 14 lines. On the wallet's: 83 QTest cases green offline, contract check green.
**A4 is complete as of 2026-09-20, and the role-based regtest tooling
(`role-based-regtest-plan.md`, R1–R7) is built, verified and green the same day**: the devnet
leaves one seat empty (`up --role {user,attestor,pool}`), a heartbeat, a price walk and six
simulated personas keep the economy moving, and the nightly `yellowback_devnet_roles.py` proves
all of it on three presets — including a third-party liquidation by the emergency clause. Running
that economy found and fixed one wallet-tier defect the A0–A5 suites had never reached (D-R-1,
§6.2). What remains: the owner walking the four scenarios (Phase A7's rehearsal), A6 (hardening,
packaging, the review document and the rc run-through), and A7–A8, which need real attestors and
cannot run on one machine.

| Phase / chunk | State |
|---|---|
| A0 `proto` — `params`, `payload` v3, `math.h`, corpus | **complete, merged** (2026-09-13); `ParamsFromArgs` (index.cpp) and the golden vector landed in the `glue` chunk |
| A0 `crypto` — `script` carrier/bond, `attest`, `bundle`, vectors, fuzz target | **complete, merged** (2026-09-13): 15 new unit cases; the `YellowbackBundle` fuzz target is in the CI target list since `glue` |
| A0 `pyfw` — `test_framework/yellowback_attest.py`, `yellowback_util.py` v3, runner pass-through | **complete, merged** (2026-09-13): 24 unit cases, pyflakes clean; the merge needed two coordinator fixes before `yellowback_framework_smoke.py` was green (`reconnect()` and `_cross_edges()` indexed nodes 6–7 in a six-node run) |
| A0 `docs` — `doc/yellowback-rpc.md` v3, contract JSON, mapping rows, frozen-file list, CI audit/agent jobs | **complete, merged** (2026-09-13); `make spec-check` clean |
| A0 `glue` — golden vector at payload v3 + preimage, `ParamsFromArgs`, `PayloadToJSON` v3, `BundleStat` → `math.h`, fuzz target in CI | **complete, merged** (2026-09-13): 162 unit cases green, `yellowback_pricefeed.py` ends with `assert_model_matches(full=True)` against the v3 node. **A0 complete.** |
| A1 — state machine v3 (`view`, `state`, model, golden) | **complete, merged** (2026-09-13): 211 unit cases (49 new, one tagged case per v3 identifier), model and golden regenerated (440 blocks: registration, arming, bundled mint, VOID mint, notice, emergency claim with residual, dormancy, equivocation, revival, bond spends; hash `abe131e0…a4fe`), fuzz corpus +12, the v3 rule-tag CI step blocking; the six v2 flows pass **unarmed** — v2 behaviour intact |
| A2 — index, pool, node RPCs, MP-1/TPL-2 wiring | **complete, merged** (2026-09-13): 216 unit cases; `yellowback_attest.py` (512 blocks, model match `full=True`), `yellowback_attest_enforcement.py`, `yellowback_rpc_contract.py`, `yellowback_index.py` (+3 cases), `yellowback_stock_node.py` green; `rpcversion` 3; `mempoolcheck_bench` 6 ms / 10k plain transactions |
| A3 — wallet builders and RPCs | **complete, merged** (2026-09-14): carriers.dat, the attest-signed.dat guard, every builder and wallet RPC, the two-step flow (`wait`, `-yellowbackcarriertimeout`); merged onto A2 by union (four conflicts, all additive) |
| A2/A3 integration — the `BuildBundle` seam, `canNotice` via `EstimateClaim`, contract exemptions removed, full re-run | **complete, merged** (2026-09-14): the wallet's builders take their bundle from the node's pool when no `bundleHex` is given; `yed_listpositions` judges claimability through the shared `EstimateClaim`; every contract exemption removed and every documented command exercised; twelve functional scripts re-run green on the combined tree; frozen-file proof empty. The coordinator additionally registered `yellowback_attest_wallet.py` with the runner — A3 had shipped it unregistered, so CI would never have run it |
| A4 `agent` — `contrib/yellowback/attest/` Rust crate | **complete, merged** (2026-09-13): `attest`/`subscribe`, real `iroh-gossip 0.101` on `iroh 1.2` (toolchain pin 1.91.0) plus the `dir` transport, aggregator port equal to the Python reference on three recorded scenarios, 34 `cargo test` cases, clippy and fmt clean. A crate-local `.cargo/config.toml` undoes the node's vendored-sources redirect so the crate builds inside a built checkout |
| A4 `calibrate` — `contrib/yellowback/attest/calibrate/`, attestor guide, contrib README | **complete, merged** (2026-09-13): 19 offline unit cases; `spreads.py`/`pinrate.py` end to end on synthetic CSVs. The contract gained `bondKeyAddress` (the P2PKH fee payee, distinct from the bond output's P2SH `bondAddress`) at the agent's suggestion |
| A4 `devnet` — devnet that arms, `yellowback_attest_agent.py` (nightly), `check` extended | **complete, merged** (2026-09-20): the devnet is eight nodes, registers 5–7 with `yed_registerattestor 10 200`, mines through `BOND_MATURITY` and `ATTEST_ARM_DELAY`, and starts three real `yellowback-attest attest` agents plus one `subscribe` on the `dir` transport. Run end to end on one laptop: TRIGGERED at 242, ARMED at 250, `poolFresh` 3, and a mint with **no** `bundleHex` built from the agents' pool (`bundleSeqs [0,1,2]`, `aMint` the attested price, the attest fee paid to a selected attestor's `bondKeyAddress`). `attestor N stop\|start\|price`, `notice` and the extended `check` all exercised; `--no-attest` keeps the five-node v2 devnet. **0 C++**, frozen files at zero delta. Three defects found by running it — see §6.1 |
| A5-a — YecWallet read-only views | **complete, merged** (2026-09-13): `RPC_VERSION 3`, every v3 field in `yellowbackrpc.h` (contract check green), Attestors page, source prices and selection line, `noticed` badge, transport settings; 73 QTest cases offline |
| A5-b — wallet actions (two-step mint, notice, launcher, attestor actions) | **complete, merged** (2026-09-14): 83 QTest cases offline; `build.sh --attest`; the devnet case is written and skips until `a4-devnet`; `--package --attest` not yet run (A6) |
| Role-based regtest (`role-based-regtest-plan.md`) — role presets, heartbeat, price walk, `yellowback-sim` personas, scenario checklists, `yellowback_devnet_roles.py` | **complete, verified** (2026-09-20): all seven chunks built; the suite green on `user`, `attestor` and `pool` (seed 7): seat empty, heartbeat on automated pools only, every persona acting, a redeem at maturity, a −70 % shock, a clause-(b) liquidation by a third party, one state hash on ten enforcing nodes. Found D-R-1 (§6.2) — a claimant-node segfault after an emergency claim — fixed the same day in the wallet layer with a regression case in `yellowback_attest_wallet.py`. 0 consensus lines; `wallet.cpp` untouched. R8 (a pool terminal view) stays deferred until Scenario 3 asks for it |
| A6 — hardening, DoS measurement, sanitizers, the review document, rc2 | **not started** — the scenario walk-throughs' findings (regtest plan §5) are its input |
| A7, A8 — testnet with real attestors, then mainnet | need real attestors; cannot run on one machine |

**Note (2026-09-13/14):** the A2 and A3 agents were each terminated once by an API session limit
with their C++ committed and their functional scripts uncommitted; both were resumed with context
intact and no work was lost.

**A1 decisions confirmed by the coordinator (2026-09-13):** (i) key prefixes `A<u16 seq>` for `Attestors` and `W<u32 height>` for `BundleLog` — the plan's `T`/`L` were already Tip and TxLog; hash order after `P`: A, N, M, W, E. (ii) **R15's evaluation order applies only when `Snapshots[R]` is ARMED**; unarmed, MINT keeps the exact v2 clause order, because moving MINT-5 behind MINT-8 changed v2 verdicts (`yellowback_void_mint.py` caught it). (iii) AFEE-1 runs after MINT-9 (it needs `A`), so the order when ARMED is MINT-2,3,4,6,7,8 → MINT-9 → AFEE-1 → MINT-5 → MINT-10; MINT-6's cap reads `xMint`. (iv) `ageOrigin` reads `Snapshots[R].attest`, a pure function of `R`. (v) `Snapshot.pMint/pClaim` keep their names and are the cross-section (`xMint/xClaim` in the RPC). (vi) `groups()` ignores nodes a script appends after setup (the A0 framework's `SPLIT_HALVES` change had broken `yellowback_index.py`'s late node 6).

**A2 findings applied (2026-09-13):** a reorged citation usually fails BUNDLE-1 at *membership* (the selection is seeded by `blockHash(R)`, which the reorg changes) — `sig` only when the two selections intersect; `attest_reorg_across_arming` splits before the third registration (both branches pass a height-based `armHeight`); a registration undone by a reorg is dead on the winning chain (REG-A1's lock distance), so the wallet must rebuild it; PIN-1 pins any pool quoting one constant price whenever attestors move over 5 % — the mining runbook must say so; `seatedCount` drops one block after a DORMANT verdict (SNAP seats before the dormancy pass). New shared helpers: `src/rpc/yellowbackrpc.h` (`PushNoticeFields`, `EstimateClaim`), `index.BuildBundleInfo`, `InsufficientMessage()`, framework `send_and_lock` (fixed a double-spend in `register_and_arm`), `build_vault_spend_raw(carrier=…)`, `withdraw_bond_raw`.

**A3 findings (2026-09-14):** `canNotice`/`canClaim` under clause (b) were judged from `xClaim` alone in A3's worktree (a sufficient condition) — the integration chunk switches them to A2's `EstimateClaim`; the carrier's two-step means every regtest script calling `yed_mint` must mine from another thread or use `wait=false` (the framework's `two_step` does the former); `CarrierConfirmed` requires both the chain and the wallet's notifier to have seen the carrier, else the mint would re-spend the carrier's funding input; `-yellowbackcarrierpool` has no semantics and is not implemented.

**A5-b findings (2026-09-14), for A6:** a `pending: true` reply names only `carrierTxid`, so the GUI follows a pending action heuristically through `yed_listtransactions`; a node-side `carrierTxid` on `yed_listtransactions` rows (or `mainTxid` once built) would make it exact — contract + node change, scheduled in A6. `yed_gettxinfo` has no `source`; the GUI derives it. `yed_listattestors` does not mark the wallet's own records; the node's `attest-key-not-held` answers.

**A4 findings applied (2026-09-13):** `iroh-gossip` has no topic discovery, so the `[transport]` table gains `peers` (bootstrap endpoint ids) and `secret_key_file` (stable id); `topic` is `topic_override`; the attestor polls sources every `poll_seconds` and signs only at a due tick, so the price window fills between ticks (§5). **Incident:** the agent's clean-build step ran `cargo clean` against the machine's global shared cargo target directory and removed other projects' build artifacts (≈ 26 GiB, nothing unrecoverable — rebuild time only); the briefing now forbids `cargo clean` outside the crate's own target.

**Golden vector (coordinator, revised 2026-09-13):** the payload version bump alone invalidates
the v2 golden vector (its raw transactions carry version-2 payloads, which v3 reads as
non-Yellowback), so "regenerate once at A1" was not achievable. It is regenerated in the A0
`glue` chunk together with the two regtest flags joining the preimage, and once more at A1 when
`Snapshots` gains its fields. Two regenerations, each with the C++ and the Python model agreeing.

**Status (2026-09-13, revision 1).** Plan only at revision 1; implementation status above. Builds on the delivered v2 (miner-enforced
Yellowback, `docs/plans/yellowback-v2-development-plan.md` revision 6, Phases 0–8 implemented on
`feature/yellowback-sf`) and implements `docs/reference/yellowback-price-attestation.md`
revision 6 ("the proposal") — the second price population, decided by the product owner on
2026-09-13 (proposal §16, D-1..D-5). Work branch: **`feature/yellowback-price-attest`** in the
workspace, `ycash-dd` and `yecwallet-dd`, each cut from `feature/yellowback-sf`. The v2 plan
stays the description of what is on the chain today; **this plan is a delta**, and where it is
silent, v2 rules.

**One-line summary.** Attestors post a CLTV bond once and sign prices off-chain; a mint or claim
carries four to six of those signatures in the scriptSig of a small P2SH *carrier* input, the
enforcing nodes verify them and combine the bond-weighted quantile with the existing pool medians
by `min` (mints) and `max` (claims); no new line in any consensus, mining or policy file of the
node; every new rule is overlay state shared by enforcing miners, exactly as v2's are.

| | changed lines (v2 actual) | v3 budget |
|---|---|---|
| `src/main.cpp` | 11 | **11 — no new line** |
| `src/miner.cpp` | 12 | **12 — no new line** |
| `src/rpc/mining.cpp` | 7 | **7 — no new line** |
| `src/policy/policy.cpp`, `src/script/*`, `src/consensus/*`, `src/primitives/*`, `configure.ac`, `src/wallet/wallet.{h,cpp}` | 0 | **0** |

---

## 0. Revision log

### Revision 3 (2026-09-22) — W17: MINT-10 reads the fast median

The owner's walk hit a second stall: after a +100 % shock the pools' fast and mid medians were at
the new price, the slow one still at the old, and MINT-10 compared the attestors (at the new
price) with `xMint` = the *minimum* of the three windows — a 100 % "disagreement" that would
last a whole slow window: 64 blocks here, ≈ 42 hours on mainnet. Decision W17: the agreement
test reads `pFast(R)`, the current market; MINT-5 keeps pricing collateral at the minimum.
Owner decision D-R-8, §6.2.

### Revision 2 (2026-09-21) — W16: the global-ratio halt keeps the best-backed class open

The owner's first walk of Scenario 1 (`role-based-regtest-plan.md` §8) hit the global-ratio
halt after a 40 % shock and asked the right question: a halt that stops *every* mint leaves the
system unable to recapitalise except by hoping the price recovers. The arithmetic agrees and is
stronger than the objection — every class minimum (300/400/500 %) exceeds the halt floor
(250 %), so any mint the halt forbids would have *raised* the ratio. Decision W16, parameter
`RECAP_RATIO_BPS`, HALT-2 amended in §3.8, `mintableClasses` on `yed_getstats`,
`globalRatioHaltBps`/`recapRatioBps` on `yed_getinfo.params`. Owner decision D-R-3, §6.2.

### Revision 1 (2026-09-13) — first draft

Written from proposal revision 6 after two audits (`docs/reference/yellowback-price-attestation-audit.md`
§1–§6) and the owner's five decisions. Hardened in place by the self-review of §0.1 (S1–S18) and an independent review (R1–R20,
applied in the text; the review's numbering is cited beside each change) before being handed
over.

### 0.1 Self-review findings applied to revision 1

| # | Finding | Applied |
|---|---|---|
| S1 | The proposal's `Attestors` table is keyed by bond outpoint but every rule addresses attestors by `seq`; two lookups per verification and an ambiguous "record" in REG-A1. | `Attestors` keyed by `seq`; a secondary `BondIndex bondOutpoint → seq` for the spend hook (§3.6). |
| S2 | `selected(R, selector)` weighted draw without replacement was under-specified (FEE-W draws one). | The draw is written out (§3.7 *Selection*): `M_SELECT + K_SLACK` rounds, each the FEE-W draw over the remaining pool with `seed_i = SHA256(seed ‖ i)`. |
| S3 | A bundle verified in `AcceptToMemoryPool` for a **mint** is never re-verified in `ConnectBlock` by MP-1 (MP-1 covers vault spends only), so the verified-bundle cache of proposal §8.2 would only ever hold claim bundles. | The cache is filled by both MP-1 and the template filter; `ConnectBlock` verifies uncached bundles and the cost bound is stated for that case (§3.9, §8.2 row). |
| S4 | `yed_addattestation` verified "against the current seated set" — a subscriber that starts before arming would refuse everything. | The pool accepts attestations from any ELIGIBLE or PENDING `seq`; selection at build time decides relevance (§4.5). |
| S5 | Carrier outputs are P2SH to a fresh key, so `IsMine` is false and the wallet's own coin selection would never see them — the upkeep rule had no mechanism. | Superseded by R2/R6: carriers are per-transaction, recorded in `carriers.dat`, never `IsMine`, signed by hand (W7). |
| S6 | The regtest `ATTEST_ARM_MIN = 2` with `M_SELECT = 2`, `K_SLACK = 1` meant a two-attestor set arms and then needs both to sign every mint — every attestor test would be a liveness test. | Regtest `ATTEST_ARM_MIN = 3`, `N_SLOTS = 5`, `M_SELECT = 2`, `K_SLACK = 1`, `BOND_MATURITY = 8`, `ATTEST_ARM_DELAY = 8` (§3.1). |
| S7 | Concurrent regtest sessions were assumed, not specified: two `rpc-tests.py` runs on one machine collide on ports and on the shared `cache/`. | §6.0 items 1–2: `--portseed` per run, one worktree per agent, `--cachedir` per worktree, the devnet's `YELLOWBACK_DEVNET_PORTBASE`. |
| S8 | The Rust agent's toolchain was "modern" with no pin — an unpinned toolchain in a repository whose node pins everything. | `contrib/yellowback/attest/rust-toolchain.toml` pins a stable version; `Cargo.lock` committed; `cargo vendor` **not** used (it never enters `depends`); the `agent` CI job builds it (§5, §6.0 item 6). |
| S9 | Functional tests depended on the Rust agent to produce attestations. | `test_framework/yellowback_attest.py` signs attestations in Python (`CECKey`) and feeds `yed_addattestation`; the agent has its own script (§6.0 item 4, §7). |
| S10 | Phase ordering: the wallet phase needed `yed_registerattestor` to seat attestors, but registration is a node-tier builder used by the framework first. | Registration is built raw in Python (`build_register_tx`) for Phases A1–A2; the RPC arrives in A3 (§6.0 item 4). |
| S18 | The proposal's `bundleHash16` payload commitment detected malleation but converted it into a free collateral-locking grief (R2). | Commitment moved into the carrier redeem script; payload fields removed (§3.3, §3.4). |
| S11 | RED-5's residual output for a `ys1…` claim destination: a Sapling-shaped claim has transparent outputs at fixed indexes (v2 §3.5); the residual output is transparent `P2PKH(ownerPubKey)` and must fit that layout. | §3.5 CLAIM template lists the residual output; the Sapling shape appends it after the fee output and `attestFeeVout`/`feeVout` name their outputs wherever they land. |
| S13 | The mint's selection selector was `ownerPubKey` (FEE-W's), which the minter chooses freely — unlimited grinding of the selected set. | The mint selector is empty (all mints at one `R` share a selection); the claim/notice selector is the vault outpoint (§3.7). |
| S14 | The verified-bundle cache was keyed by `R`; after a reorg at or below `R` the same key would return a stale verdict. | Cache per-attestation signature validity only, keyed by attestation bytes and the cited block hash (§3.9, R3). |
| S15 | The dormancy predicate scanned `DORMANCY_BLOCKS` snapshots per seated attestor per block. | `seatedSince` carried per record; evaluated every `DORMANCY_CHECK` blocks over the `BundleLog` window (§3.7). |
| S16 | An attestor could eject itself by an agent restart signing a second price for one height. | `yed_signattestation` persists what it signed and refuses a conflicting request (§4.5). |
| S17 | Arming was irreversible with no release-level way back — unacceptable for a risk-averse deployment. | `ATTEST_REQUIRED` per parameter set (W15). |
| S20 | `AreInputsStandard` is not "sigops only" for P2SH: `policy.cpp:156` runs `EvalScript` over the scriptSig, so a push over 520 bytes is refused at relay too (`interpreter.cpp:277`); `pubkey.cpp`'s verify context is in an anonymous namespace, not `extern`; Ycash 4.5 has no `Span`; the vectors need six distinct keys because `dup` forbids a repeated `seq`; `yed_revive` needs `<seq> <priceMicroUsd>`; `yed_getnotice` returns `{found: false}`; the contract gained `attest-malformed`, `bundle-malformed`, `bond-spent`. Found by the `a0-crypto` and `a0-docs` agents. | Fixed in §1, §4.2a, §4.5, Appendix A; `attest.cpp` owns a function-local verify context. |
| S19 | Carrier script length was stated as 72 (it is 71); the A0 payload-size list disagreed with §3.3; `CECKey.sign` is non-deterministic so it cannot make vectors; the zero-weight fallback was stated for the initial pool only. Found by the `a0-pyfw` agent. | Fixed in §3.4, §3.7, §6.0 item 4 and the A0 checklist. |
| S12 | The v2 `yellowback_model.py` reproduces snapshots only; bundle statistics live in `TxLog`, which the model does not read. | The model gains `TxLog` bundle fields via `yed_gettxinfo` under `full=True` and the new snapshot fields; the golden vector is regenerated once, in Phase A1, and pinned (§7). |

---

## 1. The decision in one page

1. **What v3 adds.** A second price population. Today `pMint` and `pClaim` are medians of pool
   coinbase quotes — one population, weighted by hashpower. v3 adds bonded **attestors** whose
   signed prices a minter or claimant carries into the transaction; the enforcing nodes compute a
   bond-weighted one-sided quantile over them and combine: `pMint = min(xMint, aMint)`,
   `pClaim = max(xClaim, aClaim)`. Moving the price in the direction that pays now needs a
   hashpower majority *and* a bond-weighted majority of the selected attestors, together.
2. **Tier.** The same tier as v2: overlay state and rules shared by enforcing miners, no consensus
   change, no network upgrade, **no new line in `main.cpp`, `miner.cpp`, `rpc/mining.cpp` or
   `policy.cpp`**. Every v3 rule is evaluated inside the overlay's `ProcessTx`/`ComputeSnapshot`,
   which v2's hooks already call. Block validity stays exactly "ACTIVE-vault spends obey
   RED-1..5" (V3, extended by one rule). A cheaper tier does not exist: this *is* Tier 0 plus the
   v2 soft-fork rule set.
3. **Why the surgical footprint holds.** The bundle rides in the scriptSig of a P2SH input that
   every stock node relays today (`IsStandardTx` ≤ 1,650 push-only bytes; `AreInputsStandard`
   evaluates the scriptSig's pushes, so the 520-byte element cap binds at relay as well as at
   execution, and checks P2SH sigops — proposal §8.1); the attestor's bond is a P2SH CLTV output; registration,
   notices, equivocation proofs and revivals are ≤ 80-byte `OP_RETURN` payloads. Nothing
   Yellowback needs from the node is new; the node needs one more thing from `libsecp256k1` it
   already links (compact ECDSA verify).
4. **Off-chain, but not in the node.** Attestors sign every ten blocks and gossip; the gossip and
   the exchange polling live in `yellowback-attest`, a separate binary under
   `contrib/yellowback/attest/` with its own pinned toolchain. The node holds an in-memory,
   non-consensus *attestation pool* fed by RPC — the mempool's cousin — and builds bundles from
   it. The CI "no sockets" grep over the node stays green.
5. **Arming is automatic** (D-4): five matured bonds, then one day. Until then v3 nodes behave as
   v2. Registration is open from `START_HEIGHT`, so the set forms while the chain runs
   single-source. The two calibration measurements of proposal §16 precede the first mainnet
   registration, not a release.
6. **What can go wrong, bounded.** A captured attestor set can grief (halt minting, force an early
   liquidation at an honest price with the residual returned) but not extract (proposal §10.3).
   Transport failure halts minting, never soundness. A hashpower majority keeps every power it has
   today and gains none. The full list is §8.
7. **Decentralization and risk aversion, applied.** No miner vote over attestors (proposal §5.3);
   no slashing without a network upgrade (§5.1); attestors free beyond the bond, so the seated set
   can include people on home connections (§1 of the proposal); the v2 medians untouched
   (proposal §7.1); every new parameter versioned by start height and sunset like v2's (K10, L8);
   every new field reproduced by the independent Python model before it is trusted (N23).

---

## 2. Decision record

Numbered **W1–W14** (v2 used V/K/L/M/N/P). Each names the proposal section it implements and the
options rejected.

### W1. Delta plan, not a rewrite
v2 remains the normative description of everything it covers. This plan lists *changes*: new
rules, changed rules, new tables, new RPCs, new tests. A reader needs both. Rejected: a merged
v3 document (a 5,000-line plan nobody re-reads).

### W2. Bundle carrier: scriptSig of a P2SH carrier input whose redeem script commits to the bundle (proposal §8.1, D-1; R2)
Options: (a) oversized `OP_RETURN` with a relay carve-out · (b) scriptSig carrier · (c) both.
**Decision: (b) now, (a)'s layout specified as the target behind `BUNDLE_CARRIER`** (the owner's
D-1). The verifier is written once over an abstract "bundle bytes + where they came from"; the
`OP_RETURN` reader is a second extractor behind the parameter, tested but not built by the
wallet until the parameter says so. No `policy.cpp` change in either case: (a) would be an
*upstream* change, proposed separately.

### W3. Signatures: compact ECDSA over the attestation message (proposal §4)
`secp256k1_ecdsa_verify` with `secp256k1_ecdsa_signature_parse_compact`, low-S enforced by the
verifier (a high-S signature is invalid, never normalised — two encodings of one signature would
otherwise be two bundle hashes). Rejected: Schnorr (`configure.ac` change), BLS (new crypto).

### W4. Attestors are addressed by `seq` (S1)
`Attestors seq → record`; `BondIndex bondOutpoint → seq` so IN-2's spend scan can mark a bond
spent in `O(1)`. `seq` is `u16`, assigned at registration in block order; 65,535 registrations at
20,000 YEC each is not a bound anyone reaches.

### W5. The attestation pool is not state (proposal §13)
In-memory, per node, refilled by the subscriber; never in the state hash, never read by a rule.
`yed_addattestation` verifies signature and freshness against the tip and keeps the last
`⌈ATTEST_MAX_AGE / k⌉ + 1 = 3` attestations per `seq` (R14: an attestor's node may be a block
ahead of the minter's, so its newest attestation can cite `> R`; `BuildBundle` takes, per `seq`,
the newest with `citedHeight ≤ R`). Rejected: persisting it (a restart is a refill; persistence adds a file format for no
rule).

### W6. Bundles are built by the node, not the wallet GUI (proposal §13)
`yed_mint`, `yed_claim`, `yed_claimnotice` call `BuildBundle(R, selector)` over the pool. YecWallet
never sees attestation bytes except to display them. Rejected: GUI-side assembly (two
implementations of selection).

### W7. Carriers are per-transaction and commit to their bundle (R2, R6)
`carrierScript(pk, h) = OP_SWAP OP_SHA256 <h> OP_EQUALVERIFY <pk> OP_CHECKSIG`, `h =
SHA256(bundle)`, `pk` a fresh keypool key. Created by a carrier funding transaction immediately
before the transaction that spends it (§3.5). The wallet's Yellowback layer records its
outstanding carriers `{outpoint, R, selector, bundle, pk}` in `<datadir>/yellowback/carriers.dat`
(the same file family as the signing guard, S16) and in memory; a carrier is *not* `IsMine`
(`Solver` calls the script non-standard, `ismine.cpp:80-90`), is signed by hand like the vault
input, and is never seen by `AvailableCoins`. If the record is lost, `CARRIER_VALUE` (10,000 zat)
is orphaned — accepted. Rejected: a reusable generic carrier (`OP_DROP` only) — malleable, see
R2; `AddCScript` ownership — the script is non-standard so `IsMine` stays `NO`, and it would write
to `wallet.dat`.

### W8. Verification order and a verified-bundle cache (proposal §8.2, S3)
`VerifyBundle` runs cheapest-first and returns the first failure; `VerifyCompactSig` consults an LRU keyed by
`SHA256(attestation ‖ blockHash(citedHeight))` that MP-1, the template filter and `ConnectBlock`
fill — per attestation, context-free, so no reorg or selector can stale it. `ConnectBlock` on a block
whose bundles it never saw verifies them all — bounded at `6 · (MAX_BLOCK_SIZE / ≈ 600 B) ≈
20,000` signature checks (≈ 1–2 s) once per block on enforcing nodes only, and only if every
transaction also paid `FEE_MIN` to a pool (R15); the A6 measurement uses *valid* bundles.

### W9. Selection is FEE-W repeated (proposal §8.4, S2)
Round `i ∈ [0, M_SELECT + K_SLACK)`: `seed_i = SHA256(blockHash(R) ‖ selector ‖ "S" ‖ i)` as a
little-endian `uint64`, `pick = seed_i mod Σ weight` over the remaining pool, take the first
cumulative weight past `pick`, remove it. Deterministic, `O(N_SLOTS²)`, reuses the FEE-W code.

### W10. Emergency persistence is a `Notices` record (proposal §10.3)
One record per vault, never replaced while within `EMERGENCY_NOTICE_TTL`, deleted when the vault
leaves ACTIVE. Rejected: a per-vault run counter in every snapshot (state per vault per height).

### W11. The pin tests read `BundleLog` and prior snapshots only (proposal §10.1)
`BundleLog` is one row per height that carried at least one verified bundle; never pruned; in the
state hash. The tests run before this height's medians so nothing is circular.

### W12. Dormancy needs selection evidence (proposal §12)
`BundleLog.selectedSeqs[]` is the union of `selected(R, selector)` over that height's bundles; a
seated attestor selected `DORMANCY_MIN_BUNDLES` times in the window and present in none is
DORMANT. Revival is `ATTESTOR_REVIVE`, an 78-byte `OP_RETURN` with one attestation.

### W13. Agents in Rust, tests in Python (S8, S9)
`yellowback-attest` (attest and subscribe modes) is Rust with `iroh-gossip`, pinned by
`rust-toolchain.toml`, built by its own CI job, never by `depends`. The functional tests sign
attestations in Python and never start the agent; `yellowback_attest_agent.py` is the one script
that does, and it is nightly. A `dir://` transport (a shared directory) replaces gossip in tests
and the devnet so neither needs a relay.

### W15. A disarm path exists (risk aversion)
Arming never reverses by itself (ARM-2), but a release **can** switch the layer off: a parameter
set with `ATTEST_REQUIRED = false` from its start height makes PRICE-2 read the cross-section
only and every bundle-reading rule vacuous — v2 behaviour — while registrations, seating and
the tables keep being maintained so a later set can switch back without a cold start. Same
mechanism as every parameter change (K10, L8): a start height above every validated height,
inside the previous sunset. Tested: `attest_required_false_reads_x_only`. Rejected: an
operator flag (a per-node switch over an enforcer-shared rule would fork the enforcing set).

### W17. MINT-10 compares the attestors with the market, not with the conservative minimum (owner decision D-R-8, 2026-09-22)
MINT-10 exists to refuse a mint when pools and attestors disagree, because disagreement is what
an attack on either population looks like. As written it compared `aMint` with `xMint(R)`, the
**minimum** of the fast, mid and slow pool medians — the figure MINT-5 sizes collateral at, and
one that lags a rally by a whole slow window on purpose. So an honest +100 % move produced a
"disagreement" of 100 % for 2,016 blocks on mainnet, during which nothing could be minted; "if
this becomes the global economy we can't have a day and a half pause" (the owner). **Amended:**
MINT-10 reads `pFast(R)`: `|pFast(R) − aMint| · 10⁴ ≤ DIVERGE_BPS_ATTEST · min(pFast(R), aMint)`.
The attestors now have to agree with what the pools say the market is *now*, which is the
comparison the rule meant; a rally passes as soon as the fast window fills (8 blocks on regtest,
96 on mainnet). MINT-5 is untouched: collateral is still sized at `pMint = min(xMint, aMint)`,
the lagging minimum, so a mint into a spike posts the larger collateral. A genuine pool/attestor
disagreement is still caught, since it shows in the fast median too. `pFast` is defined whenever
`xMint` is (PRICE-1 needs all three windows). `yed_estimatecollateral.divergenceBps` reads the
same pair. Tests: `mint10_reads_the_fast_median_so_a_rally_mints`, the rally case in
`yellowback_attest_wallet.py`; the existing steady-price cases are unchanged (fast = minimum).

### W16. The global-ratio halt stops leverage, not recapitalisation (owner decision D-R-3, 2026-09-21)
HALT-2 as the proposal wrote it (§5.6: "minting halts until it recovers") stops every mint
while the aggregate ratio is below `GLOBAL_RATIO_HALT_BPS`. Its stated purpose is to bound
total exposure; it never claimed a new mint could lower the ratio, and none can: a mint locks
exactly its class minimum, every class minimum exceeds the halt floor, and adding a position
above a weighted average raises the average. So the rule forbade exactly the transactions that
repair the condition, and left price recovery and liquidations as the only exits — a system
that "sits there stagnant", in the owner's words. **Amended:** under `GLOBAL_RATIO` a MINT is
accepted iff `minRatioBps(class, S) ≥ RECAP_RATIO_BPS` (50,000 on every network: twice the halt
floor, so on regtest and mainnet alike only class A, 500 %, mints through a halt; at a sigma
multiplier above 1.25× class B qualifies too, because the floor is judged on the ratio the mint
actually locks, not the class label). The halt bit itself is unchanged and still drives
`mintingAllowed`, the banner and `check`; `yed_getstats.mintableClasses` says what can mint
now. Rejected: dropping HALT-2's effect on mints entirely (every class would qualify; the halt
would bound nothing) and 1.5× (class B, 90–365-day locks, entering during stress). Tests:
`mint4_divergence_and_global_ratio`, `recap_floor_is_the_class_minimum_with_sigma`,
`yellowback_void_mint.py` (a class A mint through the halt raises the ratio; class C stays VOID).

### W14. Payload version 3, `rpcversion` 3
One release; a v2 node ignores v3 payloads (V23). The wallet refuses an `rpcversion` mismatch as
today; `RPC_VERSION = 3` lands in YecWallet's first v3 commit.

---

## 3. Protocol delta (normative; v2 §3 where not stated)

### 3.1 Constants and parameters (added or changed)

| Name | Mainnet / testnet | Regtest | Notes |
|---|---|---|---|
| `PAYLOAD_VERSION` | 3 | 3 | W14 |
| `ATTEST_ARM_MIN` / `ATTEST_ARM_DELAY` | 5 / 1,152 | 3 / 8 (`-yellowbackattestarmmin`, 0 = never arms) | ARM-1/2; D-4 |
| `ATTEST_REQUIRED` | `true` | `true` | W15: the disarm switch of a later parameter set; `false` ⇒ PRICE-2 reads `x` only, bundles ignored, whatever `Attest.status` says |
| `BUNDLE_CARRIER` | `SCRIPTSIG` | `SCRIPTSIG` (`-yellowbackbundlecarrier scriptsig\|opreturn\|either`) | W2 |
| `N_SLOTS` | 9 | 5 | |
| `M_SELECT` / `K_SLACK` / `BUNDLE_MAX` | 4 / 2 / 6 | 2 / 1 / 6 | `BUNDLE_MAX = 6` from the 520-byte push |
| `Q_LOW_BPS` / `Q_HIGH_BPS` | 3,333 / 6,667 | same | |
| `ATTEST_MAX_AGE` | 20 (= 2·k) | 8 (k = 4 on regtest) | R4: at most two signed prices per attestor fall in a bundle's window |
| `PIN_WINDOW` / `PIN_DELTA_BPS` / `PIN_MIN_TAGS` / `PIN_MIN_BUNDLES` | 288 / 500 / 3 / 2 | 16 / 500 / 2 / 2 | PIN-1/2 |
| `DIVERGE_BPS_ATTEST` | 1,500 | same | MINT-10 |
| `EMERGENCY_RATIO_BPS` / `EMERGENCY_PERSIST` / `EMERGENCY_NOTICE_TTL` | 10,500 / 48 / 1,152 | 10,500 / 4 / 64 | NOT-1, RED-4(b) |
| `RESIDUAL_MIN_ZAT` | 100,000 | same | RED-5 |
| `RECAP_RATIO_BPS` | 50,000 (2 × `GLOBAL_RATIO_HALT_BPS`) | same | HALT-2 (amended, W16): the class minimum a mint needs to be accepted during a global-ratio halt |
| `ATTEST_FEE_BPS` | 2,500 | same | AFEE-1; D-3 |
| `BOND_MIN` | 20,000 YEC | 10 YEC | |
| `BOND_MIN_LOCK` / `BOND_MATURITY` | 420,480 / 16,128 | 200 / 8 | |
| `AGE_CAP` / `FOUNDING_WINDOW` | 207,360 / 8,064 | 64 / 16 | |
| `DORMANCY_BLOCKS` / `DORMANCY_MIN_BUNDLES` / `DORMANCY_CHECK` | 16,128 / 20 / 48 | 16 / 2 / 4 | dormancy evaluated every `DORMANCY_CHECK` blocks (S15) |
| `CARRIER_VALUE` | 10,000 zat | same | **wallet policy** |
| `k` | 10 | 4 | **agent policy**: signing interval in blocks; `ATTEST_MAX_AGE = 2·k` |
| `WALLET_CONFIRMATIONS` | 6 | 1 | **wallet policy** |
| `MAX_PAYLOAD` | 80 | 80 | unchanged |

Every row not marked policy is consensus-shaped among enforcing miners and versioned by start
height and sunset (v2 K10, L8). The two regtest overrides join the state-hash preimage with v2's
four (M13). No mainnet value is read from configuration.

### 3.2 The coinbase tag — unchanged.

### 3.3 Payload encoding (version 3)

Header `"YB" ‖ 0x03 ‖ type`. A v3 node treats version 1 and 2 payloads as non-Yellowback (V23).

| Type | Body | Size |
|---|---|---|
| `0x01` MINT | `termClass u8, cents u32, lockHeight u32, refHeight u32, ownerPubKey 33, feeVout u8, attestFeeVout u8` | 52 |
| `0x02` TRANSFER | unchanged | 5 + 5·count, count ≤ 15 |
| `0x03` REDEEM | `refHeight u32, feeVout u8, attestFeeVout u8, count u8, count × (vout u8, cents u32)` | 11 + 5·count, count ≤ 13 |
| `0x05` ATTESTOR_REGISTER | `attestorPubKey 33, bondPubKey 33, bondLocktime u32, flags u8` | 75 |
| `0x06` CLAIM_NOTICE | `vaultTxid 32, vaultVout u8, refHeight u32` | 41 |
| `0x07` EQUIVOCATION | (empty; the carrier holds the two attestations) | 4 |
| `0x08` ATTESTOR_REVIVE | `seq u16, priceMicroUsd u32, citedHeight u32, sig 64` | 78 |

`attestFeeVout = 0xFF` means none. The bundle is committed by the carrier's redeem script
(§3.4), not by the payload, so MINT and REDEEM grow by one byte only. Under the `OP_RETURN`
carrier mode (W2, unshipped) the payload reader admits a body of up to 520 bytes for MINT,
REDEEM and CLAIM_NOTICE, the bundle being the tail after the fixed fields (R8); under
`SCRIPTSIG` the v2 `4..80` shape rule stands. `vaultTxid ‖ vaultVout` is the payload form of a
vault outpoint; **the `selector` of §3.7 is always the 36-byte serialised `COutPoint`** (R13).

### 3.4 Scripts

Added beside the vault script:

```
carrierScript(pk, h) = OP_SWAP OP_SHA256 <h 32> OP_EQUALVERIFY <pk 33> OP_CHECKSIG   (71 bytes; h = SHA256(bundle))
carrier output       = P2SH(HASH160(carrierScript)), nValue = CARRIER_VALUE
carrier scriptSig    = <bundle ≤ 520> <sig> <carrierScript>                          (push-only, MINIMALDATA)
bondScript(k, L)   = <L> OP_CHECKLOCKTIMEVERIFY OP_DROP <k 33> OP_CHECKSIG      (v2 vault owner path without the claim branch)
bond output        = P2SH(HASH160(bondScript)), nValue ≥ BOND_MIN
```

**Why the hash is in the redeem script (R2).** A scriptSig push is covered by no signature; a
bare `OP_DROP` carrier would let any relay node substitute a different bundle, void the mint and
lock the collateral until `lockHeight` — a free grief nobody but the owner can cause in v2. The
redeem script *is* covered (it is the `scriptCode` of the input's sighash) and is pinned by the
P2SH hash in the funding output, so the bundle is committed before the carrier exists.
Consequence: **a carrier is created per transaction, after the bundle is chosen** (§3.5, §4.6);
there is no reusable carrier and no `bundleHash16` in the payload. Execution: `[bundle, sig]` →
`OP_SWAP` → `[sig, bundle]` → `OP_SHA256` → `[sig, h']` → push `h`, `OP_EQUALVERIFY` → `[sig]` →
`OP_CHECKSIG`. **The carrier is identified by shape:** a scriptSig of exactly three pushes whose
third is a 71-byte script matching `carrierScript(·, ·)` (1+1+33+1+34+1; matched structurally, not by length alone). A REDEEM's `vin[0]` (the vault) is
never considered. Two carriers in one transaction ⇒ BUNDLE-1 false. Both scripts are verified by
consensus under `P2SH | CLTV` exactly as the vault is (`ref/ycash/src/main.cpp:2931`); unit
tests run every template through `VerifyScript` with `STANDARD_SCRIPT_VERIFY_FLAGS` and through
`IsStandardTx`/`AreInputsStandard` (v2 §7 `yellowback_script_tests.cpp`).

### 3.5 Transaction templates (deltas)

**Carrier step (R2).** Every bundle-bearing transaction is preceded by its **carrier funding
transaction**: the builder fixes `R = indexTip − REF_LAG`, builds the bundle for `(R, selector)`,
creates `P2SH(carrierScript(freshKey, SHA256(bundle)))` of `CARRIER_VALUE` from any confirmed YEC
(or from `ys1…`), broadcasts it, and waits **one confirmation** (v2's confirmed-inputs rule,
§4.6; both transactions carry `nExpiryHeight = R + REF_WINDOW`, so the pair either lands inside
the window or expires together). The main transaction then spends it. `yed_mint`/`yed_claim`/
`yed_claimnotice` do both steps in one call and return after the second broadcast; the GUI shows
"preparing price proof (1 block)". The `R` chosen at the carrier step is the `refHeight` of the
main transaction, so a carrier is good for `REF_WINDOW − 1` blocks after its own confirmation.

**MINT** (`yed_mint <cents> <lockBlocks> [from] [bundleHex]`): as v2, plus `vin[last]` = the
carrier input (confirmed, own) and, when `A ≠ ∅`, an output `P2PKH(bondPubKey(attestPayee))` of
`attestFeeZat` named by `attestFeeVout` (after the pool fee output; `vout[4]` when both fees are
present, change after). The Sapling-funded shape gains the carrier as its only transparent input.

**REDEEM, owner path**: unchanged in shape; `attestFeeVout = 0xFF` (the owner path reads no price: RED-4 is vacuous on it and RED-5 applies to the claim path only).
**No carrier input, no bundle** — RED-1's bundle clause applies to the claim path only.

**CLAIM** (`yed_claim <vaultTxid> [to] [bundleHex]`): as v2 plus the carrier input (never
`vin[0]`), the attestor fee output, and — when `residualZat ≥ RESIDUAL_MIN_ZAT` — an output
`P2PKH(ownerPubKey)` of at least `residualZat` (RED-5). Sapling shape: YED change, payload, pool
fee, attestor fee, residual — all transparent, in that order; the two `*Vout` fields name their
outputs.

**CLAIM_NOTICE** (`yed_claimnotice <vaultTxid>`): confirmed YEC inputs incl. one carrier; outputs:
the payload, change. No vault input, no fee outputs (a notice pays no enforcement fee — it
creates no YED and spends no vault).

**ATTESTOR_REGISTER** (`yed_registerattestor <bondYec> <lockBlocks> [flags]`): `vout[0]` the bond,
`vout[1]` the payload, change. `attestorPubKey` and `bondPubKey` are two fresh keypool keys. The
bond script is `TX_NONSTANDARD` to `Solver`, so the bond is **not** `IsMine` (R6); the wallet
finds its bonds through `Attestors` (records whose `bondPubKey` it holds) exactly as it finds its
vaults through `Vaults`, and `yed_withdrawbond` signs the input by hand as the vault owner path
does. Nothing is written to `wallet.dat`.

**EQUIVOCATION** (`yed_reportequivocation <attestationHexA> <attestationHexB>`): a carrier
(carrier step first) whose bundle is exactly the two attestations; payload `0x07`; change.

**ATTESTOR_REVIVE** (`yed_revive`): the attestor node signs one attestation for `citedHeight = tip − REF_LAG`
with the hot key it holds; payload `0x08`; funded from any confirmed YEC.

### 3.6 State (added)

```
Attestors    seq → { attestorPubKey, bondPubKey, bondOutpoint, bondZat, bondLocktime, flags,
                     registerHeight, status ∈ {PENDING, ELIGIBLE, DORMANT, EJECTED, WITHDRAWN},
                     statusHeight, bondSpentHeight, seatedSince }
BondIndex    bondOutpoint → seq
AttestorSeq  { next u16 }
Attest       { status ∈ {UNARMED, TRIGGERED, ARMED}, triggerHeight, armHeight }      (carried; copied into Snapshots)
BundleLog    height → { aMint, aClaim, selectedSeqs[], seqs[], prices[] }             (one row per height with ≥ 1 verified bundle; R12:
                                                                                        aMint/aClaim = lowerMedian over that height's MINT, REDEEM
                                                                                        and CLAIM_NOTICE bundles for which BUNDLE-1 held — whatever the
                                                                                        transaction's final verdict; EQUIVOCATION bundles excluded;
                                                                                        selectedSeqs/seqs/prices are unions)
Notices      vaultOutpoint → { height, refHeight, pEmerg }                             (deleted when the vault leaves ACTIVE)
Snapshots    + { attest, seated[], pinnedKeys[], pinnedSeqs[] }; pMint → xMint, pClaim → xClaim
TxLog        + { aMint, aClaim, bundleSeqs[], attestFeeZat, attestPayee, residualZat, notice }   (history; not hashed)
```

`Params` (the `P` record) gains `attestArmMin u32 ‖ bundleCarrier u8` after v2's four fields
(scriptsig 0, opreturn 1, either 2) — landed in A0 with the golden vector regenerated. Key
prefixes: `A<u16 seq>` Attestors, `B<outpoint>` BondIndex, `N` AttestorSeq, `M` Attest,
`W<u32 height>` BundleLog, `E<outpoint>` Notices (`T` and `L` were taken by Tip and TxLog). `SCHEMA_VERSION = 3`: a v2 index directory is
rebuilt from the chain at first start (`SyncToChain`'s wipe-and-rebuild path), as v2 did for v1.

**State hash order** (after v2's `Params`): every `Attestors` record by `seq`; `AttestorSeq`;
`Attest`; every `BundleLog` row by height; every `Notices` record by outpoint. `BondIndex` is
derived and excluded. Undefined `aMint`/`aClaim` in `BundleLog` never occur (a row exists only
for a verified bundle). `selected`, `pinned` arrays are sorted ascending.

### 3.7 Derived quantities (added)

**Bond weight.** `weight(seq, H) = bondZat · clamp(H − ageOrigin, 0, AGE_CAP)` in `arith_uint256`,
`ageOrigin = Attest.triggerHeight` if `Attest.status ≠ UNARMED` and `registerHeight ≤ triggerHeight
+ FOUNDING_WINDOW`, else `registerHeight`.

**Seating.** `seated(H)` = the `N_SLOTS` ELIGIBLE `seq` with greatest `weight(seq, H)`, ties by
`seq` ascending.

**Selection (W9).** `selector` is the **36-byte serialised `COutPoint` of the vault for REDEEM
and CLAIM_NOTICE and empty for MINT** (S13: the v2 FEE-W selector for a mint is `ownerPubKey`,
which the minter picks freely — a free grind; every mint at one `R` therefore shares one
selection). `pool = Snapshots[R].seated[] \ Snapshots[R].pinnedSeqs[]` — **the stored arrays,
never a recomputation** (R11: a status change after `R` must not change a bundle's verdict);
`weight(s, R)` reads only immutable record fields (`bondZat`, `registerHeight`) and
`Attest.triggerHeight`, which never regresses. For `i` in `0 .. M_SELECT + K_SLACK − 1` while
`pool ≠ ∅`: `seed_i = UintToArith256(SHA256(blockHash(R) ‖ selector ‖ "S" ‖ u8 i))`, `pick = seed_i
mod Σ_{s∈pool} weight(s, R)` (256-bit throughout, R10: weights reach `4·10¹⁷` per bond at
`AGE_CAP`, so a 64-bit `pick` would never reach the upper part of the cumulative range), `chosen` = first `s` in ascending `seq` order whose cumulative
weight exceeds `pick`; append; remove from `pool`. If `Σ weight = 0` over the remaining pool at any
round (every remaining candidate at zero age — impossible after arming since `armHeight >
triggerHeight`, stated for totality) the remaining draws are the lowest `seq` first. The seed is
read as `UintToArith256(hash)`, i.e. the 32 digest bytes **little-endian**; the Python model does
`int.from_bytes(digest, 'little')`.

**Bundle statistic.** Over the verified bundle's attestations `C` (BUNDLE-1 guarantees they are
from `selected`, unique, fresh, signed): if `|C| < M_SELECT` undefined; else sort by price
ascending (ties by `seq`), `total = Σ weight`, `aMint` = price at which cumulative weight first
`≥ ⌈Q_LOW_BPS · total / 10⁴⌉`, `aClaim` likewise with `Q_HIGH_BPS`.

**PRICE-2 (revised).** For a transaction with `refHeight = R` and bundle statistic `(aMint,
aClaim)`: if `Snapshots[R].attest.status ≠ ARMED` **or the set in force at `R` has
`ATTEST_REQUIRED = false`** (W15; "ARMED" below always means both): `pMint = xMint(R)`, `pClaim = xClaim(R)`. Else
`pMint = min(xMint(R), aMint)`, `pClaim = max(xClaim(R), aClaim)`, `pEmerg = min(xClaim(R),
aClaim)`, each undefined if any input is. `xMint`/`xClaim` are v2's `pMint`/`pClaim` (medians
over quote tags **of keys not in `pinnedKeys(R)`**).

**Eligible payees.** `E(R)` excludes keys in `pinnedKeys(R)`. **Attestor payees.** `A` = the `seq`
values of `C`. `attestFeeZat = feeZat(collateralZat) · ATTEST_FEE_BPS / 10⁴`.

**Residual.** `marginBps = CLAIM_THRESHOLD_BPS` when RED-4 holds by clause (a), `10⁴` when it
holds by clause (b) only (R1: a claim the pools do not confirm is a forced early liquidation and
pays *exactly* the debt at the adverse price — no margin, so a captured attestor set has nothing
to collect). `claimantMaxZat = ⌈mintedCents · marginBps · COIN / pClaim⌉` (units: `cents/100`
dollars × `bps/10⁴` ÷ `pClaim/10⁶` $/YEC × `COIN` — the powers of ten cancel to this form, R5;
check: $100 at 110 % and 18,333 µUSD ⇒ `10⁴ · 11,000 · 10⁸ / 18,333 ≈ 6.0·10¹¹` zat = 6,000 YEC,
v2's worked example), `arith_uint256`, `> MAX_MONEY` ⇒ residual 0;
`residualZat = max(0, collateralZat − claimantMaxZat)`. The claimant's fee outputs come out of
its own share. `TxLog.claimPath ∈ {a, b}` records which clause opened the claim.

**Pin tests** (at SNAP for `H`, before medians; `W = (H − 1 − PIN_WINDOW, H − 1]`):
PIN-1 armed iff `|{h ∈ W : BundleLog[h]}| ≥ PIN_MIN_BUNDLES` and `(aHi − aLo) · 10⁴ > PIN_DELTA_BPS
· aLo` over `BundleLog[h].aMint`; when armed `k ∈ pinnedKeys(H)` iff `k` has `≥ PIN_MIN_TAGS`
quote tags in `W`, all one price. PIN-2 armed iff `Snapshots[H − 1].xMint` and `Snapshots[H − 1 −
PIN_WINDOW].xMint` both defined and differ by more than `PIN_DELTA_BPS` of the smaller; `seq ∈
pinnedSeqs(H)` iff it appears in `≥ PIN_MIN_TAGS` rows of `BundleLog` in `W`, all at one price.

**Dormancy predicate** (SNAP, **only at heights with `H mod DORMANCY_CHECK = 0`**, S15): `seq`
DORMANT iff ELIGIBLE, `seatedSince(seq) ≤ H − DORMANCY_BLOCKS` (i.e. `seq ∈ Snapshots[h].seated`
for the whole window, R11) (`seatedSince` is a carried field
of the record: set when the attestor enters `seated`, cleared when it leaves — so "seated for
the whole window" is one comparison, not a scan), `|{h ∈ (H − DORMANCY_BLOCKS, H] : seq ∈
BundleLog[h].selectedSeqs}| ≥ DORMANCY_MIN_BUNDLES`, and `seq ∉ BundleLog[h].seqs` for every such
`h`. The `BundleLog` scan is one pass over the window's rows every `DORMANCY_CHECK` blocks.

### 3.8 Rules (added or changed)

Totality as v2. New identifiers: **ARM-1/2, REG-A1, BUNDLE-1, MINT-9, MINT-10, NOT-1, EQV-1,
REV-1, PIN-1/2, AFEE-0/1, RED-5**; changed: **RED-1, RED-3, RED-4, MINT-8, PRICE-2, SNAP, IN-2,
HALT-2 / MINT-4** (revision 2, W16).

- **HALT-2 / MINT-4 (amended, W16).** The `GLOBAL_RATIO` bit of `haltMask` is set exactly as
  in v2 (`supplyCents > 0`, `pMint` defined, `globalRatioBps < GLOBAL_RATIO_HALT_BPS`). MINT-4
  reads it differently: with `GLOBAL_RATIO` set, a MINT whose `minRatioBps(class, S) <
  RECAP_RATIO_BPS` has verdict `mint-halted-global-ratio` (before HALT-3's check, as before);
  one at or above the floor passes this clause and is judged by the remaining halts as if the bit
  were clear. The other bits keep their v2 effect: any of them set is still a halted mint.
  MINTPOL-1 mirrors it (`mintpol-global-ratio` names the classes that would go through).

- **IN-2 (amended).** A spend of an outpoint in `BondIndex` sets that attestor `WITHDRAWN`
  (`bondSpentHeight = H`) unless EJECTED (then only `bondSpentHeight`); the record stays. When an
  ACTIVE vault closes (either path, or an unpoliced spend), `Notices[vault]` is deleted; UNDO
  restores it.
- **REG-A1** — proposal §5.2 verbatim, with `bondOutpoint = txid:0`. On success `seq =
  AttestorSeq.next++`. Duplicate `attestorPubKey` against any record not WITHDRAWN ⇒ false.
- **BUNDLE-1(tx, R, selector)** — proposal §8.2, with W2's extractor: under `SCRIPTSIG`, exactly
  one carrier-shaped input (never `vin[0]` of a REDEEM) and `SHA256(bundle)` equals the hash in
  its redeem script (consensus already enforced this when the input was verified; the overlay
  re-checks so a verdict never depends on script execution having run); under `OP_RETURN`, the
  bundle is the payload tail; under `EITHER`, exactly one of the two. Well-formed; `M_SELECT ≤ count ≤ BUNDLE_MAX`; each `seq ∈
  selected(R, selector)`, unique, `citedHeight ∈ (R − ATTEST_MAX_AGE, R]`, `≥ START_HEIGHT`,
  price in `[PRICE_MIN, PRICE_MAX]`, compact low-S ECDSA over `SHA256("YBATTEST1" ‖ seq ‖ price ‖
  citedHeight ‖ blockHash(citedHeight))` under `attestorPubKey(seq)` — integers fixed-width
  little-endian, the block hash as the 32 internal bytes of `uint256` (`begin()..end()`, not the
  displayed reversed hex), the prefix as 9 ASCII bytes with no length byte (R13; the Python
  and Rust signers are tested against the same vectors). Order of checks: shape →
  hash → count → membership/uniqueness → freshness/range → signatures (W8, each signature
  through the per-attestation cache).
- **Evaluation order (R15, when ARMED only — unarmed keeps v2's exact order):** MINT-1..4, MINT-6..8 first — the payload, the vault output, the
  activation snapshot, the cap and the **pool fee of at least `FEE_MIN` (0.5 YEC)** — then MINT-9,
  then MINT-5 (which needs `pMint`) and MINT-10. Bundle signatures are therefore verified only
  for a transaction that has already paid a real fee to a pool and locked a real P2SH output, so
  bundle-verification spam costs the attacker at least `FEE_MIN` per transaction.
- **MINT-9** if `Snapshots[R].attest.status == ARMED`: BUNDLE-1 with the empty selector (W9),
  and `aMint` defined. **MINT-10** (amended, W17) if ARMED: `|pFast(R) − aMint| · 10⁴ ≤
  DIVERGE_BPS_ATTEST · min(pFast(R), aMint)` — the attestors against the pools' *fast* median,
  the current market, not the lagging minimum. MINT-5 reads `pMint` of PRICE-2 (revised), still
  `min(xMint, aMint)`. Failure ⇒ VOID with
  `voidReason` naming the rule.
- **MINT-8 / RED-3 (amended)** add: if ARMED and `A ≠ ∅`: `attestFeeVout ≠ 0xFF`, `<
  vout.size()`, `vout[attestFeeVout]` is `P2PKH(bondPubKey(s))` for some `s ∈ A`, `nValue ≥
  attestFeeZat`, and `attestFeeVout ∉ {0, 1, opReturnIndex, feeVout} ∪ assigned vouts`.
  (**AFEE-0**: not ARMED or `A = ∅` ⇒ the clause is vacuous; **AFEE-1** is the clause.)
- **RED-1 (amended)** claim path only, if ARMED: BUNDLE-1 with `selector = vaultOutpoint` and
  `aClaim` defined. Owner path: unchanged (no bundle read).
- **RED-4 (amended)** claim path: (a) underwater at `Snapshots[R]` under `pClaim` of PRICE-2
  (revised), **or** (b) `Notices[vault]` exists with `EMERGENCY_PERSIST ≤ R − notice.refHeight ≤
  EMERGENCY_NOTICE_TTL` and `collateralZat · pEmerg < mintedCents · EMERGENCY_RATIO_BPS · COIN`
  with this transaction's `pEmerg`. Before arming, (b) is false.
- **RED-5** claim path: with `residualZat` of §3.7: if `≥ RESIDUAL_MIN_ZAT`, some `vout[j]`, `j ∉
  {opReturnIndex, feeVout, attestFeeVout} ∪ assigned`, is `P2PKH(ownerPubKey)` with `nValue ≥
  residualZat`. `pClaim` undefined ⇒ false. Owner path: vacuous.
- **NOT-1** payload CLAIM_NOTICE: vault ACTIVE; ARMED at `R`; `H − REF_WINDOW ≤ R ≤ H − 1`;
  BUNDLE-1 with `selector = vaultOutpoint`; `pEmerg` defined and the inequality holds; no
  `Notices[vault]` with `H − notice.height ≤ EMERGENCY_NOTICE_TTL` ⇒ write the record. Else
  non-Yellowback (no `TxLog` unless it touched tokens).
- **EQV-1** payload EQUIVOCATION: one carrier whose bundle has `count = 2`, same `seq` (any
  status but WITHDRAWN/EJECTED), same `citedHeight ≥ START_HEIGHT` with a block hash in the
  index, different prices, both signatures valid ⇒ `EJECTED`, `statusHeight = H`.
- **REV-1** payload ATTESTOR_REVIVE: record DORMANT; `citedHeight ∈ (H − ATTEST_MAX_AGE, H − 1]`;
  signature valid ⇒ `ELIGIBLE`.
- **ARM-1/2** — proposal §6.4 verbatim, in SNAP after the maturity pass.
- **PIN-1/2** — §3.7, in SNAP before medians.
- **SNAP (revised order):** judgement (REG-4) → **activation (ACT-1..6, unchanged)** → maturity (`PENDING → ELIGIBLE` at `registerHeight +
  BOND_MATURITY`) → ARM-1/2 → pin tests → seating → medians (excluding pinned keys) → σ →
  issuance → halts → dormancy → write `Snapshots[H]`. `Attest`, `Attestors` status changes,
  `BundleLog` and `Notices` are UNDO-covered like every table.
- **HALT-1** now reads `xMint` (the cross-section); the attestation side has no halt bit because it
  has no per-height value — a mint with no usable bundle is not built (MINT-9 fails on the
  wallet's dry run first).

### 3.9 Block validity, template and mempool rules (deltas)

- **BLK-1** unchanged in kind: a block is Yellowback-invalid iff enforcement is on and it contains
  an ACTIVE-vault spend failing **RED-1..5**. Nothing else in v3 invalidates a block.
- **TPL-2 (strict)** additionally skips a MINT failing MINT-9/10, a claim failing RED-5, and a
  CLAIM_NOTICE failing NOT-1 (a notice that would register nothing wastes block space, and a
  strict pool need not carry it).
- **MP-1** unchanged in scope (vault spends only); its RED-1 evaluation now verifies the claim
  bundle and fills the W8 cache. Mints are not refused by MP-1 (V3): a stock pool can mine a
  VOID mint, as in v2 — but the wallet's dry run makes that unreachable except through a reorg.
- **Signature cache** (W8, R3): `index.cpp`, LRU of 16,384 entries keyed by
  `SHA256(attestation74 ‖ blockHash(citedHeight))` → valid/invalid — the one context-free,
  expensive step. Membership, freshness, count and hash checks are never cached (they depend on
  `R`, the selector and the branch). Filled by MP-1, `FilterTemplate` and `ConnectBlock`;
  node-local, never state; a cache hit and a cold verification always agree
  (`cache_hit_equals_cold`).

### 3.10 Determinism (added to the grep set)

`bundle.{h,cpp}`, `attest.{h,cpp}` join `state.cpp`, `tag.cpp`, `payload.cpp`, `script.cpp`,
`view.cpp` in the no-clock/no-socket/no-`GetArg` grep. `libsecp256k1` is called through one
wrapper (`VerifyCompactSig`) so the fuzz harness can stub it.

---

## 4. Architecture

### 4.1 Diff budget (v3)

| File | v2 actual | v3 delta | Tier |
|---|---|---|---|
| `src/main.cpp`, `src/miner.cpp`, `src/rpc/mining.cpp` | 11 / 12 / 7 | **0** | — |
| `src/init.cpp` | ≈ 110 | ≈ 15 (`-yellowbackattestarmmin`, `-yellowbackbundlecarrier`, `-yellowbackpreferredattestor`, RPC registration, `SCHEMA_VERSION` rebuild notice) | init |
| `src/wallet/rpcwallet.cpp`, `rpc/rawtransaction.cpp`, `wallet/rpcdump.cpp` | 65 | **0** (the H5/H7/H8 guards already cover any locked outpoint; carriers and bonds are locked outpoints) | wallet |
| `src/rpc/client.cpp`, `src/Makefile.am`, `Makefile.test.include`, `rpc-tests.py`, CI workflow | ≈ 90 | ≈ 40 | glue |
| the frozen set (`qa/yellowback-frozen-files.txt`): `src/main.cpp`, `src/miner.cpp`, `src/rpc/mining.cpp`, `src/policy/`, `src/script/`, `src/consensus/`, `src/primitives/`, `src/pow/`, `configure.ac`, `src/wallet/wallet.{h,cpp}`, `src/txdb.*`, `src/chainparams.cpp` | 0 | **0** | — |

The `audit` job's line-budget assertion keeps v2's numbers (`main.cpp` ≤ 40 etc.); a v3 PR that
moves them is refused. New: `git diff --numstat feature/yellowback-sf...HEAD -- src/main.cpp
src/miner.cpp src/rpc/mining.cpp src/policy` must be empty.

### 4.2 Modules (new and adapted, all under `src/yellowback/` unless stated)

```
params.{h,cpp}     ADAPT  §3.1 rows; PayloadVersion() = 3; BundleCarrier enum; regtest flags -yellowbackattestarmmin,
                          -yellowbackbundlecarrier; both in Params and the state-hash preimage
payload.{h,cpp}    ADAPT  version 3; MINT/REDEEM +attestFeeVout; new types 0x05..0x08; factories;
                          v2 corpus regenerated; a version-2 payload decodes to "non-Yellowback"
script.{h,cpp}     ADAPT  CarrierScript(pk, hash), IsCarrierScript, ParseCarrierScriptSig(scriptSig) -> optional<{bundle, sig, pk, hash}>,
                          BondScript(pk, locktime), ParseBondScript; FindCarrierInput(tx, skipVin0) -> optional<index>
attest.{h,cpp}     NEW    Attestation {seq, price, citedHeight, sig}; AttestMessage(seq, price, citedHeight, blockHash) -> uint256;
                          VerifyCompactSig(pubkey, msg, sig64) (the one secp256k1 call; low-S check); EncodeAttestation/Decode;
                          libbitcoin_common
bundle.{h,cpp}     NEW    Bundle {version, atts[]}; Encode/Decode; ExtractBundle(tx, carrierMode, payloadTail)
                          -> optional<{bytes, source}>; VerifyBundle(view, params, tx, R, selector, cache*) -> BundleVerdict
                          {ok, reason, C[]} (W8 order); BundleStat(C, weights) -> {aMint, aClaim}; libbitcoin_common
math.h             ADAPT  BondWeight, Quantile (cumulative-weight), ClaimantMaxZat/ResidualZat, AttestFeeZat, PriceCombine
state.{h,cpp}      ADAPT  ProcessTx: REG-A1, NOT-1, EQV-1, REV-1, IN-2 bond spend; MINT-9/10, MINT-8 clause; RED-1/3/4/5 clauses;
                          PRICE-2 per tx; TxLog fields. ComputeSnapshot: maturity, ARM-1/2, PIN-1/2, Seating, medians-minus-pinned,
                          dormancy; BundleLog row. NEW Selected(view, params, R, selector) (W9), AttestorPayees (AFEE-W default)
view.{h,cpp}       ADAPT  the tables of §3.6, prefixes, SCHEMA_VERSION 3, StateHash order, undo coverage
index.{h,cpp}      ADAPT  AttestationPool {add, list, freshest(seq)}; BundleCache (W8); BuildBundle(R, selector) -> optional<Bundle>
                          (needs cs_yellowback only); MempoolCheck fills the cache; -reindex notice on SCHEMA_VERSION change
policy.{h,cpp}     ADAPT  FilterTemplate: TPL-2 additions; fills the cache
wallet.{h,cpp}     ADAPT  carrier and bond tracking (W7): OutstandingCarriers() from carriers.dat, RecordCarrier/SpendCarrier,
                          SweepLapsedCarriers(); Bonds() through Attestors by bondPubKey; nothing IsMine, nothing in wallet.dat
txbuilder.{h,cpp}  ADAPT  BuildMint/BuildClaim gain the carrier input, attestor fee, bundle (from index or bundleHex), residual output
                          (claim); NEW BuildClaimNotice, BuildRegisterAttestor, BuildWithdrawBond, BuildRevive, BuildEquivocation,
                          BuildPrepareCarriers; carrier top-up in every builder (W7); SignCarrierInput
coinselect.{h,cpp} ADAPT  never selects carrier or bond outpoints for YEC; a Yellowback builder asks for one carrier explicitly
src/rpc/yellowback.cpp        ADAPT  §4.5 node RPCs
src/rpc/yellowbackwallet.cpp  ADAPT  §4.5 wallet RPCs
```

Placement: `attest`, `bundle` → `libbitcoin_common` (pure; `secp256k1` is already linked there
through `key.cpp`); everything else as v2. Nothing in `libbitcoin_common` calls
`libbitcoin_server`.

### 4.2a Signatures

```
// attest.h
struct Attestation { uint16_t seq; uint32_t priceMicroUsd; uint32_t citedHeight; std::array<unsigned char,64> sig; };
uint256 AttestMessage(uint16_t seq, uint32_t price, uint32_t citedHeight, const uint256& blockHash);
bool VerifyCompactSig(const CPubKey& pk, const uint256& msg, const std::array<unsigned char,64>& sig); // false on high-S; own verify-only context (pubkey.cpp's is in an anonymous namespace)
std::vector<unsigned char> EncodeAttestation(const Attestation&);                    // 74 bytes
std::optional<Attestation> DecodeAttestation(const std::vector<unsigned char>&);

// bundle.h
struct Bundle { uint8_t version; std::vector<Attestation> atts; };
std::vector<unsigned char> EncodeBundle(const Bundle&);                                 // ≤ 448
std::optional<Bundle> DecodeBundle(const std::vector<unsigned char>&);
enum class BundleSource { SCRIPTSIG, OP_RETURN };
std::optional<std::pair<std::vector<unsigned char>, BundleSource>>
    ExtractBundle(const CTransaction&, BundleCarrier mode, bool skipVin0, const std::vector<unsigned char>& payloadTail);
struct BundleVerdict { bool ok; std::string reason; std::vector<Attestation> C; std::optional<MicroUsd> aMint, aClaim; };
BundleVerdict VerifyBundle(const StateView&, const Params&, const CTransaction&, int R,
                           const std::vector<unsigned char>& selector, const std::vector<uint16_t>& selected,
                           std::function<std::optional<uint256>(int)> blockHashAt, BundleCache* cache /* nullable */);

// state.h
std::vector<uint16_t> Selected(const StateView&, const Params&, int R, const std::vector<unsigned char>& selector);   // W9
std::vector<uint16_t> Seated(const StateView&, const Params&, int H);
arith_uint256 BondWeight(const AttestorRecord&, const AttestState&, const Params&, int H);
std::optional<uint16_t> DefaultAttestPayee(const StateView&, const Params&, int R, const std::vector<unsigned char>& selector,
                                           const std::vector<uint16_t>& A, const AttestPolicy&);           // AFEE-W

// index.h
bool AddAttestation(const Attestation&, std::string& reason);           // pool; verifies vs tip; cs_yellowback
std::vector<Attestation> PoolAttestations() const;
std::optional<Bundle> BuildBundle(int R, const std::vector<unsigned char>& selector, std::string& reason);
```

Verdict strings (§4.2a of v2 extended): `mint9-no-bundle`, `mint9-bundle-<reason>`,
`mint10-diverged`, `red1-bundle-<reason>`, `red5-residual`, `afee1-fee`, and BUNDLE-1 reasons
`shape`, `hash`, `count`, `member`, `dup`, `stale`, `range`, `sig`, `two-carriers`.

### 4.3 Hook points — none added.

Every v3 rule runs inside `ProcessTx`/`ComputeSnapshot`, reached from the v2 hooks unchanged.
The one new *caller* of the overlay is the RPC layer (`yed_addattestation`, `yed_buildbundle`),
under `cs_yellowback` with the v2 lock order (`cs_main → cs_wallet → mempool.cs → cs_yellowback`).
`BuildBundle` reads `Snapshots[R]` and the pool only, never `cs_main`.

### 4.4 Miner integration — unchanged.

`getblocktemplate` and the coinbase tag are untouched. `yed_getinfo.miner` gains nothing. A pool
operator's only v3 change is upgrading `ycashd`.

### 4.5 RPC surface (`rpcversion = 3`)

`doc/yellowback-rpc.md` v3 is written **first** (Phase A0) and `make spec` regenerates
`doc/yellowback-rpc-contract.json` for both forks (P7). Node context unless marked wallet.

| Command | Purpose | Return shape (new fields) |
|---|---|---|
| `yed_getinfo` | + `attest {status, triggerHeight, armHeight, seatedCount, poolSize, poolFresh, carrierMode}`, `halts` unchanged | |
| `yed_getprice [height]` | + `xMint, xClaim, pinnedKeys, pinnedSeqs, seated` (per-tx values are in `yed_gettxinfo`) | |
| `yed_listattestors [height]` | every `Attestors` record: `seq, attestorPubKey, bondAddress (the bond output's P2SH), bondKeyAddress (P2PKH of bondPubKey: the fee payee), bondZat, bondLocktime, flags{tier, pool}, registerHeight, status, statusHeight, weight, seated, pinned, lastBundleHeight, poolFresh` | |
| `yed_getattestations` | the node's pool: `[{seq, price, citedHeight, receivedHeight, seated}]` | |
| `yed_addattestation <hex>` | verify and pool one 74-byte attestation; errors `attest-unknown-seq`, `attest-not-eligible`, `attest-stale`, `attest-bad-sig`, `attest-range` | `{accepted, seq, replaced}` |
| `yed_buildbundle <refHeight> <selectorHex>` | the bundle the node would build: `{hex, seqs, aMint, aClaim, missing[]}`; error `bundle-insufficient` with `missing` | |
| `yed_getselection <refHeight> <selectorHex>` | `selected(R, selector)` with weights — the wallet's "3 of 6 reachable" display | |
| `yed_getnotice <vaultTxid>` | the `Notices` record, or `{found: false}` (always an object, as `yed_gettag`) | |
| `yed_gettxinfo` | + `aMint, aClaim, bundleSeqs, attestFeeZat, attestPayee, residualZat, notice` | |
| `yed_decodepayload` | v3 types | |
| `yed_estimatecollateral` | + `aMint, source ∈ {x, a}`; error `bundle-insufficient` when ARMED and no bundle can be built | |
| `yed_mint … [bundleHex]`, `yed_claim … [bundleHex]` (wallet) | + optional bundle; errors `bundle-insufficient`, `mint10-diverged` (refused before build); optional `wait=false` | + `carrierTxid, bundleSeqs, attestFeeZat, attestPayee, residualZat, claimPath` |
| `yed_claimnotice <vaultTxid>` (wallet) | Step 1 of §10.3; errors as `yed_claim`, `notice-standing`, `notice-not-underwater` | `{txid, refHeight, pEmerg}` |
| `yed_sweepcarriers` (wallet) | reclaim outstanding carriers whose window lapsed | `{txid, count}` |
| `yed_registerattestor <bondYec> <lockBlocks> [flags]` (wallet) | §3.5; errors `bond-below-min`, `lock-below-min` | `{txid, seq?, attestorPubKey, bondAddress, bondKeyAddress}` (`seq` once confirmed via `yed_listattestors`; `bondKeyAddress` is what an operator exports to take the bond key cold) |
| `yed_withdrawbond <seq> [to]` (wallet) | spend the bond after `bondLocktime`; error `bond-locked` | `{txid}` |
| `yed_revive <seq> <priceMicroUsd>` (wallet, attestor node) | §3.5; errors `not-dormant`, `attest-key-not-held` | `{txid, seq, citedHeight, priceMicroUsd, hex}` |
| `yed_reportequivocation <hexA> <hexB>` (wallet) | §3.5; error `not-equivocation` | `{txid, seq}` |
| `yed_signattestation <seq> <priceMicroUsd> [citedHeight]` (wallet, attestor node) | signs with the attestor hot key held in the wallet; **the agent's RPC** so the key never leaves the node. **Equivocation guard (S16):** the node persists `(seq, citedHeight, price)` for everything it has signed in `<datadir>/yellowback/attest-signed.dat` (fsync before returning) and refuses a second signature for the same `citedHeight` at a different price with `equivocation-guard`, same price ⇒ `reused: true` with the recorded signature, different price ⇒ refused; errors `attest-key-not-held`, `equivocation-guard` | `{hex, seq, citedHeight, reused}` |
| `yed_listpositions`, `yed_listclaimable` | + `noticed, noticeHeight, emergencyOpenAt` | |

Unhealthy allow-list unchanged. `yed_addattestation` and `yed_signattestation` are RPC-auth
only; a subscriber runs beside its own node.

### 4.6 Wallet behaviour (deltas)

- **Carrier step (W7).** Each `yed_mint`/`yed_claim`/`yed_claimnotice`/`yed_reportequivocation`
  is two transactions: the carrier funding transaction, then the main one after one
  confirmation. The RPC blocks for that block (or returns `{carrierTxid, pending: true}` under
  `wait=false` and the wallet finishes on the next `ChainTip`); an outstanding carrier whose
  window lapses is swept back by the wallet (`yed_sweepcarriers`, also run at startup). Carriers
  and bonds are never `IsMine`, so no coin lock is needed and `sendtoaddress` cannot reach them;
  H5's guard is unchanged.
- **Dry run before build.** `yed_mint` evaluates MINT-1..10 with the bundle it built and refuses
  on any failure, naming the rule; `yed_claim` evaluates RED-1..5. (v2 already dry-runs; v3 adds
  the bundle to the dry run so a VOID mint is unbuildable.)
- **Reorg resubmit.** Unchanged from v2: a dropped mint is rebuilt with a fresh `refHeight`, and
  therefore a fresh bundle from the pool. If the pool cannot build one, the wallet reports it and
  stops; it never re-broadcasts the stale transaction.
- **Self-equivocation is prevented at the signer.** The one way an honest attestor gets
  ejected is signing two prices for one height — an agent restart mid-interval, or two agents
  on one key. `yed_signattestation`'s persisted guard (S16) makes that impossible from one node;
  running two nodes with one hot key is the operator's error and `doc/yellowback-attestor.md`
  says so in its first paragraph.
- **Bond wallet.** The registering wallet holds both keys; `yed_signattestation` uses the hot key
  (`attestorPubKey`); the bond key is never used except by `yed_withdrawbond`. Operators who want
  the bond key cold export it after registration and delete it from the hot wallet — documented in
  `doc/yellowback-attestor.md`, not enforced.
- **Sapling-funded mint.** Gains the carrier as its one transparent input; the carrier funding
  transaction is built from `ys1…` when `from` is shielded, to a fresh key.

### 4.7 Attestor operations (what an attestor runs)

```
ycashd -yellowback                                  # any v3 node; no payout address, no mining
ycash-cli yed_registerattestor 20000 420480 0       # once; wait BOND_MATURITY
yellowback-attest attest --conf attest.toml          # forever: polls, yed_signattestation, gossips
```

`attest.toml`: `[node] rpc_url, rpc_cookie`; `[attest] seq, every_blocks = 10, fail_polls = 2, poll_seconds = 15`;
`[[sources]]` as the quote agent; `[transport] kind = "iroh" | "dir", relays = [...], peers = [...], secret_key_file, topic_override`.
No inbound port, no domain, no funded hot wallet beyond the node's own for `yed_revive` (rare).
A bond cannot be topped up; to change it an attestor registers a new identity (new `seq`, age
from zero) and lets the old one go dormant and withdraw at its locktime.
`yed_getinfo.attest` and `yed_listattestors` are the monitoring surface; sample `systemd`/`launchd`
units in `contrib/yellowback/attest/`.

### 4.8 YecWallet (`yecwallet-dd`)

`RPC_VERSION = 3` in the first commit. Changes, all over the `yed_*` contract:

- **Mint page**: the two source prices and which one bound (`pMint` = x or a), the selection
  status ("5 of 6 selected attestors reachable"), the carrier step shown as "preparing price
  proof (1 block)", `mint10-diverged` shown as "pools and attestors
  disagree by N %; minting paused".
- **Positions**: `noticed` badge with `emergencyOpenAt`; the claim action offers "post notice"
  when the vault is under `EMERGENCY_RATIO` by either source but not under `CLAIM_THRESHOLD` by
  the combined price.
- **Attestors view** (new, read-only): `yed_listattestors` as a table, the arming banner
  (`UNARMED`/`TRIGGERED at … arms at …`/`ARMED`), seated and pinned marks, the source-tier and
  pool flags.
- **Settings**: subscriber status (running/not; the launcher for `yellowback-attest subscribe`
  beside the bundled `ycashd`; the transport config).
- **Copy rule**: "trustless" stays banned; "attested" describes a price both sources signed off
  on, never "verified".

---

## 5. Agents (`contrib/yellowback/attest/`)

**`yellowback-attest`** — one Rust binary, two subcommands, pinned by `rust-toolchain.toml`
(a current stable; the pin is bumped by PR like any dependency), `Cargo.lock` committed, no
`cargo vendor` (W13). It links `iroh-gossip` and `reqwest` (sources); it never links anything
from the node tree. Its unit tests run in the `agent` CI job.

- **`attest`**: every `every_blocks` (read from `yed_getinfo.height` via polling the node RPC
  every 15 s; no ZMQ), aggregate the sources exactly as `yellowback_price.py` does (the Rust
  port keeps the same presets and guards; the two are cross-tested on recorded fixtures), call
  `yed_signattestation <seq> <price> <tip − REF_LAG>`, publish the 74 bytes on the topic. After
  `fail_polls` failures publish nothing. Logs at `info` per publish.
- **`subscribe`**: join the topic, decode each message, drop anything not 74 bytes or with a
  `seq` not in the last `yed_listattestors` (refreshed every 60 s), call `yed_addattestation`,
  count acceptances; optional `[endpoints]` HTTPS polling of declared attestor URLs as a second
  path. Also serves as the devnet's and YecWallet's subscriber.
- **Transports**: `iroh` (default; `relays` configurable; topic = `"yellowback/attest/" ‖
  network ‖ "/" ‖ PAYLOAD_VERSION`) and `dir` (`path`; each publish appends a file `<seq>-<citedHeight>.att`;
  subscribers poll the directory) — the test and devnet transport, so no test ever needs a relay.
- **Fixtures**: `contrib/yellowback/attest/fixtures/` holds recorded exchange responses; the
  Rust and Python aggregators are asserted equal on them (`test_yellowback_price.py` gains the
  cross-check).

**Devnet** (`contrib/yellowback/devnet/yellowback-devnet`): `up` additionally starts nodes 5–7 as
attestor nodes (`-yellowback`, no payout), registers each (`yed_registerattestor 10 200`), mines
through `BOND_MATURITY` and `ATTEST_ARM_DELAY` so `up` ends **ARMED**, and starts three
`yellowback-attest attest --transport dir` plus one `subscribe` beside node 0; `status` prints
`yed_getinfo.attest` and `yed_listattestors`; `check` additionally asserts `attest.status ==
"ARMED"` and `poolFresh ≥ M_SELECT`; `attestor N {stop|start|price USD}` for demos of an outage
and of divergence; `notice <vaultTxid>` for the emergency flow. `YELLOWBACK_DEVNET_PORTBASE`
(default 28000) and `YELLOWBACK_DEVNET_DIR` allow two devnets side by side (S7). `up` mines
≈ 232 + 16 + 8 blocks.

---

## 6. Work plan

Nine phases, A0–A8, each a reviewable PR series against `feature/yellowback-price-attest` in the
relevant fork. Sizes are source lines excluding tests. A phase ends when its exit criteria pass
in CI. The v2 review rule (P13) applies unchanged: the four-part check per ported symbol, the tier
statement, the rule identifiers each test tags, the budget numbers; two reviewers for any PR
touching `state.cpp`, `bundle.cpp` or `attest.cpp`; a PR touching the consensus set, `policy.cpp`,
`main.cpp`, `miner.cpp` or `rpc/mining.cpp` is refused outright (the `audit` job enforces zero
delta against `feature/yellowback-sf` for those files).

**Keeping the tree building.** Payload version 3 is a flag day inside the fork: at A0's first
commit every v2 functional flow script that builds transactions through the wallet RPCs keeps
passing only because `attest.status == UNARMED` on regtest by default (`ATTEST_ARM_MIN = 3` and
no registrations) — **the v2 suite stays in CI throughout**, unarmed, and is the regression net.
New behaviour is exercised by scripts that register attestors and arm. The v2 golden vector is
regenerated once at A1 (the snapshot gains fields) and pinned again; `yellowback_model.py` and
the C++ must agree before the pin.

**Parallelism.** A0 first (it is the contract). A1 and A2 are sequential on one worktree; A3
(wallet builders) may start at A1's exit against raw-built attestors; A4 (agents, Rust) is
independent of A1–A3 except for the `yed_signattestation`/`yed_addattestation` contract from A0
and may start immediately; A5 (YecWallet) at A2's exit for the read-only views and A3's exit for
the actions; A6 after all. Each parallel agent works in its own `wt/<name>` worktree (§6.0).

### 6.0 Developing and testing on one machine — concurrently

v2's §6.0 stands (commands, build, the six-node topology, the helper library, IBD note, the
inner loop, CI layout). Additions:

**1. Concurrent sessions (S7).** Several agents or several test runs share one laptop:

```
# one worktree per agent, sharing depends and the cargo target (memory: ycash-dd-worktrees)
git -C ycash-dd worktree add ../wt/a1 -b feature/yellowback-price-attest-a1 feature/yellowback-price-attest
# each run gets its own port range and its own chain cache
../.venv/bin/python qa/pull-tester/rpc-tests.py --portseed=$((RANDOM%9000+1000)) --cachedir=$PWD/cache yellowback_attest
# a single script likewise
../.venv/bin/python qa/rpc-tests/yellowback_attest.py --portseed=4711 --cachedir=$PWD/cache --nocleanup
```

`--portseed` and `--cachedir` are the framework's own (`test_framework.py:111,117`) and work
when a **script is run directly**. `qa/pull-tester/rpc-tests.py` overrides both (`:267`, `:336`
append its own values after the user's, and optparse keeps the last), so through the runner the
isolation comes from **one worktree per agent** — its own build tree ⇒ its own `qa/cache` and its
own binaries — plus the runner's time-based port offset. A0 adds a pass-through in the fork's
`rpc-tests.py` (`--portseed`/`--cachedir` given by the user win; glue budget) so two runners in
one worktree also isolate (R16). Two devnets: `YELLOWBACK_DEVNET_PORTBASE=29000
YELLOWBACK_DEVNET_DIR=/tmp/devnet-b yellowback-devnet up`. The one shared resource is
`~/.zcash-params` (read-only). The rule for agents: **never run two scripts with the same
`--portseed`**, and never `--cachedir` into another worktree.

**2. Topology for v3 tests** (eight of the eight nodes):

| Node | Role | Flags |
|---|---|---|
| 0 | user wallet (minter, claimant, notice poster) | `-yellowback` |
| 1 | stock node and stock miner; the adversary | stock args |
| 2–4 | three pools | `pool_args` |
| 5 | non-enforcing observer | `-yellowback -yellowbackenforce=0` |
| 6 | attestor wallet A (holds the keys of attestors 1–3; `yed_signattestation` by key) | `-yellowback` |
| 7 | attestor wallet B (attestors 4–5; the "other operator" for overlap and equivocation cases) | `-yellowback` |

Attestors are **keys, not nodes**: one wallet can hold several attestor keys, and the framework
signs with Python for most cases (item 4). Nodes 6–7 exist for the RPC path (`yed_registerattestor`,
`yed_signattestation`, `yed_revive`, `yed_withdrawbond`) and for the agent script.

**3. Regtest arithmetic.** Registration → ELIGIBLE in 8 blocks; 3 ELIGIBLE → TRIGGERED → ARMED in
8 more; so `arm(attestors)` costs ≈ 16 blocks after `activate()`'s 129. A full v3 lifecycle
(activate, register 5, arm, mint, crash, notice, wait 4, emergency claim) is ≈ 200 `generate`
calls. `-yellowbacksigmaref=0` as before.

**4. `yellowback_util.py` (v3 additions) and `test_framework/yellowback_attest.py` (new).**
`YellowbackTestFramework` gains a `num_nodes` constructor argument (v2's class hard-wires 6,
`yellowback_util.py:431`); v3 scripts pass 8 and v2 scripts are untouched. `setup_network`
connects nodes 6–7 into the star on node 1. Constants: the §3.1 regtest values. Helpers: `attestor_keys(n)` (fixed regtest WIFs
`ATTESTOR_WIFS[0..4]` for hot keys, `BOND_WIFS` for bond keys — fixed so the golden vector is
reproducible), `build_register_tx(node, hot_pubkey, bond_pubkey, bond_zat, lock_blocks, flags)`
(raw; the bond P2SH built in Python; used by A1–A2 before the RPC exists, S10),
`sign_attestation(hot_secret, seq, price, cited_height, blockhash) -> 74 bytes` (Python
`CECKey.sign` is OpenSSL with a **random nonce**, so it cannot produce known-answer vectors;
the helper signs with RFC 6979 in pure Python — byte-identical to `secp256k1_ecdsa_sign`'s
default nonce function and to the Rust `secp256k1` crate — then sets `s = n − s` when `s > n/2`
and emits `r ‖ s`; both branches have a known-answer vector, R18; `CECKey` remains the
independent verifier; the reference implementation the C++ is tested against),
`feed(node, seq, price, cited=None)` (= `sign_attestation` + `yed_addattestation`),
`feed_all(node, prices: dict[seq → usd])`, `register_and_arm(nodes, n=3)` (registers on node 6/7,
mines to ELIGIBLE, asserts `TRIGGERED` at the exact block, mines `ATTEST_ARM_DELAY`, asserts
`ARMED` on every enforcing node and `assert_same_statehash`), `build_bundle(node, R, selector,
prices)` (Python selection — the second implementation of W9 — asserted equal to
`yed_buildbundle`), `build_carrier_tx(node, bundle) -> (txid, outpoint, pk)` / `spend_carrier(...)` (the raw carrier
step: a P2SH output whose redeem script commits `SHA256(bundle)`, W7; for
`build_mint_tx` and `build_vault_spend_raw`, which gain `bundle=` and `carrier=` arguments),
`post_notice_raw(...)`, `equivocation_raw(...)`, `revive_raw(...)`, `assert_void_reason(node,
txid, rule)`, `assert_model_matches(node, full=True)` extended (S12). Everything signs in Python;
nothing starts the Rust agent except `yellowback_attest_agent.py`.

**5. Inner loop.** `test_bitcoin --run_test='yellowback_attest*|yellowback_bundle*|yellowback_state*'`
(seconds); `yellowback_attest.py` (≈ 3 min); the v3 suite by name (`-j4`, ≈ 20 min on top of
v2's); the devnet ARMED for the GUI.

**6. CI additions** to `.github/workflows/yellowback-tests.yml` (one workflow, as v2):

| Job | Trigger | Steps |
|---|---|---|
| `main` | PR + push to `feature/yellowback-price-attest` | v2's steps **plus** the v3 scripts of §7 in `BASE_SCRIPTS`; the whole `test_bitcoin` |
| `audit` | PR + push | v2's budgets; **zero delta vs `feature/yellowback-sf`** for the frozen set of §8.4 item 1 (one list, `qa/yellowback-frozen-files.txt`, read by the job and quoted by §4.1); the determinism grep over the §3.10 set; the rule-tag loop over the v3 identifiers; the contract check |
| `agent` | PR + push (paths `contrib/yellowback/attest/**`) | `cargo build --locked`, `cargo test`, `cargo clippy -D warnings`, the fixture cross-check against `yellowback_price.py` |
| `python` | PR + push | v2's plus `pyflakes` over the new scripts and `test_framework/yellowback_attest.py`; a `sign_attestation` known-answer test |
| `nightly` | schedule | v2's plus `yellowback_attest_agent.py` (starts the Rust agent with `dir://`), `yellowback_attest_stress.py` (random arming/outage/reorg), the `SCHEMA_VERSION` rebuild case |
| `sanitizers`, `lockorder`, `coverage` | nightly | v2's plus `yellowback_attest.py`; coverage floors for `attest.cpp`, `bundle.cpp` |
| `wallet` | `yecwallet-dd` PR | v2's plus the Attestors-view offline cases and the v3 contract field check |

**7. What one machine cannot show** — real relays across NATs, real attestor diversity, real
exchange feeds — is A7.

### Phase A0 — Contract, protocol library (≈ 700 lines)

- [x] Branch hygiene: `feature/yellowback-price-attest` exists in all three repos (done
      2026-09-13); `.github/PULL_REQUEST_TEMPLATE.md` gains the "no delta in the frozen files"
      line; CI `audit` job's frozen-file zero-delta check against `feature/yellowback-sf`.
- [x] `doc/yellowback-rpc.md` v3 **first** (§4.5: every command, field, error identifier);
      `make spec` → `doc/yellowback-rpc-contract.json` in both forks; `doc/yellowback-spec.md`
      gains §3 of this plan; `doc/yellowback-attestor.md` (§4.7) drafted.
- [x] `docs/mapping.md` rows (Appendix A): the scriptSig carrier vs DigiByte's oracle bundle
      (`ref/digibyte/src/oracle/`), compact ECDSA vs DigiByte's Schnorr/MuSig2, the CLTV bond vs
      DigiByte's staking-free design, the non-`IsMine` carrier and bond (`ismine.cpp:80-90`), the 1,650-byte scriptSig
      policy (`ref/ycash/src/policy/policy.cpp:88-97`), `AreInputsStandard` P2SH sigops
      (`:178`), `MAX_SCRIPT_ELEMENT_SIZE` at execution (`interpreter.cpp`), `secp256k1` compact
      parse/verify availability in Ycash's bundled library.
- [x] `params.{h,cpp}`: §3.1; `PayloadVersion()`; `BundleCarrier`; the two regtest flags in the
      state-hash preimage; `IsArmedAt(snapshot)`.
- [x] `payload.{h,cpp}`: version 3, the seven types, factories, malformed cases; the v2 corpus
      regenerated by `gen_yellowback_corpus.py` (version byte) and the fuzz target's table.
- [x] `script.{h,cpp}`: carrier and bond scripts and parsers; `FindCarrierInput`.
- [x] `attest.{h,cpp}`: message, codec, `VerifyCompactSig` (low-S; `secp256k1_ecdsa_signature_parse_compact`
      + `secp256k1_ecdsa_verify` on the `extern secp256k1_context_verify` of `pubkey.cpp:14` —
      **never `CPubKey::Verify`**, which normalises high-S (`pubkey.cpp:32-36`) and would accept
      two encodings of one signature, R17; a high-S input is **rejected**, test `highs_rejected`).
- [x] `bundle.{h,cpp}`: codec, `ExtractBundle` (both sources, `EITHER`; the scriptSig source
      checks `SHA256(bundle)` against the redeem script's hash),
      `VerifyBundle` with the W8 order over an injected `selected` and `blockHashAt`, `BundleStat`.
- [x] `math.h`: `BondWeight`, `Quantile`, `ClaimantMaxZat`/`ResidualZat`, `AttestFeeZat`,
      `PriceCombine`.
- [x] Unit: `yellowback_attest_tests.cpp` (known-answer vectors produced by
      `test_framework/yellowback_attest.py:sign_attestation` and checked in as
      `yellowback_attest_vectors.json`; high-S; wrong block hash; wrong key),
      `yellowback_bundle_tests.cpp` (codec round trip; 6-attestation bundle is 448 bytes and a
      7th is refused; `ExtractBundle` on a MINT with a carrier at `vin[0]`, `vin[2]`, two
      carriers, a REDEEM whose `vin[0]` looks like a carrier; `VerifyBundle` order — each reason
      string reachable, `// Rule: BUNDLE-1`), `yellowback_script_tests.cpp` additions (carrier
      and bond templates under `VerifyScript(STANDARD_SCRIPT_VERIFY_FLAGS)`; a carrier spent with
      a bundle whose hash differs from the redeem script's fails `OP_EQUALVERIFY` — the
      malleation case, R2; `IsStandardTx` and
      `AreInputsStandard` **called directly** for a mint with a carrier input and a claim with
      carrier + residual; a 521-byte push fails `MAX_SCRIPT_ELEMENT_SIZE` at execution — proving
      the cap is real), `yellowback_payload_tests.cpp` v3 (every type, sizes exactly 52/41/75/4/78 and `11 + 5·count`,
      version-2 payload decodes to non-Yellowback), `yellowback_math_tests.cpp` additions
      (quantile at the boundary — cumulative weight exactly at the threshold; residual at
      110 % is 0; overflow at `PRICE_MIN`).
- [x] Fuzz: `src/fuzzing/YellowbackBundle` (decode + verify with a stub verifier that accepts a
      fixed signature) and the payload target's v3 corpus; `gen_yellowback_corpus.py --check`.
- [x] **Exit:** `make check` green; `audit` job green with the frozen-file check; the v2
      functional suite green unchanged (nothing is armed); contract JSON matches the doc.
      *Met 2026-09-13 with two recorded exceptions: `yellowback_rpc_contract.py` is red until A2
      (the contract names A2's commands); the v2 suite was sampled (`framework_smoke`,
      `pricefeed`), not run in full — the full run is A1's exit.*

### Phase A1 — State machine v3 (≈ 1,100 lines)

- [x] `view.{h,cpp}`: the §3.6 tables, prefixes, `SCHEMA_VERSION = 3`, state-hash order, undo for
      every new write (`Attestors` status, `Attest`, `BundleLog`, `Notices`, `AttestorSeq`).
- [x] `state.{h,cpp}`: REG-A1, IN-2 bond spend, NOT-1, EQV-1, REV-1; `Seated`, `Selected` (W9),
      `BondWeight`; MINT-9/10 and the MINT-8 clause; RED-1/3/4/5 clauses; PRICE-2 per
      transaction; `TxLog` fields; `ComputeSnapshot` order of §3.8 (judgement, activation, maturity, ARM-1/2,
      PIN-1/2, seating, medians minus pinned, σ, issuance, halts, dormancy); `BundleLog` row per height; `DefaultAttestPayee`
      (AFEE-W).
- [x] `yellowback_model.py`: every new snapshot field and table; `Selected` in Python (the second
      implementation); bundle statistics from `yed_gettxinfo`; regenerate
      `yellowback_golden.json` **once**, with the fixed regtest keys, and pin; `statehash_golden_vector`
      updated.
- [x] Unit: `yellowback_state_tests.cpp` additions, one case per identifier, tagged: `rega1_*`
      (bare bond script refused, below-min, duplicate hot key vs WITHDRAWN vs EJECTED — the
      loophole case `rega1_ejected_then_spent_stays_barred`), `arm1_triggers_at_exact_block`,
      `arm2_arms_after_delay`, `arm_never_reverses`, `founding_cohort_origin` (registered before
      and after the trigger; a week-late registrant is not founding), `weight_clamped_before_trigger`,
      `seating_ties_by_seq`, `selected_matches_python` (vectors from the framework),
      `selected_excludes_pinned`, `mint9_no_bundle_void`, `mint9_bundle_from_unselected_void`,
      `mint9_stale_attestation_void`, `mint10_diverged_void`, `mint10_exact_boundary_ok`,
      `price2_unarmed_reads_x_only`, `price2_min_max`, `red1_claim_needs_bundle`,
      `red1_owner_path_ignores_bundle`, `red4b_needs_notice_and_persist`, `red4b_notice_too_old`,
      `red4b_before_arming_false`, `red5_residual_paid`, `red5_residual_below_dust_vacuous`,
      `red5_residual_to_wrong_key_invalid`, `red5_normal_claim_residual_zero`,
      `not1_standing_notice_not_replaced` (the reset attack), `not1_deleted_when_vault_closes`,
      `eqv1_two_prices_one_hash_ejects`, `eqv1_fork_hashes_not_equivocation`, `rev1_only_dormant`,
      `dormancy_needs_selection_evidence`, `dormancy_unseated_never_dormant`,
      `pin1_arms_from_bundlelog`, `pin1_excludes_key_from_medians_and_E`, `pin2_excludes_seq`,
      `pin_not_armed_without_bundles`, `afee1_fee_to_contributor`, `afee0_unarmed_vacuous`,
      `in2_bond_spend_withdraws`, `attest_required_false_reads_x_only` (W15),
      `dormancy_only_at_check_heights`, `seated_since_tracks_seating`, `selection_ignores_owner_key`
      (two mints at one `R` with different owner keys share `selected`), `cache_hit_equals_cold` (the same
      attestation on two branches: two cache entries, both agreeing with cold verification), `undo_identity_v3` (apply/undo over a sequence covering every
      table), `overlay_equivalence_v3`.
- [x] Fuzz: `YellowbackEvaluate` corpus extended with v3 payloads and carriers; the four K1
      properties re-asserted (no throw, no assert, deterministic, undo-identity).
- [x] **Exit:** unit suite green; `yellowback_index.py` and `yellowback_activation.py` green
      unarmed; the golden vector reproduced by C++ and Python; determinism grep empty over §3.10.

### Phase A2 — Index, pool, node RPCs (≈ 600 lines)

- [x] `index.{h,cpp}`: `AttestationPool` (last three per `seq`, freshness vs tip, `AddAttestation`
      verifying against `Attestors` — any status but EJECTED/WITHDRAWN, S4), `BundleCache` (W8),
      `BuildBundle` (W9 selection over the pool; `missing[]`), `MempoolCheck` fills the cache;
      `SCHEMA_VERSION` mismatch ⇒ wipe-and-rebuild with a log line and `yed_getinfo.rebuilt`.
- [x] `policy.{h,cpp}`: TPL-2 additions; `FilterTemplate` fills the cache.
- [x] Node RPCs of §4.5 (`yed_listattestors`, `yed_getattestations`, `yed_addattestation`,
      `yed_buildbundle`, `yed_getselection`, `yed_getnotice`, `yed_gettxinfo`/`yed_getprice`/
      `yed_getinfo`/`yed_estimatecollateral`/`yed_decodepayload` fields); `client.cpp` rows;
      `ycash-cli` rebuilt; `init.cpp` flags and registration.
- [x] `qa/rpc-tests/yellowback_attest.py` (raw builders; the core v3 flow): register five
      attestors raw on nodes 6–7; `TRIGGERED` at the exact block the third matures; `ARMED` after
      8; `feed_all`; `yed_buildbundle` equals the Python bundle; a raw mint with the bundle in a
      carrier confirms ACTIVE with `aMint` recorded, `attestFeeZat` paid; the same mint mined by
      node 1 (stock) is ACTIVE too (deterministic); a mint with a bundle citing a reorged block
      (split, mine, join) is VOID with `mint9-bundle-sig` on every node — the hash changed, not the
      age (R9) — and the state hashes agree; a bundle citing `R − ATTEST_MAX_AGE` is
      `mint9-bundle-stale`; `mint10_diverged_unbuildable` (attestors at 2× the pools: `yed_estimatecollateral`
      refuses, a raw mint is VOID); pinning: pools hold one price while attestors move 6 %
      across 16 blocks — `pinnedKeys` fills, `E(R)` shrinks, `xMint` follows only unpinned
      pools; `pin_test_not_armed_without_bundles`; a claim with the bundle; RED-5 residual on a
      300 %-covered vault claimed through the emergency path (notice, 4 blocks, claim) returns
      the residual and the owner's balance shows it; `not1_reset_attack_fails`; equivocation
      raw ⇒ EJECTED on all nodes; dormancy (attestor 5 seated, selected twice, absent) ⇒
      DORMANT, `revive_raw` ⇒ ELIGIBLE; bond spend after locktime ⇒ WITHDRAWN and the ejected
      case stays EJECTED; `assert_model_matches(full=True)` at the end; `checkpoint()` after
      every block.
- [x] `qa/rpc-tests/yellowback_attest_enforcement.py`: node 1 mines a claim without a bundle
      after arming ⇒ rejected `yellowback-vault-spend` by 0, 2–4, followed by node 5; DoS 0; a
      claim paying no residual ⇒ rejected; a correct claim from node 1's mempool ⇒ accepted; the
      valve still clears after six blocks (v2 case 9 re-run armed); `unarmed_v2_behaviour`
      (no registrations: every v2 enforcement case passes unchanged — run by importing v2's
      cases).
- [x] `yellowback_rpc_contract.py`: v3 commands and every new error identifier provoked.
- [x] `yellowback_index.py` additions: `schema3_rebuilds_v2_index` (a v2 datadir from the cache
      starts, rebuilds, matches a fresh node's hash), `attest_tables_survive_kill9`,
      `attest_reorg_across_arming` (split at `armHeight − 1`; one branch arms, the other does
      not; join; hashes agree with the winner).
- [x] **Exit:** the four scripts green in `main`; `yellowback_stockparity.py` nightly unchanged
      (node 1 unaffected); `mempoolcheck_bench` within v2's bound for non-vault transactions.

### Phase A3 — Wallet builders and RPCs (≈ 700 lines)

- [x] `wallet.{h,cpp}`: carrier and bond tracking (W7: `carriers.dat`, outstanding carriers,
      bonds through `Attestors`); `yed_sweepcarriers` at startup.
- [x] `txbuilder.{h,cpp}`: `BuildMint`/`BuildClaim` with carrier, bundle (index or `bundleHex`),
      attestor fee, residual; `BuildClaimNotice`, `BuildRegisterAttestor`, `BuildWithdrawBond`,
      `BuildRevive`, `BuildEquivocation`, `BuildCarrier` (the carrier step, W7) and the
      two-transaction flow with `wait`; `SignCarrierInput`; the dry run extended to MINT-9/10 and RED-5; Sapling shapes (S11).
- [x] Wallet RPCs of §4.5; `yed_signattestation` (hot key lookup by `attestorPubKey` held in the
      wallet); `-yellowbackpreferredattestor`, `-yellowbackcarrierpool`.
- [x] `qa/rpc-tests/yellowback_attest_wallet.py`: `yed_registerattestor` on nodes 6–7 → the same
      records the raw path produced; `yed_mint` with the node-built bundle (two transactions, one
      block apart; ACTIVE, both fees, `bundleSeqs`), from `ys1…` (one transparent input, the
      carrier), `wait=false` then completion on the next block, a carrier whose window lapses
      swept by `yed_sweepcarriers`, `bundle-insufficient` with `missing`, `mint10-diverged` refused before build, manual `bundleHex` from
      `yed_buildbundle`; `yed_claim` normal and emergency (`yed_claimnotice`, wait, claim;
      residual to the owner's address, `yed_listpositions.noticed`), to `ys1…` with the residual
      transparent; `yed_withdrawbond` before/after locktime; `yed_revive`; `yed_reportequivocation`;
      `yed_signattestation` twice for one height at two prices ⇒ `equivocation-guard`, and across a
      node restart (the persisted guard);
      `lockunspent` cannot unlock a carrier or bond (H5 re-run); `sendtoaddress` never spends
      one; restore (`yellowback_wallet_restore.py` additions: bonds reappear after `importprivkey` +
      `-rescan` through `Attestors` by `bondPubKey`; an outstanding carrier survives a restart via
      `carriers.dat` and is orphaned, not lost to a third party, when that file is absent, W7).
- [x] The v2 flow scripts (`yellowback_lifecycle.py`, `yellowback_claim.py`,
      `yellowback_void_mint.py`, `yellowback_sapling.py`) gain an `--armed` mode that calls
      `register_and_arm` first; both modes in CI.
- [x] **Exit:** the wallet scripts green in both modes; `src/wallet/wallet.{h,cpp}` and
      `rpcwallet.cpp` at zero v3 delta. *Met 2026-09-14 on the integrated tree: every flow script
      green in both modes, and `git diff feature/yellowback-sf...HEAD -- $(cat
      qa/yellowback-frozen-files.txt)` is empty.*

### Phase A4 — Agents, devnet, docs (Rust and Python; 0 C++)

- [x] `contrib/yellowback/attest/`: the Rust crate (§5) with `attest`/`subscribe`, `iroh` and
      `dir` transports, the source aggregator port, fixtures and the cross-check; `rust-toolchain.toml`,
      `Cargo.lock`; the `agent` CI job.
- [x] `qa/rpc-tests/yellowback_attest_agent.py` (nightly): three `attest` processes on `dir://`
      against nodes 6–7's `yed_signattestation`, one `subscribe` beside node 0; `poolFresh`
      reaches 3 within two polls; a mint builds from the pool; stopping one agent leaves
      `K_SLACK` covering; stopping two refuses with `missing`. *Registered in
      `EXTENDED_SCRIPTS` and run by the `nightly` job, which builds the crate first and fails if
      the binary is absent — the script itself SKIPs without one, so the job must not. Green
      locally in 198 s: three agents published 7/6/4 times and the subscriber accepted 17
      attestations across the outage and recovery steps.*
- [x] Devnet changes of §5; `check` extended. *The rest of this row is done (2026-09-13/14):
      `doc/yellowback-attestor.md` finished (bond key hygiene, the one-day arming notice, dormancy
      and revival, equivocation consequences, the one-hot-key-one-node warning first), the
      `doc/yellowback-mining.md` note, and `contrib/yellowback/README.md`; both docs also carry the
      PIN-1 paragraph — a constant quote is pinned once the other side moves.*
- [x] Calibration scripts (proposal §16): `contrib/yellowback/attest/calibrate/spreads.py` and
      `pinrate.py`, with a README on how to run them for two weeks and read the result.
- [ ] **Exit:** `agent` job green; devnet `check` exits 0 ARMED; `yellowback_attest_agent.py`
      green nightly.

### Phase A5 — YecWallet (`yecwallet-dd`; ≈ 500 lines changed)

- [x] `RPC_VERSION = 3`; contract copy; `yellowbackrpc.h` fields.
- [x] Mint page, Positions, Attestors view, Settings of §4.8; the subscriber launcher beside the
      bundled `ycashd` (the `yellowback-attest` binary packaged by `build.sh`; a missing binary
      disables the launcher with a message, never the wallet).
- [x] QTest: offline cases for every new element with a fake `Connection`; the devnet case
      extended (mint ARMED, notice, emergency claim, attestor outage banner), skipped without
      `YELLOWBACK_DEVNET_DIR`.
- [x] `build.sh --package` includes `yellowback-attest`; `grep -rn 'trustless\|verified price'
      src/` empty. *`build.sh --attest PATH` implemented and its argument handling tested; the grep
      is empty. Running `--package --attest` end to end is an A6 item.*
- [ ] **Exit:** `wallet` job green; the devnet case passes by hand and is recorded. *The offline
      half is met (83 QTest cases, contract check, copy rule); the devnet case QSKIPs until the
      A4 devnet chunk exists.*

### Phase A6 — Hardening and review (≈ 2 weeks)

- [ ] DoS review rows: bundle verification cost (W8) measured — a block of 3,000 carrier
      transactions **with valid six-signature bundles and the `FEE_MIN` pool fee** on regtest,
      `ConnectBlock` time with a cold cache (expected ≈ 1–2 s, R15); the pool's memory bound
      (three per `seq`, ≤ 3 × 65,535 entries × 74 B); `yed_addattestation` rate (RPC-auth only);
      notice spam (one record per vault, ≤ vault count).
- [ ] `yellowback_attest_stress.py` (nightly): random registrations, outages, equivocations,
      reorgs of depth 1–6 across arming, notices and claims; state-hash equality and
      undo-identity at every step; cold rebuild equals.
- [ ] Sanitizers and `lockorder` over the v3 scripts; coverage floors for `attest.cpp`,
      `bundle.cpp`, the new `state.cpp` paths.
- [ ] `doc/yellowback-review.md` v3: the §8.4 checklist scored; the frozen-file proof
      (`git diff feature/yellowback-sf...HEAD -- <frozen>` empty); the trust statement delta
      (§8.1) as it will be published.
- [ ] rc run-through `yellowback_rc2.py`: v2's rc1 steps with arming inserted after activation,
      an emergency claim, an attestor ejection and a withdrawal; hash ledger.
- [ ] **Exit:** every §8.4 item scored yes or explicitly deferred with a reason; the owner signs
      off the trust statement.

### Phase A7 — Testnet with real attestors (≥ 4 weeks)

- [ ] Recruit ≥ 5 attestors with distinct source sets (at least two on direct exchange APIs);
      publish the arming rule and the one-day notice; observe TRIGGERED → ARMED.
- [ ] Drills: attestor outage (K_SLACK), two-attestor outage (minting refuses), divergence (a
      mock feed at 2×), pinning (a frozen feed for 7 h), a notice and emergency claim on a test
      vault, an equivocation report, a dormancy and revival, a withdrawal at locktime; relay
      failure (all relays down: minting halts, manual `bundleHex` works).
- [ ] Run the two calibration measurements against live data; fix `DIVERGE_BPS_ATTEST`,
      `PIN_WINDOW`, `PIN_DELTA_BPS` in the release parameter set.
- [ ] **Exit:** four weeks ARMED without a state-hash divergence among enforcing nodes; every
      drill recorded in `doc/yellowback-testnet-v3.md`.

### Phase A8 — Mainnet

- [ ] The v3 release with the calibrated set; registration opens at the release's start height;
      arming is automatic (D-4) — the announcement explains the trigger and the day's notice.
- [ ] Monitoring: `yed_getinfo.attest` on every pool's node; an explorer page over
      `yed_listattestors` (overlap disclosure, proposal §7.5).
- [ ] The enshrinement note (§9) filed with the Ycash maintainers together with the separate
      relay-policy and toolchain recommendations (proposal §8.1, §13).

### 6.1 Found by running the A4 devnet (2026-09-20)

Three defects and one usability finding, all in test and tooling code — no node change. Rows in
`docs/mapping.md` §14.1.

| # | Found | Fix |
|---|---|---|
| D-A4-1 | The third attestor's `yed_registerattestor` failed with `insufficient-yec: need 10.00001, have 0.00`. `sync_blocks` waits on block height and does **not** relay mempools, so node 0's third funding transaction had not reached the pool that mined the next block | `sync_mempools` before the funding and registration blocks, plus a per-node balance assertion that names the node rather than surfacing an RPC error two steps later |
| D-A4-2 | `qa/rpc-tests/yellowback_enforcement.py` failed in CI at case 6 with `IndexError: list index out of range`. `EDGES` declares the **eight**-node v3 topology (the attestor slots 6–7 joined it in A0) but that script runs six nodes; three framework methods filtered privately while the script iterated `EDGES` raw in five places | One accessor, `live_edges()`, filtered by the started node count, used by every edge walk in the framework and the script. The `audit` job now greps for `in self.EDGES` outside the accessor, so no future script can reintroduce it |
| D-A4-3 | The `audit` job's Determinism step failed on `src/rpc/yellowbackwallet.cpp`. Its M11 exclusion was written with unescaped dots (`rpc/yellowback.cpp`) and so never covered A3's file, whose two `GetTimeMillis()` calls are `WaitForCarrier`'s `-yellowbackcarriertimeout` deadline — wallet-tier, user-facing, and no consensus value depends on it | A third home, anchored and escaped, plus a narrower grep asserting `GetTimeMillis` is the only clock symbol in that file. The pure modules' and `index.cpp`'s stricter checks are untouched |
| D-A4-5 | **CI had never run the v3 attestation suite.** `yellowback_attest.py`, `yellowback_attest_enforcement.py` and `yellowback_attest_wallet.py` — the whole of the A1–A3 test evidence — were registered in `qa/pull-tester/rpc-tests.py` but absent from `YELLOWBACK_SCRIPTS`, and all three were non-executable, which the runner (it `exec`s each script directly) turns into `PermissionError` before the framework starts. The identical omission is already recorded in the workflow for mining/enforcement/stock_node/hardening on 2026-09-11; it recurred for v3 | All three `chmod +x` and added to `YELLOWBACK_SCRIPTS`. The `audit` job now walks `qa/rpc-tests/yellowback_*.py` and fails on any script that is not executable **or** that no job runs, so neither half can recur |
| D-A4-4 | A `seq` is assigned on chain in the order registrations land in their block, **not** in node order: the devnet's node 6 drew seq 0 and node 5 drew seq 2. Reading `node7` as `seq 7` misreads every status line | `status` and the `attestor` command messages print the seq beside the node |

Two further traps cost a run each while writing `yellowback_attest_agent.py`, both recorded in
`docs/mapping.md` §14.1: `two_step` appends `wait` after whatever arguments it is given (so every
positional before it must be passed, and it returns the RPC's full result dict, not a txid), and
the regtest price is not a convention — `yellowback_attest_wallet.py` uses $50 while
`yellowback_attest.py` uses $0.50, and the collateral a mint needs scales inversely.

The devnet's `check` was also confirmed to fail correctly: after `price 1.00` crashed the quote
98 %, it reported halted minting and a pool off eligibility while the attestation half still
passed — the v2 half of `check` judging a chain deliberately broken, not a false green.

---

### 6.2 Found by walking the roles (2026-09-20)

The role-based regtest tooling (`docs/plans/role-based-regtest-plan.md`, §8) ran the simulated
economy — six personas, a heartbeat, a price walk, a −70 % shock — on the finished A0–A5 code.
Its findings that are product defects, not tooling, graduate here for A6:

| # | Found | For A6 |
|---|---|---|
| D-R-1 | **The claimant's node segfaults on the two-step RPC that follows a clause-(b) claim** (regtest plan F-7). Reproduced twice: the liquidator's `yed_claim` by RED-4 clause (b) returns success (committed and logged as relayed) and the next `yed_claim` or `yed_claimnotice` on that node, a few hundred milliseconds later, dies in `CWalletTx::IsTrusted` → `CWallet::IsMine` reading `parent->vout[0]` of a wallet transaction whose `vout` is empty (`EXC_BAD_ACCESS` at `0x8`), reached from `yellowback::Context::SelectYec` → `AvailableCoins`. Clause-(a) claims never crashed. The crash lands before the claim leaves the node: network-wide the vault stays ACTIVE with the notice standing, and `notice-standing` blocks a fresh notice for `EMERGENCY_NOTICE_TTL` blocks — a liquidator who crashes here loses both the claim and the window | **Fixed 2026-09-20.** Cause: the frozen `CWallet::CommitTransaction` indexes `mapWallet` by every input's txid (`mapWallet[txin.prevout.hash]`, safe upstream where a wallet spends only its own coins) and so inserted a blank `CWalletTx` under the vault's id. Fix on the fork's side: `YellowbackWallet::Commit` wraps `CommitTransaction` and erases the blank entries it leaves for inputs the wallet never held; both fork commit sites use it. Regression case in `yellowback_attest_wallet.py`; the `user` preset of `yellowback_devnet_roles.py` is green. The A6 review should still read `wallet.cpp` for other `mapWallet[...]` reads on a foreign input — `GetAddressGroupings` is guarded by `IsMine(txin)`, `MarkAffectedTransactionsDirty` by `count()`; nothing else was found |
| D-R-3 | **The global-ratio halt stopped every mint, including the ones that would have repaired it** (Scenario 1 step 6: "if minting is globally halted, it is very difficult for the system to recapitalize; it just sits there stagnant"). Every class minimum exceeds the 250 % floor, so no mint can lower the ratio and the rule forbade only improvements | **Decided and applied 2026-09-21 as W16**: `RECAP_RATIO_BPS` = 50,000; under the halt a mint is accepted iff its class minimum ratio reaches the floor — class A on every network. Owner chose 2× over 1.5× (class B too) and 1× (every class) |
| D-R-4 | Wallet findings from the same walk (regtest plan F-9 to F-12): clipped long values on the Overview and Mint pages, no per-vault collateral ratio, a self-send shown as "Sent $0.00", a stale "Minted" line | **Fixed 2026-09-21** in `yecwallet-dd`: wrapped form rows and growing labels (a layout QTest guards it), **Ratio now** and **Underwater below** columns on Positions, a **self-transfer** label, the status cleared two blocks on. Five new QTest cases |
| D-R-5 | **`claimable` is node-local under the fallback.** `EstimateClaim` judges RED-4 clause (b) with the bundle this node's pool can build; when it cannot (`bundleOk` false) `pEmerg` falls back to the cross-section `xClaim`, so a vault the attested price has put deep underwater reads "not claimable" on a node whose pool is empty or stale, while a claimant with a fed pool claims it (seen on the owner's own vault: attested $3 against a cross-section of $40, claimed by clause (b)) | For A6: report the fallback on the row (`claimEstimate: "pool" \| "cross-section"`) so wallets can say "this node cannot judge the emergency clause: run a subscriber", and consider judging (b) from the standing notice's recorded `pEmerg` when no bundle can be built |
| D-R-6 | Owner decision 2026-09-21: the mainnet grace period stays at 30 days (`GRACE` = 34,560); the wallet makes the deadline visible (regtest plan F-17) rather than the protocol lengthening the window an underwater vault sits unclaimable | none; a second walk with the Act-by column in place revisits the number |
| D-R-7 | Owner decision 2026-09-22: **YecWallet's YEC/USD rate is the Yellowback protocol price** (the pools' fast median at the tip) whenever the node is enabled, activated and has one; CoinGecko is the fallback (pre-activation, undefined price, or a protocol price older than 15 minutes). One market, one number, across the Balance tab and the Yellowback tab (regtest plan F-23) | Wallet only (`Settings::setYellowbackPrice` / `setCoinGeckoPrice`, the controller's push on every stats and activation reply); no node change |
| D-R-8 | **A rally paused minting for a whole slow window.** After a +100 % shock MINT-10 compared the attestors (at the new price) with `xMint`, the minimum of the windows, still at the old price for 64 blocks (2,016 on mainnet ≈ 42 h) | **Decided and applied 2026-09-22 as W17**: MINT-10 reads `pFast(R)`; collateral is still sized at the minimum |
| D-R-2 | On regtest the emergency tier (`EMERGENCY_PERSIST = 4`) and the ordinary claim open within a few blocks of each other after a shock, because the price windows are 8/24/64 blocks; on mainnet the emergency tier leads by hours (48 vs 576/2,016) | none; a note for whoever reads a regtest walk-through as if it were mainnet timing |

## 7. Test plan (v3 additions)

| Layer | Location | Covers |
|---|---|---|
| Unit | `yellowback_attest_tests.cpp` | message, codec, compact low-S verify, Python known-answer vectors |
| Unit | `yellowback_bundle_tests.cpp` | codec, sizes, extraction from every input position and both carrier modes, `VerifyBundle` order and every reason (BUNDLE-1) |
| Unit | `yellowback_script_tests.cpp` (+) | carrier and bond scripts under `VerifyScript`, `IsStandardTx`, `AreInputsStandard`; the 521-byte push |
| Unit | `yellowback_payload_tests.cpp` (+) | v3 types and sizes; version-2 rejection |
| Unit | `yellowback_math_tests.cpp` (+) | weight, quantile boundaries, residual, attestor fee, combine |
| Unit | `yellowback_state_tests.cpp` (+) | one tagged case per new or changed identifier (A1 list); undo identity; overlay equivalence |
| Unit | `yellowback_index_tests.cpp` (+) | pool add/replace/freshness, `BuildBundle` missing set, cache hit/miss, schema rebuild |
| Unit | `yellowback_txbuilder_tests.cpp` (+) | every v3 template's shape, both funding modes, carrier top-up, dry-run refusals |
| Functional | `yellowback_attest.py` | the core flow (A2 list): arming, bundles, VOID reasons, pinning, emergency claim, residual, equivocation, dormancy/revival, withdrawal, model match |
| Functional | `yellowback_attest_enforcement.py` | RED-1/5 rejection against a stock miner armed; DoS 0; valve; v2 cases unarmed |
| Functional | `yellowback_attest_wallet.py` | every wallet RPC of §4.5; carriers; restore; H5 |
| Functional | `yellowback_rpc_contract.py` (+) | v3 commands, fields, error identifiers |
| Functional | `yellowback_index.py` (+) | schema rebuild, kill9 with new tables, reorg across arming |
| Functional | v2 flow scripts `--armed` | the v2 lifecycle under v3 rules |
| Functional (nightly) | `yellowback_attest_agent.py` | the Rust agent end to end on `dir://` |
| Functional (nightly) | `yellowback_attest_stress.py` | randomized arming/outage/equivocation/reorg |
| Functional (release) | `yellowback_rc2.py` | rc run-through with arming, emergency claim, ejection, withdrawal |
| Fuzz | `YellowbackBundle` (new), `YellowbackPayload` (+), `YellowbackEvaluate` (+) | codec robustness; totality with carriers and bundles |
| Model | `yellowback_model.py` (+) | every new snapshot field and table; `Selected` in Python; bundle statistics via `yed_gettxinfo` |
| Agent | `cargo test` in `contrib/yellowback/attest/` | aggregator port vs Python fixtures; transport `dir` round trip; message framing |
| Application | `yecwallet-dd` QTest | offline cases per §4.8; devnet case ARMED |

Rule-tag loop: every identifier in §3.8 appears verbatim in a `// Rule:` / `# Rule:` tag; the
`audit` job's loop is extended with the v3 list.

---

## 8. Trust statement delta, threat model, review checklist

### 8.1 Trust statement (delta, to be published with v3)

v2's paragraph "price honesty rests on the honest-majority-hashpower assumption" becomes:

> Prices come from two populations that cannot forge each other: mining pools, weighted by
> blocks, and bonded attestors, weighted by bond and age. A mint is sized at the lower of the
> two; a claim opens at the higher. Moving a price in the direction that pays therefore needs a
> majority of hashpower and a bond-weighted majority of the selected attestors at once. A
> hashpower majority alone keeps exactly the powers it has today — it can halt minting, delay or
> censor transactions, and reorganise the chain — and gains none. A captured attestor set alone
> can halt minting or force an early liquidation at an honest price with the remainder returned
> to the owner; it cannot take collateral. Attestors are not slashed: their penalty is ejection
> and a bond that earns nothing until it unlocks. Attestations travel outside the chain; if that
> transport fails, minting pauses and nothing else changes. Every YEC/USD price is bounded by the
> depth of the markets it is read from.

### 8.2 Threat model (rows added)

| Threat | Outcome in v3 | Mitigation |
|---|---|---|
| Attestor set colludes high | mints unaffected (`min`); normal claims held shut for at most the 110 %→105 % gap | the emergency tier fires from the pools' `xClaim` (RED-4b) |
| Attestor set colludes low | mints over-collateralized; emergency notices on healthy vaults | a clause-(b) claim pays exactly the debt at `pClaim = max` — the 10 % margin exists only when the pools agree (R1) — and returns the rest; two steps an hour apart; the owner is warned |
| Pools and attestors both captured in one direction | price moves | the chain's standing majority assumption plus a bonded, aged, visible set; §7.5 overlap disclosure |
| Aggregator correlation | several attestors move together | source-tier flag; venue-median guidance; PIN-1/2 catch a frozen aggregator |
| Pinned pool quotes | claims held shut | PIN-1 excludes frozen keys from medians and `E(R)` when attestors moved |
| Pinned attestors | `aMint` frozen | PIN-2 excludes them from selection and fees |
| Bond-weight capture | a new entrant buys the set | age weighting (`AGE_CAP` ≈ 6 months), founding cohort, `BOND_MIN`, `Q` thresholds needing two parties |
| Selection grinding (40 `refHeight` draws) | a friendlier selected set | the mint selector is empty, so `ownerPubKey` cannot be ground (S13); the claim selector is the fixed vault outpoint; bounded by `min`/`max` against the pools (D-5) |
| Carrier malleation in relay | a different bundle substituted ⇒ the mint VOID with collateral locked for the term | impossible: the carrier's redeem script commits `SHA256(bundle)` and is covered by the sighash and the P2SH hash (R2, W7) |
| Bundle verification cost under spam | ≈ 20k signature checks, 1–2 s, per stuffed block on enforcing nodes | signatures verified only after MINT-1..8 (a real vault output and `FEE_MIN` to a pool per transaction, R15); per-attestation cache; measured in A6; stock nodes unaffected |
| Notice reset by the vault owner | emergency clock never runs | a standing notice is never replaced (NOT-1) |
| Notice spam | table growth | one record per ACTIVE vault; deleted on close |
| Ejected attestor re-registers | the operator returns under new keys with the same capital | the key and the outpoint are barred (REG-A1, IN-2); the operator is not — there is no identity — and pays a new bond, a new maturity and a new age climb from zero |
| Unseated attestor "dormant" | honest capital ejected | dormancy needs selection evidence (W12) |
| Dormant attestor stranded | cannot return | `ATTESTOR_REVIVE` (REV-1) |
| Transport (relay) failure | minting halts | manual `bundleHex`; several relays; HTTPS second path; never soundness |
| Subscriber feeds junk to the pool | pool pollution | `yed_addattestation` verifies signature, `seq`, freshness; RPC-auth only |
| Reorg drops a cited block | bundle stale | identical exposure to `refHeight` (proposal §8.5); wallet resubmits with a fresh bundle |
| Automatic arming by a small friendly set (D-4) | the layer arms before diversity | real matured bonds, the day's notice, displacement, grief-only bound; a release can override |
| A v2 node meets v3 payloads | ignores them | V23; nothing on mainnet yet |
| A minter or claimant who is also a selected attestor pays the attestor fee to itself | no net fee on its own transactions | accepted, as v2's K23 for pools; no soundness effect |
| Hot attestor key stolen | the thief signs prices | bounded like a colluding attestor (grief); equivocation by the thief ejects the seat; the bond key is separate |

### 8.3 What Yellowback cannot affect — unchanged.

### 8.4 Review checklist (v3, Phase A6)

1. `git diff feature/yellowback-sf...HEAD -- $(cat qa/yellowback-frozen-files.txt)` is empty
   (mechanical, `audit` job; the list is §4.1's frozen set).
2. Determinism grep empty over the §3.10 set; `secp256k1` reached only through `VerifyCompactSig`.
3. Every v3 rule identifier tagged (§7 loop); every functional flow has a script.
4. BUNDLE-1 reasons all reachable and tested in W8 order; high-S rejected; cache never changes a
   verdict (`cache_hit_equals_cold` test).
5. Apply/undo identity and cold-rebuild equality with every new table under
   `yellowback_attest_stress.py`.
6. `IsStandardTx`/`AreInputsStandard` pass for every v3 template incl. a claim with carrier,
   residual and both fees, and a `ys1…` claim.
7. `yellowback_stockparity.py` and `yellowback_stock_node.py` unchanged: a stock node relays every
   v3 template.
8. The golden vector reproduced by C++ and Python at the pinned regtest keys; the model matches
   `full=True` at the end of every v3 script.
9. Fail open on storage only: the new tables under the same BLK-3 boundary (`storage:` fault at a
   `BundleLog` write accepts the block and sets unhealthy).
10. Coin locking covers carriers and bonds across restart, rescan and reorg; `lockunspent`
    refuses them; `sendtoaddress` never spends them.
11. `ConnectBlock` cold-cache verification of a 3,000-carrier block measured and recorded.
12. The trust statement delta published verbatim; the proposal's §17 residuals each have a
    threat-model row.
13. `doc/yellowback-rpc-contract.json` identical in both forks; the wallet's field check green.
14. The Rust agent builds with `--locked` on the pinned toolchain from a clean checkout; no crate
    from it appears in the node's `Cargo.lock` or `depends/`.

---

## 9. Upgrade path — enshrinement (design constraint only)

At a Ycash network upgrade: the bond becomes slashable (a covenant or a consensus rule over
`Attestors`), heartbeat or bundle inclusion can become block validity, and the `OP_RETURN`
layout behind `BUNDLE_CARRIER` becomes the natural carrier if relay policy has moved. Nothing in
v3 forecloses any of these; nothing in v3 requires them.

---

## 10. Deviations from the proposal (revision 6)

The proposal was updated in place on 2026-09-13 to match this plan on four points of precision
(MINT 68 bytes, CLAIM_NOTICE 57 bytes with `vaultTxid ‖ vaultVout`, regtest `ATTEST_ARM_MIN = 3`,
`Attestors` keyed by `seq`). What remains is additive:

| Proposal | This plan | Why |
|---|---|---|
| Selection "the FEE-W draw repeated" (§8.4) | written out with per-round seeds (W9) | determinism needs the exact procedure |
| `yed_signattestation` not mentioned (§13) | added; the agent never holds a key | the hot key stays in the node's wallet, as the quote agent never holds one |
| Bundle committed by `bundleHash16` in the payload (§8.1) | committed by the carrier's redeem script; per-transaction carriers, one confirmation before the main transaction (W7, R2) | a scriptSig-only commitment let any relay node void a mint and lock its collateral |
| Emergency claims pay the 110 % cap (§10.3) | a clause-(b) claim pays exactly the debt at `pClaim` (R1) | otherwise a captured attestor set collects the margin from every vault |
| `ATTEST_MAX_AGE = REF_WINDOW` (§15) | 20 blocks (R4) | at most two signed prices per attestor per bundle window |
| Residual formula with `10⁴` (§10.3) | without (R5) | unit error; v2's worked example |
| Verified-bundle cache filled "from mempool acceptance" (§8.2) | filled by MP-1, the template filter and `ConnectBlock` (W8) | MP-1 never sees mints (V3) |

---

## 11. Inputs required at launch (operational)

1. ≥ 5 committed attestors with distinct source sets and 20,000 YEC each; at least one exchange.
2. ≥ 2 independently operated `iroh` relays; the relay list in the release config.
3. The two calibration results (proposal §16) from ≥ 2 weeks of live data.
4. An explorer page over `yed_listattestors` with overlap disclosure.
5. The Ycash maintainers informed of the separate relay-policy and toolchain recommendations.

---

## 12. Open questions

1. **Per-pool cross-section** (proposal §7.1): deferred; revisit with testnet data.
2. **Signed coinbase tags** (v2 §12 Q14): `ATTESTOR_REGISTER` is the precedent; not in v3.
3. **Attestor fee share** (25 %): a testnet parameter; revisit if attestors report it does not
   cover operation or minters report it deters minting.
4. **`AGE_CAP` and `FOUNDING_WINDOW`**: placeholders; a testnet parameter.
5. **Light clients**: `lightwalletd`'s `GetAttestations` is outside both forks; not scheduled.

---

## Appendix A — Rows for `docs/mapping.md`

| Mechanism | DigiByte (`ref/digibyte`) | Ycash (`ref/ycash`) | v3 adaptation |
|---|---|---|---|
| Oracle bundle carrier | `OP_RETURN OP_ORACLE …` coinbase output (`src/oracle/bundle_manager.cpp:816-829`) | 80-byte `OP_RETURN` relay policy (`policy.cpp:51-53`); 1,650-byte push-only scriptSig (`:92-99`); P2SH inputs: sigops (`:178`) and the scriptSig pushes evaluated (`:156` → `interpreter.cpp:277`, the 520-byte cap at relay) | scriptSig carrier input (§3.4) |
| Oracle signatures | Schnorr / MuSig2 (`src/oracle/`) | `configure.ac:1282` enables `recovery` only | compact ECDSA via `VerifyCompactSig` |
| Oracle staking / slashing | none in DigiByte either | no covenants | CLTV bond, ejection only |
| Oracle set selection | DigiByte's fixed registry | — | bond-weighted seating, hash-selected bundle (W9) |
| Data push limits | Taproot annex/witness | `MAX_SCRIPT_ELEMENT_SIZE = 520` at execution only (`script.h:23`) | `BUNDLE_MAX = 6` |
| Wallet ownership of script outputs | descriptor wallets | `IsMine` recurses only into standard redeem scripts (`ismine.cpp:76-86`) | carriers and bonds tracked by the Yellowback wallet layer, signed by hand (W7) |

## Appendix B — Glossary (additions)

**Attestor** — a bonded party whose signed prices form source B. **Bundle** — up to six
attestations carried by a mint or claim. **Carrier** — the P2SH input that carries the bundle.
**Seated** — among the `N_SLOTS` highest-weighted eligible attestors at a height. **Selected** —
the `M_SELECT + K_SLACK` seated attestors a given transaction must draw from. **Arming** — the
height from which bundles are required. **Notice** — step one of an emergency claim.
**Residual** — collateral above the claimant's cap, returned to the owner. **`xMint`/`xClaim`** —
v2's pool medians; **`aMint`/`aClaim`** — the bundle quantiles; **`pMint`/`pClaim`** — the
combined prices every rule reads.
