# LOW — W3-B-10, W3-B-11 — No mechanical single-instance lock on the ledger; `audit-ledger` cannot see never-broadcast unlocks or any cancel (start-up restore detection added since, self mode still blind)

Repos / branches to change: `hawkeye` (`fix/W3-B-10-B-11-ledger-integrity` off `upgrade/vault`: `hawkeye-store/src/lib.rs` + `signonce.rs`, `crates/hawkeye/src/daemon.rs`, `cli.rs`, `main.rs`, `audit.rs`, `config.rs`, `restore.rs`, `peer_auth.rs` (optional §4.2), `docs/operations.md` §2 / §5 / §9). No wyec change. No node change (uses the existing `set_listsigned` RPC). · Audit source: `docs/audits/quantum-vault-ecosystem-wave3/05-bridge-hawkeye-wyec.md` §W3-B-10 (`:227-234`), §W3-B-11 (`:236-249`); `docs/audits/quantum-vault-ecosystem-wave3/verification/05-verification.md` §W3-B-10 (`:228-231`), §W3-B-11 (`:233-238`); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row "W3-B-4..13, 05/N-1..N-4"; `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` status rows W3-B-10 (`:59`, **STILL OPEN**: `daemon.rs:304-306` adds the restore check, no `flock`/pid) and W3-B-11 (`:60`, **CHANGED**, partially mitigated by `restore.rs`), stale-report note (`:84-87`: §4.3 overlaps `restore::detect`; §4.4 is still the only self-mode remedy; reconcile runbook §5 with §9 "Backups (N-2)"), §W4-B-3 (a) (`:196-216`); `docs/audits/quantum-vault-ecosystem-wave4/verification/02-verification.md` rows W3-B-11 (`:39`) and "still open" (`:42`), §W4-B-3 (`:159-168`: part (a) is a doc ambiguity, not a contradiction). · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13). · Status: pending

Both findings concern the ledger as the equivocation guard (in `ycash_signing = "self"` mode the only one, `docs/operations.md:54-55`): one keeps a second process off it, the other makes a stale copy detectable. They share the store layer and the runbook sections and land together.

## 1. Finding

**W3-B-10.** The single-instance rule — one `ycashd` that can sign with the member key, one `hawkeye run`, one ledger, ever — is procedural only (`hawkeye/docs/operations.md:41-55`). Nothing in `daemon.rs`, `main.rs` or `hawkeye-store/src/lib.rs` takes a lock (`grep flock|pid|try_lock` is empty at `f4436df` as at `b0f085f`; wave-3 verifier `:228-231`, wave-4 `:42`). On one host, SQLite's `BEGIN IMMEDIATE` and the immutable sign-once tables make two processes on one file *mostly* safe (the second `sign_once_*` sees the first's row), but each process keeps its own in-memory state (`Memory`: `submitted`, `conflict_seen`, the alarm set) and will build its own unlock, retry its own sends and race its own Ethereum nonces; the runbook itself lists "`hawkeye run` twice against one node or one ledger" as forbidden. Across hosts (a restored backup started while the original still runs; an auto-recovered VM image) nothing in code notices at all.

**W3-B-11.** `hawkeye audit-ledger` (`crates/hawkeye/src/audit.rs:1-24, 128-265`) compares the ledger's Ycash sign-once records with what the **node** shows: unspent intents (`vault_list`) and mempool unlocks, attributed to this member. "Cancels and acts are listed from the ledger only" (`:23-24`). A signed unlock that was never broadcast, or that left every mempool, and every cancel signature, leave no trace on the node. A restore from a backup taken just before such a signature passes the audit, and the daemon may later sign a different spend of that prevout — a provable equivocation (`SET_EQUIVOCATION`: ejection, bond frozen). In `"wallet"` mode the node wallet keeps its own sign-once records (07/F-5: `set_listsigned` returns `(setid, prevout, role 1|2, sighash)`, `hawkeye-ycash/src/types.rs:886-903`), but the audit does not read them.

