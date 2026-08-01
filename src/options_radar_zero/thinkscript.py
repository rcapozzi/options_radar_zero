"""Thinkscript template rendering for 0DTE options."""
from datetime import datetime, timedelta

from jinja2 import Template

try:
    import yfinance as yf
except ImportError:
    yf = None


# Load template from file
def get_thinkscript_template() -> Template:
    """Load and return the Jinja2 template."""
    template_path = __file__.replace('thinkscript.py', 'templates/thinkscript_template.j2')
    with open(template_path) as f:
        template_content = f.read()
    return Template(template_content)  # type: ignore[no-any-return]


def get_strike_prices(price: float) -> list[int]:
    """Calculate strike prices around the underlying price."""
    if price > 1000:
        price = round(price / 5) * 5
        return [int(price - i) for i in range(100, -106, -5)]
    else:
        return [int(price - i) for i in range(5, -6, -1)]


def format_expiration_date(dt: datetime) -> str:
    """Format datetime for option expiration code."""
    if dt.hour >= 16:
        dt = dt + timedelta(days=1)
    return dt.strftime("%y%m%d")


def tos_ts_0dte(symbol: str = 'SPY') -> str:
    """Generate thinkscript for SPY 0DTE options.

    Args:
        symbol: Underlying symbol (SPY, SPX, etc.)

    Returns:
        Rendered thinkscript code
    """
    if yf is None:
        raise ImportError("yfinance is required for tos_ts_0dte")

    from options_radar_zero.market_hours import EasternDT

    yf_symbol = '^GSPC' if symbol == 'SPX' else symbol
    display_symbol = 'SPXW' if symbol == 'SPX' else symbol

    quote = yf.Ticker(yf_symbol)
    price = quote.history(period="1d").iloc[-1]['Close']

    strike_prices = get_strike_prices(price)
    expiration_date = format_expiration_date(EasternDT.now())

    call_codes = [f"{display_symbol}{expiration_date}C{sp}" for sp in strike_prices]
    put_codes = [f"{display_symbol}{expiration_date}P{sp}" for sp in strike_prices]

    template = get_thinkscript_template()
    return template.render(call_codes=call_codes, put_codes=put_codes)


