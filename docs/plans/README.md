# `docs/plans/`

| Document | What it is |
|---|---|
| [`yellowback-v1-development-plan.md`](yellowback-v1-development-plan.md) | **The plan.** Decision record, normative v1 protocol, code architecture in `ycash-dd`, federation coordinator, phased work plan with exit criteria, test plan, trust statement and threat model, and the later consensus-enshrinement path. Every `**OPEN**` item in `../spec/yellowback-adaptation-spec.md` is decided here. |

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
