# INFO — W3-C-10, 06/N-3 — YEW's post-quantum key statements: the trust text and `pq.rs` say no other wallet derives YEW's PQ keys (false for ycash6, the release line); YEW signs SLH-DSA deterministically where the node hedges

Repos / branches to change: `yew` (`fix/W3-C-10-pq-portability-hedged` off `upgrade/vault`). Optional, cross-reference only: `yecwallet-dd` (docs). No node change.
Audit source: wave 3 `docs/audits/quantum-vault-ecosystem-wave3/06-clients-wallets-infra.md:52` (summary row), `:126-135` (W3-C-10), `:139-142` (the "SLH-DSA … as the node signs" sentence N-3 corrects); verification `docs/audits/quantum-vault-ecosystem-wave3/verification/06-verification.md:24` (verdict: true for ycash-dd, **false for ycash6**), `:245-263` (W3-C-10 detail), `:283-288` and `:313-315` (N-3); consolidated `docs/audits/quantum-vault-ecosystem-wave3/00-consolidated.md:53` ("W3-C-10 … true for ycash-dd, false for ycash6, the release line"). Wave 4 `docs/audits/quantum-vault-ecosystem-wave4/04-clients-wyec-recheck.md:50` (N-3 STILL ACCURATE: `core/src/pq.rs:21`, `opt_rand = PK.seed`), `:60` (W3-C-10 STILL ACCURATE, `trust_text.dart:16` unchanged).
Status: pending — re-verified at yew `9231787` (no change under `core/` or `app/lib/trust_text.dart` since `1e250f8`), node `ycash-dd` `da5e0fe` and `ycash6` `0742e43` (2026-10-13); every line below re-grepped

## 1. Finding

**W3-C-10.** PQ keys (vault owners, Falcon YED holders) are HKDF-derived from the wallet seed, identically on YEW and both node lines: info `"Ycash PQ key" ‖ scheme ‖ index_be32`, empty salt, 48 bytes. The lines differ only in the input key material:
- ycash-dd (v4.5.0 lineage) uses its 32-byte HD seed;
- ycash6 (6.20.0 lineage, **the release line**, and the node YecWallet bundles) uses the 64-byte BIP39 seed of its 24-word phrase. That is exactly YEW's IKM.

So a 24-word YEW phrase with an empty passphrase, restored into a 6.22.x `ycashd` with `-mnemonicfile`, re-derives YEW's vault-owner and Falcon keys. The node then re-finds the used ones from the chain up to a gap of 20 unused keys per scheme.

YEW's trust statement says the opposite: "Other wallets do not reliably derive the same post-quantum keys from these words (YecWallet and ycashd 4.5 do not at all)". `core/src/pq.rs` says "The two wallets' seeds differ anyway". Both are right about ycash-dd and wrong about the line that ships. The text errs on the safe side ("do not count on another wallet"), but it is factually inaccurate where users will look for a recovery path. Info.

**N-3.** The first-wave audit sentence "SLH-DSA is deterministic with `opt_rand = PK.seed` as the node signs" is wrong about the node. The node's `pq::Sign` uses the FIPS 205 *hedged* variant, with 16 fresh bytes from `GetRandBytes`, chosen so a repeated signature over the same message takes a fresh path (fault-attack resistance). YEW signs deterministically. Both are FIPS-205-conformant and the verifier is `R`-agnostic, so nothing breaks. But a phone is the more fault-exposed signer, the node chose hedging for exactly that reason, and YEW's comments claim parity it does not have. Info.

## 2. Root cause (yew `9231787`; ycash-dd `da5e0fe`, ycash6 `0742e43`)

- **Trust text.**
  - `yew/app/lib/trust_text.dart:16`: "…Other wallets do not reliably derive the same post-quantum keys from these words (YecWallet and ycashd 4.5 do not at all), so do not count on another wallet to recover a vault or YED…".
  - The canonical copy is `docs/trust.md:25-28`. They are kept identical by `scripts/check-trust-text.sh` (header `trust_text.dart:5-7`).
