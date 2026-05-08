from alpaca.trading.client import TradingClient

# Helper: Calculate buying power limit based on account value and risk percentage
def calculate_buying_power_limit(buy_power_limit, trade_client:TradingClient):
    # Check account buying power
    buying_power = float(trade_client.get_account().buying_power)
    # Calculate the limit amount of buying power to use for the trade
    buying_power_limit = buying_power * buy_power_limit
    return buying_power_limit