"""Repository layer for database access using the Repository pattern (Variant 2)."""

from funding_tracker.shared.repositories.asset import AssetRepository
from funding_tracker.shared.repositories.base import Repository
from funding_tracker.shared.repositories.contract import ContractRepository
from funding_tracker.shared.repositories.historical_funding_point import (
    HistoricalFundingPointRepository,
)
from funding_tracker.shared.repositories.live_funding_point import LiveFundingPointRepository
from funding_tracker.shared.repositories.quote import QuoteRepository
from funding_tracker.shared.repositories.section import SectionRepository

__all__ = [
    # Base
    "Repository",
    # Repositories
    "AssetRepository",
    "SectionRepository",
    "QuoteRepository",
    "ContractRepository",
    "HistoricalFundingPointRepository",
    "LiveFundingPointRepository",
]
