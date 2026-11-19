# beta4: a real price feed on the fast testnet (items 3c-3f)

**Revision 4 (2026-11-18).** All decisions are taken by the Yellowback lead architect (§0). The plan is
organised as deliverables, each with its tasks and testable done-criteria, plus a dependency order (§6).

**Scope.** Beta4 list items:

- 3c: highly available attestors;
- 3d: an attestor without a full node, cancel watcher included;
- 3e: the release part — the attestor set on chain, its id compiled into ycash6, ycash-dd and kogany;
- 3f: a post-quantum payout key in the coinbase tag.

Items 3a (pool quotes) and 3b (quote cadence) have their own plan in this directory. The 3b decision is
recorded in §0.

**Citations.** Every citation is `repo/path:line` at `origin/upgrade/vault`:

| Repo | Commit |
|---|---|
| ycash6 (primary) | `c6f009957` |
| ycash-dd | `c07b8a734` |
| kogany | `36667efc9` |
| lightwalletd-dd | `56660e5` |
| yew | `6feaf99` |

ycash-dd matches ycash6 wherever it is not named. These have identical blob ids on the two C++ lines:
`src/yellowback/{params,state,bundle,module,tag,attest}.cpp`, `src/vault/state.cpp` and
`contrib/yellowback/attest/`.

**Fast-testnet target spacing:** 75 s per block.

## 0. Decisions (lead architect, 2026-11-18)

| # | Subject | Decision |
|---|---|---|
| D-1 | House seats and layout | **9 house seats on 3 hosts (3+3+3).** One key per seat, never a key on two hosts. This amends the testnet plan's T-5, which had 7 seats |
| D-2 | Host placement | **3 regions**, not 3 zones in one region |
| D-3 | Bond and set floor | **20 YEC** for both the house bond and the set's `bondmin` |
| D-4 | Set livenessWindow | **1,152 blocks** |
| D-5 | Ceremony order | **Ceremony first, with the scanned gap** (§3.3) |
| D-6 | Light attestor | **The attest agent over lightwalletd-dd**, with:<br>• local signing and a guard file;<br>• a new `YellowbackStreamer.SubmitAttestation`;<br>• join, exit and heartbeat built in YEW core |
| D-7 | Cancel watcher on light seats | **In beta4** (§2.3) |
| D-8 | Post-quantum payout key | **Tag v2 in beta4, in the same consensus release as the set id.** No later consensus change |
| D-9 | kogany at the upgrade | **Resync**, plus a startup check that says "resync required" |
| D-10 | Tag v1 next to v2 | **Keep v1 for ECC payees and add v2 for post-quantum payees.** Both are valid from YED's start |
| D-11 | 3b quote cadence | **`yed_setquote` every 60-75 s, no heartbeat, no change threshold.** Accuracy is chosen over job churn: each call rebuilds the template (`quoteGeneration`) |

## 1. How attestation works (from the code)

### 1.1 The statement

- **Size and layout:** 74 bytes: seq u16, price u32, citedHeight u32, sig 64 (`src/yellowback/attest.h:31-45`).
- **What is signed:** SHA256(`"YBATTEST1"` ‖ seq LE16 ‖ priceMicroUsd LE32 ‖ citedHeight LE32 ‖ blockHash(citedHeight)), with a secp256k1 compact signature (`attest.cpp:17,39-50`).
- **Who signs:** the node wallet, through `yed_signattestation` (`src/rpc/yellowbackwallet.cpp:1546-1565`). The agent holds no key (`contrib/yellowback/attest/src/main.rs:1-5`).
- **Guard:** `<datadir>/yellowback/attest-signed.dat` refuses a second price for the same (seq, citedHeight), and returns the stored signature for the same price.
- **Cadence (agent policy):** sign every k = 10 blocks, citing `tip − 2` (`attest.toml.sample:30-33`, `params.cpp:122`).

### 1.2 How a statement reaches a block

**Statements never pass through miners.**

- Node P2P does not relay them: `ProcessMessage` has only the stock messages.
- The block template does not read them: the miner uses Yellowback only for the quote tag and `FilterTemplate` (`src/miner.cpp:359-361,573`).
- kogany is the same.

**The path a statement does take:**

1. The agent publishes it on an iroh-gossip topic, `yellowback/attest/<network>/3` (`attest/README.md:71-87`).
2. A `subscribe` agent beside each transaction-building node feeds it in with `yed_addattestation` (`subscribe.rs:268`). This is the only way into the node's pool (`src/rpc/yellowback.cpp:2048-2072`).
   - kogany has the same RPC with Admin access (`crates/kogany-rpc/src/yed/rpc.rs:163,1277-1299`).
3. The **minter's own transaction** carries a bundle: a MINT, a CLAIM_NOTICE, or a claim REDEEM.
   - The bundle sits in the scriptSig of a P2SH carrier input that commits to SHA256(bundle) (`bundle.cpp:153-163`).
   - It is one 520-byte push, hence BUNDLE_MAX = 6 (`params.cpp:85`).
   - Wallets build it from their pool (`txbuilder.cpp:1188-1197`).
   - Light wallets build it through `YellowbackStreamer.BuildBundle` → `yed_buildbundle` (`lightwalletd-dd/walletrpc/yellowback.proto:347`).

**So statements must reach every node that builds YED transactions for users.** On the fast testnet that
is the node behind the public lightwalletd, plus any ycashd or yewd wallet that mints.

### 1.3 Bundle and price

