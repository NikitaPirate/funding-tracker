# Scripts

## verify_exchange.py

Verification script for exchange adapters. Makes real API calls to verify that an exchange adapter correctly implements the required protocol.

### Usage

```bash
python scripts/verify_exchange.py <exchange_id>
```

### Example

```bash
python scripts/verify_exchange.py hyperliquid
```

### What it checks

1. **Protocol Validation**
   - Verifies `EXCHANGE_ID` constant exists
   - Verifies required methods: `get_contracts()`, `fetch_history()`
   - Verifies at least one live method exists: `fetch_live_batch()` or `fetch_live()`

2. **API: get_contracts()**
   - Makes real API call to exchange
   - Displays total number of contracts found
   - Shows table with first 5 contracts (asset, quote, funding interval)

3. **API: fetch_history()**
   - Fetches last 7 days of funding history for first contract
   - Displays number of data points retrieved
   - Shows date range and sample rate

4. **API: Live rates**
   - Calls `fetch_live_batch()` if available (preferred)
   - Falls back to `fetch_live()` for single symbol
   - Displays sample live funding rate

### Exit codes

- `0` - All checks passed
- `1` - Validation or API call failed

### When to use

- After implementing a new exchange adapter
- After modifying existing adapter
- To verify exchange API is still compatible
- Before deploying changes to production

### Example output

```
🔍 Verifying exchange adapter: hyperliquid

Step 1: Protocol Validation
  ✓ EXCHANGE_ID: hyperliquid
  ✓ Required methods: get_contracts, fetch_history
  ✓ Live method: fetch_live_batch

Step 2: API - get_contracts()
  ✓ Retrieved 157 contracts
  ┌──────────┬───────┬──────────────────┐
  │ Asset    │ Quote │ Funding Interval │
  ├──────────┼───────┼──────────────────┤
  │ BTC      │ USD   │ 1h               │
  │ ETH      │ USD   │ 1h               │
  │ ...      │ ...   │ ...              │
  └──────────┴───────┴──────────────────┘

Step 3: API - fetch_history(BTC)
  ✓ Retrieved 168 funding points
  Date range: 2025-11-06 → 2025-11-13
  Sample rate: 0.000100 (0.0100%)

Step 4: API - fetch_live
  ✓ fetch_live_batch() returned 157 rates
  Sample: BTC = 0.000095 (0.0095%)

✓ All checks passed for hyperliquid
```
