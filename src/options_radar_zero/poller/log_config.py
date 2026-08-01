"""Logging configuration for the market data poller."""

from __future__ import annotations

import logging
import sys


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return a logger for the poller.

    Args:
        verbose: If True, sets logging level to DEBUG for detailed logs
                 in the file. Otherwise, sets to INFO.

    Returns:
        The configured logger instance.
    """
    log = logging.getLogger("options_radar_zero.poller")
    log.setLevel(logging.DEBUG if verbose else logging.INFO)

    if not log.handlers:
        file_handler = logging.FileHandler("poller.log")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        file_handler.setFormatter(file_formatter)
        log.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        log.addHandler(console_handler)

    return log
