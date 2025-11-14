"""Entry point for funding tracker application."""

import os

# Force UTC timezone for entire application
os.environ["TZ"] = "UTC"  # noqa: E402

import asyncio
import logging
import sys

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

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields like TZ
    )

    db_connection: str


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
        settings = Settings()
    except Exception as e:
        sys.exit(f"Configuration error: {e}")

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
