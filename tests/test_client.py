import pytest
import asyncio
import json
import logging
from unittest.mock import Mock, AsyncMock, patch

from anova_oven_sdk.client import WebSocketClient
from anova_oven_sdk.exceptions import CommandError


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self, messages=None, close_after=None):
        self.messages = messages or []
        self.close_after = close_after
        self.sent_messages = []
        self.closed = False
        self._message_index = 0

    async def send(self, message):
        """Mock send."""
        self.sent_messages.append(message)

    async def close(self):
        """Mock close."""
        self.closed = True

    def __aiter__(self):
        """Make iterable."""
        return self

    async def __anext__(self):
        """Iterate messages."""
        # Handle connection closed scenario
        if self.close_after is not None and self._message_index >= self.close_after:
            from websockets.exceptions import ConnectionClosed
            raise ConnectionClosed(None, None)

        if self._message_index >= len(self.messages):
            # For empty message list, raise StopAsyncIteration immediately
            if not self.messages:
                raise StopAsyncIteration
            await asyncio.sleep(0.1)  # Simulate waiting
            raise StopAsyncIteration

        message = self.messages[self._message_index]
        self._message_index += 1
        return message


@pytest.fixture
def logger():
    """Create test logger."""
    return logging.getLogger("test")


@pytest.fixture
def client(logger):
    """Create WebSocketClient for testing."""
    return WebSocketClient(logger)


