"""Visualization module - Plotly chart creation functions.

All functions are pure: they take DataFrames and return Plotly Figures.
No Dash/Flask dependencies, no I/O, no global state.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from options_radar_zero.config import config
from options_radar_zero.data_processing import prepare_chart_data


def create_strike_volume_chart(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    strikes_df: pd.DataFrame,
    underlying_price: int,
    net_gex_price: float,
    datetime_str: str,
) -> go.Figure:
    """Create strike volume bar chart.

    Args:
        calls: Calls dataframe with strike/price data.
        puts: Puts dataframe with strike/price data.
        strikes_df: Aggregated strikes dataframe.
        underlying_price: Current underlying price level.
        net_gex_price: Calculated net GEX breakeven.
        datetime_str: Formatted datetime string for title.

    Returns:
        Plotly Figure with strike volume visualization.
    """
    fig = go.Figure(
        layout=go.Layout(
            title=go.layout.Title(text=f"Total Volume {datetime_str}"),
            barmode='overlay',
        )
    )

    fig.update_layout(
        barmode='overlay',
        yaxis_title='Strike Price',
        legend=dict(yanchor="bottom", y=1.05, xanchor="right", x=1, orientation="h"),
        margin=config.CHART_MARGIN,
        template=config.CHART_TEMPLATE,
    )
    fig.update_yaxes(autorange="reversed")
    fig.add_vline(x=0, line_color='black')
    fig.add_hline(
        y=underlying_price,
        line_color='black',
        line_dash='dot',
        annotation_text=f'SPX {underlying_price}',
    )
    fig.add_hline(
        y=net_gex_price,
        line_color=config.COLORS['gex_orange'],
        line_dash='solid',
        annotation_text=f'Secret {int(net_gex_price)}',
        annotation_position='top left',
    )

    xaxis = 'totalVolume'
    fig.add_trace(
        go.Bar(
            x=calls[xaxis], y=calls.strikePrice, name='calls',
            orientation='h', marker_color=config.COLORS['call'],
        )
    )
    fig.add_trace(
        go.Bar(
            x=puts[xaxis], y=puts.strikePrice, name='puts',
            orientation='h', marker_color=config.COLORS['put'],
        )
    )
    fig.add_trace(
        go.Bar(
            x=strikes_df.totalVolume, y=strikes_df.strikePrice,
            name='Net', orientation='h', marker_color=config.COLORS['net'], width=0.75,
        )
    )

    xmax = float(calls[xaxis].abs().max())
    xmax = math.ceil(xmax / 100) * 100 + 100
    fig.update_xaxes(range=[-xmax, xmax])

    return fig


def create_mark_comparison_chart(
    df: pd.DataFrame,
    underlying_price: int,
    datetime_str: str,
) -> go.Figure:
    """Create mark comparison chart with buy/sell signals.

    Args:
        df: Options dataframe with volume/mark data.
        underlying_price: Current underlying price level.
        datetime_str: Formatted datetime string for title.

    Returns:
        Plotly Figure with mark comparison visualization.
    """
    fig = go.Figure(
        layout=go.Layout(
            title=go.layout.Title(text="Prior One Minute Volume"),
            barmode='overlay',
        )
    )
    fig.update_layout(
        legend=dict(yanchor="bottom", y=1.05, xanchor="right", x=1, orientation="h"),
        margin=config.CHART_MARGIN,
        template=config.CHART_TEMPLATE,
    )
    fig.update_yaxes(autorange="reversed")

    fig.add_vline(x=0, line_color='black', line_dash='dot')
    fig.add_hline(
        y=underlying_price,
        line_color='black',
        line_dash='dot',
        annotation_text=f'SPX {underlying_price}',
    )

    m0 = (df.volume > df.sma5) & (df.sma5 > df.sma15) & (df.volume > 0) & (df.mark > 0.25)
    m1 = (df.volume < df.sma5) & (df.sma5 < df.sma15) & (df.volume < 0) & (df.mark > 0.25)

    for _, row in df[(m0) | (m1)].iterrows():
        action = 'Buy' if row.markDiff > 0 else 'Sell'
        fig.add_annotation(
            text=f"{action} {row.strikePrice:.0f}@{row.mark:.2f}",
            x=row.volume, y=row.strikePrice,
            arrowhead=1, showarrow=True,
        )

    return fig


def create_gex_chart(
    df: pd.DataFrame,
    symbol: str,
    mode: int = 0,
) -> go.Figure:
    """Create GEX chart (gamma exposure).

    Args:
        df: Options dataframe.
        symbol: Symbol for title.
        mode: 0 for GEX total volume, 1 for cumsum mark*volume.

    Returns:
        Plotly Figure with GEX visualization.
    """
    data = df.copy()

    if mode == 0:
        title = "Gamma Total Volume"
        data['gexTV'] = data['totalVolume'] * data.gamma.abs()
        data.loc[(data.putCall == 'CALL'), 'gexTV'] *= -1
    else:
        title = "CumSum Mark*Volume"
        data['gexTV'] = data.volume * data.mark
        data['gexTV'] = data.groupby('symbol').gexTV.cumsum()
        data.loc[(data.putCall == 'CALL'), 'gexTV'] *= -1

    max_dt = data.processDateTime.max()
    dt = max_dt.strftime('%Y-%m-%d %H:%M')
    prior_dt = max_dt - pd.Timedelta(minutes=10)

    df_prior = data[(data.processDateTime == prior_dt) & (data.gexTV.abs() > 5)]
    df_current = data[(data.processDateTime == max_dt) & (data.gexTV.abs() > 5)]

    strikes_df = df_current.groupby(['strikePrice']).agg({'gexTV': sum}).reset_index()
    underlyingPrice = int(df_current.underlyingPrice.mean())
    gamma_flip = int((strikes_df.strikePrice * strikes_df.gexTV.abs()).sum() / (strikes_df.gexTV.abs().sum()))

    fig = go.Figure(
        layout=go.Layout(
            title=go.layout.Title(text=f"{title} {dt}"),
            barmode='overlay',
        )
    )
    fig.update_layout(
        barmode='overlay',
        yaxis_title='Strike Price',
        legend=dict(yanchor="bottom", y=1.05, xanchor="right", x=1, orientation="h"),
        margin=config.CHART_MARGIN,
        template=config.CHART_TEMPLATE,
    )
    fig.update_yaxes(autorange="reversed")

    fig.add_vline(x=0, line_color='black')
    fig.add_hline(
        y=underlyingPrice,
        line_color=config.COLORS['spx_price'],
        line_dash='dot',
        annotation_text=f'SPX {underlyingPrice}',
        annotation_font_color=config.COLORS['spx_price'],
    )
    fig.add_hline(
        gamma_flip,
        line_color='white',
        line_dash='dash',
        annotation_text=f"Breakeven {gamma_flip}",
        annotation_position='top left',
        annotation_font_color='black',
    )

    puts = df_current[(df_current.putCall == 'PUT')]
    calls = df_current[(df_current.putCall == 'CALL')]

    fig.add_trace(
        go.Bar(
            y=calls.strikePrice, x=calls.gexTV, name='Call',
            orientation='h', marker_color=config.COLORS['call'],
        )
    )
    fig.add_trace(
        go.Bar(
            y=puts.strikePrice, x=puts.gexTV, name='Puts',
            orientation='h', marker_color=config.COLORS['put'],
        )
    )
    fig.add_trace(
        go.Bar(
            y=strikes_df.strikePrice, x=strikes_df.gexTV,
            name='Net', width=1, marker_color=config.COLORS['net'],
            orientation='h',
        )
    )
    fig.add_trace(
        go.Scatter(
            y=df_prior.strikePrice, x=df_prior.gexTV,
            name='Lag10', mode='markers',
        )
    )

    xmax = float(df_current.gexTV.abs().max())
    fig.update_xaxes(range=[-xmax, xmax])

    return fig


def create_pez_dispenser_chart(
    df: pd.DataFrame,
    strikes: tuple[float, float],
    yaxis: str,
    xaxis: str,
    title: str | None = None,
) -> tuple[dict[str, Any], go.Figure]:
    """Create the main pez dispenser chart.

    Args:
        df: Options dataframe.
        strikes: Tuple of (min_strike, max_strike).
        yaxis: Y-axis field name.
        xaxis: X-axis field name.
        title: Optional chart title prefix.

    Returns:
        Tuple of (state dict, Plotly Figure).
    """
    if df is None or df.empty:
        return {}, go.Figure()

    # Use pure data preparation function instead of inline logic
    data = prepare_chart_data(df, xaxis, yaxis, strikes)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    hovertemplate = '<br>'.join([
        '%{fullData.name}',
        xaxis + '=%{x}',
        yaxis + '=%{y}',
        'mark=%{customdata}',
        '<extra></extra>',
    ])

    mode = 'lines' if xaxis == 'processDateTime' and yaxis == 'gex' else 'markers'

    if xaxis == 'strikePrice':
        data = data[(df.processDateTime == data.processDateTime.max())]
        data['color'] = config.COLORS['call']

        puts = data['putCall'] == 'PUT'
        data.loc[puts, 'totalVolume'] *= -1
        data.loc[puts, 'volume'] *= -1
        data.loc[puts, 'color'] = config.COLORS['put']
        data['totalVolumeGamma'] = data.totalVolume * data.gamma

        for callPut in ['CALL', 'PUT']:
            df2 = data[data['putCall'] == callPut]
            fig.add_trace(
                go.Bar(
                    x=df2[xaxis], y=df2[yaxis], marker_color=df2.color,
                    name=callPut, customdata=df2.mark,
                    texttemplate="%{x}<br>%{customdata}", textposition="auto",
                )
            )

        fig.update_layout(barmode='relative')
    else:
        data['y'] = data[yaxis] * data['sign']
        symbols = data.symbol.sort_values().unique()

        for s in symbols:
            filter_df = data[(data.symbol == s)]
            x = filter_df[xaxis]
            y = filter_df['y']
            cd = filter_df.mark
            s0 = filter_df.iloc[0]
            name = f'{int(s0.strikePrice)}{s0.putCall[0]}'
            fig.add_trace(
                go.Scatter(
                    x=x, y=y, customdata=cd, name=name,
                    mode=mode, hovertemplate=hovertemplate,
                ),
                secondary_y=False,
            )

    if xaxis == 'processDateTime':
        ul = df.groupby('processDateTime').underlyingPrice.mean()
        fig.add_trace(
            go.Scatter(
                x=ul.index, y=ul, name="underlyingPrice",
                marker_color=config.COLORS['underlying_price'],
            ),
            secondary_y=True,
        )

    fig['layout']['yaxis']['showgrid'] = False
    fig.update_yaxes(title_text="<b>underlyingPrice</b>", secondary_y=True, showgrid=True)

    if xaxis == 'processDateTime':
        fig.update_xaxes(tickformat="%H:%M")

    fig.update_layout(
        title_text=f'SPX Call/Put Pez Dispenser {title} {yaxis}',
        template=config.CHART_TEMPLATE,
        height=config.CHART_HEIGHT,
    )

    state: dict[str, Any] = {
        'names': [row['name'] for row in fig["data"]],
        'max_dt': df.processDateTime.max(),
        'strikes': list(strikes),
        'yaxis': yaxis,
        'xaxis': xaxis,
    }

    return state, fig
