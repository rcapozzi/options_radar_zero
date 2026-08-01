"""Layout module - UI layout definitions."""
from typing import Any

import dash_bootstrap_components as dbc
import dash_extendable_graph as deg
import dash_mantine_components as dmc
from dash import dcc, html

from options_radar_zero.config import DEFAULT_X_FIELDS, DEFAULT_Y_FIELDS, config


def create_static_link(page: str) -> html.A:
    """Create a static link component."""
    return html.A(f"{page}.html",
                  href=f"static/{page}.html",
                  style={'margin-right': '10px'},
                  target="_blank")


def create_strike_slider(
    min_val: int,
    max_val: int,
    step: int,
    price_min: int,
    price_max: int
) -> html.Div:
    """Create strike price range slider."""
    return html.Div([
        html.Span("Strikes Selector", className='menu-title'),
        dcc.RangeSlider(
            min=min_val,
            max=max_val,
            step=step,
            marks={i: f'{i}' for i in range(min_val, max_val, step)},
            value=[price_min - step, price_max + step],
            tooltip={"placement": "bottom", "always_visible": True},
            id='strikes-rangeslider'
        )
    ], className="card")


def create_dropdown_field(label: str, id: str, options: list[str], value: str) -> html.Div:
    """Create a dropdown field with label."""
    return html.Div([
        html.Div(children=label, className="menu-title"),
        dcc.Dropdown(
            id=id,
            options=[{"label": opt, "value": opt} for opt in options],
            value=value,
            clearable=False,
            className="dropdown",
        )
    ])


def create_controls(symbols: list[str]) -> html.Div:
    """Create the control panel with dropdowns."""
    return html.Div([
        create_dropdown_field("Symbol", "symbol", symbols, symbols[0]),
        create_dropdown_field("x-axis", "x-axis", DEFAULT_X_FIELDS, DEFAULT_X_FIELDS[0]),
        create_dropdown_field("y-axis", "y-axis", DEFAULT_Y_FIELDS, DEFAULT_Y_FIELDS[0]),
    ], className="menu")


def create_hidden_components() -> html.Div:
    """Create hidden interval and store components."""
    return html.Div([
        dcc.Interval(
            id='pc-summary-interval',
            interval=config.DEFAULT_INTERVAL_SECONDS * 1000,
            disabled=True
        ),
        dcc.Store(id="pc-summary-store", data=None, modified_timestamp=0),
        html.Div(id="notify-container"),
    ], style={'display': 'none'})


def create_download_buttons() -> html.Div:
    """Create download buttons for data export."""
    return html.Div([
        html.Button("Download Parquet", id="btn_parquet"),
        dcc.Download(id="download-dataframe-parquet"),
        html.Button("CSV", id="btn_csv"),
        dcc.Download(id="download-dataframe-csv"),
    ])


def create_data_table_container() -> html.Div:
    """Create empty data table container."""
    return html.Div(id="data-table-div", children=[])


def create_metrics_container() -> html.Div:
    """Create metrics display container."""
    return html.Div(id='metrics-div', style={'padding': '5px', 'fontsize:': '10px', 'font-family': 'monospace'})


def create_main_layout(symbols: list[str], initial_data_loaded: bool = True) -> Any:
    """Create the main application layout.

    Args:
        symbols: List of available symbols
        initial_data_loaded: Whether data was successfully loaded

    Returns:
        Dash HTML layout component
    """
    if not initial_data_loaded:
        return html.Div([
            html.Hr(),
            html.H1("You filthy Degen. Check back during market hours."),
        ])

    content = html.Div([
        dbc.Alert(id='alerts'),
        html.Hr(),
        html.Details([
            html.Summary('Secret Section (Forked from https://github.com/rcapozzi/dash-app)',
                        style={'color': 'red', 'background': 'black'}),
            html.Div(html.A("financialjuice", href="https://www.financialjuice.com/home")),
            create_data_table_container(),
        ]),
        html.Div([
            create_static_link("traderade-0dte"),
            create_static_link("traderade-0dte-alt"),
        ], style={'display': 'flex', 'color': 'red', 'background': 'yellow'}),
        create_metrics_container(),
        html.Div(deg.ExtendableGraph(id="pc-summary-graph", config=config.CHART_MODEBAR), \
                 className="card", id='row2-div'),
        create_controls(symbols),
        html.Div(id='strikes-selector-div', className="card"),
        create_download_buttons(),
        create_hidden_components(),
    ])

    return dmc.MantineProvider(dmc.NotificationProvider([content]))
