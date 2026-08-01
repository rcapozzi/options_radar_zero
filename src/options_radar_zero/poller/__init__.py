"""Market data polling package for 0DTE option chains.

Provides a modular, testable architecture for polling TastyTrade option chain
data during NYSE market hours and persisting it to parquet files.

Modules:
    models: Data classes for strike metadata and option rows.
    log_config: Logging configuration helper.
    dataframe: DataFrame construction and persistence utilities.
    chain: Option chain selection and strike filtering.
    polling: Async polling loop.
    cli: Typer CLI entry point.
"""
from __future__ import annotations

__all__: list[str] = []
