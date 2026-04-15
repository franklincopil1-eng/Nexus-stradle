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

if __name__ == "__main__":
    unittest.main()
