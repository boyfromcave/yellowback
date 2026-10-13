# LOW — 06/Y-1, 06/Y-2, 06/Y-5 — YEW's `vault_vectors.json` is stale, its owner-spend test is SLH-DSA-only, no CI pin on the node's vector files, devnet suites off CI

Repos / branches to change: `yew` (`fix/06-Y-1-vault-vectors-resync` off `upgrade/vault`). One node change request (Y-2) for `ycash-dd` + `ycash6`, non-consensus (test data only).
Audit source: `docs/audits/quantum-vault-ecosystem/06-clients-wallets-infra.md:56-85` (Y-1), `:87-95` (Y-2), `:113-117` (Y-5); verification `verification/06-verification.md:16-17,20` (verdicts), `:30-50` (Y-1 reproduced and re-rated Low), `:58-60` (Y-4/Y-5); consolidated `00-consolidated.md` rows 06/Y-1 and 06/Y-2..Y-5, R8.
Status: done — completed 2026-10-13T12:27Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13; nightly tier pending the owner's dispatch)

## 1. Finding

`yew/core/src/vault.rs` says the node's golden vector `src/test/data/vault_vectors.json` "is replayed … from `core/tests/vectors/vault_vectors.json`, a byte-identical copy" (`:18-19`, `:28`). It is not: the copy's sha256 is `29633de7…` against the node's `4ba21283…` (identical on `ycash-dd` `055d9c2` and `ycash6` `e866c45`). The node file has since gained a `falconOwner` key, three more `ownerSpends` entries (`owner-released-selector-3-vault`, `owner-released-selector-3-intent`, `owner-falcon-selector-2` with an 88-byte `falconEntropy`), four more `intentsInvalid` cases and one more `intents` case; `keys[1]`/`signatures[1]` were relabelled `owner` → `ec-legacy`. The owner-spend test `owner_spend_is_signed_byte_for_byte` (`vault.rs:670-713`) derives one SLH-DSA key from `pqOwner` and asserts it owns **every** entry, so dropping the node's current file in makes it panic at `:687` (reproduced by the verifier). No script or CI step compares the copy to the node, unlike `pq_vectors.json` (byte-identical today, also uncompared) and x402's `test_falcon_sources_are_the_node_files`.

The verifier rewrote the test scheme-aware in a scratch copy and ran it against the node's file: all four owner spends and every other section are byte-exact, and production owner spends only ever take the one shape the stale copy does cover (SLH-DSA, selector 2, via `build/redeem.rs:304-322`). So this is a test-fidelity and process gap, not a signing defect — Low. The same gap repeats for the A-12 derivation constants, hand-copied into `pq.rs:993-1021` from the node's `pq_wallet_tests.cpp` (Y-2), and for the devnet acceptance suites (`q_falcon_*`, `q_pqaddr_*`, W1–W4), which are ignored unless `YEW_DEVNET=1` and never run in CI (Y-5), so the Falcon-holder end-to-end evidence is a note in `docs/design-notes.md:568-576`, not a check.

## 2. Root cause

- `yew/core/tests/vectors/vault_vectors.json` — stale copy (hand-copied, no pin). Sections present on the node and missing here: `falconOwner {label, owner, pk, seed}`; `ownerSpends[1..3]`; `intentsInvalid[7..10]` (`owner-scheme-as-data-push`, `owner-scheme-0`, `owner-hash-31-bytes`, `owner-hash-33-bytes`); `intents[3]` (`owner-falcon-scheme-2`). The node's generator is `ycash-dd/qa/rpc-tests/test_framework/gen_vault_vectors.py` (`:68` output path, `:102` `FALCON_SIG`, `:450-463` the Falcon owner entry with `falconEntropy`), checked in the node's CI by `gen_vault_vectors.py --check` (dd workflow `python` job).
- `yew/core/src/vault.rs:670-713`:
  - `:673` `PqKey::from_seed(1, pqOwner.seed)` — one key, scheme 1 only;
  - `:686` `parse_vault(&code)` — assumes a V scriptCode; the intent entry (`kind: "I"`) needs `parse_intent`;
  - `:687` `assert_eq!(vp.owner, key.id())` — fails on the Falcon entry;
  - `:699` `key.sign(&digest)` — SLH-DSA deterministic; the Falcon entry needs `sign_with_entropy` (`pq.rs:581-591`) with the vector's `falconEntropy`;
  - `:703-706` dispatch on selector only: `SEL_OWNER` → `vault_owner_script_sig` (`:368`), else `vault_owner_released_script_sig` (`:373`); the intent selector-3 entry needs `intent_owner_released_script_sig` (`:381`).
