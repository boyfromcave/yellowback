#!/usr/bin/env python3
# Copyright (c) 2026 The Ycash developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://www.opensource.org/licenses/mit-license.php .
"""Base58Check version search and proof for the post-quantum address prefixes (quantum spec §4, D-9).

A post-quantum address is Base58Check(version || keyHash): a 3-byte version per (network, coin,
scheme), a 32-byte key hash and a 4-byte checksum, 39 bytes in all. A version v covers the integer
interval [v * 2^288, (v + 1) * 2^288) (every key hash and every checksum). It renders the prefix p
at length L exactly when that interval lies inside [val(p) * 58^(L-3), (val(p) + 1) * 58^(L-3)) and
the first character is not '1' (no leading zero byte). That is a closed-form proof, not a sample.

  scripts/pq_addr_prefix.py prove              # the D-9 table: proof, self-check, sampling, collisions
  scripts/pq_addr_prefix.py search sqf [len]   # every 3-byte version that fixes a prefix
  scripts/pq_addr_prefix.py vectors > pq_address_vectors.json   # the shared vectors file

Exit status 0 only if every check passes. Needs only the Python standard library.
"""
import hashlib
import json
import random
import sys

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

HASH_BYTES = 32
CHECKSUM_BYTES = 4
ADDR_LEN = 53

SCHEMES = {1: "slh-dsa-sha2-128s", 2: "fn-dsa-512"}

# D-9 (the Yellowback lead architect, 2026-11-10): (network, coin, scheme) -> (prefix, 3-byte version).
D9 = {
    ("main", "yec", 2): ("sqf", 0x4DDD04),
    ("main", "yec", 1): ("sqs", 0x4DDE6A),
    ("test", "yec", 2): ("tqf", 0x4F6519),
    ("test", "yec", 1): ("tqs", 0x4F667F),
    ("regtest", "yec", 2): ("rqf", 0x4C54EF),
    ("regtest", "yec", 1): ("rqs", 0x4C5655),
    ("main", "yed", 2): ("ybf", 0x56AEDE),
    ("main", "yed", 1): ("ybs", 0x56B044),
    ("test", "yed", 2): ("ytf", 0x5721C9),
    ("test", "yed", 1): ("yts", 0x572330),
    ("regtest", "yed", 2): ("yrf", 0x571444),
    ("regtest", "yed", 1): ("yrs", 0x5715AA),
}

# Every other Base58Check family a Ycash node (src/chainparams.cpp, src/yellowback/params.cpp on
# ycash-dd upgrade/vault 85ed00309) decodes, per network: (name, version bytes, data bytes after
# the version). Sapling uses bech32 and cannot collide with a Base58 string.
_COMMON_TEST = [
    ("p2pkh", bytes([0x1C, 0x95]), 20), ("p2sh", bytes([0x1C, 0x2A]), 20),
    ("legacy-p2pkh", bytes([0x1D, 0x25]), 20), ("legacy-p2sh", bytes([0x1C, 0xBA]), 20),
    ("wif", bytes([0xEF]), 32), ("wif-compressed", bytes([0xEF]), 33),
    ("xpub", bytes([0x04, 0x35, 0x87, 0xCF]), 74), ("xprv", bytes([0x04, 0x35, 0x83, 0x94]), 74),
    ("sprout-addr", bytes([0x16, 0x52]), 64), ("legacy-sprout-addr", bytes([0x16, 0xB6]), 64),
    ("sprout-vk", bytes([0xA8, 0xAC, 0x0C]), 64), ("sprout-sk", bytes([0xAC, 0x08]), 32),
    ("old-yec-pq (2-byte, any scheme byte)", None, 33),
    ("old-yed-pq (2-byte, any scheme byte)", None, 33),
]
OTHER = {
    "main": [
        ("p2pkh", bytes([0x1C, 0x28]), 20), ("p2sh", bytes([0x1C, 0x2C]), 20),
        ("legacy-p2pkh", bytes([0x1C, 0xB8]), 20), ("legacy-p2sh", bytes([0x1C, 0xBD]), 20),
        ("wif", bytes([0x80]), 32), ("wif-compressed", bytes([0x80]), 33),
        ("xpub", bytes([0x04, 0x88, 0xB2, 0x1E]), 74), ("xprv", bytes([0x04, 0x88, 0xAD, 0xE4]), 74),
        ("sprout-addr", bytes([0x16, 0x36]), 64), ("legacy-sprout-addr", bytes([0x16, 0x9A]), 64),
        ("sprout-vk", bytes([0xA8, 0xAB, 0xD3]), 64), ("sprout-sk", bytes([0xAB, 0x36]), 32),
        ("yed-ecc", bytes([0x1F, 0xDD]), 20),
        ("old-yec-pq (2-byte, any scheme byte)", bytes([0x4D, 0xD9]), 33),
        ("old-yed-pq (2-byte, any scheme byte)", bytes([0x56, 0xAB]), 33),
    ],
    "test": [f for f in _COMMON_TEST if f[1] is not None] + [
        ("yed-ecc", bytes([0x20, 0x07]), 20),
        ("old-yec-pq (2-byte, any scheme byte)", bytes([0x4F, 0x61]), 33),
        ("old-yed-pq (2-byte, any scheme byte)", bytes([0x57, 0x1E]), 33),
    ],
    "regtest": [f for f in _COMMON_TEST if f[1] is not None] + [
        ("yed-ecc", bytes([0x20, 0x02]), 20),
        ("old-yec-pq (2-byte, any scheme byte)", bytes([0x4C, 0x51]), 33),
        ("old-yed-pq (2-byte, any scheme byte)", bytes([0x57, 0x10]), 33),
    ],
}

