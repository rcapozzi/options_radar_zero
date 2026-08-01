"""Pytest configuration - adds src to Python path."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))



@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create a sample dataframe for testing."""
    dates = pd.date_range(start='2024-01-01 09:30', periods=100, freq='min')
    dates = dates.tz_localize('US/Eastern')
    data = []
    for dt in dates:
        for strike in [4000, 4050, 4100, 4150]:
            for putcall in ['CALL', 'PUT']:
                data.append({
                    'symbol': f'SPX{strike}{putcall[0]}',
                    'processDateTime': dt,
                    'strikePrice': strike,
                    'putCall': putcall,
                    'volume': np.random.randint(50, 200),
                    'totalVolume': np.random.randint(500, 2000),
                    'mark': np.random.uniform(0.5, 5.0),
                    'gamma': np.random.uniform(0.01, 0.1),
                    'underlyingPrice': 4100,
                    'markDiff': 0.01,
                    'sma5': np.random.uniform(0.5, 2.0),
                    'sma15': np.random.uniform(0.3, 1.5),
                })
    return pd.DataFrame(data)


@pytest.fixture
def raw_option_dataframe() -> pd.DataFrame:
    """Create a raw option dataframe with timezone-aware datetimes."""
    dates = pd.date_range(start='2024-01-01 09:30', periods=50, freq='min')
    dates = dates.tz_localize('US/Eastern')
    data = []
    for dt in dates:
        for strike in [4000, 4050, 4100, 4150]:
            for putcall in ['CALL', 'PUT']:
                data.append({
                    'symbol': f'SPX{strike}{putcall[0]}',
                    'processDateTime': dt,
                    'strikePrice': strike,
                    'putCall': putcall,
                    'totalVolume': np.random.randint(500, 2000),
                    'mark': np.random.uniform(0.5, 5.0),
                    'gamma': np.random.uniform(0.01, 0.1),
                    'underlyingPrice': 4100,
                    'markDiff': 0.01,
                    'sma5': np.random.uniform(0.5, 2.0),
                    'sma15': np.random.uniform(0.3, 1.5),
                    'volatility': np.random.uniform(0.1, 0.5),
                    'delta': np.random.uniform(-1, 1),
                    'theta': np.random.uniform(-1, 0),
                    'openInterest': np.random.randint(100, 1000),
                    'tradeTimeInLong': 0,
                    'quoteTimeInLong': 0,
                    'netChange': 0,
                    'rho': 0,
                    'vega': 0,
                    'bid': 0,
                    'ask': 0,
                    'highPrice': 0,
                    'lowPrice': 0,
                    'openPrice': 0,
                    'closePrice': 0,
                    'expirationDate': '2024-01-01',
                    'lastTradingDay': '2024-01-01',
                    'multiplier': 100,
                    'timeValue': 0,
                    'theoreticalOptionValue': 0,
                    'theoreticalVolatility': 0,
                    'percentChange': 0,
                    'markChange': 0,
                    'markPercentChange': 0,
                    'intrinsicValue': 0,
                })
    return pd.DataFrame(data)


@pytest.fixture
def sample_calls_puts() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create sample calls and puts dataframes."""
    dates = pd.date_range(start='2024-01-01 09:30', periods=10, freq='min')
    dates = dates.tz_localize('US/Eastern')
    calls = pd.DataFrame({
        'strikePrice': [4000, 4050, 4100, 4150] * 10,
        'gex': np.random.uniform(-100, 100, 40),
        'putCall': ['CALL'] * 40,
        'processDateTime': np.repeat(dates, 4),
    })
    puts = pd.DataFrame({
        'strikePrice': [4000, 4050, 4100, 4150] * 10,
        'gex': np.random.uniform(-100, 100, 40),
        'putCall': ['PUT'] * 40,
        'processDateTime': np.repeat(dates, 4),
    })
    return calls, puts