**What changed at `f4436df`.** The unlock-revival delta added ledger-restore detection at daemon start-up (`crates/hawkeye/src/restore.rs`, called from `daemon.rs:304-306`): (i) a high-water mark `hawkeye.db.hwm` beside the ledger, rewritten every tick with the count of Ycash sign-once records (`restore.rs:33-63`, `engine/mod.rs:336-341`); a ledger holding fewer records than its mark is flagged restored (`restore.rs:66-74`); (ii) in `"wallet"` mode, every `set_listsigned` record of the set with no ledger row flags it too (`:75-104`), and each such unlock's vault is marked for a roll so the forgotten bytes die (`:110-133`, `:135-147`). While flagged, fresh unlocks wait for every member's signed "none" and the member answers `held/restored` (`api.rs:160-168`). This is a real mitigation for wallet mode at start-up. It leaves: `audit-ledger` itself still compares only node-visible spends (`audit.rs` byte-unchanged); in self mode the mark is the only detector and it is defeated by a backup that includes it — which runbook §5's "`tar` the set" (`docs/operations.md:117-123`) does not forbid, while §9 "Backups (N-2)" (`:378-381`) warns against it (W4-B-3 a); and nothing at all sees a cancel or act signature made after the backup in self mode. §4.3 and §4.4 below are adjusted to reuse `restore.rs` instead of duplicating it.

## 2. Root cause

- `crates/hawkeye/src/daemon.rs:288-320` (`run`; the restore check at `:304-306`) and `:25-55` (`connect` → `Store::open`) — no lock taken; `crates/hawkeye-store/src/lib.rs:87-103` (`Store::open`) — creates `0600` files (`create_private`, `:272`), no lock.
- `crates/hawkeye/src/cli.rs` — signing commands (`rogue_unlock` `:849`, `rogue_mint` `:974`) open the ledger with `Store::open` (`:857`, `:1013`) like the daemon; `status` (`:432`), `status_params` (`:283`) and `declare_leader_gone` (`:98`) go through `daemon::connect`, so any lock must not be taken in `connect`.
- `crates/hawkeye/src/restore.rs:66-104` — the start-up detector: the mark (self and wallet mode) and, in wallet mode only, `set_listsigned`; `audit-ledger` does not call it.
- `crates/hawkeye/src/audit.rs:5-24` — the documented scope: node-visible unlocks only; no `set_listsigned` comparison; no external record of signatures.
- `crates/hawkeye-store/src/signonce.rs:164, 282, 542, 768` — the four sign-once entry points (Mint, Challenge, Ycash, per-burn unlock); each runs the signer inside one `BEGIN IMMEDIATE` (`lib.rs:181-220`), the natural place to journal.

## 3. Fix options considered

| Finding | Option | Verdict |
|---|---|---|
| W3-B-10 | Exclusive advisory lock on `<store_path>.lock` with `std::fs::File::try_lock` | **Chosen.** In `std` since Rust 1.89; the pinned toolchain is 1.97.0 (`rust-toolchain.toml`), so no new crate (rule 6). A separate file, not the database: SQLite uses its own POSIX locks on `hawkeye.db`. |
| W3-B-10 | `fs4`/`fd-lock` crate | Rejected: `std` suffices. |
| W3-B-10 | Pid file | Rejected: stale after a crash; a lock is released by the kernel. |
| W3-B-10 | Cross-host detection | Partial and optional (§4.2): peers alarm when one member key signs requests from two process instances. A complete answer needs a per-member liveness signal on Ycash (a node change); not proposed. |
| W3-B-11 | Document the blind spots | **Chosen** (necessary, not sufficient). |
| W3-B-11 | `"wallet"` mode: compare `set_listsigned` with the ledger both ways | **Chosen**: closes the blind spot for unlocks and cancels in that mode with an existing RPC. |
| W3-B-11 | `"self"` mode: an append-only sign-once journal written, fsynced, inside the sign-once transaction before the signature is released, on a separately backed-up volume; the audit reads it | **Chosen.** The only record that is newer than any backup by construction. |
| W3-B-11 | Back up after every signature | Rejected as a mechanism: a backup needs both daemons stopped (`operations.md` §5); the journal is the incremental form of it. |

## 4. Recommended fix

### 4.1 Single-instance lock (W3-B-10)

`hawkeye-store/src/lib.rs`:

```rust
/// The single-instance lock (W3-B-10): an exclusive advisory lock on `<ledger>.lock`, held for
/// the life of the value. Released by the kernel when the process exits.
pub struct InstanceLock { _file: std::fs::File }

impl Store {
    pub fn lock_instance(ledger: &Path) -> Result<InstanceLock> {
        let path = ledger.with_extension("db.lock");          // hawkeye.db → hawkeye.db.lock
        let f = create_private_rw(&path)?;                    // 0600, as create_private
        match f.try_lock() {
            Ok(()) => { write pid, hostname, start time into it (truncate first); Ok(InstanceLock { _file: f }) }
            Err(std::fs::TryLockError::WouldBlock) => Err(StoreError::Locked(read_holder(&path))),
            Err(std::fs::TryLockError::Error(e)) => Err(e.into()),
        }
    }
}
```