- **Selection.**
  - At reference height R (`H − 40 ≤ R ≤ H − 1`, `params.h:85-87`), the snapshot seats the up-to N_SLOTS = 9 ELIGIBLE attestors of highest SeatRank, minus pinned seqs.
  - SeatRank is bond × age, with a 5 % hysteresis for seats already held (`state.cpp:1780-1799,2082-2086`).
  - M_SELECT + K_SLACK = 4 + 2 = 6 of the seated are drawn, weighted by bond × age, seeded by blockHash(R) and the selector (`state.cpp:2205-2254`).
  - A mint's selector is empty, so all mints at one R draw the same 6. A claim's selector is the vault outpoint.
- **Valid bundle** (`bundle.cpp:178-236`):
  - 4 to 6 attestations;
  - every seq among the 6 drawn, none twice;
  - citedHeight in (R − 20, R] (ATTEST_MAX_AGE 20);
  - prices in range and every signature valid.

  **So a bundle needs at least 4 distinct live signers among the 6 drawn.**
- **Price.**
  - aMint and aClaim are the bond-weighted 33.33 % and 66.67 % quantiles (`bundle.cpp:239-253`).
  - When ARMED, pMint = min(xMint, aMint) (`view.h:250`). MINT-10 refuses a mint where |pFast − aMint| > 15 % (`state.cpp:463`).
  - xMint comes from the pools' quote tags (`state.cpp:1802-1815`). Without tags HALT-1 applies (`:1847`), so item 3a is a prerequisite.

### 1.4 Arming, maturity, liveness, dormancy

These run in SNAP (`state.cpp:1671-1723,1855-1878`).

| Rule | Mainnet | Fast testnet | Code |
|---|---|---|---|
| Maturity: PENDING → ELIGIBLE at join + max(set maturity, BOND_MATURITY), with the bond at or above the module minimum | 16,128 | 48 | `state.cpp:1687-1702`, `params.cpp:237` |
| ARM-1: UNARMED → TRIGGERED at ELIGIBLE ≥ ATTEST_ARM_MIN | 7 | 7 | `state.cpp:1717-1721` |
| ARM-2: TRIGGERED → ARMED after ATTEST_ARM_DELAY; **ARMED never reverts** | 1,152 | 20 | `state.cpp:1714,1722`, `params.cpp:234` |
| An unarmed mint is refused | yes | yes | `state.cpp:384` |
| Liveness: ELIGIBLE → DORMANT at lastAct < H − livenessWindow. lastAct moves on a heartbeat or a mined bundle | set parameter | 1,152 (D-4; at least 40) | `state.cpp:1690,1704-1710,2088-2131`, `params.cpp:242` |
| S15: a seated seat drawn in ≥ 20 bundle rows within DORMANCY_BLOCKS without signing → DORMANT | 16,128 / every 48 | 48 / every block | `state.cpp:1855-1877`, `params.cpp:245-246` |
| Revival: DORMANT → ELIGIBLE after a heartbeat (`set_heartbeat`, `yed_revive`) | | | `state.cpp:1707-1709` |

On the fast testnet the first mint is possible 48 + 20 = 68 blocks after the last joins.

### 1.5 When signers are lost

- **Fewer than 4 of the 6 drawn have a fresh statement.**
  - A mint at that R gets `bundle-insufficient` (`txbuilder.cpp:1189-1215`).
  - The wallet uses only R = tip − mintLag (`:625`), so a retry at the next block draws a new 6.
  - Claims behave the same way, per vault.
- **Fewer than 4 live seats seated:** no bundle is possible. Minting and claims stop, and the layer stays ARMED.
- **Owner redemption never reads a bundle** (`state.cpp:628`).

### 1.6 Equivocation

- **Evidence (EQV-1).** Two attestations with the same seq and citedHeight and **different prices**, or an attestation and a conflicting cancel statement (C4b) (`state.cpp:2003-2043`).
- **Effect.**
  - The member is ejected and its bond frozen (`state.cpp:1099-1139`, `module.cpp:98-112`, `src/vault/state.cpp:627-655`).
  - A frozen bond is never spendable (`src/vault/state.cpp:450`).
  - The key is barred from seating (`state.cpp:1679-1689`).
- **The same price twice is not evidence** (`:2015`). But two hosts sharing a key fetch prices independently, and each keeps its own guard file. **A shared key therefore risks its bond (D-1).**
- **Going offline is not punished:** it only makes the seat DORMANT.
- **No member can slash another.** The module refuses `SET_REMOVE` of another member and `SET_WINDDOWN` of the set (`state.cpp:2165-2183`).

## 2. Deliverables 3c and 3d: the house attestors

### 2.1 Layout (D-1..D-4)

| Item | Setting |
|---|---|
| House seats | 9 seats, 3 per host, in 3 regions |
| Keys | One key per seat, held by exactly one host, restored only together with that host's guard file and only after the dead host is fenced |
| Bond | 20 YEC per seat, 180 YEC in all |
| Open seats | 6 of the set's 15 stay open to outside attestors (`params.cpp:111`) |

**20 YEC meets the module minimum.** The minimum is clamp(⌈5 % of YED collateral / 9⌉, 10 YEC, 20 YEC) on
the fast testnet (`math.h:378-386`, `state.cpp:2071-2075`, `params.cpp:250-251`). A bond at or above the
cap always meets it (`state.cpp:1696`).

**The floor binds outsiders too.** The ceremony's `--bond 20` sets the set's `bondmin` to 20 YEC
(`contrib/testnet/ceremony/ceremony:298-302,333`), which every outside joiner must meet
(`src/vault/state.cpp:825`).

**What the layout survives.** Bonds and ages are equal, so the 6 seats are drawn uniformly from the 9.
A mint works when at most 2 dead seats are drawn.

| State | Share of R at which a mint or claim can be built |
|---|---|
| All hosts up | 100 % |
| One host down, its statements still fresh (< 10 blocks since its last signature) | 100 % |
| One host down, statements stale | 1 − C(6,3)/C(9,6) = 64/84 = **76 %**; a retry at the next block re-draws |
| One host down for longer than livenessWindow (1,152 blocks) | **100 %**: its seats go DORMANT, leaving 6 seated, all live |
| Two hosts down | **0 %**: minting and claims stop, owner redemption continues |

For comparison, T-5's 7 seats (3+2+2) give 3/7 = 43 % when the 3-seat host is lost.

**Recovery by event:**

| Event | Recovery |
|---|---|
| Agent restart within 10 blocks of its last signature | invisible |
| Host back within 1,152 blocks | signs at its next tick |
| Host back after 1,152 blocks | `yed_revive` or `set_heartbeat` per seat, then ELIGIBLE at that block's SNAP |
| Key compromise | `set_leave`, withdraw after the exit delay, join a new key (ELIGIBLE after 48 blocks) |

### 2.2 The light attestor (D-6)

**What the agent uses on a node today** (`contrib/yellowback/attest/src`, identical in ycash-dd):

| RPC | Use | Wallet? |
|---|---|---|
| `yed_getinfo` (`attest.rs:183`) | tip, network, set id; every poll (15 s) | no |
| `yed_signattestation` (`attest.rs:239-245`) | sign every 10 blocks | **yes** |
| `yed_listattestors`, `set_getinfo` (`attest.rs:318`, `cancel.rs:861,870`) | seq, key, status | no |
| `set_heartbeat` (`attest.rs:340`) | liveness transaction | **yes** |
| `getblockchaininfo` (`cancel.rs:1044`) | sync check | no |
| the cancel set of §2.3 | cancel watcher | partly |
| `validateaddress`, `signmessage` (`cancel.rs:1849,1871`) | bind the iroh endpoint to the member key | **yes** |
| `yed_registerattestor` / `set_join`, `set_leave`, `yed_withdrawbond` | operator one-offs (`yellowbackwallet.cpp:1297-1315`, `vault.cpp:3081`) | **yes** |

The bond is P2SH(lock CLTV DROP memberKey CHECKSIG), so the seat key also controls its bond. yewd serves
every one of these names over koganyd (`yew/yewd/wallet/src/attest.rs:41-52`, `vaultrpc.rs:40-60`), but it
reaches a node only through node RPC (`yewd/README.md:7-8`).

**The light design.** A light seat is the agent alone: a seat key file, a guard file, and two
lightwalletd-dd endpoints in different regions.

| Need | Source |
|---|---|
| Tip height and hash; hash at citedHeight | `CompactTxStreamer.GetLatestBlock`, `GetBlock` (exist) |
| Seq, key, status; set; network | `YellowbackStreamer.ListAttestors`, `GetSet`, `GetYellowbackInfo` (exist, `yellowback.proto:332-356`) |
| Signature | in the agent: the message of §1.1. YEW core has `attest_message` (`yew/core/src/bundle.rs:73-194`); yewd's signer has the guard logic (`yewd/signer/src/attest.rs:5-26`) |
| Delivery | iroh gossip (unchanged), and **new `SubmitAttestation`** → `yed_addattestation` on the lightwalletd's node, the pool YEW's `BuildBundle` reads |
| Heartbeat, join, exit, withdraw | **new** YEW-core builders for `SET_HEARTBEAT`, `SET_JOIN`, self-`SET_REMOVE` and the bond spend (act codec in `yew/yewd/proto/src/act.rs:20,167-222`), funded through `GetAddressUtxos`, sent with `SendTransaction` |

**New lightwalletd-dd calls.** Each is an allow-listed proxy (`common/yellowback.go:8-11,70-111`).
`yed_addattestation`, `yed_gettag` and `gettxout` exist on all three node lines.

| Call | Proxies | Guards / purpose |
|---|---|---|
| `SubmitAttestation(bytes)` | `yed_addattestation` | exactly 74 bytes; seq is a current member (cached `yed_listattestors`); at most one frame per seq per 5 blocks; per-IP limit |
| `GetTag(HeightFilter)` | `yed_gettag` | quote tags for light monitors; shared with 3a |
| `GetTxOut(outpoint, includeMempool)` | `gettxout` | for §2.3 |
| `GetMempoolTxids` | `getrawmempool` | for §2.3. `GetMempoolTx` returns compact transactions without inputs |

**Trust.** A lying lightwalletd can make the agent cite a wrong hash. That statement is invalid, and it
cannot be equivocation, because EQV-1 verifies under the real block hash (`state.cpp:2033`). So
lightwalletd affects liveness, never the bond.

**Rejected options:**

- **yewd with a lightwalletd backend:** its whole wallet assumes node RPC.
- **One full node per region holding the seat keys:** that is layout D-1 on full nodes.

### 2.3 The cancel watcher on light seats (D-7)

**Today** (`cancel.rs:5-29`):

