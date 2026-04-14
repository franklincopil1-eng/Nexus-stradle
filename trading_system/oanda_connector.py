import v20
import v20.transaction
import time
import requests
from broker_base import Broker

class OandaConnector(Broker):
    def __init__(self, access_token, account_id, environment, logger, api_url=None):
        self.access_token = access_token
        self.account_id = account_id
        self.environment = environment # 'practice' or 'live'
        self.logger = logger
        self.api_url = api_url
        self.ctx = None
        self.connected = False
        self.name = "OANDA"

    def push_to_api(self, data):
        if not self.api_url:
            return
        try:
            requests.post(f"{self.api_url}/api/update", json=data, timeout=2)
        except Exception:
            pass

    def connect(self):
        try:
            hostname = 'api-fxtrade.oanda.com' if self.environment == 'live' else 'api-fxpractice.oanda.com'
            self.ctx = v20.Context(hostname, 443, True, application="trading_mvp", token=self.access_token)
            
            # Test connection by getting account summary
            response = self.ctx.account.summary(self.account_id)
            if response.status != 200:
                self.logger.error(f"OANDA connection failed: {response.body.get('errorMessage')}")
                return False
            
            self.logger.info(f"Connected to {self.name}: {self.account_id} ({self.environment})")
            self.push_to_api({
                "log": {"level": "INFO", "message": f"Connected to {self.name}: {self.account_id}"},
                "account": self.get_account_info()
            })
            self.connected = True
            return True
        except Exception as e:
            self.logger.error(f"OANDA connection error: {str(e)}")
            return False

    def get_tick(self, symbol):
        # OANDA symbol format is usually XAU_USD
        oanda_symbol = symbol.replace("USD", "_USD")
        try:
            response = self.ctx.pricing.get(self.account_id, instruments=oanda_symbol)
            if response.status == 200:
                price = response.body.get("prices")[0]
                return {
                    "bid": float(price.bids[0].price),
                    "ask": float(price.asks[0].price),
                    "time": price.time
                }
        except Exception:
            pass
        return None

    def get_historical_data(self, symbol, timeframe, count):
        oanda_symbol = symbol.replace("USD", "_USD")
        # Map MT5 timeframe to OANDA granularity
        granularity = "M5" # Default for now
        try:
            response = self.ctx.instrument.candles(oanda_symbol, count=count, granularity=granularity)
            if response.status == 200:
                candles = response.body.get("candles")
                data = []
                for c in candles:
                    data.append({
                        "time": c.time,
                        "open": float(c.mid.o),
                        "high": float(c.mid.h),
                        "low": float(c.mid.l),
                        "close": float(c.mid.c)
                    })
                import pandas as pd
                return pd.DataFrame(data)
        except Exception:
            pass
        return None

    def get_account_info(self):
        try:
            response = self.ctx.account.summary(self.account_id)
            if response.status == 200:
                acc = response.body.get("account")
                return {
                    "balance": float(acc.balance),
                    "equity": float(acc.NAV),
                    "marginFree": float(acc.marginAvailable),
                    "floatingPL": float(acc.unrealizedPL)
                }
        except Exception:
            pass
        return None

    def get_positions(self, symbol):
        # OANDA positions are aggregate. We look at open trades for individual tickets.
        try:
            response = self.ctx.trade.list_open(self.account_id)
            if response.status == 200:
                trades = response.body.get("trades")
                oanda_symbol = symbol.replace("USD", "_USD")
                return [{
                    "ticket": t.id,
                    "symbol": symbol,
                    "volume": float(t.currentUnits),
                    "price_open": float(t.price),
                    "sl": float(t.stopLossOrder.price) if hasattr(t, 'stopLossOrder') and t.stopLossOrder else 0,
                    "tp": float(t.takeProfitOrder.price) if hasattr(t, 'takeProfitOrder') and t.takeProfitOrder else 0,
                    "type": "BUY" if float(t.currentUnits) > 0 else "SELL"
                } for t in trades if t.instrument == oanda_symbol]
        except Exception:
            pass
        return []

    def get_pending_orders(self, symbol):
        try:
            response = self.ctx.order.list_pending(self.account_id)
            if response.status == 200:
                orders = response.body.get("orders")
                oanda_symbol = symbol.replace("USD", "_USD")
                return [{
                    "ticket": o.id,
                    "symbol": symbol,
                    "volume": float(o.units),
                    "price_open": float(o.price),
                    "sl": float(o.stopLossOnFill.price) if hasattr(o, 'stopLossOnFill') and o.stopLossOnFill else 0,
                    "tp": float(o.takeProfitOnFill.price) if hasattr(o, 'takeProfitOnFill') and o.takeProfitOnFill else 0,
                    "type": "BUY STOP" if float(o.units) > 0 else "SELL STOP"
                } for o in orders if o.instrument == oanda_symbol and o.type == "STOP"]
        except Exception:
            pass
        return []

    def execute_order(self, symbol, order_type, volume, price=None, sl=None, tp=None, comment=""):
        oanda_symbol = symbol.replace("USD", "_USD")
        # Map MT5 constants to OANDA types if needed, or use strings
        # For MVP, we'll handle BUY_STOP and SELL_STOP
        
        start_time = time.time()
        try:
            order_spec = {
                "instrument": oanda_symbol,
                "units": str(volume if "BUY" in str(order_type) else -volume),
                "timeInForce": "GTC",
            }
            
            if "STOP" in str(order_type):
                order_spec["type"] = "STOP"
                order_spec["price"] = str(price)
            else:
                order_spec["type"] = "MARKET"

            if sl: order_spec["stopLossOnFill"] = {"price": str(sl)}
            if tp: order_spec["takeProfitOnFill"] = {"price": str(tp)}

            response = self.ctx.order.create(self.account_id, order=order_spec)
            execution_delay = time.time() - start_time

            if response.status != 201:
                err_msg = f"OANDA Order failed: {response.body.get('errorMessage')}"
                self.logger.error(err_msg)
                self.push_to_api({"log": {"level": "ERROR", "message": err_msg}})
                return None

            order_id = response.body.get("orderCreateTransaction").id
            success_msg = f"OANDA Order #{order_id} placed. Delay: {execution_delay:.3f}s"
            self.logger.info(success_msg)
            self.push_to_api({"log": {"level": "EXECUTION", "message": success_msg}})
            return order_id
        except Exception as e:
            self.logger.error(f"OANDA execution error: {str(e)}")
            return None

    def cancel_order(self, ticket):
        try:
            response = self.ctx.order.cancel(self.account_id, ticket)
            return response.status == 200
        except Exception:
            return False

    def modify_position(self, ticket, sl, tp):
        try:
            # OANDA modifies trades, not positions
            order_spec = {}
            if sl: order_spec["stopLoss"] = {"price": str(sl)}
            if tp: order_spec["takeProfit"] = {"price": str(tp)}
            
            response = self.ctx.trade.set_dependent_orders(self.account_id, ticket, **order_spec)
            return response.status == 200
        except Exception:
            return False

    def shutdown(self):
        self.connected = False
