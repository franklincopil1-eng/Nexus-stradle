import MetaTrader5 as mt5
from mt5_connector import MT5Connector

class ExnessConnector(MT5Connector):
    def __init__(self, login, password, server, logger, api_url=None):
        super().__init__(login, password, server, logger, api_url)
        self.name = "Exness"

    def connect(self, base_symbol="XAUUSD"):
        # Exness often requires specific terminal settings, but we use standard MT5 lib
        success = super().connect(base_symbol)
        if success:
            self.logger.info(f"Connected to Exness: {self.login}")
        return success
