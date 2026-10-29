# Ycash Yellowback (YED) public testnet, checkpoint bootstrap bundles and release-candidate CI

**Revision 3 (2026-10-29): three testnets, see below.** **Revision 2 (2026-10-28).** Revision 2 (owner's
suggestion) builds the testnet the way Ycash itself was built:
- Zcash testnet history up to the fork height, taken from Zcash testnet and anchored by it;
- then a fresh Ycash fork at the original height, 510,248;
- no new genesis.

That splits the bootstrap bundle into an immutable, externally checkable prefix and a
rolling state layer (§2.1, §2.2, §4.0). Revision 1 started a new chain from a fresh genesis.

The plan covers three things the
[upgrade plan](yellowback-upgrade-plan.md) needs before P7 and P8:

1. A public Ycash testnet that carries `UPGRADE_VAULT` (branch ID `0x6d5b7a31`) and the YED
   module. It runs the `ycash6` line, and moving a node, a tool or a scenario from regtest to
   testnet is one setting.
2. A checksummed, signed bootstrap bundle that a new full node can start from quickly. The
   bundle is pinned by a checkpoint compiled into the release binary.
3. CI that takes a `v6.22.0-rcN` from tag to a qualified, signed, published release candidate,
   and that deploys the candidate to the testnet.

`ycash-infra` gains a testnet environment to host all of this (§6).

Items are numbered **T-\*** (decisions), and phases are **N0–N8** (§9). Every gate this plan
serves is already written down elsewhere: the hardening plan's G-10, the upgrade plan's G-12,
v3 A7, lightwalletd L4, the YEW W5 testnet run and the x402 X-11 note. This plan delivers the
network those gates are read on. It does not restate the gates.

## In plain words: what this plan does and why

**What is a testnet?** Ycash's main network ("mainnet") carries real money. Before a big
change goes live there, it should run for weeks on a public practice network ("testnet")
where the coins are worthless. There, anyone can try it, break it and report problems at no
cost. Yellowback, the Ycash dollar (YED), is that kind of change. Ycash's old testnet stopped
running years ago, so this plan builds a new one.

**How the new testnet is built.** Ycash started life as a copy of Zcash in 2019. Its history
up to the moment it split off is Zcash's history. We build the testnet the same way:
1. Copy Zcash's public testnet history up to the split point, block 510,247.
2. Start a fresh Ycash testnet from there.

This makes the practice network look like the real one, including the old history every
node has to handle.

**Why there is a "bootstrap bundle".** A new node normally downloads and checks every block
since the beginning, which takes hours. A bundle is a ready-made download of that history,
so a node can start in minutes. A download is only safe if you can check it. Each bundle
therefore comes with fingerprints (checksums and signatures), and the node software compares
it with values built into the program itself.

**What is being automated.** Copying Zcash's history (the "harvest") runs as a public GitHub
Actions job in the `ycash-infra` repository. Anyone can run it again and get exactly the same
files, down to the last byte. That makes the bundle easy to audit: you rerun the job and
compare one checksum file.

**Release candidates.** Before a new version of the node software is final, it goes out as a
"release candidate" (rc). Automated checks run it together with all the other Yellowback
programs. Then it runs on the testnet for a while, and only after that is it published.

## Revision 3 (2026-10-29, owner): three testnets, and seed infrastructure ready for mainnet

### In plain words

One testnet cannot do every job. Testers need to watch a whole vault and bond lifecycle in an
afternoon, but the release also needs a rehearsal that runs at mainnet's real pace, and a
"control" network that runs today's Ycash rules so any difference can be blamed on the upgrade
and nothing else. So we build **three practice networks at once**. All three start from the same
Zcash history (the prefix bundle already published) and split from each other at block 510,248.
The same seed machines serve all three, and one click deploys or resets any one of them without
touching the others. The same tooling is written so that, when the day comes, it can also run
the seeds for the real Ycash network.

### The three networks

