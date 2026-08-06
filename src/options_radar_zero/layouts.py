"""Layout module - UI layout definitions."""
from typing import Any

import dash_bootstrap_components as dbc
import dash_extendable_graph as deg
import dash_mantine_components as dmc
from dash import dcc, html

from options_radar_zero.config import DEFAULT_X_FIELDS, DEFAULT_Y_FIELDS, config


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


def create_file_selector() -> html.Div:
    """Create a dropdown listing all parquet files in the output directory.

    Shows filenames (e.g. SPY.20260803.chain.parquet) in a dropdown
    so the user can select which file to load.
    """
    import glob
    import os

    from options_radar_zero.config import config

    raw_files = sorted(
        [f.replace('\\', '/') for f in glob.glob(os.path.join(config.DATA_DIR, '*.parquet'))],
        reverse=True,
    )

    if not raw_files:
        return html.Div([
            html.Div(children="Data Files", className="menu-title"),
            html.P("No data files found in output directory.",
                  style={'color': 'yellow', 'padding': '10px'}),
        ])

    options = [
        {"label": f.rsplit('/', 1)[-1], "value": f}
        for f in raw_files
    ]
    default_value = options[0]["value"] if options else None

    return html.Div([
        html.Div(children="Data Files", className="menu-title"),
        dcc.Dropdown(
            id="file-selector",
            options=options,
            value=default_value,
            clearable=False,
            className="dropdown",
        )
    ])


def create_hidden_components() -> html.Div:
    """Create hidden interval and store components.

    Includes:
    - pc-summary-interval: 60s interval for periodic chart updates (disabled
      until market is open).
    - file-watcher: 10s interval that polls the parquet file's modification
      time for near real-time incremental updates via extendData.
    - pc-summary-store: Holds the chart state dict (trace names, max_dt,
      strikes, axes, symbol).
    - pc-summary-file-state: Tracks per-symbol file state (mtime, row count,
      last cumulative totalVolume per symbol) to support incremental parquet
      reads — only new rows are loaded when the file changes.
    """
    return html.Div([
        dcc.Interval(
            id='pc-summary-interval',
            interval=config.DEFAULT_INTERVAL_SECONDS * 1000,
            disabled=True
        ),
        # File watcher: polls parquet mtime every 10s for real-time updates
        dcc.Interval(
            id='file-watcher',
            interval=config.FILE_WATCHER_INTERVAL_MS,
            n_intervals=0,
            disabled=False,
        ),
        dcc.Store(id="pc-summary-store", data=None, modified_timestamp=0),
        dcc.Store(id="pc-summary-file-state", data=None),
        html.Div(id="notify-container"),
        # Hidden interval that fires once on page load to trigger initial chart setup
        dcc.Interval(
            id='initial-load-interval',
            interval=100,
            n_intervals=0,
            disabled=False,
        ),
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


def create_file_list_section() -> html.Div:
    """Create a section listing available data files in the output directory.

    Shows both symbol-keyed files (from get_parquet_files) and raw filenames,
    so the user always sees what's available even if parsing fails.
    """
    import glob
    import os

    from options_radar_zero.config import config, get_parquet_files

    files = get_parquet_files(max_files=50)
    raw_files = sorted(
        [f.replace('\\', '/') for f in glob.glob(os.path.join(config.DATA_DIR, '*.parquet'))],
        reverse=True,
    )

    if not raw_files:
        return html.Div([
            html.P("No data files found in output directory.",
                   style={'color': 'yellow', 'padding': '10px'}),
        ])

    items: list[Any] = []
    for symbol, filepath in files.items():
        items.append(html.Div([
            html.Span(symbol, style={'color': 'yellow'}),
            html.Span(f" → {filepath}", style={'color': 'lightgray', 'fontSize': '0.8em'}),
        ], style={'padding': '2px 0'}))

    # Include any files not captured in the symbol-keyed dict
    parsed_paths = set(files.values())
    for filepath in raw_files:
        if filepath not in parsed_paths:
            basename = filepath.rsplit('/', 1)[-1]
            items.append(html.Div([
                html.Span(basename, style={'color': 'yellow'}),
                html.Span(f" → {filepath}", style={'color': 'lightgray', 'fontSize': '0.8em'}),
            ], style={'padding': '2px 0'}))

    return html.Div([
        html.H4("Available data files:", style={'color': '#6366f1'}),
        html.Div(items),
    ])


def create_main_layout(symbols: list[str], initial_data_loaded: bool = True) -> Any:
    """Create the main application layout.

    Args:
        symbols: List of available symbols
        initial_data_loaded: Whether data was successfully loaded

    Returns:
        Dash HTML layout component
    """
    if symbols:
        # We have data files — show the full dashboard with dropdown
        content = html.Div([
            dbc.Alert(id='alerts'),
            html.Hr(),
            html.Details([
                html.Summary('Secret Section (Forked from https://github.com/rcapozzi/dash-app)',
                            style={'color': 'red', 'background': 'black'}),
                html.Div(html.A("financialjuice", href="https://www.financialjuice.com/home")),
                create_data_table_container(),
            ]),
            create_file_selector(),
            html.Div(id="file-info-div", style={'marginBottom': '10px'}),
            create_metrics_container(),
            html.Div(deg.ExtendableGraph(id="pc-summary-graph", config=config.CHART_MODEBAR), \
                     className="card", id='row2-div'),
            create_controls(symbols),
            html.Div(id='strikes-selector-div', className="card"),
            create_download_buttons(),
            create_hidden_components(),
        ])

        if not initial_data_loaded:
            content = html.Div([
                html.Div([
                    html.Hr(),
                    html.H1("You filthy Degen. Check back during market hours."),
                    html.Span("Error loading data", style={'padding': '5px', 'fontsize:': '10px'}),
                ]),
                create_file_selector(),
            ])

        return dmc.MantineProvider(dmc.NotificationProvider([content]))

    # No symbols found — show file selector so user knows what's available
    return dmc.MantineProvider(dmc.NotificationProvider([
        html.Div([
            html.Hr(),
            html.H1("You filthy Degen. Check back during market hours.",
                    style={'color': '#6366f1'}),
            create_file_selector(),
        ])
    ]))
