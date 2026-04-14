import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import time
import requests
from broker_base import Broker

class MT5Connector(Broker):
    def __init__(self, login, password, server, logger, api_url=None):
        self.login = int(login)
        self.password = password
        self.server = server
        self.logger = logger
        self.api_url = api_url
        self.connected = False
        self.name = "MT5"

    def push_to_api(self, data):
        if not self.api_url:
            return
        try:
            requests.post(f"{self.api_url}/api/update", json=data, timeout=2)
        except Exception:
            pass 

    def get_commands(self):
        if not self.api_url:
            return []
        try:
            response = requests.get(f"{self.api_url}/api/commands", timeout=2)
            if response.status_code == 200:
                return response.json().get("commands", [])
        except Exception:
            pass
        return []

    def connect(self):
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            err = mt5.last_error()
            self.logger.error("MT5 initialization failed", extra_data={"error": err})
            self.push_to_api({"log": {"level": "ERROR", "message": f"MT5 Init Failed: {err}"}})
            return False
        
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("Failed to get account info")
            return False
            
        self.logger.info(f"Connected to {self.name}: {account_info.login} on {account_info.server}")
        self.push_to_api({
            "log": {"level": "INFO", "message": f"Connected to {self.name}: {account_info.login}"},
            "account": self.get_account_info()
        })
        self.connected = True
        return True

    def get_tick(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return {"bid": tick.bid, "ask": tick.ask, "time": tick.time}

    def get_historical_data(self, symbol, timeframe, count):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None: return None
        return pd.DataFrame(rates)

    def get_account_info(self):
        info = mt5.account_info()
        if not info: return None
        return {
            "balance": info.balance,
            "equity": info.equity,
            "marginFree": info.margin_free,
            "floatingPL": info.profit
        }

    def get_positions(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        if not positions: return []
        return [{
            "ticket": p.ticket,
            "symbol": p.symbol,
            "volume": p.volume,
            "price_open": p.price_open,
            "sl": p.sl,
            "tp": p.tp,
            "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
        } for p in positions]

    def get_pending_orders(self, symbol):
        orders = mt5.orders_get(symbol=symbol)
        if not orders: return []
        return [{
            "ticket": o.ticket,
            "symbol": o.symbol,
            "volume": o.volume,
            "price_open": o.price_open,
            "sl": o.sl,
            "tp": o.tp,
            "type": "BUY STOP" if o.type == mt5.ORDER_TYPE_BUY_STOP else "SELL STOP"
        } for o in orders]

    def execute_order(self, symbol, order_type, volume, price=None, sl=None, tp=None, comment=""):
        # Map string order types to MT5 constants if needed, but here we assume constants are passed or handled
        # For simplicity, let's assume we pass MT5 constants for now or map them
        request = {
            "action": mt5.TRADE_ACTION_DEAL if order_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL] else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "magic": 123456,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if price: request["price"] = price
        if sl: request["sl"] = sl
        if tp: request["tp"] = tp

        start_time = time.time()
        result = mt5.order_send(request)
        execution_delay = time.time() - start_time

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            err_msg = f"MT5 Order failed: {result.retcode} ({mt5.last_error()})"
            self.logger.error(err_msg)
            self.push_to_api({"log": {"level": "ERROR", "message": err_msg}})
            return None

        success_msg = f"MT5 Order #{result.order} executed. Delay: {execution_delay:.3f}s"
        self.logger.info(success_msg)
        self.push_to_api({"log": {"level": "EXECUTION", "message": success_msg}})
        return result.order

    def cancel_order(self, ticket):
        request = {"action": mt5.TRADE_ACTION_REMOVE, "order": ticket}
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE

    def modify_position(self, ticket, sl, tp):
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": sl,
            "tp": tp
        }
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE

    def shutdown(self):
        mt5.shutdown()
