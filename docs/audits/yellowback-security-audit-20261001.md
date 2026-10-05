# Yellowback ecosystem security audit — 2026-10-01

**Status (2026-10-04).** Every Critical-to-Low finding is remediated on both node lines (ycash-dd
through `02aa77cb7`, ycash6 through `0748c68a6`, both pushed 2026-10-02) and in each client repo
(§5). The owner-approved hook changes A-1 and A-7 touched `src/main.cpp` and `src/rpc/mining.cpp`,
and the tag `yellowback-v3-baseline` (ycash-dd) was re-tagged at `ff7f45947` on 2026-10-02
(previously `9da72131e`). Open: the A-5 residual (a wallet "redeem before sunset" warning in
yecwallet-dd and yew); the Info items, not yet triaged one by one (§5, last box); on-device checks
for G-4 and G-10 and a Gradle check for G-11; and the owner's choice of lightwalletd-dd's default
branch (still `master`).

**Scope.** Every writable repository of the workspace, at the commits below, after the
`docs/plans/yellowback-ycash6-plan.md` execution was declared essentially complete. The `ref/`
checkouts were consulted only to decide whether our delta introduced a defect (baseline comparison),
never audited in themselves. Nothing was built or run except read-only gates (`go build`/`go vet`
in lightwalletd-dd, `qa/yellowback-audit.sh` and `qa/yellowback-rpc-cvt.py --check` in ycash6, one
throwaway timing test against a vendored Go package, deleted afterwards). No repository was modified.

| Repository | Branch | Commit | Baseline |
|---|---|---|---|
| ycash-dd | feature/yellowback-price-attest | `a5edaa497` | ycash-legacy (v4.5.0) |
| ycash6 | feature/yellowback | `3b0dfb6e3` | ycash6-baseline / ycash6-legacy |
| librustzcash6 | feature/yellowback | `ec525fae` | librustzcash6-legacy (zero delta, verified) |
| yecwallet-dd | feature/yellowback-price-attest | `f2e2d2a` | yecwallet-legacy |
| lightwalletd-dd | feature/yellowback-price-attest | `2d33f42` | lightwalletd-legacy |
| yew | main | `839e7d5` | — |
| yolo | main | `4dc5366` | — |
| chain-viz | main | `dd87db8` | — |
| workspace | feature/yellowback-price-attest | `27ffa40` | — |

**Method.** Nine parallel read-only reviews, one per component boundary (A node overlay core,
B ycash6 port vs ycash-dd, C node RPC/wallet surface, D attestor agent and contrib tooling,
E lightwalletd-dd, F yecwallet-dd, G YEW, H yolo + chain-viz, I CI/supply chain/secrets/test
integrity), each against a shared brief (verify before reporting; cite `repo/path:line`; mark
CONFIRMED vs PLAUSIBLE; list what was checked and found sound). The coordinator then re-verified
every High finding and the cross-line claims directly in the source. Finding IDs keep their review
letter so the per-component sections (§4) can be read on their own.

Severity: **Critical** theft / consensus split / remote crash of enforcing nodes; **High** loss of
funds availability by grief, auth bypass, unauthenticated state change; **Medium** DoS needing
resources, local-only, policy weakness; **Low** hardening; **Info** completeness / documentation.

---

## 1. Verdict

**No Critical finding.** No consensus split, no theft path against an honest client, and no remote
crash of an enforcing node was found in either node line. The overlay's state machine is total,
apply/undo is byte-symmetric for every v2 and v3 table, nothing in it reads the clock, wallet,
config or floating point, and a block can only be rejected for a Yellowback reason after every
stock consensus check has passed. The ycash6 port is complete: every divergence between the two
node lines is an include rename, a documented 6.20.0 API adaptation, or a fix that landed on one
line only (listed below). The supply chain is clean: zero dependency delta in both node forks and
in librustzcash6, every Rust component commits a lockfile with no git dependencies, no secrets in
any tree or in any fork commit beyond its baseline, and no workflow in our delta uses
`pull_request_target`, `workflow_run` or repository secrets.

**Three High findings, all at the edges where a client trusts a server or the internet:**

- **G-1 / G-2 (YEW).** The mobile wallet takes every economic parameter of a mint, redeem or claim
  (vault lock and claim heights, required collateral, enforcement fee amount and payee) from its
  single lightwalletd server with no local plausibility check, and a redeem is built and
  broadcast in one call with no preview. The node's fee rules (`state.cpp:345`, `:522`) bound the
  fee only from below and accept any eligible payee, so a malicious server whose operator is an
  eligible miner can take most of a vault's collateral as the redeem fee, and any malicious server
  can lock a minter's collateral in a VOID vault until an arbitrary height. YEW's own trust
  statement ("a dishonest server cannot take your funds") currently overclaims (G-3).
- **E-1 (lightwalletd-dd).** With `--yellowback` on, the three pre-existing transparent-address
  RPCs run a quadratic base58 decode on an unbounded client string before the baseline's
  length-bounding regex: a regression against the baseline giving any unauthenticated Internet
  client a cheap CPU-DoS (measured ×4 per doubling; one 4 MB request ≈ minutes of a core).

**Fourteen Medium findings**, grouped by theme in §2. The most consequential for the node lines:
MP-1 runs a full block evaluation including the snapshot per vault-spend candidate before script
verification with no misbehaviour score (A-1); a cheap, plausible way to pin every seated attestor
and halt ARMED minting for a pin window (A-2); the blocking carrier wait can wedge the RPC server
(C-2); `importwallet` lacks the H8 reconcile on ycash-dd (C-1/B-3); and on ycash6 a stock peer on a
minority fork longer than 64 blocks is banned (B-1).

**Completeness.** Every plan phase is delivered. The gaps that matter: the `rpcfix` backport to
ycash-dd is unmerged, so the two node lines answer `claimable`/`poolFresh` differently today (B-2,
C-4); four existing functional scripts, including stock parity and wallet lifecycle, are
allow-listed out of ycash-dd's "every script runs" gate (I-1); a "blocking" rule-tag check is
`continue-on-error` (I-2); `nodedatacheck_test` is never run by yecwallet-dd's CI (F-6); and the
ycash6 review document's §7/§8.4 are stale against the plan (B-7, I-11).

---

## 2. Cross-cutting themes

1. **Clients trust their server for economic parameters.** YEW (G-1, G-2) fully; YecWallet (F-1)
   shows an estimate the node is not bound to because `yed_mint` has no collateral cap argument
   and `yed_claim` no burn/out bounds. The cheapest ecosystem-wide fix is node-side: optional
   `maxCollateralZat` on `yed_mint` and `maxBurnCents`/`minOutZat` on `yed_claim` (C/F-1), plus
   client-side recomputation of `max(FEE_MIN, collateral·FEE_BPS/10⁴)` and the height identities
   from per-network constants (G-1, G-2).
2. **Rate limiters keyed on client-supplied forwarded-IP headers.** lightwalletd-dd `x-real-ip`
   (E-2) and chain-viz `X-Forwarded-For` in `--public` mode (H-11): both bypassable and both grow
   an unbounded map. Same fix in both: honour the header only from a configured trusted-proxy
   CIDR, cap the map.
3. **Unbounded input on internet-facing listeners.** lightwalletd address strings (E-1), yolo
   stratum line length and connection count (H-1, H-2), unmetered `submitblock`/`validateaddress`
   forwarding (H-3, H-4), attestor and quote tools' unbounded HTTP bodies (D-3), chain-viz without
   `--public` (H-12).
4. **Non-finite numbers from price venues.** The Rust attestor panics on `"inf"` volume strings
   and turns a `"nan"` price into a 0 µUSD sample (D-1); the Python quote tool silently poisons a
   source's VWAP (D-2). The two aggregators diverge on the same input.
5. **Fixes landing on one node line only**, against the owner's "fix both node lines" rule:
   `importwallet` H8 guard (ycash6 only; C-1, B-3), `claimable`/`poolFresh` (ycash6 merged,
   ycash-dd on unmerged `rpcfix`; B-2, C-4), devnet `kill_nodes` grace (ycash6 only; D-10).
6. **CI pinning.** Every repository pins third-party actions by mutable tag; the node CI builds
   `chain-viz@main` unlocked inside its merge gate (I-5) and the nightly builds the attestor
   agent without `--locked` (I-6); `curl | sh` rustup and an unchecksummed Go tarball (I-4, E-6);
   yolo and chain-viz build on floating `stable` (H-16, I-8); yolo has no CI (I-13); no advisory
   scan for the attestor agent's 392-crate tree (I-7).
7. **Enforcement gaps are anyone-can-spend windows** (A-5): every vault past `claimHeight` is
   spendable without burn whenever enforcement is off (IBD, reindex, valve trip, catch-up
   suppression, halt, sunset). As designed, but undocumented in the threat model, and the
   mechanism behind the theft leg of G-1.

---

## 3. Consolidated findings

| ID | Sev | Component | Status | Title |
|---|---|---|---|---|
| G-1 | High | yew | CONFIRMED (grief) / PLAUSIBLE (theft) | Mint vault parameters from the server used unchecked: lying server locks collateral in a VOID vault until an arbitrary height |
| G-2 | High | yew | CONFIRMED | Enforcement-fee amount and payee dictated by the server with no bound; redeem built and broadcast with no preview |
| E-1 | High | lightwalletd-dd | CONFIRMED | Quadratic base58 decode on unbounded input before the length check on three baseline taddr RPCs (regression) |
| A-1 | Medium | both nodes | CONFIRMED | MP-1 evaluates a full block (SNAP included) per vault-spend candidate, before script verification, DoS 0 |
| A-2 | Medium | both nodes | PLAUSIBLE | PIN-2 can be triggered by cheap VOID mints to pin every seated attestor and halt ARMED minting |
| B-1 | Medium | ycash6 | CONFIRMED | Stock peers on a minority fork > 64 blocks are banned by enforcing 6.20.0 nodes (headers-loop skip × note cap) |
| C-1 / B-3 | Medium | ycash-dd | CONFIRMED | `importwallet` imports transparent keys without the H8 reconcile; YED unlocked until the next block |
| C-2 | Medium | both nodes | CONFIRMED | `WaitForCarrier` blocks an HTTP worker up to 600 s; four waits wedge the RPC server |
| C-3 | Medium | both nodes | CONFIRMED / PLAUSIBLE | Two-step mint: supply cap judged at inclusion, so a mint can confirm VOID and lock collateral until `lockHeight` |
| D-1 | Medium | attestor agent | CONFIRMED | `"inf"`/`"nan"` numeric strings from a venue: panic crash-loop or a 0 µUSD sample |
| D-3 | Medium | quote tool / agent | CONFIRMED | Serial fetch with per-socket timeout stalls on a slow-drip venue; no body size cap |
| D-5 | Medium | attestor subscriber | CONFIRMED / PLAUSIBLE | Unthrottled public gossip subscriber: every frame → one `yed_addattestation` + secp verify |
| E-2 | Medium | lightwalletd-dd | CONFIRMED | Rate limiter trusts client-supplied `x-real-ip`; bypass and unbounded map |
| E-3 | Medium | lightwalletd-dd | CONFIRMED | 15 of 19 methods are unauthenticated, unlimited synchronous node calls |
| F-1 | Medium | yecwallet-dd | CONFIRMED | Mint/claim confirmation shows an estimate the node is not bound to; no collateral cap sent |
| G-3 | Medium | yew | CONFIRMED | Trust statement overclaims given G-1/G-2 |
| G-4 | Medium | yew | PLAUSIBLE | TLS on iOS cannot work with system roots; no CA-pin field |
| H-1 | Medium | yolo | CONFIRMED | Stratum reader has no line-length bound |
| H-2 | Medium | yolo | CONFIRMED | No connection cap, no idle disconnect (slow-loris) |
| H-3 | Medium | yolo | CONFIRMED | `mining.submit` forwarded unmetered with no local PoW check; floods starve the poller |
| H-11 | Medium | chain-viz | CONFIRMED | `--public` rate limiting trusts `X-Forwarded-For` unconditionally |
| I-1 | Medium | ycash-dd CI | CONFIRMED | "Registered but never run" gate allow-lists four existing scripts no job runs |
| A-3 | Low | both nodes | CONFIRMED | BLK-3 exception boundary missing on mempool, template, sweep and RPC paths |
| A-4 | Low | both nodes | CONFIRMED (latent) | PIN-1 treats an undefined `aMint == 0` row as the window minimum |
| A-5 | Low | both nodes | CONFIRMED (design) | Every enforcement gap makes vaults past `claimHeight` anyone-can-spend; undocumented |
| A-6 | Low | both nodes | CONFIRMED | Valve odometer trusts header work never contextually validated |
| B-2 / C-4 | Low | both nodes | CONFIRMED | `claimable`/`poolFresh` fix on ycash6 only; `rpcfix` unmerged on ycash-dd |
| B-4 | Low | ycash6 | CONFIRMED | V7 drops the continuity check after a skipped header |
| C-5 | Low | both nodes | CONFIRMED | Signing guard keyed without block hash: stale sig after reorg, correct re-sign refused |
| C-6 | Low | both nodes | CONFIRMED | Several read RPCs are whole-table scans under `cs_yellowback` with no paging bound |
| C-7 | Low | both nodes | CONFIRMED | H7 guard misses partial TRANSFER / vault-less REDEEM payload burns |
| D-2 | Low | quote tool | CONFIRMED | Python accepts NaN/Infinity; poisons a source's VWAP |
| D-4 | Low | both tools | CONFIRMED | Redirects followed; custom API-key header forwarded cross-host |
| D-6 | Low | attestor agent | CONFIRMED | `[subscribe] endpoints` accept `http://`; body unbounded |
| D-7 | Low | tooling | CONFIRMED | Plaintext `rpc_password` in TOML; no chmod guidance; Basic auth over http to any host |
| D-8 | Low | attestor agent | CONFIRMED | iroh secret key file created with default umask then chmod |
| E-4 | Low | lightwalletd-dd | CONFIRMED | No context propagation or timeout on node calls; streams fully buffered |
| E-5 | Low | lightwalletd-dd | CONFIRMED | `ListVaults.status` unvalidated; `count=0,skip>0` asks for 1000 rows |
| E-6 | Low | lightwalletd-dd CI | CONFIRMED | Floating toolchains, unpinned action tags, unverified Go tarball |
| F-2 | Low | yecwallet-dd | CONFIRMED | Datadir upgrade marker written before the upgrade has happened |
| F-3 | Low | yecwallet-dd | CONFIRMED | `parseDollars` turns a comma-decimal entry into a 100× amount |
| F-4 | Low | yecwallet-dd | CONFIRMED | Subscriber config with RPC password: permission window, no control-char escaping |
| F-5 | Low | yecwallet-dd | CONFIRMED | Production env var silently answers the one-way upgrade dialog |
| F-6 | Low | yecwallet-dd CI | CONFIRMED | `nodedatacheck_test` never built or run by CI |
| F-7 | Low | yecwallet-dd CI | CONFIRMED | Actions pinned by tag |
| F-8 | Low | yecwallet-dd | CONFIRMED | Attestor registration dialog parses tier/bond loosely |
| G-5 | Low | yew | CONFIRMED | `consensusBranchId` accepted from the server with no per-network table |
| G-6 | Low | yew | CONFIRMED | Unchecked multiplications on server-supplied counts in `tx.rs` |
| G-7 | Low | yew | CONFIRMED | Server streams collected unbounded |
| G-8 | Low | yew | CONFIRMED | Wrong-length txid zero-filled instead of erroring |
| G-9 | Low | yew | CONFIRMED | Mint `cents` truncated `as u32` in the payload |
| G-10 | Low | yew | CONFIRMED | Keystore items not biometric-bound; iOS data not excluded from backup |
| G-11 | Low | yew CI | CONFIRMED | Actions by tag; `cargo install` at build time; release APK signed with debug key |
| H-4 | Low | yolo | CONFIRMED | Unauthenticated `mining.authorize` is an unmetered `validateaddress` amplifier |
| H-5 | Low | yolo | CONFIRMED | Stratum password compared non-constant-time |
| H-6 | Low | yolo | CONFIRMED | Hidden `--no-flags` ships in production and silently drops the pool's price vote |
| H-8 | Low | yolo | CONFIRMED | Miner-controlled strings logged unsanitised |
| H-9 | Low | yolo, chain-viz | CONFIRMED | RPC credentials on argv over cleartext HTTP; yolo connects to `rpcbind` host |
| H-12 | Low | chain-viz | CONFIRMED | Without `--public` no resource caps |
| H-13 | Low | chain-viz | CONFIRMED | No `Origin` check on `/ws` |
| H-14 | Low | chain-viz | PLAUSIBLE | Static export embeds JSON in `<script>` without `</script>` escaping |
| H-15 | Low | chain-viz CI | CONFIRMED | Actions by tag; release job `contents: write` |
| I-2 | Low | both nodes CI | CONFIRMED | "Blocking" rule→test tag step is `continue-on-error` |
| I-3 | Low | both nodes CI | CONFIRMED | Variant jobs run scripts that SKIP without sidecar binaries |
| I-4 | Low | all CI | CONFIRMED | Third-party actions by tag; `curl \| sh` rustup; unchecksummed Go tarball |
| I-5 | Low | both nodes CI | CONFIRMED | Node CI builds `chain-viz@main` unlocked |
| I-6 | Low | both nodes CI | CONFIRMED | Nightly builds the attestor agent without `--locked` |
| I-7 | Low | agent, yolo, chain-viz | CONFIRMED | No advisory scan for the Rust components |
| I-8 | Low | yolo, chain-viz | CONFIRMED | Floating `stable` toolchain |
| I-9 | Low | both nodes CI | CONFIRMED | No-ban gate greps `DoS(` but not `Misbehaving(` |
| V-5 | Medium | both nodes | CONFIRMED | Found during validation: `yed_listclaimable` reported `attestFeeZat` 0 while the pool was stale under ARMED, so a wallet's `minOutZat` floor (F-1) under-stated the fee and the claim was refused — fixed: ycash-dd `ba793f1c1`, ycash6 `9e529e378` |
| A-7, A-8, B-5, B-6, B-7, C-8..C-11, D-9..D-12, E-7..E-11, F-9..F-11, G-12, H-7, H-10, H-16, H-17, I-10..I-14 | Info | various | — | Completeness and documentation items; see §4 |

---

## 4. Recommended order of work

1. **Node contract additions that fix two clients at once:** `maxCollateralZat` on `yed_mint`,
   `maxBurnCents`/`minOutZat` on `yed_claim` (F-1, G-1); both lines, contract JSON, wallets.
2. **YEW:** local validation of every server-supplied parameter from per-network constants;
   redeem preview/confirm; qualify the trust statement until done (G-1, G-2, G-3). iOS roots or
   CA pin before testnet (G-4).
3. **lightwalletd-dd:** length/prefix check before decode plus a regression test, `MaxRecvMsgSize`
   (E-1); trusted-proxy CIDR and map cap (E-2); limiter on every method and an in-flight
   semaphore on `CallYed` (E-3, E-4).
4. **Both node lines together:** backport `rpcfix` and the `importwallet` guard to ycash-dd
   (B-2, B-3/C-1); bound concurrent carrier waits (C-2); MP-1 via `ProcessTx` on an overlay after
   `CheckInputs` and correct spec N6 (A-1); PIN-2 to require distinct `citedHeight` with a regtest
   case (A-2); ycash6 note-cap terminal at DoS 0 and record against F-25 (B-1).
5. **Attestor tooling:** `is_finite` guards and `total_cmp` (D-1, D-2); wall-clock deadline and
   body caps (D-3); dedup and per-seq buckets in the subscriber (D-5); `Policy::none()` (D-4).
6. **yolo / chain-viz:** line-length codec, connection semaphore, idle disconnect, local
   target check before `submitblock` (H-1..H-3); trusted-proxy handling and unconditional caps
   (H-11, H-12); gate `--no-flags` to the regtest feature (H-6).
7. **CI:** drop the allow-list and port ycash6's registration check (I-1); remove
   `continue-on-error` (I-2); pin `CHAINVIZ_COMMIT`, `--locked` everywhere (I-5, I-6); SHA-pin
   actions and verify tarballs (I-4, E-6, F-7, G-11, H-15); `cargo audit` for the agent, yolo
   and chain-viz (I-7); run `nodedatacheck_test` (F-6).
8. **Documents:** threat-model rows for A-5, A-2 and the client-trust boundary; refresh the
   ycash6 review §1.2/§7/§8.4 (B-7, I-11); mapping §19 row for `-yellowbacktestfault=crash`.

---

## 5. Remediation checklist (2026-10-01, maintained as work lands)

One box per finding. A ticked box names the commit(s) and, for the node lines, both repos. "Accepted" means the owner takes the residual with the reason recorded.

*Note (2026-10-04):* nine ycash-dd hashes below were taken on the fix branches before they were
rebased, and are not ancestors of `feature/yellowback-price-attest`. The same changes on the
branch: `c07f22e89` → `e72ecc09a`, `6c827c9d8` → `20aa4c40a`, `5013ca86f` → `7d65ec32e`,
`7ff7a598b` → `090bfd692`, `352657b62` → `f13eb370b`, `cec61d924` → `3d3809048`, `f587c281a` →
`86fd8f196`, `ced3189fe` → `4f2a0044c`, `0b946b6e6` → `ff7f45947`.

- [x] **G-1** (High, yew) Mint vault parameters from the server used unchecked: lying server locks collateral in a VOID vault until an arbitrary height — fixed: yew 42ee6e6, 9de3e44, a90c2a1 (local validation of every server-supplied term; devnet confirmation in wave 2)
- [x] **G-2** (High, yew) Enforcement-fee amount and payee dictated by the server with no bound; redeem built and broadcast with no preview — fixed: yew 9de3e44, 6b18d9e (fee recomputed locally; redeem preview/confirm; residual: payee eligibility, recorded in trust.md)
- [x] **E-1** (High, lightwalletd-dd) Quadratic base58 decode on unbounded input before the length check on three baseline taddr RPCs (regression) — fixed: lightwalletd-dd 6c6422c
- [x] **A-1** (Medium, both nodes) MP-1 evaluates a full block (SNAP included) per vault-spend candidate, before script verification, DoS 0 — fixed: ycash-dd c07f22e89 (MP-1 dry-runs by ProcessTx, no SNAP; 1,000 garbage vault spends in 5.3 ms); the ATMP hook move 6c827c9d8 merged 2026-10-02 with the owner's decision to re-tag `yellowback-v3-baseline` at the merge (`ff7f45947`); ycash6 twin ported
- [x] **A-2** (Medium, both nodes) PIN-2 can be triggered by cheap VOID mints to pin every seated attestor and halt ARMED minting — fixed: ycash-dd 5013ca86f (distinct cited heights; SCHEMA_VERSION 4; model + golden vector; regtest scenario); ycash6 bfe7493d2
- [x] **B-1** (Medium, ycash6) Stock peers on a minority fork > 64 blocks are banned by enforcing 6.20.0 nodes (headers-loop skip × note cap) — fixed: ycash6 92f141ab0 (refusedNotes bounded set; enforcement case 16); ycash-dd 95ed0a358 (port), 3129e06fa (case 16 on this line)
- [x] **C-1 / B-3** (Medium, ycash-dd) `importwallet` imports transparent keys without the H8 reconcile; YED unlocked until the next block — fixed: ycash-dd a54e53503 (ycash6 already had it)
- [x] **C-2** (Medium, both nodes) `WaitForCarrier` blocks an HTTP worker up to 600 s; four waits wedge the RPC server — fixed: ycash-dd ed8f32735; ycash6 ec193e559
- [x] **C-3** (Medium, both nodes) Two-step mint: supply cap judged at inclusion, so a mint can confirm VOID and lock collateral until `lockHeight` — fixed: ycash-dd 7ff7a598b ((a) already covered by TPL-2 void-mint; (b) mempool MINTs counted; (c) documented)
- [x] **D-1** (Medium, attestor agent) `"inf"`/`"nan"` numeric strings from a venue: panic crash-loop or a 0 µUSD sample — fixed: ycash-dd df784611f (fix/audit-contrib); ycash6 f5d205d01
- [x] **D-3** (Medium, quote tool / agent) Serial fetch with per-socket timeout stalls on a slow-drip venue; no body size cap — fixed: ycash-dd 8cc5d605f, df784611f
- [x] **D-5** (Medium, attestor subscriber) Unthrottled public gossip subscriber: every frame → one `yed_addattestation` + secp verify — fixed: ycash-dd 6a7c4b628 (dedup, window, per-seq bucket; local sig pre-check left to the node, residual recorded) + follow-up 3afff8581 (the cited-height window refreshed the tip only every 5 s, so under burst mining valid frames were dropped — found by the devnet validation; now one rate-limited `yed_getinfo` before any ahead-of-window drop)
- [x] **E-2** (Medium, lightwalletd-dd) Rate limiter trusts client-supplied `x-real-ip`; bypass and unbounded map — fixed: lightwalletd-dd e5b55a2, f84ed92
- [x] **E-3** (Medium, lightwalletd-dd) 15 of 19 methods are unauthenticated, unlimited synchronous node calls — fixed: lightwalletd-dd e5b55a2
- [x] **F-1** (Medium, yecwallet-dd) Mint/claim confirmation shows an estimate the node is not bound to; no collateral cap sent — fixed: node ycash-dd ed8f32735 (`maxCollateralZat`, `minOutZat`); wallet yecwallet-dd aa26d89
- [x] **G-3** (Medium, yew) Trust statement overclaims given G-1/G-2 — fixed: yew 6c6e2e6, 854bc62
- [x] **G-4** (Medium, yew) TLS on iOS cannot work with system roots; no CA-pin field — fixed: yew c1aab01 (webpki-roots =1.0.9 + ca_pem pin; device verification pending)
- [x] **H-1** (Medium, yolo) Stratum reader has no line-length bound — fixed: yolo 392e84d
- [x] **H-2** (Medium, yolo) No connection cap, no idle disconnect (slow-loris) — fixed: yolo 392e84d
- [x] **H-3** (Medium, yolo) `mining.submit` forwarded unmetered with no local PoW check; floods starve the poller — fixed: yolo 392e84d, fda4f19 (local hash-vs-target check; Equihash verify left to the node, deliberate)
- [x] **H-11** (Medium, chain-viz) `--public` rate limiting trusts `X-Forwarded-For` unconditionally — fixed: chain-viz 48cb7e1
- [x] **I-1** (Medium, ycash-dd CI) "Registered but never run" gate allow-lists four existing scripts no job runs — fixed: ycash-dd e6af4111a (reorg_stress deleted per P-7)
- [x] **A-3** (Low, both nodes) BLK-3 exception boundary missing on mempool, template, sweep and RPC paths — fixed: ycash-dd c07f22e89
- [x] **A-4** (Low, both nodes) PIN-1 treats an undefined `aMint == 0` row as the window minimum — fixed: ycash-dd 5013ca86f
- [x] **A-5** (Low, both nodes) Every enforcement gap makes vaults past `claimHeight` anyone-can-spend; undocumented — fixed: ycash-dd 352657b62 (doc rows; wallet "redeem before sunset" warning still open for yecwallet-dd/yew)
- [x] **A-6** (Low, both nodes) Valve odometer trusts header work never contextually validated — fixed: ycash-dd cec61d924
- [x] **B-2 / C-4** (Low, both nodes) `claimable`/`poolFresh` fix on ycash6 only; `rpcfix` unmerged on ycash-dd — resolved: ycash-dd `379f9d30b`, `c23f937dd` merged to feature/yellowback-price-attest and pushed before remediation began (ycash6 `3b0dfb6e3`)
- [x] **B-4** (Low, ycash6) V7 drops the continuity check after a skipped header — fixed: ycash6 5d3bcf295
- [x] **C-5** (Low, both nodes) Signing guard keyed without block hash: stale sig after reorg, correct re-sign refused — fixed: ycash-dd f587c281a (SIGNED_MAGIC 2, v1 file migrated)
- [x] **C-6** (Low, both nodes) Several read RPCs are whole-table scans under `cs_yellowback` with no paging bound — fixed: ycash-dd ed8f32735 (yed_listtransactions accepted: L keyed by txid)
- [x] **C-7** (Low, both nodes) H7 guard misses partial TRANSFER / vault-less REDEEM payload burns — fixed: ycash-dd ced3189fe
- [x] **D-2** (Low, quote tool) Python accepts NaN/Infinity; poisons a source's VWAP — fixed: ycash-dd 8cc5d605f
- [x] **D-4** (Low, both tools) Redirects followed; custom API-key header forwarded cross-host — fixed: ycash-dd 8cc5d605f, df784611f
- [x] **D-6** (Low, attestor agent) `[subscribe] endpoints` accept `http://`; body unbounded — fixed: ycash-dd 6a7c4b628
- [x] **D-7** (Low, tooling) Plaintext `rpc_password` in TOML; no chmod guidance; Basic auth over http to any host — fixed: ycash-dd 6a7c4b628, 780deeeda, 46382da96
- [x] **D-8** (Low, attestor agent) iroh secret key file created with default umask then chmod — fixed: ycash-dd 6a7c4b628
- [x] **E-4** (Low, lightwalletd-dd) No context propagation or timeout on node calls; streams fully buffered — fixed: lightwalletd-dd e5b55a2
- [x] **E-5** (Low, lightwalletd-dd) `ListVaults.status` unvalidated; `count=0,skip>0` asks for 1000 rows — fixed: lightwalletd-dd 3945107
- [x] **E-6** (Low, lightwalletd-dd CI) Floating toolchains, unpinned action tags, unverified Go tarball — fixed: lightwalletd-dd f9218c1
- [x] **F-2** (Low, yecwallet-dd) Datadir upgrade marker written before the upgrade has happened — fixed: yecwallet-dd 04f4835
- [x] **F-3** (Low, yecwallet-dd) `parseDollars` turns a comma-decimal entry into a 100× amount — fixed: yecwallet-dd d8a07e4
- [x] **F-4** (Low, yecwallet-dd) Subscriber config with RPC password: permission window, no control-char escaping — fixed: yecwallet-dd 5750c4b
- [x] **F-5** (Low, yecwallet-dd) Production env var silently answers the one-way upgrade dialog — fixed: yecwallet-dd ce2fb3e
- [x] **F-6** (Low, yecwallet-dd CI) `nodedatacheck_test` never built or run by CI — fixed: yecwallet-dd eb5a4ff
- [x] **F-7** (Low, yecwallet-dd CI) Actions pinned by tag — fixed: yecwallet-dd eb5a4ff
- [x] **F-8** (Low, yecwallet-dd) Attestor registration dialog parses tier/bond loosely — fixed: yecwallet-dd 5750c4b
- [x] **G-5** (Low, yew) `consensusBranchId` accepted from the server with no per-network table — fixed: yew 42ee6e6, c050dc9
- [x] **G-6** (Low, yew) Unchecked multiplications on server-supplied counts in `tx.rs` — fixed: yew c050dc9
- [x] **G-7** (Low, yew) Server streams collected unbounded — fixed: yew c050dc9
- [x] **G-8** (Low, yew) Wrong-length txid zero-filled instead of erroring — fixed: yew c050dc9
- [x] **G-9** (Low, yew) Mint `cents` truncated `as u32` in the payload — fixed: yew 9de3e44
- [x] **G-10** (Low, yew) Keystore items not biometric-bound; iOS data not excluded from backup — fixed: yew f4ea42e (unverified on hardware)
- [x] **G-11** (Low, yew CI) Actions by tag; `cargo install` at build time; release APK signed with debug key — fixed: yew f4ea42e (Gradle not configuration-checked: no JDK here)
- [x] **H-4** (Low, yolo) Unauthenticated `mining.authorize` is an unmetered `validateaddress` amplifier — fixed: yolo 392e84d
- [x] **H-5** (Low, yolo) Stratum password compared non-constant-time — fixed: yolo 392e84d
- [x] **H-6** (Low, yolo) Hidden `--no-flags` ships in production and silently drops the pool's price vote — fixed: yolo 392e84d (refused unless built --features regtest)
- [x] **H-8** (Low, yolo) Miner-controlled strings logged unsanitised — fixed: yolo 392e84d
- [x] **H-9** (Low, yolo, chain-viz) RPC credentials on argv over cleartext HTTP; yolo connects to `rpcbind` host — fixed: yolo 70ced3e, 392e84d; chain-viz 48cb7e1
- [x] **H-12** (Low, chain-viz) Without `--public` no resource caps — fixed: chain-viz 48cb7e1
- [x] **H-13** (Low, chain-viz) No `Origin` check on `/ws` — fixed: chain-viz 48cb7e1
- [x] **H-14** (Low, chain-viz) Static export embeds JSON in `<script>` without `</script>` escaping — fixed: chain-viz 48cb7e1
- [x] **H-15** (Low, chain-viz CI) Actions by tag; release job `contents: write` — fixed: chain-viz cd04ee2
- [x] **I-2** (Low, both nodes CI) "Blocking" rule→test tag step is `continue-on-error` — fixed: ycash-dd e6af4111a; ycash6 d20ed19e5
- [x] **I-3** (Low, both nodes CI) Variant jobs run scripts that SKIP without sidecar binaries — fixed: ycash-dd e6af4111a
- [x] **I-5** (Low, both nodes CI) Node CI builds `chain-viz@main` unlocked — fixed: ycash-dd e6af4111a (CHAINVIZ_COMMIT dd87db83, --locked), bumped to chain-viz c388ed2 in ycash-dd a283878bc; ycash6 d20ed19e5
- [x] **I-4** (Low, both nodes CI) Third-party actions and bootstrap tooling pinned by mutable tag or fetched unverified — fixed: ycash-dd e6af4111a, a283878bc; ycash6 d20ed19e5
- [x] **I-6** (Low, both nodes CI) Nightly builds the attestor agent without `--locked` — fixed: ycash-dd e6af4111a
- [x] **I-7** (Low, agent, yolo, chain-viz) No advisory scan for the Rust components — fixed: ycash-dd e6af4111a (cargo audit) + attest deny.toml 410e0fe3d; yolo aba726b; chain-viz cd04ee2
- [x] **I-8** (Low, yolo, chain-viz) Floating `stable` toolchain — fixed: yolo 72a97d8; chain-viz 8773e31 (both 1.91.0)
- [x] **I-9** (Low, both nodes CI) No-ban gate greps `DoS(` but not `Misbehaving(` — fixed: ycash-dd e6af4111a
- [x] **V-5** (Medium, both nodes) `yed_listclaimable` under-states the attestor fee while the pool is stale — fixed: ycash-dd ba793f1c1, ycash6 9e529e378
- [x] **A-7** (Info, both nodes) `getblocktemplate` tag decoded from the served coinbase — fixed: ycash-dd 0b946b6e6 (merged as ff7f45947, re-tag decision), ycash6 0748c68a6
- [ ] **Info items** A-8, B-5, B-6, B-7, C-8, C-9, C-10, C-11, D-9, D-10, D-11, D-12, E-7, E-8, E-9, E-10, E-11, F-9, F-10, F-11, G-12, H-7, H-10, H-16, H-17, I-10, I-11, I-12, I-13, I-14 — open: not yet triaged one by one, and the per-component sections carry no resolved/accepted marks. Commits that name an Info item (addressed, not yet checked against the finding): A-8 ycash-dd f13eb370b, ycash6 14a1b3d23; B-5 ycash6 5be4e9613; B-6 ycash6 c29004d14; B-7 ycash6 ea93da770; C-8..C-11 ycash-dd ed8f32735, a54e53503, ycash6 ec193e559, b23d1a2ac; D-9 ycash-dd 46382da96; D-10 ycash-dd 06d87a79b; D-11 ycash-dd 6a7c4b628, 780deeeda, 46382da96, 0557f301d (ycash6 ports); D-12 ycash-dd 410e0fe3d, a283878bc, 46382da96, ycash6 2332f057a, d20ed19e5; E-8 lightwalletd-dd d31e1ba; E-10 lightwalletd-dd d31e1ba, ycash-dd 8c9be146d, ycash6 b19d38902; F-9 yecwallet-dd 5750c4b; F-10 yecwallet-dd ce2fb3e, cf5fd83; F-11 yecwallet-dd ce2fb3e; H-7, H-10 yolo bb038e7; H-16 yolo 72a97d8, chain-viz 8773e31; H-17 yolo 392e84d, c498027; I-11 ycash6 ea93da770, f6d536375; I-13 yolo aba726b, f01c2d1. No commit names E-7, E-9, E-11, G-12, I-10, I-12 or I-14

### Validation after remediation (2026-10-02)

Devnet run on the merged trees (ycash-dd `3129e06fa`+, lightwalletd-dd `77a9c0d`, yew `a90c2a1`, yolo `aba726b`, chain-viz `c388ed2`, yecwallet-dd `3df3d49`): default devnet + the three role presets, `yellowback_attest_agent.py`, lightwalletd's devnet suite 4/4 (after a pre-existing harness race in `lwd-rawmint` was fixed, ycash-dd `8c9be146d`; a manual probe confirmed the 1 MB garbage address is refused in milliseconds and a forged `x-real-ip` does not bypass the limiter), YEW's devnet suites w1/w2/w4 (no false positive from the new local checks; redeem preview/confirm and mint terms exercised), `yellowback_stratum.py` and `yellowback_chainviz.py` all passed. YecWallet's two attested devnet cases exposed the D-5 tip-lag regression above (fixed, ycash-dd `3afff8581`, ycash6 `567075a08`; re-run: zero dropped frames under burst mining) and then V-5 (fixed, ycash-dd `ba793f1c1`, ycash6 `9e529e378`). After both fixes YecWallet's three devnet cases pass in one run (5 passed, 0 failed) with zero dropped subscriber frames. The ycash6 line was ported in full afterwards (HEAD `0748c68a6`; 21 functional scripts green on 6.20.0, and stock parity run for the first time on that line against a local stock 6.20.0 build). Final ycash-dd HEAD `02aa77cb7`, tag `yellowback-v3-baseline` re-tagged at `ff7f45947` by owner decision.

### Pushed 2026-10-02 and owner actions

All eight repositories were pushed after the final local runs (ycash-dd `02aa77cb7` + tag `yellowback-v3-baseline` → `ff7f45947`, ycash6 `0748c68a6`, lightwalletd-dd `77a9c0d`, yecwallet-dd `414ac09`, yew `a90c2a1`, yolo `aba726b`, chain-viz `c388ed2`, workspace). Owner actions found while watching CI:

