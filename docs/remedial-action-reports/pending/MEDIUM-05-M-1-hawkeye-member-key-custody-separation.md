# MEDIUM — 05/M-1 — The member key is plaintext in the node wallet and is also the bond and gas key: say so, separate the gas key, and move Ycash signing off the wallet

Repos / branches to change: `hawkeye` (`fix/05-M-1-key-custody` off `upgrade/vault`); docs in `hawkeye/README.md`, `hawkeye/docs/hawkeye-bridge-plan.md` §3.5; no node change (two optional §10 change requests, §4.5). · Audit source: `05-bridge-hawkeye-wyec.md` §M-1 (`:139-161`); `verification/05-verification.md` §M-1 (`:98-105`); `00-consolidated.md` row 05/M-1 and recommendation R7. · Status: pending

## 1. Finding

Plan §3.5 (`hawkeye/docs/hawkeye-bridge-plan.md:370-383`) describes the member key as held "in an encrypted keystore … imported into the node wallet once at enrolment". `hawkeye enroll` (`crates/hawkeye/src/cli.rs:51-58`) does exactly that: `importprivkey(wif(key), "hawkeye", false)`. On Ycash 4.5 / 6.x `encryptwallet` throws "wallet encryption is disabled" unless the experimental `-developerencryptwallet` flag is set (`ycash-dd/src/wallet/rpcwallet.cpp:2173-2208`), so after enrolment the 32 secret bytes sit in plaintext in `wallet.dat`, readable by anyone with file access or with the RPC cookie (`dumpprivkey`). Every Ycash signature (`set_signunlock`, `set_signcancel`, `set_signact`, `set_heartbeat`) is made by that wallet (`SignSetInPlace` → `WalletPrivKey`, `ycash-dd/src/rpc/vault.cpp:1438-1527`); the keystore's scrypt password protects only the copy Hawkeye uses for EIP-712. The same key is the slashable bond key (bond script `P2SH(<locktime> CLTV DROP <memberKey> CHECKSIG)`, README `:54-57`, plan §2.4) and the Ethereum account that pays gas (`keys.rs:45-48`; `Ctx.foreign` "with the member key as sender", `engine/mod.rs:71`; `foreign::connect(s, &key)`).

One read of `wallet.dat` therefore yields the Ycash set signature (fraudulent intents, cancels, slash votes), the Ethereum guardian signature (fraudulent proposals, admin acts), the bond (spendable after the exit delay) and the gas balance. The YED attestor doc's "a stolen hot key can only grief" (`ycash-dd/doc/yellowback-attestor.md:349-351`) does not describe the bridge key, and `config.rs:667-686` refusing `secret_hex` on mainnet "in favour of the keystore" gives operators a false sense of what the keystore buys.

## 2. Root cause

- `crates/hawkeye/src/cli.rs:51-58` — `enroll` imports the secret with `importprivkey`.
- `crates/hawkeye/src/keys.rs:34-48` — `wif()` for the import, `eth_signer()` makes the member key the alloy transaction signer.
- `crates/hawkeye/src/foreign/ethereum.rs` / `foreign/mod.rs::connect` — the Ethereum adapter is built with `eth_signer(&key)` as the wallet, so the sender (gas payer) *is* the guardian.
- `crates/hawkeye/src/config.rs:667-686` — `KeysSection` has one key; no `[eth] sender` section.
- `ycash-dd/src/wallet/rpcwallet.cpp:2173-2208` — `encryptwallet` gated on `-developerencryptwallet` (same on `ycash6`); the node's sign-once guard (`vault.cpp:1463-1475`) lives in the wallet, which is why the plan put the key there.
- Consensus binds the bond to the member key at `SET_JOIN` (upgrade plan §3.2 / D-U4): separating bond and member keys is a node change, not a Hawkeye one.

## 3. Fix options considered

