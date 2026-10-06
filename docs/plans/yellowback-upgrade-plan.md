# Ycash Yellowback (YED) and Wrapped Ycash (wYEC) — one agnostic primitive, two applications, one rule module

**Revision 2 (2026-10-05): implementation opened (P2, P3-node, P4, devnet).** Revision 1 was
the plan as promoted; revision 2 adds the **execution status** block directly below and the
byte-level **implementation specification, §15**, which every implementing agent builds against
on both node lines. Where §15 had to make a choice §3–§5 left open or decide differently, it says
so in §15.0 (decisions U-9..U-20). Promoted from
`docs/ideation/` (its revision 3, same day) by owner decision: the Ycash Foundation is still
ideating its lock/unlock primitive and has not written a spec, so **this plan proceeds on stated
assumptions about the primitive (§0) and it is Yellowback's responsibility to build out what the
primitive plus two applications can be.** Every assumption is marked so it can be replaced by the
Foundation's text when it exists. Builds on the
[evidence-based hardening plan](yellowback-evidence-based-hardening-plan.md) ("the hardening plan",
revision 1) and the delivered [v3 design](yellowback-v3-development-plan.md) ("v3", revision 4);
both still apply where this plan does not amend them. Items are numbered **U-\*** (decisions),
**O-\*** (owner and Foundation decisions), **A-\*** (assumptions), and phases **P0–P8**.

## Execution status (authoritative; update as work lands)

**Goal of this round (owner, 2026-10-05):** the primitive in `ycash-dd` and `ycash6`, functional on
the devnet / regtest, and the Yellowback system running on it (the YED module). P1 (hardening, as
reshaped by §7) is **in** this round by owner instruction: its node chunks land first on
`harden/yellowback` (both lines) and are merged into `upgrade/vault` before P4 opens, because P4
rewrites the same `src/yellowback/` files; P2 runs in parallel with P1 (new files and consensus
files only). P5 (the `wyec` contract and daemon, external audit) and the Ethereum half of P3 are
not in this round. The owner's instruction was to execute without questions:
open points are recorded here and in §15.0, never blocked on.

**Branches.** Integration branch `upgrade/vault` in `ycash-dd`, `ycash6` and `librustzcash6`,
cut from each repo's `harden/yellowback` and integrated in the worktrees `wt/up-dd` and `wt/up6`
(the main trees stay on `harden/yellowback`, so `make status` is unaffected). Each agent works in
`wt/<name>` on `up/<name>` off `upgrade/vault`; the coordinator merges. Briefing for agents:
`wt/BRIEFING-upgrade.md`. Client repos (YEW, yolo, x402, chain-viz, YecWallet, lightwalletd) use
`upgrade/vault` branches off `harden/yellowback` when they need a change.

Legend: `[x]` done and verified on the integration tree, `[~]` in flight (agent / branch named),
`[ ]` not started, `[-]` deliberately out of this round.

### P0 decide
- [x] Plan promoted with §0's assumptions (revision 1)
- [x] Implementation spec §15 written (revision 2); U-9..U-20 recorded
- [ ] AGENTS.md §9 amendments: **awaiting the owner** (the session's edit of AGENTS.md was refused by its permission
  classifier; the amendments are in force for agents through `wt/BRIEFING-upgrade.md` meanwhile)
- [-] Foundation's written primitive, O-9, O-12, O-13 values (theirs; §15 uses regtest values)

### P1 hardening (hardening plan §9 as reshaped by §7) — on `harden/yellowback`, both lines
| Chunk | Content | ycash-dd | ycash6 |
|---|---|---|---|
| H0-a | mapping §21 rows, plans README row, v3 §8.2 rows, `make spec` | [x] | — |
| H0-b | `yb-calibration` policy `harden-2026-10.toml`, empty-class convention | [x] `3e6e4ae` (1038 tests) | — |
| H1-a | F-1 wallet spent-tracking, F-5 mainnet heights unset | [x] `fa6768f85` | [x] `5752fd0e3` |
| H1-b | F-2 agent sample configs and defaults | [x] `fa6768f85` | [x] `5752fd0e3` |
| H3-a+ | H-1 `mintRequiresArmed`; params H-2 (arm 7), H-4 (15 / 5,000 bps), H-5 (class A only), H-10, H-11 (300 / 600 %), H-12 (`maxMint` $2,500) | [x] `6e1df81ad` | [x] `6cb6753b3` |
| H3-c | H-9.3 RPC bounds, contract JSON, `rpcversion` 4 | [x] `fa6768f85` | [x] `5752fd0e3` |
| H4 | calibration re-runs under H0-b (≈ 6 h per standard run) | [ ] **deferred (owner, 2026-10-05)**: reduced run done (`docs/reports/2026-10-harden/`); full sweeps stopped and run only once both node lines are built and green end to end (P4 + devnet done), on the existing frozen snapshot `data/local/frozen-20261004` plus the live spreads log — no data re-pulls | — |
| H5 | wallets — rpcversion 4 + new fields: YecWallet `78ea158` [x] (108 QTest + 4 devnet cases; renew flow; client plausibility); lightwalletd `916d836`, chain-viz `4b010df` (NO_PRICE-hours counter; coalition/valve panels not built — retired), x402 `756b045`, YEW `4a93c12` [x]; YEW H5-b deadlines/plausibility `acb7f1a` [x] (stale mainnet constants fixed; trust text wording changed — owner to review) | [x] | — |
| merge | `harden/yellowback` → `upgrade/vault` (gate for P4) | [x] `4e4ae0b13` | [x] `ed0806d65` |
Retired by §7 and not done: H2 (valve), H3-b's lock-in and sunset parts, F-3, H-9.1.

