"""SPX 0DTE Option Chain Analytics Dashboard.

Thin bootstrap entry point. All application logic lives in the modular
submodules: app_factory, config, data_loader, routes, callbacks, layouts,
visualization, data_processing, thinkscript, market_hours, utils.
"""
from options_radar_zero.app_factory import create_app

app = create_app()
server = app.server

if __name__ == '__main__':
    app.logger.info("Dash app starting")
    app.run(debug=True, host='0.0.0.0', port=8050)
