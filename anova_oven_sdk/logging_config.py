# ============================================================================
# Logging Configuration
# ============================================================================

from .settings import settings
import logging
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