- **Code comment.** `yew/core/src/pq.rs:38-44`: "The node's IKM is its raw HD seed (32 bytes); **YEW's is its 64-byte BIP39 seed** … The two wallets' seeds differ anyway, so what matters is…". This is true of ycash-dd only.
- **Node facts.**
  - ycash-dd `src/wallet/wallet.cpp:412-423` (`HDSeed::RawSeed()`).
  - ycash6 `src/wallet/wallet.cpp:524-537` (`GetMnemonicSeed().RawSeed()`, the comment "6.20.0: the wallet's seed is its BIP39 MnemonicSeed").
  - ycash6 `src/zcash/address/mnemonic.h:15-18` (`SetSeedFromMnemonic` → `zip339_phrase_to_seed`, no passphrase parameter).
  - ycash6 `-mnemonicfile` restores PQ keys "up to a gap of %u unused keys per scheme" (the `-mnemonicfile` help text, `src/wallet/wallet.cpp:7799`; `PQ_KEY_LOOKAHEAD = 20`, `src/wallet/wallet.h:1451`), and rescans re-find used keys (`wallet.cpp:4487` calls `NotePQKeysUsed`, defined at `:666`).
  - The spec records the per-line IKM: `docs/plans/yellowback-quantum-spec.md:116-122` ("Q5 as implemented"; `pq_wallet_vectors.json` sections `hdSeed` = dd, `mnemonic` = ycash6 and YEW).
  - YecWallet bundles 6.20.0 (`yecwallet-dd/src/nodedatacheck.h:9`).
- **YEW indices.** Owner keys are paired with the external P2PKH chain index (`core/src/wallet.rs:1171-1183` `pq_owners_are_deterministic_and_paired_with_external_keys`). The node issues sequentially with a 20-key lookahead. A YEW wallet whose used owner/holder indices have gaps wider than 20 is only partly re-found without the documented `getnewaddress "" "pq"` + `rescanblockchain` step.
- **N-3.**
  - Node `ycash-dd/src/crypto/pq/sign.cpp:88-99`: `Sign` for SLH-DSA calls `SignWithEntropy` with 16 bytes from `GetRandBytes`, comment "FIPS 205 hedged variant … no fault-attack repeat". The same holds on ycash6 (PQ surface identical; consolidated `:57-61`).
  - YEW `core/src/pq.rs:559-578` `PqKey::sign`: `sk.try_sign_with_context(msg, &[], None)` (deterministic). The comment at `:556-557` reads "deterministic (`opt_rand = PK.seed`)". Similar claims are at `:21` (module doc), `:581`, `:652`, `:679` (test assertion "SLH-DSA is deterministic"), `core/src/vault.rs:686, 751` and `core/src/tx.rs:474`.
  - `slh-dsa` 0.1.0's `try_sign_with_context(msg, ctx, opt_rand: Option<&[u8]>)` takes the hedge directly (`signing_key.rs:136-141` in the pinned crate).
  - The node's SLH-DSA vectors carry empty entropy (deterministic form), so YEW's vector replays need the deterministic form kept for tests: `pq_vectors.json` `keys[*].entropy` is `""` for scheme 1.

## 3. Fix options considered

1. **W3-C-10: leave the conservative text.** Rejected. It tells a user holding a 24-word phrase that the release-line node cannot recover their vault when it can. Accepted instead: state precisely which wallets derive the keys and under what conditions, and keep "YEW is the supported recovery path" as the first advice.
2. **W3-C-10: make YEW's IKM match ycash-dd's.** Rejected: there is no 32-byte HD seed in a BIP39 wallet. The spec makes the per-line IKM normative, and ycash6 already matches YEW.
3. **N-3: hedge YEW's SLH-DSA signing** (16 bytes from `OsRng` as `opt_rand`), keeping a deterministic entry point for the vector replays. Accepted. It matches the node's choice, costs nothing at verification, and YEW never relies on SLH-DSA determinism: every broadcast uses the bytes signed at preview (`build/*`: `broadcast` sends `preview.raw`), and no code path re-signs and compares.
4. **N-3: keep deterministic and only fix the comments.** Acceptable fallback if the owner prefers byte-stable owner spends. Recorded as the alternative.

## 4. Recommended fix

1. **Trust text** (`docs/trust.md:25-28` and `app/lib/trust_text.dart:16`, edited together; `scripts/check-trust-text.sh` must pass). Replace the two sentences from "Other wallets…" to "…recover a vault or YED." with:
   > YEW is the wallet to restore these words into. Of the other Ycash wallets, only ycashd 6.22 and later (and YecWallet, which bundles it) derive the same post-quantum keys, and only from a 24-word phrase with no passphrase, restored with `-mnemonicfile`; ycashd 4.5 does not. Do not count on any other wallet.

   Keep the rest of the paragraph. This is an Info-level text change with no new promise beyond the spec's Q5.
