import pytest
from ibkr import IBKRClient
import yaml
import os

# Load config.yaml for test parameters
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

@pytest.fixture(scope="module")
def ibkr_client():
    client = IBKRClient(
        paper=config.get('paper_trading', True),
        client_id=config['client_id'],
        port=config['tws_port']
    )
    if client.connect():
        yield client
        client.disconnect()
    else:
        pytest.skip("Could not connect to IBKR Gateway")

def test_connection(ibkr_client):
    """Test basic connection to IBKR Gateway"""
    assert ibkr_client.connected is True

def test_get_stock_contract(ibkr_client):
    """Test creating a stock contract"""
    contract = ibkr_client.get_stock_contract(config['symbol'])
    assert contract.symbol == config['symbol']
    assert contract.currency == "USD"

def test_get_market_price(ibkr_client):
    """Test getting market price"""
    contract = ibkr_client.get_stock_contract(config['symbol'])
    price = ibkr_client.get_market_price(contract)
    assert price is not None
    assert price > 0

def test_get_account_summary(ibkr_client):
    """Test getting account summary"""
    summary = ibkr_client.get_account_summary()
    assert summary is not None
    assert len(summary) > 0

def test_has_position(ibkr_client):
    """Test checking for positions"""
    has_pos = ibkr_client.has_position(config['symbol'])
    assert isinstance(has_pos, bool)

def test_get_position(ibkr_client):
    """Test getting position size"""
    position = ibkr_client.get_position(config['symbol'])
    assert isinstance(position, int)

def test_place_limit_order(ibkr_client):
    """Test placing a limit order (far out of range to avoid execution)"""
    contract = ibkr_client.get_stock_contract(config['symbol'])
    current_price = ibkr_client.get_market_price(contract)
    
    # Place order far below current price to avoid execution
    test_price = current_price * 0.5
    trade = ibkr_client.place_limit_order(contract, "BUY", 1, test_price, gtc=True)
    
    assert trade is not None
    assert trade.order.orderId is not None
    
    # Cancel the test order
    ibkr_client.cancel_order(trade.order.orderId)

def test_order_management(ibkr_client):
    """Test order management functions"""
    contract = ibkr_client.get_stock_contract(config['symbol'])
    
    # Test counting orders
    buy_count = ibkr_client.count_open_buy_orders(contract)
    sell_count = ibkr_client.count_open_sell_orders(contract)
    
    assert isinstance(buy_count, int)
    assert isinstance(sell_count, int)
    assert buy_count >= 0
    assert sell_count >= 0