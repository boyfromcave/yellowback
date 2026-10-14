# MEDIUM — 05/M-4 — Mainnet floors on the policy parameters (`confirmations`, `delay`, `min_owner_age`, `takeover`, `roll_margin`, `heartbeat_blocks` vs `livenesswindow`)

Repos / branches to change: `hawkeye` (`fix/05-M-4-mainnet-floors` off `upgrade/vault`). No node change. · Audit source: `05-bridge-hawkeye-wyec.md` §M-4 (`:206-216`); `verification/05-verification.md` row M-4 (`:19`); `00-consolidated.md` row 05/M-4, recommendation R7. · Status: done — completed 2026-10-13T06:41Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13, re-confirmed 2026-10-14 at ycash-dd 3fe3492b6 and ycash6 1ebfee622; nightly tier pending the owner's dispatch)

## 1. Finding

`Config::check` (`crates/hawkeye/src/config.rs:609-616, 643-692`) applies mainnet rules to `mint_mode`/`mint_threshold` (`≥ 2`), `secret_hex` (refused), `[devnet] drills` (refused) and depth-only finality (refused), and requires only `delay ≥ 1`, `confirmations ≥ 1`, `min_lock ≤ max_lock`. It applies nothing to `confirmations` (`C_Y`, the lock policy's depth rule, `hawkeye-core/src/policy.rs:286-291`), `delay`, `min_owner_age`, `takeover_blocks`, `roll_margin`, `heartbeat_blocks`, or to any of them against the set's live parameters (`livenesswindow`, the vault `delay`). The sample config (`config/ethereum-anvil.example.toml:26-36`) carries `confirmations = 2`, `delay = 6`, `min_owner_age = 400`, `heartbeat_blocks = 10`. A mainnet file copied from it signs `Mint` for locks with two confirmations: a 2-block Ycash reorg (routine) turns a signed lock into an `exposure` — minted wYEC with no YEC behind it; `engine/ycash.rs:441-457` alarms and nothing pauses (`LOW-05-L-5`). `heartbeat_blocks` above `livenesswindow` makes every member DORMANT at once, which opens every vault's owner branch (plan §1.4; `OP_CHECKSETDORMANT`), the bridge's catastrophic liveness failure, caused by a typo.

## 2. Root cause

- `crates/hawkeye/src/config.rs:609-616` — the only bounds; `:651-666, 686-692` — the mainnet block, parameter-free.
- `crates/hawkeye/src/daemon.rs:62-126` — `startup_checks` reads `set_getinfo` (`:76-89`: `maturity` floor only) and never compares `heartbeat_blocks` with `livenesswindow`, nor `delay` with any vault.
- `crates/hawkeye/src/engine/mod.rs:363-392` — `heartbeat` sends every `heartbeat_blocks` from `lastAct`, no sanity bound.
- Plan §2 (`hawkeye-bridge-plan.md:195-207`) gives the mainnet proposal row (delay 1,152; `livenessWindow` 8,064 "≥ 4 × heartbeat"; `heartbeat_blocks` 288) and §3.1 gives `MIN_OWNER_AGE` ≈ 841,000; none of it is enforced.

## 3. Fix options considered

- Floors in code only vs floors derived by `yb-calibration`: the workspace rule is that constants change with a calibration result; the floors here are *sanity bounds* (an order of magnitude below any sane value is still refused), not the calibrated values. Code floors, named constants, calibration sets the actual config. Chosen.
- Static checks only vs also live checks against `set_getinfo`: the dangerous relation (`heartbeat_blocks` vs `livenesswindow`) is only knowable from the node; both. Chosen.
- Warn vs refuse on mainnet: refuse (consistent with the threshold rule); warn on testnet; nothing on regtest.

## 4. Recommended fix

### 4.1 The table (`crates/hawkeye/src/config.rs`, new `mod floors` with `pub const`s and a doc comment citing plan §2/§3.1)

| Parameter | Mainnet floor / rule | Why that number | Where enforced |
|---|---|---|---|
| `confirmations` (`C_Y`) | `≥ 20` (`MAINNET_MIN_CONFIRMATIONS = 20`, ≈ 25 min at 75 s) | deeper than any reorg seen on Ycash in years; the plan's lock-absent rule and H-2's floor derivation assume 20 | `Config::check` (static) |
| `delay` (vault challenge window, blocks) | `≥ 288` (`MAINNET_MIN_DELAY = 288`, 6 h) and `≥ 4 × confirmations` | the plan's mainnet row is 1,152 (24 h); a cancel needs `C_Y`-deep finality of the burn view plus a cancel's own inclusion; 6 h is the sanity bound | static; **and** live: every `WYEC` vault the policy accepts must carry exactly `delay` (already, `policy.rs:221-226`), and `startup_checks` warns if `vault_list tag=WYEC setid=…` shows vaults with another `delay` (a misconfigured attestor would reject every lock) |
| `min_owner_age` | `≥ 105_120` (`MAINNET_MIN_OWNER_AGE = 105_120`, 3 months) | §3.1 proposes ≈ 841,000 (2 years); the sanity bound stops a devnet value (400) | static |
| `takeover_blocks` | `≥ confirmations` and `≤ delay / 4` | a takeover faster than finality makes two leaders; slower than a quarter of the delay leaves no time for the successor before cancels mature | static |
| `roll_margin` | `≥ delay + takeover_blocks + 2 × confirmations` | a roll must be posted, possibly taken over, and released before `ownerHeight` | static |
| `heartbeat_blocks` | `≥ 1` and `≤ livenesswindow / 4` (plan D-U5 "≥ 4 × heartbeat"); refuse `0` on mainnet (0 disables heartbeats, `engine/mod.rs:364-367`) | three missed heartbeats before dormancy | **live** in `startup_checks` against `set_getinfo.params.livenesswindow`; re-checked every 60 ticks with the guardian check (a `SET_PARAMS` could shrink the window) → alarm `heartbeat-too-slow` and, on mainnet, log at `error` every tick (do not pause: heartbeats *are* the fix) |
| `min_lock` | `> 0` | dust locks cost policy evaluation and a mint each | static |
| `max_lock` | `≤ 21_000_000 YEC`; warn if `> ratelimit cap` (a lock larger than one window's cap cannot be released in one burn: `MEDIUM-05-M-2`) | | static + live |
| `[eth] finality` | `finalized` only (exists) | | existing |
| `[bridge] mint_threshold` / contract threshold | `≥ 2` (exists) | | existing |
| contract `challengeWindow`, `mintCap` | `HIGH-05-H-2` | | `check_bridge` |

Testnet: the same table with every floor divided by 4, as warnings. Regtest: unchanged.

### 4.2 Code

- `config.rs`: `fn check_mainnet_floors(&self, b: &BridgeSection) -> Result<()>` called inside the `if mainnet` block; each failure names the parameter, the value, the floor and the plan reference (`"mainnet refuses bridge.confirmations 2 < 20 (MAINNET_MIN_CONFIRMATIONS, plan §2/§4.1)"`). Keep the existing `delay ≥ 1`/`confirmations ≥ 1` for all networks.
- `daemon.rs::startup_checks`: after `set_getinfo`, `floors::check_live(&params, &set.set.params, chain)` → `heartbeat_blocks ≤ livenesswindow / 4`, `max_lock` vs cap warning, `delay` vs observed vaults warning (query `vault_list`, count by `delay`).
- `engine/mod.rs::check_guardians` (every 60 ticks): also re-run `check_live` and raise/clear `heartbeat-too-slow`, `params-drift`.
- `hawkeye status --params`: print the effective parameters, the set's, the contract's and every floor, with `OK`/`BELOW FLOOR` — the runbook's §8 command.
- `config/ethereum-anvil.example.toml`: add a comment block "mainnet floors: see `docs/operations.md` §8; these devnet values are refused on mainnet".
- `config/ethereum-mainnet.example.toml` (new): the plan §2 mainnet proposal row as values, with `# calibrated by yb-calibration, P8` on each.

## 5. Tests

- `config.rs` unit tests (the existing `sample(network, extra)` helper, `:782`): for each row, the devnet value on `"mainnet"` is refused with the exact message; the floor value passes; testnet warns (capture via `tracing-test` or assert the returned warnings vector — add `Settings.warnings: Vec<String>`).
- `tests/engine.rs` `r_heartbeat_floor_live`: mock set with `livenesswindow = 20`, config `heartbeat_blocks = 10` → `startup_checks` fails on mainnet semantics, alarm on regtest; shrink the window via the mock mid-run → `heartbeat-too-slow` raised on the next 60-tick check.
- `r2_delay_mismatch_warns`: vaults with `delay = 6` while config says 12 → `startup_checks` warns `vault_delay_mismatch`.

## 6. Acceptance criteria

1. Every row of §4.1 is a named constant with a unit test on the mainnet refusal and the floor pass.
2. `startup_checks` on mainnet refuses `heartbeat_blocks > livenesswindow / 4`; the live re-check alarms when the set changes.
3. `hawkeye status --params` shows all three parameter sources and the floors.
4. The mainnet example config passes `Config::check` with `name = "mainnet"` (unit test).

## 7. Risks and side effects

- An existing testnet/Sepolia attestor whose config is below a floor gets warnings, not refusals; a mainnet config below a floor refuses to start — intended, and there is no mainnet deployment yet.
- The floors are sanity bounds; the calibrated P8 values (plan Q-1, `yb-calibration`) are higher and unaffected.
- Bridge downtime / key rotation / contract redeploy: none.

## 8. Effort estimate and dependencies

1.5 days. Lands after `HIGH-05-H-2` (shares `startup_checks`/`check_bridge` edits); referenced by `MEDIUM-05-M-3` §8.

## Completion record

- **Completed:** 2026-10-13T06:41Z
- **hawkeye** `upgrade/vault` merge 113d380 (branch `fix/bridge-watch`): e1fddbb.
  - `floors.rs`: a mainnet config below any floor is refused, naming every breach; testnet gets warnings; regtest is unconstrained.
  - The live heartbeat check runs at startup and every 60 ticks (`heartbeat-too-slow`); a `params-drift` alarm is added.
  - Adds `hawkeye status --params` and `config/ethereum-mainnet.example.toml`.
- **Tests:** the floor, heartbeat and example-config tests pass; hawkeye lib 42. §6 criteria 1, 2 and 4 met. Criterion 3 (`status --params`) compiles but was not run against a live node.
