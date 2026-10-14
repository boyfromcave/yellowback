# INFO — 05/I-1, 05/I-2 — `Debug` on secret-bearing config types; the workspace `CLAUDE.md` says `rpcversion 5` for Hawkeye

Repos / branches to change: `hawkeye` (`fix/05-I-1-redact-debug` off `upgrade/vault`); `yellowback` workspace (`fix/05-I-2-hawkeye-rpcversion` off `upgrade/vault`: `AGENTS.md`/`CLAUDE.md`, `README.md` components table if it repeats the number). No node change. · Audit source: `05-bridge-hawkeye-wyec.md` rows I-1, I-2 (`:50-51`); `verification/05-verification.md` rows I-1, I-2 (`:32-33`); `00-consolidated.md` "various / Info". · Status: done — completed 2026-10-13T06:11Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13, re-confirmed 2026-10-14 at ycash-dd 3fe3492b6 and ycash6 1ebfee622; nightly tier pending the owner's dispatch)

## 1. Finding

**I-1.** `KeySource` derives `Debug` (`crates/hawkeye/src/config.rs:297-308`) with `Hex(String)` holding the raw secret; `Settings` derives `Debug` (`:311`) and contains `key: Option<KeySource>` and `ycash_auth: Auth`; `hawkeye-ycash`'s `Auth` derives `Debug` (`crates/hawkeye-ycash/src/client.rs:22-31`) with `UserPass { password }`; `Config`/`YcashSection`/`KeysSection` derive `Debug` with `rpc_password`/`secret_hex`. Nothing logs them today (grep for `{:?}` over `Settings`/`Config` finds none), so a future `debug!(?settings)` or an `anyhow` context that formats one would print the member secret or the RPC password into the log stream (JSON logs shipped to a collector).

**I-2.** The workspace `CLAUDE.md:199` (= `AGENTS.md`) says clients on `upgrade/vault` use `rpcversion` 5, while Hawkeye's `README.md:85-89` requires the post-quantum node line (`upgrade/quantum-vaults`), `rpcversion` 8, and "parses only the post-quantum owner shape" (`hawkeye-core/src/policy.rs:225-227`); the workspace file is stale for this component and an agent following it would test Hawkeye against a node that has no vault Hawkeye recognises.

## 2. Root cause

- `crates/hawkeye/src/config.rs:26, 66, 74, 188, 297, 311` — `#[derive(Debug …)]` on types with secrets.
- `crates/hawkeye-ycash/src/client.rs:22` — `#[derive(Clone, Debug)] pub enum Auth`.
- Workspace `CLAUDE.md:199`; `hawkeye/README.md:85-89`; the two were written for different node lines and nothing checks them against each other.

## 3. Fix options considered

- Remove `Debug` entirely: breaks `anyhow` contexts and tests that print settings. Rejected.
- Manual `Debug` that redacts: standard; a `Redacted<String>` newtype (`Debug` prints `"<redacted>"`, `Deref` for use) applied to `secret_hex`, `rpc_password`, `password` in `Auth`, and the `Hex` variant. **Chosen.** No new crate (`secrecy` would do it but adds a pin for ~20 lines).
- I-2: either make the workspace file say what Hawkeye needs today, or make Hawkeye support the `upgrade/vault` owner shape too. The second is a product decision (plan §4.1 rule 1's `OwnerScheme`); the doc fix is the INFO item.

## 4. Recommended fix

1. `hawkeye-core` (or `hawkeye-ycash`, where `Auth` lives): `pub struct Redacted<T>(T)` with `Debug` → `<redacted>`, `Clone`, `Deserialize` (transparent), `Deref`, `expose(&self) -> &T`. Apply to `KeysSection.secret_hex`, `YcashSection.rpc_password`, `Auth::UserPass.password`, `KeySource::Hex`; `NearSection.relayer_key_file` is a path (fine).
2. Unit test: `format!("{:?}", config)` and `format!("{:?}", settings)` for a sample with `secret_hex` and `rpc_password` contain neither value and do contain `<redacted>`.
3. A `clippy`-adjacent guard: a test that greps `crates/*/src` for `derive(` lines on structs with fields named `secret*`, `password*`, `*_key` and fails unless the field type is `Redacted` (cheap, keeps the next field honest).
4. I-2: workspace `AGENTS.md`/`CLAUDE.md` line 199 → "… `rpcversion` 5 (Hawkeye: the bridge attestor builds against the post-quantum node line, `upgrade/quantum-vaults`, `rpcversion` 8 — `hawkeye/README.md` 'Node requirement' — until the quantum line merges into `upgrade/vault`)"; the components table in the workspace `README.md` gets the same note if it names a version. Add a line to `docs/mapping.md` §22/§23 (the Hawkeye rows) with the citation. Hawkeye `README.md:85-89` cross-links the workspace file so the next drift is visible from either side; `scripts/check-ref-pins.sh`-style CI is out of scope for an INFO item.

## 5. Tests

§4.2 and §4.3 above; `cargo test --locked`.

## 6. Acceptance criteria

1. No `Debug` output of any config/settings/auth type contains a secret (test).
2. The workspace `AGENTS.md` and Hawkeye's `README.md` agree on the node line and `rpcversion` Hawkeye needs, with a cross-link each way.

## 7. Risks and side effects

None operational. `Redacted` changes the field types; the devnet/config loader code that reads `rpc_password` uses `.expose()`.

## 8. Effort estimate and dependencies

0.5 day. No dependencies.

## Completion record

- **Completed:** 2026-10-13T06:11Z
- **hawkeye** `upgrade/vault` merge f693026 (branch `fix/bridge-misc`): 1494a9c (`Redacted<T>` on every secret-bearing config field; `config::tests::debug_redacts_secrets`; the `tests/redaction.rs` source guard; README now states the node requirement as `upgrade/vault`, rpcversion 8).
- **Workspace:** `AGENTS.md` now says `rpcversion` 8, not 5, citing `YELLOWBACK_RPC_VERSION = 8` at `src/rpc/yellowback.cpp:61` on both node lines (it was stale for every client, not only Hawkeye). The README components table names no version, so it is unchanged.
- **Tests:** 301 passed at 957a076. §6.1 and §6.2 met.
