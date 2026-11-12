# Address interoperability plan

Plan of record for the beta2 address work (Ycash 6.22 beta2, kogany 1.8.0-ycash beta2). Decisions
D-1 … D-9 are the Yellowback lead architect's, 2026-11-10; the order of work and the later
decisions noted in §4 are of 2026-11-11. "beta2 item N" refers
to the run's working list of beta2 fixes, kept outside the repository during the run; the items
this plan depends on are restated where they are used.

## 1. Goal

Two requirements, both mandatory for beta2 (the Yellowback lead architect, 2026-11-10):

1. **Send.** A user can move YEC between every address type in one transaction, and can fund a vault
   from any of them, on every wallet the project ships.
2. **See.** A user has an easy and accurate way to display the balance of every address type: a
   total split by type, a balance per address, and a list of the wallet's addresses of each type.
Every such transaction is accepted, relayed and mined by
every node implementation, and each direction is covered by a test that runs in CI.

Address types: **ECC** (transparent P2PKH, `s1…`/`sm…`), **Sapling** (`ys1…`/`ytestsapling…`),
**PQ** (post-quantum transparent, `sq…`/`tq…`/`rq…` with the scheme letter of D-9 after it, `TX_PQPKH`, in two schemes: SLH-DSA-SHA2-128s
and FN-DSA-512). Vault funding means the generic `vault_lock` and the Yellowback mint (`yed_mint`).

Wallets: `ycashd` on both C++ lines (ycash-dd v4.5.0, ycash6 6.22) and `yewd` (the wallet half of
the kogany product). Nodes: both C++ lines and kogany.

## 2. What exists today

Read from the code on `upgrade/vault`, 2026-11-10. Nothing below was run for this survey; "tested"
means a test exists in the tree.

| Direction | ycash-dd | ycash6 | yewd | kogany validates |
|---|---|---|---|---|
| ECC → PQ | yes, tested (`sendtoaddress`, `sendmany`, `z_sendmany`) | yes, tested (`sendtoaddress`, `sendmany`) | yes, tested in core | yes, tested |
| PQ → ECC | yes, tested (`sendtoaddress`, `sendmany`) | yes, tested | yes; no yewd test | yes, tested |
| Sapling → PQ | builder accepts a PQ recipient in `z_sendmany`; **no test with a Sapling source** | **refused** (`z_sendmany cannot pay a post-quantum address`) | **refused** (`zsend.rs:296`) | no rule against it; **no test** |
| PQ → Sapling | **refused** (PQ coins erased from `z_sendmany` inputs) | **refused** | **refused** (`zsend.rs:347`) | no rule against it; **no test** |
| Sapling → `yed_mint` vault | yes, tested (`yellowback_sapling.py`) | yes, tested | yes (`zfund.rs`); **no test** | no rule against it; **no test** |
| Sapling → `vault_lock` | **absent** (transparent coins only) | **absent** | **absent** | no rule against it; **no test** |
| PQ → `vault_lock` | **excluded** (P2PKH coins only, `src/rpc/vault.cpp:744`) | **excluded** (P2PKH coins only, `src/rpc/vault.cpp:761`) | **excluded** (ECC coins only, `send.rs:782`) | no rule against it; **no test** |
| ECC → `vault_lock` | yes, tested | yes, tested | yes, tested | yes, tested |
| Sapling ↔ ECC | yes, tested | yes, tested | yes, tested | yes, tested |
| Mine to a PQ address | refused at start-up | refused at start-up | n/a | n/a |

Facts behind the table:

