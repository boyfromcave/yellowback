# DigiDollar Oracle Bundle Explainer

This document explains the DigiDollar oracle bundle system in plain language first, then in enough technical detail that another engineer can build, review, test, and operate it.

It describes the current DigiDollar V1 design used by this branch:

- Live exchange prices feed independent oracle operators.
- Oracles use MuSig2 to create one aggregate Schnorr signature.
- Oracle signer ranking is seeded from the blockchain at the epoch boundary.
- Oracle nodes converge on one signed, evidence-bound context proposal before broadcasting partial signatures.
- Oracle nodes broadcast signed version heartbeats so operators can see who is running which oracle protocol.
- Blocks carry compact v0x03 oracle bundles in the coinbase transaction.
- Full nodes verify the bundle before accepting DigiDollar price-dependent blocks.
- Wallet and RPC code fail closed when the chain does not have a valid price.

The main idea is simple:

> The chain only trusts a price when enough independent oracle keys signed the same price, timestamp, signer set, nonce set, and attempt for the same epoch.

## Who This Is For

If you are not a programmer, read:

- "The Short Version"
- "What Problem The Oracle Solves"
- "How Oracle Signers Are Selected"
- "What Happens When Oracles Go Offline"
- "Why The Bundle Is Safe To Trust"

If you are building or reviewing code, also read:

- "The Full Flow"
- "MuSig2 Signing Context"
- "v0x03 Bundle Format"
- "Validator Rules"
- "Recovery Rules"
- "Implementation Map"
- "Testing Blueprint"

## The Short Version

DigiDollar needs a live DGB/USD price. The blockchain itself cannot call exchanges, so independent oracle operators fetch prices and sign a shared answer.

Every oracle does three jobs:

1. Fetch a live DGB/USD price from exchanges.
2. Broadcast a signed price message to other nodes.
3. Join a MuSig2 signing round when selected for the current epoch.

An epoch is a fixed block window. In the current V1 testnet setup, oracle epochs rotate every 40 blocks.

During an epoch, oracle nodes collect nonce messages. A nonce is a one-time public commitment used for one signing round. The matching secret nonce must never be reused.

The signer set is not "oracle IDs 0 through 8 forever." Current V1 code uses deterministic chain-seeded scoring:

1. Derive the epoch selection seed from the blockchain.
2. Look at the oracle IDs that submitted valid nonces for the epoch.
3. Score each one with `GetOracleEpochSelectionHash(epoch, oracle_id, epoch_selection_seed)`.
4. Sort by score.
5. Take the first threshold set, currently 7 signers on testnet/mainnet V1.

That gives every node the same answer without a coordinator. The seed comes from the chain, so nobody can privately pick a favorite committee. It also means higher-numbered oracle IDs count. If lower-numbered oracle IDs are offline but enough higher-numbered active IDs are online and submit nonces, the session can still reach the 7-signer quorum.

Once the selected signers agree on the price, timestamp, signer set, nonce set, and epoch seed, they produce one aggregate MuSig2 signature. The miner puts that signature and the price into the block as a v0x03 oracle bundle.

Every full node verifies the bundle from the block. If the bundle is missing, malformed, stale, or signed by too few valid oracle keys, price-dependent DigiDollar actions fail closed.

## What Problem The Oracle Solves

DigiDollar minting and redemption need to know how much DGB equals a given amount of DD.

Example:

- If DGB is worth $0.004, then 1 DGB is 0.4 cents.
- A mint for $100 of DD needs enough DGB collateral for that live price and the chosen lock tier.
- A redemption must release collateral according to the rules for the vault being redeemed.

The chain needs one price that all nodes can verify. It cannot accept:

- A wallet's local price cache.
- A miner's private price.
- A fallback test price.
- A single exchange quote.
- A single oracle operator's word.

The oracle bundle solves this by committing one quorum-signed price into the block.

## Core Terms

### Oracle

An oracle is an operator with an assigned oracle ID and public key in chainparams. The operator runs DigiByte Core with oracle signing enabled and uses the matching private key.

### Oracle Roster

The roster is the list of oracle public keys known by consensus parameters.

The current V1 shape is:

