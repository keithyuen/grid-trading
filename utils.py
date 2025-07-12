# grid-trading/utils.py

import os
from datetime import datetime
import logging
from math import floor
import math
from logging.handlers import TimedRotatingFileHandler

def setup_logger(log_file):
    logger = logging.getLogger('grid_trader')
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger

def round_price(price):
    return round(price, 2)

def calculate_lot_size_and_interval(cash, current_price, crash_pct=0.87, range_fraction=0.565):
    """
    Calculate lot size and interval based on trading plan formula:
    LotSize = (Cash + 0.87 * CurrentStockPrice) / (0.87 * 0.565 * CurrentStockPrice^2)
    Intervals = INT(Cash / (LotSize * 0.565 * CurrentStockPrice))
    Increments = 0.87 * CurrentStockPrice / (INT(Cash / (LotSize * 0.565 * CurrentStockPrice)) - 1)
    """
    # Input validation
    if current_price <= 0:
        raise ValueError("Current price must be positive")
    
    if cash <= 0:
        raise ValueError("Available cash must be positive")
    
    if crash_pct <= 0 or crash_pct >= 1:
        raise ValueError("Crash percentage must be between 0 and 1")
    
    if range_fraction <= 0 or range_fraction >= 1:
        raise ValueError("Range fraction must be between 0 and 1")
    
    try:
        # Step 1: Calculate lot size
        numerator = cash + (crash_pct * current_price)
        denominator = crash_pct * range_fraction * (current_price ** 2)
        
        # Check for division by zero or very small denominator
        if denominator <= 0 or math.isnan(denominator):
            raise ValueError("Invalid denominator in lot size calculation")
        
        lot_size = numerator / denominator
        # alternative: hard code the lot size instead
        # lot_size = 15
        
        # Check for NaN or infinite values
        if math.isnan(lot_size) or math.isinf(lot_size):
            raise ValueError("Lot size calculation resulted in NaN or infinite value")
        
        lot_size = floor(lot_size)
        if lot_size < 1:
            lot_size = 1
        
        # Step 2: Calculate number of intervals
        interval_cost = lot_size * range_fraction * current_price
        
        # Check for division by zero
        if interval_cost <= 0:
            raise ValueError("Invalid interval cost calculation")
        
        intervals = floor(cash / interval_cost)
        if intervals <= 1:
            intervals = 1
            interval = 0  # fallback if not enough cash
        else:
            # Step 3: Calculate interval increment
            interval = (crash_pct * current_price) / (intervals - 1)
            
            # Check for NaN or infinite values
            if math.isnan(interval) or math.isinf(interval):
                raise ValueError("Interval calculation resulted in NaN or infinite value")
        
        return lot_size, interval
        
    except Exception as e:
        # Fallback to simple calculation if the complex formula fails
        logging.warning(f"Complex calculation failed: {e}. Using fallback calculation.")
        
        # Simple fallback: use 1% of cash per order, minimum 1 share
        lot_size = max(1, floor(cash * 0.01 / current_price))
        interval = current_price * 0.01  # 1% interval
        
        return lot_size, interval

def setup_daily_logging(log_folder='logs', log_level=logging.INFO):
    """
    Set up daily rotating logs in a dedicated folder.
    
    Args:
        log_folder (str): Folder to store log files (default: 'logs')
        log_level: Logging level (default: logging.INFO)
    
    Returns:
        logging.Logger: Configured logger
    """
    # Create logs directory if it doesn't exist
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)
        print(f"📁 Created log directory: {log_folder}")
    
    # Generate log filename with current date
    today = datetime.now().strftime('%Y-%m-%d')
    log_filename = os.path.join(log_folder, f'trading-{today}.log')
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            # File handler with daily rotation
            TimedRotatingFileHandler(
                log_filename,
                when='midnight',
                interval=1,
                backupCount=30,  # Keep 30 days of logs
                encoding='utf-8'
            ),
            # Console handler
            logging.StreamHandler()
        ],
        force=True  # Override any existing logging configuration
    )
    
    logger = logging.getLogger()
    logger.info(f"Logging initialized: {log_filename}")
    
    return logger