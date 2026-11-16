# Item 17: the fast-testnet light-wallet server, acceptance record

Beta3 item 17 (`docs/plans/beta3/beta3-plan.md`): a lightwalletd for the fast testnet at
`fastnet-lightwallet.ycash.team`, with the YEW core and the hosted web wallet
(`fastnet-wallet.ycash.team`) sending shielded YEC through it.

This record was written on 2026-11-16 from the run logs and screenshots kept on the machine that ran
the checks, and from public lookups made the same day (the host's `GetLightdInfo`, the fast-testnet
explorer's transaction API, the snapshots front). It holds no seed, key, viewing key, passphrase,
wallet address or IP address. All times are UTC.

**The node behind the host was ycashd 6.22.0-beta2 when these checks ran.** They show that the
server, the core and the web wallet work together on beta2; they say nothing yet about beta3. The
check is to be repeated after the beta3 rollout of the light-wallet host (the section at the end).

## What was running

| Part | Value | How it was read |
|---|---|---|
| Light-wallet server | `https://fastnet-lightwallet.ycash.team` (TLS, gRPC and gRPC-web) | the wallets' server setting |
| lightwalletd | lightwalletd-dd `2d457b4d4` (on `upgrade/vault`, 2026-11-13), vendor "ECC LightWalletD" | `GetLightdInfo.version`, 2026-11-16 15:5x |
| Node behind it | ycashd `v6.22.0-beta2`, subversion `/YcashCpp:6.22.0-beta2/` | `GetLightdInfo.zcashdBuild`, `zcashdSubversion` |
| Chain | `test` (testnet-yb-fast), consensus branch `6d5b7a31` | `GetLightdInfo.chainName`, `consensusBranchId` |
| Host's first-start source | the `testnet-prefix-v1` prefix bundle: `SHA256SUMS` pin `c7b55a2a6770df8108d910572cca2dbf643a0418eb0b2d556879928a43cbc403`; its `manifest.json` sha256 `7026607bd21d9b34c0bd7736ec3ff14f3882628c98c62228c8ac2e85eb7ccea5` | the deployment's pin; `manifest.json` fetched from `https://snapshots.ycash.team/prefix/testnet-prefix-v1/` |
| Web wallet | `https://fastnet-wallet.ycash.team` (YEW web, served on the light-wallet host's origin); run 1 loaded `assets/index-XwgC5bft.js` | the browser's resource timing |

The host was deployed by the private operations repository's `deploy` workflow (layer
`lightwallet`, network `yb-fast`); its image digests are pinned there.

## Run 0: the YEW core (command line), 2026-11-15

Two wallets, A and B, made with the YEW core's command-line shell against the host (the core is the
same Rust library the mobile app and the web wallet use). Both synced to the tip (511,352 at the
start) on branch `6d5b7a31`.

| What | Result |
|---|---|
| A sends 2.00000000 YEC, Sapling to Sapling, to B, memo "fastnet acceptance, core", fee 1,000 zat (0.00001 YEC) | proved in 2.4 s, broadcast |
| txid `094038e6c398f90367940647405799924a2d9576e6c9d5f09649858f8e4a14b0` | **mined at height 511,359** (block `07f2a3ecd8fd…b059d013`, 2026-11-15 12:23:34), 1 Sapling spend, 2 Sapling outputs, no transparent part, value balance 0.00001 YEC (= the fee) |

## Run 1: hosted web wallet, headless Chrome, 2026-11-16 09:27–09:39

A fresh browser profile per step; the scripted steps and their logs are s1–s6 of that run.

