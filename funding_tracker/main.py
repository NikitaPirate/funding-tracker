"""Entry point for funding tracker application."""

import argparse
import os

# Force UTC timezone for entire application
os.environ["TZ"] = "UTC"  # noqa: E402

import asyncio
import logging
import sys

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from funding_tracker.bootstrap import bootstrap
from funding_tracker.exchanges import EXCHANGES

load_dotenv()

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


def _add_instance_to_logs(instance_id: int, total_instances: int) -> None:
    """Add instance identifier to all log messages."""
    if total_instances <= 1:
        return  # No need for single instance

    # Update format for all handlers
    for handler in logging.root.handlers:
        assert handler.formatter is not None
        old_format: str = handler.formatter._fmt  # type: ignore[assignment]
        # Insert instance_id after levelname
        new_format = old_format.replace(
            "%(levelname)s", f"%(levelname)s [{instance_id}/{total_instances}]"
        )
        handler.setFormatter(logging.Formatter(new_format))


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields like TZ
    )

    db_connection: str = Field(alias="DB_CONNECTION")
    debug_exchanges: str | None = Field(default=None, alias="DEBUG_EXCHANGES")
    debug_exchanges_live: str | None = Field(default=None, alias="DEBUG_EXCHANGES_LIVE")
    exchanges: str | None = Field(default=None, alias="EXCHANGES")
    instance_id: int = Field(default=0, alias="INSTANCE_ID")
    total_instances: int = Field(default=1, alias="TOTAL_INSTANCES")


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


def _configure_live_logging(exchanges_spec: str | None) -> None:
    """Configure debug logging for live collection operations."""
    if not exchanges_spec:
        return

    exchanges = [e.strip() for e in exchanges_spec.split(",") if e.strip()]
    if not exchanges:
        return

    logger.info(f"Enabling DEBUG logging for live collection: {exchanges}")

    for exchange_name in exchanges:
        live_logger = logging.getLogger(f"funding_tracker.exchanges.{exchange_name}.live")
        live_logger.setLevel(logging.DEBUG)


def _parse_exchanges_arg(exchanges_str: str | None) -> list[str] | None:
    """Parse comma-separated exchanges string into list.

    Returns None if empty/None (meaning "run all exchanges").
    Validates against available exchanges and logs warnings for unknown IDs.
    """
    if not exchanges_str:
        return None

    exchanges = [e.strip() for e in exchanges_str.split(",") if e.strip()]
    if not exchanges:
        return None

    available = set(EXCHANGES.keys())
    requested = set(exchanges)
    unknown = requested - available

    if unknown:
        logger.warning(
            f"Unknown exchange IDs requested: {sorted(unknown)}. "
            f"Available exchanges: {sorted(available)}"
        )

    valid = sorted(requested & available)
    logger.info(f"Filtered to {len(valid)} exchange(s): {valid}")

    return valid if valid else None


def _filter_exchanges_by_instance(
    exchanges: list[str], instance_id: int, total_instances: int
) -> list[str]:
    """Filter exchanges to those assigned to this instance.

    Simple round-robin: exchanges[0::3], exchanges[1::3], exchanges[2::3]
    Sorted list ensures consistent distribution.
    """
    if total_instances <= 1:
        return exchanges  # No filtering needed for single instance

    sorted_exchanges = sorted(exchanges)
    return sorted_exchanges[instance_id::total_instances]


async def run_scheduler(db_connection: str, exchanges: list[str] | None = None) -> None:
    """Bootstrap and run the funding scheduler."""
    scheduler = await bootstrap(db_connection=db_connection, exchanges=exchanges)
    scheduler.start()
    logger.info("Scheduler started, waiting for jobs...")

    # Block forever, keeping the scheduler running
    await asyncio.Event().wait()


