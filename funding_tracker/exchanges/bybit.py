"""Bybit exchange adapter.

Bybit has both USDT and USDC perpetuals. API limit is 200 records per request.
Minimal funding interval is 1 hour.
_FETCH_STEP = 198 hours (200 - 2 safety buffer).
"""

import logging
from datetime import datetime
from typing import Any

from funding_tracker.exchanges.base import BaseExchange
from funding_tracker.exchanges.dto import ContractInfo, FundingPoint
from funding_tracker.infrastructure import http_client
from funding_tracker.shared.models.contract import Contract

logger = logging.getLogger(__name__)


class BybitExchange(BaseExchange):
    """Bybit exchange adapter."""

    EXCHANGE_ID = "bybit"
    API_ENDPOINT = "https://api.bybit.com"

    # 200 records max, 1-hour min interval -> 198 hours (200 - 2 safety buffer)
    _FETCH_STEP = 198

    _SUFFIXES = {"USDT": "USDT", "USDC": "PERP"}

    def _format_symbol(self, contract: Contract) -> str:
        suffix = self._SUFFIXES.get(contract.quote_name, contract.quote_name)
        return f"{contract.asset.name}{suffix}"

    async def get_contracts(self) -> list[ContractInfo]:
        logger.debug(f"Fetching contracts from {self.EXCHANGE_ID}")

        all_contracts = []
        cursor = None

        while True:
            params = {"category": "linear"}
            if cursor:
                params["cursor"] = cursor

            response: Any = await http_client.get(
                f"{self.API_ENDPOINT}/v5/market/instruments-info", params=params
            )

            all_contracts.extend(response["result"]["list"])

            cursor = response["result"].get("nextPageCursor")
            if not cursor:
                break

        contracts = []
        for contract in all_contracts:
            if contract["contractType"] == "LinearPerpetual":
                contracts.append(
                    ContractInfo(
                        asset_name=contract["baseCoin"],
                        quote=contract["quoteCoin"],
                        funding_interval=int(contract["fundingInterval"] / 60),
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

        response: Any = await http_client.get(
            f"{self.API_ENDPOINT}/v5/market/funding/history",
            params={
                "symbol": symbol,
                "category": "linear",
                "startTime": start_ms,
                "endTime": end_ms,
            },
        )

        points = []
        raw_records = response.get("result", {}).get("list", [])
        if raw_records:
            for raw_record in raw_records:
                rate = float(raw_record["fundingRate"])
                timestamp = datetime.fromtimestamp(
                    int(raw_record["fundingRateTimestamp"]) / 1000.0
                )
                points.append(FundingPoint(rate=rate, timestamp=timestamp))

        logger.debug(f"Fetched {len(points)} funding points for {self.EXCHANGE_ID}/{symbol}")
        return points

    async def _fetch_live_single(self, contract: Contract) -> FundingPoint:
        symbol = self._format_symbol(contract)

        self.logger_live.debug(f"Fetching live rate for {symbol}")

        response: Any = await http_client.get(
            f"{self.API_ENDPOINT}/v5/market/tickers",
            params={"symbol": symbol, "category": "linear"},
        )

        data = response.get("result", {}).get("list", [])
        if not data:
            raise ValueError(f"No funding rate data for {symbol}")

        record = data[0]
        now = datetime.now()
        rate = float(record["fundingRate"])
        return FundingPoint(rate=rate, timestamp=now)

    async def fetch_live(self, contracts: list[Contract]) -> dict[Contract, FundingPoint]:
        from funding_tracker.exchanges.utils import fetch_live_parallel

        return await fetch_live_parallel(self, contracts)
