# Innovation acknowledgements

**Ycash Yellowback (YED)** exists because the DigiByte team showed that a decentralized,
UTXO-native digital dollar is buildable on a proof-of-work chain with no company, no bank, no
custodian and no smart-contract VM. This document records that debt plainly, names the specific
DigiDollar innovations we learned from, and states — just as plainly — where Yellowback departs
from them and why.

Line citations are to the pinned reference trees: `ref/digibyte` @ **v9.26.5** (`05b50e229d`) and
`ref/ycash` @ **v4.5.0** (`624c12814`). Run `make status` before trusting them. The normative
protocol is [`spec/yellowback-spec.md`](spec/yellowback-spec.md); the design rationale is
[`why-miner-enforced.md`](why-miner-enforced.md); the mechanism-level crosswalk between the two
codebases is [`mapping.md`](mapping.md).

---

## 1. Thank you to the DigiByte team

DigiDollar is the first working demonstration we know of that a UTXO chain with no covenants, no
account model and no virtual machine can carry a collateral-backed dollar where **the user never
hands anyone their keys**. Before DigiDollar, the answer to "how do you do a stablecoin without a
custodian?" was "you need Ethereum, or you need a company". DigiByte answered it differently, in
C++, on a Bitcoin-derived codebase, and shipped the whole stack — consensus rules, oracle network,
wallet, GUI, RPC surface and test suite.

That answer is the reason this project had a starting point instead of a blank page. Several of the
hardest questions in Yellowback's design were questions we did not have to ask, because DigiDollar
had already asked them and published an answer we could read, test and argue with.

We are also grateful for how it was published. The DigiByte DigiDollar work is open source with
unusually thorough design documentation — architecture documents validated against the codebase,
explainers written for non-implementers, flowcharts, minimum-amount analyses, oracle specifications
and a repository map. Verbatim copies of the ones we leaned on hardest are kept under
[`spec/upstream-digibyte/`](spec/upstream-digibyte/) so that anyone auditing Yellowback can read
the reference design in its own words rather than through ours.

## 2. The specific DigiDollar innovations we learned from

These are the ideas we credit to DigiByte. Each is a design decision that survived into Yellowback
in some form, even where the mechanism underneath it had to be rebuilt.

- **The time-locked self-custodial vault as the primitive.** Lock the native coin in a
  time-locked output *you* control, receive a dollar-denominated token against it, and burn the
  token to unlock the coin. The collateral never moves to anyone else. DigiByte's framing of this
  — "the gold never leaves your vault" — is the framing Yellowback inherited wholesale.
  (`ref/digibyte/src/digidollar/txbuilder.cpp`, `validation.cpp`)

- **Term-graded over-collateralization.** Longer locks earn lower collateral requirements, because
  a longer lock absorbs more volatility. DigiByte's ten canonical lock tiers (30 days at 500 %
  down to 10 years at 200 %) and its published analysis of when each tier goes underwater
  (`spec/upstream-digibyte/4_tier_collateral.md`) is the direct ancestor of Yellowback's three
  term classes: A, 30–90 days at 500 %; B, 90–365 days at 400 %; C, 1–5 years at 300 %
  (plan §3.1). We chose fewer, wider classes; the *idea* that the ratio is a function of the term
  is DigiByte's.

- **Canonical tiers instead of free-form terms.** Mint payloads must declare a tier, and
  validation accepts only the canonical window for the declared tier. This closes a whole family of
  under-locking attacks with an integer comparison, and it is why Yellowback's term classes are
  block ranges rather than user-chosen durations (V19).

- **Layered crisis controls rather than a liquidation engine.** DigiByte's Dynamic Collateral
  Adjustment (`src/consensus/dca.cpp`), Emergency Redemption Ratio (`src/consensus/err.cpp`) and
  volatility controls (`src/consensus/volatility.cpp`) protect the peg by raising requirements as
  system health degrades — and ERR notably takes its correction as extra token burn rather than as
  a haircut on the user's collateral. Yellowback's volatility multiplier, global-ratio halt,
  divergence halt and supply cap (plan §3.7) are in that tradition: bounded, integer, automatic,
  and never a keeper-run auction that can cascade.

- **Integer-only economics.** Every ratio, price and threshold in DigiDollar's protection systems
  is computed in integer arithmetic (`__int128` where needed) precisely because a stablecoin's
  rules must be evaluated identically by every node. Yellowback follows this without deviation:
  `CENT`, `MICRO_USD`, basis points, `arith_uint256`, and a determinism requirement written into
  the spec (plan §3.10).

