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

    def apply_trailing_stop(self, connector, position):
        # position is a dict from get_positions
        point = 0.01 # Standard for XAUUSD
        current_tick = connector.get_tick(position["symbol"])
        if not current_tick: return
        
        pos_type = position["type"]
        pos_price = position["price_open"]
        pos_sl = position["sl"]
        pos_tp = position["tp"]
        ticket = position["ticket"]

        if pos_type == "BUY":
            if current_tick["bid"] - pos_price > self.trailing_stop_points * point:
                new_sl = round(current_tick["bid"] - (self.trailing_stop_points * point), 2)
                if new_sl > pos_sl + (point * 10): 
                    if connector.modify_position(ticket, new_sl, pos_tp):
                        self.logger.info(f"[{connector.__class__.__name__}] Trailing stop updated for {ticket} to {new_sl}")
        
        elif pos_type == "SELL":
            if pos_price - current_tick["ask"] > self.trailing_stop_points * point:
                new_sl = round(current_tick["ask"] + (self.trailing_stop_points * point), 2)
                if new_sl < pos_sl - (point * 10) or pos_sl == 0:
                    if connector.modify_position(ticket, new_sl, pos_tp):
                        self.logger.info(f"[{connector.__class__.__name__}] Trailing stop updated for {ticket} to {new_sl}")