class TestWebSocketClient:
    """Test WebSocketClient class."""

    def test_init(self, client, logger):
        """Test client initialization."""
        assert client.logger == logger
        assert client._ws is None
        assert client._connected is False
        assert client._receive_task is None
        assert client._pending_requests == {}
        assert client._callbacks == []

    def test_is_connected_false(self, client):
        """Test is_connected when not connected."""
        assert client.is_connected is False

    def test_is_connected_true_with_ws(self, client):
        """Test is_connected when connected."""
        client._ws = Mock()
        client._connected = True
        assert client.is_connected is True

    def test_is_connected_false_no_ws(self, client):
        """Test is_connected false when no websocket."""
        client._connected = True
        client._ws = None
        assert client.is_connected is False

    def test_add_callback(self, client):
        """Test adding callback."""
        callback = Mock()
        client.add_callback(callback)
        assert callback in client._callbacks

    def test_add_multiple_callbacks(self, client):
        """Test adding multiple callbacks."""
        callback1 = Mock()
        callback2 = Mock()
        client.add_callback(callback1)
        client.add_callback(callback2)
        assert len(client._callbacks) == 2

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.websockets.connect')
    @patch('anova_oven_sdk.client.settings')
    async def test_connect_success(self, mock_settings, mock_ws_connect, client):
        """Test successful connection."""
        mock_settings.ws_url = "wss://test.com"
        mock_settings.token = "anova-test-token"
        mock_settings.supported_accessories = ["APO"]
        mock_settings.connection_timeout = 30

        # Create a proper async mock that returns a MockWebSocket
        mock_ws = MockWebSocket()

        # Mock websockets.connect to return the mock websocket directly
        async def mock_connect(*args, **kwargs):
            return mock_ws

        mock_ws_connect.return_value = mock_connect()

        await client.connect()

        assert client.is_connected is True
        assert client._ws == mock_ws
        assert client._receive_task is not None

        # Cleanup
        client._receive_task.cancel()
        try:
            await client._receive_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.websockets.connect')
    @patch('anova_oven_sdk.client.settings')
    async def test_connect_already_connected(self, mock_settings, mock_ws_connect, client, logger):
        """Test connecting when already connected."""
        client._connected = True
        client._ws = Mock()

        with patch.object(logger, 'warning') as mock_warning:
            await client.connect()
            mock_warning.assert_called_once()

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.websockets.connect')
    @patch('anova_oven_sdk.client.settings')
    async def test_connect_timeout(self, mock_settings, mock_ws_connect, client):
        """Test connection timeout."""
        mock_settings.ws_url = "wss://test.com"
        mock_settings.token = "anova-test-token"
        mock_settings.supported_accessories = ["APO"]
        mock_settings.connection_timeout = 0.1

        async def slow_connect(*args, **kwargs):
            await asyncio.sleep(1)

        mock_ws_connect.return_value = slow_connect()

        with pytest.raises(Exception):  # ConnectionError
            await client.connect()

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.websockets.connect')
    @patch('anova_oven_sdk.client.settings')
    async def test_connect_failure(self, mock_settings, mock_ws_connect, client):
        """Test connection failure."""
        mock_settings.ws_url = "wss://test.com"
        mock_settings.token = "anova-test-token"
        mock_settings.supported_accessories = ["APO"]
        mock_settings.connection_timeout = 30

        async def failing_connect(*args, **kwargs):
            raise Exception("Connection failed")

        mock_ws_connect.return_value = failing_connect()

        with pytest.raises(Exception):  # ConnectionError
            await client.connect()

    @pytest.mark.asyncio
    async def test_disconnect_when_connected(self, client):
        """Test disconnecting when connected."""
        # Create a proper async mock for the websocket
        mock_ws = Mock()
        mock_ws.close = AsyncMock()
        client._ws = mock_ws
        client._connected = True

        # Create a mock task that can be cancelled and awaited
        async def mock_task_coro():
            raise asyncio.CancelledError()

        mock_task = asyncio.create_task(mock_task_coro())
        client._receive_task = mock_task

        # Give the task a moment to start
        await asyncio.sleep(0.01)

        await client.disconnect()

        assert client._connected is False
        assert mock_task.cancelled() or mock_task.done()
        mock_ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_task_already_cancelled(self, client):
        """Test disconnect when task is already cancelled."""
        mock_ws = Mock()
        mock_ws.close = AsyncMock()
        client._ws = mock_ws
        client._connected = True

        # Create a task and cancel it before disconnect
        async def long_running():
            await asyncio.sleep(10)

        mock_task = asyncio.create_task(long_running())
        mock_task.cancel()
        client._receive_task = mock_task

        # Should handle the CancelledError gracefully
        await client.disconnect()

        assert client._connected is False
        mock_ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, client):
        """Test disconnecting when not connected."""
        await client.disconnect()  # Should not raise

    @pytest.mark.asyncio
    async def test_receive_loop_valid_json(self, client):
        """Test receive loop with valid JSON."""
        messages = [
            json.dumps({"command": "TEST", "payload": {}})
        ]
        mock_ws = MockWebSocket(messages)
        client._ws = mock_ws
        client._connected = True

        callback = Mock()
        client.add_callback(callback)

        await client._receive_loop()

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_loop_invalid_json(self, client, logger):
        """Test receive loop with invalid JSON."""
        messages = ["invalid json"]
        mock_ws = MockWebSocket(messages)
        client._ws = mock_ws
        client._connected = True

        with patch.object(logger, 'error') as mock_error:
            await client._receive_loop()
            mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_receive_loop_message_error(self, client, logger):
        """Test receive loop with message handling error."""
        messages = [json.dumps({"command": "TEST"})]
        mock_ws = MockWebSocket(messages)
        client._ws = mock_ws
        client._connected = True

        def bad_callback(data):
            raise ValueError("Callback error")

        client.add_callback(bad_callback)

        with patch.object(logger, 'error') as mock_error:
            await client._receive_loop()
            assert mock_error.call_count >= 1

    @pytest.mark.asyncio
    async def test_receive_loop_handle_message_exception(self, client, logger):
        """Test receive loop when _handle_message raises an exception."""
        messages = [json.dumps({"command": "TEST", "data": "value"})]
        mock_ws = MockWebSocket(messages)
        client._ws = mock_ws
        client._connected = True

        # Mock _handle_message to raise an exception
        async def failing_handle_message(data):
            raise RuntimeError("Handle message failed")

        with patch.object(client, '_handle_message', side_effect=failing_handle_message):
            with patch.object(logger, 'error') as mock_error:
                await client._receive_loop()
                # Should log "Message error: Handle message failed"
                mock_error.assert_called()
                # Verify it was called with exc_info=True
                call_args = mock_error.call_args
                assert 'Message error:' in str(call_args)
                assert call_args[1]['exc_info'] is True

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.settings')
    async def test_receive_loop_connection_closed_with_reconnect(self, mock_settings, client, logger):
        """Test receive loop handles connection closed with auto-reconnect."""
        # Configure settings to enable auto_reconnect
        mock_settings.get.return_value = True  # auto_reconnect

        # Create websocket that will raise ConnectionClosed immediately
        mock_ws = MockWebSocket(messages=[], close_after=0)
        client._ws = mock_ws
        client._connected = True

        # Track the state when _reconnect is called
        reconnect_called_with_connected_false = []

        async def mock_reconnect_impl():
            # Record what _connected was when reconnect was called
            reconnect_called_with_connected_false.append(client._connected)

        # Mock the reconnect method and logger
        with patch.object(client, '_reconnect', side_effect=mock_reconnect_impl) as mock_reconnect:
            with patch.object(logger, 'warning') as mock_warning:
                await client._receive_loop()
                mock_reconnect.assert_called_once()
                mock_warning.assert_called_with("Connection closed")
                # Verify _connected was set to False BEFORE _reconnect was called
                assert len(reconnect_called_with_connected_false) == 1
                assert reconnect_called_with_connected_false[0] is False
                # Verify _connected is False after the loop
                assert client._connected is False

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.settings')
    async def test_receive_loop_connection_closed_without_reconnect(self, mock_settings, client, logger):
        """Test receive loop handles connection closed without auto-reconnect."""
        # Configure settings to disable auto_reconnect
        mock_settings.get.return_value = False  # auto_reconnect disabled

        # Create websocket that will raise ConnectionClosed immediately
        mock_ws = MockWebSocket(messages=[], close_after=0)
        client._ws = mock_ws
        client._connected = True

        with patch.object(logger, 'warning') as mock_warning:
            # Also track that _reconnect is NOT called
            with patch.object(client, '_reconnect', new_callable=AsyncMock) as mock_reconnect:
                await client._receive_loop()
                mock_warning.assert_called_with("Connection closed")
                # Should set connected to False but NOT call reconnect
                assert client._connected is False
                mock_reconnect.assert_not_called()

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.settings')
    async def test_receive_loop_connection_closed_auto_reconnect_default(self, mock_settings, client, logger):
        """Test that auto_reconnect defaults to True when not specified."""

        # When settings.get is called with default value True
        def settings_get_side_effect(key, default=None):
            if key == 'auto_reconnect':
                return default  # Return the default (True)
            return None

        mock_settings.get.side_effect = settings_get_side_effect

        # Create websocket that will raise ConnectionClosed immediately
        mock_ws = MockWebSocket(messages=[], close_after=0)
        client._ws = mock_ws
        client._connected = True

        with patch.object(client, '_reconnect', new_callable=AsyncMock) as mock_reconnect:
            await client._receive_loop()
            # Should call reconnect since default is True
            mock_reconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_loop_general_exception(self, client, logger):
        """Test receive loop handles general exceptions."""
        mock_ws = Mock()

        # Create an async generator that raises an exception
        async def bad_iter():
            raise ValueError("Test error")
            yield  # This line will never be reached

        mock_ws.__aiter__ = lambda self: bad_iter()
        client._ws = mock_ws
        client._connected = True

        with patch.object(logger, 'error') as mock_error:
            await client._receive_loop()
            mock_error.assert_called()
            assert client._connected is False

    @pytest.mark.asyncio
    async def test_reconnect_success(self, client):
        """Test successful reconnection."""
        with patch.object(client, 'connect', new_callable=AsyncMock) as mock_connect:
            await client._reconnect()
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_failure(self, client, logger):
        """Test failed reconnection."""

        async def failing_connect():
            raise Exception("Reconnect failed")

        with patch.object(client, 'connect', side_effect=failing_connect):
            with patch.object(logger, 'error') as mock_error:
                await client._reconnect()
                mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_handle_message_basic(self, client):
        """Test handling basic message."""
        data = {"command": "TEST", "payload": {}}

        callback = Mock()
        client.add_callback(callback)

        await client._handle_message(data)

        callback.assert_called_once_with(data)

    @pytest.mark.asyncio
    async def test_handle_message_with_request_id(self, client):
        """Test handling message with request ID."""
        request_id = "test-123"
        data = {"command": "RESPONSE", "requestId": request_id}

        future = asyncio.Future()
        client._pending_requests[request_id] = future

        await client._handle_message(data)

        assert future.done()
        assert future.result() == data
        assert request_id not in client._pending_requests

    @pytest.mark.asyncio
    async def test_handle_message_with_already_done_future(self, client):
        """Test handling message when future is already done."""
        request_id = "test-456"
        data = {"command": "RESPONSE", "requestId": request_id}

        # Create a future that's already done
        future = asyncio.Future()
        future.set_result({"previous": "result"})
        client._pending_requests[request_id] = future

        # Should not raise even though future is already done
        await client._handle_message(data)

        # Future should still have original result, not be overwritten
        assert future.result() == {"previous": "result"}
        # Request should be removed from pending
        assert request_id not in client._pending_requests

    @pytest.mark.asyncio
    async def test_handle_message_callback_error(self, client, logger):
        """Test handling message when callback raises error."""
        data = {"command": "TEST"}

        def bad_callback(data):
            raise ValueError("Callback error")

        client.add_callback(bad_callback)

        with patch.object(logger, 'error') as mock_error:
            await client._handle_message(data)
            mock_error.assert_called()

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.settings')
    async def test_send_command_success(self, mock_settings, client):
        """Test sending command successfully."""
        mock_settings.command_timeout = 10

        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        client._ws = mock_ws
        client._connected = True

        result = await client.send_command("TEST_CMD", {"data": "test"})

        mock_ws.send.assert_called_once()
        assert result is None

    @pytest.mark.asyncio
    async def test_send_command_not_connected(self, client):
        """Test sending command when not connected."""
        with pytest.raises(Exception):  # ConnectionError
            await client.send_command("TEST_CMD", {})

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.settings')
    async def test_send_command_with_response(self, mock_settings, client):
        """Test sending command and waiting for response."""
        mock_settings.command_timeout = 10

        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        client._ws = mock_ws
        client._connected = True

        # Simulate response
        async def simulate_response():
            await asyncio.sleep(0.01)
            request_id = list(client._pending_requests.keys())[0]
            await client._handle_message({"command": "RESPONSE", "requestId": request_id})

        task = asyncio.create_task(simulate_response())

        result = await client.send_command("TEST_CMD", {"data": "test"}, wait_response=True)

        await task
        assert result is not None

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.settings')
    async def test_send_command_timeout(self, mock_settings, client):
        """Test send command timeout."""
        mock_settings.command_timeout = 0.01

        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        client._ws = mock_ws
        client._connected = True

        with pytest.raises(Exception):  # TimeoutError
            await client.send_command("TEST_CMD", {}, wait_response=True, timeout=0.01)

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.settings')
    async def test_send_command_exception(self, mock_settings, client):
        """Test send command with exception."""
        mock_settings.command_timeout = 10

        mock_ws = Mock()
        mock_ws.send = AsyncMock(side_effect=Exception("Send failed"))
        client._ws = mock_ws
        client._connected = True

        with pytest.raises(CommandError):
            await client.send_command("TEST_CMD", {})

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.settings')
    async def test_send_command_exception_with_pending_request(self, mock_settings, client):
        """Test send command exception cleans up pending request."""
        mock_settings.command_timeout = 10

        mock_ws = Mock()
        mock_ws.send = AsyncMock(side_effect=Exception("Send failed"))
        client._ws = mock_ws
        client._connected = True

        # Should cleanup pending request even with exception
        with pytest.raises(CommandError):
            await client.send_command("TEST_CMD", {}, wait_response=True)

        # Verify pending requests were cleaned up
        assert len(client._pending_requests) == 0

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.settings')
    async def test_send_command_timeout_cleanup(self, mock_settings, client):
        """Test send command timeout cleans up pending request."""
        mock_settings.command_timeout = 0.01

        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        client._ws = mock_ws
        client._connected = True

        with pytest.raises(Exception):  # TimeoutError
            await client.send_command("TEST_CMD", {}, wait_response=True, timeout=0.01)

        # Verify pending requests were cleaned up
        assert len(client._pending_requests) == 0

    @pytest.mark.asyncio
    @patch('anova_oven_sdk.client.settings')
    async def test_send_command_custom_timeout(self, mock_settings, client):
        """Test send command with custom timeout."""
        mock_settings.command_timeout = 10

        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        client._ws = mock_ws
        client._connected = True

        await client.send_command("TEST_CMD", {}, timeout=5)
        mock_ws.send.assert_called_once()