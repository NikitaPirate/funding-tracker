"""Unit of Work pattern implementation for transaction management.

This module provides the foundational components for implementing the Unit of Work pattern
with SQLAlchemy async sessions. It handles transaction lifecycle, session management,
and provides a clean interface for repository access.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType
from typing import Any, Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class UnitOfWorkBase(ABC):
    """Abstract base class for Unit of Work pattern.

    Provides automatic transaction management through async context manager protocol.
    Concrete implementations must override __aenter__ to initialize their specific repositories.

    Usage:
        async with uow_factory() as uow:
            result = await uow.repository.get(id)
            # Automatically commits on success, rolls back on exception
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize UnitOfWork with a session factory.

        Args:
            session_factory: SQLAlchemy async sessionmaker for creating database sessions
        """
        self._session_factory: async_sessionmaker[AsyncSession] = session_factory

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Initialize session and repositories.

        Each concrete UnitOfWork implementation must override this method
        to initialize its specific repositories.

        Returns:
            Self: The UnitOfWork instance with initialized session and repositories
        """
        self._session: AsyncSession = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Handle transaction completion and cleanup.

        Automatically commits the transaction if no exception occurred,
        otherwise rolls back. Always closes the session safely.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        try:
            if exc_val:
                await self.rollback()
            else:
                await self.commit()
        finally:
            await self._close()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()

    async def merge(self, instance: Any) -> Any:  # noqa: ANN401
        """Merge a detached instance into the current session."""
        return await self._session.merge(instance)

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        await self._session.rollback()

    async def _close(self) -> None:
        """Close the session with cancellation protection.

        Uses asyncio.shield to ensure cleanup completes even if the task is cancelled,
        preventing connection leaks.
        """
        import asyncio

        await asyncio.shield(self._session.close())

    async def execute_raw(
        self, query: str, params: dict[str, Any] | tuple[Any, ...] | None = None
    ) -> object:
        """Execute raw SQL query.

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            Query execution result
        """
        return await self._session.execute(text(query), params)


def setup_db_session(
    db_connection: str,
    session_kwargs: dict[str, Any] | None = None,
    engine_kwargs: dict[str, Any] | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Create a SQLAlchemy async session factory.

    This function sets up the database engine and creates a session factory.
    It is intended to be used by application-specific UoW factory functions.

    Args:
        db_connection: Database connection string
        session_kwargs: Additional kwargs for async_sessionmaker (optional)
        engine_kwargs: Additional kwargs for create_async_engine (optional)

    Returns:
        An async_sessionmaker instance that can be used to create database sessions
    """
    session_kwargs = session_kwargs or {}
    # Force expire_on_commit=False for correct UoW work
    # This prevents lazy-loading issues after commit
    session_kwargs["expire_on_commit"] = False

    engine_kwargs = engine_kwargs or {}

    engine = create_async_engine(db_connection, **engine_kwargs)
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        **session_kwargs,
    )


def create_uow_factory[T: UnitOfWorkBase](
    uow_class: type[T],
    db_connection: str,
    session_kwargs: dict[str, Any] | None = None,
    engine_kwargs: dict[str, Any] | None = None,
) -> Callable[[], T]:
    """Create a factory function that produces UnitOfWork instances.

    This generic factory function sets up the database engine, creates a session factory,
    and returns a factory function that produces UnitOfWork instances of the specified type.

    Type safety is preserved through the use of generics, allowing each module to have
    strongly-typed UoW factories.

    Args:
        uow_class: The concrete UnitOfWork class to instantiate
        db_connection: Database connection string
        session_kwargs: Additional kwargs for async_sessionmaker (optional)
        engine_kwargs: Additional kwargs for create_async_engine (optional)

    Returns:
        A factory function that creates UnitOfWork instances of the specified type

    Example:
        uow_factory = create_uow_factory(
            UnitOfWork,
            "postgresql+asyncpg://user:pass@localhost/db",
            engine_kwargs={"pool_size": 20}
        )

        async with uow_factory() as uow:
            result = await uow.repository.get(id)
    """
    session_factory = setup_db_session(
        db_connection,
        session_kwargs=session_kwargs,
        engine_kwargs=engine_kwargs,
    )

    def _create_uow() -> T:
        return uow_class(session_factory)

    return _create_uow
