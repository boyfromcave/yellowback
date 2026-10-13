# LOW — 01/V-6 — `VaultDB::Read` caches a value read outside its mutex (latent stale-cache race)

**Repos / branches to change:** `ycash-dd` (`src/vault/db.cpp`) and `ycash6` (same file, `:74`), branch `fix/01-V-6-vaultdb-read-lock` off `upgrade/vault` in each.
**Audit source:** `01-vault-primitive-consensus.md` §V-6 (`:122-131`); `verification/01-verification.md` row V-6 (`:19`), detail (`:127-130`).
**Status:** pending.

## 1. Finding

`VaultDB::Read` checks its memory cache under `cs`, then **drops the lock**, reads LevelDB, re-takes the lock and inserts what it read. `ConnectBlock`/`DisconnectBlock` commit a batch and update the cache under `cs` as one step. A reader that interleaves — cache miss, DB read of the pre-commit value, commit + `CachePut(new)` by the connecting thread, then the reader's `CachePut(old)` — installs the stale value, which every later consensus read (`VaultState::Read` → `VaultDB::Read`) sees until the cache is cleared (`MAX_CACHE_ENTRIES` overflow or `Wipe`). That would be a consensus divergence on one node (stale set state), not a chain-wide one.

Latent today: every caller holds `cs_main` (`src/rpc/vault.cpp` readers `LOCK`/`LOCK2`; the miner, mempool and ConnectBlock paths all run under `cs_main`), so no reader can interleave with a commit. The guard is an invariant nobody asserts; a future unlocked reader (an RPC taking only `cs` for speed, an indexer thread) would trigger it. Verified Low (latent).

## 2. Root cause

ycash-dd `055d9c2` `src/vault/db.cpp:62-79` (ycash6 `e866c45` `:74` for the unguarded read; same code):

```cpp
bool VaultDB::Read(const std::string& key, std::string& value) const
{
    {   std::lock_guard<std::mutex> lock(cs);  /* cache hit path */ ... }
    std::string v;
    bool found = db->Read(RawKey(key), v);          // no lock
    std::lock_guard<std::mutex> lock(cs);
    CachePut(key, found ? std::optional<std::string>(v) : std::nullopt);   // may overwrite a newer CachePut
    ...
```
`CachePut` (`:55-60`) comments "caller holds cs" and clears the whole cache at `MAX_CACHE_ENTRIES` (`db.h:87`, 100,000). The writers (`ConnectBlock` `:139-150`, `DisconnectBlock` `:165-178`) take `cs` only around `WriteBatch` + `CachePut`, so a reader's DB read can straddle the batch.

## 3. Fix options considered

1. **Hold `cs` across the DB read.** Simplest; serialises concurrent readers of the vault DB (a small LevelDB; reads are microseconds) and makes `cs` cover both the store and the cache. Safe because `WriteBatch` already runs under `cs`. Slight contention cost only.
2. **Re-check after the read (double-checked insert):** after re-taking `cs`, insert only if the key is still absent from the cache; a commit that raced ahead has already put the newer value, and the reader returns the (possibly older) value it read without poisoning the cache. The reader's own return value can still be pre-commit — acceptable only because such a reader is by construction not under `cs_main` and gets what it would have gotten a moment earlier. Keeps readers concurrent. **Recommended** (minimal and keeps today's performance), plus an `AssertLockHeld`-style invariant where it can be expressed.
3. **Version-stamp the cache** (bump a counter on every commit, discard reads started before the counter changed): most precise; more code than a Low item warrants. Rejected.

## 4. Recommended fix

`src/vault/db.cpp` `Read` (both lines):

```cpp
    std::string v;
    const bool found = db->Read(RawKey(key), v);
    std::lock_guard<std::mutex> lock(cs);
    // A ConnectBlock/DisconnectBlock may have committed and cached this key while the read ran
    // outside cs: never overwrite a newer entry with what was read before the commit (audit 01/V-6).
    if (cache.find(key) == cache.end()) CachePut(key, found ? std::optional<std::string>(v) : std::nullopt);
    if (found) value = v;
    return found;
```
Add a one-line comment to `db.h` above `cs` (`:85`): "guards `cache` and the write batch; every consensus reader additionally holds `cs_main`, which is what orders reads against commits". Optionally, in `VaultDB::Read`, `AssertLockHeld(cs_main)` is not available (the DB layer does not include `sync.h`/`main.h` by design); leave the comment.

`SetSnapshot::Load` (`state.cpp:239-252`) has the same shape but each snapshot is a per-evaluation immutable object (verifier), so no change there.

Consensus footprint: none (node-local caching; the value returned to a `cs_main` holder is unchanged).

## 5. Tests

- `src/test/vault_state_tests.cpp` `db_connect_disconnect` (LevelDB-backed): add a sequential simulation of the race through a test seam — expose `void VaultDB::TestOnlyCachePut(key, value)` guarded by a `#ifdef` is unnecessary: use the public API: `Read(k)` (miss → caches old), `ConnectBlock` (caches new), `Read(k)` → new. This passes before and after; it pins the cache-coherence contract. The actual interleaving is proven by review, not by a unit test.
- Nightly `sanitizers` job: the TSan/ASan variant runs the functional suite; no new step.
- Both lines: `diff` of `db.cpp` between the lines stays include-only.

## 6. Acceptance criteria

- `Read` never inserts into `cache` a value read before a commit that has since cached the key (reviewer traces the two writer paths and the reader).
- `db.h` documents the locking contract.
- `vault_state_tests`, `vault_primitive.py`, `vault_rpc_contract.py` pass on both lines; `src/vault/db.cpp` differs across lines only by includes.

## 7. Risks and side effects

- None functional. A reader outside `cs_main` can still observe pre-commit values (it could before too); what changes is that it can no longer make a `cs_main` holder observe them.

## 8. Effort estimate and dependencies

~30 minutes per line plus review. No dependencies.
