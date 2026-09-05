# DigiDollar Oracle Phase 1 Specification

> Historical pre-V1 note: this Phase One single-oracle/mock-price plan is
> retained for audit history only. Current V1 release behavior uses live
> exchange-backed oracle data and MuSig2 v0x03 bundles; mock price RPCs are
> regtest-only helpers.

**MVP for Testnet - Single Oracle Implementation**

**Version**: 2.1
**Date**: 2025-11-20
**Status**: 75% Complete - Ready for Final Push
**Scope**: Single Oracle (oracle.digibyte.io) - Testnet MVP Only

---

## IMPLEMENTATION STATUS OVERVIEW

**Current State: 75% Complete**

### ✅ COMPLETED (Keep for reference)
- ✅ Core data structures (COraclePriceMessage, COracleBundle) - src/primitives/oracle.h/cpp
- ✅ Schnorr signatures (BIP-340) - signing and verification working
- ✅ Bundle manager (1-of-1 consensus, singleton, price cache) - src/oracle/bundle_manager.cpp
- ✅ Chain parameters (testnet, mainnet, regtest) - src/kernel/chainparams.cpp
- ✅ Block integration (miner adds to coinbase) - src/node/miner.cpp
- ✅ Block validation (validates oracle data) - src/validation.cpp
- ✅ P2P message receiving (ORACLEPRICE handler) - src/net_processing.cpp
- ✅ Message validation, rate limiting, duplicate detection
- ✅ Mock oracle system - src/oracle/mock_oracle.cpp
- ✅ Test infrastructure (9 unit test files, 2 functional tests) - 100+ tests total

### ⚠️ PARTIALLY COMPLETE (Needs work)
- ⚠️ Exchange APIs (8 implemented, 3 need UniValue conversion) - src/oracle/exchange.cpp
- ⚠️ P2P broadcasting (receiving works, initial broadcast missing) - src/oracle/node.cpp
- ⚠️ Test suite (100+ tests written, ~20% failing)

### ❌ CRITICAL MISSING (Must implement for testnet)
- ❌ **OP_ORACLE opcode (0xbf)** - Currently using OP_RETURN with "ORC" marker
- ❌ Initial P2P broadcast from oracle node
- ❌ Exchange API completion (KuCoin, Crypto.com, Binance need UniValue conversion)
- ❌ Micro-USD vs cents consistency fix
- ❌ RPC commands (startoracle, getoraclestatus)
- ❌ MAD outlier filtering activation
- ❌ All tests passing

**Estimated Time to Complete: 4-6 days**

---

## 1. Executive Summary

### What We're Building

A **single oracle price feed** for DigiDollar testnet that:
- Runs at **oracle.digibyte.io:9001**
- Fetches real DGB/USD prices from 5+ exchanges
- Broadcasts prices via P2P network
- Miners include oracle data in blocks using **OP_ORACLE** opcode (0xbf)
- DigiDollar uses oracle prices for collateral calculations

**This is Phase 1:** 1-of-1 consensus, testnet only, hardcoded oracle.

**This is NOT:** Multiple oracles, staking, slashing, reputation, or mainnet deployment.

### Success Criteria (What's Left)

- [ ] **OP_ORACLE opcode defined and used** (0xbf)
- [ ] Oracle fetches prices from 5+ exchanges successfully
- [ ] Oracle broadcasts prices every ~60 seconds to P2P network
- [ ] Miners include oracle data in every block (after activation)
- [ ] DigiDollar validates collateral using real oracle prices (no mocks on testnet)
- [ ] **ALL oracle tests passing** (currently ~80% passing)
- [ ] Testnet can be reset and restarted cleanly

---

## 2. CRITICAL PATH TO COMPLETION

### Priority 0: OP_ORACLE Opcode Implementation (CRITICAL)

**Status**: ❌ **NOT IMPLEMENTED**

**Current Problem**: Implementation uses `OP_RETURN` with "ORC" marker (3-byte string). Spec requires `OP_ORACLE` opcode (0xbf) at byte position 1.

**Current Structure** (WRONG):
```
scriptPubKey: OP_RETURN | 'O' | 'R' | 'C' | <oracle_data>
              (0x6a)    | 0x4F| 0x52| 0x43| (bytes 4+)
              byte 0    | byte 1-3        | bytes 4+
```

**Required Structure** (CORRECT):
```
scriptPubKey: OP_RETURN | OP_ORACLE | <oracle_data>
              (0x6a)    | (0xbf)    | (bytes 2+)
              byte 0    | byte 1    | bytes 2+
```

**What Must Be Done**:

