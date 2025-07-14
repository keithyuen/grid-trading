import logging
from ib_async import *
import yaml
from datetime import datetime
import pytz
from typing import List, Dict, Optional
import math
from database import TradeDB

logger = logging.getLogger()  # Use the root logger for all logging in this module

class IBKRClient:
    def __init__(self, paper: bool = True, client_id: int = 1, port: int = 4002):
        self.ib = IB()
        self.paper = paper
        self.client_id = client_id
        self.port = port
        self.connected = False
        self.open_orders = {}
        self.db = TradeDB('trade_logs.db')
        
        # Load config
        with open("config.yaml", "r") as f:
            self.config = yaml.safe_load(f)
        
        self.symbol = self.config["symbol"]
        
    def connect(self) -> bool:
        """Connect to IB Gateway with timeout and retry"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.debug(f"Attempting to connect to IBKR Gateway (attempt {attempt + 1}/{max_retries})")
                self.ib.connect("127.0.0.1", self.port, clientId=self.client_id, timeout=20)
                self.connected = True
                logger.debug(f"Connected to IBKR Gateway (Paper: {self.paper})")
                return True
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info("Waiting 5 seconds before retry...")
                    import time
                    time.sleep(5)
                else:
                    logger.error(f"All connection attempts failed. Last error: {e}")
                    return False
    
    def disconnect(self):
        """Disconnect from IB Gateway"""
        try:
            if self.connected:
                self.ib.disconnect()
                self.connected = False
                logger.info("Disconnected from IBKR Gateway")
        except Exception as e:
            logger.warning(f"Disconnection issue: {e}")
    
    def get_trading_period(self):
        """Return the current trading period: 'pre-market', 'regular', 'after-hours', or 'overnight' (ET)"""
        from datetime import datetime, time as dtime
        import pytz
        eastern = pytz.timezone("US/Eastern")
        now = datetime.now(eastern)
        
        # Check if it's weekend (Saturday = 5, Sunday = 6)
        if now.weekday() >= 5:  # Saturday or Sunday
            return 'closed'
        
        now_time = now.time()
        # Customizable session boundaries
        pre_market_open = dtime(4, 5)
        pre_market_close = dtime(7, 30)
        regular_open = dtime(9, 31)
        regular_close = dtime(15, 57)
        after_hours_open = dtime(16, 10)
        after_hours_close = dtime(19, 45)
        overnight_open = dtime(20, 15)
        overnight_close = dtime(3, 45)
        if pre_market_open <= now_time < pre_market_close:
            return 'pre-market'
        elif regular_open <= now_time < regular_close:
            return 'regular'
        elif after_hours_open <= now_time < after_hours_close:
            return 'after-hours'
        elif (now_time >= overnight_open) or (now_time < overnight_close):
            return 'overnight'
        else:
            return 'closed'

    def is_market_open(self):
        """Return True if any trading period is open (pre-market, regular, after-hours, overnight)"""
        return self.get_trading_period() in ['pre-market', 'regular', 'after-hours', 'overnight']
    
    def get_stock_contract(self, symbol: str):
        """Create and qualify a stock contract, handling routing based on trading period"""
        from datetime import datetime
        import pytz
        eastern = pytz.timezone("US/Eastern")
        now = datetime.now(eastern)
        period = self.get_trading_period()
        logger.info(f"Current time (Eastern): {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"Trading period: {period}")
        
        # Try different exchange configurations if qualification fails
        exchange_configs = [
            ("SMART", "NASDAQ"),
            ("NASDAQ", "NASDAQ"), 
            ("ARCA", "ARCA"),
            ("SMART", None),  # Let SMART choose
        ]
        
        for exchange, primary_exchange in exchange_configs:
            try:
                contract = Stock(symbol, exchange=exchange, currency="USD")
                if primary_exchange:
                    contract.primaryExchange = primary_exchange
                
                logger.info(f"Attempting to qualify {symbol} with exchange={exchange}, primaryExchange={primary_exchange}")
                
                # Try to qualify the contract
                qualified_contracts = self.ib.qualifyContracts(contract)
                
                if qualified_contracts and len(qualified_contracts) > 0:
                    qualified_contract = qualified_contracts[0]
                    if hasattr(qualified_contract, 'conId') and qualified_contract.conId:
                        logger.info(f"Successfully qualified {symbol} with conId={qualified_contract.conId}, exchange={qualified_contract.exchange}")
                        return qualified_contract
                    else:
                        logger.warning(f"Contract qualified but no conId found for {symbol}")
                else:
                    logger.warning(f"No qualified contracts returned for {symbol} with exchange={exchange}")
                    
            except Exception as e:
                logger.warning(f"Failed to qualify {symbol} with exchange={exchange}: {e}")
                continue
        
        # If all qualification attempts failed, create a basic contract and log warning
        logger.error(f"All qualification attempts failed for {symbol}. Creating unqualified contract.")
        contract = Stock(symbol, exchange="SMART", currency="USD")
        contract.primaryExchange = "NASDAQ"
        return contract
    
    def get_market_price(self, contract) -> float:
        """Get current market price for a contract"""
        ticker = self.ib.reqMktData(contract)
        self.ib.sleep(3)  # Wait longer for market data
        
        # Try multiple price sources in order of preference
        price = None
        
        # First try market price
        if ticker.marketPrice() and ticker.marketPrice() > 0 and not math.isnan(ticker.marketPrice()):
            price = ticker.marketPrice()
        # Then try last price
        elif ticker.last and ticker.last > 0 and not math.isnan(ticker.last):
            price = ticker.last
        # Then try close price
        elif ticker.close and ticker.close > 0 and not math.isnan(ticker.close):
            price = ticker.close
        # Then try bid/ask midpoint
        elif (ticker.bid and ticker.ask and ticker.bid > 0 and ticker.ask > 0 and 
              not math.isnan(ticker.bid) and not math.isnan(ticker.ask)):
            price = (ticker.bid + ticker.ask) / 2
        # Finally try bid or ask alone
        elif ticker.bid and ticker.bid > 0 and not math.isnan(ticker.bid):
            price = ticker.bid
        elif ticker.ask and ticker.ask > 0 and not math.isnan(ticker.ask):
            price = ticker.ask
        
        if price is None or price <= 0 or math.isnan(price):
            logger.warning(f"Could not get valid price for {contract.symbol}. Market may be closed.")
            
            # Try to get historical data as fallback
            try:
                from datetime import datetime, timedelta
                import pytz
                eastern = pytz.timezone("US/Eastern")
                end_time = datetime.now(eastern).strftime('%Y%m%d %H:%M:%S US/Eastern')
                bars = self.ib.reqHistoricalData(
                    contract, endDateTime=end_time, durationStr='1 D',
                    barSizeSetting='1 min', whatToShow='TRADES', useRTH=False
                )
                if bars and len(bars) > 0:
                    price = bars[-1].close
                    logger.info(f"Using historical price for {contract.symbol}: ${price:.2f}")
                else:
                    raise ValueError("No historical data available")
            except Exception as hist_error:
                logger.error(f"Historical data fallback failed: {hist_error}")
                raise ValueError(f"Invalid market price for {contract.symbol}. Market may be closed or data unavailable.")
        
        logger.debug(f"Market price for {contract.symbol}: ${price:.2f}")
        return price
    
    def get_account_summary(self) -> List:
        """Get account summary"""
        return self.ib.accountSummary()
    
    def has_position(self, symbol: str) -> bool:
        """Check if we have any position in the symbol"""
        positions = self.ib.positions()
        for position in positions:
            if position.contract.symbol == symbol and position.position != 0:
                return True
        return False
    
    def get_position(self, symbol: str) -> Optional[int]:
        """Get current position size for a symbol"""
        positions = self.ib.positions()
        for position in positions:
            if position.contract.symbol == symbol:
                return position.position
        return 0
    
    def record_order(self, symbol, action, price, quantity, order_id=None):
        # Deduplicate: check if order already exists
        if not self.db.order_exists(symbol, action, price, quantity, order_id):
            self.db.record_order(symbol, action, price, quantity, order_id)
    
    def record_trade(self, symbol, action, price, quantity, trade_id=None):
        # Deduplicate: check if trade already exists
        if not self.db.trade_exists(symbol, action, price, quantity, trade_id):
            self.db.record_trade(symbol, action, price, quantity, trade_id)
    
    def record_cancel(self, symbol, action, price, quantity, order_id=None):
        # Deduplicate: check if cancel already exists
        if not self.db.cancel_exists(symbol, action, price, quantity, order_id):
            self.db.record_cancel(symbol, action, price, quantity, order_id)
    
    def update_position(self, symbol):
        # Get current position and update in DB
        position = self.get_position(symbol)
        self.db.update_position(symbol, position)
    
    # IBKR API: https://www.interactivebrokers.com/campus/ibkr-api-page/order-types/#bracket-orders
    def place_bracket_order(self, contract, quantity: int, buy_price: float, profit_pct: float = None):
        """
        Place a bracket order with a buy order and attached profit-taking sell order.
        
        Args:
            contract: IBKR contract object
            quantity: Number of shares to buy
            buy_price: Price for the buy order
            profit_pct: Profit percentage for sell order (defaults to config value)
        
        Returns:
            List of trades (parent buy order and attached sell order)
        """
        if profit_pct is None:
            profit_pct = self.config.get('profit_pct', 0.015)  # Default 1.5%
        
        period = self.get_trading_period()
        if period == 'closed':
            logger.warning('Market is not open. Orders not placed.')
            return None
        tif = 'GTC'  # Use GTC for all orders for consistency
        
        # Calculate sell price based on profit percentage
        sell_price = round(buy_price * (1 + profit_pct), 2)
        
        logger.debug(f"Creating bracket order: BUY {quantity} @ ${buy_price:.2f}, SELL @ ${sell_price:.2f} ({profit_pct*100:.1f}% profit)")
        
        # Create the parent buy order
        parent_order = LimitOrder('BUY', quantity, buy_price, tif=tif)
        # not needed as outsideRth can be placed during regular hours too: if period in ['pre-market', 'after-hours']:
        if period in ['pre-market', 'after-hours']:
            order.outsideRth = True  # Allow order to execute outside regular hours
        if period == 'overnight':
            parent_order.exchange = 'OVERNIGHT'
        parent_order.transmit = False
        
        # Create the attached sell order (profit-taking)
        take_profit_order = LimitOrder('SELL', quantity, sell_price, tif=tif)
        # not needed as outsideRth can be placed during regular hours too: if period in ['pre-market', 'after-hours']:
        if period in ['pre-market', 'after-hours']:
            order.outsideRth = True  # Allow order to execute outside regular hours
        if period == 'overnight':
            take_profit_order.exchange = 'OVERNIGHT'
        take_profit_order.transmit = True
        
        # Create bracket order
        bracket = self.ib.placeOrder(contract, parent_order)
        self.ib.sleep(1);
        
        # Attach the take profit order to the parent
        take_profit_order.parentId = bracket.order.orderId
        take_profit_trade = self.ib.placeOrder(contract, take_profit_order)
        
        # Track both orders
        self.open_orders[bracket.order.orderId] = {
            'symbol': contract.symbol,
            'action': 'BUY',
            'quantity': quantity,
            'price': buy_price,
            'trade': bracket,
            'order_type': 'bracket_parent'
        }
        
        self.open_orders[take_profit_trade.order.orderId] = {
            'symbol': contract.symbol,
            'action': 'SELL',
            'quantity': quantity,
            'price': sell_price,
            'trade': take_profit_trade,
            'order_type': 'bracket_child',
            'parent_id': bracket.order.orderId
        }
        
        # Record orders in database
        self.record_order(contract.symbol, 'BUY', buy_price, quantity, bracket.order.orderId)
        self.record_order(contract.symbol, 'SELL', sell_price, quantity, take_profit_trade.order.orderId)
        
        logger.info(f"BRACKET: BUY {quantity} @ ${buy_price:.2f} (ID:{bracket.order.orderId}), SELL @ ${sell_price:.2f} (ID:{take_profit_trade.order.orderId})")
        
        return [bracket, take_profit_trade]
    
    # IBKR API: https://www.interactivebrokers.com/campus/ibkr-api-page/order-types/#bracket-orders
    def place_market_bracket_order(self, contract, quantity: int, profit_pct: float = None):
        """
        Place a market bracket order with a market buy and attached limit sell order.
        
        Args:
            contract: IBKR contract object
            quantity: Number of shares to buy
            profit_pct: Profit percentage for sell order (defaults to config value)
        
        Returns:
            List of trades (parent market buy order and attached limit sell order)
        """
        if profit_pct is None:
            profit_pct = self.config.get('profit_pct', 0.015)  # Default 1.5%
        
        period = self.get_trading_period()
        if period == 'closed':
            logger.warning('Market is not open. Orders not placed.')
            return None
        
        # Check if we can use market orders (only during regular hours)
        if period == 'regular':
            # Get current market price for order calculation
            current_price = self.get_market_price(contract)
            sell_price = round(current_price * (1 + profit_pct), 2)
            
            logger.info(f"Creating market bracket order: BUY {quantity} shares at market, SELL at ${sell_price:.2f} ({profit_pct*100:.1f}% profit)")
            
            # Create the parent market buy order
            parent_order = MarketOrder('BUY', quantity)
            parent_order.transmit = False
            
            # Create the attached sell order (profit-taking)
            take_profit_order = LimitOrder('SELL', quantity, sell_price, tif='GTC')
            # Note: During regular hours, no special exchange or outside RTH settings needed
            take_profit_order.transmit = True

            # Place market buy order
            bracket = self.ib.placeOrder(contract, parent_order)
            self.ib.sleep(1);
            
            # Attach the take profit order to the parent
            take_profit_order.parentId = bracket.order.orderId
            take_profit_trade = self.ib.placeOrder(contract, take_profit_order)
            
            # Track both orders
            self.open_orders[bracket.order.orderId] = {
                'symbol': contract.symbol,
                'action': 'BUY',
                'quantity': quantity,
                'price': None,  # Market order
                'trade': bracket,
                'order_type': 'bracket_parent'
            }
            
            self.open_orders[take_profit_trade.order.orderId] = {
                'symbol': contract.symbol,
                'action': 'SELL',
                'quantity': quantity,
                'price': sell_price,
                'trade': take_profit_trade,
                'order_type': 'bracket_child',
                'parent_id': bracket.order.orderId
            }
            
            # Record orders in database
            self.record_order(contract.symbol, 'BUY', None, quantity, bracket.order.orderId)
            self.record_order(contract.symbol, 'SELL', sell_price, quantity, take_profit_trade.order.orderId)
            
            logger.info(f"MARKET BRACKET: BUY {quantity} @ market (ID:{bracket.order.orderId}), SELL @ ${sell_price:.2f} (ID:{take_profit_trade.order.orderId})")
            
            return [bracket, take_profit_trade]
        else:
            # Only limit orders allowed outside regular hours
            # Use aggressive price for quick fill
            current_price = self.get_market_price(contract)
            buy_price = round(current_price * 1.005, 2)  # 0.5% aggressive buy price
            
            logger.debug(f"Outside regular hours. Using limit bracket order: BUY {quantity} @ ${buy_price:.2f} (aggressive)")
            
            # Use the regular bracket order method with aggressive pricing
            return self.place_bracket_order(contract, quantity, buy_price, profit_pct)

    def place_market_order(self, contract, action: str, quantity: int):
        period = self.get_trading_period()
        if period == 'closed':
            logger.warning('Market is not open. Orders not placed.')
            return None
        if period == 'regular':
            order = MarketOrder(action, quantity)
            trade = self.ib.placeOrder(contract, order)
            logger.info(f"MARKET: {action} {quantity} {contract.symbol}")
            self.record_order(contract.symbol, action, None, quantity, getattr(trade.order, 'orderId', None))
            # Track the market order in self.open_orders for fill detection
            self.open_orders[trade.order.orderId] = {
                'symbol': contract.symbol,
                'action': action,
                'quantity': quantity,
                'price': None,  # Market order, no price
                'trade': trade
            }
            return trade
        else:
            # Only limit orders allowed outside regular hours
            limit_price = self.get_market_price(contract)
            # Use aggressive price for quick fill (1% above/below market)
            if action == 'BUY':
                price = round(limit_price * 1.005, 2)  # 1% above market
            else:
                price = round(limit_price * 0.995, 2)  # 1% below market
            return self.place_limit_order(contract, action, quantity, price)

    def place_limit_order(self, contract, action: str, quantity: int, price: float, gtc: bool = True):
        period = self.get_trading_period()
        if period == 'closed':
            logger.warning('Market is not open. Orders not placed.')
            return None
        tif = 'GTC'  # Use GTC for all orders for consistency
        exchange = None
        if period == 'overnight':
            exchange = 'OVERNIGHT'
        # Build order
        order = LimitOrder(action, quantity, price, tif=tif)
        if exchange:
            order.exchange = exchange
        if period in ['pre-market', 'after-hours']:
            order.outsideRth = True  # Allow order to execute outside regular hours
        trade = self.ib.placeOrder(contract, order)
        self.open_orders[trade.order.orderId] = {
            'symbol': contract.symbol,
            'action': action,
            'quantity': quantity,
            'price': price,
            'trade': trade
        }
        logger.info(f"LIMIT: {action} {quantity} {contract.symbol} @ ${price}")
        self.record_order(contract.symbol, action, price, quantity, getattr(trade.order, 'orderId', None))
        return trade
    
    def cancel_order(self, order_id: int):
        """Cancel a specific order"""
        if order_id in self.open_orders:
            order_info = self.open_orders[order_id]
            self.ib.cancelOrder(order_info['trade'].order)
            self.db.update_order_status(order_id, 'Cancelled')
            del self.open_orders[order_id]
            logger.info(f"CANCEL: Order {order_id}")
    
    def cancel_all_orders(self, contract):
        """Cancel all open orders for a contract using reqGlobalCancel"""
        logger.info(f"CANCEL ALL: {contract.symbol}")
        self.ib.reqGlobalCancel()
        
        # Update database status for tracked orders
        cancelled_count = 0
        for order_id, order_info in list(self.open_orders.items()):
            if order_info['symbol'] == contract.symbol:
                self.db.update_order_status(order_id, 'Cancelled')
                cancelled_count += 1
        
        # Clear in-memory tracking for this symbol
        self.open_orders = {k: v for k, v in self.open_orders.items() if v['symbol'] != contract.symbol}
        
        logger.info(f"CANCELLED: {cancelled_count} orders for {contract.symbol}")
    
    def cancel_all_buy_orders(self, contract):
        """Cancel all open buy orders for a contract"""
        cancelled = 0
        for order_id, order_info in list(self.open_orders.items()):
            if order_info['symbol'] == contract.symbol and order_info['action'] == 'BUY':
                self.cancel_order(order_id)
                cancelled += 1
        logger.info(f"CANCELLED: {cancelled} BUY orders for {contract.symbol}")
    
    def cancel_all_sell_orders(self, contract):
        """Cancel all open sell orders for a contract"""
        cancelled = 0
        for order_id, order_info in list(self.open_orders.items()):
            if order_info['symbol'] == contract.symbol and order_info['action'] == 'SELL':
                self.cancel_order(order_id)
                cancelled += 1
        logger.info(f"CANCELLED: {cancelled} SELL orders for {contract.symbol}")
    
    def count_open_buy_orders(self, contract) -> int:
        """Count open buy orders for a contract using database records."""
        return self.db.count_open_orders(contract.symbol, 'BUY')
    
    def count_open_sell_orders(self, contract) -> int:
        """Count open sell orders for a contract using database records."""
        return self.db.count_open_orders(contract.symbol, 'SELL')
    
    def check_filled_orders(self) -> List[Dict]:
        """Check for filled orders by checking order status from IBKR"""
        fills = []
        cancelled_count = 0
        inactive_count = 0
        
        # Check orders in our in-memory tracking
        for order_id, order_info in list(self.open_orders.items()):
            try:
                trade = order_info['trade']
                if hasattr(trade, 'orderStatus') and trade.orderStatus:
                    status = trade.orderStatus.status
                    if status == 'Filled':
                        fill = {
                            'order_id': order_id,
                            'action': order_info['action'],
                            'price': trade.orderStatus.avgFillPrice,
                            'quantity': trade.orderStatus.filled,
                            'symbol': order_info['symbol']
                        }
                        fills.append(fill)
                        self.record_trade(order_info['symbol'], order_info['action'], trade.orderStatus.avgFillPrice, trade.orderStatus.filled, order_id)
                        self.db.update_order_status(order_id, 'Filled')
                        # Update position in DB after fill
                        self.update_position(order_info['symbol'])
                        del self.open_orders[order_id]
                        logger.info(f"FILL: Order {order_id} {order_info['action']} {trade.orderStatus.filled} {order_info['symbol']} @ ${trade.orderStatus.avgFillPrice}")
                    elif status == 'Cancelled':
                        self.db.update_order_status(order_id, 'Cancelled')
                        del self.open_orders[order_id]
                        cancelled_count += 1
                    elif status == 'Inactive':
                        self.db.update_order_status(order_id, 'Inactive')
                        del self.open_orders[order_id]
                        inactive_count += 1
                else:
                    logger.warning(f"Order {order_id} has no orderStatus")
            except Exception as e:
                logger.warning(f"Error checking order {order_id} status: {e}")
                continue
        
        # Summary logging
        if fills or cancelled_count > 0 or inactive_count > 0:
            summary = []
            if fills:
                summary.append(f"{len(fills)} filled")
            if cancelled_count > 0:
                summary.append(f"{cancelled_count} cancelled")
            if inactive_count > 0:
                summary.append(f"{inactive_count} inactive")
            logger.info(f"Order status check: {', '.join(summary)}")
        
        return fills
    

    
    def get_open_orders(self) -> List[Dict]:
        """Get all open orders from in-memory tracking"""
        return list(self.open_orders.values())
    
    def sync_open_orders_from_ibkr(self):
        """Fetch all open orders from IBKR, repopulate self.open_orders, and mark missing DB orders as cancelled."""
        if not self.connected:
            logger.error("Cannot sync orders: not connected to IBKR")
            return False
            
        try:
            ibkr_open_orders = self.ib.reqAllOpenOrders()
            
            if ibkr_open_orders is None:
                logger.error("IBKR returned None for open orders")
                return False
                
            # Validate and extract IBKR orders safely
            ibkr_open_order_ids = set()
            valid_ibkr_orders = []
            symbol_orders_count = 0
            
            for trade in ibkr_open_orders:
                try:
                    # Validate trade object structure
                    if not self._is_valid_trade_object(trade):
                        continue
                    
                    # Extract order information safely
                    order_info = self._extract_order_info(trade)
                    if order_info is None:
                        continue
                    
                    order_id = order_info['order_id']
                    symbol = order_info['symbol']
                    action = order_info['action']
                    quantity = order_info['quantity']
                    
                    # Only process orders for our configured symbol
                    if symbol != self.symbol:
                        continue
                    
                    symbol_orders_count += 1
                    ibkr_open_order_ids.add(order_id)
                    valid_ibkr_orders.append((order_id, order_info, trade))
                    
                except Exception as e:
                    logger.warning(f"Error processing IBKR order: {e}")
                    continue
            
            # Repopulate in-memory open_orders safely
            old_open_orders_count = len(self.open_orders)
            self.open_orders.clear()
            
            for order_id, order_info, trade in valid_ibkr_orders:
                try:
                    self.open_orders[order_id] = {
                        'symbol': order_info['symbol'],
                        'action': order_info['action'],
                        'quantity': order_info['quantity'],
                        'price': order_info['price'],
                        'trade': trade
                    }
                except Exception as e:
                    logger.warning(f"Error adding order {order_id} to memory: {e}")
                    continue
            
            # Safely handle database order synchronization
            cancelled_count = self._sync_database_orders(ibkr_open_order_ids)
            
            # Summary logging
            if symbol_orders_count > 0 or cancelled_count > 0:
                logger.info(f"Order sync: {symbol_orders_count} {self.symbol} orders from IBKR, {cancelled_count} cancelled in DB, memory: {old_open_orders_count}->{len(self.open_orders)}")
            else:
                logger.debug(f"Order sync: {symbol_orders_count} {self.symbol} orders from IBKR, memory: {old_open_orders_count}->{len(self.open_orders)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Critical error during order sync: {e}")
            return False
    
    def _is_valid_trade_object(self, trade):
        """Validate that a trade object has the required structure."""
        try:
            return (hasattr(trade, 'order') and 
                   hasattr(trade, 'contract') and 
                   trade.order is not None and 
                   trade.contract is not None)
        except Exception:
            return False
    
    def _extract_order_info(self, trade):
        """Safely extract order information from a trade object."""
        try:
            # Validate required attributes exist
            if not (hasattr(trade.order, 'orderId') and 
                   hasattr(trade.order, 'action') and 
                   hasattr(trade.order, 'totalQuantity')):
                return None
            
            if not hasattr(trade.contract, 'symbol'):
                return None
            
            # Extract values with validation
            order_id = trade.order.orderId
            if not isinstance(order_id, int) or order_id <= 0:
                return None
            
            symbol = trade.contract.symbol
            if not symbol or not isinstance(symbol, str):
                return None
            
            action = trade.order.action
            if action not in ['BUY', 'SELL']:
                return None
            
            quantity = trade.order.totalQuantity
            if not isinstance(quantity, (int, float)) or quantity <= 0:
                return None
            
            # Extract price safely
            price = None
            if hasattr(trade.order, 'lmtPrice'):
                price = trade.order.lmtPrice
                if price is not None and (not isinstance(price, (int, float)) or price < 0):
                    price = None
            
            return {
                'order_id': order_id,
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'price': price
            }
            
        except Exception:
            return None
    
    def _sync_database_orders(self, ibkr_open_order_ids):
        """Safely synchronize database orders with IBKR orders."""
        try:
            db_open_orders = self.db.get_open_orders()
            if not db_open_orders:
                return 0
            
            cancelled_count = 0
            
            for db_order in db_open_orders:
                try:
                    db_order_id = db_order.get('order_id')
                    if not db_order_id:
                        continue
                    
                    if db_order_id not in ibkr_open_order_ids:
                        # Mark as cancelled in DB
                        try:
                            self.db.update_order_status(db_order_id, 'Cancelled')
                            cancelled_count += 1
                        except Exception as e:
                            logger.error(f"Failed to update order {db_order_id} status: {e}")
                        
                except Exception as e:
                    logger.warning(f"Error processing database order: {e}")
                    continue
            
            return cancelled_count
                
        except Exception as e:
            logger.error(f"Error during database sync: {e}")
            return 0

    def sleep(self, seconds: float):
        """Sleep for specified seconds"""
        self.ib.sleep(seconds)

# Legacy functions for backward compatibility
def connect_ib():
    client = IBKRClient()
    return client.connect()

def disconnect_ib():
    # This would need to be called on the client instance
    pass

def get_market_price():
    client = IBKRClient()
    if client.connect():
        contract = client.get_stock_contract(client.symbol)
        price = client.get_market_price(contract)
        client.disconnect()
        return price
    return None

def get_account_summary():
    client = IBKRClient()
    if client.connect():
        summary = client.get_account_summary()
        client.disconnect()
        return summary
    return None