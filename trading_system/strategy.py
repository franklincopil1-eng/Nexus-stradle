import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from event_logger import trade_logger

class StraddleStrategy:
    def __init__(self, connector, risk_manager, symbol, timeframe, htf_timeframe, lookback_candles, offset_points, logger):
        self.connector = connector
        self.risk_manager = risk_manager
        self.symbol = symbol
        self.timeframe = timeframe # M1
        self.m5_timeframe = 5 # In minutes (MT5.TIMEFRAME_M5)
        self.htf_timeframe = htf_timeframe # M15 (MT5.TIMEFRAME_M15)
        self.lookback_candles = lookback_candles
        self.offset_points = offset_points
        self.logger = logger
        
        # Trade Lifecycle State Tracking (Step 9.1 & 9.2)
        self.active_tickets = {} # ticket: {state, entry_time, tp1_hit, alignment_score}
        self.has_placed_first_trade = False
        self.session_atr_avg = None
        self.daily_atr_avg = None

    def _calculate_indicators(self, df):
        if df is None or len(df) < 14: return None
        # ATR (14)
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        df['atr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
        # EMA 200
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))
        return df

    def _is_session_active(self):
        now = datetime.utcnow()
        return 8 <= now.hour < 21

    def _get_range_quality(self, df, high, low):
        """Step 2.5: Range Quality Filter"""
        if df is None or len(df) < self.lookback_candles: return False
        window = df.tail(self.lookback_candles)
        
        # 1. Touches (within 5% of range height)
        range_height = high - low
        threshold = range_height * 0.05
        high_touches = len(window[window['high'] >= (high - threshold)])
        low_touches = len(window[window['low'] <= (low + threshold)])
        
        # 2. No strong directional candles (> 50% of range height)
        strong_candles = len(window[abs(window['close'] - window['open']) > (range_height * 0.5)])
        
        # 3. Presence of wick rejection (Wick > Body)
        rejections = len(window[ (window['high'] - window[['open', 'close']].max(axis=1)) > abs(window['open'] - window['close']) ])
        
        is_valid = high_touches >= 2 and low_touches >= 2 and strong_candles <= 2 and rejections >= 2
        return is_valid

    def _get_alignment_case(self, m1_dir, m5_dir, m15_dir):
        """Step 2.6: Multi-Timeframe Guidance Alignment Mapping"""
        if m1_dir == m5_dir == m15_dir:
            return 1, 1.0 # Align: Full
        elif m1_dir == m5_dir:
            return 2, 0.7 # Partial: 70%
        elif m1_dir == m15_dir:
            return 2, 0.7 # Partial
        else:
            return 3, 0.4 # Conflict: 40%

    def run_iteration(self):
        # 0. Sync Active State
        positions = self.connector.get_positions(self.symbol)
        self._handle_active_positions(positions)
        
        state = self.connector.get_straddle_state(self.symbol)
        if state == "POSITION_ACTIVE":
            return

        # 1. Session Filter
        if not self._is_session_active(): return

        # 2. Data Collection (M1, M5, M15) - Step 2.1
        df_m1 = self.connector.get_historical_data(self.symbol, self.timeframe, 100)
        df_m5 = self.connector.get_historical_data(self.symbol, self.m5_timeframe, 50)
        df_m15 = self.connector.get_historical_data(self.symbol, self.htf_timeframe, 201)
        
        if any(d is None or d.empty for d in [df_m1, df_m5, df_m15]): return
        
        df_m1 = self._calculate_indicators(df_m1)
        df_m5 = self._calculate_indicators(df_m5)
        df_m15 = self._calculate_indicators(df_m15)

        # 3. Volatility Context (Step 2.4)
        curr_atr = df_m1.iloc[-1]['atr']
        # Session avg ATR calculation (dummy logic for now, in prod keep rolling daily stat)
        self.session_atr_avg = df_m1['atr'].tail(60).mean() # Last hour avg
        
        if curr_atr > self.session_atr_avg * 1.5:
            # self.logger.info("Volatility elevated - skipping setup")
            return

        # 4. Range Quality Filter (Step 2.5)
        r_high = df_m1['high'].tail(self.lookback_candles).max()
        r_low = df_m1['low'].tail(self.lookback_candles).min()
        if not self._get_range_quality(df_m1, r_high, r_low):
            return

        # 5. Multi-Timeframe Guidance (Step 2.6)
        m5_dir = "BULL" if df_m5.iloc[-1]['close'] > df_m5.iloc[-1]['ema200'] else "BEAR"
        m15_dir = "BULL" if df_m15.iloc[-1]['close'] > df_m15.iloc[-1]['ema200'] else "BEAR"
        
        # 6. Adaptive Buffer Logic (Step 3.2)
        spread = 0
        tick = self.connector.get_tick(self.symbol)
        info = None
        import MetaTrader5 as mt5
        info = mt5.symbol_info(self.symbol)
        if tick and info:
            spread = (tick['ask'] - tick['bid']) / info.point
        
        buffer_pts = max(0.2 * curr_atr / (info.point if info else 1), spread * 1.5)
        buffer = buffer_pts * (info.point if info else 1)
        
        buy_stop_price = self.connector.normalize_price(self.symbol, r_high + buffer)
        sell_stop_price = self.connector.normalize_price(self.symbol, r_low - buffer)

        # 7. Position Sizing & Confidence (Step 12.4)
        # For Straddle, we evaluate alignment for BOTH sides
        _, buy_conf = self._get_alignment_case("BULL", m5_dir, m15_dir)
        _, sell_conf = self._get_alignment_case("BEAR", m5_dir, m15_dir)
        
        acc = self.connector.get_account_info()
        sl_points = 300 # Base SL
        
        buy_lot = self.risk_manager.calculate_lot(acc['equity'], sl_points, buy_conf)
        sell_lot = self.risk_manager.calculate_lot(acc['equity'], sl_points, sell_conf)

        # 8. Execution
        if state != "NO_STRADDLE": return

        is_mt5 = "MT5" in self.connector.__class__.__name__ or "Exness" in self.connector.__class__.__name__
        order_type_buy = mt5.ORDER_TYPE_BUY_STOP if is_mt5 else "BUY_STOP"
        order_type_sell = mt5.ORDER_TYPE_SELL_STOP if is_mt5 else "SELL_STOP"

        # Adaptive SL/TP (Step 3.5)
        # Buy Side
        sl_buy = buy_stop_price - (sl_points * (info.point if info else 1) * (1.2 if m15_dir == "BEAR" else 1.0))
        tp_buy = buy_stop_price + (sl_points * 2 * (info.point if info else 1) * (1.5 if m15_dir == "BULL" else 1.0))
        
        # Sell Side
        sl_sell = sell_stop_price + (sl_points * (info.point if info else 1) * (1.2 if m15_dir == "BULL" else 1.0))
        tp_sell = sell_stop_price - (sl_points * 2 * (info.point if info else 1) * (1.5 if m15_dir == "BEAR" else 1.0))

        self.logger.info(f"[{self.connector.name}] Placing High-IQ Straddle. Buffer: {buffer_pts:.1f}pts")
        
        b_ticket = self.connector.execute_order_with_retry(self.symbol, order_type_buy, buy_lot, buy_stop_price, sl_buy, tp_buy, "M1 Straddle Upgrade")
        if b_ticket:
            self.active_tickets[b_ticket] = {"state": "ARMED", "entry_time": None, "tp1_hit": False, "conf": buy_conf, "dir": "BUY"}
            
        s_ticket = self.connector.execute_order_with_retry(self.symbol, order_type_sell, sell_lot, sell_stop_price, sl_sell, tp_sell, "M1 Straddle Upgrade")
        if s_ticket:
            self.active_tickets[s_ticket] = {"state": "ARMED", "entry_time": None, "tp1_hit": False, "conf": sell_conf, "dir": "SELL"}

    def _handle_active_positions(self, positions):
        # 1. Cleanup OCO & Missing State (Step 3.3)
        current_p_tickets = {p["ticket"] for p in positions}
        
        # Sync with MT5 pending orders too
        pending = self.connector.get_pending_orders(self.symbol)
        current_o_tickets = {o["ticket"] for o in pending}
        
        # OCO Trigger Detection (Step 3.3/3.2)
        if len(current_p_tickets) > 0 and len(current_o_tickets) > 0:
            for o_ticket in current_o_tickets:
                self.connector.cancel_order(o_ticket)
                self.logger.warning(f"OCO: Closing opposite pending order #{o_ticket}")

        # 2. Position Management per Ticket
        tick = self.connector.get_tick(self.symbol)
        import MetaTrader5 as mt5
        info = mt5.symbol_info(self.symbol)
        if not tick or not info: return

        for pos in positions:
            ticket = pos["ticket"]
            if ticket not in self.active_tickets:
                self.active_tickets[ticket] = {"state": "TRIGGERED", "entry_time": datetime.utcnow(), "tp1_hit": False, "conf": 0.5, "dir": pos['type']}
            
            p_data = self.active_tickets[ticket]
            entry_price = pos['price_open']
            cur_sl = pos['sl']
            cur_tp = pos['tp']
            
            # Step 4.1: Breakout Strength Validation (Candle Close)
            if p_data['state'] == "TRIGGERED":
                # Check current M1 candle
                df = self.connector.get_historical_data(self.symbol, self.timeframe, 1)
                if df is not None and not df.empty:
                    last_c = df.iloc[-1]
                    # If candle closed (time difference > 1min)
                    # We check weakness
                    body = abs(last_c['close'] - last_c['open'])
                    high_wick = last_c['high'] - max(last_c['close'], last_c['open'])
                    low_wick = min(last_c['close'], last_c['open']) - last_c['low']
                    wick = high_wick if pos['type'] == "BUY" else low_wick
                    
                    if body < wick: # Weak breakout (Step 4.1)
                        self.logger.warning(f"Weak Breakout Detected. Exiting Early #{ticket}")
                        self.connector.close_position(ticket, self.symbol)
                        continue
                    p_data['state'] = "VALIDATED"

            # Step 4.2: Partial Take Profit (1R)
            sl_dist = abs(entry_price - cur_sl) if cur_sl != 0 else (300 * info.point)
            profit_pts = (tick['bid'] - entry_price) if pos['type'] == "BUY" else (entry_price - tick['ask'])
            
            if not p_data['tp1_hit'] and profit_pts >= sl_dist:
                self.logger.info(f"TP1 (1R) Reached. Closing 50% of #{ticket}")
                if self.connector.close_position(ticket, self.symbol, volume=pos['volume']/2):
                    p_data['tp1_hit'] = True
                    p_data['state'] = "SCALE_OUT"
                    # Move to Break Even immediately (Step 9.3)
                    self.connector.modify_position(ticket, entry_price, cur_tp)
            
            # Step 4.3: Momentum Acceleration Mode
            # Detect 2-3x size candles
            df = self.connector.get_historical_data(self.symbol, self.timeframe, 5)
            if df is not None:
                avg_body = abs(df['close'] - df['open']).mean()
                curr_body = abs(df.iloc[-1]['close'] - df.iloc[-1]['open'])
                if curr_body > avg_body * 2.5:
                    # Momentum acceleration actions (extend TP, delay trailing)
                    pass

            # Step 9.2: Smart Trailing Logic
            self.risk_manager.apply_trailing_stop(self.connector, pos)
