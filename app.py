# STRATEGY SUMMARY
# This is a strategy taken from Alapca's example but modified to be intraday. However,
# it is very conservation. 
# 
# Trading Mechanics
# Long trades are made only during an up-trend and short trades
# are made during a down-trend. This way you don't end up taking a long position a.k.a 
# catching a knife due to RSI bounce from oversold during a down-trend a.k.a dead cat bounce. 
#
# Trading Intuition
# 
# ###########################Rules################################################
# Timeframes:
#   MAIN  (1-min)  : RSI + MACD signals are computed here.
#   TREND (30-min) : Three moving averages define whether we're in an up- or
#                    down-trend. We only trade in the direction of the trend.
#
# LONG trade (uptrend: MA20 > MA50 > MA100 on 30-min bars):
#   Entry   RSI crosses UP through 30 (oversold bounce)
#             AND MACD golden cross (MACD line crosses above Signal)
#             Both events must occur within WINDOW_SIZE bars of each other.
#   Exit    RSI drops below 65 from above 70 (overbought retreat)
#             AND (MACD death cross OR MACD drops below zero)
#             Both events must occur within WINDOW_SIZE bars of each other.
#
# SHORT trade (downtrend: MA20 < MA50 < MA100 on 30-min bars):
#   Entry  RSI crosses DOWN through 70 (overbought peak)
#             AND MACD death cross (MACD line crosses below Signal)
#             Both events must occur within WINDOW_SIZE bars of each other.
#   Exit    RSI rises above 35 from below 30 (oversold bounce)
#             AND (MACD golden cross OR MACD rises above zero)
#             Both events must occur within WINDOW_SIZE bars of each other.
#
# BUGS FIXED and ENHANCED vs. ORIGINAL ALPACA EXAMPLE
# 
# 1. isna().any() bug  Original checks if ANY row in the MA series is NaN
#    (always True because early rows lack enough history), so in_uptrend was
#    ALWAYS False and the bot NEVER traded. Fixed: check only the last bar.
#
# 2. Signal staleness  Original never expires pending signals, so an RSI
#    bounce from 50 bars ago could still combine with a fresh MACD cross to
#    trigger a trade. Fixed: SIGNAL_EXPIRY window.
#
# 5. RSI smoothing Original compute_rsi used simple rolling mean (incorrect).
#    Proper Wilder's smoothing is used in the updated technicals.py.
#
# 6. Sleeps until next day but seperate sleep for 5 seconds interval. Moved a lot 
#    codes to functions out of the loop
#
# PARAMETERS TUNED FOR 1-MIN / 30-MIN
# 
# RSI period  : 7  (standard 14 is designed for daily; 7 is more responsive
#               on 1-min without being too noisy)
# MACD        : 12/26/9 is kept it is timeframe-agnostic by nature and
#               remains the most widely-used combination even on intraday bars.
# Trend MAs   : Scaled from 50/100/200 (daily) to 20/50/100 (30-min).
#               200 bars X 30 min = 6,000 trading minutes ~ 4.17 days. Too long memory.
#               100 bars X 30 min = 3,000 trading mintues ~ 2.08 days. I think thats just right.
#               20/50/100 which still captures short / medium / long micro-trend.
# RSI thresholds (30/70): Kept. 1-min RSI does cross these levels on volatile
#               stocks; you may tighten to 35/65 if signals are too rare.
#
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

import logging, logging.config, configparser, time
from datetime import datetime, timedelta
import pandas as pd

# Config 
logging.config.fileConfig('resources/logging.ini')
config = configparser.ConfigParser()
config.read("resources/config.ini")

# Utilities
from src.utilities.market_data import fetch_bars, update_bars, get_underlying_price
from src.utilities.technicals import compute_rsi, compute_macd
from src.utilities.account import calculate_buying_power_limit
from src.utilities.misc import sleep_until

# Alpaca SDK
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

