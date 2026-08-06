from pathlib import Path
from typing import Any

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

#from options_radar_zero.config import config

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.layout = html.Div([
    html.H1("Options Data Files", style={"color": "#6366f1"}),
    dcc.Graph(id="volume-scatter"),
], style={"padding": "20px"})


def get_parquet_options() -> list[dict[str, str]]:
    """Get list of parquet files for dropdown."""
    files = sorted(Path(config.DATA_DIR).glob("*.parquet"))
    return [
        {"label": f.name, "value": str(f)}
        for f in files
    ]

@app.callback(
    Output("volume-scatter", "figure"),
)
def update_volume_scatter() -> go.Figure:
    y = np.random.randint(1, 50, 20)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=list(range(20)), y=y, mode="markers")
    )
    return fig
if __name__ == "__main__":
    app.run(debug=True, port=8050)