| | **testnet-yb-fast** | **testnet-yb-slow** | **testnet-legacy** |
|---|---|---|---|
| Job | Iterate: vault cycles, bond maturity, dormancy and revival, in hours | Mainnet rehearsal: every Yellowback value exactly as on mainnet; the rc soak | Control: today's Ycash rules, no Vault, the baseline to compare against |
| Datadir | `testnet-yb-fast` | `testnet-yb-slow` | `testnet-legacy` |
| Magic | `f7 79 62 d3` (T-2) | `f7 79 62 d4` | `f7 79 62 d5` |
| P2P / RPC ports | 18833 / 18832 (clients' testnet defaults keep working) | 18933 / 18932 | 19033 / 19032 |
| History | Prefix 0..510,247 (`testnet-prefix-v1`, shared: it is magic-neutral), fork at 510,248, Blossom / Heartwood / Canopy at 510,250 / 252 / 254 | same | same |
| `UPGRADE_VAULT` | 510,400 | **Later, set by the network's first rc** (about a week of blocks after launch), so the activation itself is rehearsed live, with miners, wallets and lightwalletd crossing it as on mainnet | Never (`NO_ACTIVATION_HEIGHT`): YED off |
| Set maturity (`nVaultMinSetMaturity`, YED `BOND_MATURITY`) | 48 / 48 (D4) | 16,128 / 16,128 (mainnet) | n/a |
| Other YED block windows (dormancy, founding window, seat age, emergency notice, liveness minimum, …) | Scaled down in a "fast" column in the node's own parameters, by one stated rule, every invariant asserted (T-16), the way regtest's column exists today | Mainnet's | n/a |
| Attestor set | Its own launch ceremony | Its own ceremony, after its activation | None |
| Node lines | ycash6 and ycash-dd | both | both |

Block time (75 s), Equihash, subsidy and address prefixes (`yt…`) are the same on all three, so
wallets, pools and explorers treat every one as "testnet". Only the magic, ports, datadir and the
Yellowback timing differ.

### How a node picks one (N1, both lines)

- **Compiled-in profiles, not free-form parameters.** `-testnet` plus `-testnetprofile=fast|slow|legacy`
  (T-14). A missing or unknown profile stops the node at startup with a clear message, so nobody
  lands on the wrong network by default, and a typo cannot create a fourth chain. Every
  profile's values are reviewed like any other chain parameter.
- `NetworkIDString()` stays `"test"` for all three, so address encoding, the YED module's
  `network` and every client's chain check stay unchanged. `getblockchaininfo` gains one
  additive field naming the profile.
- Fixed seeds per profile: the same seed hosts, each network on its own port.
- **Replay between networks (accepted).** fast and slow share the Vault branch ID, and legacy
  shares the Ycash one, so a transaction spending pre-fork coins can be replayed onto a sibling
  network. That is harmless for worthless coins. Distinct branch IDs would be a consensus
  change for no product gain.
- N1 as written (one testnet) becomes the `fast` profile; its review and PRs wait for the
  profile rework.

### Infrastructure (N3 and the seeds)

- **One seed host serves all three networks:** one container per network, its own port, its
  own data directory, the same image (the profile is a runtime argument). Networks matter more
  than seed count (owner), so start with **2 hosts × 3 networks** (T-17). The host count is one
  variable; adding a network is one map entry.
- **Per-network lifecycle:** deploy, upgrade (image per network), reset and status, each for one
  network, without changing the Elastic IPs or touching the other two. One workflow run can also
  do all three.
- Bundles: the prefix is shared. State bundles, checkpoints and the snapshotter run per network.
- `charts/ycash-testnet`: one release per network (a `network` value); kind can run any one, or all three.
- Services per network (T-19): seeds, lightwalletd, faucet and chain-viz on all three; YED
  personas and the attestor set on the two `yb` networks.
- rc flow: an rc deploys to fast first, then slow (the soak the gates read). legacy runs the
  same rc with Vault off, the non-activation regression: the upgrade code, inactive, must not
  change today's rules.

### Ready for mainnet seeds (T-18)

- The seed module treats `main` as one more profile (port 8833).
- A mainnet stack is a separate instance of the same module, with:
  - its own state, Elastic IPs and AWS account (recommended);
  - a GitHub Environment that needs the owner's approval for every apply.
- Nothing is created for mainnet until the upgrade plan's P8. Mainnet keeps its existing DNS seeds; these hosts add fixed seeds.

### Kubernetes on AWS in the same private deployment (T-20)

In plain words: the seed machines only keep the networks alive. The services people use (the
light-wallet server, the address index, the web wallet, the faucet, the chain visualizer, the
bundle snapshotter) run on Kubernetes. That stack was built and proven on kind and written for
AWS (EKS) in `ycash-infra` K2. The private `ycash-ops` repository deploys it too, with the
same one-click flow as the seeds.

- **Two layers, both driven from `ycash-ops`:**
  - **Seeds on EC2.** Always on, cheap, fixed IPs, independent of the cluster. The seeds stay
    on EC2 rather than in the cluster, so the networks survive a cluster being down, rebuilt or
    switched off.
  - **The service stack on EKS.** `infra/eks` plus the `ycash-lightwallet` and `ycash-testnet` charts.
- **One testnet cluster, one namespace per network** (`yb-fast`, `yb-slow`, `legacy`), each
  running that network's lightwalletd, yindex, web, faucet, chain-viz, snapshotter and status.
  The personas run only on the two `yb` networks (T-19). yindex uses one RDS instance, with
  one database per network.
- **Switched on when needed.** The K2 runbook estimates about $625–645 a month for the
  cluster, which is most of the testnet's cost. Recommendation: bring it up for test campaigns
  and the rc soak, and take it down otherwise. The seeds keep the chains running in between.
  `make eks-up` / `eks-down` already exist; `ycash-ops` gets the same as workflow buttons.
- **Public side (ycash-infra):** `infra/eks` becomes a reusable module, like `infra/testnet-seeds`:
  - the provider and backend move to the caller, and every name, domain, zone and e-mail is a variable;
  - the local `make eks-*` path keeps working through a thin example root;
  - outputs that embed the account ID (`ecr_registry`) are masked in workflow logs, never printed.
- **Private side (`ycash-ops`):**
  - `eks/testnet/` calls the module at a pinned SHA, and holds the domain, hosted zone, ACME e-mail and sizes.
  - The deploy workflow gains cluster plan / apply / down, and a per-network chart deploy (images by digest from ghcr, mirrored to ECR, T-12), followed by the smoke tests.
- **Mainnet:** `eks/mainnet/` is the same module in its own account and state, behind the
  approval-gated `mainnet` Environment. Nothing is created before P8.
- **Anonymity limits (honest):**
  - A public hostname is public: certificates are logged in Certificate Transparency.
  - The domain should be registered with privacy protection, and the ACME e-mail should be a role address.
  - The account ID, ARNs, state bucket and Terraform plans stay in `ycash-ops` and its private logs.

### Cost (estimate, us-east-1 on demand)

Seeds: a `t3a.medium` (4 GiB, for three nodes), about 100 GiB of gp3 and one public IPv4 address come
to about $40 per host per month. **2 hosts ≈ $80 a month**, plus data transfer. The
single-network plan was three hosts at about $66. The EKS service stack (T-20) adds about
$625–645 a month while it is up.

## Execution status (authoritative; kept by the coordinator from agent reports)

Started 2026-10-28 (owner: begin with ycash-infra and the testnet harvest). Node baselines
for this round: `ycash6` `upgrade/vault` at `1c10c93cc` (ycash6#63 merged) and `ycash-dd`
`upgrade/vault` at `1bbcf26bc` (ycash-dd#141 merged; `yellowback tests` run 40754261395
green). Legend: `[x]` done and verified, `[~]` in flight, `[ ]` not started.

### N0 decide
- [x] T-1: re-fork from Zcash testnet (the owner's suggestion, revision 2)
- [x] Bundle production and hosting live in `ycash-infra`; node repos pin what they accept (revision 2, owner)
- [x] D3 (2026-10-28): the Zcash parameter files are mirrored as a GitHub release in ycash-infra (`zcash-params-v1`; ycash-infra#13)
- [x] T-2 (2026-10-29):
  - datadir **`testnet-yb`**;
  - new magic **`f7 79 62 d3`**, chosen to match none of Ycash's or Zcash's mainnet, testnet or regtest values (`24e92764`, `fa1af9bf`, `aae83f5f`).
- [x] D1 (2026-10-29): **fixed seeds only**, no DNS seed; the seed IPs come with rc1.
- [x] Seed hosting (2026-10-29): **option B, AWS EC2 + Elastic IPs**, split in two:
  - a generic Terraform module in public ycash-infra;
  - the account-specific configuration in the private `boyfromcave/ycash-ops`.
  - Nothing that identifies the account is public.
- [x] D4 (2026-10-29): testnet set maturity **48 blocks (about 1 hour)**, in both halves. The owner wanted faster iteration than the first recommendation (1,152).
  - `nVaultMinSetMaturity` (the vault primitive's minimum) and the YED module's testnet `BOND_MATURITY` are both 48. The module adopts a set only when the set's maturity equals `BOND_MATURITY` (`state.cpp:1184`), so both must move together.
  - Floor: `BOND_MATURITY ≥ ATTEST_MAX_AGE` (20; `params.cpp:173-177`), asserted for testnet too. Mainnet keeps 16,128, regtest 2 / 8.
  - Committed on both lines (ycash6 `775725259`, ycash-dd `b4db29da3`); cross-line identity and the vault-params compare pass.
- [x] Revision 3 (2026-10-29, owner): three testnets (fast, slow, legacy), seeds and the EKS service stack deployed from `ycash-ops`, ready for mainnet. T-14..T-20 decided as recommended
- [x] T-3, T-5, T-6 (2026-10-29): a workspace-owned domain held in `ycash-ops`; signer sets fast 7 house seats, slow 3 house + 4 invited; owner minisign key, automatic signing from `ycash-ops`, testnet verifier rule relaxed to 2 house keys
- [x] Round 3 decisions (owner, 2026-10-29):
  - testnet-yb-fast house-seat bonds at a thousandth of mainnet's (10 / 20 YEC, `TestFastParams`); testnet-yb-slow keeps mainnet's (in ycash6#70 / ycash-dd#147);
  - the Vault-era protocol version is 270200 (T-8);
  - ycash-dd `MIN_PEER_PROTO_VERSION` stays 170002 until the P8 checklist raises it to 270013;
  - §5.1's rc row amended to T-15 (slow's height may precede its set);
  - T-9: testnet keys allowed in `charts/ycash-testnet` (the faucet wallet, the publish token), from External Secrets only, never mainnet (ycash-infra `AGENTS.md` rule 4, in ycash-infra#17);
  - the status page is one host per network.
- [ ] Remaining T-decisions (§8 recommendations are the working defaults)

### Security housekeeping (`ycash-infra`, owner request 2026-10-28)
- [x] PR #5 chart hardening merged (`4ba1e6f`): Checkov 214 → 70 failing checks, 0 new.
  - **Confirmed on a cluster by the owner's `make kind-up` (2026-10-28):** a fresh regtest chain, images rebuilt from `upgrade/vault` (ycash6 `1c10c93cc`, lightwalletd-dd `a1d141e`, rpcversion 8).
  - Passing: `make kind-smoke` and YEW's web smoke.
  - Clean: every pod's logs scanned for read-only and permission errors. The only hit was a stale pre-#5 `web:local` image.
- [x] Kind defects K-1..K-6 fixed on ycash-infra#10, merged 2026-10-28 as `d673148` (`92b3742`..`8be1eec`, `f81b3ac` for `kind-personas up` waiting for the node's RPC after a reset, and `2e6bf16` for K-6).
  - **Owner's re-test on kind (2026-10-28): K-1..K-5 confirmed.**
    - K-1: stale images caught, and the allow-list override works.
    - K-2: every workload rolled out, none failing.
    - K-3: A-3 answered 39, limited 41.
    - K-4: `kind-reset-chain` no longer hangs on the faucet.
    - K-5: after the node pod was deleted, the miner resumed by itself (410 → 416 in 30 s).
  - The personas armed: 3 seated, minting allowed.
  - **K-6 confirmed after the follow-up fix.** The server and the ingester raced to create the schema on a fresh database (SQLSTATE 23505). The schema is now applied under a Postgres advisory lock, and a regression test fails on the old code. On the owner's re-test, both yindex pods showed 0 restarts on a fresh chain.
- [ ] Open code-scanning alert count confirmed at 0 (the agent token cannot list alerts: 403; Dependabot is disabled on the repository)

### N3-a prefix harvest (`ycash-infra`)
- [x] Prefix format v1 frozen (`bundles/prefix/FORMAT.md`, ycash-infra `3ff8575`): gzip of the length-prefixed raw stream per 50,000-block chunk. §2.1 and §4.0 say tar + gzip; the format drops the tar layer, since a single stream needs none
- [x] Harvest scripts (`bundles/prefix/harvest.py`, `3ff8575`): export from Zebra, verify (hash chain, Zebra v7.0.0 source checkpoints vendored with sha256, Ycash compiled checkpoints), deterministic pack, manifest, `SHA256SUMS`. Zebra `zfnd/zebra:7.0.0@sha256:a70d2be8…`, pack image `python:3.13.18-slim-trixie@sha256:76baad60…`. Zebra RPC and stop-at-height behaviour read from source; first exercised by the smoke run
- [x] Unit tests on real Zcash testnet block vectors: 33 tests, offline, green locally; pack twice gives identical `SHA256SUMS` (blocks 0..10)
- [x] `testnet-prefix.yml` smoke harvest green on GitHub: run 40767275967 at `8ac3c81`, 2026-10-28, blocks 0..4,799.
  - Timings: Zebra synced from the public testnet seeders in 34 s (tip 19,200 by then), the export took 5 s (4,800 blocks in 4 s) and the pack 2 s.
  - Output: 7,823,558 raw bytes (1,630 B per block) packed to 7,120,271 bytes gzipped, a 9 % saving. Hash chain from genesis verified; 12 checkpoints matched (Zebra source + Ycash compiled); re-verified outside the container.
  - `SHA256SUMS`: `de642d6c…` for the chunk, `31a66dc2…` for `manifest.json`.
  - Run 2 (40763603501) had failed in the export: Zebra 7.0.0 starts RPC only after its peer set is up (`zebrad/src/commands/start.rs:388-395`, `:512-514`), so a restart with no network never served RPC. `3801e77` fixed it by exporting from the running, syncing zebrad.
- [x] **Full harvest 0..510,247 green on GitHub** (run 40783490314, 2026-10-28):
  - Timings: Zebra synced from the public testnet seeders in about 19 min; the export took 437 s (510,248 blocks) and the pack 59 s. Whole job: 28 min of the 350 min budget.
  - Size: 1,086,239,501 bytes raw in 11 chunks, 960,757,996 bytes gzipped. Every chunk is far under GitHub's 2 GiB asset limit.
  - Checks: hash chain verified from genesis; **1,277 checkpoints matched** (Zebra's source checkpoints plus Ycash's compiled ones); re-verified outside the container.
  - `SHA256SUMS`: `manifest.json` `7026607b…`, the first chunk `41317fa2…`, the last chunk `d3377353…`.
  - Zebra's state is cached (3.7 GB) for reruns.
- [x] **Byte-identical second run** (run 40787936355): all 12 files in `SHA256SUMS` are identical to run 40783490314. Run 2 resumed from run 1's cached Zebra state; the export, verify and pack are fully repeated. The publish run syncs cold, which gives a third, independent reproduction
- [x] **`testnet-prefix-v1` published** 2026-10-29 00:26 UTC: https://github.com/boyfromcave/ycash-infra/releases/tag/testnet-prefix-v1. Its publish run (40790941022) synced cold from the public seeders, a third independent reproduction, and its `SHA256SUMS` is identical to runs 40783490314 and 40787936355. 13 assets (11 chunks, `manifest.json`, `SHA256SUMS`); build provenance attested

### N3-b prefix import checks (`ycash-infra`)
- [x] Framing and import scripts (`bundles/prefix/import/`, ycash-infra `c0fc439`): raw stream to `-loadblock` records with the network magic; manifest, hash-chain and checkpoint-height checks; 22 + 6 tests green against a stand-in node. No real ycashd yet: the sandbox cannot fetch the `node-bin` artifacts
- [x] `testnet-prefix-import.yml`: matrix {ycash6 `1c10c93cc`, ycash-dd `1bbcf26bc`} × {checkpoints, full}, with node binaries from their CI artifacts. Written and lint-clean. Its `workflow_run` trigger fires only once the workflow is on `upgrade/vault`, so it has not run. The `node-bin` artifacts expire after 3 days and must be re-dispatched for older pins
- [x] Import green on both lines, **both modes**, smoke range 0..4,799: runs 40783701751 and 40783689294, 2026-10-28, after ycash-infra#10 merged (`d673148`). All four legs and the compare passed on ycash6 `1c10c93cc` and ycash-dd `1bbcf26bc` binaries, in about 1 minute per leg. The node pins move to ycash6 `727c613` / ycash-dd `559d04e` once ycash6's CI on `727c613` is green
- [x] Import of the **full prefix** with checkpoints, green on both lines (run 40787221990, pins ycash6 `1c10c93cc` / ycash-dd `1bbcf26bc`): ycash6 in 21.7 min, ycash-dd in 42.9 min
- [x] Import with `-checkpoints=0` (full verification) green on both lines, full prefix: ycash6 in 24.7 min, ycash-dd in 25.9 min (run 40787221990)

### N3-c testnet chart scaffold (`ycash-infra`)
- [x] `charts/ycash-testnet` (ycash-infra `0fd0f0a`): seed StatefulSet (ycash6, 3), cross-line verifier (ycash-dd, 1), prefix-restore init container (off by default; refuses an unpinned or mismatched bundle); no keys (T-9 pending). Render-only until N1: today's testnet parameters are the unreachable old testnet
- [x] `values-testnet.yaml` for `charts/ycash-lightwallet` (overlay on `values-eks.yaml`; hostnames are T-3 placeholders)
- [x] Lint, kubeconform and image-pin checks green in CI on ycash-infra#10. Every check passed on `c2b905a`, CodeQL and Semgrep code scanning included, after fixing the PR's 6 test-file alerts.
- [x] Security hardening and scans (`d851da3`..`8ac3c81`): the testnet chart gets #5's pod and container hardening. Checkov now scans the testnet renders, and its gate keys rendered resources. Run locally, the testnet work adds **0 new findings** to Checkov (44 base / 44 head), Semgrep, zizmor, actionlint, gitleaks, shellcheck and CodeQL (python, actions). Not yet run in a pod
- [x] `ycash-infra` plan gains the testnet phase rows (K5–K7) and a plain-words testnet section

### N3-d Zcash params mirror (D3, `ycash-infra`)
- [x] `bundles/zcash-params/` and `zcash-params.yml` (ycash-infra#13): download the three parameter files from download.z.cash, check them against the sizes and SHA-256 values ycash-dd pins (`zcutil/fetch-params.sh:223-225`), publish as a release with build provenance. Dry run green (run 40795883900)
- [x] **`zcash-params-v1` published** 2026-10-29 (run 40797228488): https://github.com/boyfromcave/ycash-infra/releases/tag/zcash-params-v1. Assets checked against the pins: `sapling-spend.params` 47,958,396 B `8e48ffd2…`, `sapling-output.params` 3,592,860 B `2f0ebbcb…`, `sprout-groth16.params` 725,523,612 B `b685d700…`, plus `SHA256SUMS`. The chart's `zcashParams.url` can point at it

### N1 node parameters (both lines)
- [~] Written and committed on both lines (`claude/lucid-fermi-ry9sby`: ycash6 `775725259`, ycash-dd `b4db29da3`), 5 commits each including D4. Not yet compiled: `yellowback tests` dispatched on both (ycash6 run 40799401716, ycash-dd run 40799404971). Changes:
  - datadir `testnet-yb`, magic `f7 79 62 d3`;
  - DNS seed removed (and ycash-dd's old fixed seed); `pnSeed6_test` empty until rc1; fixed seeds used at once when a network has no DNS seeds;
  - checkpoint 510,247 `0000ec90…fb31` added, 650,000 removed; the old fork-block hash unset;
  - Blossom / Heartwood / Canopy at 510,250 / 510,252 / 510,254 (audit in the first commit message); the future-timestamp rule aligned on both lines at Blossom + 6 (the lines had disagreed);
  - `UPGRADE_VAULT` at 510,400; `-stopatheight` (from Bitcoin Core); new tests `testnet_params_tests.cpp` and `stopatheight.py`, byte-identical on both lines.
- **Deviation:** `nMinimumChainWork` is block 280,000's work (`0x23bc0da20`), not 0. With 0 and the Overwinter and Sapling hashes still pinned, a node with a tip below 207,500 aborts (a fresh datadir at genesis). The value stays below the prefix's work, so F-T2 holds.
- [x] Single-network N1 + D4 compiled and tested in CI on both lines (ycash6 run 40799401716, ycash-dd run 40799404971): build, unit and every functional group green; only the audit failed (three upstream files without the Ycash copyright line, `ycash6` named in a test comment), fixed in the rework
- [~] **Profiles (revision 3)** committed on both lines (ycash6 `05ad13a47`, ycash-dd `24e871ac1`, plus the copyright fix): `-testnetprofile=fast|slow|legacy`, required, checked in `ChainNameFromCommandLine()`; `CTestNetParams` plus three subclasses (the release guard parses constructor bodies); per-profile magic, ports, datadir, Vault height, maturity, empty fixed seeds; `getblockchaininfo.testnetprofile`; the YED fast column `TestFastParams` (rule max(floor, ceil(mainnet × 48 / 16,128)), every invariant asserted; mapping §22); release guard R7 per profile; docker entrypoint needs `YCASHD_TESTNET_PROFILE`. Local checks green (qa Python suites, cross-line identity both ways, vault-params compare, the ycash-dd audit's every gating leg). CI dispatched (ycash6 run 40805292068, ycash-dd run 40805298247)
  - Note: on fast the first mint still needs about 28 hours after activation, because the price windows keep mainnet's values (`pSlowMinFill` 1,344 tagged blocks). Lifecycles run in hours after that warm-up
- [x] PRs open: ycash6#67 and ycash-dd#145 (four-part check and tier in each body). **PR CI green on both** (yellowback tests run 40808099700 / 40808100848: build, unit, every functional group, audit including cross-line identity; codeql, semgrep, secops green)
- [x] **Merged 2026-10-29** on the owner's decision, with CI green: ycash6#67 (`d1cf1c182`) and ycash-dd#145 (`fec0be1d1`), squash. **Deviation:** merged ahead of the two independent reviews the G-9 gate asks for. The reviews remain owed, before any rc is tagged
- [x] yolo reads `testnetprofile=` for the cookie directory and default RPC port (yolo#9, merged `0659f41`)

### Seed hosting (option B) and the EKS layer, three networks (revision 3)
- [x] Public (ycash-infra#14, **merged `dbf448a`** 2026-10-29; ycash-ops pinned to it). Fixed before merge: the seeds and the light-wallet chart now pass `YCASHD_TESTNET_PROFILE`, which the node image's entrypoint requires on testnet:
  - `infra/testnet-seeds`: one host serves yb-fast, yb-slow and legacy (one container each, ports 18833 / 18933 / 19033). Per-network deploy, upgrade, reset and status through SSM and an on-host `seedctl`. `main` is supported but off.
  - `infra/eks/module`: the K2 stack as a reusable module, one namespace and one database per network, account-bearing outputs sensitive. Per-network chart values.
  - `node-image.yml`; the owner's minisign key `keys/ycash-release.pub` and verify sections.
  - Offline checks green: terraform test, seedctl tests, helm and kubeconform renders, Checkov 0 new, actionlint, zizmor. PR CI running
- [x] Private `ycash-ops` (`main` at `c89508a`):
  - three-network seed roots, `eks/testnet` (domain set, zone and ACME e-mail placeholders), inert mainnet roots;
  - `deploy.yml` (layer, network, action, typed confirm; environments `testnet` and, later, approval-gated `mainnet`), one infra pin;
  - `sign-release.yml` and `scripts/sign-release.sh` (environment `release-signing`: the signing key is never visible to the deploy jobs); dry-run tests green
- [x] Node image rebuilt with the package-page labels and its own page (ycash-infra#16; `node-image` run 40832098390, ycash6 `71e74a9ef`): `ghcr.io/boyfromcave/ycashd@sha256:78f4a969…`, provenance attested; pinned in ycash-ops `testnet-seeds/nodes/main.tf` (the first build `b65049be…` is superseded)
- [ ] Owner: make the `ycashd` package public (ycash-ops `docs/aws-setup.md` §8)
- [x] DNS (§10): the zone is delegated to Route 53 (NS checked); zone and ACME contact set in `ycash-ops` only
- [ ] Owner, in this order:
  1. AWS account, state bucket, OIDC, the two deploy roles.
  2. DNS: hosted zone, registrar name servers, WHOIS privacy.
  3. GitHub environments `testnet` and `release-signing` with their secrets.
  4. Merge the PRs, bump the infra pin, build the image, then `apply` and `deploy`.
- [ ] Not verified on real AWS: SSM delivery, cloud-init, the first EKS apply, DNS and certificates, the signing run against a real release
- Cost: seeds about $78 a month (2 hosts × 3 networks); EKS about $660–680 a month while up

### Round 3 in flight (2026-10-29): parallel helpers, one branch and PR per repo each
- [~] **N2 tooling**: draft PRs ycash6#70 and ycash-dd#147 (branch `claude/n2-tooling`; no `src/` change). **PR CI green on both lines** after three fix rounds, including the functional `testnet_ceremony.py` (the full regtest rehearsal: prefix bundle and restore, the fork block, the set, the house seats, maturity, an rc1-like node agreeing) and `ycash_bootstrap.py`. The fixes: find the set transaction through the blocks, not the wallet; a bond locktime of tip + 1, not 0; CodeQL file permissions; gitleaks.
  - devnet join mode: `yellowback-devnet up --network testnet-yb-*`; regtest unchanged; profiles `contrib/yellowback/profiles/*.toml`.
  - `contrib/testnet/ceremony/ceremony`: steps check → fork → vault → set → seats → mature → record; the record `ycash-ceremony/1`; `rehearse` on regtest, the entry point rc-qualify calls.
  - `ycash-bootstrap`: the prefix pinned to `testnet-prefix-v1`'s `SHA256SUMS`, an optional minisign check, the `ycash-state/1` state path; `YCASHD_BOOTSTRAP` in the image.
  - **Owner decision:** the house-seat bonds (10,000 YEC per seat; fast's 7 seats need 70,000) cannot be mined soon after the fork. Scale the fast column's bond floor, or fund the seats another way.
  - Plan §2.2 to amend: the fork-block miner needs `-maxtipage`; after the fork, mining is Equihash 192,7 (a GPU miner through yolo).
- [~] **N3 remainder**: draft PR ycash-infra#17 (branch `claude/n3-services`), **PR CI green** (after a shellcheck SC2015 fix). Not run on a cluster or a real node. Per network, all off by default:
  - testnet faucet: its own wallet node, limits per IP and per address, optional proof of work;
  - status page and probe: the cross-line state-hash check;
  - snapshotter and verifier: format `ycash-state/1`, `bundles/state/`; ycash6 and ycash-dd statements must agree;
  - alerts (PrometheusRule).
  - Owner decisions open: T-9 (keys in the chart; the faucet and the GitHub publish token wait on it), T-3 (one status host or one per network).
  - Open question: do ycash6 and ycash-dd report the same `utxo_hash_serialized`?
- [~] **N4 release-candidate CI**: draft PRs ycash6#69, ycash-dd#146, yellowback#25 (branch `claude/n4-rc-ci`); **PR CI green on all three** after one fix round (the Ycash notice on `version.h`, no `ycash6` in `src/`, an action pin's version comment, test-file permissions); `rc-qualify` itself first runs at an rc tag:
  - release rules by stage (beta, rc, final; R7 per testnet profile; slow may have a height without a set, T-15);
  - protocol version 270013 → 270200 (T-8);
  - a release `sign` job: SBOM, SHA256SUMS, provenance, keyless cosign;
  - `rc-qualify.yml` steps 1–4 and the qualification record;
  - the release train (`releases/v<version>.yaml`, `scripts/release-train.py`).
  - Owner decisions open: 270200; ycash-dd `MIN_PEER_PROTO_VERSION` (stays 170002, P8 says 270013); §5.1's rc row is to be amended to T-15.
  - Not done: the §5.5 release image (ghcr push, `Dockerfile.release`), client release workflows, bundle-manifest provenance.
- These stay off the seeds code (`infra/testnet-seeds`, `node-image.yml`) and ycash-ops while the owner tests the first deploy; each merges when the owner chooses

### Findings this round (they amend the plan text)
- **F-T1 (import agent, cited in `bundles/prefix/import/README.md`).** Neither node line
  verifies Sprout proofs from before Sapling (block 280,000), even with `-checkpoints=0`
  (`proof_verifier.cpp:26-31`). The "full verification" legs therefore verify everything the
  node verifies, and no more.

  In checkpoints mode both lines skip proof and script checks for the whole prefix:
  - ycash6, because its last checkpoint is 650,000 (`main.cpp:3538`);
  - ycash-dd, because of its import workaround (`checkpoints.cpp:81-100`). That workaround
    also does not check checkpoint hashes during import, so `import.sh` checks them itself.
- **F-T2 (N1 constraint).** A node aborts when its chain work reaches `nMinimumChainWork`
  while an upgrade has its activation hash pinned but is not yet active (ycash6
  `main.cpp:2581`). So N1 must not set `nMinimumChainWork` to the prefix's work while
  `UPGRADE_YCASH`'s activation hash is pinned:
  - keep it below the prefix's work until rc1 pins the new fork block;
  - from rc1, raise it only to heights above the fork.

  §2.1's "the chain work at 510,247 in N1" is amended accordingly. The import legs record
  `chainwork` to confirm today's binaries stay below their current value.
- **F-T3.** The ycash-dd line needs the Sapling and Sprout-Groth16 parameter files at
  startup (`init.cpp:819-836`). ycash6 has them compiled in. Bundles and the chart must
  provide them for ycash-dd nodes.

### Not started this round
N1 (node parameters), N2 (devnet `--network`, ceremony, `ycash-bootstrap`), N4 (release CI), N5–N8.

**Branch timing.** On 2026-10-28 `upgrade/vault` in `ycash-dd` and `ycash6` has an open PR
each: the rewind fix, [boyfromcave/ycash-dd#141](https://github.com/boyfromcave/ycash-dd/pull/141)
and [boyfromcave/ycash6#63](https://github.com/boyfromcave/ycash6/pull/63), with CI running.
§9 orders the phases so that work starts now:
- Decisions, infrastructure, CI scaffolding and tooling go first. They touch no node file, or
  they land on node branches that merge after those PRs.
- The node changes (N1) touch `src/chainparams*.cpp`, `src/yellowback/params.cpp` and the
  release scripts. These do not overlap with the rewind fix's files, so N1 can be written in
  parallel and merged after the PRs.

---

## 1. Where things stand (facts, cited at the 2026-10-28 `upgrade/vault` tips)

### 1.1 The existing testnet cannot be used

The testnet `CTestNetParams` describes is the old Ycash testnet: Zcash's testnet history,
forked at `UPGRADE_YCASH` 510,248. Nobody can reach it. Here is what is in the code
(`ycash6/src/chainparams.cpp`):

- **Genesis and network identity.** The genesis block is Zcash's (`05a60a92…`, :546-553).
  The magic is `fa 1a f9 bf` (:539-542). P2P port 18833, RPC port 18832, datadir `testnet3`
  (`src/chainparamsbase.cpp:47-50`).
- **Seeds.** The only DNS seed is `testseed.ycash.xyz` (:557). `pnSeed6_test` is empty
  (`src/chainparamsseeds.h`). On 2026-10-02 the seed did not answer and no peer was reachable
  (`doc/yellowback-release.md` "Network parameters"; hardening plan §7 G-10).
- **Pins to the old history.** Checkpoints at 38,000 and 650,000 (:568-577). The
  `hashActivationBlock` of Overwinter, Sapling and the Ycash fork (:426-436). A non-zero
  `nMinimumChainWork` (:537). Once a chain has the minimum work, `main.cpp:2600-2615` aborts
  the node if an activation block hash differs.

  So a new chain cannot simply be mined on these parameters, and nobody holds the old
  chain's data.
- **Vault.** `UPGRADE_VAULT` has `NO_ACTIVATION_HEIGHT` on testnet (:455-459).
  `TestParams().attestorSetId` is null (`src/yellowback/params.cpp:183-196`). Yellowback is
  therefore not live there (`IsConfigured()`, `params.h:276`).
- **The attestor set cannot come from a flag on testnet.** `-yellowbackattestorset` and the
  five other Yellowback tuning flags are refused off regtest (`src/yellowback/index.cpp:1141-1153`).
  The set is compiled in, per 01/V-7.

Two further facts:
- The magic `fa 1a f9 bf` is Zcash testnet's own. The old Ycash testnet never changed it.
- A ycash6 node still cannot sync from Zcash testnet peers.
  `MIN_TESTNET_PEER_PROTO_VERSION` is 270013 (`src/version.h:56`, enforced at
  `main.cpp:8316`), and zcashd and Zebra advertise 170xxx versions.

**Consequence (T-1):** the public testnet is a **re-fork of Zcash testnet**:
- Everything at or below block 510,247 is Zcash testnet's history, unchanged. Today's
  pre-fork parameters already describe it: the genesis, Overwinter 207,500 and Sapling 280,000
  with their activation hashes, and the 38,000 checkpoint.
- Block 510,248 onward is a **new** Ycash branch. Only the post-fork parameters change.
- The blocks below the fork are harvested once from Zcash testnet and imported (§2.1). There is
  no P2P link to Zcash peers.
- The network keeps the `-testnet` flag. It gets a new magic and a new datadir (T-2).

### 1.2 Regtest is where everything works today, and where it differs from testnet

The differences below are the ones the regtest-to-testnet path (§3) has to absorb:

| Topic | Regtest (today) | Testnet (§2) |
|---|---|---|
| Upgrades | Every upgrade is supplied by `-nuparams`: the six pre-Vault ones at height 1, Vault at `<h>` (`qa/rpc-tests/test_framework/yellowback_util.py:156-160`) | Compiled. Overwinter and Sapling are at Zcash testnet's heights. The Ycash fork is at 510,248. Blossom, Heartwood, Canopy and Vault follow just after the fork (§2.1). `-nuparams` is refused off regtest (`init.cpp:1479-1482`) |
| History below the first Ycash block | None | 510,248 blocks of Zcash testnet history, including Sprout and Sapling, imported from the prefix (§2.1) |
| Attestor set | `-yellowbackattestorset=<setid>`, given after the set is created | Compiled (`TestParams().attestorSetId`) |
| Set maturity | `nVaultMinSetMaturity` 2 (`chainparams.cpp:700`) | 16,128 today (`consensus/params.h:233`; T-4) |
| Equihash | 48,5. The Python `stratum-miner` and yolo `auto` both use it | 192,7 after the fork upgrade (`chainparams.cpp:1012-1031`). This needs a real solver: the node's `-gen` miner, or a GPU miner behind yolo, whose `auto` mode picks 192,7 off regtest |
| Difficulty | No retargeting | Retargets over a 17-block window. A min-difficulty block is allowed after a gap of 6 × 75 s (`chainparams.cpp:415`, `pow.cpp:83-84`) |
| Peers | `-connect` between local nodes | DNS seed, fixed seeds, `addnode` |
| Tooling | `yellowback-devnet` (8 or 11 nodes), `upgrade-walk`, the kind chart's `arm.yaml` Job, host-run personas | Not yet built (§3, §6) |

### 1.3 Release and CI today

- **The release workflow.** `ycash6/.github/workflows/yellowback-release.yml` builds four
  tier-1 and two tier-2 platform packages, runs `qa/yellowback-release-smoke.sh`, writes
  `SHA256SUMS`, and creates a **draft** release. A `-rc` or `-beta` tag marks it a pre-release.
  The binaries are unsigned and the builds are not reproducible (`doc/yellowback-release.md`).
  The version is 6.22.0-rc1 (`configure.ac` BUILD 25). It has never been tagged.
- **The release gate refuses every tag today.** `qa/yellowback-release-heights.sh` applies
  R1–R7 to every tag:
  - R1 and R2 require the mainnet Vault height and attestor set.
  - R3–R5 require the protocol-version bump, which is deferred (upgrade plan P8, part D).
  - Both conditions are unmet, so **no rc can be tagged**. N4 makes the rules depend on the
    release stage (T-8).
- **Node CI.** The node CI is `yellowback-tests.yml` on both lines. Each push runs a build and a
  sharded functional suite, including yolo and chain-viz at pinned commits. The nightly runs
  the devnet presets and lightwalletd-dd on a 5-node devnet.
- **Cross-repo coverage is spread across repos.** No single job runs the whole ecosystem
  against one binary:
  - YEW's `devnet-nightly` runs the node artifact, the attest agent, lightwalletd and YEW.
  - Hawkeye's `devnet-e2e` runs the node with the bridge.
  - chain-viz, x402, yolo, lightwalletd and YecWallet each run a devnet on dispatch only.
- **Publishing.** No repository publishes container images. The node Dockerfiles exist
  (`ycash6/contrib/docker/ycashd/`). `ycash-infra` pushes only to ECR, and only by hand
  (`make eks-push`).

### 1.4 `ycash-infra` today

`ycash-infra` holds one chart, `charts/ycash-lightwallet`. It runs `ycashd` (from `ycash6`),
lightwalletd-dd, yindex, Redis, Envoy and the `yew/web` bundle. kind runs it on regtest; EKS
runs it on mainnet. EKS is written and validated offline but has never been applied.

Testnet appears only as a `ycashd.network` value. The things a testnet needs are all missing:
- seed nodes and a DNS seeder;
- a testnet miner;
- containerised attestors (`images/personas/` is a skeleton, and the personas run on the host);
- a public faucet (the faucet is regtest-only);
- an explorer;
- snapshots, and a chain-restore init container;
- an image built from release tarballs (`images/ycashd/Dockerfile.release` is listed in the
  README, but it does not exist);
- a registry that anyone else can pull from.

Its rule 4 (non-custodial) forbids the keys that testnet operator roles need (T-9).

### 1.5 What a datadir holds on this line

| Subdirectory | Contents | Rebuilt by |
|---|---|---|
| `blocks/` | `blk*.dat`, `rev*.dat`, `blocks/index` | — |
| `blocks/insight-index` | Insight index, only with `-insightexplorer` / `-lightwalletd` | `-reindex` |
| `chainstate/` | The coin database | `-reindex-chainstate` |
| `vaults/` | VaultDB | Wiped by `-reindex` and `-reindex-chainstate`, then rebuilt from blocks and undo data (`init.cpp:2284`). This is why `-prune` is refused where Vault has a height (`init.cpp:1611`) |
| `yellowback/` | The YED index | `-reindex-yellowback` or `-reindex`. `carriers.dat` in it is wallet state |
| `database/` | Wallet | — |
| `peers.dat`, `banlist.dat`, `onion_private_key` | Per-node state | — |

Three RPCs give agreement digests:
- `gettxoutsetinfo` returns `hash_serialized` (`rpc/blockchain.cpp`).
- `vault_getinfo` returns `statehash` over the whole set state (`rpc/vault.cpp:405,448`).
- `yed_getstatehash` returns the YED state at a height (`rpc/yellowback.cpp:897-917`).

---

## 2. The testnet: Zcash testnet to block 510,247, then a new Ycash fork, on the `ycash6` line

### 2.1 Chain parameters (N1, both node lines)

`CTestNetParams` is changed **identically on `ycash6` and `ycash-dd`**:
- The release guard compares the Vault fields of main, test and regtest across the two lines.
- `ycash-dd` nodes on the testnet are the cross-line verifiers (§5.3).
- Workspace rule: a shared change is made on both lines together.

`chainparams.cpp` is outside the review-gate list (`src/consensus/`, `src/script/`, `main.cpp`,
`src/primitives/`). The values below are still consensus for the testnet, so the N1 PR carries
the four-part check and gets two reviewers anyway.

**Why the fork height stays at 510,248.**
- It is the height every existing pre-fork pin was written for, so the change touches only the
  post-fork values.
- It lies below Zcash testnet's own Blossom (584,000). A later fork height would make Ycash
  validate Zcash's post-Blossom history under Zcash's upgrade heights, which Ycash's upgrade
  table does not describe.

The result has the same shape as mainnet, which is Zcash mainnet through 569,999 and then
Ycash:
- the fork code paths run on testnet: the Equihash switch to 192,7, `minDifficultyAtYcashFork`
  (`pow.cpp:53`) and the Ycash branch ID;
- so do years of Sprout and Sapling history;
- and so do realistic sizes for reindexing, rebuilding `vaults/` and producing bundles.

| Parameter | Value | Why |
|---|---|---|
| Genesis, pre-fork upgrades, checkpoint 38,000, founders' reward addresses, Equihash 200,9 before the fork, `nPowAllowMinDifficultyBlocksAfterHeight` 299,187 | **Unchanged** (`chainparams.cpp:404-436`, :546-553, :568-606) | They describe Zcash testnet's history, which is kept |
| Checkpoint 510,247 | **New**: Zcash testnet's block hash at 510,247, taken from the harvest and matched against two independent Zcash testnet sources | Anchors the whole prefix to Zcash testnet. Expensive checks below it are skipped on import (`main.cpp:3530-3540`) |
| Checkpoint 650,000 | **Removed** | It belongs to the old, lost Ycash branch |
| `UPGRADE_YCASH` | 510,248, unchanged. `hashActivationBlock` is the **new** fork block, set by rc1 from the ceremony and unset in the ceremony build | Pins the new branch, and refuses the old one (`main.cpp:2600-2615`) |
| Blossom, Heartwood, Canopy | Moved from 661,610 / 661,622 / 661,634 to just after the fork: the smallest heights N1's ordering and funding-stream audit accepts (for example 510,250 / 510,252 / 510,254) | Waiting 150,000 blocks at 150 s would take about 260 days |
| NU5, NU6, NU6.1, NU6.2 | `NO_ACTIVATION_HEIGHT` | Required: they cannot be scheduled with Vault (`init.cpp:1556-1560`) |
| `UPGRADE_VAULT` | Height `H_V`, shortly after Canopy (for example 510,400; fixed at the ceremony, §2.2) | Sapling must be active at or below it (`init.cpp:1556`) |
| `nMinimumChainWork` | Below the prefix's work in N1 (F-T2). Raised in each rc, from rc1, to the bundle height's work above the fork | Reaching it while `UPGRADE_YCASH`'s hash is pinned but not active aborts the node (F-T2) |
| `pchMessageStart` | New, distinct from Zcash testnet, mainnet and regtest (T-2) | No Zcash testnet peer, and no leftover peer from the old Ycash testnet, ever handshakes. The prefix comes from the harvest, not from peers |
| Ports | P2P 18833, RPC 18832, unchanged | Clients' defaults keep working |
| Datadir | `testnet4` (T-2) | A leftover `testnet3` directory holds the old branch, and the node would abort on it. yolo's cookie lookup (`yolo/src/main.rs:109-110`) follows the name |
| `nVaultMinSetMaturity` | T-4 (recommended: 1,152, about one day) | 16,128 blocks is about 14 days of waiting before every set exists |
| `pqFalconHeight` | 0 | Same as mainnet (R6) |
| Attestor set | `TestParams().attestorSetId`, the YED set created in the ceremony | 01/V-7 |
| Checkpoints after the fork | One per bundle height, added by each rc (§4.2) | The state bundle's trust anchor |
| DNS seeds | Seeder hosts from §6.2 (T-3) | |
| Fixed seeds | `pnSeed6_test` from the seed nodes' stable addresses (§6.2) | The fallback when DNS fails |
| Post-fork height-indexed constants | **Audit every one in N1:** YDF addresses and `nYdfMandateEndHeight`, funding streams at the moved Canopy height, halving, `nFutureTimestampSoftForkHeight` (follows Blossom), the Sprout and chain-supply checkpoints | The fork-relative schedules shift with Blossom and Canopy. The old testnet's YDF `sm…` addresses are kept unless T-2 replaces them with workspace testnet keys. A unit test asserts the subsidy and outputs of block 510,248 and of the first Canopy block |

Address prefixes are unchanged (`sm…`, `ytestsapling`, `yt…` and PQ `571E` from
`src/yellowback/params.cpp:183-196`). YEW, x402, yindex and lightwalletd keep their testnet
encodings. Pre-fork coins on the prefix belong to whoever held them on Zcash testnet. That is
harmless on a testnet, and mirrors mainnet.

**The harvest is an automated, reproducible job (N1), owned by `ycash-infra`.** It runs as
`ycash-infra/.github/workflows/testnet-prefix.yml`, with the same script in
`ycash-infra/bundles/prefix/` for anyone to run locally under Docker.

**Who owns what.** The rule is: **`ycash-infra` produces and hosts data; the node repositories
define what that data must be.**

| `ycash-infra` (produce, host) | Node repos, `ycash6` and `ycash-dd` (define, consume, vouch) |
|---|---|
| The prefix harvest, its import checks, and the `testnet-prefix-v1` release | The checkpoints and `nMinimumChainWork` that anchor every bundle |
| The state-bundle snapshotter and verifier jobs (§4.3) | `ycash-bootstrap` and the entrypoint's `YCASHD_BOOTSTRAP` (§4.4). They ship inside each release and must match its parameters |
| The bundle CDN, `charts/ycash-testnet`, and testnet deploys | **The prefix's `SHA256SUMS` hash, pinned in `ycash-bootstrap`.** This is how a node release vouches for an artifact that infra produced |
| | The node release workflow and `rc-qualify` (§5). These stay tag-driven next to the code they release |

This keeps ycash-infra's rule 1 (no node change). The harvest uses a pinned third-party image,
which is the precedent of its plan §1.3.

The import legs need node binaries from another repository. They take them the way YEW's
`devnet-nightly` already does: `gh run download` of the latest trusted `node-bin` artifact
from `ycash6` and `ycash-dd`, with `actions: read`. Both repositories are public, so the job's
own token reads them.

**Where it can run:**
- **Not in a cloud agent session.** Its egress is an HTTPS proxy with an allow-list. On
  2026-10-28 it refused the Zcash testnet explorers with 403, and Zebra needs raw P2P TCP on
  18233.
- **Yes on a GitHub-hosted runner.** These have open outbound TCP. `boyfromcave/ycash-infra`
  is public, so minutes and artifact storage are free.
- **Yes in the `ycash-infra` cluster, or on a laptop**, with the same container.

**Jobs:**

1. **`harvest`** (ubuntu-latest, inside the 6 h job limit):
   - Run `zebrad` from its image at a pinned digest, on Testnet, with the RPC on localhost.
   - Once the tip passes 510,247, export blocks 0..510,247 with `getblockhash` and
     `getblock <hash> 0`, then stop Zebra.
   - Write them as a **magic-neutral raw block stream** (`u32 length ‖ block`) in fixed
     height-range chunks of 50,000 blocks (11 files).
   - **Check every block hash against Zebra's own source checkpoints** at a pinned commit:
     1,276 hashes at or below 510,247 in `zebra-chain/src/parameters/checkpoint/test-checkpoints.txt`,
     one every 400 blocks. Also check Ycash's compiled 38,000 / 207,500 / 280,000. The 38,000
     and 280,000 hashes were checked against Zebra's list on 2026-10-28 and match.
   - Then `tar --sort=name --mtime=@0 --owner=0 --group=0` and `gzip -n` per chunk, in the
     same pinned container.
   - Write `manifest.json`: per-chunk `sha256` and byte counts, the hash at every 10,000th
     height, the Zebra image digest, and the checkpoint file's commit.
   - Upload as a workflow artifact.
2. **`import`**, a matrix of {ycash6, ycash-dd} × {checkpoints, `-checkpoints=0`}:
   - Takes the node from the latest trusted `node-bin` artifact, the pattern YEW and yolo
     already use.
   - Frames the stream with the network's magic, imports with `-loadblock`, and checks the
     manifest's hashes.
   - Records each line's `gettxoutsetinfo` at 510,247. The two lines' digests are compared
     within a line only, since their serialisations need not agree.
   - The full-verification legs may run longer, as separate jobs.
3. **`publish`**, on dispatch with `publish: true`:
   - A release `testnet-prefix-v1` on `ycash-infra`. It is kept away from the node
     repositories' `v*` release tags.
   - Assets: the 11 chunks, `manifest.json`, `SHA256SUMS`, build-provenance attestations and
     a cosign signature.
   - Release assets do not expire; workflow artifacts expire after 90 days at most.
   - The same repository mirrors them to the bundle CDN.

**Why anyone can audit it.** The output is a pure function of Zcash testnet's history and
the script version. Raw blocks are canonical bytes, chunks are cut by height, and the
archive step runs in a pinned image. So **a rerun by anyone, from a fork of the repository or
locally, must reproduce `SHA256SUMS` byte for byte**. Comparing one file is the whole audit.

The magic-neutral stream is framed at import, so the prefix does not change when T-2's
magic is chosen, or when a reset (T-7) changes it again. The same chunks also import into
**today's** `upgrade/vault` binaries, whose testnet pre-fork pins are identical. The import
legs can therefore run before N1 merges.

**Size, estimated from public facts and to be measured by the first run.** Expected: about
1–2 GB raw, and not much smaller compressed (Equihash solutions and proofs are random
bytes).

| Part | Estimate | Basis |
|---|---|---|
| Headers | ≈ 0.76 GB, incompressible | 510,248 headers × (140-byte header + 1,344-byte Equihash 200,9 solution + 3-byte length) |
| Coinbases | ≈ 0.1–0.15 GB | One per block, a few hundred bytes with the founders' output |
| Other transactions | ≈ 0.1–0.9 GB | The old Ycash testnet counted 862,651 transactions through 650,000 (`chainparams.cpp:575`), coinbases included. That leaves at most about 350,000 non-coinbase transactions below the fork, at 0.3–2.5 KB each (transparent, Sprout, Sapling) |
| Hard upper bound | < 40 GiB | Zebra cuts a checkpoint early once 32 MiB accumulates (`MAX_CHECKPOINT_BYTE_COUNT`). None of its 1,276 gaps up to 510,247 is shorter than 400 blocks, so no 400-block window reaches 32 MiB. Its first short gap is at 4,306,000 |

It fits:
- Each 50,000-block chunk is about 100–200 MB, far under GitHub's 2 GiB per-asset limit.
- The runner's disk holds Zebra's state for this range plus the output.
- The ycash6 state bundle adds the Ycash part's blocks and the state. That is a few hundred
  MB at testnet volumes.

**If the Zebra sync does not finish inside 6 h** (testnet peers are fewer than mainnet's):
- cache Zebra's state between runs (`actions/cache`, ≤ 10 GB per repository) and resume;
- or use a larger or self-hosted runner;
- or run the same container as a `ycash-infra` Job.

The output does not depend on where it ran.

**Mapping rows.** Two findings go into `docs/mapping.md` §22 with N1 (workspace rule 5):
- The old testnet's checkpoint at 650,000 and its Ycash-fork activation hash make any
  re-fork abort.
- The peer floor (270013) means Ycash cannot sync its own pre-fork history from Zcash peers.
  The harvest-and-import path is the workaround.

### 2.2 The launch ceremony: re-forking, and getting an attestor set that the release can name

**The problem.** `setId` is the txid of a `SET_CREATE`. A `SET_CREATE` is valid only after
Vault activates. So on any new network the set exists only *after* the Vault height, and the
release that names it must come later. This plan does not change 01/V-7's rule that the set
is compiled in. It sequences around it:

0. **Import the prefix.** Every launch operator's node imports the prefix bundle (§4.0) and
   stops at 510,247.
1. **Ceremony build (not tagged, not published).** N1's parameters with `H_V` set, the
   `UPGRADE_YCASH` activation hash unset, and `attestorSetId` null. In this state the module validates inertly
   (`init.cpp:1592` logs it). The planned P8 `InitError`, which stops a main or test node
   that has a Vault height but no set, must land **with or after** rc1 (step 4), never before.
   N1 records this ordering.
2. **Private mining from the fork.** The launch operators mine the new fork block 510,248 at
   minimum difficulty (`minDifficultyAtYcashFork`), then on past `H_V`, with `-connect`
   among themselves only. Each operator controls at least one node: ycash6 nodes, plus one ycash-dd
   node.
3. **Create the sets.** At `H_V`+ε, create the YED attestor set: `ratelimitbps` 0, per the
   P8 checklist, with the founding attestors' keys (T-5). Create the bridge persona's set at
   the same time if G-12 needs both shapes. Mine to maturity (T-4).
4. **Tag `v6.22.0-rc1`.** It names the set, pins the new fork block as `UPGRADE_YCASH`'s
   `hashActivationBlock`, and adds its first post-fork checkpoint, which is the set-creation
   block or later, together with the first state bundle (§4) at that height.
   - The ycash-dd pairing tag `vault-params/v6.22.0-rc1` comes first, as for any release.
   - Seeds open, and the chain is public from here.

The ceremony is a script, not a procedure (`contrib/testnet/ceremony`, N2). It runs end to end
in the kind cluster with **the same steps on regtest**, which makes it the rehearsal (§3).
Launching the testnet is a re-run of a script that is already green.

**Resets (T-7).** Before mainnet, a vault-rule change that makes past testnet history invalid
**resets** the testnet:
- a new magic in the next rc;
- a fresh ceremony from the unchanged prefix, which gives a new fork block that the next rc
  pins;
- every node wipes its post-prefix state and re-imports the prefix bundle. `ycash-bootstrap
  --reset` does this.

The prefix never changes, so a reset costs one maturity period and one import. A rule change that adds rules and leaves history valid
rolls forward like a normal rc. A reset is announced on the status page (§6.4) with the rc
that carries it.

### 2.3 Who runs what on the testnet

| Role | Count at launch | Run by | Image |
|---|---|---|---|
| Seed nodes, ycash6 | 3, on at least 2 providers or regions | Workspace (`ycash-infra`) | Release image |
| Cross-line verifier, ycash-dd | 1 or more | Workspace (`ycash-infra`), and invited operators | ycash-dd image at the `vault-params` tag |
| Miners | 2 independent block producers at launch, then yolo pools | Workspace: node `-gen` at first. Pool operators bring yolo plus GPU miners (192,7) | Release image, yolo release |
| YED attestors | The ceremony set (T-5). G-5 wants at least 7 seats from at least 7 operators | Founding seats per T-5, then recruited operators | `contrib/yellowback/attest` release |
| Bridge signers (persona) | One set per shape, for G-12 | Workspace, with `bridge-sim` until wyec P5 | |
| lightwalletd-dd + yindex | 1 public endpoint | Workspace (`charts/ycash-lightwallet`, `network: testnet`) | lightwalletd-dd release |
| chain-viz | 1 public instance | Workspace | chain-viz release |
| Faucet | 1 | Workspace | `images/faucet`, ungated (§6.3) |
| Bundle producer and verifier | 1 producer (ycash6), plus at least 2 independent verifiers (§4.3) | Workspace, plus invited operators | Release image |

---

## 3. Regtest to testnet is one setting: the network profile

The user-facing promise is: **a scenario that passes on the devnet runs unchanged on testnet,
with `--network testnet` (tools) or `network: testnet` (chart).** Everything that differs in
§1.2 moves into a single *network profile* that each tool reads. No tool tests the network
name inline.

### 3.1 The profile

A profile is a small file, `contrib/yellowback/profiles/{regtest,testnet,mainnet}.toml`. It
lives in `ycash6`, with an identical copy in `ycash-dd`, checked by the cross-line audit leg.
It holds:
- the node arguments that differ by network (regtest: the `-nuparams` and
  `-yellowbackattestorset` lines; testnet: none);
- ports and the datadir subdirectory;
- the Equihash parameters;
- where the attestor set comes from (`flag` or `compiled`);
- the set maturity;
- the address HRPs;
- the seeds and the public endpoints (lightwalletd, chain-viz, faucet, bundle URL);
- whether the tool may mine with `generate` (regtest) or must wait for blocks (testnet).

`yb-calibration`'s policy and the clients do not read it. They keep their own network enums
(§3.3).

### 3.2 Node-side tools

- **`yellowback-devnet`** gets `--network {regtest,testnet}`.
  - On regtest it behaves as today.
  - On testnet it **joins instead of spawning**. It attaches the requested roles (minter,
    attestor, pool, user personas, bridge-sim, `yellowback-sim`) to a running testnet node
    given by `--rpc` and cookie. Commands that only work on a private chain are refused with a
    clear message: `mine N` (use `--wait-blocks`), a price walk that moves the clock, and the
    fault injections.
  - The role scenarios (`scenarios/*.md`) and the `upgrade-walk` checks run on both. A check
    that cannot run on testnet is marked so in the walk itself, not skipped silently.
  - Waits are block-count based, never sleep-based, so 75 s blocks only lengthen them.
- **`contrib/docker/ycashd/entrypoint.sh`** (both lines) reads the profile.
  - `YCASHD_NETWORK=testnet` writes `testnet=1` and nothing regtest-only, as today.
  - New: `YCASHD_BOOTSTRAP=<manifest URL>` restores a bundle into an empty datadir before the
    first start (§4.4).
- **The ceremony script** (§2.2) runs on regtest in CI, against the testnet profile's
  maturity and heights, wherever the flags allow it. That makes it the rehearsal of the real
  launch.

### 3.3 Clients

Each client already has a testnet enum. N5 fills in the values.

| Client | Change |
|---|---|
| YEW | `default_servers(Network::Testnet)` gets the public endpoint (today `&[]`, `core/src/net/tls.rs:33`). Testnet's compiled `vault_activation_height()` and `attestor_set_id()` come from rc1 (P8 checklist W3-Y-3). A testnet build goes to the internal and TestFlight tracks |
| YecWallet | A testnet start option that bundles the rc's `ycashd`. The fast-start bundle offer (§4.4) comes later (T-10) |
| lightwalletd-dd | No source change. `network: testnet` in the chart. Its testnet byte-equality run against the baseline binary is L4 |
| yolo | Already selects 192,7 off regtest. Follows the `testnet4` datadir (T-2). Release artifacts added (§5.4) |
| chain-viz | A testnet profile, and a hosted instance (§6.3) |
| x402-ycash | The e2e config gets a testnet target. This closes the X-11 note "until Ycash testnet has seeds" |
| Hawkeye | Sepolia (or Holesky) plus the Ycash testnet once wyec P5 deploys there. Hawkeye's devnet stays its CI |
| yb-calibration | Nothing. G-10's measurements read the testnet through stock RPCs |

---

## 4. The checkpoint bootstrap bundle

### 4.0 Two layers: an immutable prefix and a rolling state bundle

The re-fork (§2.1) splits the chain into two parts with different trust properties. The
bundle follows that split.

| Layer | Contents | Changes | Anchored by | Restored by |
|---|---|---|---|---|
| **Prefix bundle** | Blocks 0..510,247 as a magic-neutral raw block stream, 11 deterministic `.tar.gz` chunks of 50,000 blocks (§2.1). **Blocks only, no state** | Never. Published once, reused by every reset | Zcash testnet itself: Zebra's 1,276 source checkpoints, any Zcash testnet node or explorer, and a byte-identical rerun of the job by anyone. Also the compiled checkpoints at 38,000 and 510,247, and the node's own validation on import | `-loadblock` import. Every block is validated, so nothing in it is taken on trust except the checkpoint skipping of expensive checks below 510,247 (which `--verify-full` / `-checkpoints=0` turns off) |
| **State bundle** | A datadir at `H_B` above the fork (§4.1). It includes the prefix's blocks | Per rc | The compiled post-fork checkpoint, verifier statements and signatures (§4.2) | Extract, then verify the digests (§4.4) |

**Picking a layer:**
- An operator who trusts nothing but Zcash testnet and their own CPU takes the prefix, then
  syncs the Ycash part from peers. The Ycash part is small; most of the chain's history is
  pre-fork.
- An operator who wants minutes, not hours, takes the state bundle.
- The ceremony (§2.2) and every reset start from the prefix.

The prefix is produced in N1 by the harvest. Its `manifest.json` lists the block hash at
every 10,000th height. `ycash-bootstrap --prefix` checks the tarball's `sha256`, imports it,
and compares those hashes with the running node.

**Mainnet has the same structure.** Ycash mainnet is Zcash mainnet through 569,999. A
mainnet prefix bundle is anchored by Zcash mainnet in the same way, and by Ycash mainnet's
existing checkpoints. The mainnet state bundle sits on top of it (§4.4).

### 4.1 The state bundle

The bundle is a `.tar.gz` of a ycash6 datadir, taken from a cleanly stopped node at height
`H_B`. It holds `blocks/` (including `blocks/index` and the undo files), `chainstate/`,
`vaults/` and `yellowback/`.

It excludes:
- `database/`, `wallet.dat` and `yellowback/carriers.dat` (wallet state);
- `peers.dat`, `banlist.dat`, `onion_private_key`, `debug.log`, `.lock` and `ycash.conf`.

There are two flavours:
- **`full`**: the default above.
- **`full-insight`**: also holds `blocks/insight-index`, for `-insightexplorer` /
  `-lightwalletd` nodes such as lightwalletd-dd's backend.

The bundle is **per node line**. A ycash-dd node does not start from a ycash6 bundle, because
the two lines' on-disk formats are not promised to agree. ycash-dd nodes sync from peers.
That is also what makes them verifiers.

Next to the tarball sits **`manifest.json`**:

```json
{ "network": "testnet", "line": "ycash6", "version": "6.22.0-rc2", "flavour": "full",
  "height": 20160, "blockhash": "…", "chainwork": "…",
  "utxo_hash_serialized": "…",           // gettxoutsetinfo
  "vault_statehash": "…",                // vault_getinfo
  "yed_statehash": "…",                  // yed_getstatehash H_B
  "tarball": "ycash6-testnet-20160-full.tar.gz", "sha256": "…", "bytes": 0,
  "created": "2026-…Z", "producer": "ycash-infra/snapshotter" }
```

### 4.2 Why a user can trust it: three anchors, none of which is "trust the uploader"

1. **The binary pins the height.** Every rc that ships a bundle compiles `(H_B, blockhash)`
   into `checkpointData`, and raises `nMinimumChainWork` to that block's work. A bundle whose
   tip is not the checkpointed block fails the node's own checkpoint check
   (`main.cpp:6150-6172`). The checkpoint goes through code review with the release; the
   bundle only has to agree with it.
2. **Independent agreement on the state.** Before publication, at least 2 independent
   verifiers (T-6) sync to `H_B` **from peers**, not from the bundle, with `-stopatheight` (N1).
   - At least one of them runs ycash-dd.
   - Each signs a *checkpoint statement*: the manifest minus the tarball fields, which are
     `{network, height, blockhash, chainwork, utxo_hash_serialized, vault_statehash, yed_statehash}`.
   - The publish step refuses unless every statement is byte-identical.
   - The tarball bytes are not deterministic (LevelDB layout), so the statement signs the
     state, and `sha256` binds the bytes the producer uploaded.
3. **Integrity of the bytes.** `SHA256SUMS` covers the tarball and the manifest. It is signed
   by the release workflow's identity (§5.2) and by the verifiers' keys.

### 4.3 Production: `ycash-infra` snapshotter

The snapshotter is a CronJob, and a manual job before each rc:
1. Pick `H_B`: the last multiple of 1,440 that is at least 1,000 blocks deep.
2. On a dedicated `ycash6` pod, `-stopatheight=H_B`. Then a clean stop.
   - Neither node line has this option today. N1 ports it from Bitcoin Core: the option in
     `init.cpp`, and a single check after each connected block in `ActivateBestChain`.
   - That check is in `main.cpp`, so it goes through the review gate. It changes no validity
     rule.
   - It is chosen over rolling back with `invalidateblock`. A rollback would leave a
     `BLOCK_FAILED` mark in the bundle's `blocks/index`, and a node restored from that bundle
     would refuse the chain.
3. Record the three digests.
4. `tar` with sorted entries and fixed mtimes (`--sort=name --mtime=@0 --owner=0 --group=0`),
   which removes every variance except LevelDB's own. Then `gzip -n`.
5. Hash, then upload to a staging prefix.
6. Open a statement request. The verifier jobs (§2.3) answer with signed statements.
7. Publish when the statements agree.

Storage is an object store behind a CDN (S3 + CloudFront on EKS). The GitHub release carries
the manifest, `SHA256SUMS` and the signatures, and links to the tarball. GitHub's 2 GiB asset
limit does not hold a mainnet bundle.

### 4.4 Consumption: `ycash-bootstrap`

`contrib/bootstrap/ycash-bootstrap` (ycash6) is POSIX shell, with Python for the JSON, and runs
on any platform the release ships. It:
1. fetches the manifest, `SHA256SUMS` and the signatures;
2. checks the signatures against the keys in the release (`contrib/bootstrap/keys/`);
3. downloads the tarball and checks `sha256`;
4. **refuses a non-empty target datadir**;
5. extracts;
6. starts `ycashd` with `-connect=0 -listen=0`. It checks that `getblockhash H_B` equals the
   compiled checkpoint, and that `gettxoutsetinfo`, `vault_getinfo` and
   `yed_getstatehash H_B` equal the manifest;
7. stops, and tells the user to start the node normally.

`--verify-full` additionally runs `-reindex-chainstate` in the background. That validates the
bundle's blocks from scratch without a download, for operators who will not accept the
anchors.

The Docker entrypoint and the chart's init container run the same script. A fresh
`ycash-lightwallet` replica then starts in minutes, not after an hour-long sync.

`ycash-bootstrap --prefix` restores the prefix layer instead (§4.0). `--reset` wipes a
datadir down to nothing and restores the prefix, for testnet resets.

**Mainnet bundles** (prefix and state) use the same machinery once the format has run on
testnet for two rc cycles (N7). No YED state exists on mainnet before activation; `vaults/` and `yellowback/`
are empty and their digests are those of the empty state.

---

## 5. Release-candidate CI

### 5.1 Stage-aware release rules (N4, both lines)

`qa/yellowback-vault-params.py` today applies R1–R7 to every tag. The rule set will depend on
the stage the tag names (T-8):

| Tag | Required | Not required |
|---|---|---|
| `v6.22.N-betaM` | parity between lines, maturity set, 6.22 version | heights, sets, protocol version |
| `v6.22.N-rcM` | parity; R7 per testnet profile (owner 2026-10-29, amended to T-15): testnet-yb-fast's Vault height and set both set; testnet-yb-slow may have its height without a set (its set follows its activation), never a set without a height; testnet-legacy never a height; R3–R5 (the protocol-version bump to 270200); R6 | R1 and R2 (mainnet height and set stay unset on an rc unless the owner sets them) |
| `v6.22.N` (final) | R1–R7 as today | — |

The protocol-version bump (P8 part D) is therefore **taken with rc1**:
- `UPGRADE_VAULT.nProtocolVersion` = `PROTOCOL_VERSION` = V > 270013, the same on both lines
  and on all three networks.
- `MIN_PEER_PROTO_VERSION` stays at 270013.
- The testnet is the first place the epoch gate disconnects a stale peer. That is a drill
  worth having before mainnet.

### 5.2 Signing and provenance

These are added to `yellowback-release.yml` (T-6):

- **Build provenance** for every package and the bundle manifest, with
  `actions/attest-build-provenance` (SLSA build level 2, GitHub OIDC). Verifiable with
  `gh attestation verify`, no keys to manage.
- **A detached signature on `SHA256SUMS`** with keyless `cosign sign-blob`. The certificate's
  identity is `…/yellowback-release.yml@refs/tags/v…`. Recommended alongside: a minisign key
  held by the owner, for users without the Sigstore tools.
- **An SBOM per package** (syft), attached to the release.
- **Reproducible builds** (Guix, replacing the dead gitian descriptors) are **not** an rc
  requirement. They are recorded as a mainnet-launch item (T-11), because they need two
  independent builders to be meaningful.

### 5.3 The qualification workflow (`rc-qualify`)

`rc-qualify` is a new workflow in `ycash6`. It runs when the release workflow's draft exists,
and on dispatch with a tag. It tests **the released packages**, downloaded from the draft, not
a CI rebuild:

1. **Node suites against the release binary.** It reuses `yellowback-tests.yml`'s functional
   matrix and nightly tier. The shards already consume the build job's `node-bin.tgz`
   artifact. N4 adds an input that takes it from the release package instead (`test_bitcoin`
   is not in the package, so the unit tier still uses a CI build).
2. **Ecosystem walk.** One job brings up the devnet with *every* client at the release-train
   pins (§5.4):
   - `upgrade-walk` with chain-viz, two lightwalletds (fork and baseline) and yolo;
   - YEW's devnet W1/W2/W4/falcon/pqaddr;
   - x402's `test:devnet`;
   - Hawkeye's `demo` scenario against anvil;
   - YecWallet's QTest devnet cases.

   Today these run in five separate repositories (§1.3). This is the first job that holds them
   together. It runs on a large runner. It is allowed to take hours, because it is not in the
   push tier.
3. **Cross-line.** The same devnet with two ycash-dd nodes at the `vault-params/v6.22.N-rcM`
   tag. The three state digests must agree at every 100th height.
4. **Ceremony rehearsal.** The §2.2 ceremony on regtest, with the profile's maturity.
5. **Testnet canary** (from rc2 on, once the testnet exists):
   - deploy the rc image to one canary seed and one canary miner;
   - for 24 h, confirm no fork, no state-digest divergence against the previous rc's nodes, and
     that peers are kept;
   - also run `ycash-bootstrap` against the newest bundle.

**Promotion.** A green `rc-qualify` posts a summary to the draft release. The owner then
publishes the pre-release, which triggers:
- container images (§5.5);
- the rolling testnet upgrade (§6.5);
- the bundle publication for the rc's `H_B`.

A red `rc-qualify` means a new rc number, never a moved tag (the existing rule).

### 5.4 The release train: every component at a named commit

The workspace gains `releases/v6.22.0-rcN.yaml`, one per rc. It names the commit of every
component that the rc was qualified with:
- `ycash6`, and `ycash-dd`'s `vault-params` tag;
- `librustzcash6`;
- lightwalletd-dd, YecWallet, YEW, yolo, chain-viz, x402-ycash, Hawkeye and wyec;
- the workspace commit, for spec copies.

It also records `rpcversion`, the testnet `H_V`, the set id, and the bundle's `H_B`.

`workspace-check.yml` validates:
- every commit exists on that repo's `upgrade/vault`;
- every client's pinned contract copy matches the node's at that commit (the `make spec-check`
  logic);
- `rpcversion` agrees.

`rc-qualify` reads its pins from this file. This replaces the `YOLO_COMMIT`, `CHAINVIZ_COMMIT`,
`LWD_COMMIT` and `WORKSPACE_COMMIT` env pins for the release path only. The push tier keeps its
own pins.

Client repos that ship binaries tag in step. Their tags are `<their version>` with a
`ycashd-6.22.0-rcN` note:
- chain-viz has `release.yml` already;
- yolo and lightwalletd-dd gain the same shape (tarballs plus `.sha256` plus provenance);
- YecWallet takes the node packages as inputs (`doc/yellowback-release.md` "Wallet releases");
- YEW ships to internal and TestFlight tracks.

### 5.5 Container images

`Dockerfile.release` is added on both node lines, beside `contrib/docker/ycashd/Dockerfile`. It
installs the **release tarball** after checking it against `SHA256SUMS`, so there is no second
compile. It uses the same entrypoint.

On publish, images are pushed to **ghcr.io** (`ghcr.io/boyfromcave/ycashd`), tagged `6.22.0-rcN`
and `testnet`. They are signed with keyless cosign and carry the provenance attestation.
`ycash-infra` pulls by digest. ECR stays the EKS mirror (T-12). The same applies to
lightwalletd-dd, chain-viz, yolo and the attest agent.

---

## 6. `ycash-infra`: the testnet environment

### 6.1 Shape

A second chart, **`charts/ycash-testnet`**, holds the network-operator roles. The existing
`charts/ycash-lightwallet` is reused unchanged with `values-testnet.yaml` (`network: testnet`,
release images, `YCASHD_BOOTSTRAP` init) for the public lightwalletd/yindex/web endpoint.

The roles are a separate chart because they hold keys, and the lightwallet chart's rule 4
stays absolute. T-9 records the amendment to `ycash-infra/AGENTS.md`:
- `charts/ycash-testnet` may hold **testnet-only** miner payout, faucet and house-attestor keys,
  from External Secrets;
- a mainnet value set for that chart is refused at render.

Rule 5 (images from the workspace trees) gains its exception for release images: the testnet
runs what was released, by digest.

### 6.2 Components (N3)

| Component | Kind | Notes |
|---|---|---|
| `seed` | StatefulSet, 3 replicas, `podAntiAffinity` by zone; each pod gets a stable public IP (NLB per pod, or a node with hostNetwork on a small dedicated pool) on 18833 | The addresses go into `pnSeed6_test` (N1 follow-up, each rc) |
| `dnsseed` | Deployment of a Ycash-configured seeder (a fork of `zcash/zcash-seeder` set to the new magic and port); NS delegation for the seed hostname (T-3) | Crawls the network and answers A/AAAA |
| `verifier-dd` | StatefulSet, 1 replica, ycash-dd image | Signs bundle statements. Its state digests are scraped (§6.4) |
| `miner` | Deployment, 2 replicas, release image with `-gen -genproclimit=N -mineraddress=<testnet key>` | Until real pools join. Each replica is in a different zone |
| `pool` | Optional yolo Deployment and Service on 3333 | For invited GPU miners at 192,7 |
| `attestor` | One StatefulSet per house seat: the attest agent plus its node, keys from External Secrets | Founding seats only (T-5). Replaces the host-run `kind-personas.py` for testnet. The image comes from `images/personas/`, finished here |
| `bridge-persona` | `bridge-sim` per shape | For G-12, until wyec P5 |
| `faucet` | Deployment, ungated from `regtest.enabled`; per-IP and per-address rate limits; a proof-of-work or captcha challenge; a daily cap | Pays tYEC. It never pays YED: users mint it |
| `explorer` | chain-viz hosted (read-only), plus yindex's address lookups through the web shell | A full block explorer is out of scope (T-13) |
| `snapshotter`, `bundle-verifier` | CronJob, Job | §4.3 |
| `status` | Static page: height, peers, H_V, set id, current rc, bundle, reset notices | Fed by Prometheus |

### 6.3 Network and DNS

Hostnames are T-3. A working set:
- `testseed.<domain>` (DNS seed);
- `testnet-lite.<domain>` (lightwalletd gRPC/gRPC-web);
- `testnet-viz.<domain>`, `faucet.testnet.<domain>`, `bootstrap.testnet.<domain>` (CDN),
  `status.testnet.<domain>`.

`testseed.ycash.xyz` is the Foundation's name. Reusing it needs the Foundation (T-3).

### 6.4 Monitoring and alerts

Alerts are added to the existing kube-prometheus-stack:
- tip age over 15 min;
- fewer than 4 peers on any seed;
- a `getchaintips` fork longer than 2 blocks;
- **`vault_getinfo.statehash` or `yed_getstatehash` disagreeing between any two of our nodes at
  the same height**: the G-10 "no state-hash divergence" metric, measured continuously
  instead of by hand;
- the attestor set's ARMED state, and per-seat liveness;
- faucet balance;
- bundle age.

### 6.5 Operations

- **Rolling upgrade per rc:** canary, then seeds one at a time, then miners, then attestors,
  then the lightwallet endpoint. It is stopped by any §6.4 alert.
- **Reset runbook (T-7):** stop roles, wipe PVCs, run the ceremony, republish the bundle,
  update the status page.
- **Cost:** the lightwallet stack's ≈ $625–645/month (`docs/eks-runbook.md`) plus about
  10 small nodes and a CDN bucket. N3 measures it on kind first and records an estimate before
  the apply.

The first EKS apply (K2) is the owner's, with credentials, and it is on this plan's critical
path.

---

## 7. What the testnet is for: the gates read on it

| Gate | Source | Read on the testnet as |
|---|---|---|
| G-10 | Hardening plan §7 | 4 weeks ARMED with real attestors, no state-hash divergence (§6.4 metric), every A7 drill. Recorded in `doc/yellowback-testnet-v3.md`, renamed `doc/yellowback-testnet.md` |
| G-12 | Upgrade plan P7 | Primitive drills: cancel, equivocation slash, dormancy recovery, wind-down, both bridge shapes, a wrong-price claim cancelled |
| G-11 | Upgrade plan P7 | Cancel inclusion latency on a real block sequence. The testnet's sequence is a proxy only; mainnet observation is still required |
| A7 | v3 | Attestor recruitment, arming, the drill list |
| L4 | lightwalletd plan | Public server against a testnet node; byte-equality against the baseline binary |
| W5 | YEW plan | 4-week testnet run against the public endpoint |
| X-11 | x402 plan | e2e against testnet |
| Protocol-version drill | Upgrade plan P8 part D | A stale-version peer is disconnected at the epoch |
| Bundle | This plan | Two rc cycles of bundles verified by at least 2 independent verifiers, and one cold start from a bundle on each tier-1 platform |

---

## 8. Decisions (owner)

Each decision has a recommendation. Phases that depend on a decision state that dependency in
§9.

| # | Decision | Recommendation |
|---|---|---|
| **T-1** | Revive the old testnet, start a fresh genesis, or re-fork from Zcash testnet | **Re-fork from Zcash testnet at 510,248** (§2.1). Reviving needs a chain nobody can reach. A fresh genesis loses the mainnet-shaped history and the fork code paths, and gives the bundle no external anchor |
| **T-2** | Network identity, and the post-fork YDF addresses | New magic (the old one is Zcash testnet's), ports unchanged, datadir `testnet4`, selected by `-testnet`. Keep the old YDF testnet addresses, or replace them with workspace-held testnet keys: recommended **replace**, so the testnet's development-fund outputs are spendable in drills |
| **T-3** | Domains and seed hostnames; the Foundation's `testseed.ycash.xyz` | **Decided (owner 2026-10-29).** A workspace-owned domain (not ycash.xyz), registered with WHOIS privacy; its name lives only in `ycash-ops`. Hostnames per network (`lite-fast.`, `lite-slow.`, `lite-legacy.`, `viz-*`, `faucet-*`, `status.`). No DNS seed (fixed seeds, D1) |
| **T-4** | Testnet `nVaultMinSetMaturity` | **1,152 (≈ 1 day).** Mainnet's 16,128 is tested by regtest suites with the value as a parameter, and the parity check compares mainnet. Testnet's job is the drill cadence, including resets |
| **T-5** | Founding attestor set | **Decided (owner 2026-10-29).** testnet-yb-fast: 7 house seats, keys generated into the cluster secret store. testnet-yb-slow: 3 house seats at launch, 4 invited operators added as recruited (house seats fill in until then). G-5's "≥ 7 operators" is read on slow |
| **T-6** | Signing | **Decided (owner 2026-10-29).** GitHub provenance plus keyless cosign for all assets; the owner's minisign key (`02C923A6C593AF18`, public key `RWQYr5PFpiPJAigk86vf89bPYrJCXj5tskgRAPRYFsEXyciZo8dveOGQ`; replaced the first key the same day) signs `SHA256SUMS`, automatically from a `ycash-ops` workflow (secret key in its secrets) and by hand with a local script when needed. Testnet bundle statements: 2 house verifier keys (relaxed); at least one outside verifier is a mainnet requirement |
| **T-7** | Reset policy | Reset on any history-invalidating rule change before mainnet. Never reset after the mainnet height is set |
| **T-8** | Stage-aware release rules, and taking the protocol-version bump at rc1 | Yes (§5.1) |
| **T-9** | Amend `ycash-infra` rules 4 and 5 for `charts/ycash-testnet` | Yes, scoped to testnet keys and release images |
| **T-10** | YecWallet fast start from a bundle | After two rc cycles of bundles. Not in the first rc |
| **T-11** | Reproducible builds | A mainnet-launch item, not an rc item |
| **T-12** | Registry | ghcr.io public, ECR as the EKS mirror |
| **T-13** | Explorer | chain-viz plus yindex for testnet. A full explorer is a separate proposal |
| **T-14** | Names and selection of the three testnets (revision 3) | **Decided (owner 2026-10-29).** `testnet-yb-fast`, `testnet-yb-slow`, `testnet-legacy`; `-testnet -testnetprofile=<fast\|slow\|legacy>`, required, compiled-in; `NetworkIDString()` stays `"test"`. Magics `f77962d3` / `d4` / `d5`; ports 18833 / 18933 / 19033 (RPC one below) |
| **T-15** | When `testnet-yb-slow` activates Vault | **Decided (owner 2026-10-29).** About a week of blocks after its launch, set by its first rc, so the activation is rehearsed live as on mainnet. fast activates at 510,400; legacy never |
| **T-16** | fast's other YED block windows | **Decided (owner 2026-10-29).** Scaled down in a fast column in the node's parameters by one stated rule, every invariant asserted, so dormancy, revival and seat aging are testable in hours |
| **T-17** | Seed shape | **Decided (owner 2026-10-29).** 2 hosts, each serving all three networks (`t3a.medium`); host count is a variable |
| **T-18** | Mainnet seed readiness | **Decided (owner 2026-10-29).** `main` is a profile of the same module; a separate stack, state and account, applied only through an approval-gated GitHub Environment; nothing created before P8 |
| **T-19** | Services per network | **Decided (owner 2026-10-29).** Seeds, lightwalletd, faucet and chain-viz on all three; YED personas and attestor sets on the two `yb` networks |
| **T-20** | Kubernetes (EKS) for the testnets | **Decided (owner 2026-10-29).** One cluster, a namespace per network, deployed from `ycash-ops` like the seeds; up for campaigns and the rc soak, down otherwise; mainnet a separate approval-gated cluster in its own account, nothing before P8 |

---

## 9. Phases

| Phase | Content | Depends on | Can start now? |
|---|---|---|---|
| **N0** decide | §8 answered; this plan revised; a row in the plans README | — | **Yes** |
| **N1** node params (both lines) | §2.1 parameters, including the 510,247 checkpoint taken from the prefix (which `ycash-infra` produces in N3); pinning the prefix's `SHA256SUMS` hash in `ycash-bootstrap`; the post-fork height audit plus a unit test; `-stopatheight` (§4.3, review gate); the mapping §22 row; the profile files (§3.1). Branch `up/testnet-params` off `upgrade/vault` in `ycash6` and `ycash-dd`, merged after ycash6#63 and ycash-dd#141. The ceremony build is this branch with `H_V` set | N0 (T-1, T-2, T-4) | **Write now**, merge after the open PRs |
| **N2** tooling | `yellowback-devnet --network`, join mode, the walk marked per network; `contrib/testnet/ceremony` (regtest rehearsal green); `ycash-bootstrap` plus the entrypoint `YCASHD_BOOTSTRAP` (proven against a regtest bundle); `Dockerfile.release` on both lines | N1 profile format | **Yes**, on regtest |
| **N3** infra | `testnet-prefix.yml` (harvest, the import legs on both lines including `-checkpoints=0`, publish); `charts/ycash-testnet` (§6.2), `values-testnet.yaml`, personas image, the faucet ungated, the snapshotter, the alerts, the status page; everything green on kind with a *private* testnet (`-connect` only, the N1 ceremony build); the AGENTS.md amendments (T-9); then the EKS apply (owner, K2) | N0 (T-3, T-9, T-12); N1 for the kind run | **Yes**: chart, images and snapshotter against regtest/kind now |
| **N4** release CI | Stage-aware rules (§5.1) and the protocol-version bump; provenance, cosign, SBOM; `rc-qualify` steps 1–4; `releases/*.yaml` and its check; ghcr push; client release workflows (yolo, lightwalletd-dd) | N0 (T-6, T-8); the open PRs merged before the version-rule change lands | **Yes**, on `ci/rc` branches |
| **N5** clients | §3.3 values that do not depend on the set id (endpoints, profiles, e2e targets) | N3 hostnames | After N3 picks hosts |
| **N6** launch | Ceremony on EKS; tag `vault-params/v6.22.0-rc1` then `v6.22.0-rc1` with the set id, the checkpoint and the first bundle; publish; open the seeds; YEW's compiled testnet values; announce | N1–N5; K2 applied | — |
| **N7** operate | rc2+ through `rc-qualify` including the canary; bundle per rc; recruit attestors to G-5; run the G-10/G-12 drills; mainnet bundle once the format has passed two cycles | N6 | — |
| **N8** hand-off to P8 | The gates of §7 recorded; the mainnet release (final rules R1–R7) uses the same pipeline | N7, ≥ 4 weeks ARMED | — |

**Rough calendar, if N0 is answered this week:**

| Weeks | Work |
|---|---|
| 1 | `ycash-infra` `testnet-prefix.yml` (harvest, import on both lines against today's binaries, publish `testnet-prefix-v1`). Needs no node change. Starts N1 and N3 |
| 1–3 | N1–N4 in parallel |
| 3–4 | Private testnet on kind, then on EKS |
| 4 | N6 launch: rc1, after one maturity period of the ceremony (≈ 1 day at T-4's value) |
| 5–9 | N7's four weeks ARMED, at the earliest |

The long poles are outside the code:
- the EKS apply (credentials);
- the Foundation's DNS name (T-3);
- recruiting the invited attestors (T-5).

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| A missed post-fork height constant splits the two lines at the fork or at Canopy | The N1 unit test asserts the subsidy and outputs at 510,248 and at the first Canopy block on both lines. The ceremony runs a ycash-dd node from the prefix |
| One of the lines rejects some Zcash testnet block that the other accepts (a pre-fork rule difference between the v4.5.0 and 6.20.0 lineages) | The N1 `-checkpoints=0` import on both lines. A divergence is a finding against that line, recorded in mapping §22 |
| The harvested prefix is wrong (a bad source node) | Every 400th hash checked against Zebra's source checkpoints, plus the compiled 38,000 / 207,500 / 280,000; byte-identical reruns by others; full validation on import |
| The ceremony build (Vault height, no set) is mistaken for a release | It is never tagged or published. R7 tightened at rc (§5.1) refuses it. The P8 `InitError` lands with rc1 |
| The workspace dominates the testnet: house miners and house attestor seats | Stated on the status page. G-5 and G-4-style readings exclude house seats. Invited operators are on the launch checklist |
| A bundle with a bad state is published | Three anchors (§4.2). The node refuses a tip that is not the checkpoint. Verifiers must agree byte for byte. `--verify-full` is there for the doubtful |
| Testnet resets erode participation | Resets only for history-invalidating changes (T-7); each is announced with its rc; the ceremony is scripted, so a reset costs one maturity period |
| CI cost and duration of `rc-qualify` | It runs per rc, not per push, and on large runners. Steps 1–4 are parallel jobs. Step 5 is wall-clock, not compute |
| The Foundation's seed name stays unavailable | A workspace domain, plus fixed seeds compiled into each rc |
