"""Typer CLI entry point for the market data poller.

The poller must be configured via a YAML file (--config).  A single
process polls all configured symbols concurrently using one shared
Tastytrade session.

When the market is open, the poller enters a live polling loop per symbol
until market close.  When the market is closed, the poller performs an
end-of-day catch-up: it fetches fresh market data once for each symbol
and merges it into existing parquet files, filling any gaps from the
live polling session.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Annotated, Any

import typer
from filelock import FileLock
from filelock import Timeout as FileLockTimeout
from typer import Option

from options_radar_zero.market_hours import MarketIntervalCalculator
from options_radar_zero.poller.config import PollerConfig
from options_radar_zero.poller.log_config import setup_logging
from options_radar_zero.poller.polling import poll_symbols

logger = logging.getLogger(__name__)

cli = typer.Typer(no_args_is_help=True)


def _create_session() -> Any:
    """Load credentials from a .env file and create a Tastytrade Session.

    The Tastytrade OAuth2 refresh-token flow reads ``TT_REFRESH`` and
    ``TT_SECRET`` from the environment.  We use ``python-dotenv`` to
    optionally populate those from a project-level ``.env`` file.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:  # pragma: no cover
        pass

    from tastytrade.session import Session

    return Session()


async def _run_poller(
    config: PollerConfig,
    market_interval_calculator: MarketIntervalCalculator,
) -> None:
    """Create a session and run the polling loop for all symbols.

    Session creation reads ``TT_REFRESH`` / ``TT_SECRET`` from the environment
    (optionally loaded from ``.env``).  Both session creation and polling
    run inside the same event loop.  The same session is reused across
    all symbols.

    If the market is open, ``poll_symbols`` enters a live polling loop
    until close.  If the market is closed, it performs an end-of-day
    catch-up instead.
    """
    session = _create_session()
    from options_radar_zero.tastytrade_api import TastyTradeAPI

    api: Any = TastyTradeAPI(session)
    await poll_symbols(config, api, market_interval_calculator)


@cli.command(
    help=(
        "Polls 0DTE option chain data and saves to parquet. "
        "Requires YAML config (--config). When market is closed, "
        "performs end-of-day catch-up."
    )
)
def main(
    config_path: Annotated[
        str | None, Option("--config", "-c", help="Path to YAML config file.")
    ] = None,
    output_dir: Annotated[
        str | None, Option("--output-dir", "-o", help="Override output dir from config.")
    ] = None,
    verbose: Annotated[bool, Option("--verbose", "-v", help="Enable verbose logging.")] = False,
) -> None:
    """Main entry point for the polling application.

    Args:
        config_path: Path to YAML config file (required).
        output_dir: Override output directory from config.
        verbose: Enable verbose logging.
    """
    global logger
    logger = setup_logging(verbose)

    if config_path is None:
        logger.critical("Config file not specified. Use --config /path/to/config.yaml")
        sys.exit(1)

    config = PollerConfig.from_yaml(config_path)
    if output_dir is not None:
        config = PollerConfig(
            output_dir=output_dir,
            symbols=config.symbols,
        )

    lock_file_path = os.path.join(config.output_dir, ".poller.lock")
    lock = FileLock(lock_file_path)

    try:
        with lock:
            logger.info("Acquired lock for %s.", ", ".join(config.all_symbols))
            market_interval_calculator = MarketIntervalCalculator()

            if market_interval_calculator.is_market_open():
                logger.info("Market is open. Starting live polling.")
            else:
                logger.info("Market is closed. Will perform end-of-day catch-up.")

            asyncio.run(_run_poller(config, market_interval_calculator))
    except FileLockTimeout:
        logger.warning("Another instance of the poller is already running. Exiting.")
        sys.exit(0)
    except KeyError as e:
        logger.critical(
            "Missing required credential %s. Set TT_REFRESH and TT_SECRET "
            "environment variables, or add them to a .env file in the project root.",
            e,
        )
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Polling stopped by user.")
    except Exception as e:
        logger.critical("A critical error occurred: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
