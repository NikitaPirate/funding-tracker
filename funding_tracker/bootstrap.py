"""Bootstrap function for setting up the funding tracker scheduler.

This module provides the main entry point for initializing and configuring
the scheduler with exchange orchestrators for funding history tracking.
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from funding_tracker.exchanges import EXCHANGES
from funding_tracker.materialized_view_refresher import MaterializedViewRefresher
from funding_tracker.orchestration import ExchangeOrchestrator
from funding_tracker.shared.unit_of_work import create_uow_factory
from funding_tracker.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


async def bootstrap(
    db_connection: str,
    exchanges: list[str] | None = None,
    concurrency_limit: int = 10,
    mv_refresher_debounce: int = 10,
) -> AsyncIOScheduler:
    """Set up scheduler with orchestrators for specified exchanges.

    Initializes all shared dependencies (UoW factory, materialized view refresher)
    and creates an orchestrator for each exchange with its own semaphore.
    Registers scheduler jobs for periodic updates and live rate collection.

    Jobs registered per exchange:
    - update(): Immediate on start + hourly at minute 0 (register contracts + sync/update history)
    - update_live(): Every minute (collect live funding rates, evenly distributed)

    Args:
        db_connection: Database connection string (PostgreSQL)
        exchanges: List of exchange identifiers (e.g., ["hyperliquid", "binance"]).
            If None, uses all registered exchanges (default: None)
        concurrency_limit: Max parallel tasks per exchange (default: 10)
        mv_refresher_debounce: Materialized view refresh debounce in seconds (default: 10)

    Returns:
        Configured AsyncIOScheduler ready to start

    Raises:
        KeyError: If exchange not registered in EXCHANGES
        DatabaseError: If database connection fails

    Example:
        # Use all registered exchanges
        scheduler = await bootstrap(
            db_connection="postgresql+asyncpg://user:pass@localhost/db"
        )

        # Or specify specific exchanges
        scheduler = await bootstrap(
            db_connection="postgresql+asyncpg://user:pass@localhost/db",
            exchanges=["hyperliquid"]
        )

        scheduler.start()
        # Keep running...
        await asyncio.Event().wait()
    """
    # Use all registered exchanges if none specified
    if exchanges is None:
        exchanges = list(EXCHANGES.keys())
        logger.info(f"No exchanges specified, using all registered: {exchanges}")
    else:
        logger.info(f"Bootstrapping funding tracker for exchanges: {exchanges}")

        # Validate all requested exchanges exist
        available = set(EXCHANGES.keys())
        requested = set(exchanges)
        unknown = requested - available

        if unknown:
            logger.warning(
                f"Unknown exchange IDs will be skipped: {sorted(unknown)}. "
                f"Available: {sorted(available)}"
            )

            # Filter to only valid exchanges
            exchanges = [e for e in exchanges if e in available]

            if not exchanges:
                logger.error("No valid exchanges remaining after filtering")
                raise KeyError(f"All requested exchanges are unknown: {sorted(unknown)}")

    # Initialize shared dependencies
    uow_factory = create_uow_factory(
        UnitOfWork,
        db_connection,
        engine_kwargs={"pool_size": 30, "max_overflow": 200},
    )
    mv_refresher = MaterializedViewRefresher(
        uow_factory,
        debounce_seconds=mv_refresher_debounce,
    )

    logger.debug(
        f"Initialized shared dependencies: "
        f"concurrency_limit={concurrency_limit} (per exchange), "
        f"mv_refresher_debounce={mv_refresher_debounce}s"
    )

    # Create scheduler with job defaults
    scheduler = AsyncIOScheduler(
        job_defaults={
            "coalesce": True,  # Skip missed runs if overlapping
            "max_instances": 1,  # Only one instance per job at a time
            "misfire_grace_time": 3600,  # Allow delayed starts within 1 hour
        }
    )

    # Calculate even distribution of live rate collection across the minute
    # Example: 3 exchanges -> 0s, 20s, 40s; 5 exchanges -> 0s, 12s, 24s, 36s, 48s
    seconds_per_exchange = 60 // len(exchanges) if exchanges else 0

    # Create orchestrator and register jobs for each exchange
    for idx, exchange_name in enumerate(exchanges):
        exchange_adapter = EXCHANGES[exchange_name]

        # Create separate semaphore for this exchange (concurrency control)
        exchange_semaphore = asyncio.Semaphore(concurrency_limit)

        # Create orchestrator with all dependencies
        orchestrator = ExchangeOrchestrator(
            exchange_adapter=exchange_adapter,
            section_name=exchange_name,
            uow_factory=uow_factory,
            semaphore=exchange_semaphore,
            mv_refresher=mv_refresher,
        )

        # Register update job: immediate on start + hourly at minute 0
        scheduler.add_job(
            orchestrator.update,
            trigger=OrTrigger(
                [
                    DateTrigger(),  # Run immediately on start
                    CronTrigger(hour="*", minute=0, second=5),  # Then hourly
                ]
            ),
            name=f"{exchange_name}_update",
        )
        logger.info(f"Registered update job for {exchange_name} (immediate + hourly)")

        # Register live rate collection: every minute, evenly distributed
        second = idx * seconds_per_exchange
        scheduler.add_job(
            orchestrator.update_live,
            trigger=CronTrigger(second=second),
            name=f"{exchange_name}_live",
        )
        logger.info(
            f"Registered live rate collection for {exchange_name} (every minute at :{second:02d})"
        )

    # Register materialized view refresher
    scheduler.add_job(
        mv_refresher.check_and_refresh_if_needed,
        trigger=CronTrigger(second="*"),
        name="materialized_views_refresher",
    )
    logger.info("Registered materialized view refresher (every second)")

    logger.info(
        f"Bootstrap complete: {len(exchanges)} exchange(s) configured, "
        f"{len(scheduler.get_jobs())} job(s) registered"
    )

    return scheduler