- **Watcher.** It judges every confirmed claim at its refHeight with the seat's recorded price. A wrong-price claim (not claimable at that price, with `margin_bps` to spare) is co-signed and published.
- **Gossip.** It takes in co-signature frames (115 bytes), rate-limited per peer and per seq.
- **Collector.** A rota of members, rotated by the intent hash, picks one driver per claim. The driver collects `cancelsRequired` co-signatures plus spares, then calls `yed_buildcancel`, `set_signcancel` and the broadcast.

**Limits that matter:**

- The cancel must confirm within CLAIM_DELAY: 20 blocks on the fast testnet (`params.cpp:229`).
- `cancelsRequired` is 1, then rises by one for each further cancel within CANCEL_QUIET, up to 4 (`yellowbackwallet.cpp:2253-2256`, `params.cpp:116,243`).
- **A fourth cancel therefore always needs co-signers on two hosts.**

**What it reads, and the light source for each:**

| Read (today, `cancel.rs` line) | Light source |
|---|---|
| Claims in CLAIMING: intent, refHeight, burn, `cancelsRequired`, `refundHolder` (`yed_listvaults` :905, `yed_getvault` :1257) | `ListVaults(status "CLAIMING")`, `GetVault` (exist, `yellowback.proto:25,170`) |
| Claim transaction and payload (:955, :961) | `GetTransaction`, `DecodePayload` (exist) |
| Block hashes and reorgs (:937) | `GetBlock`, `GetLatestBlock` (exist) |
| The seat's recorded prices (:1010) | `GetAttestations` (exists), plus the guard file |
| Set and members (:861, :870) | `GetSet`, `ListAttestors` (exist) |
| Spent or unspent, mempool included: intent, carrier, lingering cancel, fee inputs (:1248, :2127) | **`GetTxOut`** (new) |
| Claims and cancels in the mempool (:2113) | **`GetMempoolTxids`** (new) |

**How co-signatures and the cancel are submitted:**

- **Co-signatures go to the driver, not to a node.** No node keeps a pool of them; `yed_buildcancel` takes them as arguments. They travel over:
  - the cancel gossip topic and the members' direct iroh endpoint (unchanged);
  - the on-chain fallback, an OP_RETURN "YF" transaction (`onchain.rs:1-19`), built from the seat's own coin and sent with `SendTransaction`.
- **Signing is local.** A co-signature signs `CancelCosignMessage(setId, intent, n, citedHeight, price, blockHash)` (`state.cpp:2041`). It goes into the guard file, because a co-signature that conflicts with an attestation is equivocation (`state.cpp:2018-2022`). The endpoint binding is signed locally too.
- **The driver builds the cancel in YEW core.** This ports `yed_buildcancel` and `set_signcancel` (`yellowbackwallet.cpp:2243-2265`):
  - vout 0 re-creates the vault;
  - vout 1 refunds the burn to `refundHolder`;
  - the co-signature carrier is the last input, and the CANCEL_COSIGN marker the last output;
  - the member key signs SIGHASH_ALL|ANYONECANPAY under the Vault branch ID;
  - fees come from the seat's own coins.

  YEW core already builds claims and carriers (`yew/core/src/build/claim.rs`).
- **Checked, then sent.** The driver checks the cancel with `ValidateRawTransaction` (exists), then sends the carrier and the cancel through both endpoints.
- **No co-signature mailbox in lightwalletd:** it would put state there, and the agent already runs iroh.
- **Two endpoints, checked against each other.** A lightwalletd can hide a claim, which only affects liveness. A claim must appear on both endpoints before the seat co-signs. A fake claim yields a co-signature no rule counts.

### 2.4 Tasks

| # | Repo | Change |
|---|---|---|
| A-T1 | ycash-infra, ycash-ops | Seat-host recipe in 3 regions: agent, key files, guard file, monitoring, alerting. A full-node fallback (ycashd wallet, or yewd + koganyd) is used only while B-T3 is not done |
| A-T2 | ycash-infra, ycash-ops | A second lightwalletd-dd in another region; the subscribe agent beside each lightwalletd node |
| A-T3 | ycash-infra (status page) | Label the feed "house-operated" |
| A-T4 | ycash-infra | Runbook: fence the dead host, restore its keys together with its guard file, revive the seats |
| A-T5 | ycash6, ycash-dd, yew | Wallet retry on `bundle-insufficient` at the next block (ycashd wallet, yewd, YEW) |
| B-T1 | lightwalletd-dd | `SubmitAttestation`, `GetTag`, `GetTxOut`, `GetMempoolTxids`, with guards; tested against ycash6 and kogany |
| B-T2 | yew | Core builders for `SET_JOIN`, `SET_HEARTBEAT`, self-`SET_REMOVE` and the bond withdraw; a `yew-attestor` CLI for the one-offs |
| B-T3 | ycash6 + ycash-dd `contrib/yellowback/attest` | `[backend] lightwalletd`: two endpoints, local signer, key file, guard file, heartbeat through YEW core |
| B-T4 | ycash6 + ycash-dd `contrib/yellowback/attest` | Cancel watcher over lightwalletd: the reads of §2.3, local co-signature and binding signatures, on-chain fallback, driver through YEW core |
| B-T5 | yew | Core cancel builder: the `yed_buildcancel` and `set_signcancel` port, co-signature carrier |

### 2.5 Done when

