# LOW — W3-B-6 — The peer-auth replay cache is written before the membership check and is unbounded

Repos / branches to change: `hawkeye` (`fix/W3-B-6-replay-cache` off `upgrade/vault`: `crates/hawkeye/src/peer_auth.rs`, `tests/engine.rs`). No wyec change. No node change. No change to the signed request format or its vectors (plan §4.6 unchanged). · Audit source: `docs/audits/quantum-vault-ecosystem-wave3/05-bridge-hawkeye-wyec.md` §W3-B-6 (`:174-184`); `docs/audits/quantum-vault-ecosystem-wave3/verification/05-verification.md` §W3-B-6 (`:198-205`, Low bordering Info); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md` row "W3-B-4..13, 05/N-1..N-4"; `docs/audits/quantum-vault-ecosystem-wave4/02-hawkeye-recheck-and-delta.md` status row W3-B-6 (`:55`, **STILL OPEN**, lines moved; three new routes behind the same layer) and stale-report note (`:81-83`); `docs/audits/quantum-vault-ecosystem-wave4/verification/02-verification.md` status row (`:42`, confirmed: `peer_auth.rs:305` `admit_once` before `:309` membership). Related: verifier N-4 (in-memory cache across a restart), tracked in `INFO-W3-B-12-B-13-05-N-4-bridge-contract-notes-test-fidelity.md` and implemented on this branch (same function). · Re-verified at hawkeye `f4436df` / wyec `dfd51cb` (2026-10-13). · Status: done — completed 2026-10-16 (merged on `upgrade/vault`; see the completion record). Previously pending

## 1. Finding

The middleware of the authenticated routes (`crates/hawkeye/src/peer_auth.rs:223-330`; since `f4436df` it guards six routes — `/slash/sign`, `/unlock/sign`, `/cancel/sign` and the new `/burns/unlock`, `/vaults/orphaned`, `/members/gone`, `api.rs:31-41`) runs: headers well-formed (`:260`), (2) fresh within `SKEW_SECS = 60` (`:277-284`), (4) the signature recovers to the header's member key (`:285-303`), **(3) record `(member, nonce)` in the replay cache** (`:304-307`, `admit_once` `:105-113`), and only then (5) the key is a current member of the set (`:308-314`). Step 4 proves possession of *some* secp256k1 key, not membership: anyone who can reach the API can sign with fresh throwaway keys and insert one cache entry per request. Entries live `2 × SKEW_SECS` = 120 s (`:111`); the map is pruned on every call but has no size bound, so memory grows with request rate × 120 s, and every insert also costs the `retain` pass over the whole map (`:107`) under one mutex shared with honest peers' requests (and, since `f4436df`, with every takeover's `POST /burns/unlock` round). The runbook puts the API behind TLS and a firewall (`[peers] allow_from`, optional), so the reachable population is insiders and mis-configured proxies; each request also costs the attacker one signature and the server one recovery. Low.

A second, smaller amplification sits next to it: before the engine's first tick the member snapshot is empty and `is_current_member` (`:203-219`) calls the node's `set_getinfo` for **every** signature-valid request, so a non-member can drive one node RPC per request during start-up.

## 2. Root cause

- `crates/hawkeye/src/peer_auth.rs:304-314` — step 3 before step 5.
- `crates/hawkeye/src/peer_auth.rs:79-80, 105-113` — `replay: Mutex<HashMap<(PubKey33, [u8;16]), u64>>`, unbounded; `retain` over the whole map on every admission.
- `crates/hawkeye/src/peer_auth.rs:203-219` — empty snapshot → `set_getinfo` per request.
- `docs/hawkeye-bridge-plan.md:530-534` (§4.6) lists the admission conditions as a conjunction (fresh, not seen in 120 s, recovers, current member) without an order or a bound; the implementation chose the order.

## 3. Fix options considered

| Option | Verdict |
|---|---|
| (a) Check membership before inserting | **Chosen.** Only current members (dozens at most) can then reach the cache. |
| (b) Bound the map: per-member cap and a global cap, refuse `429` when over | **Chosen** as well: a compromised member key must not be able to grow it either. |
| (c) Bucket entries by expiry second and drop whole buckets (O(1) prune) | **Chosen** (cheap; removes the full `retain` scan from the hot path). |
| (d) Persist the cache (closes N-4) | Rejected: a start-time floor on `X-Hawkeye-Time` achieves the same with no I/O (§4.3). |

## 4. Recommended fix

### 4.1 Order (`peer_auth.rs::layer`)

Steps become 1 well-formed → 2 fresh → 4 signature → **5 current member** → **3 replay**. Update the module comment (`peer_auth.rs:1-25`) and plan §4.6 (`:530-534`): "`(member, nonce)` is recorded only for a current member whose signature verified, at most 4,096 per member; a request older than the process is refused". The `401 replayed` / `403 not a current member` codes are unchanged; a non-member's replay is now answered `403` (it never reaches the cache), which is the more informative answer.

### 4.2 Bounded cache (`AuthState`)

```rust
const REPLAY_PER_MEMBER: usize = 4_096;      // ≫ an honest peer's signing requests per 120 s
replay: Mutex<ReplayCache>,

