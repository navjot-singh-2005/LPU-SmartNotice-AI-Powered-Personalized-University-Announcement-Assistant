import logging
import sys
from app.core.config import settings

def setup_logging() -> logging.Logger:
    """Configure application logging format and level."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger("smartnotice")
    logger.setLevel(log_level)
    return logger

logger = setup_logging()