| Option | Verdict |
|---|---|
| **`-developerencryptwallet` + `encryptwallet`** on the attestor node, Hawkeye calling `walletpassphrase` before each signing RPC | Rejected as the mechanism. It is an experimental, unsupported flag on both lines (the help text says so); the sidecar would hold the wallet passphrase on the same host as the daemon, so a host compromise still yields the key; `walletpassphrase <timeout>` leaves the key decrypted in memory; and the Ycash team's risk posture (workspace prime directive) argues against relying on a feature they disabled. Allowed as an operator *choice* in the runbook (defence in depth on the file at rest), never required or assumed by Hawkeye. |
| **Document the reality, encrypted volume, dedicated user** | Necessary, not sufficient; done in §4.1 and the runbook (`MEDIUM-05-M-3`). |
| **Separate gas key** (`[eth] sender`) | Cheap, contained, no protocol impact (`WyecBridge.sol:40`: any account may submit). Chosen. |
| **Self-signed set signatures: Hawkeye signs Ycash set/act messages with the keystore key; the node wallet holds only fee coins** | The node's `SignSetInPlace` accepts pre-existing signatures in the scriptSig and only verifies they recover (`vault.cpp:1448-1461`); `hawkeye-core` already has `zip243` (`sighash.rs:94`, used for the bond withdrawal), `set_sig_msg`, `sign_compact` and `selector_script_sig` (`setsig.rs:52-60, 93`, `template.rs:461`). So an UNLOCK/CANCEL can be fully signed by Hawkeye and sent with `vault_send`, which signs only the wallet's fee inputs. The node's sign-once guard is bypassed, but Hawkeye's ledger record (`sign_once_ycash`) already writes before signing and is the guard for EIP-712 today; with `HIGH-05-H-1`'s burn dimension it is the stronger of the two. Heartbeats and acts (`set_heartbeat`, `set_signact`) sign with wallet keys too; the act message is `act_msg` (`setsig.rs:63-70`), so Hawkeye can produce the signature — **whether `set_signact`/`set_sendact` accept an externally placed member signature must be verified on regtest** (the RPC doc, `vault-rpc.md:228-250`, describes "this wallet's signatures" only). Chosen as the **medium-term** mode (`[keys] ycash_signing = "self"`), behind a regtest test on both lines; if the act path cannot be reproduced from the RPC surface, CR-N6 (§4.5). |
| **Remote signer (KMS/HSM) behind a `Signer` trait** | Plan §3.5's H8 option; the self-signing mode above is its prerequisite (once Hawkeye signs everything, the signing backend can move). Not in this report. |
| **Separate bond owner (`bondOwner`)** | Consensus change (QS-7b); recorded as CR-N7, not blocking. |

## 4. Recommended fix

### 4.1 Tell the truth (docs, 0.5 day; land first)

- `hawkeye/README.md` "Joining and leaving" gets a **Key custody** subsection: the member key is hot on both chains; the keystore is a transport format for the Ethereum copy; after `enroll` the secret is in `wallet.dat` in clear; what one copy yields (the list in §1); the mitigations below and the runbook's single-instance rule.
- `hawkeye-bridge-plan.md` §3.5: replace "holds the key in an encrypted keystore … imports it into the node wallet" with the same statement; add decision **HK-14** to §12: "The member key is hot in the node wallet until self-signing (§4.3) ships; the gas key is separate from the member key on mainnet."
- `config.rs:669-672` error text: `"mainnet refuses keys.secret_hex: use a keystore (note: the keystore protects the file at rest only; the node wallet holds the same key in clear after `hawkeye enroll` — see README 'Key custody')"`.
- `ycash-dd/doc/yellowback-attestor.md` and the `ycash6` copy: the "a stolen hot key can only grief" sentence is about the YED price attestor; add one line "(the bridge attestor's key is different: see hawkeye/README.md)". Both node lines, docs only.

### 4.2 Separate the gas key (`config.rs`, `keys.rs`, `foreign/mod.rs`, `foreign/ethereum.rs`, 1 day)

- `[eth]` gains `sender_keystore: Option<PathBuf>`, `sender_password_env: Option<String>` (and `sender_secret_hex` for devnets only, refused on mainnet like `keys.secret_hex`). `Settings.eth_sender: Option<KeySource>`.
- `foreign::connect`: the alloy wallet is `eth_signer(&sender_key)` when configured, else the member key (devnet default); `Ctx.key` stays the member key and is used only for EIP-712 digests (`sign_digest`) and set-signature work.
- Mainnet rule (`Config::check`): `eth_sender` **required** and its address ≠ the member key's address (`"mainnet refuses the member key as the Ethereum sender: configure [eth] sender_keystore (a gas-only account)"`).
- `hawkeye status`: show `sender`, its ETH balance (`eth_getBalance`) and alarm `gas-low` below a configurable floor (`[eth] min_sender_balance_wei`, default 0.05 ETH on mainnet).
- Devnet scripts (`devnet/`): fund a sender account per attestor from anvil account 0 (one `anvil_setBalance` per attestor, as `tests/engine.rs:160-168` already does for guardians).

### 4.3 Self-signed Ycash signatures (`hawkeye-ycash`, `engine/burn.rs`, `watch.rs`, `roll.rs`, `slash.rs`, `mod.rs::heartbeat`, 3 days + regtest verification)

`[keys] ycash_signing = "wallet" | "self"` (default `wallet`; `self` recommended on mainnet once the act path is verified):

