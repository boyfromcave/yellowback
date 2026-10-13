# LOW — 05/L-4 — One guardian can veto every honest proposer for a lock; the threshold fallback is not automated

Repos / branches to change: `hawkeye` (`fix/05-L-4-threshold-fallback` off `upgrade/vault`); `wyec`: no change (documented behaviour; an optional note in `wyec-contract-design.md` §4.5.2). No node change. · Audit source: `05-bridge-hawkeye-wyec.md` §L-4 (`:246-253`); `verification/05-verification.md` row L-4 (`:23`); `00-consolidated.md` row 05/L-1..L-5. · Status: done — completed 2026-10-13T06:11Z (merged locally on `upgrade/vault`; not yet pushed)

## 1. Finding

`challengeMint` (`wyec/contracts/WyecBridge.sol:243-251`) deletes the proposal on **any** current guardian's `Challenge` signature and marks the proposer `vetoed[lockId][proposer] = true` for good (`:110, 248`). This is the intended answer to signature replay (design §4.5.2 "Replaying a challenged proposer's public Mint signature"), but it lets a single rogue or faulty guardian veto honest proposers one by one: Hawkeye re-proposes with the next eligible member (`crates/hawkeye/src/engine/mint.rs:852-919`: `eligible` = live members not `vetoed`), and once every live member is barred it logs `mint_no_eligible_proposer` and waits "for a threshold mint" (`:876-882`) — which nothing automates: `mint()` in `Optimistic` mode never falls back to the `Threshold` path. The griefer is attributable (the challenger's address is in `MintChallenged`) and Hawkeye raises `matching-proposal-challenged` (`:302-310`) but opens **no** `Griefing` slash case for it (only an alarm, `:165, 278, 302`); plan §2.3 says griefing is `SET_REMOVE burn=0` by `slashThreshold`. Liveness only, no loss; but a lock can be stuck for as long as the operators take to notice and act by hand.

## 2. Root cause

- `crates/hawkeye/src/engine/mint.rs:876-882` — `mint_no_eligible_proposer`: log and return.
- `crates/hawkeye/src/engine/mint.rs` `mint()` — the mode dispatch (`MintMode::Optimistic` → `propose`/`execute`; `MintMode::Threshold { k }` → gather `k` signatures over `GET /locks/<id>` and `threshold_mint`); the optimistic branch has no path into the threshold machinery.
- `crates/hawkeye/src/engine/mint.rs:165, 278, 302-310` — `griefed` → alarm only; no `NewSlashCase { fault: FaultKind::Griefing, … }`.
- `wyec/contracts/WyecBridge.sol:243-251` — by design (HK-11/design §4.5.2); the threshold path (`mint`, `:202-207`) "overrides at once" and is the documented fallback.

## 3. Fix options considered

- Contract-side `clearVeto` under threshold: adds an admin act, a struct, vectors and a governance round to do what `mint` already does. Rejected.
- Rate-limit challenges per guardian in the contract: breaks the "any one honest guardian stops any fraud" property. Rejected.
- Hawkeye automates the threshold fallback and opens the griefing case. **Chosen** — the design doc already names it; it is pure sidecar logic.

## 4. Recommended fix

