# kogany planning

Plans for bringing Ycash Yellowback (YED) and the vault network upgrade to **kogany**, the fork of
Zakura (a Rust Zcash full node from the Zebra lineage) that becomes the third Ycash node line.

- [`kogany-yellowback-plan.md`](kogany-yellowback-plan.md) — **the plan** (revision 3, 2026-11-01): **all 26 decisions locked by the lead architect 2026-11-01; the sidecar is `yewd` inside `yew`** (`yew/yewd/`, a third shell on the YEW core beside `app` and `web`, not a new repository). Decisions (lead architect) K-1…K-26, waves W0–W9 with chunks and gates, and the **parity sidecar track S0–S5** (§3b): the product is kogany plus a separate wallet process on yew-core that answers the ycashd wallet RPCs, with a signer boundary, gated on the wallet RPC contracts and the 48 wallet-needing scripts. Budgets, CI, estimate, risks, mapping §24 rows. Revision 1 (same day) had the wallet on a ycash6 sidecar only; that sidecar remains the test rig. **Execution (2026-11-02):** W0–W8, W9-a, W9-c, S0–S4, KP-1..4 and PR-1/PR-2 merged on `vaults/kogany-compat`; W9-b and S5 in flight; the status block, the findings log (KF-01…KF-85) and the 2026-11-02 decisions addendum in §0 are the record.

- [`coordination-handoff.md`](coordination-handoff.md) — how a coordination agent runs the plan with parallel agents: start-up, state at handoff (2026-11-02), operating model, dependency graph and batches, gates.

- **The review package** — kogany `doc/yellowback-review.md` (W9-d, on kogany `vaults/kogany-compat`): budget actuals per wave against §4.1, the hook table with every consensus-path file and its chunk's four-part check, the dormancy and cross-line evidence, the `yewd` track, the known gaps and the §6 demonstration transcript as far as recorded runs carry it.

- [`kogany-branch-inventory.md`](kogany-branch-inventory.md) — the 603 branches GitHub copied into `boyfromcave/kogany`: the KEEP list (4) and the commands to delete the other 599 by hand (nothing deleted).

- [`ci-design.md`](ci-design.md) — the cross-line CI: the dependency graph across ycash6, kogany, yew and yolo, the artifact contracts (`node-bin`, `koganyd-bin`, `yewd-bin`; 30 days, pinned commits), what blocks and when it flips, re-run granularity, and the GitHub settings for the lead architect.

Surveys (2026-11-01, inputs to the plan):

- [`surveys/a-zakura-architecture.md`](surveys/a-zakura-architecture.md) — lane A: Zakura's validation layers, upgrade model, script crate, state and mempool, and the Yellowback hook table.
- [`surveys/b-ycash-network-on-zakura.md`](surveys/b-ycash-network-on-zakura.md) — lane B: what makes kogany a Ycash node (branch IDs, Equihash 192,7, YDF, checkpoints, P2P) and the crate-fork options.
- [`surveys/c-yellowback-delta-inventory.md`](surveys/c-yellowback-delta-inventory.md) — lane C: the C++ Yellowback/vault delta classified for a wallet-less Rust node, client dependencies and layer order.
- [`surveys/d-minimalism-future-compat.md`](surveys/d-minimalism-future-compat.md) — lane D: placing Vault between Canopy and NU5 so NU5/NU6/NU7/Tachyon stay enable-able later.
- [`surveys/e-verification-strategy.md`](surveys/e-verification-strategy.md) — lane E: vector replay, the mixed-line regtest harness, kogany CI and the wave → gate matrix.

Research notes (2026-11-01 and 2026-11-02, read-only; the first two are inputs to revision 2):

- [`research/tx-v4-vs-v5-protocol.md`](research/tx-v4-vs-v5-protocol.md) — transaction v4 versus v5: the formats (ZIP 225, ZIP 244), where each node line implements them, and the trade-offs.
- [`research/vault-on-v5-assessment.md`](research/vault-on-v5-assessment.md) — what defining the vault upgrade on v5 would take; options A–D. The Yellowback lead architect chose **D** (v4-only now, a dormant ZIP-244 message), recorded as K-21.
- [`research/pruning-assessment.md`](research/pruning-assessment.md) — Zakura's Pruned mode, ycashd `-prune` and why the vault line refused it, the `H_V` height floor, kogany retention and size projections (2026-11-02); decisions 1–8 taken by the Yellowback lead architect the same day (§6a), carried out as PR-1/PR-2 and KP-1..4.
