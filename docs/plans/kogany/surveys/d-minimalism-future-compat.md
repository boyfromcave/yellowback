# Lane D: minimalism and future compatibility (placing Vault in Zakura's upgrade sequence)

**Date:** 2026-11-01 · **Lane:** D (kogany planning surveys, `wt/BRIEFING-kogany.md`)

**Pins surveyed:** `ref/zakura` @ `2b062412c5` (= kogany `upgrade/vault` = `kogany-legacy`);
`ref/ycash6` @ `040894344b`; `ref/ycash` @ v4.5.0; `ycash6` `upgrade/vault` @ `65cb4ae0f`;
`ycash-dd` `upgrade/vault` @ `781946771`; `librustzcash6` `upgrade/vault` @ `af841431`.
Every Zakura path below is relative to `ref/zakura/`.

**Summary.** Zakura models network upgrades as one global, totally ordered enum. The order is
the activation order: it is enforced by a compile-time assertion, by the configured-height
builder, and by about 20 `>=`/`<` comparisons in consensus code (for example "v5 is valid iff
`nu >= Nu5`" and "v4 is invalid from NU7"). An upgrade also inherits every rule of the upgrades
ordered before it. So **where Vault sits in the enum decides which Zcash rules apply under it**.
The C++ lines put Vault *after* NU5..NU6.2 (`ycash6/src/consensus/params.h:43-56`). Copying that
order into Zakura would hand the Vault epoch NU5, NU6 and (after Nu7) NU7 rules: v5 and v6
transactions, Orchard, ZIP-244 block commitments, the NU6 coinbase-equality rule, 25-second blocks
and the NU7 ban on v4 transactions. That would be fatal. **Recommendation: insert `Vault`
immediately after `Canopy` and before `Nu5`.** The existing Ord gates then treat Vault as
Canopy-era, so v5 is invalid under Vault exactly as U-26 requires, with no new code. Ycash can still
schedule `Nu5`..`Nu7` (and an upstream Tachyon variant) at later heights. Vault stays a runtime
parameter (a height of `None` on Zcash networks), not a cargo feature. Three traps come with the
placement, and each needs an explicit guard: (1) Zakura's activation-height fallback reports an unset
upgrade at the next upgrade's height, so on Zcash Mainnet `Vault` "activates" at NU5's 1,687,104;
vault rules must therefore be gated by an explicit-membership predicate, never `current >= Vault`;
(2) the branch-id table is global and the librustzcash conversion rejects unknown IDs, so every v4
sighash under Vault fails until the `zakura-protocol` fork knows `0x6d5b7a31`; (3) wildcard `_ =>`
match arms compile silently with a new variant. The relative order of Vault and NU5 has no effect on
consensus today on all three lines, because U-26 forbids scheduling NU5..NU6.2 together with Vault.
The divergence from the C++ index order should be recorded as an invariant, not fixed now. Size: an
upstream precedent (NU6.3 wired in as a no-op, `51d3d8839`) touched 27 files, +124/−37 lines.

---

## 1. How Zakura orders and activates upgrades (the facts the design rides on)

| # | Mechanism | Where | Consequence for a Ycash-only upgrade |
|---|---|---|---|
| Z1 | `NetworkUpgrade` derives `Ord`; "variants must be ordered by activation height" | `crates/zakura-chain/src/parameters/network_upgrade.rs:23-27` | Placement = semantics: every `nu >= X` gate reads the enum position |
| Z2 | `NETWORK_UPGRADES` list + `const` assertion that position == discriminant | `network_upgrade.rs:73-100` | The variant is inserted in two lists; the build fails if they disagree |
| Z3 | Mainnet/Testnet activation tables are `const`s; heights in `constants.rs` | `network_upgrade.rs:131-176`; `parameters/constants.rs:51-111` | Zcash networks simply omit Vault (no entry = never current) |
| Z4 | `current()` = the highest-**height** entry ≤ h in the network's `activation_list()` (a `BTreeMap<Height, NU>`) | `network_upgrade.rs:388-393, 406-426` | An unset upgrade is never `current`; dormancy = absence from the map |
| Z5 | `activation_height()` **falls back to the next upgrade's height** when an upgrade is unset | `network_upgrade.rs:448-469` | Trap T1: `Vault.activation_height(&Mainnet)` = NU5's height on Zcash Mainnet |
| Z6 | Same-height upgrades collapse: the later one in enum order overwrites the earlier in the `BTreeMap` | `parameters/network/testnet.rs:924-929` | Vault sharing a height with NU5+ disappears from the map; Vault sharing Canopy's height keeps Vault (harmless) |
| Z7 | Configured heights must ascend in enum order (`OutOfOrderUpgrades`); height 0 refused | `testnet.rs:959-976` | Ycash can set NU5 later only if Vault < Nu5 in the enum |
| Z8 | `ConfiguredActivationHeights`, a struct with one field per NU and `deny_unknown_fields`; `for_regtest()` fills Overwinter..Canopy only | `testnet.rs:547-671` | Vault needs a `vault` field (`"Vault"` in config); Regtest default leaves it unset, like `-nuparams` on the C++ lines |
| Z9 | Branch IDs: one **global** `const` bijection, "the same for mainnet and testnet"; `branch_id()` takes no network | `network_upgrade.rs:249-274, 488-497` | Adding `(Vault, 0x6d5b7a31)` is harmless; Ycash's own Blossom/Heartwood/Canopy/NU5 IDs need a per-network table (lane B) |
| Z10 | `ConsensusBranchId → zcash_protocol::BranchId` via `try_from(u32)` | `network_upgrade.rs:240-247`; `crates/zakura-chain/src/transaction.rs:1857-1878` | Trap T2: the crates.io `zakura-protocol` rejects `0x6d5b7a31` → `SigHasher::new` fails (`transaction/sighash.rs:173-185`) |
| Z11 | `From<zcash_protocol::NetworkUpgrade>` is an exhaustive match; `impl Parameters for Network` routes through it | `network_upgrade.rs:660-678`; `parameters/network.rs:411-424` | If the protocol fork gains `Vault`, this match gains an arm; librustzcash's `for_height` then sees Vault |
| Z12 | NU7 is already scheduled on Zakura mainnet (3,543,405) and testnet | `constants.rs:78-111` | Upstream moves fast at the tail of the enum; insertion in the middle avoids that churn |
| Z13 | Upstream itself inserted an upgrade mid-sequence (NU6.3 between NU6.2 and NU7) as a "no-op activation height" | `git show 51d3d8839` (2026-06-21): 27 files, +124/−37 | Precedent and size model for wave "dormant Vault scaffolding" |
| Z14 | Dormant-feature pattern: Orchard/Ironwood checks use `Nu5/Nu6_3.activation_height(network).is_none_or(...)`; `ZFuture` is a `cfg(zcash_unstable)` variant | `crates/zakura-network/src/zakura/header_sync/wire.rs:134-170`; `network_upgrade.rs:68-69` | "Gate, don't delete" already works for Orchard: no height → dormant code, still compiled and tested on Zcash networks |

### The Ord gates (non-test), and what Vault-before-Nu5 makes them do

| Gate | Where | Vault between Canopy and Nu5 | Vault at the end (C++ order) |
|---|---|---|---|
| v5 tx header branch id must be `>= Nu5` | `transaction/serialize.rs:1140` | v5 under Vault rejected (U-26 for free) | accepted |
| v6 requires `>= Nu6_3` | `serialize.rs:834, 1199`; `zakura-consensus/src/transaction.rs:1243` | rejected | accepted |
| v5 network-upgrade match | `zakura-consensus/src/transaction.rs:1152-1190` | Vault arm joins the "does not support V5" group | joins "supports" group |
| v4 invalid from NU7 (ZIP 2003) | `zakura-consensus/src/transaction.rs:1036-1053` | v4 stays valid | **every vault spend invalid** |
| Coinbase output must **equal** input from NU6 | `zakura-consensus/src/block/check.rs:377` | pre-NU6 rule (≤) | NU6 rule |
| Fee split from NU7 | `zakura-chain/src/parameters/network/subsidy/fees.rs:25` | none | applies |
| Block spacing / averaging window / testnet min-difficulty | `network_upgrade.rs:503-516, 564, 609-618, 640-642` | 75 s, window 17 | 25 s, window 102 (a PoW fork) |
| Auth-data root (ZIP-244 commitments) | `zakura-consensus/src/checkpoint.rs:1355-1357`; `zakura-state/src/service/finalized_state.rs:943, 1081` | not computed | computed |
| `local_genesis` (test chains activate everything ≤ latest) | `zakura-chain/src/local_genesis.rs:417-436` | Vault included when latest ≥ Vault | different set |

This table is the main finding of the lane. A literal port of the C++ position is consensus-dead in
the same way an `OP_DIGIDOLLAR` transplant is (AGENTS rule 3): it compiles, and it forks on the
first Vault block.

## 2. Why the C++ lines could put Vault last and Zakura cannot

On ycashd an epoch is the **highest index whose height is set**
(`ycash6/src/consensus/upgrades.cpp:130-139`). The rules are gated per upgrade by
`NetworkUpgradeActive(h, UPGRADE_X)`, which is height-based and not ordinal. So an unset NU5 placed
before Vault contributes nothing. Vault sits after `UPGRADE_NU6_2` on 6.20.0
(`ycash6/src/consensus/params.h:43-56`) and after `UPGRADE_NU5` on 4.5.0
(`ycash-dd/src/consensus/params.h:41-44`). librustzcash6 copies the order: `UPGRADES_IN_ORDER` ends
`…, Nu6_2, Vault` (`librustzcash6/components/zcash_protocol/src/consensus.rs:691-704`). The C++ lines
needed three special cases for it, and each one shows what a non-ordinal model costs:

- `PrevEpochBranchId` walks back past the unset NU5..NU6.2 (`ycash6/src/consensus/upgrades.cpp:144-162`,
  plan item 15).
- The regtest `-nuparams` back-fill must skip Vault, or `-nuparams=6d5b7a31:h` would also activate
  NU5..NU6.2 (`ycash6/src/init.cpp:1528-1539`, plan item 19).
- The history-tree dispatcher forces V1 leaves for `BranchId::Vault` (`ycash6/src/rust/src/history.rs:50-63`,
  plan item 20).

U-26 then refuses at start-up every schedule that has Vault together with any of NU5..NU6.2, or
Vault without Sapling at or below it (`ycash6/src/init.cpp:1541-1565`; upgrade plan §15.1, U-26
line 827: "NU5 cannot activate on a Vault chain without a further upgrade that defines that
message").

**Consequence for "NU5 later" on the C++ lines (a finding, not a defect today):** suppose the U-26
refusal were lifted and NU5 scheduled after Vault. `CurrentEpoch` would still return Vault (the
higher index) forever, so a v5 transaction could never carry the NU5 branch ID. Turning NU5 on
later therefore needs `UPGRADE_VAULT` moved below `UPGRADE_NU5`, or a new upgrade index after
Vault, on **both** C++ lines and in librustzcash6. Zakura's model, with Vault before Nu5, is the
shape the C++ lines would have to adopt anyway. Minor latent inaccuracy in the same family:
librustzcash6's `BranchId::Canopy.height_bounds` ends at NU5 (`None` on Ycash), so its range overlaps
Vault's (`consensus.rs:882-884`). It is only used by `arb_height` proptests (`consensus.rs:995-1006`),
so it has no consensus effect.

## 3. Design options

| Option | What | Verdict |
|---|---|---|
| **O1** | `Vault` variant between `Canopy` and `Nu5`; height `None` on Zcash networks; set per Ycash network (and `Vault = h` in regtest config) | **Recommended** |
| O2 | `Vault` at the end of the enum (after `Nu7`), mirroring the C++ index | Rejected: inherits NU5–NU7 rules (§1 table), and a v4 vault spend is invalid by ZIP 2003 |
| O3 | `Vault` after `Nu6_2` (literal mirror of ycash6) | Rejected: inherits v5/Orchard, ZIP-244 commitments, NU6 coinbase rule |
| O4 | Vault not an upgrade: a separate `vault_activation_height` parameter plus a branch-id override | Rejected: the branch ID is per-upgrade everywhere: 17 non-test `branch_id()` call sites (history tree `history_tree.rs:138, 236`, ZIP-221 nodes `primitives/zcash_history.rs:203-213, 411`, native ZIP-243 `transaction/sighash/v4.rs:170`, RPC, mempool grace `zakurad/src/components/mempool.rs:195`), and the history tree resets on *upgrade* change (`history_tree.rs:335-342`). An override would spread across all of them. Smaller-looking diff, larger risk |
| O5 | Per-network upgrade sequences (drop derived `Ord`, order per `Network`) | Rejected for now: rewrites every Ord gate (~20 non-test sites), the builder, `local_genesis`, `next_upgrade`. Maximal rebase friction. Only needed if Ycash ever wants an order Zcash forbids (§5, D-4) |
| O6 | O1 behind a cargo feature or `cfg(...)`, as `ZFuture` is | Rejected: every exhaustive match gains `cfg` arms, it doubles the CI matrix, and cargo feature unification would turn it on for every crate. kogany is a Ycash node; the runtime network decides |

**Which rung, and why not lower (rule 4).** Within the decided tier (a network upgrade), O1 is the
data-plus-enum rung: one variant, one branch-ID row, and one height per network. The rung below
(O4, parameters only) looks smaller but misplaces the branch ID, and the branch ID is what
ZIP-243, ZIP-221 and peers bind to. Nothing lower expresses "a new epoch with a new branch ID".

## 4. Recommended design (O1) and the guards it needs

### 4.1 The change set (the "dormant Vault scaffolding" wave; no vault rule yet)

1. `NetworkUpgrade::Vault` after `Canopy`, before `Nu5`, in both the enum and `NETWORK_UPGRADES`
   (`network_upgrade.rs:47-51, 80-81`). Serde name `"Vault"` (the C++ `strName`).
2. `(Vault, ConsensusBranchId(0x6d5b7a31))` in `CONSENSUS_BRANCH_IDS` (`network_upgrade.rs:259-274`).
   It is valid for every network: no Zcash network uses the ID.
3. `vault: Option<u32>` in `ConfiguredActivationHeights` and through `for_regtest`/`heights`/`or`/`From`/
   `with_activation_heights` (`testnet.rs:185-205, 547-671, 899-957`). Regtest default `None`.
4. One arm in every exhaustive match (compile-enforced). Each arm gets the **Canopy** behaviour
   unless a later wave says otherwise:
   - `target_spacing`, `averaging_window` (`network_upgrade.rs:504-513, 610-617`)
   - history tree, `PreOrchard`/V1 (`history_tree.rs:141, 239`); this matches ycash6 item 20
   - block commitment, `ChainHistoryRoot` (`block/commitment.rs:141`)
   - v4 "supports" and v5 "does not support" (`zakura-consensus/src/transaction.rs:1071-1092, 1169-1189`)
   - halo2 verifier group (`zakura-consensus/src/primitives/halo2.rs:394`)
   - p2p minimum version, Ycash Vault = 270200 (`ycash6/src/chainparams.cpp:154`), in
     `zakura-network/src/protocol/external/types.rs:88-120`; the per-network table is lane B
   - `transaction/arbitrary.rs:796`
   - `local_genesis.rs:417-430`
5. **Audit every `_ =>` arm** that matches on an upgrade. These compile silently. Known case:
   `getblocktemplate` proposal commitment bytes, `zakura-rpc/src/methods/types/get_block_template/proposal.rs:206-216`.
   It lists `Canopy` explicitly, so a Vault block template falls into `_ =>` and errors
   ("pre-Canopy"). The inventory belongs to lane A.
6. The Ycash upgrade `0x374d694f` (Sapling < Ycash < Blossom) is the same mechanism and the same
   guards; lane B owns it.

Measured against the precedent `51d3d8839`, expect roughly 25–30 files and +150–250 lines with
tests. The gate for the wave is that Zakura's own test suite passes unchanged on Zcash networks.
That proves the dormant Zcash machinery is intact (§6).

### 4.2 Guards (the traps of O1)

| Trap | Mechanism | Guard |
|---|---|---|
| **T1** fallback activation | Z5: `Vault.activation_height(&Mainnet)` = NU5 height; on a Ycash network with Vault unset and NU5 set later, it would equal NU5's | All vault, set and YED rules gate on one predicate, `Network::is_vault_active(height)`, defined as "`Vault` is present in `activation_list()` and `height >=` its key". **Never** `current(..) >= Vault` and never `Vault.activation_height(..)`. Enforce with a test that runs Zcash Mainnet and Testnet heights across NU5..NU7 and asserts the predicate is false, plus a grep check in CI (lane E) |
| **T2** branch ID unknown to librustzcash | Z10: `to_librustzcash` → `BranchId::try_from(0x6d5b7a31)` fails; `SigHasher::new` builds `PrecomputedTxData` even for v4 (`sighash.rs:173-185`), although a native ZIP-243 path exists (`sighash/v4.rs:148-247`) | The `zakura-protocol` fork (lane B) gains `BranchId::Vault`/`NetworkUpgrade::Vault`, **placed before `Nu5` in its `UPGRADES_IN_ORDER`** (unlike librustzcash6, §2), `has_orchard() = false`, V5 invalid, as librustzcash6 `eeb7740d`. Golden vector: the ZIP-243 sighash under `0x6d5b7a31` from `vault_vectors.json` on both C++ lines |
| **T3** same-height collapse | Z6 | Builder error (mirrors U-26) if Vault is set together with any of `Nu5..Nu7` (and later tail variants), or if Sapling is unset or above Vault. Vault at Canopy's height stays legal (Vault wins the collapse, which is correct) |
| **T4** wildcard arms | §4.1 item 5 | Audit list from lane A; one test per arm at a Vault-height block |
| **T5** global branch-ID ↔ upgrade map | Z9: `NetworkUpgrade::try_from(u32)` parses v5 headers without network context (`serialize.rs:1132`) | Fine for Vault (unique ID). For future Ycash-ID NU5 (`0xf919a198`, `ycash6/src/consensus/upgrades.cpp:68`), see §5. Compare raw branch IDs, not upgrade enums, where a transaction's ID is checked against the network's |
| **T6** script flags are constant | `zakura-script/src/lib.rs:170`: `Flags::P2SH | Flags::CHECKLOCKTIMEVERIFY` for every height | Vault introduces the first epoch-dependent flags (CSV + VAULT, upgrade plan §15.1). Plumb `(network, height)` into the verifier. **Keep the flags independent of the transaction version**: U-26's v4-only rule stays a transaction-validity check, as on the C++ lines, never a "flags off in v5" shortcut (that would turn 0xb2 back into NOP3 for a non-v4 spender) |
| **T7** checkpoint and fast sync skip script checks | Checkpoint-verified blocks commit without script verification; VCT fast sync imports commitment trees (`zakura-state/src/service/finalized_state/vct.rs:1-6`, `treestate_artifact.rs:1-17`) | Per-vault, set and YED state must be derived in the finalized-state **write path**, which checkpointed and semantically verified blocks share, and must never be imported from an artifact. Ycash checkpoint lists must not cover Vault-epoch blocks until kogany's state at those heights matches the C++ lines (lane E gate) |
| T8 persistence | `HistoryTreeParts` stores `NetworkKind`, not the upgrade (`zakura-state/src/service/finalized_state/disk_format/chain.rs:77-83`); `NetworkKind` order is bincode-significant (`parameters/network.rs:33-35`) | Inserting `Vault` mid-enum is DB-safe. A new `NetworkKind` (if lane B picks one) is appended, never inserted |
| T9 Zcash-only constants | Orchard-disabling soft-fork heights (`parameters/network.rs:22-31`), funding streams, lockbox (`testnet.rs:124-133, 741-819`) | Ycash networks return `None`/empty (lane B). This matters for future adoption: scheduling NU6+ on Ycash brings the NU6 coinbase rule (`check.rs:377`) with an empty stream set |

### 4.3 Cross-line invariant to record (mapping §24)

"The position of Vault relative to NU5..NU7 has no consensus effect on any line while U-26 holds,
because no network may schedule both. ycash-dd orders Vault after NU5, ycash6 after NU6.2,
librustzcash6 after Nu6_2, and kogany (and its `zakura-protocol` fork) after Canopy and before
Nu5. Before U-26 is relaxed, all lines adopt kogany's order (§5)." The golden vectors
(`vault_vectors.json`, `pq_vectors.json`, `yellowback_golden.json`) and a regtest chain crossing the
Vault activation are the oracles. The chain-crossing check compares `hashBlockCommitments` at
H_V−1, H_V and H_V+1, because the history tree resets at H_V (`history_tree.rs:335-342`;
ZIP-221).

## 5. What "turning Orchard / NU6 / NU7 / Tachyon on later" would require

Zakura activates upgrades implicitly. A later upgrade carries every earlier rule
(`local_genesis.rs:440`; `is_nu7_active` "treats every upgrade after NU7 as NU7-active",
`network_upgrade.rs:634-642`). So Ycash adopting a later Zcash upgrade means scheduling Zakura's
existing variants at heights above Vault on the Ycash network, with **Ycash branch IDs**, as Ycash
did for Blossom/Heartwood/Canopy (`ycash6/src/consensus/upgrades.cpp:44-69`). With O1 the Zakura
side is configuration plus a per-network ID table. The vault rules are the hard part:

| Future step | Requires of the vault rules | Lines affected |
|---|---|---|
| NU5 (Orchard, v5/ZIP-244) on Ycash | Relax U-26. Either (a) v5 becomes valid generally while vault templates and opcodes still require a v4 spender, or (b) define a ZIP-244 message for `OP_CHECKSETSIG`/`OP_CHECKPQSIG` (the option U-26 rejected). The history tree goes V1→V2 at the NU5 boundary; Zakura handles this by resetting at the upgrade, whereas ycash6's item-20 dispatcher is keyed by branch ID | All three nodes + both Rust crates + YEW/x402/hawkeye signers |
| NU6/NU6.1 | Nothing of the vault; Ycash takes on the coinbase-equality rule and empty funding streams | Parameters only on kogany; C++ lines would need the same |
| NU6.2/NU6.3 (Ironwood, v6) | Same question as NU5, now for v6 transactions | As NU5 |
| **NU7** (ZIP 2003: v4 invalid; 25 s blocks; ZIP 218 limits) | **Hard boundary**: vault spends are v4-only, so a ZIP-244/v6 vault signing message must already exist and be in use. The 25 s spacing changes every block-count constant (CLAIM_DELAY, CANCEL_QUIET, set maturity) by 3× in wall-clock terms → recalibration (`yb-calibration`) | All lines; calibration |
| Tachyon | No variant exists at the pin. It is mentioned only in `README.md:21, 30` and `docs/design/dogwood.md:47, 203`. Assume it is appended after `Nu7` and carries NU7's rules | As NU7, plus whatever transaction format Tachyon defines |

So O1 keeps every one of these *reachable*; none of them is free. Of the decisions before the
lead architect, only the order choice is consequential now: putting Vault before Nu5 is what keeps NU5..NU7
reachable on kogany without reordering later.

## 6. Verification hooks this design gives lane E

- **Zcash regression as the "gate, don't delete" oracle**: upstream's own tests on Mainnet/Testnet/
  Regtest (Zcash) pass unchanged after every kogany wave. Any diff in a Zcash test is a broken
  dormant feature.
- T1 test: `is_vault_active` is false on every Zcash network at every activation boundary.
- Builder tests: the T3 refusals produce the same accept/refuse table as `ycash6/src/init.cpp:1541-1565`
  and `ycash6/src/test/testnet_params_tests.cpp:193`.
- Activation-boundary equivalence vs ycash6 regtest: branch ID, `getblockchaininfo.upgrades`,
  `hashBlockCommitments`, and the v5 rejection reason at H_V.

---

## Open questions for the lead architect

1. **D-1, Vault's position on kogany.** Approve Vault between Canopy and Nu5 (O1). This diverges
   from the C++ index order (after NU5 on ycash-dd, after NU6.2 on ycash6) and from librustzcash6.
   The divergence has no consensus effect while U-26 holds; it is recorded as the §4.3 invariant.
   *Recommended: yes.*
2. **D-2, realigning the C++ lines.** Should ycash-dd, ycash6 and librustzcash6 move Vault below
   NU5 now, so all three lines share one order? *Recommended: no, not now.* It is semantics-free
   today and touches the consensus review gate on both lines. Make it a mandatory precondition of
   any future U-26 relaxation (§2 shows the C++ `CurrentEpoch` would otherwise pin Vault forever).
3. **D-3, keep Zcash networks in kogany.** Keep Zakura's Zcash Mainnet/Testnet/Regtest intact,
   with Ycash networks added alongside rather than replacing them. This keeps the dormant NU5+
   machinery exercised by upstream's tests and minimises rebase conflicts. *Recommended: keep.*
   This needs lane B's network-shape answer.
4. **D-4, implicit activation.** Accept Zakura's model, in which adopting a later Zcash upgrade on
   Ycash brings every earlier one (Tachyon ⇒ NU7 ⇒ 25 s blocks, v4 ban, NU6 coinbase rule).
   Cherry-picking would need O5 (per-network sequences), a large rebase-hostile change.
   *Recommended: accept, and revisit only if Ycash ever plans Tachyon.*
5. **D-5, runtime, not compile-time.** Gate Vault by network parameters only (no cargo feature /
   `cfg`). *Recommended: runtime.*
6. **D-6, future NU5-on-Ycash branch ID.** When Ycash adopts NU5 it uses a Ycash-specific ID.
   ycash6 already carries `0xf919a198` (`ycash6/src/consensus/upgrades.cpp:68`). Confirm that this
   is the reserved value, or that a fresh one will be chosen then. It only matters for the
   per-network table design (lane B) and for T5.
7. **D-7, NU7 boundary.** Record now that Ycash cannot adopt NU7 or Tachyon until a v5/v6 vault
   signing message exists and the block-count constants are recalibrated for 25 s blocks.
   *Recommended: add as a known limitation to upgrade plan U-26's "given up".*

## Inputs the synthesis needs from other lanes

- **Lane A:** (i) the full list of `match` sites on `NetworkUpgrade` with a `_ =>` arm (T4); (ii) how
  `(network, height)` reaches the script verifier (T6); (iii) the finalized-state write path that
  checkpoint and semantic verification share, where per-vault state would be computed (T7); (iv) whether
  `zakura-zcash-script` (crates.io 0.0.1, `Cargo.toml:159`) has to be forked for 0xb2/0xc0–0xc2.
- **Lane B:** (i) the per-network branch-ID table design and how `branch_id()` (17 callers) gains a
  network; (ii) the `Network` shape for Ycash (new `NetworkKind`? appended, T8); (iii) the
  `zakura-protocol` fork that carries `Vault` (before `Nu5`) and the Ycash IDs (T2); (iv) where the
  `Ycash` upgrade (`0x374d694f`) is inserted, same O1 pattern; (v) Ycash p2p protocol versions per
  upgrade (Vault 270200).
- **Lane C:** the list of every rule gated by "Vault active" on the C++ lines (`NetworkUpgradeActive(…,
  UPGRADE_VAULT)` sites), so each maps to `is_vault_active` (T1). Lane C should also confirm that
  no rule depends on Vault's *index* relative to NU5 (beyond `PrevEpochBranchId` and history-tree dispatch).
- **Lane E:** gates for §6: the Zcash-regression gate, the T1 grep and test, the builder-refusal
  parity table, and the activation-boundary equivalence run against ycash6 regtest.

### Mapping §24 rows proposed (four-part check)

| Ycash does X in Y via M | Zakura equivalent Z, lacking M | Adaptation W | Rung / why not lower |
|---|---|---|---|
| Vault epoch = highest **index** with a height, Vault after NU5..NU6.2 (`ycash6/src/consensus/upgrades.cpp:130-139`, `params.h:43-56`) | `current()` = highest **height**; rules gated by enum `Ord` (`network_upgrade.rs:23-27, 406-426`), so position = inherited rules | `Vault` between `Canopy` and `Nu5` | Enum variant (data rung); the parameter-only rung (O4) misplaces the branch ID |
| Unset upgrade = `NO_ACTIVATION_HEIGHT`, inactive (`upgrades.cpp:112-113`) | `activation_height()` falls back to the next upgrade (`network_upgrade.rs:459-469`) | `is_vault_active` = explicit membership in `activation_list()` | Predicate in parameters; nothing lower |
| Branch IDs per network via chainparams `NetworkUpgradeInfo` (`upgrades.cpp:44-99`) | One global const table (`network_upgrade.rs:249-274`) | Vault row global; Ycash IDs per network (lane B) | Table row; per-network table only where IDs differ |
| U-26 start-up refusal of Vault + NU5..NU6.2 (`ycash6/src/init.cpp:1541-1565`) | Builder checks only order and height 0 (`testnet.rs:959-976`) | New `ParametersBuilderError` variants with the same accept/refuse table | Parameter validation; no consensus code |
| Script flags by height (`GetVaultScriptFlags`, plan item 17) | Constant `P2SH | CLTV` (`zakura-script/src/lib.rs:170`) | Plumb `(network, height)`; flags independent of transaction version | Verifier plumbing; required by the opcodes |