1. **Define OP_ORACLE opcode** - src/script/script.h
   - Add: `OP_ORACLE = 0xbf,  // OP_NOP15 - Oracle price data marker`
   - Location: After existing opcodes, before OP_INVALIDOPCODE

2. **Update block integration** - src/oracle/bundle_manager.cpp (lines 286-300)
   - Change from: `script << OP_RETURN << "ORC" << data`
   - Change to: `script << OP_RETURN << OP_ORACLE << data`
   - Remove "ORC" marker string entirely
   - Oracle data now starts at byte 2 (not byte 4)

3. **Update block validation** - src/validation.cpp (lines 4103-4111)
   - Check for: `scriptPubKey[0] == OP_RETURN && scriptPubKey[1] == OP_ORACLE`
   - Extract data from byte 2 onward (not byte 4 as with "ORC" marker)

4. **Update all tests**
   - Update tests expecting "ORC" marker to expect OP_ORACLE
   - Fix serialization tests

**Estimated Time**: 2-4 hours

**Acceptance Criteria**:
- [ ] OP_ORACLE defined in src/script/script.h
- [ ] Miner uses OP_ORACLE in coinbase
- [ ] Validation checks for OP_ORACLE
- [ ] All related tests updated and passing

### Priority 1: Fix P2P Broadcasting

**Status**: ⚠️ **RECEIVING WORKS, BROADCASTING MISSING**

**Current Problem**: Oracle node creates messages but can't broadcast to network. BroadcastMessage() only stores locally.

**Files**: src/oracle/bundle_manager.cpp (lines 454-474), src/oracle/node.cpp

**What Must Be Done**:

1. **Add CConnman to OracleBundleManager**
   - Add `CConnman* m_connman` member variable
   - Add `SetConnman(CConnman* connman)` method
   - Call from init.cpp during node initialization

2. **Implement BroadcastMessage()**
   ```cpp
   void OracleBundleManager::BroadcastMessage(const COraclePriceMessage& msg) {
       LOCK(m_mutex);

       if (!m_connman) {
           LogPrint(BCLog::ORACLE, "Cannot broadcast: no P2P connection\n");
           return;
       }

       // Store locally
       AddMessage(msg);

       // Broadcast to all peers
       m_connman->ForEachNode([&msg](CNode* node) {
           m_connman->PushMessage(node,
               CNetMsgMaker(node->GetCommonVersion()).Make(
                   NetMsgType::ORACLEPRICE, msg));
       });
   }
   ```

3. **Connect oracle node to P2P**
   - Update OracleNode::Run() to use BroadcastMessage()
   - Test with 2-node setup

**Estimated Time**: 1-2 days

**Acceptance Criteria**:
- [ ] BroadcastMessage() pushes to P2P network
- [ ] 2-node test shows message propagation
- [ ] oracle_p2p_tests pass

### Priority 2: Resolve Micro-USD vs Cents Confusion

**Status**: ❌ **INCONSISTENT**

**Current Problem**: Code uses micro-USD (1,000,000 = $1.00) but some comments/docs say cents (100 = $1.00). This is a 10,000x magnitude error!

**What Must Be Done**:

1. **Standardize on micro-USD**
   - Update ALL comments to say micro-USD
   - Rename any `price_cents` variables to `price_micro_usd`
   - Update DIGIDOLLAR_ORACLE_PHASE_ONE_SPEC.md (done)

2. **Verify DigiDollar calculations**
   - Check src/digidollar/validation.cpp uses micro-USD
   - Verify collateral calculations are correct
   - Test with known values

3. **Update all tests**
   - Ensure tests use micro-USD consistently
   - Update test expectations (12,340 micro-USD = $0.01234)

**Estimated Time**: 4-6 hours

**Acceptance Criteria**:
- [ ] All code comments say micro-USD
- [ ] No references to "cents" remain
- [ ] DigiDollar calculations verified correct
- [ ] Tests pass with micro-USD values

### Priority 3: Complete Exchange APIs

**Status**: ⚠️ **8 IMPLEMENTED, 3 NEED UNIVALVE**

**Current Implementation**:
- CoinMarketCap (90%) - Good, uses UniValue
- CoinGecko (90%) - Good, uses UniValue
- Messari (90%) - Good, uses UniValue
- Coinbase (85%) - Good
- Kraken (85%) - Good
- KuCoin (70%) - Uses string parsing, needs UniValue
- Crypto.com (70%) - Uses string parsing, needs UniValue
- Binance (60%) - Basic HTTP, needs UniValue

**Files**: src/oracle/exchange.cpp (1,237 lines)

