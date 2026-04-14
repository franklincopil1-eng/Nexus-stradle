import os
import time
from dotenv import load_dotenv
import MetaTrader5 as mt5
from logger import setup_logger
from mt5_connector import MT5Connector
from risk_manager import RiskManager
from strategy import StraddleStrategy

# Load environment variables
load_dotenv()

# Configuration
SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_M5
LOOKBACK_CANDLES = 12 # 1 hour if M5
OFFSET_POINTS = 50
FIXED_LOT = 0.01
SL_POINTS = 200
TP_POINTS = 400
TRAILING_STOP_POINTS = 150
ITERATION_SLEEP = 60 # Check every minute

def main():
    logger = setup_logger()
    logger.info("Starting XAUUSD Trading MVP")

    # Initialize Connector
    connector = MT5Connector(
        login=os.getenv("MT5_LOGIN"),
        password=os.getenv("MT5_PASSWORD"),
        server=os.getenv("MT5_SERVER"),
        logger=logger,
        api_url=os.getenv("API_URL")
    )

    if not connector.connect():
        logger.error("Failed to connect to MT5. Exiting.")
        return

    # Initialize Risk Manager
    risk_manager = RiskManager(
        fixed_lot=FIXED_LOT,
        sl_points=SL_POINTS,
        tp_points=TP_POINTS,
        trailing_stop_points=TRAILING_STOP_POINTS,
        logger=logger
    )

    # Initialize Strategy
    strategy = StraddleStrategy(
        connector=connector,
        risk_manager=risk_manager,
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        lookback_candles=LOOKBACK_CANDLES,
        offset_points=OFFSET_POINTS,
        logger=logger
    )

    try:
        while True:
            logger.info(f"Running iteration at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Fetch current state to push to API
            tick = connector.get_tick(SYMBOL)
            account_info = mt5.account_info()
            positions = mt5.positions_get(symbol=SYMBOL)
            orders = mt5.orders_get(symbol=SYMBOL)
            
            # Format orders/positions for the dashboard
            all_orders = []
            if positions:
                for p in positions:
                    all_orders.append({
                        "ticket": f"#{p.ticket}",
                        "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                        "volume": str(p.volume),
                        "price": str(p.price_open),
                        "sl": str(p.sl),
                        "tp": str(p.tp),
                        "status": "OPEN"
                    })
            if orders:
                for o in orders:
                    all_orders.append({
                        "ticket": f"#{o.ticket}",
                        "type": "BUY STOP" if o.type == mt5.ORDER_TYPE_BUY_STOP else "SELL STOP",
                        "volume": str(o.volume),
                        "price": str(o.price_open),
                        "sl": str(o.sl),
                        "tp": str(o.tp),
                        "status": "PENDING"
                    })

            if tick and account_info:
                connector.push_to_api({
                    "price": tick.bid,
                    "spread": round((tick.ask - tick.bid) / mt5.symbol_info(SYMBOL).point / 10, 1),
                    "account": {
                        "balance": account_info.balance,
                        "equity": account_info.equity,
                        "marginFree": account_info.margin_free,
                        "floatingPL": account_info.profit
                    },
                    "orders": all_orders
                })

            strategy.run_iteration()
            time.sleep(ITERATION_SLEEP)
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    finally:
        connector.shutdown()
        logger.info("System shutdown complete")

if __name__ == "__main__":
    main()
