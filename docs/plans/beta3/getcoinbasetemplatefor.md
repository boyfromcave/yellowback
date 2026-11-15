# `getcoinbasetemplatefor`: design note (beta3 item 3, chunk N-1)

**Revision 1 (2026-11-15). For the Yellowback lead architect's approval before 3n, 3k and 3p start.**
This note fixes the interface between three implementations that are built in parallel: the node
call on ycash-dd and ycash6 (chunk 3n), kogany's equivalent (3k) and yolo's paired jobs (3p). Each
of the three implements against this note alone. Where the note says MUST, a deviation is a defect
on that line.

Code is cited at the tips the run started from: ycash6 `9a794e761`, ycash-dd `f273cf90a`, kogany
`0c4f678f6`, yolo `e91154a`. Measurements were taken on 2026-11-15 on regtest nodes of this lane
(§10 lists every run and its script).

## 1. What is fixed, and what this note adds

Fixed by the lead architect (`wt/beta3-list.md` item 3) and not reopened here:

- The call is `getcoinbasetemplatefor`. It is stateless in the node; the caller caches.
- Its arguments are a payout address and a reference to a template the node produced. There is no
  amount argument and no way to ask for a lower amount: the node derives the amount (block subsidy
  plus every fee of that template's transactions) itself.
- `getblocktemplate` and `submitblock` are untouched. Nothing here is a consensus change.
- A miner who finds a block is paid in full.

This note adds: the exact request and response (§3), how the template is named and what "stale"
means (§4), the coinbase's contents and what a pool may change in it (§5), locking, concurrency
and cost (§6), the errors (§7), yolo's flow and the interface 3p may code against today (§8),
kogany's contract (§9), the evidence (§10), and the findings that need the lead architect's decision (§2, and D-6 in §8.1).

## 2. Findings that need the lead architect's decision

Each is the smallest change this lane can propose; none is applied anywhere yet.

| # | Finding | Proposed |
|---|---|---|
| **D-1** | **"No way to request a lower amount" cannot be absolute in a stateless call.** A node that remembers nothing cannot tell a template it issued from a list of mempool transactions a caller made up. With the reference of §4 (the previous block hash and the template's transaction ids) a caller can name fewer transactions than its block will carry and so obtain a coinbase that claims fewer fees. Consensus accepts such a block (measured, §10 run 1: a coinbase built for an empty template, on a block with fee-paying transactions, was accepted and 637 zatoshi of fees were claimed by nobody). No design of this call can prevent that: a pool can also keep an old coinbase, or build its own. Only the exact-claim consensus rule could, and it is not requested. | Accept the stateless reference of §4. The interface still has no amount argument, the node never lowers an amount, and yolo checks every answer against the stock template (§8.3) and never pairs a coinbase with a transaction set other than the one it named. The alternative, a bounded per-tip memory of issued templates in the node (not per address), costs a hook inside `getblocktemplate`'s code path, has no counterpart in kogany, and closes nothing, because the pairing happens in the pool. |
| **D-2** | **The swap path and the paired path disagree when the pool node runs with `-ydf=<n>` above 0.** The stock coinbase carries the operator's optional fund share (yolo keeps "any further output" as the node built it, `yolo/src/work.rs:110-118`), while `getcoinbasetemplatefor` builds no optional share. A transparent miner on the swap path would then be paid 5 % less than a Sapling miner on the same pool. With item 4 (default 0 %) this needs an operator who opted in. | In per-miner mode (no `--payout`) yolo refuses to issue work, with a clear log line, while the stock coinbase has more than one output at a height where `coinbasetxn.foundersreward` is absent or zero (the share is then optional). The pool recipe sets `-ydf=0`. No node change. |
| **D-3** | **A full block has no room for a Sapling coinbase.** Both C++ assemblers reserve 1,000 bytes for the header and the coinbase together (`ycash6/src/miner.cpp:310-317`, `ycash-dd/src/miner.cpp:486`) and cap the rest at `MAX_BLOCK_SIZE - 1000`. A mainnet header with its Equihash 192,7 solution is 1,487 bytes, so only about 510 bytes are certain to be free; a Sapling coinbase is 1,119 bytes (measured). A template within about 600 bytes of the size limit cannot take one. Ycash blocks are far from full, so this is a boundary, not a daily case, and it already exists for a node mining to its own Sapling `-mineraddress`. | The call refuses with `coinbase-does-not-fit` (§7) instead of returning a coinbase that makes the block invalid. yolo MUST NOT drop transactions to make room on a paired job (today's `build_work` truncates at the size limit, `yolo/src/work.rs:131-137`; on a paired job that would leave the coinbase claiming fees of dropped transactions, `bad-cb-amount`). The miner stays on its previous pair until the next template. No change to the assembler. |
| **D-4** | **kogany cannot build a Sapling coinbase today** (§9, measured). It has no Sapling prover and loads no proving parameters. | 3k ships transparent and post-quantum payouts first and answers a Sapling address with the refusal of §7 row 9. The Sapling part is a separate chunk, size M to L (an output prover, the 3.6 MB Sapling output parameters and their loading, a v4 coinbase path with a Sapling output, tests). The lead architect decides whether it holds the kogany release. The demonstration's pool node is ycashd, so criterion 2 does not depend on it. |
| **D-5** | **A username with a worker suffix is refused today** (`<address>.rig1`: `Invalid address`, measured), and mining programs commonly add one. | 3p accepts `<address>` and `<address>.<worker>`: the part before the first `.` is the address (no address of any of the three kinds contains a `.`), the rest a label of at most 32 characters from `[A-Za-z0-9_-]`, shown in the log and `/status` only. F-1 passes the bare address. |

Two smaller facts the three lanes must know are in §5.4 (the quote tag is the node's current one,
not the template's) and §6.3 (a cap on parallel requests, or `submitblock` waits behind proofs).

## 3. The call

### 3.1 Request

```
getcoinbasetemplatefor "address" {"previousblockhash": "<hex>", "txids": ["<hex>", ...]}
```

| Position | Name | Type | Meaning |
|---|---|---|---|
| 0 | `address` | string | The payout address, in the node's network encoding. Accepted kinds: transparent P2PKH (`s1…` mainnet, `sm…` testnet and regtest), transparent P2SH, Sapling (`ys1…`, `ytestsapling1…`, `yregtestsapling1…`), post-quantum plain YEC (`sqf…`/`sqs…`, `tqf…`/`tqs…`, `rqf…`/`rqs…`). Nothing else: no Sprout address, no unified address, no YED address (`yb…`), no pre-D-9 post-quantum form. |
| 1 | `template` | object | Exactly two keys; any other key is refused (so an `amount` key can never be accepted by accident). |
| | `template.previousblockhash` | string, 64 hex characters | `previousblockhash` of the `getblocktemplate` reply the caller holds, verbatim (display byte order). |
| | `template.txids` | array of strings, each 64 hex characters | The `hash` of every entry of that reply's `transactions`, in the reply's order. Empty for a template without transactions. At most 50,000 entries. |

Hex is lower or upper case on input; every hex string in the response is lower case. Hashes are in
display byte order, as `getblocktemplate` prints them.

`ycash-cli` gets a conversion entry for parameter 1 (`src/rpc/client.cpp`); ycash6 also registers
the call in `src/rpc/common.h`. The call is in the `mining` category and needs neither a wallet
nor `-mineraddress` (unlike `getblocktemplate`, `ycash6/src/rpc/mining.cpp:525-534`).

### 3.2 Response

One object. All amounts are integers in zatoshi, as `getblocktemplate` prints `fee`.

| Key | Type | Meaning |
|---|---|---|
| `data` | string, hex | The serialized coinbase transaction, complete and valid as returned. |
| `hash` | string, 64 hex | Its transaction id (display order). It changes if the caller rewrites the scriptSig (§5.5). |
| `height` | number | The height the coinbase is for: the tip's height plus one. |
| `previousblockhash` | string, 64 hex | Echo of the request. |
| `addresstype` | string | `"p2pkh"`, `"p2sh"`, `"sapling"` or `"pq"` (the names `z_validateaddress` uses). |
| `subsidy` | number | The block subsidy at `height`. |
| `fund` | number | The development-fund output's value: `subsidy / 20` where consensus requires the output at `height`, otherwise `0` and no such output exists (§5.2). |
| `fees` | number | The sum of the fees of the named transactions. |
| `amount` | number | What `address` receives: `subsidy - fund + fees`. Never anything else. |
| `txcount` | number | The number of transaction ids the amount was derived from. |
| `flags` | string, hex | The scriptSig bytes after `<height> OP_0`: the Yellowback quote tag push, or empty (§5.4). Same meaning as `getblocktemplate`'s `coinbaseaux.flags`. |
| `sigops` | number | The coinbase's legacy signature-operation count, as `coinbasetxn.sigops`. |

Reserved, absent today: `defaultroots` (an object shaped like `getblocktemplate`'s). It will carry
the per-coinbase header values if a header rule that commits to the coinbase ever activates on
Ycash (§4.4). Until that is implemented the call refuses at such a height (§7 row 13), so a caller
that ignores the key is never handed a coinbase that needs it.

Example (regtest, a Sapling address, a template with three transactions paying 734 zatoshi in
fees, the fund output not required):

```json
{
  "data": "0400008085202f89010000…",
  "hash": "1eea759c…043d5022",
  "height": 111,
  "previousblockhash": "04188e0f…ca1973f7",
  "addresstype": "sapling",
  "subsidy": 625000000,
  "fund": 0,
  "fees": 734,
  "amount": 625000734,
  "txcount": 3,
  "flags": "",
  "sigops": 0
}
```

### 3.3 What the node does (normative, both C++ lines)

1. **Parse** the parameters (no lock). Decode the address for the node's network. Shape errors are
   §7 rows 1 to 6.
2. **Refuse as `getblocktemplate` does**, with its codes and strings: no peers outside regtest,
   initial block download, an unhealthy Yellowback index (`ycash6/src/rpc/mining.cpp:522-523,
   586-590`).
3. **Under `cs_main` and `mempool.cs`, read only:**
   - the tip's hash MUST equal `previousblockhash`, else *stale* (§7 row 10); `height` = tip + 1;
   - the address kind MUST be payable in a coinbase at `height` (§5.1), else §7 row 8;
   - if the header commits to the coinbase at `height` (NU5 rules active), refuse (§7 row 13);
   - every transaction id MUST be in the mempool, else *stale* (§7 row 11); a repeated id is an
     error (§7 row 5); sum the entries' fees, serialized sizes and signature-operation counts;
   - the quote tag for a coinbase built now: `yellowback::policy::BuildTagScript(index, GetTime())`
     when the index exists, else empty. Read it into a local; do not read or write the global
     `COINBASE_FLAGS` (it belongs to `CreateNewBlock`, `ycash6/src/miner.cpp:354`);
   - `subsidy`, and whether the fund output is required at `height`.
4. **Release both locks. Build the coinbase** (§5) for `amount = subsidy - fund + fees`: outputs,
   scriptSig, and for a Sapling address the output proof and the binding signature.
5. **Check it fits**: the block made of a header with the network's Equihash solution, the
   coinbase and the named transactions MUST respect `MAX_BLOCK_SIZE` and `MAX_BLOCK_SIGOPS`, else
   §7 row 12.
6. **Take `cs_main` again**: the tip MUST still equal `previousblockhash`, else *stale*. (The
   mempool is not read again: a transaction that left it without a new block is still valid in
   the block.)
7. Return §3.2.

The node MUST NOT, in this call: read `-ydf` or `-mineraddress`; touch the wallet; read, replace
or invalidate `getblocktemplate`'s cached template or its statics; keep anything between calls.
Two calls with the same arguments return two valid coinbases that differ only in the Sapling
output's randomness (and in `flags`, if the quote changed in between).

The amount is taken from the mempool entry's fee (`CTxMemPoolEntry::GetFee()`), the same number
`getblocktemplate` prints per transaction on both lines (measured equal, §10 run 1) and the one
consensus sums into the coinbase limit (`bad-cb-amount`, `ycash6/src/main.cpp:4322-4331`,
`ycash-dd/src/main.cpp:3520`).

## 4. Naming the template

### 4.1 What the reference is

The reference is **`previousblockhash` plus the list of the template's transaction ids**. Both are
in today's `getblocktemplate` reply; nothing is added to that reply.

That pair is sufficient: the coinbase amount depends on the height (subsidy, fund rule) and on the
fees of the transactions, and on nothing else in the template. And it is what a stateless node can
check: the tip it knows, and each transaction's fee from its own mempool.

### 4.2 Why not the other fields

| Field of the reply | Why it cannot serve |
|---|---|
| `longpollid` | Not unique. It is the tip hash followed by the mempool's update counter at the last rebuild (`ycash6/src/rpc/mining.cpp:837`). A rebuild caused by a new quote keeps the counter (`:691-698`), the node sets the counter to 0 when it serves an empty block from a cached shielded coinbase (`:704`), and two nodes with the same mempool print different ids only by accident. And the node could not turn it back into a fee total without remembering templates. |
| `defaultroots.merkleroot` | Identifies the template exactly (it covers the stock coinbase and every transaction), but a stateless node cannot invert it. |
| `curtime` | Changes on every call (`UpdateTime`, `:736`) without the template changing; the coinbase does not depend on it. |
| `coinbasetxn` | The caller could send it back and the node could read the amount from it, but that is an amount argument by another name, and the node could not tell an altered one. |
| `transactions[].fee` | The same objection: the node must derive the fees, not be told them. |

### 4.3 Stale and unknown references

- **The tip moved** (`previousblockhash` is not the tip, at step 3 or at step 6): refused. The
  caller's template is void anyway.
- **A named transaction is not in the mempool** (mined, expired, evicted, or never there): refused,
  naming the first missing id. This is how "the mempool moved on" shows: the node can no longer
  state that transaction's fee, so it states nothing.
- **New transactions arrived**: irrelevant. They are not in the caller's template, the coinbase is
  for the named set, and they go into the caller's next template. The call keeps working for the
  old set for as long as the tip stands and its transactions stay in the mempool.
- **The node restarted**: its mempool is empty, so any non-empty reference is refused until the
  caller fetches a new template. Nothing else is lost, because nothing was kept.

On either refusal the caller fetches `getblocktemplate` again and asks again (§8.2).

### 4.4 The header root does not depend on the coinbase (question c)

A pool pairs the stock template's header fields with a coinbase the template did not contain. That
is sound exactly when the header's fourth field (`hashBlockCommitments` on ycash6,
`hashLightClientRoot` on ycash-dd) does not commit to this block's coinbase.

| Rules at the height | The field is | Depends on this block's coinbase |
|---|---|---|
| Sapling, before Heartwood | the Sapling tree root after this block (`ycash6/src/miner.cpp:478-480`, check `main.cpp:4268-4275`) | Only through Sapling outputs in the coinbase, and before Heartwood a coinbase may not have any (`bad-cb-has-output-description`, `main.cpp:1179-1184`). So: no. |
| Heartwood's activation height | null (`miner.cpp:470-472`, `main.cpp:4245-4252`) | No |
| Heartwood and later, before NU5 | the chain history root of the previous block (`miner.cpp:473-476`, `main.cpp:4253-4267`; ycash-dd `miner.cpp:692-695`, `main.cpp:3471-3485`) | No |
| NU5 and later | a hash over the history root and the block's authorizing-data root (`miner.cpp:446-468`) | **Yes** |

| Network | Heartwood | NU5 | Heights that matter | Independent |
|---|---|---|---|---|
| mainnet | 1,100,003 | never (`NO_ACTIVATION_HEIGHT`, `ycash6/src/chainparams.cpp:136-141`) | tip near 3,102,000 | yes |
| testnet, fast profile (inherits testnet) | 510,252 | never (`:458-463`, `:648-652`) | tip near 511,350; Vault at 510,400 | yes |
| testnet, slow and legacy profiles (inherit mainnet) | 1,100,003 | never (`:679`, `:766-800`) | above 3,079,999 | yes |
| regtest | by `-nuparams` | by `-nuparams` | every height the suites use | yes whenever NU5 is not switched on; a Sapling payout additionally needs Heartwood on |

ycash-dd has no NU5 branch in its header code at all (`ycash-dd/src/miner.cpp:692-698`).
Vault sits between Canopy and NU5 and its transactions are v4 only, so no Ycash network reaches
the fourth row. The call refuses there rather than guess (§7 row 13); the reserved `defaultroots`
key is where the per-coinbase value will go.

Proof by a block: §10 run 1. Two nodes with the same tip and the same mempool, one mining to a
transparent address and one to a Sapling address, served the same root; a block made of the
transparent node's header fields and transactions and the Sapling node's coinbase was accepted at
height 111 with Heartwood, Canopy and Vault active.

## 5. The coinbase

### 5.1 Outputs by address kind

| Kind | Payable in a coinbase | Transparent outputs | Shielded part |
|---|---|---|---|
| P2PKH, P2SH | at every height | `vout[0]` = `amount` to the address's script; then the fund output if required | none |
| Post-quantum (`<32-byte key hash> <scheme> OP_CHECKPQSIG`, 35 bytes) | from the Vault upgrade's activation height | as transparent | none |
| Sapling | from Heartwood's activation height | only the fund output, if required (it is then `vout[0]`) | one Sapling output of `amount` to the address, empty memo, encrypted to the all-zero outgoing viewing key as consensus requires of a coinbase; `valueBalance = -amount`; the binding signature |

This is the layout both nodes' own miners already produce (`AddOutputsToCoinbaseTxAndSign`,
`ycash6/src/miner.cpp:96-268`, `ycash-dd/src/miner.cpp:162-314`); 3n reuses those visitors and
gives them the two things that differ: the fund rule of §5.2 instead of `-ydf`, and the tag as an
argument instead of the global.

Fixed fields: version 4 with the Sapling version group, `nLockTime` 0, `nExpiryHeight` 0, one
input with a null prevout and sequence `0xffffffff`, as `CreateCoinbaseTransaction` sets them.

Measured sizes: 141 bytes for a P2PKH coinbase with a fund output, 151 for a post-quantum one,
1,119 for a Sapling one with a fund output.

### 5.2 The fund output

- Where consensus requires it at `height` (`height < nYdfMandateEndHeight`, after the Ycash fork:
  `ycash6/src/main.cpp:6267-6283`): one output of `subsidy / 20` to
  `GetFoundersRewardScriptAtHeight(height)`, and `fund` reports it.
- Everywhere else: no fund output, `fund` is 0, whatever `-ydf` says. The call never deducts an
  optional share on a miner's behalf.
- Before the Ycash fork (regtest without the Ycash upgrade): the founders' reward rule of that era
  applies as in `CreateCoinbaseTransaction` (`subsidy / 5` while required); `fund` reports that
  output. No network of ours is there; the suites that leave the Ycash upgrade off still pass.

Today that means: mainnet, none (the mandate ended at 2,275,000); the fast testnet, required until
the height item 5 sets; regtest, required below height 5.

### 5.3 The scriptSig

`<height> OP_0 <flags>`: the minimal height push consensus requires first, `OP_0` where the
internal miner puts its extranonce, then the tag push. This is byte for byte what the node's own
coinbase carries (`ycash6/src/miner.cpp:291`), so a pool that leaves it alone mines the same
script on both paths.

### 5.4 The quote tag

`flags` is the tag the node would put into a coinbase it built at the moment of the call (step 3),
not the tag of the caller's template. They differ only when a quote was set between the caller's
`getblocktemplate` and this call. The newer one is the better one to mine, no property of a tag
makes a block invalid (`ycash6/src/yellowback/tag.h:20-30`, TAG-4), and reproducing the template's
tag would need the node to remember it. The caller uses the response's `flags` wherever it used
`coinbaseaux.flags` for that job.

The tag's `payoutKey` is the node's `-yellowbackpayoutaddress`, on this path as on the swap path
(yolo `/status` `tagPayoutKey: "node"`): miners are not registered as Yellowback miners by their
username. Unchanged by this item.

### 5.5 What the pool may change afterwards, and what it must never change

**May change:** the scriptSig bytes after the height push, within 100 bytes in total, keeping the
`flags` bytes verbatim somewhere after the height push. That is yolo's `--text`
(`<height> <flags> <push of the text>`, `yolo/src/work.rs:99-107`). It is safe for a Sapling
coinbase too: a v4 transaction's binding signature signs the ZIP 243 hash, which covers prevouts,
sequences and outputs but no scriptSig. Measured: a Sapling coinbase with bytes appended to its
scriptSig was accepted (§10 run 1). After a change the pool recomputes the transaction id and the
merkle root, as it does today.

**Must never change, on a coinbase from this call:** any output, script or value; `valueBalance`;
the Sapling output, its proof, the binding signature; version, lock time, expiry. One zatoshi of
difference in `valueBalance` makes the block invalid (`bad-sapling-bundle-authorization`,
measured). In particular yolo MUST NOT run its `vout[0]` script swap on such a coinbase (for a
Sapling payout with a required fund output, `vout[0]` is the fund).

**Must never change, in the job:** the transaction set. The block carries exactly the named
transactions, in the template's order. Fewer transactions would leave the coinbase claiming fees
that are not in the block (`bad-cb-amount`, measured); more would forgo fees (D-1).

### 5.6 Extranonce

None is needed in the coinbase. In Ycash stratum the miner's search space is the header's 32-byte
nonce, split by yolo into 14 bytes it assigns per connection and 18 the miner iterates
(`yolo/src/stratum.rs:31`), plus `nTime`. Two connections with the same payout address share a
coinbase and differ in the pool's nonce part. So a shielded coinbase needs no rewriting per share,
per miner or per connection, and one proof serves a miner for the life of a job.

## 6. Locks, concurrency, cost

### 6.1 Proving outside `cs_main`

Steps 1, 4 and 5 hold no lock; steps 3 and 6 hold `cs_main` (step 3 also `mempool.cs`) for a hash
comparison and one mempool lookup per transaction. The proof is made in step 4. There is precedent
in the same file: `getblocktemplate`'s long-poll branch already builds a shielded coinbase after
`LEAVE_CRITICAL_SECTION(cs_main)` (`ycash6/src/rpc/mining.cpp:639-656`). What that precedent gets
wrong, and this call must not repeat, is reading the global `COINBASE_FLAGS` there without the
lock: pass the tag in.

The Sapling prover is safe to run from several threads at once on both lines (the wallet's
asynchronous operations already do).

### 6.2 Cost

Per call: one mempool lookup per named transaction, plus, for a Sapling address only, one Sapling
output proof and one binding signature. Transparent and post-quantum calls make no proof.

Measured on this machine (Apple M5, 10 cores, under load from other builds; §10 runs 1 and 4):

| What | ycash6 (6.22.0-beta2) | ycash-dd |
|---|---|---|
| `getblocktemplate` on a fresh tip, transparent miner address | 0.06 to 0.15 s | 0.03 to 0.04 s |
| the same with a Sapling miner address (one proof, one binding signature) | 0.14 to 0.28 s | 0.11 to 0.13 s |
| **difference: the cost a Sapling call adds** | **0.07 to 0.18 s** | **about 0.09 s** |
| `zcbenchmark createsaplingoutput` (the output proof alone, 12 samples) | 0.26 to 0.48 s | 0.10 to 0.15 s |

The machine's load average was 9 to 10 during these runs, so they are upper bounds for it. The
ycash6 prover uses several threads. Restricting the Sapling node to fewer threads
(`RAYON_NUM_THREADS`, run 4, 20 templates each, load average 20 to 35 from other lanes' builds, so
read the minima):

| Threads | Sapling template, minimum / median | Added over the transparent template (minimum) |
|---|---|---|
| default (10 cores) | 0.21 / 0.28 s | 0.15 s |
| 2 | 0.34 / 0.48 s | 0.28 s |
| 1 | 0.74 / 1.13 s | 0.69 s |

**Estimate for the pool host, not a measurement.** The pool host is a `t3a.small`
(the `testnet-pools` deployment): two virtual CPUs that are the two threads of one
2017-generation core, burstable. Its single-thread speed is roughly a quarter of this machine's,
and the second thread adds perhaps a quarter more. From the one-thread figure above that gives
**about 2 to 4 seconds per Sapling coinbase** on that host, and two requests at once take about
twice as long each, because they share one core. No AWS call was in this lane's remit, so this is
arithmetic from a ratio; the first thing 3n's rollout does on the pool host is run
`zcbenchmark createsaplingoutput 10` and replace this paragraph.

What it means: with two Sapling miners and 75-second blocks, each of them works on a void job for
roughly 3 to 8 seconds after every new block, 4 to 10 % of its time, on that host. That is slow
enough to matter and cheap to remove without any reward-only bridge: a pool host with two real
cores of a current generation (for example a `c7a.large`) brings a proof under about half a
second. This note recommends sizing the host, keeping the empty-block bridge off, and deciding
after the host's own measurement. Transparent and post-quantum miners are never affected.

### 6.3 Concurrency

Each call occupies one RPC worker thread for its duration. ycashd has 4 by default
(`-rpcthreads`), and `getblocktemplate` and `submitblock` use the same pool. A pool that fired one
request per shielded miner at once could make a found block wait behind proofs.

- yolo MUST cap its requests in flight (default 2, `--coinbase-concurrency`) and MUST send
  `submitblock` and `getblocktemplate` on connections that are never queued behind them (it
  already separates the template poll from the blocking pool, `yolo/src/poller.rs:98-110`).
- The pool recipe sets `-rpcthreads` to that cap plus 2 or more.
- The node adds no limit of its own: the call is authenticated RPC, like every mining call.

## 7. Errors

Codes and strings are the contract: identical on ycash-dd, ycash6 and kogany, tested on each line
with the same expectations. `<…>` is filled in. A caller matches on the code and on the text
before the first colon.

| # | Code | Message | When |
|---|---|---|---|
| 1 | -8 | `template must be an object with exactly the keys previousblockhash and txids` | parameter 1 is not such an object (a missing key, an extra key, another type) |
| 2 | -8 | `previousblockhash must be 64 hex characters` | |
| 3 | -8 | `txids must be an array of strings of 64 hex characters` | |
| 4 | -8 | `txids has more than 50000 entries` | |
| 5 | -8 | `txids names a transaction twice: <txid>` | |
| 6 | -5 | `Invalid address` | parameter 0 is not a string or does not decode for this network |
| 7 | -5 | `Address type cannot receive a coinbase: <type>` | a valid address of a kind §3.1 does not accept; `<type>` as `z_validateaddress` names it (`sprout`, `unified`, …) |
| 8 | -5 | `Address type cannot receive a coinbase at height <height>: <type>` | `pq` before the Vault upgrade is active at `height`; `sapling` before Heartwood is |
| 9 | -5 | `Address type cannot receive a coinbase on this node: sapling` | kogany only, until it can prove (D-4). The C++ lines never return it. |
| 10 | -1 | `template-stale: previousblockhash is not the tip` | step 3 or step 6 |
| 11 | -1 | `template-stale: transaction is not in the mempool: <txid>` | step 3; the first missing id in the request's order |
| 12 | -1 | `coinbase-does-not-fit: <what>` | step 5; `<what>` is `block size <n> exceeds <limit>` or `sigops <n> exceed <limit>` |
| 13 | -1 | `unsupported: the header commits to the coinbase at height <height>` | NU5 rules active at `height` (§4.4) |
| 14 | -9 | `Ycash is not connected!` | as `getblocktemplate` |
| 15 | -10 | `Ycash is downloading blocks...` | as `getblocktemplate` |
| 16 | -26 | `yellowback-unhealthy: <reason>; restart with -reindex-yellowback` | as `getblocktemplate` |
| 17 | -32603 | `coinbase construction failed: <detail>` | the prover or the signer failed; never expected |

Order of checks: rows 1 to 7 (in that order), then 14 to 16, then 10, 8, 13, 11 and 5 in step 3,
then 17, 12, and 10 again. A wrong number of parameters is each line's usual usage error and is
not part of the contract.

## 8. yolo: paired jobs

### 8.1 Which miner takes which path

| Username | Path |
|---|---|
| transparent (P2PKH, P2SH) | the swap path, unchanged: yolo writes the address's script into `vout[0]` of the stock coinbase |
| post-quantum | the paired path, as the list fixes it (but see D-6) |
| Sapling | the paired path: one `getcoinbasetemplatefor` per template |

**D-6, for the lead architect:** a post-quantum username already works on the swap path, with no
change to yolo or the node (question a, §10 run 2: `validateaddress` returns a `scriptPubKey` for
`rqf…` and `rqs…`, yolo swaps it in, the blocks were accepted and paid the address). The call
would build the same single output, so the two paths pay the same once D-2 holds. Keeping
post-quantum miners on the swap path costs no RPC and no wait at a new block, and lets F-1 and the
demonstration's post-quantum miner run before 3n merges. Putting them on the paired path gives one
rule ("only P2PKH and P2SH are swapped") and makes them independent of the node's `-ydf`. The
call supports both; 3p implements the table above unless the lead architect chooses the swap path
for them, which changes one line of the table and nothing else in this note.

yolo decides the kind from the node's answers at `mining.authorize`: `validateaddress` with a
`scriptPubKey` and `pqscheme` absent means swap; `pqscheme` present means post-quantum (paired, or swap under D-6); otherwise `z_validateaddress` with `isvalid` and `type` `sapling` means
paired; anything else is refused with `Invalid address` as today. Both answers are cached as
today's are (`yolo/src/state.rs`).

### 8.2 The flow for a Sapling miner

A **pair** is one template's transaction set and one coinbase built for exactly that set and one
address. yolo keys it by `(address, previousblockhash, digest of the txid list)`.

1. The poller fetches the stock template as today (every second).
2. When the template's **pair key part** `(previousblockhash, txid list)` or its
   `coinbaseaux.flags` changes, every Sapling miner needs a new pair:
   - **new block** (`previousblockhash` changed): at once. The miner's current job is void and it
     is told nothing new until its pair arrives. No reward-only or lower-amount coinbase is ever
     issued in the meantime (the list's step 6).
   - **new quote** (`flags` changed): at once; the miner keeps its valid current job meanwhile.
   - **changed transaction set only**: no more often than once every 5 seconds per address (the
     node itself rebuilds its template for mempool changes no more often than that,
     `ycash6/src/rpc/mining.cpp:691-692`); the miner keeps its valid current job meanwhile.
3. yolo calls `getcoinbasetemplatefor(address, previousblockhash, txids)` with the cap of §6.3.
   One call per address, not per connection: connections that share an address share the pair.
4. It checks the answer (§8.3). If the template it named is still yolo's current one, it builds
   the job: the stock template's header fields (version, previous hash, the header root, bits,
   `curtime`), the returned coinbase (scriptSig rewritten only as §5.5 allows), the named
   transactions, all of them, in order. It sends `mining.notify` with the clean flag set.
5. If the answer is `template-stale` (row 10 or 11), yolo wakes the poller for a fresh template
   and the cycle starts again from step 2. Any other error: the miner keeps its current job if it
   has a valid one, the error is logged once per address and template, and the next template
   change retries. `Address type cannot receive a coinbase…` at authorize time is an
   `Invalid address` to the miner.
6. A share that meets the block target is submitted with `submitblock` exactly as today.

A miner that authorizes in the middle of a template gets its pair by steps 3 and 4.

`/status` gains, per miner, the payout kind (`p2pkh`, `p2sh`, `pq`, `sapling`) and, for the pool,
counts by kind, the number of pairs waiting for a coinbase and the last coinbase round-trip time.

### 8.3 What yolo checks on every answer

All MUST hold, or the answer is dropped, logged as an error and no job is built from it:

- `previousblockhash` and `height` equal the template's; `txcount` equals the number of ids sent;
- `fees` equals the sum of the template's `transactions[].fee`;
- the coinbase parses, has one input with a null prevout, and the sum of its transparent outputs
  minus `valueBalance` equals the sum of the outputs of the template's own `coinbasetxn` (both are
  subsidy plus fees: measured equal, 625,000,734 on both in run 1);
- `amount` equals that sum minus `fund`.

yolo's coinbase codec (`yolo/src/tx.rs`) refuses a transaction with shielded outputs today. For
this it learns to carry everything after `valueBalance` as opaque bytes; it never parses or
rewrites the shielded part.

`getblocktemplate` in `proposal` mode validates an assembled block without proof of work. 3p's
tests use it on every job they build; production does not need it.

### 8.4 The frozen interface (3p may code against this today)

```rust
/// One answer of getcoinbasetemplatefor (§3.2). Amounts in zatoshi.
#[derive(Debug, Clone, serde::Deserialize)]
pub struct CoinbaseFor {
    pub data: String,
    pub hash: String,
    pub height: u32,
    pub previousblockhash: String,
    pub addresstype: String,
    pub subsidy: u64,
    pub fund: u64,
    pub fees: u64,
    pub amount: u64,
    pub txcount: usize,
    pub flags: String,
    pub sigops: u32,
}

/// Where paired coinbases come from: the node (RpcClient) in production, a stub in tests.
pub trait CoinbaseSource: Send + Sync {
    fn coinbase_for(&self, address: &str, previousblockhash: &str, txids: &[String])
        -> Result<CoinbaseFor, RpcError>;
}
```

`RpcClient` implements it with the JSON-RPC call of §3.1; unknown response keys are ignored (so
`defaultroots` can appear later). `RpcError` carries the node's code and message so §7 can be
matched.

**The stub for 3p, until 3n merges.** A second regtest node, started with
`-mineraddress=<the miner's Sapling address> -minetolocalwallet=0` and connected to the pool's
node, already produces the coinbase this call will return: its `getblocktemplate.coinbasetxn.data`
is a Sapling coinbase for that address, valid on the pool node's template whenever both nodes have
the same tip and the same mempool fees. Run 1 is exactly this and its block was accepted. The stub
`CoinbaseSource` asks that helper node for a template, checks `previousblockhash` and the fee
total against the request (answering `template-stale` otherwise) and fills `CoinbaseFor` from it.
Its limits: one helper node per Sapling address, and the helper applies `-ydf`, so run it with
`-ydf=0`. It is a test fixture only.

## 9. kogany

Same request, same response, same errors, same rules (§3 to §7), under the `ycash` feature, in
`crates/zakura-rpc`. Lane 3k owns the mapping row; what it needs to know:

- **The reference maps directly.** kogany's template transactions carry `miner_fee`
  (`crates/zakura-chain/src/transaction/unmined.rs:360`) and its mempool answers lookups by mined
  id (`crates/zakura-node-services/src/mempool.rs:103`), so step 3 is one mempool request and one
  tip read. kogany keeps no template between calls either, so nothing in §4 needs state.
- **The scriptSig already matches**: with no `extra_coinbase_data`, kogany writes
  `<height> OP_0 <tag>` (`crates/zakura-rpc/src/methods/types/get_block_template.rs:816-826`).
- **The fund output** follows §5.2: required-only, from `ydf_output`'s mandate branch
  (`crates/zakura-rpc/src/methods/types/ycash.rs:356`), never the optional share that 4k makes
  configurable.
- **Post-quantum payout** needs a miner-reward variant that pays an arbitrary 35-byte script
  (kogany's `MinerAddress` has transparent, Sapling, unified and TEX only,
  `get_block_template/miner_address.rs:15-38`). Small.
- **Sapling payout: not possible today** (question b). `CoinbasePlan::new` returns
  `Sapling coinbase construction is not supported` for a Sapling miner address
  (`crates/zakura-rpc/src/methods/types/transaction.rs:217-223`), the builder is given a prover
  that cannot prove (`transaction/no_sapling.rs`), and the node links Sapling verifying keys only
  (`crates/zakura-consensus/Cargo.toml:59`, `pinned-vk-only`). Measured: koganyd `v1.8.0-ycash.beta2` on regtest answers `getblocktemplate` with a 140-byte coinbase for a transparent miner address and with `could not construct coinbase tx: Sapling coinbase construction is not supported; use a unified or transparent miner address` for a Sapling one (§10 run 3). See D-4.
- Proving, when it comes, runs on a blocking thread outside any state service call; the cap of
  §6.3 is the pool's.

## 10. Evidence

Scripts and raw results are in `wt/scratch/b3-n1/` (untracked). Nodes: ycashd `v6.22.0-beta2`
(the released macOS binary) for ycash6; for ycash-dd the build of lane A's worktree (`v4.5.0-bf7328cfc-dirty`: the beta2 tip plus that lane's wallet fee display, nothing in the mining path); koganyd `v1.8.0-ycash.beta2`,
yolo built from `e91154a`. Regtest, own data directories, random port seeds, all stopped.

**Run 1, `exp1.py`: pairing a stock template with another coinbase.** Two nodes, same tip, same
mempool (three fee-paying transactions); node 0 mines to its wallet's transparent address, node 1
to a Sapling address (`-mineraddress`). Heartwood, Canopy and the Ycash upgrade at height 1, Vault
at 103. Identical on both lines unless a cell says otherwise.

| Check | ycash6 | ycash-dd |
|---|---|---|
| header root of the two templates at height 111 | equal (`bea68066…561564b3`) | equal (`d5d72571…78735fae`) |
| fee total; total output of the two coinbases | 735; 625,000,735 and 625,000,735 | the same |
| mempool entry fees equal `transactions[].fee` | yes | yes |
| block = node 0's header fields and transactions + node 1's Sapling coinbase | accepted, `03b3350b…9ea395cb` | accepted, `03100ec3…3389c7e0` |
| the note in the owning wallet | 593,750,735 = subsidy − 5 % + fees (the nodes ran with the default `-ydf`, which today adds the fund output) | the same |
| Sapling coinbase with 9 bytes appended to its scriptSig | accepted | accepted |
| Sapling coinbase with `valueBalance` changed by 1 zatoshi | `bad-sapling-bundle-authorization` | `bad-txns-sapling-binding-signature-invalid` |
| coinbase of an empty template on a block with fee-paying transactions | accepted; 637 zatoshi unclaimed | accepted; 636 unclaimed |
| coinbase of a fee-paying template on an empty block | `bad-cb-amount` | `bad-cb-amount` |
| stock coinbase with `vout[0]` rewritten to a `rqf…` script, and to a `rqs…` script | both accepted, both pay the address | the same |
| `validateaddress` of a Sapling address | `isvalid: false` (`z_validateaddress`: valid, `sapling`) | the same |
| coinbase sizes: P2PKH, post-quantum, Sapling (each with a fund output) | 141, 151, 1,119 bytes | the same |

**Run 2, `exp2_yolo.py`: usernames through yolo as it is (questions a and e).** yolo `e91154a`, no
`--payout`, the Python 48,5 miner, one block per username, ycashd 6.22.0-beta2 with Falcon on.

| Username | Length | Result |
|---|---|---|
| `sm…` (P2PKH) | 35 | authorized; block accepted; `vout[0]` pays it |
| `rqf…` (FN-DSA-512) | 53 | authorized; block accepted; `vout[0]` pays it |
| `rqs…` (SLH-DSA-SHA2-128s) | 53 | authorized; block accepted; `vout[0]` pays it |
| `yregtestsapling1…` | 91 | refused at authorize: `Invalid address` |
| `sm….rig1` | 40 | refused at authorize: `Invalid address` |

**Run 3, `exp3_kogany.py`: kogany and a Sapling miner address (question b).** Quoted in §9.

**Run 4, `exp4_timing.py`: proving time (question d).** §6.2.

**Username lengths and characters (question e).**

| Kind | mainnet | testnet (all profiles) | regtest | Characters |
|---|---|---|---|---|
| P2PKH, P2SH | 35 (`s1…`, `s3…`) | 35 (`sm…`) | 35 | Base58 (digits and letters without `0`, `O`, `I`, `l`) |
| Sapling | 78 (`ys1…`) | **88** (`ytestsapling1…`) | 91 (`yregtestsapling1…`) | lower-case letters and digits (Bech32) |
| post-quantum | 53 (`sqf…`, `sqs…`) | 53 (`tqf…`, `tqs…`) | 53 | Base58 |

So the longest username the demonstration needs is 88 characters, and none contains anything but
ASCII letters and digits. Nothing in yolo's stratum parsing limits them: a line may be 8,192 bytes
(`yolo/src/stratum.rs:122`), the username is taken whole (`:455-499`), the address cache key is
the full string, and only the log shortens strings, at 128 bytes (`:124`). What a mining program
does with an 88-character username is F-1's test; yolo's side is clear.

## 11. Tests each lane owes

**3n (ycash-dd, then ycash6, the same script and expectations):**

1. For each of P2PKH, P2SH, post-quantum FN-DSA, post-quantum SLH-DSA and Sapling: a block made of
   the stock template's header fields and transactions and the returned coinbase is accepted by
   `submitblock` and by a second node, and the address received exactly `subsidy - fund + fees`
   (transparent kinds from the block, Sapling from `z_listunspent` in the owning wallet), with a
   template that has fee-paying transactions and with an empty one.
2. The same at a height where the fund output is required (regtest below height 5 with the Ycash
   upgrade on) and where it is not; and with `-ydf=5` on the node, where the stock coinbase has a
   fund output and the returned one has none.
3. `getblocktemplate`'s reply is byte-identical before and after a series of calls (same tip, same
   mempool, same second), and `longpollid` does not move.
