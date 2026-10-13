# HIGH — W4-B-2, 02/V-N2, 02/V-N3, W4-B-5 — Takeover adopts an unlock signed only by a departed member; the row never dies and pins the vault until its owner branch opens; burns draw on roll-due vaults; `hawkeye leave` has no guard; rejoined keys and network upgrades revive or strand signed unlocks

Repos / branches to change: `hawkeye` (`fix/W4-B-2-departed-signer-unlocks` off `upgrade/vault`: `crates/hawkeye/src/engine/burn.rs`, `engine/roll.rs`, `engine/sign.rs`, `engine/mod.rs`, `cli.rs` (`leave`), `main.rs`, `crates/hawkeye-store/src/signonce.rs` + `schema.rs` (one migration), `crates/hawkeye-ycash/src/mock.rs` (currency and branch enforcement), `crates/hawkeye/tests/engine.rs`, `devnet/hawkeye-devnet` (one scenario), `docs/hawkeye-bridge-plan.md` §3.1 / §5.1 / §5.2 / §11, `docs/operations.md` §7 / §9 / §11). No wyec change. **No node change** on either line: everything below uses the node's existing rule (`CheckSetSigs`) and existing RPCs (`set_getinfo`, `gettxout`, `getblockchaininfo`); nothing here is a plan §10 change request. · Audit source: `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` §W4-B-2 (`:156-194`, filed Medium), §W4-B-5 (`:244-257`), "Test fidelity" (`:305-312`); `docs/audits/quantum-vault-ecosystem-wave4/verification/02-verification.md` §W4-B-2 (`:91-157`, **raised to High (conditional)**), §W4-B-5 (`:183-189`), new findings V-N2 (`:210`, Medium, part of W4-B-2) and V-N3 (`:211`, Low); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md` rows W4-B-2, 02/V-N2, "W4-B-3..5, 02/V-N3", priority 1. Background: `docs/audits/quantum-vault-ecosystem-wave3/05-bridge-hawkeye-wyec.md` (the 01/V-2 revival rule this delta implements). · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13); node rules at ycash-dd `da5e0fe`. · Status: pending

The four findings are one defect seen from four sides: Hawkeye decides whether a signed unlock "could still confirm" without asking the question the node asks (are its signers current, under this branch id?), and the per-vault sign-once row that follows from that wrong answer blocks the only defence of the vault (the roll). They share the dead-row rule, the adoption rule and the roll gate, and land as one change.

## 1. Finding

