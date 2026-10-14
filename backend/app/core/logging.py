import logging
import re
import sys
from typing import Any

# Pattern to mask passwords or secrets in log outputs
SECRET_PATTERN = re.compile(r"(password|pwd|secret|token)=([^&\s]+)", re.IGNORECASE)
DB_CRED_PATTERN = re.compile(r"://([^:@]+):([^@]+)@", re.IGNORECASE)


class RedactingFormatter(logging.Formatter):
    """Custom formatter that scrubs sensitive credentials from log strings."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        # Redact password params
        msg = SECRET_PATTERN.sub(r"\1=***", msg)
        # Redact db uri user:password
        msg = DB_CRED_PATTERN.sub(r"://\1:***@", msg)
        return msg


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("workplace_intelligence")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            RedactingFormatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
            )
        )
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


logger = setup_logging()
