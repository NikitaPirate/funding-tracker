from funding_tracker.db.repositories.base import Repository
from funding_tracker.shared.models.live_funding_point import LiveFundingPoint


class LiveFundingPointRepository(Repository[LiveFundingPoint]):
    _model = LiveFundingPoint