| # | Criterion |
|---|---|
| A-1 | Each of the 3 hosts, in 3 regions, holds exactly 3 seat keys. No key file exists on two hosts (inventory check) |
| A-2 | With all hosts up, `yed_listattestors` shows 9 house seats ELIGIBLE and seated, and `yed_getinfo` shows ARMED |
| A-3 | Regtest, one host of three stopped: over 100 blocks, at least 70 % of mint attempts succeed, and every mint succeeds on a retry at the next block |
| A-4 | Regtest, one host stopped beyond livenessWindow: its 3 seats are DORMANT, 6 seats are seated, and every mint attempt succeeds. After restart and revive, they are ELIGIBLE again |
| A-5 | Regtest, two hosts stopped: a mint fails with `bundle-insufficient`, and an owner redemption succeeds |
| A-6 | A restored host refuses to re-sign one of its already signed citedHeights at a different price (`equivocation-guard`) |
| A-7 | The status page names the feed house-operated |
| B-1 | A light seat host runs no node process. Its agent signs at every interval from lightwalletd data alone |
| B-2 | A statement sent through `SubmitAttestation` appears in `GetAttestations` and in a `BuildBundle` result on that lightwalletd's node (ycash6 and kogany backends) |
| B-3 | `SubmitAttestation` refuses a wrong size, a non-member seq and a frame above the rate limit |
| B-4 | A YEW mint through the fast-testnet lightwalletd carries a bundle containing light seats' statements |
| B-5 | `SET_HEARTBEAT`, `SET_JOIN`, `SET_LEAVE` and the bond withdraw, built by YEW core, confirm; lastAct advances after a heartbeat |
| B-6 | With one of the two lightwalletd endpoints stopped, a light seat keeps signing |
| B-7 | Regtest, a lightwalletd serving a wrong block hash: the seat's statements are rejected, and no equivocation evidence or ejection follows |
| B-8 | Regtest, light seats only: a wrong-price claim is cancelled within CLAIM_DELAY. The 1st to 4th cancels within CANCEL_QUIET succeed, the 4th with co-signers on two hosts |
| B-9 | With gossip blocked, the on-chain "YF" fallback delivers a co-signature and the cancel confirms |
| B-10 | A claim shown by only one of the two endpoints is not co-signed |

## 3. Deliverable 3e: the release part

### 3.1 Facts

- **Heights.**
  - The fork is at 510,248 and Vault (H_V) at 510,400 (`ycash6/src/chainparams.cpp:449,663`; `ycash-dd/src/chainparams.cpp:602`).
  - YED's start height becomes the Vault height once an id is set (`src/yellowback/index.cpp:1153-1166`; kogany `crates/zakura-state/src/service/finalized_state/zakura_db/yed.rs:192-211`). **YED therefore starts at 510,400, retroactively.**
- **No network carries an id today.**
  - Only RegtestParams sets one (`params.cpp:349`), and `-yellowbackattestorset` is regtest-only (`init.cpp:455`).
  - A slot is needed in `TestFastParams` on the three lines. The tests that assert the id is null need updating: ycash6 `testnet_params_tests.cpp:322`; kogany `tests/params_tables.rs:463`, `tests/params_cpp.rs`.
- **Adoption needs** (`params.cpp:111-115,237,242`; `state.cpp:1176-1193`) an open set with:
  - 15 seats, cancel threshold 1, unlock threshold 1, rate limit 0;
  - maturity 48;
  - livenessWindow ≥ 40.

  The ceremony's parameters meet these (`ceremony:298-302`).

### 3.2 The two open questions

**The ceremony accepts a chain past the fork.**

- `check` needs (`ceremony:251-280`):
  - the profile;
  - blocks ≥ 510,247 and the prefix hash;
  - no other governed set;
  - Vault > fork;
  - a peer and no IBD when mining.
- `fork` and `vault` return at once on a longer chain (`mine_to`, `:192-210`).
- Nothing ties `SET_CREATE` to H_V.
- `record` reads every block from 510,248 (`:366-368`).
- Run it with `--no-mine`.

**Replaying 510,400..tip with the earlier joins:**

| Line | Result |
|---|---|
| ycash6, ycash-dd: **in place** | The primitive indexes set state from Vault regardless of params (`src/vault/node.cpp:366-411`). The YED index, having no tip, applies 510,400..tip (`index.cpp:309-341`) and adopts the `SET_CREATE` whose txid is the id (`state.cpp:1176-1193`). `ApplyBlock` never fails (`state.cpp:1964-1972`). No reindex is needed, but a pruned node must resync (`doc/yellowback.md:148`) |
| kogany: **stops** | There is no in-place YED rebuild (`yed.rs:24-29`). The first new block fails `check_base` with `TipMismatch` (`yed.rs:439-448`), and the node stops (`yed.rs:772-789`). The format migration that asks for a resync runs only on the move to 30.2.0 (`disk_format/upgrade/add_yed_state.rs:26-28,69-78`). Hence D-9 |

### 3.3 The gap (D-5) and the rollout order

**Blocks between `SET_CREATE` and the upgrade.** In-place nodes keep them; nodes that sync fresh judge
them with the module live. The module refuses:

- a `SET_WINDDOWN` of the set;
- a `SET_REMOVE` of another member (`state.cpp:2165-2183`);
- a `SET_JOIN` below BondMinZat (`state.cpp:1148-1160`).

It also decides displacement into a full set (`module.cpp:116-168`). If such an act is mined in the gap,
the chain splits.

**Retroactive tags.** YED starts at 510,400, so any coinbase since then that carries a tag pattern
becomes a tag record.

**Measures:**