**What Must Be Done**:

1. **Convert KuCoin, Crypto.com, Binance to UniValue**
   - Replace fragile string parsing
   - Use proper JSON object navigation
   - Add error handling

2. **Test all 8 exchanges**
   - Run oracle_exchange_tests.cpp
   - Verify median calculation works
   - Test with 3/5 minimum threshold

**Estimated Time**: 1 day

**Acceptance Criteria**:
- [ ] All 8 exchanges return real prices
- [ ] All use UniValue for JSON parsing (no string parsing)
- [ ] Median calculation works with 5+ successful fetches
- [ ] oracle_exchange_tests pass (currently ~56 tests)

### Priority 4: Activate MAD Outlier Filtering

**Status**: ⚠️ **IMPLEMENTED BUT NOT ACTIVE**

**Current Problem**: Code exists for MAD (Median Absolute Deviation) outlier filtering but simpler percentage threshold is used instead.

**Files**: src/oracle/exchange.cpp (lines 800-850)

**What Must Be Done**:

1. **Switch from percentage to MAD**
   - Change `CalculateMedianWithOutlierFiltering()` to use MAD algorithm
   - MAD threshold: 3.0 (standard for outlier detection)

2. **Test with realistic data**
   - Create test with one exchange returning bad price
   - Verify outlier is filtered out
   - Verify median is still accurate

**Estimated Time**: 2-3 hours

**Acceptance Criteria**:
- [ ] MAD algorithm active
- [ ] Outlier tests pass
- [ ] No false positives (good prices not filtered)

---

## 3. OP_ORACLE Opcode Specification

### Requirements

- **Opcode Value**: 0xbf (OP_NOP15)
- **Location**: `src/script/script.h`
- **Purpose**: Marks oracle data in OP_RETURN outputs
- **Format**: `OP_RETURN OP_ORACLE <serialized_oracle_data>`

### Coinbase Structure

```
vout[0] = Miner payout (standard)
vout[1] = OP_RETURN OP_ORACLE <oracle_bundle>
vout[2] = Witness commitment (if SegWit)
```

### Why OP_ORACLE (not plain OP_RETURN)

- Explicit semantic meaning for oracle data
- Easy identification in block explorers
- Distinguishes from other OP_RETURN uses
- Clean upgrade path for future enhancements
- **Matches specification exactly**

### ⚠️ CRITICAL: Oracle Data Structure

**IMPORTANT**: Oracle data is NOT stored in plain OP_RETURN. The structure is:

```
scriptPubKey: OP_RETURN | OP_ORACLE | <oracle_data>
              (0x6a)    | (0xbf)    | (actual COraclePriceMessage bytes)
              byte 0    | byte 1    | bytes 2+
```

**Breakdown**:
- **Byte 0** (`OP_RETURN`/`0x6a`): Standard Bitcoin opcode marking output as unspendable
- **Byte 1** (`OP_ORACLE`/`0xbf`): Custom DigiByte opcode identifying this as oracle data
- **Bytes 2+**: ALL oracle data (serialized COraclePriceMessage)

**This means**:
- ✅ Oracle data starts AFTER OP_ORACLE (at byte position 2)
- ✅ OP_ORACLE is the semantic marker distinguishing oracle data from other OP_RETURN uses
- ❌ Do NOT put oracle data directly after OP_RETURN (that would be plain OP_RETURN usage)
- ❌ Do NOT use OP_RETURN without OP_ORACLE for oracle data

**Why this matters**: The blockchain can have many OP_RETURN outputs (arbitrary data, metadata, etc.). The OP_ORACLE opcode specifically identifies which OP_RETURN outputs contain oracle price data.

### Implementation Details

**File**: src/script/script.h
```cpp
// Add after existing opcodes, before OP_INVALIDOPCODE
OP_ORACLE = 0xbf,  // OP_NOP15 - Oracle price data marker
```

**Creating OP_ORACLE output** (src/oracle/bundle_manager.cpp):
```cpp
CScript script;
script << OP_RETURN << OP_ORACLE << oracle_data;
```

**Parsing OP_ORACLE** (src/validation.cpp):
```cpp
if (scriptPubKey.size() >= 2 &&
    scriptPubKey[0] == OP_RETURN &&
    scriptPubKey[1] == OP_ORACLE) {
    // Extract oracle data (everything after OP_ORACLE)
    std::vector<unsigned char> oracle_data(
        scriptPubKey.begin() + 2,
        scriptPubKey.end()
    );
}
```

---

## 4. Chain Parameters (✅ COMPLETE)

### Testnet Configuration
- **Status**: ✅ COMPLETE
- **Activation Height**: 1,000,000
- **Oracle Endpoint**: oracle.digibyte.io:9001
- **Oracle ID**: 0 (always 0 for Phase 1)
- **Min Signatures**: 1 (1-of-1 consensus)
- **Max Age**: 300 seconds (5 minutes)
- **Oracle Public Key**: 32-byte XOnlyPubKey (BIP-340 Schnorr)
- **File**: src/kernel/chainparams.cpp (lines 520-540)

### Mainnet Configuration
- **Status**: ✅ COMPLETE
- **Activation Height**: INT_MAX (disabled)
- **Oracle List**: Empty (no oracles enabled)
- **File**: src/kernel/chainparams.cpp (lines 293-358)

### RegTest Configuration
- **Status**: ✅ COMPLETE
- **Activation Height**: 1 (immediate)
- **Oracle Endpoint**: 127.0.0.1:9001 (local testing)
- **Same oracle config as testnet for consistency**
- **File**: src/kernel/chainparams.cpp (lines 953-965)

---

## 5. Data Structures (✅ COMPLETE)

### COraclePriceMessage (✅ COMPLETE)

**Status**: ✅ **100% COMPLETE**

**Location**: `src/primitives/oracle.h` (lines 50-120)

**Fields**:
- version (uint32_t) - Protocol version, always 1 for Phase 1
- oracle_id (uint32_t) - Always 0 for Phase 1
- price_micro_usd (uint64_t) - Price in micro-USD (1,000,000 = $1.00)
- timestamp (int64_t) - Unix timestamp when created
- block_height (int32_t) - Block height when created
- nonce (uint64_t) - Random nonce for signature uniqueness
- oracle_pubkey (XOnlyPubKey) - 32-byte Schnorr public key
- schnorr_sig (vector<unsigned char>) - 64-byte Schnorr signature (BIP-340)

**Methods Implemented**:
- ✅ Sign(CKey) - Sign message with Schnorr
- ✅ Verify() - Verify Schnorr signature
- ✅ IsValid() - Validate price range and timestamp
- ✅ Serialization support (SERIALIZE_METHODS)

**Validation Rules** (✅ Implemented):
- Price: 100 to 10,000,000 micro-USD ($0.0001 to $10.00)
- Timestamp: Not more than 60 seconds in future, not older than 300 seconds
- Oracle ID: Must be 0 for Phase 1

---

## 6. Exchange API Integration (⚠️ 80% COMPLETE)

### Minimum Exchanges Required: 5 (We have 8)

**Status by Exchange**:

1. ✅ **CoinMarketCap** (90%) - pro-api.coinmarketcap.com (with API key)
   - Excellent, uses UniValue

2. ✅ **CoinGecko** (90%) - api.coingecko.com/api/v3/simple/price?ids=digibyte
   - Excellent, uses UniValue

3. ✅ **Messari** (90%) - data.messari.io/api/v1/assets/dgb/metrics/market-data
   - Excellent, uses UniValue

4. ✅ **Coinbase** (85%) - api.coinbase.com/v2/prices/DGB-USD/spot
   - Works well

5. ✅ **Kraken** (85%) - api.kraken.com/0/public/Ticker?pair=DGBUSD
   - Works well

**Additional Exchanges** (need UniValue conversion):
6. ⚠️ **KuCoin** (70%) - api.kucoin.com - Uses string parsing, needs UniValue
7. ⚠️ **Crypto.com** (70%) - api.crypto.com - Uses string parsing, needs UniValue
8. ⚠️ **Binance** (60%) - api.binance.com - Basic HTTP, needs UniValue

### Implementation Requirements

**Location**: `src/oracle/exchange.cpp` (1,237 lines)

**Tasks Remaining**:
- [ ] Convert KuCoin to UniValue (remove string parsing)
- [ ] Convert Crypto.com to UniValue (remove string parsing)
- [ ] Convert Binance to UniValue (remove string parsing)
- [ ] Test all 8 exchanges
- [ ] Verify median calculation works
- [ ] Require minimum 3 successful fetches (out of 8)

**Current Implementation**: Uses libcurl with 5-second timeout, rate limiting.

**Critical**: Always work in micro-USD. 1,000,000 micro-USD = $1.00 USD.

**Note**: Bittrex and Poloniex have been removed (exchanges no longer exist).

---

## 7. Oracle Node Daemon (✅ 85% COMPLETE)

### Status

