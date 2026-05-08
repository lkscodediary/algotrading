
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.data.historical.stock import StockHistoricalDataClient, StockLatestTradeRequest
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import Adjustment
NY_TZ = ZoneInfo('America/New_York')

# Helper: Fetch recent bar data  
def fetch_bars(client: StockHistoricalDataClient, underlying_symbol: str, timeframe: TimeFrame, amount: int = 90) -> pd.DataFrame:
    right_now = datetime.now(NY_TZ)
    req = StockBarsRequest(
        symbol_or_symbols=[underlying_symbol],
        adjustment = Adjustment.SPLIT,
        timeframe = timeframe,  # specify timeframe
        start = right_now - timedelta(minutes = amount),             # specify start datetime, default=the beginning of the current day.
    )
    ticker_data = client.get_stock_bars(req)
    ticker_data_df = ticker_data.df.reset_index().drop(columns="symbol")
    return ticker_data_df

def get_underlying_price(symbol: str, stock_data_client: StockHistoricalDataClient) -> float:
    """Return the most recent trade price for `symbol`."""
    req  = StockLatestTradeRequest(symbol_or_symbols=symbol)
    resp = stock_data_client.get_stock_latest_trade(req)
    return resp[symbol].price