| Step | Result |
|---|---|
| Load `fastnet-wallet.ycash.team` | first render 1.2 s; only the wallet's own origin contacted; the fast-testnet banner shows ("coins here have no value") |
| Create a wallet | onboarding 5.8 s, home synced 23 s later |
| Restore B from its recovery phrase | server prefilled `https://fastnet-lightwallet.ycash.team`, "Server ok · tip 511638"; synced in 22.8 s; balance 0.99999000 YEC private, equal to the core's view of B |
| Send 0.1 YEC from B, Sapling to Sapling, memo "hosted fastnet accept" | proving files fetched in 13.5 s (51.6 MB, then cached); preview fee **0.00001000 YEC**; prove and broadcast 28.3 s |
| txid `ba35110245f33755629195afd20a158f5f22a0db0ed8940184311ece76a76e6e` | **mined at height 511,639**, the first block after the send (tip 511,638 at sending), block `00b4bff0ffdd…04c0afd2`, 2026-11-16 09:45:39; 1 Sapling spend, 2 Sapling outputs, value balance 0.00001 YEC |
| Balances after mining (core, synced to 511,800) | A 4.09999000 YEC, B 0.89998000 YEC: B paid 0.1 + 0.00001 fee, A received 0.1 |
| Hard reload mid-sync (A) | the wallet locks, unlocks, resumes the sync (18.2 s), balance and history intact |
| Server setting | other servers cannot be reached: `https://example.com`, a public lightwalletd, a look-alike host name ending in another domain are blocked by the page's content security policy; `http://127.0.0.1:9067` and `not a url` are refused as invalid |

Minor findings of this run (the favicon 404, rough edges in the server step) were fixed in yew #51
before run 2.

## Run 2: hosted web wallet after yew #51, headless Chrome, 2026-11-16 13:37–13:47

| Step | Result |
|---|---|
| Create a wallet | the server step is read-only and names `https://fastnet-lightwallet.ycash.team`; the favicon loads (200). The passkey lock was not exercised (headless; the prompt was cancelled) and the passphrase lock was used |
| Receive screen | the private (Sapling), public, post-quantum (FN-DSA-512, `tqf…`) and YED (`ytf…`) codes all render |
| Reopen A and B (profiles from run 1) | unlock and sync in about 19 s each; balances 4.09999000 and 0.89998000 YEC, as the core reports; a second tab is refused ("This wallet is open in another tab or window") |
| Restore B again and send 0.05 YEC, memo "hosted fastnet acceptance 2" | preview fee **0.00001000 YEC**; prove and broadcast 27.7 s; txid `a85bd841aa5d9158d32b7f59a0a5cb01c49b02cd37b34ba6053a9a5b1531edd0` |
| Mined? | **Not mined when this record was written.** The fast testnet's last block was 511,800 at 10:41:41, three hours before the send; no block had been found since (15:56). The explorer reports the transaction with no block and expiry height 511,841. It is mined, or it expires, when blocks resume |
| Stored wallet | IndexedDB holds the phrase only encrypted (no word of the phrase found in the dump); the address after reload equals B's |

## What this does and does not show

- Shown on beta2: the host serves the fast testnet over TLS to the core and to the hosted web wallet;
  a wallet created, restored and reloaded in the browser sees the same balances as the core; two
  shielded sends through the host were mined (run 0 and run 1), the second in the block after it was
  sent; the fee shown before sending is 1,000 zat, Ycash's Sapling fee.
- Not shown: the mobile app's own shell against this host (only its core, through the command line);
  the passkey lock (needs a real authenticator); the second web send's confirmation (the network had
  stopped mining); anything about the beta3 node.

## After the beta3 rollout (to be filled in)

Repeat runs 0 and 1 against the host once it runs ycashd 6.22.0-beta3, and the mobile app if it can
be run against the host. Record the same fields.

| Field | Value |
|---|---|
| Date and time (UTC) | |
| `GetLightdInfo`: lightwalletd version, `zcashdBuild`, `zcashdSubversion` | |
| Host's restore source (bundle, `SHA256SUMS` pin or manifest hash) | |
| Web wallet build (yew commit or asset name) | |
| Core send: txid, height, fee | |
| Web send: txid, height, fee | |
| App send (if run): txid, height, fee | |
| Balances after, as the core sees them | |
| Findings | |
