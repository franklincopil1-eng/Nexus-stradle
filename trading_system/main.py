import os
import time
from dotenv import load_dotenv
import MetaTrader5 as mt5
from logger import setup_logger
from mt5_connector import MT5Connector
from oanda_connector import OandaConnector
from exness_connector import ExnessConnector
from valetax_connector import ValetaxConnector
from pepperstone_connector import PepperstoneConnector
from risk_manager import RiskManager
from strategy import StraddleStrategy

# Load environment variables
load_dotenv()

# Configuration
SYMBOL = "XAUUSDm"
TIMEFRAME = mt5.TIMEFRAME_M1 # Primary timeframe: 1 min
HTF_TIMEFRAME = mt5.TIMEFRAME_M15 # Higher timeframe: 15 min
LOOKBACK_CANDLES = 12 
OFFSET_POINTS = 50
FIXED_LOT = 0.01
SL_POINTS = 200
TP_POINTS = 400
TRAILING_STOP_POINTS = 150
ITERATION_SLEEP = 5 

def main():
    logger = setup_logger()
    logger.info("Starting XAUUSD Trading MVP (Multi-Broker)")

    brokers = []

    # Helper to add MT5 brokers
    def add_mt5_broker(prefix, name):
        login = os.getenv(f"{prefix}_LOGIN")
        if login:
            broker = MT5Connector(
                login=login,
                password=os.getenv(f"{prefix}_PASSWORD"),
                server=os.getenv(f"{prefix}_SERVER"),
                logger=logger,
                api_url=os.getenv("API_URL")
            )
            # Set a custom name for the broker instance
            broker.name = name
            if broker.connect(SYMBOL):
                brokers.append(broker)
                # Update global SYMBOL to the resolved one if it's the primary broker
                if name == "Primary MT5":
                    global SYMBOL
                    SYMBOL = broker.symbol
            else:
                logger.warning(f"{name} connection failed, skipping.")

    # Initialize specific MT5 Brokers
    add_mt5_broker("MT5", "Primary MT5")
    
    # Exness Kenya
    if os.getenv("EXNESS_LOGIN"):
        exness = ExnessConnector(
            login=os.getenv("EXNESS_LOGIN"),
            password=os.getenv("EXNESS_PASSWORD"),
            server=os.getenv("EXNESS_SERVER"),
            logger=logger,
            api_url=os.getenv("API_URL")
        )
        if exness.connect(SYMBOL): brokers.append(exness)

    # Valetax
    if os.getenv("VALETAX_LOGIN"):
        valetax = ValetaxConnector(
            login=os.getenv("VALETAX_LOGIN"),
            password=os.getenv("VALETAX_PASSWORD"),
            server=os.getenv("VALETAX_SERVER"),
            logger=logger,
            api_url=os.getenv("API_URL")
        )
        if valetax.connect(SYMBOL): brokers.append(valetax)

    # Pepperstone
    if os.getenv("PEPPERSTONE_LOGIN"):
        pepperstone = PepperstoneConnector(
            login=os.getenv("PEPPERSTONE_LOGIN"),
            password=os.getenv("PEPPERSTONE_PASSWORD"),
            server=os.getenv("PEPPERSTONE_SERVER"),
            logger=logger,
            api_url=os.getenv("API_URL")
        )
        if pepperstone.connect(SYMBOL): brokers.append(pepperstone)

    # Initialize OANDA if credentials exist
    if os.getenv("OANDA_ACCESS_TOKEN"):
        oanda_broker = OandaConnector(
            access_token=os.getenv("OANDA_ACCESS_TOKEN"),
            account_id=os.getenv("OANDA_ACCOUNT_ID"),
            environment=os.getenv("OANDA_ENV", "practice"),
            logger=logger,
            api_url=os.getenv("API_URL")
        )
        if oanda_broker.connect(SYMBOL):
            brokers.append(oanda_broker)
        else:
            logger.warning("OANDA connection failed, skipping.")

    if not brokers:
        logger.error("No brokers connected. Exiting.")
        return

    # Initialize Risk Manager
    risk_manager = RiskManager(
        fixed_lot=FIXED_LOT,
        sl_points=SL_POINTS,
        tp_points=TP_POINTS,
        trailing_stop_points=TRAILING_STOP_POINTS,
        logger=logger
    )

    # Initialize Strategies (one per broker)
    strategies = []
    for broker in brokers:
        strategies.append(StraddleStrategy(
            connector=broker,
            risk_manager=risk_manager,
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            htf_timeframe=HTF_TIMEFRAME, # Pass HTF
            lookback_candles=LOOKBACK_CANDLES,
            offset_points=OFFSET_POINTS,
            logger=logger
        ))

    is_halted = False

    try:
        while True:
            print("\n🚀 LOOP START")
            logger.info(f"Running iteration at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Use the first broker for UI commands and global state for now
            primary_broker = brokers[0]
            commands = primary_broker.get_commands()
            
            for cmd in commands:
                if cmd == "HALT":
                    is_halted = True
                    logger.warning("SYSTEM HALTED BY UI")
                    for broker in brokers:
                        orders = broker.get_pending_orders(SYMBOL)
                        for o in orders:
                            broker.cancel_order(o["ticket"])
                elif cmd == "RESUME":
                    is_halted = False
                    logger.info("SYSTEM RESUMED BY UI")
                elif cmd == "CLOSE_ALL":
                    logger.warning("CLOSING ALL POSITIONS BY UI")
                    for broker in brokers:
                        positions = broker.get_positions(SYMBOL)
                        for p in positions:
                            # Close position by executing opposite market order
                            side = "SELL" if p["type"] == "BUY" else "BUY"
                            import MetaTrader5 as mt5
                            order_type = mt5.ORDER_TYPE_SELL if side == "SELL" else mt5.ORDER_TYPE_BUY
                            if "Oanda" in broker.__class__.__name__:
                                order_type = side
                            broker.execute_order(SYMBOL, order_type, p["volume"], comment="Close All")

            # Update UI with aggregate state
            all_orders = []
            total_equity = 0
            total_profit = 0
            total_balance = 0
            total_margin_free = 0
            broker_stats = []
            
            primary_tick = brokers[0].get_tick(SYMBOL)
            spread = (primary_tick["ask"] - primary_tick["bid"]) * 100 if primary_tick else 0 # in points
            
            # Get range data from primary broker
            df = brokers[0].get_historical_data(SYMBOL, TIMEFRAME, LOOKBACK_CANDLES)
            range_high = df['high'].max() if df is not None and not df.empty else 0
            range_low = df['low'].min() if df is not None and not df.empty else 0

            for broker in brokers:
                acc = broker.get_account_info()
                positions = broker.get_positions(SYMBOL)
                orders = broker.get_pending_orders(SYMBOL)
                
                if acc:
                    total_balance += acc["balance"]
                    total_equity += acc["equity"]
                    total_margin_free += acc["marginFree"]
                    total_profit += acc["floatingPL"]
                    
                    broker_stats.append({
                        "name": broker.name,
                        "balance": acc["balance"],
                        "equity": acc["equity"],
                        "profit": acc["floatingPL"],
                        "status": "CONNECTED"
                    })
                
                for p in positions:
                    all_orders.append({**p, "ticket": f"{broker.name[:3]}_{p['ticket']}", "status": "OPEN"})
                for o in orders:
                    all_orders.append({**o, "ticket": f"{broker.name[:3]}_{o['ticket']}", "status": "PENDING"})

            # Push aggregate state to API
            primary_broker.push_to_api({
                "price": primary_tick["bid"] if primary_tick else 0,
                "spread": round(spread, 1),
                "rangeHigh": range_high,
                "rangeLow": range_low,
                "riskSettings": {
                    "fixedLot": FIXED_LOT,
                    "slPoints": SL_POINTS,
                    "tpPoints": TP_POINTS,
                    "trailingStop": TRAILING_STOP_POINTS,
                    "lookback": LOOKBACK_CANDLES
                },
                "account": {
                    "balance": total_balance,
                    "equity": total_equity,
                    "marginFree": total_margin_free,
                    "floatingPL": total_profit
                },
                "brokers": broker_stats,
                "orders": all_orders
            })

            # Run strategies
            if not is_halted:
                for strat in strategies:
                    print("📊 Running strategy iteration")
                    strat.run_iteration()
            
            print("✅ Loop complete")
            time.sleep(ITERATION_SLEEP)
            
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        for broker in brokers:
            broker.shutdown()

if __name__ == "__main__":
    main()
