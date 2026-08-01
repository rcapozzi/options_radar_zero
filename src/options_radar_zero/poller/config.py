"""Configuration models for the market data poller.

Supports loading a YAML config file that specifies multiple symbols
and their strike distances to poll in a single process.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Any

import pytz


@dataclass(frozen=True)
class SymbolConfig:
    """Configuration for a single symbol to poll.

    Attributes:
        symbol: The underlying symbol (e.g., SPY).
        strikes: Number of strikes to fetch around the money.
    """

    symbol: str
    strikes: int


@dataclass
class PollerConfig:
    """Full configuration for the poller.

    Attributes:
        output_dir: Directory where parquet files are written.
        symbols: List of symbols to poll.
    """

    output_dir: str
    symbols: list[SymbolConfig]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PollerConfig:
        """Build a PollerConfig from a dictionary (e.g., parsed YAML)."""
        output_dir = data.get("output_dir", ".")
        raw_symbols = data.get("symbols", [])
        symbols: list[SymbolConfig] = []
        for item in raw_symbols:
            if isinstance(item, dict):
                symbols.append(
                    SymbolConfig(
                        symbol=item["symbol"],
                        strikes=int(item.get("strikes", 40)),
                    )
                )
            else:
                symbols.append(SymbolConfig(symbol=item, strikes=40))
        return cls(output_dir=output_dir, symbols=symbols)

    @classmethod
    def from_yaml(cls, path: str) -> PollerConfig:
        """Load configuration from a YAML file."""
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required to load YAML config files. "
                "Install with: uv pip install pyyaml"
            ) from exc

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data)

    def filename_for(self, symbol: str) -> str:
        """Generate the parquet filename for a symbol on today's date."""
        ymd = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y%m%d")
        return os.path.join(self.output_dir, f"{symbol}.{ymd}.chain.parquet")

    @cached_property
    def all_symbols(self) -> list[str]:
        """List of all unique symbols."""
        return [s.symbol for s in self.symbols]
