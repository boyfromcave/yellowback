# LOW — W3-P-3, W3-P-5 (= W3-PQ-7), W3-P-6, 04/NEW-3 — State the remaining cross-line asymmetries where users and operators meet them: ZIP-401/317 relay ranking, PQ dust under `-minrelaytxfee`, PQ keys not seed-portable across lines, `-nuparams` back-fill

**Repos / branches to change:** `ycash-dd` and `ycash6` (both), new branch `fix/W3-P-3-cross-line-caveats` off `upgrade/vault` in each. Docs and RPC help text only, plus one optional regtest-only `init.cpp` message. No consensus, policy or wallet-behaviour change. The workspace gets a `docs/mapping.md` §22 row and a quantum-spec sentence.
**Audit source:** `docs/audits/quantum-vault-ecosystem-wave3/04-cross-line-parity-activation.md:163-183` (W3-P-3), `:209-226` (W3-P-5), `:228-238` (W3-P-6); `docs/audits/quantum-vault-ecosystem-wave3/verification/04-verification.md:42` (P-3), `:44` (P-5), `:45` (P-6), `:78-83` (NEW-3); `docs/audits/quantum-vault-ecosystem-wave3/02-post-quantum-crypto.md:160-169` (W3-PQ-7, the same fact as W3-P-5) and `docs/audits/quantum-vault-ecosystem-wave3/verification/02-verification.md:121-126`; `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:49`, `:52`. Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:101` (STILL OPEN, Δ-free); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`. The ycash6 release-doc citation for the 04/N-1 fee section is corrected to `:201-212`.
**Status:** pending

## 1. Finding

The consensus overlay is the same on both lines, and both auditors re-derived that. What remains is four places where the two lines behave differently by design or by stock inheritance. None of them is written down where an operator or wallet user would meet it:

- **W3-P-3 (relay ranking).** ycash-dd's ZIP-401 limiter penalises `fee < DEFAULT_FEE` (1,000 zat) with `MIN_TX_COST`/`LOW_FEE_PENALTY` 4,000/16,000. ycash6 (stock 6.20.0) penalises `fee < tx.GetConventionalFee()` (ZIP-317) with 10,000/40,000, and has the opt-in `-txunpaidactionlimit`. Both node wallets already pay the ZIP-317 conventional fee for PQ inputs. A third-party flat-fee PQ spend (1,000 zat) is accepted by both lines but is the first evicted on a ycash6 node under `-mempooltxcostlimit` pressure, and it is refused under `-txunpaidactionlimit=0`. The operator caveat is already in `ycash6/doc/yellowback-release.md:201-212` (from 04/N-1). The client-facing fee documentation (`yed_estimatefee`, the TOK-PQ builder notes) does not tell external builders (YEW, x402, hand-built spends) to target the conventional fee.
- **04/NEW-3 (PQ dust).** ycash-dd prices TX_PQPKH/TX_PQCHANNEL dust at the operator's `::minRelayTxFee`. ycash6 prices it at the fixed `ONE_THIRD_DUST_THRESHOLD_RATE` (100 zat/kB, which equals the default `-minrelaytxfee`). Defaults agree. A ycash-dd operator who raises `-minrelaytxfee` refuses PQ outputs that ycash6 relays. Stock 4.5.0 behaviour for every output type; Info.
- **W3-P-5 / W3-PQ-7 (PQ key portability).** Both lines derive PQ keys with the same HKDF (`DerivePQSeed`, `src/pqkey.cpp`, byte-identical) but from different IKM. ycash-dd uses the 32-byte HD seed (`-hdseedfile`); ycash6 uses the 64-byte BIP39 seed (`-mnemonicfile`). This is the spec's Q5 ruling, vectored in `pq_wallet_vectors.json` with one section per line. Loss-of-access scenario: a holder of Falcon/SLH-DSA vaults or `sq…` coins who kept only the seed and migrates from the v4.5.0 line to the 6.20.0 release line cannot re-derive those keys. `z_exportwallet`'s `pqseed=` lines and `z_importpqkey` recover them, but no document says the seed alone is not enough across lines. The seed-restore bullets on both lines describe the same-line case only.
- **W3-P-6 (`-nuparams` back-fill).** ycash6 keeps upstream's regtest convenience: an unset lower upgrade takes the height of the next higher one given, except that Vault's height never back-fills NU5..NU6.2. ycash-dd (4.5.0) has no back-fill. `-nuparams=<canopy>:1 -nuparams=6d5b7a31:10` starts on ycash6 (Overwinter..Canopy at 1) and is refused on ycash-dd ("The Vault upgrade requires Sapling active…"). The shared harness passes all six Ycash upgrades explicitly (`YCASH_UPGRADE_ARGS`), so CI is unaffected. Hand-run devnets copied from one line's notes can fail on the other.

All Low or Info; no consensus effect.

## 2. Root cause

ycash-dd `da5e0fe`, ycash6 `0742e43` (re-verified):

