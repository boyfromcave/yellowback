# Ycash Yellowback (YED) — lightwalletd Development Plan: a light-client relay for Yellowback

**Status (2026-09-24, revision 7). BASELINE SWITCHED — the L0–L3 code must be re-ported.**
On 2026-09-24 the owner re-created `boyfromcave/lightwalletd` as a fork of
**`yodl/lightwalletd`** (`master` `187a26765e`, 2021-07-13: `zcash/lightwalletd` 0.4.6 plus four
commits, the last adapting the transparent-address regex to Ycash's `s…`). That is the ECC
lineage, a different codebase from the yecdev/Zecwallet-derived server this plan was written
against and on which Phases L0–L3 were built and verified. The workspace is reconfigured
(`repos.yaml`, `ref/lightwalletd` re-pinned, `lightwalletd-dd` re-cloned with
`lightwalletd-legacy` = `187a267`, the mirrors updated). The delivered yecdev-based tree is
kept locally at `wt/lightwalletd-dd-yecdev-baseline` (its branches no longer exist on the
remote); §1.1, the budget table and the file-level findings F-1..F-10 describe the OLD
baseline and are superseded by the re-port survey (§10, pending). The node side (N1,
`yed_listtokens`, the devnet subcommand, `lwd-rawmint`) is unaffected; the devnet's
`lightwalletd` subcommand and the nightly step call `cmd/lwdinfo`, which the new fork does not
have until the re-port. **Next: Phase R0 (§7), the re-port.** The record below stands as the
history of what was proven on the old baseline. Previous status:
**Phases L0–L3 and N1 complete** (§7). The server has the
nineteen-method `YellowbackStreamer` incl. `GetAddressTokens`, a per-peer rate limit, edge
validation, the regtest suite (`scripts/devnet-test.sh`: the `GetBlockRange` byte-equality gate,
wallet and raw-parts mints through the server) green on a five-node devnet, the review packet
(`lightwalletd-dd/docs/review.md`) and the runbook. N1 (`yed_listtokens`) is merged into the
node's `feature/yellowback-price-attest`. The nightly step is registered in the node's workflow
and unverified until its next scheduled run. Remaining: L4 (testnet with real attestors, with
v3 Phase A7), and §9's open items — the carrier path of the raw-parts mint on an ARMED devnet.
Phase L1 record: the
`YellowbackStreamer` service is implemented (18 methods, allow-listed proxies), the offline suite
(24 cases against the contract) is green, and on a five-node regtest devnet every method answers
through the real node while the legacy binary returns `UNIMPLEMENTED` for all of them and the old
service's answers are byte-identical with the flag on and off. Next: N1 (`yed_listtokens`) and
L2 (`GetAddressTokens`, the devnet integration test). Phase L0 record: Go 1.27.1 builds and tests the
untouched baseline; the baseline binary is built from `lightwalletd-legacy`; the generator pin
(protoc-gen-go v1.3.2) reproduces both generated files; CI skeleton in place; the node's devnet
gained `lightwalletd start|stop|status` and `check` probes the server; on a five-node regtest
devnet the fork build and the baseline binary answered `GetLightdInfo`/`GetLatestBlock`
identically. Owner decisions D-L-4, D-L-7, D-L-8 and §9 Q3 taken on 2026-09-23 (§0). Next: L1
(the `YellowbackStreamer` service) and N1 (`yed_listtokens`), in parallel. Written after a survey of
`lightwalletd-dd` at its baseline (`lightwalletd-legacy` = upstream `master` `ec3b96f12`,
2020-12-06) and of the delivered Yellowback node (`ycash-dd` `feature/yellowback-price-attest`,
`rpcversion 3`). Work branch: **`feature/yellowback-price-attest`** in `lightwalletd-dd`, cut from
`lightwalletd-legacy` (workspace commit of 2026-09-23). The node and wallet plans are
[`yellowback-v2-development-plan.md`](yellowback-v2-development-plan.md) (what is on the chain)
and [`yellowback-v3-development-plan.md`](yellowback-v3-development-plan.md) (the price
attestation delta); this plan is the third fork's, and where it is silent on protocol, those two
rule. The v3 plan's open question 5 ("`lightwalletd`'s `GetAttestations` is outside both forks;
not scheduled") is what this plan schedules.

**One-line summary.** lightwalletd stays exactly what it is — a relay that light wallets already
trust for block data — and gains a **second, separate gRPC service** whose every method is a
thin, allow-listed proxy of a *read-only* `yed_*` RPC on the node it already talks to. The
existing `CompactTxStreamer` service, its protobuf file, its wire bytes and its behaviour are
**untouched**: a YecLite or mobile client built in 2020 sees a server indistinguishable from
today's. Yellowback becomes visible to a light client through the path it already uses for
transparent funds (`GetAddressTxids` + `GetTransaction`, which return the raw bytes including the
`OP_RETURN` payload) plus the new service for the three things a client cannot compute alone:
the node's **verdicts** (is this mint VOID, is this output really YED), the **price and
collateral** numbers, and the **attestation bundle** a mint or claim must carry. One node RPC is
added (`yed_listtokens`, an index read, zero consensus lines) so a server can answer "which YED
outputs sit on these addresses" for wallets it has never seen.

| Fork | Budget (lines changed in files that exist at the baseline) | Rationale |
|---|---|---|
| `lightwalletd-dd` `walletrpc/service.proto`, `walletrpc/compact_formats.proto`, `parser/*` | **0** | the wire contract old clients depend on; the parser is not on the YED path |
| `lightwalletd-dd` `frontend/service.go` | **≤ 12** (D-L-4: the address regex, optional) | every existing handler keeps its code path |
| `lightwalletd-dd` `common/common.go`, `common/cache.go` | **0** | the ingest loop is not on the YED path |
| `lightwalletd-dd` `cmd/server/main.go` | **≤ 30** | one flag, one capability probe, one `RegisterServer` call |
| `lightwalletd-dd` `go.mod` / `vendor/` | **0 new dependencies; no version bumps** (D-L-6) | six years of a working dependency set |
| `ycash-dd` `src/rpc/yellowback.cpp` (+ contract, docs) | one RPC, ≈ 80 lines | index read; `src/main.cpp`, `miner.cpp`, `policy.cpp`, `script/*`, `consensus/*`, `wallet/*`: **0** |

New files in `lightwalletd-dd` (≈ 900 lines of Go excluding generated code and tests):
`walletrpc/yellowback.proto` (+ `yellowback.pb.go`), `frontend/yellowback.go`,
`common/yellowback.go`, `frontend/yellowback_test.go`, `testdata/yellowback/*.json`, a
`docs/yellowback.md`, and `.github/workflows/yellowback-tests.yml`.

---

## 0. Revision log

### Revision 7 (2026-09-24) — baseline switched to yodl/lightwalletd; re-port scheduled

The fork's source moved (status paragraph). Design decisions D-L-1..D-L-8 stand: they were
made about *how* to add Yellowback to a lightwalletd, not about which lightwalletd. What
changes is every file-level fact: layout, entry point, RPC client, generated-code toolchain,
tests, the address regex's home, and the diff-budget rows. §10 (to be written from the survey)
lists them; Phase R0 re-ports L0–L3 file by file, keeping the same acceptance evidence (offline
suite against the contract, the byte-equality gate against a `lightwalletd-legacy` = `187a267`
binary, the devnet integration cases). Nothing from the old tree is copied blindly: each file is
re-derived against the new baseline's conventions, and the old tree is a reference only.

### Revision 6 (2026-09-24) — Phases L2 and L3 executed

L2: `GetAddressTokens` (proto, handler, allow-list, offline cases); the regtest suite
(`frontend/yellowback_devnet_test.go`, `scripts/devnet-test.sh`) with the byte-equality gate
over every `CompactBlock`, the wallet-mint and raw-parts-mint cases (the mint assembled by
`ycash-dd/contrib/yellowback/devnet/lwd-rawmint` from numbers the server gave); the nightly step
in the node's workflow. Three harness lessons in mapping §15: the devnet's RPC URL embeds
credentials that are not URL-safe (use the port); `yed_mint` blocks for the carrier's block and
btcd's `rpcclient` serialises HTTP POSTs, so the miner needs a second client; a server's cache
is empty for a few seconds after start. L3: the per-peer token bucket on the four node-work
methods, edge validation recorded, `-race` and `staticcheck` run (baseline findings only, none
changed), `docs/review.md`, the runbook and upgrade order, one README line. The §6.3 item
"restart the node without `-yellowback`" is not automated (the devnet has no node-0 restart);
the probe's behaviour on a stock node is covered offline (`TestProbe`) and by D-L-5's startup
path. The armed-devnet carrier path of the raw mint is an open item (§9 Q6).

### Revision 5 (2026-09-24) — Phase N1 executed

`yed_listtokens <addresses> [minHeight]` landed in `src/rpc/yellowback.cpp` (+66 lines, one
registration row), with two `client.cpp` conversion rows, a `doc/yellowback-rpc.md` section and
two error rows (`too-many-addresses`, `invalid-address`), the contract regenerated by `make spec`
into all three copies, a `yellowback_rpc_contract.py` case (equality with `yed_listunspent` on
the wallet's own addresses in both address forms, the `minHeight` cut, the two errors) and a
`yellowback_index.py` case (every enforcing node's `yed_listtokens` equals each wallet node's
`yed_listunspent`). Both scripts green on regtest; frozen files at zero delta vs
`feature/yellowback-sf`. The model's `tokens_by_script()` was not added: the index case already
compares the node-context scan with the wallet's `IsMine` view of the same `Tokens` records, and
the model's state hash covers the records themselves. Done in a worktree because the main
`ycash-dd` tree carried the owner's uncommitted lock-order work. Two compile lessons in mapping
§15 (`Params` is ambiguous inside `src/rpc/`, `CTxDestination` is a `std::variant`).

### Revision 4 (2026-09-23) — Phase L1 executed

L1's seven items are done and checked in §7; `lightwalletd-dd/docs/yellowback.md` carries the
evidence and the diff actuals. Two deviations from the text, both recorded: `frontend/service.go`
changed 17 lines, not 12 — the D-L-4 conversion plus the F-1 guard plus a package-level switch
(the baseline handler has no place to hang a flag without changing its constructor); `go.mod`
gained one line, promoting `btcutil` (already in `go.sum` as an indirect dependency, same version)
to a direct requirement for its base58 package. Hex values stay strings in the proto (`hex`,
`txid`, as the contract) rather than `bytes`, so the JSON result unmarshals without a decode step.
`YellowbackInfo.params` carries a typed subset of the node's parameter block. The devnet's
`lightwalletd` subcommand records the server's extra flags and `check` runs the eighteen-method
probe when `-yellowback` is among them.

### Revision 3 (2026-09-23) — Phase L0 executed

L0's five items are done and checked in §7; `lightwalletd-dd/docs/yellowback.md` is the record.
Findings: F-6 was wrong (`TestBlockParser` passes at the baseline; the fixture is not missing);
new F-8 (a `go vet` finding in `bytestring.ReadByte`; CI vets with `-stdmethods=false`), F-9
(`vendor/` is stale against `go.mod`, so builds resolve through `go.sum`, never `-mod=vendor`;
left alone under D-L-6), F-10 (`GetLatestBlock` returns an empty hash, baseline behaviour). The
generated-code gate masks the gzipped descriptor block, which changes with the protoc release
while the Go API does not (D-L-6 refined). The devnet's `lightwalletd` subcommand writes its own
four-key conf beside node 0's `ycash.conf`, and node 0 now starts with `-insightexplorer -txindex`.
Testing on regtest only; the running role-session devnet was never touched (a second devnet,
`--dir ~/yb-devnet-lwd --portseed 8`).

### Revision 2 (2026-09-23) — owner decisions, regtest rule, context trimmed

The product owner confirmed the recommended answers: **D-L-4** (the server converts `ye…`/`yt…`/
`yr…` addresses itself; the one edit to `frontend/service.go`), **D-L-7** (`yed_listtokens` is
added to the node now, Phase N1), **D-L-8** (only F-1 is fixed; the other baseline findings are
recorded), and **§9 Q3** (a mempool view stays out of scope). D-L-1, D-L-2, D-L-3, D-L-5 and
D-L-6 follow from the prime directive and stand as written. §6.1 now states the testing rule
explicitly: `lightwalletd-dd` is tested against a regtest `ycash-dd` the same way `yecwallet-dd`
is, and no phase is accepted on the offline suite alone. Pre-fork history of the server was
removed from §1.1, D3, §8 and Appendix A: the baseline commit is the only input.

### Revision 1 (2026-09-23) — first draft

Written from two surveys: the server (§1.1) and the node's on-chain footprint and RPC surface
(§1.2). The owner decisions this plan needs are listed in §2 as D-L-1..D-L-8 with the
recommended answer applied in the text; each is reversible by a one-line change until its phase
starts.

---

## 1. The decision in one page

### 1.1 What `lightwalletd-dd` is at the baseline

`lightwalletd-dd` is a Go gRPC server between light wallets and `ycashd`: nine non-vendor Go
files, ≈ 1,100 lines, `go 1.12`, an in-memory compact-block cache, transparent-address support.
It is the backend of **YecLite** (`yecdev/YecLite`) and the yecdev mobile wallet, and has been
in service unchanged since 2020 — the last commit, `ec3b96f`, is the one regular expression that
makes `GetAddressTxids` accept `s…` addresses (`frontend/service.go:81-88`). Its history before
that is not an input to this plan; the baseline is what it is.

What it does, and therefore what must not change:

| Surface | Where | What a client depends on |
|---|---|---|
| gRPC service `cash.z.wallet.sdk.rpc.CompactTxStreamer` | `walletrpc/service.proto:62-80` | seven methods: `GetLatestBlock`, `GetBlock`, `GetBlockRange`, `GetTransaction`, `SendTransaction`, `GetAddressTxids`, `GetLightdInfo`; field numbers of `BlockID`, `BlockRange`, `TxFilter`, `RawTransaction{data, height}`, `SendResponse`, `LightdInfo{version, vendor, taddrSupport, chainName, saplingActivationHeight, consensusBranchId, blockHeight}` |
| Compact formats | `walletrpc/compact_formats.proto:12-48` | `CompactBlock`, `CompactTx{index, hash, fee, spends, outputs}`, `CompactSpend{nf}`, `CompactOutput{cmu, epk, ciphertext}` |
| What a compact block contains | `parser/block.go:101-119`, `parser/transaction.go:307-322` | **only Sapling spends and outputs**; a transaction with no Sapling component is dropped from the block; **every transparent vin and vout, and every `OP_RETURN`, is dropped** |
| Node RPCs called | `common/common.go:19-95`, `frontend/service.go:91-97, 326, 356-360, 456` | `getblockchaininfo`, `getblock <height> 0`, `getrawtransaction` (twice per tx), `getaddresstxids` (needs `insightexplorer=1 txindex=1`), `sendrawtransaction` |
| Configuration | `cmd/server/main.go:118-127`, `frontend/rpc_client.go:17-22` | `-bind-addr`, `-tls-cert/-tls-key/-no-tls`, `-log-level/-log-file`, `-conf-file` (RPC credentials read from the node's conf), `-cache-size`, `-params-port`, `-metrics-port` |
| Build | `build.sh`, `docker/Dockerfile` | static `go build`, `FROM scratch` image; vendored dependencies; no CI, no tests outside `parser/` |

### 1.2 What Yellowback puts on the chain, seen from a light client

Everything a light client needs is in the v2/v3 plans and `docs/spec/yellowback-spec.md`; the
facts that decide this plan's shape:

- **YED is a colored-output overlay on ordinary transparent P2PKH outputs.** No new transaction
  version (`nVersion` stays 4), no new serialisation, no new opcode. A Yellowback transaction is
  an ordinary v4 transaction with exactly one `OP_RETURN <4..80 bytes>` whose data begins `"YB"
  ‖ 0x03 ‖ type` (`ycash-dd/src/yellowback/payload.h:21-35`, spec §3.3). The baseline parser
  handles every one of them today (`parser/transaction.go:324-470` never interprets a script).
- **A light client cannot decide from a UTXO alone whether it is YED.** `TOKEN_VALUE` = 10,000
  zat is a hint, not a rule: whether `txid:vout` carries cents depends on the transaction's
  verdict (MINT-1..10, XFER-1..3, RED-1..5), which depends on the price snapshot at `refHeight`,
  the attestation bundle, and whether its inputs were themselves tokens. The node's index
  (`Tokens`, `Vaults`, `TxLog`, spec §3.6) is the answer; the 2,960-line
  `qa/rpc-tests/test_framework/yellowback_model.py` is the only other implementation and is
  not something a phone should run.
- **Confirmed YED activity is already reachable by a light client.** Compact blocks carry no
  transparent data, but YecLite-lineage clients track transparent addresses through
  `GetAddressTxids` and fetch each transaction raw through `GetTransaction` — bytes that include
  the payload and every output. The server already does what a YED client needs for *history*;
  what it lacks is *judgement* and *price*.
- **Building a mint or a claim needs the node.** `ATTEST_REQUIRED = true` on mainnet: the
  transaction spends a carrier whose scriptSig holds a bundle of attestor signatures
  (`yed_buildbundle`), the collateral is `requiredZat` at the reference height
  (`yed_estimatecollateral`), and the bundle comes from the node's in-memory attestation pool —
  "light clients cannot gossip; `lightwalletd` gains `GetAttestations`"
  (`docs/reference/yellowback-price-attestation.md:818`). A TRANSFER needs none of this: YED
  inputs, `TOKEN_VALUE` outputs, a payload — the client can build it, but should ask the node to
  **dry-run** it (`yed_validaterawtransaction`) first, because a malformed transfer burns.
- **The read-only `yed_*` set is exactly the light-client surface.** Twenty-five node-context
  RPCs registered without a wallet (`ycash-dd/src/rpc/yellowback.cpp:1832-1856`), with a
  machine-readable contract (`doc/yellowback-rpc-contract.json`, `rpcversion 3`) that already
  drives YecWallet's offline tests. The **one gap**: nothing returns the YED outputs of an
  *arbitrary* address — `yed_listunspent` is wallet-scoped, `yed_gettxinfo` is by txid.
- **YED addresses are transparent addresses with a different prefix.** `ye…` (mainnet), `yt…`,
  `yr…` decode to the same 20-byte key hash as `s1…` (`ycash-dd/src/yellowback/address.h:14-21`);
  the prefix is a UX guard, not a script type.

### 1.3 The design

**D1. A second service, not a bigger one.** `walletrpc/yellowback.proto` declares
`cash.z.wallet.sdk.rpc.YellowbackStreamer`, registered on the same gRPC server as
`CompactTxStreamer`. Protobuf and gRPC are additive by construction: a client that does not know
the new service never sends its method names; a new client against an old server gets
`UNIMPLEMENTED` and falls back. `service.proto` and `compact_formats.proto` are not edited — not
even to add an optional field to `LightdInfo`, because the *existence* of Yellowback support is
answered by the new service's own `GetYellowbackInfo` (§4.1) and a diff of the old files is the
easiest thing for the Ycash maintainers to check.

**D2. Every method is a proxy of a read-only node RPC, from an allow-list.** The server holds no
Yellowback state, runs no Yellowback logic, and decodes nothing it does not have to: it forwards
the JSON-RPC result into a protobuf message with the same field names. The allow-list (§4.2) is
a Go map; anything not in it — every wallet RPC, `yed_setquote`, `yed_addattestation` — is
unreachable through the server by construction, not by omission.

**D3. Compact blocks stay as they are.** Adding transparent outputs to `CompactTx` would change
the bytes of every block served and make every client re-scan — the opposite of the prime
directive. History stays on `GetAddressTxids`; judgement
comes from the new service.

**D4. One node RPC, `yed_listtokens`, so the server can answer any address.** An index scan of
the `K` (Tokens) prefix filtered by scriptPubKey (§4.4). Node-context, read-only, no consensus
file touched, added to the contract like every other RPC. Until it lands (Phase L1 runs before
it), the server answers YED balances for *transactions* (`GetTxInfo`) but not for *addresses*.

**D5. Off by default; capability-probed.** The service registers only when `-yellowback` is
passed **and** the node reports `"yellowback"` in `getinfo.experimentalfeatures` and a
`yed_getinfo.rpcversion` the server knows (3). A server without the flag, or on a stock Ycash
node, is the baseline binary in every observable way.

**D6. Client-side building is the client's job; this plan fixes the contract it builds against.**
Signing a vault owner path, a carrier, or a transfer is done with the client's own keys — the
node's wallet is never involved, which is why a light client can mint at all. §5 states what the
client must implement, so the YecLite/mobile work can be scheduled against this server.

### 1.4 What this gives a light client, by tier

| Tier | Server work | What a client can do | What it cannot |
|---|---|---|---|
| **L0** (today, no change) | none | see YED transactions on its addresses (raw bytes), decode payloads, show *provisional* YED balances (the wallet's `PreLock` rule, `ycash-dd/src/yellowback/wallet.cpp:410-427`), broadcast anything | know a mint was VOID, know an output is really YED after a reorg or a burn, know the price, build a mint or claim |
| **L1** (Phase L1–L2) | `YellowbackStreamer` proxying the existing read-only set | everything above plus: verdict per transaction, price and collateral, dry-run before broadcast, bundle and selection for a mint or claim, vault status, attestor list | confirmed YED balance of an address it has not seen every transaction of |
| **L2** (Phase L3, needs `yed_listtokens`) | + `GetAddressTokens` | authoritative YED UTXO set per address — restore from seed, balance after reorg | — |
| **L3** (out of scope here; §5) | — | YecLite / mobile: `ye…` addresses, the two-step mint, claim, transfer | — |

---

## 2. Decision record

### D-L-1. Separate service, zero edits to the existing `.proto` files (recommended, applied)
Alternative: add methods to `CompactTxStreamer`. Wire-compatible too, but it puts Yellowback in
the file every client vendors and makes "what changed for old clients" a diff to read rather than
`git diff --stat` showing `0`. **Given up:** one `LightdInfo.yellowbackSupport` boolean; clients
probe `GetYellowbackInfo` instead.

### D-L-2. Proxy, not indexer (recommended, applied)
Alternative: port `yellowback_model.py` to Go and let the server judge transactions itself, so a
client's view would not depend on the node's `-yellowback` index. Rejected: a third
implementation of the state machine (after C++ and Python) is the largest possible footprint and
the largest possible source of disagreement between what a phone shows and what enforcing miners
apply; the node's index is rebuildable and audited (v2 §7). The server trusts its node exactly as
it does for `getaddresstxids`.

### D-L-3. Allow-list, typed messages, no generic passthrough (recommended, applied)
Alternative: one `CallYed(method, jsonParams) → jsonResult` method. Smallest code, but it makes
the server's exposure equal to the node's read-only surface *forever*, including RPCs added later
that this plan has not reviewed, and gives clients no schema. Each method is typed; adding one is
a deliberate, reviewable proto change.

### D-L-4. The address regex admits `ye…`/`yt…`/`yr…` and maps them to `s…` (owner decision 2026-09-23: yes; the one edit to `service.go`)
`GetAddressTxids` validates with `^s[a-zA-Z0-9]{34}$` and splices the string into the RPC call
(`frontend/service.go:81-93`). A YED-aware client holds `ye…` addresses whose key hash is an
`s1…`; it can convert client-side, so this is optional. Recommended anyway, ≤ 12 lines, because
it lets a client pass what it displays and because the conversion (base58check, version bytes
`0x1FE4 → 0x1C28`) is one place to get right instead of one per client. **Owner decision:** do it
in L1, or leave it to clients. **Decided: do it**, in L1, behind the same `-yellowback` flag, so
the baseline regex path is byte-identical when the flag is off.

### D-L-5. Off by default, capability-probed at startup (applied)
`-yellowback` flag; probe `getinfo.experimentalfeatures` and `yed_getinfo.rpcversion`; refuse to
start the service (log at error, keep serving the old service) on a stock node or an unknown
`rpcversion`. A server can therefore be upgraded ahead of its node with no change in behaviour.

### D-L-6. No dependency changes; generated code from the vendored generator (applied)
`go.mod` says `go 1.12`, `github.com/golang/protobuf v1.3.2`, `google.golang.org/grpc` as
vendored. Modern Go builds this module unchanged (the `go` directive is a language floor, not a
toolchain pin). New `.pb.go` files are generated with the vendored `protoc-gen-go` so the two
generated files in the repo agree on API generation; the exact `protoc` and plugin versions are
recorded in `docs/yellowback.md` and checked by CI regenerating and diffing. **Given up:** the
newer `google.golang.org/protobuf` API and its niceties.

### D-L-7. `yed_listtokens` is added to the node in this plan, not deferred (owner decision 2026-09-23: yes, Phase N1)
Without it a restored-from-seed light wallet can only reconstruct its YED balance by replaying
every transaction on its addresses through `GetTxInfo` — correct but O(history) round trips and
still blind to tokens created by transactions it never saw. One RPC, read-only, ≈ 80 lines in
`src/rpc/yellowback.cpp`, a contract entry, a functional test. Scan cost: the `K` prefix is the
live token set (spent tokens are erased by IN-1), so a full scan is O(live tokens); a secondary
index by script hash is deferred until measured (§9 Q2).

### D-L-8. Pre-existing server defects are fixed only where the Yellowback path crosses them (owner decision 2026-09-23: F-1 only)
The survey found several (§8, F-1..F-7): a panic on an RPC error string without a colon in
`SendTransaction` (`frontend/service.go:465`), unchecked type assertions in `GetSaplingInfo`
(`common/common.go:41-50`), an unstoppable ingestor (`common/common.go:158-159`), the missing
`testdata/blocks` fixture. Only F-1 is on the YED path (a rejected YED transaction's error
string) and is fixed in L1 with a test. The rest are recorded, not touched — the same rule as
node rule 7: do not tidy what you are not porting.

---

## 3. Protocol: what the server relays (normative for the server; the node plans are normative for the chain)

The server adds **no rule**. This section fixes the mapping from node RPC to gRPC message so the
two forks' contracts stay one contract (v3 plan §4.7: "the `yed_*` RPC surface is the sole
interface").

### 3.1 Naming
gRPC service `cash.z.wallet.sdk.rpc.YellowbackStreamer` in package `walletrpc`, file
`walletrpc/yellowback.proto`. Message names are `Yed…` for amounts and `Yellowback…` for the
system (AGENTS.md rule 6). Field names are the JSON names of the contract, unchanged, so the
contract JSON's example values are the fixtures (§6.2).

### 3.2 Units
`cents` (`uint64`, 1 YED = 100 cents), `…Zat` (`int64`), `…MicroUsd` (`uint64`), heights
`uint32` — as the contract. The server never converts, rounds or formats.

### 3.3 Errors
A node RPC error is returned as gRPC status `FAILED_PRECONDITION` with the node's error
identifier (`bundle-insufficient`, `vault-locked`, … — the contract's `errors` table) as the
status message, verbatim. Transport failures to the node are `UNAVAILABLE`. A method the server
does not offer (flag off, stock node) is `UNIMPLEMENTED` — which is what an old server returns,
so a client has one code path for "no Yellowback here".

### 3.4 Versioning
`GetYellowbackInfo.rpcversion` is the node's; `GetYellowbackInfo.serverVersion` is this fork's
(`"0.2-yec-lightwalletd"`; the baseline reports `"0.1-yec-lightwalletd"` in `LightdInfo.version`
and that string does **not** change). A client refuses an `rpcversion` it does not know, exactly
as YecWallet does (`mapping.md` §12).

---

## 4. Architecture

### 4.1 `YellowbackStreamer` — the methods

| gRPC method | Node RPC (read-only) | Purpose for a light client |
|---|---|---|
| `GetYellowbackInfo(Empty) → YellowbackInfo` | `yed_getinfo` | is Yellowback enabled/active/enforcing/armed; `rpcversion`; params; `network`; `height` vs `chainHeight` (index lag) |
| `GetPrice(HeightFilter) → YedPrice` | `yed_getprice [height]` | `pMint`, `pClaim`, `pFast/pMid/pSlow`, `xMint/xClaim`, `seated`, `pinnedSeqs`; the display price |
| `GetStats(Empty) → YellowbackStats` | `yed_getstats` | supply, collateral, ratio, vault counts |
| `GetTxInfo(TxFilter) → YedTxInfo` | `yed_gettxinfo <txid>` | **the verdict**: `type`, `verdict`, `assigned[]{vout, cents}`, `spentTokens[]`, `closedVaults[]`, `burned`, `yedIn/yedOut`, `expired`, `height` |
| `ValidateRawTransaction(RawTransaction) → YedValidation` | `yed_validaterawtransaction <hex>` | **dry run before `SendTransaction`**: `valid`, `verdict`, `burned`, `wouldBeRejected`, `unconfirmedInputs[]` |
| `DecodePayload(Bytes) → YedPayload` | `yed_decodepayload <hex>` | optional convenience; clients may decode locally |
| `GetVault(TxFilter) → YedVault` | `yed_getvault <txid>` | status, `lockHeight`, `claimHeight`, `claimable`, `noticed`, `underwaterAt`, `sweepBefore` |
| `ListVaults(VaultFilter) → stream YedVault` | `yed_listvaults [status] [count] [skip]` | explorer-style listing; paginated as the RPC is |
| `ListClaimable(Empty) → stream YedVault` | `yed_listclaimable` | the liquidator persona of the role-based regtest plan, on a phone |
| `EstimateCollateral(YedMintQuery) → YedCollateralEstimate` | `yed_estimatecollateral <cents> <lockBlocks> [priceMicroUsd]` | `requiredZat`, `lockHeight`, `claimHeight`, `refHeight`, `termClass`, `source`, `bundleSeqs`, `attestFeeZat` |
| `EstimateFee(YedFeeQuery) → YedFeeEstimate` | `yed_estimatefee` | enforcement-fee amount and payee for a given collateral |
| `GetFeePayee(YedPayeeQuery) → YedPayee` | `yed_getfeepayee` | the fee output's address for `(refHeight, selector)` |
| `BuildBundle(YedBundleQuery) → YedBundle` | `yed_buildbundle <refHeight> <selectorHex>` | **the carrier step**: `hex`, `seqs`, `selected`, `missing`, `aMint`, `aClaim`; error `bundle-insufficient` |
| `GetSelection(YedBundleQuery) → YedSelection` | `yed_getselection` | "3 of 6 selected attestors reachable" |
| `GetAttestations(Empty) → stream YedAttestation` | `yed_getattestations` | the pool: `seq, price, citedHeight, receivedHeight, seated` — the `GetAttestations` the proposal names; a client verifies every signature against the seated set (§5) |
| `ListAttestors(HeightFilter) → stream YedAttestor` | `yed_listattestors [height]` | the seated set and bond addresses |
| `GetNotice(TxFilter) → YedNotice` | `yed_getnotice <vaultTxid>` | claim-notice state of a vault |
| `GetActivation(Empty) → YellowbackActivation` | `yed_getactivation` | signalling / lock-in / active |
| `GetAddressTokens(AddressList) → stream YedToken` | **`yed_listtokens <addresses…>`** (new, §4.4) | **the authoritative YED UTXO set** of the client's addresses: `txid, vout, cents, nValue, height, address` |

Not offered, by allow-list: every wallet RPC (`yed_mint`, `yed_send`, …, they need the node's
keys), `yed_setquote` (miner-local state), `yed_addattestation` and `yed_signattestation`
(RPC-auth only, v3 §4.5), `yed_getstatehash`/`yed_gethistory`/`yed_getblockverdict`/`yed_gettag`/
`yed_listminers` (test and operator tooling; nothing a wallet shows), `yed_getselection`'s
cousin `yed_getbundle…` variants that do not exist. Adding one later is a proto change and a row
here.

### 4.2 Modules (`lightwalletd-dd`)

| File | Content | Size |
|---|---|---|
| `walletrpc/yellowback.proto` | the service and messages of §4.1; `import "compact_formats.proto"` for nothing — it reuses `Empty`, `TxFilter`, `RawTransaction` from `service.proto` by `import "service.proto"` (read-only import; the file is not edited) | ≈ 250 |
| `walletrpc/yellowback.pb.go` | generated (D-L-6) | generated |
| `common/yellowback.go` | `ProbeYellowback(client) (YellowbackCapability, error)`: `getinfo` → experimental features contains `"yellowback"`; `yed_getinfo` → `rpcversion == 3`, `network`; the `RawRequest` helpers `callYed(method, params...) (json.RawMessage, error)` that map a `btcjson.RPCError` to `codes.FailedPrecondition` with the node's message; the **allow-list** `var yedMethods = map[string]bool{…}` consulted by `callYed` — the only function that can reach a `yed_*` RPC | ≈ 120 |
| `frontend/yellowback.go` | `type YellowbackStreamer struct{…}` implementing the generated interface; one function per method, each ≤ 20 lines: validate input, `callYed`, `json.Unmarshal` into the proto message with the standard library — the generated structs carry `json:"<contractName>,omitempty"` tags (`walletrpc/service.pb.go:30-31`), and `jsonpb` is **not** vendored (`vendor/github.com/golang/protobuf/` has `proto`, `ptypes`, `protoc-gen-go` only), so no new dependency (D-L-6); `bytes` fields that the contract gives as hex (`hex`, `txid`) are decoded explicitly — return | ≈ 400 |
| `frontend/yellowback_addr.go` | (D-L-4) `yedToTransparent(addr string) (string, bool)`: base58check decode with the vendored `btcutil/base58`, version bytes `{0x1F,0xE4}→{0x1C,0x28}` (mainnet `ye`→`s1`), `{0x20,0x07}→{0x1C,0x95}` (testnet `yt`→`sm`), `{0x20,0x02}→{0x1C,0x95}` (regtest `yr`→`sm`) — the node's `ycash-dd/src/yellowback/params.cpp:142,156,189` and `ref/ycash/src/chainparams.cpp:149,409,613` (`base58Prefixes[PUBKEY_ADDRESS]`) are the source of the constants and the unit test pins them against `yed_validateaddress`'s `transparentAddress` | ≈ 60 |
| `cmd/server/main.go` | `-yellowback` flag; after `GetSaplingInfo`: `if opts.yellowback { cap, err := common.ProbeYellowback(rpcClient); … walletrpc.RegisterYellowbackStreamerServer(server, frontend.NewYellowbackStreamer(rpcClient, cap)) }`; log one line either way | ≤ 30 changed |
| `frontend/service.go` | (D-L-4 only) in `GetAddressTxids`: `if s.yellowback { if t, ok := yedToTransparent(addr); ok { addr = t } }` before the existing regex | ≤ 12 changed |
| `frontend/yellowback_test.go` | offline tests against a fake node (§6.2) | ≈ 400 |
| `testdata/yellowback/contract.json` | a copy of `ycash-dd/doc/yellowback-rpc-contract.json`, kept identical by `make spec` (§6.4) | copy |
| `docs/yellowback.md` | operator guide: node flags (`experimentalfeatures=1 yellowback=1 insightexplorer=1 txindex=1`), the flag, the probe, the method table, the client contract (§5), the generator versions (D-L-6), the devnet recipe | ≈ 200 |
| `.github/workflows/yellowback-tests.yml` | `go vet ./...`, `go test ./...`, `go build`, regenerate-and-diff the `.pb.go`, contract equality; a nightly devnet job when a built `ycash-dd` is available (§6.3) | ≈ 120 |

### 4.3 What the server does at startup, with the flag

```
getinfo                      → experimentalfeatures ∋ "yellowback"?   no → log, serve baseline only
yed_getinfo                  → rpcversion == 3? network == chainName?  no → log, serve baseline only
RegisterYellowbackStreamerServer
```

Nothing else changes: the ingestor, the cache, `GetSaplingInfo`, the metrics and params servers
are untouched. The probe runs once; a node restarted without `-yellowback` mid-flight makes every
YED method return `FAILED_PRECONDITION` with the node's "Yellowback disabled" message, which is
the node's own answer relayed.

### 4.4 The node change: `yed_listtokens` (`ycash-dd`)

```
yed_listtokens <addresses> [minHeight]
  addresses   JSON array of transparent (s1…/sm…) or YED (ye…/yt…/yr…) addresses, 1..100
  minHeight   only tokens created at or above this height (default 0)
→ [{ txid, vout, cents, nValue, height, address (the YED form), transparentAddress }]
   sorted by (height, txid, vout); node context; error `too-many-addresses` above 100
```

Implementation: `view.h`'s Tokens record already stores `scriptPubKey` and `height`; the RPC
decodes each address to a `CKeyID`, builds the set of `P2PKH` scripts, iterates the `K` prefix
(`YellowbackWallet::AllCoins()` at `ycash-dd/src/yellowback/wallet.cpp:364-381` shows the
iteration, minus `IsMine`), and keeps matches. ≈ 80 lines in `src/rpc/yellowback.cpp`, one
row in `doc/yellowback-rpc.md`, one contract entry with example values, one case in
`qa/rpc-tests/yellowback_rpc_contract.py`, and a case in `yellowback_index.py` that mints,
transfers, redeems and checks `yed_listtokens` against `yed_listunspent` on the owning node and
against the model. Files touched: `src/rpc/yellowback.cpp`, `doc/yellowback-rpc.md`,
`doc/yellowback-rpc-contract.json` (regenerated), two test scripts. Frozen files: zero delta.
**This is the whole node footprint of this plan.**

### 4.5 What does not change in the node
No `-lightwalletd` interplay: Ycash 4.5.0's own `-lightwalletd` experimental flag only gates
`getblockdeltas`/`getblockhashes` (`ref/ycash/src/rpc/blockchain.cpp:417,500`) and this server
calls neither. The server's node needs `insightexplorer=1 txindex=1` as today, plus
`experimentalfeatures=1 yellowback=1` (and `yellowbackenforce=0` — a relay's node has no reason
to enforce, and enforcement changes which chain the node follows, v2 §3.9). `yellowback_stock_node.py`
already proves a `-yellowback` node and a stock node follow the same chain, so a server operator
who turns the flag on serves the same blocks as before.

---

## 5. The client contract (for YecLite / mobile; out of this plan's scope, in its interface)

A YED-capable light client, built against this server, must:

1. **Detect** Yellowback: `GetYellowbackInfo` (fallback on `UNIMPLEMENTED`); refuse an unknown
   `rpcversion`; show nothing YED-related unless `enabled && activation.status == "active"`.
2. **Address**: derive `ye…` from its own transparent keys (same key hash; version bytes §4.2);
   show YED balances only for outputs it has confirmed through `GetAddressTokens` (authoritative)
   or, before that lands, `GetTxInfo.assigned` for every transaction on its addresses. The
   `PreLock` rule (MINT ⇒ `vout[1]`, TRANSFER/REDEEM ⇒ the payload's assignments) may label
   *unconfirmed* outputs "pending YED", never "YED".
3. **Payload**: decode `"YB" ‖ 0x03 ‖ type` locally (spec §3.3) for display; never treat a
   decoded payload as a verdict.
4. **Transfer**: select YED inputs from `GetAddressTokens`, build `TOKEN_VALUE` P2PKH outputs
   and the TRANSFER payload (spec §3.5), pay the miner fee from YEC inputs, call
   `ValidateRawTransaction` and **refuse to broadcast unless `valid && verdict == "ok" &&
   burned == 0`**, then `SendTransaction`. This one check is what stands between a client bug
   and a burn.
5. **Mint** (two transactions, v3 §3.5): `EstimateCollateral(cents, lockBlocks)` → `refHeight`,
   `requiredZat`; `BuildBundle(refHeight, selector)` → `hex`; carrier funding transaction paying
   `P2SH(carrierScript(freshKey, SHA256(bundle)))` of `CARRIER_VALUE`; wait one confirmation
   (`GetTxInfo` or `GetTransaction.height`); main transaction per the MINT template with
   `vin[last]` the carrier (scriptSig `<bundle> <sig> <carrierScript>`), `vout[0..4]` as spec
   §3.5, `nExpiryHeight = refHeight + REF_WINDOW`; `ValidateRawTransaction`; `SendTransaction`.
   If the window lapses, sweep the carrier (the client owns its key).
6. **Redeem / claim**: owner path needs only the client's own key and `nLockTime = lockHeight`;
   claim path needs a bundle (carrier as in 5) and `nLockTime = claimHeight`. Verify the bundle
   it is handed: every attestation's compact ECDSA signature against the pubkey of its `seq` in
   `ListAttestors` (the proposal's "the server is a relay it cannot lie through — only withhold").
7. **Trust statement**, shown once: the server relays the node's verdicts and prices; it can
   withhold or show a stale view, and it can misreport a verdict — which affects what the wallet
   *displays*, never what the chain *applies*; the dry run is advice, the chain is the judge.

The v1 archived plan put YecLite out of scope (`archived/yellowback-v1-development-plan.md:1475`)
"because redemption would still need the user's node for signing" — that was the federation
design. Under v2/v3 every signature is the owner's own key over scripts the client can construct,
so the objection no longer holds; this section is the evidence.

---

## 6. Testing

### 6.1 Principles
`lightwalletd-dd` is tested **the same way `yecwallet-dd` is**: an offline suite driven by the
node's RPC contract for every method, and a **regtest** suite that runs the real server against a
real `ycash-dd` regtest network — the same devnet (`yellowback-devnet up`) and the same
`yellowback-sim` economy the wallet's devnet QTest case and the nightly
`yellowback_devnet_roles.py` use (mapping §12, `role-based-regtest-plan.md`). Every phase's
acceptance names its regtest evidence; nothing is "done" on the offline suite alone. The baseline
has parser tests only (`parser/*_test.go`, `testdata/`), nothing for `common/`, `frontend/` or
`cmd/`, and no CI. This plan adds tests for what it adds and **one regression gate for what it
must not change**: byte equality of the old service's answers, before and after, on that regtest
chain.

### 6.2 Offline: fake node, contract fixtures
`frontend/yellowback_test.go` starts an `httptest.Server` answering JSON-RPC from
`testdata/yellowback/contract.json`'s example values (the same trick as YecWallet's
`yellowbacktab_test.cpp`, mapping §12): every method of §4.1 gets a case that calls the gRPC
handler and asserts the proto fields equal the contract's example; every documented error
identifier gets a case asserting `FAILED_PRECONDITION` with that message; the allow-list gets a
case that every `yed_*` method in the contract is either in §4.1 or in the explicit "not
offered" list — a new node RPC fails this test until this plan has a row for it. The probe gets
cases for stock node, wrong `rpcversion`, flag off. D-L-4 gets known-answer vectors from
`yed_validateaddress` on regtest, testnet and mainnet version bytes.

### 6.3 Regtest: the server against `ycash-dd` on one laptop
`contrib/yellowback/devnet/yellowback-devnet up` (ycash-dd; ≈ 2 min; activated and ARMED) gives
an eight-node regtest chain with pools quoting, attestors signing, and a `yellowback-sim`
economy (`role-based-regtest-plan.md`). A new devnet subcommand **`lightwalletd`** writes a
`ycash.conf` for node 0's RPC port (node 0 runs with `insightexplorer=1 txindex=1` — a devnet
change, `contrib/` only), starts the server with `-yellowback -no-tls -bind-addr 127.0.0.1:<port>`,
and the Go integration test (`//go:build devnet`, `frontend/yellowback_devnet_test.go`) then:
- streams `GetBlockRange` from the server and from a **baseline binary** (built from
  `lightwalletd-legacy` by the same script) on the same node and asserts **byte equality** of
  every `CompactBlock` — the backward-compatibility gate;
- asserts `GetLightdInfo` is byte-identical between the two;
- walks the economy: `GetAddressTokens` of a persona's address equals node 0's
  `yed_listunspent` for that persona's wallet (the sim runs its personas on known nodes);
  `GetTxInfo` of a mint the sim made says `verdict == "ok"` and of a VOID mint from
  `yellowback_void_mint.py`'s recipe says the rule; `BuildBundle` returns a bundle that
  `yed_validaterawtransaction` accepts inside a mint the test assembles from raw parts (the
  framework's `build_mint_raw`/`carrier` helpers, exported through a tiny Python driver the Go
  test shells out to — or the test builds it in Go from the spec; decided in L2);
- restarts the node without `-yellowback` and asserts every YED method returns
  `FAILED_PRECONDITION` while `GetBlockRange` keeps streaming.
Registered with the nightly `yellowback_devnet_roles.py` run so it runs on the same chain.

### 6.4 Contract equality
`scripts/extract-spec.sh` (`make spec` / `make spec-check`) already copies the contract into
both forks; it gains `lightwalletd-dd/testdata/yellowback/contract.json` as a third copy, so
`make status` fails when the server's fixtures drift from the node's contract.

### 6.5 CI
`.github/workflows/yellowback-tests.yml` in `lightwalletd-dd`: on push/PR — `go vet`, `go test
./...` (parser and offline YED tests), `go build` (static, as `build.sh`), regenerate
`yellowback.pb.go` with the pinned generator and `git diff --exit-code`, `make spec-check`
equivalent on the contract copy. Nightly — the devnet job, gated on a `ycash-dd` artifact
(reuse `ycash-dd`'s CI build artifact if the workflow is cross-repo; else document the manual
run — the node's own nightly is the precedent, plan v3 §6.0 F-27..F-33).

---

## 7. Work plan

Chunks are sized for one agent each in a `wt/<name>` worktree of `lightwalletd-dd` (the node
pattern; `go build` is seconds, so no shared build cache is needed). Order: **L0 → L1 → L2 in the
server; N1 in the node in parallel with L1; L3 after both.** Each chunk ends with its tests
green and a mapping row (Appendix A) for every impedance mismatch met.

### Phase L0 — Toolchain, baseline capture, CI skeleton (≈ 1 day; 0 lines in existing Go)
- [x] Go 1.27.1 installed by the owner; recorded in `docs/yellowback.md`; `go build ./cmd/server`
      (≈ 8 s) and `go test ./...` on the untouched baseline: 7 parser cases pass, no other
      package has tests. `TestBlockParser` passes — F-6 corrected.
- [x] Baseline binary: `scripts/build-baseline.sh` exports `lightwalletd-legacy` with `git archive`
      and builds it into `wt/lightwalletd-legacy-bin/lightwalletd-legacy` (+ `COMMIT`).
- [x] `.github/workflows/yellowback-tests.yml`: static build, `go vet -stdmethods=false` (F-8),
      `go test`, `cmd/lwdinfo` builds, generated-code check.
- [x] Generator pinned: protoc-gen-go v1.3.2 reproduces both `.pb.go` files' Go API exactly;
      only the embedded gzipped descriptor differs by protoc release, so
      `scripts/check-generated.sh` masks that block (and comment re-wrapping) and CI runs it.
- [x] Devnet: node 0 starts with `-insightexplorer -txindex`; `yellowback-devnet lightwalletd
      start|stop|status [--baseline] [--port] [--extra]` runs the fork build (or the legacy
      binary) against node 0 with its own `lightwalletd.conf`; `check` probes `GetLightdInfo`
      and `GetLatestBlock` through `cmd/lwdinfo` (waits up to 20 s for the cache); `down` stops
      it. (ycash-dd, `contrib/` only.)
**Acceptance — met 2026-09-23:** baseline build, vet, test and the generated-code check green
locally (CI runs on push); on a five-node `--no-attest` regtest devnet the fork build (9067) and
the baseline binary (9068) answered `GetLightdInfo`/`GetLatestBlock` identically at height 232;
`check` passed.

### Phase L1 — `YellowbackStreamer`, read-only set (≈ 4 days; ≈ 800 lines new, ≤ 42 changed)
- [x] `walletrpc/yellowback.proto`: every method of §4.1 except `GetAddressTokens`; generated
      with the pinned generator (`check-generated.sh` covers the third file).
- [x] `common/yellowback.go`: `ProbeYellowback`, `CallYed` (the only path to a `yed_*` RPC),
      `YedMethods` + `NotOffered`, error mapping (§3.3), safe JSON params.
- [x] `frontend/yellowback.go`: the eighteen handlers with edge validation;
      `frontend/yellowback_addr.go` (D-L-4, behind the flag).
- [x] `cmd/server/main.go`: `-yellowback`, probe, register (+17 lines).
- [x] F-1: `SendTransaction`'s `errParts[1]` guard — the only baseline fix.
- [x] `frontend/yellowback_test.go`: 24 cases (§6.2) incl. allow-list completeness, probe,
      address vectors; `testdata/yellowback/contract.json` is `make spec`'s third copy.
- [x] `docs/yellowback.md` L1 section; `cmd/lwdinfo -yellowback` probes all methods; the devnet's
      `check` runs it.
**Acceptance — met 2026-09-23:** offline suite green (24); `git diff --stat lightwalletd-legacy`
shows `service.proto`, `compact_formats.proto`, `parser/`, `common/common.go`, `common/cache.go`
at **0** (`main.go` 17, `service.go` 17, `go.mod` 1, `generate.go` 1); on the regtest devnet
every method answers on node 0 (the node's own `FailedPrecondition` identifiers for the probe's
inputs), the legacy binary answers `Unimplemented` for all eighteen, and
`GetLightdInfo`/`GetLatestBlock` are identical between fork and baseline with the flag on and
off. The `GetBlockRange` byte-equality gate itself is L2.

### Phase N1 — `yed_listtokens` in the node (≈ 2 days; ycash-dd, RPC + docs + tests only)
- [x] `src/rpc/yellowback.cpp`: the RPC of §4.4, registered node-context (+66 lines); two
      `src/rpc/client.cpp` rows so `ycash-cli` converts the array and the number.
- [x] `doc/yellowback-rpc.md` section and error rows; contract regenerated into all three copies
      by `make spec`.
- [x] `yellowback_rpc_contract.py` case; `yellowback_index.py` case vs `yed_listunspent` on every
      enforcing node (the model filter was not needed — revision 5 note).
- [x] Frozen-file proof: `git diff --stat feature/yellowback-sf -- <frozen list>` empty;
      `main.cpp` unchanged.
**Acceptance — met 2026-09-24:** `yellowback_index.py` and `yellowback_rpc_contract.py` green on
regtest (the contract script runs both unarmed and armed sections in one pass); `make
spec-check` green with the third copy. Branch `feature/yellowback-price-attest-n1-listtokens`
awaits merge into `feature/yellowback-price-attest`.

### Phase L2 — `GetAddressTokens`, the devnet integration test (≈ 3 days)
- [x] `yellowback.proto` gains `GetAddressTokens`; handler; offline cases (stream, params,
      three validation cases).
- [x] `frontend/yellowback_devnet_test.go` (§6.3) with `scripts/devnet-test.sh`: the
      byte-equality gate, the baseline's `UNIMPLEMENTED`, the wallet mint's view, and the
      raw-parts mint `EstimateCollateral → GetFeePayee → (BuildBundle when armed) → lwd-rawmint →
      ValidateRawTransaction → SendTransaction → GetTxInfo → GetAddressTokens`.
- [x] Nightly registration: the "lightwalletd against the devnet" step in the node's workflow
      (clones the fork, installs Go, runs the driver `--up --down`); unverified until it runs.
**Acceptance — met 2026-09-24 (unarmed devnet):** 235 compact blocks byte-identical between
fork and baseline; `GetAddressTokens` equal to `yed_listunspent` for every wallet address after
a mint; the raw-parts mint validated, sent and confirmed with `verdict ok`. The armed carrier
path is §9 Q6.

### Phase L3 — Hardening, packaging, review document (≈ 1 week)
- [x] Rate limiting: `frontend/yellowback_ratelimit.go`, a per-peer token bucket (20, then one
      per second) on `EstimateCollateral`, `BuildBundle`, `ValidateRawTransaction`,
      `GetAddressTokens`; peer as the baseline identifies it; `TestRateLimit` offline.
- [x] Edge validation on every method (recorded in `docs/yellowback.md` L3).
- [x] `build.sh`/`docker/Dockerfile` unchanged; `docs/yellowback.md` has the runbook, the
      relay's node flags and the upgrade order; README gains one line.
- [x] `docs/review.md`, the review packet for the Ycash maintainers.
- [x] `go vet`, `go test -race`, `staticcheck` (eight baseline findings, none changed).
**Acceptance — met 2026-09-24:** review document written; budgets: `main.go` 17 [≤ 30],
`service.go` 17 [12 + F-1], `go.mod` 1, `generate.go` 1, `README.md` 2, everything else 0;
the release candidate is the tip of `feature/yellowback-price-attest` (a tag is the owner's
call at L4).

### Phase R0 — Re-port L0–L3 onto the yodl baseline (after the §10 survey)
- [ ] L0 again: baseline build/test/vet on `187a267`; `build-baseline.sh` from the new
      `lightwalletd-legacy`; generator pin re-established for this tree's `.pb.go` toolchain;
      CI skeleton in this tree's conventions.
- [ ] L1 again: `yellowback.proto` and the service registered beside `CompactTxStreamer` the way
      this tree registers its second (darkside) service; `common`/`frontend` files re-derived
      against this tree's RPC client and test stubs; `-yellowback` in this tree's flag/config
      system; the address mapping where this tree's `s…` regex lives; the offline suite.
- [ ] L2 again: `GetAddressTokens`; `cmd/lwdinfo` (so the devnet subcommand and nightly work
      again); the regtest suite and driver.
- [ ] L3 again: rate limit, edge validation, review packet and runbook rewritten for this tree.
**Acceptance:** the same evidence as L0–L3, on the new baseline; old-baseline records marked
historical.

### Phase L4 — Testnet (with v3 Phase A7; ≥ 4 weeks)
- [ ] A public server against a testnet `ycash-dd` node with real attestors (A7's network).
- [ ] The client team's first YED build (§5) against it; findings back into §8.

### Out of scope, tracked
YecLite / mobile implementation (§5 is its contract); any non-Yellowback addition to the
server's surface (a mempool view, §9 Q3, is the one a YED client will ask for first — a separate
proposal); a Go indexer (D-L-2).

---

## 8. Findings and defects (the survey's; fixed only per D-L-8)

| # | Where | What | Disposition |
|---|---|---|---|
| F-1 | `frontend/service.go:465` | `SendTransaction` splits the node's error on `:` and indexes `[1]` unguarded — an error without a colon panics the handler | **fixed in L1** (on the YED path: a rejected YED transaction's message) with a test |
| F-2 | `common/common.go:41-50` | `GetSaplingInfo` type-asserts `chain`, `upgrades["76b809bb"]`, `headers`, `consensus.nextblock` unchecked — a node answer missing one panics at startup | recorded; not on the YED path |
| F-3 | `common/common.go:158-159` | ingestor's `case <-stopChan: break` breaks the `select`, not the loop | recorded |
| F-4 | `parser/block.go:71-95` | coinbase height extraction assumes `vtx[0].vin[0]` and a BIP34 push | recorded; every Ycash coinbase has both |
| F-5 | `frontend/service.go:91-93` | client string spliced into the JSON-RPC params; the regex is the only guard | D-L-4 keeps the regex as the last check after conversion; L3 validates lengths at the edge |
| F-6 | `testdata/blocks` | *(withdrawn in L0)* the first draft said the block-parser fixture was missing; `TestBlockParser` passes at the baseline | none |
| F-8 | `parser/internal/bytestring/bytestring.go:66` | `ReadByte(out *byte) bool` fails `go vet`'s standard-method check | CI vets with `-stdmethods=false`; not on the YED path, not changed |
| F-9 | `vendor/modules.txt` vs `go.mod` | the vendored tree is stale (`ini.v1 v1.41.0` / `golang/protobuf v1.2.0` vendored, `v1.48.0` / `v1.3.2` required), so `-mod=vendor` cannot build; module-aware Go resolves through `go.sum` | left alone (D-L-6: no dependency change); `docs/yellowback.md` says builds are `go.sum`-reproducible, never vendor |
| F-10 | `frontend/service.go` `GetLatestBlock` | answers the height with an empty `hash` (never set from the cache) | recorded; clients use the height; not on the YED path |
| F-7 | `README.md` | describes the pre-fork server; no Ycash or Yellowback operator guidance | `docs/yellowback.md` is the operator guide; README gains one link line (L3) |

---

## 9. Open questions

1. **Should `GetAddressTokens` also stream *spent* history** (`TxLog.spentTokens`) so a client
   can show "you sent 5 YED" without re-deriving it? `GetTxInfo` per transaction answers it
   today; revisit after the client team's first build (L4).
2. **`yed_listtokens` scan cost** on a mainnet-sized token set: measure in N1 with a synthetic
   100k-token index; a `Y<scriptHash>` secondary index (v2's index gains a prefix; schema bump)
   only if the scan exceeds 50 ms.
3. **Mempool view** — *closed 2026-09-23: out of scope.* A light client sees its own pending YED
   only after confirmation; the baseline has no mempool method. Adding one is a non-Yellowback
   change to the server's surface and is a separate proposal, raised by the client team when
   they need it.
4. **TLS and public hosting** are unchanged (nginx in front, README §2); should the YED service
   be exposed on the same port? Yes by default (one server, one certificate); an operator who
   wants the old surface only leaves the flag off.
5. **Whether YecWallet (the full-node GUI) should ever use this path** — no: it has the node's
   wallet and `yed_mint`. The two clients stay on their two paths.
6. **The armed carrier path of the raw-parts mint.** `lwd-rawmint --bundle-hex` and the Go case
   implement it (`BuildBundle` → carrier → `build_mint_tx_v3`), but the L2 run used the unarmed
   five-node devnet; run `scripts/devnet-test.sh` against an eight-node armed devnet
   (`yellowback-devnet up` without `--no-attest`, the attest agent built) before L4.

---

## Appendix A — Rows for `docs/mapping.md` (new §15, "lightwalletd")

| DigiByte / upstream mechanism | lightwalletd-dd at the baseline | Adaptation |
|---|---|---|
| DigiDollar's GUI reads in-process wallet models (mapping §12) | `parser/transaction.go:307-322`, `parser/block.go:101-119`: compact blocks carry Sapling data only and drop any transaction without it, so no transparent output and no `OP_RETURN` reaches a client through blocks | **not changed** (D1, D3); YED history rides `GetAddressTxids` + `GetTransaction` (raw bytes), judgement rides the new service |
| Node index answers "is this output YED" for the wallet (`AllCoins`, `IsMine`) | no RPC answers it for an arbitrary address; `yed_listunspent` is wallet-scoped | `yed_listtokens` (node, §4.4) → `GetAddressTokens` |
| YED address `ye…` = `s1…` key hash, different version bytes (`ycash-dd/src/yellowback/address.h:14-21`) | `GetAddressTxids` regex `^s[a-zA-Z0-9]{34}$` (`frontend/service.go:81-88`), string spliced into the RPC | D-L-4: base58check conversion before the regex, flag-gated; regex kept as the last guard |
| v3 attestation pool is gossip (`iroh-gossip`), node-local, in-memory | a light client cannot gossip (proposal §13) | `GetAttestations`/`BuildBundle`/`GetSelection` proxy the server's node's pool; the client verifies signatures against `ListAttestors` |
| Contract JSON drives YecWallet's offline QTest | no tests for `frontend/` or `common/` at the baseline | `httptest` fake node answering from the same contract JSON; `make spec` keeps the third copy equal |
| `go.mod` `go 1.12`, `golang/protobuf v1.3.2`, vendored | modern Go builds it; `.pb.go` API generation must match across files | D-L-6: generate with the vendored plugin; CI regenerates and diffs |
| Node's `-lightwalletd` experimental flag (`ref/ycash/src/rpc/blockchain.cpp:417,500`) | only gates `getblockdeltas`/`getblockhashes`, which this server never calls | not needed; the server's node needs `insightexplorer=1 txindex=1 experimentalfeatures=1 yellowback=1 yellowbackenforce=0` |
