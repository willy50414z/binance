# your_project/__init__.py
import logging
import os
from logging.handlers import RotatingFileHandler

from com.willy.binance.config import const


def _setup_logging(log_path: str = f"{const.PROJECT_DIR}/log/binance.log",
                   level: int = logging.DEBUG,
                   max_bytes: int = 5 * 1024 * 1024,
                   backup_count: int = 5) -> None:
    # 確保日誌目錄存在
    log_dir = os.path.dirname(log_path)
    try:
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    except Exception as e:
        # 若無法建立目錄，至少輸出到 Console
        print(f"Warning: could not create log directory {log_dir}: {e}")

    logger = logging.getLogger()
    logger.setLevel(level)

    # 避免重複加入 handler
    if logger.handlers:
        return

    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(fmt)

    # File handler（使用 RotatingFileHandler 避免單檔過大）
    file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# 啟動時呼叫設定
_setup_logging()
