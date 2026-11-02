# Survey B: making kogany a Ycash node first

**Date:** 2026-11-01. **Lane:** B (Ycash network identity on Zakura; the librustzcash dependency question).

**Pins surveyed:** `ref/zakura` @ `2b062412c` (= kogany `upgrade/vault` = `kogany-legacy`);
`ref/ycash6` @ `040894344`; `ref/ycash` @ v4.5.0 (`624c12814`); `ycash6` `upgrade/vault` @ `65cb4ae0f`;
`ycash-dd` `upgrade/vault` @ `781946771`; `ref/librustzcash6` @ `ec525fae`; `librustzcash6` `upgrade/vault`
@ `af841431`. Zakura's librustzcash crates were read from the published crates.io packages
`zakura-protocol`, `zakura-primitives`, `zakura-address`, `zakura-equihash` 5.0.0-rc.2 and
`zakura-zcash-script` 0.0.1. Each package's `.cargo_vcs_info.json` names `zakura-core/common` @
`bdbca121628d` (`zakura-zcash-script` @ `ca4c341ed9c4`). Those packages are cited as `zakura-protocol:src/…`
and so on.

## Summary

Ycash differs from Zcash in about a dozen places at the node level: Ycash's own upgrade (`0x374d694f`)
sits between Sapling and Blossom, Ycash uses its **own branch IDs for Blossom, Heartwood, Canopy and
NU5**, Equihash changes from (200,9) to (192,7) at that upgrade, Ycash has its own address prefixes,
ports, seeds, checkpoints, development-fund (YDF) coinbase rule and P2P protocol versions. Ycash
**shares** Zcash's genesis blocks and network magic. Zakura hard-codes every one of these items for
Zcash, in two layers:

1. Zakura's own `zakura-chain`/`-network`/`-consensus` code holds compile-time tables keyed on a unit
   variant `Network::Mainnet`, with 641 non-test mentions of `Mainnet`.
2. The `zakura-*` librustzcash forks hold the branch-ID enum, the address constants and transaction
   parsing.

The **blocking trap** is in layer 2. Zakura turns every transaction into a `zcash_primitives` object
for sighash precomputation and for coinbase note decryption. That conversion calls
`zakura-protocol`'s `BranchId::try_from(u32)`, which rejects every Ycash branch ID from 570,000 onward.
So an unpatched Zakura cannot validate one Ycash transaction after the fork.

The dependency options are laid out below. The recommendation is a **feature-gated fork of
`zakura-core/common`** (`ycash` cargo feature), modelled line-for-line on librustzcash6's two Ycash
commits plus its Vault commits, combined with a compile-time Ycash network profile inside kogany.

Estimate for "Ycash on Zakura" as its own wave, before any Yellowback code:
- about 2.5–4k lines of hand-written production code and 3–5k lines of tests in kogany;
- about 250–400 lines in the forked crates;
- about 7k lines of generated checkpoint data;
- 8–10 agent-sized chunks;
- the exit gate is a full mainnet sync to tip, cross-checked block by block against ycash6.

## 1. Ycash identity inventory: where it lives, where Zakura's equivalent is

Ycash values are cited at `ref/ycash6`, which equals ycash-dd for every row unless noted. Zakura
values are cited at `ref/zakura`.

