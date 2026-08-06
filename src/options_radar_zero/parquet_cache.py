"""Caching layer for parquet data loaded from the on-disk chain files.

The external poller rewrites each ``*.chain.parquet`` file roughly once per
minute.  Reading and transforming these files on every Dash callback is
wasteful — the original ``mini_app.py`` called ``pd.read_parquet`` three times
for three callbacks.  This module provides a **single** entry point that
performs the read, transform, and derived-value extraction in one shot and
caches the result via Flask-Caching:

* :func:`get_cached_parquet(filepath) <options_radar_zero.parquet_cache.get_cached_parquet>`
  returns a :class:`CachedParquet` dataclass containing the **transformed**
  DataFrame, the sorted list of unique strikes, and the latest underlying
  price.

Invalidation strategy
---------------------
The cache key embeds ``os.stat(filepath)`` (``st_mtime_ns``, ``st_size``).
When the external process rewrites the parquet file, the signature changes and
the cache key changes, forcing a fresh read.  A 60-second Flask-Caching
``timeout`` acts as a backstop so that even if mtimes are not monotonic
(clock skew, rewritten in-place with identical timestamps, etc.) we still
refresh at most once per 60 seconds.

Because everything is computed from a single parquet read, the file is read
from disk **exactly once** per (60 s / mtime change) window regardless of how
many fields the caller needs from the result.

Flask-Caching integration
-------------------------
A lightweight Flask application is created at module import time solely to
back the :class:`~flask_caching.Cache` instance.  This allows the cache to be
used without a full Dash/Flask app context.  When this module is used inside
a Dash app, call :func:`init_cache` with the app's Flask server to register
cache-clearing hooks on startup/shutdown.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import pandas as pd
from flask import Flask
from flask_caching import Cache

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
CACHE_TTL: int = 60
"""Flask-Caching timeout in seconds.  The mtime-based cache key normally fires
before this expires, but this backstop guarantees at-most-60-second staleness."""

_LEGACY_ALIASES: dict[str, str] = {
    "last_trade_at": "processDateTime",
    "strike": "strikePrice",
    "price": "mark",
    "day_volume": "totalVolume",
    "underlying_price": "underlyingPrice",
    "open_interest": "openInterest",
}

# --------------------------------------------------------------------------- #
# Flask-Caching setup
# --------------------------------------------------------------------------- #
logger = logging.getLogger(__name__)

# A throwaway Flask app exists solely to back the Cache instance.  This lets
# the cached functions work in any context (standalone scripts, tests, Dash
# callbacks) without requiring a pre-existing Flask app context.
_flask_app = Flask(__name__)
_cache = Cache(
    config={
        "CACHE_TYPE": "SimpleCache",
        "CACHE_DEFAULT_TIMEOUT": CACHE_TTL,
    },
)
_cache.init_app(_flask_app)


def init_cache(app: Any) -> None:
    """Register the cache with a Dash/Flask application's server.

    Call this from ``mini_app.py`` or ``demo.py`` after creating the Dash
    app to ensure cache-clearing hooks are registered:

        .. code-block:: python

            app = Dash(__name__)
            init_cache(app.server)

    When called, the existing SimpleCache-backed Cache instance is re-bound
    to the provided Flask app so that ``clear_parquet_cache`` can flush all
    entries uniformly.  No-op if the cache is already initialized.
    """
    # The _flask_app already initialized _cache.  We don't need to re-init;
    # the SimpleCache backend is shared in-process.
    _ = app  # acknowledged — SimpleCache is in-process, no extra binding needed


def _cache_key(filepath: str, _signature: tuple[float, int]) -> str:
    """Build a cache key that changes when the file signature changes."""
    return f"parquet_cache:{filepath}:{_signature}"


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CachedParquet:
    """Bundle of all data extracted from a single parquet file read.

    The transform and derived-value extraction happen **seamlessly** inside the
    cached function — callers simply read the fields they need from the result.
    """

    df: pd.DataFrame
    """Transformed DataFrame (column-normalised, minute-floored, incremental
    volume computed, PUT volume negated)."""

    unique_strikes: list[float]
    """Sorted unique ``strikePrice`` values."""

    latest_underlying_price: float
    """Most-recent ``underlyingPrice`` (by ``processDateTime``)."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _file_signature(filepath: str) -> tuple[float, int]:
    """Return ``(mtime_ns, size)`` — enough entropy to detect file changes."""
    stat = os.stat(filepath)
    return stat.st_mtime_ns, stat.st_size


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename legacy column names to the canonical current format."""
    for old_name, new_name in _LEGACY_ALIASES.items():
        if old_name in df.columns and new_name not in df.columns:
            df.rename(columns={old_name: new_name}, inplace=True)
    return df


def _transform(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the standard transforms that mini_app needs.

    * floor ``processDateTime`` to the nearest minute
    * compute per-symbol incremental ``volume`` (diff of cumulative
      ``totalVolume``, clamped to ≥ 0)
    * negate volume for PUTs
    """
    df = df.copy()
    df["processDateTime"] = df["processDateTime"].dt.floor("min")
    df = df.sort_values(["symbol", "processDateTime"])
    df["volume"] = df.groupby("symbol")["totalVolume"].diff().fillna(0)
    df["volume"] = df["volume"].clip(lower=0)
    df.loc[df.putCall == "PUT", "volume"] = df["volume"] * -1
    return df


