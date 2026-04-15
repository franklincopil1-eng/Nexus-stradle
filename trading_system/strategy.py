import pandas as pd
from datetime import datetime, timedelta

class StraddleStrategy:
    def __init__(self, connector, risk_manager, symbol, timeframe, lookback_candles, offset_points, logger):
        self.connector = connector
        self.risk_manager = risk_manager
        self.symbol = symbol
        self.timeframe = timeframe
        self.lookback_candles = lookback_candles
        self.offset_points = offset_points
        self.logger = logger

    def run_iteration(self):
        # 1. Get state
        state = self.connector.get_straddle_state(self.symbol)

        # 2. If state != NO_STRADDLE → EXIT (Handle positions if active)
        if state == "POSITION_ACTIVE":
            positions = self.connector.get_positions(self.symbol)
            self._handle_active_positions(positions)
            return
            
        if state != "NO_STRADDLE":
            return

        # 3. Calculate straddle prices
        prices = self.connector.calculate_straddle_prices(self.symbol, self.timeframe, self.offset_points)
        
        # 4. If None → EXIT
        if not prices:
            return
        buy_stop_price, sell_stop_price = prices

        # 5. Place: Buy Stop, Sell Stop
        acc = self.connector.get_account_info()
        lot = self.risk_manager.calculate_lot(acc)
        
        # Calculate SL/TP
        sl_buy = round(buy_stop_price - (200 * 0.01), 2)
        tp_buy = round(buy_stop_price + (400 * 0.01), 2)
        sl_sell = round(sell_stop_price + (200 * 0.01), 2)
        tp_sell = round(sell_stop_price - (400 * 0.01), 2)

        import MetaTrader5 as mt5
        is_mt5 = any(x in self.connector.__class__.__name__ for x in ["MT5", "Exness", "Valetax", "Pepperstone"])
        order_type_buy = mt5.ORDER_TYPE_BUY_STOP if is_mt5 else "BUY_STOP"
        order_type_sell = mt5.ORDER_TYPE_SELL_STOP if is_mt5 else "SELL_STOP"

        self.logger.info(f"[{self.connector.name}] Placing clean straddle at {buy_stop_price} / {sell_stop_price}")
        self.connector.execute_order_with_retry(self.symbol, order_type_buy, lot, buy_stop_price, sl_buy, tp_buy, "Straddle Buy")
        self.connector.execute_order_with_retry(self.symbol, order_type_sell, lot, sell_stop_price, sl_sell, tp_sell, "Straddle Sell")

    def _handle_active_positions(self, positions):
        # Cancel pending
        orders = self.connector.get_pending_orders(self.symbol)
        for order in orders:
            self.connector.cancel_order(order["ticket"])
            self.logger.info(f"[{self.connector.name}] Cancelled pending {order['ticket']}")

        # Apply trailing stop
        for pos in positions:
            self.risk_manager.apply_trailing_stop(self.connector, pos)
