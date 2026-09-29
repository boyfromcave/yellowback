# `docs/spec/`

| Path | What it is |
|---|---|
| `upstream-digibyte/` | Verbatim copies of the DigiDollar design docs from `ref/digibyte` at tag **v9.26.5** (`05b50e229d`). Reference material — **do not edit**. The full set (97 more docs) lives in `ref/digibyte/digidollar/` and the repo root. |
| `yellowback-spec.md` | **The normative protocol of Ycash Yellowback (YED)** — §3 of [`../plans/yellowback-v2-development-plan.md`](../plans/yellowback-v2-development-plan.md) plus its §8.1 trust statement, reproduced verbatim so rule identifiers (`MINT-1`, `RED-4`, `ACT-6`, …) have one citable home. **Generated, never edited:** `make spec` runs `scripts/extract-spec.sh`, which writes this file, the byte-identical fork copy `ycash-dd/doc/yellowback-spec.md`, and the RPC contract `yellowback-rpc-contract.json` (from the plan's §4.5 and, once it exists, `ycash-dd/doc/yellowback-rpc.md`) into `ycash-dd/doc/` and `yecwallet-dd/docs/`. Line 1 is `Source: … revision N; sha256: <hash of the body>`; `make spec-check` (run by `make status`) fails when any copy is stale, and the fork's CI re-checks the hash locally with `sed '1,/^---$/d' doc/yellowback-spec.md \| sha256sum`. The format of every output is documented at the top of `scripts/extract_spec.py`. Rationale, decisions and the work plan stay in the plan; the spec of the retired federation design is under `../plans/archived/`. |

Read `../mapping.md` before either. It is the mechanism-level crosswalk; these are the
protocol-level specs.
