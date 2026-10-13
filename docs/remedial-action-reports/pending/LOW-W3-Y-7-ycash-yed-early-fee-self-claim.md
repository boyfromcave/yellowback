# LOW — W3-Y-7 (+ the A-8 part of 03/NEW-3) — An owner whose vault is claimable avoids the IT-9′ early-redeem fee by self-claiming through the APP branch: document it as accepted; correct design A-8

**Repos / branches to change.** Documentation only: `ycash-dd` and `ycash6` `doc/yellowback-spec.md` / `doc/yellowback.md` (owner-facing fee text), workspace `docs/plans/yellowback-in-term-claims-plan.md` (IT-9′/D-IT-16), `yellowback-cancel-limit-design.md` §3 A-8 (shared with `MEDIUM-W3-Y-3-ycash-yed-ratelimit-pin-cancel-design-corrections.md`), `make spec`. Branch `fix/W3-Y-7-early-fee-doc`. No code change recommended.
**Audit source.** `docs/audits/quantum-vault-ecosystem-wave3/03-yellowback-module.md:211-220` (W3-Y-7); `docs/audits/quantum-vault-ecosystem-wave3/verification/03-verification.md:169-175` (confirmed Low: `state.cpp:648` charges the early fee only when `!claim`; a path-(a) claim takes the whole collateral, so a self-claim pays FEE-1′ only), `:240-243` (NEW-3: design A-8 wrong). Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:91` (STILL OPEN, Δ-free); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`, none of which this report cites; the design doc `:243-246` is unchanged.
**Status:** pending

## 1. Finding

IT-9′ charges an owner redeem before `lockHeight` `earlyRedeemFeeBps[class]` of the debt (5 % / 2.5 % / 1 %) on top of FEE-1′ (`src/yellowback/state.cpp:648-652`, `params.cpp:63`). A claim pays FEE-1′ only (plus the attestor half when armed). IT-2 opens the APP branch from the block after the mint, so an owner whose vault is already claimable — under 125 % at `pClaim`, or under 105 % at `pEmerg` with a standing notice — can burn its own debt through a claim whose claimant intent pays its own (or any) key, wait `CLAIM_DELAY` and release, paying ~1 % instead of up to 5 % + 1 %. On path (a) the claimant cap (125 % margin) is at least the collateral, so the owner-as-claimant gets the whole collateral back.

The harm is small: the vault must already be claimable, i.e. the owner is exiting a position the system wants closed, and anyone else could liquidate it at the same moment. But the early fee's stated purpose (term commitment) is bypassed exactly in the crash window, and the design doc's A-8 claims "No path lets an owner avoid the early-redeem fee through a self-claim plus cancel" — true only of the cancel variant (NEW-3).

## 2. Root cause

At `ycash-dd` `da5e0fe` / `ycash6` `0742e43`: `src/yellowback/state.cpp:648-652` (`!claim && H < lockHeight` guard); `yellowback-cancel-limit-design.md:243-246` (A-8).

## 3. Fix options considered

| | A — **document as accepted** | B — charge the early fee on a claim whose claimant intent pays the owner's key | C — charge the early fee on every in-term claim |
|---|---|---|---|
| Effect | States the behaviour; no consensus change. | Trivially evaded: the owner names any other key as the claimant recipient (the recipient is free). | Charges a third-party liquidator the owner's term penalty, which deters exactly the liquidations the system needs in a crash. |
| Verdict | **Recommended.** | Rejected (cosmetic). | Rejected (harms liquidation). |

## 4. Recommended fix

1. In-term plan (IT-9′ / D-IT-16 row): "The early fee applies to the owner's redeem path only. An owner whose vault is already claimable may instead liquidate it through a claim and pay FEE-1′ only; accepted (W3-Y-7): a claim is open to anyone at that point, so the early fee cannot bind it without taxing third-party liquidations."
2. Design doc A-8 (`:243-246`): replace the last sentence with "A plain self-claim (no cancel) of a claimable vault avoids IT-9′; accepted (W3-Y-7). The claim-plus-cancel variant does not: the burn is refunded but FEE-1′ is not, and CAN-3 holds any residual." **Owned by `MEDIUM-W3-Y-3-ycash-yed-ratelimit-pin-cancel-design-corrections.md` §4 step 4**, which applies this exact wording in its Revision 2 commit; do not edit the design doc from this report.
3. Owner-facing doc (`doc/yellowback.md` fees section): one sentence with the same content.

## 5. Tests

Optional, documents the behaviour: a unit test that an in-term path-(a) claim by the owner's key before `lockHeight` passes with FEE-1′ only (no `bad-redeem-early-fee`), and that the owner's redeem at the same height without the early fee fails `bad-redeem-early-fee`.

## 6. Acceptance criteria

The three texts updated and `make spec-check` clean; optional test present.

## 7. Risks and side effects

None.

## 8. Effort estimate and dependencies

2 hours. Coordinate the A-8 edit with `MEDIUM-W3-Y-3-ycash-yed-ratelimit-pin-cancel-design-corrections.md`.
