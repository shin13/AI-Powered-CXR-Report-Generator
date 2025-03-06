import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger():
    log_directory = "./logs"
    os.makedirs(log_directory, exist_ok=True)
    log_path = os.path.join(log_directory, "app.log")
    handler = RotatingFileHandler(log_path, maxBytes=10*1024*1024, backupCount=5)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d - %(message)s',
        handlers=[
            handler,
            logging.StreamHandler()
        ]
    )