"""Tests for callback_state module."""
from datetime import datetime

from options_radar_zero.callback_state import ChartState, decode_state, encode_state


class TestChartState:
    def test_default_values(self):
        """Test that ChartState has sensible defaults."""
        state = ChartState()
        assert state.names == []
        assert state.max_dt is None
        assert state.strikes == (0.0, 0.0)
        assert state.yaxis == 'volume'
        assert state.xaxis == 'processDateTime'
        assert state.symbol == ''

    def test_custom_values(self):
        """Test creating ChartState with custom values."""
        state = ChartState(
            names=['trace1', 'trace2'],
            max_dt=datetime(2024, 1, 1, 10, 0),
            strikes=(4000, 4200),
            yaxis='gex',
            xaxis='strikePrice',
            symbol='SPX.X',
        )
        assert state.names == ['trace1', 'trace2']
        assert state.strikes == (4000, 4200)
        assert state.yaxis == 'gex'
        assert state.xaxis == 'strikePrice'
        assert state.symbol == 'SPX.X'


class TestChartStateToDict:
    def test_to_dict_returns_dict(self):
        """Test that to_dict returns a dict."""
        state = ChartState(
            names=['trace1'],
            strikes=(4000, 4200),
            yaxis='gex',
            xaxis='strikePrice',
            symbol='SPX.X',
        )
        d = state.to_dict()
        assert isinstance(d, dict)
        assert d['names'] == ['trace1']
        assert d['strikes'] == [4000, 4200]
        assert d['yaxis'] == 'gex'
        assert d['xaxis'] == 'strikePrice'
        assert d['symbol'] == 'SPX.X'

    def test_to_dict_strikes_are_list(self):
        """Test that strikes are serialized as a list (JSON-compatible)."""
        state = ChartState(strikes=(4000, 4200))
        d = state.to_dict()
        assert isinstance(d['strikes'], list)


class TestChartStateFromDict:
    def test_from_dict_round_trip(self):
        """Test that from_dict/to_dict round-trips correctly."""
        original = ChartState(
            names=['trace1', 'trace2'],
            max_dt=datetime(2024, 1, 1, 10, 0),
            strikes=(4000, 4200),
            yaxis='gex',
            xaxis='strikePrice',
            symbol='SPX.X',
        )
        d = original.to_dict()
        restored = ChartState.from_dict(d)
        assert restored.names == original.names
        assert restored.strikes == original.strikes
        assert restored.yaxis == original.yaxis
        assert restored.xaxis == original.xaxis
        assert restored.symbol == original.symbol

    def test_from_dict_none(self):
        """Test that from_dict(None) returns default ChartState."""
        state = ChartState.from_dict(None)
        assert state.names == []
        assert state.max_dt is None
        assert state.strikes == (0.0, 0.0)

    def test_from_dict_empty(self):
        """Test that from_dict({}) returns default ChartState."""
        state = ChartState.from_dict({})
        assert state.names == []
        assert state.max_dt is None
        assert state.strikes == (0.0, 0.0)


class TestEncodeDecode:
    def test_encode_state(self):
        """Test encode_state returns a dict."""
        state = ChartState(names=['a', 'b'], symbol='SPX.X')
        d = encode_state(state)
        assert isinstance(d, dict)
        assert d['names'] == ['a', 'b']

    def test_decode_state(self):
        """Test decode_state returns a ChartState."""
        d = {'names': ['a'], 'symbol': 'SPX.X', 'strikes': [4000, 4200]}
        state = decode_state(d)
        assert isinstance(state, ChartState)
        assert state.names == ['a']
        assert state.symbol == 'SPX.X'
        assert state.strikes == (4000, 4200)

    def test_decode_state_none(self):
        """Test decode_state(None) returns default ChartState."""
        state = decode_state(None)
        assert isinstance(state, ChartState)
        assert state.names == []
