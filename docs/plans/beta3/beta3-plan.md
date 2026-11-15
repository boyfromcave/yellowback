# Beta3 plan: 6.22.0-beta3 and a pool that pays shielded miners

**Revision 2 (2026-11-15). Proposal for the Yellowback lead architect; not started.**
Revision 2 adds two items at the lead architect's request: a lightwalletd deployment for the fast
testnet (17) and the ycash.team landing page (18).
Source: the beta3 list refined with the lead architect on 2026-11-13..15 (18 requested items, 2
process requirements). This plan orders that work for a team of agents. Its status block (§2) is
the record once the run starts.

## 1. What success is

Beta3 is done when both of these are true:

1. **The beta3 releases are published** as one release train (`releases/v6.22.0-beta3.yaml`):
   ycashd `v6.22.0-beta3` (ycash6), `vault-params/v6.22.0-beta3` (ycash-dd), koganyd
   `v1.8.0-ycash.beta3`, and the clients at their train commits (yew with yewd, yolo, YecWallet's
   first real release, lightwalletd, chain-viz, x402-ycash, hawkeye). Every one of the 18 items
   is in it or explicitly dropped by the lead architect.
2. **The yolo pool on the fast testnet pays several unrelated miners in full, at their own
   addresses, shielded ones included.** At least **four rented GPU miners at the same time**, each
   with a different payout address: one transparent (`sm…`), **two or more Sapling**
   (`ytestsapling…`) and one post-quantum (`tqf…` or `tqs…`). Each finds at least one block whose
   coinbase pays that miner's own address the block reward plus every fee in the block, with no
   development-fund deduction. Evidence is recorded in the run (§9).

The second criterion is the end-to-end proof of items 3, 4 and 5 and needs one thing the list
did not name: the miner fleet tooling must start several miners with different payout addresses
of three kinds (chunk F-1).

Rules that hold throughout:

- **A miner who finds a block is rewarded in full**: reward plus all ordinary fees. No design in
  this run lets a pool pay less.
- **Reference order: ycash-dd → ycash6 → kogany**, generally. A shared change is designed and
  first implemented on ycash-dd, ported to ycash6 (the release line), then matched in kogany, and
  the three are tested against each other. Exceptions are named where a line lacks the feature.
- **No AI attribution anywhere** (AGENTS.md rule 8): commits, merge commits, PR titles, bodies
  and comments, code comments and docs. Commits are authored and committed as
  `boyfromcave <57612331+boyfromcave@users.noreply.github.com>`.

## 2. Status block

Filled in by the coordinator during the run. `[ ]` open, `[~]` in progress, `[x]` merged,
`[-]` dropped by the lead architect.

| Chunk | What | dd | y6 | kogany | clients / infra |
|---|---|---|---|---|---|
| P-1 | Qualification harness out of the node repository | n/a | [ ] | n/a | [ ] workspace |
| 15 | Rust toolchain pinned | n/a | n/a | [ ] | [ ] common fork |
| 1 | `gettransaction` fee display | [ ] local branch | [ ] local branch | n/a | — |
| 6 | Sender address on post-quantum spends; kogany input values, addresses, block fee | [ ] | [ ] | [ ] | — |
| 4 | Development-fund mining default 0 % | [ ] | [ ] | [ ] | [ ] yolo README |
| 5 | Fast testnet: end the fund mandate (consensus gate) | [ ] | [ ] | [ ] | — |
| 3 | `getcoinbasetemplatefor` + yolo paired jobs | [ ] | [ ] | [ ] | [ ] yolo |
| 2 | Chain value pools by address type | [ ] | [ ] | [ ] | [ ] chain-viz, lightwalletd, YecWallet |
| 7 | koganyd accepts 1.0 batch requests | n/a | n/a | [ ] | — |
| 11 | kogany per-address counts, chain transaction count | n/a | n/a | [ ] | — |
| 12 | Reorganisation depth and check order (consensus gate) | n/a | n/a | [ ] | — |
| 8 | Snapshot restore must not fail silently | n/a | [ ] | n/a | — |
| 9 | Snapshot bundles above 50 GB | n/a | [ ] restorer | n/a | [ ] ycash-infra, site |
| 10 | Wallet fees on shielded sends | n/a | n/a | n/a | [ ] yew (local branch) |
| 16 | Mobile wallet fee warning | n/a | n/a | n/a | [ ] yew (local branch) |
| 14 | yewd gaps against ycashd's wallet | n/a | n/a | n/a | [ ] yew |
| 13 | YecWallet release; macOS first-run instructions | n/a | n/a | n/a | [ ] yecwallet-dd, site |
| 17 | lightwalletd for the fast testnet at `fastnet-lightwallet.ycash.team` | n/a | n/a | n/a | [ ] ycash-infra, ycash-ops, yew |
| 18 | The ycash.team landing page | n/a | n/a | n/a | [ ] new site repo, ycash-ops |
| F-1 | Miner fleet: several miners, three address kinds | n/a | n/a | n/a | [ ] ycash-infra, ycash-ops |
| R-1 | RPC contract version and clients | [ ] | [ ] | [ ] | [ ] all clients |
| Q | Qualification (incl. P-2) | [ ] | [ ] | [ ] | [ ] |
| T | Testnet rollout, mandate-end height crossed | — | — | — | [ ] |
| D | Pool demonstration: four miners | — | — | — | [ ] |
| REL | Tags, releases, site | [ ] | [ ] | [ ] | [ ] |