1. **Fallback** (`engine/mint.rs`): extract the threshold-mode gathering into `async fn threshold_mint_for(&mut self, l: &LockRecord, to: &Account, k: u8) -> Result<()>` (its body is the existing `Threshold { k }` branch: own `Mint` signature from `sign_once_mint`, peers' from `GET /locks/<id>`, verify each recovers to a distinct current guardian — this already exists for threshold mode — then `foreign.threshold_mint(lock_id, amount, to, sigs)`). In `propose`, when `mint_leader_for(&l.lock_id, &eligible, …)` is `None` (`:876`): if `self.ctx.params.mainnet` or `[bridge] fallback_to_threshold = true` (default true), call `threshold_mint_for(l, to, contract_threshold)` with `contract_threshold = foreign.threshold()` (not `mint_threshold`, which is the config for threshold mode). The submitter is the mint leader over **all** live members for that lock (`mint_leader_for(&l.lock_id, self.live(), since, takeover)`), so one attestor submits and takeover covers it; log `event = "mint_threshold_fallback"` with the barred set. Peers answer `GET /locks/<id>` with their stored `Mint` signature only when their ledger has the lock `Signed`/`Proposed`/`Challenged` with the same `(amount, to)` — already the case (`api.rs:50-78` returns `mint_signature`).
2. **Griefing case** (`scan_eth`, `:302-310`): for each `griefed (lock_id, proposal_id, by)` where `by` recovers to a current member key (`members.iter().find(|k| guardian_of(k) == by)`) and `by != me`, `open_slash_case(NewSlashCase { target_key, fault: FaultKind::Griefing, subject: lock_id ‖ proposal_id, evidence_json: { "fault": "GRIEFING", "lock_id", "proposal_id", "challenger", "challenge_tx", "lock_state", "amount", "to" }, opened_height })`; `slash.rs::verify_evidence` (`:167-179`) gains `FaultKind::Griefing` → `verify_griefing`: the challenged proposal must match a lock that is policy-OK **on the verifier's own ledger** with the same `(amount, to)` (so a challenge of a proposal the verifier itself would have challenged is *not* griefing — the verifier refuses to vote), and the `MintChallenged` log must be final on the verifier's foreign view. `auto_slash` governs submission as for the other faults (manual on mainnet, `config.rs:719`); the act is `SET_REMOVE burn=0` (`verify_and_sign` already checks `burn == (fault != Griefing)`, `slash.rs:437-440`).
3. **Second strike**: a proposer vetoed on **two** locks by the same challenger within `2 × takeover` blocks is strong evidence; still one case per `(challenger, lock)` — cases are per fault per subject (`slash_cases` uniqueness, `schema.rs:145`); the runbook's incident playbook (`MEDIUM-05-M-3` §10) says when to vote.
4. **Docs**: `wyec-contract-design.md` §4.5.2 last row: "Hawkeye falls back to the threshold path automatically once every live proposer is vetoed and opens a `GRIEFING` case against the challenger." Plan §5.3 step list and §12 **HK-15**.

## 5. Tests

- `tests/engine.rs` `t_all_proposers_vetoed_falls_back_to_threshold`: 3 engines, optimistic, threshold 2; engine 2 is the griefer (test helper submits `challengeMint` with engine 2's key for each honest proposal); after engines 0 and 1 are vetoed, the lock is minted by `mint` with 2 signatures (engine 0 + engine 1's over `GET /locks`), `Minted` observed; a `GRIEFING` case against engine 2 is open on engines 0 and 1 with the challenge tx as evidence; engine 2's own ledger opens none against itself.
- `t2_griefing_vote_refused_for_a_fraudulent_proposal`: the challenged proposal had no lock on the verifier → `verify_evidence` refuses (`"not griefing here: the proposal does not match a policy-OK lock"`).
- `t3_threshold_fallback_respects_signing_pause`: with `guardian-drift` on mainnet semantics the fallback does not submit (reuses `signing_paused`).
- Existing `m_challenged_matching_proposal_is_reproposed_by_another` (`:1840`) unchanged.

## 6. Acceptance criteria

1. A lock whose every live proposer is vetoed is minted by the threshold path within one takeover period without operator action (devnet scenario).
2. The griefer has a `GRIEFING` case with verifiable evidence on every honest attestor; honest challenges never produce one.
3. `signing_paused` gates the fallback like every other submission.

## 7. Risks and side effects

- The fallback uses the contract's threshold, i.e. a quorum signs a mint at once; the lock was policy-OK on `k` attestors (each signed its own `Mint` only after its own policy check: `signonce.rs:175-191`), so this is the design's "quorum, immediate" override, not a weakening.
- Gas: one `mint` (~110k) per griefed lock instead of a proposal — borne by the submitter (`MEDIUM-05-M-1` gas key).
- No contract change, no redeploy, no key rotation, no downtime.

## 8. Effort estimate and dependencies

1.5 days. Benefits from `HIGH-05-H-1` (authenticated `/slash/sign` for the griefing vote) but does not depend on it.

## Completion record

- **Completed:** 2026-10-13T06:11Z
- **hawkeye** `upgrade/vault` merge f693026 (branch `fix/bridge-misc`): d60e935 (automatic threshold fallback once every proposer is barred, `[bridge] fallback_to_threshold`; GRIEFING cases against the challenger of a matching proposal, verified by peers), 957a076 (plan §2.3, §3.3, §5.3, HK-15). **wyec** merge aef923c: 2ab9b6c (design-doc note, §4.2 and §4.5.2).
- **Tests:** 301 passed at 957a076. New: `t_all_proposers_vetoed_falls_back_to_threshold`, `t3_threshold_fallback_respects_signing_pause`, and `n_` asserting that an honest challenge opens no case. §6 criteria 1–3 met; criterion 1 is met on anvil, not on the devnet.
- **Beyond the report:** a member with a recorded GRIEFING case for a lock is also barred from proposing for that lock. Without this, a griefer that never proposes would stay eligible and the fallback would never fire.
- **Open:** the devnet run of the §6.1 scenario.
