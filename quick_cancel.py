#!/usr/bin/env python3
"""
Quick order cancellation script - use command line arguments
Usage: python quick_cancel.py [all|buy|sell|status]
"""

import yaml
from ibkr import IBKRClient
import sys

def main():
    if len(sys.argv) != 2:
        print("Usage: python quick_cancel.py [all|buy|sell|status]")
        print("  all    - Cancel all orders")
        print("  buy    - Cancel only BUY orders")
        print("  sell   - Cancel only SELL orders")
        print("  status - Show current order status")
        return
    
    action = sys.argv[1].lower()
    
    if action not in ['all', 'buy', 'sell', 'status']:
        print("Invalid action. Use: all, buy, sell, or status")
        return
    
    # Load config
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return
    
    # Connect to IBKR
    ibkr = IBKRClient(
        paper=config.get('paper_trading', True),
        client_id=config['client_id'] + 30,  # Unique client ID
        port=config['tws_port']
    )
    
    if not ibkr.connect():
        print("❌ Failed to connect to IBKR Gateway")
        return
    
    try:
        contract = ibkr.get_stock_contract(config['symbol'])
        
        if action == 'status':
            buy_orders = ibkr.count_open_buy_orders(contract)
            sell_orders = ibkr.count_open_sell_orders(contract)
            print(f"📊 Order Status for {config['symbol']}:")
            print(f"  BUY orders: {buy_orders}")
            print(f"  SELL orders: {sell_orders}")
            print(f"  Total: {buy_orders + sell_orders}")
            
        elif action == 'all':
            buy_orders = ibkr.count_open_buy_orders(contract)
            sell_orders = ibkr.count_open_sell_orders(contract)
            
            if buy_orders > 0:
                print(f"🗑️  Cancelling {buy_orders} BUY orders...")
                ibkr.cancel_all_buy_orders(contract)
            
            if sell_orders > 0:
                print(f"🗑️  Cancelling {sell_orders} SELL orders...")
                ibkr.cancel_all_sell_orders(contract)
            
            if buy_orders == 0 and sell_orders == 0:
                print("✅ No orders to cancel")
            else:
                print("✅ All orders cancelled")
                
        elif action == 'buy':
            buy_orders = ibkr.count_open_buy_orders(contract)
            if buy_orders > 0:
                print(f"🗑️  Cancelling {buy_orders} BUY orders...")
                ibkr.cancel_all_buy_orders(contract)
                print("✅ BUY orders cancelled")
            else:
                print("✅ No BUY orders to cancel")
                
        elif action == 'sell':
            sell_orders = ibkr.count_open_sell_orders(contract)
            if sell_orders > 0:
                print(f"🗑️  Cancelling {sell_orders} SELL orders...")
                ibkr.cancel_all_sell_orders(contract)
                print("✅ SELL orders cancelled")
            else:
                print("✅ No SELL orders to cancel")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        ibkr.disconnect()

if __name__ == "__main__":
    main() 