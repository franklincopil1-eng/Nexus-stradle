import json
import os
from datetime import datetime

class TradeEventLogger:
    def __init__(self, log_file="logs/trade_events.jsonl"):
        self.log_file = log_file
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def log_event(self, symbol, event_type, price=None, expected_price=None, actual_price=None, spread=None, position_id=None, details=None):
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "symbol": symbol,
            "event_type": event_type,
            "price": price,
            "expected_price": expected_price,
            "actual_price": actual_price,
            "spread": spread,
            "position_id": position_id,
            "details": details
        }
        
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"Failed to log trade event: {e}")

# Global instance for easy access
trade_logger = TradeEventLogger()
