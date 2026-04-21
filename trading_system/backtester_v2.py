import pandas as pd
import numpy as np
import os
import requests
from datetime import datetime, timedelta
import MetaTrader5 as mt5
from strategy import StraddleStrategy
from risk_manager import RiskManager
from logger import setup_logger
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_URL")

class BacktestConnector:
    """Mocks the MT5Connector for historical simulation"""
    def __init__(self, data_m1, data_m5, data_m15, symbol):
        self.data_m1 = data_m1
        self.data_m5 = data_m5
        self.data_m15 = data_m15
        self.symbol = symbol
        self.current_idx = 0
        self.name = "Backtest"
        self.positions = []
        self.pending_orders = []
        self.history = []
        self.equity = 10000.0
        self.equity_curve = []
        self.point = 0.01 # Gold standard

    def get_tick(self, symbol):
        row = self.data_m1.iloc[self.current_idx]
        return {"bid": row['close'], "ask": row['close'] + 0.20, "time": row.name}

    def get_valid_tick(self, symbol):
        return type('Tick', (), self.get_tick(symbol))

    def get_historical_data(self, symbol, timeframe, count):
        # Timeframe is minutes
        if timeframe == 1:
            return self.data_m1.iloc[:self.current_idx+1].tail(count)
        elif timeframe == 5:
            # Simple M5 conversion - find current time in M5
            curr_time = self.data_m1.index[self.current_idx]
            return self.data_m5[self.data_m5.index <= curr_time].tail(count)
        elif timeframe == 15:
            curr_time = self.data_m1.index[self.current_idx]
            return self.data_m15[self.data_m15.index <= curr_time].tail(count)
        return None

    def get_account_info(self):
        # Calculate floating profit
        floating = 0
        tick = self.get_tick(self.symbol)
        for p in self.positions:
            if p['type'] == 'BUY':
                floating += (tick['bid'] - p['price_open']) * p['volume'] * 100
            else:
                floating += (p['price_open'] - tick['ask']) * p['volume'] * 100
        return {"equity": self.equity + floating, "balance": self.equity, "floatingPL": floating}

    def get_straddle_state(self, symbol):
        if self.positions: return "POSITION_ACTIVE"
        if self.pending_orders: return "STRADDLE_PENDING"
        return "NO_STRADDLE"

    def get_positions(self, symbol):
        return self.positions

    def get_pending_orders(self, symbol):
        return self.pending_orders

    def normalize_price(self, symbol, price):
        return round(float(price), 2)

    def execute_order_with_retry(self, symbol, order_type, volume, price, sl, tp, comment):
        ticket = len(self.history) + len(self.positions) + len(self.pending_orders) + 1000
        order = {
            "ticket": ticket,
            "type": "BUY STOP" if order_type == mt5.ORDER_TYPE_BUY_STOP else "SELL STOP",
            "volume": volume,
            "price_open": price,
            "sl": sl,
            "tp": tp,
            "symbol": symbol
        }
        self.pending_orders.append(order)
        return ticket

    def cancel_order(self, ticket):
        self.pending_orders = [o for o in self.pending_orders if o['ticket'] != ticket]
        return True

    def modify_position(self, ticket, sl, tp):
        for p in self.positions:
            if p['ticket'] == ticket:
                p['sl'] = sl
                p['tp'] = tp
                return True
        return False

    def close_position(self, ticket, symbol, volume=None):
        for i, p in enumerate(self.positions):
            if p['ticket'] == ticket:
                tick = self.get_tick(symbol)
                price = tick['bid'] if p['type'] == 'BUY' else tick['ask']
                
                # Calculate PnL
                if p['type'] == 'BUY':
                    pnl = (price - p['price_open']) * (volume if volume else p['volume']) * 100
                else:
                    pnl = (p['price_open'] - price) * (volume if volume else p['volume']) * 100
                
                self.equity += pnl
                if volume and volume < p['volume']:
                    p['volume'] -= volume
                else:
                    self.history.append({**p, "exit_price": price, "pnl": pnl})
                    self.positions.pop(i)
                return True
        return False

    def step(self):
        """Simulation step: check orders and exits"""
        if self.current_idx >= len(self.data_m1) - 1: return False
        self.current_idx += 1
        
        tick = self.get_tick(self.symbol)
        
        # 1. Check Pending
        for o in list(self.pending_orders):
            triggered = False
            if o['type'] == "BUY STOP" and tick['ask'] >= o['price_open']:
                triggered = True
            elif o['type'] == "SELL STOP" and tick['bid'] <= o['price_open']:
                triggered = True
            
            if triggered:
                pos = {**o, "type": "BUY" if "BUY" in o['type'] else "SELL", "price_open": o['price_open']}
                self.positions.append(pos)
                self.pending_orders.remove(o)
                # OCO handled by strategy run_iteration usually, or automatically here
        
        # 2. Check exits (SL/TP)
        for p in list(self.positions):
            exit_price = None
            if p['type'] == "BUY":
                if tick['bid'] <= p['sl'] and p['sl'] > 0: exit_price = p['sl']
                elif tick['bid'] >= p['tp'] and p['tp'] > 0: exit_price = p['tp']
            else:
                if tick['ask'] >= p['sl'] and p['sl'] > 0: exit_price = p['sl']
                elif tick['ask'] <= p['tp'] and p['tp'] > 0: exit_price = p['tp']
            
            if exit_price:
                self.close_position(p['ticket'], self.symbol)
        
        self.equity_curve.append(self.get_account_info()['equity'])
        return True

