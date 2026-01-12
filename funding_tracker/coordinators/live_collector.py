"""Live funding rate collector."""

import asyncio
import logging
from typing import TYPE_CHECKING

from httpx import HTTPError

from funding_tracker.shared.models.contract import Contract
from funding_tracker.shared.models.live_funding_point import LiveFundingPoint
from funding_tracker.unit_of_work import UOWFactoryType

if TYPE_CHECKING:
    from funding_tracker.exchanges.base import BaseExchange

logger = logging.getLogger(__name__)


async def collect_live(
    exchange_adapter: "BaseExchange",
    section_name: str,
    uow_factory: UOWFactoryType,
    semaphore: asyncio.Semaphore,
) -> None:
    """Collect unsettled rates; uses batch API if available, else parallel calls."""
    logger.debug(f"Starting live rate collection for {section_name}")

    # Fetch all active (not deprecated) contracts for this section
    async with uow_factory() as uow:
        contracts = await uow.contracts.get_active_by_section(section_name)

    if not contracts:
        logger.warning(f"No active contracts found for {section_name}")
        return

    logger.debug(f"Collecting live rates for {len(contracts)} contracts")

    if hasattr(exchange_adapter, "fetch_live_batch"):
        logger.debug(f"Using batch API for {section_name}")
        all_rates = await exchange_adapter.fetch_live_batch()
        live_records = []
        for contract in contracts:
            symbol = exchange_adapter._format_symbol(contract)
            rate = all_rates.get(symbol)
            if rate is None:
                logger.warning(
                    f"No live rate returned for {contract.asset.name} "
                    f"on {section_name} (symbol: {symbol})"
                )
            else:
                live_records.append(
                    LiveFundingPoint(
                        contract_id=contract.id,
                        timestamp=rate.timestamp,
                        funding_rate=rate.rate,
                    )
                )

    else:
        logger.debug(f"Using individual API calls for {section_name}")

        async def fetch_rate_for_contract(
            contract: Contract,
        ) -> LiveFundingPoint | None:
            async with semaphore:
                try:
                    rate = await exchange_adapter.fetch_live(contract)
                    return LiveFundingPoint(
                        contract_id=contract.id,
                        timestamp=rate.timestamp,
                        funding_rate=rate.rate,
                    )
                except HTTPError as e:
                    logger.warning(
                        f"Failed to fetch live rate for {contract.asset.name} "
                        f"on {section_name}: {e}"
                    )
                    return None
                except ValueError as e:
                    logger.warning(
                        f"Invalid funding rate data for {contract.asset.name} "
                        f"on {section_name}: {e}"
                    )
                    return None

        tasks = [fetch_rate_for_contract(contract) for contract in contracts]
        results = await asyncio.gather(*tasks)
        live_records = [r for r in results if r is not None]

    if not live_records:
        logger.warning(f"No live rates collected for {section_name}")
        return

    async with uow_factory() as uow:
        await uow.live_funding_records.bulk_insert_ignore(live_records)

    success_count = len(live_records)
    failure_count = len(contracts) - success_count

    # Only log at INFO level if there were failures
    if failure_count > 0:
        logger.info(
            f"Live rate collection for {section_name}: "
            f"{success_count} success, {failure_count} failed"
        )
    else:
        logger.debug(
            f"Live rate collection for {section_name}: "
            f"all {success_count} rates collected successfully"
        )