- **P-3:** `ycash-dd/src/mempool_limit.cpp:155` (`if (fee < DEFAULT_FEE)`), `src/mempool_limit.h:22-23` (4000/16000); `ycash6/src/mempool_limit.cpp:47` (`if (fee < tx.GetConventionalFee())`), `src/mempool_limit.h:24-25` (10000/40000); `-txunpaidactionlimit` at `ycash6/src/init.cpp:563,1369-1370`, `src/zip317.h:42,54`, `src/main.cpp:2157-2166`. `mempool_limit.*` carries zero overlay delta on either line (verifier). The client fee doc is `doc/yellowback-rpc.md:1417` (`### yed_estimatefee`, both lines). The operator caveat is `ycash6/doc/yellowback-release.md:201-212`.
- **NEW-3:** `ycash-dd/src/policy/policy.cpp:153` (`GetPQDustThreshold(txout, ::minRelayTxFee)`); `ycash6/src/policy/policy.cpp:184` (`GetPQDustThreshold(txout, CFeeRate(ONE_THIRD_DUST_THRESHOLD_RATE))`), the comment at `:401`, `src/policy/policy.h:116` (`ONE_THIRD_DUST_THRESHOLD_RATE = 100`).
- **P-5 / PQ-7:** `ycash-dd/src/wallet/wallet.cpp:412-443` (`GetHDSeed` → 32-byte `RawSeed()`), `ycash6/src/wallet/wallet.cpp:524-537` (`GetMnemonicSeed().value().RawSeed()`, 64 bytes); `src/pqkey.cpp:69-80` (identical). The vectors are `src/test/data/pq_wallet_vectors.json` (`hdSeed` and `mnemonic` sections) and `ycash-dd/src/test/pq_wallet_tests.cpp:146-156`. The docs that omit the caveat: `ycash-dd/doc/yellowback-rpc.md:173-178` and `ycash6/doc/yellowback-rpc.md:173` / `ycash6/doc/yellowback-release.md:188-193` (the seed-only restore bullets), and the `getnewaddress` help (`ycash-dd/src/wallet/rpcwallet.cpp:171-177`; ycash6 equivalent).
- **P-6:** `ycash6/src/init.cpp:1484-1510` (back-fill loop with `if (i != Consensus::UPGRADE_VAULT)`), `:1512-1530` (R-A3 checks); `ycash-dd/src/init.cpp:1326-1357` (no back-fill), `:1359-1370` (the Vault-below-Sapling `InitError`). The devnet docs: `ycash-dd/doc/yellowback-devnet.md:83-101`, `ycash6/doc/yellowback-devnet.md:95-96`.

## 3. Fix options considered

1. **Make the behaviour identical in code.** For P-3, port ZIP-317 ranking to dd, or revert 6.20.0's to the flat fee. For NEW-3, make one line follow the other's dust rate. For P-5, derive PQ keys from the same IKM on both lines. For P-6, add the back-fill to dd. Every one of these touches stock relay policy or wallet derivation, and P-5 would change every existing PQ key on one line, which the Q5 ruling and the vectors pin. Rejected: the asymmetries are inherited (P-3, NEW-3, P-6) or designed (P-5). The workspace's minimal-change rule favours documenting them.
2. **Document each asymmetry once, where the affected person reads it, and record it in the crosswalk.** Recommended (it is what both auditors and verifiers propose).
3. For P-6 only, an optional code nicety: when dd refuses a Vault height because Sapling is unset, say in the `InitError` that ycash-dd does not back-fill and that every `-nuparams` must be given. Regtest-only, no behaviour change. Optional.

## 4. Recommended fix

Both lines unless stated. Wording is a suggestion; keep each to one or two sentences.

1. **P-3: client fee guidance** in `doc/yellowback-rpc.md`, under `### yed_estimatefee` (`:1417`), and in the TOK-PQ / PQ-spend builder notes of the same file:
   > Transactions built outside this wallet should pay at least the ZIP-317 conventional fee (`MARGINAL_FEE` 500 zat per logical action, 2 grace actions, inputs counted by size in 150-byte units; ~27,000 zat for an SLH-DSA input, ~5,500 for a Falcon one). The 1,000-zat flat floor is accepted by both node lines, but 6.20.0 nodes rank it first for eviction under `-mempooltxcostlimit` pressure and refuse it under `-txunpaidactionlimit=0` (audit W3-P-3).

   Mirror the figures from `ycash6/doc/yellowback-release.md:201-212` so the two documents cannot disagree, and cite that section. Clients: YEW, x402-ycash and lightwalletd already have fee notes from LOW-04-N-1 (done). Check that they cite the conventional fee, and file a one-line client issue if not.
2. **NEW-3: dust** in `ycash-dd/doc/yellowback-rpc.md` next to the `-sendchangeback` bullet (`:179-180`), which already names `GetPQDustThreshold`:
   > On this line the PQ dust threshold follows `-minrelaytxfee`; the 6.20.0 line uses a fixed 100 zat/kB. Raising `-minrelaytxfee` above the default makes this node refuse small PQ outputs that 6.20.0 nodes relay (audit 04/NEW-3).

   And in `ycash6/doc/yellowback-release.md`'s operator section: "PQ dust is priced at the fixed rate whatever `-minrelaytxfee` says (stock 6.20.0 behaviour; v4.5.0 nodes follow the flag)".
