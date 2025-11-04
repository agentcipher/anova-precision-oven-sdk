import pytest

from anova_oven_sdk.utils import (
    generate_uuid, retry_async, async_retry, get_masked_token
)


class TestGenerateUUID:
    """Test UUID generation."""

    def test_generate_uuid_format(self):
        """Test UUID generation returns valid format."""
        uuid = generate_uuid()
        assert isinstance(uuid, str)
        assert len(uuid) == 36
        assert uuid.count('-') == 4

    def test_generate_uuid_unique(self):
        """Test UUIDs are unique."""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()
        assert uuid1 != uuid2

    def test_generate_uuid_multiple(self):
        """Test multiple UUID generations."""
        uuids = [generate_uuid() for _ in range(100)]
        assert len(set(uuids)) == 100  # All unique


class TestRetryAsync:
    """Test retry_async function."""

    @pytest.mark.asyncio
    async def test_retry_success_first_try(self):
        """Test successful execution on first try."""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_async(success_func, max_retries=3)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test successful execution after failures."""
        call_count = 0

        async def eventual_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = await retry_async(eventual_success, max_retries=3, delay=0.01)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_max_retries_exceeded(self):
        """Test failure after max retries."""
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(Exception):  # TimeoutError from utils
            await retry_async(always_fails, max_retries=2, delay=0.01)
        assert call_count == 3  # Initial try + 2 retries

    @pytest.mark.asyncio
    async def test_retry_with_backoff(self):
        """Test retry with exponential backoff."""
        call_times = []

        async def track_time():
            import time
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("Retry")
            return "success"

        result = await retry_async(track_time, max_retries=3, delay=0.05, backoff=2.0)
        assert result == "success"
        assert len(call_times) == 3

        # Check that delays increased (with some tolerance)
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]
            assert delay2 > delay1  # Second delay should be longer

    @pytest.mark.asyncio
    async def test_retry_with_custom_exceptions(self):
        """Test retry with custom exception types."""
        call_count = 0

        async def custom_exception_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Retry this")
            return "success"

        result = await retry_async(
            custom_exception_func,
            max_retries=2,
            delay=0.01,
            exceptions=(ValueError,)
        )
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_wrong_exception_type(self):
        """Test retry doesn't catch wrong exception type."""
        async def wrong_exception():
            raise TypeError("Wrong type")

        with pytest.raises(TypeError):
            await retry_async(
                wrong_exception,
                max_retries=2,
                delay=0.01,
                exceptions=(ValueError,)
            )


class TestAsyncRetryDecorator:
    """Test async_retry decorator."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorator with successful function."""
        call_count = 0

        @async_retry(max_retries=3, delay=0.01)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "decorated success"

        result = await success_func()
        assert result == "decorated success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_with_retries(self):
        """Test decorator with retries."""
        call_count = 0

        @async_retry(max_retries=3, delay=0.01)
        async def retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return "success after retry"

        result = await retry_func()
        assert result == "success after retry"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_with_args(self):
        """Test decorator preserves function arguments."""
        @async_retry(max_retries=2, delay=0.01)
        async def func_with_args(x, y, z=10):
            return x + y + z

        result = await func_with_args(5, 10, z=20)
        assert result == 35

    @pytest.mark.asyncio
    async def test_decorator_no_params(self):
        """Test decorator without parameters."""
        call_count = 0

        @async_retry()
        async def default_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return "success"

        result = await default_retry()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_max_retries_exceeded(self):
        """Test decorator when max retries exceeded."""
        call_count = 0

        @async_retry(max_retries=2, delay=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(Exception):
            await always_fails()
        assert call_count == 3


class TestGetMaskedToken:
    """Test token masking for logging."""

    def test_mask_long_token(self):
        """Test masking a long token."""
        token = "anova-1234567890abcdefghijklmnop"
        masked = get_masked_token(token, mask=True)
        assert masked.startswith("anova-12345")
        assert masked.endswith("mnop")
        assert "..." in masked
        assert len(token) > len(masked)

    def test_mask_short_token(self):
        """Test masking a short token."""
        token = "anova-short"
        masked = get_masked_token(token, mask=True)
        assert masked == "anova-***"

    def test_no_mask(self):
        """Test not masking token."""
        token = "anova-1234567890abcdefghijklmnop"
        result = get_masked_token(token, mask=False)
        assert result == token

    def test_empty_token_with_mask(self):
        """Test empty token with masking."""
        result = get_masked_token("", mask=True)
        assert result == "anova-***"

    def test_empty_token_without_mask(self):
        """Test empty token without masking."""
        result = get_masked_token("", mask=False)
        assert result == ""

    def test_token_exactly_15_chars(self):
        """Test token exactly 15 characters."""
        token = "anova-123456789"
        masked = get_masked_token(token, mask=True)
        assert masked == "anova-***"

    def test_token_16_chars(self):
        """Test token with 16 characters."""
        token = "anova-1234567890"
        masked = get_masked_token(token, mask=True)
        assert "..." in masked
        assert masked.startswith("anova-12345")

    def test_none_token_with_mask(self):
        """Test None token with masking."""
        result = get_masked_token(None, mask=True)
        assert result == "anova-***"

    def test_none_token_without_mask(self):
        """Test None token without masking."""
        result = get_masked_token(None, mask=False)
        assert result is None
