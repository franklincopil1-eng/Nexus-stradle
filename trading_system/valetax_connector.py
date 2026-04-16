import MetaTrader5 as mt5
from mt5_connector import MT5Connector

class ValetaxConnector(MT5Connector):
    def __init__(self, login, password, server, logger, api_url=None):
        super().__init__(login, password, server, logger, api_url)
        self.name = "Valetax"

    def connect(self, base_symbol="XAUUSD"):
        success = super().connect(base_symbol)
        if success:
            self.logger.info(f"Connected to Valetax: {self.login}")
        return success