3. **P-5 / PQ-7: key portability**, three places per line:
   - The seed-only restore bullet (`ycash-dd/doc/yellowback-rpc.md:173`; `ycash6/doc/yellowback-rpc.md:173` and `ycash6/doc/yellowback-release.md:188`). Append:
     > Post-quantum keys are derived from **this line's** seed format (v4.5.0: the 32-byte HD seed; 6.20.0 and YEW: the 64-byte BIP39 seed). The same backup does not reproduce them on the other node line: carry PQ keys across lines with `z_exportwallet` / `importwallet` (the `pqseed=` lines) or `z_importpqkey`, never with the seed alone. A copied `wallet.dat` keeps its stored keys.
   - The `getnewaddress` help (`rpcwallet.cpp:171-177`) and `yed_getnewaddress "pq"` / `"pqowner"` help. Add one line: `"Back the key up with z_exportwallet (pqseed=): the wallet seed reproduces it on this node line only."`
   - The release notes of the gate-passing release (ycash6 `doc/yellowback-release.md` release-notes section, and dd `doc/release-notes.md`): a "Migrating between node lines" bullet with the same sentence.

   This closes W3-PQ-7 too; INFO-W3-PQ-6-PQ-10 points here.
4. **P-6: back-fill.** `ycash-dd/doc/yellowback-devnet.md` and `doc/yellowback-mining.md` (at the `-nuparams=6d5b7a31:<h>` mention, `:33`) get:
   > ycash-dd does not back-fill lower upgrades from a higher `-nuparams` (the 6.20.0 line does, except that Vault never back-fills NU5..NU6.2): always pass all six Ycash upgrades plus Vault, as the functional tests do (`YCASH_UPGRADE_ARGS`).

   ycash6's devnet doc gets the mirror sentence. Optional code (option 3), dd only, regtest only: in `init.cpp:1366-1369`, when `NetworkIDString() == "regtest"` and Sapling is unset, append " (ycash-dd does not back-fill: pass -nuparams for every lower upgrade)" to the `InitError` text. `vault_upgrade.py`'s R-A3 cell asserts the message prefix; check that it uses a prefix match, or update it.
5. **Crosswalk and spec.** `docs/mapping.md` §22: one row per item ("ZIP-401 trigger", "PQ dust rate", "PQ IKM per line", "`-nuparams` back-fill") with the citations above and "documented, not changed (audit W3-P-3/5/6, 04/NEW-3)". `docs/plans/yellowback-quantum-spec.md` Q5 ("as implemented"): add "a seed does not carry PQ keys across node lines; `pqseed=` does".

Consensus footprint: none. Policy footprint: none (text only, except the optional regtest message).

## 5. Tests

- None functional. The behaviours are already tested: ZIP-401/317 by ycash6's `yellowback_fee` / `yellowback_mempool_limits`; PQ IKM per line by `pq_wallet_tests` and `gen_pq_wallet_vectors.py --check`; the dd R-A3 refusal by `vault_upgrade.py`.
- If the optional `InitError` text lands: re-run `vault_upgrade.py` on dd (its R-A3 cell asserts the start-up failure), and adjust the expected message if it matches exactly.
- `qa/yellowback-audit.sh` `leg_documents` / the RPC-contract legs: if `yed_getnewaddress` help text is part of the generated RPC contract (`doc/yellowback-rpc-contract.json`, `leg_contract`), regenerate the contract through the workspace generator (`make spec`) on both lines and commit it in the same PR.

## 6. Acceptance criteria

- `doc/yellowback-rpc.md` (both lines) states the conventional-fee target for external builders and the PQ seed-portability caveat; ycash-dd's states the `-minrelaytxfee` dust behaviour.
- `getnewaddress` / `yed_getnewaddress` PQ help says the seed reproduces the key on this line only (both lines); the RPC contract is regenerated if affected and the contract legs pass.
- The devnet/mining docs on both lines tell the reader to pass every `-nuparams`.
- The release-notes bullet is present in ycash6's release doc (and dd's `release-notes.md`).
- `docs/mapping.md` §22 has the four rows; the quantum spec's Q5 has the portability sentence.

## 7. Risks and side effects

- None to consensus, relay or wallet behaviour.
- Help-text changes can ripple into the RPC contract JSON (generated); regenerate rather than hand-edit.
- The fee figures in the docs must track the ZIP-317 constants (`Zip317ConventionalFee` on dd, `zip317.h:16-19` on ycash6). Cite the constants instead of restating numbers where possible.

## 8. Effort estimate and dependencies

- ~0.5 day across both lines (docs + help + contract regeneration). One reviewer.
- No dependency. INFO-W3-PQ-6-PQ-10-02-N-1-N-2 defers W3-PQ-7 to this report. Related history: LOW-04-N-1 (done; ZIP-317 fee guidance for clients).
