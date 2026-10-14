# LOW — 06/L-1, 06/L-2, 06/V6-N1 — lightwalletd's vault contract fixture is stale and CI skips silently; the 200 kB raw-transaction cap is below the node's 2 MB and below what YEW builds

Repos / branches to change: `lightwalletd` (`fix/06-L-1-vault-contract-rawtx-cap` off `upgrade/vault`). Cross-reference only: `yew` (V6-N1's client-side alternative, not recommended).
Audit source: `docs/audits/quantum-vault-ecosystem/06-clients-wallets-infra.md:176-183` (L-1), `:185-191` (L-2); verification `verification/06-verification.md:23-24` (verdicts, L-1 field attribution corrected, L-2 impact sharpened), `:66-70` (detail), `:93` (V6-N1); consolidated `00-consolidated.md` rows 06/L-1, L-2, R8, R10.
Status: done — completed 2026-10-13T07:12Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13, re-confirmed 2026-10-14 at ycash-dd 3fe3492b6 and ycash6 1ebfee622; nightly tier pending the owner's dispatch)

## 1. Finding

`testdata/vault/vault-rpc-contract.json` is the node's generated vault RPC contract as of 2026-10-11 20:21 (`232904d`); the node's file changed 46 minutes later (`b22b8d6`) and the copy was never refreshed. The diff is small — the `Member` shape and the `set_leave` result gained optional `exitheight`/`unlockheight` — and harmless at runtime (`vault_list` rows are unmarshalled with unknown fields ignored, and no set-member call is proxied), but `TestVaultContractFieldsAreDeclared` reads the copy, so the vault fields test checks the server against a contract the node no longer serves. The CI step that guards against exactly this compares only the Yellowback contract (`testdata/yellowback/contract.json`, which does match) and `exit 0`s with a `::notice` whenever the node branch cannot be fetched, so a fork of the repo, a renamed branch or a GitHub outage turns the check into a pass.

Separately, `ValidateRawTransaction` refuses any raw transaction over 200 kB (`maxHexLen = 2 * 200000`, a comment that still cites the pre-Sapling 100 kB `MAX_TX_SIZE`), while the node accepts `MAX_TX_SIZE_AFTER_SAPLING = MAX_BLOCK_SIZE` = 2,000,000 bytes and lightwalletd's own gRPC receive bound is 2 MiB + 64 KiB. YEW selects up to `MAX_INPUTS = 250` YED inputs; with 1,577-byte Falcon scriptSigs that is ≈ 394 kB signed, which the only broadcast path (the `ValidateRawTransaction` gate, no override) refuses with an argument error. The user sees a gate refusal, not "split the transaction" (V6-N1). On mainnet Falcon holders exist from block 0, so this is reachable the first time a wallet consolidates > ~126 Falcon-held YED outputs.

## 2. Root cause

- `lightwalletd/testdata/vault/vault-rpc-contract.json` sha256 `f8d8b7d1…` vs `ycash-dd/doc/vault-rpc-contract.json` `2de6e640…` (the contracts' *embedded* `sha256` stamps are `d7783c8e…` vs `5eaa4477…`). The content diff (`python3 -m json.tool` both, `diff`): the stamp line, `shapes.Member` gains `exitheight {type: height}` and `unlockheight {type: height}`, and the shape's `optional` list gains both. Node side: `ycash-dd/src/rpc/vault.cpp:328-329` (Member JSON), `:1188` (`set_leave` result); `doc/vault-rpc.md:93`. `ycash6/doc/vault-rpc-contract.json` (`bcafccfd…`) differs from ycash-dd's **only in its embedded stamp** (line 5), so a byte `cmp` must target ycash-dd's file (the one CI already resolves) or strip the stamp line.
- `lightwalletd/frontend/yellowback_contract_test.go:246-253` (`TestVaultContractFieldsAreDeclared`) reads `../testdata/vault/vault-rpc-contract.json`.
- `lightwalletd/.github/workflows/yellowback-tests.yml:88-110`: the step "The contract fixture equals the node's" resolves the node branch from the PR/base branch (`:97-103`), fetches **only** `doc/yellowback-rpc-contract.json` (`:104`), and on failure prints a notice and `exit 0` (`:105-108`); `cmp` at `:109`. `NODE_REPO_YCASH_DD` is `:60`. (The nightly devnet job has a second, richer branch-resolution block at `:196-215` with `NODE_REPO_YCASH6`; it is not reused here.)
- `lightwalletd/frontend/yellowback.go:32`: `maxHexLen = 2 * 200000 // a raw transaction is at most 100 kB on Ycash's MAX_TX_SIZE ... generous`; `:191`: `len(in.Data) > maxHexLen/2` → `badArg`. Node: `ycash-dd/src/consensus/consensus.h:29` `MAX_TX_SIZE_AFTER_SAPLING = MAX_BLOCK_SIZE` (2,000,000; same on ycash6). lightwalletd's gRPC bound: `cmd/root.go:140` `grpcMaxRecvMsgSize = 2*1024*1024 + 64*1024`, justified by the same constant at `:137-139`. `SendTransaction` has no 200 kB cap.
- YEW: `core/src/params.rs:806` `MAX_INPUTS = 250` ("the node's `maxInputs` cap for YED selection, plan §3.7"); `core/src/build/yed_transfer.rs:256-262` passes it to `select_floor_aware`; Falcon scriptSig 1,577 B (`pq.rs:639-648`, quantum spec). 250 × 1,577 ≈ 394 kB; the lightwalletd ceiling is ≈ 126 Falcon inputs.
- Existing input-validation test: `frontend/yellowback_test.go:487` covers only the empty `RawTransaction`.

## 3. Fix options considered

1. **Cap YEW's Falcon-input selection at ⌊(200,000 − overhead)/1,577⌋ ≈ 120** (V6-N1's client-side form). Rejected as the primary fix: `MAX_INPUTS` is the node's own selection cap, the node accepts the transaction, and every other client (x402, YecWallet via the node, Hawkeye) is unaffected by lightwalletd's private limit; the limit is wrong, not the client.
2. **Raise `maxHexLen` to the node's limit** (2,000,000 bytes of raw transaction, 4,000,000 hex characters to the node). Accepted. The gRPC receive bound already admits it; the node's own `yed_validaterawtransaction` enforces `MAX_TX_SIZE_AFTER_SAPLING`.
3. **Keep 200 kB and document a client-side split.** Rejected: it writes a lightwalletd quirk into every wallet's plan.
4. For CI: **fail on an unreachable node branch everywhere.** Accepted for the branches whose node branch is known to exist (`upgrade/*`, `harden/*`, the quantum line); the default mapping (`feature/yellowback-price-attest`, used by `ci/*` branches that are not `ci/upgrade*`/`ci/harden*`/`ci/q*`) keeps the notice-and-skip, since those are the branches where the node side may genuinely not exist yet.

## 4. Recommended fix

1. **Re-copy the fixture**: `cp ycash-dd/doc/vault-rpc-contract.json lightwalletd/testdata/vault/vault-rpc-contract.json` at `055d9c2` (sha `2de6e640…`). Re-run `go test ./frontend/ -run 'Vault|ContractFields'`; the forward check ("every proto field is a contract field") is unaffected (no proto change — the new fields are on `Member`/`set_leave`, which lightwalletd does not proxy); the reverse check must still pass.
2. **CI step (`yellowback-tests.yml:88-110`)** — rewrite as:
   ```bash
   case "$BRANCH" in
     ci/harden*|harden/yellowback)      node=harden/yellowback;      required=1 ;;
     upgrade/vault-in-term)             node=upgrade/vault-in-term;  required=1 ;;
     ci/q*|upgrade/quantum-vaults|q/*)  node=upgrade/quantum-vaults; required=1 ;;
     ci/upgrade*|upgrade/vault)         node=upgrade/vault;          required=1 ;;
     *)                                 node=feature/yellowback-price-attest; required=0 ;;
   esac
   for pair in "testdata/yellowback/contract.json:doc/yellowback-rpc-contract.json" \
               "testdata/vault/vault-rpc-contract.json:doc/vault-rpc-contract.json"; do
     local=${pair%%:*}; remote=${pair#*:}
     if ! curl -fsSL -o "$RUNNER_TEMP/$(basename "$remote")" "https://raw.githubusercontent.com/$NODE_REPO_YCASH_DD/$node/$remote"; then
       if [ "$required" = 1 ]; then echo "::error::$NODE_REPO_YCASH_DD@$node/$remote unreachable; the fixture check cannot run"; exit 1; fi
       echo "::notice::$NODE_REPO_YCASH_DD has no $node (or no $remote) yet; fixture comparison skipped"; continue
     fi
     cmp "$local" "$RUNNER_TEMP/$(basename "$remote")" && echo "$local = $NODE_REPO_YCASH_DD@$node $remote"
   done
   ```
   Optional second loop against `NODE_REPO_YCASH6` with the stamp line stripped (`grep -v '"sha256"'` on both sides) to honour "both node lines"; report-only at first.
3. **`frontend/yellowback.go:32`**: replace the constant and its comment:
   ```go
   // The node's post-Sapling transaction limit (ycash-dd/src/consensus/consensus.h:29
   // MAX_TX_SIZE_AFTER_SAPLING = MAX_BLOCK_SIZE = 2 000 000 bytes; the same on ycash6); the gRPC
   // receive bound in cmd/root.go is sized to it. A YED transfer of 250 Falcon-held inputs
   // (YEW's MAX_INPUTS, 1,577-byte scriptSigs) is ~394 kB and must pass here.
   maxRawTxBytes = 2000000
   ```
   and at `:191` `len(in.Data) > maxRawTxBytes`. Grep for other `maxHexLen` users (`frontend/`) and convert them to the same constant (hex-string callers compare `2 * maxRawTxBytes`).
   Rate limiting: `ValidateRawTransaction` already charges `yedCostHeavy` (`:188`); if the limiter's budget was sized for 200 kB bodies, scale the cost by `ceil(len/200000)` so a 2 MB validate costs ten heavy units (one-line change in `limited`'s caller; check `yellowback_ratelimit.go` for the unit).
