#!/usr/bin/env python3
"""
Test script for bracket order functionality
"""

import logging
import sys
import time
from ibkr import IBKRClient
from utils import setup_logger

def test_bracket_orders():
    """Test bracket order functionality"""
    
    # Setup logging
    logger = setup_logger('test_bracket_orders.log')
    logger.info("Starting bracket order test...")
    
    # Initialize IBKR client
    ibkr = IBKRClient(paper=True, client_id=3)  # Use different client ID for testing
    
    try:
        # Connect to IBKR
        if not ibkr.connect():
            logger.error("Failed to connect to IBKR")
            return False
        
        logger.info("Connected to IBKR successfully")
        
        # Get contract for TQQQ
        contract = ibkr.get_stock_contract("TQQQ")
        logger.info(f"Got contract for TQQQ: {contract}")
        
        # Get current market price
        current_price = ibkr.get_market_price(contract)
        logger.info(f"Current TQQQ price: ${current_price}")
        
        # Test 1: Place a limit bracket order
        logger.info("=== Testing Limit Bracket Order ===")
        buy_price = round(current_price * 0.95, 2)  # 5% below current price
        lot_size = 10  # Small test quantity
        
        try:
            trades = ibkr.place_bracket_order(contract, lot_size, buy_price, profit_pct=0.015)
            logger.info(f"Successfully placed limit bracket order: {len(trades)} trades")
            
            # Wait a moment and check order status
            time.sleep(5)
            open_orders = ibkr.get_open_orders()
            logger.info(f"Open orders after placing bracket: {len(open_orders)}")
            
            # Cancel the test order
            ibkr.cancel_all_orders(contract)
            logger.info("Cancelled test bracket order")
            
        except Exception as e:
            logger.error(f"Failed to place limit bracket order: {e}")
            return False
        
        # Test 2: Place a market bracket order
        logger.info("=== Testing Market Bracket Order ===")
        try:
            trades = ibkr.place_market_bracket_order(contract, lot_size, profit_pct=0.015)
            logger.info(f"Successfully placed market bracket order: {len(trades)} trades")
            
            # Wait a moment and check order status
            time.sleep(5)
            open_orders = ibkr.get_open_orders()
            logger.info(f"Open orders after placing market bracket: {len(open_orders)}")
            
            # Cancel the test order
            ibkr.cancel_all_orders(contract)
            logger.info("Cancelled test market bracket order")
            
        except Exception as e:
            logger.error(f"Failed to place market bracket order: {e}")
            return False
        
        logger.info("All bracket order tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return False
    
    finally:
        # Disconnect
        ibkr.disconnect()
        logger.info("Disconnected from IBKR")

if __name__ == "__main__":
    success = test_bracket_orders()
    sys.exit(0 if success else 1) 