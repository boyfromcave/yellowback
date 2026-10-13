# LOW — W3-P-4 — ycash6's miner re-scripts only template and PQ candidates: pin the activation-boundary argument with a regression cell

**Repos / branches to change:** `ycash6` (the cell), new branch `fix/W3-P-4-activation-template-cell` off `upgrade/vault`; `ycash-dd` gets the same cell for parity (its miner already re-scripts every candidate, so the cell passes there unchanged). Functional tests and a code comment only; no miner or consensus change.
**Audit source:** `docs/audits/quantum-vault-ecosystem-wave3/04-cross-line-parity-activation.md:185-207` (W3-P-4); `docs/audits/quantum-vault-ecosystem-wave3/verification/04-verification.md:43` (verdict: Low, miner-local; "I agree it is unreachable as a split"); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:52`. Prior work: LOW-04-F-4 (done; ycash6 miner safety-net parity: `TemplateRun` added the PQ-script and sequence-lock rechecks). Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:102` (STILL OPEN, Δ-free: `miner.cpp`); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`, none of which this report cites.
**Status:** pending

## 1. Finding

ycash-dd's `CreateNewBlock` re-runs every candidate's input scripts at the template height with `MANDATORY | GetVaultScriptFlags(nHeight)`, then the vault trial and the YED filter. ycash6 cannot do that cheaply. `TestBlockValidity` connects the template with `CheckAs::BlockTemplate` and `fExpensiveChecks = false`, so no script runs. The port compensates with `vault::TemplateRun::Try`, which re-runs, per candidate:
- the template (V/I) input scripts;
- the PQ input scripts (`RecheckPQScripts(forTemplate=true)`, at `STANDARD | vault`);
- BIP68 at the template height.

A candidate with neither a template nor a PQ input is not script-checked again on ycash6.

The only scripts whose validity changes with the template height are those that change at the Vault activation itself: CSV becomes BIP112, and 0xc0/0xc1 become evaluated. Both auditors argue that those cannot reach a ycash6 template invalid:
- ATMP verifies at `nextBlockHeight` under STANDARD flags. Before activation, `DISCOURAGE_UPGRADABLE_NOPS` already refuses an `OP_NOP3` (CSV) spend, and 0xc0/0xc1 are bad opcodes.
- At the activation tip change, `removeWithoutBranchId` evicts every mempool transaction signed under the previous branch ID, and `RecheckMempool` re-evaluates the rest at tip+1.

If the argument were wrong, ycash6 would mine an invalid block that every node rejects. That loses the miner's reward; it does not split the chain. The argument is sound today, but it rests on two stock behaviours, the upgradable-NOP policy flag and the branch-ID eviction, that no Vault test pins at the template boundary. A future policy relaxation (e.g. a `-acceptnonstdtxn` change to the script-flag set) or an eviction refactor would reopen the gap silently.

## 2. Root cause

ycash6 `0742e43` (re-verified):

- `src/main.cpp:3511-3515` and `:6608` (`CheckAs::BlockTemplate` → `fExpensiveChecks = false` in `TestBlockValidity`).
- `src/miner.cpp:375-378` (`vault::TemplateRun` holder), `src/vault/node.h:93,126-129` (`TemplateRun`, `RecheckPQScripts(forTemplate)`), `TemplateRun::Try` in `src/vault/node.cpp`.
- Branch-ID eviction at every tip change: `src/main.cpp:5092`, `:5242`, `:5260` (`mempool.removeWithoutBranchId`); ycash-dd `src/main.cpp:4177,4268,4286`.
- The pre-activation policy refusal the argument relies on is already asserted for the *mempool* only: `qa/rpc-tests/vault_upgrade.py:216-219` ("before Vault: OP_CHECKSEQUENCEVERIFY is OP_NOP3 (non-standard, valid in a block)"; `assert_mempool_rejects(raw, 'non-mandatory-script-verify-flag')`). No cell looks at `getblocktemplate` across the boundary.
- ycash-dd's per-candidate check for comparison: `src/miner.cpp` overlay delta ("UPGRADE_VAULT adds CSV and the set opcodes at nHeight"), `ContextualCheckInputs(…, MANDATORY_SCRIPT_VERIFY_FLAGS | GetVaultScriptFlags(nHeight), …)`.

## 3. Fix options considered

1. **Turn on script checks in ycash6's `TestBlockValidity` for templates.** That diverges from stock 6.20.0's miner, costs a full script pass per `getblocktemplate`, and touches `main.cpp` (consensus review gate) for a miner-local benefit. Rejected.
2. **Extend `TemplateRun::Try` to re-script every candidate at `MANDATORY | vault`** (ycash-dd parity). Small code, but a per-candidate script pass on every template is exactly the cost 6.20.0 avoids; the auditors found no reachable case. Not recommended now; keep as the fallback if the cell below ever fails.
3. **A regression cell that pins both legs of the argument at the activation boundary, on both lines** (the auditor's recommendation, adjusted; see below), plus a comment at the `TemplateRun` call site naming the two invariants. **Recommended.**

**Correction to the audit's suggested cell.** The audit proposes building "a template at the activation height with a pre-activation CSV-failing P2SH spend in the mempool". Such a spend can never be in the mempool: before activation, ATMP refuses it under `DISCOURAGE_UPGRADABLE_NOPS` (`vault_upgrade.py:218` asserts exactly that). The cell therefore pins the two invariants instead: (a) that refusal, and (b) branch-ID eviction of a Canopy-signed transaction left in the mempool at `ACT-1`, checked through `getblocktemplate`.

## 4. Recommended fix

Both lines, `qa/rpc-tests/vault_upgrade.py`, in the "the activation block carries…" section (ycash6 `:257-273`; dd equivalent before its activation block):

1. **Leg (b), branch-ID eviction at the template boundary.**
   - At tip `ACT-2` (`nextblock` = Canopy), build and `sendrawtransaction` a Canopy-signed spend with the existing helper `self.spend_p2pkh_signed(YCASH_CANOPY_BRANCH_ID)` (ycash6 `:239-241` uses it).
   - Mine block `ACT-1` **without** it: `mine_block_raw(n0, [])` (`test_framework/yellowback_util.py:1382`) assembles a block with only the coinbase.
   - Now `nextblock` is Vault. Assert that the txid is not in `getrawmempool()`, and not in `[t['hash'] for t in getblocktemplate()['transactions']]`.
   - Mine `ACT` with `self.mine()` and assert that the block was accepted and does not contain the txid.
   - Re-send the same raw tx and assert the rejection `old-consensus-branch-id`, as `:296-299` does after activation.
   - On ycash-dd use its own helpers: `mine_block_raw` at `test_framework/yellowback_util.py:1261`, and the Canopy-signed spend and `assert_raises_rpc('old-consensus-branch-id', …)` pattern at `vault_upgrade.py:286-288`.
2. **Leg (a), the upgradable-NOP refusal at the boundary.** At tip `ACT-1` (next block = Vault), a P2SH CSV spend with `nSequence` 0 must be refused by the mempool with the BIP112 reason, not accepted. Assert this with the existing `assert_mempool_rejects` and the post-activation message used at `:306-311`. Then assert that `getblocktemplate()['transactions']` holds no spend of that coin. Together with `:216-219` (refused at `ACT-2` as non-standard) this pins that a CSV-failing spend never enters the mempool on either side of the boundary.
3. **ycash6 code comment** at the `TemplateRun` call site (`src/miner.cpp:375`): "A candidate with neither a template nor an OP_CHECKPQSIG input is not re-scripted here. That is safe because ATMP verified it at nextBlockHeight under STANDARD flags (DISCOURAGE_UPGRADABLE_NOPS refuses pre-activation CSV) and removeWithoutBranchId evicts previous-epoch transactions at every tip change; vault_upgrade.py's activation-boundary cell pins both (audit W3-P-4)." Comment only. `miner.cpp` is not under the G-9 paths.
4. **`docs/mapping.md` §22** (or §19): one row, "6.20.0 template connect runs no scripts → TemplateRun rechecks template/PQ inputs; the rest relies on ATMP-at-next-height + branch-ID eviction (pinned by vault_upgrade.py)".

## 5. Tests

- The new cell on both lines (`vault_upgrade` is in both `YELLOWBACK_SCRIPTS`; dd also runs it under sanitizers).
- **Would-have-caught check, once, in the PR (ycash6):** comment out the `removeWithoutBranchId` call after `ActivateBestChain`'s tip change (`main.cpp:5260`, scratch only). The cell must fail: the Canopy-signed txid appears in the template, and the mined block is rejected or the assertion catches it first. Revert.

## 6. Acceptance criteria

- `vault_upgrade.py` on both lines asserts both legs at `ACT-1`/`ACT` through `getblocktemplate`, and passes.
- ycash6 `miner.cpp` carries the comment naming the two invariants and the cell.
- The scratch negative is recorded in the PR.
- Mapping row added.

## 7. Risks and side effects

- None to consensus or mining. Test and comment only.
- `mine_block_raw` solves regtest Equihash in Python (seconds). That is one extra block in an already long script; acceptable.
- If a future change makes the cell fail, the fix is option 2 (`TemplateRun` re-scripts every candidate). It must not be "relax the cell".

## 8. Effort estimate and dependencies

- ~0.5 day (two lines, one cell, the scratch negative). One reviewer.
- No dependency. It touches the same script as LOW-W3-04-NEW-2 (dd `vault_upgrade.py` gains the history cell) and INFO-W3-P-7-P-8-P-9 (cell reconciliation), so land those together or rebase.