struct ReplayCache {
    by_member: HashMap<PubKey33, HashMap<[u8; 16], u64 /* expiry */>>,
    buckets: BTreeMap<u64 /* expiry second */, Vec<(PubKey33, [u8; 16])>>,
}
```

`admit_once(member, nonce, now)`: drop every bucket with key `< now` (and their entries); refuse `Replayed` if present; refuse `Full` if `by_member[member].len() ≥ REPLAY_PER_MEMBER` (answered `429 Too Many Requests`, logged `peer_auth_rate_limited`, member key in the log); else insert. The global size is then bounded by `|members| × REPLAY_PER_MEMBER`; members that leave the set are dropped on `publish` (`:99-102`).

### 4.3 Start-up (`is_current_member`) and the restart window (N-4)

- While the engine has not published a snapshot (`members` empty), the daemon answers `503 Service Unavailable` ("starting: no member snapshot yet") instead of calling `set_getinfo` per request; the `set_getinfo` fallback is kept only for code paths with no engine (none of the signing routes in `hawkeye run`). Peers already retry on the next tick.
- N-4: record `AuthState.started_at = now_secs()` at construction and refuse (`401 "request predates this process"`) any request with `X-Hawkeye-Time < started_at`. A request captured before a restart can then never be replayed after it; an honest peer whose clock is behind by up to `SKEW_SECS` is refused for at most that long after a restart and succeeds on its next tick with a fresh timestamp.

## 5. Tests

- `peer_auth.rs` unit tests: `replay_cache` (`:452-461`) extended: per-member cap → `Full`; bucket expiry drops entries; a member removed from the snapshot loses its entries; `started_at` floor refuses an older timestamp.
- `crates/hawkeye/tests/engine.rs` (anvil-backed, `HAWKEYE_REQUIRE_ANVIL=1`; `k1_signing_routes_authenticated_and_inert_at_threshold_one`, `:1963-2097`, is the template and **already** covers stale and replayed requests end to end, `:2037-2079` — the wave-3 claim that they were missing was inaccurate, see `INFO-W3-B-12-B-13-05-N-4`): `peer_auth_non_member_never_enters_replay_cache` — 10,000 requests signed by fresh keys to each of the six routes → all `403`, cache length 0 (expose `AuthState::replay_len()` under `#[cfg(test)]`); fails at `f4436df` (cache length 10,000 per route); `peer_auth_request_older_than_the_process_refused` — a request signed before an engine restart, replayed after it within 60 s → `401`; `peer_auth_starting_returns_503` before the first tick. Extend `k1` with a replay to `/burns/unlock` (the route a takeover uses most).
- No vector changes (`hawkeye-core/tests/peerauth.rs` untouched).

## 6. Acceptance criteria

1. A signature-valid request from a non-member never allocates in the replay cache.
2. The cache is bounded by `|members| × REPLAY_PER_MEMBER`, pruned without a full scan.
3. A request older than the process is refused; a request replayed within its 120 s lifetime is refused (unchanged).
4. No node RPC is made per request before the first tick.

## 7. Risks and side effects

- An honest peer that legitimately sends more than 4,096 signing requests in 120 s gets `429`; Hawkeye's own traffic is a few requests per tick per peer. Mixed-version peers are unaffected (wire format unchanged).
- **Bridge downtime / key rotation / contract redeploy:** none.

## 8. Effort estimate and dependencies

0.5–1 day. No dependencies; implements verifier N-4 on the same branch (the INFO report records it as done by this one).

## Completion record

- **Completed:** 2026-10-15
- **Merged:** hawkeye `#15` `c6a824d`. The replay nonce is recorded only after the signature verifies and the key is a current member. Each member is capped at 4,096 live entries (`429` past that).
- **Not closed by this landing:** a 503 before the first member snapshot, the `started_at` restart floor, and O(1) expiry buckets.
