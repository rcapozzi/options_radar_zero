"""Callbacks module - Dash callback definitions."""
import datetime
import os
from typing import Any

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import pandas as pd
import pytz
from dash import Input, Output, State, dcc, html, no_update
from dash_iconify import DashIconify

from options_radar_zero.data_processing import (
    build_extenddata_payload,
    calculate_gex_metrics,
    calculate_strike_range,
    calculate_strike_volume_data,
    compute_incremental_volume,
    read_incremental_raw_rows,
)
from options_radar_zero.market_hours import is_market_open as _is_market_open
from options_radar_zero.visualization import (
    create_gex_chart,
    create_mark_comparison_chart,
    create_pez_dispenser_chart,
    create_strike_volume_chart,
)


def is_market_open() -> bool:
    """Check if market is currently open."""
    try:
        return _is_market_open()
    except Exception:
        return True


def calculate_strike_range_data(df: pd.DataFrame) -> Any:
    """Calculate strike range for slider."""
    return calculate_strike_range(df)


def init_file_state(oq: Any, symbol: str) -> dict:
    """Initialize per-symbol file-state tracking dict.

    Reads the full parquet file once to capture the baseline mtime, row
    count, and last cumulative ``totalVolume`` per option symbol.  Subsequent
    file-watcher polls use ``read_incremental_raw_rows`` to read only rows
    appended after ``row_count``.

    Args:
        oq: OptionQuotes instance for the symbol.
        symbol: The symbol key being tracked.

    Returns:
        Dict ``{symbol: {'mtime', 'row_count', 'last_total_volume'}}``
        suitable for storing in ``pc-summary-file-state``.
    """
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(oq.filename)
    # Column-projected read: only 'symbol' and 'totalVolume' are needed
    # for baseline tracking.
    schema_names = {field.name for field in pf.schema_arrow}
    columns = [c for c in ('symbol', 'totalVolume') if c in schema_names]
    table = pf.read(columns=columns or None)
    raw_df = table.to_pandas()
    # Normalize legacy column names
    from options_radar_zero.data_processing import _LEGACY_ALIASES
    for old_name, new_name in _LEGACY_ALIASES.items():
        if old_name in raw_df.columns and new_name not in raw_df.columns:
            raw_df.rename(columns={old_name: new_name}, inplace=True)
    return {
        symbol: {
            'mtime': os.path.getmtime(oq.filename),
            'row_count': pf.metadata.num_rows,
            'last_total_volume': raw_df.groupby('symbol')['totalVolume'].last().to_dict(),
        }
    }


