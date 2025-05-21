import logging
import os
from datetime import datetime

# --- Logging Configuration --- START ---
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = os.path.join(LOG_DIR, f"chatbot_api_{current_time}.log")


logger = logging.getLogger()
logger.setLevel(logging.DEBUG) 

for handler in logger.handlers[:]:
    logger.removeHandler(handler)
    handler.close() 


file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.DEBUG) 


console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO) 


formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)


logger.addHandler(file_handler)
logger.addHandler(console_handler) 

logging.info(f"Logging initialized from logging_config.py. Log file: {log_filename}")

logging.getLogger("aiosqlite").setLevel(logging.INFO)

def get_logger(name=None):
    return logging.getLogger(name) 