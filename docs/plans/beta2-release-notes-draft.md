<!-- Copyright (c) 2026 The Ycash developers -->
# Beta2 release notes: draft for the Yellowback lead architect

Draft, 2026-11-11; corrected 2026-11-12 (D-9, the has-held-YED guard and the ceremony seed merged; the
statements the RELNOTES lane found false fixed). Not release notes yet: it collects what the beta2
release notes of each component will say, from what is merged on `upgrade/vault`. Each statement that
depends on a pull request not merged on 2026-11-12 is marked **[pending: …]**; flip or drop it when the
PR merges or is dropped.

The final text goes into each component's own notes, in their style; the per-line drafts (in
`wt/handoff/relnotes/`, applied by the checklist there once the open PRs merge) land at:

| Line | Final location |
|---|---|
| ycash6 (ycashd 6.22.0-beta2, the release line) | `ycash6/doc/release-notes/release-notes-6.22.0-beta2.md` (today it carries only the beta1 rebuild fixes) |
| ycash-dd (the reference line) | `ycash-dd/doc/release-notes.md` |
| kogany 1.8.0-ycash beta2 | `kogany/doc/release-notes/v1.8.0-ycash.beta2.md` (new) |
| yew (`yewd`, the app, the web wallet) | `yew/docs/release-notes-beta2.md` (new) |

Scope: ycashd 6.22.0-beta2 (ycash6, the release line), ycashd on Ycash 4.5.0 (ycash-dd, the reference
line), kogany 1.8.0-ycash beta2 with `yewd`, and the clients. Plan:
`docs/plans/yellowback-address-interop-plan.md` (decisions D-1 to D-9). The vault upgrade and
Ycash Yellowback (YED) remain proposed, unaudited, with no activation height on mainnet.

## 1. User-visible changes

### Both C++ node lines (ycash6 and ycash-dd)

Merged: ycash-dd #162, #163, #164, #165, #166, #170; ycash6 #92, #95, #96, #97, #98, #99, #100.

- **Send YEC between every address type** (D-2). `z_sendmany` takes an ECC, Sapling or post-quantum
  from address and any mix of ECC, Sapling and post-quantum recipients. A post-quantum source spends
  its own coins; its change returns to the same address (D-4); its fee is priced on its size (about
  27,000 zat for one SLH-DSA input, 5,500 for one FN-DSA-512 input), and an explicit fee below that
  is refused. `ANY_TADDR` still selects ECC coins only.
- **`sendtoaddress` and `sendmany`** (as merged): they choose among all the wallet's transparent coins,
  post-quantum ones included, priced by size, so the source cannot be named. **[pending: the wallet
  follow-ups pair, `up/b2-wallet-followups`, not pushed: both calls then select ECC coins only,
  `fundrawtransaction` adds no unnamed post-quantum coin, and a send only post-quantum coins could
  cover is refused with a message naming `z_sendmany`; replace this bullet with that text]**
- **`z_mergetoaddress` follows** (D-6): named post-quantum sources (at most 100 inputs per call) and a
  post-quantum destination. `z_shieldcoinbase` still refuses a post-quantum source (D-7).
- **Privacy policy on ycash6** (D-5): a post-quantum party is a transparent party. With the default
  `LegacyCompat` every direction is allowed; with a stricter policy, Sapling → post-quantum needs
  `AllowRevealedRecipients` and post-quantum → Sapling `AllowRevealedSenders` (or
  `AllowFullyTransparent` with change). ycash-dd has no policy argument.
- **Fund a vault from any address type** (D-3): `vault_lock` takes an optional `"from"`, an ECC,
  post-quantum or Sapling address of the wallet; change returns to it. Without `"from"`, funding is
  unchanged. `yed_mint`'s `from` is unchanged (ECC or Sapling).
- **Balances by address type**: `z_gettotalbalance` adds `transparent_ecc`, `transparent_pq` and
  `pq_by_scheme`; `getwalletinfo` adds `balance_ecc`, `balance_pq`, `unconfirmed_balance_ecc`,
  `unconfirmed_balance_pq` and `pq_by_scheme`. Existing fields keep their meaning.
- **`z_getbalance`** takes a post-quantum address of either scheme, and now **refuses** (code -5) a
  transparent or post-quantum address the wallet does not hold; a watch-only address still answers.
  On ycash-dd this changes inherited behaviour, which answered 0.
- **Listings name the scheme**: `listreceivedbyaddress` adds `pqscheme` / `pqschemename` to a
  post-quantum address; on ycash6 `listaddresses` has a `pq` list with the same fields.
