"""Tests for the poller config module."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from options_radar_zero.poller.config import PollerConfig, SymbolConfig


class TestSymbolConfig:
    def test_creation(self):
        sc = SymbolConfig(symbol="SPY", strikes=40)
        assert sc.symbol == "SPY"
        assert sc.strikes == 40

    def test_frozen(self):
        sc = SymbolConfig(symbol="SPY", strikes=40)
        with pytest.raises(FrozenInstanceError):
            sc.strikes = 50


class TestPollerConfig:
    def test_single_symbol(self):
        cfg = PollerConfig.single("SPY", 40, "/tmp")
        assert len(cfg.symbols) == 1
        assert cfg.symbols[0].symbol == "SPY"
        assert cfg.symbols[0].strikes == 40
        assert cfg.output_dir == "/tmp"

    def test_multiple_symbols(self):
        cfg = PollerConfig(
            output_dir="/tmp",
            symbols=[SymbolConfig("SPY", 40), SymbolConfig("QQQ", 30)],
        )
        assert len(cfg.symbols) == 2
        assert cfg.all_symbols == ["SPY", "QQQ"]

    def test_filename_for_default_date(self):
        cfg = PollerConfig.single("SPY", 40, "/data")
        fname = cfg.filename_for("SPY")
        assert fname.startswith("/data/SPY.")
        assert fname.endswith(".chain.parquet")

    def test_filename_for_specific_date(self):
        cfg = PollerConfig.single("SPY", 40, "/data")
        fname = cfg.filename_for("SPY", trade_date=date(2024, 1, 15))
        assert fname == "/data/SPY.20240115.chain.parquet"

    def test_from_yaml(self, tmp_path):
        yaml_content = """
output_dir: /tmp/data
symbols:
  - symbol: SPY
    strikes: 40
  - symbol: QQQ
    strikes: 30
"""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml_content)

        cfg = PollerConfig.from_yaml(str(cfg_path))
        assert cfg.output_dir == "/tmp/data"
        assert len(cfg.symbols) == 2
        assert cfg.symbols[0].symbol == "SPY"
        assert cfg.symbols[0].strikes == 40
        assert cfg.symbols[1].symbol == "QQQ"
        assert cfg.symbols[1].strikes == 30

    def test_from_dict_with_string_items(self):
        data = {"output_dir": "/tmp", "symbols": ["SPY", "QQQ"]}
        cfg = PollerConfig.from_dict(data)
        assert len(cfg.symbols) == 2
        assert cfg.symbols[0].symbol == "SPY"
        assert cfg.symbols[0].strikes == 40  # default

    def test_filename_for_weekend_date(self):
        """End-of-day catch-up uses last trade date for filename."""
        cfg = PollerConfig.single("SPY", 40, "/data")
        # Friday Jan 13 2024 (Monday was a holiday, so Friday is last trade day)
        fname_friday = cfg.filename_for("SPY", trade_date=date(2024, 1, 12))
        assert fname_friday == "/data/SPY.20240112.chain.parquet"

        # If run on Sunday, should still use Friday's date
        fname_sunday = cfg.filename_for("SPY", trade_date=date(2024, 1, 14))
        assert fname_sunday == "/data/SPY.20240114.chain.parquet"
