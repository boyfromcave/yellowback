# Ycash Yellowback (YED) v1 — Hardening Plan: coin selection and coin locking

**Status:** DRAFT — revision 1 (2026-09-06). Companion to
[`yellowback-v1-development-plan.md`](yellowback-v1-development-plan.md) (the *development plan*
below); it does not change any decision recorded there. Rule identifiers from the development plan
(`B4`, `C3`, `C20`, `D3`, `D18`, `F3`) and the spec (`XFER-1..3`, `IN-1..3`) are used unchanged;
this document's own items are numbered **H1–H12**.

**Scope.** Two wallet-side features that decide whether an ordinary user can lose YED by accident:

1. **Coin selection** — which YED outputs a transfer or redemption spends, so that the change floor
   (`MIN_OUTPUT`, $1.00) is a rule the wallet works around rather than an error the user works around.
2. **Coin locking** — how YED outputs are kept out of every path that would spend them as plain YEC
   and thereby burn them (spec IN-1..3, development plan D18).

**Tier.** Everything here is **Tier 0**: `src/yellowback/`, `src/rpc/`, `src/wallet/rpcwallet.cpp`,
`src/init.cpp` in `ycash-dd`, and `yecwallet-dd`. **No consensus code, no overlay rule, no payload
byte and no parameter changes.** XFER-1..3 stay exactly as written; `MIN_OUTPUT` stays $1.00. A
reader who wants the reasoning for keeping the floor and for keeping cents as the unit will find it
in §1.

**Pins.** As the development plan: `ref/digibyte` `v9.26.5` (`05b50e229d`), `ref/ycash` `v4.5.0`
(`624c12814`), `ref/yecwallet` `v4.5.0` (`1eb277d`). Line cites into `ycash-dd` and `yecwallet-dd`
are against the `feature/digidollar` branches as of 2026-09-06 and will drift; cites into `ref/`
will not.

---

## 1. The problem in one page

**What the rules say.** Every YED output a transaction creates — a payment *and* the sender's own
change — must carry between `MIN_OUTPUT` ($1.00) and `MAX_OUTPUT` ($100,000) (spec §3.1,
`docs/spec/yellowback-adaptation-spec.md:41`; XFER-1, `:360-361`). Amounts are integer cents; there
is no whole-dollar restriction on what a user can *send*. The rule bites in exactly one case: the
YED inputs the wallet chose exceed the amount by less than $1.00. That remainder cannot be a change
output, and XFER-2 says the unassigned difference is **burned**.

**What the code does today.** `SelectYed` picks inputs smallest-first until they cover the amount
and refuses if the change lands in `(0, MIN_OUTPUT)`
(`ycash-dd/src/yellowback/txbuilder.cpp:213-233`, rule C20, development plan `:134`). The message
names the two escapes — send everything selected, or at most `sum − MIN_OUTPUT`. The GUI shows
that message verbatim (`yecwallet-dd/src/yellowbacktab.cpp:381-390`). This is DigiByte's policy too
(`ref/digibyte/src/wallet/digidollarwallet.cpp:112-129`, `DDChangeIsStandard`): refuse, and let the
user change the number. **Nothing is ever burned by the refusal**; the shortcoming is UX, not
safety.

**Why the floor stays.** Each YED output carries `TOKEN_VALUE` (10,000 zat) and a permanent row in
the token index; without a floor anyone could spray one-cent outputs at a cost of nothing. It is the
YED dust rule and it is consensus for the overlay. The unit stays cents for the reasons recorded in
the 2026-09-06 discussion: a pegged unit does not appreciate, nothing in the protocol generates
fractional cents, `u32` amount fields fit only in cents (spec §3.3), and every formula is transcribed
from DigiByte in cents.

**Where YED can actually be lost.** Not in the refusal. It is lost when a YED output is spent
*without* a payload that reassigns it — as plain YEC. §3 inventories every such path; two of them
are open today (H5, H6) and one is a documentation gap that can only be closed by documentation (H9).

**Four-part check** (AGENTS.md rule 4):