4. Stale: after a new block (row 10); after a named transaction is mined or leaves the mempool
   (row 11); an id that never existed (row 11).
5. No lower amount: an `amount` key, a `fees` key, a third positional parameter are refused; the
   returned `amount` never differs from `subsidy - fund + fees` computed by the test from the
   chain.
6. Every row of §7 that a test can reach (1 to 8, 10, 11, 13 with NU5 on regtest where the line
   has it, 14 to 16).
7. Sixteen calls in parallel for sixteen Sapling addresses while another thread calls
   `getblocktemplate` and `getblockcount`: all succeed, and the node's `cs_main` is not held across
   a proof (the lock-order checker build, and `getblockcount` latency during the run).
8. The scriptSig carries the tag when a quote is set, and `flags` equals the next
   `getblocktemplate`'s `coinbaseaux.flags`.

**3k:** the same script against kogany, with row 9 expected for Sapling until D-4 is built; a
cross-line run in which ycashd accepts a block built from kogany's coinbase and the reverse.

**3p:** on regtest with the 48,5 miner, a mixed pool of three miners (transparent, post-quantum,
Sapling), each finding a block that pays it exactly subsidy plus fees, with fee-paying
transactions in the blocks; usernames of 35, 53 and 91 characters and one with a worker suffix (D-5); a template change in the middle of a job; a `template-stale` answer;
a node with `-ydf=5` (D-2); the checks of §8.3 each tripped by the stub.

