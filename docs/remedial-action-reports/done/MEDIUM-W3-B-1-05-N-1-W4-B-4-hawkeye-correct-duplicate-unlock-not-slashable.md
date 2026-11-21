# MEDIUM — W3-B-1, 05/N-1, W4-B-4 — A correct duplicate unlock by a burn's leader or taker is slashable after `takeover` blocks; a burn already paid is reassigned (now: falsely held) after a late cancel; the owner override can fire on a live, partitioned leader and feed the same slash

Repos / branches to change: `hawkeye` (`fix/W3-B-1-correct-duplicate` off `upgrade/vault`: `hawkeye-core` matcher + `peerauth.rs` (`gone_msg`), `hawkeye` engine `ycash.rs` / `watch.rs` / `slash.rs` / `burn.rs` (override rules), `cli.rs` (`declare-leader-gone`), `hawkeye-store` helpers, plan §2.3 / §4.6 / §5.1 / §5.2 / §8, `docs/operations.md` §9 / §10, devnet drill D-3). No wyec change. No node change on either line (the slash vote is a Hawkeye-level decision; `SET_EQUIVOCATION` is not involved). · Audit source: `docs/audits/quantum-vault-ecosystem-wave3/05-bridge-hawkeye-wyec.md` §W3-B-1 (`:67-106`); `docs/audits/quantum-vault-ecosystem-wave3/verification/05-verification.md` §W3-B-1 (`:35-153`, severity High → **Medium**), new finding N-1 (`:284-302`); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row W3-B-1, priority 4; `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` status table (`:49-50` W3-B-1 **CHANGED**, the "consumed before amount/recipient" hole **STILL OPEN**; `:63` 05/N-1 **CHANGED**), "Remedial reports that are now stale" (`:70-77`), §W4-B-4 (`:218-242`); `docs/audits/quantum-vault-ecosystem-wave4/verification/02-verification.md` status rows W3-B-1 / 05/N-1 (`:38`, `:41`), §W4-B-4 (`:170-181`, **Low**). · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13). · Status: done — completed 2026-10-18 (see the completion record). Previously pending

