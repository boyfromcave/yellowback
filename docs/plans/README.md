# `docs/plans/`

| Document | What it is |
|---|---|
| [`yellowback-v2-development-plan.md`](yellowback-v2-development-plan.md) | **The current plan (DRAFT revision 6, 2026-09-10, audited twelve times across revisions 1–5 and ready for implementation): miner-enforced Yellowback.** Replaces the federation with mining pools running a patched `ycashd`: a YEC/USD quote in a coinbase tag, rolling medians, a template filter, and — after ≥ 75 % of blocks signal — a block-validity hook that rejects vault spends without the matching burn. Owner-only vault script with an anyone-can-claim path after a grace period. Decision record V1–V26 and L1–L14, normative protocol (incl. the work valve, catch-up suppression, the enforcement sunset and the owner sweep), the exact `main.cpp`/`miner.cpp` hook lines and their budget, the one-machine multi-pool test workflow with per-phase acceptance blocks and mechanical CI gates, phases 0–10. The four adjustments of revision 6 (L11–L14) are applied in the text and await the product owner's confirmation. Built from the proposal in `../reference/yellowback-miner-enforced-proposal.md` and on the reusable two-thirds of the prototype code on `feature/digidollar`, which Phase 0 strips of its federation. |
| [`archived/`](archived/) | **Inactive.** The federation design this initiative replaced (its plan, hardening plan and protocol spec). History only; not an input. |
| [`../ideation/`](../ideation/) | **Experimental ideas**, not plans (currently the interoperability proposal). Nothing there is scheduled or being built. |

The plan covers both forks: the node (`ycash-dd`) and the YecWallet GUI (`yecwallet-dd`), plus the
single-machine test workflow (its §6.0). It stands alone: every rule, constraint and finding it
relies on is stated in it, so a new session needs nothing from `archived/`.

Reading order for a new session: `../../AGENTS.md` → `../mapping.md` (§13 for the v2 hooks, §12 for
the GUI) → the v2 plan §1–§3 → the phase you are working on in its §6. Read
[`../why-miner-enforced.md`](../why-miner-enforced.md) for why v2 is enforced by pools, the
priorities that decided it and the trade-offs it accepts.

The v2 plan's one-line summary: **Yellowback v2 is a miner-enforced overlay** — a colored-output token model, a rebuildable index, a manual transaction builder and a wallet tab, with the federation replaced by pools that publish prices in their coinbases and enforce burn-on-release at the template and, after activation, at block validity; it is a soft fork carried by mining software, with about 60 inserted lines in `main.cpp`/`miner.cpp`, all behind `-yellowback`, fail-open, and switchable off.