- the ceremony runs only after the consensus PRs (P1) are approved and frozen;
- every block from 510,400 to the release is scanned for acts naming the set, and every coinbase for the v1 and v2 tag patterns;
- if any are found, the ceremony is rerun with a new set.

**Rollout order.** Upgraded nodes enforce YED rules that beta3 nodes do not. Upgrade in this order:

1. the pool's node and miners;
2. seeds, lightwalletd and the explorer;
3. kogany nodes, by resync.

**YED-live regtests and devnets resync at beta4** (recorded 2026-11-19, P1 review). A chain on which YED was already
live before beta4 (a devnet, a long-lived regtest) must be resynced from genesis with the beta4 binary, not rebuilt in
place from its stored blocks under the old index. Before beta4 a `0x31 "YED!"` byte run in a coinbase scriptSig was no
tag; from beta4 it can be a v2 tag, and a v2 tag that comes first now decides (TAG-5). So a historical block can gain a
tag record, which changes E(R) and every fee verdict that reads it. SCHEMA_VERSION 16 forces the index rebuild on
ycashd; the release notes tell operators of such chains to resync (kogany refuses to start: "resync required", D-9).
The fast testnet and mainnet carry no tag before the release (the gap scan, C-5), so this note concerns private chains.

**Client releases before the node rollout** (recorded 2026-11-19, P1 review: a hard prerequisite of P5, not fixed by
P1). `rpcversion` 11 makes the shipped clients switch Yellowback off when they meet a beta4 node: lightwalletd-dd
(`common/yellowback.go`, the known version 10), YEW core (`net/yellowback.rs`) and YecWallet (`RPC_VERSION` 10) all
treat a newer version as unknown. Their D-T8 updates (accept 11, render post-quantum payees) ship and are deployed
before step 2 of the rollout order above.

### 3.4 Tasks

| # | Repo | Change |
|---|---|---|
| C-T1 | ycash-dd → ycash6 → kogany | The id slot in `TestFastParams`, in the P1 consensus change set (two-reviewer gate, four-part check). Parameter-table tests updated |
| C-T2 | kogany | A startup check: with Yellowback on and the YED tip behind the start height on a database past it, print "resync required" and exit |
| C-T3 | ycash6 | A ceremony test against a chain well past H_V (`--seats 9 --bond 20 --no-mine` against a mining peer) |
| C-T4 | ycash6, ycash-dd | A replay-equivalence test: inert from H_V, set created and joined late, restarted with the id, compared with a fresh sync |
| C-T5 | ycash6, kogany | A gap-split test: a gap block carrying a foreign `SET_REMOVE`, a `SET_WINDDOWN` or a below-minimum join |
| C-T6 | ycash6 `contrib/testnet/ceremony` | The gap scan: set acts and tag patterns from 510,400 to a given height |
| C-T7 | operations | The ceremony on the fast testnet: fund ≥ 9 × (20 + `FEE_MARGIN`) YEC; `--steps set,seats`; split the key files 3/3/3 to the hosts and delete them from the ceremony host; fill in the id; scan; tag beta4; upgrade in order; `--steps mature,record` |

### 3.5 Done when

| # | Criterion |
|---|---|
| C-1 | C-T3 passes: the ceremony completes on a chain past H_V |
| C-2 | C-T4: an in-place upgraded node and a fresh-sync node report the same `yed_getstatehash`, vault state hash and `yed_listattestors` at the tip (ycash6 and ycash-dd) |
| C-3 | A kogany beta3 database started with the beta4 binary prints "resync required" and exits. After the resync its state hash equals ycash6's |
| C-4 | C-T5 shows different in-place and fresh-sync verdicts for the gap-split case |
| C-5 | The gap scan of the fast testnet reports zero acts on the set and zero tag patterns before the release |
| C-6 | On the fast testnet after the upgrade, `yed_getinfo` reports `attestorSetId` = the `SET_CREATE` txid, 9 ELIGIBLE house seats, ARMED, and a defined pMint |
| C-7 | A YEW mint on the fast testnet succeeds |
| C-8 | The parameter tables with the compiled id pass on all three lines |

## 4. Deliverable 3f: tag v2, a post-quantum payout key (D-8, D-10)

### 4.1 Today

- **The v1 tag** is 36 bytes (`src/yellowback/tag.h:17-21`, `tag.cpp:38-55`): `"YED!"`, 0x01, flags, price u64, sourceMask u16, **payoutKey Hash160 (20 bytes)**. It is pushed as `0x24` + 36.
- **FindTag** scans after the height push for `24 59 45 44 21` (`tag.cpp:57-80`):
  - the first match decides (TAG-5);
  - an unknown version means no tag, and the block stays valid (TAG-4).
- **Fees go to P2PKH(payoutKey):**
  - E(R) is built in `state.cpp:1554-1573`;
  - MINT-8 (`:423-430`) and RED-3' (`:644-657`) take only a 25-byte P2PKH (`:88-94`);
  - PIN-1, `TagRecord` and the vault fee records use `uint160` (`:1740-1748`, `view.h:185-200`, `state.cpp:493,776`).
- **The payout address must be P2PKH.** `-yellowbackpayoutaddress` and `-yellowbackpreferredpayee` refuse anything else (`init.cpp:1648-1655`; default from `-mineraddress`, `:2467-2472`).
- **kogany** has the same rules: `crates/kogany-yellowback/src/codecs/tag.rs:22-111`, `lookups.rs:79-97`, `state/mint.rs:238-246`, `state/redeem.rs:187-201`. Its payout is P2PKH of `mining.miner_address` (`kogany-rpc/src/yed/live.rs:51-86`).

