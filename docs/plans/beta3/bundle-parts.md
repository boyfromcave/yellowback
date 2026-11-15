# Snapshot bundles in parts (beta3 item 9, design note N-3)

Status: design note, Wave 0 (`beta3-plan.md` chunks N-3, 8 and 9; `wt/beta3-list.md` item 9).
Read-only: nothing here has changed any repository yet. Chunk 9 implements it after chunk 8.

## 0. Conclusion first

**Yes: stronger compression alone would keep the bundle under 50 GB for years. This note still
recommends parts, with the compressor unchanged, because parts remove the limit instead of
postponing it and add no new dependency for any reader. Neither change is urgent.**

- Measured on the real 3,100,949 insight datadir and extrapolated by kind (§6), the 41.8 GB
  bundle (`gzip -6`) would be:
  - about 38 GB with zstd -3;
  - **about 34 GB with zstd -9** (-20 %, and faster to pack than gzip);
  - about 31 GB with zstd -19 (4x slower than gzip, even with three threads);
  - roughly 27 GB with zstd -19 `--long=27` (-35 %, 2.7 hours with three threads). The long-range
    gain is concentrated in the insight index and depends on the sample.
- Chain growth is slow. From 2,800,000 to 3,079,999 (eight months) the `full` bundle grew
  266 MB, and from 2,275,000 to 2,800,000 it grew 829 MB. The `full-insight` bundle is 1.71x
  `full`. So the insight bundle grows by about 0.5–1.1 GB a year at today's activity: it would
  reach 45 GB in 3–6 years and 50 GB in 7–16. With zstd -9 the headroom to 50 GB is about 16 GB,
  which is decades at that rate.
- Why parts anyway:
  - **A limit postponed is still a limit.** A vault-era rise in activity, or LevelDB's layout
    varying between captures, only moves the date. (The `full` bundle *shrank* 9 MB between
    3,079,999 and 3,087,294.)
  - **zstd adds a dependency to every reader, parts add none.** Python's standard library reads
    zstd only from 3.14, so `verify.py` and `ycash-bootstrap` would need the `zstd` binary, and so
    would the Docker image and every manual restore. Parts need only what is used today.
  - **Parts bring their own gains**: resumable, verified-per-gigabyte downloads, and a restore
    that needs one part of extra disk instead of the whole bundle (§2).
- **Decision for the lead architect** (B3-D-new; this note's recommendation in bold):
  (a) **parts in beta3, gzip unchanged**;
  (b) zstd -9 instead of parts;
  (c) defer item 9, given the growth figures.
  A later format revision can still adopt zstd -9 on top of parts, to cut CDN transfer by about
  a fifth; it is not needed for item 9.

## 1. The format: `ycash-state/3` (a bundle in parts)

**Version.** FORMAT.md says a change under "Contract" is a new format version. `ycash-state/3` is
`ycash-state/2` with the tarball split into parts. Nothing else changes: the tar stream, the
encoding, the statements, the tree hash, the pins and `treestate.json` stay as they are. The
kogany formats are left alone (`kogany-state/2`: 22 GB archive, 5.4 GB pruned, far below the
limit). The same extension is written generically so that `kogany-state/3` can adopt it word for
word when it is needed.

**The stream is unchanged; only the storage is cut.** The producer writes exactly the bytes a
`/2` tarball would hold, the same GNU tar piped through `gzip -n -6`, and cuts them into
consecutive byte ranges. Concatenating the parts in order gives, byte for byte, the tarball a
`/2` producer would have written from the same datadir. Parts are not separate tar or gzip
members. This keeps reproducibility, `tree_sha256` and the encoding text of v1/v2 unchanged. It
also lets the published 41.8 GB `/2` bundle be re-cut later without repacking. Its whole-stream
`sha256` stays `5f866db5…0dd5`, though it would need a new `SHA256SUMS` and signature.

**Part naming.** `<tarball>.<NNN>`: three decimal digits, from `000`, e.g.
`ycash6-main-3100949-full-insight.tar.gz.000` … `.039`. Every name matches the restorer's file-name
rule (`[A-Za-z0-9][A-Za-z0-9._-]*`), so it is safe to use as a path or a URL. It sorts in stream
order bytewise, and it is what `split -a 3 -d` would write. The limit is 1,000 parts (1 TiB at
1 GiB).

**Part size: `part_bytes` = 1,073,741,824 (1 GiB).** Every part is exactly `part_bytes` long
except the last, which is 1..`part_bytes`. A `/3` bundle always has at least one part. The reasons for 1 GiB:
- It sits far below the CDN's 50 GB object limit, which then stops mattering at any chain size.
- A failed part costs at most 1 GiB to fetch again. The restorer streams with only one part on
  disk (§2), so the part size is also the restorer's disk overhead.
- It is under GitHub's 2 GiB release-asset limit, so the optional release mirror (FORMAT v1,
  "Where it is published") can carry the whole bundle again.