def setup_callbacks(app: Any, data_loader: Any = None) -> None:
    """Register all Dash callbacks.

    Args:
        app: Dash application instance
        data_loader: DataLoader instance (optional, for backward compat)
    """
    # Use data_loader if provided, otherwise fall back to app.OptionQuotes
    def get_oq(symbol: str) -> Any:
        if data_loader is not None:
            return data_loader.get(symbol)
        return app.OptionQuotes[symbol]  # type: ignore[attr-defined]

    # Update strikes selector when symbol changes — fires on initial load too
    @app.callback(
        Output("strikes-selector-div", "children"),
        Input('symbol', 'value'),
    )
    def update_strikes_selector(symbol: str) -> Any:  # type: ignore[no-untyped-def]
        """Update strikes range slider based on current symbol data."""
        df = get_oq(symbol).reload()
        df = df.loc[(df.totalVolume > 10)]
        min_strike, max_strike, step_size, price_min, price_max, _ = calculate_strike_range_data(df)

        return [
            html.Span("Strikes Selector", className='menu-title'),
            dcc.RangeSlider(
                min=min_strike, max=max_strike, step=step_size,
                marks={i: f'{i}' for i in range(min_strike, max_strike, step_size)},
                value=[price_min - step_size, price_max + step_size],
                tooltip={"placement": "bottom", "always_visible": True},
                id='strikes-rangeslider'
            )
        ]
    # Initial chart setup callback fires when the interval triggers on page load
    @app.callback(
        Output("pc-summary-interval", "disabled", allow_duplicate=True),
        Output("pc-summary-store", "data", allow_duplicate=True),
        Output("pc-summary-file-state", "data", allow_duplicate=True),
        Output("pc-summary-graph", "figure", allow_duplicate=True),
        Input("initial-load-interval", "n_intervals"),
        State("symbol", "value"),
        State("x-axis", "value"),
        State("y-axis", "value"),
        prevent_initial_call='initial_duplicate'
    )
    def setup_chart_initial(n: int, symbol: str, xaxis: str, yaxis: str) -> tuple:  # type: ignore[no-untyped-def]
        """Set up chart on initial page load.

        Also initializes the per-symbol file-state tracking dict so the
        file watcher knows the baseline mtime and row count to compare
        against.
        """
        if n > 0:
            return no_update, no_update, no_update, no_update

        date_string = symbol.split(".")[-1]
        today = datetime.datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
        interval_disabled = not (date_string == today and is_market_open())

        df = get_oq(symbol).reload()
        df = df.loc[(df.totalVolume > 10)]
        min_strike, max_strike, step_size, price_min, price_max, _ = calculate_strike_range_data(df)
        strikes = [price_min - step_size, price_max + step_size]

        state, fig = create_pez_dispenser_chart(df, tuple(strikes), yaxis, xaxis, title=symbol)
        state['symbol'] = symbol

        # Initialize file-state tracking for this symbol
        oq = get_oq(symbol)
        file_state = init_file_state(oq, symbol)

        return interval_disabled, state, file_state, fig

    # Display file info when file-selector changes
    @app.callback(
        Output("file-info-div", "children"),
        Input("file-selector", "value"),
        prevent_initial_call=False
    )
    def update_file_info(filepath: str) -> Any:  # type: ignore[no-untyped-def]
        """Display information about the selected file."""
        if not filepath or not os.path.exists(filepath):
            return html.P("No file selected.", style={'color': '#6366f1', 'fontSize': '0.9em'})

        df = pd.read_parquet(filepath)
        row_count = len(df)
        unique_strikes = df['strikePrice'].nunique() if 'strikePrice' in df.columns else 0
        unique_dates = df['processDate'].nunique() if 'processDate' in df.columns else 0
        calls = len(df[df['putCall'] == 'CALL']) if 'putCall' in df.columns else 0
        puts = len(df[df['putCall'] == 'PUT']) if 'putCall' in df.columns else 0

        filename = os.path.basename(filepath)
        return html.Div([
            html.Span(f"📄 {filename}", style={'color': '#6366f1', 'fontSize': '0.9em', 'fontWeight': 'bold'}),
            html.Div([
                html.Span(f"Rows: {row_count}", style={'color': '#14b8a6', 'marginRight': '15px'}),
                html.Span(f"Strikes: {unique_strikes}", style={'color': '#14b8a6', 'marginRight': '15px'}),
                html.Span(f"Dates: {unique_dates}", style={'color': '#14b8a6', 'marginRight': '15px'}),
                html.Span(f"Calls: {calls}", style={'color': '#fbbf24', 'marginRight': '15px'}),
                html.Span(f"Puts: {puts}", style={'color': '#f87171'}),
            ], style={'marginTop': '4px', 'fontSize': '0.85em'}),
        ])

    # Show notification when chart is set up
    @app.callback(
        Output("notify-container", "children"),
        Input("pc-summary-store", "data"),
        State("symbol", "value"),
        State("pc-summary-interval", "disabled"),
        prevent_initial_call=True
    )
    def show_notification(cookie: dict, symbol: str, interval_disabled: bool) -> Any:  # type: ignore[no-untyped-def]
        """Show notification when chart is set up."""
        if cookie is None:
            return no_update
        date_string = symbol.split(".")[-1]
        today = datetime.datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
        interval_disabled_val = not (date_string == today and is_market_open())
        status = "disabled" if interval_disabled_val else "enabled"
        return dmc.Notification(
            id="my-notification",
            message=f"Updates {status} for {symbol}",
            color="green",
            action="show",
            icon=DashIconify(icon="mdi:gun"),
            autoClose=5_000
        )

    # Setup chart with initial data — fires when symbol or params change
    @app.callback(
        Output("pc-summary-interval", "disabled", allow_duplicate=True),
        Output("pc-summary-store", "data", allow_duplicate=True),
        Output("pc-summary-file-state", "data", allow_duplicate=True),
        Output("pc-summary-graph", "figure", allow_duplicate=True),
        Input("symbol", "value"),
        Input("x-axis", "value"),
        Input("y-axis", "value"),
        State("strikes-rangeslider", "value"),
        prevent_initial_call=True
    )
    def setup_chart(symbol: str, xaxis: str, yaxis: str, strikes: list | None, interval_disabled: bool = True) -> tuple:  # type: ignore[no-untyped-def]
        """Set up chart with initial data.

        When the symbol or axes change the chart is rebuilt from scratch and
        the per-symbol file-state tracking is reset so incremental reads
        start from row 0.
        """
        date_string = symbol.split(".")[-1]
        today = datetime.datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
        interval_disabled_val = not (date_string == today and is_market_open())

        df = get_oq(symbol).reload()
        # Use strikes from slider if available, otherwise calculate default range
        if strikes is None:
            strikes_df = df.loc[(df.totalVolume > 10)]
            if len(strikes_df) > 0:
                min_strike, max_strike, step_size, price_min, price_max, _ = calculate_strike_range_data(strikes_df)
                strikes = [price_min - step_size, price_max + step_size]
            else:
                strikes = [0, 100]
        state, fig = create_pez_dispenser_chart(df, tuple(strikes), yaxis, xaxis, title=symbol)
        state['symbol'] = symbol

        # Reset file-state tracking for this symbol
        oq = get_oq(symbol)
        file_state = init_file_state(oq, symbol)

        return interval_disabled_val, state, file_state, fig

    # ------------------------------------------------------------------
    # File watcher callback — incremental extendData on mtime change
    # ------------------------------------------------------------------
    @app.callback(
        Output("notify-container", "children", allow_duplicate=True),
        Output("pc-summary-file-state", "data", allow_duplicate=True),
        Output("pc-summary-store", "data", allow_duplicate=True),
        Output("pc-summary-graph", "extendData"),
        Input("file-watcher", "n_intervals"),
        State("pc-summary-store", "data"),
        State("pc-summary-file-state", "data"),
        prevent_initial_call=True
    )
    def update_chart_from_file(
        n: int,
        cookie: dict,
        file_state: dict,
    ) -> tuple:  # type: ignore[no-untyped-def]
        """Update chart with incremental data detected by the file watcher.

        Fires every ``FILE_WATCHER_INTERVAL_MS`` (10 s).  When the parquet
        file's mtime has advanced, only the newly appended rows are read
        (via ``read_incremental_raw_rows``), per-symbol volume deltas are
        computed (``compute_incremental_volume``), and the extendData payload
        is assembled (``build_extenddata_payload``).

        If the file hasn't changed, ``no_update`` is returned for all outputs.
        """
        notification: Any = no_update

        if not is_market_open():
            notification = dmc.Notification(
                id="my-notification",
                message="Updates disabled",
                color="red",
                action="show",
                autoClose=5_000
            )
            return notification, no_update, no_update, no_update

        if cookie is None or 'symbol' not in cookie:
            return no_update, no_update, no_update, no_update

        symbol = cookie['symbol']
        oq = get_oq(symbol)
        filepath = oq.filename

        # --- lazy-initialise per-symbol file tracking state -----------------
        if file_state is None:
            file_state = {}
        symbol_state: dict = file_state.get(symbol, {})

        # --- mtime check ----------------------------------------------------
        try:
            current_mtime = os.path.getmtime(filepath)
        except OSError:
            return no_update, no_update, no_update, no_update

        last_mtime = symbol_state.get('mtime', 0)

        if current_mtime <= last_mtime:
            # File unchanged since last poll
            return no_update, no_update, no_update, no_update

        # --- file changed: read incremental rows ----------------------------
        last_row_count = symbol_state.get('row_count', 0)
        new_df = read_incremental_raw_rows(filepath, last_row_count)

        if new_df.empty:
            # mtime advanced but no new rows (e.g. file rewritten in-place)
            symbol_state['mtime'] = current_mtime
            symbol_state['row_count'] = last_row_count
            file_state[symbol] = symbol_state
            return no_update, file_state, no_update, no_update

        # Compute incremental volume deltas per symbol.
        # totalVolume in the raw data is cumulative; we diff against the
        # last known cumulative value for each option symbol.
        last_total_volume: dict[str, float] = symbol_state.get(
            'last_total_volume', {}
        )
        new_df = compute_incremental_volume(new_df, last_total_volume)

        # Build extendData payload aligned to existing trace names
        strikes = tuple(cookie.get('strikes', [0, 100]))
        yaxis = cookie.get('yaxis', 'volume')
        xaxis = cookie.get('xaxis', 'processDateTime')

        updates, updated_names, _added_traces = build_extenddata_payload(
            new_df, cookie['names'], strikes, yaxis, xaxis
        )

        # If there are no new data points to extend, just update tracking
        if not updates or all(
            len(u.get('x', [])) == 0 for u in updates
        ):
            symbol_state['mtime'] = current_mtime
            symbol_state['row_count'] = last_row_count + len(new_df)
            symbol_state['last_total_volume'] = last_total_volume
            file_state[symbol] = symbol_state
            return no_update, file_state, cookie, no_update

        # --- update cookie (pc-summary-store) ------------------------------
        cookie['names'] = updated_names
        new_max_dt = new_df['processDateTime'].max()
        cookie['max_dt'] = new_max_dt

        # --- update file-state tracking ------------------------------------
        symbol_state['mtime'] = current_mtime
        symbol_state['row_count'] = last_row_count + len(new_df)
        symbol_state['last_total_volume'] = last_total_volume
        file_state[symbol] = symbol_state

        return no_update, file_state, cookie, updates

    # Strike volume charts update
    @app.callback(
        Output("strike-volume-div", "children"),
        Input('pc-summary-interval', 'n_intervals'),
        Input("symbol", "value"),
    )
    def update_strike_volume(n: int, symbol: str) -> Any:  # type: ignore[no-untyped-def]
        """Update strike volume charts."""
        cache_key = 'strike-volume-div'
        oq = get_oq(symbol)
        df = oq.reload()
        max_dt = oq.max_dt

        if n is not None and max_dt.time() >= datetime.time(16, 0):
            return no_update

        content = oq.cache_get(cache_key)
        if content is not None:
            return content

        calls, puts, underlying_price = calculate_strike_volume_data(df, max_dt)
        _, _, net_gex_price = calculate_gex_metrics(df[(df.processDateTime == max_dt)])

        strikes_df = df.groupby(['strikePrice']).agg({'totalVolume': sum}).reset_index()
        dt = max_dt.strftime('%Y-%m-%d %H:%M')

        fig = create_strike_volume_chart(calls, puts, strikes_df, underlying_price, net_gex_price, dt)
        fig2 = create_mark_comparison_chart(df, underlying_price, dt)
        fig3 = create_gex_chart(oq.data, symbol, mode=0)
        fig4 = create_gex_chart(oq.data, symbol, mode=1)

        content = [
            dbc.Col(dcc.Graph(id="strike-volume-left", config={"displayModeBar": False}, figure=fig),
                   style={'width': '49%', 'display': 'inline-block'}, class_name='card'),
            dbc.Col(dcc.Graph(id="strike-volume-right", config={"displayModeBar": False}, figure=fig2),
                   style={'width': '49%', 'display': 'inline-block'}, className='card'),
            dbc.Col(dcc.Graph(id="strike-volume-left2", config={"displayModeBar": False}, figure=fig3),
                   style={'width': '49%', 'display': 'inline-block'}, className='card'),
            dbc.Col(dcc.Graph(id="strike-volume-right2", config={"displayModeBar": False}, figure=fig4),
                   style={'width': '49%', 'display': 'inline-block'}, className='card'),
        ]

        return oq.cache_set(cache_key, content)
