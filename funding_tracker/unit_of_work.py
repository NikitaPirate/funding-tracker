"""Unit of Work implementation for funding tracker module.

Provides concrete UnitOfWork with all repositories needed for funding history tracking.
"""

from collections.abc import Callable
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from funding_tracker.shared.repositories import (
    AssetRepository,
    ContractRepository,
    HistoricalFundingPointRepository,
    LiveFundingPointRepository,
    QuoteRepository,
    SectionRepository,
)
from funding_tracker.shared.unit_of_work import UnitOfWorkBase

# Type alias for UoW factory function
UOWFactoryType = Callable[[], "UnitOfWork"]


class UnitOfWork(UnitOfWorkBase):
    """Unit of Work for funding tracker module.

    Encapsulates all repositories needed for funding history operations
    and manages transaction boundaries.

    Repositories:
        - assets: Crypto assets (BTC, ETH, etc.)
        - sections: Exchange/section data (Binance, Bybit, etc.)
        - contracts: Perpetual contracts for specific assets
        - historical_funding_records: Historical funding rate data points
        - live_funding_records: Real-time unsettled funding rate data
        - quotes: Quote currency data (USDT, USDC, etc.)

    Usage:
        async with uow_factory() as uow:
            asset = await uow.assets.get_by_symbol("BTC")
            contracts = await uow.contracts.get_by_asset_id(asset.id)
    """

    # Type hints for IDE autocomplete and static type checking
    assets: AssetRepository
    sections: SectionRepository
    contracts: ContractRepository
    historical_funding_records: HistoricalFundingPointRepository
    live_funding_records: LiveFundingPointRepository
    quotes: QuoteRepository

    async def __aenter__(self) -> Self:
        """Initialize session and all repositories.

        Returns:
            Self: UnitOfWork instance with initialized repositories
        """
        self._session: AsyncSession = self._session_factory()

        # Initialize all repositories with the session
        self.assets = AssetRepository(self._session)
        self.sections = SectionRepository(self._session)
        self.contracts = ContractRepository(self._session)
        self.historical_funding_records = HistoricalFundingPointRepository(self._session)
        self.live_funding_records = LiveFundingPointRepository(self._session)
        self.quotes = QuoteRepository(self._session)

        return self
