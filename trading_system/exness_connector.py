import MetaTrader5 as mt5
from mt5_connector import MT5Connector

class ExnessConnector(MT5Connector):
    def __init__(self, login, password, server, logger, api_url=None):
        super().__init__(login, password, server, logger, api_url)
        self.name = "Exness"

    def connect(self):
        # Exness often requires specific terminal settings, but we use standard MT5 lib
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            err = mt5.last_error()
            self.logger.error(f"Exness ({self.server}) connection failed", extra_data={"error": err})
            return False
        
        account_info = mt5.account_info()
        if account_info is None:
            return False
            
        self.logger.info(f"Connected to Exness: {account_info.login}")
        self.push_to_api({
            "log": {"level": "INFO", "message": f"Connected to Exness: {account_info.login}"},
            "account": self.get_account_info()
        })
        self.connected = True
        return True
