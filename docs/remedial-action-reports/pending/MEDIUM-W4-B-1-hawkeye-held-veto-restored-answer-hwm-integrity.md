# MEDIUM — W4-B-1, 02/V-N1, W4-B-3 (+ W4-B-7 alarm label) — One member can hold any burn indefinitely: an un-adoptable observed unlock makes it a required answerer, a signed `held` answer is a permanent veto, and an edited `hawkeye.db.hwm` gives that veto to stock software; restored members never learn of their own evicted unlock

Repos / branches to change: `hawkeye` (`fix/W4-B-1-held-veto` off `upgrade/vault`: `crates/hawkeye/src/engine/burn.rs` (`prior_unlock`, `observed_signers`), `api.rs` (`burn_unlock`), `peers.rs` (`BurnUnlockResponse`), `restore.rs`, `engine/mod.rs` (the mark writer), `daemon.rs`, `main.rs` / `cli.rs` (`--reset-ledger-hwm`), `crates/hawkeye/tests/engine.rs`, `docs/hawkeye-bridge-plan.md` §5.2 / §5.5 / §11, `docs/operations.md` §5 / §9). No wyec change. **No node change** (governance removal stays the node's existing `SET_REMOVE`; no plan §10 request). · Audit source: `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` §W4-B-1 (`:109-154`), §W4-B-3 (`:196-216`), §W4-B-7 bullet 2 (`:273`), "Test fidelity" gaps (`:305-310`); `docs/audits/quantum-vault-ecosystem-wave4/verification/02-verification.md` §W4-B-1 (`:46-89`, partially confirmed, **Medium**, with corrections 1–5), §W4-B-3 (`:159-168`, partially confirmed, Low; part (a) overstated), new finding V-N1 (`:209`, Medium, part of W4-B-1), probes `v02_a`/`v02_b` (`:20-27`); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md` rows "W4-B-1 / 02/V-N1", "W4-B-3..5", priority 1 ("make the `held` veto expire or require evidence"). · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13). · Status: pending

W4-B-1 and V-N1 are one weakness (an un-expiring, evidence-free `held` answer) reached two ways; W4-B-3 is the same answer function seen from the restored member's side (it never reports what it *observed*, only what it signed), and its runbook half is the same `.hwm` file V-N1 abuses. They change the same three places — `prior_unlock`'s required set, the `POST /burns/unlock` answer, and the restore mark — and land together.

## 1. Finding

**W4-B-1 (Medium).** Member R, not burn n's leader, builds a *correct* unlock for n (right amount, recipient and memo) of some free vault, adds a change output funded by its own fee input, set-signs and broadcasts it. Every ledger stores it as an observed unlock with R as signer (`engine/ycash.rs:188-215`), and since it matches, the burn goes `INTENT_PENDING`. R then gets a conflicting spend of its fee input mined (Ycash v4.5.0 has no mempool RBF, so R needs its own hashpower, a miner or pool that never saw the unlock, or a race; or, more simply, a correct unlock on a vault that another honest unlock spends first). After `max(TAKEOVER, C_Y)` blocks the burn returns to `FINALIZED` (M-3, `engine/watch.rs:390-419`) and is assigned again. The leader finds no row of its own; it cannot adopt R's unlock, because a "fat" unlock fails `unlock_value_bounded` (`burn.rs:897`); but every attributed signer of every observed unlock joins the required set (`observed_signers`, `burn.rs:827-847`, filtered only by currency at `:702`), so R must answer. R answers, signed, `held: true` without bytes — which is never "none" (`burn.rs:742-761`, `:797-814`) and, by design, never overridden (`:787-791`; `docs/operations.md:374-376`: "can never be overridden, by design … only removing it from the set (`SET_REMOVE`) releases the burns it holds up"). The burn waits for a governance act. R committed no evidence fault (the intent was correct and never mined), so no case opens. It repeats this per burn for two fees each; independently of the fat-unlock trick, any member already in a burn's leader rotation (`burn_leaders`, `hawkeye-store/src/burns.rs:377-391`) can veto that burn with the same answer. Reproduced by the auditor's probe `w4_p3` (burn states `ASSIGNED, ASSIGNED, INTENT_PENDING`, 0 cases) and re-run by the verifier with anvil.

The verifier's corrections stand and shape the fix: a **silent** R (heartbeating, not answering) is overridable by the existing quorum (`v02_a`); only the signed `held` answer is a hard veto. "Non-slashable" means *no evidence case*: a governance `SET_REMOVE` with `burn = 1` by `slashThreshold` co-signers needs no evidence (`ycash-dd src/vault/state.cpp:833-841`), but the runbook prescribes `burn = 0` for griefing. Impact is liveness only (burned-wYEC holders wait); the fat unlock leaves no sign-once row on honest ledgers, so it pins no vault (contrast `HIGH-W4-B-2`).

**02/V-N1 (Medium, part of W4-B-1).** The veto needs no modified software. `restore::detect` flags the ledger restored when the high-water mark file holds a larger number than the ledger's record count (`restore.rs:66-74`); the flag is set at start-up (`restore.rs:135-157`, `:149`), and from then on `POST /burns/unlock` answers `held: true, restored: true` for **every** burn (`api.rs:160-168`). An operator gets that by writing a larger number into `hawkeye.db.hwm` before starting a stock daemon — a plain decimal number with no binding to the ledger or the key (`restore.rs:39-63`) — or by genuinely restoring and never acknowledging. It is indistinguishable from an honest restore, so no case or alarm tells them apart; every burn whose required set includes that member is frozen until `SET_REMOVE` (`v02_b`; it paid once the member left).

**W4-B-3 (Low).** (a) Runbook §5 lists the backup set as `wallet.dat`, `hawkeye.db` + `-wal`/`-shm`, keystores and `hawkeye.toml`, and says "`tar` the set" (`docs/operations.md:117-123`); §9 "Backups (N-2)" warns that backing up the whole directory restores the mark with the ledger and defeats the self-mode check (`:378-381`). Following §5 literally does not include the mark, so the verifier rates (a) a doc ambiguity, not a contradiction — but nothing in §5 says to keep the mark out, and the mark sits in the same directory. (b) A restored member's own `k = 1` unlock that was broadcast and then evicted after the backup was co-signed by nobody, so every peer truthfully answers "none" (`burn.rs:676-678` requires every other current member's answer while restored): `POST /burns/unlock` answers only from sign-once rows and the restored flag (`api.rs:140-170`), never from the `observed_unlock/` rows peers hold with the very bytes. The restored member signs a fresh vault; whoever still has the old bytes can revive them (01/V-2) — a double release the watchers must cancel and, while W3-B-1 is open, a slash case against the honest restored member.

