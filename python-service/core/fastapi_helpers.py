"""FastAPI lifecycle and startup helpers."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Optional

from fastapi import FastAPI


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan_with_callback(
    app: FastAPI,
    startup_callback: Callable[[], Any],
    shutdown_callback: Optional[Callable[[], Any]] = None,
) -> AsyncGenerator[None, None]:
    """Create a FastAPI lifespan context manager with startup/shutdown callbacks.
    
    Use with FastAPI to manage startup tasks (like starting background services)
    and shutdown cleanup.
    
    Args:
        app: FastAPI application instance
        startup_callback: Async or sync callable to run on app startup
        shutdown_callback: Optional async or sync callable to run on shutdown
        
    Yields:
        None (used by FastAPI's lifespan parameter)
        
    Example:
        >>> from fastapi import FastAPI
        >>> 
        >>> async def start_service():
        ...     logger.info("Service starting")
        >>>
        >>> async def stop_service():
        ...     logger.info("Service stopping")
        >>>
        >>> app = FastAPI(
        ...     lifespan=lambda app: lifespan_with_callback(
        ...         app,
        ...         start_service,
        ...         stop_service,
        ...     )
        ... )
    """
    try:
        # Startup
        if callable(startup_callback):
            result = startup_callback()
            # Handle both async and sync callables
            if hasattr(result, "__await__"):
                await result
        
        logger.info("Lifespan startup complete")
        yield
    finally:
        # Shutdown
        if shutdown_callback and callable(shutdown_callback):
            result = shutdown_callback()
            # Handle both async and sync callables
            if hasattr(result, "__await__"):
                await result
        
        logger.info("Lifespan shutdown complete")


def create_lifespan(
    startup_callback: Callable[[], Any],
    shutdown_callback: Optional[Callable[[], Any]] = None,
) -> Callable[[FastAPI], Any]:
    """Create a lifespan function for FastAPI.
    
    Returns a function suitable for the FastAPI `lifespan=` parameter.
    
    Args:
        startup_callback: Async or sync callable for app startup
        shutdown_callback: Optional async or sync callable for app shutdown
        
    Returns:
        Lifespan function compatible with FastAPI
        
    Example:
        >>> async def on_startup():
        ...     print("App starting")
        >>>
        >>> async def on_shutdown():
        ...     print("App stopping")
        >>>
        >>> lifespan = create_lifespan(on_startup, on_shutdown)
        >>> app = FastAPI(lifespan=lifespan)
    """
    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        async for _ in lifespan_with_callback(app, startup_callback, shutdown_callback):
            yield
    
    return _lifespan
