"""Entry point for funding tracker application."""

import os

# Force UTC timezone for entire application
os.environ["TZ"] = "UTC"  # noqa: E402

import asyncio
import logging
import sys

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from funding_tracker.bootstrap import bootstrap

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

# Reduce noise from third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields like TZ
    )

    db_connection: str = Field(alias="DB_CONNECTION")
    debug_exchanges: str | None = Field(default=None, alias="DEBUG_EXCHANGES")


def _configure_debug_logging(exchanges_spec: str | None) -> None:
    if not exchanges_spec:
        return

    exchanges = [e.strip() for e in exchanges_spec.split(",") if e.strip()]
    if not exchanges:
        return

    logger.info(f"Enabling DEBUG logging for exchanges: {exchanges}")

    for exchange_name in exchanges:
        exchange_logger = logging.getLogger(f"funding_tracker.exchanges.{exchange_name}")
        exchange_logger.setLevel(logging.DEBUG)


async def run_scheduler(db_connection: str) -> None:
    """Bootstrap and run the funding scheduler."""
    scheduler = await bootstrap(db_connection=db_connection)
    scheduler.start()
    logger.info("Scheduler started, waiting for jobs...")

    # Block forever, keeping the scheduler running
    await asyncio.Event().wait()


def main() -> None:
    """Main entry point for funding tracker."""
    try:
        settings = Settings()  # type: ignore[call-arg]
    except Exception as e:
        sys.exit(f"Configuration error: {e}")

    _configure_debug_logging(settings.debug_exchanges)
    logger.info("Starting funding tracker application...")

    try:
        asyncio.run(run_scheduler(db_connection=settings.db_connection))
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
