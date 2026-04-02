"""Async and threading utilities."""

import asyncio
import logging
from threading import Thread
from typing import Any, Coroutine, Optional


logger = logging.getLogger(__name__)


def run_async_in_thread(
    coro: Coroutine[Any, Any, Any],
    daemon: bool = True,
    name: Optional[str] = None,
) -> Thread:
    """Run an async coroutine in a background thread with its own event loop.
    
    Useful for blocking on long-running async code (like WebSocket loops)
    without stopping the main thread.
    
    Args:
        coro: Coroutine to run (e.g., result of calling an async function)
        daemon: If True, thread will not prevent process exit (default: True)
        name: Optional thread name for debugging
        
    Returns:
        Started Thread object
        
    Example:
        >>> async def websocket_loop():
        ...     # Long-running async work
        ...     pass
        >>>
        >>> thread = run_async_in_thread(websocket_loop(), name="ws-loop")
        >>> # Main thread continues; ws-loop runs in background
    """
    def thread_target() -> None:
        """Target function for the thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro)
        except Exception:
            logger.exception("Error in async thread target")
        finally:
            loop.close()
    
    thread = Thread(target=thread_target, daemon=daemon, name=name)
    thread.start()
    return thread