Taken, before the ledger is opened, by `hawkeye run` (`daemon.rs::run`, held in a variable for the loop's lifetime) and by every other command that can produce a member-key **set** signature through the ledger or the node: `rogue-unlock`, `rogue-mint`, `acknowledge-restore`, `leave`, `withdraw-bond`. Not taken by read-only or operator-record commands, which must keep working while the daemon runs: `status`, `audit-ledger`, `exposure list|ack`, `acknowledge-ledger-restore` (a `meta` write and a mark reset, `cli.rs:83-94`), `declare-leader-gone` (a declaration signature, not a sign-once record; it is used precisely while the daemon runs), and `slash list|show|approve|reject` / `gone list` from `MEDIUM-W3-B-2-05-N-2-hawkeye-slash-sign-honours-auto-slash`. The refusal: `"ledger <path> is in use by pid <pid> on <host> since <time>: one hawkeye per ledger (docs/operations.md §2)"`. Runbook §2: the lock covers one host and a local filesystem; it does not see a copy on another host (that is still the procedure, plus §4.2).

### 4.2 Optional cross-host signal (`peer_auth.rs`)

Each process draws a random 16-byte `instance` at start and sends it as `X-Hawkeye-Instance` on signed peer requests (outside the signed message: the request itself is still member-signed, so only the member key's holder can attach it; vectors unchanged). A peer records `member → (instance, last_seen)` and raises page alarm `member-two-instances` ("member <key> signed requests from two Hawkeye processes within 10 min: a copied ledger or key may be running") when two instances of one member alternate within 10 minutes (a restart produces one switch, not alternation). Limited: a clone that never contacts peers is not seen. Document it as a detector, not a guard.

### 4.3 Audit: the node wallet's records (`"wallet"` mode) (W3-B-11)

Reuse, do not duplicate: factor the comparison loop of `restore::detect` (`restore.rs:75-104`) into `restore::node_records_missing(ctx) -> Vec<(SignDomain, OutPoint, sighash)>`, used by `detect` (start-up flag), `unrecorded_unlocks` (`:108-133`) and the audit. In `audit::audit_view` (`audit.rs:140-260`), when `ycash_signing = "wallet"`: call it (it reads `set_listsigned`) and, for every node record of this set (`role` 1 unlock, 2 cancel), require a ledger `sign_once_ycash` row for `(domain, set, prevout)` with the same sighash; a node record with no ledger row is **missing** (same exit code and refusal as today: `"ledger is behind the node wallet: <role> record for <prevout> missing"`); a ledger row with no node record is reported as a warning (the node wallet was restored and not re-imported — `acknowledge-restore` covers it). This sees never-broadcast unlocks and every cancel, because the node writes its record before signing (`ycash-dd src/rpc/vault.cpp:1690-1692`). The audit then agrees with the start-up detector instead of passing a ledger the daemon will flag a moment later. (A crash between the node's record and the ledger's commit produces the same "missing" result; that false positive is documented in `INFO-W4-B-6-B-7-hawkeye-restore-false-positive-operator-drift`.)

### 4.4 Sign-once journal (`"self"` mode, and recommended in both) (W3-B-11)

Config `[ledger] journal = "<path>"` (optional; on mainnet in `"self"` mode a missing journal is a start-up **warning** now and a floor at P8 — record the decision in plan §11). Format: one JSON line per new sign-once row, `{"v":1,"domain":"ycash-unlock|ycash-cancel|ycash-act|eip712-mint|eip712-challenge|…","set":"…","key":"<prevout or lockId[/proposalId]>","sighash|digest":"…","at":<unix>}` — the record's key and digest, **not** the signature (a journal leak reveals nothing a broadcast would not).

Write it in the sign-once transaction, after the signer returns and **before** commit: `append + fsync` (open with `O_APPEND`, `0600`); a write failure aborts the transaction, so no signature leaves the process unjournalled (the signer has produced bytes, but they are dropped with the rollback, exactly as a signer failure today; `signonce.rs` tests already prove a rolled-back transaction releases nothing). The operator places the file on a volume backed up continuously and separately from `hawkeye.db` (a mounted remote volume, or a local file shipped by the host's log forwarder). `hawkeye audit-ledger --journal <path>` (and the start-up audit, `daemon.rs::ledger_audit`, `:255-286`) reads it: a journal line with no ledger row is **missing** (refuse to start, as today). In self mode the journal supersedes the high-water mark as the restore detector (the mark counts records; the journal names them, and lives off the ledger's volume); keep the mark as a cheap second check, bound as in `MEDIUM-W4-B-1-hawkeye-held-veto-restored-answer-hwm-integrity` §4.5.

### 4.5 Runbook (`docs/operations.md`)

- §2: the lock (§4.1), what it does not cover, the optional `member-two-instances` alarm (§9 row).
- §5 "What `audit-ledger` cannot see": signed unlocks never broadcast or dropped from every mempool, cancel and act signatures — unless `"wallet"` mode (§4.3) or the journal (§4.4) is in place; "a restore without either is safe only if no signature can have been made after the backup: take the backup with both daemons stopped and start from it only if the original never ran again".
- §5 vs §9 (W4-B-3 a, wave-4 stale note): §5's backup list (`docs/operations.md:117-123`) gains the sentence that `hawkeye.db.hwm` is **not** part of the tarball (owned by `MEDIUM-W4-B-1-hawkeye-held-veto-restored-answer-hwm-integrity` §4.6 — land its wording, do not write a second one) and the journal's place ("on its own volume, never in the tarball either"); §9 "Backups (N-2)" (`:378-381`) is reduced to a pointer to §5, so the two sections can no longer disagree.
- §8 table: `[ledger] journal` | — | set on mainnet in `"self"` mode.

## 5. Tests

- `hawkeye-store/tests/` new `instance_lock.rs`: a second `lock_instance` on the same path → `Locked` naming the holder; after dropping the first, it succeeds; the lock file is `0600`.
- `crates/hawkeye/tests/instance.rs` (new; the first binary-level test in the repo, using `env!("CARGO_BIN_EXE_hawkeye")` and `std::process::Command`, no new dev-dependency): start `hawkeye run` against a regtest mock config, then a second `hawkeye run` with the same ledger exits non-zero with the message; `hawkeye status` succeeds meanwhile. If a binary-level test is unwanted, test `daemon::run`'s lock acquisition as a function instead.
- `audit.rs` tests (mock node; `q_audit_ledger_detects_missing_record`, `crates/hawkeye/tests/engine.rs:4656`, and `r10_ledger_restore_is_detected`, `:5371`, are the templates, anvil-backed with `HAWKEYE_REQUIRE_ANVIL=1`): `audit_wallet_mode_sees_unbroadcast_unlock` — the mock wallet holds a `set_listsigned` record for a prevout the ledger lacks (simulate the restore by copying the ledger before the signature) → missing, non-zero; `audit_wallet_mode_sees_cancel` — same for role 2. Both fail at `f4436df` (the audit passes although `restore::detect` would flag the same ledger at start-up).
- `self_mode_restore_with_the_mark_is_caught_by_the_journal` — copy ledger **and** `hawkeye.db.hwm` (the whole directory, the W4-B-3 a mistake), sign more, restore the copy: the mark no longer detects it; with the journal configured, start-up refuses. Fails at `f4436df` (starts unflagged).
- `hawkeye-store/tests/sign_once.rs`: `journal_line_per_record` (each entry point appends exactly one line); `journal_failure_rolls_back` (journal path on a read-only dir → the sign-once call fails, no row, signer output discarded); `journal_survives_ledger_restore` (restore an older ledger, audit with the journal → missing).
- `tests/alarm_table.rs` for `member-two-instances` if §4.2 is taken.

## 6. Acceptance criteria

1. A second `hawkeye run` (or signing command) on the same ledger on the same host refuses to start; read-only commands still work.
2. In `"wallet"` mode, `audit-ledger` fails when the node wallet holds an unlock or cancel record the ledger lacks.
3. With a journal configured, a ledger restored from before any signature fails the audit; a journal write failure prevents the signature from being recorded or used.
4. The runbook states the remaining blind spots exactly.

## 7. Risks and side effects

- **Upgrade order.** The lock file is new; an old binary ignores it, so upgrade every process on a host together.
- **Journal latency.** One fsync per signature; signatures are rare (per lock, burn, cancel, act). A remote volume that stalls stalls signing — choose a reliable mount, alarm on `journal_write_failed` (ticket) via the existing error counters.
- **Network filesystems.** Advisory locks over NFS are unreliable; the runbook already requires a local ledger.
- **Bridge downtime / key rotation / contract redeploy:** none.

## 8. Effort estimate and dependencies

2 days (lock 0.5, audit 0.5, journal 0.5, tests and docs 0.5; +0.5 for the optional §4.2). Coordinate the command list with `MEDIUM-W3-B-2-05-N-2-hawkeye-slash-sign-honours-auto-slash` (its `slash` / `gone list` subcommands must not take the lock) and runbook §5 with `MEDIUM-W4-B-1-hawkeye-held-veto-restored-answer-hwm-integrity` (the `.hwm` sentence and mark format are that report's).
