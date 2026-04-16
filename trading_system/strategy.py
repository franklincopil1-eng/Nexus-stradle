import pandas as pd
from datetime import datetime, timedelta
from event_logger import trade_logger

class StraddleStrategy:
    def __init__(self, connector, risk_manager, symbol, timeframe, lookback_candles, offset_points, logger):
        self.connector = connector
        self.risk_manager = risk_manager
        self.symbol = "XAUUSDm" # HARD WIRED SYMBOL
        self.timeframe = timeframe
        self.lookback_candles = lookback_candles
        self.offset_points = offset_points
        self.logger = logger
        self.active_tickets = set() # Track active tickets for exit detection
        self.has_placed_first_trade = False # FORCE FIRST TRADE FLAG

    def run_iteration(self):
        # 1. Get state
        state = self.connector.get_straddle_state(self.symbol)

        # 2. If state != NO_STRADDLE → EXIT (Handle positions if active)
        if state == "POSITION_ACTIVE":
            positions = self.connector.get_positions(self.symbol)
            self._handle_active_positions(positions)
            return
            
        # FORCE FIRST TRADE LOGIC
        if not self.has_placed_first_trade:
            print("🔥 LIVE TRADE TEST TRIGGERED")
            print("📢 SIGNAL GENERATED (FORCED FIRST TRADE)")
        elif state != "NO_STRADDLE":
            return

        # 3. Calculate straddle prices
        prices = self.connector.calculate_straddle_prices(self.symbol, self.timeframe, self.offset_points)
        
        # 4. If None → EXIT
        if not prices:
            return
        buy_stop_price, sell_stop_price = prices
        
        if self.has_placed_first_trade:
            print("📢 SIGNAL GENERATED")

        # 5. Place: Buy Stop, Sell Stop
        acc = self.connector.get_account_info()
        lot = 0.01 # HARD LIMIT LOT SIZE
        
        # Calculate SL/TP
        sl_buy = round(buy_stop_price - (200 * 0.01), 2)
        tp_buy = round(buy_stop_price + (400 * 0.01), 2)
        sl_sell = round(sell_stop_price + (200 * 0.01), 2)
        tp_sell = round(sell_stop_price - (400 * 0.01), 2)

        import MetaTrader5 as mt5
        is_mt5 = any(x in self.connector.__class__.__name__ for x in ["MT5", "Exness", "Valetax", "Pepperstone"])
        order_type_buy = mt5.ORDER_TYPE_BUY_STOP if is_mt5 else "BUY_STOP"
        order_type_sell = mt5.ORDER_TYPE_SELL_STOP if is_mt5 else "SELL_STOP"

        print("🚀 SENDING ORDER TO MT5")
        self.logger.info(f"[{self.connector.name}] Placing clean straddle at {buy_stop_price} / {sell_stop_price}")
        
        self.connector.execute_order_with_retry(self.symbol, order_type_buy, lot, buy_stop_price, sl_buy, tp_buy, "Straddle Buy")
        self.connector.execute_order_with_retry(self.symbol, order_type_sell, lot, sell_stop_price, sl_sell, tp_sell, "Straddle Sell")
        
        self.has_placed_first_trade = True

    def _handle_active_positions(self, positions):
        # 0. Detect Exits (SL/TP)
        current_tickets = {p["ticket"] for p in positions}
        exited_tickets = self.active_tickets - current_tickets
        
        for ticket in exited_tickets:
            # Log exit (In a real system, we'd fetch the actual exit price from history)
            # For now, we log that it closed.
            trade_logger.log_event(
                self.symbol, 
                "POSITION_CLOSED", 
                position_id=ticket,
                details="Position no longer found in active list (SL/TP/Manual)"
            )
        
        self.active_tickets = current_tickets

        # 1. Detect active position types
        has_buy = any(p["type"] == "BUY" for p in positions)
        has_sell = any(p["type"] == "SELL" for p in positions)

        # 2. Fetch all pending orders for the symbol
        orders = self.connector.get_pending_orders(self.symbol)

        # 3. Logic: Cleanup opposite pending orders
        for order in orders:
            if has_buy and order["type"] == "SELL STOP":
                self.connector.cancel_order(order["ticket"])
                self.logger.info(f"[{self.connector.name}] Removed opposite pending order: SELL STOP")
            elif has_sell and order["type"] == "BUY STOP":
                self.connector.cancel_order(order["ticket"])
                self.logger.info(f"[{self.connector.name}] Removed opposite pending order: BUY STOP")

        # 4. Professional Position Management
        import MetaTrader5 as mt5
        tick = self.connector.get_valid_tick(self.symbol)
        info = mt5.symbol_info(self.symbol)
        if not tick or not info:
            return

        point = info.point
        be_trigger = 100 # points
        ts_start = 150   # points
        ts_step = 50     # points

        for pos in positions:
            ticket = pos["ticket"]
            entry_price = pos["price_open"]
            current_sl = pos["sl"]
            pos_type = pos["type"]
            tp = pos["tp"]
            
            # Log Market Update for MFE/MAE
            current_price = tick.bid if pos_type == "BUY" else tick.ask
            trade_logger.log_event(
                self.symbol,
                "POSITION_MARKET_UPDATE",
                position_id=ticket,
                price=current_price,
                details=f"Type: {pos_type}"
            )
            
            new_sl = None
            log_msg = ""
            
            if pos_type == "BUY":
                current_price = tick.bid
                profit_points = (current_price - entry_price) / point
                
                # Trailing Logic
                if profit_points >= ts_start:
                    potential_sl = current_price - (ts_step * point)
                    # Only update if it improves SL and is meaningful (>10 points)
                    if potential_sl > current_sl + (10 * point):
                        new_sl = potential_sl
                        log_msg = "Trailing Stop Updated"
                
                # Break Even Logic
                elif profit_points >= be_trigger:
                    if current_sl < entry_price:
                        new_sl = entry_price
                        log_msg = "Moved SL to Break Even"
            
            elif pos_type == "SELL":
                current_price = tick.ask
                profit_points = (entry_price - current_price) / point
                
                # Trailing Logic
                if profit_points >= ts_start:
                    potential_sl = current_price + (ts_step * point)
                    # Only update if it improves SL (lower for SELL) and is meaningful
                    if current_sl == 0 or potential_sl < current_sl - (10 * point):
                        new_sl = potential_sl
                        log_msg = "Trailing Stop Updated"
                
                # Break Even Logic
                elif profit_points >= be_trigger:
                    if current_sl == 0 or current_sl > entry_price:
                        new_sl = entry_price
                        log_msg = "Moved SL to Break Even"

            if new_sl is not None:
                new_sl = self.connector.normalize_price(self.symbol, new_sl)
                if self.connector.modify_position(ticket, new_sl, tp):
                    self.logger.info(f"[{self.connector.name}] {log_msg} for #{ticket} to {new_sl}")
                    
                    # Log event
                    event_type = "POSITION_BREAK_EVEN" if log_msg == "Moved SL to Break Even" else "POSITION_TRAILING_UPDATE"
                    trade_logger.log_event(
                        self.symbol, 
                        event_type, 
                        price=new_sl, 
                        position_id=ticket, 
                        details=f"New SL: {new_sl}"
                    )
