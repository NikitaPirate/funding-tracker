"""Historical funding data fetcher."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from funding_tracker.shared.models.contract import Contract
from funding_tracker.shared.models.historical_funding_point import HistoricalFundingPoint
from funding_tracker.unit_of_work import UOWFactoryType

if TYPE_CHECKING:
    from funding_tracker.exchanges.protocol import ExchangeAdapter

logger = logging.getLogger(__name__)


async def sync_contract(
    exchange_adapter: "ExchangeAdapter",
    contract: Contract,
    uow_factory: UOWFactoryType,
    assemble_symbol: Callable[[str, Contract], str],
) -> int:
    """Fetch backwards until no more data; marks contract as synced.

    Returns:
        Number of new points fetched (0 if skipped).
    """
    if contract.synced:
        logger.debug(
            f"Contract {contract.asset.name}/{contract.quote_name} "
            f"on {contract.section_name} already synced, skipping"
        )
        return 0

    logger.debug(
        f"Starting sync for {contract.asset.name}/{contract.quote_name} on {contract.section_name}"
    )

    symbol = assemble_symbol(contract.section_name, contract)

    async with uow_factory() as uow:
        oldest = await uow.historical_funding_records.get_oldest_for_contract(contract.id)
        before_timestamp = oldest.timestamp if oldest else None

        logger.debug(f"Fetching history for {symbol} before {before_timestamp or 'beginning'}")

        points = await exchange_adapter.fetch_history(symbol, before_timestamp)

        if not points:
            contract.synced = True
            logger.debug(f"No more history for {symbol}, marking as synced")
            await uow.commit()
            return 0

        funding_records = [
            HistoricalFundingPoint(
                contract_id=contract.id,
                timestamp=point.timestamp,
                funding_rate=point.rate,
            )
            for point in points
        ]

        await uow.historical_funding_records.bulk_insert_ignore(funding_records)

        await uow.commit()

        logger.debug(
            f"Synced {len(points)} funding points for {symbol} "
            f"(oldest: {min(p.timestamp for p in points)})"
        )

        return len(points)


async def update_contract(
    exchange_adapter: "ExchangeAdapter",
    contract: Contract,
    uow_factory: UOWFactoryType,
    assemble_symbol: Callable[[str, Contract], str],
) -> int:
    """Fetch new data after latest point; skips if interval not elapsed.

    Returns:
        Number of new points fetched (0 if skipped).
    """
    logger.debug(
        f"Checking update for {contract.asset.name}/{contract.quote_name} "
        f"on {contract.section_name}"
    )

    symbol = assemble_symbol(contract.section_name, contract)

    async with uow_factory() as uow:
        newest = await uow.historical_funding_records.get_newest_for_contract(contract.id)

        if newest is None:
            logger.warning(f"No historical data found for {symbol}, run sync first")
            return 0

        now = datetime.now()
        time_since_last = now - newest.timestamp
        required_interval = timedelta(hours=contract.funding_interval)

        if time_since_last < required_interval:
            logger.debug(
                f"Skipping update for {symbol}, only {time_since_last} "
                f"passed (need {required_interval})"
            )
            return 0

        logger.debug(f"Fetching history for {symbol} after {newest.timestamp}")

        points = await exchange_adapter.fetch_history(symbol, newest.timestamp)

        if not points:
            logger.debug(f"No new funding points for {symbol}")
            return 0

        funding_records = [
            HistoricalFundingPoint(
                contract_id=contract.id,
                timestamp=point.timestamp,
                funding_rate=point.rate,
            )
            for point in points
        ]

        await uow.historical_funding_records.bulk_insert_ignore(funding_records)

        await uow.commit()

        logger.debug(
            f"Updated {len(points)} funding points for {symbol} "
            f"(newest: {max(p.timestamp for p in points)})"
        )

        return len(points)