2. **`core/src/pq.rs:38-44`**: replace "The two wallets' seeds differ anyway…" with the per-line facts: dd's IKM is its 32-byte HD seed (different from YEW's); ycash6's is the 64-byte BIP39 seed, the same as YEW's for a 24-word phrase with an empty passphrase (`pq_wallet_vectors.json` `mnemonic`). Cite the quantum spec Q5.
3. **N-3: hedged SLH-DSA signing.** In `core/src/pq.rs` `PqKey::sign` (`:559-578`):
   ```rust
   let mut opt_rand = [0u8; 16];
   rand::rngs::OsRng.fill_bytes(&mut opt_rand);
   let sig = sk.try_sign_with_context(msg, &[], Some(&opt_rand)).expect("…").to_vec();
   wipe(&mut opt_rand);
   debug_assert!(verify(self.scheme, &self.pk, &sig, msg));
   sig
   ```
   - Add `pub(crate) fn sign_deterministic(&self, msg) -> Vec<u8>` (scheme 1 only; `None` opt_rand) for the vector replays.
   - Switch the replay call sites to it: `pq.rs:680` (`pq_reproduces_the_node_vectors`), and `vault.rs:753` (`owner_spend_is_signed_byte_for_byte`). `tx.rs:486` (`Transaction::pq_signature`) is the production owner-spend signer: leave it on the hedged `sign`. If a test reaches it and compares bytes, give that test a deterministic key path instead of changing production.
   - Update the comments at `pq.rs:21, 556-557, 581, 652`, `vault.rs:686`, `tx.rs:474` to "hedged (16 fresh bytes, as the node's `pq::Sign`); the vectors use the deterministic form".
4. **YecWallet (optional, docs only).** `yecwallet-dd/docs/` (the Yellowback user notes): one sentence saying the bundled 6.20.0-line node restores PQ keys from its 24-word phrase via `-mnemonicfile`. That is the node's behaviour, not a GUI feature.
5. **Workspace.** `docs/mapping.md` §16 (YEW): add a row "PQ key portability: same keys as ycash6 for 24 words / empty passphrase; not ycash-dd".

## 5. Tests

- `scripts/check-trust-text.sh` passes, and `flutter test` (trust text widget/golden, if any).
- New `pq.rs` test `slh_dsa_signing_is_hedged`: two `sign()` calls over the same message differ, both `verify`, and `sign_deterministic` equals the node vector's signature (existing `pq_reproduces_the_node_vectors` keeps asserting that).
- Existing replays (`pq_reproduces_the_node_vectors`, `owner_spend_is_signed_byte_for_byte`, `spends_sighash_under_the_vault_branch_id`) green with `sign_deterministic`.
- Portability, devnet-tier (nightly, `YEW_DEVNET=1`, optional): start a ycash6 regtest node with `-mnemonicfile` holding the 24-word test phrase whose `mnemonic` section is in `pq_wallet_vectors.json`. The node's `getnewaddress "" "pq"` (scheme 1, index 0) must equal YEW's `pq_owner_id(0)` for the same phrase. Separately, assert in a unit test that YEW's 24-word phrase from that vector derives the vector's `mnemonic` outputs (already covered by `derivation_reproduces_the_node_wallet_vector`; confirm the section is the one exercised).
- A 12-word phrase: not claimed in the text. Add a unit note or test only if a 12-word restore into ycash6 is verified on devnet.

## 6. Acceptance criteria

- `docs/trust.md` and `trust_text.dart` name ycashd 6.22+/YecWallet as deriving the same keys under the stated conditions and ycashd 4.5 as not. `check-trust-text.sh` passes.
- `pq.rs` no longer says the wallets' seeds "differ anyway".
- `PqKey::sign` hedges SLH-DSA; vector replays use `sign_deterministic`; no comment in `core/src` claims the node signs deterministically.

## 7. Risks and side effects

- **Over-promising recovery.** The text names the exact conditions (24 words, no passphrase, `-mnemonicfile`, gap 20) and keeps "YEW is the wallet to restore into". It must not be shortened into "any Ycash wallet works".
- **Hedging changes signature bytes**, never validity; nothing in YEW compares re-signed bytes (§3.3). Owner-spend txids are no longer reproducible across re-signs. That is the node's behaviour too.
- No wire, key or address change; existing vaults and keys are untouched (derivation is unchanged).

## 8. Effort estimate and dependencies

- ~0.5 day (text, comments, hedged signing with a deterministic test path). The devnet portability check is optional, ~0.5 day.
- Depends on nothing.
