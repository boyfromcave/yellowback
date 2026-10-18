# Remedial action reports

Handoff documents for the agents and developers who implement fixes for the findings of the 2026-10-13
quantum / vault ecosystem security audit (two waves: seven area audits, each independently re-verified). The audit reports themselves are kept out of this repository; the `docs/audits/quantum-vault-ecosystem/...` citations inside each report refer to them and are available from the audit owner. Severities are the post-verification ones.

- `pending/` — not yet implemented. `done/` — implemented and merged on `upgrade/vault`: the file is moved, its Status line carries the UTC completion timestamp, and a closing "Completion record" lists the commits.
- **File name:** `<SEVERITY>-<audit-id>-<repo>-<slug>.md`, severity first so a directory listing sorts by priority:
  `HIGH-03-H-1-ycash-yed-claim-cancel-refund.md`, `MEDIUM-01-V-2-ycash-set-sig-anyonecanpay.md`,
  `LOW-02-PQ-1-ycash-falcon-drbg-wipe.md`. Severity ∈ `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`. Tightly coupled
  findings that must land as one change share one report (list every audit ID in the header).
- **Branch rule:** every fix goes on a new branch in the component repo (suggested: `fix/<audit-id>-<slug>` off
  `upgrade/vault`); never commit to `upgrade/vault`, `harden/yellowback`, a `-legacy` branch or `ref/`.
  Node fixes land on **both** node lines (`ycash-dd` and `ycash6`) together; consensus changes carry the rule-4
  four-part check and the tier answer in the PR body and go through the review gate (workspace `CLAUDE.md` rule 2).

## Report template

```
# <SEVERITY> — <audit IDs> — <title>
Repos / branches to change · Audit source (report + verification file:line) · Status: pending
## 1. Finding (what is wrong, in two paragraphs, with the exploit or failure scenario)
## 2. Root cause (the exact code, file:line at the audited commit)
## 3. Fix options considered (with the one rejected by verification, if any, and why)
## 4. Recommended fix (step by step; diff-level guidance; consensus footprint; both node lines; spec/plan edits)
## 5. Tests (new or changed tests that prove the fix and would have caught the defect; golden/vector regeneration)
## 6. Acceptance criteria (how a reviewer knows it is done)
## 7. Risks and side effects (chain split, vector freeze, client impact, rollout order)
## 8. Effort estimate and dependencies (other reports that must land first)
```

## Index of reports (2026-10-13; 44 reports: 3 HIGH, 10 MEDIUM, 28 LOW, 3 INFO; all 44 in `done/` as of 2026-10-13)

Recommended landing order (dependencies are repeated inside each report):
1. **Node, consensus-bearing (both lines, review gate):** `LOW-03-T-1` (golden process) → `HIGH-03-H-1` → `MEDIUM-01-V-1` → `MEDIUM-01-V-2` (vectors regenerate; re-pin YEW/Hawkeye copies afterwards) → `MEDIUM-04-F-2` → `LOW-04-F-6`.
2. **Node, non-consensus:** `MEDIUM-07-F-1`, `MEDIUM-07-F-5`, `MEDIUM-04-F-1`, then the LOW node reports in any order (`LOW-07-F-7` after `MEDIUM-01-V-1`).
3. **Bridge:** `LOW-05-T-1` → `HIGH-05-H-1` → `HIGH-05-H-2` → `MEDIUM-05-M-4` / `LOW-05-L-5` → `LOW-05-L-3` → `MEDIUM-05-M-1` → `MEDIUM-05-M-3` last (its alarm table must match final names); `MEDIUM-05-M-2`, `LOW-05-L-2`, `LOW-05-L-4`, `INFO-05-I-1` independent.
4. **Clients and infra:** independent, except `LOW-06-Y-1` re-pins after `MEDIUM-01-V-2`.

