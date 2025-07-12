# Bracket Orders Implementation

## Overview

This implementation simplifies the grid trading strategy by using IBKR's bracket order feature. Instead of manually managing separate buy and sell orders, each buy order now automatically includes an attached profit-taking sell order.

## Key Benefits

1. **Simplified Logic**: Eliminates complex order management and timeout handling
2. **Automatic Profit Taking**: Each buy order automatically includes a sell order at the configured profit percentage
3. **Reduced Risk**: No risk of forgetting to place sell orders after buy fills
4. **Better Order Management**: IBKR handles the relationship between parent and child orders

## Implementation Details

### New Methods Added to IBKRClient

#### `place_bracket_order(contract, quantity, buy_price, profit_pct=None)`
- Places a limit buy order with an attached limit sell order
- `buy_price`: Price for the buy order
- `profit_pct`: Profit percentage for sell order (defaults to config value)
- Returns list of trades (parent buy + child sell)

#### `place_market_bracket_order(contract, quantity, profit_pct=None)`
- Places a market buy order with an attached limit sell order
- Uses current market price to calculate sell price
- `profit_pct`: Profit percentage for sell order (defaults to config value)
- Returns list of trades (parent market buy + child limit sell)

### How Bracket Orders Work

1. **Parent Order**: The buy order (market or limit)
2. **Child Order**: The attached sell order with profit target
3. **Relationship**: Child order is linked to parent via `parentId`
4. **Execution**: When parent fills, child becomes active automatically

### Configuration

The profit percentage is configurable in `config.yaml`:
```yaml
profit_pct: 0.015  # 1.5% profit target per trade
```

## Simplified Trading Logic

### Before (Complex Manual Management)
```python
# Place buy order
trade = ibkr.place_market_order(contract, 'BUY', lot_size)

# Wait for fill, handle timeouts, retry logic
if order_pending:
    # Complex timeout and retry logic
    if (time.time() - initial_order_start_time) > 300:
        # Modify order, retry, etc.
        pass

# After buy fills, manually place sell order
if fill['action'] == 'BUY':
    sell_price = round_price(fill['price'] * (1 + config['profit_pct']))
    ibkr.place_limit_order(contract, 'SELL', fill['quantity'], sell_price)
```

### After (Simple Bracket Orders)
```python
# Place bracket order (buy + attached sell)
trades = ibkr.place_market_bracket_order(contract, lot_size, profit_pct=config['profit_pct'])

# When buy fills, sell order is already active
if fill['action'] == 'BUY':
    logger.info("Buy order filled. Attached sell order is already active.")
```

## Trading Flow

1. **Initial Entry**: Place market bracket order
   - Market buy order executes immediately
   - Limit sell order becomes active at profit target

2. **Grid Orders**: Place limit bracket orders below current price
   - Each grid level has its own buy + sell bracket
   - Profit targets are automatically set

3. **Order Fills**: 
   - Buy fills: Attached sell order becomes active
   - Sell fills: Record profit, place replacement grid order

4. **Continuous Operation**: 
   - No complex timeout handling
   - No manual sell order placement
   - Automatic profit taking at configured percentage

## Testing

Use the test script to verify bracket order functionality:
```bash
python test_bracket_orders.py
```

This will test both limit and market bracket orders with small quantities.

## Advantages Over Previous Implementation

1. **Eliminates Complex State Management**: No more `order_pending`, `initial_order_start_time`, `order_modification_count`
2. **No Timeout Handling**: IBKR manages order lifecycle
3. **Automatic Profit Taking**: No risk of missed sell orders
4. **Cleaner Code**: Reduced from ~200 lines to ~50 lines in main loop
5. **Better Reliability**: Less chance of order management errors

## Order Tracking

Bracket orders are tracked with additional metadata:
```python
self.open_orders[order_id] = {
    'symbol': contract.symbol,
    'action': 'BUY',
    'quantity': quantity,
    'price': buy_price,
    'trade': trade,
    'order_type': 'bracket_parent'  # or 'bracket_child'
}
```

## Error Handling

- Bracket orders handle trading period restrictions automatically
- Outside RTH orders are configured when needed
- Proper TIF (Time In Force) settings based on market hours

## Future Enhancements

1. **Stop Loss Orders**: Add stop loss as third order in bracket
2. **Trailing Stops**: Implement trailing stop functionality
3. **Dynamic Profit Targets**: Adjust profit targets based on volatility
4. **Order Scaling**: Scale order sizes based on position size 