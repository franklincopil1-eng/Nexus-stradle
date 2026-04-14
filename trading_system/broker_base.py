from abc import ABC, abstractmethod

class Broker(ABC):
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def get_tick(self, symbol):
        pass

    @abstractmethod
    def execute_order(self, symbol, order_type, volume, price=None, sl=None, tp=None, comment=""):
        pass

    @abstractmethod
    def cancel_order(self, ticket):
        pass

    @abstractmethod
    def get_positions(self, symbol):
        pass

    @abstractmethod
    def get_pending_orders(self, symbol):
        pass

    @abstractmethod
    def get_account_info(self):
        pass

    @abstractmethod
    def get_historical_data(self, symbol, timeframe, count):
        pass

    @abstractmethod
    def modify_position(self, ticket, sl, tp):
        pass

    @abstractmethod
    def shutdown(self):
        pass