| Report | Title |
|---|---|
| [HIGH-03-H-1-ycash-yed-claim-cancel-refund.md](done/HIGH-03-H-1-ycash-yed-claim-cancel-refund.md) | HIGH — 03/H-1, 03/I-3 (+ 03/V-1 doc, 03/V-2 info) — An attestor cancel forfeits the claimant's burn with no slash: refund the burn on cancel; pin `cancelThreshold` |
| [HIGH-05-H-1-hawkeye-peer-channel-auth-burn-sign-once.md](done/HIGH-05-H-1-hawkeye-peer-channel-auth-burn-sign-once.md) | HIGH — 05/H-1, 05/N-1, 05/N-2, 05/L-1 — Authenticate the Hawkeye peer channel, gate `/unlock/sign`, add the per-burn sign-once dimension, validate reused unlock hex, gather cancels and bound cancel capacity |
| [HIGH-05-H-2-hawkeye-wyec-watch-latest-challenge-window-floor.md](done/HIGH-05-H-2-hawkeye-wyec-watch-latest-challenge-window-floor.md) | HIGH — 05/H-2, 05/T-3 — Watch `MintProposed` at `latest`, enforce a mainnet `challengeWindow` floor and a non-zero `mintCap`, alarm and pause on a finality stall, and test it with pinned finality |
| [MEDIUM-01-V-1-ycash-preactivation-template-coins.md](done/MEDIUM-01-V-1-ycash-preactivation-template-coins.md) | MEDIUM — 01/V-1 = 07/F-3, 01/V-3, 01/N-1, 01/T-1 — Pre-activation template coins: live `ConnectBlock` accepts a spend that `Reconcile` cannot replay; `-prune` guard only under Yellowback |
| [MEDIUM-01-V-2-ycash-set-sig-anyonecanpay.md](done/MEDIUM-01-V-2-ycash-set-sig-anyonecanpay.md) | MEDIUM — 01/V-2 = 07/F-2, 07/N-2 — Set signatures bind the builder's fee inputs: sign `SIGHASH_ALL|ANYONECANPAY` in `CheckSetSigs`; make `vault_buildunlock` idempotent |
| [MEDIUM-04-F-1-ycash-vault-pq-reorg-ci-skip-guard.md](done/MEDIUM-04-F-1-ycash-vault-pq-reorg-ci-skip-guard.md) | MEDIUM — 04/F-1, 04/N-4 — `vault_pq_reorg.py` can pass the merge gate as a vacuous SKIP; CI has no SKIP detection |
| [MEDIUM-04-F-2-ycash6-v5-under-vault.md](done/MEDIUM-04-F-2-ycash6-v5-under-vault.md) | MEDIUM — 04/F-2 (+ 02/I-4) — v5 (ZIP-225) transactions under NU5 + Vault are unspecified: declare v5 invalid under Vault, refuse NU5 ≤ Vault on regtest, and fix the placeholder-prevout rechecks |
| [MEDIUM-05-M-1-hawkeye-member-key-custody-separation.md](done/MEDIUM-05-M-1-hawkeye-member-key-custody-separation.md) | MEDIUM — 05/M-1 — The member key is plaintext in the node wallet and is also the bond and gas key: say so, separate the gas key, and move Ycash signing off the wallet |
| [MEDIUM-05-M-2-hawkeye-rate-limit-head-of-line.md](done/MEDIUM-05-M-2-hawkeye-rate-limit-head-of-line.md) | MEDIUM — 05/M-2 — Rate-limit head-of-line blocking: an over-cap burn parks every later release forever |
| [MEDIUM-05-M-3-hawkeye-operations-runbook.md](done/MEDIUM-05-M-3-hawkeye-operations-runbook.md) | MEDIUM — 05/M-3 — Write the bridge-attestor operations runbook; fix `yellowback-attestor.md`'s contradictions |
| [MEDIUM-05-M-4-hawkeye-mainnet-config-floors.md](done/MEDIUM-05-M-4-hawkeye-mainnet-config-floors.md) | MEDIUM — 05/M-4 — Mainnet floors on the policy parameters (`confirmations`, `delay`, `min_owner_age`, `takeover`, `roll_margin`, `heartbeat_blocks` vs `livenesswindow`) |
| [MEDIUM-07-F-1-ycash-mempool-dos-carveout.md](done/MEDIUM-07-F-1-ycash-mempool-dos-carveout.md) | MEDIUM — 07/F-1 — Narrow the mempool `DoS(0)` carve-out for template-input transactions to the set-state-dependent script errors |
| [MEDIUM-07-F-5-ycash-sign-once-record-restore.md](done/MEDIUM-07-F-5-ycash-sign-once-record-restore.md) | MEDIUM — 07/F-5 — The set sign-once record lives only in `wallet.dat`: a seed restore or a second host can equivocate. Document, export/import the record, warn at restore time |
| [LOW-01-T-2-ycash-vault-primitive-test-fidelity.md](done/LOW-01-T-2-ycash-vault-primitive-test-fidelity.md) | LOW — 01/T-2, 01/T-3, 01/T-4, 01/T-5, 01/T-6, 07/F-4 — Vault primitive test fidelity: `SetSigChecker` negatives, a real V through `VerifyScript`, scriptSig-opcode parity, state-rule fuzzing, the pre-activation restart case, and the devnet walk's lost no-module witness |
| [LOW-01-V-4-V-5-ycash-selector-malleability-app-branch.md](done/LOW-01-V-4-V-5-ycash-selector-malleability-app-branch.md) | LOW — 01/V-4, 01/V-5 — Template-spend malleability (selector and extra pushes outside the sighash) and the signature-free APP branch on ungoverned tags |
| [LOW-01-V-6-ycash-vaultdb-read-cache-race.md](done/LOW-01-V-6-ycash-vaultdb-read-cache-race.md) | LOW — 01/V-6 — `VaultDB::Read` caches a value read outside its mutex (latent stale-cache race) |
| [LOW-01-V-7-ycash-attestor-set-chain-parameter.md](done/LOW-01-V-7-ycash-attestor-set-chain-parameter.md) | LOW — 01/V-7 — Primitive set state depends on the node-local `-yellowbackattestorset` (the P8 chain-parameter item) |
| [LOW-02-PQ-1-PQ-2-ycash-falcon-drbg-slhdsa-zeroize.md](done/LOW-02-PQ-1-PQ-2-ycash-falcon-drbg-slhdsa-zeroize.md) | LOW — 02/PQ-1, 02/PQ-2 — Wipe the Falcon DRBG/sampler SHAKE states and zeroize slhdsa-c's `slh_var_t` (local patch P3) |
| [LOW-02-PQ-3-ycash-slhdsa-hedged-signing.md](done/LOW-02-PQ-3-ycash-slhdsa-hedged-signing.md) | LOW — 02/PQ-3 — Hedge SLH-DSA wallet signing (`pq::Sign` → `SignWithEntropy` with 16 fresh bytes) |
| [LOW-02-PQ-4-ycash-pq-key-decrypt-cache.md](done/LOW-02-PQ-4-ycash-pq-key-decrypt-cache.md) | LOW — 02/PQ-4 (+ verification N-2) — Cache decrypted PQ keys per unlock instead of re-running keygen on every `GetPQKey` |
| [LOW-03-M-1-M-2-ycash-cancel-accounting-bundlelog.md](done/LOW-03-M-1-M-2-ycash-cancel-accounting-bundlelog.md) | LOW — 03/M-1, 03/M-2 (+ 03/T-2 cancel-path tests) — Cancel accounting (`supplyCents` vs Σ debt) and `BundleLog` rows from non-held transactions: clarify the spec, add the tests, optionally harden |
| [LOW-03-T-1-ycash-yed-golden-model-independence.md](done/LOW-03-T-1-ycash-yed-golden-model-independence.md) | LOW — 03/T-1, 03/T-2, 03/T-3, 03/T-4 — The YED golden vector is regenerated by the model it checks; the cancel path has no C++ unit negatives; the Python model mirrors `math.h` clause for clause; three copies of the golden hash |
| [LOW-04-F-3-ycash6-tpl1-void-mint-test-port.md](done/LOW-04-F-3-ycash6-tpl1-void-mint-test-port.md) | LOW — 04/F-3 — Port the TPL-1 functional case (`tpl_primitive_skip_leaves_no_yed_effect`) to ycash6, whose spec still cites it |
| [LOW-04-F-4-ycash6-miner-safety-net-parity.md](done/LOW-04-F-4-ycash6-miner-safety-net-parity.md) | LOW — 04/F-4 — ycash6's block assembler has a thinner per-candidate safety net than ycash-dd's (no PQ-script or sequence-lock recheck) |
| [LOW-04-F-5-ycash-mainnet-topology-upgrade-test.md](done/LOW-04-F-5-ycash-mainnet-topology-upgrade-test.md) | LOW — 04/F-5 — ycash-dd's `vault_upgrade.py` tests Vault-after-Sapling; mainnet is Vault-after-Canopy (never exercised on dd) |
| [LOW-04-F-6-librustzcash6-vault-v5-orchard-consistency.md](done/LOW-04-F-6-librustzcash6-vault-v5-orchard-consistency.md) | LOW — 04/F-6 — librustzcash6: `BranchId::Vault.has_orchard()` and `V5.is_valid_for_branch(Vault)` are permissive while the node (and `suggested_for_branch`) say v4-only |
| [LOW-04-N-1-ycash6-zip317-pq-fee-guidance.md](done/LOW-04-N-1-ycash6-zip317-pq-fee-guidance.md) | LOW — 04/N-1 — ZIP-317 unpaid-action gate (opt-in) and ZIP-401 low-fee penalty on ycash6 vs ycash-dd-fee PQ transactions: fee guidance for Yellowback clients and relays |
| [LOW-05-L-2-hawkeye-rpc-transport-and-file-permissions.md](done/LOW-05-L-2-hawkeye-rpc-transport-and-file-permissions.md) | LOW — 05/L-2 — ycashd RPC credentials over plain `http://` to any host; no loopback/TLS rule; no file-permission checks |
| [LOW-05-L-3-wyec-setbridge-successor-consumed.md](done/LOW-05-L-3-wyec-setbridge-successor-consumed.md) | LOW — 05/L-3 — A successor bridge does not inherit `consumed`; Hawkeye's `lockId`-keyed Mint record both guards and blocks across a migration |
| [LOW-05-L-4-wyec-hawkeye-veto-griefing-threshold-fallback.md](done/LOW-05-L-4-wyec-hawkeye-veto-griefing-threshold-fallback.md) | LOW — 05/L-4 — One guardian can veto every honest proposer for a lock; the threshold fallback is not automated |
| [LOW-05-L-5-hawkeye-reorged-lock-mint-and-start-height.md](done/LOW-05-L-5-hawkeye-reorged-lock-mint-and-start-height.md) | LOW — 05/L-5 — A mint of a reorged-away lock is judged `Ok` (alarm only); a wrong `start_height` makes an attestor challenge and slash honest proposers |
| [LOW-05-T-1-hawkeye-wyec-test-fidelity.md](done/LOW-05-T-1-hawkeye-wyec-test-fidelity.md) | LOW — 05/T-1, 05/T-2, 05/T-4 — Test fidelity: the EIP-712 vector stamp follows the pin, exact `expectRevert` selectors, one copy of the contract tests, negative EIP-712 vectors |
| [LOW-06-I-1-ycash-infra-kubectl-pin.md](done/LOW-06-I-1-ycash-infra-kubectl-pin.md) | LOW — 06/I-1 — `bitnami/kubectl:latest` is the only unpinned image in the Helm chart |
| [LOW-06-L-1-lightwalletd-vault-contract-resync-ci-rawtx-cap.md](done/LOW-06-L-1-lightwalletd-vault-contract-resync-ci-rawtx-cap.md) | LOW — 06/L-1, 06/L-2, 06/V6-N1 — lightwalletd's vault contract fixture is stale and CI skips silently; the 200 kB raw-transaction cap is below the node's 2 MB and below what YEW builds |
| [LOW-06-X-1-x402-close-before-next-upgrade.md](done/LOW-06-X-1-x402-close-before-next-upgrade.md) | LOW — 06/X-1, 06/X-2 — x402 batch-settlement server never closes channels before the next network-upgrade activation height; the Falcon YED key file is plaintext (Info) |
| [LOW-06-Y-1-yew-vault-vectors-resync-scheme-aware-ci.md](done/LOW-06-Y-1-yew-vault-vectors-resync-scheme-aware-ci.md) | LOW — 06/Y-1, 06/Y-2, 06/Y-5 — YEW's `vault_vectors.json` is stale, its owner-spend test is SLH-DSA-only, no CI pin on the node's vector files, devnet suites off CI |
| [LOW-06-Y-4-yew-falcon-active-check-pq-ikm-text.md](done/LOW-06-Y-4-yew-falcon-active-check-pq-ikm-text.md) | LOW — 06/Y-4, 06/Y-3, 06/V6-N2 — YEW forces `falcon_active` off regtest instead of checking the server; the PQ-key IKM differs from the node's and the trust text implies portability |
| [LOW-07-F-11-ycash-lockorder-filter-vault-gating.md](done/LOW-07-F-11-ycash-lockorder-filter-vault-gating.md) | LOW — 07/F-11 — Lockorder checker ignores `vault` locks; which nightly legs should gate |
| [LOW-07-F-6-ycash-pq-orphan-size-limit.md](done/LOW-07-F-6-ycash-pq-orphan-size-limit.md) | LOW — 07/F-6 — Orphan size bound (5,000 B) drops every SLH-DSA spend that arrives before its parent |
| [LOW-07-F-7-F-8-ycash-vault-undo-retention.md](done/LOW-07-F-7-F-8-ycash-vault-undo-retention.md) | LOW — 07/F-7, 07/F-8 — Prune the vault DB's per-block undo records (and document the Yellowback index's 4,096-block recovery bound) |
| [LOW-07-F-9-ycash-regtest-min-set-maturity-floor-test.md](done/LOW-07-F-9-ycash-regtest-min-set-maturity-floor-test.md) | LOW — 07/F-9 — Regtest `nVaultMinSetMaturity` lowered 8→2 to fit the suites; add a functional below-floor rejection |
| [INFO-02-N-1-01-V-11-01-N-2-01-N-3-yellowback-spec-maintenance.md](done/INFO-02-N-1-01-V-11-01-N-2-01-N-3-yellowback-spec-maintenance.md) | INFO — 02/N-1, 01/V-11, 01/N-2, 01/N-3 — Spec maintenance: `pqFalconHeight` ruling (R-A2), §15.4/§15.5 drift from the code, released-set branch non-exclusivity, `epochUsed` not refunded on cancel |
| [INFO-05-I-1-hawkeye-debug-derive-and-rpcversion-doc.md](done/INFO-05-I-1-hawkeye-debug-derive-and-rpcversion-doc.md) | INFO — 05/I-1, 05/I-2 — `Debug` on secret-bearing config types; the workspace `CLAUDE.md` says `rpcversion 5` for Hawkeye |
| [INFO-06-W-1-yecwallet-random-password.md](done/INFO-06-W-1-yecwallet-random-password.md) | INFO — 06/W-1, 06/V6-N3 — `randomPassword()` can emit a NUL-truncated RPC password and leaks its buffer |

