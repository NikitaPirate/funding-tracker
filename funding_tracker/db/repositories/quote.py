from funding_tracker.db.repositories.base import Repository
from funding_tracker.shared.models.quote import Quote


class QuoteRepository(Repository[Quote]):
    """Repository for managing quote currencies."""

    _model = Quote