**What's Working** (✅):
- ✅ Multi-threaded price fetching (PriceThreadFunc)
- ✅ Hardcoded testnet key management (privkey 0x01)
- ✅ Schnorr message signing (BIP-340)
- ✅ Automatic 15-second update cycle
- ✅ Testnet-only activation enforcement

**What's Missing** (❌):
- ❌ P2P broadcast connection (broadcasts to local only)

**Location**: `src/oracle/node.cpp` (728 lines)

**What It Does**:
- Runs in background thread
- Every 15 seconds: fetch median price from exchanges
- Create COraclePriceMessage with current height, timestamp, nonce
- Sign message with oracle private key (Schnorr BIP-340)
- **[NEEDS FIX]** Broadcast to all P2P peers via ORACLEPRICE message
- Log price and broadcast status
- Handle errors gracefully

**Configuration**:
- Oracle private key from digibyte.conf: `oracleprivkey=<hex>`
- Testnet only (guard against mainnet)
- Requires P2P connection manager (g_connman)

---

## 8. P2P Network Protocol (⚠️ 60% COMPLETE)

### Message Type (✅ COMPLETE)

**Status**: ✅ **DEFINED AND IMPLEMENTED**

**Location**: `src/protocol.h` (lines 276-289)

Message type: `ORACLEPRICE = "oracleprice"`

### Message Handler (✅ RECEIVING COMPLETE, ❌ BROADCASTING MISSING)

**Status**: ✅ **Receiving Works**, ❌ **Broadcasting Missing**

**Location**: `src/net_processing.cpp` (lines 5316-5516)

**What's Working**:
- ✅ Deserialize COraclePriceMessage from message payload
- ✅ Validate message (IsValid() checks)
- ✅ Verify Schnorr signature (Verify())
- ✅ Check oracle_id == 0 (Phase 1 requirement)
- ✅ Check timestamp freshness (within 5 minutes)
- ✅ Add to OracleBundleManager singleton
- ✅ Relay to other peers (except sender to avoid echo)
- ✅ Rate limit: max 100 messages per hour per peer
- ✅ Apply misbehavior score for invalid messages

**What's Missing**:
- ❌ Initial broadcast from oracle node (see Priority 1 above)

---

## 9. Bundle Manager (✅ 95% COMPLETE)

### Status

**What's Working** (✅):
- ✅ Singleton pattern with GetInstance()
- ✅ Thread-safe with RecursiveMutex
- ✅ 1-of-1 consensus (store latest message)
- ✅ Price cache (map<height, price>)
- ✅ Keep last 1000 blocks in cache
- ✅ AddMessage() stores latest message
- ✅ GetLatestPrice() returns cached price
- ✅ GetPriceAtHeight() returns historical price
- ✅ GetLatestMessage() for block inclusion

**What Needs Work** (⚠️):
- ⚠️ BroadcastMessage() only stores locally (needs P2P push)

**Location**: `src/oracle/bundle_manager.h` and `bundle_manager.cpp` (1,197 lines)

**Implementation Notes**:
- Phase 1: Simply store the latest message (no multi-oracle consensus)
- Latest message from oracle_id=0 IS the consensus
- No bundle creation needed (1-of-1 = the message IS the bundle)

---

## 10. Block Integration - Miner (✅ 100% COMPLETE)

### Status: ✅ **COMPLETE** (except OP_ORACLE opcode)

**Location**: `src/node/miner.cpp` (lines 170-177)

**What It Does**:
- ✅ Called from CreateNewBlock()
- ✅ After activation height, gets latest message from OracleBundleManager
- ✅ Serializes COraclePriceMessage to byte vector
- ⚠️ **Creates OP_RETURN script** (needs OP_ORACLE opcode added)
- ✅ Adds as new vout to coinbase (typically vout[1])
- ✅ Oracle data optional during transition period

**Current Format**:
```
OP_RETURN + "ORC" marker (3 bytes) + oracle data
```

**Required Format** (after OP_ORACLE implementation):
```
OP_RETURN + OP_ORACLE (0xbf) + oracle data
```

**Size**: ~85 bytes total (well within OP_RETURN limits)

---

## 11. Block Validation (✅ 90% COMPLETE)

### Status: ✅ **MOSTLY COMPLETE**

**Location**: `src/validation.cpp` (lines 4103-4111) - CheckBlock()

**What's Working**:
- ✅ CheckBlock() validates oracle bundle structure
- ✅ ValidateBlockOracleData() verifies signatures
- ✅ Enforces Phase 1 constraints (exactly 1 message)
- ✅ Graceful degradation during transition period
- ✅ Network-specific activation (testnet/regtest only)

