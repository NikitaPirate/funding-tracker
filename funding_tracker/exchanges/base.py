"""Base exchange adapter using ABC."""

from abc import ABC, abstractmethod
from datetime import datetime

from funding_tracker.exchanges.dto import ContractInfo, FundingPoint
from funding_tracker.shared.models.contract import Contract


class BaseExchange(ABC):
    """Base class for exchange adapters.

    Subclasses must implement all abstract methods.
    """

    EXCHANGE_ID: str
    _FETCH_STEP: int

    """Fetch step size in hours (or records if exchange limits by records, not time).

    Calculated using MINIMUM funding interval to avoid exceeding API limits.
    Document per-exchange reasoning in class docstring.
    """

    def __init_subclass__(cls) -> None:
        """Validate subclass implements required methods."""
        super().__init_subclass__()

        # Check EXCHANGE_ID is defined
        if not hasattr(cls, "EXCHANGE_ID"):
            raise NotImplementedError(f"{cls.__name__}: missing EXCHANGE_ID class attribute")

        # Check at least one live method is implemented (not from BaseExchange)
        has_batch = "fetch_live_batch" in cls.__dict__
        has_individual = "fetch_live" in cls.__dict__

        if not has_batch and not has_individual:
            raise NotImplementedError(
                f"{cls.__name__}: must implement at least one of: "
                "fetch_live_batch() or fetch_live()"
            )

    @abstractmethod
    def _format_symbol(self, contract: Contract) -> str:
        """Format exchange-specific symbol from Contract."""
        ...

    @abstractmethod
    async def get_contracts(self) -> list[ContractInfo]:
        """Fetch all perpetual contracts from exchange."""
        ...

    @abstractmethod
    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        """Fetch funding history for contract within time window.

        Returns points in chronological order.
        May contain duplicates - caller handles deduplication.
        """
        ...

    async def fetch_history_before(
        self, contract: Contract, before_timestamp: datetime | None
    ) -> list[FundingPoint]:
        """Fetch funding points before timestamp (backward sync).

        Default implementation works for most exchanges using _fetch_history().
        Override if exchange has different pagination/fetching/offset logic.
        """
        end_ms = int(
            (before_timestamp.timestamp() if before_timestamp else datetime.now().timestamp())
            * 1000
        )
        start_ms = end_ms - (self._FETCH_STEP * 3600 * 1000)
        return await self._fetch_history(contract, start_ms, end_ms)

    async def fetch_history_after(
        self, contract: Contract, after_timestamp: datetime
    ) -> list[FundingPoint]:
        """Fetch funding points after timestamp (forward sync).

        Default implementation works for most exchanges using _fetch_history().
        Override if exchange has different pagination/fetching/offset logic.
        """
        start_ms = int(after_timestamp.timestamp() * 1000)
        end_ms = int(datetime.now().timestamp() * 1000)
        return await self._fetch_history(contract, start_ms, end_ms)

    async def fetch_live_batch(self) -> dict[str, FundingPoint]:
        """[PREFERRED] Get all unsettled rates in one API call."""
        raise NotImplementedError(
            f"{self.EXCHANGE_ID}: fetch_live_batch() not implemented. "
            "Implement fetch_live_batch() or fetch_live()."
        )

    async def fetch_live(self, contract: Contract) -> FundingPoint:
        """[FALLBACK] Get unsettled rate for single contract."""
        raise NotImplementedError(
            f"{self.EXCHANGE_ID}: fetch_live() not implemented. "
            "Implement fetch_live() or fetch_live_batch()."
        )