> DigiByte selects DD inputs with a greedy accumulator over wallet-provided UTXOs and refuses
> sub-minimum change (`digidollarwallet.cpp:112-129`; `src/digidollar/txbuilder.cpp:79-125`), and
> **persists** locks on collateral outpoints through `WalletBatch` so the regular coin selector
> never touches them (`digidollarwallet.cpp:311-321`). The mechanism is Bitcoin Core v26's
> per-output `Coin` model, its `LockCoin(outpoint, persist=true)` and its in-wallet DD models.
> Ycash 4.5's equivalent is `CWallet::LockCoin` (`ref/ycash/src/wallet/wallet.h:1369`), which is
> **in-memory only** (`setLockedCoins`, `wallet.h:1327`) and can be cleared wholesale by
> `lockunspent true` (`ref/ycash/src/wallet/rpcwallet.cpp:2237-2241`); the DD wallet models do not
> exist and balances come from the rebuildable index. So the adaptation is: keep the index as the
> source of truth and **re-derive** locks from it (already the design, B4 stage iii), make the
> Yellowback locks unremovable by the generic RPC (H5), and replace the greedy accumulator with a
> floor-aware selector plus a dry-run RPC so the GUI can steer the user before the refusal (H1–H3).

---

## 2. Decisions

| # | Decision | Kind | Where |
|---|---|---|---|
| H1 | Replace smallest-first accumulation with the **floor-aware selector** of §4.1 for `yed_send`, `yed_sendmany` and `yed_redeem`. Exact match first, then a single input with valid change, then greedy with extension, then a bounded search. Deterministic; unit-tested against a table of adversarial coin sets. | UX | §4.1 |
| H2 | **TRANSFER never burns.** If no selection yields change of 0 or ≥ `MIN_OUTPUT`, refuse as today (C20) — but with a structured message carrying the nearest workable amounts below and above (§4.3). | safety | §4.3 |
| H3 | New RPC **`yed_estimatesend`** (dry run, no signing, no locking): given recipients and amounts, returns the selection, the change, and — when the amount is unworkable — the alternatives. The GUI calls it while the user types and never lets an unworkable amount reach the Send button. Mirrors `yed_estimatecollateral` for Mint. | UX | §4.4, §6 |
| H4 | **REDEEM may burn a sub-dollar remainder.** A redemption is a burn by definition; when the only selections leave change in `(0, MIN_OUTPUT)`, the builder burns the remainder (bounded by $0.99), reports it as `extraBurnCents`, and the wizard shows it on the review step. Selections with valid change are still preferred. | UX | §4.2 |
| H5 | **Yellowback locks are protected.** `lockunspent` refuses to unlock an outpoint the Yellowback wallet holds, and `lockunspent true` (unlock-all) re-applies them. The deliberate escape hatch is a new RPC **`yed_unlockcoin <txid> <n> "I understand this burns YED"`**. | safety | §5.2 |
| H6 | **A wallet that holds YED refuses to start without `-yellowback`.** If the datadir contains the Yellowback index and `-yellowback` is absent, `init` fails with a message; `-yellowback=0` given explicitly acknowledges that YED outputs become spendable as plain YEC. | safety | §5.3 |
| H7 | **`sendrawtransaction` guards owned YED.** When `-yellowback` is on, a raw transaction that spends a `Tokens` outpoint that is mine and whose payload does not reassign it is refused unless the new third parameter `allowyedburn` is true. Same shape as the existing `allowhighfees`. | safety | §5.4 |
| H8 | **Re-lock after key import.** `importprivkey`, `importwallet` and `importaddress` (after their rescan) and `z_importkey`'s transparent path call `Reconcile()`, so YED belonging to an imported key is locked before the next block, not after it. | safety | §5.5 |
| H9 | **Documented, not enforced:** keys imported into other software, `-yellowback` nodes that are not this wallet, and YED sent to a recipient that does not run the overlay. The `ye…` address prefix (D10) is the only technical guard on the last one and it stays. | docs | §5.6 |
| H10 | **`yed_getinfo` reports `lockedOutputs`** (count of YED outpoints currently locked) and **`protectedByIndex: true`**; `rpcversion` goes 1 → 2 for H3/H5/H7/H10. The GUI treats a mismatch between `lockedOutputs` and `yed_listunspent` as the trigger for `yed_lockcoins`. | contract | §6 |
| H11 | **Input cap stays 250** (`txbuilder.cpp:232`); a TRANSFER with 250 P2PKH inputs is ≈ 37 kB, well under `MAX_TX_SIZE`. No consolidation RPC in v1; the selector's greedy stage consolidates small outputs naturally. | precision | §4.1 |
| H12 | **Tests before code** for H1 (table-driven unit test) and H5/H6/H7 (functional); the lifecycle test's `lockunspent false` step becomes `yed_unlockcoin`. | process | §7 |

