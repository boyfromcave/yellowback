# Beta3 plan: 6.22.0-beta3 and a pool that pays shielded miners

**Revision 7 (2026-11-18). Beta3 is released; §2 is the record.** Revision 7 closes the status block (Q, T, D, REL) and adds the close-out entry to the run log. Revision 6 (2026-11-16): Wave 4 (integration) was complete but for five open pull requests;
Wave 5 had not started. It brought the status block and the run log up
to 2026-11-16 15:00 UTC: `rpcversion` 10 merged on all three node lines and every client, the
post-quantum coinbase spend found and fixed in the run, the fast-testnet light-wallet server
accepted, the hosted web wallet live, the fast-testnet pool in per-miner mode, and the decisions
taken since revision 5 (§2.1); five pull requests are open (kogany #43, #44, ycash-dd #194, ycash6
#132, yew #53). The demonstration runbook is
[`pool-demonstration.md`](pool-demonstration.md). Revision 5
brings the status block up to 2026-11-16 06:30 UTC: every node chunk of Waves 1 to 3 is merged on
all three lines, the integration step R-1 (`rpcversion` 10) is open on kogany and local on the C++
lines, the beta2 proof run of the relocated harness is recorded, and item 17's host is deployed
(§2.1). Revision 4 brought the status block up to 2026-11-16 01:40 UTC and added the run log (§2.1): the rulings and decisions taken during the run,
also written into the chunks they change (P-1, 5, 3n, 11, 12, 3k, 2k, 3p, 17, §4, §8).
Revision 3 records decisions B3-D1..D10 (§3). Revision 2 added a lightwalletd deployment for the
fast testnet (17) and the ycash.team landing page (18).
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
| P-1 | Qualification harness out of the node repository | n/a | [x] #123 (pointer) | n/a | [x] workspace #60; [x] the beta2 proof run (§2.1) |
| 15 | Rust toolchain pinned | n/a | n/a | [x] #34 | [x] common fork #9 |
| 1 | `gettransaction` fee display | [x] #191, in #192 | [x] #129, in #130 | n/a | — |
| 6 | Sender address on post-quantum spends; kogany input values, addresses, block fee | [x] #190 | [x] #128 | [x] #40 (6k) | — |
| 4 | Development-fund mining default 0 % | [x] #187 | [x] #125 | [x] #38 (4k) | [x] yolo README, in yolo #16 |
| 5 | Fast testnet: end the fund mandate (consensus gate) | [x] #189, in #192; [~] the release guard on beta tags, local (`up/b3-cut`) | [x] #127, in #130; [~] the release guard on beta tags, local (`up/b3-cut`) | [x] #38 (5k, provisional height); [x] the cut gate, in #42; [~] the release guard on beta tags, #43 | — |
| 3 | `getcoinbasetemplatefor` + yolo paired jobs | [x] in #192 | [x] in #130 | [x] in #39 (3k, Sapling payouts included); koganyd's Sapling and post-quantum coinbases accepted by ycashd in CI (the #43 run) | [x] yolo #16 (3p) |
| 3+ | A post-quantum miner shields its coinbase with `z_sendmany` (a wallet gap found in the run, §2.1) | [x] #195 | [x] #133 | n/a (no wallet in the node) | [x] yew #52 (yewd); the YEW app and web wallet: a documented limit |
| 2 | Chain value pools by address type | [x] #188, in #192 | [x] #126, in #130 | [x] #41 (2k, with the chain transaction count) | [x] chain-viz #11 (the block tooltip reads `transparentPools` by id); lightwalletd and YecWallet need nothing (value-pools note §7) |
| 7 | koganyd accepts 1.0 batch requests | n/a | n/a | [x] #35 | — |
| 11 | kogany per-address counts, chain transaction count | n/a | n/a | [x] in #39; `transactions` [x] in #41 (§2.1) | — |
| 12 | Reorganisation depth and check order (consensus gate) | n/a | n/a | [x] #36 (R3); [x] #37 (R1, R2) | — |
| 8 | Snapshot restore must not fail silently | [x] #186 | [x] #122 | n/a | — |
| 9 | Snapshot bundles above 50 GB | [x] restorer, in #193 | [x] restorer, in #131 | n/a | [x] design note (workspace #59); [x] ycash-infra #52 (`ycash-state/3`, the publisher); [ ] the site's snapshots page |
| 10 | Wallet fees on shielded sends | n/a | n/a | n/a | [x] yew #44 |
| 16 | Mobile wallet fee warning | n/a | n/a | n/a | [x] yew #44 |
| 14 | yewd gaps against ycashd's wallet | n/a | n/a | n/a | [x] yew #46; [x] yew #47 (watch-only imports) |
| 13 | YecWallet release; macOS first-run instructions | n/a | n/a | n/a | [x] yecwallet-dd #21; [ ] the site's download page |
| 17 | lightwalletd for the fast testnet at `fastnet-lightwallet.ycash.team` | n/a | n/a | n/a | [x] ycash-infra #50, ycash-ops #31; [x] host created and deployed (2026-11-16); [x] four fixed peers, ycash-ops #34 (applied); [x] the testnet default, yew #50 (draft #45 closed); [x] acceptance (§2.1) |
| 17w | The YEW web wallet hosted for the fast testnet at `fastnet-wallet.ycash.team` (decided in the run, §2.1) | n/a | n/a | n/a | [x] ycash-ops #33; [x] yew #48, #49, #51; [x] live and accepted; [~] yew #53; [x] ycash-team-site #1 (YEW Web tile and page) |
| 18 | The ycash.team landing page | n/a | n/a | n/a | [x] ycash-ops #29, live at ycash.team since 2026-11-15; [x] workspace registration of `ycash-team-site` (#62) |
| F-1 | Miner fleet: several miners, three address kinds | n/a | n/a | n/a | [x] ycash-infra #51, ycash-ops #32 |
| R-1 | RPC contract version and clients | [x] #193 | [x] #131 | [x] #42 (with the item-5 cut gate and the parity scripts in CI); [~] #43 (pins and contract copies at the rpcversion-10 ycash6) | [x] chain-viz #11, hawkeye #44, x402-ycash #23, lightwalletd-dd #20, yecwallet-dd #22, yew #50; [x] x402-ycash #25 (run against both C++ lines at 10); [x] ycash-infra #54 (the chart accepts 9 to 10) |
| R-1+ | Found in R-3 and the run: the value-pool index resumes after an unclean stop; ycash6's wallet node survives `-reindex-chainstate` (refused with `-rescan`); koganyd's follow stall (backup writes, isolated redial) | [~] #194 | [~] #132 | [~] #44 | — |
| R-2 | Documents for beta3 | [x] in #193 | [x] in #131 | [x] in #42 | [x] workspace #64, #65; yolo #17, chain-viz #12, hawkeye #45, x402-ycash #24, ycash-infra #53, common fork #11, kogany-site #13; [~] the final pass (this revision) |
| Q | Qualification (incl. P-2) | [x] | [x] | [x] | [x] rc-qualify run 44066664793, `qualified: true` (2026-11-17) |
| T | Testnet rollout, mandate-end height crossed | — | — | — | [x] every fast-testnet node on beta3; mandate end 512,417 crossed 2026-11-17 16:15 UTC (`000ca3b7…9fd34d`), no fund output after; pacing live (ycash-ops #41) |
| D | Pool demonstration: four miners | — | — | — | [x] runbook ([`pool-demonstration.md`](pool-demonstration.md)); [x] the run, four miners paid in full and wallet-verified (2026-11-17) |
| REL | Tags, releases, site | [x] tag [`vault-params/v6.22.0-beta3`](https://github.com/boyfromcave/ycash-dd/tree/vault-params/v6.22.0-beta3) (7c4d8af68) | [x] [v6.22.0-beta3](https://github.com/boyfromcave/ycash6/releases/tag/v6.22.0-beta3), 2026-11-17 | [x] [v1.8.0-ycash.beta3](https://github.com/boyfromcave/kogany/releases/tag/v1.8.0-ycash.beta3), 2026-11-17 | [x] YecWallet [v6.22.0-beta3](https://github.com/boyfromcave/yecwallet-dd/releases/tag/v6.22.0-beta3), 2026-11-18; train merged (workspace #70, #74); sites kogany-site #14, ycash-team-site #2; all pre-releases, signed |

PR numbers are in the repository of the column (`#192` in the dd column is ycash-dd #192).
"In #192" means the change is carried by an integration pull request: ycash-dd #192 and ycash6 #130
(`up/b3-integration-1`) carry items 5, 1, 2 and 3n together; kogany #39
(`up/b3-kogany-integration-2`) carries 3k and 11. "Local" means committed on the lane's branch and
reviewed there, not yet pushed (the push rule, §2.1); the R-1 node branches also carry item 9's
restorer and the beta3 sections of the release notes. State as of 2026-11-16 15:00 UTC, from the
merged and open pull requests of ycash-dd, ycash6, kogany, zakura-common-ycash, yew, yolo,
yecwallet-dd, ycash-infra, ycash-ops, chain-viz, hawkeye, x402-ycash, the workspace and
ycash-team-site.

### 2.1 Run log

Rulings and decisions taken during the run, in order. Each is also written into the chunk it changes.

- **2026-11-15, N-4 approved.** The lead architect approved the reorganisation-parity note's
  R1-R6 as proposed ([`reorg-parity.md`](reorg-parity.md)): R1(b) and R2 (koganyd refuses a
  reorganisation deeper than 99 blocks and shuts down, also across a restart), R3 swapped (the
  difficulty target before the median-time rules), R4, R5 and R6 documented (`docs/mapping.md`
  §24).
- **2026-11-15, the push rule** (the lead architect). GitHub runners are the run's bottleneck: an
  agent commits locally as often as it likes and pushes only when the work is ready (built, tested,
  audited, self-reviewed) and the coordinator releases the push, in critical-path order. Reviews
  happen on local branches before the one push; review and CI fixes are batched into one push.
  To save runs, changes that must merge together travel in integration pull requests: ycash-dd #192
  / ycash6 #130 carry items 5, 1, 2 and 3n; kogany #39 carries 3k and 11.
- **2026-11-15, item 17's acceptance** (the coordinator). On the fast testnet `GetChainInfo` answers
  Unimplemented: the YED module has no attestor set there, so lightwalletd registers no Yellowback
  service, and YEW does not need it there (its activation height is compiled in). `GetChainInfo` is
  required only where YED is live. The fast-testnet acceptance is `GetLightdInfo`, the YEW app's
  sync, balance and shielded send, and the web wallet's shielded send, run once. The web wallet has
  no public home, so its run is made from a developer's machine against the public server.
- **2026-11-15, the getcoinbasetemplatefor decisions D-1..D-6** (the lead architect), recorded in
  the design note's §2 ([`getcoinbasetemplatefor.md`](getcoinbasetemplatefor.md#2-decisions)): the
  stateless reference stands (D-1); the call honours the node's `-ydf` (D-2); it refuses a coinbase
  that does not fit (D-3); **beta3 is held for kogany's Sapling coinbase** (D-4); yolo accepts
  `<address>.<label>` (D-5); post-quantum miners take the paired path (D-6).
- **2026-11-15, P-1's beta2 proof run** (the coordinator; workspace #60). The pin check stands as
  written. ycash6 at `fbc9f625` pins yolo, chain-viz, lightwalletd-dd and workspace commits that differ from the beta2
  train's, so re-qualifying the unchanged beta2 commits proves the move when the train, candidate,
  package-shard and steps 2-4 jobs are green and the only failure is that client-pin mismatch, named
  in the record under `node_suites_ci_build_problems`. A `qualified: true` record is not expected
  for beta2. For beta3, ycash6's default client pins are aligned with the train before the candidate
  is cut. The proof run itself is the coordinator's, after the merge; it is not recorded yet.
- **2026-11-15, item 5's height.** The tree carries a provisional fast-testnet mandate end of
  **600,000**, deliberately far above the tip, so a node built from `upgrade/vault` before the cut
  stays strict. The final value (B3-D4: the tip at the release-candidate cut plus 400) is set at
  that cut. The release guard (`qa/yellowback-vault-params.py` rule R9, both C++ lines) refuses an
  rc or final tag that still carries 600,000; a beta may. **Cut gate:** kogany's parameter audit
  must compare kogany's mandate end with ycash6's before the candidate is cut (kogany #38 shipped
  5k with the same provisional value).
- **2026-11-15, kogany's `transactions` count** (the lead architect: one disk-format bump, not
  two). `getblockchaininfo.transactions` moves from item 11 to chunk 2k's zakura-state format
  upgrade, which adds the cumulative count to `BlockInfo` in the same bump as the value pools.
- **2026-11-15, yolo and a Sapling payout's recipient.** yolo checks a Sapling paired coinbase's
  shape and value (one Sapling output, `valueBalance` of minus the amount, no transparent output
  besides the fund's), not its recipient: it does not decrypt the output. That the output pays the
  miner is the node's responsibility (yolo README, yolo #16). The demonstration (§9) proves it from
  the owning wallet.
- **2026-11-15, `-ydf`'s range.** The merged code accepts 0 to 100 on every line and resets an
  out-of-range value to the default, 0; the design note's "at most 5" is corrected.
- **2026-11-16, Waves 1 to 3 merged.** The integration pull requests ycash-dd #192 and ycash6 #130
  (items 5, 1, 2, 3n, with #188, #189, #191 and #126, #127, #129) merged together; on kogany #39
  (3k with Sapling payouts, 11), #40 (6k), #41 (2k and the chain `transactions` count, one
  zakura-state format step) and #37 (R1, R2); yolo #16 (3p); yew #46 and #47 (item 14, watch-only
  imports included); zakura-common-ycash #9 (item 15); ycash-infra #52 (item 9's publisher,
  `ycash-state/3`). No node chunk remains open.
- **2026-11-16, P-1's beta2 proof run** (`rc-qualify` run 43798820497, workspace `upgrade/vault`).
  The train, the candidate, the six package shards, the sidecars and steps 2 to 4 (walk, YEW, x402,
  Hawkeye, YecWallet, cross-line, ceremony) were green. The CI-build evidence half was skipped, so
  the record says `qualified: false`, as ruled (entry of 2026-11-15 above). P-1 is done.
- **2026-11-16, R-1 under way.** The clients that only needed to accept 10 are merged (chain-viz
  #11, hawkeye #44, x402-ycash #23: each accepts 9 and 10). kogany #42 is open (`YED_RPC_VERSION`
  10, the item-5 cut gate in kogany's parameter audit, the beta3 parity scripts in CI). Local, not
  pushed: `YELLOWBACK_RPC_VERSION` 10 on ycash-dd and ycash6 (`up/b3-rpcversion-10`, with item 9's
  restorer and the release notes' beta3 sections), and the lightwalletd-dd, yecwallet-dd and yew
  client changes. Before the train can name 10, the workspace's `scripts/release-train.py`
  (`SPEC_MODE`) must accept it.
- **2026-11-16, item 17's host.** The fast-testnet light-wallet host was created and deployed
  (`fastnet-lightwallet.ycash.team`). The acceptance (§5, item 17) is pending, and so is yew #45,
  which makes it the app's and the web wallet's testnet default.
- **2026-11-16, item 18 is live** at https://ycash.team; its YecWallet button waits for the beta3
  download (item 13).
- **2026-11-16, authorizations for this run** (the lead architect). The four-miner demonstration
  may spend at most **$10 in total on vast.ai**; more needs asking. At the rollout the coordinator
  may stop, upgrade and restart the two local fast-testnet nodes with their settings, telling the
  lead architect before and after; mainnet and explorer nodes stay untouched.
- **2026-11-16, item 17's wallet acceptance is run headless by agents** (the lead architect): a
  throwaway wallet outside `wt/`, the YEW app's core through yew-cli and the web wallet in a
  headless browser. Passkey (WebAuthn) requests are not started on the shared machine: the passkey
  path stays without an automated test.
- **2026-11-16, public hosting of the YEW web wallet for the fast testnet** (the lead architect).
  The web wallet gets a public home for the fast testnet only, a static site in the ycash.team
  pattern at `fastnet-wallet.ycash.team` (chunk 17w); it runs beside the release and does not hold
  the node tags. Deploys are manual (`web-wallet-deploy`, run by hand on `upgrade/vault`); the
  light-wallet server allows that origin. Mainnet stays app-only, a decision about trust.
- **2026-11-16, R-1 merged** on every line: ycash-dd #193 and ycash6 #131 (`rpcversion` 10, item
  9's restorer, the release notes), kogany #42 (with the cut gate and the audit fixes), and the
  clients lightwalletd-dd #20, yecwallet-dd #22 and yew #50. The R-3 audits rated the C++ lines
  "ship" and kogany "ship after fixes" (in #42).
- **2026-11-16, item 17 accepted.** The host serves with four fixed peers (both seeds, the pool's
  node, the explorer's; ycash-ops #34); `GetLightdInfo` over gRPC and gRPC-web; a wallet's
  shielded send was mined in the next block; the hosted web wallet passed its walk twice in a
  headless browser.
- **2026-11-16, the post-quantum coinbase spend joins beta3** (the lead architect). Found in the
  run: where a coinbase must be shielded, no wallet call could spend a reward paid to a
  post-quantum address (`z_shieldcoinbase` refuses such a source and `z_sendmany` left coinbase
  out). A wallet change, not consensus: `z_sendmany` from the address takes its mature coinbase
  when every recipient is shielded, with no change and an exact-amount refusal (ycash-dd #195,
  ycash6 #133, yew #52 for yewd). The YEW app and the web wallet cannot see a coinbase flag in the
  light-client coin listing: a documented limit (pay post-quantum rewards to a ycashd or yewd
  address). The run against real nodes with yewd waits on the pin move in yew's parity job, before
  qualification.
- **2026-11-16, kogany's reorganisation guard with the non-finalized backup off: warn and
  document in beta3** (the lead architect). With the backup off a restarted koganyd has no tip to
  keep and follows its peers' best chain; it warns at every start, and `docs/kogany.md` and the
  notes say so. A fix is for after beta3.
- **2026-11-16, the release guards refuse the provisional mandate end on beta tags too.** This
  supersedes the entry of 2026-11-15 above ("a beta may"): ycash6 and ycash-dd rule R9 on the cut
  branches, kogany's guard in #43 from `v1.8.0-ycash.beta3` on (beta1 and beta2 tags still verify).
  So beta3 cannot be tagged with 600,000; the coordinator sets the final height on all three lines
  at the cut.
- **2026-11-16, the fast-testnet pool in per-miner mode** (ycash-infra #55, ycash-ops #35,
  applied): yolo runs without `--payout`, usernames are payout addresses, at most two Sapling or
  post-quantum addresses per source IP; the miner image accepts Sapling and post-quantum
  usernames. The pool's node is still the beta2 image with `-ydf=5` (`status` shows `"payout":
  "username"`, `"coinbaseCall": false`): Sapling and post-quantum miners need it on beta3, and the
  fund share goes once every fast-testnet node runs beta3.
- **2026-11-16, found while making the mixed-node checks blocking** (kogany #44, open): koganyd's
  non-finalized backup rewrote every block shared by two chains at each tip update, so a follower
  holding a stale side branch crawled; and a node with no open connection waited about two minutes
  to redial. Both are upstream Zakura behaviours; a report for its maintainers is drafted.
- **Open at 15:00 UTC:** kogany #43 (pins; red on the stall #44 fixes, then rerun), kogany #44,
  ycash-dd #194 and ycash6 #132 (a pair), yew #53 (reviewed).
- **2026-11-18, close-out.** Beta3 released (REL above). The mainnet snapshot bundle at
  3,105,000 (ycash-state/3, 24 parts) is published at snapshots.ycash.team and a restore from the
  public URL passed (records: ycash-infra #67; Kogany site parts page: kogany-site #15). The
  fast-testnet faucet pays post-quantum addresses (ycash-infra #65, ycash-ops #46,
  ycash-team-site #5). The explorer has a value-pools page at `/pools/` and a menu link to it
  (ycash-infra #63, #66; ycash-ops #44, #47). The snapshot restorer's fix (`ycash-bootstrap`
  refused every mainnet restore) is merged on both C++ lines (ycash-dd #200, ycash6 #139) and must
  ship in beta4. Advisories: chrono RUSTSEC-2026-0543 recorded as informational (ycash-dd #201,
  ycash6 #140, librustzcash6 #27, hawkeye #46, common fork #12; kogany #46, with libz-sys 1.1.33, still open);
  humantime RUSTSEC-2026-0542 recorded won't fix in librustzcash6 (the lead architect).

## 3. Decisions (taken by the lead architect, 2026-11-15)

| # | Decision | Decided |
|---|---|---|
| B3-D1 | Merge authority for this run | **The coordinator merges**, after an independent agent review, its own review and green CI; consensus-gate PRs after two independent reviews |
| B3-D2 | Who pushes tags and publishes | **Delegated to the coordinator.** The coordinator's own conditions before any tag: every beta3 PR merged, `upgrade/vault` CI green in every repository, qualification (Q-1..Q-3) passed, the testnet rollout and the four-miner demonstration done, the notes final; the train's order; a report before and after. Release signing (the minisign key) stays the lead architect's, on an explicit "go". Agents other than the coordinator never touch tags |
| B3-D3 | Where the qualification harness lives (P-1) | **The workspace repository**, under `qualify/`, beside `releases/` |
| B3-D4 | The fast testnet's mandate-end height (item 5) | **The fast-testnet tip when the release candidate is cut, plus 400 blocks**, compiled into rc1 |
| B3-D5 | The `rpcversion` step | **One step to 10**, at integration (R-1), covering every new call and field of this run |
| B3-D6 | The demonstration's payout addresses | **The coordinator makes a test wallet** on the fast testnet for the demonstration (testnet coins only), outside `wt/`, and records where its keys are; four or more addresses from it: one transparent, two Sapling, one post-quantum |
| B3-D7 | Start | **After this plan is committed and the lead architect has compacted the session**; then Wave 0 |
| B3-D8 | Where lightwalletd runs (item 17) | **Its own host**, in the pool-host pattern |
| B3-D9 | The web wallet and item 17 | **Both from the start**: the first deployment serves the app (native gRPC over TLS) and the web wallet (gRPC-web) together |
| B3-D10 | The landing page (item 18) | **A simple page per product** (one screen, written for a newcomer: what it is, how to get it, one button; live services link straight to the service). **All eight tiles, grouped** in two short rows: "Use Ycash" (YEW, YecWallet, Explorer) first, then "Run and build" (ycashd, Kogany, Yolo, x402, lightwalletd). **No sentence under "Ycash = Your …"**: the logo, the rotating line and the tiles only |

Decided earlier and recorded in the list: the fund default 0 % with `-ydf` opt-in on all lines;
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
  superseded runs; no ad hoc full-tier dispatches; no job that sleeps or polls. **Since the push
  rule (§2.1), an agent pushes only when the coordinator releases it** (it reports
  `READY-TO-PUSH`); reviews happen on the local branch first, and changes that merge together
  travel in one integration pull request per line.
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
| P-1 | harness | **Important process change.** Move `qa/test_yellowback_rc_qualify.py` and `.github/workflows/rc-qualify.yml` out of ycash6 to the workspace repository's `qualify/` (B3-D3). The harness takes the node commits from the train file and records its own commit in the run's result; a harness fix never moves a node's head. Fold in the two fixes left from ycash6 #114 (open `ycash.conf` with "w"; the kogany wait fails fast on a dead node). ycash6 keeps a pointer in `doc/yellowback-release.md`. **Merged** (workspace #60, ycash6 #123). The beta2 proof run's pass condition is the coordinator's ruling in §2.1 (only the client-pin mismatch may fail; no `qualified: true` record is expected for beta2). | B3-D3 | M |
| 15 | k-tools | Pin kogany's Rust toolchain in `rust-toolchain.toml` and in every workflow that installs one; the same in `zakura-common-ycash`; a short "how to bump" note. | — | S |
| W0-a | coord | `wt/BRIEFING-beta3.md`, `wt/COORDINATION-beta3.md`, the skeleton `releases/v6.22.0-beta3.yaml`. | — | S |
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
| 5 | C mining | The fast profile gets its own `nYdfMandateEndHeight` (B3-D4); the default testnet value and the slow and legacy profiles are untouched. Tests: a block without the fund output is rejected one block before the height and accepted at it; a block with it stays valid after. **Height (§2.1):** the tree carries a provisional 600,000 until the release-candidate cut, where the coordinator sets the final value; the release guard (R9) refuses an rc or final tag with 600,000; at the cut kogany's parameter audit must compare its mandate end with ycash6's. | 4 | **two reviews** | S |
| 3n | C mining | `getcoinbasetemplatefor` as N-1 specifies, with decisions D-1..D-6 ([`getcoinbasetemplatefor.md`](getcoinbasetemplatefor.md) §2) (`src/rpc/mining.cpp`, `src/miner.cpp`): stateless; the amount derived from the node's template; transparent, Sapling and post-quantum payout addresses; proving outside `cs_main`. `getblocktemplate` and `submitblock` untouched (a test asserts the stock template is byte-identical before and after). Tests: a block assembled from the stock template and a returned coinbase is accepted for each address kind and pays exactly subsidy plus fees; a stale template reference is refused; no lower amount can be requested. | 4, 5, N-1 | one review plus the coordinator's (mining path) | L |
| 2 | D index | Value pools by type as N-2 specifies (chain index, `getblockchaininfo`, `getblock`). Touches `main.cpp` / `chain.h`. Reindex or migration test; totals equal the old `transparent` entry. | N-2 | **two reviews** | L |

Kogany-only work starts now too, because it depends on nothing above:

| Chunk | Lane | What | After | Gate | Size |
|---|---|---|---|---|---|
| 7 | K rpc | Accept JSON-RPC 1.0-style batch members as ycashd does (`crates/zakura-rpc`); a test with the exact batch Inzyght sends (`wt/handoff/EXPLORER-KOGANY-FASTNET.md`). | 15 | — | S |
| 11 | K rpc | `getaddressfirstlastheight`; `txcount` in `getaddressbalance`; `commitments` no longer 0. Parity tests against ycashd. (`transactions` in `getblockchaininfo` moved to 2k's format upgrade, §2.1.) | 7 | — | M |
| 12 | K consensus | Reorganisation depth and check order as N-4 decides, under the `ycash` feature; a cross-line test for each difference. N-4's R1-R6 approved as proposed (§2.1): R1(b)/R2 refuse a reorganisation deeper than 99 blocks and shut down, durably across a restart (kogany #37); R3 swap the order (kogany #36); R4, R5, R6 documented in `docs/mapping.md` §24. | N-4, 15 | **two reviews** | M |

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
| 17 | L lightwallet | **lightwalletd for the fast testnet, deployed like the pool and the explorer.** ycash-infra: the seeds module gains a `lightwallet` block beside `pool` and `explorer` (a node with `-txindex -insightexplorer -experimentalfeatures`, which lightwalletd's address calls need; the `lightwalletd-dd` image with `--yellowback`; a proxy that terminates TLS and passes gRPC through; automatic certificate; nothing else public; RPC on the host's internal network only; memory limits; `status` reports the server's height and its `GetLightdInfo`); an image workflow for `lightwalletd-dd` in the `yolo-image.yml` pattern (public image, pinned by digest, with provenance). ycash-ops: roots `testnet-lightwallet/{ips,nodes}`, a deploy layer `lightwallet` with its own role (`deploy-testnet-lightwallet`) and environment, the layer policy extended to four layers (and the older gap toward the Kubernetes layer's machines closed in the same re-put), docs, a CloudShell runbook for the lead architect. yew: the fast testnet's server in the testnet default list (it is empty today), so the app finds it without typing. **From the start (B3-D9): a gRPC-web listener for the web wallet beside the native one** (a gRPC-web proxy container, as the Kubernetes chart's gateway and yew's web plan use), and the web wallet's testnet default pointing at it. **Acceptance (as ruled during the run, §2.1):** `https://fastnet-lightwallet.ycash.team` answers `GetLightdInfo` with a valid certificate; `GetChainInfo` is required only where YED is live, so not on the fast testnet; the YEW app syncs against it on the fast testnet, shows a balance and makes a shielded send that confirms; the web wallet makes a shielded send in a browser over gRPC-web, run once (it has no public home, so the run is made from a developer's machine against the public server). | the first deploy uses the current node image | L |
| 18 | H landing | **The ycash.team landing page.** The page built locally on 2026-11-15 (`/Users/boy/projects/ycash-team-site`: dark theme, the Ycash logo, "Ycash = Your" with the rotating words Electronic Cash, Team, Life, Family, Collateral, Assets, Wallet, Future, ❤️, Friends, 🛡️, Vault, eight product tiles, almost no text; written for someone completely new to Ycash) becomes a public repository and a workspace component like `kogany-site`, with a deploy workflow and a strict content security policy. ycash-ops: `site/ycash-team` (private S3 behind CloudFront at the apex `ycash.team`, with `www` redirecting), hand-applied by the lead architect as the Kogany site was. Content as decided (B3-D10): no sentence under the rotating line; the eight tiles in two labelled rows, "Use Ycash" (YEW, YecWallet, Explorer) then "Run and build" (ycashd, Kogany, Yolo, x402, lightwalletd); **a one-screen page per product** on the site (what it is, how to get it, one button; facts only from the repositories and release notes), with the YecWallet page leading to its beta3 download (item 13) and the explorer and wallet backend leading straight to the live fast-testnet services. **Acceptance:** `https://ycash.team` serves the page with a valid certificate and security headers; every tile leads to its product page and every page's button works; it reads correctly with scripts off and with reduced motion. | the YecWallet page's download button waits for item 13 | M |

Collisions to sequence: lanes S and N-C both edit ycash6 but different trees (`contrib/` against
`src/`); lanes W and Y both edit yew (`core/`, `app/`, `web/` against `yewd/`): Y rebases onto W's
fee rule when it lands.

### Wave 3: kogany matches the C++ lines; yolo learns paired jobs

| Chunk | Lane | What | After | Gate | Size |
|---|---|---|---|---|---|
| 6k | K rpc | `vin[].value` / `valueSat` / `address` for every input, post-quantum included, and `blockfee` (`transaction.rs`; the indexes exist). Parity with ycash6 on the fast testnet and mainnet. | 6 (ycash6), 11 | — | M |
| 4k | K mining | The mining default becomes 0 % and kogany gains the opt-in setting it lacks (`crates/zakura-rpc/src/methods/types/ycash.rs`). | 4 | — | S |
| 5k | K mining | The fast profile's mandate end in `crates/zakura-chain/src/parameters/ycash/ydf.rs`, the same height. | 5 | **two reviews** | S |
| 3k | K mining | kogany's equivalent of `getcoinbasetemplatefor`, to the same contract. If N-1 found that kogany cannot build a shielded coinbase, this chunk is first "transparent and post-quantum payouts", and the shielded part is recorded as a finding with its size; the lead architect decides whether it holds the release. **Decided (D-4): it holds the release.** 3k includes a Sapling output prover and its parameters, on the critical path. | 3n (ycash6), 4k, 5k | one review plus the coordinator's | L |
| 2k | K index | Value pools by type in zakura-state, the same names and numbers as ycash6; a cross-line test and the mainnet ycashd / koganyd pair on this Mac as the live check. The same disk-format bump adds the cumulative transaction count for `getblockchaininfo.transactions` (moved from item 11, §2.1). | 2 (ycash6) | — | M |
| 3p | P pool | **yolo paired jobs.** Usernames of all three address kinds are accepted and validated with the node. Transparent miners stay on today's swap path. For a Sapling or post-quantum miner, yolo requests a coinbase for the template it holds and issues the pair as one job; it refreshes on a new block, a changed transaction set (no more often than every few seconds) and a new quote; requests run in parallel; no precomputed lower-amount coinbase. `/status` shows miners by payout kind. README corrected (the fund share is not always present). yolo checks a Sapling coinbase's shape and value, not its recipient (§2.1); the recipient is the node's responsibility. Tests on regtest with the 48,5 miner: a mixed pool of three miners, one per kind, each finds a block that pays it exactly subsidy plus fees. | 3n (ycash6 merged or its interface frozen by N-1) | one review plus the coordinator's | L |

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
| T-3 | The pool host switches to per-miner payouts (no fixed `--payout`) with the new yolo image; the fleet file gets the demonstration wallet's four payout addresses (B3-D6). | coordinator |
| T-4 | A miner burst carries the chain across the height. Check: the first block after it without a fund output is accepted by every node on the checklist; the explorer shows it. | coordinator |
| D-1 | **The demonstration** (§9). | coordinator |
| L-1 | With beta3 nodes everywhere, repeat item 17's acceptance (the YEW app against `fastnet-lightwallet.ycash.team`) and item 18's link check, so the landing page and the wallet backend are correct on release day. | coordinator |
| REL | Tags in the train's order (ycash-dd `vault-params/v6.22.0-beta3`, then ycash6 `v6.22.0-beta3`, kogany `v1.8.0-ycash.beta3`, the clients), the signing step (the lead architect's key and "go"), publication, the site's download and snapshots pages, the train file merged. | the coordinator (B3-D2), under its conditions; signing by the lead architect |

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
| kogany cannot build a shielded coinbase | N-1 found it cannot today; **decided (D-4): beta3 is held for it**, and 3k builds the prover and loads the parameters. The demonstration's pool node is ycashd, so criterion 2 does not depend on it; the release does |
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

1. **Addresses** (B3-D6): the coordinator creates a demonstration wallet on the fast testnet (a
   beta3 ycashd with its own data directory outside `wt/`; testnet coins only; the location of
   its keys recorded in the run notes) and takes four addresses at least, all different: one
   transparent, two Sapling, one post-quantum; a second post-quantum scheme if a fifth miner is
   wanted (FN-DSA and SLH-DSA).
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