**H4 reduced result (2026-10-05, `yb-calibration/docs/reports/2026-10-harden/`, REDUCED — owner decisions
needed when the full run confirms):** the worse-window rule (H-3) gives class A `baseRatioBps[0]` =
**192,500 (1,925 %)**: 725 % suffices on full history but last-365-day bootstrap needs 162,500–192,500
(bad-debt 3.8–4.9 % at 725 % against 0.5 %). Consequences: 0.052 YED per USD locked; a `minMint`
round trip costs 7.2 %. Contradictions with hardening values: H-4's fee arithmetic (2.72 % round trip at
725 %, seat ≈ $41/month vs the $50 floor); H-11's 300 % halt fails `halt_sys_bad` (2.9 %; class A only
means a 0.5 % system tolerance, not 1.6 %); `maxMint` $2,500 fails `maxMint_ok` (environment limit, as
expected); `signalWindow` drifts 2,592 → ~3,168 (moot under the upgrade). These are recorded, not acted on:
the parameter values are the owner's (hardening plan §8).
P1 open defect (2026-10-06, found by `h5-yew`, both lines): `yed_listclaimable.residualZat` omits the
`RESIDUAL_MIN_ZAT` floor that the builder's `ClaimAt` applies (ycash-dd `rpc/yellowback.cpp` EstimateClaim vs
`txbuilder.cpp:917-919`; ycash6 `rpc/yellowback.cpp:2019,2048` vs `txbuilder.cpp:1023`) — reported residual can be
0 < r < 100,000 zat while the builder pays 0. RPC-only; fix with the P4 port.
P1 notes (2026-10-05, `hd-wallet`): F-1 reproduced (30/30 back-to-back mints failed on the unfixed binary, 0/30
with the fix, both lines); F-5 adds `qa/yellowback-release-heights.sh` and a release-workflow guard; the spreads replay
at `min_sources` 2 fails closed 0.18–1.43 % per hour (G-1 should be read from ybcal's per-block replay); `make spec-check`
was red on the client copies until H5 landed; green again since YecWallet `78ea158`.
P1 notes (2026-10-05, `hd-rules`): until H4 sets class A's `baseRatioBps[0]` (H-3 expects ≥ 72,500), mainnet's
current 50,000 is below the 60,000 recap floor, so under a global-ratio halt or above the supply cap nothing
mints on mainnet — safe-side, and moot while F-5 leaves mainnet unset. H-5's refusal is MINT-2's
`bad-mint-lock-height` (no `mint-class-term` verdict exists). `SCHEMA_VERSION` 4 → 5; golden stateHash
`d3d60429…dbd0`. Devnet `--mint-requires-armed` (hardening §10) not yet done.

### P2 primitive — both lines
| Item | ycash-dd | ycash6 |
|---|---|---|
| `UPGRADE_VAULT`, branch ID `0x6d5b7a31`, chainparams, `-nuparams`, Equihash epoch row | [x] `f71eb7ddd` | [x] `91c557ecb` |
| `librustzcash6` `BranchId::Vault` + `ycash6/Cargo.toml` repoint | n/a | [x] librustzcash6 `4867cf85` pushed (`upgrade/vault`); Cargo repointed |
| BIP68 sequence locks + `OP_CHECKSEQUENCEVERIFY` (0xb2) from activation | [x] `f71eb7ddd` | [x] `91c557ecb` |
| `OP_CHECKSETSIG` (0xc0), `OP_CHECKSETDORMANT` (0xc1), checker interface | [x] `f71eb7ddd` | [x] `91c557ecb` |
| `src/vault/`: templates, `YV` act codec, set state, rules, rate limit, slashing, undo, DB | [x] merged `bd33dc0b9` (49 cases / 1432 assertions incl. vector replay) | [x] merged `ae1ab3a3c` (49 / 1432, vectors byte-identical) |
| Module table (empty in P2) + interface | [x] `bd33dc0b9` | [x] `ae1ab3a3c` |
| Hooks: CheckInputs checker, ConnectBlock/DisconnectBlock, mempool, miner, init | [x] `f4b2e2dc6` | [x] `a56cd4e20` (+ miner `TemplateRun`) |
| Policy: templates standard, `YV` OP_RETURN up to 1,200 bytes | [x] `f4b2e2dc6` | [x] `a56cd4e20` |
| RPCs `set_*` / `vault_*` (§15.8) | [x] `f4b2e2dc6` (21 RPCs, `doc/vault-rpc.md`) | [x] `a56cd4e20` |
| Python `test_framework/vault.py` + golden vector `vault_vectors.json` (identical on both lines) | [x] merged `b97a4f994` (33 unit tests; vectors agree with C++ objects, 228/0) | [x] `ae1ab3a3c` (byte-identical) |
| Unit tests `vault_*_tests.cpp` | [x] 65 cases on `99f33ea04` | [x] 65 cases on `a56cd4e20` |
| Functional `vault_upgrade.py`, `vault_primitive.py`, `vault_slashing.py` (CI-registered) | [x] `99f33ea04`: vault_upgrade, vault_rpc, vault_primitive, vault_slashing, vault_bridge all pass | [x] `a56cd4e20`: all five vault suites + yellowback_lifecycle / attest / mint_armed pass |

### P3 bridge template (Ycash side only)
- [x] `WYEC` lock → intent → release / cancel / recovery, both signer shapes, `vault_bridge.py` — ycash-dd `99f33ea04`, ycash6 `a56cd4e20`
- [ ] devnet bridge persona (mock burn feed, no Ethereum)
- [-] anvil / local Ethereum, `wyec/` repo (P5)

### P4 YED module — both lines
| Item | ycash-dd | ycash6 |
|---|---|---|
| P4-a enforcement machinery removed (§6), Yellowback rules consensus at `UPGRADE_VAULT`, DoS 100 | [x] `03161317c` | [~] `up/up-yed6` |
| P4-a YED vault = primitive template (`YED\0`), owner redeem, claim as APP intent, attestor cancel | [x] `03161317c` | [~] `up/up-yed6` |
| P4-a VOID → invalid; module always on at activation; golden vector regenerated, model parity | [x] `03161317c` | [~] `up/up-yed6` |
| P4-b attestor registry on the primitive signer set (`ATTESTOR_REGISTER` retired) | [x] `c025f8f5e`; on the integration tree `a903fae2f` all 28 yellowback_*/vault_* suites pass (chainviz against the P6 chain-viz build) | [~] primitive half (U-25) [x] `07d626235`; YED half after the P4-a port |
| Functional suites rewritten (obsolete enforcement suites removed) | [x] `03161317c`: all 28 yellowback_*/vault_* suites pass on the integration tree (chainviz SKIPs until chain-viz speaks rpcversion 5) | [~] `up/up-yed6` |

### Devnet and clients
- [~] `yellowback-devnet up` on the upgrade (both lines): sets, attestor set, mint, redeem, claim, cancel — ycash-dd up and armed; full walk pending
- [ ] role regtest (`yellowback_devnet_roles.py`) on the upgrade
- [~] P6 clients on `upgrade/vault` branches (not yet merged): lightwalletd-dd `ce5f40e` [x] (rpcversion 5; read-only
  GetVaultInfo/ListSets/GetSet/ListVaultOutputs; devnet incl. byte-equality gate green on wt/up-dd); yolo `af66b6e` [x]
  (no source change; mines across the activation; yellowback_stratum green); chain-viz `b4eb44b` [x] (rpcversion 5 tolerant, set/vault
  panels, cancel detection; 61 tests, ui-smoke 22/22 on a devnet); x402 `8daa6fb` [x] (light path signs for the next block's branch via GetChainInfo; Vault vectors; 865 TS + 418 Py + Rust; devnet on wt/up-dd); YecWallet `p6-wallet` [~]; YEW `ae1c69e` [x] (Rust signer builds V/I spends with 0x6d5b7a31, checked against the golden vectors; 120 Rust + 67 Flutter; devnet W2, W4, attestor cancel; release via its own gate blocked by finding (56))
- [x] `yellowback-devnet up` on ycash-dd's upgrade line, attested and `--no-attest` (first exercised by p6-light);
  `lwd-rawmint` fixed for U-23 (`7ea838c4d`). ycash6 devnet pending the P4 port.
- [x] `docs/mapping.md` §22: P2 rows and P4 rows (ycash-dd citations; ycash6 citations after its P4 port); contract
  generator for the upgrade line + `make spec-check-upgrade` (`382d1dc`). Open: the −32601 text in
  `src/rpc/yellowback.cpp:70` still names `-experimentalfeatures -yellowback` (both lines)

### CI/CD (owner request 2026-10-06; design in `wt/BRIEFING-upgrade.md` "CI/CD design")
Every repo: triggers on `harden/yellowback`, `upgrade/vault`, `main`; push tier ≤ 25 min warm (build once,
sharded functional matrix from one artifact), nightly variants and cross-repo devnets, weekly fuzz; exact cache keys;
SHA-pinned actions; actionlint + zizmor clean. Node-line audit on `upgrade/vault`: frozen/budget legs report-only
(G-9 review gate), consensus-diff artifact, DoS rule, rpcversion 5 contract via the generator, cross-line vector
identity. Branches `ci/harden` and `ci/upgrade` per repo; the coordinator pushes and reads the runs.

| Repo | Agent | `ci/harden` | `ci/upgrade` | pushed + green |
|---|---|---|---|---|
| ycash-dd | `ci-dd` | [~] | [~] | [ ] |
| ycash6 (+ release workflow, upstream workflows scoped) | `ci-6` | [~] | [~] | [ ] |
| librustzcash6 | `ci-6` | — | [~] | [ ] |
| yew, yolo, chain-viz, x402-ycash | `ci-rust` | [~] | [~] | [ ] |
| yecwallet-dd, lightwalletd-dd | `ci-misc` | [~] | [~] | [ ] |
| yb-calibration, workspace | `ci-misc` | [~] | — | [ ] |

### P1, P5, P7, P8
- [-] P1 hardening (own plan) · [-] P5 wyec · [-] P7 gates · [-] P8 release

### Log
- 2026-10-05: revision 2; spec §15; integration branches `upgrade/vault` cut (ycash-dd, ycash6, librustzcash6) with
  integration worktrees `wt/up-dd`, `wt/up6`; wave 1 dispatched: `up-core-dd`, `up-cons-dd`, `up-cons6` (+`up-rz6`),
  `up-pyfw`, `hd-rules`, `hd-wallet`, `hd-cal`. Owner: include P1.
- 2026-10-05: P2 complete on ycash-dd (`99f33ea04`): library, plumbing, hooks, RPCs, 65 unit cases, five
  functional suites green with yellowback_lifecycle / yellowback_attest / yellowback_mint_armed. ycash6 has library +
  plumbing (59 cases, vault_upgrade green); hooks/RPC port `up-int6` and P4-a `up-yed-dd` in flight.
- 2026-10-05: **P2 complete on both node lines** (ycash6 `a56cd4e20`: 65 vault unit cases, all five vault functional
  suites and the Yellowback regressions green). P3's Ycash side complete on both lines. P1 node chunks complete.
- 2026-10-06 (wave 6, owner asked to widen parallelism): seven agents in flight — `up-yed6` (P4-a → ycash6),
  `up-p4b6-prim` (P4-b's primitive hook → ycash6, in parallel with P4-a), `devnet-dd` (full ecosystem walk on the
  upgrade + the P3 bridge persona), `docs-tooling` (contract generator for the upgrade line, mapping §22 P4 rows),
  `dd-polish` (cancel from the mempool, vault RPC contract, fuzz corpus, signalling wording), `p6-wallet`, `p6-yew`.
  Waiting on them: P4-b's YED half on ycash6 (after `up-yed6`), the ycash6 devnet and client runs against `wt/up6`.
- 2026-10-06: **P4-a and P4-b complete on ycash-dd** (`a903fae2f`): all 28 functional suites, devnet_roles presets,
  chain-viz against the node. P6: lightwalletd, chain-viz, x402, yolo done on `upgrade/vault` branches (unmerged);
  YecWallet, YEW and the ycash6 P4 port in flight.

## 0. Assumptions about the Foundation's primitive

Stated once, numbered, each with what happens if the Foundation decides otherwise. Where this plan
says "the primitive", it means §3 as assumed here.

| # | Assumption | If the Foundation differs |
|---|---|---|
| A-1 | The primitive is a **vault output** with unlock, cancel and owner branches, parameterised by a signer set, a delay and an owner key (§3.1) | a different template changes §3.1 and the wallets' vault recognition; nothing in the module |
| A-2 | **Signer sets are a consensus object** with bonds, threshold, cancel, rate limit, slashing and liveness (§3.2–§3.7) | if sets are plain multisig, rotation, rate limit and slashing move into each application, and the bridge is no longer module-free; the plan would be re-cut |
| A-3 | **BIP68 / CSV** relative timelocks are part of it (§3.3) | if absolute CLTV only, intents carry an explicit maturity height set at creation; weaker but workable |
| A-4 | The primitive carries an **opaque application tag** and a compile-time **module table** (§3.8) | if declined (O-12), YED runs the fallback of §5.4: collateral in consensus, dollar rules in the overlay |
| A-5 | The bridge signer shape is the Foundation's (O-9); this plan designs for **both** the single-relayer-plus-challengers and the 9 / 6 / 7 rows (§4.2) and tests both | none: whichever they pick is a parameter row |
| A-6 | Opcodes are allocated above `OP_NOP10`, gated on one new branch ID, on both node lines (§3.9, §8) | an opcode allocation of theirs is adopted as given, never `0xbb`–`0xbf` |
| A-7 | R1–R3 are firm (O-1) | if R2 is relaxed, the ZK path of §14 is reconsidered for the bridge only; YED is unaffected |

What this plan shows the Foundation: the primitive of §3 as a complete, testable spec; the bridge
running on it with zero application code in consensus (§4); and a second application that needs
exactly one registered module and why (§5). P2 delivers the primitive with **no application** on
both node lines first, so the Foundation can evaluate the generic part on its own.

**The premise.** The Ycash Foundation has set three requirements for a bridge, which the owner
has confirmed as firm and as covering Yellowback's collateral too (O-1). In this plan's words:

- **R1, Ethereum-failure tolerance.** Ycash keeps working, unchanged, if Ethereum stops, forks or
  the contract disappears, and vaulted YEC stays recoverable.
- **R2, rules independence.** Ycash consensus never reads Ethereum data or state. The Ethereum
  contract may carry Ycash identifiers but never interprets them. An upgrade on either chain
  cannot break the other's rules.
- **R3, miners enforce, miners do not vote.** Every bridge rule on Ycash is a consensus rule that
  every full node checks; miners keep only ordinary transaction selection.

The Foundation has also expressed a design preference: the consensus change should be a generic
lock and unlock facility, agnostic as to application, with wYEC as one application of it and YED
as a possible other.

**The owner's position.** Yellowback is one collateralised dollar on Ycash, not a toolkit. The
dollar's rules (who may mint, at what price, who may take a bad vault's collateral) must be checked
by every full node, not by pools that opt in. Price attestation stays **multi-party** (bonded
attestors, a bond-weighted quantile), whatever signer shape the Foundation chooses for its bridge.

**The reconciliation, in one table** (agreed 2026-10-05):

| | Bridge (wYEC) | Dollar (YED) |
|---|---|---|
| Uses the generic vault | yes | yes |
| Uses a registered signer set | guardians | attestors |
| Uses delay, cancel, cap, slashing | yes | yes, for the claim path |
| Needs consensus to know the application | **no** | **yes**: the rule module |

**Reading map.** §0 the assumptions. §1 the decision in one page. §2 R1–R3 as design rules. **§3 the primitive: what
is generic, element by element, each with its tier and why no cheaper tier does.** §4 the bridge
as an application with no module. §5 Yellowback as an application with a module. §6 what the
upgrade removes from v3 and what closes by construction. §7 the hardening plan: kept, reshaped,
retired. §8 activation plumbing on both node lines. **§9 the working rules that change
(AGENTS.md amendments, proposed).** §10 tier, trust statement, what is given up. §11 threat rows.
§12 sequencing. §13 decision record. §14 rejected.

---

## 1. The decision in one page

1. **The primitive is the Foundation's and it knows no application.** A vault output, registered
   signer sets with bonds, a relative timelock, a cancel branch, a rate limit, equivocation
   slashing, a liveness test, and an opaque application tag. Script gains two opcodes. Nothing in
   it says "price", "dollar", "Ethereum" or "burn". (U-1)
2. **The bridge is a script template on the primitive and nothing else in consensus.** Lock to a
   vault; unlock by the guardian set after a delay unless a member cancels; rate-limited; owner
   recovery on guardian silence or a long timelock. The Foundation's preferred single-relayer plus
   challenge-window shape and the owner's 9-of-6 shape are **parameter choices of the same
   primitive** (§4.2). Everything that makes it a bridge is in the contract and the daemon. (U-2)
3. **Yellowback is a second application, and the only one that registers a rule module.** Its
   vaults, attestor set, claim delay, cancel, cap and slashing are the primitive's. Its dollar
   rules (mint, price, ratio, supply, transfer, claim-by-burn) are a module the upgrade ships,
   invoked by consensus only for vaults tagged `YED`. That module is the delivered v3 overlay's
   rule set with its enforcement machinery removed. (U-3)
4. **Why the module exists.** A dollar's safety rule is "the spender burned this vault's debt at
   an attested price". That is a statement about ledger state, not about signatures. An agnostic
   primitive cannot check it; a bonded set signing it would make the price oracle a custodian
   (v3 §1.6 forbids exactly that). The module is the smallest thing that gives YED full-node
   verification. (U-4)
5. **R3 is met for both.** Every bridge rule is the primitive. Every YED rule is the primitive or
   the module. Pool signalling, lock-in, the sunset, the valve, the ENFORCEMENT halt and VOID
   verdicts cease to exist. (U-5)
6. **R1 is the primitive's liveness test.** A set that posts nothing for a window is dormant, a
   Ycash-native fact; the owner branch of every vault opens. A dead Ethereum, a lost contract and
   a vanished guardian set all look the same to Ycash. (U-6)
7. **The fallback is built in.** If the Foundation ships the primitive and declines the module,
   the bridge is unchanged and YED runs with its collateral in consensus and its dollar rules in
   today's overlay (option A1 of the 2026-10-05 discussion). Same vaults, same attestors, same
   wallets. (U-7)
8. **The hardening gates still come first.** The upgrade fixes every enforcement finding. It does
   nothing about one pool setting every median, bad-debt classes, thin venues or quote
   availability. A dollar rule in consensus that mints on a bad price is worse than an overlay
   rule that does, because no renewal can switch it off. (U-8)

---

## 2. The three requirements as design rules

| Requirement | What it forbids | What it forces | Where it lands |
|---|---|---|---|
| R1 | any Ycash rule whose evaluation needs Ethereum liveness; collateral whose only exit is an Ethereum event | an owner branch on every vault, opened by set dormancy, set wind-down or age | primitive: liveness, `OP_CHECKSETDORMANT`, CLTV |
| R2 | ZK proofs of Ethereum headers; posted Ethereum checkpoints; any consensus-read field encoding Ethereum state; a contract that verifies Equihash or Yellowback payloads | every authorisation is a signature under a key registered on Ycash; identifiers crossing the bridge are opaque bytes on both sides | primitive: signer sets, the opaque application tag; contract: `bytes32` lock ids |
| R3 | pool signalling and lock-in, the valve, the ENFORCEMENT halt, the sunset, mined-but-VOID transactions, template policy carrying rule content | a network upgrade: new branch ID, rules in block validity | §8 |

"Neither chain's upgrade can break the other's rules" is structural: the Ycash side knows a set of
secp256k1 keys; the contract knows the same keys. Either chain changes everything else freely.

---

## 3. The primitive

Every element: what it is, the tier it lands on, why no cheaper tier does. The ladder vocabulary
is README.md's, applied **inside** the upgrade: a change that can be a script template is not an
opcode; one that can be an opcode is not a new transaction field; one that can be per-vault state
is not global state.

### 3.1 The vault output

A P2SH output whose redeem script is the **vault template**: an unlock branch, a cancel branch and
an owner branch, parameterised by a set id, a delay, and an owner key, with a 4-byte **application
tag** pushed and dropped (consensus reads the tag only to decide whether a registered module must
also validate the spend, §3.8). The template is fixed by the upgrade so every node, wallet and
indexer recognises a vault by shape, the way v3 recognises its vault script (`script.cpp`).

*Tier:* script template, no opcode of its own. *Why not cheaper:* a template is the cheapest
thing there is.

### 3.2 Signer sets

A consensus object, keyed by `setId`, created by a `SET_CREATE` transaction and populated by
`SET_JOIN` transactions that lock a bond (a P2SH CLTV output, as v3's attestor bond). A set has:

| Field | Meaning | Bridge value (owner's O-2) | Bridge value (Foundation's single relayer) | YED attestors |
|---|---|---|---|---|
| `seats` | maximum members by bond | 9 | 1 | `N_SLOTS` 9 |
| `unlockThreshold` | signatures to spend the unlock branch | 6 | 1 | n/a (YED claims are not set-signed; §5.3) |
| `cancelThreshold` | signatures to spend the cancel branch | 1 | 1 of the **challenger** set (a second set, bonded, open) | 1 |
| `slashThreshold` | signatures to burn a member's bond on a contested cancel | 7 | challenger-set majority | 7 |
| `rateLimit` | value the set may unlock per `rateWindow` | `RELEASE_CAP_BPS` of locked value | same | n/a |
| `livenessWindow` | blocks without any member act before the set is DORMANT | `GUARDIAN_DORMANCY_BLOCKS` | same | `DORMANCY_BLOCKS` |
| `bondMin`, `bondLock`, `maturity` | as v3's attestor bond | ≥ attestor bond | high (one bond backs everything) | `BOND_MIN` |

A member's acts are: a signature on an unlock, a signature on a cancel, a `HEARTBEAT`. Membership
changes (join, withdraw at bond locktime, removal by `slashThreshold` with the bond returned, O-6)
are transactions, so the set rotates without touching any vault.

*Tier:* new consensus state (a table in the chainstate, UNDO-covered like v3's `Attestors`).
*Why not cheaper:* a `CHECKMULTISIG` over fixed keys cannot rotate, cannot be rate-limited and
cannot be slashed; a set referenced by id can. This is the one genuinely new consensus object and
it is shared by both applications.

### 3.3 Relative timelock

BIP68 sequence semantics and `OP_CHECKSEQUENCEVERIFY`, which Zcash and Ycash never adopted. The
unlock branch of a vault's **intent output** must age `delay` blocks before the set may spend it.

*Tier:* opcode plus `nSequence` semantics, exactly Bitcoin's. *Why not cheaper:* CLTV is absolute
and an intent's height is not known when the vault is created. *Why not bigger:* the design is
twelve years old and audited everywhere; it is the lowest-risk consensus change in this document.

### 3.4 The cancel branch

The intent output's second branch: spendable **before** maturity by `cancelThreshold` signatures
of the set (or of the challenger set, §4.2), back into a vault of the same owner. A cancel is a
native act with no reason field. Consensus never learns why.

*Tier:* template branch over `OP_CHECKSETSIG`. *Why not cheaper:* a cancel by a fixed key is a
single point of failure; a cancel by any bonded member is the pasted feedback's "one honest
watcher stops the theft".

### 3.5 Rate limit

Per set: the sum of values unlocked over the trailing `rateWindow` may not exceed `rateLimit`,
expressed as basis points of the value locked under that set at the window start. An unlock that
would exceed it is invalid.

*Tier:* consensus state (a rolling sum per set). *Why not cheaper:* a per-vault cap does not bound
the aggregate (hardening D-RD-INF-4); only the set knows its aggregate.

### 3.6 Slashing

Two signatures by one member over two different spends of **the same outpoint** is equivocation,
provable from the two signatures alone: the member is EJECTED and the bond is **burned**. This is
the slashing v3 could not have without a network upgrade (v3 §1.7). A contested cancel (the
Foundation's challenge window) is resolved by `slashThreshold` signatures of the relevant set
naming the member to slash; consensus records the slash, not the reason.

*Tier:* consensus rule over set state. *Why not cheaper:* without slashing a set's bond is a
deposit, not a stake, and the Foundation's single-relayer shape is unsafe.

### 3.7 Liveness and dormancy

A set is DORMANT when fewer than `cancelThreshold` members have acted in `livenessWindow`. A
member is DORMANT when it has not acted in that window (v3's per-attestor dormancy, S15). The
owner branch of every vault under a DORMANT set is open (`OP_CHECKSETDORMANT`). This is R1.

*Tier:* consensus state already needed by §3.2, plus one opcode.

### 3.8 The application tag and module registration

The tag is 4 opaque bytes. Consensus treats a vault as **untagged** (the primitive alone governs
spends) unless the tag matches a module registered by the upgrade, in which case the module's
`ValidateSpend` and `ValidateCreate` also run. Registration is a compile-time table in the upgrade
(`{ 'YED\0' → yellowback::Module }`), not a transaction: adding a module is a network upgrade,
which is the Foundation's review point.

*Tier:* one table and two virtual calls. *Why it exists:* §1.4. *Why it is still agnostic:* the
primitive runs identically for every tag; a module can only add constraints, never remove one.

### 3.9 Script additions, in full

| Opcode | Semantics |
|---|---|
| `OP_CHECKSEQUENCEVERIFY` | BIP112 |
| `OP_CHECKSETSIG` | pops `setId`, `k`; verifies `k` compact ECDSA signatures by distinct current members of `setId` over the ZIP-243 sighash; records them for §3.6 |
| `OP_CHECKSETDORMANT` | pops `setId`; true iff the set is DORMANT at the spending height |

Three opcodes from the unassigned range above `OP_NOP10`, gated on the branch ID. Bytes
`0xbb`–`0xbf` are **not** used (`docs/mapping.md` §2: on Ycash they are `BAD_OPCODE`, and the
DigiByte association would mislead).

---

## 4. Application 1: the bridge (wYEC), no module

### 4.1 On Ycash

| Step | Transaction | Rule |
|---|---|---|
| Lock | vault output, tag `WYEC`, set = guardians, `destination 32` opaque in an `OP_RETURN` (an Ethereum address the wallet writes and consensus never reads) | primitive only |
| Intent | the guardian set (per `unlockThreshold`) moves vault value into an **intent output** naming `recipient` (Ycash) and `amount` | primitive: `OP_CHECKSETSIG`, rate limit checked here |
| Release | after `delay`, the set spends the intent to `recipient`; change re-locks | primitive: `OP_CHECKSEQUENCEVERIFY`, `OP_CHECKSETSIG` |
| Halt / challenge | before `delay`, `cancelThreshold` members spend the intent back to a vault | primitive: cancel branch |
| Recovery | owner spends a vault iff the set is DORMANT, or a `SET_WINDDOWN` is final, or `height ≥ lockHeight + BRIDGE_MAX_AGE` and no intent names it (O-5) | primitive: owner branch, `OP_CHECKSETDORMANT`, CLTV |
| Griefer removal | `slashThreshold` members post `SET_REMOVE seq`; bond returned (O-6) | primitive |

There is no `yed_*`-style bridge RPC in consensus terms; the node exposes the primitive
(`set_list`, `set_getinfo`, `vault_list tag=WYEC`, the signing RPCs `set_signunlock`,
`set_signcancel`, `set_heartbeat`, which keep the key on the node as `yed_signattestation` does).

### 4.2 The two signer shapes

The Foundation's bridge prefers a **single relayer with a challenge window and slashing**; the
owner's O-2 chose **9 seats, 6 to unlock, 7 to slash**. Both are rows of §3.2:

| | Single relayer + challengers | 9 / 6 / 7 guardians |
|---|---|---|
| Who unlocks | one bonded relayer | 6 of 9 |
| Who cancels | any bonded challenger (an open second set) | any 1 of 9 |
| Who slashes a bad unlock | challenger-set majority after a contested cancel | 7 of 9 |
| Theft needs | the relayer plus every challenger silent for `delay` | 6 colluders plus the other 3 silent |
| Liveness needs | one party | 6 parties |
| Capture cost | one bond (so `bondMin` must be large) | 6 bonds |
| Matches Foundation preference | yes | no |

The owner's preference for multi-party applies to **price attestation** (§5.2), which is a different
set with a different job. The bridge's shape is the Foundation's call (O-9, open); the primitive
supports either, and the daemon differs only in configuration.

### 4.3 Off Ycash: the `wyec/` repository

Its own repository on `main`, net new, no reference, no baseline. The contract (Solidity, Ethereum
L1 first, O-4): an ERC-20 with `mint(lockId, amount, to, sigs[])` under the same guardian keys,
`lockId` stored as `bytes32` and never parsed (R2); `burn(amount, ycashRecipient)` emitting the
event the daemon turns into an intent; key rotation and pause by threshold. The daemon follows
Ycash by RPC and Ethereum by JSON-RPC (finalised blocks only), co-signs mints for observed locks,
posts intents for finalised burns, co-signs releases after `delay`, cancels any intent it cannot
match to a burn, and heartbeats. Contract audit is external and on the critical path.

---

## 5. Application 2: Yellowback (YED), with the rule module

### 5.1 On the primitive

| YED thing | Primitive element |
|---|---|
| Vault | the vault template, tag `YED\0`, set = attestors, owner branch at `lockHeight` (CLTV) as today |
| Attestor registry, bonds, maturity, dormancy, revival | a signer set (§3.2, §3.7) |
| Attestor equivocation (two prices, one height) | **stays in the module**: it is about signed prices, not outpoints; the bond burn uses §3.6's mechanism |
| Claim path delay and cancel | an intent output: the claimant moves the vault into an intent carrying its burn; after `CLAIM_DELAY` the claimant spends it; before, any attestor may cancel (a wrong-price claim is stopped by one honest attestor) |
| Cap | the set's `rateLimit` bounds claims per window; the **supply cap** is module state (§5.3) |

### 5.2 Price attestation stays multi-party

Unchanged from v3: `N_SLOTS` bonded attestors, bundles carried in the transaction, a bond-weighted
one-sided quantile, `pMint = min(xMint, aMint)`, `pClaim = max(xClaim, aClaim)`, the pins, the
arming bar (hardening H-2: seven matured distinct bonds). The attestor set is the signer set of
§3.2 with `unlockThreshold` unused: attestors never spend anything; they sign prices that the
module reads. The owner's position stands: a single price signer is not a price.

### 5.3 The module

`yellowback::Module` is the delivered `src/yellowback/` rule set, invoked by consensus for every
transaction that creates or spends a `YED`-tagged vault or carries a Yellowback payload:

| Stays, as consensus | Leaves (§6) |
|---|---|
| MINT-1..10, PRICE-2, the pins, ARM-1/2, AFEE | ACT-1..6, lock-in, `SIGNAL_WINDOW` |
| RED-1..5 (now: the intent's burn and price, checked at intent creation; the spend after delay re-checks nothing but the delay) | the valve, note cap, odometer |
| TRANSFER, the token index, `supplyCents`, HALT-1/2 (NO_PRICE, GLOBAL_RATIO, unarmed), MINT-6 cap gate | ENFORCEMENT halt, abandonment, catch-up suppression |
| NOT-1 emergency notice, EQV-1 price equivocation, REV-1 | VOID verdicts, `voidReason`, TPL-1/2, MP-1's rule content |
| SNAP, `Snapshots[h]`, the golden vector and the Python model (N23) | the anyone-can-spend claim branch (A-5): the claim is an intent on the primitive |

A failing mint is an invalid transaction. A failing claim intent is invalid. There is no
"mined but VOID". The module's state (`Snapshots`, the token index, `BundleLog`, `Notices`)
becomes chainstate, UNDO-covered, and the state hash joins the block-validity check it already
mirrors on the devnet (`ybcal devnet validate --strict`).

### 5.4 The fallback (A1)

If the Foundation declines the module: the `YED` tag is unregistered, vaults are governed by the
primitive alone (owner branch at `lockHeight`, claim intents under the attestor set's delay and
cancel with **no** burn check), and the delivered overlay keeps MINT, TRANSFER, the index and the
claim's burn rule at today's tier. Collateral is consensus-safe; the peg's enforcement is as
today. No vault, wallet or attestor change between the two outcomes.

---

## 6. What the upgrade removes from v3, and what closes by construction

| Removed | Was | Why it goes |
|---|---|---|
| Pool signalling, ACT-1..6, lock-in, `SIGNAL_WINDOW`, `activationThreshold` | v2 L3, hardening H-7 | activation is a height in `chainparams.cpp` |
| `ENFORCE_UNTIL_HEIGHT`, the sunset, renewal releases, W18/W19 | v3 revision 4 | a consensus rule has no sunset |
| The work valve, note cap, persistence, odometer | v2 L7, hardening H-6, F-3, audit A-6 | no enforcing minority to protect |
| ENFORCEMENT halt, catch-up suppression, abandonment | W21 | nothing to abandon |
| VOID verdicts, `voidReason`, MINTPOL's VOID mirror | v2 V3 | an invalid transaction is not mined |
| TPL-1/2, MP-1's rule content | v2 | mempool and template follow validity |
| The anyone-can-spend claim branch | `script.cpp:90`, audit A-5 | the claim is a primitive intent |
| Frozen-file zero-delta checks, hook budgets | v3 §4.1, gate G-9 | consensus files change by design; replaced by the review gate (§7) |

Closes by construction: hardening B-3, B-6, C-8, C-9; audit A-5, A-6; the "majority pool leaves"
and "spurious lock-in" rows. B-1's enforcement leg closes; its oracle leg does not.

Stays exactly as delivered: payloads (new types added), the carrier, PRICE-2, the pins, the
emergency notice, the `yed_*` surface (plus the primitive's `set_*`/`vault_*` RPCs), the Python
model and golden vector discipline, the devnet and role regtest, chain-viz, lightwalletd's
streamer, YEW, x402, yb-calibration.

---

## 7. The hardening plan under this idea

| Item | Fate | Note |
|---|---|---|
| H-1 minting requires ARMED | **kept** | the oracle leg of B-1; a hand-built unarmed mint is invalid |
| H-2 arming bar 7, G-5 | **kept** | applies to the attestor set; the bridge set's bar is O-9 |
| H-3 ratios on the worse window | **kept** | |
| H-4 fee split | **kept** | a bridge fee is a new line (O-2) |
| H-5 class A only | **kept** | B/C stay off; a pre-maturity rule is now a module change, not a script change |
| H-6 valve | **retired** | |
| H-7 two-window lock-in | **retired** | |
| H-8 START_HEIGHT after commitment | **reshaped** | the activation height is set by the gate-passing release; the commitment sought is node-operator and exchange **upgrade adoption** (G-4) |
| H-9.1 sunset stand-down | **retired** | |
| H-9.2 wallet deadlines, renew | **kept** | sunset warning dropped |
| H-9.3 client plausibility bounds | **kept** | |
| H-10 class-A cap gate | **kept** | module state |
| H-11 halt 300 %, recap 600 % | **kept** | |
| H-12 `maxMint` $2,500 | **kept** | |
| F-1 wallet spent-tracking, F-2 agent configs, F-5 heights unset | **kept** | |
| F-3 odometer | **retired** | |
| F-4 | **reshaped** | plausibility kept, sunset warning dropped |
| G-1, G-2, G-3, G-5, G-7, G-8, G-10 | **kept** | G-10 adds the primitive drills (§12) |
| G-4 coalition commitment | **reshaped** | upgrade adoption ≥ 70 % of blocks and the listed exchanges before the height |
| G-6 valve | **retired** | |
| G-9 frozen files | **reshaped** | the **consensus review gate**: every changed line under `src/consensus/`, `src/script/`, `main.cpp`, `src/primitives/`, both lines, reviewed by two people independent of the author, with the four-part check in the PR body |
| §6 trust statement | **rewritten** | §10 |
| §9 work plan | H0, H1, H3-a, H3-c, H4, H5 kept; H2 and H3-b's lock-in/sunset parts dropped; H6–H8 become P6–P8 |

---

## 8. Activation plumbing on both node lines

The four-part check, once for the mechanism:

> DigiByte activates in `src/consensus/params.h` using BIP9 versionbits (`docs/mapping.md` §4).
> The Ycash equivalent is a height-gated network upgrade (`enum UpgradeIndex`,
> `NetworkUpgradeInfo[]` in `src/consensus/upgrades.cpp`, `vUpgrades[].nActivationHeight` in
> `src/chainparams.cpp`, `NetworkUpgradeActive(...)` at each check site), which lacks signalling by
> design. So the adaptation is `UPGRADE_VAULT` with a fresh `nBranchId`, heights set by the
> gate-passing release, regtest via `-nuparams`, the three opcodes and the set table gated on it,
> and the YED module registered under it. Tier: network upgrade, by R3; no cheaper tier meets R3.

| Site | ycash-dd (v4.5.0 lineage) | ycash6 (6.20.0, Zcash 6.x lineage) |
|---|---|---|
| Upgrade table | `src/consensus/upgrades.cpp`, after Canopy | after `0x5437f330`, before the `0xffffffff` sentinel |
| Chain params | `vUpgrades[UPGRADE_VAULT]` main/test/regtest | same |
| Sighash | ZIP-243 bound to `consensusBranchId`: every signer presents the new ID | same; `librustzcash6` gains the `BranchId` and **stops being zero-delta**; `ycash6/Cargo.toml` repoints at `boyfromcave/librustzcash6` |
| Script | three opcodes in `src/script/interpreter.cpp` behind the branch ID; the vault template in `src/script/standard.cpp` | same |
| Consensus state | the set table and rate sums in the chainstate (`CCoinsView` extension on ycash-dd; the 6.x equivalent) | `docs/mapping.md` §19 |
| Check site | `main.cpp` `ConnectBlock`: set state transitions, module dispatch by tag | the 6.x equivalents |
| Clients that sign | YecWallet, YEW (Rust signer), yolo (branch ID in templates), x402 (verifier), the Python `test_framework` | same |
| Tooling | `make diff` budgets re-based; the frozen list becomes the review-gate list | same |

Both lines stay in step; branch ID and heights are identical. The release line is `ycash6`,
version **6.22.0** (O-7).

---

## 9. The working rules that change (AGENTS.md amendments, proposed)

The guiding principles stand: Ycash is risk-averse, the shielded pool's soundness rests on code
few people fully understand, and every change takes the smallest footprint that works. What
changes is that a network upgrade is now the owner's and the Foundation's decided tier, so the
rules written to keep the fork **off** that tier are replaced by rules that keep it **small on**
that tier.

| AGENTS.md rule today | Amendment |
|---|---|
| Prime directive: "Prefer the cheapest tier that works: Tier 0 … over a soft fork, and a soft fork over a coordinated network upgrade" | **"The tier is a network upgrade, by Foundation requirement R3 and owner decision O-1. Within it, prefer a script template over an opcode, an opcode over a transaction field, per-vault state over global state, and the primitive over the module. Record what was given up."** |
| Rule 2: frozen-file zero-delta checks against `yellowback-v3-baseline` | **retired** for `src/consensus/`, `src/script/`, `main.cpp`, `src/primitives/`; replaced by the consensus review gate (§7, G-9). The `-legacy` line budgets stay, as a size measure, not a gate |
| Rule 2: "the `yed_*` RPC surface is the sole interface between the node and either client" | **extended**: the primitive's `set_*` and `vault_*` RPCs join it; the bridge daemon uses only those plus stock RPCs; nothing else changes |
| Rule 3: "DigiByte's DD opcodes … a verbatim port compiles and is consensus-dead" | **stands**, and gains: the three new opcodes are allocated above `OP_NOP10`, never `0xbb`–`0xbf`; the mapping §2 row is the reason |
| Rule 4: the four-part check, "which tier does W land on, and why won't a cheaper tier do?" | **stands**, with the ladder of the prime directive amendment; a consensus PR without it is rejected at the review gate |
| Rule 7: "Consensus code is not refactorable … Do not tidy, rename, or improve surrounding code" | **stands, verbatim.** The upgrade adds; it never tidies |
| "Two node lines … a shared Yellowback defect or rule change is made on both lines together" | **stands**; the primitive, the module and the branch ID are one change on both lines |
| `librustzcash6` "zero-delta until the port needs it" | **it now needs it**: the branch ID |
| Component rules (yolo, chain-viz, x402, YEW "never needs a node change") | **stand**; they need the branch ID for signing or verifying, which is a client update, not a node change they ask for |
| Memory rule `v3-comparison-base` (frozen checks vs the tag) | **retired with rule 2's frozen check**; `feature/yellowback-sf` remains no comparison base |

Applied to AGENTS.md when this plan's first implementation chunk opens (P2), not before: until then the delivered forks are still measured by the rules as written.

---

## 10. Tier, trust statement, what is given up

**Tier.** Network upgrade, by R3, O-1 and the Foundation's own preference for a generic primitive.
Within it: three opcodes, one consensus object (signer sets with rate sums), one template, one
module table, one module. Recorded in `docs/mapping.md` (new §22) so no later session re-litigates
it.

**Trust statement (replaces hardening §6).** The product promises, in these words, and no more:

- **Every Yellowback and every bridge rule is a Ycash consensus rule, checked by every full node.**
  There is no pool that enforces, no pause, no abandonment.
- YED is created only when both a hashpower majority and a bonded attestor majority agree on the
  price. Neither alone can mint against a price it sets. A single signer is never a price.
- Collateral behind YED is locked for 30 to 90 days and returned to the owner who redeems before
  `lockHeight + 30 days`; after that, anyone may close the vault by paying its debt in YED, after
  a delay during which any honest attestor can stop a claim at a wrong price.
- **Wrapped Ycash is a federated bridge.** YEC behind wYEC is released only by its bonded signer
  set, after a delay, within a per-window cap, and only while no bonded watcher has cancelled.
  Ycash never reads Ethereum. If the signers go silent or wind down, every depositor recovers
  their own YEC with no counterparty. Bonds are burned for signing conflicting releases.
- Nothing in either application touches the shielded pool.

**What is given up:**

1. The soft-fork tier and everything built for it (§6), delivered and calibrated, then retired.
2. A trustless bridge release path: R2 forbids it; the bridge is federated and says so.
3. Renewal as the parameter mechanism: parameters move inside consensus-bounded ranges by set
   threshold signal (O-8), or by upgrade.
4. `librustzcash6` as a zero-delta fork.
5. The frozen-file invariant as a one-command proof of consensus safety, replaced by review.
6. Agnosticism in full: one registered module. The primitive stays agnostic; the node is not.

---

## 11. Threat model rows (added to v3 §8.2 and hardening §5)

| Threat | Outcome | Mitigation | Residual |
|---|---|---|---|
| Bridge set unlocks without a burn | theft bounded by `rateLimit` per window, only if no watcher cancels within `delay` | delay, cancel, rate limit, slashing, distinctness (G-5-style, O-9) | a captured unlock set with every watcher silent steals one window's cap; stated in §10 |
| One watcher cancels repeatedly | releases stall per cancel | `SET_REMOVE` by `slashThreshold`, bond returned (O-6) | delay, never loss |
| Ethereum halts, forks, contract lost | no mints, no burns; signers heartbeat or wind down | owner branch (R1) | wYEC on a dead chain is the Foundation's wind-down policy |
| Ethereum reorgs a burn after release | the daemon acts on finalised blocks only; `delay` exceeds finality many times | daemon policy | a finality failure is a bridge loss, bounded by the cap |
| Signer key compromise | one seat's acts | threshold, delay, cancel, ejection | one bond |
| A claimant's intent at a wrong price | any attestor cancels within `CLAIM_DELAY` | §5.1 | an attestor set captured **and** a pool majority **and** every honest attestor silent: the v3 collusion row, now with a delay in front of it |
| The majority pool censors cancels | ordinary censorship (R3) | `delay` long enough that a cancel reaches a block with high probability; measured (G-11) | a majority censoring every cancel for a full delay enables the theft rows |
| A module bug | an invalid YED transaction accepted, or a valid one refused, by every node at once | the golden vector and the Python model (N23) in CI; the state hash in block validity; the review gate | a consensus bug is a chain halt or a fork; this is the cost of full-node verification and is why the module is the delivered, calibrated rule set and not new code |

---

## 12. Sequencing

| Phase | Content | Depends on |
|---|---|---|
| **P0** decide | **done in part (2026-10-05):** this plan promoted with §0's assumptions; the AGENTS.md amendments of §9 land with it. **Open:** the Foundation's written primitive (replaces §0's assumptions one by one), O-9, O-12; the O-8 design note | — |
| **P1** harden | hardening H0, H1, H3-a, H3-c, H4, H5 as written minus §7's retired items; G-1, G-2, G-3, G-5, G-7, G-8 read | hardening plan |
| **P2** primitive | both lines: `UPGRADE_VAULT`, branch ID, BIP68/CSV, `OP_CHECKSETSIG`, `OP_CHECKSETDORMANT`, the set table and rate sums, the vault template, `SET_*` transactions, the module table (empty), the primitive's RPCs; `librustzcash6` branch ID; test framework ID; unit and functional suites for the primitive **with no application** | P1 binaries |
| **P3** bridge template | the `WYEC` template and intent flow on the primitive; a bridge persona in the role regtest with a local Ethereum (anvil); both signer shapes exercised | P2 |
| **P4** YED module | `yellowback::Module` from the delivered rule set: §6 removals, VOID → invalid, the claim as an intent, module state into chainstate, golden vector regenerated once with the diff explained, Python model parity | P2 |
| **P5** wyec repo | contract (external audit), daemon, devnet preset | P3 |
| **P6** clients | YecWallet, YEW, lightwalletd, chain-viz (set and vault panels), x402 and yolo (branch ID) | P2 for the ID; P3/P4 for the surface |
| **P7** gates | kept gates; reshaped G-4, G-9; **G-11** cancel inclusion latency on the real block sequence; **G-12** primitive drills on testnet or a public multi-operator devnet: cancel, equivocation slash, dormancy recovery, wind-down, both bridge shapes, a wrong-price claim cancelled | everything |
| **P8** release | `ycash6` 6.22.0 and `ycash-dd` in step; activation height and the later bridge enable height (O-3) set by this release; the contract deployed with the registered set | P7 |

P1 and P2 run in parallel worktrees; P2 does not touch P1's files until P1 merges. P3 and P4 are
independent and run in parallel. P5's contract audit is external and on the critical path.

**Budget.** No line budget on the consensus files under the review gate; a size estimate instead:
the primitive ≈ 1,500 lines per node line (BIP68/CSV is a known-size port from Bitcoin ≈ 300;
the set table, opcodes, template and transactions the rest); the module is the delivered
`src/yellowback/` minus ≈ a third (§6) plus the intent flow ≈ 400. The bridge adds nothing to the
node beyond the template.

---

## 13. Decision record

**Owner, 2026-10-05, under revision 2** (each put with the recommendation first; every
recommendation taken), re-read under revision 3:

| # | Decision | Decided | Under revision 3 |
|---|---|---|---|
| O-1 | Scope and firmness of R1–R3 | both mechanisms, R1–R3 firm | stands; "both" now means the primitive governs both and the module gives YED full-node verification |
| O-2 | Bridge set 9 / 6 / 7, bond ≥ attestor, bps fee | taken | one of the two rows of §4.2; the Foundation's single-relayer row is the alternative (O-9) |
| O-3 | Bridge enables at a later height in the same release | taken | stands (`WYEC` tag live at the second height) |
| O-4 | Ethereum L1 first | taken | stands |
| O-5 | `BRIDGE_MAX_AGE` recovery | yes | stands, on the owner branch |
| O-6 | Griefer removal by threshold, bond returned | taken | stands as `SET_REMOVE` |
| O-7 | Version 6.22.0 | taken | stands |
| O-8 | Bounded, set-signalled parameters | taken | stands; the signal is a set act in the primitive |

**Owner, 2026-10-05, under revision 3:**

| # | Decision | Decided |
|---|---|---|
| O-10 | The path: agnostic primitive, two applications, one registered rule module for YED | **yes** (the table in the preamble) |
| O-11 | Price attestation stays multi-party regardless of the bridge's signer shape | **yes** |

**Open, the Foundation's:**

| # | Decision | Recommendation |
|---|---|---|
| O-9 | Bridge signer shape: single relayer + challenger set, or 9 / 6 / 7 | the primitive supports both; if single relayer, `bondMin` must cover one window's `rateLimit` in full, so a theft never pays |
| O-12 | Acceptance of the module table (§3.8) as part of a generic primitive | the argument of §1.4; the fallback of §5.4 if declined |
| O-13 | Numeric values: `delay` per application, `rateWindow`, `rateLimit`, `livenessWindow`, `BRIDGE_MAX_AGE`, `CLAIM_DELAY` | `ybcal` derives them in P1/P4; starting points one day, one week, and a cap sized to the window's worst case |

---

## 14. Considered and rejected

- **ZK proof of the Ethereum sync committee as the release authority.** By R2. Also weaker than it
  looks (no slashing for a false header) and a proof-system mismatch with what ycashd verifies.
- **One application-aware consensus module for both** (revision 2). Rejected by the Foundation's
  preference for an agnostic primitive; the bridge needs no module, so the shared module was
  carrying bridge logic that belongs in a template.
- **YED's dollar rules enforced by the attestor set signing claims** (option A2). Turns the price
  oracle into a custodian; v3 §1.6 forbids it and the owner declined it.
- **A fully agnostic node with YED at the overlay tier** (option A1) as the primary path. It is the
  fallback (§5.4), not the plan: it leaves the peg's enforcement with opt-in pools.
- **Attestors as bridge signers.** Different jobs, different failure modes; v3 D-1 stands.
- **Guardian multisig in the vault script.** Cannot rotate, cannot be rate-limited, cannot be
  slashed.
- **Depositor veto on bridge releases.** Once wYEC is sold the depositor has no claim.
- **Reusing `0xbb`–`0xbf` for the opcodes.** `docs/mapping.md` §2.
- **Keeping VOID semantics under consensus.** Exists only because non-enforcing miners exist.
- **A single price signer with a challenge window** for YED. A challenge needs a second opinion to
  exist; a quantile over nine bonded opinions is the challenge, every block.

---

## 15. Implementation specification (revision 2)

Normative for both node lines. Byte layouts, constants and rule text below must be implemented
**identically** in `ycash-dd` and `ycash6`; the golden vector `vault_vectors.json` (§15.9) is the
proof. "Template input" means an input spending a V or I output (§15.3). All integers in act
payloads are fixed-width little-endian; script numbers are minimal `CScriptNum` pushes.

### 15.0 Decisions taken while specifying (U-9..U-20)

| # | Decision | Why / what was given up |
|---|---|---|
| U-9 | Branch ID `0x6d5b7a31`, name `Vault`, enum position after the last real upgrade (`UPGRADE_NU5` on ycash-dd, `UPGRADE_NU6_2` on ycash6), before `UPGRADE_ZFUTURE` | both lines identical; activates without NU5/NU6 (Ycash never activated them) |
| U-10 | `OP_CHECKSEQUENCEVERIFY` is **BIP112's own byte `0xb2` (`OP_NOP3`)**; the two new opcodes are `0xc0`, `0xc1` | "exactly Bitcoin's" (§3.3) wins over §3.9's "three above `OP_NOP10`"; `0xbb`–`0xbf` untouched |
| U-11 | BIP68 applies to **every input** (disable bit clear) from activation, height-based only; time-based relative locks (bit 22) are invalid | exactly BIP68 minus the time flag; every Ycash wallet we know sets the disable bit (`0xfffffffe`/`0xffffffff`); recorded in mapping §22 |
| U-12 | Vault and intent outputs are **bare** scriptPubKeys, not P2SH | consensus must see vault value at creation for the rate limit (§3.5) and the set's locked value; P2SH hides it until spent |
| U-13 | `OP_CHECKSETSIG` takes a **role** (1 unlock, 2 cancel), not `k`; `k` is the set's threshold for that role, read from set state | thresholds live in the set (O-8 can move them); a script-pushed `k` could undercut them |
| U-14 | Set signatures are 65-byte **recoverable** compact signatures over a message that binds `setId`, role, the spent **outpoint** and the ZIP-243 sighash | equivocation (§3.6) is then provable from two signatures alone |
| U-15 | Intent **release needs no second set signature**: the intent commits the recipient script hash, and after `delay` anyone may broadcast the release paying it | the plan's release-by-set added a liveness dependency and no safety: the recipient is fixed when the set signs the unlock |
| U-16 | At most **one template input per transaction** | no batching; every covenant rule becomes per-transaction and unambiguous |
| U-17 | Script evaluation sees set state **as of the parent block**; acts apply **sequentially in block order** | parallel script checks need an immutable snapshot; acts need ordering for seats and removals |
| U-18 | Set state lives in its own LevelDB (`<datadir>/vaults/`) with per-block undo and a tip marker reconciled on start (replay from blocks), not inside the coins DB | the pattern the delivered Yellowback index already proves; the coins DB is not touched. Given up: one atomic flush |
| U-19 | Liveness counts only `SET_JOIN` (at maturity) and `SET_HEARTBEAT`; signing an unlock or cancel is not an act | no interpreter side effects; daemons heartbeat |
| U-20 | Rate windows are fixed epochs `floor(h / rateWindow)`; the basis is the set's locked value at the epoch's start | O(1) state; up to 2× cap across an epoch boundary, stated in §10 |

YED-specific (P4) choices: U-21..U-24 in §15.10; U-25 below.

| U-25 | **Module ejection hook.** A registered module may name the one set its vaults govern (`GovernedSet`) and return member keys to eject (`Ejections`); the primitive applies `SET_EQUIVOCATION`'s effect (eject, freeze bond) inside the block overlay, undo-covered. The hook never invalidates a transaction and never touches another set | EQV-1 (two prices at one height) is about signed prices, which the primitive cannot see; the hook keeps the primitive agnostic ("a module may eject a member of its own set"), at the cost of one generic module-to-primitive effect |

### 15.1 Upgrade and constants

- `Consensus::UPGRADE_VAULT`; `NetworkUpgradeInfo` row `{0x6d5b7a31, "Vault", "Ycash vault primitive (docs/plans/yellowback-upgrade-plan.md)"}`; the per-epoch Equihash table gains the same row as the epoch before it.
- Activation: mainnet and testnet `NO_ACTIVATION_HEIGHT` (P8 sets them); regtest `NO_ACTIVATION_HEIGHT`, set by `-nuparams=6d5b7a31:<h>`.
- Script flags: `SCRIPT_VERIFY_CHECKSEQUENCEVERIFY` and `SCRIPT_VERIFY_VAULT`, both added to the consensus flags for blocks at heights where `UPGRADE_VAULT` is active (and to mempool checks for tip+1).
- Python: `VAULT_BRANCH_ID = 0x6D5B7A31` in `test_framework/util.py`.

### 15.2 Script

**`OP_CHECKSEQUENCEVERIFY` (0xb2)** with `SCRIPT_VERIFY_CHECKSEQUENCEVERIFY`: BIP112 exactly, except that the transaction version test reads Ycash's `nVersion` (4 ≥ 2 always passes) and a stack argument with the type flag (bit 22) set fails (`SCRIPT_ERR_UNSATISFIED_LOCKTIME`). Without the flag it is `OP_NOP3` as today.

**BIP68** (consensus, `UPGRADE_VAULT` active at the block height): for each input whose `nSequence` has bit 31 clear: bit 22 set → transaction invalid (`bad-txns-vault-timelock`); otherwise the input's coin height + `(nSequence & 0xffff)` must be ≤ the spending height (Bitcoin's `CalculateSequenceLocks`/`EvaluateSequenceLocks`, height part). Mempool: checked for tip+1; `ConnectTip` evicts mempool transactions that become non-final after a reorg.

**`OP_CHECKSETSIG` (0xc0)** with `SCRIPT_VERIFY_VAULT` (without it: `SCRIPT_ERR_BAD_OPCODE` as today):
1. Pop `role` (top of stack, as the templates push it last; exactly one byte, 1 or 2) and then `setId` (exactly 32 bytes); else `SCRIPT_ERR_SETSIG`.
2. `k = checker.SetThreshold(setId, role)`; unknown set → `SCRIPT_ERR_SETSIG`.
3. Pop `k` elements; each must be 65 bytes (`header || r || s`, header 31..34 = compressed recoverable, the `signmessage` format) with low S.
4. `msg = SHA256d("YcashSetSig" (11 ASCII bytes) || setId (32) || role (1) || prevout.hash (32) || prevout.n (u32 LE) || sighash (32))`, `sighash = SignatureHash(scriptCode, txTo, nIn, SIGHASH_ALL, amount, consensusBranchId)` with `scriptCode` from the last `OP_CODESEPARATOR`, as `OP_CHECKSIG`.
5. Each recovered key must be a **current member** (§15.4) of `setId` in the snapshot, all distinct. Any failure → `SCRIPT_ERR_SETSIG` (no "false" result). Success pushes `1`.
6. At most one `OP_CHECKSETSIG` per script evaluation (`SCRIPT_ERR_SETSIG_COUNT`). It does not add to the legacy sigop count (counting it would reprice historical blocks); its cost is bounded by `seats ≤ 15` and rule 6.

**`OP_CHECKSETDORMANT` (0xc1)** with `SCRIPT_VERIFY_VAULT`: pop `setId` (32 bytes, else `SCRIPT_ERR_SETSIG`); push `1` if `checker.IsSetReleased(setId)` (§15.4: dormant or wound down, or unknown) else `0` (empty vector).

**Checker interface** (`BaseSignatureChecker`, defaults fail / `false`):
`std::optional<int> SetThreshold(const uint256& setId, uint8_t role) const`,
`bool CheckSetSigs(const uint256& setId, uint8_t role, const std::vector<valtype>& sigs, const CScript& scriptCode, uint32_t consensusBranchId) const`,
`bool IsSetReleased(const uint256& setId) const`.
The implementation (`vault::SetSigChecker`, derived from the caching checker) holds a `std::shared_ptr<const vault::SetSnapshot>` and the spending height. Set-signature checks are **not** cached in the signature cache.

### 15.3 Templates

`setId` is the txid of its `SET_CREATE` transaction, pushed as its 32 internal bytes. `tag` is 4 bytes. `h`/`d` are minimal script numbers. The **selector** is the last push of the input's scriptSig: exactly the one byte `0x01`..`0x04` (pushed as `OP_1`..`OP_4`).

**Vault V** (bare scriptPubKey):
```
<tag:4> <cancelSetId:32> <delay> OP_2DROP OP_DROP
OP_DUP OP_1 OP_EQUAL OP_IF
    OP_DROP <setId:32> OP_1 OP_CHECKSETSIG
OP_ELSE OP_DUP OP_2 OP_EQUAL OP_IF
    OP_DROP <ownerHeight> OP_CHECKLOCKTIMEVERIFY OP_DROP <ownerKey:33> OP_CHECKSIG
OP_ELSE OP_DUP OP_3 OP_EQUAL OP_IF
    OP_DROP <setId:32> OP_CHECKSETDORMANT OP_VERIFY <ownerKey:33> OP_CHECKSIG
OP_ELSE
    OP_4 OP_EQUALVERIFY <appHeight> OP_CHECKLOCKTIMEVERIFY
OP_ENDIF OP_ENDIF OP_ENDIF
```
scriptSigs: UNLOCK `<sig_1> … <sig_k> OP_1`; OWNER `<ownerSig> OP_2`; OWNER-RELEASED `<ownerSig> OP_3`; APP `OP_4`.
Field ranges (a V-shaped output outside them is not a template, rule V-1 then rejects it):
`delay` 1..65535, `ownerHeight` 1..499999999, `appHeight` 0..499999999 (0 = APP branch disabled,
rule S-4), `ownerKey` compressed. Bridge vaults: `ownerHeight = lockHeight + BRIDGE_MAX_AGE`, `appHeight = 0`.

**Intent I** (bare scriptPubKey):
```
<tag:4> <recipientHash:32> <vaultHash:32> OP_2DROP OP_DROP
OP_DUP OP_1 OP_EQUAL OP_IF
    OP_DROP <delay> OP_CHECKSEQUENCEVERIFY
OP_ELSE OP_DUP OP_2 OP_EQUAL OP_IF
    OP_DROP <cancelSetId:32> OP_2 OP_CHECKSETSIG
OP_ELSE
    OP_3 OP_EQUALVERIFY <setId:32> OP_CHECKSETDORMANT OP_VERIFY <ownerKey:33> OP_CHECKSIG
OP_ENDIF OP_ENDIF
```
`recipientHash = SHA256(recipient scriptPubKey)`, `vaultHash = SHA256(originating V scriptPubKey)`.
scriptSigs: RELEASE `OP_1` (input `nSequence = delay`); CANCEL `<sig_1> … <sig_k> OP_2`; OWNER-RELEASED `<ownerSig> OP_3`.

**Bond B** (P2SH, as v3's attestor bond): redeem `<locktime> OP_CHECKLOCKTIMEVERIFY OP_DROP <memberKey:33> OP_CHECKSIG`.

`vault::ParseVault`/`ParseIntent` accept only the exact byte shapes above with minimal pushes.
Standardness: V and I are new `txnouttype`s (`TX_VAULT`, `TX_VAULT_INTENT`), standard once the upgrade is active at tip+1.

### 15.4 Set state

Per set (key `setId`): the `SET_CREATE` parameters; `createHeight`; `windDownHeight` (0 = none);
rate fields `lockedValue`, `epoch`, `epochBasis`, `epochUsed` (zatoshi); members.
Per member (key `setId‖memberKey`): `bondOutpoint`, `bondValue`, `bondLocktime`, `joinHeight`,
`lastAct`, `status ∈ {ACTIVE, REMOVED, EJECTED, WITHDRAWN}`, `bondFrozen` (bool). Plus a frozen-bond
index `outpoint → (setId, memberKey)` and a template-output index is **not** needed (V/I parse from the coin).

- **Current member at height h:** `status = ACTIVE` and `h ≥ joinHeight + maturity`.
- **Seat count:** members with `status = ACTIVE` (mature or not) ≤ `seats`.
- **Dormant at h:** fewer than `cancelThreshold` current members with `lastAct ≥ h − livenessWindow`.
- **Released at h:** dormant, or `windDownHeight ≠ 0 ∧ h ≥ windDownHeight + livenessWindow`, or the set is unknown.
- `lastAct` starts at `joinHeight + maturity`.
- **Snapshot:** the state after the parent block, evaluated at the spending height (block height; tip+1 in the mempool).

### 15.5 Acts: the `YV` OP_RETURN

One output `OP_RETURN <P> [<S_1> … <S_n>]`: `P = "YV" (0x59 0x56) || version 0x01 || type u8 || body`,
each `S_i` a 65-byte recoverable signature over `actMsg = SHA256d("YcashSetAct" (11) || P || vin[0].prevout (36))`.
After activation: a transaction with two `YV` outputs, an unknown version/type, a malformed body,
trailing bytes, or a failed rule is **invalid** (`bad-vault-act-*`). Before activation `YV` outputs
are ordinary data. Policy: a `YV` OP_RETURN may be up to 1,200 bytes (other OP_RETURNs unchanged).
Acts apply in block order against the running state (U-17); mempool validates against the tip.

| Type | Body | Signatures | Rule |
|---|---|---|---|
| 0x01 `SET_CREATE` | `seats u8, unlockThreshold u8, cancelThreshold u8, slashThreshold u8, flags u8 (bit0 OPEN), rateLimitBps u16, rateWindow u32, livenessWindow u32, bondMin i64, bondLockMin u32, maturity u32, admitKey 33` (64) | none | `1 ≤ seats ≤ 15`; thresholds in `1..seats`; `rateLimitBps ≤ 10000` (0 = no limit); `rateWindow, livenessWindow` in `1..1048576`; `1 ≤ bondMin ≤ MAX_MONEY`; `admitKey` compressed; other flag bits 0. `setId = txid` |
| 0x02 `SET_JOIN` | `setId 32, memberKey 33, bondLocktime u32, bondVout u8` (70) | `S_1` by `memberKey`; then, unless OPEN: `slashThreshold` current-member signatures if the set has ≥ `slashThreshold` current members, else one by `admitKey` | set exists (created in an earlier block), not wound down; seats free; key not ACTIVE in the set; `vout[bondVout]` = P2SH(B(memberKey, bondLocktime)), value ≥ `bondMin`; `bondLocktime ≥ h + bondLockMin`, `< 500000000` |
| 0x03 `SET_HEARTBEAT` | `setId 32, memberKey 33` (65) | `S_1` by `memberKey` | key is a current member; `lastAct = h` |
| 0x04 `SET_REMOVE` | `setId 32, memberKey 33, burn u8 (0/1)` (66) | `slashThreshold` distinct current members other than the target | target ACTIVE → `REMOVED`; `burn = 1` also freezes its bond (contested-cancel slash); `burn = 0` is O-6 (bond returned) |
| 0x05 `SET_EQUIVOCATION` | `setId 32, prevout 36, roleA u8, sighashA 32, sigA 65, roleB u8, sighashB 32, sigB 65` (264) | none (anyone submits) | both signatures valid (§15.2 step 4 messages) and recover to the same key `K`; `(roleA, sighashA) ≠ (roleB, sighashB)`; `K` is a member whose bond is unspent and not frozen → `EJECTED`, bond frozen |
| 0x06 `SET_WINDDOWN` | `setId 32` (32) | `slashThreshold` current members | `windDownHeight = h`; no further joins |

Bond rules: spending a frozen bond outpoint is invalid (`bad-vault-bond-frozen`); spending the bond
of an ACTIVE member sets `WITHDRAWN`.

**Reconciled 2026-10-05 (Python ↔ C++ cross-check, `up-pyfw`):** (1) BIP68 is Bitcoin's height
test exactly, so RELEASE (valid from `coinHeight + delay`) and CANCEL (valid while
`h − coinHeight < delay`) meet with no gap and no overlap. (2) `bondMin` is bounded by `MAX_MONEY`.
(3) Field ranges the codec does not check (`bondLocktime < 500000000`, `burn ∈ {0,1}`, roles 1/2 in
`SET_EQUIVOCATION`, signature header 31..34) are rejected at rule time (`ActFieldsValid`), with the
same `bad-vault-act-*` reason. (4) "Compressed" means the 02/03 prefix; an off-curve key parses and
can never sign. (5) Act signature counts are exact and signers distinct; extra scriptSig pushes
before a template's arguments are not rejected (no CLEANSTACK). (6) The epoch in which a set is
created has basis 0: nothing unlocks under a rate limit until the next epoch. (7) setId, txids and
prevouts are internal byte order; a prevout is the `COutPoint` serialisation.

**Added by the C++ implementation (`up-core-dd`, 2026-10-05), adopted:** (8) an I-shaped output
that is malformed (non-minimal push, out-of-range field) is invalid like a malformed V
(`bad-txns-vault-malformed`), so I-0 cannot be bypassed by mis-encoding; (9) an act in a coinbase
is invalid (`bad-vault-act-coinbase`: every coinbase shares a null `vin[0]`, so act signatures
would replay) and so is an act in a transaction with no transparent input (`bad-vault-act-novin`);
(10) every V output under a set adds its value to `lockedValue` and every V spend (any selector)
subtracts it, floored at 0; (11) the bond index covers every unspent member bond, so spending the
bond of an ACTIVE member marks it WITHDRAWN; (12) a second `SET_WINDDOWN` and a `SET_CREATE` of an
existing set are invalid; a missing input coin is `bad-txns-vault-inputs-missing`. Undo records are
not pruned (≈ 40 bytes per block).

**Added by the consensus plumbing (`up-cons-dd`, 2026-10-05), adopted for both lines:** (13) the
one-`OP_CHECKSETSIG` limit is per `EvalScript` call; (14) a CSV operand with bit 31 set is a NOP even
if bit 22 is set (BIP112's disable flag wins); (15) `PrevEpochBranchId` for Vault walks back to the
highest upgrade **with an activation height** (NU5 never activated on Ycash), so an old-branch spend
after activation is diagnosed `old-consensus-branch-id` (DoS 10) as at every other upgrade;
(16) `nProtocolVersion` for Vault is today's `PROTOCOL_VERSION` (270013) on every network until P8
picks a fresh value and bumps `version.h` on both lines together (a higher value now would make
regtest nodes disconnect each other at activation); (17) the vault flags are added by height, never
to the static `STANDARD`/`MANDATORY` sets, so wallet signing verification (`sign.cpp`,
`signrawtransaction`) must add `GetVaultScriptFlags(tip+1)`; (18) on the plain regtest harness
`getblocktemplate` aborts at height ≥ 150 (the known founders'-reward defect), so functional tests
activate below that or pass the Ycash upgrade arguments.

**Added by the 6.20.0 plumbing (`up-cons6`, 2026-10-05):** (19) 6.20.0's regtest `-nuparams` back-fill
(an unset upgrade takes the next-higher one's height) excludes Vault, so `-nuparams=6d5b7a31:h`
does not also schedule NU5..NU6.2 (whose protocol versions would partition regtest); (20) the
ZIP-221 history tree uses **V1 leaves under Vault** (6.20.0's Rust default would have sent an
unnamed branch to V2 while ConnectBlock builds V1 with NU5 inactive); if NU5 ever activates
alongside Vault this becomes state-dependent; (21) 6.20.0's `CreateNewBlock` does not re-check each
transaction (it validates the template through `TestBlockValidity`), so the mempool must never
hold a transaction invalid at tip+1: the per-block re-validation of template spends and acts is
mandatory on that line, not an optimisation; (22) 6.20.0 has no script-execution cache; set
signatures bypass the ECDSA cache; (23) on `upgrade/vault` the audit's frozen-set leg also exempts
`Cargo.toml`, `Cargo.lock` and `src/rust/*` (the `librustzcash6` repoint), under the review gate.

**Found by the functional suites (`up-ftest-dd`, 2026-10-05):** (24) mempool re-validation after a
tip change must re-run the **scripts** of template spends, not only the primitive rules (set
membership and dormancy are read by the opcodes); (25) an `OP_CHECKSETSIG`/`OP_CHECKSETDORMANT`
failure in the mempool is state-dependent and must not carry DoS 100 (a peer on another tip would
be banned); both fixed in `up-int-dd`. (26) **Open, for O-9:** §4.2's "challenger-set majority
slashes the relayer" is not expressible: `SET_REMOVE` is signed by members of the target's own
set, and a one-seat relayer set has no other member. Today the relayer is slashable only by
equivocation (which also makes its set dormant, so every owner recovers). A contested-cancel slash
across sets would need a new act (`SET_REMOVE` naming a second, authorised set), to be added if the
Foundation picks the single-relayer shape. (27) A bridge destination OP_RETURN whose first push
starts `YV` is parsed as an act and invalidates the lock; the `wyec` wallet and daemon must write
destinations as ABI `bytes32` (left-padded) and never begin one with `0x5956`.

**Found by the 6.20.0 wiring (`up-int6`, 2026-10-05):** (28) 6.20.0's `TestBlockValidity` for a
template runs **no scripts** (`CheckAs::BlockTemplate` clears `fExpensiveChecks`), so finding (21)'s
premise was incomplete: a stale set-dependent spend would have been mined into an invalid template.
ycash6's miner now re-runs acts, template rules and template-input scripts per candidate
(`vault::TemplateRun`), independently of the mempool re-check (both shown to work alone by a negative
control); v4.5.0's miner already re-checks inputs per transaction. (29) The audit exemption for
`upgrade/vault` also covers `src/policy/policy.{cpp,h}` (§15.3/§15.5 require them). (30) `-reindex-chainstate`
(6.20.0 only) also wipes the vault DB.

**Found by P4-a (`up-yed-dd`, 2026-10-06):** (31) `-yellowback`/`-experimentalfeatures` no longer gate YED;
regtest needs `-nuparams=6d5b7a31:<h>` + `-yellowbackattestorset=<setid>`; `-yellowbackstartheight` and
`-yellowbackenforceuntil` are init errors; the enforce/signal/template-policy/require-healthy flags are logged and
ignored. (32) An unhealthy Yellowback index now stops the node (`AbortNode`): under consensus a node that cannot
evaluate YED cannot validate blocks. (33) The claimant intent carries the collateral less the RED-5 residual
(the residual stays with the owner); fees come from the claimant's YEC; a cancel re-creates the vault from the
claimant intent only. (34) A failed TRANSFER still burns and is valid (unchanged semantics). (35) Issuance for the
supply cap counts from the upgrade height. (36) Golden vector: blocks 137, 217 and 251 are invalid and re-mined
without the offending transaction. (37) A real v4.5.0 reference binary cannot follow the chain past the upgrade
height (the stock-parity variants run without it). (38) `rpcversion` 5; `yed_sweep` removed (owner sweeps are
ordinary owner-branch spends). (39) The workspace `make spec` still sources the RPC contract's version and command
list from the v3 plan (rpcversion 4 on `harden/yellowback`); on `upgrade/vault` the contract is generated from the
node's `doc/yellowback-rpc.md`. Resolved 2026-10-06 (`382d1dc`): the generator detects the line from the doc's rpcversion (≥ 5 = upgrade)
and, on the upgrade line, takes the whole contract from the node doc; `make spec-check-upgrade` checks the
integration-tree copies (byte-identical to the hand-edited JSON).

**Owner decisions raised by P4 (open, not blocking the devnet):**
- **D-U1** A claim to a Sapling (`ys1…`) destination is refused (`bad-address`): an intent commits a transparent
  recipient script. Recommendation: accept; the claimant shields afterwards.
- **D-U2** A node whose Yellowback index is unhealthy halts (`AbortNode`) instead of running unpoliced.
  Recommendation: accept (it is what consensus requires).
- **D-U3** A cancelled wrong-price claim forfeits its burn (U-24). Recommendation: accept (it prices a griefing
  attempt and only over-collateralises the system).

**Found by P4-b (`up-p4b-dd`, 2026-10-06):** (40) the YED module mirrors the set's acts from the block's own
transactions into its `Attestors[seq]` records (one seq per join; weight = bond × age as in v3), so the Yellowback
index never reads the vault DB and still rebuilds alone; (41) seat eligibility = the set's rules plus the module's
stricter ones (maturity `max(set, BOND_MATURITY)`, `BOND_MIN`/`BOND_MIN_LOCK`, a key that ever had a frozen bond
never seats again; S15 dormancy on top of the set's; revival = a `SET_HEARTBEAT` after dormancy); `ATTESTOR_REGISTER`
/ `ATTESTOR_REVIVE` invalid after activation; `seated` ≤ min(`N_SLOTS`, set `seats`); (42) EQV-1 finds the signing
key by trying candidate members and must bypass the W8 signature cache (keyed by attestation, not key);
(43) `SCHEMA_VERSION` 7; golden state hash `b0103e92…20bc`; `yed_registerattestor`/`yed_revive` now send
`set_join`/`set_heartbeat` with unchanged result shapes (rpcversion stays 5); the Rust agent heartbeats every
`heartbeat_blocks` (default 1,152). (44) The workspace contract generator does not reproduce the upgrade line's
contract JSON (cf. (39)); the JSON is edited to the generator's shape by hand until (39) is resolved.

**Owner decisions raised by P4-b (open, not blocking the devnet):**
- **D-U4** An attestor's price key, bond key and fee key are now **one key** (the set keys the bond by the member
  key, and heartbeats need it online), so the bond can no longer be held cold. Recommendation: accept for this
  round; a later act could let a member name a separate hot key (one more field in `SET_JOIN`), recorded as given up.
- **D-U5** Signing prices is not a set act (U-19), so attestors must heartbeat on chain to stay live: mainnet's
  attestor-set `livenessWindow` must be well above the agent's `heartbeat_blocks` (devnet: 1,000 vs 100; framework:
  100,000). Recommendation: `livenessWindow` 4 × `heartbeat_blocks`, set in P8 with O-13.

**Found by the P6 clients (2026-10-06):** (45) the node no longer lists `yellowback` in `getexperimentalfeatures`
(P4-a), so clients probe `yed_getinfo` directly (−32601 = no Yellowback); (46) `set_getinfo.memberlist[].wallet`
and `vault_list[].wallet` reveal which keys the serving node's wallet holds — public proxies (lightwalletd does)
must strip them; (47) the vault RPCs have no machine-readable contract (prose doc, decimal YEC amounts): a
`vault-rpc-contract.json` on the node would let clients share fixtures (open); (48) yolo needs no change: a v4
coinbase carries no branch ID and the pool uses the node's `coinbasetxn` and roots.

**Found by chain-viz (2026-10-06):** (49) `vault_decodescript` emitted a duplicate `"type"` key for acts; it is now
`"type": "act"` with `"acttype"` (ycash-dd `a903fae2f`; ycash6 to mirror); (50) `vault_buildcancel` cannot pre-build
a cancel for an intent still in the mempool (it reads the originating vault from the vault DB) — relevant to G-11
cancel latency; (51) the rate fields render in YEC decimals in RPCs though §15.4 stores zatoshi (units only).

**Found by x402 (2026-10-06):** (52) a light client that signs with `GetLightdInfo`'s chain-tip branch signs the
wrong branch on the block before an upgrade; clients must use `YellowbackStreamer.GetChainInfo.nextBlockBranchId`
(asked once per tip height: the streamer is rate-limited); (53) librustzcash6 `4867cf85` marks Vault
`has_orchard = true` and accepts V5 while `suggested_for_branch(Vault)` is V4 — permissive, Ycash's own NU5 gate
decides; noted for other crate users.

**Found by the 6.20.0 P4-b primitive port (2026-10-06):** (54) on 6.20.0 the miner's running copy is
`vault::TemplateRun`, which takes the ancestor hashes in its constructor (miner.cpp unchanged); (55) ycash6 splits
`VaultState::ApplyEjections` into a loop plus `ApplyEjectionsOf(const Module&, tx, h)` as a test seam (no behaviour
change) — back-port to ycash-dd so the two lines' `state.cpp` stay identical (assigned with the YED-half port).

**Found by YEW (2026-10-06):** (56) **defect, both lines:** `yed_validaterawtransaction` (`VerifyAllInputs`,
`src/yellowback/policy.cpp`) verifies with static flags, so every intent RELEASE is reported invalid (cf. (17));
fix in flight (`fix-validate` on ycash-dd; ycash6 in the P4-a port). (57) A stale crate-local attest agent build
breaks a fresh devnet `up` after P4-b (`heartbeat_blocks`); rebuild the agent. (58) YEW refuses shielded spends after
activation rather than mis-signing them until it builds against librustzcash6 `upgrade/vault` and x402-light's
`upgrade/vault` (open: repoint YEW's path deps on its `upgrade/vault` branch). (59) `params.attestorSetId` is
display-order hex (`GetHex`); clients reverse it like a txid before pushing it into the V.

### 15.6 Template rules (consensus, outside the interpreter; from activation)

- **S-1** At most one template input per transaction. A template input's scriptSig is push-only and its selector parses (§15.3); else invalid.
- **V-1** A V output's `setId` and `cancelSetId` exist (created in an earlier block). If its tag is registered (§15.7), the module's `ValidateCreate` also passes. Creation adds its value to `lockedValue(setId)`.
- **S-2 (UNLOCK, APP covenant)** A V input spent with selector 1 or 4: every output is an I output with the V's `tag, setId, cancelSetId, delay, ownerKey` and `vaultHash = SHA256(V.spk)`, or a V output with byte-identical scriptPubKey (re-lock), or OP_RETURN, or an ordinary output; and `Σ I + Σ re-lock ≥ V.value` (the vault's value never leaves to ordinary outputs; the fee comes from other inputs).
- **S-3 (rate)** For such a spend, `unlocked = Σ I`. Epoch roll per U-20, then `epochUsed + unlocked ≤ epochBasis × rateLimitBps / 10000` unless `rateLimitBps = 0`. `lockedValue −= V.value; += Σ re-lock`.
- **S-4** Selector 4 with `appHeight = 0` is invalid. A V spent with selector 2 or 3 subtracts its value from `lockedValue`.
- **I-0** An I output may only be created by a transaction satisfying S-2 (or by a cancel's re-lock, which creates a V, never an I).
- **I-1 (RELEASE)** selector 1: the transaction has an output with `SHA256(spk) = recipientHash` and value ≥ the I value.
- **I-2 (CANCEL)** selector 2: `h − coinHeight < delay`, and an output with `SHA256(spk) = vaultHash` and value ≥ the I value (it is a V, so V-1 applies and `lockedValue` grows again).
- **I-3** selector 3: script only.
- Module dispatch: for a template input or output whose tag is registered, the module's `ValidateSpend` / `ValidateCreate` runs after the primitive rules. A module can only reject.
- Mempool: all of the above against the tip snapshot at tip+1; `ConnectTip`/`DisconnectTip` re-check mempool template spends and acts (set state, BIP68 and I-2 change with height).
- Miner: transaction selection applies acts and S-3 against a running copy and skips a transaction that fails.

### 15.7 Module table

`src/vault/module.h`: `class Module { virtual std::optional<std::string> ValidateCreate(const CTransaction&, size_t vout, const VaultParams&, const ModuleContext&) const; virtual std::optional<std::string> ValidateSpend(const CTransaction&, size_t vin, const TemplateSpend&, const ModuleContext&) const; virtual std::optional<std::string> CheckBlock(const CBlock&, const CBlockIndex*, const ModuleContext&) const; }`, and `const Module* FindModule(const std::array<unsigned char,4>& tag)`. Empty in P2. P4 registers `{ 'Y','E','D',0x00 }`. `WYEC` (`{'W','Y','E','C'}`) is never registered (§4).

### 15.8 RPCs (primitive; wallet-signing ones keep keys in the node)

Read: `vault_getinfo` (activation height, branch ID, counts), `set_list`, `set_getinfo "setid" [height]` (params, members, current/dormant/released, rate fields), `vault_list {"tag","setid","owner"}`, `vault_decodescript "hex"`.
Acts: `set_create {params}` → setId; `set_join "setid" bondamount bondlocktime ["memberkey"]`; `set_heartbeat "setid" ["memberkey"]`; `set_buildact "type" {params}` → funded, unsigned act hex (vin[0] fixed); `set_signact "hex" "setid"` (adds this wallet's member or admit signatures); `set_sendact "hex"` (signs inputs, broadcasts); `set_equivocation {proof}`.
Vaults: `vault_lock {tag, setid, cancelsetid, delay, ownerheight, appheight, amount, ownerkey?}`; `vault_buildunlock "outpoint" [{"address"|"script", amount}] ` → funded unsigned hex; `set_signunlock "hex"`; `vault_buildcancel "intentoutpoint"`; `set_signcancel "hex"`; `vault_send "hex"`; `vault_release "intentoutpoint"`; `vault_ownerspend "outpoint" "address"` (selector 2 or 3 automatically); `vault_app "outpoint" [intents]` (selector 4 skeleton, for modules).
All registered in `rpc/client.cpp` conversions; documented in `doc/vault-rpc.md`.

### 15.9 Tests and vectors

- `qa/rpc-tests/test_framework/vault.py`: template builders/parsers, act codec, `setSigMsg`/`actMsg`, recoverable signing (pure Python, RFC 6979, low S), `VAULT_BRANCH_ID`. It writes `src/test/data/vault_vectors.json` (templates, acts, messages, signatures from fixed keys); `src/test/vault_vectors_tests.cpp` replays it. **The file is byte-identical on both lines.**
- Unit: `vault_template_tests`, `vault_act_tests`, `vault_state_tests` (join/maturity/dormancy/release/removal/equivocation/winddown/rate epochs/undo), `vault_script_tests` (opcodes, CSV, BIP68), all `--run_test='vault_*'`.
- Functional (`qa/rpc-tests/`, executable, in `rpc-tests.py` and the workflow's lists): `vault_upgrade.py` (activation, branch ID in signing, CSV/BIP68 before/after, opcode bytes invalid before), `vault_primitive.py` (set lifecycle, lock, unlock → intent → release, cancel, owner after height, owner on dormancy, wind-down, rate limit, reorg/undo, restart reconciliation), `vault_slashing.py` (equivocation, remove with/without burn, frozen bond), `vault_bridge.py` (P3: both shapes).

### 15.10 YED on the primitive (P4)

- **U-21** The YED module is the delivered `src/yellowback/` with the §6 removals. Its block verdict (`EvaluateBlock` → `blockInvalid`) is a **consensus** rejection (`DoS(100)`, `bad-yellowback-*`) at every height where `UPGRADE_VAULT` is active, with none of today's node-local conjuncts (enforce flag, valve, IBD, catch-up, sunset). Header-note hook, rejected set, kill switch, valve, signalling, lock-in, `ENFORCE_UNTIL_HEIGHT`, abandonment and template policy go. Mempool check becomes ordinary validity.
- **U-22** The index is **always on** where `UPGRADE_VAULT` and a YED attestor set are configured (`-yellowback` and `-experimentalfeatures` no longer gate it). Parameters: `yellowbackStartHeight` = the activation height; `attestorSetId` per network (mainnet/testnet unset; regtest `-yellowbackattestorset=<setid>`). YED is live from the first block at which both are known.
- **U-23** A MINT's vault output is a V with `tag = YED\0`, `setId = cancelSetId = attestorSetId`, `delay = CLAIM_DELAY`, `ownerHeight = lockHeight`, `appHeight = lockHeight + GRACE`, `ownerKey` = the payload's owner. Owner redeem = selector 2 (+ REDEEM payload, RED rules as today). Claim = selector 4 into intents (claimant's debt-worth and the owner's residual, RED-4/RED-5 checked at intent creation; the REDEEM payload's burn happens there). Release after `CLAIM_DELAY` closes the vault; an attestor cancel (I-2) returns the collateral to a byte-identical vault, which the module re-indexes as the same position (ACTIVE). **The cancelled claimant's burn is not refunded** (U-24: a wrong-price claim costs its burn; supply falls, the vault's debt does not, so the system only becomes more collateralised). The v3 anyone-can-spend claim branch and CLAIM_NOTICE's role in path (b) stay only as the module reads them; `VaultScript` (P2SH) is no longer accepted for new mints after activation.
- **P4-b** The attestor registry becomes the primitive set `attestorSetId`: a seat is a current member, its bond weight is the member's bond value, maturity/dormancy are the set's; `ATTESTOR_REGISTER` and `ATTESTOR_REVIVE` are invalid after activation; EQV-1 (two prices at one height) stays in the module and freezes the member's bond via the set's frozen-bond rule.
- VOID: a MINT failing `MintVerdict` is an invalid transaction; `voidReason` and VOID vault records are not produced after activation.
- Golden vector `yellowback_golden.json` regenerated once with the diff explained in its commit; `yellowback_model.py` follows (enforcement removed; block 217 becomes an invalid block, not "applied anyway").
- Obsolete: `yellowback_enforcement.py`, `yellowback_activation.py`, `yellowback_attest_enforcement.py` and the unit cases listed by the 2026-10-05 survey (index valve/suppression cases, `act*`, `blk1/blk2`). Removed with the code they test, in the same commit.
