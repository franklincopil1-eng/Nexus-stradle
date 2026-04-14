class RiskManager:
    def __init__(self, fixed_lot, sl_points, tp_points, trailing_stop_points, logger):
        self.fixed_lot = fixed_lot
        self.sl_points = sl_points
        self.tp_points = tp_points
        self.trailing_stop_points = trailing_stop_points
        self.logger = logger

    def calculate_lot(self, account_info):
        # Simple fixed lot for MVP
        return self.fixed_lot

    def get_sl_tp(self, symbol_info, direction, entry_price):
        point = symbol_info.point
        if direction == "BUY":
            sl = entry_price - (self.sl_points * point)
            tp = entry_price + (self.tp_points * point)
        else:
            sl = entry_price + (self.sl_points * point)
            tp = entry_price - (self.tp_points * point)
        return sl, tp

    def apply_trailing_stop(self, connector, position):
        import MetaTrader5 as mt5
        symbol_info = connector.get_symbol_info(position.symbol)
        point = symbol_info.point
        current_tick = connector.get_tick(position.symbol)
        
        if position.type == mt5.POSITION_TYPE_BUY:
            if current_tick.bid - position.price_open > self.trailing_stop_points * point:
                new_sl = current_tick.bid - (self.trailing_stop_points * point)
                if new_sl > position.sl + (point * 10): # Only move if significant
                    self._modify_sl(connector, position.ticket, new_sl, position.tp)
        
        elif position.type == mt5.POSITION_TYPE_SELL:
            if position.price_open - current_tick.ask > self.trailing_stop_points * point:
                new_sl = current_tick.ask + (self.trailing_stop_points * point)
                if new_sl < position.sl - (point * 10) or position.sl == 0:
                    self._modify_sl(connector, position.ticket, new_sl, position.tp)

    def _modify_sl(self, connector, ticket, sl, tp):
        import MetaTrader5 as mt5
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": sl,
            "tp": tp
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            self.logger.info(f"Trailing stop updated for {ticket}", extra_data={"new_sl": sl})
