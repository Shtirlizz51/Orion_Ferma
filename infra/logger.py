import logging
from logging.handlers import RotatingFileHandler
import os

class ZefirLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Формат сообщений
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d - %(message)s'
        )
        
        # Консольный вывод
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        
        # Файловый вывод (с ротацией)
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        fh = RotatingFileHandler(
            os.path.join(log_dir, 'zefir.log'), 
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5
        )
        fh.setFormatter(formatter)
        
        if not self.logger.hasHandlers():
            self.logger.addHandler(ch)
            self.logger.addHandler(fh)
    
    def log(self, message: str, level: str = "info"):
        getattr(self.logger, level)(message)