**Location**: `src/oracle/validation.cpp` (needs creation/review)

**Tasks**:
- [ ] Verify extracts OP_ORACLE correctly (update for 0xbf opcode)
- [ ] Find OP_RETURN OP_ORACLE output in coinbase
- [ ] Extract oracle data bytes (everything after OP_ORACLE)
- [ ] Deserialize to COraclePriceMessage
- [ ] Call msg.IsValid() - validate price range, timestamp
- [ ] Call msg.Verify() - verify Schnorr signature
- [ ] Verify oracle_id == 0 (Phase 1 requirement)
- [ ] If all valid, add to OracleBundleManager cache

---

## 12. DigiDollar Integration (⚠️ NEEDS VERIFICATION)

### Status: ⚠️ **IMPLEMENTED BUT NEEDS MICRO-USD VERIFICATION**

**Location**: `src/digidollar/validation.cpp`

**What's Implemented**:
- Oracle price lookup from OracleBundleManager
- Fallback to mock price during development
- Collateral calculations using oracle price

**What Needs Verification**:
- [ ] Verify uses micro-USD (not cents!)
- [ ] Test collateral calculations with known values
- [ ] Verify mock fallback disabled on testnet
- [ ] Test DigiDollar mint with real oracle price

**Helper Functions Needed**:
**Location**: `src/oracle/integration.cpp` (may need creation)

- GetCurrentOraclePrice() - Return latest price
- GetOraclePriceAtHeight(int) - Return price at specific height
- IsOracleReady() - Check if oracle has any price available

---

## 13. RPC Commands (❌ NOT IMPLEMENTED)

### getoraclestatus (❌ NOT IMPLEMENTED)

**Purpose**: Check oracle system status and current price

**Should Return**:
- enabled (bool) - Is oracle active?
- price_micro_usd (uint64) - Current price in micro-USD
- price_usd (double) - Current price in USD
- last_update (timestamp) - When last updated
- oracle_id (int) - Always 0 for Phase 1

**Implementation**: Add to src/rpc/oracle.cpp (may need creation)

### startoracle (❌ NOT IMPLEMENTED)

**Purpose**: Start oracle daemon (testnet only)

**Requirements**:
- Only works on testnet (reject on mainnet)
- Requires `oracleprivkey` in config
- Starts background daemon thread

**Returns**: Success message or error

**Implementation**: Add to src/rpc/oracle.cpp

---

## 14. Testing Status (⚠️ ~80% PASSING)

### Unit Test Files (✅ CREATED, ⚠️ ~80% PASSING)

**Total Tests**: 100+ tests across 9 files

**Files**:
1. ✅ **oracle_config_tests.cpp** (13 tests) - **PASSING**
   - Chain params configuration tests

2. ⚠️ **oracle_bundle_manager_tests.cpp** (8 tests) - **MIXED**
   - ❌ oracle_node_price_fetching failing
   - ✅ Other bundle manager tests passing

3. ❌ **oracle_block_validation_tests.cpp** (8 tests) - **FAILING**
   - Multiple validation tests failing
   - ConnectBlock cache update issues
   - Signature validation issues

4. ⚠️ **oracle_message_tests.cpp** (15 tests) - **MIXED**
   - Schnorr signature tests
   - Message format tests

5. ⚠️ **oracle_miner_tests.cpp** (6 tests) - **MIXED**
   - Coinbase integration tests

6. ❌ **oracle_p2p_tests.cpp** (30+ tests) - **MANY FAILING**
   - P2P protocol tests failing (broadcasting not implemented)

7. ⚠️ **oracle_exchange_tests.cpp** (56 tests) - **MIXED**
   - Exchange API tests (some stubbed exchanges failing)

8. ✅ **oracle_integration_tests.cpp** (3 tests) - **PASSING**
   - End-to-end flow tests

9. ⚠️ **digidollar_oracle_tests.cpp** (50+ tests) - **MIXED**
   - Comprehensive oracle tests

**Pass Rate**: ~80% (estimated from architecture doc)

### Functional Tests (✅ CREATED, ⚠️ MIXED RESULTS)

1. **digidollar_oracle.py** (1152 lines, 20+ scenarios)
   - ✅ Basic oracle tests passing
   - ❌ Advanced TDD Phase 2 tests RED (expected)

2. **feature_oracle_p2p.py** (408 lines, 6+ tests)
   - ❌ Most tests RED (expected, awaiting P2P broadcast)

