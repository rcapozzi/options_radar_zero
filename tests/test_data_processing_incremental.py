"""Tests for incremental data processing functions."""
import os
from datetime import datetime, timezone

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from options_radar_zero.data_processing import (
    build_extenddata_payload,
    compute_incremental_volume,
    read_incremental_raw_rows,
)


@pytest.fixture
def raw_parquet_file(tmp_path: str):
    """Create a raw parquet file with option chain data for incremental testing."""
    # Create two batches of data: an initial batch and an appended batch
    base_time = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    batch1_time = base_time
    batch2_time = datetime(2024, 1, 1, 10, 1, tzinfo=timezone.utc)

    rows = []
    # Initial batch: 3 strikes x 2 put/call = 6 rows
    for strike in [4000, 4050, 4100]:
        for putcall in ['CALL', 'PUT']:
            rows.append({
                'processDateTime': batch1_time,
                'symbol': f'SPX{strike}{putcall[0]}',
                'putCall': putcall,
                'strikePrice': strike,
                'totalVolume': 1000,
                'mark': 5.0,
                'underlyingPrice': 4100,
                'openInterest': 100,
                'bid': 0,
                'ask': 0,
            })

    filepath = os.path.join(tmp_path, "SPX.20240101.chain.parquet")
    pd.DataFrame(rows).to_parquet(filepath)

    # Append a second batch: 3 strikes x 2 put/call = 6 rows at a later time
    batch2_raw = []
    for strike in [4000, 4050, 4100]:
        for putcall in ['CALL', 'PUT']:
            batch2_raw.append({
                'processDateTime': batch2_time,
                'symbol': f'SPX{strike}{putcall[0]}',
                'putCall': putcall,
                'strikePrice': strike,
                'totalVolume': 1500,  # increased from 1000
                'mark': 5.5,
                'underlyingPrice': 4101,
                'openInterest': 120,
                'bid': 0,
                'ask': 0,
            })

    # Append batch2 to the parquet file
    import pyarrow as pa
    import pyarrow.parquet as pq

    table1 = pq.read_table(filepath)
    table2 = pa.Table.from_pandas(pd.DataFrame(batch2_raw))
    combined = pa.concat_tables([table1, table2])
    pq.write_table(combined, filepath)

    return filepath


class TestReadIncrementalRawRows:
    def test_read_all_rows_when_no_offset(self, raw_parquet_file):
        """Reading with row_count=0 should return all rows."""
        df = read_incremental_raw_rows(raw_parquet_file, 0)
        assert len(df) == 12  # 6 initial + 6 appended

    def test_read_only_new_rows(self, raw_parquet_file):
        """Reading with row_count=6 should return only the 6 new rows."""
        df = read_incremental_raw_rows(raw_parquet_file, 6)
        assert len(df) == 6

    def test_read_no_new_rows(self, raw_parquet_file):
        """Reading with row_count=12 should return empty DataFrame."""
        df = read_incremental_raw_rows(raw_parquet_file, 12)
        assert len(df) == 0

    def test_read_beyond_total_rows(self, raw_parquet_file):
        """Reading with row_count > total rows should return empty DataFrame."""
        df = read_incremental_raw_rows(raw_parquet_file, 100)
        assert len(df) == 0

    def test_read_uses_column_projection(self, raw_parquet_file):
        """Only the columns needed by the incremental pipeline should be returned."""
        df = read_incremental_raw_rows(raw_parquet_file, 6)
        # bid, ask, openInterest should NOT be in the result (column projection)
        assert 'bid' not in df.columns
        assert 'ask' not in df.columns
        assert 'openInterest' not in df.columns
        # Required columns must be present
        for col in ('processDateTime', 'symbol', 'putCall', 'strikePrice',
                     'totalVolume', 'mark', 'underlyingPrice'):
            assert col in df.columns

    def test_read_correct_data_after_offset(self, raw_parquet_file):
        """Rows after the offset should have totalVolume=1500 (batch2)."""
        df = read_incremental_raw_rows(raw_parquet_file, 6)
        assert (df['totalVolume'] == 1500).all()

    def test_read_multi_row_group(self, tmp_path):
        """Reading across multiple row groups returns the correct new rows."""
        # Create a parquet file with 2 row groups: 4 rows each.
        rows = []
        for i in range(8):
            rows.append({
                'processDateTime': datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                'symbol': f'SPX{4000 + i}C',
                'putCall': 'CALL',
                'strikePrice': 4000 + i,
                'totalVolume': 1000 + i,
                'mark': 5.0,
                'underlyingPrice': 4100,
            })
        table = pa.Table.from_pandas(pd.DataFrame(rows))
        filepath = os.path.join(tmp_path, "multi.parquet")
        pq.write_table(table, filepath, row_group_size=4)

        pf = pq.ParquetFile(filepath)
        assert pf.num_row_groups == 2

        # Read rows 4-7 (second row group)
        df = read_incremental_raw_rows(filepath, 4)
        assert len(df) == 4
        assert (df['totalVolume'] == [1004, 1005, 1006, 1007]).all()


