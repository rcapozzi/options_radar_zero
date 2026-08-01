"""Backward-compatibility shim.

The market data polling logic has been refactored into the ``options_radar_zero.poller``
package. This module re-exports the public API so that existing imports and
CLI invocations (``python -m options_radar_zero.tt_poll_market_data``) continue to work.
"""

from __future__ import annotations

from options_radar_zero.poller.cli import cli, main
from options_radar_zero.poller.dataframe import (
    create_dataframe_from_market_data,
    merge_save_df,
)

# Re-export for backward compatibility
__all__ = [
    "cli",
    "main",
    "create_dataframe_from_market_data",
    "merge_save_df",
]

if __name__ == "__main__":
    cli()
