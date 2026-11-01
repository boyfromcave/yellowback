# kogany planning

Plans for bringing Ycash Yellowback (YED) and the vault network upgrade to **kogany**, the fork of
Zakura (a Rust Zcash full node from the Zebra lineage) that becomes the third Ycash node line.

- [`kogany-yellowback-plan.md`](kogany-yellowback-plan.md) — **the plan** (revision 2, 2026-11-01): owner decisions K-1…K-26 (K-20 and K-21 decided), waves W0–W9 with chunks and gates, and the **parity sidecar track S0–S5** (§3b): the product is kogany plus a separate wallet process on yew-core that answers the ycashd wallet RPCs, with a signer boundary, gated on the wallet RPC contracts and the 48 wallet-needing scripts. Budgets, CI, estimate, risks, mapping §24 rows. Revision 1 (same day) had the wallet on a ycash6 sidecar only; that sidecar remains the test rig.

Surveys (2026-11-01, inputs to the plan):

- [`surveys/a-zakura-architecture.md`](surveys/a-zakura-architecture.md) — lane A: Zakura's validation layers, upgrade model, script crate, state and mempool, and the Yellowback hook table.
- [`surveys/b-ycash-network-on-zakura.md`](surveys/b-ycash-network-on-zakura.md) — lane B: what makes kogany a Ycash node (branch IDs, Equihash 192,7, YDF, checkpoints, P2P) and the crate-fork options.
- [`surveys/c-yellowback-delta-inventory.md`](surveys/c-yellowback-delta-inventory.md) — lane C: the C++ Yellowback/vault delta classified for a wallet-less Rust node, client dependencies and layer order.
- [`surveys/d-minimalism-future-compat.md`](surveys/d-minimalism-future-compat.md) — lane D: placing Vault between Canopy and NU5 so NU5/NU6/NU7/Tachyon stay enable-able later.
- [`surveys/e-verification-strategy.md`](surveys/e-verification-strategy.md) — lane E: vector replay, the mixed-line regtest harness, kogany CI and the wave → gate matrix.

Research notes (2026-11-01, read-only, inputs to revision 2):

- [`research/tx-v4-vs-v5-protocol.md`](research/tx-v4-vs-v5-protocol.md) — transaction v4 versus v5: the formats (ZIP 225, ZIP 244), where each node line implements them, and the trade-offs.
- [`research/vault-on-v5-assessment.md`](research/vault-on-v5-assessment.md) — what defining the vault upgrade on v5 would take; options A–D. The owner chose **D** (v4-only now, a dormant ZIP-244 message), recorded as K-21.
