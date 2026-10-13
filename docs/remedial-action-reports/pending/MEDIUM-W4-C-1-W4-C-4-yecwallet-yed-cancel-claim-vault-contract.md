# MEDIUM — W4-C-1 (+ W4-C-4 Info) — YecWallet's "Cancel claim" calls `vault_buildcancel`, which the node refuses for every YED intent, and tells the attestor the burn "is NOT refunded": build with `yed_buildcancel`, correct the CAN-1 refund text everywhere, and give YecWallet a pinned vault-RPC contract check

Repos / branches to change: `yecwallet-dd` only (`fix/W4-C-1-yed-cancel` off `upgrade/vault`). No node change: both node lines already serve `yed_buildcancel` (CAN-1). Coordinates with the node's cancel-limit work `HIGH-W3-Y-2-ycash-yed-cancel-limit-escalation-c4b.md` (§8).
Audit source: wave 4 `docs/audits/quantum-vault-ecosystem-wave4/04-clients-wyec-recheck.md:66` (STATUS row: recorded as W4-C-1), `:110` and `:113` (NEW findings rows W4-C-1, W4-C-4), `:115-151` (W4-C-1 evidence, impact, fix), `:203-209` (W4-C-4), `:286` (test fidelity: no vault-contract copy); `docs/audits/quantum-vault-ecosystem-wave4/00-consolidated.md:44` (W4-C-1 Medium, confirmed by the coordinator), `:49` (W4-C-4 Info), `:65` (priority 4). First observed by the writer of `HIGH-W3-Y-2-…` (§7 "Clients", not an audit ID at the time). Background: CAN-1, `done/HIGH-03-H-1-ycash-yed-claim-cancel-refund.md`.
Status: pending — verified at yecwallet-dd `c830233`, node `ycash-dd` `da5e0fe` and `ycash6` `0742e43` (2026-10-13)

## 1. Finding

**W4-C-1.** A member of the YED attestor set who runs YecWallet cancels a wrong-price claim from the Pending claims page. The button calls `YellowbackController::buildCancel`, which calls the vault primitive's `vault_buildcancel`. Since CAN-1 (audit 03/H-1, done) a YED claim intent can only be cancelled by a transaction that also refunds the claim's burn, so the node's `vault_buildcancel` refuses every intent tagged `YED\0` with `"a YED claim intent is cancelled with yed_buildcancel (its cancel refunds the claim's burn, CAN-1)"`. Every intent on the Pending claims page is a YED claim intent, so the button always fails. It fails closed: the error comes back from the build step, before `set_signcancel`, so nothing is signed, no sign-once record is written, and there is no equivocation risk and no direct loss.

The cost falls on a safety function. Within the claim delay, an attestor using the GUI cannot stop a wrong-price claim; the member has to know to fall back to the CLI (`yed_buildcancel` + `set_signcancel` + `vault_send`). If no member does so in time, the vault owner loses the collateral to the claimant. Hawkeye never calls `yed_*` (workspace rule), so YecWallet is the only shipped GUI for this role, which is why wave 4 rates it Medium rather than Low. The flow also misinforms. The confirm dialog the attestor accepts says "the claimant's burn of %4 of YED is NOT refunded. Cancelling an honest claim takes that burn from someone who did nothing wrong", the pre-CAN-1 rule. The same false statement appears in nine other places, including what the **claimant** is told before claiming and after a cancel. Under CAN-1 the cancel re-issues the claim's whole burn as a YED token to the holder of the claim's lowest-index YED input (the claimant, for a claim built by `yed_claim`); only the claimant's YEC costs (protocol fee, network fees) are lost.

**W4-C-4 (Info), why it went unnoticed.** YecWallet mirrors the node's `doc/yellowback-rpc-contract.json` and checks its `yed_*` constants against it in CI, but it calls eight vault-primitive RPCs (`src/vaultrpc.h`) and holds no copy of `doc/vault-rpc-contract.json`. Nothing tests those names or shapes. Its offline QTest's fake transport answers `vault_buildcancel` with a success, so the CAN-1 refusal never reached YecWallet's CI. The devnet case that would have shown it runs only on manual dispatch.

## 2. Root cause (yecwallet-dd `c830233`; node `ycash-dd` `da5e0fe`, `ycash6` `0742e43`)