class TestComputeIncrementalVolume:
    def test_volume_diff_calculated(self, raw_parquet_file):
        """Volume diff should be new_totalVolume - last_totalVolume."""
        df = read_incremental_raw_rows(raw_parquet_file, 0)
        # All rows: totalVolume=1000 (batch1) and totalVolume=1500 (batch2)
        new_df = read_incremental_raw_rows(raw_parquet_file, 6)

        last_total_volume = {}
        # Process batch1 to set baseline
        batch1 = df.iloc[:6]
        result = compute_incremental_volume(batch1, last_total_volume)
        for sym in batch1['symbol']:
            last_total_volume[sym] = 1000.0

        # Process batch2
        result2 = compute_incremental_volume(new_df, last_total_volume)
        assert len(result2) == 6
        # Volume diff should be 1500 - 1000 = 500
        for _, row in result2.iterrows():
            assert row['volume'] == 500

    def test_put_volume_negated(self, raw_parquet_file):
        """PUT volume should be negated (sign=-1)."""
        df = read_incremental_raw_rows(raw_parquet_file, 6)
        last_total_volume = {row['symbol']: 1000.0 for _, row in df.iterrows()}
        result = compute_incremental_volume(df, last_total_volume)

        puts = result[result['putCall'] == 'PUT']
        calls = result[result['putCall'] == 'CALL']
        assert (puts['signed_volume'] == -500).all()
        assert (calls['signed_volume'] == 500).all()

    def test_empty_dataframe(self):
        """Empty DataFrame should return unchanged."""
        result = compute_incremental_volume(pd.DataFrame(), {})
        assert len(result) == 0

    def test_total_volume_updates_in_dict(self):
        """The last_total_volume dict should be updated with new values."""
        df = pd.DataFrame([
            {'symbol': 'A', 'putCall': 'CALL', 'totalVolume': 200},
            {'symbol': 'B', 'putCall': 'PUT', 'totalVolume': 300},
        ])
        last_total_volume = {'A': 100.0, 'B': 250.0}
        result = compute_incremental_volume(df, last_total_volume)
        assert last_total_volume['A'] == 200
        assert last_total_volume['B'] == 300

    def test_multiple_rows_per_symbol(self):
        """Within a batch, volume diffs should be computed per-symbol."""
        df = pd.DataFrame([
            {'symbol': 'A', 'putCall': 'CALL', 'totalVolume': 200},
            {'symbol': 'A', 'putCall': 'CALL', 'totalVolume': 300},
            {'symbol': 'A', 'putCall': 'CALL', 'totalVolume': 350},
        ])
        last_total_volume = {'A': 100.0}
        result = compute_incremental_volume(df, last_total_volume)
        # Diffs: 200-100=100, 300-200=100, 350-300=50
        assert result['volume'].tolist() == [100.0, 100.0, 50.0]
        assert result['signed_volume'].tolist() == [100.0, 100.0, 50.0]
        assert last_total_volume['A'] == 350

    def test_negative_volume_raises_error(self):
        """A decreasing totalVolume (negative diff) should raise ValueError."""
        df = pd.DataFrame([
            {'symbol': 'A', 'putCall': 'CALL', 'totalVolume': 100},
        ])
        last_total_volume = {'A': 200.0}
        with pytest.raises(ValueError, match="Negative incremental volume"):
            compute_incremental_volume(df, last_total_volume)

    def test_negative_volume_does_not_mutate_input_or_dict(self):
        """On failure, the input DataFrame and last_total_volume should be untouched."""
        df = pd.DataFrame([
            {'symbol': 'A', 'putCall': 'CALL', 'totalVolume': 50},
        ])
        df_before = df.copy()
        last_total_volume = {'A': 100.0}
        with pytest.raises(ValueError):
            compute_incremental_volume(df, last_total_volume)
        pd.testing.assert_frame_equal(df, df_before)
        assert last_total_volume == {'A': 100.0}


