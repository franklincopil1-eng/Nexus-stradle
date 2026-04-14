import logging
import json
from datetime import datetime
import os

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName
        }
        if hasattr(record, 'extra_data'):
            log_record.update(record.extra_data)
        return json.dumps(log_record)

def setup_logger(name="trading_system"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Ensure logs directory exists
    if not os.path.exists("logs"):
        os.makedirs("logs")
        
    # File handler
    file_handler = logging.FileHandler(f"logs/trading_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler.setFormatter(JsonFormatter())
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