- **Consensus does not stand in the way.** No rule on any line restricts shielded parts in a
  transaction that carries PQ or vault scripts (`ycash6/src/yellowback/state.cpp:1306`, "Shielded
  components are ignored (TX-0)"; `kogany/crates/kogany-vault/src/state/tx.rs:29`). Vault
  transactions are v4, so the ZIP-243 sighash that `OP_CHECKPQSIG` signs covers the Sapling parts.
- **The ycash6 gap is a recorded decision, not an accident.** Quantum spec A-15
  (`docs/plans/yellowback-quantum-spec.md`, item A-15): the 6.x `WalletTxBuilder` has no PQ recipient
  type, "leave it absent … record it as a 6-only limitation". This plan reverses A-15.
- **The Sapling-funded mint is the precedent.** `yed_mint` takes a `ys1…` funding address and spends
  its notes in the minting transaction; `yed_redeem` pays a Sapling address
  (`src/rpc/yellowbackwallet.cpp:878`, `:1014`; `src/yellowback/txbuilder.cpp`, `ParseAddressChoice`,
  `Context::SelectSapling`). The generic `vault_lock` never got the same treatment.
- **x402-ycash does not build any of the mixed directions.** It has ECC → PQ payments (built and
  tested for YED) and a Sapling-to-Sapling light client. It has no general signer for a YEC PQ
  input and no vault builder.
- **librustzcash6 has no PQ type** (no `TX_PQPKH`, no `OP_CHECKPQSIG`). yewd builds and signs the
  transparent and PQ parts itself and calls `sapling_crypto::builder` for the Sapling part
  (`yew/yewd/signer/src/sapling.rs:466`), so this plan needs no librustzcash6 change.
- **kogany has no test with both Sapling parts and a PQ or vault script**, in Rust or in the
  Python parity harness. Its vault sighash vectors were not checked for Sapling content.

### Live findings on testnet-yb-fast

Run of 2026-11-10 on the 6.22.0-beta1 build, heights 510,402–510,404, one wallet.
Step 1: `z_sendmany` Sapling → `smEv…` 3 YEC with `AllowRevealedRecipients` (`b266f593…73be`).
Step 2: `sendtoaddress` 1 YEC to the FN-DSA-512 address `tq3whEUz…` (`e0d38478…7e0c`) and 1 YEC to
the SLH-DSA address `tq3v3gYK…` (`25303cfc…3b27`). All three mined; both seeds followed.

| # | Finding | Kind | Where it goes |
|---|---|---|---|
| L-1 | Sapling → ECC and ECC → PQ (both schemes) work and confirm. `sendtoaddress` left the wallet's transparent coinbase alone, as the coinbase-must-be-shielded rule requires. | works | Matrix cells, as regression |
| L-2 | PQ coins are counted inside `transparent` in `z_gettotalbalance`, `getbalance` and `getwalletinfo`: 38.62494245 = 35.625 ECC coinbase + 0.99994245 ECC change + 2.0 PQ. Nothing says how much of it is post-quantum. | gap | W1.5 split; matrix balance assertions |
| L-3 | `z_getbalance <tq…>` fails with "Invalid from address, should be a taddr or zaddr." The message is wrong as well as the behaviour: a `tq…` address is a transparent address of this wallet. | defect | W1.5 |
| L-4 | `listaddresses` shows the ECC address and the two ECC change addresses, and neither PQ address. No call lists them; a user must keep the string. | gap | W1.5 |
| L-5 | The scheme is not visible in the address: both start `tq3`. Only `validateaddress` (`pqscheme` 2 / 1) or the script tail (`52c2` / `51c2`) tells them apart. | gap | Decision D-9 below |
| L-6 | With a payment unconfirmed, the views disagree: `z_gettotalbalance` said transparent 35.625 (default minconf 1) while `getbalance` and `getwalletinfo` said 38.62494245 and `unconfirmed_balance` said 0. A user sees 3 YEC vanish from one view for a block. | defect (inherited behaviour, made visible by PQ and change) | W1.5: one documented rule for unconfirmed own funds across the three calls |
| L-7 | The two PQ payments are the same size (255 bytes, one ECC input, two outputs) and paid different fees: 255 zatoshi to the FN-DSA address, 5,500 to the SLH-DSA address. Not explained yet; the second spent the first's unconfirmed change. | open | Read the fee path (`wallet.cpp` near 6975) before W1; the matrix asserts the fee of every cell |
| L-8 | `getreceivedbyaddress` on a PQ address works (1.0 each) and `listunspent` with the address works (one coin each, spendable). These are the only per-address views today. | works | Matrix cells |
| L-9 | Raw transaction decoding names the output type `pqpubkeyhash` and prints the `tq…` address. | works | W4.3 checks kogany prints the same |

Not run yet: spending from a PQ address (PQ → ECC), and anything with a vault.

## 3. Tier and the four-part check

The change is **wallet and RPC code only**. No consensus rule, opcode, template or primitive
changes; the answer to "which tier" is none.

> DigiByte has no shielded pool, so DigiDollar has no counterpart to these directions. Ycash's
> equivalent is the Sapling transaction builder in each wallet, which lacks a PQ recipient and a PQ
> input on the 6.x and yewd paths. The adaptation is to add both to the wallet builders, following
> the shape `yed_mint` already uses for Sapling funding.

One condition: this plan sends transaction shapes through consensus that no test has exercised. If
W4's tests find that the lines disagree on any of them, that is a shared defect and is handled
under the shared-defect rule (all lines in one change set, G-9 review), ahead of everything else
here.

## 4. Decisions

Decided by the Yellowback lead architect, 2026-11-10.

| # | Decision | Decided |
|---|---|---|
| D-1 | Quantum spec A-15 on ycash6 | **Reversed.** ycash6 gains PQ recipients and sources in its shielded send path, matching ycash-dd. |
| D-2 | Which RPC moves value between types | **`z_sendmany` is the any-to-any call**: source ECC, PQ or Sapling; recipients of any type, mixed. `sendtoaddress` / `sendmany` stay transparent-source and keep paying ECC and PQ. |
| D-3 | `vault_lock` funding | **An optional funding address (`"from"`)**, ECC, PQ or Sapling, parsed the way `yed_mint` parses its funding address. Default unchanged: the wallet's transparent coins. |
| D-4 | Change for a PQ source | **Back to the source PQ address** (same scheme, no new key to back up); a fresh address only on request. Sapling-source change stays a Sapling note. |
| D-5 | Privacy policy on 6.x | **Same as ECC**: Sapling → PQ needs `AllowRevealedRecipients`; PQ → Sapling needs `AllowRevealedSenders`. ycash-dd has no policy argument and is unchanged. |
| D-6 | `z_mergetoaddress` and `z_shieldcoinbase` | **`z_mergetoaddress` follows `z_sendmany`** (PQ source and destination). `z_shieldcoinbase` from PQ waits for D-7. |
| D-7 | Mining to a PQ address | **Separate, later.** Not in this plan; decided after the address moves are done and tested. |
| D-8 | YEW app and web screens | **Same release** as the core and yewd change (W3). |
| D-9 | Make the scheme visible in the address prefix (L-5) | **Decided: yes.** YEC: `sqf…` FN-DSA-512 / `sqs…` SLH-DSA (test `tqf…` / `tqs…`, regtest `rqf…` / `rqs…`). YED: `ybf…` / `ybs…` on mainnet (Yellowback, Falcon / SLH); test `ytf…` / `yts…`, regtest `yrf…` / `yrs…`. The ECC YED address is unchanged: on mainnet it already renders `yb…` (35 characters, version `1F DD`, D-Q-21), so mainnet YED stays one `yb` family; it can never begin `ybf` or `ybs`. The existing 2 version bytes + scheme byte are read as one 3-byte version per scheme; length stays 53. Not a consensus change; every component changes together (W6). The twelve 3-byte versions are proved in quantum spec §4.1 (`scripts/pq_addr_prefix.py`). Two fields of `yed_getinfo` (`pqAddressVersion`, `pq.plainAddressVersion`) become objects keyed by scheme, so the RPC contract version goes from 8 to 9 (`docs/plans/yellowback-pq-prefix-rpc-delta.md`) and every client moves to 9. |

## 5. Work packages

### W1. ycash6 (release line)

1. PQ recipient in `z_sendmany` and `z_mergetoaddress`: remove `RefusePQRecipient`
   (`src/wallet/rpcwallet.cpp:5511`, `:6128`); carry a PQ destination through `WalletTxBuilder` as a
   transparent output (`TransactionBuilder::AddTransparentOutput` already takes a script,
   `src/transaction_builder.h`); apply `EnsurePQRecipientPayable`.
2. PQ source: remove `RefusePQSource` for `z_sendmany` / `z_mergetoaddress`; select the address's
   PQ coins; sign PQ inputs under the next block's vault flags, reusing the signing path
   `sendtoaddress` uses (`src/wallet/wallet.cpp:6931`); fee by size as policy requires.
3. Change and wallet accounting: D-4; make `IsChange` and the transaction listings see PQ change
   (A-15 notes that the 6.x `IsChange` does not).
4. `vault_lock` `"from"` (D-3), sharing `ParseAddressChoice` / `SelectSapling` with the mint builder.
5. Balances and listings (beta2 item 15): `z_gettotalbalance` and `getwalletinfo` split `transparent`
   into ECC and post-quantum (existing fields kept); `z_getbalance` takes a PQ address, and refuses a
   transparent or post-quantum address the wallet does not hold on both lines (decided 2026-11-11;
   watch-only still answers); `listaddresses` lists PQ addresses with their scheme. Same on ycash-dd (W2) and yewd (W3).
6. Argument-table rows for any changed arity (`src/rpc/common.h`). The unit suite that compares
   every registered RPC with the table in both directions (`rpc_table_tests`, ycash6 #91) must pass:
   a method without a row cannot be called at all on 6.x.

### W2. ycash-dd (v4.5.0 line)

1. PQ source in `z_sendmany` and `z_mergetoaddress`: stop erasing PQ coins
   (`src/wallet/asyncrpcoperation_sendmany.cpp:871`), sign them as in W1.2.
2. `vault_lock` `"from"`, as W1.4.
3. Same change rule (D-4).

W1 and W2 land together: same RPC shapes, same error strings, same test script.

### W3. yew: yewd and the YEW core

1. `z_sendmany`: lift `refuse_pq` for recipient and source (`yewd/wallet/src/zsend.rs:296`, `:347`).
2. Planner: accept a PQ recipient on a shielded spend (`core/src/shielded.rs:938`); build PQ →
   Sapling as a shield with PQ inputs (`core/src/build/yec_move.rs`).
3. `vault_lock`: fund from PQ coins and from Sapling (`yewd/wallet/src/send.rs:782`; the Sapling part
   as `zfund.rs` does for the mint).
4. Gate (`core/src/gate.rs`): the `Shielded` path forbids `OP_RETURN` outputs and any transparent
   input, and `Shield` allows Sapling outputs only. Extend the paths for exactly the new shapes
   (Sapling spends with a vault-lock output; PQ inputs with Sapling outputs) and nothing wider.
5. `getnewaddress` takes the address type as its first argument (`getnewaddress pq`, `pqslh`,
   `p2pkh`), and `getnewaddress "" <type>` keeps working, as on the node lines.
6. Fix the stale revision in the comment at `core/Cargo.toml:47`.
7. App and web screens (D-8, same release): the send screen offers every source and destination
   type of the matrix, with the revealed-party notice beside a Sapling ↔ PQ move; the vault screen
   offers the funding address. The shells call the core builders of items 2–4 and add no
   transaction logic of their own.

### W4. kogany and zakura-common-ycash

No wallet change. Tests only, unless they find a defect:

1. Consensus, mempool and mining tests for each mixed shape: Sapling spends with a PQ output; a PQ
   input (each scheme) with a Sapling output; Sapling spends with a vault-lock output.
2. Shared sighash vectors that contain Sapling parts and a PQ input, generated on a C++ line and
   replayed in `zakura-chain/tests/vault_sighash.rs`.
3. Decoding and address-index coverage: `getrawtransaction`, `decoderawtransaction` and the
   `getaddress*` indexes show the PQ address of a mixed transaction.
4. Extend `qa/mempool_ycash_parity.py` with the mixed shapes, built by ycashd.

### W5. Documentation

1. RPC docs site: add a "send between address types" matrix to the addresses page, with the call
   for each cell; every command is run against the release binary (beta2 item 13c).
2. `doc/yellowback-rpc.md`, `doc/vault-rpc.md` and the RPC contract hashes on both C++ lines.
3. Amend quantum spec A-15; add the row to `docs/mapping.md`.

### W6. Scheme-visible address prefixes (D-9)

1. Done: the twelve 3-byte versions are proved by interval arithmetic and by sampling, and
   recorded in quantum spec §4.1 and `docs/mapping.md`.
2. Encode and decode by 3-byte version on both C++ lines (`src/key_io.cpp`, `PlainPQAddressVersion`;
   `yellowback/address.{h,cpp}` for the YED form), kogany (`zakura-chain`, `Address::PayToPqKeyHash`),
   yewd and the YEW core, lightwalletd (address regex), x402-ycash, chain-viz, hawkeye.
3. The old `sq…`/`tq…`/`rq…` and `yb…`/`yt…`/`yr…` 53-character forms stop being produced. Decide in the
   PR whether they are still accepted on input for one release (testnet addresses exist since
   2026-11-10; no mainnet address can exist before the Vault height is set).
4. Test vectors shared by every component: for each network, coin and scheme, a key hash and its
   address; a decode of the old form; the matrix test asserts the prefix of every address it creates.
5. Wallet listings and the YEW screens show the scheme name beside each PQ address (with W1.5).

### Not in scope

x402-ycash beyond the prefix change of W6 (it pays, it does not move a user's funds between types;
its missing general PQ-input signer is noted for its own plan), mining to PQ and `z_shieldcoinbase` from PQ (D-7). Handled in beta2 but outside this plan: the seed-restore
defect (post-quantum keys not returned to the address book), the older wallet defects found in review
(`sendtoaddress` signing under the node's locks, the `vault_lock` default path, `yed_mint` note
locking), and the dependency-advisory work.

## 6. Test plan

**One matrix script, run everywhere.** `wallet_address_matrix.py`, identical on ycash-dd and ycash6,
and run again with yewd as the wallet and with kogany as the node.

Sources: ECC, Sapling, PQ (FN-DSA-512), PQ (SLH-DSA). Destinations: ECC, Sapling, PQ (each scheme),
`vault_lock`, `yed_mint`. For every cell:

1. build and send with the documented call;
2. the transaction is accepted to the mempool of a ycash-dd node, a ycash6 node and a kogany node;
3. it is mined, once by a C++ node and once by kogany, and all three stay on one tip;
4. balances and transaction listings are right on the sending and the receiving wallet;
5. the received output is spent again (proves it is spendable, not only receivable);
6. one reorg across the transaction, then steps 4 and 5 again.

Negative cases: before the Vault height; a Falcon address before the Falcon height; dust priced on
the real PQ spend size; a coinbase source where coinbase must be shielded; the 6.x privacy policy
missing (D-5); a locked wallet; a multi-recipient send mixing all three types.

**Node profiles.** The 6.22 node has no separate "quantum index": a PQ address is indexed by the
ordinary address index when that is on. Every test names the profile it runs under, and the matrix
runs under each profile marked "matrix".

| Profile | Flags | What it adds | Runs |
|---|---|---|---|
| P0 default | none | Wallet views only. `getrawtransaction` finds only mempool transactions and ones with an unspent transparent output; `getaddress*` and `getspentinfo` are disabled. This is what a new user, the testnet seeds (`insight: false`) and the fast-testnet miner run. | matrix (all sends, all wallet balance and listing calls: nothing a user needs for sending or balances may depend on an index) |
| P1 txindex | `-txindex` | `getrawtransaction` for any transaction, including spent ones. | matrix step 4 re-checked through `getrawtransaction` for every transaction, old and spent |
| P2 insight | `-experimentalfeatures -insightexplorer` (with `-txindex`) | Address, spent and timestamp indexes: `getaddressbalance` / `utxos` / `txids` / `deltas` / `mempool`, `getspentinfo`, `getblockdeltas`. | matrix, plus: the address index agrees with the wallet for every address type and scheme, in the mempool and after confirmation and after the reorg; `wallet_pq_address.py`, `addressindex.py`, `spentindex.py` |
| P3 lightwalletd | `-experimentalfeatures -lightwalletd` (with `-txindex`) | The address index as lightwalletd-dd and YEW use it. | The yewd and YEW cells of the matrix; `yellowback_lightwalletd.py`; ycash-infra's `yindex` parity script |
| P4 module live | an attestor set compiled in or, on regtest, `-yellowbackattestorset=<setid>` | The Yellowback index and the `yed_*` RPCs (absent otherwise: "Method not found" on the fast-testnet node today). `-reindex-yellowback` rebuilds it. | The `yed_mint` cells (Sapling-funded mint), `yed_verifyindex` after the matrix and after the reorg |

Each profile is also run once from a restart with `-reindex`, to prove the indexes rebuild to the same
answers. kogany has its own always-on indexes; W4.3 checks its `getaddress*` and decode answers
against a P2 C++ node for the same chain.

**Cross-implementation.** A transaction built by ycashd validated by kogany, and one built by yewd
validated by both C++ lines, for every mixed shape. The shared sighash vectors of W4.2.

**Live.** On testnet-yb-fast after the release: the matrix by hand, small amounts, recorded in the
testnet log, as the first-hour walkthrough of beta2 item 13d.

## 7. Order of work

| Step | What | Gate to pass |
|---|---|---|
| 0 | D-1 … D-9 answered | Done 2026-11-10 (§4) |
| 1 | W4 tests, using ycash-dd's existing Sapling → PQ builder and hand-built transactions for the rest | All lines agree on every mixed shape. A disagreement stops the plan and becomes a shared defect |
| 2 | **ycash-dd, the reference** (W2, with the balance views and W6 encoding): every new behaviour is built, specified and tested here first; the matrix script is written here | Whole matrix green on ycash-dd under profiles P0 and P2 |
| 3 | **ycash6, the primary C++ node** (W1): port step 2 and close the 6.x-only gaps (A-15) | The same matrix script green on ycash6; both lines give identical answers and error strings |
| 4 | **kogany and yew, the Rust line** (W3, W4.3, W6): yewd, the YEW core, the app and web screens; kogany decoding, indexes and prefixes | Whole matrix green with yewd as the wallet and kogany as the node |
| 5 | W5 and the fastnet walkthrough | Docs commands run; walkthrough recorded |

The order follows the project's pattern (the Yellowback lead architect, 2026-11-11): ycash-dd is the
reference, ycash6 the primary C++ node, kogany with yew the Rust node; all three end with the same
functionality.

Step 1 comes first on purpose: it is cheap, it needs no new wallet code, and it tells us whether the
"consensus already allows it" reading holds before anyone builds on it.

Review: wallet signing changes get one reviewer independent of the author on each line. Nothing here
touches the consensus paths, so G-9 applies only if step 1 finds a defect.

## 8. Risks

- **Untested consensus shapes.** The largest risk, addressed by step 1.
- **Size and fees.** An SLH-DSA spend is about 8 KB and Sapling proofs add more; a multi-input
  PQ → Sapling transaction can approach policy limits (9,000-byte PQ scriptSig, sigop cost per
  `OP_CHECKPQSIG`). The matrix includes a many-input case.
- **Proving time with locks held.** The mint builder proves with no wallet lock held and re-locks to
  sign (`FinishSapling`); the new paths must do the same.
- **Change accounting on 6.x.** `IsChange` does not see PQ change today; a wrong answer shows up as
  wrong balances and listings, which step 4 of the matrix checks.
- **Privacy expectations.** A PQ address is transparent. Sapling → PQ reveals the amount and the
  recipient, as Sapling → ECC does. The docs matrix says so beside each cell.
- **Line drift.** The reason this plan exists. The matrix script is one file shared by both C++ lines
  and run in both CIs, so a direction cannot be dropped on one line again without a red test.

## 9. Done means

Every cell of §2 reads "yes, tested" for ycash-dd, ycash6, yewd and kogany; the matrix runs in the CI
of ycash-dd, ycash6, yew and kogany; the sighash vectors with Sapling parts and a post-quantum input
are shared by the C++ lines and kogany (W4.2); every component reads and writes post-quantum
addresses by the 3-byte versions of D-9 from the one shared vectors file, at RPC contract version 9
(W6); the YEW app and web screens offer every move; the docs site shows the matrix with commands
that were run against the release; the fastnet walkthrough is recorded.