- Testnet/mainnet V1 target: 35 oracle public keys, 7 required signatures.
- Regtest: 7 oracle public keys, 4 required signatures.

Changing the roster or threshold is a consensus-sensitive change. Do not do it casually.

### Epoch

An epoch is a block window used for oracle signing rotation.

Current testnet/mainnet V1 code uses:

- `nDDOracleEpochBlocks = 40`
- About 10 minutes at roughly 15 seconds per block.
- About 6 oracle epochs per hour.

Each epoch gets its own nonce exchange and signing context.

### Epoch Selection Seed

The epoch selection seed is the block hash used to rank oracles for that epoch.

For epoch `E`:

```text
epoch_start_height = E * nDDOracleEpochBlocks
seed_height        = epoch_start_height - 1
epoch_seed         = block_hash(seed_height)
```

For the first epoch, the seed is clamped to the genesis block hash.

This keeps selection deterministic for every node, but tied to the chain. Before `seed_height` exists, nodes may collect nonces for the upcoming epoch, but they must not choose the final signing context yet.

### Price Message

A price message says:

- Oracle ID.
- DGB/USD price in micro-USD.
- Timestamp.
- Signature by that oracle.

All oracle operators can broadcast price messages. Price gossip is not the final chain truth. It is input to the MuSig2 signing round.

### Nonce

A nonce is a one-time MuSig2 signing commitment.

There are two parts:

- Public nonce: broadcast to peers.
- Secret nonce: kept private in memory and destroyed after signing.

Never reuse a secret nonce. Reusing signing nonces can leak private keys.

### Attempt

An attempt is a retry number inside one epoch.

Most epochs use attempt `0`. If a session fails before it completes, the network can start a fresh attempt with fresh nonces. Attempt IDs are off-chain signing metadata. They do not change the on-chain v0x03 bundle format.

Attempt IDs matter because a MuSig2 secret nonce may only be used once. A partial signature from attempt `0` must never be accepted into attempt `1`.

### Partial Signature

Each selected oracle signs the same message and broadcasts one partial signature.

The partial signature is not useful by itself. When enough matching partial signatures arrive, they combine into one 64-byte Schnorr aggregate signature.

### Bundle

The bundle is the compact data committed to the block. It includes:

- Version byte `0x03`.
- Signer bitmap.
- Epoch.
- Price.
- Timestamp.
- Aggregate Schnorr signature.

### Bitmap

The bitmap says which oracle IDs signed.

If bit 5 is set, oracle ID 5 signed. If bit 14 is set, oracle ID 14 signed.

Validators use the bitmap to reconstruct the aggregate public key and verify the aggregate signature.

### Version Heartbeat

A version heartbeat is a signed off-chain status message from an oracle. It reports:

- Oracle ID.
- DigiByte Core client version.
- P2P protocol version.
- Oracle protocol version.
- MuSig2 context version.
- Software version string.
- Timestamp and nonce.

Heartbeats help operators answer a simple live-network question: "Which oracle slots are online, and what version are they running?"

Heartbeats are not mined, do not set the price, and do not change consensus.

### Fail Closed

Fail closed means "do not guess."

If the node cannot prove a valid oracle price from the chain, DigiDollar mint/redeem behavior that needs a price stops instead of inventing one.

## System Flow At A Glance

```text
               LIVE EXCHANGES
                     |
                     v
        +---------------------------+
        | Independent oracle nodes  |
        | fetch DGB/USD prices      |
        +---------------------------+
                     |
                     v
        +---------------------------+
        | Signed price gossip       |
        | ORACLEPRICE messages      |
        +---------------------------+
                     |
                     v
        +---------------------------+
        | Epoch MuSig2 session      |
        | nonce round + signing     |
        +---------------------------+
                     |
                     v
        +---------------------------+
        | v0x03 oracle bundle       |
        | in coinbase transaction   |
        +---------------------------+
                     |
                     v
        +---------------------------+
        | Full nodes validate       |
        | price, bitmap, signature  |
        +---------------------------+
                     |
                     v
        +---------------------------+
        | DigiDollar mint/redeem    |
        | uses validated price      |
        +---------------------------+
```

## The Full Flow

### Phase 1: Price Fetching

