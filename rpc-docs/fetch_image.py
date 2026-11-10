#!/usr/bin/env python3
"""Extract files from a public container image without Docker.

    rpc-docs/fetch_image.py ghcr.io/boyfromcave/ycashd:ycash6-a8120c787aa4 /tmp/ycash-bin \
        usr/local/bin/ycashd usr/local/bin/ycash-cli

Reads the image anonymously over the OCI distribution API, checks every blob against its digest,
applies the layers in order and writes only the requested paths (flat, into DEST). Prints a JSON
record of the image (reference, manifest digest, platform) on stdout, which capture.py stores as the
snapshot's provenance.
"""
import argparse
import hashlib
import json
import os
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request

ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])
INDEX_TYPES = ("application/vnd.oci.image.index.v1+json",
               "application/vnd.docker.distribution.manifest.list.v2+json")


def parse_ref(ref):
    """`registry/repo/path:tag` -> (registry, repo, tag)."""
    registry, _, rest = ref.partition("/")
    if not rest or "." not in registry:
        raise SystemExit("fetch_image: give a full reference, e.g. ghcr.io/owner/name:tag")
    repo, sep, tag = rest.rpartition(":")
    if not sep or "/" in tag:
        repo, tag = rest, "latest"
    return registry, repo, tag


class Registry:
    def __init__(self, registry, repo):
        self.base = "https://%s/v2/%s" % (registry, repo)
        self.token = None
        self.registry = registry
        self.repo = repo

    def _open(self, url, accept=None):
        headers = {"User-Agent": "yellowback-rpc-docs"}
        if accept:
            headers["Accept"] = accept
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120)
        except urllib.error.HTTPError as e:
            if e.code != 401 or self.token:
                raise
            self.token = self._anonymous_token(e.headers.get("WWW-Authenticate", ""))
            return self._open(url, accept)

    def _anonymous_token(self, challenge):
        if not challenge.lower().startswith("bearer "):
            raise SystemExit("fetch_image: registry asked for %r, only anonymous bearer tokens are supported" % challenge)
        fields = dict(p.split("=", 1) for p in challenge[7:].split(","))
        fields = {k.strip(): v.strip().strip('"') for k, v in fields.items()}
        query = {"service": fields.get("service", self.registry),
                 "scope": fields.get("scope", "repository:%s:pull" % self.repo)}
        with urllib.request.urlopen(fields["realm"] + "?" + urllib.parse.urlencode(query), timeout=60) as r:
            body = json.load(r)
        return body.get("token") or body["access_token"]

    def manifest(self, ref):
        with self._open("%s/manifests/%s" % (self.base, ref), ACCEPT) as r:
            raw = r.read()
            digest = r.headers.get("Docker-Content-Digest") or "sha256:" + hashlib.sha256(raw).hexdigest()
        return json.loads(raw), digest

    def blob_to(self, digest, fh):
        algo, _, want = digest.partition(":")
        if algo != "sha256":
            raise SystemExit("fetch_image: unsupported digest %s" % digest)
        h = hashlib.sha256()
        with self._open("%s/blobs/%s" % (self.base, digest)) as r:
            for chunk in iter(lambda: r.read(1 << 20), b""):
                h.update(chunk)
                fh.write(chunk)
        if h.hexdigest() != want:
            raise SystemExit("fetch_image: blob %s failed its digest check" % digest)


def resolve(reg, tag, platform):
    manifest, digest = reg.manifest(tag)
    if manifest.get("mediaType") in INDEX_TYPES or "manifests" in manifest:
        os_, _, arch = platform.partition("/")
        for m in manifest["manifests"]:
            p = m.get("platform", {})
            if p.get("os") == os_ and p.get("architecture") == arch:
                image, _ = reg.manifest(m["digest"])
                return image, digest, m["digest"]
        raise SystemExit("fetch_image: no %s image in %s" % (platform, tag))
    return manifest, digest, digest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("image")
    ap.add_argument("dest")
    ap.add_argument("paths", nargs="+", help="paths inside the image, e.g. usr/local/bin/ycashd")
    ap.add_argument("--platform", default="linux/amd64")
    args = ap.parse_args(argv)

    registry, repo, tag = parse_ref(args.image)
    reg = Registry(registry, repo)
    image, index_digest, image_digest = resolve(reg, tag, args.platform)
    wanted = {p.removeprefix("./").lstrip("/") for p in args.paths}
    found = {}
    os.makedirs(args.dest, exist_ok=True)
    for layer in image["layers"]:
        with tempfile.TemporaryFile() as fh:
            reg.blob_to(layer["digest"], fh)
            fh.seek(0)
            with tarfile.open(fileobj=fh, mode="r:*") as tar:
                for member in tar:
                    name = member.name.removeprefix("./").lstrip("/")
                    if name in wanted and member.isfile():
                        out = os.path.join(args.dest, os.path.basename(name))
                        with tar.extractfile(member) as src, open(out, "wb") as dst:
                            dst.write(src.read())
                        os.chmod(out, 0o755)
                        found[name] = out
    missing = sorted(wanted - set(found))
    if missing:
        raise SystemExit("fetch_image: not in the image: %s" % ", ".join(missing))
    json.dump({"image": args.image, "digest": index_digest, "platformDigest": image_digest,
               "platform": args.platform}, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
