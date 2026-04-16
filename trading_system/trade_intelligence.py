import json
import os
import pandas as pd
from datetime import datetime

class TradeIntelligenceEngine:
    def __init__(self, log_file="logs/trade_events.jsonl"):
        self.log_file = log_file

    def load_events(self):
        if not os.path.exists(self.log_file):
            return []
        events = []
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except:
                    continue
        return events

    def reconstruct_trades(self):
        events = self.load_events()
        if not events:
            return []

        # Group events by position_id
        trades_map = {}
        for event in events:
            pos_id = event.get("position_id")
            if pos_id:
                if pos_id not in trades_map:
                    trades_map[pos_id] = []
                trades_map[pos_id].append(event)

        reconstructed_trades = []
        for pos_id, pos_events in trades_map.items():
            trade = self._reconstruct_single_trade(pos_id, pos_events)
            if trade:
                reconstructed_trades.append(trade)
        
        return reconstructed_trades

    def _reconstruct_single_trade(self, pos_id, events):
        # Sort events by timestamp
        events.sort(key=lambda x: x["timestamp"])
        
        trade = {
            "position_id": pos_id,
            "symbol": None,
            "type": None,
            "entry_price": None,
            "exit_price": None,
            "entry_time": None,
            "exit_time": None,
            "pnl": 0,
            "max_favorable_excursion": 0,
            "max_adverse_excursion": 0,
            "spread_at_entry": None,
            "slippage": 0,
            "status": "OPEN"
        }

        prices_during_trade = []
        
        for e in events:
            etype = e["event_type"]
            trade["symbol"] = e["symbol"]
            
            if etype == "ORDER_ACCEPTED":
                trade["entry_price"] = e["price"]
                trade["entry_time"] = e["timestamp"]
                trade["slippage"] = (e["price"] - e["expected_price"]) if e.get("expected_price") else 0
                if e.get("details") and "BUY" in e["details"]:
                    trade["type"] = "BUY"
                elif e.get("details") and "SELL" in e["details"]:
                    trade["type"] = "SELL"
            
            elif etype == "ORDER_PLACEMENT_ATTEMPT":
                if e.get("spread"):
                    trade["spread_at_entry"] = e["spread"]

            elif etype == "POSITION_MARKET_UPDATE":
                if e.get("price"):
                    prices_during_trade.append(e["price"])
                if not trade["type"] and e.get("details"):
                    trade["type"] = "BUY" if "BUY" in e["details"] else "SELL"

            elif etype == "POSITION_CLOSED":
                trade["exit_price"] = e["price"] if e.get("price") else prices_during_trade[-1] if prices_during_trade else None
                trade["exit_time"] = e["timestamp"]
                trade["status"] = "CLOSED"

        # Calculate PnL and Excursions
        if trade["entry_price"] and prices_during_trade:
            entry = trade["entry_price"]
            if trade["type"] == "BUY":
                mfe_price = max(prices_during_trade)
                mae_price = min(prices_during_trade)
                trade["max_favorable_excursion"] = max(0, mfe_price - entry)
                trade["max_adverse_excursion"] = max(0, entry - mae_price)
                if trade["exit_price"]:
                    trade["pnl"] = trade["exit_price"] - entry
            elif trade["type"] == "SELL":
                mfe_price = min(prices_during_trade)
                mae_price = max(prices_during_trade)
                trade["max_favorable_excursion"] = max(0, entry - mfe_price)
                trade["max_adverse_excursion"] = max(0, mae_price - entry)
                if trade["exit_price"]:
                    trade["pnl"] = entry - trade["exit_price"]

        return trade

def analyze_trades(log_file="/logs/trade_events.jsonl"):
    engine = TradeIntelligenceEngine(log_file)
    trades = engine.reconstruct_trades()
    
    if not trades:
        return {
            "win_rate": 0,
            "avg_rr": 0,
            "expectancy": 0,
            "avg_slippage": 0,
            "avg_spread_cost": 0,
            "total_trades": 0
        }

    df = pd.DataFrame(trades)
    closed_trades = df[df["status"] == "CLOSED"]
    
    if closed_trades.empty:
        return {
            "total_trades": len(df),
            "closed_trades": 0,
            "msg": "No closed trades to analyze metrics"
        }

    wins = closed_trades[closed_trades["pnl"] > 0]
    losses = closed_trades[closed_trades["pnl"] <= 0]
    
    win_rate = len(wins) / len(closed_trades)
    avg_win = wins["pnl"].mean() if not wins.empty else 0
    avg_loss = abs(losses["pnl"].mean()) if not losses.empty else 1 # Avoid div by zero
    
    avg_rr = avg_win / avg_loss if avg_loss != 0 else 0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    return {
        "total_trades": len(df),
        "closed_trades": len(closed_trades),
        "win_rate": round(win_rate * 100, 2),
        "avg_rr": round(avg_rr, 2),
        "expectancy": round(expectancy, 4),
        "avg_slippage": round(df["slippage"].mean(), 4),
        "avg_spread_cost": round(df["spread_at_entry"].dropna().mean(), 2)
    }

if __name__ == "__main__":
    # Example usage
    analysis = analyze_trades()
    print(json.dumps(analysis, indent=2))
