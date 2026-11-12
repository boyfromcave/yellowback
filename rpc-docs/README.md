# rpc-docs — the Ycash RPC reference at rpc.ycash.team

Every RPC of the Ycash node, as each release's own `ycash-cli help` prints it, one page per method,
with the vault and Yellowback RPC contracts (`doc/*-rpc-contract.json`) beside the help text. Every
release keeps its own pages, so an integrator on a beta reads the beta's RPCs, not the latest ones.
Modelled on Zcash's [RPC docs](https://zcash.github.io/rpc/) ([generator](https://github.com/zcash/rpc)),
plus versions, channels, a per-release change log and curated sections (post-quantum, vault,
Yellowback).

Plain static HTML, CSS and a little optional JavaScript; the generator is Python standard library
only. Nothing runs at serve time.

## Publishing a release's RPC docs

Three steps per node release (a beta, a release candidate or a general release):

1. **Capture** the release's RPC surface. From the workspace root, with the node repository's tag
   fetched (`git -C ycash6 fetch --tags`):

   ```bash
   # from the published image of the tag's commit (no Docker needed: the layers are read directly)
   make rpc-docs-capture VERSION=v6.22.0-rc1 IMAGE=ghcr.io/boyfromcave/ycashd:ycash6-<sha12 of the tag>
   # or from binaries you built from the tag
   make rpc-docs-capture VERSION=v6.22.0-rc1 BIN=ycash6/src COMMIT=v6.22.0-rc1
   ```

   This starts a throwaway regtest node (wallet on, the vault upgrade and a placeholder YED
   attestor set configured, so the Vault and Yellowback categories register), writes
   `versions/<version>/help/*.txt` (the output of `help` and of `help <method>`), copies the RPC
   contracts from the tag into `versions/<version>/contracts/`, and records the binary, the tag
   and their commits in `versions/<version>/source.json`. It takes a few seconds.

   The binaries must be built from the tag's commit. When no build of the tag exists, binaries of a
   later commit may stand in if the RPC sources did not change in between; pass
   `MISMATCH="<why>"`, and the reason is recorded in `source.json`.