4. **Docs**: `docs/` (lightwalletd's plan section on input bounds) and the workspace `docs/mapping.md` §15 row for the cap: "2 MB, the node's; was 200 kB".

## 5. Tests

- `TestVaultContractFieldsAreDeclared` on the refreshed fixture (both directions) — green.
- New Go test in `frontend/yellowback_test.go` next to `:487`: with a stub RPC that records the hex it receives, `ValidateRawTransaction` with a 1,999,999-byte body reaches the stub (hex length 3,999,998) and a 2,000,001-byte body returns `InvalidArgument` without calling the stub. Also a 394,000-byte body (the YEW Falcon maximum) reaches the stub — the regression this report exists for.
- Rate-limit test (if step 3's cost scaling is adopted): a 2 MB validate consumes ten units in `yellowback_ratelimit_test.go`'s harness.
- CI negative, once in the PR: set `NODE_REPO_YCASH_DD` to a non-existent repo in a throwaway commit → the step fails with `::error` on `upgrade/vault`; revert.
- Devnet (`yellowback_devnet_test.go:466` already drives `ValidateRawTransaction` end to end): add, behind the existing devnet build tag, one validate of a node-built transaction > 200 kB (`yed_transfer` of many Falcon tokens via `yellowback-devnet`, or `createrawtransaction` padding) — optional, nightly.

## 6. Acceptance criteria

- `sha256sum testdata/vault/vault-rpc-contract.json` = `2de6e6409d97c7b1…` (= `ycash-dd@055d9c2 doc/vault-rpc-contract.json`).
- The CI step compares both fixtures and exits 1 on an unreachable node branch for `upgrade/*`, `harden/*`, `ci/upgrade*`, `ci/harden*`, `ci/q*`, `q/*`; the PR links one deliberately failing run.
- `frontend/yellowback.go` has no `200000` literal; the cap equals 2,000,000 raw bytes with the consensus citation; the boundary test exists and runs in the `-run` regex of the frontend job (`yellowback-tests.yml:116`; the names must match `InputValidation|…`).
- `go test -mod=vendor ./frontend/ -run 'Vault|ContractFields|InputValidation'` green.

## 7. Risks and side effects

- A 2 MB `ValidateRawTransaction` is ~10× the previous worst case per call; the heavy rate-limit cost (and the optional size scaling) bounds it, and the node's own RPC does the work either way. No new exposure beyond what `SendTransaction` already accepts.
- Making the fixture check fail on fetch errors means a GitHub raw outage reds lightwalletd's CI; acceptable (re-run), and it is the documented behaviour of the node-line checks elsewhere.
- The vault contract will change again when R5/R7 (`vault_buildunlock` idempotency, "call once" docs) and R1 land on the node; each re-copy is one commit; the CI step is the reminder.
- YEW needs no change for V6-N1 once the cap is raised; if the owner prefers belt-and-braces, YEW can surface "this transfer needs N inputs; your server validates up to M bytes" from the gate error — not recommended here.

## 8. Effort estimate and dependencies

- ~0.5 day (fixture copy, constant, test, CI step). No consensus review. Depends on nothing; coordinate the re-copy with the node reports that change `doc/vault-rpc-contract.json` (R5 `MEDIUM-01-V-2-ycash-set-sig-anyonecanpay.md`, R7 `MEDIUM-07-F-5-ycash-sign-once-record-restore.md`) by re-running the CI step after they land.

## Completion record

- **Completed:** 2026-10-13T07:12Z
- **lightwalletd-dd** `upgrade/vault` merge 9dd0f7a (branch `fix/clients`):
  - 5f22bee: `maxRawTxBytes = 2000000`, matching the node; rate cost scales per 200 kB.
  - 983077a: the vault fixture is re-synced from ycash-dd 055d9c2; new `scripts/sync-node-contracts.sh` (`--check`, `--github`, `--required`); CI fails, never skips, on `upgrade/*` and `harden/*`; `VaultSetMember` gains `exitheight` and `unlockheight` (the proxy was silently dropping them; regenerated with the pinned generators).
- **Workspace:** mapping §15 row (merge 8b9d1b5).
- **Tests:** frontend 41/41, including `TestInputValidationRawTxSize` and `TestRateLimitRawTxCost`; the other Go packages pass; the generated files reproduce.
- **Finding:** the report was wrong that the reverse check would keep passing. `GetSet` proxies the member list, so the stale fixture had been hiding dropped fields.
- **Follow-up:** re-run `scripts/sync-node-contracts.sh` after the set-sig and yed-cancel node lanes change `doc/vault-rpc-contract.json`.
