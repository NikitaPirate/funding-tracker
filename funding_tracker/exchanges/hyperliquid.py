"""HyperLiquid exchange adapter.

API docs: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
"""

import logging
from datetime import datetime

from funding_tracker.exchanges.dto import ContractInfo, FundingPoint
from funding_tracker.infrastructure import http_client

logger = logging.getLogger(__name__)

EXCHANGE_ID = "hyperliquid"
API_ENDPOINT = "https://api.hyperliquid.xyz/info"


async def get_contracts() -> list[ContractInfo]:
    logger.debug(f"Fetching contracts from {EXCHANGE_ID}")

    response = await http_client.post(
        API_ENDPOINT,
        json={"type": "meta"},
        headers={"Content-Type": "application/json"},
    )

    # Response is a dict with "universe" key
    assert isinstance(response, dict)

    contracts = []
    for listing in response["universe"]:
        asset_name = listing["name"]
        contracts.append(
            ContractInfo(
                asset_name=asset_name,
                quote="USD",
                funding_interval=1,  # hourly funding
                section_name=EXCHANGE_ID,
            )
        )

    logger.debug(f"Fetched {len(contracts)} contracts from {EXCHANGE_ID}")
    return contracts


async def fetch_history(symbol: str, after_timestamp: datetime | None) -> list[FundingPoint]:
    # HyperLiquid uses milliseconds
    start_time_ms = int(after_timestamp.timestamp() * 1000) if after_timestamp else 0
    end_time_ms = int(datetime.now().timestamp() * 1000)

    logger.debug(
        f"Fetching history for {EXCHANGE_ID}/{symbol} from {after_timestamp or 'beginning'} to now"
    )

    response = await http_client.post(
        API_ENDPOINT,
        json={
            "type": "fundingHistory",
            "coin": symbol,
            "startTime": start_time_ms,
            "endTime": end_time_ms,
        },
        headers={"Content-Type": "application/json"},
    )

    # Response is a list of funding history records
    points = []
    if response:
        assert isinstance(response, list)
        for raw_record in response:
            rate = float(raw_record["fundingRate"])
            timestamp = datetime.fromtimestamp(raw_record["time"] / 1000.0)
            points.append(FundingPoint(rate=rate, timestamp=timestamp))

    logger.debug(f"Fetched {len(points)} funding points for {EXCHANGE_ID}/{symbol}")
    return points


async def fetch_live_batch() -> dict[str, FundingPoint]:
    logger.debug(f"Fetching live rates batch from {EXCHANGE_ID}")

    response = await http_client.post(
        API_ENDPOINT,
        json={"type": "metaAndAssetCtxs"},
        headers={"Content-Type": "application/json"},
    )

    # Response: [meta, contexts] - parallel arrays
    assert isinstance(response, list)
    meta_data = response[0]["universe"]
    asset_contexts = response[1]

    asset_names = {i: asset["name"] for i, asset in enumerate(meta_data)}

    now = datetime.now()
    rates = {}
    for idx, ctx in enumerate(asset_contexts):
        if "funding" in ctx:
            asset_name = asset_names[idx]
            rates[asset_name] = FundingPoint(
                rate=float(ctx["funding"]),
                timestamp=now,
            )

    logger.debug(f"Fetched {len(rates)} live rates from {EXCHANGE_ID}")
    return rates
