# beta4: a real price feed on the fast testnet (items 3c-3f)

**Revision 3 (2026-11-18): every decision is taken.** The Yellowback lead architect decided D-1..D-11 on 2026-11-18 (§6). Revision 2 recorded D-8 (the post-quantum payout key in beta4, §5) and the 3b cadence (§0.1). Revision 3 records the rest. It also brings the cancel watcher onto light seats in beta4 (D-7, changed from revision 1's recommendation, §3.3) and revises the effort and phases to match. This plan covers beta4 list
items 3c (highly available attestors), 3d (an attestor without a full node), 3e (the release part: the
attestor set on chain and its id compiled into ycash6, ycash-dd and kogany) and 3f (a post-quantum payout
key in the coinbase tag). Items 3a (pool quotes in the coinbase tag) and 3b (quote cadence) have their
own plan, written in parallel in this directory. Section 1 relies on it but does not repeat it.

Every citation is `repo/path:line` at `origin/upgrade/vault` (ycash6 `c6f009957`, ycash-dd `c07b8a734`,
kogany `36667efc9`, lightwalletd-dd `56660e5`, yew `6feaf99`), with ycash6 as the primary line. Where
ycash-dd is not mentioned, it matches ycash6. `src/yellowback/{params,state,bundle,module,tag,attest}.cpp`
and `src/vault/state.cpp` have identical blob ids on the two C++ lines, and so does
`contrib/yellowback/attest/`.

Fast-testnet scale: one block is about 75 s. 10 blocks are about 12.5 min, 20 blocks 25 min and 1,152
blocks 24 h.

## 0. Summary

| Item | Recommendation | Effort (agent-days) |
|---|---|---|
| 3c | **Decided (D-1..D-4): split, not round robin.** 9 house seats on 3 hosts (3+3+3), in 3 different regions, one key per seat and no key on two hosts, 20 YEC bond per seat (180 YEC). Losing one host costs nothing for about 12 minutes. After that a mint fails at about 1 block in 4, and the user retries at the next block. After about 24 h the dead seats go DORMANT and minting is fully back. Losing two hosts halts minting and claims, but not owner redemption. | 3-4 (ycash-infra, ycash-ops) |
| 3d | **Decided (D-6, D-7): the attest agent gets a lightwalletd backend, cancel watcher included.** It signs locally with its own guard file and sends statements over gossip and over a new `YellowbackStreamer.SubmitAttestation`. Heartbeats, joins, exits and the cancel transaction are built in YEW core, and lightwalletd adds `GetTxOut` and `GetMempoolTxids` for the watcher. A light host needs no node at all, only two lightwalletd endpoints. | 29-39 over lightwalletd-dd, ycash6/ycash-dd contrib, yew, ycash-infra |
| 3e | **Decided (D-5, D-9).** Run the ceremony on the live chain with `--seats 9 --bond 20` (the script accepts a chain past the fork), compile the id in on all three lines, then upgrade. The C++ nodes replay 510,400..tip in place. **kogany nodes must resync**, because otherwise they stop at the first block. The gap between `SET_CREATE` and the upgrade must be kept short and scanned for acts on the set. | 8-11 + ops |
| 3f | **Decided (D-8, D-10): tag v2 in beta4**, in the same consensus release as the set id. It adds a 49-byte tag (scheme + 32-byte post-quantum key hash) and keeps v1 for ECC payees; both are valid from YED's start, so no extra activation height is needed. Enforcement fees are paid to a 35-byte PQPKH. These fees are not coinbase outputs, so the shield-first rule does not apply to them. rpcversion becomes 11, and the change is made on ycash-dd, ycash6 and kogany together, plus yolo, YEW and the Python model (§5). | 16-21 |

### 0.1 Recorded: the 3b quote cadence (lead architect, 2026-11-18)

`yellowback-quote` fetches and calls `yed_setquote` **every 60-75 s**, with no heartbeat and no change
threshold. The lead architect chose accuracy over job churn: every call rebuilds the template
(`quoteGeneration`), so pools see about one extra job per 75 s block. The details are in the 3a/3b plan.

## 1. How attestation works today (from the code)

### 1.1 The statement

An attestor seat is a member of the vault primitive's attestor set, mirrored by the YED module as an
`AttestorRecord` with a `seq` (u16).

- **What is signed** (`ycash6/src/yellowback/attest.cpp:17,39-50`):
  - The message is SHA256(`"YBATTEST1"` ‖ seq LE16 ‖ priceMicroUsd LE32 ‖ citedHeight LE32 ‖ blockHash(citedHeight)).
  - The signature is secp256k1 compact r‖s, 64 bytes.
  - The whole attestation is **74 bytes**: seq 2, price 4, citedHeight 4, sig 64 (`attest.h:31-45`).
- **Who signs:** the node wallet does, through `yed_signattestation` (`src/rpc/yellowbackwallet.cpp:1546-1565`).
  - The agent holds no key (`contrib/yellowback/attest/src/main.rs:1-5`).
  - The wallet's equivocation guard `<datadir>/yellowback/attest-signed.dat` refuses a second, different price for the same (seq, citedHeight). It hands back the stored signature when the price is the same (`yellowbackwallet.cpp:1546-1549`).
- **Cadence** (agent policy, not consensus; `attest.toml.sample:30-33`):
  - The agent signs every `every_blocks` = **k = 10** blocks (`params.cpp:122` `attestInterval`).
  - It cites `tip − ref_lag` with `ref_lag` = 2.
  - It polls `yed_getinfo` every 15 s.

### 1.2 How statements reach a block

Statements are **not** relayed over node P2P, and the miner's template never reads them. `main.cpp`
`ProcessMessage` knows only the stock messages, and `miner.cpp` uses Yellowback only for the coinbase quote
tag and `FilterTemplate` (`src/miner.cpp:359-361,573`). kogany has no attestation P2P message either.
Instead:

1. **Transport between agents.**
   - The agent publishes every statement on an iroh-gossip topic, SHA-256(`yellowback/attest/<network>/3`), bootstrapped from configured peers. A shared-directory transport also exists (`contrib/yellowback/attest/README.md:71-87`).
   - Cancel co-signatures use their own topic.
2. **Intake into a node's pool.**
   - A `subscribe`-mode agent beside each node that builds YED transactions calls `yed_addattestation <hex>` (`attest/src/subscribe.rs:268`).
   - That RPC is the **only** way into the pool. It is RPC-auth only and never wallet-gated (`src/rpc/yellowback.cpp:2048-2072,2239`).
   - kogany has the same RPC with Admin access (`kogany/crates/kogany-rpc/src/yed/rpc.rs:163`, implementation at `:1277-1299`).
3. **Into the block.**
   - The **minter's own transaction** (MINT, CLAIM_NOTICE, or a claim's REDEEM) carries a *bundle*.
   - With `BUNDLE_CARRIER` = SCRIPTSIG (`params.cpp:81`), the bundle sits in the scriptSig of a P2SH carrier input whose redeem script commits to SHA256(bundle) (`bundle.cpp:153-163`, `bundle.h:32-33`).
   - The bundle is one 520-byte push, which is why **BUNDLE_MAX = 6** (`params.cpp:85`).
   - The wallet builds it from the local pool (`BuildBundleInfo`, `txbuilder.cpp:1188-1197`), or takes it from `bundleHex`.
   - Light wallets get it through `YellowbackStreamer.BuildBundle` → `yed_buildbundle` on the lightwalletd's node (`lightwalletd-dd/walletrpc/yellowback.proto:347`).

