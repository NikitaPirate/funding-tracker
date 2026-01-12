import logging
from datetime import datetime
from typing import Any

from funding_tracker.exchanges.dto import ContractInfo, FundingPoint
from funding_tracker.infrastructure import http_client

logger = logging.getLogger(__name__)

EXCHANGE_ID = "binance_usd-m"
API_ENDPOINT = "https://fapi.binance.com/fapi"

# Binance returns max 1000 records per request
# Minimum funding interval is 1 hour (some contracts like FLOWUSDT, GMTUSDT)
# Safe fetch window: 1 hour/record * 1000 records = 1000 hours
_MAX_FETCH_WINDOW_HOURS = 1000


async def get_contracts() -> list[ContractInfo]:
    """Fetch all perpetual contracts from Binance USD-M."""
    logger.debug(f"Fetching contracts from {EXCHANGE_ID}")

    # Fetch exchange info
    exchange_response: Any = await http_client.get(f"{API_ENDPOINT}/v1/exchangeInfo")

    # Fetch funding info for funding intervals
    funding_response: Any = await http_client.get(f"{API_ENDPOINT}/v1/fundingInfo")

    contracts = []

    # Build funding intervals mapping
    funding_intervals = {item["symbol"]: item["fundingIntervalHours"] for item in funding_response}

    for instrument in exchange_response["symbols"]:
        if instrument["contractType"] == "PERPETUAL":
            # Use funding interval from API, default to 8 hours
            funding_interval = funding_intervals.get(instrument["pair"], 8)

            contracts.append(
                ContractInfo(
                    asset_name=instrument["baseAsset"],
                    quote=instrument["quoteAsset"],
                    funding_interval=funding_interval,
                    section_name=EXCHANGE_ID,
                )
            )

    logger.debug(f"Fetched {len(contracts)} contracts from {EXCHANGE_ID}")
    return contracts


async def _fetch_history(symbol: str, start_time_ms: int, end_time_ms: int) -> list[FundingPoint]:
    """Fetch historical funding points for given time window."""
    logger.debug(
        f"Fetching history for {EXCHANGE_ID}/{symbol} "
        f"from {datetime.fromtimestamp(start_time_ms / 1000)} "
        f"to {datetime.fromtimestamp(end_time_ms / 1000)}"
    )

    response: Any = await http_client.get(
        f"{API_ENDPOINT}/v1/fundingRate",
        params={
            "symbol": symbol,
            "startTime": start_time_ms,
            "endTime": end_time_ms,
            "limit": 1000,
        },
    )

    points = []
    if response:
        for raw_record in response:
            rate = float(raw_record["fundingRate"])
            timestamp = datetime.fromtimestamp(raw_record["fundingTime"] / 1000.0)
            points.append(FundingPoint(rate=rate, timestamp=timestamp))

    logger.debug(f"Fetched {len(points)} funding points for {EXCHANGE_ID}/{symbol}")
    return points


async def fetch_history_before(
    symbol: str, before_timestamp: datetime | None
) -> list[FundingPoint]:
    """Fetch historical funding points before given timestamp (backward sync).

    If before_timestamp is None, fetch from beginning.
    Returns points in chronological order (oldest first).
    """
    end_time_ms = int(
        (before_timestamp.timestamp() if before_timestamp else datetime.now().timestamp()) * 1000
    )
    start_time_ms = end_time_ms - (_MAX_FETCH_WINDOW_HOURS * 60 * 60 * 1000)

    logger.debug(
        f"Fetching backward history for {EXCHANGE_ID}/{symbol} before {before_timestamp or 'now'}"
    )

    return await _fetch_history(symbol, start_time_ms, end_time_ms)


async def fetch_history_after(symbol: str, after_timestamp: datetime) -> list[FundingPoint]:
    """Fetch historical funding points after given timestamp (forward sync).

    Returns points in chronological order (oldest first).
    """
    start_time_ms = int(after_timestamp.timestamp() * 1000)
    end_time_ms = int(datetime.now().timestamp() * 1000)

    logger.debug(f"Fetching forward history for {EXCHANGE_ID}/{symbol} after {after_timestamp}")

    return await _fetch_history(symbol, start_time_ms, end_time_ms)


async def fetch_live_batch() -> dict[str, FundingPoint]:
    """Get all unsettled rates in one API call (preferred method)."""
    logger.debug(f"Fetching live rates batch from {EXCHANGE_ID}")

    response: Any = await http_client.get(f"{API_ENDPOINT}/v1/premiumIndex")

    now = datetime.now()
    rates = {}
    for item in response:
        symbol = item["symbol"]
        rate = float(item["lastFundingRate"])
        rates[symbol] = FundingPoint(rate=rate, timestamp=now)

    logger.debug(f"Fetched {len(rates)} live rates from {EXCHANGE_ID}")
    return rates