**W4-B-7, one bullet (Info, carried here because it is the same alarm).** The `unlock-prior-unknown` text labels every missing answerer "(previous leaders" (`burn.rs:805-813`), so an observed signer that never led the burn (R above) is misdescribed to the operator who has to decide on its removal.

## 2. Root cause

- `crates/hawkeye/src/engine/burn.rs:681-687` — every signer of every observed unlock joins `required`; `observed_signers` (`:827-847`) reads the `observed_unlock/<burn>/` rows without classifying them; the adoption check that *would* classify them (`check_prior_unlock`, `:887-935`: `MatchedBurn`, `unlock_value_bounded`, vault unspent) is applied only to decide adoption (`observed_unlock_for`, `:851-877`).
- `crates/hawkeye/src/engine/ycash.rs:188-215` — `remember_observed_unlock` stores any selector-1 unlock whose memo names a burn of this deployment, with its attributed signers; no classification or vault filter. Rows are pruned only once the burn is `RELEASED` `C_Y` deep (`roll.rs:459-500`), so the requirement outlives the fat unlock's vault being rolled or spent.
- `burn.rs:742-761`, `:787-814` — a signed `held: true` with no bytes is recorded in `held_from`, is never "none", and is never overridden; no bound in time, no evidence asked for.
- `crates/hawkeye/src/api.rs:130-175` — `burn_unlock`: `held = row.is_some() || restored` (`:167`); bytes only from this member's own sign-once row while the burn is unpaid here (`:149-161`); `observed_unlock/` rows are not consulted; no vault, intent or "since" in the answer (`peers.rs:82-100`).
- `crates/hawkeye/src/restore.rs:39-74` — the mark is an unauthenticated decimal file beside the ledger (`hwm_path`, `:33-37`); `detect` treats any `mark > count` as a restore; `check_restore` sets `LEDGER_RESTORED` (`:149`); the mark is rewritten each tick (`engine/mod.rs:336-341`).
- `docs/operations.md:117-123` (§5 backup set) vs `:378-381` (§9 "Backups (N-2)"); `:374-376` (the by-design veto).
- `burn.rs:805-813` — the alarm text.

