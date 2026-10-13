# LOW — 05/L-2 — ycashd RPC credentials over plain `http://` to any host; no loopback/TLS rule; no file-permission checks

Repos / branches to change: `hawkeye` (`fix/05-L-2-transport-and-perms` off `upgrade/vault`). No node change. · Audit source: `05-bridge-hawkeye-wyec.md` §L-2 (`:228-233`); `verification/05-verification.md` row L-2 (`:21`); `00-consolidated.md` row 05/L-1..L-5. · Status: pending

## 1. Finding

`hawkeye-ycash` sends HTTP Basic credentials (`-rpcuser`/`-rpcpassword`, or the node's cookie) wherever `ycash.rpc_url` points (`crates/hawkeye-ycash/src/client.rs:21-66` builds the header, `:134-150` sends it on every call); there is no loopback or `https://` check in the client or in `Config::check` (`crates/hawkeye/src/config.rs`). An operator who points `rpc_url` at a node on another host over plain HTTP exposes the RPC secret — which can `dumpprivkey` the member key (`MEDIUM-05-M-1`) and sign set acts — to the network path. The YED attest agent already refuses this (`ycash-dd/doc/yellowback-attestor.md:240-243`: cleartext Basic auth only to loopback, else `https://`, `allow_insecure_rpc = true` to insist; config file must be `0600`, `--insecure-config-permissions` to override). Hawkeye checks no file mode anywhere (`grep -rn "permissions\|metadata" crates/hawkeye/src` → nothing): `hawkeye.toml` may hold `rpc_password` or `secret_hex`, the keystore holds the encrypted key, `hawkeye.db` holds the sign-once ledger, and all are created with the process umask.

## 2. Root cause

- `crates/hawkeye-ycash/src/client.rs:109-125` — `YcashRpc::new`/`with_timeout` accept any URL string; `:134-150` attach `Authorization` unconditionally.
- `crates/hawkeye/src/config.rs:73-88` (`YcashSection`), `:693-697` (only `api.listen` is parsed) — no transport rule; `[eth] rpc_url` and `[peers] urls` likewise.
- `crates/hawkeye/src/config.rs:747-762` (`load_key`) and `crates/hawkeye-store/src/lib.rs:82-85` (`Store::open`) — no mode check or set.

## 3. Fix options considered

- Enforce in the client (`hawkeye-ycash`) vs in config validation: the client is also used by tests, the mock and tools; the rule belongs in `Config::check` with a small pure helper the client can reuse. Chosen: helper in `hawkeye-ycash` (`transport::is_loopback_or_tls(url) -> bool`), enforced in `Config::check`, with the attest agent's override names so operators learn one vocabulary.
- Refuse vs warn for file modes: refuse on mainnet, warn elsewhere (the devnet creates files with whatever umask the scripts have).

## 4. Recommended fix

1. **`hawkeye-ycash/src/transport.rs`** (new): `pub fn credentials_safe(url: &str) -> Result<(), TransportError>`: parse with `url` (already a transitive dep of `reqwest`; add the exact pin to `Cargo.toml` or parse by hand: scheme + host); OK iff scheme is `https`, or host ∈ {`127.0.0.0/8`, `::1`, `localhost`} (resolve literal IPs only; a hostname other than `localhost` is *not* loopback). Unit-tested with the attest agent's cases.
2. **`Config::check`**: `ycash.rpc_url` must pass `credentials_safe` unless `[ycash] allow_insecure_rpc = true` (refused on mainnet even with the flag? — no: mirror the agent: the flag overrides on every network, but mainnet logs it at `error` on every start); `[peers] urls` must each pass on mainnet (coordinated with `HIGH-05-H-1` §4.1); `[eth] rpc_url` carries no credentials, so only warn when `http://` to a non-loopback host (an Ethereum provider URL often embeds an API key in the path — warn about that too: `"eth.rpc_url embeds a secret in the URL and is not https"`).
3. **File modes** (`crates/hawkeye/src/config.rs::load`, `load_key`, `daemon::connect`): on Unix, `metadata(path).permissions().mode() & 0o077 == 0` required for `hawkeye.toml` **when it contains** `rpc_password` or `secret_hex`, for the keystore always, and for `hawkeye.db` always; failure → `"… is group/world readable: chmod 600 it (or pass --insecure-file-permissions)"`; refused on mainnet without the flag, warned elsewhere. `Store::open` creates the file with `OpenOptions::mode(0o600)` before SQLite opens it (create the empty file first, then `Connection::open`), and sets `0o600` on `-wal`/`-shm` after the first write (`PRAGMA journal_mode = WAL` creates them) — or document that SQLite inherits the main file's mode for `-wal`/`-shm` (it does since 3.7; state the version in a comment and assert at runtime with a `metadata` check after open).
4. **`hawkeye init`** (if the command exists; the CLI list shows no `init` — add a `hawkeye keys encrypt`/`hawkeye init` that writes the config with `0600`): write every new file `0600`.
5. Docs: `README.md` configuration section and `docs/operations.md` §3 (`MEDIUM-05-M-3`): the transport rule, the modes, the overrides.

## 5. Tests

- `hawkeye-ycash` unit: `credentials_safe("http://127.0.0.1:18232")` OK; `http://[::1]:18232` OK; `http://localhost:18232` OK; `http://10.0.0.5:18232` refused; `https://node.example` OK; `http://ycashd.internal` refused (hostname, not loopback).
- `config.rs` tests: `rpc_url = "http://10.0.0.5:18232"` refused; with `allow_insecure_rpc = true` accepted with a warning; mainnet `[peers] urls = ["http://1.2.3.4:7801"]` refused.
- File-mode tests (`tempfile`, `set_permissions(0o644)`) for the config with `rpc_password`, the keystore, the db; `0o600` passes; the flag overrides off-mainnet.
- `Store::open` creates `0600` (assert `mode() & 0o777 == 0o600`).

## 6. Acceptance criteria

1. Cleartext credentials can only go to loopback or TLS without an explicit override; the override is logged at `error` on mainnet.
2. Secret-bearing files are refused when group/world readable on mainnet, warned elsewhere; the ledger is created `0600`.
3. The vocabulary matches the YED attest agent's (`allow_insecure_rpc`, `--insecure-*-permissions`).

## 7. Risks and side effects

- Devnet scripts that run ycashd on another container over plain HTTP must set `allow_insecure_rpc = true` (regtest) — update `devnet/` configs in the same PR.
- No downtime, rotation or redeploy.

## 8. Effort estimate and dependencies

1 day. Shares `check_transport` with `HIGH-05-H-1` (land H-1 first, or this one first with the helper and let H-1 call it).
