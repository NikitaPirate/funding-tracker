import logging
from datetime import datetime
from typing import Any

from funding_tracker.exchanges.dto import ContractInfo, FundingPoint
from funding_tracker.infrastructure import http_client

logger = logging.getLogger(__name__)

EXCHANGE_ID = "binance_coin-m"
API_ENDPOINT = "https://dapi.binance.com/dapi"

# Binance returns max 1000 records per request
# All COIN-M contracts use 8 hours funding interval
# Safe fetch window: 8 hours/record * 1000 records = 8000 hours
_MAX_FETCH_WINDOW_HOURS = 8000


async def get_contracts() -> list[ContractInfo]:
    """Fetch all perpetual contracts from Binance COIN-M."""
    logger.debug(f"Fetching contracts from {EXCHANGE_ID}")

    response: Any = await http_client.get(f"{API_ENDPOINT}/v1/exchangeInfo")

    contracts = []
    for instrument in response["symbols"]:
        if instrument["contractType"] == "PERPETUAL":
            contracts.append(
                ContractInfo(
                    asset_name=instrument["baseAsset"],
                    quote=instrument["quoteAsset"],
                    funding_interval=8,  # COIN-M uses default 8 hours
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
