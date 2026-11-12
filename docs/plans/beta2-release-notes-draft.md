<!-- Copyright (c) 2026 The Ycash developers -->
# Beta2 release notes: draft for the Yellowback lead architect

Draft, 2026-11-11. Not release notes yet: it collects what the beta2 release notes of each component
will say, from what is merged on `upgrade/vault` today. Each statement that depends on a pull request
not merged on 2026-11-11 is marked **[pending: …]**; flip or drop it when the PR merges or is dropped.
The final text goes into each component's own notes (ycash6
`doc/release-notes/release-notes-6.22.0-beta2.md`, which today carries only the beta1 rebuild fixes,
and the kogany and yew release notes), in their style.

Scope: ycashd 6.22.0-beta2 (ycash6, the release line), ycashd on Ycash 4.5.0 (ycash-dd, the reference
line), kogany 1.8.0-ycash beta2 with `yewd`, and the clients. Plan:
`docs/plans/yellowback-address-interop-plan.md` (decisions D-1 to D-9). The vault upgrade and
Ycash Yellowback (YED) remain proposed, unaudited, with no activation height on mainnet.

## 1. User-visible changes

### Both C++ node lines (ycash6 and ycash-dd)

Merged: ycash-dd #162, #163, #164, #165; ycash6 #92, #96, #98, #99, #100.

- **Send YEC between every address type** (D-2). `z_sendmany` takes an ECC, Sapling or post-quantum
  from address and any mix of ECC, Sapling and post-quantum recipients. A post-quantum source spends
  its own coins; its change returns to the same address (D-4); its fee is priced on its size (about
  27,000 zat for one SLH-DSA input, 5,500 for one FN-DSA-512 input), and an explicit fee below that
  is refused. `ANY_TADDR` still selects ECC coins only. `sendtoaddress` and `sendmany` are unchanged.
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
  regtest; 53 characters as before; the old form is no longer produced or accepted.
  **[pending: ycash-dd #166, ycash6 #95]**
- **Has-held-YED guard**: a wallet that has ever held YED refuses to load on a node where Yellowback
  is not live, unless started with `-yellowback=0` (which warns, in `getinfo` errors, and sets
  `getwalletinfo.yed_unlocked`); new field `getwalletinfo.yed_held`.
  **[pending: ycash-dd #170, ycash6 #97]**
- **ycash6 seed restore finds transparent coins**: a lookahead of `-keypool`+1 keys per legacy HD
  chain, mark-used on scan and a re-scan until no new key is found; only key IDs are written to the
  wallet, never an extended public key; `getwalletinfo` gains `lookahead_incomplete` and
  `restore_in_progress`. **[pending: ycash6 `up/b2-seed-restore` and its ycash-dd test companion,
  not pushed]**
- **Ceremony seed**. **[pending: ycash-dd #169, ycash6 #93; describe from their PR bodies]**

### kogany

Merged: kogany #11, #17, #18; zakura-common-ycash #7.

- The P2P user agent carries the kogany release tag.
- Tests: transactions with Sapling spends and outputs beside post-quantum and vault scripts,
  recorded on a C++ line and replayed, are accepted the same way. No consensus change.
- RPC contract version 9 and the D-9 address forms. **[pending: kogany `kc/b2-pq-prefix`, after
  ycash6 #95]**

### yew: `yewd` and the YEW app and web wallet

**[pending: everything in this section; yew `up/b2-pq-prefix`, not pushed; merge gate: a run against
a real ycashd and lightwalletd-dd]**

- `yewd`: `z_sendmany` between every address type, `vault_lock "from"`, read-only `z_gettotalbalance`
  and `listaddresses` (K-25 amended for beta2), the D-9 prefixes and rpcversion 9.
- App: balances per type, send between every type, mint funded from ECC, post-quantum or the private
  balance; fee bounds with a second confirmation for an unusual fee; a local provenance check of each
  plain-YEC input; the has-held-YED guard at send time.
- Web wallet: the same, except the three shapes listed under known limitations.

### Clients

**[pending: the D-9 client ports, local commits, merged after the node pair publishes rpcversion 9]**
lightwalletd-dd, chain-viz, x402-ycash, hawkeye and yecwallet-dd move to RPC contract version 9 and
the D-9 address forms; ycash-infra's `yindex` needs the same port (not assigned yet).

## 2. Defects fixed that were present in beta1

- **A refused post-quantum send could be paid twice.** A post-quantum send whose fee was above the
  mempool's cap was written to the wallet, refused by the mempool, and re-broadcast at restart after
  the user had sent again. Reproduced on ycash-dd; the same experiment did not reproduce on 6.22.0-beta1
  (the fee was refused before building), and the protections were ported to both lines: the fee cap
  is checked before signing and again under the node's locks, and a refused send is erased from the
  wallet. Merged (ycash-dd #163, ycash6 #99).
- **Node crash after an erased send.** Erasing a wallet transaction left its entries in the spend
  index; a later send of the same coins created an empty wallet transaction, and the next re-broadcast
  stopped the node (`Assertion failed: (pwallet)`). Present in beta1 through the Yellowback orphan
  removal. One erase function now clears every index on both lines. Merged (ycash-dd #163, ycash6 #99).
- **An interrupted seed restore silently skipped history.** The "scan from genesis" of a restore was
  kept in memory only; after a stop during the restore the node resumed near the tip. Now recorded in
  the wallet until a complete scan. **[pending: ycash6 `up/b2-seed-restore`]**
- **Seed restore missed transparent coins on ycash6.** Every coin paid to a `getnewaddress` address
  past the first was missed (a test restored 110 of 230 outputs). **[pending: ycash6
  `up/b2-seed-restore`]**
- **`getunconfirmedbalance` could not be called on ycash6** (no argument-table row). Fixed in ycash6
  #91, already in this release's base.

## 3. What an operator must do on upgrade

- **RPC contract version 9.** `yed_getinfo.params.pqAddressVersion` and `.params.pq.plainAddressVersion`
  become objects keyed by scheme number. Every client must be at version 9; lightwalletd-dd and yew
  check the version exactly. **[pending: D-9, ycash-dd #166, ycash6 #95]**
- **Address book rewrite.** On first load, a wallet written before D-9 rewrites its post-quantum
  address-book records under the new address form, once. Back up `wallet.dat` first; an older binary
  does not read the new form. **[pending: D-9]**
- **`-yellowback=0` now has the has-held-YED guard.** A wallet that has held YED refuses to load where
  Yellowback is not live; `-yellowback=0` overrides it with a warning, and with it the wallet will
  spend a YED-carrying coin as plain YEC (its YED burns). Do not leave `-yellowback=0` in a
  configuration file. **[pending: ycash-dd #170, ycash6 #97]**
- **Scripts that read `z_getbalance` for foreign addresses** must expect error -5 instead of 0.
- **Scripts that call `getnewaddress` with a non-empty first string** get a different error code and
  message.

## 4. Known limitations

- **ycash-dd: a seed-only restore recovers no transparent coins.** Its transparent keys are random,
  not derived from the seed (`-hdseedfile` says so); back up `wallet.dat`. ycash6 derives them from the
  seed. Its post-quantum rescan is forward-only with a lookahead of 20.
- **The has-held-YED marker does not cover** a seed restore, rescan or key import done where
  Yellowback is not live, nor a wallet last used by a release before the marker. **[pending: ycash-dd
  #170, ycash6 #97]**
- **The browser wallet cannot build** post-quantum → Sapling, private → post-quantum, or a mint funded
  from the private balance: the hybrid builder is not compiled for the browser in beta2. The core
  refuses them with an explanation; the app builds all three. **[pending: yew; decision on beta2 or a
  later beta with the Yellowback lead architect]**
- **`yewd` does not serve `z_mergetoaddress`** (outside K-25; it answers only the post-quantum
  refusals).
- **ycash6 `getbalance` with `asOfHeight`** reads a cached credit that ignores the height and can
  differ from `getwalletinfo`; an inherited defect (ycash6 upstream report §3.11), documented.
- **Default vault funding can pick coinbase coins** where coinbase must be shielded (`vault_lock`
  without `"from"`); pre-existing, follow-up on both lines.
- **App fee bound**: the YEW app cannot verify the attested price and bounds post-quantum fees against
  a compiled floor of $0.01 per YEC; a hostile server can raise a fee up to that bound, and above the
  usual fee the app asks for a second confirmation. **[pending: yew]**
- **Wallet encryption** remains experimental on both C++ lines (`-experimentalfeatures
  -developerencryptwallet`); on ycash6 `getnewaddress` refuses while the wallet is locked.

## 5. Pending before the tag

| What | Where | State on 2026-11-11 |
|---|---|---|
| D-9 prefixes, rpcversion 9 | ycash-dd #166, ycash6 #95 | open |
| D-9 ports | kogany `kc/b2-pq-prefix`; lightwalletd-dd, chain-viz, x402-ycash, hawkeye, yecwallet-dd `up/b2-pq-prefix`; ycash-infra `yindex` | local commits; `yindex` not assigned |
| Has-held-YED guard | ycash-dd #170, ycash6 #97 | open, in CI |
| Ceremony seed | ycash-dd #169, ycash6 #93 | open, in CI |
| ycash6 seed-restore lookahead and interrupted-restore fix | ycash6 `up/b2-seed-restore` + ycash-dd companion | local, reviewed, not pushed |
| yewd, YEW app and web | yew `up/b2-pq-prefix` | local; real-node run outstanding |
| librustzcash6 client tests, SQLite upgrade | librustzcash6 `up/b2-client-tests`, #22 | local / open |
| Stale help: ycash6 `getnewaddress` says "the z_* operations never pay or spend it" | ycash6 `src/wallet/rpcwallet.cpp` (merged text) | not fixed; found while writing these notes |
| Beta2 RPC snapshot for rpc.ycash.team (turns on the "Moving YEC" page) | workspace `rpc-docs/versions/v6.22.0-beta2` | after the tag |
| Release train file | workspace `releases/v6.22.0-beta2.yaml` | not written |
