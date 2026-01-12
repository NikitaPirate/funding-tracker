"""Live funding rate collector."""

import logging
from typing import TYPE_CHECKING

from funding_tracker.shared.models.live_funding_point import LiveFundingPoint
from funding_tracker.unit_of_work import UOWFactoryType

if TYPE_CHECKING:
    from funding_tracker.exchanges.base import BaseExchange

logger = logging.getLogger(__name__)


async def collect_live(
    exchange_adapter: "BaseExchange",
    section_name: str,
    uow_factory: UOWFactoryType,
) -> None:
    """Collect unsettled rates for given exchange section."""
    logger.debug(f"Starting live rate collection for {section_name}")

    async with uow_factory() as uow:
        contracts = await uow.contracts.get_active_by_section(section_name)

    if not contracts:
        logger.warning(f"No active contracts found for {section_name}")
        return

    logger.debug(f"Collecting live rates for {len(contracts)} contracts")

    rates_by_contract = await exchange_adapter.fetch_live(list(contracts))

    if not rates_by_contract:
        logger.warning(f"No live rates collected for {section_name}")
        return

    live_records = [
        LiveFundingPoint(
            contract_id=contract.id,
            timestamp=rate.timestamp,
            funding_rate=rate.rate,
        )
        for contract, rate in rates_by_contract.items()
    ]

    async with uow_factory() as uow:
        await uow.live_funding_records.bulk_insert_ignore(live_records)

    success_count = len(live_records)
    failure_count = len(contracts) - success_count

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
