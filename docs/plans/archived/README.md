# `docs/plans/archived/`

**Inactive. History only.** The **federation design** of Ycash Yellowback (YED) was replaced on
2026-09-10 by the miner-enforced design ([`../yellowback-v2-development-plan.md`](../yellowback-v2-development-plan.md);
the rationale is [`../../why-miner-enforced.md`](../../why-miner-enforced.md)). Nothing in it is
an input to current work: every rule, constraint and finding the current plans rely on is stated
in those plans.

Its documents are not on `main`. They live at the tag **`archive/v1-federation`** (the workspace
as it stood at the end of that design):

```bash
git show archive/v1-federation:docs/plans/yellowback-v1-development-plan.md   # the federation plan (revision 17)
git show archive/v1-federation:docs/plans/yellowback-v1-hardening-plan.md     # wallet hardening H1–H12 (carried forward as v2 Phase 8)
git show archive/v1-federation:docs/spec/yellowback-adaptation-spec.md        # its normative protocol (superseded by ../../spec/yellowback-spec.md)
```

The prototype code built from them is the `feature/digidollar` branch in `ycash-dd` and
`yecwallet-dd`, kept as a record and never built on (AGENTS.md rule 2). Citations of the form
`archived/yellowback-v1-development-plan.md:NNNN` in the current plans refer to the file at that tag.
