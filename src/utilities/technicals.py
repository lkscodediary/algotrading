# Helper: Compute RSI with Wilder's smoothing
import pandas as pd

def compute_rsi(prices: pd.Series, period: int) -> pd.Series:
    """
    Compute RSI using Wilder's smoothing (the standard definition).

    Args:
        prices: Close price Series (must be sorted oldest → newest).
        period: Look-back period (e.g. 7 for 1-min bars, 14 for daily).

    Returns:
        RSI Series aligned with `prices` (first `period` values will be NaN).
    """
    delta = prices.diff()
    gains  = delta.clip(lower=0)        # positive moves, zero elsewhere
    losses = (-delta).clip(lower=0)     # absolute negative moves, zero elsewhere

    # Wilder's EMA: alpha = 1/period, seed after first full window
    avg_gain = gains.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs  = avg_gain / avg_loss.replace(0, float('nan'))   # avoid division by zero
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def compute_macd(
    prices: pd.Series,
    fast: int,
    slow: int,
    signal: int,
) -> tuple[pd.Series, pd.Series]:
    """
    Compute MACD line and signal line.

    Standard formula (timeframe-agnostic):
        MACD line   = EMA(fast) − EMA(slow)
        Signal line = EMA(MACD line, signal)

    Args:
        prices: Close price Series.
        fast:   Fast EMA period  (typically 12).
        slow:   Slow EMA period  (typically 26).
        signal: Signal EMA period (typically 9).

    Returns:
        (macd_line, signal_line) — both are pd.Series aligned with `prices`.
    """
    ema_fast    = prices.ewm(span=fast,   adjust=False).mean()
    ema_slow    = prices.ewm(span=slow,   adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line