# Self-check: the versions in use before D-9, each re-derived by the same rule.
# (prefix, version bytes, data bytes after the version, expected length)
EXISTING = [
    ("sq", bytes([0x4D, 0xD9]), 33, 53), ("tq", bytes([0x4F, 0x61]), 33, 53), ("rq", bytes([0x4C, 0x51]), 33, 53),
    ("yb", bytes([0x56, 0xAB]), 33, 53), ("yt", bytes([0x57, 0x1E]), 33, 53), ("yr", bytes([0x57, 0x10]), 33, 53),
    ("yb", bytes([0x1F, 0xDD]), 20, 35), ("yt", bytes([0x20, 0x07]), 20, 35), ("yr", bytes([0x20, 0x02]), 20, 35),
    ("s1", bytes([0x1C, 0x28]), 20, 35), ("sm", bytes([0x1C, 0x95]), 20, 35), ("tm", bytes([0x1D, 0x25]), 20, 35),
]


def b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = B58[r] + out
    pad = len(data) - len(data.lstrip(b"\0"))
    return "1" * pad + out


def b58check(data: bytes) -> str:
    return b58encode(data + hashlib.sha256(hashlib.sha256(data).digest()).digest()[:CHECKSUM_BYTES])


def b58val(s: str) -> int:
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    return n


def interval(version: bytes, rest: int):
    """[lo, hi) of the integers Base58Check(version || any rest bytes || any checksum) can take."""
    shift = 8 * (rest + CHECKSUM_BYTES)
    v = int.from_bytes(version, "big")
    return v << shift, (v + 1) << shift, len(version) + rest + CHECKSUM_BYTES


def proves(version: bytes, rest: int, prefix: str, length: int) -> bool:
    """True iff every payload and checksum renders `prefix` at exactly `length` characters."""
    if version[0] == 0 or prefix[0] == "1":
        return False
    lo, hi, _ = interval(version, rest)
    unit = 58 ** (length - len(prefix))
    a = b58val(prefix)
    return a * unit <= lo and hi <= (a + 1) * unit


