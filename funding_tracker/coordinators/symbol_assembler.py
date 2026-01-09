"""Symbol format registry.

Registry mapping exchange_id to symbol assembly functions.
Add new exchanges to SYMBOL_FORMATS dict.
"""

import logging
from collections.abc import Callable

from funding_tracker.shared.models.contract import Contract

logger = logging.getLogger(__name__)

BYBIT_SUFFIXS = {"USDT": "USDT", "USDC": "PERP"}

SYMBOL_FORMATS: dict[str, Callable[[Contract], str]] = {
    "hyperliquid": lambda contract: contract.asset.name,
    "bybit": lambda c: f"{c.asset.name}{BYBIT_SUFFIXS[c.quote_name]}",
    # TODO: Add exchanges as migrated:
    # "binance_usdm": lambda c: f"{c.asset.name}{c.quote.name}",
    # "binance_coinm": lambda c: f"{c.asset.name}{c.quote.name}_PERP",
}


def assemble_symbol(exchange_id: str, contract: Contract) -> str:
    if exchange_id not in SYMBOL_FORMATS:
        raise KeyError(
            f"Exchange '{exchange_id}' not registered in SYMBOL_FORMATS. "
            f"Available exchanges: {list(SYMBOL_FORMATS.keys())}"
        )

    formatter = SYMBOL_FORMATS[exchange_id]
    symbol = formatter(contract)

    logger.debug(f"Assembled symbol for {exchange_id}: {contract.asset.name} -> {symbol}")
    return symbol