## 3. Fix options considered

| Option | Verdict |
|---|---|
| (a) An observed unlock puts its signers into `required` only if it could still pay **this** burn as adopted: `MatchedBurn` here, `unlock_value_bounded`, vault unspent (or spent < `C_Y` deep), and confirmable (`HIGH-W4-B-2` §4.1) | **Chosen** (the auditor's fix a). A fat or fraudulent unlock can be revived only by its own signer funding its change — a deliberate second unlock by a member, which the watchers cancel and which `MEDIUM-W3-B-1-05-N-1-W4-B-4` classifies as an *unscheduled* correct duplicate: slashable. The free veto becomes a slashable act. |
| (b) Bound the `held` answer in time: page `unlock-hostage` after `N × TAKEOVER`, runbook `SET_REMOVE` trigger | **Chosen** (the auditor's fix b, the verifier's "most useful"). Alone it still leaves a human-speed veto; (c) narrows what an honest daemon can ever answer. |
| (c) Evidence-backed `held`: the answer names the vault of the live row and, when no bytes are served, the intent the responder believes pays the burn and since when; the asker checks the claim against its own ledger and chain | **Chosen**. An honest `held` without bytes lasts at most `max(TAKEOVER, C_Y)` past an eviction (M-3 re-finalizes the burn, after which the bytes are served) unless the named intent is mined — so a held answer whose named intent the asker cannot see for `2 × max(TAKEOVER, C_Y)` is something honest software does not produce. |
| (c′) Let the override quorum apply to such a stale-evidence `held` | **Recommended, owner decision** (it changes the 2026-10-13 "never overridden, by design" rule; record in plan §12). Safe because a stale claim cannot be backed by bytes the responder still serves. Default in code: off (page only) until decided. |
| (d) Make every `held` overridable after a timeout | Rejected: an honest `held` with a mined paying intent would be overridden into a double release. |
| (e) Bind the restore mark to the ledger and the member key (signed `{ledger_id, count}`), and refuse to start on an unverifiable mark instead of flagging "restored" | **Chosen** for V-N1. A hand-edited number no longer turns a stock daemon into a vetoing one; a genuine restore (same `ledger_id`, valid signature, smaller count) is still detected. Producing a signed inflated mark needs custom tooling — modified software, outside V-N1's "stock" premise. |
| (f) A restored member's `restored` answer carries `restored_since`; peers page `member-restored-unacknowledged` after `RESTORED_ACK_DEADLINE`; the runbook names that deadline for `audit-ledger` + `set_importsigned` + `acknowledge-ledger-restore` | **Chosen** (the verifier's V-N1 fix). After (g), overriding a restored member's hold past the deadline is also safe in the sense of (c′) — same owner decision. |
| (g) `POST /burns/unlock` also answers from the responder's `observed_unlock/` rows: `held: true` **with the bytes** when it holds an observed unlock of the burn that passes the adoption checks on its ledger | **Chosen** (W4-B-3 b, the auditor's fix). Adds no veto (bytes are always served with it, so the asker adopts, never waits), and closes the restored member's blind spot. |
| (h) Runbook §5: name `hawkeye.db.hwm` explicitly as **not** part of the tarball; optional `[ledger] hwm_path` to keep it off the ledger directory | **Chosen** (W4-B-3 a). Consistent with §9; with (e) a restored-together mark is still a hazard (it hides the restore), so the text is still needed. |

## 4. Recommended fix

### 4.1 Required observed signers (W4-B-1) (`engine/burn.rs:681-687`, `:827-847`)