# Secrets
API_KEY            = config.get("alpaca", "key")
API_SECRET         = config.get("alpaca", "secret")
ALPACA_PAPER_TRADE = config.getboolean("alpaca", "paper_trade")

# Ticker
ticker = 'MU'
logger = logging.getLogger(f"{ticker} Trader")

# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# STRATEGY PARAMETERS
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

RSI_PERIOD      = 7     # Responsive RSI for 1-min bars (standard 14 is too slow)
MACD_FAST       = 12    # MACD fast EMA  (standard, timeframe-agnostic)
MACD_SLOW       = 26    # MACD slow EMA
MACD_SIGNAL     = 9     # MACD signal EMA

# Trend MAs on 30-min bars.  Scaled down from 50/100/200 (daily equivalent).
# 100  24 min = 2 400 trading min H 6 trading days practical to warm up.
MA_FAST         = 20
MA_MID          = 50
MA_SLOW         = 100

BUY_POWER_LIMIT = 0.02  # Max fraction of buying power per trade

# Signal confluence window (in bars on the MAIN 1-min timeframe)
WINDOW_SIZE     = 5     # RSI and MACD signals must be d 5 bars apart to confirm
SIGNAL_EXPIRY   = 15    # A signal older than 15 bars is considered stale and ignored

# Timeframes
TIMEFRAME_MAIN  = TimeFrame(amount=1,  unit=TimeFrameUnit.Minute)
TIMEFRAME_TREND = TimeFrame(amount=30, unit=TimeFrameUnit.Minute)

# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# SIGNAL STATE  (global, reset on startup)
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

# Long entry signals
rsi_bounce_bar       = None   # Bar index when RSI crossed UP through 30
macd_cross_bar       = None   # Bar index when MACD golden-crossed signal

# Long exit signals
rsi_retreat_bar      = None   # Bar index when RSI dropped from >70 to <65
macd_death_cross_bar = None   # Bar index when MACD death-crossed signal
macd_centerline_bar  = None   # Bar index when MACD dropped below zero

# Short entry signals
rsi_peak_bar         = None   # Bar index when RSI crossed DOWN through 70
macd_short_cross_bar = None   # Bar index when MACD death-crossed signal

# Short exit (cover) signals
rsi_dip_bar          = None   # Bar index when RSI crossed UP through 30
macd_cover_cross_bar = None   # Bar index when MACD golden-crossed signal
macd_center_up_bar   = None   # Bar index when MACD rose above zero

current_bar_index = 0

# Clients
trade_client      = TradingClient(api_key=API_KEY, secret_key=API_SECRET, paper=ALPACA_PAPER_TRADE)
stock_data_client = StockHistoricalDataClient(api_key=API_KEY, secret_key=API_SECRET)


# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# HELPERS
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

def signal_valid(signal_bar: int | None, current_bar: int, expiry: int = SIGNAL_EXPIRY) -> bool:
    """
    Return True only if:
      " the signal has been set (not None), AND
      " it is not older than `expiry` bars.
    This prevents a signal from 30 minutes ago combining with a fresh
    signal now and accidentally triggering an entry/exit.
    """
    return signal_bar is not None and (current_bar - signal_bar) <= expiry


def reset_long_entry_signals():
    global rsi_bounce_bar, macd_cross_bar
    rsi_bounce_bar = macd_cross_bar = None


def reset_long_exit_signals():
    global rsi_retreat_bar, macd_death_cross_bar, macd_centerline_bar
    rsi_retreat_bar = macd_death_cross_bar = macd_centerline_bar = None


def reset_short_entry_signals():
    global rsi_peak_bar, macd_short_cross_bar
    rsi_peak_bar = macd_short_cross_bar = None


def reset_short_exit_signals():
    global rsi_dip_bar, macd_cover_cross_bar, macd_center_up_bar
    rsi_dip_bar = macd_cover_cross_bar = macd_center_up_bar = None

# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
# MAIN LOOP
# PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

def main():
    """Main trading loop."""

    global rsi_bounce_bar, macd_cross_bar, rsi_retreat_bar,\
            macd_death_cross_bar, macd_centerline_bar,\
            rsi_peak_bar, macd_short_cross_bar,\
            rsi_dip_bar, macd_cover_cross_bar, macd_center_up_bar,\
            current_bar_index

    # Startup
    clock       = trade_client.get_clock()
    market_open = clock.is_open

    reset_long_entry_signals()
    reset_long_exit_signals()
    reset_short_entry_signals()
    reset_short_exit_signals()
    current_bar_index = 0

    logger.info(f"Starting algorithmic {ticker} trader")

    trade_tik_tok  = datetime.now()
    in_trade = "==NOT IN TRADE=="

    # Display variables (initialised so logger.info never crashes on first tick)
    rsi_now = rsi_prev = macd_now = macd_prev = sig_now = sig_prev = 0.0
    ma_fast = ma_mid = ma_slow = pd.Series([0.0])
    current_price = 0.0

    # Download history to warm up the technicals
    df_main  = fetch_bars(stock_data_client, ticker, TIMEFRAME_MAIN,  amount = MA_SLOW + 10)
    df_trend = fetch_bars(stock_data_client, ticker, TIMEFRAME_TREND, amount = round(30*MA_SLOW*2.5))

    logger.info("Fetched %d main bars and %d trend bars", len(df_main), len(df_trend))
    # Loop
    while True:

        # Sleep for 5 seconds then wake up and update statistics and trade if >= 1 minute since last check
        time.sleep(5)
        clock = trade_client.get_clock()

        if market_open and not clock.is_open:
            logger.info("Pencils down. Market closed. Sleeping until %s", clock.next_open)
            market_open = False
            sleep_until(clock.next_open)
            continue

        if (not market_open) and clock.is_open:
            logger.info("Market opened. Resuming trading.")
            market_open = True

        if not clock.is_open:
            logger.info("Market is closed. Exiting.")
            exit(0)

        current_price = get_underlying_price(ticker, stock_data_client)
        logger.info(
            "%s | %s | PRICE[%.4f] | RSI[%.4f�%.4f] | "
            "MACD[%.4f�%.4f] | SIG[%.4f�%.4f] | "
            "MA.F[%.4f] MA.M[%.4f] MA.S[%.4f]",
            ticker, in_trade, current_price,
            rsi_prev, rsi_now,
            macd_prev, macd_now,
            sig_prev, sig_now,
            ma_fast.iloc[-1], ma_mid.iloc[-1], ma_slow.iloc[-1],
        )

        # Trading logic every 1 min
        if datetime.now() - trade_tik_tok < timedelta(minutes=1):
            continue  # Nothing to do yet; tight loop burns CPU add a micro-sleep if desired

        #Update bars
        df_main_update  = update_bars(stock_data_client, ticker, TIMEFRAME_MAIN,  start_date_time = df_main['timestamp'].iloc[-1])
        logger.info(f"It's been a minute {datetime.now() - trade_tik_tok}")
        
        if df_main_update.shape[0] > 1:
            # Leave the far end history behind to achive a rolling window 
            # and also leave first row of the updated bars otherwise because it starts with the last row of the previous data frame
            df_main = pd.concat([df_main.loc[1:], df_main_update.loc[1: ]], ignore_index = True)

        df_trend_update = update_bars(stock_data_client, ticker, TIMEFRAME_TREND, start_date_time = df_trend['timestamp'].iloc[-1])
        if df_trend_update.shape[0] > 1:
            # Leave the far end history behind to achive a rolling window 
            # and also leave first row of the updated bars otherwise because it starts with the last row of the previous data frame
            df_trend = pd.concat([df_trend.loc[1:], df_trend_update.loc[1: ]], ignore_index = True)

        if len(df_main) < MACD_SLOW + RSI_PERIOD:
            logger.warning("Not enough main bars to compute indicators. Skipping.")
            trade_tik_tok = datetime.now()
            continue

        current_bar_index = len(df_main) - 1

        # Position state
        try:
            position      = trade_client.get_open_position(ticker)
            current_qty   = int(position.qty)        # negative = short position
            long_position  = current_qty > 0
            short_position = current_qty < 0
            position_open  = True
        except Exception:
            current_qty    = 0
            long_position  = False
            short_position = False
            position_open  = False

        # Compute indicators
        prices     = df_main.close
        rsi_series = compute_rsi(prices, RSI_PERIOD)
        macd_line, signal_line = compute_macd(prices, MACD_FAST, MACD_SLOW, MACD_SIGNAL)

        rsi_now   = rsi_series.iloc[-1]
        rsi_prev  = rsi_series.iloc[-2]
        macd_now  = macd_line.iloc[-1]
        macd_prev = macd_line.iloc[-2]
        sig_now   = signal_line.iloc[-1]
        sig_prev  = signal_line.iloc[-2]

        # Trend filter (30-min MAs)
        ma_fast = df_trend.close.rolling(MA_FAST).mean()
        ma_mid  = df_trend.close.rolling(MA_MID).mean()
        ma_slow = df_trend.close.rolling(MA_SLOW).mean()

        # BUG FIX: original used .isna().any() which checks EVERY row in the
        # Series and is always True (early rows are always NaN).  We only care
        # whether the LATEST bar has a valid value.
        trend_ready = (
            pd.notna(ma_fast.iloc[-1]) and
            pd.notna(ma_mid.iloc[-1])  and
            pd.notna(ma_slow.iloc[-1])
        )

        in_uptrend   = trend_ready and (ma_fast.iloc[-1] > ma_mid.iloc[-1] > ma_slow.iloc[-1])
        in_downtrend = trend_ready and (ma_fast.iloc[-1] < ma_mid.iloc[-1] < ma_slow.iloc[-1])

        logger.info(
            "%s | TREND | MA20[%.4f] MA50[%.4f] MA100[%.4f] | up=%s down=%s",
            ticker,
            ma_fast.iloc[-1] if trend_ready else float('nan'),
            ma_mid.iloc[-1]  if trend_ready else float('nan'),
            ma_slow.iloc[-1] if trend_ready else float('nan'),
            in_uptrend, in_downtrend,
        )

        # Position sizing (fresh price every cycle)
        # BUG FIX: original reused a stale current_price from the screen loop.
        current_price      = get_underlying_price(ticker, stock_data_client)
        buying_power_limit = calculate_buying_power_limit(BUY_POWER_LIMIT, trade_client)
        position_size      = int(buying_power_limit / current_price)

        # PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
        # LONG SIDE  (only when uptrend confirmed)
        # PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

        # Long entry signal 1: RSI oversold bounce
        #    RSI was below 30 (oversold) and has now crossed back above 30.
        #    This suggests selling exhaustion and a potential reversal up.
        if rsi_prev < 30 and rsi_now >= 30:
            rsi_bounce_bar = current_bar_index
            logger.info(
                "%s | LONG SIGNAL | RSI oversold bounce: %.2f  %.2f",
                ticker, rsi_prev, rsi_now,
            )

        # Long entry signal 2: MACD golden cross
        #    MACD line crosses above the signal line momentum turning bullish.
        if macd_prev < sig_prev and macd_now > sig_now:
            macd_cross_bar = current_bar_index
            logger.info(
                "%s | LONG SIGNAL | MACD golden cross: MACD[%.4f�%.4f] SIG[%.4f�%.4f]",
                ticker, macd_prev, macd_now, sig_prev, sig_now,
            )

        # Long ENTRY
        #    Requires: uptrend + both signals valid + signals close enough in time.
        if not position_open and in_uptrend and position_size > 0:
            both_valid = (
                signal_valid(rsi_bounce_bar, current_bar_index) and
                signal_valid(macd_cross_bar, current_bar_index) and
                abs(rsi_bounce_bar - macd_cross_bar) <= WINDOW_SIZE
            )
            if both_valid:
                req = MarketOrderRequest(
                    symbol=ticker, qty=position_size,
                    side=OrderSide.BUY, type=OrderType.MARKET,
                    time_in_force=TimeInForce.DAY,
                )
                res = trade_client.submit_order(req)
                logger.info(
                    "BUY (LONG) - %s | Qty: %d | Est.Price: $%.2f | OrderID: %s",
                    ticker, position_size, current_price, res.id,
                )
                reset_long_entry_signals()
                in_trade = "==LONG========="

        # Long exit signal 1: RSI overbought retreat
        #    RSI was above 70 (overbought) and has now dropped below 65.
        #    The wider gap (not just below 70) filters out brief dips and
        #    confirms momentum has genuinely rolled over.
        if rsi_prev > 70 and rsi_now < 65:
            rsi_retreat_bar = current_bar_index
            logger.info(
                "%s | LONG EXIT SIGNAL | RSI overbought retreat: %.2f  %.2f",
                ticker, rsi_prev, rsi_now,
            )

        # Long exit signal 2a: MACD death cross
        #    MACD drops below the signal line momentum turning bearish.
        if macd_prev > sig_prev and macd_now < sig_now:
            macd_death_cross_bar = current_bar_index
            logger.info(
                "%s | LONG EXIT SIGNAL | MACD death cross: MACD[%.4f�%.4f] SIG[%.4f�%.4f]",
                ticker, macd_prev, macd_now, sig_prev, sig_now,
            )

        #  Long exit signal 2b: MACD crosses below zero
        #    MACD going negative means the fast EMA has crossed below the slow
        #    EMA a stronger bearish confirmation than just a signal-line cross.
        elif macd_prev > 0 and macd_now < 0:
            macd_centerline_bar = current_bar_index
            logger.info(
                "%s | LONG EXIT SIGNAL | MACD below zero: %.4f  %.4f",
                ticker, macd_prev, macd_now,
            )

        # Long EXIT
        if long_position:
            macd_exit_triggered = (
                (signal_valid(macd_death_cross_bar, current_bar_index) and
                 abs(rsi_retreat_bar - macd_death_cross_bar) <= WINDOW_SIZE)
                or
                (signal_valid(macd_centerline_bar, current_bar_index) and
                 abs(rsi_retreat_bar - macd_centerline_bar) <= WINDOW_SIZE)
            ) if rsi_retreat_bar is not None else False

            if signal_valid(rsi_retreat_bar, current_bar_index) and macd_exit_triggered:
                req = MarketOrderRequest(
                    symbol=ticker, qty=current_qty,
                    side=OrderSide.SELL, type=OrderType.MARKET,
                    time_in_force=TimeInForce.DAY,
                )
                res = trade_client.submit_order(req)
                logger.info(
                    "SELL (CLOSE LONG) - %s | Qty: %d | Est.Price: $%.2f | OrderID: %s",
                    ticker, current_qty, current_price, res.id,
                )
                reset_long_exit_signals()
                in_trade = "==NOT IN TRADE=="

        # PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
        # SHORT SIDE  (only when downtrend confirmed)
        # PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP

        # Short entry signal 1: RSI overbought peak
        #    RSI was above 70 (overbought) and has now crossed back below 70.
        #    This is the mirror of the long bounce: buying exhaustion in a downtrend.
        if rsi_prev > 70 and rsi_now <= 70:
            rsi_peak_bar = current_bar_index
            logger.info(
                "%s | SHORT SIGNAL | RSI overbought peak: %.2f  %.2f",
                ticker, rsi_prev, rsi_now,
            )

        # Short entry signal 2: MACD death cross
        #    MACD drops below signal in a downtrend  renewed bearish momentum.
        if macd_prev > sig_prev and macd_now < sig_now:
            macd_short_cross_bar = current_bar_index
            logger.info(
                "%s | SHORT SIGNAL | MACD death cross: MACD[%.4f�%.4f] SIG[%.4f�%.4f]",
                ticker, macd_prev, macd_now, sig_prev, sig_now,
            )

        # Short ENTRY
        if not position_open and in_downtrend and position_size > 0:
            both_valid = (
                signal_valid(rsi_peak_bar, current_bar_index) and
                signal_valid(macd_short_cross_bar, current_bar_index) and
                abs(rsi_peak_bar - macd_short_cross_bar) <= WINDOW_SIZE
            )
            if both_valid:
                req = MarketOrderRequest(
                    symbol=ticker, qty=position_size,
                    side=OrderSide.SELL,   # Short sell
                    type=OrderType.MARKET,
                    time_in_force=TimeInForce.DAY,
                )
                res = trade_client.submit_order(req)
                logger.info(
                    "SELL SHORT - %s | Qty: %d | Est.Price: $%.2f | OrderID: %s",
                    ticker, position_size, current_price, res.id,
                )
                reset_short_entry_signals()
                in_trade = "==SHORT========"

        # Short exit signal 1: RSI oversold dip
        #    RSI was below 30 (oversold) and crosses back above 35.
        #    Wider gap (35 not 30) filters noise, confirms a real bounce.
        if rsi_prev < 30 and rsi_now > 35:
            rsi_dip_bar = current_bar_index
            logger.info(
                "%s | SHORT EXIT SIGNAL | RSI oversold bounce: %.2f  %.2f",
                ticker, rsi_prev, rsi_now,
            )

        # Short exit signal 2a: MACD golden cross
        if macd_prev < sig_prev and macd_now > sig_now:
            macd_cover_cross_bar = current_bar_index
            logger.info(
                "%s | SHORT EXIT SIGNAL | MACD golden cross: MACD[%.4f�%.4f] SIG[%.4f�%.4f]",
                ticker, macd_prev, macd_now, sig_prev, sig_now,
            )

        # Short exit signal 2b: MACD crosses above zero
        elif macd_prev < 0 and macd_now > 0:
            macd_center_up_bar = current_bar_index
            logger.info(
                "%s | SHORT EXIT SIGNAL | MACD above zero: %.4f  %.4f",
                ticker, macd_prev, macd_now,
            )

        #  Short EXIT (buy to cover)
        if short_position:
            macd_cover_triggered = (
                (signal_valid(macd_cover_cross_bar, current_bar_index) and
                 abs(rsi_dip_bar - macd_cover_cross_bar) <= WINDOW_SIZE)
                or
                (signal_valid(macd_center_up_bar, current_bar_index) and
                 abs(rsi_dip_bar - macd_center_up_bar) <= WINDOW_SIZE)
            ) if rsi_dip_bar is not None else False

            if signal_valid(rsi_dip_bar, current_bar_index) and macd_cover_triggered:
                req = MarketOrderRequest(
                    symbol=ticker, qty=abs(current_qty),  # qty must be positive
                    side=OrderSide.BUY,   # Buy to cover
                    type=OrderType.MARKET,
                    time_in_force=TimeInForce.DAY,
                )
                res = trade_client.submit_order(req)
                logger.info(
                    "BUY TO COVER (CLOSE SHORT) - %s | Qty: %d | Est.Price: $%.2f | OrderID: %s",
                    ticker, abs(current_qty), current_price, res.id,
                )
                reset_short_exit_signals()
                in_trade = "==NOT IN TRADE=="

        trade_tik_tok = datetime.now()


#
if __name__ == "__main__":
    main()