1. **Unlock/cancel** (`post_unlock`, `cancel`, `verify_and_sign_unlock`, `verify_and_sign_cancel`, rolls): build with `vault_buildunlock`/`vault_buildcancel` as now (fee inputs from the wallet, unsigned); compute the template input's sighash with `hawkeye_core::sighash::zip243(tx, idx, coin.script_pubkey, coin.value, SIGHASH_ALL, branch_id)` where `branch_id` is the next block's (`getblockchaininfo.upgrades` / `consensus.nextblock.branchid`, already parsed for the bond withdrawal) and the coin comes from `gettxout`; `msg = set_sig_msg(set_id, role, prevout, sighash)`; `sig = sign_compact(member_key, msg)`; `script_sig = selector_script_sig(&[existing…, sig], role)`; write it into the input; the sign-once closure returns `(signed_hex, sighash)` exactly as the node's reply did, so `sign_once_ycash`/`sign_once_unlock` are unchanged. Cross-check on regtest that `sighash` equals what `set_signunlock` reports for the same transaction (the mock's placeholder set-sig scheme is not usable here; this needs a real node of **each line**, rule 5).
2. **Heartbeat/acts**: `set_buildact heartbeat {setid, memberkey}` → unsigned act; sign `act_msg(payload, vin[0].prevout)` with the member key; place the signature where `set_signact` would (verify the act's signature carrier on regtest: `set_signact` on a wallet holding the key, then `decoderawtransaction` both; if the placement is in the payload's `OP_RETURN` or the input script, replicate; if it is not derivable, stop and file CR-N6); `set_sendact`.
3. **`enroll`** in `self` mode imports **nothing**; it only prints `key_info`. The fee key is whatever the wallet already has (`getnewaddress`); the runbook tells the operator to fund it.
4. Slash votes (`sign_act` in `slash.rs`) and the bond withdrawal (already self-signed) follow the same path.
5. The node's `set-sign-once` guard no longer applies; `HIGH-05-H-1`'s per-burn dimension and the existing per-prevout record are the guard, and the ledger backup rule in the runbook becomes the only equivocation protection — say so loudly in the README.

### 4.4 Change requests (plan §10; Hawkeye commits none)

| # | Repo | Change | Why | Blocking? |
|---|---|---|---|---|
| CR-N6 | ycash-dd, ycash6 | `set_signact` accepts an externally produced member signature (`{"sig": hex}` param) and `set_heartbeat` has a `--sign-only`/unsigned form, so an act can be signed outside the wallet | needed only if §4.3 step 2 cannot reproduce the act signature placement from the RPC surface | no (verify first) |
| CR-N7 | ycash-dd, ycash6 | QS-7b `bondOwner`: `SET_JOIN` names a separate bond key (`bondOwner`) so the hot member key cannot spend the bond after the exit delay | consensus change, review gate; the only way to make a stolen hot key unable to take the bond | no (owner decision; next upgrade round) |

## 5. Tests

- `config.rs` unit tests: mainnet without `sender_keystore` → refused; sender == member → refused; devnet defaults unchanged.
- `tests/engine.rs`: with a distinct sender, `propose_mint`/`challenge_mint` transactions are sent **from** the sender (assert `tx.from` on anvil) while the recovered EIP-712 signer is the guardian.
- `self` mode: `hawkeye-ycash` gets a feature-gated real-node test (`HAWKEYE_REGTEST_URL`) run against **both** `ycash-dd` and `ycash6` regtest: build → self-sign → `vault_send` accepted; the node's `set_signunlock` on the same tx reports the same `sighash`; a cancel; a heartbeat act; `set_equivocation` is **not** triggered by one self-signed unlock plus the node's idempotent re-sign of the identical transaction.
- Sign-once drill D-16 crash points still fire in `self` mode (record-then-crash before broadcast).

## 6. Acceptance criteria

1. README, plan §3.5/§12 and the config error text state that the member key is plaintext in `wallet.dat` in `wallet` mode and what that implies.
2. On mainnet `hawkeye run` refuses to start without a distinct Ethereum sender; Ethereum submissions are sent from it; `gas-low` fires below the floor.
3. In `self` mode `wallet.dat` never receives the member key (`dumpprivkey` of the member address fails), every bridge transaction still confirms on both node lines' regtest, and `sighash` parity with the node is proven by test.
4. `cargo test --locked` and the regtest suite pass on both lines.

## 7. Risks and side effects

- **Key rotation**: none forced. An operator moving from `wallet` to `self` mode should rotate (join with a fresh key, leave with the old: plan §2.4) because the old secret has been in `wallet.dat`; the runbook (`MEDIUM-05-M-3`) gives the order.
- **Bridge downtime**: a sender change is a config restart; `self` mode is a config restart plus a verified regtest run first.
- **Contract redeploy**: none.
- **Equivocation**: `self` mode removes the node's duplicate guard; the ledger's guard and backup discipline must be in place first — do not enable `self` before `HIGH-05-H-1` and `MEDIUM-05-M-3` have landed.
- Fee-input signing stays in the wallet (`vault_send`), so a wallet compromise still lets an attacker burn fee coins — acceptable; fee coins are small.

## 8. Effort estimate and dependencies

Docs 0.5 day; gas key 1 day; self-signing 3 days + 1 day of two-line regtest verification. **Total ≈ 5.5 days.** Depends on `HIGH-05-H-1` (ledger guard) before `self` mode is recommended; `MEDIUM-05-M-3` carries the operational text. `LOW-05-L-2` (file permissions for the keystore) complements this.
