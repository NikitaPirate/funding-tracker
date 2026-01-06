"""Exchange adapters registry.

This module maintains a registry of all available exchange adapters.
Each adapter is a module implementing the ExchangeAdapter protocol.

To add a new exchange:
1. Copy exchanges/_template.py to exchanges/{exchange_name}.py
2. Fill in all TODO sections in the template
3. Import your adapter module here
4. Add to EXCHANGES registry below
5. The validate_adapter() function will automatically check your implementation

Example:
    from funding_tracker.exchanges import hyperliquid, binance

    EXCHANGES = {
        "hyperliquid": hyperliquid,
        "binance": binance,
    }
"""

import logging
from types import ModuleType

from funding_tracker.exchanges import hyperliquid
from funding_tracker.exchanges.protocol import ExchangeAdapter

logger = logging.getLogger(__name__)


def validate_adapter(module: ModuleType, name: str) -> None:
    """Validate that a module implements the ExchangeAdapter protocol.

    Performs runtime checks to ensure the adapter has all required attributes
    and methods. This provides fail-fast error detection during application startup
    rather than discovering missing methods at runtime.

    Args:
        module: The adapter module to validate
        name: Exchange name for error messages

    Raises:
        TypeError: If module is missing required attributes or methods,
                  or if it doesn't implement at least one live rate method

    Checks:
        - EXCHANGE_ID attribute exists and is a string
        - get_contracts() method exists
        - fetch_history() method exists
        - At least one of: fetch_live_batch() or fetch_live() exists
    """
    # Check required constant
    if not hasattr(module, "EXCHANGE_ID"):
        raise TypeError(f"{name}: missing required attribute EXCHANGE_ID")

    if not isinstance(module.EXCHANGE_ID, str):
        raise TypeError(f"{name}: EXCHANGE_ID must be str, got {type(module.EXCHANGE_ID)}")

    # Check required methods
    required_methods = ["get_contracts", "fetch_history_before", "fetch_history_after"]
    for method_name in required_methods:
        if not hasattr(module, method_name):
            raise TypeError(f"{name}: missing required method {method_name}()")

    # Check live rate methods - at least one required
    has_batch = hasattr(module, "fetch_live_batch")
    has_individual = hasattr(module, "fetch_live")

    if not has_batch and not has_individual:
        raise TypeError(
            f"{name}: must implement at least one of: fetch_live_batch() or fetch_live()"
        )

    # Log which live rate method is available
    if has_batch:
        logger.info(f"✓ {name}: validated (uses batch API - optimal)")
    else:
        logger.info(f"✓ {name}: validated (uses individual API - fallback)")


# Validate and register adapters
def _build_registry() -> dict[str, ExchangeAdapter]:
    """Build EXCHANGES registry with validation.

    Returns:
        Dict mapping exchange_id to validated adapter module

    Raises:
        TypeError: If any adapter fails validation
    """
    adapters = {
        "hyperliquid": hyperliquid,
        # TODO: Add your new adapters here
        # "binance": binance,
        # "bybit": bybit,
    }

    registry = {}
    for name, module in adapters.items():
        validate_adapter(module, name)
        registry[name] = module

    logger.info(f"Exchange adapter registry initialized with {len(registry)} exchanges")
    return registry


# Registry mapping exchange_id to adapter module (with validation)
EXCHANGES: dict[str, ExchangeAdapter] = _build_registry()

__all__ = ["EXCHANGES", "ExchangeAdapter", "hyperliquid"]