class TestBuildExtenddataPayload:
    @pytest.fixture
    def new_df(self):
        """Create a small dataframe simulating new raw rows with volume computed."""
        base_time = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        df = pd.DataFrame([
            {
                'processDateTime': base_time,
                'symbol': 'SPX4000C',
                'putCall': 'CALL',
                'strikePrice': 4000,
                'totalVolume': 1500,
                'mark': 5.0,
                'underlyingPrice': 4100,
            },
            {
                'processDateTime': base_time,
                'symbol': 'SPX4000P',
                'putCall': 'PUT',
                'strikePrice': 4000,
                'totalVolume': 800,
                'mark': 5.0,
                'underlyingPrice': 4100,
            },
        ])
        # Run through compute_incremental_volume to add volume/signed_volume.
        # Provide prior totalVolume values so the diff is non-zero.
        prior_tv = {
            'SPX4000C': 1000.0,
            'SPX4000P': 500.0,
        }
        return compute_incremental_volume(df, prior_tv)

    def test_empty_df_returns_empty(self):
        """Empty DataFrame should return empty updates."""
        updates, names, added = build_extenddata_payload(
            pd.DataFrame(), [], (4000, 4100), 'volume', 'processDateTime'
        )
        assert updates == []
        assert names == []
        assert added == set()

    def test_existing_traces_get_data(self, new_df):
        """Existing trace names should get their x/y data."""
        # Include underlyingPrice in existing traces since build_extenddata_payload
        # always adds it for processDateTime x-axis
        existing = ['4000C', '4000P', 'underlyingPrice']
        updates, names, added = build_extenddata_payload(
            new_df, existing, (4000, 4100), 'volume', 'processDateTime'
        )
        assert len(updates) == 3
        assert len(updates[0]['x']) == 1  # 4000C trace
        assert len(updates[1]['x']) == 1  # 4000P trace
        assert len(updates[2]['x']) == 1  # underlyingPrice trace

    def test_call_volume_positive_put_negative(self, new_df):
        """CALL volume should be positive, PUT volume should be negative."""
        existing = ['4000C', '4000P', 'underlyingPrice']
        updates, names, added = build_extenddata_payload(
            new_df, existing, (4000, 4100), 'volume', 'processDateTime'
        )
        # First update is for 4000C (CALL → sign=1)
        assert updates[0]['y'][0] > 0
        # Second update is for 4000P (PUT → sign=-1)
        assert updates[1]['y'][0] < 0

    def test_new_traces_appended(self, new_df):
        """New trace names not in the existing list should be appended."""
        updates, names, added = build_extenddata_payload(
            new_df, [], (4000, 4100), 'volume', 'processDateTime'
        )
        # 2 option traces + 1 underlyingPrice trace = 3 updates
        assert len(updates) == 3
        assert '4000C' in added
        assert '4000P' in added
        assert 'underlyingPrice' in added
        assert len(names) == 3

    def test_underlying_price_trace_added(self, new_df):
        """underlyingPrice trace should be included for processDateTime x-axis."""
        updates, names, added = build_extenddata_payload(
            new_df, [], (4000, 4100), 'volume', 'processDateTime'
        )
        assert 'underlyingPrice' in names

    def test_no_underlying_price_for_strikePrice_xaxis(self, new_df):
        """underlyingPrice trace should NOT be added for strikePrice x-axis."""
        updates, names, added = build_extenddata_payload(
            new_df, [], (4000, 4100), 'volume', 'strikePrice'
        )
        assert 'underlyingPrice' not in names

    def test_yaxis_respected_for_mark(self, new_df):
        """y_val should use the yaxis column, not hardcoded 'volume'."""
        existing = ['4000C', '4000P', 'underlyingPrice']
        updates, names, added = build_extenddata_payload(
            new_df, existing, (4000, 4100), 'mark', 'processDateTime'
        )
        # 4000C trace should use mark value (5.0) * sign (1) = 5.0
        assert updates[0]['y'][0] == pytest.approx(5.0)
        # 4000P trace should use mark value (5.0) * sign (-1) = -5.0
        assert updates[1]['y'][0] == pytest.approx(-5.0)

    def test_yaxis_respected_for_totalVolume(self, new_df):
        """y_val should use totalVolume column when yaxis='totalVolume'."""
        existing = ['4000C', '4000P', 'underlyingPrice']
        updates, names, added = build_extenddata_payload(
            new_df, existing, (4000, 4100), 'totalVolume', 'processDateTime'
        )
        # 4000C: totalVolume=1500 * sign(1) = 1500
        assert updates[0]['y'][0] == pytest.approx(1500.0)
        # 4000P: totalVolume=800 * sign(-1) = -800
        assert updates[1]['y'][0] == pytest.approx(-800.0)

    def test_underlying_price_uses_mean_per_timestamp(self):
        """underlyingPrice trace should use mean per timestamp (not first row)."""
        dt1 = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        dt2 = datetime(2024, 1, 1, 10, 1, tzinfo=timezone.utc)
        df = pd.DataFrame([
            {
                'processDateTime': dt1,
                'symbol': 'SPX4000C',
                'putCall': 'CALL',
                'strikePrice': 4000,
                'totalVolume': 1500,
                'mark': 5.0,
                'underlyingPrice': 4100.0,
            },
            {
                'processDateTime': dt1,
                'symbol': 'SPX4000P',
                'putCall': 'PUT',
                'strikePrice': 4000,
                'totalVolume': 800,
                'mark': 5.0,
                'underlyingPrice': 4200.0,
            },
            {
                'processDateTime': dt2,
                'symbol': 'SPX4100C',
                'putCall': 'CALL',
                'strikePrice': 4100,
                'totalVolume': 1700,
                'mark': 6.0,
                'underlyingPrice': 4300.0,
            },
        ])
        prior_tv = {'SPX4000C': 1000.0, 'SPX4000P': 500.0, 'SPX4100C': 1200.0}
        df = compute_incremental_volume(df, prior_tv)

        existing = ['4000C', '4000P', '4100C', 'underlyingPrice']
        updates, names, added = build_extenddata_payload(
            df, existing, (4000, 4100), 'volume', 'processDateTime'
        )
        # underlyingPrice is at index 3 (after 4000C, 4000P, 4100C)
        up_update = updates[3]
        # Two distinct timestamps → two entries
        assert len(up_update['x']) == 2
        # Mean for dt1: (4100 + 4200) / 2 = 4150; dt2: 4300
        assert up_update['y'] == pytest.approx([4150.0, 4300.0])

    def test_underlying_price_no_duplicates_for_same_timestamp(self):
        """underlyingPrice trace should not duplicate entries for same timestamp."""
        dt1 = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        df = pd.DataFrame([
            {
                'processDateTime': dt1,
                'symbol': 'SPX4000C',
                'putCall': 'CALL',
                'strikePrice': 4000,
                'totalVolume': 1500,
                'mark': 5.0,
                'underlyingPrice': 4100.0,
            },
            {
                'processDateTime': dt1,
                'symbol': 'SPX4000P',
                'putCall': 'PUT',
                'strikePrice': 4000,
                'totalVolume': 800,
                'mark': 5.0,
                'underlyingPrice': 4200.0,
            },
            {
                'processDateTime': dt1,
                'symbol': 'SPX4100C',
                'putCall': 'CALL',
                'strikePrice': 4100,
                'totalVolume': 1700,
                'mark': 6.0,
                'underlyingPrice': 4150.0,
            },
        ])
        prior_tv = {'SPX4000C': 1000.0, 'SPX4000P': 500.0, 'SPX4100C': 1200.0}
        df = compute_incremental_volume(df, prior_tv)

        existing = ['4000C', '4000P', '4100C', 'underlyingPrice']
        updates, names, added = build_extenddata_payload(
            df, existing, (4000, 4100), 'volume', 'processDateTime'
        )
        up_update = updates[3]
        # 3 rows all at dt1, but only 1 unique timestamp → 1 entry (no dups)
        assert len(up_update['x']) == 1
        assert len(up_update['y']) == 1
        # Mean: (4100 + 4200 + 4150) / 3 = 4150
        assert up_update['y'][0] == pytest.approx(4150.0)
