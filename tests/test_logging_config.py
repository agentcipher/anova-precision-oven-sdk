import logging
from unittest.mock import Mock, patch

from anova_oven_sdk.logging_config import TokenMaskingFilter, setup_logging


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


class TestSetupLogging:
    """Test setup_logging function."""

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_basic(self, mock_settings):
        """Test basic logging setup."""
        mock_settings.log_level = "INFO"
        mock_settings.get.return_value = None  # No log file
        
        logger = setup_logging()
        
        assert logger.name == "anova_oven"
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_debug_level(self, mock_settings):
        """Test logging setup with DEBUG level."""
        mock_settings.log_level = "DEBUG"
        mock_settings.get.return_value = None
        
        logger = setup_logging()
        
        assert logger.level == logging.DEBUG

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_clears_handlers(self, mock_settings):
        """Test that setup clears existing handlers."""
        mock_settings.log_level = "INFO"
        mock_settings.get.return_value = None
        
        # Setup once
        logger = setup_logging()
        handler_count_1 = len(logger.handlers)
        
        # Setup again - should clear old handlers
        logger = setup_logging()
        handler_count_2 = len(logger.handlers)
        
        assert handler_count_1 == handler_count_2

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_console_handler(self, mock_settings):
        """Test console handler is added."""
        mock_settings.log_level = "INFO"
        mock_settings.get.side_effect = lambda key, default=None: {
            'log_file': None,
            'log_format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }.get(key, default)
        
        logger = setup_logging()
        
        # Check console handler exists
        console_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(console_handlers) > 0

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_console_format(self, mock_settings):
        """Test console handler format."""
        mock_settings.log_level = "INFO"
        custom_format = "%(levelname)s - %(message)s"
        mock_settings.get.side_effect = lambda key, default=None: {
            'log_file': None,
            'log_format': custom_format
        }.get(key, default)
        
        logger = setup_logging()
        
        console_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(console_handlers) > 0

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_with_file_handler(self, mock_settings, tmp_path):
        """Test file handler is added when log_file is set."""
        log_file = tmp_path / "test.log"
        mock_settings.log_level = "INFO"
        mock_settings.get.side_effect = lambda key, default=None: {
            'log_file': str(log_file),
            'log_format': '%(message)s',
            'log_max_bytes': 1024,
            'log_backup_count': 3
        }.get(key, default)
        
        logger = setup_logging()
        
        # Check file handler exists
        file_handlers = [h for h in logger.handlers 
                        if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) > 0

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_creates_log_directory(self, mock_settings, tmp_path):
        """Test that log directory is created if it doesn't exist."""
        log_dir = tmp_path / "logs" / "nested"
        log_file = log_dir / "test.log"
        
        mock_settings.log_level = "INFO"
        mock_settings.get.side_effect = lambda key, default=None: {
            'log_file': str(log_file),
            'log_format': '%(message)s',
            'log_max_bytes': 1024,
            'log_backup_count': 3
        }.get(key, default)
        
        logger = setup_logging()
        
        assert log_dir.exists()

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_file_handler_rotation(self, mock_settings, tmp_path):
        """Test file handler rotation settings."""
        log_file = tmp_path / "test.log"
        mock_settings.log_level = "INFO"
        mock_settings.get.side_effect = lambda key, default=None: {
            'log_file': str(log_file),
            'log_format': '%(message)s',
            'log_max_bytes': 5000,
            'log_backup_count': 7
        }.get(key, default)
        
        logger = setup_logging()
        
        file_handlers = [h for h in logger.handlers 
                        if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) > 0
        
        handler = file_handlers[0]
        assert handler.maxBytes == 5000
        assert handler.backupCount == 7

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_file_handler_level(self, mock_settings, tmp_path):
        """Test file handler uses DEBUG level."""
        log_file = tmp_path / "test.log"
        mock_settings.log_level = "INFO"
        mock_settings.get.side_effect = lambda key, default=None: {
            'log_file': str(log_file),
            'log_format': '%(message)s',
            'log_max_bytes': 1024,
            'log_backup_count': 3
        }.get(key, default)
        
        logger = setup_logging()
        
        file_handlers = [h for h in logger.handlers 
                        if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) > 0
        assert file_handlers[0].level == logging.DEBUG

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_token_masking_filter(self, mock_settings):
        """Test that TokenMaskingFilter is added to handlers."""
        mock_settings.log_level = "INFO"
        mock_settings.get.return_value = None
        
        logger = setup_logging()
        
        # Check filters are added
        for handler in logger.handlers:
            filters = [f for f in handler.filters if isinstance(f, TokenMaskingFilter)]
            assert len(filters) > 0

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_file_handler_format(self, mock_settings, tmp_path):
        """Test file handler has detailed format."""
        log_file = tmp_path / "test.log"
        mock_settings.log_level = "INFO"
        mock_settings.get.side_effect = lambda key, default=None: {
            'log_file': str(log_file),
            'log_format': '%(message)s',
            'log_max_bytes': 1024,
            'log_backup_count': 3
        }.get(key, default)
        
        logger = setup_logging()
        
        file_handlers = [h for h in logger.handlers 
                        if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) > 0
        
        # File handler should have detailed format with funcName and lineno
        formatter = file_handlers[0].formatter
        assert 'funcName' in formatter._fmt
        assert 'lineno' in formatter._fmt

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_warning_level(self, mock_settings):
        """Test logging setup with WARNING level."""
        mock_settings.log_level = "WARNING"
        mock_settings.get.return_value = None
        
        logger = setup_logging()
        
        assert logger.level == logging.WARNING

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_error_level(self, mock_settings):
        """Test logging setup with ERROR level."""
        mock_settings.log_level = "ERROR"
        mock_settings.get.return_value = None
        
        logger = setup_logging()
        
        assert logger.level == logging.ERROR

    @patch('anova_oven_sdk.logging_config.settings')
    def test_setup_logging_critical_level(self, mock_settings):
        """Test logging setup with CRITICAL level."""
        mock_settings.log_level = "CRITICAL"
        mock_settings.get.return_value = None
        
        logger = setup_logging()
        
        assert logger.level == logging.CRITICAL