## 12. Proposed `docs/mapping.md` rows (the coordinator lands them)

| Where | Row |
|---|---|
| §17 (yolo) | A post-quantum username already works on the swap path: `validateaddress` returns `scriptPubKey` (`20 <key hash> <scheme> c2`, 35 bytes) for `sqf…`/`sqs…` on both C++ lines, and yolo writes it into `vout[0]` (`yolo/src/work.rs:110-118`). A Sapling username does not: `validateaddress` says `isvalid: false` for it, only `z_validateaddress` knows it, and its payout is not a script. Paired jobs (`docs/plans/beta3/getcoinbasetemplatefor.md`) are for Sapling. |
| §17 (yolo) | A coinbase from `getcoinbasetemplatefor` is never run through the `vout[0]` swap and its job never drops transactions at the size limit (`yolo/src/work.rs:131-137`): with a Sapling payout and a required fund output `vout[0]` is the fund, and a dropped transaction leaves the coinbase over the limit consensus allows (`bad-cb-amount`). |
| §19 (the two C++ lines) | `getblocktemplate.coinbasetxn` differs: ycash-dd always prints `ydfpercentage` and `foundersreward` (the value of `vout[1]`, or 0: wrong for a Sapling `-mineraddress`, whose fund output is `vout[0]`; `ycash-dd/src/rpc/mining.cpp:742-743`); ycash6 prints `foundersreward` only while the output is required and has no `ydfpercentage` (`ycash6/src/rpc/mining.cpp:772-782`). A client must not derive the fund rule from these keys alone; `getcoinbasetemplatefor`'s `fund` is the same on both. |
| §19 | A Sapling coinbase whose binding signature fails is `bad-txns-sapling-binding-signature-invalid` on ycash-dd and `bad-sapling-bundle-authorization` on ycash6 (the 6.x bundle verifier). Same verdict, different reason string. |
| §19 | Both assemblers reserve 1,000 bytes for header and coinbase (`ycash6/src/miner.cpp:310-317`, `ycash-dd/src/miner.cpp:486`); a 192,7 header is 1,487 bytes and a Sapling coinbase 1,119. A template within about 600 bytes of `MAX_BLOCK_SIZE` cannot take a Sapling coinbase; `getcoinbasetemplatefor` refuses (`coinbase-does-not-fit`) rather than the assembler changing. |
| §24 (kogany) | kogany cannot build a Sapling coinbase: `CoinbasePlan::new` refuses a Sapling miner address (`crates/zakura-rpc/src/methods/types/transaction.rs:217-223`), the builder's prover is `NoSaplingProver` (`transaction/no_sapling.rs`), and only verifying keys are linked (`crates/zakura-consensus/Cargo.toml:59`). ycashd builds one for `-mineraddress=<Sapling>` (`ycash6/src/miner.cpp:237-250`). Until kogany gains a prover, its `getcoinbasetemplatefor` answers a Sapling address with `Address type cannot receive a coinbase on this node: sapling`. |
| §24 | kogany's `MinerAddress` has no post-quantum variant (`get_block_template/miner_address.rs:15-38`); a post-quantum payout is a 35-byte script output and needs one. |
