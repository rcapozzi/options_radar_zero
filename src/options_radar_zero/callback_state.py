"""Callback state management for the Dash application.

Provides a ChartState dataclass for serializing/deserializing chart state
between callbacks, replacing the ad-hoc dict-based 'cookie' pattern.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChartState:
    """Serializable state for the pez dispenser chart.

    Attributes:
        names: List of trace names currently in the chart.
        max_dt: Maximum processDateTime in the data.
        strikes: Tuple of (min_strike, max_strike) for the strike slider.
        yaxis: Y-axis field name.
        xaxis: X-axis field name.
        symbol: Currently selected symbol.
    """
    names: list[str] = field(default_factory=list)
    max_dt: Any | None = None  # pd.Timestamp or datetime
    strikes: tuple[float, float] = (0.0, 0.0)
    yaxis: str = 'volume'
    xaxis: str = 'processDateTime'
    symbol: str = ''

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict suitable for dcc.Store."""
        return {
            'names': self.names,
            'max_dt': self.max_dt,
            'strikes': list(self.strikes),
            'yaxis': self.yaxis,
            'xaxis': self.xaxis,
            'symbol': self.symbol,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> ChartState:
        """Deserialize from a dict (as stored in dcc.Store)."""
        if d is None:
            return cls()
        return cls(
            names=d.get('names', []),
            max_dt=d.get('max_dt'),
            strikes=tuple(d.get('strikes', [0.0, 0.0])),
            yaxis=d.get('yaxis', 'volume'),
            xaxis=d.get('xaxis', 'processDateTime'),
            symbol=d.get('symbol', ''),
        )


def encode_state(state: ChartState) -> dict[str, Any]:
    """Encode a ChartState into a dict for dcc.Store."""
    return state.to_dict()


def decode_state(d: dict[str, Any] | None) -> ChartState:
    """Decode a dict from dcc.Store into a ChartState."""
    return ChartState.from_dict(d)
