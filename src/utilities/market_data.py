
from datetime import datetime, timedelta
from dateutil import tz
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.data.historical.stock import StockHistoricalDataClient, StockLatestTradeRequest
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import Adjustment
NY_TZ = ZoneInfo('America/New_York')

# Helper: Fetch recent bar data  
def fetch_bars(client: StockHistoricalDataClient, underlying_symbol: str, timeframe: TimeFrame, amount: int = 90) -> pd.DataFrame:
    right_now = datetime.now(tz.UTC)
    req = StockBarsRequest(
        symbol_or_symbols=[underlying_symbol],
        adjustment = Adjustment.SPLIT,
        timeframe = timeframe,  # specify timeframe
        start = right_now - timedelta(minutes = amount),             # specify start datetime, default=the beginning of the current day.
    )
    ticker_data = client.get_stock_bars(req)
    ticker_data_df = ticker_data.df.reset_index().drop(columns="symbol")
    return ticker_data_df

def update_bars(client: StockHistoricalDataClient, underlying_symbol: str, timeframe: TimeFrame, start_date_time) -> pd.DataFrame:
    req = StockBarsRequest(
        symbol_or_symbols=[underlying_symbol],
        adjustment = Adjustment.SPLIT,
        timeframe = timeframe,  # specify timeframe
        start = start_date_time)
    ticker_data = client.get_stock_bars(req)
    ticker_data_df = ticker_data.df.reset_index().drop(columns="symbol")
    return ticker_data_df

# def fetch_bars(client: StockHistoricalDataClient, underlying_symbol: str, timeframe: TimeFrame, days: int = 5) -> pd.DataFrame:
#     """
#     Fetch OHLCV bars for `underlying_symbol` going back `days` calendar days.

#     Args:
#         client:             Alpaca StockHistoricalDataClient
#         underlying_symbol:  Ticker symbol (e.g. 'MU')
#         timeframe:          TimeFrame object (e.g. TimeFrame(1, TimeFrameUnit.Minute))
#         days:               Calendar days to look back from now.
#                             Use enough days to warm up your longest indicator.
#                             See module docstring for the rule of thumb.

#     Returns:
#         pd.DataFrame with columns: open, high, low, close, volume (MultiIndex
#         [symbol, timestamp] as returned by alpaca-py).
#     """
#     right_now = datetime.now(NY_TZ)
#     req = StockBarsRequest(
#         symbol_or_symbols=[underlying_symbol],
#         adjustment=Adjustment.SPLIT,
#         timeframe=timeframe,
#         start=right_now - timedelta(days=days),
#     )
#     df = client.get_stock_bars(req).df

#     # Drop the symbol level of the MultiIndex so callers can do df.close directly
#     if isinstance(df.index, pd.MultiIndex):
#         df = df.droplevel(0)

#     return df

# Helper: Get the latest price of the underlying stock
def get_underlying_price(symbol: str, stock_data_client: StockHistoricalDataClient) -> float:
    """Return the most recent trade price for `symbol`."""
    req  = StockLatestTradeRequest(symbol_or_symbols=symbol)
    resp = stock_data_client.get_stock_latest_trade(req)
    return resp[symbol].price