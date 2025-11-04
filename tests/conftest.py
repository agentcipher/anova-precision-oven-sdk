"""
Shared pytest fixtures and configuration.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset settings before each test."""
    # This ensures tests don't interfere with each other
    yield


@pytest.fixture
def temp_log_file(tmp_path):
    """Provide a temporary log file path."""
    return tmp_path / "test.log"


# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)
