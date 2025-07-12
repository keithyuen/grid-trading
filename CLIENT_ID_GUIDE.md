# Client ID Management Guide

## Overview
To avoid connection conflicts, each component that connects to IBKR Gateway needs a unique client ID.

## Current Client ID Assignment

| Component | Client ID | Purpose |
|-----------|-----------|---------|
| Main Trading Bot | 2 | Primary trading operations |
| Streamlit Dashboard | 3 | Monitoring and account info |
| Test Scripts | 4+ | Testing and debugging |

## How It Works

### Main Trading Bot (`main.py`)
- Uses `client_id: 2` from `config.yaml`
- Handles all trading operations
- Places and manages orders

### Streamlit Dashboard (`streamlit_dashboard.py`)
- Automatically uses `client_id + 1` (so 3)
- Only reads account data and market info
- Does not place orders

### Test Scripts
- Use higher client IDs (4, 5, 6, etc.)
- For testing connections and functionality

## Configuration

### config.yaml
```yaml
client_id: 2  # Base client ID for main trading bot
```

### Automatic Client ID Assignment
- Main Bot: Uses `client_id` directly
- Dashboard: Uses `client_id + 1`
- Tests: Use `client_id + 2` or higher

## Best Practices

1. **Never use the same client ID** for multiple components
2. **Keep client IDs sequential** for easy management
3. **Document any changes** to client ID assignments
4. **Test connections** before running multiple components

## Troubleshooting

### "Client ID already in use" Error
- Check if another component is using the same client ID
- Stop all running components
- Restart with proper client ID assignments

### Connection Issues
- Ensure IBKR Gateway is running
- Verify port settings (4002 for paper, 4001 for live)
- Check firewall settings

## Running Multiple Components

```bash
# Terminal 1: Main trading bot
python main.py

# Terminal 2: Dashboard (different client ID)
streamlit run streamlit_dashboard.py

# Terminal 3: Test scripts (if needed)
python test_connection.py
```

Each component will use a different client ID automatically, preventing conflicts. 