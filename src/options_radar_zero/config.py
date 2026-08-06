"""Configuration module for the Dash app."""
import os
from dataclasses import dataclass, field
from typing import Any

DEFAULT_X_FIELDS: list[str] = ['processDateTime', 'strikePrice', 'distance']
DEFAULT_Y_FIELDS: list[str] = ['volume', 'totalVolume', 'gex', 'mark']


@dataclass(frozen=True)
class AppConfig:
    """Immutable configuration for the application."""
    # Paths
    DATA_DIR: str = './output'
    STATIC_DIR: str = 'static'

    # Polling intervals
    DEFAULT_INTERVAL_SECONDS: int = 60

    # File watcher interval for incremental parquet updates (milliseconds)
    FILE_WATCHER_INTERVAL_MS: int = 10000

    # Market hours (EST)
    MARKET_OPEN_TIME: str = '09:30'
    MARKET_CLOSE_TIME: str = '16:00'

    # Color scheme
    COLORS = {
        'call': 'rgb(26, 118, 255)',
        'put': 'rgb(55, 83, 109)',
        'net': 'white',
        'underlying_price': 'yellow',
        'gex_orange': 'orange',
        'spx_price': 'crimson',
    }

    # Thresholds
    MIN_VOLUME_THRESHOLD: int = 10
    LOW_VOLUME_FILTER_MIN: int = 50

    # Chart layout constants
    CHART_TEMPLATE: str = 'plotly_dark'
    CHART_HEIGHT: int = 600
    CHART_MARGIN: dict[str, int] = field(default_factory=lambda: {'l': 10, 'r': 10, 't': 10, 'b': 10})
    CHART_MODEBAR: dict[str, Any] = field(default_factory=lambda: {"displayModeBar": False})


config = AppConfig()


def get_parquet_files(max_files: int = 20) -> dict[str, str]:
    """Get parquet files from data directory.

    Parses filenames to extract the underlying symbol.  Supports both
    the poller format ``{symbol}.{YYYYMMDD}.chain.parquet`` and the legacy
    ``{symbol}.{YYYY-MM-DD}.parquet`` format.

    Args:
        max_files: Maximum number of files to return.

    Returns:
        Dict mapping symbol keys to file paths (most recent first).
    """
    import glob

    file_dict: dict[str, str] = {}
    pattern = os.path.join(config.DATA_DIR, '*.parquet')

    for filepath in glob.glob(pattern):
        filepath = filepath.replace('\\', '/')
        basename = filepath.rsplit('/', 1)[-1]  # e.g. SPY.20240802.chain.parquet
        name_without_ext = basename.replace('.parquet', '')

        # Extract the underlying symbol: everything before the first date-like segment
        # Poller format: SPY.20240802.chain → symbol = SPY
        # Legacy format: SPY.2024-01-15 → symbol = SPY
        parts = name_without_ext.split('.')
        symbol = parts[0]

        file_dict[symbol] = filepath

    # Sort and limit
    keys = sorted(file_dict.keys(), reverse=True)[:max_files]
    return {key: file_dict[key] for key in keys}
