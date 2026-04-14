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
        # 1. Check if we have open positions
        positions = self.connector.get_positions(self.symbol)
        if positions:
            self._handle_active_positions(positions)
            return

        # 2. Check if we already have pending orders
        orders = self.connector.get_pending_orders(self.symbol)
        if orders:
            self.logger.info(f"[{self.connector.name}] Pending orders exist, skipping")
            return

        # 3. Calculate High/Low
        df = self.connector.get_historical_data(self.symbol, self.timeframe, self.lookback_candles)
        if df is None or df.empty:
            self.logger.error(f"[{self.connector.name}] Failed to fetch history")
            return

        recent_high = df['high'].max()
        recent_low = df['low'].min()
        
        # Use a fixed point value for now if not available from broker
        point = 0.01 # Standard for XAUUSD (10 points = 0.10)
        
        buy_stop_price = round(recent_high + (self.offset_points * 0.01), 2)
        sell_stop_price = round(recent_low - (self.offset_points * 0.01), 2)

        # 4. Place orders
        acc = self.connector.get_account_info()
        lot = self.risk_manager.calculate_lot(acc)
        
        # Generic order types (handled by connector)
        # We'll use MT5 constants if it's MT5, or strings for OANDA
        # For simplicity, let's pass strings and let connector handle it
        
        # Buy Stop
        sl_buy = round(buy_stop_price - (200 * 0.01), 2)
        tp_buy = round(buy_stop_price + (400 * 0.01), 2)
        
        import MetaTrader5 as mt5 # Still needed for constants if using MT5
        order_type_buy = mt5.ORDER_TYPE_BUY_STOP if "MT5" in self.connector.__class__.__name__ else "BUY_STOP"
        order_type_sell = mt5.ORDER_TYPE_SELL_STOP if "MT5" in self.connector.__class__.__name__ else "SELL_STOP"

        self.connector.execute_order(self.symbol, order_type_buy, lot, buy_stop_price, sl_buy, tp_buy, "Straddle Buy")
        self.connector.execute_order(self.symbol, order_type_sell, lot, sell_stop_price, sl_buy, tp_buy, "Straddle Sell")

    def _handle_active_positions(self, positions):
        # Cancel pending
        orders = self.connector.get_pending_orders(self.symbol)
        for order in orders:
            self.connector.cancel_order(order["ticket"])
            self.logger.info(f"[{self.connector.name}] Cancelled pending {order['ticket']}")

        # Apply trailing stop
        for pos in positions:
            self.risk_manager.apply_trailing_stop(self.connector, pos)