- Each part fits a single S3 PUT (5 GiB). Publishing a part needs no multipart upload.
- The object count stays small: 39 parts for today's insight bundle, and 23 for `full`.
A smaller size multiplies objects and requests for no gain. A larger one only brings back the
problems above. The size is a manifest field, not a constant, so a reader never assumes it.

**`manifest.json`** (canonical, as v2) carries v2's fields, with `format: "ycash-state/3"`, plus
these:

| Field | Value |
|---|---|
| `tarball`, `sha256`, `bytes` | unchanged meaning: the name, SHA-256 and size of the **whole stream** (the concatenation). No object of that name is published |
| `part_bytes` | `1073741824` |
| `parts` | `[{"name": "<tarball>.000", "bytes": n, "sha256": hex}, …]` in stream order. The names must be `<tarball>.000` … consecutive; the sizes must follow the rule above and sum to `bytes` |
| `unpacked_bytes` | sum of the regular files' sizes in the tar (the datadir it restores to). The restorer's disk check and the site's "needs X GB free" read it |

**`SHA256SUMS`** has v2's rule unchanged: it lists every *file in the directory* except the
signatures, sorted bytewise. For `/3` that means the parts, `manifest.json`, the statements and
`treestate.json`. It never lists the whole stream, because that is not a file there, and so
`shasum -a 256 -c SHA256SUMS` works as it does today. Each part's line must equal its
`parts[].sha256`.

**Signature.** As v1/v2: `SHA256SUMS.minisig` (the release key) signs `SHA256SUMS`. That covers
each part directly by its line. It covers the manifest by its line, and through the manifest the
part list, `part_bytes`, `unpacked_bytes`, the whole-stream `sha256`/`bytes` and `tree_sha256`. One
signature anchors everything, and nothing new is signed.

**`verify.py`** accepts `/3` and checks:
- the field rules above;
- `SHA256SUMS` lists exactly the parts plus v2's other files;
- each part's size and hash;
- the whole-stream hash, by hashing the parts in order (one sequential read, which it already
  does for the one-file tarball);
- with `--tree`, the tree hash read through a reader that chains the parts.

It also refuses any file in a bundle directory larger than `part_bytes` in `/3`, and any file over
49 GiB in any format. That guard makes the CDN limit a checked rule rather than a hope.

## 2. The restorer (`ycash-bootstrap --state`)

Today `ycash-bootstrap` restores only `ycash-state/1` (the testnets). It downloads the whole
tarball and then extracts it, so it needs the bundle plus the datadir on disk. The entrypoint
refuses `YCASHD_BOOTSTRAP` on mainnet, and mainnet users follow the site's manual steps. Chunk 9
makes it read **`ycash-state/2` and `/3` on `--network main`**, and makes the tarball path
streaming for every format. Chunk 8 is done first, and its behaviour stays: an import node that
ignores peers, a non-zero exit, and a refusal marker the entrypoint will not start past.

The order of work below is also the order of trust:

1. **Source.** A source that ends in `latest/` or `latest/manifest.json` is read for `height`
   only, and then re-based to `../<height>/`. Every later file comes from the height directory.
   `latest/` holds only `manifest.json` (FORMAT "Where it is published"), and its short cache TTL
   means it can change while a restore runs. It is never trusted beyond naming a height. Today's
   `--source <base>/<net>/latest/` fails for exactly this reason, because there is no
   `SHA256SUMS` at `latest/`.
2. **Anchors.** The restorer reads `SHA256SUMS`, checks `SHA256SUMS.minisig` against the release
   key (required on mainnet; `--require-signature` becomes the default there), and checks
   `manifest.json` against its line. It then checks the manifest itself: the format, the network,
   `line`, the flavour, and the pins against the release's own compiled checkpoints. It checks
   `parts` against `SHA256SUMS` and the size rules. A `/2` manifest is treated internally as one
   part (`[{name: tarball, bytes, sha256}]`), so there is a single code path. Statements and
   `treestate.json` are each checked against their line.
3. **Disk.** The restorer refuses up front, with numbers, unless free space on the datadir's file
   system is at least `unpacked_bytes` + `part_bytes` + 1 GiB. For `/2` it uses `2 × bytes` as the
   estimate.
4. **Stream.** One extractor reads a file-like object that serves the parts in order. It uses
   `tarfile.open(fileobj=…, mode="r|gz")`, the streaming mode, instead of today's `"r:gz"`, and
   keeps `extract_state`'s entry rules. For each part `i`:
   - fetch it to `work/<name>.part`;
   - check its size and SHA-256 against the signed line, **before any byte of it reaches the
     extractor**;
   - rename it to `work/<name>`, serve it, and delete it.
   Disk overhead is one part. While the extractor reads, a second worker may fetch part `i+1`
   (two parts on disk; optional). The extractor also updates the whole-stream hash and a tree hash
   (`<sha256>  <path>` per regular file, in tar order, as FORMAT v2).
5. **Resume a failed part.**
   - An interrupted transfer continues with `Range: bytes=<have>-`. A 206 response appends to the
     partial file. A 200 response restarts the part from 0, for a server that ignores ranges.
   - Each part gets five attempts with backoff. The extractor just waits on its pipe meanwhile.
   - A complete part whose hash is wrong is deleted and fetched once more from 0. A second mismatch
     is a `BundleError`.
   - A `/3` part is never larger than `part_bytes`, so a server sending more is cut off and
     refused.
6. **Staging, then install.** Entries are extracted under `<datadir>/.bootstrap-staging/`, never
   into the live tree (mainnet strips `main/` as `tar --strip-components=1` does).
   - Nothing there is trusted until the end of the stream. At that point the stream's total
     `bytes`, whole-stream `sha256` and tree hash must equal the manifest's, and nothing may
     follow the end of the tar.
   - Only then are `blocks/`, `chainstate/`, `vaults/` and `yellowback/` renamed into the datadir.
     This is the same file system, so each rename is atomic per directory.
   - Then the node's offline check against the statement at `H` runs (as `check_state` does
     today). For a `full-insight` bundle it runs with `-experimentalfeatures -insightexplorer
     -txindex`.
   - Any failure removes the staging directory and the installed directories, and leaves chunk
     8's marker behind.
7. **Interruption of the whole process.** A gzip stream cannot be resumed in the middle, so a
   re-run starts extracting from part 0 again, with the staging directory wiped first. To avoid
   fetching again what was already extracted, `--keep-parts` keeps the verified parts in `work/`.
   That costs the bundle's size in extra disk, and a re-run then reads them locally (their hashes
   are checked again). A `--source` that is a local directory of parts downloaded by hand works
   the same way: the restore runs offline and still uses only one part's worth of extra disk.

`ycash-bootstrap` is byte-identical on ycash-dd and ycash6 today, so it stays identical: the
ycash-dd PR comes first and the ycash6 twin follows (reference order). The state restore is still
a ycash6 datadir. A ycash-dd node does not start from it (FORMAT v1), so the offline check needs
ycash6's `--ycashd`.

## 3. The publisher

**Splitting while packing (`mainnet/snapshot.py pack`).** `pack_tree` already pipes its GNU tar
stream through `gzip -n -6`, but gzip writes straight into one `.tar.gz.part` file. Instead,
gzip's stdout becomes a pipe that a `PartWriter` reads. The `PartWriter`:
- writes `<tarball>.<NNN>.part`;
- rolls over to the next part at exactly `part_bytes` (`--part-bytes`, default 1 GiB; tests pass
  a few KiB);
- renames each finished part into place;
- hashes each part and the whole stream as it goes.