| # | Item | Ycash value (citation) | Zakura equivalent (citation) | Gap |
|---|---|---|---|---|
| 1 | Upgrade sequence | Sprout, Overwinter 347,500, Sapling 419,200, **Ycash 570,000**, Blossom 1,100,000, Heartwood 1,100,003, Canopy 1,100,006; NU5..NU6.2 none (`src/chainparams.cpp:115-153`). Testnet: Ycash 510,248, B/H/C 661,610/622/634 (`:424-433`). On `ycash6` upgrade/vault the re-forked testnet has B/H/C at 510,250/252/254 and three profiles (`ycash6 src/chainparams.cpp:394-690`). Regtest: everything off by default (`:640-680`). | `NetworkUpgrade` enum has no Ycash variant (`crates/zakura-chain/src/parameters/network_upgrade.rs:27-71`). The order is enforced at compile time (`:73-100`). Heights are Zcash constants (`parameters/constants.rs:84-112`). Configured testnets take heights for the existing variants only (`network/testnet.rs:549-583,899-990`). | A new variant `Ycash` is needed between `Sapling` and `Blossom` (librustzcash6 does exactly this, `ref/librustzcash6` `02d42df5`). Lane D owns its placement. |
| 2 | Branch IDs | Ycash `374d694f`, Blossom **`8e471bd6`**, Heartwood **`66314da3`**, Canopy **`19bd2d2f`**, NU5 **`f919a198`**; Overwinter, Sapling and NU6.x as Zcash (`src/consensus/upgrades.cpp:23-80`). Vault `6d5b7a31` (`ycash6 src/consensus/upgrades.cpp`, upgrade/vault). | One global table, documented as "the same for mainnet and testnet" (`network_upgrade.rs:259-273`), with Zcash's `2bb40e60/f5b9230b/e9ff75a6/c2d6d0b4`. `zakura-protocol:src/consensus.rs:713-760` knows only Zcash IDs. | **Blocking** (§2, trap T1). |
| 3 | Equihash | (200,9) through 569,999; (192,7) from the Ycash upgrade onward, inherited by later epochs (`src/consensus/upgrades.cpp:37-43`). Context-free check by solution size (`src/pow.cpp:155-191`). Height-aware size check (`src/main.cpp:5757-5774`). Regtest (48,5) under every upgrade (`ycash6 src/chainparams.cpp`, `EquihashN` regtest override). | `Solution` is an enum of fixed arrays: `Common([u8;1344])` and `Regtest([u8;36])` (`crates/zakura-chain/src/work/equihash.rs:43-72`). `check` picks (200,9) for every non-regtest network (`:102-115`). The shape is validated without a height (`:118-136`). The header chain's context-free PoW policy calls these (`crates/zakura-header-chain/src/validation/context_free/pow_policy.rs:69-74`). The verifier crate accepts (192,7): collision length 24 is in range (`zakura-equihash:src/params.rs:9-22`), and ycash6 already verifies (192,7) with the same Rust code (`ref/ycash6 src/rust/src/equihash.rs:26`). | A third 400-byte variant plus height-aware parameter selection (trap T3). |
| 4 | Ycash-fork difficulty | Testnet: minimum difficulty for 17 blocks after the fork. Mainnet: time-scaled difficulty for 17 blocks (`src/pow.cpp:53-79`; flags `src/consensus/params.h:312-315`). | No equivalent (`crates/zakura-chain/src/work/difficulty.rs`, `zakura-state/src/service/read/difficulty.rs`). | Inside the checkpointed range on mainnet (§3). Needed only if headers are contextually validated below the mandatory checkpoint (open question 4). |
| 5 | Subsidy, halving | Same formula as Zcash (`src/consensus/params.cpp:121-160`), but Ycash's later Blossom moves the halvings: the first halving is pre-Blossom at 850,000, not Zcash's 1,046,400. | Generic over activation heights (`network/subsidy.rs:927-980`). | None beyond correct heights; add vectors at 849,999/850,000 and at the second halving. |
| 6 | Founders' reward and YDF | Before 570,000: 20% to the Zcash multisig list (stored `t3…`, re-encoded `s3…`, `src/chainparams.cpp:292-343,885-940`). From 570,000 to 2,274,999: exactly 5% to `vYcashFoundersRewardAddress[(h-570000)/17917 mod 48]`, P2PKH or P2SH (`:348-371,909-916`; consensus `src/main.cpp:5901-5939`). From 2,275,000 onward: optional, with no consensus check; miners use `-ydf` (`src/miner.cpp:119-147`). Testnet mandate end 900,000; regtest 5 (`:452,685`). No ZIP-207/214 funding streams, no lockbox. | Pre-Canopy founders' reward ends at the first halving (`network/subsidy.rs:1044-1059`; check `crates/zakura-consensus/src/block/check.rs:205-228`). Canopy onward uses Zcash funding streams, P2SH-only (`check.rs:229-300`; `network/testnet.rs:1556-1561` "panics on … not P2SH"). The address list is Zcash `t3…` (`network/subsidy/constants/mainnet.rs:113`). | New rule (trap T4). This is live consensus from Canopy (1,100,006) to 2,274,999. |
| 7 | Transparent address prefixes | Main `s1` `1C28`, `s3` `1C2C`. Test and regtest `sm` `1C95`, script `1C2A`. Sprout `yc` `1636`. Secret key `80`/`EF`. Coin type 347 (`src/chainparams.cpp:161-176,456-469,689-697`). Legacy Zcash prefixes kept for decoding (`:188-203`; `src/key_io.cpp:303-307`). | `NetworkKind::b58_*` read `zcash_protocol::constants::{mainnet,testnet}` (`parameters/network.rs:75-117`; `transparent/address.rs:201-253`). The constants are Zcash's (`zakura-protocol:src/constants/mainnet.rs`). | Crate constants, or a kogany-native table. |
| 8 | Sapling HRPs | `ys`, `ytestsapling`, `yregtestsapling`. Viewing and spending key HRPs unchanged (`zviews`, `zxviews`, `secret-extended-key-*`) (`src/chainparams.cpp:176-182,471-477,698-704`). | `zakura-protocol:src/consensus.rs:324-412` returns `zs`/`ztestsapling`/`zregtestsapling` from constants. `zakura-chain/src/primitives/address.rs:170-176` encodes through `zcash_address`. | Same as row 7. |
| 9 | Yellowback and PQ forms | YED `yb` `1FDD` / `yt` `2007` / `yr` `2002` (`ycash6 src/yellowback/params.cpp:129,177,288`). PQ plain `sq` `4DD9` / `tq` `4F61` / `rq` `4C51` (`ycash6 src/key_io.cpp:25-31`). | None. | Not this wave. Listed so the profile table reserves them (lane C). |
| 10 | Magic | **Same as Zcash**: `24e92764`, `fa1af9bf`, `aae83f5f` (`src/chainparams.cpp:214-217,521-524,726-729`). The ycash6 re-forked testnet profiles use `f77962d3/d4/d5` (`ycash6 src/chainparams.cpp:647,668,687`). | `parameters/constants.rs:43-45`; configurable on testnets (`network/testnet.rs:869`). | Mainnet: none. Testnet profiles: configured magic. Note trap T6. |
| 11 | Ports | P2P 8833 / 18833 (`fast`) / 18933 (`slow`) / 19033 (`legacy`) / 18344 regtest. RPC 8832 / 18832 / 18932 / 19032 / 18832 (`src/chainparams.cpp:218,525,730`; `ycash6 src/chainparams.cpp:648,669,688`; `src/chainparamsbase.cpp:36-74`). | P2P port hard-coded 8233 / 18233 with a TODO (`parameters/network.rs:254-260`). RPC doc defaults 8232 / 18232 (`crates/zakura-rpc/src/config/rpc.rs:19-24`). Listen default `[::]:8233` (`crates/zakura-network/src/config.rs:904`). | A profile field. |
| 12 | Seeds | DNS `seed.ycash.xyz`, `testseed.ycash.xyz`, fixed `pnSeed6_main` (`src/chainparams.cpp:230-234,537-541`). Re-forked testnet: fixed seeds only (`ycash6`, upgrade/vault). | Zcash DNS seeders (`crates/zakura-network/src/config.rs:886-897`). | A profile field. Fixed seeds need a Zakura equivalent (it has a peer cache; whether it can be seeded with fixed IPs is open question 6). |
| 13 | Genesis | **Same as Zcash**: `00040fe8…ce08` / `05a60a92…2c38` / `029f11d8…e327`; merkle `c4eaa5…` (`src/chainparams.cpp:221-228,533-535`, regtest `:735-740`). | `checkpoint/main-checkpoints.txt:1`; `network/testnet.rs:51-56`. | None. Note trap T6. |
| 14 | Fork-block pin | `UPGRADE_YCASH.hashActivationBlock = 0000014f…7ec5` (mainnet, `src/chainparams.cpp:131-132`), enforced at `src/main.cpp:2346-2385`. | Checkpoints play this role. | Covered by the checkpoint list (row 15). |
| 15 | Checkpoints | Sparse: 13 shared pre-fork entries, then 572,760 … 2,250,000 (`src/chainparams.cpp:242-283`). | Dense Zcash list, one every ~400 blocks to 3,535,411 (`checkpoint/main-checkpoints.txt`, 14,483 lines). The 1,493 entries ≤ 569,686 are **shared history and reusable**. Mandatory checkpoint = Canopy − 1 (`parameters/network.rs:271-280`). Generator: `crates/zakura-utils` `zakura-checkpoints` (`checkpoint/README.md`). | Regenerate above 569,686 from a synced ycash6 (≈7k lines for mainnet), and the same for each testnet profile. |
| 16 | P2P versions, user agent | `PROTOCOL_VERSION 270013`, `MIN_PEER_PROTO_VERSION 270013`, `CINV_WTX_VERSION` pinned unreachable (no MSG_WTX), Vault-era 270200 (`ref/ycash6 src/version.h:13-56`; `ycash6 src/chainparams.cpp` `UPGRADE_VAULT.nProtocolVersion`). Client name `YcashCpp` (`src/clientversion.cpp:23`). | `CURRENT_NETWORK_PROTOCOL_VERSION = 170_190` (`crates/zakura-network/src/constants.rs:350-364`). Per-upgrade minima 170_xxx (`protocol/external/types.rs:88-129`). | Trap T5. |
| 17 | Fast-sync artefacts | None. ycash6 has a chain-supply checkpoint at 2,800,000 (`src/chainparams.cpp:372-379`). | The Zcash-mainnet frontier grid (`zakura-assets` `=0.3535411.0`, root `Cargo.toml:50`), the VCT manifest, `treestate_artifact.rs` (66 `Mainnet` mentions), `commitment_aux_verify.rs`, release-state scripts. | Disable on Ycash. The crate README says a failed grid check is "skipped rather than fatal" (`crates/zakura-assets/README.md`), but kogany should not ship Zcash bytes. |
| 18 | Zcash-only rules | None of: NU5+ Orchard, NU6 lockbox and deferred pool, NU6.1 disbursement, ZIP-234/235 NSM, NU6.3, NU7 25-second spacing, the temporary Orchard-disabling soft fork, Ironwood. | `network.rs:306-393`, `network_upgrade.rs:275-330`, `testnet.rs:779-785`. | Keep dormant by height `None` (lane D). Every such path must tolerate an absent height. |
| 19 | RPC surface used by Ycash clients | lightwalletd-dd calls `getaddressbalance/-txids/-utxos`, `getblock`, `getblockchaininfo`, `getinfo`, `getrawmempool`, `getrawtransaction`, `gettxout`, `sendrawtransaction`, `z_gettreestate`, `yed_getinfo`. It requires t-addrs matching `\As[a-zA-Z0-9]{34}\z` (`lightwalletd-dd frontend/service.go:84`). yolo needs `getblocktemplate`, `submitblock`, `validateaddress`, `getblockchaininfo`. | All the stock methods exist (`crates/zakura-rpc/src/methods.rs`, `methods/rpc_openrpc.rs`). Their answers embed Zcash upgrade names, branch IDs, funding streams and HRPs. | Answers must match ycash6 field for field. `getblocktemplate` must build the YDF output and use (192,7) context. `getblocksubsidy` must report YDF. |

