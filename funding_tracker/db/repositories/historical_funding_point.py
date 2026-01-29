from uuid import UUID

from sqlalchemy.sql.expression import asc, desc, select

from funding_tracker.db.repositories.base import Repository
from funding_tracker.shared.models.historical_funding_point import HistoricalFundingPoint


class HistoricalFundingPointRepository(Repository[HistoricalFundingPoint]):
    _model = HistoricalFundingPoint

    async def get_oldest_for_contract(self, contract_id: UUID) -> HistoricalFundingPoint | None:
        stmt = (
            select(HistoricalFundingPoint)
            .where(HistoricalFundingPoint.contract_id == contract_id)  # type: ignore[arg-type]
            .order_by(asc(HistoricalFundingPoint.timestamp))  # type: ignore[arg-type]
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_newest_for_contract(self, contract_id: UUID) -> HistoricalFundingPoint | None:
        stmt = (
            select(HistoricalFundingPoint)
            .where(HistoricalFundingPoint.contract_id == contract_id)  # type: ignore[arg-type]
            .order_by(desc(HistoricalFundingPoint.timestamp))  # type: ignore[arg-type]
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
