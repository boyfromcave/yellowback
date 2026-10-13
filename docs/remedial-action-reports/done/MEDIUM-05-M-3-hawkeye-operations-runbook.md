# MEDIUM — 05/M-3 — Write the bridge-attestor operations runbook; fix `yellowback-attestor.md`'s contradictions

Repos / branches to change: `hawkeye` (`fix/05-M-3-operations-runbook` off `upgrade/vault`: new `docs/operations.md`, README links, devnet README cross-links); `ycash-dd` and `ycash6` (`fix/05-M-3-attestor-doc` off `upgrade/vault`, **docs only**: `doc/yellowback-attestor.md`, `doc/vault-rpc.md` sign-once paragraph — the node-side F-5 fix itself is `07/F-5`'s report). · Audit source: `05-bridge-hawkeye-wyec.md` §M-3 (`:182-204`); `verification/05-verification.md` row M-3 (`:18`); `00-consolidated.md` rows 05/M-3, 07/F-5, recommendation R7. · Status: done — completed 2026-10-13T11:21Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13; nightly tier pending the owner's dispatch)

## 1. Finding

There is no document that tells a bridge-attestor operator what the software assumes of them. The equivocation guards are *per machine*: the node wallet's `vaultsetsig` record (`ycash-dd/doc/vault-rpc.md:300-305`; `src/rpc/vault.cpp:1463-1475`, written only to the local `wallet.dat`, `walletdb.cpp:1498-1507`) and Hawkeye's SQLite ledger (`crates/hawkeye-store/src/signonce.rs`). A hot-standby node restored from a `wallet.dat` backup, or a second Hawkeye pointed at a second node, can sign a second unlock of the same vault → `SET_EQUIVOCATION` → ejection and a frozen bond (plan §2.3 row 1), and for the bridge two conflicting intents. Nothing tells the operator this. Guardian rotation has two halves (`setGuardians` on Ethereum, `set_leave`/`set_join` on Ycash) with no ordering guidance, and between them `guardian_mismatch` pauses signing on mainnet (`crates/hawkeye/src/engine/mod.rs:514-517`, `daemon.rs:101-106`), so a careless round pauses the whole set. Hawkeye's README stops at "rotate the guardian in the same governance round" (`README.md:63-65`).

The node document that exists, `ycash-dd/doc/yellowback-attestor.md`, is the **YED price attestor** guide (`yed_signattestation`, `attest-signed.dat`, iroh gossip — none used by Hawkeye) and contradicts itself: the "Since the vault upgrade" block (`:18-66`) says "the bond key cannot be kept cold any more" (`:27-31`) while "Bond key hygiene" (`:154-181`) still instructs moving it cold, and the quick reference still lists `yed_withdrawbond` beside `set_leave`. A bridge operator who finds it will follow the wrong half.

## 2. Root cause

- `hawkeye/README.md:47-93` — joining/leaving, commands, node requirement; no custody, backup, single-instance, rotation-order or monitoring sections. `hawkeye/docs/` holds the two plans only.
- `hawkeye-bridge-plan.md:608-614` (§6 "Operations") lists metrics and the status API, and §9 H5 promises "operator guide, runbooks" under `docs/` that were never written.
- `ycash-dd/doc/yellowback-attestor.md:18-31` vs `:154-181` and the quick reference; identical file on `ycash6/doc/`.
- `ycash-dd/doc/vault-rpc.md:300-305` — "across restarts" says nothing about restores or second hosts (07/F-5).

## 3. Fix options considered

- Extend the README only: rejected — the README is the project card; a runbook is a checklist operators print.
- One shared "attestor" doc for YED and the bridge: rejected — different software, different keys, different failure modes; the audit's I-2 shows how a shared file drifts.
- Chosen: `hawkeye/docs/operations.md` (normative for bridge attestors), README links to it, `yellowback-attestor.md` retitled and corrected, `vault-rpc.md` sign-once paragraph extended.

## 4. Recommended fix

### 4.1 `hawkeye/docs/operations.md` — outline (write every section; headings are the deliverable)

