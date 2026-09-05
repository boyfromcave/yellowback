# DigiDollar System Flowcharts
**Technical Reference Guide for DigiByte v8.26**
*Last Updated: 2025-12-18*
*Document Version: 2.0 - ERR Semantics Corrected*

This document provides visual flowcharts explaining how DigiDollar works. Each flowchart includes the technical details from the actual implementation.

---

## Table of Contents
1. [Minting DigiDollars](#1-minting-digidollars)
2. [Transferring DigiDollars](#2-transferring-digidollars)
3. [Redemption Process](#3-redemption-process)
4. [Oracle Price System](#4-oracle-price-system)
5. [Dynamic Collateral Adjustment (DCA)](#5-dynamic-collateral-adjustment-dca)
6. [Emergency Redemption Ratio (ERR)](#6-emergency-redemption-ratio-err)
7. [Volatility Protection](#7-volatility-protection)

---

## 1. Minting DigiDollars

### What is Minting?
Minting is how you create new DigiDollars by locking your DGB as collateral. The longer you lock, the less collateral required.

### Collateral Ratio Schedule (9 Tiers)

| Lock Period | Collateral Ratio | Example: Mint $100 DD |
|-------------|------------------|----------------------|
| 1 hour      | 1000%            | Lock $1,000 of DGB   |
| 30 days     | 500%             | Lock $500 of DGB     |
| 3 months    | 400%             | Lock $400 of DGB     |
| 6 months    | 350%             | Lock $350 of DGB     |
| 1 year      | 300%             | Lock $300 of DGB     |
| 3 years     | 250%             | Lock $250 of DGB     |
| 5 years     | 225%             | Lock $225 of DGB     |
| 7 years     | 212%             | Lock $212 of DGB     |
| 10 years    | 200%             | Lock $200 of DGB     |

### Minting Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MINT DIGIDOLLARS FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

    User Request: "I want to mint $500 DigiDollars, lock for 1 year"
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: VALIDATE REQUEST                                                    │
│  ─────────────────────────                                                   │
│  • Check: Amount ≥ $100 minimum? (minMintAmount = 10000 cents)              │
│  • Check: Amount ≤ $100,000 maximum? (maxMintAmount = 10000000 cents)       │
│  • Check: Is minting frozen? (Volatility check)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     │                             │
                  PASS ✓                        FAIL ✗
                     │                             │
                     ▼                             ▼
┌──────────────────────────────┐    ┌──────────────────────────────┐
│  STEP 2: GET ORACLE PRICE    │    │  RETURN ERROR                │
│  ────────────────────────    │    │  "Amount out of range" or    │
│  • Fetch current DGB/USD     │    │  "Minting temporarily frozen"│
│  • Price in micro-USD        │    └──────────────────────────────┘
│  • Example: 6500 = $0.0065   │
└──────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: CALCULATE COLLATERAL REQUIREMENT                                    │
│  ────────────────────────────────────────                                    │
│                                                                              │
│  Formula:                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ BaseRatio = GetCollateralRatioForLockTime(1 year) = 300%            │    │
│  │ DCAMultiplier = GetDCAMultiplier(systemHealth)                       │    │
│  │ FinalRatio = BaseRatio × DCAMultiplier                               │    │
│  │                                                                      │    │
│  │ CollateralUSD = DDAmount × (FinalRatio / 100)                        │    │
│  │ CollateralDGB = CollateralUSD / OraclePrice                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Example (healthy system, DCA = 1.0x):                                       │
│  • DD Amount: $500                                                           │
│  • Base Ratio: 300% (1 year lock)                                            │
│  • DCA Multiplier: 1.0x (system health ≥ 150%)                              │
│  • Collateral USD: $500 × 3.0 = $1,500                                       │
│  • Oracle Price: $0.0065/DGB                                                 │
│  • Collateral DGB: $1,500 ÷ $0.0065 = 230,769 DGB                           │
└─────────────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: SELECT UTXOS & BUILD TRANSACTION                                    │
│  ────────────────────────────────────────                                    │
│                                                                              │
│  Select DGB UTXOs totaling ≥ 230,769 DGB + fees                              │
│                                                                              │
│  Transaction Structure:                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  INPUTS:                                                            │     │
│  │    vin[0]: DGB UTXO (e.g., 250,000 DGB)                            │     │
│  │    vin[1]: DGB UTXO for fees (e.g., 1 DGB)                         │     │
│  │                                                                     │     │
│  │  OUTPUTS:                                                           │     │
│  │    vout[0]: COLLATERAL VAULT (P2TR with MAST tree)                 │     │
│  │             • Amount: 230,769 DGB                                   │     │
│  │             • Script: Taproot with CLTV timelock                       │     │
│  │             • Locked until: current_height + 2,102,400 blocks       │     │
│  │                                                                     │     │
│  │    vout[1]: DD TOKEN OUTPUT (Simple P2TR key-path)                 │     │
│  │             • Amount: 546 satoshis (dust limit)                     │     │
│  │             • Represents: $500.00 DigiDollars (50000 cents)         │     │
│  │             • Script: P2TR key-path only (no MAST)                  │     │
│  │                                                                     │     │
│  │    vout[2]: OP_RETURN METADATA                                      │     │
│  │             • Type: DD_TX_MINT (0x44440100)                         │     │
│  │             • DD Amount: 50000 cents                                │     │
│  │             • Lock Duration: 2,102,400 blocks                       │     │
│  │             • Collateral Ratio: 300%                                │     │
│  │                                                                     │     │
│  │    vout[3]: DGB CHANGE (if any)                                     │     │
│  │             • Amount: 250,000 - 230,769 - fees ≈ 19,230 DGB        │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: SIGN TRANSACTION                                                    │
│  ────────────────────────                                                    │
│  • Sign DGB inputs with owner's private key (ECDSA or Schnorr)              │
│  • Create Schnorr signature for collateral output commitment                 │
└─────────────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 6: BROADCAST & CONFIRM                                                 │
│  ───────────────────────────                                                 │
│  • Broadcast to DigiByte P2P network                                         │
│  • Miners include in block                                                   │
│  • Confirmation: Transaction is now on-chain                                 │
│                                                                              │
│  RESULT:                                                                     │
│  ✓ 230,769 DGB locked in collateral vault                                    │
│  ✓ $500 DD token created and spendable                                       │
│  ✓ Vault unlocks after 1 year (2,102,400 blocks)                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Code Locations
- `src/digidollar/txbuilder.cpp` - MintTxBuilder class
- `src/consensus/digidollar.h` - Collateral ratio definitions
- `src/consensus/dca.cpp` - DCA multiplier calculations

---

## 2. Transferring DigiDollars

### What is a Transfer?
Sending DigiDollars from one address to another. The collateral stays locked - only the DD token moves.

### Transfer Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TRANSFER DIGIDOLLARS FLOW                            │
└─────────────────────────────────────────────────────────────────────────────┘

    User Request: "Send $200 DD to DDabc123..."
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: VALIDATE                                                            │
│  ────────────────                                                            │
│  • Check: Recipient address valid? (DD/TD/RD prefix for Mainnet/Test/Reg)   │
│  • Check: Amount ≥ $1 minimum? (minOutputAmount = 100 cents)                │
│  • Check: User has sufficient DD balance?                                    │
│  • Check: Operations not frozen? (Volatility check)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: SELECT DD UTXOS                                                     │
│  ───────────────────────                                                     │
│  • Find DD UTXOs in wallet totaling ≥ $200                                   │
│  • DD UTXOs are vout[1] outputs from previous mint/transfer txs              │
│  • Each DD UTXO has an associated DD amount in its OP_RETURN                 │
│                                                                              │
│  Example Selection:                                                          │
│  • UTXO A: $150 DD                                                           │
│  • UTXO B: $100 DD                                                           │
│  • Total: $250 DD (need $200, will get $50 change)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: BUILD TRANSFER TRANSACTION                                          │
│  ──────────────────────────────────                                          │
│                                                                              │
│  Transaction Structure:                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  INPUTS:                                                            │     │
│  │    vin[0]: DD UTXO A ($150 DD value)                               │     │
│  │    vin[1]: DD UTXO B ($100 DD value)                               │     │
│  │    vin[2]: DGB UTXO for fees (e.g., 0.1 DGB)                       │     │
│  │                                                                     │     │
│  │  OUTPUTS:                                                           │     │
│  │    vout[0]: DD TO RECIPIENT                                         │     │
│  │             • Address: DDabc123... (P2TR)                           │     │
│  │             • Amount: 546 satoshis (dust)                           │     │
│  │             • Represents: $200.00 DD                                │     │
│  │                                                                     │     │
│  │    vout[1]: DD CHANGE BACK TO SENDER                                │     │
│  │             • Amount: 546 satoshis (dust)                           │     │
│  │             • Represents: $50.00 DD change                          │     │
│  │                                                                     │     │
│  │    vout[2]: OP_RETURN METADATA                                      │     │
│  │             • Type: DD_TX_TRANSFER (0x44440200)                     │     │
│  │             • Output 0 Amount: 20000 cents ($200)                   │     │
│  │             • Output 1 Amount: 5000 cents ($50)                     │     │
│  │                                                                     │     │
│  │    vout[3]: DGB FEE CHANGE (if any)                                 │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: SIGN WITH KEY-PATH (SIMPLE SCHNORR)                                 │
│  ───────────────────────────────────────────                                 │
│                                                                              │
│  DD tokens use SIMPLE P2TR (key-path only, no MAST tree):                    │
│  • Create Schnorr signature for each DD input                                │
│  • No script path needed - just sign with internal key                       │
│  • Sign fee inputs normally (ECDSA or Schnorr)                               │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  KEY INSIGHT: DD tokens are designed for easy spending!            │     │
│  │                                                                     │     │
│  │  • DD Output (vout[1]): Simple P2TR, key-path only                 │     │
│  │  • Collateral (vout[0]): Complex P2TR with MAST tree               │     │
│  │                                                                     │     │
│  │  This means: Transfer DD = Simple Schnorr signature                │     │
│  │              Redeem collateral = Complex MAST script path          │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: BROADCAST & CONFIRM                                                 │
│  ───────────────────────────                                                 │
│                                                                              │
│  RESULT:                                                                     │
│  ✓ Recipient receives $200 DD at DDabc123...                                 │
│  ✓ Sender keeps $50 DD change                                                │
│  ✓ Original collateral vaults unchanged (still locked)                       │
│  ✓ Fee paid in DGB                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Code Locations
- `src/wallet/digidollarwallet.cpp` - TransferDigiDollar()
- `src/digidollar/txbuilder.cpp` - TransferTxBuilder class

---

## 3. Redemption Process

### What is Redemption?
Burning DigiDollars to unlock your collateral DGB. There are **2 redemption paths** depending on system health.

### The 2 Redemption Paths

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        2 REDEMPTION PATHS OVERVIEW                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────┐   ┌──────────────────────────────────────┐
│           NORMAL REDEMPTION           │   │           ERR REDEMPTION              │
│  ─────────────────────────────────── │   │  ─────────────────────────────────── │
│                                       │   │                                       │
│  When:                                │   │  When:                                │
│  • Lock time has expired              │   │  • Lock time has expired              │
│  • System health ≥ 100%               │   │  • System health < 100%               │
│                                       │   │                                       │
│  Requires:                            │   │  Requires (BURNS MORE DD!):           │
│  • Burn original minted DD amount     │   │  • Burn MORE DD than you minted       │
│  • Wait for timelock expiry           │   │  • Wait for timelock expiry           │
│                                       │   │                                       │
│  Returns:                             │   │  DD Burn Required (by health tier):   │
│  • 100% of locked collateral          │   │  • 95-100% health → Burn 105% DD      │
│                                       │   │  • 90-95% health → Burn 111% DD       │
│                                       │   │  • 85-90% health → Burn 118% DD       │
│                                       │   │  • <85% health → Burn 125% DD (max)   │
│                                       │   │                                       │
│                                       │   │  Returns: 100% COLLATERAL (always!)   │
└──────────────────────────────────────┘   └──────────────────────────────────────┘

IMPORTANT: ERR increases DD burn, NOT reduces collateral. You always get 100% collateral back.
IMPORTANT: New minting is BLOCKED when system health < 100%.
```

### Normal Redemption Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NORMAL REDEMPTION FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

    User: "My 1-year lock has expired, I want my DGB back"
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: CHECK TIMELOCK                                                      │
│  ──────────────────────                                                      │
│  • Get collateral vault's unlock height from OP_RETURN                       │
│  • Compare: current_height ≥ unlock_height?                                  │
│                                                                              │
│  Example:                                                                    │
│  • Minted at height: 1,000,000                                               │
│  • Lock period: 1 year = 2,102,400 blocks                                    │
│  • Unlock height: 3,102,400                                                  │
│  • Current height: 3,500,000 → UNLOCKED ✓                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     │                             │
              UNLOCKED ✓                    STILL LOCKED ✗
                     │                             │
                     ▼                             ▼
┌──────────────────────────────┐    ┌──────────────────────────────┐
│  STEP 2: CHECK SYSTEM HEALTH │    │  Cannot redeem yet.          │
│  ──────────────────────────  │    │  Must wait for timelock.     │
│                              │    └──────────────────────────────┘
│  System health = collateral  │
│  value / DD supply × 100     │
│                              │
│  IF health ≥ 100%:           │
│    → Normal redemption       │
│    → Burn original DD        │
│    → Get 100% collateral     │
│                              │
│  IF health < 100%:           │
│    → ERR redemption          │
│    → Burn MORE DD (105-125%) │
│    → Get 100% collateral     │
└──────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: BUILD REDEEM TRANSACTION                                            │
│  ────────────────────────────────                                            │
│                                                                              │
│  Transaction Structure:                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  INPUTS:                                                            │     │
│  │    vin[0]: Collateral vault (P2TR with timelock)                   │     │
│  │    vin[1]: DD tokens to burn                                       │     │
│  │            • Normal: Original minted amount                         │     │
│  │            • ERR: MORE DD (original / ERR ratio)                   │     │
│  │    vin[2]: DGB for transaction fees                                │     │
│  │                                                                     │     │
│  │  OUTPUTS:                                                           │     │
│  │    vout[0]: Returned collateral to owner                           │     │
│  │             (ALWAYS 100% - collateral never reduced!)               │     │
│  │    vout[1]: OP_RETURN with DD_TX_REDEEM (0x44440300)               │     │
│  │    vout[2]: DGB change (if any)                                    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: SIGN TRANSACTION                                                    │
│  ────────────────────────                                                    │
│                                                                              │
│  • Collateral input: Schnorr key-path signature (P2TR)                       │
│  • DD input: Schnorr key-path signature (P2TR)                               │
│  • Fee input: Standard ECDSA signature                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: BURN DD TOKENS                                                      │
│  ──────────────────────                                                      │
│  • DD inputs are consumed (spent)                                            │
│  • No DD output created → DD is destroyed ("burned")                         │
│  • DD supply decreases by redemption amount                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 6: BROADCAST & CONFIRM                                                 │
│  ───────────────────────────                                                 │
│                                                                              │
│  RESULT (Normal - system health ≥ 100%):                                     │
│  ✓ Collateral (230,769 DGB) returned to owner - 100%                         │
│  ✓ $500 DD burned (original minted amount)                                   │
│  ✓ Vault closed permanently                                                  │
│                                                                              │
│  RESULT (ERR - system health < 100%):                                        │
│  ✓ Collateral (230,769 DGB) returned to owner - 100% (FULL!)                │
│  ✓ MORE DD burned (e.g., $625 DD at 80% health for $500 position)           │
│  ✓ Extra DD burned creates buying pressure, stabilizing system               │
│  ✓ Vault closed permanently                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### ERR Adjustment Tiers

**CRITICAL: ERR increases DD burn requirement, NOT reduces collateral!**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ERR (EMERGENCY REDEMPTION RATIO) TIERS                    │
│                    ★ BURNS MORE DD, RETURNS FULL COLLATERAL ★               │
└─────────────────────────────────────────────────────────────────────────────┘

  System Health │ ERR Ratio │ DD Burn Required    │ Collateral Returned
  ──────────────┼───────────┼─────────────────────┼─────────────────────────
  95-100%       │  0.95     │ 105% (100/0.95)     │ 100% (FULL - 230,769 DGB)
  90-95%        │  0.90     │ 111% (100/0.90)     │ 100% (FULL - 230,769 DGB)
  85-90%        │  0.85     │ 118% (100/0.85)     │ 100% (FULL - 230,769 DGB)
  < 85%         │  0.80     │ 125% (100/0.80)     │ 100% (FULL - 230,769 DGB)

  Example: $500 DD position at 80% system health:
  • Must burn: $500 / 0.80 = $625 DD (25% more than minted)
  • Receives: 100% of locked collateral (230,769 DGB)
  • Extra $125 DD burned creates buying pressure, helping system recover

  WHY THIS DESIGN?
  • Creates demand for DD during crises (people need more DD to redeem)
  • Buying pressure helps stabilize DD price
  • Collateral is NEVER taken from users
  • Fair to all DD holders
```

### Key Code Locations
- `src/digidollar/txbuilder.cpp` - RedeemTxBuilder class
- `src/digidollar/validation.cpp` - ValidateNormalRedemptionConditions()
- `src/consensus/err.cpp` - ERR tier calculation

---

## 4. Oracle Price System

### What is the Oracle?
The Oracle provides real-world DGB/USD prices to the blockchain. Without it, the system can't know what your collateral is worth.

### Oracle System Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORACLE PRICE SYSTEM FLOW                             │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────┐
                    │         13 EXCHANGE APIs            │
                    │  (Real libcurl + Mock Fallback)     │
                    └─────────────────────────────────────┘
                                    │
        ┌───────┬───────┬───────┬───┴───┬───────┬───────┬───────┐
        ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼
    ┌───────┐┌───────┐┌───────┐┌───────┐┌───────┐┌───────┐┌───────┐
    │Binance││Coinbase│Kraken ││KuCoin ││Gate.io││  HTX  ││Crypto.│
    │$0.0065││$0.0066││$0.0064││$0.0065││$0.0063││$0.0067││com    │
    └───┬───┘└───┬───┘└───┬───┘└───┬───┘└───┬───┘└───┬───┘└───┬───┘
        │       │       │       │       │       │       │
        └───────┴───────┴───────┴───┬───┴───────┴───────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: FETCH PRICES (Every 60 seconds)                                     │
│  ───────────────────────────────────────                                     │
│                                                                              │
│  Exchange Fetchers in src/oracle/exchange.cpp:                               │
│  • BinanceFetcher     → api.binance.vision/api/v3/ticker/price              │
│  • CoinbaseFetcher    → api.coinbase.com/v2/prices/DGB-USD/spot             │
│  • KrakenFetcher      → api.kraken.com/0/public/Ticker?pair=DGBUSD          │
│  • KuCoinFetcher      → api.kucoin.com/api/v1/market/orderbook/level1       │
│  • GateIOFetcher      → api.gateio.ws/api/v4/spot/tickers                   │
│  • HTXFetcher         → api.htx.com/market/detail/merged                    │
│  • CryptoComFetcher   → api.crypto.com/v2/public/get-ticker                 │
│  • CoinGeckoFetcher   → api.coingecko.com/api/v3/simple/price               │
│  • MessariFetcher     → data.messari.io/api/v1/assets/dgb/metrics/market    │
│  • BittrexFetcher     → api.bittrex.com/v3/markets/DGB-USD/ticker           │
│  • PoloniexFetcher    → api.poloniex.com/markets/DGB_USDT/price             │
│  • CoinMarketCapFetcher → pro-api.coinmarketcap.com (requires API key)      │
│  • MultiExchangeAggregator → Combines all above                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: FILTER OUTLIERS (MAD + IQR Methods)                                 │
│  ───────────────────────────────────────────                                 │
│                                                                              │
│  Raw prices: [0.0063, 0.0064, 0.0065, 0.0065, 0.0066, 0.0067, 0.0120]       │
│                                                              ▲               │
│                                                         OUTLIER             │
│                                                                              │
│  Filtering methods (src/oracle/bundle_manager.cpp):                          │
│  1. Basic: Remove prices > 10% from median                                   │
│  2. MAD (Modified Z-Score): Statistical outlier detection                    │
│  3. IQR (Interquartile Range): 1.5 × IQR rule                               │
│                                                                              │
│  After filtering: [0.0063, 0.0064, 0.0065, 0.0065, 0.0066, 0.0067]          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: CALCULATE MEDIAN PRICE                                              │
│  ──────────────────────────────                                              │
│                                                                              │
│  Sorted prices: [0.0063, 0.0064, 0.0065, 0.0065, 0.0066, 0.0067]            │
│                                    ▲                                         │
│                                 MEDIAN                                       │
│                                                                              │
│  Median = (0.0065 + 0.0065) / 2 = $0.0065 per DGB                           │
│                                                                              │
│  Convert to micro-USD: 0.0065 × 1,000,000 = 6,500 micro-USD                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: CREATE ORACLE MESSAGE (COraclePriceMessage)                         │
│  ───────────────────────────────────────────────────                         │
│                                                                              │
│  Message Structure (src/primitives/oracle.h):                                │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  uint32_t oracle_id        = 0                (Oracle identifier)  │     │
│  │  uint64_t price_micro_usd  = 6500             (Price: $0.0065)     │     │
│  │  int64_t  timestamp        = 1733836800       (Unix timestamp)     │     │
│  │  int32_t  block_height     = 1234567          (Current height)     │     │
│  │  uint64_t nonce            = random           (Uniqueness)         │     │
│  │  XOnlyPubKey oracle_pubkey = [32 bytes]       (Schnorr pubkey)     │     │
│  │  vector<uchar> schnorr_sig = [64 bytes]       (BIP-340 signature)  │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Operator message size: ~128 bytes before MuSig2 aggregation                 │
│  V1 coinbase format: MuSig2 v0x03 aggregate bundle                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: EMBED IN BLOCK (Coinbase Transaction)                               │
│  ─────────────────────────────────────────────                               │
│                                                                              │
│  V1: MuSig2 v0x03 bundle with signer bitmap and aggregate signature          │
│                                                                              │
│  V1 Coinbase OP_RETURN:                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Byte 0:     OP_RETURN (0x6a)                                      │     │
│  │  Byte 1:     OP_ORACLE (0xbf)                                      │     │
│  │  Byte 2:     Push version byte                                      │     │
│  │  Byte 3:     Version (0x03)                                        │     │
│  │  Payload:    signer bitmap, epoch, price, timestamp, MuSig2 sig    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 6: VALIDATE & CACHE                                                    │
│  ────────────────────────                                                    │
│                                                                              │
│  Validation checks (ValidateBlockOracleData):                                │
│  ✓ Timestamp within 1 hour of block time                                     │
│  ✓ Not from the future (60s tolerance)                                       │
│  ✓ Oracle pubkey matches chainparams                                         │
│  ✓ Price within sanity bounds ($0.0001 - $1000)                             │
│                                                                              │
│  Price Cache:                                                                │
│  • Stored by block height                                                    │
│  • Accessible via GetPriceAtHeight(height)                                   │
│  • Used for collateral calculations                                          │
│  • Max 1000 blocks cached (auto-eviction)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Mock Oracle (RegTest/Testing)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MOCK ORACLE (Testing Mode)                              │
└─────────────────────────────────────────────────────────────────────────────┘

  For RegTest and development, a mock oracle provides prices:

  RPC Command: setmockoracleprice <price_micro_usd>

  Example:
  $ digibyte-cli -regtest setmockoracleprice 6500
  → Sets price to $0.0065/DGB (6500 micro-USD)

  Default mock price: 6500 micro-USD ($0.0065/DGB)

  Code location: src/oracle/mock_oracle.cpp
```

### Key Code Locations
- `src/oracle/exchange.cpp` - Exchange API implementations
- `src/oracle/bundle_manager.cpp` - Price aggregation and caching
- `src/primitives/oracle.h` - COraclePriceMessage, COracleBundle
- `src/oracle/mock_oracle.cpp` - MockOracleManager

---

## 5. Dynamic Collateral Adjustment (DCA)

### What is DCA?
DCA increases collateral requirements when system health drops, protecting the system during stress.

### DCA Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│               DYNAMIC COLLATERAL ADJUSTMENT (DCA) FLOW                       │
└─────────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────────┐
                        │  SYSTEM HEALTH CHECK    │
                        │  (Every Block)          │
                        └───────────┬─────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: CALCULATE SYSTEM HEALTH                                             │
│  ───────────────────────────────                                             │
│                                                                              │
│  Formula (src/consensus/dca.cpp):                                            │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                                                                     │     │
│  │  System Health % = (Total Collateral Value USD / Total DD Supply)  │     │
│  │                    × 100                                           │     │
│  │                                                                     │     │
│  │  Where:                                                            │     │
│  │  • Total Collateral Value = Sum of all locked DGB × Oracle Price   │     │
│  │  • Total DD Supply = Sum of all DigiDollars in circulation         │     │
│  │                                                                     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Example:                                                                    │
│  • Total locked DGB: 100,000,000 DGB                                         │
│  • Oracle price: $0.0065/DGB                                                 │
│  • Total collateral value: $650,000                                          │
│  • Total DD supply: $500,000                                                 │
│  • System Health: ($650,000 / $500,000) × 100 = 130%                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: DETERMINE HEALTH TIER                                               │
│  ─────────────────────────────                                               │
│                                                                              │
│  Health Tiers (src/consensus/dca.cpp lines 19-24):                           │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  HEALTH RANGE       TIER        MULTIPLIER    EFFECT               │     │
│  │  ─────────────────────────────────────────────────────────────────│     │
│  │  ≥ 150%            HEALTHY      1.0x         Normal collateral     │     │
│  │  120% - 149%       WARNING      1.2x         +20% extra collateral │     │
│  │  100% - 119%       CRITICAL     1.5x         +50% extra collateral │     │
│  │  < 100%            EMERGENCY    2.0x         +100% extra collateral│     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  In our example (130% health) → WARNING tier → 1.2x multiplier              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: APPLY DCA TO NEW MINTS                                              │
│  ──────────────────────────────                                              │
│                                                                              │
│  Formula:                                                                    │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Adjusted Ratio = Base Ratio × DCA Multiplier                      │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Example:                                                                    │
│  • User wants to mint $500 DD with 1-year lock                               │
│  • Base ratio: 300%                                                          │
│  • System health: 130% (WARNING tier)                                        │
│  • DCA multiplier: 1.2x                                                      │
│  • Adjusted ratio: 300% × 1.2 = 360%                                        │
│  • Collateral required: $500 × 3.6 = $1,800 (instead of $1,500)             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  VISUAL: DCA MULTIPLIER BY SYSTEM HEALTH                                     │
│  ───────────────────────────────────────                                     │
│                                                                              │
│  Multiplier                                                                  │
│     2.0x │█████████████████████████████████████                              │
│          │█ EMERGENCY (< 100%)                                               │
│     1.5x │                            █████████                              │
│          │                            █ CRITICAL                             │
│     1.2x │                                      ████████                     │
│          │                                      █ WARNING                    │
│     1.0x │                                               ████████████████████│
│          │                                               █ HEALTHY           │
│          └──────────────────────────────────────────────────────────────────│
│          0%      50%      100%     120%     150%     200%     250%          │
│                           System Health %                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Code Locations
- `src/consensus/dca.cpp` - DynamicCollateralAdjustment class
- `src/consensus/dca.h` - HealthTier definitions

---

## 6. Emergency Redemption Ratio (ERR)

### What is ERR?
**ERR increases DD burn requirement when system health falls below 100%.** Collateral return is ALWAYS 100% - users never lose collateral. ERR creates buying pressure on DD during crises by requiring more DD to redeem.

### ERR Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              EMERGENCY REDEMPTION RATIO (ERR) FLOW                           │
│              ★ BURNS MORE DD, RETURNS FULL COLLATERAL ★                      │
└─────────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────────┐
                        │   SYSTEM HEALTH CHECK   │
                        │   Health < 100%?        │
                        └───────────┬─────────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     │                             │
                  YES ✓                          NO ✗
                     │                             │
                     ▼                             ▼
┌──────────────────────────────┐    ┌──────────────────────────────┐
│  ERR ACTIVATES               │    │  ERR INACTIVE                │
│  ─────────────               │    │  ────────────                │
│  System is under-            │    │  Normal operations           │
│  collateralized!             │    │  Burn original DD amount     │
│  New minting BLOCKED!        │    │  Get 100% collateral         │
└──────────────────────────────┘    └──────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: CALCULATE DD BURN REQUIREMENT                                       │
│  ──────────────────────────────────────                                      │
│                                                                              │
│  ERR Tiers (src/consensus/err.cpp):                                          │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  SYSTEM HEALTH     ERR RATIO    DD BURN REQUIRED    COLLATERAL     │     │
│  │  ─────────────────────────────────────────────────────────────────│     │
│  │  95% - 100%        0.95         105% (1/0.95)       100% (FULL)    │     │
│  │  90% - 95%         0.90         111% (1/0.90)       100% (FULL)    │     │
│  │  85% - 90%         0.85         118% (1/0.85)       100% (FULL)    │     │
│  │  < 85%             0.80         125% (1/0.80) max   100% (FULL)    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  CRITICAL: Collateral is NEVER reduced - only DD burn increases!             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: APPLY ERR TO REDEMPTION                                             │
│  ───────────────────────────────                                             │
│                                                                              │
│  Formula (GetRequiredDDBurn):                                                │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Required DD = Original DD Minted / ERR Ratio                      │     │
│  │  Collateral Return = 100% (always full amount)                     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Example (System health: 92%):                                               │
│  • User wants to redeem $500 DD position                                     │
│  • Collateral locked: 230,769 DGB                                            │
│  • ERR tier: 90-95% → 0.90 ratio                                            │
│  • DD required to burn: $500 / 0.90 = $555.56 DD                            │
│  • User burns $555.56 DD, receives ALL 230,769 DGB back                     │
│  • Extra $55.56 DD burned creates buying pressure on DD market               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: QUEUE MANAGEMENT (FIFO)                                             │
│  ───────────────────────────────                                             │
│                                                                              │
│  During ERR, redemptions may be queued:                                      │
│                                                                              │
│  Queue Order (First-In-First-Out):                                           │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Position 1: Alice   - $1,000 DD - Queued at height 1,000,000     │     │
│  │  Position 2: Bob     - $500 DD   - Queued at height 1,000,005     │     │
│  │  Position 3: Charlie - $2,000 DD - Queued at height 1,000,010     │     │
│  │  ...                                                               │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Processing:                                                                 │
│  • Oldest redemptions processed first                                        │
│  • System processes as collateral allows                                     │
│  • Queue clears as system health improves                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: SYSTEM RECOVERY                                                     │
│  ───────────────────────                                                     │
│                                                                              │
│  ERR deactivates when:                                                       │
│  • System health returns to ≥ 100%                                          │
│  • DGB price increases (more collateral value)                               │
│  • DD gets burned (less liabilities)                                         │
│  • New high-ratio mints add collateral                                       │
│                                                                              │
│  On deactivation:                                                            │
│  • Normal 100% redemptions resume                                            │
│  • Remaining queue processes at full value                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### ERR Visual Timeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ERR ACTIVATION TIMELINE                              │
│                  ★ DD BURN INCREASES, COLLATERAL STAYS 100% ★               │
└─────────────────────────────────────────────────────────────────────────────┘

  System
  Health %
     │
  150% ───────────────────────────────────────────────────────────
     │  HEALTHY (DCA 1.0x, burn 100% DD)
     │
  120% ───────────────────────────────────────────────────────────
     │  WARNING (DCA 1.2x, burn 100% DD)
     │
  100% ═══════════════════════════════════════════════════════════  ← ERR THRESHOLD
     │        ERR ACTIVE (MINTING BLOCKED)     │    ERR INACTIVE
     │        Burn MORE DD to redeem           │    Normal operations
   95% ───────────────────┐                    │
     │  burn 105% DD      │                    │
   90% ──────────┐        │                    │
     │  burn 111%│        │                    │
   85% ──┐       │        │                    │
     │   │burn   │        │                    │
         │118%   │        │                    │
         ▼       ▼        ▼                    │
       125%    118%     111%                  100%
       DD burn DD burn  DD burn              DD burn
       (max)                                 (normal)

       COLLATERAL RETURN: ALWAYS 100% IN ALL TIERS!

  Time →
       ├────────────────────────────────────────────────────────────►
       │  DGB price drops   │  Users redeem by    │  Price recovers  │
       │  causing under-    │  burning MORE DD    │  system healthy  │
       │  collateralization │  (creates DD demand)│  again           │
```

### Key Code Locations
- `src/consensus/err.cpp` - EmergencyRedemptionRatio class
- `src/consensus/err.h` - ERRState, ERR tier definitions

---

## 7. Volatility Protection

### What is Volatility Protection?
Automatic freezes when DGB price moves too fast, preventing exploitation during market chaos.

### Volatility Protection Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      VOLATILITY PROTECTION FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────────┐
                        │   PRICE MONITORING      │
                        │   (Every Block)         │
                        └───────────┬─────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: RECORD PRICE POINT                                                  │
│  ──────────────────────────                                                  │
│                                                                              │
│  PricePoint structure:                                                       │
│  • price: Current oracle price (micro-USD)                                   │
│  • timestamp: Unix timestamp                                                 │
│  • height: Block height                                                      │
│                                                                              │
│  History maintained: Up to 30 days (720 hourly data points)                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: CALCULATE VOLATILITY                                                │
│  ────────────────────────────                                                │
│                                                                              │
│  Three time windows calculated:                                              │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  1-Hour Volatility  = Max % change from 1 hour ago                 │     │
│  │  24-Hour Volatility = Max % change from 24 hours ago               │     │
│  │  7-Day Volatility   = Max % change from 7 days ago                 │     │
│  │                                                                     │     │
│  │  Also calculates: 2× Standard Deviation for sustained volatility  │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Example calculation:                                                        │
│  • Price 1 hour ago: $0.0065                                                 │
│  • Current price: $0.0078                                                    │
│  • 1-hour volatility: |($0.0078 - $0.0065) / $0.0065| × 100 = 20%           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: CHECK THRESHOLDS                                                    │
│  ────────────────────────                                                    │
│                                                                              │
│  Threshold Levels (src/consensus/volatility.h lines 58-64):                  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  THRESHOLD          WINDOW      ACTION                             │     │
│  │  ─────────────────────────────────────────────────────────────────│     │
│  │  WARNING_1H = 10%   1 hour      Log warning                        │     │
│  │  FREEZE_MINT = 20%  1 hour      FREEZE NEW MINTING                 │     │
│  │  FREEZE_ALL = 30%   24 hours    FREEZE ALL DD OPERATIONS           │     │
│  │  EMERGENCY = 50%    7 days      EMERGENCY MODE                     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     │              │              │
               1H ≥ 20%       24H ≥ 30%       7D ≥ 50%
                     │              │              │
                     ▼              ▼              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  ┌────────────────┐  ┌────────────────────┐  ┌────────────────────────────┐ │
│  │ FREEZE MINTING │  │ FREEZE ALL         │  │ EMERGENCY MODE             │ │
│  │ ─────────────  │  │ ──────────         │  │ ──────────────             │ │
│  │                │  │                    │  │                            │ │
│  │ • New mints    │  │ • New mints        │  │ • All operations blocked   │ │
│  │   blocked      │  │   blocked          │  │ • Requires oracle override │ │
│  │ • Transfers OK │  │ • Transfers blocked│  │   (8-of-15 approval)       │ │
│  │ • Redemptions  │  │ • Redemptions      │  │                            │ │
│  │   OK           │  │   blocked          │  │                            │ │
│  └────────────────┘  └────────────────────┘  └────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: COOLDOWN PERIOD                                                     │
│  ───────────────────────                                                     │
│                                                                              │
│  After freeze triggers:                                                      │
│  • Cooldown: 144 blocks (~36 hours at 15s blocks)                           │
│  • Freeze lifts only if volatility drops below WARNING level                 │
│  • Manual override possible with 8-of-15 oracle approval                     │
│                                                                              │
│  Timeline example:                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Block 1000: Price spikes 25% in 1 hour → MINT FREEZE              │     │
│  │  Block 1001-1143: Cooldown period (freeze active)                  │     │
│  │  Block 1144: If volatility < 10% → Freeze lifts                    │     │
│  │              If volatility ≥ 10% → Cooldown extends                │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Volatility Visual Timeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VOLATILITY PROTECTION TIMELINE                            │
└─────────────────────────────────────────────────────────────────────────────┘

  Volatility %
     │
  50% ─────────────────────────────────────────────────────── EMERGENCY (7D)
     │                              ▲
  40% ─────────────────────────────┐│
     │                             ││
  30% ─────────────────────────────┼┼────────────────────── FREEZE ALL (24H)
     │                         ▲   ││
  20% ─────────────────────────┼───┼┼────────────────────── FREEZE MINT (1H)
     │                    ▲    │   ││
  10% ─────────────────────────┼───┼┼────────────────────── WARNING
     │         ▲          │    │   ││
     │         │          │    │   ││         Normal
   0% ─────────┴──────────┴────┴───┴┴─────────────────────── Operations
     │
     └────────────────────────────────────────────────────────────────────────►
                                Time
           │      │        │      │       │
           │      │        │      │       └─ Price stabilizes
           │      │        │      └─ Major crash (EMERGENCY)
           │      │        └─ Price volatility increases
           │      └─ Minor spike (WARNING only)
           └─ Normal market
```

### Key Code Locations
- `src/consensus/volatility.cpp` - VolatilityMonitor class
- `src/consensus/volatility.h` - VolatilityThresholds, VolatilityState

---

## Quick Reference: Transaction Types

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DIGIDOLLAR TRANSACTION TYPES                              │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┬────────────┬─────────────────────────────────────────────┐
  │ TYPE         │ ENCODED AS │ DESCRIPTION                                 │
  ├──────────────┼────────────┼─────────────────────────────────────────────┤
  │ DD_TX_MINT   │ 0x44440100 │ Lock DGB, create new DigiDollars            │
  │ DD_TX_TRANSFER│ 0x44440200│ Move DD between addresses                   │
  │ DD_TX_REDEEM │ 0x44440300 │ Burn DD, unlock 100% collateral (normal)    │
  │ DD_TX_ERR    │ 0x44440500 │ Burn MORE DD (105-125%), get 100% collateral│
  └──────────────┴────────────┴─────────────────────────────────────────────┘

  NOTE: DD_TX_PARTIAL (0x44440400) is disabled - partial redemptions not supported.
  NOTE: ERR burns MORE DD, but collateral return is ALWAYS 100%.

  The 0x4444 prefix = "DD" in ASCII (DigiDollar identifier)
```

---

## Quick Reference: Address Prefixes

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DIGIDOLLAR ADDRESS FORMATS                              │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┬────────────────┬────────────────────────────────────────────┐
  │ NETWORK  │ PREFIX         │ EXAMPLE                                    │
  ├──────────┼────────────────┼────────────────────────────────────────────┤
  │ Mainnet  │ DD             │ DDabc123def456...                          │
  │ Testnet  │ TD             │ TDxyz789ghi012...                          │
  │ Regtest  │ RD             │ RDtest123abc456...                         │
  └──────────┴────────────────┴────────────────────────────────────────────┘

  All DigiDollar addresses use P2TR (Taproot/Pay-to-Taproot) format.
```

---

## Summary: Protection System Interaction

```
┌─────────────────────────────────────────────────────────────────────────────┐
│            HOW PROTECTION SYSTEMS WORK TOGETHER                              │
└─────────────────────────────────────────────────────────────────────────────┘

                           ┌───────────────────┐
                           │   ORACLE PRICE    │
                           │   ($0.0065/DGB)   │
                           └─────────┬─────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
           ┌────────────────┐ ┌────────────┐ ┌────────────────┐
           │  VOLATILITY    │ │   DCA      │ │     ERR        │
           │  PROTECTION    │ │            │ │                │
           └───────┬────────┘ └─────┬──────┘ └───────┬────────┘
                   │                │                │
                   │ Price moves    │ Calculates     │ Activates if
                   │ too fast?      │ system health  │ health < 100%
                   │                │                │
                   ▼                ▼                ▼
           ┌────────────────┐ ┌────────────┐ ┌────────────────┐
           │ FREEZE         │ │ ADJUST     │ │ INCREASE DD    │
           │ Operations     │ │ Collateral │ │ BURN (not      │
           │                │ │ Requirements│ │ collateral!)   │
           └───────┬────────┘ └─────┬──────┘ └───────┬────────┘
                   │                │                │
                   └────────────────┼────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │     PROTECTED DIGIDOLLAR      │
                    │     SYSTEM                    │
                    │                               │
                    │  • Stable value ($1 = 1 DD)   │
                    │  • Fair collateral returns    │
                    │  • Resilient to market chaos  │
                    └───────────────────────────────┘
```

---

*Document Version: 2.0 - ERR Semantics Corrected*
*Based on DigiByte v8.26 DigiDollar Implementation*
*Updated: 2025-12-18*
*Code locations verified against actual implementation*

**Key Changes in v2.0:**
- ERR now correctly documented as increasing DD burn requirement (not reducing collateral)
- Collateral return is ALWAYS 100% in all ERR tiers
- Minting is BLOCKED during ERR (system health < 100%)
- Added formula: Required DD = Original DD / ERR Ratio
