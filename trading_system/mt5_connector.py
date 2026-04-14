import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import time
import requests

class MT5Connector:
    def __init__(self, login, password, server, logger, api_url=None):
        self.login = int(login)
        self.password = password
        self.server = server
        self.logger = logger
        self.api_url = api_url
        self.connected = False

    def push_to_api(self, data):
        if not self.api_url:
            return
        try:
            requests.post(f"{self.api_url}/api/update", json=data, timeout=2)
        except Exception:
            pass # Don't block if API is down

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
            
        self.logger.info(f"Connected to MT5: {account_info.login} on {account_info.server}")
        self.push_to_api({
            "log": {"level": "INFO", "message": f"Connected to MT5: {account_info.login}"},
            "account": {
                "balance": account_info.balance,
                "equity": account_info.equity,
                "marginFree": account_info.margin_free,
                "floatingPL": account_info.profit
            }
        })
        self.connected = True
        return True

    def get_tick(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            self.logger.error(f"Failed to get tick for {symbol}")
            return None
        return tick

    def get_symbol_info(self, symbol):
        info = mt5.symbol_info(symbol)
        if info is None:
            self.logger.error(f"Symbol {symbol} not found")
            return None
        if not info.visible:
            if not mt5.symbol_select(symbol, True):
                self.logger.error(f"Failed to select {symbol}")
                return None
        return info

    def execute_order(self, symbol, order_type, lot, price=None, sl=None, tp=None, comment=""):
        request = {
            "action": mt5.TRADE_ACTION_DEAL if order_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL] else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lot,
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
            self.logger.error("Order failed", extra_data={
                "retcode": result.retcode,
                "error": mt5.last_error(),
                "symbol": symbol,
                "type": order_type
            })
            return None

        self.logger.info("Order executed successfully", extra_data={
            "ticket": result.order,
            "price": result.price,
            "execution_delay": execution_delay,
            "request_price": price
        })
        return result

    def cancel_order(self, ticket):
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Failed to cancel order {ticket}", extra_data={"retcode": result.retcode})
            return False
        return True

    def close_position(self, ticket):
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return False
        
        pos = position[0]
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(pos.symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "position": ticket,
            "price": price,
            "magic": 123456,
            "comment": "Close position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE

    def shutdown(self):
        mt5.shutdown()