---

## 3. Inventory: how a user can lose YED by accident

Each row is a path by which a YED output could be spent as plain YEC (burning it, D18) or a
transfer could under-assign (burning the remainder). "Today" is the state of the trees on
2026-09-06.

| # | Path | Mechanism | Today | Gap | Fix |
|---|---|---|---|---|---|
| P1 | Change below the floor | XFER-1 cannot assign `(0, MIN_OUTPUT)`; XFER-2 burns the unassigned difference | **Refused** by `SelectYed` (C20); nothing burns | UX only: user must re-enter an amount | H1–H3 |
| P2 | Plain YEC spend of a YED output from this wallet (`sendtoaddress`, `sendmany`, `z_sendmany` from a t-address, `z_mergetoaddress`, `z_shieldcoinbase`) | All go through `AvailableCoins`, which skips locked coins (`ycash-dd/src/wallet/wallet.cpp:5074`; `asyncrpcoperation_sendmany.cpp:854`; `rpcwallet.cpp:2498,3373,4599,4922`) | **Closed** by the three-stage locking (B4, `src/yellowback/wallet.cpp:71-135`): pre-lock at `SyncTransaction`, lock before commit, `Reconcile` after every block and at startup (`init.cpp:1896`, before `SetRPCWarmupFinished` at `:2009`) | none | verify in §7 only |
| P3 | `lockunspent false [outpoint]` on a YED output, then any spend | Generic RPC removes the lock; locks are in-memory | **Open.** The lifecycle test uses exactly this to provoke a burn (development plan `:1837`) | a script, another tool or a user following a forum recipe can unlock YED without knowing it | H5 |
| P4 | `lockunspent true` with no outputs (unlock **all**) | `UnlockAllCoins` (`rpcwallet.cpp:2237-2241`) | **Open.** Every YED lock is gone until the next block's `Reconcile` (≈ 75 s window, longer if the chain stalls) | as P3, and it is the more common invocation | H5 |
| P5 | Node started without `-yellowback` | No index, no locks; YED outputs are 10,000-zat P2PKH coins to the wallet | **Open.** YecWallet writes `yellowback=1` into `ycash.conf` (`yecwallet-dd/src/connection.cpp:195-197`) and offers to repair a conf that lacks it (`:831-845`), but `ycashd` run by hand, or after a conf edit, has no guard | one `sendtoaddress` for the wallet's whole balance burns every YED output | H6 |
| P6 | Raw transaction spending a YED output (`createrawtransaction` + `signrawtransaction` + `sendrawtransaction`) | Bypasses `AvailableCoins` and the locks entirely | **Open** by design; `yed_validaterawtransaction` exists but nothing calls it on the send path | power users and integrators; the same tool an exchange would script with | H7 |
| P7 | Keys imported into this wallet after the YED was received | `Reconcile` runs at startup and on each block, not after `importprivkey`'s rescan | **Open** for one block: between the import and the next `ChainTip`, the tokens are `IsMine` but unlocked | narrow, but the restore flow is exactly when users sweep balances | H8 |
| P8 | Keys imported into **other** software (a lite wallet, a paper-wallet sweeper, another `ycashd` without the overlay) | The other software sees 10,000-zat coins and sweeps them | **Cannot be closed** from this codebase | user documentation; the "back up `wallet.dat` after minting" rule already in §4.5 | H9 |
| P9 | YED sent to an address whose owner does not run the overlay (an exchange, a plain `ycashd`) | Recipient's wallet sweeps the output as YEC | **Partly closed** by D10: a `ye…` address only exists if the recipient asked a Yellowback wallet for it; `yed_send` refuses `s1…` | a recipient who generated a `ye…` address and later runs without `-yellowback` — that is P5 on their side | H6, H9 |
| P10 | A TRANSFER that under-assigns (wallet bug) | D18: only the remainder burns | **Closed** in the builder by construction (`Σ assigned == yedIn` for TRANSFER); no independent check | a future edit could break the invariant silently | builder self-check via the `yed_validaterawtransaction` logic before `CommitTransaction` (§4.5) |
| P11 | Re-spending YED inputs reserved by a pending redemption | D3: `SpendableCoins` skips `reservedInputs` and `IsSpent` (`wallet.cpp:53-63`) | **Closed** | none | — |
| P12 | Disconnected block (reorg) returning a YED output to the mempool | C3: nothing is unlocked on disconnect | **Closed** | none | — |
| P13 | GUI YEC send | YecWallet sends YEC with `z_sendmany` (`yecwallet-dd/src/zcashdrpc.cpp:309`), which honours locks (P2) | **Closed** | the GUI has no coin control, so nothing else to guard | verify in §7 (also the turnstile/migration screens, which use node RPCs of the same family) |

