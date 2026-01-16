"""dYdX v4 exchange adapter.

dYdX v4 uses 1-hour funding interval. History limit is 1000 records per request.
_FETCH_STEP = 1000 hours (1000 records at 1-hour interval).
"""

import logging
from datetime import datetime

from funding_tracker.exchanges.base import BaseExchange
from funding_tracker.exchanges.dto import ContractInfo, FundingPoint
from funding_tracker.infrastructure import http_client
from funding_tracker.shared.models.contract import Contract

logger = logging.getLogger(__name__)


class DydxExchange(BaseExchange):
    """dYdX v4 exchange adapter."""

    EXCHANGE_ID = "dydx"
    API_ENDPOINT = "https://indexer.dydx.trade/v4"

    # API limit: 1000 records at 1-hour interval = 1000 hours
    _FETCH_STEP = 1000

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset.name}-USD"

    async def get_contracts(self) -> list[ContractInfo]:
        logger.debug(f"Fetching contracts from {self.EXCHANGE_ID}")

        response = await http_client.get(
            f"{self.API_ENDPOINT}/perpetualMarkets",
            headers={"Content-Type": "application/json"},
        )

        assert isinstance(response, dict)

        contracts = []
        markets = response.get("markets", {})

        for ticker, _ in markets.items():
            if "-" in ticker and ticker.endswith("-USD"):
                asset_name = ticker.removesuffix("-USD")
                contracts.append(
                    ContractInfo(
                        asset_name=asset_name,
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

        # dYdX uses ISO8601 format, not milliseconds
        end_time_iso = datetime.fromtimestamp(end_ms / 1000).isoformat()

        response = await http_client.get(
            f"{self.API_ENDPOINT}/historicalFunding/{symbol}",
            params={
                "effectiveBeforeOrAt": end_time_iso,
            },
            headers={"Content-Type": "application/json"},
        )

        assert isinstance(response, dict)

        points = []
        raw_records = response.get("historicalFunding", [])

        if raw_records:
            for raw_record in raw_records:
                rate = float(raw_record["rate"])
                timestamp = datetime.fromisoformat(raw_record["effectiveAt"])
                points.append(FundingPoint(rate=rate, timestamp=timestamp))

        logger.debug(f"Fetched {len(points)} funding points for {self.EXCHANGE_ID}/{symbol}")
        return points

    async def _fetch_all_rates(self) -> dict[str, FundingPoint]:
        self.logger_live.debug("Fetching live rates batch")

        response = await http_client.get(
            f"{self.API_ENDPOINT}/perpetualMarkets",
            headers={"Content-Type": "application/json"},
        )

        assert isinstance(response, dict)

        now = datetime.now()
        rates = {}
        markets = response.get("markets", {})

        for ticker, market in markets.items():
            if "-" in ticker and "nextFundingRate" in market:
                rates[ticker] = FundingPoint(
                    rate=float(market["nextFundingRate"]),
                    timestamp=now,
                )

        self.logger_live.debug(f"Fetched {len(rates)} live rates")
        return rates

    async def fetch_live(self, contracts: list[Contract]) -> dict[Contract, FundingPoint]:
        symbol_to_contract = {self._format_symbol(c): c for c in contracts}
        all_rates = await self._fetch_all_rates()

        return {
            symbol_to_contract[symbol]: rate
            for symbol, rate in all_rates.items()
            if symbol in symbol_to_contract
        }
