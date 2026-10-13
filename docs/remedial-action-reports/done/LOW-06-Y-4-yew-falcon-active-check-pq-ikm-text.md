# LOW — 06/Y-4, 06/Y-3, 06/V6-N2 — YEW forces `falcon_active` off regtest instead of checking the server; the PQ-key IKM differs from the node's and the trust text implies portability

Repos / branches to change: `yew` (`fix/06-Y-4-falcon-active-check` off `upgrade/vault`). Docs only in the workspace (`docs/plans/yellowback-quantum-clients.md` cross-reference, no rule change).
Audit source: `docs/audits/quantum-vault-ecosystem/06-clients-wallets-infra.md:105-111` (Y-4), `:97-103` (Y-3); verification `verification/06-verification.md:18-19` (verdicts: Y-3 framing reduced to Info, Y-4 Low), `:52-56` (Y-3 detail), `:60` (Y-4), `:94` (V6-N2); consolidated `00-consolidated.md` row 06/Y-2..Y-5.
Status: done — completed 2026-10-13T12:27Z (merged and pushed on `upgrade/vault`; push-tier CI green in every repo 2026-10-13; nightly tier pending the owner's dispatch)

## 1. Finding

Off regtest, `Wallet::pq_terms()` overwrites whatever the server reported with `falcon_active = true, falcon_height = Some(0)`. That matches both node lines today (`pqFalconHeight = 0` on mainnet and testnet, owner decision D-Q-2), and the terms check does refuse a server that lists scheme 2 as *inactive* — but a server that reports Falcon inactive with scheme 2 absent, or a future node release that moves the height, is masked by the override: YEW would keep handing out Falcon holder addresses and building TOK-PQ shapes the network does not yet accept. The node's dry run and YEW's holder-shape checks stop a wrong-shaped output before broadcast, so there is no burn path; the defect is that the wallet asserts a network constant instead of verifying it.

Separately (Y-3, Info after verification), YEW derives its PQ keys with HKDF over the 64-byte BIP39 seed while `ycashd` uses its 32-byte raw HD seed, so the same words give different PQ keys in the two wallets. Cross-restore between YEW and `ycashd` was never possible for any key type (v4.5.0 has no BIP39 import; YEW has no `wallet.dat` import) and the client survey records PQ keys as not seed-portable across implementations — the only residual is the trust text's sentence "only your seed, in a wallet that knows post-quantum keys, can spend a vault", which a user can read as "any PQ-aware wallet" (V6-N2).

## 2. Root cause

- `yew/core/src/wallet.rs:598-611` `pq_terms()`: `:604-611` `if self.network != Network::Regtest { t.falcon_active = true; t.falcon_height = Some(0); }` with the doc comment "Off regtest the terms always say Falcon is active, whatever a server or the offline default says".
- `yew/core/src/build/terms.rs:528-562` `PqTerms` (`falcon_height: Option<u64>` `:546`, `falcon_active: bool` `:548`, offline default inactive `:561-562`); `:571-572` `falcon_at(height)`; `:611-623` the consistency check (`schemes ∌ 1`, an unknown scheme, or `schemes ∋ 2 ∧ !falcon_active` → `inconsistent`); `:719-720` the terms read from the server (`pq.falcon_height`, `pq.falcon_active`). `wallet.rs:623-640` `note_server_params` stores them.
- Node: `ycash-dd/src/chainparams.cpp:148` (mainnet), `:414` (testnet) `pqFalconHeight = 0`; `ycash6/src/chainparams.cpp:159`, `:463`. Regtest reads `-pqfalconheight`.
- Y-3: `yew/core/src/pq.rs:446-449` `PqSeedRoot::from_seed(seed)` with `seed = keys::seed_from_mnemonic` (`keys.rs:134-138`, `Mnemonic::to_seed`, 64 bytes) vs node `wallet.cpp:409-420` `HDSeed::RawSeed()` (32 bytes) → `DerivePQSeed` (`pqkey.cpp:71-80`); spec A-12 (`yellowback-quantum-spec.md:96-98`) binds the node's IKM only; `yellowback-quantum-clients.md:48` ("not seed-portable across implementations") and `:186`; `yew/docs/design-notes.md:524`.
- V6-N2: `yew/app/lib/trust_text.dart:16` (paragraph 3) and its source `yew/docs/trust.md` (the two must be identical: `scripts/check-trust-text.sh:6-7, 33-37`, run in CI `ci.yml` `app` job). Seed screens: `app/lib/screens/seed_backup.dart`, `app/lib/screens/onboarding.dart` (restore step `:16`, `:173`), `app/lib/state/app_state.dart:186-189` `seedWordsForBackup`.

## 3. Fix options considered

1. **Keep the override, add a log line.** Rejected: silent divergence stays silent for the user.
2. **Drop the override and trust the server entirely.** Rejected: the offline default (`falcon_active: false`) would then give a mainnet wallet P2PKH YED receive addresses before its first server answer, which TOK-PQ refuses — the override exists to prevent exactly that.
3. **Compiled-in expectation + refusal on mismatch** (the audit's fix): the network's default is a compiled constant used offline; a server answer that disagrees is an `Inconsistent` error, not silently overridden. Accepted.
4. Y-3: adopt one IKM across wallets in the spec (a node change: `DerivePQSeed` over the mnemonic seed, which v4.5.0 does not have). Rejected for now — recorded as a non-goal by the survey; reword the text instead.

## 4. Recommended fix

1. **`core/src/params.rs`**: add `pub const PQ_FALCON_HEIGHT_MAINNET: u64 = 0;` and `PQ_FALCON_HEIGHT_TESTNET: u64 = 0;` with the citations (`ycash-dd/src/chainparams.cpp:148,414`; `ycash6/src/chainparams.cpp:159,463`; D-Q-2), and `pub fn pq_falcon_height(network) -> Option<u64>` (`None` on regtest = follow the server).
2. **`core/src/build/terms.rs`**: `PqTerms::default_for(network)` returns `falcon_active: true, falcon_height: Some(0)` for mainnet/testnet and the inactive default for regtest; `pq_terms(p, network)` (add the `network` argument) checks, off regtest, `pq.falcon_height == expected && pq.falcon_active == true` and otherwise returns `inconsistent(format!("params.pq.falconHeight {} / falconActive {} (this build expects {} on {})", …))`. Keep the existing scheme-2 consistency check.
3. **`core/src/wallet.rs:598-611`**: remove the override; `pq_terms()` returns the stored terms, which start as `PqTerms::default_for(self.network)` (initialise the `pq_terms` mutex with it in the wallet constructor) and are replaced only by a server answer that passed step 2. Update the doc comment.
4. **Surface the refusal**: `note_server_params` already returns `MintError`; make the sync path treat `Inconsistent` on `params.pq` the way it treats an unscheduled Vault report (`params.rs:414-447` `UnscheduledVault`): YED features disabled with the server-settings banner, not a crash.
5. **Y-3 / V6-N2 text** (`docs/trust.md` paragraph 3 and the `trust_text.dart` copy, regenerated so `check-trust-text.sh` passes): replace "only your seed, in a wallet that knows post-quantum keys, can spend a vault" with "only your seed, restored into YEW, can spend a vault — another wallet, YecWallet or ycashd included, does not derive the same post-quantum keys from these words". Add one sentence to `seed_backup.dart` (shown with the words) and to the onboarding restore step: "This phrase restores YEW only. Vaults and YED held by post-quantum keys are not recoverable in any other wallet." Mirror in `README.md` "Restore" and `docs/design-notes.md:524`.

## 5. Tests

- `terms.rs` unit tests (next to `:1661-1667`, `:1861`): mainnet with `falcon_height = 0, falcon_active = true` → ok; mainnet with `falcon_height = 300` → `Inconsistent`; mainnet with `falcon_active = false` and scheme 2 absent → `Inconsistent` (the case the override masked); regtest with `falcon_height = 300` → ok, `falcon_at(299) == false`, `falcon_at(300) == true`.
- `wallet.rs`: a mainnet wallet with no server answer has `pq_terms().falcon_at(0) == true` (offline default) and its YED receive address is a Falcon holder (`yed_holder_script`, `yed_transfer.rs:296-320`); after a disagreeing server answer the wallet reports the inconsistency and does not change its terms.
- App: `scripts/check-trust-text.sh` passes; `flutter test` for the seed-backup screen asserts the new sentence (widget key `seed-restores-yew-only`).
- Devnet (nightly, see `LOW-06-Y-1-…`): `q_falcon_*` unchanged — regtest still follows `-pqfalconheight`.

## 6. Acceptance criteria

- `grep -n 'falcon_active = true' core/src/wallet.rs` → none; the expectation lives in `params.rs` with the chainparams citations.
- `pq_terms` refuses a mainnet/testnet server whose `pq.falconHeight`/`falconActive` differ from the compiled expectation, with a unit test per case.
- Offline mainnet behaviour unchanged (Falcon receive address before any server answer).
- `docs/trust.md` and `app/lib/trust_text.dart` carry the reworded sentence; the seed-backup and restore screens carry the "YEW only" line; `check-trust-text.sh` green.

## 7. Risks and side effects

- If P8 or a later release ever moves `pqFalconHeight` on a public network, YEW must ship a build with the new constant *before* connecting to such a node — that is the intended coupling (the same as the compiled Vault activation height in `params.rs`). Document in `docs/release.md`.
- A misconfigured lightwalletd (pointing at a regtest node while the app is on mainnet) now produces a visible inconsistency error instead of silently working with the override; good.
- No signing path changes; no vector changes.

## 8. Effort estimate and dependencies

- 0.5 day core + 0.25 day app/docs. No dependencies. Independent of `LOW-06-Y-1-…` (can share the branch if convenient).

## Completion record

- **Completed:** 2026-10-13T12:27Z
- **Merged and pushed:** yew upgrade/vault 1e250f8. 9ff253b: falcon_active checked against compiled PQ_FALCON_HEIGHT constants (a refused server hides YED with the reason shown; no override). Restore text: the same 24 words restore in YEW; other wallets do not reliably derive the PQ keys. 572e045: trust text paragraph 3 corrected (vault owners SLH-DSA, YED holders Falcon).
- **Also landed with resync-a:** b4b461f, PQ spends pay at least the ZIP-317 conventional fee (the audit 04/N-1 client follow-up).
- **Tests:** yew-core suites and flutter test pass; check-trust-text.sh ok.
