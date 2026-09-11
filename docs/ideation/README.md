# `docs/ideation/`

**Experimental ideas. Not plans. Nothing here is scheduled, funded or being built.**

Documents in this directory explore directions that *might* follow the current work but have not
been adopted. They are inactive: no phase in
[`../plans/yellowback-v2-development-plan.md`](../plans/yellowback-v2-development-plan.md) depends on
them, no code should be written from them, and their assumptions may be stale relative to the
current design (several were written against the earlier federation design, now archived under
`../plans/archived/`). Treat them as input to a future decision, not as a decision.

| Document | Idea | Status |
|---|---|---|
| [`yellowback-interoperability-plan.md`](yellowback-interoperability-plan.md) | How YED could reach other chains with no overlay change: the Ycash index as ledger of record, one bespoke hop to an EVM hub, standard rails from there, an atomic-swap liquidity layer, and a trust ladder ending in a proof-verifying opcode on Ycash. | **Inactive** (proposal, 2026-09-06; written against the federation design — its escrow and attestation assumptions need re-examination under miner enforcement) |

To promote an idea: write the decision into the current plan (a `V` entry with options, decision,
cost) and move the document to `../plans/`. To retire one: move it to `../plans/archived/` with a
line in that README.