def run_backtest(days=3):
    print(f"📊 Starting Atlas-X Backtest (Last {days} days)...")
    if not mt5.initialize():
        print("❌ MT5 Init Failed for data download. Run on Windows with MT5.")
        return

    symbol = "XAUUSD" # Adjust to your broker suffix
    # 1. Download Data
    now = datetime.utcnow()
    start = now - timedelta(days=days)
    
    print("📥 Fetching historical data...")
    m1_rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, now)
    m5_rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M5, start - timedelta(hours=24), now)
    m15_rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start - timedelta(days=5), now)
    
    if m1_rates is None or m5_rates is None or m15_rates is None:
        print("❌ Could not download data.")
        return

    df_m1 = pd.DataFrame(m1_rates)
    df_m1['time'] = pd.to_datetime(df_m1['time'], unit='s')
    df_m1.set_index('time', inplace=True)
    
    df_m5 = pd.DataFrame(m5_rates)
    df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s')
    df_m5.set_index('time', inplace=True)
    
    df_m15 = pd.DataFrame(m15_rates)
    df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
    df_m15.set_index('time', inplace=True)

    # 2. Setup Backtest Environment
    logger = setup_logger()
    risk = RiskManager(fixed_lot=0.1, max_risk_percent=1.0, sl_points=300, tp_points=600, trailing_stop_points=150, logger=logger)
    connector = BacktestConnector(df_m1, df_m5, df_m15, symbol)
    strategy = StraddleStrategy(connector, risk, symbol, 1, 15, 12, 50, logger)

    print("🏃 Execution Loop...")
    while connector.step():
        strategy.run_iteration()

    # 3. Report
    print("\n" + "="*30)
    print("📈 BACKTEST COMPLETE")
    print(f"💰 Starting Balance: $10,000")
    print(f"💵 Ending Equity: ${connector.equity_curve[-1]:.2f}")
    print(f"📊 Total Trades: {len(connector.history)}")
    
    if connector.history:
        wins = [t for t in connector.history if t['pnl'] > 0]
        win_rate = (len(wins) / len(connector.history)) * 100
        total_pnl = sum([t['pnl'] for t in connector.history])
        print(f"🎯 Win Rate: {win_rate:.1f}%")
        print(f"💵 Total Profit: ${total_pnl:.2f}")

        # Push to API
        if API_URL:
            try:
                payload = {
                    "backtest": {
                        "win_rate": round(win_rate, 1),
                        "avg_rr": round(total_pnl / (abs(sum([t['pnl'] for t in connector.history if t['pnl'] < 0])) or 1), 2),
                        "total_trades": len(connector.history),
                        "total_pnl": round(total_pnl, 2),
                        "equity_curve": connector.equity_curve[::10] # Sample every 10th to save bandwidth
                    }
                }
                requests.post(f"{API_URL}/api/update", json=payload, timeout=5)
                print("📡 Dashboard Updated with Backtest Results")
            except Exception as e:
                print(f"⚠️ Could not update dashboard: {e}")
    
    print("="*30)
    mt5.shutdown()

if __name__ == "__main__":
    run_backtest(3)