Two observations that shape the design. First, every open path (P3–P7) is a way of getting
*around* the lock set, not a weakness in how it is derived: the index-derived lock set (B4) is the
right design and stays. Second, the wallet has one authoritative list of "outputs that are YED and
mine" — `YellowbackWallet::AllCoins()` — and every fix below consults that list rather than
introducing a second one.

---

## 4. Coin selection (H1–H4)

### 4.1 The floor-aware selector

Inputs: the spendable YED coins `S` (confirmed, mine, not reserved, not spent by an unconfirmed
wallet transaction — unchanged, F3/D3), a target `T` in cents, the floor `F = MIN_OUTPUT`, the cap
`N = 250` inputs. A selection is **valid** iff `sum ≥ T` and `change := sum − T` is `0` or `≥ F`.
The selector returns the first valid selection found in this order, and each stage is deterministic
given `S` sorted by `(cents, txid, vout)`:

1. **Exact.** A single coin with `cents == T`. No change output at all (saves `TOKEN_VALUE` and a
   keypool key).
2. **Single with valid change.** The *smallest* single coin with `cents ≥ T + F`. One input, one
   change output.
3. **Greedy with extension** (today's algorithm, made to finish the job). Accumulate smallest-first
   until `sum ≥ T`. If valid, done. If `change ∈ (0, F)`: keep adding the next-smallest unused coin
   while `|sel| < N`; the first sum with `change ≥ F` wins (each added coin is ≥ F itself, so one
   more coin always suffices when any unused coin exists).
4. **Swap.** If stage 3 exhausted the coins (the wallet's whole spendable balance minus `T` is in
   `(0, F)`), try dropping the last-added coin and replacing it with the smallest unused coin that
   makes `change == 0` or `change ≥ F`. This catches sets such as `{$2, $2, $3.50}` with `T = $5.50`.
5. **Bounded search.** Depth-first over `S` sorted descending, at most 1,000 node visits, looking
   for any valid selection with `|sel| ≤ N`. This is the same budget Bitcoin Core gives branch-and-
   bound (`SelectCoinsBnB`, 100,000 there; the sets here are tiny). Prefer fewer inputs, then
   smaller change.
6. **Refuse** (C20, §4.3).

Properties worth stating in the test: stage 1–2 selections are the cheapest possible; stage 3 never
produces more inputs than today's selector plus one for the same set; the result never depends on
iteration order of a `std::map` or on wall-clock; the selector is a pure function of `(S, T, F, N)`
and lives in `src/yellowback/coinselect.{h,cpp}` with no wallet dependency, so it is unit-testable
without a `CWallet`.

Why not just "add one more coin" and stop there: stage 4–5 matter exactly when the wallet is small
(one or two outputs), which is every new user. Why not always minimise inputs: the greedy stage's
consolidation keeps the output count of a long-lived wallet bounded without a separate consolidate
operation (H11).

### 4.2 Redemption

`BuildRedeem` calls the same selector with `T = requiredBurn` (`txbuilder.cpp:395-414`). Two
differences (H4):

- After stage 5 fails, instead of refusing, the builder **burns the remainder**: it takes the
  stage-3 selection, assigns no change, and sets `extraBurnCents = change`, which is `< F` by
  construction ($0.99 at most). REDEEM's XFER-2 semantics make this well-defined (the difference
  `yedIn − Σ` is the burn), and the redemption is a burn already.
- The RPC result gains `extraBurnCents` (0 in the normal case) and `burnCents` becomes
  `requiredBurn + extraBurnCents`. The wizard's review step shows "Burn: $105.27 required + $0.53
  that cannot be returned as change".

Refusing here would strand a user whose balance is, say, $105.80 against a $105.27 burn — they
could neither redeem nor easily obtain 47 more cents. Burning under a dollar is the better trade.

### 4.3 The refusal (TRANSFER only)

When stage 5 fails for a TRANSFER, the wallet refuses (H2). The message keeps the `C20` token the
GUI already matches on (`yecwallet-dd/src/yellowbackrpc.h:264-265`) and gains a fixed, parseable
tail:

```
change of 53 cents is below the minimum output of 100 cents (C20);
alternatives: below=300 above=400 spendable=400
```

`below` is the largest amount `≤ T` for which the selector succeeds; `above` is the smallest amount
`≥ T` for which it succeeds (often "send everything", i.e. `spendable`); either may be absent.
Both come from two more selector calls: `below` from `T' = sum − F` over the stage-3 selection
(valid change of exactly `F`) and `above` from `T' = sum` (no change). The selector is cheap enough
to call twice.

### 4.4 `yed_estimatesend`

```
yed_estimatesend [{"address":"ye…","cents":n}, …]
→ { "ok": true|false,
    "inputs": [{"txid","vout","cents"}…], "inputCount": n, "sumCents": n, "changeCents": n,
    "feeZat": n, "tokenValueZat": n,
    "error": "C20 …" (when !ok),
    "alternatives": { "belowCents": n, "aboveCents": n, "spendableCents": n } (when !ok) }
```

No signing, no locking, no reservation; it reads `SpendableCoins()` under `cs_wallet` and runs the
selector. `yed_send`/`yed_sendmany` call the same function and then build, so the estimate and the
send cannot disagree unless the wallet's coins changed in between (a new block), which the GUI
handles by re-estimating on every `refresh`.

### 4.5 Builder self-check (P10)

Before `CommitTransaction`, `BuildTransfer` runs the payload through the same evaluation
`yed_validaterawtransaction` uses and asserts `yedOut == yedIn` for TRANSFER and
`yedIn − yedOut == burnCents` for REDEEM. A mismatch throws; nothing is committed. This is ~10 lines
and turns a silent D18 burn into a wallet error.

---

## 5. Coin locking (H5–H9)

### 5.1 What stays

The three-stage design of B4 is unchanged and is the foundation: the index is the source of truth,
`AllCoins()` is the one list, `Reconcile()` re-derives `setLockedCoins` from it after every block
and at startup, and `yed_lockcoins` re-runs it on demand (`src/rpc/yellowbackwallet.cpp:646-660`).
Lock ordering (B15) is unchanged: never `cs_main` in callbacks; `cs_yellowback` then `cs_wallet`.

### 5.2 Protected locks (H5)

`YellowbackWallet` already tracks the outpoints it locked (`ourLocks`, `wallet.cpp:71-78`).
Expose `bool IsProtected(const COutPoint&) const` over that set (under `cs_wallet`) and change
the generic RPC, not `CWallet`:

- `lockunspent false [{txid,vout}…]` (lock) — unchanged.
- `lockunspent true [{txid,vout}…]` (unlock listed) — for each outpoint that `IsProtected`, skip it
  and collect it; if any were skipped, throw `RPC_INVALID_PARAMETER` **after** unlocking the others:
  `"3 output(s) are YED and stay locked; use yed_unlockcoin to release one (spending it burns the
  YED)"`.
