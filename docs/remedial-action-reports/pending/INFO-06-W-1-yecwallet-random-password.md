# INFO — 06/W-1, 06/V6-N3 — `randomPassword()` can emit a NUL-truncated RPC password and leaks its buffer

Repos / branches to change: `yecwallet-dd` (`fix/06-W-1-random-password` off `upgrade/vault`).
Audit source: `docs/audits/quantum-vault-ecosystem/06-clients-wallets-infra.md:207-213` (W-1); verification `verification/06-verification.md:25` (verdict), `:74` (W-1 detail), `:95` (V6-N3); consolidated `00-consolidated.md` row 06/Y-2..Y-5 ("yecwallet randomPassword fix").
Status: pending

## 1. Finding

When YecWallet creates `ycash.conf` for the bundled node it writes `rpcpassword=<randomPassword()>`. The generator indexes a 62-character alphabet with `bounded(sizeof(alphanum))`, and `sizeof` of the string literal is 63 (it counts the terminator), so each of the 10 positions has a 1-in-63 chance of being the NUL byte; `QString::fromStdString(s)` stops at the first NUL. About 15 % of generated passwords are shorter than 10 characters and about 1.6 % are empty. The RPC listens on loopback only (the generated conf sets no `rpcbind`/`rpcallowip`) and the wallet reads the same file back, so it still connects; inherited from upstream. The buffer `new char[passwordLength + 1]` is never `delete[]`d (V6-N3). Info.

## 2. Root cause

`yecwallet-dd/src/connection.cpp:120-134` at `bed26fd`:
```cpp
QString randomPassword() {
    static const char alphanum[] = "0123456789" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "abcdefghijklmnopqrstuvwxyz";   // :121-124
    const int passwordLength = 10;                                                                            // :125
    char* s = new char[passwordLength + 1];                                                                   // :126  (never deleted)
    for (int i = 0; i < passwordLength; ++i) {
        s[i] = alphanum[QRandomGenerator::global()->bounded(quint32(sizeof(alphanum)))];                     // :128  sizeof = 63
    }
    s[passwordLength] = 0;
    return QString::fromStdString(s);                                                                         // :134  stops at NUL
}
```
Used at `src/connection.cpp:203` (`out << "rpcpassword=" % randomPassword()`), inside `createZcashConf()` (declared `src/connection.h:51`; `randomPassword` itself has no header declaration). The conf's `rpcbind`/`rpcallowip` absence: `:200-203`.

## 3. Fix options considered

1. `sizeof(alphanum) - 1` only. Correct and minimal; keeps the leak and the 10-character length.
2. Rewrite with `QString`, `bounded(quint32(sizeof(alphanum) - 1))`, 24 characters, no heap. Accepted (same number of lines, no new dependency; `QRandomGenerator::global()` is already the CSPRNG-backed source).
3. Regenerate the password on every launch. Out of scope (the conf is read back by the wallet; changing it is a behaviour change for users who copied it).

## 4. Recommended fix

Replace `:120-134` with:
```cpp
QString randomPassword() {
    static const char alphanum[] =
        "0123456789"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz";
    constexpr int alphabetSize = sizeof(alphanum) - 1;   // the literal's terminator is not a symbol (audit 06/W-1)
    constexpr int passwordLength = 24;
    QString s;
    s.reserve(passwordLength);
    for (int i = 0; i < passwordLength; ++i)
        s.append(QLatin1Char(alphanum[QRandomGenerator::global()->bounded(quint32(alphabetSize))]));
    return s;
}
```
Declare it in `src/connection.h` (next to `createZcashConf` at `:51`) so a test can call it. No other change; existing `ycash.conf` files are untouched.

## 5. Tests

- New `tests/connection_test.cpp` (the harness: `CMakeLists.txt:337-351` registers `tests/<name>.cpp` as a ctest): 10,000 draws; each result has length 24, contains no `QChar(0)`, and every character is in the alphabet; the set of distinct first characters covers all 62 symbols after 10,000 draws (sanity that the range is right, probability of a miss < 10⁻⁶⁰). Register in CI (`yecwallet-tests.yml` already runs ctest).
- Manual: delete a test profile's `ycash.conf`, launch, confirm the written `rpcpassword=` line has 24 characters.

## 6. Acceptance criteria

- `bounded(quint32(sizeof(alphanum)))` no longer appears; no `new char[` in `connection.cpp`.
- `connection_test` passes in CI; the function is declared in `connection.h`.

## 7. Risks and side effects

- None for existing installs (the conf is only written when absent, `connection.cpp` `createZcashConf` path). New installs get a 24-character password. Loopback-only exposure unchanged.

## 8. Effort estimate and dependencies

- 1 hour. No dependencies.