## 3. Decisions the lead architect must take before the run starts

| # | Decision | Recommendation |
|---|---|---|
| B3-D1 | Merge authority for this run (beta2's was for beta2 only) | As in beta2: the coordinator merges after an independent agent review, its own review and green CI |
| B3-D2 | Who pushes tags and publishes | The lead architect, unless delegated again; release signing (minisign) is the lead architect's in any case |
| B3-D3 | Where the qualification harness lives (P-1) | The workspace repository, under `qualify/`, beside `releases/` (public repository, so its runs are free; the train file already names every commit) |
| B3-D4 | The fast testnet's mandate-end height (item 5) | The fast-testnet tip when the release candidate is cut, plus 400 blocks; compiled into rc1 |
| B3-D5 | The `rpcversion` step | 10, once, at integration (R-1), covering every new call and field of this run |
| B3-D6 | Four payout addresses for the demonstration | Fresh addresses from the lead architect's own fast-testnet wallet (keys stay local; only addresses go in the fleet file) |
| B3-D7 | Start | "go" on Wave 0 |
| B3-D8 | Where lightwalletd runs (item 17) | Its own small host in the pool-host pattern (own address, role and environment), not on the explorer host: the explorer host's 4 GiB is already budgeted, and a wallet backend and an explorer should not fail together |
| B3-D9 | Whether the web wallet is served by this deployment | Not in the first cut: the app's native gRPC over TLS first; the web wallet's gRPC-web listener as a second step of the same item |
| B3-D10 | The landing page's open choices (item 18) | Where the YEW, YecWallet, Yolo, x402 and lightwalletd tiles lead (a one-screen page per product, not a source repository); whether a newcomer page keeps the builder tiles; the one-line tagline; the tile order |

Already decided and recorded in the list: the fund default 0 % with `-ydf` opt-in on all lines;
testnet and mainnet behave the same; exact-amount coinbases only; no Apple Developer signing;
fresh mainnet snapshots wait; the exact-claim consensus rule is not requested.

## 4. How the team works

**Coordinator** (the lead session): owns this plan's status block, `wt/BRIEFING-beta3.md` (the
rules below, given to every agent) and `wt/COORDINATION-beta3.md` (who holds which lane and
which files), starts lanes, arranges reviews, merges under B3-D1, reports to the lead architect
with a CPO table (percent and red/yellow/green) on request.

**Agents:** model opus; effort medium, **high for anything under the consensus review gate or
that moves value** (items 2, 3, 5, 12, the coinbase path of item 4). One agent per lane; a lane
owns a set of files, and two lanes never edit the same file at once (§6 names the collisions).
Hand off at about 450K tokens of context through `wt/handoff/B3-<lane>.md`.

**Rules for every agent** (the briefing repeats them):

- Work in `wt/b3-<lane>` on a branch `up/b3-<topic>` cut from a freshly fetched
  `origin/upgrade/vault`; PRs target `upgrade/vault` (ycash-ops: `main`). Never commit to
  `-legacy`, `main`, `vaults/kogany-compat` or any record branch. No force push, no remote branch
  deletion, no tags.
- No AI attribution; the configured git identity only. The merge commit message is written by
  whoever merges.
- Search with `git -C <repo> grep`. Python from the workspace `.venv` only. `ref/` is read-only.
  `env -u GH_TOKEN gh …` for GitHub.
