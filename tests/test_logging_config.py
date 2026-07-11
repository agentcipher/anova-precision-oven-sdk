import logging
from unittest.mock import Mock, patch

from anova_oven_sdk.logging_config import TokenMaskingFilter


class TestTokenMaskingFilter:
    """Test TokenMaskingFilter class."""

    def test_filter_with_token_in_message(self):
        """Test filtering message with token."""
        token_filter = TokenMaskingFilter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Token is anova-1234567890abcdefghij in this message",
            args=(),
            exc_info=None
        )

        with patch('anova_oven_sdk.logging_config.settings') as mock_settings:
            mock_settings.get.return_value = "anova-1234567890abcdefghij"

            result = token_filter.filter(record)

            assert result is True
            assert "anova-1234567890abcdefghij" not in record.msg
            assert "..." in record.msg

    def test_filter_without_token(self):
        """Test filtering when no token in settings."""
        token_filter = TokenMaskingFilter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="No token in this message",
            args=(),
            exc_info=None
        )

        with patch('anova_oven_sdk.logging_config.settings') as mock_settings:
            mock_settings.get.return_value = ""

            result = token_filter.filter(record)

            assert result is True
            assert record.msg == "No token in this message"

    def test_filter_with_non_string_message(self):
        """Test filtering with non-string message."""
        token_filter = TokenMaskingFilter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=123,  # Not a string
            args=(),
            exc_info=None
        )

        with patch('anova_oven_sdk.logging_config.settings') as mock_settings:
            mock_settings.get.return_value = "anova-token"

            result = token_filter.filter(record)

            assert result is True

    def test_filter_without_msg_attribute(self):
        """Test filtering record without msg attribute."""
        token_filter = TokenMaskingFilter()

        record = Mock(spec=[])  # No attributes

        result = token_filter.filter(record)

        assert result is True
