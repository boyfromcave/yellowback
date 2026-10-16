# MEDIUM — W3-B-2, 05/N-2 — `POST /slash/sign` votes without the operator when `auto_slash = false`; there is no command to vote on one reviewed case

Repos / branches to change: `hawkeye` (`fix/W3-B-2-slash-approval` off `upgrade/vault`: `engine/slash.rs`, `api.rs`, `peers.rs`, `cli.rs` + `main.rs`, `hawkeye-store` schema (one migration), `status.rs`, `docs/operations.md`, plan §5.3). No wyec change. No node change. · Audit source: `docs/audits/quantum-vault-ecosystem-wave3/05-bridge-hawkeye-wyec.md` §W3-B-2 (`:108-123`); `docs/audits/quantum-vault-ecosystem-wave3/verification/05-verification.md` §W3-B-2 (`:155-164`), new finding N-2 (Info, `:304-311`); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row W3-B-2, priority 4 ("make `/slash/sign` honour `auto_slash` and add a vote command"); `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` status rows W3-B-2 and 05/N-2 (`:51`, `:64`, both **STILL OPEN**) and "Remedial reports that are now stale" (`:88-90`: still valid; the new `declare-leader-gone` override is a second operator act that fans out to peers); `docs/audits/quantum-vault-ecosystem-wave4/verification/02-verification.md` status row (`:42`, confirmed: `slash.rs:530` never reads `auto_slash`, only `:650`; no `slash` subcommand). · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13): `engine/slash.rs`, `config.rs`, `hawkeye-store/src/schema.rs` and `slash.rs` are byte-unchanged since `b0f085f`; `api.rs`, `cli.rs`, `main.rs`, `peers.rs`, `daemon.rs` and the runbook moved (lines below are at `f4436df`). · Status: done — completed 2026-10-16 (merged on `upgrade/vault`; see the completion record). Previously pending

## 1. Finding

The runbook promises that on mainnet a slash vote is a human decision: `docs/operations.md:242` (alarm `slash-case-<id>`: "a slash case waits for this operator (`auto_slash = false`, the mainnet default)"), `:404-405` ("On mainnet the slash vote is manual (`auto_slash = false`): verify, then vote"), and plan §5.3 step 3 ("`auto_slash = true|false` per operator (default false on mainnet: an operator confirms)"). The code implements that gate only for cases this attestor **owns**: the case loop raises the alarm and `continue`s when `!auto_slash` (`crates/hawkeye/src/engine/slash.rs:650-658`). The peer route does not look at the flag: `POST /slash/sign` → `api.rs:201-218` → `verify_and_sign` (`slash.rs:530-577`) runs the repeat check, `decode_remove`, `verify_evidence`, the own-removal and consistency checks, and then `sign_act` at once. So one member with `auto_slash = true` (or one operator who flips it) drives a case and collects `slashThreshold − 1` act signatures from peers whose operators never saw it. Any verdict defect (W3-B-1 is one: an honest leader's or taker's correct duplicate) then removes an honest member and burns its bond with a single human in the loop.

N-2 (Info) is the other half: there is no way to "vote" on one reviewed case. `hawkeye` has no slash subcommand (`main.rs:24-202`, the `Command` enum; `cli.rs` only lists cases in `status`), and the case loop drives nothing while `auto_slash = false`. The only way to act on the runbook's "verify, then vote" is to set `auto_slash = true` and restart, which drives **every** open case this attestor owns, reviewed or not, and keeps auto-voting on every peer request until the flag is flipped back.

## 2. Root cause

- `crates/hawkeye/src/engine/slash.rs:530-577` — `verify_and_sign`: no read of `ctx.params.auto_slash`, no notion of an operator decision.
- `crates/hawkeye/src/engine/slash.rs:650-658` — the only consumer of `auto_slash`; a binary gate with no per-case override.
- `crates/hawkeye/src/api.rs:201-218` — the handler maps every error to `403`, so a "waiting for my operator" answer is indistinguishable from a refusal.
- `crates/hawkeye/src/config.rs:885` — `auto_slash` defaults to `!mainnet`; `config/ethereum-mainnet.example.toml:52` sets `false`.
- `crates/hawkeye-store/src/schema.rs:150-168, 226-252` — `slash_cases`, `slash_votes`, `slash_votes_given`; nothing records an operator decision.
- `docs/operations.md:242, 404-405` — the promise; `main.rs` / `cli.rs` — no command to keep it.

## 3. Fix options considered

