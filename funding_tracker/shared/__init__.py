"""Shared foundation layer for funding history tracking.

This package provides the data models, repository layer, and Unit of Work pattern
following best practices with a flat structure and utility functions.
"""

from funding_tracker.shared import models, repositories
from funding_tracker.shared.unit_of_work import (
    UnitOfWorkBase,
    create_uow_factory,
    setup_db_session,
)

__all__ = [
    "models",
    "repositories",
    "UnitOfWorkBase",
    "setup_db_session",
    "create_uow_factory",
]
