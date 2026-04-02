# Adding New Service Types

This guide walks through creating a new handler for any device you want to
control through the Sinric Pro → home-automation bridge.

---

## Architecture Overview

Each device type is a Python class that inherits `ServiceHandler`. The service
loads them at startup from `SERVICES_CONFIG` and routes Sinric Pro commands to
the right handler.

```
SERVICES_CONFIG (env var, JSON)
         │
         ▼
   _build_handlers()  [main.py]
         │   looks up type → class in _SERVICE_HANDLER_CLASSES
         │   instantiates handler, runs verify_configuration()
         ▼
   HANDLERS dict  {device_id → ServiceHandler instance}
      │                  │
      │  WebSocket        │  FastAPI REST
      │  (Sinric Pro)     │  (local LAN)
      ▼                  ▼
  handle_action()    get_state() / get_details()
      │
      ▼
  Downstream API (UniFi, HTTP, GPIO, etc.)
```

---

## Step-by-Step: Add a New Service Type

### 1. Create `services/my_service_handler.py`

Inherit from `ServiceHandler` and import what you need:

```python
# python-service/services/my_service_handler.py
import logging
from typing import Any
from services.base_handler import ServiceHandler

logger = logging.getLogger(__name__)


class MyServiceHandler(ServiceHandler):
    """Controls a hypothetical device via HTTP."""

    async def handle_action(self, action: str, value: dict) -> dict:
        ...

    async def get_state(self) -> Any:
        ...
```

### 2. Implement `handle_action` and `get_state`

