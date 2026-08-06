"""Standalone demo: SPY 0-DTE option-chain volume per minute, by symbol.

Reads the cached SPY chain parquet with ``get_cached_parquet`` — a single
mtime-cached read that applies the minute-floor / volume-diff / PUT-sign-flip
transforms — then plots *volume* vs *processDateTime* with one Plotly trace
per option ``symbol``.

A second figure plots *open interest* (static for the trading day) as a bar
chart — one bar per symbol for all symbols, where x = strikePrice and
y = openInterest.  Put open interest is negated so puts appear below the
zero line, and a vertical line marks the day's opening underlying price.

Run::

    uv run python demo.py

Then open http://127.0.0.1:8050 in your browser.

Note
----
Importing :mod:`options_radar_zero.parquet_cache` triggers the package
``__init__``.  The global ``warnings.simplefilter("ignore", UserWarning)``
that *used* to live there was moved into ``create_app()`` (see
``app_factory.py``), so this deliberately-standalone module — which does *not*
call ``create_app`` — leaves Python's default warning behaviour intact.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html

from options_radar_zero.parquet_cache import get_cached_parquet, init_cache

# --------------------------------------------------------------------------- #
# Dark theme (existing design tokens)
# --------------------------------------------------------------------------- #
BG_COLOR = "#0b0d10"  # page / plot background
PRIMARY = "#6366f1"  # indigo — titles, axis labels, call traces
ACCENT = "#14b8a6"  # teal   — axis lines, grids, puts, zero line
FONT_COLOR = "#e2e8f0"  # readable slate on the dark background
GRID_COLOR = "rgba(20, 184, 166, 0.15)"  # faint teal gridlines (#14b8a6 @15%)
ZERO_LINE_COLOR = "rgba(20, 184, 166, 0.6)"  # stronger teal zero line

# The on-disk chain file written by the poller.
PARQUET_FILE = "output/SPY.20260805.chain.parquet"

app = Dash(__name__)
# Bind the in-process SimpleCache to this app so cache-clearing hooks are
# registered.  (No-op otherwise — SimpleCache is shared in-process, but this
# mirrors the pattern in mini_app.py.)
init_cache(app.server)


def _shared_layout() -> dict:
    """Return common layout kwargs for both figures (DRY dark theme)."""
    return dict(
        plot_bgcolor=BG_COLOR,
        paper_bgcolor=BG_COLOR,
        font=dict(color=FONT_COLOR),
        hoverlabel=dict(
            bgcolor=BG_COLOR,
            font=dict(color=FONT_COLOR, size=12),
            bordercolor=GRID_COLOR,
        ),
        modebar=dict(color=FONT_COLOR, activecolor=PRIMARY),
        legend=dict(
            title="Symbol",
            title_font=dict(color=ACCENT),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=FONT_COLOR),
        ),
        margin=dict(l=60, r=20, t=50, b=40),
        height=650,
    )


def create_figure() -> go.Figure:
    """Build the volume-vs-time figure with one trace per option symbol.

    ``get_cached_parquet`` reads the file once and caches the result (mtime
    signature + 60 s TTL), applying the minute-floor / volume-diff /
    PUT-sign-flip transforms.  The only further prep here is collapsing
    duplicate ``(symbol, minute)`` records — feed artefacts that share a
    process time but differ only in ``underlyingPrice`` — so each trace has a
    single volume sample per minute.
    """
    cached = get_cached_parquet(PARQUET_FILE)
    df = cached.df

    per_minute = (
        df.groupby(["symbol", "processDateTime"], as_index=False)
        .agg(volume=("volume", "sum"))
        .sort_values(["symbol", "processDateTime"])
    )

    # putCall is constant per symbol — look it up once for colouring.
    put_call_by_symbol: pd.Series = df[["symbol", "putCall"]].drop_duplicates("symbol").set_index("symbol")["putCall"]

    fig = go.Figure()
    for symbol, subset in per_minute.groupby("symbol", sort=True):
        is_call = put_call_by_symbol.loc[symbol] == "CALL"
        fig.add_trace(
            go.Scatter(
                x=subset["processDateTime"],
                y=subset["volume"],
                mode="markers",
                name=symbol,
                line=dict(
                    color=PRIMARY if is_call else ACCENT,
                    width=1.4,
                ),
                opacity=0.85,
                hovertemplate=("<b>%{fullData.name}</b><br>time=%{x|%H:%M:%S}<br>volume=%{y:,.0f}<extra></extra>"),
            )
        )

    # A zero line makes the negative (put) volumes read as clearly as the
    # positive (call) ones above it.
    fig.add_hline(y=0, line_width=1, line_dash="solid", line_color=ZERO_LINE_COLOR)

    max_vol = 25_000
    fig.update_layout(
        title=dict(
            text="SPY Option Volume Per Minute — by Symbol",
            font=dict(color=PRIMARY, size=18),
        ),
        xaxis_title="Process Time (minute)",
        xaxis_title_font=dict(color=PRIMARY),
        yaxis_title="Volume",
        yaxis_title_font=dict(color=PRIMARY),
        yaxis_range=[-max_vol, max_vol],
        xaxis=dict(
            gridcolor=GRID_COLOR,
            zerolinecolor=ZERO_LINE_COLOR,
            zerolinewidth=1,
            tickformat="%H:%M",
            tickfont=dict(color=FONT_COLOR),
        ),
        yaxis=dict(
            gridcolor=GRID_COLOR,
            zerolinecolor=ZERO_LINE_COLOR,
            zerolinewidth=1,
            zeroline=True,
            tickfont=dict(color=FONT_COLOR),
        ),
        **_shared_layout(),
    )
    return fig


def create_oi_figure() -> go.Figure:
    """Build the open-interest bar chart for all symbols.

    Open interest is static for the entire trading day, so we take a single
    ``(symbol, putCall, strikePrice, openInterest)`` record per symbol by
    dropping duplicates.  All symbols are shown (no top-20% filter).  Put open
    interest is negated so calls appear above the zero line and puts below,
    making the call/put skew immediately visible.

    A horizontal line at y=0 separates calls from puts.  A vertical line marks
    the opening underlying price (the ``underlyingPrice`` at
    ``min(processDateTime)``), giving a reference point on the strike axis.

    The resulting figure uses :class:`go.Bar` — one bar per symbol with
    x = ``strikePrice`` and y = ``openInterest`` — coloured indigo for calls
    and teal for puts, on the same dark theme as the volume figure.
    """
    cached = get_cached_parquet(PARQUET_FILE)
    df = cached.df

    # Open interest is static for the trading day — collapse to one row per
    # symbol.  We keep putCall + strikePrice + openInterest.
    oi_df = (
        df[["symbol", "putCall", "strikePrice", "openInterest"]].drop_duplicates(subset=["symbol"], keep="first").copy()
    )

    # Negate put open interest so puts appear below the zero line.
    oi_df.loc[oi_df["putCall"] == "PUT", "openInterest"] = -oi_df.loc[oi_df["putCall"] == "PUT", "openInterest"]

    # Opening underlying price = underlyingPrice at min(processDateTime).
    min_dt = df["processDateTime"].min()
    opening_price = float(df.loc[df["processDateTime"] == min_dt, "underlyingPrice"].iloc[0])

    # Separate call and put bars so we can colour them differently.
    call_df = oi_df[oi_df["putCall"] == "CALL"].sort_values("strikePrice")
    put_df = oi_df[oi_df["putCall"] == "PUT"].sort_values("strikePrice")

    fig = go.Figure()

    if len(call_df) > 0:
        fig.add_trace(
            go.Bar(
                x=call_df["strikePrice"],
                y=call_df["openInterest"],
                name="Calls",
                marker_color=PRIMARY,
                hovertemplate=("<b>Call %{x}</b><br>open_interest=%{y:,.0f}<extra></extra>"),
            )
        )

    if len(put_df) > 0:
        fig.add_trace(
            go.Bar(
                x=put_df["strikePrice"],
                y=put_df["openInterest"],
                name="Puts",
                marker_color=ACCENT,
                hovertemplate=("<b>Put %{x}</b><br>open_interest=%{y:,.0f}<extra></extra>"),
            )
        )

    # Horizontal line at y=0 — separates calls (above) from puts (below).
    fig.add_hline(y=0, line_width=1, line_dash="solid", line_color=ZERO_LINE_COLOR)

    # Vertical line at the opening underlying price.
    fig.add_vline(
        x=opening_price,
        line_width=1.5,
        line_dash="dash",
        line_color=FONT_COLOR,
        annotation_text=f"Open: {opening_price:,.1f}",
        annotation_position="top left",
        annotation_font=dict(color=FONT_COLOR, size=11),
    )

    # Title includes the date/time of the data (opening snapshot).
    oi_title = f"SPY Open Interest — All Symbols ({min_dt.strftime('%Y-%m-%d %H:%M')})"

    fig.update_layout(
        title=dict(
            text=oi_title,
            font=dict(color=PRIMARY, size=18),
        ),
        xaxis_title="Strike Price",
        xaxis_title_font=dict(color=PRIMARY),
        yaxis_title="Open Interest (calls +, puts −)",
        yaxis_title_font=dict(color=PRIMARY),
        xaxis=dict(
            gridcolor=GRID_COLOR,
            zerolinecolor=GRID_COLOR,
            zerolinewidth=1,
            tickfont=dict(color=FONT_COLOR),
        ),
        yaxis=dict(
            gridcolor=GRID_COLOR,
            zerolinecolor=GRID_COLOR,
            zerolinewidth=1,
            zeroline=True,
            tickfont=dict(color=FONT_COLOR),
        ),
        barmode="overlay",
        **_shared_layout(),
        annotations=[
            dict(
                text=(
                    "Each bar = one option symbol's open interest at its strike. "
                    "Calls are indigo (#6366f1, above zero), puts are teal "
                    f"(#14b8a6, below zero — negated). The dashed line marks "
                    f"today's opening price ({opening_price:.1f})."
                ),
                xref="paper",
                yref="paper",
                x=0,
                y=-0.18,
                showarrow=False,
                font=dict(color=FONT_COLOR, size=11),
                align="left",
            )
        ],
    )
    return fig


app.layout = html.Div(
    [
        html.H1(
            "SPY Chain Volume — by Symbol",
            style={"color": PRIMARY, "marginBottom": "12px"},
        ),
        html.P(
            f"Source: {PARQUET_FILE}  ·  cached (mtime + 60s TTL)",
            style={
                "color": FONT_COLOR,
                "marginBottom": "8px",
                "fontSize": "0.9em",
            },
        ),
        dcc.Graph(id="volume-by-symbol", figure=create_figure()),
        html.H2(
            "Open Interest — All Symbols",
            style={"color": PRIMARY, "marginBottom": "8px", "marginTop": "24px"},
        ),
        html.P(
            "Bar chart of open interest per strike for all symbols. "
            "Calls (indigo, above zero) and puts (teal, below zero — negated). "
            "The dashed line marks today's opening price.",
            style={
                "color": FONT_COLOR,
                "marginBottom": "16px",
                "fontSize": "0.9em",
            },
        ),
        dcc.Graph(id="oi-by-symbol", figure=create_oi_figure()),
    ],
    style={"backgroundColor": BG_COLOR, "padding": "20px"},
)


if __name__ == "__main__":
    app.run(debug=True, port=8050)