The three findings share one consequence (an honest member's correct unlock classified `consumed-burn` and slashed) and one test harness. W3-B-1 is the classification; 05/N-1 and W4-B-4 are two paths into it (a third unlock after a late cancel; an override applied to a leader that is alive). They land as one change so the new duplicate class, the re-link rule and the override gate are never half-deployed.

**What changed since this report was first written (wave 3, at `b0f085f`).** The `fix/unlock-revival` delta (`c6a3bd6`, `f4436df`) made a takeover leader ask every previous leader and every observed signer, signed, before signing a fresh vault (`engine/burn.rs:666-815`), and a leader whose burn is `INTENT_PENDING` answers `held: true` (`api.rs:167`). So the original trigger — a reachable leader and an eclipsed taker — now **holds** the burn instead of duplicating it. The matcher, slash and case code are byte-unchanged (`git diff --stat b0f085f..f4436df` lists none of `matcher.rs`, `slash.rs`); the duplicate class is still missing, and the residual triggers are listed in §1. The wave-3 regression test `f4` (taker posts B after A is withheld from its mempool) can no longer reproduce as written; §5 replaces it. 05/N-1's "third unlock" is now a false **hold**, not a payment; §4.4 is still needed to clear it.

## 1. Finding

**W3-B-1 (Medium).** Two intents can still pay one burn honestly, through the paths the delta left open: (1) the **owner override** applied to a leader that is alive but unreachable from the taker (W4-B-4 below); (2) a leader excluded as **non-current** that later rejoins (`burn.rs:689-702`, acknowledged in the comment; closed by `HIGH-W4-B-2` §4.3–4.6, which rolls such vaults at the departure); (3) a **restored** member that signs afresh while its own evicted unlock survives elsewhere (W4-B-3, closed by `MEDIUM-W4-B-1` §4.4); (4) divergent first-leader assignment between ledgers (a genuine benign race inside `takeover`). In each, both unlocks pay the burn's amount to the burn's recipient. The matcher (`crates/hawkeye-core/src/matcher.rs:199-221`) returns `ConsumedBurn { by, benign_race }` **before** it checks value and recipient; `benign_race` is `|first_seen(by) − first_seen(obs)| ≤ takeover` (`:153-155`); `Unmatched::slashable()` (`:121-129`) is true for everything except a benign race. Once one is mined, every voter whose ledger saw the other at least `takeover` blocks apart classifies it `unmatched:consumed-burn` (non-benign), opens a `FRAUDULENT_INTENT` case (`engine/watch.rs:325-370`), and `verify_intent` (`engine/slash.rs:206-360`) votes `SET_REMOVE burn=1` against an honest signer. On mainnet the case is driven only after an operator sets `auto_slash = true` (default `false`, `config.rs:885`), but `MEDIUM-W3-B-2` shows peers co-sign without their operators. Loss: an honest member's bond. Likelihood is lower than at `b0f085f` (each path needs an operator act, a departure, a restore or a genuine race), so Medium stands.

A third, unchanged consequence of the same ordering: because `ConsumedBurn` is returned before the value and recipient checks, an intent naming a consumed burn **with the wrong recipient or value**, posted within `takeover` blocks of the consumer, is classified `consumed-burn:benign-race` and never slashed (`matcher.rs:203-208` before `:209-220`; wave 4 "STILL OPEN"). It is still cancelled, but a rogue member gets a free option to redirect a burn's second payment while the cancel capacity is stressed. The fix below closes it.

**05/N-1 (Low), as it behaves now.** When the cancel of the burn's linked intent A mines and the burn is `INTENT_PENDING`/`INTENT_CONFIRMED` on A, `apply_spends` selector 2 (`engine/ycash.rs:353-377`) still moves it `CANCELLED → FINALIZED` ("intent cancelled: reassign", `:365-376`) without asking whether another intent B already paid the burn; `reclassify` (`watch.rs:170-255`) adopts only `MATURED_UNMATCHED` + `unknown-burn`, and `link_burn` (`ycash.rs:148-177`) only a burn in `FINALIZED|ASSIGNED|WAITING_CAP`. The burn is reassigned. At `b0f085f` a member with no row then signed a third, correct unlock. At `f4436df` that member must first get "none" from every previous leader and observed signer (`burn.rs:676-688`); B's signer holds a live row (its `LiveUnlock::Out`, `burn.rs:275`) and answers `held`, so the burn is **held**: alarm `unlock-prior-unknown` on a burn that is in fact paid, and a wrong burn state on every ledger that linked A first. No loss; by reading, untested (wave-4 verifier, `:41`).

**W4-B-4 (Low).** The override (`hawkeye declare-leader-gone`, `POST /members/gone`) counts a declaration until the declared member's `lastact` exceeds the height **the receiving ledger** recorded it at (`burn.rs:1113-1117`; `height: tip` from the receiver's `getblockcount`, `:1170`, `:1194-1195`), so a declaration delivered late counts from its arrival; it applies to every required member that did not answer **this** request round (`:787-791`); and `gone_quorum(1, 2) = 1` (`:1053-1055`), so at `n_current = 2` one declaration suffices. A leader that is alive but unreachable from the taker's API (partition, TLS or firewall fault) heartbeats only every `heartbeat_blocks` (288 on the mainnet example, `config/ethereum-mainnet.example.toml:35`) while a declaration's default expiry is `2 × TAKEOVER` = 96 (`cli.rs:117`), so a quorum declared after its last heartbeat counts until its next one. The taker then signs a fresh vault while the leader still re-sends its own live row (`burn.rs:386-392`) until its ledger sees the new unlock; if both mine, the second is `ConsumedBurn` and, with W3-B-1 open, a case against an honest member. The quorum is a strict majority of humans (4 of 7 on mainnet), so this is operator error, not an attack, and a malicious member at `k = 1` does not need the override at all.

