# `docs/plans/explorer/`

A block explorer for the vault network upgrade: first on the public fast testnet (yb-fast) at
`fastnet-explorer.ycash.team`, then as the worked example for mainnet.

| Document | What it is |
|---|---|
| [`explorer-plan.md`](explorer-plan.md) | **Revision 1 (2026-11-14), proposal; nothing implemented.** The plan: goals, where the code lives, the deployment (an EC2 host in the pool-host pattern, Terraform in `ycash-ops`, restore from the block prefix bundle), the vault and post-quantum views, phases E0–E8, the decisions EX-1..EX-10 the Yellowback lead architect has to make, and the candidate beta3 node items the explorer work has already found. |
| [`node-choice.md`](node-choice.md) | **The advice on the backend node (2026-11-14):** build on ycashd 6.22.0-beta2 now, keep the explorer node-agnostic, add koganyd as a second backend later. The evidence: source reading and live read-only probes of both nodes at the same mainnet tip, and of the fast testnet. |

Reference: `ref/inzyght` (`miodragpop/inzyght`, `main` @ `17f505f273`), surveyed in
[`../../mapping.md`](../../mapping.md) §25.

This plan replaces decision T-13 of [`../yellowback-testnet-plan.md`](../yellowback-testnet-plan.md)
("chain-viz plus yindex for testnet; a full explorer is a separate proposal") once EX-6 is decided:
this is that proposal.