Both are required (abstract). See the [Handler Contract](#handler-contract) section below.

### 3. Register the handler class in `main.py`

Find `_SERVICE_HANDLER_CLASSES` in `main.py` and add your entry:

```python
from services.my_service_handler import MyServiceHandler

_SERVICE_HANDLER_CLASSES: dict = {
    "wifi_ssid": WiFiSSIDHandler,
    "my_service": MyServiceHandler,   # ← add this
}
```

### 4. Add any env vars your handler needs

Document required env vars at the top of your handler file. Read them at
call-time (inside methods, not `__init__`) so they can be overridden in tests:

```python
import os

def _get_api_url(self) -> str:
    host = os.getenv("MY_DEVICE_HOST", "192.168.1.50")
    return f"http://{host}/api"
```

### 5. Add an entry to `SERVICES_CONFIG`

```json
[
  {
    "device_id": "my-device-uuid",
    "type": "my_service",
    "name": "My Device",
    "config": {
      "required_key": "value"
    }
  }
]
```

---

## Handler Contract

All three return values are enforced by `main.py` — use exactly these shapes.

### `handle_action(action: str, value: dict) -> dict`

Called by both the Sinric Pro WebSocket loop and the local REST API.

**Must return:**
```python
{
    "success": True,          # bool — did the operation succeed?
    "message": "OK",          # str  — human-readable status
    "value": {"state": "On"}, # dict — echoed back in the Sinric Pro response
}
```

On any unexpected exception, catch it, log it, and return `success=False`.
Never let an exception escape — the WebSocket loop will catch it, but the Sinric
device will appear to malfunction.

### `get_state() -> Any`

Return the raw current state of the device. The type depends on your device:
- Switch / SSID: `bool` (`True` = on/enabled)
- Lock: `str` (`"locked"` / `"unlocked"`)
- Garage door: `bool` (`True` = open)
- Thermostat: `float` (temperature)

### `get_details() -> dict`

Optional. Override to return richer info (raw API response, multiple fields).
Default implementation returns `{"state": await self.get_state()}`.

### `verify_configuration() -> bool`

Optional but strongly recommended. Called once at startup. Return `False` (do
not raise) to prevent the handler from being registered.

### `cleanup() -> None`

Optional. Called on service shutdown. Use to close connections or release
resources.

---

## Complete Example: GarageDoorHandler

A full working skeleton for a garage door opener that exposes a simple HTTP API.

```python
# python-service/services/garage_door_handler.py
"""Garage door handler — controls an HTTP-based garage door opener."""

import logging
import os
from typing import Any

import requests

from services.base_handler import ServiceHandler

logger = logging.getLogger(__name__)


class GarageDoorHandler(ServiceHandler):
    """Controls a garage door via a local HTTP API.

    Required config keys:
        host  - IP or hostname of the garage door controller

    Optional config keys:
        port  - HTTP port (default: 80)

    Required env vars:
        GARAGE_API_TOKEN  - Bearer token for the controller API
    """

    def _base_url(self) -> str:
        host = self.config.get("host", "")
        port = self.config.get("port", 80)
        return f"http://{host}:{port}"

    def _token_header(self) -> dict:
        token = os.getenv("GARAGE_API_TOKEN", "")
        if not token:
            raise ValueError("GARAGE_API_TOKEN not set")
        return {"Authorization": f"Bearer {token}"}

    # ── State ─────────────────────────────────────────────────────────────────

    async def get_state(self) -> Any:
        """Return True if the door is open, False if closed."""
        import asyncio
        return await asyncio.to_thread(self._fetch_state)

    def _fetch_state(self) -> bool:
        resp = requests.get(
            f"{self._base_url()}/status",
            headers=self._token_header(),
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()      # expects {"state": "open"} or {"state": "closed"}
        return data.get("state", "closed").lower() == "open"

    async def get_details(self) -> dict:
        import asyncio
        raw = await asyncio.to_thread(
            lambda: requests.get(
                f"{self._base_url()}/status",
                headers=self._token_header(),
                timeout=5,
            ).json()
        )
        return raw

    # ── Actions ───────────────────────────────────────────────────────────────

    async def handle_action(self, action: str, value: dict) -> dict:
        """Handle Sinric Pro garage door actions.

        Sinric sends action="setMode" with value={"mode": "Open"} or {"mode": "Close"}.
        """
        if action == "setMode":
            mode = value.get("mode", "").lower()  # "open" or "close"
            if mode not in ("open", "close"):
                return {
                    "success": False,
                    "message": f"Unknown mode: {mode!r}",
                    "value": {},
                }
            try:
                import asyncio
                await asyncio.to_thread(self._send_command, mode)
                return {
                    "success": True,
                    "message": "OK",
                    "value": {"mode": mode.capitalize()},
                }
            except Exception as exc:
                logger.exception(
                    "GarageDoorHandler: failed to %s door for device %s",
                    mode, self.device_id,
                )
                return {
                    "success": False,
                    "message": str(exc),
                    "value": {},
                }

        return {
            "success": False,
            "message": f"Unsupported action: {action!r}",
            "value": {},
        }

    def _send_command(self, command: str) -> None:
        """POST /command with {"action": "open"} or {"action": "close"}."""
        resp = requests.post(
            f"{self._base_url()}/command",
            json={"action": command},
            headers=self._token_header(),
            timeout=10,
        )
        resp.raise_for_status()

    # ── Validation ────────────────────────────────────────────────────────────

    async def verify_configuration(self) -> bool:
        if not self.config.get("host"):
            logger.error("Device %r: missing required config key 'host'", self.device_id)
            return False
        if not os.getenv("GARAGE_API_TOKEN"):
            logger.error("Device %r: GARAGE_API_TOKEN env var not set", self.device_id)
            return False
        return True
```

### Register in `main.py`

```python
from services.garage_door_handler import GarageDoorHandler

_SERVICE_HANDLER_CLASSES: dict = {
    "wifi_ssid": WiFiSSIDHandler,
    "garage_door": GarageDoorHandler,
}
```

### Add to `SERVICES_CONFIG`

```json
[
  {
    "device_id": "garage-main-uuid",
    "type": "garage_door",
    "name": "Main Garage",
    "config": {
      "host": "192.168.1.75",
      "port": 8080
    }
  }
]
```

---

## Testing Your Handler

Test the REST API before connecting to Sinric. The local endpoints mirror every
action `handle_action` supports.

**List registered services (confirm your handler loaded):**
```bash
curl http://localhost:8000/services
```

**Get current state:**
```bash
curl http://localhost:8000/service/garage-main-uuid/details \
  -H "X-API-Key: $API_TOKEN"
```

**Trigger an action manually:**
```bash
# For switch-type handlers:
curl -X POST http://localhost:8000/service/my-device-uuid/on \
  -H "X-API-Key: $API_TOKEN"

curl -X POST http://localhost:8000/service/my-device-uuid/off \
  -H "X-API-Key: $API_TOKEN"
```

> **Note:** The `/on` and `/off` endpoints call `handle_action("setPowerState", ...)`
> under the hood. For handlers that use different action names (e.g., `setMode`),
> test them via a real Sinric Pro command or by temporarily adding a test endpoint.

**Check logs** for handler errors:
```bash
docker compose logs -f wifi-toggle | grep -E "ERROR|WARNING|garage"
```

---

## Supported Sinric Pro Device Types

Sinric Pro sends different action names depending on the virtual device type you
created in the portal. Match `action` strings in your `handle_action` accordingly.

| Sinric device type | Action name | `value` dict |
|---|---|---|
| Switch | `setPowerState` | `{"state": "On"}` / `{"state": "Off"}` |
| Toggle Switch | `setPowerState` | `{"state": "On"}` / `{"state": "Off"}` |
| Dimmable Switch | `setPowerState` / `setBrightness` | `{"brightness": 75}` |
| Lock | `setLockState` | `{"state": "lock"}` / `{"state": "unlock"}` |
| Garage Door | `setMode` | `{"mode": "Open"}` / `{"mode": "Close"}` |
| Thermostat | `targetTemperature` / `setThermostatMode` | `{"temperature": 22.0}` |
| Contact Sensor | state updates only (no inbound action) | — |

For the full list see the [Sinric Pro device types docs](https://sinricpro.github.io/esp8266-esp32-sdk/).
