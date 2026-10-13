# HIGH — 05/H-1, 05/N-1, 05/N-2, 05/L-1 — Authenticate the Hawkeye peer channel, gate `/unlock/sign`, add the per-burn sign-once dimension, validate reused unlock hex, gather cancels and bound cancel capacity

Repos / branches to change: `hawkeye` (`fix/05-H-1-peer-channel` off `upgrade/vault`; the audited HEAD is `69fb2a8` on the quantum-vaults descendant branch — land the fix on whichever of the two is the branch Hawkeye ships from and cherry-pick to the other, the code paths are identical). No node change on either line; one optional §10 change request (CR-N5, §4.6). · Audit source: `docs/audits/quantum-vault-ecosystem/05-bridge-hawkeye-wyec.md` §H-1 (`:62-106`), §L-1 (`:218-225`); `verification/05-verification.md` §H-1 (`:37-79`), N-1 (`:118-132`), N-2 (`:134-137`), N-3 (`:139-141`); `00-consolidated.md` rows 05/H-1, 05/N-1, 05/N-2, 05/L-1 and recommendation R2. · Status: pending

The four findings share one surface (`POST /unlock/sign` and what the leader does with what comes back over the peer channel) and one fix set; they land as one change so that no intermediate state leaves the endpoint authenticated but still burn-agnostic, or burn-aware but still open.

## 1. Finding