1. **What you are running and what it can lose.** One member key = Ycash set signature + bond + Ethereum guardian signature (+ gas until `MEDIUM-05-M-1` lands). Table: key copy → what an attacker gets. The equivocation rule in one paragraph (two different signatures over one `(set, prevout)` by one key = ejection + frozen bond; two intents for one burn = a double release the others must cancel).
2. **The single-instance rule.** Exactly one `ycashd` holding the member key, exactly one Hawkeye, one ledger file, ever. Forbidden: hot standby with a `wallet.dat` copy; a restored backup started while the original runs; a second Hawkeye on a second node; running `hawkeye run` twice against one node (SQLite `busy_timeout` serialises writes but the second process has its own in-memory state and will build a second unlock); cloud auto-restart of a VM image that still contains `wallet.dat` + `hawkeye.db`. In `self` signing mode (M-1 §4.3) the ledger is the *only* guard: say so.
3. **Hosts and users.** Dedicated host (or VM) per attestor; `ycashd` and `hawkeye` as separate unprivileged users; `txindex=1` (plan §6); `wallet.dat`, the keystore and `hawkeye.db` on an encrypted volume; `rpcbind=127.0.0.1` + cookie auth; the API on loopback behind a reverse proxy that terminates TLS for peers (`HIGH-05-H-1`); firewall: API reachable from peers only; `[peers] urls` are `https://`. File modes (`LOW-05-L-2`): `hawkeye.toml` 0600, keystore 0600, `hawkeye.db` 0600, `.cookie` 0600.
4. **Key ceremony.** Generate the member key **offline** (`hawkeye keys derive --secret <hex>` on an air-gapped machine, or `cast wallet new` / `openssl rand -hex 32`); encrypt into the keystore v3 file there (`cast wallet import` or `hawkeye keys encrypt` — add this command if absent); the password through a separate channel (never in the config, `[keys] password_env`); record `memberkey`, `eth_address`, `near_guardian`; one copy of the keystore + password in sealed escrow (two custodians); transfer the keystore to the host; `hawkeye enroll` (in `wallet` mode this is the moment the secret lands in `wallet.dat` in clear — see M-1); `set_join` with the bond (plan §2.4); hand `eth_address` to the governance round for `setGuardians`. Checklist with signatures.
5. **Backups.** What: `wallet.dat` (member key in `wallet` mode, fee keys, the `vaultsetsig` sign-once records) **and** `hawkeye.db` (+ `-wal`/`-shm`) **and** the keystore **and** `hawkeye.toml` — always together, always with the daemon **and** the node stopped (`systemctl stop hawkeye ycashd`), never while running (WAL is consistent but the two files would be from different instants). How: `tar` + encrypt (`age`/`gpg`), off-host, two generations. Restore: only onto a host where the original is **destroyed** (section 2); after restore, before `hawkeye run`: `hawkeye status` (read-only), compare the ledger's last events with the chain (`hawkeye audit-ledger` — add a read-only command that lists live sign-once records and checks each against `gettxout`/`getrawtransaction`), and if any doubt, **do not sign**: `hawkeye leave` and rejoin with a fresh key. Record retention: sign-once records are never deleted; a restored ledger older than the last signature is an equivocation risk — the audit command must say "ledger is behind the chain: records for vault X missing" and refuse to start without `--i-accept-equivocation-risk`.
6. **Moving hosts.** Stop both daemons on the old host → backup → wipe the old host's `wallet.dat`/`hawkeye.db` (or power it off for good) → restore on the new host → start `ycashd`, wait for sync → `hawkeye status` → `hawkeye run`. Never two hosts alive with the key.
7. **Rotation (join/leave) order.** Table with the three parties (new attestor, old attestor, governance round) and the `guardian-drift` semantics (mainnet: drift **pauses signing for every attestor**, `engine/mod.rs:514-517`). Order: (1) new attestor's key ceremony + `set_join` on Ycash; (2) wait until `set_getinfo` shows it `current` (after `maturity`); (3) governance round signs `SetGuardians(new set incl. new, excl. leaving)` with the **current** threshold and submits — from this moment the Ycash set and the contract disagree by one member until step (4), so (4) **immediately**: old attestor `hawkeye leave`; (5) all attestors see `guardian-drift` clear; (6) old attestor `withdraw-bond` after `maturity`. Admin acts share one `adminNonce` (HK-11): one admin round at a time, coordinate who submits. Emergency rotation (a key is compromised): pause first (`setPaused(true)`), then the same order; the compromised member is slashed by `SET_REMOVE burn=1` rather than leaving.
8. **Parameters that must agree.** Hawkeye `[bridge]` vs the set (`delay` = vault delay; `heartbeat_blocks ≤ livenesswindow/4`; `confirmations`, `min_owner_age`, `takeover_blocks`, `roll_margin`) and vs the contract (`challengeWindow ≥ 2 h`, `mintCap > 0`, `threshold ≥ 2`): the floors in `MEDIUM-05-M-4` and `HIGH-05-H-2`, and the command that prints them (`hawkeye status --params`).
9. **Monitoring.** Every alarm with meaning, severity and the operator action: `supply` (wYEC > locked: page), `exposure` (signed lock reorged: page, pause mints — `LOW-05-L-5`), `guardian-drift` (rotation mid-flight; mainnet signing paused), `matured-unmatched` (an unmatched intent past its cancel window: loss happened; page), `not-a-member`, `fraudulent-mint`, `matching-proposal-challenged` (a griefer), `eth-finality-stall` (H-2), `mint-cap-unbounded` (H-2), `burn-over-cap` (M-2), `unlock-dead`, `fee-coins-low`/`fee-coins-exhausted` (H-1), `gas-low` (M-1), `peer-unreachable`. `/metrics` gauges to graph: `hawkeye_ycash_lag`, `hawkeye_eth_lag`, `hawkeye_eth_finalized_age_seconds`, `hawkeye_fee_coins`, `hawkeye_alarm{name}`, live members vs seats, pending burns by state. Liveness: `lastAct` age vs `livenesswindow` (dormancy ejects the **whole set's** protection: plan §1.4). Suggested alert rules (Prometheus expressions).
10. **Incident response.** Playbooks: (a) suspected key compromise (pause → rotate → slash); (b) equivocation alarm against *you* (stop signing, preserve logs, expect ejection); (c) `exposure`/`supply` breach (pause mints by quorum, reconcile); (d) finality stall (nothing to do but watch; own proposals paused); (e) over-cap burn (governance); (f) peer channel down (`unlock_signature_refused` storms); (g) ledger corruption (`PRAGMA integrity_check`, restore procedure, section 5); (h) node reorg deeper than `C_Y` (the daemon rewinds; check `exposure`). Who to call: the set's out-of-band channel; the slash vote is manual on mainnet (`auto_slash = false`, `config.rs:719`).
11. **Upgrades.** Stop → backup → upgrade binary → `hawkeye status` → start; ledger migrations are automatic and forward-only (`schema.rs:3-6`); never downgrade past a migration; the peer-auth rollout order from `HIGH-05-H-1` §7.
12. **Quick reference.** Commands (`run`, `status`, `enroll`, `keys derive|encrypt`, `leave`, `withdraw-bond`, `split-coins`, `audit-ledger`), files and their modes, ports, the alarm table, the rotation table.

### 4.2 `hawkeye/README.md`

Add "Operating an attestor: read `docs/operations.md` before `enroll`" under "Joining and leaving"; move the key-custody paragraph from `MEDIUM-05-M-1` §4.1 there as a summary with a link.

### 4.3 `ycash-dd/doc/yellowback-attestor.md` and `ycash6/doc/yellowback-attestor.md` (identical edits, both lines)

- Title → `# Running a YED price attestor` and a first line: "This is the **YED price attestor** (`yellowback-attest`). The **wYEC bridge attestor** (Hawkeye) is a different program with a different key: see `hawkeye/docs/operations.md`."
- "Bond key hygiene" (`:154-181`): keep the text for the record but head it with "**Obsolete since the vault upgrade (P4-b):** the bond key *is* the member key and cannot be kept cold (see 'Since the vault upgrade' above). This section describes the v3 registry and applies to no running network." Or delete it; the owner decides — the report recommends the heading (history stays greppable).
- Quick reference: `yed_withdrawbond` → "`hawkeye withdraw-bond` / the primitive's bond spend after `exitHeight + maturity`; `yed_withdrawbond` is the v3 registry's command" — check `yellowback-rpc.md` for whether `yed_withdrawbond` still exists on `upgrade/vault` and say which.
- `:349-351` "a stolen hot key can only grief": add the bridge caveat (M-1 §4.1).

### 4.4 `doc/vault-rpc.md` (both lines), the "Sign once" paragraph (`:300-305`)

Append: "The record lives in this wallet's `wallet.dat` only. A wallet restored from a seed or a backup, or a second node holding the same member key, has **no** record and will sign a different spend of the same outpoint when asked — a provable equivocation. Keep the member key in exactly one wallet, back `wallet.dat` up with the sidecar's own ledger, and never run two copies (see `hawkeye/docs/operations.md`)." The node-side enforcement (restore marker / chain-derived record) is `07/F-5`'s report.

## 5. Tests

- Docs: `make spec-check`-style link check in Hawkeye CI (a `lychee`/`markdown-link-check` step pinned by SHA) so the README → `docs/operations.md` link and the node-doc cross-links resolve.
- The new read-only `hawkeye audit-ledger` command: `tests/engine.rs` `q_audit_ledger_detects_missing_record`: delete a `sign_once_ycash` row from a copied ledger (bypassing the trigger via a raw connection) → the command reports the vault as "signed on chain, no record here" and exits non-zero.
- Devnet scenario `rotation` (`devnet/hawkeye-devnet scenario rotation`): runs the §4.1-7 order end to end and asserts `guardian-drift` is raised at step 3 and cleared at step 5; and the inverse order (leave before `setGuardians`) shows the drift pausing mainnet-mode signing (run the scenario with `mainnet = true` semantics on regtest via a test flag, or assert the alarm only).

## 6. Acceptance criteria

1. `hawkeye/docs/operations.md` exists with the twelve sections, every alarm Hawkeye can raise is in §9's table (grep `self.alarm(` over `crates/hawkeye/src` and diff against the table — add a unit test that extracts the alarm names from `status.rs`/a central `alarms.rs` list and compares).
2. `yellowback-attestor.md` on both lines is retitled, the obsolete section is marked, the quick reference is consistent.
3. `vault-rpc.md` on both lines carries the restore/second-host warning.
4. A reviewer who has never run Hawkeye can follow §4–§7 on the devnet and end with a rotated set and no drift alarm.

## 7. Risks and side effects

- Docs only on the node lines (no code, no consensus, no RPC change).
- `audit-ledger` is read-only; it must open the ledger without migrating (open with `Store::open_readonly`, add it) so a newer ledger is not touched by an older binary.
- Bridge downtime / key rotation / contract redeploy: none; the rotation order prevents a pause rather than causing one.

## 8. Effort estimate and dependencies

Runbook 2 days (the person who wrote the plan should review), node-doc edits 0.5 day, `audit-ledger` + rotation scenario 1.5 days. **≈ 4 days.** Cross-references `HIGH-05-H-1` (peer rollout, fee coins), `HIGH-05-H-2` (stall alarm), `MEDIUM-05-M-1` (custody), `MEDIUM-05-M-4` (floors), `LOW-05-L-2` (modes); write the runbook against their final names, so land it last in the Medium batch or keep the alarm table in sync via the unit test above.

## Completion record

- **Completed:** 2026-10-13T11:21Z
- **Merged:** hawkeye 45fbebc (docs/operations.md, audit-ledger, scenario rotation, alarm-table sync test); node docs ycash-dd 97eafdfc9 / ycash6 fc4611812 (yellowback-attestor.md is the YED price-attestor guide; vault-rpc.md sign-once paragraph). Hawkeye 353 tests pass; rotation scenario PASS on a ycash-dd devnet.
- **Open:** review of the runbook by the plan's author; a markdown link check in CI; rotation on ycash6.
- **Verification:** Integration run 2026-10-13 (both node lines built; full test_bitcoin dd 872/872, ycash6 923/923; qa/yellowback-audit.sh dd --mode upgrade rc 0 (18 PASS), ycash6 --report-only rc 0; functional suites pass; vault_vectors / golden / pq vectors byte-identical across lines). Logs: wt/scratch/integ/.