Each oracle operator continuously fetches live DGB/USD prices.

The node rejects bad prices before they can become consensus input:

- Price must be within the configured minimum and maximum.
- Timestamp must be fresh enough.
- Oracle ID must be part of the active consensus keyset.
- Signature must authenticate the oracle message.

Good messages are stored in the oracle bundle manager pending pool.

```text
Oracle 0 price ---> pending_messages[0]
Oracle 1 price ---> pending_messages[1]
Oracle 2 price ---> pending_messages[2]
...
Oracle 15 price --> pending_messages[15]
```

The pending pool is local memory. It is not the chain truth yet.

### Phase 2: Start An Epoch Session

When blocks connect, the signing orchestrator ticks the current epoch session.

Near the end of an epoch, the orchestrator also pre-starts the next epoch. That is intentional. It gives public nonces time to spread before the next epoch's first block is mined.

Important rule:

- Nonce exchange may begin before the next epoch seed is known.
- Context proposal and partial signing must wait until the seed is known.

For each local oracle key running on the node:

1. Compute the aggregate key context for the roster.
2. Generate a fresh MuSig2 nonce.
3. Keep the secret nonce private.
4. Broadcast the public nonce.

```text
Block connected
      |
      v
TickEpochSession(epoch, height)
      |
      v
Generate public nonce for local oracle IDs
      |
      v
Broadcast ORACLEMUSIGNONCE
```

```text
Current epoch tail
      |
      v
Pre-start next epoch nonce collection
      |
      v
Wait until seed_height block is known
      |
      v
Only then select signers and propose context
```

### Phase 3: Collect Nonces

Every node collects valid public nonces.

The nonce map is keyed by oracle ID:

```text
m_pubnonces = {
  0: nonce_from_oracle_0,
  1: nonce_from_oracle_1,
  2: nonce_from_oracle_2,
  5: nonce_from_oracle_5,
  10: nonce_from_oracle_10,
  14: nonce_from_oracle_14,
  ...
}
```

Once enough valid nonces exist, the node can select the threshold signing set.

RC38 keeps the signed nonce messages as evidence. A later context proposal includes the nonce evidence for the signing set, so a node can reconstruct the exact nonce set before it signs.

## How Oracle Signers Are Selected

No central node picks the signers.

Every honest node can compute the same ranking from public data:

```text
epoch_start_height = epoch * epoch_length
seed_height        = max(0, epoch_start_height - 1)
epoch_seed         = block_hash(seed_height)
score              = GetOracleEpochSelectionHash(epoch, oracle_id, epoch_seed)
```

Then nodes sort by score and take the first threshold set from the nonce submitters.

That is the "random" part in plain terms:

- The roster is known.
- The current epoch is known.
- The seed comes from the chain.
- Every oracle ID gets a hash score.
- Lowest score wins priority for that epoch.

It is not a dice roll from one server. It is deterministic randomness from public chain data. Everyone gets the same answer after the seed block exists.

Example with 7 required signers:

```text
Epoch: 40
Seed:  block hash at height (40 * epoch_length - 1)
Nonce submitters: 0, 1, 2, 3, 4, 5, 10, 14, 15

Compute score for each submitter:

  score(40, 14) = lowest
  score(40, 5)
  score(40, 1)
  score(40, 3)
  score(40, 10)
  score(40, 0)
  score(40, 4)
  score(40, 2)
  score(40, 15) = highest in this set

Sorted committee:

  14, 5, 1, 3, 10, 0, 4
```

At least 7 submitted nonces, so the session can move forward.

This is the important behavior:

```text
Wrong behavior:
  Always wait for 0,1,2,3,4,5,6,7,8.
  If 6,7,8 are offline, signing stalls forever.

Current V1 behavior:
  Rank nonce submitters by chain-seeded epoch score.
  Take the threshold set from actual submitters.
  Higher IDs can sign when low IDs are offline.
```

The ranking changes when the epoch changes, because both the epoch number and chain seed are part of the score.

```text
Epoch 40 committee order: 14, 5, 1, 3, 10, 0, 4, 2, 15
Epoch 41 committee order: different score order
Epoch 42 committee order: different score order
```

This is deterministic rotation, not a hidden coordinator.

