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
    DATA_DIR: str = '../tda-tbd/wip'
    STATIC_DIR: str = 'static'

    # Polling intervals
    DEFAULT_INTERVAL_SECONDS: int = 60

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

    Args:
        max_files: Maximum number of files to return.

    Returns:
        Dict mapping date keys to file paths.
    """
    import glob
    import re

    file_dict = {}
    pattern = os.path.join(config.DATA_DIR, '*.parquet')

    for filename in glob.glob(pattern):
        # Skip chain files
        if 'chain' in filename:
            continue
        filename = filename.replace('\\', '/')
        match = re.search(r"([^/]+)\.parquet$", filename)
        if match:
            key = match.group(1)
            file_dict[key] = filename

    # Sort and limit
    keys = sorted(file_dict.keys(), reverse=True)[:max_files]
    return {key: file_dict[key] for key in keys}