### 4.2 Why v1 and v2 side by side (D-10)

- **No tag exists on any public chain yet.** YED goes live on the fast testnet with this release, and it is off on mainnet (`params.cpp:185-188`).
- **So v2 is valid from YED's start on every network.** It needs no activation height of its own.
- **Each payee has one encoding:** v1 for ECC payees, v2 for post-quantum payees.
- **ECC pools and the existing vectors are unchanged.**
- **"v2 only" was rejected:** it would make every tag 50 bytes and rewrite the tested path in the same release as the set id.

### 4.3 Specification

**Byte layout:** 49 bytes, little-endian, pushed as `0x31` + 49.

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | `"YED!"` (59 45 44 21) |
| 4 | 1 | version 0x02 |
| 5 | 1 | flags (bit 0 = signal, other bits zero) |
| 6 | 8 | priceMicroUsd (PRICE_MIN..PRICE_MAX) |
| 14 | 2 | sourceMask |
| 16 | 1 | payoutScheme: 0x01 SLH-DSA-SHA2-128s or 0x02 FN-DSA-512 (`crypto/pq/scheme.h:20`); any other value means no tag |
| 17 | 32 | payoutHash = SHA256(scheme ‖ pk), the `CPQKeyID` hash (`script.h:669-696`) |

**Parsing.**

- FindTag matches `24 59 45 44 21` or `31 59 45 44 21`, and the first match decides.
- A malformed v2 means no tag, and the block stays valid.

**Payee script.**

- The payee is a TX_PQPKH output: `0x20 <payoutHash> OP_<scheme> OP_CHECKPQSIG`, 35 bytes (`src/script/standard.cpp:67-75`).
- Both schemes are live on the testnets and on mainnet (`chainparams.cpp:160,479`).

**scriptSig budget.** The consensus range is 2 to 100 bytes (`main.cpp:1864-1865`), and the height push
is 4 bytes up to height 8,388,607.

| Producer | v1 used / free | v2 used / free |
|---|---|---|
| Template, `getblocktemplate`, `getcoinbasetemplatefor` (`<h> OP_0` + tag, `miner.cpp:296`) | 42 / 58 | 55 / 45 |
| Internal miner (`<h> <extranonce ≤ 6>`, `miner.cpp:817-818`) | ≤ 47 / ≥ 53 | ≤ 60 / ≥ 40 |
| kogany (5-byte marker when tight, `zakura-rpc .../get_block_template/ycash.rs:259-300`) | 46 | 59 |
| yolo (extranonce in the header nonce, `yolo/src/stratum.rs:27-33`; text truncated, `tx.rs:182-206`) | text ≤ 58 | text ≤ 44 |

**Consensus** (ycash-dd, ycash6 and kogany in one change set):

- `TagRecord` holds the payee as (kind u8, where 0 = P2PKH or the scheme byte; a 20- or 32-byte hash). **SCHEMA_VERSION goes from 15 to 16**, and the index is rebuilt (`view.h:89`).
- E(R), PIN-1 and the wallet-policy registry (`state.cpp:1575-1640`) are keyed by payee script.
- MINT-8, RED-3' and the vault fee records require the fee output to be exactly the payee's script, 25 or 35 bytes. The amount clauses are unchanged.
- The attestor fee (AFEE-1, `state.cpp:298-310`) stays P2PKH, because attestor keys are secp256k1.
- The four-part check for the PR body: DigiByte has no coinbase payee. The adaptation is a template match inside the module, with no opcode and no transaction field: the module rung.

**Fees are not coinbase outputs.**

- The fee is an output of the user's MINT, REDEEM or claim transaction (`state.cpp:423-430`, `txbuilder.cpp:172,237,304`).
- So the post-quantum coinbase rule (100-block maturity, then shielded at the exact amount; item 7) does not apply to fees.
- A post-quantum fee output is spendable after one confirmation, to any destination. Only a pool's post-quantum block reward carries the coinbase rule.
- **Spending cost:** an SLH-DSA input is about 8 kB (`policy.cpp:392-393`), so FN-DSA payouts are preferred.
- **Dust:** the post-quantum dust threshold (≈ 2,400 zat, `policy.cpp:390-406`) is far below the $1 minimum fee (`params.cpp:48`).

**Node options.**

- `-yellowbackpayoutaddress` and `-yellowbackpreferredpayee` accept:
  - P2PKH;
  - `tqf…` / `tqs…` on the testnets;
  - `sqf…` / `sqs…` on mainnet;
  - `rqf…` / `rqs…` on regtest.
- The `-mineraddress` default takes a post-quantum address too. A Sapling address still gives no tag (`policy.cpp:30`).
- The node emits v1 for a P2PKH payee and v2 for a post-quantum one.
- kogany: `set_payout_address` and `is_p2pkh_address` (`live.rs:51-86`) accept a post-quantum `mining.miner_address`, and a new `yed.payout_address` setting mirrors `-yellowbackpayoutaddress`.

**RPC contract: rpcversion 10 → 11.** The constant is `YELLOWBACK_RPC_VERSION` (`src/rpc/yellowback.cpp:62`) and kogany's `YED_RPC_VERSION`.

