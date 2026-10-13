# MEDIUM — W3-P-1, 04/NEW-1 — Mechanised cross-line check of every Vault chain parameter, a ycash-dd release guard, and the P8 protocol-version gating plan

**Repos / branches to change:** `ycash-dd` and `ycash6` (both; the new extractor script is byte-identical on both lines), new branch `fix/W3-P-1-cross-line-vault-params` off `upgrade/vault` in each. The workspace (`docs/mapping.md` §22, `docs/plans/yellowback-upgrade-plan.md` P8 checklist) gets doc rows only. Part A/B/C are CI and release tooling (no consensus file). Part D is a decision record plus, if the owner takes the recommended early landing, a `chainparams.cpp` / `version.h` change on both lines. Neither file is under the G-9 consensus paths, but D changes network behaviour, so it carries the four-part check in the PR body.
**Audit source:** `docs/audits/quantum-vault-ecosystem-wave3/04-cross-line-parity-activation.md:88-133` (W3-P-1), summary row `:76`; `docs/audits/quantum-vault-ecosystem-wave3/verification/04-verification.md:40` (W3-P-1 verdict, split into (a) and (b), and the three-bump "what gating requires" note), `:54-64` (NEW-1, folded in here as the verifier asks); `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:41`, priority 5 (`:102-103`). Wave 4 (re-check at the new HEADs): `docs/audits/quantum-vault-ecosystem-wave4/01-node-lines-recheck-and-delta.md:99` (STILL OPEN, Δ-free: chainparams, release script, `version.h`); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:25` (node lines: every wave-3 finding still open).
**Re-verified** at ycash-dd `da5e0fe` / ycash6 `0742e43` (2026-10-13): still open; the only node changes since the audited `d5206bc` / `1310a41` are `src/rpc/vault.cpp`, `doc/vault-rpc*`, `qa/rpc-tests/vault_refee.py` and (ycash6) one CI audit step in `yellowback-tests.yml`; Vault `nProtocolVersion` still 270013 on every network of both lines, ycash-dd still has no release workflow. One off-by-one doc citation corrected.
**Status:** pending

## 1. Finding

The two node lines must activate the vault upgrade at the same mainnet height, with the same attestor set, the same `pqFalconHeight` and the same set-maturity floor. Any difference splits the v4.5.0 population from the 6.20.0 population for good. Plan P8 sets all of them by hand, in two repositories, in the gate-passing release. Only one guard exists. `qa/yellowback-release-heights.sh` reads **this** repository's **first** `UPGRADE_VAULT].nActivationHeight =` match and `MainParams().attestorSetId`, and refuses a tag while either is unset. It runs only in ycash6's release workflow, on a tag. Nothing compares the values with the other line. The cross-line CI step and ycash-dd's `leg_cross_line` hash vector files and `src/crypto/pq`, not `chainparams.cpp` or `params.cpp`. ycash-dd has no release workflow, so the line that is not the release line has no guard at all (04/NEW-1). The release doc's "Make the same change on the other node line" (`ycash6/doc/yellowback-release.md:140`) is prose. Within one repository the guard still has gaps: it does not check that the testnet block was set or that `pqFalconHeight` is still 0, and the first-match parse assumes the mainnet class comes first.

The second half is peer gating. `vUpgrades[UPGRADE_VAULT].nProtocolVersion` is `270013` on every network of both lines. That equals `PROTOCOL_VERSION` on both lines and the version every stock v4.4.4+/Yolk peer advertises. So the stock rule "disconnect a peer below the current epoch's `nProtocolVersion`" disconnects nobody at activation. The pre-activation eviction preference (`net.cpp`, the last 1,728 blocks before a known height) never fires either. A stock node stays connected through activation and keeps relaying its fork's blocks and transactions, and no upgraded peer tells it "Version must be N or greater". The comment in `chainparams.cpp` says this is a deliberate deferral to P8. The risk is the release process: gating needs three coordinated changes on two lines, and nothing checks them. Those changes are `nProtocolVersion` raised identically, `PROTOCOL_VERSION` raised to at least that value, and a deliberate `MIN_PEER_PROTO_VERSION`, which already differs between the lines (170002 vs 270013). Verified Medium by both the auditor and the verifier.

## 2. Root cause

ycash-dd `da5e0fe`, ycash6 `0742e43` (re-verified):

- **Release guard, single repo, first match:** `ycash6/qa/yellowback-release-heights.sh:24-25` (`awk '/UPGRADE_VAULT\]\.nActivationHeight *=/{getline n; print $0 n; exit}'`), `:27-28` (the `MainParams()` body up to `TestParams()`, last `m.attestorSetId = uint256S(…)`), `:31-41` (refusal). `ycash-dd/qa/yellowback-release-heights.sh` is identical apart from the message at `:39`.
- **Where it runs:** `ycash6/.github/workflows/yellowback-release.yml:41-44` (`on: push: tags: 'v*'`, `workflow_dispatch`), `:95-100` (tag → strict, otherwise `--warn`). `ycash-dd/.github/workflows/` contains `book.yml` and `yellowback-tests.yml` only. Nothing invokes `yellowback-release-heights.sh` on ycash-dd.
- **The cross-line steps hash vectors only:** `ycash6/.github/workflows/yellowback-tests.yml:701-742` (the file list at `:725-727`; `src/crypto/pq` tree hash at `:731-737`); `ycash-dd/qa/yellowback-audit.sh:538-572` (`leg_cross_line`, list at `:553-555`, `src/crypto/pq` file by file at `:561-570`), run as a blocking leg at `:653` with `YB_OTHER_LINE_DIR` from `ycash-dd/.github/workflows/yellowback-tests.yml:500-516`. ycash6's own `qa/yellowback-audit.sh` is a different, smaller script with no cross-line leg.
- **The parameters that must agree** (all equal today):
  - mainnet `UPGRADE_VAULT`: `ycash-dd/src/chainparams.cpp:140-144` / `ycash6/src/chainparams.cpp:151-155` (`nProtocolVersion = 270013`, `nActivationHeight = NO_ACTIVATION_HEIGHT`), `pqFalconHeight = 0` at `:148` / `:159`;
  - testnet: dd `:408-414` / ycash6 `:457-463`;
  - regtest: dd `:621-625` / ycash6 `:696-700` (`nVaultMinSetMaturity = 2`); default `nVaultMinSetMaturity = 16128` at `ycash-dd/src/consensus/params.h:265` / `ycash6/src/consensus/params.h:233`;
  - `src/yellowback/params.cpp` (`MainParams` `:158-178`, `TestParams` `:180-194`): byte-identical across lines today. `startHeight` is not a separate knob; it is derived from the Vault height when the attestor set is non-null (`src/yellowback/index.cpp:992-1001`).
- **Peer gating:** `PROTOCOL_VERSION = 270013` (`ycash-dd/src/version.h:12`, `ycash6/src/version.h:18`); `MIN_PEER_PROTO_VERSION = 170002` (dd `version.h:21`) vs `270013` (ycash6 `version.h:26`, comment "agreed as the floor across ycashd and Yolk/Zebra"; ycash6 also has `MIN_TESTNET_PEER_PROTO_VERSION = 270013`, `:56`, and the `CINV_WTX_VERSION = 0x7FFFFFFF` sentinel, `:51`). The epoch gate: `ycash-dd/src/main.cpp:6292-6306` (version message) and `:6443-6458` (existing connection), `ycash6/src/main.cpp:8321-8336`. The pre-activation eviction preference is in `net.cpp:938-952` on both, with `NETWORK_UPGRADE_PEER_PREFERENCE_BLOCK_PERIOD = 1728` (`net.h:80`, both). `DEFAULT_NU_REJECT_OLD_VERSIONS = true` (dd `main.h:140`, ycash6 `main.h:168`).
- **Other assigned protocol versions** (the value P8 picks must not collide in meaning): dd mainnet NU5 `270015` (`chainparams.cpp:137`), regtest NU5 `270014` (`:618`); ycash6 NU5 `270015`, NU6 `270120`, NU6.1 `270140`, NU6.2 `270150` (mainnet block).
- **Tests that hard-code the Vault protocol version:** `qa/rpc-tests/vault_dos.py:57` and `qa/rpc-tests/vault_pq_relay.py:31` (`PROTO = 270013  # UPGRADE_VAULT's nProtocolVersion`), identical on both lines.