### Why The Seed Uses The Previous Boundary Block

The signer set for an epoch must be known before miners try to build a bundle for that epoch.

Using the block immediately before the epoch starts gives both properties:

- It is chain data, so every node can verify it.
- It is available right before the epoch starts, so nonce collection can already be underway.

```text
... block 78 ... block 79 | block 80 ... block 119 | block 120 ...
                  ^          ^
                  |          |
          seed for epoch 2   epoch 2 starts
```

With a 40-block epoch, epoch 2 starts at height 80 and uses block 79 as the seed.

### Who Gets To Propose The Context

There is still no central coordinator.

Context proposal priority uses the same chain-seeded oracle ranking. The top-ranked eligible proposer gets the first chance. If that proposer is offline or cannot build a valid context, lower-ranked proposers become eligible in later rounds.

```text
Seeded proposer order for epoch E:
  14, 5, 1, 3, 10, 0, 4, 2, 15, ...

Round 0:
  Oracle 14 may propose.

Round 1:
  Oracle 14 or 5 may propose.

Round 2:
  Oracle 14, 5, or 1 may propose.
```

The proposer does not get to invent the answer. A proposal is accepted only if every node can verify:

- The epoch seed matches the local chain.
- The signer IDs are the top threshold set from the valid nonces the node has already seen.
- The signer IDs are sorted by the seeded ranking.
- The signer count equals the required threshold.
- Every signer has a valid nonce.
- The price/timestamp matches the selected signers' price messages.
- The context ID matches the exact nonce set and signer bitmap.
- The proposal is signed by the proposer oracle key.

## Phase 4: Compute The Price To Sign

The signing round must sign one exact message.

That message is built from:

- Consensus price.
- Consensus timestamp.

For RC38, the price calculation used for the signing context is scoped to the selected signer IDs and is committed as price evidence in the context proposal.

That matters because the signed message must not drift while nodes are signing.

```text
Selected signers:
  0, 1, 2, 3, 4, 5, 10, 14, 15

Use price messages from exactly those IDs:
  pending_messages[0]
  pending_messages[1]
  pending_messages[2]
  pending_messages[3]
  pending_messages[4]
  pending_messages[5]
  pending_messages[10]
  pending_messages[14]
  pending_messages[15]

Ignore non-signer prices for this signing message.
```

The price algorithm uses the existing oracle consensus price calculation. Outliers are filtered before the median price is chosen.

If a selected signer does not have a fresh price message, the node waits instead of signing a different message.

The context proposal carries the selected signers' signed price messages. Validators of the off-chain context recompute the consensus price and timestamp from that evidence. This prevents one node from signing a price that another node cannot reproduce from the same context.

## Phase 5: Propose And Freeze The Signing Context

This is the RC38 convergence point.

MuSig2 partial signatures are only valid for one exact signing transcript. The transcript includes:

- Chain genesis hash.
- Epoch.
- Epoch selection seed.
- Context version.
- Price/timestamp message hash.
- Signer bitmap.
- Public nonce set hash.

RC38 has an explicit context proposal message:

```text
OracleMusigContextMsg {
  epoch,
  attempt_id,
  context_version,
  epoch_selection_seed,
  proposer_id,
  participant_ids,
  nonce_set_hash,
  quote_set_hash,
  consensus_price,
  consensus_timestamp,
  session_context_id,
  nonce_evidence[],
  price_evidence[],
  auth_signature
}
```

The proposal says, "this is the exact transcript selected oracles should sign."

Every node independently validates the proposal before signing it. If the proposal does not match local chain data, the signed nonce evidence, the signed price evidence, or locally known higher-priority nonces, the node rejects it.

The context ID is computed from:

```text
session_context_id =
  H(
    "DigiDollar/MuSig2SessionContext/v1",
    chain_genesis_hash,
    epoch,
    attempt_id,
    epoch_selection_seed,
    context_version,
    message_hash,
    signer_bitmap,
    nonce_set_hash
  )
```

That context ID is carried by partial signature P2P messages.

Why it matters:

- A partial signature for price A must not be accepted into a session signing price B.
- A partial signature for signer set A must not be accepted into signer set B.
- A partial signature using nonce set A must not be accepted into nonce set B.
- A partial signature from another chain must not be accepted here.

