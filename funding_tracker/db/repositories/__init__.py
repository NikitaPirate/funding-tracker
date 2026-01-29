"""Repository layer for database access using the Repository pattern (Variant 2)."""

from funding_tracker.db.repositories.asset import AssetRepository
from funding_tracker.db.repositories.base import Repository
from funding_tracker.db.repositories.contract import ContractRepository
from funding_tracker.db.repositories.historical_funding_point import (
    HistoricalFundingPointRepository,
)
from funding_tracker.db.repositories.live_funding_point import LiveFundingPointRepository
from funding_tracker.db.repositories.quote import QuoteRepository
from funding_tracker.db.repositories.section import SectionRepository

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
