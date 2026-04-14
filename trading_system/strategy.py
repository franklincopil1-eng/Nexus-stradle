import MetaTrader5 as mt5
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
        self.pending_orders = []

    def run_iteration(self):
        # 1. Check if we have open positions
        positions = mt5.positions_get(symbol=self.symbol)
        if positions:
            # Handle trailing stop and cancel opposite pending if one triggered
            self._handle_active_positions(positions)
            return

        # 2. Check if we already have pending orders
        orders = mt5.orders_get(symbol=self.symbol)
        if orders:
            self.logger.info("Pending orders already exist, skipping placement")
            return

        # 3. Calculate High/Low of last X candles
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.lookback_candles)
        if rates is None or len(rates) == 0:
            self.logger.error("Failed to fetch rates")
            return

        df = pd.DataFrame(rates)
        recent_high = df['high'].max()
        recent_low = df['low'].min()
        
        symbol_info = self.connector.get_symbol_info(self.symbol)
        point = symbol_info.point
        
        buy_stop_price = recent_high + (self.offset_points * point)
        sell_stop_price = recent_low - (self.offset_points * point)

        # 4. Place orders
        lot = self.risk_manager.calculate_lot(mt5.account_info())
        
        # Buy Stop
        sl_buy, tp_buy = self.risk_manager.get_sl_tp(symbol_info, "BUY", buy_stop_price)
        self.connector.execute_order(self.symbol, mt5.ORDER_TYPE_BUY_STOP, lot, buy_stop_price, sl_buy, tp_buy, "Straddle Buy")
        
        # Sell Stop
        sl_sell, tp_sell = self.risk_manager.get_sl_tp(symbol_info, "SELL", sell_stop_price)
        self.connector.execute_order(self.symbol, mt5.ORDER_TYPE_SELL_STOP, lot, sell_stop_price, sl_sell, tp_sell, "Straddle Sell")

    def _handle_active_positions(self, positions):
        # If a position is open, cancel all pending orders for this symbol
        orders = mt5.orders_get(symbol=self.symbol)
        for order in orders:
            if order.type in [mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_SELL_STOP]:
                self.connector.cancel_order(order.ticket)
                self.logger.info(f"Cancelled pending order {order.ticket} as position is active")

        # Apply trailing stop
        for pos in positions:
            self.risk_manager.apply_trailing_stop(self.connector, pos)