- Rule 4's four-part check in the PR body for any ported or shared change; rule 5's mapping row
  for every new mismatch between the lines; Yellowback is the system, YED the unit.
- Consensus files (`src/consensus/`, `src/script/`, `main.cpp`, `src/primitives/`, and kogany's
  consensus crates) change only through the consensus review gate: two reviews independent of
  the author. Nothing is tidied in passing.
- **A shared change is one change on every line**: the ycash-dd PR and its ycash6 twin are opened
  as a pair, and no CI run is started that must fail for lack of its twin.
- CI runners are scarce: one push when the change is ready and checked locally; cancel
  superseded runs; no ad hoc full-tier dispatches; no job that sleeps or polls.
- A worktree is trusted only after fetch, `HEAD` = the remote tip, and a clean rebuild.
- New crate versions that cargo-vet refuses are admitted by trusting the publisher, never by an
  exemption an agent wrote.
- Never stop, restart or reconfigure a running local node or the live hosts; chain data lives
  outside `wt/`; no AWS call and no workflow dispatch unless the brief says so.
- Report in under 250 words: PR URLs, what was tested and how, what is uncertain.

**Reviews:** every PR gets one independent agent review before merge; gate PRs get two; the
coordinator reads each diff itself. A reviewer is given the code, not the author's conclusion.

## 5. The order of work

Six waves. Inside a wave, lanes run in parallel; a lane's chunks run in the order shown. A wave
does not have to finish before the next starts: a chunk starts as soon as what it depends on
(the "after" column) is merged.

```
Wave 0  groundwork ──────────────► P-1 harness │ 15 toolchain │ design notes │ push the local branches
Wave 1  ycash-dd reference ──────► 6 │ 4 → 5 → 3(node) │ 2          kogany-only: 7 → 11 │ 12
Wave 2  ycash6 ports ────────────► the twin of each Wave 1 PR        clients: 10,16 │ 14 │ 13 │ 8 → 9 │ F-1
Wave 3  kogany matches ──────────► 6k │ 4k → 5k → 3k │ 2k             yolo: 3(pool)
Wave 4  integration ─────────────► R-1 rpcversion + clients │ release notes │ version bumps
Wave 5  qualify, roll out, show ─► Q (with P-2) → T testnet → D four miners → REL tags
```

### Wave 0: groundwork (first; everything else waits for P-1 only where it says so)

| Chunk | Lane | What | After | Size |
|---|---|---|---|---|
| P-1 | harness | **Important process change.** Move `qa/test_yellowback_rc_qualify.py` and `.github/workflows/rc-qualify.yml` out of ycash6 to the home chosen in B3-D3. The harness takes the node commits from the train file and records its own commit in the run's result; a harness fix never moves a node's head. Fold in the two fixes left from ycash6 #114 (open `ycash.conf` with "w"; the kogany wait fails fast on a dead node). ycash6 keeps a pointer in `doc/yellowback-release.md`. | B3-D3 | M |
| 15 | k-tools | Pin kogany's Rust toolchain in `rust-toolchain.toml` and in every workflow that installs one; the same in `zakura-common-ycash`; a short "how to bump" note. | — | S |
| W0-a | coord | `wt/BRIEFING-beta3.md`, `wt/COORDINATION-beta3.md`, the skeleton `releases/v6.22.0-beta3.yaml`. | B3-D1..D10 | S |
| W0-b | fees | Push the work already done locally and open PRs: item 1 (`up/b3-gettransaction-fee` in ycash-dd and ycash6, `wt/handoff/B3-FEE-DISPLAY.md`) and yew's `up/b3-fees-and-guards` (items 10 and 16 in part, `wt/handoff/B3-YEW-FEES.md`). Rebase by merge onto today's `upgrade/vault`, re-run their tests, then review. | — | S |
| N-1 | design | **Design note for item 3** (`docs/plans/beta3/getcoinbasetemplatefor.md`): the call's exact request and response; how a caller names the template it holds (so the node derives the exact amount and refuses a stale reference); what the coinbase carries (quote tag; fund output only where consensus requires it); proving outside `cs_main`; errors. Measure the shielded coinbase proving time on a seed-class host and on this Mac. Answer three questions with tests, not reading: does a post-quantum username already work through yolo's swap path; can kogany build a shielded coinbase today; is the header root independent of the coinbase on every Ycash network at every height that matters. | — | M |
| N-2 | design | **Design note for item 2** (`value-pools.md`): the entries and their names (matching the wallet's `transparent_ecc`, `transparent_pq`, `pq_by_scheme`), where vault-locked and YED-carrying value falls, how the existing order `[0]` transparent, `[1]` sprout, `[2]` sapling is kept (Inzyght reads by position), the block-index field and the reindex or migration, the cross-line check. | — | M |
| N-3 | design | **Design note for item 9** (`bundle-parts.md`): the manifest and `SHA256SUMS` shape for a bundle in parts under 50 GB, how the restorer streams parts into one tar, how the snapshots page shows it, backward compatibility with one-file bundles; measure whether zstd alone would buy enough. | — | S |
| N-4 | design | **Decision note for item 12** (`reorg-parity.md`): ycashd's behaviour is the reference (a reorganisation deeper than 99 blocks shuts the node down); what kogany does at 100 and at 1,000, the check-order and ban-score differences from `wt/handoff/KG-CONSENSUS-SWEEP.md` (F10 and its neighbours), the value and behaviour proposed for each, and the test that proves parity. | — | S |

N-1..N-4 are read-only and run in parallel with everything in Wave 0. Each note is reviewed by
the coordinator and, for N-1 and N-4, approved by the lead architect before its code starts.

### Wave 1: ycash-dd, the reference (and the work that exists only in kogany)

Four node lanes on ycash-dd. Lanes B, C and D touch different files; where they meet
(`src/rpc/blockchain.cpp`, the RPC docs) the coordinator sequences the merges.

| Chunk | Lane | What | After | Gate | Size |
|---|---|---|---|---|---|
| 1 | A fees | Review and merge the pushed fee-display branch (W0-b). | W0-b | — | S |
| 6 | B rpc | `vin[].address` for an input that spends a post-quantum output, in `getrawtransaction 1`, `getblock 2`, `getblockdeltas` (`src/rpc/rawtransaction.cpp`, `src/rpc/blockchain.cpp`; reuse the names map the `getaddress*` calls use, `src/rpc/misc.cpp`). An rpc-test with an FN-DSA and an SLH-DSA spend. | — | — | M |
| 4 | C mining | `DEFAULT_YDF_FEE_PERCENTAGE` 5 → 0 (`src/consensus/consensus.h`; miner and init use it); `-ydf=<n>` help text; `getblocksubsidy` and the metrics screen report the configured share. Test: default pays nothing past the mandate, `-ydf=5` pays 5 %, the mandate period is unchanged. | — | — (a constant in a consensus header read only by the miner: one extra review) | S |
| 5 | C mining | The fast profile gets its own `nYdfMandateEndHeight` (B3-D4); the default testnet value and the slow and legacy profiles are untouched. Tests: a block without the fund output is rejected one block before the height and accepted at it; a block with it stays valid after. | 4 | **two reviews** | S |
| 3n | C mining | `getcoinbasetemplatefor` as N-1 specifies (`src/rpc/mining.cpp`, `src/miner.cpp`): stateless; the amount derived from the node's template; transparent, Sapling and post-quantum payout addresses; proving outside `cs_main`. `getblocktemplate` and `submitblock` untouched (a test asserts the stock template is byte-identical before and after). Tests: a block assembled from the stock template and a returned coinbase is accepted for each address kind and pays exactly subsidy plus fees; a stale template reference is refused; no lower amount can be requested. | 4, 5, N-1 | one review plus the coordinator's (mining path) | L |
| 2 | D index | Value pools by type as N-2 specifies (chain index, `getblockchaininfo`, `getblock`). Touches `main.cpp` / `chain.h`. Reindex or migration test; totals equal the old `transparent` entry. | N-2 | **two reviews** | L |

Kogany-only work starts now too, because it depends on nothing above:

| Chunk | Lane | What | After | Gate | Size |
|---|---|---|---|---|---|
| 7 | K rpc | Accept JSON-RPC 1.0-style batch members as ycashd does (`crates/zakura-rpc`); a test with the exact batch Inzyght sends (`wt/handoff/EXPLORER-KOGANY-FASTNET.md`). | 15 | — | S |
| 11 | K rpc | `getaddressfirstlastheight`; `txcount` in `getaddressbalance`; `transactions` in `getblockchaininfo`; `commitments` no longer 0. Parity tests against ycashd. | 7 | — | M |
| 12 | K consensus | Reorganisation depth and check order as N-4 decides, under the `ycash` feature; a cross-line test for each difference. | N-4, 15 | **two reviews** | M |

### Wave 2: ycash6, the release line (and the clients, which wait for no node change)

For every Wave 1 node chunk, its **twin on ycash6** is written as soon as the ycash-dd PR is
approved, by the same lane, and the pair merges together: 1, 6, 4, 5, 3n, 2. ycash6 specifics:
item 6 also covers the fields only ycash6 has (`blockfee`'s inputs are unaffected); item 2 also
covers `chainSupply` / `valuePools` in `getblock` (fields ycash-dd does not have); item 3's proving
uses ycash6's Rust prover. The cross-line checkers must pass on the pair.

Client and tooling lanes run alongside from the start of the run; none needs a node change:

| Chunk | Lane | What | After | Size |
|---|---|---|---|---|
| 10 | W fees | One fee rule for the app, the web wallet and yewd, equal to the node's for each transaction shape (the local branch covers the app's Sapling fee; add the web wallet's 10,000 / 15,000 zat shapes and yewd); a test per shape against ycashd's own figure. | W0-b | M |
| 16 | W fees | The fee warning compares against the fee the node would charge for that shape, with an absolute floor (the local branch has the price-only case); wording. | 10 | S |
| 14 | Y yewd | Close the gaps in `wt/handoff/KG-YEWD-VAULT-PARITY.md`: watch-only imports and `importaddress`; `z_mergetoaddress` from post-quantum; funding change in `gettransaction` details; the vault lock that leaves a coin locked; help text; the harness's port collisions and per-file-wallet emulation. Each gap gets a parity test that passes on ycashd first. | — | L |
| 13 | G wallet | YecWallet: a tag-driven release workflow, macOS in CI, `version.h` to the release version, the bundled ycashd at the train commit; a build check that Apple Silicon binaries carry the linker's ad-hoc signature. No Apple signing. First-run instructions for macOS on the site's download page and in the release notes, with the project's own signature checks beside the download. | — | M |
| 8 | S restore | `ycash-bootstrap`'s import node ignores peers whatever `ycash.conf` says; a refused restore exits non-zero and leaves a marker the entrypoint will not start past; the missing-`.minisig` case accepts 403 as "absent" for a bucket that is not listable. A test that reproduces the silent failure first (ycash6 `contrib/bootstrap`, `contrib/docker/ycashd`). | — | M |
| 9 | S restore | Bundles in parts as N-3 specifies: `ycash-infra/bundles/state` (`FORMAT.md`, `verify.py`, `mainnet/snapshot.py`, `publish-s3.sh`), `ycash-bootstrap`, and the snapshots page in `kogany-site`. A restore test from a small bundle split into three parts. | 8, N-3 | M |
| F-1 | F fleet | **Several miners with different payout addresses.** Today the fleet file has one `payout` per network and accepts only a transparent address (`ycash-infra/scripts/vast-fleet.py`, `PAYOUT_RE`; the miner container's `PAYOUT`). Change: a per-network list of payouts, one per miner, cycling by miner index; accept transparent, Sapling and post-quantum address forms for the network; `burst` takes the list; `status` and `logs` show each miner's payout kind and its accepted-share count; the miner image passes the address as the stratum username unchanged (check miniZ accepts a 78-character Sapling username and a post-quantum one; if it truncates, say so and find the workaround). ycash-ops: `miners/fleet.json` and the `miners` workflow inputs. | N-1's username answer | M |
| 17 | L lightwallet | **lightwalletd for the fast testnet, deployed like the pool and the explorer.** ycash-infra: the seeds module gains a `lightwallet` block beside `pool` and `explorer` (a node with `-txindex -insightexplorer -experimentalfeatures`, which lightwalletd's address calls need; the `lightwalletd-dd` image with `--yellowback`; a proxy that terminates TLS and passes gRPC through; automatic certificate; nothing else public; RPC on the host's internal network only; memory limits; `status` reports the server's height and its `GetLightdInfo`); an image workflow for `lightwalletd-dd` in the `yolo-image.yml` pattern (public image, pinned by digest, with provenance). ycash-ops: roots `testnet-lightwallet/{ips,nodes}`, a deploy layer `lightwallet` with its own role (`deploy-testnet-lightwallet`) and environment, the layer policy extended to four layers (and the older gap toward the Kubernetes layer's machines closed in the same re-put), docs, a CloudShell runbook for the lead architect. yew: the fast testnet's server in the testnet default list (it is empty today), so the app finds it without typing. Second step (B3-D9): a gRPC-web listener for the web wallet. **Acceptance:** `https://fastnet-lightwallet.ycash.team` answers `GetLightdInfo` and `GetChainInfo` with a valid certificate; the YEW app syncs against it on the fast testnet, shows a balance and makes a shielded send that confirms. | B3-D8; the first deploy uses the current node image | L |
| 18 | H landing | **The ycash.team landing page.** The page built locally on 2026-11-15 (`/Users/boy/projects/ycash-team-site`: dark theme, the Ycash logo, "Ycash = Your" with the rotating words Electronic Cash, Team, Life, Family, Collateral, Assets, Wallet, Future, ❤️, Friends, 🛡️, Vault, eight product tiles, almost no text; written for someone completely new to Ycash) becomes a public repository and a workspace component like `kogany-site`, with a deploy workflow and a strict content security policy. ycash-ops: `site/ycash-team` (private S3 behind CloudFront at the apex `ycash.team`, with `www` redirecting), hand-applied by the lead architect as the Kogany site was. Content pass with the lead architect's choices (B3-D10): tiles lead to pages a newcomer can use (the YecWallet tile to its beta3 download, item 13; the explorer and wallet backend to the live fast-testnet services), not to source repositories. **Acceptance:** `https://ycash.team` serves the page with a valid certificate and security headers; every tile link works; it reads correctly with scripts off and with reduced motion. | B3-D10; the YecWallet tile's final link waits for item 13 | M |

Collisions to sequence: lanes S and N-C both edit ycash6 but different trees (`contrib/` against
`src/`); lanes W and Y both edit yew (`core/`, `app/`, `web/` against `yewd/`): Y rebases onto W's
fee rule when it lands.

### Wave 3: kogany matches the C++ lines; yolo learns paired jobs

| Chunk | Lane | What | After | Gate | Size |
|---|---|---|---|---|---|
| 6k | K rpc | `vin[].value` / `valueSat` / `address` for every input, post-quantum included, and `blockfee` (`transaction.rs`; the indexes exist). Parity with ycash6 on the fast testnet and mainnet. | 6 (ycash6), 11 | — | M |
| 4k | K mining | The mining default becomes 0 % and kogany gains the opt-in setting it lacks (`crates/zakura-rpc/src/methods/types/ycash.rs`). | 4 | — | S |
| 5k | K mining | The fast profile's mandate end in `crates/zakura-chain/src/parameters/ycash/ydf.rs`, the same height. | 5 | **two reviews** | S |
| 3k | K mining | kogany's equivalent of `getcoinbasetemplatefor`, to the same contract. If N-1 found that kogany cannot build a shielded coinbase, this chunk is first "transparent and post-quantum payouts", and the shielded part is recorded as a finding with its size; the lead architect decides whether it holds the release. | 3n (ycash6), 4k, 5k | one review plus the coordinator's | L |
| 2k | K index | Value pools by type in zakura-state, the same names and numbers as ycash6; a cross-line test and the mainnet ycashd / koganyd pair on this Mac as the live check. | 2 (ycash6) | — | M |
| 3p | P pool | **yolo paired jobs.** Usernames of all three address kinds are accepted and validated with the node. Transparent miners stay on today's swap path. For a Sapling or post-quantum miner, yolo requests a coinbase for the template it holds and issues the pair as one job; it refreshes on a new block, a changed transaction set (no more often than every few seconds) and a new quote; requests run in parallel; no precomputed lower-amount coinbase. `/status` shows miners by payout kind. README corrected (the fund share is not always present). Tests on regtest with the 48,5 miner: a mixed pool of three miners, one per kind, each finds a block that pays it exactly subsidy plus fees. | 3n (ycash6 merged or its interface frozen by N-1) | one review plus the coordinator's | L |

3p may start against N-1's frozen interface and a stub before 3n merges; it cannot finish until
it runs against the real ycash6 call.

### Wave 4: integration

| Chunk | What | After | Size |
|---|---|---|---|
| R-1 | `YELLOWBACK_RPC_VERSION` 9 → 10 on both C++ lines and kogany, once, with the contract documents regenerated (`make spec`, the RPC site). Every client accepts 10: lightwalletd's known version, hawkeye, chain-viz (and its value-pool panel), YecWallet, yew and yewd, x402-ycash. Clients that read `valuePools` use ids, not positions. | every node chunk merged | M |
| R-2 | Version bumps (`configure.ac`, kogany's crate version, YecWallet), `releases/v6.22.0-beta3.yaml` filled with the candidate commits, release notes (`docs/plans/beta3/release-notes-draft.md`): what changed, the two things an operator must act on (**a miner who wants to keep donating sets `-ydf=5`**; fast-testnet nodes must upgrade before the mandate-end height), known limitations. Mapping rows for every mismatch found. | R-1 | S |
| R-3 | Independent audit pass over the run's whole delta on the three node lines (one agent per line, high effort), reading for the items' own acceptance tests and for anything changed outside an item. | R-1 | M |

### Wave 5: qualify, roll out, demonstrate, release

Strictly in this order.

| Step | What | Who |
|---|---|---|
| Q-1 | The relocated harness (P-1) runs against the candidate commits in the train file: all tiers on ycash-dd, ycash6 and kogany, the cross-line checkers, the client suites. Failures are fixed in the repositories and the candidate commits move; the harness commit is recorded. | agents, coordinator |
| Q-2 | **P-2:** the candidate koganyd syncs the fast testnet to the tip and yewd runs against it; the wallet walk-through passes on the upgrade-active chain. (About 26 minutes with a local peer, about 6.5 hours from the seeds.) | agent |
| Q-3 | Release dry run (packages build, checksums, SBOM, the YecWallet packages), with nothing published. | coordinator |
| T-1 | Node images built from the candidate commits. The mandate-end height (B3-D4) is in them. | coordinator |
| T-2 | **Every fast-testnet node upgrades before that height:** the two seeds, the pool host, the explorer host and the lightwalletd host from item 17 (deploy workflows), the local ycashd and the local koganyd (the lead architect's machines: the lead architect restarts them, or says who may). A node on the old binary rejects the first block without the fund output. The checklist is ticked here, node by node, with each node's reported version. | coordinator, lead architect |
| T-3 | The pool host switches to per-miner payouts (no fixed `--payout`) with the new yolo image; the fleet file gets the four payout addresses (B3-D6). | coordinator |
| T-4 | A miner burst carries the chain across the height. Check: the first block after it without a fund output is accepted by every node on the checklist; the explorer shows it. | coordinator |
| D-1 | **The demonstration** (§9). | coordinator |
| L-1 | With beta3 nodes everywhere, repeat item 17's acceptance (the YEW app against `fastnet-lightwallet.ycash.team`) and item 18's link check, so the landing page and the wallet backend are correct on release day. | coordinator |
| REL | Tags in the train's order (ycash-dd `vault-params/v6.22.0-beta3`, then ycash6 `v6.22.0-beta3`, kogany `v1.8.0-ycash.beta3`, the clients), the signing step (the lead architect's key and "go"), publication, the site's download and snapshots pages, the train file merged. | per B3-D2 |

## 6. What can run at the same time

- **From the first hour:** P-1, 15, W0-b, N-1..N-4, and the client lanes W (10, 16), Y (14),
  G (13), S (8), L (17) and H (18). That is up to twelve agents with no shared files.
- **ycash-dd lanes B, C, D** run in parallel with each other and with the kogany-only lane
  (7 → 11) and, once N-4 is approved, 12.
- **Strictly in sequence:** 4 → 5 → 3n inside lane C (same files, and "paid in full" needs 4 and
  5); each ycash-dd PR before its ycash6 twin before its kogany match; 8 → 9; 10 → 16;
  7 → 11 → 6k (one crate); R-1 after every node chunk; Wave 5 as written.
- **Same-file collisions the coordinator must sequence:** `src/rpc/blockchain.cpp` (6 and 2),
  `src/rpc/mining.cpp` and `src/miner.cpp` (4, 5's tests, 3n), `src/chainparams.cpp` (5 only),
  the RPC documents (every node chunk; regenerate once per merge, never by hand), kogany's
  `crates/zakura-rpc` (7, 11, 6k, 4k, 3k: one lane, or two with files assigned), yew (W and Y;
  17's one-line server default goes through lane W), the seeds module and ycash-ops' deploy
  workflow and role policy (17 and any explorer follow-up: one at a time), ycash-ops' `miners`
  files (F-1 only).
- **The critical path** to the demonstration is N-1 → 4 → 5 → 3n (dd) → 3n (y6) → 3p → F-1 →
  T → D. Everything else has slack; staff this path first and never let it wait for a review.

## 7. Review gates in this run

| Chunk | Why | Reviews |
|---|---|---|
| 5, 5k | Changes which blocks are valid on the fast testnet | Two independent, the four-part check in the PR body |
| 12 | Kogany's chain selection and check order | Two independent |
| 2 | Touches `main.cpp` / `chain.h` (an index, not a rule) | Two independent |
| 3n, 3k, 3p | Builds the transaction that pays miners | One independent plus the coordinator's own, with the "exact amount" tests read line by line |
| 4, 4k | A constant in a consensus header, read only by the miner | One independent plus the coordinator's own |

## 8. Risks

| Risk | Handling |
|---|---|
| kogany cannot build a shielded coinbase | N-1 finds out in Wave 0; 3k is scoped accordingly and the lead architect decides whether the shielded part holds the release. The demonstration's pool node is ycashd, so criterion 2 does not depend on it |
| Proving time makes each new block slow for many shielded miners | N-1 measures it; parallel requests; the empty-block bridge stays off unless the measurement demands it and the lead architect agrees |
| A miner program truncates or rejects long usernames | F-1 tests miniZ with Sapling and post-quantum usernames early; fallback: another Equihash 192,7 miner in the image |
| A fast-testnet node is missed at T-2 and forks off | The node-by-node checklist with reported versions; the height has 400 blocks of margin; the chain advances only a few blocks an hour without a burst |
| The value-pool index needs a reindex on upgrade | N-2 decides migration against reindex; the release notes say which and how long |
| The harness move breaks qualification itself | P-1 is first and is proven by re-qualifying the unchanged beta2 commits before any beta3 change merges |
| The lightwalletd host is a fourth deploy layer: its role and the re-put of three live role policies | The same procedure as the explorer's, already proven: backup, diff shown to the coordinator, put, simulator checks (with each action checked against a resource type it acts on) |
| The landing page sends newcomers to things that are not ready | Its tiles carry honest labels (Beta, Testnet) and lead only to what exists on release day; the content pass is the lead architect's |
| Eighteen items is a large release | Items are independent except the chains in §6; the lead architect can drop any `[ ]` without unpicking others, except 4 and 5, which item 3's "in full" needs |

## 9. The demonstration: four miners, three kinds of address

Preconditions: T-1..T-4 done; the pool host runs the beta3 ycashd and the beta3 yolo in per-miner
mode; the fund mandate has ended on the fast testnet; F-1 merged.

1. **Addresses** (B3-D6), four at least, all different: one transparent, two Sapling, one
   post-quantum; a second post-quantum scheme if a fifth miner is wanted (FN-DSA and SLH-DSA).
   Their keys stay in the wallet that made them.
2. **Start** one burst of four miners from the `miners` workflow, each with its own address as
   its stratum username, for long enough that each is likely to find several blocks (with four
   equal cards and 75-second blocks, two hours gives each about twenty-four).
3. **While it runs:** the pool's status shows four miners, by payout kind, all with accepted
   shares; the explorer shows blocks arriving.
4. **Evidence, per miner:** at least one block it found, with
   - the coinbase paying that miner's address and nothing else (no fund output, no pool output);
   - the amount equal to the block subsidy plus the sum of that block's fees, checked by
     arithmetic from `getblock … 2` (at least one of the blocks used must contain fee-paying
     transactions: send a few during the burst, a post-quantum spend among them);
   - for the transparent and post-quantum miners, the address's balance on the explorer;
   - for the Sapling miners, the note in the owning wallet (`z_listunspent` / `z_viewtransaction`),
     since a shielded payout is not visible to anyone else, and the coinbase's shielded output
     count on the explorer.
5. **Negative checks:** a miner with an invalid username is refused; the pool's `/status` and
   the node's log show no coinbase built for an amount other than the exact one.
6. **Record** the block heights, hashes and the arithmetic in
   `docs/plans/beta3/pool-demonstration.md`, and the pool's status output. The burst ends itself;
   the expiry pass is run from a local timer.

Cost: four cards for two hours at about six cents an hour each.

## 10. After beta3 (not in this run)

The candidates left on the list: kogany's spent index and push channel; fresh mainnet snapshots
(waiting, by decision); the software bill of materials detail; YecWallet display polish; the
operations permission gap toward the undeployed Kubernetes layer (an operations task); the
explorer's vault and post-quantum views (waiting on Inzyght's licence); a mainnet lightwalletd
and a mainnet explorer (the fast-testnet deployments are their worked examples).