- **The call.**
  - `src/yellowbackcontroller.cpp:1178-1180` `buildCancel` → `call(VaultRpc::VAULT_BUILDCANCEL, [outpoint])`; declared at `src/yellowbackcontroller.h:361` ("vault_buildcancel").
  - `src/vaultrpc.h:26` `VAULT_BUILDCANCEL = "vault_buildcancel"`; the header comment `:11` and the `Cancel` namespace comment `:82`, `:96` name it.
  - Only caller: `src/yellowbacktab.cpp:2066` `YellowbackTab::cancelClaim`, build at `:2110`, error label at `:2144` (`failed(VAULT_BUILDCANCEL, e)`). Tooltip `:1943`, header comments `src/yellowbacktab.h:42, 103`, docs `docs/yellowback.md:38` (action table) and `:527` (file table; it lists seven vault RPCs and omits `set_leave`).
- **The node refusal.** `ycash-dd/src/rpc/vault.cpp:1840-1841` (`BuildIntentCancel` with `yedAllowed = false`, the path `vault_buildcancel` takes); ycash6 `src/rpc/vault.cpp:1862`. Documented in `ycash-dd/doc/vault-rpc.md:387-391`, which also says this refusal is deliberately not in the vault contract's error table.
- **The RPC to use.** `yed_buildcancel "intentoutpoint"` (`ycash-dd/src/rpc/yellowbackwallet.cpp:1805-1878`, same line on ycash6): `vault_buildcancel`'s transaction with the refund carrier at `vout[1]`; result `{hex, required, cancelsetid, deadline, intentconfirmed, refund: {vout, script, cents}}` and no `sighash`/`build` fields. It refuses a mempool claim that spends an unconfirmed output, and refuses while the Yellowback index lags the tip. It is already in YecWallet's contract copy (`docs/yellowback-rpc-contract.json:496`, byte-identical to the node's) but not in `src/yellowbackrpc.h`. Rule text: `ycash-dd/doc/yellowback-spec.md:525` (U-23, CAN-1) and `:526` ("Given up by CAN-1", the YEC costs).
- **The false refund statements** (all pre-CAN-1):
  - attestor: `src/yellowbacktab.cpp:2098-2107` (confirm dialog, "is NOT refunded… takes that burn from someone who did nothing wrong"), `:2131-2133` ("Cancel sent… the claimant's burn is not refunded");
  - claimant: `:1873` (claim confirm, "does NOT refund the %3 of YED you burn"), `:1221-1222` (claim result, "the YED burned is not refunded"), `:1971` (`describeCancelledClaims`, "the %4 of YED it burned are not refunded");
  - everyone: `:1919-1923` (Pending claims intro), `src/yellowbackmodels.cpp:938-939` (intent tooltip), comments `src/yellowbackmodels.h:335` and `src/yellowbackcontroller.h:365`, and `docs/yellowback.md:38` ("a warning naming the claimant's lost burn") and `:51`.
  - The dialog also states the burn as `c.vault.mintedCents` (`:2106`), while the refund is the CLAIMING record's `burnedCents` (which includes any sub-dollar over-burn).
- **Tests that encode the old behaviour.**
  - `tests/yellowbacktab_test.cpp:1586-1655` `cancelClaimFlow`: the fake transport answers `vault_buildcancel` (`:1597`) and the test asserts it is called (`:1618`) and that the text says "NOT refunded" (`:1610`) / "burn is not refunded" (`:1623`).
  - `:1656-1676` `cancelledClaimsAreShown` (`:1675`), `:2437` (claim confirm text).
  - The devnet case `:4127-4364` `devnetClaimReleaseAndCancel` (QSKIP without `YELLOWBACK_DEVNET_DIR`; runs only on `workflow_dispatch` with the `devnet` input, `.github/workflows/yecwallet-tests.yml:30-37`). It asserts no error notice from the cancel (`:4329`), "NOT refunded" (`:4330`), "it burned are not refunded" (`:4353`) and an unchanged YED balance after the cancel (`:4354`). Against today's node it fails at `:4329`.
- **W4-C-4.**
  - `tests/check-rpc-contract.py` checks only `src/yellowbackrpc.h` against `docs/yellowback-rpc-contract.json` (`:6-31`); CI runs it at `.github/workflows/yecwallet-tests.yml:67-68`.
  - The contract-copy step `:72-94` compares the Yellowback contract against the node's `upgrade/vault` **head** (the moving-branch shape of W4-C-3).
  - There is no `docs/vault-rpc-contract.json`; `src/vaultrpc.h` carries no `// contract:` markers.

## 3. Fix options considered

1. **Keep `vault_buildcancel` and append the refund output in the GUI.** Rejected: the GUI would have to find the refund holder (the lowest-index YED input's script, or for a mempool claim, read through the index) and re-implement CAN-1. That is the node's job, and `yed_buildcancel` exists for it.
2. **Switch to `yed_buildcancel` now, with the single-signature flow** (wave 4's fix). Accepted. It works on today's node on both lines, and it is the shape the CAN-2 extension builds on.
3. **Wait for the cancel-limit work (`HIGH-W3-Y-2-…`) and do both in one client PR**, as that report's §7 suggests. Rejected as the plan: the GUI's safety function is broken now, and the CAN-2 node change is a larger consensus change with its own review gate. Land this first; `HIGH-W3-Y-2`'s client item extends it (§8).
4. **W4-C-4: assert that names the vault contract marks "YED-refused" are not used** (wave 4's suggestion). Not possible as stated: the node's vault contract does not mark the refusal (`vault-rpc.md:387-391` keeps it out of the error table on purpose). Accepted instead: mirror and pin the vault contract, check every `VaultRpc` name and field against it, **delete** `VAULT_BUILDCANCEL` from the wallet (it never cancels a non-YED intent), and make the fake transport answer `vault_buildcancel` with the node's real CAN-1 refusal. A node-side annotation in the contract generator (for example `"refuses": ["YED\\0"]`) would let the check be fully mechanical. That is optional, a node change request, and not needed for this fix.

## 4. Recommended fix

1. **RPC constants** (`src/yellowbackrpc.h`).
   - Add `YED_BUILDCANCEL = "yed_buildcancel"` beside the other `yed_*` methods.
   - Add a namespace `BuildCancel { // contract: yed_buildcancel` with `HEX`, `REQUIRED`, `CANCEL_SET_ID`, `DEADLINE`, `INTENT_CONFIRMED`, `REFUND`, and a namespace `BuildCancelRefund { // contract: yed_buildcancel.refund` with `VOUT`, `SCRIPT`, `CENTS`. `check-rpc-contract.py` then verifies them against the existing Yellowback contract copy.
   - In `src/vaultrpc.h`, delete `VAULT_BUILDCANCEL` and `ERR_NO_LONGER_CANCELLABLE`'s "vault_buildcancel" comment wording (the message is the same from `yed_buildcancel`, which goes through `BuildIntentCancel`). Keep the `Cancel` namespace for `set_signcancel`'s fields (`COMPLETE`, `SIGNATURES`), and rewrite the header comment (`:9-13`) to "a YED claim intent is cancelled with `yed_buildcancel` (CAN-1) + `set_signcancel` + `vault_send`".
2. **Controller** (`src/yellowbackcontroller.{h,cpp}`). `buildCancel` calls `YellowbackRpc::YED_BUILDCANCEL` with `[outpoint]` (`yed_buildcancel` takes exactly one parameter). Update the comment at `.h:361` and `.h:365`.
3. **Flow** (`YellowbackTab::cancelClaim`, `src/yellowbacktab.cpp:2066-2146`).
   - Keep the order: checks, confirm, build, sign, keep, send.
   - In the confirm text, state the burn as `c.vault.burnedCents` (fall back to `mintedCents` only when the record has none).
   - After the build and **before** `set_signcancel`: require `refund.vout == 1`, a non-empty `refund.script`, and `refund.cents == c.vault.burnedCents` when the latter is known. On a mismatch, show "The node built a cancel whose refund differs from the claim's burn; nothing was signed." and stop. A member's signature on a prevout is single-use (sign-once), so a build that would be refused (`intent-cancel-no-refund`) must never be signed.
   - Map the two new `yed_buildcancel` refusals to plain text: the mempool claim with an unconfirmed input ("try again after the claim's inputs confirm, before height %deadline") and the index lag ("the node is catching up; try again in a moment").
   - `failed(VAULT_BUILDCANCEL, e)` at `:2144` becomes `failed(YED_BUILDCANCEL, e)`. Tooltip `:1943`: "(yed_buildcancel, set_signcancel, vault_send)".
4. **Correct the refund text** (every place listed in §2). Wording, as one source sentence reused via a helper (for example `YellowbackTab::cancelRefundSentence()`), so the ten copies cannot drift again:
   > A cancel returns the collateral to the vault, which is ACTIVE again with its debt unchanged, and re-issues the claim's burn of %1 of YED to the holder it was burned from (the claimant). The claimant's YEC costs (the protocol fee and network fees) are not refunded.
   - Attestor confirm (`:2098-2107`): replace the "NOT refunded … takes that burn from someone who did nothing wrong" sentences with the one above, and keep the warning's purpose: "Cancel only a claim made at a wrong price. Each cancel costs an honest claimant the claim delay and its YEC fees, and the vault stays open while its collateral may keep falling." Keep the equivocation and sign-once paragraphs unchanged.
   - "Cancel sent" (`:2131-2133`): "…and the claimant's burn of %1 of YED is re-issued to it at %2:1."
   - Claimant side (`:1221-1222`, `:1873`, `:1971`): the claim confirm says a cancel re-issues the burned YED to you and costs you the fees and the delay. `describeCancelledClaims` says "…was cancelled by the attestor set: the %4 of YED it burned were re-issued to you; the collateral went back to the vault."
   - `:1919-1923`, `yellowbackmodels.cpp:938-939`, comments `yellowbackmodels.h:335` and `yellowbackcontroller.h:365`.
   - `docs/yellowback.md:38` (RPC column `yed_buildcancel`, `set_signcancel`, `vault_send`; "a warning naming the claimant's YEC costs and the equivocation risk"), `:51`, `:527` (eight RPCs, including `set_leave`; `vault_buildcancel` removed).
5. **W4-C-4: a pinned vault-contract check.**
   - Add `docs/vault-rpc-contract.json`, a copy of the node's `doc/vault-rpc-contract.json`, and `docs/NODE_PIN` in YEW's format (`ycash-dd <full commit> upgrade/vault <date>`, then a `ycash6` line), at `da5e0fe…` (= `bb21b675d` for the contract files).
   - Add `scripts/sync-node-contracts.sh`, the shape of lightwalletd's script after `LOW-W3-C-3-W3-C-4-W4-C-2-W4-C-3-…` step 13: it copies both contracts from a local tree or GitHub, writes `NODE_PIN`, and has `--check --required --pinned`.
   - CI (`yecwallet-tests.yml:72-94`): compare **both** contract copies against `NODE_PIN` (required). Turn today's branch-head comparison into a report-only warning, so a node doc commit no longer turns YecWallet's CI red (the W4-C-3 lesson, applied from the start).
   - Extend `tests/check-rpc-contract.py` with a `--vault` pass (run by default): every `constexpr const char*` method constant in `src/vaultrpc.h` must be a key of `methods`; each field namespace carries a `// contract: <method>[.path]` marker and its constants must be result fields there (`Info` → `vault_getinfo`, `Set`/`Member` → `set_getinfo`, `Heartbeat`, `Leave`, `Cancel` → `set_signcancel`); and `vault_buildcancel` must not appear anywhere under `src/` (a one-line denylist with the CAN-1 reason, until the contract can express it).
6. **Workspace** (coordinator, not this repo): `docs/mapping.md` §12 (wallet) gets the row "a YED intent is cancelled with `yed_buildcancel`; the GUI pins and checks the vault contract as well as the Yellowback one".

## 5. Tests

- **Offline QTest, `cancelClaimFlow`** (`tests/yellowbacktab_test.cpp:1586-1655`), rewritten:
  - the fake transport answers `yed_buildcancel` with the contract example shape (`hex`, `required`, `cancelsetid`, `deadline`, `intentconfirmed`, `refund: {vout: 1, script, cents: <the claim's burnedCents>}`) and answers `vault_buildcancel` with the node's real error text, `"a YED claim intent is cancelled with yed_buildcancel (its cancel refunds the claim's burn, CAN-1)"`;
  - assert `h.rpc.count("vault_buildcancel") == 0` throughout and `h.rpc.lastParams("yed_buildcancel") == [outpoint]`;
  - the confirm text names the re-issued burn and the YEC costs, and contains neither "NOT refunded" nor "did nothing wrong";
  - **refund mismatch:** `refund.cents` ≠ `burnedCents`, or `refund.vout` ≠ 1 → an error notice, `set_signcancel` count 0, no `QSettings` record;
  - the two new refusals render their plain-text hints;
  - the existing re-send, partly-signed, non-attestor and matured cases are kept as they are.
  - This is the test that would have caught W4-C-1: with today's code it fails on the first `vault_buildcancel` count.
- **Text cases.** Update `:1675` (`cancelledClaimsAreShown`) and `:2437` (claim confirm) to the new sentences. Add a guard over every user-visible string the tab and models produce in the cancel and claim flows: "not refunded" must not appear with "burn"/"YED" (extend `h.copyIsClean()` with that rule).
- **Devnet case** `devnetClaimReleaseAndCancel` (`:4127-4364`): expect the cancel to succeed through `yed_buildcancel`; the claimant's `confirmedCents()` after the cancel confirms is `yedBefore + 10000` (the $100 burn re-issued, replacing `:4354`), and `lblCancelledClaims` says it was re-issued. Run it on **both** node lines via `workflow_dispatch` (`node_line` input) and record both runs in the PR. Wave 4's "a member key cancels a wrong-price claim end to end from the controller" is this case.
- **Contract checks.** `python3 tests/check-rpc-contract.py` passes with the new `yed_buildcancel` namespaces and the `--vault` pass. Negatives recorded in the PR: re-adding a `VAULT_BUILDCANCEL` constant, renaming a `Member` field, or a `NODE_PIN` at a commit before `ce6df11` each fail with one line naming the problem.
- Run: the offline QTest binaries under `QT_QPA_PLATFORM=offscreen` (`ctest`), `tests/check-rpc-contract.py`, the copy check.

## 6. Acceptance criteria

- `grep -rn vault_buildcancel src/` is empty. The Cancel action calls `yed_buildcancel`, checks the refund before signing, and cancels a wrong-price claim end to end on a devnet of each node line.
- No user-visible string or doc in `yecwallet-dd` says a cancelled claim's burn is not refunded. The attestor's and the claimant's texts both state the CAN-1 refund and that the YEC costs are not refunded.
- `docs/vault-rpc-contract.json` and `docs/NODE_PIN` exist. CI checks both contract copies against the pin and every `VaultRpc` name and field against the vault contract.
- The offline QTest fails on the pre-fix code and passes on the fix.

## 7. Risks and side effects

- **A refused build after confirmation.** `yed_buildcancel` refuses a mempool claim with unconfirmed inputs and refuses while the index lags. The attestor must retry within the deadline; the hints say so. This is the node protecting the member's single signature, and it is not a regression (today every cancel fails).
- **Remembered builds.** `yed_buildcancel` remembers its build and locks the fee inputs, as `vault_buildcancel` did. A build that the refund check rejects leaves them locked until a rebuild or restart. Acceptable: the case should not happen with an honest node, and nothing was signed.
- **Text-only changes elsewhere** (claimant pages, docs) change no RPC call. The "not refunded" guard prevents the same drift if the rule changes again.
- **The CAN-2 change will reshape this flow.** When `HIGH-W3-Y-2-…` lands on the node, `yed_buildcancel` gains `entries[]` and refuses a build with fewer than `cancelsRequired` entries. This fix's single-signature flow then stops working past the first cancel of a vault until the client extension lands (§8). Ship them in step: the node release that carries CAN-2 must ship with the extended YecWallet.
- No consensus, wire or vector change. The vault-contract pin adds one more file to resync when the node's vault docs change, and that is its purpose.

## 8. Effort estimate and dependencies

- Flow, constants, refund check and texts: ~1 day. Contract mirror, pin, script and `--vault` checks: ~0.5 day. Tests, including both devnet runs: ~0.5 day. Total ~2 days.
- **Depends on nothing on the node:** `yed_buildcancel` exists on `ycash-dd` `da5e0fe` and `ycash6` `0742e43`.
- **Relation to `HIGH-W3-Y-2-ycash-yed-cancel-limit-escalation-c4b.md`** (YED cancel limit, CAN-2). That report's §7 assigns the YecWallet cancel flow to its own client PR: `yed_buildcancel` with `entries[]`, `yed_signcancelstatement`, entry gathering, and the `cancelsRequired` display. Land **this** report first, so the GUI works on today's rules. `HIGH-W3-Y-2`'s client PR then extends the same `cancelClaim` function and reuses this report's refund check, `BuildCancel` constants and contract pin. It must not re-fix the `vault_buildcancel` call or the refund text: both are done here. (Both reports now cite the node refusal at `src/rpc/vault.cpp:1840-1841` on `da5e0fe`, ycash6 `:1861-1862`; `:1809` was the audited commit.) If the node's CAN-2 change lands first, this PR must include the entries from the start.
- `INFO-W3-C-6-W3-C-9-yecwallet-signed-cancel-record-rpc-password.md` (the `set_listsigned` check in the same function) lands after this one, or in the same PR.
- `LOW-W3-C-3-W3-C-4-W4-C-2-W4-C-3-yew-x402-lightwalletd-node-file-pins.md` defines the pinned-fixture shape (lightwalletd step 13) that step 5 reuses. Either can land first.