- **lightwalletd-dd CI had never run.** Every push since 2026-09-24 showed a failed run with zero jobs because `.github/workflows/yellowback-tests.yml` was invalid: the step name `Test (frontend: the Yellowback suite by name)` is an unquoted scalar with a colon-space, which GitHub's parser rejects at line 37 (the owner read the error off GitHub; a local PyYAML load had accepted it). Quoted in `455ab0c`; the workflow runs for the first time on that push. No other workflow in the eight repositories has the pattern. Still an owner choice: set that fork's default branch to `feature/yellowback-price-attest`.
- **cargo-deny 0.18.3 cannot parse the CVSS 4.0 advisories now in the RustSec database** (reproduced locally; first seen in chain-viz's audit job). Bumped to 0.20.2 in chain-viz `a8ae46c`, yolo `4617bed`, ycash-dd `6d7ee5217`, ycash6 `043a84fab`.
- **yolo's audit job used `rustsec/audit-check`, which posts a check run and needs `checks: write`** under the workflow's read-only token. Replaced by the token-free cargo-deny + cargo-audit steps chain-viz uses (yolo `f01c2d1`).
- **lightwalletd's generated-code gate compared comment lines.** protoc-gen-go formats doc comments with the go/format of the Go that compiled it; Go 1.24 on the runner reflows one indented comment in the baseline `compact_formats.pb.go` that Go 1.27 here does not. Reproduced in an Ubuntu 24.04 container; the mask now ignores comment-only and blank lines and a negative check confirms an API change still fails (`da3f73a`). The job is also split into named steps.

---

## 6. Per-component reports

Each section is the component reviewer's full report, including its "checked and found sound"
list, which is as much part of the record as the findings.


---

### Node overlay core (ycash-dd, consensus-adjacent soft-fork logic) — audit report

#### Summary

Read-only review of `ycash-dd/src/yellowback/{state,index,view,db,policy,payload,bundle,attest,tag,params,script,math.h,address}` and the four hook sites in `src/main.cpp`, `src/miner.cpp`, `src/rpc/mining.cpp` (delta vs `ycash-legacy`), against `doc/yellowback-spec.md` and the v3 plan §8.2. The core design holds up well: the state machine is total (no throw, no unchecked division, every product in `arith_uint256`), every write goes through one undo-recording `State` so apply/undo is byte-symmetric for all v2 and v3 tables, nothing in `state.cpp` reads the clock/wallet/config, map iteration is over ordered containers, and a block can only be rejected for a failing ACTIVE-vault spend after every stock consensus check has passed. The storage fail-open boundary (BLK-3) is implemented in the three ConnectBlock/DisconnectBlock hooks but not in the mempool/template/sweep paths. The most significant findings are a mempool-side CPU amplification (MP-1 runs a full `EvaluateBlock` including SNAP, before script verification, with DoS 0 — contradicting the spec's N6 claim) and a plausible cheap grief against PIN-2 that can pin the whole seated attestor set and halt minting for a pin window. No consensus-split, theft, or remote-crash path was found.

#### Findings

##### A-1 [Severity: Medium] MP-1 evaluates a full block (SNAP included) per vault-spend candidate, before script verification, with DoS 0
- Where: ycash-dd/src/main.cpp:1645-1646 (hook placement); ycash-dd/src/yellowback/index.cpp:690-730 (`MempoolCheckLocked`); ycash6 twin: ycash6/src/main.cpp:1891, ycash6/src/yellowback/index.cpp:759
- Status: CONFIRMED (traced; not benchmarked)
- Applies to: both
- What: `MempoolCheckLocked` builds a two-tx pseudo-block and calls `EvaluateBlock`, which runs `ComputeSnapshot` (REG-4 judge, `SignalCount` over 2,016 heights, PIN-1/2 over 288 BundleLog + 288 Tag rows, `Attestors()` full scan + per-record re-serialisation, `QuotePrices` over `pSlowWindow` = 2,016 heights, SIGMA samples, dormancy) in addition to RED-1..5 and up to `BUNDLE_MAX` ECDSA verifications. The spec (doc/yellowback-spec.md:598-600) states `MempoolCheck` "never computes a SNAP"; the code does for every tx whose input references an ACTIVE vault. The hook sits after `view.HaveInputs` but before `AreInputsStandard`/`CheckInputs`, so the spending script is never verified first, and the refusal is `DoS(0)`. Ycash's `recentRejects` only filters identical txids.
- Evidence:
  ```
  // main.cpp:1645
  view.SetBackend(dummy);
  if (yellowback::g_yellowback && !yellowback::g_yellowback->MempoolCheck(tx))
      return state.DoS(0, false, REJECT_NONSTANDARD, "yellowback-vault-spend");
  // index.cpp:715-716
  OverlayStateView overlay(*db);
  BlockEvaluation ev = EvaluateBlock(overlay, p, pseudo, next, uint256(), 0, &sigCache);
  ```
- Scenario: any peer streams distinct transactions whose `vin[0].prevout` is a public ACTIVE vault outpoint and whose scriptSig is garbage (or a `OP_0 <script>` claim-path shape with a REDEEM payload and a carrier input holding 6 random 64-byte signatures). Each costs the enforcing node several thousand LevelDB reads plus up to 6 failing secp256k1 verifications under `cs_main`, then is dropped with no misbehaviour score. A stock node spends one script check and bans at DoS 100. Enforcing nodes (the miners) can be held under `cs_main` by one unbanned peer; block validation and template building stall. Pre-fix cost is roughly 100x a stock node's per-bad-tx cost; the attacker's cost is bandwidth.
- Recommendation: (1) replace `EvaluateBlock` in `MempoolCheckLocked` with `ProcessTx` on an overlay (as `FilterTemplate` already does, policy.cpp:92-94) — RED-1..5 read only `Snapshots[ref ≤ H-1]`, so SNAP is unnecessary and the spec already promises its absence; (2) move the hook after `CheckInputs` so only script-valid spends are evaluated (after `claimHeight` the claim branch is anyone-can-spend, so (1) is still needed); (3) consider a per-peer counter/`Misbehaving(…, small)` for repeated `yellowback-vault-spend` refusals. Update spec N6 text if (1) is not done.

##### A-2 [Severity: Medium] PIN-2 can be triggered by an attacker to pin every seated attestor and halt ARMED minting for up to PIN_WINDOW
- Where: ycash-dd/src/yellowback/state.cpp:1145-1166 (PIN-2), :121-181 (`EvalContext::Bundle` records every *verified* bundle regardless of the final verdict), :329-365 (MINT-5 evaluated after MINT-9 when ARMED); ycash6 twin: ycash6/src/yellowback/state.cpp (same functions)
- Status: PLAUSIBLE (logic traced; not executed on regtest)
- Applies to: both
- What: BundleLog rows carry the (seq, price) pairs of every bundle for which BUNDLE-1 held "whatever the transaction's final verdict" (view.h:514-519). When ARMED, a MINT reaches MINT-9 (bundle verification) before MINT-5 (collateral), so a mint with 2 YEC collateral (`4 * feeMin`), a 0.5 YEC pool fee and the attestor fee writes a BundleLog row and then VOIDs; the attacker keeps the 2 YEC (a VOID vault is an ordinary spend). PIN-2 pins any seq that appears in ≥ `PIN_MIN_TAGS` (3) rows of the last 288 blocks with exactly one price, whenever `xMint` moved > 5 % over 288 blocks. Attestations are valid for 20 blocks, so the same attestation of each selected attestor can be reused in three rows. `Selected()` removes pinned seqs from the pool; when all `N_SLOTS` seated seqs are pinned the pool is empty, BUNDLE-1 fails "member" for every bundle, MINT-9 VOIDs every mint and NOT-1 cannot register notices.
- Evidence:
  ```
  // state.cpp:1161-1162
  if (kv.second.first >= std::max(1, P.pinMinTags) && kv.second.second.size() == 1) s.pinnedSeqs.push_back(kv.first);
  // state.cpp:1444-1445
  for (uint16_t seq : s->seated) {
      if (std::find(s->pinnedSeqs.begin(), s->pinnedSeqs.end(), seq) != s->pinnedSeqs.end()) continue;
  ```
- Scenario: during a > 5 % / 6 h price move (common), an attacker submits ~9–12 cheap VOID mints over ~20 blocks choosing refHeights (40 candidates) whose `selected(R, "")` draws cover all nine seated attestors, reusing one attestation per attestor each time. Cost ≈ 0.6 YEC per row (fees) with collateral returned. Honest mints in the same window that carry a *different* attestation of the same attestor break the pin, so the grief works best in low-activity periods and lasts until the window rolls (≤ 288 blocks). Mint halt and emergency-claim halt; no theft. §8.2 lists "Pinned attestors" only as an honest-failure case.
- Recommendation: build PIN-2's per-seq price set from the attestations' `citedHeight` distinctness as well as price (an attestor that signed only one cited height in the window has not "frozen"), or count rows only from transactions whose final verdict is OK/a registered notice, or require `PIN_MIN_TAGS` rows with *distinct* citedHeights. Add a regtest case to `yellowback_attest_*` that reuses one attestation across three VOID mints and asserts `pinnedSeqs` stays empty.

##### A-3 [Severity: Low] BLK-3 exception boundary is missing on the mempool, template, sweep and RPC paths
- Where: ycash-dd/src/yellowback/index.cpp:690-763 (`MempoolCheckLocked`, `RemoveInvalidVaultSpends`), ycash-dd/src/yellowback/policy.cpp:66-127 (`FilterTemplate`), index.cpp:1016-1051 (`AddAttestation`), :1071-1111 (`BuildBundleInfo`); ycash6 twins same files
- Status: CONFIRMED
- Applies to: both
- What: `CheckConnect`/`CommitConnect`/`UndoDisconnect` wrap storage in try/catch and call `SetUnhealthy` (BLK-3). The other readers of `YellowbackDB` do not; `CDBWrapper::Read` throws `dbwrapper_error` on an I/O error (not on NotFound). From `AcceptToMemoryPool` the exception escapes to `ProcessMessages`' catch (a logged error, tx dropped) or to the RPC; from `CreateNewBlock` to `getblocktemplate`/the internal miner; from `ConnectTip` (the sweep runs after `CommitConnect`) out of `ActivateBestChain`.
- Evidence:
  ```
  // index.cpp:744-749 — no try/catch
  void YellowbackIndex::RemoveInvalidVaultSpends(CTxMemPool& pool) {
      AssertLockHeld(cs_main); LOCK(pool.cs); LOCK(cs_yellowback);
      if (stopped || !healthy) return;
      ... MempoolCheckLocked(tx) ...
  ```
- Scenario: a disk fault during the ConnectTip sweep unwinds `ActivateBestChain` after the block's chainstate and the index were both committed; the node is left with the block connected but `UpdateTip` not run, and the index is not marked unhealthy, so the next hook sees a tip mismatch and *then* goes unhealthy — recoverable, but the failure is reported one block late and in a different place than BLK-3 promises.
- Recommendation: wrap `MempoolCheckLocked`'s evaluation, `FilterTemplate`'s dry run and the sweep in the same try/catch → `SetUnhealthy` pattern (returning "admit"/"keep" on failure, consistent with fail-open).

##### A-4 [Severity: Low] PIN-1 treats an undefined (`aMint == 0`) BundleLog row as the window minimum
- Where: ycash-dd/src/yellowback/state.cpp:1126-1131; ycash6 twin ycash6/src/yellowback/state.cpp:1128
- Status: CONFIRMED (latent; unreachable with shipped params)
- Applies to: both
- What: `BundleLogRecord.aMint` is stored as 0 when every bundle in the block had an undefined statistic (`LowerMedian(aMints).value_or(0)`, state.cpp:188). PIN-1 initialises `aLo = -1` and takes `row.aMint < aLo` without excluding 0, so a 0 row makes `aLo = 0` and `(aHi - 0) * BPS > delta * 0` is true for any positive `aHi`, pinning every key with a frozen quote.
- Evidence:
  ```
  if (aLo < 0 || row.aMint < aLo) aLo = row.aMint;
  ...
  if (aLo >= 0 && (aHi - aLo) * BPS > (int64_t)std::max(0, P.pinDeltaBps) * aLo) {
  ```
- Scenario: `WeightedQuantile` returns nullopt only for `qBps > 10000` or an empty C; BUNDLE-1 guarantees |C| ≥ M_SELECT and params fix Q at 3,333/6,667, so no shipped parameter set reaches it. A future parameter set or a regtest override with `qLowBps > 10000` would silently pin every miner.
- Recommendation: skip rows with `aMint <= 0` in the PIN-1 scan (mirror `Snapshot::Price`'s "0 is never a value" rule), and add the same guard to the Python model.

##### A-5 [Severity: Low] Every enforcement gap converts vaults past `claimHeight` into anyone-can-spend without burn; the sunset gap is ~5 days
- Where: ycash-dd/src/yellowback/script.cpp:86-92 (claim branch is `<claimHeight> CLTV DROP OP_TRUE`), index.cpp:364-385 (BLK-2 clauses: ACT-5 off, kill switch, valve, IBD/reindex/import, catch-up suppression), state.cpp:945-952 (sunset in `EnforcementOn`)
- Status: CONFIRMED (behaviour as designed; flagged for the threat-model text)
- Applies to: both
- What: the only guard on the claim branch is RED-2/RED-4 enforced by miners. Whenever BLK-2 does not act — IBD (`nMaxTipAge` 24 h behind), `-reindex`/`-loadblock`, the valve tripped, catch-up suppression (6 blocks of work ahead), `ENFORCEMENT` halt, the sunset — a stock-mined claim-path spend with no burn takes the collateral and the vault closes `unbacked`. At the sunset (L8) the plan expects a successor set; without one, abandonment (`yed_sweep`) only becomes true ~2,016 + 4,032 blocks later (signal bits decay below the floor, then `ABANDON_BLOCKS`), so vaults past `claimHeight` are exposed for roughly five days before owners' sweeps are even admitted by MP-1/TPL-1 on their own nodes (MP-1 still refuses the non-burning sweep until `IsAbandoned()`).
- Evidence:
  ```
  // script.cpp:90
  script << (int64_t)claimHeight << OP_CHECKLOCKTIMEVERIFY << OP_DROP << OP_TRUE;
  // state.cpp:950
  if (P.enforceUntilHeight > 0 && height > P.enforceUntilHeight) return false;
  ```
- Scenario: a release with no successor reaches `ENFORCE_UNTIL_HEIGHT`; any stock miner (or anyone who can get a tx to one) claims every ACTIVE vault past `claimHeight` without burning YED; the YED stays in circulation unbacked.
- Recommendation: document in §8.2 and in the wallet (owner-facing "redeem before sunset" warning at `ENFORCE_UNTIL_HEIGHT - grace`); consider letting MP-1/TPL-1 stand down on the sunset itself (not only on abandonment) so owner sweeps are admitted immediately.

##### A-6 [Severity: Low] Valve odometer and catch-up suppression trust header work that is never contextually validated
- Where: ycash-dd/src/yellowback/index.cpp:526-582 (`NoteHeaderOnRejectedChain`), :517-524 (`NetworkAlreadyBuiltOn`), main.cpp:4562-4563 (hook runs before `ContextualCheckBlockHeader`)
- Status: CONFIRMED
- Applies to: both
- What: a noted header passed `CheckBlockHeader` (PoW against its *own* `nBits`) but not `ContextualCheckBlockHeader` (nBits vs. consensus difficulty, timestamps). P2 bounds the loosening to 132 % of the *parent note's* `nBits`, compounding per note (64 notes ⇒ up to 1.32^64 easier), but work is summed from each header's own `nBits`, so the geometric sum caps the discount at ≈ 3.1 blocks of tip work; an attacker still needs ≈ `VALVE_BLOCKS - 3` ≈ 3 real blocks of PoW to trip the valve of every enforcing node. The suppression clause uses `pindexBestHeader`, which does go through `ContextualCheckBlockHeader`, so it is sound.
- Evidence:
  ```
  if (target > parentTarget / 100 * 132) { ... return true; }   // parentTarget is the previous *note*, not consensus
  n.work = parentWork + GetBlockProof(tmp);
  ```
- Scenario: a griefer with ~3 blocks of hashpower-time per rejected root can switch enforcement off (until restart, with an alert) on all enforcing nodes without producing a single valid block. Honest stock miners reaching 6 blocks trip it anyway, so this halves the honest cost rather than creating a new class of attack.
- Recommendation: bound the noted target against the consensus `GetNextWorkRequired` of the parent note's position (or simply against the rejected root's `nBits`, not the previous note's), and/or require a notes-only trip to reach `VALVE_BLOCKS` headers *and* work.

##### A-7 [Severity: Info] `getblocktemplate.yellowback.tag` / `coinbaseaux.flags` reflect the current `COINBASE_FLAGS`, not the cached template's coinbase
- Where: ycash-dd/src/rpc/mining.cpp:770, :785; ycash-dd/src/yellowback/index.cpp:815-848 (`TemplateInfo` decodes `COINBASE_FLAGS`)
- Status: CONFIRMED
- Applies to: ycash-dd (ycash6 if the same hook is ported)
- What: `getblocktemplate` reuses `pblocktemplate` for up to 5 s / until the tip or mempool changes; `yed_setquote` between two calls changes `COINBASE_FLAGS` only on the next `CreateNewBlock`. A pool reading `coinbasetxn` sees the old tag while `yellowback.tag` shows the new one.
- Recommendation: decode the tag from `pblocktemplate->block.vtx[0].vin[0].scriptSig` instead of the global.

##### A-8 [Severity: Info] Attestor seq space is a non-reusable u16 and REG-A1 scans every attestor record linearly
- Where: ycash-dd/src/yellowback/state.cpp:672-676, :1095-1097 (`ComputeSnapshot` deserialises and re-serialises every attestor each block)
- Status: CONFIRMED
- Applies to: both
- What: 65,536 registrations exhaust the layer permanently ("the u16 counter wrapped (totality)"); `BOND_MIN` = 20,000 YEC and a one-year lock bound concurrent attestors to ≈ supply/20,000 ≈ 1,000, so exhaustion takes decades and the per-block scan stays small. Noted for completeness; no action needed unless `BOND_MIN` drops.

#### Checked and found sound

- Apply/undo symmetry: every write in `EvaluateBlock`/`ComputeSnapshot`/`ProcessTxImpl` goes through `State::Put/EraseKey` with the undo pointer (view.cpp:287-309); v3 tables A/B/N/M/W/E included; `CommitConnect` applies `overlay.Pending()` and writes the same `ev.undo` `ApplyOne` would (index.cpp:424-429); `UndoBlock` restores byte-identical pre-images; undo pruning at `UNDO_KEEP` only erases U keys (index.cpp:430-434).
- Reorg handling: `DisconnectBlock` hook guarded by `updateIndices` (VerifyDB passes `false`, main.cpp:5144); `UndoDisconnect` checks `tip == pindex`; `TipMatches` keys on `pprev` hash (K5); K6 skips re-verification; `SyncToChain` undo-walks an index ahead of an unflushed chainstate and wipes on a missing undo record (index.cpp:273-284).
- Determinism: no `GetTime`/wallet/`GetArg` in state.cpp, math.h, bundle.cpp, attest.cpp (`policy::TagScript` and the RPC are the only clock readers); all containers iterated are `std::map`/`std::set` or explicitly sorted with total-order comparators (state.cpp:1096, 1173, 1392, 1406); no floating point; `BundleStat` sorts by (price, seq).
- Integer math: every product in `arith_uint256` with `FitsInt64`/`MoneyRange` checks (math.h); divisors checked non-zero before every `/` (`SelectAttestors` total≠0, `DefaultAttestPayee` n≥1, `Judge` med>0, `AccuracyBps` quoted>0, `SigmaMultBps` b>0); HALT-3 and PIN products bounded by `PRICE_MAX`=1e8 × 1e4; `issuedZat` deliberately wraps; uint32 payload fields widened to int64 before comparison.
- Fail-open: `CheckConnect` is placed after `control.Wait()` and the coinbase-amount check (main.cpp:3193-3200) so no non-Yellowback reason is ever added; only `redFailed` sets `blockInvalid`; malformed payloads/bundles/tags are "non-Yellowback" or VOID, never invalid; DoS(0) on every refusal; `NoteHeaderOnRejectedChain` pre-empts the stock DoS(100) `bad-prevblk` for rejected roots only.
- Parsers: `payload.cpp` Reader is bounds-checked with exact-size checks per type; `DecodeBundle` exact length and `maxCount`; `FindTag` index arithmetic bounded; `ReadHeightPush` catches `scriptnum_error`; `ParseVaultSpendPath`/`ParseCarrierScriptSig` use `GetOp`. Fuzz targets exist for payload, bundle (incl. carrier shapes and the signature step), tag, script parsers, full `EvaluateBlock` (apply/undo identity, overlay equivalence) and `DefaultPayee` (src/fuzzing/Yellowback*). Not fuzzed: `ParseBondScript`, `IsCarrierScript` alone, `DeserializeRecord` over corrupt DB bytes (only the catch-all try/catch protects it).
- Signature cache: key = SHA256(att74 ‖ blockHash) covers every verification input (seq→pubkey is immutable); LRU bounded 16,384; false results cached too (only a perf concern).
- MP-1 / TPL-1 / BLK-1 / BLK-2 agreement: all three use `ProcessTxImpl`'s `redFailed`; MP-1 and TPL-1 evaluate at index tip + 1 which equals chain tip + 1 whenever healthy; both stand down under `IsAbandoned()`; TPL strict adds expiry + shape only; ConnectTip sweep runs after `CommitConnect` so it sees the new tip.
- Lock order: every hook asserts `cs_main` and takes `cs_yellowback` inside; `RemoveInvalidVaultSpends` takes `mempool.cs` then `cs_yellowback`; `TemplateView` holds `cs_yellowback` inside `LOCK2(cs_main, mempool.cs)`; `TemplateInfo` drops `cs_yellowback` between `GetMinerStatus` and its own lock; `IncrementExtraNonce` now under `cs_main` (miner.cpp:837-840).
- Economic rules: RED-5 residual uses the higher `pClaim` and 100 % margin under (b) (R1); NOT-1 reset-attack guard; EQV-1 cross-reorg safe (both sigs verified under the current hash at `citedHeight`); REV-1 needs a fresh signature under the chain's hash; bond spend before locktime impossible (CLTV); MINT fee/attest fee vouts excluded from assignments; token/vault outputs keyed by (txid, vout) so cross-tx collisions are impossible.
- Memory/disk growth: `notes` ≤ 64 per rejected root, `pool` ≤ 3 per seq, one `Evaluation` cache, Undo pruned at 4,096; TxLog/VOID vault/Snapshot growth is linear in chain activity.

#### Not covered / needs a different auditor

- `src/yellowback/{txbuilder,wallet,coinselect}.cpp` and `src/rpc/yellowback.cpp` (wallet/RPC surface; `AddAttestation` and `BuildBundle` reviewed only as called from them).
- `src/init.cpp` flag parsing (191-line delta) and `-yellowbacktestfault` reachability on non-regtest.
- The Python model (`qa/rpc-tests/test_framework/yellowback_model.py`) agreement with A-4's edge case and A-2's scenario (needs a regtest run; "do not build" applied).
- Attestor agent / lightwalletd / pool behaviour around re-signing the same `citedHeight` (which EQV-1 treats as equivocation).
- ycash6 twin lines were spot-checked by grep (MP-1 hook and the PIN-1/PIN-2 code are identical) but not read in full.

---

### ycash6 port (ycashd 6.20.0 line) vs ycash-dd — audit report

#### Summary
I diffed every overlay file (`src/yellowback/*`, `src/rpc/yellowback*`, `src/test/yellowback_*`, the six `src/fuzzing/Yellowback*/fuzz.cpp`) between `ycash-dd` (`feature/yellowback-price-attest` @ a5edaa497) and `ycash6` (`feature/yellowback` @ 3b0dfb6e3), read every pre-existing-file hunk on `ycash6` against the tag `ycash6-baseline`, ran the read-only audit gate (`qa/yellowback-audit.sh`: frozen set zero, every budget within limit, 48 `yed_*` arity rows current), and confirmed `librustzcash6` `feature/yellowback` is zero-delta against `librustzcash6-legacy`. Of the 20 divergent files, every divergence is an include rename, a listed 6.20.0 API adaptation (ZIP-244 `PrecomputedTransactionData`, move-only builder, `asOfHeight` positionals, `DecodeHexTx` throwing, `TestOnlyRandomKey`), the P-2 fee rule, or a 6.20.0-only fix (F-27, F-31, F-37, F-38) — except one RPC fix (poolFresh / claimable) that is on `ycash6` but only on an unmerged `ycash-dd` branch, and the `importwallet` H8 guard, which exists on `ycash6` only. The 6.20.0-specific adaptations are sound: sighashes are v4-only and fail closed for anything else; the builder is constructed in place; `CheckConnect` is side-effect-free under `fJustCheck`; the baseline fixes are regtest-only or byte-neutral on mainnet. One behavioural consequence of the headers-loop skip (V7) deserves a decision: on 6.20.0 a stock peer on a persistent minority fork longer than `VALVE_NOTE_CAP` (64) blocks is banned by enforcing nodes. Overall verdict: the port is complete and no Critical/High issue was found; two Low/Medium items and several Info items follow.

#### Findings

##### B-1 [Severity: Medium] Stock peers on a long minority fork are banned by enforcing 6.20.0 nodes (headers-loop skip × `VALVE_NOTE_CAP`)
- Where: `ycash6/src/main.cpp:8621-8631` (the V7 skip), `ycash6/src/main.cpp:5976-5982` (hook + stock `bad-prevblk` DoS 10), `ycash6/src/yellowback/index.cpp:563-619` (`NoteHeaderOnRejectedChain`), `ycash6/src/yellowback/index.h:65` (`VALVE_NOTE_CAP = 64`), `ycash6/src/yellowback/params.cpp:33` (`valveBlocks = 6`)
- Status: CONFIRMED (by trace; not run)
- Applies to: ycash6 (reachable in one message there; on ycash-dd the loop aborts at the first refused header, `ycash-dd/src/main.cpp:4562`, so the 66th header is never reached on that path)
- What: Once a root is rejected, each descendant header is noted (DoS 0) up to 64 notes per root; the 65th is refused but *not* noted (`index.cpp:600-602`, still `return true`); the 66th has a prev that is in neither `notes` nor `mapBlockIndex`, so `NoteHeaderOnRejectedChain` returns false and the stock path answers `prev block not found` **DoS 10**. The V7 skip keeps the loop running past the first 65 refusals, so a single `headers` message reaches the 66th. The valve trips only when the rejected chain's work reaches `tip.work + 6 × proof(tip)` (`index.cpp:612-614`), i.e. when it is *ahead* of our chain; a stock minority chain that stays behind never trips it but keeps growing past 64 blocks. Each new block the stock peer announces triggers `getheaders` (its hash is never in `mapBlockIndex`), and its reply replays the whole rejected chain from the fork point, so the peer earns 10 ban-score per announcement and is banned after ~10 blocks.
- Evidence:
```
    if (notesPerRoot[root] >= VALVE_NOTE_CAP) {
        LogPrint("yellowback", "valve: header %s not noted (root %s holds %d notes)\n", ...);
        return true;                                   // refused, but its child will not be found
    }
...
        BlockMap::iterator mi = mapBlockIndex.find(block.hashPrevBlock);
        if (mi == mapBlockIndex.end())
            return state.DoS(10, error("%s: prev block not found", __func__), 0, "bad-prevblk", BodyCorruption::HeaderOnly);
```
- Scenario: a minority of hash power stays on stock 6.20.0 and mines a rule-breaking block; the enforcing majority rejects it and continues. After the stock branch is 65 blocks long, every enforcing node assigns the stock peers DoS 10 per announcement and bans them within ~10 blocks; the plan's §4 ("no peer banned") no longer holds for this case, stock miners lose their enforcing peers (and vice versa), and a partition forms. No funds are at risk; the chain selection is unaffected (the branch is already refused). Plan F-25 records this as **open** ("as on v4.5.0"), but on 6.20.0 it is reachable within one message rather than only through the old direct-fetch path.
- Recommendation: make the post-cap refusal terminal at DoS 0 — e.g. when the cap is hit, `break` out of the headers loop instead of `continue` (the odometer cannot learn more from that root anyway), or have `NoteHeaderOnRejectedChain` remember refused-but-unnoted hashes in a bounded set so their children also answer `bad-prevblk-yellowback`. Either is a 2–3 line change inside the existing guarded hook, within the `main.cpp` budget. Record the decision against F-25.

##### B-2 [Severity: Low] RPC fix (poolFresh / claimable) landed on ycash6 but not on ycash-dd — the two lines answer differently today
- Where: `ycash6/src/yellowback/index.cpp:1098-1103` (`PoolFreshAt`), `ycash6/src/rpc/yellowback.cpp:252-255,637,1706` vs `ycash-dd/src/yellowback/index.cpp` (`PoolHasNewerThan`), `ycash-dd/src/rpc/yellowback.cpp:252-256` (`claimable` by clause (a) only); backport on `ycash-dd` branch `rpcfix` (c23f937dd, 379f9d30b), unmerged (`git -C ycash-dd log feature/yellowback-price-attest..rpcfix`)
- Status: CONFIRMED
- Applies to: both (owner rule "fix both node lines")
- What: On ycash6 `yed_getvault.claimable` / `yed_listvaults` / `yed_listpositions` use `EstimateClaim` (RED-4 by either clause) and `poolFresh` counts only citations in `(R − ATTEST_MAX_AGE, R]`; on ycash-dd `claimable` tests only the tip-snapshot clause and `poolFresh` has no upper bound (a citation above R counts as fresh). The plan checkpoint says the backport "builds and its unit tests pass; functional tests are running", but it is not on the branch of record.
- Evidence (ycash-dd, still the old predicate):
```
    bool claimable = false;
    if (v.Status() == VaultStatus::ACTIVE && tip >= v.claimHeight && tipSnap.has_value()) {
        claimable = IsUnderwater(v.collateralZat, tipSnap->PClaim(), v.mintedCents, p.claimThresholdBps);
    }
```
- Scenario: YEW / yecwallet-dd / chain-viz drive both lines through the same `yed_*` contract; a wallet on a v4.5.0 node reports a vault not claimable (or an attestor seat "fresh") where a 6.20.0 node says the opposite; a user acting on the v4.5.0 answer misses a claim window or builds a mint whose bundle has nothing to cite. Wallet-tier only; no consensus effect.
- Recommendation: merge `rpcfix` into `feature/yellowback-price-attest` once its functional run is green; after that the overlay delta between the lines should be include renames + listed adaptations only (I measured 67/13/18/20/80 differing lines remaining in the five files after the backport, all of the documented kinds).

##### B-3 [Severity: Low] `importwallet` / `z_importwallet` lack the H8 reconcile on ycash-dd
- Where: `ycash6/src/wallet/rpcdump.cpp:397` (guarded) vs `ycash-dd/src/wallet/rpcdump.cpp:409-429` (`importwallet` → `importwallet_impl`, no `YellowbackReconcileOnExit`; the four guards on ycash-dd are at `:117,169,303,945`)
- Status: CONFIRMED
- Applies to: ycash-dd (ycash6 fixed; plan F-7 calls it "a v4.5.0 gap", never backported)
- What: `importwallet` imports spending keys and rescans; YED token outputs that become mine are not re-locked until the next `ChainTip` stage (iii) or a manual `yed_lockcoins`.
- Evidence (ycash6 has it, ycash-dd does not):
```
    YellowbackReconcileOnExit yellowbackReconcile;   // H8 (6.20.0 port: importwallet imports spending keys and rescans, as importprivkey does)
    LOCK2(cs_main, pwalletMain->cs_wallet);
```
- Scenario: a user restores a wallet dump holding YED on a v4.5.0 node and immediately runs `sendtoaddress` / `z_sendmany`; automatic coin selection may spend a 10,000-zat token output as plain YEC and burn the YED (the H7 raw-tx guard does not cover wallet-built sends). Window: until the next block.
- Recommendation: backport the one-line guard to `importwallet_impl` on ycash-dd.

##### B-4 [Severity: Low] V7 drops the continuity check after a skipped header (recorded as review V-7)
- Where: `ycash6/src/main.cpp:8613-8616` (continuity check keyed on `pindexLast`), `:8628-8629` (`pindexLast = NULL; continue;`)
- Status: CONFIRMED
- Applies to: ycash6
- What: After a skipped header the stock `non-continuous headers sequence` (DoS 20) check is disabled for the next header, so a peer can replay a known Yellowback-rejected block (a cheap `duplicate`) and follow it with unrelated headers in one message. Each is still fully validated by `AcceptBlockHeader` (PoW before the hook, `main.cpp:5968-5976`), so only the ban-score signal is lost, and only while a rejection is live and the valve is untripped.
- Evidence: see `:8613` `if (pindexLast != NULL && header.hashPrevBlock != pindexLast->GetBlockHash())`.
- Scenario: a peer batches up to 2000 unconnected but valid-PoW headers per message instead of one per message; bounded CPU, no state corruption. The review's suggested disposition (record and accept) is reasonable.
- Recommendation: accept, or track the refused run's last hash (`uint256 hashSkipped`) and keep the DoS 20 for a header whose prev is neither `pindexLast` nor `hashSkipped`.

##### B-5 [Severity: Info] F-2 mitigation relies on named-return-value elision, not on the language
- Where: `ycash6/src/yellowback/txbuilder.h` (`BuiltTx::builder` is `std::optional<TransactionBuilder>`), `ycash6/src/yellowback/txbuilder.cpp:761,1162,1271,1594` (`slot.emplace`), every `return out;` of a `BuiltTx` local; `ycash6/src/transaction_builder.h:296-298` (the upstream move ctor moving `firstSaplingSpendAddr` from `*this`)
- Status: CONFIRMED (no move expression exists; `grep std::move` finds none in the overlay), impact nil
- Applies to: ycash6
- What: C++17 guarantees elision only for prvalues; `return out;` of a named local is NRVO, which every shipping compiler performs here but the standard does not require. If a builder were ever moved after `AddSaplingSpend`, `firstSaplingSpendAddr` would be lost — harmless today because both spend shapes call `SendChangeTo(source.sapling, ovk)` explicitly (`txbuilder.cpp:1164,1274`) and the output-only shapes have no spends.
- Recommendation: either hold the builder through `std::unique_ptr<TransactionBuilder>` in `BuiltTx`, or add a comment at `BuiltTx` that an explicit `SendChangeTo` is what makes the F-2 defect unreachable. Report F-2 upstream as planned.

##### B-6 [Severity: Info] `yed_getnewaddress` / `FreshKey` now require an unlocked wallet; `keypool-empty` can no longer occur (F-5)
- Where: `ycash6/src/rpc/yellowbackwallet.cpp:594-596`, `ycash6/src/yellowback/txbuilder.cpp:449-453`
- Status: CONFIRMED
- Applies to: ycash6
- What: 6.20.0 has no keypool draw; the overlay calls `GenerateNewKey(true)` after an `IsLocked()` check. The RPC contract still lists `keypool-empty` (reservekey paths still raise it, `txbuilder.cpp` change outputs). Wallet-tier behaviour change the clients should know about (a locked wallet now fails `yed_mint` etc. with `wallet-locked`).
- Recommendation: document in `doc/yellowback-rpc.md` (contract JSON unchanged by owner rule).

##### B-7 [Severity: Info] Documentation gaps found while cross-checking the review package
- Where: `ycash6/doc/yellowback-review.md` §1.2 omits `src/util/system.cpp` (+7/−? , `PrivacyInfo()` branding, commit 67068368d); `-yellowbacktestfault=crash:<height>` (`index.cpp:175-178, 385-391`, regtest-only, SIGKILLs the node) exists on ycash6 only and is not in `docs/mapping.md` §19; plan §4 item 5/6 "no peer banned" is contradicted by B-1 beyond the note cap; review §7 still says the §4 demonstration and the extra CI jobs are unrun while the plan says they passed (the plan is newer).
- Status: CONFIRMED
- Applies to: ycash6
- Recommendation: refresh §1.2 and §7 of the review when §4.10 is ticked; add the `crash:` fault to mapping §19 (it is a test hook, guarded by the regtest-only `-yellowbacktestfault` check at `init.cpp:1296`).

#### Checked and found sound
- **Overlay parity (file by file).** 20 of 55 overlay files differ; all differences are include renames (`util.h` → `util/system.h`, `util/strencodings.h`, `util/time.h`, `util/moneystr.h`, `util/test.h`), `CKey::TestOnlyRandomKey`, `DecodeHexTx` throwing (`rpc/yellowback.cpp:1362-1364,1408-1412`, `yellowback_state_tests.cpp:534`), `GetBlockSubsidy` as a method (F-3), `CCriticalBlock` → `UniqueLock`, `CAlert::Notify` → `AlertNotify`, `ChainTip(…, MerkleFrontiers)`, the P-2 fee loops, F-27/F-31/F-37/F-38 and the two RPC fixes (B-2). `SchedulePending`'s `[=, &yw]` → `[=]` drops an unused capture only (bodies identical, `yellowbackwallet.cpp:563-586` both lines). `librustzcash6`: zero delta (`git diff librustzcash6-legacy...HEAD --stat` empty).
- **(1) ZIP-244 sighash usage.** `V4TxData` (`ycash6/src/yellowback/txbuilder.cpp:144-151`) throws unless `fOverwintered && nVersionGroupId == SAPLING_VERSION_GROUP_ID && nVersion == SAPLING_TX_VERSION`; for that shape `SetPrecomputed` never reads `allPrevOutputs` (`ycash6/src/script/interpreter.cpp:1161-1176`) and `SignatureHash` takes `amount` and `consensusBranchId` from its arguments (ZIP-243 path, `:1219` onward), so every signature is bound to the explicit vault/carrier/bond amount and the caller's branch id, exactly as v4.5.0. `NewTx` passes `requireV4 = true` (`:398`); the builder is given no Orchard anchor; if a v5 transaction ever appeared, signing fails closed. `policy.cpp:153-172` gathers all prevouts from the view before constructing `PrecomputedTransactionData` and verifies each input with the matching `prev.nValue`.
- **(2) Move-only builder (F-2).** Constructed in place via `slot.emplace(::Params(), chainHeight + 1, std::nullopt, anchor)` (`txbuilder.cpp:410-417`); the Sapling anchor is the witnesses' anchor for spend shapes and `pcoinsTip->GetBestAnchor(SAPLING)` for output-only shapes; `GetSaplingNoteWitnesses(ops, 1, …)` returns the newest witness (`wallet.cpp:4623-4650`), matching v4.5.0. `AddTransparentInputUnsigned` carries the real `scriptPubKey` (looked up from `pcoinsTip`, `SpentScript`, `:461-465`) and `Build()` skips those inputs (`transaction_builder.cpp:638`). No `std::move` of a builder anywhere (B-5 is the only caveat).
- **(3) `BlockAssembler` / `TestForBlock` / `CheckAs::BlockTemplate`.** `ybviewHolder` is declared after `LOCK2(cs_main, mempool.cs)` so `cs_yellowback` is released before them (`miner.cpp:353-355`); the filter is the last refusal before `AddToBlock` (`:546-547`); `CheckConnect(fJustCheck)` writes nothing (`Rejected` is recorded only under `!fJustCheck`, `index.cpp:421-431`; `suppressedBlocks++` is unreachable for the dummy template index since `NetworkAlreadyBuiltOn` needs `pindexBestHeader->GetAncestor(h) == pindex`); the `Evaluate` memo is keyed by block hash. V-1 (dry-run committed before the turnstile check) is fail-safe as recorded. `COINBASE_FLAGS` is assigned and read under `cs_main` (K17 lock added at `:917-920`).
- **(4) Headers-loop skip (V7).** Hook sits after `CheckBlockHeader` (PoW) in `AcceptBlockHeader` (`main.cpp:5968-5977`), so a refused header costs real PoW; `duplicate` sets `*ppindex` before returning (`:5958-5963`) so `IsRejectedAncestor(pindexLast)` sees the right entry; `ValveTripped()` is read under `cs_main`, written under `cs_main`+`cs_yellowback`; `UpdateBlockAvailability`/`getheaders` are guarded on `pindexLast`. Residual issues are B-1 and B-4.
- **(5) ZIP-317 / ZIP-401.** P-2 prices every builder at `max(-yellowbackfee, conventional fee)` with stand-in signatures that never undercount (`NetworkFee`, `PendingP2PKHSig`, `PendingCarrierSig`, `txbuilder.cpp:186-230`; unit tests `p2_mint_fee_is_the_conventional_fee`, `p2_redeem_fee_is_the_conventional_fee`). The reprice loops only raise the fee and end when `SelectYec`/`SelectSapling` throw. No rule in `state.cpp` bounds the network fee (`grep g_yellowbackFee|networkFee src/yellowback/state.cpp` → none), so the larger conventional fee cannot trip a RED/MINT rule. Eviction under `-mempooltxcostlimit` is weighted-random with no low-fee penalty for P-2-priced transactions (`mempool_limit.cpp`), the same footing as any wallet transaction; an evicted mint fails without VOID (the carrier lapses and is swept), an evicted claim leaves the vault claimable later — grief only, generic to the mempool, covered by `yellowback_mempool_limits.py` (F-40). `RemoveInvalidVaultSpends` runs under `cs_main → pool.cs → cs_yellowback` after `removeExpired` (`main.cpp:4525-4526`).
- **(6) Regtest Equihash guard.** `if (NetworkIDString() == CBaseChainParams::REGTEST) return consensus.nEquihashN/K;` (`chainparams.cpp:984-985,993-994`), exactly 4 lines; mainnet/testnet fall through to `GetEquihashOverride` unchanged.
- **(7) Arity rows.** `qa/yellowback-rpc-cvt.py --check` passes (48 rows current); rows are generated from each handler's `fHelp ||` guard and the script exits on any unreadable guard or registered-without-guard handler; `sendrawtransaction` `{{s},{o,o}}` matches its `size() > 3` guard. A wrong `s`/`o` would only affect `ycash-cli` string conversion, not server-side acceptance.
- **(8) Wallet API shifts.** `AvailableCoins(coins, std::nullopt, true, nullptr, false, true, false, 1)` maps positionally to v4.5.0's `(true, nullptr, false, true, false, 1)` (`ycash6/src/wallet/wallet.h:1829-1837` vs `ycash-dd:1341-1344`); `GetFilteredNotes(sprout, sapling, orchard, filter, std::nullopt, 1, INT_MAX, true, true, true)` likewise (`:2514-2523`); `IsSpent(h, n, std::nullopt)` and `GetDepthInMainChain(std::nullopt)` are explicit everywhere (no defaulted parameter could shift). `CommitTransaction(wtx, reservekey, state)` adds only an out-parameter.
- **(9) Frozen set and budgets.** `git diff ycash6-baseline...HEAD --stat -- <frozen>` is empty; `qa/yellowback-audit.sh` reports main.cpp 19/40, miner.cpp 15/35, miner.h 5/10, rpc/mining.cpp 7/35, chainparams.cpp 4/4. The script is read-only (git diff + the `--check` generator).
- **(10) Baseline fixes.** `saplingAnchor = {}` in the three coinbase paths (`miner.cpp:196,235,252`) only replaces an uninitialised array fed to `sapling::new_builder` for spend-less bundles; v4 transactions carry no bundle anchor, so serialized blocks are unchanged — mainnet-safe. The harness fixes are `ycash.conf`/`src/ycashd` names only.
- **(11) rpcdump H8.** `importprivkey`, `importaddress`, `importwallet_impl` (both `importwallet` and `z_importwallet`), `z_importkey` declare `YellowbackReconcileOnExit` before `LOCK2` (`rpcdump.cpp:130,262,397,843`) so `Reconcile()` runs after `cs_wallet` is released. `rescanblockchain` has no 6.20.0 counterpart (V-3).
- **init.cpp hooks.** Identical to ycash-dd apart from the documented 6.20.0 additions: the pre-`ThreadImport` `ActivateBestChain` with `fImporting` false (F-37, skipped under `-reindex*`), the `FlushStateToDisk()` before `ClearRejected()` (F-30), and `Wipe()` deferred to `SyncToChain` under `cs_main` with a reconsider + flush (F-38, `index.cpp:114-140,261-264`). The duplicate flush commit `db91a1975` the review warns about is only on `yb6/lockorder` (`git branch --contains`), not merged.
- **Lock order of the new flushes.** `TripValve` and `Wipe` call `FlushStateToDisk()` under `cs_main` + `cs_yellowback`; `FlushStateToDisk` adds only `cs_LastBlockFile`; the lockorder CI job (S3) is recorded green.
- **CI.** `yellowback-tests.yml` triggers on `push`/`pull_request`/`schedule`/`workflow_dispatch` only; the inherited `ci-skip.yml` `pull_request_target` is upstream at the pin (`.github` delta vs `ycash6-legacy` is the one new workflow).

#### Not covered / needs a different auditor
- Whether YEW, lightwalletd-dd and the Python `test_framework` builders implement the P-2 fee rule; a client still paying the flat 1000 zat is refused or evicted first on 6.20.0 (`-txunpaidactionlimit`), which starves its mints/claims on that line only.
- The shared overlay logic itself (`state.cpp`, `policy.cpp`, `attest.cpp`, `bundle.cpp`, `script.cpp`, `payload.cpp`): byte-identical between the lines apart from includes, so it belongs to the ycash-dd auditor.
- Running anything: no build, no test, no devnet was executed (brief rule). The plan items still pending that bear on security: F-25 (B-1, open), §4.10 (first green GitHub CI on ycash6 not yet seen), F-44 (wallet-side notice polling, not a node issue), and the owner action to set the `boyfromcave/ycash6` default branch so the scheduled lockorder/sanitizer/fuzz jobs actually run.

---

### Node RPC and wallet surface (ycash-dd primary, ycash6 twin) — audit report

#### Summary
Read every `yed_*` handler in `ycash-dd/src/rpc/yellowback.cpp` (26 node-context commands) and `src/rpc/yellowbackwallet.cpp` (22 wallet-context commands), the wallet layer (`src/yellowback/wallet.{h,cpp}`), the transaction builder and selector (`txbuilder.{h,cpp}`, `coinselect.cpp`), the attestation pool and `AddAttestation` in `index.cpp`, the H5/H7/H8/I2 deltas vs `ycash-legacy` (`rpcwallet.cpp`, `rawtransaction.cpp`, `rpcdump.cpp`, `transaction_builder.{h,cpp}`), the `init.cpp` delta, `experimental_features.*`, the RPC contract JSON/markdown, and the behavioural diff of the same files under `ycash6`. Overall the surface is well-hardened: every command is registered only under `-experimentalfeatures -yellowback`, inputs are typed and range-checked, no key material reaches logs or RPC output, the wallet never broadcasts a half-signed Sapling-shaped transaction, and the stock-operator defaults are inert. The findings are two Medium items (an H8 gap in `importwallet`, and RPC-worker exhaustion via the blocking carrier wait), a Medium-conditional griefing window in the two-step mint (supply cap judged at inclusion, collateral then locked in a VOID vault), and a handful of Low/Info hardening and consistency items including two ycash-dd/ycash6 behavioural divergences.

#### Findings

##### C-1 [Severity: Medium] `importwallet` imports transparent keys without the H8 reconcile; freshly-mine YED is unlocked until the next block
- Where: ycash-dd/src/wallet/rpcdump.cpp:79-93 (guard struct), :117, :169, :303, :945 (the four call sites), :409-470 (`importwallet` / `importwallet_impl`, no guard); ycash6 twin: same file, same shape (mechanical diff auditor to confirm line numbers)
- Status: CONFIRMED
- Applies to: both
- What: H8 adds `YellowbackReconcileOnExit` to `rescanblockchain`, `importprivkey`, `importaddress` and `z_importkey` so YED outputs that become `IsMine` after an import are locked immediately. `importwallet` (the bulk restore path that imports every transparent key from a `dumpwallet` file and rescans) has no guard. Until the next connected block fires `onReconcile` (or the operator runs `yed_lockcoins`), those Tokens outputs are ordinary unlocked P2PKH coins to `sendtoaddress`/`z_sendmany`/`z_shieldcoinbase`/`z_mergetoaddress` coin selection.
- Evidence:
```
$ grep -n "YellowbackReconcileOnExit yellowbackReconcile" src/wallet/rpcdump.cpp
117: (rescanblockchain)  169: (importprivkey)  303: (importaddress)  945: (z_importkey)
$ grep -n "^UniValue \(import\|z_import\|rescan\)\w*(" src/wallet/rpcdump.cpp
138 importprivkey 259 importaddress 329 importpubkey 386 z_importwallet 409 importwallet 432 importwallet_impl 910 z_importkey 1016 z_importviewingkey 1231 z_importivk
```
`importwallet_impl` (line 432ff) takes `LOCK2(cs_main, cs_wallet)`, calls `AddKeyPubKey` per line and `ScanForWalletTransactions` — the same shape as `importprivkey`, minus the guard. (`importpubkey`, `z_importviewingkey`, `z_importivk`, `z_importwallet` are watch-only or shielded-only; `IsMineScript` requires `ISMINE_SPENDABLE`, so they need no guard.)
- Scenario: a user restores a wallet with `importwallet backup.txt` then immediately `sendtoaddress` a large YEC amount; the selector may spend a YED token output (10 000-zat P2PKH) as an input. The state machine burns the YED (XFER-1 assigns nothing). Local, needs the wallet owner's own action, but it is exactly the accident H5-H8 exist to prevent and the restore flow is the one where it is most likely.
- Recommendation: add `YellowbackReconcileOnExit yellowbackReconcile;` before the `LOCK2` in `importwallet_impl` (both lines). Consider also calling `Reconcile()` from `CWallet::AddToWallet`-adjacent hooks is out of scope (src/wallet frozen); the RAII guard is the minimal fix.

##### C-2 [Severity: Medium] `WaitForCarrier` blocks an HTTP worker thread for up to `-yellowbackcarriertimeout` (600 s); four concurrent waits wedge the whole RPC server
- Where: ycash-dd/src/rpc/yellowbackwallet.cpp:388-401 (`WaitForCarrier`), :757, :887, :932, :1188 (the `wait=true` default path of `yed_mint`, `yed_claim`, `yed_claimnotice`, `yed_reportequivocation`); src/httpserver.h:12 `DEFAULT_HTTP_THREADS=4`; ycash6: identical
- Status: CONFIRMED
- Applies to: both
- What: with `wait` defaulting to `true`, each of these RPCs polls `CarrierConfirmed()` every 200 ms until the carrier has one confirmation, holding its libevent worker. There is no cap on concurrent waiters and no shorter default for programmatic callers.
- Evidence:
```
const int64_t timeoutMs = std::max<int64_t>(1, GetArg("-yellowbackcarriertimeout", 600)) * 1000;
...
while (!CarrierConfirmed(c.outpoint)) { ... MilliSleep(200); }
```
- Scenario: a GUI or script (or any authenticated RPC user — a shared pool/attestor node often has several) issues four `yed_mint … wait=true` while blocks are slow (or the carrier is stuck below the mempool fee floor). All four workers block; `getblocktemplate`, `yed_setquote`, `yed_signattestation` and `stop` are unreachable for up to ten minutes. On an enforcing pool node this stalls block production. Local-DoS class, but the trigger is the documented default usage.
- Recommendation: bound concurrent waiters (a small semaphore, refuse with `carrier-wait-busy`), or make `wait=false` the default for non-interactive use and document the completion-thread path; also cap `-yellowbackcarriertimeout` and list it in `HelpMessage` (it is undocumented, see C-8).

##### C-3 [Severity: Medium] Two-step mint: the supply cap (MINT-6) is judged at inclusion against live totals, so a mint that passed preflight and the pre-commit dry run can confirm VOID and lock its collateral until `lockHeight`
- Where: ycash-dd/src/yellowback/txbuilder.cpp:812-816 (preflight cap check against `GetTotals()` at the index tip), :1180 (`DryRunOrThrow` at H = tip+1, index state only), src/yellowback/state.cpp:334-335 (MINT-6 at inclusion), src/rpc/yellowbackwallet.cpp:430 (`MempoolGate … trivially true for a mint`), txbuilder.cpp:1291-1298 (`BuildRedeem` requires `indexHeight >= lockHeight` for the VOID release too); ycash6: same logic
- Status: CONFIRMED (mechanism) / PLAUSIBLE (deliberate griefing)
- Applies to: both
- What: MINT-1..10 are evaluated inside the block; the vault is created VOID rather than the transaction being invalid, so miners include it and the collateral is locked by the P2SH CLTV script until `lockHeight` (the VOID release in `yed_redeem` enforces `vault-locked` as well). The only MINT rule whose inputs are not fixed at R is MINT-6 (`totals.supplyCents + cents > cap`), which depends on which other mints land first. The wallet's preflight and dry run both read confirmed index state, never the mempool, and MP-1 does not police mints.
- Evidence:
```
// txbuilder.cpp:813-816 (wallet, confirmed state)
std::optional<Cents> cap = SupplyCapCents(S->issuedZat, g.xMint, p.supplyCapBps);
if (cap.has_value() && totals.supplyCents + cents > cap.value()) throw ... "mintpol-cap"
// state.cpp:334-335 (consensus-in-overlay, at inclusion)
std::optional<Cents> cap = SupplyCapCents(S->issuedZat, xMint, P.supplyCapBps);
if (cap.has_value() && totals.supplyCents + (Cents)p.cents > cap.value()) return verdict::MINT_SUPPLY_CAP;
```
- Scenario: supply is within one mint of the cap. Victim's `yed_mint` passes preflight, its carrier confirms, its MINT enters the mempool. An observer submits a competing MINT with a higher fee (or is simply earlier in the block). Victim's vault records VOID; victim's collateral (potentially class C, hundreds of blocks) is locked with no YED issued and no fee refund. Loss of availability only, needs the cap to be nearly exhausted (mainnet `supplyCapBps` makes this rare; regtest/testnet caps make it easy).
- Recommendation: (a) in the template filter (`-yellowbacktemplatepolicy=strict`) drop a MINT whose verdict would be VOID — a policy change on the miner side only, no consensus change; (b) in `CompleteMint`, also count MINT payloads already in the mempool toward the cap before committing (the way `yed_getbalance` already walks `mempool.mapTx`); (c) document the residual race in `doc/yellowback-rpc.md` under `yed_mint`.

##### C-4 [Severity: Low] Behavioural divergence between the two node lines: `claimable` and `poolFresh` are computed differently
- Where: ycash-dd/src/rpc/yellowback.cpp:252-256 (`VaultToJSON.claimable`: v2 clause (a) under the tip snapshot only) vs ycash6/src/rpc/yellowback.cpp:252-254 (`EstimateClaim(...).claimable`, RED-4 by either clause); ycash-dd/src/rpc/yellowbackwallet.cpp:215-220 (`VaultRow`) vs ycash6 :193 (takes the caller's `EstimateClaim` verdict); ycash-dd/src/rpc/yellowback.cpp:638, :1701 (`PoolHasNewerThan(seq, h - REF_LAG - attestMaxAge)`) vs ycash6 :637, :1706 (`PoolFreshAt(seq, h - REF_LAG)`); ycash-dd/src/rpc/yellowbackwallet.cpp:599-601 (`yed_getnewaddress` from keypool) vs ycash6 :594-596 (`GenerateNewKey`, requires an unlocked wallet)
- Status: CONFIRMED
- Applies to: both (the fix landed on ycash6 only)
- What: on ycash-dd, `yed_getvault.claimable`, `yed_listvaults[].claimable` and `yed_listpositions[].claimable` ignore the emergency clause (b) and the combined `pClaim` while armed, so a vault `yed_listclaimable` lists is reported `claimable: false` by `yed_getvault`. The `poolFresh` predicate on ycash-dd accepts attestations citing a height above R (`citedHeight > h - lag - maxAge` with no upper bound), which `Freshest()` (index.cpp:927) would never select for a bundle at R; ycash6's `PoolFreshAt` mirrors `Freshest`. These are the "fix both node lines" rule being missed.
- Evidence: see the `diff ycash-dd/src/rpc/yellowback.cpp ycash6/src/rpc/yellowback.cpp` hunks at 252-255, 638, 1701.
- Scenario: a GUI reading ycash-dd shows "not claimable" for a vault that a claim would in fact open under clause (b); an attestor dashboard shows `poolFresh: true` for an attestation that no bundle can use. No funds at risk; wrong operator decisions.
- Recommendation: port the ycash6 `EstimateClaim`-based `claimable` and `PoolFreshAt` to ycash-dd (they are pure RPC-layer changes) and record the keypool/`GenerateNewKey` difference in `doc/yellowback-rpc.md` (`yed_getnewaddress` on 6.20.0 needs `walletpassphrase`).

##### C-5 [Severity: Low] Signing guard is keyed by `(seq, citedHeight)` without the block hash: after a reorg it returns a stale, non-verifying signature as `reused: true` and refuses a correct re-sign
- Where: ycash-dd/src/yellowback/txbuilder.cpp:1491-1500 (`SignAttestationGuarded`), src/yellowback/wallet.cpp:490-515 (`LookupSigned`/`RecordSigned`); ycash6: same
- Status: CONFIRMED (by reading; a regtest reorg across `citedHeight` would demonstrate it)
- Applies to: both
- What: `AttestMessage` commits to `blockHash(citedHeight)`, but the guard record does not. If the block at `citedHeight` is reorged out, `LookupSigned` finds the prior entry, and (same price) hands back the old `sig` marked `reused`, which `yed_addattestation` on any node rejects as `attest-bad-sig`; (different price) refuses `equivocation-guard` although signing a different chain is not equivocation under EQV-1 (which also binds the hash, txbuilder.cpp:1564-1567).
- Evidence:
```
std::optional<SignedAttestation> prior = yw.LookupSigned(seq, (uint32_t)citedHeight);
if (prior.has_value()) { if (prior->priceMicroUsd != price) throw "equivocation-guard…"; a.sig = prior->sig; reused = true; return a; }
const uint256 msg = AttestMessage(seq, a.priceMicroUsd, a.citedHeight, ctx.BlockHashAt(citedHeight));
```
- Scenario: a 2-block reorg at the attestor's cited height; the attestor agent keeps calling `yed_signattestation` for that height and silently publishes a signature nobody accepts, losing the attestor's bundle slot (and fee share) for that height; its freshness lapses toward dormancy if repeated. Fail-safe (never equivocates), availability only.
- Recommendation: store `blockHash` in `SignedAttestation` and key the guard on `(seq, citedHeight, blockHash)`; keep refusing a different price for the *same* hash. Bump `SIGNED_MAGIC` for the new record layout.

##### C-6 [Severity: Low] Several read RPCs are whole-table scans with no paging bound, callable by any RPC-authenticated user
- Where: ycash-dd/src/rpc/yellowback.cpp:1202-1214 (`yed_listtokens`, full `K` table per call, up to 100 addresses), :1153-1162 (`yed_listvaults` scans the whole `V` table when the status filter matches nothing), :1254-1281 (`yed_listclaimable`: `BuildBundleInfo` + signature verification per ACTIVE-past-claimHeight vault), :943-951 and :975-996 (`yed_listminers`: `window` is unbounded above), :1668-1674 (`yed_listattestors`: whole BundleLog); src/rpc/yellowbackwallet.cpp:1293-1313 (`yed_listpositions`: `EstimateClaim` per own vault), :1338-1413 (`yed_listtransactions`: whole `L` table plus `mapWallet` every call, then paged in memory); ycash6: same
- Status: CONFIRMED
- Applies to: both
- What: cost is linear in index size (bounded by the chain, so not unbounded in the strict sense) and all of it runs under `cs_yellowback` (and `cs_main`/`cs_wallet` for the wallet ones), stalling block connection for the duration.
- Evidence: `index.View().Iterate("K", …)` with no early exit in `yed_listtokens`; `for (size_t i = skip; …)` after building every row in `yed_listtransactions`.
- Scenario: a lightwalletd or GUI polling `yed_listtokens` for 100 addresses every few seconds on a mature index keeps `cs_yellowback` busy; combined with C-2 this is a cheap way for an authenticated-but-careless client to degrade an enforcing node.
- Recommendation: cap `window` in `yed_listminers` (e.g. `<= 4 * payeeWindow`), add `count/skip` to `yed_listtokens` and `yed_listclaimable`, iterate `L` by height range in `yed_listtransactions`, or add a per-script secondary index for tokens if lightwalletd depends on `yed_listtokens` at scale.

##### C-7 [Severity: Low] `sendrawtransaction` H7 guard covers only the "no reassignment at all" case; a TRANSFER that reassigns part of the spent YED, or a malformed REDEEM, passes silently
- Where: ycash-dd/src/yellowback/wallet.cpp:518-520 (`YedBurnedByRawTransaction`), src/rpc/rawtransaction.cpp:1141-1153; ycash6: same
- Status: CONFIRMED
- Applies to: both
- What: the guard returns `false` for any REDEEM payload (documented: "judged by MP-1") and for any TRANSFER whose `assignments` is non-empty, regardless of whether `Σ assigned cents == Σ spent cents`. A hand-built TRANSFER assigning 1 cent of a 10 000-cent input burns 9 999 cents; a REDEEM payload spending own tokens that is not a vault spend (no vault input) burns everything, and MP-1 does not reject it (it is not a vault spend).
- Evidence:
```
if (fp.has_value() && fp->payload.type == PayloadType::REDEEM) return false;
if (fp.has_value() && fp->payload.type == PayloadType::TRANSFER && !fp->payload.assignments.empty()) return false;
```
- Scenario: a wallet integrator constructing TRANSFERs by hand (lightwalletd/YEW will not use this path, but `createrawtransaction` users might) under-assigns and loses YED with no warning; the guard advertises protection it does not give.
- Recommendation: compare `Σ assignments.cents` against `Σ` own spent cents and refuse on a shortfall unless `allowyedburn`; treat a REDEEM payload with no vault input (`FindCarrierInput`/vault outpoint lookup) like a TRANSFER.

##### C-8 [Severity: Info] Contract / documentation / help gaps
- Where: ycash-dd/doc/yellowback-rpc-contract.json (`yed_sendmany.args` is empty; the markdown has no `yed_sendmany` heading — my script: `handler-not-md ['yed_sendmany']` in both forks); ycash-dd/src/init.cpp `HelpMessage` does not list `-yellowbackcarriertimeout` (read at yellowbackwallet.cpp:391); src/wallet/rpcdump.cpp:82-84 says Reconcile "takes cs_yellowback and then cs_wallet", while `Reconcile()` (wallet.cpp:660-698) takes them sequentially, never nested (the N25 comment inside `Reconcile` is the correct one)
- Status: CONFIRMED
- Applies to: both
- What: contract JSON is byte-identical in both forks and every handler name matches a contract key and vice versa (verified); the three items above are the only inconsistencies found.
- Recommendation: give `yed_sendmany` its own block (`args: <{yedaddress: cents, …}>`), add the timeout flag to help, fix the stale comment.

##### C-9 [Severity: Info] Datadir path leaks into RPC error text
- Where: ycash-dd/src/yellowback/txbuilder.cpp:1511 (`"guard-write-failed: cannot append to " + SignedFile().string()`), src/yellowback/wallet.cpp (log lines only, fine); ycash6: same
- Status: CONFIRMED
- Applies to: both
- What: an RPC-authenticated caller learns the absolute datadir path on a write failure. Harmless for a local operator; mildly undesirable for shared nodes.
- Recommendation: log the path, return the identifier only.

##### C-10 [Severity: Info] `yed_estimatesend` sums recipient amounts before range-checking them (signed overflow)
- Where: ycash-dd/src/rpc/yellowbackwallet.cpp:1457-1460 then :1470; ycash6: same
- Status: CONFIRMED
- Applies to: both
- What: `amount += obj[name].get_int64()` over up to 14 values can wrap (UB) before `amount < p.minOutput || amount > p.maxOutput` is tested; `BuildTransfer` (txbuilder.cpp:1220-1225) checks each amount first, so the real send path is safe. Dry-run only; no funds at risk.
- Recommendation: check each amount in the loop as `BuildTransfer` does.

##### C-11 [Severity: Info] `wait=false` completions are memory-only; a restart strands a confirmed carrier until its window lapses
- Where: ycash-dd/src/yellowback/wallet.h:184-193, wallet.cpp:519-523 (`pending` map, not persisted); carriers themselves are persisted (carriers.dat) and swept by `yed_sweepcarriers`/`StartupSweep`; qa/rpc-tests/yellowback_wallet_restore.py:146-166 exercises exactly this
- Status: CONFIRMED (documented and tested behaviour)
- Applies to: both
- What: only `CARRIER_VALUE` (10 000 zat) plus the carrier fee is tied up for at most `REF_WINDOW` (40) blocks, then reclaimed. Recorded here because the brief asks for the carrier flow's windows; no action needed beyond perhaps persisting the pending intent (cents, lockBlocks, from) in carriers.dat so a restart can finish the mint.

#### Checked and found sound
- Experimental gating: both `RegisterYellowbackRPCCommands` (rpc/yellowback.cpp:1933-1944) and the wallet registration (init.cpp delta, `if (fExperimentalYellowback) RegisterYellowbackWalletRPCCommands`) register nothing without `-yellowback`; `EnsureIndex`/`EnsureYW` re-check at call time; `InitExperimentalMode` refuses `-yellowback` without `-experimentalfeatures` (experimental_features.cpp). No `yed_*` is reachable on a stock-configured node; `help` shows the v4.5.0 surface. `qa/rpc-tests/yellowback_stock_node.py` is cited as the regression.
- Argument validation (rpc/yellowback.cpp): heights via `HeightArg` with explicit range checks; `ParseHashV` for every txid/blockhash; `SelectorArg` enforces exactly 0 or 36 bytes (R13); `yed_addattestation`/`ParseAttestationArg` require hex and exactly `ATTESTATION_SIZE` bytes; `yed_setquote` bounds price to `[PRICE_MIN, PRICE_MAX]` and mask to 16 bits and refuses without a payout key; `yed_getfeepayee`/`yed_estimatefee` bound collateral to `[0, MAX_MONEY]`; `yed_gethistory` caps 2016 rows; `yed_listtokens` 1..100 addresses with both YED and P2PKH forms decoded against the network; `yed_estimatecollateral`'s `priceMicroUsd` override is fed to `RequiredCollateral` which returns nullopt for `pMint <= 0` (math.h:115-124) so no division by zero; `yed_decodepayload` decodes bundles with a 255 cap and never verifies; `BlockIndexOf` saturates `atoi64` and range-checks. All refusals carry the stable identifier and the right code class (`ThrowBuildError`'s RULE/PARAM tables).
- `yed_addattestation` (index.cpp:1016-1057): refuses unknown/ejected/withdrawn seqs, stale or future `citedHeight`, out-of-range price, and verifies the compact signature against this chain's block hash through the LRU sig cache before pooling; pool is bounded at `POOL_PER_SEQ = 3` per registered seq (index.h:138), so memory is `O(attestors × 3)`; `BuildBundleInfo` re-verifies after reorgs (R9).
- Key handling: `yed_registerattestor`, `yed_signattestation`, `yed_revive` return public keys, signatures and hex only; `carriers.dat` holds outpoint/bundle/pubkey, `attest-signed.dat` holds (seq, height, price, sig) — no private material in either; `LogPrintf` lines in wallet.cpp/yellowbackwallet.cpp print txids, outpoints and counts only. The hot key and bond key are ordinary keypool keys (wallet.dat backup rule is stated in every help text). `SignAttestationGuarded` fsyncs the guard before returning and fails closed on write failure (txbuilder.cpp:1506-1511).
- Coin locking (wallet.cpp:632-727): stage (i) `LockOwn` before `CommitTransaction`; stage (ii) `PreLock` on `onSyncTransaction` (mempool arrival) for MINT/TRANSFER/REDEEM assignments that are mine; stage (iii) `Reconcile` after every applied block and at startup (init.cpp delta), releasing only outpoints whose transaction is confirmed in TxLog and assigned no cents — never on disconnect (C3), so a reorg cannot unlock. Vault collateral, carriers and bonds are P2SH and not `IsMine`, so stock coin selection never sees them; `SelectYec` additionally skips any P2SH and any Tokens/Vaults outpoint (txbuilder.cpp:412-414). `AvailableCoins` honours `IsLockedCoin` (wallet.cpp:5074) for `sendtoaddress`, `z_sendmany`, `z_shieldcoinbase`, `z_mergetoaddress`.
- H5 `lockunspent` (rpcwallet.cpp delta): unlocking a Yellowback-held outpoint is refused atomically (checked before any lock is touched); `lockunspent true` with no list re-applies the overlay locks; locking is unrestricted. `yed_unlockcoin` needs the literal acknowledgement and reports `wasYellowbackLocked`/`cents`.
- H6 (init.cpp delta): a datadir with a `yellowback/` directory refuses to start without `-yellowback` unless `-yellowback=0` is explicit or `-disablewallet`; `-prune` is refused; all regtest-only flags are refused off-regtest; `-yellowbackfee` floor = `DEFAULT_YELLOWBACK_FEE` (1000 zat); `-yellowbackmintlag` in `[0, MAX_REF_LAG]`; payout/preferred-payee must be P2PKH; `-yellowbackpreferredattestor` is a u16. Stock operator (no `-yellowback`): no index, no RPCs, no hooks, no validation interface registered. Kill switch (`-yellowbackenforce=0`) reconsiders only recorded rejections under `cs_main` then `ActivateBestChain` outside it; ycash6 additionally `FlushStateToDisk()`s before clearing the record (a correct hardening of the same path).
- I2 unsigned-input builder (transaction_builder.{h,cpp} delta): `AddTransparentInputUnsigned` records `sign=false`; `Build()` skips those inputs and signs the rest with the keystore as before; every Sapling-shaped flow (`RunVaultSpend`, `CompleteMint`, `CarrierStep`, `yed_withdrawbond`) runs `FinishSapling` with no lock held, then re-locks, re-checks `EnsureWalletIsUnlocked`/`EnsureHealthy`, signs (`SignVaultSpend`/`SignBuiltInputs`), dry-runs (`DryRunBuilt`) and MP-1-gates before `Commit`. A signing failure throws and the `BuiltTx` is dropped; the raw hex is returned only by `yed_sweep`, after commit. No path logs or returns an unsigned transaction.
- Fee and change (txbuilder.cpp): flat `g_yellowbackFee` on ycash-dd; ycash6 reprices every shape with ZIP-317 `max(g_yellowbackFee, CalculateConventionalFee(actions))` in a monotone loop (`Reprice` only rises, so it terminates) and prices the vault spend out of the collateral (`PlanPricedVaultSpend`). `nExpiryHeight = R + REF_WINDOW` with `CheckExpiry` refusing "expiring too soon"; change goes to a reserved key (YEC) or a fresh keypool key (YED, locked via `ownYedOutputs`); mint collateral is `max(required, 4*feeMin)` rounded up to 1000; `PlanVaultSpend` throws `vault-value-too-small` when fees exceed the vault. Prices come from the index (`xMint`) and a BUNDLE-1-verified bundle (`aMint`) with `pMint = min(x, a)` and MINT-10 divergence refused — a malicious `bundleHex` must carry valid signatures of the selected attestors, so a user cannot be tricked into over-collateralising by unauthenticated input; the only user-overridable price is `yed_estimatecollateral`'s estimate.
- Two-step carrier flow: `CheckCarrier` requires a confirmed unspent coin whose R is inside the window; `BuildClaim`/`BuildClaimNotice` require the carrier's selector to equal the vault outpoint; `BuildEquivocation` requires the committed bundle to equal `{a, b}`; the main transaction spends the carrier as the last input and `ownYedOutputs` is recomputed after the carrier is signed. Lapsed carriers are swept (`BuildSweepCarriers`) at startup and on demand, and a lapsed record whose outpoint is already spent is forgotten.
- Wallet restore (`qa/rpc-tests/yellowback_wallet_restore.py`): a second wallet importing node 0's keys without a rescan sees identical balance, coins and positions from the index alone, locks them with `yed_lockcoins`, redeems with the imported owner key; an encrypted wallet refuses every signing command while locked; a carrier survives a restart in carriers.dat. Nothing Yellowback-specific is written to wallet.dat, so restore state is a pure function of (keys, index).
- Lock order: every handler takes `cs_main → cs_wallet → mempool.cs → cs_yellowback` (N25) as commented; `yed_getinfo` reads `LockedCount()` (cs_wallet) before `mempool.cs`; `Reconcile`/`PreLock` never nest `cs_yellowback` inside `cs_wallet`; `YedBurnedByRawTransaction` takes `cs_wallet` before `cs_yellowback` under the caller's `cs_main`.
- `Commit` (wallet.cpp:316-335) erases the blank `mapWallet` entries the inherited `CommitTransaction` inserts for foreign inputs (claimed vault, restored bond) — the F-7 crash fix — and only when they have no inputs and no outputs.
- RPC contract: `doc/yellowback-rpc-contract.json` byte-identical in both forks; every `yed_*` key has a handler and vice versa; arity in the help strings matches the contract args for all 48 commands (one omission, C-8).

#### Not covered / needs a different auditor
- Consensus/state-machine correctness of MINT-1..10, RED-1..5, BUNDLE-1, EQV-1, the index apply/undo symmetry and reorg handling (`state.cpp`, `index.cpp`, `bundle.cpp`, `attest.cpp`) — only the RPC-facing entry points were read.
- The mechanical ycash-dd ↔ ycash6 diff (assigned elsewhere); I report only the behavioural differences I noticed (C-4, ZIP-317 repricing, `GenerateNewKey`, `ActivateBestChain`/`FlushStateToDisk` in init).
- The YecWallet, lightwalletd `YellowbackStreamer`, YEW and yolo clients of these RPCs; the attestor agent under `contrib/yellowback/attest` and `yellowback-quote` (which call `yed_signattestation`/`yed_setquote` and would be where C-5 bites).
- ZIP-317 fee-floor interaction with ycash6's mempool policy was read in the builder only; whether the mempool's minimum relay fee can still reject a repriced Yellowback transaction was not verified.
- No build or test was run (brief: read-only).

---

### Off-node operator tooling (contrib/yellowback, attestor agent, quote tool, devnet/pool scripts, packaging) — audit report

#### Summary

Covered `ycash-dd/contrib/yellowback/**` in full (the Rust attestor agent `attest/` — all nine source files plus Cargo metadata, toolchain, packaging and sample config; the Python `yellowback-quote` and `yellowback_price.py`; `pool/` check-coinbase, monitor-quote.sh, units; `devnet/` yellowback-devnet, yellowback-sim, stratum-miner, stratum-perl-check, lwd-rawmint; `attest/calibrate/`), the `ycash6` twin (diffed file by file), the CI job that builds the agent, and `doc/yellowback-attestor.md`, `yellowback-mining.md`, `yellowback-devnet.md`. Read-only; nothing was built or run. The overall picture is sound: the agent holds no key, signing and signature verification stay in the node, the attestation message is bound to the cited block hash, supply chain is exact-pinned with `--locked` CI, systemd units run unprivileged and hardened, and the aggregator fails closed below `min_sources`/`min_venues`. The real defects are in robustness against a hostile or broken price venue: the Rust aggregator panics (crash loop) on a non-finite numeric string in a venue's volume field and turns a `"nan"` price into a 0 µUSD sample, the Python quote agent can be stalled indefinitely by a slow-drip venue because it fetches serially with a per-socket timeout, and neither tool bounds response bodies. The subscriber forwards every registered-`seq` gossip message to the node unthrottled on a topic anyone can join. The two node lines' `contrib/yellowback` trees are byte-identical apart from docs and the `BITCOIND`/`ZCASHD` env name, with one real code divergence (a devnet cleanup fix present only on ycash6).

#### Findings

##### D-1 [Severity: Medium] Rust aggregator: a venue returning `"inf"`/`"nan"` as a numeric string crashes the attestor (panic in `median`) or injects a 0 µUSD sample
- Where: ycash-dd/contrib/yellowback/attest/src/price.rs:579-586 (`to_f64`), :894-897 (`price <= 0.0`), :920-923 (`py_round`), :927-936 (`weight`), :1051-1061 (`window_average`), :822-831 (`median`); ycash6 twin: identical lines (files are byte-identical)
- Status: CONFIRMED (traced; not executed)
- Applies to: both (attestor agent; same crate in both node lines)
- What: `to_f64` accepts any string `str::parse::<f64>` accepts, and Rust's `f64: FromStr` accepts `"inf"`, `"infinity"`, `"nan"` (case-insensitive). Kraken and Peatio (SafeTrade) return their numbers as JSON strings, so a compromised or misbehaving venue (or a shape change) can deliver non-finite values that pass every guard:
  - Volume: `extract_number(&obj, vp).ok()` yields `Some(inf)`; `weight()` returns `Some(inf)` because `inf > prev`; once every sample after the first in the window carries a `Some` weight, `window_average` computes `inf/inf = NaN`; `live_twaps` returns a NaN TWAP; `aggregate` calls `median`, whose `sort_by(|a,b| a.partial_cmp(b).expect("no NaN in prices"))` panics. With `Restart=always` the unit crash-loops for as long as the venue serves the value (the window persists only in memory, but the next poll reproduces it after two more samples).
  - Price: `"nan"` gives `price = NaN`; `NaN <= 0.0` is false so the "not positive" check passes; `py_round(NaN * MICRO)` is `NaN.round_ties_even() as i64 == 0`, so a 0 µUSD sample enters the window. `"inf"` saturates to `i64::MAX`. These are mostly caught downstream (outlier filter; the `u32` range check at attest.rs:229), but a 0 sample drags that source's TWAP for 15 minutes, and the Python reference refuses the same input (`int(round(nan))` raises), so the two aggregators diverge on exactly the input the fixtures do not cover.
- Evidence:
  ```rust
  fn to_f64(v: &Value) -> Option<f64> { match v { Value::Number(n) => n.as_f64(),
      Value::String(s) => s.trim().parse::<f64>().ok(), ... } }                       // price.rs:579
  let mut price = extract_number(&obj, &src.path)? * src.scale;
  if price <= 0.0 { return Err(ShapeError(format!("price not positive: {price}")).into()); } // :894
  match (volume, prev) { (Some(v), Some(p)) if v > p => Some(v - p), _ => None }      // :933
  let tot: f64 = samples[1..].iter().map(|s| s.weight.unwrap_or(0.0)).sum();
  return samples[1..].iter().map(|s| s.micro as f64 * s.weight.unwrap_or(0.0)).sum::<f64>() / tot; // :1053
  v.sort_by(|a, b| a.partial_cmp(b).expect("no NaN in prices"));                      // :824
  ```
- Scenario: SafeTrade's Peatio endpoint (string-typed `volume`) is compromised or buggy and answers `"volume":"inf"`. Every attestor using the `peatio_ticker` preset with the default config crashes at the third poll and restarts every 5 s; none of them publishes, the attestor set thins toward `ATTEST_ARM_MIN`, and the attestors involved drift toward dormancy. Cost to the attacker: one venue. No funds at risk directly (the node still signs only what it is asked), but availability of the attestation layer.
- Recommendation: in `to_f64` (or right after `extract_number`) reject non-finite values (`f.is_finite()`), reject non-finite `scale`, and make `median` total-order (`f64::total_cmp`) or filter non-finite TWAPs before it. Add a fixture scenario with `"inf"`/`"nan"`/`Infinity` so the Rust/Python cross-check pins the behaviour. Apply the same `is_finite` guard in `yellowback_price.py` (D-2).

##### D-2 [Severity: Low] Python quote agent: non-finite volume or price silently poisons a source's window; Python's `json.loads` also accepts bare `NaN`/`Infinity` literals
- Where: ycash-dd/contrib/yellowback/yellowback_price.py:460-465 (`extract_number`), :538 (`json.loads` default `parse_constant`), :572-580 (`_weight`), :648-656 (`_window_average`), :682-688 (`aggregate`); ycash6 twin identical
- Status: CONFIRMED (traced)
- Applies to: both (quote agent used by pools; same file in both lines)
- What: `float("nan")`/`float("inf")`/`json.loads('{"v": Infinity}')` all succeed. A NaN/inf price is refused later by `int(round(...))` raising (caught by the broad `except Exception` in `poll`, so no crash). A NaN or inf **volume** is not: `_weight` returns `nan - prev` (because `nan <= prev` is False) or `inf`, `_window_average` yields NaN, `statistics.median` over a list containing NaN sorts non-deterministically, and the outlier comparison with NaN is False, so the affected source silently drops out — or, if the NaN lands in the middle of the sort, `med` is NaN and `kept` is empty: the pool's quote clears to signal-only after `fail_polls`. No crash, no wrong price (fail closed), but an unexplained outage that `sources` reports as "ok".
- Evidence:
  ```python
  def _weight(self, name, volume):
      prev = self.last_volume.get(name)
      if volume is not None: self.last_volume[name] = volume
      if volume is None or prev is None or volume <= prev:   # NaN <= prev is False
          return None
      return volume - prev                                     # NaN or inf
  ```
- Scenario: as D-1 but against pools; outcome is a silent signal-only pool rather than a crash.
- Recommendation: `math.isfinite` on every extracted number; `json.loads(..., parse_constant=...)` that rejects `NaN`/`Infinity`; a unit test in `test_yellowback_price.py` and `fixtures/scenarios.json`.

##### D-3 [Severity: Medium] Quote agent fetches sources serially with a per-socket timeout: one slow-drip venue stalls every poll; neither tool bounds the response body
- Where: ycash-dd/contrib/yellowback/yellowback_price.py:526-530 (`_http_get`, `urlopen(..., timeout=)` then `resp.read()`), :636-645 (`poll`, sequential loop), :598-608 (`_btc_reference_usd`, sequential); ycash-dd/contrib/yellowback/attest/src/attest.rs:37-57 (`fetch_all`, `resp.bytes()` unbounded) and rpc.rs:101; ycash6 identical
- Status: CONFIRMED (traced)
- Applies to: both (quote agent: Medium; attestor agent: Low — see below)
- What: `urllib`'s `timeout` is a per-operation socket timeout, not a deadline. A venue that sends one byte every 14 s never trips a 15 s timeout, and because `poll()` iterates the sources in order, the whole poll (and the daemon's `run_loop`) blocks on that one venue. The pool's quote goes stale, `yed_setquote` is never called again, and the node falls back to signal-only via its own `-yellowbackquotemaxage` clock — which is the designed backstop, but the agent reports nothing and the operator's monitoring (`monitor-quote.sh`) only sees "stale". `resp.read()` has no size cap, so a venue can also push an arbitrarily large body into memory (bounded only by the drip rate × whatever time it chooses). The Rust fetcher uses reqwest's `.timeout()`, which is a total deadline covering the body, and fetches all sources concurrently, so it is only exposed to `bandwidth × fetch_timeout` bytes of memory per source — a much smaller problem, but still unbounded in configuration.
- Evidence:
  ```python
  def _http_get(url, headers, timeout):
      req = urllib.request.Request(url, headers=...)
      with urllib.request.urlopen(req, timeout=timeout) as resp:
          return resp.read()                       # no size cap, per-op timeout only
  ...
  for s in self.sources:                           # serial
      micro, age, spread, volume = self._sample(s, now, btc_median)
  ```
- Scenario: a venue (or anyone on the path who can hold a TCP connection open — HTTPS protects integrity, not liveness) drips the ticker body. Every pool using that venue stops updating its quote within one poll, stays signal-only, and the pools' side of `pMint`/`pClaim` thins to whichever pools do not use that venue.
- Recommendation: Python — fetch sources in a thread pool with a wall-clock deadline (`concurrent.futures` + `wait(timeout)`), and `resp.read(MAX+1)` with a 1 MiB cap. Rust — `Content-Length` check and a streamed read capped at ~1 MiB (`resp.bytes()` → `resp.chunk()` loop), and the same cap in rpc.rs (the node is trusted, so Low there).

##### D-4 [Severity: Low] HTTP redirects are followed and the CoinGecko API key header rides along to any host
- Where: ycash-dd/contrib/yellowback/attest/src/attest.rs:30-34 (reqwest `Client::builder()` with default redirect policy, limited(10)); yellowback_price.py:528-529 (`urllib` default `HTTPRedirectHandler`); headers: price.rs:217-222 / yellowback_price.py:210-211 (`x-cg-demo-api-key`)
- Status: CONFIRMED (default-policy behaviour of both libraries; not executed)
- Applies to: both
- What: both clients follow 3xx redirects, including to another host and from https to http. reqwest strips only `Authorization`/`Cookie`-class headers on cross-origin redirects; `urllib` copies all non-`Content-*` request headers. The operator's `api_key` (sent as a custom header) therefore leaks to any host CoinGecko — or whoever controls its edge — redirects to. Price integrity is unaffected (the redirect target is as untrusted as the origin and goes through the same guards).
- Evidence: `let client = reqwest::Client::builder().timeout(...).user_agent("yellowback-attest/3").build()?;` — no `.redirect(Policy::none())`.
- Scenario: credential leak of a demo-tier API key; low value.
- Recommendation: `redirect(reqwest::redirect::Policy::none())` (venue APIs do not redirect) or a policy that refuses host/scheme changes; in Python, a `HTTPRedirectHandler` subclass that drops the key on host change or refuses redirects.

##### D-5 [Severity: Medium] Subscriber forwards every registered-`seq` gossip message to `yed_addattestation` with no local throttling, on a topic anyone can join
- Where: ycash-dd/contrib/yellowback/attest/src/subscribe.rs:72-86 (`handle`), :88-118 (`push`), :158-171 (`run` select loop); transport/iroh.rs:36-38 (`topic_id` = SHA-256 of the public name), :103-116 (default relay = n0 public relays); ycash6 identical
- Status: CONFIRMED for the agent side; PLAUSIBLE for impact (node-side per-seq/per-call bounds of `yed_addattestation` not audited here)
- Applies to: both (subscriber beside every minting node, including YecWallet's bundled node)
- What: the only pre-RPC filters are "exactly 74 bytes (or hex of)" and "`seq` is in `yed_listattestors`". The registered `seq` set is public, the topic id is `SHA-256("yellowback/attest/main/3")`, and iroh's default relays are public, so any party can join the swarm and broadcast 74-byte frames with a valid `seq` and garbage signatures at line rate. Each frame becomes one HTTP JSON-RPC round-trip and one secp256k1 verification in the node, serialized on the single-threaded `recv` loop — which also means legitimate attestations queue behind the flood (`Event::Lagged` drops them, iroh.rs:189). There is no per-`seq` token bucket, no dedup of already-seen frames, and no backoff.
- Evidence:
  ```rust
  if !self.known_seqs.contains(&att.seq) { ... return Outcome::UnknownSeq(att.seq); }
  self.push(&att).await        // -> node.call("yed_addattestation", ...) for every frame
  ```
- Scenario: a griefer joins the mainnet topic and broadcasts 10k frames/s with `seq` 0..8 and random signatures. Every subscriber's node spends its RPC worker on signature failures; honest attestations arrive late or are dropped as `Lagged`, so `poolFresh` goes false on minting nodes and mints/claims fail to find bundles until the flood stops. The node's RPC thread pool (`-rpcthreads`) is the shared resource with wallet operations.
- Recommendation: in the subscriber, (a) dedup on the 74-byte frame (a bounded LRU keyed by `sha256(frame)`), (b) a per-`seq` token bucket sized to the attestation cadence (e.g. a few frames per `every_blocks` interval, since a legitimate attestor emits one frame per height), (c) drop frames whose `citedHeight` is outside `[tip − window, tip]` using the last `yed_getinfo` height before calling the node, (d) consider verifying the signature locally against the pubkey from `yed_listattestors` before the RPC (the agent would then "hold" only public keys, which does not conflict with the no-key rule). Node auditor: confirm `yed_addattestation` has its own per-seq cap and that a failing signature is cheap.

##### D-6 [Severity: Low] `[subscribe] endpoints` accept `http://` although every document calls them HTTPS endpoints
- Where: ycash-dd/contrib/yellowback/attest/src/config.rs:233-236; docs: attest/README.md:9, doc/yellowback-attestor.md:26-29, attest.toml.sample:94; ycash6 identical
- Status: CONFIRMED
- Applies to: both
- What: `if !(e.starts_with("https://") || e.starts_with("http://"))` — plaintext endpoints pass validation. Integrity is covered by the node's signature check, so the exposure is availability/metadata only (an on-path attacker can substitute stale-but-valid frames or garbage), but the documented contract is HTTPS-only.
- Recommendation: require `https://` (allow `http://` only for `127.0.0.1`/regtest), and cap the endpoint body size (same `r.bytes()` pattern as D-3, subscribe.rs:179).

##### D-7 [Severity: Low] RPC credential handling: plaintext password in TOML with no permission check or guidance, Basic auth over `http://` to any host, cookie file permissions unchecked
- Where: ycash-dd/contrib/yellowback/attest/src/config.rs:166-172 (`rpc_url` only checked for scheme), rpc.rs:75-86 (cookie re-read per call, no mode check); yellowback_price.py:61-83; pool/yellowback-quote.toml.sample:9-15 (ships `rpc_user`/`rpc_password = "change-me"` as the uncommented default, cookie commented out); packaging/*.service:20 (`ReadOnlyPaths=/etc/yellowback`, nothing about mode); ycash6 identical
- Status: CONFIRMED
- Applies to: both
- What: nothing stops `rpc_url = "http://10.0.0.5:8832"` with `rpc_user/rpc_password`, which sends the node's RPC credentials in cleartext Basic auth over the LAN (these credentials can `yed_signattestation` with the attestor hot key, `yed_setquote`, and everything else in the wallet's RPC). The sample configs and the three READMEs never say to `chmod 600` the TOML, and the pool sample's default branch is the password one. Neither client warns when the cookie or config file is group/world-readable. (Credentials are never logged: both clients strip `user:pass@` from the URL before it can appear in an error string — checked rpc.rs:57-62, yellowback_price.py:75-78.)
- Recommendation: refuse (or loudly warn on) `http://` with a non-loopback host; prefer `rpc_cookie` as the uncommented default in both samples; document `chmod 600`; optionally warn when the config/cookie file mode has group/other bits.

##### D-8 [Severity: Low] iroh `secret_key_file` is created world-readable for an instant, then chmod'ed; parent-dir creation errors are swallowed
- Where: ycash-dd/contrib/yellowback/attest/src/transport/iroh.rs:53-66; ycash6 identical
- Status: CONFIRMED
- Applies to: both
- What: `std::fs::write(path, hex)` creates the file with the umask default (typically 0644) and `set_permissions(0o600)` follows, with `let _ =` on the result. The key is only the transport identity (endpoint id), not a signing key, so the impact is impersonation of this agent's endpoint id in the swarm (peers list it as a bootstrap peer) — not price integrity.
- Evidence:
  ```rust
  std::fs::write(path, hex::encode(key.to_bytes()))...?;
  #[cfg(unix)] { let _ = std::fs::set_permissions(path, Permissions::from_mode(0o600)); }
  ```
- Recommendation: `OpenOptions::new().write(true).create_new(true).mode(0o600)`; surface the `create_dir_all` error.

##### D-9 [Severity: Info] Default transport relays are iroh's public (n0) relays; the attestor's IP and endpoint id are visible to that operator
- Where: ycash-dd/contrib/yellowback/attest/src/transport/iroh.rs:72-75 (`RelayMode::Default`), :103 (`presets::N0`); attest.toml.sample:85
- Status: CONFIRMED
- Applies to: both
- What: with `relays = []` (the sample's default) the swarm bootstraps through n0's relay infrastructure. Content is signed and public, so the relay cannot forge or alter attestations; it can observe which IPs attest, delay, or partition the swarm (`relays = ["none"]` and self-hosted relays are supported). Worth one sentence in `doc/yellowback-attestor.md`'s "What you are NOT asked to do" list, which currently reads as if nothing third-party is involved.
- Recommendation: document; consider recommending a Ycash-operated relay list for mainnet.

##### D-10 [Severity: Info] Twin divergence: ycash6's devnet carries a cleanup fix absent from ycash-dd; everything else in `contrib/yellowback` is byte-identical
- Where: ycash6/contrib/yellowback/devnet/yellowback-devnet:673 (`kill_nodes(state["dir"], grace=10)` in the start-failure path, commit d1d1ac9e5) vs ycash-dd/contrib/yellowback/devnet/yellowback-devnet:669-672 (absent); the only other differences are the `ZCASHD`/`BITCOIND` environment name (:385-388, :705-707) and `ycash6`/`ycash-dd` wording in READMEs and scenario docs
- Status: CONFIRMED (`diff -rq`, then `diff -u` of the five differing files)
- Applies to: ycash-dd (missing the fix)
- What: on ycash6, when a node fails to start, every node started before it is killed; on ycash-dd they are left running (the next `up` then needs `--force`). Operational only, but the workspace rule is that shared fixes land on both lines.
- Recommendation: port the one line to ycash-dd.

##### D-11 [Severity: Info] `--mock-price` has no network guard
- Where: ycash-dd/contrib/yellowback/attest/src/main.rs:43-47, attest.rs:88-89, 283-285 (`network` is known before the loop but not consulted); yellowback-quote:270-271; doc/yellowback-attestor.md:39-41 ("`--mock-price` exists for regtest and demos only"); ycash6 identical
- Status: CONFIRMED
- Applies to: both
- What: on `network == "main"` the attestor will sign and publish whatever number is in the file, and the quote agent will push it with `yed_setquote`. An attestor can already sign any price with its own key, so this is not a new capability — but it is the one-keystroke way to become a pinned/ignored attestor (PIN-2) or an outlier pool, and the doc promises it is for regtest only.
- Recommendation: refuse `--mock-price` when `yed_getinfo.network == "main"` unless an explicit `--allow-mainnet-mock` is given.

##### D-12 [Severity: Info] Completeness and CI supply-chain notes
- Where: ycash-dd/contrib/yellowback/pool/README.md:58, :90-112 (five `TODO (survey)` items: whether the Perl/yolo/hosted stacks honour `coinbaseaux.flags`, refresh templates per block, rewrite the coinbase — "every item marked TODO is unverified against a live pool"); ycash-dd/.github/workflows/yellowback-tests.yml:186-196 (chain-viz built from a moving `main` ref without `--locked`, by the workflow's own admission; yolo is pinned to `YOLO_COMMIT` and `--locked`); workspace `requirements.txt` (`>=` ranges, used by the devnet/test framework, not by the quote tool, which is stdlib-only)
- Status: CONFIRMED
- Applies to: ycash-dd (CI); both (pool README)
- What: the pool-integration survey the mining doc leans on is still marked unverified; the CI's chain-viz step is the only unpinned, unlocked build in the workflow (test-only dependency, not shipped). No stubs, `TODO`, `unimplemented!`, skipped or assert-nothing tests were found in the agent crate, the Python tools or the devnet scripts.
- Recommendation: pin `CHAINVIZ_REF` to a commit and build `--locked` like yolo; resolve or date the pool README TODOs before the mining doc is handed to pool operators.

#### Checked and found sound

- Key material: the agent never holds, derives or logs a signing key; signing is `yed_signattestation` and the only key file is iroh's transport identity (attest/src/attest.rs, main.rs, transport/iroh.rs). Credentials are stripped from URLs before any error text (rpc.rs:55-62, yellowback_price.py:74-78); `tracing` never prints the auth header.
- Replay/cross-chain: `AttestMessage` includes the cited block hash (ycash-dd/src/yellowback/attest.cpp:38-45), so an attestation cannot be replayed onto another chain or height; the topic name also carries the network (transport/mod.rs:22-24). `topic_override` cannot cross-register a key because the subscriber's node verifies against its own `Attestors` table.
- Price→integer: `py_round` is round-half-even with saturating `as i64`; the `u32` range check before signing (attest.rs:229-232) and the node's `attest-range` make an out-of-range price unsignable; Python `int(round())` plus the node's `PRICE_MIN..PRICE_MAX` for `yed_setquote`.
- Outlier/median logic: per-source 15-minute VWAP/TWAP → median → drop >10 % from median → re-median; fail closed below `min_sources` (3) and `min_venues` (2); a single bad venue within 10 % can move the result only to its honest neighbour, outside 10 % it is dropped (price.rs:1086-1115, yellowback_price.py:670-688). BTC-quoted pairs need `min_btc_sources` live references or are refused (`btcref`), never guessed.
- Config validation: `deny_unknown_fields` on every TOML table, scheme check on `rpc_url`, cookie/user exclusivity, preset allowlist (`PRESET_KINDS`), `mask_bit` range, duplicate-name check (config.rs, price.rs:346-443; yellowback-quote:80-110, yellowback_price.py:316-382). Paths with unbalanced brackets are refused; `parse_selector` slicing is safe for every segment `split_path` can produce.
- TLS: rustls with the `ring` provider installed once (tls.rs); reqwest built with `rustls-no-provider` + `json` only; no `danger_accept_invalid_certs`/`invalid_hostnames` anywhere; every preset URL is `https://`; Python `urllib` verifies certificates by default.
- Panics on network data: apart from D-1 the only `unwrap`/`expect` calls on runtime data are in `#[cfg(test)]` modules; `serde_json::from_slice` errors are mapped to `ShapeError`; `Attestation::decode` length-checks before slicing (framing.rs:43-55).
- Subscriber fail-closed: `known_seqs` is empty until `yed_listattestors` answers, so nothing is forwarded before the registered set is known (subscribe.rs:55-69, 141-147).
- Supply chain: `Cargo.toml` pins every dependency with `=`; `Cargo.lock` committed (392 packages), no `git`/`path` sources; `rust-toolchain.toml` pins 1.91.0 with clippy/rustfmt; `.cargo/config.toml` only re-points crates.io to the sparse crates.io index; CI runs `cargo build/test/clippy --locked` and asserts no `iroh`/agent crate in the node's `Cargo.lock` or `depends/packages` (yellowback-tests.yml:424-472); `ycash-dd/Cargo.lock` and `ycash6/Cargo.lock` contain no `yellowback`/`attest`/`iroh` entries. The quote tool and `yellowback_price.py` are stdlib-only (Python ≥ 3.11 for `tomllib`). No `.pyc`/`__pycache__` is tracked (`*.pyc` in .gitignore).
- Packaging: both systemd units run as `User=ycash` with `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome=read-only`, `ReadOnlyPaths=/etc/yellowback`; launchd plists are per-user LaunchAgents; `Restart=always` is appropriate for an agent whose only non-zero exit is bad config.
- Shell safety: `check-coinbase`, `monitor-quote.sh`, `yellowback-devnet`, `stratum-perl-check`, `lwd-rawmint` build argv lists (`subprocess.run/Popen/check_output`), never `shell=True`/`os.system`; `monitor-quote.sh` quotes `"$CLI" "$@"`. Devnet RPC credentials are the regtest test framework's (`rpcuser💻N`/`rpcpass🔑N`, util.py:186), nodes bind loopback with the framework's `rpcallowip`; `stratum-perl-check` uses `u`/`p` with `rpcallowip=127.0.0.1` on regtest; `up` refuses to `rmtree` a non-empty directory without `--force` and never touches a dir with live nodes.
- `attest/calibrate/*.py`: offline CSV analysis plus a logger built on `yellowback_price`; no subprocess, eval or extra network surface.
- Docs vs code: `doc/yellowback-attestor.md`, `yellowback-mining.md`, `yellowback-devnet.md` describe the implemented commands, exit codes, L5 behaviour, equivocation guard and transport options accurately; the devnet doc's "mock price file is in dollars" gotcha matches `read_mock`.

#### Not covered / needs a different auditor

- Node side of every RPC the agents call: `yed_signattestation` equivocation guard and `attest-signed.dat` fsync, `yed_addattestation` per-seq/per-call bounds and the cost of a failing signature (D-5's impact depends on it), `yed_setquote` range/staleness, RPC thread-pool exhaustion.
- iroh/iroh-gossip internals (QUIC, relay auth, membership gossip limits) — taken as a dependency; only the agent's use of them was read.
- The functional tests that drive the agents (`qa/rpc-tests/yellowback_attest_agent.py`, `yellowback_quote.py`, `yellowback_devnet_roles.py`) and the test framework builders `lwd-rawmint` imports.
- yolo (pool) and chain-viz repositories themselves; only the ycash-dd workflow steps that build them were read.
- Behaviour of the devnet on a multi-user host (`pgrep -f`/`pkill -f` with unescaped directory and port patterns, yellowback-devnet:309, :1455) — local, regtest-only tooling; noted, not pursued.

---

### lightwalletd-dd — audit report

#### Summary

Covered the whole fork delta (`git -C lightwalletd-dd diff lightwalletd-legacy...HEAD`, 25 files): the
19-method `YellowbackStreamer` (`frontend/yellowback.go`), the allow-list proxy (`common/yellowback.go`),
the YED address mapping spliced into the baseline taddr paths (`frontend/yellowback_addr.go`,
`frontend/service.go`), the per-peer token bucket (`frontend/yellowback_ratelimit.go`), `cmd/root.go`,
the proto and generated-code gate, the three scripts, the fork's CI workflow and the node nightly step
that drives it, the docs, and both test suites. `go build -mod=vendor ./...` and `go vet` are clean
(go 1.27.1). The design is sound: a strictly read-only, allow-listed, typed proxy with no server-side
state, JSON-escaped parameters (no RPC injection), bounded request sizes on the YED methods, and a
clean UNIMPLEMENTED answer from a stock server. Two real hardening defects were found, both in
the delta: (E-1) the YED address mapping runs an O(n²) base58 decode on an unbounded client string
*before* the baseline's length-bounding regex, giving any unauthenticated client a cheap CPU-DoS on
three pre-existing CompactTxStreamer methods (a regression against the baseline); and (E-2) the
rate limiter keys on a client-supplied `x-real-ip` gRPC header that nothing in this tree
authenticates, so the limiter is bypassable and its map is attacker-growable. The rest is Medium/Low
hardening (unlimited node-work methods, no node-call timeouts, floating CI toolchains) and Info.

#### Findings

##### E-1 [Severity: High] Quadratic base58 decode on unbounded input before the length check — CPU DoS on GetTaddressTxids / GetTaddressBalance / GetAddressUtxos (regression vs baseline)
- Where: lightwalletd-dd/frontend/service.go:56-63 (`taddrOf`), :89 (`GetTaddressTxids`), :347-349 (`getTaddressBalanceZcashdRpc`), :530-532 (`getAddressUtxos`); lightwalletd-dd/frontend/yellowback_addr.go:36-40 (`yedToTransparent`); vendor/github.com/btcsuite/btcutil/base58/base58.go:17-32
- Status: CONFIRMED (traced and measured)
- Applies to: lightwalletd-dd
- What: With `--yellowback` on, every address the three baseline taddr RPCs receive is first passed to `yedToTransparent`, which calls `base58.Decode(addr)` on the raw string and only *then* checks the decoded length. btcutil's `Decode` is a big-integer loop (`j.Mul(j, bigRadix)`, `answer.Add`) whose cost grows quadratically with input length. The baseline protected these paths with `\As[a-zA-Z0-9]{34}\z` (service.go:67), an O(n) regex that rejects any 4 MB string in microseconds; the fork now runs the decode before that regex. gRPC's default receive limit in this tree is 4 MB (`grpc.NewServer` at cmd/root.go:135,162 sets no `MaxRecvMsgSize`), and `AddressList`/`GetAddressUtxosArg` carry *repeated* strings.
- Evidence:
  ```go
  // service.go:56-63
  func taddrOf(addr string) string {
      if YellowbackAddresses {
          if t, ok := yedToTransparent(addr); ok { return t }
      }
      return addr
  }
  // yellowback_addr.go:36-38
  func yedToTransparent(addr string) (string, bool) {
      raw := base58.Decode(addr)
      if len(raw) != 2+20+4 { // version(2) + hash160(20) + checksum(4)
  ```
  Measured with a throwaway test against the vendored package (file created and deleted again; tree left clean): 20 000 chars 15.6 ms, 40 000 chars 60.2 ms, 80 000 chars 242 ms — ×4 per doubling. Extrapolated, one 4 MB `Address` costs on the order of 10 minutes of a core; one `AddressList` message may carry many.
- Scenario: Any Internet client sends `GetTaddressBalance{addresses: ["zzzz…" × 4 MB]}` repeatedly (no auth, no rate limit on these methods). Each request pins a core for minutes; a handful of concurrent streams exhaust the host and stall the compact-block service for every mobile wallet. The limiter in E-2 does not cover these methods anyway.
- Recommendation: Reject before decoding: in `taddrOf` (or at the top of `yedToTransparent`) return early unless `len(addr) == 35` (a 26-byte base58check payload is always 34–35 chars) and `addr[0] == 'y'`; equivalently run a cheap regex `\A[a-km-zA-HJ-NP-Z1-9]{34,35}\z` first. Add an offline test feeding a 1 MB string to `taddrOf` with a time bound. Consider also setting `grpc.MaxRecvMsgSize` for the server, which the baseline never did.

##### E-2 [Severity: Medium] Rate limiter trusts a client-supplied `x-real-ip` header — bypass and unbounded limiter map
- Where: lightwalletd-dd/frontend/yellowback_ratelimit.go:82-97 (`peerKey`), :51-80 (`allow`), docs/yellowback.md:42
- Status: CONFIRMED
- Applies to: lightwalletd-dd
- What: `peerKey` prefers gRPC incoming metadata `x-real-ip` over the connection address. gRPC metadata is set by the client; nothing in this server strips or validates it, and there is no "trusted proxy" setting. The comment says it "mirrors the baseline's peer identification (service.go peerIPFromContext)", but no such function, and no use of `metadata` or `peer`, exists anywhere in the fork outside this file (`grep -rn x-real-ip --include='*.go'` → only yellowback_ratelimit.go and its test). The fork's own test (`yellowback_test.go:591`) demonstrates the bypass by minting "another peer" with a forged header. Each distinct key allocates a `tokenBucket`; the sweep runs at most every 10 minutes (`yedRateIdleSweep`) and only inside `allow`, so an attacker rotating the header grows the map for 10 minutes before any entry is freed.
- Evidence:
  ```go
  func peerKey(ctx context.Context) string {
      if md, ok := metadata.FromIncomingContext(ctx); ok {
          if v := md.Get("x-real-ip"); len(v) > 0 && v[0] != "" {
              return v[0]
          }
      }
  ```
- Scenario: A client calling `BuildBundle`/`EstimateCollateral`/`ValidateRawTransaction`/`GetAddressTokens` sets a fresh `x-real-ip` per call: the limiter never refuses, every call reaches the node (see E-3), and the map grows at the request rate (≈100 B per entry: 10 k req/s for 10 min ≈ 6 M entries, hundreds of MB). Behind a real nginx that *does* set `x-real-ip`, the header value is also only as trustworthy as nginx's own config.
- Recommendation: Use the connection address by default; honour `x-real-ip`/`x-forwarded-for` only when a new flag (`--trusted-proxy-cidr`) matches the peer address. Cap the map (refuse or evict when `len(peers)` exceeds a bound) and sweep on size as well as time. Fix the misleading comment. Note the baseline's `GetBlockRange` latency cache also has no per-IP keying in this lineage, so there is no precedent to mirror.

##### E-3 [Severity: Medium] Fifteen of nineteen methods are unauthenticated, unlimited, synchronous node calls — node RPC-thread exhaustion
- Where: lightwalletd-dd/frontend/yellowback.go (every handler without `y.limited`), yellowback_ratelimit.go:5-10; node side ycash-dd/src/rpc/yellowback.cpp:822-824 (`yed_getprice`), :1151-1163 (`yed_listvaults`), :1803-1830 (`yed_getselection`), :936-945 (payee window scan)
- Status: CONFIRMED (code paths traced; not load-tested)
- Applies to: lightwalletd-dd (impact on the ycash-dd node it fronts)
- What: Only `ValidateRawTransaction`, `EstimateCollateral`, `BuildBundle` and `GetAddressTokens` call `limited`. `GetPrice` takes `cs_main`, `mempool.cs` and `cs_yellowback` on the node per call; `ListVaults` iterates the entire `V` prefix of the index on every call regardless of `skip` (and the node has no upper bound on `count` — the server's 1000 is the only cap); `GetSelection` does the same weight computation `BuildBundle` is limited for; `GetFeePayee` scans a `payeeWindow` of tags; `GetTxInfo`/`GetVault`/`GetNotice` are index reads. Each gRPC request is one blocking `RawRequest` to the node, which serves RPC on a small fixed thread pool, shared with the server's own `getblock`/`sendrawtransaction` traffic.
- Evidence:
  ```go
  // yellowback.go:95-102 — no limiter, no bound on how often this hits cs_main
  func (y *YellowbackStreamer) GetPrice(ctx context.Context, in *walletrpc.HeightFilter) (*walletrpc.YedPrice, error) {
      ...
      return out, y.call(out, "yed_getprice", params...)
  ```
  ```cpp
  // ycash-dd/src/rpc/yellowback.cpp:1151-1163 — whole-table walk per call
  index.View().Iterate("V", [&](const std::string& k, const std::string& raw) {
      ...
      if (seen++ < skip) return true;
  ```
- Scenario: A client floods `GetPrice`/`ListVaults{skip:N}`/`GetSelection` from many connections; the node's RPC threads are all busy on index/`cs_main` work, the server's block-cache ingest and `SendTransaction` time out, and every wallet behind the server loses service. No funds at risk; availability only.
- Recommendation: Gate every Yellowback method with the limiter (cheap ones with a lighter weight), add a server-wide concurrency semaphore on `CallYed` (e.g. 8 in flight, others `RESOURCE_EXHAUSTED`), and consider a short TTL cache (one block) for the per-tip answers (`GetYellowbackInfo`, `GetPrice{0}`, `GetStats`, `GetActivation`, `ListClaimable`, `GetAttestations`) since the proxy serves identical bytes to every client between blocks.

##### E-4 [Severity: Low] No context propagation or timeout on node calls; streamed results are fully buffered
- Where: lightwalletd-dd/frontend/yellowback.go:54-64 (`call`), :182-191, :196-205, :296-305, :314-323, :349-358; common/yellowback.go:149-165 (`CallYed`)
- Status: CONFIRMED
- Applies to: lightwalletd-dd (pattern shared with the baseline's `RawRequest` use)
- What: `ctx` is accepted by every unary handler and `stream.Context()` is available to streaming ones, but neither is passed to `CallYed`; `common.RawRequest` (btcd rpcclient) has no deadline. A cancelled or departed client does not cancel the node call, so under E-3 the backlog cannot drain early. Streaming handlers unmarshal the whole JSON array into memory before the first `Send`, so a large `yed_listvaults`/`yed_listtokens` answer is held twice (raw JSON + decoded). No goroutines are spawned, so there is no goroutine leak.
- Evidence: `raw, err := RawRequest(method, params)` — no ctx parameter exists on the function variable (common/common.go:56).
- Recommendation: Wrap each call in a bounded timeout (e.g. 10 s) via a goroutine + `select` on `ctx.Done()`, or move the node client to `rpcclient`'s async API; combine with the E-3 semaphore.

##### E-5 [Severity: Low] `ListVaults.status` is forwarded unvalidated and unbounded; `count=0,skip>0` silently asks for 1000 rows
- Where: lightwalletd-dd/frontend/yellowback.go:164-181
- Status: CONFIRMED
- Applies to: lightwalletd-dd
- What: `in.Status` is JSON-escaped by `common.JSONString` (so there is no RPC injection) but has no length cap or enum check, so a multi-megabyte string is serialised and sent to the node, which parses it before rejecting (`yellowback.cpp:1142`). When `count==0` but `skip!=0` the server substitutes `maxListCount` (1000), ten times the node's own default of 100.
- Evidence:
  ```go
  if in.Status != "" || in.Count != 0 || in.Skip != 0 {
      params = append(params, common.JSONString(in.Status))
  }
  if in.Count != 0 || in.Skip != 0 {
      count := int64(in.Count)
      if count == 0 { count = maxListCount }
  ```
- Recommendation: Validate `status ∈ {"", ACTIVE, VOID, CLOSED, CLAIMED}` at the edge (the offline test's "the node was called for malformed input" assertion would then cover it) and default `count` to 100 to match the node.

##### E-6 [Severity: Low] CI supply chain: floating toolchains, unpinned action tags, unverified Go tarball and branch-name clone in the node nightly
- Where: lightwalletd-dd/.github/workflows/yellowback-tests.yml:19-22,39-46; ycash-dd/.github/workflows/yellowback-tests.yml:658-660
- Status: CONFIRMED
- Applies to: lightwalletd-dd (and the ycash-dd nightly step that drives it)
- What: The fork's workflow uses `go-version: stable` (floating), `actions/checkout@v4`/`setup-go@v5` by tag not SHA, and `apt-get install protobuf-compiler` unpinned — the generated-code gate therefore depends on whatever protoc Ubuntu ships that day (the mask in `check-generated.sh` hides descriptor/version drift, so this is mostly benign). The node's nightly clones `boyfromcave/lightwalletd` by *branch name* and installs Go with `curl -sSL …go1.24.7… | tar -xz` with no checksum. The workflow triggers are `push`/`pull_request`/`workflow_dispatch` — **no** `pull_request_target`, no secrets referenced, no `curl | sh`: the dangerous patterns are absent.
- Evidence:
  ```yaml
  git clone --quiet --branch feature/yellowback-price-attest https://github.com/boyfromcave/lightwalletd.git "$RUNNER_TEMP/lightwalletd-dd"
  curl -sSL https://go.dev/dl/go1.24.7.linux-amd64.tar.gz | tar -C "$RUNNER_TEMP" -xz
  ```
- Recommendation: Pin `go-version` to the version `docs/yellowback.md` records, pin actions by SHA, verify the Go tarball against the published SHA-256 (or use `actions/setup-go` in that job), and clone the lightwalletd fork at a commit recorded in the node's `repos.yaml`-style pin.

##### E-7 [Severity: Info] Protobuf: separate service in the shared `cash.z.wallet.sdk.rpc` package — no collisions today, name-space risk against future upstream
- Where: lightwalletd-dd/walletrpc/yellowback.proto:14-17, :174-194; scripts/check-generated.sh
- Status: CONFIRMED (no collision at the pin) / PLAUSIBLE (future)
- Applies to: lightwalletd-dd, YEW
- What: `yellowback.proto` imports `service.proto` (for `Empty`, `RawTransaction`) and declares 50 new messages in the *same* proto package. None of the names (`HeightFilter`, `Yed*`, `Yellowback*`) exist in this lineage's `service.proto`/`compact_formats.proto`/`darkside.proto`, and `service.proto` is byte-untouched (docs/review.md:24 claims 0 lines; the diff confirms). Because it is a distinct `service YellowbackStreamer`, there is no field-number interaction with `CompactTxStreamer`; a YEW client against a stock server receives `UNIMPLEMENTED` (asserted by `TestDevnetBaselineHasNoYellowback`). `check-generated.sh` pins protoc-gen-go v1.26.0 / protoc-gen-go-grpc v1.1.0 and the checked-in `.pb.go` builds. Residual risk: a later upstream zcash/lightwalletd rebase that adds a message named e.g. `HeightFilter` to the same package would fail at protoc time — loud, not silent.
- Recommendation: None required; optionally move the YED messages to their own proto package (`cash.z.wallet.sdk.rpc.yellowback`) before any client ships, since renaming later breaks the wire-compatible Go/Dart types.

##### E-8 [Severity: Info] TLS and node credentials: unchanged from baseline, correctly documented
- Where: lightwalletd-dd/docs/yellowback.md:107-110, :146-150; cmd/root.go:191-203; ycash-dd/contrib/yellowback/devnet/yellowback-devnet:448-453
- Status: CONFIRMED
- Applies to: lightwalletd-dd
- What: The fork adds no TLS or credential code path. Plaintext gRPC requires the baseline's explicit `--no-tls-very-insecure`; the runbook says "TLS as the README describes, or nginx in front". Node RPC credentials come from `ycash.conf` (`--zcash-conf-path`) or the four `--rpc*` flags; the devnet passes `--rpcpassword` on the command line (visible in `ps`), acceptable for regtest only and the docs say so ("Never mainnet"). `testtools/lwdinfo` dials `grpc.WithInsecure()` by design (a devnet probe). The service is registered on the same listener as `CompactTxStreamer`, so whatever TLS the operator configures covers it (plan §9 Q4).
- Recommendation: One sentence in the runbook that `--rpcpassword` on the command line is for the devnet only would close the gap.

##### E-9 [Severity: Info] Consistency across reorgs / with the compact-block stream: no server cache, node index tip may lag; documented as a trust statement
- Where: lightwalletd-dd/frontend/yellowback.go:5-9; docs/review.md:98-104; ycash-dd/src/rpc/yellowback.cpp:822-826 (`IndexHeight`, `EnsureHealthy`)
- Status: CONFIRMED
- Applies to: lightwalletd-dd
- What: The server holds no Yellowback state, so there is nothing to go stale on a reorg; each answer is the node index's view at call time. That view can lag the chain tip the block cache streams (the index is rebuilt asynchronously; `yed_getinfo` exposes both `height` and `chainHeight`), and an unhealthy index yields `FAILED_PRECONDITION` rather than stale data (fail-closed). A client that pairs `GetTxInfo` verdicts with compact blocks must tolerate `height` < `chainHeight`; `GetYellowbackInfo` gives it the numbers to do so. The relay-can-lie caveat is stated in docs/review.md.
- Recommendation: Add `height`/`chainHeight` lag handling to the YEW plan's client contract if it is not already there (outside this audit).

##### E-10 [Severity: Info] Tests: substantive, with two gaps
- Where: lightwalletd-dd/frontend/yellowback_test.go, yellowback_devnet_test.go, .github/workflows/yellowback-tests.yml:31-36
- Status: CONFIRMED
- Applies to: lightwalletd-dd
- What: The offline suite compares every method's decoded message field-by-field with the node contract's example values (lines 147-243), asserts param encodings, error-code mapping, that malformed input never reaches the stub node (`len(node.calls)==0`), that every contract `yed_*` is in exactly one of `YedMethods`/`NotOffered`, the probe matrix, address vectors, and the limiter. The devnet suite asserts byte-equality of `GetLightdInfo` and every `CompactBlock` between fork and baseline binaries (proto.Marshal + bytes.Equal, lines 209-268), UNIMPLEMENTED on the baseline, `GetAddressTokens == yed_listunspent`, and an end-to-end raw mint. Gaps: (a) no test feeds a long/garbage address through `taddrOf` (would have caught E-1); (b) the baseline `frontend` tests are excluded by name (F-R1), so the three edited taddr paths in `service.go` run under no regression test other than `TestTaddrOfMapsYedAddresses`; (c) `TestDevnetRawMintThroughServer` skips when `LWD_RAWMINT` is unset and the armed carrier path (plan §9 Q6) has never run on a devnet.
- Recommendation: Add (a); consider restoring a minimal `GetTaddressTxids` regression test with Ycash `s…` fixtures.

##### E-11 [Severity: Info] Completeness vs the plan
- Where: docs/plans/yellowback-lightwalletd-plan.md §7 (all boxes checked), §9 Q2 and Q6; plan §7 L1 lines 619,623 reference `cmd/server/main.go` and `cmd/lwdinfo`, which in this tree are `cmd/root.go` and `testtools/lwdinfo`
- Status: CONFIRMED
- Applies to: lightwalletd-dd
- What: Every phase item (L0–L3, N1, R0) is implemented and present in the tree; the 19 proto methods match §4.1 and the allow-list. Still open by the plan's own account: Q2 (`yed_listtokens` scan cost on a mainnet-sized index unmeasured — relevant to E-3), Q6 (armed carrier path untested on a devnet), and the node nightly step is marked "Unverified until the next scheduled run". The plan's L1 checklist paths are stale after the R0 re-port (cosmetic).
- Recommendation: Update the stale paths; keep Q2/Q6 open in the plan until run.

#### Checked and found sound
- RPC injection: every client string reaches the node through `common.JSONString` (`json.Marshal`) or `json.Marshal` of the address slice; numbers through `strconv.FormatInt`; no string splicing (common/yellowback.go:170-178, frontend/yellowback.go:341-345).
- Allow-list is the only path: `CallYed` refuses anything not in `YedMethods` with INTERNAL; no wallet/miner/attestor RPC (`yed_mint`, `yed_setquote`, `yed_addattestation`, `yed_signattestation`…) is reachable; `TestAllowListIsTheOnlyPath` and `TestAllowListCoversContract` enforce it (common/yellowback.go:36-91,149-152).
- Nothing beyond read-only data is exposed: no relay of transactions or bundles by the new service; `ValidateRawTransaction` is a dry run (node `yed_validaterawtransaction`), broadcasting stays on the baseline `SendTransaction`; `BuildBundle` returns bytes the node assembles from its own pool and takes only a ≤36-byte hex selector + height (frontend/yellowback.go:258-282).
- Input bounds on the YED methods: txid regex `^[0-9a-fA-F]{64}$`, hex regex `^([0-9a-fA-F]{2})*$` with explicit length caps (raw tx ≤ 200 kB bytes, payload ≤ 520 B, selector ≤ 36 B), addresses 1..100 × ≤ 64 chars, `count` ≤ 1000; all regexes are linear (Go RE2) — no ReDoS (frontend/yellowback.go:28-37,70-82).
- Integer handling: `uint32` heights/`uint64` cents cast to `int64` cannot overflow in a dangerous way — values ≥ 2^63 become negative and the node rejects them (`cents must be between`, `height must be between`, `RefHeightArg`), `collateralZat` is checked `≤ MAX_MONEY` node-side (ycash-dd/src/rpc/yellowback.cpp:1069,1523-1525,1763-1771).
- Node error mapping: JSON-RPC errors → FAILED_PRECONDITION with the node message verbatim (message, not stack); transport → UNAVAILABLE; contract mismatch → INTERNAL with a log line, never leaking the raw body (common/yellowback.go:149-165, frontend/yellowback.go:54-64).
- YED→transparent mapping correctness: version bytes 0x1FE4/0x2007/0x2002 match ycash-dd/src/yellowback/address.h:14-21; targets {0x1C,0x28}/{0x1C,0x95} match ref/ycash/src/chainparams.cpp:149,409,613; double-SHA256 checksum verified before mapping; a transparent or garbage address passes through unchanged into the baseline regex, which remains the last guard; off by default (`YellowbackAddresses` only set after a successful probe, cmd/root.go:272-283).
- Capability probe: the service registers only when the node lists the `yellowback` experimental feature *and* `yed_getinfo.rpcversion == 3`; otherwise one log line and the baseline surface (common/yellowback.go:108-142, cmd/root.go:272-283). Fail-closed.
- Baseline frozen files: `walletrpc/service.proto`, `compact_formats.proto`, `darkside.proto`, `parser/`, `common/cache.go` are unchanged in the delta (`git diff --stat`); `service.go` changes are the three `taddrOf` splices plus the flag variable; vendor/ unchanged (btcutil was already vendored as an indirect dependency, `lightwalletd-legacy:vendor/modules.txt:12-15`).
- No secrets in the delta; `scripts/*.sh` use `set -euo pipefail`, quote their variables, `mktemp -d` with a trap, and `git archive` the baseline rather than checking it out; `devnet-test.sh`'s `pkill -f` pattern is scoped to the baseline binary name and port.
- No goroutines spawned by the new code; the limiter's mutex is held only for map work; `now` is injectable for tests.
- `go build -mod=vendor ./...` and `go vet -mod=vendor ./cmd/... ./common/... ./frontend/... ./walletrpc/...` pass (go 1.27.1, this session). Working tree left clean (a throwaway timing test was created under `frontend/` for E-1 and removed; `git status --short` empty).

#### Not covered / needs a different auditor
- The node-side cost and locking of each `yed_*` RPC the proxy fans out to (`cs_main` in `yed_getprice`, the full-table iterate in `yed_listvaults`, `yed_listtokens` scan cost — plan Q2): node auditor (ycash-dd `src/rpc/yellowback.cpp`), and the same for the ycash6 twin.
- The baseline's own pre-existing issues (btcd rpcclient without deadlines, no `MaxRecvMsgSize`, the hanging `frontend` tests at F-R1) beyond where the delta crosses them.
- `ycash-dd/contrib/yellowback/devnet/yellowback-devnet` and `lwd-rawmint` (Python; drive this fork's regtest suite): devnet/tooling auditor.
- YEW's client-side handling of the index-lag and trust statement (E-9): YEW auditor.
- Load-testing E-3 against a real node (not run; the brief forbids running the devnet).

---

### yecwallet-dd — audit report

#### Summary
Covered the whole `yecwallet-legacy...feature/yellowback-price-attest` delta (70 commits, 48 files, +12,370): the datadir upgrade check (`nodedatacheck.*`, `ConnectionLoader::confirmNodeDataUpgrade`), the two-line node compatibility layer (`nodecompat.h`, `connection.cpp`, `zcashdrpc.cpp`, `mainwindow.cpp` rescans/imports), the Yellowback tab (`yellowbacktab.cpp` 1,904 lines, `yellowbackcontroller.cpp`, `yellowbackmodels.cpp`, `yellowbackrpc.h`), settings, the subscriber launcher, `build.sh`, the CI workflow, and the three QTest suites plus `check-rpc-contract.py`. Read-only; nothing was built.

Verdict: the wallet is a thin JSON-RPC client of its own node, holds no key material, adds no outbound network endpoint, and every spending action goes validate → confirm dialog → one RPC with the amounts the dialog showed, which the offline tests assert. The security-relevant weaknesses are all local/hardening grade: the mint (and claim) confirmation shows a collateral figure the node is not bound to (no cap argument exists in `yed_mint`), the datadir marker is written before the upgrade succeeds, the comma-as-decimal locale trap in `parseDollars`, the subscriber TOML file carrying the RPC password with a brief world-readable window and no control-character escaping, a production env-var bypass of the upgrade dialog, and `nodedatacheck_test` not being run by CI. No Critical or High findings.

#### Findings

##### F-1 [Severity: Medium] Mint/claim confirmation shows an estimate the node is not bound to; no collateral cap is sent
- Where: yecwallet-dd/src/yellowbacktab.cpp:810-868 (doMint), yecwallet-dd/src/yellowbackcontroller.cpp:771-773 (mint), ycash-dd/src/rpc/yellowbackwallet.cpp:689-760 (yed_mint arguments), :412-427 (CompleteMint → BuildMint at the carrier's refHeight)
- Status: CONFIRMED
- Applies to: yecwallet-dd (node interface on both lines)
- What: `doMint` re-runs `yed_estimatecollateral`, puts `required` in the dialog ("Mint $X of YED against Y YEC"), then calls `yed_mint(cents, lockBlocks, from, "", false)`. The node sizes the collateral again in `PreflightMint` at *its* reference height when the call arrives, and the wallet passes nothing that bounds it; `yed_mint` has no max-collateral argument at all. A block arriving between the dialog and the click (or a price shock, which the devnet persona `shock=-70%` models) makes the vault lock materially more YEC than the user agreed to. The same holds for the claim dialog's "You receive: about N" computed from the `yed_listclaimable` row (`claimVault`, :1263-1283) and the redeem fee from `yed_getfeepayee`.
- Evidence:
```cpp
// yellowbackcontroller.cpp:771
void YellowbackController::mint(qint64 cents, int lockBlocks, const QString& from, OkFn ok, ErrFn err) {
    call(YellowbackRpc::MINT, json::array({cents, lockBlocks, from.toStdString(), "", false}), ok, err);
}
// yellowbackwallet.cpp:693  "yed_mint cents lockBlocks ( \"from\" \"bundleHex\" wait )"
```
- Scenario: user confirms a $1,000 mint at 251 YEC; the next block's reference price is 30 % lower; the node locks 359 YEC. The summary dialog afterwards prints the real `collateralZat` from `yed_gettxinfo` but does not compare it with what was confirmed, so the user may not notice. Not theft (collateral returns on redeem) but an unconsented lock-up of funds for the term, which on a class C term is months.
- Recommendation: node side, add an optional `maxCollateralZat` to `yed_mint` (refuse with a stable identifier when exceeded) and `maxBurnCents`/`minOutZat` to `yed_claim`; wallet side until then, pass the dialog's `required` through the `done` callback and show a prominent warning in `mintSummary` when `collateralZat` differs from it by more than, say, 1 %, and re-estimate if `ctl->height()` changed between dialog and click.

##### F-2 [Severity: Low] Datadir upgrade marker is written before the upgrade has happened
- Where: yecwallet-dd/src/connection.cpp:456-466 (confirmNodeDataUpgrade tail), yecwallet-dd/src/nodedatacheck.cpp:98-104 (Marked short-circuit)
- Status: CONFIRMED
- Applies to: yecwallet-dd
- What: After the user accepts, `writeMarker` runs immediately, then (for `Older`) `reindex=1` is appended and the node is started. `inspect` returns `Marked` whenever the marker names ≥ 6.20.0, before looking at `debug.log`. If the reindex is never completed (user quits during the hours-long mainnet reindex, node crashes, disk full), or the user later restores a v4.5.0 copy of `blocks/`, the directory is still in the old format but the wallet never warns again; the pre-existing fallback in `startEmbeddedZcashd` (:481-484) then silently appends `reindex=1` on the node's "-reindex" error.
- Evidence:
```cpp
    QString error;
    if (!NodeDataCheck::writeMarker(dirs.netDir, bundledText, &error))
        main->logger->write("Could not write the data directory marker: " + error);
    if (result.state == NodeDataCheck::State::Older)
        Settings::addToZcashConf(confLocation, "reindex=1");
    return true;
```
- Scenario: user accepts, quits at 20 % of the reindex, copies an old `blocks/` back from a backup to "undo", starts the wallet: no dialog, silent reindex, backup not re-offered.
- Recommendation: treat the marker as "accepted" only together with evidence: in `inspect`, if the marker is present but `debug.log`'s last loader is older than 6.20.0 (state would be `Older`), still warn (a shorter "the upgrade did not complete" variant), or write the marker from `Controller::setConnection` once the 6.20.0 node has answered `getinfo` (the same place `reindex=1` is removed).

##### F-3 [Severity: Low] `parseDollars` turns a comma-decimal entry into a 100× amount
- Where: yecwallet-dd/src/yellowbacktab.cpp:474-489
- Status: CONFIRMED
- Applies to: yecwallet-dd
- What: Commas are stripped before matching, so "12,50" (every comma-decimal locale) parses as 1,250 dollars. The confirm dialog shows the real figure ("$1,250.00") and the balance check caps it at the confirmed YED, which is why this is Low rather than Medium; the mint path has the same parser.
- Evidence:
```cpp
    t.remove('$').remove(',').remove(' ');
    static const QRegularExpression re("^(\\d{1,9})(?:\\.(\\d{1,2}))?$");
```
- Scenario: a German-locale user with $2,000 YED types "12,50" to send, skims the dialog, sends $1,250. Irreversible transparent transfer.
- Recommendation: reject input whose last separator is a comma followed by exactly two digits unless it also contains a '.', or parse with `QLocale` and show the parsed amount next to the field live. Add "12,50" and "1,5" to `parsesDollars` (tests/yellowbacktab_test.cpp:545).

##### F-4 [Severity: Low] Subscriber config written with the RPC password: permission window and no control-character escaping
- Where: yecwallet-dd/src/yellowbacktab.cpp:1748-1778 (subscriberConfigToml), :1804-1816 (write then chmod)
- Status: CONFIRMED
- Applies to: yecwallet-dd
- What: (a) `yellowback-subscribe.toml` is created with the process umask (typically 0644 on a shared machine) and only then `setPermissions(ReadOwner|WriteOwner)`; the file holds `rpc_password` whenever no `.cookie` is found, which is the default since the wallet-written `ycash.conf` uses `rpcuser`/`rpcpassword`. (b) The TOML quoting escapes only `\` and `"`; a newline or other control character in the transport path/relay/peer fields (pasted into the `QLineEdit`, which does not strip them) breaks the file or injects a `[node]` key. The values are the user's own settings, so this is integrity of a local file, not an attack surface.
- Evidence:
```cpp
    auto q = [](const QString& v) -> QString { QString e = v; e.replace("\\", "\\\\").replace("\"", "\\\""); return "\"" % e % "\""; };
    ...
    f.write(toml.toUtf8());
    f.close();
    f.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);   // it may carry the RPC password
```
- Scenario: multi-user host; another local user reads the RPC password during the write window (or from a previous run if `setPermissions` failed and the error was ignored), then issues `yed_send`/`z_sendmany` to the node.
- Recommendation: use `QSaveFile`/create with 0600 before writing (open with `QIODevice::NewOnly` after `QFile::remove`, then `setPermissions`, then write), check the `setPermissions` return, and escape `\n`, `\r`, `\t` and `\u0000-\u001f` in `q()` (or refuse such input in `saveSettings`). Prefer the cookie file: `cookiePathFor` uses the conf's directory, not `datadir=` (connection.cpp:781), so a conf with `datadir=` never finds the cookie.

##### F-5 [Severity: Low] Production env var silently answers the one-way upgrade dialog
- Where: yecwallet-dd/src/connection.cpp:401-408
- Status: CONFIRMED
- Applies to: yecwallet-dd
- What: `YECWALLET_UPGRADE_ANSWER=continue` in the environment skips the dialog and the backup in release builds. Anything able to set the wallet's environment could already do worse, so this is hardening only, but a launcher script, a shell profile or a copied devnet recipe that exports it defeats the owner's "warn before the one-way upgrade" decision.
- Evidence:
```cpp
    const QString hook = qEnvironmentVariable("YECWALLET_UPGRADE_ANSWER").toLower();
    const bool hooked = !hook.isEmpty();
    if (hooked) {
        answer = hook == "backup" ? Answer::Backup : hook == "continue" ? Answer::Continue : Answer::Quit;
```
- Recommendation: honour the hook only when `YECWALLET_TEST_ISOLATE` is also set (the existing test-isolation gate, main.cpp:196), or compile it out of release builds.

##### F-6 [Severity: Low] `nodedatacheck_test` exists but CI never builds or runs it
- Where: yecwallet-dd/.github/workflows/yecwallet-tests.yml:41-50, yecwallet-dd/CMakeLists.txt:334
- Status: CONFIRMED
- Applies to: yecwallet-dd
- What: CMake registers `yellowback_test nodecompat_test nodedatacheck_test`; the workflow builds `yecwallet yellowback_test nodecompat_test` and runs only those two. The 16-case suite that guards the upgrade warning (log parsing, marker, backup naming) is local-only; the ycash6 plan line 36 reports "ctest 3/3" from a developer machine.
- Evidence:
```yaml
      - name: Build the app and the QTest target
        run: ninja -C build yecwallet yellowback_test nodecompat_test
```
- Recommendation: add `nodedatacheck_test` to the build and a run step (or replace the two run steps with `ctest --test-dir build --output-on-failure`).

##### F-7 [Severity: Low] CI actions pinned by tag, not by commit SHA
- Where: yecwallet-dd/.github/workflows/yecwallet-tests.yml:21,31,51
- Status: CONFIRMED
- Applies to: yecwallet-dd
- What: `actions/checkout@v4`, `jurplel/install-qt-action@v4` (third party, downloads Qt from its own mirror), `actions/upload-artifact@v4`. No secrets are used and the trigger is plain `pull_request`, so the blast radius is a false-green or a poisoned test build, not a leak.
- Recommendation: pin to full SHAs with a version comment; the same rule the node repo's workflow should follow.

##### F-8 [Severity: Low] Attestor registration dialog parses tier/bond loosely
- Where: yecwallet-dd/src/yellowbacktab.cpp:1497-1517
- Status: CONFIRMED
- Applies to: yecwallet-dd
- What: `tier.trimmed().toInt()` ignores the `ok` flag, so "abc" is tier 0 (exchange APIs) silently; `bond` is parsed to `double` and sent as a JSON float (`registerAttestor(double ...)`, yellowbackcontroller.cpp:798). The confirm dialog prints the parsed values, which bounds the damage; the node enforces `bond-below-min`.
- Recommendation: use the `ok` flags for all three parses and send the bond as a decimal string (the node's `AmountFromValue` accepts strings) to avoid double rounding on 8-decimal amounts.

##### F-9 [Severity: Info] Pending two-step follow-up is heuristic (known, plan A5-b)
- Where: yecwallet-dd/src/yellowbackcontroller.cpp:831-911 (awaitPending)
- Status: CONFIRMED
- Applies to: yecwallet-dd; needs a node contract change
- What: After a `pending: true` reply the wallet polls `yed_listtransactions` and takes the first row of the type that is not in the baseline set and is above `refHeight`. Two concurrent actions of the same type (two mints, or a mint from another client on the same wallet) can be cross-attributed in the summary dialog. The plan records this (v3 plan line 63) and schedules `carrierTxid`/`mainTxid` on the rows for A6; it has not been done.
- Recommendation: finish the A6 contract item; until then match on `carrierTxid` when the row carries it and fall back to the heuristic otherwise.

##### F-10 [Severity: Info] Datadir check inspects the conf the wallet uses, not the conf the embedded node reads
- Where: yecwallet-dd/src/connection.cpp:386-389, yecwallet-dd/src/main.cpp:237, yecwallet-dd/src/connection.cpp:521-527
- Status: PLAUSIBLE (pre-existing baseline behaviour, not introduced by the delta)
- Applies to: yecwallet-dd
- What: `confirmNodeDataUpgrade` resolves `datadir=`/`testnet=`/`regtest=` from `Settings::getZcashdConfLocation()`, which `--conf PATH` overrides; the embedded `ycashd` is started with no arguments and so reads the default `~/.ycash/ycash.conf`. With `--conf` and no `--no-embedded`, the directory inspected (and the one that receives the marker, the backup and `reindex=1`) can differ from the one the node upgrades. The baseline already has this `--conf`/embedded mismatch; the new check inherits it.
- Recommendation: either start the embedded node with `-conf=<confLocation>` (a one-line change that also makes the existing `reindex=1`/`rescan=1` appends land where the node reads them) or skip the embedded start when `--conf` names a non-default file.

##### F-11 [Severity: Info] Two-line field differences are handled; one gap in the version read
- Where: yecwallet-dd/src/connection.cpp:607-629, yecwallet-dd/src/nodecompat.h:27-32
- Status: CONFIRMED
- Applies to: yecwallet-dd
- What: `nodeVersion` is set only on the path where `getrescaninfo` fails. A v4.5.0 node keeps `nodeVersion = 0` by design. A 6.20.0 node whose `getinfo` reply lacks a numeric `version` would also be 0 and be driven with v4.5.0 shapes; `getinfo.version` is always an integer on both lines (`clientversion.h`), so this is theoretical. The `yed_*` contract is version-checked separately (`rpcversion == 3`, yellowbackcontroller.cpp:162) and `docs/yellowback-rpc-contract.json` is one file for both lines; `check-rpc-contract.py` verifies the header against it. No `yed_*` field differs between the lines (`yellowbackwallet.cpp` is the same source in both forks per the ycash6 plan).
- Recommendation: none required; optionally log a warning when a node answers `getinfo` without a numeric `version`.

#### Checked and found sound
- Upgrade detection logic (`nodedatacheck.cpp:48-111`): regexes match the exact `LogPrintf` formats at both pins (`ref/ycash/src/init.cpp:916,1760`, `ref/ycash6/src/init.cpp:1018,2013`); a failed 6.20.0 start (no " block index Nms" line) correctly does not count; missing/rotated `debug.log` → `Unknown` → warns (fail-safe); a marker naming < 6.20.0 is ignored; the 16 MiB tail read bounds memory; `inspect` is proven read-only by `inspectChangesNothing`. The `--version` probe runs the bundled binary with a fixed argument and a 5 s timeout; an unparseable result assumes 6.20.0 (fail-safe).
- Backup ordering and paths (`connection.cpp:434-454`, `nodedatacheck.cpp:140-156`): the whole dialog runs before `startEmbeddedZcashd`, so wallet.dat is copied before any node touches the directory; a failed copy returns false and nothing is started or written; the backup name is `wallet.dat.yecwallet-backup-<ts>[-n]` with an existence loop (no overwrite) in the same directory as wallet.dat (no new exposure); `QFile::copy` preserves the source permissions. Quit truly changes nothing (checked: no write before the answer).
- RPC plumbing: `createZcashConf` (`connection.cpp:195-214`) writes `experimentalfeatures=1`/`yellowback=1` and a random `rpcpassword` exactly as the baseline did; `offerYellowbackConfRepair` appends two fixed lines only after a Yes; `rpcallowip` is never written or read; no `rpcbind` change; all node traffic stays on the baseline `QNetworkAccessManager` to the conf's host (plain HTTP, baseline behaviour).
- Process spawning: `ycashd` from the app directory with no args (baseline) or `--version`; `yellowback-attest subscribe --conf <appdata path>` from the app directory only (`yellowbacktab.cpp:1780-1829`), fixed argv, user-settable path only inside the TOML file, not on the command line. No shell, no user-controlled argv.
- Key material: the GUI never handles attestor hot/bond keys; `yed_registerattestor` draws them in the node and the dialog says so (`yellowbacktab.cpp:1566-1585`); `reportEquivocation` validates 148-hex before calling. `YellowbackController` holds only JSON snapshots.
- Dialog ↔ RPC consistency: `sendConfirmationAndCall`, `mintConfirmationAndCall`, `mintTwoStepHappyPath`, `redeem*`, `claimConfirmationAndResult`, `sweepCarriesTheAcknowledgement`, `attestorActionsRequestShapes` (tests/yellowbacktab_test.cpp:1260-1340, 1355-1420, 1420-1560, 1602-1645, 2190-2287) assert both the dialog text and the exact `lastParams` of the call; `mintCancelledMakesNoCall` asserts no call on cancel. Sweep sends the L10 acknowledgement verbatim; VOID release/redeem/sweep buttons are gated on node-reported `canRedeem/canSweep` plus local height checks.
- Input validation: Yellowback address prefix per `yed_getinfo.network` plus base58 charset and a node-side `yed_validateaddress` before every send; shielded/transparent addresses explicitly refused with a hint; amounts bounded by MIN/MAX mint and confirmed balance; `qint64` maths cannot overflow with the 9-digit whole-part cap.
- JSON readers (`yellowbackmodels.cpp:11-58`): type-checked, null-tolerant, default-returning; no `get<>` on an unchecked type anywhere in the delta; error messages from the node are displayed verbatim but only through `QMessageBox`/labels (no HTML rendering, no URL building except `openTxInExplorer` on a txid, baseline function).
- Price display (`settings.cpp:137-154`): the protocol fast median overrides CoinGecko only while fresh (15 min) and only when `yed_getstats.pFast > 0` and activation is `active`; source is labelled in the tooltip. No new outbound HTTP, hard-coded host or update URL in the delta; the baseline's HTTPS endpoints (CoinGecko, GitHub releases, yecblockexplorer) are unchanged.
- Rescan/import compatibility (`mainwindow.cpp:455-760`, `zcashdrpc.cpp:22-36`): the 6.20.0 synchronous import holds back other calls via `syncRescanInFlight` and always ends the busy state on success or error; `rescan=1`/`reindex=1` removal at the next connect is the baseline mechanism.
- Secrets in repo: none found (`grep` for password/token/BEGIN PRIVATE across the delta; the only password-bearing file is written at run time, F-4). `LICENSE`/copyright additions are add-only.
- Tests: `yellowbacktab_test.cpp` has 97 cases and 818 assertions over a fake `Connection`; the 3 devnet cases `QSKIP` without `YELLOWBACK_DEVNET_DIR` (documented). `nodecompat_test` uses a loopback `QTcpServer` on `127.0.0.1:0` (tests/nodecompat_test.cpp:39). `check-rpc-contract.py` really checks RPC_VERSION, method names and every key against the contract JSON; the copy check greps "trustless".
- Completeness vs plan §4.8 / Phase A5 / mapping §12: Mint page (source prices, selection line, carrier step, `mint10-diverged` banner), Positions `noticed`/`emergencyOpenAt` and notice action, read-only Attestors view with arming banner, Settings subscriber launcher and transport config, `build.sh --attest`, RPC_VERSION 3, the one-way upgrade warning (ycash6 plan item 3) — all present. Open per the plan itself: A5 exit (devnet case recorded), A6 `carrierTxid` on rows (F-9), `--package --attest` end-to-end.

#### Not covered / needs a different auditor
- The `yellowback-attest` subscriber binary itself (TLS to iroh relays, `.att` file parsing, `yed_addattestation` rate) — ycash-dd/contrib auditor.
- Whether `yed_estimatecollateral`, `yed_getfeepayee` and `yed_listclaimable` figures are consistent with what `BuildMint`/`BuildClaim` later use at the same reference height (node-side half of F-1).
- The baseline YecWallet code paths that the delta reuses unchanged (plain-HTTP RPC, `QSettings`-stored RPC password, CoinGecko/GitHub HTTPS calls, `--conf`/embedded mismatch in F-10) — upstream, out of scope.
- No build or run: the QTest assertions were read, not executed.

---

### yew (YEW mobile wallet) — audit report

#### Summary
Covered the whole `yew/` repository at `839e7d5`: the Rust core (`core/src/*.rs`, `core/src/net/`, `core/src/build/`, the bridge `api.rs`), the CLI, the Flutter app (`app/lib/**`, Android manifest/Kotlin, iOS plist), tests, scripts, CI and the W5 security review it ships with. Key handling, the gate, the serializer/signer, TLS plumbing, storage and supply chain are in good shape and match the plan; the W5 review (`docs/security-review.md`) is accurate for what it covers. The gap is the one the W5 review treats as "amounts the user confirmed": **every economic parameter of a mint, redeem or claim (vault lock/claim heights, required collateral, enforcement fee amount and payee, attestor fee) is taken from the single lightwalletd server without any local plausibility check, and a redeem is built and broadcast in one call with no preview**. A malicious or compromised server can therefore grief a minter (collateral locked in a VOID vault until an arbitrary height) and, where the fee payee is an eligible miner, take most of a vault's collateral as "fee" at redeem — contrary to the trust statement's promise that "a dishonest server cannot take your funds". Everything else found is Low/Info hardening or documented owner items.

#### Findings

##### G-1 [Severity: High] Mint vault parameters from the server are used unchecked: a lying server locks the collateral in a VOID vault until an arbitrary height (and, with enforcement off, makes it anyone-can-spend)
- Where: `yew/core/src/build/mint.rs:271-299` (`estimate`), `:436-500` (`start`), `:604-615` (`mint_outputs` builds `vault_script(m.lock_height, …, m.claim_height)`); `yew/core/src/net/yellowback.rs:338-352` (`estimate_collateral`)
- Status: CONFIRMED (grief, traced in code + spec); PLAUSIBLE (theft when enforcement is off)
- Applies to: yew
- What: `mint::estimate` copies `ref_height`, `lock_height`, `claim_height`, `required_zat`, `term_class`, `armed` verbatim from `EstimateCollateral`; `start` stores them in the `mints` row and `finish` builds the vault P2SH from them. Nothing checks `lock_height == ref_height + lock_blocks`, that `lock_blocks` is inside the class range the app itself knows (`app/lib/term_classes.dart`), that `claim_height == lock_height + GRACE` (34,560 mainnet / 24 regtest, spec table), that `ref_height ∈ [tip − REF_WINDOW, tip − 1]`, or that `required_zat` is consistent with the bundle's attested prices (the bundle *is* verified locally, but its prices are never compared with the server's `required_zat`/`p_mint`). The remote gate layer is the same server, so it says `ok`.
- Evidence:
  ```rust
  // mint.rs:271-293
  let e = yb.estimate_collateral(cents, lock_blocks, 0).await?;
  ...
  Ok(MintEstimate { ..., ref_height: e.ref_height as u32, lock_height: e.lock_height as u32,
      claim_height: e.claim_height as u32, required_zat: e.required_zat, ... })
  // mint.rs:604-606
  let vault = script::vault_script(m.lock_height, owner_pubkey, m.claim_height)
  ```
  Spec `ycash-dd/doc/yellowback-spec.md:434-436`: "If MINT-1 holds and any of MINT-2..8 fails and `vout[0]` is P2SH: `Vaults[txid:0] = VOID`, `yedOut = 0` (no YED is created; the collateral is locked until `lockHeight`)". Spec `:155-161`: the `OP_ELSE` branch is `<claimHeight> OP_CHECKLOCKTIMEVERIFY OP_DROP OP_TRUE` (no signature); `:687`: once enforcement is abandoned "every vault's claim path becomes spendable by anyone at its claim height".
- Scenario: the user picks (or is phished into) a server. On mint it answers `lock_height = R + 400_000_000`‑ish (any value `< LOCKTIME_THRESHOLD`) or a `lock_height` outside the class range, or `required_zat` far below the real ratio. The wallet shows the numbers, the user slides, the carrier and the MINT are signed and broadcast. MINT-2/MINT-5 fail on the network → VOID vault, no YED, collateral owner-releasable only after the server-chosen `lockHeight` (years, or never in practice). Grief with full loss of availability. If the server instead keeps `lock_height` plausible and sets `claim_height = lock_height + 1`, the vault is VOID with a claim branch that opens one block after the lock: while miners enforce (RED-1..4 via MP-1) the claim-path spend of a VOID vault is refused, but after the sunset `ENFORCE_UNTIL_HEIGHT` / abandonment (ACT-5, §4.6) it is a plain `OP_TRUE` spend — whoever is first (the server operator, who knows the script) takes the collateral. The W5 review's S-4 table lists `EstimateCollateral` as "overpaying … within what the user confirmed"; it does not consider the vault script heights.
- Recommendation: validate every server-supplied mint parameter locally before the carrier step: `lock_height == ref_height + lock_blocks`; `lock_blocks` within `termClassOf(network)` (hard-code the spec's class ranges in the core as `params.rs` already does for other constants); `claim_height == lock_height + GRACE(network)`; `tip − REF_WINDOW ≤ ref_height ≤ tip`; `term_class` consistent with `lock_blocks`; `required_zat ≥ cents · 10⁶ · ratio_min / medianAttestedPrice` computed from the verified bundle (or at minimum refuse when the bundle's median price and `p_mint` disagree by more than the spec's band). Record in `docs/trust.md` that the vault script terms are checked locally. Same check in `sync::refresh_vaults` before a stored vault is shown as redeemable.

##### G-2 [Severity: High] Enforcement-fee amount and payee (redeem, claim, mint) are dictated by the server with no bound; a redeem is built and broadcast in one call with no preview, so the fee is never shown before signing
- Where: `yew/core/src/build/redeem.rs:398-410, 436-439, 143` (`build_redeem`); `yew/core/src/wallet.rs:426-437` (`redeem` = build + broadcast); `yew/core/src/api.rs:1795-1830` (`redeem` bridge call); `yew/core/src/build/mint.rs:156-172` (`fee_payee`), `:238-245` (`attest_payee`: `fee_zat * attest_fee_bps / BPS` with `bps` from `GetYellowbackInfo`), `:457`; `yew/core/src/build/claim.rs:60-83, 136-157`; `app/lib/screens/vault.dart:370-379` (slider text shows burn and collateral only)
- Status: CONFIRMED (code path); theft requires the payee to be in `E(R)` (PLAUSIBLE for a server operator who also mines/pools)
- Applies to: yew
- What: `GetFeePayee` returns `fee_zat` and `preferred`/`default.payout_address`; the wallet pays exactly that amount to exactly that address. `plan_vault_spend` only refuses `collateral_out <= 0`. The node's RED-3/MINT-8 accept any fee `≥ feeZat(collateral)` to any `k ∈ E(R)`. For redeem, `Wallet::redeem` calls `build_redeem` then `broadcast` in the same call; the app's `redeem(vaultTxid)` returns the result after the send. The Vault screen's confirmation line is "Slide to redeem: burn $X" — the fee and payee appear only on the post-send card (`vault.dart:431`). For mint and claim the fee is displayed on the estimate (`mint.dart:242-243`, `claimable.dart:558-561`) but unbounded; the mint's fee is re-fetched at `start` (`mint.rs:457`) and the stored value is not compared with the one the user saw.
- Evidence:
  ```rust
  // redeem.rs:400-410
  let p = yb.fee_payee(r, v.collateral_zat, &keys::hex(&selector)).await?;
  let payee = if !p.preferred.is_empty() { p.preferred } else if let Some(d) = p.default { d.payout_address } else { String::new() };
  (sel, change, extra, stage, p.fee_zat, payee)
  // redeem.rs:143
  if collateral_out <= 0 { return Err(...) }
  // wallet.rs:433-434
  let p = redeem::build_redeem(self, yb, vault_txid, tip, branch_id).await?;
  let (txid, v) = redeem::broadcast(self, client, validator, &p).await?;
  ```
- Scenario: a server whose operator runs an eligible (signalling) pool answers a redeem's `GetFeePayee` with `preferred = <own payout address>, fee_zat = collateral − 2_000`. The wallet builds `vout[0] = 1,000 zat` to the owner and `vout[1] = collateral − 2,000` to the pool, signs with the owner key, the same server's dry run says `ok`, enforcing miners accept it (fee ≥ required, payee eligible). The user burned the full debt and received ~0 collateral. No screen showed the fee before the slide. If the payee is not eligible the redeem is merely refused (grief: the user has already burned nothing because the tx fails, but the lock on the YED inputs and the failed-redeem history row remain until expiry).
- Recommendation: (a) compute the enforcement fee locally — `max(FEE_MIN, collateral·FEE_BPS/10⁴)` with FEE_MIN/FEE_BPS hard-coded per network in `params.rs` (the spec fixes them per parameter set, `yellowback-spec.md:43`) — and refuse a server `fee_zat` above it (and an `attest_fee_bps` above the spec's value); (b) split `redeem` into `redeem_preview` / `redeem_confirm` like the YEC/YED sends, showing collateral back, fee, payee and burn before the slide; (c) at `mint_start` refuse a fee or payee that differs from the estimate the user confirmed; (d) show the payee on the mint/claim estimate cards; (e) treat `minted_cents` from `ListClaimable`/`GetVault` the same way (it sets the burn): cross-check `GetVault.minted_cents == ListClaimable.minted_cents` and display it, which is done; keep.

##### G-3 [Severity: Medium] The trust statement overclaims: "A dishonest server cannot take your funds"
- Where: `yew/docs/trust.md:10-18`, `app/lib/trust_text.dart` (checked equal by `scripts/check-trust-text.sh`); `docs/security-review.md` S-4 table
- Status: CONFIRMED (given G-1/G-2)
- Applies to: yew
- What: the statement the user must accept at onboarding says the server "cannot take your funds, but it can lie about them". With G-1 (collateral locked for an arbitrary term / anyone-can-spend after sunset) and G-2 (fee of the server's choosing to a payee of the server's choosing) that is not true for Yellowback operations; it is true for plain YEC sends and YED transfers.
- Evidence: `trust.md:14-16`: "A dishonest server cannot take your funds, but it can lie about them: it can hide a payment, show a balance that is not there, or refuse to relay a transaction."
- Scenario: a user relies on the statement when choosing an unknown public server for minting.
- Recommendation: fix G-1/G-2, then keep the sentence; until then qualify it ("…cannot spend your YEC or YED; for minting, redeeming and claiming it sets the terms you confirm — use only a server you trust").

##### G-4 [Severity: Medium] TLS on iOS does not work with system roots, and the app has no CA-pin field — mainnet/testnet on iOS cannot connect at all
- Where: `yew/core/src/net/tls.rs:118-125` (`with_native_roots()` only), `yew/core/Cargo.toml:30` (`tls-native-roots`), `README.md:260-261`, `docs/plans/yellowback-wallet-plan.md:3` (revision 11 note); `app/lib/api/wallet_api.dart` (no `caPem` parameter)
- Status: PLAUSIBLE (documented by the authors; not run here)
- Applies to: yew
- What: `rustls-native-certs` has no iOS backend (its Apple support is `security-framework` on macOS), so `ClientTlsConfig::with_native_roots()` yields an empty root store on iOS and every non-regtest connection fails the handshake. The only alternative in the core is `Server::ca_pem`, which the bridge and the app do not expose. The failure is closed (nothing connects), but it creates pressure to "temporarily" allow `plain` on testnet/mainnet, which `Server::parse_for` currently forbids.
- Evidence: `tls.rs:120-123`:
  ```rust
  let tls = match &self.ca_pem {
      Some(pem) => ClientTlsConfig::new().ca_certificate(Certificate::from_pem(pem)),
      None => ClientTlsConfig::new().with_native_roots(),
  };
  ```
- Scenario: the first iOS testnet build cannot reach any TLS lightwalletd; an owner adds a plain-transport escape hatch.
- Recommendation: add `webpki-roots` (allow-list decision) or ship the mainnet endpoint's certificate via the `ca_pem` path, and plumb `ca_pem` through `probe_server`/`create_wallet`/`unlock`/`set_server` and Settings before the testnet run. Keep `parse_for`'s regtest-only `plain` rule.

##### G-5 [Severity: Low] `consensusBranchId` is taken from the server with no network table
- Where: `yew/core/src/net/compact.rs:98-101`, `yew/core/src/params.rs:11-13` ("deliberately not a constant"), `yew/core/src/sync.rs:58-61`
- Status: CONFIRMED
- Applies to: yew
- What: the ZIP-243 personalization is the only domain separator between Ycash and Zcash (and between Ycash epochs). The branch id is stored from `GetLightdInfo` and never compared with the known ids of the wallet's network. A wrong id normally just makes every signature invalid (no loss, as the W5 review says). The exception is a key imported by WIF (D-W-11) that still holds pre-fork (height < 570,000) outputs on Zcash: a server supplying Zcash's current branch id would make the wallet produce a signature valid on Zcash, spending the user's ZEC duplicate to the same recipient hash160 — for a mint, to a vault/fee output the server chose.
- Evidence: `compact.rs:98`: `let branch_id = u32::from_str_radix(i.consensus_branch_id.trim_start_matches("0x"), 16)`
- Scenario: niche (imported pre-fork key + malicious server); loss bounded to the pre-fork ZEC duplicate.
- Recommendation: carry the per-network list of Ycash branch ids (`ref/ycash/src/chainparams.cpp` upgrade table) in `params.rs` and refuse a `branch_id` not in it; it also catches a misconfigured server early.

##### G-6 [Severity: Low] Unchecked multiplications in the transaction parser on server-supplied bytes
- Where: `yew/core/src/tx.rs:289, 294, 300`
- Status: CONFIRMED
- Applies to: yew
- What: `shielded.spends * SPEND_DESCRIPTION_SIZE`, `shielded.outputs * OUTPUT_DESCRIPTION_SIZE`, `shielded.joinsplits * js_size` use a `compact_size()` read from the wire (up to `u64::MAX`) without `checked_mul`. In debug/test builds this panics; in release (`overflow-checks` off, `Cargo.toml` sets none) it wraps and the subsequent `take` either fails or, with a wrapped small product, reads too little and ends in `Trailing`. No memory issue (the `Reader` is bounds-checked), but a panic in a debug app build aborts the sync (frb converts panics to a Dart exception).
- Evidence: `r.take(shielded.spends * SPEND_DESCRIPTION_SIZE)?;`
- Scenario: a server streams a crafted "transaction" in `GetTaddressTxids`; debug builds crash the sync, release builds get a parse error for that tx and the sync aborts (`sync.rs:93` `?`), so the wallet cannot sync from that server — DoS only.
- Recommendation: `checked_mul` → `TxError::Truncated`; consider skipping an unparseable transaction with a warning instead of failing the whole sync.

##### G-7 [Severity: Low] Server streams are collected without bounds
- Where: `yew/core/src/net/compact.rs:171-194` (`address_utxos` grows `max_entries` to `u32::MAX`), `:201-225` (`taddress_txs` collects every raw tx into a `Vec`), `yew/core/src/net/yellowback.rs:284-296, 300-312, 452-467, 484-501` (`list_vaults`, `list_claimable`, `attestations`, `address_tokens` collect)
- Status: CONFIRMED
- Applies to: yew
- What: a malicious server can answer with gigabytes; the phone's process is killed. Only the chosen server can do this (DoS of the victim's wallet, no loss).
- Recommendation: cap the number of messages / bytes per call and fail the sync with a clear error.

##### G-8 [Severity: Low] A malformed `GetAddressUtxos` entry is silently turned into outpoint `0000…:n`
- Where: `yew/core/src/net/compact.rs:261-273` (`from_reply`)
- Status: CONFIRMED
- Applies to: yew
- What: `if r.txid.len() == 32 { copy } ` else the txid stays all-zero and the entry is accepted as a UTXO with the server's `value_zat`/script, later classified as YEC/HELD and shown in the balance; a spend of it is refused by the node (phantom coin). Should be a `Mismatch` error.
- Recommendation: return `Err(NetError::Mismatch)` for a txid that is not 32 bytes; same for `index < 0`.

##### G-9 [Severity: Low] Mint `cents` is truncated to `u32` in the payload after being estimated as `u64`
- Where: `yew/core/src/build/mint.rs:626` (`cents: m.cents as u32`), `yew/core/src/api.rs:1575-1583` (`mint_estimate(cents: i64)` only checks `<= 0`)
- Status: CONFIRMED
- Applies to: yew
- What: an amount above 4,294,967,295 cents is estimated and collateralised at the full value by the server, but the MINT payload carries `cents mod 2³²`; the node then evaluates a different mint than the one shown. In practice the node's supply cap / `EstimateCollateral` refuses such sizes, but the bound belongs in the wallet.
- Recommendation: refuse `cents > u32::MAX` (and `> MAX_OUTPUT_CENTS` if the node's mint cap applies) in `api::mint_estimate`/`mint_start`.

##### G-10 [Severity: Low] Keystore items are not biometric-bound; the BIP39 passphrase sits beside the seed
- Where: `yew/app/lib/state/secrets.dart:27-31` (`IOSOptions(accessibility: first_unlock_this_device)`, Android default options), `app_state.dart:103-105` (passphrase written to the keystore); `docs/security-review.md` A-1 (deferred), A-7
- Status: CONFIRMED (known and recorded as deferred)
- Applies to: yew
- What: the "device unlock" toggle is an app-level `local_auth` prompt; a process with the app's sandbox (jailbreak, backup extraction on iOS — the Keychain item is `ThisDeviceOnly` so not in backups, good) reads the seed without biometrics. The passphrase adds nothing against keystore compromise. iOS's support directory (the SQLite cache: addresses, history, wrapped imported keys) is still iCloud-backed-up unless `NSURLIsExcludedFromBackupKey` is set (S-5, `[owner]`).
- Recommendation: owner decision as recorded; at least set `AndroidOptions(encryptedSharedPreferences/keyCipherAlgorithm …, enforceBiometrics)` behind the toggle, add the iOS `accessControl` variant, and exclude the data dir from iCloud backup.

##### G-11 [Severity: Low] CI actions pinned by tag, not by commit SHA; codegen/audit tools installed from crates.io at build time
- Where: `yew/.github/workflows/ci.yml:22, 25, 48, 51, 60` (`actions/checkout@v4`, `Swatinem/rust-cache@v2`, `subosito/flutter-action@v2`), `:40-41` (`cargo install cargo-audit --locked`), `:73` (`cargo install flutter_rust_bridge_codegen --version … --locked`)
- Status: CONFIRMED
- Applies to: yew
- What: a compromised action tag or a yanked/replaced crate version can alter CI output. Trigger is `pull_request` (not `pull_request_target`), no secrets are used, the bridge diff check is a real guard, and the app binaries (`jniLibs`, `YewCore.xcframework`) are gitignored, not committed — so the blast radius is CI integrity only. Also `app/android/app/build.gradle.kts:38-40` still signs release with the debug key (`[owner]` TODO).
- Recommendation: pin actions to SHAs; keep `--locked`; set up the release signing config before any store build.

##### G-12 [Severity: Info] Completeness against the plan
- Where: `docs/plans/yellowback-wallet-plan.md` §7 (W0–W5 ticked, revision 11), `yew/README.md` owner list, `core/tests/vectors.rs:183` (`#[ignore] ywallet_derivation_vector` pending the owner capture), `core/tests/devnet.rs` (three `#[ignore]` suites gated on `YEW_DEVNET=1`), `app/integration_test/*` (M1 passes on simulator/emulator; M2 stops at the node's $100 mint floor), `docs/security-review.md` S-3b/S-5b/A-1/A-3 (deferred)
- Status: CONFIRMED
- Applies to: yew
- What: W0–W6 are delivered; no `TODO`/`unimplemented!` in the core (only Flutter template TODOs in `build.gradle.kts`). Open owner items: Ywallet derivation vector (the only test of D-W-7 compatibility is the plan's assertion, not a vector), ≥ 4-week testnet run, public endpoints (mainnet/testnet default lists are empty by design, `tls.rs:30-31`), the app's CA-pin field, iOS roots (G-4), iOS switcher blur, "Rebuild from chain" losing in-flight carriers (S-5b: the carrier is P2SH and never listed by `GetAddressUtxos`), store metadata and signing. Also by design but worth stating in the UX: the MINT main transaction is broadcast **automatically** by the progress screen's timer once the carrier confirms (`app/lib/screens/mint_progress.dart:57-68`) — the user's one confirmation is at the estimate.
- Recommendation: none beyond the owner list; add the Ywallet vector before mainnet (a derivation mismatch would strand restores).

#### Checked and found sound
- Seed generation: `bip39 3.0.0` `Mnemonic::generate_in` with the `rand` feature (OS RNG), 12/24 words; mnemonic/seed/HMAC outputs wiped (`keys.rs:67-105, 121-131, 163-205`); the only `unsafe` in the crate is `ptr::write_volatile` in `wipe` (`keys.rs:73`). `secp256k1 =0.33.1`, no `zcash_*`/librustzcash dependency anywhere (`Cargo.lock` has no git sources).
- BIP32/BIP44 path `m/44'/347'/0'/{0,1}/i`, compressed keys, `hash160`; address version bytes match `ycash-dd/src/chainparams.cpp` and `yellowback/params.cpp` (`params.rs:50-83`); WIF prefix/compressed flag checked; parsing refuses other networks (`keys.rs:393-455`); node-generated vectors for signing, addresses, templates and payloads pass byte-for-byte (`core/tests/vectors.rs`, `tests/vectors/*.json`).
- ZIP-243 sighash and v4 transparent serializer (`tx.rs:196-230, 338-410`): header `0x80000004`, group `0x892F2085`, three zero shielded hashes, `valueBalance = 0`, SIGHASH_ALL only, DER + `0x01`, `nExpiryHeight = tip + 40` (`params.rs:142-146`), `nLockTime`/`nSequence 0xFFFFFFFE` on vault spends (`redeem.rs:80-85`), fee = 1,000 zat (`params.rs:97-116` cites the node).
- Payload codec (`payload.rs`): bounds-checked reader, exact sizes per type, `MIN/MAX_PAYLOAD`, assignment uniqueness and non-zero cents, single-`OP_RETURN` rule, cross-checked against node templates; carrier/vault scripts and push encoding reproduce `script.cpp` (`script.rs`), bundle push ≤ 520 B enforced.
- Bundle verification (`bundle.rs:174-224`): shape, count ≤ 6, seated membership, no duplicate seq, compact ECDSA with high-S rejected, message = `SHA256("YBATTEST1"‖…‖blockHash)` — the one thing verified independently of the server's dry run.
- The broadcast gate (`gate.rs`): both layers mandatory, no `cfg`/feature/env bypass, `send_transaction` reachable only from the five `broadcast`/`send` sites after `gate::confirm[_burning]`; the local layer refuses HELD/PENDING_TOKEN/UNKNOWN_P2SH/FOREIGN inputs on every path and pins the carrier/vault positions. TOKEN class only from `GetAddressTokens`; a 10,000-zat own output the server does not list is HELD and unspendable (`coins.rs:170-190`).
- TLS (`net/tls.rs`): `https` unless `plain`; `plain` refused outside regtest by the only constructor the bridge/CLI use (`parse_for`, `api.rs:789`); host charset restricted to DNS/IPv4/[IPv6]; 15 s connect timeout; optional single-anchor `ca_pem`; mainnet/testnet default server lists empty by design.
- Bridge boundary (`api.rs`): secrets wrapped in `SecretString`, generated mnemonic returned once; errors carry node verdict text but never key material; `expect()` only on invariants (`conn` set just above, runtime build); frb 2.13.0 converts Rust panics into Dart exceptions rather than aborting; one async mutex guards the handle.
- App: no `print`/`debugPrint`/`log` of secrets; seed only in `flutter_secure_storage`, never in `AppState` fields (`app_state.dart`); `FLAG_SECURE` on seed/export/import screens (`MainActivity.kt`, `screen_privacy.dart`); no URL schemes / deep-link intent filters (only `MAIN/LAUNCHER`; no `CFBundleURLTypes`); `allowBackup=false` + full extraction exclusion; `Clipboard` used only for address/txid copy and paste (`send.dart:164`, `history.dart:123`, `address_qr.dart:42`); no analytics or network plugin (`check-app-imports.sh` enforces it).
- Storage (`store.rs:383-405`): SQLite `0600`, WAL; no seed/HD key stored; imported keys wrapped with an HMAC-SHA256 keystream under a seed-derived key and verified by `hash160` on unwrap (`wallet.rs:214-247`); wallet file bound to the seed via `primary_hash160` and to the network.
- Supply chain: all direct deps `=x.y.z`, `Cargo.lock` committed (227 crates, 0 advisories at W5), `rust-toolchain.toml` 1.92.0, `pubspec.lock` with sha256 for every package, `flutter_rust_bridge` 2.13.0 pinned in crate, codegen and Dart package with a CI regenerate-and-diff check, protos byte-pinned to `lightwalletd-dd` `1f10c771` (`proto/PIN`, `check-proto-pin.sh`); no `curl | sh` in scripts; no secrets in the repo (`ExportOptions.plist.example` has a placeholder; the real file is gitignored).
- Tests: 29 widget tests over a fake `WalletApi` assert real behaviour (verbatim gate refusals, disabled sliders, numbers shown); core unit tests cover gate property cases, selector parity, payload fuzz-ish rejects, parse round trips; devnet suites exercise mint/lapse/sweep/redeem/claim/import end to end (gated, by design).

#### Not covered / needs a different auditor
- Whether lightwalletd-dd's `YellowbackStreamer` proxies (`GetFeePayee`, `EstimateCollateral`, `ListClaimable`, `ValidateRawTransaction`) can themselves be made to return the values G-1/G-2 rely on by a third party (e.g. a hostile node behind an honest lightwalletd) — lightwalletd/node auditors.
- The node-side consequences of a VOID vault's claim branch after `ENFORCE_UNTIL_HEIGHT`/abandonment (G-1's theft leg) — node/spec auditor.
- `coinselect.rs` (the floor-aware selector) was not reviewed line by line; it is pure arithmetic over local data, parity-tested against `yed_estimatesend` on the devnet.
- Running the Flutter app, the iOS TLS behaviour (G-4) and the keystore options on real devices — not possible here (read-only audit).

---

### yolo + chain-viz — audit report

#### Summary

Read every Rust source file of `yolo/` (13 files, ~2.6k lines) and `chain-viz/` (16 files + `ui/*.js`, ~3.5k lines), their `Cargo.toml`/`Cargo.lock`/`rust-toolchain.toml`, chain-viz's CI workflow, the READMEs' hosting/credential sections, and compared yolo's stratum behaviour with `ref/yolo` (Perl) where security-relevant. Neither component holds keys or sends transactions; neither reaches a write RPC (chain-viz enforces this with `tests/readonly_gate.rs`). The Yellowback tag in yolo is taken verbatim from the node's `coinbaseaux.flags` and a miner has no path to alter it (miners control only the 18-byte nonce2); Y-F1 (Perl cenote dropping the tag) is fixed and pinned by tests. The real weaknesses are resource bounds on yolo's internet-facing stratum listener (unbounded line length, no connection cap or idle disconnect, unmetered `submitblock`/`validateaddress` forwarding to the node) and chain-viz's unconditional trust of `X-Forwarded-For` in `--public` mode, which defeats its only abuse control. Everything else found is hardening or completeness. No Critical or High finding.

#### Findings

##### H-1 [Severity: Medium] [yolo] Stratum reader has no line-length bound: one client can exhaust the pool's memory
- Where: yolo/src/stratum.rs:147,152
- Status: CONFIRMED
- Applies to: yolo
- What: Each miner connection is read with `BufReader::new(rd).lines()` and `next_line()`. tokio's `read_line` grows the `String` until a `\n` arrives; there is no cap. A peer that streams bytes without a newline makes the pool allocate without limit.
- Evidence:
  ```rust
  let mut lines = BufReader::new(rd).lines();
  ...
  line = lines.next_line() => match line {
      Ok(Some(line)) => self.handle_line(&line, &state, &mut out).await,
  ```
- Scenario: `nc pool 3333 < /dev/zero` (or N such sockets) until the pool is OOM-killed; every miner on the pool loses work until restart. No auth is needed: the read happens before `mining.authorize`.
- Recommendation: Replace with `tokio_util::codec::LinesCodec::new_with_max_length(8192)` (or a manual `read_until` with a cap) and disconnect on overflow. A stratum line is well under 2 KB even at 192,7 (403-byte solution = 806 hex chars).

##### H-2 [Severity: Medium] [yolo] No connection cap and no idle disconnect for unauthenticated sockets (slow-loris)
- Where: yolo/src/stratum.rs:76-103 (accept loop), :150-175 (keepalive branch)
- Status: CONFIRMED
- Applies to: yolo
- What: `serve` spawns a task per accepted socket with no limit. The 60 s timer only *re-notifies* an authorized, mining client; a socket that never sends anything (or sends one byte an hour) is kept forever. Each idle task holds a `BufReader` (8 KiB), a `watch::Receiver` and a `Client`; the `miners` gauge in `/status` counts them as miners.
- Evidence:
  ```rust
  _ = keepalive => {
      if self.mining && !state.lock().template_stale() { ... re-notify ... }
      self.last_write = Instant::now();
      Action::Continue
  }
  ```
- Scenario: tens of thousands of idle TCP connections from a few hosts exhaust file descriptors (`ulimit -n`) so real miners get `accept: Too many open files` (the loop then sleeps 100 ms and retries forever); `/status` reports a bogus miner count.
- Recommendation: Cap concurrent connections (a `Semaphore` acquired in `serve`), add a per-IP cap, and disconnect any socket that has not completed `mining.authorize` within e.g. 30 s and any client silent for more than N keepalive periods. Also exclude unauthorized sockets from the `miners` gauge.

##### H-3 [Severity: Medium] [yolo] `mining.submit` is forwarded to the node unmetered and without any local PoW check; a flood starves the template poller
- Where: yolo/src/stratum.rs:321-327, :337-355; yolo/src/work.rs:170-180; yolo/src/poller.rs:98
- Status: CONFIRMED
- Applies to: yolo
- What: `Submit::check` validates only hex-ness and lengths; the block hash is never compared to the target and the Equihash solution is never verified locally. Every well-formed submit becomes a `submitblock` RPC carrying the whole block hex (up to `sizelimit` = 2 MB) run on `spawn_blocking`. In addition each submit resets `mining`/`ready`, so the next `pump` rebuilds a job (`build_work` hex-encodes all template transactions again, under the state mutex) and re-sends `set_target` + `notify`. The poller's `getblocktemplate` also runs on `spawn_blocking`; tokio's blocking pool is bounded (512 threads by default) and FIFO, so a flood of submits queues the template refresh behind them.
- Evidence:
  ```rust
  "mining.submit" => {
      self.mining = false;
      self.ready = false;
      let ok = self.submit(&id, &params, state).await;
  ...
  let block = assemble_block(&work, &self.nonce1, &submit);
  let rpc = state.rpc.clone();
  let verdict = tokio::task::spawn_blocking(move || rpc.submitblock(&block)).await;
  ```
  `Submit::check` (work.rs:170-180) ends with `equihash.check_solution_hex(solution)?` which only checks `bytes.len() != self.solution_wire_len()`.
- Scenario: One authorized client (any valid t-addr suffices when `--password` is unset, which is the default and what the README calls "anything") loops `mining.submit` with random nonce2/solution: the pool's node receives a stream of 2 MB `submitblock` calls (each decoded and PoW-checked by ycashd on its 4 `-rpcthreads`), the pool spends CPU rebuilding jobs, and after ~512 in-flight calls the poller cannot fetch templates so every other miner works on a stale height.
- Recommendation: Verify locally before forwarding: compute the header hash (`dsha256` of the 140-byte header ‖ solution) and compare to `target`; optionally verify the Equihash solution (a 192,7 verify is cheap). Reject and count a `high-hash` locally; disconnect/ban a client after N bad submits per minute. Give the poller its own dedicated blocking thread (or a `Semaphore` on submit forwarding, e.g. 2 in flight per client, 8 total) so template refresh is never queued behind submits. Note the Perl behaved the same (`stratumsolo:122` forwards everything), so nothing was lost — this is a hardening gap carried over.

##### H-4 [Severity: Low] [yolo] Unauthenticated `mining.authorize` is an unmetered `validateaddress` amplifier
- Where: yolo/src/stratum.rs:263-283
- Status: CONFIRMED
- Applies to: yolo
- What: Without `--payout`, every `mining.authorize` triggers a `validateaddress` RPC on `spawn_blocking`, before any password check succeeds when `--password` is unset, and it can be repeated on an already-authorized connection without limit.
- Evidence:
  ```rust
  let rpc = state.rpc.clone();
  let address = self.worker.clone();
  let result = tokio::task::spawn_blocking(move || rpc.validateaddress(&address)).await;
  ```
- Scenario: Same effect as H-3 at lower cost per message: thousands of `authorize` lines per second from one socket occupy the node's RPC threads and the pool's blocking pool.
- Recommendation: Allow one `authorize` per connection (disconnect on a second), rate-limit per IP, and cache `validateaddress` results per address.

##### H-5 [Severity: Low] [yolo] Stratum password compared non-constant-time, shared by all miners, sent in clear
- Where: yolo/src/stratum.rs:266-271
- Status: CONFIRMED
- Applies to: yolo
- What: `if &password != expected` is an early-exit string compare. Stratum is plaintext TCP so the password is sniffable anyway; the compare is the lesser issue but trivial to fix.
- Evidence: `if &password != expected { out.push_str(&msg_auth_failed(&id, "Auth Failed")); ... return Action::Disconnect; }`
- Scenario: Timing side channel over the network is impractical for a short string but costs nothing to close.
- Recommendation: Use `subtle::ConstantTimeEq` (or compare SHA-256 digests). Document in the README that `--password` is an access gate, not a secret channel, and recommend a firewall/allowlist for a private pool.

##### H-6 [Severity: Low] [yolo] Hidden `--no-flags` flag ships in the production binary and silently drops the pool's price vote
- Where: yolo/src/main.rs:64-66; yolo/src/work.rs:102
- Status: CONFIRMED
- Applies to: yolo
- What: `--no-flags` ("Test only: reproduces the Perl cenote; drops the tag") is a `hide = true` clap flag, not `cfg(test)`/feature gated. With it set, `build_coinbase` rebuilds the scriptSig without `coinbaseaux.flags`, so every block the pool mines carries no quote/signal tag — the pool's node operator has configured a vote that never reaches the chain, and the only trace is `tag: none` in the log line.
- Evidence:
  ```rust
  #[arg(long, hide = true)]
  no_flags: bool,
  ...
  let flags = if policy.no_flags { Vec::new() } else { t.flags_bytes()? };
  ```
- Scenario: An operator copying a test invocation (`yellowback_stratum.py` negative case) into a systemd unit mines untagged blocks for weeks; participation/registration (REG-1) silently lapses for that payoutKey.
- Recommendation: Gate behind `#[cfg(feature = "regtest")]` (the feature already exists), or at minimum log at `error!` on every template and expose `"noFlags": true` in `/status`.

##### H-7 [Severity: Info] [yolo] Tag `payoutKey` and coinbase payee diverge when miners are paid by username
- Where: yolo/src/work.rs:110-118; ycash-dd/doc/yellowback-spec.md:98,369,609 (MINER-2, FEE-2)
- Status: CONFIRMED (behaviour), design question for the owner
- Applies to: yolo
- What: Without `--payout`, `vout[0]` is rewritten to the miner's address but the tag inside `coinbaseaux.flags` still carries the node's `-yellowbackpayoutaddress` Hash160 (MINER-2). Per FEE-2 the eligible fee payees are the tag's `payoutKey`s, so a block mined by miner A credits enforcement-fee eligibility (and the quote itself) to the pool operator's key. That is probably intended (the pool's node is the voter) but is not stated in `yolo/README.md` (lines 54-60 only say the key "defaults to mineraddress").
- Evidence: `cb.vout[0].script_pubkey = spk.to_vec();` with the scriptSig/flags untouched (`// scriptSig untouched` test at work.rs:293).
- Scenario: A miner on a username-payout pool expects to be a registered Yellowback miner and never is; or a pool operator collects fees for hash power that is not theirs — both are economic-rule surprises rather than exploits.
- Recommendation: State in the README (and `/status`) that the tag's payoutKey is always the node's, independent of `--payout`; consider logging a one-time warning when `--payout` is unset.

##### H-8 [Severity: Low] [yolo] Miner-controlled strings are logged unsanitized (log injection)
- Where: yolo/src/stratum.rs:258-260, :267-269, :277, :290, :301, :329
- Status: CONFIRMED
- Applies to: yolo
- What: `software` (subscribe param 0), `worker` (authorize param 0) and the unknown method name are logged with `{}`/`{:?}` after JSON decoding, so `\n`, ANSI escapes and fake "block accepted" lines can be injected into the pool log. `{:?}` is used in some lines (escapes control chars) but not in `subscribed ({})` or `paying {}`.
- Evidence: `info!("miner {}: subscribed ({}), nonce1 {}", self.index, self.software, self.nonce1);`
- Scenario: An attacker forges "block N accepted" lines to confuse an operator's monitoring (`monitor-quote.sh`-style greps on the log).
- Recommendation: Log with `{:?}` everywhere, or truncate and strip non-printables; cap `software`/`worker` at e.g. 128 bytes.

##### H-9 [Severity: Low] [yolo, chain-viz] RPC credentials on argv and over cleartext HTTP; yolo connects to the conf's `rpcbind` host
- Where: yolo/src/main.rs:43-48; yolo/src/rpc.rs:74-77,145; chain-viz/src/main.rs:35-40; chain-viz/src/rpc.rs:181
- Status: CONFIRMED
- Applies to: yolo / chain-viz
- What: `--rpc-password` / `--rpcpassword` and `--nodes http://user:pass@host` are visible in `ps`/shell history. Both clients speak plain `http://` with Basic auth; nothing warns when the host is not loopback. yolo additionally derives the connect URL from `rpcbind=` in the conf (`ConfFile::url`), which is a *listen* address (`0.0.0.0` is common) and not where to connect.
- Evidence: `let host = self.rpcbind.clone().unwrap_or_else(|| "127.0.0.1".into());`
- Scenario: An operator pointing yolo at a remote node leaks the node's RPC password on the wire; `rpcbind=0.0.0.0` yields `http://0.0.0.0:8832`, which works on Linux by accident and fails elsewhere.
- Recommendation: Prefer cookie/env/file sources, warn when the RPC URL is not loopback and not `https`, and stop reading `rpcbind` as a connect host (use `rpcconnect` if present).

##### H-10 [Severity: Info] [yolo] `/status` is unauthenticated and bound to the stratum bind address
- Where: yolo/src/main.rs:110; yolo/src/status.rs:14-43
- Status: CONFIRMED
- Applies to: yolo
- What: `--status-port` binds on the same IP as stratum (default `0.0.0.0`) and answers anyone with payout address, node-up flag, height, miner count, last verdict. The handler is bounded (2 KiB read, 5 s timeout, `Connection: close`) so no DoS, only disclosure.
- Recommendation: Default the status listener to loopback (`--status-bind`), or document that it is public.

##### H-11 [Severity: Medium] [chain-viz] `--public` rate limiting trusts `X-Forwarded-For` unconditionally: bypass and unbounded bucket map
- Where: chain-viz/src/public.rs:89-96, :52-57; chain-viz/README.md:310-313
- Status: CONFIRMED
- Applies to: chain-viz
- What: `client_ip` takes the first `X-Forwarded-For` entry whenever the header is present, whether or not a proxy sits in front. The README explicitly offers `--public` "with or without a proxy". A direct client therefore chooses its own bucket key. The bucket map's only eviction runs when `len() > 4096` and removes entries idle for more than 120 s, so a client rotating a fresh XFF value per request keeps every entry live.
- Evidence:
  ```rust
  if let Some(xff) = req.headers().get("x-forwarded-for").and_then(|v| v.to_str().ok()) {
      if let Some(ip) = xff.split(',').next().and_then(|s| s.trim().parse().ok()) {
          return Some(ip);
  ...
  if b.len() > 4096 {
      b.retain(|_, (_, last)| now.duration_since(*last).as_secs_f64() < IDLE_SECS);
  }
  ```
- Scenario: A public instance without a proxy: `for i in ...; curl -H "X-Forwarded-For: 10.$i" /api/snapshot` sidesteps the 10 req/s limit entirely, and at a few thousand req/s the `HashMap<IpAddr,(f64,Instant)>` grows by ~hundreds of thousands of entries per 120 s window. `/api/snapshot` serialises 200 blocks with their `yb` views per call, so the CPU cost per request is not trivial. Behind a proxy that *appends* rather than overwrites XFF (nginx's `$proxy_add_x_forwarded_for` appends), the first entry is still client-supplied — the README's own nginx snippet is vulnerable.
- Recommendation: Add `--trusted-proxies <cidr,…>` and honour XFF only when the TCP peer is in that list, taking the *last* untrusted hop rather than the first entry; otherwise use the peer address. Cap the bucket map (evict LRU past N entries regardless of idleness).

##### H-12 [Severity: Low] [chain-viz] Without `--public` there are no resource caps: unbounded WebSocket clients, 100k-event `/api/events` dumps, 64 MiB inbound WS frames
- Where: chain-viz/src/server.rs:218-231, :81-87; chain-viz/src/main.rs:141,207 (`Bus::new(100_000, …)`); chain-viz/src/server.rs:261-263
- Status: CONFIRMED
- Applies to: chain-viz
- What: The WS cap, events cap and rate limit are installed only under `--public`. The default bind is loopback and `main.rs:229` warns when a non-loopback bind lacks `--public`, which is the right design, but an operator who ignores the warning (or puts a proxy in front without `--public`, which the README lists as option A) gets: unlimited WS sessions each with a 4096-deep broadcast receiver; `/api/events?since=0` cloning and serialising up to 100,000 events per request; inbound WS messages read and discarded with axum/tungstenite defaults (64 MiB max message), so one client can make the server buffer 64 MiB per in-flight message.
- Evidence: `let mut list = self.bus.since(since); if self.public.is_some() { list.truncate(public::EVENTS_CAP); }`
- Scenario: Reverse-proxied instance started per README option A without `--public`: a single curl loop on `/api/events` saturates a core; a few hundred WS clients multiply memory.
- Recommendation: Make the caps unconditional (they cost nothing locally); set `WebSocketUpgrade::max_message_size(64 * 1024)`; make `--public` only control redaction + rate limiting. Alternatively refuse to bind non-loopback without `--public` instead of warning.

##### H-13 [Severity: Low] [chain-viz] No `Origin` check on `/ws` and no authentication: any web page can read a local instance over WebSocket
- Where: chain-viz/src/server.rs:218-231, :233-266
- Status: CONFIRMED
- Applies to: chain-viz
- What: The REST endpoints are protected from cross-site reads by the browser's same-origin policy (no CORS layer is installed — good), but WebSockets are not subject to CORS and the upgrade handler never inspects `Origin`. There is no auth of any kind (`auth.rs` only reads the *node's* cookie). Everything is read-only, so impact is disclosure of what the operator's loopback instance sees: node ids/roles, errors (scrubbed of addresses), replay file path, devnet heartbeat/sim JSON, and under `--record` nothing extra.
- Evidence: `async fn ws(State(s): State<Arc<AppState>>, upgrade: WebSocketUpgrade) -> Response { ... upgrade.on_upgrade(...) }`
- Scenario: Operator with chain-viz on 127.0.0.1:8480 visits a hostile page that opens `ws://127.0.0.1:8480/ws` and exfiltrates the event stream (including `--devnet` sim stats and node error text).
- Recommendation: Reject WS upgrades whose `Origin` host does not match the `Host` header (or an `--allow-origin` list); apply `public::redact` to WS frames always, not only under `--public`.

##### H-14 [Severity: Low] [chain-viz] Static export embeds JSON in a `<script>` without `</script>` escaping
- Where: chain-viz/src/export.rs:52-53
- Status: PLAUSIBLE (sink confirmed; no chain-derived free text reaches it today)
- Applies to: chain-viz
- What: `ui/data.js` is `window.CHAIN_VIZ_STATIC = {json};` written with `serde_json`'s `Display`, which does not escape `<`/`/`. A string containing `</script>` would terminate the script element in the exported `index.html`. I checked `events.rs`/`classify.rs`: event strings are hashes, txids, addresses, enum-like `tx_type`/`verdict`/`status`, collector `note.text` (node RPC error messages, scrubbed) and devnet `heartbeat.json`/`sim-stats.json`/`attest-price-*` contents (local files). None is attacker-controlled on-chain text today, but node error messages can echo RPC input and a future memo/coinbase-text event would be.
- Evidence: `write_atomic(&dir.join("ui").join("data.js"), format!("window.CHAIN_VIZ_STATIC = {};\n", data).as_bytes())?;`
- Recommendation: Escape `<` as `<`, `>` as `>` and U+2028/2029 in the embedded JSON (one `replace` chain), as every JSON-in-HTML embedder does.

##### H-15 [Severity: Low] [chain-viz] CI actions pinned by mutable tag; release job has `contents: write`
- Where: chain-viz/.github/workflows/ci.yml:22-25, :49-54, :62
- Status: CONFIRMED
- Applies to: chain-viz
- What: `actions/checkout@v4`, `dtolnay/rust-toolchain@stable`, `Swatinem/rust-cache@v2`, `softprops/action-gh-release@v2` are floating tags. The release job runs with `contents: write` on `v*` tags and uploads binaries + sha256 produced in the same job (the checksum attests nothing beyond the upload). The workflow uses `pull_request`, not `pull_request_target`, and no secrets beyond `GITHUB_TOKEN` — good.
- Recommendation: Pin actions to commit SHAs; consider building the checksum file in a separate step/job or signing. yolo has no CI at all (`yolo/.github` absent) — `cargo test` and `clippy -D warnings` never run on push there (Info).

##### H-16 [Severity: Info] [yolo, chain-viz] Floating `stable` toolchain; lockfiles present and git-free
- Where: yolo/rust-toolchain.toml, chain-viz/rust-toolchain.toml; Cargo.lock in both (0 `git` sources); `rust-version = "1.85"`
- Status: CONFIRMED
- Applies to: both
- What: `channel = "stable"` is deliberate (shields from ycash-dd's 1.51 pin) but means builds are not reproducible across time; CI uses `--locked`, so dependency drift is controlled, compiler drift is not.
- Recommendation: Pin `channel = "1.xx.y"` and bump deliberately; keep `--locked`.

##### H-17 [Severity: Info] [yolo] Minor robustness notes carried from the trusted-node boundary
- Where: yolo/src/tx.rs:71-72,83-84 (`pos + sig_len as usize` from a node-supplied compact size, overflow panics in debug); yolo/src/stratum.rs:340 (an unknown `job_id` silently falls back to the latest job rather than rejecting); yolo/src/stratum.rs:33-40 (`client_index & 0xffff` wraps after 65 536 connections; uniqueness then rests solely on the 12 random bytes, which is fine)
- Status: CONFIRMED
- Applies to: yolo
- Recommendation: Use `checked_add` in the parser; reject submits for unknown job ids (count them as `stale`).

#### Checked and found sound

- [yolo] Tag integrity: the price/signal/payoutKey come only from the node's `coinbaseaux.flags` (`template.rs:28-31`, `work.rs:100-108`); miners never touch the coinbase (no coinbase extranonce; nonce2 lives in the 32-byte header nonce, `work.rs:186-199`), so neither a miner nor a stratum peer can steer the pool's vote. Y-F1 is fixed (`tx.rs:146-177`, flags appended verbatim) and pinned (`work.rs` tests `text_set_carries_flags_and_text`). `change_key` re-issues work when flags change (Y-F2, `template.rs:120-127`).
- [yolo] `--text` can never push the scriptSig past 100 bytes (`rebuild_script_sig`, boundary tests at `tx.rs:285-316`); `coinbaseaux.flags` is hex-decoded, never trusted as a push.
- [yolo] Equihash parameter math (`solution_len` 36 / 400 bytes, `equihash.rs:32-39`) and compact-size encoding/decoding (`codec.rs:29-59`, fixes the Perl's 65536..65556 gap, Y-F13) are correct; merkle root duplication rule correct and vector-tested against regtest block 105.
- [yolo] Payout authorization: without `--payout` the username must pass `validateaddress` and have a `scriptPubKey` (shielded addresses rejected, `stratum.rs:285-297`); with `--payout` the address is resolved once at start-up (`lib.rs:49-67`). Only `vout[0]` is rewritten; the founders/YDF output is preserved (`work.rs:110-118`).
- [yolo] Malformed stratum JSON disconnects (`stratum.rs:246-251`); no `unwrap()` on network data in the non-test paths (the four in `codec.rs` are on slices whose length was just checked); serde_json's default recursion limit (128) bounds nesting. Unknown methods disconnect.
- [yolo] `submitblock` verdicts are mapped correctly (`rpc.rs:178-184`, Y-F4 fix): only JSON `null` is "accepted"; strings and RPC errors are logged and counted, never reported as success.
- [yolo] Template refresh race: each client keeps its own `Work` (transactions included) so a submit always assembles against the job it was given; `accepted_parent`/`template_stale` stops re-issuing a built-past template (`state.rs:38-44`, `stratum.rs:202-207`, Y-F14).
- [yolo] Secrets in logs: `RpcClient`'s `Debug` omits the Authorization header (`rpc.rs:117-121`); the miner password is never logged; the cookie parser is sane.
- [yolo] Versus the Perl: nothing security-relevant was lost, and one real hole was closed — the Perl shelled out `node_rpc("validateaddress $req->{'params'}[0]")` (`ref/yolo/stratumpool:135`), a command injection via the stratum username; the Rust uses JSON-RPC over HTTP with a typed parameter (`rpc.rs:186-189`). The Perl's "say yes to everyone" authorize (`stratumsolo:97`) matches yolo's behaviour only when `--password` is unset.
- [chain-viz] Read-only by construction: all RPC wrappers in `rpc.rs:228-320` are read methods; `tests/readonly_gate.rs` greps `src/` for every §4.2 writer name; there is no RPC proxy endpoint — the UI reaches only `/api/{health,snapshot,yellowback,revenue,events}` and `/ws`. No `std::process::Command` anywhere; blocknotify is not used (ZMQ + polling only, `source/zmq.rs` treats frames as opaque hex).
- [chain-viz] Path handling: `--export`, `--record`, `--replay`, `--devnet` paths come from the CLI only; no request parameter reaches the filesystem. `/ui/{*path}` serves from an `include_dir!` embedded tree (`server.rs:136-151`), so traversal is impossible. Export writes atomically via rename.
- [chain-viz] Credential hygiene: `NodeConfig` (which carries `password`) is never serialised into a response (only `.zmq`/`.role` are read, `collector.rs:166-172`); `RpcClient::scrub` strips the node URL/host:port from transport errors (`rpc.rs:196-199`); `Debug` prints only the id; `public::redact` catches URLs, `user@host`, `host:port` and paths in every JSON/WS frame under `--public` and in every export regardless; `tests/hardening.rs::public_mode_leaks_nothing_and_rate_limits` runs the binary and asserts on it.
- [chain-viz] UI XSS: zero `innerHTML`/`insertAdjacentHTML`/`eval` in `ui/`; every panel builds DOM with `h()`/`svg()` (`ui/lib.js:8-25`) which appends strings as text nodes. `h()` does set arbitrary properties (`el[k] = v`) but the only `href` uses are the two static stylesheet links; no chain string reaches an attribute sink.
- [chain-viz] CSRF: every route is `GET` and read-only; no CORS layer, so cross-origin `fetch` cannot read responses (WS caveat in H-13).
- [chain-viz] Event bus bounds: log capped at `max` (100k) and additionally evicted by height (`bus.rs:73-78`); broadcast channel of 4096 with `Lagged` handling so a slow WS client cannot stall publishers (`server.rs:254-258`); per-node RPC concurrency semaphore (`rpc.rs:202`).
- [chain-viz] Session replay parser tolerates torn/duplicate lines without panicking (`session.rs:60-103`), input is a local file.
- [both] `Cargo.lock` committed, no git dependencies, `ureq`/`reqwest` built with rustls (no OpenSSL); dependency count within the plan's budget.

#### Not covered / needs a different auditor

- The node side of the stratum interface (`getblocktemplate` `coinbaseaux.flags` construction, `submitblock` DoS resistance in ycashd) — node auditors.
- `yolo/tests/regtest.rs` / the Python stratum miner and `yellowback_stratum.py` were not executed (no builds/runs per brief); their assertions were read only where cited above.
- chain-viz model correctness (reorg handling in `model/chain.rs`, revenue reconciliation) was skimmed for safety, not audited for accuracy — it is read-only presentation and out of the security scope here.
- The devnet scripts that write `devnet.json`/`heartbeat.json` consumed by chain-viz (ycash-dd `contrib/yellowback/devnet`) — workspace-scripts auditor.

---

### Cross-cutting: CI, supply chain, secrets, test integrity, workspace tooling — audit report

#### Summary
Covered every GitHub workflow in the nine writable repos (ycash-dd, ycash6, librustzcash6, yecwallet-dd, lightwalletd-dd, yew, yolo, chain-viz, the workspace repo), the dependency deltas of the forks against their `-legacy` baselines, the Rust/Go/Python manifests and lockfiles of the app repos, a secrets scan of every working tree and of every fork commit beyond its baseline, the integrity of the Yellowback functional-test registration and of the CI `audit` job's grep gates (dry-run in the scratchpad), the workspace `Makefile` and `scripts/*.sh`, and the ycash6 review/plan documents' pending items. Overall verdict: the supply chain is clean (zero dependency delta in both node forks and in librustzcash6; `ycash6/Cargo.toml` still pins `miodragpop/librustzcash` at `ec525fae`; every Rust component commits a `Cargo.lock` with no git dependencies; no secrets anywhere, in trees or history), no workflow in our delta uses `pull_request_target`, `workflow_run`, `issue_comment` or repository secrets, and the workspace scripts are injection-free and genuinely fast-forward-only. The findings are about test-gate integrity (a whitelist that defeats the "every script is run" check, a "blocking" step that is `continue-on-error`, variant jobs that silently SKIP two scripts) and about hardening of the CI supply chain (unpinned third-party actions, `curl | sh` rustup, an unchecksummed Go tarball, a moving `chain-viz@main` built inside the node's CI). Nothing rises above Medium.

#### Findings

##### I-1 [Severity: Medium] ycash-dd's "registered but never run" gate whitelists four existing scripts that no job runs (and four that do not exist)
- Where: ycash-dd/.github/workflows/yellowback-tests.yml:310-317 (audit job)
- Status: CONFIRMED
- Applies to: ycash-dd (ycash6 has a tighter list, see below)
- What: The check that every `qa/rpc-tests/yellowback_*.py` is run by some CI job accepts a hard-coded allow-list in addition to `$YELLOWBACK_SCRIPTS`/`$SANITIZER_SCRIPTS`. Grepping the whole workflow for each allow-listed name shows that `yellowback_reorg_stress`, `yellowback_stockparity`, `yellowback_wallet_lifecycle` and `yellowback_framework_smoke` exist in `qa/rpc-tests/` but appear in no `rpc-tests.py` invocation of any job; `yellowback_runbook`, `yellowback_rc1`, `yellowback_rc2`, `yellowback_attest_stress` are allow-listed but do not exist. `yellowback_framework_smoke.py` is additionally not registered in `qa/pull-tester/rpc-tests.py` at all (ycash-dd has no registration check; ycash6 added one at its workflow `:328`). The workflow's own comment (`:51-54`) records that exactly this pattern — "registered in rpc-tests.py but never run" — hid the v2 enforcement suite and then the whole v3 attestation suite; the gate written to prevent a recurrence has a hole the size of four scripts.
- Evidence:
  ```
  case " $YELLOWBACK_SCRIPTS $SANITIZER_SCRIPTS yellowback_attest_agent yellowback_devnet_roles yellowback_reorg_stress yellowback_stockparity yellowback_quote yellowback_runbook yellowback_rc1 yellowback_rc2 yellowback_wallet_lifecycle yellowback_framework_smoke yellowback_attest_stress " in
    *" $n "*) ;;
    *) echo "$n is in qa/rpc-tests/ but no CI job runs it"; exit 1 ;;
  ```
  Jobs that invoke scripts by name: main `:214,:222`, nightly `:607,:636,:647`, lockorder `:798`, sanitizers `:882`, coverage `:967` — none names the four. The nightly comment `:609-613` says reorg_stress "is not run" because it is still the v1 federation script.
- Scenario: `yellowback_stockparity.py` (stock-parity: the fork without `-yellowback` must be indistinguishable from stock — a soft-fork safety property) and `yellowback_wallet_lifecycle.py` (coin locking across restarts) can regress on ycash-dd with CI green. On ycash6 both are run nightly (`:653`), so the primary line is the one with the gap.
- Recommendation: Drop the names that do not exist; for the four that exist either add them to a job (ycash6's nightly shape: `yellowback_stockparity yellowback_stock_node` against a stock binary) or delete/quarantine them under a non-`yellowback_` name with a reason, so the glob gate means what it says. Add ycash6's registration check (`grep -q "'$n\.py'" qa/pull-tester/rpc-tests.py`) to ycash-dd.

##### I-2 [Severity: Low] "Rule -> test tags (blocking from Phase 6)" is `continue-on-error: true`
- Where: ycash-dd/.github/workflows/yellowback-tests.yml:392-411; ycash6/.github/workflows/yellowback-tests.yml:419
- Status: CONFIRMED
- Applies to: both
- What: The step's name says blocking, its comment says "so the loop reports until Phase 6's acceptance makes it block", and v2 Phase 6 is long delivered, yet the step carries `continue-on-error: true`. Any of the ~58 v2 rule identifiers (`MINT-*`, `RED-*`, `HALT-*`, `MINER-*`, …) can lose its tagged test without failing CI. The v3 step directly below (`:415`) is blocking.
- Evidence:
  ```
        if: ${{ !cancelled() }}
        continue-on-error: true
        run: |
          set -e
          tagged=$(grep -ho '^\(//\|#\) Rule: .*' ...
  ```
- Recommendation: Remove `continue-on-error` (fold the v2 list into the v3 loop as the comment at `:417` already suggests).

##### I-3 [Severity: Low] Variant jobs run scripts that SKIP (exit 0) without the sidecar binaries they need
- Where: ycash-dd/.github/workflows/yellowback-tests.yml:798 (lockorder), :967 (coverage); scripts qa/rpc-tests/yellowback_stratum.py:253, yellowback_chainviz.py:365; ycash6 twins (lockorder `:~900`, coverage `:~1000`)
- Status: CONFIRMED
- Applies to: both
- What: `$YELLOWBACK_SCRIPTS` includes `yellowback_stratum` and `yellowback_chainviz`, which exit 0 with "SKIP: no yolo/chain-viz binary" when `YOLO_BIN`/`CHAINVIZ_BIN` are unset. Only the `main` job builds and exports those binaries (`:177`, `:198`). In `lockorder` and `coverage` the two scripts are counted as passes but execute nothing, so the DEBUG_LOCKORDER run and the coverage floors never see the stratum/getblocktemplate path or the observer's RPC usage. (`main` is sound: there a build failure fails the job before the scripts run.)
- Recommendation: Either build the sidecars in those jobs too, or run `$YELLOWBACK_SCRIPTS` minus the two in variants and print the omission; better, make the scripts `sys.exit(1)` when a `YELLOWBACK_REQUIRE_SIDECARS=1` env is set and set it in CI.

##### I-4 [Severity: Low] Third-party actions and bootstrap tooling pinned by mutable tag or fetched unverified
- Where: ycash-dd and ycash6 `yellowback-tests.yml` (every `uses:` is `@v4`/`@v5`; rustup via `curl … https://sh.rustup.rs | sh` at ycash-dd `:151,:449,:626`; Go via `curl -sSL https://go.dev/dl/go1.24.7.linux-amd64.tar.gz | tar` at `:660` with no checksum); yecwallet-dd `jurplel/install-qt-action@v4`; yew `Swatinem/rust-cache@v2`, `subosito/flutter-action@v2`, `cargo install cargo-audit --locked` (no `--version`); chain-viz `dtolnay/rust-toolchain@stable`, `Swatinem/rust-cache@v2`, `softprops/action-gh-release@v2` (the release job has `contents: write`); workspace `.github/workflows/workspace-check.yml` `actions/checkout@v4`.
- Status: CONFIRMED
- Applies to: all components
- What: Only the inherited `ycash6/.github/workflows/release-docker-hub.yml` pins actions by SHA. Everything in our delta trusts a floating major tag. The exposure is the usual one: a compromised tag of `jurplel/install-qt-action`, `Swatinem/rust-cache` or `softprops/action-gh-release` runs with the job's token; in chain-viz's release job that token can write release assets (`permissions: contents: write`), i.e. replace the binary users download. The rustup `curl|sh` and the unchecksummed Go tarball are TLS-only trust.
- Recommendation: Pin third-party actions to full SHAs with a version comment (as release-docker-hub.yml already does), keep `actions/*` at least on tags; verify the Go tarball's sha256 (go.dev publishes it); for rustup, download the script to a file and check it against a recorded hash, or use `dtolnay/rust-toolchain` pinned by SHA. Add `dependabot`/`renovate` for actions if the pins should move.

##### I-5 [Severity: Low] The node's CI builds and executes `boyfromcave/chain-viz@main`, a moving ref, without `--locked`
- Where: ycash-dd/.github/workflows/yellowback-tests.yml:63-64, :179-199; ycash6 twin `:~215`
- Status: CONFIRMED
- Applies to: both
- What: yolo is checked out at a full commit (`YOLO_COMMIT: dc0cb249…`, on `origin/main`, built `--locked`), but chain-viz is `CHAINVIZ_REF: main` and built with plain `cargo build --release` ("Not --locked: `main` is a moving ref"). Whatever is on chain-viz `main` at the time of the run — code and whatever its unlocked resolution pulls from crates.io — executes inside the node repo's CI job. Today both repos share an owner, so this is a reproducibility and blast-radius issue rather than an exploit, but it also makes the `main` job non-reproducible and lets a chain-viz push break the node's merge gate.
- Evidence:
  ```
  CHAINVIZ_REPO: boyfromcave/chain-viz
  CHAINVIZ_REF: main
  …
          cargo build --release
  ```
- Recommendation: Pin `CHAINVIZ_COMMIT` like yolo and build `--locked`; bump by PR.

##### I-6 [Severity: Low] Nightly builds the attestor agent without `--locked`
- Where: ycash-dd/.github/workflows/yellowback-tests.yml:627 (`"$HOME/.cargo/bin/cargo" build --release`); ycash6 twin `:~690`
- Status: CONFIRMED
- Applies to: both
- What: The `agent` job (merge gate) builds, tests and clippies with `--locked`, but the nightly's "Build the attestor agent for the agent script" step does not, so the binary that `yellowback_attest_agent.py` and `yellowback_devnet_roles.py` exercise can resolve differently from the committed lock if the lock is stale. With every dependency `=`-pinned in Cargo.toml the drift surface is small, but the point of the committed lock (plan §5) is lost in exactly the job that runs the real binary end to end.
- Recommendation: `cargo build --release --locked`.

##### I-7 [Severity: Low] The attestor agent's 392-crate tree (iroh, rustls, reqwest, tokio) has no advisory scan in CI
- Where: ycash-dd/contrib/yellowback/attest/Cargo.{toml,lock}; ycash-dd/.github/workflows/yellowback-tests.yml:430-489 (agent job)
- Status: CONFIRMED
- Applies to: both
- What: The agent is the one Yellowback component that opens outbound network connections (iroh relays/gossip, HTTPS price sources) and holds an attestor signing key. Its `Cargo.lock` lists 392 packages; there is no `cargo audit`/`cargo deny` step and no `deny.toml`. yew runs `cargo audit` (`yew/scripts/audit.sh`, blocking when a fix exists); yolo and chain-viz have nothing either (yolo has no CI at all, see I-13). Advisories against iroh/rustls/ring will be seen only by hand.
- Recommendation: Copy yew's `scripts/audit.sh` pattern into the agent job (blocking on fixable advisories) and into chain-viz/yolo; add a `deny.toml` with a license/source allow-list for the agent (crates.io only, which is already true).

##### I-8 [Severity: Low] Unpinned `stable` toolchain for the two mainnet-facing binaries (yolo, chain-viz)
- Where: yolo/rust-toolchain.toml (`channel = "stable"`); chain-viz/rust-toolchain.toml (`channel = "stable"`); chain-viz release job `dtolnay/rust-toolchain@stable`
- Status: CONFIRMED
- Applies to: yolo, chain-viz
- What: The attest agent (`1.91.0`) and yew (`1.92.0`) pin an exact toolchain; yolo (the pool that builds mainnet blocks) and chain-viz (whose release job publishes binaries) build with whatever `stable` is that day. Builds are therefore not reproducible across time and a toolchain regression lands silently in a release.
- Recommendation: Pin an exact channel like the agent does, bump by PR.

##### I-9 [Severity: Low] The audit job's no-ban gates look only for `DoS([1-9]`, not for `Misbehaving(`
- Where: ycash-dd/.github/workflows/yellowback-tests.yml:317-323 and :377 (`grep 'DoS(' | { ! grep -v 'DoS(0'; }`); ycash6 twins
- Status: CONFIRMED (gap; no current violation — verified `git grep Misbehaving` in `src/yellowback`, `src/rpc/yellowback*` and in the main.cpp delta of both repos: none)
- Applies to: both
- What: N1 ("never ban a peer for a Yellowback verdict") is enforced by two greps for `DoS(`. The other ban entry point in this codebase, `Misbehaving(pfrom->GetId(), n)`, is not matched, so a future main.cpp hook or RPC that calls it directly passes the gate. Dry run in the scratchpad: `Misbehaving(pfrom, 100)` on an inserted line passes both greps.
- Recommendation: Extend both patterns to `DoS([1-9]|Misbehaving\(`.

##### I-10 [Severity: Info] Grep-gate portability and evasion notes from the dry run
- Where: ycash-dd/.github/workflows/yellowback-tests.yml:282-331 (audit job); ycash6 `:291-335`
- Status: CONFIRMED by dry run (scratchpad `audit/dry/`)
- Applies to: both
- What: (a) Every `! grep … || exit 1` now fails the step on a hit (the 2026-10-01 fix); without the `|| exit 1`, `set -e` ignores a negated pipeline (reproduced). (b) The comment-skip filter `grep -v ':[0-9]*:[[:space:]]*\(//\|\*\)'` relies on grep printing a filename prefix; it works because every invocation names ≥ 2 files (the single-file `yellowbackwallet.cpp` check does not use it). It skips any line whose first non-blank is `*` or `//`, so `* x; */ int t = GetTime();` on one line evades it — a reviewer-visible trick, not a silent one. (c) `double|float` matches identifiers (`doubled`): fail-closed false positives only. (d) `GetTime` also matches `GetTimeMillis`, which is why `yellowbackwallet.cpp` needs its own allow line. (e) All patterns are POSIX BRE/ERE and run on GNU grep; ycash6 switched the rule-tag loop to `git grep -qP` (PCRE), which needs a libpcre-enabled git — true on ubuntu-22.04 runners, not guaranteed on macOS git. None of these is exploitable; recorded so the next edit does not reintroduce (a).

##### I-11 [Severity: Info] ycash6 review document still describes the CI jobs as `if: false`; the plan's owner-action list is partly done
- Where: ycash6/doc/yellowback-review.md:679-680, :714, :916-917 ("**pending:** both CI jobs are `if: false`; no nightly run exists"); docs/plans/yellowback-ycash6-plan.md:38 and F-39 (:326)
- Status: CONFIRMED
- Applies to: ycash6
- What: `grep 'if: false'` over both workflows finds nothing (F-39 switched the seven jobs on at `8185cba3a`), and `git remote show origin` for ycash6 reports `HEAD branch: feature/yellowback`, so the owner action "set the default branch" is done and scheduled jobs can fire. The review doc's §8.4 rows 23–24 and the §4.4 table are stale on this point. Still genuinely pending and security-relevant per the review: first green scheduled runs of `lockorder`/`sanitizers`/`coverage`/`weekly-fuzz` on ycash6 (no run yet existed when the doc was scored); `yellowback_stratum.py` with a real `YOLO_BIN` on 6.20.0 (plan `:179` says it now passes with yolo `4a28eef`, but the node CI pins yolo `dc0cb24`; make them agree); `ycash-gtest TransactionBuilder*` (plan `:179` says 18 pass — review doc row 22 still PARTIAL); the lockorder allow-listed `cs_yellowback`/`ControlMutex` inversion (F-37, "structural fix is a one-line change in frozen miner.cpp" — accepted as non-deadlocking because both paths hold `cs_main`; worth a second reviewer's eye, it is consensus-adjacent). lightwalletd-dd's default branch is `master` (not the feature branch); harmless today because its workflow has no `schedule:` and the node nightlies clone the feature branch by name — but any future scheduled job there would silently run the baseline.
- Recommendation: Refresh the review doc rows; reconcile the yolo pin between the two node workflows; record the F-37 decision in the ycash6 plan's findings table with the reviewer's name.

##### I-12 [Severity: Info] Weekly fuzz job commits generated C++ and opens a PR with `contents: write`
- Where: ycash-dd/.github/workflows/yellowback-tests.yml:1018-1115; ycash6 twin
- Status: CONFIRMED
- Applies to: both
- What: The job runs with `contents: write`, `pull-requests: write`, `git add -f`s corpus files plus `src/test/yellowback_fuzz_tests.cpp` (regenerated by `gen_yellowback_corpus.py --write`), pushes a `weekly-fuzz/<date>` branch and opens a PR whose body says "no src/ change". The replay table is C++ compiled into `test_bitcoin`; its contents come from libFuzzer output. The PR path (not a direct push to the branch of record) keeps a human in the loop, and `python` job's `gen_yellowback_corpus.py --check` re-derives the table, so this is acceptable — but the PR body wording undersells what the reviewer must look at, and `git add -f` bypasses `.gitignore` deliberately.
- Recommendation: Say in the PR body that `yellowback_fuzz_tests.cpp` is regenerated code to be diffed; keep the token scope (the job needs it) but consider a `workflow_dispatch`-only approval step before push.

##### I-13 [Severity: Info] yolo has no CI of its own; its only automated run is inside the node's CI at a pinned commit
- Where: yolo/ (no `.github/`); ycash-dd workflow `YOLO_COMMIT`
- Status: CONFIRMED
- Applies to: yolo
- What: `cargo test`, clippy, fmt and any audit for the pool software run nowhere automatically; a push to yolo `main` is unchecked until someone bumps `YOLO_COMMIT` in the node repos. For software that assembles mainnet coinbases this is a completeness gap.
- Recommendation: Add the chain-viz `ci.yml` shape (fmt, build/test/clippy `--locked`) and the audit step from I-7.

##### I-14 [Severity: Info] Small credential-handling notes (no exposure found)
- Where: yecwallet-dd/src/yellowbacktab.cpp:1807-1814; ycash-dd/contrib/yellowback/devnet/yellowback-devnet:452; lightwalletd-dd/docker/cert.key, docker/zcash.conf
- Status: CONFIRMED
- Applies to: yecwallet-dd, devnet, lightwalletd-dd
- What: (a) The wallet writes `yellowback-subscribe.toml` (may contain the RPC password) with default umask and only then `setPermissions(ReadOwner|WriteOwner)` — a brief window with group/world-readable bits on a permissive umask; use `QSaveFile`/open with 0600 first. (b) The devnet passes `--rpcpassword <pw>` on the argv of the agent (visible to other local users via `ps`); regtest-only, fine for a one-laptop devnet, do not copy the pattern into mainnet docs. (c) `docker/cert.key` and `rpcpassword=notsecure` are inherited from the upstream baseline (`b7e3e50`, pre-fork) and are a self-signed test cert/sample config, not a secret of ours; they are not part of the delta. (d) `requirements.txt` cites `yellowback_fed.py and yellowback-redeem` for `requests` — both retired; `requests` is now needed only by inherited `qa/zcash/*` scripts. Stale comment.

#### Checked and found sound
- Workflow triggers in our delta: ycash-dd, ycash6, yecwallet-dd, lightwalletd-dd, yew, chain-viz, workspace — only `push`/`pull_request`/`schedule`/`workflow_dispatch`; no `pull_request_target`, `workflow_run`, `issue_comment`; no `secrets.*` beyond `github.token`; no self-hosted runners; `permissions:` blocks present on every job that writes (issues/contents/PRs) and read-only elsewhere. The `pull_request_target` (`ci-skip.yml`) and `workflow_run` (`ci-status.yml`) in ycash6 are inherited from upstream Zcash unchanged (`git diff ycash6-legacy...HEAD -- .github` adds only `yellowback-tests.yml`); ci-skip never checks out or executes PR code (fetches commits, runs `git diff --name-only` only), and the repo-name/sha pass through env vars. librustzcash6 `.github` is upstream's (zizmor, cargo-deny) at zero delta.
- Default branches (`git remote show origin`): ycash-dd and yecwallet-dd = `feature/yellowback-price-attest`, ycash6 and librustzcash6 = `feature/yellowback`, so the `schedule:` jobs in the two node workflows fire from the branch that carries them. lightwalletd-dd = `master` (no scheduled job there; noted in I-11).
- Supply chain, node forks: `git diff ycash-legacy...HEAD -- Cargo.toml Cargo.lock depends/ configure.ac rust-toolchain .cargo` is empty for ycash-dd; same for ycash6 against ycash6-legacy. `ycash6/Cargo.toml:128-134` `[patch.crates-io]` pins all six `zcash_*`/`f4jumble` crates to `miodragpop/librustzcash` rev `ec525fae828ff67af0bf5d1995acfe445340ce66`, and `Cargo.lock` resolves them to that exact rev. `librustzcash6` is zero-delta against `librustzcash6-legacy` (empty diff, no commits). The agent job asserts no `iroh` in the node's `Cargo.lock` and no agent package under `depends/packages` (`:486-489`).
- Supply chain, Go: lightwalletd-dd's only `go.mod` change promotes `github.com/btcsuite/btcutil` from indirect to direct; `go.sum` and `vendor/modules.txt` already carried it at the same pseudo-version (vendor unchanged, `-mod=vendor` builds). No new module.
- Supply chain, Rust apps: `Cargo.lock` committed in attest (both repos, identical), yew, yolo, chain-viz; no `git =`/`branch =` dependencies in any `Cargo.toml` (only intra-workspace `path`); no crate from a personal fork; attest pins every dependency with `=`; attest's `.cargo/config.toml` re-points crates.io at the sparse index to undo the node's vendored redirect (correct and documented); CI builds attest/yolo/chain-viz/yew tests `--locked`; yew has a direct-dependency allow-list (`scripts/check-deps.sh`), license check and `cargo audit`.
- Python: `requirements.txt` has lower-bound pins only (dev tooling, venv-only; bootstrap never touches system pip); the only runtime `pip install` is in CI steps (`simplejson pyzmq pyflakes`) and `scripts/bootstrap.sh` into `.venv`; the pyblake2 shim is written to user site-packages, not the repo.
- Secrets: `git grep` across all nine working trees for private-key blocks, cloud/GitHub/Slack tokens, `rpcpassword=`, hard-coded hex/WIF keys outside tests — nothing of ours (only PGP public keys, man pages, the inherited docker test cert). `git log -p <legacy>..HEAD` over all 281+63+70+7 fork commits and the full history of yew/yolo/chain-viz: no private key, token or password ever committed. No `.env`, `.cookie` or wallet files tracked.
- TLS: no `verify=False`, `_create_unverified_context`, `danger_accept_invalid_certs`, `InsecureSkipVerify` or `CERT_NONE` anywhere in our delta (ycash-dd contrib, yecwallet-dd, yew, yolo, chain-viz, lightwalletd-dd).
- Test integrity (what does hold): every `qa/rpc-tests/yellowback_*.py` is executable in both repos; the `main` job runs 19 (ycash-dd) / 23 (ycash6) scripts plus the stock baseline and the whole `test_bitcoin`; nightly refuses to run the agent/devnet-roles scripts if the binary is missing (`test -x … || exit 1`) rather than letting them SKIP; `--armed` appears only in the calibration tool, not as a test switch; the frozen-file check fetches the baseline tag explicitly and errors if it is missing; `yellowback-coverage-floor.sh` fails on any floor miss and reports absent files instead of counting them; `yellowback-lockorder-check.py` fails on any Yellowback-involving inversion except the one documented pair.
- Cache poisoning: caches are keyed on `hashFiles(depends/**)`, `Cargo.lock`, `YOLO_COMMIT`, `fetch-params.sh`; fork PRs cannot write to base-branch cache scope; nothing is uploaded as an artifact except logs, lcov and fuzz corpora.
- Workspace tooling: `Makefile`, `scripts/repos.sh`, `bootstrap.sh`, `pull.sh`, `repo-status.sh` — no `eval`, no `rm -rf` on a variable (the only `rm -rf` are on `mktemp -d` paths in lightwalletd-dd scripts and `$RUNNER_TEMP/...` literals in CI); repo paths come from the tracked `repos.yaml`; `run()` executes `"$@"` not a string; the fast-forward claim holds (`merge --ff-only` for the checked-out branch, `git fetch origin b:b` without `+` for baselines, dirty/diverged/wrong-branch trees are skipped with the command printed); `chmod -R a-w` then `u+w .git` on references, with a warning (not a silent fix) if a reference is found writable; the workspace CI re-resolves every reference pin against upstream and fails on a moved tag.
- Document/copy gates: the spec copy's header hash is checked against its body; the RPC contract JSON is byte-identical across ycash-dd, ycash6, yecwallet-dd (`cmp`); every registered `yed_*` must appear in the contract.

#### Not covered / needs a different auditor
- The content of the tests (whether each script's assertions are meaningful for the rule it tags) — assertion counts were only sampled (the lowest are `yellowback_wallet_lifecycle.py` 14, `reorg_stress` 16).
- The attestor agent's runtime behaviour (iroh transport, key storage, price-source TLS) beyond its dependency manifest.
- yew's Flutter/Dart dependency tree (`pubspec.lock`) and iOS/Android signing, which the CI explicitly leaves to the owner's machine.
- Branch-protection and required-status-check configuration on GitHub (cannot be read offline); every grep gate lives in the PR's own tree, so the gates are only as strong as the review requirement on the branch of record.
- Inherited upstream workflows in ycash6/librustzcash6 (Zcash's `ci.yml` matrix, `lints.yml`'s archived `actions-rs/clippy-check@v1`) — not our delta.
