# INFO — W3-Y-10, W3-Y-11 — Attestor operational notes: the u16 `seq` cliff belongs in the attestor guide; `attest-signed.dat` is as critical as the key (seed restores), with an on-chain-history guard for restored nodes

**Repos / branches to change.** `ycash-dd` and `ycash6` (`doc/yellowback-attestor.md` is byte-identical on both; `src/yellowback/txbuilder.cpp` / `src/rpc/yellowbackwallet.cpp` differ only in 6.x spellings): branch `fix/W3-Y-10-11-attestor-ops`. Docs, plus one optional wallet-side guard (no consensus change).
**Audit source.** `docs/audits/quantum-vault-ecosystem-wave3/03-yellowback-module.md:246-260` (W3-Y-10, W3-Y-11); `docs/audits/quantum-vault-ecosystem-wave3/verification/03-verification.md:191-199` (both confirmed Info; W3-Y-10 is unit-tested at `yellowback_state_tests.cpp:2963-2976`). Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:93` (STILL OPEN, Δ-free); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`, none of which this report cites.
**Status:** pending

## 1. Finding

**W3-Y-10.** Once 65,536 `SET_JOIN`s of the attestor set have been mirrored, every further join is `attestor-seq-exhausted` (`src/yellowback/state.cpp:1017`) and the set can never admit a member again short of a network upgrade. Not reachable at today's parameters (each join needs a ≥ 10,000 YEC bond and the exit delay; `doc/yellowback.md:100-106` estimates ≥ ~1.5 years of full-supply churn), and it is tested; but `doc/yellowback.md:120-124` (ycash6 `:121-125`) is the only place it is stated — the operator guide that attestors read does not mention it.

**W3-Y-11.** `SignAttestationGuarded` (`txbuilder.cpp:1805-1853` dd / `:1966-2014` ycash6) keys its sign-once guard on `(seq, citedHeight, block hash)` in `<datadir>/yellowback/attest-signed.dat`. An operator who restores from the **seed** (the file is not derived from it), or loses the file, can sign a second price for a cited height and is ejected with a frozen bond by EQV-1. `doc/yellowback-attestor.md:12-20` already says "two nodes holding one hot key defeat that guard … copy `wallet.dat` *and* `attest-signed.dat` together … Do not delete `attest-signed.dat`", but not that a seed restore has no record, and the node does nothing when the file is missing while the key has signed before. With HIGH-W3-Y-2's C4b, cancel statements go through the same guard, so the file also protects against cancel-statement slashing. The 07/NEW-1 salvage gap (`-salvagewallet` drops vault records) is the same class for set signatures (reported separately).

## 2. Root cause

Design: the guard is node-local by necessity (W3-Y-11) and the seq space is `u16` (W3-Y-10, `view.h` `AttestorSeqRecord`). Docs: `doc/yellowback-attestor.md` lacks both statements.

## 3. Fix options considered

- W3-Y-10: document (recommended); widening `seq` is a payload/attestation format change (74-byte attestations, vectors on both lines and in YEW/x402/yb-calibration) — not justified at today's parameters.
- W3-Y-11: (a) document (required); (b) **recommended addition:** a restore guard — when `attest-signed.dat` is missing or empty and the wallet holds a member key whose `seq` has attestations on chain, `yed_signattestation` refuses any `citedHeight ≤` the highest height that seq has been credited for (`AttestorRecord.lastAct`, mirror) plus `REF_WINDOW`, until the operator passes an explicit `-attestrestorefloor=<height>`; (c) derive the guard from chain data only — rejected: unbroadcast signatures are invisible to the chain, so (b) is a floor, not a proof.

## 4. Recommended fix

1. `doc/yellowback-attestor.md` (both lines, byte-identical): a "Known limits" paragraph — the 65,536-join cliff, with the `doc/yellowback.md:120-124` estimate and "recovery requires a network upgrade"; and in the sign-once section: "a seed restore has **no** sign-once record; restore `attest-signed.dat` from backup, or wait until the chain tip is `REF_WINDOW` past any height you may have signed, before attesting or signing a cancel statement".
2. Optional wallet guard (b): in `SignAttestationGuarded`, if the guard file was created by this start (no prior records) and the index shows `lastAct > 0` for the seq, refuse `citedHeight ≤ lastAct + REF_WINDOW` with `restore-guard` unless `-attestrestorefloor` is set; log once at start-up. Same in both lines' `txbuilder.cpp`.

## 5. Tests

Docs: none. Guard (b): a wallet unit/functional test — attest at h, delete the guard file, restart, `yed_signattestation` at `h` fails `restore-guard`, at `h + REF_WINDOW + 1` succeeds; with `-attestrestorefloor` the refusal lifts.

## 6. Acceptance criteria

Attestor guide states both limits on both lines; if (b) is taken, the test passes and `doc/yellowback-rpc.md` documents `restore-guard`.

## 7. Risks and side effects

None to consensus. Guard (b) can delay a legitimately restored attestor by up to `REF_WINDOW` blocks (minutes); the override flag covers operators who restored the file.

## 8. Effort estimate and dependencies

Docs 1 hour; guard (b) 0.5 day. Independent; coordinate the doc wording with `HIGH-W3-Y-2-ycash-yed-cancel-limit-escalation-c4b.md` (cancel statements share the guard) and `MEDIUM-W3-07-NEW-1-ycash-salvagewallet-sign-once-records.md`.
