# kogany planning

Plans for bringing Ycash Yellowback (YED) and the vault network upgrade to **kogany**, the fork of
Zakura (a Rust Zcash full node from the Zebra lineage) that becomes the third Ycash node line.

- [`kogany-yellowback-plan.md`](kogany-yellowback-plan.md) — **the plan** (revision 1, 2026-11-01): owner decisions K-1…K-19, waves W0–W9 with chunks and gates, budgets, CI, estimate, mapping §24 rows.

Surveys (2026-11-01, inputs to the plan):

- [`surveys/a-zakura-architecture.md`](surveys/a-zakura-architecture.md) — lane A: Zakura's validation layers, upgrade model, script crate, state and mempool, and the Yellowback hook table.
- [`surveys/b-ycash-network-on-zakura.md`](surveys/b-ycash-network-on-zakura.md) — lane B: what makes kogany a Ycash node (branch IDs, Equihash 192,7, YDF, checkpoints, P2P) and the crate-fork options.
- [`surveys/c-yellowback-delta-inventory.md`](surveys/c-yellowback-delta-inventory.md) — lane C: the C++ Yellowback/vault delta classified for a wallet-less Rust node, client dependencies and layer order.
- [`surveys/d-minimalism-future-compat.md`](surveys/d-minimalism-future-compat.md) — lane D: placing Vault between Canopy and NU5 so NU5/NU6/NU7/Tachyon stay enable-able later.
- [`surveys/e-verification-strategy.md`](surveys/e-verification-strategy.md) — lane E: vector replay, the mixed-line regtest harness, kogany CI and the wave → gate matrix.