`pack.json` records `parts`, `part_bytes`, the whole `sha256`/`bytes`, `unpacked_bytes` and
`tree_sha256`. No whole tarball and no second copy is ever on disk: the bundle directory holds the
parts, which take the same total bytes as today's single file. `finalize` writes the `/3`
manifest from `pack.json`. It does not hash the parts again, because `verify.py` does that
independently. `write_sums` is unchanged, since it already lists every file in the directory.
From beta3 on, the producer writes **only `/3`**, including bundles of one part. A single path
means the parts code is exercised by every bundle rather than discovered broken at 50 GB.

**Uploading (`mainnet/publish-s3.sh`).** It runs `verify.py` first, as today, so an old publisher
refuses a `/3` directory. The new script does the following:
1. `ycash-state/3` maps to the same roots as `/2` (`<base>/main/`, `<base>/main-insight/`).
2. It uploads each part in manifest order with `aws s3 cp`. On a re-run it skips a part whose
   `head-object` size already matches; the final `verify.py` against the manifest still covers
   its hash.
3. It uploads the statements and `treestate.json`, then **`manifest.json` and `SHA256SUMS`
   last**, as today. A reader that sees a manifest therefore sees every part it names.
4. It refuses any object over 49 GiB in any format, as a second guard for the CDN limit.