def search(prefix: str, vbytes: int, rest: int, length: int):
    """Every vbytes-byte version that fixes `prefix` at `length` (closed form, then each one proved)."""
    shift = 8 * (rest + CHECKSUM_BYTES)
    unit = 58 ** (length - len(prefix))
    a = b58val(prefix)
    lo = -(-(a * unit) // (1 << shift))
    hi = ((a + 1) * unit >> shift) - 1
    hits = [v for v in range(max(lo, 1 << (8 * (vbytes - 1))), min(hi, (1 << (8 * vbytes)) - 1) + 1)
            if proves(v.to_bytes(vbytes, "big"), rest, prefix, length)]
    return hits


def hexv(v: int, n: int = 3) -> str:
    return " ".join(f"{b:02X}" for b in v.to_bytes(n, "big"))


def fail(msg, errors):
    errors.append(msg)
    print("FAIL:", msg)


def prove() -> int:
    errors = []
    print("== Self-check: the versions in use before D-9 re-derived by the same rule")
    for prefix, ver, rest, length in EXISTING:
        hits = search(prefix, len(ver), rest, length)
        v = int.from_bytes(ver, "big")
        ok = proves(ver, rest, prefix, length) and v in hits
        print(f"  {prefix:3} {ver.hex().upper():6} len {length}: {len(hits)} hits "
              f"{hits[0]:#06x}..{hits[-1]:#06x}, in use is {'the lowest' if hits and v == hits[0] else 'a hit'}"
              f"{'' if ok else '  <-- NOT PROVED'}")
        if not ok:
            fail(f"self-check {prefix} {ver.hex()}", errors)

    print("\n== D-9: closed-form proof (every key hash, every checksum), lowest hit, sampling")
    rng = random.Random(0x5946)  # fixed seed: the run is reproducible
    for (net, coin, scheme), (prefix, v) in D9.items():
        ver = v.to_bytes(3, "big")
        hits = search(prefix, 3, HASH_BYTES, ADDR_LEN)
        proved = proves(ver, HASH_BYTES, prefix, ADDR_LEN)
        lowest = bool(hits) and hits[0] == v
        samples = [bytes(32), b"\xff" * 32] + [rng.randbytes(32) for _ in range(10000)]
        bad = [h for h in samples if not (lambda s: len(s) == ADDR_LEN and s.startswith(prefix))(b58check(ver + h))]
        lo_s, hi_s = b58check(ver + bytes(32)), b58check(ver + b"\xff" * 32)
        print(f"  {net:7} {coin} {SCHEMES[scheme]:17} {prefix} {hexv(v)}  proved={proved} "
              f"lowest-of-{len(hits)}={lowest} samples={len(samples)} bad={len(bad)}  {lo_s[:8]}…/{hi_s[:8]}…")
        if not proved:
            fail(f"{prefix} {hexv(v)} not proved", errors)
        if not lowest:
            fail(f"{prefix} {hexv(v)} is not the lowest hit (lowest {hexv(hits[0]) if hits else None})", errors)
        if bad:
            fail(f"{prefix} {hexv(v)}: {len(bad)} sampled addresses off-prefix or off-length", errors)

    print("\n== Non-collision: no two families a node decodes share a byte string")
    # Two Base58Check strings are equal iff their byte strings are equal (Base58 is a bijection on byte
    # strings once leading zero bytes map to '1'), so two families can only collide at the same total
    # byte length with overlapping intervals. Checked per network and across all networks at once.
    all_new = []
    for net in ("main", "test", "regtest"):
        fams = [(name, *interval(ver, rest)) for name, ver, rest in OTHER[net]]
        new = [(f"{coin}-{SCHEMES[s]} {p}", *interval(v.to_bytes(3, "big"), HASH_BYTES))
               for (n, coin, s), (p, v) in D9.items() if n == net]
        all_new += [(f"{net} {name}", lo, hi, ln) for name, lo, hi, ln in new]
        for name, lo, hi, ln in new:
            for oname, olo, ohi, oln in fams + [f for f in new if f[0] != name]:
                if ln == oln and lo < ohi and olo < hi:
                    fail(f"{net}: {name} overlaps {oname}", errors)
        print(f"  {net}: {len(new)} new families vs {len(fams)} existing: "
              f"{'disjoint' if not [e for e in errors if e.startswith(net)] else 'OVERLAP'}")
    for i, (name, lo, hi, ln) in enumerate(all_new):
        for oname, olo, ohi, oln in all_new[i + 1:]:
            if ln == oln and lo < ohi and olo < hi:
                fail(f"across networks: {name} overlaps {oname}", errors)
    # Every network's existing families against every new version (a string valid on one network
    # never decodes as a post-quantum address on another).
    for net in OTHER:
        for oname, ver, rest in OTHER[net]:
            olo, ohi, oln = interval(ver, rest)
            for name, lo, hi, ln in all_new:
                if ln == oln and lo < ohi and olo < hi:
                    fail(f"{name} overlaps {net} {oname}", errors)
    print(f"  all twelve versions distinct and pairwise disjoint across networks and coins: "
          f"{len({v for _, v in D9.values()}) == 12 and not errors}")
    # Scheme separation: the scheme is the version, so FN-DSA and SLH-DSA intervals are disjoint by
    # construction; also check no new version begins with an old 2-byte version (the old form can
    # never be read as a new one, whatever its third byte).
    old2 = {ver for net in OTHER for name, ver, rest in OTHER[net] if name.startswith("old-")}
    for (net, coin, s), (p, v) in D9.items():
        if v.to_bytes(3, "big")[:2] in old2:
            fail(f"{p} {hexv(v)} begins with an old 2-byte version", errors)
    print("  scheme 1 and scheme 2 versions differ on every (network, coin); no new version extends an old one")

    print("\n" + ("ALL CHECKS PASS" if not errors else f"{len(errors)} FAILURES"))
    return 0 if not errors else 1


def vectors() -> dict:
    """The shared vectors (quantum spec §4): positive (network, coin, scheme, keyhash, address) and
    negative strings every component must reject. Deterministic: no randomness."""
    hashes = [bytes(32), b"\xff" * 32, bytes(range(32)), bytes(range(32, 0, -1)),
              hashlib.sha256(b"ycash pq address vector 0").digest(),
              hashlib.sha256(b"ycash pq address vector 1").digest()]
    old = {("main", "yec"): bytes([0x4D, 0xD9]), ("test", "yec"): bytes([0x4F, 0x61]),
           ("regtest", "yec"): bytes([0x4C, 0x51]), ("main", "yed"): bytes([0x56, 0xAB]),
           ("test", "yed"): bytes([0x57, 0x1E]), ("regtest", "yed"): bytes([0x57, 0x10])}
    valid, invalid = [], []
    for (net, coin, scheme), (prefix, v) in D9.items():
        ver = v.to_bytes(3, "big")
        for h in hashes:
            valid.append({"network": net, "coin": coin, "scheme": scheme, "scheme_name": SCHEMES[scheme],
                          "version": ver.hex(), "keyhash": h.hex(), "address": b58check(ver + h)})
        h = hashes[4]
        invalid.append({"network": net, "coin": coin, "reason": "old-form",
                        "address": b58check(old[(net, coin)] + bytes([scheme]) + h)})
        invalid.append({"network": net, "coin": coin, "reason": "truncated",
                        "address": b58check(ver + h[:31])})
        invalid.append({"network": net, "coin": coin, "reason": "extended",
                        "address": b58check(ver + h + b"\0")})
        bad = b58check(ver + h)
        last = B58[(B58.index(bad[-1]) + 1) % 58]
        invalid.append({"network": net, "coin": coin, "reason": "bad-checksum", "address": bad[:-1] + last})
        # The next version up renders the same prefix but is not a registered version.
        nxt = (v + 1).to_bytes(3, "big")
        assert b58check(nxt + h).startswith(prefix)
        invalid.append({"network": net, "coin": coin, "reason": "unknown-version",
                        "address": b58check(nxt + h)})
    return {
        "_comment": "Ycash post-quantum address vectors (quantum spec §4, D-9). Generated by "
                   "scripts/pq_addr_prefix.py vectors in the workspace repo; do not edit by hand. "
                   "address = Base58Check(version || keyhash), version is 3 bytes per (network, coin, "
                   "scheme), 53 characters. Every 'valid' address decodes to (scheme, keyhash) on its own "
                   "network and coin only; every 'invalid' address is rejected on its own network and "
                   "coin (and so everywhere).",
        "format": "ycash-pq-address-vectors-1",
        "schemes": {str(k): v for k, v in SCHEMES.items()},
        "valid": valid,
        "invalid": invalid,
    }


def main(argv):
    if len(argv) >= 2 and argv[1] == "search":
        prefix = argv[2]
        length = int(argv[3]) if len(argv) > 3 else ADDR_LEN
        hits = search(prefix, 3, HASH_BYTES, length)
        print(f"{prefix} at {length}: {len(hits)} hits", " ".join(hexv(h).replace(" ", "") for h in hits))
        return 0
    if len(argv) >= 2 and argv[1] == "vectors":
        print(json.dumps(vectors(), indent=1))
        return 0
    return prove()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