- `lockunspent true` (unlock all) — call `UnlockAllCoins()` as today, then immediately
  `g_yellowbackWallet->Reconcile()`, so the YED locks are back before the RPC returns. Report in the
  result how many were re-applied (`lockunspent` returns a bare `true` today; keep that and log the
  count under `-debug=yellowback`, to avoid changing the RPC's result type).
- `listlockunspent` — unchanged; YED outputs keep appearing there, which is the honest view.

`yed_unlockcoin <txid> <n> "<acknowledgement>"` — the acknowledgement must equal the literal
`"I understand this burns YED"`; the RPC removes the outpoint from `ourLocks` and from
`setLockedCoins`, and records it in a small in-memory `manualUnlocks` set that `Reconcile` skips
(otherwise the next block would re-lock it). A manual unlock dies with the process or when the
outpoint is spent. This is the only sanctioned way to spend YED as YEC and it exists for tests and
for the rare recovery case (a user who wants the 10,000 zat back from a worthless VOID token — note
that VOID tokens are *already* released by stage iii, so the case is rarer still).

The change to `rpcwallet.cpp` is ≈ 25 lines in the `lockunspent` handler, guarded by
`if (yellowback::g_yellowbackWallet)`, so a node without `-yellowback` compiles and behaves as
before.

### 5.3 Refuse to start without the overlay (H6)

In `init.cpp`, in the block that already decides `fExperimentalYellowback` (`:1127-1150`): if
`-yellowback` is **not** set, the wallet is enabled, and `GetDataDir() / "yellowback"` exists, then

- if `mapArgs.count("-yellowback")` is zero (the flag was never given): `InitError` —
  `"This data directory has a Yellowback index. Start with -yellowback (and -experimentalfeatures),
  or pass -yellowback=0 to run without it; without it, YED outputs are ordinary YEC to this wallet
  and spending them destroys the YED."` YecWallet never hits this because it writes the conf lines;
  a hand-run `ycashd` gets one clear stop instead of a silent burn.
- if `-yellowback=0` was given explicitly: log a warning at startup and continue. The user has
  acknowledged.

`GetBoolArg` cannot distinguish absent from `=0`; use `mapArgs.count` for the test, as the same
block already does for the regtest-only options (`:1150`). Nothing changes when the index directory
does not exist, so fresh installs and non-Yellowback users are unaffected.

### 5.4 `sendrawtransaction` guard (H7)

`sendrawtransaction "hex" ( allowhighfees allowyedburn )`. When `-yellowback` is on and the wallet
is enabled: decode, and for each input whose outpoint is in `Tokens` **and** `IsMine`, check whether
the transaction's payload (if any, via `FindPayload`) reassigns at least the input's cents in
total — i.e. run the same `yedIn`/`yedOut` computation as `yed_validaterawtransaction` restricted to
owned inputs. If the transaction would burn owned YED and `allowyedburn` is not true, throw
`RPC_VERIFY_REJECTED`: `"this transaction spends N cents of this wallet's YED without reassigning
them (burn); pass allowyedburn=true to send it anyway"`.

Restricting the guard to **owned** tokens keeps `sendrawtransaction` a faithful relay for everyone
else's transactions (a co-signer relaying a redemption, a test harness injecting a deliberately
under-assigning TRANSFER, B1). The guard is policy in a wallet-facing RPC, not in `AcceptToMemoryPool`,
so it changes no network behaviour and adds no divergence between nodes.

### 5.5 Re-lock after import (H8)

`importprivkey`, `importaddress`, `importwallet` and `z_importkey`/`z_importwallet` (transparent
part) end with a rescan when asked. Add one call after each rescan: `if
(yellowback::g_yellowbackWallet) yellowback::g_yellowbackWallet->Reconcile();`. Reconcile is idempotent
and cheap (one index scan of `Tokens`). The restore test (`qa/rpc-tests/yellowback_wallet_restore.py`)
gains an assertion that `listlockunspent` shows the imported YED **before** any block is mined.

### 5.6 What only documentation can cover (H9)

