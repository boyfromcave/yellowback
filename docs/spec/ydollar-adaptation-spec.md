# YDollar — Ycash adaptation spec

**Status:** skeleton. Every `**OPEN**` below is an unresolved design decision that blocks code.

**Base:** Ycash `v4.5.0` (`624c12814`) · **Reference:** DigiByte `v9.26.5` (`05b50e229d`)
**Mechanism crosswalk:** [`../mapping.md`](../mapping.md) — read that first.

---

## 1. Scope

DigiDollar on DigiByte is: over-collateralised DGB→DD minting, a 7-of-35 MuSig2 oracle price feed
committed per block, tiered collateral, time-locked redemption, and a stats index. See
`upstream-digibyte/DIGIDOLLAR_ARCHITECTURE.md`.

**In scope for v1:** *(decide and record)*
**Out of scope for v1:** Qt GUI (Ycash has no `src/qt/`); shielded YDollar (see §6).

---

## 2. Upgrade vehicle

DigiDollar deploys as a BIP9 soft fork riding BIP342 `OP_SUCCESSx`. Ycash has neither.
See `mapping.md` §2, §4.

- **OPEN — Recommended:** new network upgrade `UPGRADE_YDOLLAR` with a fresh `nBranchId`,
  inserted before `UPGRADE_ZFUTURE` in `Consensus::UpgradeIndex`.
  - [ ] Choose `nBranchId` (must not collide with any entry in `ref/ycash/src/consensus/upgrades.cpp`)
  - [ ] Choose `nProtocolVersion`
  - [ ] Choose mainnet / testnet / regtest `nActivationHeight`
  - [ ] Confirm the branch-ID sighash binding gives the replay protection we want across the fork

---

## 3. Script layer

**OPEN.** DigiByte's mint script (`ref/digibyte/src/digidollar/scripts.h:112`):

```
<lockHeight> OP_CHECKLOCKTIMEVERIFY OP_DROP OP_DIGIDOLLAR <amount> OP_DDVERIFY <ownerKey> OP_CHECKSIG
```

- [ ] Opcode encoding: new opcodes gated on `UPGRADE_YDOLLAR`, or `OP_NOPx` re-encoding? (`mapping.md` §2)
- [ ] **Do not** port `OP_CHECKPRICE` — disabled upstream as a chain-fork vector.
- [ ] `OP_CHECKCOLLATERAL` needs operands; Ycash `OP_NOPx` slots are bare no-ops (nine free: `OP_NOP1`, `OP_NOP3`–`OP_NOP10`). Resolve.
- [ ] Ycash has **no `OP_CHECKSEQUENCEVERIFY`** — only CLTV. Confirm no DD script needs relative locktime.
- [ ] Script lives in a P2SH `redeemScript`, not a tapleaf. Re-evaluate the commitment strength (`mapping.md` §3).

---

## 4. Transaction marking

**OPEN.** DigiByte bit-packs type+flags into `nVersion`; Ycash pins `nVersion == 4` and adds
`nVersionGroupId` (`mapping.md` §5).

- [ ] (a) New tx version 5 + `YDOLLAR_VERSION_GROUP_ID`, ZIP-202 style — or — (b) `OP_RETURN` payload output
- [ ] Restate all value-conservation invariants to account for `valueBalance` and the shielded pools

---

## 5. Oracle

**OPEN.** New build, not a port (`mapping.md` §7). See `upstream-digibyte/DIGIDOLLAR_ORACLE_ARCHITECTURE.md`.

- [ ] Enable secp256k1 `schnorrsig`/`musig` modules and port MuSig2 — or — fall back to N-of-M ECDSA
- [ ] Threshold and roster size (DigiByte: 7-of-35)
- [ ] Per-block bundle commitment location — Ycash's header has no spare field; coinbase `OP_RETURN`?
- [ ] P2P transport: Ycash's `ProcessMessage` lives in the monolithic `src/main.cpp`

---

## 6. Shielded pools

**OPEN — decide early, it constrains everything.** (`mapping.md` §6)

- [ ] Default recommendation: **YDollar outputs must be transparent.** Reject `UPGRADE_YDOLLAR`-typed
      transactions carrying `vShieldedOutput` / `vJoinSplit`. Rationale: a shielded DD output makes
      global supply and the collateral ratio unverifiable by consensus.
- [ ] If shielded YDollar is required, scope it as research, not a port.

---

## 7. State, RPC, wallet

- [ ] YDollar state persistence — Ycash has no `src/index/` base-index framework (`mapping.md` §1)
- [ ] RPC surface: re-derive from `ref/digibyte/src/rpc/digidollar.cpp` into Ycash's `fHelp` convention
- [ ] Mint/redeem as `AsyncRPCOperation`s
- [ ] Wallet: coin locking / selection rules from `ref/digibyte/src/wallet/digidollarwallet.cpp`, re-implemented for the legacy keypool wallet
