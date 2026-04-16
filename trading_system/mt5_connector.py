import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import time
import requests
from broker_base import Broker
from event_logger import trade_logger

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

    def connect(self, base_symbol="XAUUSD"):
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            err = mt5.last_error()
            self.logger.error("MT5 initialization failed", extra_data={"error": err})
            self.push_to_api({"log": {"level": "ERROR", "message": f"MT5 Init Failed: {err}"}})
            return False
        
        # Dynamic Symbol Selection
        selected_symbol = None
        
        # Try exact match first
        if mt5.symbol_select(base_symbol, True):
            selected_symbol = base_symbol
        else:
            # Scan for alternatives
            all_symbols = mt5.symbols_get()
            alternatives = [s.name for s in all_symbols if base_symbol in s.name]
            if alternatives:
                self.logger.info(f"Symbol {base_symbol} not found. Scanning alternatives: {alternatives}")
                for alt in alternatives:
                    if mt5.symbol_select(alt, True):
                        selected_symbol = alt
                        self.logger.info(f"Selected alternative symbol: {selected_symbol}")
                        break
        
        if not selected_symbol:
            self.logger.error(f"Failed to find or select symbol {base_symbol} or its alternatives.")
            return False
        
        self.symbol = selected_symbol # Store the resolved symbol
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

        print("📡 Sending REAL MT5 order")
        start_time = time.time()
        result = mt5.order_send(request)
        execution_delay = time.time() - start_time

        if result is None:
            err_msg = f"MT5 Order failed: Terminal returned None (Connection lost?)"
            self.logger.error(err_msg)
            self.push_to_api({"log": {"level": "ERROR", "message": err_msg}})
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            err_msg = f"MT5 Order failed: {result.retcode} ({mt5.last_error()})"
            self.logger.error(err_msg)
            self.push_to_api({"log": {"level": "ERROR", "message": err_msg}})
            return None

        print("✅ MT5 confirmed execution")
        print(f"📄 Ticket: {result.order}")
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

    def verify_order_exists(self, order_id, symbol):
        """TASK 2: Robust verification with registration wait"""
        # Short polling for registration (MT5 can have slight latency)
        for _ in range(3):
            orders = mt5.orders_get(symbol=symbol)
            if orders:
                for o in orders:
                    if o.ticket == order_id:
                        return True
            time.sleep(0.2)
        return False

    def normalize_price(self, symbol, price):
        """TASK 3: Round price to broker precision (Dynamic Digits)"""
        if price is None: return None
        info = mt5.symbol_info(symbol)
        if info is None:
            self.logger.error(f"[{self.name}] Failed to get dynamic symbol info for {symbol}")
            return None
        return round(float(price), info.digits)

    def get_valid_tick(self, symbol):
        """TASK 1: Fetch and validate recent tick (Freeze Detection)"""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None: return None
        
        # Integrity check
        if not (tick.bid > 0 and tick.ask > 0 and tick.ask > tick.bid):
            return None
            
        # Freeze detection: Ensure tick is within 2 seconds of system time
        if (time.time() - tick.time) > 2:
            delay = time.time() - tick.time
            self.logger.warning(f"[{self.name}] Market Freeze Detected: Tick is {delay:.1f}s old")
            trade_logger.log_event(symbol, "MARKET_TICK_FREEZE", details=f"Delay: {delay:.1f}s")
            return None
            
        return tick

    def is_spread_acceptable(self, symbol, max_spread_points):
        """TASK 2: Check if current spread is within limits (Atomic)"""
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if tick is None or info is None: return False
        
        # Recalculate points dynamically in case broker changes contract specs
        spread_points = round((tick.ask - tick.bid) / info.point)
        if spread_points > max_spread_points:
            self.logger.warning(f"[{self.name}] Spread Spike: {spread_points} pts > {max_spread_points} limit")
            trade_logger.log_event(symbol, "MARKET_SPREAD_SPIKE", spread=spread_points, details=f"Limit: {max_spread_points}")
            return False
        return True

    def is_trading_time(self, symbol):
        """TASK 4: Avoid market open and rollover"""
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return False
        
        server_time = datetime.fromtimestamp(tick.time)
        hour, minute = server_time.hour, server_time.minute
        
        # Avoid rollover (23:55+) and first 5 mins of open (00:00-00:05)
        if (hour == 23 and minute >= 55) or (hour == 0 and minute <= 5):
            self.logger.warning(f"[{self.name}] Outside trading window: {hour:02d}:{minute:02d}")
            return False
        return True

    def get_straddle_state(self, symbol):
        """TASK 1: Straddle State Machine"""
        # 1. Check for active positions
        positions = mt5.positions_get(symbol=symbol)
        if positions and len(positions) > 0:
            return "POSITION_ACTIVE"

        # 2. Check for pending orders
        orders = mt5.orders_get(symbol=symbol)
        if orders:
            has_buy_stop = any(o.type == mt5.ORDER_TYPE_BUY_STOP for o in orders)
            has_sell_stop = any(o.type == mt5.ORDER_TYPE_SELL_STOP for o in orders)
            
            if has_buy_stop and has_sell_stop:
                return "STRADDLE_PENDING"
        
        return "NO_STRADDLE"

    def calculate_straddle_prices(self, symbol, timeframe, buffer_points=50):
        """TASK 1: Clean straddle price calculation"""
        # 1. Get recent candles (last 20)
        df = self.get_historical_data(symbol, timeframe, 20)
        if df is None or df.empty:
            return None
            
        # 2. Find High/Low
        recent_high = df['high'].max()
        recent_low = df['low'].min()
        
        # 3. Buffer calculation
        info = mt5.symbol_info(symbol)
        if not info: return None
        buffer = buffer_points * info.point
        
        # 4. Calculate stops
        buy_stop = recent_high + buffer
        sell_stop = recent_low - buffer
        
        # 5. Normalize
        buy_stop = self.normalize_price(symbol, buy_stop)
        sell_stop = self.normalize_price(symbol, sell_stop)
        
        # 6. Ensure validity against current market
        tick = self.get_valid_tick(symbol)
        if not tick: return None
        
        if buy_stop <= tick.ask or sell_stop >= tick.bid:
            self.logger.warning(f"[{self.name}] Straddle invalid: BS({buy_stop}) <= Ask({tick.ask}) or SS({sell_stop}) >= Bid({tick.bid})")
            return None
            
        return buy_stop, sell_stop

    def execute_order_with_retry(self, symbol, order_type, volume, price=None, sl=None, tp=None, comment="", retries=3):
        """TASK 1 & 3: Stress-tested execution with Atomic Market Awareness and State Control"""
        
        # 1. Trading Window Filter (Pre-flight)
        if not self.is_trading_time(symbol):
            return None

        # TASK 2: State Control - Prevent Duplicate Placement
        state = self.get_straddle_state(symbol)
        if state in ["STRADDLE_PENDING", "POSITION_ACTIVE"]:
            self.logger.info(f"[{self.name}] State Control: {state} for {symbol}. Skipping placement.")
            return None

        for attempt in range(1, retries + 1):
            self.logger.info(f"[{self.name}] Execution attempt {attempt}/{retries} for {symbol}")
            
            # 2. Atomic Market Validation (Protects against freezes/spikes between retries)
            tick = self.get_valid_tick(symbol)
            if not tick or not self.is_spread_acceptable(symbol, 100):
                time.sleep(1)
                continue

            # 3. Dynamic Normalization (Protects against dynamic digit changes)
            n_price = self.normalize_price(symbol, price)
            n_sl = self.normalize_price(symbol, sl)
            n_tp = self.normalize_price(symbol, tp)
            
            if n_price is None and price is not None: # Info fetch failed
                time.sleep(1)
                continue

            # 4. Duplicate prevention check
            existing_orders = self.get_pending_orders(symbol)
            if any(o['type'] == ("BUY STOP" if order_type == mt5.ORDER_TYPE_BUY_STOP else "SELL STOP") for o in existing_orders):
                self.logger.warning(f"[{self.name}] Duplicate Prevention: {symbol} {comment} already exists. Skipping.")
                return None

            # 5. Execution
            # Capture spread at entry
            tick = self.get_valid_tick(symbol)
            spread = round((tick.ask - tick.bid) / mt5.symbol_info(symbol).point) if tick else None
            
            trade_logger.log_event(
                symbol, 
                "ORDER_PLACEMENT_ATTEMPT", 
                expected_price=n_price, 
                spread=spread,
                details=comment
            )
            
            order_id = self.execute_order(symbol, order_type, volume, n_price, n_sl, n_tp, comment)
            
            if order_id:
                # Log accepted with expected price to calculate slippage later
                trade_logger.log_event(
                    symbol, 
                    "ORDER_ACCEPTED", 
                    position_id=order_id, 
                    price=n_price,
                    expected_price=n_price,
                    details=f"Type: {'BUY_STOP' if order_type == mt5.ORDER_TYPE_BUY_STOP else 'SELL_STOP'}"
                )
                # Verification for pending orders
                is_pending = order_type not in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL]
                if not is_pending or self.verify_order_exists(order_id, symbol):
                    # ONLY log success after verification
                    success_msg = f"[{self.name}] Order #{order_id} confirmed and verified in book."
                    self.logger.info(success_msg)
                    self.push_to_api({"log": {"level": "EXECUTION", "message": success_msg}})
                    return order_id
                else:
                    print("❌ ORDER FAILED (Verification)")
                    self.logger.error(f"[{self.name}] Order #{order_id} placed but NOT found in book. Retrying...")
            else:
                print("❌ ORDER FAILED")
                trade_logger.log_event(symbol, "ORDER_REJECTED", expected_price=n_price, details=f"Retcode: {mt5.last_error()}")
            
            time.sleep(1) # Safety delay between retries
            
        self.logger.error(f"[{self.name}] CRITICAL: All {retries} attempts failed for {symbol}")
        return None

    def get_closed_trade_details(self, ticket):
        """Fetch historical data for a closed position"""
        from datetime import datetime
        
        # Look for deals associated with this position
        deals = mt5.history_deals_get(position=ticket)
        if not deals or len(deals) < 2:
            return None
            
        entry_deal = None
        exit_deal = None
        
        for d in deals:
            if d.entry == mt5.DEAL_ENTRY_IN:
                entry_deal = d
            elif d.entry == mt5.DEAL_ENTRY_OUT:
                exit_deal = d
                
        if not entry_deal or not exit_deal:
            return None
            
        return {
            "ticket": f"{self.name[:3]}_{ticket}",
            "type": "BUY" if entry_deal.type == mt5.DEAL_TYPE_BUY else "SELL",
            "volume": str(entry_deal.volume),
            "entryPrice": entry_deal.price,
            "exitPrice": exit_deal.price,
            "pnl": round(entry_deal.profit + exit_deal.profit + exit_deal.commission + exit_deal.swap, 2),
            "timeEntry": datetime.fromtimestamp(entry_deal.time).strftime('%H:%M:%S'),
            "timeExit": datetime.fromtimestamp(exit_deal.time).strftime('%H:%M:%S')
        }

    def shutdown(self):
        mt5.shutdown()