Before this hardening, partial signature messages identified the epoch and oracle ID, but not the exact transcript. That was safe in the sense that invalid aggregate signatures failed verification, but it hurt liveness because honest nodes could produce partial signatures for slightly different local contexts and then reject each other's partials.

RC38 makes the context explicit and evidence-bound before partial signatures are broadcast.

## Phase 6: Broadcast Partial Signatures

Each selected local oracle signs only after it has accepted the same context proposal. It then broadcasts:

```text
OracleMusigPartialSigMsg {
  epoch,
  attempt_id,
  context_version,
  session_context_id,
  oracle_id,
  partial_sig,
  auth_signature
}
```

The authentication signature also commits to the context.

If a peer changes the context version or context ID after signing, authentication fails.

If a node receives a partial signature for a different context than its local session, it ignores it.

Pending partial signatures are buffered by:

```text
epoch -> session_context_id -> oracle_id
```

That prevents a stale or different-context partial signature from replacing the right one.

The buffer is also bounded per context and per epoch. That matters because an attacker with an authenticated oracle key must not be able to create unlimited pending entries by grinding random context IDs.

## Phase 7: Aggregate The Signature

When enough valid partial signatures arrive for the same context:

1. The node aggregates the partial signatures.
2. The result is one 64-byte BIP-340 Schnorr signature.
3. The completed session records the signed price and signed timestamp.

```text
Partial sig 0  \
Partial sig 1   \
Partial sig 2    \
...              +--> AggregateSignature() --> 64-byte Schnorr signature
Partial sig 14  /
Partial sig 15 /
```

The miner can now include a v0x03 bundle in a block.

## Phase 8: Mine The Bundle

The miner adds the oracle bundle to the coinbase transaction as an `OP_RETURN OP_ORACLE` output.

```text
Block
  |
  +-- coinbase transaction
        |
        +-- OP_RETURN OP_ORACLE <v0x03 bundle>
```

This keeps the oracle proof inside the block. Validators do not need the off-chain P2P messages to validate the final block.

## v0x03 Bundle Format

The on-chain bundle format is unchanged by RC38.

```text
+------------+---------------+-------------------------------+
| Field      | Size          | Meaning                       |
+------------+---------------+-------------------------------+
| version    | 1 byte        | 0x03                          |
| bitmap_len | 1 byte        | Number of bitmap bytes        |
| bitmap     | bitmap_len    | One bit per oracle ID         |
| epoch      | 4 bytes       | Little-endian uint32          |
| price      | 8 bytes       | Little-endian uint64 microUSD |
| timestamp  | 8 bytes       | Little-endian uint64 unix     |
| signature  | 64 bytes      | BIP-340 Schnorr aggregate sig |
+------------+---------------+-------------------------------+
```

Example shape for the current 35-oracle active roster:

```text
version       = 03
bitmap_len    = 05
bitmap        = 5 bytes, enough for oracle IDs 0..34
epoch         = current oracle epoch
price         = DGB/USD in micro-USD
timestamp     = oracle consensus timestamp
signature     = 64-byte aggregate Schnorr signature
```

The bitmap is critical. It tells validators exactly which oracle public keys to aggregate.

## Validator Rules

Full nodes validate the block bundle. They do not trust the miner.

The validator checks:

```text
Bundle version is 0x03
Bitmap length matches the configured oracle roster size
Bitmap has at least the required number of signers
Every set bit is a valid oracle ID
Price is inside allowed min/max bounds
Timestamp is not stale or too far in the future
Epoch matches the block height's oracle epoch
Aggregate public key reconstructed from bitmap signers
Aggregate signature verifies against the signed price/timestamp message
```

If these checks fail, the bundle is invalid. Price-dependent DigiDollar behavior cannot use it.

## What Happens When Oracles Go Offline

The system is designed to fail closed and recover.

### If fewer than threshold oracles are available

If fewer than 7 valid testnet/mainnet V1 oracles are online and fresh:

- No valid MuSig2 aggregate bundle can be produced.
- Minting that needs a fresh price pauses.
- Redemption paths that need a fresh price pause unless their rules can use already locked data.
- The node does not invent a price.
- Existing chain history remains valid.

This is an outage, not a consensus split.

### If enough oracles come back

When enough oracles return:

1. They fetch live prices again.
2. They broadcast fresh price messages.
3. They broadcast fresh nonces for the current epoch.
4. Nodes select the threshold signer set from nonce submitters.
5. A new context-bound MuSig2 signing round completes.
6. New v0x03 bundles appear in blocks.

No manual fake price is required.

### If an oracle misses an epoch

Missing an epoch does not permanently break the node.

The next epoch is a fresh session with fresh nonces and a fresh context ID.

### If an oracle goes down for days

The oracle can recover by starting again with its assigned key on the correct chain. It does not need old secret nonces. Old nonces are not reusable and should be gone.

The network still needs threshold participation. If too many operators are offline at once, the system waits.

## Why The Bundle Is Safe To Trust

The bundle is safe only because several protections stack together:

```text
Live exchange fetching
      |
      v
Independent oracle signatures on price messages
      |
      v
Deterministic threshold signer selection
      |
      v
Verifiable context proposal
      |
      v
MuSig2 aggregate signature over one exact message
      |
      v
Signer bitmap committed in the bundle
      |
      v
Full-node validation of bitmap, price, timestamp, and signature
```

The miner cannot choose an arbitrary price because it cannot forge the aggregate signature.

A single oracle cannot choose the price because threshold signing is required.

A stale partial signature cannot be mixed into a new context because RC38 binds partial signatures to `attempt_id` and `session_context_id`.

A message from another network cannot be replayed because oracle message hashes bind to the chain genesis hash.

## Decentralization Model

No single node decides the bundle.

Several independent pieces must line up:

- Oracles independently fetch price data.
- Oracles independently broadcast price and nonce messages.
- Every node independently derives the epoch seed from the chain.
- Every node independently scores nonce submitters for the epoch.
- Every node independently computes the selected signer set.
- The eligible proposer is chosen by the same seeded ranking.
- The proposal is accepted only if it is locally reproducible.
- Every selected oracle independently signs the same context.
- Any miner can include a completed bundle.
- Every validator independently verifies the final bundle from the block.

The bundle only becomes useful when enough independent oracle keys signed the same thing.

## What RC38 Hardens

RC38 kept the on-chain v0x03 format and the then-current 9-of-17 V1 model. Current chainparams use 7-of-35 on mainnet/testnet. The RC38 hardening still matters because it made the off-chain signing path converge after restarts, timing drift, partial outages, and mixed message arrival order.

### Problem

Live logs showed nodes collecting prices and nonces, then getting stuck with too few valid partial signatures or no fresh bundle for the current epoch.

The deeper issue was convergence. Nodes could honestly see nonce and price gossip in different orders, then freeze slightly different local contexts. MuSig2 correctly rejects mismatched partial signatures, but that means the bundle never finishes.

The previous hardening made nodes agree on a context proposal before they sign. RC38 tightens that proposal so it carries the nonce and price evidence needed to reproduce the context. It also adds attempt IDs so a retry cannot mix messages from an older failed attempt.

### Fix

RC38 adds and enforces these rules:

- The selected quorum signers are ranked with `GetOracleEpochSelectionHash(epoch, oracle_id, epoch_selection_seed)`.
- The epoch seed comes from the chain boundary block, not from a remote peer.
- Future epoch nonce prestart is allowed, but context signing waits until the seed exists.
- A signed `OracleMusigContextMsg` announces the exact attempt, signer set, nonce set hash, price evidence hash, price, timestamp, epoch seed, and context ID.
- Nodes validate the context proposal from the included signed nonce and price evidence before signing.
- Remote context proposals cannot define the local seed. The local chain defines the seed.
- Partial signatures bind to both `attempt_id` and the accepted `session_context_id`.
- The old epoch-only bundle-manager MuSig2 ingestion path is bypassed for live P2P relay, so the signing orchestrator is the single off-chain session owner.
- Signed oracle version heartbeats are relayed and exposed through RPC for operator visibility.

The context ID binds:

- Chain genesis hash.
- Epoch.
- Attempt ID.
- Epoch selection seed.
- Price/timestamp message.
- Selected signer bitmap.
- Public nonce set.

