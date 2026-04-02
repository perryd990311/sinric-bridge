"""WiFi SSID Service Handler — toggles UniFi WiFi broadcasts via the integration API."""

import asyncio
import logging
import os
from typing import Any

from core.utils.http import HTTPClient, create_insecure_ssl_context
from core.utils.json_helpers import normalize_response
from services.base_handler import ServiceHandler

logger = logging.getLogger(__name__)

_WLAN_READ_ONLY = {"id", "metadata"}


class WiFiSSIDHandler(ServiceHandler):
    """Manages a single UniFi WiFi broadcast (SSID) via the integration API.

    Reads the following global env vars at runtime (not at init-time):
        UNIFI_HOST      - UniFi controller hostname/IP (default: 192.168.1.1)
        UNIFI_API_KEY   - UniFi integration API key
        UNIFI_SITE_ID   - UniFi site UUID

    Required config keys (from SERVICES_CONFIG entry):
        wlan_id - UUID of the WiFi broadcast to control
    """

    def __init__(self, device_id: str, service_type: str, config: dict):
        super().__init__(device_id, service_type, config)
        self._http = HTTPClient(
            ssl_context=create_insecure_ssl_context(),
            logger_instance=logger,
        )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _get_wlan_path(self) -> str:
        site_id = os.getenv("UNIFI_SITE_ID") or os.getenv("UNIFI_SITE", "")
        if not site_id:
            raise ValueError("UNIFI_SITE_ID not set")
        wlan_id = self.config.get("wlan_id", "")
        if not wlan_id:
            raise ValueError(f"wlan_id not configured for device {self.device_id!r}")
        return f"/proxy/network/integration/v1/sites/{site_id}/wifi/broadcasts/{wlan_id}"

    def _unifi_request(self, method: str, path: str, payload: dict | None = None) -> dict:
        api_key = os.getenv("UNIFI_API_KEY", "")
        if not api_key:
            raise ValueError("UNIFI_API_KEY not set")
        host = os.getenv("UNIFI_HOST", "192.168.1.1")
        url = f"https://{host}{path}"
        return self._http.request(
            method,
            url,
            data=payload,
            headers={"X-API-KEY": api_key},
        )

    # ── Public interface ──────────────────────────────────────────────────────

    async def get_details(self) -> dict:
        """Return the raw UniFi WiFi broadcast configuration."""
        return await asyncio.to_thread(self._unifi_request, "GET", self._get_wlan_path())

    async def get_state(self) -> Any:
        """Return current SSID enabled state as bool."""
        details = await self.get_details()
        payload = normalize_response(details, _WLAN_READ_ONLY)
        return bool(payload.get("enabled", False))

    async def _set_wlan_state(self, enabled: bool) -> dict:
        details = await self.get_details()
        wlan = normalize_response(details, _WLAN_READ_ONLY)
        wlan["enabled"] = enabled
        return await asyncio.to_thread(self._unifi_request, "PUT", self._get_wlan_path(), wlan)

    async def handle_action(self, action: str, value: dict) -> dict:
        """Process Sinric action.  Only 'setPowerState' is supported."""
        if action == "setPowerState":
            state_str = value.get("state", "")
            enabled = state_str.lower() == "on"
            try:
                await self._set_wlan_state(enabled)
                return {
                    "success": True,
                    "message": "OK",
                    "value": {"state": "On" if enabled else "Off"},
                }
            except Exception:
                logger.exception(
                    "WiFiSSIDHandler: failed to set state for device %s", self.device_id
                )
                return {
                    "success": False,
                    "message": "Failed to set WLAN state",
                    "value": {"state": state_str.capitalize() if state_str else ""},
                }

        return {
            "success": False,
            "message": f"Unsupported action: {action!r}",
            "value": {},
        }

    async def verify_configuration(self) -> bool:
        """Check that wlan_id is present in config."""
        if not self.config.get("wlan_id"):
            logger.error("Device %r has no wlan_id in config", self.device_id)
            return False
        return True
