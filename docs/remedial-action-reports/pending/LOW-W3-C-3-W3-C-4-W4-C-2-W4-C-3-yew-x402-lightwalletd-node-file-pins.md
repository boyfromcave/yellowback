# LOW — W3-C-3, W3-C-4, W4-C-2 (+ W3-C-7 Info, W4-C-3 Info) — Client copies of node files are not all pinned: YEW's stale Falcon KAT, x402's unchecked vector copies, the vendored Falcon C in both clients, YEW's skipping proto check, and lightwalletd's fixture check against a moving node branch

Repos / branches to change: `yew` (`fix/W3-C-3-node-file-pins` off `upgrade/vault`), `x402-ycash` (`fix/W3-C-4-node-file-pins` off `upgrade/vault`), `lightwalletd` (`fix/W4-C-3-node-pin` off `upgrade/vault`). No node change.
Audit source: wave 3 `docs/audits/quantum-vault-ecosystem-wave3/06-clients-wallets-infra.md:45-46,49` (summary rows), `:110-118` (W3-C-3), `:120-124` (W3-C-7), `:263-269` (W3-C-4), `:376-391` (test-fidelity table); verification `docs/audits/quantum-vault-ecosystem-wave3/verification/06-verification.md:17-18,21` (verdicts), `:193-212` (W3-C-3 reproduced: `cmp` differs at byte 518; W3-C-4 confirmed), `:235-236` (W3-C-7); consolidated `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:53`, `:104` (priority 5). Wave 4 `docs/audits/quantum-vault-ecosystem-wave4/04-clients-wyec-recheck.md:53-54,57` (W3-C-3, W3-C-4, W3-C-7 STILL OPEN), `:65` and `:93-104` (Falcon sha256 re-run), `:153-183` (W4-C-2, Low: the vendored-Falcon drift this report's first version recorded as a writer's finding, now an audit ID), `:185-201` (W4-C-3, Info), `:273-286` (test fidelity); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:48` (W4-C-2 confirmed by sha256), `:49` (W4-C-3).
Status: pending — re-verified at yew `9231787`, x402-ycash `6af477a`, lightwalletd `f89ce24`, node `ycash-dd` `da5e0fe` / `ycash6` `0742e43` (2026-10-13): the KAT still differs (`fc06971c…` vs `5afd31f5…`), the same 3 of 16 Falcon files differ in both clients (node `ycash_falcon.h` `72daef34adba`, `ycash_falcon_sign.c` `406be99a5e50`, `ycash_falcon_verify.c` `30d8ec78ed8c`; both clients `a86e003f55ea`, `e9932c30e0a3`, `b56cb53382b4`), x402's three vector copies are still byte-identical to the node, and `git diff 8af82551b da5e0fe -- src/test/data src/crypto/pq` is empty, so the existing pin stays correct.

## 1. Finding

The first-wave remedial `LOW-06-Y-1` made YEW's node vector copies pinned and `cmp`-checked in CI (`scripts/check-node-vectors.sh`, "fails, never skips"). It listed three files. The fourth node file YEW replays, `core/tests/vectors/pq_falcon_kat.json`, is not in the list and is stale. The node's file gained `r3_all`, 100 verify-only NIST round-3 rows (Falcon audit F-6, ycash-dd `f21af99`), already present at YEW's own pin `8af82551b`. YEW's test reads only `r3` and `padded`, so nothing is wrong today. The 100 extra rows are simply not replayed, and the next node change to the file would also go unnoticed (W3-C-3). x402-ycash copies `pq_vectors.json`, `yellowback_pq_vectors.json` and `sapling_key_components.json` from the node and names the commit in `vectors/README.md`, but no CI step compares them, unlike YEW and lightwalletd. All three are byte-identical to the node today (W3-C-4). YEW's `check-proto-pin.sh` exits 0 when the sibling `lightwalletd-dd` checkout is absent. CI clones the sibling first, so CI cannot skip, but nothing makes that explicit (W3-C-7, Info).

**W4-C-2.** The same gap affects source, not only vectors. YEW (`core/pq-c/falcon/`) and x402 (`python/x402_ycash/pq/_falcon_c/`) each vendor "byte copies" of the node's `src/crypto/pq/falcon/`, and each client signs Falcon with it (YEW on the phone; x402's Python SDK). Thirteen of the sixteen files match the node. The three Ycash entry-point files do not:
- `ycash_falcon.h`, `ycash_falcon_sign.c` and `ycash_falcon_verify.c` predate the node's F-1 length patch (`f21af99`: `ycash_falcon512_verify` gains `pklen` and refuses any signature or key that is not exactly 666 or 897 bytes).
- They also predate the 02/PQ-1 wipe (`3962b19`: keygen wipes the SHAKE256 DRBG state seeded by the keygen seed, and signing wipes the sampler state).

Both node commits are ancestors of the clients' own vector pin (`8af82551b`). YEW's `vendored_falcon_matches_its_manifest` passes because its `SHA256SUMS` pins the stale copy, not the node. The consequences are bounded:
- YEW's Rust `pq::verify` enforces both lengths before calling C (`core/src/pq.rs:597-601`), so F-1's missing check is not reachable through YEW.
- x402 verifies with its stdlib port, not the C (`falcon.py:19-20`); its differential `c_verify` checks both lengths before calling C (`falcon.py:175-179`).
- The missing wipe leaves secret-key-determining DRBG state in a freed stack frame on the device after keygen. This is memory hygiene, the same class the node fixed as 02/PQ-1.

So the F-1 drift changes no verdict today; it only removes one of two independent checks if a future caller skips the wrapper. The missing wipe is real hygiene on the device that holds the YED keys (the keygen DRBG state alone determines the Falcon key pair). Wave 4 confirmed it and gave it the ID W4-C-2 (Low).

**W4-C-3 (lightwalletd, Info).** lightwalletd's node-contract fixtures (`testdata/yellowback/contract.json`, `testdata/vault/vault-rpc-contract.json`, `testdata/vault/vault-rpc.md`) are checked in CI against whatever ycash-dd's `upgrade/vault` holds at the moment, not against a recorded commit. The check is fail-closed, which is the right direction, and it passes at `f89ce24` against `da5e0fe`. But the commit a fixture was synced from is recorded only in a commit message (`f89ce24` names `bb21b675d`), so a lightwalletd commit cannot later be re-verified against its node commit. And any node doc change turns lightwalletd's CI red with no lightwalletd change, which is what happened between `ce6df11` and `f89ce24`. YEW's `PIN` files already do both jobs. Info.

Low overall (W3-C-3, W3-C-4, W4-C-2 Low; W3-C-7, W4-C-3 Info). One pattern fixes all five: a PIN file per client that names the node commit, and a check that compares every node-file copy against that commit, never skipping.

## 2. Root cause (yew `9231787`, x402-ycash `6af477a`, lightwalletd `f89ce24`; node `ycash-dd` `da5e0fe`, client pins `8af82551b` / ycash6 `047b561ac`)

- **YEW KAT.**
  - `core/tests/vectors/pq_falcon_kat.json` sha256 `fc06971c…` vs node `5afd31f5…`. The node file is identical at `da5e0fe`, at the pin `8af82551bc81…` and on ycash6 at `047b561ac9d8…`.
  - Keys: YEW `comment, r3_source, r3 (5), padded (1)`; node adds `r3_all (100)` (`{count, pk, msg, sig}`) and a different `comment`.
  - `scripts/check-node-vectors.sh:26-30` `FILES` lists `vault_vectors.json`, `pq_vectors.json`, `pq_wallet_vectors.json`. `scripts/resync-node-vectors.sh:28-41` copies exactly that list.
  - `core/src/pq.rs:790-835` `falcon_reproduces_the_nist_kats` (fn at `:796`) iterates `r3` (`:812`) and `padded` (`:830`). The node's loop over `r3_all` is `ycash-dd/src/test/pq_crypto_tests.cpp:574-592` (verify, then verify-fails with one bit flipped at `41 + (n % 200)`, `msg.len() == 33·(n+1)`, the first five `pk`s equal `r3`'s).
- **YEW vendored Falcon.**
  - `core/pq-c/falcon/` vs `ycash-dd/src/crypto/pq/falcon/`: `ycash_falcon.h`, `ycash_falcon_sign.c` and `ycash_falcon_verify.c` differ. The other 13 files are identical, and ycash-dd = ycash6 for all 16.
  - `core/pq-c/SHA256SUMS` pins the stale bytes. `core/pq-c/README.md:3-6` claims "byte copy … at `upgrade/quantum-vaults` (last change `ccf49e913`)".
  - The test that checks only the manifest is `core/src/pq.rs:839-853` (`vendored_falcon_matches_its_manifest`, fn at `:841`). The FFI declaration without `pklen` is `core/src/pq.rs:85-91`, called at `:605-611`. `core/build.rs:66-92` compiles the sources.
- **YEW proto pin.** `scripts/check-proto-pin.sh:12-15` is `exit 0` with "not present, skipped". `.github/workflows/ci.yml:62-65` clones `lightwalletd-dd` at `proto/PIN`, `:75` runs the script, and `:78` runs `check-node-vectors.sh`.
- **x402 vectors.** `vectors/README.md:9-13` names `8af82551b` for `vectors/pq/pq_vectors.json` and `vectors/pq/yellowback_pq_vectors.json`. `vectors/sapling/sapling_key_components.json` is byte-identical to `ycash-dd/src/test/data/sapling_key_components.json` (the README attributes it to zcash-test-vectors via Ycash 4.5.0). All three equal the node at the pin on both lines (`cmp` run for this report). `.github/workflows/ci.yml` jobs `unit` (`:54-72`), `light`, `python` (`:127-146`) and `devnet` (`:159-251`) contain no fetch-and-compare step. There is no `vectors/PIN` and no check script (`scripts/` holds only `devnet.sh`, `light-agent.sh`).
- **x402 vendored Falcon.**
  - `python/x402_ycash/pq/_falcon_c/` has the same three-file drift.
  - Its `README.md:3-4` claims byte-identity "at `upgrade/quantum-vaults` `4eabbeead`".
  - `python/tests/unit/test_pq.py:78-81` `test_falcon_sources_are_the_node_files` checks only that the files exist.
  - The ctypes signature without `pklen` is `python/x402_ycash/pq/falcon.py:124-125`, called by `c_verify` at `:175-179`.
- **lightwalletd fixtures (W4-C-3).**
  - `.github/workflows/yellowback-tests.yml:97-107` maps the branch `upgrade/vault` to node branch `upgrade/vault` and runs `scripts/sync-node-contracts.sh --check --required --github "$NODE_REPO_YCASH_DD" "$node"`, which fetches `raw.githubusercontent.com/<repo>/<branch>/<path>` (`sync-node-contracts.sh:59`), a moving head.
  - The script's local mode copies from `--ref` (default `origin/upgrade/vault`, `:33`) and writes no record of the commit. There is no `testdata/NODE_PIN`.
  - `git log -1 f89ce24` is the only record: "re-synced from ycash-dd bb21b675d".
  - YecWallet's own contract-copy step has the same moving-branch shape (`yecwallet-dd/.github/workflows/yecwallet-tests.yml:72-94`). It is not changed here: the YecWallet vault-contract work is `MEDIUM-W4-C-1-W4-C-4-…`, which adopts the PIN shape from the start.

## 3. Fix options considered

1. **Re-copy only.** Rejected: that is how the copies went stale. A copy without a CI `cmp` against a pin is a snapshot.
2. **One shared check script vendored into each client.** Rejected: each client's layout differs (`core/tests/vectors/` vs `vectors/pq/`, two Falcon directories), and the workspace rule is that clients reach the node through public files at a pinned commit, not through a shared tool. Accepted instead: the same *shape* (PIN file, `FILES` list, fail-never-skip) in each repo, copied from YEW's script.
3. **Compare the vendored Falcon C by manifest only (status quo).** Rejected: a manifest pins whatever was copied. The check must compare with the node at the pin, as the vector check does.
4. **W3-C-7: leave the local skip.** The skip is useful for a developer without the sibling checkout. Accepted with a `--required` flag that CI passes, so the CI intent is explicit and a broken clone step fails rather than skips.
5. **W4-C-3: keep following the node's branch head** (status quo). Rejected as the *gate*: CI goes red on node commits, and the provenance is lost. **Pin only, never look at the head.** Also rejected: then nothing notices that the node moved on. Accepted: the required check compares with the pinned commit; a second, report-only step compares with the branch head and prints a warning (failing only in a new daily scheduled job), so drift is visible without blocking unrelated PRs.

## 4. Recommended fix

### YEW (`yew`)

1. **Re-copy the KAT.** From the existing pin (no PIN change: the pinned commits already carry `r3_all`):
   `git -C ../ycash-dd show 8af82551bc81844c865b04e7b77a39226cffa899:src/test/data/pq_falcon_kat.json > core/tests/vectors/pq_falcon_kat.json` (sha256 `5afd31f5debd290c…`).
2. **Add it to the check.** In `scripts/check-node-vectors.sh:26-30`, add `src/test/data/pq_falcon_kat.json` to `FILES`. `resync-node-vectors.sh` then copies it automatically, because it reads `--files`.
3. **Replay `r3_all`.** In `core/src/pq.rs`, extend `falcon_reproduces_the_nist_kats` (or add `falcon_verifies_the_nist_r3_all_rows`), mirroring `pq_crypto_tests.cpp:574-592`:
   - for each row `n`: assert `count == n`, `pk.len() == 897`, `sig.len() == 666`, `msg.len() == 33·(n+1)`;
   - call the C verifier directly through `falcon_ffi::ycash_falcon512_verify`, because `pq::verify` takes a 32-byte message and these rows carry longer ones. Expect `== 0`;
   - flip the bit at index `41 + (n % 200)` and expect `== -1`;
   - for `n < 5`, assert `pk == r3[n].pk`;
   - finally assert the count is 100.
4. **Vendored Falcon pinned to the node (W4-C-2).**
   - Re-copy all 16 files of `src/crypto/pq/falcon/` from `ycash-dd` at the pin into `core/pq-c/falcon/` and regenerate `SHA256SUMS`.
   - Update the FFI declaration at `pq.rs:85-91` to `(sig, siglen, m, mlen, pk, pklen)` and the call at `:605-611` to pass `pk.len()`.
   - Update `core/pq-c/README.md` to name the PIN instead of `ccf49e913`, and list the local patches carried from the node: P1 (`fips202` inline context), F-1 (verify lengths), PQ-1 (DRBG wipes).
   - Extend `scripts/check-node-vectors.sh` with a second list, `SOURCES=(src/crypto/pq/falcon/{LICENSE,codec.c,common.c,fft.c,fips202.c,fips202.h,fpr.c,fpr.h,inner.h,keygen.c,rng.c,sign.c,vrfy.c,ycash_falcon.h,ycash_falcon_sign.c,ycash_falcon_verify.c})`, compared against `core/pq-c/falcon/<basename>` with the same fetch and fail logic. `--files` prints both lists so `resync-node-vectors.sh` copies the sources too. Rename the script's first line of help to "node files" (vectors and vendored sources).
   - Keep `vendored_falcon_matches_its_manifest`: it now guards local edits between resyncs.
5. **W3-C-7.** In `scripts/check-proto-pin.sh`, add `--required`: when it is given and the sibling is absent, print `check-proto-pin: $src not present` to stderr and `exit 1`. Change `ci.yml:75` to `scripts/check-proto-pin.sh --required`. Update the header comment (`:6-8`), which currently says "Skips when the sibling checkout is absent (CI)". That is wrong; CI clones it.
6. **Docs.** `core/src/pq.rs:790-794` doc: name the PIN. README "Tests": add the KAT and Falcon sources to the list of pinned node files.

### x402-ycash (`x402-ycash`)

7. **PIN and check script.**
   - Add `vectors/PIN` in YEW's format (`ycash-dd <full commit> upgrade/vault <date>`, then a `ycash6` line), at `8af82551bc81844c865b04e7b77a39226cffa899` / `047b561ac9d870b041df545368cc27664838a10a`.
   - Add `scripts/check-node-files.sh`, adapted from `yew/scripts/check-node-vectors.sh`:
     - pairs `(node path, local path)`: `src/test/data/pq_vectors.json` → `vectors/pq/pq_vectors.json`; `src/test/data/yellowback_pq_vectors.json` → `vectors/pq/yellowback_pq_vectors.json`; `src/test/data/sapling_key_components.json` → `vectors/sapling/sapling_key_components.json`; and the 16 `src/crypto/pq/falcon/*` files → `python/x402_ycash/pq/_falcon_c/<basename>` (`_falcon_c/README.md` is x402's own and is excluded);
     - sources: sibling checkout at the pinned commit, else `raw.githubusercontent.com/boyfromcave/<repo>/<commit>/<path>`;
     - fails, never skips: no `exit 0` path other than success.
   - Add a resync companion, `scripts/resync-node-files.sh`.
8. **CI.** In `.github/workflows/ci.yml` job `unit` (`:54-72`), add after checkout `- run: scripts/check-node-files.sh` (needs only `bash`, `curl`, `cmp`). Also add it to the `python` job, because the Falcon sources are compiled there.
9. **Re-copy the vendored Falcon (W4-C-2)** at the pin (step 7's resync).
   - Update `falcon.py:124-125` argtypes to six parameters (`…, c_char_p, c_size_t`) and `c_verify` (`:179`) to pass `len(pk)`.
   - The library cache key is "the SHA-256 of the sources and the compiler command" (`falcon.py:14-16`), so the rebuilt library gets a new name automatically.
   - Update `_falcon_c/README.md:3-6` to name `vectors/PIN` and the carried patches (P1, F-1, PQ-1).
10. **Test.** Rename `test_falcon_sources_are_the_node_files` (`test_pq.py:78`) to `test_falcon_sources_are_complete`, since it checks presence; byte identity is now the script's job. Add `test_c_verify_refuses_wrong_lengths`: a 665-byte and a 667-byte signature, and an 896-byte key, all return `False` from `c_verify` (this proves the F-1 patch is the one compiled).
11. **Docs.** `vectors/README.md:9-13`: replace the prose commit names with "pinned in `vectors/PIN`, checked by `scripts/check-node-files.sh` in CI". Workspace `docs/mapping.md` §20: add the row "x402's node copies (vectors, Falcon C) are pinned and `cmp`ed in CI".

### lightwalletd (`lightwalletd`), W4-C-3

12. **`testdata/NODE_PIN`**, in YEW's format: `ycash-dd <full commit> upgrade/vault <date>`. Initial value: `bb21b675d0fd370eb87eea0c363e04f3ad53443a` (the commit `f89ce24` was synced from; equal at these three paths to `da5e0fe`, which the wave-4 check confirmed).
13. **`scripts/sync-node-contracts.sh`.**
    - In sync mode, write `NODE_PIN` from the commit it copied from (`git -C "$tree" rev-parse "$ref"`; with `--github`, resolve the branch with `git ls-remote` first and fetch by that commit).
    - Add `--pinned`: read the commit from `NODE_PIN` and fetch `raw.githubusercontent.com/<repo>/<commit>/<path>` (or `git show <commit>:<path>` from a local tree). A `NODE_PIN` that is missing or not a 40-hex commit is an error.
    - Keep `--github REPO BRANCH` for the drift check.
14. **CI** (`.github/workflows/yellowback-tests.yml:97-107`):
    - the required step becomes `scripts/sync-node-contracts.sh --check --required --pinned --github "$NODE_REPO_YCASH_DD"`;
    - add a report-only step, `continue-on-error: true`, that runs today's branch-head comparison and prints `::warning::node <branch> has moved past NODE_PIN; run scripts/sync-node-contracts.sh`;
    - add a small `node-drift` job on a new daily `schedule:` trigger (the workflow has none today, `:14-16`) that runs the head comparison and **fails**, so a stale pin is noticed within a day without blocking PRs.
15. **Docs.** Script header (`:5-26`) and `docs/yellowback.md`'s fixture paragraph: name `NODE_PIN` as the record of provenance; the commit message is no longer it.

## 5. Tests

- YEW:
  - `cargo test --locked -p yew-core --lib pq::`: the new `r3_all` replay (100 rows verified, 100 flipped rows refused); `vendored_falcon_matches_its_manifest` on the regenerated manifest; `pq_reproduces_the_node_vectors` and `falcon_reproduces_the_nist_kats` unchanged on the new C (keygen and signing outputs are unaffected by the wipes and the length check).
  - The existing iOS core build in CI (`.github/workflows/ci.yml:124`, `scripts/build-core-ios.sh`) must stay green, which catches the FFI signature change on a mobile target. Run one Android build by hand before merging.
- Negatives for both scripts, recorded in the PRs:
  - flip one byte in a local copy → exit 1 naming the file;
  - point the PIN at a commit before `f21af99` → the KAT and the three Falcon files fail;
  - `check-proto-pin.sh --required` with `LIGHTWALLETD_DD=/nonexistent` → exit 1;
  - grep each script for `exit 0`: only the success path.
- lightwalletd:
  - `scripts/sync-node-contracts.sh --check --pinned --tree ../ycash-dd` passes at `bb21b675d`;
  - negatives recorded in the PR: a `NODE_PIN` naming `ce6df11`'s parent fails (the `vault_refee` prose differs); a malformed `NODE_PIN` fails; the head step with a fixture edited locally warns and does not fail on a PR;
  - `go test -mod=vendor -count=1 ./frontend/ -run 'Vault|ContractFields|AllowList'` stays green (9/9 at `f89ce24`).
- x402:
  - `npm test` and `test:kat` unchanged;
  - `python -m pytest python/tests/unit/test_pq.py`, including the new length test and the existing Falcon vector signing (keys and signatures from `pq_vectors.json` must still match byte for byte);
  - `python -m x402_ycash.pq.falcon` (the documented build-and-check step) passes.

## 6. Acceptance criteria

- YEW:
  - `sha256sum core/tests/vectors/pq_falcon_kat.json` = `5afd31f5debd290c…`;
  - `scripts/check-node-vectors.sh --files` lists the KAT and the 16 Falcon sources;
  - `core/pq-c/falcon/` equals `ycash-dd@8af82551b:src/crypto/pq/falcon/`;
  - the `r3_all` replay asserts 100 rows;
  - CI runs `check-proto-pin.sh --required`.
- x402:
  - `vectors/PIN` exists;
  - `scripts/check-node-files.sh` runs in CI with no skip path and covers the two PQ vector files, the Sapling key components and the 16 Falcon sources;
  - `_falcon_c/` equals the node at the pin;
  - `c_verify` takes `pklen`.
- lightwalletd: `testdata/NODE_PIN` exists and is written by the sync script; the required CI step compares against it; a node commit alone no longer turns lightwalletd's PR CI red (the head comparison warns on PRs and fails only in the daily `node-drift` job).
- All three clients' README/doc text names the PIN instead of a prose commit.

## 7. Risks and side effects

- **Re-pin churn.** Node reports that change the vector files (the W3 node reports, `W3-P-2`'s byte-identity work) will turn YEW's and x402's steps red until each client resyncs. That is intended. For lightwalletd the opposite trade is made on purpose: a node change no longer blocks its PRs, so the daily `node-drift` job is the only signal and must not be switched off.
- **Behaviour change in the vendored C.**
  - The wipes do not change outputs; the KAT and vector replays prove it.
  - The length check makes the C verifier stricter, which can only refuse inputs the Rust/Python gates already refuse.
  - YEW's FFI signature change is a link-level change. A mismatch between the declaration and the compiled C would be undefined behaviour, so the declaration and the C must change in one commit, and the mobile builds must be run.
- No wire, key or address change; no app change; no lightwalletd code change (fixtures and CI only).

## 8. Effort estimate and dependencies

- YEW: ~0.5 day (copy, script lists, `r3_all` test, FFI update, `--required`). x402: ~0.5 day (PIN, script, CI, ctypes update, test). lightwalletd: ~2 hours (PIN, script flag, two CI steps).
- Depends on nothing; the three repos land independently. Re-run each client's resync after any node change to these files. The node-side counterpart that extends the *node's* own cross-line byte-identity step to all vector files is `MEDIUM-W3-P-2-ycash-cross-line-byte-identity-manifest.md`.
