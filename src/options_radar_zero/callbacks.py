"""Callbacks module - Dash callback definitions."""
import datetime
from typing import Any

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import pandas as pd
import pytz
from dash import Input, Output, State, dcc, html, no_update
from dash_iconify import DashIconify

from options_radar_zero.data_processing import (
    calculate_gex_metrics,
    calculate_strike_range,
    calculate_strike_volume_data,
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

    # Update strikes selector when symbol changes
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

    # Main chart update on interval
    @app.callback(
        Output("notify-container", "children", allow_duplicate=True),
        Output("pc-summary-interval", "disabled", allow_duplicate=True),
        Output("pc-summary-store", "data", allow_duplicate=True),
        Output("pc-summary-graph", "extendData"),
        Output("data-table-div", "children"),
        Output("metrics-div", "children"),
        Input('pc-summary-interval', 'n_intervals'),
        State("pc-summary-store", "data"),
        prevent_initial_call=True
    )
    def update_chart_on_interval(n_interval: int, cookie: dict) -> tuple:  # type: ignore[no-untyped-def]
        """Update chart with incremental data from polling."""
        notification: Any = no_update
        interval_disabled: Any = no_update

        if not is_market_open():
            notification = dmc.Notification(
                id="my-notification",
                message="Updates disabled",
                color="red",
                action="show",
                autoClose=5_000
            )
            interval_disabled = True
            return notification, interval_disabled, no_update, no_update, no_update, no_update

        symbol = cookie['symbol']
        oq = get_oq(symbol)
        df = oq.reload()
        max_dt = cookie['max_dt']
        df = df[(df.processDateTime > max_dt)]

        if df.empty:
            return no_update, no_update, cookie, no_update, no_update, no_update

        state, fig = create_pez_dispenser_chart(
            df, cookie['strikes'], cookie['yaxis'], cookie['xaxis'], title='Nope'
        )

        data = {trace['name']: {'x': trace['x'], 'y': trace['y']} for trace in fig['data']}
        updates = []

        for name in cookie['names']:
            if name in data:
                updates.append(data[name])
            else:
                updates.append({'x': [], 'y': []})

        new_traces = set(data.keys()) - set(cookie['names'])
        for name in new_traces:
            updates.append(data[name])

        cookie['names'].extend(new_traces)
        cookie['max_dt'] = state['max_dt']

        return notification, interval_disabled, cookie, updates, no_update, no_update

    # Initial chart setup on parameter change
    @app.callback(
        Output("notify-container", "children"),
        Output("pc-summary-interval", "disabled"),
        Output("pc-summary-store", "data"),
        Output("pc-summary-graph", "figure"),
        Input("symbol", "value"),
        Input("strikes-rangeslider", "value"),
        Input("x-axis", "value"),
        Input("y-axis", "value"),
        State("pc-summary-interval", "disabled"),
        prevent_initial_call=True
    )
    def setup_chart(symbol: str, strikes: list, xaxis: str, yaxis: str, interval_disabled: bool) -> tuple:  # type: ignore[no-untyped-def]
        """Set up chart with initial data."""
        date_string = symbol.split(".")[-1]
        today = datetime.datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
        interval_disabled = not (date_string == today and is_market_open())

        status = "disabled" if interval_disabled else "enabled"
        icon = "mdi:gun"
        notification = dmc.Notification(
            id="my-notification",
            message=f"Updates {status} for {symbol}",
            color="green",
            action="show",
            icon=DashIconify(icon=icon),
            autoClose=5_000
        )

        df = get_oq(symbol).reload()
        state, fig = create_pez_dispenser_chart(df, strikes, yaxis, xaxis, title=symbol)
        state['symbol'] = symbol

        return notification, interval_disabled, state, fig

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