- `yew/core/src/pq.rs:993-1021` (`derivation_reproduces_the_node_wallet_vector`): five string literals equal to `ycash-dd/src/test/pq_wallet_tests.cpp:53-57` (`SEED_1_0`, `SEED_2_0`, `KEYHASH_1_0`, …) and `ycash6/src/test/pq_wallet_tests.cpp:55-59`. Correct today; a node-side regeneration is not noticed.
- `yew/.github/workflows/ci.yml` `core-linux` job: clones `lightwalletd-dd` at `proto/PIN` (`:55-57`) and runs `scripts/check-proto-pin.sh` (`:67`); no vector step. `scripts/check-proto-pin.sh:12-15` exits 0 when the sibling is absent — the pattern to copy, minus the skip.
- `yew/core/tests/devnet.rs:5` ("ignored unless `YEW_DEVNET=1`"), `:39` run line; `ci.yml:11-14` records that the devnet suites "stay nightly on the owner's machine".

## 3. Fix options considered

1. **Re-copy and leave the test SLH-only, skipping Falcon entries.** Rejected: hides exactly the shapes the node added, and `vault.rs` would still claim "byte-identical" for a file it only half-replays.
2. **Re-copy, scheme-aware test, pinned-rev `cmp` in CI** (the first wave's fix; the verifier's scratch rewrite is a working draft). Accepted.
3. **Fetch the vector files at test time instead of committing copies.** Rejected: `cargo test --locked` must work offline and reproducibly; the committed copy plus a CI pin is the convention every client in the workspace uses.
4. **Y-5: build the whole devnet in a hosted runner.** >60 min cold (ycash-dd build, lightwalletd-dd, the attest agent, the Python framework). Rejected as the first step; accepted as the target. First step: a scheduled self-hosted job on the machine that already runs the suites, non-gating, opening an issue on failure (the node's nightly-tier model).

## 4. Recommended fix

1. **Re-copy both vector files** from `ycash-dd` at `055d9c2` (`src/test/data/vault_vectors.json`, `src/test/data/pq_vectors.json`; `cmp` against `ycash6` `e866c45` — identical) into `core/tests/vectors/`. Add `core/tests/vectors/PIN` with two lines: `ycash-dd 055d9c2…` and `ycash6 e866c45…` (full hashes), the same shape as `proto/PIN`.
2. **Rewrite `owner_spend_is_signed_byte_for_byte`** (`vault.rs:670-713`):
   - load both owners: `pq = PqKey::from_seed(1, pqOwner.seed)`, `fo = PqKey::from_seed(2, falconOwner.seed)`; assert each `public_key()` and `id()` against the JSON;
   - for each entry: parse the scriptCode by `kind` (`"V"` → `parse_vault`, `"I"` → `parse_intent`); take `owner` from the parsed params; pick the key by `owner.scheme` and assert `key.id() == owner`;
   - sighash as today; signature: scheme 1 → `key.sign(&digest)`, scheme 2 → `key.sign_with_entropy(&digest, &falconEntropy)` (88 bytes, `nonce(40) ‖ sampler seed(48)` — the node's `pq::SignWithEntropy`); `assert!(pq::verify(scheme, pk, &sig, &digest))`;
   - dispatch `(kind, selector)`: `("V", 2)` → `vault_owner_script_sig`, `("V", 3)` → `vault_owner_released_script_sig`, `("I", 3)` → `intent_owner_released_script_sig`; anything else is a test failure (a new shape must be added deliberately);
   - assert the scriptSig hex and the re-serialised transaction as today; count entries and assert `(slh, falcon, v, i) == (3, 1, 3, 1)` so a silently shrunk file fails (the pattern `pq.rs:654-705` uses: `(slh, falcon) == (2, 3)`).
   - Fix the module doc at `vault.rs:18-19` and `:28` to describe the PIN mechanism instead of asserting "byte-identical".
3. **`scripts/check-node-vectors.sh`** (new) + CI step in `core-linux` after `check-proto-pin.sh`:
   - reads `core/tests/vectors/PIN`; for each of the two node repos fetches `src/test/data/vault_vectors.json` and `src/test/data/pq_vectors.json` at the pinned commit (`curl -fsSL https://raw.githubusercontent.com/boyfromcave/<repo>/<commit>/…`, or `git clone --filter=blob:none` + `git show <commit>:<path>` as the proto step does) and `cmp`s against the copies;
   - **fails, never skips**, when a fetch fails in CI; locally, `YCASH_DD=../ycash-dd YCASH6=../ycash6` compare against sibling checkouts and print a note (not a failure) if the sibling's HEAD is not the pin (mirrors `check-proto-pin.sh:23-30`);
   - interim for Y-2 (until the node change lands): fetch `src/test/pq_wallet_tests.cpp` at the pin and assert the five literals in `pq.rs:993-1021` appear in it (`grep -F` each hex) — cheap and removes the "not noticed" risk now.
4. **Y-2 node change request** (both lines, test data only, no consensus): have the node emit the A-12 derivation vector as JSON — either a new `src/test/data/pq_wallet_vectors.json` `{seed, derive:[{scheme,index,out}], slhPk, keyHash}` written by a small generator and read by `pq_wallet_tests.cpp` instead of the literals, or a `derivation` section in `pq_vectors.json` regenerated by its existing generator. Then YEW's test reads the copied file and the `cmp` step covers it; delete the literals. Track it as a plan §10 change request in the workspace (`docs/plans/yellowback-quantum-spec.md` A-12 vectors).
5. **Y-5 devnet suites in CI.** Add `.github/workflows/devnet-nightly.yml`: `on: schedule` (nightly) + `workflow_dispatch`; `runs-on: [self-hosted, yb-devnet]` (the owner's machine registered as a runner, with the workspace checked out at `$YB_WORKSPACE`); steps run `scripts/devnet-falcon.sh up && … test`, `scripts/devnet-pqaddr.sh`, `scripts/devnet-w1.sh`, `-w2`, `-w4` with `YEW_DEVNET=1 cargo test -p yew-core --test devnet -- --ignored --nocapture`; on failure, open/update an issue (the node's nightly pattern). Non-gating by construction (schedule only). Target state (second PR): a hosted job that builds `ycash-dd` from `core/tests/vectors/PIN`'s commit (cache the build), `lightwalletd-dd` from `proto/PIN`, and runs the `q_falcon_*`/`q_pqaddr_*` subset (the two the quantum line added) in ≤ 60 min.
6. **Docs.** `README.md` "Tests": say which suites run where; `docs/design-notes.md` gets a line pointing at the PIN; workspace `docs/mapping.md` §16 gains a row ("client vector copies are pinned and `cmp`ed in CI").

## 5. Tests

- The rewritten `owner_spend_is_signed_byte_for_byte` must print/verify four entries (the verifier's run: `owner-selector-2` scheme 1, `owner-released-selector-3-vault` scheme 1, `owner-released-selector-3-intent` scheme 1, `owner-falcon-selector-2` scheme 2; `cargo test --locked -p yew-core --lib vault::`, 9 tests green, ~22 s).
- The existing `intents_build_parse_and_derive_byte_for_byte`, `vaults_build_and_parse_byte_for_byte`, `selectors_match_the_vector`, `spends_sighash_under_the_vault_branch_id`, `yed_vault_matches_the_app_enabled_vector`, `constants_match_the_vector` pass unchanged on the new file (verified by the second wave); the four new `intentsInvalid` cases are exercised by the first of them — add an assertion that `intentsInvalid.len() == 11`.
- Negative for the CI step: flip one byte in the local copy → `scripts/check-node-vectors.sh` exits 1 naming the file; change the PIN to a commit whose file differs → exits 1. Record both in the PR.
- Negative for the test: a scratch entry with `kind: "V", selector: 1` must fail the dispatch (`unreachable shape`), proving new shapes cannot pass silently.
- Y-5: the nightly workflow's first green run linked from the PR (and its first red run, if any, with the issue it opened).

## 6. Acceptance criteria

- `sha256sum core/tests/vectors/vault_vectors.json` = `4ba212836eed05b9…`; `pq_vectors.json` = `1a146175d7815b82…`; `core/tests/vectors/PIN` names `055d9c2` (ycash-dd) and `e866c45` (ycash6) in full.
- `ci.yml` `core-linux` runs `scripts/check-node-vectors.sh` and it has no skip path in CI (reviewer greps for `exit 0` in the script).
- The owner-spend test iterates `ownerSpends[]` by `kind` and `owner.scheme`, uses `sign_with_entropy` for scheme 2, and asserts the entry counts.
- `vault.rs:18-19,28` no longer claim a byte-identical copy without naming the pin.
- The A-12 literals are either read from a node-exported file (after the node change) or grep-pinned by the check script (interim).
- A scheduled devnet workflow exists and has run at least once; `ci.yml:11-14` comment updated.

## 7. Risks and side effects

- **Vector churn ahead.** R5 (`MEDIUM-01-V-2-ycash-set-sig-anyonecanpay.md`, 01/V-2: `SIGHASH_ALL|ANYONECANPAY` in `CheckSetSigs`) and R1/R4 may regenerate the node's `vault_vectors.json` (hashtype byte in `spends[]`, possibly new `spendsInvalid` cases). YEW re-copies and bumps the PIN after each; the `cmp` step will go red the moment the pin is moved without the copy — that is the intended signal. Sequence: land this now against `055d9c2`, re-pin after R5 merges on both lines.
- Rule 5 ("both node lines"): the PIN carries both commits; if the two lines ever diverge on a vector, the step fails and the workspace must reconcile first (that is a workspace defect, not a YEW one).
- The self-hosted devnet runner exposes the owner's machine to workflow code from the repo; restrict the workflow to `schedule`/`workflow_dispatch` on `upgrade/vault` only, never `pull_request`.
- No change to any signing path; `build/redeem.rs` and `build/release.rs` untouched.

## 8. Effort estimate and dependencies

- Steps 1–3, 6: ~1 day (the test rewrite is a half-day; the verifier's scratch rewrite is a starting point). Step 4 (node side): ~0.5 day on each line plus a review that it is test-data-only. Step 5 first form: ~1 day (runner registration, workflow, issue-on-failure); the hosted form: 2–4 days, separate PR.
- Depends on nothing. Re-pin after R5 (`MEDIUM-01-V-2-ycash-set-sig-anyonecanpay.md`) lands on both lines. Share the "fail, never skip" convention with the lightwalletd report (`LOW-06-L-1-…`).

## Completion record

- **Completed:** 2026-10-13T12:27Z
- **Merged and pushed:** yew upgrade/vault 1e250f8 (branches fix/yew-vectors + fix/resync-a). Node test data: ycash-dd 93c8ea2f6 / ycash6 b3bdf929d (pq_wallet_vectors.json + generator, CI --check), merged d2cf7abde / 96b0f607b and pushed with the node lines.
  - Vectors re-synced, with core/tests/vectors/PIN = ycash-dd 8af82551b / ycash6 047b561ac (1406969); SET_SIGHASH = 0x81 asserted.
  - Scheme-aware owner-spend test (SLH-DSA + Falcon); scripts/check-node-vectors.sh in CI with no skip path; resync-node-vectors.sh; nightly devnet workflow (self-hosted, first form).
- **Tests:** yew-core 161 lib + 6 vectors pass; fmt/clippy clean; check-node-vectors ok in CI mode; flutter test 77 pass.
- **Open (owner):** register the yb-devnet self-hosted runner and trigger the nightly workflow's first run; the hosted devnet job is a follow-up.
