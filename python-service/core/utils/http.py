"""HTTP client utilities for making authenticated requests with custom SSL contexts."""

import json
import logging
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


def create_insecure_ssl_context() -> ssl.SSLContext:
    """Create an SSL context that skips hostname and certificate verification.
    
    Useful for self-signed certificates in trusted LAN environments.
    Use with caution — only for infrastructure you control.
    
    Returns:
        ssl.SSLContext configured to skip verification
        
    Example:
        >>> ctx = create_insecure_ssl_context()
        >>> client = HTTPClient(ssl_context=ctx)
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class HTTPClient:
    """Generic HTTP client with header support and error handling.
    
    Makes synchronous HTTP requests with custom headers and optional SSL context.
    Handles JSON serialization/deserialization and provides detailed error logging.
    """
    
    def __init__(
        self,
        ssl_context: Optional[ssl.SSLContext] = None,
        headers: Optional[Dict[str, str]] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """Initialize HTTPClient.
        
        Args:
            ssl_context: Optional custom SSL context (e.g., with cert verification disabled)
            headers: Optional default headers dict to include in all requests
            logger_instance: Optional logger instance for this client (defaults to module logger)
        """
        self.ssl_context = ssl_context
        self.headers = headers or {}
        self.logger = logger_instance or logger
    
    def request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request and return parsed JSON response.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            url: Full URL to request
            data: Optional dict to JSON-encode and send as request body
            headers: Optional dict of headers to merge with default headers
            
        Returns:
            Parsed JSON response as dict
            
        Raises:
            urllib.error.HTTPError: On non-2xx HTTP status codes
            json.JSONDecodeError: If response body is not valid JSON
            ValueError: If required configuration is missing
            
        Example:
            >>> client = HTTPClient(headers={"X-API-KEY": "secret"})
            >>> result = client.request("GET", "https://api.example.com/status")
            >>> print(result)
        """
        if not url:
            raise ValueError("URL is required")
        
        # Prepare request body
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
        
        # Merge headers
        req_headers = {**self.headers}
        if headers:
            req_headers.update(headers)
        
        # Ensure Content-Type and Accept for JSON
        req_headers.setdefault("Content-Type", "application/json")
        req_headers.setdefault("Accept", "application/json")
        
        # Create request
        req = urllib.request.Request(
            url,
            data=body,
            headers=req_headers,
            method=method,
        )
        
        # Build opener with SSL context if provided
        handlers = []
        if self.ssl_context:
            handlers.append(urllib.request.HTTPSHandler(context=self.ssl_context))
        opener = urllib.request.build_opener(*handlers)
        
        # Execute request
        try:
            with opener.open(req) as resp:
                response_body = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            response_body = exc.read()
            status = exc.code
            self.logger.error(
                "HTTP %s %s → %d: %s",
                method,
                url,
                status,
                response_body[:500].decode(errors="replace"),
            )
            raise
        
        # Parse response
        if not response_body:
            return {}
        
        try:
            return json.loads(response_body)
        except json.JSONDecodeError:
            self.logger.error(
                "HTTP %s %s → %d returned non-JSON: %s",
                method,
                url,
                status,
                response_body[:500].decode(errors="replace"),
            )
            raise
