"""JSON response normalization utilities."""

from typing import Any, Dict, Set


def normalize_response(
    data: Dict[str, Any],
    read_only_fields: Set[str],
) -> Dict[str, Any]:
    """Normalize API response by removing read-only fields.
    
    Useful when an API returns metadata with GET responses that are not
    valid in PUT/PATCH requests. Handles nested "data" responses.
    
    Args:
        data: Response data (may be wrapped in {"data": ...} structure)
        read_only_fields: Set of field names to exclude (e.g., {"id", "metadata"})
        
    Returns:
        Normalized dict with read-only fields removed
        
    Example:
        >>> response = {
        ...     "id": "123",
        ...     "name": "WiFi",
        ...     "enabled": True,
        ...     "metadata": {"created_at": "2025-01-01"}
        ... }
        >>> normalized = normalize_response(response, {"id", "metadata"})
        >>> print(normalized)
        {"name": "WiFi", "enabled": True}
    """
    # Unwrap nested response structures (some APIs wrap in {"data": {...}})
    if isinstance(data.get("data"), list) and data["data"]:
        data = data["data"][0]
    elif isinstance(data.get("data"), dict):
        data = data["data"]
    
    # Filter out read-only fields
    return {k: v for k, v in data.items() if k not in read_only_fields}
