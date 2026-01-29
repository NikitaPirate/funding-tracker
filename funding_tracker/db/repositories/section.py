from funding_tracker.db.repositories.base import Repository
from funding_tracker.shared.models.section import Section


class SectionRepository(Repository[Section]):
    """Repository for managing exchange sections."""

    _model = Section
