"""Data loader module — manages OptionQuotes instances and provides injectable access.

Replaces the ``app.OptionQuotes`` global dict pattern with a proper class
that can be injected into callbacks and routes for testability.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from options_radar_zero.config import get_parquet_files
from options_radar_zero.utils import OptionQuotes


class DataLoader:
    """Manages loading and caching of OptionQuotes data.

    This class encapsulates the file discovery and OptionQuotes instantiation
    that was previously done inline in app.py / app_refactored.py.
    """

    def __init__(
        self,
        file_finder: Callable[[], dict[str, str]] | None = None,
    ) -> None:
        """Initialize the DataLoader.

        Args:
            file_finder: Optional callable that returns a dict of {symbol: filepath}.
                         Defaults to ``config.get_parquet_files``.
        """
        self._file_finder: Callable[[], dict[str, str]] = file_finder or get_parquet_files
        self._option_quotes: dict[str, OptionQuotes] = {}
        self._symbols: list[str] = []
        self._loaded: bool = False

    def load(self) -> bool:
        """Discover and load all available option chain files.

        Returns:
            True if data was loaded successfully, False otherwise.
        """
        symbols: list[str] = ['SPX.X']
        try:
            files = self._file_finder()
            for k, v in files.items():
                self._option_quotes[k] = OptionQuotes(symbol=k, filename=v)
            symbols.extend(sorted(files.keys(), reverse=True))
            self._symbols = sorted(self._option_quotes.keys(), reverse=True)
            if not self._symbols:
                self._loaded = False
                return False
            self._option_quotes[self._symbols[0]].reload()
            self._loaded = True
            return True
        except Exception as e:
            print(f"Error loading data: {e}")
            self._loaded = False
            return False

    @property
    def is_loaded(self) -> bool:
        """Whether data has been successfully loaded."""
        return self._loaded

    @property
    def symbols(self) -> list[str]:
        """List of available symbols."""
        return self._symbols

    def get(self, symbol: str) -> OptionQuotes:
        """Get the OptionQuotes instance for a given symbol.

        Args:
            symbol: The symbol to look up.

        Returns:
            The OptionQuotes instance for the symbol.

        Raises:
            KeyError: If the symbol is not loaded.
        """
        return self._option_quotes[symbol]

    def reload(self, symbol: str) -> Any:
        """Reload data for a given symbol.

        Args:
            symbol: The symbol to reload.

        Returns:
            The reloaded DataFrame.
        """
        return self._option_quotes[symbol].reload()

    def all_symbols(self) -> list[str]:
        """Return all available symbols."""
        return self._symbols
