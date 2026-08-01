# Options Radar Zero

Real-time 0DTE option chain monitoring for SPX, SPY, and ES.

![Screenshot](images/demo.gif)

SPX:
![Screenshot](images/demo4.gif)

## Setup

```bash
uv sync
```

Create a `.env` file with Tastytrade OAuth credentials:

```ini
TT_REFRESH=your_refresh_token
TT_SECRET=your-secret
```

## Development

```bash
make lint      # ruff check
make typecheck # mypy
make test      # pytest
make run       # Start dashboard
```

### Poller

Create a `.env` file with Tastytrade OAuth credentials (see Setup above).

Create a YAML config file:

```yaml
# poller_config.yaml
output_dir: ./output
symbols:
  - symbol: SPY
    strikes: 40
  - symbol: QQQ
    strikes: 40
  - symbol: SPX
    strikes: 30
  - symbol: ES
    strikes: 20
```

Run the poller:
```bash
make poller
# or
uv run python -m options_radar_zero.poller.cli --config examples/poller_config.yaml
```

A sample config is provided at `examples/poller_config.yaml`.

## Project Structure

Based on the refactored modular structure — a tested, CI-ready codebase:

| Module | Responsibility |
|--------|---------------|
| `app.py` | Thin Bootstrap |
| `app_factory.py` | `create_app()` Factory |
| `routes.py` | Flask Routes + Downloads |
| `callbacks.py` | Dash Callback Registration |
| `callback_state.py` | `ChartState` Dataclass |
| `layouts.py` | UI Component Factories |
| `visualization.py` | Plotly Chart Functions |
| `data_processing.py` | Pure Data Transformations |
| `thinkscript.py` | ThinkScript Template Rendering |
| `market_hours.py` | Market Hours + Intervals |
| `config.py` | `AppConfig` + Constants |
| `data_loader.py` | `DataLoader` Class |
| `utils.py` | Slimmed `OptionQuotes` |
| `tastytrade_api.py` | Tastytrade API Wrapper |
| `poller/` | 0DTE Data Poller (CLI) |

## CI

GitHub Actions runs `ruff`, `mypy`, and `pytest` (95% coverage threshold) on Python 3.11–3.14.