Replace `observed_signers` with `observed_payers(b) -> Vec<(PubKey33, String /*txid*/)>`: for each `observed_unlock/<burn>/<txid>` row, decode `raw` and run the same checks as `check_prior_unlock` (`:887-935`) minus the "this attestor already signed another spend" clause — classification `MatchedBurn { nonce: b.key.nonce }`, `unlock_value_bounded`, the vault unspent or spent by this very transaction, and (`HIGH-W4-B-2` §4.1) `confirmable == Yes`. Only signers of rows that pass are added to `required`. A row that fails is logged once per `(burn, txid)` as `unlock_observed_ignored` with the reason (`fat`, `not-matched`, `vault-spent`, `unconfirmable`). Rows themselves stay (pruned as today, `roll.rs:459-500`).

### 4.2 Evidence in the answer (W4-B-1, V-N1) (`peers.rs:82-100`, `api.rs:130-175`)

`BurnUnlockResponse` gains (serde-default, so older peers parse it; the response stays signed by the peer-auth layer):

```rust
/// The vault of the live row the `held` refers to (W4-B-1).
#[serde(default, skip_serializing_if = "Option::is_none")]
pub vault: Option<String>,
/// With `held` and no `unlock`: the intent this ledger links to the burn (it thinks the burn is
/// being paid) and the height it was linked at.
#[serde(default, skip_serializing_if = "Option::is_none")]
pub paying_intent: Option<String>,
#[serde(default)]
pub since: u32,
/// With `restored`: the height the ledger was flagged restored at (V-N1).
#[serde(default)]
pub restored_since: u32,
```

`burn_unlock` fills them from the row (`vault`), the burn record (`intent`, the `INTENT_PENDING` edge height from `events_for`) and a new `meta` key `ledger_restored_height` written by `check_restore` (`restore.rs:149`).

### 4.3 Judging a `held` answer (`burn.rs:742-814`)

- `held` with bytes: unchanged (validated, adopted or rejected).
- `held` without bytes, `restored == false`: if `paying_intent` is confirmed on this node, or in its mempool, or linked to the burn in this ledger → a valid hold (as today). Otherwise record `(member, burn) → first_stale_height` in memory (and `meta` `held_stale/<burn>/<member>` so a restart keeps the clock). Once `tip − first_stale ≥ 2 × max(TAKEOVER, C_Y)`: page alarm **`unlock-hostage`** — `"member <key> has held burn <n> for <b> blocks naming intent <op> that this node has never seen mined or in its mempool (or naming none): honest software re-serves the signed unlock within max(TAKEOVER, C_Y); review and, if confirmed, remove it (SET_REMOVE, docs/operations.md §9)"`. With the (c′) decision taken, such a member also becomes eligible for the existing override (`:787-791` drops the `!held_from.contains` clause for it); until then, page only.
- `restored == true`: as today (never "none"), but once `tip − restored_since ≥ RESTORED_ACK_DEADLINE` (new constant, default `10 × TAKEOVER`, = the longest declaration, `GONE_MAX_TAKEOVERS`) raise page **`member-restored-unacknowledged`** naming the member and the burns it holds; the same (c′) decision governs whether the override then applies.
- Alarm text (W4-B-7): split `missing` into `previous leaders` (from `burn_leaders`) and `observed signers` (from 4.1), and print each list under its own label.

### 4.4 Peers report observed unlocks (W4-B-3 b) (`api.rs:140-170`)

When the responder holds no live row of its own for the burn, look up its `observed_unlock/<burn>/` rows and return the first whose bytes pass the §4.1 checks on its ledger: `held: true`, `unlock: Some(bytes)`, `vault: Some(..)`. Also while the burn is not "unpaid" here: these bytes are already public on Ycash, and the asker validates them (`check_prior_unlock`) before adopting. The restored member then adopts its own evicted unlock instead of signing a fresh vault. A peer that only *observed* an unlock never answers `held` without bytes, so (g) adds no veto.

### 4.5 A bound mark (V-N1) (`restore.rs:33-63`, `engine/mod.rs:336-341`, `daemon.rs:304-306`)

