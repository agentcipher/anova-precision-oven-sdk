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
from .exceptions import CommandError, ConnectionError, TimeoutError


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
        # Set on every successful connection, cleared on disconnect/close.
        # Lets send_command() wait for an in-flight reconnect to land
        # instead of failing outright when the server closes the
        # connection mid-send.
        self._reconnected_event = asyncio.Event()
        # Serializes _connect_once()/disconnect() so concurrent callers
        # (e.g. the background _reconnect() loop racing an explicit
        # connect() call from application code) can't both pass the
        # `is_connected` check while a connection attempt is still in
        # flight and each open a duplicate WebSocket + receive task.
        self._connection_lock = asyncio.Lock()

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
        async with self._connection_lock:
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
                self._reconnected_event.set()
                self.logger.info("✓ Connected")

                self._receive_task = asyncio.create_task(self._receive_loop())

            except asyncio.TimeoutError:
                raise ConnectionError("Connection timeout", {"timeout": settings.connection_timeout})
            except Exception as e:
                raise ConnectionError(f"Connection failed: {e}")

    async def disconnect(self) -> None:
        """Disconnect from server, including stopping any in-progress
        automatic reconnect.

        `_receive_task` is cancelled unconditionally (not gated on
        `is_connected`) because it may currently be inside `_reconnect()`'s
        background retry loop -- `is_connected` is already False while
        that's happening, so gating on it would leave the reconnect loop
        running forever even after the caller asked to disconnect.

        The task is cancelled *before* acquiring `_connection_lock` (rather
        than holding the lock across the cancel+await) so that if the task
        is currently inside `_connect_once()` holding that same lock, the
        cancellation can interrupt it instead of disconnect() deadlocking
        waiting on a lock only the task being cancelled can release.
        """
        if not self.is_connected and (self._receive_task is None or self._receive_task.done()):
            return

        self.logger.info("Disconnecting...")
        self._connected = False
        self._reconnected_event.clear()

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        async with self._connection_lock:
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
            self._reconnected_event.clear()
            if settings.get('auto_reconnect', True):
                await self._reconnect()
        except Exception as e:
            self.logger.error(f"Receive loop error: {e}", exc_info=True)
            self._connected = False
            self._reconnected_event.clear()

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
        """Send command.

        If the connection closes mid-send (e.g. a server-initiated close),
        this waits, bounded, for the automatic reconnect already running in
        the background to land, then retries the send exactly once against
        the new connection -- rather than failing outright when a working
        connection exists again moments later.
        """
        timeout = timeout or settings.command_timeout
        return await self._send_command_attempt(command, payload, wait_response, timeout, allow_retry=True)

    async def _send_command_attempt(
            self,
            command: str,
            payload: Dict[str, Any],
            wait_response: bool,
            timeout: float,
            allow_retry: bool
    ) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            raise ConnectionError("Not connected")

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
            self.logger.error(f"Command timeout: {command} (timeout={timeout}s)")
            raise TimeoutError(f"Command timeout: {command}", {"timeout": timeout})
        except websockets.exceptions.ConnectionClosed as e:
            if request_id in self._pending_requests:
                del self._pending_requests[request_id]
            if allow_retry and await self._wait_for_reconnect():
                self.logger.info(f"Reconnected, retrying command: {command}")
                return await self._send_command_attempt(
                    command, payload, wait_response, timeout, allow_retry=False
                )
            self.logger.error(f"Send failed: {e}")
            raise CommandError(f"Send failed: {e}")
        except Exception as e:
            if request_id in self._pending_requests:
                del self._pending_requests[request_id]
            self.logger.error(f"Send failed: {e}")
            raise CommandError(f"Send failed: {e}")

    async def _wait_for_reconnect(self) -> bool:
        """Bounded wait for an in-flight automatic reconnect to land.

        A single bounded wait, not a retry loop of its own -- `_reconnect()`
        (started by `_receive_loop()`) does the actual unbounded backoff
        retrying in the background. This just gives one command a chance to
        ride out a reconnect that's already happening instead of failing
        immediately.
        """
        if not settings.get('auto_reconnect', True):
            return False
        if self.is_connected:
            return True
        wait_timeout = settings.get('reconnect_wait', 5.0)
        self.logger.warning(
            f"Connection closed mid-send, waiting up to {wait_timeout:.1f}s for reconnect..."
        )
        try:
            await asyncio.wait_for(self._reconnected_event.wait(), timeout=wait_timeout)
            return True
        except asyncio.TimeoutError:
            return False