**W4-B-2 (High, conditional).** Leader L signs unlock A of vault V1 for burn n; A is observed by the other members but not mined (evicted, or still in the mempool when L's removal mines, which invalidates it). L then leaves the set — by `SET_REMOVE`, which is the runbook's own preferred escape for a gone member (`docs/operations.md:350-351`), or by an honest `hawkeye leave`. During L's bond exit delay (the set's `maturity`, ≥ 16,128 blocks on mainnet, plan §2.4) L is still *slashable*, and Hawkeye's adoption check accepts any slashable signer. So each takeover leader adopts A from its observed record, records a sign-once row on V1, re-funds A and sends it — and the node refuses it, because `CheckSetSigs` requires exactly k signatures of members **current** at the spend height, and a REMOVED member is not current. Nothing ever marks the row dead (a row dies only when its vault is spent), so the burn is stuck, and every adopter's per-vault row makes it skip V1 in the roll path. After about (n − 1) × `TAKEOVER` blocks (288 on the mainnet example) every live member has adopted and nobody can roll V1. At V1's `ownerHeight` the owner branch opens "even while the bridge is live" (plan §3.1, F-1), and the owner is the **depositor**: it can take the YEC while the wYEC minted against V1, and burn n's claim on it, are still outstanding. Loss of backing, not just liveness. Reproduced on the mock by the auditor's probe `w4_p2` (signers = `[the departed leader's key]` only; the mock does not enforce currency, the node rule does) and re-run by the verifier with anvil and `HAWKEYE_REQUIRE_ANVIL=1`.

Triggers: (1) **honest** — a leader leaves (`hawkeye leave` or a governance `SET_REMOVE`) while its unlock is unmined (mempool lag, a rate-cap wait after broadcast); (2) **malicious** — a member that is also V1's depositor signs a correct unlock of its own near-expiry vault for someone else's burn, gets it observed and kept unmined (mining influence, see `MEDIUM-W4-B-1`), leaves voluntarily (no evidence fault; its bond is at risk only by a governance vote during the exit delay) and reclaims V1 at `ownerHeight` after selling the wYEC. The verifier rates it **High (conditional)**: Medium only if the project accepts "operators intervene by hand within `ROLL_MARGIN`" as a control, and Hawkeye gives them no tool for that today (§2).

**02/V-N2 (Medium, part of W4-B-2).** The fresh-unlock vault choice sorts **Live and RollDue** vaults by `owner_height`, nearest first (`burn.rs:434-441`). Plan §3.1 step 3 ("drain order: releases spend the vaults with the nearest `ownerHeight` first", HK-6) is the reason for nearest-first, but including `RollDue` vaults means a pinned unlock lands, systematically, on the vault closest to its owner branch — often already inside `ROLL_MARGIN` (2,880 blocks on mainnet, `config/ethereum-mainnet.example.toml:33`), leaving operators at most that long after the supply/exposure alarm. And `hawkeye leave` (`cli.rs:1085-1123`) checks only that the key is ACTIVE: it does not look for live signed unlock rows, which is the honest trigger above.

**02/V-N3 (Low).** A departed key whose old bond has been spent may join again (`ycash-dd src/vault/state.cpp:752-756`) and, once mature, is current again: every unlock it signed while it was current becomes valid again (the node checks currency at the spend height, not at signing). That is today the only (undocumented) recovery from W4-B-2, and it is equally a double-pay hazard for burns re-signed meanwhile (acknowledged only in a code comment, `burn.rs:693-696`).

**W4-B-5 (Low).** The set sighash commits to `NextBranchId()` (`ycash-dd src/rpc/vault.cpp:803-808`; self mode signs under `next_branch_id`, `sign.rs:152-156`) and builds carry no expiry (`vault.cpp:717-721`). After any future network upgrade the set signatures of every unmined signed unlock commit to the old branch id and can never confirm, yet Hawkeye keeps those rows live and re-sends them for ever — the same vault pin as W4-B-2 for every row unmined at the activation. Not reachable before the next upgrade after `UPGRADE_VAULT`. By reading at `f4436df` (an addition of this report): Hawkeye's signature attribution is hard-wired to the constant `hawkeye_core::VAULT_BRANCH_ID` in eight places (`burn.rs:914`, `:1609`; `ycash.rs:723`, `:803`; `sign.rs:382`, `:411`; `slash.rs:257`; `audit.rs:229`), so after such an upgrade attribution of *new* spends would fail as well; the same branch-awareness fixes both.

## 2. Root cause

Hawkeye (`f4436df`):
- `crates/hawkeye/src/engine/burn.rs:666-673` — `prior_unlock` takes `members = self.slashable_member_keys()` (current members **and** REMOVED, unfrozen members whose bond is unspent: `engine/mod.rs:860-885`, `slashable_members`) and passes it both to `observed_unlock_for` (`:673`, `:851-877`) and to `check_prior_unlock` (`:746`).
- `burn.rs:917-921` — `check_prior_unlock` requires `a.signers.iter().all(|s| members.contains(&s.pubkey))`: membership, not currency, and no `== unlockThreshold` count (the node requires exactly k, `state.cpp:292`).
- `burn.rs:410-431` — adoption calls `sign_once_unlock` with `origin: Leader` and records a per-vault `sign_once_ycash` row and a per-burn row unconditionally, even when the adopter adds no signature: self mode returns the bytes unchanged once `args.len() >= need` (`sign.rs:182-196`); in wallet mode the node writes no record because it adds no signature (`ycash-dd src/rpc/vault.cpp:1679-1693`: the `WriteVaultSetSig` call sits inside the signing loop), so Hawkeye's ledger and the node wallet disagree about what this member signed.
- `burn.rs:201-333` — `judge_live_unlock`: a row is `Dead` only when the **vault** is spent by another transaction `C_Y` deep or its own intent was cancelled `C_Y` deep (`:266-288`); while the vault is unspent it is `Resend` for ever (`:298-332`). Signer currency and branch id are never examined.
- `crates/hawkeye-store/src/signonce.rs:957-990` — `mark_unlock_dead`, whose only caller is `burn.rs:370-372` (the vault-spent rule). No CLI or engine path marks a row dead for any other reason.
- `crates/hawkeye/src/engine/roll.rs:636-643` — `post_rolls` skips any vault this member holds a `sign_once_ycash` record of ("signed for another spend"). The orphan roll (`roll.rs:42-70`, `orphan_of`) needs the burn paid **elsewhere** `C_Y` deep; the restore roll needs a restore (`restore.rs:131-157`). Neither fires here.
- After the exit delay non-adopters cannot adopt A either: adopters serve the bytes, `check_prior_unlock` rejects them ("a signer is not a member of the set") and counts the responder in `held_from` (`burn.rs:742-761`), so the result is `Prior::Unknown` (`:797-814`) — the burn stays held.
- `burn.rs:433-451` — fresh-unlock vault choice: `Live` + `RollDue`, `sort_by_key(owner_height)` (V-N2).
- `crates/hawkeye/src/cli.rs:1085-1123` — `leave` / `leave_set`: no ledger read, no live-row check (V-N2).
- `burn.rs:689-697` — the comment that acknowledges rejoin revival (V-N3); no code acts on it.
- `crates/hawkeye/src/engine/sign.rs:152-156` (`next_branch_id`) — read at signing time but not stored with the record (W4-B-5).
- `crates/hawkeye-ycash/src/mock.rs:2633-2678` — the mock's `vault_send` counts scriptSig signatures only (`sigs.len() < need`): it recovers no key, checks no currency and no branch id, so the engine suite cannot see either rule (wave-4 "Test fidelity", `02-hawkeye-recheck-and-delta.md:305-312`).

Node (ycash-dd `da5e0fe`, the rules Hawkeye must mirror):
- `src/vault/state.cpp:195-198` — `IsCurrent`: `status == MEMBER_ACTIVE && h >= joinHeight + maturity`.
- `src/vault/state.cpp:289-306` — `SetSnapshot::CheckSetSigs`: exactly k signatures, distinct keys, each current at `h`.
- `src/vault/state.cpp:827-841` — `SET_REMOVE` (governance or voluntary) sets `MEMBER_REMOVED`; with `burn` the bond is frozen, without it the exit delay starts.
- `src/vault/state.cpp:752-756` — a key may join again only once its previous bond in the set is spent (so never while frozen, and never during its exit delay).
- `src/rpc/vault.cpp:803-808` (`SetSighash` under `NextBranchId()`), `:717-721` (`nExpiryHeight = 0`).

Plan: §3.1 step 3 (drain order nearest-first, HK-6; `docs/hawkeye-bridge-plan.md:278-307`, decision record `:875`) does not say whether roll-due vaults are drained; §5.1 (`:544-565`) has no "dead" edge for an unlock row other than the vault spend.

## 3. Fix options considered

| Option | Verdict |
|---|---|
| (a) Adopt only an unlock whose attributed signers are exactly `unlockThreshold` distinct **current** members (the node's rule) | **Chosen** (the auditor's first fix). Removes the trigger. Alone it does not free rows already adopted (ledgers from `f4436df`), nor rows of the departed member's co-signers at `k > 1`. |
| (b) Mark a live row dead when its bytes can no longer satisfy `CheckSetSigs` at the next height and cannot again before the vault is gone: signers below k current, the non-current ones REMOVED or EJECTED (not merely unmatured); or signed under a branch id that is no longer the next block's, `C_Y` past the activation | **Chosen**, with (c). This is the same "could it still confirm?" question the revival rule asks (01/V-2), answered with the node's inputs. |
| (c) On such a "dead by departure" verdict, mark the vault `ROLL_DUE` at once (`mark_orphan`'s path) so it is spent long before the departed key could rejoin (exit delay + bond withdrawal + re-join maturity), and page if the key's bond is spent while the vault is still unspent | **Chosen** — closes V-N3's revival window by construction instead of by timing luck; uses the existing roll machinery. |
| (d) Do not record a per-vault sign-once row when the adopter added no signature (record the adoption under its own domain and a per-burn row of origin `adopted`); the roll path and vault choice then see the vault as free of this member's signatures but still busy for burns | **Chosen**. Matches the node wallet, which records nothing when it signs nothing; makes a pinned vault rollable by every member that never signed it. A member that *did* sign (the leader, a co-signer) still never signs a second spend of the vault (equivocation). |
| (d′) Let the roll path ignore records that carry none of this member's signatures, keeping the current record | Rejected: the `sign_once_ycash` key is `(domain, set, prevout)`, so the roll's own record would collide with the adoption record; it needs the separate domain of (d) anyway. |
| (e) Exclude `RollDue` vaults from fresh-unlock vault choice; keep nearest-first among `Live` (HK-6) | **Chosen** (V-N2). A roll-due vault is about to be rolled; using it for a burn races the roll and puts a burn's unlock where a pin hurts most. |
| (e′) Prefer the vault with the **farthest** `ownerHeight` | Rejected: reverses HK-6's drain-nearest decision (owner decision) for a risk (c)+(d) already remove. |
| (f) `hawkeye leave` refuses while this ledger holds a live signed unlock row whose vault is unspent, or a burn assigned to this member (override flag `--with-live-unlocks`) | **Chosen** (V-N2). With (a)–(d) a leave is no longer dangerous, only costly (the burn is re-signed elsewhere and the vault rolled); the guard keeps the honest path quiet. |
| (g) A manual tool: `hawkeye unlock-dead <burn> <vault> --reason` | Rejected as the mechanism (a human must notice; the departed member can be the attacker); (b) decides it from chain data. A read-only `hawkeye status` listing of pinned vaults is added instead (§4.7). |
| (h) Node change: an expiry on set builds, or a `vault_*` RPC answering "can these signatures still confirm?" | Rejected: not needed (Hawkeye can evaluate `CheckSetSigs` from `set_getinfo` and the bytes); an expiry would also kill honest revivals that 01/V-2 relies on. Not raised as a plan §10 request. |
| (i) Document the manual recovery (wallet-mode `set_signunlock` of a roll; letting the key rejoin) | Rejected as the fix (rejoin is the V-N3 hazard); the runbook records why neither is used (§4.8). |

Given up, recorded in plan §5.1: an unlock whose signer later rejoins and matures could have confirmed again; after (b)+(c) its vault is rolled first, so that unlock is deliberately killed. Payment of the burn moves to a fresh vault (one more fee).

## 4. Recommended fix

### 4.1 One currency-and-branch test (`engine/burn.rs`, new helper next to `check_prior_unlock`)

```rust
/// Whether signed bytes `tx` could satisfy the node's `CheckSetSigs` (ycash-dd
/// src/vault/state.cpp:289-306) at the next height: exactly `k` distinct set signatures over the
/// template input, under the next block's branch id, each recovering to a member current now.
pub(crate) enum Confirmable {
    Yes,
    /// Below k current signers; `revivable_after` = the earliest height a non-current signer
    /// could be current again (its bond spendable + a join + maturity), `None` if never
    /// (EJECTED, or REMOVED with a frozen bond).
    Departed { signers: Vec<PubKey33>, revivable_after: Option<u32> },
    /// The signatures recover to no member under the next block's branch id (W4-B-5).
    WrongBranch { signed_under: Option<u32>, next: u32 },
}
async fn confirmable(&self, tx: &Transaction, vault: &CoreOutPoint, coin: &(Vec<u8>, u64)) -> Result<Confirmable>
```

- Attribute the vault input's signatures under `next_branch_id(&self.ctx.ycash)` (`sign.rs:152-156`), not the constant. If attribution under the next branch finds fewer than k signers but attribution under the row's stored branch id (§4.4) finds k → `WrongBranch`.
- Classify each signer with `self.mem.members` (the `set_getinfo` member list the engine already holds): `m.current` → current; `status == Removed && !bondfrozen` → departed, `revivable_after = bond exit height + maturity + maturity` (bond spendable, then a fresh join must mature: `state.cpp:195-198`, `:752-756`); `Removed && bondfrozen` or `Ejected` → departed, `None`; ACTIVE but not yet mature → treated as **current-to-be** (not departed: its signature becomes valid at maturity, so the row is not dead).
- `Yes` iff the count of current (or current-to-be) distinct signers is exactly `unlock_quorum()`.

Replace the constant in the other attribution sites with the branch id of the spend's height (for a mined spend: the branch active at its block, from `getblockchaininfo.upgrades`; for a mempool spend: the next block's). Keep `VAULT_BRANCH_ID` only as the expected value in tests and the golden vectors.

### 4.2 Adoption (W4-B-2) (`burn.rs:666-761`, `:887-935`)

- `prior_unlock`: adoption candidates (`observed_unlock_for`, `:673`) and served bytes (`:746`) pass `check_prior_unlock` only if `confirmable(..) == Yes`; add `ensure!(a.signers.len() == k)` beside the membership check at `:918-921`. `members` stays the slashable list **only** for accepting a signed *answer* (`:729`): a member in its exit delay may still say "none".
- A rejected candidate whose verdict is `Departed`/`WrongBranch` does **not** put its signers into `held_from`; log `unlock_prior_unconfirmable` with the reason. (Today such bytes make the responder count as "held", which is how the burn stays `Prior::Unknown` after the exit delay.)

### 4.3 Dead rows (W4-B-2, W4-B-5) (`burn.rs:201-333`, `:355-393`)

In `judge_live_unlock`, after the vault-unspent branch (before the fee-input loop, `:298`), call `confirmable` on the stored bytes:

- `Departed { revivable_after, .. }` → `LiveUnlock::Dead("signer(s) <keys> no longer current (REMOVED/EJECTED); the bytes cannot confirm unless a key rejoins (earliest height <h>|never)")`.
- `WrongBranch` → `Dead` only once `tip ≥ activation_height + C_Y` of the branch that replaced the signed one (read from `getblockchaininfo.upgrades`); before that, `Hold` (a reorg below the activation would make them valid again).
- In the `Dead` arm of `post_unlock` (`:368-385`) and for every live row in the orphan loop (`roll.rs:501-592`, which already walks `live_unlock_rows`): when the reason is departure or branch, call `mark_orphan` on the vault (`roll.rs:313-332`: `LIVE → ROLL_DUE`, detail `"unconfirmable signed unlock of burn <n> (departed signer|old branch): rolled so it can never confirm"`) and raise ticket alarm `unlock-unconfirmable` (`"burn <n>: unlock of vault <v> can no longer confirm (<why>); the burn is re-signed from another vault and <v> rolled"`), cleared when the vault is spent.
- The judgement runs on **every** member's ledger for every live row, not only the burn's leader: non-leaders do not call `post_unlock`, so add the check to the orphan pass (`roll.rs` `orphans()`, `:420`), which every member runs each tick.

A row marked dead releases the per-burn guard (`signonce.rs:808-823`, `is_live` `:722-724`, counts only live rows), so the next leader signs a fresh vault; `prior_unlock` no longer requires the departed signer (`:697-702`, unchanged) and no longer adopts the bytes (§4.2).

### 4.4 Ledger: adopted rows and the signing branch (`hawkeye-store`, one migration)

Schema: the next free `user_version` after `V9` (coordinate with `MEDIUM-W3-B-2-05-N-2`, which also adds a migration: whichever lands first takes V10, the other V11; neither depends on the other's tables. Under the consolidated landing order (this report first) this is **V10** and MEDIUM-W3-B-2's is V11; no other pending Hawkeye report adds a migration).

```sql
-- W4-B-2: an unlock adopted at takeover without adding a signature of this member is not a
-- signature of this member: it is recorded per burn (origin 'adopted', its bytes kept for
-- re-sending), never as a sign_once_ycash 'ycash-unlock' row of the vault.
-- W4-B-5: the branch id a set signature was made under, and the height it was made at.
-- (SQLite cannot alter a CHECK: rebuild sign_once_unlock_burn with origin IN
--  ('leader','cosign','drill','adopted') and the new nullable columns, copy, re-create the
--  indexes and immutability triggers as in V6.)
ALTER ... sign_once_unlock_burn ADD adopted_hex TEXT, ADD branch_id INTEGER, ADD signed_height INTEGER;
ALTER TABLE sign_once_ycash ADD COLUMN branch_id INTEGER;   -- NULL for rows before this version
```

Store API (`signonce.rs`):
- `UnlockOrigin::Adopted` (`:654-675`; `as_str` "adopted").
- `Tx::adopt_unlock(set_id, burn, prevout, hex, signed_height)`: the per-burn guard of `sign_once_unlock` steps 1–2 (`:768-823`: refuse if a live row of this burn names another vault, or if this member holds a `ycash-unlock` record of the vault with different bytes), then insert only the per-burn row with `adopted_hex`. Used by `post_unlock`'s adoption arm (`burn.rs:410-431`) **when the signer adds no signature** (`SetSigning::sign` returns the input unchanged, `signatures` unchanged); when it adds one (`k > 1`, a current co-signer completing it), the existing `sign_once_unlock` path is kept.
- `live_unlock_for_burn` (`:921-932`) returns adopted rows too; `post_unlock` (`:347-354`) reads their bytes from `adopted_hex` instead of `ycash_signature`.
- `sign_once_ycash` / `sign_once_unlock` store the branch id the signer used (`SetSigning` exposes it: self mode `SelfSigner.branch_id`, wallet mode the `next_branch_id` read just before `set_signunlock`).
- Fresh-vault choice (`burn.rs:441-451`) skips a vault with **any** live per-burn row (`unlock_burns_of_vault`, `signonce.rs:902-915`), not only one with this member's `ycash-unlock` record: an adopted vault is busy for burns.
- `post_rolls` (`roll.rs:636-643`) keeps skipping a vault this member **signed** (`ycash-unlock` record); a vault with only an adopted row is rollable. A roll racing an adopted unlock that is still confirmable is safe (one spend of the vault confirms) and is only possible once the vault is `ROLL_DUE`.

Upgrade of existing ledgers (testnet/devnet only; no mainnet deployment exists): an adoption recorded by `f4436df` is a `ycash-unlock` record whose bytes carry no signature of this member plus an origin-`leader` per-burn row. The migration cannot tell it from a leader's own record without attribution, so: at start-up after the migration, attribute every live origin-`leader` row's bytes; one with no signature of this member is reported (`legacy_adoption_row`, ticket alarm) and treated as adopted for the roll gate (the per-vault record stays, immutable; the roll of that vault is then done by another member). Runbook §11: "settle every burn before upgrading" (already required for the H-1 shape change, `docs/operations.md:383-386`).

### 4.5 Vault choice and the leave guard (V-N2) (`burn.rs:433-441`, `cli.rs:1085-1123`, `main.rs`)

- `burn.rs:434-439`: draw on `Live` vaults only, nearest `owner_height` first (HK-6 unchanged); additionally skip a `Live` vault whose `owner_height ≤ tip + roll_margin + takeover × |live|` (it falls due before a pinned unlock could be noticed and rolled). Plan §3.1 step 3 reads: "releases spend the **live** vaults with the nearest `ownerHeight` first; a vault due to roll (`ROLL_DUE`, or within `ROLL_MARGIN` plus one full takeover rotation) is never drawn for a burn".
- `hawkeye leave`: before `set_leave`, open the ledger read-only (`Store::open_readonly`, as `audit-ledger` does at `cli.rs:232`) and refuse when (i) `live_unlock_rows(set)` has a row of origin `leader` or `cosign` whose vault is unspent (`gettxout`), or (ii) a burn is `ASSIGNED` to this member or `INTENT_PENDING` on an intent this member signed. Message: `"this member holds live signed unlocks (burn <n> on vault <v>, …): let them confirm, or leave with --with-live-unlocks (the set re-signs those burns and rolls the vaults; docs/operations.md §7)"`. `--with-live-unlocks` proceeds and logs `leave_with_live_unlocks` at `warn`.
- Runbook §7 ("leave") and §9 "A permanently gone member" option 1: removing a member with an unmined signed unlock is safe after this fix (the row dies, the vault rolls); say so, and that a removed member's unlocks are re-signed after one takeover.

### 4.6 Rejoined keys (V-N3)

- The engine already re-reads the member list every tick. When a key that is the signer of a **dead-by-departure** row whose vault is still unspent becomes ACTIVE again, raise **page** alarm `departed-signer-revivable` (`"member <key> joined again; its unlock of vault <v> for burn <n> (dead since <h>) becomes valid at height <joinHeight + maturity>: the vault must be rolled first"`), and move the vault to the front of the roll schedule (`roll_due_from` with `marked = joinHeight`). With §4.3 the vault was marked `ROLL_DUE` at the departure, so in practice it is long spent; the alarm is the backstop.
- Plan §2.4 and the runbook: "a key that leaves and joins again makes any unlock it signed in its previous membership valid again; Hawkeye rolls every vault such an unlock spends as soon as the signer leaves (§5.1)". Replace the comment at `burn.rs:693-696` with a pointer to this rule.

### 4.7 Visibility

- `hawkeye status` gains `pinned_vaults`: every `ROLL_DUE` (or within `ROLL_MARGIN`) vault that this member cannot roll because it holds a `ycash-unlock` record of it, with the record's burn, `ownerHeight` and blocks left; `/metrics` gauge `hawkeye_pinned_vaults`.
- Page alarm `vault-pinned` when such a vault is within `ROLL_MARGIN / 2` of `ownerHeight` and no member's roll of it is in the mempool: `"vault <v> (owner height <h>, <b> blocks left) cannot be rolled by this member (it signed burn <n>'s unlock of it); check that another member rolls it"`. Row in `docs/operations.md` §9 (`tests/alarm_table.rs` enforces the table).

### 4.8 Plan and runbook edits

- Plan §5.1: a signed-unlock row is dead when (1) its vault is spent by another transaction `C_Y` deep (today), (2) its intent is cancelled `C_Y` deep (today), (3) its set signatures can no longer satisfy `CheckSetSigs` — a signer REMOVED/EJECTED (the vault is then rolled at once) — or (4) they were made under a branch id that is no longer the next block's, `C_Y` past the activation. What was given up (§3).
- Plan §3.1 step 3 as in §4.5; §11: none (no open question remains).
- `docs/operations.md` §9: alarms `unlock-unconfirmable` (ticket), `departed-signer-revivable` (page), `vault-pinned` (page), `legacy_adoption_row` (ticket, upgrade only); §7: the leave guard; §11 (upgrades): "settle every burn before a **Ycash network upgrade** activates as well: unlocks signed under the old branch id cannot confirm after it; Hawkeye marks them dead `C_Y` past the activation and rolls their vaults; it never re-signs a stored unlock or cancel under the new branch — a second set signature over a different sighash for the same prevout is a provable equivocation (`LOW-W3-N-5-ycash-sign-once-branch-bound-doc.md`)" (W4-B-5's runbook step; this report owns the Hawkeye runbook text for both W4-B-5 and LOW-W3-N-5); remove from §9 the implication that `SET_REMOVE` of a member with a live unlock is free of consequences.

## 5. Tests

All engine tests run on the shared mock node with anvil (`HAWKEYE_REQUIRE_ANVIL=1`; without anvil `setup_with` returns `None` and the test passes vacuously, `crates/hawkeye/tests/engine.rs:201-212`). Assert on burn and vault **state** and on the mined chain, not only on `unlocks_for` (`engine.rs:1939`), which lists the mempool only (verifier caveat, `02-verification.md:28-31`).

Mock fidelity first (`crates/hawkeye-ycash/src/mock.rs`), without which the tests below would pass wrongly today:
- `vault_send` and block assembly enforce `CheckSetSigs`: for a vault input with selector 1 (and an intent input with selector 2), recover each scriptSig signature over `SetSigMsg(setId, role, prevout, zip243(… SIGHASH 0x81, next_branch))` with the `hawkeye-core` functions the engine already uses, and require exactly k distinct keys current at the next height (the mock's own notion of current: `status == Active`, `mock.rs:19` — a join is current once mined; keep that, the rule under test is departure); refuse `16: mandatory-script-verify-flag-failed` otherwise. Add `MockState::set_next_branch(id, from_height)` driving `getblockchaininfo.consensus.nextblock` and the sighash branch.
- Unit tests in `mock.rs`: a departed member's signature is refused; a rejoined-and-matured key's old signature is accepted again; a signature under the old branch id is refused after `set_next_branch`.

Engine (`crates/hawkeye/tests/engine.rs`; `s1_a_member_no_longer_current_is_not_required` `:5456`, `held_takeover` `:5431` and `with_one_down` `:5402` are the templates):
- `w4b2_unlock_signed_by_a_departed_member_is_never_adopted` — the `w4_p2` shape that would have caught the defect: leader L signs A for burn n on V1; A is observed by every engine, then removed from the mempool; `leave_member(L)` (`mock.rs:975`); run `4 × TAKEOVER`. Assert: no engine records an adopted row for V1; a fresh unlock on another vault confirms and the burn is `RELEASED`; V1 is `ROLL_DUE` then `ROLLED` on every ledger before its `ownerHeight`; no slash case. Fails at `f4436df` (burn never released, V1 never rolled).
- `w4b2_pre_fix_adopted_rows_die_and_the_vault_rolls` — build the `f4436df` end state directly in the ledgers (every engine holding an origin-`leader` row for A on V1 with no own signature), start the fixed engines: `legacy_adoption_row` raised, rows dead by departure, V1 rolled by some member, burn paid once.
- `w4b2_cosigned_unlock_with_a_departed_cosigner_dies_at_k2` (`views(2, 1)`, `engine.rs:1857`): a co-signer leaves; the row is dead on every ledger; only members that did not sign V1 roll it; nobody signs two spends of V1 (assert every `sign_once_ycash` record of V1 per ledger is unique).
- `w4b2_rejoined_signer_pages_and_its_vault_is_rolled_first` (V-N3): L leaves, the mock spends L's bond and re-joins L (current at once in the mock) before V1 was rolled (mine with the roll suppressed); `departed-signer-revivable` raised; the re-joined key's old bytes are never re-sent by any engine and V1 is rolled at once; in the mock (no maturity) assert that the roll is mined before any re-send of A could be, i.e. A never confirms.
- `w4b2_burns_never_draw_on_roll_due_vaults` (V-N2): one `ROLL_DUE` vault nearest `ownerHeight` and one `Live` vault; the burn's unlock spends the `Live` one; with only roll-due vaults, `unlock_no_vault` and no signature.
- `w4b5_unlock_signed_under_the_old_branch_dies_after_activation_plus_cy`: sign A, keep it unmined, `set_next_branch(new, h)`; before `h + C_Y` the row is `Hold`; after, `Dead`, the vault is rolled, the burn is paid from a fresh vault signed under the new branch.
- `cli` test (`crates/hawkeye/tests/`, mock node, no daemon): `leave_refuses_with_a_live_signed_unlock` and `leave_with_live_unlocks_flag_proceeds`.
- `hawkeye-store/tests/migrations.rs`: V9 → next preserves every `sign_once_unlock_burn` row and trigger; `origin = 'adopted'` accepted; immutability unchanged. `sign_once.rs`: `adopt_unlock` refuses a second live vault for a burn; an adopted row does not block `sign_once_ycash` of a roll of that vault; a `ycash-unlock` record does.
- `tests/alarm_table.rs` with the four new rows.

Devnet (real `CheckSetSigs`, both node lines, `hawkeye/CLAUDE.md` rule 5): `hawkeye-devnet scenario leave-with-live-unlock` — burn n; stop the leader's ycashd relay so its unlock stays unmined; `hawkeye leave --with-live-unlocks` on the leader; assert on both `ycash-dd` and `ycash6` that the takeover leader logs `unlock_prior_unconfirmable`, signs a fresh vault, the burn is released once, and the old vault is rolled (`vault_rolled`). Transcripts in `devnet/transcripts/`.

No golden or vector change (no encoding changes; attribution under the next branch equals `VAULT_BRANCH_ID` today).

## 6. Acceptance criteria

1. No engine adopts, serves as "held", or re-sends an unlock whose set signatures are not exactly `unlockThreshold` distinct members current at the next height (`w4b2_unlock_signed_by_a_departed_member_is_never_adopted`).
2. A row whose signer departed is dead on every ledger within one tick of the departure being mined `C_Y` deep, its vault is rolled before its `ownerHeight`, and its burn is paid once (`w4b2_*`, devnet `leave-with-live-unlock` on both node lines).
3. No vault is ever pinned: every `ROLL_DUE` vault is rollable by at least one current member that never signed a spend of it, and `vault-pinned` pages otherwise.
4. Burns never draw on `ROLL_DUE` vaults; `hawkeye leave` refuses with live signed unlocks unless overridden.
5. After a (mock) network upgrade, unmined rows signed under the old branch die `C_Y` past the activation and their vaults roll; attribution uses the spend's branch id.
6. The mock enforces currency and branch binding; plan §3.1/§5.1 and runbook §7/§9/§11 updated in the same branch; `cargo test --workspace --all-features --locked` green with `HAWKEYE_REQUIRE_ANVIL=1`; clippy and fmt clean.

## 7. Risks and side effects

- **Safety argument.** Marking a row dead lets this member sign a second vault for the burn. That is safe exactly when the first bytes cannot confirm before the first vault is spent: true for EJECTED/frozen signers (never current again) and for REMOVED signers whose bond is in its exit delay (≥ 16,128 blocks on mainnet before a rejoin is even possible, plus a fresh `maturity`), provided the vault is rolled in that window — which §4.3 schedules at once and §4.6 pages on. A branch change is final once `C_Y` deep. Review this argument with the 01/V-2 revival rule (`burn.rs:186-200`).
- **Ledger migration.** A table rebuild of `sign_once_unlock_burn` (to widen its `CHECK`). Take the §5 backup first; the migration test proves rows and triggers survive. Coordinate the version number with `MEDIUM-W3-B-2-05-N-2`.
- **Liveness cost.** A burn whose leader leaves mid-flight is paid one takeover later from a fresh vault, plus one roll fee for the old vault.
- **Mixed versions.** An old peer still adopts and pins; upgrade every attestor together (nothing is deployed on mainnet).
- **Bridge downtime / key rotation / contract redeploy:** none. Node: none (both lines unchanged).

## 8. Effort estimate and dependencies

4–5 days: mock currency and branch enforcement 1 day; confirmability, adoption and dead rule 1 day; store migration and adopted rows 1 day; vault choice, leave guard, alarms, status 0.5 day; tests and the devnet scenario on both lines 1–1.5 days. Land **before** any mainnet bridge (consolidated priority 1). Independent of the wyec reports. Land with or before `MEDIUM-W4-B-1-hawkeye-held-veto-restored-answer-hwm-integrity` (both edit `prior_unlock`; this report owns the adoption and dead-row rules, that one the `held` answers) and before `MEDIUM-W3-B-1-05-N-1-W4-B-4-hawkeye-correct-duplicate-unlock-not-slashable` (whose tests use the currency-enforcing mock). Schema version: coordinate with `MEDIUM-W3-B-2-05-N-2-hawkeye-slash-sign-honours-auto-slash`.