Nodes now reject or buffer partial signatures by exact attempt and context.

### Result

Nodes first converge on one transcript, then aggregate only partial signatures that belong to that transcript.

That improves liveness without weakening validation and without changing the on-chain bundle format.

## Startup And First Epoch

At startup, oracle nodes may not all be online at once.

The correct behavior is:

1. Start fetching live prices as soon as oracle mode is running.
2. Start nonce exchange for the current epoch.
3. Derive the epoch selection seed from the local chain.
4. Wait until threshold fresh prices and threshold nonces exist.
5. Accept or build one valid context proposal.
6. Sign only when the exact context is ready.
7. Mine a bundle once the aggregate signature completes.

For the first epoch, the seed uses the genesis block hash. For later epochs, the seed uses the block immediately before that epoch begins.

If the first epoch after activation does not get threshold participation, the system waits for the next viable epoch. It should not fall back to a fake price.

This works for testnet and mainnet because the bundle is validated from the block, not from a local startup assumption.

## Existing Testnet And Mainnet Readiness

### Existing testnet

RC38 does not reset testnet26 and does not change the v0x03 bundle format.

Oracle nodes running RC38 need the attempt-aware, evidence-bound context proposal messages for live signing. Mixed oracle versions may gossip prices and nonces, but they will not reliably converge on the RC38 signing context.

The chain-visible bundle remains v0x03. Validators still verify the same on-chain data shape.

### Mainnet deployment

Mainnet deployment still needs Jared's review, tag, release, and deploy decision.

Before mainnet activation, the must-pass behavior is:

- Live exchange price path works.
- At least threshold oracles are online.
- MuSig2 sessions complete with context-bound partial signatures.
- Miners include valid v0x03 bundles.
- Validators reject invalid bundles.
- Wallet/RPC/Qt fail closed when no price is available.
- Restart, rescan, reindex, backup, and restore do not corrupt DigiDollar state.

## Implementation Map

Key files:

```text
src/primitives/oracle.{h,cpp}
  Oracle price messages, oracle constants, epoch selection helpers.

src/oracle/musig2_session.{h,cpp}
  Nonce collection, participant selection, nonce aggregation,
  session context ID, partial signature aggregation.

src/oracle/signing_orchestrator.{h,cpp}
  Per-block epoch ticking, local oracle nonce/signature broadcast,
  epoch seed tracking, context proposal handling,
  pending partial signature buffering.

src/oracle/bundle_manager.{h,cpp}
  Price message pool, selected-oracle consensus values,
  version heartbeat storage, bundle assembly and validation helpers.

src/oracle/musig2_messages.h
  P2P message structures for MuSig2 nonce, context proposal,
  and partial signatures.

src/protocol.cpp
  Oracle P2P message hashes, heartbeat hashes, and authentication hash binding.

src/net_processing.cpp
  P2P relay and rejection rules for oracle messages.

src/kernel/chainparams.cpp
  Oracle roster, threshold, epoch length, activation parameters.

src/digidollar/validation.cpp
  DigiDollar block and transaction validation using chain oracle data.

src/wallet, src/rpc, src/qt
  User-facing mint, redeem, transfer, balance, and status behavior.
```

## Testing Blueprint

The oracle bundle system is not proven by one unit test. It needs layered testing.

### Unit tests

Unit tests should prove:

- Epoch scoring is deterministic.
- Epoch scoring changes when the chain seed changes.
- Committee selection changes across epochs.
- Offline low IDs do not block a valid threshold set.
- Nodes converge on the same selected signers and context ID even when nonce arrival order differs.
- Remote context proposals cannot define the local epoch seed.
- Context proposal authentication binds attempt, seed, proposer, participants, nonce evidence, price evidence, price, timestamp, and context ID.
- Partial signature authentication binds attempt and session context.
- Partial signatures from the wrong context are rejected.
- Attempt ID changes alter nonce, context, and partial-signature hashes.
- Signed version heartbeats verify, serialize, store latest status, and reject tampering.
- Selected-oracle price calculation ignores non-signer outliers for the signing context.
- v0x03 bundle parsing and validation reject malformed bundles.