**`latest/`** works as today. `<root>/latest/manifest.json` is a copy of the height's manifest and
only moves forward. Part names are relative to `<root>/<H>/` and are never resolved against
`latest/`. Every reader takes `height` from `latest` and fetches from `<H>/` (the site's commands
already do this, and the restorer's step 1 does it from now on).

## 4. The snapshots page (kogany-site)

The page shows **one card per bundle, as today**:
- `snapshots.json` lists `ycash-state/3` beside `/2` in the ycashd families' `formats`. The
  `files` lists stay the small files.
- The facts row shows the total download (`bytes`, the whole stream), "in N parts" when `N > 1`,
  and "needs X GB free" (`unpacked_bytes`; for `/2`, the existing size line).
- The SHA-256 shown stays the whole stream's. The help text says it is the hash of the parts
  joined together, and that each part is in `SHA256SUMS`.

**The copyable command** (the first tab, "ycash-bootstrap") restores in one line, streaming,
verified, with only one part of extra disk:

```
ycash-bootstrap --network main --datadir ~/.ycash \
  --source https://snapshots.ycash.team/main-insight/latest/ --ycashd "$(command -v ycashd)" --cli "$(command -v ycash-cli)"
```

**Manual download** (the "curl" and "aria2" tabs, today's steps extended). The parts come from the
manifest, so the commands never go stale:

```
B=https://snapshots.ycash.team/main-insight
H=$(curl -fsS $B/latest/manifest.json | jq -r .height)
curl -fsS --remote-name-all $B/$H/{manifest.json,SHA256SUMS,SHA256SUMS.minisig}
for p in $(jq -r '.parts[].name' manifest.json); do curl -fL -C - -O $B/$H/$p; done
#   aria2: aria2c -x16 -c -i <(jq -r --arg b $B/$H/ '.parts[]|$b+.name+"\n  checksum=sha-256="+.sha256' manifest.json)
minisign -Vm SHA256SUMS -P <key>
shasum -a 256 -c SHA256SUMS
cat $(jq -r '.parts[].name' manifest.json) | tar -xzf - -C ~/.ycash --strip-components=1
```

The manual path needs the bundle plus the datadir on disk, as today, and the page says so,
pointing to `ycash-bootstrap` as the low-disk way. A shell-only stream (`curl | tar`) would
extract bytes before they are verified, so the page does not offer it. The kogany families'
steps do not change.

## 5. Backward compatibility

| Reader | Meets | Result |
|---|---|---|
| old `verify.py`, old `publish-s3.sh` | `/3` | refuses: "manifest: format 'ycash-state/3', expected one of …" (exit 1) |
| old `ycash-bootstrap` | `/3` (or `/2`) | refuses: "manifest format … expected 'ycash-state/1'" (it never read mainnet) |
| an old copied manual recipe | `/3` | `curl -fL -O $B/$H/$T` gets 404 (the whole stream is never published) and `curl -f` exits 22; `shasum -c` reports the missing parts |
| old site build | `/3` | the manifest fails `valid()` (format not in the family) and is not shown. Stale, never wrong; the site PR lands before the first `/3` publish |
| new readers | `/2`, `kogany-state/1`, `/2` | read as today; a `/2` bundle is one part named `tarball` |

The rule that makes this loud is that **a `/3` bundle never publishes an object named
`tarball`**, so no old path can half-work. `format` is the version field: readers dispatch on it
and refuse what they do not know. No reader infers parts from the presence of a field.

## 6. Measurement: would stronger compression alone suffice?

**Sample.** The sample was taken from the stopped capture clone of the published insight bundle
(`wt/.snapshots/ycash-mainnet-insight/tip-3100949/datadir`, height 3,100,949), read-only. No running
node's directory was touched. Composition of the whole datadir (`du`):

| Part of the datadir | Size | Sample |
|---|---|---|
| `blocks/blk*.dat` | 23.2 GB | blk00020, blk00100, blk00165 (401 MB) |
| `blocks/rev*.dat` | 2.8 GB | rev00020, 00100, 00165 (55 MB) |
| `blocks/insight-index/` | 24.1 GB | every 50th `.ldb` (497 MB) |
| `blocks/index/` | 3.6 GB | every 10th `.ldb` (648 MB) |
| `chainstate/` | 2.5 GB | every 4th small `.ldb` (227 MB) |
| total | 56.1 GB | 1.83 GB, tarred per kind |

gzip -6 of the whole datadir gives 41.84 GB (ratio 0.746). Each method was run on the same tar per
kind, with zstd 1.5.7 and xz at `-T3` (the shared machine's limit); gzip is single-threaded.

Compressed size as a fraction of the input, per kind. "Whole" is the size-weighted estimate for
the 56.1 GB datadir, scaled by 0.977 so that gzip -6 gives the real 41.84 GB (the unscaled
estimate was 42.8 GB). "MB/s" is the sample's throughput.

| Method | blk | rev | insight | index | chainstate | Whole (GB) | MB/s |
|---|---|---|---|---|---|---|---|
| `gzip -n -6` (today) | 0.828 | 0.499 | 0.717 | 0.796 | 0.862 | **41.8** | 50 (1 thread) |
| `zstd -3` | 0.751 | 0.309 | 0.672 | 0.793 | 0.680 | 38.1 | 830 |
| `zstd -9` | 0.683 | 0.271 | 0.572 | 0.780 | 0.501 | **33.6** | 180 |
| `zstd -19` | 0.648 | 0.231 | 0.491 | 0.767 | 0.443 | 30.6 | 12 |
| `zstd -19 --long=27` | 0.618 | 0.229 | 0.375 | 0.758 | 0.408 | 27.1 | 5.7 |
| `xz -6` | 0.660 | 0.223 | 0.507 | 0.774 | 0.459 | 31.3 | 10 |

How to read the table:
- Block files are mostly Equihash solutions and Sapling proofs, which barely compress at any
  level.
- The gains come from the LevelDB directories, whose repeated keys and values reach beyond
  gzip's 32 KB window.
- The long-range figure for the insight index is an upper bound. The sample's 16 files are a
  50th of the directory, and a 128 MiB window over the whole stream may find more repetition or
  less.
- Packing the whole datadir would take about 5 minutes at zstd -9 and about 2.7 hours at
  `-19 --long=27`. Today's gzip pack takes 20 minutes (`pack.json`: 1,197 s).

The conclusion is in §0. The samples were deleted after the run.

## 7. The chunk 9 test: three parts restore to the same state

The tests go in the repositories that own the code. Each runs offline, in a temporary directory,
and starts no node except its own regtest one.

- **ycash-infra `tests/test_mainnet.py`** (the producer and `verify.py`; this repository has no
  node):
  1. Pack a synthetic `main/{blocks,chainstate,vaults}` tree with `--part-bytes` chosen so the
     stream is **exactly three parts**.
  2. Assert that the parts joined together are byte-identical to the one-file `/2` pack of the
     same tree, with the same `sha256` and `tree_sha256`.
  3. Assert that `verify.py --tree` accepts it, and that it refuses each of these:
     - a flipped byte in part 2;
     - a missing part;
     - a short middle part;
     - an extra file;
     - a `parts` name out of sequence;
     - a `/3` manifest that also names a published whole tarball.
  4. Run `publish-s3.sh` (the existing mock `aws`) to check that it uploads the three parts before
     `manifest.json` and `SHA256SUMS`, and that it refuses an object over the guard.
- **ycash-dd and ycash6 `contrib/bootstrap/test_ycash_bootstrap.py`**:
  1. Build the `/3` fixture in three parts, served by a local `http.server` that supports
     `Range`. On the first request for part 1 it drops the connection halfway, so the test
     exercises resume.
  2. Restore into an empty datadir. Assert that every restored file is byte-identical to the
     source tree, that the tree hash matches, and that the work directory is gone. Assert that
     peak extra disk stayed at most one part: the fixture records the high-water mark of `work/`.
  3. Negative cases:
     - a corrupted part 2 is refused before any byte of it is extracted: the staging directory
       holds only part 1's entries when the error is raised, it is then removed, the exit code is
       non-zero, and chunk 8's marker is present;
     - a `latest/` source re-bases to `<H>/`;
     - a `/2` one-file bundle still restores.
- **The end-to-end case** (ycash6, the same file, gated on `--ycashd`, like the existing state
  tests):
  1. Mine a regtest chain past a few blocks with a vault, then stop the node.
  2. Pack it as `/3` in three parts. Regtest is allowed as a network for tests only.
  3. Restore it into a fresh datadir and start it offline.
  4. Compare `getbestblockhash`, `gettxoutsetinfo.hash_serialized`, `finalsaplingroot` and
     `vault_getinfo.statehash` with the original. This is the "same state" claim.

## 8. Exactly what changes, and where

| Repository | Files |
|---|---|
| **ycash-infra** | `bundles/state/FORMAT.md` (new section "format v3 (`ycash-state/3`)": §1 of this note); `bundles/state/verify.py` (`/3` checks, the 49 GiB guard, the chained reader); `bundles/state/mainnet/snapshot.py` (`PartWriter`, `--part-bytes`, `unpacked_bytes`, `/3` finalize); `bundles/state/mainnet/publish-s3.sh` (parts upload, the guard); `bundles/state/mainnet/README.md` (producing and restoring a `/3` bundle); `bundles/state/tests/test_mainnet.py`, `tests/test_state.py`, `tests/mocknode/aws` (record `head-object`/`cp` order) |
| **ycash-dd** (first) and **ycash6** (twin, identical files) | `contrib/bootstrap/ycash-bootstrap` (mainnet `ycash-state/2`/`3`, streaming `r\|gz`, parts, Range resume, staging and install, the `latest/` re-base, the disk check, `--keep-parts`); `contrib/bootstrap/test_ycash_bootstrap.py`; `contrib/bootstrap/README.md`. On ycash6 only: `contrib/docker/ycashd/entrypoint.sh` (allow `YCASHD_BOOTSTRAP` on mainnet with a URL, never `prefix`), `contrib/docker/ycashd/test_entrypoint.py`, `contrib/docker/ycashd/README.md`. None of these are consensus files |
| **kogany-site** | `snapshots.json` (`ycash-state/3` in the ycashd families' `formats`); `snapshots_render.py` (parts facts, the `ycash-bootstrap` tab, the manual loop); `content/snapshots.html` only if the tab labels live there |
| **kogany** | none (`kogany-state/2` is unchanged; `doc/mainnet-restore.md` stays one-file) |
| **ycash-ops** | none in beta3. Parts of 1 GiB are cacheable, so the `uncached_patterns` stop-gap in `site/snapshots` can be retired once no object over 50 GB remains (a hand-applied change, separate) |
| **workspace** | this note; the beta3 status block row 9 when chunk 9 lands. No `docs/mapping.md` row: the node lines do not differ here |

Order: the ycash-infra format PR (FORMAT and `verify.py` first, so the contract lands before any
reader), then ycash-dd and the ycash6 twin of `ycash-bootstrap`, then the site. The first `/3`
publish comes after all three. The published `/2` bundles stay valid and are not re-cut.