**Consequence for this plan:** statements do not need to reach pools or miners. They need to reach the
pool of **every node that builds YED transactions for users**. On the fast testnet that means the node
behind `fastnet-lightwallet.ycash.team` (YEW users) and any ycashd or yewd wallet that mints.

### 1.3 A valid bundle (BUNDLE-1) and an ARMED price

Selection (`state.cpp:2240-2254`):

- At reference height R (MINT-2: `H − REF_WINDOW ≤ R ≤ H − 1`, REF_WINDOW 40, `params.h:85-87`), the snapshot's **seated** list is the up-to **N_SLOTS = 9** ELIGIBLE seats of highest SeatRank (bond × age, plus a 5 % hysteresis for those already seated; `state.cpp:1780-1799,2082-2086`), minus pinned seqs.
- From the seated list, **M_SELECT + K_SLACK = 4 + 2 = 6** seats are drawn, weighted by bond × age, with seed SHA256(blockHash(R) ‖ selector ‖ "S" ‖ round) (`state.cpp:2205-2238`).
- The selector is empty for a MINT, so every mint at a given R draws the same 6. For a claim it is the vault outpoint, so each vault gets its own 6.

`VerifyBundle` (`bundle.cpp:178-236`) requires:

- **4 to 6 attestations** (`count < mSelect || count > bundleMax`, `:197`);
- every seq among the 6 drawn, with no seq twice (`:200-204`);
- **citedHeight in (R − 20, R]**: ATTEST_MAX_AGE 20 (`:209`, `params.cpp:88`);
- price in range, and every signature valid (`:206-230`).

So a bundle needs **at least 4 distinct live signers among the 6 drawn for that R**. The price it
yields:

- `BundleStat` gives the bond-weighted 33.33 % and 66.67 % quantiles (`qLowBps` 3,333 and `qHighBps` 6,667, `params.cpp:86-87`; `bundle.cpp:239-253`): aMint and aClaim.
- **When ARMED, pMint = min(xMint, aMint)** (`view.h:250`). MINT-10 refuses a mint where |pFast − aMint| > 15 % (`state.cpp:463`, `divergeBpsAttest` 1,500).

Attestors alone never make a price. xMint comes from the pools' coinbase quote tags (pFast, pMid and
pSlow, `state.cpp:1802-1815`). With no tags, HALT-1 (no price) applies (`:1847`). That is item 3a, so 3a
and 3c-3e must both ship for the fast testnet to mint.

### 1.4 Arming, maturity, liveness, dormancy

All of this happens in SNAP (`state.cpp:1671-1723,1855-1878`):

| Rule | Mainnet | Fast testnet | Code |
|---|---|---|---|
| **Maturity:** PENDING → ELIGIBLE at join + max(set maturity, BOND_MATURITY), with the bond at or above the module minimum | 16,128 | 48 (≈ 1 h) | `state.cpp:1687-1702`, `params.cpp:237` |
| **ARM-1:** UNARMED → TRIGGERED when ELIGIBLE count ≥ ATTEST_ARM_MIN | 7 | 7 | `state.cpp:1717-1721`, `params.cpp:78` |
| **ARM-2:** TRIGGERED → ARMED after ATTEST_ARM_DELAY | 1,152 | 20 (25 min) | `state.cpp:1722`, `params.cpp:79,234` |
| **ARMED never moves back** | | | comment at `state.cpp:1714` |
| **Unarmed mint refused** (MINT_REQUIRES_ARMED) | yes | yes | `state.cpp:384`, `params.cpp:124` |
| **Liveness:** ELIGIBLE → DORMANT when lastAct < H − set livenessWindow. lastAct moves on a heartbeat or on an attestation inside a mined bundle | set param, ≥ 1,152 | ceremony sets 1,152 (≥ 40 required) | `state.cpp:1690,1704-1710,2088-2131`, `params.cpp:115,242` |
| **S15 dormancy:** a seated seat drawn in ≥ DORMANCY_MIN_BUNDLES bundle rows within DORMANCY_BLOCKS without signing one → DORMANT | 20 in 16,128, checked every 48 | 20 in 48, checked every block | `state.cpp:1855-1877`, `params.cpp:118-120,245-246` |
| **Revival:** DORMANT → ELIGIBLE after a heartbeat (`set_heartbeat` or `yed_revive`) that follows the dormancy | | | `state.cpp:1707-1709` |

From the joins to the first mint on the fast testnet takes 48 + 20 = **68 blocks (about 85 min)**.

### 1.5 When signers are lost

- **ARMED and fewer than 4 of the 6 drawn have a fresh statement:**
  - A MINT at that R cannot carry a bundle. The wallet throws `bundle-insufficient` (`txbuilder.cpp:1189-1215`) and uses only R = tip − mintLag (`:625`), so the user retries at the next block, which draws a new 6.
  - Claims (CLAIM_NOTICE and the claim REDEEM) behave the same way, each with its own draw.
  - **Owner redemption reads no bundle** (RED-1 amended, `state.cpp:628`) and is never stopped by an attestor outage.
- **Fewer than 4 live seats seated:** no bundle can be built at any R. Minting and claims halt until signers return. The layer stays ARMED.
- **Not yet ARMED:** minting is refused outright (`mint-halted-unarmed`).

### 1.6 Slashing: what one key on two hosts does

