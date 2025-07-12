#!/usr/bin/env python3
"""
Script to close any open position for the configured symbol (reset to zero)
Places a limit order at 0.5% above (for buy to cover short) or below (for sell to flatten long) the current price, using overnight or regular logic.
"""

import yaml
from ibkr import IBKRClient
import time

def close_position():
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    symbol = config['symbol']
    qty_round = config.get('lot_size', 1)
    pct = 0.005  # 0.5%

    # Connect to IBKR
    ibkr = IBKRClient(
        paper=config.get('paper_trading', True),
        client_id=config['client_id'] + 40,  # Unique client ID
        port=config['tws_port']
    )
    if not ibkr.connect():
        print("❌ Failed to connect to IBKR Gateway")
        return

    try:
        contract = ibkr.get_stock_contract(symbol)
        position = ibkr.get_position(symbol)  # Use symbol string here
        print(f"Current position for {symbol}: {position} shares")
        if position == 0:
            print("✅ Already flat. No action needed.")
            return
        
        # Get current market price
        market_price = ibkr.get_market_price(contract)
        if not market_price or market_price <= 0:
            print("❌ Could not fetch market price. Aborting.")
            return
        print(f"Current market price: {market_price}")

        is_open = ibkr.is_market_open()  # FIXED: no contract argument
        # TIF and exchange are handled inside IBKRClient.place_limit_order
        
        if position < 0:
            # Need to buy to cover short, at 0.5% above market (to fill quickly)
            qty = int(abs(position) // qty_round * qty_round)
            if abs(position) % qty_round != 0:
                qty += qty_round  # round up to next lot
            limit_price = round(market_price * (1 + pct), 2)
            print(f"🟢 Placing limit BUY order for {qty} shares at {limit_price} (0.5% above market)...")
            ibkr.place_limit_order(contract, 'BUY', qty, limit_price)
            print("✅ Limit buy order placed.")
        else:
            # Need to sell to flatten, at 0.5% below market (to fill quickly)
            qty = int(position // qty_round * qty_round)
            if position % qty_round != 0:
                qty += qty_round  # round up to next lot
            limit_price = round(market_price * (1 - pct), 2)
            print(f"🔴 Placing limit SELL order for {qty} shares at {limit_price} (0.5% below market)...")
            ibkr.place_limit_order(contract, 'SELL', qty, limit_price)
            print("✅ Limit sell order placed.")
        print("⏳ Waiting for order to fill (check your IBKR interface)...")
        time.sleep(15)
        new_position = ibkr.get_position(symbol)
        print(f"New position for {symbol}: {new_position} shares")
        if new_position == 0:
            print("🎉 Position successfully reset to zero!")
        else:
            print("⚠️  Position not fully closed. Please check manually.")
    finally:
        ibkr.disconnect()

if __name__ == "__main__":
    close_position() 