- On the first open after this change, write `meta.ledger_id` = 16 random bytes (`/dev/urandom`, as `peer_auth` draws nonces; no new dependency) if absent. It is copied with the ledger by any backup, so a genuine restore keeps it.
- Mark format v2 (one JSON line): `{"v":2,"ledger_id":"<hex>","count":N,"sig":"<130 hex>"}`, `sig` = `sign_compact(member key, sha256d("HawkeyeLedgerHwm" ‖ set_id ‖ ledger_id ‖ count u64 LE))`. This is a new encoding: add it to plan §4 (a short subsection beside §4.6) and a golden vector to `crates/hawkeye-core/tests/peerauth.rs` first (`hawkeye/CLAUDE.md` rule 3).
- `detect`: a v1 (bare number) mark is migrated once (re-written as v2 at its value) and logged; a v2 mark whose `ledger_id` differs from the ledger's, or whose signature does not recover to this member key, is **not** "restored": start-up fails with `"ledger high-water mark <path> does not verify (edited, or from another ledger): inspect it, then `hawkeye run --reset-ledger-hwm` to re-write it from this ledger"`. A valid mark with `count` > the ledger's count is a restore (today's behaviour).
- `--reset-ledger-hwm` (on `run`; logged at `warn` as `ledger_hwm_reset` with the old file's contents) re-writes the mark from the ledger.
- Optional `[ledger] hwm_path` (default `<store>.hwm`, unchanged) so operators can keep the mark off the ledger's directory (W4-B-3 a).

### 4.6 Runbook and plan

- `docs/operations.md` §5 (`:117-123`): the backup set adds "**not** `hawkeye.db.hwm`: back it up separately or not at all; restoring it with the ledger hides the restore (section 9, 'Backups')"; §9 "Backups (N-2)" (`:378-381`) cites §5. Coordinate the §5 wording with `LOW-W3-B-10-B-11-hawkeye-single-instance-lock-audit-blind-spots` (its journal text goes into the same section).
- §9 alarm rows: `unlock-hostage` (page), `member-restored-unacknowledged` (page); the "A member that answers `held: true` … can never be overridden, by design" paragraph (`:374-376`) rewritten: a `held` must name its evidence; a stale or unacknowledged-restore hold pages, and after the deadline is a `SET_REMOVE` trigger (and, if decided, overridable). State the restore deadline: within `RESTORED_ACK_DEADLINE` blocks of `ledger-restored`, run `audit-ledger`, `set_importsigned` (wallet mode) and `acknowledge-ledger-restore`, or leave the set.
- Plan §5.2: the required set (previous leaders + signers of *adoptable* observed unlocks); the evidence fields; §12: the (c′) decision once taken.

## 5. Tests

Engine tests on the mock node with anvil (`HAWKEYE_REQUIRE_ANVIL=1`; assert burn **state**, not only `unlocks_for`, which sees the mempool only: `engine.rs:1939`). Templates: `held_takeover` (`engine.rs:5431`), `with_one_down` (`:5402`), `fat_unlock` (`:4792`), `r2_takeover_never_funds_a_fat_unlock` (`:4874`), `s3_a_restored_ledger_answers_unknown` (`:5558`), `t3_a_declared_member_that_answers_keeps_its_hold` (`:6057`), `r10_ledger_restore_is_detected` (`:5371`).

- `w4b1_fat_unlock_by_a_non_leader_does_not_hold_the_burn` — the `w4_p3` probe as a regression test (the test that would have caught it): R posts a correct fat unlock and its fee input is double-spent (mock: spend R's fee coin in a mined block); after `4 × TAKEOVER + 4` blocks the burn is `RELEASED` on every ledger (a fresh vault), R's API answering `held: true` throughout; `unlock_observed_ignored{reason=fat}` logged. Fails at `f4436df` (`ASSIGNED, ASSIGNED, INTENT_PENDING`).
- `w4b1_fraudulent_observed_unlock_does_not_hold_the_burn` — the `w4_p1` shape (wrong memo): cases open against R as today, and the burn is paid.
- `w4b1_stale_held_pages_unlock_hostage` — a stub peer (the `rogue_peer` pattern, `engine.rs:2763`) answering signed `held: true` with a `paying_intent` the mock never saw: `unlock-hostage` after `2 × max(TAKEOVER, C_Y)`; the burn stays held (default: page only). With the (c′) switch on, two declarations then release it.
- `w4b1_honest_held_with_a_mined_intent_never_pages` — the paying intent is mined: no alarm, no override, no fresh vault.
- `vn1_edited_hwm_refuses_start` — write `999\n` (v1) after a v2 mark existed, or a v2 mark with a wrong signature: start-up fails with the verification message; `--reset-ledger-hwm` recovers; no `ledger-restored` flag is set. Fails at `f4436df` (the daemon starts flagged restored and answers `held/restored` for every burn).
- `vn1_genuine_restore_still_detected` — copy the ledger and its v2 mark, sign more records, restore the copy (mark from after): flagged restored (the `r10` test, but by restoring a ledger copy instead of writing the mark by hand — closes the wave-4 gap "`r10` simulates a restore by writing the `.hwm` by hand").
- `vn1_restored_member_paged_after_the_deadline` — the `v02_b` probe: a restored, unacknowledged member answers `held/restored`; after `RESTORED_ACK_DEADLINE` every honest ledger pages `member-restored-unacknowledged` naming it; after `leave_member` the burn is paid (as `v02_b`).
- `w4b3_peers_serve_a_restored_members_evicted_unlock` — k = 1: member A signs and broadcasts unlock U for burn n, U is evicted, A's ledger is replaced by a pre-U copy (flagged restored); A asks; a peer answers `held: true` with U's bytes from its `observed_unlock/` row; A adopts U (`unlock_prior_found`), signs no fresh vault, one payment. Fails at `f4436df` (A signs a fresh vault).
- `w4b7_alarm_names_observed_signers_apart_from_leaders` — the `unlock-prior-unknown` text lists R under "observed signers".
- `hawkeye-core/tests/peerauth.rs`: golden vector for the v2 mark message.
- `tests/alarm_table.rs` with the two new page rows.

## 6. Acceptance criteria

1. A member that never led a burn and whose observed unlock of it cannot be adopted is never a required answerer (`w4b1_fat_*`, `w4b1_fraudulent_*`).
2. A `held` answer without bytes carries its evidence; a stale one pages `unlock-hostage` within `2 × max(TAKEOVER, C_Y)` and names the member; an honest one with a visible paying intent never pages.
3. Editing `hawkeye.db.hwm` cannot make a stock daemon answer `restored`; a genuine restore is still detected; an unacknowledged restore pages peers after the deadline.
4. A restored member adopts its own evicted unlock from a peer's observed copy instead of signing a fresh vault.
5. Runbook §5/§9 and plan §5.2 (and §4 for the mark encoding, with its vector) updated in the same branch; the (c′) owner decision recorded (either way) in plan §12; `cargo test --workspace --all-features --locked` green with `HAWKEYE_REQUIRE_ANVIL=1`.

## 7. Risks and side effects

- **Fewer required answerers.** Dropping un-adoptable observed signers lets a fresh vault be signed while such an unlock exists. Its revival needs its own signer to fund it: cancelled by any one watcher and, with `MEDIUM-W3-B-1-05-N-1-W4-B-4`, slashable as an unscheduled correct duplicate. Land that report's classification before or with this one on any set where `auto_slash` is on.
- **Start-up refusal on an unverifiable mark.** A mark corrupted by a disk fault now stops the daemon until the operator resets it; that is deliberate (the previous behaviour silently entered a set-wide veto). The first start after upgrading migrates v1 marks.
- **Mixed versions.** Old peers send no evidence fields: treated as `held` without evidence (stale clock starts at once, page after the bound). Upgrade every attestor together.
- **Bridge downtime / key rotation / contract redeploy:** none.

## 8. Effort estimate and dependencies

3 days: required-set filter 0.5, evidence fields and judging 1, mark v2 and start-up 0.5, observed-unlock serving 0.25, tests and docs 0.75. Depends on `HIGH-W4-B-2-hawkeye-departed-signer-unlock-pins-vault` for `confirmable` (land it first, or implement 4.1 without the currency clause and add it when that lands). Coordinate runbook §5 with `LOW-W3-B-10-B-11-hawkeye-single-instance-lock-audit-blind-spots` and §9 with `INFO-W4-B-6-B-7-hawkeye-restore-false-positive-operator-drift` (its wallet-mode false-positive note is in the same `ledger-restored` row). The (c′) override decision is the owner's.
