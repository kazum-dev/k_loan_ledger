# modules/logger.py
import logging
import os
import time

# 規定は data/app.log に出力 (環境変数で上書き可)
LOG_FILE = os.getenv("APP_LOG_FILE", "data/app.log")

_shared_file_handler = None


def _build_file_handler() -> logging.Handler:
    global _shared_file_handler
    if _shared_file_handler is not None:
        return _shared_file_handler

    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    fmt = logging.Formatter(
        fmt="%(asctime)sZ\t%(levelname)s\t%(name)s\t%(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    fmt.converter = time.gmtime  # UTC固定

    fh = logging.FileHandler(LOG_FILE, encoding="UTF-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)

    _shared_file_handler = fh
    return fh


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    have_file = any(isinstance(h, logging.FileHandler) for h in logger.handlers)
    if not have_file:
        logger.addHandler(_build_file_handler())
        logger.propagate = False  # 二重出力防止
    return logger
