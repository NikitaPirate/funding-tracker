"""Extended exchange adapter.

Extended (Starknet) uses 1-hour funding interval. API limit is ~4326 records per request.
Records are returned hourly (1 record/hour).
_FETCH_STEP = 2160 hours (90 days with 24 records/day = 2160, safely under 4326 limit).

**API Characteristics:**
- Envelope response: {"status": "OK", "data": [...]}
- Symbol format: BTC-USD, ETH-USD
- Batch API available for live rates (all markets in one request)

**Fetching Strategy:**
- fetch_history_before: Standard time-based batching (2160 hours = 90 days)
- fetch_history_after: Uses default BaseExchange implementation
- fetch_live: Batch API (all markets in one request, like Backpack)
"""

import logging
from datetime import datetime

from funding_tracker.exchanges.base import BaseExchange
from funding_tracker.exchanges.dto import ContractInfo, FundingPoint
from funding_tracker.infrastructure import http_client
from funding_tracker.shared.models.contract import Contract

logger = logging.getLogger(__name__)


class ExtendedExchange(BaseExchange):
    """Extended (Starknet) exchange adapter."""

    EXCHANGE_ID = "extended"
    API_ENDPOINT = "https://api.starknet.extended.exchange"

    # 90 days * 24 hours = 2160 hours (safely under 4326 record limit)
    _FETCH_STEP = 2160

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset.name}-{contract.quote_name}"

    async def get_contracts(self) -> list[ContractInfo]:
        logger.debug(f"Fetching contracts from {self.EXCHANGE_ID}")

        response = await http_client.get(f"{self.API_ENDPOINT}/api/v1/info/markets")

        assert isinstance(response, dict)
        if response.get("status") != "OK":
            raise RuntimeError(f"Extended API error: {response}")

        markets = response.get("data", [])

        contracts = []
        for market in markets:
            # Only active markets
            if market.get("status") != "ACTIVE":
                continue

            asset_name = market.get("assetName", "")
            quote = market.get("collateralAssetName", "")

            contracts.append(
                ContractInfo(
                    asset_name=asset_name,
                    quote=quote,
                    funding_interval=1,  # 1 hour
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

        response = await http_client.get(
            f"{self.API_ENDPOINT}/api/v1/info/{symbol}/funding",
            params={
                "startTime": start_ms,
                "endTime": end_ms,
            },
        )

        assert isinstance(response, dict)
        if response.get("status") != "OK":
            raise RuntimeError(f"Extended API error: {response}")

        raw_records = response.get("data", [])

        points = []
        for record in raw_records:
            rate = float(record["f"])
            timestamp = datetime.fromtimestamp(record["T"] / 1000.0)
            points.append(FundingPoint(rate=rate, timestamp=timestamp))

        logger.debug(f"Fetched {len(points)} funding points for {self.EXCHANGE_ID}/{symbol}")
        return points

    async def _fetch_all_rates(self) -> dict[str, FundingPoint]:
        """Fetch all live rates in one batch request.

        Extended provides batch API that returns all markets at once.
        Similar to Backpack exchange pattern.
        """
        self.logger_live.debug("Fetching live rates batch")

        response = await http_client.get(f"{self.API_ENDPOINT}/api/v1/info/markets")

        assert isinstance(response, dict)
        if response.get("status") != "OK":
            raise RuntimeError(f"Extended API error: {response}")

        markets = response.get("data", [])

        now = datetime.now()
        rates = {}

        for market in markets:
            if market.get("status") != "ACTIVE":
                continue

            symbol = market.get("name", "")
            funding_rate = market.get("marketStats", {}).get("fundingRate")

            if funding_rate is not None:
                rate = float(funding_rate)
                rates[symbol] = FundingPoint(rate=rate, timestamp=now)

        self.logger_live.debug(f"Fetched {len(rates)} live rates")
        return rates

    async def fetch_live(self, contracts: list[Contract]) -> dict[Contract, FundingPoint]:
        """Fetch unsettled rates for given contracts using batch API.

        All markets fetched in one request, then mapped to contracts.
        """
        symbol_to_contract = {self._format_symbol(c): c for c in contracts}
        all_rates = await self._fetch_all_rates()

        return {
            symbol_to_contract[symbol]: rate
            for symbol, rate in all_rates.items()
            if symbol in symbol_to_contract
        }