| Option | Verdict |
|---|---|
| (a) Document that the mainnet default is "auto-vote on independently verified evidence" and drop the contrary wording | Rejected for mainnet: the independent verification is exactly what W3-B-1 showed can be uniformly wrong on every honest ledger; the human gate is the only defence against a shared verdict bug, and a slash is irreversible. Kept as the meaning of `auto_slash = true`. |
| (b) `/slash/sign` refuses outright when `!auto_slash` | Makes slashing impossible on a mainnet set that follows the runbook (nobody's peer would ever co-sign). Rejected. |
| (c) `/slash/sign` records the request as a case awaiting **this** operator's decision, answers "pending", and signs once the operator approves that case; an explicit `hawkeye slash approve|reject <case>` command drives one case once | **Chosen.** Per-case, persistent, auditable, no restart, and the approval never bypasses `verify_evidence` (it is re-run at signing time). |
| (d) Interactive approval over the API (an operator endpoint) | Rejected: a new authenticated operator surface on a service exposed to peers; the CLI on the host, writing to the ledger as `exposure ack` already does (`cli.rs:418-430`), is enough. The same holds for `declare-leader-gone` (`cli.rs:98-146`), which already runs on the host. |

## 4. Recommended fix

### 4.1 Ledger: operator decisions (the next schema version after V9, `crates/hawkeye-store/src/schema.rs`, append to `MIGRATIONS`; `HIGH-W4-B-2-hawkeye-departed-signer-unlock-pins-vault` §4.4 also adds one — whichever lands first takes V10, the other V11; under the consolidated landing order HIGH-W4-B-2 lands first, so this is **V11**; no other pending Hawkeye report adds a migration)

```sql
-- An operator's decision on a slash case (W3-B-2): with auto_slash = false this attestor votes
-- (as case owner or for a peer) only on an approved (fault, subject, target). One decision per
-- case key, immutable.
CREATE TABLE slash_decisions (
    fault       TEXT    NOT NULL,
    subject     BLOB    NOT NULL,
    target_key  BLOB    NOT NULL CHECK (length(target_key) = 33),
    decision    TEXT    NOT NULL CHECK (decision IN ('approve', 'reject')),
    note        TEXT    NOT NULL,
    decided_at  INTEGER NOT NULL,
    PRIMARY KEY (fault, subject, target_key)
) WITHOUT ROWID;
CREATE TRIGGER slash_decisions_immutable_update BEFORE UPDATE ON slash_decisions
BEGIN SELECT RAISE(ABORT, 'slash decisions are immutable'); END;
CREATE TRIGGER slash_decisions_immutable_delete BEFORE DELETE ON slash_decisions
BEGIN SELECT RAISE(ABORT, 'slash decisions are immutable'); END;

-- Peer requests for this attestor's vote that wait for a decision (who asked, with which act).
CREATE TABLE slash_peer_requests (
    case_id     INTEGER NOT NULL REFERENCES slash_cases (id),
    requester   BLOB    NOT NULL CHECK (length(requester) = 33),
    act_hex     TEXT    NOT NULL,
    first_at    INTEGER NOT NULL,
    last_at     INTEGER NOT NULL,
    PRIMARY KEY (case_id, requester)
) WITHOUT ROWID;
```

Store API (`hawkeye-store/src/slash.rs`, beside `open_slash_case` at `:81`): `decide_slash(&CaseKey, Decision, note)`, `slash_decision(&CaseKey) -> Option<Decision>`, `note_peer_slash_request(case_id, requester, act_hex)`, `peer_slash_requests(case_id)`. Migration test in `hawkeye-store/tests/migrations.rs` (v9 → next preserves rows; the new version refuses an older binary as today).

### 4.2 `verify_and_sign` honours the flag (`engine/slash.rs:530-577`)

After every existing check (so only **verified** evidence is ever queued) and before `sign_act`:

```rust
if !ctx.params.auto_slash {
    let key = CaseKey { fault: verdict.fault, subject: verdict.subject.clone(), target: verdict.target };
    match ctx.db(|t| t.slash_decision(&key))? {
        Some(Decision::Approve) => {}                                   // fall through to sign_act
        Some(Decision::Reject) => bail!("this operator rejected the case (slash_decisions)"),
        None => {
            let (case, _) = ctx.db(|t| {
                let c = t.open_slash_case(&NewSlashCase { target_key: verdict.target, fault: verdict.fault,
                    subject: verdict.subject.clone(), evidence_json: req.evidence.to_string(),
                    opened_height: Some(tip) })?;
                t.note_peer_slash_request(c.0.id, &requester, &req.act)?;
                Ok(c)
            })?;
            return Err(SlashPending { case: case.id }.into());          // typed, see 4.3
        }
    }
}
```

`verify_and_sign` gains the verified requester (`Option<PubKey33>`, as `verify_and_sign_unlock` already takes it, `engine/burn.rs:1344`; `api.rs:206` already has it as `requester`). The local case it opens is the same row the owner's loop would open (`UNIQUE (fault, subject, target_key)`), so the operator sees one list. The case loop's alarm (`slash.rs:650-658`) then fires for it: `slash-case-<id>`, text `"<fault> against <key>: requested by <peer> — review, then `hawkeye slash approve <id>` or `reject <id>`"`.

### 4.3 The pending answer on the wire (`api.rs`, `peers.rs`)

`slash_sign` maps `SlashPending` to **`409 Conflict`** with `ApiError { error: "pending operator decision (case <id>)", pending_case: Some(id) }` (add the optional field to `ApiError`, `peers.rs:232-237`; serde default so older peers parse it). Other errors stay `403`. The response is still signed by the peer-auth layer. In `drive_case` (`slash.rs:686`; the peer loop `:731-764`) a `409` logs `slash_vote_pending` (info) instead of `slash_vote_refused`, and the peer is asked again on the next drive (the loop already retries unvoted peers). No change to `/unlock/sign`, `/cancel/sign`, `/burns/unlock`, `/vaults/orphaned` or `/members/gone`: cancels must stay automatic (the defence is time-critical, plan §5.3 step 1), and the others sign no act.

### 4.4 The case loop drives approved cases (`engine/slash.rs:650-658`)

```rust
if !self.ctx.params.auto_slash {
    match self.ctx.db(|t| t.slash_decision(&c.key()))? {
        Some(Decision::Approve) => {}                         // drive this one case
        Some(Decision::Reject) => { transition to EXPIRED, detail "operator rejected"; clear alarm; continue }
        None => { alarm as today (new text); continue }
    }
}
```

Ownership (`leader_for` over the others) is unchanged; an approval on a non-owner only lets it answer peers. An approved case is still re-verified by every voter (`verify_evidence` in `verify_and_sign`) and by the owner before `set_buildact` (add a `verify_evidence` call at the top of `drive_case` for `Opened` cases; today the owner trusts its own case record).

### 4.5 The vote command (05/N-2) (`main.rs`, `cli.rs`)

```
hawkeye slash list [--json]                 open cases: id, fault, target, opened, owner?, decision, peer requests
hawkeye slash show <id> [--json]            the evidence bundle and a fresh verify_evidence() verdict on this node and ledger (read-only)
hawkeye slash approve <id> --note <text>    record 'approve' (refused unless `show`'s verdict is "established" right now)
hawkeye slash reject <id> --note <text>     record 'reject'
```

`approve`/`reject` open the ledger with `Store::open` (SQLite serialises with the running daemon, as `exposure ack` does, `cli.rs:427`) and print `"the daemon acts on it at its next tick"`. `approve` connects (as `status` does) and re-runs `verify_evidence`; it refuses when the evidence does not verify here. `--note` is mandatory (kept in the ledger and logged as `slash_decided`).

### 4.6 Config, status, docs

- Start-up (`daemon.rs::startup_checks`, `:113`): on mainnet with `auto_slash = true`, `warn!(event = "auto_slash_on_mainnet", "every verified case and every peer request is voted without operator review")`; `hawkeye status --params` prints `auto_slash` with `manual (operator approves each case)` / `AUTOMATIC`.
- `/status` and `/metrics`: `slash_cases_awaiting_decision` count and gauge `hawkeye_slash_cases_awaiting_decision`.
- `docs/operations.md` §9 row `slash-case-<id>`: meaning "a slash case — owned here or requested by a peer — waits for this operator's decision"; action "`hawkeye slash show <id>`, verify (§10a), then `hawkeye slash approve <id> --note …` or `reject`". §10: "On mainnet the slash vote is manual: with `auto_slash = false` this attestor votes — as case owner **or for a peer** — only on a case its operator approved. `auto_slash = true` votes on any independently verified evidence." Add the commands to the §12 command table (`docs/operations.md:439-452`). Coordinate with `MEDIUM-W3-B-1-05-N-1-W4-B-4-hawkeye-correct-duplicate-unlock-not-slashable`'s §10a note on duplicates (§7 there).
- Plan §5.3 step 3 (`docs/hawkeye-bridge-plan.md:610`): the same rule, and the 409 pending answer.
- The owner override (wave 4, `02-hawkeye-recheck-and-delta.md:88-90`): a peer's `declare-leader-gone` is recorded on every ledger without that ledger's operator (`POST /members/gone` → `record_gone`, `engine/burn.rs:1135-1208`). It changes no vote and each declaration is one operator's own act, so no approval gate is added; but make it visible the same way: ticket alarm `member-declared-gone` ("member <key> declared gone by <declarer> (<reason>): <n> of <quorum> declarations") when a peer's declaration is recorded, and `hawkeye slash list` gains a sibling `hawkeye gone list` (read-only) printing the declarations this ledger counts. The override's own rules are in `MEDIUM-W3-B-1-05-N-1-W4-B-4-hawkeye-correct-duplicate-unlock-not-slashable` §4.5.

## 5. Tests

`crates/hawkeye/tests/engine.rs` (three engines on the mock node with anvil, `HAWKEYE_REQUIRE_ANVIL=1`; `f_slash_votes_verified_independently`, `:1261`, is the template):
- `w3b2_peer_request_waits_for_operator` — engine 0 `auto_slash = true` drives a case against a rogue intent (`rogue_unlock`); engine 1 `auto_slash = false`. Assert: engine 1's `verify_and_sign` returns the pending error, no `slash_votes_given` row, no `set_signact` call on its node (mock call log), a local case with a `slash_peer_requests` row, alarm `slash-case-<id>`. Then `decide_slash(approve)` on engine 1's ledger; the next drive receives engine 1's vote. **Fails at `f4436df`** (engine 1 signs at once).
- `w3b2_rejected_case_never_signed` — reject on engine 1: its answer stays a refusal; its own copy of the case goes `EXPIRED`.
- `w3b2_approval_does_not_bypass_verification` — approve, then change engine 1's ledger so the intent now matches a finalized burn: `verify_and_sign` refuses.
- `w3b2_owner_drives_only_approved_case` — two cases owned by one engine with `auto_slash = false`; approve one; only it gets `set_buildact`.
- `w3b2_decision_survives_restart` — approve, restart the engine from its ledger file, the case is driven.
- Existing `f_*`, `f3_*`, `g2_restart_resumes_slash_case_without_re_signing` unchanged with `auto_slash = true`.
- `hawkeye-store/tests/migrations.rs`: v9 → next; immutability triggers on `slash_decisions`.
- `w3b2_peer_declaration_raises_member_declared_gone` — a peer's `POST /members/gone` raises the ticket alarm on the receiver; `hawkeye gone list` prints it.
- `cli.rs` unit tests: argument parsing, `--note` required, refusal text when the verdict does not verify.
- `tests/alarm_table.rs` stays green with the reworded row.

## 6. Acceptance criteria

1. With `auto_slash = false`, no act signature leaves this attestor — through the case loop or through `/slash/sign` — for a case its operator has not approved (`w3b2_peer_request_waits_for_operator`).
2. An operator can approve or reject exactly one case without a restart and without changing `auto_slash`; the decision is persistent, immutable and logged.
3. `auto_slash = true` behaves exactly as at `f4436df`.
4. `docs/operations.md` §9/§10/§12 and plan §5.3 describe the behaviour; the alarm table test passes (with `member-declared-gone`).

## 7. Risks and side effects

- **Slashing liveness.** A real thief is removed only when `slashThreshold` operators approve within `CASE_EXPIRY_BLOCKS = 2_880` (`slash.rs:37`, ≈ 60 h at 75 s). `slash-case-*` is already a page; the runbook should name a response time. A member in its bond exit delay stays slashable for the set's maturity (≥ 16,128 blocks), far beyond the case expiry, so a lapsed case can be re-opened from fresh evidence.
- **Mixed versions.** An old peer answers `403` instead of `409`; the owner simply retries. An old peer still auto-votes on requests: upgrade all attestors before mainnet (nothing is deployed yet).
- **Bridge downtime / key rotation / contract redeploy:** none. The ledger migration is additive; take the §5 backup before upgrading, as for every schema change.

## 8. Effort estimate and dependencies

2–3 days (store 0.5, engine/API 1, CLI 0.5, tests and docs 1). Independent of the wyec reports. Lands with or before `MEDIUM-W3-B-1-05-N-1-W4-B-4-hawkeye-correct-duplicate-unlock-not-slashable` (the two together close the honest-slash path; W3-B-1 stays schema-free). Schema version: coordinate with `HIGH-W4-B-2-hawkeye-departed-signer-unlock-pins-vault` (first to land takes V10). `LOW-W3-B-10-B-11-hawkeye-single-instance-lock-audit-blind-spots` must not take its instance lock in the `slash` / `gone list` commands.

## Completion record

- **Completed:** 2026-10-15
- **Merged:** hawkeye `#17` `ad1fc89`. With `auto_slash = false`, `POST /slash/sign` records the case and refuses until `hawkeye slash approve <id> --note`. Decisions are immutable (store migration V11, `slash_decisions`). `auto_slash = true` is unchanged.
- **Not closed by this landing:** the peer-request table, a typed 409, `slash show`, approve-time re-verification, and the `member-declared-gone` alarm. Older peers still auto-vote, so every attestor has to move before mainnet.
