# XAUUSD Multi-Broker Trading System (Professional MVP)

A high-fidelity, execution-first algorithmic trading system for XAUUSD, featuring multi-broker support, robust market awareness, and advanced multi-timeframe intelligence.

## 🚀 Core Capabilities

### 1. Multi-Broker Orchestration
- **Unified Interface**: Supports multiple MT5 brokers (Exness, Valetax, Pepperstone) and OANDA simultaneously.
- **Global State Management**: Aggregate account metrics (Balance, Equity, PnL) pushed to a real-time UI.
- **Remote Control**: Support for `HALT`, `RESUME`, and `CLOSE_ALL` commands via API.

### 2. Advanced Straddle Strategy
- **MTF Intelligence**: Executes on the **1-minute (M1)** timeframe while respecting the **15-minute (M15)** market structure.
- **Dynamic Pricing**: Calculates Buy/Sell stops based on recent volatility (lookback candles) with a configurable buffer.
- **State Machine**: Prevents duplicate orders and ensures only one straddle lifecycle exists at a time.

### 3. Professional Position Management
- **Opposite Order Cleanup**: Automatically cancels the opposite pending order as soon as one side is triggered.
- **Break-Even Logic**: Moves SL to entry price once profit reaches 100 points.
- **Hybrid Trailing Stop**:
    - **Standard Trail**: 50-point step after 150 points of profit.
    - **HTF Structure Trail**: Automatically trails SL behind **15m Liquidity/Resistance zones** when price breaks key structural levels.

### 4. Robust Execution Engine
- **Atomic Validation**: Checks for tick freezes (latency > 2s), spread spikes, and trading windows before every order.
- **Retry & Verify**: 3x retry logic with post-placement verification in the MT5 order book.
- **Dynamic Normalization**: Automatically rounds prices to broker-specific precision (digits).

### 5. Trade Forensics & Intelligence
- **Event Capture**: Structured JSONL logging of every significant event (Order Placement, Acceptance, Rejection, SL/TP hits, Market Spikes).
- **Reconstruction Engine**: Analyzes raw logs to compute:
    - **MFE/MAE**: Max Favorable/Adverse Excursion.
    - **Slippage**: Expected vs. Actual execution price.
    - **Cost Analysis**: Spread impact at the millisecond of entry.
- **Batch Analyzer**: Computes Win Rate, Expectancy, and Average RR.

## 📂 Project Structure

```text
/trading_system
  ├── main.py              # Entry point & Multi-broker loop
  ├── mt5_connector.py     # Core MT5 Execution & Validation
  ├── strategy.py          # Straddle Logic & MTF Management
  ├── event_logger.py      # Structured JSONL Logging
  ├── trade_intelligence.py # Performance Analytics & Reconstruction
  ├── risk_manager.py      # Lot sizing & Risk logic
  ├── broker_base.py       # Abstract Broker Interface
  └── test_harness.py      # Failure simulation & Robustness suite
```

## 🛠️ Setup & Execution

### Prerequisites
- **Windows Environment**: Required for the `MetaTrader5` Python library.
- **MT5 Terminal**: Installed and logged into a broker account.
- **Algorithmic Trading**: Enabled in MT5 (`Tools` -> `Options` -> `Expert Advisors`).

### Installation
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure `.env` (see `.env.example`):
   ```env
   MT5_LOGIN="123456"
   MT5_PASSWORD="password"
   MT5_SERVER="Exness-MT5Trial"
   SYMBOL="XAUUSDm"
   
   # Important: Link to your cloud dashboard
   API_URL="https://ais-dev-udk65hnd4gccc7nd7xsj6h-688925601810.europe-west2.run.app"
   ```
3. Run the system:
   ```bash
   python main.py
   ```

## 📊 Performance Analysis
To analyze your trading performance after a session, run:
```bash
python trade_intelligence.py
```
This will output a comprehensive breakdown of your win rate, slippage, and expectancy based on the forensic logs.

## ⚠️ Safety Warning
**ALWAYS test on a DEMO account first.** This system is designed for high-frequency environments where slippage and spread can significantly impact results. Monitor the `trade_events.jsonl` logs to understand how your broker handles execution during volatile periods.