**Tasks**:
- [ ] Fix failing unit tests
- [ ] Get oracle_block_validation_tests passing
- [ ] Get oracle_p2p_tests passing (after P2P broadcast implemented)
- [ ] Get oracle_exchange_tests passing (after exchanges completed)
- [ ] Achieve 90%+ test pass rate

---

## 15. Configuration Examples (✅ DOCUMENTED)

### Oracle Operator (oracle.digibyte.io)

**digibyte.conf**:
```ini
testnet=1
oracle=1
oracleprivkey=<ORACLE_PRIVATE_KEY_HEX>
```

### Regular Testnet Node

**digibyte.conf**:
```ini
testnet=1
```

(Oracle messages received automatically via P2P)

---

## 16. Deployment Checklist

### Prerequisites
- [ ] OP_ORACLE opcode implemented (0xbf)
- [ ] P2P broadcasting working
- [ ] All 5+ exchanges returning real prices
- [ ] All critical tests passing
- [ ] Micro-USD consistency verified

### Testnet Launch Procedure

1. **Implement Remaining Features** (4-6 days)
   - Implement OP_ORACLE opcode
   - Fix P2P broadcasting
   - Complete exchange APIs
   - Fix micro-USD consistency
   - Get tests passing

2. **Generate Oracle Keys**
   - Generate oracle private key (32-byte, BIP-340 compatible)
   - Derive public key
   - Update chainparams.cpp with public key
   - Rebuild

3. **Deploy Oracle Node**
   - Configure oracle.digibyte.io server
   - Install DigiByte Core v8.26
   - Configure with oracle=1 and private key
   - Start daemon

4. **Test Oracle**
   - Verify price fetching from exchanges
   - Verify P2P broadcasting
   - Verify blocks include oracle data
   - Test DigiDollar minting

5. **Launch Testnet**
   - Deploy to testnet
   - Monitor for 24+ hours
   - Verify stability

---

## 17. File Checklist

### ✅ Files Already Created

- ✅ `src/primitives/oracle.h` - Core data structures
- ✅ `src/primitives/oracle.cpp` - Data structure implementation
- ✅ `src/oracle/bundle_manager.h` - Bundle manager interface
- ✅ `src/oracle/bundle_manager.cpp` - Bundle manager implementation (1,197 lines)
- ✅ `src/oracle/exchange.h` - Exchange API interface
- ✅ `src/oracle/exchange.cpp` - Exchange API implementation (1,237 lines)
- ✅ `src/oracle/node.h` - Oracle daemon interface
- ✅ `src/oracle/node.cpp` - Oracle daemon implementation (728 lines)
- ✅ `src/oracle/mock_oracle.h` - Mock oracle for testing
- ✅ `src/oracle/mock_oracle.cpp` - Mock oracle implementation
- ✅ `src/test/oracle_*.cpp` - 9 unit test files (100+ tests)
- ✅ `test/functional/digidollar_oracle.py` - Functional tests (1152 lines)
- ✅ `test/functional/feature_oracle_p2p.py` - P2P tests (408 lines)

### ⚠️ Files Needing Modification

- ⚠️ **`src/script/script.h`** - Add OP_ORACLE = 0xbf
- ⚠️ `src/kernel/chainparams.cpp` - Verify oracle.digibyte.io configuration
- ⚠️ `src/net_processing.cpp` - P2P handler (already has receiving, just verify)
- ⚠️ `src/node/miner.cpp` - Update to use OP_ORACLE opcode
- ⚠️ `src/validation.cpp` - Update to check for OP_ORACLE opcode
- ⚠️ `src/oracle/bundle_manager.cpp` - Fix BroadcastMessage() P2P push
- ⚠️ `src/oracle/exchange.cpp` - Complete stubbed exchanges
- ⚠️ `src/digidollar/validation.cpp` - Verify micro-USD usage
- ⚠️ All test files - Update for OP_ORACLE opcode

### ❌ Files That May Need Creation

- ❌ `src/oracle/validation.cpp` - Dedicated oracle validation functions (may already be in bundle_manager.cpp)
- ❌ `src/oracle/integration.cpp` - DigiDollar integration helpers (may already be in bundle_manager.cpp)
- ❌ `src/rpc/oracle.cpp` - RPC commands (startoracle, getoraclestatus)

---

## 18. Critical Design Decisions (✅ CONFIRMED)

### Price Format: MICRO-USD (✅ CONFIRMED)

**Decision**: Use micro-USD throughout (1,000,000 = $1.00)

**Rationale**:
- Avoids floating point precision issues
- Provides 6 decimal places of precision
- Prevents magnitude errors
- Consistent with implementation

**Status**: ✅ Implementation uses micro-USD, just needs comment/doc updates

