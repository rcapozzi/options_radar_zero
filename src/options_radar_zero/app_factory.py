"""Application factory for the Dash app.

Creates and configures the Dash application instance with all modules wired together.
"""
from __future__ import annotations

import datetime
import warnings

import pytz
from dash import Dash, html

from options_radar_zero.callbacks import setup_callbacks
from options_radar_zero.data_loader import DataLoader
from options_radar_zero.layouts import create_main_layout
from options_radar_zero.routes import register_routes

warnings.simplefilter(action='ignore', category=UserWarning)


def create_app() -> Dash:
    """Create and configure the Dash application.

    Returns:
        Configured Dash application instance.
    """
    # External stylesheets
    external_stylesheets = [
        {
            "href": "https://fonts.googleapis.com/css2?family=Lato:wght@400;700&display=swap",
            "rel": "stylesheet",
        }
    ]

    app = Dash(
        __name__,
        external_stylesheets=external_stylesheets,
        suppress_callback_exceptions=True,
    )
    app.title = 'SPX 0DTE Chain React Analytics Peaker'

    # Initialize data loader
    data_loader = DataLoader()
    data_loaded = data_loader.load()

    # Set up layout
    if data_loaded:
        app.layout = create_main_layout(data_loader.symbols)
    else:
        app.layout = html.Div([
            html.Hr(),
            html.H1("You filthy Degen. Check back during market hours."),
            html.Span("Error loading data", style={'padding': '5px', 'fontsize:': '10px'}),
        ])

    # Register Flask routes
    register_routes(app, data_loader)

    # Register Dash callbacks
    setup_callbacks(app, data_loader)

    # Attach data_loader for backward compatibility (some code may reference app.data_loader)
    app.data_loader = data_loader  # type: ignore[attr-defined]

    return app


def get_app_info() -> str:
    """Return startup info string."""
    return f"Dash app starting {datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))}"
