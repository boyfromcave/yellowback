# Yellowback attestor agent: gossip layer evaluation

**Revision 1, 2026-10-13. Research and recommendation only; no agent code is changed.** The subject is the transport
of the Ycash Yellowback (YED) attestor agent, `ycash-dd` `contrib/yellowback/attest`, read at branch
`fix/cancel-automation` @ `6cbbbfd91` (worktree `wt/fx-cancel-auto-dd`). Library sources were read at the exact pins
the agent's `Cargo.lock` resolves (`iroh 1.2.0`, `iroh-gossip 0.101.0`, from the local cargo registry), and the
upstream repositories, crates.io and docs.rs were checked on 2026-10-13. The question comes from the cancel-limit
design (`yellowback-cancel-limit-design.md`, CAN-2 + C4b): a wrong-price theft is stopped only if enough member
co-signatures reach the cancel driver within `CLAIM_DELAY` = 576 blocks (~12 h).

---

## Owner decisions (2026-10-13)

1. **Co-signature path: direct, members only.** Each agent delivers its cancel co-signature straight to the other
   members over iroh QUIC connections. Non-members are refused at the handshake (`EndpointHooks::after_handshake`);
   each member endpoint id is bound to its seat by one `signmessage` statement from the member key. The open cancel
   gossip topic is retired once the direct path has run alongside it in a trial.
2. **On-chain fallback: yes.** When direct delivery has not gathered `cancelsRequired` co-signatures in time, agents
   publish their 79-byte co-signature record in a standard OP_RETURN (no node change); drivers read them from chain.
3. **Price-attestation channel: reviewed next** with the same method, after the cancel path ships.
4. **Relays: n0 public relays by default, with an optional project-run relay as a configured fallback** (documented
   how to run one).
Also: upgrade iroh-gossip when its peer-refusal fix (#155) is released, for the price channel.

## 0. Summary

- **The finding is confirmed in the library source.** iroh-gossip's PlumTree forwards a message to its eager and
  lazy peers *before* it emits the message to the application, and it offers no validation hook
  (`iroh-gossip-0.101.0/src/proto/plumtree.rs:490-545`: `eager_push`/`lazy_push` at 527-528, `EmitEvent` at 541).
  The only check before forwarding is that the message id is the BLAKE3 hash of the content. There is no rate
  limiting, peer scoring or allowlist in 0.101.0, and no release after it (crates.io, 2026-10-13).
- **The co-signature traffic does not need gossip at all.** There are 15 seats, membership and member keys are on
  chain, and the members are the only producers and the only consumers of co-signatures (every driver is a member).
  A 15-node full mesh is 14 connections per agent, and iroh already provides authenticated, NAT-traversing QUIC
  connections to it.
- **Recommendation: option E1, direct member-to-member delivery over a members-only iroh protocol** on the endpoint
  the agent already runs. Each member's iroh endpoint id is bound to its on-chain member key by a record the member
  key signs through the node's stock `signmessage`. Connections from endpoint ids not bound to a current member are
  refused by an iroh `EndpointHooks::after_handshake` hook. Every co-signature then arrives on the author's own
  authenticated connection: the author is known, a per-member quota replaces the global sampler, and a flood by
  anyone (member or not) can no longer dilute an honest member's frames. No new crate and no node change are needed.
- **Keep iroh-gossip for the public price-attestation topic.** Its subscribers (minters, YecWallet, the devnet) are
  not members, so that topic cannot be closed. Its exposure is a separate, smaller problem: frames are verified by
  the node, and the subscriber already applies per-seq token buckets.
- **Optional third layer, owner's call: an on-chain bulletin board** for co-signatures (one standard OP_RETURN
  transaction per co-signature). It has exactly the censorship resistance of the cancel itself and costs a fee per
  co-signature.
- **libp2p gossipsub (option D) is not recommended.** It does fix validate-before-forward, but it would add about
  130 crates including a second QUIC stack, and a NAT story we would have to operate ourselves. It is also still a
  gossip protocol, solving a fan-out problem that 15 nodes do not have.

## 1. What the agent does today