## 2. Traps (rule 4 four-part rows)

**T1. Branch IDs reach librustzcash.** Ycash binds v4 sighash to its own per-epoch IDs
(`src/consensus/upgrades.cpp:33-66`). ycash6 does this through librustzcash6, where `BranchId` is
rewritten to Ycash values (`ref/librustzcash6` `02d42df5`, `components/zcash_protocol/src/consensus.rs`).
Zakura's equivalent is its native table `CONSENSUS_BRANCH_IDS` (`network_upgrade.rs:259`) plus
`Transaction::to_librustzcash` (`crates/zakura-chain/src/transaction.rs:1857-1878`). That function calls
`zakura-protocol` `BranchId::try_from` (`zakura-protocol:src/consensus.rs:744-760`), which knows only
Zcash IDs. It is reached from `SigHasher::new` → `PrecomputedTxData::new`
(`transaction/sighash.rs:173-185`; `primitives/zcash_primitives.rs:252-257`) and from coinbase
`decrypts_successfully` (`primitives/zcash_note_encryption.rs:12-17`; used at
`crates/zakura-consensus/src/transaction/check.rs:530`). The v4 ZIP-243 digest itself is native and
reads the u32 from Zakura's table (`transaction/sighash/v4.rs:166-170,246-247`). **Adaptation:** make
the crate recognise Ycash IDs (§4), and switch kogany's table to Ycash's. **Rung:** a parameter
change, not a rule change. A shim that maps Ycash IDs onto Zcash enum values would work for v4 only.
It fails for v5, where the branch ID is in the transaction bytes, so it would block "turn NU5 on later"
(Ycash's NU5 ID `f919a198` ≠ Zcash's `c2d6d0b4`).

