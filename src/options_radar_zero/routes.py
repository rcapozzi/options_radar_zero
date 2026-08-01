"""Flask route handlers for the Dash application.

All Flask routes are registered via ``register_routes(app, data_loader)``.
This separates HTTP endpoint logic from the Dash app bootstrap.
"""
from __future__ import annotations

import io
from typing import Any

from dash import Input, Output, State, dcc
from flask import make_response, request, send_file, send_from_directory

from options_radar_zero.data_loader import DataLoader
from options_radar_zero.market_hours import EasternDT
from options_radar_zero.thinkscript import tos_ts_0dte


def register_routes(app: Any, data_loader: DataLoader) -> None:
    """Register all Flask routes on the Dash app's server.

    Args:
        app: The Dash application instance.
        data_loader: The DataLoader instance providing option quotes data.
    """

    @app.server.route('/data/raw/<symbol>')
    def serve_data_raw_file(symbol: str) -> Any:
        """Serve raw parquet file for download."""
        oq = data_loader.get(symbol)
        response = make_response(send_file(oq.filename))
        response.headers['Content-Disposition'] = f'attachment; filename="{symbol}.parquet"'
        return response

    @app.server.route('/static/<path:path>')
    def serve_static(path: str) -> Any:
        """Serve static files with caching."""
        response = send_from_directory('static', path)
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response

    @app.server.route('/tos/0dte/<symbol>')
    def serve_thinkscript(symbol: str) -> str:
        """Serve thinkscript for 0DTE options."""
        return f'<pre>{tos_ts_0dte(symbol)}</pre>'

    @app.server.route('/data/<symbol>')
    def serve_data_file(symbol: str) -> Any:
        """Serve incremental parquet data."""
        u_val = request.args.get('u')
        max_dt = EasternDT.u2e(float(u_val) if u_val else 0)
        oq = data_loader.get(symbol)
        df = oq.reload()

        parquet_data = io.BytesIO()
        df[(df.processDateTime > max_dt)].to_parquet(parquet_data)
        parquet_data.seek(0)

        response = make_response(
            send_file(parquet_data, mimetype='application/octet-stream',
                      as_attachment=True, download_name=f"{symbol}.parquet")
        )
        return response

    # Download callbacks
    @app.callback(
        Output("download-dataframe-parquet", "data"),
        Input("btn_parquet", "n_clicks"),
        State("symbol", "value"),
        prevent_initial_call=True,
    )
    def download_parquet(n_clicks: int, symbol: str) -> Any:
        """Handle parquet download request."""
        oq = data_loader.get(symbol)
        return dcc.send_file(oq.filename)  # type: ignore[attr-defined]

    @app.callback(
        Output("download-dataframe-csv", "data"),
        Input("btn_csv", "n_clicks"),
        State("symbol", "value"),
        prevent_initial_call=True,
    )
    def download_csv(n_clicks: int, symbol: str) -> Any:
        """Handle CSV download request."""
        import os
        oq = data_loader.get(symbol)
        csv_filename = oq.filename.replace(".parquet", ".csv.gz")

        if os.path.exists(csv_filename):
            return dcc.send_file(csv_filename)
        else:
            return dcc.send_data_frame(oq.reload().to_csv, f'{symbol}.csv', index=False)