- `src/transport/iroh.rs` `open_topics`: one iroh `Endpoint` (`presets::N0`: n0's pkarr/DNS address lookup and n0's
  relays unless `[transport] relays` overrides them), one `Gossip` instance, `Router::accept(GOSSIP_ALPN, gossip)`,
  and one subscription per topic, bootstrapped from `[transport] peers` (endpoint ids). Both topics share the
  endpoint, the peers and the relays: `yellowback/attest/<network>/3` (74-byte attestations) and
  `yellowback/cancel/<network>/1` (115-byte `cosig::Frame`, magic `YCG1`).
- `recv_from` returns `delivered_from`, which is the neighbour that forwarded the frame, not its author
  (`transport/mod.rs`, the `recv_from` doc).
- `src/gossip.rs` (the cancel receive pipeline, on its own task): size and magic, a digest dedup, the cheap checks
  against the agent's view (current member seq, known claim, refHeight, not claimable, seq not already held), then
  a uniform reservoir sample within `VERIFY_PER_SECOND` = 2,000 secp256k1 recoveries a second, then the per-seq
  token bucket (`gossip_burst`, `gossip_refill_seconds`). The honest member republishes every block while the claim
  is short.
- The weakness the reviews named, restated precisely: the sampler makes an honest frame's chance per copy equal to
  `budget / offered`. A flood of frames that pass the cheap checks lowers that chance, and these are easy to make:
  a valid header naming a real claim, a real seq whose entry is not yet held, and a garbage signature. The
  republish-every-block loop turns this into "a few blocks with high probability" only while the flood is below
  some multiple of the budget, and an attacker's cost per frame is the bandwidth of 115 bytes. Honest members
  forward the flood to each other before anyone validates it (PlumTree, above), so the flood also spends the honest
  members' bandwidth. Endpoint ids are free Ed25519 keys, so per-neighbour limits would only push the attacker to
  use more ids. That is why the reviewer called the remaining risk "much better but still cheap".

## 2. What the libraries can and cannot do (primary sources)

### 2.1 iroh 1.2.0

- **`EndpointHooks`** (`iroh-1.2.0/src/endpoint/hooks.rs:68-107`, installed with `Endpoint::builder(..).hooks(..)`,
  `endpoint.rs:783`):
  - `before_connect(remote_addr, alpn)` can abort an outgoing dial before any packet is sent.
  - `after_handshake(&Connection)` runs for incoming **and** outgoing connections once TLS has completed. At that
    point the remote endpoint id is authenticated (`Connection::remote_id`, `connection.rs:568`) and the ALPN is
    known (`alpn`, `connection.rs:1125`). Returning `Reject { error_code, reason }` closes the connection.
  - This is the right place for an allowlist. It can be made per ALPN, so a members-only protocol and the public
    attestation topic can share one endpoint.
- **`ProtocolHandler`** (`protocol.rs:240-290`): `on_accepting` (early, before the handshake completes, mainly for
  0-RTT) and `accept(Connection)`. A wrapper around `Gossip` could check `remote_id()` in `accept` before calling
  `Gossip::handle_connection`. The endpoint hook is the cleaner choice, though, because it also covers the
  connections gossip *dials*.
- **Address lookup.** `presets::N0` publishes and resolves endpoint addresses through n0's pkarr/DNS service
  (`presets.rs:116-139`) and uses n0's relays by default. The agent adds a `MemoryLookup`. An id-only peer list
  therefore depends on n0's DNS service unless addresses are configured. This holds for every iroh-based option
  equally.
- **iroh 1.3.0** was released on 2026-09-28. Nothing in this evaluation depends on it.

### 2.2 iroh-gossip 0.101.0