- **Network-wide health as a first-class, queryable object.** DigiDollar tracks total collateral,
  total supply, per-tier and aggregate collateralization, and exposes them
  (`src/digidollar/health.cpp`, `src/index/digidollarstatsindex.*`). Yellowback's rebuildable
  overlay index and `yed_getinfo` / `yed_getvault` / `yed_listminers` surface exist because
  DigiByte demonstrated that a stablecoin without a visible balance sheet is unauditable.

- **Deterministic on-chain pricing at all.** DigiDollar's MuSig2 oracle network — operators
  aggregating exchange medians off-chain, running a signing round, and placing one aggregate
  BIP-340 signature bundle in the coinbase for block validation
  (`spec/upstream-digibyte/DIGIDOLLAR_ORACLE_EXPLAINER.md`) — is a genuinely hard piece of
  engineering. Yellowback does not use it, for reasons in §3, but the structural insight we kept is
  DigiByte's: **the price must arrive in the coinbase, so that block validation can read it
  without any node making a network call.**

- **Minimums, maximums and dust discipline.** Minimum mint, maximum mint, minimum output, and the
  token-as-dust-output-plus-`OP_RETURN`-payload representation
  (`ref/digibyte/src/digidollar/txbuilder.cpp:407-418`) are DigiByte's, and Yellowback's are the
  same shape with parameters scaled to Ycash's much smaller liquidity ($100 / $10,000 rather than
  $100 / $100,000).

- **Graceful degradation in block assembly.** DigiDollar strips failing token transactions from the
  template rather than letting them block a block (`src/node/miner.cpp:707-744`). Yellowback's
  template filter is built on the same principle, and its fail-open posture and kill switch
  (V13, V14) generalise it: loss of price or participation must end in "no new mints", never in
  "a minter cannot redeem".

Where our code borrowed shape as well as ideas, we say so in the commit messages and in
[`mapping.md`](mapping.md). We have not hidden the lineage, and we do not want to.

## 3. Where Yellowback goes its own way — and why

Yellowback is **not** a port of DigiDollar. It could not have been, and we would not have wanted it
to be. Two independent forces made it a different protocol: the codebase, and the principles.

### 3.1 The codebase made a port impossible

DigiByte v9.26.5 is Bitcoin Core ~v26/28 with SegWit, Taproot and Tapscript. Ycash v4.5.0 is
Zcash 4.5 over Bitcoin Core ~0.11/0.12 with **none of them**, plus two shielded pools, ZIP-243
sighash bound to a `consensusBranchId`, a transaction `nVersion` pinned to 4, a `CCoins` UTXO
model, and monolithic validation in `src/main.cpp`. The full table is [`mapping.md`](mapping.md) §0–§9.

The sharpest example, and the reason this workspace has the rules it has: DigiDollar's opcodes
(0xbb–0xbf) get their soft-fork safety from BIP342 `OP_SUCCESSx` under
`sigversion == SigVersion::TAPSCRIPT`. On Ycash those same bytes hit
`default: return set_error(serror, SCRIPT_ERR_BAD_OPCODE)`
(`ref/ycash/src/script/interpreter.cpp:942`), and Ycash's `SigVersion` enum means something else
entirely — a sighash algorithm, not a script version. A verbatim transplant compiles and is
consensus-dead. DigiByte had a cheap, safe extension mechanism available; Ycash's only activation
mechanism is a height-gated network upgrade with a new branch ID. Nothing about the enforcement
layer could be copied. It had to be re-derived from first principles for a chain that has no
covenants and no soft-fork hook.

### 3.2 The principles made a different protocol the right answer

Ycash's core commitments are **decentralization, self-sovereignty and risk aversion** — the last of
these expressed as a shielded pool whose soundness rests on consensus code few people fully
understand, maintained by a small, deliberately conservative team. Those commitments are not
constraints we worked around; they are the design inputs, and they pointed somewhere DigiDollar did
not go.

**Self-sovereignty: no roster, no quorum, no gatekeeper on redemption.** DigiDollar's price is
produced by a 35-slot oracle roster with a 7-signature MuSig2 quorum. We built a federation
prototype in that tradition first — 5-of-9 operators co-signing releases and prices — and then
retired it (plan §0, 2026-09-10) precisely because it failed this test. Any committee design means
redemption has a counterparty: `k` operators must be online, reachable and willing; an outage
pauses redemptions and a veto blocks them; a colluding quorum holds a release key to every vault;
and the price is whatever the committee signs, so manipulation costs the price of corrupting `k`
people. A standing institution with keys, rotation and ceremonies also has to exist and be
maintained for as long as one vault is open. For Ycash, that is the wrong trade at any efficiency.