2. **Review** with `make rpc-docs-serve` (http://localhost:8001). The new version's
   *Changes* page lists every added, removed and changed RPC against the previous release.

3. **Open a pull request** with the new `versions/<version>/` directory. Its diff is exactly the RPC
   text that changed. Merging to `upgrade/vault` publishes the site (`.github/workflows/rpc-docs.yml`).

A published snapshot is never edited: its pages stay at `/<version>/` for good. `capture.py --force`
replaces one only to correct a bad capture.

## Versions and channels

| URL | Serves |
|---|---|
| `/v6.22.0-beta1/` | that release, permanently |
| `/beta/` | the newest release of any stage |
| `/rc/` | the newest release candidate or general release |
| `/stable/` | the newest general release |
| `/` | `stable`, or `beta` before the first general release |
| `/versions.html` | every release and channel |

Versions are the node line's release tags (`vX.Y.Z`, `vX.Y.Z-betaN`, `vX.Y.Z-rcN`), ordered beta <
rc < general release. The channels move by themselves when a newer snapshot lands. To hold one
back, pin it in `site.json`: `"channels": {"stable": "v6.22.0"}`.

A channel page is a copy of its version's page, with a banner and a canonical link to the
permanent `/<version>/` page, so deep links like `/rc/vault_lock.html` work. The version picker
keeps the reader on the same method when switching versions.

## Addresses

`site.json` `receive` is the page at `/<version>/addresses.html`: one place that says which call
creates an address for YEC and which creates one for YED, and which address types are supported.
The call named there is the one that works on Ycash: where a release's inherited help calls it
deprecated (`getnewaddress`, `z_getnewaddress` in v6.22.0-beta1; from beta2 the help says
"Supported on Ycash"), the entry's `note` says why it is still the call to use.

Releases differ, so a `summary` or `note` may be a list of variants, each `{"text", "since"?,
"until"?}`; the variants whose range holds the release are joined. `steps` take `since`/`until`
too. A variant that says what the node's help says names the words it relies on in `helpSays`, and
the build fails when the help of that call, in a release the variant is shown for, does not
contain them: a reworded help cannot leave a stale note behind. A test refuses a note that cites
the help without `helpSays`. A method is named there and also in its `help` category. It is not copied into a second
category. `otherKeys` holds keys that are not receive addresses (the vault owner).

`site.json` `unavailable` lists the methods a Ycash node refuses (the unified-address account calls,
which need NU5) and the reason. Each gets a notice above its help text and a line on the addresses
page. Add a method there only after reading the refusal in the node source.

## Moving YEC between address types

`site.json` `moving` is the page at `/<version>/moving.html`: for each node line (ycashd 6.22,
ycashd on 4.5.0, kogany with `yewd`) which call moves YEC from each address type to each, where
the change goes, how to fund a vault from each type, how to read balances by type, and the
scheme-visible post-quantum prefixes (D-9). It is shown from the release named by `since`, and
only there; the page and the addresses page link each other. Each section is `paragraphs` and
`tables` (`columns`, `rows`, `notes`); cells take `` `code` `` and `**bold**`; the build refuses a row
whose cell count differs from its columns.

A statement that rests on work not yet merged carries `"pending": "<what is missing>"` and a
`pendingText` the reader sees. `build.py` prints every pending marker; when the work lands, delete
the marker (and the `pendingText`) and reword the section. `source` records which merges a section
describes; it is not rendered.

## Sections

`site.json` `sections` defines the featured groups on each version's overview and the badges on
method pages. A section with `categories` takes every method in those `help` categories (`Vault`,
`Yellowback`). A section with `methods` is a curated list; a listed method a release does not have
is skipped for that release. A method belongs to one section, so the overview lists it once.

## Layout

```
rpc-docs/
├── versions/<version>/   one release: help/*.txt, contracts/*.json, source.json (capture.py writes it)
├── site.json             title, domain, sections, channel pins
├── capture.py            node -> versions/<version>/
├── fetch_image.py        public container image -> binaries, without Docker
├── build.py              versions/ -> _site/ (gitignored)
├── template.html         the page frame
├── assets/               site.css, site.js, favicon.svg
└── test_rpc_docs.py      unit tests (make rpc-docs-test)
```

## Hosting

GitHub Pages serves the site from this public repository. `.github/workflows/rpc-docs.yml` runs
the tests and the build on every pull request touching `rpc-docs/`, and deploys on `upgrade/vault`.
TLS is GitHub's, issued and renewed automatically. The only AWS piece is DNS: a CNAME in the
`ycash.team` Route 53 zone.

One-time setup:

1. **Pages source:** repository *Settings → Pages → Build and deployment → Source: GitHub Actions*.
2. **Verify the domain on the account**, so no other GitHub account can claim a `ycash.team` name
   on Pages: *profile Settings → Pages → Add a domain → `ycash.team`*. GitHub shows a TXT record
   (`_github-pages-challenge-boyfromcave.ycash.team` and a value); create it in Route 53 (below),
   then click *Verify*.
3. **The CNAME**, in the `ycash.team` hosted zone (CloudShell in the account that holds the zone,
   or the Route 53 console):

   ```bash
   ZONE_ID=<the ycash.team hosted zone id>
   aws route53 change-resource-record-sets --hosted-zone-id "$ZONE_ID" --change-batch '{
     "Changes": [{"Action": "UPSERT", "ResourceRecordSet": {
       "Name": "rpc.ycash.team", "Type": "CNAME", "TTL": 300,
       "ResourceRecords": [{"Value": "boyfromcave.github.io"}]}}]}'
   dig +short rpc.ycash.team   # boyfromcave.github.io. and GitHub's addresses
   ```

4. **Custom domain:** repository *Settings → Pages → Custom domain: `rpc.ycash.team`*, then, once
   the certificate is issued, tick *Enforce HTTPS*.

The EKS cluster's external-dns also writes into the `ycash.team` zone, but with `policy: sync` it
only changes records it owns (its TXT ownership records), so it leaves `rpc` alone. No cluster
Service or Gateway may claim the `rpc.ycash.team` hostname.

## Scope

The versions are the release line's (`ycash6`, 6.22.x on `upgrade/vault`). The `ycash-dd` line and
`kogany` expose slightly different surfaces; either can get its own snapshots under a `line` of its
own later. The capture records `line` in `source.json` for that.
