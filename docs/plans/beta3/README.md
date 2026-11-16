# `docs/plans/beta3/`

The plan for the beta3 release train (`v6.22.0-beta3`) and the fast-testnet pool that pays
shielded miners.

| Document | What it is |
|---|---|
| [`beta3-plan.md`](beta3-plan.md) | **Revision 6 (2026-11-16), in progress (Wave 4 done but for five open pull requests; Wave 5 next).** Eighteen requested items and two process requirements ordered into six waves for a team of agents: what runs in parallel and what must be sequential, the reference order ycash-dd → ycash6 → kogany, the review gates, the decisions the Yellowback lead architect took (B3-D1..D10), and the two success criteria: the beta3 releases, and the yolo pool on the fast testnet paying four rented miners at once (transparent, two Sapling, post-quantum) in full. Its status block is the record during the run. |

Beside it, the design notes written in Wave 0 (each is the specification its chunk implements):

| Document | What it is |
|---|---|
| [`getcoinbasetemplatefor.md`](getcoinbasetemplatefor.md) | The `getcoinbasetemplatefor` call (item 3): request, response, errors, yolo's paired jobs; decisions D-1..D-6 |
| [`value-pools.md`](value-pools.md) | Chain value pools by address type (item 2): `transparentPools` beside `valuePools` |
| [`bundle-parts.md`](bundle-parts.md) | Snapshot bundles in parts under 50 GB (item 9) |
| [`reorg-parity.md`](reorg-parity.md) | kogany's reorganisation depth and check order against ycashd's (item 12), R1-R6 approved |
| [`rpc-contract-delta.md`](rpc-contract-delta.md) | The `rpcversion` 10 contract delta the generator reads (`make spec-beta3`, B3-D5) |
| [`beta3-release-announcement.md`](beta3-release-announcement.md) | The draft announcement the release pages draw on |
| [`release-notes-draft.md`](release-notes-draft.md) | The combined release notes of the train (R-2): upgrade actions first, then operators, pools and miners, wallet users, explorers, other clients, the `rpcversion` 10 table and the known limits; two values filled in and one sentence confirmed at the cut |
| [`pool-demonstration.md`](pool-demonstration.md) | The runbook of the four-miner demonstration (§9, step D-1): preconditions, the demonstration wallet, the one-card username check, the run, the acceptance table; its §9 becomes the record |