**Decentralization: the enforcer is hashpower, and it is permissionless.** Yellowback's answer is
that on a proof-of-work chain, the only party who can refuse a transaction without a consensus
change is the miner. So the one rule Ycash script cannot express — *release this collateral only if
the matching YED is burned* — is handed to mining pools. Pools running the Yellowback module
publish a YEC/USD quote in each coinbase, keep rule-breaking transactions out of their own blocks,
and, once three quarters of blocks signal, refuse to build on a block that releases collateral
without the burn. There is no roster to join and no slot to be granted: **any pool that mines a
block can quote, and is paid for quoting** — an enforcement fee of `max(0.5 YEC, 0.25 % of
collateral)` to a pool that quoted recently, earned in proportion to blocks quoted, so a small pool
that quotes every block earns its share (V10, FEE-W). The price becomes rolling medians of 96, 576
and 2,016 blocks, fail-closed below a minimum fill (V16, L9), so moving it costs a sustained
majority of quote-tagged blocks over hours to days rather than the corruption of a fixed set of
named operators. Nobody holds a key to anyone's collateral but the minter. Nobody sits between a
minter and their redemption. The price comes from hashpower, not from a committee.

**Risk aversion: the smallest footprint that works, in writing.** DigiDollar took the consensus
route DigiByte's codebase made cheap: new opcodes, a reserved `OP_CHECKPRICE`, new consensus
modules, BIP9 activation, a new address type. Yellowback deliberately took the opposite path. It
adds **no opcode, no branch ID, no network upgrade, and no release the Ycash team must ship**. The
enforcement rule is about 50 lines inside the `ConnectBlock` window of the patched node plus the
miner, all inert without `-yellowback`, with zero lines in `consensus/`, `script/`, `primitives/`
or `pow/` (plan §4.1). Vaults are ordinary P2SH with `CHECKLOCKTIMEVERIFY`, which Ycash already
validates in every block (`ref/ycash/src/main.cpp:2931`). YED tokens are ordinary transparent
P2PKH outputs with one 80-byte `OP_RETURN` payload that Ycash already relays
(`ref/ycash/src/policy/policy.cpp:52,121-122`). Addresses are plain Base58Check P2PKH with new
version bytes and no `chainparams.cpp` edit. The price tag rides in the never-assigned
`COINBASE_FLAGS` global, so the internal miner, regtest `generate` and `getblocktemplate` all emit
it with no new plumbing (V4, V5) — and a coinbase tag never makes a block invalid to a stock node.
Every block an enforcing pool mines is valid to an unpatched Ycash node, and an unpatched node
never rejects anything it accepts today.

This is a soft fork in effect and not a consensus change in code, and the project says so in those
words rather than softening either half (`why-miner-enforced.md` §1). The costs of that choice are
tabulated, not elided: §5 of that document lists every trade-off with a plan citation bounding it,
including the ones we cannot remove. That accounting is itself a product of the risk-aversion
principle — a conservative team is owed the liabilities, not just the features.

**Deliberate divergences, briefly.** Alongside the above: no oracle daemon, no MuSig2, no Schnorr
(absent from Ycash entirely); three term classes rather than ten tiers; a permissionless
claim path where YED holders take collateral from abandoned underwater vaults by burning YED after
a 30-day grace at a slow-window price, with no keeper, auction or custodian (plan §3.8);
mint/redeem caps scaled to Ycash's liquidity; a single-clause abandonment predicate so every
release answers alike (L10, L12); an enforcement sunset and parameter-set versioning so no two
releases can ever both enforce at one height (L8, K10); an explicit kill switch and work valve
(V13, L7); and a wallet that reaches all of it over JSON-RPC — YecWallet is a separate Qt
application driving `ycashd`, so DigiByte's in-process `src/qt/digidollar*` widgets are a
behavioural reference and never source ([`mapping.md`](mapping.md) §12).

## 4. The stance, stated once

Yellowback is an independent protocol, designed for Ycash, by people who read DigiByte's work
carefully and admire it. We take the inspiration seriously enough to be explicit about it, and we
take Ycash's principles seriously enough to have thrown away a working federation prototype that
would have been faster to ship and closer to the reference design.

Two projects, two chains, two threat models, two answers to the same good question. DigiByte proved
the question had an answer. Ycash answered it for a chain with no covenants, no Tapscript, a
shielded pool to protect, and a community whose first commitment is that nobody — no company, no
committee, no roster, and no developer — should stand between a person and their own money.

Thank you to the DigiByte team for going first.

---

*Corrections welcome.* If anything in §2 or §3 misstates DigiDollar's design, it is an error on our
part and not a characterisation we wish to keep: open an issue against the Yellowback fork and it
will be fixed here and in [`mapping.md`](mapping.md).
