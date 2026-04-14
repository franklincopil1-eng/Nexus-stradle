# XAUUSD MT5 Trading MVP

This is an execution-first algorithmic trading system for XAUUSD.

## IMPORTANT: Runtime Environment
The `MetaTrader5` Python library is a Windows-only DLL wrapper. It **requires** a Windows environment with the MetaTrader 5 terminal installed and logged into your broker account.

## Setup Instructions (Local Windows Machine)

1. **Install MetaTrader 5**: Download and install the MT5 terminal from your broker.
2. **Enable Algorithmic Trading**: In MT5, go to `Tools` -> `Options` -> `Expert Advisors` and check "Allow algorithmic trading".
3. **Install Python**: Ensure Python 3.8+ is installed on your Windows machine.
4. **Clone/Download this folder**: Copy the `trading_system` folder to your local machine.
5. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
6. **Configure Environment**:
   Create a `.env` file in the `trading_system` folder (use `.env.example` as a template) and fill in your MT5 credentials and the API URL:
   ```env
   MT5_LOGIN="your_login"
   MT5_PASSWORD="your_password"
   MT5_SERVER="your_broker_server"
   API_URL="https://your-app-url.run.app"
   ```
   *Note: You can find your App URL in the AI Studio interface.*
7. **Run the System**:
   ```bash
   python main.py
   ```

## System Components

- **`main.py`**: Entry point, orchestrates the connection and strategy loop.
- **`mt5_connector.py`**: Wrapper for MT5 API calls (orders, ticks, info).
- **`strategy.py`**: Implements the Straddle strategy (High/Low breakout).
- **`risk_manager.py`**: Handles lot sizing, SL/TP, and trailing stops.
- **`logger.py`**: Structured JSON logging for execution analysis.

## Strategy Logic (Straddle)
- Every minute, the system checks for open positions.
- If no positions/orders exist, it calculates the High and Low of the last 12 M5 candles (1 hour).
- It places a **Buy Stop** slightly above the high and a **Sell Stop** slightly below the low.
- When one order triggers, the other is automatically cancelled.
- A trailing stop is applied to active positions to lock in profit.

## Safety Warning
**ALWAYS test on a DEMO account first.** Algorithmic trading involves significant risk. Observe the logs for execution delays and slippage before moving to a live account.
