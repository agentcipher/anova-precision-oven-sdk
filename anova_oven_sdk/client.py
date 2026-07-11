# ============================================================================
# WebSocket Client
# ============================================================================

import json
import asyncio
import logging
import ssl
from typing import Optional, List, Dict, Any, Callable
from .utils import async_retry, generate_uuid
from .settings import settings
from .exceptions import CommandError


import websockets
from websockets.asyncio.client import ClientConnection as WebSocketClientProtocol

class WebSocketClient:
    """Manages WebSocket connection."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._receive_task: Optional[asyncio.Task] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._callbacks: List[Callable] = []

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    def add_callback(self, callback: Callable[[Dict], None]):
        """Add message callback."""
        self._callbacks.append(callback)

    @async_retry()
    async def connect(self) -> None:
        """Connect to WebSocket server, retrying a bounded number of times."""
        await self._connect_once()

    async def _connect_once(self) -> None:
        """Make a single connection attempt with no retry of its own.

        Used directly by `connect()` (wrapped in a bounded retry) and by
        `_reconnect()` (wrapped in its own unbounded backoff loop) so retry
        behavior only ever happens at one layer at a time.
        """
        if self.is_connected:
            self.logger.warning("Already connected")
            return

        url = (f"{settings.ws_url}?"
               f"token={settings.token}&"
               f"supportedAccessories={','.join(settings.supported_accessories)}")

        try:
            self.logger.info(f"Connecting to {settings.ws_url} using supported_accessories: {settings.supported_accessories}")

            ssl_context = None
            if url.startswith("wss://"):
                loop = asyncio.get_running_loop()
                ssl_context = await loop.run_in_executor(None, ssl.create_default_context)

            self._ws = await asyncio.wait_for(
                websockets.connect(url, ssl=ssl_context),
                timeout=settings.connection_timeout
            )
            self._connected = True
            self.logger.info("✓ Connected")

            self._receive_task = asyncio.create_task(self._receive_loop())

        except asyncio.TimeoutError:
            raise ConnectionError("Connection timeout", {"timeout": settings.connection_timeout})
        except Exception as e:
            raise ConnectionError(f"Connection failed: {e}")

    async def disconnect(self) -> None:
        """Disconnect from server."""
        if not self.is_connected:
            return

        self.logger.info("Disconnecting...")
        self._connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        self.logger.info("Disconnected")

    async def _receive_loop(self) -> None:
        """Receive messages loop."""
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON: {message[:100]}")
                except Exception as e:
                    self.logger.error(f"Message error: {e}", exc_info=True)
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("Connection closed")
            self._connected = False
            if settings.get('auto_reconnect', True):
                await self._reconnect()
        except Exception as e:
            self.logger.error(f"Receive loop error: {e}", exc_info=True)
            self._connected = False

    async def _reconnect(self) -> None:
        """Retry a single connection attempt indefinitely with backoff.

        Calls `_connect_once()` rather than `connect()` so retries only
        happen at this layer, not also inside `connect()`'s own bounded
        `@async_retry`.
        """
        delay = settings.get('retry_delay', 1.0)
        backoff = settings.get('retry_backoff', 2.0)
        max_delay = 60.0
        while not self._connected:
            try:
                self.logger.info("Reconnecting...")
                await self._connect_once()
            except Exception as e:
                self.logger.error(f"Reconnect failed: {e}, retrying in {delay:.1f}s")
                await asyncio.sleep(delay)
                delay = min(delay * backoff, max_delay)

    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming message."""
        command = data.get('command', '')
        request_id = data.get('requestId')

        self.logger.debug(f"← {command}")

        if request_id and request_id in self._pending_requests:
            future = self._pending_requests.pop(request_id)
            if not future.done():
                future.set_result(data)

        for callback in self._callbacks:
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"Callback error: {e}", exc_info=True)

    async def send_command(
            self,
            command: str,
            payload: Dict[str, Any],
            wait_response: bool = False,
            timeout: float = None
    ) -> Optional[Dict[str, Any]]:
        """Send command."""
        if not self.is_connected:
            raise ConnectionError("Not connected")

        timeout = timeout or settings.command_timeout
        request_id = generate_uuid()

        message = {
            "command": command,
            "requestId": request_id,
            "payload": payload
        }

        future = None
        if wait_response:
            future = asyncio.Future()
            self._pending_requests[request_id] = future

        try:
            self.logger.debug(f"→ {command}")
            await self._ws.send(json.dumps(message))

            if wait_response:
                return await asyncio.wait_for(future, timeout=timeout)

        except asyncio.TimeoutError:
            if request_id in self._pending_requests:
                del self._pending_requests[request_id]
            raise TimeoutError(f"Command timeout: {command}", {"timeout": timeout})
        except Exception as e:
            if request_id in self._pending_requests:
                del self._pending_requests[request_id]
            raise CommandError(f"Send failed: {e}")