### 1-of-1 Consensus (✅ IMPLEMENTED)

**Decision**: Phase 1 uses single oracle, no complex consensus

**Implementation**: Latest message from oracle_id=0 IS the consensus

**Status**: ✅ Fully implemented in bundle_manager.cpp

### Testnet Only Deployment (✅ IMPLEMENTED)

**Status**: ✅ Hardcoded in chainparams.cpp
- Testnet: Activation height 1,000,000
- Mainnet: Activation height INT_MAX (never)
- Guards in code prevent mainnet activation

### OP_ORACLE Opcode (❌ NOT IMPLEMENTED)

**Decision**: Use OP_ORACLE (0xbf) for semantic clarity

**Current State**: Using OP_RETURN with "ORC" marker

**Status**: ❌ **MUST BE IMPLEMENTED** (see Priority 0)

---

## 19. Acceptance Criteria - What Must Be True for Testnet Deployment

### Critical Requirements (Must Have)

- [ ] **OP_ORACLE opcode defined** (0xbf) in src/script/script.h
- [ ] oracle.digibyte.io configured in chainparams.cpp (testnet)
- [ ] 5+ exchanges fetch prices successfully
- [ ] Oracle daemon broadcasts every 60 seconds via P2P
- [ ] P2P messages relay across network
- [ ] Bundle manager caches latest price
- [ ] Miners include OP_ORACLE in coinbase vout[1]
- [ ] Block validation verifies Schnorr signatures
- [ ] DigiDollar uses oracle price (micro-USD, not mock)
- [ ] **ALL critical unit tests passing** (oracle_block_validation, oracle_bundle_manager, oracle_message)
- [ ] **Functional tests passing** (at least digidollar_oracle.py basics)

### Quality Requirements

- [ ] No compiler warnings
- [ ] No memory leaks (valgrind clean)
- [ ] Follows DigiByte coding standards
- [ ] Proper error handling everywhere
- [ ] Network type checked everywhere (testnet only)
- [ ] Micro-USD used consistently (no cents references)

### Documentation Requirements

- [✅] DIGIDOLLAR_ORACLE_ARCHITECTURE.md complete (current status documented)
- [✅] DIGIDOLLAR_ORACLE_PHASE_ONE_SPEC.md updated (this document)
- [ ] Operator setup guide
- [ ] Testnet reset procedures
- [ ] Configuration examples
- [ ] RPC command documentation

---

## 20. Estimated Time to Complete

**Total Time: 4-6 days** (with focused work)

### Day 1-2: Critical Path
- OP_ORACLE opcode implementation (2-4 hours)
- P2P broadcasting fix (1-2 days)
- Micro-USD consistency fix (4-6 hours)

### Day 3: Exchange APIs
- Convert KuCoin, Crypto.com, Binance to UniValue (1 day)

### Day 4: Testing & Bug Fixes
- Fix failing unit tests (1 day)
- Verify all critical tests passing

### Day 5-6: Final Integration & Testing
- End-to-end testing (1 day)
- Documentation updates
- Testnet deployment preparation

---

## Quick Reference

### Key Constants

```
ORACLE_ID = 0
ORACLE_ACTIVATION_HEIGHT_TESTNET = 1000000
ORACLE_ACTIVATION_HEIGHT_MAINNET = INT_MAX
ORACLE_MIN_SIGNATURES = 1
ORACLE_MAX_AGE_SECONDS = 300
ORACLE_FETCH_INTERVAL_SECONDS = 15
MICRO_USD_PER_USD = 1000000
OP_ORACLE = 0xbf
```

### Oracle Endpoint

```
oracle.digibyte.io:9001
```

### Message Types

```
NetMsgType::ORACLEPRICE = "oracleprice"
```

### Price Range

```
Min: 100 micro-USD ($0.0001)
Max: 10,000,000 micro-USD ($10.00)
```

### Signature Type

```
BIP-340 Schnorr
XOnlyPubKey: 32 bytes
Signature: 64 bytes
```

---

## FINAL NOTES

This specification reflects the **current implementation status** (75% complete) and provides a **clear roadmap** to 100% completion for testnet deployment.

**Most Critical Tasks**:
1. ⚠️ Implement OP_ORACLE opcode (0xbf)
2. ⚠️ Fix P2P broadcasting
3. ⚠️ Complete exchange APIs
4. ⚠️ Get all tests passing

**After these are complete, the oracle system will be ready for testnet deployment.**

---

**END OF SPECIFICATION**

*This document defines what needs to be implemented for a tested, working oracle system ready for testnet deployment.*