- `yed_gettag` gains `version` (1 or 2) and `payoutScheme` (`"p2pkh"`, `"fn-dsa-512"` or `"slh-dsa-sha2-128s"`).
- These fields may now hold a post-quantum address:
  - `yed_gettag.payoutAddress` (`:501`);
  - `yed_getinfo.miner.payoutAddress` (`:720`);
  - `yed_listminers[].payoutAddress` (`:1175`);
  - `yed_setquote` `next.payoutAddress` (`:1267`);
  - `yed_getfeepayee` `default` / `eligible` (`:1305`);
  - every `payee` field (`:417,1701,1762`; `yellowbackwallet.cpp:339,623,1126,1791`).
- The delta is recorded in `docs/plans/beta4/rpc-contract-delta.md`, and `make spec` regenerates the copies.

### 4.4 Tasks

| # | Repo | Change |
|---|---|---|
| D-T1 | ycash-dd → ycash6 → kogany (P1 change set) | v2 parse and encode, payee kind in `TagRecord`, payee-script E(R) / PIN-1 / registry, MINT-8 / RED-3' / fee records, SCHEMA_VERSION 16 |
| D-T2 | ycash-dd, ycash6 | `init.cpp` payout and preferred-payee options; the miner emits v2 for a post-quantum payee; RPC fields; rpcversion 11 |
| D-T3 | kogany | Post-quantum `mining.miner_address`, `yed.payout_address`, RPC fields, `YED_RPC_VERSION` 11 |
| D-T4 | ycash6, ycash-dd, kogany | Shared golden vectors (v1, v2, a bad scheme, v1/v2 ordering, the state hash after a v2 tag) |
| D-T5 | yolo | `src/tag.rs` decodes v2 and shows the post-quantum payout; PRICE_MAX corrected to 4,294,967,295 (`tag.rs:16`) |
| D-T6 | ycash6 + ycash-dd `contrib/yellowback` | `yellowback_price.py` `encode_tag` / `decode_tag` (`:860-891`) and `pool/check-coinbase` learn v2. `yellowback-quote` needs no change: the node builds the tag |
| D-T7 | yew | `p2pkh_of_address` (`core/src/build/mint.rs:2262`, used at `claim.rs:866`) becomes "script of address" for P2PKH and post-quantum addresses |
| D-T8 | lightwalletd-dd, yecwallet-dd, chain-viz | Contract fixtures and samples; post-quantum payee strings render. The ycash6 wallet builders need no change (`GetScriptForDestination`, `txbuilder.cpp:172`) |
| D-T9 | workspace | The rpcversion 11 contract delta; `make spec` |

### 4.5 Done when

| # | Criterion |
|---|---|
| D-1 | A regtest block mined with `-yellowbackpayoutaddress=rqf…` carries a 49-byte v2 tag. `yed_gettag` reports `version` 2, `payoutScheme` `"fn-dsa-512"` and `payoutAddress` `rqf…`. The same holds for `rqs…` with `"slh-dsa-sha2-128s"`, and on the fast testnet for `tqf…` |
| D-2 | The same tag appears in blocks built from `getcoinbasetemplatefor` (yolo) and by kogany, and the three lines agree on the tag record |
| D-3 | A MINT whose fee output pays the 35-byte script of an eligible v2 payee is accepted. A P2PKH fee output in its place is refused with `bad-mint-fee`. A claim REDEEM and an owner REDEEM behave the same, the latter refused with `vault-spend-bad-payee` |
| D-4 | With v1 and v2 tags in the payee window, `yed_getfeepayee` lists both kinds, and fees to either are accepted |
| D-5 | A post-quantum fee output is spent at one confirmation to a transparent address |
| D-6 | A coinbase at height 8,388,607 with a 6-byte extranonce and a v2 tag (60 bytes) is valid |
| D-7 | A v2 with scheme 0x03, or truncated, yields no tag and a valid block |
| D-8 | The golden vectors are byte-identical on ycash-dd, ycash6 and kogany, and cross-line state hashes match with v2 tags |
| D-9 | `rpcversion` is 11 on all three lines, and `make spec-check` passes |
| D-10 | yolo shows a v2 payout and a price above $100, and truncates `--text` to 44 bytes |
| D-11 | A YEW mint and a YEW claim pay a post-quantum payee |

## 5. Dependency order

| Phase | Contents | Depends on | Done when |
|---|---|---|---|
| P0 | Record the T-5 amendment in the testnet plan (9 house seats, 3 regions) | — | the testnet plan updated |
| P1 | The consensus change set, ycash-dd → ycash6 → kogany, two-reviewer gate: C-T1, D-T1..D-T4, C-T2 | P0 | C-2, C-3 (regtest part), C-4, C-8, D-1, D-3..D-9 |
| P1b | Clients for v2: D-T5..D-T9 | P1 contract | D-2, D-10, D-11 |
| P2 | Light attestor and cancel watcher: B-T1..B-T5 | P0 (P1 for D-T7 overlap in yew) | B-1..B-3, B-5..B-10 on regtest |
| P3 | Hosts: A-T1..A-T4, light (full-node fallback only if P2 is not done) | P0; P2 for light | A-1, A-6, A-7 |
| P4 | Wallet retry: A-T5 | P1 | A-3, A-4, A-5 |
| P5 | The ceremony and the release: C-T3..C-T7, beta4 tags, rollout in order (§3.3) | P1, P1b (the D-T8 client releases are a hard prerequisite, §3.3), P3, 3a | C-1, C-5, C-6, C-7, A-2, B-4 |
| P6 | Fast-testnet confirmation | P5 | C-3 (live), D-1 (`tqf…` live), A-2 held, and a wrong-price claim cancelled by light seats (B-8 live) |
