"""WebSocket utilities for persistent connections with auto-reconnect."""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


class AutoReconnectingWebSocket:
    """Generic WebSocket client with exponential backoff reconnection.
    
    Maintains a persistent WebSocket connection and automatically reconnects
    on disconnection with exponential backoff (5s → 5s → 5s... configurable).
    
    Designed to wrap raw websockets.connect() and provide a loop-style interface
    for message handling.
    """
    
    def __init__(
        self,
        url: str,
        message_handler: Callable[[Dict[str, Any]], None],
        additional_headers: Optional[List[Tuple[str, str]]] = None,
        ping_interval: int = 30,
        ping_timeout: int = 10,
        reconnect_delay: int = 5,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """Initialize AutoReconnectingWebSocket.
        
        Args:
            url: WebSocket URL (e.g., "wss://ws.example.com")
            message_handler: Async callable that receives parsed JSON messages.
                           Should handle errors internally.
            additional_headers: Optional list of (header_name, header_value) tuples
            ping_interval: Seconds between WebSocket pings (default: 30)
            ping_timeout: Seconds to wait for pong response (default: 10)
            reconnect_delay: Seconds to wait before reconnecting (default: 5)
            logger_instance: Optional logger instance
        """
        self.url = url
        self.message_handler = message_handler
        self.additional_headers = additional_headers or []
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.reconnect_delay = reconnect_delay
        self.logger = logger_instance or logger
    
    async def run(self) -> None:
        """Start the auto-reconnecting WebSocket loop.
        
        This method runs indefinitely, reconnecting on any disconnection.
        Block the main app with asyncio.run() or run in a thread with
        run_async_in_thread().
        
        Example:
            >>> import asyncio
            >>> async def handle_msg(msg):
            ...     print(f"Got message: {msg}")
            >>>
            >>> ws = AutoReconnectingWebSocket(
            ...     "wss://ws.example.com",
            ...     handle_msg,
            ... )
            >>> asyncio.run(ws.run())
        """
        import websockets
        
        while True:
            try:
                async with websockets.connect(
                    self.url,
                    additional_headers=self.additional_headers,
                    ping_interval=self.ping_interval,
                    ping_timeout=self.ping_timeout,
                ) as ws:
                    self.logger.info("WebSocket connected: %s", self.url)
                    async for raw_message in ws:
                        try:
                            msg = json.loads(raw_message)
                            await self.message_handler(msg)
                        except json.JSONDecodeError:
                            self.logger.error(
                                "Failed to parse JSON message: %s",
                                raw_message[:200],
                            )
                        except Exception:
                            self.logger.exception("Error handling WebSocket message")
            except Exception as exc:
                self.logger.warning(
                    "WebSocket disconnected (%s) — reconnecting in %ds",
                    exc,
                    self.reconnect_delay,
                )
                await asyncio.sleep(self.reconnect_delay)