- **`getnewaddress` takes the type first**: `getnewaddress pq`, `pqslh`, `p2pkh`. The older
  `getnewaddress "" pq` still works. Another first string is refused with `Accounts are unsupported;
  the first argument is the address type, …` (code `RPC_WALLET_ACCOUNTS_UNSUPPORTED`; ycash6 beta1
  said `dummy first argument must be excluded or set to "".` with `RPC_INVALID_PARAMETER`).
- **ycash6 help text**: the RPCs upstream marked deprecated (`getnewaddress`, `z_getnewaddress`,
  `z_gettotalbalance`, the legacy account calls, …) now say "Supported on Ycash" and why, instead of
  "DEPRECATED and will be removed". `-allowdeprecated=none` still turns them off.
- **YED is not spent as plain YEC by a send**: every path that selects coins itself (`z_sendmany`,
  `z_mergetoaddress`, `sendtoaddress`/`sendmany`, `vault_lock "from"`, the vault fee funding) leaves
  out a coin the Yellowback index knows as a YED token, vault or carrier, also when its coin lock was
  removed with `yed_unlockcoin`; while the index is unhealthy, a plain-YEC send from a post-quantum
  address is refused.
- **Scheme-visible post-quantum prefixes** (D-9): `sqf…` / `sqs…` (FN-DSA-512 / SLH-DSA) for YEC and
  `ybf…` / `ybs…` for YED on mainnet, `tqf`/`tqs`/`ytf`/`yts` on testnet, `rqf`/`rqs`/`yrf`/`yrs` on
  regtest; 53 characters as before; the old form is no longer produced or accepted, except when a
  wallet loads its own address book (rewritten under the new form) and by `importwallet` of an older
  key dump. RPC contract version 9. Merged (ycash-dd #166, ycash6 #95).
- **Has-held-YED guard**: a wallet that has ever held YED refuses to load on a node where Yellowback
  is not live, unless started with `-yellowback=0` (which warns, in `getinfo` errors, and sets
  `getwalletinfo.yed_unlocked`); new field `getwalletinfo.yed_held`. Merged (ycash-dd #170, ycash6
  #97).
- **ycash6 seed restore finds transparent coins**: a lookahead of `-keypool`+1 keys per legacy HD
  chain, mark-used on scan and a re-scan until no new key is found; only key IDs are written to the
  wallet, never an extended public key; `getwalletinfo` gains `lookahead_incomplete` and
  `restore_in_progress`. **[pending: ycash6 #102 and its ycash-dd test companion #172]**

The ceremony-seed pair (ycash-dd #169, ycash6 #93) is merged; it changes only how CI runs the testnet
ceremony rehearsal and is not a user-visible item.

### kogany

Merged: kogany #11, #17, #18, #19; zakura-common-ycash #7.

- The P2P user agent carries the kogany release tag.
- Tests: transactions with Sapling spends and outputs beside post-quantum and vault scripts,
  recorded on a C++ line and replayed, are accepted the same way. No consensus change.
- `getinfo` errors, the local peer port and the restore guide (#19).
- RPC contract version 9 and the D-9 address forms. **[pending: kogany #20, pinned to ycash6
  `f8beb78e1a`, the merge of #95]**

### yew: `yewd` and the YEW app and web wallet

**[pending: everything in this section; yew #27 (`up/b2-pq-prefix`), with `up/b2-yewd-ecc-only` and
`up/b2-real-run-fixes` stacked on it, not pushed; the real-node run (YEW-REAL) is done and its fixes
are in review]**

- `yewd`: `z_sendmany` between every address type, `vault_lock "from"`, read-only `z_gettotalbalance`
  and `listaddresses` (K-25 amended for beta2), the D-9 prefixes and rpcversion 9; `sendtoaddress`,
  `sendmany` and `fundrawtransaction` ECC-only with the C++ strings (`up/b2-yewd-ecc-only`); spending
  Sapling notes from before Canopy and the wallet's own change notes (`up/b2-real-run-fixes`).
- App: balances per type, send between every type, mint funded from ECC, post-quantum or the private
  balance; fee bounds with a second confirmation for an unusual fee; a local provenance check of each
  plain-YEC input; the has-held-YED guard at send time.
- Web wallet: the same, except the three shapes listed under known limitations.

### Clients

chain-viz (#9), x402-ycash (#19) and ycash-infra's `yindex` (#34) are on RPC contract version 9 and the
D-9 address forms (merged). **[pending: lightwalletd-dd #17, hawkeye #40, yecwallet-dd #18]**

## 2. Defects fixed that were present in beta1

- **Node crash after an erased send.** Erasing a wallet transaction left its entries in the spend
  index; a later send of the same coins created an empty wallet transaction, and the next re-broadcast
  stopped the node: on 6.22.0-beta1 (ycash6) through a null wallet pointer in
  `assert(pwallet->GetBroadcastTransactions())` (`src/wallet/wallet.cpp:5951` at the beta1 tag), on
  ycash-dd with `Assertion failed: (pwallet)`. Present in beta1 through the Yellowback orphan removal.
  One erase function now clears every index on both lines. Merged (ycash-dd #163, ycash6 #99).
- **An interrupted seed restore silently skipped history.** The "scan from genesis" of a restore was
  kept in memory only; after a stop during the restore the node resumed near the tip. Now recorded in
  the wallet until a complete scan. **[pending: ycash6 `up/b2-seed-restore`]**
- **Seed restore missed transparent coins on ycash6.** Every coin paid to a `getnewaddress` address
  past the first was missed (a test restored 110 of 230 outputs). **[pending: ycash6
  `up/b2-seed-restore`]**
- **`getunconfirmedbalance` could not be called on ycash6** (no argument-table row). Fixed in ycash6
  #91, already in this release's base.

Hardened, not a beta1 defect:

- **A refused post-quantum send cannot be paid twice.** On ycash-dd a post-quantum send whose fee was
  above the mempool's cap was written to the wallet, refused by the mempool, and re-broadcast at restart
  after the user had sent again. The same experiment did not reproduce on 6.22.0-beta1 (the fee was
  refused before building). The protections are on both lines: the fee cap is checked before signing
  and again under the node's locks, and a refused send is erased from the wallet. Merged (ycash-dd #163,
  ycash6 #99).

## 3. What an operator must do on upgrade

- **RPC contract version 9.** `yed_getinfo.params.pqAddressVersion` and `.params.pq.plainAddressVersion`
  become objects keyed by scheme number. Every client must be at version 9; lightwalletd-dd and yew
  check the version exactly. (Merged on both node lines; the client ports are listed above.)
- **Address book rewrite.** On first load, a wallet written before D-9 rewrites its post-quantum
  address-book records under the new address form, once. Back up `wallet.dat` first; an older binary
  does not read the new form.
- **`-yellowback=0` now has the has-held-YED guard.** A wallet that has held YED refuses to load where
  Yellowback is not live; `-yellowback=0` overrides it with a warning, and with it the wallet will
  spend a YED-carrying coin as plain YEC (its YED burns). Do not leave `-yellowback=0` in a
  configuration file.
- **Scripts that read `z_getbalance` for foreign addresses** on ycash-dd must expect error -5 instead
  of 0. ycash6 already refused an address the wallet does not hold with -5 (`From address does not
  belong to this node.`); only the message text changes there.
- **Scripts that call `getnewaddress` with a non-empty first string** get a different error code and
  message.
- **Testnet peers.** Seed hosts run for the three public testnets (`fastnet-seed.ycash.team`,
  `slownet-seed.ycash.team`, `legacy-seed.ycash.team`), but none is compiled into this build (the
  testnet DNS seed lists and `src/chainparamsseeds.h` are empty): connect with
  `-addnode=<seed name>`. Mainnet keeps its existing DNS seed. (The merged ycash6 beta2 notes' "No
  testnet seed nodes yet" is stale.)

## 4. Known limitations

- **ycash-dd: a seed-only restore recovers no transparent coins.** Its transparent keys are random,
  not derived from the seed (`-hdseedfile` says so); back up `wallet.dat`. ycash6 derives them from the
  seed. Its post-quantum rescan is forward-only with a lookahead of 20.
- **The has-held-YED marker does not cover** a seed restore, rescan or key import done where
  Yellowback is not live, nor a wallet last used by a release before the marker; such a wallet lists a
  YED output as ordinary spendable YEC. **[pending: the wallet follow-ups pair makes every
  coin-selecting send leave out an output whose own payload gives YED, mark or no mark; a raw
  transaction that names it still spends it. Keep this bullet, reworded, if the pair does not merge]**
- **The browser wallet cannot build** post-quantum → Sapling, private → post-quantum, or a mint funded
  from the private balance: the hybrid builder is not compiled for the browser in beta2. The core
  refuses them with an explanation; the app builds all three. **[pending: yew; decision on beta2 or a
  later beta with the Yellowback lead architect]**
- **`yewd` does not serve `z_mergetoaddress`** (outside K-25; it answers only the post-quantum
  refusals).
- **ycash6 `getbalance` with `asOfHeight`** reads a cached credit that ignores the height and can
  differ from `getwalletinfo`; an inherited defect (ycash6 upstream report §3.11), documented.
  **[pending: fixed by the wallet follow-ups pair (an as-of-height read bypasses the cache); drop when
  it merges]**
- **Default vault funding can pick coinbase coins** where coinbase must be shielded (`vault_lock`
  without `"from"`); pre-existing. **[pending: fixed by the wallet follow-ups pair; drop when it
  merges]**
- **App fee bound**: the YEW app cannot verify the attested price. A server's fee terms are refused
  above the rates of the node's dollar targets at a compiled floor of $0.01 per YEC, and no send pays
  more than the build's limit (about 3.6 YEC for an FN-DSA send, 10 YEC for an SLH-DSA send, 5.75 YEC
  for a YED transfer). Below that, a fee needs a separate confirmation when it is unusual against the
  wallet's reference price: the 30-day median of the servers' reports, one per day, moving at most ×4
  per day. A fee above twice the usual fee at the reference, or a server price below half of it, is
  unusual. While the reference is weak (fewer than three days of reports, or below $0.05 per YEC,
  first use included) every fee above 0.1 YEC is flagged. So without the separate confirmation a
  hostile server can take at most 0.1 YEC per send on a weak reference, and at an honest $0.30
  reference 0.24 YEC per FN-DSA send, 1.08 per SLH-DSA send and 0.38 per YED transfer (twice the honest
  fee). Residual risk: a server that is the wallet's only source of reports for more than half of the
  window sets the reference, by at most ×4 per day; the user can reset the reference. Figures from yew
  `docs/address-types.md` §4 item 6 and `core/src/build/terms.rs` (`guard_fee`). **[pending: yew]**
- **A post-quantum → Sapling send in YEW copies the Sapling spending key.** The send needs only the
  outgoing viewing key, but the builder copies the full spending key, and the copies are not zeroized;
  a memory disclosure during such a send would expose it. Accepted for beta2 by the Yellowback lead
  architect; the fix splits the builder's signing code and follows after beta2. **[pending: yew]**
- **Wallet encryption** remains experimental on both C++ lines (`-experimentalfeatures
  -developerencryptwallet`); on ycash6 `getnewaddress` refuses while the wallet is locked.

## 5. Pending before the tag

| What | Where | State on 2026-11-12 |
|---|---|---|
| D-9 prefixes, rpcversion 9 | ycash-dd #166, ycash6 #95 | merged |
| D-9 ports | chain-viz #9, x402-ycash #19, ycash-infra #34; kogany #20, lightwalletd-dd #17, hawkeye #40, yecwallet-dd #18 | first three merged; the rest open |
| Has-held-YED guard | ycash-dd #170, ycash6 #97 | merged |
| Ceremony seed | ycash-dd #169, ycash6 #93 | merged (CI only) |
| ycash6 seed-restore lookahead and interrupted-restore fix | ycash6 #102, ycash-dd #172 | open |
| Wallet follow-ups (ECC-only `sendtoaddress`/`sendmany`, payload-based YED refusal, `asOfHeight` cache, `walletconfirmbackup`, default vault funding) | `up/b2-wallet-followups` on both C++ lines | local, in review, not pushed |
| Release dry run | ycash6 #104, ycash-dd #174, kogany #21 | open |
| yewd, YEW app and web | yew #27, with `up/b2-yewd-ecc-only` and `up/b2-real-run-fixes` stacked | open / local; real-node run done, fixes in review |
| librustzcash6 client tests, SQLite upgrade | librustzcash6 #23, #24; x402-ycash #18 | merged; yew `up/b2-sqlite-041` follows #27 |
| Stale `getnewaddress` help on both C++ lines: ycash-dd says "z_sendmany, z_shieldcoinbase and z_mergetoaddress never do" pay or spend a post-quantum address, ycash6 says "the z_* operations never pay or spend it" (both false since ycash-dd #163 / ycash6 #99); the D-9 prefix wording in the same help became true with #166 / #95 | ycash-dd and ycash6 `src/wallet/rpcwallet.cpp`, `getnewaddress` help | fixed on `up/b2-wallet-followups` (not pushed) |
| Beta2 RPC snapshot for rpc.ycash.team (turns on the "Moving YEC" page) | workspace `rpc-docs/versions/v6.22.0-beta2` | after the tag |
| Release train file | workspace `releases/v6.22.0-beta2.yaml` | DRAFT (pins move before the tag) |
