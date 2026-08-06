"""Minimal app that lists data files in a dropdown and shows a volume scatter plot.

All three callbacks share a single cached parquet read via
:mod:`options_radar_zero.parquet_cache`.  The ``get_cached_parquet`` function
reads the file, applies all transforms (minute-floor, volume diff, PUT sign
flip), and extracts derived values (unique strikes, latest underlying price)
in one shot.  The result is cached with mtime-based invalidation plus a
60-second TTL, so the file is read from disk exactly **once** per
invalidation window regardless of how many callbacks fire.
"""

from pathlib import Path
from typing import Any

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

from options_radar_zero.parquet_cache import get_cached_parquet, init_cache

# from options_radar_zero.config import config as orz_config

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
init_cache(app.server)


def get_parquet_options() -> list[dict[str, str]]:
    """Get list of parquet files for dropdown."""
    # files = sorted(Path(orz_config.DATA_DIR).glob("*.parquet"))
    files = sorted(Path("output").glob("*.parquet"))
    return [{"label": f.name, "value": str(f)} for f in files]


dropdown_options = get_parquet_options()

app.layout = html.Div(
    [
        html.H1("Options Data Files", style={"color": "#6366f1"}),
        html.P("Select a data file:"),
        dcc.Dropdown(
            id="file-selector",
            options=dropdown_options,
            value=dropdown_options[0]["value"] if dropdown_options else None,
            clearable=False,
        ),
        html.Div(id="file-info", style={"marginTop": "20px"}),
        dcc.Graph(id="volume-scatter"),
        html.Div(id="option-ladder", style={"marginTop": "30px"}),
    ],
    style={"padding": "20px"},
)


@app.callback(
    Output("file-info", "children"),
    Input("file-selector", "value"),
)
def show_file_info(filepath: str | None) -> Any:
    """Display file info when file is selected.

    The DataFrame is loaded and transformed seamlessly via
    :func:`get_cached_parquet` — no separate parquet reads needed for strike
    counts, call/put counts, or max date.
    """
    if not filepath:
        return html.P("No file selected.")

    cached = get_cached_parquet(filepath)
    df = cached.df
    max_date = df.processDateTime.max()
    calls = len(df[df.putCall == "CALL"])
    puts = len(df[df.putCall == "PUT"])

    return html.Div(
        [
            html.H3(filepath, style={"color": "#6366f1"}),
            html.P(f"Calls: {calls} Puts: {puts}"),
            html.H5(
                f"Underlying: {cached.latest_underlying_price} Max Date: {max_date}",
                style={"color": "#14b8a8", "marginTop": "10px"},
            ),
        ]
    )


@app.callback(
    Output("volume-scatter", "figure"),
    Input("file-selector", "value"),
)
def update_volume_scatter(filepath: str | None) -> go.Figure:
    """Update scatter plot when file is selected.

    The DataFrame is loaded, transformed, and cached in one call to
    :func:`get_cached_parquet` — the floor, volume-diff, and PUT-sign-flip
    transforms are applied seamlessly, and unique strikes + underlying price
    are extracted alongside it at no extra cost.
    """
    if not filepath:
        return go.Figure()

    cached = get_cached_parquet(filepath)
    df = cached.df
    underlying_price = cached.latest_underlying_price

    # Limit to 10 strikes on either side of underlyingPrice for plotting
    all_strikes = cached.unique_strikes
    lower_strikes = [s for s in all_strikes if s < underlying_price][-10:]
    upper_strikes = [s for s in all_strikes if s > underlying_price][:10]
    plot_strikes = set(lower_strikes + upper_strikes)
    df = df[df["strikePrice"].isin(plot_strikes)]

    fig = go.Figure()
    fig.update_layout(
        title="Option Volume Per Minute",
        xaxis_title="Time",
        yaxis_title="Volume",
    )
    fig.update_xaxes(tickformat="%H:%M")

    # Compute y-axis range from data to ensure all traces are visible
    max_vol = max(abs(df["volume"].max()), abs(df["volume"].min())) * 1.1 if len(df) > 0 else 100
    fig.update_yaxes(
        range=[-max_vol, max_vol],
        zeroline=True,
        zerolinewidth=2,
        zerolinecolor="white",
    )
    fig.update_layout(showlegend=True, legend_title_text="Symbol")

    # Each symbol gets its own series
    for symbol, subset in df.groupby("symbol"):
        fig.add_trace(
            go.Scatter(
                x=subset["processDateTime"],
                y=subset["volume"],
                mode="markers",
                name=symbol,
            )
        )

    return fig