- **EQV-1** (`state.cpp:1109-1139,2003-2043`):
  - Evidence is two attestations with the same seq and citedHeight and **different prices**, both valid under the member key (`:2015`). A regular attestation paired with a conflicting cancel statement (C4b) also counts.
  - Anyone can post it.
  - The member is EJECTED and its **bond is frozen** (`EjectRecord`, `:1099-1107`; the primitive's hook in `src/yellowback/module.cpp:98-112` and `src/vault/state.cpp:627-655`).
  - A frozen bond can never be spent (`src/vault/state.cpp:450`, `bad-vault-bond-frozen`), and the key is barred from seating for good (`state.cpp:1679-1689`).
- **The same price twice is not evidence** (`:2015`).
  - The agent's guard file does not protect two hosts that share a key, because each host has its own guard file.
  - Two hosts fetching prices independently will cite the same height with different prices (the tip is the same, the sources tick differently).
  - **So the code does not make double signing harmless.** A shared seat key is a slashing risk, and in a split brain it would be one for every shared seat at once.
- **No liveness slashing:** going offline only makes a seat DORMANT.
- **No member can slash another:** the module refuses any `SET_REMOVE` that is not the member's own exit, and any `SET_WINDDOWN` of the YED set (`state.cpp:2165-2183`). This holds even though the set's slashThreshold is 1 (`params.cpp:112-113`).

**kogany and ycash-dd.** kogany ports the same rules in `crates/kogany-yellowback/src/attest/` (attestation, bundle,
equivocation, seats, liveness), with the same parameters (`params.rs:278-298`). Its pool and bundle builder
are in `crates/kogany-rpc/src/yed/live_index.rs`. It has no wallet: `yed_signattestation` and the `set_*` writes
come from yewd (`yew/yewd/wallet/src/attest.rs:41-52`, `vaultrpc.rs:40-60`). ycash-dd has identical files.

## 2. Item 3c: attestors on several hosts

### 2.1 Layouts compared

The table gives the share of blocks at which a mint (or a given vault's claim) can be built right away.
It is P(at most 2 dead among the 6 drawn), with equal bonds and ages so equal weights, before any dead
seat has gone DORMANT. "Later" is after about 24 h (livenessWindow 1,152), when dead seats leave the
seated list.

| Layout | Seats | 1 host down | 2 hosts down | Later (1 host) | Key risk | Hosts |
|---|---|---|---|---|---|---|
| **A. split 3+3+3** | 9 (1 key each, on 1 host) | 76 % (1 − C(6,3)/C(9,6) = 1 − 20/84) | 0 %: halted until a host returns | 100 % (6 seated, all live) | none | 3 |
| B. split 7 (3+2+2), T-5 as written | 7 | 43 % if the 3-seat host is lost, 100 % if a 2-seat host is | 0 % | 100 % (4 seated) | none | 3 |
| C. one seat per host | 9 | 100 % | 100 % | 100 % | none | 9 |
| D. round robin: all 9 keys on 3 hosts, one active | 9 | 100 % after failover | 100 % after failover | n/a | **a split brain freezes up to 9 × 20 = 180 YEC and ejects every seat. The layer stays ARMED with no seats, so minting halts until new joins mature** | 3 |
| E. A + a key-less cold spare | 9 | as A, then 100 % once the spare takes over | as A | as A | none, if fencing is done | 3 + 1 cold |

- With 4 of 9 seats dead (for example A, plus one seat restarting elsewhere), 34/84 = 40 % of blocks still work. With 5 dead it is 12 %.
- At 76 % a user waits 1.3 blocks on average. Nothing is lost, but every fourth attempt shows `bundle-insufficient`. A wallet retry over the next block or two (§7, P4) hides it.
- Seats beyond 9 are standbys only. They are seated when a seated seat goes DORMANT, not before. A tenth to twelfth house seat would leave the immediate numbers unchanged and would use up the open seats meant for outside attestors (15 in all, `params.cpp:111`).

**Decided: layout A** (D-1, D-2), with E's spare as a runbook rather than a running machine. The details:

- **9 house seats instead of T-5's 7.** Seven seats are exactly ATTEST_ARM_MIN, and at 43 % the 3-seat host matters too much. 9 fills N_SLOTS, so outside joiners displace house seats only by out-ranking them (SeatRank, `EvictionVictim` `state.cpp:2133-2163`).
- **3 hosts in 3 regions,** or at least 3 availability zones (D-2).
- **One key per seat, each key on exactly one host,** with no hot standby holding a key.
- **Restore by fencing first:** destroy or stop the dead host before its keys are restored anywhere else.

### 2.2 Time to recover

| Event | Effect | Recovery |
|---|---|---|
| Agent or node restart under about 12 min | none: the last statement stays fresh for 20 blocks and the next is due 10 blocks after it | automatic |
| Host down 12 min to 24 h | its 3 seats are stale, and minting works at 76 % of blocks | restart: the seat signs at its next tick (≤ 10 blocks) |
| Host down over 24 h (livenessWindow 1,152) | its seats go DORMANT, and minting is back to 100 % on 6 seats | on return: `yed_revive` or `set_heartbeat` per seat, ELIGIBLE at that block's SNAP |
| Host lost | as above | light host: new VM, binary, 3 key files and the guard file (minutes). Full-node host: node restore from a snapshot (about 1 h) or sync (hours) |
| Key compromised | the bond is at risk only through EQV-1 (an attacker signing two prices) | `set_leave`, then withdraw after the exit delay. Join a new key (48 blocks to ELIGIBLE) |

Restore the guard file together with the keys. A seat restored without it can re-sign a citedHeight it
already signed, at a new price. That is equivocation.

### 2.3 Bond and cost

- **Bond: 20 YEC per seat is allowed.**
  - The module minimum is clamp(⌈5 % of YED collateral / 9⌉, floor, cap) (`math.h:378-386`, `state.cpp:2071-2075`), and on the fast testnet floor = 10 YEC and cap = 20 YEC (`params.cpp:250-251`).
  - A bond at or above the cap always meets the minimum (`state.cpp:1696`).
  - The primitive has no maximum bond, and a join must meet the set's own `bondmin` (`src/vault/state.cpp:825`).
- **The ceremony uses one `--bond` value for both the set's `bondmin` and each join** (`contrib/testnet/ceremony/ceremony:298-302,333`), so `--bond 20` makes 20 YEC the permanent floor for every outside joiner as well (D-3).
- **Total:** 9 × 20 = 180 YEC locked, plus fees.
- **Hosts** (estimates at AWS on-demand list prices, to be confirmed in ycash-ops):

  | Host type | Instance | Cost per host | Cost for 3 |
  |---|---|---|---|
  | Light host (agent only) | t4g.small, 8 GB disk | ≈ $13/month | ≈ $40/month |
  | Full-node host (ycashd wallet, or yewd + koganyd) | t4g.medium, 40 GB gp3 | ≈ $28/month | ≈ $85/month |

  The full-node figure is to be checked against the fast-testnet chain size.

## 3. Item 3d: an attestor without a full node

### 3.1 What the agent needs from a node today

These come from `contrib/yellowback/attest/src`, and the copy in ycash-dd is identical.

| RPC | Where | Purpose | Frequency |
|---|---|---|---|
| `yed_getinfo` | `attest.rs:183`, `cancel.rs:825` | network, tip height, `upgrade.attestorSetId` | every poll (15 s) |
| `yed_signattestation [seq, price, cited]` | `attest.rs:239-245` | **wallet:** signs with the seat key, behind the guard | every 10 blocks |
| `yed_listattestors` | `attest.rs:318`, `cancel.rs:861` | own seq, key, status | every poll |
| `set_getinfo` | `cancel.rs:870` | set state | every poll |
| `set_heartbeat [setId, memberKey]` | `attest.rs:340` | **wallet tx:** keeps the seat out of DORMANT | every 1,152 blocks |
| `getblockchaininfo` | `cancel.rs:1044` | sync check | every poll |
| `yed_listvaults CLAIMING`, `getblockhash`, `getrawtransaction`, `yed_decodepayload`, `yed_getattestations`, `gettxout`, `yed_getvault`, `getrawmempool` | `cancel.rs:905-2127` | the cancel watcher | every poll |
| `yed_signcancelcosign`, `yed_buildcancel`, `set_signcancel` | `cancel.rs:1025,2302,2362` | **wallet:** cancel a wrongful claim | on a claim |
| `sendrawtransaction` (to extra nodes) | `cancel.rs:2436-2452` | re-broadcast | on a cancel |
| `validateaddress`, `signmessage` | `cancel.rs:1849,1871` | **wallet:** bind the iroh endpoint to the member key | once, and at renewal |
| `getblock` (verbosity 2), `listunspent`, `yed_listunspent`, `createrawtransaction`, `signrawtransaction` | `cancel.rs:1924-2049` | on-chain fallback for cancel co-signatures | rare |

**Subscribe mode** calls `yed_listattestors` every 60 s, `yed_getinfo` on refresh, and
`yed_addattestation` for each frame (`subscribe.rs:109,131,268`).

**One-offs** are done by the operator, not the agent:

- `yed_registerattestor` or `set_join` to join (`src/rpc/yellowbackwallet.cpp:1297-1315`);
- `set_leave` to exit (`src/rpc/vault.cpp:3081`);
- `yed_withdrawbond` to take the bond back.

The bond is P2SH(lock CLTV DROP memberKey CHECKSIG) (`vault.cpp`, `set_join` help), so the seat key
also controls its bond.

**Today a seat needs a node wallet:** a ycashd wallet, or yewd + koganyd (yewd serves every one of these
names, `yew/yewd/wallet/src/attest.rs:41-52`). yewd's only backend is node JSON-RPC; lightwalletd is
"later" (`yew/yewd/README.md:7-8`, `yewd/facade/src/backend.rs:5-10`).

### 3.2 Design: the agent over lightwalletd-dd (recommended)

A light seat is the agent alone: a local secp256k1 key, a local guard file, and two or more
lightwalletd endpoints.

| Need | Light source | Status |
|---|---|---|
| Tip height and hash | `CompactTxStreamer.GetLatestBlock` | exists |
| Hash at citedHeight | `CompactTxStreamer.GetBlock(height)` | exists |
| Own seq, key, status; set info; network | `YellowbackStreamer.ListAttestors`, `GetSet`, `GetYellowbackInfo` (`yellowback.proto:347-354`) | exist |
| Signing | in the agent: the message of §1.1 and a compact low-S signature. YEW core already has `attest_message` and verification (`yew/core/src/bundle.rs:73-194`) | **new**: a signer and guard in the agent, porting the `attest-signed.dat` semantics (yewd's signer has the same logic in `yewd/signer/src/attest.rs:5-26`) |
| Statement delivery | (a) iroh gossip, unchanged; (b) **new `YellowbackStreamer.SubmitAttestation(bytes 74)` → `yed_addattestation`** on the lightwalletd's node, which is the node whose pool YEW's `BuildBundle` reads | **new** in lightwalletd-dd |
| Heartbeat, join, exit, withdraw | build the `SET_HEARTBEAT`, `SET_JOIN` and `SET_REMOVE` (self) acts and the bond spend in YEW core, funded from a transparent UTXO (`GetAddressUtxos`), sent with `SendTransaction` | **new** in yew core. The act codec exists in `yew/yewd/proto/src/act.rs:20,167-222`; core has no set-act builder |
| Cancel watcher | §3.3 | **in beta4** (D-7) |

**New lightwalletd-dd calls.** These need no node change: every one is an allow-listed proxy, like the
existing ones (`common/yellowback.go:8-11,70-111`).

- **`SubmitAttestation(YedAttestationBytes) → YedSubmitResult`**, which calls `yed_addattestation`.
  - Today this is deliberately **not** reachable (`common/yellowback.go:8-11`), so the change is a policy decision (D-6).
  - Guard: exactly 74 bytes; the seq must be an ELIGIBLE or PENDING member (checked against a cached `yed_listattestors`); a per-seq rate of 1 frame per 5 blocks; a per-IP rate limit.
  - The node already validates against the tip and the key. The worst abuse is a valid statement re-posted, which is idempotent.
- **`GetTag(HeightFilter) → YedTag`** wraps `yed_gettag` (ycash6 `src/rpc/yellowback.cpp:2223`; kogany `rpc.rs:97`). It gives the tip's quote tag, so light monitors can watch 3a's pool quotes. It is optional and shared with 3a.

Both lines serve these: `yed_addattestation` and `yed_gettag` exist on ycash6, ycash-dd and kogany.

**Trust.** A lying lightwalletd can only make the agent cite a wrong hash or height. The resulting
statement is invalid (BUNDLE-1 `sig` or `stale`) and **cannot be equivocation**, because EQV-1 verifies
both statements under the real block hash at citedHeight (`state.cpp:2033`). So lightwalletd affects
liveness, not the bond. Two endpoints in different regions cover that. Today there is one fast-testnet
lightwalletd, so a second is part of this item (ycash-infra).

### 3.3 The cancel watcher on light seats (D-7, in beta4)

**What it does today** (`contrib/yellowback/attest/src/cancel.rs:5-29`). It runs once per poll, in three parts:

- **Watcher.** It reads every confirmed YED claim and judges it at the claim's refHeight with the seat's own recorded price. A *wrong-price* claim (the vault was not claimable at that price with `margin_bps` to spare) is co-signed and published.
- **Gossip.** It takes in other members' 115-byte co-signature frames, checked and rate-limited per peer and per seq.
- **Collector.** One member drives each claim, chosen by a rota of members in seq order rotated by the intent hash. The driver waits for `cancelsRequired` co-signatures plus spares, then:
  - builds the cancel (`yed_buildcancel`);
  - adds the set signature (`set_signcancel`);
  - broadcasts the carrier and the cancel, re-pushing or rebuilding as needed.

The cancel must confirm within CLAIM_DELAY, which is 20 blocks (about 25 min) on the fast testnet
(`params.cpp:229`). A first cancel needs 1 co-signature, and each further cancel within CANCEL_QUIET needs
one more, up to 4 (`yellowbackwallet.cpp:2253-2256`, `params.cpp:116,243`). With 3 seats per host, a
fourth cancel always needs a second host.

**What the watcher reads, and where a light seat gets it.**

| Read (today's RPC, `cancel.rs` line) | Light source |
|---|---|
| Claims in CLAIMING: intent outpoint, refHeight, claim height, burn, `cancelsRequired`, `refundHolder` (`yed_listvaults CLAIMING` :905, `yed_getvault` :1257) | `YellowbackStreamer.ListVaults(status "CLAIMING")` and `GetVault` (exist; `yellowback.proto:25,170`) |
| The claim transaction and its payload (`getrawtransaction` :955, `yed_decodepayload` :961) | `CompactTxStreamer.GetTransaction` (raw) and `YellowbackStreamer.DecodePayload` (exist) |
| Block hash at a height and reorg detection (`getblockhash` :937) | `GetBlock` and `GetLatestBlock` (exist) |
| The seat's signed prices on record (`yed_getattestations` :1010) | `GetAttestations` (exists), plus the agent's own guard file |
| Set and member state (`set_getinfo` :870, `yed_listattestors` :861) | `GetSet` and `ListAttestors` (exist) |
| Whether an outpoint is spent, with mempool (the intent, the carrier, a lingering cancel, the fee inputs) (`gettxout` :1248, :2127) | **new `GetTxOut(outpoint, includeMempool)` → `gettxout`** |
| Claims and cancels still in the mempool (`getrawmempool` :2113) | **new `GetMempoolTxids` → `getrawmempool`**. `GetMempoolTx` gives compact transactions without the inputs the check needs |
| Index sync (`getblockchaininfo` :1044) | `GetChainInfo` and `GetLatestBlock` (exist) |

**How co-signatures and the cancel are submitted.**

- **Co-signatures are not for nodes.** No node keeps a pool of them, and `yed_buildcancel` takes them as arguments. They go to the claim's driver by:
  - the cancel gossip topic and the members' direct iroh endpoint (both unchanged: `gossip.rs`, `direct.rs`);
  - the on-chain fallback, an OP_RETURN "YF" transaction (`onchain.rs:1-19`), built by the light agent from its own transparent coin and sent with `SendTransaction`.
- **Signing is local.** The co-signature is a recoverable secp256k1 signature over `CancelCosignMessage(setId, intent, n, citedHeight, price, blockHash)` (`src/yellowback/state.cpp:2041`). The guard file records it, because a co-signature at a price that conflicts with an attestation is equivocation (C4b, `state.cpp:2018-2022`). The iroh endpoint binding (today `signmessage`, `cancel.rs:1871`) is signed locally too.
- **The driver builds the cancel in YEW core.** This ports `yed_buildcancel`, the `set_signcancel` signature and the carrier (`yellowbackwallet.cpp:2243-2265`):
  - the claimed vault is re-created at vout 0, and the claim's burn is refunded at vout 1 to `refundHolder`;
  - the carrier holding the co-signatures (CARRIER_VALUE) is spent as the last input, with the CANCEL_COSIGN marker as the last output;
  - the member key signs SIGHASH_ALL|ANYONECANPAY under the Vault branch ID;
  - fees come from the seat's own coins.

  YEW core already builds claims and carriers (`yew/core/src/build/claim.rs`) and signs vault spends, so this is reuse.
- **Before sending,** the driver checks the cancel with `ValidateRawTransaction` (exists). It then sends the carrier and the cancel with `SendTransaction` through both lightwalletd endpoints, in place of `broadcast_rpc`.
- **No other lightwalletd write is added.** A mailbox for co-signatures was considered and rejected: it would put state in lightwalletd, and the light agent already runs iroh.

**Trust.** As in §3.2, a lying lightwalletd can hide a claim (liveness) or show a fake one. A fake claim
produces a co-signature for a claim that does not exist, which no consensus rule counts. Two endpoints,
and cross-checking a claim on both before co-signing, cover the hiding case.

### 3.4 Alternatives

| Option | Node per seat host | New code | Weak point |
|---|---|---|---|
| **Agent over lightwalletd** (§3.2, §3.3; decided D-6) | none | lightwalletd 4 calls; agent backend, signer, cancel watcher; YEW-core set acts and cancel builder | lightwalletd availability (two endpoints) |
| yewd with a lightwalletd backend | none | yewd backend abstraction over gRPC (wallet RPCs over a light source, the larger change: yewd's whole wallet assumes node RPC); agent unchanged | larger change; yewd becomes a light wallet |
| One shared full node per region, agents on light hosts calling it | 1 per region | none | `yed_signattestation` needs the seat key in **that node's wallet**, so the region node is the seat holder. That is layout A with full nodes, and the agent hosts add nothing |
| Today's full node per host (ycashd wallet, or yewd + koganyd) | 1 per host | none | cost (§2.3), sync and restore time |

**Decided (D-6):** the agent over lightwalletd. The house seats start on full-node hosts only if the light
agent has not passed its regtest acceptance by the ceremony. They move to light hosts when it passes (P5).

### 3.5 Effort

| Repo | Work | Days |
|---|---|---|
| lightwalletd-dd | `SubmitAttestation`, `GetTag`, `GetTxOut`, `GetMempoolTxids`: guards and tests against ycash6 and kogany | 3-4 |
| ycash6 (+ ycash-dd copy) `contrib/yellowback/attest` | `[backend] lightwalletd` (tonic client), local signer, guard, key file, heartbeat through YEW core | 6-8 |
| same | cancel watcher over lightwalletd: the reads of §3.3, local co-signature and binding signing, the on-chain fallback, the driver calling YEW core, sending through both endpoints | 5-7 |
| yew | core set-act builders (join, heartbeat, self-remove, bond withdraw) and a small `yew-attestor` CLI | 4-6 |
| yew | core cancel builder: the `yed_buildcancel` port, the co-signature carrier, the set signature | 5-7 |
| kogany | none in code; confirm lightwalletd-dd over koganyd serves the two new calls | 1 |
| ycash-infra / ycash-ops | 3 seat hosts, second lightwalletd, secrets, monitoring, "house-operated" label on the status page | 3-4 |
| tests | regtest: 3 light seats + 6 full seats arm, mint, and lose one host; key-restore with the guard | 2 |
| tests | regtest: a wrong-price claim cancelled by light seats only (1st to 4th cancel, co-signers on two hosts), the on-chain fallback, a lightwalletd hiding a claim | 2-3 |
| **Total** | | **29-39** |

## 4. Item 3e: release part

### 4.1 Facts

- **Heights.**
  - The fork (UPGRADE_YCASH) is at 510,248 (`ycash6/src/chainparams.cpp:449`).
  - Vault (H_V) is at 510,400 (`ycash6/src/chainparams.cpp:663`, `ycash-dd/src/chainparams.cpp:602`).
  - YED's startHeight is not stored. It becomes the Vault height when an id is set (`src/yellowback/index.cpp:1153-1166`; kogany `crates/zakura-state/src/service/finalized_state/zakura_db/yed.rs:192-211`).
  - So after the release **YED starts at 510,400, before the set existed**. `issuedBeforeStart` = CirculatingSupplyAt(510,399).
- **No network carries an id today.**
  - Only RegtestParams sets one (`params.cpp:349`). `-yellowbackattestorset` is regtest-only (`src/init.cpp:455`, `index.cpp:1147`).
  - The release needs a code slot in `TestFastParams` (or in `ParamsFromArgs` for the fast profile) on all three lines.
  - It also needs test updates: ycash6 `testnet_params_tests.cpp:322`; kogany `tests/params_tables.rs:463`, `tests/params_cpp.rs`.
- **Adoption** (`params.cpp:111-115,237,242`; `state.cpp:1176-1193`) requires the set's shape:
  - open, 15 seats, cancel threshold 1, unlock threshold 1, rate limit 0;
  - maturity exactly 48;
  - livenessWindow ≥ 40.

  The ceremony's `set_params` meets all of these (`ceremony:298-302`).

### 4.2 The two open questions

**Q1: Does the ceremony script accept a chain past the fork? Yes.**

- `check` needs:
  - the profile;
  - `blocks ≥ 510,247` and the prefix hash;
  - `vault_getinfo` not governing another set (beta3 governs none);
  - Vault > fork;
  - a peer, and no IBD when mining (`ceremony:251-280`).
- `fork` and `vault` call `mine_to`, which returns at once when the tip is already past (`:192-210`, `:195`). `fork` only re-reads block 510,248 and checks its parent (`:284-292`).
- Nothing requires `SET_CREATE` near H_V. The plan's "at H_V+ε" (testnet plan, ceremony section) is not enforced.
- `record` sums tx counts over every block from 510,248 to the tip (`:366-368`). That is slow on a long chain but correct.
- Use `--no-mine` on the live network.

**Q2: Do upgraded nodes replay 510,400..tip cleanly with earlier joins?**

| Line | Answer |
|---|---|
| **ycash6, ycash-dd: yes, in place.** | The primitive's set state is generic and indexed from Vault whatever the params say (`src/vault/node.cpp:366-411`). The YED index has no tip yet, so `SyncToChain` applies 510,400..tip (`index.cpp:309-341`) and adopts the `SET_CREATE` whose txid equals the id (`state.cpp:1176-1193`, `module.cpp:42-52`). `ApplyBlock` never fails (`state.cpp:1964-1972`). No `-reindex` is needed (`index.cpp:240-268`), but the blocks from 510,400 must be on disk (`doc/yellowback.md:148`); a pruned node needs a resync. |
| **kogany: no, it stops.** | It has no in-place YED rebuild (`zakura_db/yed.rs:24-29`). A database past 510,400 with no YED tip fails `check_base` with `TipMismatch` at the first new block (`yed.rs:439-448`), and `prepare_yed_batch` stops the node (`yed.rs:772-789`). The format migration that would ask for a resync runs only on the upgrade to 30.2.0 (`disk_format/upgrade/add_yed_state.rs:26-28,69-78`), which beta3 databases have probably passed. **Every fast-testnet kogany node must resync, or restore a snapshot made by a node of the new release.** Better still, add a startup check that reports "resync required" instead of stopping at the next block (1-2 days). |

**The gap risk (both C++ lines).** Already-connected blocks are not re-validated by in-place nodes, but
nodes that sync fresh judge them with the module live. Inside the primitive, the module refuses:

- a `SET_WINDDOWN` of the set, or a `SET_REMOVE` of another member (`state.cpp:2165-2183`);
- a `SET_JOIN` below BondMinZat (`state.cpp:1148-1160`).

It also decides displacement into a full set (`module.cpp:116-168`). If such an act lands between
`SET_CREATE` and the upgrade, in-place nodes keep that block and fresh nodes reject it: **a chain split.**

- With `--bond 20` as the set's `bondmin`, a low join is already refused by the primitive.
- An outsider can still join in the gap and post a `SET_REMOVE` of a house seat (slashThreshold 1).
- Mitigation:
  - keep the gap to hours (build the release before the ceremony and leave only the id to fill in);
  - scan every gap block for acts naming the set before tagging;
  - if anything is found, rerun the ceremony with a new set.
- A no-gap alternative is to pre-sign `SET_CREATE`, compile its txid, release, then broadcast. But `set_create` always broadcasts (`src/rpc/vault.cpp:1565,1581`), so this needs new ceremony code, and it carries a txid-malleability risk before mining. **Not recommended.**

**Rollout order.** Upgraded nodes enforce the YED rules (they reject YED transactions without a valid
bundle or price). Old beta3 nodes accept anything that passes the primitive. Upgrade the pool's node and
the miners first, then the seeds and lightwalletd, then announce.

### 4.3 Ceremony steps for the fast testnet

1. Freeze the release branch on all three lines with an empty id slot. Two-reviewer gate, with the four-part check in the PR body.
2. Fund the ceremony wallet (ycashd beta3, fast testnet) with ≥ 9 × (20 + `FEE_MARGIN`) YEC.
3. Run `contrib/testnet/ceremony/ceremony --network testnet-yb-fast --no-mine --seats 9 --bond 20 --secrets <dir outside git> --steps set,seats`, and wait 6 confirmations each.
4. Split the 9 seat key files into 3 sets of 3. Move each set to its host and import it there (`importprivkey` on that host's wallet or yewd, or the light agent's key file). **Delete them from the ceremony host.**
5. Fill the id (`record.release.attestorSetId`) into ycash6, ycash-dd and kogany. Scan the gap blocks for set acts. Tag `beta4`.
6. Upgrade the pool node and miners, then seeds, lightwalletd and the explorer. Resync or restore every kogany node.
7. Start the 3 seat hosts and the subscribe agent beside the lightwalletd node. `--steps mature,record` runs until all 9 seats are ELIGIBLE (48 blocks), then ARMED (+20).
8. Bring up the 3a pool quotes, check `yed_getinfo` (ARMED, pMint defined), mint once from YEW, and label the feed house-operated on the status page.

### 4.4 What needs a test

| # | Test | Lines |
|---|---|---|
| T1 | Ceremony against a regtest chain well past H_V (`--seats 9 --bond 20`, all steps, `--no-mine` against a mining peer) | ycash6 (`contrib/testnet/ceremony/test_ceremony.py`, `qa/rpc-tests/testnet_ceremony.py`) |
| T2 | Inert from H_V for many blocks, set created and joined late, restarted with the id. Must equal a fresh sync on `yed_getstatehash`, the vault state hash and `yed_listattestors`. The closest existing test is `qa/rpc-tests/yellowback_upgrade.py:9-13`, which has an empty pre-set gap | ycash6, ycash-dd |
| T3 | The same for kogany: shows the stop (or the new startup check) and a resync that matches | kogany |
| T4 | A gap block holding a `SET_REMOVE` of another member, a `SET_WINDDOWN`, or a below-minimum join: the in-place and fresh-sync verdicts (proves the scan is needed) | ycash6, kogany |
| T5 | Parameter tables with the compiled id | all three |
| T6 | Regtest 3 × 3 hosts: one host killed, mint success per block around 76 %, DORMANT after the liveness window, revive. Two hosts killed: halt; owner redemption still works | ycash6 |

## 5. Item 3f: a post-quantum payout key in the tag (decided: beta4)

**Decided by the lead architect on 2026-11-18 (D-8):** the tag v2 ships in beta4, in the same consensus
release as the attestor set id (3e). There is no later consensus change for it.

### 5.1 Today: v1 and its 20-byte key

- **The tag** (`src/yellowback/tag.h:17-21`, `tag.cpp:38-55`) is 36 bytes: `"YED!"`, version 0x01, flags, priceMicroUsd u64, sourceMask u16, **payoutKey Hash160 (20)**. It is pushed as `0x24` + 36, so it takes 37 bytes of scriptSig.
- **FindTag** (`tag.cpp:57-80`) requires the BIP34 height push first, then scans for `24 59 45 44 21`.
  - The first match decides (TAG-5).
  - An unknown version means "no tag", and the block stays valid (TAG-4, `tag.h:29-30`).
- **Consensus pays enforcement fees to P2PKH(payoutKey):**
  - E(R) is the deduplicated payoutKeys of the quote tags in the payee window, minus pinned keys (`state.cpp:1554-1573`).
  - MINT-8 (`state.cpp:423-430`) and RED-3' (`:644-657`) accept only a 25-byte P2PKH fee output (`P2PKHKey`, `:88-94`).
  - PIN-1 pins by `uint160` (`:1740-1748`). `TagRecord.payoutKey` is `uint160` (`view.h:185-200`), and so are the vault fee records (`state.cpp:493,776`).
- **The payout address must be P2PKH.** `-yellowbackpayoutaddress` and `-yellowbackpreferredpayee` are refused unless P2PKH (`src/init.cpp:1648-1655`). The default is `-mineraddress`, used only if it is P2PKH (`:2467-2472`).
- **kogany** has the same rules: `crates/kogany-yellowback/src/codecs/tag.rs:22-111`, E(R) at `lookups.rs:79-97`, `state/mint.rs:238-246`, `state/redeem.rs:187-201`. Its payout key comes from `mining.miner_address`, P2PKH only (`kogany-rpc/src/yed/live.rs:51-86`).

### 5.2 v1 alongside v2, or v2 replacing v1: **both accepted from YED start**

YED goes live with this release on the fast testnet. Its start height is the Vault height, applied
retroactively (§4.1). It is not live on mainnet (`params.cpp:185-188`). No tag of either version exists
on any public chain yet, so the choice costs no transition either way, and **neither option needs its own
activation height**. v2 is valid from YED's start on every network.

| | **Keep v1 and add v2 (recommended)** | v2 only, carrying both kinds of key |
|---|---|---|
| ECC pools (yolo with a transparent payout, existing tooling) | unchanged, 37 bytes of scriptSig | must move to a v2 encoding; 50 bytes for everyone |
| New consensus | one more parse path; payee becomes "P2PKH or PQPKH" | a new parse with variable-length keys; every regtest and golden vector changes |
| One payee, one encoding | yes: v1 is ECC only, v2 is post-quantum only (scheme 1 or 2, any other value means no tag) | yes |
| Risk | lowest: v1 code, vectors and harness keep working | rewrites the tested path in the same release as the set id |

### 5.3 The v2 specification

**Byte layout** (49 bytes, little-endian, pushed as `0x31` + 49 = 50 bytes):

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | magic `"YED!"` (59 45 44 21) |
| 4 | 1 | version **0x02** |
| 5 | 1 | flags (bit 0 signal; bits 1-7 zero) |
| 6 | 8 | priceMicroUsd u64 (PRICE_MIN..PRICE_MAX, as v1) |
| 14 | 2 | sourceMask u16 |
| 16 | 1 | **payoutScheme**: 0x01 SLH-DSA-SHA2-128s or 0x02 FN-DSA-512 (`crypto/pq/scheme.h:20`). Anything else means no tag |
| 17 | 32 | **payoutHash** = SHA256(scheme ‖ pk), the `CPQKeyID` hash (`script.h:669-696`) |

**FindTag** scans for either pattern, `24 59 45 44 21` (v1) or `31 59 45 44 21` (v2), after the height
push. The first match of either decides, as TAG-5 does today. A v2 with a bad scheme, short data or a
failed IsValidTag means no tag, and the block stays valid (TAG-4 unchanged).

**The payee script** of a v2 tag is TX_PQPKH: `0x20 <payoutHash> OP_<scheme> OP_CHECKPQSIG`, 35 bytes
(`src/script/standard.cpp:67-75`). Both schemes are live on the testnets and mainnet
(`pqFalconHeight` 0, `chainparams.cpp:160,479`).

**scriptSig budget** (consensus: 2 to 100 bytes, `main.cpp:1864-1865`). The height push is 4 bytes
for heights up to 8,388,607. A block carries one tag.

| Producer | v1 (used / free) | v2 (used / free) |
|---|---|---|
| Template, `getblocktemplate`, `getcoinbasetemplatefor` (`<h> OP_0` + tag, `miner.cpp:296`) | 42 / 58 | 55 / 45 |
| Internal miner (`<h> <extranonce, ≤ 6 bytes>`, `miner.cpp:817-818`, which asserts ≤ 100) | ≤ 47 / ≥ 53 | ≤ 60 / ≥ 40 |
| kogany (5-byte marker when tight, `zakura-rpc .../get_block_template/ycash.rs:259-300`) | 46 | 59 |
| yolo: `<h>` ‖ tag ‖ push(text), with the extranonce in the header nonce (`yolo/src/stratum.rs:27-33`, `tx.rs:182-206`) | text ≤ 58 | text ≤ 44 |

**The consensus change** is made on the three lines together (ycash-dd, ycash6 and kogany in one change
set, with the two-reviewer gate):

- `TagRecord` carries the payee as (kind u8: 0 for P2PKH, or the scheme; hash 20 or 32). This changes the state hash, so **SCHEMA_VERSION 15 → 16** and the index is rebuilt (`view.h:89`).
- E(R), PIN-1 (`pinnedKeys`) and the wallet-policy registry (`Registered`, `Penalized`, `AccuracyBps` and `DefaultPayee`, `state.cpp:1575-1640`) are keyed by the payee script instead of `CKeyID`.
- MINT-8, RED-3' and the vault fee records (`state.cpp:423-430,644-657,493,776`) match the fee output's exact scriptPubKey: either the 25-byte P2PKH or the 35-byte PQPKH of an eligible payee. The amount clauses are unchanged.
- The attestor fee (AFEE-1, `state.cpp:298-310`) stays P2PKH, because attestor keys are secp256k1.
- kogany mirrors each of these: `codecs/tag.rs`, `view`, `lookups.rs:79-97,134`, `state/mint.rs`, `state/redeem.rs`, plus new golden vectors shared with the C++ lines.
- Four-part check, for the PR body: DigiByte has no coinbase payee. The Ycash adaptation is a template-level payee match inside the module, with no opcode and no new transaction field. That is the module rung, the cheapest one that can carry a post-quantum payee.

**Fee outputs are not coinbase outputs.**

- An enforcement fee is an output of the user's MINT, REDEEM or claim transaction (`state.cpp:423-430`, `txbuilder.cpp:172,237,304`).
- So the post-quantum coinbase rule (100-block maturity, then shielded at the exact amount; beta4 item 7) **does not apply** to the fees. A post-quantum fee output is spendable after one confirmation, to any destination.
- Only the pool's **block reward**, if paid to a post-quantum address, has that rule. That is item 7's subject and unchanged here. A pool should still pay its block rewards to a ycashd or yewd wallet.
- Spend cost: an SLH-DSA input is about 8 kB of scriptSig (`policy.cpp:392-393`), and a Falcon input is under 2 kB, so pools should prefer FN-DSA payout addresses.
- The post-quantum dust threshold is about 3 × 100 zat/kB × 8 kB ≈ 2,400 zat (`policy.cpp:390-406`, `policy.h:116`). The smallest fee is $1 (`params.cpp:48`), so dust is never an issue.

**Node options and policy (both C++ lines):**

- `-yellowbackpayoutaddress` and `-yellowbackpreferredpayee` accept P2PKH or a post-quantum address: `tqf…` / `tqs…` on the testnets, `sqf…` / `sqs…` on mainnet, `rqf…` / `rqs…` on regtest (`init.cpp:1648-1655`).
- The default from `-mineraddress` now takes a post-quantum mining address too (`:2467-2472`). A Sapling `-mineraddress` still gives no tag (`policy.cpp:30`).
- The miner emits v1 for a P2PKH payee and v2 for a post-quantum one.

**kogany:** `set_payout_address` and `is_p2pkh_address` (`live.rs:51-86`) accept a post-quantum `mining.miner_address`. A separate `yed.payout_address` setting is added, matching `-yellowbackpayoutaddress`.

**RPC contract: rpcversion 10 → 11** (`YELLOWBACK_RPC_VERSION`, ycash6 `src/rpc/yellowback.cpp:62`; kogany `YED_RPC_VERSION`, `crates/kogany-rpc/src/yed/mod.rs`):

- `yed_gettag` gains `version` (1 or 2) and `payoutScheme` (`"p2pkh"`, `"fn-dsa-512"` or `"slh-dsa-sha2-128s"`), and its `payoutAddress` may be a post-quantum address (`yellowback.cpp:501`).
- The same "may be post-quantum" rule applies to:
  - `yed_getinfo.miner.payoutAddress` (`:720`);
  - `yed_listminers[].payoutAddress` (`:1175`);
  - `yed_setquote`'s `next.payoutAddress` (`:1267`);
  - `yed_getfeepayee`'s `default` and `eligible` (`:1305`);
  - every `payee` field of the TxLog, history and tx-info readers and of the wallet build results (`:417,1701,1762`; `yellowbackwallet.cpp:339,623,1126,1791`).
- The text of `yed_setquote`'s `no-payout-address` refusal changes.
- `make spec` updates the contract copies, and a `docs/plans/beta4/rpc-contract-delta.md` records the delta.

**Clients:**

| Client | Change |
|---|---|
| YEW core | `p2pkh_of_address` (`yew/core/src/build/mint.rs:2262`, used for the fee payee at `claim.rs:866` and in mint and redeem) becomes "script of address" for P2PKH and post-quantum. `fee_payee` (`mint.rs:377`) is unchanged |
| ycash6 / ycash-dd wallet builders | none: they already build `GetScriptForDestination(payee)` (`txbuilder.cpp:172,237,304`). Only the payee type widens |
| yolo | `src/tag.rs` decodes v2 (pattern, 49-byte body, scheme, hash) and shows the post-quantum payout. Its PRICE_MAX is fixed to 4,294,967,295 (it says 100,000,000 at `tag.rs:16`, a log-only defect). The `--text` room falls to 44 bytes |
| `yellowback-quote` and `yellowback_price.py` | the quote agent calls only `yed_setquote`, so the node builds the tag and the agent is unaffected. The Python model's `encode_tag` and `decode_tag` (`contrib/yellowback/yellowback_price.py:860-891`, which assert 20 bytes) and `pool/check-coinbase` learn v2 |
| lightwalletd-dd | none in code: payee strings pass through (`YedPayee`, `walletrpc/yellowback.proto:238-241`). Contract samples and tests are updated |
| YecWallet, chain-viz | display and revenue ledger are keyed by address strings (`yecwallet-dd/src/yellowbacktab.cpp`; `chain-viz/src/model/revenue.rs`). Check that post-quantum strings render, and update the contract fixtures |

**Tests:**

| # | Test | Lines |
|---|---|---|
| V1 | Golden vectors for v1 and v2: encode, FindTag (v1 first, v2 first, a bad scheme), the state hash after a v2 tag | ycash-dd, ycash6, kogany (shared vectors) |
| V2 | Regtest: a pool with an `rqf…` payout. MINT, owner REDEEM and claim REDEEM each pay the 35-byte payee. A P2PKH fee output to that payee is refused (`bad-mint-fee`, `vault-spend-bad-payee`). Then a mixed E(R) of v1 and v2 payees | ycash6, ycash-dd |
| V3 | The scriptSig budget at height 8,388,607 with a 6-byte extranonce and a v2 tag (60 bytes); `getcoinbasetemplatefor` with a v2 tag; kogany's marker path | ycash6, kogany |
| V4 | The fee output spent at one confirmation to a transparent destination: no coinbase rule applies | ycash6 |
| V5 | Cross-line state-hash parity with v2 tags (the mixed kogany harness) | all three |
| V6 | yolo: a v2 tag decoded from a live template; text truncation at 44 bytes | yolo |
| V7 | YEW: a mint and a claim against a post-quantum payee | yew |

**Effort (agent-days):**

| Area | Days |
|---|---|
| ycash-dd consensus, RPC and init | 4-5 |
| ycash6 port (identical files) | 1-2 |
| kogany | 3-4 |
| Contract, rpcversion 11, `make spec` | 1 |
| yolo | 1 |
| Python model and check-coinbase | 1 |
| YEW core | 1 |
| lightwalletd-dd, YecWallet and chain-viz fixtures | 1 |
| Tests V1-V7 | 3-4 |
| **Total** | **16-21**, plus the two-reviewer gate |

### 5.4 Release ordering

v2 is on the beta4 critical path. It lands in P1 with the id slot, in the same consensus PRs on the three
lines. The ceremony (P3) runs only once those PRs are approved and the release branch is frozen, so the
gap between `SET_CREATE` and the upgrade stays short (§4.2).

Because YED starts retroactively at 510,400, the gap scan covers **every coinbase from 510,400** for
either tag pattern, as well as set acts. A stray `YED!` push in that range would become a tag record.

## 6. Decisions (all taken by the lead architect, 2026-11-18)

| # | Decision | Decided |
|---|---|---|
| D-1 | House seats and layout | **9 house seats on 3 hosts (3+3+3), one key per seat, never a key on two hosts.** Amends T-5's 7. Round robin rejected (§1.6, §2.1) |
| D-2 | Host placement | **3 regions**, not 3 zones in one region |
| D-3 | Bond and set floor | **20 YEC for both** the house bond and the set's `bondmin` (`--bond 20`, no ceremony change) |
| D-4 | Set livenessWindow | **1,152 blocks (about 24 h)** |
| D-5 | Ceremony order | **Ceremony first, with the scanned gap** (§4.2, §5.4) |
| D-6 | Light attestor | **The attest agent over lightwalletd:** local signing and guard file, a new `YellowbackStreamer.SubmitAttestation`, join, exit and heartbeat through YEW core (§3.2) |
| D-7 | Cancel watcher on light seats | **In beta4** (changed from revision 1's "defer"): the reads and submission paths of §3.3, two new lightwalletd reads, the cancel builder in YEW core |
| D-8 | Tag v2 (post-quantum payout key) | **In beta4, in the same consensus release as the set id** (§5) |
| D-9 | kogany at the upgrade | **Resync** (or restore a new-release snapshot), **plus a startup check that says "resync required"** |
| D-10 | v1 beside v2 | **Keep v1 for ECC payees and add v2 for post-quantum; both valid from YED start** (§5.2) |
| D-11 | 3b quote cadence | **Every 60-75 s, no heartbeat, no change threshold** (§0.1) |

**Total effort (agent-days):**

| Item | Days |
|---|---|
| 3c | 3-4 |
| 3d (cancel watcher included) | 29-39 |
| 3e | 8-11 |
| 3f | 16-21 |
| **Total** | **56-75**, plus ops and the two-reviewer gate |

## 7. Phased tasks

| Phase | Work | Repos | Depends on |
|---|---|---|---|
| P0 | Done: D-1..D-11 decided. Remaining: record the T-5 amendment (9 house seats, 3 regions) in the testnet plan | workspace | — |
| P1 | One consensus change set on the three lines (ycash-dd → ycash6 → kogany), behind the two-reviewer gate: the id slot in `TestFastParams` (left empty) and the tag v2 (§5.3: tag, payee matching, SCHEMA_VERSION 16, payout-address options, rpcversion 11); tests T2-T5 and V1-V5; kogany startup check; ceremony test T1 | ycash6, ycash-dd, kogany | P0 |
| P1b | v2 clients: yolo `tag.rs` (and PRICE_MAX), YEW core payee script, Python model and check-coinbase, contract fixtures in lightwalletd-dd, YecWallet and chain-viz; V6-V7 | yolo, yew, ycash6 + ycash-dd contrib, lightwalletd-dd, yecwallet-dd, chain-viz | P1 contract |
| P2 | Seat host recipe for 3 hosts in 3 regions (light; a full-node fallback, ycashd wallet or yewd + koganyd, only if P5 is late); the subscribe agent beside the lightwalletd node; a second lightwalletd in another region; monitoring | ycash-infra, ycash-ops | P0 |
| P3 | Ceremony (§4.3 steps 2-4, `--seats 9 --bond 20`, livenessWindow 1,152) once P1 is approved and frozen; gap scan for set acts and for both tag patterns from 510,400; id filled; beta4 tag; upgrade in order; kogany resync | all node lines, ycash-ops | P1, P1b, P2, 3a ready |
| P4 | Wallet retry: on `bundle-insufficient` rebuild at the next block (ycashd wallet, yewd, YEW). Test T6 | ycash6, ycash-dd, yew | P1 |
| P5 | Light attestor, started in parallel with P1: lightwalletd `SubmitAttestation`, `GetTag`, `GetTxOut`, `GetMempoolTxids`; the agent's lightwalletd backend, signer and guard; the cancel watcher over lightwalletd (§3.3); YEW-core set acts and cancel builder; regtest acceptance, including the cancel tests; the seat hosts run light (or move to it if P3 went first on full nodes) | lightwalletd-dd, ycash6 + ycash-dd contrib, yew, ycash-infra | P0 (code); P3 (live) |

**Acceptance of the item:**

- On the fast testnet, `yed_getinfo` shows ARMED and a defined pMint;
- a YEW mint succeeds;
- killing one seat host keeps minting at more than 70 % of blocks and owner redemption at 100 %;
- a wrong-price claim on the fast testnet is cancelled by light seats within CLAIM_DELAY;
- the status page names the feed house-operated.
