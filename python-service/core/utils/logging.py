"""Logging utilities for home automation services."""

import logging


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with standard format.
    
    Format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
        
    Example:
        >>> logger = get_logger("my_service")
        >>> logger.info("Service started")
        2025-04-02 10:15:30,123 [INFO] my_service: Service started
    """
    logger = logging.getLogger(name)
    
    # Only configure if this logger doesn't have handlers yet
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger
