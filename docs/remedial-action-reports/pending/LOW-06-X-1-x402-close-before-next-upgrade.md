# LOW — 06/X-1, 06/X-2 — x402 batch-settlement server never closes channels before the next network-upgrade activation height; the Falcon YED key file is plaintext (Info)

Repos / branches to change: `x402-ycash` (`fix/06-X-1-close-before-upgrade` off `upgrade/vault`).
Audit source: `docs/audits/quantum-vault-ecosystem/06-clients-wallets-infra.md:142-151` (X-1), `:153-157` (X-2); verification `verification/06-verification.md:21-22` (verdicts), `:62-64` (detail: refund unaffected); consolidated `00-consolidated.md` row 06/Y-2..Y-5 (x402 "close before next NU" MUST unimplemented).
Status: pending

## 1. Finding

The scheme spec says vouchers commit to the consensus branch id current at signing (ZIP-243), so a voucher signed before a network-upgrade activation height cannot be completed and mined after it, and "a server MUST therefore close every channel before the activation height of the next network upgrade (it can treat that height like t for its margin), or a client MUST choose t below that height". The server implements neither: `sweep` closes on margin (`tip ≥ t − margin`) and idle only, and the only extra close bound is the Falcon height `F` for a YED channel opened before it. No code under `batch/` reads an activation height, although `getblockchaininfo.upgrades[*].activationheight` is in the node answer the server already fetches (`chainContext`) and lightwalletd's `GetYellowbackInfo` carries the same list. At close the server re-signs under the branch current at close time, but the client's half of the voucher cannot be re-made, so a channel that straddles an activation is uncompletable: the merchant loses the vouchered amount; the client's refund (built and signed at broadcast under `consensus.nextblock`) is unaffected. On mainnet YED channels exist only after the vault upgrade, so this bites at a *future* upgrade — Low, but it is a spec MUST with no implementation.

X-2 (Info): the CLI's Falcon YED key seed is a plaintext hex file written with mode 0600 and flag `wx`; documented as the operator's responsibility. A runbook note is enough.

## 2. Root cause

- Spec: `x402-ycash/specs/scheme_batch_settlement_ycash.md:107-112` (the MUST) and `:688-690` (Network upgrades bullet).
- Server close triggers: `packages/ycash/src/batch/server/manager.ts:270-291` (`sweep`: `height >= marginHeightOf(ch.terms)` → `"margin"` at `:287`, idle at `:288`); `:245-266` `close` re-signs with `chainContext(...).branchId` at `:253-254`; the watcher at `:300-320` (`marginHeightOf`, `closeBy` passed through at `:318`); `:397-400` refuses vouchers once inside the margin.
- The one existing extra bound: `packages/ycash/src/batch/verify.ts:264-267` (`VerifiedOpen.closeBy`: "t, or min(t, F)"), `:329-346` (Falcon logic; `closeBy = channelCloseBy(…, falconHeight)` at `:344`; refusal at open when already inside the margin at `:345-346`); `packages/ycash/src/channel/falcon.ts:142-145` `channelCloseBy`; `packages/ycash/src/batch/watcher.ts:23-24` `marginHeightOf = min(refundHeight, closeBy ?? refundHeight) − closeMarginBlocks`; persisted at `server/ledger.ts:46` (`closeBy?`), set at `manager.ts:168`.
- The data is available: `verify.ts:219-224` `chainContext` calls `chain.getBlockchainInfo()` whose type `packages/ycash/src/node/types.ts:35` has `upgrades: Record<string, { name; activationheight; status; info? }>`; the LWD path `packages/ycash/src/lwd/chain.ts:108,141` drops everything but chain/height/branch, while `lightwalletd/walletrpc/yellowback.proto:243-253` (`YedUpgrade`, `repeated YedUpgrade upgrades = 7`) carries the list through `GetYellowbackInfo`. `grep -rn 'activation|upgrades' packages/ycash/src/batch` → none.
- X-2: `packages/cli/src/run.ts:87-88` (`randomBytes(48)`, `fn-dsa-512:<hex>`, `mode 0o600`, `flag "wx"`); `packages/cli/src/fileStorage.ts:3`.

## 3. Fix options considered

1. **Client-side only (choose t below the next activation).** Rejected as the sole fix: the spec puts the MUST on the server, and a client cannot know about an activation scheduled after it opened.
2. **Server treats the next pending activation height as a second `closeBy`, re-read every sweep tick.** Accepted. It reuses the Falcon `closeBy` plumbing exactly (`channelCloseBy` → `min`), and re-reading each tick handles the mainnet case where the height is *set by a later release* (P8) while channels are open.
3. **Refuse to open any channel whose `t` is past the next activation.** Too strict (the spec allows closing early); instead refuse only when the channel would already be inside the activation margin at open, as the Falcon logic does.