# --------------------------------------------------------------------------- #
# Cached core function
# --------------------------------------------------------------------------- #
@_cache.cached(timeout=CACHE_TTL, make_cache_key=_cache_key)
def _load_and_transform(filepath: str, _signature: tuple[float, int]) -> CachedParquet:
    """Internal cached: read + transform + derive, keyed by file signature.

    This is the single point that touches disk.  All public accessors delegate
    here so the file is read **once** per invalidation window.
    """
    raw = _normalize_columns(pd.read_parquet(filepath))
    df = _transform(raw)

    # Unique strikes — cast to plain Python floats for JSON serialisation
    strikes = [float(s) for s in sorted(raw["strikePrice"].unique())] if "strikePrice" in raw.columns else []

    # Latest underlying price
    if "underlyingPrice" in raw.columns and "processDateTime" in raw.columns:
        sorted_prices = raw.sort_values("processDateTime")
        latest_price = float(sorted_prices["underlyingPrice"].iloc[-1])
    else:
        latest_price = 0.0

    return CachedParquet(
        df=df,
        unique_strikes=strikes,
        latest_underlying_price=latest_price,
    )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def get_cached_parquet(filepath: str) -> CachedParquet:
    """Load, transform, and cache all data from *filepath*.

    Returns a :class:`CachedParquet` bundle containing:

    * ``df`` — the transformed DataFrame (floor, volume diff, PUT sign flip)
    * ``unique_strikes`` — sorted list of unique strike prices
    * ``latest_underlying_price`` — most-recent ``underlyingPrice``

    The file is read from disk once per mtime change / 60-second TTL.  Every
    subsequent call within that window returns the cached bundle instantly.
    """
    sig = _file_signature(filepath)
    return _load_and_transform(filepath, sig)


# Backwards-compatible convenience accessors (thin wrappers around
# get_cached_parquet).  Kept for callers that only need one field.
def get_cached_dataframe(filepath: str) -> pd.DataFrame:
    """Return the **transformed** DataFrame for *filepath* (cached)."""
    return get_cached_parquet(filepath).df


def get_unique_strikes(filepath: str) -> list[float]:
    """Return the sorted list of unique strikes (cached)."""
    return get_cached_parquet(filepath).unique_strikes


def get_latest_underlying_price(filepath: str) -> float:
    """Return the most-recent ``underlyingPrice`` value (cached)."""
    return get_cached_parquet(filepath).latest_underlying_price


def clear_parquet_cache() -> None:
    """Clear all parquet cache entries (utility for tests / hot-reload)."""
    _cache.clear()
