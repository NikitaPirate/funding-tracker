"""Live funding rate collector."""

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from funding_tracker.exchanges.dto import FundingPoint
from funding_tracker.shared.models.contract import Contract
from funding_tracker.shared.models.live_funding_point import LiveFundingPoint
from funding_tracker.unit_of_work import UOWFactoryType

if TYPE_CHECKING:
    from funding_tracker.exchanges.protocol import ExchangeAdapter

logger = logging.getLogger(__name__)


async def collect_live(
    exchange_adapter: "ExchangeAdapter",
    section_name: str,
    uow_factory: UOWFactoryType,
    assemble_symbol: Callable[[str, Contract], str],
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
        try:
            all_rates = await exchange_adapter.fetch_live_batch()
            results = []
            for contract in contracts:
                symbol = assemble_symbol(contract.section_name, contract)
                rate = all_rates.get(symbol)
                if rate is None:
                    logger.warning(
                        f"No live rate returned for {contract.asset.name} "
                        f"on {section_name} (symbol: {symbol})"
                    )
                results.append((contract, rate))
        except Exception as e:
            logger.error(
                f"Failed to fetch batch live rates for {section_name}: {e}",
                exc_info=True,
            )
            results = [(contract, None) for contract in contracts]
    else:
        logger.debug(f"Using individual API calls for {section_name}")

        async def fetch_rate_for_contract(
            contract: Contract,
        ) -> tuple[Contract, FundingPoint | None]:
            async with semaphore:
                try:
                    symbol = assemble_symbol(contract.section_name, contract)
                    rate = await exchange_adapter.fetch_live(symbol)
                    return (contract, rate)
                except Exception as e:
                    logger.error(
                        f"Failed to fetch live rate for {contract.asset.name} "
                        f"on {section_name}: {e}",
                        exc_info=True,
                    )
                    return (contract, None)

        tasks = [fetch_rate_for_contract(contract) for contract in contracts]
        results = await asyncio.gather(*tasks)

    live_records = []
    for contract, rate in results:
        if rate is not None:
            live_records.append(
                LiveFundingPoint(
                    contract_id=contract.id,
                    timestamp=rate.timestamp,
                    funding_rate=rate.rate,
                )
            )

    if not live_records:
        logger.warning(f"No live rates collected for {section_name}")
        return

    async with uow_factory() as uow:
        await uow.live_funding_records.bulk_insert_ignore(live_records)
        await uow.commit()

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
