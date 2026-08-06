# Spec: Real-time Incremental Chart Updates via File Watcher + extendData (Option B)

## Overview
Replace the current pattern of reloading the entire parquet file on each interval tick with an incremental approach. The Dash app polls the parquet file's modification time at a shorter interval (e.g., 10s) and, when the file has changed, reads only the newly appended rows and extends the existing plotly traces via `extendData`.

## Requirements
1. **File modification polling**: `dcc.Interval` component checking for parquet file mtime changes
2. **Incremental parquet read**: Track last-seen row count per symbol; use row offset to read only new data
3. **Per-symbol tracking**: Track `max_dt` and `names` per symbol to align trace data correctly
4. **extendData integration**: Map new data to existing plotly traces by symbol name

## Data Flow
```
Poller (background):
  - Writes new rows to output/SPY.20260803.chain.parquet every minute
  - Parquet file grows with appended rows

Dash Server:
  - interval callback fires every 10s
  - Checks file mtime vs last known mtime
  - If changed:
    - Read from last_row_index to end of parquet
    - Compute totalVolume diff per symbol (incremental volume)
    - Negate PUT volume
    - Return extendData payload mapping traces by name
  - If unchanged: return no_update
```

## Implementation Steps

### Phase 1: File Watcher Infrastructure
- Add `dcc.Interval(id="file-watcher", interval=10000, n_intervals=0)` hidden component to layout
- Add new `dcc.Store` for mtime tracking per symbol
- Store last-known row count in a `dcc.Store` keyed by symbol

### Phase 2: Incremental Read Callback
- New callback `update_chart_from_file(n: int, stored_row_counts: dict)` fires on file-watcher interval
- Reads `stored_row_counts` from dcc.Store to determine where to start reading
- Uses row-group-aware parquet reading via `ParquetFile.read_row_groups()` with column projection
  instead of `pd.read_parquet` to avoid decoding the entire file
- Computes incremental volume diffs per symbol using vectorized pandas groupby operations
- Validates that `totalVolume` (cumulative) never decreases between polls; raises `ValueError` on anomaly
- Returns `extendData` payload aligned to trace names

### Phase 3: extendData Integration
- Replace current `update_chart_on_interval` callback output to use `extendData` instead of full `figure` update
- Map new data points to traces by symbol name from `cookie['names']`

## Data Schema Tracking
- Track per-symbol: `last_row_count`, `max_dt`, active trace names
- Store in `pc-summary-store` data dict

## Benefits
- Near real-time updates (~10s latency)
- No WebSocket server or Redis dependency
- Minimal data transfer (new rows only)
- Works with existing infrastructure

## Drawbacks
- Still polls file system (not push-based)
- 10s polling adds filesystem load (negligible for single file)
- Parquet row offset support requires skip_rows approach (slight overhead)