def main() -> None:
    """Main entry point for funding tracker."""
    # Parse CLI arguments first
    parser = argparse.ArgumentParser(
        description="Funding tracker - Crypto funding rate collection and analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all exchanges (default)
  funding-tracker

  # Run specific exchanges via CLI
  funding-tracker --exchanges hyperliquid,bybit

  # Run single exchange
  funding-tracker --exchanges hyperliquid

  # Enable debug logging for specific exchanges
  funding-tracker --exchanges hyperliquid --debug-exchanges hyperliquid,bybit

Instance Scaling:
  --instance-id N      Instance identifier (default: 0)
  --total-instances N  Total number of instances (default: 1)

Examples:
  # Run all exchanges on single instance (default)
  funding-tracker

  # Run instance 1 of 3 (distributes exchanges across instances)
  funding-tracker --instance-id 1 --total-instances 3

Environment Variables:
  EXCHANGES          Comma-separated list of exchanges (overridden by CLI)
  DEBUG_EXCHANGES    Comma-separated list for debug logging (independent of execution)
  INSTANCE_ID        Instance identifier for multi-instance deployment
  TOTAL_INSTANCES    Total number of instances (default: 1)

Available exchanges:
  aster, backpack, binance_usd-m, binance_coin-m, bybit, derive, dydx,
  extended, hyperliquid, kucoin, lighter, okx, pacifica, paradex
        """,
    )

    parser.add_argument(
        "--exchanges",
        type=str,
        help="Comma-separated list of exchanges to run (default: all). "
        "Example: --exchanges hyperliquid,bybit",
    )

    parser.add_argument(
        "--debug-exchanges",
        type=str,
        help="Comma-separated list of exchanges for DEBUG logging (independent of execution). "
        "Example: --debug-exchanges hyperliquid,bybit",
    )

    parser.add_argument(
        "--debug-exchanges-live",
        type=str,
        help="Comma-separated list for live collection DEBUG (independent of general debug)",
    )

    parser.add_argument(
        "--instance-id",
        type=int,
        default=0,
        help="Instance identifier for multi-instance deployment (default: 0). "
        "Used to distribute exchanges across instances.",
    )

    parser.add_argument(
        "--total-instances",
        type=int,
        default=1,
        help="Total number of instances in deployment (default: 1). "
        "Exchanges are distributed using round-robin.",
    )

    args = parser.parse_args()

    # Load settings from environment
    try:
        settings = Settings()  # type: ignore[call-arg]
    except Exception as e:
        sys.exit(f"Configuration error: {e}")

    # CLI arguments override environment variables
    exchanges_arg = args.exchanges if args.exchanges else settings.exchanges
    debug_exchanges_arg = (
        args.debug_exchanges if args.debug_exchanges else settings.debug_exchanges
    )
    debug_exchanges_live_arg = (
        args.debug_exchanges_live if args.debug_exchanges_live else settings.debug_exchanges_live
    )
    instance_id = args.instance_id if args.instance_id != 0 else settings.instance_id
    total_instances = (
        args.total_instances if args.total_instances != 1 else settings.total_instances
    )

    # Add instance identifier to logs for multi-instance deployments
    _add_instance_to_logs(instance_id, total_instances)

    # Parse exchanges list
    exchanges = _parse_exchanges_arg(exchanges_arg)

    # Apply instance filtering if multi-instance deployment
    if exchanges is None:
        exchanges = sorted(EXCHANGES.keys())

    if total_instances > 1:
        exchanges = _filter_exchanges_by_instance(exchanges, instance_id, total_instances)
        logger.info(
            f"Instance {instance_id}/{total_instances}: "
            f"Running {len(exchanges)} exchange(s): {exchanges}"
        )
    else:
        exchanges = None if len(exchanges) == len(EXCHANGES) else exchanges

    # Configure debug logging
    _configure_debug_logging(debug_exchanges_arg)
    _configure_live_logging(debug_exchanges_live_arg)

    if exchanges:
        logger.info(f"Starting funding tracker with {len(exchanges)} exchange(s): {exchanges}")
    else:
        logger.info("Starting funding tracker with all exchanges")

    try:
        asyncio.run(run_scheduler(db_connection=settings.db_connection, exchanges=exchanges))
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
