import logging
import json
import requests
from datetime import datetime
import os

class ApiLogHandler(logging.Handler):
    def __init__(self, api_url):
        super().__init__()
        self.api_url = api_url

    def emit(self, record):
        if not self.api_url:
            return
        log_entry = {
            "level": record.levelname,
            "message": self.format(record)
        }
        try:
            # We use a separate thread or very short timeout to avoid blocking execution
            requests.post(f"{self.api_url}/api/update", json={"log": log_entry}, timeout=0.1)
        except Exception:
            pass

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

def setup_logger(name="trading_system", api_url=None):
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

    # API handler if available
    if api_url:
        api_handler = ApiLogHandler(api_url)
        api_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(api_handler)
    
    return logger
