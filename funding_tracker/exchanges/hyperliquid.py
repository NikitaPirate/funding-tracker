"""Hyperliquid exchange adapter.

HyperLiquid uses 1-hour funding interval. API limit is 500 records per request.
_FETCH_STEP = 498 hours (500 - 2 safety buffer).
"""

import logging
from datetime import datetime

from funding_tracker.exchanges.base import BaseExchange
from funding_tracker.exchanges.dto import ContractInfo, FundingPoint
from funding_tracker.infrastructure import http_client
from funding_tracker.shared.models.contract import Contract

logger = logging.getLogger(__name__)


class HyperliquidExchange(BaseExchange):
    """Hyperliquid exchange adapter."""

    EXCHANGE_ID = "hyperliquid"
    API_ENDPOINT = "https://api.hyperliquid.xyz/info"

    # 500 records max, 1-hour interval -> 498 hours (500 - 2 safety buffer)
    _FETCH_STEP = 498

    def _format_symbol(self, contract: Contract) -> str:
        return contract.asset.name

    async def get_contracts(self) -> list[ContractInfo]:
        logger.debug(f"Fetching contracts from {self.EXCHANGE_ID}")

        response = await http_client.post(
            self.API_ENDPOINT,
            json={"type": "meta"},
            headers={"Content-Type": "application/json"},
        )

        assert isinstance(response, dict)

        contracts = []
        for listing in response["universe"]:
            contracts.append(
                ContractInfo(
                    asset_name=listing["name"],
                    quote="USD",
                    funding_interval=1,
                    section_name=self.EXCHANGE_ID,
                )
            )

        logger.debug(f"Fetched {len(contracts)} contracts from {self.EXCHANGE_ID}")
        return contracts

    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        symbol = self._format_symbol(contract)

        logger.debug(
            f"Fetching history for {self.EXCHANGE_ID}/{symbol} "
            f"from {datetime.fromtimestamp(start_ms / 1000)} "
            f"to {datetime.fromtimestamp(end_ms / 1000)}"
        )

        response = await http_client.post(
            self.API_ENDPOINT,
            json={
                "type": "fundingHistory",
                "coin": symbol,
                "startTime": start_ms,
                "endTime": end_ms,
            },
            headers={"Content-Type": "application/json"},
        )

        points = []
        if response:
            assert isinstance(response, list)
            for raw_record in response:
                rate = float(raw_record["fundingRate"])
                timestamp = datetime.fromtimestamp(raw_record["time"] / 1000.0)
                points.append(FundingPoint(rate=rate, timestamp=timestamp))

        logger.debug(f"Fetched {len(points)} funding points for {self.EXCHANGE_ID}/{symbol}")
        return points

    async def fetch_live_batch(self) -> dict[str, FundingPoint]:
        logger.debug(f"Fetching live rates batch from {self.EXCHANGE_ID}")

        response = await http_client.post(
            self.API_ENDPOINT,
            json={"type": "metaAndAssetCtxs"},
            headers={"Content-Type": "application/json"},
        )

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

        logger.debug(f"Fetched {len(rates)} live rates from {self.EXCHANGE_ID}")
        return rates
