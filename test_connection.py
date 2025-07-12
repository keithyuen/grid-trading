# test_connection.py

from ib_async import *
import yaml
from datetime import datetime
import pytz

def is_outside_market_hours():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    return now.hour < 9 or (now.hour == 9 and now.minute < 30) or now.hour >= 16

def main():
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    ib = IB()
    try:
        ib.connect('127.0.0.1', config['tws_port'], clientId=config['client_id'])
        print("✅ Connected to IBKR Gateway")

        contract = Stock(config['symbol'], exchange='NASDAQ', currency='USD')
        if is_outside_market_hours():
            contract.exchange = 'OVERNIGHT'
            contract.primaryExchange = 'NASDAQ'
        ib.qualifyContracts(contract)

        ticker = ib.reqMktData(contract)
        ib.sleep(2)
        print(f"📈 Current price for {config['symbol']}: {ticker.marketPrice()}")

        # Handle list of AccountSummaryTag
        summary = ib.accountSummary()
        print("📊 Account Summary:")
        for item in summary:
            print(f"{item.tag}: {item.value} {item.currency}")

    except Exception as e:
        print("API connection failed:", e)
    finally:
        ib.disconnect()
        print("❌ Disconnected from IBKR Gateway")

if __name__ == '__main__':
    main()