#!/usr/bin/env python3
"""Exchange adapter verification script.

Usage: python scripts/verify_exchange.py hyperliquid
"""

import asyncio
import sys
from datetime import datetime
from importlib import import_module

from rich.console import Console
from rich.table import Table

from funding_tracker.exchanges import validate_adapter

console = Console()


async def verify_exchange(exchange_id: str) -> bool:
    console.print(f"\n🔍 [bold cyan]Verifying exchange adapter: {exchange_id}[/bold cyan]\n")

    try:
        adapter = import_module(f"funding_tracker.exchanges.{exchange_id}")
    except ImportError as e:
        console.print(f"[bold red]✗[/bold red] Failed to import adapter: {e}")
        return False

    # Step 1: Protocol validation
    console.print("[bold]Step 1: Protocol Validation[/bold]")
    try:
        validate_adapter(adapter, exchange_id)
        console.print(f"  [green]✓[/green] EXCHANGE_ID: {adapter.EXCHANGE_ID}")
        console.print("  [green]✓[/green] Required methods: get_contracts, fetch_history")

        has_batch = hasattr(adapter, "fetch_live_batch")
        has_single = hasattr(adapter, "fetch_live")
        if has_batch:
            console.print("  [green]✓[/green] Live method: fetch_live_batch")
        elif has_single:
            console.print("  [green]✓[/green] Live method: fetch_live")

    except Exception as e:
        console.print(f"  [bold red]✗[/bold red] Protocol validation failed: {e}")
        return False

    # Step 2: Fetch contracts
    console.print("\n[bold]Step 2: API - get_contracts()[/bold]")
    try:
        contracts = await adapter.get_contracts()
        console.print(f"  [green]✓[/green] Retrieved {len(contracts)} contracts")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Asset", style="cyan")
        table.add_column("Quote", style="yellow")
        table.add_column("Funding Interval", style="green")

        for contract in contracts[:5]:
            table.add_row(contract.asset_name, contract.quote, f"{contract.funding_interval}h")

        if len(contracts) > 5:
            table.add_row("...", "...", "...", style="dim")

        console.print(table)

    except Exception as e:
        console.print(f"  [bold red]✗[/bold red] get_contracts() failed: {e}")
        return False

    # Step 3: Fetch history for first contract
    if contracts:
        test_symbol = contracts[0].asset_name
        console.print(f"\n[bold]Step 3: API - fetch_history({test_symbol})[/bold]")
        try:
            # Fetch last 7 days of history
            seven_days_ago = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ).timestamp() - (7 * 24 * 3600)
            from datetime import datetime as dt

            after_ts = dt.fromtimestamp(seven_days_ago)

            history = await adapter.fetch_history(test_symbol, after_ts)
            console.print(f"  [green]✓[/green] Retrieved {len(history)} funding points")

            if history:
                oldest = min(point.timestamp for point in history)
                newest = max(point.timestamp for point in history)
                console.print(f"  [dim]Date range: {oldest.date()} → {newest.date()}[/dim]")

                sample = history[0]
                rate_pct = sample.rate * 100
                console.print(f"  [dim]Sample rate: {sample.rate:.6f} ({rate_pct:.4f}%)[/dim]")

        except Exception as e:
            console.print(f"  [bold red]✗[/bold red] fetch_history() failed: {e}")
            return False

    # Step 4: Fetch live rates
    console.print("\n[bold]Step 4: API - fetch_live[/bold]")
    try:
        if hasattr(adapter, "fetch_live_batch"):
            live_rates = await adapter.fetch_live_batch()
            console.print(
                f"  [green]✓[/green] fetch_live_batch() returned {len(live_rates)} rates"
            )

            if live_rates:
                sample_symbol = list(live_rates.keys())[0]
                sample_rate = live_rates[sample_symbol]
                rate_pct = sample_rate.rate * 100
                console.print(
                    f"  [dim]Sample: {sample_symbol} = {sample_rate.rate:.6f} "
                    f"({rate_pct:.4f}%)[/dim]"
                )

        elif hasattr(adapter, "fetch_live"):
            test_symbol = contracts[0].asset_name if contracts else "BTC"
            live_rate = await adapter.fetch_live(test_symbol)
            if live_rate:
                rate_pct = live_rate.rate * 100
                console.print(
                    f"  [green]✓[/green] fetch_live({test_symbol}) = {live_rate.rate:.6f} "
                    f"({rate_pct:.4f}%)"
                )
            else:
                console.print(f"  [yellow]⚠[/yellow] fetch_live({test_symbol}) returned None")

    except Exception as e:
        console.print(f"  [bold red]✗[/bold red] Live rate fetch failed: {e}")
        return False

    console.print(f"\n[bold green]✓ All checks passed for {exchange_id}[/bold green]\n")
    return True


async def main() -> int:
    if len(sys.argv) < 2:
        console.print(
            "[bold red]Usage:[/bold red] python scripts/verify_exchange.py <exchange_id>"
        )
        console.print("\nExample: python scripts/verify_exchange.py hyperliquid")
        return 1

    exchange_id = sys.argv[1]
    success = await verify_exchange(exchange_id)
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