## 4. Recommended fix

1. **`verify.ts` `ChainContext`**: add `nextActivationHeight?: number` — the least `activationheight` among `info.upgrades` whose `status` is `"pending"` and whose height is `> tip` (node path); for the LWD path extend `lwd/chain.ts`'s `ChainState`/`getBlockchainInfo` shim to map `GetYellowbackInfo.upgrades[]` (`activationheight`, `active`) into the same shape, `undefined` when the server predates the field. Read it in `chainContext` (`:219-224`).
2. **At open** (`verify.ts:329-346`): `closeBy = min(channelCloseBy(…, falconHeight), ctx.nextActivationHeight ?? ∞)`; the existing `:345-346` refusal then also covers "already inside the activation margin". Persist as today (`ledger.ts:46`, `manager.ts:168`), with the log line naming which bound applied.
3. **At sweep** (`manager.ts:270-291`): once per tick compute `ctx = chainContext(...)` (it is fetched per close anyway) and use `marginHeightOf({ ...ch.terms, closeBy: min(ch.terms.closeBy ?? ∞, ctx.nextActivationHeight ?? ∞) })`; when the recomputed bound is lower than the stored one, lower the stored `closeBy` (`ledger` update) so a later restart (`restart.test.ts` path) keeps it. Add a `CloseReason` `"upgrade"` for the log/`onClose` (`:287`).
4. **Voucher acceptance** (`manager.ts:397-400`): the same recomputed margin, so a voucher presented inside the activation margin is refused with `CHANNEL_CLOSING` naming "the next upgrade".
5. **Client** (`batch/client`): when the server's terms or the chain context carry a next activation height, bound the requested `t` by it (spec "or a client MUST choose t below that height") and surface it in the open error path.
6. **Spec**: `scheme_batch_settlement_ycash.md:107-112` gains "implemented as a `closeBy` bound beside the Falcon height, re-evaluated every sweep"; `:688-690` cross-references.
7. **X-2 runbook**: `packages/cli/README.md` (or the operator docs): the key file is plaintext under 0600; recommend a dedicated service user, an encrypted volume, and `X402_YED_KEY_FILE` on tmpfs for ephemeral agents; optional follow-up: accept the seed from an environment variable/secret manager so no file is written.

## 5. Tests

- `packages/ycash/test/unit/batch/fakeChain.ts:45-47` (`getBlockchainInfo` returns `upgrades: {}`): add a settable `upgrades` map.
- New `test/unit/batch/upgradeClose.test.ts` modelled on `yed.falcon.test.ts:149-150, 240, 272`: (a) `marginHeightOf` with an activation bound; (b) open at tip 100 with `t = 500`, activation pending at 300, margin 10 → stored `closeBy = 300`; `sweep()` at tip 290 closes with reason `"upgrade"`; (c) open with no pending activation, then the fake chain schedules one at 300 → the next `sweep()` lowers the stored bound and closes at 290 (the P8 case); (d) voucher at tip 291 refused `CHANNEL_CLOSING`; (e) `restart.test.ts` variant: the lowered bound survives a ledger reload; (f) a client `open` with `t ≥ activation` is bounded or refused per step 5.
- Devnet job (existing CI `devnet` job): one regtest run with `-nuparams=<a fake later branch>:<h>`? Not available (regtest knows only the defined upgrades) — instead run the Vault activation itself: start the devnet below the Vault height with a YEC channel, assert the server closes it before activation and the voucher completes under the old branch. This also exercises the real `getblockchaininfo.upgrades` shape.

## 6. Acceptance criteria

- `grep -rn 'nextActivationHeight' packages/ycash/src/batch` shows the context field, the open bound, the sweep recomputation and the voucher refusal.
- Unit tests (a)–(f) green; the devnet activation case green in CI.
- Spec text updated; CLI runbook carries the key-file note.
- `cargo test`/`npm test`/pytest unchanged otherwise.

## 7. Risks and side effects

- Servers will close channels early around any future activation (by `closeMarginBlocks`) — the spec's intent; operators see reason `"upgrade"` in logs.
- A node that lists a *pending* upgrade with a bogus low height (misconfigured regtest) would close every channel at once; bound the effect by ignoring activations `≤ tip` and logging the source.
- lightwalletd servers older than the `upgrades` field leave `nextActivationHeight` undefined: behaviour as today; log once.

## 8. Effort estimate and dependencies

- 1 day (plumbing + tests), 0.25 day spec/runbook. No dependencies; the lightwalletd `upgrades` field already exists (`yellowback.proto:253`).
