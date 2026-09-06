# `docs/plans/`

| Document | What it is |
|---|---|
| [`yellowback-v1-development-plan.md`](yellowback-v1-development-plan.md) | **The plan.** Decision record, normative v1 protocol, code architecture in `ycash-dd`, federation coordinator, phased work plan with exit criteria, test plan, trust statement and threat model, and the later consensus-enshrinement path. Every `**OPEN**` item in `../spec/yellowback-adaptation-spec.md` is decided here. |
| [`yellowback-v1-hardening-plan.md`](yellowback-v1-hardening-plan.md) | **Hardening (DRAFT, 2026-09-06).** Wallet-side only, Tier 0: the floor-aware YED coin selector and `yed_estimatesend` (so the $1.00 change floor, C20, is steered around rather than reported), and the coin-locking gaps that let YED be spent as plain YEC by accident (`lockunspent`, running without `-yellowback`, raw transactions, key import). Inventory of every accidental-burn path in its §3; items H1–H12. |

The plan covers both forks: the node (`ycash-dd`, §1–§6) and the YecWallet GUI (`yecwallet-dd`,
§4.7 and Phase 5b), plus the single-machine multi-operator test workflow (§6.0).

Reading order for a new session: `../../AGENTS.md` → `../mapping.md` (§12 for the GUI) →
[`../why-no-consensus-change.md`](../why-no-consensus-change.md) (the plain-language rationale for
Tier 0) → this plan §1–§3 → the phase you are working on in §6.

The plan's one-line summary: **Ycash Yellowback (YED) v1 is a Tier-0 overlay** — colored transparent outputs
with `OP_RETURN` payloads, P2SH vaults of `CLTV + owner + 5-of-9 federation`, prices published by
the federation spending a k-of-n anchor UTXO, a rebuildable LevelDB index fed by the existing
`ChainTip` wallet-notifier signal, ECDSA only, and **zero lines changed in `main.cpp`,
`consensus/`, `script/`, `primitives/` or `chainparams.cpp`.** The two invariants this leaves to
the federation (burn-on-release, honest prices) are stated in §8 and the network-upgrade that would
enshrine the first of them is sketched in §9.