**T2. `Network::Mainnet` is Zcash, by unit variant.** ycash6 rewrote the Zcash `CMainParams` in place
(`src/chainparams.cpp:87-380`), so "main" is Ycash. In Zakura, `Network::Mainnet` carries no parameters
(`parameters/network.rs:62-73`). Every mainnet value is a `match` arm or a constant, with 641
non-test `Mainnet` mentions concentrated in `treestate_artifact.rs`, `commitment_aux_verify.rs` (both
copies), network discovery and handler, and `header-chain/config.rs`. **Adaptation:** a compile-time
Ycash profile (`cfg(feature = "ycash")` on `zakura-chain`, which the other crates inherit) that swaps
the mainnet and default-testnet constant modules. This mirrors ycash6's in-place replacement while
leaving the default build byte-identical to Zakura, so upstream tests still run and the code can be
rebased. The alternative is a runtime `Network::Ycash(..)` variant. It touches every `match` (hundreds
of sites) and is not recommended. A third option, Ycash mainnet as a configured `Network::Testnet(params)`,
gets the wrong `kind()` and t-addr kind (`network.rs:215-232`) and is rejected. **Rung:** parameters
only.

**T3. Equihash parameters change with height, but the header has no height.** Ycash checks the
solution by size without context, then checks the size against the height (`src/pow.cpp:155-191`;
`src/main.cpp:5757-5774`). Zakura binds (n,k) to the network only, by design: a peer must not choose
parameters through solution length (`work/equihash.rs:95-136`). It has no 400-byte representation, and
its header-chain policy is context-free (`pow_policy.rs:69-74`). **Adaptation:**
- add `Solution::Ycash([u8;400])` (or the TODO's `Other(Vec)`, `equihash.rs:106-107`);
- `validate_shape` accepts {1344, 400} on Ycash networks;
- `check` takes the height. The block path has it from the coinbase (`checkpoint.rs:653-670`, `block.rs:430`). The header-chain path needs the header's position, and the shape rule must become "1344 iff height < Ycash activation".

**Rung:** a parameter selection in existing code, with no new rule. The Zakura protections must be
kept: never derive (n,k) from length alone.

**T4. YDF is not a Zcash funding stream.** Ycash pays 5% to a rotating P2PKH/P2SH list from 570,000
until the mandate ends, and checks nothing afterwards (`src/main.cpp:5901-5939`). Zakura's founders'
reward stops at the first halving (850,000 on Ycash), and its funding streams are P2SH-only with
ZIP-214 shapes (`check.rs:205-300`; `testnet.rs:1556-1561`). **Adaptation:** a Ycash-only
`ydf_reward_is_valid` branch in `subsidy_is_valid`, plus `ydf_address(height)`, and lists for
mainnet, testnet and regtest. Funding streams and lockbox stay empty. Reusing funding streams was
considered and rejected: a stream's fixed fraction and P2SH-only recipients are both wrong here.
**Rung:** a rule port, consensus-reviewed, with no new rule design. Golden vectors are taken from
ycash6 coinbases at 570,000; 570,000 + 17,917·k; 1,100,006; 2,274,999; 2,275,000.

**T5. P2P protocol versions.** ycashd peers advertise 270013 and refuse peers below 270013
(`ref/ycash6 src/version.h:18,26`). Zakura advertises 170_190 (`constants.rs:350`), so every ycashd and
ycash6 peer would drop it. Zakura's minimum would also let Zcash peers (170_150+) through.
**Adaptation:** a profile-driven version table: 270013 floor and current, 270200 from Vault; NU7's
version stays unused. Keep MSG_WTX unadvertised like ycash6 (`version.h:39-51`). **Rung:** network
policy, not consensus.

**T6. Same genesis and magic as Zcash.** Ycash separates from Zcash by port, seeds, protocol version
and, finally, branch-ID validation. Zakura's native v2 overlay identifies a chain by
`chain_id = genesis hash` (`crates/zakura-network/src/zakura/handshake.rs:265-271`;
`zakura/README.md`), so a kogany node and a Zakura Zcash node look like the same chain on the
QUIC/v2 layer and its signed discovery records. **Adaptation:** for Ycash, derive `chain_id` from the
fork block (`0000014f…7ec5`) or a domain-separated tag, as the dev-cohort mechanism already does; or
ship kogany with the v2 stack off (legacy TCP only) until that is designed. **Rung:** network-layer
identity, no consensus change.

**T7. Pre-Canopy Ycash history is checkpoint-only.** zcashd and ycashd fully validate from genesis.
Zebra and Zakura check pre-Canopy blocks against the checkpoint list (hash chain, PoW, merkle root:
`crates/zakura-consensus/src/checkpoint.rs:647-690`). **Adaptation:** a Ycash checkpoint list through
at least 1,100,005, generated from a ycash6 node that fully validated. The Ycash-specific pre-Canopy
rules are then enforced by the hashes, not by code: the fork difficulty, the 20% founders' reward to
569,999, and the first 530k blocks of YDF. That is the same trust Zakura places in Zcash history.
It must be written down as a stated assumption.

## 3. What a Ycash-correct kogany must compute, by height band (mainnet)

| Band | Validation in kogany | Ycash-specific work |
|---|---|---|
| 0 – 569,999 | checkpoints (shared Zcash list) | none |
| 570,000 – 1,100,005 | checkpoints (new Ycash list), Equihash (192,7) and difficulty threshold per block | T3, plus row 15 |
| 1,100,006 – 2,274,999 | full validation | T1, T3, T4 (YDF 5%), Ycash branch IDs, Canopy rules (ZIP-211/212/213/215) |
| 2,275,000 – tip | full validation | as above, YDF unchecked |
| Vault height (unset) | full validation | Yellowback waves (lanes C and D) |

The testnet profiles follow the same shape with a re-forked fork block. Their checkpoints come with
each rc (`ycash6 src/chainparams.cpp` testnet comment, "checkpoints above the fork come with each rc").

## 4. The dependency question

What ycash6 needed from librustzcash, as measured in `ref/librustzcash6`:
- `02d42df5`, 7 files, +113/−69: a `NetworkUpgrade::Ycash`/`BranchId::Ycash` variant, Ycash IDs
  replacing Zcash's, Ycash heights with NU5+ `None`, `ZIP212_GRACE_PERIOD` 32256→3, Ycash
  prefixes/HRPs/coin type, and the Ycash epoch as v4;
- `ec525fae`, 6 files, +38/−6: tests;
- on `librustzcash6` upgrade/vault, Vault adds `4867cf85` (5 files, +75/−9) and `eeb7740d` (3 files,
  +32/−6: Vault v4-only).

The rest of librustzcash6's 6.5k-line delta is CI, security work and wasm. The genuine Ycash
consensus-parameter delta in the library is therefore about **250 lines including tests**.

Zakura's crates are a different line: `zakura-core/common` 5.0.0-rc.2, which has `Nu6_3`, `Nu7`, V6
transactions and Ironwood (`zakura-protocol:src/consensus.rs:713-741`;
`zakura-primitives:src/transaction/mod.rs:201-225`). librustzcash6's commits do not apply to it
mechanically, but they apply one for one by meaning.

| Option | What | Rebase onto zakura main | Consensus risk | Minimalism / future NU5 | Size |
|---|---|---|---|---|---|
| **O1. Replace-in-fork** (librustzcash6 pattern) | Fork `zakura-core/common` at `bdbca121`. Replace Zcash IDs and constants with Ycash's, add `Ycash` (later `Vault`) variants. kogany pins it via `[patch.crates-io]`, the way ycash6 pins librustzcash6 (`ycash6 Cargo.toml`). | Every bump of `zakura-*` 5.0.x means re-porting about 250 lines. The fork's upstream tests (Zcash vectors) break and must be skipped, as in `ec525fae`. | Low. A proven pattern; the crate becomes Ycash-only, so a wrong-chain mix-up is impossible. | Ycash's NU5 ID is representable. Orchard remains available. | ~250–300 lines |
| **O2. Feature-gated fork** (recommended) | As O1, but every Ycash value sits behind `#[cfg(feature = "ycash")]` in `zcash_protocol`, `zcash_primitives` and `zcash_address`. kogany's `ycash` feature turns it on. | Better than O1: with the feature off the fork is upstream, so upstream tests still pass, and it could be offered upstream. | Low. It adds a feature-unification hazard: a Zcash-built dependency in the same binary would silently become Ycash. That is acceptable for a node binary, and CI must build both ways. | As O1. | ~300–400 lines |
| **O3. kogany-only shim, no crate fork** | Keep the stock `zakura-*`. Map each Ycash ID to the Zcash `BranchId` of the same era only inside `to_librustzcash`, and hash with the native u32. Encode `s1`/`ys` addresses with a kogany-native encoder. | Best: no crate fork. | **Medium.** Every `zcash_primitives` path that folds the enum's branch ID into a digest must be proven unreachable for Ycash. Today that means the non-v4 fallback in `sighash.rs:233-237` and any library-side signing. A wrong ID there silently changes consensus. | **Fails the lead architect's constraint.** v5 transactions carry the branch ID in their bytes, and Zcash's enum cannot represent `f919a198`, so turning NU5 on later would force O1 or O2 anyway. | ~400 lines in kogany |
| O4. Swap in librustzcash6 crates | Replace `zakura-*` with librustzcash6's `zcash_*` 0.9/0.28 line. | Breaks every Zakura API that uses NU6.3, NU7, V6 or Ironwood. | High | Defeats rebasing. | Very large. **Reject.** |
| O5. Upstream generalisation | Propose that `zakura-core/common` take branch IDs and constants from a `Parameters` object (`BranchId::Other(u32)` or similar). | Ideal if accepted. | — | — | Not in our control. Pursue alongside O2, never as a dependency. |

**Recommendation: O2**, together with T2's compile-time Ycash profile in kogany. The fork lives as a
new workspace repo: a fifth Rust fork, `zakura-common-ycash` (name for the lead architect), with a `-legacy`
baseline at `bdbca121`. It is pinned by exact rev, with the same discipline as
`ycash6 → librustzcash6`. The workspace already runs that line, so the review-gate, CI and pin
machinery (`repos.yaml`, `make status`) carries over.

Shared-defect rule: a Vault or branch-ID change becomes **three** coordinated edits (librustzcash6,
the common fork, kogany), on top of the C++ lines. That rule needs restating in AGENTS.md (lane D/E
input).

## 5. "Ycash on Zakura" as a wave (before any Yellowback code)

Proposed chunks, each one agent in one worktree. The line counts are estimates for hand-written code.
Tests are roughly 1–1.5× the code.

| Chunk | Content | Est. lines | Exit gate |
|---|---|---|---|
| Y0 | Fork `zakura-core/common`. Behind `ycash`: `NetworkUpgrade/BranchId::Ycash`, the Ycash ID table, Ycash constants and HRPs, ZIP-212 grace 3, Ycash epoch v4-only. | 250–350 | The fork's tests pass with the feature both on and off. Branch-ID round trip matches `ref/ycash6 src/consensus/upgrades.cpp`. |
| Y1 | kogany `ycash` profile: `NetworkUpgrade::Ycash`, branch-ID table, mainnet and testnet heights, ports, seeds, magic, network names. Zcash-only paths become height-`None`-safe. | 400–700 | Unit tests: `ConsensusBranchId::current` for every band in §3 equals ycash6 `getblockchaininfo`. |
| Y2 | Equihash (192,7): `Solution` variant, height-aware `check`/`validate_shape`, header-chain policy. | 300–500 | Real Ycash headers at 569,999 and 570,000 accept and reject correctly. Fuzz on the solution length. |
| Y3 | YDF and founders' rules (T4), YDF address lists. | 250–400 | Coinbase golden vectors from ycash6 (listed in T4). |
| Y4 | Checkpoints: Ycash mainnet list regenerated from ycash6 with `zakura-checkpoints`, plus testnet-profile lists. Disable the frontier grid and VCT on Ycash. | 150 code + ~7k generated | Checkpoint sync from genesis to 1,100,005. |
| Y5 | P2P: version table (T5), user agent, MSG_WTX off, v2 `chain_id` or v2 disabled (T6). | 200–400 | Peers with ycash6 and ycashd 4.5.0 on regtest and mainnet. No Zcash peer is retained. |
| Y6 | Addresses in RPC and config (`s1`/`sm`/`ys`/`yc`); Ycash `getblocktemplate` coinbase (YDF); `getblockchaininfo`, `getblocksubsidy` and `validateaddress` answers. | 400–700 | RPC diff against ycash6 for the lightwalletd-dd and yolo call sets (row 19). |
| Y7 | Regtest parity with ycash6 (Ycash off by default, `-nuparams`-like activation, (48,5)). | 150–300 | The lane E harness runs one regtest script on both nodes. |
| Y8 | Mainnet full sync to tip, alongside ycash6, comparing block by block: hash, `getblockchaininfo` (value pools, ZIP-221 history root from Heartwood 1,100,003), `z_gettreestate` at sampled heights. | harness | Byte-identical answers; zero rejected blocks. **This is the wave's exit gate.** |

**Total:** about 2.3–4k lines of production code in kogany, 250–400 in the crate fork, 3–5k lines of
tests, and about 7k lines of generated checkpoint data. That is two to three times the size of the
librustzcash6 library delta, because Zakura spreads network identity across many crates where
ycashd puts it in `chainparams.cpp`.

## Open questions for the lead architect

1. **Dependency option.** O2 (feature-gated fork of `zakura-core/common`, recommended), O1
   (Ycash-only fork), or O3 (shim, which conflicts with "turn NU5 on later")? Also the fork's repo
   name and the GitHub account that holds it, and whether it enters `repos.yaml` with a `-legacy` baseline.
2. **Profile mechanism.** A compile-time `ycash` feature, so the kogany binary is Ycash-only and the
   default build stays Zakura-identical (recommended)? Or a runtime network variant that could run
   Zcash and Ycash from one binary?
3. **Yolk.** `ref/ycash6 src/version.h:16,25,42,55` names "Yolk v4.3.1", a Zebra-based Ycash node on
   the live network. A web search found no public source. If its source exists, it is the closest
   prior art for Y1–Y5 (a Zebra lineage with Ycash parameters) and should become a `ref/` pin. Who
   owns it?
4. **Pre-Canopy trust.** Accept checkpoint-only validation of 0–1,100,005 (T7), as Zakura does for
   Zcash? Or also implement the Ycash-fork difficulty rules and the pre-Canopy YDF, for an
   independent re-validation run?
5. **Testnet.** Carry all three re-forked profiles (fast, slow, legacy) from the start? Or only
   `slow` and `fast`? The legacy Ycash testnet3 should be dropped, as ycash6 did.
6. **Zakura v2 P2P on Ycash.** Ship legacy-TCP-only first (recommended), or design a Ycash `chain_id`
   now (T6)? Does Ycash need fixed seed IPs that Zakura's config cannot express?
7. **zcashd-compat mode.** `docs/zcashd-compat.md` pairs Zakura with a zcashd sidecar. Is the target
   a kogany front with a ycash6 sidecar (which keeps wallet and `yed_*` in C++), or a standalone
   kogany? This changes how much of Y6 and the Yellowback RPC must be native.
8. **Release-state machinery.** The frontier-grid asset, the VCT manifest and
   `scripts/check-release-state.sh` are Zcash-mainnet artefacts. Disable them for Ycash, or build a
   Ycash equivalent later?

## Inputs the synthesis needs from other lanes

- **Lane A:**
  - Does the header chain validate difficulty and solution shape **contextually** below the mandatory
    checkpoint? If so, the Ycash-fork difficulty rule (row 4) and the (200,9)→(192,7) switch are
    needed in header sync, not only in block validation.
  - Where exactly the height enters `pow_policy`.
  - Does `zakura-zcash-script` compute any sighash from the library's enum branch ID? This is T1's
    residual risk.
- **Lane D:**
  - The placement of `NetworkUpgrade::Ycash` (between Sapling and Blossom, matching librustzcash6)
    and of `Vault`.
  - Confirmation that `activation_height`'s "inherit the next upgrade's height" fallback
    (`network_upgrade.rs:459-468`) is safe when Ycash leaves NU5..NU7 at `None`.
  - Whether `CONSENSUS_BRANCH_IDS` becomes per-profile. Ycash's NU5 ID is `f919a198`, not Zcash's.
- **Lane C:** whether `yb/yt/yr`, `sq/tq/rq` and the `rpcversion` field belong in the Y1 profile
  table or in a Yellowback wave; and which RPC answers lightwalletd-dd and yolo compare beyond row 19.
- **Lane E:**
  - A harness that runs ycash6 and kogany side by side for Y8 (mainnet sync comparison) and for
    regtest.
  - A CI matrix that builds the common fork with `ycash` both on and off.
  - Whether a regtest (48,5) solver is needed, given Zakura's regtest `disable_pow`
    (`network/testnet.rs:1527`) versus ycash6's real (48,5).
- **Synthesis:**
  - Mapping §24 rows for T1–T7.
  - A restatement of the shared-defect rule across the C++ lines, librustzcash6, the common fork
    and kogany.
  - The Y0–Y8 wave as "Wave 0", ahead of every Yellowback wave.