`crates/hawkeye/src/api.rs:111-119` routes `POST /unlock/sign` to `verify_and_sign_unlock` (`crates/hawkeye/src/engine/burn.rs:406-531`) with no authentication; `crates/hawkeye/src/peers.rs:120-124` states this as the v1 design ("every answer is verified by the caller, so the channel needs no authentication of its own"). The endpoint checks that the transaction spends one `WYEC` vault of the set, creates exactly one intent, and that the intent classifies `MatchedBurn`/`MatchedRoll` against the local ledger; it then signs through `sign_once_ycash` keyed by `(YcashUnlock, set, vault prevout)` (`burn.rs:502-516`; `crates/hawkeye-store/src/signonce.rs:438-478`) and the node's `set_signunlock`, whose own guard is also per prevout (`ycash-dd/src/rpc/vault.cpp:1463-1475`). Nothing marks the burn as "signed for" at sign time (`matcher_burn` derives `consumed_by` from *mined* intents only, `crates/hawkeye-store/src/burns.rs:285-312`), nothing checks who asks, and nothing checks that the requester is the burn's assigned leader. With `unlockThreshold = 1` (HK-1, the mainnet shape) the response carries a complete set signature, and the endpoint has no legitimate caller at all (`complete_unlock` never contacts peers when its own node's signatures suffice, `burn.rs:347-357`).

Three attacks follow, none needing a bond, a member key or any Ycash stake, only TCP reachability to one attestor's API (which `[peers] urls` forces every mainnet deployment to expose at least to the other attestors' networks). **(H-1, loss, conditional)**: burn `n` to a recipient the attacker controls, build `k` unlocks of `k` different vaults each paying burn `n` with the `HKB1` memo and attacker-funded fee inputs, get each signed (a different prevout is a fresh sign-once key on both guards), broadcast all `k`; each is a consensus-valid intent; the watchers classify the second and later ones `unmatched:consumed-burn:benign-race` and cancel them if a cancel confirms within `delay`; if cancels miss (N-2 below), up to `cap − epochUsed` leaves the bridge against one burn. **(N-1, liveness, certain)**: for a *victim's* burn `n`, get one unlock of vault `V` with attacker fee inputs signed at member `M` and never broadcast it: `M`'s ledger and `M`'s wallet now hold a sign-once record for `V` (so `M` can never unlock or roll `V` for anything else), and when `M` is the leader for `n`, `signed_unlock_for` (`burn.rs:107-131`) finds the attacker's hex (it names nonce `n`) and `post_unlock` re-sends it every tick (`:145-152`); `vault_send` → `SignWalletInputs` skips inputs the wallet does not own (`vault.cpp:753-765`), broadcast is rejected, `unlock_failed`, **no other vault is tried**; takeover moves the burn to the next member, where the attacker has done the same. One HTTP request per member per burn stalls that redemption indefinitely. **(L-1, liveness, `unlockThreshold > 1` only)**: `complete_unlock` adopts any peer answer with more selector-1 pushes (`burn.rs:365-372`, count by `unlock_signatures` `:391-399`) without checking that it is the same unsigned transaction or that the pushes are valid member signatures; a peer that returns the same transaction with junk pushes makes `vault_send` fail every tick and the peer order is fixed, so one such peer blocks the leader until takeover (then the next leader asks the same peer). **(N-2, the quantitative gap H-1 drives through)**: `watch.rs::cancel` (`crates/hawkeye/src/engine/watch.rs:352-378`) signs on its own node only, so a `cancelThreshold > 1` deployment can never complete a cancel; and at `cancelThreshold = 1` each cancel is one transaction funded from confirmed P2PKH coins (`Fund`, `vault.cpp:716-746`, `nDepth ≥ 1`), so an attestor with few UTXOs sends few cancels per block and a flood of `k` intents can outrun it within `delay`. The verifier also notes (N-3) that the endpoint reads the vault with `getrawtransaction`, not `gettxout` (`burn.rs:425-440`), so its own checks are weaker than its doc comment says (the node's `FindTemplateInput` refuses a spent vault, `vault.cpp:1412-1434`, so this is hygiene).

## 2. Root cause

- `crates/hawkeye/src/api.rs:24-33` — the router adds no authentication layer; `:111-119` — `unlock_sign` handler.
- `crates/hawkeye/src/peers.rs:120-124` — the "no authentication in v1" decision; `:200-216` — `UnlockSignRequest { hex }` carries nothing about the requester; `:264-286` — the client sends no credentials.
- `crates/hawkeye/src/engine/burn.rs:406-531` — `verify_and_sign_unlock`: no requester check, no `unlockThreshold == 1` gate, no leader check, no burn-level sign-once (`:502-516`), vault read via `getrawtransaction` (`:425-440`).
- `crates/hawkeye-store/src/signonce.rs:98-108, 438-478` — `YcashSignKey` = `(domain, set_id, prevout)`; no burn dimension. Schema `crates/hawkeye-store/src/schema.rs:133-143` (`sign_once_ycash`, PK `(domain, set_id, prevout_txid, prevout_vout)`), immutable by trigger `:186-189`.
- `crates/hawkeye/src/engine/burn.rs:107-131` — `signed_unlock_for` reuses any record naming the nonce, whatever its origin; `:145-152, 210-236` — resend with no fallback.
- `crates/hawkeye/src/engine/burn.rs:347-387` — `complete_unlock` adopts a longer scriptSig unverified; `:391-399` — `unlock_signatures` counts pushes only.
- `crates/hawkeye/src/engine/watch.rs:352-378` — `cancel` signs on its own node only; no peer gathering, no capacity awareness.
- `ycash-dd/src/rpc/vault.cpp:716-746` (`Fund`: confirmed P2PKH only, coins locked in memory), `:753-765` (`SignWalletInputs` skips foreign inputs), `:1438-1527` (`SignSetInPlace`, per-prevout record) — identical on `ycash6` (`src/rpc/vault.cpp`, same functions; the audit's `cmp` of the vector files and the shared RPC contract apply). Consensus is burn-agnostic by design (`src/vault/state.cpp:484-545`): the node cannot help here, and must not (plan §10 rule: Hawkeye never needs a node change).

## 3. Fix options considered

**Peer authentication: mutual TLS vs member-key-signed requests.**

| | mTLS (pinned peer certificates) | Member-key-signed requests (HTTP signature headers) |
|---|---|---|
| Authorisation = set membership | No: a certificate says nothing about `SET_JOIN`/`SET_REMOVE`; a rotated-out member keeps a valid cert until operators rotate certs out of band | Yes: the server recovers the signer and checks it against `set_getinfo.memberlist` (`current`), which already drives `is_current_member`, `live()` and `guardian_mismatch`; rotation on Ycash is the rotation |
| Key material | A second secret per attestor (cert key), its own ceremony, expiry, renewal, distribution of every peer's cert to every other peer, a CA or a pinned-fingerprint list in `[peers]` | The member key the daemon already loads (`ctx.key`), no new secret, no distribution: public keys are on chain |
| Dependencies (rule 6, exact pins, `cargo-deny`) | `axum-server`/`tokio-rustls` + `rustls-pemfile` on the server, client certs through `reqwest` (`rustls-tls` feature already on): 2–3 new pinned crates | `k256`/`sha2` already in `hawkeye-core` (`setsig.rs`: `sign_compact`, `recover_compact`), `hex`, `axum` middleware: no new crate |
| Replay | Transport-level: none at the request layer; a captured request body can still be replayed inside a session only by the TLS peer | Needs an explicit timestamp + nonce (specified below) |
| Confidentiality | Yes | No, but nothing on this channel is secret (unlock hex, evidence bundles and act hex are all public once broadcast); TLS is still recommended as transport (`https://` peers, §4.1) |
| What it protects | Every route | The routes that sign (`/unlock/sign`, `/slash/sign`, the new `/cancel/sign`); the read-only routes stay public (users self-submit from `/locks/<id>`, plan §6 "Operations") |

**Recommendation: member-key-signed requests, with TLS as transport and `peers.allow_from` as an optional network-level belt.** mTLS alone was rejected because authorisation must follow the Ycash set, not a certificate list; mTLS *in addition* is allowed by this design (an operator may terminate TLS with client-certificate checks in a reverse proxy) but is not what the daemon relies on.

**Gate or remove `/unlock/sign` at `unlockThreshold = 1`.** Removing the endpoint would make non-HK-1 deployments (devnet `unlockThreshold 2` scenarios, the §4.2 "9 / 6 / 7" shape the owner's O-2 preferred) impossible; gating on the live set parameter keeps one binary for both. Chosen: gate (refuse, 403, with a start-up log line), not remove.

**Per-burn sign-once: a column on `sign_once_ycash` vs a side table.** A column would need a table rebuild of an immutable `WITHOUT ROWID` table and a backfill that decodes memos in SQL (impossible). A side table `sign_once_unlock_burn` written in the same transaction, with a Rust backfill at migration time, keeps `sign_once_ycash` untouched. Chosen: side table.

**Fallback for an unsendable signed unlock.** Rejected: re-signing another spend of the *same* vault (a different sighash over one prevout is `SET_EQUIVOCATION`, and the node refuses it with `set-sign-once` anyway). Rejected: silently signing another vault for the same burn (that is exactly the double release the per-burn dimension exists to stop). Chosen: a *dead marker* on the burn's record, set only when the recorded transaction can no longer confirm (a fee input is spent by a transaction ≥ `C_Y` deep while the vault is still unspent), after which one new vault may be signed; plus takeover, which already moves the burn to the next member and is the primary liveness answer once the endpoint is authenticated.

**Cancel capacity.** Rejected: batching cancels (S-1: one template input per transaction, consensus). Rejected: using unconfirmed own change for fee inputs from Hawkeye (the node's `Fund` is what picks inputs; changing it is a node change — recorded as the optional CR-N5 in §4.6, not required). Chosen: Hawkeye measures its fee-coin capacity, alarms below a floor, offers a `split-coins` command, prioritises cancels by deadline, and gathers cancel co-signatures from peers when `cancelThreshold > 1`.

## 4. Recommended fix

### 4.1 Peer request authentication (`crates/hawkeye/src/peers.rs`, `api.rs`, new `crates/hawkeye/src/peer_auth.rs`)

**Headers** on every `POST` to a signing route (`/unlock/sign`, `/slash/sign`, `/cancel/sign`):

| Header | Value |
|---|---|
| `X-Hawkeye-Member` | 66 lowercase hex chars: the requester's 33-byte compressed member key (`hex::encode(ctx.me)`) |
| `X-Hawkeye-Time` | Unix seconds, decimal ASCII, no leading zeros |
| `X-Hawkeye-Nonce` | 32 lowercase hex chars: 16 random bytes (`rand` is not a dependency: use `alloy::primitives::B128::random()` or read `/dev/urandom` via `std::fs`; both are already reachable without a new crate) |
| `X-Hawkeye-Sig` | 130 lowercase hex chars: the 65-byte compact recoverable signature below |

**Signed message** (`hawkeye_core::peerauth::request_msg`, new module in `hawkeye-core` so it is pure and vectored):

```
preimage =
    b"HawkeyePeerReq"                          (14 bytes, ASCII, no terminator)
 ‖  set_id                                    (32 bytes, internal byte order: ctx.params.set_id)
 ‖  deployment.chain_id                       (u64, little-endian, 8 bytes)
 ‖  deployment.bridge                         (20 bytes: ctx.params.deployment.bridge.0)
 ‖  u8(len(method)) ‖ method                  ("POST": 0x04 "POST")
 ‖  u16 LE len(path) ‖ path                   (the route as matched, no query, no host: "/unlock/sign")
 ‖  timestamp                                 (u64 LE, 8 bytes: the X-Hawkeye-Time value)
 ‖  nonce                                     (16 bytes: the X-Hawkeye-Nonce value)
 ‖  sha256(body)                              (32 bytes: SHA-256 of the exact request body bytes as sent)
msg = sha256d(preimage)
sig = sign_compact(member_key, msg)           (hawkeye_core::setsig::sign_compact: 65 bytes, header 31..34, low S)
```

The body is hashed as raw bytes; nothing is canonicalised. The server therefore reads the body with `axum::body::Bytes` first, verifies, then deserialises. Binding `set_id` and the deployment makes a request for one bridge useless on another (a devnet and mainnet attestor sharing a key cannot be cross-fed); binding `path` and `method` stops a `/slash/sign` body being replayed to `/unlock/sign`.

**Server verification** (`peer_auth::verify(ctx, method, path, headers, body) -> Result<PubKey33, AuthError>`), applied as an axum `from_fn_with_state` middleware on the three signing routes only (`api.rs::router`: `Router::new().route("/unlock/sign", post(unlock_sign)).route("/slash/sign", post(slash_sign)).route("/cancel/sign", post(cancel_sign)).route_layer(middleware::from_fn_with_state(ctx.clone(), peer_auth::layer))`, then `.route("/healthz", …)` etc. added after so the layer does not cover them):

1. All four headers present and well-formed, else `401 {"error":"peer auth: missing or malformed <header>"}`.
2. `|now − timestamp| ≤ 60` s (`PEER_AUTH_SKEW_SECS = 60`), else `401 … stale`.
3. `(member, nonce)` not in the replay cache (`Mutex<HashMap<(PubKey33, [u8;16]), u64 /*expiry*/>>` on `Ctx`, pruned on insert; entries live `2 × PEER_AUTH_SKEW_SECS`), else `401 … replayed`. Insert *after* the signature verifies.
4. `recover_compact(sig, msg)` (`setsig.rs:145-156`) must equal the `X-Hawkeye-Member` key, else `401 … signature does not recover to the member`.
5. The key must be a **current** member of the set: read from a snapshot the engine refreshes every tick (`Ctx.members: Arc<RwLock<Vec<Member>>>`, written in `refresh_set`, `engine/mod.rs:296-330`); fall back to `set_getinfo` when the snapshot is empty (`hawkeye status` runs no engine). A member in its exit delay is **not** current and is refused; else `403 … not a current member`.
6. The verified key is passed to the handler as an extension (`Extension<PeerMember>`), and every handler logs it (`requester = %hex::encode(key)`).

**Client** (`Peers`): `Peers::new(urls, Option<SecretKey>, set_id, deployment)`; every signing POST serialises the body once to `Vec<u8>`, signs, sets the headers, sends those exact bytes. `GET /locks`, `GET /burns` are unchanged and unsigned.

**Response authentication** (same shape, cheap, closes the MITM-swaps-the-answer case that L-1's content check alone does not): the server adds `X-Hawkeye-Member`/`X-Hawkeye-Sig` on signing responses, over `sha256d(b"HawkeyePeerResp" ‖ request_msg (32) ‖ sha256(response_body))`; the client verifies the signer is a current member and, for `/unlock/sign` and `/cancel/sign`, that it is the peer whose signature it then counts (§4.4). A response without the headers is refused on mainnet (`[peers] require_auth`, below).

**Config** (`config.rs` `PeersSection`): `require_auth: Option<bool>` (default `true`; `false` is refused on mainnet, allowed on regtest for the devnet's older scripts during the transition), `allow_from: Vec<String>` (CIDRs; when non-empty the middleware also checks the peer address — behind a reverse proxy this is the proxy's address, so document it as a belt, not the mechanism). On mainnet every `[peers] urls` entry must be `https://` or loopback (same rule as L-2's for `ycash.rpc_url`; implement both in one `config::check_transport` helper).

**Vectors**: `hawkeye-core/tests/peerauth.rs` with fixed inputs (set id `0x11…11`, chain 31337, bridge `0x5FbDB2…0aa3`, `POST /unlock/sign`, timestamp `1760000000`, nonce `00…0f`, body `{"hex":"00"}`) and the expected `msg` hex committed; the Rust signer/verifier round-trips and a changed byte in any field changes `msg`.

### 4.2 Gate `/unlock/sign` at `unlockThreshold = 1`; co-sign only for the burn's leader

In `verify_and_sign_unlock`, **before any node call**: read `ctx.members`/`set` snapshot (or `set_getinfo`) and

```rust
let need = set.params.unlockthreshold;
anyhow::ensure!(need > 1, "unlock co-signing is disabled: the set's unlockThreshold is 1 (HK-1); the leader completes its own unlocks");
```

`startup_checks` (`daemon.rs:62-126`) logs `event = "peer_unlock_sign_disabled"` when `unlockthreshold == 1` so operators see the endpoint is inert. `complete_unlock` (`burn.rs:347`) already returns early at threshold 1; add a debug assertion that it never calls peers in that case.

Then, for a `MatchedBurn { nonce }`: load `t.burn(&BurnKey::new(deployment, nonce))` and require `b.leader == Some(requester)` (the verified `PeerMember`), where takeover has already rewritten `leader` in this ledger (`burns()`, `burn.rs:51-65`) — so "the leader or its takeover successor" is exactly "the leader in this ledger"; refuse otherwise with `"the requester is not the burn's leader here (leader = …)"`. For a `MatchedRoll`: require `requester == mint_leader_for(&lock_id(&vault.outpoint), live, since, takeover)` as `roll.rs:169-174` computes it. Also replace the `getrawtransaction` vault read with `gettxout(txid, vout, true)` (N-3) so a spent vault is refused here with a clear message rather than by the node.

### 4.3 Per-burn sign-once dimension (`hawkeye-store`)

**Schema V6** (`schema.rs`, append to `MIGRATIONS`):

```sql
-- Sign-once, the burn an UNLOCK signature pays (05/H-1): one live vault per burn, ever. A row is
-- dead only when its transaction can no longer confirm (a fee input spent ≥ C_Y deep while the
-- vault is unspent); dead rows are the only mutation, and only from NULL.
CREATE TABLE sign_once_unlock_burn (
    set_id        BLOB    NOT NULL CHECK (length(set_id) = 32),
    chain_id      INTEGER NOT NULL CHECK (chain_id >= 0),
    bridge        BLOB    NOT NULL CHECK (length(bridge) = 20),
    nonce         INTEGER NOT NULL CHECK (nonce >= 0),
    prevout_txid  BLOB    NOT NULL CHECK (length(prevout_txid) = 32),
    prevout_vout  INTEGER NOT NULL CHECK (prevout_vout >= 0),
    origin        TEXT    NOT NULL CHECK (origin IN ('leader', 'cosign', 'drill')),
    signed_at     INTEGER NOT NULL,
    dead_reason   TEXT,
    dead_height   INTEGER,
    CHECK ((dead_reason IS NULL) = (dead_height IS NULL)),
    PRIMARY KEY (set_id, chain_id, bridge, nonce, prevout_txid, prevout_vout),
    FOREIGN KEY (set_id, prevout_txid, prevout_vout)
        REFERENCES sign_once_ycash (set_id, prevout_txid, prevout_vout)
) WITHOUT ROWID;
CREATE INDEX sign_once_unlock_burn_live ON sign_once_unlock_burn (set_id, chain_id, bridge, nonce)
    WHERE dead_reason IS NULL;
CREATE TRIGGER sign_once_unlock_burn_immutable_update BEFORE UPDATE ON sign_once_unlock_burn
    WHEN OLD.dead_reason IS NOT NULL OR NEW.set_id != OLD.set_id OR NEW.nonce != OLD.nonce
      OR NEW.prevout_txid != OLD.prevout_txid OR NEW.prevout_vout != OLD.prevout_vout
      OR NEW.origin != OLD.origin OR NEW.signed_at != OLD.signed_at
BEGIN SELECT RAISE(ABORT, 'sign-once records are immutable'); END;
CREATE TRIGGER sign_once_unlock_burn_immutable_delete BEFORE DELETE ON sign_once_unlock_burn
BEGIN SELECT RAISE(ABORT, 'sign-once records are immutable'); END;
```

(`sign_once_ycash`'s PK includes `domain`; the FK above needs a unique index on `(set_id, prevout_txid, prevout_vout)` restricted to `domain = 'ycash-unlock'` — SQLite FKs cannot target partial indexes, so either drop the FK and enforce the pairing in Rust, or key the FK on all four columns with a constant `'ycash-unlock'` column. Keep it simple: no FK, enforce in `sign_once_unlock`.)

**Backfill** in `Store::init` after `migrate` when the version crossed 5→6: iterate `sign_once_ycash WHERE domain = 'ycash-unlock'`, decode `signed_hex` with `hawkeye_ycash::tx::Transaction::decode_hex` — `hawkeye-store` must not depend on `hawkeye-ycash`; instead expose `Store::backfill_unlock_burns(decode: impl Fn(&str) -> Option<(Deployment, u64)>)` and call it from `daemon::connect` with a closure that uses `parse_memo_script_for` (as `signed_unlock_for` does) — and insert rows with `origin = 'leader'` (every pre-fix record was written by the leader path, the drill or the co-sign path; mark pre-fix rows `'leader'` and say so in the migration comment). Record completion in `chain_cursor`-style metadata (`PRAGMA user_version` is already 6; add a `meta(key TEXT PRIMARY KEY, value TEXT)` table in V6 with `backfill_unlock_burns = done`).

**API** (`signonce.rs`):

```rust
pub struct UnlockBurn { pub key: BurnKey, pub origin: UnlockOrigin }  // Leader | Cosign | Drill

/// `sign_once_ycash` for the unlock domain with the burn dimension: refused
/// (`SignOnceConflict { domain: "ycash-unlock", key: "burn <chainId:bridge:nonce>", .. }`)
/// when a live row names this burn with another prevout. `burn = None` is only for rolls.
pub fn sign_once_unlock<F, E>(&self, key: &YcashSignKey, burn: Option<&UnlockBurn>, built_hex: &str, sign: F) -> Result<YcashSignRecord>
```

Order inside the transaction: (1) existing per-prevout record → same `built_hex` returns it (and the burn row must already exist and match, else `corrupt`); (2) `SELECT prevout FROM sign_once_unlock_burn WHERE … AND dead_reason IS NULL` → any row with a different prevout → `SignOnceConflict`; (3) call `sign`; (4) insert `sign_once_ycash` then `sign_once_unlock_burn`. New lookups: `live_unlock_for_burn(&BurnKey) -> Option<(OutPoint, UnlockOrigin)>` and `mark_unlock_dead(&BurnKey, &OutPoint, reason, height)`.

**Callers**: `post_unlock` (`burn.rs:193-200`) passes `Some(UnlockBurn { key: b.key, origin: Leader })`; `verify_and_sign_unlock` (`:509-516`) passes `Cosign` with the `BurnKey` from the `MatchedBurn` classification; `roll.rs:245` passes `None`; `cli.rs:491` (`rogue-unlock --replay-burn`, drill D-3) passes `Drill` **and** a `allow_double: true` flag that skips step (2) — the drill exists to produce the double release the watchers must cancel, is gated by `drill_gate` (`cli.rs:369-374`, never on mainnet), and must keep working.

The node side stays per prevout; no change request is needed because every bridge signature passes through Hawkeye.

### 4.4 Validate what is reused and what peers return

**`signed_unlock_for` (`burn.rs:107-131`)**: iterate `sign_once_unlock_burn` for the burn instead of every vault's record; reuse only a live row with `origin = 'leader'`; before returning the hex, check every non-template input is this wallet's (`listunspent 0 9999999 [address]` is heavy; use `gettxout` + `validateaddress(address).ismine` on the P2PKH address of each fee input, or the stock `getrawtransaction … 1` `vin` decode followed by `validateaddress`). A record whose fee input is already spent by a transaction with ≥ `C_Y` confirmations while the vault is unspent → `mark_unlock_dead(reason = "fee input <op> spent by <txid> at <h>")`, alarm `unlock-dead` (nonce, vault, reason), and the next tick builds on another vault. An unsendable record whose conflict is shallower than `C_Y` → alarm only, keep resending.

**`complete_unlock` (`burn.rs:347-387`)**, adopting a peer's answer only if **all** hold:

1. `Transaction::decode_hex(&r.hex)` succeeds and the transaction equals ours in every field **except** the selector-1 input's `script_sig` (compare `version`, group id, `inputs[i].prevout`/`sequence` for all `i`, every `inputs[j].script_sig` for `j ≠ template`, all outputs, locktime, expiry).
2. The template input's scriptSig parses (`parse_selector(Vault, …)`) to selector 1 with `args.len() ≤ unlockthreshold` and total scriptSig length ≤ `1 + 65 × unlockthreshold + 1 + 15` bytes (push opcodes), and each arg is exactly 65 bytes.
3. Each arg verifies: `recover_compact(arg, set_sig_msg(set_id, 1, prevout, sighash))` (`setsig.rs:52-60, 145-156`) where `sighash` is the one our own node reported when we signed (`rec.sighash` from the stored record — the same transaction has the same sighash) recovers to a **distinct current member**; the set includes every signer we already had.
4. `args.len() > have`.

A peer whose answer fails any check is logged `unlock_signature_rejected` with the reason and skipped; the loop continues to the next peer; a peer that fails twice in a row is deprioritised for that burn (`mem.peer_backoff: HashMap<String, u32>`).

`unlock_signatures` (`:391-399`) stays as the counter but is only called on hex that passed the shape check.

### 4.5 Cancel gathering and capacity (N-2)

**`POST /cancel/sign`** (new, authenticated as §4.1): request `{ "hex": <cancel tx hex with the signatures so far>, "intent": "<txid:vout>" }`; the server (`verify_and_sign_cancel`) decodes the transaction, requires its template input to be `intent`, classifies the intent on its **own** ledger exactly as `watch()` would (`handle_unmatched`'s inputs: the intent row must exist here and be unmatched, or not exist in the ledger and its burn not matched — refuse a cancel of an intent this ledger has `Matched`), requires `requester` to be a current member, then `sign_once_ycash` with `cancel_key(set_id, intent)` (`watch.rs:422-428`) and `set_signcancel`. Response `{ hex, complete, signatures, required }` plus the response headers. `Engine::cancel` (`watch.rs:352-378`): after its own `set_signcancel`, if `!complete` and `cancelthreshold > 1`, gather over peers with the same adoption checks as §4.4 (role 2, `set_sig_msg(set_id, 2, …)`), then `vault_send`.

**Capacity**: a `fee_coins()` check in `refresh_set` every 20 ticks — `listunspent 1` filtered to `TX_PUBKEYHASH` with `amount ≥ VAULT_RPC_FEE + VAULT_RPC_MIN_CHANGE` (read both from `vault_getinfo` if exposed, else the constants in `vault.cpp`) — published in `Status.fee_coins` and `/metrics` (`hawkeye_fee_coins`); alarm `fee-coins-low` when `< FEE_COINS_FLOOR` (`8`, plan §5.5 / finding (76)), `fee-coins-exhausted` at 0. **`hawkeye split-coins --count N [--amount YEC]`** (new CLI): one stock `sendmany` from the wallet to `N` fresh own addresses, so an operator restores capacity in one command. **Cancel ordering** in `watch()`: process cancellable unmatched intents by `confirmed_height + delay` ascending (nearest deadline first), and on `RPC_WALLET_INSUFFICIENT_FUNDS` continue to the next intent only after logging `cancel_unfunded` and raising `fee-coins-exhausted` (so the operator sees it on the first miss, not after `delay`).

### 4.6 Optional change request (plan §10): CR-N5

| # | Repo | Change | Why | Blocking? |
|---|---|---|---|---|
| CR-N5 | ycash-dd, ycash6 | `vault_buildcancel` / `Fund` may spend this wallet's **own unconfirmed change** (`nDepth ≥ 0` for outputs of transactions this wallet sent) so that `k` cancels can chain within one block from one coin | raises per-block cancel capacity from "number of confirmed fee coins" to "number of cancels the mempool chain limit allows"; wallet-only, no consensus footprint | no — `split-coins` and the floor alarm are sufficient at HK-1 |

Hawkeye commits nothing under `ycash-dd`/`ycash6`; the row is added to `hawkeye/docs/hawkeye-bridge-plan.md` §10 by this fix.

### 4.7 Docs

`peers.rs` module doc and plan §6 "Peer channel": replace "needs no authentication of its own in v1" with the §4.1 scheme; plan §12 add **HK-13**: "The peer channel is authenticated by member-key request signatures; `/unlock/sign` is inert at `unlockThreshold = 1`; every unlock signature is recorded per burn as well as per vault." `README.md` "Node requirement" unchanged.

## 5. Tests

- `hawkeye-core/tests/peerauth.rs`: the committed `msg` vector; field-by-field sensitivity; `recover_compact` round trip; header encoding/decoding.
- `crates/hawkeye/tests/engine.rs`:
  - `k_unlock_cosign_endpoint` (`:1688-1763`) becomes two: at `unlockThreshold = 1` the endpoint returns 403 `disabled` and calls `set_signunlock` **zero** times (assert on `mock.state().calls_to("set_signunlock")`); at `unlockThreshold = 2` (set created with that param) an unsigned request → 401, a request signed by a non-member key → 403, a request signed by a member that is not the burn's leader → 403, by the leader → signed once, repeated → same hex, zero extra node calls.
  - `k2_per_burn_sign_once`: leader signs burn `n` on `V1`; a second request (from the leader itself, signed) for burn `n` on `V2` → `SignOnceConflict` naming `burn <id>`; a roll on `V2` still signs.
  - `k3_attacker_prefilled_record_is_not_reused` (N-1): a `cosign` row for burn `n` exists; `post_unlock` builds on another vault instead of resending; and a `leader` row whose fee input is spent ≥ `C_Y` deep is marked dead and a new vault is signed (mock: spend the fee coin, mine `C_Y`).
  - `k4_peer_returns_junk_pushes` (L-1): a peer answering the same tx with two 65-byte junk pushes is rejected with `unlock_signature_rejected`, the next peer's valid answer is adopted; a peer returning a *different* unsigned transaction (changed output) is rejected.
  - `k5_cancel_cosign_endpoint`: `cancelThreshold = 2`, the watcher gathers one peer cancel signature and the cancel confirms.
  - `k6_fee_coins_alarm`: wallet with 3 coins → `fee-coins-low`; `split-coins --count 16` → cleared.
- `hawkeye-store/tests/sign_once.rs`: V5→V6 migration keeps rows and the backfill marks one `leader` row per existing unlock; `sign_once_unlock` conflict/idempotence/dead-marker semantics; dead rows cannot be un-deaded (trigger); `drill` rows with `allow_double`.
- `hawkeye-store/tests/migrations.rs`: `TABLES` gains `sign_once_unlock_burn` and `meta`.
- Devnet (`devnet/README.md` scenario `demo`): peers configured with `https://` through the devnet's reverse proxy or `require_auth = true` over plain http on regtest; the three Hawkeyes still complete D-1.

## 6. Acceptance criteria

1. An unauthenticated or non-member `POST /unlock/sign`, `/slash/sign`, `/cancel/sign` never reaches a signing closure (no `set_sign*` call on the mock, no ledger row).
2. At `unlockThreshold = 1` the endpoint is inert and says so at start-up.
3. For one burn, at most one live `sign_once_unlock_burn` row exists per attestor; a second vault can only be signed after the first row is dead, and a dead row needs a ≥ `C_Y`-deep conflicting spend.
4. `signed_unlock_for` never resends a record it did not create as leader.
5. `complete_unlock` adopts only byte-identical transactions whose extra selector-1 pushes recover to distinct current members over the stored sighash.
6. A `cancelThreshold = 2` devnet completes a cancel; `fee-coins-low` fires below 8 coins.
7. `cargo test --workspace --locked` and `HAWKEYE_REQUIRE_ANVIL=1` CI pass on both node lines' regtest (rule 5).

## 7. Risks and side effects

- **Bridge downtime**: none on the HK-1 shape (the endpoint was unused). Rolling out `require_auth = true` across a running set must be done peer by peer *with the new binary everywhere first* (an old peer cannot sign requests; an old server ignores the headers, so new→old works, old→new fails 401). Order: deploy the binary to every attestor with `require_auth = false`, then flip to `true` in one maintenance window; mainnet refuses `false`, so a mainnet set deploys straight to `true` and accepts that slash/cancel gathering is unavailable until the last attestor restarts (minutes).
- **Key rotation**: none; the scheme uses the member key. A rotated-out member's requests fail at step 5 immediately.
- **Contract redeploy**: none.
- **Ledger migration**: V6 is additive plus a backfill; take a `hawkeye.db` backup first (runbook, 05/M-3). The backfill runs once; a crash mid-backfill reruns it (idempotent inserts, `INSERT OR IGNORE`).
- **Dead marker misuse**: a wrong dead marker could let an attestor sign two unlocks for one burn — bounded by the `≥ C_Y` conflict rule and by the watchers' benign-race cancel; log it at `warn` with the full evidence.

## 8. Effort estimate and dependencies

- Peer auth (core module, middleware, client, config, vectors): 2 days.
- Gate + leader check + `gettxout`: 0.5 day.
- Store V6 + backfill + API + tests: 1.5 days.
- Reuse/adoption validation + dead marker: 1 day.
- Cancel endpoint, gathering, capacity, `split-coins`: 1.5 days.
- Docs/plan/devnet: 0.5 day. **Total ≈ 7 days**, one engineer.
- Dependencies: none must land first. `LOW-05-L-2` (transport/permissions) shares the `check_transport` helper — land this report first and let L-2 reuse it. `MEDIUM-05-M-3` (runbook) documents the rollout order above.
