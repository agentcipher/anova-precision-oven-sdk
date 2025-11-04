# ============================================================================
# Utilities
# ============================================================================

import uuid as uuid_lib
from functools import wraps
import asyncio
from typing import Callable
from .settings import settings


def generate_uuid() -> str:
    """Generate UUID v4 string."""
    return str(uuid_lib.uuid4())


async def retry_async(
        func: Callable,
        max_retries: int = None,
        delay: float = None,
        backoff: float = None,
        exceptions: tuple = (Exception,)
):
    """Retry async function with exponential backoff."""
    max_retries = max_retries or settings.get('max_retries', 3)
    delay = delay or settings.get('retry_delay', 1.0)
    backoff = backoff or settings.get('retry_backoff', 2.0)

    last_exception = None
    current_delay = delay

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            else:
                raise TimeoutError(
                    f"Failed after {max_retries} retries",
                    {"last_error": str(last_exception)}
                ) from last_exception


def async_retry(max_retries: int = None, delay: float = None, backoff: float = None):
    """Decorator for retrying async functions."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                delay=delay,
                backoff=backoff
            )

        return wrapper

    return decorator

def get_masked_token(token: str, mask: bool = True) -> str:
    """Mask token for logging."""
    if not token or not mask or len(token) <= 15:
        return "anova-***" if mask else token
    return f"{token[:11]}...{token[-4:]}"