"""Cryptographic utilities for HMAC signing and verification."""

import base64
import hashlib
import hmac
import json
from typing import Any, Dict


class HMACHelper:
    """HMAC-SHA256 signing and verification for JSON payloads.
    
    Designed to work with services like Sinric Pro that use HMAC signatures
    for message authentication.
    """
    
    def __init__(self, secret: str) -> None:
        """Initialize with a shared secret.
        
        Args:
            secret: Shared secret string (typically an app secret or API key)
            
        Example:
            >>> helper = HMACHelper("my-secret-key")
        """
        self.secret = secret
    
    def sign(self, payload: Dict[str, Any]) -> str:
        """Compute HMAC-SHA256 of payload JSON and return Base64-encoded digest.
        
        Uses compact JSON serialization (no whitespace) with sort_keys=False
        to match standard Sinric Pro SDK behavior.
        
        Args:
            payload: Dictionary to sign
            
        Returns:
            Base64-encoded HMAC-SHA256 digest
            
        Example:
            >>> helper = HMACHelper("secret")
            >>> signature = helper.sign({"deviceId": "abc123", "action": "on"})
            >>> print(signature)
            L7h8K9...==
        """
        payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=False)
        digest = hmac.new(
            self.secret.encode("utf-8"),
            payload_str.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("utf-8")
    
    def verify(self, message: Dict[str, Any]) -> bool:
        """Verify HMAC signature of incoming message.
        
        Expects message structure:
        {
            "payload": {...},
            "signature": {"HMAC": "base64_string"}
        }
        
        Uses timing-safe comparison to prevent timing attacks.
        
        Args:
            message: Message dict with "payload" and "signature" fields
            
        Returns:
            True if signature is valid, False otherwise
            
        Example:
            >>> msg = {
            ...     "payload": {"deviceId": "abc", "action": "on"},
            ...     "signature": {"HMAC": "..."}
            ... }
            >>> helper = HMACHelper("secret")
            >>> is_valid = helper.verify(msg)
        """
        remote_hmac = (message.get("signature") or {}).get("HMAC") or ""
        payload = message.get("payload")
        
        if not remote_hmac or not isinstance(payload, dict):
            return False
        
        computed_hmac = self.sign(payload)
        return hmac.compare_digest(remote_hmac, computed_hmac)