| Feature | Present? | Source |
|---|---|---|
| Validation before forwarding | **No.** It forwards, then emits. The only pre-forward check is id = BLAKE3(content) | `proto/plumtree.rs:490-545` |
| "Do not forward" | **Yes**: `broadcast_neighbors` (`Scope::Neighbors`) sends to direct neighbours only; receivers emit it and never forward it (and do not dedup it) | `api.rs:186`, `api.rs:237`; `plumtree.rs:174-207` |
| Peer allowlist | **No** built-in allowlist. `join_peers` only adds bootstrap peers. Filtering has to be done at the iroh endpoint (hooks) or in a `ProtocolHandler` wrapper | `api.rs:192`; `net.rs:129-131` |
| Neighbour management | HyParView `active_view_capacity` 5 and `passive_view_capacity` 30 by default, configurable through `Builder::membership_config` | `proto/hyparview.rs:197-219`; `net.rs:160` |
| Maximum message size | `Builder::max_message_size`, default 4,096 bytes, minimum 512 | `net.rs:154`; `proto.rs:69-72` |
| Custom ALPN (a second, separate gossip instance on one endpoint) | **Yes**: `Builder::alpn` | `net.rs:178` |
| Rate limiting / peer scoring | **No**, neither in 0.101.0 nor on `main` | crate source; upstream `main` |
| After 0.101.0 | No release. On `main`: "fix bugs in peer lifecycle management (#161)" and "stop the actor without a panic when the runtime shuts down (#183)", both 2026-10-09 | github.com/n0-computer/iroh-gossip/commits/main |

