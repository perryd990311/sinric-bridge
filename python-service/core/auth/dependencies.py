"""Authentication and authorization utilities for FastAPI."""

from typing import List, Optional, Union

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader
import ipaddress

# Create the security scheme once (consumed by dependency functions)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def verify_token(
    key: str = Security(_api_key_header),
    expected_token: Optional[str] = None,
) -> str:
    """FastAPI dependency to verify X-API-Key header.
    
    Use as a dependency in FastAPI route handlers:
    
        @app.get("/protected")
        async def protected_endpoint(_token: str = Depends(verify_token)):
            ...
    
    Args:
        key: API key from X-API-Key header (injected by FastAPI)
        expected_token: Expected token value to validate against.
                       If None, will raise 500 error.
        
    Returns:
        The verified API key
        
    Raises:
        HTTPException: 
            - 500 if API_TOKEN not configured
            - 403 if key doesn't match expected_token
    """
    if not expected_token:
        raise HTTPException(status_code=500, detail="API_TOKEN not configured")
    if key != expected_token:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return key


def verify_local_network(
    request: Request,
    allowed_networks: Optional[
        List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]
    ] = None,
) -> None:
    """FastAPI dependency to verify request comes from allowed network.
    
    Use as a dependency in FastAPI route handlers:
    
        @app.get("/local-only")
        async def local_endpoint(
            request: Request,
            _net: None = Depends(verify_local_network),
        ):
            ...
    
    Args:
        request: FastAPI Request object
        allowed_networks: List of allowed IPv4Network/IPv6Network objects.
                         If None or empty, allows all.
        
    Raises:
        HTTPException: 403 if client IP not in allowed networks
        
    Example:
        >>> from core.utils import parse_allowed_networks
        >>> networks = parse_allowed_networks("127.0.0.1,192.168.0.0/16")
        >>> @app.get("/local")
        >>> async def local_endpoint(
        ...     request: Request,
        ...     _: None = Depends(
        ...         lambda r: verify_local_network(r, networks)
        ...     )
        ... ):
        ...     return {"ok": True}
    """
    if not allowed_networks:
        # No restrictions if networks list is empty
        return
    
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied — invalid IP")
    
    is_allowed = any(addr in net for net in allowed_networks)
    if not is_allowed:
        raise HTTPException(
            status_code=403,
            detail="Access denied — local network only",
        )