def create_option_ladder(df: pd.DataFrame) -> Any:
    """Create an option ladder component showing 8 strikes around underlyingPrice.

    Layout spec:
    - 4 strikes below underlyingPrice (lower strikes)
    - 4 strikes above underlyingPrice (higher strikes)
    - Table headers: Ticker | Mark | Vol | OI | Strike
    - Calls on the left, puts on the right
    - Calls in green (#22c55e), puts in red (#ef4444)
    - underlyingPrice highlighted as central reference row
    """
    # Get the latest rows (max processDateTime)
    max_ts = df["processDateTime"].max()
    latest = df[df["processDateTime"] == max_ts].copy()

    # Get underlyingPrice from the latest timestamp
    underlying_price = latest["underlyingPrice"].iloc[0]

    # Get unique strikes sorted
    strikes = sorted(latest["strikePrice"].unique())

    # Find 4 strikes below and 4 above the underlying price
    lower_strikes = [s for s in strikes if s < underlying_price]
    upper_strikes = [s for s in strikes if s > underlying_price]
    lower_strikes = lower_strikes[-4:]  # closest 4 below
    upper_strikes = upper_strikes[:4]  # closest 4 above

    atm_exists = any(s == underlying_price for s in strikes)
    ladder_strikes = lower_strikes + [underlying_price] + upper_strikes if atm_exists else lower_strikes + upper_strikes

    # Helper to format individual cells
    def format_ticker(row):
        if row is None or len(row) == 0:
            return html.Td("--", style={"textAlign": "center", "fontSize": "0.8em", "color": "#666"})
        return html.Td(
            row["symbol"],
            style={"textAlign": "center", "fontSize": "0.65em", "color": "#666"},
        )

    def format_mark(row, is_call):
        if row is None or len(row) == 0:
            return html.Td("--", style={"textAlign": "center", "fontSize": "0.8em"})
        mark = f"{row['mark']:.3f}" if pd.notna(row["mark"]) else "--"
        color = "#22c55e" if is_call else "#ef4444"
        return html.Td(mark, style={"textAlign": "center", "fontSize": "0.8em", "color": color})

    def format_vol(row, is_call):
        if row is None or len(row) == 0:
            return html.Td("--", style={"textAlign": "center", "fontSize": "0.8em"})
        vol = int(row["totalVolume"]) if pd.notna(row["totalVolume"]) else 0
        color = "#22c55e" if is_call else "#ef4444"
        return html.Td(f"{vol:,}", style={"textAlign": "center", "fontSize": "0.8em", "color": color})

    def format_oi(row, is_call):
        if row is None or len(row) == 0:
            return html.Td("--", style={"textAlign": "center", "fontSize": "0.8em"})
        oi = int(row["openInterest"]) if pd.notna(row["openInterest"]) else 0
        color = "#22c55e" if is_call else "#ef4444"
        return html.Td(f"{oi:,}", style={"textAlign": "center", "fontSize": "0.8em", "color": color})

    def format_strike(strike, is_atm):
        color = "#6366f1" if is_atm else "#14b8a8"
        return html.Td(
            f"{strike:.1f}",
            style={"textAlign": "center", "fontWeight": "bold", "color": color, "fontSize": "0.8em"},
        )

    # Build table header
    header = html.Thead(
        html.Tr(
            [
                html.Th("Symbol", style={"textAlign": "center", "color": "#22c55e", "fontSize": "0.8em"}),
                html.Th("Mark", style={"textAlign": "center", "color": "#22c55e", "fontSize": "0.8em"}),
                html.Th("Vol", style={"textAlign": "center", "color": "#22c55e", "fontSize": "0.8em"}),
                html.Th("OI", style={"textAlign": "center", "color": "#22c55e", "fontSize": "0.8em"}),
                html.Th("Strike", style={"textAlign": "center", "color": "#6366f1", "fontSize": "0.8em"}),
                html.Th("OI", style={"textAlign": "center", "color": "#ef4444", "fontSize": "0.8em"}),
                html.Th("Vol", style={"textAlign": "center", "color": "#ef4444", "fontSize": "0.8em"}),
                html.Th("Mark", style={"textAlign": "center", "color": "#ef4444", "fontSize": "0.8em"}),
                html.Th("Symbol", style={"textAlign": "center", "color": "#ef4444", "fontSize": "0.8em"}),
            ]
        )
    )

    # Build ladder rows
    rows = []
    for strike in ladder_strikes:
        strike_calls = latest[(latest["strikePrice"] == strike) & (latest["putCall"] == "CALL")]
        strike_puts = latest[(latest["strikePrice"] == strike) & (latest["putCall"] == "PUT")]

        call_row = strike_calls.iloc[0] if len(strike_calls) > 0 else None
        put_row = strike_puts.iloc[0] if len(strike_puts) > 0 else None

        is_atm = strike == underlying_price
        row_style = {"backgroundColor": "#1e293b"} if is_atm else {}

        rows.append(
            html.Tr(
                [
                    format_ticker(call_row),
                    format_mark(call_row, is_call=True),
                    format_vol(call_row, is_call=True),
                    format_oi(call_row, is_call=True),
                    format_strike(strike, is_atm),
                    format_oi(put_row, is_call=False),
                    format_vol(put_row, is_call=False),
                    format_mark(put_row, is_call=False),
                    format_ticker(put_row),
                ],
                style=row_style,
            )
        )

    table = dbc.Table(
        [header, html.Tbody(rows)],
        bordered=False,
        striped=False,
        hover=False,
        responsive=True,
    )

    last_trade_time = latest["processDateTime"].iloc[0]
    return html.Div(
        [
            html.H4(
                f"Option Ladder  |  Underlying: ${underlying_price:.2f} @ {last_trade_time}",
                style={"color": "#6366f1", "textAlign": "center"},
            ),
            table,
        ],
        style={"marginTop": "15px"},
    )


@app.callback(
    Output("option-ladder", "children"),
    Input("file-selector", "value"),
)
def update_option_ladder(filepath: str | None) -> Any:
    """Update option ladder when file is selected.

    The DataFrame is loaded, transformed, and cached seamlessly via
    :func:`get_cached_parquet`.
    """
    if not filepath:
        return html.P("No file selected.")

    cached = get_cached_parquet(filepath)
    df = cached.df
    return create_option_ladder(df)


if __name__ == "__main__":
    app.run(debug=True, port=8050)