## 2. Root cause

- `crates/hawkeye-core/src/matcher.rs:199-221` — the `BurnRelease` arm checks `consumed_by` (`:203-208`) before `obs.value != burn.amount` (`:209`) and `recipient_hash` (`:218`).
- `matcher.rs:121-129` (`slashable`) and `:153-155` (`is_benign_race`) — the only exemption is the timing window; "correct but duplicated" has no class.
- `crates/hawkeye-store/src/burns.rs:310-340` (`matcher_burn`) — `consumed_by` = the earliest-**first-seen** mined `Matched`/`Released` intent (`ORDER BY first_seen_height, txid`, `:322`), so the accused flips with each voter's first-seen view, not with mining order.
- `crates/hawkeye/src/engine/watch.rs:325` — the case-opening exemption is a string compare against `"unmatched:consumed-burn:benign-race"`; every other code with a signer ≠ me opens a case (`:330-370`, in `handle_unmatched` `:257-371`).
- `crates/hawkeye/src/engine/slash.rs:206-360` (`verify_intent`) — re-classifies on the voter's ledger; only `!u.slashable()` refuses (`:335-337`); nothing asks whether the accused led or was scheduled to take over the burn, though the ledger now has exactly that list: `Tx::burn_leaders` (`hawkeye-store/src/burns.rs:377-391`, reading the `ASSIGNED` edges whose detail `assign_burn` writes as `"leader <hex>"`, `:406-407`).
- `crates/hawkeye/src/engine/burn.rs:83-97` — takeover is purely `tip ≥ assigned_height + takeover` over `ASSIGNED` burns (by design).
- `crates/hawkeye/src/engine/ycash.rs:353-377` — selector-2 reset with no search for another paying intent (05/N-1).
- `crates/hawkeye/src/engine/burn.rs:1053-1055` (`gone_quorum`), `:1078-1124` (`gone_counts`: void only on `member.lastact > height`, `:1113-1117`), `:1135-1208` (`record_gone`: `height` = receiver's tip, `:1170`, `:1194-1195`), `:787-791` (override applies to every required, non-answering member); `crates/hawkeye-core/src/peerauth.rs:118-126` (`gone_msg` binds `setId ‖ member ‖ seq ‖ expiry`, no "silent since" height, and has no golden vector in `crates/hawkeye-core/tests/peerauth.rs`) (W4-B-4).
- `docs/hawkeye-bridge-plan.md:239` (§2.3 row 2: "or a burn already consumed" is a fraudulent intent) and `:567-573` (§5.2: the benign line is the takeover overlap). The code follows the plan; the fix is a **plan change first** (`hawkeye/CLAUDE.md` rule 3 covers encodings — `gone_msg` is one; the rule change is treated the same way).

## 3. Fix options considered

| Option | Verdict |
|---|---|
| (a-plain) Every correct duplicate (right amount, right recipient) is cancel-only, never slashed, whoever signed it | Removes all honest-slash risk, but turns a deliberate double release into a free option for **any** member and makes drill D-3 (plan §8, `:758`: "slashed outside the race window") meaningless. Rejected as the whole rule; kept as the fallback if the scheduled-role computation proves too fragile in testing. |
| (a-scoped) A correct duplicate is cancel-only **when its signer was the burn's leader or a scheduled taker on the voter's ledger and did not also sign the consuming intent**; otherwise today's rule | **Chosen.** Exactly the honest artefact is exempt; an unsolicited replay (D-3) and a self-duplicate (one key, two vaults, one burn — impossible for an honest binary since the per-burn sign-once dimension, `hawkeye-store/src/signonce.rs:755-836`) stay slashable. `MEDIUM-W4-B-1` relies on "unscheduled correct duplicate ⇒ slashable" to turn its fat-unlock veto into a slashable act. |
| (b) Before taking over, ask the current leader and wait while it reports a live unlock | **Implemented differently by the delta** (`prior_unlock`): it is what made the original trigger hold. It does not remove the need for (a-scoped): the residual paths in §1 bypass it. |
| (c) Refuse to vote when the accused was the burn's leader or a scheduled taker per the voter's own ledger | **Chosen**, as the vote-side half of (a-scoped); also refuses evidence bundles from older peers that still say `consumed-burn`. |
| (d) Lengthen the benign window | Rejected: widens the free window for *incorrect* duplicates too. |
| (e) Evaluate value and recipient before "consumed" | **Chosen** (part of a-scoped): closes the benign-race hole. |
| (f) W4-B-4: require the declared member's `lastact` to be older than `heartbeat_blocks` plus slack before an override applies; bind the declarer's tip ("silent since") into `gone_msg`; refuse the override at `n_current < 3` | **Chosen** (the auditor's fix). The `gone_msg` change is an encoding change: plan §4.6 first, then a golden vector (none exists today). |
| (g) W4-B-4: make declarations burn-scoped | Rejected: burn-unscoped by design (one gone host holds every burn it led); the heartbeat rule already scopes them in time. |

Given up, recorded in the plan: a *scheduled* taker that saw the leader's unlock and posts a correct duplicate anyway is not slashed; the defence is the cancel (any one Hawkeye, I-2, within `delay`) and the `duplicate-unlock` alarm. A role divergence between voters' ledgers can still make an honest taker look unscheduled on some voters; the schedule slack (§4.2) and the operator gate (`MEDIUM-W3-B-2`) bound that residual. A two-member set can no longer use the override (W4-B-4): it removes the gone member on chain instead.

## 4. Recommended fix

### 4.1 Matcher: value and recipient first, then a distinct duplicate class (`hawkeye-core/src/matcher.rs`)

Add a variant and reorder the `BurnRelease` arm:

```rust
pub enum Unmatched {
    …
    /// The burn was already consumed by another intent, and this one pays the burn's amount to
    /// the burn's recipient (W3-B-1). Whether its signer is slashed is the engine's call
    /// (`engine::ycash::duplicate_role`): never when it was the burn's leader or a scheduled
    /// taker; as `ConsumedBurn` otherwise.
    DuplicateBurn { by: Consumer, benign_race: bool },
    …
}

MemoKind::BurnRelease => {
    let Some(burn) = lookup(memo.reference).filter(|b| b.tx_hash == memo.data) else {
        return U(Unmatched::UnknownBurn);
    };
    if obs.value != burn.amount { return U(Unmatched::WrongValue { expected: burn.amount, got: obs.value }); }
    let Ok(recipient) = YcashRecipient::from_bytes(&burn.recipient) else { return U(Unmatched::OrphanedBurn); };
    if recipient.recipient_hash() != obs.intent.recipient_hash { return U(Unmatched::WrongRecipient); }
    if let Some(by) = burn.consumed_by.filter(|c| c.txid != obs.txid) {
        return U(Unmatched::DuplicateBurn {
            by,
            benign_race: is_benign_race(by.first_seen, obs.first_seen, ctx.takeover),
        });
    }
    Classification::MatchedBurn { nonce: burn.nonce }
}
```

`ConsumedBurn` stays in the enum (the engine maps an *unscheduled* duplicate to it, and old ledgers store the code), but the matcher no longer returns it. `slashable()` returns `false` for `DuplicateBurn` (the engine decides) and for a benign `ConsumedBurn`. Extend `Consumer` with `signer: Option<PubKey33>` (`matcher_burn`'s `SELECT` adds `signer_key`, `burns.rs:310-340`). The NEAR bridge uses the same arm (`classify_intent_for`); `engine_near.rs` gets the same test.

An adopted re-send (`burn.rs:410-431`: leader L's bytes re-funded and sent by taker M) spends the **same vault** as L's original, so only one of them can ever confirm; it is never a duplicate and needs no role rule.

### 4.2 The engine's role function (`hawkeye/src/engine/ycash.rs`, beside `classify` `:106-131`)

```rust
pub enum DuplicateRole { Scheduled, SelfDuplicate, Unscheduled }

/// W3-B-1: who `signer` was for burn `k` on this ledger when it posted an intent first seen at
/// `first_seen`.
pub fn duplicate_role(t: &Tx<'_>, p: &Params, k: &BurnKey, signer: &PubKey33,
                      consumer_signer: Option<&PubKey33>, first_seen: u32, live: &[PubKey33]) -> Result<DuplicateRole>
```

1. `consumer_signer == Some(signer)` → `SelfDuplicate`.
2. `t.burn_leaders(k)` (`burns.rs:377-391`) names `signer` with an `ASSIGNED` edge at height ≤ `first_seen + takeover` (read heights from `events_for`) → `Scheduled`.
3. The deterministic schedule from the burn's **first** `ASSIGNED` edge `(h0, leader L)`: `steps = (first_seen − h0) / takeover + 1` (one step of slack); the scheduled set is `{ live[(pos(L) + j) % |live|] : 0 ≤ j ≤ steps }` over this ledger's live list, **and** the same over the set's current members ordered by key (the order `leader_for` uses, `hawkeye-core/src/leader.rs:28-54`); `signer` in either → `Scheduled`.
4. Otherwise `Unscheduled`.

`classify` takes the signer through `IntentFacts` (new field `signer: Option<&PubKey33>`; `apply_unlock` already attributes it, `verify_intent` has it at `slash.rs:259-275`) and maps `DuplicateBurn` to a stored code:

| Role | Stored code | Cancelled | Case / vote |
|---|---|---|---|
| `Scheduled` | `unmatched:duplicate-burn:scheduled` | yes | never |
| `SelfDuplicate` | `unmatched:duplicate-burn:self` | yes | `FRAUDULENT_INTENT` (slashable, any timing) |
| `Unscheduled` | `unmatched:consumed-burn` or `…:benign-race` (today's codes) | yes | as today |

Add `pub fn classification_slashable(code: &str) -> bool` in `hawkeye-store/src/intents.rs` next to `classification_code` (`:140`) and use it at `watch.rs:325` instead of the string compare. A `Scheduled` duplicate raises ticket alarm `duplicate-unlock` (`"burn <n>: a second correct unlock by <key> (scheduled leader/taker), cancelled, not slashed"`), cleared when it is cancelled or matured; row in `docs/operations.md` §9 (`tests/alarm_table.rs` enforces the table).

### 4.3 The vote-side guard (`engine/slash.rs::verify_intent`, `:296-357`)

After classification and before the `match`, when the evidence's intent carries a `BurnRelease` memo naming a burn this ledger knows and the classification is `DuplicateBurn`, `ConsumedBurn` (any variant) or an evidence `classification` of `unmatched:consumed-burn`: compute `duplicate_role` for the accused and `bail!("the accused was burn {n}'s leader or a scheduled taker here: a correct duplicate is cancelled, never slashed (W3-B-1)")` on `Scheduled`. Logged as `slash_vote_refused_here`, `reason = "scheduled-duplicate"`. The case owner's `drive_case` (`slash.rs:686`) uses the same check before building the act, so an old case already open moves to `EXPIRED` with detail `"scheduled duplicate (W3-B-1)"` at the first tick after the upgrade (no schema change).

### 4.4 Re-link a burn already paid (05/N-1) (`engine/ycash.rs::apply_spends`, `:353-377`)

Before the `CANCELLED → FINALIZED` reset (`:365-376`):

```rust
let payer = t.intents_for_burn(&b.key)?            // hawkeye-store/src/intents.rs:259
    .into_iter()
    .filter(|j| j.outpoint != op)
    .find(|j| matches!(j.state, IntentState::Released | IntentState::Matched)
           || (j.state == IntentState::MaturedUnmatched && j.released_txid.is_some()
               && j.classification.as_deref().is_some_and(|c| c.starts_with("unmatched:duplicate-burn"))));
```

- `payer` released → `CANCELLED → FINALIZED → INTENT_PENDING(payer) → INTENT_CONFIRMED → RELEASED` (forward edges, `hawkeye-store/src/state.rs:315-335`), detail `"re-linked to <payer>: already released (05/N-1)"`; log `burn_relinked`.
- `payer` `Matched` (mined or in the mempool) → `CANCELLED → FINALIZED → INTENT_PENDING(payer)` (and `INTENT_CONFIRMED` if mined).
- none → today's reset.

For `intents_for_burn` to find a correct duplicate, `apply_unlock` (`ycash.rs:221`) sets `matched_burn` for `DuplicateBurn` intents too. Extend `reclassify` (`watch.rs:170-255`) so a `RELEASED` burn's later duplicate re-runs, and so a `MATURED_UNMATCHED` intent classified `duplicate-burn:*` with a release recorded is adopted as the burn's payer when the burn is not `RELEASED` here (same adoption path as `unknown-burn`, drill D-7). This also clears the false `unlock-prior-unknown` hold described in §1: the burn is no longer `ASSIGNED`.

### 4.5 The override gate (W4-B-4) (`engine/burn.rs:1053-1208`, `hawkeye-core/src/peerauth.rs:118-126`, `cli.rs:98-146`)

1. **Plan §4.6 first**, then code: `gone_msg` v2 = `sha256d("HawkeyeMemberGone2" ‖ setId ‖ member ‖ seq u32 LE ‖ expiry u32 LE ‖ silent_since u32 LE)`, where `silent_since` is the declarer's view of the member's `lastact` when it declares (from `set_getinfo`). Add a golden vector to `crates/hawkeye-core/tests/peerauth.rs`. `GoneDeclaration` (`peers.rs:128`) gains `silent_since`; a v1 declaration (no field) is refused after the upgrade (`"re-declare with this release"`).
2. `record_gone` (`:1135-1208`) refuses a declaration whose `silent_since` is not the member's current `lastact` on this node (the declarer must have seen the latest heartbeat) and stores `silent_since` instead of the receiver's tip; `gone_counts` (`:1113-1117`) voids a declaration once `member.lastact > silent_since` (the heartbeat rule, now bound to what the declarer signed, so a late delivery no longer counts from its arrival).
3. The override applies to a member only when `tip ≥ member.lastact + heartbeat_blocks + takeover` (it has missed at least one heartbeat by a takeover's slack) — not merely when it did not answer this round (`:787-791`).
4. `gone_quorum` (`:1053-1055`): refuse the override when `n_current < 3` (`declared_gone` returns nothing; `declare-leader-gone` prints `"a set of <n> current members cannot use the override: remove the member on chain (SET_REMOVE)"`).
5. Runbook §9 "A permanently gone member" (`docs/operations.md:346-372`): the heartbeat condition, the two-member exception, and "land and deploy the W3-B-1 duplicate classification on every attestor before using the override on mainnet" (an override is exactly how a live leader's correct unlock gets duplicated).

### 4.6 Plan and drill edits

- Plan §2.3 row 2 (`:239`): "… or the wrong value or recipient, or a burn already consumed — **unless it pays the burn's amount to the burn's recipient and its signer was the burn's leader or a scheduled taker (§5.2) and did not sign the consuming intent: such a duplicate is cancelled, never slashed (W3-B-1)**".
- Plan §5.2 (`:567-573`): define *scheduled taker* (the §4.2 step 3 set, with its one-step slack); state that the benign window now concerns only unscheduled correct duplicates; record what was given up (§3).
- Plan §5.1 (`:544-565`): the burn re-link edge on a late cancel (05/N-1).
- Plan §4.6: `gone_msg` v2 (W4-B-4).
- Plan §8 D-3 (`:758`): "double release by a member that was **not** the burn's leader or taker (unsolicited) → cancelled; slashed". `devnet/hawkeye-devnet` `drill_double` (`:2821`): choose as replayer a member that is neither the burn's leader nor any scheduled taker at replay time and assert `unmatched:consumed-burn`; add drill D-3b (`scenario double-scheduled`): force a duplicate by the scheduled taker through the override path (stop the leader's API only, keep its node and heartbeats running; declare it gone by quorum after a missed heartbeat; the taker signs a fresh vault; release the leader's withheld unlock) and assert `duplicate-burn:scheduled`, no case, no vote. Re-record transcripts on both node lines; `devnet/README.md:310` row for `double` and a row for `double-scheduled`.

## 5. Tests

`crates/hawkeye-core` (`matcher.rs` unit tests):
- `duplicate_correct_is_duplicate_burn` — consumed burn, right value and recipient → `DuplicateBurn`, `!slashable()`.
- `consumed_wrong_recipient_inside_takeover_is_fraud` — consumed burn, wrong recipient, `|Δfirst_seen| ≤ takeover` → `WrongRecipient` (was `ConsumedBurn{benign_race:true}`). Same for wrong value.
- `crates/hawkeye-core/tests/peerauth.rs`: golden vector for `gone_msg` v2.

`crates/hawkeye/tests/engine.rs` (shared mock node, anvil, `HAWKEYE_REQUIRE_ANVIL=1`; templates `f2_benign_race_cancelled_never_slashed` `:1428`, `f_slash_votes_verified_independently` `:1261`, `s2_declared_gone_by_a_quorum_releases_the_hold` `:5479`, `with_one_down` `:5402`; assert burn state and mined chain, not only `unlocks_for`, which reads the mempool only, `:1939`):
- `f4_override_on_a_live_leader_duplicate_not_slashed` — the replacement for the wave-3 `f4`, which cannot reproduce at `f4436df` (the taker now holds on the leader's `held` answer): leader L posts A; A is withheld from taker M's mempool (drop it before M's tick, as `:1649` does); L's **API** is down (`with_one_down`) but its node keeps heartbeating; a quorum declares L gone; with today's rules M signs B after the override. Mine B, then re-insert and mine A. Assert on every engine: the later one is `unmatched:duplicate-burn:scheduled`, cancelled, **no** slash case; `verify_and_sign` with a hand-built bundle against M (and against L) is refused with the W3-B-1 message; `duplicate-unlock` raised then cleared. With §4.5 also applied, assert instead that the override does **not** apply before L misses a heartbeat (the burn stays held, no B) — keep both assertions behind the two halves of the change so each half is proven. Fails at `f4436df` (case opened against the later signer).
- `f5_unscheduled_correct_duplicate_still_slashed` — the D-3 shape: a member that was never leader or scheduled taker posts a correct duplicate `> takeover` later → `consumed-burn`, case opened, peers vote.
- `f6_self_duplicate_slashed` — one key signs two vaults for one burn (drill origin, `rogue-unlock --replay-burn`, `allow_double`, `signonce.rs:784-792`) → `duplicate-burn:self`, slashable inside the benign window too.
- `f7_old_consumed_burn_case_expires_after_upgrade` — a `consumed-burn` case with the old code against a scheduled taker: the new binary moves it to `EXPIRED` with the W3-B-1 detail; no vote.
- `n1_late_cancel_relinks_released_burn` (05/N-1) — A linked on engine 2, B released (mature `delay`), A's cancel mined after B's release: the burn ends `RELEASED` re-linked to B on every engine; no `unlock-prior-unknown` alarm; no third unlock mined or in the mempool after `3 × takeover`. Fails at `f4436df` (burn `ASSIGNED`, held, alarm raised) — the first test of 05/N-1's current behaviour (wave 4: "no test of 05/N-1's new hold").
- `n1_late_cancel_relinks_matched_burn` — the same with B mined, not matured.
- `w4b4_late_declaration_does_not_count_past_a_heartbeat` — a declaration signed before L's heartbeat and delivered after it is void; `w4b4_override_refused_in_a_two_member_set`; `w4b4_v1_declaration_refused`.
- `engine_near.rs`: the `f4` shape on the NEAR adapter (memo `HKN1`).

Devnet (both node lines): `scenario double` (revised) and `scenario double-scheduled`. No golden change other than the new `gone_msg` v2 vector.

## 6. Acceptance criteria

1. A correct duplicate whose signer was the burn's leader or a scheduled taker on a ledger is cancelled and never opens a case there, and that ledger never votes for it, whatever the first-seen gap (`f4_*`).
2. An unsolicited correct duplicate and any self-duplicate remain slashable (`f5`, `f6`); a wrong-value or wrong-recipient intent is slashable inside the benign window.
3. A late cancel never reassigns (or holds) a burn another intent already paid (`n1_*`).
4. The override applies only to a member that missed a heartbeat by a takeover's slack, never in a set of fewer than three current members, and counts declarations from the height the declarer signed (`w4b4_*`).
5. Plan §2.3, §4.6, §5.1, §5.2, §8 and `docs/operations.md` §9 updated in the same branch; `tests/alarm_table.rs` passes; drills D-3 and D-3b pass on `ycash-dd` and `ycash6` (`hawkeye/CLAUDE.md` rule 5).
6. `cargo test --workspace --all-features --locked` with `HAWKEYE_REQUIRE_ANVIL=1` green; clippy, fmt clean.

## 7. Risks and side effects

- **Mixed-version sets.** An old peer still opens `consumed-burn` cases and votes on them, and still sends v1 declarations. Upgrade every attestor before re-enabling `auto_slash` anywhere and before any override; nothing is deployed on mainnet.
- **Role divergence.** Voters with different live lists may disagree on "scheduled"; the slack and the dual list narrow it; the operator gate (`MEDIUM-W3-B-2`) is the backstop. Runbook §10a: "before approving a FRAUDULENT_INTENT vote on a duplicate, check `/burns/<nonce>` on the accused's API, the takeover history and any `declare-leader-gone` in the last `10 × TAKEOVER`".
- **Override availability.** Two-member sets lose the override; the heartbeat condition delays it by up to `heartbeat_blocks + takeover` after a real loss.
- **Ledger.** No migration: new classification codes are strings; `gone/` values gain a field.
- **Bridge downtime / key rotation / contract redeploy:** none.

## 8. Effort estimate and dependencies

4 days: matcher and engine 1.5, re-link 0.5, override gate 0.5, tests 1, plan/runbook/drills 0.5–1 (devnet transcripts on both lines). Land with `MEDIUM-W3-B-2-05-N-2-hawkeye-slash-sign-honours-auto-slash` (operator approval of votes; together they make an honest member's bond safe even when one of them is wrong) and after `HIGH-W4-B-2-hawkeye-departed-signer-unlock-pins-vault` (its currency-enforcing mock is used by `f4`; it also closes residual path (2)). `MEDIUM-W4-B-1-hawkeye-held-veto-restored-answer-hwm-integrity` depends on this report's "unscheduled correct duplicate ⇒ slashable" rule. No dependency on the wyec reports.

## Completion record

- **Completed:** 2026-10-18
- **Merged:** hawkeye `#24` `cb2f391` (correct-duplicate classification, late-cancel re-link, gone-declaration v2, and the missed-heartbeat override). Plan §2.3, §4.6, §5.1, §5.2, §8 and `docs/operations.md` §9 landed in that merge.
- **Drills:** `scenario double` (D-3) and `scenario double-scheduled` (D-3b) passed on ycash-dd and ycash6, on Ethereum and on NEAR. Hawkeye devnet-e2e run `39104674607` at `6921ab7` (pull request `#25`). D-3: an attestor who did not lead the burn is cancelled and slashed as `unmatched:consumed-burn`. D-3b: after the leader's `lastact` settles and the missed-heartbeat slack passes, the other attestors declare it gone, the scheduled taker releases the burn, and the leader's duplicate is cancelled as `unmatched:consumed-burn:scheduled` with no slash case.
- **CI:** hawkeye `ci` run `39104674605` on the same commit (`cargo test --workspace --all-features --locked`, `HAWKEYE_REQUIRE_ANVIL=1`).
