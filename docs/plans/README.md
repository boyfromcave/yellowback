# `docs/plans/`

| Document | What it is |
|---|---|
| [`yellowback-v2-development-plan.md`](yellowback-v2-development-plan.md) | **Delivered (revision 6, 2026-09-10, audited twelve times; Phases 0–8 implemented on `feature/yellowback-sf`, which is now the diff baseline v3 measures against): miner-enforced Yellowback.** Replaces the federation with mining pools running a patched `ycashd`: a YEC/USD quote in a coinbase tag, rolling medians, a template filter, and — after ≥ 75 % of blocks signal — a block-validity hook that rejects vault spends without the matching burn. Owner-only vault script with an anyone-can-claim path after a grace period. Decision record V1–V26 and L1–L14, normative protocol (incl. the work valve, catch-up suppression, the enforcement sunset and the owner sweep), the exact `main.cpp`/`miner.cpp` hook lines and their budget, the one-machine multi-pool test workflow with per-phase acceptance blocks and mechanical CI gates, phases 0–10. The four adjustments of revision 6 (L11–L14) are applied in the text and await the product owner's confirmation. Built from the proposal in `../reference/yellowback-miner-enforced-proposal.md` and on the reusable two-thirds of the prototype code on `feature/digidollar`, which Phase 0 strips of its federation. |
| [`yellowback-v3-development-plan.md`](yellowback-v3-development-plan.md) | **The current plan (revision 1, 2026-09-13; in implementation on `feature/yellowback-price-attest` — Phases A0–A5 merged in both forks, A4's devnet and A6–A8 remain; its own status table at the top is authoritative): bond-weighted price attestation.** A delta on v2 that adds a second price population — bonded attestors whose signed prices a mint or claim carries in the scriptSig of a P2SH carrier input — combined with the pool medians by `min`/`max`. No new line in `main.cpp`, `miner.cpp`, `rpc/mining.cpp` or `policy.cpp`; the agents live outside the node. Decision record W1–W14, the protocol delta (§3), the concurrent one-machine test workflow (§6.0), phases A0–A8. Implements [`../reference/yellowback-price-attestation.md`](../reference/yellowback-price-attestation.md) revision 6 after its audit. Branch `feature/yellowback-price-attest`. |
| [`archived/`](archived/) | **Inactive.** The federation design this initiative replaced (its plan, hardening plan and protocol spec). History only; not an input. |
| [`../ideation/`](../ideation/) | **Experimental ideas**, not plans (currently the interoperability proposal). Nothing there is scheduled or being built. |

Both plans cover both forks: the node (`ycash-dd`) and the YecWallet GUI (`yecwallet-dd`), plus the
single-machine test workflow (§6.0 of each; v3's adds the concurrent-agent rules). **v3 is a delta:
where it is silent, v2 rules**, so an implementer needs both — but neither needs `archived/`.

Reading order for a new session: `../../AGENTS.md` → `../mapping.md` (§13 for the v2 hooks, §12 for
the GUI, §14 for the v3 price-attestation rows) → the v3 plan's status table and §1–§3 → the chunk
you are working on in its §6, with the v2 plan §3 beside it for anything v3 does not restate. Read
[`../why-miner-enforced.md`](../why-miner-enforced.md) for why v2 is enforced by pools, and
[`../reference/yellowback-price-attestation.md`](../reference/yellowback-price-attestation.md) for
why v3 adds a second price population.

The v3 plan's one-line summary: **attestors post a CLTV bond once and sign prices off-chain**; a mint or claim carries four to six of those signatures in the scriptSig of a small P2SH *carrier* input, and enforcing nodes combine the bond-weighted quantile with the existing pool medians by `min` (mints) and `max` (claims) — so moving the price in the direction that pays needs a hashpower majority *and* a bond-weighted majority of the selected attestors at once. No new line in any consensus, mining or policy file.

The v2 plan's one-line summary: **Yellowback v2 is a miner-enforced overlay** — a colored-output token model, a rebuildable index, a manual transaction builder and a wallet tab, with the federation replaced by pools that publish prices in their coinbases and enforce burn-on-release at the template and, after activation, at block validity; it is a soft fork carried by mining software, with about 60 inserted lines in `main.cpp`/`miner.cpp`, all behind `-yellowback`, fail-open, and switchable off.
