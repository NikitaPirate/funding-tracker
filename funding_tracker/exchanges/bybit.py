import logging
from datetime import datetime
from typing import Any

from funding_tracker.exchanges.dto import ContractInfo, FundingPoint
from funding_tracker.infrastructure import http_client

logger = logging.getLogger(__name__)

EXCHANGE_ID = "bybit"
API_ENDPOINT = "https://api.bybit.com"

# Bybit returns max 200 records per request
# Minimal funding interval is 1 hour -> set max fetch window to 198 hours
_MAX_FETCH_WINDOW_HOURS = 198


async def get_contracts() -> list[ContractInfo]:
    """Fetch all perpetual contracts from Bybit (both USDT and USDC)."""
    logger.debug(f"Fetching contracts from {EXCHANGE_ID}")

    # Fetch all instruments with pagination
    all_contracts = []
    cursor = None

    while True:
        params = {"category": "linear"}
        if cursor:
            params["cursor"] = cursor

        response: Any = await http_client.get(
            f"{API_ENDPOINT}/v5/market/instruments-info", params=params
        )

        all_contracts.extend(response["result"]["list"])

        cursor = response["result"].get("nextPageCursor")
        if not cursor:
            break

    # Filter for perpetual contracts (both USDT and USDC)
    contracts = []
    for contract in all_contracts:
        if contract["contractType"] == "LinearPerpetual":
            contracts.append(
                ContractInfo(
                    asset_name=contract["baseCoin"],
                    quote=contract["quoteCoin"],
                    funding_interval=int(
                        contract["fundingInterval"] / 60
                    ),  # Convert minutes to hours
                    section_name=EXCHANGE_ID,
                )
            )

    logger.debug(f"Fetched {len(contracts)} contracts from {EXCHANGE_ID}")
    return contracts


async def fetch_history_before(
    symbol: str, before_timestamp: datetime | None
) -> list[FundingPoint]:
    """Fetch historical funding points before given timestamp (backward sync).

    If before_timestamp is None, fetch from beginning.
    Returns points in chronological order (oldest first).
    """
    logger.debug(
        f"Fetching backward history for {EXCHANGE_ID}/{symbol} before {before_timestamp or 'now'}"
    )

    # Calculate time window
    end_time_ms = int(
        (before_timestamp.timestamp() if before_timestamp else datetime.now().timestamp()) * 1000
    )
    start_time_ms = end_time_ms - (_MAX_FETCH_WINDOW_HOURS * 60 * 60 * 1000)

    # Fetch from API
    response: Any = await http_client.get(
        f"{API_ENDPOINT}/v5/market/funding/history",
        params={
            "symbol": symbol,
            "category": "linear",
            "startTime": start_time_ms,
            "endTime": end_time_ms,
        },
    )

    # Parse response
    points = []
    raw_records = response.get("result", {}).get("list", [])
    if raw_records:
        for raw_record in raw_records:
            rate = float(raw_record["fundingRate"])
            timestamp = datetime.fromtimestamp(int(raw_record["fundingRateTimestamp"]) / 1000.0)
            points.append(FundingPoint(rate=rate, timestamp=timestamp))

    logger.debug(f"Fetched {len(points)} funding points for {EXCHANGE_ID}/{symbol}")
    return points


async def fetch_history_after(symbol: str, after_timestamp: datetime) -> list[FundingPoint]:
    """Fetch historical funding points after given timestamp (forward sync).

    Returns points in chronological order (oldest first).
    """
    logger.debug(f"Fetching forward history for {EXCHANGE_ID}/{symbol} after {after_timestamp}")

    # Calculate time window
    start_time_ms = int(after_timestamp.timestamp() * 1000)
    end_time_ms = int(datetime.now().timestamp() * 1000)

    # Fetch from API
    response: Any = await http_client.get(
        f"{API_ENDPOINT}/v5/market/funding/history",
        params={
            "symbol": symbol,
            "category": "linear",
            "startTime": start_time_ms,
            "endTime": end_time_ms,
        },
    )

    # Parse response
    points = []
    raw_records = response.get("result", {}).get("list", [])
    if raw_records:
        for raw_record in raw_records:
            rate = float(raw_record["fundingRate"])
            timestamp = datetime.fromtimestamp(int(raw_record["fundingRateTimestamp"]) / 1000.0)
            points.append(FundingPoint(rate=rate, timestamp=timestamp))

    logger.debug(f"Fetched {len(points)} funding points for {EXCHANGE_ID}/{symbol}")
    return points


async def fetch_live(symbol: str) -> FundingPoint:
    """Get unsettled rate for single symbol.

    Bybit only provides per-symbol endpoint for live rates.
    """
    logger.debug(f"Fetching live rate for {EXCHANGE_ID}/{symbol}")

    response: Any = await http_client.get(
        f"{API_ENDPOINT}/v5/market/tickers", params={"symbol": symbol, "category": "linear"}
    )

    data = response.get("result", {}).get("list", [])
    if not data:
        raise ValueError(f"No funding rate data for {symbol}")

    record = data[0]
    now = datetime.now()
    rate = float(record["fundingRate"])
    return FundingPoint(rate=rate, timestamp=now)