## 3. Fix options considered

1. **More prose in `doc/yellowback-release.md`.** This is what failed: rejected.
2. **Extend `yellowback-release-heights.sh` with more `awk`/`sed`.** The first-match parse is the bug class; more regexes against a 900-line C++ file repeat it. Rejected as the main mechanism; the script stays as the entry point and calls the extractor.
3. **Move the Vault parameters into one shared, byte-identical file** (e.g. `src/vault/chainparams_vault.inc`, included by both `chainparams.cpp`) so byte identity (W3-P-2's manifest) guarantees equality. This is the cleanest end state. It changes `chainparams.cpp` structure on both lines, and the four `nActivationHeight` sites differ in shape (regtest uses `-nuparams`), so the include needs per-network macros. It would be a reasonable follow-up. Not chosen for this fix: the extractor below gives the same guarantee with no product-code change.
4. **A small stdlib-Python extractor, byte-identical on both lines, that prints a canonical JSON of every Vault parameter per network class, plus a comparator. CI runs it on every push; the release guards run it on tags on both lines.** Recommended, with the verifier's NEW-1 points: parse by class body, not first match; cover testnet and regtest; check `pqFalconHeight`, `nVaultMinSetMaturity` and `params.cpp`; give ycash-dd a guard of its own.
5. **Protocol version:** (a) leave all three numbers to P8 and guard them at tag time only; (b) **land the bump now on `upgrade/vault`** (both lines, identical value) and guard it continuously. P8 then sets heights only, and every regtest/devnet run from today exercises the disconnect path. Recommended: (b), with (a)'s tag-time checks as well. The owner picks the value. Raising `MIN_PEER_PROTO_VERSION` to the Vault version was **rejected**: an upgraded node would refuse every stock peer *before* activation and partition the network weeks early. That is the opposite of the eviction-preference design.

## 4. Recommended fix

### A. The extractor: `qa/yellowback-vault-params.py` (new, byte-identical on both lines)

Python 3 stdlib only (it runs in the release workflow's `version` job, which has no venv). Two subcommands:

- `extract [--root DIR | --git-ref REF [--git-dir DIR]]` reads `src/chainparams.cpp`, `src/consensus/params.h`, `src/version.h` and `src/yellowback/params.cpp` from a directory or from a git object (`git show REF:path`, so CI can read the other line without a checkout). It prints canonical JSON (sorted keys):
  ```json
  {"version": {"PROTOCOL_VERSION": 270013, "MIN_PEER_PROTO_VERSION": 170002, "MIN_TESTNET_PEER_PROTO_VERSION": null},
   "main":    {"vault_protocol_version": 270013, "vault_activation_height": "NO_ACTIVATION_HEIGHT",
               "pq_falcon_height": 0, "vault_min_set_maturity": 16128},
   "test":    {...}, "regtest": {...},
   "yellowback_params": {"MainParams": "<sha256 of the normalised body>", "TestParams": "<…>",
                         "main_attestor_set_id": null, "test_attestor_set_id": null}}
  ```
  Parsing rules:
  1. Split `chainparams.cpp` into class bodies by `class CMainParams`, `class CTestNetParams`, `class CRegTestParams`, each up to the next `^class ` or `^static C.*Params .*;`. Search only inside the body; **never** take a first match over the file.
  2. In each body, join continuation lines, then match `vUpgrades\[Consensus::UPGRADE_VAULT\]\.nProtocolVersion\s*=\s*(\S+);` and `…nActivationHeight\s*=\s*(\S+);`. Normalise `Consensus::NetworkUpgrade::NO_ACTIVATION_HEIGHT` to the string `NO_ACTIVATION_HEIGHT`.
  3. `pqFalconHeight` / `nVaultMinSetMaturity`: take the explicit assignment in the body if present, else the member default from `consensus/params.h` (`uint32_t nVaultMinSetMaturity = 16128;`). The regtest `consensus.pqFalconHeight = height;` setter (dd `:758`, ycash6 `:853`) lives outside the constructor and must not be picked up. Rule 1's body boundary handles it. Assert that the constructor body has no `pqFalconHeight` for regtest.
  4. If any expected assignment is missing or appears twice in one body, exit 2 with the file and class. A parse failure is never "unset".
  5. `params.cpp`: extract the `MainParams()` and `TestParams()` bodies by brace matching from the definition line. Hash the body with comments and whitespace stripped, so that a comment typo does not fail and any code change does. Also report the literal `attestorSetId = uint256S("…")`, or `null`.
- `compare A.json B.json [--release main]` exits 1 with a field-by-field diff when any of these differ: every `main`/`test`/`regtest` field, `version.PROTOCOL_VERSION`, the two `yellowback_params` hashes. `MIN_PEER_PROTO_VERSION` is reported but compared only after step D aligns it, gated by a flag in the script (`STRICT_MIN_PEER = True` once D lands). With `--release main`, it also applies the release rules to A:
  - R1: `main.vault_activation_height` is an integer greater than 0;
  - R2: `main_attestor_set_id` is set and non-zero;
  - R3: `main.vault_protocol_version > LIVE_NETWORK_PROTOCOL_VERSION`, a constant `270013` in the script with a comment citing `version.h` and this report;
  - R4: `version.PROTOCOL_VERSION >= main.vault_protocol_version`. Otherwise the upgraded node would be disconnected by its own rule at activation.
  - R5: `version.MIN_PEER_PROTO_VERSION <= LIVE_NETWORK_PROTOCOL_VERSION`, so no pre-activation partition;
  - R6: `main.pq_falcon_height == 0`, or the release names a different value deliberately. In that case the constant in the script changes in the same PR, and the release doc says why.
  - R7 (testnet): either both `test` height and `test_attestor_set_id` are unset, or both are set. A half-configured testnet is refused.

Add `qa/test_yellowback_vault_params.py` (unittest) with fixtures: the real files at HEAD (expected JSON checked in as `qa/yellowback-vault-params.expected.json`, which documents the current state); a synthetic `chainparams.cpp` where testnet precedes mainnet (proves no first-match dependence); a two-line `nActivationHeight =\n  3300000;`; a duplicate assignment (exit 2); a regtest `pqFalconHeight` setter outside the constructor (ignored).

### B. Wire it into CI on both lines (continuous, not only at a tag)

- **ycash6** `yellowback-tests.yml`, the "Cross-line vectors" step (`:701-742`): after the file loop, add
  ```bash
  python3 qa/yellowback-vault-params.py extract --root . > "$RUNNER_TEMP/mine.json"
  python3 qa/yellowback-vault-params.py extract --git-ref other-line/head > "$RUNNER_TEMP/theirs.json"
  python3 qa/yellowback-vault-params.py compare "$RUNNER_TEMP/mine.json" "$RUNNER_TEMP/theirs.json" || rc=1
  ```
  `--git-ref` reads with `git show`. The step already fetched `other-line/head` at depth 1. Rename the step "Cross-line vectors and Vault chain parameters".
- **ycash-dd** `qa/yellowback-audit.sh` `leg_cross_line` (`:538-572`): the same extract/compare through the leg's existing `show()` indirection. Write the other line's four files to a temp dir with `show` and run `extract --root`. The leg already blocks in upgrade mode (`:653`).
- Both lines: run `qa/test_yellowback_vault_params.py` in the `python` job next to `test_rpc_tests_classify.py` (dd `:645-647`; ycash6 equivalent).
- Add `qa/yellowback-vault-params.py`, its test and its expected JSON to the cross-line byte-identity set (MEDIUM-W3-P-2's manifest). The tool that checks parity must itself be the same on both lines.

### C. Release guards on both lines

- **`qa/yellowback-release-heights.sh` (both copies):** keep the CLI and the `--warn` mode, and replace the `awk`/`sed` body with `python3 qa/yellowback-vault-params.py extract --root . | … compare --release main` applied to this tree alone (R1-R7). The first-match parse goes. Keep the one differing message line (dd `:39`); everything else becomes identical.
- **ycash6 `yellowback-release.yml`**, "Mainnet Yellowback heights are set" (`:95-100`): on a tag, additionally fetch ycash-dd at the **pairing tag** `vault-params/v<version>` (`git ls-remote --exit-code --tags https://github.com/boyfromcave/ycash-dd.git "refs/tags/vault-params/v$version"`, then `git fetch --depth 1`). Refuse the release when the pairing tag is missing or `compare` fails. A `workflow_dispatch` run compares with ycash-dd `upgrade/vault` and only warns.
- **ycash-dd: new workflow `.github/workflows/yellowback-release-guard.yml`** (this is 04/NEW-1's missing counterpart), triggered on `push: tags: ['vault-params/*']` and `workflow_dispatch`. One job, `ubuntu-22.04`, no build:
  1. Run `qa/yellowback-release-heights.sh` (strict on a tag).
  2. Run `extract` here, and fetch ycash6 at `upgrade/vault`, or at `v<version>` if that tag already exists; `compare`.
  3. On a tag, refuse when the tag's `<version>` is not a 6.22.x version (the vault release line, `yellowback-release.yml:85`).

  The pairing tag is the ycash-dd commit whose parameters the ycash6 release `v<version>` was checked against. The release order is documented: **tag ycash-dd `vault-params/v6.22.N` first (its guard must pass), then tag ycash6 `v6.22.N`.**
- **Docs:** `ycash6/doc/yellowback-release.md` "Network parameters" (`:127-146`): replace the prose bullet at `:140` with the procedure above (pairing tag, order, the two guards, R1-R7). Add a "Protocol version" bullet: "raise `UPGRADE_VAULT.nProtocolVersion` and `PROTOCOL_VERSION` identically on both lines; never raise `MIN_PEER_PROTO_VERSION` to the Vault version". ycash-dd gets the same section in `doc/yellowback.md` (it has no `yellowback-release.md`) pointing at ycash6's doc as the release line's.

### D. The P8 protocol-version gating plan (both lines, identical values)

What gating requires, from the verifier's note made concrete:

| Constant | Today dd / ycash6 | Required at release | Why |
|---|---|---|---|
| `vUpgrades[UPGRADE_VAULT].nProtocolVersion`, main/test/regtest | 270013 / 270013 | **V** > 270013, the same on both lines and all three networks | The epoch gate disconnects peers below V once Vault is the current epoch; the 1,728-block eviction preference starts favouring ≥ V peers before it. |
| `PROTOCOL_VERSION` | 270013 / 270013 | **≥ V**, the same on both lines | An upgraded node advertising less than V is disconnected *by the other upgraded line* at activation. |
| `MIN_PEER_PROTO_VERSION` | 170002 / 270013 | **270013 on both** (align dd); never V | A floor at V would refuse every stock peer *before* activation. 270013 is the agreed live floor (ycash6 `version.h:24-26`). Pre-Canopy peers (< 270013) cannot follow mainnet past Canopy at 1,100,006 anyway. |
| `MIN_TESTNET_PEER_PROTO_VERSION` | n/a / 270013 | unchanged | ycash6-only stock 6.20.0 constant; no dd counterpart is needed (testnet has no Vault height). |
| `CINV_WTX_VERSION` (ycash6) | `0x7FFFFFFF` | **unchanged** | It must stay the sentinel. A V near Zcash's NU5 numbering must never reach it. |

**Choosing V.** Every number between 270014 and 270150 is already assigned to an unscheduled upgrade on at least one line (dd NU5 270015, regtest 270014; ycash6 NU6 270120, NU6.1 270140, NU6.2 270150). A V in that range would make an upgraded node look NU5/NU6-capable to the (inactive) eviction preference of those upgrades. Recommend **V = 270200** (above every assigned number, below the ZFUTURE sentinel), recorded as one constant per line:
```cpp
// version.h, both lines (identical text)
//! The vault upgrade's protocol version (plan P8; audit W3-P-1): above every protocol version assigned
//! to an unscheduled upgrade on either node line (NU5..NU6.2 = 270014..270150), so peers that have not
//! upgraded (270013) are disconnected when Vault becomes the current epoch.
static const int VAULT_PROTOCOL_VERSION = 270200;
static const int PROTOCOL_VERSION = VAULT_PROTOCOL_VERSION;
```
In `chainparams.cpp` (both lines, the three Vault blocks) use `consensus.vUpgrades[Consensus::UPGRADE_VAULT].nProtocolVersion = VAULT_PROTOCOL_VERSION;` and rewrite the comment ("gates no peer until P8 assigns one" becomes "peers below VAULT_PROTOCOL_VERSION are disconnected from the activation height; audit W3-P-1"). ycash-dd `version.h:21` becomes `MIN_PEER_PROTO_VERSION = 270013` with ycash6's comment. The owner may choose a different V. The extractor's R3/R4 then hold for any value above 270013.

**Recommended timing: land D now on `upgrade/vault`**, not at P8:
- No mainnet/testnet Vault height exists on either line (no public network is affected), and no `upgrade/vault` build can be released before P8, because R1/R2 refuse it.
- Regtest and devnet then exercise the disconnect path continuously. That is the only way to learn before P8 whether a client (lightwalletd, yolo, chain-viz, Hawkeye, x402, YEW through lightwalletd) or a test relies on `protocolversion == 270013`.
- P8 shrinks to "set two heights and an attestor set", which R1-R7 check.

If the owner prefers to defer D to P8, keep parts A-C (which already enforce R3-R5 at the tag) and record the deferral in the upgrade plan's P8 checklist with this table.

**Four-part check for D (for the PR body):** Zcash's `NetworkUpgrade::nProtocolVersion` gates peers per epoch in `main.cpp`'s version handling (mechanism M: the per-epoch minimum peer version). Ycash's Vault epoch uses the same mechanism unchanged; it lacks only a distinct value. Adaptation W: assign a distinct value, raise `PROTOCOL_VERSION` to match, align the dd floor. Tier: no consensus rule changes (peer policy only). Byte-identical behaviour on both lines.

**Consensus footprint:** none. `chainparams.cpp`'s `nProtocolVersion` and `version.h` are networking, not validation. No vector changes.

### E. Spec, plan and mapping

- `docs/plans/yellowback-upgrade-plan.md` P8 checklist: add "pairing tag `vault-params/v6.22.N` on ycash-dd before the ycash6 tag; both release guards green; protocol-version table (W3-P-1); YEW's compiled `vault_activation_height()` and `attestor_set_id()` set in the same release (`MEDIUM-W3-C-1-yew-token-value-fee-bound-yed-activation.md` §4 step 5)". This report owns the P8-checklist edit for both.
- `docs/mapping.md` §22: one row ("Zcash per-epoch `nProtocolVersion` gate → Vault needs a distinct V on both lines; `MIN_PEER_PROTO_VERSION` stays at the live floor") with the citations above, per workspace rule 5.

## 5. Tests

- **Extractor unit tests** (`qa/test_yellowback_vault_params.py`, part A), on both lines in the `python` job. They include the "testnet class before mainnet class" fixture that the old `awk` would have read wrongly (the regression for NEW-1).
- **Negative CI proof, once, recorded in the PR:** on a scratch branch of ycash6, change only the mainnet `pqFalconHeight` to 1 (or the regtest `nVaultMinSetMaturity` to 3). The "Cross-line vectors and Vault chain parameters" step must fail naming the field. On ycash-dd, `leg_cross_line` must fail the same way. Revert before merge.
- **Release-guard dry run:** on a scratch fork, set the mainnet Vault height and an attestor set on ycash6 only, then push a `v6.22.99-rc1`-style tag. The release workflow must refuse it (no pairing tag), and with a pairing tag on unchanged ycash-dd it must refuse with the height diff. Do the same for `vault-params/v6.22.99` on ycash-dd. Record the four run URLs.
- **Peer gating (D), functional, both lines.** Add a cell to `vault_upgrade.py`: a `NodeConn` at the old version 270013 stays connected before `ACT`. After `ACT` it receives `reject` "Version must be 270200 or greater" and is disconnected, and a fresh connection at 270013 is refused at `version`. A peer at `VAULT_PROTOCOL_VERSION` stays connected throughout. On regtest the gate is active because `-nurejectoldversions` defaults to true (`main.h:140` / `:168`).
- **Test fallout from D:** replace the hard-coded `PROTO = 270013` in `vault_dos.py:57` and `vault_pq_relay.py:31` (both lines) with a constant exported from `test_framework/util.py` (`VAULT_PROTOCOL_VERSION = 270200`, next to `YCASH_UPGRADE_ARGS`). Run the whole functional list. Every `NodeConn` that connects after activation must use it; `grep -rn 'NodeConn(' qa/rpc-tests/{vault,yellowback}_*.py` lists the candidates (`vault_dos`, `vault_pq_relay`, `vault_upgrade`, `yellowback_mining`, `yellowback_pq`, `yellowback_upgrade` on dd). Run the devnet/role suites (`yellowback_devnet_upgrade`, `yellowback_devnet_roles`, the stock-parity tier) to find any stock-binary peer expected to follow past activation.
- **Client grep (before merge):** `git grep -n '270013\|protocolversion'` in `lightwalletd-dd`, `yolo`, `chain-viz`, `hawkeye`, `x402-ycash`, `yew`, `ycash-infra`. Anything that asserts the node's `protocolversion` gets a one-line client update on its own `upgrade/vault` branch.

## 6. Acceptance criteria

- `qa/yellowback-vault-params.py` exists, is byte-identical on both lines, and is in the cross-line identity set. Its unit tests run in both `python` jobs.
- On every push, ycash6's cross-line step and ycash-dd's `leg_cross_line` compare every field listed in A (all three networks, the version constants, both `params.cpp` bodies). The scratch-branch negative fails on both lines.
- `yellowback-release-heights.sh` no longer contains a first-match `awk`, and it enforces R1-R7.
- ycash-dd has `yellowback-release-guard.yml`. ycash6's release workflow requires the `vault-params/v<version>` pairing tag and refuses on any field difference. The documented order is dd pairing tag, then ycash6 tag.
- Either D has landed (V identical on both lines and all networks; `PROTOCOL_VERSION == V`; dd `MIN_PEER_PROTO_VERSION == 270013`; the disconnect cell passes on both lines; no test hard-codes 270013 as the Vault version), or the owner's deferral and the table are recorded in the P8 checklist and R3-R5 are enforced at the tag.
- `docs/mapping.md` §22 row added. `ycash6/doc/yellowback-release.md:140`'s prose is replaced by the procedure.

## 7. Risks and side effects

- **No consensus effect** from A-C (tooling). D changes peer policy only. On regtest/devnet it disconnects old-version `NodeConn`s and any stock-binary node after Vault activates, which is the intended behaviour, so expect a round of test updates (section 5).
- **Choice of V.** A value inside 270014-270150 would make an upgraded node look NU5/NU6-capable to those upgrades' (inactive) peer preference. That is harmless while they have no height, but it is a trap for a future NU5 on Ycash. 270200 avoids it. The owner decides, and the value is recorded once per line.
- **`MIN_PEER_PROTO_VERSION` alignment on dd** refuses peers below 270013. No such peer can follow mainnet past Canopy, so this is a no-op on the live network. It is a behaviour change for any old regtest harness that connects at 170002 (mininode's default `SPROUT_PROTO_VERSION`). Run the stock-parity list.
- **Parse fragility:** the extractor fails closed (exit 2) on any unexpected shape, so a refactor of `chainparams.cpp` turns CI red rather than silently passing.
- **Release order:** the pairing tag adds one manual step. A forgotten dd tag blocks the ycash6 release, which is the intended failure.

## 8. Effort estimate and dependencies

- A + B + tests: ~1.5 days (one shared script, two CI wirings). C: ~0.5 day (two workflows, two doc sections). D: ~0.5 day code + ~1 day test fallout across both functional lists and devnet suites. Review: one reviewer for A-C; D carries the four-part check and gets the owner's sign-off on V.
- **Depends on / pairs with:** MEDIUM-W3-P-2 (the identity manifest must include the extractor; land P-2 first or together). Coordinate with LOW-01-V-7 (done: attestor set as a chain parameter), whose `params.cpp` fields the extractor reads. Independent of every consensus report.
