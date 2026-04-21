class RiskManager:
    def __init__(self, fixed_lot, max_risk_percent, sl_points, tp_points, trailing_stop_points, logger):
        self.fixed_lot = fixed_lot
        self.max_risk_percent = max_risk_percent / 100.0
        self.sl_points = sl_points
        self.tp_points = tp_points
        self.trailing_stop_points = trailing_stop_points
        self.logger = logger
        self.consecutive_losses = 0

    def calculate_lot(self, equity, sl_points, confidence_multiplier=1.0):
        """
        Calculates lot size based on equity risk and strategy confidence.
        Multi-Timeframe guidance applies multipliers:
        - Case 1 (Align): 1.0
        - Case 2 (Partial): 0.7
        - Case 3 (Conflict): 0.3 - 0.5
        """
        # Loss recovery logic (Step 10.1)
        recovery_multiplier = 1.0
        if self.consecutive_losses >= 2:
            recovery_multiplier = 0.5
            self.logger.warning(f"Risk Manager: Applying loss recovery multiplier (0.5x) due to {self.consecutive_losses} losses.")

        if equity <= 0: return self.fixed_lot

        # Standard lot value calculation (assuming XAUUSD gold 100oz contracts)
        # Risk = Equity * Risk%
        risk_amount = equity * self.max_risk_percent
        
        # Points to Cash (Gold 0.01 = 1 point)
        # Lot = Risk / (SL_points * 1.0) # Approx for 0.01 point = $1 profit on 1 lot
        potential_lot = risk_amount / (sl_points if sl_points > 0 else self.sl_points)
        
        # Apply multipliers
        final_lot = potential_lot * confidence_multiplier * recovery_multiplier
        
        # Min/Max sanity checks
        final_lot = max(0.01, round(final_lot, 2))
        
        # Cap at fixed_lot for safety during testing if requested
        if self.fixed_lot > 0:
            final_lot = min(final_lot, self.fixed_lot)
            
        return final_lot

    def update_loss_state(self, profit):
        if profit < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

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