**Known issue that bears on option B:** iroh-gossip
[#155](https://github.com/n0-computer/iroh-gossip/issues/155) (open, filed against iroh 1.0.3 / gossip 0.101.0)
reports that rejecting a peer in a `ProtocolHandler` (accept, then close) leaves the remote's connection actor alive,
so `NeighborUp` never fires and a third peer's join can stall. The lifecycle fixes in #161 are on `main` but not
released. Allowlisting *inside* gossip is therefore not yet a well-trodden path.

### 2.3 rust-libp2p gossipsub (`libp2p-gossipsub` 0.50.0 / `libp2p` 0.57.0, 2026-09-11)

- **Validation before forwarding:** `ConfigBuilder::validate_messages()` "prevents automatic forwarding of all
  received messages". The application then calls `Behaviour::report_message_validation_result(msg_id, source,
  MessageAcceptance::{Accept, Reject, Ignore})`, and `Reject` feeds peer scoring (docs.rs, `ConfigBuilder`,
  `Behaviour`).
- **Signed messages:** `MessageAuthenticity::Signed(keypair)` together with `ValidationMode::Strict` (the default)
  makes every message carry its author's libp2p identity and signature, so the author is known whoever relays it.
- **Peer scoring** (`with_peer_score`, `set_topic_params`, `set_application_score`), `add_explicit_peer`,
  `blacklist_peer`, subscription filters, `max_transmit_size` (default 2,048), IDONTWANT, `max_messages_per_rpc`,
  `connection_handler_queue_len`. Connection allow and block lists come from the separate `libp2p-allow-block-list`
  crate.
- **Maturity:** this is the gossipsub v1.1/v1.2 implementation that Ethereum consensus clients run, with an
  adversarial pedigree. Its scoring parameters are tuned for meshes of hundreds of peers and are known to be hard to
  set well.
- **Cost, measured:** a `libp2p` 0.57 build with gossipsub, QUIC, TCP, noise, yamux, relay, DCUtR, identify,
  AutoNAT and DNS resolves to 375 crates (all-platform lockfile). Next to the agent's current 408, it adds **129
  crates the agent does not have today**, among them `quinn`/`quinn-proto`/`quinn-udp`, a second QUIC stack beside
  iroh's `noq`. (Measured in a scratch crate with `cargo generate-lockfile`.)
- **NAT:** libp2p's answer is circuit relay v2 + DCUtR hole punching + AutoNAT. Somebody has to run the relay nodes
  (there is no default public relay set for an application network), and the operator has to understand the
  multiaddr and identify model. iroh does the same job with a single relay URL and with n0's relays as the default.

## 3. The options

The delivery requirement used throughout: **an honest, live member's co-signature reaches the driving member within
a few blocks, every block, for up to 576 blocks, against an adversary who wants it not to.** The quantity that
matters is how many co-signatures arrive, not when the first one does: the driver needs `cancelsRequired` (up to 5:
its own plus 4 others) plus `spares`.

### A. iroh-gossip as used today

- **Under a non-member flood:** probabilistic. An honest frame competes with every forged frame that passes the
  cheap checks, at a per-copy chance of `budget / offered`. Any outsider who knows the topic name and one
  endpoint id can join, and honest members forward the flood to each other before validating it. The guarantee
  degrades smoothly with flood volume and fails at a volume the attacker controls. That volume is cheap: 2,000
  frames a second is about 230 kB/s.
- **Under a malicious-member flood:** the same as above. A member gains nothing over an outsider, because frames
  are not attributed to their sender.
- **Effort:** none (done).
- **Dependencies:** as today (iroh 1.2.0, iroh-gossip 0.101.0, a 0.x crate on top of a 1.x crate).
- **NAT:** iroh's (hole punching with relay fallback), good.
- **Operations:** low. `peers` and an optional own relay.
- **Fit with attestations:** a natural fit; the attestation topic is public by design.

### B. iroh-gossip restricted to members

How it would be built:

1. A second `Gossip` instance under its own ALPN (`Builder::alpn`, e.g. `ycash/yed-cancel/1`), so the public
   attestation topic keeps working for non-member subscribers.
2. An `EndpointHooks` implementation whose `after_handshake` rejects any connection on that ALPN whose
   `remote_id()` is not bound to a current member, and whose `before_connect` refuses to dial such ids. This also
   stops HyParView from dialling an outsider learned through a shuffle.
3. A binding from endpoint id to member key, which is needed by B and E alike (§4).

Does this close the non-member flood? **Yes, at the transport level.** An outsider cannot complete a connection on
the cancel ALPN, so it cannot inject frames, and honest members never forward its traffic. What is left to an
outsider is volumetric DoS against IP addresses or relays, which no overlay design removes. The issue-#155 risk
applies to this route (§2.2), because rejection happens next to gossip's own connection management.

**Under a malicious-member flood:** still weak. A member is admitted, so its frames are forwarded by honest
members before validation (PlumTree is unchanged). `delivered_from` is still the forwarding neighbour, not the
author. A member flooding garbage under *other* members' seqs therefore still dilutes the sampler, and the per-seq
bucket cannot charge the flood to the right party. Two mitigations are possible:

- set `active_view_capacity` ≥ 14 and use `broadcast_neighbors` only. That makes the protocol a full mesh without
  forwarding, which is option E built out of gossip parts, with HyParView adding nothing;
- or accept that only 1 to 4 colluding members can mount this attack. The design already concedes that four
  colluding members can cancel an honest claim every time (A-3), but that concession is about *false* cancels.
  Being able to *suppress true* cancels is a new power, and B does not remove it.

- **Effort:** medium, about 400–600 lines (binding, hook, second gossip instance, tests). The sampler stays.
- **Dependencies:** none new.
- **NAT:** as A.
- **Operations:** as A, plus the binding (§4).
- **Fit with attestations:** good, through the separate ALPN.

### C. iroh-gossip features we do not use yet

These are worth adopting whatever is decided, but none of them closes the hole:

- `Builder::max_message_size(512)` (the minimum). The frames are 115 and 74 bytes; the default of 4,096 lets a
  flooder push 35 times more bytes per message through honest forwarders.
- `broadcast_neighbors` stops forwarding of *our own* frames, but an outsider's frames are still forwarded by
  others. On its own it only reduces reach.
- A larger `active_view_capacity`. With 15 seats it makes the overlay closer to a mesh and shortens paths.
- **Nothing in iroh-gossip 0.101.0 or on its `main`** validates before forwarding, rate-limits, or scores peers.
  The upstream plumtree code carries a TODO at the very spot ("Do we want to take any measures against the sender
  …", `plumtree.rs:494`).

### D. libp2p gossipsub

- **Under a non-member flood:** good, if it is configured well. Validation happens before forwarding, invalid
  messages are dropped and score their sender down, and an allowlist (`libp2p-allow-block-list` plus explicit
  peers) can close the topic entirely.
- **Under a malicious-member flood:** good. Signed messages identify the author, so per-author limits are exact and
  `Reject` lowers the sender's score.
- **Effort:** high, about 3–5 weeks. Either a second transport stack beside iroh, or both topics moved to libp2p:
  swarm event loop, identity management, relay/DCUtR/AutoNAT, scoring parameters, tests.
- **Dependencies:** +129 crates, a second QUIC implementation, and a larger `cargo deny` surface.
- **NAT:** we would have to run relays and tune hole punching ourselves. Operators would have to understand
  multiaddrs.
- **Operations:** high. Score parameters are notoriously hard to set and to debug.
- **Fit with attestations:** good, if it replaced iroh for both topics. Doing so throws away a working,
  already-audited transport for the public topic, whose problems are smaller.

**Verdict:** it is the right tool for a large open network that needs gossip. Ours is 15 known, bonded, on-chain
members, so most of what it brings is unused weight.

### E. No gossip for co-signatures: direct member-to-member delivery

**E1 (recommended): members-only iroh protocol.** A new ALPN on the existing endpoint, e.g. `ycash/yed-cosig/1`,
handled by a small `ProtocolHandler`, with the same hook as in B. Each agent keeps one connection to every other
bound member (both sides may dial; duplicates collapse to the newer connection). A co-signature is sent directly to
every member (14 small QUIC streams), at once and again every block while the claim is short. Frames are never
forwarded on the receiving side.

- **Under a non-member flood:** closed. The handshake is refused (§4.3 bounds the admission path), and the
  non-member never reaches a member's frame pipeline. As with any design, IP-level volumetric DoS remains. The
  relay fallback and an own relay are the mitigations.
- **Under a malicious-member flood:** bounded per author. A frame received on member X's connection is accepted
  only if its signature recovers to X's own key. That costs one recovery per frame, charged to X's per-connection
  quota (e.g. a token bucket of a few frames per claim per block). X can exhaust only its own quota. It cannot
  dilute anyone else's frames, because honest frames arrive on the honest members' own connections, each with its
  own quota. The global sampler is no longer needed on this path. A member's only remaining power is to withhold
  its own co-signature, which the design already accounts for.
- **Delivery guarantee:** deterministic given reachability. A live honest member whose agent can reach the driver
  (directly or through any relay both can use) delivers its co-signature within one poll after signing, and the
  repeat every block covers a restart. The only remaining dependency is reachability (§6 Q3), not traffic volume.
- **Effort:** medium, about 600–900 lines with tests, roughly 1–2 weeks:
  - the binding record and its verification (§4);
  - the hook;
  - the handler (length-prefixed frames on a uni stream; the existing 115-byte `cosig::Frame` unchanged);
  - a connection manager (dial bound members, reconnect with backoff);
  - plugging into the existing `gossip.rs` checks after the sampler, keeping the cheap checks and the
    verification;
  - a regtest scenario with an outsider flood and a member flood.
- **Dependencies:** none new (iroh 1.2.0 only; iroh-gossip stays for the attestation topic).
- **NAT:** iroh's, identical to today.
- **Operations:** slightly lower than today. The member endpoint ids are discovered from the binding table (§4.2)
  rather than hand-exchanged, so `peers` is only a bootstrap hint.
- **Fit with attestations:** clean. It shares the endpoint, the key file and the relays; the attestation topic is
  untouched; one hook dispatches by ALPN.

**E2: co-signatures over the node's P2P network** (a new P2P message or relay rule). This needs a node change on
both lines. The prime directive and the cancel design's "no node change" footprint rule it out, and it buys nothing
over E1.

**E3: co-signatures in the mempool as standard data transactions.** See F1; it is the same idea.

### F. Other options

**F1. An on-chain bulletin board (no node change).** Each co-signing member also sends one standard transaction with
an `OP_RETURN` output carrying its co-signature, and drivers read co-signatures from blocks and the mempool.

- **Size:** the standard limit is `MAX_OP_RETURN_RELAY` = 83 bytes of script (`ycash-dd` and `ycash6`
  `src/script/standard.h`), so about 80 bytes of data. The 115-byte frame does not fit. A compact record does:
  - a 2-byte tag, an 8-byte intent short id (a truncated hash of txid‖n; the claim is known on chain), the
    4-byte price and the 65-byte signature, 79 bytes in all;
  - the seq comes from key recovery and the refHeight from the claim.
- **Delivery guarantee:** inclusion in the chain. This is *exactly* the assumption the cancel itself already makes
  (A-7: a majority that censors cancels for 576 blocks already enables theft). So this layer can fail only where
  the system fails anyway, and spamming the board costs the spammer fees. Latency is one or two blocks.
- **Costs:**
  - a fee per co-signature per claim, from the few YEC every member already keeps for carriers;
  - a public link between the member's transparent coins and its co-signing (already public through the cancel);
  - the agent has to build a v4 transaction with an OP_RETURN output itself, because `createrawtransaction` in
    either line has no `data` outputs. It would then fund it with `fundrawtransaction`, which is present on
    ycash-dd and deprecated but allowed by default on ycash6 (`DEFAULT_ALLOW_DEPRECATED`, `ycash6/src/deprecation.h:58`), sign it with `signrawtransaction`, and send
    it with `sendrawtransaction`;
  - drivers must scan blocks and the mempool for the tag.
- **Effort:** about 1–2 weeks.
- **Role:** a fallback layer, used when a claim is still short of co-signatures N blocks after it confirmed. It is
  not the primary path.

**F2. A shielded memo board.** The same idea on a Sapling address whose viewing key is published, using 512-byte
memos. It has more room, but costs Sapling proofs and adds viewing-key scanning to every agent. F1 is simpler.

**F3. A pull path through the node.** Drivers fetch co-signatures from members' `subscribe` HTTPS endpoints. This
reuses an optional component that most attestors do not run and needs DNS/TLS that iroh avoids. Not recommended.

## 4. Binding a member's iroh endpoint to its on-chain key

Both B and E need every agent to know which endpoint ids belong to current members.

### 4.1 Deriving the iroh key from the member key: rejected

Deriving the iroh secret deterministically (e.g. `HKDF(memberPriv, "ycash-yed-iroh" ‖ setId)`) has three problems:

1. The member's private key is in the node's wallet, and the agent never holds it: it signs through `yed_sign*` /
   `set_sign*` RPCs. Derivation would mean exporting the hot bond key into a second process, which is a real
   key-handling regression.
2. A verifier still cannot check the link. Knowing the member's secp256k1 public key does not reveal the derived
   Ed25519 public key, so a signed statement is needed anyway.
3. The two keys would rotate together (losing the iroh key file would mean the member key leaked), and the same
   secret would be used across two signature schemes. HKDF makes that sound, but it is still an avoidable coupling.

### 4.2 A signed binding record through stock `signmessage`: recommended

```
binding = "YED-IROH-1" ‖ network ‖ attestorSetId(hex) ‖ seq ‖ endpointId(hex) ‖ issuedHeight
sig     = signmessage <P2PKH address of the member key> <binding>      (node wallet, stock RPC)
```

- **Domain separation.** `signmessage` signs `SHA256d("Zcash Signed Message:\n" ‖ varint(len) ‖ msg)`
  (`ycash-dd/src/main.cpp:141`, `ycash6/src/main.cpp:156`: the same string on both lines). That prefix cannot collide with:
  - a ZIP-243 sighash (BLAKE2b with a branch-bound personalisation);
  - an attestation (`SHA256("YBATTEST1" ‖ …)`);
  - a cancel co-signature (`SHA256d("YedCancelCosign" ‖ …)`, whose preimage does not start with the signmessage
    magic).

  The message's own `YED-IROH-1` tag separates it from any other signed message. Signing it states nothing about a
  price, so EQV-1 cannot be triggered by it.
- **Both lines have it:** `signmessage` (`ycash-dd/src/wallet/rpcwallet.cpp:5371`,
  `ycash6/src/wallet/rpcwallet.cpp:6600`) and `verifymessage` (`ycash-dd/src/rpc/misc.cpp:1227`,
  `ycash6/src/rpc/misc.cpp:1385`). The magic string is identical on both lines. The agent can verify
  locally with k256 (the compact recoverable format it already uses in `cosig::recover`), or call `verifymessage`
  on its node.
- **Validity:** a record is valid while its `seq` is a current member of `attestorSetId` in `set_getinfo` and the
  recovered key equals that member's key. Per seq, the record with the highest `issuedHeight` wins (rotation), and
  a seq may rebind at most once per N blocks (e.g. 10). Removing a member on chain drops its record and closes its
  connection.
- **Distribution, with no registry:**
  - when a connection opens on the members-only ALPN, each side sends its own record and then the table of records
    it holds (at most 15, each self-verifying);
  - one admitted connection therefore yields every member's endpoint id, and the agent dials the rest;
  - `[transport] peers` remains a bootstrap hint, and any single reachable member is enough.

### 4.3 Admission and the outsider path

- `after_handshake` on the members-only ALPN accepts at once any endpoint id that is bound to a current member.
- An unknown id is admitted *provisionally*, under a small global budget (e.g. at most 8 pending admissions, at
  most 2 new ones a second, a 3-second deadline). It must present a valid binding for exactly its own `remote_id`
  as its first message, or it is closed. An outsider's maximum cost to us is therefore a QUIC handshake plus one
  signature recovery, a few per second, and established member connections are never queued behind it.
- A member whose id is already bound never goes through the budget. This is the property that matters: **honest
  member links do not compete with outsider traffic.**

## 5. Comparison

| | Non-member flood | Malicious-member flood | Effort | New deps | NAT | Ops | Attestation topic |
|---|---|---|---|---|---|---|---|
| **A** today | probabilistic, cheap to degrade | same as non-member | done | – | iroh | low | public topic, fits |
| **B** gossip, members only | closed (transport) | still dilutes the sampler (no author) | medium | – | iroh | low + binding | separate ALPN |
| **C** unused gossip features | marginal gains | none | small | – | iroh | low | applies to both |
| **D** libp2p gossipsub | strong (validate-before-forward, scoring, allowlist) | strong (signed authors) | high | +129 crates, second QUIC | own relays/DCUtR | high | would move too, or two stacks |
| **E1** direct, members only | closed (transport) | bounded per author; no dilution | medium | – | iroh | low (auto-discovery) | untouched, shares endpoint |
| **F1** chain board | as strong as the cancel's own inclusion | spam costs fees | medium | – | n/a | fee per co-signature | n/a |

## 6. Recommendation

1. **Adopt E1** for co-signatures: a members-only iroh ALPN, admission by on-chain-bound endpoint ids (§4), direct
   delivery to every member, a per-author quota, and no forwarding.
2. **Keep iroh-gossip for the price-attestation topic**, with `max_message_size(512)`, and move off 0.101.0 to the
   first release that carries #161 once it ships.
3. **Retire the cancel gossip topic** once E1 has run on the devnet and the regtest flood tests pass. It must not
   stay as an extra *input* (that would keep the dilution surface open). At most it can be kept, for one release, as
   publish-only for observers such as chain-viz.
4. **F1 (on-chain board) as a decision for the owner** (Q1). It is the only layer whose guarantee does not depend on
   the members' network reachability, and it costs fees.
5. **Do not adopt libp2p.**

Record of what is given up:

- E1 gives up the multi-hop path that gossip provides. A member that can reach some members but not the driver no
  longer gets its co-signature relayed. iroh's relay fallback makes that case rare; F1 covers it if the owner wants
  it closed.
- The binding adds one small signed record per member and the use of `signmessage` with the member key.

## 7. Migration plan

Everything is in `contrib/yellowback/attest`. There is no node change and no consensus change, and the agent is
identical on both node lines (the `signmessage` magic is the same on both, checked).

| Step | What | Done when |
|---|---|---|
| M0 | Interim, independent of the rest: `Gossip::builder().max_message_size(512)` | unit test; devnet green |
| M1 | `binding.rs`: record format, `signmessage` call, local verification against `set_getinfo` members, the rotation rule; unit vectors on both node lines | vectors verify on ycash-dd and ycash6 regtest |
| M2 | `EndpointHooks` (ALPN-scoped allowlist and `before_connect` filter) and the provisional admission budget | a test where an outsider's connection on the members ALPN is refused while the attestation topic still accepts it |
| M3 | `transport/direct.rs`: handler, connection manager, record-table exchange, per-author quota; feeds the existing `gossip.rs` checks after the sampler | two- and five-agent local tests; reconnect test |
| M4 | Dual-run: the collector takes co-signatures from both E1 and the old topic; the agent publishes on both | devnet role walk; chain-viz shows the co-signers |
| M5 | Regtest adversarial tests in `qa/`: an outsider flood at 10× and 100× the old budget, and a member flood under foreign seqs; the honest co-signatures reach the driver within one block in both | the new `yellowback_cancel_flood.py` passes on both lines |
| M6 | Drop the cancel topic as an input (publish-only for one release, then removed); update `doc/yellowback-attestor.md` (the "No inbound port" text stays true: iroh still needs none) and the threat rows | review gate; the docs updated in the same PR |
| M7 (if Q1 = yes) | F1: the compact 79-byte record, raw transaction build, scanner, triggered N blocks after confirmation while short | regtest shows a cancel driven from chain-read co-signatures with iroh disabled |

The calibration constant this touches is the driver's takeover spacing (`takeover_blocks`). E1 lowers co-signature
latency, so yb-calibration should re-check it if G-11's latency budget used gossip timings.

## 8. Open questions for the owner

- **Q1. On-chain backup for co-signatures?** Each co-signature could also be posted as a tiny transaction, at a
  small fee each time. That makes delivery as reliable as getting the cancel itself mined, and independent of the
  internet path between attestors. Yes, no, or later?
- **Q2. Is it acceptable for attestors to sign one extra statement with their member key**, "my agent's network
  address id is X", using the node's ordinary message-signing command? It cannot be confused with a price or a
  transaction.
- **Q3. Relays.** Today attestors connect through n0's public relays by default. For a 15-member network, should
  the Ycash project run one or two relays of its own and make them the default for mainnet attestors?
- **Q4. Observers.** With the change, nobody outside the 15 members sees co-signatures before the cancel is mined.
  Do chain-viz or anyone else need to see them earlier? If so, the agent can re-publish verified co-signatures to a
  public read-only topic.
- **Q5. Price-attestation topic.** It stays public (minters and wallets need it). Should its own flood exposure be
  reviewed in the same way next, or is the node-side verification plus the per-attestor limits enough for now?
- **Q6. Housekeeping:** agree to upgrade iroh-gossip when the release with its connection lifecycle fixes ships
  (they are on its main branch, not yet released).

## Sources

- Agent: `ycash-dd` `fix/cancel-automation` @ `6cbbbfd91`: `contrib/yellowback/attest/src/transport/{iroh,mod}.rs`,
  `src/gossip.rs`, `src/cosig.rs`, `src/cancel.rs`, `doc/yellowback-attestor.md` (cancel and subscriber sections).
- iroh 1.2.0 (crates.io source): `src/endpoint/hooks.rs`, `src/endpoint.rs:783`, `src/protocol.rs:240-290`,
  `src/endpoint/connection.rs`, `src/endpoint/presets.rs:116-139`.
- iroh-gossip 0.101.0 (crates.io source): `src/proto/plumtree.rs`, `src/proto/hyparview.rs`, `src/proto.rs`,
  `src/net.rs`, `src/api.rs`, `CHANGELOG.md`; https://github.com/n0-computer/iroh-gossip/issues/155;
  https://github.com/n0-computer/iroh-gossip/commits/main (2026-10-13).
- crates.io API (2026-10-13): iroh-gossip latest 0.101.0 (2026-06-15); iroh latest 1.3.0 (2026-09-28);
  libp2p 0.57.0 and libp2p-gossipsub 0.50.0 (2026-09-11).
- docs.rs `libp2p-gossipsub` 0.49.2 (`ConfigBuilder`, `Behaviour`; 0.50.0's docs.rs build failed).
- Node lines: `src/script/standard.h` (`MAX_OP_RETURN_RELAY` = 83), `src/main.cpp:141` (`strMessageMagic`),
  `signmessage`/`verifymessage` RPC tables, `ycash6/src/main.cpp:156`, `ycash6/src/deprecation.h:58`.
- Cancel design: `docs/plans/yellowback-cancel-limit-design.md` §2 (CAN-2), §3 (A-3, A-7), §4 (iii), §5.
