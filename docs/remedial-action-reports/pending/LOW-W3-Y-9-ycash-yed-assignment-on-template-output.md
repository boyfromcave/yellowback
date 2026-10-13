# LOW — W3-Y-9 — Before the Falcon height a REDEEM/TRANSFER/MINT assignment may name a vault-template output (a claim's own intent), creating a token that silently burns: refuse template scripts as YED holders at every height

**Repos / branches to change.** `ycash-dd` and `ycash6`, branch `fix/W3-Y-9-template-holder` off `upgrade/vault` (or the next commit of `fix/W3-03-NEW-1-residual` — same golden window): `src/yellowback/script.cpp` (one clause), `qa/rpc-tests/test_framework/yellowback_model.py` (mirror), `src/test/yellowback_state_tests.cpp`, `doc/yellowback-spec.md` (TOK-PQ / holder text), workspace `yellowback-quantum-plan.md` TOK-PQ note + `make spec`.
**Audit source.** `docs/audits/quantum-vault-ecosystem-wave3/03-yellowback-module.md:237-244` (W3-Y-9); `docs/audits/quantum-vault-ecosystem-wave3/verification/03-verification.md:183-189` (partially confirmed, Low, regtest only: any script is a holder pre-Falcon and assignments exclude only the fee vout; the burn-at-release tail not re-traced). Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:92` (STILL OPEN, Δ-free); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`, none of which this report cites (`script.cpp:130-132` still returns true before the Falcon height).
**Status:** pending

## 1. Finding

`HolderAllowed` accepts **any** script before `pqFalconHeight` (`src/yellowback/script.cpp:130-132`). `RedVerdict` checks each assignment's range and holder (`src/yellowback/state.cpp:600-606`) and later excludes only the fee vout from assignments (`:643`). So on a claim, a pre-Falcon assignment may name the claim's own claimant or residual **intent** output; the module writes a `TokenRecord` on a template output (`ApplyVaultSpend`, `:741-755`). When the intent is released or cancelled, that token is spent as `yedIn` of a transaction that may carry no YED payload (`:829`), so it burns — a token the holder can never move. The same applies to a TRANSFER (`:547`) or a MINT's token output (`:419`) naming any primitive template output (a bridge-tag V created in the same transaction, for instance).

On mainnet and testnet `pqFalconHeight` is 0, so TOK-PQ already restricts holders to Falcon `TX_PQPKH` / `TX_PQCHANNEL` and this cannot happen; it is a regtest/devnet-only divergence between the "before" and "after" behaviours. Low.

## 2. Root cause

At `ycash-dd` `da5e0fe` / `ycash6` `0742e43` (byte-identical): `src/yellowback/script.cpp:130-137` (`if (!p.IsPQFalconActive(height)) return true;`), callers `state.cpp:419` (MINT token), `:547` (TRANSFER), `:605` (REDEEM/claim); `state.cpp:643` (fee-vout-only exclusion).

## 3. Fix options considered

- **A (recommended): `HolderAllowed` returns false for any vault-primitive template script (V or I, any tag) at every height.** One clause; post-Falcon it changes nothing (a template is never a `TX_PQPKH`), so mainnet/testnet behaviour is identical; pre-Falcon it closes the hole for MINT, TRANSFER and REDEEM alike.
- B: exclude the claim's `intents` vouts in `RedVerdict` only (the auditor's one-liner). Covers the claim path but not TRANSFER/MINT naming a template created in the same transaction. Rejected as narrower.

**Rule-4 check (PR body).** DigiByte does **X** = restrict DigiDollar holders to spendable key scripts, in **Y** = `ref/digibyte/src/digidollar/`, using **M** = Taproot/P2TR holder outputs. Ycash's equivalent **Z** = `HolderAllowed` (TOK-PQ), which before the Falcon height admits any script, including template outputs whose spends carry no YED payload. So **W** = refuse template scripts as holders at all heights. **Ladder:** a module rule on an existing check; no state.

## 4. Recommended fix

1. `script.cpp:130`: first lines `vault::VaultParams vp; vault::IntentParams ip; if (vault::ParseVault(script, vp) || vault::ParseIntent(script, ip)) return false;` (the primitive's parsers, `src/vault/template.h:120-121`; any tag). Keep the Falcon branch as is.
2. Model: the same clause in `yellowback_model.py`'s `holder_ok` (`:2658`).
3. Spec: TOK-PQ text "a vault-template output is never a YED holder (any height)".
4. Golden: run `--write-golden`; the fixture is not expected to assign to a template (hash unchanged). If HIGH-W3-03-NEW-1 regenerates anyway, add one rejected block (`bad-yed-holder`, a pre-Falcon claim assigning to its own residual intent) in that window.

## 5. Tests

Unit (both lines): pre-Falcon claim assigning to its claimant intent → `bad-yed-holder`; pre-Falcon TRANSFER assigning to a V output created in the same transaction → `bad-yed-holder`; post-Falcon unchanged (existing TOK-PQ tests at the `GOLDEN_FALCON` blocks still pass); model unit mirror.

## 6. Acceptance criteria

Template scripts are never holders on either line at any height; mainnet/testnet behaviour unchanged (no golden hash change unless a rejected block is added deliberately); spec updated.

## 7. Risks and side effects

No public-network effect. Regtest/devnet chains that assigned YED to a template before the Falcon height become invalid on replay — none exist outside tests. Wallets never build such assignments.

## 8. Effort estimate and dependencies

2-3 hours plus review gate (it is a module consensus clause). Prefer to land inside HIGH-W3-03-NEW-1's PR so the golden moves once; otherwise independent.
