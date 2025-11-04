# ============================================================================
# Logging Configuration
# ============================================================================

from logging.handlers import RotatingFileHandler
from .settings import settings
import logging
import sys
from pathlib import Path
from .utils import get_masked_token


class TokenMaskingFilter(logging.Filter):
    """Filter to mask tokens in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            token = settings.get('token', '')
            if token:
                masked = get_masked_token(token, mask=True)
                record.msg = record.msg.replace(token, masked)
        return True


def setup_logging() -> logging.Logger:
    """Setup logging with configuration from Dynaconf."""
    logger = logging.getLogger('anova_oven')
    logger.setLevel(getattr(logging, settings.log_level))
    logger.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, settings.log_level))
    console_fmt = logging.Formatter(
        settings.get('log_format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    console.setFormatter(console_fmt)
    console.addFilter(TokenMaskingFilter())
    logger.addHandler(console)

    # File handler (if configured)
    log_file = settings.get('log_file')
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=settings.get('log_max_bytes', 10 * 1024 * 1024),
            backupCount=settings.get('log_backup_count', 5)
        )
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_fmt)
        file_handler.addFilter(TokenMaskingFilter())
        logger.addHandler(file_handler)

    return logger