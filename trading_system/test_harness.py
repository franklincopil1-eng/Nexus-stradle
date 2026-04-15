import time
import unittest
from unittest.mock import MagicMock, patch
from mt5_connector import MT5Connector

class MockResult:
    def __init__(self, retcode, order=0):
        self.retcode = retcode
        self.order = order

class TestMT5Robustness(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        # Mock MT5 constants
        with patch('mt5_connector.mt5') as mock_mt5:
            mock_mt5.TRADE_RETCODE_DONE = 10009
            mock_mt5.ORDER_TYPE_BUY = 0
            mock_mt5.ORDER_TYPE_BUY_STOP = 4
            mock_mt5.TRADE_ACTION_PENDING = 5
            self.connector = MT5Connector(123, "pass", "server", self.logger)
            self.mock_mt5 = mock_mt5

    def test_case_1_mt5_returns_none(self):
        print("\n--- Testing Case 1: MT5 returns None ---")
        self.mock_mt5.order_send.return_value = None
        self.mock_mt5.orders_get.return_value = []
        
        result = self.connector.execute_order_with_retry("XAUUSD", 4, 0.01, 2000.0)
        
        self.assertIsNone(result)
        # Expected logs: 3 attempts, each logging "Terminal returned None"
        print("Expected Logs:")
        print("[INFO] [MT5] Execution attempt 1/3 for XAUUSD")
        print("[ERROR] MT5 Order failed: Terminal returned None (Connection lost?)")
        print("[INFO] [MT5] Execution attempt 2/3 for XAUUSD")
        print("[ERROR] MT5 Order failed: Terminal returned None (Connection lost?)")
        print("[INFO] [MT5] Execution attempt 3/3 for XAUUSD")
        print("[ERROR] MT5 Order failed: Terminal returned None (Connection lost?)")
        print("[ERROR] [MT5] CRITICAL: All 3 attempts failed for XAUUSD")

    def test_case_2_invalid_volume(self):
        print("\n--- Testing Case 2: Invalid Volume ---")
        # Simulate MT5 retcode for invalid volume (e.g., 10014)
        self.mock_mt5.order_send.return_value = MockResult(10014) 
        self.mock_mt5.orders_get.return_value = []
        
        result = self.connector.execute_order_with_retry("XAUUSD", 4, 999.0, 2000.0)
        
        self.assertIsNone(result)
        print("Expected Logs:")
        print("[INFO] [MT5] Execution attempt 1/3 for XAUUSD")
        print("[ERROR] MT5 Order failed: 10014 (...)")
        print("[ERROR] [MT5] CRITICAL: All 3 attempts failed for XAUUSD")

    def test_case_3_successful_order(self):
        print("\n--- Testing Case 3: Successful Order ---")
        self.mock_mt5.order_send.return_value = MockResult(10009, order=999)
        # Mock verification success
        mock_order = MagicMock()
        mock_order.ticket = 999
        self.mock_mt5.orders_get.return_value = [mock_order]
        
        # Mock valid market conditions
        mock_info = MagicMock()
        mock_info.digits = 2
        mock_info.point = 0.01
        self.mock_mt5.symbol_info.return_value = mock_info
        
        mock_tick = MagicMock()
        mock_tick.bid = 2000.0
        mock_tick.ask = 2000.1
        mock_tick.time = time.time()
        self.mock_mt5.symbol_info_tick.return_value = mock_tick
        
        result = self.connector.execute_order_with_retry("XAUUSD", 4, 0.01, 2000.0)
        
        self.assertEqual(result, 999)
        print("Expected Logs:")
        print("[INFO] [MT5] Execution attempt 1/3 for XAUUSD")
        print("[INFO] [MT5] Order #999 confirmed and verified in book.")

    def test_phase2_tick_freeze(self):
        print("\n--- Testing Phase 2: Tick Freeze Detection ---")
        mock_tick = MagicMock()
        mock_tick.bid = 2000.0
        mock_tick.ask = 2000.1
        mock_tick.time = time.time() - 10 # 10 seconds old
        self.mock_mt5.symbol_info_tick.return_value = mock_tick
        
        result = self.connector.get_valid_tick("XAUUSD")
        self.assertIsNone(result)
        print("Expected Logs:")
        print("[WARNING] [MT5] Market Freeze Detected: Tick is 10.0s old")

    def test_phase2_spread_spike(self):
        print("\n--- Testing Phase 2: Spread Spike Detection ---")
        mock_tick = MagicMock()
        mock_tick.bid = 2000.0
        mock_tick.ask = 2005.0 # 500 points spread
        self.mock_mt5.symbol_info_tick.return_value = mock_tick
        
        mock_info = MagicMock()
        mock_info.point = 0.01
        self.mock_mt5.symbol_info.return_value = mock_info
        
        result = self.connector.is_spread_acceptable("XAUUSD", 100)
        self.assertFalse(result)
        print("Expected Logs:")
        print("[WARNING] [MT5] Spread Spike: 500 pts > 100 limit")

    def test_phase2_price_normalization(self):
        print("\n--- Testing Phase 2: Price Normalization ---")
        mock_info = MagicMock()
        mock_info.digits = 3
        self.mock_mt5.symbol_info.return_value = mock_info
        
        result = self.connector.normalize_price("XAUUSD", 2000.123456)
        self.assertEqual(result, 2000.123)
        print(f"Normalized 2000.123456 to {result} (Digits: 3)")

    def test_phase3_state_no_straddle(self):
        print("\n--- Testing Phase 3: State NO_STRADDLE ---")
        self.mock_mt5.positions_get.return_value = []
        self.mock_mt5.orders_get.return_value = []
        
        state = self.connector.get_straddle_state("XAUUSD")
        self.assertEqual(state, "NO_STRADDLE")
        print(f"Detected State: {state}")

    def test_phase3_state_pending(self):
        print("\n--- Testing Phase 3: State STRADDLE_PENDING ---")
        self.mock_mt5.positions_get.return_value = []
        
        order_buy = MagicMock()
        order_buy.type = 4 # BUY_STOP
        order_sell = MagicMock()
        order_sell.type = 5 # SELL_STOP
        self.mock_mt5.orders_get.return_value = [order_buy, order_sell]
        
        state = self.connector.get_straddle_state("XAUUSD")
        self.assertEqual(state, "STRADDLE_PENDING")
        print(f"Detected State: {state}")

    def test_phase3_state_active(self):
        print("\n--- Testing Phase 3: State POSITION_ACTIVE ---")
        pos = MagicMock()
        self.mock_mt5.positions_get.return_value = [pos]
        
        state = self.connector.get_straddle_state("XAUUSD")
        self.assertEqual(state, "POSITION_ACTIVE")
        print(f"Detected State: {state}")

    def test_phase3_duplicate_prevention_via_state(self):
        print("\n--- Testing Phase 3: Duplicate Prevention via State Machine ---")
        # Simulate STRADDLE_PENDING
        self.mock_mt5.positions_get.return_value = []
        order_buy = MagicMock()
        order_buy.type = 4
        order_sell = MagicMock()
        order_sell.type = 5
        self.mock_mt5.orders_get.return_value = [order_buy, order_sell]
        
        # Mock valid time
        mock_tick = MagicMock()
        mock_tick.time = time.time()
        self.mock_mt5.symbol_info_tick.return_value = mock_tick
        
        result = self.connector.execute_order_with_retry("XAUUSD", 4, 0.01, 2000.0)
        self.assertIsNone(result)
        print("Expected Logs:")
        print("[INFO] [MT5] State Control: STRADDLE_PENDING for XAUUSD. Skipping placement.")

    def test_cleanup_opposite_order(self):
        print("\n--- Testing Cleanup of Opposite Pending Order ---")
        from strategy import StraddleStrategy
        
        # Mock active BUY position
        positions = [{"type": "BUY", "ticket": 123, "symbol": "XAUUSD", "price_open": 2000.0, "sl": 1998.0, "tp": 2004.0}]
        
        # Mock pending SELL STOP order
        pending_orders = [{"type": "SELL STOP", "ticket": 456, "symbol": "XAUUSD"}]
        self.connector.get_pending_orders = MagicMock(return_value=pending_orders)
        self.connector.cancel_order = MagicMock(return_value=True)
        
        # Mock valid tick for position management
        mock_tick = MagicMock()
        mock_tick.bid = 2000.5
        mock_tick.ask = 2000.6
        mock_tick.time = time.time()
        self.mock_mt5.symbol_info_tick.return_value = mock_tick
        
        mock_info = MagicMock()
        mock_info.point = 0.01
        mock_info.digits = 2
        self.mock_mt5.symbol_info.return_value = mock_info
        
        strategy = StraddleStrategy(self.connector, MagicMock(), "XAUUSD", None, 20, 50, self.logger)
        strategy._handle_active_positions(positions)
        
        self.connector.cancel_order.assert_called_with(456)
        print("Verified: SELL STOP order 456 was cancelled when BUY position 123 was active.")

    def test_phase4_break_even(self):
        print("\n--- Testing Phase 4: Break-even Logic ---")
        from strategy import StraddleStrategy
        
        # BUY position at 2000.0, SL at 1998.0
        # Price moves to 2001.0 (+100 points)
        positions = [{"type": "BUY", "ticket": 123, "symbol": "XAUUSD", "price_open": 2000.0, "sl": 1998.0, "tp": 2004.0}]
        
        mock_tick = MagicMock()
        mock_tick.bid = 2001.0
        mock_tick.ask = 2001.1
        mock_tick.time = time.time()
        self.mock_mt5.symbol_info_tick.return_value = mock_tick
        
        mock_info = MagicMock()
        mock_info.point = 0.01
        mock_info.digits = 2
        self.mock_mt5.symbol_info.return_value = mock_info
        
        self.connector.modify_position = MagicMock(return_value=True)
        self.connector.get_pending_orders = MagicMock(return_value=[])
        
        strategy = StraddleStrategy(self.connector, MagicMock(), "XAUUSD", None, 20, 50, self.logger)
        strategy._handle_active_positions(positions)
        
        # Should move SL to entry (2000.0)
        self.connector.modify_position.assert_called_with(123, 2000.0, 2004.0)
        print("Verified: SL moved to Break Even (2000.0) when profit reached 100 points.")

    def test_phase4_trailing_stop(self):
        print("\n--- Testing Phase 4: Trailing Stop Logic ---")
        from strategy import StraddleStrategy
        
        # BUY position at 2000.0, SL already at BE 2000.0
        # Price moves to 2002.0 (+200 points)
        # Trailing Start: 150 points, Step: 50 points
        # New SL should be 2002.0 - 0.50 = 2001.5
        positions = [{"type": "BUY", "ticket": 123, "symbol": "XAUUSD", "price_open": 2000.0, "sl": 2000.0, "tp": 2004.0}]
        
        mock_tick = MagicMock()
        mock_tick.bid = 2002.0
        mock_tick.ask = 2002.1
        mock_tick.time = time.time()
        self.mock_mt5.symbol_info_tick.return_value = mock_tick
        
        mock_info = MagicMock()
        mock_info.point = 0.01
        mock_info.digits = 2
        self.mock_mt5.symbol_info.return_value = mock_info
        
        self.connector.modify_position = MagicMock(return_value=True)
        self.connector.get_pending_orders = MagicMock(return_value=[])
        
        strategy = StraddleStrategy(self.connector, MagicMock(), "XAUUSD", None, 20, 50, self.logger)
        strategy._handle_active_positions(positions)
        
        self.connector.modify_position.assert_called_with(123, 2001.5, 2004.0)
        print("Verified: Trailing Stop moved to 2001.5 (Price 2002.0 - 50 pts).")

    def test_phase4_no_sl_regression(self):
        print("\n--- Testing Phase 4: No SL Regression ---")
        from strategy import StraddleStrategy
        
        # BUY position at 2000.0, SL already at 2001.5
        # Price drops to 2001.6 (Still in profit, but trailing would suggest 2001.1)
        # SL should NOT move backward
        positions = [{"type": "BUY", "ticket": 123, "symbol": "XAUUSD", "price_open": 2000.0, "sl": 2001.5, "tp": 2004.0}]
        
        mock_tick = MagicMock()
        mock_tick.bid = 2001.6
        mock_tick.ask = 2001.7
        mock_tick.time = time.time()
        self.mock_mt5.symbol_info_tick.return_value = mock_tick
        
        mock_info = MagicMock()
        mock_info.point = 0.01
        mock_info.digits = 2
        self.mock_mt5.symbol_info.return_value = mock_info
        
        self.connector.modify_position = MagicMock()
        self.connector.get_pending_orders = MagicMock(return_value=[])
        
        strategy = StraddleStrategy(self.connector, MagicMock(), "XAUUSD", None, 20, 50, self.logger)
        strategy._handle_active_positions(positions)
        
        self.connector.modify_position.assert_not_called()
        print("Verified: SL did NOT move backward when price dropped.")

if __name__ == "__main__":
    unittest.main()
