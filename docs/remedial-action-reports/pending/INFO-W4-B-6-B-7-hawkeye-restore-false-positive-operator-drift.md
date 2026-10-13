# INFO — W4-B-6, W4-B-7, 02/V-N4 — Wallet-mode restore false positive after a crash; stale override help text, unpruned restore/declaration keys, a per-tick lineage scan, the burn-0 probe; test helpers that read only the mempool

Repos / branches to change: `hawkeye` (`fix/W4-B-6-B-7-operator-drift` off `upgrade/vault`: `crates/hawkeye/src/main.rs`, `engine/roll.rs`, `engine/burn.rs` (`gone_counts` housekeeping), `restore.rs` (one log line), `crates/hawkeye/tests/engine.rs` (helper), `docs/operations.md` §9, `README.md` "Build and try it"). No wyec change. No node change. · Audit source: `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` §W4-B-6 (`:259-267`), §W4-B-7 (`:269-281`), "Test fidelity" (`:285-316`); `docs/audits/quantum-vault-ecosystem-wave4/verification/02-verification.md` §W4-B-6 (`:191-195`), §W4-B-7 (`:197-203`), new finding V-N4 (`:212`) and the probe caveat (`:28-31`); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md` Info row. · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13). · Status: pending

None of these is a vulnerability: one fail-safe false positive to document, operator-facing text that contradicts the code, bounded but never-pruned ledger keys, and a test-helper trap that already misled one verifier run. Grouped as one small change. The `unlock-prior-unknown` "(previous leaders" label (W4-B-7, second bullet) is fixed in `MEDIUM-W4-B-1-hawkeye-held-veto-restored-answer-hwm-integrity` §4.3, because that report rewrites the same alarm; W3-B-13's own wording correction (part of V-N4) is recorded in `INFO-W3-B-12-B-13-05-N-4-bridge-contract-notes-test-fidelity`.

## 1. Finding

**W4-B-6 (Info).** In `"wallet"` mode Hawkeye signs inside its sign-once closure (`crates/hawkeye/src/engine/sign.rs:119-133`, called from `sign_once_unlock`); the node writes its own `set-sign-once` record before it returns (`ycash-dd src/rpc/vault.cpp:1690-1692`, `WriteVaultSetSig`), and Hawkeye commits its SQLite row only after the call returns. A crash (or `kill -9`) between the two leaves a node record without a ledger row, which `restore::detect` reads as a restore (`restore.rs:75-104`: any node record of the set with no ledger row ⇒ "restored"). On restart the member is flagged restored, answers `held/restored` for every burn (`api.rs:160-168`), and `check_restore` marks the vault a restored orphan (`restore.rs:135-147`), until the operator runs `acknowledge-ledger-restore`. Fail-safe (it signs nothing extra); by reading, not tested. The operator sees "the ledger was restored" when it was not.

**W4-B-7 (Info).**
- `crates/hawkeye/src/main.rs:79-81` — `declare-leader-gone` help: "once at least `unlockThreshold` distinct current members other than it have declared it gone". The code requires the strict-majority quorum `max(k, floor((n − 1)/2) + 1)` (`engine/burn.rs:1048-1055`, `9f47bf0`; `docs/operations.md:358-362` says so correctly).
- `engine/roll.rs:444` — every tick runs `restore_lineage_contains` (a full scan, `:155-212`, over every recorded root, the `Released`/`Matched` intents and the live vaults) only to refresh lineage keys; `restore_rolled/` and `restore_lineage/` keys (`roll.rs:89-92`, written at `:200`, `:303`) are never pruned. Bounded by the report caps (`MAX_RESTORE_REPORT` 64 / `RESTORE_UNCORROBORATED_CAP` 4 per reporter per `RESTORE_WINDOW` 4,032 blocks, `roll.rs:77-84`) but grows for ever.
- `engine/burn.rs:1093-1121` — expired `gone/` declarations are ignored by `gone_counts` but deleted only when the member answers (`:734-741`); bounded by members².
- `engine/roll.rs:102-150`, `:127` — `reporter_says_restored` probes `POST /burns/unlock` for burn nonce 0 to read the `restored` flag; harmless, but a real burn 0's bytes may be returned to a probe that discards them.

**02/V-N4 (Info).** (1) W3-B-13's wave-4 status ("worse in scope: the gate *now also* hides the engine suite") is inaccurate: at `b0f085f` the same `on_path("anvil")` gate already covered the engine suite (46 tests); only the count grew (72 now, `tests/engine.rs:201-212`). CI (`.github/workflows/ci.yml:97-110`) and `make test` (`Makefile:5-19`) enforce anvil, so CI is sound. (2) A probe-writing hazard: the test helper `unlocks_for` (`tests/engine.rs:1939-1961`) lists **mempool** transactions only, so "posted = 0" does not prove a hold — a mined payout also reads 0 (the verifier's first `v02` run did exactly that). Several existing tests assert `unlocks_for(..).is_empty()` as "held" (`:5182`, `:5211`, `:5448`, `:5691`) and would pass on a burn that was in fact paid and mined.

## 2. Root cause

- `engine/sign.rs:119-133` + `ycash-dd src/rpc/vault.cpp:1679-1693` (record before return) + `restore.rs:75-104` (any unmatched node record ⇒ restored): no way to tell "the node signed and Hawkeye crashed before committing" from "the ledger is older than the wallet".
- `main.rs:76-92` doc comment not updated with `9f47bf0`.
- `roll.rs:444` (per-tick call), `:155-212`, `:89-92`; `burn.rs:1093-1121`; `roll.rs:127`.
- `tests/engine.rs:1939-1961` (`unlocks_for` filters `st.mempool`).

## 3. Fix options considered

| Item | Option | Verdict |
|---|---|---|
| W4-B-6 | Detect the crash case: when `detect`'s only unmatched node records are for prevouts whose **unsigned build** this ledger holds as the latest remembered build (or for which `signing_started/<prevout>` was written before the RPC call), report "possibly an interrupted signature" instead of "restored" | Rejected for now: a pre-call marker is a second write per signature for a fail-safe case; and a ledger *is* missing a record — the operator should look. |
| W4-B-6 | Document it in the `ledger-restored` alarm row and the restore log line | **Chosen** (the audit's fix). |
| W4-B-7 | Correct the help text; prune expired `gone/` keys and `restore_rolled/`/`restore_lineage/` keys older than `RESTORE_WINDOW` whose vault and successors are spent `C_Y` deep; run the lineage refresh every 20 ticks (with `check_gas`); probe the `restored` flag with a dedicated nonce | **Chosen**. |
| V-N4 | Make `unlocks_for` see mined transactions too (or add `payouts_for` and assert burn state) | **Chosen**. |

## 4. Recommended fix

1. **W4-B-6.** `docs/operations.md` §9 `ledger-restored` row (`:249`): append "In `"wallet"` mode a crash between the node's signature and the ledger's commit produces the same alarm (the node holds a record the ledger lacks): `hawkeye audit-ledger` lists the vault; if this host never ran from a backup, `acknowledge-ledger-restore` after checking that the vault's unlock is the one in the node wallet's `set_listsigned`." `restore.rs:96-99`: add to the `detect` reason "(or a crash between the node's signature and the ledger's commit)". Coordinate the row with `MEDIUM-W4-B-1-hawkeye-held-veto-restored-answer-hwm-integrity` §4.6 (same row).
2. **Help text.** `main.rs:79-81`: "once a strict majority of the current members other than it — and never fewer than `unlockThreshold` — have declared it gone (`max(k, floor((n − 1)/2) + 1)`)".
3. **Housekeeping.** In `roll.rs` `orphans()` (`:420-470`): call the lineage refresh every 20 ticks only (`self.mem.ticks.is_multiple_of(20)`, as `check_gas` does, `engine/mod.rs:588`); delete `restore_rolled/<vault>` and `restore_lineage/<vault>` once the vault and every recorded successor are spent `C_Y` deep and the key is older than `RESTORE_WINDOW`. In `gone_counts`' caller (`declared_gone`, `burn.rs:1062-1075`), delete declarations whose `expiry < tip` in the same transaction (one `delete_meta_prefix` per expired key).
4. **Burn-0 probe.** `roll.rs:127`: probe with `nonce = u64::MAX` (never a real burn nonce on Ethereum within any horizon) and ignore `unlock` in the answer; document in `BurnUnlockRequest` that `u64::MAX` is the "restored-flag only" probe.
5. **V-N4.** `tests/engine.rs`: rename the helper `mempool_unlocks_for` and add `unlocks_for` that scans the mock's mined blocks as well (`MockState` keeps them); replace every "held" assertion that uses it with an assertion on burn state (`burn_view`, `:3311`) plus "no unlock of the burn mined or in the mempool". `README.md` "Build and try it": one line that `cargo test` without anvil passes the engine and Ethereum suites vacuously (they print `SKIPPED`); use `make test`.

## 5. Tests

- `w4b6_wallet_mode_crash_after_node_sign_is_reported` — mock wallet mode: make the sign-once closure fail after `set_signunlock` returns (a test hook that returns `Err` from the closure, so SQLite rolls back with the node record written): restart → `ledger-restored` raised with the new reason text; `audit-ledger` lists the vault.
- `w4b7_expired_declarations_are_pruned` and `w4b7_restore_keys_pruned_after_window` (extend `v3_old_restore_reports_are_pruned`, `tests/engine.rs:6274`).
- `w4b7_heartbeat_voids_a_declaration` — the gap the audit lists ("no test that a heartbeat voids a declaration", `02-hawkeye-recheck-and-delta.md:305`): a quorum declares member L gone, L heartbeats (`set_heartbeat` on the mock), the override no longer applies (`declared_gone` empty), a new declaration after the heartbeat applies again.
- The re-pointed "held" assertions (`:5182`, `:5211`, `:5448`, `:5691`) pass with the mined-aware helper.
- `main.rs` has no test for help text; review only.

## 6. Acceptance criteria

1. The `ledger-restored` alarm row and log reason mention the wallet-mode crash case.
2. CLI help, runbook and code agree on the override quorum.
3. Expired `gone/` keys and old restore keys are pruned; the lineage scan no longer runs every tick.
4. No engine test treats "nothing in the mempool" as "held"; a heartbeat-voids-declaration test exists.

## 7. Risks and side effects

None material. Pruning deletes only keys that no rule reads any more (expired, or about spent vaults `C_Y` deep). The probe nonce change is wire-compatible (older peers answer an unknown burn). Bridge downtime / key rotation / contract redeploy: none.

## 8. Effort estimate and dependencies

0.5–1 day. Land after `MEDIUM-W4-B-1-hawkeye-held-veto-restored-answer-hwm-integrity` (shared alarm row and alarm text) and after `MEDIUM-W3-B-1-05-N-1-W4-B-4-hawkeye-correct-duplicate-unlock-not-slashable` (its §4.5 rewrites `record_gone`/`gone_counts` with `silent_since`; this report's pruning of expired `gone/` keys and its `w4b7_heartbeat_voids_a_declaration` test must use that rule). This report owns the README "`cargo test` without anvil passes vacuously" line (INFO-W3-B-12 points here). Independent of the wyec reports.