### Functional tests

Functional tests should prove:

- DigiDollar activation boundaries are respected.
- Mint/redeem paths require valid oracle data.
- Wallet state survives restart, rescan, reindex, backup, and restore.
- Regtest mock oracle prices only work when explicitly enabled.
- No production path silently uses a fake price.

### Fuzz tests

Fuzz tests should exercise:

- Oracle bundle parsing.
- Bitmap parsing.
- MuSig2 aggregate validation boundaries.
- Context proposal authentication and mutation boundaries.
- Partial signature message serialization.
- Oracle version heartbeat message serialization.
- Price and timestamp edge cases.

### Live multi-oracle script

The highest-value gate is:

```bash
./test_multi_oracle_testnet.sh
```

That script proves the system as a whole:

- Live prices.
- Multiple oracle operators.
- MuSig2 bundles.
- Mining.
- Minting.
- Redemption.
- Transfers.
- Oracle recovery.
- Wallet restart.
- Wallet restore.
- Rescan.
- Reindex.

Partial progress is not a pass. It must finish end-to-end.

## Operator Checklist

For oracle operators:

```text
1. Confirm the node is on the intended network.
2. Confirm the wallet/oracle key for the assigned oracle ID is available.
3. Confirm live price fetching is working.
4. Confirm nonce messages are being sent and received.
5. Confirm `getoracles` shows a fresh heartbeat and the expected RC/protocol versions for your oracle ID.
6. Confirm context proposal messages are being sent and received.
7. Confirm partial signature messages include the current attempt and a non-null session context.
8. Confirm v0x03 bundles appear after activation.
9. Confirm getoracleprice returns a nonzero validated chain price.
10. Do not use mock prices on production-style testnet or mainnet.
```

Useful RPCs:

```bash
digibyte-cli -testnet getblockchaininfo
digibyte-cli -testnet getnetworkinfo
digibyte-cli -testnet getoracles
digibyte-cli -testnet getoraclesigners
digibyte-cli -testnet listoracle
digibyte-cli -testnet getoracleprice
digibyte-cli -testnet getdigidollarstats
```

## Failure Cheat Sheet

```text
Symptom:
  Prices are visible, but no bundle is mined.

Check:
  Are at least threshold fresh oracle price messages present?
  Are at least threshold public nonces present for the epoch?
  Is the epoch selection seed known locally?
  Are valid context proposals being accepted?
  Do context proposals include valid nonce and price evidence?
  Are partial signatures using the same attempt_id and session_context_id?

Symptom:
  Partial signatures arrive but do not aggregate.

Check:
  Does the message context match the local session context?
  Does the attempt ID match the local session attempt?
  Are all partials for the same price/timestamp, bitmap, and nonce set?
  Did every selected signer accept the same context proposal?
  Are old buffered partials being ignored by context?

Symptom:
  Bundle is mined but rejected.

Check:
  Does bitmap length match roster size?
  Does popcount meet threshold?
  Does the aggregate signature verify against the bitmap signer keys?
  Is timestamp within allowed window?
  Is price within min/max bounds?

Symptom:
  Minting fails with no oracle price.

Check:
  Is there a validated on-chain price?
  Did the block include a valid v0x03 bundle?
  Is this a real oracle outage? If yes, fail-closed is correct.
```

## Rules That Should Not Be Weakened

Do not weaken these just to make tests pass:

- Do not add production fallback prices.
- Do not let a single oracle set the chain price.
- Do not accept partial signatures without a valid session context.
- Do not accept stale or future oracle timestamps.
- Do not accept invalid signer bitmap bits.
- Do not accept bundles with too few signers.
- Do not make wallet caches consensus truth.
- Do not treat regtest mock prices as production behavior.

## Final Mental Model

Think of a DigiDollar oracle bundle as a notarized price receipt:

- The receipt is the v0x03 bundle.
- The notaries are the selected oracle keys.
- The signatures are combined into one compact Schnorr signature.
- The bitmap lists exactly which notaries signed.
- The block carries the receipt.
- Every full node checks the receipt before using the price.

If the receipt is valid, DigiDollar can use the price.

If the receipt is missing or invalid, DigiDollar stops rather than guessing.