## Follow-up audit (waves 3 and 4)

The still-open set is on `audit/quantum-vault-ecosystem-wave4` (`docs/remedial-action-reports/pending/`, 48 reports). A report moves here, into `done/`, once its fix has merged on `upgrade/vault`. Seventeen follow-up reports are in `done/` below; a partial landing stays pending on the audit branch.

| Report | Title |
|---|---|
| [HIGH-W3-Y-2-ycash-yed-cancel-limit-escalation-c4b.md](done/HIGH-W3-Y-2-ycash-yed-cancel-limit-escalation-c4b.md) | HIGH — W3-Y-2 (+ the CAN-2 parts of W3-Y-3) — Unbounded one-seat cancel veto: CAN-2 escalating co-signed cancels and C4b, merged 2026-10-13 (round 2: cap 4, claimable-position residual hold) |
| [HIGH-W3-03-NEW-1-ycash-yed-residual-role-floor-emergency-sizing-hold.md](done/HIGH-W3-03-NEW-1-ycash-yed-residual-role-floor-emergency-sizing-hold.md) | HIGH — 03/NEW-1, W3-Y-1, W3-Y-5 (+ the residual-hold part of W3-Y-3) — Path-(b) residual extraction: pin the claim's intent roles by position with a claimant value floor, size the path-(b) cap at `pEmerg`, and hold a cancelled claim's residual until the position closes (CAN-3) |
| [HIGH-W4-B-2-hawkeye-departed-signer-unlock-pins-vault.md](done/HIGH-W4-B-2-hawkeye-departed-signer-unlock-pins-vault.md) | HIGH — W4-B-2, 02/V-N2, 02/V-N3, W4-B-5 — Takeover adopts an unlock signed only by a departed member; the row never dies and pins the vault until its owner branch opens; burns draw on roll-due vaults; `hawkeye leave` has no guard; rejoined keys and network upgrades revive or strand signed unlocks |
| [MEDIUM-W3-07-NEW-1-ycash-salvagewallet-sign-once-records.md](done/MEDIUM-W3-07-NEW-1-ycash-salvagewallet-sign-once-records.md) | MEDIUM — 07/NEW-1 — The fork's own `-salvagewallet` drops every `vault*` record and `pqissued` and sets no restore marker: keep the records, and fail closed after any salvage |
| [MEDIUM-W3-B-1-05-N-1-W4-B-4-hawkeye-correct-duplicate-unlock-not-slashable.md](done/MEDIUM-W3-B-1-05-N-1-W4-B-4-hawkeye-correct-duplicate-unlock-not-slashable.md) | MEDIUM — W3-B-1, 05/N-1, W4-B-4 — A correct duplicate by a burn's leader or scheduled taker is cancelled, not slashed. Drills D-3 and D-3b passed on both node lines, 2026-10-18 |
| [MEDIUM-W3-B-2-05-N-2-hawkeye-slash-sign-honours-auto-slash.md](done/MEDIUM-W3-B-2-05-N-2-hawkeye-slash-sign-honours-auto-slash.md) | MEDIUM — W3-B-2, 05/N-2 — `POST /slash/sign` votes without the operator when `auto_slash = false`; there is no command to vote on one reviewed case |
| [MEDIUM-W3-B-3-wyec-hawkeye-rogue-guardian-proposal-spam.md](done/MEDIUM-W3-B-3-wyec-hawkeye-rogue-guardian-proposal-spam.md) | MEDIUM — W3-B-3 — A rogue guardian can open unlimited optimistic proposals on fresh `lockId`s; every one costs the watchers a challenge, and a burst can outrun them |
| [MEDIUM-W3-C-1-yew-token-value-fee-bound-yed-activation.md](done/MEDIUM-W3-C-1-yew-token-value-fee-bound-yed-activation.md) | MEDIUM — W3-C-1, 06/N-1 (+ 06/N-2 Low, 06/N-4 Info) — A server-listed "token" can burn a YEC coin as fee: check token values, account inputs at their real value, bound the fee in the gate's local layer, and stop treating YED as available on the server's word |
| [MEDIUM-W3-N-1-07-NEW-2-ycash-vault-send-signs-only-own-builds.md](done/MEDIUM-W3-N-1-07-NEW-2-ycash-vault-send-signs-only-own-builds.md) | MEDIUM — W3-N-1 (+ 07/NEW-2) — `vault_send` / `set_sendact` sign only coins this wallet's builders chose, require a template input, and preview with `dryrun`. Merged 2026-10-17; the functional shards passed on both node lines |
| [MEDIUM-W3-N-3-ycash-set-sign-validate-before-record.md](done/MEDIUM-W3-N-3-ycash-set-sign-validate-before-record.md) | MEDIUM — W3-N-3 (+ W3-N-14(b)) — `set_signunlock` / `set_signcancel` write the sign-once record before validating the build: validate with `vault::CheckTx` (S-2 / I-2) first, add a write-nothing inspect path, and do NOT add a record delete |
| [MEDIUM-W4-B-1-hawkeye-held-veto-restored-answer-hwm-integrity.md](done/MEDIUM-W4-B-1-hawkeye-held-veto-restored-answer-hwm-integrity.md) | MEDIUM — W4-B-1, 02/V-N1, W4-B-3 — A stale `held` answer pages `unlock-hostage` and is not overridden; a restored member adopts its observed unlock. Merged in hawkeye `#24` |
| [MEDIUM-W4-C-1-W4-C-4-yecwallet-yed-cancel-claim-vault-contract.md](done/MEDIUM-W4-C-1-W4-C-4-yecwallet-yed-cancel-claim-vault-contract.md) | MEDIUM — W4-C-1 (+ W4-C-4 Info) — YecWallet's "Cancel claim" calls `vault_buildcancel`, which the node refuses for every YED intent, and tells the attestor the burn "is NOT refunded": build with `yed_buildcancel`, correct the CAN-1 refund text everywhere, and give YecWallet a pinned vault-RPC contract check |
| [MEDIUM-W4-K-5-yb-calibration-ci-node-crosscheck.md](done/MEDIUM-W4-K-5-yb-calibration-ci-node-crosscheck.md) | MEDIUM — W4-K-5 — yb-calibration's CI never reaches the node: clone-backed tests skip, delegated-kernel parity is tautological, the release-constants test never reads `params.cpp`, and the drift test pins the v3 drift as passing |
| [LOW-W3-B-4-B-5-hawkeye-zero-destination-mainnet-chain-binding.md](done/LOW-W3-B-4-B-5-hawkeye-zero-destination-mainnet-chain-binding.md) | LOW — W3-B-4, W3-B-5 — The lock policy accepts the zero destination address; a Ycash-mainnet config is not bound to Ethereum chain id 1 |
| [LOW-W3-B-6-hawkeye-peer-auth-replay-cache-before-membership.md](done/LOW-W3-B-6-hawkeye-peer-auth-replay-cache-before-membership.md) | LOW — W3-B-6 — The peer-auth replay cache is written before the membership check and is unbounded |
| [LOW-W3-B-7-wyec-setbridge-successor-wiring.md](done/LOW-W3-B-7-wyec-setbridge-successor-wiring.md) | LOW — W3-B-7 — `setBridge` does not check that the successor reads this bridge as its predecessor |
| [LOW-W3-C-2-lightwalletd-high-fee-resubmit-bound.md](done/LOW-W3-C-2-lightwalletd-high-fee-resubmit-bound.md) | LOW — W3-C-2 — `SendTransaction`'s `allowhighfees` resubmission: bound it by the node's effective Yellowback cap and the published size rate, and meter its `gettxout` work |
