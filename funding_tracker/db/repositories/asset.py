from funding_tracker.db.repositories.base import Repository
from funding_tracker.shared.models.asset import Asset


class AssetRepository(Repository[Asset]):
    _model = Asset
