import MetaTrader5 as mt5
from mt5_connector import MT5Connector

class PepperstoneConnector(MT5Connector):
    def __init__(self, login, password, server, logger, api_url=None):
        super().__init__(login, password, server, logger, api_url)
        self.name = "Pepperstone"

    def connect(self):
        success = super().connect()
        if success:
            self.logger.info(f"Connected to Pepperstone Kenya: {self.login}")
        return success