- **Other software.** A private key that holds YED, imported into any wallet that does not run the
  overlay, will be swept as YEC. User documentation for Yellowback addresses says so in the same
  sentence that tells users to back up `wallet.dat` after minting. The `ye…` prefix helps here too:
  a user who exports "the key for ye…" has a visible hint that it is not an ordinary address.
- **Recipients.** Sending YED to a `ye…` address is safe by construction; the recipient's wallet
  produced that address only because it runs the overlay. If they later run without it, H6 stops
  them at startup. The remaining case — they delete the index directory and run without the flag —
  is deliberate and out of scope.
- **`getbalance` counts `TOKEN_VALUE`.** Each YED output adds 0.0001 YEC to the YEC balance. Already
  documented in the development plan §4.5; the GUI's YEC balance may subtract `lockedOutputs ×
  TOKEN_VALUE` (H10 makes the count available) so the two figures do not confuse users. Optional.

---

## 6. RPC contract and GUI (development plan §4.7)

**Node (`ycash-dd`).** `rpcversion` 1 → 2.

| RPC | Change |
|---|---|
| `yed_estimatesend` | new (§4.4) |
| `yed_send`, `yed_sendmany` | selector H1; refusal format §4.3 |
| `yed_redeem` | selector H1; `extraBurnCents` in the result; `burnCents` includes it (H4) |
| `yed_unlockcoin` | new (§5.2) |
| `yed_getinfo` | `lockedOutputs`, `protectedByIndex` (H10) |
| `lockunspent` | protects YED outpoints; unlock-all re-applies (§5.2) |
| `sendrawtransaction` | third parameter `allowyedburn` (§5.4) |
| `importprivkey` & co. | re-lock after rescan (§5.5) |

**GUI (`yecwallet-dd`).**

| Screen | Change |
|---|---|
| **Send** | On every amount edit (debounced 300 ms) and on every `refresh`, call `yed_estimatesend`. While `ok` is false, disable Send and show `"$3.47 would leave $0.53 that cannot be change. Send $3.00 or $4.00 instead."` with two buttons that set the amount. Show `inputCount` and the YEC fee from the estimate. The existing error handler for `C20` stays as the belt-and-braces path. |
| **Redeem** wizard, step 2 | Show `extraBurnCents` when non-zero: `"+ $0.53 that cannot be returned as change"`. |
| **Overview** | YEC balance shown net of `lockedOutputs × TOKEN_VALUE` (optional, H9). |
| **Status banner** | If `yed_getinfo.lockedOutputs` is less than the number of spendable outputs in `yed_listunspent`, call `yed_lockcoins` once and log; never show the user a "locks drifted" message — it is the wallet's job to fix, not theirs. |
| **Settings** | none. `rpcversion` 2 is required; the existing version check message names the node build needed. |

The `yellowbackrpc.h` constants file gets the new method and field names; the `MIN_OUTPUT_CENTS`
fallback (`:304`) stays for the pre-params case.

---

## 7. Tests

| Kind | File | Covers |
|---|---|---|
| Unit | `src/test/yellowback_coinselect_tests.cpp` (new) | H1 stages 1–5 on a table of coin sets: single coin exact; single coin with valid change; greedy valid; greedy sub-floor fixed by extension; the `{$2,$2,$3.50}` swap case; whole-balance-minus-target sub-floor (refusal with correct `below`/`above`); 250-input cap; determinism (shuffle input order, same result); REDEEM remainder burn (H4) |
| Unit | `yellowback_payload_tests.cpp` | builder self-check rejects an under-assigning TRANSFER (P10) |
| Functional | `qa/rpc-tests/yellowback_lifecycle.py` | replace the `lockunspent false` burn provocation with `yed_unlockcoin` (H5); assert `lockunspent true` (unlock-all) leaves YED locked; assert `lockunspent true [yed outpoint]` is refused; `yed_estimatesend` agrees with `yed_send` on the same amount; a send that previously hit C20 now succeeds via extension |
| Functional | `qa/rpc-tests/yellowback_wallet_restore.py` | imported YED locked before the next block (H8) |
| Functional | `qa/rpc-tests/yellowback_rawtx_guard.py` (new) | `sendrawtransaction` refuses an owned-YED burn without `allowyedburn`; relays the same transaction with it; relays a burn of **someone else's** YED without the flag (H7 scope) |
| Functional | `yellowback_lifecycle.py` | node restarted without `-yellowback` fails init with the H6 message; with `-yellowback=0` it starts and logs the warning |
| GUI QTest | `yecwallet-dd/tests/` | Send screen: entering an unworkable amount disables Send and offers both alternatives; clicking one sets the amount and re-enables (mocked `yed_estimatesend`) |

Exit criterion for the whole document: the lifecycle test contains **no** step that burns YED
except through `yed_unlockcoin` or `allowyedburn=true`, and every such step names itself as a burn.

---

## 8. Work plan

Order chosen so that the safety items (H5–H8) land before the UX items, because they are smaller
and independent of the selector.

| Step | Items | Files | ≈ lines | Exit |
|---|---|---|---|---|
| 1 | H5, H10 | `src/yellowback/wallet.{h,cpp}`, `src/rpc/yellowbackwallet.cpp`, `src/wallet/rpcwallet.cpp` | 120 | lifecycle test's lock assertions green; `yed_unlockcoin` replaces `lockunspent false` |
| 2 | H6 | `src/init.cpp` | 20 | restart-without-flag test green |
| 3 | H8 | `src/wallet/rpcwallet.cpp`, `src/wallet/rpcdump.cpp` | 15 | restore test's new assertion green |
| 4 | H7 | `src/rpc/rawtransaction.cpp`, `src/yellowback/` (shared evaluation helper) | 80 | raw-tx guard test green |
| 5 | H1, H2, H4, P10 | `src/yellowback/coinselect.{h,cpp}` (new), `txbuilder.cpp` | 250 + 150 test | unit table green; lifecycle send/redeem steps green |
| 6 | H3 | `src/rpc/yellowbackwallet.cpp` | 80 | estimate/send agreement test green |
| 7 | GUI | `yecwallet-dd/src/yellowbacktab.cpp`, `yellowbackcontroller.cpp`, `yellowbackrpc.h`, `yellowbackredeemwizard.cpp`, `yellowbacksend.ui` | 250 | QTest green; manual run on the devnet (`contrib/yellowback/devnet`) with a wallet holding one $4.00 token sending $3.47 |
| 8 | Docs | `docs/mapping.md` §11/§12 rows for `LockCoin` persistence and `lockunspent`; development plan §4.5, §4.7, §7 cross-references; user documentation text for H9 | — | `make status` clean; this document's status → DECIDED |

Total ≈ 1,000 lines including tests; no consensus files touched (`make diff` must show nothing under
`src/consensus/`, `src/script/`, `src/main.cpp`, `src/primitives/`).

---

## 9. Considered and rejected

- **Lowering `MIN_OUTPUT`** (to $0.01 or $0.10) to make the floor bite less. It is an overlay
  consensus parameter and the YED dust rule; changing it moves the problem to index bloat and does
  not remove the class of failure (any floor > 1 cent has a sub-floor band). Rejected.
- **More decimal places for YED.** See §1; rejected in the 2026-09-06 discussion.
- **Burning the remainder on TRANSFER** as a user-approved option. Overpaying the recipient by the
  same amount is strictly better for the user and needs no new consent flow (the alternatives in
  §4.3 already express it). Rejected; REDEEM is different (H4).
- **Persisting locks in `wallet.dat`** as DigiByte does. Ycash 4.5's `CWallet` has no persistent
  lock storage; adding it means a `wallet.dat` schema change for a fact the index already knows.
  Re-deriving from the index (B4) is strictly more robust. Rejected.
- **Guarding in `AcceptToMemoryPool`** (refuse to relay any burn of a `Tokens` outpoint). That is
  network policy, differs between nodes with and without the overlay, and would block legitimate
  burns (REDEEM's own burn is one). Rejected; H7 guards only the local wallet's RPC.
- **A `yed_consolidate` RPC.** The greedy stage consolidates as a side effect; add it only if
  fragmentation is observed on testnet (H11).
- **Coin control in the GUI.** YecWallet has none for YEC either; the estimate flow (H3) gives the
  user the only two levers that matter (amount and "send all").
