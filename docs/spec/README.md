# `docs/spec/`

**Start with [`yellowback-risk-profile.md`](yellowback-risk-profile.md).** It states what the
`upgrade/vault` node enforces today, cited to the source, and how Yellowback's collateral model
was deliberately changed from DigiDollar's after a review of DigiDollar's risk profile.

**Which spec is current.** Two generated spec copies exist and they describe different lines:

| Line | Where the generated spec lives | Collateral it specifies |
|---|---|---|
| **`upgrade/vault`, the line being built** (the vault network upgrade with the in-term claims overlay) | `ycash-dd/doc/yellowback-spec.md` and `ycash6/doc/yellowback-spec.md`, written by `make spec-in-term` from the upgrade plan §10 + §15 and the in-term plan §3–§4; its first line names both plans | A 30–90 d **300 %**, B 91–180 d **400 %**, C 181–365 d **500 %**; claims at any height below 125 %; owner redeem at any height |
| `harden/yellowback`, the no-upgrade fallback (= v3) | `yellowback-spec.md` **in this directory**, written by `make spec` from the v2 and v3 plans | A 30–90 d 500 %, B 90–365 d 400 %, C 1–5 y 300 %; claims after the term only |

The file in this directory is the fallback line's. **Do not read its term-class table as the
current design**: on `upgrade/vault` the ratios run the other way and the terms stop at one year.
The copies are not merged into one because each is hashed and checked against its own plans.

| Path | What it is |
|---|---|
| `yellowback-risk-profile.md` | Hand-written. The collateral model as implemented on `upgrade/vault` (both node lines, cited to `src/yellowback/params.cpp` and `state.cpp`), DigiDollar's model beside it, the calibration findings and the Ycash lead Yellowback architect's decisions that changed it, and the residual risk. Update it when the parameters change. |
| `upstream-digibyte/` | Verbatim copies of the DigiDollar design docs from `ref/digibyte` at tag **v9.26.5** (`05b50e229d`). Reference material — **do not edit**. They describe DigiByte's design: where they describe collateral (less for a longer lock, no liquidation before the timelock), Yellowback does the opposite on purpose. The full set (97 more docs) lives in `ref/digibyte/digidollar/` and the repo root. |
| `yellowback-spec.md` | **The protocol of the v3 / `harden/yellowback` line**, reproduced verbatim so rule identifiers (`MINT-1`, `RED-4`, `ACT-6`, …) have one citable home: §3 of [`../plans/yellowback-v2-development-plan.md`](../plans/yellowback-v2-development-plan.md), then the §8.1 trust statement (v2's, followed by v3's without its heading), then a `## v3 delta` heading and §3 of [`../plans/yellowback-v3-development-plan.md`](../plans/yellowback-v3-development-plan.md) (v2 rules where v3 is silent). On `upgrade/vault` it is history and the base of the fallback; the rule identifiers it defines are still the ones the upgrade plan §15 and the in-term plan §4 amend. **Generated, never edited:** `make spec` runs `scripts/extract-spec.sh`, which writes this file and, for a tree on the harden line, the byte-identical node copies `ycash-dd/doc/yellowback-spec.md` and `ycash6/doc/yellowback-spec.md`, and the RPC contract (from the plans' §4.5 and `ycash-dd/doc/yellowback-rpc.md`) as `ycash-dd/doc/yellowback-rpc-contract.json`, `yecwallet-dd/docs/yellowback-rpc-contract.json` and `lightwalletd-dd/testdata/yellowback/contract.json` (byte-identical), plus the 6.20.0 line's `ycash6/doc/yellowback-rpc-contract.json` from its own `ycash6/doc/yellowback-rpc.md` (identical except where that document notes 6.20.0 behaviour). Line 1 is `Source: … revision N + … revision M; sha256: <hash of the body>`; `make spec-check` (run by `make status`) fails when any copy is stale, the workspace CI runs `scripts/extract-spec.sh --check-workspace` (this file only), and the fork's CI re-checks the hash locally with `sed '1,/^---$/d' doc/yellowback-spec.md \| sha256sum`. A tree on `upgrade/vault` gets the upgrade line's copy instead (`make spec-in-term`, and the later `spec-quantum` / `spec-fees` contract overlays), from the upgrade plan and the in-term plan. The format of every output is documented at the top of `scripts/extract_spec.py`. Rationale, decisions and the work plan stay in the plans; the spec of the retired federation design is kept at tag `archive/v1-federation`. |

Read `../mapping.md` before either. It is the mechanism-level crosswalk; these are the
protocol-level specs.
